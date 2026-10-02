# -*- coding: utf-8 -*-
"""BLOCK 1 · SEMÁNTICA DEL ESTADO DE RIESGO — prueba BLOQUEANTE (offline).

Reglas §17/§18/§19 sobre los cuatro atributos de riesgo:

  · remoción / riesgo con resultado espacial y geometría evaluada
        ⇒ NO pueden quedar `NOT_EVALUATED`;
  · inundación cuyas capas están `enabled=false`
        ⇒ `SOURCE_UNAVAILABLE` (ausencia declarada) con el MOTIVO exacto, nunca
          «NO EVALUADO» como cajón general;
  · riesgo no mitigable sin escalón declarado en la cobertura
        ⇒ `NOT_SUPPORTED` con el motivo, nunca `NOT_EVALUATED`;
  · el chip del panel de riesgos tiene rama BAJA/BAJO (RSK-4: caía en `NO_EVALUADO`).
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))

import attribute_truth as at  # noqa: E402
import dictus_ejecutivo as de  # noqa: E402
import dictus_sources as ds  # noqa: E402
import source_resolution as sr  # noqa: E402

RUN_STATE = (ROOT / "docs" / "forensics" / "040-646406" / "dictus_2b"
             / "DICTUS_RUN_STATE_040-646406.json")


def _registro_golden():
    if not RUN_STATE.exists():
        return None
    rs = json.loads(RUN_STATE.read_text(encoding="utf-8"))
    rs["geometry_state"] = {"evaluado": True, "modo": "PACKAGED_GEOMETRY_QUERY",
                            "layers_available": True}
    return at.resolver_atributos(rs, fecha="2026-10-01")


class TestEstadoDeRiesgo(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.registro = _registro_golden()
        if cls.registro is None:
            raise unittest.SkipTest("no está el run state del Golden")

    def test_remocion_con_resultado_espacial_no_es_not_evaluated(self):
        ficha = self.registro["attributes"]["remocion"]
        self.assertTrue(ficha["spatial_result_available"])
        self.assertTrue(ficha["geometry_evaluated"])
        self.assertNotEqual(ficha["fact_status"], at.NOT_EVALUATED)
        self.assertTrue(ficha["source_selected"])

    def test_riesgo_con_resultado_espacial_no_es_not_evaluated(self):
        ficha = self.registro["attributes"]["riesgo"]
        self.assertTrue(ficha["spatial_result_available"])
        self.assertNotEqual(ficha["fact_status"], at.NOT_EVALUATED)

    def test_inundacion_declara_la_ausencia_con_su_motivo(self):
        ficha = self.registro["attributes"]["inundacion"]
        self.assertEqual(ficha["resolution_status"], at.SOURCE_UNAVAILABLE)
        self.assertEqual(ficha["fact_status"], at.SOURCE_UNAVAILABLE)
        self.assertNotEqual(ficha["fact_status"], at.NOT_EVALUATED)
        self.assertIsNone(ficha["source_selected"])
        motivos = " ".join(str(i.get("rejected_reason") or "")
                           for i in ficha["source_attempts"])
        self.assertTrue(motivos.strip(), "la ausencia tiene que declarar el motivo")
        estados = {i["status"] for i in ficha["source_attempts"]}
        self.assertTrue(estados & {ds.NO_SOPORTADA, ds.FUENTE_NO_DISPONIBLE}, estados)

    def test_riesgo_no_mitigable_es_not_supported_con_motivo(self):
        ficha = self.registro["attributes"]["riesgo_no_mitigable"]
        self.assertEqual(ficha["resolution_status"], at.NOT_SUPPORTED)
        self.assertEqual(ficha["fact_status"], at.NOT_SUPPORTED)
        self.assertNotEqual(ficha["fact_status"], at.NOT_EVALUATED)
        self.assertIn("escalón", ficha["canonical_reason"])
        self.assertIn("NOT_EVALUATED", ficha["canonical_reason"])

    def test_ninguna_ausencia_se_llama_no_evaluado_de_forma_generica(self):
        for atributo in ("inundacion", "riesgo_no_mitigable", "uso_pot", "clase_suelo"):
            ficha = self.registro["attributes"][atributo]
            self.assertNotEqual(ficha["fact_status"], at.NOT_EVALUATED, atributo)
            self.assertTrue(ficha["canonical_reason"], atributo)

    def test_la_geometria_evaluada_se_persiste_en_el_estado_del_atributo(self):
        for atributo in ("remocion", "riesgo", "inundacion", "riesgo_no_mitigable"):
            self.assertTrue(self.registro["attributes"][atributo]["geometry_evaluated"],
                            atributo)


class TestChipDeRiesgo(unittest.TestCase):
    """RSK-4: el vocabulario del chip no tenía el escalón BAJO."""

    def test_una_baja_declarada_no_se_rotula_no_evaluado(self):
        self.assertEqual(de._chip_de_riesgo("Baja · polígono: intersecta el predio"),
                         "RIESGO_BAJO")
        self.assertEqual(de._chip_de_riesgo("Bajo"), "RIESGO_BAJO")

    def test_los_demas_escalones_se_conservan(self):
        self.assertEqual(de._chip_de_riesgo("Alta"), "RIESGO_ALTO")
        self.assertEqual(de._chip_de_riesgo("Media"), "RIESGO_MEDIO")
        self.assertEqual(de._chip_de_riesgo("Sin afectación"), "SIN_AFECTACION")

    def test_sin_nivel_no_evaluado_solo_cuando_nada_se_evaluo(self):
        self.assertEqual(de._chip_de_riesgo(None), "NO_EVALUADO")
        self.assertEqual(de._chip_de_riesgo(""), "NO_EVALUADO")

    def test_un_nivel_desconocido_declara_evaluado_y_no_no_evaluado(self):
        self.assertEqual(de._chip_de_riesgo("Zonificación especial"),
                         "EVALUADO")

    def test_los_chips_declarados_tienen_su_etiqueta_de_render(self):
        for chip in ("RIESGO_ALTO", "RIESGO_MEDIO", "RIESGO_BAJO", "SIN_AFECTACION",
                     "NO_EVALUADO", "EVALUADO"):
            self.assertIn(chip, de._ESTADOS_VISUALES, chip)


class TestEscaleraDeRiesgoNoInventa(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.reg = ds.cargar_registro()
        if cls.reg.get("_status") == ds.NO_SOPORTADA:
            raise unittest.SkipTest("el registro del Source Pack aún no está generado")

    def test_una_fuente_deshabilitada_se_declara_not_supported(self):
        """El pack declara «fuente deshabilitada → NOT_SUPPORTED»: nunca NO_MATCH."""
        for sid in ("POT_BAQ_INUNDACION_2024", "POT_BAQ_INUNDACION_HIST",
                    "POT_BAQ_AREAS_ACTIVIDAD", "POT_BAQ_POLIGONOS_USO"):
            fuente = (self.reg.get("sources") or {}).get(sid) or {}
            self.assertIs(fuente.get("enabled"), False, sid)

    def test_la_ausencia_de_inundacion_no_se_convierte_en_no_match(self):
        r = sr.resolver_atributo("inundacion", consultas={}, registro=self.reg,
                                 fecha="2026-09-29")
        self.assertNotEqual(r["resolution_status"], ds.SIN_COINCIDENCIA)
        self.assertIn(r["resolution_status"], (sr.SOURCE_UNAVAILABLE, sr.UNRESOLVED))
        for intento in r["attempts"]:
            self.assertNotEqual(intento["status"], ds.SIN_COINCIDENCIA)


if __name__ == "__main__":
    unittest.main()

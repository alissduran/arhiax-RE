# -*- coding: utf-8 -*-
"""BLOCK 1 · BINDING DE GEOMETRÍA — prueba BLOQUEANTE (offline).

§11: un binding de IDENTIFICADORES (`NATIONAL_IDENTIFIERS`: nupre / numero_predial) NO
acredita que la GEOMETRÍA sea la del predio, y un **geocode de dirección NUNCA equivale a
geometría oficial del predio**.

Mientras no exista polígono oficial del predio + comparación geométrica con criterio +
segunda geometría independiente + relaciones `cr_construccion_guid`/`cr_terreno_guid` +
geometría de la unidad + CRS declarado, el documento NO puede rotular el binding como
«binding de la geometría oficial: VERIFICADA»: se declara el alcance REAL y lo que falta.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))

import attribute_truth as at  # noqa: E402

RUN_STATE = (ROOT / "docs" / "forensics" / "040-646406" / "dictus_2b"
             / "DICTUS_RUN_STATE_040-646406.json")

MC_GOLDEN_PROV = {
    "source_system": "CATASTRO_MUNICIPAL_BARRANQUILLA_ARCGIS",
    "layer": "105 · direccion",
    "feature_id": "6c663607-5509-401f-b57d-384d2beeeac1",
    "feature_id_kind": "cr_predio_guid",
    "geometry_type": "Point",
    "resolution_method": "DIRECCION_OFICIAL_LIGADA_POR_GUID",
    "predio_globalid": "6c663607-5509-401f-b57d-384d2beeeac1",
    "link_verificado": True,
    "canonical_binding_status": "VERIFIED",
    "canonical_binding_fields": ["nupre", "numero_predial"],
    "canonical_binding_scope": "NATIONAL_IDENTIFIERS",
}


def _mc(prov, binding="VERIFIED", scope="NATIONAL_IDENTIFIERS"):
    return {"coordinate_source": "OFFICIAL_PREDIO", "coordinate_source_verified": True,
            "canonical_binding_status": binding, "canonical_binding_scope": scope,
            "canonical_binding_fields": ["nupre", "numero_predial"],
            "coordinate_provenance": prov}


class TestProcedenciaGeometrica(unittest.TestCase):

    def test_un_punto_de_la_capa_de_direccion_no_es_la_geometria_del_predio(self):
        categoria = at.clasificar_procedencia_geometrica(_mc(MC_GOLDEN_PROV))
        self.assertEqual(categoria["categoria"], at.PUNTO_OFICIAL_DE_DIRECCION)
        self.assertFalse(categoria["es_geometria_del_predio"])
        self.assertIn("DIRECCIÓN", categoria["motivo"])

    def test_un_geocode_de_direccion_nunca_pasa_por_official_predio(self):
        geocode = dict(MC_GOLDEN_PROV, source_system="NOMINATIM",
                       resolution_method="GEOCODE_DIRECCION", layer="address points",
                       geometry_type="Point")
        categoria = at.clasificar_procedencia_geometrica(_mc(geocode))
        self.assertEqual(categoria["categoria"], at.GEOCODE_DIRECCION)
        self.assertTrue(categoria["es_geocode_de_direccion"])
        self.assertFalse(categoria["es_geometria_del_predio"])
        self.assertIn("NUNCA", categoria["motivo"].upper() + " NUNCA")

    def test_solo_un_poligono_oficial_del_predio_es_geometria_del_predio(self):
        poligono = dict(MC_GOLDEN_PROV, layer="315 · terreno", geometry_type="Polygon",
                        resolution_method="RELACION_OFICIAL_PREDIO")
        categoria = at.clasificar_procedencia_geometrica(_mc(poligono))
        self.assertEqual(categoria["categoria"], at.GEOMETRIA_OFICIAL_PREDIO)
        self.assertTrue(categoria["es_geometria_del_predio"])

    def test_sin_procedencia_declarada_no_se_afirma_geometria(self):
        categoria = at.clasificar_procedencia_geometrica({})
        self.assertEqual(categoria["categoria"], at.SIN_GEOMETRIA)


class TestBindingDeclarado(unittest.TestCase):

    def test_el_binding_del_golden_no_se_rotula_como_geometrico(self):
        """El alcance declarado es `NATIONAL_IDENTIFIERS`: es un binding de IDENTIFICADORES."""
        info = at.binding_geometria(_mc(MC_GOLDEN_PROV))
        self.assertFalse(info["es_binding_geometrico"])
        self.assertEqual(info["estado"], "IDENTIFICADORES")
        self.assertNotIn("Binding de la geometría oficial", info["etiqueta"])
        self.assertIn("identidad canónica", info["etiqueta"])
        self.assertEqual(info["fact_status"], at.KNOWN_BUT_UNVERIFIED)
        self.assertNotEqual(info["fact_status"], at.VERIFIED)

    def test_declara_exactamente_que_falta_para_un_binding_geometrico(self):
        info = at.binding_geometria(_mc(MC_GOLDEN_PROV))
        faltantes = info["faltantes_para_verified_geometrico"]
        self.assertGreaterEqual(len(faltantes), 8)
        texto = " ".join(faltantes).lower()
        for exigencia in ("polígono oficial del predio", "comparación geométrica",
                          "segunda geometría", "cr_construccion_guid", "cr_terreno_guid",
                          "crs", "unidad"):
            self.assertIn(exigencia, texto, exigencia)

    def test_el_detalle_nombra_el_alcance_y_los_faltantes(self):
        info = at.binding_geometria(_mc(MC_GOLDEN_PROV))
        self.assertIn("NATIONAL_IDENTIFIERS", info["detalle"])
        self.assertIn("NO acredita", info["detalle"])

    def test_un_binding_geometrico_real_si_se_rotula_verificado(self):
        prov = dict(MC_GOLDEN_PROV, layer="315 · terreno", geometry_type="Polygon",
                    resolution_method="RELACION_OFICIAL_PREDIO")
        info = at.binding_geometria(_mc(prov, scope="OFFICIAL_PREDIO_GEOMETRY"))
        self.assertTrue(info["es_binding_geometrico"])
        self.assertEqual(info["estado"], "VERIFICADA")
        self.assertEqual(info["fact_status"], at.VERIFIED)

    def test_el_geocode_se_advierte_en_el_detalle_del_binding(self):
        geocode = dict(MC_GOLDEN_PROV, source_system="NOMINATIM",
                       resolution_method="GEOCODE", layer="geocode")
        info = at.binding_geometria(_mc(geocode))
        self.assertIn("GEOCODE", info["detalle"])

    def test_el_registro_del_golden_declara_el_binding_sin_sobre_alcance(self):
        if not RUN_STATE.exists():
            raise unittest.SkipTest("no está el run state del Golden")
        rs = json.loads(RUN_STATE.read_text(encoding="utf-8"))
        registro = at.resolver_atributos(rs, fecha="2026-10-01")
        ficha = registro["attributes"]["binding_geometria"]
        self.assertFalse(ficha["binding"]["es_binding_geometrico"])
        self.assertNotEqual(ficha["fact_status"], at.VERIFIED)
        self.assertEqual(ficha["resolution_status"], at.UNRESOLVED)
        self.assertTrue(ficha["canonical_reason"])


if __name__ == "__main__":
    unittest.main()

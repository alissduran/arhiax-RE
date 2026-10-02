# -*- coding: utf-8 -*-
"""BLOCK 1 · UNA SOLA VERDAD POR ATRIBUTO — prueba BLOQUEANTE (offline).

Regla §10: un atributo → UN `canonical_value` y UN `canonical_fact_status`. Las páginas
(P1, P4, P5, P6) PROYECTAN esa verdad; ninguna la recrea ni la contradice.

El helper `assert_single_truth_per_attribute()` es el contrato de esta prueba: se ejerce
sobre el registro REAL de la corrida Golden y sobre las SECCIONES REALES que produce el
render (recalculadas offline desde el run state y el manifest del Golden).
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))

import attribute_truth as at  # noqa: E402
import dictus_historia as dh  # noqa: E402
import dictus_secciones as dst  # noqa: E402

GOLDEN = ROOT / "docs" / "forensics" / "040-646406" / "dictus_2b"
RUN_STATE = GOLDEN / "DICTUS_RUN_STATE_040-646406.json"
MANIFEST = GOLDEN / "DICTUS_MANIFEST_040-646406.json"

PAGINAS = ("P1", "P4", "P5", "P6")


def assert_single_truth_per_attribute(registro, secciones=None):
    """Un atributo → un `canonical_value` y un `canonical_fact_status`; las páginas solo
    proyectan esa verdad.

    Comprueba, en este orden:
      1. el vocabulario y la unicidad de `canonical_value`/`canonical_fact_status`;
      2. que el estado de cada fila impresa salga del MISMO `fact_status` (no hay dos
         estados del mismo atributo en el documento);
      3. que un atributo declarado `VERIFIED` declare de dónde sale.
    """
    at.assert_single_truth_per_attribute(registro)
    attrs = registro["attributes"]
    # 1 · una sola clave de valor y de estado por atributo (sin duplicados por alias).
    for alias, ficha in attrs.items():
        origen = ficha.get("alias_de")
        if origen:
            base = attrs.get(origen)
            assert base is not None, f"{alias}: alias de un atributo inexistente"
            assert ficha["canonical_value"] == base["canonical_value"], (
                f"{alias}: el alias declara un valor distinto del atributo del que es alias")
            assert ficha["fact_status"] == base["fact_status"], (
                f"{alias}: el alias declara un estado distinto del atributo del que es alias")
    if secciones is None:
        return
    # 2 · el documento no puede tener dos estados del mismo atributo.
    identidad = secciones.get("identidad") or {}
    por_atributo = {}
    for fila in identidad.get("filas") or []:
        clave = fila.get("atributo_clave")
        if not clave:
            continue
        esperado = at.estado_de_coherencia(registro, clave)
        if esperado is None:
            continue
        assert fila["estado"] == esperado, (
            f"P6 · {clave}: la fila imprime {fila['estado']!r} y la verdad única del "
            f"atributo es {esperado!r}")
        por_atributo.setdefault(clave, set()).add(fila["estado"])
    for clave, estados in por_atributo.items():
        assert len(estados) == 1, f"{clave}: dos estados distintos en la misma corrida"
    # 3 · el resumen de identidad cumple su alcance declarado (§10).
    resumen = identidad.get("identidad_resumen") or {}
    at.assert_resumen_identidad_cumple(registro, resumen)
    if str(resumen.get("estado", "")).startswith("VERIFICADA"):
        assert not resumen.get("degradado_por"), resumen


class TestVerdadUnicaGolden(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not (RUN_STATE.exists() and MANIFEST.exists()):
            raise unittest.SkipTest("no están los artefactos del Golden")
        cls.rs = json.loads(RUN_STATE.read_text(encoding="utf-8"))
        cls.modelo = json.loads(MANIFEST.read_text(encoding="utf-8"))["modelo"]
        hist = dh.reclasificar_informe(
            cls.rs.get("historical_consistency") or {},
            dh.cargar_matriz_del_caso("040-646406"))
        cls.rs["historical_consistency"] = hist
        cls.registro = at.resolver_atributos(cls.rs, historial=hist, fecha="2026-10-01")
        at.aplicar_verdad_al_estado(cls.rs, cls.registro)
        cls.rs[at.CLAVE_RUN_STATE] = cls.registro
        cls.secciones = dst.desde_estado(cls.rs, cls.modelo, hist)

    def test_un_atributo_una_verdad(self):
        assert_single_truth_per_attribute(self.registro, self.secciones)

    def test_todo_atributo_auditado_tiene_ficha(self):
        for atributo in at.ATRIBUTOS:
            self.assertIn(atributo, self.registro["attributes"], atributo)

    def test_ninguna_fila_de_identidad_queda_sin_estado_declarado(self):
        filas = (self.secciones.get("identidad") or {}).get("filas") or []
        self.assertEqual(len(filas), 9)
        for fila in filas:
            self.assertTrue(fila.get("estado"), fila)

    def test_el_resumen_de_identidad_no_contradice_a_sus_componentes(self):
        resumen = (self.secciones.get("identidad") or {}).get("identidad_resumen") or {}
        self.assertIn("alcance_declarado", resumen)
        self.assertTrue(resumen["regla"])
        if resumen["estado"] == "VERIFICADA":
            for componente in resumen["alcance_declarado"]:
                self.assertEqual(resumen["componentes_del_alcance"].get(componente),
                                 dh.VERIFICADO, componente)

    def test_el_barrio_resuelto_es_el_mismo_en_todas_las_paginas(self):
        """Un barrio resuelto por la escalera vale lo mismo en P1, P4 y P5."""
        ficha = self.registro["attributes"]["barrio"]
        self.assertTrue(ficha["source_selected"], "el barrio del Golden está resuelto")
        secciones = self.secciones
        valor_p1 = ((secciones.get("entorno") or {}).get("accesibilidad") or [])[0][1]
        self.assertEqual(str(valor_p1), str(ficha["canonical_value"]))
        p4 = [f for f in (secciones.get("urbano") or {}).get("filas") or []
              if f.get("etiqueta") == "Barrio / sector oficial"]
        p5 = (secciones.get("entorno") or {}).get("accesibilidad") or []
        self.assertEqual(str(p5[0][1]), str(ficha["canonical_value"]))
        if p4:
            self.assertEqual(str(p4[0].get("valor")), str(ficha["canonical_value"]))

    def test_el_estado_de_uso_pot_no_puede_ser_verificado_sin_fuente(self):
        """§4: un valor con estado «verificado» y `source=null` es imposible."""
        ficha = self.registro["attributes"]["uso_pot"]
        self.assertIsNone(ficha["source_selected"])
        self.assertNotEqual(ficha["fact_status"], at.VERIFIED)
        self.assertNotEqual(ficha["resolution_status"], at.RESOLVED_PRIMARY)
        uso = (self.rs.get("market_context") or {}).get("uso") or {}
        self.assertEqual(uso.get("status_declarado_por_la_corrida"), "VERIFIED_OFFICIAL")
        self.assertNotEqual(uso.get("status"), "VERIFIED_OFFICIAL")
        self.assertIsNone(uso.get("source"))


if __name__ == "__main__":
    unittest.main()

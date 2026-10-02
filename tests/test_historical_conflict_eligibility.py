# -*- coding: utf-8 -*-
"""BLOCK 1 · ELEGIBILIDAD DE CONFLICTO HISTÓRICO — prueba BLOQUEANTE (offline).

Un «conflicto histórico» NO es cualquier diferencia entre versiones: exige las SIETE
condiciones (mismo atributo · misma semántica · mismo objeto · vigencia comparable ·
autoridad comparable · valores incompatibles · precedencia que NO resuelve). El recuento
que imprime DICTUS se deriva SOLO de `TRUE_CONFLICT` (puede subir o bajar: no se preserva
por compatibilidad), y cada clasificación queda persistida con su motivo.

Casos mínimos exigidos (§29):
  · histórico ≠ vigente                → NO es conflicto
  · fuentes vigentes de misma semántica que discrepan → `TRUE_CONFLICT`
  · diferencias de CAJA en el titular  → `NORMALIZATION_DIFFERENCE`
  · dos ausencias (`None → None`)      → no es un cambio
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))

import dictus_historia as dh  # noqa: E402

MATRIZ_GOLDEN = (ROOT / "docs" / "forensics" / "040-646406" / "dictus_2"
                 / "ATTRIBUTE_HISTORY_MATRIX.json")


def _version(nombre, fecha_iso="2026-01-01"):
    return {"version": nombre, "fecha": fecha_iso, "origen": f"{nombre}.pdf"}


def _matriz(valores_por_version, atributo="altura_maxima", fuente="altura del edificio según catastro"):
    """Matriz sintética: `valores_por_version` = [(nombre_version, valor|None), ...]."""
    versiones = [_version(n) for n, _ in valores_por_version]
    filas = []
    for (nombre, valor) in valores_por_version:
        for atributo_ in dh._ATRIBUTOS:
            filas.append({"version": nombre, "fecha": "2026-01-01", "atributo": atributo_,
                          "value": valor if atributo_ == atributo else None,
                          "status": "VERIFICADO" if valor is not None else dh.SIN_DATO,
                          "source": fuente if atributo_ == atributo else None,
                          "source_version": None, "query_date": "2026-01-01",
                          "provenance": {}, "identity_binding": "no declarado"})
    cambios = []
    for i in range(1, len(valores_por_version)):
        prev, cur = valores_por_version[i - 1], valores_por_version[i]
        for atributo_ in dh._ATRIBUTOS:
            datos_a = {atributo_: {"value": prev[1]}}
            datos_b = {atributo_: {"value": cur[1]}}
            c = dh.clasificar_cambio(atributo_, datos_a, datos_b)
            if c.get("cambio"):
                c.update({"version_anterior": prev[0], "version_actual": cur[0],
                          "material": atributo_ in dh.ATRIBUTOS_MATERIALES})
                cambios.append(c)
    return {"versiones": versiones, "atributos": sorted(dh._ATRIBUTOS), "filas": filas,
            "cambios": cambios, "conflictos_historicos_abiertos": []}


class TestCondicionesDeConflicto(unittest.TestCase):

    def test_dos_ausencias_no_son_un_cambio(self):
        """`None → None` no es un cambio: antes generaba 13 «cambios» falsos para `area`."""
        matriz = _matriz([("v1", None), ("v2", None), ("v3", None)], atributo="area")
        self.assertEqual(matriz["cambios"], [])
        reporte = dh.reporte_consistencia(matriz)
        self.assertEqual(reporte["conflictos_abiertos"], [])
        self.assertNotIn("area", [r["atributo"] for r in reporte["requieren_revision"]])

    def test_valores_iguales_no_son_cambio(self):
        matriz = _matriz([("v1", "8"), ("v2", "8")])
        self.assertEqual(matriz["cambios"], [])
        self.assertEqual(dh.clasificar_conflicto_historico("altura_maxima", matriz)["veredicto"],
                         dh.NOT_A_CONFLICT)

    def test_vigentes_de_misma_semantica_que_discrepan_son_true_conflict(self):
        matriz = _matriz([("v1", "8"), ("v2", "11")])
        clas = dh.clasificar_conflicto_historico("altura_maxima", matriz)
        self.assertEqual(clas["veredicto"], dh.TRUE_CONFLICT)
        self.assertTrue(clas["abierto"])
        condiciones = clas["condiciones"]
        for nombre in dh.CONDICIONES_CONFLICTO:
            self.assertTrue(condiciones[nombre], f"la condición {nombre} tiene que cumplirse")

    def test_historico_frente_a_vigente_no_es_conflicto(self):
        """Una capa HISTÓRICA no compite con la vigente: diferencia de HISTORIA, no conflicto."""
        matriz = _matriz([("v1", "versión ANTERIOR del POT: 8 pisos"), ("v2", "11")],
                         atributo="altura_maxima", fuente="altura del edificio según catastro")
        clas = dh.clasificar_conflicto_historico("altura_maxima", matriz)
        self.assertEqual(clas["veredicto"], dh.HISTORICAL_CHANGE)
        self.assertEqual(clas["condicion_que_decide"], "4_vigencia_comparable")

    def test_amenaza_historica_la_resuelve_la_precedencia_declarada(self):
        """Si además hay precedencia declarada, la discrepancia tampoco es conflicto."""
        matriz = _matriz([("v1", "versión ANTERIOR del POT: sin afectación"), ("v2", "ALTA")],
                         atributo="amenaza", fuente="capa POT de amenaza")
        clas = dh.clasificar_conflicto_historico("amenaza", matriz)
        self.assertNotEqual(clas["veredicto"], dh.TRUE_CONFLICT)
        self.assertEqual(clas["condicion_que_decide"], "7_precedencia_no_resuelve")

    def test_precedencia_declarada_resuelve_y_no_es_conflicto(self):
        matriz = _matriz([("v1", "AMENAZA BAJA"), ("v2", "AMENAZA MEDIA")],
                         atributo="amenaza", fuente="capa POT de amenaza")
        clas = dh.clasificar_conflicto_historico("amenaza", matriz)
        self.assertEqual(clas["veredicto"], dh.RESOLVED_BY_PRECEDENCE)
        self.assertEqual(clas["condicion_que_decide"], "7_precedencia_no_resuelve")

    def test_semantica_distinta_no_es_conflicto(self):
        matriz = _matriz([("v1", "ACTIVIDAD CENTRAL (Capa 2 - confirmado)"),
                          ("v2", "Habitacional (consulta en vivo)")],
                         atributo="uso_pot", fuente="Uso de Suelo")
        clas = dh.clasificar_conflicto_historico("uso_pot", matriz)
        self.assertEqual(clas["veredicto"], dh.SEMANTIC_DIFFERENCE)
        self.assertEqual(clas["condicion_que_decide"], "2_misma_semantica")

    def test_diferencias_de_caja_en_el_titular_son_normalizacion(self):
        matriz = _matriz([("v1", "Duran Bacca Alisson (CC 1.045.718.995) 50%"),
                          ("v2", "DURAN BACCA ALISSON CC# 1045718995X 50%")],
                         atributo="titulares", fuente=None)
        clas = dh.clasificar_conflicto_historico("titulares", matriz)
        self.assertEqual(clas["veredicto"], dh.NORMALIZATION_DIFFERENCE)
        self.assertEqual(clas["condicion_que_decide"], "6_valores_incompatibles")
        self.assertIn("NO son incompatibles", clas["motivo"])

    def test_cascada_por_punto_distinto_no_duplica_el_defecto(self):
        """Dos versiones que evaluaron PUNTOS distintos: cascada del cambio de geometría."""
        versiones = [("v1", "CONSOLIDACION"), ("v2", "DESARROLLO")]
        versiones_coord = [("v1", "11.00538 -74.83862"), ("v2", "11.00612 -74.83753")]
        versiones_dh = [_version(n) for n, _ in versiones]
        filas = []
        for (nombre, trat), (_, coord) in zip(versiones, versiones_coord):
            for atributo, valor in (("tratamiento", trat), ("coordenada", coord)):
                filas.append({"version": nombre, "fecha": "2026-01-01", "atributo": atributo,
                              "value": valor, "status": "VERIFICADO",
                              "source": "tratamientos urbanísticos (capa POT)",
                              "source_version": None, "query_date": "2026-01-01",
                              "provenance": {}, "identity_binding": "no declarado"})
        matriz = {"versiones": versiones_dh, "atributos": ["tratamiento", "coordenada"],
                  "filas": filas,
                  "cambios": [{"atributo": "tratamiento", "anterior": "CONSOLIDACION",
                               "actual": "DESARROLLO", "clave_anterior": frozenset({"CONSOLIDACION"}),
                               "clave_actual": frozenset({"DESARROLLO"}),
                               "version_anterior": "v1", "version_actual": "v2"}],
                  "conflictos_historicos_abiertos": []}
        clas = dh.clasificar_conflicto_historico("tratamiento", matriz)
        self.assertEqual(clas["veredicto"], dh.HISTORICAL_CHANGE)
        self.assertTrue(clas["cascada_de_geometria"])
        self.assertEqual(clas["condicion_que_decide"], "3_mismo_objeto")


class TestRecuentoDerivadoDeTrueConflict(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not MATRIZ_GOLDEN.exists():
            raise unittest.SkipTest("no está la matriz histórica del Golden")
        cls.matriz = json.loads(MATRIZ_GOLDEN.read_text(encoding="utf-8"))
        cls.recuento = dh.recuento_true_conflict(cls.matriz)
        cls.reporte = dh.reporte_consistencia(cls.matriz)

    def test_el_recuento_sale_solo_de_true_conflict(self):
        verdaderos = {a for a, d in self.recuento["desglose"].items()
                      if d["veredicto"] == dh.TRUE_CONFLICT}
        self.assertEqual(set(self.recuento["atributos"]), verdaderos)
        self.assertEqual(self.recuento["total"], len(verdaderos))

    def test_el_golden_baja_de_6_a_2(self):
        """La auditoría midió 6 → 2; la implementación reproduce el 2 con sus atributos."""
        self.assertEqual(self.recuento["total"], 2)
        self.assertEqual(self.recuento["atributos"], ["altura_maxima", "coordenada"])
        self.assertEqual(len(self.reporte["conflictos_abiertos"]), 2)

    def test_los_atributos_abiertos_son_solo_true_conflict(self):
        for c in self.reporte["conflictos_abiertos"]:
            self.assertEqual(c["clase_conflicto"], dh.TRUE_CONFLICT)

    def test_las_clasificaciones_quedan_persistidas(self):
        clases = self.reporte["clasificaciones_conflicto"]
        self.assertEqual(clases["tratamiento"]["veredicto"], dh.HISTORICAL_CHANGE)
        self.assertEqual(clases["uso_pot"]["veredicto"], dh.SEMANTIC_DIFFERENCE)
        self.assertEqual(clases["amenaza"]["veredicto"], dh.RESOLVED_BY_PRECEDENCE)
        self.assertEqual(clases["titulares"]["veredicto"], dh.NORMALIZATION_DIFFERENCE)
        for atributo, clas in clases.items():
            if clas["veredicto"] != dh.NOT_A_CONFLICT:
                self.assertTrue(clas["motivo"], f"{atributo}: clasificación sin motivo")

    def test_lo_reclasificado_sigue_en_revision_y_no_verificado(self):
        revisar = {r["atributo"]: r for r in self.reporte["requieren_revision"]}
        for atributo in ("tratamiento", "uso_pot", "amenaza", "titulares"):
            self.assertIn(atributo, revisar, atributo)
            self.assertEqual(revisar[atributo]["estado"], dh.REQUIERE_VALIDACION)
            self.assertNotEqual(revisar[atributo]["estado"], dh.VERIFICADO)
            self.assertIn(revisar[atributo].get("clase_conflicto"),
                          (dh.HISTORICAL_CHANGE, dh.SEMANTIC_DIFFERENCE,
                           dh.RESOLVED_BY_PRECEDENCE, dh.NORMALIZATION_DIFFERENCE))

    def test_el_informe_reclasificado_declara_su_origen_y_lo_almacenado(self):
        informe = dh.reclasificar_informe({"version": "dictus-historical-consistency/1.0.0",
                                           "conflictos_abiertos": [1, 2, 3, 4, 5, 6]},
                                          self.matriz)
        self.assertEqual(informe["origen"], "RECOMPUTADO_DESDE_ATTRIBUTE_HISTORY_MATRIX")
        self.assertEqual(informe["informe_almacenado"]["conflictos_abiertos"], 6)
        self.assertEqual(len(informe["conflictos_abiertos"]), 2)

    def test_la_banda_de_sensibilidad_es_declarada(self):
        banda = self.recuento["banda_sensibilidad"]
        self.assertEqual(banda["estricta_TRUE_CONFLICT"], 2)
        self.assertGreaterEqual(banda["incluyendo_cascadas_de_geometria"], 2)

    def test_sin_matriz_no_se_inventa_un_recuento(self):
        self.assertEqual(dh.recuento_true_conflict({})["total"], 0)
        self.assertEqual(dh.recuento_true_conflict(None)["total"], 0)


if __name__ == "__main__":
    unittest.main()

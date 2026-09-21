# -*- coding: utf-8 -*-
"""
Remediation 03H.2 — CADASTRAL + URBAN CONTEXT RECOVERY (Golden 040-646406).

Recupera la riqueza catastral/urbanística sin perder las garantías de identidad
y provenance: contexto urbano completo, altura/tratamiento reales, estado de la
capa de construcción y semántica correcta del estrato.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = ROOT / "api"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(API))

from market_context import (
    resolve_official_urban_context, coordinate_source_verified,
    STATUS_VERIFIED_OFFICIAL, STATUS_CONFLICT, STATUS_UNRESOLVED,
    STATUS_SOURCE_UNAVAILABLE, COORD_OFFICIAL_ADDRESS_GEOCODE, COORD_CITY_CENTROID,
)

_URBANO_GOLDEN = {
    "disponible": True,
    "barrio": "Miramar",
    "localidad": "Norte Centro Histórico",
    "estrato": "4",
    "tratamiento": "Consolidación",
    "tipo_tratamiento": "Nivel 2",
    "altura_maxima": "11",
    "pieza_urbana": "Pieza Norte",
    "codigo_manzana": "08001010300001",
    "context_status": "OK",
    "campos_ambiguos": [],
}


class TestUrbanContextContract(unittest.TestCase):
    """#1/#2/#3: el contrato NO descarta atributos devueltos por la fuente."""

    def test_propaga_todos_los_atributos(self):
        out = resolve_official_urban_context(
            ciudad="barranquilla", lat=10.9870, lon=-74.8115,
            coordinate_source=COORD_OFFICIAL_ADDRESS_GEOCODE,
            consultar_entorno=lambda lat, lon: dict(_URBANO_GOLDEN))
        self.assertEqual(out["barrio"], "Miramar")
        self.assertEqual(out["barrio_status"], STATUS_VERIFIED_OFFICIAL)
        self.assertEqual(out["localidad"], "Norte Centro Histórico")
        self.assertEqual(out["estrato"], "4")
        self.assertEqual(out["estrato_status"], STATUS_VERIFIED_OFFICIAL)
        self.assertEqual(out["tratamiento"], "Consolidación")
        self.assertEqual(out["tratamiento_status"], STATUS_VERIFIED_OFFICIAL)
        self.assertEqual(out["tipo_tratamiento"], "Nivel 2")
        self.assertEqual(out["altura_maxima"], "11")
        self.assertEqual(out["altura_status"], STATUS_VERIFIED_OFFICIAL)
        self.assertEqual(out["codigo_manzana"], "08001010300001")
        self.assertEqual(out["coordinate_source"], COORD_OFFICIAL_ADDRESS_GEOCODE)

    def test_ambiguedad_no_marca_verificado(self):
        r = dict(_URBANO_GOLDEN)
        r["context_status"] = "AMBIGUOUS_CONTEXT"
        r["campos_ambiguos"] = ["estrato"]
        out = resolve_official_urban_context(
            ciudad="barranquilla", lat=10.9870, lon=-74.8115,
            coordinate_source=COORD_OFFICIAL_ADDRESS_GEOCODE,
            consultar_entorno=lambda lat, lon: r)
        self.assertEqual(out["estrato"], None)
        self.assertEqual(out["estrato_status"], STATUS_CONFLICT)
        self.assertEqual(out["barrio_status"], STATUS_VERIFIED_OFFICIAL)
        self.assertEqual(out["context_status"], "AMBIGUOUS_CONTEXT")


class TestEdificabilidadGolden(unittest.TestCase):
    """#3/#13: tratamiento y altura REALES (no hardcodeados)."""

    def test_tratamiento_y_altura_desde_la_fuente(self):
        from edificabilidad import filas_edificabilidad
        d = dict(filas_edificabilidad("barranquilla", _URBANO_GOLDEN, 11,
                                      construction_status="AVAILABLE"))
        self.assertEqual(d["Tratamiento urbanístico"], "Consolidación (Nivel 2)")
        self.assertEqual(d["Altura normativa máxima"],
                         "Hasta 11 pisos (POT Barranquilla)")
        self.assertEqual(d["Pisos construidos (catastro)"], "11 piso(s)")

    def test_sin_dato_no_inventa_altura(self):
        from edificabilidad import filas_edificabilidad
        ent = {"tratamiento": "Consolidación", "tipo_tratamiento": "Nivel 2"}
        d = dict(filas_edificabilidad("barranquilla", ent, None,
                                      construction_status="SOURCE_UNAVAILABLE"))
        self.assertEqual(d["Altura normativa máxima"], "N/D")
        self.assertEqual(d["Tratamiento urbanístico"], "Consolidación (Nivel 2)")


class TestNoPosibleLote(unittest.TestCase):
    """#6: distinguir NO_MATCH de SOURCE_UNAVAILABLE."""

    def test_source_unavailable_no_dice_posible_lote(self):
        from edificabilidad import filas_edificabilidad
        d = dict(filas_edificabilidad("barranquilla", _URBANO_GOLDEN, None,
                                      construction_status="SOURCE_UNAVAILABLE"))
        txt = d["Pisos construidos (catastro)"]
        self.assertNotIn("posible lote", txt.lower())
        self.assertIn("no disponible", txt)
        self.assertIn("fuente de construcción", d["Confrontación (construido vs. norma)"])

    def test_no_match_si_dice_sin_edificacion(self):
        from edificabilidad import filas_edificabilidad
        d = dict(filas_edificabilidad("barranquilla", _URBANO_GOLDEN, None,
                                      construction_status="NO_MATCH"))
        self.assertIn("sin edificación registrada",
                      d["Pisos construidos (catastro)"])


class TestEstratoSemantico(unittest.TestCase):
    """#9: estrato faltante != uso no residencial."""

    def _estrato(self, **kw):
        from dictamen_data import get_catastral_dt
        return dict(get_catastral_dt("Miramar", 58.75, **kw))["Estrato"]

    def test_none_y_destino_none_pendiente(self):
        t = self._estrato(estrato=None, destino_economico=None)
        self.assertIn("PENDIENTE", t.upper())
        self.assertNotIn("No aplica", t)

    def test_habitacional_sin_estrato_pendiente_residencial(self):
        t = self._estrato(estrato=None, destino_economico="Habitacional")
        self.assertIn("residencial confirmado", t)
        self.assertNotIn("No aplica", t)

    def test_no_residencial_declarado_si_no_aplica(self):
        t = self._estrato(estrato=None, destino_economico="Industrial")
        self.assertIn("No aplica (uso no residencial declarado)", t)

    def test_estrato_presente_se_muestra(self):
        self.assertEqual(self._estrato(estrato="4",
                                       destino_economico="Habitacional"), "4")

    def test_barrio_label_oficial(self):
        from dictamen_data import get_catastral_dt
        filas = dict(get_catastral_dt("Miramar", 58.75))
        self.assertIn("Barrio / sector oficial", filas)


class TestNegativos(unittest.TestCase):
    """#14: nunca inventar contexto."""

    def test_urban_context_source_unavailable_no_inventa(self):
        out = resolve_official_urban_context(
            ciudad="barranquilla", lat=10.9870, lon=-74.8115,
            coordinate_source=COORD_OFFICIAL_ADDRESS_GEOCODE,
            consultar_entorno=lambda lat, lon: {"disponible": False})
        self.assertIsNone(out["barrio"])
        self.assertIsNone(out["estrato"])
        self.assertIsNone(out["altura_maxima"])
        self.assertEqual(out["context_status"], STATUS_SOURCE_UNAVAILABLE)
        self.assertNotEqual(out["barrio_status"], STATUS_VERIFIED_OFFICIAL)

    def test_coordenada_no_autorizada_no_consulta(self):
        out = resolve_official_urban_context(
            ciudad="barranquilla", lat=10.9870, lon=-74.8115,
            coordinate_source=COORD_CITY_CENTROID,
            consultar_entorno=lambda lat, lon: dict(_URBANO_GOLDEN))
        self.assertEqual(out["context_status"], "COORDINATE_SOURCE_NOT_AUTHORIZED")
        self.assertIsNone(out["altura_maxima"])

    def test_altura_ambigua_no_verificada(self):
        r = dict(_URBANO_GOLDEN)
        r["context_status"] = "AMBIGUOUS_CONTEXT"
        r["campos_ambiguos"] = ["tratamiento"]
        out = resolve_official_urban_context(
            ciudad="barranquilla", lat=10.9870, lon=-74.8115,
            coordinate_source=COORD_OFFICIAL_ADDRESS_GEOCODE,
            consultar_entorno=lambda lat, lon: r)
        self.assertIsNone(out["altura_maxima"])
        self.assertEqual(out["altura_status"], STATUS_CONFLICT)


if __name__ == "__main__":
    unittest.main()

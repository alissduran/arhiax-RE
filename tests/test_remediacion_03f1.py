# -*- coding: utf-8 -*-
"""
Remediation 03F.1 — POI truthful provenance + receipt semantics + appraisal cost.

Sin red: se prueban las funciones puras (receipt_rows, poi_source_label,
compute_poi_category_status, estimar_carga_hipotecaria, appraisal_cost).
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = ROOT / "api"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(API))


def _poi(name, dist, source, tipo="X"):
    return {"name": name, "distance": dist, "type": tipo, "source": source}


class TestReceiptPoiRows(unittest.TestCase):
    """#1: receipt_rows NO presenta NO_MATCH/SOURCE_UNAVAILABLE como CONSULTADO."""

    def _receipt(self, pois, poi_status):
        from receipts import build_execution_receipts
        return build_execution_receipts(
            ciudad="barranquilla", predio_real=None, volcan={}, pois=pois,
            poi_status=poi_status, titulux={}, geo_eval={},
            canonical_identity={"estado": "X", "resolution_confidence": "UNRESOLVED",
                                "nupre": None, "codigo_catastral": None},
            versionado={}, lat=10.9, lon=-74.8, ctl_adjuntado=True,
            catastro_live={"disponible": False})

    def test_mezcla_available_no_match_source_unavailable(self):
        from receipts import receipt_rows
        pois = {
            "Salud": [_poi("H1", 100, "OSM_OVERPASS"), _poi("H2", 200, "OSM_OVERPASS"),
                      _poi("H3", 300, "OSM_OVERPASS")],
            "Educacion": [_poi("C1", 150, "OSM_OVERPASS"), _poi("C2", 250, "OSM_OVERPASS")],
            "Comercio": [],
            "Recreacion": [],
        }
        poi_status = {"Salud": "AVAILABLE", "Educacion": "AVAILABLE",
                      "Comercio": "NO_MATCH", "Recreacion": "SOURCE_UNAVAILABLE"}
        filas = dict(receipt_rows(self._receipt(pois, poi_status)))
        fila = filas["Equipamiento urbano (POI)"]
        self.assertIn("Salud AVAILABLE (3)", fila)
        self.assertIn("Educacion AVAILABLE (2)", fila)
        self.assertIn("Comercio NO_MATCH", fila)
        self.assertIn("Recreacion SOURCE_UNAVAILABLE", fila)
        # NO afirmar que las cuatro categorías tienen equipamientos disponibles
        self.assertNotIn("Comercio AVAILABLE", fila)
        self.assertNotIn("Recreacion AVAILABLE", fila)

    def test_no_match_no_se_presenta_como_consultado_con_resultado(self):
        from receipts import receipt_rows
        pois = {"Salud": [_poi("H", 100, "OSM_OVERPASS")],
                "Educacion": [], "Comercio": [], "Recreacion": []}
        poi_status = {"Salud": "AVAILABLE", "Educacion": "NO_MATCH",
                      "Comercio": "NO_MATCH", "Recreacion": "NO_MATCH"}
        filas = dict(receipt_rows(self._receipt(pois, poi_status)))
        fila = filas["Equipamiento urbano (POI)"]
        self.assertIn("Educacion NO_MATCH", fila)
        self.assertIn("Comercio NO_MATCH", fila)
        self.assertNotIn("Educacion AVAILABLE", fila)


class TestPoiSourceLabel(unittest.TestCase):
    """#2: fuente de la sección 03 derivada de los POI renderizados."""

    def test_solo_overpass(self):
        from poi_engine import poi_source_label
        pois = {"Salud": [_poi("H", 100, "OSM_OVERPASS")],
                "Educacion": [], "Comercio": [], "Recreacion": []}
        self.assertEqual(poi_source_label(pois), "OpenStreetMap / Overpass API")

    def test_solo_photon(self):
        from poi_engine import poi_source_label
        pois = {"Salud": [], "Comercio": [_poi("M", 100, "PHOTON_OSM")],
                "Educacion": [], "Recreacion": []}
        self.assertEqual(poi_source_label(pois), "OpenStreetMap vía Photon")

    def test_mixto(self):
        from poi_engine import poi_source_label
        pois = {"Salud": [_poi("H", 100, "OSM_OVERPASS")],
                "Comercio": [_poi("M", 200, "PHOTON_OSM")],
                "Educacion": [], "Recreacion": []}
        self.assertEqual(poi_source_label(pois), "OpenStreetMap / Overpass + Photon")

    def test_vacio(self):
        from poi_engine import poi_source_label
        self.assertIsNone(poi_source_label({"Salud": [], "Educacion": [],
                                            "Comercio": [], "Recreacion": []}))


class TestCategoryStatus(unittest.TestCase):
    """#3: NO_MATCH != SOURCE_UNAVAILABLE."""

    def test_no_match_cuando_fuente_respondio(self):
        from poi_engine import compute_poi_category_status
        items = {"Salud": [], "Educacion": [], "Comercio": [], "Recreacion": []}
        st = compute_poi_category_status(items, overpass_ok=True)
        self.assertEqual(st["Comercio"], "NO_MATCH")
        self.assertEqual(st["Recreacion"], "NO_MATCH")

    def test_source_unavailable_cuando_nadie_respondio(self):
        from poi_engine import compute_poi_category_status
        items = {"Salud": [], "Educacion": [], "Comercio": [], "Recreacion": []}
        st = compute_poi_category_status(items, overpass_ok=False, photon_ok_cats=set())
        self.assertEqual(st["Comercio"], "SOURCE_UNAVAILABLE")
        self.assertEqual(st["Salud"], "SOURCE_UNAVAILABLE")

    def test_photon_responde_por_categoria(self):
        from poi_engine import compute_poi_category_status
        items = {"Salud": [], "Educacion": [], "Comercio": [], "Recreacion": []}
        st = compute_poi_category_status(items, overpass_ok=False,
                                         photon_ok_cats={"Comercio"})
        self.assertEqual(st["Comercio"], "NO_MATCH")
        self.assertEqual(st["Recreacion"], "SOURCE_UNAVAILABLE")

    def test_available_gana(self):
        from poi_engine import compute_poi_category_status
        items = {"Salud": [_poi("H", 100, "OSM_OVERPASS")],
                 "Educacion": [], "Comercio": [], "Recreacion": []}
        st = compute_poi_category_status(items, overpass_ok=True)
        self.assertEqual(st["Salud"], "AVAILABLE")


class TestUnknownEconomicPropagation(unittest.TestCase):
    """#8: valuation bloqueada -> NO ESTIMABLE; cuantía CTL -> LTV NO CALCULABLE."""

    def test_bloqueada_sin_cuantia(self):
        from carga_economica import estimar_carga_hipotecaria
        # valor_inmueble = val_data.consolidado (=0 cuando bloqueado)
        r = estimar_carga_hipotecaria(valor_inmueble=0, fecha_constitucion=None,
                                      capital_original=None)
        self.assertIs(r["available"], False)
        self.assertIsNone(r["capital_estimado"])
        self.assertIsNone(r["saldo_estimado"])
        self.assertIsNone(r["cuota_mensual_orientativa"])
        self.assertIsNone(r["ltv_estimado"])

    def test_bloqueada_con_cuantia_ctl(self):
        from carga_economica import estimar_carga_hipotecaria
        r = estimar_carga_hipotecaria(valor_inmueble=0, fecha_constitucion="25-11-2022",
                                      plazo_anos=20, capital_original=160000000)
        self.assertIs(r["available"], True)
        self.assertEqual(r["capital_estimado"], 160000000)
        self.assertGreaterEqual(r["saldo_estimado"], 0)
        # LTV NO CALCULABLE mientras falte valor inmobiliario
        self.assertIsNone(r["ltv_estimado"])


class TestAppraisalCostContract(unittest.TestCase):
    """#5/#6: regla histórica NO encontrada -> contrato vacío sin cifras."""

    def test_contrato_vacio(self):
        from appraisal_cost import (build_appraisal_cost_estimate,
                                    APPRAISAL_COST_HISTORICAL_RULE)
        self.assertEqual(APPRAISAL_COST_HISTORICAL_RULE, "NOT_FOUND")
        est = build_appraisal_cost_estimate()
        self.assertIs(est["available"], False)
        self.assertIsNone(est["central_cop"])
        self.assertIsNone(est["low_cop"])
        self.assertIsNone(est["high_cop"])
        self.assertIsNone(est["method"])
        self.assertIsNone(est["source"])


if __name__ == "__main__":
    unittest.main()

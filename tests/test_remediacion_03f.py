# -*- coding: utf-8 -*-
"""
Remediation 03F — recuperación de capacidades del Dictus:
  A) POI completeness per-category (Overpass + Photon merge)
  B) (histórico de costo de avalúo: NO encontrado -> no se restaura)
  C) UNKNOWN != ZERO en carga económica hipotecaria.

Sin red: las pruebas usan las funciones puras (merge_poi_sources,
poi_category_status, estimar_carga_hipotecaria).
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = ROOT / "api"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(API))


def _poi(name, dist, source="OSM_OVERPASS", tipo="X"):
    return {"name": name, "distance": dist, "type": tipo, "source": source}


class TestMergePoiSources(unittest.TestCase):
    """#6/#11: Overpass válido + Photon solo para categorías faltantes."""

    def test_completa_categorias_faltantes_por_categoria(self):
        from poi_engine import merge_poi_sources
        overpass = {
            "Salud": [_poi("Hospital A", 100), _poi("Clinica B", 200), _poi("Doctores C", 300)],
            "Educacion": [_poi("Colegio X", 150), _poi("Uni Y", 250)],
            "Comercio": [],
            "Recreacion": [],
        }
        photon = {
            "Comercio": [_poi("Supermercado M", 400, "PHOTON_OSM"), _poi("Mall N", 500, "PHOTON_OSM")],
            "Recreacion": [_poi("Parque P", 350, "PHOTON_OSM"), _poi("Play Q", 600, "PHOTON_OSM")],
        }
        merged = merge_poi_sources(overpass, photon)
        self.assertEqual(len(merged["Salud"]), 3)
        self.assertEqual(len(merged["Educacion"]), 2)
        self.assertEqual(len(merged["Comercio"]), 2)     # desde Photon
        self.assertEqual(len(merged["Recreacion"]), 2)   # desde Photon
        # Provenance conservada
        self.assertTrue(all(p["source"] == "OSM_OVERPASS" for p in merged["Salud"]))
        self.assertTrue(all(p["source"] == "PHOTON_OSM" for p in merged["Comercio"]))

    def test_deduplica_por_nombre_normalizado(self):
        from poi_engine import merge_poi_sources
        overpass = {"Salud": [_poi(" Hospital  A ", 100)],
                    "Educacion": [], "Comercio": [], "Recreacion": []}
        photon = {"Salud": [_poi("hospital a", 120, "PHOTON_OSM")],
                  "Educacion": [], "Comercio": [], "Recreacion": []}
        merged = merge_poi_sources(overpass, photon)
        # Overpass no vacío -> se preserva Overpass, sin duplicar con Photon
        self.assertEqual(len(merged["Salud"]), 1)
        self.assertEqual(merged["Salud"][0]["source"], "OSM_OVERPASS")

    def test_ordena_y_limita(self):
        from poi_engine import merge_poi_sources
        overpass = {"Salud": [_poi("A", 500), _poi("B", 100), _poi("C", 300), _poi("D", 200)],
                    "Educacion": [], "Comercio": [], "Recreacion": []}
        merged = merge_poi_sources(overpass, {})
        dists = [p["distance"] for p in merged["Salud"]]
        self.assertEqual(dists, sorted(dists))
        self.assertLessEqual(len(merged["Salud"]), 3)  # límite por categoría


class TestPoiNoInvent(unittest.TestCase):
    """#12: categoría sin datos en ambas fuentes => NO_MATCH, sin POIs fijos."""

    def test_categoria_vacia_no_inventa(self):
        from poi_engine import merge_poi_sources, poi_category_status
        overpass = {"Salud": [_poi("H", 100)],
                    "Educacion": [], "Comercio": [], "Recreacion": []}
        photon = {"Comercio": [], "Recreacion": []}
        merged = merge_poi_sources(overpass, photon)
        self.assertEqual(merged["Comercio"], [])  # nada inventado
        status = poi_category_status(merged)
        self.assertEqual(status["Salud"], "AVAILABLE")
        self.assertEqual(status["Comercio"], "NO_MATCH")
        self.assertEqual(status["Recreacion"], "NO_MATCH")


class TestPoiCategoryStatus(unittest.TestCase):
    def test_status_disponible_y_no_match(self):
        from poi_engine import poi_category_status
        pois = {"Salud": [_poi("H", 100)], "Educacion": [],
                "Comercio": [], "Recreacion": []}
        st = poi_category_status(pois)
        self.assertEqual(st, {"Salud": "AVAILABLE", "Educacion": "NO_MATCH",
                              "Comercio": "NO_MATCH", "Recreacion": "NO_MATCH"})


class TestReceiptPoiStructure(unittest.TestCase):
    """#13: receipt POI por categoría (status + count)."""

    def test_receipt_poi_por_categoria(self):
        from receipts import build_execution_receipts
        r = build_execution_receipts(
            ciudad="barranquilla", predio_real=None, volcan={},
            pois={"Salud": [_poi("H", 100), _poi("C", 200)],
                  "Educacion": [_poi("C", 150)],
                  "Comercio": [], "Recreacion": []},
            titulux={}, geo_eval={},
            canonical_identity={"estado": "X", "resolution_confidence": "UNRESOLVED",
                                "nupre": None, "codigo_catastral": None},
            versionado={}, lat=10.9, lon=-74.8, ctl_adjuntado=True,
            catastro_live={"disponible": False})
        poi = r["poi"]
        self.assertTrue(poi["disponible"])
        self.assertEqual(poi["categorias"]["Salud"], {"status": "AVAILABLE", "count": 2})
        self.assertEqual(poi["categorias"]["Educacion"], {"status": "AVAILABLE", "count": 1})
        self.assertEqual(poi["categorias"]["Comercio"], {"status": "NO_MATCH", "count": 0})


class TestUnknownVsZero(unittest.TestCase):
    """#25/#26: UNKNOWN != ZERO en carga económica hipotecaria."""

    def test_sin_base_no_estimable(self):
        from carga_economica import estimar_carga_hipotecaria, generar_tabla_carga
        r = estimar_carga_hipotecaria(None, None)
        self.assertIs(r["available"], False)
        self.assertIsNone(r["capital_estimado"])
        self.assertIsNone(r["saldo_estimado"])
        self.assertIsNone(r["ltv_estimado"])
        filas = dict(generar_tabla_carga(r, lambda v: f"${v:,.0f}"))
        self.assertIn("NO ESTIMABLE", filas["Capital estimado del crédito"])
        self.assertIn("NO CALCULABLE", filas["LTV estimado"])

    def test_valuation_bloqueada_no_es_cero(self):
        """valuation.metodologia_aplica=False + consolidado=0 => carga NO ESTIMABLE."""
        from carga_economica import estimar_carga_hipotecaria
        # El PDF pasa valor_inmueble=val_data.consolidado (=0 cuando bloqueado)
        r = estimar_carga_hipotecaria(valor_inmueble=0, fecha_constitucion=None)
        self.assertIs(r["available"], False)
        self.assertIsNone(r["capital_estimado"])
        self.assertIsNone(r["ltv_estimado"])

    def test_capital_known_sin_valor_ltv_no_calculable(self):
        """Cuantía del CTL presente pero sin valor del inmueble: capital estimable,
        LTV NO CALCULABLE (no 0%)."""
        from carga_economica import estimar_carga_hipotecaria
        r = estimar_carga_hipotecaria(
            valor_inmueble=None, fecha_constitucion="25-11-2022",
            plazo_anos=20, capital_original=160000000)
        self.assertIs(r["available"], True)
        self.assertEqual(r["capital_estimado"], 160000000)
        self.assertIsNone(r["ltv_estimado"])

    def test_valor_real_cero_no_es_el_camino(self):
        """Con valor inmueble positivo, el flujo normal sigue devolviendo LTV numérico."""
        from carga_economica import estimar_carga_hipotecaria
        r = estimar_carga_hipotecaria(200000000, "25-11-2022", plazo_anos=20)
        self.assertIs(r["available"], True)
        self.assertGreaterEqual(r["ltv_estimado"], 0)


if __name__ == "__main__":
    unittest.main()

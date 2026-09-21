# -*- coding: utf-8 -*-
"""
Remediation 03H.1 — MARKET CONTEXT INTEGRATION CLOSURE.

Cierra las rutas de valoración por fallback genérico y valida el pipeline
identidad → ubicación → contexto → autorización, de extremo a extremo (con
mocks, sin red).
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = ROOT / "api"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(API))

from market_context import (
    build_market_context, market_context_ready, market_context_authorized,
    resolve_market_sector, resolve_market_location,
    STATUS_VERIFIED_OFFICIAL, STATUS_VERIFIED_REGISTRAL, STATUS_UNRESOLVED,
    STATUS_SOURCE_UNAVAILABLE, MATCH_EXACT,
)


def _golden_identity():
    return {
        "identity_source": "OFFICIAL_ADOPTION_REGISTRY",
        "identity_verified": True,
        "resolution_confidence": "VERIFIED_UNIT_IDENTITY",
        "adopcion_registro": {"direccion": "Transversal 43 100 50 TO 8 AP 430"},
    }


class TestResolveMarketLocation(unittest.TestCase):
    """#1/#2/#3: ubicación de mercado (no identidad) con authoritative_address."""

    def test_oficial_adoption_address_es_authoritative(self):
        loc = resolve_market_location(
            canonical_identity=_golden_identity(), predio_real=None,
            lat_geo=10.9870, lon_geo=-74.8115,
            db_lat=None, db_lon=None, db_direccion="calle falsa 123",
            barrio="Miramar", es_bogota=False, es_medellin=False,
            es_pasto=False, ciudad="barranquilla")
        self.assertEqual(loc["authoritative_address"], "Transversal 43 100 50 TO 8 AP 430")
        self.assertEqual(loc["address_source"], "OFFICIAL_ADOPTION_REGISTRY")
        self.assertEqual(loc["lat"], 10.9870)
        self.assertEqual(loc["lon"], -74.8115)
        self.assertEqual(loc["coordinate_source"], "OFFICIAL_ADDRESS_GEOCODE")

    def test_sin_predio_ni_geo_cae_a_centroide_no_verificado(self):
        loc = resolve_market_location(
            canonical_identity={}, predio_real=None,
            lat_geo=None, lon_geo=None, db_lat=None, db_lon=None,
            db_direccion=None, barrio="Centro", es_bogota=False,
            es_medellin=False, es_pasto=False, ciudad="barranquilla")
        self.assertEqual(loc["coordinate_source"], "CITY_CENTROID")


class TestGoldenPipeline(unittest.TestCase):
    """#11: ArcGIS SOURCE_UNAVAILABLE + adopción EXACT + barrio/estrato oficiales."""

    def _pipeline(self, estrato, estrato_status):
        loc = resolve_market_location(
            canonical_identity=_golden_identity(), predio_real=None,
            lat_geo=10.9870, lon_geo=-74.8115, db_lat=None, db_lon=None,
            db_direccion=None, barrio="Miramar", es_bogota=False,
            es_medellin=False, es_pasto=False, ciudad="barranquilla")
        sector = resolve_market_sector("Miramar")
        mc = build_market_context(
            identity_verified=True,
            barrio="Miramar", barrio_status=STATUS_VERIFIED_OFFICIAL,
            estrato=estrato, estrato_status=estrato_status,
            tipologia="Apartamento — Propiedad Horizontal",
            tipologia_status=STATUS_VERIFIED_REGISTRAL,
            sector_resolution=sector, market_rate_source=sector.get("source"),
            coordinates={"lat": loc["lat"], "lon": loc["lon"]})
        return mc, loc

    def test_golden_full_ready(self):
        mc, loc = self._pipeline(4, STATUS_VERIFIED_OFFICIAL)
        self.assertTrue(market_context_ready(mc))
        self.assertTrue(market_context_authorized(mc))
        self.assertEqual(mc["sector_metodologico"]["value_m2"], 6800000)
        self.assertEqual(mc["sector_metodologico"]["match_type"], MATCH_EXACT)
        self.assertEqual(loc["authoritative_address"], "Transversal 43 100 50 TO 8 AP 430")

    def test_golden_negative_estrato_source_unavailable(self):
        """#12: estrato SOURCE_UNAVAILABLE -> context NO ready (no default 4)."""
        mc, _ = self._pipeline(None, STATUS_SOURCE_UNAVAILABLE)
        self.assertFalse(market_context_ready(mc))
        self.assertFalse(market_context_authorized(mc))
        # NO default estrato 4
        self.assertIsNone(mc["estrato"]["value"])


class TestMalformedRate(unittest.TestCase):
    """#13: sector con source pero sin valor_central_m2 -> bloqueado, nunca 5.2M."""

    def test_market_rate_value_missing_bloquea(self):
        sector = {"matched_sector": "Miramar", "match_type": MATCH_EXACT,
                  "value_m2": None, "source": "fuente presente",
                  "source_date": "Q3-2026"}
        mc = build_market_context(
            identity_verified=True,
            barrio="Miramar", barrio_status=STATUS_VERIFIED_OFFICIAL,
            estrato=4, estrato_status=STATUS_VERIFIED_OFFICIAL,
            tipologia="Apartamento PH", tipologia_status=STATUS_VERIFIED_REGISTRAL,
            sector_resolution=sector, market_rate_source="fuente presente")
        self.assertFalse(market_context_ready(mc))
        self.assertFalse(market_context_authorized(mc))
        self.assertTrue(any("market rate value" in b for b in mc["blockers"]))


class TestCallerSafety(unittest.TestCase):
    """#8/#14: get_valuation sin autorización explícita (False) -> bloqueado."""

    def test_get_valuation_sin_autorizacion_bloquea(self):
        from dictamen_data import get_valuation
        v = get_valuation(58.75, "Miramar", estrato=4, valuation_authorized=False)
        self.assertIs(v["metodologia_aplica"], False)
        self.assertEqual(v["consolidado"], 0)
        self.assertIn("no autorizada", v["motivo_no_aplica"])

    def test_get_valuation_autorizada_calcula(self):
        from dictamen_data import get_valuation
        v = get_valuation(58.75, "Miramar", estrato=4, valuation_authorized=True)
        self.assertIs(v["metodologia_aplica"], True)
        self.assertEqual(v["market_rate_match_type"], "EXACT")
        self.assertEqual(v["value_m2"], 6800000)


if __name__ == "__main__":
    unittest.main()

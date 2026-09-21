# -*- coding: utf-8 -*-
"""
Remediation 03H.1A — SINGLE-SOURCE MARKET CONTEXT CLOSURE.

Prueba el wiring real de extremo a extremo (con mocks, sin red):

  OFFICIAL IDENTITY → AUTHORITATIVE LOCATION → OFFICIAL URBAN CONTEXT
  → MARKET CONTEXT → SINGLE MARKET RATE → VALUATION
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
    resolve_market_sector, resolve_market_location, resolve_official_urban_context,
    coordinate_source_verified, STATUS_VERIFIED_OFFICIAL, STATUS_VERIFIED_REGISTRAL,
    STATUS_UNRESOLVED, STATUS_SOURCE_UNAVAILABLE,
    COORD_OFFICIAL_ADDRESS_GEOCODE, COORD_CITY_CENTROID,
)

_GOLDEN = {
    "identity_source": "OFFICIAL_ADOPTION_REGISTRY",
    "identity_verified": True,
    "resolution_confidence": "VERIFIED_UNIT_IDENTITY",
    "adopcion_registro": {"direccion": "Transversal 43 100 50 TO 8 AP 430"},
}


def _entorno_miramar(lat, lon):
    return {"disponible": True, "barrio": "Miramar", "estrato": "4",
            "tratamiento": None, "context_status": "OK", "campos_ambiguos": []}


def _entorno_no_disponible(lat, lon):
    return {"disponible": False, "error": "sin respuesta"}


def _geocoder_golden(direccion, ciudad=None):
    return (10.9870, -74.8115)


def _orquestar(entorno, coordinate_source, geocoder):
    loc = resolve_market_location(
        canonical_identity=_GOLDEN, predio_real=None, lat_geo=None, lon_geo=None,
        db_lat=None, db_lon=None, db_direccion=None, barrio="",
        es_bogota=False, es_medellin=False, es_pasto=False,
        ciudad="barranquilla", geocoder=geocoder)
    urbano = resolve_official_urban_context(
        ciudad="barranquilla", lat=loc["lat"], lon=loc["lon"],
        coordinate_source=coordinate_source, consultar_entorno=entorno)
    sector = resolve_market_sector(urbano.get("barrio"))
    mc = build_market_context(
        identity_verified=True,
        barrio=urbano.get("barrio"), barrio_status=urbano.get("barrio_status"),
        estrato=urbano.get("estrato"), estrato_status=urbano.get("estrato_status"),
        tipologia="Apartamento — Propiedad Horizontal",
        tipologia_status=STATUS_VERIFIED_REGISTRAL,
        sector_resolution=sector, market_rate_source=sector.get("source"),
        coordinates={"lat": loc["lat"], "lon": loc["lon"]})
    return loc, urbano, mc


class TestCoordinateAllowlist(unittest.TestCase):
    """#2: allowlist explícita; None/UNRESOLVED/centroide NO autorizados."""

    def test_allowlist(self):
        self.assertTrue(coordinate_source_verified(COORD_OFFICIAL_ADDRESS_GEOCODE))
        self.assertTrue(coordinate_source_verified("OFFICIAL_PREDIO"))
        self.assertTrue(coordinate_source_verified("CTL_ADDRESS_GEOCODE"))

    def test_none_y_unresolved_no_autorizados(self):
        self.assertFalse(coordinate_source_verified(None))
        self.assertFalse(coordinate_source_verified("UNRESOLVED"))

    def test_demo_centroide_no_autorizados(self):
        self.assertFalse(coordinate_source_verified("DB_COORDINATES"))
        self.assertFalse(coordinate_source_verified("BARRIO_DEMO"))
        self.assertFalse(coordinate_source_verified(COORD_CITY_CENTROID))


class TestOfficialUrbanContext(unittest.TestCase):
    def test_contexto_oficial_resuelto(self):
        urbano = resolve_official_urban_context(
            ciudad="barranquilla", lat=10.9870, lon=-74.8115,
            coordinate_source=COORD_OFFICIAL_ADDRESS_GEOCODE,
            consultar_entorno=_entorno_miramar)
        self.assertEqual(urbano["barrio"], "Miramar")
        self.assertEqual(urbano["barrio_status"], STATUS_VERIFIED_OFFICIAL)
        self.assertEqual(urbano["estrato"], "4")
        self.assertEqual(urbano["estrato_status"], STATUS_VERIFIED_OFFICIAL)
        self.assertEqual(urbano["context_status"], "OK")

    def test_source_unavailable(self):
        urbano = resolve_official_urban_context(
            ciudad="barranquilla", lat=10.9870, lon=-74.8115,
            coordinate_source=COORD_OFFICIAL_ADDRESS_GEOCODE,
            consultar_entorno=_entorno_no_disponible)
        self.assertEqual(urbano["barrio_status"], STATUS_UNRESOLVED)
        self.assertEqual(urbano["estrato_status"], STATUS_UNRESOLVED)
        self.assertEqual(urbano["context_status"], STATUS_SOURCE_UNAVAILABLE)

    def test_coordinate_source_no_autorizado_no_consulta(self):
        urbano = resolve_official_urban_context(
            ciudad="barranquilla", lat=10.9870, lon=-74.8115,
            coordinate_source=COORD_CITY_CENTROID,
            consultar_entorno=_entorno_miramar)
        # No consulta y NO marca nada como oficial.
        self.assertIsNone(urbano["barrio"])
        self.assertNotEqual(urbano["barrio_status"], STATUS_VERIFIED_OFFICIAL)
        self.assertEqual(urbano["context_status"], "COORDINATE_SOURCE_NOT_AUTHORIZED")


class TestE2EGolden(unittest.TestCase):
    """#13/#14/#15: orquestación end-to-end con mocks."""

    def test_golden_full_pipeline(self):
        loc, urbano, mc = _orquestar(_entorno_miramar,
                                     COORD_OFFICIAL_ADDRESS_GEOCODE,
                                     _geocoder_golden)
        self.assertEqual(loc["coordinate_source"], COORD_OFFICIAL_ADDRESS_GEOCODE)
        self.assertTrue(loc["coordinate_source_verified"])
        self.assertEqual(urbano["barrio"], "Miramar")
        self.assertEqual(urbano["estrato"], "4")
        self.assertTrue(market_context_ready(mc))
        self.assertTrue(market_context_authorized(mc))
        self.assertEqual(mc["sector_metodologico"]["value_m2"], 6800000)

        from dictamen_data import get_valuation
        v = get_valuation(58.75, None, None, valuation_authorized=True,
                          market_context=mc)
        self.assertIs(v["metodologia_aplica"], True)
        self.assertEqual(v["value_m2"], 6800000)
        self.assertGreater(v["consolidado"], 0)

    def test_negative_source_unavailable(self):
        loc, urbano, mc = _orquestar(_entorno_no_disponible,
                                     COORD_OFFICIAL_ADDRESS_GEOCODE,
                                     _geocoder_golden)
        self.assertFalse(market_context_ready(mc))
        self.assertFalse(market_context_authorized(mc))
        from dictamen_data import get_valuation
        v = get_valuation(58.75, None, None, valuation_authorized=False,
                          market_context=mc)
        self.assertEqual(v["consolidado"], 0)

    def test_wrong_coord_source_centroide_bloquea(self):
        # Identidad verificada + coordinate_source=CITY_CENTROID + contexto que
        # sí devuelve Miramar/4 -> MarketContext debe quedar BLOCKED.
        loc = resolve_market_location(
            canonical_identity=_GOLDEN, predio_real=None, lat_geo=None, lon_geo=None,
            db_lat=10.9870, db_lon=-74.8115, db_direccion=None, barrio="",
            es_bogota=False, es_medellin=False, es_pasto=False,
            ciudad="barranquilla", geocoder=lambda d, c=None: None)
        urbano = resolve_official_urban_context(
            ciudad="barranquilla", lat=loc["lat"], lon=loc["lon"],
            coordinate_source=loc["coordinate_source"],
            consultar_entorno=_entorno_miramar)
        self.assertEqual(urbano["context_status"], "COORDINATE_SOURCE_NOT_AUTHORIZED")
        self.assertIsNone(urbano["barrio"])
        sector = resolve_market_sector(urbano.get("barrio"))
        mc = build_market_context(
            identity_verified=True, barrio=urbano.get("barrio"),
            barrio_status=urbano.get("barrio_status"), estrato=urbano.get("estrato"),
            estrato_status=urbano.get("estrato_status"),
            tipologia="Apartamento PH", tipologia_status=STATUS_VERIFIED_REGISTRAL,
            sector_resolution=sector, market_rate_source=sector.get("source"))
        self.assertFalse(market_context_ready(mc))


if __name__ == "__main__":
    unittest.main()

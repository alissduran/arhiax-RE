# -*- coding: utf-8 -*-
"""
Remediation 03H — MARKET CONTEXT RECOVERY.

Identidad y contexto son dos problemas distintos. La valoración se habilita solo
cuando `identity_authorized AND market_context_authorized`. Sin fallback
silencioso (no default estrato 4, no fallback por estrato sin marcar).

Sin red: se prueban `resolve_market_sector`, `build_market_context`,
`market_context_authorized` y el bloqueo de `get_valuation`.
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
    resolve_market_sector, STATUS_VERIFIED_OFFICIAL, STATUS_VERIFIED_REGISTRAL,
    STATUS_UNRESOLVED, MATCH_EXACT, MATCH_NO_MATCH, MATCH_GENERIC_ESTRATO_FALLBACK,
)


class TestResolveMarketSector(unittest.TestCase):
    """#16/#17: leer el YAML Lonja y resolver el sector por barrio."""

    def test_miramar_exact_6800000(self):
        r = resolve_market_sector("Miramar")
        self.assertEqual(r["match_type"], MATCH_EXACT)
        self.assertEqual(r["matched_sector"], "Miramar")
        self.assertEqual(r["value_m2"], 6800000)
        self.assertIsNotNone(r["source"])
        self.assertIsNotNone(r["source_date"])
        self.assertIsNotNone(r["methodology_version"])

    def test_barrio_desconocido_no_match(self):
        r = resolve_market_sector("Barrio Inexistente")
        self.assertEqual(r["match_type"], MATCH_NO_MATCH)
        self.assertIsNone(r["value_m2"])
        self.assertIsNone(r["source"])

    def test_deterministico(self):
        a = resolve_market_sector("Miramar")
        b = resolve_market_sector("Miramar")
        self.assertEqual(a["value_m2"], b["value_m2"])
        self.assertEqual(a["matched_sector"], b["matched_sector"])


def _full_context(**overrides):
    sector = resolve_market_sector("Miramar")
    base = dict(
        identity_verified=True,
        barrio="Miramar", barrio_status=STATUS_VERIFIED_OFFICIAL,
        estrato=4, estrato_status=STATUS_VERIFIED_OFFICIAL,
        tipologia="Apartamento — Propiedad Horizontal",
        tipologia_status=STATUS_VERIFIED_REGISTRAL,
        sector_resolution=sector,
        market_rate_source=sector.get("source"),
    )
    base.update(overrides)
    return build_market_context(**base)


class TestMarketContextReady(unittest.TestCase):
    """#12/#13/#31/#32/#33: el gate verifica confianza, no solo strings."""

    def test_full_verified_ready(self):
        mc = _full_context()
        self.assertTrue(market_context_ready(mc))
        self.assertTrue(market_context_authorized(mc))

    def test_no_estrato_bloquea(self):
        """#31: barrio verificado + estrato None -> market_context_ready=False."""
        mc = _full_context(estrato=None, estrato_status=STATUS_UNRESOLVED)
        self.assertFalse(market_context_ready(mc))
        self.assertIn("estrato", market_context_blockers_text(mc))

    def test_no_sector_bloquea(self):
        """#32: sector sin match -> market_context_ready=False (no fallback estrato)."""
        mc = _full_context(sector_resolution=resolve_market_sector("Barrio Inexistente"),
                           market_rate_source=None)
        self.assertFalse(market_context_ready(mc))
        self.assertIn("sector", market_context_blockers_text(mc))

    def test_identity_no_verificada_bloquea(self):
        mc = _full_context(identity_verified=False)
        self.assertFalse(market_context_ready(mc))

    def test_tipologia_no_verificada_bloquea(self):
        mc = _full_context(tipologia=None, tipologia_status=STATUS_UNRESOLVED)
        self.assertFalse(market_context_ready(mc))


def market_context_blockers_text(mc):
    return "; ".join(mc.get("blockers") or [])


class TestValuationBlock(unittest.TestCase):
    """#30/#35: sin fallback silencioso; el fallback por estrato queda bloqueado."""

    def test_305_5M_regression_bloqueado(self):
        """58.75 × 5.2M = 305.5M era el fallback silencioso; ahora queda bloqueado."""
        from dictamen_data import get_valuation
        # Sin gate: el fallback por estrato produce 305.5M y se MARCA como fallback.
        v_fallback = get_valuation(58.75, "Barrio Inexistente", estrato=4)
        self.assertEqual(v_fallback["market_rate_match_type"], MATCH_GENERIC_ESTRATO_FALLBACK)
        self.assertAlmostEqual(v_fallback["consolidado"], 305500000, delta=20000)
        # Con el gate de contexto bloqueado: VALUATION_BLOCKED (consolidado 0).
        v_blocked = get_valuation(58.75, "Barrio Inexistente", estrato=4,
                                  market_context_blocked=True)
        self.assertIs(v_blocked["metodologia_aplica"], False)
        self.assertEqual(v_blocked["consolidado"], 0)
        self.assertIn("mercado", v_blocked["motivo_no_aplica"])

    def test_sector_exact_miramar_no_es_fallback(self):
        """Con sector Miramar resuelto, la tasa es EXACT (6.8M) y no es fallback."""
        from dictamen_data import get_valuation
        v = get_valuation(58.75, "Miramar", estrato=4)
        self.assertEqual(v["market_rate_match_type"], "EXACT")
        self.assertEqual(v["market_rate_sector"], "Miramar")
        self.assertEqual(v["value_m2"], 6800000)
        self.assertIsNotNone(v["market_rate_source"])

    def test_no_default_estrato_para_gate(self):
        """#8/#9/#31: estrato faltante no se sustituye por 4 para el gate."""
        mc = _full_context(estrato=None, estrato_status=STATUS_UNRESOLVED)
        self.assertFalse(market_context_ready(mc))
        # el valor de estrato no se "inventa" como 4
        self.assertIsNone(mc["estrato"]["value"])


class TestDeterminism(unittest.TestCase):
    """#36: mismos inputs verificados -> mismo market_context."""

    def test_deterministico(self):
        a = _full_context()
        b = _full_context()
        self.assertEqual(market_context_ready(a), market_context_ready(b))
        self.assertEqual(a["sector_metodologico"]["value_m2"],
                         b["sector_metodologico"]["value_m2"])


if __name__ == "__main__":
    unittest.main()

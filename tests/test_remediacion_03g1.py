# -*- coding: utf-8 -*-
"""
Remediation 03G.1 — AUTHORITATIVE STATIC IDENTITY RESOLVER (Barranquilla).

Segunda ruta autoritativa de resolución exacta basada en el Anexo 1 de adopción
catastral (Resolución GGCD 003 del 07/03/2025). Golden 040-646406.
Sin red: todo se prueba sobre el módulo estático local.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = ROOT / "api"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(API))

_GOLDEN = {
    "folio": "040-646406",
    "numero_predial": "080010103000010040001908040002",
    "codigo_homologado": "AFT0005BOHA",
    "direccion": "Transversal 43 100 50 TO 8 AP 430",
}
_VECINO = {
    "folio": "040-646407",
    "numero_predial": "080010103000010040001908040003",
    "codigo_homologado": "AFT0005BORE",
    "direccion": "Transversal 43 100 50 TO 8 AP 431",
}


class TestConsultarAdopcion(unittest.TestCase):

    def test_golden_exact_3(self):
        from barranquilla_adopcion import consultar_adopcion, STATUS_EXACT_3
        r = consultar_adopcion(folio=_GOLDEN["folio"],
                               numero_predial=_GOLDEN["numero_predial"],
                               codigo_homologado=_GOLDEN["codigo_homologado"])
        self.assertTrue(r["disponible"])
        self.assertEqual(r["match_status"], STATUS_EXACT_3)
        self.assertEqual(r["registro"]["direccion"], _GOLDEN["direccion"])

    def test_neighbor_unit_discrimination(self):
        """#10: AP 430 != AP 431 (no se confunden unidades vecinas)."""
        from barranquilla_adopcion import consultar_adopcion
        rg = consultar_adopcion(folio=_GOLDEN["folio"],
                                numero_predial=_GOLDEN["numero_predial"],
                                codigo_homologado=_GOLDEN["codigo_homologado"])
        rn = consultar_adopcion(folio=_VECINO["folio"],
                                numero_predial=_VECINO["numero_predial"],
                                codigo_homologado=_VECINO["codigo_homologado"])
        self.assertIn("AP 430", rg["registro"]["direccion"])
        self.assertIn("AP 431", rn["registro"]["direccion"])
        self.assertNotEqual(rg["registro"]["direccion"], rn["registro"]["direccion"])
        self.assertNotEqual(rg["registro"]["numero_predial"], rn["registro"]["numero_predial"])

    def test_conflict_identificador_contradice(self):
        """#6: si un identificador contradice a otro => CONFLICT (no elegir uno)."""
        from barranquilla_adopcion import consultar_adopcion, STATUS_CONFLICT
        # folio/numero_predial apuntan al golden; codigo_homologado apunta al vecino
        r = consultar_adopcion(folio=_GOLDEN["folio"],
                               numero_predial=_GOLDEN["numero_predial"],
                               codigo_homologado=_VECINO["codigo_homologado"])
        self.assertEqual(r["match_status"], STATUS_CONFLICT)
        self.assertIsNone(r["registro"])

    def test_no_match(self):
        from barranquilla_adopcion import consultar_adopcion, STATUS_NO_MATCH
        r = consultar_adopcion(folio="040-999999",
                               numero_predial="080010103000010040009999999999",
                               codigo_homologado="AFTZZZZZZZZ")
        self.assertEqual(r["match_status"], STATUS_NO_MATCH)

    def test_provenance_completa(self):
        from barranquilla_adopcion import consultar_adopcion
        r = consultar_adopcion(folio=_GOLDEN["folio"],
                               numero_predial=_GOLDEN["numero_predial"],
                               codigo_homologado=_GOLDEN["codigo_homologado"])
        p = r["provenance"]
        self.assertIn("Anexo 1", p["source_name"])
        self.assertEqual(p["resolution_number"], "GGCD 003")
        self.assertEqual(p["resolution_date"], "2025-03-07")
        self.assertEqual(len(p["sha256"]), 64)  # SHA-256 hex
        self.assertIsNotNone(p["version"])


class TestResolverIdentidadOficial(unittest.TestCase):
    """#5/#11: fragmento canónico -> VERIFIED + identity_verified + market_context_ready=False."""

    def test_golden_verified_identity(self):
        from barranquilla_adopcion import resolver_identidad_oficial
        r = resolver_identidad_oficial(folio=_GOLDEN["folio"],
                                       numero_predial=_GOLDEN["numero_predial"],
                                       codigo_homologado=_GOLDEN["codigo_homologado"])
        self.assertEqual(r["estado"], "MATCH_EXACT")
        self.assertEqual(r["resolution_method"], "official_adoption_registry")
        self.assertEqual(r["resolution_confidence"], "VERIFIED_UNIT_IDENTITY")
        self.assertIs(r["identity_verified"], True)
        # 03G.1: identidad verificada NO habilita valoración sola.
        self.assertIs(r["market_context_ready"], False)

    def test_conflict_no_verifica(self):
        from barranquilla_adopcion import resolver_identidad_oficial
        r = resolver_identidad_oficial(folio=_GOLDEN["folio"],
                                       numero_predial=_GOLDEN["numero_predial"],
                                       codigo_homologado=_VECINO["codigo_homologado"])
        self.assertEqual(r["estado"], "IDENTITY_CONFLICT")
        self.assertIs(r["identity_verified"], False)

    def test_no_match_no_verifica(self):
        from barranquilla_adopcion import resolver_identidad_oficial
        r = resolver_identidad_oficial(folio="040-999999",
                                       numero_predial="080010103000010040009999999999",
                                       codigo_homologado="AFTZZZZZZZZ")
        self.assertEqual(r["estado"], "NO_MATCH")
        self.assertIs(r["identity_verified"], False)


class TestMarketContextGate(unittest.TestCase):
    """#11: segundo gate MARKET_CONTEXT_READY — identidad verificada NO basta."""

    def test_verificado_pero_market_context_false_bloquea(self):
        from canonical import can_value_property
        auth = can_value_property({
            "propiedad_horizontal": True,
            "resolution_confidence": "VERIFIED_UNIT_IDENTITY",
            "market_context_ready": False,
        })
        self.assertIs(auth["allowed"], False)
        self.assertIn("mercado", auth["reason"])

    def test_market_context_ausente_no_bloquea(self):
        """Backward-compatible: sin el campo market_context_ready no se bloquea."""
        from canonical import can_value_property
        auth = can_value_property({
            "propiedad_horizontal": True,
            "resolution_confidence": "VERIFIED_UNIT_IDENTITY",
        })
        self.assertIs(auth["allowed"], True)


if __name__ == "__main__":
    unittest.main()

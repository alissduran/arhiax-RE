# -*- coding: utf-8 -*-
"""Tests del PRE_RENDER_CONSISTENCY_GATE (api/consistency.py)."""
import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
API_DIR = ROOT_DIR / "api"
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(API_DIR))


def _ctx_aceptacion():
    """Contexto coherente del caso de aceptación 240-211101 (no debe bloquear)."""
    return {
        "geo_eval": {"evaluado": True},
        "score_result": {"score_hidrologico": 88.0},
        "canonical_identity": {
            "estado": "MATCH_EXACT",
            "folio_snr": "240-211101",
            "codigo_catastral": "520010102000000440902900000116",
            "nupre": None,
            "matricula_municipal": "240-211101",
            "titular": {"nombre": "CABRERA VIVEROS JUAN SEBASTIAN",
                        "tipo_documento": "cc",
                        "tipo_persona": "NATURAL_PERSON"},
        },
        "administrative_context": {"comuna": "Comuna 1"},
        "predio_real": {"predio": {"numero_predial_nacional": "520010102000000440902900000116"}},
        "folio": "240-211101",
        "comuna_mostrada": "Comuna 1",
    }


class TestConsistencyGate(unittest.TestCase):

    def test_contexto_coherente_no_bloquea(self):
        from consistency import ejecutar_gate
        informe = ejecutar_gate(_ctx_aceptacion())
        self.assertTrue(informe["ok"])
        self.assertEqual(informe["bloqueantes"], [])

    def test_noeval_con_score_bloquea(self):
        """Bug G (regresión): NO EVALUADO con score hidrológico numérico -> bloquear."""
        from consistency import ejecutar_gate, InconsistenciaBloqueante
        ctx = _ctx_aceptacion()
        ctx["geo_eval"] = {"evaluado": False}
        ctx["score_result"] = {"score_hidrologico": 100.0}
        with self.assertRaises(InconsistenciaBloqueante):
            ejecutar_gate(ctx)

    def test_noeval_sin_score_no_bloquea(self):
        """NO EVALUADO con score hidrológico None (comportamiento correcto) pasa."""
        from consistency import ejecutar_gate
        ctx = _ctx_aceptacion()
        ctx["geo_eval"] = {"evaluado": False}
        ctx["score_result"] = {"score_hidrologico": None}
        informe = ejecutar_gate(ctx)
        self.assertTrue(informe["ok"])

    def test_identity_conflict_afirmando_predio_bloquea(self):
        from consistency import ejecutar_gate, InconsistenciaBloqueante
        ctx = _ctx_aceptacion()
        ctx["canonical_identity"]["estado"] = "IDENTITY_CONFLICT"
        with self.assertRaises(InconsistenciaBloqueante):
            ejecutar_gate(ctx)

    def test_codigo_catastral_divergente_bloquea(self):
        """El código catastral canónico y el número predial del predio resuelto
        se comparan contra su propio campo (03D.1): divergencia -> bloquear."""
        from consistency import ejecutar_gate, InconsistenciaBloqueante
        ctx = _ctx_aceptacion()
        ctx["predio_real"] = {"predio": {"numero_predial_nacional": "OTRO_CODIGO"}}
        with self.assertRaises(InconsistenciaBloqueante):
            ejecutar_gate(ctx)

    def test_nupre_divergente_bloquea(self):
        """El NUPRE canónico alfanumérico y el NUPRE del predio resuelto se
        comparan contra su propio campo (03D.1): divergencia -> bloquear."""
        from consistency import ejecutar_gate, InconsistenciaBloqueante
        ctx = _ctx_aceptacion()
        ctx["canonical_identity"]["nupre"] = "AFT0040BBHC"
        ctx["predio_real"] = {"predio": {"codigo_homologado": "AFTOTRA"}}
        with self.assertRaises(InconsistenciaBloqueante):
            ejecutar_gate(ctx)

    def test_matricula_divergente_advertencia_no_bloquea(self):
        from consistency import ejecutar_gate
        ctx = _ctx_aceptacion()
        ctx["canonical_identity"]["matricula_municipal"] = "240-216"
        informe = ejecutar_gate(ctx)
        self.assertTrue(informe["ok"])
        self.assertTrue(any(r["codigo"] == "I-MATRICULA" for r in informe["advertencias"]))

    def test_comuna_divergente_advertencia(self):
        from consistency import ejecutar_gate
        ctx = _ctx_aceptacion()
        ctx["comuna_mostrada"] = "Comuna 9"
        informe = ejecutar_gate(ctx)
        self.assertTrue(informe["ok"])
        self.assertTrue(any(r["codigo"] == "I-COMUNA" for r in informe["advertencias"]))

    def test_titular_natural_con_nit_advertencia(self):
        from consistency import ejecutar_gate
        ctx = _ctx_aceptacion()
        ctx["canonical_identity"]["titular"] = {
            "nombre": "X", "tipo_documento": "nit", "tipo_persona": "NATURAL_PERSON"}
        informe = ejecutar_gate(ctx)
        self.assertTrue(any(r["codigo"] == "I-TITULAR" and not r["cumple"]
                            for r in informe["resultados"]))


if __name__ == "__main__":
    unittest.main()

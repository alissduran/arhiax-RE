# -*- coding: utf-8 -*-
"""
Bug K: finding registry único coherente.
"""
import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
API_DIR = ROOT_DIR / "api"
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(API_DIR))


def _hallazgo_hipoteca():
    return ("ALTO", None, None, "H-01 | Hipoteca vigente (Anot. 007)", "SNR Registral",
            "hipoteca vigente", "bloqueo")


def _titulux_sin_cargas():
    return [{"id": "TIT_B04", "titulo": "Gravámenes y limitaciones", "estado": "OK",
             "severidad": "baja", "descripcion": "No se identificaron gravámenes vigentes"}]


def _titulux_falta_folio():
    return [{"id": "TIT_B01", "titulo": "Identidad del inmueble",
             "estado": "INFORMACION_INSUFICIENTE", "severidad": "alta",
             "descripcion": "falta folio de matrícula o código catastral."}]


class TestFindingRegistry(unittest.TestCase):

    def test_coherente_sin_hallazgos(self):
        from finding_registry import coherencia
        informe = coherencia([], [], {})
        self.assertTrue(informe["coherente"])
        self.assertEqual(informe["contradicciones"], [])

    def test_contradiccion_titulux_sin_cargas_vs_hipoteca_legal(self):
        from finding_registry import coherencia
        informe = coherencia([_hallazgo_hipoteca()], _titulux_sin_cargas(), {})
        self.assertFalse(informe["coherente"])
        self.assertTrue(any(c["codigo"] == "FR-TITB04-CARGAS" for c in informe["contradicciones"]))

    def test_contradiccion_titb01_falta_folio_vs_nupre_resuelto(self):
        from finding_registry import coherencia
        informe = coherencia([], _titulux_falta_folio(),
                             {"nupre": "520010102000000440902900000116"})
        self.assertFalse(informe["coherente"])
        self.assertTrue(any(c["codigo"] == "FR-TITB01-NUPRE" for c in informe["contradicciones"]))

    def test_sin_nupre_no_contradice_titb01(self):
        from finding_registry import coherencia
        informe = coherencia([], _titulux_falta_folio(), {})
        self.assertTrue(informe["coherente"])

    def test_detectar_duplicados(self):
        from finding_registry import detectar_duplicados, normalizar_hallazgos
        reg = normalizar_hallazgos([_hallazgo_hipoteca(), _hallazgo_hipoteca()])
        dups = detectar_duplicados(reg)
        self.assertEqual(dups, [])  # mismo id + mismo título = no es duplicado
        reg2 = normalizar_hallazgos([
            _hallazgo_hipoteca(),
            ("ALTO", None, None, "H-01 | Embargo vigente (Anot. 008)", "SNR", "x", "y"),
        ])
        self.assertTrue(detectar_duplicados(reg2))


class TestGateIntegraRegistry(unittest.TestCase):

    def test_gate_bloquea_contradiccion_titb04(self):
        from consistency import ejecutar_gate, InconsistenciaBloqueante
        ctx = {
            "geo_eval": {"evaluado": True},
            "score_result": {"score_hidrologico": 88.0},
            "canonical_identity": {"estado": "MATCH_EXACT", "folio_snr": "240-1",
                                   "nupre": "N", "matricula_municipal": "240-1",
                                   "titular": {}},
            "administrative_context": {"comuna": "Comuna 1"},
            "predio_real": {"predio": {"numero_predial_nacional": "N"}},
            "folio": "240-1", "comuna_mostrada": "Comuna 1",
            "hallazgos": [_hallazgo_hipoteca()],
            "titulux": {"pre_dictamen": _titulux_sin_cargas()},
        }
        with self.assertRaises(InconsistenciaBloqueante):
            ejecutar_gate(ctx)


if __name__ == "__main__":
    unittest.main()

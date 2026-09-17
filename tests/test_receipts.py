# -*- coding: utf-8 -*-
"""
Bug H: execution receipts reales para la Declaración de Alcance.
"""
import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
API_DIR = ROOT_DIR / "api"
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(API_DIR))


def _receipts():
    from receipts import build_execution_receipts
    return build_execution_receipts(
        ciudad="pasto",
        predio_real={"capas": {"riesgos_urbano": {"estado": "NO_MATCH"},
                               "predios_estratificacion": {"estado": "NOT_APPLICABLE"},
                               "tratamientos_urbanisticos": {"estado": "SOURCE_UNAVAILABLE"}},
                     "fuente": {"estado": "CONSULTADA EN VIVO (Geoportal Municipal de Pasto)"}},
        volcan={"disponible": True, "nivel": "Amenaza Alta"},
        pois={"Salud": ["x"], "Educacion": []},
        titulux={"screening_completo": True, "screening_agregado": "sinCoincidencia",
                 "fuentes_pendientes": []},
        geo_eval={"evaluado": True},
        canonical_identity={"estado": "MATCH_BY_NOMENCLATURA",
                            "nupre": "520010102000000440902900000116",
                            "folio_snr": "240-211101"},
        versionado={"ARHIAX_RE_VERSION": "1.4.0", "GIT_COMMIT_SHA": "abc123",
                    "DICTUS_ENGINE_VERSION": "1.4.0", "GIS_ADAPTER_VERSION": "1.2.0",
                    "TITULUX_VERSION": "1.1.0", "RULESET_VERSION": "1.3.0"},
        lat=1.21194, lon=-77.28663, ctl_adjuntado=True,
    )


class TestBuildExecutionReceipts(unittest.TestCase):

    def test_receipts_reflejan_estado_real(self):
        r = _receipts()
        self.assertEqual(r["identidad"]["nupre"], "520010102000000440902900000116")
        self.assertTrue(r["riesgo_volcanico"]["disponible"])
        self.assertTrue(r["sarlaft"]["completo"])
        self.assertTrue(r["poi"]["disponible"])
        self.assertEqual(r["gis"]["capas"]["riesgos_urbano"]["estado"], "NO_MATCH")

    def test_receipt_rows_incluye_traza(self):
        from receipts import receipt_rows
        filas = dict(receipt_rows(_receipts()))
        self.assertIn("Versión ARHIAX RE", filas)
        self.assertIn("Identidad predial", filas)
        self.assertIn("Riesgo volcánico (SGC)", filas)
        # La capa de riesgos urbano debe reportarse como SIN COINCIDENCIA, no "EJECUTADA".
        traza = " ".join(filas.values())
        self.assertIn("SIN COINCIDENCIA", traza)

    def test_estado_legible(self):
        from receipts import estado_legible
        self.assertIn("COINCIDENCIA", estado_legible("MATCH_EXACT"))
        self.assertIn("SIN COINCIDENCIA", estado_legible("NO_MATCH"))
        self.assertIn("NO DISPONIBLE", estado_legible("SOURCE_UNAVAILABLE"))


class TestAlcanceConReceipts(unittest.TestCase):

    def test_alcance_pasto_no_afirma_ejecutada_si_no_disponible(self):
        """Con receipts, la fila de riesgos NO dice 'EJECUTADA EN VIVO' si la capa
        no tuvo coincidencia / no respondió."""
        from dictamen_data import get_alcance_dt
        filas = get_alcance_dt("Centro", ciudad="pasto", receipts=_receipts())
        d = dict(filas)
        riesgos = d["Riesgos municipales por predio"]
        self.assertNotIn("EJECUTADA EN VIVO", riesgos)
        self.assertIn("sin coincidencia", riesgos.lower())

    def test_alcance_pasto_volcan_refleja_nivel_real(self):
        from dictamen_data import get_alcance_dt
        filas = get_alcance_dt("Centro", ciudad="pasto", receipts=_receipts())
        d = dict(filas)
        self.assertIn("Amenaza Alta", d["Riesgo volcanico (Volcan Galeras)"])

    def test_alcance_sin_receipts_mantiene_texto_estatico(self):
        from dictamen_data import get_alcance_dt
        filas = get_alcance_dt("Centro", ciudad="pasto")
        d = dict(filas)
        self.assertIn("EJECUTADA EN VIVO", d["Riesgos municipales por predio"])


if __name__ == "__main__":
    unittest.main()

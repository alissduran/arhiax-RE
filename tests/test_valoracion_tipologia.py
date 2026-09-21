# -*- coding: utf-8 -*-
"""
Bug L: precondiciones de valoración por tipología.

Un predio de suelo de protección / no construible / rural NO debe valorarse por
comparación de mercado (M1) como si fuera un apartamento terminado.
"""
import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
API_DIR = ROOT_DIR / "api"
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(API_DIR))


class TestPrecondicionesValoracion(unittest.TestCase):

    def test_procede_para_urbano_ph(self):
        from dictamen_data import precondiciones_valoracion
        pre = precondiciones_valoracion(clase_suelo="Urbano", destino="Residencial",
                                        tipologia="Apartamento -- Propiedad Horizontal")
        self.assertTrue(pre["procede"])
        self.assertIsNone(pre["motivo"])

    def test_no_procede_suelo_proteccion(self):
        from dictamen_data import precondiciones_valoracion
        pre = precondiciones_valoracion(clase_suelo="Suelo de proteccion")
        self.assertFalse(pre["procede"])
        self.assertIn("protección", pre["motivo"])

    def test_no_procede_no_construible(self):
        from dictamen_data import precondiciones_valoracion
        pre = precondiciones_valoracion(clase_suelo="Urbano", destino="No construible")
        self.assertFalse(pre["procede"])

    def test_no_procede_rural(self):
        from dictamen_data import precondiciones_valoracion
        pre = precondiciones_valoracion(clase_suelo="Rural")
        self.assertFalse(pre["procede"])


class TestGetValuationPrecondicion(unittest.TestCase):

    def test_no_procede_devuelve_consolidado_cero_y_flag(self):
        from dictamen_data import get_valuation
        # 03H.1A: modo de referencia legacy explícito (exploratorio)
        v = get_valuation(80, "Centro", estrato=3, ciudad="pasto",
                          clase_suelo="Suelo de proteccion",
                          allow_legacy_reference=True)
        self.assertIs(v["metodologia_aplica"], False)
        self.assertEqual(v["consolidado"], 0)
        self.assertTrue(v["motivo_no_aplica"])

    def test_procede_devuelve_valor_y_flag_true(self):
        from dictamen_data import get_valuation
        v = get_valuation(76, "Centro", estrato=3, ciudad="pasto",
                          clase_suelo="Urbano", allow_legacy_reference=True)
        self.assertIs(v["metodologia_aplica"], True)
        self.assertGreater(v["consolidado"], 0)
        self.assertIsNone(v["motivo_no_aplica"])

    def test_pemp_centro_no_es_suelo_proteccion(self):
        """El PEMP del centro histórico (área de actividad) NO es suelo de protección:
        la clase de suelo sigue siendo Urbano y la valoración SÍ procede."""
        from dictamen_data import get_valuation
        v = get_valuation(76, "Centro", estrato=3, ciudad="pasto",
                          clase_suelo="Urbano",
                          destino="Plan especial de manejo y proteccion (PEMP)",
                          allow_legacy_reference=True)
        self.assertIs(v["metodologia_aplica"], True)
        self.assertGreater(v["consolidado"], 0)


if __name__ == "__main__":
    unittest.main()

# -*- coding: utf-8 -*-
"""
Tests de regresión Sprint 3 (expansión Bogotá).

Cubren:
- Normalizador de direcciones de Bogotá (formatos usuario -> vía + placa oficial).
- Dispatcher del geocoder universal hacia el catastro de Bogotá (mock).
- Módulo catastro_predio_bogota: consulta de entorno por punto con mocks.
- Honestidad: Bogotá no publica NUPRE predial; la resolución es por punto
  referencial y no afirma NUPRE.

Los casos en vivo están marcados @pytest.mark.network.
"""
import sys
import unittest
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
API_DIR = ROOT_DIR / "api"
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(API_DIR))


class TestExpansionBogota(unittest.TestCase):

    def test_normalizador_direcciones_bogota(self):
        """El normalizador convierte formatos comunes a (vía, texto) oficiales."""
        from geocoder_catastral_bogota import normalizar_direccion_bogota
        casos = {
            "Carrera 9 # 61-08": ("KR 9", "61 08"),
            "KR 9 # 61-08": ("KR 9", "61 08"),
            "Calle 17 # 4-70": ("CL 17", "4 70"),
            "Carrera 7 # 72A-82": ("KR 7", "72A 82"),
            "Carrera 9 # 61-08, Chapinero": ("KR 9", "61 08"),
            "Carrera 9 # 61-08, Bogotá": ("KR 9", "61 08"),
            "Avenida Calle 19 # 3-32": None,  # 'Calle 19' no es clase de vía principal aquí
        }
        for entrada, esperado in casos.items():
            self.assertEqual(normalizar_direccion_bogota(entrada), esperado,
                             f"falló para '{entrada}'")
        # No matchea (sin placa completa)
        self.assertIsNone(normalizar_direccion_bogota("Calle 10"))
        self.assertIsNone(normalizar_direccion_bogota("Transversal 93"))

    def test_geocoder_universal_despacha_bogota(self):
        """El geocoder universal usa el catastro de Bogotá (mock)."""
        import geocoder as gc
        import geocoder_catastral_bogota as gbog
        original = gbog.geocodificar_catastro_bogota
        gc._GEOCODE_CACHE.clear()
        try:
            llamado = {}

            def stub(direccion):
                llamado["dir"] = direccion
                return {"lat": 4.646815, "lon": -74.061595, "direccion_oficial": "KR 9 # 61 08"}

            gbog.geocodificar_catastro_bogota = stub
            lat, lon = gc.geocodificar_direccion("Carrera 9 # 61-08", "Bogotá")
            self.assertAlmostEqual(lat, 4.6468, places=3)
            self.assertTrue(llamado.get("dir"), "no se invocó el catastro de Bogotá")
        finally:
            gbog.geocodificar_catastro_bogota = original
            gc._GEOCODE_CACHE.clear()

    def test_catastro_bogota_mock_entorno(self):
        """Con mocks, el entorno por punto devuelve sector/localidad/uso reales."""
        import catastro_predio_bogota as cb
        original_ent = cb.consultar_entorno_urbano
        original_const = cb.consultar_construccion
        original_amz = cb.consultar_amenazas
        cb._CACHE.clear()
        try:
            cb.consultar_entorno_urbano = lambda lat, lon, codigo_lote=None, codigo_manzana=None: {
                "disponible": True, "barrio": "LA SALLE", "sector_catastral": "008206",
                "localidad": "CHAPINERO", "upz": "PARDO RUBIO", "estrato": 3,
                "uso_economico": "COMERCIO Y OFICINAS", "clase_suelo": "Urbano",
                "valor_ref_m2": 3600000.0, "codigo_lote": "008213029001",
                "codigo_manzana": "008213029"}
            cb.consultar_construccion = lambda lat, lon, codigo_lote=None: {
                "disponible": True, "tipo_construccion": "Edificación",
                "total_pisos": 1, "codigo_construccion": "X"}
            cb.consultar_amenazas = lambda lat, lon: {
                "disponible": True,
                "movimiento_masa_urbano": {"intersecta": True, "nivel": "Amenaza Alta"},
                "respuesta_sismica": {"intersecta": False},
                "geotecnia_tipo_suelo": "Aluvial"}

            r = cb.enriquecer_por_punto(4.646815, -74.061595)
            self.assertTrue(r["disponible"])
            self.assertEqual(r["entorno"]["barrio"], "LA SALLE")
            self.assertEqual(r["entorno"]["localidad"], "CHAPINERO")
            self.assertEqual(r["entorno"]["uso_economico"], "COMERCIO Y OFICINAS")
            self.assertTrue(r["amenazas"]["movimiento_masa_urbano"]["intersecta"])
            # Sin capa predial: la resolución es por punto referencial y el predio
            # dict está vacío (no se afirma NUPRE).
            self.assertEqual(r.get("resolucion"), "por_punto_referencial")
            self.assertEqual(r.get("predio"), {})
        finally:
            cb.consultar_entorno_urbano = original_ent
            cb.consultar_construccion = original_const
            cb.consultar_amenazas = original_amz
            cb._CACHE.clear()

    @pytest.mark.network
    def test_bogota_vivo_por_punto(self):
        """En vivo (network): el punto de Carrera 9 # 61-08 (Chapinero) resuelve
        el sector catastral LA SALLE en la localidad CHAPINERO."""
        import catastro_predio_bogota as cb
        r = cb.enriquecer_por_punto(4.646815, -74.061595)
        if r.get("disponible"):
            self.assertEqual(r["entorno"]["localidad"], "CHAPINERO")
            self.assertTrue(r["entorno"].get("barrio"))
        else:
            self.skipTest("servicio catastro Bogotá no disponible: " + str(r.get("error")))


if __name__ == "__main__":
    unittest.main()

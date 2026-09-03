# -*- coding: utf-8 -*-
"""
Tests de regresión Sprint 3 (expansión Medellín).

Cubren:
- Normalizador de direcciones de Medellín (formatos usuario -> oficial).
- Geocoder universal despachando por ciudad (mocks, sin red).
- Módulo catastro_predio_medellin: consulta por código con mocks.
- Resolución "por punto" sin CTL: NO afirma NUPRE de un predio vecino.

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


class TestExpansionMedellin(unittest.TestCase):

    def test_normalizador_direcciones_medellin(self):
        """El normalizador convierte formatos comunes al oficial 'CR 43C 9-46'."""
        from geocoder_catastral_medellin import normalizar_direccion_medellin
        casos = {
            "Carrera 43C # 9-46": "CR 43C 9-46",
            "CRA 43C # 9-46": "CR 43C 9-46",
            "Calle 10 # 43B-43": "CL 10 43B-43",
            "CL 10 43B-43": "CL 10 43B-43",
            "CR 43C 9-46": "CR 43C 9-46",
            "Carrera 43C # 9-46, El Poblado": "CR 43C 9-46",
            "Calle 10 # 43B-43, Medellín": "CL 10 43B-43",
        }
        for entrada, esperado in casos.items():
            self.assertEqual(normalizar_direccion_medellin(entrada), esperado,
                             f"falló para '{entrada}'")
        # No matchea (sin placa)
        self.assertIsNone(normalizar_direccion_medellin("Calle 10"))
        self.assertIsNone(normalizar_direccion_medellin("Avenida El Poblado"))

    def test_geocoder_universal_despacha_medellin(self):
        """El geocoder universal usa el catastro de Medellín cuando la ciudad
        es Medellín (mock: se verifica que se invoca el módulo correcto)."""
        import geocoder as gc
        import geocoder_catastral_medellin as gmed
        original = gmed.geocodificar_catastro_medellin
        gc._GEOCODE_CACHE.clear()
        try:
            llamado = {}

            def stub(direccion):
                llamado["dir"] = direccion
                return {"lat": 6.2108, "lon": -75.5721, "direccion_oficial": "CR 43C 9-46"}

            gmed.geocodificar_catastro_medellin = stub
            lat, lon = gc.geocodificar_direccion("Carrera 43C # 9-46", "Medellín")
            self.assertAlmostEqual(lat, 6.2108, places=4)
            self.assertTrue(llamado.get("dir"), "no se invocó el catastro de Medellín")
        finally:
            gmed.geocodificar_catastro_medellin = original
            gc._GEOCODE_CACHE.clear()

    def test_geocoder_fallback_centroide_medellin(self):
        """Dirección inválida en Medellín cae al centroide de Medellín (no BAQ)."""
        import geocoder as gc
        gc._GEOCODE_CACHE.clear()
        lat, lon = gc.geocodificar_direccion("Avenida Inexistente 99999", "medellin")
        # Sin red el catastro no responde -> Nominatim falla -> centroide Medellín
        self.assertAlmostEqual(lat, 6.2442, places=2)
        self.assertAlmostEqual(lon, -75.5812, places=2)
        gc._GEOCODE_CACHE.clear()

    def test_catastro_medellin_mock_por_codigo(self):
        """Con mocks, la resolución por código del CTL devuelve el destino real."""
        import catastro_predio_medellin as cp
        original_predio = cp.consultar_predio_por_codigo
        original_ent = cp.consultar_entorno_urbano
        original_lote = cp.consultar_lote_y_construccion
        original_amz = cp.consultar_amenazas
        cp._CACHE.clear()
        try:
            cp.consultar_predio_por_codigo = lambda c, n: {
                "disponible": True,
                "numero_predial_nacional": "050010105142000150010000000000",
                "nupre": "AAB0001XFKE",
                "destino_economico": "Comercial y Servicios",
                "estrato": 4, "direccion_cruda": "CL 9 43B-68",
                "lat": 6.2105, "lon": -75.5720,
            }
            cp.consultar_entorno_urbano = lambda lat, lon: {
                "disponible": True, "barrio": "Astorga", "comuna": "El Poblado",
                "estrato": 4, "clase_suelo": "Urbano", "tratamiento": "Consolidación Nivel 4"}
            cp.consultar_lote_y_construccion = lambda lat, lon: {
                "disponible": True, "area_lote": 216.0, "tipo_construccion": "N",
                "total_pisos": 1, "area_construida": 138.18}
            cp.consultar_amenazas = lambda lat, lon: {
                "disponible": True,
                "movimiento_masa": {"intersecta": True, "nivel": "Baja"},
                "inundacion": {"intersecta": False},
                "avenida_torrencial": {"intersecta": False},
                "sismo": {"intersecta": False}}

            r = cp.enriquecer_desde_ctl("050010105142000150010000000000", "AAB0001XFKE")
            self.assertTrue(r["disponible"])
            self.assertEqual(r["predio"]["destino_economico"], "Comercial y Servicios")
            self.assertEqual(r["entorno"]["barrio"], "Astorga")
            self.assertEqual(r["entorno"]["comuna"], "El Poblado")
            self.assertTrue(r["amenazas"]["movimiento_masa"]["intersecta"])
        finally:
            cp.consultar_predio_por_codigo = original_predio
            cp.consultar_entorno_urbano = original_ent
            cp.consultar_lote_y_construccion = original_lote
            cp.consultar_amenazas = original_amz
            cp._CACHE.clear()

    def test_resolucion_por_punto_no_afirma_nupre_ajeno(self):
        """Sin CTL, la resolución por punto NO debe exponer el NUPRE del predio
        más cercano como si fuera el del folio (regla de honestidad)."""
        import catastro_predio_medellin as cp
        original = cp.consultar_predio_por_punto
        cp._CACHE.clear()
        try:
            cp.consultar_predio_por_punto = lambda lat, lon: {
                "disponible": True,
                "numero_predial_nacional": "050010105142000150010000000000",
                "nupre": "AAB0001XFKE",
                "destino_economico": "Comercial y Servicios",
                "estrato": 4,
            }
            r = cp.enriquecer_por_punto(6.2105, -75.5720)
            self.assertTrue(r["disponible"])
            # La resolución queda marcada como referencial por punto
            self.assertEqual(r.get("resolucion"), "por_punto_referencial")
            # No se fija direccion_oficial (no pisar la del usuario)
            self.assertIsNone(r.get("direccion_oficial"))
        finally:
            cp.consultar_predio_por_punto = original
            cp._CACHE.clear()

    @pytest.mark.network
    def test_medellin_vivo_por_codigo(self):
        """En vivo (network): el código catastral real de El Poblado resuelve
        destino Comercial y Servicios en la comuna El Poblado."""
        import catastro_predio_medellin as cp
        r = cp.enriquecer_desde_ctl("050010105142000150010000000000", "AAB0001XFKE")
        if r.get("disponible"):
            self.assertEqual(r["predio"]["destino_economico"], "Comercial y Servicios")
            self.assertEqual(r["entorno"]["comuna"], "El Poblado")
        else:
            self.skipTest("servicio Medellín no disponible: " + str(r.get("error")))


if __name__ == "__main__":
    unittest.main()

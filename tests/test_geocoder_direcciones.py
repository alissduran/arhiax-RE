# -*- coding: utf-8 -*-
"""
Tests del geocoder por dirección (Sprint 3 — mejora de tasa de acierto).

Cubren la limpieza de direcciones con formato SNR/CTL (prefijos de listado
'2) ', sufijos de mejora 'BDGA 3', indicadores 'No.') que antes rompían la
consulta a las capas catastrales, y la normalización por ciudad.

El benchmark contra los servicios oficiales está marcado network.
"""
import sys
import unittest
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
API_DIR = ROOT_DIR / "api"
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(API_DIR))

from address_normalizer import limpiar_direccion_consulta


class TestLimpiezaDireccionConsulta(unittest.TestCase):

    def test_quita_prefijo_listado_snr(self):
        self.assertEqual(limpiar_direccion_consulta("2) CL 40 # 50 B - 62 BDGA 3"),
                         "CL 40 # 50B - 62")

    def test_quita_sufijo_mejora(self):
        self.assertEqual(limpiar_direccion_consulta("CL 40 # 50B-62 BODEGA 3"),
                         "CL 40 # 50B - 62")
        self.assertEqual(limpiar_direccion_consulta("Calle 10 # 43B - 43 Local 1"),
                         "Calle 10 # 43B - 43")
        self.assertEqual(limpiar_direccion_consulta("KR 9 # 61-08 TORRE 2 APTO 501"),
                         "KR 9 # 61 - 08")

    def test_indicador_numero_a_almohadilla(self):
        self.assertEqual(limpiar_direccion_consulta("Calle 80 No. 5-90"),
                         "Calle 80 # 5 - 90")
        self.assertEqual(limpiar_direccion_consulta("Carrera 43C N° 9-46"),
                         "Carrera 43C # 9 - 46")

    def test_direccion_limpia_queda_igual(self):
        self.assertEqual(limpiar_direccion_consulta("Cra 43 # 98-32"),
                         "Cra 43 # 98 - 32")

    def test_letra_de_placa_pegada(self):
        """'50 B - 62' (formato SNR) -> '50B - 62' (letra pegada al número)."""
        self.assertEqual(limpiar_direccion_consulta("CL 40 # 50 B - 62"),
                         "CL 40 # 50B - 62")


class TestNormalizadoresPorCiudad(unittest.TestCase):

    def test_medellin_acepta_direccion_snr_con_sufijo(self):
        from geocoder_catastral_medellin import normalizar_direccion_medellin
        # Dirección SNR real con prefijo y mejora: antes no matcheaba
        self.assertEqual(normalizar_direccion_medellin("2) Carrera 43C # 9-46 BDGA"),
                         "CR 43C 9-46")
        self.assertEqual(normalizar_direccion_medellin("Calle 10 # 43B-43"),
                         "CL 10 43B-43")
        self.assertEqual(normalizar_direccion_medellin("Carrera 43C # 9-46, Medellín"),
                         "CR 43C 9-46")

    def test_bogota_acepta_direccion_snr(self):
        from geocoder_catastral_bogota import normalizar_direccion_bogota
        self.assertEqual(normalizar_direccion_bogota("Carrera 9 # 61-08, Chapinero"),
                         ("KR 9", "61 08"))
        self.assertEqual(normalizar_direccion_bogota("1. CL 17 No. 4-70 Local 3"),
                         ("CL 17", "4 70"))

    def test_barranquilla_parsea_limpia(self):
        from geocoder_catastral import parsear_direccion_colombiana
        p = parsear_direccion_colombiana("2) CRA 43 No. 98-32")
        self.assertEqual(p[0], "Carrera")
        self.assertEqual(p[1], "43")
        self.assertEqual(p[3], "98")
        self.assertEqual(p[4], "32")
        # Letra en la vía generadora (50B) no la soporta la capa 105: no se
        # afirma una coincidencia falsa (cae a Nominatim/street-level).
        self.assertIsNone(parsear_direccion_colombiana("CL 40 # 50B - 62"))


class TestBenchmarkGeocoderDirecciones(unittest.TestCase):
    """Benchmark en vivo (marcado network) con direcciones reales de las 3
    ciudades: mide la tasa de resolución catastral (no centroide)."""

    @pytest.mark.network
    def test_benchmark_direcciones_reales(self):
        from geocoder import geocodificar_direccion, _centroide
        casos = [
            ("barranquilla", "Tv 43 # 100-50"),
            ("barranquilla", "2) CL 40 # 50 B - 62 BDGA 3"),   # SNR folio 040-347004
            ("barranquilla", "Calle 63 # 37-71"),
            ("medellin", "Carrera 43C # 9-46"),
            ("medellin", "Calle 10 # 43B-43"),
            ("bogota", "Carrera 9 # 61-08"),
            ("bogota", "Calle 17 # 4-70"),
        ]
        ok = 0
        for ciudad, dir_ in casos:
            lat, lon = geocodificar_direccion(dir_, ciudad=ciudad)
            centroide = _centroide(ciudad)
            resuelta = (abs(lat - centroide[0]) > 1e-4 or abs(lon - centroide[1]) > 1e-4)
            if resuelta:
                ok += 1
            print(f"[BENCH] {ciudad:14s} {dir_!r:38} -> ({lat:.5f}, {lon:.5f}) {'OK' if resuelta else 'CENTROIDE'}")
        # Regresión: la dirección SNR del folio real 040-347004 ya no debe caer
        # al centroide de Barranquilla (se resuelve por vía o street-level).
        self.assertGreaterEqual(ok, 5, f"benchmark con solo {ok}/{len(casos)} resueltas")
        lat, lon = geocodificar_direccion("2) CL 40 # 50 B - 62 BDGA 3", ciudad="barranquilla")
        self.assertNotAlmostEqual(lat, _centroide("barranquilla")[0], places=3)


if __name__ == "__main__":
    unittest.main()

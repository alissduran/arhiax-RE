# -*- coding: utf-8 -*-
"""Tests del corrector ortográfico (tildes) aplicado al texto del dictamen."""
import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
API_DIR = ROOT_DIR / "api"
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(API_DIR))

from ortografia import corregir_es


class TestCorregirEs(unittest.TestCase):

    def test_tildes_basicas(self):
        self.assertEqual(corregir_es("Direccion oficial"), "Dirección oficial")
        self.assertEqual(corregir_es("Codigo catastral"), "Código catastral")
        self.assertEqual(corregir_es("Matricula Inmobiliaria"), "Matrícula Inmobiliaria")
        self.assertEqual(corregir_es("Este es un analisis de base"), "Este es un análisis de base")

    def test_regla_ion(self):
        self.assertEqual(corregir_es("construccion"), "construcción")
        self.assertEqual(corregir_es("verificacion registral"), "verificación registral")
        self.assertEqual(corregir_es("condicion"), "condición")
        self.assertEqual(corregir_es("guion"), "guion")  # excepción

    def test_preserva_mayusculas(self):
        self.assertEqual(corregir_es("ANALISIS REGISTRAL"), "ANÁLISIS REGISTRAL")
        self.assertEqual(corregir_es("Area"), "Área")
        self.assertEqual(corregir_es("Urbanistico"), "Urbanístico")

    def test_no_dana_html_ni_urls(self):
        t = "<link href='https://www.medellin.gov.co/servidormapas'>Medellín</link> y bogota"
        self.assertEqual(corregir_es(t),
                         "<link href='https://www.medellin.gov.co/servidormapas'>Medellín</link> y bogotá")
        self.assertEqual(corregir_es("https://www.medellin.gov.co"),
                         "https://www.medellin.gov.co")
        self.assertEqual(corregir_es("<b>Analisis</b>"), "<b>Análisis</b>")

    def test_metodo_frances_y_parametros(self):
        self.assertEqual(corregir_es("metodo frances de amortizacion"),
                         "método francés de amortización")
        self.assertEqual(corregir_es("parametros de mercado"), "parámetros de mercado")
        self.assertEqual(corregir_es("Metodo de Costo"), "Método de Costo")

    def test_publica_adjetivo_pero_no_verbo(self):
        # "pública" como adjetivo lleva tilde...
        self.assertEqual(corregir_es("escritura publica"), "escritura pública")
        # ...pero "publica" como verbo (3.ª pers. de publicar) NO lleva tilde.
        self.assertEqual(corregir_es("no publica capa predial"), "no publica capa predial")


if __name__ == "__main__":
    unittest.main()

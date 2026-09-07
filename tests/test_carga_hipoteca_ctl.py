# -*- coding: utf-8 -*-
"""
Regresión (dictamen real 50C-1463431, auditoría del usuario):
  1. La carga económica 08B amortiza desde la CONSTITUCIÓN del crédito
     (fecha de la anotación de hipoteca, 25-11-2022) — no desde la apertura
     del folio (1997) que producía '0 cuotas' — y usa la CUANTÍA declarada en
     el CTL (160.000.000 COP) en vez de un LTV 70% supuesto sobre el valor.
  2. legal_analyzer expone `hipoteca_vigente` con fecha y cuantía_cop.
  3. _parsear_cuantia_cop normaliza formatos colombianos.
"""
import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
API_DIR = ROOT_DIR / "api"
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(API_DIR))


class TestParsearCuantiaCop(unittest.TestCase):

    def test_formatos_colombianos(self):
        from legal_analyzer import _parsear_cuantia_cop
        self.assertEqual(_parsear_cuantia_cop("CUANTIA: 160.000.000"), 160000000)
        self.assertEqual(_parsear_cuantia_cop("por valor de $ 160.000.000,00"), 160000000)
        self.assertEqual(_parsear_cuantia_cop("VALOR ACTO 80,000,000"), 80000000)
        self.assertIsNone(_parsear_cuantia_cop("Sin cuantia declarada"))
        self.assertIsNone(_parsear_cuantia_cop(None))

    def test_coincide_con_cuantia_de_los_hallazgos(self):
        """La cuantía expuesta debe ser la misma que aparece en el hallazgo
        H-01 ('por 160.000.000 COP') del dictamen real."""
        from legal_analyzer import _parsear_cuantia_cop
        texto_hipoteca = (
            "GRAVAMEN: HIPOTECA ABIERTA SIN LIMITE DE CUANTIA? No.\n"
            "CUANTIA: 160.000.000\n"
            "DE: DIAZ DURAN ANGELA VIVIANA -> A: BBVA COLOMBIA"
        )
        self.assertEqual(_parsear_cuantia_cop(texto_hipoteca), 160000000)


class TestHipotecaVigenteEnAnalisis(unittest.TestCase):

    _CTL_BOG_REAL = """
La validez de este documento podra verificarse en la pagina certificados.supernotariado.gov.co
Certificado generado con el Pin No: 2609075062142575095Nro Matricula: 50C-1463431
CIRCULO REGISTRAL: 50C - BOGOTA ZONA CENTRO  DEPTO: BOGOTA D C  MUNICIPIO: BOGOTA, D.C.
FECHA APERTURA: 17-09-1997
ANOTACION: Nro 001 Fecha: 16-09-1997
ESPECIFICACION: OTRO
NRO TOTAL DE ANOTACIONES: *2*
ANOTACION: Nro 013 Fecha: 25-11-2022
ESPECIFICACION: COMPRAVENTA
DE: RIVERA CUBIDES MARLIO CC# 3547978
A: DIAZ DURAN ANGELA VIVIANA CC# 1016063585
ANOTACION: Nro 014 Fecha: 25-11-2022
ESPECIFICACION: GRAVAMEN: HIPOTECA
CUANTIA: 160.000.000
DE: DIAZ DURAN ANGELA VIVIANA
A: BANCO BILBAO VIZCAYA ARGENTARIA COLOMBIA S.A. BBVA COLOMBIA
NRO TOTAL DE ANOTACIONES: *1*
"""

    def test_hipoteca_vigente_con_fecha_y_cuantia(self):
        from legal_analyzer import analizar_texto_certificado
        res = analizar_texto_certificado(self._CTL_BOG_REAL)
        hv = res.get("hipoteca_vigente")
        self.assertIsNotNone(hv)
        self.assertEqual(hv["anotacion"], "014")
        self.assertEqual(hv["cuantia_cop"], 160000000)
        self.assertIn("BBVA", (hv.get("acreedor") or "").upper())
        self.assertIn("BANCO", (hv.get("acreedor") or "").upper())

    def test_sin_hipoteca_queda_none(self):
        from legal_analyzer import analizar_texto_certificado
        txt = self._CTL_BOG_REAL.replace(
            "ANOTACION: Nro 014 Fecha: 25-11-2022\nESPECIFICACION: GRAVAMEN: HIPOTECA\nCUANTIA: 160.000.000\nDE: DIAZ DURAN ANGELA VIVIANA\nA: BANCO BILBAO VIZCAYA ARGENTARIA COLOMBIA S.A. BBVA COLOMBIA\n",
            "")
        res = analizar_texto_certificado(txt)
        self.assertIsNone(res.get("hipoteca_vigente"))
        self.assertIsNone(res.get("acreedor_snr"))


class TestCargaEconomicaConCuantiaDelCtl(unittest.TestCase):

    def test_cuotas_pagadas_desde_la_constitucion_no_desde_apertura(self):
        """Regresión 50C-1463431: hipoteca constituida 25-11-2022 -> hoy hay
        cuotas pagadas (>0); usando la apertura del folio (1997) daba 0 cuotas
        porque el texto de apertura no es fecha parseable."""
        from carga_economica import estimar_carga_hipotecaria
        r = estimar_carga_hipotecaria(
            valor_inmueble=291460000,
            fecha_constitucion="25-11-2022",
            plazo_anos=20,
            capital_original=160000000,
        )
        self.assertGreater(r["cuotas_pagadas"], 0)
        self.assertLess(r["cuotas_pagadas"], 12 * 20)
        # Capital: la cuantía del CTL (160M), no LTV 70% del valor (204M)
        self.assertEqual(r["capital_estimado"], 160000000)
        self.assertLess(r["saldo_estimado"], 160000000)

    def test_fecha_no_parseable_no_rompe(self):
        """La apertura del folio trae texto adicional ('17-09-1997 RADICACIÓN...'):
        no debe lanzar y degrada a 0 cuotas (nunca rompe el PDF)."""
        from carga_economica import estimar_carga_hipotecaria
        r = estimar_carga_hipotecaria(
            valor_inmueble=291460000,
            fecha_constitucion="17-09-1997 RADICACION: 1997-82939 CON: ESCRITURA DE: 16-09-1997",
            plazo_anos=20,
            capital_original=160000000,
        )
        self.assertIn("saldo_estimado", r)
        self.assertGreaterEqual(r["ltv_estimado"], 0)


if __name__ == "__main__":
    unittest.main()

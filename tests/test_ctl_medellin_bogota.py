# -*- coding: utf-8 -*-
"""
Tests mejora 2 (Sprint 3): CTL reales de Medellín y Bogotá.

El analizador asumía folios '040-...' (Barranquilla). Colombia usa una matrícula
por oficina de registro: Medellín '001-...' y Bogotá con sub-oficinas
alfanuméricas '50C-...', '50N-...', '50S-...' (Zona Centro/Norte/Sur). Estos
tests verifican que el folio y el círculo registral se extraen correctamente y
que las fechas (dd-mm-aaaa) nunca se confunden con un folio.
"""
import sys
import unittest
from io import BytesIO
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
API_DIR = ROOT_DIR / "api"
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(API_DIR))

_TEXTO_CTL_MEDELLIN = """
CERTIFICADO DE TRADICION Y LIBERTAD
MATRICULA INMOBILIARIA: 001-1234567
CIRCULO REGISTRAL: 001 - MEDELLIN
FECHA APERTURA: 15-06-2005
ESTADO DEL FOLIO: ACTIVO
DESCRIPCION: CASA LOTE CON AREA DE 120 MTS2
DIRECCION DEL INMUEBLE
Tipo Predio: URBANO
2) CR 43C # 9 - 46
ANOTACION: Nro 001 Fecha: 10-05-2005
ESPECIFICACION: MODO DE ADQUISICION: 160 DIVISION MATERIAL
DE: URBANIZADORA MEDELLIN S.A.
A: FAMILIA PEREZ GOMEZ
NRO TOTAL DE ANOTACIONES: *1*
"""

_TEXTO_CTL_BOGOTA = """
CERTIFICADO DE TRADICION Y LIBERTAD
OFICINA DE REGISTRO DE INSTRUMENTOS PUBLICOS DE BOGOTA ZONA CENTRO
MATRICULA INMOBILIARIA: 50C-1092514
CIRCULO REGISTRAL: 050 - BOGOTA D.C.
FECHA APERTURA: 20-01-1998
ESTADO DEL FOLIO: ACTIVO
DIRECCION DEL INMUEBLE
Tipo Predio: URBANO
1) KR 9 # 61 - 08
ANOTACION: Nro 001 Fecha: 05-02-1998
ESPECIFICACION: MODO DE ADQUISICION: 160 DIVISION MATERIAL
DE: CONSTRUCTORA CENTRO S.A.
A: FAMILIA GARCIA LOPEZ
NRO TOTAL DE ANOTACIONES: *1*
"""


class TestCtlMedellin(unittest.TestCase):

    def test_folio_001_extraido(self):
        from legal_analyzer import analizar_texto_certificado
        res = analizar_texto_certificado(_TEXTO_CTL_MEDELLIN)
        self.assertEqual(res["folio"], "001-1234567")
        self.assertEqual(res["circulo_registral"], "001 - MEDELLIN")
        self.assertIn("PEREZ", res["titulares"].upper())
        self.assertEqual(len(res["anotaciones"]), 1)

    def test_sanitizar_folio_001(self):
        from index import _sanitizar_folio
        self.assertEqual(_sanitizar_folio("001-1234567"), "001-1234567")


class TestCtlBogota(unittest.TestCase):
    """Regresión clave: el folio de Bogotá '50C-...' antes no se capturaba
    (el regex exigía 3 dígitos antes del guion) y quedaba '040-XXXXXX'."""

    def test_folio_50c_extraido(self):
        from legal_analyzer import analizar_texto_certificado
        res = analizar_texto_certificado(_TEXTO_CTL_BOGOTA)
        self.assertEqual(res["folio"], "50C-1092514")
        self.assertNotEqual(res["folio"], "040-XXXXXX")
        self.assertEqual(res["circulo_registral"], "050 - BOGOTA D.C.")

    def test_folio_50n_y_50s(self):
        from legal_analyzer import analizar_texto_certificado
        for folio, circ in [("50N-9876543", "050 - BOGOTA D.C. ZONA NORTE"),
                            ("50S-1122334", "050 - BOGOTA D.C. ZONA SUR")]:
            txt = (_TEXTO_CTL_BOGOTA.replace("50C-1092514", folio)
                   .replace("050 - BOGOTA D.C.", circ))
            res = analizar_texto_certificado(txt)
            self.assertEqual(res["folio"], folio)

    def test_sanitizar_folio_bogota(self):
        from index import _sanitizar_folio
        self.assertEqual(_sanitizar_folio("50C-1092514"), "50C-1092514")
        # No alfanumérico válido tras el guion -> Pendiente (seguridad de archivos)
        self.assertEqual(_sanitizar_folio("50C-abc"), "Pendiente")
        self.assertEqual(_sanitizar_folio("../../etc"), "Pendiente")

    def test_extraer_datos_de_pdf_folio_bogota(self):
        """extraer_datos_de_pdf (flujo del endpoint) reconoce el folio de Bogotá."""
        from reportlab.pdfgen import canvas
        buf = BytesIO()
        c = canvas.Canvas(buf)
        y = 790
        for linea in _TEXTO_CTL_BOGOTA.splitlines():
            c.drawString(50, y, linea[:95])
            y -= 14
        c.save()
        tmp = ROOT_DIR / "tmp_ctl_bog.pdf"
        tmp.write_bytes(buf.getvalue())
        try:
            from index import extraer_datos_de_pdf
            datos = extraer_datos_de_pdf(str(tmp), ciudad="bogota")
            self.assertEqual(datos.get("folio"), "50C-1092514")
        finally:
            tmp.unlink(missing_ok=True)


class TestFechasNoSeConfundenConFolio(unittest.TestCase):

    def test_fecha_no_es_folio(self):
        """Una fecha dd-mm-aaaa no debe extraerse como matrícula."""
        from legal_analyzer import analizar_texto_certificado
        texto = "FECHA APERTURA: 21-03-2001\nANOTACION Nro 001 Fecha: 21-03-2001\nNRO TOTAL: *1*"
        res = analizar_texto_certificado(texto)
        self.assertNotIn("21-03", res["folio"])
        self.assertEqual(res["folio"], "040-XXXXXX")  # sin etiqueta MATRICULA

    def test_fecha_en_texto_con_folio_bogota(self):
        from legal_analyzer import analizar_texto_certificado
        res = analizar_texto_certificado(_TEXTO_CTL_BOGOTA)
        self.assertEqual(res["folio"], "50C-1092514")  # no '20-01' de apertura


class TestDiscrepanciaCirculoRegistral(unittest.TestCase):

    def test_discrepancia_ctl_de_otra_ciudad(self):
        """Un CTL de Medellín (001) en un caso de Bogotá (50) se detecta."""
        from pdf_compiler import _detectar_discrepancia_circulo
        prefijo, discrepante = _detectar_discrepancia_circulo(
            "001-1234567", "001 - MEDELLIN", "50")
        self.assertEqual(prefijo, "1")  # normalizado sin ceros a la izquierda
        self.assertTrue(discrepante)

    def test_sin_discrepancia_por_ciudad(self):
        from pdf_compiler import _detectar_discrepancia_circulo
        casos_ok = [
            ("040-347004", "040 - BARRANQUILLA", "040"),
            ("001-1234567", "001 - MEDELLIN", "001"),
            ("50C-1092514", "050 - BOGOTA D.C.", "50"),   # 50C empieza con 50
            ("50N-9876543", "050 - BOGOTA D.C. ZONA NORTE", "50"),
        ]
        for folio, circ, ciudad in casos_ok:
            prefijo, discrepante = _detectar_discrepancia_circulo(folio, circ, ciudad)
            self.assertFalse(discrepante, f"{folio} vs {ciudad}")

    def test_folio_digitado_de_otra_ciudad_se_detecta(self):
        """Sin CTL pero con folio digitado del círculo equivocado."""
        from pdf_compiler import _detectar_discrepancia_circulo
        _, discrepante = _detectar_discrepancia_circulo("040-646406", None, "001")
        self.assertTrue(discrepante)


if __name__ == "__main__":
    unittest.main()

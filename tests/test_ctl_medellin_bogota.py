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

# Fragmento REAL del CTL de Bogotá comprado por el usuario (folio 50C-1463431):
# encabezado moderno 'Nro Matrícula:', código catastral de 18 dígitos pegado a
# la siguiente etiqueta, NUPRE con prefijo 'AAA' y un folio HISTÓRICO citado en
# la COMPLEMENTACION ('REGISTRADA AL FOLIO 050-0554696') que NO debe ganarle.
_TEXTO_CTL_BOGOTA_REAL = """
La validez de este documento podra verificarse en la pagina certificados.supernotariado.gov.co
Certificado generado con el Pin No: 2609075062142575095Nro Matricula: 50C-1463431
Pagina 1 TURNO: 2026-50C-1-644770
Impreso el 7 de Septiembre de 2026 a las 08:59:37 AM
"ESTE CERTIFICADO REFLEJA LA SITUACION JURIDICA DEL INMUEBLE
HASTA LA FECHA Y HORA DE SU EXPEDICION"
No tiene validez sin la firma del registrador en la ultima pagina
CIRCULO REGISTRAL: 50C - BOGOTA ZONA CENTRO  DEPTO: BOGOTA D C  MUNICIPIO: BOGOTA, D.C.  VEREDA:  BOGOTA D. C.
FECHA APERTURA: 17-09-1997  RADICACION: 1997-82939  CON: ESCRITURA  DE: 16-09-1997
CODIGO CATASTRAL: 007202182500104001COD CATASTRAL ANT: SIN INFORMACION
NUPRE: AAA0083SHNN
ESTADO DEL FOLIO: ACTIVO
DESCRIPCION: CABIDA Y LINDEROS
Contenidos en ESCRITURA Nro 3822 de fecha 15-09-97 en NOTARIA 5 DE SANTAFE DE BOGOTA APARTAMENTO 401 con area de 56.05 M2 con coeficiente de 5.40%
COMPLEMENTACION:
L.E.P.INGENIEROS LTDA ADQUIRIO ASI: PARTE POR COMPRA A RINCON ROJAS MARIA CRISTINA POR ESCRITURA 2105
DE 2-08-94 NOTARIA 33 DE SANTAFE DE BOGOTA, REGISTRADA AL FOLIO 050-0554696 ESTA ADQUIRIO POR COMPRA
ANOTACION: Nro 001 Fecha: 16-09-1997
ESPECIFICACION: OTRO
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


class TestCtlBogotaRealComprado(unittest.TestCase):
    """Regresión con el fragmento REAL del CTL de Bogotá comprado (50C-1463431):
    encabezado moderno, código de 18 dígitos pegado, NUPRE 'AAA', y un folio
    histórico citado en la COMPLEMENTACION que no debe ganarle a la etiqueta."""

    def test_folio_principal_no_el_citado(self):
        from legal_analyzer import analizar_texto_certificado
        res = analizar_texto_certificado(_TEXTO_CTL_BOGOTA_REAL)
        self.assertEqual(res["folio"], "50C-1463431")
        self.assertNotEqual(res["folio"], "050-0554696")

    def test_nupre_aaa_extraido(self):
        from legal_analyzer import analizar_texto_certificado
        res = analizar_texto_certificado(_TEXTO_CTL_BOGOTA_REAL)
        self.assertEqual(res["nupre"], "AAA0083SHNN")

    def test_codigo_catastral_18_digitos(self):
        from legal_analyzer import analizar_texto_certificado
        res = analizar_texto_certificado(_TEXTO_CTL_BOGOTA_REAL)
        self.assertEqual(res["codigo_catastral"], "007202182500104001")

    def test_circulo_recortado_sin_departamento(self):
        from legal_analyzer import analizar_texto_certificado
        res = analizar_texto_certificado(_TEXTO_CTL_BOGOTA_REAL)
        self.assertEqual(res["circulo_registral"], "50C - BOGOTA ZONA CENTRO")
        self.assertNotIn("DEPTO", res["circulo_registral"])


class TestCondicionJuridicaDesdeCtl(unittest.TestCase):
    """La condición jurídica (PH / No PH) se infiere del CTL cuando el catastro
    no la publica (Medellín/Bogotá). El CTL real de Bogotá dice 'APARTAMENTO
    401 con coeficiente' + anotación de PROPIEDAD HORIZONTAL -> PH."""

    def test_bogota_apartamento_con_coeficiente_es_ph(self):
        from legal_analyzer import (analizar_texto_certificado,
                                    inferir_condicion_juridica)
        res = analizar_texto_certificado(_TEXTO_CTL_BOGOTA_REAL)
        cond = inferir_condicion_juridica(res.get("texto_ctl"),
                                          res.get("descripcion_ctl"))
        self.assertEqual(cond, "Propiedad Horizontal")

    def test_bodega_sin_ph_es_no_ph(self):
        from legal_analyzer import inferir_condicion_juridica
        texto = ("MATRICULA INMOBILIARIA: 040-347004\n"
                 "DESCRIPCION: CABIDA Y LINDEROS BODEGA NUMERO 3, AREA 570.9 M2")
        self.assertEqual(inferir_condicion_juridica(texto), "No Propiedad Horizontal")

    def test_no_ph_explicito(self):
        from legal_analyzer import inferir_condicion_juridica
        texto = "MATRICULA: 001-123\nNO PROPIEDAD HORIZONTAL. CASA LOTE"
        self.assertEqual(inferir_condicion_juridica(texto), "No Propiedad Horizontal")

    def test_sin_marcador_devuelve_none(self):
        from legal_analyzer import inferir_condicion_juridica
        texto = "MATRICULA: 001-123\nANOTACION Nro 001 COMPRAVENTA"
        self.assertIsNone(inferir_condicion_juridica(texto))
        self.assertIsNone(inferir_condicion_juridica(None))


    def test_direccion_catastral_prioritaria(self):
        """Regresión (dictamen real): el CTL de Bogotá trae varias placas en el
        bloque del inmueble ('AVENIDA (CALLE)63 20-04/CARRERA 20 61-55' y la
        oficial 'DG 61B 20 04 AP 401 (DIRECCION CATASTRAL)'). Se debe extraer la
        DIRECCION CATASTRAL (no la placa registral alternativa, que se
        geocodificaba en un punto equivocado). Remediation 03D: la dirección
        COMPLETA se preserva (incluye la unidad AP 401); la base sin unidad se
        DERIVA en direccion_base para integraciones externas, sin destruirla."""
        from legal_analyzer import analizar_texto_certificado
        from geocoder import extraer_direccion_de_ctl
        bloque = ("DIRECCION DEL INMUEBLE\nTipo Predio: URBANO\n"
                  "1) AVENIDA (CALLE)63 20-04/CARRERA 20 61-55 EDIFICIO SAN FELIPE "
                  "P.H. APARTAMENTO 401\n"
                  "2) DG 61B 20 04 AP 401 (DIRECCION CATASTRAL)\n"
                  "DETERMINACION DEL INMUEBLE:")
        res = analizar_texto_certificado(bloque)
        # La dirección completa (con unidad) se preserva: no se descarta el AP 401.
        self.assertEqual(res["direccion"], "DG 61B 20 04 AP 401")
        self.assertEqual(res["direccion_base"], "DG 61B 20 04")
        self.assertEqual(res["apartamento"], "401")
        # El geocodificador sigue usando la base sin unidad para el punto.
        self.assertEqual(extraer_direccion_de_ctl(bloque), "DG 61B 20 04")
        # El normalizador de Bogotá acepta el formato catastral sin guion
        from geocoder_catastral_bogota import normalizar_direccion_bogota
        self.assertEqual(normalizar_direccion_bogota("DG 61B 20 04"),
                         ("DG 61B", "20 04"))

    def test_hipoteca_anotacion_014_con_acreedor(self):
        """La hipoteca vigente de la anot. 014 (BBVA, escritura 5069/2022) se
        detecta con su acreedor: el hallazgo ALTO es REAL del folio."""
        from legal_analyzer import analizar_texto_certificado
        anot = ("ANOTACION: Nro 014 Fecha: 25-11-2022 Radicacion: 2022-50C-6-107189\n"
                "Doc: ESCRITURA 5069 DEL 09-11-2022 NOTARIA CUARENTA Y CUATRO DE BOGOTA\n"
                "ESPECIFICACION: GRAVAMEN: 0219 HIPOTECA ABIERTA SIN LIMITE DE CUANTIA\n"
                "A: BANCO BILBAO VIZCAYA ARGENTARIA COLOMBIA S.A. BBVA COLOMBIA\n")
        res = analizar_texto_certificado(anot)
        hip = [a for a in res["anotaciones"] if "Hipoteca" in a[2] and "CANCELADA" not in a[4]]
        self.assertEqual(len(hip), 1)
        self.assertIn("BBVA", hip[0][3].upper())
        self.assertTrue(any("Hipoteca" in h[3] for h in res["hallazgos"]))


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

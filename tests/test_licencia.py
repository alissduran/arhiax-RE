# -*- coding: utf-8 -*-
"""
Tests mejora 5 (Sprint 3): Licencia de Construcción en el dictamen.

Verifican que el analizador extrae los parámetros autorizados (número,
modalidad, pisos, altura, curaduría, fecha) de un PDF de licencia y que la
confrontación detecta el exceso frente a la LICENCIA (caso 'la constructora
edificó más pisos de los autorizados'), incluso cuando la capa POT no lo
refleje. Cuando la licencia no permite identificar pisos, nunca se inventa.
"""
import sys
import unittest
from io import BytesIO
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
API_DIR = ROOT_DIR / "api"
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(API_DIR))

from edificabilidad import (confrontacion_con_licencia,
                            hallazgo_exceso_licencia, filas_licencia)


def _pdf_de(texto):
    """Crea un PDF de una sola página con `texto` (para probar el analizador)."""
    from reportlab.pdfgen import canvas
    buf = BytesIO()
    c = canvas.Canvas(buf)
    y = 790
    for linea in texto.splitlines():
        if y < 40:
            c.showPage()
            y = 790
        c.drawString(50, y, linea[:100])
        y -= 14
    c.save()
    tmp = ROOT_DIR / "tmp_licencia_test.pdf"
    tmp.write_bytes(buf.getvalue())
    return tmp


_TEXTO_LICENCIA_11 = """
REPUBLICA DE COLOMBIA
CURADURIA URBANA No. 2 DE BOGOTA D.C.
LICENCIA DE CONSTRUCCION No. LC-19-000123
Modalidad: OBRA NUEVA
Se autoriza la construccion de una edificacion de 11 pisos, con altura de
36.5 m y area de construccion de 4500 m2, de conformidad con los planos
aprobados. Expedida el 15/03/2019. Vigencia 24 meses.
"""


class TestAnalizadorLicencia(unittest.TestCase):

    def test_extrae_parametros_autorizados(self):
        from licencia_analyzer import analizar_licencia
        pdf = _pdf_de(_TEXTO_LICENCIA_11)
        try:
            r = analizar_licencia(str(pdf))
        finally:
            pdf.unlink(missing_ok=True)
        self.assertTrue(r["disponible"])
        self.assertEqual(r["numero_licencia"], "LC-19-000123")
        self.assertEqual(r["pisos_aprobados"], 11)
        self.assertIn("36.5", str(r["altura_aprobada_m"]))
        self.assertEqual(r["curaduria"], "2")
        self.assertIn("OBRA NUEVA", (r["modalidad"] or "").upper())
        self.assertEqual(r["fecha_expedicion"], "15/03/2019")

    def test_licencia_sin_pisos_no_inventa(self):
        from licencia_analyzer import analizar_licencia
        txt = ("CURADURIA URBANA No. 5\nLICENCIA No. LU-2020-0456\n"
               "Modalidad: ADECUACION\nExpedida el 02/06/2020")
        pdf = _pdf_de(txt)
        try:
            r = analizar_licencia(str(pdf))
        finally:
            pdf.unlink(missing_ok=True)
        self.assertTrue(r["disponible"])
        self.assertEqual(r["numero_licencia"], "LU-2020-0456")
        self.assertIsNone(r["pisos_aprobados"])  # no se inventa

    def test_sin_archivo_no_disponible(self):
        from licencia_analyzer import analizar_licencia
        r = analizar_licencia(str(ROOT_DIR / "no_existe_lic.pdf"))
        self.assertFalse(r["disponible"])


class TestConfrontacionConLicencia(unittest.TestCase):

    def test_exceso_construido_vs_licenciado(self):
        """Caso del usuario: 20 pisos construidos, licencia autorizaba 11."""
        lic = {"numero_licencia": "LC-19-000123", "pisos_aprobados": 11}
        ent = {"tratamiento": "Consolidacion", "altura_maxima": "30"}  # POT permite más
        estado, texto = confrontacion_con_licencia("barranquilla", ent, 20, lic)
        self.assertEqual(estado, "exceso_licencia")
        self.assertIn("20", texto)
        self.assertIn("11", texto)
        h = hallazgo_exceso_licencia("barranquilla", ent, 20, lic)
        self.assertIsNotNone(h)
        self.assertEqual(h[0], "ALTO")
        self.assertIn("H-LIC", h[3])

    def test_dentro_de_licencia_sin_hallazgo(self):
        lic = {"numero_licencia": "LC-19-000123", "pisos_aprobados": 11}
        h = hallazgo_exceso_licencia("barranquilla", {}, 8, lic)
        self.assertIsNone(h)
        estado, texto = confrontacion_con_licencia("barranquilla", {}, 8, lic)
        self.assertEqual(estado, "dentro_licencia")
        self.assertIn("8", texto)

    def test_sin_licencia_cae_a_norma_pot(self):
        estado, _ = confrontacion_con_licencia("barranquilla",
                                               {"altura_maxima": "11"}, 20, None)
        self.assertEqual(estado, "sin_licencia")

    def test_licencia_sin_pisos_no_afirma_exceso(self):
        lic = {"numero_licencia": "LC-19-000123", "pisos_aprobados": None}
        self.assertIsNone(hallazgo_exceso_licencia("barranquilla", {}, 20, lic))
        estado, _ = confrontacion_con_licencia("barranquilla", {}, 20, lic)
        self.assertEqual(estado, "licencia_sin_pisos")

    def test_licencia_mayor_que_pot_advierte_derechos(self):
        """Licencia ampara más pisos que la capa POT: conforme, pero se avisa
        (posibles derechos adquiridos o norma anterior)."""
        lic = {"numero_licencia": "LC-19-000123", "pisos_aprobados": 20}
        ent = {"altura_maxima": "11"}
        estado, texto = confrontacion_con_licencia("barranquilla", ent, 12, lic)
        self.assertEqual(estado, "dentro_licencia")
        self.assertIn("derechos adquiridos", texto)

    def test_filas_licencia(self):
        lic = {"numero_licencia": "LC-19-000123", "pisos_aprobados": 11,
               "modalidad": "obra nueva", "curaduria": "2",
               "altura_aprobada_m": 36.5}
        filas = filas_licencia(lic)
        txt = " | ".join("{}={}".format(k, v) for k, v in filas)
        self.assertIn("LC-19-000123", txt)
        self.assertIn("11 piso", txt)


if __name__ == "__main__":
    unittest.main()

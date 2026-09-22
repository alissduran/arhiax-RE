# -*- coding: utf-8 -*-
"""
Tests de Edificabilidad y Altura Máxima (norma urbanística POT por ciudad).

Verifican que el dictamen confronta los pisos CONSTRUIDOS del catastro con la
ALTURA MÁXIMA normativa del polígono y detecta el exceso (caso 'construyeron
20 pisos donde la norma permitía 11'), y que cuando la capa oficial NO expone
número de pisos (Bogotá/ficha UPZ, planes parciales, franjas sin número) se
marca PENDIENTE sin inventar.
"""
import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
API_DIR = ROOT_DIR / "api"
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(API_DIR))

from edificabilidad import (altura_permitida, filas_edificabilidad,
                            _confrontacion, hallazgo_exceso_altura,
                            fuente_norma_texto, _parse_pisos)


class TestParsePisos(unittest.TestCase):

    def test_valores_numericos(self):
        self.assertEqual(_parse_pisos("11"), 11)
        self.assertEqual(_parse_pisos(11), 11)
        self.assertEqual(_parse_pisos("20.0"), 20)
        self.assertEqual(_parse_pisos("40"), 40)
        self.assertEqual(_parse_pisos(8), 8)

    def test_valores_no_numericos(self):
        self.assertIsNone(_parse_pisos(None))
        self.assertIsNone(_parse_pisos(""))
        self.assertIsNone(_parse_pisos("N/A"))
        self.assertIsNone(_parse_pisos("Plan Parcial"))
        self.assertIsNone(_parse_pisos("Sujeta a ficha"))


class TestAlturaPermitida(unittest.TestCase):

    def test_barranquilla_pisos(self):
        ent = {"tratamiento": "Consolidacion", "tipo_tratamiento": "Nivel 2",
               "altura_maxima": "11"}
        pisos, tipo, txt = altura_permitida("barranquilla", ent)
        self.assertEqual(pisos, 11)
        self.assertEqual(tipo, "pisos")
        self.assertIn("11", txt)

    def test_barranquilla_plan_parcial_no_inventa_pisos(self):
        ent = {"tratamiento": "Renovacion", "altura_maxima": "Plan Parcial"}
        pisos, tipo, txt = altura_permitida("barranquilla", ent)
        self.assertIsNone(pisos)
        self.assertEqual(tipo, "plan_parcial")

    def test_medellin_altura_normativa_pisos(self):
        ent = {"tratamiento": "Consolidacion Nivel 5", "altura_normativa": "20",
               "indice_construccion_max": "1,2", "densidad_max": "75"}
        pisos, tipo, txt = altura_permitida("medellin", ent)
        self.assertEqual(pisos, 20)
        self.assertEqual(tipo, "pisos")

    def test_medellin_sin_numero_usa_franja(self):
        ent = {"tratamiento": "Consolidacion Nivel 1", "altura_normativa": "N/A",
               "franja_altura": "Alta"}
        pisos, tipo, txt = altura_permitida("medellin", ent)
        self.assertIsNone(pisos)
        self.assertEqual(tipo, "franja")

    def test_bogota_siempre_ficha_upz(self):
        ent = {"upz": "LA SALLE"}
        pisos, tipo, txt = altura_permitida("bogota", ent)
        self.assertIsNone(pisos)
        self.assertEqual(tipo, "ficha_upz")  # nunca se inventa un máximo


class TestConfrontacionYHallazgo(unittest.TestCase):

    def test_exceso_construido_vs_permitido(self):
        """Caso del usuario: 20 pisos construidos donde la norma permite 11."""
        ent = {"tratamiento": "Consolidacion", "altura_maxima": "11"}
        estado, texto = _confrontacion("barranquilla", ent, 20)
        self.assertEqual(estado, "exceso")
        self.assertIn("20", texto)
        self.assertIn("11", texto)

        h = hallazgo_exceso_altura("barranquilla", ent, 20)
        self.assertIsNotNone(h)
        self.assertEqual(h[0], "ALTO")          # severidad
        self.assertIn("H-URB", h[3])            # título
        self.assertIn("20", h[3])
        self.assertIn("11", h[3])

    def test_dentro_de_altura_no_genera_hallazgo(self):
        ent = {"tratamiento": "Consolidacion", "altura_maxima": "11"}
        estado, texto = _confrontacion("barranquilla", ent, 8)
        self.assertEqual(estado, "dentro")
        self.assertIsNone(hallazgo_exceso_altura("barranquilla", ent, 8))

    def test_bogota_sin_numero_no_genera_hallazgo(self):
        """Sin máximo numérico (ficha UPZ) jamás se afirma exceso."""
        ent = {"upz": "LA SALLE"}
        estado, texto = _confrontacion("bogota", ent, 25)
        self.assertEqual(estado, "pendiente")
        self.assertIsNone(hallazgo_exceso_altura("bogota", ent, 25))

    def test_medellin_exceso_por_altura_normativa(self):
        ent = {"tratamiento": "Consolidacion Nivel 5", "altura_normativa": "20"}
        h = hallazgo_exceso_altura("medellin", ent, 24)
        self.assertIsNotNone(h)
        self.assertEqual(h[0], "ALTO")
        # 18 <= 20 -> sin exceso
        self.assertIsNone(hallazgo_exceso_altura("medellin", ent, 18))

    def test_sin_pisos_construidos_pendiente_sin_exceso(self):
        """03H.2 + 03I.1 · F12: NO_MATCH = la capa respondió SIN REGISTRO en el
        punto (no 'no hay edificación': el punto geocodificado puede caer en la
        vía). Se distingue de SOURCE_UNAVAILABLE y de NOT_EVALUATED."""
        ent = {"tratamiento": "Consolidacion", "altura_maxima": "11"}
        estado, texto = _confrontacion("barranquilla", ent, None, "NO_MATCH")
        self.assertEqual(estado, "sin_registro_construccion")
        self.assertIn("no se afirma ausencia de edificación", texto.lower())
        estado_na, _ = _confrontacion("barranquilla", ent, None, "SOURCE_UNAVAILABLE")
        self.assertEqual(estado_na, "pendiente_fuente")
        estado_ne, _ = _confrontacion("barranquilla", ent, None)
        self.assertEqual(estado_ne, "pendiente")
        self.assertIsNone(hallazgo_exceso_altura("barranquilla", ent, None))


class TestFilasYFuentes(unittest.TestCase):

    def test_filas_barranquilla(self):
        ent = {"tratamiento": "Consolidacion", "tipo_tratamiento": "Nivel 2",
               "altura_maxima": "11"}
        filas = filas_edificabilidad("barranquilla", ent, 20)
        txt = " | ".join("{}={}".format(k, v) for k, v in filas)
        self.assertIn("Altura normativa máxima", txt)
        self.assertIn("Pisos construidos", txt)
        self.assertIn("POSIBLE EXCESO", txt)
        self.assertIn("11", txt)

    def test_filas_bogota_incluye_upz_y_ficha(self):
        ent = {"upz": "LA SALLE", "clase_suelo": "Suelo Urbano"}
        filas = filas_edificabilidad("bogota", ent, 12)
        txt = " | ".join("{}={}".format(k, v) for k, v in filas)
        self.assertIn("LA SALLE", txt)
        self.assertIn("Ficha normativa de la UPZ", txt)

    def test_filas_medellin_incluye_indice_y_densidad(self):
        ent = {"tratamiento": "Consolidacion Nivel 5", "codigo_tratamiento": "Z5_CN5_17",
               "indice_construccion_max": "1,2", "densidad_max": "75",
               "franja_altura": "Baja", "altura_normativa": "20"}
        filas = filas_edificabilidad("medellin", ent, 10)
        txt = " | ".join("{}={}".format(k, v) for k, v in filas)
        self.assertIn("1,2", txt)
        self.assertIn("75", txt)
        self.assertIn("20", txt)

    def test_fuente_norma_texto_por_ciudad(self):
        self.assertIn("Acuerdo 48 de 2014",
                      fuente_norma_texto("medellin"))
        self.assertIn("Decreto 555 de 2021",
                      fuente_norma_texto("bogota"))
        self.assertIn("Tratamientos urbanísticos",
                      fuente_norma_texto("barranquilla"))


if __name__ == "__main__":
    unittest.main()

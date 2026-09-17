# -*- coding: utf-8 -*-
"""
Bug J: separación hipoteca / embargo / medida cautelar / gravamen genérico.

Antes "MEDIDA CAUTELAR" (inscripción de demanda, prohibición de enajenar, comiso)
se fundía en "GRAVAMEN: Embargo", y un gravamen genérico (servidumbre/usufructo)
no se distinguía de la hipoteca/embargo. Estos tests fijan la taxonomía separada.
"""
import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
API_DIR = ROOT_DIR / "api"
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(API_DIR))


def _tipos_de(texto):
    from legal_analyzer import analizar_texto_certificado
    res = analizar_texto_certificado(texto)
    return [a["tipo"] for a in res["anotaciones_detalle"]]


class TestClasificacionGravamenes(unittest.TestCase):

    def test_hipoteca_es_hipoteca(self):
        t = _tipos_de(
            "Nro Matrícula: 240-999999\n"
            "ANOTACION: Nro 001 Fecha: 10-05-2020\n"
            "ESPECIFICACION: GRAVAMEN: 0205 HIPOTECA ABIERTA SIN LIMITE DE CUANTIA\n"
            "DE: X\nA: BANCO DE BOGOTA S.A. NIT 8600029644\n")
        self.assertIn("GRAVAMEN: Hipoteca", t)

    def test_embargo_es_embargo(self):
        t = _tipos_de(
            "Nro Matrícula: 240-999999\n"
            "ANOTACION: Nro 002 Fecha: 10-05-2021\n"
            "ESPECIFICACION: EMBARGO EJECUTIVO\n"
            "DE: JUZGADO\nA: DEMANDANTE\n")
        self.assertIn("GRAVAMEN: Embargo", t)
        self.assertNotIn("MEDIDA CAUTELAR", t)

    def test_medida_cautelar_no_es_embargo(self):
        """Inscripción de demanda / prohibición de enajenar NO son embargo."""
        t = _tipos_de(
            "Nro Matrícula: 240-999999\n"
            "ANOTACION: Nro 003 Fecha: 10-05-2022\n"
            "ESPECIFICACION: MEDIDA CAUTELAR: INSCRIPCION DE DEMANDA\n"
            "DE: JUZGADO CIVIL\nA: DEMANDANTE\n")
        self.assertIn("MEDIDA CAUTELAR", t)
        self.assertNotIn("GRAVAMEN: Embargo", t)

    def test_gravamen_generico_servidumbre(self):
        t = _tipos_de(
            "Nro Matrícula: 240-999999\n"
            "ANOTACION: Nro 004 Fecha: 10-05-2023\n"
            "ESPECIFICACION: GRAVAMEN: SERVIDUMBRE DE TRANSITO\n"
            "DE: X\nA: Y\n")
        self.assertIn("GRAVAMEN", t)
        # No es hipoteca ni embargo
        self.assertNotIn("GRAVAMEN: Hipoteca", t)
        self.assertNotIn("GRAVAMEN: Embargo", t)


class TestTituluxTipoGravamen(unittest.TestCase):

    def test_mapeo_tipo_titulux(self):
        from titulux_bridge import _tipo_titulux
        self.assertEqual(_tipo_titulux("GRAVAMEN: HIPOTECA"), "hipoteca")
        self.assertEqual(_tipo_titulux("GRAVAMEN: EMBARGO"), "embargo")
        self.assertEqual(_tipo_titulux("MEDIDA CAUTELAR"), "medida_cautelar")
        self.assertEqual(_tipo_titulux("GRAVAMEN"), "gravamen")
        self.assertEqual(_tipo_titulux("SERVIDUMBRE DE TRANSITO"), "gravamen")

    def test_gravamenes_rule_considera_cautelar_y_generico(self):
        """La regla Titulux detecta medida cautelar y gravamen como carga vigente."""
        from arhia_title.contracts import Anotacion, Caso, Predio, Avaluo
        from arhia_title.rules import gravamenes
        caso = Caso(
            id="T", tipo="informe_base",
            predio=Predio("240-1", "COD"),
            anotaciones=(
                Anotacion(1, "medida_cautelar", "2022-01-01", estado="vigente"),
                Anotacion(2, "gravamen", "2022-01-02", estado="vigente"),
            ),
        )
        h = gravamenes(caso)
        self.assertTrue(any("medida_cautelar" in x.titulo or "medida" in x.titulo for x in h))
        self.assertTrue(any("gravamen" in x.titulo for x in h))


if __name__ == "__main__":
    unittest.main()

# -*- coding: utf-8 -*-
"""
Remediation 03D — identidad de unidad PH no destructiva + catastro determinista
+ gate de valoración. Caso de referencia: 040-646406 (TV 43 # 100-50 TO 8 AP 430).
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = ROOT / "api"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(API))


class TestUnidadInmobiliaria(unittest.TestCase):

    def test_extrae_torre_y_apartamento(self):
        from unidad_inmobiliaria import extraer_unidad
        u = extraer_unidad("TV 43 # 100-50 TO 8 AP 430")
        self.assertEqual(u["torre"], "8")
        self.assertEqual(u["apartamento"], "430")
        self.assertEqual(u["direccion_base"], "TV 43 # 100-50")

    def test_preserva_raw(self):
        from unidad_inmobiliaria import extraer_unidad
        u = extraer_unidad("TV 43 # 100-50 TO 8 AP 430")
        self.assertEqual(u["direccion_raw"], "TV 43 # 100-50 TO 8 AP 430")

    def test_sin_unidad_no_alucina(self):
        from unidad_inmobiliaria import extraer_unidad
        u = extraer_unidad("TV 43 # 100-50")
        self.assertIsNone(u["torre"])
        self.assertIsNone(u["apartamento"])
        self.assertEqual(u["direccion_base"], "TV 43 # 100-50")

    def test_unidades_distintas(self):
        from unidad_inmobiliaria import extraer_unidad
        a = extraer_unidad("TV 43 # 100-50 TO 8 AP 430")
        b = extraer_unidad("TV 43 # 100-50 TO 8 AP 431")
        self.assertEqual(a["torre"], b["torre"])          # mismo edificio
        self.assertNotEqual(a["apartamento"], b["apartamento"])  # distinta unidad


class TestLegalAnalyzerDireccion(unittest.TestCase):

    def test_direccion_preserva_unidad(self):
        from legal_analyzer import analizar_texto_certificado
        texto = (
            "Nro Matrícula: 040-646406\n"
            "DIRECCION DEL INMUEBLE:\n"
            "TV 43 # 100-50 TO 8 AP 430\n"
            "ANOTACION: Nro 001 Fecha: 10-10-2020\n"
            "ESPECIFICACION: COMPRAVENTA\nA: DURAN BACCA ALISSON CC 1045718995\n"
        )
        res = analizar_texto_certificado(texto)
        self.assertEqual(res["folio"], "040-646406")
        # La dirección completa sobrevive (no se trunca silenciosamente)
        self.assertIn("AP 430", res["direccion"])
        self.assertEqual(res["torre"], "8")
        self.assertEqual(res["apartamento"], "430")
        self.assertEqual(res["direccion_base"], "TV 43 # 100-50")


class TestSeleccionPredio(unittest.TestCase):

    def _f(self, nacional, homologado=None):
        return {"properties": {"numero_predial_nacional": nacional,
                               "codigo_homologado": homologado}}

    def test_exact_codigo_gana(self):
        from catastro_predio import _seleccionar_predio
        codigo = "080010102000001710004000000000"
        f, status = _seleccionar_predio(
            [{"features": [self._f("OTRO-1"), self._f(codigo), self._f("OTRO-2")]}],
            codigo, None)
        self.assertEqual(status, "EXACT")
        self.assertEqual(f["properties"]["numero_predial_nacional"], codigo)

    def test_orden_independiente(self):
        from catastro_predio import _seleccionar_predio
        codigo = "080010102000001710004000000000"
        feats = [self._f("A"), self._f(codigo), self._f("B")]
        for orden in ([feats[0], feats[1], feats[2]],
                      [feats[2], feats[0], feats[1]],
                      [feats[1], feats[2], feats[0]]):
            f, status = _seleccionar_predio([{"features": orden}], codigo, None)
            self.assertEqual(status, "EXACT")
            self.assertEqual(f["properties"]["numero_predial_nacional"], codigo)

    def test_ambiguo_sin_exact(self):
        from catastro_predio import _seleccionar_predio
        f, status = _seleccionar_predio(
            [{"features": [self._f("A"), self._f("B"), self._f("C")]}],
            "CODIGO_INEXISTENTE", None)
        self.assertIsNone(f)
        self.assertEqual(status, "AMBIGUOUS")


class TestValuationGate(unittest.TestCase):

    def test_unidad_ph_no_resuelta_no_emite(self):
        from dictamen_data import get_valuation
        v = get_valuation(58.75, "Miramar", estrato=4, ciudad="barranquilla",
                          unidad_ph_no_resuelta=True)
        self.assertIs(v["metodologia_aplica"], False)
        self.assertEqual(v["consolidado"], 0)
        self.assertIn("unidad PH", v["motivo_no_aplica"])

    def test_sin_unidad_ph_no_afecta(self):
        from dictamen_data import get_valuation
        v = get_valuation(58.75, "Miramar", estrato=4, ciudad="barranquilla",
                          unidad_ph_no_resuelta=False)
        self.assertIs(v["metodologia_aplica"], True)
        self.assertGreater(v["consolidado"], 0)


if __name__ == "__main__":
    unittest.main()

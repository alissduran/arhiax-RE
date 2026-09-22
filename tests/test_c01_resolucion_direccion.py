# -*- coding: utf-8 -*-
"""C-01 — Resolución de dirección sin valores por defecto (regresiones).

Defecto cerrado: `api/index.py::resolver_matricula_por_direccion()` devolvía el folio
del caso Golden HARDCODEADO por coincidencia de subcadenas («43» y «100») y
`estrato = 4` como valor POR DEFECTO para cualquier dirección desconocida; además
`create_dictamen`/`create_case` persistían ese 4 y el portal lo replicaba.

Estas pruebas fijan el contrato nuevo: estado por campo, sin defaults, y estrato solo
si una fuente oficial lo declara.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))


def _campo(value=None, status="UNRESOLVED", source=None, motivo=None):
    return {"value": value, "status": status, "source": source, "motivo": motivo}


class TestResumenLegacySinDefaults(unittest.TestCase):

    def test_solo_devuelve_campos_verificados(self):
        from address_resolution import resumen_legacy
        res = {"campos": {
            "folio_matricula": _campo("040-646406", "VERIFIED_OFFICIAL", "registro"),
            "barrio": _campo("Miramar", "VERIFIED_OFFICIAL", "capa oficial"),
            "estrato": _campo(None, "UNRESOLVED", motivo="sin registro en el punto"),
        }}
        self.assertEqual(resumen_legacy(res), ("040-646406", "Miramar", None))

    def test_unstatus_no_verificado_no_se_afirma(self):
        from address_resolution import resumen_legacy
        res = {"campos": {
            "folio_matricula": _campo("040-646406", "UNRESOLVED", motivo="parcial"),
            "barrio": _campo("Miramar", "CONFLICT"),
            "estrato": _campo("4", "UNRESOLVED"),
        }}
        self.assertEqual(resumen_legacy(res), ("Pendiente", "", None))

    def test_salida_vacia_es_pendiente_sin_estrato(self):
        from address_resolution import resumen_legacy
        self.assertEqual(resumen_legacy({}), ("Pendiente", "", None))


class TestResolucionEstructurada(unittest.TestCase):

    def setUp(self):
        import address_resolution as ar
        self.ar = ar
        self._pred = ar._predial_desde_capa_direcciones
        # Determinista y offline: sin predial oficial, sin geocoder, sin capas.
        ar._predial_desde_capa_direcciones = lambda direccion, fuentes: None
        import geocoder_catastral
        self._geo = geocoder_catastral.geocodificar_catastro_barranquilla
        geocoder_catastral.geocodificar_catastro_barranquilla = lambda *a, **k: None

    def tearDown(self):
        self.ar._predial_desde_capa_direcciones = self._pred
        import geocoder_catastral
        geocoder_catastral.geocodificar_catastro_barranquilla = self._geo

    def test_todo_campo_tiene_estado_y_motivo_cuando_no_hay_dato(self):
        res = self.ar.resolver_direccion("Carrera 5 # 20-33", ciudad="barranquilla")
        self.assertIn("campos", res)
        for nombre in ("folio_matricula", "barrio", "estrato", "numero_predial"):
            c = res["campos"][nombre]
            self.assertIn("status", c)
            if c["value"] in (None, ""):
                self.assertTrue(c.get("motivo"), f"{nombre} sin dato y sin motivo")
                self.assertNotEqual(c["status"], "VERIFIED_OFFICIAL")

    def test_estrato_nunca_por_defecto(self):
        res = self.ar.resolver_direccion("Calle 30 # 10-20", ciudad="barranquilla")
        self.assertIsNone(res["campos"]["estrato"]["value"])

    def test_direccion_vacia_no_resuelve_nada(self):
        res = self.ar.resolver_direccion("", ciudad="barranquilla")
        self.assertEqual(res["campos"]["folio_matricula"]["value"], None)
        self.assertIn("sin dirección", res["campos"]["folio_matricula"]["motivo"])

    def test_registra_las_fuentes_consultadas(self):
        res = self.ar.resolver_direccion("Calle 30 # 10-20", ciudad="barranquilla")
        self.assertIsInstance(res["fuentes"], list)
        self.assertTrue(any(f.get("id") in ("capa_direcciones_105", "geocoder_catastro_baq",
                                            "normalizador")
                            for f in res["fuentes"]))

    def test_no_hay_coincidencia_por_subcadenas(self):
        """La dirección del Golden NO se resuelve por contener «43» y «100»."""
        res = self.ar.resolver_direccion("Carrera 43 # 100-20", ciudad="medellin")
        self.assertIsNone(res["campos"]["folio_matricula"]["value"])
        # Y con las fuentes caídas, nada se afirma.
        self.assertIsNone(res["campos"]["estrato"]["value"])


class TestCaseServiceSinEstratoPorDefecto(unittest.TestCase):

    def test_estrato_ausente_no_se_convierte_en_4(self):
        import case_service
        capturado = {}

        class _Repo:
            def insert(self, **kw):
                capturado.update(kw)
                return 1

            def get(self, _id):
                return {"id": 1, **capturado}

        orig = case_service._repo
        case_service._repo = _Repo()
        try:
            case_service.create_case(folio_matricula="X", direccion="Y")
            self.assertEqual(capturado["estrato"], 0,
                             "sin estrato verificado se persiste 0, nunca 4")
        finally:
            case_service._repo = orig

    def test_estrato_valido_se_persiste(self):
        import case_service
        capturado = {}

        class _Repo:
            def insert(self, **kw):
                capturado.update(kw)
                return 1

            def get(self, _id):
                return {"id": 1, **capturado}

        orig = case_service._repo
        case_service._repo = _Repo()
        try:
            case_service.create_case(folio_matricula="X", direccion="Y", estrato=4)
            self.assertEqual(capturado["estrato"], 4)
            case_service.create_case(folio_matricula="X", direccion="Y", estrato=0)
            self.assertEqual(capturado["estrato"], 0, "0 significa «sin verificar»")
            case_service.create_case(folio_matricula="X", direccion="Y", estrato=9)
            self.assertEqual(capturado["estrato"], 0, "9 no es un estrato válido")
        finally:
            case_service._repo = orig


class TestRenderNoInventaEstrato(unittest.TestCase):

    def test_estrato_0_se_renderiza_pendiente(self):
        from dictamen_data import get_catastral_dt
        filas = dict(get_catastral_dt("Miramar", 58.75, estrato=0,
                                      destino_economico=None))
        self.assertIn("PENDIENTE", filas["Estrato"].upper())
        self.assertNotIn("0", filas["Estrato"])

    def test_estrato_valido_se_muestra(self):
        from dictamen_data import get_catastral_dt
        filas = dict(get_catastral_dt("Miramar", 58.75, estrato=4))
        self.assertEqual(filas["Estrato"], "4")


if __name__ == "__main__":
    unittest.main()

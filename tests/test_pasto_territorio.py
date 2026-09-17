# -*- coding: utf-8 -*-
"""
Tests del conector territorial de Pasto (api/pasto_territorio.py).

El geoportal municipal de Pasto se descubrió y verificó en vivo el 2026-09-16:
publica NUPRE, tratamiento urbanístico, edificabilidad (pisos/metros), clase de
suelo, área de actividad y riesgo volcánico por predio.

Sin red: `requests.get` se sustituye por un doble controlado.
"""
import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
API_DIR = ROOT_DIR / "api"
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(API_DIR))

# Respuestas reales medidas en Pasto centro (1.2136, -77.2811)
_TRATAMIENTOS = {
    "codigo_predial": "520010102000000770901900000000",
    "tratamiento_urbanistico": "PEMP - Conservacion del contexto con ajuste arquitectonico",
    "edificabilidad": "PEMP - 4 pisos - 11,20 metros",
    "nivel_intervencion_pemp": "Nivel 3 - Conservacion contextual",
    "unidad_territorial": "Centro",
    "sector_normativo": "CC-aa",
}
_AREAS = {
    "codigo_predial_nacional": "520010102000000770901900000000",
    "codigo_predial_anterior": "52001010200770901901",
    "clase_de_suelo": "Urbano",
    "area_actividad": "Plan especial de manejo y proteccion (PEMP) del centro historico",
    "codigo_area_actividad": "PEMP - AAM-I",
    "zava_t_269_de_2015": "No aplica",
    "zona_especial_uso_pemp": "Si aplica",
    "ubicacion": "Centro historico",
}
_RIESGOS = {
    "codigo_predial": "520010102000000770901900000000",
    "riesgo_volcanico_ea27": "Bajo",
    "inundacion_ea23": "No aplica",
    "subsidencia_ea29": "No aplica",
    "remocion_en_masa_ea19": "No aplica",
    "zava_t_269_de_2015": "No aplica",
}
_PREDIOS = {
    "codigo_predial_nacional": "520010102000000770901900000000",
    "codigo_predial_anterior": "52001010200770901901",
    "codigo_predial_corto": "010200770901901",
    "codigo_de_manzana": "52001010200000077",
    "sector_catastral": "02",
    "matricula_inmobiliaria": "Sin informacion",   # basura -> debe quedar None
    "direccion": "Sin informacion",
}


class _FakeResp:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


def _get_ok(url, params=None, **_k):
    if "/34/query" in url:
        return _FakeResp(200, {"features": [{"attributes": _PREDIOS}]})
    return _FakeResp(200, {"features": [{"attributes": _TRATAMIENTOS}]})


class TestPastoTerritorio(unittest.TestCase):

    def setUp(self):
        import pasto_territorio
        self.mod = pasto_territorio
        self.mod._CACHE.clear()
        self.orig_get = pasto_territorio.requests.get

    def tearDown(self):
        self.mod.requests.get = self.orig_get
        self.mod._CACHE.clear()

    def _router(self, mapa):
        """mapa: {id de capa: atributos o None}. None -> sin coincidencia."""
        def _get(url, params=None, **_k):
            for lid, attrs in mapa.items():
                if f"/{lid}/query" in url:
                    if attrs is None:
                        return _FakeResp(200, {"features": []})
                    return _FakeResp(200, {"features": [{"attributes": attrs}]})
            return _FakeResp(200, {"features": []})
        return _get

    def test_consulta_completa_por_punto(self):
        self.mod.requests.get = self._router({
            self.mod.CAPA_TRATAMIENTOS: _TRATAMIENTOS,
            self.mod.CAPA_AREAS_ACTIVIDAD: _AREAS,
            self.mod.CAPA_RIESGOS_URBANO: _RIESGOS,
            self.mod.CAPA_PREDIOS: _PREDIOS,
        })
        res = self.mod.consultar_pasto(lat=1.2136, lon=-77.2811)
        self.assertTrue(res["disponible"])
        p, e, r = res["predio"], res["entorno"], res["riesgos"]
        self.assertEqual(p["numero_predial_nacional"], "520010102000000770901900000000")
        self.assertEqual(e["clase_suelo"], "Urbano")
        self.assertEqual(e["altura_maxima"], "4")           # de "4 pisos"
        self.assertEqual(e["edificabilidad_texto"], "PEMP - 4 pisos - 11,20 metros")
        self.assertEqual(e["tratamiento"][:4], "PEMP")
        self.assertEqual(e["comuna"], "Centro")             # unidad territorial
        self.assertEqual(r["riesgo_volcanico_ea27"], "Bajo")
        # Los valores basura del municipio ('Sin informacion') NO se afirman
        self.assertIsNone(p["matricula_inmobiliaria"])
        self.assertIsNone(p["direccion_oficial"])

    def test_filas_para_el_dictamen(self):
        self.mod.requests.get = self._router({
            self.mod.CAPA_TRATAMIENTOS: _TRATAMIENTOS,
            self.mod.CAPA_AREAS_ACTIVIDAD: _AREAS,
            self.mod.CAPA_RIESGOS_URBANO: _RIESGOS,
            self.mod.CAPA_PREDIOS: _PREDIOS,
        })
        res = self.mod.consultar_pasto(lat=1.2136, lon=-77.2811)
        filas = dict(self.mod.filas_pasto(res))
        self.assertIn("Codigo predial nacional (NUPRE)", filas)
        self.assertIn("Edificabilidad (POT Pasto)", filas)
        self.assertIn("Tratamiento urbanistico (POT Pasto)", filas)
        self.assertIn("Clasificacion del suelo (POT Pasto)", filas)

    def test_consulta_por_codigo_predial(self):
        capturado = {}

        def _get(url, params=None, **_k):
            capturado["where"] = (params or {}).get("where")
            if "/34/query" in url:
                return _FakeResp(200, {"features": [{"attributes": _PREDIOS}]})
            return _FakeResp(200, {"features": [{"attributes": _TRATAMIENTOS}]})

        self.mod.requests.get = _get
        res = self.mod.consultar_pasto(codigo_predial="520010102000000770901900000000")
        self.assertTrue(res["disponible"])
        self.assertEqual(res["resolucion"], "por_codigo")
        self.assertIn("codigo_predial_nacional=", capturado["where"])

    def test_servicio_caido_no_afirma_datos(self):
        """Si el geoportal no responde: NO DISPONIBLE, sin datos inventados."""
        self.mod.requests.get = lambda *a, **k: _FakeResp(503)
        res = self.mod.consultar_pasto(lat=1.2136, lon=-77.2811)
        self.assertFalse(res["disponible"])
        self.assertEqual(res["predio"], {})
        self.assertEqual(res["entorno"], {})
        self.assertIn("NO DISPONIBLE", res["fuente"]["estado"])

    def test_error_arcgis_con_200_no_cuenta_como_sin_dato(self):
        """ArcGIS devuelve 200 + {'error':...}: es un FALLO, no 'sin coincidencia'."""
        self.mod.requests.get = lambda *a, **k: _FakeResp(
            200, {"error": {"code": 400, "message": "Invalid or missing input parameters."}})
        res = self.mod.consultar_pasto(lat=1.2136, lon=-77.2811)
        self.assertFalse(res["disponible"])

    def test_sin_coincidencia_en_el_punto(self):
        """El servicio responde pero el punto no cae en ningún predio."""
        self.mod.requests.get = self._router({
            self.mod.CAPA_TRATAMIENTOS: None,
            self.mod.CAPA_AREAS_ACTIVIDAD: None,
            self.mod.CAPA_RIESGOS_URBANO: None,
            self.mod.CAPA_PREDIOS: None,
        })
        res = self.mod.consultar_pasto(lat=99.0, lon=-77.0)
        self.assertTrue(res["disponible"])
        self.assertIn("sin coincidencia", res["fuente"]["estado"])

    def test_parseo_de_edificabilidad(self):
        f = self.mod._pisos_de_edificabilidad
        self.assertEqual(f("PEMP - 4 pisos - 11,20 metros"), 4)
        self.assertEqual(f("Hasta 12 pisos"), 12)
        self.assertIsNone(f("PEMP - Conservacion contextual"))
        self.assertIsNone(f(None))


if __name__ == "__main__":
    unittest.main()

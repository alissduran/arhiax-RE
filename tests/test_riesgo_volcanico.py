# -*- coding: utf-8 -*-
"""
Tests del riesgo volcánico (SGC, en vivo) — módulo api/riesgo_volcanico.py

Cubre los casos medidos en Pasto contra el servicio oficial del SGC:
  · Pasto centro  -> "Amenaza Baja" por caída de piroclastos (Galeras)
  · Pasto norte   -> "Amenaza Alta" por lahares (Galeras)  <- el crítico
  · servicio caído -> NO DISPONIBLE (nunca se asume "sin amenaza")
  · punto sin zona cartografiada -> se declara explícitamente

Sin red: `requests.get` se reemplaza por un doble controlado.
"""
import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
API_DIR = ROOT_DIR / "api"
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(API_DIR))


class _FakeResp:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


def _feature(**attrs):
    return {"features": [{"attributes": attrs}]}


class TestRiesgoVolcanico(unittest.TestCase):

    def setUp(self):
        import riesgo_volcanico
        self.mod = riesgo_volcanico
        self.mod._CACHE.clear()
        self.orig_get = riesgo_volcanico.requests.get

    def tearDown(self):
        self.mod.requests.get = self.orig_get
        self.mod._CACHE.clear()

    def test_pasto_centro_amenaza_baja(self):
        """Centro de Pasto: amenaza BAJA por caída de piroclastos del Galeras."""
        def _get(url, params=None, **k):
            if "/19/query" in url:
                return _FakeResp(200, _feature(
                    NOMBRE_VOLCAN="V. Galeras", GRADO_AMENAZA="Amenaza Baja",
                    FENOMENO_VOLCANICO="Caida de Piroclastos (ceniza y lapilli) transportados por el viento",
                    DESCRIPCION="Zona de caida de piroclastos de ceniza"))
            return _FakeResp(200, {"features": []})

        self.mod.requests.get = _get
        res = self.mod.verificar_riesgo_volcanico(1.2136, -77.2811)
        self.assertTrue(res["disponible"])
        self.assertEqual(res["nivel"], "BAJO")
        self.assertIn("Galeras", res["zonas"][0]["volcan"])
        # Amenaza baja NO genera hallazgo (no se alarma sin motivo)
        self.assertIsNone(self.mod.hallazgo_volcanico(res))

    def test_pasto_norte_amenaza_alta_lahares(self):
        """Norte de Pasto: amenaza ALTA por lahares -> hallazgo H-VOL ALTO."""
        def _get(url, params=None, **k):
            if "/19/query" in url:
                return _FakeResp(200, _feature(
                    NOMBRE_VOLCAN="V. Galeras", GRADO_AMENAZA="Amenaza Alta",
                    FENOMENO_VOLCANICO="Lahares",
                    DESCRIPCION="Areas afectadas por lahares en cuencas"))
            return _FakeResp(200, {"features": []})

        self.mod.requests.get = _get
        res = self.mod.verificar_riesgo_volcanico(1.2310, -77.2830)
        self.assertEqual(res["nivel"], "ALTO")
        h = self.mod.hallazgo_volcanico(res)
        self.assertIsNotNone(h)
        self.assertEqual(h[0], "ALTO")
        self.assertIn("H-VOL", h[3])
        self.assertIn("Lahares", h[3])

    def test_peor_grado_entre_varias_capas(self):
        """Si dos capas dan grados distintos, se reporta el PEOR."""
        def _get(url, params=None, **k):
            if "/19/query" in url:
                return _FakeResp(200, _feature(
                    NOMBRE_VOLCAN="V. Galeras", GRADO_AMENAZA="Amenaza Baja",
                    FENOMENO_VOLCANICO="Caida de Piroclastos"))
            return _FakeResp(200, _feature(
                NOMBRE_VOLCAN="Complejo volcanico Chiles - Cerro Negro",
                GRADO_AMENAZA="Amenaza Media", FENOMENO_VOLCANICO="Flujos piroclasticos"))

        self.mod.requests.get = _get
        res = self.mod.verificar_riesgo_volcanico(1.2050, -77.2600)
        self.assertEqual(res["nivel"], "MEDIO")
        self.assertEqual(len(res["zonas"]), 2)
        h = self.mod.hallazgo_volcanico(res)
        self.assertIsNotNone(h)
        self.assertEqual(h[0], "MEDIO")

    def test_servicio_caido_no_asume_sin_amenaza(self):
        """Si el SGC no responde: NO DISPONIBLE, y jamás 'sin riesgo'."""
        self.mod.requests.get = lambda *a, **k: _FakeResp(503)
        res = self.mod.verificar_riesgo_volcanico(1.2136, -77.2811)
        self.assertFalse(res["disponible"])
        self.assertEqual(res["nivel"], "NO EVALUADO")
        self.assertIsNone(self.mod.hallazgo_volcanico(res))
        filas = dict(self.mod.filas_riesgo_volcanico(res))
        self.assertIn("NO DISPONIBLE", filas["Riesgo volcanico (SGC)"])

    def test_punto_sin_zona_cartografiada(self):
        """El servicio responde pero el punto no cae en ninguna zona.

        03I.1 · F8: NO_INTERSECTION no es LOW_HAZARD. Antes este caso fijaba
        `nivel="BAJO"`, y el dictamen imprimía a la vez "Amenaza volcanica BAJA"
        (por `nivel`) y "SIN ZONA DE AMENAZA VOLCANICA CARTOGRAFIADA" (por
        `zonas`), contradiciéndose en el mismo capítulo 8.2. Ahora el estado único
        (`NO_COVERAGE`/`NO_INTERSECTION`) gobierna TODO el texto y el nivel queda
        NO EVALUADO (no se afirma amenaza que la fuente no declaró).
        """
        self.mod.requests.get = lambda *a, **k: _FakeResp(200, {"features": []})
        res = self.mod.verificar_riesgo_volcanico(4.7110, -74.0721)  # Bogotá
        self.assertTrue(res["disponible"])
        self.assertEqual(res["nivel"], "NO EVALUADO")
        self.assertIn(res["estado"], ("NO_INTERSECTION", "NO_COVERAGE"))
        filas = dict(self.mod.filas_riesgo_volcanico(res))
        _fila = filas["Riesgo volcanico (SGC)"]
        # No puede afirmar amenaza ni contradecirse: o declara la ausencia de
        # intersección, o declara que el punto está fuera de la cobertura.
        _sin_interseccion = "NO cae" in _fila
        _sin_cobertura = "fuera del area cartografiada" in _fila
        self.assertTrue(_sin_interseccion or _sin_cobertura, _fila)
        self.assertNotIn("amenaza volcanica BAJA", _fila)
        texto = self.mod.texto_volcanico(res)["hallazgo"]
        self.assertNotIn("Amenaza volcanica BAJA", texto)

    def test_excepcion_de_red_no_rompe(self):
        """Una excepción de red no debe propagarse (el dictamen nunca se cae)."""
        def _boom(*_a, **_k):
            raise RuntimeError("conexion caida")

        self.mod.requests.get = _boom
        res = self.mod.verificar_riesgo_volcanico(1.2136, -77.2811)
        self.assertFalse(res["disponible"])
        self.assertIn("conexion caida", res.get("error") or "")


if __name__ == "__main__":
    unittest.main()

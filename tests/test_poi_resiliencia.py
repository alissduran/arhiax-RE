# -*- coding: utf-8 -*-
"""
Resiliencia del motor de POIs (Overpass) — regresión de producción.

Bug corregido: en `poi_engine.py` el manejo del timeout comparaba contra
`OVPASS_REINTENTOS` (typo) en vez de `OVERPASS_REINTENTOS`. Eso lanzaba
`NameError` en CADA timeout de Overpass y, como la llamada no estaba protegida
en `pdf_compiler`, tumbaba la generación COMPLETA del dictamen: el usuario veía
"se queda pensando" y nunca salía el PDF.
"""
import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
API_DIR = ROOT_DIR / "api"
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(API_DIR))


class TestPoiEngineResiliencia(unittest.TestCase):

    def test_sin_typo_de_constante(self):
        """La constante del reintento debe llamarse OVERPASS_REINTENTOS (no OVPASS_*)."""
        src = (API_DIR / "poi_engine.py").read_text(encoding="utf-8")
        self.assertNotIn("OVPASS_REINTENTOS", src,
                         "typo reintroducido: 'OVPASS_REINTENTOS' no existe y lanza NameError")
        self.assertIn("OVERPASS_REINTENTOS", src)

    def test_timeout_no_lanza_nameerror_y_devuelve_vacio(self):
        """Con Overpass caído (timeout), debe devolver categorías VACÍAS, no excepción."""
        import requests
        import poi_engine

        orig_post = poi_engine.requests.post
        orig_cache = dict(poi_engine._POI_CACHE)
        orig_presupuesto = poi_engine.OVERPASS_PRESUPUESTO_TOTAL
        try:
            def _fake_post(*_a, **_k):
                raise requests.exceptions.Timeout("timeout simulado")

            poi_engine.requests.post = _fake_post
            poi_engine._POI_CACHE.clear()
            poi_engine.OVERPASS_PRESUPUESTO_TOTAL = 0.05  # no esperar los espejos
            # Coordenadas fuera de cualquier caché previa en disco
            res = poi_engine.get_nearby_pois(3.3333, -70.1111, radius=2000)

            self.assertEqual(set(res.keys()), set(poi_engine.CATEGORIAS))
            for cat, items in res.items():
                self.assertEqual(items, [], f"{cat} debería venir vacío, no {items}")
        finally:
            poi_engine.requests.post = orig_post
            poi_engine.OVERPASS_PRESUPUESTO_TOTAL = orig_presupuesto
            poi_engine._POI_CACHE.clear()
            poi_engine._POI_CACHE.update(orig_cache)


if __name__ == "__main__":
    unittest.main()

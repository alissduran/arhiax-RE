# -*- coding: utf-8 -*-
"""
Tests de scripts/publicar_equipamientos_agol.py (lógica pura, sin red).

El script publica los equipamientos de OpenStreetMap como capa propia en el
ArcGIS Online del usuario, para que la sección 03 del dictamen no dependa de la
disponibilidad de Overpass. Verificado en vivo (2026-09-16): exportó 989
equipamientos de Pasto en una sola consulta.
"""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SCRIPT = ROOT_DIR / "scripts" / "publicar_equipamientos_agol.py"

_spec = importlib.util.spec_from_file_location("publicar_equipamientos_agol", SCRIPT)
mod = importlib.util.module_from_spec(_spec)
sys.modules["publicar_equipamientos_agol"] = mod
_spec.loader.exec_module(mod)


class TestLogicaPura(unittest.TestCase):

    def test_clasificar_por_etiqueta_osm(self):
        self.assertEqual(mod.clasificar_poi({"amenity": "hospital"}), "Salud")
        self.assertEqual(mod.clasificar_poi({"amenity": "clinic"}), "Salud")
        self.assertEqual(mod.clasificar_poi({"amenity": "school"}), "Educacion")
        self.assertEqual(mod.clasificar_poi({"amenity": "university"}), "Educacion")
        self.assertEqual(mod.clasificar_poi({"shop": "supermarket"}), "Comercio")
        self.assertEqual(mod.clasificar_poi({"shop": "mall"}), "Comercio")
        self.assertEqual(mod.clasificar_poi({"leisure": "park"}), "Recreacion")

    def test_no_clasifica_lo_que_no_es_equipamiento(self):
        """Regresión: 'ParkTool' (shop=tools) NO es un parque."""
        self.assertIsNone(mod.clasificar_poi({"shop": "tools"}))
        self.assertIsNone(mod.clasificar_poi({"shop": "clothes_repair"}))
        self.assertIsNone(mod.clasificar_poi({}))
        self.assertIsNone(mod.clasificar_poi(None))

    def test_filtro_por_area(self):
        bbox = mod.CIUDADES["pasto"]
        self.assertTrue(mod.dentro_del_area(1.2136, -77.2811, bbox))    # Pasto
        self.assertFalse(mod.dentro_del_area(10.987, -74.8115, bbox))   # Barranquilla

    def test_fila_desde_elemento_nodo(self):
        elem = {"type": "node", "lat": 1.2136, "lon": -77.2811,
                "tags": {"name": "Hospital de Prueba", "amenity": "hospital",
                         "addr_street": "Calle 18", "addr_housenumber": "25"}}
        f = mod.fila_desde_elemento(elem, mod.CIUDADES["pasto"])
        self.assertIsNotNone(f)
        self.assertEqual(f["categoria"], "Salud")
        self.assertEqual(f["nombre"], "Hospital de Prueba")
        self.assertEqual(f["tipo_osm"], "hospital")
        self.assertIn("Calle 18", f["direccion"])

    def test_fila_desde_elemento_way_usa_center(self):
        elem = {"type": "way", "center": {"lat": 1.22, "lon": -77.28},
                "tags": {"name": "Parque Central", "leisure": "park"}}
        f = mod.fila_desde_elemento(elem, mod.CIUDADES["pasto"])
        self.assertIsNotNone(f)
        self.assertEqual(f["categoria"], "Recreacion")

    def test_descarta_sin_nombre_fuera_de_area_o_sin_categoria(self):
        bbox = mod.CIUDADES["pasto"]
        self.assertIsNone(mod.fila_desde_elemento(
            {"lat": 1.21, "lon": -77.28, "tags": {"amenity": "hospital"}}, bbox))  # sin nombre
        self.assertIsNone(mod.fila_desde_elemento(
            {"lat": 10.98, "lon": -74.81, "tags": {"name": "X", "amenity": "hospital"}}, bbox))
        self.assertIsNone(mod.fila_desde_elemento(
            {"lat": 1.21, "lon": -77.28, "tags": {"name": "Y", "shop": "tools"}}, bbox))

    def test_deduplicar_por_nombre_y_categoria(self):
        filas = [
            {"nombre": "Hospital A", "categoria": "Salud"},
            {"nombre": "Hospital A", "categoria": "Salud"},
            {"nombre": "Hospital A", "categoria": "Educacion"},
        ]
        self.assertEqual(len(mod.deduplicar(filas)), 2)

    def test_escribir_csv(self):
        import shutil
        filas = [{"nombre": "A", "categoria": "Salud", "tipo_osm": "hospital",
                  "direccion": "", "lat": 1.2, "lon": -77.2}]
        # Carpeta dentro del repo: el temp del sistema puede no ser borrable en
        # entornos confinados (el cleanup fallaba con PermissionError).
        carpeta = ROOT_DIR / "_tmp_test_csv"
        shutil.rmtree(carpeta, ignore_errors=True)
        try:
            p = mod.escribir_csv(filas, carpeta / "x.csv")
            texto = p.read_text(encoding="utf-8")
            self.assertIn("nombre,categoria,tipo_osm", texto)
            self.assertIn("hospital", texto)
        finally:
            shutil.rmtree(carpeta, ignore_errors=True)

    def test_payload_publish_usa_lat_lon(self):
        p = mod.payload_publish("Equipamientos_Pasto")
        self.assertEqual(p["locationType"], "coordinates")
        self.assertEqual(p["latitudeFieldName"], "lat")
        self.assertEqual(p["longitudeFieldName"], "lon")

    def test_consulta_overpass_incluye_bbox_y_claves(self):
        q = mod._consulta_overpass((-77.5, 1.0, -77.0, 1.45))
        self.assertIn("1.0,-77.5,1.45,-77.0", q)
        for clave in mod.CLAVES_OSM:
            self.assertIn(f'"{clave}"', q)
        self.assertIn("out center;", q)


if __name__ == "__main__":
    unittest.main()

# -*- coding: utf-8 -*-
"""Evidencia local (sin dependencias): ¿el punto Golden cae en las capas POT empaquetadas?

Ray casting puro sobre Polygon/MultiPolygon GeoJSON.
"""
from __future__ import annotations

import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PUNTOS = [("oficial_predio_2b", 11.006055954316363, -74.8375696549899),
          ("hint_estrato_03i1", 11.005378, -74.8386199)]
ARCHIVOS = [RAIZ / "api" / "data" / "amenaza_remocion_masa.geojson",
            RAIZ / "api" / "data" / "areas_en_riesgo.geojson"]


def _en_anillo(x: float, y: float, anillo) -> bool:
    dentro = False
    n = len(anillo)
    for i in range(n):
        x1, y1 = anillo[i][0], anillo[i][1]
        x2, y2 = anillo[(i + 1) % n][0], anillo[(i + 1) % n][1]
        if (y1 > y) != (y2 > y):
            xi = (x2 - x1) * (y - y1) / ((y2 - y1) or 1e-18) + x1
            if x < xi:
                dentro = not dentro
    return dentro


def _en_poligono(x: float, y: float, anillos) -> bool:
    if not anillos or not _en_anillo(x, y, anillos[0]):
        return False
    for hoyo in anillos[1:]:
        if _en_anillo(x, y, hoyo):
            return False
    return True


def contiene(geom: dict, x: float, y: float) -> bool:
    t = geom.get("type")
    c = geom.get("coordinates")
    if t == "Polygon":
        return _en_poligono(x, y, c)
    if t == "MultiPolygon":
        return any(_en_poligono(x, y, poly) for poly in c)
    return False


def main() -> int:
    for etiqueta, lat, lon in PUNTOS:
        print("#" * 72)
        print(f"PUNTO {etiqueta} lat={lat} lon={lon}")
        for ruta in ARCHIVOS:
            if not ruta.exists():
                print("no existe:", ruta)
                continue
            gj = json.loads(ruta.read_text(encoding="utf-8"))
            hits = [f.get("properties") for f in (gj.get("features") or [])
                    if contiene(f.get("geometry") or {}, lon, lat)]
            print("-" * 70)
            print(ruta.name, "| features:", len(gj.get("features") or []),
                  "| contienen el punto:", len(hits))
            for h in hits[:5]:
                print("   ->", json.dumps(h, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

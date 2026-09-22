# -*- coding: utf-8 -*-
"""03I.1 — Sonda de ESTRATO, ronda 4: corroboracion ESPACIAL correcta.

La ronda 3 mostro que el prefijo de 17 digitos del numero predial
(08001010300001004) es la UNICA manzana oficial que matchea, con estrato '4' y
barrio Miramar. Falta corroborar que esa manzana sea la DEL PREDIO:
  * distancia real (en metros) del punto autorizado a cada poligono candidato,
    con geometrias pedidas en outSR=4326 (la ronda anterior mezclaba SR),
  * punto OFICIAL de la direccion (servicio ordenamiento/direcciones),
  * capa Manzana/Direccion de catastro/datosabiertos.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "ARHIAX-RE/1.0 (Sinergia Consulting Group)"}
TIMEOUT = 15.0

SVC_ORD = "https://miciudad.barranquilla.gov.co/gis/rest/services/ordenamiento"
SVC_CAT = "https://miciudad.barranquilla.gov.co/gis/rest/services/catastro"
MANZANA_PREDIAL = "08001010300001004"
LAT, LON = 11.005378, -74.8386199
DIRECCION = "TRANSVERSAL 43 100 50"

TRACE: list = []


def get(url, params, etq):
    item = {"via": etq, "url": url, "params": params}
    try:
        r = requests.get(url, params=params, headers=UA, timeout=TIMEOUT)
        item["http"] = r.status_code
        data = r.json()
        if isinstance(data, dict) and data.get("error"):
            item["error"] = str(data["error"])[:200]
            TRACE.append(item)
            return {}
        item["ok"] = True
        feats = data.get("features")
        if feats is not None:
            item["n_features"] = len(feats)
            item["attrs"] = [f.get("attributes") for f in feats[:6]]
        else:
            item["keys"] = list(data.keys())[:15]
        TRACE.append(item)
        return data
    except Exception as e:  # noqa: BLE001
        item["error"] = f"{type(e).__name__}: {e}"
        TRACE.append(item)
        return {}


def _m(a, b):
    (la1, lo1), (la2, lo2) = a, b
    p = math.pi / 180
    h = 0.5 - math.cos((la2 - la1) * p) / 2 + math.cos(la1 * p) * math.cos(la2 * p) * (1 - math.cos((lo2 - lo1) * p)) / 2
    return round(2 * 6371000 * math.asin(math.sqrt(h)), 1)


def dist_poligono(rings):
    """Distancia (m) del punto al poligono en grados WGS84; 0 si lo contiene."""
    from shapely.geometry import Point, Polygon
    pt = Point(LON, LAT)
    poly = Polygon([(p[0], p[1]) for p in rings[0]])
    if not poly.is_valid:
        poly = poly.buffer(0)
    if poly.contains(pt):
        return 0.0
    near = poly.exterior.interpolate(poly.exterior.project(pt))
    return _m((LAT, LON), (near.y, near.x))


def espacial():
    print("=== 1. DISTANCIAS REALES (outSR=4326) ===")
    d = get(f"{SVC_ORD}/estratificacion/MapServer/1/query",
            {"where": "1=1", "outFields": "*", "returnGeometry": "true", "outSR": "4326",
             "geometry": json.dumps({"x": LON, "y": LAT, "spatialReference": {"wkid": 4326}}),
             "geometryType": "esriGeometryPoint", "inSR": "4326",
             "distance": 150, "units": "esriSRUnit_Meter",
             "spatialRel": "esriSpatialRelIntersects", "f": "json"},
            "manzanas en buffer 150 m (4326)")
    for f in ((d or {}).get("features") or []):
        at = f.get("attributes") or {}
        rings = (f.get("geometry") or {}).get("rings")
        dd = dist_poligono(rings) if rings else None
        marca = "  <== MANZANA DEL PREDIAL (prefijo)" if at.get("codigo_manzana") == MANZANA_PREDIAL else ""
        print(f"  {at.get('codigo_manzana')} estrato={at.get('estratificacion')!r:12} "
              f"barrio={at.get('nombre_barrio')!r} dist={dd} m{marca}")
    d2 = get(f"{SVC_ORD}/estratificacion/MapServer/1/query",
             {"where": f"codigo_manzana='{MANZANA_PREDIAL}'", "outFields": "*",
              "returnGeometry": "true", "outSR": "4326", "f": "json"},
             f"manzana del predial {MANZANA_PREDIAL} (4326)")
    for f in ((d2 or {}).get("features") or []):
        at = f.get("attributes") or {}
        rings = (f.get("geometry") or {}).get("rings")
        print(f"  [predial] {at.get('codigo_manzana')} estrato={at.get('estratificacion')!r} "
              f"barrio={at.get('nombre_barrio')!r} dist_punto={dist_poligono(rings) if rings else None} m")


def punto_oficial_direccion():
    print("\n=== 2. PUNTO OFICIAL DE LA DIRECCION (ordenamiento/direcciones) ===")
    d0 = get(f"{SVC_ORD}/direcciones/MapServer", {"f": "json"}, "ordenamiento/direcciones metadata")
    for l in (d0.get("layers") or []):
        print(f"  capa {l.get('id')}: {l.get('name')}")
        lid = l.get("id")
        d1 = get(f"{SVC_ORD}/direcciones/MapServer/{lid}", {"f": "json"}, f"direcciones capa {lid} fields")
        campos = [fld.get("name") for fld in (d1.get("fields") or [])]
        print(f"    campos: {campos}")
        for where in (f"UPPER(nomenclatura) LIKE '%43%100%50%'",
                      f"UPPER(direccion) LIKE '%43%100%50%'",
                      "1=1"):
            if not any(c.lower().startswith(("nomenclatura", "direccion", "texto", "name")) for c in campos) and where != "1=1":
                continue
            d2 = get(f"{SVC_ORD}/direcciones/MapServer/{lid}/query",
                     {"where": where, "outFields": "*", "returnGeometry": "true",
                      "outSR": "4326", "resultRecordCount": 5, "f": "json"},
                     f"direcciones capa {lid} where={where[:40]}")
            feats = (d2 or {}).get("features") or []
            if feats:
                for f in feats[:3]:
                    at = f.get("attributes") or {}
                    g = f.get("geometry") or {}
                    if g.get("x") is not None:
                        print(f"    {at} -> ({g.get('y'):.6f},{g.get('x'):.6f}) "
                              f"dist_al_punto={_m((LAT, LON), (g.get('y'), g.get('x')))} m")
                break


def capa_manzana_catastro():
    print("\n=== 3. CAPA MANZANA / DIRECCION DE catastro/datosabiertos ===")
    d0 = get(f"{SVC_CAT}/datosabiertos/MapServer", {"f": "json"}, "datosabiertos metadata")
    capas = {l.get("name"): l.get("id") for l in (d0.get("layers") or [])}
    print("  capas:", capas)
    for nombre in ("Manzana", "Dirección", "Nomenclatura", "Terreno"):
        lid = capas.get(nombre)
        if lid is None:
            continue
        d = get(f"{SVC_CAT}/datosabiertos/MapServer/{lid}/query",
                {"where": "1=1", "outFields": "*", "returnGeometry": "false", "outSR": "4326",
                 "geometry": json.dumps({"x": LON, "y": LAT, "spatialReference": {"wkid": 4326}}),
                 "geometryType": "esriGeometryPoint", "inSR": "4326",
                 "distance": 60, "units": "esriSRUnit_Meter",
                 "spatialRel": "esriSpatialRelIntersects", "f": "json"},
                f"datosabiertos {nombre} punto+60m")
        feats = (d or {}).get("features") or []
        print(f"  {nombre} (capa {lid}): {len(feats)} features")
        for f in feats[:3]:
            print("   ->", f.get("attributes"))


def main() -> int:
    espacial()
    punto_oficial_direccion()
    capa_manzana_catastro()
    out = ROOT / "docs" / "forensics" / "040-646406" / "golden_03i1"
    out.mkdir(parents=True, exist_ok=True)
    (out / "ESTRATO_PROBE_TRACE_4.json").write_text(
        json.dumps(TRACE, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\ntrace: {out / 'ESTRATO_PROBE_TRACE_4.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

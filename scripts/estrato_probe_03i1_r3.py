# -*- coding: utf-8 -*-
"""03I.1 — Sonda de ESTRATO, ronda 3: unicidad del prefijo + corroboracion.

Hipotesis a verificar (NO se acepta sin corroborar): el `codigo_manzana` oficial
(17 digitos) es el PREFIJO del numero predial (30 digitos). Se prueba:
  1. que la derivacion sea UNICA (un solo prefijo matchea una sola manzana),
  2. que la manzana derivada caiga cerca del punto autorizado,
  3. que la manzana derivada coincida con la manzana CADASTRAL del punto
     (capa catastro/manzanas, point-in-polygon),
  4. que exista una via directa predio -> estrato (capa lotes/predios).
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
NUMERO_PREDIAL = "080010103000010040001908040002"
LAT, LON = 11.005378, -74.8386199
BARRIO_OFICIAL = "Miramar"

TRACE: list = []


def get(url, params, etq, keep_geom=False):
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
            item["attrs"] = [f.get("attributes") for f in feats[:12]]
            if keep_geom:
                item["rings"] = [(f.get("geometry") or {}).get("rings") for f in feats[:12]]
        TRACE.append(item)
        return data
    except Exception as e:  # noqa: BLE001
        item["error"] = f"{type(e).__name__}: {e}"
        TRACE.append(item)
        return {}


def _haversine(a, b):
    (la1, lo1), (la2, lo2) = a, b
    p = math.pi / 180
    d = 0.5 - math.cos((la2 - la1) * p) / 2 + math.cos(la1 * p) * math.cos(la2 * p) * (1 - math.cos((lo2 - lo1) * p)) / 2
    return 2 * 6371000 * math.asin(math.sqrt(d))


def unicidad_prefijo():
    print("=== 1. UNICIDAD DE LA DERIVACION POR PREFIJO ===")
    resultados = []
    for L in range(14, 23):
        pref = NUMERO_PREDIAL[:L]
        d = get(f"{SVC_ORD}/estratificacion/MapServer/1/query",
                {"where": f"codigo_manzana='{pref}'", "outFields": "*",
                 "returnGeometry": "true", "f": "json"},
                f"prefijo {L} = {pref}", keep_geom=True)
        feats = (d or {}).get("features") or []
        if feats:
            at = feats[0].get("attributes") or {}
            pol = (feats[0].get("geometry") or {}).get("rings")
            dist = None
            if pol:
                try:
                    from shapely.geometry import Point, Polygon
                    poly = Polygon([(p[0], p[1]) for p in pol[0]])
                    pt = Point(LON, LAT)
                    if poly.is_valid:
                        if poly.contains(pt):
                            dist = 0.0
                        else:
                            # distancia del punto al borde, en metros (aprox local)
                            d_deg = (poly.exterior.distance(pt))
                            dist = round(_haversine((LAT, LON), (LAT + d_deg, LON)), 1)
                except Exception as e:  # noqa: BLE001
                    dist = f"n/d ({e})"
            resultados.append((L, at.get("codigo_manzana"), at.get("estratificacion"),
                               at.get("nombre_barrio"), dist))
            print(f"  L={L:2d} manzana={at.get('codigo_manzana')} estrato={at.get('estratificacion')!r} "
                  f"barrio={at.get('nombre_barrio')!r} dist_punto={dist} m")
        else:
            print(f"  L={L:2d} sin coincidencia ({pref})")
    return resultados


def manzana_catastral():
    print("\n=== 2. MANZANA CADASTRAL DEL PUNTO (catastro/manzanas) ===")
    d0 = get(f"{SVC_CAT}/manzanas/MapServer", {"f": "json"}, "catastro/manzanas metadata")
    for l in (d0.get("layers") or []):
        print(f"  capa {l.get('id')}: {l.get('name')}")
    for lid in [l.get("id") for l in (d0.get("layers") or []) if l.get("id") is not None][:6]:
        d = get(f"{SVC_CAT}/manzanas/MapServer/{lid}/query",
                {"where": "1=1", "outFields": "*", "returnGeometry": "false",
                 "geometry": json.dumps({"x": LON, "y": LAT, "spatialReference": {"wkid": 4326}}),
                 "geometryType": "esriGeometryPoint", "inSR": "4326",
                 "spatialRel": "esriSpatialRelIntersects", "f": "json"},
                f"manzanas capa {lid} punto")
        feats = (d or {}).get("features") or []
        if feats:
            print(f"  capa {lid}: {len(feats)} manzana(s) contienen el punto:")
            for f in feats[:3]:
                print("   ->", f.get("attributes"))


def lotes_predio():
    print("\n=== 3. VIA DIRECTA PREDIO -> ESTRATO (catastro/lotes, datosabiertos) ===")
    for svc, capas in (("lotes", None), ("datosabiertos", None)):
        d0 = get(f"{SVC_CAT}/{svc}/MapServer", {"f": "json"}, f"catastro/{svc} metadata")
        ids = [l.get("id") for l in (d0.get("layers") or [])]
        print(f"  catastro/{svc} capas: {[l.get('name') for l in (d0.get('layers') or [])]}")
        for lid in ids[:4]:
            if lid is None:
                continue
            d = get(f"{SVC_CAT}/{svc}/MapServer/{lid}/query",
                    {"where": "1=1", "outFields": "*", "returnGeometry": "false",
                     "geometry": json.dumps({"x": LON, "y": LAT, "spatialReference": {"wkid": 4326}}),
                     "geometryType": "esriGeometryPoint", "inSR": "4326",
                     "spatialRel": "esriSpatialRelIntersects", "f": "json"},
                    f"{svc} capa {lid} punto")
            feats = (d or {}).get("features") or []
            if feats:
                at = feats[0].get("attributes") or {}
                campos_clave = {k: v for k, v in at.items()
                                if any(t in k.lower() for t in
                                       ("manzana", "estrato", "predial", "nupre", "lote"))}
                print(f"   {svc} capa {lid}: {campos_clave}")


def main() -> int:
    res = unicidad_prefijo()
    manzana_catastral()
    lotes_predio()
    print("\n=== RESUMEN ===")
    unicos = [r for r in res if r[2]]
    print(f"prefijos con match: {[(r[0], r[1], r[2]) for r in unicos]}")
    out = ROOT / "docs" / "forensics" / "040-646406" / "golden_03i1"
    out.mkdir(parents=True, exist_ok=True)
    (out / "ESTRATO_PROBE_TRACE_3.json").write_text(
        json.dumps(TRACE, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"trace: {out / 'ESTRATO_PROBE_TRACE_3.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

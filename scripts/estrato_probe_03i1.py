# -*- coding: utf-8 -*-
"""03I.1 — Sonda de ESTRATO oficial (Barranquilla) para el caso 040-646406.

INVESTIGACIÓN, no producto: prueba vías OFICIALES para resolver el estrato
socioeconómico del predio y registra el trace crudo de cada intento.

Regla: no se infiere, no se usa default, no se copia el histórico. Si ninguna
fuente oficial aporta el estrato, el resultado es UNRESOLVED y eso es válido.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "api"))

UA = {"User-Agent": "ARHIAX-RE/1.0 (Sinergia Consulting Group)"}
TIMEOUT = 12.0

BASE_ORD = "https://miciudad.barranquilla.gov.co/gis/rest/services/ordenamiento"
BASE_CAT = "https://miciudad.barranquilla.gov.co/gis/rest/services/catastro"

LAT, LON = 11.005378, -74.8386199
NUMERO_PREDIAL = "080010103000010040001908040002"
NUPRE = "AFT0005BOHA"
DIRECCION = "TRANSVERSAL 43 100 50"

TRACE: list = []


def _get(url: str, params: dict, etiqueta: str) -> dict:
    item = {"via": etiqueta, "url": url, "params": params}
    try:
        r = requests.get(url, params=params, headers=UA, timeout=TIMEOUT)
        item["http"] = r.status_code
        try:
            data = r.json()
        except Exception:
            item["error"] = "respuesta no JSON"
            item["raw"] = r.text[:300]
            TRACE.append(item)
            return {}
        if isinstance(data, dict) and data.get("error"):
            item["error"] = str(data["error"])[:300]
            TRACE.append(item)
            return {}
        item["ok"] = True
        feats = data.get("features")
        if feats is not None:
            item["n_features"] = len(feats)
            item["campos"] = sorted((feats[0].get("attributes") or {}).keys()) if feats else []
            item["sample"] = feats[0].get("attributes") if feats else None
        else:
            item["sample"] = {k: v for k, v in list(data.items())[:12]}
        TRACE.append(item)
        return data
    except Exception as e:  # noqa: BLE001
        item["error"] = f"{type(e).__name__}: {e}"
        TRACE.append(item)
        return {}


def step_meta():
    print("\n=== 0. METADATA DE LA CAPA DE ESTRATIFICACION ===")
    for url, etq in (
        (f"{BASE_ORD}/estratificacion/MapServer", "ordenamiento/estratificacion (root)"),
        (f"{BASE_ORD}/estratificacion/MapServer/1", "estratificacion capa 1 (metadata)"),
    ):
        d = _get(url, {"f": "json"}, etq)
        if d:
            print(f"[{etq}] http={TRACE[-1].get('http')} "
                  f"name={d.get('name')} type={d.get('type')} "
                  f"fields={[f.get('name') for f in (d.get('fields') or [])]}")


def step_punto():
    print("\n=== 1. CONSULTA POR PUNTO (la que hace el producto hoy) ===")
    for etq, extra in (
        ("estratificacion punto exacto", {}),
        ("estratificacion punto + buffer 25 m", {"distance": 25, "units": "esriSRUnit_Meter"}),
        ("estratificacion punto + buffer 100 m", {"distance": 100, "units": "esriSRUnit_Meter"}),
    ):
        params = {
            "where": "1=1", "outFields": "*", "returnGeometry": "false",
            "geometry": json.dumps({"x": LON, "y": LAT, "spatialReference": {"wkid": 4326}}),
            "geometryType": "esriGeometryPoint", "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects", "f": "json",
        }
        params.update(extra)
        d = _get(f"{BASE_ORD}/estratificacion/MapServer/1/query", params, etq)
        t = TRACE[-1]
        print(f"[{etq}] http={t.get('http')} n={t.get('n_features')} err={t.get('error')} "
              f"sample={t.get('sample')}")


def step_barrio():
    print("\n=== 2. MANZANAS DEL BARRIO MIRAMAR (atributo) + PIP LOCAL ===")
    d = _get(f"{BASE_ORD}/estratificacion/MapServer/1/query",
             {"where": "UPPER(nombre_barrio) LIKE '%MIRAMAR%'", "outFields": "*",
              "returnGeometry": "true", "f": "json"}, "estratificacion barrio MIRAMAR")
    feats = (d or {}).get("features") or []
    print(f"[barrio MIRAMAR] manzanas devueltas: {len(feats)}")
    if feats:
        print("  campos:", sorted((feats[0].get('attributes') or {}).keys()))
        try:
            from shapely.geometry import Point, shape
            pt = Point(LON, LAT)
            hits = []
            for f in feats:
                rings = (f.get("geometry") or {}).get("rings")
                if not rings:
                    continue
                from shapely.geometry import Polygon
                poly = Polygon([(p[0], p[1]) for p in rings[0]])
                if poly.is_valid and poly.contains(pt):
                    hits.append(f.get("attributes"))
            print(f"  PIP local: polígonos que CONTIENEN el punto = {len(hits)}")
            for h in hits[:3]:
                print("   ->", {k: h.get(k) for k in
                                ("estratificacion", "codigo_manzana", "nombre_barrio")})
            if hits:
                print(f"  ESTRATO POR PIP LOCAL: {hits[0].get('estratificacion')}")
        except Exception as e:  # noqa: BLE001
            print(f"  PIP local no disponible: {e}")


def step_manzana():
    print("\n=== 3. MANZANA OFICIAL DEL PUNTO (catastro datosabiertos capa 320) ===")
    d = _get(f"{BASE_CAT}/datosabiertos/MapServer/320/query",
             {"where": "1=1", "outFields": "*", "returnGeometry": "false",
              "geometry": json.dumps({"x": LON, "y": LAT, "spatialReference": {"wkid": 4326}}),
              "geometryType": "esriGeometryPoint", "inSR": "4326",
              "spatialRel": "esriSpatialRelIntersects", "f": "json"}, "capata 320 Manzana punto")
    t = TRACE[-1]
    print(f"[capa 320] http={t.get('http')} n={t.get('n_features')} err={t.get('error')} "
          f"sample={t.get('sample')}")
    codigo = None
    feats = (d or {}).get("features") or []
    if feats:
        at = feats[0].get("attributes") or {}
        codigo = (at.get("codigo_manzana") or at.get("CODIGO_MANZANA")
                  or at.get("manzana") or at.get("MANZANA"))
    if codigo:
        print(f"[capa 320] codigo_manzana del punto = {codigo}")
        _estrato_por_manzana(str(codigo))
    else:
        print("[capa 320] sin codigo de manzana en la respuesta")


def _estrato_por_manzana(codigo: str):
    print(f"\n=== 4. ESTRATO POR CODIGO DE MANZANA {codigo!r} ===")
    for etq, where in (
        (f"estratificacion codigo_manzana={codigo!r}", f"codigo_manzana='{codigo}'"),
        (f"estratificacion codigo_manzana LIKE %{codigo}%", f"codigo_manzana LIKE '%{codigo}%'"),
    ):
        d = _get(f"{BASE_ORD}/estratificacion/MapServer/1/query",
                 {"where": where, "outFields": "*", "returnGeometry": "false", "f": "json"}, etq)
        t = TRACE[-1]
        print(f"[{etq}] http={t.get('http')} n={t.get('n_features')} err={t.get('error')}")
        feats = (d or {}).get("features") or []
        if feats:
            print("   ESTRATO:", (feats[0].get("attributes") or {}).get("estratificacion"),
                  "| barrio:", (feats[0].get("attributes") or {}).get("nombre_barrio"))


def step_predio():
    print("\n=== 5. PREDIO / DIRECCION OFICIAL (catastro datosabiertos 500 y 105) ===")
    d = _get(f"{BASE_CAT}/datosabiertos/MapServer/500/query",
             {"where": f"numero_predial='{NUMERO_PREDIAL}' OR codigo_homologado='{NUPRE}' OR nupre='{NUPRE}'",
              "outFields": "*", "returnGeometry": "false", "f": "json"},
             "capa 500 Predio por numero_predial/NUPRE")
    t = TRACE[-1]
    print(f"[capa 500] http={t.get('http')} n={t.get('n_features')} err={t.get('error')} "
          f"campos={t.get('campos')}")
    d2 = _get(f"{BASE_CAT}/datosabiertos/MapServer/105/query",
              {"where": "1=1", "outFields": "*", "returnGeometry": "false",
               "geometry": json.dumps({"x": LON, "y": LAT, "spatialReference": {"wkid": 4326}}),
               "geometryType": "esriGeometryPoint", "inSR": "4326",
               "spatialRel": "esriSpatialRelIntersects", "f": "json"},
              "capa 105 Direccion punto")
    t2 = TRACE[-1]
    print(f"[capa 105 Direccion] http={t2.get('http')} n={t2.get('n_features')} "
          f"err={t2.get('error')} campos={t2.get('campos')}")
    if (t2.get("n_features") or 0) > 0:
        print("   sample:", t2.get("sample"))
        at = d2["features"][0].get("attributes") or {}
        for k in ("codigo_manzana", "manzana", "estrato", "numero_predial", "direccion"):
            for kk, vv in at.items():
                if kk.lower() == k:
                    print(f"   {kk} = {vv!r}")


def main() -> int:
    print(f"caso: folio 040-646406 · predial {NUMERO_PREDIAL} · NUPRE {NUPRE}")
    print(f"punto autorizado: {LAT}, {LON} (OFFICIAL_ADOPTION_ADDRESS_GEOCODE)")
    step_meta()
    step_punto()
    step_barrio()
    step_manzana()
    step_predio()
    out = ROOT / "docs" / "forensics" / "040-646406" / "golden_03i1"
    out.mkdir(parents=True, exist_ok=True)
    (out / "ESTRATO_PROBE_TRACE.json").write_text(
        json.dumps(TRACE, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\ntrace: {out / 'ESTRATO_PROBE_TRACE.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

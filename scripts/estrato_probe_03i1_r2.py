# -*- coding: utf-8 -*-
"""03I.1 — Sonda de ESTRATO, ronda 2: catálogo completo + consulta por MANZANA.

El punto geocodificado NO cae dentro de ninguna manzana del barrio Miramar
(0 features en la consulta exacta), así que la vía espacial no puede atribuir
estrato: hay que resolver la MANZANA del predio por IDENTIFICADOR y consultarla
por atributo (sin ambigüedad espacial).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "ARHIAX-RE/1.0 (Sinergia Consulting Group)"}
TIMEOUT = 15.0

SVC_ORD = "https://miciudad.barranquilla.gov.co/gis/rest/services/ordenamiento"
SVC_CAT = "https://miciudad.barranquilla.gov.co/gis/rest/services/catastro"
NUMERO_PREDIAL = "080010103000010040001908040002"

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
            item["attrs"] = [f.get("attributes") for f in feats[:12]]
        else:
            item["keys"] = list(data.keys())[:20]
        TRACE.append(item)
        return data
    except Exception as e:  # noqa: BLE001
        item["error"] = f"{type(e).__name__}: {e}"
        TRACE.append(item)
        return {}


def catalogo():
    print("=== A. CATALOGO DE SERVICIOS ===")
    d = get(f"{SVC_ORD}", {"f": "json"}, "ordenamiento (root)")
    print("ordenamiento root:", {k: d.get(k) for k in ("folders", "services")})
    d2 = get(f"{SVC_ORD}/estratificacion/MapServer", {"f": "json"}, "estratificacion MapServer")
    print("capas de estratificacion:")
    for l in (d2.get("layers") or []):
        print(f"   {l.get('id')}: {l.get('name')}")
    d3 = get(f"{SVC_CAT}", {"f": "json"}, "catastro (root)")
    print("catastro root:", {k: d3.get(k) for k in ("folders", "services")})


def manzanas_prefijo():
    print("\n=== B. MANZANAS CON PREFIJO DEL PREDIAL (08001010300001) ===")
    d = get(f"{SVC_ORD}/estratificacion/MapServer/1/query",
            {"where": "codigo_manzana LIKE '08001010300001%'", "outFields": "*",
             "returnGeometry": "false", "f": "json"}, "manzanas prefijo 08001010300001")
    feats = (d or {}).get("features") or []
    print(f"manzanas con ese prefijo: {len(feats)}")
    for f in feats[:20]:
        at = f.get("attributes") or {}
        print(f"   {at.get('codigo_manzana')} estrato={at.get('estratificacion')!r} "
              f"barrio={at.get('nombre_barrio')!r}")


def manzanas_prefijo_largo():
    print("\n=== C. MANZANAS CON PREFIJO LARGO (0800101030000100) ===")
    d = get(f"{SVC_ORD}/estratificacion/MapServer/1/query",
            {"where": "codigo_manzana LIKE '0800101030000100%'", "outFields": "*",
             "returnGeometry": "false", "f": "json"}, "manzanas prefijo 0800101030000100")
    for f in ((d or {}).get("features") or []):
        at = f.get("attributes") or {}
        print(f"   {at.get('codigo_manzana')} estrato={at.get('estratificacion')!r} "
              f"barrio={at.get('nombre_barrio')!r}")
    print(f"total: {len((d or {}).get('features') or [])}")


def candidatos_exactos():
    print("\n=== D. CANDIDATOS DERIVADOS DEL NUMERO PREDIAL ===")
    cands = [
        "08001010300001004", "08001010300001006", "0800101030000104",
        "0800101030000100004", "0800101030000100400",
    ]
    for c in cands:
        d = get(f"{SVC_ORD}/estratificacion/MapServer/1/query",
                {"where": f"codigo_manzana='{c}'", "outFields": "*",
                 "returnGeometry": "false", "f": "json"}, f"codigo_manzana={c}")
        feats = (d or {}).get("features") or []
        if feats:
            at = feats[0].get("attributes") or {}
            print(f"   {c} -> estrato={at.get('estratificacion')!r} barrio={at.get('nombre_barrio')!r} "
                  f"manzana={at.get('codigo_manzana')!r}")
        else:
            print(f"   {c} -> sin coincidencia")


def miramar_valores():
    print("\n=== E. VALORES DE ESTRATO EN EL BARRIO MIRAMAR (contexto, NO atribucion) ===")
    d = get(f"{SVC_ORD}/estratificacion/MapServer/1/query",
            {"where": "UPPER(nombre_barrio)='MIRAMAR'", "outFields": "*",
             "returnGeometry": "false", "f": "json"}, "Miramar manzanas")
    feats = (d or {}).get("features") or []
    from collections import Counter
    c = Counter((f.get("attributes") or {}).get("estratificacion") for f in feats)
    print(f"manzanas de Miramar: {len(feats)} · distribución de estrato: {dict(c)}")


def otras_fuentes():
    print("\n=== F. OTRAS FUENTES OFICIALES ===")
    d = get("https://www.datos.gov.co/api/views.json",
            {"q": "estratificacion Barranquilla", "limit": 5},
            "datos.gov.co busqueda 'estratificacion Barranquilla'")
    for v in (d if isinstance(d, list) else [])[:5]:
        print(f"   [{v.get('id')}] {v.get('name')} — {v.get('attribution')}")


def main() -> int:
    catalogo()
    manzanas_prefijo()
    manzanas_prefijo_largo()
    candidatos_exactos()
    miramar_valores()
    otras_fuentes()
    out = ROOT / "docs" / "forensics" / "040-646406" / "golden_03i1"
    out.mkdir(parents=True, exist_ok=True)
    (out / "ESTRATO_PROBE_TRACE_2.json").write_text(
        json.dumps(TRACE, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\ntrace: {out / 'ESTRATO_PROBE_TRACE_2.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

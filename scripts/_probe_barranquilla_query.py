# -*- coding: utf-8 -*-
"""Consulta espacial de las capas del observatorio en el punto del sujeto. Solo lectura."""
from __future__ import annotations

import json
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _probe_barranquilla_crawl import BASE, get, jget, OUT  # noqa: E402

LAT, LON = 11.006055954316363, -74.8375696549899
MANZANA = "08001010300001004"

CONSULTAS = [
    ("valoresm2_area", 1, "Rango valores por m2. Area (36-60m2)."),
    ("valorsuelourbano", 5, "Suelo urbano vigencia 2026"),
    ("valorcompraventas", 7, "Valor compraventas 2025"),
    ("arrendamientos", 1, "Arrendamientos 2024"),
    ("avaluocatastral", 1, "Avaluo catastral 2026"),
    ("cantidadtransacciones", 8, "Transacciones por manzana 2026"),
]


def qurl(servicio: str, lid: int, **params) -> str:
    base = f"{BASE}/observatorio/{servicio}/MapServer/{lid}/query"
    p = {"f": "json", "outFields": "*", "returnGeometry": "false"}
    p.update({k: v for k, v in params.items() if v is not None})
    return base + "?" + urllib.parse.urlencode(p)


def main() -> int:
    salida = {}
    punto = f"{LON},{LAT}"

    for servicio, lid, etiqueta in CONSULTAS:
        print("=" * 78)
        print(f"### {servicio}/{lid} — {etiqueta}")

        # 1 · conteo total de la capa
        rc, rrc = jget(qurl(servicio, lid, where="1=1", returnCountOnly="true"))
        print(f"  COUNT total = {rc.get('count')} [{rrc['http_status']}]")
        salida[f"{servicio}/{lid}"] = {
            "etiqueta": etiqueta,
            "count_url": qurl(servicio, lid, where="1=1", returnCountOnly="true"),
            "count": rc.get("count"), "count_status": rrc["http_status"],
            "count_sha256": rrc["sha256"],
        }

        # 2 · consulta espacial en el punto del sujeto (WGS84 → capa)
        u = qurl(servicio, lid, geometry=punto, geometryType="esriGeometryPoint",
                 inSR="4326", spatialRel="esriSpatialRelIntersects")
        d, r = jget(u)
        print(f"  PUNTO [{r['http_status']}] bytes={r['bytes']} sha={str(r['sha256'])[:12]}")
        if "error" in d:
            print(f"    ERROR = {json.dumps(d['error'], ensure_ascii=False)[:300]}")
        feats = d.get("features") or []
        print(f"    features = {len(feats)}")
        for f in feats[:12]:
            print("      ", json.dumps(f.get("attributes"), ensure_ascii=False))
        salida[f"{servicio}/{lid}"]["query_url_punto"] = u
        salida[f"{servicio}/{lid}"]["query_status_punto"] = r["http_status"]
        salida[f"{servicio}/{lid}"]["query_sha256_punto"] = r["sha256"]
        salida[f"{servicio}/{lid}"]["query_bytes_punto"] = r["bytes"]
        salida[f"{servicio}/{lid}"]["features_punto"] = feats
        salida[f"{servicio}/{lid}"]["raw_punto"] = d
        (OUT / f"raw_{servicio}_{lid}_punto.json").write_bytes(r["body"])

        # 3 · consulta por codigo de manzana cuando la capa lo tiene
        nombres = {f2.get("name") for f2 in
                   ((json.loads((OUT / "campos_capas.json").read_text(encoding="utf-8"))
                     .get(f"{servicio}/{lid}", {}).get("meta") or {}).get("fields") or [])}
        campo_mz = None
        for cand in ("codigo_manzana", "identificador_barrio", "nombre_barrio"):
            if cand in nombres:
                campo_mz = cand
                break
        if campo_mz:
            where = f"{campo_mz} = '{MANZANA}'" if campo_mz == "codigo_manzana" \
                else f"{campo_mz} = 'Miramar'"
            u2 = qurl(servicio, lid, where=where)
            d2, r2 = jget(u2)
            feats2 = d2.get("features") or []
            print(f"  WHERE {where} [{r2['http_status']}] features={len(feats2)} "
                  f"sha={str(r2['sha256'])[:12]}")
            for f in feats2[:6]:
                print("      ", json.dumps(f.get("attributes"), ensure_ascii=False))
            salida[f"{servicio}/{lid}"]["query_url_where"] = u2
            salida[f"{servicio}/{lid}"]["query_status_where"] = r2["http_status"]
            salida[f"{servicio}/{lid}"]["query_sha256_where"] = r2["sha256"]
            salida[f"{servicio}/{lid}"]["features_where"] = feats2
            (OUT / f"raw_{servicio}_{lid}_where.json").write_bytes(r2["body"])

    (OUT / "consultas_resultado.json").write_text(
        json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""Texto completo de metodologia (serviceDescription) + universos completos. Solo lectura."""
from __future__ import annotations

import html
import json
import re
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _probe_barranquilla_crawl import BASE, jget, OUT  # noqa: E402

LAT, LON = 11.006055954316363, -74.8375696549899


def texto_plano(bruto: str) -> str:
    t = re.sub(r"<[^>]+>", " ", bruto or "")
    t = html.unescape(t)
    return re.sub(r"\s+", " ", t).strip()


def qurl(servicio: str, lid: int, **params) -> str:
    base = f"{BASE}/observatorio/{servicio}/MapServer/{lid}/query"
    p = {"f": "json", "outFields": "*", "returnGeometry": "false"}
    p.update({k: v for k, v in params.items() if v is not None})
    return base + "?" + urllib.parse.urlencode(p)


def main() -> int:
    salida = {}
    for servicio in ("valoresm2_area", "valorsuelourbano", "valorcompraventas",
                     "arrendamientos", "avaluocatastral", "cantidadtransacciones"):
        meta, r = jget(f"{BASE}/observatorio/{servicio}/MapServer?f=json")
        sd = texto_plano(meta.get("serviceDescription") or "")
        print("=" * 78)
        print(f"### {servicio} [{r['http_status']}] sha={str(r['sha256'])[:12]}")
        print(f"  DESCRIPTION: {texto_plano(meta.get('description') or '')}")
        print(f"  SERVICE_DESCRIPTION: {sd}")
        salida[servicio] = {"url": f"{BASE}/observatorio/{servicio}/MapServer?f=json",
                            "http_status": r["http_status"], "bytes": r["bytes"],
                            "sha256": r["sha256"],
                            "description_plano": texto_plano(meta.get("description") or ""),
                            "serviceDescription_plano": sd}

    # universo completo de la banda 36-60 m2 (las 5 zonas)
    print("=" * 78)
    print("### valoresm2_area/1 · universo completo (las 5 zonas de la banda 36-60)")
    u = qurl("valoresm2_area", 1, where="1=1")
    d, r = jget(u)
    for f in d.get("features") or []:
        print("   ", json.dumps(f.get("attributes"), ensure_ascii=False))
    salida["valoresm2_area_1_universo"] = {"url": u, "http_status": r["http_status"],
                                           "bytes": r["bytes"], "sha256": r["sha256"],
                                           "features": d.get("features")}
    (OUT / "raw_valoresm2_area_1_universo.json").write_bytes(r["body"])

    # valorcompraventas: hay dato cerca del sujeto? (buffer 300 m)
    print("=" * 78)
    print("### valorcompraventas/7 · buffer 300 m alrededor del sujeto")
    u2 = qurl("valorcompraventas", 7, geometry=f"{LON},{LAT}",
              geometryType="esriGeometryPoint", inSR="4326",
              spatialRel="esriSpatialRelIntersects",
              distance="300", units="esriSRUnit_Meter")
    d2, r2 = jget(u2)
    feats = d2.get("features") or []
    print(f"  [{r2['http_status']}] features={len(feats)} sha={str(r2['sha256'])[:12]}")
    for f in feats[:10]:
        print("   ", json.dumps(f.get("attributes"), ensure_ascii=False))
    salida["valorcompraventas_7_buffer300"] = {"url": u2, "http_status": r2["http_status"],
                                              "bytes": r2["bytes"], "sha256": r2["sha256"],
                                              "features": feats}
    (OUT / "raw_valorcompraventas_7_buffer300.json").write_bytes(r2["body"])

    (OUT / "metodologia_capas.json").write_text(
        json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())

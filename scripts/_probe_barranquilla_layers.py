# -*- coding: utf-8 -*-
"""Metadata de capas de los MapServer del observatorio. Solo lectura."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _probe_barranquilla_crawl import BASE, jget, OUT  # noqa: E402

CAPAS = ["valoresm2_area", "valorsuelourbano", "valorcompraventas",
         "arrendamientos", "avaluocatastral", "cantidadtransacciones"]


def main() -> int:
    salida = {}
    for capa in CAPAS:
        url = f"{BASE}/observatorio/{capa}/MapServer?f=json"
        meta, r = jget(url)
        print("=" * 78)
        print(f"{capa}  [{r['http_status']}] {r['bytes']} B sha={str(r['sha256'])[:12]} "
              f"cf={r['cf_ray']}")
        if not meta:
            print(f"  SIN JSON · err={r['error']} · body={r['body'][:200]!r}")
            salida[capa] = {"http_status": r["http_status"], "bytes": r["bytes"],
                            "sha256": r["sha256"], "error": r["error"], "meta": None}
            continue
        salida[capa] = {"http_status": r["http_status"], "bytes": r["bytes"],
                        "sha256": r["sha256"], "url": url, "meta": meta}
        print(f"  serviceDescription = {str(meta.get('serviceDescription'))[:200]!r}")
        print(f"  description        = {str(meta.get('description'))[:200]!r}")
        print(f"  copyrightText      = {str(meta.get('copyrightText'))[:200]!r}")
        print(f"  spatialReference   = {meta.get('spatialReference')}")
        for l in meta.get("layers") or []:
            print(f"  · LAYER {l.get('id')} | {l.get('name')!r} | "
                  f"geom={l.get('geometryType')} | minScale={l.get('minScale')}")
        for t in meta.get("tables") or []:
            print(f"  · TABLE {t.get('id')} | {t.get('name')!r}")
    (OUT / "metadata_capas.json").write_text(
        json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""Campos de las capas objetivo + consulta de la banda del sujeto. Solo lectura."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _probe_barranquilla_crawl import BASE, jget, OUT  # noqa: E402

# (servicio, layer_id, etiqueta humana de la capa)
OBJETIVO = [
    ("valoresm2_area", 1, "Rango valores por m2. Area (36-60m2)."),
    ("valorsuelourbano", 5, "Valor del metro cuadrado del suelo urbano. Vigencia 2026."),
    ("valorcompraventas", 7, "Valor compraventas 2025"),
    ("arrendamientos", 1, "Valor arrendamientos. Ano 2024."),
    ("avaluocatastral", 1, "Avaluo catastral por destino economico. Vigencia 2026."),
    ("cantidadtransacciones", 8, "Cantidad de transacciones por manzana. Ano 2026."),
]


def main() -> int:
    salida = {}
    for servicio, lid, etiqueta in OBJETIVO:
        url = f"{BASE}/observatorio/{servicio}/MapServer/{lid}?f=json"
        meta, r = jget(url)
        print("=" * 78)
        print(f"{servicio}/{lid}  [{r['http_status']}] {r['bytes']} B "
              f"sha={str(r['sha256'])[:12]}")
        if not meta:
            print(f"  SIN JSON err={r['error']}")
            continue
        print(f"  name={meta.get('name')!r}")
        print(f"  description={str(meta.get('description'))[:400]!r}")
        print(f"  geom={meta.get('geometryType')} oid={meta.get('objectIdField')} "
              f"maxRecordCount={meta.get('maxRecordCount')}")
        print(f"  extent={meta.get('extent')}")
        campos = meta.get("fields") or []
        for f in campos:
            print(f"    - {f.get('name'):32s} {f.get('type'):20s} "
                  f"alias={str(f.get('alias'))[:60]!r}")
        # valores unicos del campo con pinta de barrio
        salida[f"{servicio}/{lid}"] = {"url": url, "http_status": r["http_status"],
                                       "bytes": r["bytes"], "sha256": r["sha256"],
                                       "etiqueta": etiqueta, "meta": meta}
    (OUT / "campos_capas.json").write_text(
        json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())

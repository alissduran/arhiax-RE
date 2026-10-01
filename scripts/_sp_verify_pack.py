# -*- coding: utf-8 -*-
"""Verificación final del pack congelado (solo lectura)."""
from __future__ import annotations

import collections
import csv
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PACK = RAIZ / "docs" / "source_pack"


def main() -> int:
    reg = json.loads((PACK / "barranquilla_sources_v1.json").read_text(encoding="utf-8"))
    man = json.loads((PACK / "BARRANQUILLA_SOURCE_PACK_MANIFEST.json").read_text(encoding="utf-8"))
    fuentes = reg["sources"]
    print("== REGISTRO ==")
    print("fuentes:", len(fuentes), "| habilitadas:",
          sum(1 for f in fuentes.values() if f["enabled"] is not False))
    print("por authority_class:", dict(collections.Counter(f["authority_class"]
                                                           for f in fuentes.values())))
    print("por precedence:", dict(collections.Counter(f["precedence"] for f in fuentes.values())))
    print("con evidencia adjunta:", sum(1 for f in fuentes.values() if f.get("evidence")))
    for sid, f in sorted(fuentes.items()):
        ev = f.get("evidence") or {}
        if ev:
            print(f"   {sid}: {ev.get('origin')} <- {Path(ev.get('capture_file', '')).name}")
    print("\n== FUENTES (id | layer_id | spec | authority | precedence | enabled) ==")
    for sid, f in sorted(fuentes.items()):
        print(f"   {sid:<32} {str(f['layer_id']):>5} | {str(f['spec_layer_id']):>5} | "
              f"{f['authority_class']:<24} {f['precedence']:<21} {f['enabled']}")
    print("\n== MANIFEST ==")
    for k in ("pack_version", "registry_version", "tested_at"):
        print(f"   {k}: {man.get(k)}")
    print("   secciones:", sorted(man.keys()))
    print("   approved_sources:", len(man["approved_sources"]),
          "| disabled_sources:", len(man["disabled_sources"]))
    print("   hashes por fuente:", len(man["source_metadata_hashes"]))
    print("\n== MATRIZ ==")
    filas = list(csv.DictReader((PACK / "SOURCE_COVERAGE_MATRIX_040-646406.csv")
                                .open(encoding="utf-8")))
    print("   filas:", len(filas), "| columnas:", list(filas[0].keys()))
    print("   estados:", dict(collections.Counter(f["status"] for f in filas)))
    for f in filas:
        print(f"   {f['row']:<22} {f['source']:<36} {f['status']}")
    print("\n== PRUEBAS DOCUMENTADAS EN EL REPORTE ==")
    rep = (PACK / "acceptance_report.md").read_text(encoding="utf-8")
    for aguja in ("61 passed", "10 passed, 1 xfailed", "49 passed", "18 filas × 7 columnas"):
        print(f"   contiene {aguja!r}: {aguja in rep}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

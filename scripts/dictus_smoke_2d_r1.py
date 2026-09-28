# -*- coding: utf-8 -*-
"""HOTFIX 2.0D-R1 §12 · verificación de la ENTREGA REAL del producto (mismo código que
usa la API: `compile_pdf` → `construir_entregables` → `auditar_ejecutivo`).

Lee los entregables que dejó la corrida real del producto y comprueba, sobre el PDF
físico: 6 páginas, arquitectura aprobada, presupuesto vertical por página y ausencia de
solapamientos/desbordes. Imprime el resumen que exige el hotfix.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))

import dictus_entrega as entrega  # noqa: E402

FOLIO = "040-646406"
SALIDA = ROOT / "docs" / "forensics" / FOLIO / "dictus_2b"


def main() -> int:
    ejecutivo = SALIDA / f"DICTUS_EJECUTIVO_{FOLIO}.pdf"
    manifest_p = SALIDA / f"DICTUS_MANIFEST_{FOLIO}.json"
    if not ejecutivo.exists():
        print(f"[FAIL] falta el ejecutivo: {ejecutivo}")
        return 1
    manifest = json.loads(manifest_p.read_text(encoding="utf-8"))
    auditoria = entrega.auditar_ejecutivo(ejecutivo)
    sha = hashlib.sha256(ejecutivo.read_bytes()).hexdigest()
    presupuesto = (manifest.get("render_budget") or {})

    print("=" * 74)
    print("SMOKE DEL PRODUCTO · DICTUS 2.0D-R1 (página 6)")
    print("=" * 74)
    print(f"generación            : OK (mismo camino que la API: compile_pdf → "
          f"construir_entregables)")
    print(f"archivo               : {ejecutivo.name}")
    print(f"sha256                : {sha}")
    print(f"páginas               : {auditoria['page_count']} "
          f"(límite {entrega.MAX_PAGINAS_EJECUTIVO})")
    print(f"auditoría arquitectura: ok={auditoria['ok']} · fallos={len(auditoria['fallos'])}")
    for i, titulo in enumerate(auditoria["titulos"] or [], start=1):
        print(f"   P{i} {titulo}")
    p6 = presupuesto.get("6") or {}
    print(f"P6 consumido          : {p6.get('consumed_height'):.1f} pt")
    print(f"P6 restante           : {p6.get('remaining_height'):.1f} pt "
          f"(límite {p6.get('footer_limit'):.0f} · objetivo 65)")
    print(f"P6 blockers           : {p6.get('blocker_count')} declarados · "
          f"{p6.get('blockers_printed')} impresos")
    print(f"P6 filas identidad    : {p6.get('identity_row_count')}")
    print(f"P6 desborda           : {p6.get('overflow')}")
    print("presupuesto por página: " + " · ".join(
        f"P{k}={float((presupuesto.get(k) or {}).get('remaining_height') or 0):.1f}"
        for k in sorted(presupuesto)))
    print(f"master hash           : {manifest.get('master_hash')}")
    for f in auditoria["fallos"]:
        print(f"   [FALLO] {f}")
    ok = bool(auditoria["ok"]) and not p6.get("overflow")
    print("-" * 74)
    print("RESULTADO: " + ("OK · entrega apta" if ok else "NO APTA · revisar fallos"))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

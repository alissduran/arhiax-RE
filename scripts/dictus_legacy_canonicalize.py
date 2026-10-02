# -*- coding: utf-8 -*-
"""BLOCK 1.1 · C — canonicalización del juego de artefactos del folio 040-646406.

Mueve a `legacy/` los artefactos de corridas ANTERIORES preservando bytes
(sha256_before == sha256_after) y deja en la raíz solo lo de la corrida vigente.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASE = ROOT / "docs" / "forensics" / "040-646406" / "dictus_2b"
LEGACY = BASE / "legacy"

# (origen relativo, destino relativo, run_id, generated_at, motivo)
MOVIMIENTOS = [
    ("DICTUS_2.0B_TEXTO_EJECUTIVO_040-646406.txt",
     "DICTUS_2.0B_TEXTO_EJECUTIVO_040-646406.txt",
     "DX-040-646406-20260925", "2026-09-25",
     "Texto del ejecutivo de la corrida 2.0B (DICTUS ID DX-040-646406-20260925). "
     "La corrida vigente es DX-040-646406-20261002."),
    ("ENTREGA_2.0B_R1.md", "ENTREGA_2.0B_R1.md",
     "DX-040-646406-20260925", "2026-09-25",
     "Entregable documental de la fase 2.0B-R1: describe una arquitectura y un juego "
     "de artefactos anteriores a la corrida vigente."),
    ("paginas", "paginas_2.0B_20260925",
     "DX-040-646406-20260925", "2026-09-25",
     "Páginas rasterizadas del ejecutivo 2.0B (6 PNG, 25/09/2026). No corresponden a "
     "la corrida vigente; se regeneran con scripts/dictus_render_ejecutivo.py."),
]


def sha256(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def hashes_de(ruta: Path) -> dict:
    if ruta.is_dir():
        return {str(p.relative_to(ruta)).replace("\\", "/"): sha256(p)
                for p in sorted(ruta.rglob("*")) if p.is_file()}
    return {"": sha256(ruta)}


def main() -> int:
    LEGACY.mkdir(parents=True, exist_ok=True)
    movidos = []
    fallos = []
    for origen_rel, destino_rel, run_id, gen, motivo in MOVIMIENTOS:
        origen = BASE / origen_rel
        destino = LEGACY / destino_rel
        if not origen.exists():
            print(f"[c] AUSENTE (ya canonicalizado?): {origen_rel}")
            continue
        antes = hashes_de(origen)
        destino.parent.mkdir(parents=True, exist_ok=True)
        if destino.exists():
            print(f"[c] FAIL: el destino ya existe: {destino}")
            return 1
        shutil.move(str(origen), str(destino))
        despues = hashes_de(destino)
        identico = antes == despues
        if not identico:
            fallos.append(origen_rel)
        movidos.append({
            "path": f"docs/forensics/040-646406/dictus_2b/legacy/{destino_rel}",
            "original_path": f"docs/forensics/040-646406/dictus_2b/{origen_rel}",
            "run_id": run_id,
            "generated_at": gen,
            "status": "HISTORICAL_ONLY",
            "motivo": motivo,
            "sha256_before": {k: v for k, v in antes.items()},
            "sha256_after": {k: v for k, v in despues.items()},
            "sha256_preservado": identico,
        })
        print(f"[c] MOVIDO {origen_rel} -> legacy/{destino_rel} | "
              f"sha256_before==after: {identico} | "
              f"{next(iter(antes.values()))[:16]}...")

    registro = {
        "folio": "040-646406",
        "convencion": ("la raíz de dictus_2b/ contiene SOLO los artefactos de la corrida "
                       "vigente; los de corridas anteriores viven en legacy/ sin "
                       "reescribirse (bytes preservados)"),
        "legacy_artifacts": movidos,
        "sha256_preservados_todos": all(m["sha256_preservado"] for m in movidos),
    }
    (LEGACY / "LEGACY_ARTIFACTS.json").write_text(
        json.dumps(registro, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[c] legacy/LEGACY_ARTIFACTS.json · {len(movidos)} artefacto(s) · "
          f"todos preservados: {registro['sha256_preservados_todos']}")
    if fallos:
        print(f"[c] FAIL: bytes alterados en {fallos}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

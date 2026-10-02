# -*- coding: utf-8 -*-
"""BLOCK 1.1 · C — ÍNDICE CANÓNICO DE ARTEFACTOS del folio 040-646406.

    python scripts/dictus_artifact_index.py

Escribe `docs/forensics/040-646406/dictus_2b/ARTIFACT_INDEX_040-646406.json`.

Para qué sirve: `dictus_2b/` acumuló ejecutivos de corridas distintas (un PDF de la
corrida vigente y un TXT de la corrida 2.0B anterior). Un revisor tenía que abrir los
artefactos para saber cuál era el Dictus VIGENTE. Este índice lo declara SIN
AMBIGÜEDAD: la corrida canónica (con su `run_id` y `generated_at`), los artefactos
canónicos con su huella, y los históricos con `status: HISTORICAL_ONLY`.

NO reescribe ningún artefacto: solo los mide (sha256) y los clasifica.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FOLIO = "040-646406"
BASE = ROOT / "docs" / "forensics" / FOLIO / "dictus_2b"
LEGACY = BASE / "legacy"
INDICE = BASE / f"ARTIFACT_INDEX_{FOLIO}.json"

# Artefactos CANÓNICOS de la corrida vigente, con su rol contractual. El orden es el
# contrato del índice (el revisor los lee en este orden).
CANONICOS = {
    "executive_pdf": f"DICTUS_EJECUTIVO_{FOLIO}.pdf",
    "technical_pdf": f"DICTUS_TECNICO_{FOLIO}.pdf",
    "run_state": f"DICTUS_RUN_STATE_{FOLIO}.json",
    "manifest": f"DICTUS_MANIFEST_{FOLIO}.json",
    "acceptance_pack": f"ACEPTACION_{FOLIO}.json",
}
# Artefactos canónicos AUXILIARES (declarados por el RunState como SAME_RUN).
AUXILIARES = (
    f"ACEPTACION_{FOLIO}.md",
    f"DICTUS_2.0C_TEXTO_EJECUTIVO_{FOLIO}.txt",
    "poi_map.png",
    "poi_map.html",
    "sombra_9am.png",
    "sombra_3pm.png",
)


def sha256(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def ficha(ruta: Path) -> dict:
    return {
        "path": f"docs/forensics/{FOLIO}/dictus_2b/{ruta.name}",
        "bytes": ruta.stat().st_size,
        "sha256": sha256(ruta),
    }


def main() -> int:
    rs_path = BASE / CANONICOS["run_state"]
    mf_path = BASE / CANONICOS["manifest"]
    for obligatorio in (rs_path, mf_path):
        if not obligatorio.exists():
            print(f"[index] FAIL: falta {obligatorio}")
            return 1
    rs = json.loads(rs_path.read_text(encoding="utf-8"))
    mf = json.loads(mf_path.read_text(encoding="utf-8"))

    resumen = rs.get("historical_consistency_summary") or {}
    artefactos = {}
    for rol, nombre in CANONICOS.items():
        ruta = BASE / nombre
        artefactos[rol] = ficha(ruta) if ruta.exists() else {
            "path": f"docs/forensics/{FOLIO}/dictus_2b/{nombre}",
            "bytes": None, "sha256": None, "status": "AUSENTE"}

    legacy = []
    reg_legacy = LEGACY / "LEGACY_ARTIFACTS.json"
    if reg_legacy.exists():
        legacy = json.loads(reg_legacy.read_text(encoding="utf-8")).get(
            "legacy_artifacts") or []

    indice = {
        "indice_version": "dictus-artifact-index/1.0.0",
        "folio": FOLIO,
        "convencion": ("la raíz de dictus_2b/ contiene SOLO los artefactos de la corrida "
                       "canónica; los de corridas anteriores viven en legacy/ con "
                       "status HISTORICAL_ONLY y sus bytes preservados"),
        # ── la corrida VIGENTE, declarada sin ambigüedad ─────────────────────────
        "canonical_run_id": rs.get("run_id"),
        "canonical_generated_at": rs.get("generated_at"),
        "canonical_dictus_id": mf.get("dictus_id"),
        "canonical_master_hash": mf.get("master_hash"),
        "canonical_run_state_version": mf.get("run_state_version"),
        "canonical_true_conflict_count": resumen.get("true_conflict_count"),
        "canonical_true_conflict_attributes": list(resumen.get("true_conflicts") or []),
        # ── artefactos canónicos ─────────────────────────────────────────────────
        **artefactos,
        "auxiliares": [ficha(BASE / n) for n in AUXILIARES if (BASE / n).exists()],
        # ── histórico: NO es el Dictus vigente ───────────────────────────────────
        "legacy_artifacts": [
            {"path": m["path"], "original_path": m["original_path"],
             "run_id": m["run_id"], "generated_at": m["generated_at"],
             "status": m["status"], "sha256_before": m["sha256_before"],
             "sha256_after": m["sha256_after"],
             "sha256_preservado": m["sha256_preservado"], "motivo": m["motivo"]}
            for m in legacy],
    }
    INDICE.write_text(json.dumps(indice, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[index] {INDICE.relative_to(ROOT)}")
    print(f"[index] canonical_run_id = {indice['canonical_run_id']}")
    print(f"[index] canonical_generated_at = {indice['canonical_generated_at']}")
    print(f"[index] true_conflict_count = {indice['canonical_true_conflict_count']} · "
          f"{indice['canonical_true_conflict_attributes']}")
    print(f"[index] legacy_artifacts = {len(indice['legacy_artifacts'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

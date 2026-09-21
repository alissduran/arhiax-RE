# -*- coding: utf-8 -*-
"""03S.1 / 03S.1A — Aceptación EN VIVO de las fuentes de screening (UN / OFAC / UKSL).

Registra por fuente: estado de adquisición, fecha efectiva declarada por la
propia fuente, número de registros, SHA-256 y versión del parser. Si no hay red,
informa `LIVE_SOURCES_NOT_VERIFIED` y NO simula éxito (§40).

Con `--dos-fases` ejecuta la prueba de integridad de frescura (§ 03S.1A-8):

  1. `force_refresh=True`  -> debe registrar LIVE_FRESH (hubo descarga real);
  2. corrida inmediata `force_refresh=False` -> debe registrar CACHED_FRESH
     (el snapshot se leyó del store y NO puede reclamar "en vivo").

Uso:
    python scripts/screening_live_check.py [--cache-dir RUTA] [--json]
                                           [--dos-fases] [--sujetos RUTA_JSON]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "api"))

from sanctions.acquire import adquirir_fuente, es_cache, es_en_vivo  # noqa: E402
from sanctions.registry import CORE_SOURCE_IDS, get_source  # noqa: E402
from sanctions.snapshots import SnapshotStore  # noqa: E402


def _registro(sid, snap):
    d = get_source(sid)
    return {
        "source_id": sid, "authority": d.authority,
        "official_url": snap.source_url,
        "acquisition_status": snap.acquisition_status,
        "freshness": snap.freshness,
        "en_vivo": es_en_vivo(snap), "desde_snapshot": es_cache(snap),
        "effective_date": snap.effective_date,
        "record_count": snap.record_count,
        "sha256": snap.sha256,
        "parser": d.parser, "parser_version": snap.parser_version,
        "retrieved_at": snap.retrieved_at, "error": snap.error,
    }


def _imprimir(e, silencioso=False):
    if silencioso:
        return
    print(f"[{e['source_id']}] {e['acquisition_status']} · {e['freshness']} · "
          f"registros={e['record_count']} · efectiva={e['effective_date']} · "
          f"sha256={e['sha256'][:16]} · parser={e['parser_version']}")
    if e["error"]:
        print(f"    error: {e['error']}")


def dos_fases(store, timeout, json_out=False):
    """Prueba obligatoria: LIVE_FRESH en la descarga, CACHED_FRESH al releer."""
    res = {"fase_1_force_refresh": {}, "fase_2_sin_refresh": {}, "ok": True}
    for sid in CORE_SOURCE_IDS:
        snap, _ = adquirir_fuente(sid, store=store, timeout=timeout,
                                  force_refresh=True)
        res["fase_1_force_refresh"][sid] = _registro(sid, snap)
        _imprimir({**res["fase_1_force_refresh"][sid],
                   "source_id": sid}, silencioso=json_out)
    for sid in CORE_SOURCE_IDS:
        snap, _ = adquirir_fuente(sid, store=store, timeout=timeout,
                                  force_refresh=False)
        res["fase_2_sin_refresh"][sid] = _registro(sid, snap)
        _imprimir({**res["fase_2_sin_refresh"][sid],
                   "source_id": sid}, silencioso=json_out)
    for sid in CORE_SOURCE_IDS:
        a = res["fase_1_force_refresh"][sid]["freshness"]
        b = res["fase_2_sin_refresh"][sid]["freshness"]
        if a != "LIVE_FRESH" or b != "CACHED_FRESH":
            res["ok"] = False
        res.setdefault("comparacion", {})[sid] = {
            "fase_1": a, "fase_2": b,
            "correcto": (a == "LIVE_FRESH" and b == "CACHED_FRESH")}
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache-dir", default=None)
    ap.add_argument("--timeout", type=int, default=240)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--dos-fases", action="store_true")
    ap.add_argument("--sujetos", default=None,
                    help="Ruta a un JSON con el analysis del caso para probar el screening")
    args = ap.parse_args()

    store = SnapshotStore(cache_dir=args.cache_dir)
    registro = {"live_sources_verified": True, "fuentes": {}, "sujetos": None,
                "dos_fases": None}

    if args.dos_fases:
        fases = dos_fases(store, args.timeout, json_out=args.json)
        registro["dos_fases"] = fases
        for sid, cmp in (fases.get("comparacion") or {}).items():
            if not cmp["correcto"]:
                registro["live_sources_verified"] = False
        for sid in CORE_SOURCE_IDS:
            registro["fuentes"][sid] = fases["fase_1_force_refresh"][sid]
        if not args.json:
            print("\nFASE 1 (force_refresh): "
                  + ", ".join(f"{s}={e['freshness']}"
                              for s, e in fases["fase_1_force_refresh"].items()))
            print("FASE 2 (sin refresh):   "
                  + ", ".join(f"{s}={e['freshness']}"
                              for s, e in fases["fase_2_sin_refresh"].items()))
            print("VEREDICTO DOS FASES: " + ("OK" if fases["ok"] else "FALLO"))
    else:
        for sid in CORE_SOURCE_IDS:
            snap, _regs = adquirir_fuente(sid, store=store, timeout=args.timeout)
            estado = _registro(sid, snap)
            registro["fuentes"][sid] = estado
            if snap.acquisition_status != "OPERATIVA":
                registro["live_sources_verified"] = False
            _imprimir(estado, silencioso=args.json)

    if args.sujetos:
        from sanctions.engine import ejecutar_screening
        analysis = json.loads(Path(args.sujetos).read_text(encoding="utf-8"))
        s = ejecutar_screening(analysis=analysis, cache_dir=args.cache_dir,
                               timeout=args.timeout, force_refresh=False)
        registro["sujetos"] = {
            "status": s.status, "executed": s.executed,
            "coverage_status": s.coverage_status,
            "coverage_complete": s.coverage_complete,
            "declarados": s.subjects_declared, "screeningados": s.subjects_screened,
            "no_screeningados": s.subjects_not_screened,
            "evidence_expected": s.evidence_expected_count,
            "evidence_created": s.evidence_created_count,
            "evidence_chain_status": s.evidence_chain_status,
            "reason": s.reason,
            "por_sujeto": [
                {"sujeto": e.canonical_name, "tipo": e.person_type,
                 "documento": f"{e.document_type or ''} {e.document_number or ''}".strip(),
                 "variantes": list(e.declared_name_variants),
                 "resultados": [{"fuente": o.source_id, "resultado": o.result,
                                 "score": o.score} for o in s.outcomes_de(e.subject_id)]}
                for e in s.subjects],
        }
    if args.json:
        print(json.dumps(registro, ensure_ascii=False, indent=1))
    elif not registro["live_sources_verified"]:
        print("LIVE_SOURCES_NOT_VERIFIED: alguna fuente oficial no quedó OPERATIVA "
              "o la prueba de dos fases no se cumplió.")
    return 0 if registro["live_sources_verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())


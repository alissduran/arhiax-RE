# -*- coding: utf-8 -*-
"""03S.1 — Aceptación EN VIVO de las fuentes de screening (UN / OFAC / UKSL).

Registra por fuente: estado de adquisición, fecha efectiva declarada por la
propia fuente, número de registros, SHA-256 y versión del parser. Si no hay red,
informa `LIVE_SOURCES_NOT_VERIFIED` y NO simula éxito (§40).

Uso:
    python scripts/screening_live_check.py [--cache-dir RUTA] [--json]
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache-dir", default=None)
    ap.add_argument("--timeout", type=int, default=240)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--sujetos", default=None,
                    help="Ruta a un JSON con el analysis del caso para probar el screening")
    args = ap.parse_args()

    store = SnapshotStore(cache_dir=args.cache_dir)
    registro = {"live_sources_verified": True, "fuentes": {}, "sujetos": None}

    for sid in CORE_SOURCE_IDS:
        d = get_source(sid)
        snap, regs = adquirir_fuente(sid, store=store, timeout=args.timeout)
        estado = {
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
        registro["fuentes"][sid] = estado
        if snap.acquisition_status != "OPERATIVA":
            registro["live_sources_verified"] = False
        if not args.json:
            print(f"[{sid}] {estado['acquisition_status']} · {estado['freshness']} · "
                  f"registros={estado['record_count']} · efectiva={estado['effective_date']} · "
                  f"sha256={estado['sha256'][:16]} · parser={estado['parser_version']}")
            if estado["error"]:
                print(f"    error: {estado['error']}")

    if args.sujetos:
        from sanctions.engine import ejecutar_screening
        analysis = json.loads(Path(args.sujetos).read_text(encoding="utf-8"))
        s = ejecutar_screening(analysis=analysis, cache_dir=args.cache_dir,
                               timeout=args.timeout, force_refresh=False)
        registro["sujetos"] = {
            "status": s.status, "executed": s.executed,
            "declarados": s.subjects_declared, "screeningados": s.subjects_screened,
            "no_screeningados": s.subjects_not_screened,
            "reason": s.reason,
            "por_sujeto": [
                {"sujeto": e.canonical_name, "tipo": e.person_type,
                 "documento": f"{e.document_type or ''} {e.document_number or ''}".strip(),
                 "resultados": [{"fuente": o.source_id, "resultado": o.result,
                                 "score": o.score} for o in s.outcomes_de(e.subject_id)]}
                for e in s.subjects],
        }
    if args.json:
        print(json.dumps(registro, ensure_ascii=False, indent=1))
    elif not registro["live_sources_verified"]:
        print("LIVE_SOURCES_NOT_VERIFIED: alguna fuente oficial no quedó OPERATIVA.")
    return 0 if registro["live_sources_verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

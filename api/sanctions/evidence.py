# -*- coding: utf-8 -*-
"""Evidencia por consulta (§20) y semántica de hashes (§21).

Se distinguen CUATRO hashes, cada uno con un objeto sellado distinto:

  * `subject_hash`  — sella el SUJETO CANÓNICO (identidad consultada).
  * `snapshot_hash` — sella el ARTEFACTO de la fuente oficial (la lista/versión).
  * `query_hash`    — sella la CONSULTA (sujeto + fuente + snapshot + algoritmo).
  * `evidence_hash` — sella el ENVELOPE de evidencia completo de esa consulta.

Un hash prueba la INTEGRIDAD del artefacto y la reproducibilidad de la consulta;
NO prueba que la información de origen sea verdadera ni sustituye la validación
de la fuente oficial.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import uuid
from typing import Any, Dict, Optional, Tuple

from .contracts import EvidenceRecord, SourceOutcome, SubjectEnvelope
from .matching import ALGORITHM_VERSION

CONTROL_ID = "SAG-S1"
EVENT_TYPE = "SUBJECT_SCREENED"

SEMANTICA_HASH = (
    "subject_hash sella el sujeto canónico consultado; snapshot_hash sella el artefacto de la "
    "fuente oficial (lista y versión); query_hash sella la consulta (sujeto + fuente + snapshot + "
    "algoritmo); evidence_hash sella el envelope de evidencia completo. Los hashes prueban "
    "INTEGRIDAD y reproducibilidad del artefacto, NO que la información de origen sea verdadera."
)


def _canonical(d: Any) -> bytes:
    return json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(data: Any) -> str:
    if isinstance(data, bytes):
        return hashlib.sha256(data).hexdigest()
    return hashlib.sha256(_canonical(data)).hexdigest()


def subject_hash(env: SubjectEnvelope) -> str:
    return sha256_hex({
        "subject_id": env.subject_id, "canonical_name": env.canonical_name,
        "person_type": env.person_type, "document_type": env.document_type,
        "document_normalized": env.document_normalized, "roles": list(env.roles),
    })


def query_hash(env: SubjectEnvelope, source_id: str, snapshot_sha256: str,
               algorithm_version: str = ALGORITHM_VERSION) -> str:
    return sha256_hex({
        "subject_id": env.subject_id,
        "subject_hash": subject_hash(env),
        "source_id": source_id,
        "snapshot_sha256": snapshot_sha256 or "",
        "algorithm_version": algorithm_version,
    })


def build_evidence(env: SubjectEnvelope, outcome: SourceOutcome,
                   *, screened_at: Optional[str] = None,
                   algorithm_version: str = ALGORITHM_VERSION) -> EvidenceRecord:
    """Construye el envelope de evidencia de UNA consulta sujeto×fuente."""
    ts = screened_at or datetime.datetime.now(
        datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    qh = query_hash(env, outcome.source_id, outcome.snapshot_sha256, algorithm_version)
    base = {
        "evidence_id": None,
        "subject_id": env.subject_id,
        "canonical_name": env.canonical_name,
        "document_type": env.document_type,
        "document_number_masked": env.masked_document,
        "source_id": outcome.source_id,
        "snapshot_sha256": outcome.snapshot_sha256,
        "snapshot_effective_date": outcome.snapshot_effective_date,
        "query_hash": qh,
        "screened_at": ts,
        "algorithm_version": algorithm_version,
        "result": outcome.result,
        "score": round(float(outcome.score or 0.0), 4),
        "matched_record_ids": list(outcome.matched_record_ids),
        "matching_reasons": list(outcome.matching_reasons),
        "review_status": outcome.review_status,
        "subject_hash": subject_hash(env),
    }
    ev_hash = sha256_hex({k: v for k, v in base.items() if k != "evidence_id"})
    record = EvidenceRecord(evidence_id=ev_hash[:24], **{k: v for k, v in base.items()
                                                         if k != "evidence_id"},
                            evidence_hash=ev_hash)
    return record


def evidence_payloads(records: Tuple[EvidenceRecord, ...]) -> Tuple[Dict[str, Any], ...]:
    """Payloads de evidencia (para encadenar con el envelope HMAC existente)."""
    return tuple(r.to_dict() for r in records)


def encadenar_eventos(payloads: Tuple[Dict[str, Any], ...], agent_id: str
                      ) -> Tuple[Dict[str, Any], ...]:
    """Encadena la evidencia con el mecanismo HMAC ya existente (arhia_sag_screen).

    Nunca lanza: si el subsistema de evidencia no está disponible, devuelve ()
    (la consulta sigue siendo válida; solo no se encadena).
    """
    try:
        from arhia_sag_screen.evidence.envelope import build_event
    except Exception:  # noqa: BLE001
        return ()
    eventos = []
    prev = ""
    for p in payloads:
        try:
            ev = build_event(CONTROL_ID, EVENT_TYPE, agent_id, dict(p),
                             previous_hash=prev)
            prev = ev.get("chain_hash", "")
            eventos.append(ev)
        except Exception:  # noqa: BLE001
            break
    return tuple(eventos)

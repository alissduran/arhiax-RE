# -*- coding: utf-8 -*-
"""Evidencia por consulta (§20) y semántica de hashes (§21 / 03S.1C).

Se distinguen CINCO hashes, cada uno con un objeto sellado distinto:

  * `subject_hash`          — identidad canónica del SUJETO.
  * `screening_input_hash`  — INPUTS EFECTIVOS enviados al matcher (nombre
    canónico, variantes declaradas, tipo/normalización de documento e
    identificadores adicionales, fecha de nacimiento si existe). Dos sujetos que
    el matcher puede tratar de forma distinta NO pueden compartir este hash.
  * `snapshot_hash`         — bytes/versión de la lista oficial.
  * `query_hash`            — screening_input + snapshot + PARSER + MATCHER.
  * `evidence_hash`         — envelope completo (incluye el sello de tiempo);
    `evidence_content_hash` es el mismo contenido SIN el sello de tiempo, para
    reproducibilidad binaria.

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
    "subject_hash sella la identidad canónica del sujeto; screening_input_hash sella los inputs "
    "efectivos enviados al matcher (nombre canónico, variantes declaradas, documento e "
    "identificadores); snapshot_hash sella el artefacto de la fuente oficial (lista y versión); "
    "query_hash sella la consulta (inputs + snapshot + versión del parser + versión del matcher); "
    "evidence_hash sella el envelope completo, incluido el sello de tiempo, y "
    "evidence_content_hash el mismo contenido sin ese sello (reproducibilidad binaria). Los "
    "hashes prueban INTEGRIDAD y reproducibilidad del artefacto, NO que la información de origen "
    "sea verdadera."
)


def _canonical(d: Any) -> bytes:
    return json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(data: Any) -> str:
    if isinstance(data, bytes):
        return hashlib.sha256(data).hexdigest()
    return hashlib.sha256(_canonical(data)).hexdigest()


def subject_hash(env: SubjectEnvelope) -> str:
    """Identidad canónica del sujeto (incluye su rol y su tipo de persona)."""
    return sha256_hex({
        "subject_id": env.subject_id, "canonical_name": env.canonical_name,
        "person_type": env.person_type, "document_type": env.document_type,
        "document_normalized": env.document_normalized, "roles": list(env.roles),
    })


def screening_input_hash(env: SubjectEnvelope) -> str:
    """Inputs MATERIALES que el matcher usa realmente (03S.1C-4).

    Incluye nombre canónico, variantes declaradas (que se consultan por
    separado), tipo y forma normalizada del documento, identificadores
    adicionales del sujeto y fecha de nacimiento si existiera. NO incluye campos
    de presentación (nombre declarado crudo, participación, provenance) porque no
    alteran el resultado del cotejo.
    """
    from .subjects import match_key
    _ids = []
    for i in (env.identifiers or ()):
        if isinstance(i, dict):
            _ids.append({"type": i.get("type") or "", "value": i.get("value") or ""})
    return sha256_hex({
        "canonical_match_key": match_key(env.canonical_name),
        "declared_name_variants": [match_key(v) for v in (env.declared_name_variants or ())],
        "document_type": env.document_type or "",
        "document_normalized": env.document_normalized or "",
        "identifiers": sorted(_ids, key=lambda x: (x["type"], x["value"])),
        "fecha_nacimiento": getattr(env, "fecha_nacimiento", None),
    })


def query_hash(env: SubjectEnvelope, source_id: str, snapshot_sha256: str,
               parser_version: str = "",
               algorithm_version: str = ALGORITHM_VERSION) -> str:
    """Sella la CONSULTA: inputs + snapshot + PARSER + MATCHER (03S.1C-3).

    El mismo XML crudo procesado por un parser distinto produce una
    representación normalizada potencialmente distinta y, por tanto, un
    resultado potencialmente distinto: la versión del parser es parte de la
    identidad criptográfica de la consulta.
    """
    return sha256_hex({
        "screening_input_hash": screening_input_hash(env),
        "subject_id": env.subject_id,
        "source_id": source_id,
        "snapshot_sha256": snapshot_sha256 or "",
        "parser_version": parser_version or "",
        "algorithm_version": algorithm_version,
    })


def build_evidence(env: SubjectEnvelope, outcome: SourceOutcome,
                   *, screened_at: Optional[str] = None,
                   algorithm_version: str = ALGORITHM_VERSION) -> EvidenceRecord:
    """Construye el envelope de evidencia de UNA consulta sujeto×fuente.

    La versión del PARSER viene del snapshot que produjo los registros
    (`outcome.parser_version`), no se infiere después del registry: para
    reproducir evidencia histórica importa el parser usado EN ESE MOMENTO.
    """
    ts = screened_at or datetime.datetime.now(
        datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    _parser_v = outcome.parser_version or ""
    qh = query_hash(env, outcome.source_id, outcome.snapshot_sha256,
                    parser_version=_parser_v, algorithm_version=algorithm_version)
    base = {
        "evidence_id": None,
        "subject_id": env.subject_id,
        "canonical_name": env.canonical_name,
        "document_type": env.document_type,
        "document_number_masked": env.masked_document,
        "source_id": outcome.source_id,
        "snapshot_sha256": outcome.snapshot_sha256,
        "snapshot_effective_date": outcome.snapshot_effective_date,
        "matcher_version": algorithm_version,
        "parser_version": _parser_v,
        "screening_input_hash": screening_input_hash(env),
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
    _sin_id = {k: v for k, v in base.items() if k != "evidence_id"}
    # Hash de CONTENIDO: sin el sello de tiempo -> reproducible bit a bit entre
    # ejecuciones equivalentes. El hash del envelope sí incluye el timestamp.
    content_hash = sha256_hex({k: v for k, v in _sin_id.items() if k != "screened_at"})
    ev_hash = sha256_hex(_sin_id)
    record = EvidenceRecord(evidence_id=ev_hash[:24], **_sin_id,
                            evidence_hash=ev_hash,
                            evidence_content_hash=content_hash)
    return record


def evidence_payloads(records: Tuple[EvidenceRecord, ...]) -> Tuple[Dict[str, Any], ...]:
    """Payloads de evidencia (para encadenar con el envelope HMAC existente)."""
    return tuple(r.to_dict() for r in records)


def verificar_cadena(eventos) -> bool:
    """Verifica la cadena HMAC delegando en el mecanismo existente.

    03S.1A-2: la verificación es explícita. Si el subsistema no está disponible
    o la cadena no se puede verificar, devuelve False (y el motor lo declara como
    `evidence_chain_status=FAILED`, nunca en silencio).
    """
    if not eventos:
        return False
    try:
        from arhia_sag_screen.evidence.envelope import verificar_cadena as _v
    except Exception:  # noqa: BLE001
        return False
    try:
        return bool(_v(list(eventos)))
    except Exception:  # noqa: BLE001
        return False


def encadenar_eventos(payloads: Tuple[Dict[str, Any], ...], agent_id: str
                      ) -> Tuple[Dict[str, Any], ...]:
    """Encadena la evidencia con el mecanismo HMAC ya existente (arhia_sag_screen).

    Devuelve () si el subsistema no está disponible: el llamador DEBE declararlo
    como `FAILED` explícitamente (nunca interpretarlo como éxito silencioso).
    """
    try:
        from arhia_sag_screen.evidence.envelope import build_event
    except Exception as e:  # noqa: BLE001
        print(f"[SCREENING][EVIDENCE] cadena no disponible: {e}")
        return ()
    eventos = []
    prev = ""
    for p in payloads:
        ev = build_event(CONTROL_ID, EVENT_TYPE, agent_id, dict(p),
                         previous_hash=prev)
        prev = ev.get("chain_hash", "")
        eventos.append(ev)
    return tuple(eventos)

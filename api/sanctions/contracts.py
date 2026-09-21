# -*- coding: utf-8 -*-
"""Contratos de la capa de screening sancionatorio (03S.1).

Vocabulario ÚNICO y cerrado de estados. Nada fuera de estas listas se imprime
en el dictamen; si un productor devuelve un valor desconocido, se degrada a
`NOT_SCREENED` (nunca a un estado "bueno").
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

# ── Tipos de persona (Gate 1) ────────────────────────────────────────────────
# UNKNOWN != NATURAL_PERSON: la ausencia de documento NO convierte a nadie en
# persona natural.
PERSON_NATURAL = "NATURAL_PERSON"
PERSON_LEGAL = "LEGAL_ENTITY"
PERSON_UNKNOWN = "UNKNOWN"
PERSON_TYPES = (PERSON_NATURAL, PERSON_LEGAL, PERSON_UNKNOWN)

# ── Resultado POR FUENTE (§18) ───────────────────────────────────────────────
RESULT_NO_MATCH = "NO_MATCH"
RESULT_POTENTIAL = "POTENTIAL_MATCH"
RESULT_STRONG = "STRONG_MATCH"
RESULT_EXACT = "EXACT_MATCH"
RESULT_REVIEW = "REVIEW_REQUIRED"
RESULT_NOT_SCREENED = "NOT_SCREENED"
RESULT_SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"

RESULT_STATES = (RESULT_NO_MATCH, RESULT_POTENTIAL, RESULT_STRONG,
                 RESULT_EXACT, RESULT_REVIEW, RESULT_NOT_SCREENED,
                 RESULT_SOURCE_UNAVAILABLE)

# Estados que EXIGEN revisión humana antes de cualquier decisión.
RESULT_STATES_REVISION = (RESULT_POTENTIAL, RESULT_STRONG, RESULT_EXACT,
                          RESULT_REVIEW)
# Estados que NO son una conclusión de "sin coincidencia".
RESULT_STATES_NO_CONCLUYENTES = (RESULT_NOT_SCREENED, RESULT_SOURCE_UNAVAILABLE)

# Etiquetas de celda del dictamen (§23).
RESULT_LABEL = {
    RESULT_NO_MATCH: "NO MATCH",
    RESULT_POTENTIAL: "REVIEW",
    RESULT_STRONG: "REVIEW",
    RESULT_EXACT: "MATCH",
    RESULT_REVIEW: "REVIEW",
    RESULT_NOT_SCREENED: "NOT SCREENED",
    RESULT_SOURCE_UNAVAILABLE: "UNAVAILABLE",
}


def result_label(state: Optional[str], *, cached: bool = False) -> str:
    """Etiqueta corta de celda (§23/§16): MATCH/REVIEW/NO MATCH/UNAVAILABLE/CACHED."""
    base = RESULT_LABEL.get(state or "", "NOT SCREENED")
    if cached and state not in (RESULT_NOT_SCREENED, RESULT_SOURCE_UNAVAILABLE):
        return base + " (CACHED)"
    return base


# ── Estado global del screening (§25) ────────────────────────────────────────
SCREENING_COMPLETE = "SCREENING_COMPLETE"
SCREENING_PARTIAL = "SCREENING_PARTIAL"
SCREENING_NOT_EXECUTED = "SCREENING_NOT_EXECUTED"
SCREENING_REVIEW_REQUIRED = "SCREENING_REVIEW_REQUIRED"

SCREENING_STATES = (SCREENING_COMPLETE, SCREENING_PARTIAL,
                    SCREENING_NOT_EXECUTED, SCREENING_REVIEW_REQUIRED)

SCREENING_LABEL = {
    SCREENING_COMPLETE: "COMPLETO",
    SCREENING_PARTIAL: "PARCIAL",
    SCREENING_NOT_EXECUTED: "NO EJECUTADO",
    SCREENING_REVIEW_REQUIRED: "REQUIERE REVISIÓN",
}

# ── Frescura del snapshot (§15) ──────────────────────────────────────────────
FRESH_LIVE = "LIVE_FRESH"
FRESH_CACHED = "CACHED_FRESH"
STALE_ALLOWED = "STALE_ALLOWED"
STALE_NOT_ALLOWED = "STALE_NOT_ALLOWED"
SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
NO_SNAPSHOT = "NO_SNAPSHOT"

FRESHNESS_STATES = (FRESH_LIVE, FRESH_CACHED, STALE_ALLOWED, STALE_NOT_ALLOWED,
                    SOURCE_UNAVAILABLE, NO_SNAPSHOT)

# "en vivo" SOLO con adquisición real en esta ejecución (§16).
FRESHNESS_LABEL = {
    FRESH_LIVE: "consultado en vivo",
    FRESH_CACHED: "consultado contra snapshot oficial versionado",
    STALE_ALLOWED: "consultado contra snapshot oficial versionado (fuera de TTL, autorizado)",
    STALE_NOT_ALLOWED: "no consultado (snapshot fuera de vigencia)",
    SOURCE_UNAVAILABLE: "fuente no disponible en esta ejecución",
    NO_SNAPSHOT: "sin snapshot disponible",
}


def freshness_label(state: Optional[str]) -> str:
    return FRESHNESS_LABEL.get(state or "", "no consultado")


# ── Categoría de fuente (§10) ────────────────────────────────────────────────
CAT_SANCTIONS = "SANCTIONS_LIST"
CAT_REGULATORY_REPORTING = "REGULATORY_REPORTING"
CAT_PEP = "PEP_REGISTRY"
CAT_ENFORCEMENT = "LAW_ENFORCEMENT_NOTICE"

# Política de adquisición
ACQ_LIVE = "LIVE_DOWNLOAD"
ACQ_FILE = "OFFICIAL_FILE_REQUIRED"
ACQ_OUT_OF_SCOPE = "OUT_OF_SCOPE_FOR_SCREENING"

# Estado de adquisición del snapshot
SNAP_OPERATIVA = "OPERATIVA"
SNAP_SYNTHETIC = "SYNTHETIC_TEST_FIXTURE"


@dataclass(frozen=True)
class SanctionsSnapshot:
    """Snapshot versionado e inmutable de una fuente oficial (§13)."""
    snapshot_id: str
    source_id: str
    authority: str
    retrieved_at: str
    effective_date: str = ""
    source_url: str = ""
    sha256: str = ""
    record_count: int = 0
    parser_version: str = ""
    acquisition_status: str = SNAP_OPERATIVA
    freshness: str = NO_SNAPSHOT
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id, "source_id": self.source_id,
            "authority": self.authority, "retrieved_at": self.retrieved_at,
            "effective_date": self.effective_date, "source_url": self.source_url,
            "sha256": self.sha256, "record_count": self.record_count,
            "parser_version": self.parser_version,
            "acquisition_status": self.acquisition_status,
            "freshness": self.freshness, "error": self.error,
        }


@dataclass(frozen=True)
class SubjectEnvelope:
    """Sujeto canónico (Gate 1). Único insumo del screening."""
    subject_id: str
    raw_name: str
    canonical_name: str
    person_type: str = PERSON_UNKNOWN
    document_type: Optional[str] = None
    document_number: Optional[str] = None
    document_normalized: Optional[str] = None
    roles: Tuple[str, ...] = ()
    participation: Optional[str] = None
    source: str = ""
    source_reference: str = ""
    identity_confidence: str = "UNVERIFIED"
    identity_warnings: Tuple[str, ...] = ()
    screened: bool = True
    reason_for_screening: str = ""
    not_screened_reason: Optional[str] = None

    @property
    def masked_document(self) -> str:
        return mask_document(self.document_type, self.document_normalized)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subject_id": self.subject_id, "raw_name": self.raw_name,
            "canonical_name": self.canonical_name, "person_type": self.person_type,
            "document_type": self.document_type,
            "document_number": self.document_number,
            "document_normalized": self.document_normalized,
            "roles": list(self.roles), "participation": self.participation,
            "source": self.source, "source_reference": self.source_reference,
            "identity_confidence": self.identity_confidence,
            "identity_warnings": list(self.identity_warnings),
            "screened": self.screened,
            "reason_for_screening": self.reason_for_screening,
            "not_screened_reason": self.not_screened_reason,
        }


def mask_document(document_type: Optional[str], number: Optional[str]) -> str:
    """Máscara de documento para evidencia (§20): CC 1045*****X / NIT 8600*****."""
    if not number:
        return "N/D"
    n = str(number)
    if len(n) <= 4:
        return "****"
    return f"{n[:4]}{'*' * (len(n) - 5)}{n[-1]}"


@dataclass(frozen=True)
class SourceOutcome:
    """Resultado de un sujeto contra UNA fuente (§18/§23)."""
    subject_id: str
    source_id: str
    result: str = RESULT_NOT_SCREENED
    score: float = 0.0
    matched_record_ids: Tuple[str, ...] = ()
    matching_reasons: Tuple[str, ...] = ()
    snapshot_id: str = ""
    snapshot_sha256: str = ""
    snapshot_effective_date: str = ""
    freshness: str = NO_SNAPSHOT
    review_status: str = "NO_REQUIERE"
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subject_id": self.subject_id, "source_id": self.source_id,
            "result": self.result, "score": self.score,
            "matched_record_ids": list(self.matched_record_ids),
            "matching_reasons": list(self.matching_reasons),
            "snapshot_id": self.snapshot_id,
            "snapshot_sha256": self.snapshot_sha256,
            "snapshot_effective_date": self.snapshot_effective_date,
            "freshness": self.freshness, "review_status": self.review_status,
            "note": self.note,
        }


@dataclass(frozen=True)
class EvidenceRecord:
    """Envelope de evidencia por consulta (§20)."""
    evidence_id: str
    subject_id: str
    canonical_name: str
    document_type: Optional[str]
    document_number_masked: str
    source_id: str
    snapshot_sha256: str
    snapshot_effective_date: str
    query_hash: str
    screened_at: str
    algorithm_version: str
    result: str
    score: float
    matched_record_ids: Tuple[str, ...]
    matching_reasons: Tuple[str, ...]
    review_status: str
    subject_hash: str = ""
    evidence_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id, "subject_id": self.subject_id,
            "canonical_name": self.canonical_name,
            "document_type": self.document_type,
            "document_number_masked": self.document_number_masked,
            "source_id": self.source_id, "snapshot_sha256": self.snapshot_sha256,
            "snapshot_effective_date": self.snapshot_effective_date,
            "query_hash": self.query_hash, "screened_at": self.screened_at,
            "algorithm_version": self.algorithm_version, "result": self.result,
            "score": self.score,
            "matched_record_ids": list(self.matched_record_ids),
            "matching_reasons": list(self.matching_reasons),
            "review_status": self.review_status,
            "subject_hash": self.subject_hash,
            "evidence_hash": self.evidence_hash,
        }


@dataclass(frozen=True)
class ScreeningSummary:
    """Resumen ÚNICO consumido por 05, 09, 16, 16.b y receipts (§25)."""
    status: str = SCREENING_NOT_EXECUTED
    executed: bool = False
    subjects_declared: int = 0
    subjects_screened: int = 0
    subjects_not_screened: int = 0
    subjects: Tuple[SubjectEnvelope, ...] = ()
    outcomes: Tuple[SourceOutcome, ...] = ()
    sources: Tuple[str, ...] = ()
    sources_available: Tuple[str, ...] = ()
    sources_unavailable: Tuple[str, ...] = ()
    snapshots: Tuple[SanctionsSnapshot, ...] = ()
    review_required_subjects: Tuple[str, ...] = ()
    matched_subjects: Tuple[str, ...] = ()
    reason: str = ""
    executed_at: str = ""
    algorithm_version: str = ""
    scope_note: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    # ── Consumidores (una sola verdad) ───────────────────────────────────────
    @property
    def completo(self) -> bool:
        return self.status == SCREENING_COMPLETE

    @property
    def cobertura_completa(self) -> bool:
        """¿Se consultaron TODAS las fuentes para TODOS los sujetos?

        Es distinto de `completo`: un screening con cobertura completa puede
        exigir revisión humana (REVIEW_REQUIRED) sin que falte ninguna fuente.
        """
        return self.status in (SCREENING_COMPLETE, SCREENING_REVIEW_REQUIRED)

    @property
    def hay_coincidencia(self) -> bool:
        return bool(self.matched_subjects)

    @property
    def etiqueta(self) -> str:
        return SCREENING_LABEL.get(self.status, "NO EJECUTADO")

    def outcomes_de(self, subject_id: str) -> Tuple[SourceOutcome, ...]:
        return tuple(o for o in self.outcomes if o.subject_id == subject_id)

    def subject(self, subject_id: str) -> Optional[SubjectEnvelope]:
        for s in self.subjects:
            if s.subject_id == subject_id:
                return s
        return None

    def snapshot(self, source_id: str) -> Optional[SanctionsSnapshot]:
        for s in self.snapshots:
            if s.source_id == source_id:
                return s
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status, "executed": self.executed,
            "subjects_declared": self.subjects_declared,
            "subjects_screened": self.subjects_screened,
            "subjects_not_screened": self.subjects_not_screened,
            "subjects": [s.to_dict() for s in self.subjects],
            "outcomes": [o.to_dict() for o in self.outcomes],
            "sources": list(self.sources),
            "sources_available": list(self.sources_available),
            "sources_unavailable": list(self.sources_unavailable),
            "snapshots": [s.to_dict() for s in self.snapshots],
            "review_required_subjects": list(self.review_required_subjects),
            "matched_subjects": list(self.matched_subjects),
            "reason": self.reason, "executed_at": self.executed_at,
            "algorithm_version": self.algorithm_version,
            "scope_note": self.scope_note, "extra": dict(self.extra),
        }

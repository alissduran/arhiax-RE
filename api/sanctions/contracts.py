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


# ── Estado de la cadena de evidencia (§ 03S.1A-2) ───────────────────────────
CHAIN_SEALED = "SEALED"
CHAIN_FAILED = "FAILED"
CHAIN_NOT_REQUIRED_DEV = "NOT_REQUIRED_DEV"

CHAIN_STATES = (CHAIN_SEALED, CHAIN_FAILED, CHAIN_NOT_REQUIRED_DEV)


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
    # 03S.1B-6: el refresco FALLIDO se declara aparte. La frescura describe la
    # EDAD del snapshot, no el éxito/fracaso del intento deactualizarlo.
    refresh_error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id, "source_id": self.source_id,
            "authority": self.authority, "retrieved_at": self.retrieved_at,
            "effective_date": self.effective_date, "source_url": self.source_url,
            "sha256": self.sha256, "record_count": self.record_count,
            "parser_version": self.parser_version,
            "acquisition_status": self.acquisition_status,
            "freshness": self.freshness, "error": self.error,
            "refresh_error": self.refresh_error,
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
    # § 03S.1A-5: variantes de nombre DECLARADAS por la fuente ("A / B"). No son
    # una fusión jurídica: cada variante se consulta por separado y se agrega el
    # resultado más conservador.
    declared_name_variants: Tuple[str, ...] = ()
    # Identificadores adicionales del sujeto (si la fuente aporta varios).
    identifiers: Tuple[Dict[str, Any], ...] = ()

    @property
    def nombres_a_consultar(self) -> Tuple[str, ...]:
        """Nombre canónico + variantes declaradas (sin duplicados, en orden)."""
        out = []
        for n in (self.canonical_name,) + tuple(self.declared_name_variants):
            n = (n or "").strip()
            if n and n not in out:
                out.append(n)
        return tuple(out)

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
            "declared_name_variants": list(self.declared_name_variants),
            "identifiers": [dict(i) for i in self.identifiers],
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
    # 03S.1C-12: versión del PARSER que generó los registros normalizados, tomada
    # del SNAPSHOT (no del registry): es la que realmente produjo el resultado.
    parser_version: str = ""
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
            "parser_version": self.parser_version,
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
    # 03S.1C: identidad de EJECUCIÓN (versiones) + inputs efectivos + hash de
    # contenido sin sello de tiempo.
    matcher_version: str = ""
    parser_version: str = ""
    screening_input_hash: str = ""
    evidence_content_hash: str = ""

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
            "matcher_version": self.matcher_version,
            "parser_version": self.parser_version,
            "screening_input_hash": self.screening_input_hash,
            "evidence_content_hash": self.evidence_content_hash,
        }


@dataclass(frozen=True)
class ScreeningSummary:
    """Resumen ÚNICO consumido por 05, 09, 16, 16.b y receipts (§25).

    03S.1A separa DECISIÓN de COBERTURA:
      * `status` (decisión): COMPLETE / PARTIAL / NOT_EXECUTED / REVIEW_REQUIRED.
      * `coverage_complete`: se deriva de los OUTCOMES (¿se consultó a todos los
        sujetos contra todas las fuentes solicitadas?), no del status.
    """
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
    # Evidencia (§ 03S.1A-2 / 03S.1B-7/8): el conteo debe cuadrar con los outcomes.
    evidence_records: Tuple[Dict[str, Any], ...] = ()
    evidence_expected_count: int = 0
    evidence_created_count: int = 0
    evidence_chain_status: str = CHAIN_NOT_REQUIRED_DEV
    evidence_errors: Tuple[Dict[str, Any], ...] = ()
    extra: Dict[str, Any] = field(default_factory=dict)

    # ── Consumidores (una sola verdad) ───────────────────────────────────────
    @property
    def decision_status(self) -> str:
        """Estado de DECISIÓN (lo que el dictamen afirma sobre el caso)."""
        return self.status

    @property
    def coverage_status(self) -> str:
        """Estado de COBERTURA, independiente de la decisión."""
        if not self.executed:
            return "COVERAGE_NOT_EXECUTED"
        if self.coverage_complete:
            return "COVERAGE_COMPLETE"
        return "COVERAGE_PARTIAL"

    @property
    def coverage_complete(self) -> bool:
        """¿Se consultó a TODOS los sujetos screeningables contra TODAS las
        fuentes solicitadas? Se deriva de los outcomes, no del status.

        Antes se derivaba del status (`in (COMPLETE, REVIEW_REQUIRED)`), lo que
        permitía declarar cobertura completa teniendo una fuente caída.
        """
        if not self.executed or not self.subjects or not self.sources:
            return False
        _screeningables = {s.subject_id for s in self.subjects if s.screened}
        if not _screeningables:
            return False
        _esperados = {(sid, src) for sid in _screeningables for src in self.sources}
        _cubiertos = {
            (o.subject_id, o.source_id) for o in self.outcomes
            if o.subject_id in _screeningables and o.source_id in self.sources
            and o.result not in (RESULT_NOT_SCREENED, RESULT_SOURCE_UNAVAILABLE)
        }
        return _cubiertos == _esperados

    @property
    def completo(self) -> bool:
        return self.status == SCREENING_COMPLETE

    @property
    def cobertura_completa(self) -> bool:
        """Alias histórico de `coverage_complete` (misma derivación)."""
        return self.coverage_complete

    @property
    def evidence_complete(self) -> bool:
        """¿Hay un envelope por CADA consulta esperada? (conteo, sin más)."""
        return (self.evidence_expected_count > 0
                and self.evidence_created_count == self.evidence_expected_count)

    @property
    def evidence_sealed(self) -> bool:
        """¿La cadena HMAC quedó SELLADA en esta ejecución?

        03S.1B-7: `NOT_REQUIRED_DEV` NUNCA cuenta como sellado.
        """
        return self.evidence_chain_status == CHAIN_SEALED

    @property
    def evidence_reproducible(self) -> bool:
        """¿La consulta puede reproducirse con lo registrado?

        03S.1C-7: exige los envelopes COMPLETOS y, por cada uno, la identidad de
        ejecución completa: `subject_hash`, `screening_input_hash`,
        `snapshot_sha256`, `parser_version`, `matcher_version`, `query_hash` y
        `evidence_hash`. La presencia de los cuatro hashes antiguos ya no basta.
        No exige que la cadena esté sellada: en desarrollo (`NOT_REQUIRED_DEV`) la
        evidencia es reproducible pero NO está sellada, y así se declara.
        """
        if not self.evidence_complete:
            return False
        _requeridos = ("subject_hash", "screening_input_hash", "snapshot_sha256",
                       "parser_version", "matcher_version", "query_hash",
                       "evidence_hash")
        for e in self.evidence_records:
            if not all(e.get(k) for k in _requeridos):
                return False
        return True

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
            "decision_status": self.decision_status,
            "coverage_status": self.coverage_status,
            "coverage_complete": self.coverage_complete,
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
            "scope_note": self.scope_note,
            "evidence_records": [dict(e) for e in self.evidence_records],
            "evidence_expected_count": self.evidence_expected_count,
            "evidence_created_count": self.evidence_created_count,
            "evidence_chain_status": self.evidence_chain_status,
            "evidence_errors": [dict(e) for e in self.evidence_errors],
            "evidence_complete": self.evidence_complete,
            "evidence_sealed": self.evidence_sealed,
            "evidence_reproducible": self.evidence_reproducible,
            "extra": dict(self.extra),
        }

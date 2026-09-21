# -*- coding: utf-8 -*-
"""Motor de screening sancionatorio 03S.1 (una sola verdad).

Flujo:
  SUJETOS CANÓNICOS → FUENTES OFICIALES → SNAPSHOTS VERSIONADOS →
  MATCHING DETERMINISTA → EVIDENCIA → ScreeningSummary

El `ScreeningSummary` es el ÚNICO resumen que consumen las secciones 05, 09, 16,
16.B y los receipts (§25): no puede haber un capítulo que diga "screening
ejecutado" y otro "no ejecutado".

Nunca lanza: ante un fallo devuelve un summary NO EJECUTADO con la causa.
"""
from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import matching
from .acquire import adquirir_fuente, es_cache, es_en_vivo, fuente_disponible
from .contracts import (
    RESULT_NOT_SCREENED, RESULT_SOURCE_UNAVAILABLE, RESULT_STATES_REVISION,
    SCREENING_COMPLETE, SCREENING_NOT_EXECUTED, SCREENING_PARTIAL,
    SCREENING_REVIEW_REQUIRED, SNAP_OPERATIVA, ScreeningSummary, SourceOutcome,
    SubjectEnvelope,
)
from .evidence import build_evidence, encadenar_eventos
from .registry import (
    CORE_SOURCE_IDS, cobertura_declarada, get_source, screening_sources,
)
from .snapshots import TTL_DEFAULT, SnapshotStore

ALGORITHM_VERSION = matching.ALGORITHM_VERSION

SIGLA = {
    "UN_CONSOLIDATED": "ONU",
    "OFAC_SDN": "OFAC SDN",
    "OFAC_NON_SDN": "OFAC no-SDN",
    "UK_SANCTIONS_LIST": "UKSL",
    "EU_CONSOLIDATED": "UE",
}

SCOPE_NOTE = (
    "Este screening es apoyo automatizado a la debida diligencia LA/FT: identifica y "
    "consulta contrapartes contra fuentes oficiales y deja evidencia versionada. NO "
    "declara cumplimiento normativo, no determina si una parte es sujeto obligado y no "
    "sustituye la verificación del oficial de cumplimiento."
)


def sigla(source_id: str) -> str:
    return SIGLA.get(source_id, source_id)


def ejecutar_screening(
    *,
    analysis: Dict[str, Any],
    identidad: Optional[Dict[str, Any]] = None,
    source_ids: Sequence[str] = CORE_SOURCE_IDS,
    store: Optional[SnapshotStore] = None,
    cache_dir: Optional[str] = None,
    timeout: int = 120,
    force_refresh: bool = False,
    ttl_segundos: int = TTL_DEFAULT,
    permitir_stale: bool = True,
    permitir_descarga: bool = True,
    agent_id: str = "arhiax-dictus",
    ciudad: str = "barranquilla",
    encadenar_evidencia: bool = True,
) -> ScreeningSummary:
    """Ejecuta el screening completo y devuelve el resumen único."""
    from .subjects import build_subject_envelopes, verificar_invariante

    ejecutado_en = datetime.datetime.now(datetime.timezone.utc).isoformat()
    store = store or SnapshotStore(cache_dir=cache_dir)

    # 1) Sujetos canónicos (Gate 1).
    try:
        envelopes = build_subject_envelopes(analysis or {}, identidad or {},
                                           ciudad=ciudad)
        verificar_invariante(envelopes)
    except Exception as e:  # noqa: BLE001
        return ScreeningSummary(
            status=SCREENING_NOT_EXECUTED, executed=False, reason=f"subject_set_invariant: {e}",
            executed_at=ejecutado_en, algorithm_version=ALGORITHM_VERSION,
            scope_note=SCOPE_NOTE)

    # 2) Fuentes solicitadas que existen y son de screening.
    defs: List[Any] = []
    for sid in source_ids:
        d = get_source(sid)
        if d is not None and d.es_screening:
            defs.append(d)

    # 3) Adquisición (snapshot por fuente, con degradación honesta).
    snapshots: Dict[str, Any] = {}
    registros: Dict[str, List[Any]] = {}
    for d in defs:
        try:
            snap, regs = adquirir_fuente(
                d.source_id, store=store, timeout=timeout,
                force_refresh=force_refresh, ttl_segundos=ttl_segundos,
                permitir_stale=permitir_stale,
                permitir_descarga=permitir_descarga)
        except Exception as e:  # noqa: BLE001
            from .snapshots import error_snapshot
            snap, regs = error_snapshot(d.source_id, d.authority, d.official_url,
                                        f"{type(e).__name__}: {str(e)[:160]}",
                                        d.parser_version), []
        snapshots[d.source_id] = snap
        registros[d.source_id] = list(regs or ())

    # 4) Matching + evidencia.
    outcomes: List[SourceOutcome] = []
    revisión: List[str] = []
    coincidentes: List[str] = []
    for env in envelopes:
        for d in defs:
            snap = snapshots.get(d.source_id)
            out = _consultar(env, d.source_id, snap, registros.get(d.source_id) or [])
            outcomes.append(out)
            if out.result in (matching.RESULT_EXACT,):
                coincidentes.append(env.subject_id)
            elif out.result in RESULT_STATES_REVISION:
                revisión.append(env.subject_id)

    # 5) Estado global (§25/§35).
    status, reason = _estado(envelopes, defs, snapshots, outcomes)

    # 6) Evidencia encadenada (mecanismo existente), best-effort.
    eventos: Tuple[Dict[str, Any], ...] = ()
    if encadenar_evidencia:
        try:
            evidencias = []
            for env in envelopes:
                for out in [o for o in outcomes if o.subject_id == env.subject_id]:
                    evidencias.append(build_evidence(env, out))
            eventos = encadenar_eventos(tuple(e.to_dict() for e in evidencias), agent_id)
        except Exception:  # noqa: BLE001
            eventos = ()

    disponibles = tuple(sorted(s for s, sn in snapshots.items() if fuente_disponible(sn)))
    no_disponibles = tuple(sorted(set(snapshots) - set(disponibles)))
    return ScreeningSummary(
        status=status, executed=bool(disponibles),
        subjects_declared=len(envelopes),
        subjects_screened=sum(1 for e in envelopes if e.screened),
        subjects_not_screened=sum(1 for e in envelopes if not e.screened),
        subjects=tuple(envelopes), outcomes=tuple(outcomes),
        sources=tuple(d.source_id for d in defs),
        sources_available=disponibles, sources_unavailable=no_disponibles,
        snapshots=tuple(snapshots[s] for s in sorted(snapshots)),
        review_required_subjects=tuple(sorted(set(revisión))),
        matched_subjects=tuple(sorted(set(coincidentes))),
        reason=reason, executed_at=ejecutado_en, algorithm_version=ALGORITHM_VERSION,
        scope_note=SCOPE_NOTE,
        extra={
            "cobertura": cobertura_declarada([d.source_id for d in defs]),
            "cobertura_completa": (status in (SCREENING_COMPLETE,
                                              SCREENING_REVIEW_REQUIRED)),
            "en_vivo": [s for s in sorted(snapshots)
                        if es_en_vivo(snapshots[s])],
            "desde_snapshot": [s for s in sorted(snapshots) if es_cache(snapshots[s])],
            "eventos_evidencia": list(eventos),
        },
    )


def _consultar(env: SubjectEnvelope, source_id: str, snap, regs) -> SourceOutcome:
    if not env.screened:
        return SourceOutcome(
            subject_id=env.subject_id, source_id=source_id,
            result=RESULT_NOT_SCREENED, note=env.not_screened_reason or "no screeningado",
            snapshot_id=getattr(snap, "snapshot_id", ""),
            snapshot_sha256=getattr(snap, "sha256", ""),
            snapshot_effective_date=getattr(snap, "effective_date", "") or "",
            freshness=getattr(snap, "freshness", ""))
    if not fuente_disponible(snap):
        return SourceOutcome(
            subject_id=env.subject_id, source_id=source_id,
            result=RESULT_SOURCE_UNAVAILABLE,
            note=(getattr(snap, "error", None)
                  or getattr(snap, "freshness", "") or "fuente no disponible"),
            snapshot_id=getattr(snap, "snapshot_id", ""),
            snapshot_sha256=getattr(snap, "sha256", ""),
            snapshot_effective_date=getattr(snap, "effective_date", "") or "",
            freshness=getattr(snap, "freshness", ""))
    r = matching.consultar(env, regs)
    return SourceOutcome(
        subject_id=env.subject_id, source_id=source_id, result=r.result,
        score=r.score, matched_record_ids=r.matched_record_ids,
        matching_reasons=r.reasons, snapshot_id=snap.snapshot_id,
        snapshot_sha256=snap.sha256,
        snapshot_effective_date=snap.effective_date or "",
        freshness=snap.freshness,
        review_status="REQUIERE_REVISION" if r.requiere_revision else "NO_REQUIERE",
        note="; ".join(r.reasons) if r.reasons else "")


def _estado(envelopes, defs, snapshots, outcomes) -> Tuple[str, str]:
    """Estado global determinista + motivo imprimible."""
    if not defs:
        return SCREENING_NOT_EXECUTED, "no hay fuentes de screening configuradas"
    screeningados = [e for e in envelopes if e.screened]
    if not screeningados:
        return (SCREENING_NOT_EXECUTED,
                "no se identificaron sujetos screeningables en el caso")
    disponibles = [s for s in snapshots if fuente_disponible(snapshots[s])]
    if not disponibles:
        return (SCREENING_NOT_EXECUTED,
                "ninguna fuente oficial de screening estuvo disponible en esta ejecución")

    _revision = [o for o in outcomes if o.result in RESULT_STATES_REVISION]
    _no_disp = sorted({o.source_id for o in outcomes
                       if o.result == RESULT_SOURCE_UNAVAILABLE})
    _no_scr = [o for o in outcomes if o.result == RESULT_NOT_SCREENED]

    partes: List[str] = []
    if _revision:
        status = SCREENING_REVIEW_REQUIRED
        partes.append("hay candidatos que exigen revisión humana en "
                      + ", ".join(sorted({sigla(o.source_id) for o in _revision})))
    elif _no_disp or _no_scr:
        status = SCREENING_PARTIAL
    else:
        status = SCREENING_COMPLETE

    if not _revision:
        if _no_disp:
            partes.append("Sin coincidencias en las fuentes efectivamente consultadas. "
                          + ", ".join(sigla(s) for s in _no_disp) + " no estuvo disponible.")
        else:
            partes.append("Sin coincidencias en las fuentes efectivamente consultadas ("
                          + cobertura_declarada(disponibles) + ").")
    if _no_scr:
        partes.append("{} sujeto(s) no screeningado(s) por nombre no utilizable.".format(
            len(_no_scr)))
    return status, " ".join(partes)


# ── Serialización / rehidratación (el dictamen transporta dicts) ─────────────

def summary_a_dict(summary: ScreeningSummary) -> Dict[str, Any]:
    return summary.to_dict()


def summary_desde_dict(d: Optional[Dict[str, Any]]) -> Optional[ScreeningSummary]:
    if not d:
        return None
    try:
        from .contracts import SanctionsSnapshot

        def _env(x):
            return SubjectEnvelope(
                subject_id=x.get("subject_id", ""), raw_name=x.get("raw_name", ""),
                canonical_name=x.get("canonical_name", ""),
                person_type=x.get("person_type", "UNKNOWN"),
                document_type=x.get("document_type"),
                document_number=x.get("document_number"),
                document_normalized=x.get("document_normalized"),
                roles=tuple(x.get("roles") or ()),
                participation=x.get("participation"), source=x.get("source", ""),
                source_reference=x.get("source_reference", ""),
                identity_confidence=x.get("identity_confidence", "UNVERIFIED"),
                identity_warnings=tuple(x.get("identity_warnings") or ()),
                screened=bool(x.get("screened", True)),
                reason_for_screening=x.get("reason_for_screening", ""),
                not_screened_reason=x.get("not_screened_reason"))

        def _out(x):
            return SourceOutcome(
                subject_id=x.get("subject_id", ""), source_id=x.get("source_id", ""),
                result=x.get("result", RESULT_NOT_SCREENED),
                score=float(x.get("score") or 0.0),
                matched_record_ids=tuple(x.get("matched_record_ids") or ()),
                matching_reasons=tuple(x.get("matching_reasons") or ()),
                snapshot_id=x.get("snapshot_id", ""),
                snapshot_sha256=x.get("snapshot_sha256", ""),
                snapshot_effective_date=x.get("snapshot_effective_date", "") or "",
                freshness=x.get("freshness", ""),
                review_status=x.get("review_status", "NO_REQUIERE"),
                note=x.get("note", ""))

        def _snap(x):
            return SanctionsSnapshot(
                snapshot_id=x.get("snapshot_id", ""), source_id=x.get("source_id", ""),
                authority=x.get("authority", ""), retrieved_at=x.get("retrieved_at", ""),
                effective_date=x.get("effective_date", "") or "",
                source_url=x.get("source_url", "") or "",
                sha256=x.get("sha256", "") or "",
                record_count=int(x.get("record_count") or 0),
                parser_version=x.get("parser_version", "") or "",
                acquisition_status=x.get("acquisition_status", SNAP_OPERATIVA),
                freshness=x.get("freshness", ""), error=x.get("error"))

        return ScreeningSummary(
            status=d.get("status", SCREENING_NOT_EXECUTED),
            executed=bool(d.get("executed")),
            subjects_declared=int(d.get("subjects_declared") or 0),
            subjects_screened=int(d.get("subjects_screened") or 0),
            subjects_not_screened=int(d.get("subjects_not_screened") or 0),
            subjects=tuple(_env(x) for x in (d.get("subjects") or ())),
            outcomes=tuple(_out(x) for x in (d.get("outcomes") or ())),
            sources=tuple(d.get("sources") or ()),
            sources_available=tuple(d.get("sources_available") or ()),
            sources_unavailable=tuple(d.get("sources_unavailable") or ()),
            snapshots=tuple(_snap(x) for x in (d.get("snapshots") or ())),
            review_required_subjects=tuple(d.get("review_required_subjects") or ()),
            matched_subjects=tuple(d.get("matched_subjects") or ()),
            reason=d.get("reason", ""), executed_at=d.get("executed_at", ""),
            algorithm_version=d.get("algorithm_version", ""),
            scope_note=d.get("scope_note", ""), extra=dict(d.get("extra") or {}))
    except Exception:  # noqa: BLE001
        return None

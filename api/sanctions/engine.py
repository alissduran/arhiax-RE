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
    CHAIN_FAILED, CHAIN_NOT_REQUIRED_DEV, CHAIN_SEALED, RESULT_NOT_SCREENED,
    RESULT_SOURCE_UNAVAILABLE, RESULT_STATES_REVISION, SCREENING_COMPLETE,
    SCREENING_NOT_EXECUTED, SCREENING_PARTIAL, SCREENING_REVIEW_REQUIRED,
    SNAP_OPERATIVA, ScreeningSummary, SourceOutcome, SubjectEnvelope,
)
from .evidence import build_evidence, encadenar_eventos, verificar_cadena
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

    # 5) Cobertura y decisión: DOS cosas distintas (§ 03S.1A-3).
    #    La cobertura se mide contra TODAS las fuentes SOLICITADAS (no solo las
    #    disponibles): una fuente caída deja la cobertura INCOMPLETA aunque el
    #    resto haya respondido.
    _fuentes_disponibles = tuple(sorted(s for s, sn in snapshots.items()
                                       if fuente_disponible(sn)))
    _fuentes_no_disponibles = tuple(sorted(set(snapshots) - set(_fuentes_disponibles)))
    _solicitadas = tuple(d.source_id for d in defs)
    _screeningables = {e.subject_id for e in envelopes if e.screened}
    _esperados = {(sid, src) for sid in _screeningables for src in _solicitadas}
    _cubiertos = {(o.subject_id, o.source_id) for o in outcomes
                  if o.subject_id in _screeningables
                  and o.source_id in _fuentes_disponibles
                  and o.result not in (RESULT_NOT_SCREENED, RESULT_SOURCE_UNAVAILABLE)}
    _cobertura_completa = bool(_esperados) and _cubiertos == _esperados

    # 6) Evidencia: SIEMPRE un registro por outcome sujeto×fuente (§ 03S.1A-2),
    #    con aislamiento POR OUTCOME (§ 03S.1B-8): el fallo de uno NO impide
    #    crear los demás; el fallo se registra en `evidence_errors`.
    _evidencias = []
    _evidence_errors = []
    for env in envelopes:
        for out in [o for o in outcomes if o.subject_id == env.subject_id]:
            try:
                _evidencias.append(build_evidence(env, out))
            except Exception as e:  # noqa: BLE001
                _evidence_errors.append({
                    "subject_id": env.subject_id, "source_id": out.source_id,
                    "error": f"{type(e).__name__}: {str(e)[:160]}"})
    _evidence_error = (_evidence_errors[0]["error"] if _evidence_errors else None)

    # 7) Cadena HMAC: se intenta y se DECLARA su estado (nunca en silencio).
    #    Si faltan envelopes, la cadena NO puede declararse sellada.
    _chain_status = CHAIN_NOT_REQUIRED_DEV
    _chain_error = None
    if encadenar_evidencia:
        try:
            if _evidence_errors:
                raise RuntimeError(
                    f"{len(_evidence_errors)} envelope(s) de evidencia no se "
                    f"pudieron crear: {_evidence_error}")
            _eventos = encadenar_eventos(tuple(e.to_dict() for e in _evidencias), agent_id)
            if _eventos and verificar_cadena(_eventos):
                _chain_status = CHAIN_SEALED
            else:
                _chain_status = CHAIN_FAILED
                _chain_error = "la cadena no devolvió eventos verificables"
        except Exception as e:  # noqa: BLE001
            _chain_status = CHAIN_FAILED
            _chain_error = f"{type(e).__name__}: {str(e)[:160]}"

    status, reason = _estado(envelopes, defs, snapshots, outcomes,
                             cobertura_completa=_cobertura_completa,
                             chain_status=_chain_status, chain_error=_chain_error)

    # Fail-closed de la capa de evidencia en producción: sin cadena sellada NO se
    # puede declarar el screening completo ni "evidencia sellada".
    if _chain_status == CHAIN_FAILED and status == SCREENING_COMPLETE and _es_produccion():
        status = SCREENING_PARTIAL
        reason = (reason + " La evidencia no pudo sellarse (cadena HMAC "
                  f"FAILED): el screening no se declara completo.").strip()

    return ScreeningSummary(
        status=status, executed=bool(_fuentes_disponibles),
        subjects_declared=len(envelopes),
        subjects_screened=sum(1 for e in envelopes if e.screened),
        subjects_not_screened=sum(1 for e in envelopes if not e.screened),
        subjects=tuple(envelopes), outcomes=tuple(outcomes),
        sources=tuple(d.source_id for d in defs),
        sources_available=_fuentes_disponibles,
        sources_unavailable=_fuentes_no_disponibles,
        snapshots=tuple(snapshots[s] for s in sorted(snapshots)),
        review_required_subjects=tuple(sorted(set(revisión))),
        matched_subjects=tuple(sorted(set(coincidentes))),
        reason=reason, executed_at=ejecutado_en, algorithm_version=ALGORITHM_VERSION,
        scope_note=SCOPE_NOTE,
        evidence_records=tuple(e.to_dict() for e in _evidencias),
        evidence_expected_count=len(outcomes),
        evidence_created_count=len(_evidencias),
        evidence_chain_status=_chain_status,
        evidence_errors=tuple(_evidence_errors),
        extra={
            "cobertura": cobertura_declarada([d.source_id for d in defs]),
            "cobertura_completa": _cobertura_completa,
            "coverage_status": ("COVERAGE_COMPLETE" if _cobertura_completa
                                else "COVERAGE_PARTIAL"),
            "gate_pares_sin_consultar": sorted(
                f"{sid}|{src}" for sid, src in (_esperados - _cubiertos)),
            "evidence_error": _evidence_error,
            "evidence_chain_error": _chain_error,
            "refresh_errors": {s: snapshots[s].refresh_error for s in sorted(snapshots)
                               if getattr(snapshots[s], "refresh_error", None)},
            "en_vivo": [s for s in sorted(snapshots)
                        if es_en_vivo(snapshots[s])],
            "desde_snapshot": [s for s in sorted(snapshots) if es_cache(snapshots[s])],
        },
    )


def _es_produccion() -> bool:
    """¿Corre en producción? (fail-closed de la capa de evidencia)."""
    import os
    return bool(os.environ.get("VERCEL")) or \
        (os.environ.get("ARHIAX_ENV") or "").strip().lower() in ("prod", "production")


def _consultar(env: SubjectEnvelope, source_id: str, snap, regs) -> SourceOutcome:
    if not env.screened:
        return SourceOutcome(
            subject_id=env.subject_id, source_id=source_id,
            result=RESULT_NOT_SCREENED, note=env.not_screened_reason or "no screeningado",
            snapshot_id=getattr(snap, "snapshot_id", ""),
            snapshot_sha256=getattr(snap, "sha256", ""),
            snapshot_effective_date=getattr(snap, "effective_date", "") or "",
            parser_version=getattr(snap, "parser_version", "") or "",
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
            parser_version=getattr(snap, "parser_version", "") or "",
            freshness=getattr(snap, "freshness", ""))
    # 03S.1A-5: se consulta el nombre canónico Y cada variante DECLARADA por
    # separado; se agrega el resultado MÁS CONSERVADOR (nunca se fusiona la
    # identidad jurídica por similitud de nombre).
    _nombres = env.nombres_a_consultar or (env.canonical_name,)
    _peor = None
    _motivos: List[str] = []
    _errores: List[str] = []
    for _n in _nombres:
        try:
            _r = matching.consultar(env, regs, nombre=_n)
        except Exception as e:  # noqa: BLE001
            _errores.append(f"error al consultar la variante {_n!r}: {type(e).__name__}")
            continue
        _etiqueta = tuple(_r.reasons)
        if len(_nombres) > 1 and _r.result not in (matching.RESULT_NO_MATCH,):
            _etiqueta = tuple(f"variante declarada {_n!r}: {x}" for x in _r.reasons) \
                or (f"variante declarada {_n!r} sin motivos",)
        if _peor is None:
            _peor, _motivos = _r, list(_etiqueta)
            continue
        # Resultado MÁS CONSERVADOR (el más severo) entre las variantes.
        if _r.result != _peor.result and \
                matching.peor_resultado(_r.result, _peor.result) == _r.result:
            _peor, _motivos = _r, list(_etiqueta)
        else:
            _motivos.extend(x for x in _etiqueta if x not in _motivos)
    _motivos.extend(_errores)
    if _peor is None:
        return SourceOutcome(
            subject_id=env.subject_id, source_id=source_id,
            result=RESULT_REVIEW, note="; ".join(_motivos) or "error en la consulta",
            snapshot_id=snap.snapshot_id, snapshot_sha256=snap.sha256,
            snapshot_effective_date=snap.effective_date or "",
            parser_version=snap.parser_version or "",
            freshness=snap.freshness, review_status="REQUIERE_REVISION")
    return SourceOutcome(
        subject_id=env.subject_id, source_id=source_id, result=_peor.result,
        score=_peor.score, matched_record_ids=_peor.matched_record_ids,
        matching_reasons=tuple(_motivos), snapshot_id=snap.snapshot_id,
        snapshot_sha256=snap.sha256,
        snapshot_effective_date=snap.effective_date or "",
        parser_version=snap.parser_version or "",
        freshness=snap.freshness,
        review_status="REQUIERE_REVISION" if _peor.requiere_revision else "NO_REQUIERE",
        note="; ".join(_motivos) if _motivos else "")


def _estado(envelopes, defs, snapshots, outcomes, *, cobertura_completa: bool = True,
            chain_status: str = "", chain_error: Optional[str] = None) -> Tuple[str, str]:
    """Estado de DECISIÓN + motivo imprimible que declara AMBAS dimensiones.

    03S.1A-3: el motivo debe informar la decisión Y la cobertura (qué fuente
    faltó), nunca solo una de las dos.
    """
    if not defs:
        return SCREENING_NOT_EXECUTED, "no hay fuentes de screening configuradas"
    screeningados = [e for e in envelopes if e.screened]
    if not screeningados:
        return (SCREENING_NOT_EXECUTED,
                "no se identificaron sujetos screeningables en el caso")
    disponibles = [s for s in snapshots if fuente_disponible(snapshots[s])]
    if not disponibles:
        _faltan = ", ".join(sigla(s) for s in sorted(snapshots))
        return (SCREENING_NOT_EXECUTED,
                "ninguna fuente oficial de screening estuvo disponible en esta "
                "ejecución (no consultadas: " + (_faltan or "todas") + ")")

    _revision = [o for o in outcomes if o.result in RESULT_STATES_REVISION]
    _no_disp = sorted({o.source_id for o in outcomes
                       if o.result == RESULT_SOURCE_UNAVAILABLE})
    _no_scr = [o for o in outcomes if o.result == RESULT_NOT_SCREENED]

    # DECISIÓN
    if _revision:
        status = SCREENING_REVIEW_REQUIRED
        _donde = ", ".join(sorted({sigla(o.source_id) for o in _revision}))
        _decision = (f"Existe candidato que requiere revisión humana ({_donde}); "
                     "una coincidencia por nombre no confirma una designación.")
    elif _no_disp or _no_scr or not cobertura_completa:
        status = SCREENING_PARTIAL
        _decision = ""
    else:
        status = SCREENING_COMPLETE
        _decision = ""

    # COBERTURA (se declara SIEMPRE, junto a la decisión)
    if cobertura_completa:
        _cobertura = ("Cobertura completa: " + cobertura_declarada(disponibles) + ".")
    else:
        _faltan_txt = ", ".join(sigla(s) for s in _no_disp) or "sin identificar"
        _cobertura = (f"Cobertura PARCIAL: {_faltan_txt} no estuvo disponible."
                      if _no_disp else
                      "Cobertura PARCIAL: hay sujetos o fuentes sin consulta.")
        if _no_scr:
            _cobertura += f" {len(_no_scr)} consulta(s) de sujeto no screeningado(s)."

    if not _revision:
        _decision = ("Sin coincidencias en las fuentes efectivamente consultadas"
                     + ("" if cobertura_completa else " (no en las no disponibles)") + ".")

    if chain_status == CHAIN_FAILED:
        _cobertura += (" La evidencia no pudo sellarse (cadena HMAC FAILED"
                       + (f": {chain_error}" if chain_error else "") + ").")
    return status, (_decision + " " + _cobertura).strip()


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
                not_screened_reason=x.get("not_screened_reason"),
                declared_name_variants=tuple(x.get("declared_name_variants") or ()),
                identifiers=tuple(x.get("identifiers") or ()))

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
                parser_version=x.get("parser_version", "") or "",
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
                freshness=x.get("freshness", ""), error=x.get("error"),
                refresh_error=x.get("refresh_error"))

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
            scope_note=d.get("scope_note", ""),
            evidence_records=tuple(d.get("evidence_records") or ()),
            evidence_expected_count=int(d.get("evidence_expected_count") or 0),
            evidence_created_count=int(d.get("evidence_created_count") or 0),
            evidence_chain_status=d.get("evidence_chain_status", CHAIN_NOT_REQUIRED_DEV),
            evidence_errors=tuple(d.get("evidence_errors") or ()),
            extra=dict(d.get("extra") or {}))
    except Exception:  # noqa: BLE001
        return None

# -*- coding: utf-8 -*-
"""
ARHIAX RE — Execution receipts (bug H).

La Declaración de Alcance del dictamen ya NO debe afirmar "EJECUTADA EN VIVO"
de forma estática: debe reflejar lo que REALMENTE corrió en esta generación
(estado por capa del geoportal, disponibilidad del SGC volcánico, POI, SARLAFT,
identidad resuelta y versionado). Este módulo compila esos receipts y los
convierte en filas legibles para el renderer.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional, Tuple

from canonical import RESOLUTION_VERIFIED_UNIT

# Estados de capa legibles (alineados con pasto_territorio._estado_capa).
_ESTADO_LEGIBLE = {
    "MATCH_EXACT": "CON COINCIDENCIA (datos del predio)",
    "NO_MATCH": "SIN COINCIDENCIA (consultado, sin dato para el predio)",
    "NULL_VALUE": "RESPONDIO SIN VALOR (atributos vacíos)",
    "NOT_APPLICABLE": "NO APLICA (no se consulta en esta resolución)",
    "SOURCE_UNAVAILABLE": "FUENTE NO DISPONIBLE (sin respuesta)",
    "SOURCE_TIMEOUT": "FUENTE AGOTADA POR TIEMPO",
    "SCHEMA_CHANGED": "ESQUEMA DE LA FUENTE CAMBIADO",
    "NOT_EVALUATED": "NO EVALUADO",
}

_ETIQUETA_CAPA = {
    "tratamientos_urbanisticos": "Tratamientos urbanísticos (POT)",
    "areas_de_actividad": "Áreas de actividad (POT)",
    "riesgos_urbano": "Riesgos urbanos por predio",
    "predios_estratificacion": "Predios/Estratificación (NUPRE)",
    "dpa_barrios_comunas": "Barrios/Comunas (DPA)",
    "tablas_estratificacion": "Tablas de estratificación (estrato/nomenclatura)",
}


def estado_legible(estado: Optional[str]) -> str:
    return _ESTADO_LEGIBLE.get((estado or "").upper(), (estado or "PENDIENTE"))


def build_execution_receipts(
    *,
    ciudad: str,
    predio_real: Optional[Dict[str, Any]],
    volcan: Optional[Dict[str, Any]],
    pois: Optional[Dict[str, Any]],
    titulux: Optional[Dict[str, Any]],
    geo_eval: Optional[Dict[str, Any]],
    canonical_identity: Optional[Dict[str, Any]],
    versionado: Dict[str, Any],
    lat: Optional[float],
    lon: Optional[float],
    ctl_adjuntado: bool,
    catastro_live: Optional[Dict[str, Any]] = None,
    poi_status: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compila los receipts REALES de esta ejecución (sin red, ya resueltos)."""
    capas = (predio_real or {}).get("capas") or {}
    # 03I.1: el MarketContext viaja dentro de la identidad canónica (autoridad única
    # del render); el recibo lee de ahí y no reconstruye valores.
    _mc = (canonical_identity or {}).get("market_context")
    _mc = _mc if isinstance(_mc, dict) else {}
    fuente_gis = ((predio_real or {}).get("fuente") or {}).get("estado")
    # 03D.2A: 'exacto' deriva de la SEMÁNTICA NORMALIZADA de resolución de la
    # identidad canónica, NO de predio_real.disponible (que puede ser PARTIAL /
    # CONTEXT_ONLY / AMBIGUOUS / bbox). Solo VERIFIED_UNIT_IDENTITY es exacto.
    _confianza = (canonical_identity or {}).get("resolution_confidence")
    _exacto = _confianza == RESOLUTION_VERIFIED_UNIT
    _consultado = bool((predio_real and predio_real.get("disponible"))
                       or (catastro_live or {}).get("disponible"))
    _espacial = _consultado and not _exacto
    return {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "ciudad": ciudad,
        "versionado": dict(versionado or {}),
        "ctl_adjuntado": bool(ctl_adjuntado),
        # 03D.2: estado de ejecución catastral ÚNICO (exacto vs espacial) para que
        # los capítulos 06 y 16 no reconstruyan estados divergentes.
        "catastro": {
            "consultado": _exacto or _espacial,
            "exacto": _exacto,
            "espacial": _espacial,
        },
        "identidad": {
            "estado": (canonical_identity or {}).get("estado"),
            "nupre": (canonical_identity or {}).get("nupre"),
            "codigo_catastral": (canonical_identity or {}).get("codigo_catastral"),
            "folio_snr": (canonical_identity or {}).get("folio_snr"),
        },
        "gis": {
            "estado_fuente": fuente_gis,
            "capas": dict(capas),
        },
        "riesgo_volcanico": {
            "disponible": bool((volcan or {}).get("disponible")),
            "nivel": (volcan or {}).get("nivel"),
            # 03I.1 · F8: el ESTADO es la única verdad del capítulo 8.2 (el nivel
            # "NO EVALUADO" ya no se imprime como "amenaza baja").
            "estado": (volcan or {}).get("estado"),
            "cobertura_confirmada": (volcan or {}).get("cobertura_confirmada"),
        },
        # 03I.1 · F: la metodología que produjo la tasa de mercado (id + versión
        # del artefacto real + sha256) viaja al recibo, igual que en el manifest.
        "mercado": {
            "ready": _mc.get("ready"),
            "metodologia_id": _mc.get("market_methodology_id"),
            "metodologia_version": _mc.get("market_methodology_version"),
            "metodologia_sha256": _mc.get("market_methodology_sha256"),
            "sector": (_mc.get("sector_metodologico") or {}).get("matched_sector"),
            "match_type": (_mc.get("sector_metodologico") or {}).get("match_type"),
            "blockers": list(_mc.get("blockers") or []),
        },
        # 03I.1 · F4: procedencia del estrato (espacial vs manzana del predial).
        "contexto_urbano": {
            "estrato": (_mc.get("estrato") or {}).get("value"),
            "estrato_status": (_mc.get("estrato") or {}).get("status"),
            "estrato_origen": (_mc.get("official_urban_context") or {}).get("estrato_origen"),
            "urban_source_mode": (_mc.get("urban_source_summary") or {}).get("source_mode"),
        },
        "geo_evaluado": bool((geo_eval or {}).get("evaluado")),
        # 03F.1: receipt por categoría (status + count). El status respeta la
        # metadata de ejecución (AVAILABLE / NO_MATCH / SOURCE_UNAVAILABLE) si
        # está disponible; sin ella degrada a NO_MATCH (lista vacía).
        "poi": {
            "disponible": bool(pois and any(pois.get(c) for c in pois)),
            "categorias": {
                c: {"status": ((poi_status or {}).get(c)
                               or ("AVAILABLE" if (pois or {}).get(c) else "NO_MATCH")),
                    "count": len((pois or {}).get(c) or [])}
                for c in sorted(set((pois or {}).keys()) | set((poi_status or {}).keys()))
            },
        },
        # 03S.1: el screening se reporta desde el ScreeningSummary único (misma
        # verdad que los capítulos 05/09/16): estado canónico, sujetos, fuentes y
        # frescura REAL de cada snapshot.
        "sarlaft": _screening_receipt(titulux),
        # 03I.2B §N: la geocodificación viaja con PROCEDENCIA (fuente, capa, feature,
        # método y alcance). Antes solo viajaban lat/lon: el recibo no permitía saber
        # si el punto era geometría oficial del predio o un centroide de referencia.
        "geocodificacion": {
            "lat": lat, "lon": lon,
            "coordinate_source": _mc.get("coordinate_source"),
            "coordinate_source_verified": _mc.get("coordinate_source_verified"),
            "provenance": _mc.get("coordinate_provenance") or {},
            "source_system": (_mc.get("coordinate_provenance") or {}).get("source_system"),
            "source_layer": (_mc.get("coordinate_provenance") or {}).get("layer"),
            "source_feature_id": (_mc.get("coordinate_provenance") or {}).get("feature_id"),
            "resolution_method": (_mc.get("coordinate_provenance") or {}).get("resolution_method"),
            "coordinate_scope": _mc.get("coordinate_scope"),
            "official_predio_rejected_reason": _mc.get("official_predio_rejected_reason"),
        },
    }


def _screening_receipt(titulux: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Receipt de screening derivado del resumen único (03S.1)."""
    titulux = titulux or {}
    _sum = titulux.get("screening_summary") or {}
    if not _sum:
        return {
            "status": "SCREENING_NOT_EXECUTED",
            "etiqueta": "NO EJECUTADO",
            "completo": bool(titulux.get("screening_completo")),
            "agregado": titulux.get("screening_agregado"),
            "fuentes_pendientes": list(titulux.get("fuentes_pendientes") or []),
            "sujetos_declarados": None, "sujetos_screeningados": None,
            "fuentes": [], "reason": "", "ejecutado": False,
        }
    _snaps = {s.get("source_id"): s for s in (_sum.get("snapshots") or [])}
    # 03I.2A §13: el recibo lleva la MISMA fila de sujeto que los capítulos 05 y 09
    # (nombre, tipo, etiqueta, documento y subject_id idénticos en los tres).
    _sujetos_detalle = []
    try:
        from sanctions.subjects import fila_sujeto_dictamen
        for _s in (_sum.get("subjects") or []):
            if isinstance(_s, dict):
                _sujetos_detalle.append({
                    "subject_id": _s.get("subject_id"),
                    "canonical_name": _s.get("canonical_name"),
                    "person_type": _s.get("person_type"),
                    "person_type_label": _s.get("person_type_label"),
                    "document": _s.get("document") or _s.get("documento"),
                })
            else:
                _sujetos_detalle.append(fila_sujeto_dictamen(_s))
    except Exception:  # noqa: BLE001 — el recibo nunca debe tumbar el dictamen
        _sujetos_detalle = []
    return {
        "status": _sum.get("status"),
        "sujetos_detalle": _sujetos_detalle,
        "etiqueta": {
            "SCREENING_COMPLETE": "COMPLETO",
            "SCREENING_PARTIAL": "PARCIAL",
            "SCREENING_REVIEW_REQUIRED": "REQUIERE REVISIÓN",
            "SCREENING_NOT_EXECUTED": "NO EJECUTADO",
        }.get(_sum.get("status"), "NO EJECUTADO"),
        "completo": _sum.get("status") == "SCREENING_COMPLETE",
        "agregado": titulux.get("screening_agregado"),
        "fuentes_pendientes": list(_sum.get("sources_unavailable") or []),
        "sujetos_declarados": _sum.get("subjects_declared"),
        "sujetos_screeningados": _sum.get("subjects_screened"),
        "sujetos_no_screeningados": _sum.get("subjects_not_screened"),
        "revision_requerida": list(_sum.get("review_required_subjects") or []),
        "coincidencias": list(_sum.get("matched_subjects") or []),
        "reason": _sum.get("reason") or "",
        "ejecutado": bool(_sum.get("executed")),
        "algorithm_version": _sum.get("algorithm_version"),
        # § 03S.1A-2/3: decisión y cobertura son dimensiones distintas, y la
        # evidencia no puede desaparecer en silencio.
        "decision_status": _sum.get("decision_status") or _sum.get("status"),
        "coverage_status": (_sum.get("coverage_status")
                            or ("COVERAGE_COMPLETE" if _sum.get("coverage_complete")
                                else "COVERAGE_PARTIAL")),
        "coverage_complete": bool(_sum.get("coverage_complete")),
        "evidence_expected": _sum.get("evidence_expected_count"),
        "evidence_created": _sum.get("evidence_created_count"),
        "evidence_chain_status": _sum.get("evidence_chain_status"),
        "evidence_errors": list(_sum.get("evidence_errors") or []),
        "evidence_sealed": bool(_sum.get("evidence_sealed")
                                if _sum.get("evidence_sealed") is not None
                                else _sum.get("evidence_chain_status") == "SEALED"),
        "evidence_reproducible": bool(_sum.get("evidence_reproducible")),
        # 03S.1C: identidad de ejecución (versiones que produjeron el resultado).
        "matcher_version": _sum.get("algorithm_version"),
        "parser_versions": {s.get("source_id"): s.get("parser_version")
                            for s in (_sum.get("snapshots") or [])},
        "fuentes": [{
            "source_id": sid, "sigla": sid,
            "freshness": (_snaps.get(sid) or {}).get("freshness"),
            "effective_date": (_snaps.get(sid) or {}).get("effective_date"),
            "sha256": (_snaps.get(sid) or {}).get("sha256"),
            "record_count": (_snaps.get(sid) or {}).get("record_count"),
            "parser_version": (_snaps.get(sid) or {}).get("parser_version"),
        } for sid in (_sum.get("sources") or [])],
    }


def receipt_rows(receipts: Optional[Dict[str, Any]]) -> List[Tuple[str, str]]:
    """Filas (label, valor) de la traza técnica de ejecución para el renderer."""
    if not receipts:
        return [("Ejecución", "Sin trazabilidad disponible")]
    filas: List[Tuple[str, str]] = []
    filas.append(("Generado", receipts.get("generated_at") or "N/D"))
    ver = receipts.get("versionado") or {}
    filas.append(("Versión ARHIAX RE", ver.get("ARHIAX_RE_VERSION") or "N/D"))
    filas.append(("Commit (git SHA)", (ver.get("GIT_COMMIT_SHA") or "desconocido")[:12]))
    filas.append(("Motor dictus / GIS / Titulux / reglas",
                  " / ".join([
                      ver.get("DICTUS_ENGINE_VERSION") or "-",
                      ver.get("GIS_ADAPTER_VERSION") or "-",
                      ver.get("TITULUX_VERSION") or "-",
                      ver.get("RULESET_VERSION") or "-"])))
    filas.append(("CTL adjuntado", "SÍ" if receipts.get("ctl_adjuntado") else "NO"))
    ident = receipts.get("identidad") or {}
    _detalle_ident = [ident.get("estado") or "NO_RECORD"]
    if ident.get("nupre"):
        _detalle_ident.append(f"NUPRE {ident['nupre']}")
    if ident.get("codigo_catastral"):
        _detalle_ident.append(f"Código catastral {ident['codigo_catastral']}")
    filas.append(("Identidad predial", " · ".join(_detalle_ident)))
    gis = receipts.get("gis") or {}
    if gis.get("estado_fuente"):
        filas.append(("Geoportal (fuente)", gis["estado_fuente"]))
    for capa, det in (gis.get("capas") or {}).items():
        etiqueta = _ETIQUETA_CAPA.get(capa, capa)
        estado = det.get("estado") if isinstance(det, dict) else det
        filas.append((f"  · Capa {etiqueta}", estado_legible(estado)))
    vol = receipts.get("riesgo_volcanico") or {}
    filas.append(("Riesgo volcánico (SGC)",
                  ("CONSULTADO · " + (vol.get("nivel") or "N/D")) if vol.get("disponible")
                  else "NO DISPONIBLE / PENDIENTE"))
    poi = receipts.get("poi") or {}
    # 03F.1: mostrar el estado REAL por categoría (NO presentar NO_MATCH como
    # CONSULTADO CON RESULTADO, ni hacer join sobre las claves del dict).
    _poi_cats = poi.get("categorias") or {}
    _poi_partes = []
    for _c in sorted(_poi_cats.keys()):
        _det = _poi_cats[_c] if isinstance(_poi_cats[_c], dict) else {"status": str(_poi_cats[_c])}
        _st = _det.get("status")
        _cnt = _det.get("count", 0)
        if _st == "AVAILABLE":
            _poi_partes.append(f"{_c} AVAILABLE ({_cnt})")
        elif _st == "NO_MATCH":
            _poi_partes.append(f"{_c} NO_MATCH")
        elif _st == "SOURCE_UNAVAILABLE":
            _poi_partes.append(f"{_c} SOURCE_UNAVAILABLE")
        else:
            _poi_partes.append(f"{_c} {_st or 'NOT_EVALUATED'}")
    if poi.get("disponible"):
        _poi_txt = "CONSULTADO · " + "; ".join(_poi_partes)
    else:
        _poi_txt = "NO DISPONIBLE" + ((" · " + "; ".join(_poi_partes)) if _poi_partes else "")
    filas.append(("Equipamiento urbano (POI)", _poi_txt))
    sag = receipts.get("sarlaft") or {}
    if sag.get("ejecutado"):
        _detalle_sag = [
            "{} sujeto(s) screeningado(s) de {} declarado(s)".format(
                sag.get("sujetos_screeningados"), sag.get("sujetos_declarados")),
            "cobertura: " + str(sag.get("coverage_status") or "—"),
            "evidencia: {}/{} envelopes · cadena {}".format(
                sag.get("evidence_created"), sag.get("evidence_expected"),
                sag.get("evidence_chain_status") or "—"),
        ]
        if sag.get("fuentes_pendientes"):
            _detalle_sag.append("no disponibles: "
                                + ", ".join(sag.get("fuentes_pendientes") or []))
        filas.append(("Screening de contrapartes",
                      "{} · {}".format(sag.get("etiqueta") or "—",
                                       " · ".join(x for x in _detalle_sag if x))))
        # 03I.2A §13: misma fila de sujeto que 05 y 09 (nombre | tipo | documento |
        # subject_id). Es el valor que el dictamen afirma sobre cada contraparte.
        for _s in (sag.get("sujetos_detalle") or []):
            filas.append((f"  · Contraparte {_s.get('subject_id') or '—'}",
                          "{} | {} | {} | {}".format(
                              _s.get("canonical_name") or "—",
                              _s.get("person_type_label") or "No determinado",
                              _s.get("document") or "—",
                              _s.get("subject_id") or "—")))
    else:
        filas.append(("Screening de contrapartes",
                      "NO EJECUTADO · " + (sag.get("reason") or "sin fuentes disponibles")))
    # 03I.2B §N: procedencia de la COORDENADA que abrió el contexto de mercado.
    # Sin esta fila, «OFFICIAL_PREDIO» no sería auditable en el dictamen impreso.
    geo = receipts.get("geocodificacion") or {}
    if geo.get("lat") is not None and geo.get("lon") is not None:
        _prov = geo.get("provenance") or {}
        _det_geo = [f"{geo.get('coordinate_source') or 'UNRESOLVED'}"
                    + (" (verificada)" if geo.get("coordinate_source_verified") else "")]
        if _prov.get("source_system"):
            _det_geo.append(f"fuente {_prov['source_system']}")
        if _prov.get("layer"):
            _det_geo.append(f"capa {_prov['layer']}")
        if _prov.get("feature_id"):
            _det_geo.append(f"feature {_prov['feature_id']}")
        if _prov.get("resolution_method"):
            _det_geo.append(f"método {_prov['resolution_method']}")
        if geo.get("coordinate_scope"):
            _det_geo.append(str(geo["coordinate_scope"]))
        if geo.get("official_predio_rejected_reason"):
            _det_geo.append("geometría del predio NO promovida: "
                            + str(geo["official_predio_rejected_reason"]))
        filas.append(("Ubicación de mercado (coordenada)", " · ".join(_det_geo)))
    return filas

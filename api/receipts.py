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
) -> Dict[str, Any]:
    """Compila los receipts REALES de esta ejecución (sin red, ya resueltos)."""
    capas = (predio_real or {}).get("capas") or {}
    fuente_gis = ((predio_real or {}).get("fuente") or {}).get("estado")
    return {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "ciudad": ciudad,
        "versionado": dict(versionado or {}),
        "ctl_adjuntado": bool(ctl_adjuntado),
        "identidad": {
            "estado": (canonical_identity or {}).get("estado"),
            "nupre": (canonical_identity or {}).get("nupre"),
            "folio_snr": (canonical_identity or {}).get("folio_snr"),
        },
        "gis": {
            "estado_fuente": fuente_gis,
            "capas": dict(capas),
        },
        "riesgo_volcanico": {
            "disponible": bool((volcan or {}).get("disponible")),
            "nivel": (volcan or {}).get("nivel"),
        },
        "geo_evaluado": bool((geo_eval or {}).get("evaluado")),
        "poi": {
            "disponible": bool(pois and any(pois.get(c) for c in pois)),
            "categorias": sorted([c for c in (pois or {}) if pois.get(c)]),
        },
        "sarlaft": {
            "completo": (titulux or {}).get("screening_completo"),
            "agregado": (titulux or {}).get("screening_agregado"),
            "fuentes_pendientes": (titulux or {}).get("fuentes_pendientes") or [],
        },
        "geocodificacion": {"lat": lat, "lon": lon},
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
    filas.append(("Identidad predial", f"{ident.get('estado') or 'NO_RECORD'}"
                  + (f" · NUPRE {ident.get('nupre')}" if ident.get('nupre') else "")))
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
    filas.append(("Equipamiento urbano (POI)",
                  ("CONSULTADO (" + ", ".join(poi.get("categorias") or []) + ")")
                  if poi.get("disponible") else "NO DISPONIBLE"))
    sag = receipts.get("sarlaft") or {}
    filas.append(("Screening SARLAFT",
                  ("COMPLETO · " + (sag.get("agregado") or "")) if sag.get("completo")
                  else ("INCOMPLETO · pendientes: " + ", ".join(sag.get("fuentes_pendientes") or ["?"]))))
    return filas

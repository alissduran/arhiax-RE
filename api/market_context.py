# -*- coding: utf-8 -*-
"""
ARHIAX RE — Market Context (03H).

Identidad y contexto de mercado son DOS problemas distintos:

    WHAT PROPERTY?      → identity_verified (resuelto por otra fuente)
    WHAT MARKET CONTEXT? → market_context_ready (este módulo)

La valoración solo se habilita cuando AMBOS son suficientes:

    valuation_authorized = identity_authorized AND market_context_authorized

Regla dura: NUNCA fallback silencioso.
  - estrato faltante NO se sustituye por 4.
  - sector metodológico sin match NO cae a "fallback por estrato" sin marcarlo;
    para valoración de alta confianza ese fallback NO es MARKET_CONTEXT_READY.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

# ── Estados de campo ───────────────────────────────────────────────────────────
STATUS_VERIFIED_OFFICIAL = "VERIFIED_OFFICIAL"
STATUS_VERIFIED_GEOGRAPHIC = "VERIFIED_GEOGRAPHIC"
STATUS_VERIFIED_REGISTRAL = "VERIFIED_REGISTRAL"
STATUS_VERIFIED_CATASTRAL = "VERIFIED_CATASTRAL"
STATUS_UNRESOLVED = "UNRESOLVED"
STATUS_SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
STATUS_CONFLICT = "CONFLICT"

# ── Match de sector metodológico ──────────────────────────────────────────────
MATCH_EXACT = "EXACT"
MATCH_NORMALIZED_EXACT = "NORMALIZED_EXACT"
MATCH_ALIAS = "ALIAS"
MATCH_NO_MATCH = "NO_MATCH"
MATCH_AMBIGUOUS = "AMBIGUOUS"

# El fallback genérico por estrato NO es una metodología específica de sector.
MATCH_GENERIC_ESTRATO_FALLBACK = "GENERIC_ESTRATO_FALLBACK"

_YAML_PATH = (
    Path(__file__).resolve().parent.parent
    / "motor_tma_lonja_baq_v1.0" / "motor_tma_lonja_baq_v1.0"
    / "lonja_layer" / "lonja_baq_metodologia.yaml"
)


def _load_lonja(yml_path: Optional[Path] = None) -> Dict[str, Any]:
    p = Path(yml_path) if yml_path else _YAML_PATH
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


def lonja_metadata(yml: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Metadata de metodología (versión + vigencia) desde el YAML Lonja."""
    y = yml or _load_lonja()
    decl = y.get("declaracion") or {}
    cons = y.get("regla_consolidacion") or {}
    return {
        "entidad": decl.get("entidad"),
        "vigencia_desde": decl.get("vigencia_desde"),
        "vigencia_hasta": decl.get("vigencia_hasta"),
        "version": cons.get("version") or "0.1",
    }


def resolve_market_sector(barrio: Optional[str],
                          yml_path: Optional[Path] = None) -> Dict[str, Any]:
    """MarketSectorResolution: resuelve el sector metodológico de la Lonja por barrio.

    Estados: EXACT / NORMALIZED_EXACT / ALIAS / NO_MATCH / AMBIGUOUS.
    Lee `valor_suelo_por_sector` del YAML. No usa fuzzy semántico automático.
    """
    y = _load_lonja(yml_path)
    meta = lonja_metadata(y)
    sectores = y.get("valor_suelo_por_sector") or {}
    barrio_clean = str(barrio or "").strip()

    base = {
        "input_barrio": barrio_clean or None,
        "matched_sector": None,
        "match_type": MATCH_NO_MATCH,
        "methodology_version": meta.get("version"),
        "methodology_entity": meta.get("entidad"),
        "vigencia_desde": meta.get("vigencia_desde"),
        "value_m2": None,
        "source": None,
        "source_date": None,
        "rango_min_m2": None,
        "rango_max_m2": None,
        "provenance": {
            "methodology_file": _YAML_PATH.name,
            "methodology_version": meta.get("version"),
            "methodology_entity": meta.get("entidad"),
        },
    }

    if not barrio_clean:
        return base

    barrio_key = barrio_clean.replace(" ", "_").strip().title()
    matched = []
    for k in sectores:
        if k == barrio_clean or k.lower() == barrio_clean.lower():
            matched.append(k)
    if not matched:
        # NORMALIZED_EXACT: coincidencia por clave normalizada (espacios→guion)
        for k in sectores:
            if k.lower() == barrio_key.lower():
                matched.append(("normalized", k))
    if not matched and len(sectores) == 1:
        # No hay alias definido: sin match documental.
        return base

    if not matched:
        return base

    if len(matched) > 1:
        base["match_type"] = MATCH_AMBIGUOUS
        base["candidates"] = [m[1] if isinstance(m, tuple) else m for m in matched]
        return base

    m = matched[0]
    normalized = isinstance(m, tuple)
    key = m[1] if normalized else m
    sector = sectores[key]
    base.update({
        "matched_sector": key,
        "match_type": MATCH_NORMALIZED_EXACT if normalized else MATCH_EXACT,
        "value_m2": sector.get("valor_central_m2"),
        "source": sector.get("fuente"),
        "source_date": sector.get("vigencia"),
        "rango_min_m2": sector.get("rango_min_m2"),
        "rango_max_m2": sector.get("rango_max_m2"),
    })
    base["provenance"]["sector"] = key
    return base


def _field(value, status, source=None) -> Dict[str, Any]:
    return {"value": value, "status": status, "source": source}


def build_market_context(*, identity_verified: bool,
                         barrio: Optional[str], barrio_status: str,
                         estrato, estrato_status: str,
                         tipologia: Optional[str], tipologia_status: str,
                         uso: Optional[str] = None, uso_status: str = STATUS_UNRESOLVED,
                         sector_resolution: Optional[Dict[str, Any]] = None,
                         market_rate_source: Optional[str] = None,
                         coordinates: Optional[Dict[str, Any]] = None,
                         geocoder_source: Optional[str] = None,
                         geocoder_confidence: Optional[str] = None) -> Dict[str, Any]:
    """Construye el MarketContext (puro: recibe fuentes ya resueltas).

    No inventa valores: cada campo conserva value/status/source.
    `ready` se evalúa por confianza (criterio mínimo 03H), no por "existe string".
    """
    sector = sector_resolution or {}
    match_type = sector.get("match_type") or MATCH_NO_MATCH
    _rate_source = market_rate_source
    if market_rate_source is None and match_type not in (MATCH_NO_MATCH, MATCH_AMBIGUOUS):
        _rate_source = sector.get("source")

    mc = {
        "identity_verified": bool(identity_verified),
        "barrio": _field(barrio, barrio_status, "official POT / Alcaldía" if barrio_status == STATUS_VERIFIED_OFFICIAL else None),
        "estrato": _field(estrato, estrato_status, "estratificación oficial" if estrato_status == STATUS_VERIFIED_OFFICIAL else None),
        "tipologia": _field(tipologia, tipologia_status, "CTL + registro oficial" if tipologia_status == STATUS_VERIFIED_REGISTRAL else None),
        "uso": _field(uso, uso_status, None),
        "sector_metodologico": sector,
        "market_rate_source": _rate_source,
        "coordinates": coordinates or {},
        "geocoder_source": geocoder_source,
        "geocoder_confidence": geocoder_confidence,
        "provenance": {
            "market_rate_source": _rate_source,
            "methodology_version": sector.get("methodology_version"),
            "methodology_entity": sector.get("methodology_entity"),
        },
        "ready": False,
        "blockers": [],
    }
    mc["ready"], mc["blockers"] = _evaluate_ready(mc)
    return mc


def _evaluate_ready(mc: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Criterio mínimo 03H para PH residencial (alta confianza)."""
    blockers: List[str] = []

    if mc.get("identity_verified") is not True:
        blockers.append("identity_verified != True")

    barrio_st = (mc.get("barrio") or {}).get("status")
    if barrio_st not in (STATUS_VERIFIED_OFFICIAL, STATUS_VERIFIED_GEOGRAPHIC):
        blockers.append("barrio no verificado (requiere VERIFIED_OFFICIAL/GEOGRAPHIC)")

    estrato_st = (mc.get("estrato") or {}).get("status")
    if estrato_st != STATUS_VERIFIED_OFFICIAL:
        blockers.append("estrato no verificado (requiere VERIFIED_OFFICIAL)")

    tipologia_st = (mc.get("tipologia") or {}).get("status")
    if tipologia_st not in (STATUS_VERIFIED_REGISTRAL, STATUS_VERIFIED_CATASTRAL):
        blockers.append("tipología no verificada (requiere VERIFIED_REGISTRAL/CATASTRAL)")

    sector = mc.get("sector_metodologico") or {}
    match_type = sector.get("match_type")
    if match_type not in (MATCH_EXACT, MATCH_NORMALIZED_EXACT, MATCH_ALIAS):
        blockers.append(f"sector metodológico no resuelto (match_type={match_type or 'NO_MATCH'})")

    if mc.get("market_rate_source") is None:
        blockers.append("market_rate_source ausente (sin tasa de mercado autorizada)")

    # 03H.1: la tasa debe existir y ser > 0.
    _v = sector.get("value_m2")
    if _v is None or _v <= 0:
        blockers.append("market rate value missing/invalid")

    return (not blockers), blockers


def market_context_ready(mc: Dict[str, Any]) -> bool:
    return bool((mc or {}).get("ready"))


def market_context_authorized(mc: Dict[str, Any]) -> bool:
    """Autorización de contexto de mercado: ready (confianza) y tasa autorizada."""
    if not market_context_ready(mc):
        return False
    # La tasa NO puede ser un fallback genérico por estrato.
    sector = (mc or {}).get("sector_metodologico") or {}
    if sector.get("match_type") == MATCH_GENERIC_ESTRATO_FALLBACK:
        return False
    return (mc or {}).get("market_rate_source") is not None


def market_context_blockers(mc: Dict[str, Any]) -> List[str]:
    return list((mc or {}).get("blockers") or [])


# ── Categorías de fuente de coordenadas (03H.1) ───────────────────────────────
# Solo las autorizadas pueden alimentar el gate de contexto.
COORD_OFFICIAL_PREDIO = "OFFICIAL_PREDIO"
COORD_OFFICIAL_ADDRESS_GEOCODE = "OFFICIAL_ADDRESS_GEOCODE"
COORD_FORM_ADDRESS_GEOCODE = "FORM_ADDRESS_GEOCODE"
COORD_DB_COORDINATES = "DB_COORDINATES"
COORD_BARRIO_DEMO = "BARRIO_DEMO"
COORD_CITY_CENTROID = "CITY_CENTROID"

# Fuentes NO autorizadas para VERIFIED_OFFICIAL / VERIFIED_GEOGRAPHIC.
_COORD_SOURCES_NO_VERIFIED = {COORD_BARRIO_DEMO, COORD_CITY_CENTROID, COORD_DB_COORDINATES}


def resolve_market_location(*, canonical_identity: Optional[Dict[str, Any]],
                            predio_real: Optional[Dict[str, Any]],
                            lat_geo, lon_geo,
                            db_lat, db_lon, db_direccion: Optional[str],
                            barrio: str, es_bogota: bool, es_medellin: bool,
                            es_pasto: bool, ciudad: str) -> Dict[str, Any]:
    """03H.1: resuelve la ubicación de MERCADO (no identidad) con provenance.

    La geocodificación ubica el edificio/contexto; NO demuestra identidad predial.
    Devuelve authoritative_address/address_source/lat/lon/geocoder_source/
    geocoder_confidence/coordinate_source.
    """
    authoritative_address = None
    address_source = None
    # Dirección de mayor autoridad: registro oficial de adopción (03H.1).
    cid = canonical_identity or {}
    if cid.get("identity_source") == "OFFICIAL_ADOPTION_REGISTRY":
        reg = cid.get("adopcion_registro") or {}
        if reg.get("direccion"):
            authoritative_address = reg["direccion"]
            address_source = "OFFICIAL_ADOPTION_REGISTRY"

    lat = lon = None
    coordinate_source = None
    geocoder_source = None
    geocoder_confidence = None

    if predio_real and predio_real.get("lat") is not None and predio_real.get("lon") is not None:
        lat, lon = predio_real["lat"], predio_real["lon"]
        coordinate_source = COORD_OFFICIAL_PREDIO
    elif lat_geo is not None and lon_geo is not None:
        lat, lon = lat_geo, lon_geo
        coordinate_source = (COORD_OFFICIAL_ADDRESS_GEOCODE if authoritative_address
                             else COORD_FORM_ADDRESS_GEOCODE)
    elif db_lat or db_lon:
        lat, lon = db_lat, db_lon
        coordinate_source = COORD_DB_COORDINATES

    if not lat or not lon:
        # Geocodificar la dirección BASE (sin unidad PH si el geocoder no la reconoce).
        _dir_geo = authoritative_address or db_direccion or ""
        if _dir_geo:
            try:
                from unidad_inmobiliaria import extraer_unidad
                _u = extraer_unidad(_dir_geo)
                _base = _u.get("direccion_base") or _dir_geo
            except Exception:
                _base = _dir_geo
        else:
            _base = ""
        try:
            from geocoder import geocodificar_direccion
            if _base and _base.lower() not in ("pendiente", ""):
                lat, lon = geocodificar_direccion(_base, ciudad=ciudad)
                geocoder_source = "NOMINATIM/OSM"
                coordinate_source = (COORD_OFFICIAL_ADDRESS_GEOCODE if authoritative_address
                                     else COORD_FORM_ADDRESS_GEOCODE)
            else:
                raise ValueError("sin direccion valida")
        except Exception:
            _bl = (barrio or "").lower().strip()
            if _bl == "miramar":
                lat, lon = (10.9870, -74.8115)
                coordinate_source = COORD_BARRIO_DEMO
            elif _bl in ("el recreo", "recreo"):
                lat, lon = (10.9838, -74.7998)
                coordinate_source = COORD_BARRIO_DEMO
            elif es_bogota:
                lat, lon = (4.7110, -74.0721)
                coordinate_source = COORD_CITY_CENTROID
            elif es_medellin:
                lat, lon = (6.2442, -75.5812)
                coordinate_source = COORD_CITY_CENTROID
            elif es_pasto:
                lat, lon = (1.2136, -77.2811)
                coordinate_source = COORD_CITY_CENTROID
            else:
                lat, lon = (10.9685, -74.7813)
                coordinate_source = COORD_CITY_CENTROID

    return {
        "authoritative_address": authoritative_address,
        "address_source": address_source,
        "lat": lat, "lon": lon,
        "geocoder_source": geocoder_source,
        "geocoder_confidence": geocoder_confidence,
        "coordinate_source": coordinate_source,
    }


def coordinate_source_verified(coordinate_source: Optional[str]) -> bool:
    """True solo para fuentes de coordenadas autorizadas (no demo/centroide)."""
    return coordinate_source not in _COORD_SOURCES_NO_VERIFIED

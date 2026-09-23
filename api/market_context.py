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

import math
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
        "autor": cons.get("autor"),
    }


# ── Identidad metodológica del mercado (03I.1 · F) ────────────────────────────
# Una tasa autorizable NO puede viajar con `methodology_version = null`: el
# dictamen debe poder citar QUÉ artefacto metodológico la produjo y con qué
# versión. La versión NO se inventa retrospectivamente: se deriva del artefacto
# real (`regla_consolidacion.version` del YAML de la Lonja) y se sella con el
# sha256 del archivo leído.
METHODOLOGY_ID = "lonja_baq_metodologia"


def market_methodology(yml_path: Optional[Path] = None) -> Dict[str, Any]:
    """Identidad + versión REAL del artefacto metodológico de mercado."""
    import hashlib
    p = Path(yml_path) if yml_path else _YAML_PATH
    try:
        sha = hashlib.sha256(p.read_bytes()).hexdigest()
    except Exception:
        sha = None
    meta = lonja_metadata(_load_lonja(p) if p.exists() else None)
    return {
        "id": METHODOLOGY_ID,
        "version": meta.get("version"),
        "entity": meta.get("entidad"),
        "autor": meta.get("autor"),
        "vigencia_desde": meta.get("vigencia_desde"),
        "vigencia_hasta": meta.get("vigencia_hasta"),
        "file": p.name,
        "sha256": sha,
        "ruta": str(p),
    }


def resolve_market_sector(barrio: Optional[str],
                          yml_path: Optional[Path] = None) -> Dict[str, Any]:
    """MarketSectorResolution: resuelve el sector metodológico de la Lonja por barrio.

    Estados: EXACT / NORMALIZED_EXACT / ALIAS / NO_MATCH / AMBIGUOUS.
    Lee `valor_suelo_por_sector` del YAML. No usa fuzzy semántico automático.
    """
    y = _load_lonja(yml_path)
    meta = lonja_metadata(y)
    _met = market_methodology(yml_path)
    sectores = y.get("valor_suelo_por_sector") or {}
    barrio_clean = str(barrio or "").strip()

    base = {
        "input_barrio": barrio_clean or None,
        "matched_sector": None,
        "match_type": MATCH_NO_MATCH,
        "methodology_version": meta.get("version"),
        "market_methodology_id": _met.get("id"),
        "market_methodology_version": _met.get("version"),
        "market_methodology_sha256": _met.get("sha256"),
        "market_methodology_file": _met.get("file"),
        "methodology_entity": meta.get("entidad"),
        "vigencia_desde": meta.get("vigencia_desde"),
        "value_m2": None,
        "source": None,
        "source_date": None,
        "rango_min_m2": None,
        "rango_max_m2": None,
        "provenance": {
            "methodology_file": _met.get("file") or _YAML_PATH.name,
            "methodology_version": meta.get("version"),
            "methodology_id": _met.get("id"),
            "methodology_sha256": _met.get("sha256"),
            "methodology_entity": meta.get("entidad"),
            "artifact_autor": _met.get("autor"),
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
        # 03I.1 · F: la metodología que produjo la tasa viaja hasta el manifest y el
        # receipt (antes quedaba en None y una tasa autorizable salía sin versión).
        "market_methodology_id": sector.get("market_methodology_id"),
        "market_methodology_version": sector.get("market_methodology_version"),
        "market_methodology_sha256": sector.get("market_methodology_sha256"),
        "market_methodology_file": sector.get("market_methodology_file"),
        "coordinates": coordinates or {},
        "geocoder_source": geocoder_source,
        "geocoder_confidence": geocoder_confidence,
        "provenance": {
            "market_rate_source": _rate_source,
            "methodology_version": sector.get("methodology_version"),
            "market_methodology_id": sector.get("market_methodology_id"),
            "market_methodology_version": sector.get("market_methodology_version"),
            "market_methodology_sha256": sector.get("market_methodology_sha256"),
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

    # 03I.1 · F: una tasa autorizable no puede viajar sin identidad metodológica
    # (id + versión del artefacto real). Sin versión no hay trazabilidad.
    if match_type in (MATCH_EXACT, MATCH_NORMALIZED_EXACT, MATCH_ALIAS):
        if not mc.get("market_methodology_id") or not mc.get("market_methodology_version"):
            blockers.append("metodología de mercado sin id/versión trazable "
                            "(market_methodology_version ausente)")

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


# ── Categorías de fuente de coordenadas (03H.1 / 03H.1A) ──────────────────────
# ALLOWLIST explícita: SOLO estas fuentes pueden alimentar el contexto oficial.
COORD_OFFICIAL_PREDIO = "OFFICIAL_PREDIO"
COORD_OFFICIAL_ADDRESS_GEOCODE = "OFFICIAL_ADOPTION_ADDRESS_GEOCODE"
COORD_CTL_ADDRESS_GEOCODE = "CTL_ADDRESS_GEOCODE"
# NO autorizadas (nunca abren el gate de contexto):
COORD_FORM_ADDRESS_GEOCODE = "FORM_ADDRESS_GEOCODE"
COORD_DB_COORDINATES = "DB_COORDINATES"
COORD_BARRIO_DEMO = "BARRIO_DEMO"
COORD_CITY_CENTROID = "CITY_CENTROID"
COORD_UNRESOLVED = "UNRESOLVED"

_COORD_SOURCES_VERIFIED = frozenset({
    COORD_OFFICIAL_PREDIO,
    COORD_OFFICIAL_ADDRESS_GEOCODE,
    COORD_CTL_ADDRESS_GEOCODE,
})


def coordinate_source_verified(coordinate_source: Optional[str]) -> bool:
    """True SOLO para fuentes de coordenadas en la allowlist.

    03H.1A: `None` y `"UNRESOLVED"` NO son autorizadas (antes se colaban como
    verificadas por estar fuera de la lista negra).
    """
    return coordinate_source in _COORD_SOURCES_VERIFIED


# ── 03I.2B · H-1: elegibilidad ESTRICTA de la geometría oficial del predio ────
# Antes, `resolve_market_location` promovía CUALQUIER `predio_real["lat"]` a
# `OFFICIAL_PREDIO`: un «hint» geocodificado (o un punto referencial por cercanía)
# entraba al gate de valoración con la etiqueta de geometría oficial. La promoción
# ahora exige 7 criterios explícitos y evidencia declarada por el PRODUCTOR.
PREDIO_ORIGENES_ELEGIBLES = frozenset({
    "DIRECCION_OFICIAL_LIGADA_AL_PREDIO",   # punto de la dirección oficial enlazada
    "GEOMETRIA_OFICIAL_PREDIO",             # geometría propia del predio (capa/lote)
})
# Métodos y tipos de geometría NO admisibles como geometría oficial del predio.
# (Se listan métodos CONCRETOS, no la palabra «centroide» a secas: el centroide de
#  una geometría OFICIAL del predio sí es geometría oficial del predio.)
_METHOD_BLOCKLIST = ("GEOCODE", "HINT", "CENTROIDE_DE_BARRIO", "CENTROIDE_DE_CIUDAD",
                     "CITY_CENTROID", "BARRIO_DEMO", "DEMO", "ESTIMAD", "INTERPOLA",
                     "PLACA")
_GEOMETRY_TYPES_OK = frozenset({"Point", "Polygon", "MultiPolygon"})
_PROV_REQUIRED = ("source_system", "layer", "feature_id", "geometry_type",
                  "resolution_method", "predio_globalid")
# Claves de enlace que SÍ identifican oficialmente un predio. Una geometría cuyo
# `feature_id` provenga de un campo fuera de esta lista no acredita el predio.
_ID_KINDS_OFICIALES = frozenset({"cr_predio_guid", "globalid", "numero_predial_nacional",
                                 "lotcodigo", "codigo_lote", "nupre"})
# Cajas de cordura municipal: una coordenada proyectada (millones) o de otro país
# no puede pasar por geometría oficial del predio de ESTE caso.
_BBOX_CIUDAD = {
    "barranquilla": (10.70, 11.15, -75.05, -74.55),
    "bogota": (3.70, 4.85, -74.30, -73.95),
    "bogotá": (3.70, 4.85, -74.30, -73.95),
    "medellin": (6.10, 6.40, -75.65, -75.45),
    "medellín": (6.10, 6.40, -75.65, -75.45),
    "pasto": (1.10, 1.35, -77.40, -77.20),
}
BBox = Tuple[float, float, float, float]
# La geometría oficial acredita el PREDIO, no la unidad privada. Se documenta en
# el objeto para que ningún consumidor lea más de lo que la fuente sostiene.
COORD_SCOPE_OFICIAL_PREDIO = ("geometría oficial del PREDIO (lote/edificio): NO acredita "
                              "la posición del apartamento dentro de la edificación")


def _bbox_de(ciudad: Optional[str], *, es_bogota: bool = False,
             es_medellin: bool = False, es_pasto: bool = False) -> Optional[BBox]:
    if es_bogota:
        return _BBOX_CIUDAD["bogota"]
    if es_medellin:
        return _BBOX_CIUDAD["medellin"]
    if es_pasto:
        return _BBOX_CIUDAD["pasto"]
    return _BBOX_CIUDAD.get(str(ciudad or "").strip().lower())


def _sin_llaves(guid) -> str:
    return str(guid or "").strip().strip("{}").lower()


def evaluar_geometria_oficial_predio(*, predio_real: Optional[Dict[str, Any]],
                                     ciudad: Optional[str] = None,
                                     es_bogota: bool = False,
                                     es_medellin: bool = False,
                                     es_pasto: bool = False) -> Dict[str, Any]:
    """H-1: ¿puede esta coordenada declararse `OFFICIAL_PREDIO`? (7 criterios)

    1. El predio está RESUELTO y disponible (`disponible` no es False) y trae lat/lon.
    2. El PRODUCTOR declara un origen elegible (`coordenada_origen`) — nunca se
       deduce del hecho de que existan lat/lon.
    3. Vínculo oficial verificado: `feature_id` == globalid del predio (y
       `link_verificado` no es False cuando el productor lo declara).
    4. Identificadores oficiales presentes (globalid, o número predial + NUPRE).
    5. Procedencia COMPLETA: `source_system`, `layer`, `feature_id`, `geometry_type`,
       `resolution_method` y `predio_globalid` no vacíos.
    6. Método y tipo de geometría admisibles (ni geocode, ni hint, ni centroide, ni
       demo; geometría Point/Polygon/MultiPolygon).
    7. Cordura espacial: lat/lon finitas, no degeneradas y dentro de la caja del
       municipio del caso.

    Devuelve `{"eligible", "reason", "provenance", "bbox"}`. NUNCA lanza.
    """
    out: Dict[str, Any] = {"eligible": False, "reason": None, "provenance": {},
                           "bbox": None}
    pr = predio_real or {}
    # (1)
    if not pr:
        out["reason"] = "sin predio resuelto"
        return out
    if pr.get("disponible") is False:
        out["reason"] = "el predio no está disponible (disponible=False)"
        return out
    lat, lon = pr.get("lat"), pr.get("lon")
    if lat is None or lon is None:
        out["reason"] = "el predio no aporta lat/lon"
        return out
    try:
        lat_f, lon_f = float(lat), float(lon)
    except (TypeError, ValueError):
        out["reason"] = f"lat/lon no numéricos: {lat!r}/{lon!r}"
        return out
    # (2)
    origen = str(pr.get("coordenada_origen") or "").strip()
    if origen not in PREDIO_ORIGENES_ELEGIBLES:
        out["reason"] = (f"origen no elegible declarado por el productor: "
                         f"{origen or 'AUSENTE'}")
        return out
    # (5) procedencia completa
    prov = pr.get("coordenada_provenance")
    if not isinstance(prov, dict):
        out["reason"] = "procedencia de la coordenada ausente (coordenada_provenance)"
        return out
    faltan = [k for k in _PROV_REQUIRED
              if prov.get(k) is None or str(prov.get(k)).strip() == ""]
    if faltan:
        out["reason"] = "procedencia incompleta: faltan " + ", ".join(sorted(faltan))
        return out
    out["provenance"] = dict(prov)
    # (4) identificadores oficiales del predio
    pred = pr.get("predio") or {}
    globalid = _sin_llaves(pred.get("globalid") or pr.get("globalid"))
    num_predial = str(pred.get("numero_predial_nacional") or pred.get("numero_predial")
                      or pr.get("numero_predial") or "").strip()
    nupre = str(pred.get("nupre") or pred.get("codigo_homologado")
                or pr.get("nupre") or "").strip()
    _kind = str(prov.get("feature_id_kind") or "").strip().lower()
    _por_clave_oficial = bool(_kind in _ID_KINDS_OFICIALES
                              and str(prov.get("feature_id") or "").strip())
    if not globalid and not (num_predial and nupre) and not _por_clave_oficial:
        out["reason"] = ("sin identificadores oficiales del predio (globalid, número "
                         "predial + NUPRE o clave de enlace oficial declarada)")
        return out
    # (3) vínculo verificado entre la geometría y ESTE predio
    if prov.get("link_verificado") is False:
        out["reason"] = "vínculo de la coordenada con el predio NO verificado"
        return out
    fid = _sin_llaves(prov.get("feature_id"))
    if not fid:
        out["reason"] = "feature_id vacío: la geometría no es trazable a una feature"
        return out
    _pg = _sin_llaves(prov.get("predio_globalid"))
    if origen == "DIRECCION_OFICIAL_LIGADA_AL_PREDIO":
        if not globalid:
            out["reason"] = ("origen por dirección oficial pero el predio no declara "
                             "globalid con el que verificar el enlace")
            return out
        if fid != globalid or _pg != globalid:
            out["reason"] = (f"el enlace no coincide con el predio: feature_id={fid!r} "
                             f"predio_globalid={_pg!r} globalid={globalid!r}")
            return out
    else:
        # Geometría propia del predio: la procedencia debe identificar el MISMO
        # predio por un identificador oficial (globalid, número predial, NUPRE) o por
        # la misma clave de enlace declarada como oficial.
        _ids = {globalid, _sin_llaves(num_predial), _sin_llaves(nupre)} - {""}
        if not _pg:
            out["reason"] = "la procedencia no declara el predio de la geometría"
            return out
        if _pg != fid and _pg not in _ids:
            out["reason"] = ("la procedencia no acredita el mismo predio "
                             f"(predio_globalid={_pg!r}, feature_id={fid!r})")
            return out
    # (6) método y tipo de geometría
    _metodo = str(prov.get("resolution_method") or "").upper()
    _bloq = [b for b in _METHOD_BLOCKLIST if b in _metodo]
    if _bloq:
        out["reason"] = (f"método de resolución no admisible para geometría oficial: "
                         f"{prov.get('resolution_method')!r}")
        return out
    if str(prov.get("geometry_type")) not in _GEOMETRY_TYPES_OK:
        out["reason"] = (f"tipo de geometría no admisible: "
                         f"{prov.get('geometry_type')!r}")
        return out
    # (7) cordura espacial
    if not (math.isfinite(lat_f) and math.isfinite(lon_f)):
        out["reason"] = "lat/lon no finitas"
        return out
    if abs(lat_f) < 1e-6 and abs(lon_f) < 1e-6:
        out["reason"] = "coordenada degenerada (0, 0)"
        return out
    bbox = _bbox_de(ciudad, es_bogota=es_bogota, es_medellin=es_medellin,
                    es_pasto=es_pasto)
    out["bbox"] = bbox
    if bbox is not None:
        s, n, w, e = bbox
        if not (s <= lat_f <= n and w <= lon_f <= e):
            out["reason"] = (f"coordenada fuera de la caja del municipio {ciudad!r}: "
                            f"({lat_f}, {lon_f})")
            return out
    elif not (-90.0 <= lat_f <= 90.0 and -180.0 <= lon_f <= 180.0):
        out["reason"] = f"lat/lon fuera de rango geográfico: ({lat_f}, {lon_f})"
        return out
    out["eligible"] = True
    out["reason"] = "geometría oficial del predio con procedencia verificada"
    return out


def _geocodificador(geocoder=None):
    if geocoder is not None:
        return geocoder
    try:
        from geocoder import geocodificar_direccion
        return geocodificar_direccion
    except Exception:
        return None


def resolve_market_location(*, canonical_identity: Optional[Dict[str, Any]],
                            predio_real: Optional[Dict[str, Any]],
                            lat_geo, lon_geo,
                            db_lat, db_lon, db_direccion: Optional[str],
                            barrio: str, es_bogota: bool, es_medellin: bool,
                            es_pasto: bool, ciudad: str,
                            lat_geo_source: Optional[str] = None,
                            geocoder=None) -> Dict[str, Any]:
    """03H.1A: resuelve la ubicación de MERCADO (no identidad) con provenance REAL.

    Regla de no escalada de procedencia: una coordenada preexistente NO se
    reetiqueta como oficial. Si el registro oficial aporta una dirección, se
    GEOCODIFICA ESA dirección para poder marcarla como
    OFFICIAL_ADOPTION_ADDRESS_GEOCODE; si no se puede geocodificar, se conserva
    el origen real de las coordenadas y el gate bloqueará si no alcanza.
    """
    authoritative_address = None
    address_source = None
    cid = canonical_identity or {}
    if cid.get("identity_source") == "OFFICIAL_ADOPTION_REGISTRY":
        reg = cid.get("adopcion_registro") or {}
        if reg.get("direccion"):
            authoritative_address = reg["direccion"]
            address_source = "OFFICIAL_ADOPTION_REGISTRY"

    lat = lon = None
    source_address = None
    coordinate_source = COORD_UNRESOLVED
    geocoder_source = None
    geocoder_confidence = None
    coordinate_provenance: Dict[str, Any] = {}
    matched_nupre = None
    matched_predial = None
    _geo = _geocodificador(geocoder)

    def _geocodificar(texto):
        nonlocal geocoder_source
        if not _geo or not texto:
            return None, None
        try:
            from unidad_inmobiliaria import extraer_unidad
            _u = extraer_unidad(texto)
            base = _u.get("direccion_base") or texto
        except Exception:
            base = texto
        if not base or base.lower() in ("pendiente", ""):
            return None, None
        try:
            r = _geo(base, ciudad=ciudad)
        except Exception:
            return None, None
        if isinstance(r, (tuple, list)) and len(r) == 2 and r[0] is not None \
                and r[1] is not None:
            geocoder_source = "NOMINATIM/OSM"
            return r[0], r[1]
        return None, None

    # 1) geometría OFICIAL del predio resuelto — SOLO si supera los 7 criterios H-1
    # (antes bastaba con que `predio_real` trajera lat/lon: un hint geocodificado o
    #  un punto referencial entraban al gate etiquetados como oficiales).
    _eleg = evaluar_geometria_oficial_predio(
        predio_real=predio_real, ciudad=ciudad, es_bogota=es_bogota,
        es_medellin=es_medellin, es_pasto=es_pasto)
    _predio_elegible = bool(_eleg.get("eligible"))
    if _predio_elegible:
        lat, lon = predio_real["lat"], predio_real["lon"]
        coordinate_source = COORD_OFFICIAL_PREDIO
        source_address = predio_real.get("direccion_oficial") or None
        coordinate_provenance = dict(_eleg.get("provenance") or {})
        matched_nupre = coordinate_provenance.get("nupre")
        matched_predial = coordinate_provenance.get("numero_predial")
    elif predio_real:
        print(f"[MARKET][H1] geometria del predio NO promovida a OFFICIAL_PREDIO: "
              f"{_eleg.get('reason')}")

    # 2) dirección oficial de adopción -> geocodificar ESA dirección
    if lat is None and authoritative_address:
        _la, _lo = _geocodificar(authoritative_address)
        if _la is not None:
            lat, lon = _la, _lo
            coordinate_source = COORD_OFFICIAL_ADDRESS_GEOCODE
            source_address = authoritative_address
            coordinate_provenance = {
                "source_system": "REGISTRO_OFICIAL_DE_ADOPCION",
                "layer": None,
                "feature_id": None,
                "geometry_type": "Point",
                "resolution_method": "GEOCODE_DIRECCION_OFICIAL_DE_ADOPCION",
                "direccion_origen": authoritative_address,
                "link_verificado": None,
            }

    # 3) coordenadas ya geocodificadas (CTL) — conservan su origen REAL
    if lat is None and lat_geo is not None and lon_geo is not None:
        lat, lon = lat_geo, lon_geo
        coordinate_source = lat_geo_source or COORD_CTL_ADDRESS_GEOCODE
        source_address = db_direccion
        coordinate_provenance = {
            "source_system": "GEOCODER_DE_DIRECCION_DEL_CTL",
            "resolution_method": "GEOCODE_DIRECCION_CTL",
            "geometry_type": "Point",
            "direccion_origen": db_direccion,
            "declared_source": lat_geo_source,
        }

    # 4) coordenadas de la base de datos (NO autorizadas)
    if lat is None and (db_lat or db_lon):
        lat, lon = db_lat, db_lon
        coordinate_source = COORD_DB_COORDINATES
        source_address = db_direccion
        coordinate_provenance = {
            "source_system": "BASE_DE_DATOS_DEL_CASO",
            "resolution_method": "COORDENADAS_PERSISTIDAS",
            "geometry_type": "Point",
        }

    # 5) geocodificar la dirección del formulario
    if lat is None and db_direccion:
        _la, _lo = _geocodificar(db_direccion)
        if _la is not None:
            lat, lon = _la, _lo
            coordinate_source = COORD_FORM_ADDRESS_GEOCODE
            source_address = db_direccion
            coordinate_provenance = {
                "source_system": geocoder_source or "GEOCODER_EXTERNO",
                "resolution_method": "GEOCODE_DIRECCION_DEL_FORMULARIO",
                "geometry_type": "Point",
                "direccion_origen": db_direccion,
            }

    # 6) centroides/demo — NUNCA autorizados para el gate
    if lat is None:
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
        coordinate_provenance = {
            "source_system": "CENTROIDE_DE_REFERENCIA",
            "resolution_method": "CENTROIDE_DE_BARRIO_O_CIUDAD",
            "geometry_type": "Point",
            "nota": "coordenada de referencia: NO acredita el predio",
        }

    return {
        "authoritative_address": authoritative_address,
        "address_source": address_source,
        "lat": lat, "lon": lon,
        "source_address": source_address,
        "coordinate_source": coordinate_source,
        "coordinate_source_verified": coordinate_source_verified(coordinate_source),
        "geocoder_source": geocoder_source,
        "geocoder_confidence": geocoder_confidence,
        # 03I.2B §H/§N: procedencia de la coordenada (auditable en receipt/manifest).
        "coordinate_provenance": coordinate_provenance,
        "source_feature_id": coordinate_provenance.get("feature_id"),
        "source_layer": coordinate_provenance.get("layer"),
        "source_system": coordinate_provenance.get("source_system"),
        "resolution_method": coordinate_provenance.get("resolution_method"),
        "matched_nupre": matched_nupre,
        "matched_predial": matched_predial,
        # H-1: qué acredita y qué NO acredita esta geometría.
        "coordinate_scope": (COORD_SCOPE_OFICIAL_PREDIO
                             if coordinate_source == COORD_OFFICIAL_PREDIO else None),
        # Motivo declarado cuando la geometría del predio NO pudo promoverse.
        "official_predio_rejected_reason": (None if _predio_elegible
                                            else (_eleg.get("reason") if predio_real
                                                  else None)),
    }


# ── UrbanSourceSummary (03I.1 · F2) ───────────────────────────────────────────
# Declara, POR CAMPO, qué fuente produjo el valor urbano que muestra el dictamen.
# El caso Golden llegó a mostrar en 6.2 el texto fijo "CONSOLIDACION / DESARROLLO"
# y una fila "Fuente de capas: GeoJSON empaquetados (sin consulta en vivo)"
# mientras la tabla del mismo capítulo mostraba el tratamiento REAL de la capa
# oficial en vivo (Desarrollo / Bajo / altura 8). Dos verdades = un defecto.
USM_LIVE = "LIVE_OFFICIAL"
USM_PACKAGED = "PACKAGED_REFERENCE"
USM_MIXED = "MIXED"
USM_UNAVAILABLE = "SOURCE_UNAVAILABLE"

# Campos urbanos que pueden venir del contexto oficial en vivo.
_CAMPOS_OFICIALES = ("barrio", "localidad", "pieza_urbana", "estrato", "tratamiento",
                     "tipo_tratamiento", "altura_maxima")


def build_urban_source_summary(*, official_urban_context: Optional[Dict[str, Any]] = None,
                               campos_empaquetados: Optional[List[str]] = None,
                               etiqueta_empaquetados: str = ("Geometrias del POT "
                                                             "empaquetadas en la aplicacion")) -> Dict[str, Any]:
    """Resumen auditable de procedencia urbana (por campo + modo global).

    Args:
        official_urban_context: salida de `resolve_official_urban_context`.
        campos_empaquetados: hechos que provienen de geometrías EMPAQUETADAS
            (p. ej. las capas de riesgo del POT consultadas por STRtree local).

    Returns:
        {"source_mode", "campos": {campo: {value, fuente, modo}}, "fuente_oficial",
         "declaracion"}
    """
    ouc = official_urban_context or {}
    campos: Dict[str, Dict[str, Any]] = {}
    for campo in _CAMPOS_OFICIALES:
        valor = ouc.get(campo)
        status = ouc.get(f"{campo}_status") if campo != "localidad" and campo != "pieza_urbana" else ouc.get("context_status")
        if valor in (None, ""):
            continue
        vivo = (campo in ("localidad", "pieza_urbana")) or status == STATUS_VERIFIED_OFFICIAL
        campos[campo] = {
            "value": valor,
            "status": status,
            "fuente": (ouc.get("source") or "official_urban_layer") if vivo else None,
            "modo": USM_LIVE if vivo else USM_PACKAGED,
        }
    for campo in (campos_empaquetados or []):
        campos.setdefault(campo, {"value": None, "status": None,
                                  "fuente": etiqueta_empaquetados, "modo": USM_PACKAGED})

    _modos = {c["modo"] for c in campos.values()}
    if not _modos:
        modo = USM_UNAVAILABLE
    elif _modos == {USM_LIVE}:
        modo = USM_LIVE
    elif _modos == {USM_PACKAGED}:
        modo = USM_PACKAGED
    else:
        modo = USM_MIXED

    if modo == USM_LIVE:
        declaracion = ("Todos los valores urbanos mostrados provienen de la capa oficial "
                       "consultada EN VIVO.")
    elif modo == USM_PACKAGED:
        declaracion = ("Los valores urbanos mostrados provienen de geometrias "
                       "empaquetadas en la aplicacion (sin consulta en vivo).")
    elif modo == USM_MIXED:
        _vivos = ", ".join(k for k, v in campos.items() if v["modo"] == USM_LIVE)
        _emp = ", ".join(k for k, v in campos.items() if v["modo"] == USM_PACKAGED)
        declaracion = ("Procedencia MIXTA: " + (f"EN VIVO ({_vivos})" if _vivos else "EN VIVO (—)")
                       + " · " + (f"EMPAQUETADO ({_emp})" if _emp else "EMPAQUETADO (—)"))
    else:
        declaracion = "Sin valores urbanos resueltos en esta ejecución."
    return {
        "source_mode": modo,
        "campos": campos,
        "fuente_oficial": ouc.get("source"),
        "context_status": ouc.get("context_status"),
        "declaracion": declaracion,
    }


def urban_source_mode(summary: Optional[Dict[str, Any]]) -> str:
    return (summary or {}).get("source_mode") or USM_UNAVAILABLE


# ── Contexto urbano OFICIAL por coordenadas autorizadas (03H.1A) ──────────────
def resolve_official_urban_context(*, ciudad: str, lat, lon,
                                   coordinate_source: Optional[str],
                                   consultar_entorno=None,
                                   numero_predial: Optional[str] = None) -> Dict[str, Any]:
    """Consulta OFICIAL de barrio/estrato/tratamiento por coordenadas.

    Es CONTEXTO ESPACIAL, no identidad: NO modifica identity_source y funciona
    aunque `predio_real` sea None (la identidad puede venir del registro oficial
    de adopción). Solo se consulta si `coordinate_source` está en la allowlist.

    03I.1 · F4: `numero_predial` habilita la resolución del estrato por MANZANA
    cuando la consulta espacial por punto no intersecta ningún polígono de
    manzana (caso Golden 040-646406). La atribución sigue siendo OFICIAL: la
    manzana sale del propio número predial y se consulta por atributo.
    """
    out: Dict[str, Any] = {
        "barrio": None, "barrio_status": STATUS_UNRESOLVED,
        "localidad": None,
        "estrato": None, "estrato_status": STATUS_UNRESOLVED,
        "estrato_origen": None, "estrato_trace": None,
        "tratamiento": None, "tratamiento_status": STATUS_UNRESOLVED,
        "tipo_tratamiento": None, "tipo_tratamiento_status": STATUS_UNRESOLVED,
        "altura_maxima": None, "altura_status": STATUS_UNRESOLVED,
        "pieza_urbana": None,
        "codigo_manzana": None,
        "context_status": None, "campos_ambiguos": [],
        "source": None, "coordinate_source": coordinate_source,
    }

    if not coordinate_source_verified(coordinate_source):
        out["context_status"] = "COORDINATE_SOURCE_NOT_AUTHORIZED"
        return out
    if lat is None or lon is None:
        out["context_status"] = "NO_COORDINATES"
        return out

    _fn = consultar_entorno
    if _fn is None:
        _c = (ciudad or "").lower()
        try:
            if "medellin" in _c or "medellín" in _c:
                from catastro_predio_medellin import consultar_entorno_urbano as _fn
            else:
                from catastro_predio import consultar_entorno_urbano as _fn
        except Exception:
            _fn = None
    if _fn is None:
        out["context_status"] = STATUS_SOURCE_UNAVAILABLE
        return out

    try:
        if numero_predial:
            r = _fn(lat, lon, numero_predial=numero_predial) or {}
        else:
            r = _fn(lat, lon) or {}
    except TypeError:
        # Productores antiguos/alternativos que no aceptan el número predial.
        try:
            r = _fn(lat, lon) or {}
        except Exception:
            out["context_status"] = STATUS_SOURCE_UNAVAILABLE
            return out
    except Exception:
        out["context_status"] = STATUS_SOURCE_UNAVAILABLE
        return out

    if not r.get("disponible"):
        out["context_status"] = STATUS_SOURCE_UNAVAILABLE
        return out

    out["source"] = "official_urban_layer"
    # 03H.2A (#A): ambigüedad POR CAMPO. La fuente declara exactamente qué
    # atributos no pudo consolidar; un campo ambiguo NO se afirma y su status
    # queda CONFLICT (nunca VERIFIED_OFFICIAL). El fallback global solo aplica a
    # productores antiguos que no informan `campos_ambiguos`.
    amb = set(r.get("campos_ambiguos") or [])
    if r.get("context_status") == "AMBIGUOUS_CONTEXT" and not amb:
        amb = {"barrio", "estrato", "tratamiento", "tipo_tratamiento",
               "altura_maxima"}
    out["campos_ambiguos"] = sorted(amb)

    # 03H.2: conservar TODOS los atributos devueltos (no descartar riqueza).
    if r.get("barrio") and "barrio" not in amb:
        out["barrio"] = r["barrio"]
        out["barrio_status"] = STATUS_VERIFIED_OFFICIAL
    elif "barrio" in amb:
        out["barrio_status"] = STATUS_CONFLICT

    out["localidad"] = r.get("localidad")
    out["pieza_urbana"] = r.get("pieza_urbana")
    out["codigo_manzana"] = r.get("codigo_manzana")
    # 03I.1 · F4: procedencia del estrato (espacial vs manzana del predial).
    out["estrato_origen"] = r.get("estrato_origen")
    out["estrato_trace"] = r.get("estrato_trace")

    if r.get("estrato") not in (None, "") and "estrato" not in amb:
        out["estrato"] = r["estrato"]
        out["estrato_status"] = STATUS_VERIFIED_OFFICIAL
    elif "estrato" in amb:
        out["estrato_status"] = STATUS_CONFLICT

    if r.get("tratamiento") and "tratamiento" not in amb:
        out["tratamiento"] = r["tratamiento"]
        out["tratamiento_status"] = STATUS_VERIFIED_OFFICIAL
    elif "tratamiento" in amb:
        out["tratamiento_status"] = STATUS_CONFLICT

    # 03H.2A (#A): tipo_tratamiento tiene su PROPIA ambigüedad. Aunque el tipo se
    # haya consolidado, si el TRATAMIENTO no se pudo consolidar el polígono del
    # predio no está determinado y el tipo no es atribuible: no se afirma.
    if (r.get("tipo_tratamiento")
            and "tipo_tratamiento" not in amb and "tratamiento" not in amb):
        out["tipo_tratamiento"] = r["tipo_tratamiento"]
        out["tipo_tratamiento_status"] = STATUS_VERIFIED_OFFICIAL
    elif "tipo_tratamiento" in amb or "tratamiento" in amb:
        out["tipo_tratamiento_status"] = STATUS_CONFLICT

    # Altura normativa (misma capa que tratamiento: se propaga, no se hardcodea).
    # 03H.2A: VERIFIED_OFFICIAL solo si la altura se consolidó SIN conflicto
    # (una altura elegida de features[0] NO puede afirmarse como oficial).
    if (r.get("altura_maxima") not in (None, "")
            and "altura_maxima" not in amb and "tratamiento" not in amb):
        out["altura_maxima"] = r["altura_maxima"]
        out["altura_status"] = STATUS_VERIFIED_OFFICIAL
    elif "altura_maxima" in amb or "tratamiento" in amb:
        out["altura_status"] = STATUS_CONFLICT

    out["context_status"] = ("AMBIGUOUS_CONTEXT" if amb else "OK")
    return out

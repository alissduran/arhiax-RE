# -*- coding: utf-8 -*-
"""
ARHIAX RE — Resolución catastral del predio en Bogotá (Sprint 3, expansión)

Misma interfaz que catastro_predio_medellin / catastro_predio (Barranquilla)
para que el dictamen despache por ciudad.

El catastro distrital de Bogotá (serviciosgis.catastrobogota.gov.co) NO publica
una capa predial con el NUPRE/número predial nacional de 30 dígitos: el detalle
por predio (destino económico individual) no está en datos abiertos. Por eso la
resolución es POR PUNTO (honesta y referencial):

    lote/manzana          -> catastro/lote + catastro/manzana
    barrio/sector         -> catastro/sectorcatastral (SCANOMBRE)
    uso económico (mz)    -> catastro/usopredominante (GRUPOUSOECON por manzana)
    estrato               -> ordenamientoterritorial/estratificacion l1
    UPZ / localidad       -> ordenamientoterritorial/unidadplaneamientozonal,
                             localidad
    suelo (POT Decreto 555/2021) -> ordenamientoterritorial/suelo
    valor referencia m2   -> catastro/valorreferencia (V_REF por manzana)
    construcción          -> catastro/construccion (pisos)
    riesgos (IDIGER)      -> emergencias/gestionriesgos (mov. masa, geotecnia,
                             respuesta sísmica)

Nunca lanza; disponible=False honesto si el servicio no responde. El NUPRE/código
del CTL se muestra como declarado en el certificado (sin verificación puntual en
abierto), nunca se afirma el de un predio vecino.
"""

from __future__ import annotations

import re
import time
from typing import Any, Optional

import requests

UA = {"User-Agent": "ARHIAX-RE/1.0 (Sinergia Consulting Group)"}
BASE = "https://serviciosgis.catastrobogota.gov.co/arcgis/rest/services"

# 03I.2B · H-1: origen declarado de las coordenadas (mismo vocabulario que los
# demás catastros: el consumidor de mercado NO debe adivinar la procedencia).
SOURCE_SYSTEM_BOGOTA = "CATASTRO_MUNICIPAL_BOGOTA_ARCGIS"
ORIGEN_GEOMETRIA_OFICIAL = "GEOMETRIA_OFICIAL_PREDIO"
ORIGEN_HINT = "HINT_NO_OFICIAL"

TIMEOUT = 7.0
TTL_CACHE = 3600

_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


def _cache_get(key: str):
    item = _CACHE.get(key)
    if item and (time.time() - item[0]) < TTL_CACHE:
        return item[1]
    return None


def _cache_set(key: str, res: dict):
    _CACHE[key] = (time.time(), res)


def _get_json(url: str, params: dict, timeout: float = TIMEOUT) -> Optional[dict]:
    try:
        resp = requests.get(url, params=params, headers=UA, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and data.get("error"):
            return None
        return data
    except Exception:
        return None


def _norm_feature(feature: dict) -> dict:
    props = feature.get("attributes") if isinstance(feature, dict) else None
    geom_raw = feature.get("geometry") if isinstance(feature, dict) else None
    geom = None
    if isinstance(geom_raw, dict):
        if "x" in geom_raw and geom_raw.get("x") is not None:
            geom = {"type": "Point", "coordinates": [float(geom_raw["x"]), float(geom_raw["y"])]}
        elif geom_raw.get("rings"):
            rings = geom_raw["rings"]
            geom = {"type": "Polygon",
                    "coordinates": [[[float(p[0]), float(p[1])] for p in ring] for ring in rings]}
    return {"properties": props or {}, "geometry": geom}


def _q_capa(svc_path: str, lid: int, where: str, out_fields: str = "*",
            max_features: int = 5, return_geometry: bool = False,
            timeout: float = TIMEOUT) -> dict[str, Any]:
    params = {
        "where": where, "outFields": out_fields, "outSR": "4326",
        "returnGeometry": "true" if return_geometry else "false",
        "f": "json", "resultRecordCount": str(max_features),
    }
    data = _get_json(f"{BASE}/{svc_path}/MapServer/{lid}/query", params, timeout)
    if data is None:
        return {"disponible": False, "features": [], "error": "servicio sin respuesta"}
    features = [_norm_feature(f) for f in data.get("features", [])]
    return {"disponible": True, "features": features, "total": len(features), "error": None}


def _q_bbox(svc_path: str, lid: int, lon: float, lat: float,
            out_fields: str = "*", max_features: int = 6,
            buf: float = 0.003, timeout: float = TIMEOUT) -> dict[str, Any]:
    """Consulta una capa por BBOX alrededor del punto (envuelve la geometría)."""
    params = {
        "where": "1=1", "outFields": out_fields, "outSR": "4326",
        "geometry": f"{lon-buf},{lat-buf},{lon+buf},{lat+buf}",
        "geometryType": "esriGeometryEnvelope", "inSR": "4326",
        "returnGeometry": "false", "f": "json", "resultRecordCount": str(max_features),
    }
    data = _get_json(f"{BASE}/{svc_path}/MapServer/{lid}/query", params, timeout)
    if data is None:
        return {"disponible": False, "features": [], "error": "servicio sin respuesta"}
    features = [_norm_feature(f) for f in data.get("features", [])]
    return {"disponible": True, "features": features, "total": len(features), "error": None}


def _q_pip(svc_path: str, lid: int, lon: float, lat: float,
           out_fields: str = "*", max_features: int = 3,
           timeout: float = TIMEOUT) -> dict[str, Any]:
    """Consulta point-in-polygon EXACTA: devuelve SOLO el polígono que contiene
    el punto (esriGeometryPoint + intersects). A diferencia del bbox, no trae
    features VECINAS de otras manzanas/sectores en orden arbitrario — regresión:
    el dictamen del predio real (DG 61B # 20-04, lote 007202018025) resolvía el
    entorno en el Restrepo/localidad vecina porque el bbox devolvía primero otro
    lote (el punto de placa está en el borde de la manzana)."""
    params = {
        "where": "1=1", "outFields": out_fields, "outSR": "4326",
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint", "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "returnGeometry": "false", "f": "json", "resultRecordCount": str(max_features),
    }
    data = _get_json(f"{BASE}/{svc_path}/MapServer/{lid}/query", params, timeout)
    if data is None:
        return {"disponible": False, "features": [], "error": "servicio sin respuesta"}
    features = [_norm_feature(f) for f in data.get("features", [])]
    return {"disponible": True, "features": features, "total": len(features), "error": None}


def _centro(feature: dict) -> Optional[tuple]:
    geom = feature.get("geometry") or {}
    coords = geom.get("coordinates")
    if not coords:
        return None
    if geom.get("type") == "Point":
        return (float(coords[0]), float(coords[1]))
    try:
        if geom.get("type") == "MultiPolygon":
            ring = coords[0][0]
        else:
            ring = coords[0] if isinstance(coords[0], list) else coords
        xs = [float(c[0]) for c in ring]
        ys = [float(c[1]) for c in ring]
        return (sum(xs) / len(xs), sum(ys) / len(ys))
    except Exception:
        return None


# ── 1. Entorno urbano por punto (lote, sector, uso, estrato, UPZ, suelo) ─────

def consultar_entorno_urbano(lat: float, lon: float, codigo_lote: str = None,
                             codigo_manzana: str = None) -> dict[str, Any]:
    """Lote+manzana, sector con nombre, uso por manzana, estrato, UPZ,
    localidad, suelo y valor de referencia por punto.

    Regresión (dictamen real 50C-1463431): antes se consultaba por BBOX y se
    tomaba la PRIMERA feature (features[0]) — pero el bbox alrededor del punto
    de placa (que queda en el borde de la manzana) devolvía el LOTE VECINO de
    otra localidad (Restrepo/LA ESPERANZA) en vez del lote real del CTL
    (SAN LUIS / TEUSAQUILLO). Ahora se resuelve por point-in-polygon exacto y,
    cuando se conoce el código de lote (de la placa domiciliaria oficial), se
    consulta la manzana por código."""
    cache_key = f"bog_entorno|{round(lat, 5)}|{round(lon, 5)}|{codigo_lote or ''}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    res = {"disponible": False, "error": None,
           "barrio": None, "sector_catastral": None, "localidad": None,
           "upz": None, "estrato": None, "uso_economico": None,
           "clase_suelo": None, "valor_ref_m2": None, "codigo_manzana": None,
           "codigo_lote": None}

    mz = codigo_manzana
    if codigo_lote and not mz:
        # Lote exacto por código: entrega la manzana real del predio (el bbox
        # alrededor del punto de placa podía caer en la manzana vecina).
        r_lote_cod = _q_capa("catastro/lote", 0, f"LOTCODIGO='{codigo_lote}'",
                             "LOTCODIGO,MANZCODIGO,LOTUPREDIA", max_features=3)
        for f in r_lote_cod.get("features", []):
            p = f.get("properties", {})
            mz = p.get("MANZCODIGO") or mz
            if not res["codigo_lote"]:
                res["codigo_lote"] = p.get("LOTCODIGO") or codigo_lote
    if not res["codigo_lote"]:
        res["codigo_lote"] = codigo_lote
    if not mz:
        # Sin código: identificar el lote/manzana del punto por point-in-polygon
        # (el bbox devolvía el LOTE VECINO como features[0]).
        r_lote = _q_pip("catastro/lote", 0, lon, lat,
                        "LOTCODIGO,MANZCODIGO,LOTUPREDIA", max_features=3)
        if not r_lote.get("features"):
            r_lote = _q_bbox("catastro/lote", 0, lon, lat,
                             "LOTCODIGO,MANZCODIGO,LOTUPREDIA", max_features=10)
        for f in r_lote.get("features", []):
            p = f.get("properties", {})
            if not res["codigo_lote"]:
                res["codigo_lote"] = p.get("LOTCODIGO")
            mz = p.get("MANZCODIGO") or mz
            break

    # Sector catastral con NOMBRE (barrio oficial): point-in-polygon exacto
    # (regresión: el bbox devolvía el sector VECINO cuando el punto está en el
    # límite — p. ej. 'LA ESPERANZA' en vez de 'SAN LUIS').
    r_sec = _q_pip("catastro/sectorcatastral", 0, lon, lat, "SCACODIGO,SCANOMBRE,SCATIPO")
    if not r_sec.get("features"):
        r_sec = _q_bbox("catastro/sectorcatastral", 0, lon, lat, "SCACODIGO,SCANOMBRE,SCATIPO")
    if r_sec.get("features"):
        p = r_sec["features"][0].get("properties", {})
        res["sector_catastral"] = p.get("SCACODIGO")
        res["barrio"] = p.get("SCANOMBRE")

    # Uso económico predominante por MANZANA (exacto si tenemos el código)
    if mz:
        r_uso = _q_capa("catastro/usopredominante", 0, f"MANCODIGO='{mz}'",
                        "MANCODIGO,GRUPOUSOECON,ANO")
        if not r_uso.get("features"):
            r_uso = _q_pip("catastro/usopredominante", 0, lon, lat,
                           "MANCODIGO,GRUPOUSOECON,ANO")
    else:
        r_uso = _q_pip("catastro/usopredominante", 0, lon, lat,
                       "MANCODIGO,GRUPOUSOECON,ANO")
    if r_uso.get("features"):
        p = r_uso["features"][0].get("properties", {})
        res["uso_economico"] = p.get("GRUPOUSOECON")

    # Estrato (manzanas de estrato). Bogotá estratifica 1-6: el valor '0' o
    # ausente significa manzana SIN estratificación (uso no residencial), no un
    # estrato real: se deja None para que el dictamen lo marque como tal.
    r_est = _q_pip("ordenamientoterritorial/estratificacion", 1, lon, lat,
                   "CODIGO_MANZANA,ESTRATO")
    if not r_est.get("features"):
        r_est = _q_bbox("ordenamientoterritorial/estratificacion", 1, lon, lat,
                        "CODIGO_MANZANA,ESTRATO")
    if r_est.get("features"):
        p = r_est["features"][0].get("properties", {})
        estr = p.get("ESTRATO")
        try:
            estr_int = int(str(estr).strip() or 0)
        except (TypeError, ValueError):
            estr_int = 0
        res["estrato"] = estr_int if 1 <= estr_int <= 6 else None

    # UPZ / Localidad / Suelo: point-in-polygon exacto (una sola feature por
    # punto; el bbox podía mezclar dos localidades en el límite).
    r_upz = _q_pip("ordenamientoterritorial/unidadplaneamientozonal", 0, lon, lat,
                   "CODIGO_UPZ,NOMBRE")
    if not r_upz.get("features"):
        r_upz = _q_bbox("ordenamientoterritorial/unidadplaneamientozonal", 0, lon, lat,
                        "CODIGO_UPZ,NOMBRE")
    if r_upz.get("features"):
        p = r_upz["features"][0].get("properties", {})
        res["upz"] = p.get("NOMBRE")

    r_loc = _q_pip("ordenamientoterritorial/localidad", 0, lon, lat, "LOCCODIGO,LOCNOMBRE")
    if not r_loc.get("features"):
        r_loc = _q_bbox("ordenamientoterritorial/localidad", 0, lon, lat,
                        "LOCCODIGO,LOCNOMBRE")
    if r_loc.get("features"):
        p = r_loc["features"][0].get("properties", {})
        res["localidad"] = p.get("LOCNOMBRE")

    r_sue = _q_pip("ordenamientoterritorial/suelo", 0, lon, lat,
                   "SUECODIGO,SUECSUELO,SUEAADMIN")
    if not r_sue.get("features"):
        r_sue = _q_bbox("ordenamientoterritorial/suelo", 0, lon, lat,
                        "SUECODIGO,SUECSUELO,SUEAADMIN")
    if r_sue.get("features"):
        p = r_sue["features"][0].get("properties", {})
        cs = p.get("SUECSUELO")
        res["clase_suelo"] = {1: "Urbano", 2: "Rural", 3: "Expansión"}.get(cs, f"Suelo {cs}")

    # Valor de referencia (m2 por manzana) — solo la manzana REAL del predio
    # (regresión: antes tomaba V_REF de la primera manzana del bbox, ajena).
    if mz:
        r_val = _q_capa("catastro/valorreferencia", 0, f"MANCODIGO='{mz}'",
                        "MANCODIGO,V_REF,ANO")
        if not r_val.get("features"):
            r_val = _q_pip("catastro/valorreferencia", 0, lon, lat, "MANCODIGO,V_REF,ANO")
    else:
        r_val = _q_pip("catastro/valorreferencia", 0, lon, lat, "MANCODIGO,V_REF,ANO")
    if r_val.get("features"):
        # Varias filas por año: tomar la más reciente (mayor ANO)
        mejores = sorted(r_val["features"],
                         key=lambda f: ((f.get("properties") or {}).get("ANO") or 0),
                         reverse=True)
        p = mejores[0].get("properties", {})
        res["valor_ref_m2"] = p.get("V_REF")
        if not mz:
            mz = p.get("MANCODIGO")

    res["codigo_manzana"] = mz or res.get("codigo_manzana")
    res["disponible"] = bool(res["barrio"] or res["localidad"] or res["estrato"]
                             or res["uso_economico"] or res["clase_suelo"])
    if not res["disponible"]:
        res["error"] = "entorno sin coincidencia en capas de Bogotá"
    _cache_set(cache_key, res)
    return res


# ── 2. Construcción (pisos) ─────────────────────────────────────────────────

def consultar_construccion(lat: float, lon: float, codigo_lote: str = None) -> dict[str, Any]:
    """Pisos del EDIFICIO PRINCIPAL del lote.

    Cuando se conoce el código de lote (placa domiciliaria oficial), se consulta
    por LOTECODIGO EXACTO: el dictamen real (50C-1463431, lote 007202018025)
    reportaba '4 piso(s)' porque el bbox alrededor del punto de placa devolvía
    primero una construcción VECINA de otra manzana; el lote real tiene un
    edificio de 6 pisos (la persona que vive allí lo confirmó: 'mi edificio es
    de más de 4 pisos'). El bbox se mantiene solo como respaldo."""
    cache_key = f"bog_const|{round(lat, 5)}|{round(lon, 5)}|{codigo_lote or ''}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    res = {"disponible": False, "error": None, "tipo_construccion": None,
           "total_pisos": None, "area_construida": None, "codigo_construccion": None}
    feats = []
    if codigo_lote:
        r = _q_capa("catastro/construccion", 0, f"LOTECODIGO='{codigo_lote}'",
                    "CONCODIGO,CONNPISOS,CONALTURA,LOTECODIGO", max_features=10)
        feats = r.get("features") or []
    if not feats:
        r = _q_bbox("catastro/construccion", 0, lon, lat,
                    "CONCODIGO,CONNPISOS,CONALTURA,LOTECODIGO", max_features=10)
        feats = r.get("features") or []
    if codigo_lote and feats:
        feats_lote = [f for f in feats
                      if str((f.get("properties") or {}).get("LOTECODIGO") or "") == str(codigo_lote)]
        if feats_lote:
            feats = feats_lote

    def _pisos(f):
        try:
            return int((f.get("properties") or {}).get("CONNPISOS") or 0)
        except (TypeError, ValueError):
            return 0

    def _altura(f):
        try:
            return float((f.get("properties") or {}).get("CONALTURA") or 0)
        except (TypeError, ValueError):
            return 0

    if feats:
        # Edificio principal: mayor (pisos, altura) entre las del lote
        mejor = max(feats, key=lambda f: (_pisos(f), _altura(f)))
        p = mejor.get("properties", {})
        res["codigo_construccion"] = p.get("CONCODIGO")
        pisos = _pisos(mejor)
        res["total_pisos"] = pisos or None
        res["altura"] = p.get("CONALTURA")
        res["tipo_construccion"] = "Edificación"
        res["disponible"] = bool(pisos or p.get("CONALTURA"))
    else:
        res["error"] = "construcción sin coincidencia en Bogotá"
    _cache_set(cache_key, res)
    return res


def _es_no_afectacion(valor) -> bool:
    """True si el valor textual de una capa de amenazas indica que NO hay
    afectación (los servicios IDIGER devuelven textos tipo 'Sin afectación',
    'No aplica' que antes se trataban como intersección real)."""
    if valor is None:
        return True
    s = str(valor).strip().upper()
    # Normaliza tildes ('SIN AFECTACIÓN' -> 'SIN AFECTACION')
    for a, b in (("Á", "A"), ("É", "E"), ("Í", "I"), ("Ó", "O"), ("Ú", "U")):
        s = s.replace(a, b)
    if not s or s in ("0", "NA", "N/A", "NINGUNA", "NO APLICA", "NO REGISTRA",
                      "NO PRESENTA", "SIN DATO", "SIN INFORMACION"):
        return True
    return any(k in s for k in ("SIN AFECTACION", "SIN RIESGO", "SIN AMENAZA"))


# ── 3. Amenazas y riesgos (IDIGER) ──────────────────────────────────────────

def consultar_amenazas(lat: float, lon: float) -> dict[str, Any]:
    cache_key = f"bog_riesgo|{round(lat, 5)}|{round(lon, 5)}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    # Solo capas de AMENAZA real: remoción en masa (l2) y respuesta sísmica
    # (l7, microzonificación con nivel Alta/Media/Baja). La capa l8 GEOTECNIA
    # describe el TIPO DE SUELO ('Aluvial', 'Lacustre'...) y NO es una amenaza:
    # se reporta como dato informativo sin disparar intersección (regresión:
    # un predio en suelo 'Aluvial' aparecía como 'Afectación por Amenaza').
    capas = {
        "movimiento_masa_urbano": (2, "AMENAZA"),
        "respuesta_sismica": (7, "ZONA_RESPUESTA"),
    }
    res = {"disponible": False, "error": None, "geotecnia_tipo_suelo": None}
    for nombre, (lid, campo) in capas.items():
        r = _q_bbox("emergencias/gestionriesgos", lid, lon, lat, campo, max_features=3)
        if r.get("features"):
            p = r["features"][0].get("properties", {})
            valor = p.get(campo)
            intersecta = bool(valor) and not _es_no_afectacion(valor)
            res[nombre] = {"intersecta": intersecta,
                           "nivel": None if not intersecta else valor}
        else:
            res[nombre] = {"intersecta": False, "nivel": None}
    # Geotecnia (tipo de suelo) — informativo, nunca intersección de amenaza
    try:
        r_geo = _q_bbox("emergencias/gestionriesgos", 8, lon, lat, "GEOTECNIA", max_features=3)
        if r_geo.get("features"):
            v_geo = (r_geo["features"][0].get("properties") or {}).get("GEOTECNIA")
            res["geotecnia_tipo_suelo"] = None if _es_no_afectacion(v_geo) else v_geo
    except Exception:
        pass
    res["disponible"] = any(
        (res[k].get("intersecta") if isinstance(res.get(k), dict) else False) for k in capas)
    if not res["disponible"]:
        res["error"] = "sin coincidencia de amenazas/riesgos en Bogotá (IDIGER)"
    _cache_set(cache_key, res)
    return res


# ── 4. Enriquecimiento integral por punto (Bogotá no expone NUPRE en abierto) ─

def _centroide_lote_por_codigo(codigo_lote: str):
    """Centroide (lon, lat) del polígono del lote consultado por código.

    El punto de la placa domiciliaria cae en el BORDE de la manzana (a veces
    sobre la vía) y el point-in-polygon sobre él puede resolver la manzana
    vecina. El centroide del lote real es el punto de referencia estable para
    sector/localidad/UPZ/estrato (regresión dictamen 50C-1463431)."""
    if not codigo_lote:
        return None
    r = _q_capa("catastro/lote", 0, f"LOTCODIGO='{codigo_lote}'",
                "LOTCODIGO,MANZCODIGO", max_features=3, return_geometry=True)
    for f in r.get("features", []):
        c = _centro(f)
        if c:
            return (float(c[1]), float(c[0]))  # (lat, lon)
    return None


def enriquecer_por_punto(lat: float = None, lon: float = None,
                         codigo_lote: str = None) -> dict[str, Any]:
    """Pipeline por coordenadas (no hay resolución por código en abierto).

    codigo_lote: si se conoce (placa domiciliaria oficial resuelta por el
    geocoder catastral), se pasa a entorno/construcción para consultar la
    manzana y el edificio EXACTOS del predio (regresión: el dictamen real
    50C-1463431 resolvía el entorno en el lote vecino del Restrepo)."""
    if lat is None or lon is None:
        return {"disponible": False, "error": "sin coordenadas", "predio": {}}
    # Punto de referencia estable: centroide del lote por código cuando se
    # conoce (el punto de placa queda en el borde de la manzana).
    _lat_ref, _lon_ref = float(lat), float(lon)
    _centro_lote = _centroide_lote_por_codigo(codigo_lote) if codigo_lote else None
    if _centro_lote:
        _lat_ref, _lon_ref = _centro_lote
    res: dict[str, Any] = {"disponible": False, "error": None, "predio": {}}
    res["lat"] = _lat_ref
    res["lon"] = _lon_ref
    res["resolucion"] = "por_punto_referencial"
    # 03I.2B · H-1: el centroide del LOTE oficial (por LOTCODIGO del predio) es
    # geometría oficial del predio; el punto de placa geocodificado NO lo es.
    if _centro_lote:
        res["coordenada_origen"] = ORIGEN_GEOMETRIA_OFICIAL
        res["coordenada_provenance"] = {
            "source_system": SOURCE_SYSTEM_BOGOTA,
            "layer": "catastro/lote",
            "feature_id": str(codigo_lote).strip(),
            "feature_id_kind": "LOTCODIGO",
            "geometry_type": "Polygon",
            "resolution_method": "CENTROIDE_DE_GEOMETRIA_OFICIAL_DEL_LOTE",
            "predio_globalid": str(codigo_lote).strip(),
            "numero_predial": str(codigo_lote).strip(),
            "link_verificado": True,
        }
    else:
        res["coordenada_origen"] = ORIGEN_HINT
    res["entorno"] = consultar_entorno_urbano(_lat_ref, _lon_ref,
                                              codigo_lote=codigo_lote)
    # Pasar el código de lote para elegir la construcción del EDIFICIO del
    # predio (no la primera construcción vecina del bbox)
    _lote_efectivo = (codigo_lote
                      or (res["entorno"].get("codigo_lote") or None))
    res["construccion"] = consultar_construccion(
        _lat_ref, _lon_ref, codigo_lote=_lote_efectivo)
    res["amenazas"] = consultar_amenazas(_lat_ref, _lon_ref)
    res["disponible"] = bool(res["entorno"].get("disponible")
                             or res["construccion"].get("disponible")
                             or res["amenazas"].get("disponible"))
    if _centro_lote:
        # 03I.2B · H-1: si se obtuvo la geometría OFICIAL del lote, el predio quedó
        # resuelto aunque las capas de contexto no respondan: `disponible` describe la
        # resolución del predio, no la disponibilidad de capas auxiliares.
        res["disponible"] = True
        res["error"] = None
    if not res["disponible"]:
        res["error"] = "sin coincidencia catastral en Bogotá para el punto"
    return res


# ── Utilidad (re-export del extractor nacional de código/NUPRE del CTL) ──────
from catastro_predio import extraer_codigo_nupre_de_ctl  # noqa: E402

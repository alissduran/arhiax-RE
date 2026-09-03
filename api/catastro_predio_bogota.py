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

def consultar_entorno_urbano(lat: float, lon: float) -> dict[str, Any]:
    """Lote+manzana, sector con nombre, uso por manzana, estrato, UPZ,
    localidad, suelo y valor de referencia por punto."""
    cache_key = f"bog_entorno|{round(lat, 5)}|{round(lon, 5)}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    res = {"disponible": False, "error": None,
           "barrio": None, "sector_catastral": None, "localidad": None,
           "upz": None, "estrato": None, "uso_economico": None,
           "clase_suelo": None, "valor_ref_m2": None, "codigo_manzana": None,
           "codigo_lote": None}

    # Lote (identifica predio y manzana)
    r_lote = _q_bbox("catastro/lote", 0, lon, lat, "LOTCODIGO,MANZCODIGO,LOTUPREDIA", max_features=10)
    if r_lote.get("features"):
        p = r_lote["features"][0].get("properties", {})
        res["codigo_lote"] = p.get("LOTCODIGO")
        res["codigo_manzana"] = p.get("MANZCODIGO")
        mz = p.get("MANZCODIGO")

    # Sector catastral con NOMBRE (barrio oficial)
    r_sec = _q_bbox("catastro/sectorcatastral", 0, lon, lat, "SCACODIGO,SCANOMBRE,SCATIPO")
    if r_sec.get("features"):
        p = r_sec["features"][0].get("properties", {})
        res["sector_catastral"] = p.get("SCACODIGO")
        res["barrio"] = p.get("SCANOMBRE")

    # Uso económico predominante por MANZANA (exacto si tenemos el código)
    mz = res.get("codigo_manzana")
    if mz:
        r_uso = _q_capa("catastro/usopredominante", 0, f"MANCODIGO='{mz}'",
                        "MANCODIGO,GRUPOUSOECON,ANO")
        if not r_uso.get("features"):
            r_uso = _q_bbox("catastro/usopredominante", 0, lon, lat, "MANCODIGO,GRUPOUSOECON,ANO")
    else:
        r_uso = _q_bbox("catastro/usopredominante", 0, lon, lat, "MANCODIGO,GRUPOUSOECON,ANO")
    if r_uso.get("features"):
        p = r_uso["features"][0].get("properties", {})
        res["uso_economico"] = p.get("GRUPOUSOECON")

    # Estrato (manzanas de estrato)
    r_est = _q_bbox("ordenamientoterritorial/estratificacion", 1, lon, lat, "CODIGO_MANZANA,ESTRATO")
    if r_est.get("features"):
        p = r_est["features"][0].get("properties", {})
        res["estrato"] = p.get("ESTRATO")

    # UPZ
    r_upz = _q_bbox("ordenamientoterritorial/unidadplaneamientozonal", 0, lon, lat,
                    "CODIGO_UPZ,NOMBRE")
    if r_upz.get("features"):
        p = r_upz["features"][0].get("properties", {})
        res["upz"] = p.get("NOMBRE")

    # Localidad
    r_loc = _q_bbox("ordenamientoterritorial/localidad", 0, lon, lat, "LOCCODIGO,LOCNOMBRE")
    if r_loc.get("features"):
        p = r_loc["features"][0].get("properties", {})
        res["localidad"] = p.get("LOCNOMBRE")

    # Suelo (clasificación POT vigente)
    r_sue = _q_bbox("ordenamientoterritorial/suelo", 0, lon, lat, "SUECODIGO,SUECSUELO,SUEAADMIN")
    if r_sue.get("features"):
        p = r_sue["features"][0].get("properties", {})
        cs = p.get("SUECSUELO")
        res["clase_suelo"] = {1: "Urbano", 2: "Rural", 3: "Expansión"}.get(cs, f"Suelo {cs}")

    # Valor de referencia (m2 por manzana)
    r_val = _q_bbox("catastro/valorreferencia", 0, lon, lat, "MANCODIGO,V_REF,ANO")
    if r_val.get("features"):
        p = r_val["features"][0].get("properties", {})
        res["valor_ref_m2"] = p.get("V_REF")

    res["disponible"] = bool(res["barrio"] or res["localidad"] or res["estrato"]
                             or res["uso_economico"] or res["clase_suelo"])
    if not res["disponible"]:
        res["error"] = "entorno sin coincidencia en capas de Bogotá"
    _cache_set(cache_key, res)
    return res


# ── 2. Construcción (pisos) ─────────────────────────────────────────────────

def consultar_construccion(lat: float, lon: float) -> dict[str, Any]:
    cache_key = f"bog_const|{round(lat, 5)}|{round(lon, 5)}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    res = {"disponible": False, "error": None, "tipo_construccion": None,
           "total_pisos": None, "area_construida": None, "codigo_construccion": None}
    r = _q_bbox("catastro/construccion", 0, lon, lat,
                "CONCODIGO,CONNPISOS,CONALTURA,LOTECODIGO", max_features=10)
    if r.get("features"):
        p = r["features"][0].get("properties", {})
        res["codigo_construccion"] = p.get("CONCODIGO")
        res["total_pisos"] = p.get("CONNPISOS")
        res["altura"] = p.get("CONALTURA")
        res["tipo_construccion"] = "Edificación" if (p.get("CONNPISOS") or 0) > 1 else "Edificación"
        res["disponible"] = True
    else:
        res["error"] = "construcción sin coincidencia en Bogotá"
    _cache_set(cache_key, res)
    return res


# ── 3. Amenazas y riesgos (IDIGER) ──────────────────────────────────────────

def consultar_amenazas(lat: float, lon: float) -> dict[str, Any]:
    cache_key = f"bog_riesgo|{round(lat, 5)}|{round(lon, 5)}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    capas = {
        "movimiento_masa_urbano": (2, "AMENAZA"),
        "respuesta_sismica": (7, "ZONA_RESPUESTA"),
        "zonificacion_geotecnica": (8, "GEOTECNIA"),
    }
    res = {"disponible": False, "error": None}
    for nombre, (lid, campo) in capas.items():
        r = _q_bbox("emergencias/gestionriesgos", lid, lon, lat, campo, max_features=3)
        if r.get("features"):
            p = r["features"][0].get("properties", {})
            valor = p.get(campo)
            res[nombre] = {"intersecta": bool(valor), "nivel": valor or None}
        else:
            res[nombre] = {"intersecta": False, "nivel": None}
    res["disponible"] = any(
        (res[k].get("intersecta") if isinstance(res.get(k), dict) else False) for k in capas)
    if not res["disponible"]:
        res["error"] = "sin coincidencia de amenazas/riesgos en Bogotá (IDIGER)"
    _cache_set(cache_key, res)
    return res


# ── 4. Enriquecimiento integral por punto (Bogotá no expone NUPRE en abierto) ─

def enriquecer_por_punto(lat: float = None, lon: float = None) -> dict[str, Any]:
    """Pipeline por coordenadas (no hay resolución por código en abierto)."""
    if lat is None or lon is None:
        return {"disponible": False, "error": "sin coordenadas", "predio": {}}
    res: dict[str, Any] = {"disponible": False, "error": None, "predio": {}}
    res["lat"] = float(lat)
    res["lon"] = float(lon)
    res["resolucion"] = "por_punto_referencial"
    res["entorno"] = consultar_entorno_urbano(float(lat), float(lon))
    res["construccion"] = consultar_construccion(float(lat), float(lon))
    res["amenazas"] = consultar_amenazas(float(lat), float(lon))
    res["disponible"] = bool(res["entorno"].get("disponible")
                             or res["construccion"].get("disponible")
                             or res["amenazas"].get("disponible"))
    if not res["disponible"]:
        res["error"] = "sin coincidencia catastral en Bogotá para el punto"
    return res


# ── Utilidad (re-export del extractor nacional de código/NUPRE del CTL) ──────
from catastro_predio import extraer_codigo_nupre_de_ctl  # noqa: E402

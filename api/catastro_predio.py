# -*- coding: utf-8 -*-
"""
ARHIAX RE — Resolución catastral del predio REAL (Sprint 2, exactitud de datos)

Cuando el CTL (Certificado de Tradición y Libertad del SNR) trae el CÓDIGO
CATASTRAL (número predial nacional de 30 dígitos) o el NUPRE (p. ej.
"AFT0040BBHC" = codigo_homologado), este módulo consulta EN VIVO el catastro
abierto de Barranquilla (ArcGIS REST "catastro/datosabiertos" + servicios
de ordenamiento POT) y devuelve los datos REALES del predio:

    destino económico (Industrial/Habitacional/Comercial...),
    condición jurídica (No propiedad horizontal / PH),
    tipo y pisos de construcción (capa 310),
    dirección oficial normalizada (capa 105) y sus coordenadas,
    barrio/localidad/estrato oficiales (capas POT de la Alcaldía).

Postura honesta (regla dura del proyecto): SIEMPRE que exista código/NUPRE en
el CTL, los datos del dictamen deben venir de aquí, NO de barrios/tipologías
de demostración. Si el servicio no responde o el predio no se encuentra, se
devuelve disponible=False y el llamador muestra "PENDIENTE DE VERIFICACIÓN"
en lugar de inventar valores.

Nunca lanza: toda función devuelve dicts con disponible/error/fuente.
"""

from __future__ import annotations

import re
import time
from typing import Any, Optional

import requests

UA = {"User-Agent": "ARHIAX-RE/1.0 (Sinergia Consulting Group)"}

# Servicios oficiales de Barranquilla (Alcaldía — datos abiertos)
BASE_CATASTRO = "https://miciudad.barranquilla.gov.co/gis/rest/services/catastro/datosabiertos/MapServer"
BASE_ORDENAMIENTO = "https://miciudad.barranquilla.gov.co/gis/rest/services/ordenamiento"

# Capas:
#   catastro/datosabiertos: 500 Predio (oculta pero consultable), 105 Dirección,
#                           315 Terreno, 310 Construcción, 320 Manzana
#   catastro/condicion:     condición jurídica por año (capa 5 = 2025)
#   catastro/destinoseconomicos: destino económico por año (capa 5 = 2026)
#   ordenamiento/unidadesadministrativas: 1 Barrios, 3 Localidades
#   ordenamiento/estratificacion: 1 Estratificación por manzanas
#   ordenamiento/planeacion: 4 Tratamientos urbanísticos
CAPA_PREDIO = 500
CAPA_DIRECCION = 105
CAPA_CONSTRUCCION = 310
CAPA_MANZANA = 320

TIMEOUT = 5.0
TTL_CACHE = 3600  # 1 hora

_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


def _cache_get(key: str):
    item = _CACHE.get(key)
    if item and (time.time() - item[0]) < TTL_CACHE:
        return item[1]
    return None


def _cache_set(key: str, res: dict):
    _CACHE[key] = (time.time(), res)


def _get_json(url: str, params: dict, timeout: float = TIMEOUT) -> Optional[dict]:
    """GET con User-Agent ARHIAX. Devuelve JSON o None (red/HTTP/parseo)."""
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
    """Normaliza una feature de ArcGIS REST (f=json) a GeoJSON-like.

    ArcGIS devuelve "attributes" (tabla) y "geometry" con formato propio
    (Point: {x,y}; polígono: {rings: [...]}). Aquí se traduce a
    {"properties": {...}, "geometry": {"type": ..., "coordinates": ...}}.
    """
    props = feature.get("attributes") if isinstance(feature, dict) else None
    geom_raw = feature.get("geometry") if isinstance(feature, dict) else None
    geom = None
    if isinstance(geom_raw, dict):
        if "x" in geom_raw and "y" in geom_raw and geom_raw.get("x") is not None:
            geom = {"type": "Point", "coordinates": [float(geom_raw["x"]), float(geom_raw["y"])]}
        elif geom_raw.get("rings"):
            rings = geom_raw["rings"]
            geom = {"type": "Polygon", "coordinates": [[[float(p[0]), float(p[1])] for p in ring] for ring in rings]}
        elif geom_raw.get("paths"):
            paths = geom_raw["paths"]
            geom = {"type": "MultiLineString", "coordinates": [[[float(p[0]), float(p[1])] for p in path] for path in paths]}
    return {"properties": props or {}, "geometry": geom}


def _query_capa(base: str, capa: int, where: str, out_fields: str = "*",
                max_features: int = 5, return_geometry: bool = False,
                timeout: float = TIMEOUT) -> dict[str, Any]:
    """Consulta una capa ArcGIS con WHERE textual. Devuelve dict normalizado."""
    params = {
        "where": where,
        "outFields": out_fields,
        "outSR": "4326",
        "returnGeometry": "true" if return_geometry else "false",
        "f": "json",
        "resultRecordCount": str(max_features),
    }
    data = _get_json(f"{base}/{capa}/query", params, timeout)
    if data is None:
        return {"disponible": False, "features": [], "error": "servicio sin respuesta"}
    features = [_norm_feature(f) for f in data.get("features", [])]
    return {"disponible": True, "features": features, "total": len(features), "error": None}


def _query_punto(base: str, capa: int, lon: float, lat: float,
                 out_fields: str = "*", max_features: int = 5,
                 timeout: float = TIMEOUT) -> dict[str, Any]:
    """Consulta una capa por intersección de punto (geometría)."""
    import json as _json
    params = {
        "geometry": _json.dumps({"x": lon, "y": lat, "spatialReference": {"wkid": 4326}}),
        "geometryType": "esriGeometryPoint",
        "spatialRel": "esriSpatialRelIntersects",
        "inSR": "4326", "outSR": "4326",
        "outFields": out_fields,
        "returnGeometry": "false",
        "f": "json",
        "resultRecordCount": str(max_features),
    }
    data = _get_json(f"{base}/{capa}/query", params, timeout)
    if data is None:
        return {"disponible": False, "features": [], "error": "servicio sin respuesta"}
    features = [_norm_feature(f) for f in data.get("features", [])]
    return {"disponible": True, "features": features, "total": len(features), "error": None}


def _centro_punto(feature: dict) -> Optional[tuple]:
    """Extrae (lon, lat) del centroide de una feature (punto o polígono)."""
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


# ── 1. Predio por código catastral / NUPRE (capa 500) ────────────────────────

def consultar_predio_por_codigo(codigo_catastral: str = None, nupre: str = None) -> dict[str, Any]:
    """Consulta la capa 500 (Predio) por número predial nacional o NUPRE.

    Retorna (si encuentra): destino_economico, tipo_predio, estrato, estado_fmi,
    area_catastral_terreno, codigo_homologado, numero_predial_nacional, globalid.
    Nunca lanza.
    """
    codigo = (codigo_catastral or "").strip()
    nupre = (nupre or "").strip()
    if not codigo and not nupre:
        return {"disponible": False, "error": "sin código catastral ni NUPRE"}

    cache_key = f"predio|{codigo}|{nupre}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    res: dict[str, Any] = {
        "disponible": False, "error": "predio no encontrado en capa 500",
        "codigo_catastral": codigo or None, "nupre": nupre or None,
        "destino_economico": None, "tipo_predio": None, "estrato": None,
        "estado_fmi": None, "area_catastral_terreno": None, "globalid": None,
        "fuente": {"servicio": f"{BASE_CATASTRO}/{CAPA_PREDIO}", "consulta": "capa 500 Predio"},
    }

    campos = ("numero_predial_nacional,numero_predial_anterior,codigo_homologado,"
              "destinacion_economica,tipo_predio,estrato,estado_fmi,"
              "area_catastral_terreno,globalid,tipo_vivienda")

    # 1er intento: número predial nacional exacto (30 dígitos del CTL)
    resultados = []
    if re.fullmatch(r"\d{20,30}", codigo):
        r = _query_capa(BASE_CATASTRO, CAPA_PREDIO,
                        f"numero_predial_nacional='{codigo}'", campos)
        resultados.append(r)
        if not (r.get("features")):
            # fallback: prefijo (la capa puede recortar ceros finales)
            r2 = _query_capa(BASE_CATASTRO, CAPA_PREDIO,
                             f"numero_predial_nacional LIKE '{codigo[:24]}%'", campos)
            resultados.append(r2)
    # 2º intento: NUPRE alfanumérico (codigo_homologado p. ej. AFT0040BBHC)
    if nupre and not any(r.get("features") for r in resultados):
        r3 = _query_capa(BASE_CATASTRO, CAPA_PREDIO,
                         f"codigo_homologado='{nupre}'", campos)
        resultados.append(r3)

    feature = None
    for r in resultados:
        if r.get("features"):
            feature = r["features"][0]
            break

    if not feature:
        res["error"] = "predio no encontrado en capa 500 (código/NUPRE sin coincidencia)"
        _cache_set(cache_key, res)
        return res

    p = feature.get("properties", {})
    res.update({
        "disponible": True,
        "error": None,
        "numero_predial_nacional": p.get("numero_predial_nacional") or codigo or None,
        "numero_predial_anterior": p.get("numero_predial_anterior"),
        "nupre": p.get("codigo_homologado") or nupre or None,
        "destino_economico": p.get("destinacion_economica"),
        "tipo_predio": p.get("tipo_predio"),
        "tipo_vivienda": p.get("tipo_vivienda"),
        "estrato": p.get("estrato"),
        "estado_fmi": p.get("estado_fmi"),
        "area_catastral_terreno": p.get("area_catastral_terreno"),
        "globalid": p.get("globalid"),
    })
    _cache_set(cache_key, res)
    return res


# ── 2. Dirección oficial y coordenadas (capa 105 por cr_predio_guid) ─────────

def consultar_direccion_y_punto(globalid_predio: str = None, codigo_catastral: str = None) -> dict[str, Any]:
    """Busca la dirección oficial del predio en la capa 105 y su punto.

    Se enlaza por cr_predio_guid = globalid del predio (capa 500). Si no hay
    globalid, cae a búsqueda textual por código catastral en los GUIDs.
    """
    if not globalid_predio and not codigo_catastral:
        return {"disponible": False, "error": "sin globalid ni código"}
    cache_key = f"dir|{globalid_predio}|{codigo_catastral}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    res = {"disponible": False, "error": "dirección no encontrada", "direccion_oficial": None,
           "lat": None, "lon": None, "fuente": {"servicio": f"{BASE_CATASTRO}/{CAPA_DIRECCION}"}}
    campos = ("clase_via_principal,valor_via_principal,letra_via_principal,"
              "valor_via_generadora,letra_via_generadora,numero_predio,complemento,"
              "nombre_predio,es_direccion_principal,cr_predio_guid,cr_terreno_guid")

    r = None
    if globalid_predio:
        guid = globalid_predio.replace("{", "").replace("}", "")
        r = _query_capa(BASE_CATASTRO, CAPA_DIRECCION,
                        f"cr_predio_guid = '{globalid_predio}'", campos, return_geometry=True)
        if not r.get("features"):
            r = _query_capa(BASE_CATASTRO, CAPA_DIRECCION,
                            f"cr_predio_guid = '{{{guid}}}'", campos, return_geometry=True)

    if r and r.get("features"):
        feats = r["features"]
    else:
        return res

    # Preferir dirección principal
    feats = sorted(feats, key=lambda f: (f.get("properties", {}).get("es_direccion_principal") != 1))
    for f in feats:
        p = f.get("properties", {})
        c = _centro_punto(f)
        if not c:
            continue
        clase = p.get("clase_via_principal") or ""
        via = p.get("valor_via_principal") or ""
        letra = p.get("letra_via_principal") or ""
        gen = p.get("valor_via_generadora") or ""
        letra_gen = p.get("letra_via_generadora") or ""
        num = p.get("numero_predio") or ""
        comp = (p.get("complemento") or "").strip()
        oficial = f"{clase} {via}{letra} # {gen}{letra_gen}-{num}".replace("  ", " ").strip()
        if comp:
            oficial = f"{oficial} {comp}"
        res.update({
            "disponible": True, "error": None,
            "direccion_oficial": oficial,
            "nombre_predio": p.get("nombre_predio"),
            "complemento": comp,
            "lat": c[1], "lon": c[0],
            "cr_terreno_guid": p.get("cr_terreno_guid"),
        })
        break
    _cache_set(cache_key, res)
    return res


# ── 3. Construcción (capa 310): tipo, pisos, altura ──────────────────────────

def consultar_construccion(lat: float, lon: float) -> dict[str, Any]:
    """Consulta la capa 310 (Construcción) por el punto del predio."""
    cache_key = f"const|{round(lat, 5)}|{round(lon, 5)}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    res = {"disponible": False, "error": "sin construcción", "tipo_construccion": None,
           "total_pisos": None, "altura_total_construccion": None, "area_construida": None}
    r = _query_punto(BASE_CATASTRO, CAPA_CONSTRUCCION, lon, lat,
                     "tipo_construccion,total_pisos,total_sotanos,total_mezanines,total_semisotanos,"
                     "altura_total_construccion,st_area(shape),local_id,estado_construccion")
    if r.get("features"):
        p = r["features"][0].get("properties", {})
        res.update({
            "disponible": True, "error": None,
            "tipo_construccion": p.get("tipo_construccion"),
            "total_pisos": p.get("total_pisos"),
            "total_sotanos": p.get("total_sotanos"),
            "altura_total_construccion": p.get("altura_total_construccion"),
            "area_construida": p.get("st_area(shape)"),
            "estado_construccion": p.get("estado_construccion"),
        })
    _cache_set(cache_key, res)
    return res


# ── 4. Condición jurídica y destino económico vigente (servicios por año) ────

def consultar_condicion_destino(codigo_catastral: str = None, lat: float = None, lon: float = None) -> dict[str, Any]:
    """Consulta los servicios temáticos (condición 2025, destino 2026) por terreno."""
    cache_key = f"cond|{codigo_catastral}|{round(lat or 0, 5)}|{round(lon or 0, 5)}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    res = {"disponible": False, "condicion_juridica": None, "destino_vigente": None, "error": None}

    # Servicios temáticos se consultan por intersección de punto (terreno del predio)
    if lat is not None and lon is not None:
        r_cond = _query_punto(
            "https://miciudad.barranquilla.gov.co/gis/rest/services/catastro/condicion/MapServer",
            5, lon, lat, "terreno,condicion,anio")
        if r_cond.get("features"):
            p = r_cond["features"][0].get("properties", {})
            res["condicion_juridica"] = p.get("condicion")
        r_dest = _query_punto(
            "https://miciudad.barranquilla.gov.co/gis/rest/services/catastro/destinoseconomicos/MapServer",
            5, lon, lat, "terreno,destino,anio")
        if r_dest.get("features"):
            p = r_dest["features"][0].get("properties", {})
            res["destino_vigente"] = p.get("destino")
    # Fallback por terreno (código catastral exacto)
    if codigo_catastral and (res["condicion_juridica"] is None or res["destino_vigente"] is None):
        if res["condicion_juridica"] is None:
            r_cond = _query_capa(
                "https://miciudad.barranquilla.gov.co/gis/rest/services/catastro/condicion/MapServer",
                5, f"terreno='{codigo_catastral}'", "terreno,condicion,anio")
            if r_cond.get("features"):
                res["condicion_juridica"] = r_cond["features"][0].get("properties", {}).get("condicion")
        if res["destino_vigente"] is None:
            r_dest = _query_capa(
                "https://miciudad.barranquilla.gov.co/gis/rest/services/catastro/destinoseconomicos/MapServer",
                5, f"terreno='{codigo_catastral}'", "terreno,destino,anio")
            if r_dest.get("features"):
                res["destino_vigente"] = r_dest["features"][0].get("properties", {}).get("destino")

    res["disponible"] = bool(res["condicion_juridica"] is not None or res["destino_vigente"] is not None)
    if not res["disponible"]:
        res["error"] = "condición/destino sin coincidencia"
    _cache_set(cache_key, res)
    return res


# ── 5. Barrio / localidad / estrato / tratamiento oficiales (POT Alcaldía) ───

def consultar_entorno_urbano(lat: float, lon: float) -> dict[str, Any]:
    """Consulta barrio, localidad, estrato y tratamiento urbanístico por punto.

    Capas POT oficiales de la Alcaldía (unidadesadministrativas → Barrios,
    estratificación por manzanas, planeación → tratamientos). Esta es la fuente
    con NOMBRE del barrio (p. ej. 'Barrio Abajo'), no inferencias de OSM.
    """
    cache_key = f"entorno|{round(lat, 5)}|{round(lon, 5)}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    res = {"disponible": False, "error": None, "barrio": None, "localidad": None,
           "estrato": None, "tratamiento": None, "pieza_urbana": None}

    r_barrios = _query_punto(
        f"{BASE_ORDENAMIENTO}/unidadesadministrativas/MapServer", 1, lon, lat,
        "nombre_barrio,identificador,localidad,nombre_pieza")
    if r_barrios.get("features"):
        p = r_barrios["features"][0].get("properties", {})
        res["barrio"] = p.get("nombre_barrio")
        res["identificador_barrio"] = p.get("identificador")
        res["localidad"] = p.get("localidad")
        res["pieza_urbana"] = p.get("nombre_pieza")

    r_est = _query_punto(
        f"{BASE_ORDENAMIENTO}/estratificacion/MapServer", 1, lon, lat,
        "estratificacion,nombre_barrio,codigo_manzana")
    if r_est.get("features"):
        p = r_est["features"][0].get("properties", {})
        res["estrato"] = p.get("estratificacion")
        if not res["barrio"]:
            res["barrio"] = p.get("nombre_barrio")
        res["codigo_manzana"] = p.get("codigo_manzana")

    r_trat = _query_punto(
        f"{BASE_ORDENAMIENTO}/planeacion/MapServer", 4, lon, lat,
        "tratamiento,tipo_tratamiento,altura_maxima")
    if r_trat.get("features"):
        p = r_trat["features"][0].get("properties", {})
        res["tratamiento"] = p.get("tratamiento")
        res["tipo_tratamiento"] = p.get("tipo_tratamiento")
        res["altura_maxima"] = p.get("altura_maxima")

    res["disponible"] = bool(res["barrio"] or res["estrato"] or res["tratamiento"])
    if not res["disponible"]:
        res["error"] = "entorno sin coincidencia en capas POT"
    _cache_set(cache_key, res)
    return res


# ── 6. Enriquecimiento integral desde el CTL ─────────────────────────────────

def enriquecer_desde_ctl(codigo_catastral: str = None, nupre: str = None,
                         lat_hint: float = None, lon_hint: float = None) -> dict[str, Any]:
    """Pipeline completo: código/NUPRE del CTL → datos reales del predio.

    Devuelve un único dict con todo lo resuelto (o disponible=False honesto).
    Nunca lanza y nunca inventa datos.
    """
    base = consultar_predio_por_codigo(codigo_catastral, nupre)
    if not base.get("disponible"):
        # Sin predio en capa 500: aún podemos intentar entorno por coordenadas hint
        res = {"disponible": False, "error": base.get("error"), "predio": base}
        if lat_hint is not None and lon_hint is not None:
            res["entorno"] = consultar_entorno_urbano(lat_hint, lon_hint)
        return res

    res: dict[str, Any] = {"disponible": True, "error": None, "predio": base}

    # Coordenadas por dirección oficial (capa 105 enlazada por globalid)
    dir_info = consultar_direccion_y_punto(base.get("globalid"), codigo_catastral)
    lat, lon = None, None
    if dir_info.get("disponible"):
        res["direccion_oficial"] = dir_info.get("direccion_oficial")
        res["direccion_complemento"] = dir_info.get("complemento")
        res["cr_terreno_guid"] = dir_info.get("cr_terreno_guid")
        lat, lon = dir_info.get("lat"), dir_info.get("lon")
    elif lat_hint is not None and lon_hint is not None:
        lat, lon = lat_hint, lon_hint
    if lat is not None and lon is not None:
        res["lat"] = lat
        res["lon"] = lon

    # Construcción + condición/destino + entorno, solo si hay coordenadas
    if lat is not None and lon is not None:
        const = consultar_construccion(lat, lon)
        if const.get("disponible"):
            res["construccion"] = const
        res["condicion"] = consultar_condicion_destino(codigo_catastral, lat, lon)
        res["entorno"] = consultar_entorno_urbano(lat, lon)
    else:
        res["condicion"] = consultar_condicion_destino(codigo_catastral, None, None)

    return res


# ── Utilidad: extraer código catastral y NUPRE del texto de un CTL ───────────

_RE_CODIGO_CATASTRAL = re.compile(r"(?:CODIGO\s*CATASTRAL|C[OÓ]DIGO\s*CATASTRAL)\s*[:\-]?\s*(\d{20,30})", re.IGNORECASE)
_RE_NUPRE = re.compile(r"NUPRE\s*[:\-]?\s*([A-Z0-9]{8,40})", re.IGNORECASE)


def extraer_codigo_nupre_de_ctl(texto_pdf: str) -> dict:
    """Extrae (codigo_catastral, nupre) del texto de un CTL SNR.

    El CTL moderno del SNR incluye:
        CODIGO CATASTRAL: 080010102000001710004000000000
        NUPRE: AFT0040BBHC          <- NUPRE alfanumérico (codigo homologado)
    """
    if not texto_pdf:
        return {"codigo_catastral": None, "nupre": None}
    codigo = None
    m = _RE_CODIGO_CATASTRAL.search(texto_pdf)
    if m:
        cand = m.group(1)
        if re.fullmatch(r"\d{30}", cand):
            codigo = cand
        elif len(cand) >= 25:
            # El parser puede pegar el texto siguiente (p. ej. "COD CATASTRAL ANT:")
            codigo = re.match(r"\d{30}", cand).group(0) if re.match(r"\d{30}", cand) else cand[:30]
    nupre = None
    m2 = _RE_NUPRE.search(texto_pdf)
    if m2:
        cand2 = m2.group(1).strip()
        # Excluir capturas espurias (fechas/palabras largas sin formato AFT/08001)
        if re.match(r"^(AFT|NPR|08001)", cand2, re.IGNORECASE) and len(cand2) >= 8:
            nupre = cand2
    return {"codigo_catastral": codigo, "nupre": nupre}

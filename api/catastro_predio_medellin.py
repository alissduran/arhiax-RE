# -*- coding: utf-8 -*-
"""
ARHIAX RE — Resolución catastral del predio REAL en Medellín (Sprint 3, expansión)

Misma interfaz que catastro_predio.py (Barranquilla) para que el dictamen
despache por ciudad sin cambiar su lógica. Consulta EN VIVO el servidormapas
de la Alcaldía de Medellín:

    destino/uso económico  -> mapas_nacionales/VC_Catastro l3 "Uso del predio"
                              (numero_predial 30 dígitos, codigo_homologado/NUPRE)
    barrio/comuna/estrato   -> ServiciosCatastro/ide_catastro l1/l2 +
                               VC_Catastro_VCT l10 (estrato socioeconómico)
    lote/área/construcción  -> ServiciosCatastro/Base_Catastral l3/l5
    clasificación suelo     -> ordenamiento_ter/VM_02_Clasificacion_Suelo l4
    tratamiento urbanístico -> ordenamiento_ter/VM_22_Tratamientos_Urbanos l0
    amenazas                -> ambiente_dllo_sost/VC_Gestion_Riesgo l1/l2/l5

Nunca lanza; disponible=False honesto si el servicio no responde.
"""

from __future__ import annotations

import re
import time
from typing import Any, Optional

import requests

UA = {"User-Agent": "ARHIAX-RE/1.0 (Sinergia Consulting Group)"}
BASE = "https://www.medellin.gov.co/servidormapas/rest/services"

TIMEOUT = 6.0
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
    """Consulta una capa por WHERE textual (servidor ArcGIS REST, f=json)."""
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


def _q_punto(svc_path: str, lid: int, lon: float, lat: float,
             out_fields: str = "*", max_features: int = 5,
             timeout: float = TIMEOUT) -> dict[str, Any]:
    """Consulta una capa por intersección de punto (geometría)."""
    import json as _json
    params = {
        "geometry": _json.dumps({"x": lon, "y": lat, "spatialReference": {"wkid": 4326}}),
        "geometryType": "esriGeometryPoint", "spatialRel": "esriSpatialRelIntersects",
        "inSR": "4326", "outSR": "4326", "outFields": out_fields,
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


# ── 1. Predio por código catastral / NUPRE (capa Uso del predio) ─────────────

def consultar_predio_por_codigo(codigo_catastral: str = None, nupre: str = None) -> dict[str, Any]:
    """Consulta 'Uso del predio' (VC_Catastro l3) por número predial nacional o NUPRE.

    Retorna: destino_economico, estrato, direccion (cruda), cbml, numero_predial,
    codigo_homologado, codigo_postal, lat/lon, tipo_punto.
    """
    codigo = (codigo_catastral or "").strip()
    nupre = (nupre or "").strip()
    if not codigo and not nupre:
        return {"disponible": False, "error": "sin código catastral ni NUPRE"}
    cache_key = f"med_predio|{codigo}|{nupre}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    res: dict[str, Any] = {
        "disponible": False, "error": "predio no encontrado",
        "codigo_catastral": codigo or None, "nupre": nupre or None,
        "destino_economico": None, "estrato": None, "direccion_cruda": None,
        "numero_predial_nacional": None, "cbml": None,
        "lat": None, "lon": None,
        "fuente": {"servicio": f"{BASE}/mapas_nacionales/VC_Catastro/MapServer/3",
                   "consulta": "Uso del predio"},
    }
    campos = ("numero_predial,codigo_homologado,destinacion,estrato,direccion,"
              "cbml,codigo_postal,longitud,latitud,nombre_predio")
    resultados = []
    if re.fullmatch(r"\d{20,30}", codigo):
        r1 = _q_capa("mapas_nacionales/VC_Catastro", 3,
                     f"numero_predial='{codigo}'", campos)
        resultados.append(r1)
        if not r1.get("features"):
            r2 = _q_capa("mapas_nacionales/VC_Catastro", 3,
                         f"numero_predial LIKE '{codigo[:24]}%'", campos)
            resultados.append(r2)
    if nupre and not any(r.get("features") for r in resultados):
        r3 = _q_capa("mapas_nacionales/VC_Catastro", 3,
                     f"codigo_homologado='{nupre}'", campos)
        resultados.append(r3)

    feature = None
    for r in resultados:
        if r.get("features"):
            feature = r["features"][0]
            break
    if not feature:
        _cache_set(cache_key, res)
        return res

    p = feature.get("properties", {})
    res.update({
        "disponible": True, "error": None,
        "numero_predial_nacional": p.get("numero_predial") or codigo or None,
        "nupre": p.get("codigo_homologado") or nupre or None,
        "destino_economico": p.get("destinacion"),
        "estrato": p.get("estrato"),
        "direccion_cruda": p.get("direccion"),
        "cbml": p.get("cbml"),
        "codigo_postal": p.get("codigo_postal"),
        "nombre_predio": p.get("nombre_predio"),
        "lat": p.get("latitud"),
        "lon": p.get("longitud"),
        "tipo_punto": p.get("tipo_punto"),
    })
    _cache_set(cache_key, res)
    return res


# ── 1b. Predio por punto (dirección sin CTL) ────────────────────────────────

def consultar_predio_por_punto(lat: float, lon: float, radio_grados: float = 0.003) -> dict[str, Any]:
    """Busca el 'Uso del predio' más cercano a las coordenadas (VC_Catastro l3).

    La capa de uso es de tipo PUNTO (esriGeometryPoint), por lo que la consulta
    se hace por BBOX alrededor de las coordenadas y se elige el feature más
    cercano por distancia a los atributos longitud/latitud del propio registro.
    """
    cache_key = f"med_punto|{round(lat, 5)}|{round(lon, 5)}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    res: dict[str, Any] = {
        "disponible": False, "error": "predio no encontrado por punto",
        "destino_economico": None, "estrato": None, "direccion_cruda": None,
        "numero_predial_nacional": None, "cbml": None, "codigo_homologado": None,
        "lat": lat, "lon": lon, "fuente": {"servicio": "VC_Catastro l3 (por punto)"},
    }
    campos = ("numero_predial,codigo_homologado,destinacion,estrato,direccion,"
              "cbml,codigo_postal,longitud,latitud")
    try:
        params = {
            "where": "1=1", "outFields": campos, "outSR": "4326",
            "geometry": f"{lon-radio_grados},{lat-radio_grados},{lon+radio_grados},{lat+radio_grados}",
            "geometryType": "esriGeometryEnvelope", "inSR": "4326",
            "returnGeometry": "false", "f": "json", "resultRecordCount": "20",
        }
        data = _get_json(f"{BASE}/mapas_nacionales/VC_Catastro/MapServer/3/query", params)
        feats = data.get("features", []) if isinstance(data, dict) else []
    except Exception as e:
        res["error"] = f"error de consulta por punto: {e}"
        _cache_set(cache_key, res)
        return res

    if not feats:
        res["error"] = "sin features de uso del predio en el radio del punto"
        _cache_set(cache_key, res)
        return res

    def _dist(f):
        p = f.get("attributes", {}) or {}
        try:
            dlat = float(p.get("latitud") or lat) - lat
            dlon = float(p.get("longitud") or lon) - lon
            return dlat * dlat + dlon * dlon
        except Exception:
            return 1e9

    feats.sort(key=_dist)
    p = feats[0].get("attributes", {}) or {}
    res.update({
        "disponible": True, "error": None,
        "numero_predial_nacional": p.get("numero_predial"),
        "nupre": p.get("codigo_homologado"),
        "codigo_homologado": p.get("codigo_homologado"),
        "destino_economico": p.get("destinacion"),
        "estrato": p.get("estrato"),
        "direccion_cruda": p.get("direccion"),
        "cbml": p.get("cbml"),
        "codigo_postal": p.get("codigo_postal"),
        "distancia_aprox_km": round((_dist(feats[0]) ** 0.5) * 111.0, 3),
    })
    _cache_set(cache_key, res)
    return res


# ── 2. Entorno urbano: barrio / comuna / estrato / suelo / tratamiento ───────

def consultar_entorno_urbano(lat: float, lon: float) -> dict[str, Any]:
    """Barrio, comuna, estrato, clasificación de suelo y tratamiento por punto."""
    cache_key = f"med_entorno|{round(lat, 5)}|{round(lon, 5)}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    res = {"disponible": False, "error": None, "barrio": None, "comuna": None,
           "localidad": None, "estrato": None, "clase_suelo": None,
           "tratamiento": None, "codigo_manzana": None,
           # Parámetros de edificabilidad del POT (VM_22 l0) — Sprint 3:
           # índice de construcción máximo, densidad máxima, franja de altura
           # y altura normativa (pisos) cuando el polígono la expone.
           "indice_construccion_max": None, "densidad_max": None,
           "franja_altura": None, "altura_normativa": None,
           "categoria_tratamiento": None, "fecha_norma": None}

    # Barrio y comuna con NOMBRE (VC_Limite_Politico_Admtivo l0/l1). La capa
    # ide_catastro expone los mismos polígonos pero no responde a intersección
    # por punto; los límites político-administrativos sí.
    r_bar = _q_punto("mapas_nacionales/VC_Limite_Politico_Admtivo", 0, lon, lat,
                     "nombre,codigo,limitecomunacorregimientoid")
    if r_bar.get("features"):
        p = r_bar["features"][0].get("properties", {})
        res["barrio"] = p.get("nombre")
        res["codigo_barrio"] = p.get("codigo")
    r_com = _q_punto("mapas_nacionales/VC_Limite_Politico_Admtivo", 1, lon, lat,
                     "nombre,codigo")
    if r_com.get("features"):
        p = r_com["features"][0].get("properties", {})
        res["comuna"] = p.get("nombre")
        res["codigo_comuna"] = p.get("codigo")

    # Estrato socioeconómico (VC_Catastro_VCT l10)
    r_est = _q_punto("vivienda_ciudad_terri/VC_Catastro_VCT", 10, lon, lat, "estrato,comuna,barrio")
    if r_est.get("features"):
        p = r_est["features"][0].get("properties", {})
        res["estrato"] = p.get("estrato")
        if not res["comuna"]:
            res["comuna"] = p.get("comuna")

    # Clasificación de suelo (VM_02 l4)
    r_suelo = _q_punto("ordenamiento_ter/VM_02_Clasificacion_Suelo", 4, lon, lat,
                       "clase_suelo,categoria_suelo,codigo_tratamiento")
    if r_suelo.get("features"):
        p = r_suelo["features"][0].get("properties", {})
        res["clase_suelo"] = p.get("clase_suelo")
        res["categoria_suelo"] = p.get("categoria_suelo")

    # Tratamiento urbanístico y parámetros de edificabilidad (VM_22 l0).
    # La capa oficial del POT de Medellín (Acuerdo 48/2014, servidormapas) expone
    # por polígono normativo: tratamiento, índice de construcción máximo,
    # densidad máxima, franja de altura y altura normativa en pisos cuando aplica.
    r_trat = _q_punto("ordenamiento_ter/VM_22_Tratamientos_Urbanos", 0, lon, lat,
                      "tratamiento,tipo,codigo_tramiento,alturavariable,"
                      "indiceconstruccmax,densidadmax,franjabase,alturanormativa,"
                      "categoria_tratamiento,fecha_adopcion")
    if r_trat.get("features"):
        p = r_trat["features"][0].get("properties", {})
        res["tratamiento"] = p.get("tratamiento")
        res["tipo_tratamiento"] = p.get("tipo")
        res["codigo_tratamiento"] = p.get("codigo_tramiento")
        res["indice_construccion_max"] = p.get("indiceconstruccmax")
        res["densidad_max"] = p.get("densidadmax")
        res["franja_altura"] = p.get("franjabase")
        res["altura_normativa"] = p.get("alturanormativa")
        res["categoria_tratamiento"] = p.get("categoria_tratamiento")
        res["fecha_norma"] = p.get("fecha_adopcion")

    res["disponible"] = bool(res["barrio"] or res["comuna"] or res["estrato"]
                             or res["clase_suelo"] or res["tratamiento"])
    if not res["disponible"]:
        res["error"] = "entorno sin coincidencia en capas de Medellín"
    _cache_set(cache_key, res)
    return res


# ── 3. Lote y construcción (Base_Catastral l3/l5) ────────────────────────────

def consultar_lote_y_construccion(lat: float, lon: float) -> dict[str, Any]:
    """Lote (cbml, área) y construcción (tipo, pisos, área) por punto."""
    cache_key = f"med_lote|{round(lat, 5)}|{round(lon, 5)}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    res = {"disponible": False, "error": None, "cbml": None, "mz_igac": None,
           "area_lote": None, "tipo_construccion": None, "total_pisos": None,
           "area_construida": None}

    r_lote = _q_punto("ServiciosCatastro/Base_Catastral", 3, lon, lat,
                      "cbml,cobama,numero_predio,mz_igac,area_lote,tipo_lote", max_features=8)
    if r_lote.get("features"):
        p = r_lote["features"][0].get("properties", {})
        res["cbml"] = p.get("cbml")
        res["mz_igac"] = p.get("mz_igac")
        res["area_lote"] = p.get("area_lote")
        res["tipo_lote"] = p.get("tipo_lote")

    r_const = _q_punto("ServiciosCatastro/Base_Catastral", 5, lon, lat,
                       "cbml,tipo_construccion,numero_pisos,area_construida,id_construccion",
                       max_features=8)
    if r_const.get("features"):
        p = r_const["features"][0].get("properties", {})
        res["tipo_construccion"] = p.get("tipo_construccion")
        res["total_pisos"] = p.get("numero_pisos")
        res["area_construida"] = p.get("area_construida")
        res["id_construccion"] = p.get("id_construccion")
        if not res["cbml"]:
            res["cbml"] = p.get("cbml")

    res["disponible"] = bool(res["cbml"] or res["tipo_construccion"] or res["area_lote"])
    if not res["disponible"]:
        res["error"] = "lote/construcción sin coincidencia en Medellín"
    _cache_set(cache_key, res)
    return res


# ── 4. Amenazas (VC_Gestion_Riesgo) ──────────────────────────────────────────

def _es_no_afectacion(valor) -> bool:
    """True si el valor textual indica que NO hay afectación ('Sin afectación',
    'No aplica'...). Antes esos textos se trataban como intersección real y el
    dictamen reportaba 'Afectación Detectada (Sin afectación)'."""
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


def consultar_amenazas(lat: float, lon: float) -> dict[str, Any]:
    """Amenaza por inundación, movimiento en masa, avenida torrencial y sismo."""
    cache_key = f"med_riesgo|{round(lat, 5)}|{round(lon, 5)}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    # Capas: 1 Amenaza Inundaciones, 2 Amenaza Movimiento en Masa,
    #        0 Amenaza Avenidas Torrenciales, 13 Susceptibilidad de sismos
    capas = {
        "inundacion": (1, "categoria,grado_amenaza"),
        "movimiento_masa": (2, "categoria,grado_amenaza"),
        "avenida_torrencial": (0, "categoria,grado_amenaza"),
        "sismo": (13, "categoria,grado_amenaza"),
    }
    res = {"disponible": False, "error": None}
    for nombre, (lid, campos) in capas.items():
        r = _q_punto("ambiente_dllo_sost/VC_Gestion_Riesgo", lid, lon, lat, campos, max_features=3)
        if r.get("features"):
            p = r["features"][0].get("properties", {})
            valor = p.get("grado_amenaza") or p.get("categoria")
            # 'Sin afectación'/'No aplica' NO son intersección (regresión H-GEO)
            intersecta = bool(valor) and not _es_no_afectacion(valor)
            res[nombre] = {
                "intersecta": intersecta,
                "nivel": valor if intersecta else None,
                "categoria": p.get("categoria"),
            }
        else:
            res[nombre] = {"intersecta": False, "nivel": None, "categoria": None}
    res["disponible"] = any(res[k]["intersecta"] for k in capas if isinstance(res.get(k), dict))
    if not res["disponible"]:
        res["error"] = "sin coincidencia de amenazas en Medellín"
    _cache_set(cache_key, res)
    return res


# ── 5. Enriquecimiento integral desde el CTL ─────────────────────────────────

def enriquecer_por_punto(lat: float = None, lon: float = None) -> dict[str, Any]:
    """Igual que enriquecer_desde_ctl pero resolviendo el predio por coordenadas
    (para casos sin CTL/código: la dirección geocodificada ubica el uso)."""
    if lat is None or lon is None:
        return {"disponible": False, "error": "sin coordenadas", "predio": {}}
    base = consultar_predio_por_punto(float(lat), float(lon))
    res: dict[str, Any] = {"disponible": False, "error": None, "predio": base}
    if not base.get("disponible"):
        res["error"] = base.get("error")
        res["entorno"] = consultar_entorno_urbano(float(lat), float(lon))
        return res
    res["disponible"] = True
    res["lat"] = float(lat)
    res["lon"] = float(lon)
    # La resolución por punto es REFERENCIAL (uso del predio más cercano a las
    # coordenadas). No se afirma una dirección catastral exacta: el usuario ya
    # aportó la dirección; se deja sin direccion_oficial para no pisarla.
    res["resolucion"] = "por_punto_referencial"
    res["entorno"] = consultar_entorno_urbano(float(lat), float(lon))
    res["lote"] = consultar_lote_y_construccion(float(lat), float(lon))
    res["amenazas"] = consultar_amenazas(float(lat), float(lon))
    return res


def enriquecer_desde_ctl(codigo_catastral: str = None, nupre: str = None,
                         lat_hint: float = None, lon_hint: float = None) -> dict[str, Any]:
    """Pipeline completo equivalente al de Barranquilla: código/NUPRE del CTL
    → datos reales del predio en Medellín. Nunca lanza."""
    base = consultar_predio_por_codigo(codigo_catastral, nupre)
    if not base.get("disponible"):
        res = {"disponible": False, "error": base.get("error"), "predio": base}
        if lat_hint is not None and lon_hint is not None:
            res["entorno"] = consultar_entorno_urbano(lat_hint, lon_hint)
        return res

    res: dict[str, Any] = {"disponible": True, "error": None, "predio": base}
    lat, lon = base.get("lat"), base.get("lon")
    if (lat is None or lon is None) and lat_hint is not None:
        lat, lon = lat_hint, lon_hint
    if lat is not None and lon is not None:
        res["lat"] = float(lat)
        res["lon"] = float(lon)
        res["direccion_oficial"] = base.get("direccion_cruda")
        res["entorno"] = consultar_entorno_urbano(float(lat), float(lon))
        res["lote"] = consultar_lote_y_construccion(float(lat), float(lon))
        res["amenazas"] = consultar_amenazas(float(lat), float(lon))
    return res


# ── Utilidad: extraer código catastral y NUPRE del texto de un CTL ───────────
# (El CTL del SNR es nacional: mismo formato "CODIGO CATASTRAL: 30 dígitos" y
# "NUPRE: AAB.../08001..."; se reutiliza la función de catastro_predio.py)

from catastro_predio import extraer_codigo_nupre_de_ctl  # noqa: E402  (nacional)

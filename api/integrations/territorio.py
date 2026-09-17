# -*- coding: utf-8 -*-
"""
ARHIAX RE — Verificación territorial por ciudad (Sprint 3, expansión multi-ciudad)

Dispatcher que consulta el servicio institucional de la ciudad indicada y
devuelve un resultado UNIFORME con trazabilidad:

    barranquilla -> ArcGIS REST catastro (FeatureServer 545 + MapServer 315)
    medellin     -> ArcGIS REST POT (servidormapas, capa ClasificacionSuelo)
    cali         -> GeoServer WFS (IDESC: barrios/sectores + clasificación de suelo)
    bogota       -> EN EVALUACIÓN (catastro 503 puntual; IDECA federado; CEL sin API)
    pasto        -> EN EVALUACIÓN (sin endpoint de catastro/POT verificado en vivo aún)

Postura honesta: nunca afirma datos que no obtuvo; si el servicio no responde,
disponible=False y el llamador (dictamen/endpoint) lo declara.
Con caché por celda (~110 m) y TTL de 1 hora.
"""

from __future__ import annotations

import time
from typing import Any

from integrations.arcgis_client import query_layer_bbox
from integrations.wfs_client import get_features_bbox

TIMEOUT = 4.0
TTL_CACHE = 3600
BUFFER = 0.0025  # ~250 m

_CACHE: dict[tuple, tuple[float, dict[str, Any]]] = {}


def _celda(lat: float, lon: float) -> tuple:
    return (round(lat, 3), round(lon, 3))


def _nuevo_resultado(ciudad: str, lat: float, lon: float) -> dict[str, Any]:
    return {
        "ciudad": ciudad,
        "disponible": False,
        "features": [],
        "total_features": 0,
        "resumen": None,
        "error": None,
        "fuente": {},
    }


def _verificar_barranquilla(lat: float, lon: float, res: dict) -> dict:
    from config import get_ciudad
    cfg = get_ciudad("barranquilla")
    base = (cfg.get("arcgis") or {}).get(
        "catastro", "https://miciudad.barranquilla.gov.co/gis/rest/services/catastro/datosabiertos"
    )
    bbox = (lon - BUFFER, lat - BUFFER, lon + BUFFER, lat + BUFFER)
    r_t = query_layer_bbox(f"{base}/MapServer", 315, bbox, max_features=10, timeout=TIMEOUT)
    r_d = query_layer_bbox(f"{base}/FeatureServer", 545, bbox, max_features=10, timeout=TIMEOUT)
    res["disponible"] = bool(r_t.get("disponible") or r_d.get("disponible"))
    res["total_features"] = (r_t.get("total_features", 0) or 0) + (r_d.get("total_features", 0) or 0)
    res["features"] = (r_t.get("features") or [])[:3] + (r_d.get("features") or [])[:3]
    res["error"] = r_t.get("error") or r_d.get("error")
    res["fuente"] = r_t.get("fuente") or r_d.get("fuente") or {}
    if res["disponible"]:
        nupre = None
        if r_t.get("features"):
            nupre = r_t["features"][0].get("properties", {}).get("name")
        res["resumen"] = f"Catastro Barranquilla consultado en vivo (NUPRE: {nupre or 'N/D'})."
    return res


def _verificar_medellin(lat: float, lon: float, res: dict) -> dict:
    from config import get_ciudad
    cfg = get_ciudad("medellin")
    arcgis = cfg.get("arcgis") or {}
    base = (arcgis.get("servidormapas") or "").rstrip("/")
    capa_pot = arcgis.get("capa_pot", "ordenamiento_ter/VM_10_Sistema_Publico_Colectivo")
    if not base:
        res["error"] = "Servicio de Medellín no configurado."
        return res
    bbox = (lon - BUFFER, lat - BUFFER, lon + BUFFER, lat + BUFFER)
    # servidormapas de Medellín es lento e inestable: timeout generoso + reintentos del cliente
    r = query_layer_bbox(f"{base}/{capa_pot}/MapServer", 0, bbox, max_features=10, timeout=12.0)
    res["disponible"] = bool(r.get("disponible"))
    res["total_features"] = r.get("total_features", 0) or 0
    res["features"] = (r.get("features") or [])[:5]
    res["error"] = r.get("error")
    res["fuente"] = r.get("fuente") or {}
    if res["disponible"]:
        trat = None
        if r.get("features"):
            props = r["features"][0].get("properties", {})
            trat = props.get("codigo_tratamiento") or props.get("tratamiento") or props.get("tipo")
        res["resumen"] = (
            f"POT Medellín consultado en vivo ({res['total_features']} feature(s) en el BBOX"
            + (f", tratamiento: {trat}" if trat else "")
            + ")."
        )
    elif not res["error"]:
        res["error"] = "El servicio POT de Medellín no devolvió features en el BBOX del predio."
    return res


def _verificar_cali(lat: float, lon: float, res: dict) -> dict:
    from config import get_ciudad
    cfg = get_ciudad("cali")
    wfs = (cfg.get("wfs") or {})
    url = (wfs.get("url") or "").rstrip("/")
    capa = wfs.get("capa_barrios", "dapm:pdt_dpa_barrios_sectores")
    if not url:
        res["error"] = "Servicio de Cali (IDESC) no configurado."
        return res
    bbox = (lon - BUFFER, lat - BUFFER, lon + BUFFER, lat + BUFFER)
    r = get_features_bbox(url, capa, bbox, timeout=TIMEOUT, max_features=10)
    res["disponible"] = bool(r.get("disponible"))
    res["total_features"] = r.get("total_features", 0) or 0
    res["features"] = (r.get("features") or [])[:5]
    res["error"] = r.get("error")
    res["fuente"] = r.get("fuente") or {}
    if res["disponible"]:
        barrio = None
        if r.get("features"):
            props = r["features"][0].get("properties", {})
            barrio = props.get("barnombre") or props.get("nombre") or props.get("name")
        if barrio:
            res["resumen"] = f"IDESC Cali consultado en vivo (barrio: {barrio})."
        else:
            # Honesto: el servicio respondió pero el bbox no coincide (CRS de la capa)
            res["resumen"] = ("IDESC Cali verificado en vivo; sin coincidencias de barrio en el "
                              "BBOX del predio (revisar CRS de la capa antes de uso productivo).")
    return res


def _verificar_bogota(lat: float, lon: float, res: dict) -> dict:
    from config import get_ciudad
    cfg = get_ciudad("bogota")
    arcgis = cfg.get("arcgis") or {}
    url = (arcgis.get("ideca_feature") or "").rstrip("/")
    if not url:
        res["error"] = ("Bogotá en evaluación: capa IDECA federada no configurada; "
                        "catastro distrital 503 puntual, CEL es portal web sin API pública.")
        return res
    bbox = (lon - BUFFER, lat - BUFFER, lon + BUFFER, lat + BUFFER)
    r = query_layer_bbox(url, 0, bbox, max_features=10, timeout=TIMEOUT)
    res["disponible"] = bool(r.get("disponible"))
    res["total_features"] = r.get("total_features", 0) or 0
    res["features"] = (r.get("features") or [])[:5]
    res["error"] = r.get("error")
    res["fuente"] = r.get("fuente") or {}
    if res["disponible"]:
        res["resumen"] = ("IDECA Bogotá consultado en vivo (capas federadas). "
                          "Catastro distrital (CEL) sin API pública: verificación catastral pendiente.")
    elif not res["error"]:
        res["error"] = "El servicio IDECA de Bogotá no devolvió features en el BBOX del predio."
    return res


def _verificar_pasto(lat: float, lon: float, res: dict) -> dict:
    """Verificación territorial EN VIVO en el Geoportal Municipal de Pasto.

    Se descubrió y verificó (2026-09-16) que el municipio publica su base
    catastral y la normativa del POT por predio en
    geoportal.pasto.gov.co/server/rest/services/Planeacion: NUPRE, tratamiento
    urbanístico, edificabilidad (pisos y metros), clase de suelo, área de
    actividad y riesgo volcánico por predio.
    """
    from pasto_territorio import consultar_pasto
    try:
        datos = consultar_pasto(lat=lat, lon=lon)
    except Exception as e:  # noqa: BLE001 — nunca rompe el dictamen
        res["error"] = f"Geoportal de Pasto no disponible: {str(e)[:80]}"
        res["fuente"] = {"nombre": "Geoportal Municipal de Pasto",
                         "estado": "PENDIENTE VERIFICACIÓN"}
        return res

    res["fuente"] = datos.get("fuente") or {}
    if not datos.get("disponible"):
        res["error"] = (datos.get("fuente") or {}).get("estado") or \
            "El geoportal de Pasto no respondió al consultar el predio."
        return res

    predio = datos.get("predio") or {}
    entorno = datos.get("entorno") or {}
    nupre = predio.get("numero_predial_nacional")
    res["disponible"] = True
    res["total_features"] = 1 if (nupre or entorno) else 0
    res["features"] = ([{
        "properties": {
            "nupre": nupre,
            "tratamiento": entorno.get("tratamiento"),
            "edificabilidad": entorno.get("edificabilidad_texto"),
            "clase_suelo": entorno.get("clase_suelo"),
        }
    }] if (nupre or entorno) else [])

    partes = []
    if nupre:
        partes.append(f"NUPRE: {nupre}")
    if entorno.get("tratamiento"):
        partes.append(f"tratamiento: {entorno['tratamiento']}")
    if entorno.get("edificabilidad_texto"):
        partes.append(f"edificabilidad: {entorno['edificabilidad_texto']}")
    if entorno.get("clase_suelo"):
        partes.append(f"suelo: {entorno['clase_suelo']}")
    res["resumen"] = ("Geoportal Municipal de Pasto consultado en vivo"
                      + (f" ({'; '.join(partes)})" if partes else
                         " (sin coincidencia de predio en el punto)"))
    return res


def verificar_territorio(lat: float, lon: float, ciudad: str = "barranquilla") -> dict[str, Any]:
    """Verificación territorial en vivo de la ciudad indicada (con caché por celda)."""
    ciudad = (ciudad or "barranquilla").lower().strip()
    if ciudad not in ("barranquilla", "medellin", "cali", "bogota", "pasto"):
        return {"ciudad": ciudad, "disponible": False, "error": "Ciudad no soportada.",
                "features": [], "total_features": 0, "resumen": None, "fuente": {}}

    celda = _celda(lat, lon)
    ahora = time.time()
    if celda in _CACHE:
        ts, res = _CACHE[celda]
        if ahora - ts < TTL_CACHE:
            return res

    res = _nuevo_resultado(ciudad, lat, lon)
    try:
        if ciudad == "barranquilla":
            res = _verificar_barranquilla(lat, lon, res)
        elif ciudad == "medellin":
            res = _verificar_medellin(lat, lon, res)
        elif ciudad == "cali":
            res = _verificar_cali(lat, lon, res)
        elif ciudad == "bogota":
            res = _verificar_bogota(lat, lon, res)
        elif ciudad == "pasto":
            res = _verificar_pasto(lat, lon, res)
    except Exception as e:
        res["error"] = str(e)[:120]

    _CACHE[celda] = (ahora, res)
    return res

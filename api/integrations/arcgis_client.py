# -*- coding: utf-8 -*-
"""
ARHIAX RE — Cliente ArcGIS REST Server (Sprint 3, Fase 1)

Consulta capas de servicios ArcGIS REST (MapServer/FeatureServer) de geoportales
institucionales (Barranquilla "Mi Ciudad", IGAC, Medellín servidormapas, etc.)
mediante el endpoint estándar de query:

    <servicio>/<layerId>/query?where=...&geometry=<bbox>&geometryType=esriGeometryEnvelope
        &inSR=4326&outSR=4326&outFields=*&f=geojson

Postura honesta: nunca afirma datos que no obtuvo. Si el servicio no responde,
disponible=False y el llamador decide (p. ej. NO EVALUADO en el dictamen).
Toda respuesta incluye la fuente consultada (URL, capa, timestamp) para trazabilidad.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlencode, urlparse

import requests

log = logging.getLogger("arhiax.arcgis")

TIMEOUT = 10.0
UA = "ARHIAX-RE/1.0 (Sinergia Consulting Group)"
RETRIES = 2  # servidores públicos (p. ej. servidormapas de Medellín) responden 400 a veces


def _es_url_http(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _peticion_json(consulta: str, timeout: float) -> tuple:
    """GET con reintentos. Devuelve (data, status) o lanza Exception."""
    ultimo_err = None
    for intento in range(RETRIES + 1):
        try:
            resp = requests.get(consulta, headers={"User-Agent": UA}, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            # El servidor puede devolver 200 con {"error": {...}} (p. ej. Medellín inestable)
            if isinstance(data, dict) and data.get("error"):
                ultimo_err = f"Error del servicio: {data['error'].get('message', data['error'])}"
                continue
            return data, resp.status_code
        except Exception as e:
            ultimo_err = e
            if intento < RETRIES:
                import time as _t
                _t.sleep(0.5 * (intento + 1))
    raise ultimo_err if isinstance(ultimo_err, Exception) else Exception(ultimo_err)


def query_layer_bbox(
    url: str,
    layer_id: int | str,
    bbox: tuple[float, float, float, float],
    where: str = "1=1",
    out_fields: str = "*",
    max_features: int = 20,
    timeout: float = TIMEOUT,
    return_geometry: bool = False,
) -> dict[str, Any]:
    """Consulta una capa ArcGIS por BBOX (minx, miny, maxx, maxy en EPSG:4326).

    Retorna dict con: disponible, features, total, capa, fuente, error.
    Nunca lanza: los fallos de red se devuelven como disponible=False.
    return_geometry=True incluye la geometría de cada feature (p. ej. huellas).
    """
    minx, miny, maxx, maxy = bbox
    if not (minx < maxx and miny < maxy):
        return {"disponible": False, "error": "BBOX inválido", "features": [], "fuente": {}}
    if not _es_url_http(url):
        return {"disponible": False, "error": "URL de servicio inválida", "features": [], "fuente": {}}

    base = url.rstrip("/")
    query_url = f"{base}/{layer_id}/query"
    params = {
        "where": where,
        "geometry": f"{minx},{miny},{maxx},{maxy}",
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "outSR": "4326",
        "outFields": out_fields,
        "resultRecordCount": str(max_features),
        "returnGeometry": "true" if return_geometry else "false",
        "f": "geojson",
    }
    consulta = f"{query_url}?{urlencode(params)}"
    fuente = {
        "url": base,
        "capa": layer_id,
        "consulta": consulta,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    try:
        data, status = _peticion_json(consulta, timeout)
    except json.JSONDecodeError:
        return {
            "disponible": False,
            "error": "El servicio no devolvió JSON (¿capa inexistente o servicio caído?).",
            "features": [],
            "fuente": {**fuente, "http_status": None},
        }
    except Exception as e:
        return {
            "disponible": False,
            "error": f"Fallo de red o servicio: {e}",
            "features": [],
            "fuente": fuente,
        }

    features = data.get("features", []) if isinstance(data, dict) else []
    if data.get("error") if isinstance(data, dict) else False:
        err = data.get("error", {})
        return {
            "disponible": False,
            "error": f"Error del servicio: {err.get('message', err)}",
            "features": [],
            "fuente": {**fuente, "http_status": status},
        }

    return {
        "disponible": True,
        "features": features,
        "total_features": len(features),
        "capa": layer_id,
        "fuente": {**fuente, "http_status": status},
    }


def listar_colecciones_ogc(url: str, timeout: float = TIMEOUT) -> dict[str, Any]:
    """Lista las colecciones de un OGC API Features (/collections)."""
    if not _es_url_http(url):
        return {"disponible": False, "error": "URL inválida", "colecciones": [], "fuente": {}}
    base = url.rstrip("/")
    consulta = f"{base}/collections?f=json"
    fuente = {
        "url": base,
        "consulta": consulta,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    try:
        resp = requests.get(consulta, headers={"User-Agent": UA}, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        colecciones = [c.get("id") for c in data.get("collections", []) if isinstance(c, dict)]
        return {
            "disponible": True,
            "colecciones": colecciones,
            "total": len(colecciones),
            "fuente": {**fuente, "http_status": resp.status_code},
        }
    except Exception as e:
        return {
            "disponible": False,
            "error": f"Fallo de red o servicio: {e}",
            "colecciones": [],
            "fuente": fuente,
        }

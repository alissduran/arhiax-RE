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


def _es_url_http(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def query_layer_bbox(
    url: str,
    layer_id: int | str,
    bbox: tuple[float, float, float, float],
    where: str = "1=1",
    out_fields: str = "*",
    max_features: int = 20,
    timeout: float = TIMEOUT,
) -> dict[str, Any]:
    """Consulta una capa ArcGIS por BBOX (minx, miny, maxx, maxy en EPSG:4326).

    Retorna dict con: disponible, features, total, capa, fuente, error.
    Nunca lanza: los fallos de red se devuelven como disponible=False.
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
        "returnGeometry": "false",
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
        resp = requests.get(consulta, headers={"User-Agent": UA}, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
    except json.JSONDecodeError:
        return {
            "disponible": False,
            "error": "El servicio no devolvió JSON (¿capa inexistente o servicio caído?).",
            "features": [],
            "fuente": {**fuente, "http_status": getattr(resp, "status_code", None)},
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
            "fuente": {**fuente, "http_status": resp.status_code},
        }

    return {
        "disponible": True,
        "features": features,
        "total_features": len(features),
        "capa": layer_id,
        "fuente": {**fuente, "http_status": resp.status_code},
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

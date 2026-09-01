# -*- coding: utf-8 -*-
"""
ARHIAX RE — Cliente WFS genérico (Sprint 3: integraciones institucionales en vivo)

Cliente mínimo para consumir servicios WFS (OGC) de geoportales institucionales
(IGAC, IDECA Bogotá, geoportales municipales) mediante peticiones GET:

    GetCapabilities -> descubre las capas disponibles del servicio.
    GetFeature      -> consulta features por BBOX (EPSG:4326) y filtro de capa.

Postura honesta: el resultado siempre declara la fuente consultada (URL, capa,
fecha, parámetros) para que el dictamen trace la proveniencia real de los datos.
Si el servicio no responde o no es accesible, se devuelve un estado claro
(disponible=False) en lugar de afirmar datos que no se obtuvieron.

Las configuraciones por ciudad se definen en api/config/ciudades.yaml
(ver CARGAR desde get_config_ciudades()).
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlencode, urlparse

import requests

log = logging.getLogger("arhiax.wfs")

# Tiempos conservadores: el PDF se compila en el mismo request en Vercel
TIMEOUT_GETCAPABILITIES = 8.0
TIMEOUT_GETFEATURE = 10.0
MAX_FEATURES = 500


class WfsError(Exception):
    """Error controlado de un servicio WFS."""


def _es_url_http(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def get_capabilities(
    url: str,
    timeout: float = TIMEOUT_GETCAPABILITIES,
) -> dict[str, Any]:
    """Consulta GetCapabilities de un WFS y devuelve el XML crudo + metadatos."""
    if not _es_url_http(url):
        raise WfsError("URL de servicio WFS inválida.")
    params = {
        "service": "WFS",
        "request": "GetCapabilities",
        "version": "2.0.0",
    }
    sep = "&" if "?" in url else "?"
    try:
        resp = requests.get(
            f"{url}{sep}{urlencode(params)}",
            timeout=timeout,
            headers={"User-Agent": "ARHIAX-RE/1.0 (Sinergia Consulting Group)"},
        )
        resp.raise_for_status()
    except Exception as e:  # red, timeout, HTTP error
        raise WfsError(f"No se pudo consultar GetCapabilities: {e}") from e
    return {
        "url": url,
        "consulta": f"{url}{sep}{urlencode(params)}",
        "http_status": resp.status_code,
        "xml": resp.text,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }


def _capas_desde_getcapabilities(xml: str) -> list[str]:
    """Extrae los nombres de capas (FeatureType Name) del XML de GetCapabilities."""
    capas = re.findall(r"<Name>([^<]+)</Name>", xml)
    return list(dict.fromkeys(capas))  # únicas, preservando orden


def get_features_bbox(
    url: str,
    layer: str,
    bbox: tuple[float, float, float, float],
    timeout: float = TIMEOUT_GETFEATURE,
    output_format: str = "application/json",
    max_features: int = MAX_FEATURES,
) -> dict[str, Any]:
    """Consulta GetFeature de una capa por BBOX (minx, miny, maxx, maxy en EPSG:4326).

    Usa WFS 1.1.0 con bbox simple + srsName (compatible con GeoServer de entidades
    públicas; WFS 2.0.0 con URN suele devolver error en GeoServer).

    Retorna un dict con: disponible, features (lista), fuente (metadatos de la
    consulta), error (si aplica). Nunca lanza: los errores de red se devuelven
    como disponible=False para que el llamador decida (p. ej. marcar NO EVALUADO
    en el dictamen en lugar de afirmar 'sin afectación').
    """
    minx, miny, maxx, maxy = bbox
    if not (minx < maxx and miny < maxy):
        return {"disponible": False, "error": "BBOX inválido", "features": [], "fuente": {}}

    params = {
        "service": "WFS",
        "version": "1.0.0",
        "request": "GetFeature",
        "typeName": layer,
        "bbox": f"{minx},{miny},{maxx},{maxy}",
        "outputFormat": "application/json",
        "maxFeatures": str(max_features),
    }
    headers = {"Accept": output_format, "User-Agent": "ARHIAX-RE/1.0 (Sinergia Consulting Group)"}
    sep = "&" if "?" in url else "?"
    consulta = f"{url}{sep}{urlencode(params)}"
    fuente = {
        "url": url,
        "capa": layer,
        "consulta": consulta,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }

    try:
        resp = requests.get(consulta, headers=headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
    except json.JSONDecodeError:
        return {
            "disponible": False,
            "error": "El servicio no devolvió JSON (¿la capa o el formato no existen?).",
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
    return {
        "disponible": True,
        "features": features,
        "total_features": len(features),
        "fuente": {**fuente, "http_status": resp.status_code},
    }


def evaluar_bbox_vs_capas(
    url: str,
    capas: list[str],
    bbox: tuple[float, float, float, float],
) -> list[dict[str, Any]]:
    """Evalúa un BBOX contra varias capas de un servicio WFS (uso para riesgos POT).

    Retorna un resultado por capa con: capa, intersecta (hay features), total,
    disponible y fuente. No lanza excepciones.
    """
    resultados = []
    for capa in capas:
        r = get_features_bbox(url, capa, bbox)
        resultados.append({
            "capa": capa,
            "disponible": r["disponible"],
            "intersecta": bool(r.get("features")),
            "total_features": r.get("total_features", 0),
            "error": r.get("error"),
            "fuente": r.get("fuente", {}),
        })
    return resultados

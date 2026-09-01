# -*- coding: utf-8 -*-
"""
ARHIAX RE — Verificación catastral en vivo (Sprint 3, I-6: trazabilidad en el dictamen)

Consulta el catastro abierto de Barranquilla (ArcGIS REST "catastro/datosabiertos")
para el BBOX del predio, con CACHÉ por celda (~3 decimales ≈ 110 m) y TTL de 1 hora
para no saturar el servicio público.

Nunca lanza: devuelve un dict con disponible/nupre/total_features/fuente/error.
El dictamen usa este resultado para mostrar "CONSULTADA" o "NO DISPONIBLE" sin
afirmar datos que no se obtuvieron.
"""

from __future__ import annotations

import time
from typing import Any

from integrations.arcgis_client import query_layer_bbox

BASE = "https://miciudad.barranquilla.gov.co/gis/rest/services/catastro/datosabiertos"
TIMEOUT = 4.0          # conservador: el PDF se compila dentro del request en Vercel
TTL_CACHE = 3600       # 1 hora
BUFFER = 0.0025        # ~250 m alrededor del predio

_CACHE: dict[tuple, tuple[float, dict[str, Any]]] = {}


def _celda(lat: float, lon: float) -> tuple:
    return (round(lat, 3), round(lon, 3))


def verificar_catastro_barranquilla(lat: float, lon: float) -> dict[str, Any]:
    """Verificación catastral EN VIVO del predio contra el catastro abierto.

    Retorna dict con: disponible, nupre, total_features_terreno,
    total_features_datos, error, fuente (URL + timestamp). Con caché por celda.
    """
    celda = _celda(lat, lon)
    ahora = time.time()
    if celda in _CACHE:
        ts, res = _CACHE[celda]
        if ahora - ts < TTL_CACHE:
            return res

    bbox = (lon - BUFFER, lat - BUFFER, lon + BUFFER, lat + BUFFER)
    res: dict[str, Any] = {"disponible": False, "nupre": None,
                           "total_features_terreno": 0, "total_features_datos": 0,
                           "error": None, "fuente": {}}
    try:
        r_t = query_layer_bbox(f"{BASE}/MapServer", 315, bbox, max_features=5, timeout=TIMEOUT)
        r_d = query_layer_bbox(f"{BASE}/FeatureServer", 545, bbox, max_features=5, timeout=TIMEOUT)
    except Exception as e:  # red/timeout: nunca romper el dictamen
        res["error"] = str(e)[:120]
        _CACHE[celda] = (ahora, res)
        return res

    res["disponible"] = bool(r_t.get("disponible") or r_d.get("disponible"))
    res["total_features_terreno"] = r_t.get("total_features", 0)
    res["total_features_datos"] = r_d.get("total_features", 0)
    res["error"] = r_t.get("error") or r_d.get("error")
    res["fuente"] = r_t.get("fuente") or r_d.get("fuente") or {}

    if r_t.get("features"):
        f0 = r_t["features"][0].get("properties", {})
        res["nupre"] = f0.get("name") or None

    _CACHE[celda] = (ahora, res)
    return res

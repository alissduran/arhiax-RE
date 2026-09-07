# -*- coding: utf-8 -*-
"""
ARHIAX RE — Geocodificación catastral oficial de Barranquilla

Resuelve direcciones contra la capa 105 (Dirección) del catastro abierto de
Barranquilla, que contiene la nomenclatura oficial de cada predio con su
geometría. Es más precisa que Nominatim para direcciones de la ciudad (OSM no
indexa la mayoría de los números de predio).

  "Cra 43 # 98-32"   -> Carrera 43 # 98-32   (-74.8334, 11.0033)
  "Carrera 57 # 72-26" -> (-74.7994, 11.0010)
"""

from __future__ import annotations

import re
from typing import Optional

import requests

UA = {"User-Agent": "ARHIAX-RE/1.0 (Sinergia Consulting Group)"}
CAPA_DIRECCION = "https://miciudad.barranquilla.gov.co/gis/rest/services/catastro/datosabiertos/MapServer/105/query"

# Mapeo abreviación/forma -> clase completa usada por el catastro
_CLASES = {
    "CL": "Calle", "CLL": "Calle", "CALLE": "Calle",
    "CRA": "Carrera", "KR": "Carrera", "K": "Carrera", "CARRERA": "Carrera",
    "TV": "Transversal", "TRANSV": "Transversal", "TRANSVERSAL": "Transversal",
    "AV": "Avenida", "AVDA": "Avenida", "AVENIDA": "Avenida",
    "DG": "Diagonal", "DIAGONAL": "Diagonal",
}

_RE_DIR = re.compile(
    r"^\s*(CL|CLL|CALLE|CRA|KR|CARRERA|TV|TRANSV|TRANSVERSAL|AV|AVDA|AVENIDA|DG|DIAGONAL)"
    r"\s*\.?\s*(\d+)\s*([A-Za-z])?\s*"
    r"(?:#|\s*N[°o]?\.?|\s*n[°o]?\.?)?\s*(\d+)\s*[-–—]\s*(\d+)\s*$",
    re.IGNORECASE,
)


def parsear_direccion_colombiana(direccion: str):
    """Extrae (clase_completa, valor_via, letra, via_generadora, numero_predio)
    de una dirección tipo 'CRA 43 # 98-32'. Retorna None si no matchea."""
    if not direccion:
        return None
    from address_normalizer import limpiar_direccion_consulta
    txt = limpiar_direccion_consulta(direccion)
    txt = re.sub(r",\s*(Barranquilla|BAQ|Atl[áa]ntico|Colombia)$", "", txt, flags=re.I)
    m = _RE_DIR.match(txt)
    if not m:
        return None
    clase = _CLASES.get(m.group(1).upper())
    if not clase:
        return None
    return (clase, m.group(2), (m.group(3) or "").upper(), m.group(4), m.group(5))


def _centro(feature) -> Optional[tuple]:
    geom = feature.get("geometry") or {}
    coords = geom.get("coordinates")
    if not coords:
        return None
    if geom.get("type") == "Point":
        return (round(coords[0], 6), round(coords[1], 6))
    try:
        ring = coords[0] if isinstance(coords[0], list) else coords
        xs = [c[0] for c in ring]
        ys = [c[1] for c in ring]
        return (round(sum(xs) / len(xs), 6), round(sum(ys) / len(ys), 6))
    except Exception:
        return None


def geocodificar_catastro_barranquilla(direccion: str, timeout: float = 8.0):
    """Resuelve la dirección en el catastro oficial. Retorna dict con
    lat, lon, direccion_oficial o None (no encontrada / no parseable)."""
    partes = parsear_direccion_colombiana(direccion)
    if not partes:
        return None
    clase, via, letra, generadora, numero = partes

    where = (f"clase_via_principal='{clase}' AND valor_via_principal='{via}'"
             f" AND valor_via_generadora='{generadora}' AND numero_predio='{numero}'")
    if letra:
        where += f" AND letra_via_principal='{letra}'"
    params = {
        "where": where,
        "outFields": "clase_via_principal,valor_via_principal,letra_via_principal,valor_via_generadora,numero_predio,es_direccion_principal",
        "outSR": "4326", "returnGeometry": "true", "f": "geojson",
        "resultRecordCount": "10",
    }
    try:
        resp = requests.get(CAPA_DIRECCION, params=params, headers=UA, timeout=timeout)
        resp.raise_for_status()
        feats = resp.json().get("features", [])
    except Exception:
        return None
    if not feats:
        return None
    # Preferir dirección principal
    feats = sorted(feats, key=lambda f: (f.get("properties", {}).get("es_direccion_principal") != 1))
    for f in feats:
        c = _centro(f)
        if c:
            p = f.get("properties", {})
            oficial = (
                f"{p.get('clase_via_principal')} {p.get('valor_via_principal')}"
                f"{p.get('letra_via_principal') or ''} # {p.get('valor_via_generadora')}"
                f"-{p.get('numero_predio')}"
            )
            return {"lat": c[1], "lon": c[0], "direccion_oficial": oficial}
    return None

# -*- coding: utf-8 -*-
"""
ARHIAX RE — Geocodificación catastral oficial de Medellín

Resuelve direcciones contra la capa de Nomenclatura Domiciliaria del
servidormapas de la Alcaldía de Medellín (mapas_nacionales/VC_Direccion),
que contiene la placa/nomenclatura oficial de cada predio con su geometría.

Formatos aceptados (se normalizan antes de consultar):
  "Carrera 43C # 9-46"  -> "CR 43C 9-46"   (formato oficial del catastro)
  "Calle 10 # 43B-43"   -> "CL 10 43B-43"
  "CRA 43C # 9-46"      -> "CR 43C 9-46"
  "CR 43C 9-46, Medellín" -> idem (se descarta el sufijo de ciudad)

Sprint 3 (expansión Medellín): misma interfaz que geocoder_catastral.py
(geocodificar_catastro_<ciudad>) para que el geocoder universal despache
por ciudad sin tocar el resto del motor.
"""

from __future__ import annotations

import re
from typing import Optional

import requests

UA = {"User-Agent": "ARHIAX-RE/1.0 (Sinergia Consulting Group)"}
CAPA_NOMENCLATURA = (
    "https://www.medellin.gov.co/servidormapas/rest/services/"
    "mapas_nacionales/VC_Direccion/MapServer/0/query"
)

# Abreviación/forma de uso común -> clase oficial del catastro de Medellín
_CLASES = {
    "CL": "CL", "CLL": "CL", "CALLE": "CL",
    "CR": "CR", "CRA": "CR", "KR": "CR", "K": "CR", "CARRERA": "CR",
    "TV": "TV", "TRANSV": "TV", "TRANSVERSAL": "TV",
    "AV": "AV", "AVDA": "AV", "AVENIDA": "AV",
    "DG": "DG", "DIAGONAL": "DG",
}

# Formato de dirección colombiana estándar con placa:
#   CLASE VIA(letra) [#] NUMERO(letra) - NUMERO
_RE_DIR = re.compile(
    r"^\s*(CL|CLL|CALLE|CR|CRA|KR|CARRERA|TV|TRANSV|TRANSVERSAL|AV|AVDA|AVENIDA|DG|DIAGONAL)"
    r"[\s\.]*(\d+)\s*([A-Za-z])?\s*"
    r"(?:#\s*|\s*)?(\d+)\s*([A-Za-z])?\s*[-–—]\s*(\d+)\s*$",
    re.IGNORECASE,
)

# Sufijos de barrio/ciudad que pueden acompañar a la placa (se eliminan)
_SUFIJOS_LIMPIEZA = re.compile(
    r",\s*(?:Medell[ií]n|MED|Antioquia|Colombia|El Poblado|Laureles|Bel[eé]n|Robledo|"
    r"Manila|Astorga|Patio Bonito|Envigado|Bello|Itag[uü][ií]|Sabaneta|La Am[ée]rica|"
    r"Los Colores|Prado|Boston|Buenos Aires|La Candelaria|Villa Nueva|San Javier|"
    r"Castilla|Doce de Octubre|Aranjuez|Manrique|Popular|Santa Cruz)\s*$",
    re.IGNORECASE,
)


def normalizar_direccion_medellin(direccion: str) -> Optional[str]:
    """Convierte una dirección común a la forma oficial del catastro de Medellín
    (p. ej. 'Carrera 43C # 9-46' -> 'CR 43C 9-46'). Retorna None si no matchea."""
    if not direccion:
        return None
    from address_normalizer import limpiar_direccion_consulta
    txt = _SUFIJOS_LIMPIEZA.sub("", limpiar_direccion_consulta(direccion))
    txt = txt.strip().rstrip(".,;")
    m = _RE_DIR.match(txt)
    if not m:
        return None
    clase = _CLASES.get(m.group(1).upper())
    if not clase:
        return None
    via = m.group(2)
    letra_via = (m.group(3) or "").upper()
    num = m.group(4)
    letra_num = (m.group(5) or "").upper()
    placa = m.group(6)
    via_comp = f"{clase} {via}{letra_via}"
    placa_comp = f"{num}{letra_num}-{placa}"
    return f"{via_comp} {placa_comp}"


def _centro(feature) -> Optional[tuple]:
    geom = feature.get("geometry") or {}
    coords = geom.get("coordinates")
    if not coords:
        return None
    if geom.get("type") == "Point":
        return (round(float(coords[0]), 6), round(float(coords[1]), 6))
    try:
        ring = coords[0] if isinstance(coords[0], list) else coords
        xs = [float(c[0]) for c in ring]
        ys = [float(c[1]) for c in ring]
        return (round(sum(xs) / len(xs), 6), round(sum(ys) / len(ys), 6))
    except Exception:
        return None


def geocodificar_catastro_medellin(direccion: str, timeout: float = 8.0):
    """Resuelve la dirección en la nomenclatura oficial de Medellín.

    Retorna dict con lat, lon, direccion_oficial o None (no encontrada).
    La capa guarda la dirección en formato compacto 'CR 43C 9-46'; se consulta
    con UPPER(direccion) LIKE para tolerar variantes de espaciado.
    """
    norm = normalizar_direccion_medellin(direccion)
    if not norm:
        return None
    params = {
        "where": f"UPPER(direccion) LIKE '%{norm}%'",
        "outFields": "direccion,via,placa,numero_mejora,cbml",
        "outSR": "4326", "returnGeometry": "true", "f": "geojson",
        "resultRecordCount": "10",
    }
    try:
        resp = requests.get(CAPA_NOMENCLATURA, params=params, headers=UA, timeout=timeout)
        resp.raise_for_status()
        feats = resp.json().get("features", [])
    except Exception:
        return None
    if not feats:
        return None
    # Preferir la coincidencia exacta (no parcial de otra vía tipo 'CR 430')
    for f in feats:
        p = f.get("properties", {})
        if (p.get("direccion") or "").strip().upper() == norm:
            c = _centro(f)
            if c:
                return {"lat": c[1], "lon": c[0],
                        "direccion_oficial": p.get("direccion") or norm}
    # Fallback: primera coincidencia con geometría
    for f in feats:
        c = _centro(f)
        if c:
            p = f.get("properties", {})
            return {"lat": c[1], "lon": c[0],
                    "direccion_oficial": p.get("direccion") or norm}
    return None


if __name__ == "__main__":
    casos = [
        "Carrera 43C # 9-46",
        "Calle 10 # 43B-43",
        "CRA 43 # 9-46, Medellín",
        "CR 43C 9-46",
    ]
    for d in casos:
        r = geocodificar_catastro_medellin(d)
        print(f"{d!r:35} -> {r}")

# -*- coding: utf-8 -*-
"""
ARHIAX RE — Geocodificación catastral oficial de Bogotá

Resuelve direcciones contra la capa de Placa Domiciliaria del catastro
distrital de Bogotá (serviciosgis.catastrobogota.gov.co/catastro/placadomiciliaria),
que contiene la placa oficial de cada predio con su punto.

Formato de placa del catastro de Bogotá:  PDONVIAL='KR 9'  PDOTEXTO='61 08'
(corresponde a la dirección "Carrera 9 # 61-08"). La coincidencia se hace con
LIKE sobre la vía + filtro EXACTO normalizado en cliente (el servidor no
normaliza espacios internos).

Sprint 3 (expansión Bogotá): misma interfaz que geocoder_catastral_medellin /
geocoder_catastral (geocodificar_catastro_<ciudad>).
"""

from __future__ import annotations

import re
from typing import Optional

import requests

UA = {"User-Agent": "ARHIAX-RE/1.0 (Sinergia Consulting Group)"}
CAPA_PLACA = (
    "https://serviciosgis.catastrobogota.gov.co/arcgis/rest/services/"
    "catastro/placadomiciliaria/MapServer/0/query"
)

# Abreviación/forma común -> clase oficial del catastro de Bogotá
_CLASES = {
    "CL": "CL", "CLL": "CL", "CALLE": "CL",
    "KR": "KR", "CR": "KR", "CRA": "KR", "K": "KR", "CARRERA": "KR",
    "AK": "AK", "AV": "AK", "AVDA": "AK", "AVENIDA": "AK", "AUTOPISTA": "AK",
    "TV": "TV", "TRANSV": "TV", "TRANSVERSAL": "TV",
    "DG": "DG", "DIAGONAL": "DG",
}

_RE_DIR = re.compile(
    r"^\s*(CL|CLL|CALLE|KR|K|CR|CRA|CARRERA|AK|AV|AVDA|AVENIDA|AUTOPISTA|"
    r"TV|TRANSV|TRANSVERSAL|DG|DIAGONAL)"
    r"[\s\.]*(\d+)\s*([A-Za-z])?\s*(?:BIS)?\s*"
    r"(?:#\s*|\s*N[°o]?\.?\s*)?(\d+)\s*([A-Za-z])?\s*[-–—]\s*(\d+)\s*$",
    re.IGNORECASE,
)

# Sufijos de barrio/localidad que pueden acompañar la placa
_SUFIJOS_LIMPIEZA = re.compile(
    r",\s*(?:Bogot[áa]|Bogota|DC|D\.C\.|Cundinamarca|Colombia|Chapinero|"
    r"Centro|Candelaria|Usaqu[ée]n|Suba|Engativ[áa]|Kennedy|Fontib[óo]n|"
    r"Teusaquillo|Barrios Unidos|Puente Aranda|Antonio Nari[ñ]o|Los M[áa]rtires|"
    r"Santa Fe|San Crist[óo]bal|Rafael Uribe|Ciudad Bol[íi]var|Tunjuelito|Bosa|"
    r"La Candelaria|La Salle|Galeries|Galer[ií]as)\s*$",
    re.IGNORECASE,
)


def normalizar_direccion_bogota(direccion: str) -> Optional[tuple]:
    """Convierte una dirección común a (vía, texto_placa) oficiales de Bogotá.

    p. ej. 'Carrera 9 # 61-08' -> ('KR 9', '61 08').
    Retorna None si no matchea.
    """
    if not direccion:
        return None
    txt = _SUFIJOS_LIMPIEZA.sub("", direccion.strip()).strip().rstrip(".,;")
    m = _RE_DIR.match(txt)
    if not m:
        return None
    clase = _CLASES.get(m.group(1).upper())
    if not clase:
        return None
    via_num = m.group(2)
    via_letra = (m.group(3) or "").upper()
    pl1 = m.group(4)
    pl1_letra = (m.group(5) or "").upper()
    pl2 = m.group(6)
    via = f"{clase} {via_num}{via_letra}"
    texto = f"{pl1}{pl1_letra} {pl2}"
    return via, texto


def _norm(s: str) -> str:
    """Normaliza espacios para comparación exacta."""
    return " ".join(str(s or "").split()).upper()


def _centro(feature) -> Optional[tuple]:
    geom = feature.get("geometry") or {}
    if geom.get("type") == "Point":
        coords = geom.get("coordinates") or []
        if len(coords) >= 2:
            return (round(float(coords[0]), 6), round(float(coords[1]), 6))
    if geom.get("x") is not None and geom.get("y") is not None:
        return (round(float(geom["x"]), 6), round(float(geom["y"]), 6))
    return None


def geocodificar_catastro_bogota(direccion: str, timeout: float = 10.0):
    """Resuelve la dirección en la placa domiciliaria oficial de Bogotá.

    Retorna dict con lat, lon, direccion_oficial, placa, codigo_lote o None.
    """
    parsed = normalizar_direccion_bogota(direccion)
    if not parsed:
        return None
    via, texto = parsed
    # Doble condición (vía + texto de placa) para acotar el resultado a pocas
    # filas (calles largas con LIKE solo por vía superan el límite de la capa),
    # + filtro EXACTO normalizado en cliente (el servidor no normaliza espacios).
    params = {
        "where": f"UPPER(PDONVIAL) LIKE '%{via}%' AND UPPER(PDOTEXTO) LIKE '%{texto}%'",
        "outFields": "PDONVIAL,PDOTEXTO,PDOCLOTE,PDOCODIGO,PDOTIPO",
        "outSR": "4326", "returnGeometry": "true", "f": "geojson",
        "resultRecordCount": "100",
    }
    try:
        resp = requests.get(CAPA_PLACA, params=params, headers=UA, timeout=timeout)
        resp.raise_for_status()
        feats = resp.json().get("features", [])
    except Exception:
        return None
    if not feats:
        return None
    for f in feats:
        p = f.get("properties", {})
        if _norm(p.get("PDONVIAL")) == via and _norm(p.get("PDOTEXTO")) == texto:
            c = _centro(f)
            if c:
                oficial = f"{p.get('PDONVIAL')} # {p.get('PDOTEXTO')}".strip()
                return {
                    "lat": c[1], "lon": c[0],
                    "direccion_oficial": " ".join(oficial.split()),
                    "placa": _norm(p.get("PDOTEXTO")),
                    "codigo_lote": p.get("PDOCLOTE"),
                }
    return None


if __name__ == "__main__":
    casos = [
        "Carrera 9 # 61-08",
        "Calle 17 # 4-70",
        "KR 9 # 61-08, Chapinero",
        "Carrera 9 # 61-08, Bogotá",
    ]
    for d in casos:
        r = geocodificar_catastro_bogota(d)
        print(f"{d!r:42} -> {r}")

# -*- coding: utf-8 -*-
"""
ARHIAX RE - Modulo de Geocodificacion Universal
Convierte cualquier direccion de Barranquilla a coordenadas (lat, lon).
Sin dependencias externas. Sin API key. Usa Nominatim (OpenStreetMap).

Funciones principales:
    geocodificar_direccion(direccion, ciudad) -> (lat, lon)
    extraer_direccion_de_ctl(texto_pdf)       -> str
    extraer_barrio_de_texto(texto)            -> str | None
    geocodificar_desde_ctl(texto_pdf)         -> dict
"""

import re
import sys
import json
import urllib.request
import urllib.parse
from pathlib import Path

# Garantizar imports locales
_API_DIR = str(Path(__file__).resolve().parent)
if _API_DIR not in sys.path:
    sys.path.insert(0, _API_DIR)

from address_normalizer import normalize_address_colombia

# Centroide de Barranquilla - fallback de ultimo recurso
CENTROIDE_BAQ = (10.9685, -74.7813)

# Cache en memoria: direccion normalizada -> (lat, lon)
_GEOCODE_CACHE = {}

# Bounding box de Barranquilla (margen amplio para area metropolitana)
_BAQ_LAT_MIN, _BAQ_LAT_MAX = 10.85, 11.10
_BAQ_LON_MIN, _BAQ_LON_MAX = -74.95, -74.65


def geocodificar_direccion(direccion, ciudad="Barranquilla"):
    """
    Convierte una direccion textual a coordenadas (lat, lon) via Nominatim OSM.

    Estrategia en cascada:
      1. Cache en memoria (hit instantaneo en llamadas repetidas)
      2. Nominatim con direccion completa normalizada
      3. Nominatim con direccion original sin normalizar
      4. Nominatim con tipo de via + numero simplificado (ej: Calle 63, Barranquilla)
      5. Centroide de Barranquilla como ultimo recurso

    Returns:
        tuple: (lat, lon) - siempre retorna un valor, nunca lanza excepcion.
    """
    if not direccion or not direccion.strip():
        return CENTROIDE_BAQ

    try:
        direccion_norm = normalize_address_colombia(direccion.strip())
    except Exception:
        direccion_norm = direccion.strip().upper()

    cache_key = "{}|{}".format(direccion_norm, ciudad)
    if cache_key in _GEOCODE_CACHE:
        return _GEOCODE_CACHE[cache_key]

    # 0. Catastro oficial de Barranquilla (capa 105): precisión por nomenclatura
    # municipal, superior a Nominatim (OSM no indexa la mayoría de números de
    # predio y Nominatim devolvía el centroide del perímetro urbano).
    if "barranquilla" in ciudad.lower() or not ciudad:
        try:
            from geocoder_catastral import geocodificar_catastro_barranquilla
            res_cat = geocodificar_catastro_barranquilla(direccion)
            if res_cat:
                coords = (res_cat["lat"], res_cat["lon"])
                _GEOCODE_CACHE[cache_key] = coords
                print(f"[GEOCODER][CATASTRO] '{direccion}' -> {coords} (oficial: {res_cat.get('direccion_oficial')})")
                return coords
        except Exception:
            pass

    intentos = [
        "{}, {}, Colombia".format(direccion_norm, ciudad),
        "{}, {}, Colombia".format(direccion.strip(), ciudad),
    ]

    # Intento simplificado con tipo de via + numero
    m = re.search(r"\b(CL|CRA|AV|DG|TV|AP)\s+(\d+)", direccion_norm)
    if m:
        prefijo_map = {
            "CL": "Calle",
            "CRA": "Carrera",
            "AV": "Avenida",
            "DG": "Diagonal",
            "TV": "Transversal",
            "AP": "Autopista"
        }
        tipo_via = prefijo_map.get(m.group(1), "Calle")
        numero_via = m.group(2)
        intentos.append("{} {}, {}, Colombia".format(tipo_via, numero_via, ciudad))

    for query in intentos:
        resultado = _nominatim_query(query)
        if resultado:
            _GEOCODE_CACHE[cache_key] = resultado
            return resultado

    print("[GEOCODER][WARN] Sin resultado especifico para '{}'. Usando centroide de Barranquilla.".format(direccion))
    _GEOCODE_CACHE[cache_key] = CENTROIDE_BAQ
    return CENTROIDE_BAQ


def _nominatim_query(query):
    """
    Ejecuta una query a Nominatim y filtra resultados dentro del bbox de Barranquilla.
    Descarta resultados que representen la municipalidad completa (nodo administrativo genérico de Barranquilla).
    Retorna (lat, lon) o None si no hay resultado valido.
    """
    # Coordenadas exactas del nodo de Barranquilla que Nominatim retorna como fallback genérico
    LAT_GENERICA_BAQ = 11.0101922
    LON_GENERICA_BAQ = -74.8231794

    try:
        params = urllib.parse.urlencode({
            "q": query,
            "format": "json",
            "limit": "3",
            "countrycodes": "co",
            "bounded": "1",
            "viewbox": "{},{},{},{}".format(_BAQ_LON_MIN, _BAQ_LAT_MAX, _BAQ_LON_MAX, _BAQ_LAT_MIN)
        })
        url = "https://nominatim.openstreetmap.org/search?{}".format(params)
        req = urllib.request.Request(url, headers={"User-Agent": "ARHIAX-RE/1.0 (Sinergia Consulting Group)"})

        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        for item in data:
            lat = float(item["lat"])
            lon = float(item["lon"])
            
            # 1. Descartar si coincide exactamente con el nodo genérico del municipio de Barranquilla
            if abs(lat - LAT_GENERICA_BAQ) < 0.0001 and abs(lon - LON_GENERICA_BAQ) < 0.0001:
                continue
                
            # 2. Descartar SIEMPRE los resultados administrativos genéricos
            # (city/county/administrative, p. ej. 'Perímetro Urbano Barranquilla'):
            # su centroide NO es la ubicación de ningún predio.
            if item.get("addresstype") in ("city", "county", "state", "region") or item.get("type") == "administrative":
                continue
            
            # 3. Validar que esté dentro de los límites geográficos de Barranquilla
            if _BAQ_LAT_MIN <= lat <= _BAQ_LAT_MAX and _BAQ_LON_MIN <= lon <= _BAQ_LON_MAX:
                print("[GEOCODER][OK] '{}' -> ({:.5f}, {:.5f})".format(query, lat, lon))
                return (lat, lon)

    except Exception as e:
        print("[GEOCODER][ERROR] Nominatim fallo para '{}': {}".format(query, e))

    return None



def extraer_direccion_de_ctl(texto_pdf):
    """
    Extrae la direccion del predio desde el texto completo de un CTL colombiano.
    No depende del barrio. Usa regex heuristica sobre el texto del certificado.

    Returns:
        str: Direccion extraida, o None si no se encontro.
    """
    if not texto_pdf:
        return None

    # 1. Etiquetas explicitas en el CTL
    patrones_etiqueta = [
        r"(?:Direcci[oO]n|Ubicaci[oO]n|Localizaci[oO]n)\s*[:\-]?\s*([^\n\r]{10,100})",
        r"(?:inmueble|predio)\s+(?:ubicado\s+en|en)\s*[:\-]?\s*([^\n\r]{10,100})",
        r"(?:situada?\s+en|localizada?\s+en)\s*[:\-]?\s*([^\n\r]{10,100})",
        r"(?:DIRECCION|UBICACION)\s*[:\-]\s*([^\n\r]{10,100})",
    ]
    for patron in patrones_etiqueta:
        matches = re.findall(patron, texto_pdf, re.IGNORECASE)
        for m in matches:
            m_clean = m.strip().rstrip(".,;")
            if _es_direccion_valida(m_clean):
                return m_clean

    # 2. Nomenclatura colombiana directa en el texto
    patron_nom = (
        r"(?:CALLE|CLLE?|CLL?|CARRERA|CRA?|AVENIDA|AV[DA]?|DIAGONAL|DG|TRANSVERSAL|TRANSV|TV|AUTOPISTA|AP)"
        r"[\s\.]+\d+[A-Z]?\s*(?:No\.?|N[o]?\.?|#)?\s*\d+[A-Z]?\s*[\-\u2013]\s*\d+"
    )
    matches_nom = re.findall(patron_nom, texto_pdf, re.IGNORECASE)
    if matches_nom:
        return matches_nom[0].strip()

    return None


def extraer_barrio_de_texto(texto):
    """
    Detecta el barrio del predio desde texto libre de forma dinamica.
    No depende de lista hardcodeada.

    Returns:
        str: Nombre del barrio en Title Case, o None si no se determino.
    """
    if not texto:
        return None

    patrones = [
        r"(?:barrio|brio\.?)\s+([A-Za-z\xe0-\xff\u00c0-\u024f\s]+?)(?:\s*,|\s*\.|\s*\n|\s*-|\s*\()",
        r"(?:sector|conjunto\s+residencial|urbanizaci[oO]n|ciudadela)\s+"
        r"([A-Za-z\xe0-\xff\u00c0-\u024f\s]+?)(?:\s*,|\s*\.|\s*\n|\s*-|\s*\()",
    ]
    for patron in patrones:
        matches = re.findall(patron, texto, re.IGNORECASE)
        for m in matches:
            candidato = m.strip().title()
            if 3 <= len(candidato) <= 50:
                return candidato

    return None


def _es_direccion_valida(texto):
    """Verifica que un texto tenga estructura minima de direccion colombiana."""
    if not texto or len(texto) < 5:
        return False
    tiene_via = re.search(
        r"\b(?:CALLE|CLL?|CARRERA|CRA?|AVENIDA|AV|DIAGONAL|DG|TRANSVERSAL|TV|CL)\b",
        texto, re.IGNORECASE
    )
    tiene_numero = re.search(r"\d", texto)
    return bool(tiene_via and tiene_numero)


def geocodificar_desde_ctl(texto_pdf):
    """
    Pipeline completo: texto del CTL -> direccion -> barrio -> (lat, lon).

    Returns:
        dict: {
            'direccion':     str | None,
            'barrio':        str | None,
            'lat':           float,
            'lon':           float,
            'fuente_geocod': 'nominatim' | 'centroide_fallback',
        }
    """
    direccion = extraer_direccion_de_ctl(texto_pdf)
    barrio    = extraer_barrio_de_texto(texto_pdf)

    if direccion:
        lat, lon = geocodificar_direccion(direccion)
        fuente = "centroide_fallback" if (lat, lon) == CENTROIDE_BAQ else "nominatim"
    else:
        lat, lon = CENTROIDE_BAQ
        fuente = "centroide_fallback"

    return {
        "direccion":     direccion,
        "barrio":        barrio,
        "lat":           lat,
        "lon":           lon,
        "fuente_geocod": fuente,
    }


if __name__ == "__main__":
    casos = [
        "TV 43 # 100-50",
        "Calle 63 # 37-71",
        "Carrera 51B # 82-254, Barranquilla",
        "Av Circunvalar 110-240",
        "CL 72 # 43-15",
    ]
    print("=" * 60)
    print("  ARHIAX RE - Test Geocoder Universal")
    print("=" * 60)
    for d in casos:
        lat, lon = geocodificar_direccion(d)
        fuente = "NOMINATIM" if (lat, lon) != CENTROIDE_BAQ else "FALLBACK"
        print("  [{:8s}] {:<40} -> ({:.5f}, {:.5f})".format(fuente, d, lat, lon))


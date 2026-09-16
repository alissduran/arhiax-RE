# -*- coding: utf-8 -*-
"""
ARHIAX RE - Modulo de Geocodificacion Universal
Convierte cualquier direccion de Barranquilla u otras ciudades soportadas
(Medellín, Sprint 3) a coordenadas (lat, lon).
Sin dependencias externas. Sin API key. Usa el catastro oficial de la ciudad
cuando está disponible y Nominatim (OpenStreetMap) como respaldo.

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

from address_normalizer import normalize_address_colombia, limpiar_direccion_consulta

# Centroides por ciudad - fallback de ultimo recurso
CENTROIDE_BAQ = (10.9685, -74.7813)
CENTROIDE_MED = (6.2442, -75.5812)
CENTROIDE_BOG = (4.7110, -74.0721)
CENTROIDE_PAS = (1.2136, -77.2811)   # Pasto (Nariño) — Plaza de Nariño

# Cache en memoria: (ciudad, direccion normalizada) -> (lat, lon)
_GEOCODE_CACHE = {}

# Bounding boxes por ciudad (margen amplio para area metropolitana)
_BBOX_BAQ = (10.85, 11.10, -74.95, -74.65)          # (lat_min, lat_max, lon_min, lon_max)
_BBOX_MED = (5.98, 6.50, -75.80, -75.30)            # Valle de Aburrá amplio
_BBOX_BOG = (4.45, 4.85, -74.25, -73.90)            # Bogotá D.C. + sabana cercana
_BBOX_PAS = (1.05, 1.40, -77.45, -77.05)            # Pasto + corregimientos (Nariño)


def _es_medellin(ciudad: str) -> bool:
    c = (ciudad or "").lower().strip()
    return "medellin" in c or "medellín" in c or c in ("med", "aburra", "valle de aburra")


def _es_bogota(ciudad: str) -> bool:
    c = (ciudad or "").lower().strip()
    return "bogota" in c or "bogotá" in c or c in ("bog", "dc", "bogota dc")


def _es_pasto(ciudad: str) -> bool:
    c = (ciudad or "").lower().strip()
    return "pasto" in c or "nariño" in c or "narino" in c or c in ("pas", "san juan de pasto")


def _centroide(ciudad: str):
    if _es_medellin(ciudad):
        return CENTROIDE_MED
    if _es_bogota(ciudad):
        return CENTROIDE_BOG
    if _es_pasto(ciudad):
        return CENTROIDE_PAS
    return CENTROIDE_BAQ


def _bbox(ciudad: str):
    if _es_medellin(ciudad):
        return _BBOX_MED
    if _es_bogota(ciudad):
        return _BBOX_BOG
    if _es_pasto(ciudad):
        return _BBOX_PAS
    return _BBOX_BAQ


def geocodificar_direccion(direccion, ciudad="Barranquilla"):
    """
    Convierte una direccion textual a coordenadas (lat, lon).

    Estrategia en cascada:
      1. Cache en memoria (hit instantaneo en llamadas repetidas)
      2. Catastro oficial de la ciudad (Barranquilla capa 105 / Medellín
         VC_Direccion): precisión por nomenclatura municipal
      3. Nominatim con direccion completa normalizada
      4. Nominatim con direccion original sin normalizar
      5. Nominatim con tipo de via + numero simplificado (ej: Calle 63, ciudad)
      6. Centroide de la ciudad como ultimo recurso

    Returns:
        tuple: (lat, lon) - siempre retorna un valor, nunca lanza excepcion.
    """
    if not direccion or not direccion.strip():
        return _centroide(ciudad)

    try:
        # Limpieza SNR (prefijos '2) ', sufijos 'BDGA 3', 'No.')->'#') antes de
        # normalizar: las direcciones del CTL traen ruido que rompía la consulta.
        direccion_limpia = limpiar_direccion_consulta(direccion.strip())
        direccion_norm = normalize_address_colombia(direccion_limpia)
    except Exception:
        direccion_limpia = direccion.strip()
        direccion_norm = direccion.strip().upper()

    cache_key = "{}|{}".format(ciudad.lower().strip(), direccion_norm)
    if cache_key in _GEOCODE_CACHE:
        return _GEOCODE_CACHE[cache_key]

    # 0. Catastro oficial de la ciudad: precisión por nomenclatura municipal,
    # superior a Nominatim (OSM no indexa la mayoría de números de predio).
    try:
        if _es_medellin(ciudad):
            from geocoder_catastral_medellin import geocodificar_catastro_medellin
            res_cat = geocodificar_catastro_medellin(direccion)
            if res_cat:
                coords = (res_cat["lat"], res_cat["lon"])
                _GEOCODE_CACHE[cache_key] = coords
                print(f"[GEOCODER][CATASTRO-MED] '{direccion}' -> {coords} (oficial: {res_cat.get('direccion_oficial')})")
                return coords
        elif _es_bogota(ciudad):
            # Reintento: las capas de serviciosgis tienen timeouts intermitentes;
            # un solo fallo hacía caer al fallback Nominatim, que resuelve la
            # 'Diagonal 61' truncada en otra localidad (regresión dictamen real
            # 50C-1463431: DG 61B # 20-04 -> RESTREPO sur en vez de SAN LUIS).
            from geocoder_catastral_bogota import geocodificar_catastro_bogota
            res_cat = geocodificar_catastro_bogota(direccion)
            if not res_cat:
                import time as _time
                _time.sleep(1.5)
                res_cat = geocodificar_catastro_bogota(direccion)
            if res_cat:
                coords = (res_cat["lat"], res_cat["lon"])
                _GEOCODE_CACHE[cache_key] = coords
                print(f"[GEOCODER][CATASTRO-BOG] '{direccion}' -> {coords} (oficial: {res_cat.get('direccion_oficial')})")
                return coords
        elif "barranquilla" in ciudad.lower() or not ciudad:
            from geocoder_catastral import geocodificar_catastro_barranquilla
            res_cat = geocodificar_catastro_barranquilla(direccion)
            if res_cat:
                coords = (res_cat["lat"], res_cat["lon"])
                _GEOCODE_CACHE[cache_key] = coords
                print(f"[GEOCODER][CATASTRO] '{direccion}' -> {coords} (oficial: {res_cat.get('direccion_oficial')})")
                return coords
    except Exception:
        pass

    if _es_medellin(ciudad):
        nombre_ciudad = "Medellín"
    elif _es_bogota(ciudad):
        nombre_ciudad = "Bogotá"
    elif _es_pasto(ciudad):
        nombre_ciudad = "Pasto"
    else:
        nombre_ciudad = "Barranquilla"
    intentos = [
        "{}, {}, Colombia".format(direccion_norm, nombre_ciudad),
        "{}, {}, Colombia".format(direccion_limpia, nombre_ciudad),
        "{}, {}, Colombia".format(direccion.strip(), nombre_ciudad),
    ]

    # Intento simplificado con tipo de via + numero. En BOGOTÁ se omite: la
    # placa catastral ya se intentó arriba, y Nominatim sin el número de placa
    # devuelve el punto MEDIO de la vía, que en calles largas cae en otra
    # localidad (regresión: 'Diagonal 61B' -> Restrepo). En BAQ/MED las vías
    # son cortas y el fallback aproxima mejor; aun así se conserva.
    es_bogota_dir = _es_bogota(ciudad)
    if not es_bogota_dir:
        m = re.search(r"\b(CL|CRA|CR|AV|DG|TV|AP)\s+(\d+)", direccion_norm)
        if m:
            prefijo_map = {
                "CL": "Calle",
                "CRA": "Carrera",
                "CR": "Carrera",
                "AV": "Avenida",
                "DG": "Diagonal",
                "TV": "Transversal",
                "AP": "Autopista"
            }
            tipo_via = prefijo_map.get(m.group(1), "Calle")
            numero_via = m.group(2)
            intentos.append("{} {}, {}, Colombia".format(tipo_via, numero_via, nombre_ciudad))

    for query in intentos:
        resultado = _nominatim_query(query, ciudad)
        if resultado:
            _GEOCODE_CACHE[cache_key] = resultado
            return resultado

    print("[GEOCODER][WARN] Sin resultado especifico para '{}' en {}. Usando centroide.".format(direccion, nombre_ciudad))
    _GEOCODE_CACHE[cache_key] = _centroide(ciudad)
    return _GEOCODE_CACHE[cache_key]


def _nominatim_query(query, ciudad="Barranquilla"):
    """
    Ejecuta una query a Nominatim y filtra resultados dentro del bbox de la
    ciudad indicada (Barranquilla o Medellín). Descarta resultados que
    representen la municipalidad completa (nodo administrativo genérico).
    Retorna (lat, lon) o None si no hay resultado valido.
    """
    # Coordenadas exactas del nodo del municipio que Nominatim retorna como
    # fallback genérico (centroide administrativo, no es ningún predio)
    if _es_medellin(ciudad):
        nodo_generico = (6.2518405, -75.5635890)   # nodo ciudad de Medellín
    elif _es_bogota(ciudad):
        nodo_generico = (4.7110, -74.0721)          # nodo Bogotá D.C.
    elif _es_pasto(ciudad):
        nodo_generico = (1.2136, -77.2811)          # nodo ciudad de Pasto (Nariño)
    else:
        nodo_generico = (11.0101922, -74.8231794)  # nodo de Barranquilla
    lat_min, lat_max, lon_min, lon_max = _bbox(ciudad)

    try:
        params = urllib.parse.urlencode({
            "q": query,
            "format": "json",
            "limit": "3",
            "countrycodes": "co",
            "bounded": "1",
            "viewbox": "{},{},{},{}".format(lon_min, lat_max, lon_max, lat_min)
        })
        url = "https://nominatim.openstreetmap.org/search?{}".format(params)
        req = urllib.request.Request(url, headers={"User-Agent": "ARHIAX-RE/1.0 (Sinergia Consulting Group)"})

        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        for item in data:
            lat = float(item["lat"])
            lon = float(item["lon"])
            
            # 1. Descartar si coincide exactamente con el nodo genérico del municipio
            if abs(lat - nodo_generico[0]) < 0.0001 and abs(lon - nodo_generico[1]) < 0.0001:
                continue
                
            # 2. Descartar SIEMPRE los resultados administrativos genéricos
            # (city/county/administrative, p. ej. 'Perímetro Urbano Barranquilla'):
            # su centroide NO es la ubicación de ningún predio.
            if item.get("addresstype") in ("city", "county", "state", "region") or item.get("type") == "administrative":
                continue
            
            # 3. Validar que esté dentro de los límites geográficos de la ciudad
            if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
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

    # 0. Preferir la DIRECCION CATASTRAL oficial cuando el CTL la distingue
    # (Bogotá: 'DG 61B 20 04 AP 401 (DIRECCION CATASTRAL)' junto a placas
    # registrales alternativas 'AVENIDA (CALLE)63 20-04/CARRERA 20 61-55').
    idx_di = texto_pdf.upper().find("DIRECCION DEL INMUEBLE")
    if idx_di >= 0:
        ventana = texto_pdf[idx_di: idx_di + 700]
        m_cat = re.search(
            r"([A-Z0-9ÁÉÍÓÚÑ\.\#\-/ ]{4,90}?)\s*\(?\s*DIRECCION CATASTRAL",
            ventana, re.IGNORECASE)
        if m_cat:
            cand = m_cat.group(1).strip()
            cand = re.split(r"\s+(?:APARTAMENTO|APTO|AP\b|EDIFICIO|TORRE|CASA\b|"
                            r"CONJUNTO|BLOQUE|PISO|OFICINA|LOCAL|UNIDAD|PH\b|P\.H\.)\b",
                            cand)[0]
            cand = " ".join(cand.split()).strip(" .,;/")
            if _es_direccion_valida(cand):
                return cand

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


def geocodificar_desde_ctl(texto_pdf, ciudad="Barranquilla"):
    """
    Pipeline completo: texto del CTL -> direccion -> barrio -> (lat, lon).

    Args:
        texto_pdf: texto completo del CTL
        ciudad:    ciudad del predio ('barranquilla' | 'medellin' | ...)

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

    centroide = _centroide(ciudad)
    if direccion:
        lat, lon = geocodificar_direccion(direccion, ciudad)
        fuente = "centroide_fallback" if (lat, lon) == centroide else "nominatim"
    else:
        lat, lon = centroide
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


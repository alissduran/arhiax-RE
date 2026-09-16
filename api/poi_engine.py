import json
import math
import os
import tempfile
import time

import requests

# Caché de POIs (memoria + disco) por predio para no golpear Overpass en cada
# compilación. En Vercel la memoria persiste en la instancia caliente; el disco
# (/tmp) añade persistencia entre invocaciones de esa misma instancia.
_POI_CACHE = {}
_POI_TTL = 6 * 3600  # 6 horas: los POIs de OSM cambian poco

# Endpoints Overpass (públicos) que ALGUNA VEZ respondieron con datos, medidos
# en vivo. Los espejos públicos son BEST-EFFORT y fluctúan hora a hora: en la
# misma sesión se midió overpass-api.de OK (10 s) y luego HTTP 504; mail.ru 504
# y luego OK con 189 elementos (27 s). Por eso se listan los tres utilizables y
# se prueban en orden hasta que uno conteste (el presupuesto total los reparte).
# Descartados por inútiles: overpass.osm.ch (0 elementos en Colombia),
# overpass.osm.jp (404), overpass.openstreetmap.ru (inalcanzable),
# overpass.private.coffee (504 constante).
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
# Tiempos MEDIDOS de una consulta real de 2 km: 10-46 s según el espejo y su
# carga. Un timeout corto corta respuestas válidas y deja la sección 03 VACÍA
# (regresión real que reportó el usuario). Con Vercel Pro hay 300 s de función.
OVERPASS_TIMEOUT = 40.0
OVERPASS_REINTENTOS = 0  # sin reintento del mismo espejo: el presupuesto da para 3
# Presupuesto TOTAL (TOPE DURO de tiempo real) de la fase de POIs, en segundos:
# 3 espejos x 40 s. Al agotarse se devuelven categorías VACÍAS (el dictamen las
# declara NO DISPONIBLES: nunca inventa POIs ni distancias).
OVERPASS_PRESUPUESTO_TOTAL = 120.0

CATEGORIAS = ["Salud", "Educacion", "Comercio", "Recreacion"]


def _cache_dir():
    d = os.environ.get("ARHIA_POI_CACHE")
    if d:
        return d
    return os.path.join(tempfile.gettempdir(), "arhia_poi_cache")


def _celda(lat, lon):
    return (round(lat, 3), round(lon, 3))


def _clave(lat, lon, radius):
    c = _celda(lat, lon)
    return f"{c[0]}_{c[1]}_{radius}"


def _leer_disco(clave):
    try:
        p = os.path.join(_cache_dir(), clave + ".json")
        if not os.path.exists(p):
            return None
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        if time.time() - float(data.get("ts", 0)) < _POI_TTL:
            return data.get("pois")
    except Exception:
        return None
    return None


def _escribir_disco(clave, pois):
    try:
        os.makedirs(_cache_dir(), exist_ok=True)
        p = os.path.join(_cache_dir(), clave + ".json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"ts": time.time(), "pois": pois}, f, ensure_ascii=False)
    except Exception:
        pass


def haversine(lat1, lon1, lat2, lon2):
    """Calcula la distancia geodésica en metros entre dos puntos en la Tierra."""
    R = 6371.0  # Radio de la Tierra en km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c * 1000.0, 1)


def get_nearby_pois(lat, lon, radius=2000):
    """
    Consulta la API Overpass de OpenStreetMap para obtener hospitales, colegios,
    centros comerciales y parques en un radio dado, con las coordenadas REALES
    del predio geocodificado.

    Tolerancia: prueba varios espejos Overpass en orden (el más rápido primero),
    reintenta una vez ante timeout y usa caché (memoria + disco) de 6 h por
    predio. Postura honesta: SIEMPRE devuelve datos de OSM o listas VACÍAS.
    Nunca inventa POIs ni distancias. Si OSM no responde tras probar todos los
    espejos (con reintentos), devuelve las 4 categorías vacías y el dictamen lo
    declara como datos no disponibles.

    Retorna un dict {Salud, Educacion, Comercio, Recreacion} con listas de
    {"name", "distance", "type"} ordenadas por distancia (máx 3 por categoría).
    """
    query = f"""
    [out:json][timeout:20];
    (
      node["amenity"~"hospital|clinic|doctors|school|kindergarten|university"](around:{radius}, {lat}, {lon});
      way["amenity"~"hospital|clinic|doctors|school|kindergarten|university"](around:{radius}, {lat}, {lon});

      node["shop"~"mall|supermarket"](around:{radius}, {lat}, {lon});
      way["shop"~"mall|supermarket"](around:{radius}, {lat}, {lon});

      node["leisure"~"park|playground"](around:{radius}, {lat}, {lon});
      way["leisure"~"park|playground"](around:{radius}, {lat}, {lon});
    );
    out center 200;
    """

    def vacio():
        return {c: [] for c in CATEGORIAS}

    clave = _clave(lat, lon, radius)
    ahora = time.time()

    # 1) Caché en memoria (misma instancia, más rápida)
    if clave in _POI_CACHE:
        ts, cached = _POI_CACHE[clave]
        if ahora - ts < _POI_TTL:
            return cached

    # 2) Caché en disco (persiste entre invocaciones de la instancia caliente)
    disco = _leer_disco(clave)
    if disco is not None:
        _POI_CACHE[clave] = (ahora, disco)
        return disco

    headers = {"User-Agent": "ARHIAX-RE/1.0 (Sinergia Consulting Group)"}
    _limite_total = time.time() + OVERPASS_PRESUPUESTO_TOTAL

    for overpass_url in OVERPASS_ENDPOINTS:
        if time.time() >= _limite_total:
            break  # presupuesto total agotado: no seguir castigando la función
        for intento in range(OVERPASS_REINTENTOS + 1):
            if time.time() >= _limite_total:
                break
            try:
                # Timeout ADAPTATIVO: nunca pedir más tiempo del que queda.
                _restante = _limite_total - time.time()
                if _restante <= 1.0:
                    break
                _timeout_req = max(3.0, min(OVERPASS_TIMEOUT, _restante))
                # stream=True + lectura por bloques: da un TOPE DURO de tiempo
                # real. El timeout de requests es POR OPERACIÓN DE SOCKET, no
                # total: un servidor que envía lento tardaba 36 s pese a un
                # timeout de 25 s (medido) y se comía el presupuesto de la
                # función serverless.
                response = requests.post(overpass_url, data={"data": query},
                                         headers=headers, timeout=_timeout_req,
                                         stream=True)
                if response.status_code != 200:
                    response.close()
                    break  # error HTTP (p. ej. 429/504): pasar al siguiente espejo
                _trozos = []
                for _trozo in response.iter_content(8192):
                    _trozos.append(_trozo)
                    # Plazo ABSOLUTO de la fase (no desde el inicio de lectura):
                    # si no, cabeceras lentas + lectura lenta sumaban ~35 s.
                    if time.time() > _limite_total:
                        response.close()
                        raise TimeoutError("presupuesto de POIs agotado en la lectura")
                response.close()
                data = json.loads(b"".join(_trozos).decode("utf-8", "replace"))
                elements = data.get("elements", [])

                # Un 200 SIN elementos puede ser una réplica incompleta (p. ej.
                # sin datos de la región) o una zona realmente sin POIs. Se
                # prueba el siguiente espejo antes de asumir "sin equipamientos";
                # solo si TODOS devuelven vacío se retorna vacío (honesto).
                if not elements:
                    break

                pois_categorized = {c: [] for c in CATEGORIAS}

                for elem in elements:
                    tags = elem.get("tags", {})
                    name = tags.get("name")
                    if not name:
                        continue

                    # Obtener coordenadas del centro del elemento
                    elem_lat = elem.get("lat") or elem.get("center", {}).get("lat")
                    elem_lon = elem.get("lon") or elem.get("center", {}).get("lon")
                    if not elem_lat or not elem_lon:
                        continue

                    dist = haversine(lat, lon, elem_lat, elem_lon)

                    # Clasificación
                    amenity = tags.get("amenity")
                    shop = tags.get("shop")
                    leisure = tags.get("leisure")

                    poi_info = {"name": name, "distance": dist}

                    if amenity in ["hospital", "clinic", "doctors"]:
                        poi_info["type"] = "Salud (" + amenity.capitalize() + ")"
                        pois_categorized["Salud"].append(poi_info)
                    elif amenity in ["school", "kindergarten", "university"]:
                        poi_info["type"] = "Educacion (" + amenity.capitalize() + ")"
                        pois_categorized["Educacion"].append(poi_info)
                    elif shop in ["mall", "supermarket"] or tags.get("amenity") == "marketplace":
                        poi_info["type"] = "Comercio (" + (shop.capitalize() if shop else "Mercado") + ")"
                        pois_categorized["Comercio"].append(poi_info)
                    elif leisure in ["park", "playground"]:
                        poi_info["type"] = "Recreacion (" + leisure.capitalize() + ")"
                        pois_categorized["Recreacion"].append(poi_info)

                # Ordenar cada categoría por distancia y truncar a los 3 más cercanos
                for cat in pois_categorized:
                    pois_categorized[cat] = sorted(pois_categorized[cat],
                                                   key=lambda x: x["distance"])[:3]

                _POI_CACHE[clave] = (ahora, pois_categorized)
                _escribir_disco(clave, pois_categorized)
                return pois_categorized

            except (requests.exceptions.Timeout, TimeoutError):
                # BUG corregido: aquí se comparaba contra una constante MAL
                # ESCRITA (le faltaba "ER" al nombre de OVERPASS_REINTENTOS). Con
                # el nombre roto, CADA timeout de Overpass lanzaba NameError y
                # tumbaba la generación completa del dictamen (el usuario veía
                # "se queda pensando" y nunca salía el PDF).
                if intento < OVERPASS_REINTENTOS and time.time() < _limite_total:
                    time.sleep(1.0)  # backoff corto y reintentar el mismo espejo
                    continue
                break  # agotado el reintento: siguiente espejo
            except Exception:
                break  # error no-timeout: siguiente espejo

    # OSM no disponible en ningún espejo (con reintentos): categorías vacías.
    resultado = vacio()
    _POI_CACHE[clave] = (ahora, resultado)
    return resultado

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

# ── Respaldo Photon (komoot) ────────────────────────────────────────────────
# Overpass público bloquea/limita con frecuencia las IPs de DATACENTER (Vercel
# corre en AWS): puede funcionar desde una red residencial y devolver 504/429
# desde producción. Photon es una API pública SIN clave, estable y tolerante a
# datacenter, así que se usa como respaldo cuando Overpass no trae datos.
PHOTON_URL = "https://photon.komoot.io/api/"
# (término de búsqueda, etiqueta OSM que DEBE tener el resultado, etiqueta a mostrar).
# El filtro osm_tag es imprescindible: sin él Photon busca por NOMBRE y devuelve
# falsos positivos (medidos: "ParkTool", una marca de herramientas, aparecía como
# "Parque"; "Clínica de Ropa", una tienda, como "Clínica"). Eso sería desinformación.
PHOTON_TAGS = {
    "Salud": [("hospital", "amenity:hospital", "Salud (Hospital)"),
              ("clinic", "amenity:clinic", "Salud (Clinica)")],
    "Educacion": [("school", "amenity:school", "Educacion (Colegio)"),
                  ("kindergarten", "amenity:kindergarten", "Educacion (Jardin)"),
                  ("university", "amenity:university", "Educacion (Universidad)")],
    "Comercio": [("supermarket", "shop:supermarket", "Comercio (Supermercado)"),
                 ("mall", "shop:mall", "Comercio (Centro comercial)")],
    "Recreacion": [("park", "leisure:park", "Recreacion (Parque)")],
}


def _pois_desde_photon(lat, lon, radius=2000, timeout=8.0, categorias=None):
    """Respaldo de POIs vía Photon. Devuelve un dict {categoria: [poi]} SOLO para
    las categorías pedidas (fallback PER-CATEGORY, 03F), o None si Photon tampoco
    respondió (nunca inventa datos). Cada POI lleva source=PHOTON_OSM."""
    categorias = list(categorias or CATEGORIAS)
    resultado = {c: [] for c in categorias}
    hubo_respuesta = False
    headers = {"User-Agent": "ARHIAX-RE/1.0 (Sinergia Consulting Group)"}
    for categoria in categorias:
        vistos = set()
        for termino, osm_tag, etiqueta in PHOTON_TAGS.get(categoria, []):
            try:
                r = requests.get(PHOTON_URL, params={
                    "q": termino, "lat": lat, "lon": lon, "limit": 15,
                    "osm_tag": osm_tag,
                }, headers=headers, timeout=timeout)
                if r.status_code != 200:
                    continue
                hubo_respuesta = True
                for f in (r.json() or {}).get("features", []):
                    props = f.get("properties") or {}
                    nombre = props.get("name")
                    coords = (f.get("geometry") or {}).get("coordinates") or []
                    if not nombre or len(coords) != 2:
                        continue
                    # Verificación extra del tipo: el resultado debe traer la
                    # etiqueta OSM pedida (defensa contra falsos positivos).
                    _tag_real = f"{props.get('osm_key')}:{props.get('osm_value')}"
                    if props.get("osm_key") and _tag_real != osm_tag:
                        continue
                    plon, plat = coords[0], coords[1]
                    dist = haversine(lat, lon, plat, plon)
                    if dist > radius or nombre.lower() in vistos:
                        continue
                    vistos.add(nombre.lower())
                    resultado[categoria].append(
                        {"name": nombre, "distance": dist, "type": etiqueta,
                         "source": "PHOTON_OSM"})
            except Exception:
                continue
        resultado[categoria] = sorted(
            resultado[categoria], key=lambda x: x["distance"])[:3]
    if not hubo_respuesta:
        return None
    return resultado


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


def _norm_name(name):
    return " ".join(str(name or "").strip().lower().split())


def merge_poi_sources(overpass_pois, photon_pois, max_por_categoria=3):
    """Combina por categoría (03F): Overpass válido + Photon solo para faltantes.

    1. preserva los resultados válidos de Overpass por categoría;
    2. rellena SOLO las categorías faltantes con Photon;
    3. deduplica por nombre normalizado (no mostrar dos veces el mismo lugar);
    4. ordena por distancia y limita a `max_por_categoria`.

    Devuelve un dict {categoria: [poi]} con cada POI = {name, distance, type, source}.
    """
    merged = {}
    for cat in CATEGORIAS:
        ov = list(overpass_pois.get(cat) or [])
        ph = list(photon_pois.get(cat) or [])
        origen = ov if ov else ph
        vistos = set()
        unicos = []
        for p in sorted(origen, key=lambda x: (x.get("distance") is None, x.get("distance") or 0.0)):
            clave = _norm_name(p.get("name"))
            if clave and clave in vistos:
                continue
            if clave:
                vistos.add(clave)
            unicos.append(p)
        merged[cat] = unicos[:max_por_categoria]
    return merged


def poi_category_status(pois):
    """Estado por categoría (03F): AVAILABLE si hay POIs; NO_MATCH si vacía.

    Una lista vacía NO se interpreta como 'no existen parques': puede ser
    fallo de la fuente (SOURCE_UNAVAILABLE se decide en el llamador, cuando
    TODAS las categorías quedaron vacías).
    """
    return {c: ("AVAILABLE" if (pois or {}).get(c) else "NO_MATCH") for c in CATEGORIAS}


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
                    print(f"[POI] {overpass_url} HTTP {response.status_code}")
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

                    poi_info = {"name": name, "distance": dist,
                                "source": "OSM_OVERPASS"}

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

                # 03F: Overpass puede responder parcialmente (algunas categorías
                # vacías). Se completa POR CATEGORÍA con Photon (solo las
                # faltantes), sin devolver temprano ni inventar POIs.
                _faltantes = [c for c in CATEGORIAS if not pois_categorized.get(c)]
                if _faltantes:
                    try:
                        _ph = _pois_desde_photon(lat, lon, radius=radius,
                                                 categorias=_faltantes)
                    except Exception as _e_ph:
                        print(f"[POI][PHOTON] sin respaldo por categoria: {str(_e_ph)[:60]}")
                        _ph = None
                    if _ph:
                        pois_categorized = merge_poi_sources(pois_categorized, _ph)

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
            except Exception as _e:
                print(f"[POI] {overpass_url} fallo: {str(_e)[:60]}")
                break  # error no-timeout: siguiente espejo

    # Overpass no trajo datos (todos los espejos caídos/limitados). Respaldo
    # Photon antes de declarar la sección como NO DISPONIBLE.
    try:
        respaldo = _pois_desde_photon(lat, lon, radius=radius)
    except Exception as _e_ph:
        print(f"[POI][PHOTON] sin respaldo: {str(_e_ph)[:60]}")
        respaldo = None
    if respaldo and any(respaldo.values()):
        _POI_CACHE[clave] = (ahora, respaldo)
        _escribir_disco(clave, respaldo)
        return respaldo

    print("[POI] SIN DATOS: Overpass y Photon no respondieron "
          "(la seccion 03 se declara NO DISPONIBLE)")
    resultado = vacio()
    _POI_CACHE[clave] = (ahora, resultado)
    return resultado

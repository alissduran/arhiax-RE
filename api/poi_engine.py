import math
import time

import requests

# Caché en memoria de POIs por celda (~110 m) para evitar golpear Overpass en
# cada compilación de dictamen del mismo predio (rendimiento en Vercel).
_POI_CACHE = {}
_POI_TTL = 6 * 3600  # 6 horas: los POIs de OSM cambian poco

# Endpoints Overpass (públicos). Se prueban en orden hasta obtener respuesta.
# Los servidores públicos están a menudo saturados (de puede tardar >20 s); se
# incluyen espejos alternativos. El caché por celda (6 h) amortiza el costo.
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
OVERPASS_TIMEOUT = 18.0

CATEGORIAS = ["Salud", "Educacion", "Comercio", "Recreacion"]


def _celda(lat, lon):
    return (round(lat, 3), round(lon, 3))


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

    Postura honesta (M-03 corregido): SIEMPRE se devuelven datos de OSM o listas
    VACÍAS. Nunca se inventan POIs ni distancias (los "POIs referenciales" de
    Miramar/El Recreo fueron eliminados: presentaban lugares que no corresponden
    a la ubicación real del predio). Si OSM no responde tras probar los endpoints,
    se devuelven las 4 categorías vacías y el dictamen lo declara como datos
    no disponibles.

    Retorna un dict {Salud, Educacion, Comercio, Recreacion} con listas de
    {"name", "distance", "type"} ordenadas por distancia (máx 3 por categoría).
    """
    # Consulta Overpass para las categorías solicitadas
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
    out center;
    """

    def vacio():
        return {c: [] for c in CATEGORIAS}

    # Caché en memoria por celda (evita la llamada a Overpass en compilaciones repetidas)
    celda = _celda(lat, lon)
    ahora = time.time()
    if celda in _POI_CACHE:
        ts, cached = _POI_CACHE[celda]
        if ahora - ts < _POI_TTL:
            return cached

    headers = {"User-Agent": "ARHIAX-RE/1.0 (Sinergia Consulting Group)"}

    for overpass_url in OVERPASS_ENDPOINTS:
        try:
            response = requests.post(overpass_url, data={"data": query}, headers=headers,
                                     timeout=OVERPASS_TIMEOUT)
            if response.status_code != 200:
                continue
            data = response.json()
            elements = data.get("elements", [])

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
                pois_categorized[cat] = sorted(pois_categorized[cat], key=lambda x: x["distance"])[:3]

            _POI_CACHE[celda] = (ahora, pois_categorized)
            return pois_categorized
        except Exception:
            continue  # probar el siguiente endpoint

    # OSM no disponible en ningún endpoint: categorías vacías (sin datos inventados)
    _POI_CACHE[celda] = (ahora, vacio())
    return vacio()

import os
import json
from pathlib import Path
from shapely.geometry import shape, Point
from shapely.strtree import STRtree

# Caché en memoria para evitar recargar GeoJSON pesados en cada petición
_SPATIAL_CACHE = None

def _get_geojson_paths():
    """Busca las capas POT. Prioridad: api/data/ (empaquetadas con la app, F-17).
    Retrocompatibilidad: raíz del repo en desarrollo local. Sin rutas absolutas."""
    base_dir = Path(__file__).resolve().parent  # api/
    data_dir = base_dir / "data"
    root_dir = base_dir.parent

    path_amenaza = data_dir / "amenaza_remocion_masa.geojson"
    path_riesgo = data_dir / "areas_en_riesgo.geojson"

    if not path_amenaza.exists():
        path_amenaza = root_dir / "Amenaza por remoción en masa.geojson"
    if not path_riesgo.exists():
        path_riesgo = root_dir / "Áreas en riesgo.geojson"

    return path_amenaza, path_riesgo

def load_geospatial_index():
    """
    Carga y construye índices espaciales (STRtree) para Amenaza y Riesgo.
    Retorna una tupla (index_amenaza, index_riesgo).
    Si las capas no están disponibles, NO cachea el fallo (permite reintentos).
    """
    global _SPATIAL_CACHE
    if _SPATIAL_CACHE is not None:
        return _SPATIAL_CACHE

    path_amenaza, path_riesgo = _get_geojson_paths()

    def build_layer(filepath, level_key, soil_key):
        items = [] # (geometry, properties)
        geoms = []
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for feat in data.get('features', []):
                geom_raw = feat.get('geometry')
                props = feat.get('properties', {})
                if geom_raw:
                    try:
                        g = shape(geom_raw)
                        geoms.append(g)
                        items.append({
                            'geometry': g,
                            'properties': props,
                            'level': props.get(level_key, 'Desconocido'),
                            'clase_suelo': props.get(soil_key, 'N/A'),
                            'area_m2': props.get('st_area(shape)', 0) or 0,
                            'objectid': props.get('objectid')
                        })
                    except Exception:
                        pass
        tree = STRtree(geoms) if geoms else None
        return tree, items

    tree_amenaza, items_amenaza = build_layer(path_amenaza, 'niveldeamenaza', 'clase_suelo')
    tree_riesgo, items_riesgo = build_layer(path_riesgo, 'nivelderiesgo', 'clasesuelo')

    capas_disponibles = bool(tree_amenaza and tree_riesgo)
    _SPATIAL_CACHE = {
        'amenaza': {'tree': tree_amenaza, 'items': items_amenaza},
        'riesgo': {'tree': tree_riesgo, 'items': items_riesgo},
        'capas_disponibles': capas_disponibles
    }
    if not capas_disponibles:
        _SPATIAL_CACHE = None  # no cachear el fallo
    return _SPATIAL_CACHE

def _evaluar_predio_impl(lat: float, lon: float) -> dict:
    """
    Evalúa la posición geográfica (lat, lon) de un predio frente a las capas de Amenaza y Riesgo.

    Retorna un diccionario estructurado con los diagnósticos de ambas capas.

    CONTRATO (BLOCK 1 · §17) — la clave `evaluado` es OBLIGATORIA en TODAS las ramas
    (incluida la de excepción) y significa: «esta corrida cruzó el punto contra las
    capas del POT y obtuvo un veredicto espacial». Nunca significa «en vivo» (el modo
    se declara aparte en `modo`) ni «sin afectación». Antes la clave NO existía y el
    consumidor (`api/receipts.py`) leía `bool(geo.get("evaluado"))` ⇒ `false` SIEMPRE,
    incluso cuando `amenaza_remocion_masa`/`areas_en_riesgo` ya declaraban «polígono:
    intersecta el predio». Regla §17: si hubo consulta válida + geometría evaluada +
    fuente válida + resultado espacial, NO puede quedar `NOT_EVALUATED`.
    """
    cache = load_geospatial_index()
    point = Point(lon, lat)
    
    def query_layer(layer_data, level_default):
        tree = layer_data['tree']
        items = layer_data['items']
        
        if tree is None or not items:
            return {
                'intersecta': False,
                'nivel': level_default,
                'clase_suelo': 'N/A',
                'area_poligono_m2': 0,
                'objectid': None,
                'detalles': []
            }
            
        # STRtree query busca candidatos rápida por BBOX
        candidates_idx = tree.query(point)
        
        matches = []
        for idx in candidates_idx:
            item = items[idx]
            if item['geometry'].contains(point):
                matches.append(item)
                
        if matches:
            # Regresión (dictamen real 040-646406): el punto puede caer en varios
            # polígonos de la MISMA capa (p. ej. un polígono 'Baja' gigante de
            # fondo que cubre la ciudad y uno 'Media' local de 6.046 m2). Tomar
            # matches[0] (orden del STRtree) reportaba 'Baja' y el dictamen decía
            # 'Afectación Detectada (Baja)' con severidad MEDIO y 'Riesgo Medio'
            # en la descripción — sin sentido. Se elige la coincidencia de MAYOR
            # severidad (y, a igualdad, la de menor área = la más específica).
            orden_severidad = {'muy alta': 4, 'muy alto': 4, 'alta': 3, 'alto': 3,
                               'media': 2, 'medio': 2, 'baja': 1, 'bajo': 1,
                               'desconocido': 0, 'sin amenaza identificada': 0,
                               'sin riesgo identificado': 0, 'indeterminado': 0,
                               'n/a': 0, 'na': 0, 'none': 0, '': 0}
            def _clave(m):
                nivel = str(m['level']).strip().lower()
                return (orden_severidad.get(nivel, 0),
                        -float(m.get('area_m2') or 0))  # menor área desempata
            first = max(matches, key=_clave)
            return {
                'intersecta': True,
                'nivel': first['level'],
                'clase_suelo': 'Urbano (01)' if str(first['clase_suelo']) in ['1', '01'] else f"Clase {first['clase_suelo']}",
                'area_poligono_m2': first['area_m2'],
                'objectid': first['objectid'],
                'total_coincidencias': len(matches),
                'detalles': [m['properties'] for m in matches]
            }
        else:
            return {
                'intersecta': False,
                'nivel': level_default,
                'clase_suelo': 'Sin afectación directa',
                'area_poligono_m2': 0,
                'objectid': None,
                'total_coincidencias': 0,
                'detalles': []
            }

    res_amenaza = query_layer(cache['amenaza'], 'Sin amenaza identificada')
    res_riesgo = query_layer(cache['riesgo'], 'Sin riesgo identificado')

    # Mapeo de colores cromáticos ARHIAX para semáforo de riesgo
    color_map = {
        'Muy Alta': '#8B0000', # Rojo Oscuro
        'Muy alto': '#8B0000',
        'Alta': '#D9381E',     # Rojo
        'Alto': '#D9381E',
        'Media': '#E67E22',    # Naranja
        'Medio': '#E67E22',
        'Baja': '#27AE60',     # Verde
        'Bajo': '#27AE60',
        'Sin amenaza identificada': '#2ECC71',
        'Sin riesgo identificado': '#2ECC71'
    }

    # Resumen Sintético
    if not cache.get("capas_disponibles"):
        # F-17/H-11: si las capas no están, NO afirmar "sin afectación": marcar NO EVALUADO
        summary = (
            "No se completó la verificación espacial: capas del POT no disponibles "
            "(faltan los datos empaquetados de la aplicación). El resultado debe "
            "considerarse NO EVALUADO y requiere verificación geotécnica."
        )
    else:
        amenaza_text = f"Amenaza {res_amenaza['nivel']}" if res_amenaza['intersecta'] else "Sin Amenaza Identificada"
        riesgo_text = f"Riesgo {res_riesgo['nivel']}" if res_riesgo['intersecta'] else "Sin Riesgo Identificado"
        summary = (
            f"El predio ubicado en ({lat:.5f}, {lon:.5f}) presenta evaluación de {amenaza_text} por remoción en masa "
            f"y zonificación de {riesgo_text} según el Plan de Ordenamiento Territorial (POT) de Barranquilla."
        )

    # ── CONTRATO §17: `evaluado` + su motivo, en TODAS las ramas ──────────────
    # Las capas del POT vienen EMPAQUETADAS (`api/data/*.geojson`) y se cruzan con un
    # STRtree LOCAL: el modo se declara como tal (`PACKAGED_GEOMETRY_QUERY`) para no
    # confundir «evaluado» con «consultado en vivo» (el invariante I-NORECORD-NOEVAL de
    # `api/consistency.py` prohíbe presentar un NO_RECORD como EVALUADO EN VIVO).
    _capas = bool(cache.get("capas_disponibles"))
    _punto_valido = (isinstance(lat, (int, float)) and isinstance(lon, (int, float))
                     and -90.0 <= float(lat) <= 90.0 and -180.0 <= float(lon) <= 180.0)
    _evaluado = bool(_capas and _punto_valido)
    if _evaluado:
        _motivo_evaluado = ("Las capas del POT se consultaron para el punto y devolvieron "
                            "veredicto espacial (cruce local STRtree sobre las capas "
                            "empaquetadas): hay resultado espacial, no una ausencia.")
    elif not _punto_valido:
        _motivo_evaluado = ("No hay coordenada utilizable: sin punto no se ejecuta el cruce "
                            "espacial y el resultado queda NO EVALUADO.")
    else:
        _motivo_evaluado = ("Las capas empaquetadas del POT no están disponibles: ningún "
                            "cruce espacial se ejecutó, así que el resultado NO se evalúa "
                            "(nunca «sin afectación»).")
    return {
        'coordenadas': {'lat': lat, 'lon': lon},
        # §17 · estado de la EVALUACIÓN (no del riesgo): obligatorio y explícito.
        'evaluado': _evaluado,
        'modo': 'PACKAGED_GEOMETRY_QUERY',
        'layers_available': _capas,
        'motivo_evaluado': _motivo_evaluado,
        'evaluacion': {
            'evaluado': _evaluado,
            'modo': 'PACKAGED_GEOMETRY_QUERY',
            'capas_disponibles': _capas,
            'punto': {'lat': lat, 'lon': lon},
            'motivo': _motivo_evaluado,
        },
        'amenaza_remocion_masa': {
            **res_amenaza,
            'color_hex': color_map.get(res_amenaza['nivel'], '#7F8C8D')
        },
        'areas_en_riesgo': {
            **res_riesgo,
            'color_hex': color_map.get(res_riesgo['nivel'], '#7F8C8D')
        },
        'resumen_ejecutivo': summary
    }


def evaluate_predio(lat: float, lon: float) -> dict:
    """Evaluación espacial del predio contra las capas del POT, con estado DECLARADO.

    La rama de EXCEPCIÓN también declara el estado: un fallo del cruce espacial es
    `evaluado=False` con su motivo exacto, nunca una ausencia silenciosa ni un
    `NO_MATCH` (regla §27/§18: una ausencia no se convierte en «sin afectación»).
    """
    try:
        if not (isinstance(lat, (int, float)) and isinstance(lon, (int, float))
                and -90.0 <= float(lat) <= 90.0 and -180.0 <= float(lon) <= 180.0):
            raise ValueError(f"coordenada no utilizable (lat={lat!r}, lon={lon!r})")
        return _evaluar_predio_impl(lat, lon)
    except Exception as exc:  # noqa: BLE001 — el fallo es un ESTADO, no una excepción
        detalle = f"{type(exc).__name__}: {exc}"
        _sin_punto = "coordenada no utilizable" in detalle
        _motivo = ("No hay coordenada utilizable: sin punto no se ejecuta el cruce espacial "
                   "y el resultado queda NO EVALUADO."
                   if _sin_punto else
                   "El cruce espacial no se pudo ejecutar: el resultado queda NO EVALUADO "
                   "(capa del POT no consultable).")
        return {
            'coordenadas': {'lat': lat, 'lon': lon},
            'evaluado': False,
            'modo': 'PACKAGED_GEOMETRY_QUERY',
            'layers_available': False,
            'motivo_evaluado': _motivo,
            'error': detalle,
            'evaluacion': {'evaluado': False, 'modo': 'PACKAGED_GEOMETRY_QUERY',
                           'capas_disponibles': False,
                           'punto': {'lat': lat, 'lon': lon},
                           'motivo': _motivo,
                           'error': detalle},
            'amenaza_remocion_masa': {'intersecta': False, 'nivel': None,
                                      'clase_suelo': 'N/D', 'area_poligono_m2': 0,
                                      'objectid': None, 'total_coincidencias': 0,
                                      'detalles': [], 'color_hex': '#7F8C8D'},
            'areas_en_riesgo': {'intersecta': False, 'nivel': None,
                                'clase_suelo': 'N/D', 'area_poligono_m2': 0,
                                'objectid': None, 'total_coincidencias': 0,
                                'detalles': [], 'color_hex': '#7F8C8D'},
            'resumen_ejecutivo': (
                "No se completó la verificación espacial: el cruce contra las capas del POT "
                f"falló ({detalle}). El resultado debe considerarse NO EVALUADO."),
        }

if __name__ == "__main__":
    # Test directo al ejecutar el script
    sample_lat, sample_lon = 10.9985, -74.8252
    diag = evaluate_predio(sample_lat, sample_lon)
    print("DIAGNÓSTICO GEOESPACIAL TEST:")
    print(json.dumps(diag, indent=2, ensure_ascii=False))

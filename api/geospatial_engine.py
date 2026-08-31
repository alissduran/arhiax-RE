import os
import json
from pathlib import Path
from shapely.geometry import shape, Point
from shapely.strtree import STRtree

# Caché en memoria para evitar recargar GeoJSON pesados en cada petición
_SPATIAL_CACHE = None

def _get_geojson_paths():
    """Busca las rutas absolutas de los archivos GeoJSON."""
    base_dir = Path(__file__).resolve().parent
    root_dir = base_dir.parent
    
    path_amenaza = root_dir / "Amenaza por remoción en masa.geojson"
    path_riesgo = root_dir / "Áreas en riesgo.geojson"
    
    if not path_amenaza.exists():
        path_amenaza = Path("C:/Users/aliss/Documents/Sinergia/RE/Amenaza por remoción en masa.geojson")
    if not path_riesgo.exists():
        path_riesgo = Path("C:/Users/aliss/Documents/Sinergia/RE/Áreas en riesgo.geojson")
        
    return path_amenaza, path_riesgo

def load_geospatial_index():
    """
    Carga y construye índices espaciales (STRtree) para Amenaza y Riesgo.
    Retorna una tupla (index_amenaza, index_riesgo).
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

    _SPATIAL_CACHE = {
        'amenaza': {'tree': tree_amenaza, 'items': items_amenaza},
        'riesgo': {'tree': tree_riesgo, 'items': items_riesgo}
    }
    return _SPATIAL_CACHE

def evaluate_predio(lat: float, lon: float) -> dict:
    """
    Evalúa la posición geográfica (lat, lon) de un predio frente a las capas de Amenaza y Riesgo.
    
    Retorna un diccionario estructurado con los diagnósticos de ambas capas.
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
            # Tomamos la de mayor severidad o la primera coincidencia
            first = matches[0]
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
    amenaza_text = f"Amenaza {res_amenaza['nivel']}" if res_amenaza['intersecta'] else "Sin Amenaza Identificada"
    riesgo_text = f"Riesgo {res_riesgo['nivel']}" if res_riesgo['intersecta'] else "Sin Riesgo Identificado"

    summary = (
        f"El predio ubicado en ({lat:.5f}, {lon:.5f}) presenta evaluación de {amenaza_text} por remoción en masa "
        f"y zonificación de {riesgo_text} según el Plan de Ordenamiento Territorial (POT) de Barranquilla."
    )

    return {
        'coordenadas': {'lat': lat, 'lon': lon},
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

if __name__ == "__main__":
    # Test directo al ejecutar el script
    sample_lat, sample_lon = 10.9985, -74.8252
    diag = evaluate_predio(sample_lat, sample_lon)
    print("DIAGNÓSTICO GEOESPACIAL TEST:")
    print(json.dumps(diag, indent=2, ensure_ascii=False))

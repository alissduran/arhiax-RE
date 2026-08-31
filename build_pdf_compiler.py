import os, sys
from pathlib import Path

def main():
    with open('dictamen_napoli.py', 'r', encoding='utf-8') as f:
        orig = f.read()

    prefix = """import sys, os, hashlib, datetime
from pathlib import Path
from reportlab.platypus import SimpleDocTemplate, Spacer, Paragraph, Table, TableStyle, PageBreak, KeepTogether
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import Image as RLImage
from dictamen_part1_styles import *
from solar_engine import get_solar_position, analyze_facade_exposure
from poi_engine import get_nearby_pois
from map_generator import generate_maps
from address_normalizer import normalize_address_colombia

from dictamen_data import get_valuation, get_hallazgos, get_recs, get_identificacion_dt, get_localizacion_dt, get_cobertura_alert, get_analisis_registral_text, get_catastral_dt, get_pot_summary_dt, get_valoracion_alert, get_alcance_dt

API_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = API_DIR.parent
PAQUETE_ROOT = PROJECT_ROOT / 'motor_tma_lonja_baq_v1.0' / 'motor_tma_lonja_baq_v1.0'
sys.path.insert(0, str(PAQUETE_ROOT / 'tma_engine' / 'piezas'))
sys.path.insert(0, str(PAQUETE_ROOT / 'tma_engine' / 'datos'))
sys.path.insert(0, str(PAQUETE_ROOT / 'lonja_layer'))
sys.path.insert(0, str(API_DIR))
sys.path.insert(0, str(PROJECT_ROOT))

def compile_pdf(db_record: dict, output_pdf_path: str, assets_dir: Path = None):
    folio = db_record.get('folio_matricula', '040-XXXXXX')
    direccion = normalize_address_colombia(db_record.get('direccion', ''))
    barrio = db_record.get('barrio', '')
    area = float(db_record.get('area', 0))
    is_miramar = 'miramar' in barrio.lower()
    
    val_data = get_valuation(area, barrio)
    res_avaluo = val_data
    hallazgos = get_hallazgos(barrio)
    recs = get_recs(barrio)
    
    cert_num = f'ARHIAX-LAI-2026-{db_record.get("id", 0):04d}'
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    p_hash = hashlib.sha256(f'{folio}{cert_num}{now_utc.isoformat()}'.encode()).hexdigest()
    
    if assets_dir is None:
        if os.environ.get('VERCEL') or not os.access(str(API_DIR), os.W_OK):
            assets_dir = Path('/tmp/assets') / f'case_{db_record.get("id", 0)}'
        else:
            assets_dir = API_DIR / 'assets' / f'case_{db_record.get("id", 0)}'
    assets_dir.mkdir(parents=True, exist_ok=True)
    
    shadow_9am_path = str(assets_dir / 'sombra_9am.png')
    shadow_3pm_path = str(assets_dir / 'sombra_3pm.png')
    mapa_satellite_path = str(assets_dir / 'mapa_satelital.png')
    
    if not os.path.exists(shadow_9am_path): shadow_9am_path = str(PROJECT_ROOT / ('napoli_shadows.png' if is_miramar else 'recreo_shadows.png'))
    if not os.path.exists(shadow_3pm_path): shadow_3pm_path = str(PROJECT_ROOT / ('napoli_shadows2.png' if is_miramar else 'recreo_shadows2.png'))
    if not os.path.exists(mapa_satellite_path): mapa_satellite_path = str(PROJECT_ROOT / ('napoli_apartamentos_satellite_1778115269833.png' if is_miramar else 'recreo_poi_map.png'))
    
    poi_map_png = str(assets_dir / 'poi_map.png')
    poi_map_html = str(assets_dir / 'poi_map.html')
    
    BARRIO_COORDS = {'miramar': (10.9870, -74.8115), 'el recreo': (10.9838, -74.7998), 'recreo': (10.9838, -74.7998)}
    coords = BARRIO_COORDS.get(barrio.lower().strip(), (10.9870, -74.8115))
    lat, lon = coords
    
    pois = get_nearby_pois(lat, lon, radius=2000)
    generate_maps(lat, lon, pois, poi_map_png, poi_map_html)
    
    def fmt_cop(val):
        return f'$ {val:,.0f}'.replace(',', '.')
    
    FOLIO = folio
    CERT_NUM = cert_num
    NOW_UTC = now_utc
    P_HASH = p_hash
    MAP_IMG = mapa_satellite_path
    OUTPUT = output_pdf_path
    POI_MAP_PNG = poi_map_png
    SHADOW_9AM_IMG = shadow_9am_path
    SHADOW_3PM_IMG = shadow_3pm_path\n"""

    start_idx = orig.find('SCOPE_DISCLAIMER_FULL')
    end_idx = len(orig)
    body = orig[start_idx:end_idx]

    body_indented = []
    for line in body.splitlines():
        body_indented.append('    ' + line)

    body_str = '\n'.join(body_indented)

    # 1. Remove generate_maps
    body_str = body_str.replace('    generate_maps(lat, lon, pois, POI_MAP_PNG, POI_MAP_HTML)', '')

    # 2. Dynamic Tables Substitution
    cat_orig = '''    story.append(dt([
        ("Area SNR (Escritura 2875/2023)", "58,75 m2 privada construida"),
        ("Coeficiente", "0,2037%"),
        ("NUPRE", "080010102200400020043000000000"),
        ("Destino economico catastral", "HABITACIONAL (GIS REST Layer 5)"),
    ]))'''
    body_str = body_str.replace(cat_orig, '    story.append(dt(get_catastral_dt(barrio, area)))')

    pot_orig = '''    story.append(dt([
        ("Clasificacion del suelo", "SUELO URBANO (Capa 1 - confirmado)"),
        ("Norma uso de suelo", "ACTIVIDAD CENTRAL (Capa 2 - confirmado)"),
        ("Tratamiento urbanistico", "CONSOLIDACION -- Niveles 1B, 2 y Especial (Capa 4 - 5 poligonos)"),
        ("Altura maxima segun tratamiento", "5 pisos (Nivel 1B) a 11 pisos (Nivel 2) o segun Acuerdo (Especial)"),
        ("Planes Parciales", "SIN AFECTACION (Capa 3 - 0 features)"),
        ("Planes de Reordenamiento", "SIN AFECTACION (Capa 5 - 0 features)"),
        ("Endpoint", "miciudad.barranquilla.gov.co/gis/rest/services/ordenamiento/planeacion/MapServer"),
    ]))'''
    body_str = body_str.replace(pot_orig, '    story.append(dt(get_pot_summary_dt(barrio)))')
    
    # 3. Dynamic Identification
    ident_orig = '''    story.append(dt([
        ("Matricula Inmobiliaria", f"{FOLIO} (Circulo Registral 040 Barranquilla)"),
        ("Direccion oficial", "Transversal 43 No 100-50, Torre 8, Apto 430"),
        ("Tipologia", "Apartamento -- Propiedad Horizontal (NO VIS)"),
        ("Area privada construida", "58,75 m2 (Esc. 2875/2023)"),
        ("Coeficiente de copropiedad", "0,2037%"),
        ("Apertura del folio", "10 de mayo de 2023, Escritura 712/23-03-2023, Notaria 1a BAQ"),
        ("NUPRE", "080010102200400020043000000000 (actualizado GC-BAQ Mar 2025)"),
        ("Titulares vigentes", "Duran Bacca Alisson (CC 1.045.718.995) 50% + Triana Abello Brayan Dario (CC 1.140.834.790) 50%"),
        ("Modalidad de adquisicion", "Compraventa NO VIS -- Esc. 2875/11-10-2023, Valor: $268.516.940"),
        ("Valor Comercial Consolidado", f"{fmt_cop(res_avaluo['consolidado'])} COP (Banda: {fmt_cop(res_avaluo['banda_baja'])} -- {fmt_cop(res_avaluo['banda_alta'])})"),
        ("Constructor / Enajenante", "Urbanizadora Marval S.A.S. (NIT 830.012.053-3)"),
        ("Acreedor hipotecario (SNR)", "Banco de Bogota S.A. (NIT 860.002.964-4) -- SEGUN CERTIFICADO SNR"),
        ("Acreedor hipotecario (REAL)", "SCOTIABANK COLPATRIA S.A. -- Cesion de cartera. El SNR NO refleja este cambio"),
        ("ORIP", "Oficina de Registro de Instrumentos Publicos -- Barranquilla"),
        ("Fuente registral", f"Certificado SNR actualizado (Turno 2026-040-1-108528, 06-May-2026)"),
    ]))'''
    body_str = body_str.replace(ident_orig, '    story.append(dt(get_identificacion_dt(barrio, db_record, val_data, fmt_cop)))')

    loc_orig = '''    story.append(dt([
        ("Coordenadas WGS84", f"Lat: {lat} N | Lon: {lon} W"),
        ("Sector urbano", "Nte. Centro Historico / Miramar"),
        ("Barrio catastral", "Miramar - Sector Napoli"),
        ("Infraestructura vial", "Tv 43 (acceso) / Calle 100 / Av. Circunvalar"),
        ("Equipamientos cercanos", "Parque Miramar (~150m), Centro Comercial Miramar (~300m)"),
    ]))'''
    body_str = body_str.replace(loc_orig, '    story.append(dt(get_localizacion_dt(barrio, lat, lon)))')

    with open('api/pdf_compiler.py', 'w', encoding='utf-8') as f:
        f.write(prefix + body_str)
        f.write('\n    return cert_num, p_hash\n')

if __name__ == '__main__':
    main()

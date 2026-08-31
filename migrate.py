import os

def migrate_dictamen():
    with open('dictamen_napoli.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()

    imports = []
    body = []
    
    in_body = False
    for line in lines:
        if line.startswith('import ') or line.startswith('from '):
            imports.append(line)
        elif line.startswith('sys.path'):
            imports.append(line)
        elif line.startswith('# ── SISTEMA DE AJUSTE'):
            imports.append(line)
        elif line.startswith('def obtener_avaluo'):
            in_body = True
            body.append(line)
        elif in_body:
            body.append(line)
        elif line.startswith('FOLIO'):
            in_body = True
            body.append(line)
        else:
            if not in_body:
                imports.append(line)
            else:
                body.append(line)

    with open('api/pdf_compiler.py', 'w', encoding='utf-8') as f:
        f.write("".join(imports))
        f.write("\n\n")
        f.write("def compile_pdf(db_record, output_pdf_path, assets_dir=None):\n")
        f.write("    import datetime, hashlib, os\n")
        f.write("    from dictamen_data import get_valuation, get_hallazgos, get_recs, get_identificacion_dt, get_localizacion_dt, get_cobertura_alert, get_analisis_registral_text, get_catastral_dt, get_pot_summary_dt, get_valoracion_alert, get_alcance_dt\n")
        f.write("    from poi_engine import get_nearby_pois\n")
        f.write("    from map_generator import generate_maps\n")
        f.write("    barrio = db_record.get('barrio', '')\n")
        f.write("    folio = db_record.get('folio_matricula', '040-XXXXXX')\n")
        f.write("    area = float(db_record.get('area', 0))\n")
        f.write("    direccion = db_record.get('direccion', '')\n")
        f.write("    is_miramar = 'miramar' in barrio.lower()\n")
        
        for line in body:
            f.write("    " + line)

if __name__ == '__main__':
    migrate_dictamen()

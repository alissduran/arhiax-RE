import sys
from pathlib import Path

# Configurar sys.path para importar correctamente el motor
PROJECT_ROOT = Path(__file__).resolve().parent
TMA_PIEZAS = PROJECT_ROOT / "motor_tma_lonja_baq_v1.0" / "motor_tma_lonja_baq_v1.0" / "tma_engine" / "piezas"
TMA_DATOS = PROJECT_ROOT / "motor_tma_lonja_baq_v1.0" / "motor_tma_lonja_baq_v1.0" / "tma_engine" / "datos"
LONJA_LAYER = PROJECT_ROOT / "motor_tma_lonja_baq_v1.0" / "motor_tma_lonja_baq_v1.0" / "lonja_layer"

sys.path.insert(0, str(TMA_PIEZAS))
sys.path.insert(0, str(TMA_DATOS))
sys.path.insert(0, str(LONJA_LAYER))
sys.path.insert(0, str(PROJECT_ROOT))

from api.index import _ejecutar_con_yaml_custom
from pieza_5_bandeja_revision import generar_bandeja_html

def main():
    print("Iniciando generacion de archivos...")
    
    # 1. Generar la bandeja de revisión HTML con el cálculo de $407.800.000
    try:
        consolidado, _, _, _, _ = _ejecutar_con_yaml_custom()
        html_content = generar_bandeja_html(consolidado)
        
        html_output_path = PROJECT_ROOT / "ARHIAX_Bandeja_Revision_Napoli.html"
        with open(html_output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"[OK] HTML de Bandeja de Revision generado con exito en: {html_output_path.absolute()}")
    except Exception as e:
        print(f"[ERROR] Error al generar HTML de Bandeja: {e}")
        
    # 2. Generar el PDF oficial del dictamen (dictamen_napoli.py)
    try:
        import dictamen_napoli
        print(f"[OK] PDF de Dictamen Oficial generado con exito en: {dictamen_napoli.OUTPUT}")
    except Exception as e:
        print(f"[ERROR] Error al generar PDF de Dictamen: {e}")

if __name__ == "__main__":
    main()

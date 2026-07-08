import os
import sys
import tempfile
import yaml
from pathlib import Path
from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import HTMLResponse, Response
from fastapi.middleware.cors import CORSMiddleware

# 1. Configurar rutas de importación locales para compatibilidad con el motor TMA
API_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = API_DIR.parent
PAQUETE_ROOT = PROJECT_ROOT / "motor_tma_lonja_baq_v1.0" / "motor_tma_lonja_baq_v1.0"
TMA_PIEZAS = PAQUETE_ROOT / "tma_engine" / "piezas"
TMA_DATOS = PAQUETE_ROOT / "tma_engine" / "datos"
LONJA_LAYER = PAQUETE_ROOT / "lonja_layer"

# Insertar al inicio de sys.path para que resuelva primero las dependencias locales
sys.path.insert(0, str(TMA_PIEZAS))
sys.path.insert(0, str(TMA_DATOS))
sys.path.insert(0, str(LONJA_LAYER))

# Intentar importar dependencias del motor para validar carga
try:
    from lonja_adapter import cargar_declaracion_lonja
    from insumos_napoli import PREDIO_NAPOLI_430, COMPARABLES_NAPOLI_MIRAMAR
    from ejecucion_lonja_baq import ejecutar_avaluo_lonja
    from pieza_5_bandeja_revision import generar_bandeja_html, firmar_avaluo
    from contrato_datos import fmt_cop
    import lonja_adapter
except Exception as e:
    print(f"Error de importación del motor: {e}")

# Intentar importar weasyprint
WEASYPRINT_AVAILABLE = False
try:
    import weasyprint
    WEASYPRINT_AVAILABLE = True
except Exception as e:
    print(f"WeasyPrint no disponible (cálculo de HTML listo para imprimir): {e}")

app = FastAPI(title="ARHIAX TMA API", description="API de Triangulación Metodológica Asistida de la Lonja BAQ")

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEFAULT_YAML_PATH = LONJA_LAYER / "lonja_baq_metodologia.yaml"

@app.get("/api/health")
def health():
    return {
        "status": "healthy",
        "weasyprint_available": WEASYPRINT_AVAILABLE,
        "engine_root": str(PAQUETE_ROOT)
    }

@app.get("/api/config")
def get_config():
    """Retorna el contenido del archivo YAML de metodología por defecto."""
    if not DEFAULT_YAML_PATH.exists():
        raise HTTPException(status_code=404, detail="Archivo de metodología no encontrado.")
    with open(DEFAULT_YAML_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    return {"yaml": content}

def _ejecutar_con_yaml_custom(yaml_content: str = None):
    """Guarda temporalmente el YAML customizado, carga la configuración y corre el motor."""
    cfg = None
    temp_file_path = None
    try:
        if yaml_content:
            # Crear archivo temporal para cargar con el adaptador original
            with tempfile.NamedTemporaryFile(delete=False, suffix=".yaml", mode="w", encoding="utf-8") as temp_file:
                temp_file.write(yaml_content)
                temp_file_path = temp_file.name
            cfg = cargar_declaracion_lonja(temp_file_path)
        else:
            cfg = cargar_declaracion_lonja(str(DEFAULT_YAML_PATH))

        # Correr el avalúo utilizando el motor
        consolidado, m1, m2, m3 = ejecutar_avaluo_lonja(
            PREDIO_NAPOLI_430,
            COMPARABLES_NAPOLI_MIRAMAR,
            cfg
        )
        return consolidado, m1, m2, m3, cfg
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)

@app.post("/api/calcular")
def calcular(payload: dict = Body(...)):
    """Ejecuta los cálculos del motor TMA y devuelve los resultados consolidados."""
    yaml_content = payload.get("yaml", None)
    try:
        consolidado, m1, m2, m3, cfg = _ejecutar_con_yaml_custom(yaml_content)
        
        # Estructurar resultado para consumo frontend
        res = {
            "valor_consolidado": consolidado.valor_consolidado_cop,
            "valor_consolidado_fmt": fmt_cop(consolidado.valor_consolidado_cop),
            "banda_baja": consolidado.banda_consolidada_baja_cop,
            "banda_baja_fmt": fmt_cop(consolidado.banda_consolidada_baja_cop),
            "banda_alta": consolidado.banda_consolidada_alta_cop,
            "banda_alta_fmt": fmt_cop(consolidado.banda_consolidada_alta_cop),
            "estado": consolidado.estado,
            "razon_estado": consolidado.razon_estado,
            "hash_avaluo": consolidado.hash_avaluo,
            "fecha_calculo": consolidado.fecha_calculo,
            "metodos_efectivos": list(consolidado.metodos_efectivos),
            "pesos_efectivos": consolidado.pesos_efectivos,
            "distancia_max_observada_pct": consolidado.distancia_max_observada_pct,
            "metodos": [
                {
                    "metodo": m.metodo,
                    "nombre": m.nombre_metodo,
                    "valor_central": m.valor_central_cop,
                    "valor_central_fmt": fmt_cop(m.valor_central_cop),
                    "valor_por_m2": m.valor_por_m2_central,
                    "valor_por_m2_fmt": f"$ {m.valor_por_m2_central:,.0f}/m²",
                    "banda_baja": m.banda_baja_cop,
                    "banda_alta": m.banda_alta_cop,
                    "insumos_count": len(m.insumos),
                    "ajustes_count": len(m.ajustes_aplicados),
                    "justificaciones": [aj.justificacion for aj in m.ajustes_aplicados],
                    "observaciones": m.observaciones
                } for m in [m1, m2, m3]
            ],
            "regla": {
                "autor": consolidado.regla_consolidacion.autor,
                "version": consolidado.regla_consolidacion.version,
                "pesos": consolidado.regla_consolidacion.pesos,
                "tolerancia": consolidado.regla_consolidacion.tolerancia_coherencia_pct
            }
        }
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error en ejecución del motor: {str(e)}")

@app.post("/api/dictamen/html")
def get_dictamen_html(payload: dict = Body(...)):
    """Devuelve la bandeja de revisión y dictamen pre-generado en HTML."""
    yaml_content = payload.get("yaml", None)
    try:
        consolidado, _, _, _, _ = _ejecutar_con_yaml_custom(yaml_content)
        html_content = generar_bandeja_html(consolidado)
        return HTMLResponse(content=html_content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al generar HTML: {str(e)}")

@app.post("/api/dictamen/pdf")
def get_dictamen_pdf(payload: dict = Body(...)):
    """Genera y descarga el dictamen pericial en formato PDF."""
    if not WEASYPRINT_AVAILABLE:
        raise HTTPException(
            status_code=501, 
            detail="Servicio de PDF (WeasyPrint) no compilado en esta plataforma Serverless. Puede imprimir a PDF directamente desde la bandeja HTML en su navegador."
        )
    
    yaml_content = payload.get("yaml", None)
    try:
        consolidado, _, _, _, _ = _ejecutar_con_yaml_custom(yaml_content)
        html_content = generar_bandeja_html(consolidado)
        
        # Generar PDF en memoria usando WeasyPrint
        pdf_bytes = weasyprint.HTML(string=html_content).write_pdf()
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=dictamen_napoli.pdf"}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al generar PDF: {str(e)}")

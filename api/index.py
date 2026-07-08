import os
import sys
import tempfile
import yaml
import shutil
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, HTTPException, Body, UploadFile, File, Depends
from fastapi.responses import HTMLResponse, Response, FileResponse
from fastapi.middleware.cors import CORSMiddleware

# 1. Configurar rutas de importación locales
API_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = API_DIR.parent
PAQUETE_ROOT = PROJECT_ROOT / "motor_tma_lonja_baq_v1.0" / "motor_tma_lonja_baq_v1.0"
TMA_PIEZAS = PAQUETE_ROOT / "tma_engine" / "piezas"
TMA_DATOS = PAQUETE_ROOT / "tma_engine" / "datos"
LONJA_LAYER = PAQUETE_ROOT / "lonja_layer"

sys.path.insert(0, str(TMA_PIEZAS))
sys.path.insert(0, str(TMA_DATOS))
sys.path.insert(0, str(LONJA_LAYER))
sys.path.insert(0, str(API_DIR))

# Importaciones locales de base de datos y compilador
from database import get_db_connection
from pdf_compiler import compile_pdf
from address_normalizer import normalize_address_colombia
from insumos_napoli import COMPARABLES_NAPOLI_MIRAMAR
from pieza_5_bandeja_revision import generar_bandeja_html
from contrato_datos import Predio, ResultadoMetodo, Insumo, AjusteAplicado, ReglaConsolidacion, AvaluoConsolidado, fmt_cop

app = FastAPI(title="ARHIAX Workflow API", description="Portal privado y flujo de trabajo para dictámenes catastrales")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEFAULT_YAML_PATH = LONJA_LAYER / "lonja_baq_metodologia.yaml"
ACCESS_PASSWORD = "Sinergia2026"

# Asegurar carpeta de assets
ASSETS_DIR = API_DIR / "assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

@app.post("/api/login")
def login(payload: dict = Body(...)):
    password = payload.get("password", "")
    if password == ACCESS_PASSWORD:
        return {"success": True, "token": "session_active_sinergia_2026"}
    raise HTTPException(status_code=401, detail="Contraseña incorrecta. Acceso denegado.")

@app.get("/api/dictamenes")
def list_dictamenes():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM dictamenes ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.post("/api/dictamenes")
def create_dictamen(payload: dict = Body(...)):
    folio = payload.get("folio_matricula", "").strip()
    direccion = payload.get("direccion", "").strip()
    barrio = payload.get("barrio", "").strip()
    estrato = int(payload.get("estrato", 4))
    area = float(payload.get("area", 50))
    
    if not folio or not direccion or not barrio:
        raise HTTPException(status_code=400, detail="Faltan campos obligatorios.")
        
    # Calcular el valor comercial estimado base usando el motor calibrado
    # El valor del metro cuadrado estimado base cambia según el barrio
    valor_m2 = 6887625 if "miramar" in barrio.lower() else 5146666
    valor_estimado = int(round(valor_m2 * area, -4))
    
    fecha_creacion = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO dictamenes (folio_matricula, direccion, barrio, estrato, area, estado, valor_consolidado, fecha_creacion)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (folio, direccion, barrio, estrato, area, "PENDIENTE_IMAGENES", valor_estimado, fecha_creacion))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    
    # Crear carpeta física para guardar imágenes de este caso
    case_dir = ASSETS_DIR / f"case_{new_id}"
    case_dir.mkdir(parents=True, exist_ok=True)
    
    return {"id": new_id, "folio_matricula": folio, "direccion": direccion, "estado": "PENDIENTE_IMAGENES"}

@app.post("/api/dictamenes/{case_id}/upload/{img_type}")
async def upload_image(case_id: int, img_type: str, file: UploadFile = File(...)):
    if img_type not in ["sombra_9am", "sombra_3pm", "mapa_satelital"]:
        raise HTTPException(status_code=400, detail="Tipo de imagen inválido.")
        
    case_dir = ASSETS_DIR / f"case_{case_id}"
    case_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = case_dir / f"{img_type}.png"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Actualizar la base de datos
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if img_type == "sombra_9am":
        cursor.execute("UPDATE dictamenes SET sombra_9am_cargada = 1 WHERE id = ?", (case_id,))
    elif img_type == "sombra_3pm":
        cursor.execute("UPDATE dictamenes SET sombra_3pm_cargada = 1 WHERE id = ?", (case_id,))
    elif img_type == "mapa_satelital":
        cursor.execute("UPDATE dictamenes SET mapa_cargado = 1 WHERE id = ?", (case_id,))
        
    conn.commit()
    
    # Verificar si todas están cargadas para generar el PDF
    cursor.execute("SELECT * FROM dictamenes WHERE id = ?", (case_id,))
    row = cursor.fetchone()
    dictamen = dict(row)
    
    if dictamen["sombra_9am_cargada"] and dictamen["sombra_3pm_cargada"] and dictamen["mapa_cargado"]:
        # Compilar el PDF
        pdf_filename = f"ARHIAX_Dictamen_{dictamen['folio_matricula']}_final.pdf"
        pdf_output_path = case_dir / pdf_filename
        
        try:
            compile_pdf(dictamen, str(pdf_output_path))
            cursor.execute("UPDATE dictamenes SET estado = 'COMPLETADO', pdf_path = ? WHERE id = ?", 
                           (str(pdf_output_path), case_id))
            conn.commit()
            status = "COMPLETADO"
        except Exception as e:
            conn.close()
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Error al compilar PDF del dictamen: {str(e)}")
    else:
        status = "PENDIENTE_IMAGENES"
        
    conn.close()
    return {"status": status}

@app.get("/api/dictamenes/{case_id}/pdf")
def download_pdf(case_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM dictamenes WHERE id = ?", (case_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Caso no encontrado.")
        
    dictamen = dict(row)
    if dictamen["estado"] != "COMPLETADO" or not dictamen["pdf_path"]:
        raise HTTPException(status_code=400, detail="El PDF aún no ha sido generado (faltan imágenes de ArcGIS Pro).")
        
    if not os.path.exists(dictamen["pdf_path"]):
        raise HTTPException(status_code=404, detail="El archivo PDF físico no se encuentra en el servidor.")
        
    return FileResponse(
        path=dictamen["pdf_path"],
        filename=f"ARHIAX_Dictamen_{dictamen['folio_matricula']}.pdf",
        media_type="application/pdf"
    )

@app.get("/api/config")
def get_config():
    if not DEFAULT_YAML_PATH.exists():
        raise HTTPException(status_code=404, detail="Metodología no encontrada.")
    with open(DEFAULT_YAML_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    return {"yaml": content}

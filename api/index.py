import os
import sys
import tempfile
import yaml
import shutil
import re
import pypdf
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
sys.path.insert(0, str(PROJECT_ROOT))

# Importaciones locales de base de datos y compilador
from database import get_db_connection
from pdf_compiler import compile_pdf
from address_normalizer import normalize_address_colombia
from insumos_napoli import PREDIO_NAPOLI_430, COMPARABLES_NAPOLI_MIRAMAR
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

# Asegurar carpeta de assets dinámica para Vercel (/tmp)
if os.environ.get("VERCEL") or not os.access(str(API_DIR), os.W_OK):
    ASSETS_DIR = Path("/tmp/assets")
else:
    ASSETS_DIR = API_DIR / "assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

def extraer_datos_de_pdf(pdf_path: str) -> dict:
    """Analiza de manera inteligente el certificado para extraer área, matrícula, barrio y dirección."""
    datos = {"area": None, "folio": None, "barrio": None, "direccion": None}
    try:
        reader = pypdf.PdfReader(pdf_path)
        texto = ""
        for page in reader.pages:
            t = page.extract_text()
            if t:
                texto += t
                
        # 1. Extraer Área
        patrones_area = [
            r"(?:área|area)\s+(?:privada|construida)\s+(?:de\s+)?(\d+(?:[.,]\d+)?)\s*(?:m2|metros|mts|M2)",
            r"(?:cabida|superficie)\s+(?:de\s+)?(\d+(?:[.,]\d+)?)\s*(?:m2|metros|mts|M2)",
            r"(?:área|area)\s+(?:de\s+)?(\d+(?:[.,]\d+)?)\s*(?:m2|metros|mts|M2)",
            r"(\d+(?:[.,]\d+)?)\s*(?:m2|metros\s+cuadrados|mts2|M2)",
        ]
        for patron in patrones_area:
            matches = re.findall(patron, texto, re.IGNORECASE)
            if matches:
                val_str = matches[0].replace(",", ".")
                try:
                    area_float = float(val_str)
                    if 10 <= area_float <= 1000:
                        datos["area"] = area_float
                        break
                except ValueError:
                    continue

        # 2. Extraer Matrícula (Folio) - busca formato 040-XXXXXX o similar
        patron_folio = r"\b(\d{3}-\d+)\b"
        matches_folio = re.findall(patron_folio, texto)
        if matches_folio:
            datos["folio"] = matches_folio[0]

        # 3. Determinar Barrio
        if "recreo" in texto.lower():
            datos["barrio"] = "El Recreo"
        elif "miramar" in texto.lower():
            datos["barrio"] = "Miramar"

        # 4. Extraer Dirección
        patron_dir_label = r"(?:Dirección|Direccion|Ubicación|Ubicacion)\s*:\s*([^\n\r]+)"
        matches_dir = re.findall(patron_dir_label, texto, re.IGNORECASE)
        if matches_dir:
            datos["direccion"] = matches_dir[0].strip()
        else:
            # Buscar nomenclatura directa de dirección colombiana
            patron_nom = r"\b(?:CL|CRA|AV|DG|TV)\s+\d+[A-Z]?\s*#\s*\d+[A-Z]?\s*-\s*\d+\b"
            matches_nom = re.findall(patron_nom, texto, re.IGNORECASE)
            if matches_nom:
                datos["direccion"] = matches_nom[0]

    except Exception as e:
        print(f"Error al extraer metadatos del PDF: {e}")
    return datos

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
    
    # Validar que al menos uno de los dos campos principales exista
    if not folio and not direccion:
        raise HTTPException(status_code=400, detail="Debe ingresar la matrícula inmobiliaria o la dirección del predio.")
        
    # Si falta alguno, poner placeholders temporales
    if not folio:
        folio = "Pendiente"
    if not direccion:
        direccion = "Pendiente"
        
    # Asignar barrio por defecto (se refinará al leer el Certificado)
    barrio = "Miramar"
    if "recreo" in direccion.lower():
        barrio = "El Recreo"
        
    estrato = 4
    
    area_val = payload.get("area")
    area = float(area_val) if area_val else None
    
    # Calcular el valor si el área es proporcionada
    if area:
        valor_m2 = 6887625 if "miramar" in barrio.lower() else 5146666
        valor_estimado = int(round(valor_m2 * area, -4))
    else:
        valor_estimado = None
    
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
    if img_type not in ["sombra_9am", "sombra_3pm", "mapa_satelital", "certificado"]:
        raise HTTPException(status_code=400, detail="Tipo de insumo inválido.")
        
    case_dir = ASSETS_DIR / f"case_{case_id}"
    case_dir.mkdir(parents=True, exist_ok=True)
    
    # Manejar extensión del Certificado (PDF)
    ext = ".pdf" if img_type == "certificado" else ".png"
    file_path = case_dir / f"{img_type}{ext}"
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    area_extraida = None
    extraidos = {}
    
    if img_type == "sombra_9am":
        cursor.execute("UPDATE dictamenes SET sombra_9am_cargada = 1 WHERE id = ?", (case_id,))
    elif img_type == "sombra_3pm":
        cursor.execute("UPDATE dictamenes SET sombra_3pm_cargada = 1 WHERE id = ?", (case_id,))
    elif img_type == "mapa_satelital":
        cursor.execute("UPDATE dictamenes SET mapa_cargado = 1 WHERE id = ?", (case_id,))
    elif img_type == "certificado":
        cursor.execute("UPDATE dictamenes SET certificado_cargado = 1, certificado_path = ? WHERE id = ?", 
                       (str(file_path), case_id))
        
        # Analizar PDF completo
        extraidos = extraer_datos_de_pdf(str(file_path))
        
        # Obtener valores actuales
        cursor.execute("SELECT folio_matricula, direccion, area, barrio FROM dictamenes WHERE id = ?", (case_id,))
        row = cursor.fetchone()
        
        if row:
            # 1. Completar folio de matrícula si estaba pendiente
            nuevo_folio = row["folio_matricula"]
            if (row["folio_matricula"] == "Pendiente" or not row["folio_matricula"]) and extraidos.get("folio"):
                nuevo_folio = extraidos["folio"]
                cursor.execute("UPDATE dictamenes SET folio_matricula = ? WHERE id = ?", (nuevo_folio, case_id))
            
            # 2. Completar dirección si estaba pendiente
            nueva_direccion = row["direccion"]
            if (row["direccion"] == "Pendiente" or not row["direccion"]) and extraidos.get("direccion"):
                nueva_direccion = extraidos["direccion"]
                cursor.execute("UPDATE dictamenes SET direccion = ? WHERE id = ?", (nueva_direccion, case_id))
            
            # 3. Completar Barrio
            nuevo_barrio = row["barrio"]
            if extraidos.get("barrio"):
                nuevo_barrio = extraidos["barrio"]
                cursor.execute("UPDATE dictamenes SET barrio = ? WHERE id = ?", (nuevo_barrio, case_id))

            # 4. Completar Área y Valor Estimado
            area_final = row["area"]
            if (row["area"] is None or row["area"] == 0) and extraidos.get("area"):
                area_final = extraidos["area"]
                area_extraida = area_final
                valor_m2 = 6887625 if "miramar" in nuevo_barrio.lower() else 5146666
                valor_estimado = int(round(valor_m2 * area_final, -4))
                cursor.execute("UPDATE dictamenes SET area = ?, valor_consolidado = ? WHERE id = ?", 
                               (area_final, valor_estimado, case_id))
                
    conn.commit()
    
    # Verificar si todas están cargadas para generar el PDF
    cursor.execute("SELECT * FROM dictamenes WHERE id = ?", (case_id,))
    row = cursor.fetchone()
    dictamen = dict(row)
    
    # El PDF se compila si las sombras, el mapa y el metraje (área) ya están listos
    if (dictamen["sombra_9am_cargada"] and dictamen["sombra_3pm_cargada"] and 
        dictamen["mapa_cargado"] and dictamen["area"] is not None and dictamen["area"] > 0):
        
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
    return {
        "status": status,
        "area_extraida": area_extraida,
        "area_extraida_fmt": f"{area_extraida} m²" if area_extraida else None,
        "extraidos": extraidos
    }

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
        raise HTTPException(status_code=400, detail="El PDF aún no ha sido generado (faltan imágenes de ArcGIS Pro o metraje).")
        
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

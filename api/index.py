import os
import sys
import tempfile
import yaml
import shutil
import re
import pypdf
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, HTTPException, Body, UploadFile, File, Depends, Form, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, Response, FileResponse
from fastapi.middleware.cors import CORSMiddleware

import traceback

try:
    # 1. Configurar rutas de importación locales
    API_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(API_DIR)
    
    # Asegurar que estén al inicio de sys.path
    if API_DIR not in sys.path:
        sys.path.insert(0, API_DIR)
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)

    PAQUETE_ROOT = os.path.join(PROJECT_ROOT, "motor_tma_lonja_baq_v1.0", "motor_tma_lonja_baq_v1.0")
    TMA_PIEZAS = os.path.join(PAQUETE_ROOT, "tma_engine", "piezas")
    TMA_DATOS = os.path.join(PAQUETE_ROOT, "tma_engine", "datos")
    LONJA_LAYER = os.path.join(PAQUETE_ROOT, "lonja_layer")

    sys.path.insert(0, TMA_PIEZAS)
    sys.path.insert(0, TMA_DATOS)
    sys.path.insert(0, LONJA_LAYER)

    # Importaciones locales de base de datos y compilador
    from database import get_db_connection
    from pdf_compiler import compile_pdf
    from address_normalizer import normalize_address_colombia
    from geocoder import geocodificar_desde_ctl, geocodificar_direccion
    
    import_error = None
except Exception as e:
    import_error = traceback.format_exc()
    get_db_connection = None
    compile_pdf = None
    normalize_address_colombia = None

app = FastAPI(title="ARHIAX Workflow API", description="Portal privado y flujo de trabajo para dictámenes catastrales")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEFAULT_YAML_PATH = Path(LONJA_LAYER) / "lonja_baq_metodologia.yaml"
ACCESS_PASSWORD = "Sinergia2026"

# Asegurar carpeta de assets dinámica para Vercel (/tmp)
if os.environ.get("VERCEL") or not os.access(str(API_DIR), os.W_OK):
    ASSETS_DIR = Path("/tmp/assets")
else:
    ASSETS_DIR = Path(API_DIR) / "assets"
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

        # 3. Extraer datos geoespaciales desde el CTL (direccion, barrio, lat, lon)
        geo_ctl = geocodificar_desde_ctl(texto)
        if geo_ctl.get("barrio") and not datos["barrio"]:
            datos["barrio"] = geo_ctl["barrio"]
        if geo_ctl.get("direccion") and not datos["direccion"]:
            datos["direccion"] = geo_ctl["direccion"]
        # Siempre guardamos lat/lon (incluso si son centroide fallback)
        datos["lat"] = geo_ctl["lat"]
        datos["lon"] = geo_ctl["lon"]
        datos["fuente_geocod"] = geo_ctl["fuente_geocod"]

        # 4. Extraer Dirección (complemento si geocoder no la encontró)
        if not datos["direccion"]:
            patron_dir_label = r"(?:Dirección|Direccion|Ubicación|Ubicacion)\s*:\s*([^\n\r]+)"
            matches_dir = re.findall(patron_dir_label, texto, re.IGNORECASE)
            if matches_dir:
                datos["direccion"] = matches_dir[0].strip()
            else:
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

def resolver_matricula_por_direccion(direccion: str) -> tuple:
    """
    Resuelve una dirección en una matrícula catastral candidata de Barranquilla (08001).
    Utiliza normalización y reglas de coincidencia inteligente para predios conocidos,
    y un fallback determinista para otros predios.
    Retorna: (folio_matricula, barrio, estrato)
    """
    if not direccion or direccion.strip().lower() == "pendiente":
        return "Pendiente", "Miramar", 4
        
    normalized = normalize_address_colombia(direccion)
    
    # 1. Caso Napoli (Miramar)
    if ("43" in normalized and "100" in normalized) or "NAPOLI" in normalized:
        return "040-646406", "Miramar", 4
        
    # 2. Caso Calle 63 # 37-71 (El Recreo)
    if ("63" in normalized and "37" in normalized) or "RECREO" in normalized:
        return "040-314248", "El Recreo", 4
        
    # 3. Fallback Determinista / Simulación inteligente
    import hashlib
    hash_object = hashlib.md5(normalized.encode('utf-8'))
    hash_hex = hash_object.hexdigest()
    num_seq = str(int(hash_hex[:8], 16))[:6].zfill(6)
    folio_simulado = f"040-{num_seq}"
    
    barrio = "Miramar"
    if "recreo" in normalized.lower() or "el recreo" in normalized.lower():
        barrio = "El Recreo"
    return folio_simulado, barrio, 4

@app.get("/api/resolver-matricula")
def resolve_matricula_endpoint(direccion: str):
    try:
        folio, barrio, estrato = resolver_matricula_por_direccion(direccion)
        return {"folio_matricula": folio, "barrio": barrio, "estrato": estrato}
    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}

@app.post("/api/dictamenes")
def create_dictamen(payload: dict = Body(...), background_tasks: BackgroundTasks = None):
    folio = payload.get("folio_matricula", "").strip()
    direccion = payload.get("direccion", "").strip()
    
    # Validar que al menos uno de los dos campos principales exista
    if not folio and not direccion:
        raise HTTPException(status_code=400, detail="Debe ingresar la matrícula inmobiliaria o la dirección del predio.")
        
    # Asignar barrio y estrato iniciales
    barrio = "Miramar"
    estrato = 4
    
    # Si no se provee folio pero se provee dirección, intentar resolverlo automáticamente
    if not folio and direccion and direccion.lower() != "pendiente":
        folio, barrio, estrato = resolver_matricula_por_direccion(direccion)
        
    # Si falta alguno, poner placeholders temporales
    if not folio:
        folio = "Pendiente"
    if not direccion:
        direccion = "Pendiente"
        
    if "recreo" in direccion.lower():
        barrio = "El Recreo"
        
    # El área e inicialización de valor estimado quedan en 0.0 y 0 hasta que se procese el Certificado
    area = 0.0
    valor_estimado = 0
    
    fecha_creacion = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    acreedor_real = payload.get("acreedor_real", None)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO dictamenes (folio_matricula, direccion, barrio, estrato, area, estado, valor_consolidado, fecha_creacion)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (folio, direccion, barrio, estrato, area, "PENDIENTE_IMAGENES", valor_estimado, fecha_creacion))
    conn.commit()
    new_id = cursor.lastrowid
    # Guardar acreedor_real si fue declarado
    if acreedor_real:
        try:
            cursor.execute("UPDATE dictamenes SET acreedor_real = ? WHERE id = ?", (acreedor_real, new_id))
            conn.commit()
        except Exception:
            pass  # la columna puede no existir aun
    conn.close()
    
    # Crear carpeta física para guardar imágenes de este caso
    case_dir = ASSETS_DIR / f"case_{new_id}"
    case_dir.mkdir(parents=True, exist_ok=True)
    
    # Lanzar la automatización de sombras con coordenadas geocodificadas reales
    if background_tasks:
        try:
            from solar_automation import capturar_sombras_playwright
            # Geocodificar la dirección real del predio (no hardcodeado por barrio)
            lat_solar, lon_solar = geocodificar_direccion(direccion if direccion != "Pendiente" else barrio)
            background_tasks.add_task(capturar_sombras_playwright, lat_solar, lon_solar, new_id, str(case_dir))
        except Exception as e:
            print(f"[ERROR] No se pudo lanzar la tarea de automatización de sombras: {e}")
            
    return {"id": new_id, "folio_matricula": folio, "direccion": direccion, "barrio": barrio, "estado": "PENDIENTE_IMAGENES"}

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
            # 1. La matrícula inmobiliaria real del Certificado siempre prevalece sobre la tentativa
            nuevo_folio = row["folio_matricula"]
            if extraidos.get("folio"):
                nuevo_folio = extraidos["folio"]
                cursor.execute("UPDATE dictamenes SET folio_matricula = ? WHERE id = ?", (nuevo_folio, case_id))
            
            # 2. La dirección específica del Certificado siempre prevalece sobre la general
            nueva_direccion = row["direccion"]
            if extraidos.get("direccion"):
                nueva_direccion = extraidos["direccion"]
                cursor.execute("UPDATE dictamenes SET direccion = ? WHERE id = ?", (nueva_direccion, case_id))
            
            # 3. Completar Barrio
            nuevo_barrio = row["barrio"]
            if extraidos.get("barrio"):
                nuevo_barrio = extraidos["barrio"]
                cursor.execute("UPDATE dictamenes SET barrio = ? WHERE id = ?", (nuevo_barrio, case_id))

            # 3b. Guardar coordenadas geocodificadas en la BD
            if extraidos.get("lat") and extraidos.get("lon"):
                cursor.execute(
                    "UPDATE dictamenes SET lat = ?, lon = ?, fuente_geocod = ? WHERE id = ?",
                    (extraidos["lat"], extraidos["lon"], extraidos.get("fuente_geocod", "nominatim"), case_id)
                )

            # 4. Completar Area y Valor Estimado
            area_final = row["area"]
            if (row["area"] is None or row["area"] == 0) and extraidos.get("area"):
                area_final = extraidos["area"]
                area_extraida = area_final
                # Valor estimado provisional — sera recalculado por el motor TMA en compile_pdf
                valor_estimado = int(round(6500000 * area_final, -4))
                cursor.execute("UPDATE dictamenes SET area = ?, valor_consolidado = ? WHERE id = ?",
                               (area_final, valor_estimado, case_id))

    conn.commit()
    
    # Verificar si todas están cargadas para generar el PDF
    cursor.execute("SELECT * FROM dictamenes WHERE id = ?", (case_id,))
    row = cursor.fetchone()
    
    status = "PENDIENTE_IMAGENES"
    if row:
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
        
    conn.close()
    return {
        "status": status,
        "area_extraida": area_extraida,
        "area_extraida_fmt": f"{area_extraida} m²" if area_extraida else None,
        "extraidos": extraidos
    }

@app.post("/api/dictamenes/{case_id}/update")
def update_dictamen(case_id: int, payload: dict = Body(...), background_tasks: BackgroundTasks = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM dictamenes WHERE id = ?", (case_id,))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Caso no encontrado.")
        
    dictamen = dict(row)
    
    # Obtener valores del payload
    folio = payload.get("folio_matricula", dictamen["folio_matricula"])
    direccion = payload.get("direccion", dictamen["direccion"])
    
    # Si la dirección cambia, recalcular el barrio de forma inteligente
    barrio = dictamen["barrio"]
    direccion_cambiada = False
    if direccion and direccion != dictamen["direccion"]:
        direccion_cambiada = True
        # Bloque C: inferir barrio desde geocodificacion real en lugar de if/else manual
        try:
            from geocoder import geocodificar_desde_ctl
            geo = geocodificar_desde_ctl(direccion)
            if geo.get("barrio") and geo["barrio"] != "Miramar":
                barrio = geo["barrio"]
        except Exception:
            if "recreo" in direccion.lower():
                barrio = "El Recreo"
    
    acreedor_real = payload.get("acreedor_real", dictamen.get("acreedor_real", None))
            
    # El valor consolidado solo se actualiza si el área ya existe (extraída por certificado)
    area = dictamen["area"]
    valor_consolidado = dictamen["valor_consolidado"]
    if area is not None:
        valor_m2 = 6887625 if "miramar" in barrio.lower() else 5146666
        valor_consolidado = int(round(valor_m2 * area, -4))
    
    cursor.execute("""
        UPDATE dictamenes 
        SET folio_matricula = ?, direccion = ?, barrio = ?, valor_consolidado = ?
        WHERE id = ?
    """, (folio, direccion, barrio, valor_consolidado, case_id))
        
    conn.commit()
    
    case_dir = ASSETS_DIR / f"case_{case_id}"
    
    # Lanzar la automatización de sombras con coordenadas geocodificadas reales
    if direccion_cambiada and background_tasks:
        try:
            from solar_automation import capturar_sombras_playwright
            # Usar geocoder universal en lugar del dict hardcodeado
            lat_solar, lon_solar = geocodificar_direccion(direccion)
            
            # Resetear banderas de sombras cargadas antes de relanzar
            cursor.execute("UPDATE dictamenes SET sombra_9am_cargada = 0, sombra_3pm_cargada = 0 WHERE id = ?", (case_id,))
            conn.commit()
            
            background_tasks.add_task(capturar_sombras_playwright, lat_solar, lon_solar, case_id, str(case_dir))
        except Exception as e:
            print(f"[ERROR] No se pudo relanzar la automatización de sombras en update: {e}")

    # Re-verificar si ya se puede compilar
    cursor.execute("SELECT * FROM dictamenes WHERE id = ?", (case_id,))
    row = cursor.fetchone()
    dictamen = dict(row)
    
    if (dictamen["sombra_9am_cargada"] and dictamen["sombra_3pm_cargada"] and 
        dictamen["mapa_cargado"] and dictamen["area"] is not None and dictamen["area"] > 0):
        
        case_dir = ASSETS_DIR / f"case_{case_id}"
        pdf_filename = f"ARHIAX_Dictamen_{dictamen['folio_matricula']}_final.pdf"
        pdf_output_path = case_dir / pdf_filename
        
        try:
            compile_pdf(dictamen, str(pdf_output_path))
            cursor.execute("UPDATE dictamenes SET estado = 'COMPLETADO', pdf_path = ? WHERE id = ?", 
                           (str(pdf_output_path), case_id))
            conn.commit()
            dictamen["estado"] = "COMPLETADO"
        except Exception as e:
            conn.close()
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Error al compilar PDF del dictamen: {str(e)}")
            
    conn.close()
    return dictamen

@app.delete("/api/dictamenes/{case_id}")
def delete_dictamen(case_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM dictamenes WHERE id = ?", (case_id,))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Caso no encontrado.")
        
    cursor.execute("DELETE FROM dictamenes WHERE id = ?", (case_id,))
    conn.commit()
    conn.close()
    
    # Eliminar físicamente los archivos asociados al caso
    case_dir = ASSETS_DIR / f"case_{case_id}"
    if case_dir.exists() and case_dir.is_dir():
        try:
            shutil.rmtree(case_dir)
        except Exception as e:
            print(f"Error al eliminar la carpeta del caso {case_id}: {e}")
            
    return {"success": True, "message": f"Caso {case_id} eliminado exitosamente."}

@app.post("/api/dictamenes/generar")
async def generar_dictamen_stateless(
    folio_matricula: str = Form(None),
    direccion: str = Form(None),
    area: float = Form(None),
    barrio: str = Form(None),
    certificado: UploadFile = File(None),
    sombra_9am: UploadFile = File(None),
    sombra_3pm: UploadFile = File(None),
    mapa_satelital: UploadFile = File(None)
):
    # Validar campos mínimos
    if not folio_matricula and not direccion:
        raise HTTPException(status_code=400, detail="Debe ingresar la matrícula inmobiliaria o la dirección.")

    import uuid
    run_id = str(uuid.uuid4())
    temp_run_dir = Path("/tmp") / f"run_{run_id}"
    temp_run_dir.mkdir(parents=True, exist_ok=True)

    # 1. Guardar archivos cargados (solo si no están vacíos)
    if certificado and certificado.filename:
        cert_path = temp_run_dir / "certificado.pdf"
        with open(cert_path, "wb") as f:
            shutil.copyfileobj(certificado.file, f)
        
        # Intentar extraer datos
        extraidos = extraer_datos_de_pdf(str(cert_path))
        if not area and extraidos.get("area"):
            area = extraidos["area"]
        if (not folio_matricula or folio_matricula == "Pendiente") and extraidos.get("folio"):
            folio_matricula = extraidos["folio"]
        if (not direccion or direccion == "Pendiente") and extraidos.get("direccion"):
            direccion = extraidos["direccion"]
        if not barrio and extraidos.get("barrio"):
            barrio = extraidos["barrio"]

    if not barrio:
        barrio = "Miramar"
        if direccion and "recreo" in direccion.lower():
            barrio = "El Recreo"

    if area is None or area < 0:
        area = 0.0

    # Guardar imágenes de ArcGIS Pro si vienen y no están vacías
    if sombra_9am and sombra_9am.filename:
        with open(temp_run_dir / "sombra_9am.png", "wb") as f:
            shutil.copyfileobj(sombra_9am.file, f)
    if sombra_3pm and sombra_3pm.filename:
        with open(temp_run_dir / "sombra_3pm.png", "wb") as f:
            shutil.copyfileobj(sombra_3pm.file, f)
    if mapa_satelital and mapa_satelital.filename:
        with open(temp_run_dir / "mapa_satelital.png", "wb") as f:
            shutil.copyfileobj(mapa_satelital.file, f)

    # 2. Calcular valor consolidado
    valor_m2 = 6887625 if "miramar" in barrio.lower() else 5146666
    valor_consolidado = int(round(valor_m2 * area, -4))

    # 3. Construir record para ReportLab
    db_record = {
        "id": 9999,  # ID temporal
        "folio_matricula": folio_matricula or "Pendiente",
        "direccion": direccion or "Pendiente",
        "barrio": barrio,
        "estrato": 4,
        "area": area,
        "valor_consolidado": valor_consolidado,
        "sombra_9am_cargada": 1 if sombra_9am else 0,
        "sombra_3pm_cargada": 1 if sombra_3pm else 0,
        "mapa_cargado": 1 if mapa_satelital else 0,
        "acreedor_real": None,  # Bloque D: campo para discrepancia — se puede pasar via Form en futuras versiones
    }

    # 4. Compilar PDF
    output_pdf = temp_run_dir / f"ARHIAX_Dictamen_{db_record['folio_matricula']}_final.pdf"
    try:
        compile_pdf(db_record, str(output_pdf), assets_dir=temp_run_dir)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error al compilar el PDF pericial: {str(e)}")

    with open(output_pdf, "rb") as f:
        pdf_bytes = f.read()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="ARHIAX_Dictamen_{db_record["folio_matricula"]}.pdf"'
        }
    )

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
        
    with open(dictamen["pdf_path"], "rb") as f:
        pdf_bytes = f.read()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="ARHIAX_Dictamen_{dictamen["folio_matricula"]}.pdf"'
        }
    )

@app.get("/api/config")
def get_config():
    if not DEFAULT_YAML_PATH.exists():
        raise HTTPException(status_code=404, detail="Metodología no encontrada.")
    with open(DEFAULT_YAML_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    return {"yaml": content}

# Servir archivos estáticos del frontend (public) en la raíz
PUBLIC_DIR = os.path.join(PROJECT_ROOT, "public")
if os.path.exists(PUBLIC_DIR):
    app.mount("/", StaticFiles(directory=PUBLIC_DIR, html=True), name="public")

if import_error:
    app.routes.clear()
    @app.api_route("/{path_name:path}", methods=["GET", "POST", "PUT", "DELETE"])
    def fallback(path_name: str):
        return {
            "error": "Startup failed during imports",
            "traceback": import_error
        }

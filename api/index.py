import os
import sys
import tempfile
import time
import hmac
import hashlib
import yaml
import shutil
import re
import pypdf
from collections import defaultdict, deque
from pathlib import Path
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Body, UploadFile, File, Depends, Form, BackgroundTasks, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
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

# CORS — lista blanca explícita de orígenes (F-06: nunca "*" con credenciales)
_ALLOWED_ORIGINS = [o.strip() for o in os.environ.get(
    "ARHIAX_ALLOWED_ORIGINS",
    "https://arhiax-re.vercel.app,http://localhost:8000,http://localhost:3000"
).split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEFAULT_YAML_PATH = Path(LONJA_LAYER) / "lonja_baq_metodologia.yaml"

# ---- Autenticación real con roles (backlog: panel de administración) ----
# Credenciales desde variables de entorno (Vercel env vars). El fallback solo
# existe para desarrollo local.
ACCESS_PASSWORD = os.environ.get("ARHIAX_ACCESS_PASSWORD", "Sinergia2026")  # contraseña global = cuenta admin (retrocompat)
AUTH_SECRET = os.environ.get("ARHIAX_AUTH_SECRET", "cambiar-este-secreto-en-produccion")
TOKEN_TTL_HOURS = int(os.environ.get("ARHIAX_TOKEN_TTL_HOURS", "8"))

# Usuarios con rol, definidos por env vars (persisten en Vercel):
#   ARHIAX_ADMIN_USER / ARHIAX_ADMIN_PASSWORD        -> rol 'admin' (default: admin / ACCESS_PASSWORD)
#   ARHIAX_OPERADOR_USER / ARHIAX_OPERADOR_PASSWORD  -> rol 'operador' (opcional)
_USUARIOS = {}  # username.lower() -> (password, rol)
_USUARIOS[os.environ.get("ARHIAX_ADMIN_USER", "admin").strip().lower()] = (
    os.environ.get("ARHIAX_ADMIN_PASSWORD") or ACCESS_PASSWORD, "admin")
_op_user = os.environ.get("ARHIAX_OPERADOR_USER", "").strip().lower()
_op_pass = os.environ.get("ARHIAX_OPERADOR_PASSWORD", "").strip()
if _op_user and _op_pass:
    _USUARIOS[_op_user] = (_op_pass, "operador")

_security = HTTPBearer(auto_error=False)


def _firmar(payload: str) -> str:
    return hmac.new(AUTH_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def _crear_token(username: str, rol: str) -> str:
    exp = (datetime.now() + timedelta(hours=TOKEN_TTL_HOURS)).isoformat()
    payload = f"{exp}|{username}|{rol}"
    return f"{payload}.{_firmar(payload)}"


def _decodificar_token(token: str):
    """Retorna (username, rol) si el token es válido, o None."""
    try:
        payload, firma = token.rsplit(".", 1)
        if not hmac.compare_digest(_firmar(payload), firma):
            return None
        exp_s, username, rol = payload.split("|", 2)
        if datetime.now() >= datetime.fromisoformat(exp_s):
            return None
        return username, rol
    except Exception:
        return None


def require_auth(credentials: HTTPAuthorizationCredentials = Depends(_security)):
    if credentials is None:
        raise HTTPException(status_code=401, detail="Sesión inválida o expirada. Inicie sesión nuevamente.")
    datos = _decodificar_token(credentials.credentials)
    if datos is None:
        raise HTTPException(status_code=401, detail="Sesión inválida o expirada. Inicie sesión nuevamente.")
    return {"username": datos[0], "rol": datos[1]}


def require_admin(auth: dict = Depends(require_auth)):
    """Restringe a usuarios con rol 'admin' (403 para operadores)."""
    if auth.get("rol") != "admin":
        raise HTTPException(status_code=403, detail="Se requieren privilegios de administrador.")
    return auth


# Rate limiting simple en memoria para /api/login (F-03)
_intentos_login = defaultdict(deque)


def _check_login_rate_limit(request: Request, max_intentos: int = 5, ventana_seg: int = 300):
    ip = request.client.host if request.client else "desconocida"
    ahora = time.time()
    cola = _intentos_login[ip]
    while cola and ahora - cola[0] > ventana_seg:
        cola.popleft()
    if len(cola) >= max_intentos:
        raise HTTPException(status_code=429, detail="Demasiados intentos fallidos. Intente en 5 minutos.")
    cola.append(ahora)


# ---- Validación de insumos (F-04, F-08) ----
FOLIO_RE = re.compile(r"^\d{3}-\d{1,8}$")
MAX_UPLOAD_BYTES = 8 * 1024 * 1024  # 8 MB


def _sanitizar_folio(folio) -> str:
    """Normaliza una matrícula inmobiliaria (040-XXXXXX) o devuelve 'Pendiente'."""
    if not folio or not isinstance(folio, str):
        return "Pendiente"
    m = FOLIO_RE.match(folio.strip())
    return m.group(0) if m else "Pendiente"


def _validar_archivo_subido(file: UploadFile, img_type: str) -> None:
    """Valida firma mágica del archivo según el tipo de insumo (F-04)."""
    head = file.file.read(8)
    file.file.seek(0)
    if img_type == "certificado":
        if not head.startswith(b"%PDF"):
            raise HTTPException(status_code=400, detail="El certificado debe ser un archivo PDF válido.")
    elif img_type in ("sombra_9am", "sombra_3pm", "mapa_satelital"):
        if not head.startswith(b"\x89PNG\r\n\x1a\n"):
            raise HTTPException(status_code=400, detail="La imagen debe ser un PNG válido.")


def _copiar_con_limite(src, dst: Path, limite: int = MAX_UPLOAD_BYTES) -> int:
    total = 0
    try:
        with open(dst, "wb") as out:
            while chunk := src.read(65536):
                total += len(chunk)
                if total > limite:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Archivo excede el límite de {limite // (1024 * 1024)} MB.",
                    )
                out.write(chunk)
    except HTTPException:
        if dst.exists():
            dst.unlink()
        raise
    return total

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
def login(payload: dict = Body(...), request: Request = None):
    password = payload.get("password", "")
    username = (payload.get("username") or "").strip().lower()
    if not isinstance(password, str):
        raise HTTPException(status_code=401, detail="Credenciales inválidas.")
    if username:
        # Autenticación por usuario + rol (panel de administración)
        cred = _USUARIOS.get(username)
        if not cred or not hmac.compare_digest(password.encode("utf-8"), cred[0].encode("utf-8")):
            if request is not None:
                _check_login_rate_limit(request)
            raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos.")
        return {"success": True, "token": _crear_token(username, cred[1]), "rol": cred[1],
                "username": username, "expires_in_hours": TOKEN_TTL_HOURS}
    # Retrocompatibilidad: contraseña global == cuenta admin
    admin_cred = _USUARIOS.get("admin", ("", ""))
    if not hmac.compare_digest(password.encode("utf-8"), admin_cred[0].encode("utf-8")):
        if request is not None:
            _check_login_rate_limit(request)
        raise HTTPException(status_code=401, detail="Contraseña incorrecta. Acceso denegado.")
    return {"success": True, "token": _crear_token("admin", "admin"), "rol": "admin",
            "username": "admin", "expires_in_hours": TOKEN_TTL_HOURS}

@app.get("/api/me")
def me(auth: dict = Depends(require_auth)):
    """Devuelve el usuario y rol de la sesión actual."""
    return {"username": auth["username"], "rol": auth["rol"]}

@app.get("/api/v1/admin/usuarios")
def admin_usuarios(auth: dict = Depends(require_admin)):
    """Lista las cuentas con rol conocidas (sin secretos). Solo admin."""
    return {"usuarios": [
        {"username": u, "rol": r} for u, (_p, r) in sorted(_USUARIOS.items())
    ]}

@app.get("/api/dictamenes")
def list_dictamenes(auth: bool = Depends(require_auth)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM dictamenes ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    # No exponer rutas internas del filesystem al cliente (F-13)
    resultado = []
    for row in rows:
        d = dict(row)
        d.pop("pdf_path", None)
        d.pop("certificado_path", None)
        resultado.append(d)
    return resultado

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
        
    # 3. Fallback para direcciones desconocidas (M-01/F-15):
    # NO se fabrican folios simulados con md5 (parecerían matrículas reales en un
    # dictamen pericial). Se devuelve 'Pendiente' y el barrio inferido por texto.
    barrio = "Miramar"
    if "recreo" in normalized.lower() or "el recreo" in normalized.lower():
        barrio = "El Recreo"
    return "Pendiente", barrio, 4

@app.get("/api/resolver-matricula")
def resolve_matricula_endpoint(direccion: str, auth: bool = Depends(require_auth)):
    try:
        folio, barrio, estrato = resolver_matricula_por_direccion(direccion)
        return {"folio_matricula": folio, "barrio": barrio, "estrato": estrato}
    except Exception as e:
        print(f"[ERROR] resolver-matricula: {e}")
        raise HTTPException(status_code=500, detail="No fue posible resolver la matrícula. Intente nuevamente.")

@app.post("/api/dictamenes")
def create_dictamen(payload: dict = Body(...), background_tasks: BackgroundTasks = None, auth: bool = Depends(require_auth)):
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
async def upload_image(case_id: int, img_type: str, file: UploadFile = File(...), auth: bool = Depends(require_auth)):
    if img_type not in ["sombra_9am", "sombra_3pm", "mapa_satelital", "certificado"]:
        raise HTTPException(status_code=400, detail="Tipo de insumo inválido.")
    _validar_archivo_subido(file, img_type)

    case_dir = ASSETS_DIR / f"case_{case_id}"
    case_dir.mkdir(parents=True, exist_ok=True)

    # Manejar extensión del Certificado (PDF)
    ext = ".pdf" if img_type == "certificado" else ".png"
    file_path = case_dir / f"{img_type}{ext}"

    _copiar_con_limite(file.file, file_path)
        
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
            
            pdf_filename = f"ARHIAX_Dictamen_{_sanitizar_folio(dictamen['folio_matricula'])}_final.pdf"
            pdf_output_path = case_dir / pdf_filename
            
            try:
                compile_pdf(dictamen, str(pdf_output_path))
                cursor.execute("UPDATE dictamenes SET estado = 'COMPLETADO', pdf_path = ? WHERE id = ?", 
                               (str(pdf_output_path), case_id))
                conn.commit()
                status = "COMPLETADO"
            except Exception as e:
                conn.close()
                print(f"[ERROR] compilar PDF del dictamen {case_id}: {e}")
                raise HTTPException(status_code=500, detail="Error al compilar el PDF del dictamen. Verifique los insumos e intente nuevamente.")
        
    conn.close()
    return {
        "status": status,
        "area_extraida": area_extraida,
        "area_extraida_fmt": f"{area_extraida} m²" if area_extraida else None,
        "extraidos": extraidos
    }

@app.post("/api/dictamenes/{case_id}/update")
def update_dictamen(case_id: int, payload: dict = Body(...), background_tasks: BackgroundTasks = None, auth: bool = Depends(require_auth)):
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
        pdf_filename = f"ARHIAX_Dictamen_{_sanitizar_folio(dictamen['folio_matricula'])}_final.pdf"
        pdf_output_path = case_dir / pdf_filename
        
        try:
            compile_pdf(dictamen, str(pdf_output_path))
            cursor.execute("UPDATE dictamenes SET estado = 'COMPLETADO', pdf_path = ? WHERE id = ?", 
                           (str(pdf_output_path), case_id))
            conn.commit()
            dictamen["estado"] = "COMPLETADO"
        except Exception as e:
            conn.close()
            print(f"[ERROR] compilar PDF del dictamen {case_id}: {e}")
            raise HTTPException(status_code=500, detail="Error al compilar el PDF del dictamen. Verifique los insumos e intente nuevamente.")
            
    conn.close()
    return dictamen

@app.delete("/api/dictamenes/{case_id}")
def delete_dictamen(case_id: int, auth: dict = Depends(require_admin)):
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
    mapa_satelital: UploadFile = File(None),
    async_: bool = Form(False),
    auth: dict = Depends(require_auth)
):
    # Validar campos mínimos
    if not folio_matricula and not direccion:
        raise HTTPException(status_code=400, detail="Debe ingresar la matrícula inmobiliaria o la dirección.")

    if async_:
        # Cola asíncrona (QStash): encolar y responder 202. Sin cola configurada,
        # se degrada a síncrono (el cliente recibe el PDF igual).
        import uuid
        from cola_pdf import encolar_generacion, cola_configurada
        if not cola_configurada():
            # Sin QStash no se crea un trabajo huérfano en la BD: fallback directo.
            return {
                "encolado": False,
                "detalle": "Cola no configurada (QSTASH_TOKEN / ARHIAX_WORKER_URL). "
                           "Generando de forma síncrona.",
            }
        job_id = str(uuid.uuid4())
        _crear_trabajo(job_id, "pendiente")
        datos = {
            "job_id": job_id,
            "folio_matricula": folio_matricula,
            "direccion": direccion,
            "area": area,
            "barrio": barrio,
        }
        if certificado and certificado.filename:
            _validar_archivo_subido(certificado, "certificado")
            import base64
            contenido = certificado.file.read(MAX_UPLOAD_BYTES)
            datos["certificado_b64"] = base64.b64encode(contenido).decode("ascii")
        enc = encolar_generacion(datos)
        if enc.get("encolado"):
            return {
                "encolado": True, "job_id": job_id, "message_id": enc.get("message_id"),
                "estado": "pendiente", "consulta": f"/api/v1/pdf/trabajos/{job_id}",
            }
        # QStash configurado pero el publish falló
        _actualizar_trabajo(job_id, "error", error=enc.get("error") or "publish fallido")
        raise HTTPException(status_code=500, detail=f"Error al encolar: {enc.get('error')}")

    import uuid
    run_id = str(uuid.uuid4())
    temp_run_dir = Path("/tmp") / f"run_{run_id}"
    temp_run_dir.mkdir(parents=True, exist_ok=True)

    # 1. Guardar archivos cargados (solo si no están vacíos) con validación de contenido
    if certificado and certificado.filename:
        _validar_archivo_subido(certificado, "certificado")
        cert_path = temp_run_dir / "certificado.pdf"
        _copiar_con_limite(certificado.file, cert_path)
        
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

    # Guardar imágenes de ArcGIS Pro si vienen y no están vacías (validación de contenido)
    if sombra_9am and sombra_9am.filename:
        _validar_archivo_subido(sombra_9am, "sombra_9am")
        _copiar_con_limite(sombra_9am.file, temp_run_dir / "sombra_9am.png")
    if sombra_3pm and sombra_3pm.filename:
        _validar_archivo_subido(sombra_3pm, "sombra_3pm")
        _copiar_con_limite(sombra_3pm.file, temp_run_dir / "sombra_3pm.png")
    if mapa_satelital and mapa_satelital.filename:
        _validar_archivo_subido(mapa_satelital, "mapa_satelital")
        _copiar_con_limite(mapa_satelital.file, temp_run_dir / "mapa_satelital.png")

    # 2. Calcular valor consolidado
    valor_m2 = 6887625 if "miramar" in barrio.lower() else 5146666
    valor_consolidado = int(round(valor_m2 * area, -4))

    # H-08: si se adjuntó certificado, pasar su ruta para que compile_pdf lo analice
    # (evita el hallazgo falso "AUSENCIA DE CTL" cuando el usuario SÍ subió el CTL)
    _cert_path = str(cert_path) if (certificado and certificado.filename) else None

    # 3. Construir record para ReportLab
    db_record = {
        "id": 9999,  # ID temporal
        "folio_matricula": _sanitizar_folio(folio_matricula) or "Pendiente",
        "direccion": direccion or "Pendiente",
        "barrio": barrio,
        "estrato": 4,
        "area": area,
        "valor_consolidado": valor_consolidado,
        "sombra_9am_cargada": 1 if sombra_9am else 0,
        "sombra_3pm_cargada": 1 if sombra_3pm else 0,
        "mapa_cargado": 1 if mapa_satelital else 0,
        "acreedor_real": None,  # Bloque D: campo para discrepancia — se puede pasar via Form en futuras versiones
        "certificado_path": _cert_path,
    }

    # 4. Compilar PDF
    output_pdf = temp_run_dir / f"ARHIAX_Dictamen_{db_record['folio_matricula']}_final.pdf"
    try:
        compile_pdf(db_record, str(output_pdf), assets_dir=temp_run_dir)
    except Exception as e:
        print(f"[ERROR] compilar PDF stateless: {e}")
        raise HTTPException(status_code=500, detail="Error al compilar el PDF pericial. Verifique los insumos e intente nuevamente.")

    with open(output_pdf, "rb") as f:
        pdf_bytes = f.read()

    folio_limpio = _sanitizar_folio(db_record["folio_matricula"])
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="ARHIAX_Dictamen_{folio_limpio}.pdf"'
        }
    )

# ── Cola asíncrona de PDF (QStash) ─────────────────────────────────────

def _dir_trabajo(run_id: str) -> Path:
    """Directorio temporal de trabajo: ARHIAX_TMP_DIR (tests/dev) o /tmp (Vercel)."""
    base = os.environ.get("ARHIAX_TMP_DIR") or "/tmp"
    d = Path(base) / f"run_{run_id}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _crear_trabajo(job_id: str, estado: str = "pendiente"):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO trabajos_pdf (id, estado, creado) VALUES (?, ?, ?)",
                   (job_id, estado, datetime.now().isoformat()))
    conn.commit()
    conn.close()


def _actualizar_trabajo(job_id: str, estado: str, pdf_bytes=None, error=None):
    """Crea o actualiza un trabajo (UPSERT: funciona también si el worker se invoca
    sin pasar por /generar async, que es quien crea el job)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO trabajos_pdf (id, estado, pdf, error, creado) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            estado = excluded.estado,
            pdf = excluded.pdf,
            error = excluded.error
        """,
        (job_id, estado, pdf_bytes, error, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


@app.get("/api/v1/pdf/estado")
def estado_cola_pdf(auth: dict = Depends(require_admin)):
    """Estado de la cola asíncrona (solo admin)."""
    from cola_pdf import estado_cola
    return estado_cola()


@app.post("/api/v1/pdf/worker")
def worker_generar_pdf(payload: dict = Body(...), auth: dict = Depends(require_auth)):
    """Worker de la cola (lo invoca QStash): compila el PDF del job y lo guarda.

    Recibe JSON: {job_id, folio_matricula, direccion, area, barrio, certificado_b64?}.
    """
    import base64
    job_id = str(payload.get("job_id") or "")
    if not job_id:
        raise HTTPException(status_code=400, detail="Falta job_id.")
    _actualizar_trabajo(job_id, "procesando", error=None)

    certificado_bytes = None
    if payload.get("certificado_b64"):
        try:
            certificado_bytes = base64.b64decode(payload["certificado_b64"])
        except Exception:
            certificado_bytes = None

    import uuid
    run_id = str(uuid.uuid4())
    temp_run_dir = _dir_trabajo(run_id)

    folio = payload.get("folio_matricula")
    direccion = payload.get("direccion") or "Pendiente"
    area = float(payload.get("area") or 0)
    barrio = payload.get("barrio") or "Miramar"

    _cert_path = None
    if certificado_bytes:
        cert_path = temp_run_dir / "certificado.pdf"
        cert_path.write_bytes(certificado_bytes)
        _cert_path = str(cert_path)
        try:
            extraidos = extraer_datos_de_pdf(_cert_path)
            if not area and extraidos.get("area"):
                area = extraidos["area"]
            if (not folio or folio == "Pendiente") and extraidos.get("folio"):
                folio = extraidos["folio"]
            if not direccion and extraidos.get("direccion"):
                direccion = extraidos["direccion"]
            if not barrio and extraidos.get("barrio"):
                barrio = extraidos["barrio"]
        except Exception:
            pass

    if not barrio:
        barrio = "Miramar"
    if area is None or area < 0:
        area = 0.0

    valor_m2 = 6887625 if "miramar" in barrio.lower() else 5146666
    db_record = {
        "id": 9999,
        "folio_matricula": _sanitizar_folio(folio) or "Pendiente",
        "direccion": direccion or "Pendiente",
        "barrio": barrio,
        "estrato": 4,
        "area": area,
        "valor_consolidado": int(round(valor_m2 * area, -4)),
        "sombra_9am_cargada": 0,
        "sombra_3pm_cargada": 0,
        "mapa_cargado": 0,
        "acreedor_real": None,
        "certificado_path": _cert_path,
    }
    output_pdf = temp_run_dir / f"ARHIAX_Dictamen_{db_record['folio_matricula']}_final.pdf"
    try:
        compile_pdf(db_record, str(output_pdf), assets_dir=temp_run_dir)
        pdf_bytes = output_pdf.read_bytes()
        _actualizar_trabajo(job_id, "listo", pdf_bytes=pdf_bytes)
        return {"job_id": job_id, "estado": "listo", "bytes": len(pdf_bytes),
                "folio": db_record["folio_matricula"]}
    except Exception as e:
        print(f"[ERROR] worker PDF {job_id}: {e}")
        _actualizar_trabajo(job_id, "error", error=str(e)[:300])
        raise HTTPException(status_code=500, detail="Error al compilar el PDF en el worker.")


@app.get("/api/v1/pdf/trabajos/{job_id}")
def obtener_trabajo_pdf(job_id: str, auth: dict = Depends(require_auth)):
    """Consulta el estado de un trabajo asíncrono; si está listo, devuelve el PDF."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, estado, pdf, error FROM trabajos_pdf WHERE id = ?", (job_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado.")
    estado = row["estado"]
    if estado == "listo" and row["pdf"]:
        return Response(content=bytes(row["pdf"]), media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="ARHIAX_Dictamen_{job_id}.pdf"'})
    return {"job_id": job_id, "estado": estado, "error": row["error"]}


@app.get("/api/dictamenes/{case_id}/pdf")
def download_pdf(case_id: int, auth: bool = Depends(require_auth)):
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

    folio_limpio = _sanitizar_folio(dictamen["folio_matricula"])
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="ARHIAX_Dictamen_{folio_limpio}.pdf"'
        }
    )

@app.get("/api/health")
def health():
    """Monitoreo de plataforma (sin auth): 200 si la API responde."""
    return {
        "status": "ok",
        "servicio": "arhiax-re-api",
        "timestamp": datetime.now().isoformat(),
    }

@app.get("/api/v1/status")
def status_endpoint(auth: dict = Depends(require_admin)):
    """Monitoreo de servicios (auth): estado del motor geoespacial, ciudades y
    servicios nacionales configurados. Sin llamadas de red salientes."""
    from config import listar_ciudades, get_nacionales
    from geospatial_engine import load_geospatial_index
    cache = None
    try:
        cache = load_geospatial_index()
    except Exception as e:
        cache = {"error": str(e)[:120]}
    geo = {"capas_disponibles": False, "features_amenaza": 0, "features_riesgo": 0}
    if isinstance(cache, dict) and cache.get("capas_disponibles"):
        geo = {
            "capas_disponibles": True,
            "features_amenaza": len(cache.get("amenaza", {}).get("items", [])),
            "features_riesgo": len(cache.get("riesgo", {}).get("items", [])),
        }
    elif isinstance(cache, dict) and "error" in cache:
        geo["error"] = cache["error"]
    return {
        "api": "ARHIAX RE",
        "version": "2026.09",
        "timestamp": datetime.now().isoformat(),
        "motor_geoespacial": geo,
        "ciudades": listar_ciudades(),
        "nacionales": {k: (v.get("estado", "") if isinstance(v, dict) else "") for k, v in get_nacionales().items()},
    }

@app.get("/api/config")
def get_config(auth: bool = Depends(require_auth)):
    if not DEFAULT_YAML_PATH.exists():
        raise HTTPException(status_code=404, detail="Metodología no encontrada.")
    with open(DEFAULT_YAML_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    return {"yaml": content}

@app.get("/api/v1/geo/catastro")
def verificar_catastro_en_vivo(
    lat: float = None,
    lon: float = None,
    direccion: str = None,
    ciudad: str = "barranquilla",
    auth: bool = Depends(require_auth),
):
    """Sprint 3 (I-1/I-3): verificación territorial EN VIVO por ciudad contra los
    servicios institucionales abiertos (Barranquilla catastro ArcGIS, Medellín POT
    servidormapas, Cali IDESC WFS; Bogotá en evaluación). Devuelve features +
    fuente/timestamp; nunca afirma datos que no obtuvo (disponible=False si el
    servicio no responde)."""
    if lat is None or lon is None:
        if not direccion:
            raise HTTPException(status_code=400, detail="Indique lat/lon o dirección.")
        try:
            from geocoder import geocodificar_direccion
            lat, lon = geocodificar_direccion(direccion)
        except Exception:
            raise HTTPException(status_code=400, detail="No fue posible geocodificar la dirección.")

    from integrations.territorio import verificar_territorio
    res = verificar_territorio(lat, lon, ciudad)

    return {
        "coordenadas": {"lat": lat, "lon": lon},
        "ciudad": res.get("ciudad", ciudad),
        "disponible": res.get("disponible", False),
        "total_features": res.get("total_features", 0),
        "resumen": res.get("resumen"),
        "features": res.get("features", []),
        "error": res.get("error"),
        "fuente": res.get("fuente", {}),
        "nota": "Verificación territorial en vivo contra servicios abiertos institucionales. "
                "Los resultados no sustituyen el certificado de tradición y libertad (SNR).",
    }

@app.get("/api/v1/geo/ciudades")
def listar_ciudades_endpoint(auth: bool = Depends(require_auth)):
    """Sprint 3 (I-3): estado de las ciudades configuradas para expansión multi-mercado."""
    from config import listar_ciudades, get_nacionales
    return {
        "ciudades": listar_ciudades(),
        "nacionales": {k: (v.get("estado", "") if isinstance(v, dict) else "") for k, v in get_nacionales().items()},
    }

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

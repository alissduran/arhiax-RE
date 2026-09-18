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

# ---- Autenticación real con roles ----
# Credenciales desde variables de entorno. En producción (Vercel) los secretos
# son OBLIGATORIOS y la app FALLA EXPLÍCITAMENTE si faltan (fail-closed): nunca
# arranca con credenciales conocidas de desarrollo. En desarrollo/test se usan
# valores SINTÉTICOS inequívocos (no son credenciales reales utilizables).
_IS_PROD = bool(os.environ.get("VERCEL")) or \
    (os.environ.get("ARHIAX_ENV") or "").strip().lower() in ("prod", "production")

_DEV_AUTH_SECRET = "dev-only-not-a-real-secret"
_DEV_ACCESS_PASSWORD = "dev-only-not-a-real-password"

if _IS_PROD:
    AUTH_SECRET = (os.environ.get("ARHIAX_AUTH_SECRET") or "").strip()
    if not AUTH_SECRET:
        raise RuntimeError(
            "FALTA_CONFIGURACION_DE_SEGURIDAD: ARHIAX_AUTH_SECRET es obligatorio en producción. "
            "Defina una clave aleatoria fuerte en las variables de entorno (Vercel).")
    ACCESS_PASSWORD = (os.environ.get("ARHIAX_ACCESS_PASSWORD") or "").strip()
    _admin_password = (os.environ.get("ARHIAX_ADMIN_PASSWORD") or "").strip() or ACCESS_PASSWORD
    if not _admin_password:
        raise RuntimeError(
            "FALTA_CONFIGURACION_DE_SEGURIDAD: ARHIAX_ADMIN_PASSWORD (o ARHIAX_ACCESS_PASSWORD) "
            "es obligatorio en producción.")
else:
    AUTH_SECRET = (os.environ.get("ARHIAX_AUTH_SECRET") or "").strip() or _DEV_AUTH_SECRET
    ACCESS_PASSWORD = (os.environ.get("ARHIAX_ACCESS_PASSWORD") or "").strip() or _DEV_ACCESS_PASSWORD
    _admin_password = (os.environ.get("ARHIAX_ADMIN_PASSWORD") or "").strip() or ACCESS_PASSWORD

TOKEN_TTL_HOURS = int(os.environ.get("ARHIAX_TOKEN_TTL_HOURS", "8"))

# Usuarios con rol, definidos por env vars (persisten en Vercel):
#   ARHIAX_ADMIN_USER / ARHIAX_ADMIN_PASSWORD        -> rol 'admin'
#   ARHIAX_OPERADOR_USER / ARHIAX_OPERADOR_PASSWORD  -> rol 'operador' (opcional)
_USUARIOS = {}  # username.lower() -> (password, rol)
_USUARIOS[os.environ.get("ARHIAX_ADMIN_USER", "admin").strip().lower()] = (
    _admin_password, "admin")
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
# Folios de matrícula SNR por oficina de registro: Barranquilla '040-...',
# Medellín '001-...', Bogotá con sub-oficinas alfanuméricas '50C-/50N-/50S-...'
# (Zona Centro/Norte/Sur). Solo alfanumérico superior: seguro para nombres de
# archivo y headers (sin '/' ni '..').
FOLIO_RE = re.compile(r"^[0-9]{2,3}[A-Z]?-\d{1,12}$")
MAX_UPLOAD_BYTES = 8 * 1024 * 1024  # 8 MB


def _sanitizar_folio(folio) -> str:
    """Normaliza una matrícula inmobiliaria (040-XXXXXX) o devuelve 'Pendiente'."""
    if not folio or not isinstance(folio, str):
        return "Pendiente"
    m = FOLIO_RE.match(folio.strip())
    return m.group(0) if m else "Pendiente"


# Ciudades operativas del motor ARHIAX (Sprint 3). 'cali' está configurada en
# ciudades.yaml pero NO está integrada en catastro/geocoder/valoración: ofrecerla
# hoy generaría un dictamen con datos y geocodificación de Barranquilla sin
# que el usuario lo note (riesgo de desinformación) -> se rechaza con 400.
# 'pasto' es seleccionable: geocodificación (OSM/Nominatim) y POI operan para
# cualquier ciudad; catastro/POT/valoración local se declaran PENDIENTES de
# fuente en vivo (nunca se rellenan con datos de Barranquilla).
_CIUDADES_OPERATIVAS = ("barranquilla", "medellin", "bogota", "pasto")
_CIUDADES_PENDIENTES = {
    "cali": "Cali aún no está operativa en el motor ARHIAX (integración de catastro y POT pendiente)",
}


def _normalizar_ciudad(ciudad) -> str:
    """Normaliza la ciudad recibida a una operativa.

    - Vacía/None -> 'barranquilla' (retrocompatibilidad).
    - Operativa  -> se devuelve tal cual.
    - Pendiente (p. ej. 'cali') -> HTTPException 400: jamás se produce un
      dictamen de una ciudad con datos de otra.
    - Desconocida -> 'barranquilla' (retrocompatibilidad con clientes viejos).
    """
    c = (ciudad or "").lower().strip()
    if not c:
        return "barranquilla"
    if c in _CIUDADES_OPERATIVAS:
        return c
    if c in _CIUDADES_PENDIENTES:
        raise HTTPException(
            status_code=400,
            detail=("{}: no se puede generar el dictamen. Por el momento "
                    "seleccione Barranquilla, Medellín, Bogotá D.C. o Pasto.".format(
                        _CIUDADES_PENDIENTES[c])))
    return "barranquilla"


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

def extraer_datos_de_pdf(pdf_path: str, ciudad: str = "barranquilla") -> dict:
    """Analiza de manera inteligente el certificado para extraer área, matrícula,
    barrio, dirección y — clave para la exactitud — el código catastral/NUPRE que
    el CTL del SNR incluye. Si el CTL trae código, el predio REAL se resuelve en
    el catastro abierto de la ciudad indicada y sus datos oficiales (dirección,
    coordenadas, destino) prevalecen sobre cualquier inferencia.

    ciudad: 'barranquilla' (datosabiertos) | 'medellin' (servidormapas) | 'bogota' (serviciosgis) | 'pasto' (geocodificación OSM; catastro en vivo pendiente).
    """
    datos = {"area": None, "folio": None, "barrio": None, "direccion": None}
    es_medellin = "medellin" in (ciudad or "").lower()
    es_bogota = "bogota" in (ciudad or "").lower()
    es_pasto = "pasto" in (ciudad or "").lower()
    try:
        reader = pypdf.PdfReader(pdf_path)
        texto = ""
        for page in reader.pages:
            t = page.extract_text()
            if t:
                texto += t
                
        # 1. Extraer Área
        # Regresión (CTL real 040-646406): el certificado del SNR escribe el área
        # como 'AREA PRIVADA - METROS CUADRADOS: 58 CENTIMETROS CUADRADOS: 7500'
        # (58 m2 + 7500 cm2 = 58.75 m2). Sin este patrón el dictamen dejaba el
        # área en 0 y mostraba el área de TERRENO catastral (22.05) como si fuera
        # la del apartamento.
        patrones_area = [
            # 'AREA PRIVADA - METROS CUADRADOS: 58 CENTIMETROS CUADRADOS: 7500'
            r"(?:área|area)\s+privada\s*[-–—:]?\s*"
            r"metros\s+cuadrados\s*:?\s*(\d+(?:[.,]\d+)?)\s+"
            r"centimetros\s+cuadrados\s*:?\s*(\d+(?:[.,]\d+)?)",
            r"(?:área|area)\s+(?:privada|construida)\s+(?:de\s+)?(\d+(?:[.,]\d+)?)\s*(?:m2|metros|mts|M2)",
            r"(?:cabida|superficie)\s+(?:de\s+)?(\d+(?:[.,]\d+)?)\s*(?:m2|metros|mts|M2)",
            r"(?:área|area)\s+(?:de\s+)?(\d+(?:[.,]\d+)?)\s*(?:m2|metros|mts|M2)",
            r"(\d+(?:[.,]\d+)?)\s*(?:m2|metros\s+cuadrados|mts2|M2)",
        ]
        for patron in patrones_area:
            matches = re.findall(patron, texto, re.IGNORECASE)
            if not matches:
                continue
            try:
                if isinstance(matches[0], tuple):  # metros + centimetros
                    m_grp = matches[0]
                    area_float = float(str(m_grp[0]).replace(",", ".")) + \
                        float(str(m_grp[1]).replace(",", ".")) / 10000.0
                else:
                    area_float = float(str(matches[0]).replace(",", "."))
                if 10 <= area_float <= 1000:
                    datos["area"] = round(area_float, 2)
                    break
            except (ValueError, TypeError, IndexError):
                continue

        # 2. Extraer Matrícula (Folio): misma lógica del analizador legal
        # (acepta '040-...', '001-...' y '50C-/50N-/50S-...' de Bogotá; respeta
        # la etiqueta principal del CTL y no los folios citados en el cuerpo).
        try:
            from legal_analyzer import _extraer_folio
            folio_extraido = _extraer_folio(texto)
        except Exception:
            folio_extraido = None
        if folio_extraido:
            datos["folio"] = folio_extraido

        # 2b. Código catastral y NUPRE del CTL (fuente de verdad del predio real)
        try:
            from catastro_predio import extraer_codigo_nupre_de_ctl
            cods = extraer_codigo_nupre_de_ctl(texto)
            datos["codigo_catastral"] = cods.get("codigo_catastral")
            datos["nupre"] = cods.get("nupre")
        except Exception:
            datos["codigo_catastral"] = None
            datos["nupre"] = None

        # 2c. Si el CTL trae código/NUPRE, resolver el predio REAL en el catastro
        # de la ciudad: dirección oficial, coordenadas y barrio salen de ahí.
        # (Bogotá no publica capa predial con NUPRE: la resolución es por punto en
        # compile_pdf; aquí basta con dejar el código declarado.)
        if datos.get("codigo_catastral") or datos.get("nupre"):
            try:
                if es_medellin:
                    from catastro_predio_medellin import enriquecer_desde_ctl as _enr
                    _r = _enr(datos["codigo_catastral"], datos["nupre"])
                elif not es_bogota and not es_pasto:
                    from catastro_predio import enriquecer_desde_ctl as _enr
                    _r = _enr(datos["codigo_catastral"], datos["nupre"])
                else:
                    _r = None
                if _r and _r.get("disponible"):
                    if _r.get("direccion_oficial"):
                        datos["direccion"] = _r["direccion_oficial"]
                    if _r.get("lat") is not None and _r.get("lon") is not None:
                        datos["lat"] = _r["lat"]
                        datos["lon"] = _r["lon"]
                        datos["fuente_geocod"] = "catastro_predio_codigo"
                    _ent = _r.get("entorno") or {}
                    if _ent.get("barrio"):
                        datos["barrio"] = _ent["barrio"]
                    _p = _r.get("predio") or {}
                    datos["destino_economico"] = _p.get("destino_economico")
                    _c = _r.get("lote") or _r.get("construccion") or {}
                    datos["area_catastral"] = _c.get("area_lote") or _c.get("area_catastral_terreno")
                    datos["estrato_catastral"] = (_ent or {}).get("estrato")
            except Exception as e:
                print(f"[EXTRAER-DATOS][WARN] enriquecimiento por código falló ({ciudad}): {e}")

        # 3. Extraer datos geoespaciales desde el CTL (direccion, barrio, lat, lon)
        # Solo como complemento si el predio por código no se resolvió.
        if not datos.get("direccion") or not datos.get("lat"):
            geo_ctl = geocodificar_desde_ctl(texto, ciudad=ciudad)
            if not datos.get("barrio") and geo_ctl.get("barrio"):
                datos["barrio"] = geo_ctl["barrio"]
            if not datos.get("direccion") and geo_ctl.get("direccion"):
                datos["direccion"] = geo_ctl["direccion"]
            if not datos.get("lat") or not datos.get("lon"):
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
def list_dictamenes(auth: dict = Depends(require_auth)):
    from case_service import list_cases
    # Fuente canónica: Postgres/Neon (o SQLite local). El frontend lee de aquí.
    return list_cases()

def resolver_matricula_por_direccion(direccion: str) -> tuple:
    """
    Resuelve una dirección en una matrícula catastral candidata de Barranquilla (08001).
    Utiliza normalización y reglas de coincidencia inteligente para predios conocidos,
    y un fallback determinista para otros predios.
    Retorna: (folio_matricula, barrio, estrato)
    """
    if not direccion or direccion.strip().lower() == "pendiente":
        return "Pendiente", "", 4
        
    normalized = normalize_address_colombia(direccion)
    
    # 1. Caso Napoli (Miramar) — activo de demostración explícito
    if ("43" in normalized and "100" in normalized) or "NAPOLI" in normalized:
        return "040-646406", "Miramar", 4
        
    # 2. Caso Calle 63 # 37-71 (El Recreo)
    if ("63" in normalized and "37" in normalized) or "RECREO" in normalized:
        return "040-314248", "El Recreo", 4
        
    # 3. Fallback para direcciones desconocidas (M-01/F-15):
    # NO se fabrican folios simulados ni se afirma un barrio de demostración:
    # 'Miramar' pertenece al caso demo Napoli y no puede contaminar un predio
    # real. El barrio real se resuelve al procesar el CTL (código catastral).
    return "Pendiente", "", 4

@app.get("/api/resolver-matricula")
def resolve_matricula_endpoint(direccion: str, auth: bool = Depends(require_auth)):
    try:
        folio, barrio, estrato = resolver_matricula_por_direccion(direccion)
        return {"folio_matricula": folio, "barrio": barrio, "estrato": estrato}
    except Exception as e:
        print(f"[ERROR] resolver-matricula: {e}")
        raise HTTPException(status_code=500, detail="No fue posible resolver la matrícula. Intente nuevamente.")

@app.post("/api/dictamenes")
def create_dictamen(payload: dict = Body(...), background_tasks: BackgroundTasks = None, auth: dict = Depends(require_auth)):
    from case_service import create_case, ValidationError
    folio = (payload.get("folio_matricula") or "").strip()
    direccion = (payload.get("direccion") or "").strip()

    if not folio and not direccion:
        raise HTTPException(status_code=400, detail="Debe ingresar la matrícula inmobiliaria o la dirección del predio.")

    barrio = ""
    estrato = 4
    ciudad = (payload.get("ciudad") or "barranquilla").lower().strip()
    if ciudad not in ("barranquilla", "medellin", "bogota", "pasto"):
        ciudad = "barranquilla"

    if not folio and direccion and direccion.lower() != "pendiente":
        folio, barrio, estrato = resolver_matricula_por_direccion(direccion)

    if not folio:
        folio = "Pendiente"
    if not direccion:
        direccion = "Pendiente"
    if "recreo" in direccion.lower():
        barrio = "El Recreo"

    acreedor_real = payload.get("acreedor_real", None)
    username = auth.get("username") if isinstance(auth, dict) else None
    try:
        caso = create_case(folio_matricula=folio, direccion=direccion, barrio=barrio,
                           estrato=estrato, area=0.0, ciudad=ciudad,
                           acreedor_real=acreedor_real, created_by=username)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    new_id = caso["id"]
    # Crear carpeta física para guardar imágenes de este caso
    case_dir = ASSETS_DIR / f"case_{new_id}"
    case_dir.mkdir(parents=True, exist_ok=True)

    if background_tasks:
        try:
            from solar_automation import capturar_sombras_playwright
            lat_solar, lon_solar = geocodificar_direccion(direccion if direccion != "Pendiente" else barrio)
            background_tasks.add_task(capturar_sombras_playwright, lat_solar, lon_solar, new_id, str(case_dir))
        except Exception as e:
            print(f"[ERROR] No se pudo lanzar la tarea de automatización de sombras: {e}")

    return caso

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

@app.post("/api/dictamenes/{case_id}/documentos")
async def subir_documento_caso(
    case_id: int,
    nombre: str = Form(...),
    tipo: str = Form("sarlaft"),
    file: UploadFile = File(...),
    auth: dict = Depends(require_auth)
):
    """Adjunta un documento SARLAFT / debida diligencia al caso (UIAF, UE, PEP,
    extracto hipotecario, levantamiento, etc.). Lo sube el usuario después de
    descargarlo, cuando el agente IA no puede obtenerlo automáticamente."""
    contenido = file.file.read(MAX_UPLOAD_BYTES)
    if not contenido:
        raise HTTPException(status_code=400, detail="El archivo está vacío.")
    import datetime
    creado = datetime.datetime.now(datetime.timezone.utc).isoformat()
    tipo_limpio = (tipo or "sarlaft").strip() or "sarlaft"
    nombre_limpio = (nombre or file.filename or "documento").strip()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO documentos_caso (case_id, nombre, tipo, contenido, creado) "
        "VALUES (?, ?, ?, ?, ?)",
        (case_id, nombre_limpio, tipo_limpio, contenido, creado),
    )
    doc_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return {"id": doc_id, "case_id": case_id, "nombre": nombre_limpio,
            "tipo": tipo_limpio, "creado": creado}


@app.get("/api/dictamenes/{case_id}/documentos")
async def listar_documentos_caso(case_id: int, auth: dict = Depends(require_auth)):
    """Lista los documentos adjuntos al caso (sin el contenido binario)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, nombre, tipo, creado FROM documentos_caso WHERE case_id = ? ORDER BY id",
        (case_id,),
    )
    filas = cursor.fetchall()
    conn.close()
    return [
        {"id": f["id"], "nombre": f["nombre"], "tipo": f["tipo"], "creado": f["creado"]}
        for f in filas
    ]


@app.get("/api/dictamenes/{case_id}/documentos/{doc_id}")
async def descargar_documento_caso(case_id: int, doc_id: int, auth: dict = Depends(require_auth)):
    """Descarga el contenido binario de un documento adjunto."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT nombre, contenido FROM documentos_caso WHERE id = ? AND case_id = ?",
        (doc_id, case_id),
    )
    fila = cursor.fetchone()
    conn.close()
    if not fila:
        raise HTTPException(status_code=404, detail="Documento no encontrado.")
    from fastapi.responses import Response
    nombre_seguro = str(fila["nombre"]).replace('"', "").replace("\\", "")
    return Response(
        content=fila["contenido"],
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{nombre_seguro}"'},
    )

@app.post("/api/dictamenes/{case_id}/update")
def update_dictamen(case_id: int, payload: dict = Body(...), background_tasks: BackgroundTasks = None, auth: dict = Depends(require_auth)):
    from case_service import get_case, update_case

    dictamen = get_case(case_id)
    if not dictamen:
        raise HTTPException(status_code=404, detail="Caso no encontrado.")

    folio = payload.get("folio_matricula", dictamen["folio_matricula"])
    direccion = payload.get("direccion", dictamen["direccion"])

    # Si la dirección cambia, recalcular el barrio de forma inteligente
    barrio = dictamen.get("barrio") or ""
    direccion_cambiada = False
    if direccion and direccion != dictamen["direccion"]:
        direccion_cambiada = True
        try:
            from geocoder import geocodificar_desde_ctl
            geo = geocodificar_desde_ctl(direccion)
            if geo.get("barrio") and geo["barrio"] != "Miramar":
                barrio = geo["barrio"]
        except Exception:
            if "recreo" in direccion.lower():
                barrio = "El Recreo"

    acreedor_real = payload.get("acreedor_real", dictamen.get("acreedor_real", None))
    ciudad = (payload.get("ciudad") or dictamen.get("ciudad") or "barranquilla").lower().strip()
    if ciudad not in ("barranquilla", "medellin", "bogota", "pasto"):
        ciudad = "barranquilla"

    area = dictamen.get("area") or 0
    valor_consolidado = dictamen.get("valor_consolidado") or 0
    if area:
        valor_m2 = 6887625 if "miramar" in barrio.lower() else 5146666
        valor_consolidado = int(round(valor_m2 * area, -4))

    username = auth.get("username") if isinstance(auth, dict) else None
    # Persistencia canónica de los campos del Case vía CaseService.
    dictamen = update_case(case_id, {
        "folio_matricula": folio, "direccion": direccion, "barrio": barrio,
        "valor_consolidado": valor_consolidado, "ciudad": ciudad,
        "acreedor_real": acreedor_real,
    }, updated_by=username)
    if dictamen is None:
        raise HTTPException(status_code=404, detail="Caso no encontrado.")

    case_dir = ASSETS_DIR / f"case_{case_id}"

    # ── Side-effects de GENERACIÓN (deferred a SLICE-005/006): reset de sombras
    # y trigger de compilación del PDF. La persistencia del Case ya se hizo. ──
    if direccion_cambiada and background_tasks:
        try:
            from solar_automation import capturar_sombras_playwright
            lat_solar, lon_solar = geocodificar_direccion(direccion)
            _conn = get_db_connection()
            try:
                _cur = _conn.cursor()
                _cur.execute("UPDATE dictamenes SET sombra_9am_cargada = 0, sombra_3pm_cargada = 0 WHERE id = ?", (case_id,))
                _conn.commit()
            finally:
                _conn.close()
            background_tasks.add_task(capturar_sombras_playwright, lat_solar, lon_solar, case_id, str(case_dir))
        except Exception as e:
            print(f"[ERROR] No se pudo relanzar la automatización de sombras en update: {e}")

    # Re-verificar si ya se puede compilar (requiere la fila COMPLETA con rutas internas).
    _conn = get_db_connection()
    try:
        _cur = _conn.cursor()
        _cur.execute("SELECT * FROM dictamenes WHERE id = ?", (case_id,))
        _row = _cur.fetchone()
    finally:
        _conn.close()
    dictamen_full = dict(_row) if _row else dictamen

    if (dictamen_full.get("sombra_9am_cargada") and dictamen_full.get("sombra_3pm_cargada") and
            dictamen_full.get("mapa_cargado") and dictamen_full.get("area") is not None and
            dictamen_full.get("area") > 0):
        case_dir = ASSETS_DIR / f"case_{case_id}"
        pdf_filename = f"ARHIAX_Dictamen_{_sanitizar_folio(dictamen_full['folio_matricula'])}_final.pdf"
        pdf_output_path = case_dir / pdf_filename
        try:
            compile_pdf(dictamen_full, str(pdf_output_path))
            update_case(case_id, {"estado": "COMPLETADO"}, updated_by=username)
            _conn = get_db_connection()
            try:
                _cur = _conn.cursor()
                _cur.execute("UPDATE dictamenes SET pdf_path = ? WHERE id = ?", (str(pdf_output_path), case_id))
                _conn.commit()
            finally:
                _conn.close()
            dictamen = get_case(case_id) or dictamen
        except Exception as e:
            print(f"[ERROR] compilar PDF del dictamen {case_id}: {e}")
            raise HTTPException(status_code=500, detail="Error al compilar el PDF del dictamen. Verifique los insumos e intente nuevamente.")

    return dictamen

@app.delete("/api/dictamenes/{case_id}")
def delete_dictamen(case_id: int, auth: dict = Depends(require_admin)):
    from case_service import delete_case
    eliminado = delete_case(case_id)
    if eliminado:
        # Eliminar físicamente los archivos asociados al caso
        case_dir = ASSETS_DIR / f"case_{case_id}"
        if case_dir.exists() and case_dir.is_dir():
            try:
                shutil.rmtree(case_dir)
            except Exception as e:
                print(f"Error al eliminar la carpeta del caso {case_id}: {e}")
        return {"success": True, "message": f"Caso {case_id} eliminado exitosamente."}

    # DELETE idempotente: un id que no existe en el servidor (p. ej. un id local
    # creado cuando el POST falló) no es un error que bloquee la limpieza del portal.
    return {"success": True, "message": f"Caso {case_id} no existía en el servidor (se omite).", "ya_inexistente": True}

@app.post("/api/dictamenes/generar")
async def generar_dictamen_stateless(
    folio_matricula: str = Form(None),
    direccion: str = Form(None),
    area: float = Form(None),
    barrio: str = Form(None),
    ciudad: str = Form("barranquilla"),
    certificado: UploadFile = File(None),
    licencia: UploadFile = File(None),
    sombra_9am: UploadFile = File(None),
    sombra_3pm: UploadFile = File(None),
    mapa_satelital: UploadFile = File(None),
    async_: bool = Form(False),
    auth: dict = Depends(require_auth)
):
    # Normalizar ciudad: solo soportadas (barranquilla/medellin/bogota/pasto); Cali
    # (pendiente) se rechaza con 400 en vez de producir datos de otra ciudad.
    ciudad = _normalizar_ciudad(ciudad)
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
        # Persistir los insumos gráficos del job en la BD (el worker los recupera
        # por job_id; QStash no transporta PNG grandes en el payload).
        try:
            if (sombra_9am and sombra_9am.filename):
                _validar_archivo_subido(sombra_9am, "sombra_9am")
            if (sombra_3pm and sombra_3pm.filename):
                _validar_archivo_subido(sombra_3pm, "sombra_3pm")
            if (mapa_satelital and mapa_satelital.filename):
                _validar_archivo_subido(mapa_satelital, "mapa_satelital")
        except HTTPException:
            _actualizar_trabajo(job_id, "error", error="insumo gráfico inválido")
            raise
        _guardar_adjuntos_job(job_id, sombra_9am, sombra_3pm, mapa_satelital)
        datos = {
            "job_id": job_id,
            "folio_matricula": folio_matricula,
            "direccion": direccion,
            "area": area,
            "barrio": barrio,
            "ciudad": ciudad,
        }
        if certificado and certificado.filename:
            _validar_archivo_subido(certificado, "certificado")
            import base64
            contenido = certificado.file.read(MAX_UPLOAD_BYTES)
            datos["certificado_b64"] = base64.b64encode(contenido).decode("ascii")
        if licencia and licencia.filename:
            _validar_archivo_subido(licencia, "certificado")  # la licencia también es PDF
            import base64
            contenido_lic = licencia.file.read(MAX_UPLOAD_BYTES)
            datos["licencia_b64"] = base64.b64encode(contenido_lic).decode("ascii")
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
    _ctl_adjuntado = bool(certificado and certificado.filename)
    if _ctl_adjuntado:
        _validar_archivo_subido(certificado, "certificado")
        cert_path = temp_run_dir / "certificado.pdf"
        _copiar_con_limite(certificado.file, cert_path)
        
        # Intentar extraer datos (con la ciudad indicada para resolver el predio
        # real en el catastro correcto: BAQ datosabiertos o Medellín servidormapas)
        extraidos = extraer_datos_de_pdf(str(cert_path), ciudad=ciudad)
        if not area and extraidos.get("area"):
            area = extraidos["area"]
        if (not folio_matricula or folio_matricula == "Pendiente") and extraidos.get("folio"):
            folio_matricula = extraidos["folio"]
        if (not direccion or direccion == "Pendiente") and extraidos.get("direccion"):
            direccion = extraidos["direccion"]
        if not barrio and extraidos.get("barrio"):
            barrio = extraidos["barrio"]

    if not barrio:
        # Con CTL adjunto nunca se afirma el barrio de demostración: si el CTL
        # no permitió resolverlo, compile_pdf lo dejará PENDIENTE. Sin CTL, el
        # barrio demo ('Miramar') solo aplica al caso de demostración de BAQ.
        if not _ctl_adjuntado and ciudad == "barranquilla":
            barrio = "Miramar"
            if direccion and "recreo" in direccion.lower():
                barrio = "El Recreo"
        else:
            barrio = ""

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

    # Mejora 5: licencia de construcción (PDF opcional) para confrontar lo
    # LICENCIADO vs lo CONSTRUIDO vs la norma POT en la sección 4.3.
    _lic_path = None
    if licencia and licencia.filename:
        _validar_archivo_subido(licencia, "certificado")  # PDF válido
        _lic_path = str(temp_run_dir / "licencia.pdf")
        _copiar_con_limite(licencia.file, Path(_lic_path))

    # 2. Calcular valor consolidado (referencial; compile_pdf recalcula con Lonja)
    valor_m2 = 6887625 if "miramar" in barrio.lower() else 5146666
    valor_consolidado = int(round(valor_m2 * area, -4))

    # H-08: si se adjuntó certificado, pasar su ruta para que compile_pdf lo analice
    # (evita el hallazgo falso "AUSENCIA DE CTL" cuando el usuario SÍ subió el CTL)
    _cert_path = str(cert_path) if _ctl_adjuntado else None

    # 3. Construir record para ReportLab
    db_record = {
        "id": 9999,  # ID temporal
        "folio_matricula": _sanitizar_folio(folio_matricula) or "Pendiente",
        "direccion": direccion or "Pendiente",
        "barrio": barrio,
        "ciudad": ciudad,
        "estrato": 4,
        "area": area,
        "valor_consolidado": valor_consolidado,
        "sombra_9am_cargada": 1 if sombra_9am else 0,
        "sombra_3pm_cargada": 1 if sombra_3pm else 0,
        "mapa_cargado": 1 if mapa_satelital else 0,
        "acreedor_real": None,  # Bloque D: campo para discrepancia — se puede pasar via Form en futuras versiones
        "certificado_path": _cert_path,
        "licencia_path": _lic_path,
        # Datos reales extraídos del CTL (compile_pdf los usa como hint si el
        # catastro en vivo no responde al momento de compilar)
        "lat": extraidos.get("lat") if _ctl_adjuntado else None,
        "lon": extraidos.get("lon") if _ctl_adjuntado else None,
    }

    # 4. Compilar PDF (dictamen único con sus anexos al final)
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

# ── GPV-F-77: Formato Estudio de Títulos Art. 276 Ley 1955 de 2019 ──────
# Genera el DOCX oficial del Ministerio de Vivienda pre-diligenciado con el CTL
# del caso (mismo flujo de insumos que /api/dictamenes/generar, sin valoración).

@app.post("/api/dictamenes/gpv-f77")
async def generar_gpv_f77_endpoint(
    folio_matricula: str = Form(None),
    direccion: str = Form(None),
    area: float = Form(None),
    barrio: str = Form(None),
    ciudad: str = Form("barranquilla"),
    expediente: str = Form(None),
    certificado: UploadFile = File(None),
    auth: dict = Depends(require_auth)
):
    # Normalizar ciudad: solo soportadas (barranquilla/medellin/bogota/pasto); Cali
    # (pendiente) se rechaza con 400 (un Estudio de Títulos de Cali no puede
    # elaborarse con datos registrales/catastrales de otra ciudad).
    ciudad = _normalizar_ciudad(ciudad)

    # El GPV-F-77 es un Estudio de Títulos (instructivo GPV-I-20): el CTL del SNR
    # es la fuente registral obligatoria. Sin él no hay folio que estudiar.
    if not (certificado and certificado.filename):
        raise HTTPException(
            status_code=400,
            detail=("El GPV-F-77 (Estudio de Títulos Art. 276 Ley 1955 de 2019) requiere el "
                    "Certificado de Tradición y Libertad (CTL) del predio: sin el folio no hay "
                    "fuente registral para el estudio. Cargue el CTL e intente nuevamente."))

    import uuid
    from legal_analyzer import analizar_certificado
    from gpv_f77 import generar_docx_gpv_f77

    run_id = str(uuid.uuid4())
    temp_run_dir = _dir_trabajo(run_id)
    cert_path = temp_run_dir / "certificado.pdf"
    try:
        _validar_archivo_subido(certificado, "certificado")
        _copiar_con_limite(certificado.file, cert_path)
        # Extraer metadatos (área, dirección, barrio, código catastral/NUPRE) con el
        # geocoder de la ciudad, y el análisis jurídico completo (titulares, anotaciones).
        extraidos = extraer_datos_de_pdf(str(cert_path), ciudad=ciudad)
        analysis = analizar_certificado(str(cert_path))
    except HTTPException:
        raise
    except Exception as e:
        print(f"[GPV-F-77][ERROR] análisis del CTL: {e}")
        raise HTTPException(status_code=500,
                            detail="No se pudo analizar el Certificado de Tradición y Libertad cargado.")

    # Folio: prioridad CTL (extraidos) -> form
    folio = extraidos.get("folio") or (folio_matricula or "").strip() or analysis.get("folio") or "Pendiente"
    # Dirección: registral del CTL -> catastral oficial -> la digitada por el usuario
    dir_registral = (analysis.get("direccion") or "").strip()
    if dir_registral.lower().startswith("pendiente"):
        dir_registral = ""
    dir_final = dir_registral or (extraidos.get("direccion") or "").strip() or (direccion or "").strip()
    # Barrio: catastro/CTL -> form
    barrio_final = (extraidos.get("barrio") or "").strip() or (barrio or "").strip()

    ctx = {
        "folio": folio,
        "ciudad": ciudad,
        "direccion": dir_final,
        "barrio": barrio_final,
        "expediente": (expediente or "").strip() or None,
        "area_juridica": extraidos.get("area") or (area if area not in (None, 0) else None),
        "area_catastral": extraidos.get("area_catastral"),
        "codigo_catastral": extraidos.get("codigo_catastral") or analysis.get("codigo_catastral"),
        "nupre": extraidos.get("nupre") or analysis.get("nupre"),
        "apertura": analysis.get("apertura"),
        "titulares": analysis.get("titulares"),
        "descripcion_ctl": analysis.get("descripcion_ctl"),
        "anotaciones_detalle": analysis.get("anotaciones_detalle") or [],
        "sin_ctl": False,
    }

    try:
        docx_bytes = generar_docx_gpv_f77(ctx)
    except FileNotFoundError as e:
        print(f"[GPV-F-77][ERROR] plantilla: {e}")
        raise HTTPException(status_code=500,
                            detail="Plantilla GPV-F-77 no disponible en el servidor.")
    except Exception as e:
        print(f"[GPV-F-77][ERROR] generación DOCX: {e}")
        raise HTTPException(status_code=500,
                            detail="Error al generar el Estudio de Títulos GPV-F-77.")

    folio_limpio = _sanitizar_folio(folio) or "caso"
    return Response(
        content=docx_bytes,
        media_type=("application/vnd.openxmlformats-officedocument"
                    ".wordprocessingml.document"),
        headers={
            "Content-Disposition": f'attachment; filename="GPV-F-77_Estudio_Titulos_FMI_{folio_limpio}.docx"'
        }
    )

# ── Cola asíncrona de PDF (QStash) ─────────────────────────────────────

def _dir_trabajo(run_id: str) -> Path:
    """Directorio temporal de trabajo: ARHIAX_TMP_DIR (tests/dev) o /tmp (Vercel)."""
    base = os.environ.get("ARHIAX_TMP_DIR") or "/tmp"
    d = Path(base) / f"run_{run_id}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _guardar_adjuntos_job(job_id: str, sombra_9am=None, sombra_3pm=None, mapa_satelital=None):
    """Persiste los insumos gráficos del job en la BD (BYTEA/BLOB).

    La cola QStash no admite PNG grandes en el payload; en su lugar el worker los
    recupera por job_id desde trabajos_pdf. Los archivos se leen SOLO si vienen
    (UploadFile con nombre) y se valida su tipo antes de persistir.
    """
    def _bytes_de(upload) -> bytes:
        if upload is None:
            return None
        try:
            nombre = (upload.filename or "").strip()
            if not nombre:
                return None
            return upload.file.read(MAX_UPLOAD_BYTES)
        except Exception:
            return None

    b9 = _bytes_de(sombra_9am)
    b3 = _bytes_de(sombra_3pm)
    bm = _bytes_de(mapa_satelital)
    if not (b9 or b3 or bm):
        return
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE trabajos_pdf SET
                sombra_9am = COALESCE(?, sombra_9am),
                sombra_3pm = COALESCE(?, sombra_3pm),
                mapa_satelital = COALESCE(?, mapa_satelital)
            WHERE id = ?
            """,
            (b9, b3, bm, job_id),
        )
        conn.commit()
    except Exception as e:
        print(f"[JOB-ADJUNTOS][WARN] no se pudieron persistir imágenes del job {job_id}: {e}")
    finally:
        conn.close()


def _leer_adjuntos_job(job_id: str) -> dict:
    """Recupera los bytes de los insumos gráficos persistidos para el job."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT sombra_9am, sombra_3pm, mapa_satelital FROM trabajos_pdf WHERE id = ?",
            (job_id,),
        )
        fila = cursor.fetchone()
    except Exception:
        fila = None
    finally:
        conn.close()
    if not fila:
        return {}
    def _bytes(col):
        v = fila[col]
        if v is None:
            return None
        return bytes(v) if not isinstance(v, (bytes, bytearray)) else v
    return {
        "sombra_9am": _bytes("sombra_9am"),
        "sombra_3pm": _bytes("sombra_3pm"),
        "mapa_satelital": _bytes("mapa_satelital"),
    }


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


@app.post("/api/v1/listas/refrescar")
def refrescar_listas_screening(auth: dict = Depends(require_admin)):
    """Descarga y cachea en Neon las listas de screening (ONU/OFAC/UK). Solo admin.

    Por qué existe: en Vercel Hobby cada invocación tiene 60 s, y bajar ~54 MB de
    listas dentro de la generación del dictamen consumía todo el presupuesto
    (la función se mataba y el PDF nunca salía). Ejecutado APARTE —una vez al
    día, la caché dura 24 h— el screening del dictamen corre contra la caché y
    la generación se mantiene rápida.
    """
    try:
        from titulux_bridge import calentar_cache_listas
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Motor de listas no disponible: {e}")
    cache_dir = os.environ.get("ARHIA_LISTAS_CACHE") or (
        "/tmp/arhia_listas"
        if (os.environ.get("VERCEL") or not os.access(str(API_DIR), os.W_OK))
        else str(API_DIR / "assets" / "cache_listas")
    )
    return calentar_cache_listas(("onu", "ofac", "uk"), cache_dir=cache_dir, timeout=45)


@app.get("/api/v1/diagnostico/poi")
def diagnostico_poi(lat: float, lon: float, auth: dict = Depends(require_admin)):
    """Diagnóstico de las fuentes de POIs DESDE el entorno desplegado. Solo admin.

    Existe porque Overpass público bloquea/limita con frecuencia las IPs de
    DATACENTER (Vercel corre en AWS): una prueba desde una red residencial puede
    funcionar y produccion fallar igual. Este endpoint reporta, para las
    coordenadas dadas, el estado y el tiempo de cada espejo Overpass y del
    respaldo Photon, más el resultado real del motor de POIs.
    """
    import time as _t

    import requests as _rq
    from poi_engine import OVERPASS_ENDPOINTS, get_nearby_pois

    _consulta = (
        '[out:json][timeout:10];'
        f'node["amenity"="hospital"](around:500,{lat},{lon});'
        'out center 5;'
    )
    _ua = {"User-Agent": "ARHIAX-RE/1.0 (Sinergia Consulting Group)"}
    overpass = []
    for _url in OVERPASS_ENDPOINTS:
        _t0 = _t.time()
        try:
            _r = _rq.post(_url, data={"data": _consulta}, headers=_ua, timeout=15)
            overpass.append({
                "espejo": _url, "http": _r.status_code,
                "segundos": round(_t.time() - _t0, 1),
                "elementos": len((_r.json() or {}).get("elements", []))
                if _r.status_code == 200 else None,
            })
        except Exception as _e:  # noqa: BLE001
            overpass.append({"espejo": _url, "http": None,
                             "segundos": round(_t.time() - _t0, 1),
                             "error": str(_e)[:80]})

    _tp = _t.time()
    try:
        _rp = _rq.get("https://photon.komoot.io/api/", params={
            "q": "hospital", "lat": lat, "lon": lon, "limit": 3,
            "osm_tag": "amenity:hospital"}, headers=_ua, timeout=15)
        photon = {"http": _rp.status_code, "segundos": round(_t.time() - _tp, 1),
                  "features": len((_rp.json() or {}).get("features", []))}
    except Exception as _e2:  # noqa: BLE001
        photon = {"error": str(_e2)[:80], "segundos": round(_t.time() - _tp, 1)}

    _tm = _t.time()
    _pois = get_nearby_pois(lat, lon, radius=2000)
    return {
        "coordenadas": {"lat": lat, "lon": lon},
        "overpass": overpass,
        "photon_respaldo": photon,
        "motor_poi": {
            "segundos": round(_t.time() - _tm, 1),
            "total": sum(len(v) for v in _pois.values()),
            "por_categoria": {k: len(v) for k, v in _pois.items()},
        },
    }


def _verificar_firma_qstash(request: Request, body_bytes: bytes) -> bool:
    """Valida el JWT del header 'Upstash-Signature' (QStash v2 firma con JWT HS256
    usando la signing key del workspace)."""
    import base64 as _b64
    import json as _json
    import time as _t
    firma_header = request.headers.get("upstash-signature", "").strip()
    if not firma_header:
        return False
    claves = [
        os.environ.get("QSTASH_CURRENT_SIGNING_KEY", "").strip(),
        os.environ.get("QSTASH_NEXT_SIGNING_KEY", "").strip(),
    ]
    claves = [k for k in claves if k]
    if not claves:
        return False
    partes = firma_header.split(".")
    if len(partes) != 3:
        return False

    def _b64d(s: str) -> bytes:
        s = s.replace("-", "+").replace("_", "/")
        s += "=" * (-len(s) % 4)
        return _b64.b64decode(s)

    for clave in claves:
        try:
            firma = _b64d(partes[2])
            esperada = hmac.new(clave.encode("utf-8"),
                                f"{partes[0]}.{partes[1]}".encode("utf-8"),
                                hashlib.sha256).digest()
            if not hmac.compare_digest(firma, esperada):
                continue
            payload = _json.loads(_b64d(partes[1]))
            # La firma HS256 con la signing key ya autentica a QStash.
            # Solo rechazamos tokens expirados (si el claim existe).
            if payload.get("exp") and _t.time() > payload["exp"]:
                return False
            return True
        except Exception:
            continue
    return False


@app.post("/api/v1/pdf/worker")
async def worker_generar_pdf(request: Request):
    """Worker de la cola: compila el PDF del job y lo guarda en Neon.

    Autenticación: firma válida de QStash (Upstash-Signature) o Bearer de la app.
    Recibe JSON: {job_id, folio_matricula, direccion, area, barrio, certificado_b64?}.
    """
    import json as _json
    body_bytes = await request.body()
    if not _verificar_firma_qstash(request, body_bytes):
        # Fallback: token Bearer de la aplicación
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Sesión inválida o expirada. Inicie sesión nuevamente.")
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=auth_header[7:].strip())
        require_auth(creds)
    try:
        payload = _json.loads(body_bytes.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Body JSON inválido.")

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

    # Recuperar los insumos gráficos persistidos para el job (imágenes de ArcGIS
    # Online/mapa subidas por el usuario): el worker las escribe en temp_run_dir
    # para que compile_pdf las incruste como figuras reales.
    adjuntos = _leer_adjuntos_job(job_id)
    for nombre_img, contenido in (("sombra_9am", adjuntos.get("sombra_9am")),
                                  ("sombra_3pm", adjuntos.get("sombra_3pm")),
                                  ("mapa_satelital", adjuntos.get("mapa_satelital"))):
        if contenido:
            try:
                (temp_run_dir / f"{nombre_img}.png").write_bytes(contenido)
                print(f"[WORKER] adjunto {nombre_img}.png recuperado ({len(contenido)} bytes)")
            except Exception as e:
                print(f"[WORKER][WARN] no se pudo escribir adjunto {nombre_img}: {e}")

    folio = payload.get("folio_matricula")
    direccion = payload.get("direccion") or "Pendiente"
    area = float(payload.get("area") or 0)
    barrio = payload.get("barrio") or ""
    # Ciudad pendiente (Cali) -> job en error con mensaje claro; nunca se
    # compila un dictamen de una ciudad con datos de otra.
    try:
        ciudad = _normalizar_ciudad(payload.get("ciudad"))
    except HTTPException as _e_ciudad:
        _actualizar_trabajo(job_id, "error", error=str(_e_ciudad.detail)[:300])
        raise HTTPException(status_code=400, detail=str(_e_ciudad.detail))
    _ctl_adjuntado = bool(certificado_bytes)

    _cert_path = None
    _extra_lat = None
    _extra_lon = None
    if certificado_bytes:
        cert_path = temp_run_dir / "certificado.pdf"
        cert_path.write_bytes(certificado_bytes)
        _cert_path = str(cert_path)
        try:
            extraidos = extraer_datos_de_pdf(_cert_path, ciudad=ciudad)
            if not area and extraidos.get("area"):
                area = extraidos["area"]
            if (not folio or folio == "Pendiente") and extraidos.get("folio"):
                folio = extraidos["folio"]
            if (not direccion or direccion == "Pendiente") and extraidos.get("direccion"):
                direccion = extraidos["direccion"]
            if not barrio and extraidos.get("barrio"):
                barrio = extraidos["barrio"]
            _extra_lat = extraidos.get("lat")
            _extra_lon = extraidos.get("lon")
        except Exception:
            pass

    # Mejora 5: licencia de construcción (b64 en el payload del job)
    _lic_path = None
    licencia_b64 = payload.get("licencia_b64")
    if licencia_b64:
        try:
            lic_bytes = base64.b64decode(licencia_b64)
            if lic_bytes[:4] == b"%PDF":
                _lic_p = temp_run_dir / "licencia.pdf"
                _lic_p.write_bytes(lic_bytes)
                _lic_path = str(_lic_p)
        except Exception as e:
            print(f"[WORKER][WARN] licencia no recuperable: {e}")

    if not barrio:
        # Con CTL nunca se afirma el barrio de demostración (compile_pdf lo deja
        # PENDIENTE o lo resuelve por código catastral). Sin CTL: caso demo legado.
        if not _ctl_adjuntado:
            barrio = "Miramar" if ciudad == "barranquilla" else ""
        else:
            barrio = ""
    if area is None or area < 0:
        area = 0.0

    valor_m2 = 6887625 if "miramar" in barrio.lower() else 5146666
    db_record = {
        "id": 9999,
        "folio_matricula": _sanitizar_folio(folio) or "Pendiente",
        "direccion": direccion or "Pendiente",
        "barrio": barrio,
        "ciudad": ciudad,
        "estrato": 4,
        "area": area,
        "valor_consolidado": int(round(valor_m2 * area, -4)),
        "sombra_9am_cargada": 0,
        "sombra_3pm_cargada": 0,
        "mapa_cargado": 0,
        "acreedor_real": None,
        "certificado_path": _cert_path,
        "licencia_path": _lic_path,
        "lat": _extra_lat,
        "lon": _extra_lon,
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
    # Versionado de plataforma (matriz de versiones + SHA de git) — observable
    # por API para auditar qué código está desplegado.
    try:
        from versioning import version_blob
        _versiones = version_blob()
    except Exception as e:
        _versiones = {"error": str(e)[:120]}
    return {
        "api": "ARHIAX RE",
        "version": _versiones.get("ARHIAX_RE_VERSION", "2026.09"),
        "versionado": _versiones,
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

@app.get("/api/v1/pdf/trabajos")
def listar_trabajos_pdf(auth: dict = Depends(require_admin)):
    """Lista los trabajos asíncronos de PDF (monitoreo, solo admin)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, estado, error, creado FROM trabajos_pdf ORDER BY creado DESC LIMIT 50")
    filas = cursor.fetchall()
    conn.close()
    return {"trabajos": [dict(f) for f in filas]}

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

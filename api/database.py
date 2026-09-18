import sqlite3
import os


def _resolver_db_path():
    """Resuelve la ubicación/dsn de la base de datos (backlog: persistencia gestionada).

    Prioridad:
      1. ARHIAX_DB_PATH (variable de entorno): ruta local, `file:` de SQLite o
         URL de Postgres/Neon (postgres:// o postgresql://).
      2. Entorno Vercel: /tmp/database.db (efímero por instancia).
      3. Desarrollo local: api/database.db.

    Para Postgres/Neon: definir ARHIAX_DB_PATH con la URL de conexión y añadir
    `psycopg[binary]` a requirements.txt (el adaptador api/postgres_adapter.py
    traduce la API sqlite3 de la app a Postgres).
    """
    dsn = os.environ.get("ARHIAX_DB_PATH", "").strip()
    if dsn:
        return dsn

    API_DIR = os.path.dirname(os.path.abspath(__file__))
    if os.environ.get("VERCEL") or not os.access(API_DIR, os.W_OK):
        return "/tmp/database.db"
    return os.path.join(API_DIR, "database.db")


DB_PATH = _resolver_db_path()
_ES_POSTGRES = DB_PATH.startswith(("postgres://", "postgresql://"))


def init_db_on(conn):
    """Crea el esquema base SQLite sobre una conexión ya abierta (idempotente)."""
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dictamenes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folio_matricula TEXT NOT NULL,
            direccion TEXT NOT NULL,
            barrio TEXT NOT NULL,
            estrato INTEGER NOT NULL,
            area REAL,
            estado TEXT NOT NULL,
            valor_consolidado INTEGER,
            fecha_creacion TEXT NOT NULL,
            sombra_9am_cargada INTEGER DEFAULT 0,
            sombra_3pm_cargada INTEGER DEFAULT 0,
            mapa_cargado INTEGER DEFAULT 0,
            pdf_path TEXT
        )
    """)

    migraciones = [
        "ALTER TABLE dictamenes ADD COLUMN certificado_cargado INTEGER DEFAULT 0",
        "ALTER TABLE dictamenes ADD COLUMN certificado_path TEXT",
        "ALTER TABLE dictamenes ADD COLUMN lat REAL",
        "ALTER TABLE dictamenes ADD COLUMN lon REAL",
        "ALTER TABLE dictamenes ADD COLUMN fuente_geocod TEXT",
        "ALTER TABLE dictamenes ADD COLUMN acreedor_real TEXT",
        # Persistencia multi-ciudad: sin esta columna un caso de Bogotá/Medellín
        # guardado en Neon se recargaba como 'barranquilla' (la lista del portal
        # sincroniza con el servidor y usa c.ciudad para generar el dictamen).
        "ALTER TABLE dictamenes ADD COLUMN ciudad TEXT",
    ]
    for sql in migraciones:
        try:
            cursor.execute(sql)
        except sqlite3.OperationalError:
            pass

    # Tabla de trabajos asíncronos (cola PDF): persiste con Neon si ARHIAX_DB_PATH
    # apunta a Postgres; en SQLite /tmp (Vercel) es efímera.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trabajos_pdf (
            id TEXT PRIMARY KEY,
            estado TEXT NOT NULL,
            pdf BLOB,
            error TEXT,
            creado TEXT NOT NULL
        )
    """)
    # Insumos adjuntos del job (imágenes de ArcGIS Online / mapa): se persisten en
    # la BD para que el worker QStash las recupere por job_id (QStash no admite
    # PNG grandes en el payload). SQLite no tiene ADD COLUMN IF NOT EXISTS.
    for col in ("sombra_9am", "sombra_3pm", "mapa_satelital"):
        try:
            cursor.execute(f"ALTER TABLE trabajos_pdf ADD COLUMN {col} BLOB")
        except sqlite3.OperationalError:
            pass

    # Documentos SARLAFT / debida diligencia adjuntos al caso (subidos por el
    # usuario: UIAF, UE, PEP, extracto hipotecario, etc.).
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documentos_caso (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER NOT NULL,
            nombre TEXT NOT NULL,
            tipo TEXT NOT NULL,
            contenido BLOB,
            creado TEXT NOT NULL
        )
    """)

    conn.commit()


def init_db():
    """Crea/migra el esquema SQLite (solo para DSN local o /tmp). Retenido por
    compatibilidad (tests); el flujo normal usa `migrations.ensure_migrated`."""
    conn = sqlite3.connect(str(DB_PATH))
    try:
        init_db_on(conn)
    finally:
        conn.close()


def get_db_connection():
    """Devuelve una conexión con API compatible sqlite3 (dict rows).

    - DSN postgres (Neon): despacha a api/postgres_adapter (psycopg).
    - En otro caso: SQLite local o /tmp.

    El esquema se garantiza vía migraciones versionadas (migrations.ensure_migrated),
    ejecutadas UNA vez por DSN/proceso — no DDL en cada conexión normal.
    """
    if _ES_POSTGRES:
        from postgres_adapter import conectar_postgres
        conn = conectar_postgres(DB_PATH)
    else:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row

    from migrations import ensure_migrated
    ensure_migrated(conn)
    return conn

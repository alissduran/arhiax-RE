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


def init_db():
    """Crea/migra el esquema SQLite (solo para DSN local o /tmp)."""
    conn = sqlite3.connect(str(DB_PATH))
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

    conn.commit()
    conn.close()


def get_db_connection():
    """Devuelve una conexión con API compatible sqlite3 (dict rows).

    - DSN postgres (Neon): despacha a api/postgres_adapter (psycopg).
    - En otro caso: SQLite local o /tmp.
    """
    if _ES_POSTGRES:
        from postgres_adapter import conectar_postgres, init_postgres
        conn = conectar_postgres(DB_PATH)
        init_postgres(conn)
        return conn

    init_db()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

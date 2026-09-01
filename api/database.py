import sqlite3
import os
from pathlib import Path


def _resolver_db_path():
    """Resuelve la ubicación de la base de datos (backlog: persistencia gestionada).

    Prioridad:
      1. ARHIAX_DB_PATH (variable de entorno): ruta local o `file:` de SQLite.
         Si apunta a un esquema externo (postgres://, libsql://, wss://) se lanza
         un error claro: ese soporte requiere un driver adicional y el adaptador
         correspondiente en get_db_connection() (ver README).
      2. Entorno Vercel: /tmp/database.db (efímero por instancia — se pierde entre
         cold starts; usar ARHIAX_DB_PATH con un volumen persistente para datos reales).
      3. Desarrollo local: api/database.db.
    """
    dsn = os.environ.get("ARHIAX_DB_PATH", "").strip()
    if dsn:
        if dsn.startswith(("postgres://", "postgresql://", "libsql://", "wss://", "turso://")):
            raise RuntimeError(
                "ARHIAX_DB_PATH usa un esquema externo no soportado por este build (solo SQLite). "
                "Para conectar Turso/Postgres: instale el driver (libsql-experimental/psycopg) y "
                "ajuste get_db_connection() para despachar por esquema (ver README_PLAN -> backlog)."
            )
        return dsn

    API_DIR = os.path.dirname(os.path.abspath(__file__))
    if os.environ.get("VERCEL") or not os.access(API_DIR, os.W_OK):
        return "/tmp/database.db"
    return os.path.join(API_DIR, "database.db")


DB_PATH = _resolver_db_path()


def init_db():
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    # Crear tabla si no existe
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
    
    # Migración: Agregar columnas de Certificado de Libertad y Tradición si no existen
    try:
        cursor.execute("ALTER TABLE dictamenes ADD COLUMN certificado_cargado INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
        
    try:
        cursor.execute("ALTER TABLE dictamenes ADD COLUMN certificado_path TEXT")
    except sqlite3.OperationalError:
        pass

    # Migracion: Coordenadas geocodificadas universales (geocoder ARHIAX RE)
    try:
        cursor.execute("ALTER TABLE dictamenes ADD COLUMN lat REAL")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE dictamenes ADD COLUMN lon REAL")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE dictamenes ADD COLUMN fuente_geocod TEXT")
    except sqlite3.OperationalError:
        pass

    # Migracion Sprint 2 Bloque D: acreedor real declarado
    try:
        cursor.execute("ALTER TABLE dictamenes ADD COLUMN acreedor_real TEXT")
    except sqlite3.OperationalError:
        pass
        
    conn.commit()
    conn.close()


def get_db_connection():
    # Nota (backlog persistencia gestionada): para despachar por esquema externo
    # (Turso libsql / Postgres Neon) añadir aquí el branch según DB_PATH y el driver.
    init_db()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

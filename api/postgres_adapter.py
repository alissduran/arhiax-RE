# -*- coding: utf-8 -*-
"""
ARHIAX RE — Adaptador de compatibilidad PostgreSQL (Neon)

Permite que la aplicación (escrita contra sqlite3) funcione sobre Postgres sin
reescribir los endpoints, traduciendo en caliente:
  - Placeholders '?'  -> '%s' (las queries de la app solo usan '?' para parámetros)
  - cursor.lastrowid  -> captura de RETURNING id en INSERT
  - init de esquema   -> CREATE TABLE / ADD COLUMN IF NOT EXISTS (Postgres nativo)

Uso (en database.get_db_connection):
    conn = conectar_postgres(ARHIAX_DB_PATH)  # psycopg (v3) obligatorio

NOTA: psycopg se importa solo cuando el DSN es postgres; si no está instalado
se lanza un error claro con la instrucción de instalación.
"""

from __future__ import annotations

from typing import Any, Optional


def conectar_postgres(dsn: str):
    """Conecta a Postgres/Neon y devuelve un objeto con API compatible sqlite3."""
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as e:
        raise RuntimeError(
            "Para usar Neon/Postgres instale el driver: pip install 'psycopg[binary]' "
            "(y añádalo a requirements.txt). Luego defina ARHIAX_DB_PATH con la URL de conexión."
        ) from e

    conn = psycopg.connect(dsn, row_factory=dict_row)
    return _ConnCompat(conn)


class _CursorCompat:
    """Envuelve un cursor psycopg con API estilo sqlite3 (? -> %s, lastrowid)."""

    def __init__(self, cursor):
        self._c = cursor
        self.lastrowid: Optional[int] = None

    def _traducir(self, sql: str, params):
        sql_t = sql.replace("?", "%s") if "?" in sql else sql
        es_insert = sql_t.lstrip().upper().startswith("INSERT")
        if es_insert:
            sql_t = sql_t.rstrip().rstrip(";") + " RETURNING id"
        if params is None:
            self._c.execute(sql_t)
        else:
            if not isinstance(params, (tuple, list)):
                params = (params,)
            self._c.execute(sql_t, params)
        if es_insert:
            fila = self._c.fetchone()
            self.lastrowid = fila["id"] if fila and isinstance(fila, dict) else (fila[0] if fila else None)
        return self

    def execute(self, sql: str, params=None):
        return self._traducir(sql, params)

    def executemany(self, sql: str, seq_params):
        for p in seq_params:
            self._traducir(sql, p)
        return self

    def fetchall(self):
        return self._c.fetchall()

    def fetchone(self):
        return self._c.fetchone()

    def __getattr__(self, name):
        return getattr(self._c, name)


class _ConnCompat:
    """Envuelve una conexión psycopg con API compatible sqlite3."""

    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        return _CursorCompat(self._conn.cursor())

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def execute(self, sql: str, params=None):
        cur = self.cursor()
        cur.execute(sql, params)
        return cur

    def __getattr__(self, name):
        return getattr(self._conn, name)


def init_postgres(conn) -> None:
    """Crea el esquema en Postgres (CREATE TABLE / ADD COLUMN IF NOT EXISTS)."""
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS dictamenes (
            id SERIAL PRIMARY KEY,
            folio_matricula TEXT NOT NULL,
            direccion TEXT NOT NULL,
            barrio TEXT NOT NULL,
            estrato INTEGER NOT NULL,
            area REAL,
            estado TEXT NOT NULL,
            valor_consolidado BIGINT,
            fecha_creacion TEXT NOT NULL,
            sombra_9am_cargada INTEGER DEFAULT 0,
            sombra_3pm_cargada INTEGER DEFAULT 0,
            mapa_cargado INTEGER DEFAULT 0,
            pdf_path TEXT
        )
    """)
    columnas = {
        "certificado_cargado": "INTEGER DEFAULT 0",
        "certificado_path": "TEXT",
        "lat": "REAL",
        "lon": "REAL",
        "fuente_geocod": "TEXT",
        "acreedor_real": "TEXT",
        "ciudad": "TEXT",  # persistencia multi-ciudad (Neon)
    }
    for nombre, tipo in columnas.items():
        cur.execute(f"ALTER TABLE dictamenes ADD COLUMN IF NOT EXISTS {nombre} {tipo}")

    # Tabla de trabajos asíncronos (cola PDF) — persiste en Neon.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS trabajos_pdf (
            id TEXT PRIMARY KEY,
            estado TEXT NOT NULL,
            pdf BYTEA,
            error TEXT,
            creado TEXT NOT NULL
        )
    """)
    # Insumos adjuntos del job: imágenes ArcGIS/mapa en BYTEA para que el worker
    # QStash las recupere por job_id (no viajan en el payload de la cola).
    for col in ("sombra_9am", "sombra_3pm", "mapa_satelital"):
        cur.execute(f"ALTER TABLE trabajos_pdf ADD COLUMN IF NOT EXISTS {col} BYTEA")

    # Documentos SARLAFT / debida diligencia adjuntos al caso (subidos por el
    # usuario: UIAF, UE, PEP, extracto hipotecario, etc.).
    cur.execute("""
        CREATE TABLE IF NOT EXISTS documentos_caso (
            id SERIAL PRIMARY KEY,
            case_id INTEGER NOT NULL,
            nombre TEXT NOT NULL,
            tipo TEXT NOT NULL,
            contenido BYTEA,
            creado TEXT NOT NULL
        )
    """)
    conn.commit()

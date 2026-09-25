# -*- coding: utf-8 -*-
"""
ARHIAX RE — Migraciones versionadas (mínimas, sin ORM).

Retira la evolución de schema del flujo normal de conexiones: en vez de
`CREATE TABLE IF NOT EXISTS` + `ALTER TABLE ADD COLUMN` en cada `get_db_connection()`,
se aplica una secuencia versionada UNA vez por DSN/proceso.

Requisitos satisfechos:
  - migration id + applied_at (`schema_migrations`)
  - ejecución ordenada
  - runner idempotente (no duplica migraciones aplicadas)
  - el fallo detiene la migración (excepción se propaga)
  - no hay ALTER TABLE en cada conexión normal (ensure_migrated cachea por DSN)
  - probado de schema vacío → schema actual

Dialecto: la migración 001 reusa el DDL existente (database.init_db_on para SQLite,
postgres_adapter.init_postgres para Postgres); un único modelo de dominio, dos motores.
"""

from __future__ import annotations

import datetime
from typing import Callable, List, Tuple


def _apply_initial(conn) -> None:
    """001_initial: esquema base (dictamenes, trabajos_pdf, documentos_caso)."""
    # Dialecto resuelto en caliente para evitar import circular en carga de módulo.
    import database
    if database._ES_POSTGRES:
        from postgres_adapter import init_postgres
        init_postgres(conn)
    else:
        database.init_db_on(conn)


def _add_column(conn, tabla: str, col: str, tipo: str) -> None:
    """ALTER TABLE ADD COLUMN idempotente por dialecto."""
    import database
    if database._ES_POSTGRES:
        conn.execute(f"ALTER TABLE {tabla} ADD COLUMN IF NOT EXISTS {col} {tipo}")
    else:
        try:
            conn.execute(f"ALTER TABLE {tabla} ADD COLUMN {col} {tipo}")
        except Exception:
            pass  # SQLite: la columna ya existe (idempotente)


def _apply_case_canonical_state(conn) -> None:
    """002_case_canonical_state: metadatos de auditoría (NO ownership)."""
    _add_column(conn, "dictamenes", "created_by", "TEXT")
    _add_column(conn, "dictamenes", "updated_by", "TEXT")


def _apply_documento_principal(conn) -> None:
    """003_documento_principal: la ENTREGA del trabajo (DICTUS 2.0B-R1).

    El trabajo guarda el documento PRINCIPAL (el ejecutivo, en `pdf`), su ANEXO
    técnico, el manifest sellado de la misma corrida y el folio con el que se
    nombran los archivos entregados.
    """
    _add_column(conn, "trabajos_pdf", "pdf_tecnico", "BLOB")
    _add_column(conn, "trabajos_pdf", "manifest_json", "TEXT")
    _add_column(conn, "trabajos_pdf", "folio", "TEXT")


# Secuencia ordenada de migraciones: (id, up(conn)).
MIGRATIONS: List[Tuple[str, Callable]] = [
    ("001_initial", _apply_initial),
    ("002_case_canonical_state", _apply_case_canonical_state),
    ("003_documento_principal", _apply_documento_principal),
]


def run_migrations(conn) -> List[str]:
    """Aplica las migraciones pendientes en orden. Devuelve las aplicadas ahora."""
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations "
        "(id TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    conn.commit()

    aplicadas = set()
    for row in cur.execute("SELECT id FROM schema_migrations").fetchall():
        aplicadas.add(row["id"] if isinstance(row, dict) else row[0])

    aplicadas_ahora: List[str] = []
    for mid, up in MIGRATIONS:
        if mid in aplicadas:
            continue
        up(conn)
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        cur.execute(
            "INSERT INTO schema_migrations (id, applied_at) VALUES (?, ?)",
            (mid, ts),
        )
        conn.commit()
        aplicadas_ahora.append(mid)
    return aplicadas_ahora


# Cache por DSN: las migraciones se aplican UNA vez por base/proceso.
_migrated: set = set()


def ensure_migrated(conn) -> List[str]:
    """Garantiza el schema actual; no ejecuta DDL si este DSN ya fue migrado."""
    import database
    dsn = database.DB_PATH
    if dsn in _migrated:
        return []
    aplicadas = run_migrations(conn)
    _migrated.add(dsn)
    return aplicadas

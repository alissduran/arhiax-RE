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


def _tipo_binario() -> str:
    """Tipo de la columna BINARIA en el dialecto en uso.

    SQLite no conoce `BYTEA` y PostgreSQL no conoce `BLOB`: el tipo se declara por
    dialecto. Un `BLOB` enviado a Postgres no es un tipo «aproximado», es un error
    DDL (`type "blob" does not exist`) que aborta la migración y, con ella, TODA
    conexión de la aplicación (el incidente de producción 2.0B-R1.1).
    """
    import database
    return "BYTEA" if database._ES_POSTGRES else "BLOB"


def _normalizar_tipo(tipo: str) -> str:
    """Traduce el tipo lógico al dialecto. Regla ÚNICA, idempotente.

    Es la red de seguridad del runner: aunque una migración futura declare `BLOB`
    pensando en SQLite, en Postgres se emitirá `BYTEA`. No hay dos reglas distintas:
    `BLOB` y `BYTEA` se traducen al tipo binario del dialecto.
    """
    import database
    t = str(tipo).strip().upper()
    if t in ("BLOB", "BYTEA"):
        return _tipo_binario()
    if database._ES_POSTGRES and t in ("INTEGER PRIMARY KEY AUTOINCREMENT", "DATETIME"):
        # Tipos que la app usa en SQLite y que no existen con ese nombre en Postgres.
        return {"INTEGER PRIMARY KEY AUTOINCREMENT": "SERIAL PRIMARY KEY",
                "DATETIME": "TIMESTAMP"}[t]
    return t


def _add_column(conn, tabla: str, col: str, tipo: str) -> None:
    """ALTER TABLE ADD COLUMN idempotente por dialecto."""
    import database
    tipo = _normalizar_tipo(tipo)
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

    El tipo binario se declara POR DIALECTO (`BYTEA` en Postgres/Neon, `BLOB` en
    SQLite): la migración corre igual en la base local y en Neon.
    """
    _add_column(conn, "trabajos_pdf", "pdf_tecnico", _tipo_binario())
    _add_column(conn, "trabajos_pdf", "manifest_json", "TEXT")
    _add_column(conn, "trabajos_pdf", "folio", "TEXT")


# Secuencia ordenada de migraciones: (id, up(conn)).
MIGRATIONS: List[Tuple[str, Callable]] = [
    ("001_initial", _apply_initial),
    ("002_case_canonical_state", _apply_case_canonical_state),
    ("003_documento_principal", _apply_documento_principal),
]


def _rollback_silencioso(conn) -> None:
    """Deja la conexión UTILIZABLE tras un DDL fallido.

    En Postgres un error DDL aborta la transacción: sin rollback, cualquier comando
    posterior falla con «current transaction is aborted» y el fallo se propaga a todo
    el proceso. La aplicación volvía a intentar la migración en cada petición.
    """
    try:
        conn.rollback()
    except Exception:  # noqa: BLE001 — el rollback del limpiador nunca enmascara el fallo real
        pass


def run_migrations(conn) -> List[str]:
    """Aplica las migraciones pendientes en orden. Devuelve las aplicadas ahora.

    Garantía: una migración se registra en `schema_migrations` SOLO si TODOS sus
    pasos terminaron bien. Si falla, se hace rollback (la migración queda pendiente
    y el schema intacto) y la excepción se propaga: nunca se declara aplicada una
    migración que no lo está.
    """
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
        try:
            up(conn)
            ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
            cur.execute(
                "INSERT INTO schema_migrations (id, applied_at) VALUES (?, ?)",
                (mid, ts),
            )
            conn.commit()
        except Exception:
            # Fallo DDL: se deshace lo que la migración alcanzó a escribir y NO se
            # registra como aplicada (se reintentará cuando el fallo esté resuelto).
            _rollback_silencioso(conn)
            raise
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

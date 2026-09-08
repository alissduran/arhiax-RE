# -*- coding: utf-8 -*-
"""
ARHIAX RE — Caché persistente de listas restrictivas (Neon/Postgres)

Evita re-descargar ONU/OFAC/UK (~54 MB en total) en cada generación de dictamen
en Vercel: la primera descarga (o la ingesta manual de UE) se persiste en la
base Neon y las siguientes generaciones la leen desde ahí (TTL 24 h, porque las
listas sancionatorias se refrescan a diario).

Solo opera cuando la base es Postgres/Neon (ARHIAX_DB_PATH = postgres://...).
En SQLite local (desarrollo/tests) o sin BD, las funciones degradan sin lanzar:
`leer_todas` devuelve {} y `escribir_todas` es un no-op. El screening cae al
flujo normal (descarga en vivo + caché en disco).

Regla de honestidad: solo se persisten fuentes con estado OPERATIVA (datos
reales descargados/ingeridos). Las fuentes de muestra (SYNTHETIC_TEST_FIXTURE)
nunca se guardan como si fueran vinculantes.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional, Tuple

_TTL = 24 * 3600  # 24 horas


def _es_postgres() -> bool:
    try:
        from database import DB_PATH
        return bool(DB_PATH) and str(DB_PATH).startswith(("postgres://", "postgresql://"))
    except Exception:
        return False


def _conn():
    from database import get_db_connection
    conn = get_db_connection()
    _crear_tabla(conn)
    return conn


def _crear_tabla(conn) -> None:
    ddl = (
        "CREATE TABLE IF NOT EXISTS listas_cache ("
        "id SERIAL PRIMARY KEY, "
        "fuente TEXT UNIQUE NOT NULL, "
        "meta TEXT NOT NULL, "
        "registros TEXT NOT NULL, "
        "actualizado_en DOUBLE PRECISION NOT NULL)"
    )
    try:
        conn.execute(ddl)
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass


def _lista_desde_dict(d: Dict[str, Any]):
    from arhia_sag_screen.contracts import ListaVersion
    return ListaVersion(
        fuente=d.get("fuente", ""), nombre=d.get("nombre", ""), url=d.get("url", ""),
        formato=d.get("formato", ""), fecha_emision=(d.get("fecha_emision") or d.get("fechaEmision") or ""),
        version=d.get("version", ""), hash=d.get("hash", ""),
        licencia=d.get("licencia", "public"), registros=d.get("registros", 0),
        estado=d.get("estado", "OPERATIVA"), autoridad=d.get("autoridad", ""),
        metodo=d.get("metodo", ""), vigencia=d.get("vigencia", ""),
    )


def _registros_desde_dict(regs) -> list:
    from arhia_sag_screen.contracts import RegistroNormalizado
    out = []
    for r in regs:
        out.append(RegistroNormalizado(
            id=r.get("id", ""), nombre=r.get("nombre", ""),
            alias=tuple(r.get("alias", ())), tipo_documento=r.get("tipo_documento"),
            numero_documento=r.get("numero_documento"), fecha_nacimiento=r.get("fecha_nacimiento"),
            programas=tuple(r.get("programas", ())), fuente=r.get("fuente", ""),
            lista_version=r.get("lista_version", ""),
        ))
    return out


def _fila_a_dict(fila) -> Dict[str, Any]:
    """sqlite3.Row y dict (psycopg dict_row) soportan acceso por clave."""
    return {k: fila[k] for k in ("meta", "registros", "actualizado_en")}


def leer(fuente: str):
    """Devuelve (ListaVersion, registros) o None si no hay caché válida."""
    if not _es_postgres():
        return None
    try:
        conn = _conn()
        cur = conn.execute(
            "SELECT meta, registros, actualizado_en FROM listas_cache WHERE fuente = ?",
            (fuente,),
        )
        fila = cur.fetchone()
        conn.close()
        if not fila:
            return None
        d = _fila_a_dict(fila)
        if time.time() - float(d["actualizado_en"]) > _TTL:
            return None  # expirado: se re-descarga
        meta = json.loads(d["meta"])
        regs = json.loads(d["registros"])
        return (_lista_desde_dict(meta), _registros_desde_dict(regs))
    except Exception:
        return None


def escribir(fuente: str, lista, registros) -> None:
    """Persiste una lista OPERATIVA (descargada/ingerida) en Neon."""
    if not _es_postgres():
        return
    try:
        from dataclasses import asdict
        conn = _conn()
        meta = json.dumps(asdict(lista), ensure_ascii=False)
        regs = json.dumps([asdict(r) for r in registros], ensure_ascii=False)
        ts = time.time()
        conn.execute("DELETE FROM listas_cache WHERE fuente = ?", (fuente,))
        conn.execute(
            "INSERT INTO listas_cache (fuente, meta, registros, actualizado_en) "
            "VALUES (?, ?, ?, ?)",
            (fuente, meta, regs, ts),
        )
        conn.commit()
        conn.close()
    except Exception:
        try:
            conn.close()
        except Exception:
            pass


def leer_todas(fuentes) -> Dict[str, Tuple]:
    """Lee desde Neon las fuentes con caché válida. Devuelve {fuente: (lista, regs)}."""
    if not _es_postgres():
        return {}
    out = {}
    for f in fuentes:
        r = leer(f)
        if r is not None:
            out[f] = r
    return out


def escribir_todas(mapa: Dict[str, Tuple]) -> None:
    """Persiste en Neon varias fuentes {fuente: (ListaVersion, registros)}."""
    if not _es_postgres():
        return
    for f, (lista, regs) in mapa.items():
        escribir(f, lista, regs)

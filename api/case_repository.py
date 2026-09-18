# -*- coding: utf-8 -*-
"""
ARHIAX RE — CaseRepository (frontera de persistencia del Case, sin ORM).

Encapsula el acceso a la tabla `dictamenes` (insert/get/list/update/delete) y el
mapping DB → Case. Es la ÚNICA frontera de almacenamiento del Case; los endpoints
y el CaseService no escriben SQL de Case directamente.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import database


def _conn():
    """Conexión vía database.get_db_connection (lookup dinámico, testeable)."""
    return database.get_db_connection()

# Columnas que un UPDATE de Case puede modificar (whitelist).
_UPDATEABLE = {
    "folio_matricula", "direccion", "barrio", "estrato", "area", "estado",
    "valor_consolidado", "ciudad", "acreedor_real", "created_by", "updated_by",
}

# Columnas de auditoría que el servicio escribe (metadata, NO ownership).
_AUDIT = ("created_by", "updated_by")


def _row_to_case(row) -> Optional[Dict[str, Any]]:
    """Convierte una fila DB en el dict Case. No expone rutas internas (F-13)."""
    if row is None:
        return None
    d = dict(row)
    d.pop("pdf_path", None)
    d.pop("certificado_path", None)
    return d


class CaseRepository:
    """Persistencia del Case sobre `get_db_connection()` (SQLite o Postgres/Neon)."""

    def insert(self, *, folio_matricula: str, direccion: str, barrio: str,
               estrato: int, area: float, estado: str, valor_consolidado: int,
               fecha_creacion: str, ciudad: str, created_by: Optional[str] = None) -> int:
        conn = _conn()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO dictamenes (folio_matricula, direccion, barrio, estrato, area, "
                "estado, valor_consolidado, fecha_creacion, ciudad, created_by) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (folio_matricula, direccion, barrio, estrato, area, estado,
                 valor_consolidado, fecha_creacion, ciudad, created_by),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def get(self, case_id: int) -> Optional[Dict[str, Any]]:
        conn = _conn()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM dictamenes WHERE id = ?", (case_id,))
            return _row_to_case(cur.fetchone())
        finally:
            conn.close()

    def list(self) -> List[Dict[str, Any]]:
        conn = _conn()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM dictamenes ORDER BY id DESC")
            return [_row_to_case(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def update(self, case_id: int, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Actualiza SOLO las columnas permitidas y devuelve el Case actualizado."""
        updatable = {k: v for k, v in fields.items() if k in _UPDATEABLE}
        if not updatable:
            return self.get(case_id)
        conn = _conn()
        try:
            cur = conn.cursor()
            set_sql = ", ".join(f"{k} = ?" for k in updatable)
            params = list(updatable.values()) + [case_id]
            cur.execute(f"UPDATE dictamenes SET {set_sql} WHERE id = ?", params)
            conn.commit()
            cur.execute("SELECT * FROM dictamenes WHERE id = ?", (case_id,))
            return _row_to_case(cur.fetchone())
        finally:
            conn.close()

    def delete(self, case_id: int) -> bool:
        """Elimina el Case. Retorna True si existía (idempotente)."""
        conn = _conn()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM dictamenes WHERE id = ?", (case_id,))
            existe = cur.fetchone() is not None
            if existe:
                cur.execute("DELETE FROM dictamenes WHERE id = ?", (case_id,))
                conn.commit()
            return existe
        finally:
            conn.close()

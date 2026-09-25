# -*- coding: utf-8 -*-
"""Evidencia del hotfix: SQL que la migración 003 emite en cada dialecto.

No requiere servidor Postgres: captura el SQL que el runner enviaría a la conexión
(la traducción de dialecto es determinista y vive en un solo lugar).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))

import database          # noqa: E402
import migrations        # noqa: E402


class _Conn:
    def __init__(self):
        self.reg = []

    def cursor(self):
        reg = self.reg

        class _Cur:
            def execute(self, sql, params=None):
                reg.append(sql)
                return self

            def fetchall(self):
                return [{"id": "001_initial"}, {"id": "002_case_canonical_state"}]

            def fetchone(self):
                return None

        return _Cur()

    def execute(self, sql, params=None):
        self.reg.append(sql)
        return self.cursor()

    def commit(self):
        pass

    def rollback(self):
        pass


def main() -> int:
    for dialecto, es_postgres in (("POSTGRES/NEON", True), ("SQLITE", False)):
        database._ES_POSTGRES = es_postgres
        migrations._migrated.clear()
        conn = _Conn()
        aplicadas = migrations.run_migrations(conn)
        print("=" * 74)
        print(f"DIALECTO: {dialecto} · migraciones aplicadas: {aplicadas}")
        print("=" * 74)
        for sql in conn.reg:
            print("   ", sql)
        print()

    database._ES_POSTGRES = False
    print("ANTES DEL HOTFIX (defecto de producción, ya corregido):")
    print("    ALTER TABLE trabajos_pdf ADD COLUMN IF NOT EXISTS pdf_tecnico BLOB")
    print("    -> en Postgres: ERROR: type \"blob\" does not exist (UndefinedObject)")
    print("    -> abortaba ensure_migrated() dentro de get_db_connection():")
    print("       POST /api/dictamenes -> CaseRepository.insert() nunca llegaba a escribir.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

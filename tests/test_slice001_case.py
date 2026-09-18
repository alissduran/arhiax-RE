# -*- coding: utf-8 -*-
"""
SLICE-001 — Canonical Case Persistence.

Verifica que el Case vive en la BD (canonical) y que el CRUD pasa por
CaseService/CaseRepository, con migraciones versionadas e idempotentes.
Sin red.
"""
import importlib
import inspect
import os
import shutil
import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = ROOT / "api"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(API))

TMP = ROOT / "tmp_slice001"
_OLD_DB_PATH = None


def setUpModule():
    global _OLD_DB_PATH
    shutil.rmtree(TMP, ignore_errors=True)
    TMP.mkdir(parents=True, exist_ok=True)
    _OLD_DB_PATH = os.environ.get("ARHIAX_DB_PATH")


def tearDownModule():
    if _OLD_DB_PATH is None:
        os.environ.pop("ARHIAX_DB_PATH", None)
    else:
        os.environ["ARHIAX_DB_PATH"] = _OLD_DB_PATH
    import database
    import migrations
    importlib.reload(database)
    migrations._migrated.clear()
    shutil.rmtree(TMP, ignore_errors=True)


def _fresh_db(name):
    """Apunta la BD a un SQLite temporal y reinicia el cache de migraciones."""
    db = TMP / name
    if db.exists():
        db.unlink()
    os.environ["ARHIAX_DB_PATH"] = str(db)
    import database
    import migrations
    importlib.reload(database)
    migrations._migrated.clear()
    return db


class TestCaseCRUD(unittest.TestCase):

    def test_t1_create_persist_id(self):
        _fresh_db("t1.db")
        from case_service import create_case
        caso = create_case(folio_matricula="240-211101",
                           direccion="K 26 21 47 AP 101", ciudad="pasto")
        self.assertIsInstance(caso["id"], int)
        self.assertEqual(caso["folio_matricula"], "240-211101")
        self.assertEqual(caso["ciudad"], "pasto")
        self.assertEqual(caso["estado"], "PENDIENTE_IMAGENES")

    def test_t2_read_equivalent(self):
        _fresh_db("t2.db")
        from case_service import create_case, get_case
        c = create_case(folio_matricula="240-211101", direccion="K 26 21 47 AP 101",
                        ciudad="pasto")
        g = get_case(c["id"])
        self.assertEqual(g["folio_matricula"], c["folio_matricula"])
        self.assertEqual(g["direccion"], c["direccion"])
        self.assertEqual(g["ciudad"], c["ciudad"])

    def test_t3_update_persist(self):
        _fresh_db("t3.db")
        from case_service import create_case, update_case, get_case
        c = create_case(folio_matricula="240-1", direccion="X", ciudad="pasto")
        update_case(c["id"], {"folio_matricula": "240-2", "barrio": "Centro"})
        g = get_case(c["id"])
        self.assertEqual(g["folio_matricula"], "240-2")
        self.assertEqual(g["barrio"], "Centro")

    def test_t4_list(self):
        _fresh_db("t4.db")
        from case_service import create_case, list_cases
        create_case(folio_matricula="240-1", direccion="X")
        create_case(folio_matricula="240-2", direccion="Y")
        lista = list_cases()
        self.assertEqual(len(lista), 2)
        folios = {c["folio_matricula"] for c in lista}
        self.assertEqual(folios, {"240-1", "240-2"})

    def test_t5_reload_semantics_nueva_conexion(self):
        _fresh_db("t5.db")
        from case_service import create_case
        from case_repository import CaseRepository
        c = create_case(folio_matricula="240-211101", direccion="K 26 21 47 AP 101")
        # "Restart-equivalent": una conexión/distinta instancia del repo lee la misma BD.
        repo = CaseRepository()
        self.assertEqual(repo.get(c["id"])["folio_matricula"], "240-211101")

    def test_t6_auth_sigue_en_http(self):
        from fastapi.params import Depends
        import index
        for fn in (index.list_dictamenes, index.create_dictamen,
                   index.update_dictamen, index.delete_dictamen):
            p = inspect.signature(fn).parameters.get("auth")
            self.assertIsNotNone(p, f"{fn.__name__} debe declarar auth")
            self.assertIsInstance(p.default, Depends, f"{fn.__name__}: auth debe ser Depends")

    def test_t7_reconstruccion_conexion_cruda(self):
        _fresh_db("t7.db")
        from case_service import create_case
        cid = create_case(folio_matricula="240-1", direccion="X")["id"]
        conn = sqlite3.connect(str(TMP / "t7.db"))
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT folio_matricula FROM dictamenes WHERE id = ?", (cid,)).fetchone()
            self.assertEqual(row["folio_matricula"], "240-1")
        finally:
            conn.close()


class TestMigrations(unittest.TestCase):

    def _columnas(self, conn, tabla):
        cur = conn.cursor()
        cur.execute(f"PRAGMA table_info({tabla})")
        return {r[1] for r in cur.fetchall()}

    def test_t8_empty_to_current(self):
        _fresh_db("t8.db")
        import database
        import migrations
        conn = database.get_db_connection()
        try:
            self.assertIn("dictamenes", self._nombres_tablas(conn))
            self.assertIn("trabajos_pdf", self._nombres_tablas(conn))
            self.assertIn("documentos_caso", self._nombres_tablas(conn))
            self.assertIn("schema_migrations", self._nombres_tablas(conn))
            cols = self._columnas(conn, "dictamenes")
            self.assertIn("ciudad", cols)
            self.assertIn("created_by", cols)
            self.assertIn("updated_by", cols)
        finally:
            conn.close()

    def _nombres_tablas(self, conn):
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        return {r[0] for r in cur.fetchall()}

    def test_t9_idempotency(self):
        _fresh_db("t9.db")
        import database
        import migrations
        migrations._migrated.clear()
        conn = database.get_db_connection()  # aplica migraciones la primera vez
        aplicadas_ahora = migrations.run_migrations(conn)  # re-run: nada pendiente
        conn.close()
        self.assertEqual(aplicadas_ahora, [])
        # sin duplicados: schema_migrations registra exactamente una fila por migración
        conn2 = database.get_db_connection()
        try:
            cur = conn2.cursor()
            cur.execute("SELECT COUNT(*) AS n FROM schema_migrations")
            row = cur.fetchone()
            n = row["n"] if isinstance(row, dict) else row[0]
            self.assertEqual(n, len(migrations.MIGRATIONS))
        finally:
            conn2.close()


class TestEvidenceHmac(unittest.TestCase):

    def _limpiar(self):
        os.environ.pop("ARHIAX_EVIDENCE_HMAC_KEY", None)
        os.environ.pop("ARHIA_HMAC_KEY", None)
        os.environ.pop("VERCEL", None)
        os.environ.pop("ARHIAX_ENV", None)

    def test_hmac_estable(self):
        self._limpiar()
        from arhia_sag_screen.evidence import envelope
        k1 = envelope._key()
        k2 = envelope._key()
        self.assertEqual(k1, k2)  # estable, no aleatoria por proceso
        self.assertNotEqual(k1, "")  # sintética no vacía

    def test_hmac_desde_env(self):
        self._limpiar()
        from arhia_sag_screen.evidence import envelope
        os.environ["ARHIAX_EVIDENCE_HMAC_KEY"] = "test-evidence-key-xyz"
        try:
            self.assertEqual(envelope._key(), "test-evidence-key-xyz")
        finally:
            os.environ.pop("ARHIAX_EVIDENCE_HMAC_KEY", None)

    def test_hmac_fail_closed_prod(self):
        self._limpiar()
        from arhia_sag_screen.evidence import envelope
        os.environ["VERCEL"] = "1"
        try:
            with self.assertRaises(RuntimeError):
                envelope._key()
        finally:
            os.environ.pop("VERCEL", None)


if __name__ == "__main__":
    unittest.main()

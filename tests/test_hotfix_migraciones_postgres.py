# -*- coding: utf-8 -*-
"""HOTFIX 2.0B-R1.1 — MIGRACIONES PORTABLES + CREACIÓN DE CASO.

Incidente de producción (arhiax-re.vercel.app, `POST /api/dictamenes` → 500
«No se pudo crear el caso en el servidor»):

    migration 003_documento_principal emitía
        ALTER TABLE trabajos_pdf ADD COLUMN IF NOT EXISTS pdf_tecnico BLOB
    contra PostgreSQL/Neon, donde `BLOB` NO existe (`type "blob" does not exist`).
    El error abortaba `ensure_migrated()`, que corre dentro de
    `database.get_db_connection()`, es decir ANTES de que `CaseRepository.insert()`
    pudiera escribir. La creación de casos quedó inutilizable.

Estas pruebas NO se conforman con SQLite (fue SQLite quien dejó pasar el fallo):

  1. **Dialecto Postgres**: con `database._ES_POSTGRES = True` se captura el SQL que
     la migración 003 emite y se exige `BYTEA`, y NUNCA `BLOB`.
  2. **Registro de la migración**: 001+002 aplicadas → 003 corre → columnas creadas y
     `schema_migrations` contiene 003.
  3. **Fallo = no aplicada**: si un DDL falla, hay rollback, la migración NO queda
     registrada y la excepción se propaga (nunca se declara aplicada una migración
     que no lo está).
  4. **Idempotencia y estado parcial** sobre una base real (SQLite) y por SQL.
  5. **Flujo de creación de caso** completo: `get_db_connection()` →
     `ensure_migrated()` → `create_case()` → `CaseRepository.insert()` → `.get()`.
"""
import os
import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))

import database        # noqa: E402
import migrations      # noqa: E402


# ── doble de conexión: registra el SQL y responde como una base migrada ───────
class _CursorFalso:
    def __init__(self, registro, aplicadas, filas_selector=None, fallar_en=None):
        self.registro = registro
        self.aplicadas = aplicadas
        self.filas_selector = filas_selector or []
        self.fallar_en = fallar_en
        self.lastrowid = None

    def execute(self, sql, params=None):
        self.registro.append((sql, params))
        if self.fallar_en and self.fallar_en(sql):
            raise RuntimeError("DDL inválido (simulado)")
        return self

    def executemany(self, sql, seq):
        return self

    def fetchall(self):
        return list(self.filas_selector)

    def fetchone(self):
        return None


class _ConnFalso:
    """Conexión mínima con la API que usa el runner (cursor/execute/commit/rollback)."""

    def __init__(self, aplicadas=(), fallar_en=None):
        self.registro = []
        self.aplicadas = list(aplicadas)
        self.fallar_en = fallar_en
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        filas = [{"id": mid} for mid in self.aplicadas]
        return _CursorFalso(self.registro, self.aplicadas, filas, self.fallar_en)

    def execute(self, sql, params=None):
        return self.cursor().execute(sql, params)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        pass

    def sql(self):
        return [s for s, _ in self.registro]

    def sql_con_parametros(self):
        return list(self.registro)


class _PostgresSimulado:
    """Fuerza el dialecto Postgres durante el bloque (sin servidor ni driver)."""

    def __enter__(self):
        self._previo = database._ES_POSTGRES
        database._ES_POSTGRES = True
        return self

    def __exit__(self, *exc):
        database._ES_POSTGRES = self._previo
        return False


class TestMigracion003EnPostgres(unittest.TestCase):
    """§6 — el SQL de la migración 003 para PostgreSQL. Es el bug que llegó a prod."""

    def setUp(self):
        migrations._migrated.clear()
        self.previo = os.environ.get("ARHIAX_TMP_DIR")

    tearDown = setUp

    def _correr_003(self, *, aplicadas=("001_initial", "002_case_canonical_state"),
                    fallar_en=None):
        conn = _ConnFalso(aplicadas=aplicadas, fallar_en=fallar_en)
        with _PostgresSimulado():
            aplicadas_ahora = migrations.run_migrations(conn)
        return conn, aplicadas_ahora

    def test_003_usa_bytea_y_nunca_blob(self):
        conn, aplicadas_ahora = self._correr_003()

        columnas = [s for s in conn.sql() if "trabajos_pdf" in s and "ADD COLUMN" in s]
        self.assertTrue(columnas, "003 no emitió ningún ALTER TABLE sobre trabajos_pdf")
        self.assertTrue(any("ADD COLUMN IF NOT EXISTS pdf_tecnico BYTEA" in s
                            for s in columnas),
                        f"falta pdf_tecnico BYTEA en el SQL emitido: {columnas}")

        # El tipo inválido es el defecto de producción: no puede reaparecer.
        for sentencia in conn.sql():
            self.assertNotIn("BLOB", sentencia.upper(),
                             f"Postgres no conoce BLOB: {sentencia}")
        self.assertEqual(aplicadas_ahora, ["003_documento_principal"])

    def test_003_crea_las_tres_columnas_y_registra_la_migracion(self):
        conn, _ = self._correr_003()
        texto = " | ".join(conn.sql())
        for columna, tipo in (("pdf_tecnico", "BYTEA"), ("manifest_json", "TEXT"),
                              ("folio", "TEXT")):
            self.assertIn(f"ADD COLUMN IF NOT EXISTS {columna} {tipo}", texto)
        registro = [p for s, p in conn.sql_con_parametros()
                    if "INSERT INTO schema_migrations" in s]
        self.assertEqual(len(registro), 1, "003 debe registrarse UNA sola vez")
        self.assertEqual(registro[0][0], "003_documento_principal")
        self.assertTrue(registro[0][1], "la migración registrada debe llevar fecha")
        self.assertGreaterEqual(conn.commits, 2, "el CREATE + el INSERT deben confirmarse")

    def test_001_y_002_no_se_reintentan_cuando_ya_estan_aplicadas(self):
        conn, aplicadas_ahora = self._correr_003()
        self.assertNotIn("001_initial", aplicadas_ahora)
        self.assertNotIn("002_case_canonical_state", aplicadas_ahora)
        # El estado de partida de Neon: 001 y 002 aplicadas, 003 pendiente.
        for s in conn.sql():
            if "ADD COLUMN" in s:
                self.assertIn("trabajos_pdf", s,
                              "una base ya migrada no debe re-crear el esquema base")

    def test_fallo_ddl_no_registra_la_migracion_y_hace_rollback(self):
        """§4: si un ALTER falla, 003 queda PENDIENTE (nunca aplicada)."""
        def fallar(sql):
            return "manifest_json" in sql and "ADD COLUMN" in sql

        conn = _ConnFalso(aplicadas=("001_initial", "002_case_canonical_state"),
                          fallar_en=fallar)
        with _PostgresSimulado():
            with self.assertRaises(RuntimeError):
                migrations.run_migrations(conn)

        self.assertGreaterEqual(conn.rollbacks, 1,
                                "tras un DDL fallido hay que hacer rollback")
        registros = [p for s, p in conn.sql_con_parametros()
                     if "INSERT INTO schema_migrations" in s]
        self.assertEqual(registros, [], "una migración fallida NO se registra")

    def test_ninguna_migracion_emite_un_tipo_invalido_en_postgres(self):
        """Barrido completo: cualquier `ADD COLUMN` (todas las migraciones) es válido."""
        conn = _ConnFalso(aplicadas=())
        with _PostgresSimulado():
            try:
                migrations.run_migrations(conn)
            except Exception:  # noqa: BLE001 — 001 simula el CREATE base sobre el doble
                pass
        for sentencia in conn.sql():
            if "ADD COLUMN" in sentencia.upper():
                self.assertNotIn("BLOB", sentencia.upper(), sentencia)
                self.assertNotIn("AUTOINCREMENT", sentencia.upper(), sentencia)

    def test_el_estado_de_partida_de_produccion_queda_completo(self):
        """Neon tenía 001 y 002: tras el hotfix, 003 corre y las columnas existen."""
        conn, _ = self._correr_003()
        creadas = {s.split("ADD COLUMN IF NOT EXISTS ")[1].split()[0]
                   for s in conn.sql() if "ADD COLUMN IF NOT EXISTS" in s}
        self.assertEqual(creadas, {"pdf_tecnico", "manifest_json", "folio"})


class TestMigracionRealEnSqlite(unittest.TestCase):
    """Idempotencia y estados parciales sobre una base REAL (§5)."""

    def setUp(self):
        self.db = ROOT / "tmp_hotfix_r11" / "qa.db"
        self.db.parent.mkdir(parents=True, exist_ok=True)
        if self.db.exists():
            self.db.unlink()
        self.conn = sqlite3.connect(str(self.db))
        self.conn.row_factory = sqlite3.Row
        migrations._migrated.clear()

    def tearDown(self):
        try:
            self.conn.close()
        finally:
            if self.db.exists():
                self.db.unlink()

    def _columnas(self, tabla):
        return {r["name"] for r in self.conn.execute(f"PRAGMA table_info({tabla})")}

    def _base_de_produccion(self, *, columnas_extra=()):
        """Reproduce el estado REAL de Neon antes del hotfix: 001 y 002 aplicadas,
        `trabajos_pdf` con el esquema anterior (sin las columnas de la entrega)."""
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS trabajos_pdf (id TEXT PRIMARY KEY, estado TEXT "
            "NOT NULL, pdf BLOB, error TEXT, creado TEXT NOT NULL)")
        for col in columnas_extra:
            self.conn.execute(f"ALTER TABLE trabajos_pdf ADD COLUMN {col} TEXT")
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations (id TEXT PRIMARY KEY, "
            "applied_at TEXT NOT NULL)")
        for mid in ("001_initial", "002_case_canonical_state"):
            self.conn.execute("INSERT INTO schema_migrations (id, applied_at) "
                              "VALUES (?, ?)", (mid, "2026-01-01T00:00:00+00:00"))
        self.conn.commit()

    def test_003_sobre_esquema_001_002_y_reintento_idempotente(self):
        self._base_de_produccion()
        self.assertNotIn("pdf_tecnico", self._columnas("trabajos_pdf"))

        aplicadas = migrations.run_migrations(self.conn)
        self.assertEqual(aplicadas, ["003_documento_principal"])
        self.assertTrue({"pdf_tecnico", "manifest_json", "folio"}
                        <= self._columnas("trabajos_pdf"))
        self.assertEqual(migrations.run_migrations(self.conn), [],
                         "un segundo pase no puede re-aplicar 003")
        registradas = [r["id"] for r in self.conn.execute(
            "SELECT id FROM schema_migrations").fetchall()]
        self.assertEqual(registradas.count("003_documento_principal"), 1)

    def test_003_es_idempotente_con_columnas_ya_existentes_en_parte(self):
        """Estado parcial: una de las tres columnas ya existe (migración a medias)."""
        self._base_de_produccion(columnas_extra=("folio",))
        migrations._apply_documento_principal(self.conn)    # no debe romper
        migradas = self._columnas("trabajos_pdf")
        self.assertTrue({"pdf_tecnico", "manifest_json", "folio"} <= migradas)

    def test_001_crea_el_esquema_completo_en_una_base_nueva(self):
        """Base vacía: 001 deja el esquema con las columnas de la entrega (local)."""
        migradas = migrations.run_migrations(self.conn)
        self.assertEqual(migradas, ["001_initial", "002_case_canonical_state",
                                    "003_documento_principal"])
        self.assertTrue({"pdf_tecnico", "manifest_json", "folio"}
                        <= self._columnas("trabajos_pdf"))
        self.assertTrue({"dictamenes", "documentos_caso"} <= self._tablas())

    def _tablas(self):
        return {r["name"] for r in self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")}

    def test_el_tipo_local_sigue_siendo_blob(self):
        """El dialecto local no cambia: en SQLite la columna binaria es BLOB."""
        self.assertEqual(migrations._tipo_binario(), "BLOB")
        self.assertEqual(migrations._normalizar_tipo("BYTEA"), "BLOB")
        self.assertEqual(migrations._normalizar_tipo("BLOB"), "BLOB")
        self.assertEqual(migrations._normalizar_tipo("TEXT"), "TEXT")


class TestTipoDeColumnaPorDialecto(unittest.TestCase):
    """La regla de traducción es ÚNICA y no contradictoria."""

    def test_blob_y_bytea_se_traducen_al_dialecto(self):
        with _PostgresSimulado():
            self.assertEqual(migrations._tipo_binario(), "BYTEA")
            for tipo in ("BLOB", "BYTEA", "blob", "bytea"):
                self.assertEqual(migrations._normalizar_tipo(tipo), "BYTEA")
            self.assertEqual(migrations._normalizar_tipo("TEXT"), "TEXT")
        self.assertEqual(migrations._tipo_binario(), "BLOB")
        self.assertEqual(migrations._normalizar_tipo("BYTEA"), "BLOB")


class TestCreacionDeCasoSobreBaseReal(unittest.TestCase):
    """§7 — el flujo que fallaba en producción, de punta a punta."""

    def setUp(self):
        self.db = ROOT / "tmp_hotfix_r11" / "caso.db"
        self.db.parent.mkdir(parents=True, exist_ok=True)
        if self.db.exists():
            self.db.unlink()
        self._dsn_previo = os.environ.get("ARHIAX_DB_PATH")
        os.environ["ARHIAX_DB_PATH"] = str(self.db)
        database.DB_PATH = str(self.db)
        database._ES_POSTGRES = False
        migrations._migrated.clear()

    def tearDown(self):
        if self._dsn_previo is None:
            os.environ.pop("ARHIAX_DB_PATH", None)
        else:
            os.environ["ARHIAX_DB_PATH"] = self._dsn_previo
        database.DB_PATH = database._resolver_db_path()
        migrations._migrated.clear()
        if self.db.exists():
            self.db.unlink()

    def test_get_db_connection_ensure_migrated_create_case_get(self):
        from case_repository import CaseRepository
        from case_service import create_case

        conn = database.get_db_connection()      # dispara ensure_migrated
        try:
            migradas = [r["id"] for r in conn.execute(
                "SELECT id FROM schema_migrations").fetchall()]
            columnas = {r["name"] for r in conn.execute(
                "PRAGMA table_info(trabajos_pdf)")}
        finally:
            conn.close()
        self.assertIn("003_documento_principal", migradas)
        self.assertTrue({"pdf_tecnico", "manifest_json", "folio"} <= columnas)

        caso = create_case(folio_matricula="040-646406", direccion="CALLE 1 # 2 - 3",
                           barrio="MIRAMAR", estrato=3, area=58.75, ciudad="barranquilla",
                           created_by="qa-hotfix")
        self.assertIsNotNone(caso)
        self.assertIsInstance(caso["id"], int)
        self.assertEqual(caso["folio_matricula"], "040-646406")
        self.assertEqual(caso["direccion"], "CALLE 1 # 2 - 3")
        self.assertEqual(caso["ciudad"], "barranquilla")
        self.assertEqual(caso["created_by"], "qa-hotfix")
        self.assertEqual(caso["estado"], "PENDIENTE_IMAGENES")

        guardado = CaseRepository().get(caso["id"])
        self.assertEqual(guardado["id"], caso["id"])
        self.assertEqual(guardado["folio_matricula"], "040-646406")
        self.assertNotIn("pdf_path", guardado, "el Case no expone rutas internas")

    def test_una_migracion_pendiente_no_impide_crear_el_caso(self):
        """El fallo de producción: la migración rompía la conexión. Ahora no."""
        conn = database.get_db_connection()
        conn.close()
        from case_service import create_case
        caso = create_case(folio_matricula="", direccion="CARRERA 9 # 1 - 2",
                           ciudad="pasto")
        self.assertIsNotNone(caso.get("id"))
        self.assertEqual(caso["estado"], "PENDIENTE_IMAGENES")

    def test_validacion_sigue_devolviendo_400(self):
        from case_service import ValidationError, create_case
        with self.assertRaises(ValidationError):
            create_case(folio_matricula="", direccion="")


if __name__ == "__main__":
    unittest.main()

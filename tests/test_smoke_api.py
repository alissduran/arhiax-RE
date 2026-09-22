# -*- coding: utf-8 -*-
"""Smoke tests de la API: detectan al instante el bug H-01 (IndentationError en api/index.py)
que dejaba el backend completo caído en producción (404/500 en todos los /api/*)."""
import ast
import sys
import unittest
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
API_DIR = ROOT_DIR / "api"
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(API_DIR))


class TestSmokeApi(unittest.TestCase):

    def test_index_py_compila(self):
        """El módulo principal debe parsear sin SyntaxError (regresión de H-01)."""
        src = (API_DIR / "index.py").read_text(encoding="utf-8")
        ast.parse(src)  # lanza SyntaxError/IndentationError si está roto

    def test_index_importa_sin_errores(self):
        """El import del módulo no debe dejar import_error set."""
        import importlib
        import index  # noqa: F401  (ejecuta la inicialización del módulo)
        importlib.reload(index) if False else None
        self.assertIsNone(index.import_error, f"import_error no es None: {index.import_error}")

    def test_resolver_matricula_no_hardcodea_casos(self):
        """C-01: la resolución NO puede devolver folios fijos por subcadenas.

        Antes: `resolver_matricula_por_direccion("Tv 43 # 100-50")` devolvía el caso
        Golden hardcodeado ("040-646406", "Miramar", 4) por coincidencia de «43» y
        «100», y cualquier dirección desconocida devolvía estrato 4 por defecto.
        """
        from index import resolver_matricula_por_direccion
        # Se parchean las fuentes de red para que el test sea determinista y offline.
        import address_resolution as ar

        def _sin_red(*a, **k):
            raise RuntimeError("sin red en test")
        _orig_geo = None
        try:
            import geocoder_catastral
            _orig_geo = geocoder_catastral.geocodificar_catastro_barranquilla
            geocoder_catastral.geocodificar_catastro_barranquilla = _sin_red
        except Exception:  # noqa: BLE001
            pass

        def _predial_nulo(direccion, fuentes):
            return None
        _orig_pred = ar._predial_desde_capa_direcciones
        ar._predial_desde_capa_direcciones = _predial_nulo
        try:
            folio, barrio, estrato = resolver_matricula_por_direccion("Tv 43 # 100-50")
            self.assertEqual(folio, "Pendiente")
            self.assertEqual(barrio, "")
            self.assertIsNone(estrato)
        finally:
            ar._predial_desde_capa_direcciones = _orig_pred
            if _orig_geo is not None:
                import geocoder_catastral
                geocoder_catastral.geocodificar_catastro_barranquilla = _orig_geo

    def test_resolver_matricula_no_inventa_estrato(self):
        """Sin fuentes que respondan, el estrato es None (NUNCA 4 por defecto)."""
        from index import resolver_matricula_por_direccion
        import address_resolution as ar
        _orig = ar._predial_desde_capa_direcciones
        ar._predial_desde_capa_direcciones = lambda direccion, fuentes: None
        _orig_ent = None
        try:
            import catastro_predio
            _orig_ent = catastro_predio.consultar_entorno_urbano
            catastro_predio.consultar_entorno_urbano = lambda *a, **k: {"disponible": False}
            folio, barrio, estrato = resolver_matricula_por_direccion("Carrera 5 # 20-33")
            self.assertEqual(folio, "Pendiente")
            self.assertEqual(barrio, "")
            self.assertIsNone(estrato, "el estrato no puede tener valor por defecto")
            self.assertEqual(resolver_matricula_por_direccion("Pendiente")[0], "Pendiente")
        finally:
            ar._predial_desde_capa_direcciones = _orig
            if _orig_ent is not None:
                import catastro_predio
                catastro_predio.consultar_entorno_urbano = _orig_ent

    def test_login_endpoint_ok(self):
        """El endpoint de login acepta la contraseña correcta (probado sin capa HTTP,
        autocontenido para no depender de httpx/TestClient)."""
        from fastapi import HTTPException
        from index import login
        # Contraseña SINTÉTICA de desarrollo/test (nunca una credencial real).
        r = login({"password": "dev-only-not-a-real-password"})
        self.assertTrue(r.get("success"))
        self.assertTrue(r.get("token"))

    def test_login_endpoint_rechaza_password_incorrecta(self):
        from fastapi import HTTPException
        from index import login
        with self.assertRaises(HTTPException) as ctx:
            login({"password": "password-incorrecta-xyz"})
        self.assertEqual(ctx.exception.status_code, 401)

    def test_auth_tokens_firmados_y_expiracion(self):
        """Los tokens se firman con HMAC, expiran y llevan rol (F-01/F-02 + roles)."""
        from datetime import datetime, timedelta
        from fastapi.security import HTTPAuthorizationCredentials
        from fastapi import HTTPException
        from index import _crear_token, _decodificar_token, _firmar, require_auth, require_admin

        token = _crear_token("admin", "admin")
        self.assertEqual(_decodificar_token(token), ("admin", "admin"))
        self.assertIsNone(_decodificar_token(token + "x"))
        self.assertIsNone(_decodificar_token("firma-invalida"))

        # Token con expiración en el pasado debe rechazarse
        exp_pasado = (datetime.now() - timedelta(hours=1)).isoformat()
        payload = f"{exp_pasado}|admin|admin"
        token_expirado = f"{payload}.{_firmar(payload)}"
        self.assertIsNone(_decodificar_token(token_expirado))

        creds_ok = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        sesion = require_auth(creds_ok)
        self.assertEqual(sesion["rol"], "admin")
        self.assertEqual(require_admin(sesion)["username"], "admin")
        with self.assertRaises(HTTPException):
            require_auth(None)
        with self.assertRaises(HTTPException):
            require_auth(HTTPAuthorizationCredentials(scheme="Bearer", credentials="token-invalido"))

        # Un token de operador NO pasa require_admin (403)
        tok_operador = _crear_token("operador1", "operador")
        sesion_op = require_auth(HTTPAuthorizationCredentials(scheme="Bearer", credentials=tok_operador))
        self.assertEqual(sesion_op["rol"], "operador")
        with self.assertRaises(HTTPException) as ctx:
            require_admin(sesion_op)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_login_por_usuario_con_rol(self):
        from fastapi import HTTPException
        from index import login
        r = login({"username": "admin", "password": "dev-only-not-a-real-password"})
        self.assertEqual(r["rol"], "admin")
        self.assertEqual(r["username"], "admin")
        # Usuario inexistente -> 401
        with self.assertRaises(HTTPException) as ctx:
            login({"username": "noexiste", "password": "x"})
        self.assertEqual(ctx.exception.status_code, 401)

    @pytest.mark.network
    def test_pdf_compiler_genera_pdf_honesto(self):
        """El PDF se genera con los motores dinámicos: sin plantilla fija de Napoli,
        sin PII hardcodeada y con sección de scores presente (H-05/H-06/H-07/H-04).
        Marcado network: geocodifica en vivo (con fallbacks), se excluye del CI rápido."""
        import shutil
        from pathlib import Path as _P
        from pdf_compiler import compile_pdf
        out_dir = ROOT_DIR / "tmp_pdf_test"
        if out_dir.exists():
            shutil.rmtree(out_dir, ignore_errors=True)
        out_dir.mkdir(parents=True, exist_ok=True)
        record = {
            "id": 1,
            "folio_matricula": "040-646406",
            "direccion": "Tv 43 # 100-50",
            "barrio": "Miramar",
            "estrato": 4,
            "area": 75.5,
            "valor_consolidado": 500000000,
            "sombra_9am_cargada": 0,
            "sombra_3pm_cargada": 0,
            "mapa_cargado": 0,
            "acreedor_real": None,
            "certificado_path": None,
        }
        try:
            compile_pdf(record, str(out_dir / "test.pdf"), assets_dir=out_dir)
        except Exception as e:  # noqa: BLE001 — el compilador debe degradar con fallbacks
            self.fail(f"compile_pdf lanzó excepción: {e}")
        import pypdf
        r = pypdf.PdfReader(str(out_dir / "test.pdf"))
        txt = " ".join((p.extract_text() or "") for p in r.pages).lower()
        self.assertIn("score registral", txt)
        self.assertNotIn("torre 8", txt)
        self.assertNotIn("conjunto napoli", txt)
        self.assertNotIn("1.045.718.995", txt)
        self.assertNotIn("1.140.834.790", txt)
        # Sin certificado: la ausencia de CTL es un hallazgo HONESTO
        self.assertIn("ausencia de ctl", txt)
        shutil.rmtree(out_dir, ignore_errors=True)

    @pytest.mark.network
    def test_pdf_compiler_con_certificado_no_declara_ausencia_falsa(self):
        """H-08: si el CTL se adjuntó (certificado_path), el PDF no debe declarar
        'AUSENCIA DE CTL' ni '[SIN CTL]'. Marcado network (geocodifica en vivo)."""
        import shutil
        from io import BytesIO
        from pathlib import Path as _P
        from reportlab.pdfgen import canvas
        from pdf_compiler import compile_pdf
        out_dir = ROOT_DIR / "tmp_pdf_test_cert"
        if out_dir.exists():
            shutil.rmtree(out_dir, ignore_errors=True)
        out_dir.mkdir(parents=True, exist_ok=True)
        # Certificado de prueba mínimo
        buf = BytesIO()
        c = canvas.Canvas(buf)
        c.drawString(50, 780, "CERTIFICADO DE TRADICION Y LIBERTAD (PRUEBA)")
        c.drawString(50, 760, "MATRICULA INMOBILIARIA: 040-777777")
        c.drawString(50, 740, "DIRECCION: CALLE 63 # 37-71")
        c.drawString(50, 720, "AREA PRIVADA 75.5 M2")
        c.save()
        cert_path = out_dir / "cert_prueba.pdf"
        cert_path.write_bytes(buf.getvalue())
        record = {
            "id": 2,
            "folio_matricula": "040-777777",
            "direccion": "Calle 63 # 37-71",
            "barrio": "El Recreo",
            "estrato": 4,
            "area": 75.5,
            "valor_consolidado": 400000000,
            "sombra_9am_cargada": 0,
            "sombra_3pm_cargada": 0,
            "mapa_cargado": 0,
            "acreedor_real": None,
            "certificado_path": str(cert_path),
        }
        try:
            compile_pdf(record, str(out_dir / "test.pdf"), assets_dir=out_dir)
        except Exception as e:  # noqa: BLE001
            self.fail(f"compile_pdf con certificado lanzó excepción: {e}")
        import pypdf
        r = pypdf.PdfReader(str(out_dir / "test.pdf"))
        txt = " ".join((p.extract_text() or "") for p in r.pages).lower()
        self.assertNotIn("ausencia de ctl", txt)
        self.assertNotIn("[sin ctl]", txt)
        self.assertIn("ctl procesado", txt)
        self.assertIn("040-777777", txt)
        shutil.rmtree(out_dir, ignore_errors=True)

    def test_carga_economica_inputs_invalidos(self):
        """M-06: inputs inválidos (plazo 0, valor None, tasa absurda) no deben
        lanzar excepciones ni producir LTV negativo."""
        from carga_economica import estimar_carga_hipotecaria
        r1 = estimar_carga_hipotecaria(None, None, plazo_anos=0, tasa_anual=12.5)
        self.assertIn("saldo_estimado", r1)
        # 03F: UNKNOWN != ZERO: sin base de valor no se fabrica LTV 0.
        self.assertIs(r1["available"], False)
        self.assertIsNone(r1["ltv_estimado"])
        r2 = estimar_carga_hipotecaria(200000000, "10 de mayo de 2023")
        self.assertGreaterEqual(r2["ltv_estimado"], 0)
        self.assertGreaterEqual(r2["saldo_estimado"], 0)

    def test_motor_geoespacial_con_datos_empaquetados(self):
        """F-17: el motor usa api/data/ (empaquetado) y detecta intersección real
        en Napoli sin depender de rutas absolutas de Windows ni de red."""
        from geospatial_engine import evaluate_predio, load_geospatial_index
        cache = load_geospatial_index()
        self.assertTrue(cache.get("capas_disponibles"), "capas del POT no disponibles en api/data/")
        # Napoli (Tv 43 # 100-50) — intersecta amenaza Baja según datos POT
        r = evaluate_predio(10.99386, -74.79261)
        self.assertTrue(r["amenaza_remocion_masa"]["intersecta"])
        self.assertEqual(r["amenaza_remocion_masa"]["nivel"], "Baja")
        self.assertIn("Barranquilla", r["resumen_ejecutivo"])
        # El resumen NO debe decir que no se completó (capas disponibles)
        self.assertNotIn("no se completó", r["resumen_ejecutivo"].lower())

    def test_wfs_client_manejo_errores(self):
        """Sprint 3: el cliente WFS nunca lanza; los fallos se reportan como
        disponible=False para que el dictamen marque NO EVALUADO en vez de mentir."""
        from integrations.wfs_client import get_features_bbox
        r1 = get_features_bbox("https://ejemplo.invalido/wfs", "capa:test", (10.0, -75.0, 9.0, -74.0))
        self.assertFalse(r1["disponible"])
        self.assertIn("error", r1)
        r2 = get_features_bbox(
            "https://servicio-inexistente-xyz.com/wfs", "capa:test",
            (10.94, -74.85, 11.05, -74.77),
        )
        self.assertFalse(r2["disponible"])
        self.assertIn("fuente", r2)
        self.assertIn("timestamp_utc", r2["fuente"])

    def test_arcgis_client_manejo_errores(self):
        """Sprint 3: el cliente ArcGIS nunca lanza; fallos -> disponible=False."""
        from integrations.arcgis_client import query_layer_bbox, listar_colecciones_ogc
        r1 = query_layer_bbox("https://ejemplo.invalido/FeatureServer", 1, (10.0, -75.0, 9.0, -74.0))
        self.assertFalse(r1["disponible"])
        r2 = query_layer_bbox("no-es-una-url", 1, (10.0, -75.0, 11.0, -74.0))
        self.assertFalse(r2["disponible"])
        r3 = query_layer_bbox(
            "https://servicio-inexistente-xyz.com/FeatureServer", 1,
            (10.94, -74.85, 11.05, -74.77),
        )
        self.assertFalse(r3["disponible"])
        self.assertIn("fuente", r3)
        r4 = listar_colecciones_ogc("https://ejemplo.invalido/ogc")
        self.assertFalse(r4["disponible"])

    def test_endpoint_catastro_valida_inputs(self):
        """Sprint 3: el endpoint de catastro en vivo exige lat/lon o dirección (400)."""
        from fastapi import HTTPException
        from index import verificar_catastro_en_vivo
        with self.assertRaises(HTTPException) as ctx:
            verificar_catastro_en_vivo()
        self.assertEqual(ctx.exception.status_code, 400)

    def test_territorio_dispatcher_ciudades(self):
        """Sprint 3: el dispatcher multi-ciudad devuelve formato uniforme y
        Bogotá queda declarada en evaluación (sin afirmar datos)."""
        import api.integrations.territorio as terr
        original = terr.query_layer_bbox
        original_wfs = terr.get_features_bbox
        try:
            terr.query_layer_bbox = lambda *a, **k: {
                "disponible": True, "features": [{"properties": {"name": "0800T", "codigo_tratamiento": "Z4"}}],
                "total_features": 1, "error": None, "fuente": {"url": "stub"},
            }
            terr.get_features_bbox = lambda *a, **k: {
                "disponible": True, "features": [{"properties": {"barnombre": "SAN FERNANDO"}}],
                "total_features": 1, "error": None, "fuente": {"url": "stub"},
            }
            terr._CACHE.clear()
            r_baq = terr.verificar_territorio(10.99386, -74.79261, "barranquilla")
            self.assertTrue(r_baq["disponible"])
            self.assertIn("NUPRE", r_baq["resumen"] or "")
            r_med = terr.verificar_territorio(6.2442, -75.5812, "medellin")
            self.assertTrue(r_med["disponible"])
            self.assertIn("tratamiento", r_med["resumen"] or "")
            r_cali = terr.verificar_territorio(3.4516, -76.5320, "cali")
            self.assertTrue(r_cali["disponible"])
            self.assertIn("SAN FERNANDO", r_cali["resumen"] or "")
            # Bogotá: con IDECA federado configurado consulta en vivo (stub)
            r_bog = terr.verificar_territorio(4.7110, -74.0721, "bogota")
            self.assertTrue(r_bog["disponible"])
            self.assertIn("IDECA", r_bog["resumen"] or "")
            # Ciudad no soportada
            r_x = terr.verificar_territorio(4.0, -74.0, "cartagena")
            self.assertFalse(r_x["disponible"])
        finally:
            terr.query_layer_bbox = original
            terr.get_features_bbox = original_wfs
            terr._CACHE.clear()

    def test_database_dsn_configurable(self):
        """Backlog persistencia: DSN SQLite local funciona; DSN postgres (Neon)
        se reconoce como postgres y, sin psycopg instalado, da error claro al
        conectar (no falla silenciosamente)."""
        import os
        import importlib
        import database as db_mod
        tmp = ROOT_DIR / "tmp_db_test" / "test.db"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        old = os.environ.get("ARHIAX_DB_PATH")
        try:
            os.environ["ARHIAX_DB_PATH"] = str(tmp)
            importlib.reload(db_mod)
            self.assertFalse(db_mod._ES_POSTGRES)
            conn = db_mod.get_db_connection()
            conn.execute("SELECT 1")
            conn.close()

            os.environ["ARHIAX_DB_PATH"] = "postgres://user:pass@host-invalido-xyz/db"
            importlib.reload(db_mod)
            self.assertTrue(db_mod._ES_POSTGRES)
            # Sin servicio real: debe fallar (RuntimeError sin driver local, o error de
            # conexión con psycopg instalado en CI). Nunca devuelve conexión sqlite.
            with self.assertRaises(Exception):
                db_mod.get_db_connection()
        finally:
            if old is None:
                os.environ.pop("ARHIAX_DB_PATH", None)
            else:
                os.environ["ARHIAX_DB_PATH"] = old
            importlib.reload(db_mod)

    def test_postgres_adapter_traduccion_sql(self):
        """El adaptador Postgres traduce '?' -> '%s' y captura lastrowid con
        RETURNING (probado con un cursor simulado, sin red)."""
        from postgres_adapter import _CursorCompat

        ejecutados = []

        class CursorFake:
            def execute(self, sql, params):
                ejecutados.append((sql, params))
                self._fila = {"id": 42}

            def fetchone(self):
                return getattr(self, "_fila", None)

        c = _CursorCompat(CursorFake())
        c.execute("INSERT INTO dictamenes (folio_matricula) VALUES (?)", ("040-1",))
        sql_t, params = ejecutados[-1]
        self.assertIn("%s", sql_t)
        self.assertNotIn("?", sql_t)
        self.assertIn("RETURNING id", sql_t)
        self.assertEqual(c.lastrowid, 42)
        # UPDATE no debe añadir RETURNING
        c.execute("UPDATE dictamenes SET barrio = ? WHERE id = ?", ("x", 1))
        self.assertNotIn("RETURNING", ejecutados[-1][0])

    def test_parser_direccion_colombiana(self):
        """Geocoder catastral: el parser extrae clase/vía/generadora/número de
        formatos reales (offline, sin red)."""
        from geocoder_catastral import parsear_direccion_colombiana
        casos = {
            "CRA 43 # 98-32": ("Carrera", "43", "", "98", "32"),
            "Cra 43#98-32": ("Carrera", "43", "", "98", "32"),
            "CL 72 # 57-10": ("Calle", "72", "", "57", "10"),
            "Carrera 57 # 72-26": ("Carrera", "57", "", "72", "26"),
            "CRA 43A # 98-10": ("Carrera", "43", "A", "98", "10"),
            "Tv 43 # 100-50": ("Transversal", "43", "", "100", "50"),
            "AV 68 # 53-10": ("Avenida", "68", "", "53", "10"),
            "DG 22A # 18-2, Barranquilla": ("Diagonal", "22", "A", "18", "2"),
        }
        for texto, esperado in casos.items():
            r = parsear_direccion_colombiana(texto)
            self.assertEqual(r, esperado, f"falló para '{texto}': {r}")
        # No matchea: sin número de predio
        self.assertIsNone(parsear_direccion_colombiana("Calle 72"))
        self.assertIsNone(parsear_direccion_colombiana("Avenida Circunvalar 110-240"))

    def test_cola_pdf_fallback_sin_config(self):
        """Backlog cola: sin QSTASH_TOKEN la cola reporta no configurada y el
        encolado degrada con instrucciones claras (fallback síncrono)."""
        import cola_pdf
        import os
        old_tok = os.environ.get("QSTASH_TOKEN")
        old_url = os.environ.get("ARHIAX_WORKER_URL")
        try:
            os.environ.pop("QSTASH_TOKEN", None)
            os.environ.pop("ARHIAX_WORKER_URL", None)
            import importlib
            importlib.reload(cola_pdf)
            self.assertFalse(cola_pdf.cola_configurada())
            r = cola_pdf.encolar_generacion({"job_id": "x"})
            self.assertFalse(r["encolado"])
            self.assertIn("motivo", r)
            self.assertFalse(cola_pdf.estado_cola()["configurada"])
        finally:
            if old_tok is None:
                os.environ.pop("QSTASH_TOKEN", None)
            else:
                os.environ["QSTASH_TOKEN"] = old_tok
            if old_url is None:
                os.environ.pop("ARHIAX_WORKER_URL", None)
            else:
                os.environ["ARHIAX_WORKER_URL"] = old_url
            importlib.reload(cola_pdf)

    def test_config_ciudades_carga(self):
        """Sprint 3 (I-3): la config multi-ciudad carga y Barranquilla está activa."""
        from config import listar_ciudades, get_ciudad, get_nacionales
        ciudades = listar_ciudades()
        self.assertIn("barranquilla", ciudades)
        self.assertIn("bogota", ciudades)
        self.assertIn("medellin", ciudades)
        self.assertIn("cali", ciudades)
        cfg_baq = get_ciudad("barranquilla")
        self.assertIn("catastro", cfg_baq.get("arcgis", {}))
        self.assertIn("igac", get_nacionales())

    def test_catastro_live_estructura_y_cache(self):
        """Sprint 3 (I-6): verificar_catastro_barranquilla devuelve la estructura
        esperada y cachea por celda (sin golpear el servicio dos veces)."""
        import api.integrations.catastro_live as cl
        original = cl.query_layer_bbox
        try:
            llamadas = []

            def stub(url, capa, bbox, **kwargs):
                llamadas.append(capa)
                if capa == 315:
                    return {"disponible": True, "features": [{"properties": {"name": "0800TESTNUPRE"}}],
                            "total_features": 1, "error": None, "fuente": {"url": "stub"}}
                return {"disponible": True, "features": [], "total_features": 0,
                        "error": None, "fuente": {"url": "stub"}}

            cl.query_layer_bbox = stub
            cl._CACHE.clear()
            r1 = cl.verificar_catastro_barranquilla(10.99386, -74.79261)
            self.assertTrue(r1["disponible"])
            # 03D.2: el atributo del terreno es un número predial, no un NUPRE.
            self.assertEqual(r1["numero_predial"], "0800TESTNUPRE")
            self.assertIn("fuente", r1)
            n_llamadas = len(llamadas)
            # Segunda llamada con la misma celda: debe venir del caché (sin red)
            r2 = cl.verificar_catastro_barranquilla(10.99386, -74.79261)
            self.assertEqual(len(llamadas), n_llamadas)
            self.assertEqual(r2["numero_predial"], "0800TESTNUPRE")
        finally:
            cl.query_layer_bbox = original
            cl._CACHE.clear()

    def test_adjuntos_job_persisten_y_se_recuperan(self):
        """Sprint 2 (imágenes 3D): los insumos gráficos del job se persisten en
        trabajos_pdf (BYTEA/BLOB) y el worker los recupera por job_id.

        Regresión: en el flujo async la cola QStash no puede transportar PNG
        grandes; antes las imágenes de ArcGIS Online se descartaban y el PDF caía
        a la simulación geométrica."""
        import os
        import importlib
        import database as db_mod
        tmp = ROOT_DIR / "tmp_db_job" / "test_job.db"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        old = os.environ.get("ARHIAX_DB_PATH")
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
            os.environ["ARHIAX_DB_PATH"] = str(tmp)
            importlib.reload(db_mod)
            db_mod.init_db()
            import index as idx_mod
            importlib.reload(idx_mod)

            class FakeUpload:
                def __init__(self, data, nombre):
                    self._data = data
                    self.filename = nombre
                @property
                def file(self):
                    class _F:
                        def __init__(self, d):
                            self._d = d
                        def read(self, n):
                            return self._d
                    return _F(self._data)

            idx_mod._crear_trabajo("job-test-img", "pendiente")
            png = bytes(range(256)) * 8
            idx_mod._guardar_adjuntos_job("job-test-img",
                                          sombra_9am=FakeUpload(png, "sombra_9am.png"),
                                          mapa_satelital=FakeUpload(b"mapa-png", "mapa_satelital.png"))
            r = idx_mod._leer_adjuntos_job("job-test-img")
            self.assertEqual(r.get("sombra_9am"), png)
            self.assertEqual(r.get("mapa_satelital"), b"mapa-png")
            # Job inexistente: dict vacío (el worker degrada sin romper)
            self.assertEqual(idx_mod._leer_adjuntos_job("no-existe"), {})
        finally:
            if old is None:
                os.environ.pop("ARHIAX_DB_PATH", None)
            else:
                os.environ["ARHIAX_DB_PATH"] = old
            importlib.reload(db_mod)


class TestCiudadesNoOperativas(unittest.TestCase):
    """Regresión (fix Cali): una ciudad configurada pero NO operativa (Cali)
    jamás debe generar un dictamen con datos de otra ciudad. Antes se
    normalizaba silenciosamente a Barranquilla (riesgo de desinformación)."""

    def test_normalizar_ciudad_vacia_y_operativas(self):
        from index import _normalizar_ciudad
        self.assertEqual(_normalizar_ciudad(None), "barranquilla")
        self.assertEqual(_normalizar_ciudad(""), "barranquilla")
        self.assertEqual(_normalizar_ciudad("MEDELLIN"), "medellin")
        self.assertEqual(_normalizar_ciudad("bogota"), "bogota")

    def test_normalizar_ciudad_pendiente_cali_rechaza_400(self):
        from fastapi import HTTPException
        from index import _normalizar_ciudad
        with self.assertRaises(HTTPException) as ctx:
            _normalizar_ciudad("cali")
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Cali", ctx.exception.detail)

    def test_normalizar_ciudad_desconocida_fallback_baq(self):
        from index import _normalizar_ciudad
        # Valores raros (clientes viejos) siguen cayendo a BAQ retrocompatible
        self.assertEqual(_normalizar_ciudad("xyz-raro"), "barranquilla")

    def test_endpoint_generar_dictamen_rechaza_cali(self):
        """Generar dictamen con ciudad=cali -> 400 (antes producía un dictamen
        con datos/geocodificación de Barranquilla)."""
        import asyncio
        from fastapi import HTTPException
        from index import generar_dictamen_stateless

        async def _correr():
            with self.assertRaises(HTTPException) as ctx:
                await generar_dictamen_stateless(
                    folio_matricula="040-123456", direccion=None, area=80.0,
                    barrio=None, ciudad="cali", certificado=None,
                    sombra_9am=None, sombra_3pm=None, mapa_satelital=None,
                    async_=False, auth={"username": "admin", "rol": "admin"})
            self.assertEqual(ctx.exception.status_code, 400)
            self.assertIn("Cali", ctx.exception.detail)

        asyncio.run(_correr())

    def test_endpoint_gpv_f77_rechaza_cali(self):
        """El GPV-F-77 con ciudad=cali -> 400 (un estudio de títulos de Cali no
        puede elaborarse con datos registrales/catastrales de otra ciudad)."""
        import asyncio
        from fastapi import HTTPException
        from index import generar_gpv_f77_endpoint

        async def _correr():
            with self.assertRaises(HTTPException) as ctx:
                await generar_gpv_f77_endpoint(
                    folio_matricula="040-123456", direccion=None, area=80.0,
                    barrio=None, ciudad="cali", expediente=None,
                    certificado=None, auth={"username": "admin", "rol": "admin"})
            self.assertEqual(ctx.exception.status_code, 400)

        asyncio.run(_correr())


    def test_delete_dictamen_idempotente(self):
        """DELETE de un caso que solo existe en el navegador (localStorage) no
        debe bloquear con 404: el servidor responde success 'ya_inexistente'
        para que el portal limpie su lista local (regresión reportada por el
        usuario: 'Error al eliminar caso: Caso no encontrado')."""
        import sqlite3
        from pathlib import Path as _P
        import index as index_mod
        import database as db_mod

        tmp = _P(ROOT_DIR) / "tmp_db_test" / "delete_test.db"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        if tmp.exists():
            tmp.unlink()

        def _conectar_elim(db_path):
            c = sqlite3.connect(str(db_path))
            c.row_factory = sqlite3.Row
            return c

        conn = _conectar_elim(tmp)
        conn.execute("""CREATE TABLE dictamenes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folio_matricula TEXT NOT NULL,
            direccion TEXT NOT NULL, barrio TEXT NOT NULL, estrato INTEGER NOT NULL,
            area REAL, estado TEXT NOT NULL, valor_consolidado INTEGER,
            fecha_creacion TEXT NOT NULL)""")
        conn.execute("""INSERT INTO dictamenes
            (folio_matricula, direccion, barrio, estrato, area, estado, valor_consolidado, fecha_creacion)
            VALUES ('040-999', 'Calle 1 # 1-1', 'Miramar', 4, 50.0, 'PENDIENTE_IMAGENES', 0, '2026-01-01')""")
        conn.commit()
        conn.close()

        # SLICE-001: el endpoint delega en CaseService→CaseRepository, que obtiene
        # la conexión de `database.get_db_connection` (no de index). Se parchea la
        # fábrica canónica de conexión.
        orig_get_db = db_mod.get_db_connection
        db_mod.get_db_connection = lambda: _conectar_elim(tmp)
        try:
            # Caso inexistente (id local del navegador, nunca creado en el server):
            # responde success y NO lanza HTTPException 404.
            r = index_mod.delete_dictamen(999999999, auth={"username": "admin", "rol": "admin"})
            self.assertTrue(r.get("success"))
            self.assertTrue(r.get("ya_inexistente"))
            # Caso existente: se elimina de verdad.
            r2 = index_mod.delete_dictamen(1, auth={"username": "admin", "rol": "admin"})
            self.assertTrue(r2.get("success"))
            self.assertNotIn("ya_inexistente", r2)
            c_verif = _conectar_elim(tmp)
            cursor = c_verif.execute(
                "SELECT COUNT(*) AS n FROM dictamenes WHERE id = 1")
            self.assertEqual(cursor.fetchone()["n"], 0)
            c_verif.close()
        finally:
            db_mod.get_db_connection = orig_get_db
            if tmp.exists():
                tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()

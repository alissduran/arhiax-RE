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

    def test_resolver_matricula_casos_conocidos(self):
        from index import resolver_matricula_por_direccion
        self.assertEqual(resolver_matricula_por_direccion("Tv 43 # 100-50"), ("040-646406", "Miramar", 4))
        self.assertEqual(resolver_matricula_por_direccion("Calle 63 # 37-71"), ("040-314248", "El Recreo", 4))

    def test_resolver_matricula_fallback_y_pendiente(self):
        from index import resolver_matricula_por_direccion
        # M-01: las direcciones desconocidas devuelven 'Pendiente' (no folios simulados)
        folio, barrio, estrato = resolver_matricula_por_direccion("Carrera 5 # 20-33")
        self.assertEqual(folio, "Pendiente")
        self.assertEqual(estrato, 4)
        self.assertEqual(resolver_matricula_por_direccion("Pendiente")[0], "Pendiente")

    def test_login_endpoint_ok(self):
        """El endpoint de login acepta la contraseña correcta (probado sin capa HTTP,
        autocontenido para no depender de httpx/TestClient)."""
        from fastapi import HTTPException
        from index import login
        r = login({"password": "Sinergia2026"})
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
        r = login({"username": "admin", "password": "Sinergia2026"})
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
        self.assertGreaterEqual(r1["ltv_estimado"], 0)
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
        """Backlog persistencia: ARHIAX_DB_PATH local funciona y el esquema externo
        da un error claro (sin driver) en lugar de fallar silenciosamente."""
        import os
        import importlib
        import database as db_mod
        tmp = ROOT_DIR / "tmp_db_test" / "test.db"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        old = os.environ.get("ARHIAX_DB_PATH")
        try:
            os.environ["ARHIAX_DB_PATH"] = str(tmp)
            importlib.reload(db_mod)
            self.assertEqual(db_mod.DB_PATH, str(tmp))
            conn = db_mod.get_db_connection()
            conn.execute("SELECT 1")
            conn.close()
            os.environ["ARHIAX_DB_PATH"] = "postgres://user:pass@host/db"
            with self.assertRaises(RuntimeError):
                importlib.reload(db_mod)  # el import re-resuelve DB_PATH y debe fallar claro
        finally:
            if old is None:
                os.environ.pop("ARHIAX_DB_PATH", None)
            else:
                os.environ["ARHIAX_DB_PATH"] = old
            importlib.reload(db_mod)

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
            self.assertEqual(r1["nupre"], "0800TESTNUPRE")
            self.assertIn("fuente", r1)
            n_llamadas = len(llamadas)
            # Segunda llamada con la misma celda: debe venir del caché (sin red)
            r2 = cl.verificar_catastro_barranquilla(10.99386, -74.79261)
            self.assertEqual(len(llamadas), n_llamadas)
            self.assertEqual(r2["nupre"], "0800TESTNUPRE")
        finally:
            cl.query_layer_bbox = original
            cl._CACHE.clear()


if __name__ == "__main__":
    unittest.main()

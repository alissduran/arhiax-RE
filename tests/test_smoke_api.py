# -*- coding: utf-8 -*-
"""Smoke tests de la API: detectan al instante el bug H-01 (IndentationError en api/index.py)
que dejaba el backend completo caído en producción (404/500 en todos los /api/*)."""
import ast
import sys
import unittest
from pathlib import Path

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
        folio, barrio, estrato = resolver_matricula_por_direccion("Carrera 5 # 20-33")
        self.assertRegex(folio, r"^\d{3}-\d{6}$")  # folio simulado determinista
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
        """Los tokens se firman con HMAC y expiran (F-01/F-02)."""
        from datetime import datetime, timedelta
        from fastapi.security import HTTPAuthorizationCredentials
        from fastapi import HTTPException
        from index import _crear_token, _verificar_token, _firmar, require_auth, TOKEN_TTL_HOURS

        token = _crear_token()
        self.assertTrue(_verificar_token(token))
        self.assertFalse(_verificar_token(token + "x"))
        self.assertFalse(_verificar_token("firma-invalida"))

        # Token con expiración en el pasado debe rechazarse
        exp_pasado = (datetime.now() - timedelta(hours=1)).isoformat()
        token_expirado = f"{exp_pasado}.{_firmar(exp_pasado)}"
        self.assertFalse(_verificar_token(token_expirado))

        creds_ok = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        self.assertTrue(require_auth(creds_ok))
        with self.assertRaises(HTTPException):
            require_auth(None)
        with self.assertRaises(HTTPException):
            require_auth(HTTPAuthorizationCredentials(scheme="Bearer", credentials="token-invalido"))

    def test_pdf_compiler_genera_pdf_honesto(self):
        """El PDF se genera con los motores dinámicos: sin plantilla fija de Napoli,
        sin PII hardcodeada y con sección de scores presente (H-05/H-06/H-07/H-04)."""
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
        shutil.rmtree(out_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

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


if __name__ == "__main__":
    unittest.main()

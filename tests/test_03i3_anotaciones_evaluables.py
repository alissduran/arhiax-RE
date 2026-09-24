# -*- coding: utf-8 -*-
"""03I.3 — Guardia de ANOTACIONES: que ningún nombre sin resolver pueda volver a
romper el import en producción.

EL DEFECTO (reportado como «El servidor no pudo compilar el dictamen: name 'Optional'
is not defined»)
----------------------------------------------------------------------------------
`api/legal_analyzer.py` anotaba `def _constructor_de_adquisicion(...) -> Optional[str]`
sin importar `Optional`. Con Python ≥ 3.14 (PEP 649) las anotaciones se evalúan de
forma diferida, así que el módulo **importaba igual en local** y todas las pruebas
pasaban; el runtime de Vercel (3.12/3.13) las evalúa al definir la función, el
`import legal_analyzer` levantaba `NameError` y la compilación del dictamen fallaba.

Por eso la verificación es doble y NO depende de la versión de Python del entorno:

  1. **Estática (AST)**: en todo archivo SIN `from __future__ import annotations`, los
     nombres de `typing` usados en anotaciones deben estar importados. Se evalúan en
     cualquier intérprete, así que es el criterio que falla con 3.12.
  2. **En ejecución**: se fuerzan las anotaciones (`__annotations__`) de los módulos del
     pipeline; si algún nombre no se resuelve, aparece el mismo `NameError` que en
     producción, incluso corriendo en 3.14.
"""
import ast
import importlib
import io
import os
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))

NOMBRES_TYPING = {"Optional", "List", "Dict", "Tuple", "Any", "Union", "Callable",
                  "Iterable", "Sequence", "Mapping", "Literal", "Set", "FrozenSet",
                  "Type", "Generic", "Protocol", "NamedTuple", "TypedDict"}
IGNORAR_DIRS = {".git", "node_modules", "__pycache__", "docs", ".pytest_cache",
                "tmp_arhiax", "tmp_diag_run", "tmp_pdf_03i2a", "tmp_pdf_03i2b",
                "tmp_pdf_03i2ba", "tmp_golden_03i1"}

# Módulos que la generación del dictamen importa (el camino que falló).
MODULOS_DEL_PIPELINE = (
    "legal_analyzer", "pdf_compiler", "clasificacion", "tipologia", "market_context",
    "catastro_predio", "receipts", "address_resolution", "unidad_inmobiliaria",
    "canonical", "consistency", "ortografia", "score_engine", "dictamen_data",
    "carga_economica", "sarlaft_engine", "titulux_bridge", "cola_pdf",
    "sanctions.release_gate", "sanctions.subjects", "sanctions.matching",
)


def _nombres_de(nodo):
    usados = set()

    def visitar(n):
        if isinstance(n, ast.Name):
            usados.add(n.id)
        elif isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name):
            usados.add(n.value.id)
        for hijo in ast.iter_child_nodes(n):
            visitar(hijo)
    visitar(nodo)
    return usados


def _importados_de(arbol) -> set:
    importados = set()
    for n in ast.walk(arbol):
        if isinstance(n, ast.ImportFrom) and n.module == "typing":
            for al in n.names:
                importados.add(al.asname or al.name)
        if isinstance(n, ast.Import):
            for al in n.names:
                if al.name == "typing":
                    importados.add(al.asname or "typing")
    return importados


def _anotaciones_evaluadas(arbol):
    """(nombre_de_la_funcion, anotación) de todo lo que se evalúa al definir."""
    for n in ast.walk(arbol):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if n.returns is not None:
                yield n.name, n.returns
            for arg in (list(n.args.args) + list(n.args.kwonlyargs)
                        + list(n.args.posonlyargs)):
                if arg.annotation is not None:
                    yield n.name, arg.annotation
            if n.args.vararg and n.args.vararg.annotation:
                yield n.name, n.args.vararg.annotation
            if n.args.kwarg and n.args.kwarg.annotation:
                yield n.name, n.args.kwarg.annotation
        if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            yield getattr(n.target, "id", "?"), n.annotation


class TestAnotacionesEstaticas(unittest.TestCase):

    def test_ningun_nombre_typing_sin_importar_en_anotaciones(self):
        """Falla con el defecto real: `-> Optional[str]` sin `from typing import Optional`."""
        problemas = []
        for raiz, dirs, archivos in os.walk(str(ROOT)):
            dirs[:] = [d for d in dirs if d not in IGNORAR_DIRS]
            for nombre in archivos:
                if not nombre.endswith(".py"):
                    continue
                ruta = pathlib.Path(raiz) / nombre
                try:
                    src = io.open(ruta, encoding="utf-8").read()
                    arbol = ast.parse(src)
                except Exception:
                    continue  # archivos ilegibles/binarios no son objeto de esta prueba
                if "from __future__ import annotations" in src:
                    continue  # las anotaciones no se evalúan: no pueden romper el import
                importados = _importados_de(arbol)
                for funcion, anot in _anotaciones_evaluadas(arbol):
                    for usado in _nombres_de(anot):
                        if usado in NOMBRES_TYPING and usado not in importados:
                            problemas.append(
                                f"{ruta.relative_to(ROOT)}: {funcion} usa {usado} sin importarlo")
        self.assertEqual(problemas, [],
                         "anotaciones que romperían el import en Python < 3.14 "
                         "(el runtime de Vercel):\n  " + "\n  ".join(problemas))


class TestAnotacionesEnEjecucion(unittest.TestCase):
    """Fuerza la evaluación de anotaciones: en 3.14 también se detecta el defecto."""

    def setUp(self):
        os.environ.setdefault("ARHIAX_ENV", "test")
        os.environ.setdefault("ARHIAX_AUTH_SECRET", "qa-local-secret")
        os.environ.setdefault("ARHIAX_ADMIN_PASSWORD", "dev-only-not-a-real-password")

    def test_los_modulos_del_pipeline_resuelven_sus_anotaciones(self):
        problemas = []
        for nombre in MODULOS_DEL_PIPELINE:
            try:
                modulo = importlib.import_module(nombre)
            except Exception as e:  # noqa: BLE001 — el import también es parte del contrato
                problemas.append(f"{nombre}: no importa ({type(e).__name__}: {e})")
                continue
            for atributo in vars(modulo).values():
                if getattr(atributo, "__module__", None) != modulo.__name__:
                    continue
                objetivos = [atributo]
                if isinstance(atributo, type):
                    objetivos += [v for v in vars(atributo).values()
                                  if callable(v)]
                for obj in objetivos:
                    try:
                        obj.__annotations__          # evalúa (PEP 649) o ya está evaluado
                    except NameError as e:
                        problemas.append(f"{nombre}.{getattr(obj, '__name__', obj)}: {e}")
                    except Exception:  # noqa: BLE001 — otras excepciones no son este defecto
                        pass
        self.assertEqual(problemas, [],
                         "anotaciones irresolubles en módulos del pipeline:\n  "
                         + "\n  ".join(problemas))


class TestRegresionDelDefectoReportado(unittest.TestCase):

    def test_legal_analyzer_importa_optional_y_difiere_anotaciones(self):
        fuente = (ROOT / "api" / "legal_analyzer.py").read_text(encoding="utf-8")
        self.assertIn("from typing import Optional", fuente,
                      "legal_analyzer usa Optional: debe importarlo")
        self.assertIn("from __future__ import annotations", fuente,
                      "las anotaciones deben ser diferidas: así ningún nombre sin "
                      "resolver puede volver a romper el import en producción")

    def test_la_funcion_del_defecto_resuelve_su_anotacion(self):
        import legal_analyzer
        import typing
        pistas = typing.get_type_hints(legal_analyzer._constructor_de_adquisicion)
        self.assertIn("return", pistas)


if __name__ == "__main__":
    unittest.main(verbosity=2)

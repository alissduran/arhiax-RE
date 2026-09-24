# -*- coding: utf-8 -*-
"""QA estático del portal DICTUS (`ui/portal/`).

El portal es una pieza de interfaz: no se puede validar «a ojo» en cada cambio, así
que estas pruebas fijan sus invariantes ANTES de abrirlo en un navegador:

  1. **Coherencia HTML ↔ JS**: todo `id` que el guion usa existe en el documento
     (un id inexistente es un `null` silencioso en producción).
  2. **Accesibilidad de pestañas**: cada pestaña apunta a un panel que existe y cada
     panel tiene su encabezado (`aria-controls` / `aria-labelledby` resolubles).
  3. **Navegación completa**: cada `data-go` tiene su panel `#p-<destino>`.
  4. **Disciplina de datos (D2/D4/D7)**: el portal NO contiene valores de negocio
     (folios, direcciones, montos, estratos del caso) ni acciones de escritura más
     allá del inicio de sesión.
  5. **Sistema de diseño**: los tokens son la fuente única (el portal los importa) y
     el portal no introduce radios, sombras ni colores fuera del sistema.
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORTAL = ROOT / "ui" / "portal"
HTML = PORTAL / "index.html"
JS = PORTAL / "portal.js"
CSS = PORTAL / "portal.css"
TOKENS = ROOT / "ui" / "prototipo" / "tokens.css"

# Valores de negocio que NO pueden aparecer en la interfaz: si el portal los
# necesitara, deben llegar del endpoint, nunca del código (regla D2/D4).
LITERALES_VETADOS = (
    "040-646406",            # folio del caso de aceptación
    "AFT0005BOHA",           # NUPRE del caso
    "08001010300001",        # número predial del caso
    "399.500.000",           # valor comercial del caso
    "6.800.000",             # tasa de mercado del caso
    "1045718995",            # documento de un titular
    "8600029644",            # NIT de una contraparte
    "Miramar",               # barrio del caso
    "Transversal 43",        # dirección del caso
    "URBANIZADORA MARVAL",   # constructor del caso
)

ACCIONES_DE_ESCRITURA = ("POST", "PUT", "PATCH", "DELETE")


def _leer(p: Path) -> str:
    return p.read_text(encoding="utf-8")


class TestPortalExiste(unittest.TestCase):

    def test_archivos_de_la_experiencia(self):
        for f in (HTML, JS, CSS):
            self.assertTrue(f.exists(), f"falta {f.relative_to(ROOT)}")


class TestCoherenciaHtmlJs(unittest.TestCase):

    def test_todo_id_usado_por_el_js_existe_en_el_html(self):
        """Todo id que el guion obtiene con `$()` debe existir: en el documento o
        creado por el propio guion (los bloques de reintento se pintan al vuelo)."""
        html = _leer(HTML)
        js = _leer(JS)
        ids_documento = set(re.findall(r'id="([A-Za-z0-9_-]+)"', html))
        ids_dinamicos = set(re.findall(r'id="([A-Za-z0-9_-]+)"', js))
        ids_js = set(re.findall(r"\$\('([A-Za-z0-9_-]+)'\)", js))
        faltan = sorted(ids_js - ids_documento - ids_dinamicos)
        self.assertEqual(faltan, [],
                         f"el guion usa ids que no existen en ninguna parte: {faltan}")

    def test_toda_pestana_tiene_panel_y_encabezado(self):
        html = _leer(HTML)
        controles = re.findall(r'aria-controls="([A-Za-z0-9_-]+)"[^>]*>([^<]*)<', html)
        self.assertTrue(controles, "no se encontraron pestañas con aria-controls")
        for control, _etiqueta in controles:
            self.assertIn(f'id="{control}"', html,
                          f"aria-controls apunta a un panel inexistente: {control}")
        for ref in re.findall(r'aria-labelledby="([A-Za-z0-9_-]+)"', html):
            self.assertIn(f'id="{ref}"', html,
                          f"aria-labelledby apunta a un id inexistente: {ref}")

    def test_cada_destino_de_navegacion_tiene_su_panel(self):
        html = _leer(HTML)
        destinos = set(re.findall(r'data-go="([A-Za-z0-9_-]+)"', html))
        self.assertTrue(destinos)
        for d in sorted(destinos):
            self.assertIn(f'id="p-{d}"', html, f"falta el panel #p-{d} para data-go={d}")

    def test_las_perspectivas_del_mastil_estan_declaradas_en_css(self):
        html = _leer(HTML)
        css = _leer(CSS)
        persps = set(re.findall(r'data-persp="([a-z]+)"', html))
        self.assertGreaterEqual(len(persps), 4, "se esperan cuatro perspectivas")
        for p in sorted(persps):
            self.assertIn(f'data-persp="{p}"', css,
                          f"la perspectiva {p} no tiene regla de composición en el CSS")

    def test_el_js_es_sintacticamente_plausible(self):
        js = _leer(JS)
        # Balance de llaves/paréntesis/corchetes: un desbalance rompe el portal entero.
        for apertura, cierre, nombre in (("{", "}", "llaves"), ("(", ")", "paréntesis"),
                                         ("[", "]", "corchetes")):
            self.assertEqual(js.count(apertura), js.count(cierre),
                             f"desbalance de {nombre} en portal.js")
        self.assertIn("'use strict';", js)


class TestDisciplinaDeDatos(unittest.TestCase):

    def test_sin_valores_de_negocio_en_la_interfaz(self):
        contenido = "\n".join(_leer(f) for f in (HTML, JS, CSS))
        for literal in LITERALES_VETADOS:
            self.assertNotIn(literal, contenido,
                             f"valor de negocio incrustado en la interfaz: {literal!r}")

    def test_solo_el_login_escribe(self):
        """D7: el portal LEE. La única escritura admitida es autenticarse."""
        js = _leer(JS)
        escrituras = re.findall(r"method:\s*'([A-Z]+)'", js)
        self.assertEqual(sorted(set(escrituras)), ["POST"],
                         "apareció un verbo de escritura distinto del login")
        # El POST admitido debe ser el del inicio de sesión.
        for m in re.finditer(r"method:\s*'POST'", js):
            ventana = js[max(0, m.start() - 400): m.start() + 120]
            self.assertIn("/api/login", ventana,
                          "hay un POST que no es el inicio de sesión (D7: sin escrituras)")

    def test_los_estados_de_verdad_se_declaran_sin_valor_por_defecto(self):
        js = _leer(JS)
        for estado in ("VERIFIED_OFFICIAL", "VERIFIED_REGISTRAL", "VERIFIED_CATASTRAL",
                       "UNRESOLVED", "SOURCE_UNAVAILABLE", "CONFLICT", "PARTIAL",
                       "NO_MATCH", "AMBIGUOUS"):
            self.assertIn(estado, js, f"el portal no sabe pintar el estado {estado}")
        # El valor vacío SIEMPRE imprime estado + motivo: nunca un guion mudo.
        self.assertIn("sin motivo declarado", js)

    def test_el_token_no_se_persiste(self):
        """El token vive en memoria: se comprueba el USO, no la mención en un comentario."""
        js = _leer(JS)
        for almacen in ("localStorage", "sessionStorage", "document.cookie"):
            uso = re.search(re.escape(almacen) + r"\s*[.\[]", js)
            self.assertIsNone(uso,
                              f"el portal usa {almacen} (el token debe vivir en memoria)")


class TestSistemaDeDiseno(unittest.TestCase):

    def test_los_tokens_son_la_fuente_unica(self):
        css = _leer(CSS)
        self.assertRegex(css, r'@import\s+url\("\.\./prototipo/tokens\.css"\)',
                         "el portal debe importar los tokens del sistema, no copiarlos")
        self.assertTrue(TOKENS.exists(), "faltan los tokens del sistema")

    def test_radio_cero_y_sin_sombras_ambientales(self):
        css = _leer(CSS)
        for m in re.finditer(r"border-radius:\s*([^;]+);", css):
            valor = m.group(1).strip().lower()
            self.assertIn(valor, ("0", "0px", "var(--radius)"),
                          f"radio distinto de 0px: {valor} (el sistema es de esquina recta)")
        for m in re.finditer(r"box-shadow:\s*([^;]+);", css):
            self.assertIn("var(--shadow-pop)", m.group(1),
                          "sombra fuera de la regla de panel flotante del sistema")

    def test_colores_solo_por_token(self):
        """Ningún color literal suelto salvo los del mástil (documentados)."""
        css = _leer(CSS)
        permitidos = {"#161c20", "#f1f1ef", "#969ca1", "#3b4247", "#2e3438",
                      "#22282c", "#ffffff", "#fff"}
        for m in re.finditer(r"#[0-9a-fA-F]{3,8}\b", css):
            literal = m.group(0).lower()
            self.assertIn(literal, permitidos,
                          f"color literal fuera del mástil institucional: {literal}")

    def test_tipografia_del_sistema(self):
        css = _leer(CSS)
        self.assertIn("var(--f-mono)", css,
                      "los identificadores y coordenadas deben usar la mono del sistema")


class TestEjecucionDelPortal(unittest.TestCase):
    """Ejecuta `portal.js` en un DOM mínimo (Node) y recorre los caminos de pintado.

    El QA estático no puede ver un `ReferenceError` dentro de una función que solo
    corre cuando llega un dato; este arnés sí.
    """

    ARNES = PORTAL / "qa" / "dom_smoke.mjs"

    def test_el_arnes_existe(self):
        self.assertTrue(self.ARNES.exists(), "falta el arnés de ejecución del portal")

    def test_el_portal_se_ejecuta_sin_errores(self):
        import shutil
        import subprocess
        node = shutil.which("node")
        if not node:
            self.skipTest("node no está disponible en este entorno")
        r = subprocess.run([node, str(self.ARNES)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(r.returncode, 0,
                         f"el portal falló al ejecutarse:\n{r.stdout}\n{r.stderr}")
        self.assertIn("ejecutados sin errores", r.stdout or "")

    def test_la_copia_desplegable_se_ejecuta_sin_errores(self):
        """La copia que sirve la app (`public/portal/`) es la que usa el usuario."""
        import shutil
        import subprocess
        node = shutil.which("node")
        if not node:
            self.skipTest("node no está disponible en este entorno")
        r = subprocess.run([node, str(self.ARNES), "--dir", "public/portal"],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=120, cwd=str(ROOT))
        self.assertEqual(r.returncode, 0,
                         f"la copia desplegable falló al ejecutarse:\n{r.stdout}\n{r.stderr}")
        self.assertIn("ejecutados sin errores", r.stdout or "")


class TestCopiaDesplegable(unittest.TestCase):
    """`public/portal/` es lo que el usuario ve en `/portal/`: debe ser EXACTAMENTE
    la fuente (`ui/portal/`) más los tokens del sistema. Si alguien edita la copia a
    mano, esta prueba falla y obliga a regenerarla."""

    def test_la_copia_desplegable_esta_sincronizada(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import publicar_portal
        for destino, esperado in publicar_portal.artefactos().items():
            self.assertTrue(destino.exists(),
                            f"falta la copia desplegable {destino.relative_to(ROOT)}: "
                            "ejecute `python scripts/publicar_portal.py`")
            actual = destino.read_text(encoding="utf-8")
            self.assertEqual(actual, esperado,
                             f"{destino.relative_to(ROOT)} no coincide con la fuente: "
                             "regénere con `python scripts/publicar_portal.py`")

    def test_el_import_de_tokens_resuelve_en_la_copia(self):
        css = (ROOT / "public" / "portal" / "portal.css").read_text(encoding="utf-8")
        self.assertIn('@import url("tokens.css");', css)
        self.assertTrue((ROOT / "public" / "portal" / "tokens.css").exists(),
                        "la copia desplegable no trae los tokens del sistema")

    def test_la_consola_enlaza_la_experiencia(self):
        consola = (ROOT / "public" / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="/portal/"', consola,
                      "la consola operativa no enlaza el portal DICTUS")


if __name__ == "__main__":
    unittest.main(verbosity=2)

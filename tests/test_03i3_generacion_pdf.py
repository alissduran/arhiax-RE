# -*- coding: utf-8 -*-
"""03I.3 — Generación del dictamen: que SIEMPRE termine y que el PDF salga.

Síntoma reportado: «intento generar el dictamen y se queda pensando, no se descarga».
El giro era SILENCIOSO: la consola encolaba el trabajo en QStash y luego consultaba su
estado cada 5 s hasta 78 veces (6,5 min). Si la entrega de la cola no llegaba al worker
(firma de QStash sin configurar, URL inalcanzable) o el worker moría por el límite de
tiempo de la plataforma, el trabajo se quedaba en `pendiente` para siempre y el usuario
veía un «generando…» eterno, sin error y sin PDF.

Estas pruebas fijan las tres garantías que cierran ese agujero:

  1. **Estado terminal**: un trabajo que supera el límite se declara INTERRUMPIDO con
     motivo y sugerencia (el cliente puede informar y recuperarse).
  2. **Auto-recuperación en el cliente**: progreso visible, empuje directo del worker y
     caída a generación síncrona, con espera ACOTADA.
  3. **Portabilidad del directorio de trabajo**: la generación no depende de `/tmp`
     (en Windows `Path('/tmp')` es `C:\\tmp` y la compilación fallaba con PermissionError).
"""
import os
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))

CONSOLA = ROOT / "public" / "index.html"
API = ROOT / "api" / "index.py"
JOB_QA = "qa-test-03i3-0000-0000-000000000000"


class TestEstadoTerminalDelTrabajo(unittest.TestCase):

    def setUp(self):
        os.environ.setdefault("ARHIAX_ENV", "test")
        os.environ.setdefault("ARHIAX_AUTH_SECRET", "qa-local-secret")
        os.environ.setdefault("ARHIAX_ADMIN_PASSWORD", "dev-only-not-a-real-password")
        import index
        self.index = index
        conn = index.get_db_connection()
        conn.execute("DELETE FROM trabajos_pdf WHERE id = ?", (JOB_QA,))
        conn.commit()
        conn.close()

    tearDown = setUp

    def test_trabajo_nuevo_informa_edad_y_no_esta_vencido(self):
        self.index._crear_trabajo(JOB_QA, "pendiente")
        r = self.index.obtener_trabajo_pdf(JOB_QA, {"username": "qa", "rol": "admin"})
        self.assertEqual(r["estado"], "pendiente")
        self.assertIsInstance(r["edad_s"], int)
        self.assertLess(r["edad_s"], 10)
        self.assertIs(r["vencido"], False)

    def test_trabajo_vencido_se_declara_interrumpido_con_motivo(self):
        """El caso que producía el giro infinito: cola que nunca llega al worker."""
        self.index._crear_trabajo(JOB_QA, "pendiente")
        import datetime as modulo_tiempo
        viejo = (modulo_tiempo.datetime.now()
                 - modulo_tiempo.timedelta(
                     seconds=self.index.TRABAJO_PDF_VENCIDO_S + 45)).isoformat()
        conn = self.index.get_db_connection()
        conn.execute("UPDATE trabajos_pdf SET creado = ? WHERE id = ?", (viejo, JOB_QA))
        conn.commit()
        conn.close()

        r = self.index.obtener_trabajo_pdf(JOB_QA, {"username": "qa", "rol": "admin"})
        self.assertEqual(r["estado"], "interrumpido")
        self.assertIs(r["vencido"], True)
        self.assertGreaterEqual(r["edad_s"], self.index.TRABAJO_PDF_VENCIDO_S)
        self.assertTrue(r.get("error"), "el estado terminal debe explicar el motivo")
        self.assertTrue(r.get("sugerencia"), "el estado terminal debe decir cómo seguir")

    def test_el_limite_esta_declarado_y_es_acotado(self):
        limite = self.index.TRABAJO_PDF_VENCIDO_S
        self.assertGreaterEqual(limite, 60)
        self.assertLessEqual(limite, 300, "un límite mayor deja al usuario girando demasiado")

    def test_el_worker_no_recompila_un_trabajo_ya_listo(self):
        """Idempotencia: la cola y el navegador pueden empujar el mismo trabajo."""
        fuente = API.read_text(encoding="utf-8")
        self.assertIn("idempotente", fuente,
                      "el worker debe devolver el resultado existente sin recompilar")
        self.assertRegex(fuente, r'if _fila and _fila\["estado"\] == "listo"')


class TestPortabilidadDelDirectorioDeTrabajo(unittest.TestCase):

    def test_respeta_arhiax_tmp_dir(self):
        os.environ.setdefault("ARHIAX_ENV", "test")
        import index
        previo = os.environ.get("ARHIAX_TMP_DIR")
        try:
            destino = ROOT / "tmp_arhiax_prueba"
            os.environ["ARHIAX_TMP_DIR"] = str(destino)
            d = index._dir_trabajo("qa-03i3")
            self.assertTrue(str(d).startswith(str(destino)), f"no respetó ARHIAX_TMP_DIR: {d}")
            self.assertTrue(d.exists())
        finally:
            if previo is None:
                os.environ.pop("ARHIAX_TMP_DIR", None)
            else:
                os.environ["ARHIAX_TMP_DIR"] = previo

    def test_la_generacion_usa_el_directorio_portable(self):
        """`Path('/tmp') / f"run_…"` fijo rompía la compilación en Windows (C:\\tmp no
        es escribible). La generación debe pasar por `_dir_trabajo`."""
        fuente = API.read_text(encoding="utf-8")
        self.assertNotIn('Path("/tmp") / f"run_', fuente,
                         "la generación volvió a fijar /tmp como directorio de trabajo")
        self.assertRegex(fuente, r"temp_run_dir = _dir_trabajo\(run_id\)")

    def test_el_directorio_portable_tiene_respaldo_local(self):
        """Sin `/tmp` (Windows) debe caer en un directorio DENTRO del proyecto."""
        fuente = API.read_text(encoding="utf-8")
        inicio = fuente.index("def _dir_trabajo")
        cuerpo = fuente[inicio:inicio + 900]
        self.assertIn("ARHIAX_TMP_DIR", cuerpo)
        self.assertIn('os.path.isdir("/tmp")', cuerpo)
        self.assertIn('"tmp_arhiax"', cuerpo)


class TestAutoRecuperacionEnLaConsola(unittest.TestCase):
    """El cliente no puede quedarse girando: progreso, empuje del worker y síncrono."""

    @classmethod
    def setUpClass(cls):
        cls.js = CONSOLA.read_text(encoding="utf-8")

    def test_hay_espera_acotada(self):
        self.assertIn("ESPERA_MAX_S", self.js)
        m = re.search(r"const ESPERA_MAX_S = (\d+)", self.js)
        self.assertIsNotNone(m, "no se declaró la espera máxima")
        self.assertLessEqual(int(m.group(1)), 180,
                             "esperar más de 3 minutos sin PDF es el defecto reportado")

    def test_empuja_el_worker_directamente(self):
        self.assertIn("/api/v1/pdf/worker", self.js,
                      "la consola debe poder empujar el trabajo si la cola no entrega")
        self.assertIn("construirPayloadTrabajo", self.js)
        self.assertIn("certificado_b64", self.js,
                      "el empuje directo debe llevar el CTL (si no, el dictamen sale sin análisis registral)")

    def test_muestra_progreso_con_tiempo(self):
        self.assertRegex(self.js, r"Generando el dictamen · \$\{ultimoEstado\} · \$\{seg\} s")

    def test_cae_a_generacion_sincrona(self):
        self.assertIn("formData.delete('async_')", self.js)
        self.assertIn("no completó en ${ESPERA_MAX_S} s", self.js)

    def test_reconoce_el_estado_terminal_interrumpido(self):
        self.assertIn("'interrumpido'", self.js)
        m = re.search(r"regex|/\^\(El servidor no pudo compilar", self.js)
        self.assertIsNotNone(m, "el cliente debe distinguir un estado terminal de un fallo de red")

    def test_no_reintenta_en_bucle_infinito(self):
        self.assertNotRegex(self.js, r"while\s*\(\s*true\s*\)",
                            "ningún bucle infinito en la generación")


if __name__ == "__main__":
    unittest.main(verbosity=2)

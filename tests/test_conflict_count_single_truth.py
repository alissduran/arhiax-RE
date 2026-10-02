# -*- coding: utf-8 -*-
"""BLOCK 1.1 · A+B — UNA SOLA VERDAD PARA EL RECUENTO DE CONFLICTOS (prueba BLOQUEANTE).

El ejecutivo del folio 040-646406 imprimía DOS recuentos con la misma palabra
«atributo(s)»:

  · `2 atributo(s) requieren reconciliación histórica` — conflictos VERDADEROS
    (`TRUE_CONFLICT`, las siete condiciones): `altura_maxima`, `coordenada`.
  · `6 atributo(s) con resultados incompatibles entre versiones del expediente` —
    la métrica DISTINTA de atributos con versiones rivales comparadas (2 conflictos
    verdaderos + 4 diferencias materiales que el propio expediente YA EXPLICA:
    `amenaza` por precedencia declarada, `titulares` por normalización, `tratamiento`
    por cambio histórico y `uso_pot` por semántica distinta).

CASO B: el «6» no es residuo de código muerto (se calculaba en vivo, pero con el
RÓTULO legacy), es una métrica distinta y válida. Se conservan AMBAS con rótulos
inequívocamente distintos, y las dos salen de la MISMA función canónica
(`dictus_historia.get_true_conflict_summary`).

Esta prueba NO hardcodea el recuento: lo DERIVA del objeto canónico y lo compara con
el PDF físico. Se ejerce sobre los artefactos REALES del Golden, sin fixtures.
"""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))

import dictus_ejecutivo as de  # noqa: E402
import dictus_historia as dh  # noqa: E402


GOLDEN = ROOT / "docs" / "forensics" / "040-646406" / "dictus_2b"
RUN_STATE_P = GOLDEN / "DICTUS_RUN_STATE_040-646406.json"
MANIFEST_P = GOLDEN / "DICTUS_MANIFEST_040-646406.json"
EJECUTIVO_P = GOLDEN / "DICTUS_EJECUTIVO_040-646406.pdf"

# Frase LEGACY que este bloque elimina: afirmaba «incompatibles» para atributos que el
# criterio canónico ya explica, y competía con el rótulo de conflictos.
FRASE_LEGACY_INCOMPATIBLES = "atributo(s) con resultados incompatibles"
ROTULO_LEGACY_CONFLICTO = "atributo(s) requieren reconciliación"

# Rótulo INEQUÍVOCO de la métrica distinta (caso B).
ROTULO_COMPARADOS = "atributo(s) comparados históricamente"


def _paginas_texto(ruta: Path):
    """Texto REAL del PDF, página por página (pypdf: la misma librería del revisor)."""
    from pypdf import PdfReader
    return [p.extract_text() or "" for p in PdfReader(str(ruta)).pages]


class RecuentoCanonicoTest(unittest.TestCase):
    """Una sola verdad: `true_conflict_count == len(true_conflicts)` en las 4 etapas."""

    @classmethod
    def setUpClass(cls):
        cls.rs = json.loads(RUN_STATE_P.read_text(encoding="utf-8"))
        cls.manifest = json.loads(MANIFEST_P.read_text(encoding="utf-8"))
        cls.modelo = cls.manifest["modelo"]
        cls.hist = cls.rs["historical_consistency"]
        # Derivado de la FUENTE canónica (no de un contador persistido).
        cls.canonico = dh.get_true_conflict_summary(cls.hist)
        cls.paginas = _paginas_texto(EJECUTIVO_P)
        cls.texto = "\n".join(cls.paginas)

    # ── 1 · la invariante del objeto canónico ────────────────────────────────────
    def test_true_conflict_count_equals_len_true_conflicts(self):
        """`true_conflict_count == len(true_conflicts)`: nunca dos contadores sueltos."""
        s = self.canonico
        self.assertIn("true_conflicts", s)
        self.assertIn("true_conflict_count", s)
        self.assertEqual(s["true_conflict_count"], len(s["true_conflicts"]))
        self.assertEqual(s["attributes_compared_count"], len(s["attributes_compared"]))
        # la métrica distinta CONTIENE los conflictos verdaderos, y no los confunde
        self.assertTrue(set(s["true_conflicts"]) <= set(s["attributes_compared"]))
        # el recuento sale de la LISTA de conflictos abiertos, no de `requieren_revision`
        self.assertEqual(sorted(s["true_conflicts"]),
                         sorted(c["atributo"] for c in self.hist["conflictos_abiertos"]))
        material = sorted(r["atributo"] for r in (self.hist.get("requieren_revision") or [])
                          if r.get("diferencia_material"))
        self.assertNotEqual(material, s["true_conflicts"],
                            "el recuento NO puede salir de len(requieren_revision)")

    # ── 2 · RUNSTATE ────────────────────────────────────────────────────────────
    def test_runstate_persists_true_conflict_count(self):
        """Path y valor REALES en el RunState de la corrida."""
        self.assertIn("historical_consistency_summary", self.rs,
                      "el RunState debe PERSISTIR el resumen en su raíz")
        s = self.rs["historical_consistency_summary"]
        self.assertEqual(s["true_conflict_count"], len(s["true_conflicts"]))
        self.assertEqual(s["true_conflict_count"], self.canonico["true_conflict_count"])
        self.assertEqual(sorted(s["true_conflicts"]), sorted(self.canonico["true_conflicts"]))
        self.assertEqual(s["attributes_compared_count"], self.canonico["attributes_compared_count"])
        self.assertEqual(s["requires_action"], bool(s["true_conflicts"]))

    # ── 3 · MANIFEST ────────────────────────────────────────────────────────────
    def test_manifest_projects_same_conflict_count(self):
        """El manifest NO replica el informe completo: PROYECTA el mismo resumen."""
        self.assertIn("historical_consistency_summary", self.manifest)
        self.assertIn("historical_consistency_summary", self.modelo)
        man = self.manifest["historical_consistency_summary"]
        mod = self.modelo["historical_consistency_summary"]
        rs = self.rs["historical_consistency_summary"]
        self.assertEqual(man, mod, "manifest y modelo deben proyectar el MISMO objeto")
        self.assertEqual(man["true_conflict_count"], rs["true_conflict_count"])
        self.assertEqual(sorted(man["true_conflicts"]), sorted(rs["true_conflicts"]))
        self.assertEqual(man["attributes_compared_count"], rs["attributes_compared_count"])
        # el contrato del manifest declara la lista de conflictos, y su longitud coincide
        self.assertEqual(len(self.modelo["historical_consistency"]["conflictos_abiertos"]),
                         man["true_conflict_count"])
        # el manifest NO replica `requieren_revision` (contrato declarado, no persistido)
        self.assertNotIn("requieren_revision",
                         self.modelo["historical_consistency"],
                         "si el contrato cambia, esta prueba debe actualizarse a mano")

    # ── 4 · DOCUMENT MODEL ──────────────────────────────────────────────────────
    def test_document_model_uses_same_conflict_count(self):
        """El modelo de documento transporta el resumen al hash maestro."""
        mod = self.modelo["historical_consistency_summary"]
        self.assertEqual(mod["true_conflict_count"], len(mod["true_conflicts"]))
        self.assertEqual(mod["true_conflict_count"], self.canonico["true_conflict_count"])
        self.assertEqual(sorted(mod["true_conflicts"]),
                         sorted(self.canonico["true_conflicts"]))
        # el modelo es la entrada del hash maestro: el resumen está DENTRO
        self.assertTrue(self.modelo.get("master_hash"))
        self.assertEqual(mod["version"], dh.RESUMEN_CONFLICTOS_VERSION)

    # ── 5 · PDF: el valor llega RESUELTO y se imprime tal cual ──────────────────
    def test_pdf_prints_canonical_true_conflict_count(self):
        """El PDF imprime el recuento DERIVADO del objeto canónico (sin hardcodear)."""
        n = self.canonico["true_conflict_count"]
        self.assertEqual(n, len(self.canonico["true_conflicts"]))
        # contexto correcto: la tarjeta de coherencia de la página 1, con SU rótulo
        contexto = (f"{n} {dh.ROTULO_CONFLICTO_VERDADERO}")
        pagina1 = " ".join(self.paginas[0].split())
        self.assertIn(contexto, pagina1,
                      f"la página 1 debe declarar «{contexto}»")
        # y la métrica distinta se imprime con SU rótulo (caso B: ambas conviven)
        cmp_n = self.canonico["attributes_compared_count"]
        self.assertIn(f"{cmp_n} {dh.ROTULO_ATRIBUTOS_COMPARADOS}", pagina1,
                      "la métrica de atributos comparados debe llevar su propio rótulo")
        self.assertNotEqual(cmp_n, n, "las dos métricas deben ser distinguibles en el PDF")

    # ── 6 · PDF: el rótulo legacy no puede reaparecer como recuento vigente ─────
    def test_pdf_does_not_print_legacy_conflict_count_as_current(self):
        """La frase legacy no está, y ningún recuento compartido se imprime."""
        self.assertNotIn(FRASE_LEGACY_INCOMPATIBLES, self.texto,
                         "la frase legacy de «resultados incompatibles» no puede volver")
        n = self.canonico["true_conflict_count"]
        cmp_n = self.canonico["attributes_compared_count"]
        if n != cmp_n:
            # El rótulo de CONFLICTOS solo puede acompañar al recuento verdadero.
            self.assertNotIn(f"{cmp_n} {ROTULO_LEGACY_CONFLICTO}", self.texto,
                             f"«{cmp_n} {ROTULO_LEGACY_CONFLICTO}» sería el rótulo "
                             f"de conflictos sobre la métrica de atributos comparados")
            self.assertIn(f"{n} {ROTULO_LEGACY_CONFLICTO}", self.texto)
        # el rótulo de conflictos aparece UNA sola vez como recuento vigente
        rotulados = re.findall(r"(\d+)\s+" + re.escape(ROTULO_LEGACY_CONFLICTO), self.texto)
        self.assertEqual(sorted(set(rotulados)), [str(n)],
                         f"el rótulo de conflictos solo admite {n}: se leyó {rotulados}")

    # ── 7 · el PDF NO calcula: falla si el valor no llega resuelto ──────────────
    def test_pdf_does_not_recompute_the_counter(self):
        """Sin valor resuelto el renderer FALLA: nunca imprime un sustituto."""
        with self.assertRaises(de.RecuentoNoResuelto):
            de._recuento_coherencia({})
        with self.assertRaises(de.RecuentoNoResuelto):
            de._recuento_coherencia({"coherencia_resumen": {"diferencias_declaradas": 4}})
        with self.assertRaises(de.RecuentoNoResuelto):
            de.TarjetaCoherencia([{"atributo": "a"}, {"atributo": "b"}] * 3, pagina=1)
        # con el valor resuelto, el renderer lo imprime TAL CUAL (no lo recalcula)
        rec = de._recuento_coherencia({
            "coherencia_resumen": {"true_conflict": 2, "diferencias_declaradas": 4,
                                   "attributes_compared_count": 6}})
        self.assertEqual(rec["n_conflictos"], 2)
        self.assertEqual(rec["n_diferencias_declaradas"], 4)
        self.assertEqual(rec["rotulo_conflicto"], dh.ROTULO_CONFLICTO_VERDADERO)

    # ── 8 · cuadro E2E: las cuatro etapas coinciden ─────────────────────────────
    def test_all_stages_report_the_same_pair(self):
        """RUNSTATE == MANIFEST == MODEL == PDF para (count, attributes)."""
        rs = self.rs["historical_consistency_summary"]
        man = self.manifest["historical_consistency_summary"]
        mod = self.modelo["historical_consistency_summary"]
        n = self.canonico["true_conflict_count"]
        attrs = sorted(self.canonico["true_conflicts"])
        for nombre, s in (("RUNSTATE", rs), ("MANIFEST", man), ("DOCUMENT_MODEL", mod)):
            self.assertEqual(s["true_conflict_count"], n, f"{nombre}: recuento distinto")
            self.assertEqual(sorted(s["true_conflicts"]), attrs, f"{nombre}: atributos distintos")
        # el PDF imprime ese mismo par en la página 1
        pagina1 = " ".join(self.paginas[0].split())
        self.assertIn(f"{n} {dh.ROTULO_CONFLICTO_VERDADERO}", pagina1)

    # ── 9 · sensibilidad: el contador legacy persistido no puede divergir ───────
    def test_legacy_persisted_counter_cannot_diverge(self):
        """`recuento_conflictos.total` es la misma lista: si divergiera, el resumen lo denuncia."""
        total = (self.hist.get("recuento_conflictos") or {}).get("total")
        if total is None:
            self.skipTest("la corrida no persistió `recuento_conflictos`")
        self.assertEqual(int(total), self.canonico["true_conflict_count"])
        roto = json.loads(json.dumps(self.hist))
        roto["recuento_conflictos"]["total"] = int(total) + 1
        with self.assertRaises(AssertionError):
            dh.get_true_conflict_summary(roto)


if __name__ == "__main__":
    unittest.main(verbosity=2)

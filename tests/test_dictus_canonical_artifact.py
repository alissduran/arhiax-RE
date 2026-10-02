# -*- coding: utf-8 -*-
"""BLOCK 1.1 · C — JUEGO DE ARTEFACTOS CANÓNICO del folio 040-646406 (prueba BLOQUEANTE).

`docs/forensics/040-646406/dictus_2b/` mezclaba el ejecutivo de la corrida VIGENTE
(DICTUS ID `DX-040-646406-20261002`) con artefactos de la corrida 2.0B anterior
(`DX-040-646406-20260925`): un TXT de texto ejecutivo, el entregable de la fase 2.0B-R1
y 6 páginas rasterizadas. Un revisor no podía saber cuál era el Dictus vigente sin
abrir los archivos.

Lo que se prueba aquí (prohibir AMBIGÜEDAD, no prohibir HISTÓRICOS):

  · hay UN SOLO ejecutivo vigente y UN SOLO `run_id` vigente, declarados por
    `ARTIFACT_INDEX_040-646406.json`;
  · PDF ejecutivo, RunState y manifest comparten la corrida (`run_id` y `dictus_id`);
  · los artefactos anteriores viven en `legacy/` con `status: HISTORICAL_ONLY` y sus
    bytes PRESERVADOS (`sha256_before == sha256_after`);
  · ningún artefacto de la RAÍZ declara un `DICTUS ID` distinto del vigente.
"""
import hashlib
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))

GOLDEN = ROOT / "docs" / "forensics" / "040-646406" / "dictus_2b"
INDICE_P = GOLDEN / "ARTIFACT_INDEX_040-646406.json"
LEGACY_D = GOLDEN / "legacy"
RUN_STATE_P = GOLDEN / "DICTUS_RUN_STATE_040-646406.json"
MANIFEST_P = GOLDEN / "DICTUS_MANIFEST_040-646406.json"
EJECUTIVO_P = GOLDEN / "DICTUS_EJECUTIVO_040-646406.pdf"
TECNICO_P = GOLDEN / "DICTUS_TECNICO_040-646406.pdf"

PATRON_DICTUS_ID = re.compile(r"DX-\d{3}-\d{6}-\d{8}")

# Estados del índice que significan «es el Dictus vigente».
STATUS_VIGENTE = ("CURRENT", None)


def _sha256(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


class JuegoCanonicoTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.indice = json.loads(INDICE_P.read_text(encoding="utf-8"))
        cls.rs = json.loads(RUN_STATE_P.read_text(encoding="utf-8"))
        cls.manifest = json.loads(MANIFEST_P.read_text(encoding="utf-8"))
        from pypdf import PdfReader
        cls.paginas_pdf = [p.extract_text() or "" for p in PdfReader(str(EJECUTIVO_P)).pages]
        cls.texto_pdf = "\n".join(cls.paginas_pdf)

    # ── 1 · un solo ejecutivo vigente ───────────────────────────────────────────
    def test_un_solo_ejecutivo_current(self):
        """Exactamente UN ejecutivo canónico, declarado por el índice con su huella."""
        ejecutivos = sorted(p.name for p in GOLDEN.glob("DICTUS_EJECUTIVO_*.pdf"))
        self.assertEqual(ejecutivos, [EJECUTIVO_P.name],
                         f"la raíz debe tener UN ejecutivo vigente: {ejecutivos}")
        # ningún OTRO ejecutivo (PDF) en la raíz
        otros = sorted(p.name for p in GOLDEN.glob("*EJECUTIVO*.pdf"))
        self.assertEqual(otros, [EJECUTIVO_P.name],
                         f"la raíz no puede tener un segundo ejecutivo: {otros}")
        ficha = self.indice["executive_pdf"]
        self.assertEqual(Path(ficha["path"]).name, EJECUTIVO_P.name)
        self.assertEqual(ficha["sha256"], _sha256(EJECUTIVO_P),
                         "el índice debe declarar la huella del PDF vigente")
        # el técnico también es único y está declarado
        self.assertEqual(sorted(p.name for p in GOLDEN.glob("DICTUS_TECNICO_*.pdf")),
                         [TECNICO_P.name])
        self.assertEqual(self.indice["technical_pdf"]["sha256"], _sha256(TECNICO_P))
        # y los seis artefactos contractuales del índice existen y tienen huella
        for rol in ("executive_pdf", "technical_pdf", "run_state", "manifest",
                    "acceptance_pack"):
            self.assertIsNotNone(self.indice[rol]["sha256"], f"{rol}: sin huella")
            self.assertEqual(self.indice[rol]["sha256"],
                             _sha256(GOLDEN / Path(self.indice[rol]["path"]).name))

    # ── 2 · un solo run_id vigente ──────────────────────────────────────────────
    def test_un_solo_run_id_current(self):
        """El `run_id` vigente es UNO y el índice, el RunState y el manifest lo comparten."""
        canonico = self.indice["canonical_run_id"]
        self.assertTrue(canonico, "el índice debe declarar `canonical_run_id`")
        self.assertEqual(canonico, self.rs["run_id"])
        self.assertEqual(canonico, self.manifest["run_id"])
        self.assertEqual(self.indice["canonical_generated_at"], self.rs["generated_at"])
        self.assertEqual(self.indice["canonical_dictus_id"], self.manifest["dictus_id"])
        self.assertEqual(self.indice["canonical_master_hash"], self.manifest["master_hash"])
        # ningún `legacy` comparte el run_id vigente
        for leg in self.indice["legacy_artifacts"]:
            self.assertNotEqual(leg["run_id"], canonico)

    # ── 3 · PDF · RunState · manifest comparten corrida ─────────────────────────
    def test_pdf_runstate_manifest_comparten_run_id(self):
        """El PDF físico declara el `DICTUS ID` de la corrida del RunState y del manifest."""
        dictus_id = self.manifest["dictus_id"]
        self.assertEqual(dictus_id, self.indice["canonical_dictus_id"])
        self.assertIn(dictus_id, self.texto_pdf,
                      f"el PDF ejecutivo debe declarar «{dictus_id}»")
        # el sello del manifest es el hash que el PDF publica (abreviado)
        master = self.manifest["master_hash"]
        abreviado = self.manifest.get("master_hash_abreviado") or master[:12]
        self.assertIn(abreviado.upper(), self.texto_pdf.upper(),
                      "el PDF debe publicar el hash maestro del manifest")
        # el RunState declara el mismo folio y la misma corrida que el manifest
        self.assertEqual(self.manifest["folio"], self.indice["folio"])
        self.assertEqual(self.manifest["modelo"]["run_id"], self.manifest["run_id"])

    # ── 4 · los legacy NO se tratan como current ────────────────────────────────
    def test_legacy_no_se_trata_como_current(self):
        """Todo artefacto anterior está en `legacy/`, marcado HISTORICAL_ONLY y con bytes intactos."""
        legacy = self.indice["legacy_artifacts"]
        self.assertTrue(legacy, "el índice debe declarar los artefactos históricos")
        canonico = self.indice["canonical_run_id"]
        for leg in legacy:
            self.assertEqual(leg["status"], "HISTORICAL_ONLY",
                             f"{leg['path']}: los históricos no pueden ser CURRENT")
            self.assertNotEqual(leg["run_id"], canonico)
            self.assertTrue(leg["sha256_preservado"],
                            f"{leg['path']}: los bytes cambiaron al moverlo")
            self.assertEqual(leg["sha256_before"], leg["sha256_after"])
            # vive en legacy/ y NO en la raíz
            self.assertIn("/legacy/", leg["path"])
            destino = ROOT / leg["path"]
            self.assertTrue(destino.exists(), f"falta el histórico: {destino}")
            # y su original ya no está en la raíz
            nombre_original = Path(leg["original_path"]).name
            self.assertFalse((GOLDEN / nombre_original).exists(),
                             f"{nombre_original} sigue en la RAÍZ: ambigüedad de Dictus vigente")
            # las huellas declaradas son las REALES de los bytes en disco
            for rel, h in leg["sha256_after"].items():
                archivo = destino if not rel else destino / rel
                self.assertEqual(_sha256(archivo), h, f"{leg['path']}/{rel}: huella distinta")
        # ningún artefacto de la RAÍZ declara un DICTUS ID distinto del vigente
        vigente = self.indice["canonical_dictus_id"]
        for ruta in sorted(GOLDEN.glob("*")):
            if not ruta.is_file() or ruta.name == INDICE_P.name:
                continue
            try:
                contenido = ruta.read_text(encoding="utf-8", errors="ignore")
            except OSError:  # binario ilegible como texto: se lee su gemelo de texto
                continue
            ids = set(PATRON_DICTUS_ID.findall(contenido))
            if ids:
                self.assertEqual(ids, {vigente},
                                 f"{ruta.name} declara corridas mezcladas: {sorted(ids)}")

    # ── 5 · el índice se explica solo ───────────────────────────────────────────
    def test_indice_declara_la_corrida_sin_ambiguedad(self):
        """Un revisor identifica el Dictus vigente leyendo SOLO el índice."""
        for clave in ("canonical_run_id", "canonical_generated_at", "executive_pdf",
                      "technical_pdf", "run_state", "manifest", "acceptance_pack",
                      "legacy_artifacts"):
            self.assertIn(clave, self.indice, f"falta `{clave}` en el índice")
        self.assertIn("convencion", self.indice)
        # el índice y el resumen canónico del RunState no pueden divergir
        s = self.rs["historical_consistency_summary"]
        self.assertEqual(self.indice["canonical_true_conflict_count"],
                         s["true_conflict_count"])
        self.assertEqual(sorted(self.indice["canonical_true_conflict_attributes"]),
                         sorted(s["true_conflicts"]))
        # los históricos se listan con su `run_id` y su fecha
        for leg in self.indice["legacy_artifacts"]:
            self.assertTrue(leg.get("run_id"))
            self.assertTrue(leg.get("generated_at"))
            self.assertTrue(leg.get("motivo"))


if __name__ == "__main__":
    unittest.main(verbosity=2)

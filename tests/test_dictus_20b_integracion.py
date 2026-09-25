# -*- coding: utf-8 -*-
"""DICTUS 2.0B — Pruebas de INTEGRACIÓN del producto (§19, A–M).

Verifican sobre los artefactos REALES de la corrida integrada (`scripts/dictus_run.py`)
que una sola ejecución produce el Ejecutivo y el Técnico desde el MISMO estado canónico,
con un solo hash maestro, y que el ejecutivo no depende del PDF técnico.
"""
import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))

import dictus_estado as dse      # noqa: E402
import dictus_manifiesto as dm   # noqa: E402

SALIDA = ROOT / "docs" / "forensics" / "040-646406" / "dictus_2b"
FOLIO = "040-646406"
ACEPTACION = SALIDA / f"ACEPTACION_{FOLIO}.json"
MANIFEST = SALIDA / f"DICTUS_MANIFEST_{FOLIO}.json"
RUN_STATE = SALIDA / f"DICTUS_RUN_STATE_{FOLIO}.json"
EJECUTIVO = SALIDA / f"DICTUS_EJECUTIVO_{FOLIO}.pdf"
TECNICO = SALIDA / f"DICTUS_TECNICO_{FOLIO}.pdf"


def _j(p: Path):
    if not p.exists():
        raise unittest.SkipTest(f"falta {p.name}: ejecute `python scripts/dictus_run.py`")
    return json.loads(p.read_text(encoding="utf-8"))


class TestCorridaUnica(unittest.TestCase):
    """A · B · C: una corrida, dos documentos, una sola verdad."""

    def test_a_una_corrida_genera_ejecutivo_y_tecnico_del_mismo_run(self):
        ace = _j(ACEPTACION)
        self.assertTrue(EJECUTIVO.exists() and TECNICO.exists())
        self.assertTrue(ace["run_id"])
        self.assertIn("DICTUS_EJECUTIVO", ace["executive_pdf"])
        self.assertIn("DICTUS_TECNICO", ace["technical_pdf"])
        # Los dos SHA pertenecen a la MISMA corrida (registrados juntos).
        self.assertEqual(len(ace["executive_pdf_sha256"]), 64)
        self.assertEqual(len(ace["technical_pdf_sha256"]), 64)

    def test_b_ambos_comparten_dictus_id_fecha_identidad_y_hash(self):
        ace, man, rs = _j(ACEPTACION), _j(MANIFEST), _j(RUN_STATE)
        self.assertEqual(ace["dictus_id"], man["dictus_id"])
        self.assertEqual(ace["generated_at"], man["generated_at"])
        self.assertEqual(ace["master_hash"], man["master_hash"])
        self.assertEqual(rs["run_id"], man["run_id"], "el estado y el manifest son de la misma corrida")
        self.assertEqual(man["modelo"]["document_identity"]["dictus_id"], man["dictus_id"])
        # La identidad que imprime el ejecutivo viene del estado, no del PDF.
        pi = rs["property_identity"]
        self.assertEqual(man["modelo"]["canonical_property_identity"]["folio"], pi["folio"])

    def test_c_el_ejecutivo_no_lee_el_pdf_tecnico(self):
        """§1: prohibido PDF técnico → texto → ejecutivo."""
        for nombre in ("dictus_secciones.py", "dictus_ejecutivo.py", "dictus_estado.py",
                       "dictus_manifiesto.py"):
            fuente = (ROOT / "api" / nombre).read_text(encoding="utf-8")
            for prohibido in ("pymupdf", "cargar_texto_pdf", "fitz", "PdfReader"):
                self.assertNotIn(prohibido, fuente,
                                 f"{nombre} no puede leer PDFs: contiene {prohibido!r}")
        ace = _j(ACEPTACION)
        self.assertEqual(ace.get("nota_hash", "").count("hash") > 0, True)


class TestHashMaestro(unittest.TestCase):
    """D · E · F: determinismo, sensibilidad y orden."""

    @classmethod
    def setUpClass(cls):
        cls.man = _j(MANIFEST)
        cls.modelo = cls.man["modelo"]

    def test_d_reproducible(self):
        import copy
        self.assertEqual(dm.master_hash(copy.deepcopy(self.modelo)),
                         dm.master_hash(self.modelo))
        self.assertEqual(dse.verify_dictus_master_hash(self.man, self.man["master_hash"])["result"],
                         dse.MATCH)
        self.assertEqual(self.man["master_manifest_version"], dm.MASTER_MANIFEST_VERSION)

    def test_e_cambiar_un_hecho_material_cambia_el_hash(self):
        import copy
        base = dm.master_hash(self.modelo)
        for ruta, valor in ((("valuation", "consolidado"), 1),
                            (("canonical_property_identity", "nupre"), "OTRO"),
                            (("findings",), [{"severidad": "ALTO", "titulo": "nuevo"}])):
            m = copy.deepcopy(self.modelo)
            if len(ruta) == 1:
                m[ruta[0]] = valor
            else:
                m[ruta[0]][ruta[1]] = valor
            self.assertNotEqual(dm.master_hash(m), base, f"no cambió al alterar {ruta}")

    def test_f_reordenar_claves_no_cambia_el_hash(self):
        import random
        base = dm.master_hash(self.modelo)

        def reordenar(o):
            if isinstance(o, dict):
                items = list(o.items())
                random.shuffle(items)
                return {k: reordenar(v) for k, v in items}
            if isinstance(o, list):
                return [reordenar(x) for x in o]
            return o

        for _ in range(3):
            self.assertEqual(dm.master_hash(reordenar(self.modelo)), base)

    def test_verificador_responde_los_tres_estados(self):
        self.assertEqual(dse.verify_dictus_master_hash(self.man, "x")["result"], dse.MISMATCH)
        self.assertEqual(dse.verify_dictus_master_hash(None, "x")["result"],
                         dse.INVALID_MANIFEST)
        self.assertEqual(dse.verify_dictus_master_hash({"foo": 1}, "x")["result"],
                         dse.INVALID_MANIFEST)


class TestPoiEnElEstado(unittest.TestCase):
    """G · H · I: los ítems viajan en el estado y el ejecutivo no inventa."""

    @classmethod
    def setUpClass(cls):
        cls.rs = _j(RUN_STATE)

    def test_g_los_items_de_poi_viajan_en_el_estado(self):
        poi = self.rs["poi_state"]
        self.assertIn("items", poi)
        self.assertEqual(poi["item_count"], len(poi["items"]))
        if not poi["items"]:
            self.skipTest("la corrida no obtuvo ítems de equipamiento")
        for it in poi["items"]:
            for campo in dse.POI_ITEM_FIELDS:
                self.assertIn(campo, it, f"falta el campo {campo} del contrato de ítem")
            self.assertTrue(it["name"], "un ítem sin nombre no puede viajar")
            self.assertEqual(it["status"], "OBTENIDO")
        con_dist = [i for i in poi["items"] if i["distance_m"] is not None]
        for i in con_dist:
            self.assertGreater(i["distance_m"], 0)
            self.assertTrue(i["walking_time_estimate"])
        for cat in poi["por_categoria"].values():
            self.assertIsInstance(cat["count"], int)

    def test_h_el_ejecutivo_muestra_distancias_reales_si_existen(self):
        import pymupdf
        poi = self.rs["poi_state"]
        if not poi.get("distance_available"):
            self.skipTest("la corrida no declaró distancias")
        with pymupdf.open(str(EJECUTIVO)) as d:
            p5 = " ".join(list(d)[4].get_text().split())
        self.assertIn("más cercano:", p5)
        self.assertRegex(p5, r"más cercano: \d+ m")
        self.assertNotIn("DISTANCIA NO DISPONIBLE", p5)

    def test_i_si_no_hay_distancia_no_se_inventa(self):
        """Con un estado sin distancias, la página 5 lo declara y no imprime metros."""
        import pymupdf
        import dictus_ejecutivo as de
        import dictus_secciones as sec
        rs = json.loads(json.dumps(self.rs))
        for it in rs["poi_state"]["items"]:
            it["distance_m"] = None
            it["walking_time_estimate"] = None
        for cat in rs["poi_state"]["por_categoria"].values():
            cat["mas_cercano_m"] = None
        rs["poi_state"]["distance_available"] = False
        modelo = dm.construir_documento_maestro(rs, historial={}, folio=FOLIO)
        secciones = sec.desde_estado(rs, modelo, {})
        destino = ROOT / "tmp_dictus_2b" / "sin_distancias.pdf"
        destino.parent.mkdir(parents=True, exist_ok=True)
        de.render(modelo, secciones, destino)
        with pymupdf.open(str(destino)) as d:
            p5 = " ".join(list(d)[4].get_text().split())
        self.assertIn("DISTANCIA NO DISPONIBLE", p5)
        self.assertNotRegex(p5, r"más cercano: \d+ m")


class TestPortalYCriterios(unittest.TestCase):
    """J · K · L · M."""

    def test_j_el_portal_muestra_el_mismo_hash_maestro(self):
        man = _j(MANIFEST)
        publicado = ROOT / "public" / "dictus" / f"DICTUS_MANIFEST_{FOLIO}.json"
        self.assertTrue(publicado.exists(), "el manifest debe publicarse con la aplicación")
        self.assertEqual(json.loads(publicado.read_text(encoding="utf-8"))["master_hash"],
                         man["master_hash"])
        js = (ROOT / "ui" / "portal" / "portal.js").read_text(encoding="utf-8")
        self.assertIn("DICTUS_MANIFEST_", js)
        self.assertIn("master_hash", js)
        self.assertIn("Ver trazabilidad", (ROOT / "ui" / "portal" / "index.html").read_text(
            encoding="utf-8"))

    def test_k_el_ejecutivo_no_excede_seis_paginas(self):
        import pymupdf
        with pymupdf.open(str(EJECUTIVO)) as d:
            self.assertLessEqual(d.page_count, 6, "límite duro de 6 páginas")
            self.assertEqual(d.page_count, 6)
        self.assertEqual(_j(ACEPTACION)["executive_page_count"], 6)

    def test_l_todos_los_hallazgos_estan_en_la_pagina_1(self):
        import pymupdf
        rs = _j(RUN_STATE)
        man = _j(MANIFEST)
        with pymupdf.open(str(EJECUTIVO)) as d:
            p1 = " ".join(list(d)[0].get_text().split())
        self.assertIn("Hallazgos que condicionan la decisión", p1)
        total = len(man["modelo"]["findings"])
        self.assertGreaterEqual(total, 1)
        self.assertIn(f"{total} hallazgo(S) MATERIAL(ES)".lower(), p1.lower(),
                      "la página 1 debe declarar cuántos hallazgos contiene")
        # Cada hallazgo del estado aparece por su título en la página 1.
        faltan = [f["titulo"][:26] for f in man["modelo"]["findings"]
                  if f["titulo"][:26] not in p1]
        self.assertEqual(faltan, [], f"hallazgos fuera de la página 1: {faltan}")
        self.assertIn("Afecta:", p1)

    def test_m_sin_tecnicismos_ni_secretos_en_el_ejecutivo(self):
        import pymupdf
        with pymupdf.open(str(EJECUTIVO)) as d:
            texto = " ".join(" ".join(p.get_text().split()) for p in list(d)[:6])
        for prohibido in ("ARHIAX_EVIDENCE_HMAC_KEY", "RuntimeError", "Traceback",
                          "parser_version", "matcher_version", "BBOX", "STRtree",
                          "receipts", "commit ", "feature_id", "http://", "https://",
                          "Exception", "None"):
            self.assertNotIn(prohibido, texto, f"tecnicismo o secreto en el ejecutivo: {prohibido}")


if __name__ == "__main__":
    unittest.main(verbosity=2)

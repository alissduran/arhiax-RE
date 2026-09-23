# -*- coding: utf-8 -*-
"""SAGRILAFT / SCREENING RELEASE GATE — 10 puntos, como pruebas de regresión.

Cada prueba corresponde a un punto del gate de liberación:
  1 NIT / forma societaria -> nunca NATURAL_PERSON
  2 BANCO DE BOGOTÁ S.A. -> LEGAL_ENTITY
  3 DURAN BACCA ALISSON + CC -> NATURAL_PERSON
  4 documento presente -> el dictamen no imprime «ID=N/D» sin declarar el fallo
  5 tipo de sujeto igual en 05, 09 y 16
  6 09 y 16 consumen la misma ScreeningSummary
  7 UIAF/SIREL no es columna ni fuente de screening
  8 sin encabezado legacy «Cumplimiento SAGRILAFT (ficha estructural…»
  9 sin PENDIENTE_PLATAFORMA_EXTERNA cuando hay SourceOutcomes reales
 10 núcleo antiguo -> LEGACY / INVALID_FOR_RELEASE, o generación bloqueada
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))


def _env(**kw):
    from sanctions.contracts import SubjectEnvelope
    base = dict(subject_id="s", raw_name="R", canonical_name="R",
                person_type="LEGAL_ENTITY", document_type=None, document_number=None,
                document_normalized=None, roles=("ACREEDOR_HIPOTECARIO",),
                participation=None, source="CTL", source_reference="CTL",
                identity_confidence="VERIFIED_REGISTRAL", identity_warnings=(),
                screened=True, reason_for_screening="x")
    base.update(kw)
    return SubjectEnvelope(**base)


class TestPuntos1a3TipoDePersona(unittest.TestCase):

    def _tipo(self, raw):
        from sanctions.subjects import parse_person, person_type_from
        d = parse_person(raw)
        return person_type_from(d["canonical_name"], d["document_type"])[0], d

    def test_01_nit_y_forma_societaria_nunca_natural(self):
        for raw in ("BANCO DE BOGOTA S.A. NIT 8600029644",
                    "URBANIZADORA MARVAL S.A.S. (HOY) NIT# 8300120533",
                    "CONSTRUCTORA DEL NORTE LTDA",
                    "FIDUCIARIA S.A."):
            tipo, _ = self._tipo(raw)
            self.assertEqual(tipo, "LEGAL_ENTITY", f"{raw} -> {tipo}")

    def test_02_banco_de_bogota_sa_es_juridica(self):
        tipo, _ = self._tipo("BANCO DE BOGOTÁ S.A.")
        self.assertEqual(tipo, "LEGAL_ENTITY")

    def test_03_persona_natural_con_cc(self):
        tipo, d = self._tipo("DURAN BACCA ALISSON CC# 1045718995X")
        self.assertEqual(tipo, "NATURAL_PERSON")
        self.assertEqual(d["document_type"], "cc")

    def test_sin_senal_no_se_asume_nada(self):
        tipo, d = self._tipo("PEDRO PEREZ GOMEZ")
        self.assertEqual(tipo, "UNKNOWN")
        self.assertIn("DOCUMENT_MISSING", d["identity_warnings"])


class TestPunto4Documento(unittest.TestCase):

    def test_documento_extraido_se_imprime(self):
        from sanctions.subjects import documento_para_dictamen
        self.assertEqual(documento_para_dictamen(_env(document_type="nit",
                                                      document_number="8600029644")),
                         "NIT 8600029644")

    def test_sin_documento_en_la_fuente_no_es_n_d_mudo(self):
        from sanctions.subjects import documento_para_dictamen, DOC_NO_DECLARADO
        self.assertEqual(documento_para_dictamen(_env(identity_warnings=("DOCUMENT_MISSING",))),
                         DOC_NO_DECLARADO)
        self.assertNotEqual(DOC_NO_DECLARADO.strip(), "N/D")

    def test_fallo_de_extraccion_se_declara(self):
        from sanctions.subjects import (documento_para_dictamen, DOC_NO_EXTRAIDO,
                                        W_DOC_EXTRACTION_FAILED)
        self.assertEqual(documento_para_dictamen(
            _env(identity_warnings=("DOCUMENT_MISSING", W_DOC_EXTRACTION_FAILED))),
            DOC_NO_EXTRAIDO)

    def test_el_parser_detecta_el_fallo_cuando_la_fuente_trae_documento(self):
        from sanctions.subjects import parse_person, W_DOC_EXTRACTION_FAILED

        class _ExtractorQueFalla:
            """Finge un extractor de documentos que no captura nada."""

            @staticmethod
            def search(t):
                return None

            @staticmethod
            def sub(repl, t, *a, **k):
                return t

        from sanctions import subjects
        _orig = subjects._RE_DOC
        subjects._RE_DOC = _ExtractorQueFalla()
        try:
            d = parse_person("BANCO DE BOGOTA S.A. NIT# 8600029644")
            self.assertIsNone(d["document_type"])
            self.assertIn(W_DOC_EXTRACTION_FAILED, d["identity_warnings"])
        finally:
            subjects._RE_DOC = _orig

    def test_sin_senal_de_documento_no_se_declara_fallo(self):
        from sanctions.subjects import parse_person, W_DOC_EXTRACTION_FAILED
        d = parse_person("BANCO DE BOGOTA S.A.")
        self.assertNotIn(W_DOC_EXTRACTION_FAILED, d["identity_warnings"])


class TestPuntos5y6UnaSolaVerdad(unittest.TestCase):

    def test_05_los_tres_capitulos_usan_el_mismo_productor(self):
        pc = (ROOT / "api" / "pdf_compiler.py").read_text(encoding="utf-8")
        tb = (ROOT / "api" / "titulux_bridge.py").read_text(encoding="utf-8")
        for fn in ("person_type_label", "documento_para_dictamen"):
            self.assertIn(fn, pc, f"pdf_compiler no usa {fn}")
            self.assertIn(fn, tb, f"titulux_bridge no usa {fn}")

    def test_05_etiquetas_unicas(self):
        from sanctions.subjects import person_type_label
        self.assertEqual(person_type_label(_env(person_type="NATURAL_PERSON")), "Natural")
        self.assertEqual(person_type_label(_env(person_type="LEGAL_ENTITY")), "Jurídica")
        self.assertEqual(person_type_label(_env(person_type="UNKNOWN")), "No determinado")

    def test_06_capitulo_09_y_16_derivan_del_mismo_resumen(self):
        pc = (ROOT / "api" / "pdf_compiler.py").read_text(encoding="utf-8")
        self.assertIn("summary_desde_dict", pc)
        self.assertIn("screening_summary", pc)
        # El capítulo 16.B toma los receipts del MISMO resumen (receipts.py lo deriva).
        rec = (ROOT / "api" / "receipts.py").read_text(encoding="utf-8")
        self.assertIn("screening_summary", rec)


class TestPuntos7a9Prohibiciones(unittest.TestCase):

    def test_07_uiaf_no_es_fuente_activa(self):
        pc = (ROOT / "api" / "pdf_compiler.py").read_text(encoding="utf-8")
        _compacto = pc.replace(" ", "")
        self.assertNotIn('fuentes_activas=("onu","ofac","uiaf"', _compacto)
        self.assertIn('fuentes_activas=("onu","ofac","uk")', _compacto)

    def test_07_uiaf_sigue_documentado_como_canal_de_reporte(self):
        from sanctions import legal
        txt = Path(legal.__file__).read_text(encoding="utf-8")
        self.assertIn("UIAF", txt)   # la doctrina sigue explicando qué es UIAF

    def test_08_sin_encabezado_legacy(self):
        legacy = "Cumplimiento SAGRILAFT (ficha estructural"
        for p in (ROOT / "api").rglob("*.py"):
            self.assertNotIn(legacy.lower(), p.read_text(encoding="utf-8", errors="ignore").lower(),
                             f"{p.name} conserva el encabezado legacy")
        self.assertIn("Screening de Contrapartes y Debida Diligencia",
                      (ROOT / "api" / "pdf_compiler.py").read_text(encoding="utf-8"))

    def test_09_sin_pendiente_plataforma_externa(self):
        for p in (ROOT / "api").rglob("*.py"):
            self.assertNotIn("PENDIENTE_PLATAFORMA_EXTERNA",
                             p.read_text(encoding="utf-8", errors="ignore"),
                             f"{p.name} conserva PENDIENTE_PLATAFORMA_EXTERNA")


class TestPunto10NucleoSancionado(unittest.TestCase):

    def test_nucleo_actual_es_valido_para_liberacion(self):
        from sanctions.release_gate import evaluar_nucleo, STATUS_VALID
        ev = evaluar_nucleo()
        self.assertEqual(ev["status"], STATUS_VALID, ev.get("motivos"))
        self.assertIsNone(ev["marca"])
        self.assertFalse(ev["bloquear"])

    def test_nucleo_antiguo_se_marca_legacy(self):
        from sanctions import release_gate as rg
        _orig = rg.nucleo_vigente
        rg.nucleo_vigente = lambda: rg.NúcleoVigente(
            matcher="sanctions-matcher/1.0.0",
            subject_model="canonical-subjects/1.0.0",
            parsers={"onu_xml": "onu_xml/1.0.0", "ofac_sdn_xml": "ofac_sdn_xml/1.0.0",
                     "uk_sanctions_list_xml": "uk_sanctions_list_xml/1.0.0"},
            sources=("UN_CONSOLIDATED", "OFAC_SDN", "UK_SANCTIONS_LIST"),
            commit=None)
        try:
            ev = rg.evaluar_nucleo()
            self.assertEqual(ev["status"], rg.STATUS_LEGACY)
            self.assertEqual(ev["marca"], rg.MARCA_LEGACY)
            self.assertTrue(ev["motivos"])
        finally:
            rg.nucleo_vigente = _orig

    def test_nucleo_antiguo_bloquea_con_permitir_legacy_false(self):
        from sanctions import release_gate as rg
        _orig = rg.nucleo_vigente
        rg.nucleo_vigente = lambda: rg.NúcleoVigente(
            matcher="sanctions-matcher/1.0.0", subject_model=None, parsers={},
            sources=(), commit=None)
        try:
            ev = rg.evaluar_nucleo(permitir_legacy=False)
            self.assertTrue(ev["bloquear"], "con ARHIAX_PERMITIR_LEGACY=0 debe bloquear")
        finally:
            rg.nucleo_vigente = _orig

    def test_marca_y_filas_legibles(self):
        from sanctions.release_gate import evaluar_nucleo, filas_release_gate
        filas = dict(filas_release_gate(evaluar_nucleo()))
        self.assertIn("Motor de screening", filas)
        self.assertEqual(filas["Motor de screening"], "sanctions-matcher/1.1.0")
        self.assertIn("Modelo de sujetos", filas)
        self.assertIn("Fuentes del núcleo", filas)
        self.assertIn("UN_CONSOLIDATED", filas["Fuentes del núcleo"])

    def test_ancestria_del_nucleo(self):
        from sanctions.release_gate import ancestria_del_nucleo, SAGRILAFT_CORE_COMMIT
        anc = ancestria_del_nucleo()
        self.assertIn(anc["estado"], ("VERIFIED", "NOT_ANCESTOR", "UNKNOWN"))
        self.assertTrue(SAGRILAFT_CORE_COMMIT)


if __name__ == "__main__":
    unittest.main()

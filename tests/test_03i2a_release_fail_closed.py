# -*- coding: utf-8 -*-
"""03I.2A — Release gate fail-closed + consistencia de sujetos + clasificación.

Cubre los cinco problemas residuales del prompt:

  1. el release gate podía fallar internamente y el PDF continuaba  → §8/§9
  2. producción marcaba legacy por defecto en vez de bloquear       → §1/§5/§10/§11
  3. los invariantes 05/09/16 se probaban por presencia de código   → §13/§14
  4. uso económico vs régimen PH se confundían en tipologia.py      → §16-§21
  5. "MARVAL" hardcodeado como señal genérica de persona jurídica   → §15
"""
import io
import os
import shutil
import sys
import unittest
import warnings
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT / "tests"))

warnings.filterwarnings("ignore")

TMP_DIR = ROOT / "tmp_pdf_03i2a"


def _compilar(tmp_name="03i2a.pdf", **fuentes_kw):
    """Compila el PDF del Golden con fuentes mockeadas y DEVUELVE su ruta.

    A diferencia del helper de 03H.2A, este NO borra el archivo: las pruebas de
    fail-closed necesitan comprobar si el PDF final existe o no.
    """
    import catastro_predio
    import geocoder
    import legal_analyzer
    import pdf_compiler
    import integrations.catastro_live as catastro_live
    from test_remediacion_03h2a import (FuentesMock, GOLDEN_CODIGO, GOLDEN_DIRECCION,
                                        GOLDEN_LAT, GOLDEN_LON, GOLDEN_NUPRE)

    fuentes = FuentesMock(**fuentes_kw)
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    out_pdf = TMP_DIR / tmp_name
    if out_pdf.exists():
        out_pdf.unlink()

    analysis = dict(legal_analyzer.analizar_certificado(None))
    analysis.update({
        "folio": "040-646406", "direccion": GOLDEN_DIRECCION,
        "codigo_catastral": GOLDEN_CODIGO, "nupre": GOLDEN_NUPRE,
        "descripcion_ctl": ("APARTAMENTO 430 TORRE 8 CONJUNTO NAPOLI MIRAMAR "
                            "PROPIEDAD HORIZONTAL"),
        "texto_ctl": "APARTAMENTO 430 - PROPIEDAD HORIZONTAL",
        "tipo_predio_snr": "APARTAMENTO",
    })
    record = {
        "id": 1, "folio_matricula": "040-646406", "direccion": GOLDEN_DIRECCION,
        "barrio": "Miramar", "estrato": 4, "area": 58.75,
        "valor_consolidado": None, "sombra_9am_cargada": 0,
        "sombra_3pm_cargada": 0, "mapa_cargado": 0, "acreedor_real": None,
        "certificado_path": None, "ciudad": "barranquilla",
    }
    catastro_predio._CACHE.clear()
    with mock.patch.object(legal_analyzer, "analizar_certificado", return_value=analysis), \
            mock.patch.object(catastro_predio, "_query_capa",
                              side_effect=fuentes.query_capa), \
            mock.patch.object(catastro_predio, "_query_punto",
                              side_effect=fuentes.query_punto), \
            mock.patch.object(geocoder, "geocodificar_direccion",
                              lambda d, ciudad=None: (GOLDEN_LAT, GOLDEN_LON)), \
            mock.patch.object(pdf_compiler, "generate_maps", lambda *a, **k: None), \
            mock.patch.object(catastro_live, "verificar_catastro_barranquilla",
                              lambda *a, **k: {"disponible": False, "numero_predial": None,
                                               "error": "servicio sin respuesta",
                                               "fuente": {}}), \
            mock.patch.object(pdf_compiler, "get_poi_result",
                              lambda *a, **k: {
                                  "items": {c: [] for c in ("Salud", "Educacion",
                                                            "Comercio", "Recreacion")},
                                  "category_status": {c: "NO_MATCH" for c in (
                                      "Salud", "Educacion", "Comercio", "Recreacion")},
                                  "sources_attempted": 1, "sources_succeeded": 1}):
        pdf_compiler.compile_pdf(record, str(out_pdf), assets_dir=TMP_DIR)
    return out_pdf


def _sin_acentos(t: str) -> str:
    """Sin tildes: el corrector ortográfico acentúa la prosa (correcto), así que las
    aserciones sobre texto español deben ignorar tildes."""
    import unicodedata
    nfd = unicodedata.normalize("NFD", t or "")
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


def _texto(pdf_path: Path) -> str:
    import pymupdf
    return " ".join(p.get_text() for p in pymupdf.open(str(pdf_path)))


class _EntornoMixin:
    """Aísla las variables de entorno del gate durante cada prueba."""

    def setUp(self):
        self._env_backup = {k: os.environ.get(k) for k in
                            ("ARHIAX_ENV", "ARHIAX_ALLOW_LEGACY_RELEASE",
                             "ARHIAX_PERMITIR_LEGACY")}
        for k in self._env_backup:
            os.environ.pop(k, None)

    def tearDown(self):
        for k, v in self._env_backup.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    @staticmethod
    def _nucleo_antiguo():
        from sanctions import release_gate as rg
        return rg.NúcleoVigente(matcher="sanctions-matcher/1.0.0",
                                subject_model="canonical-subjects/1.0.0",
                                parsers={"onu_xml": "onu_xml/1.0.0",
                                         "ofac_sdn_xml": "ofac_sdn_xml/1.0.0",
                                         "uk_sanctions_list_xml": "uk_sanctions_list_xml/1.0.0"},
                                sources=("UN_CONSOLIDATED", "OFAC_SDN", "UK_SANCTIONS_LIST"),
                                commit=None)


class TestPoliticaPorEntorno(_EntornoMixin, unittest.TestCase):
    """§1/§5: la política depende del entorno; lo desconocido es conservador."""

    def test_matriz_de_politica(self):
        from release_env import POLITICA_POR_ENTORNO, POLICY_MARK, POLICY_BLOCK
        self.assertEqual(POLITICA_POR_ENTORNO["development"], POLICY_MARK)
        self.assertEqual(POLITICA_POR_ENTORNO["test"], POLICY_MARK)
        self.assertEqual(POLITICA_POR_ENTORNO["staging"], POLICY_BLOCK)
        self.assertEqual(POLITICA_POR_ENTORNO["production"], POLICY_BLOCK)

    def test_entorno_ausente_o_desconocido_es_conservador(self):
        from release_env import normalizar_entorno, ENV_PRODUCTION
        ausente = normalizar_entorno(None)
        self.assertEqual(ausente["environment"], ENV_PRODUCTION)
        self.assertFalse(ausente["declared"])
        self.assertTrue(ausente["assumed_conservative"])
        raro = normalizar_entorno("cualquier-cosa")
        self.assertEqual(raro["environment"], ENV_PRODUCTION)
        self.assertTrue(raro["assumed_conservative"])
        self.assertEqual(raro["raw"], "cualquier-cosa")

    def test_override_solo_relaja_block_a_mark(self):
        from release_env import override_activo
        self.assertFalse(override_activo()["activo"])
        os.environ["ARHIAX_ALLOW_LEGACY_RELEASE"] = "1"
        ov = override_activo()
        self.assertTrue(ov["activo"])
        self.assertEqual(ov["variable"], "ARHIAX_ALLOW_LEGACY_RELEASE")
        self.assertFalse(ov["deprecada"])

    def test_alias_deprecado_sigue_funcionando_y_se_declara(self):
        from release_env import override_activo
        os.environ["ARHIAX_PERMITIR_LEGACY"] = "1"
        ov = override_activo()
        self.assertTrue(ov["activo"])
        self.assertTrue(ov["deprecada"])


class TestContratoDelGate(_EntornoMixin, unittest.TestCase):
    """§2: contrato completo, sin None, con evaluación fallida explícita."""

    def test_nucleo_actual_en_produccion_es_valido(self):
        os.environ["ARHIAX_ENV"] = "production"
        from sanctions.release_gate import evaluar_release_seguro
        ev = evaluar_release_seguro()
        self.assertEqual(ev["evaluation_status"], "EVALUATED")
        self.assertEqual(ev["release_status"], "VALID_FOR_RELEASE")
        self.assertEqual(ev["policy"], "BLOCK")
        self.assertFalse(ev["blocking"])
        self.assertFalse(ev["mark"])
        self.assertIsNone(ev["marca"])

    def test_nucleo_antiguo_en_produccion_bloquea(self):
        os.environ["ARHIAX_ENV"] = "production"
        from sanctions import release_gate as rg
        with mock.patch.object(rg, "nucleo_vigente", lambda: self._nucleo_antiguo()):
            ev = rg.evaluar_release_seguro()
        self.assertEqual(ev["release_status"], "LEGACY_INVALID_FOR_RELEASE")
        self.assertEqual(ev["policy"], "BLOCK")
        self.assertTrue(ev["blocking"])
        self.assertTrue(ev["mark"])

    def test_nucleo_antiguo_en_development_marca(self):
        os.environ["ARHIAX_ENV"] = "development"
        from sanctions import release_gate as rg
        with mock.patch.object(rg, "nucleo_vigente", lambda: self._nucleo_antiguo()):
            ev = rg.evaluar_release_seguro()
        self.assertEqual(ev["policy"], "MARK")
        self.assertFalse(ev["blocking"])
        self.assertTrue(ev["mark"])
        self.assertEqual(ev["marca"], rg.MARCA_LEGACY)

    def test_fallo_interno_nunca_devuelve_none_ni_valido(self):
        def _boom(*a, **k):
            raise RuntimeError("synthetic gate failure")

        for entorno in ("production", "staging", "development", "test"):
            os.environ["ARHIAX_ENV"] = entorno
            from sanctions.release_gate import evaluar_release_seguro
            ev = evaluar_release_seguro(evaluador=_boom)
            self.assertIsNotNone(ev)
            self.assertEqual(ev["evaluation_status"], "EVALUATION_FAILED")
            self.assertEqual(ev["release_status"], "GATE_EVALUATION_FAILED")
            self.assertNotEqual(ev["release_status"], "VALID_FOR_RELEASE")
            self.assertTrue(ev["mark"])
            self.assertIn("synthetic gate failure", " ".join(ev["reasons"]))
            self.assertEqual(ev["blocking"], entorno in ("production", "staging"))

    def test_override_excepcional_en_produccion_marca_pero_nunca_valida(self):
        os.environ["ARHIAX_ENV"] = "production"
        os.environ["ARHIAX_ALLOW_LEGACY_RELEASE"] = "1"
        from sanctions import release_gate as rg
        with mock.patch.object(rg, "nucleo_vigente", lambda: self._nucleo_antiguo()):
            ev = rg.evaluar_release_seguro()
        self.assertEqual(ev["policy"], "MARK")
        self.assertFalse(ev["blocking"])
        self.assertNotEqual(ev["release_status"], "VALID_FOR_RELEASE")
        self.assertEqual(ev["release_status"], "LEGACY_INVALID_FOR_RELEASE")
        self.assertTrue(ev["override_used"])
        self.assertEqual(ev["override_variable"], "ARHIAX_ALLOW_LEGACY_RELEASE")

    def test_recibo_de_liberacion_tiene_todos_los_campos(self):
        os.environ["ARHIAX_ENV"] = "production"
        from sanctions.release_gate import evaluar_release_seguro, filas_receipt_liberacion
        filas = dict(filas_receipt_liberacion(evaluar_release_seguro()))
        for campo in ("release_gate_evaluation_status", "release_gate_status", "release_gate_policy",
                      "environment", "blocking", "override_used", "reasons",
                      "matcher_version", "subject_model_version", "parser_versions",
                      "sources", "ancestry"):
            self.assertIn(campo, filas, f"falta {campo} en el recibo")
        self.assertEqual(filas["release_gate_status"], "VALID_FOR_RELEASE")
        self.assertEqual(filas["matcher_version"], "sanctions-matcher/1.1.0")
        self.assertIn("UN_CONSOLIDATED", filas["sources"])


class TestFailClosedEnElCompilador(_EntornoMixin, unittest.TestCase):
    """§8-§11 (BLOCKING): el PDF final no existe cuando el gate bloquea."""

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    def test_gate_crash_en_produccion_no_deja_pdf(self):
        os.environ["ARHIAX_ENV"] = "production"
        from consistency import InconsistenciaBloqueante
        from sanctions import release_gate as rg

        def _boom(*a, **k):
            raise RuntimeError("synthetic gate failure")

        with mock.patch.object(rg, "evaluar_release_seguro", _boom):
            with self.assertRaises(InconsistenciaBloqueante):
                _compilar("gate_crash_prod.pdf")
        self.assertFalse((TMP_DIR / "gate_crash_prod.pdf").exists(),
                         "un gate que falla NO puede dejar un PDF final")

    def _afirmar_contiene(self, texto, aguja, etiqueta=""):
        """Aserción que NO vuelca el dictamen completo en el mensaje de error."""
        self.assertTrue(_sin_acentos(aguja) in _sin_acentos(texto),
                        f"el dictamen no contiene {etiqueta or aguja!r}")

    def _afirmar_no_contiene(self, texto, aguja, etiqueta=""):
        self.assertNotIn(_sin_acentos(aguja), _sin_acentos(texto),
                         f"el dictamen NO debería contener {etiqueta or aguja!r}")

    def test_gate_crash_en_development_deja_artefacto_marcado(self):
        os.environ["ARHIAX_ENV"] = "development"
        from sanctions import release_gate as rg

        def _boom(*a, **k):
            raise RuntimeError("synthetic gate failure")

        # El wrapper NO lanza: devuelve EVALUATION_FAILED y el PDF sale marcado.
        with mock.patch.object(rg, "evaluar_release_seguro", _boom):
            pdf = _compilar("gate_crash_dev.pdf")
        self.assertTrue(pdf.exists())
        n = " ".join(_texto(pdf).split()).upper()
        self._afirmar_contiene(n, "INVALID_FOR_RELEASE", "la marca de invalidez")
        self._afirmar_contiene(n, "EVALUACION DEL GATE FALLIDA",
                               "el estado legible de evaluación fallida")
        self._afirmar_contiene(n, "GATE_EVALUATION_FAILED", "el release_status crudo")
        self._afirmar_no_contiene(n, "RELEASE_GATE_STATUS VALID_FOR_RELEASE",
                                  "un estado válido")

    def test_nucleo_antiguo_en_produccion_no_deja_pdf(self):
        os.environ["ARHIAX_ENV"] = "production"
        from consistency import InconsistenciaBloqueante
        from sanctions import release_gate as rg
        with mock.patch.object(rg, "nucleo_vigente", lambda: self._nucleo_antiguo()):
            with self.assertRaises(InconsistenciaBloqueante):
                _compilar("nucleo_antiguo_prod.pdf")
        self.assertFalse((TMP_DIR / "nucleo_antiguo_prod.pdf").exists())

    def test_nucleo_actual_en_produccion_emite_dictamen_vigente(self):
        os.environ["ARHIAX_ENV"] = "production"
        pdf = _compilar("nucleo_actual_prod.pdf")
        self.assertTrue(pdf.exists())
        n = " ".join(_texto(pdf).split()).upper()
        self._afirmar_contiene(n, "RELEASE_GATE_STATUS VALID_FOR_RELEASE", "el estado válido")
        self._afirmar_contiene(n, "16.C RECIBO DE LIBERACION", "el recibo de liberación")
        self._afirmar_no_contiene(n, "LEGACY / INVALID_FOR_RELEASE", "la marca legacy")

    def test_nucleo_antiguo_en_development_marca_el_pdf(self):
        os.environ["ARHIAX_ENV"] = "development"
        from sanctions import release_gate as rg
        with mock.patch.object(rg, "nucleo_vigente", lambda: self._nucleo_antiguo()):
            pdf = _compilar("nucleo_antiguo_dev.pdf")
        self.assertTrue(pdf.exists())
        n = " ".join(_texto(pdf).split()).upper()
        self._afirmar_contiene(n, "LEGACY / INVALID_FOR_RELEASE", "la marca legacy")
        self._afirmar_contiene(n, "SANCTIONS-MATCHER/1.0.0", "el matcher antiguo")

    def test_sin_pdf_parcial_tras_fallo_de_construccion(self):
        """§4: si la construcción falla, no queda temporal ni final."""
        import pdf_compiler
        os.environ["ARHIAX_ENV"] = "production"
        out = TMP_DIR / "parcial.pdf"
        TMP_DIR.mkdir(parents=True, exist_ok=True)
        if out.exists():
            out.unlink()
        with mock.patch.object(pdf_compiler.SimpleDocTemplate, "build",
                               side_effect=RuntimeError("build roto")):
            with self.assertRaises(RuntimeError):
                _compilar("parcial.pdf")
        self.assertFalse(out.exists(), "no debe quedar PDF final tras un fallo de build")
        self.assertEqual([p.name for p in TMP_DIR.glob("parcial.pdf.part-*")], [],
                         "no debe quedar archivo temporal")


class TestClasificacionUsoRegimenTipologia(unittest.TestCase):
    """§16-§21: tres dimensiones separadas, con precedencia y conflicto propios."""

    def _c(self, **kw):
        from clasificacion import clasificar_inmueble, texto_tipologia
        clas = clasificar_inmueble(**kw)
        return clas, texto_tipologia(clas)

    def test_a_ph_mas_habitacional_conserva_ph(self):
        clas, txt = self._c(condicion_juridica="Propiedad Horizontal (inferido del CTL)",
                            destino_economico="Habitacional",
                            tipologia_fisica_fuente="APARTAMENTO")
        self.assertEqual(clas["juridical_regime"]["value"], "PROPIEDAD_HORIZONTAL")
        self.assertEqual(clas["economic_use"]["value"], "HABITACIONAL")
        self.assertEqual(clas["physical_typology"]["value"], "APARTAMENTO")
        self.assertIn("Apartamento -- Propiedad Horizontal", txt)

    def test_b_ph_mas_comercial_conserva_ph(self):
        clas, txt = self._c(condicion_juridica="Propiedad Horizontal",
                            destino_economico="Comercial")
        self.assertEqual(clas["juridical_regime"]["value"], "PROPIEDAD_HORIZONTAL")
        self.assertEqual(clas["economic_use"]["value"], "COMERCIAL")
        self.assertIsNone(clas["physical_typology"]["value"], "no se inventa la unidad")
        self.assertNotIn("No Propiedad Horizontal", txt)
        self.assertIn("Propiedad Horizontal", txt)
        self.assertIn("uso Comercial", txt)

    def test_c_ph_mas_oficina_conserva_ph(self):
        clas, txt = self._c(condicion_juridica="Propiedad Horizontal",
                            destino_economico="Oficina")
        self.assertEqual(clas["juridical_regime"]["value"], "PROPIEDAD_HORIZONTAL")
        self.assertEqual(clas["economic_use"]["value"], "OFICINA")
        self.assertIn("Propiedad Horizontal", txt)

    def test_d_ph_mas_garaje_conserva_ph(self):
        clas, txt = self._c(condicion_juridica="Propiedad Horizontal",
                            destino_economico="Garaje")
        self.assertEqual(clas["juridical_regime"]["value"], "PROPIEDAD_HORIZONTAL")
        self.assertEqual(clas["economic_use"]["value"], "GARAJE")
        self.assertIn("Propiedad Horizontal", txt)

    def test_e_sin_ph_con_uso_comercial_no_inventa_tipologia(self):
        clas, txt = self._c(destino_economico="Comercial")
        self.assertIsNone(clas["juridical_regime"]["value"])
        self.assertEqual(clas["economic_use"]["value"], "COMERCIAL")
        self.assertIsNone(clas["physical_typology"]["value"])
        self.assertEqual(clas["physical_typology"]["status"], "UNRESOLVED")
        self.assertIn("Uso Comercial", txt)

    def test_f_bodega_industrial_no_afirma_regimen(self):
        clas, txt = self._c(destino_economico="Industrial",
                            descripcion_registral="BODEGA 3 MANZANA 4")
        self.assertEqual(clas["physical_typology"]["value"], "BODEGA")
        self.assertIsNone(clas["juridical_regime"]["value"],
                          "la tipología no decide el régimen jurídico")
        self.assertEqual(clas["juridical_regime"]["status"], "UNRESOLVED")
        self.assertNotIn("No Propiedad Horizontal", txt)

    def test_g_ph_catastral_y_registral_coherentes(self):
        clas, _ = self._c(condicion_juridica="Propiedad Horizontal (condición catastral)",
                          condicion_source="capa_predio", destino_economico="Habitacional")
        self.assertEqual(clas["juridical_regime"]["value"], "PROPIEDAD_HORIZONTAL")
        self.assertEqual(clas["juridical_regime"]["status"], "VERIFIED_CATASTRAL")
        self.assertEqual(clas["conflicts"], [])

    def test_h_ph_registral_vs_catastro_incompatible_es_conflicto(self):
        clas, txt = self._c(condicion_juridica="Propiedad Horizontal (inferido del CTL)",
                            descripcion_catastral="NO PROPIEDAD HORIZONTAL",
                            destino_economico="Habitacional")
        self.assertEqual(clas["juridical_regime"]["status"], "CONFLICT")
        self.assertTrue(clas["conflicts"])
        self.assertEqual(clas["conflicts"][0]["dimension"], "juridical_regime")
        self.assertIn("conflicto", txt.lower())

    def test_ph_con_uso_no_es_conflicto(self):
        clas, _ = self._c(condicion_juridica="Propiedad Horizontal",
                          destino_economico="Comercial")
        self.assertEqual(clas["conflicts"], [], "uso distinto no es contradicción")

    def test_el_mercado_exige_regimen_o_tipologia_no_un_uso(self):
        from clasificacion import clasificar_inmueble, estado_aceptable_para_mercado
        _ok_uso, motivo_uso = estado_aceptable_para_mercado(
            clasificar_inmueble(destino_economico="Comercial"))
        self.assertFalse(_ok_uso, "un uso declarado no habilita la valoración")
        _ok_ph, motivo_ph = estado_aceptable_para_mercado(
            clasificar_inmueble(condicion_juridica="Propiedad Horizontal",
                                destino_economico="Comercial"))
        self.assertTrue(_ok_ph, motivo_ph)


class TestSujetos050916(unittest.TestCase):
    """§13/§14: el MISMO valor renderizado en los tres capítulos (no presencia)."""

    ANALYSIS = {
        "titulares": "DURAN BACCA ALISSON CC# 1045718995X 50%",
        "acreedor_snr": "BANCO DE BOGOTA S.A.NIT# 8600029644",
        "acreedor_real": None,
        "constructor": "URBANIZADORA MARVAL S.A.S. (HOY) 83001205533",
        "anotaciones_detalle": [],
    }

    @classmethod
    def setUpClass(cls):
        from sanctions.contracts import ScreeningSummary
        from sanctions.subjects import build_subject_envelopes
        from titulux_bridge import _screening_legado
        cls.envs = build_subject_envelopes(dict(cls.ANALYSIS))
        cls.summary = ScreeningSummary(subjects=tuple(cls.envs),
                                       subjects_declared=len(cls.envs),
                                       subjects_screened=len(cls.envs),
                                       status="SCREENING_COMPLETE",
                                       algorithm_version="sanctions-matcher/1.1.0")
        cls.filas_05_16 = _screening_legado(cls.summary)

    def _por_rol(self, fragmento):
        return next(e for e in self.envs if fragmento in e.subject_id)

    def test_banco_de_bogota_juridica_nit_en_05_09_16(self):
        from sanctions.subjects import fila_sujeto_dictamen
        from sarlaft_engine import _sujetos_desde_envelopes
        from receipts import _screening_receipt

        env = self._por_rol("acreedor")
        fila = fila_sujeto_dictamen(env)                 # capítulo 09
        ficha05 = next(f for f in _sujetos_desde_envelopes(self.envs)
                       if f["subject_id"] == env.subject_id)   # capítulo 05
        row_screen = next(r for r in self.filas_05_16
                          if r["sujeto_id"] == env.subject_id)     # capa 05/16
        rec16 = _screening_receipt({"screening_summary": {
            "status": "SCREENING_COMPLETE", "subjects": [fila], "snapshots": [],
            "coverage_complete": True, "subjects_declared": 1, "subjects_screened": 1,
            "evidence_created_count": 1, "evidence_expected_count": 1,
            "evidence_chain_status": "SEALED"}})
        det16 = rec16["sujetos_detalle"][0]

        self.assertEqual(fila["canonical_name"], "BANCO DE BOGOTA S.A.")
        self.assertEqual(fila["person_type"], "LEGAL_ENTITY")
        for etiqueta, valor in (("09", fila["person_type_label"]),
                                ("05", ficha05["tipo_persona_txt"]),
                                ("05/16-legacy", row_screen["person_type_label"]),
                                ("16", det16["person_type_label"])):
            self.assertEqual(valor, "Jurídica", f"etiqueta distinta en {etiqueta}")
        for etiqueta, valor in (("09", fila["document"]),
                                ("05", ficha05["identificacion"]),
                                ("05/16-legacy", row_screen["documento"]),
                                ("16", det16["document"])):
            self.assertEqual(valor, "NIT 8600029644", f"documento distinto en {etiqueta}")
        for etiqueta, valor in (("05", ficha05["subject_id"]),
                                ("05/16-legacy", row_screen["sujeto_id"]),
                                ("16", det16["subject_id"])):
            self.assertEqual(valor, fila["subject_id"], f"subject_id distinto en {etiqueta}")

    def test_duran_bacca_natural_cc_en_05_09_16(self):
        from sanctions.subjects import fila_sujeto_dictamen
        from sarlaft_engine import _sujetos_desde_envelopes

        env = self._por_rol("titular_actual")
        fila = fila_sujeto_dictamen(env)
        ficha05 = next(f for f in _sujetos_desde_envelopes(self.envs)
                       if f["subject_id"] == env.subject_id)
        row_screen = next(r for r in self.filas_05_16
                          if r["sujeto_id"] == env.subject_id)
        self.assertEqual(fila["person_type"], "NATURAL_PERSON")
        self.assertEqual(fila["person_type_label"], "Natural")
        self.assertEqual(ficha05["tipo_persona_txt"], "Natural")
        self.assertEqual(row_screen["person_type_label"], "Natural")
        self.assertEqual(fila["document"], "CC 1045718995X")
        self.assertEqual(ficha05["identificacion"], "CC 1045718995X")
        self.assertEqual(row_screen["documento"], "CC 1045718995X")

    def test_los_tres_sujetos_del_caso_comparten_identidad(self):
        from sanctions.subjects import fila_sujeto_dictamen
        ids_09 = [fila_sujeto_dictamen(e)["subject_id"] for e in self.envs]
        ids_05 = [r["sujeto_id"] for r in self.filas_05_16]
        self.assertEqual(ids_09, ids_05)

    def test_ningun_documento_sale_como_n_d_mudo(self):
        from sanctions.subjects import fila_sujeto_dictamen
        for e in self.envs:
            self.assertNotEqual(fila_sujeto_dictamen(e)["document"].strip(), "N/D")


class TestMarvalFueraDelVocabulario(unittest.TestCase):
    """§15: 'MARVAL' no es señal genérica de persona jurídica."""

    def test_marval_no_esta_en_los_tokens_legales(self):
        from sanctions import subjects as S
        self.assertNotIn("MARVAL", S._LEGAL_TOKENS)

    def test_el_constructor_golden_sigue_siendo_juridica(self):
        from sanctions.subjects import parse_person, person_type_from
        for raw in ("URBANIZADORA MARVAL S.A.S.",
                    "URBANIZADORA MARIN VALENCIA S.A.NIT# 8300120533",
                    "URBANIZADORA MARVAL S.A.S. (HOY) 83001205533"):
            d = parse_person(raw)
            tipo, _ = person_type_from(d["canonical_name"], d["document_type"])
            self.assertEqual(tipo, "LEGAL_ENTITY", f"{raw!r} -> {tipo}")

    def test_una_empresa_llamada_igual_sin_señal_juridica_es_unknown(self):
        """Si el nombre no trae forma societaria ni documento, NO se asume jurídica."""
        from sanctions.subjects import parse_person, person_type_from
        d = parse_person("MARVAL")
        tipo, _ = person_type_from(d["canonical_name"], d["document_type"])
        self.assertEqual(tipo, "UNKNOWN")


if __name__ == "__main__":
    unittest.main()

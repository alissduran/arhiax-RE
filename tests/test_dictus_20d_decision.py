# -*- coding: utf-8 -*-
"""DICTUS 2.0D — GRAMÁTICA DE DECISIÓN: objetos, compuertas y disposición.

Cubre las pruebas obligatorias de §43:

  · Evidence ≠ Observation ≠ Finding ≠ Decision ≠ Disposition (objetos separados).
  · `SOURCE_UNAVAILABLE` / `NOT_RUN` / `QUERY_FAILED` nunca producen `NO_MATCH`.
  · Un conflicto histórico nunca produce un valor definitivo.
  · El POI no se pierde entre el motor y el ejecutivo.
  · El activo de sombra aparece si fue generado y declara sus supuestos.
  · La altura normativa NO se usa como altura física sin contrato explícito.
  · Una valoración bloqueada no explica después que el valor fue calculado.
  · Una evidencia no sellada no aparece como sellada en otra sección.
  · Todas las decisiones tienen motivos; todos los hallazgos materiales, actores;
    todas las recomendaciones, referencias de evidencia.
  · El hash maestro cambia ante una decisión material.
"""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))

import dictus_decision as dd            # noqa: E402
import dictus_entrega as entrega        # noqa: E402
import dictus_ejecutivo as de           # noqa: E402
import dictus_estado as dse             # noqa: E402
import dictus_manifiesto as dm          # noqa: E402
import dictus_secciones as sec          # noqa: E402
from test_dictus_20c_fidelidad import procedencia_sintetica   # noqa: E402

FOLIO = "TST-000001"
GOLDEN = ROOT / "docs" / "forensics" / "040-646406"


def _estado(**over):
    """Estado de corrida sintético con la MISMA forma que la corrida real."""
    rs = {
        "run_state_version": "dictus-run-state/1.0.0", "run_id": "qa-2d",
        "generated_at": "2026-01-15T10:05:00+00:00", "ciudad": "barranquilla",
        "property_identity": {"folio": FOLIO, "nupre": "AFT0000TEST",
                              "codigo_catastral": "0000000000000",
                              "direccion_raw": "CALLE 1 # 2 - 3 APARTAMENTO 101 TORRE 1",
                              "unidad": "APARTAMENTO 101 TORRE 1", "torre": "1",
                              "apartamento": "101", "identity_verified": True,
                              "resolution_method": "nupre", "estado": "MATCH_BY_NUPRE"},
        "title_state": {"folio": FOLIO, "titulares": "TITULAR DE PRUEBA CC# 1000000000",
                        "modalidad_adquisicion": "Compraventa",
                        "modalidad_evidencia": "Anot. 006 · ESCRITURA 100",
                        "anotaciones_total": 3, "certificado_adjuntado": True,
                        "gravamenes_vigentes": [
                            {"anotacion": "007", "tipo": "GRAVAMEN: Hipoteca",
                             "partes": "TITULAR -> BANCO", "estado": "VIGENTE"},
                            {"anotacion": "008", "tipo": "LIMITACION: Afectacion Vivienda",
                             "partes": "TITULAR", "estado": "VIGENTE"}]},
        "urban_context": {"area": 58.75, "barrio": "BARRIO DE PRUEBA", "localidad": "01",
                          "estrato": "3", "tratamiento": "Consolidacion",
                          "tipo_tratamiento": "Nivel 2", "altura_maxima": "11",
                          "condicion_juridica": "Propiedad Horizontal",
                          "destino_economico": "Habitacional", "clase_suelo": None},
        "screening_summary": {
            "status": "SCREENING_COMPLETE", "subjects": [
                {"subject_id": "s1", "canonical_name": "TITULAR DE PRUEBA",
                 "roles": ["TITULAR_ACTUAL"], "document_type": "cc",
                 "document_number": "1000000000"}],
            "outcomes": [{"subject_id": "s1", "source_id": "UN_CONSOLIDATED",
                          "result": "NO_MATCH"}],
            "sources": ["UN_CONSOLIDATED", "OFAC_SDN"], "matched_subjects": [],
            "evidence_chain_status": "SEALED", "evidence_created_count": 2,
            "evidence_expected_count": 2, "coverage_status": "COVERAGE_COMPLETE",
            "subjects_screened": 1, "subjects_declared": 1},
        "poi_state": {"por_categoria": {"Salud": {"status": "AVAILABLE", "count": 3,
                                                  "mas_cercano_m": 420.0,
                                                  "items": [{"name": "CENTRO 1"}]},
                                        "Recreacion": {"status": "SOURCE_UNAVAILABLE",
                                                       "count": 0, "items": []}},
                      "item_count": 3, "distance_available": True,
                      "sources_succeeded": ["OSM_OVERPASS"], "queried_at": "2026-01-15"},
        "risk_context": {"amenaza_remocion_masa": "Media · polígono: intersecta el predio",
                         "inundacion": None, "riesgo_no_mitigable": None},
        "solar_state": {"momentos": [
            {"hora": "09:00 COT", "azimut": "102.33°", "elevacion": "45.98°",
             "estado": "Sol Directo"},
            {"hora": "12:00 COT", "azimut": "191.14°", "elevacion": "78.25°",
             "estado": "Sol Directo"},
            {"hora": "15:00 COT", "azimut": "259.25°", "elevacion": "41.62°",
             "estado": "Sombra (Orientación)"}]},
        "valuation_state": {"value_m2": 6000000, "consolidado": 352500000,
                            "banda_baja": 330000000, "banda_alta": 375000000,
                            "authorization": {"allowed": True, "identity_authorized": True,
                                              "market_context_authorized": True}},
        "market_context": {"coordinates": {"lat": 11.0055, "lon": -74.8375},
                           "coordinate_source": "OFFICIAL_PREDIO",
                           "coordinate_source_verified": True,
                           "canonical_binding_status": "VERIFIED",
                           "canonical_binding_fields": ["nupre", "numero_predial"],
                           "market_methodology_id": "lonja_prueba",
                           "market_methodology_version": "0.9-test",
                           "market_rate_source": "Tasa de prueba verificada",
                           # La tasa del fixture declara su ORIGEN con procedencia
                           # COMPLETA: es lo único que habilita la valoración.
                           "sector_metodologico": {
                               "matched_sector": "SECTOR DE PRUEBA",
                               "match_type": "EXACT",
                               **procedencia_sintetica(
                                   "tests/test_dictus_20d_decision.py::_estado")},
                           "uso": {"value": "Habitacional", "status": "VERIFIED_OFFICIAL"},
                           "blockers": [],
                           "urban_source_summary": {"campos": {
                               "tratamiento": {"modo": "LIVE_OFFICIAL"},
                               "altura_maxima": {"modo": "PACKAGED_REFERENCE"}}}},
        "findings": [{"severidad": "ALTO", "codigo": "H-01",
                      "titulo": "Hipoteca vigente", "afectados": ["COMPRADOR", "VENDEDOR"],
                      "accion": "Gestionar el crédito y cancelar la hipoteca.",
                      "por_que": "El folio declara hipoteca abierta."}],
        "historical_consistency": {"versiones_comparadas": 14, "conflictos_abiertos": [
            {"atributo": "altura_maxima", "valores": ["8", "11"], "detalle": "x"}]},
        "visual_assets": {"assets": {"poi_map": {"status": "AVAILABLE", "source": "motor",
                                                 "sha256": "abc", "generated_at": "2026-01-15"}}},
        "shadow_simulation": {"altura_m": 9.0, "fuente_huella": "huella estimada",
                              "fuente_altura": None, "fecha": "2026-01-15",
                              "generado_en": "2026-01-15T10:00:00+00:00"},
        "release_state": {"release_status": "VALID_FOR_RELEASE"},
    }
    for ruta, valor in over.items():
        actual = rs
        partes = ruta.split("__")
        for p in partes[:-1]:
            actual = actual.setdefault(p, {})
        actual[partes[-1]] = valor
    return rs


class TestObjetosSeparados(unittest.TestCase):
    """§43 · Evidence ≠ Observation ≠ Finding ≠ Recommendation ≠ Decision ≠ Disposition."""

    def test_la_cadena_tiene_objetos_distintos(self):
        rs = _estado()
        d = dd.construir(rs, captura_sombras=rs["shadow_simulation"])
        obs, fnd, rec, gates, disp = (d["observations"], d["findings"],
                                      d["recommendations"], d["decision_gates"],
                                      d["disposition"])
        self.assertTrue(obs and fnd and rec and gates and disp)
        for o in obs:
            self.assertIn(o["status"], dd.ESTADOS_OBSERVACION)
            self.assertNotIn("decision", o, "una observación no decide")
            self.assertNotIn("severity", o, "una observación no tiene severidad")
        for f in fnd:
            self.assertIn("meaning", f)
            self.assertIn(f["decision"], dd.VOCABULARIO_DECISION)
            self.assertIn(f["observation_id"], [o["observation_id"] for o in obs])
            self.assertIn(f["risk_class"], (dd.RIESGO_PREDIO, dd.RIESGO_INFORMACION))
            self.assertTrue(f["affected_parties"],
                            "todo hallazgo material declara a quién afecta")
            self.assertTrue(f["evidence_refs"], "todo hallazgo cita su evidencia")
        for r in rec:
            self.assertTrue(r["evidence_refs"], "toda recomendación cita su evidencia")
        for g in gates:
            self.assertTrue(g["reasons"], "toda compuerta declara motivos")
            self.assertIn(g["decision"], dd.VOCABULARIO_DECISION)
        self.assertIn(disp["disposition"], (dd.SUFICIENTE, dd.CONDICIONES,
                                            dd.VALIDACION_PROFESIONAL, dd.INSUFICIENTE))
        self.assertEqual(disp["specific_dispositions"], disp["by_gate"])

    def test_el_sistema_no_decide_por_la_persona(self):
        rs = _estado()
        d = dd.construir(rs)
        texto = json.dumps(d, ensure_ascii=False).upper()
        for prohibido in ("COMPRE", "NO COMPRE", "CRÉDITO APROBADO", "SEGURO APROBADO",
                          "TÍTULO GARANTIZADO"):
            self.assertNotIn(prohibido, texto)
        self.assertTrue(d["human_review"]["review_required"])
        self.assertEqual(d["human_review"]["status"], "PENDIENTE")


class TestNoConfundirAusenciaConResultado(unittest.TestCase):
    """§11/§43 · SOURCE_UNAVAILABLE / NOT_RUN / QUERY_FAILED nunca son NO_MATCH."""

    def test_fuente_no_disponible_no_produce_no_match(self):
        rs = _estado()
        rs["poi_state"]["por_categoria"]["Salud"]["status"] = "SOURCE_UNAVAILABLE"
        d = dd.construir(rs)
        salud = [o for o in d["observations"]
                 if o["subject"] == "Equipamiento · Salud"][0]
        self.assertEqual(salud["status"], dd.FUENTE_NO_DISPONIBLE_OBS)
        env = [g for g in d["decision_gates"] if g["gate"] == dd.ENVIRONMENT_GATE][0]
        self.assertNotEqual(env["decision"], dd.SIN_HALLAZGO_EN_FUENTE)

    def test_consulta_no_ejecutada_no_es_sin_coincidencia(self):
        rs = _estado()
        rs["screening_summary"]["outcomes"] = [
            {"subject_id": "s1", "source_id": "UN_CONSOLIDATED", "result": "NOT_SCREENED"}]
        d = dd.construir(rs)
        estado = [o["status"] for o in d["observations"]
                  if o["domain"] == "COUNTERPARTY"]
        self.assertIn(dd.NO_CONSULTADO, estado)
        self.assertNotIn(dd.NO_MATCH, estado)
        cp = [g for g in d["decision_gates"] if g["gate"] == dd.COUNTERPARTY_GATE][0]
        self.assertEqual(cp["decision"], dd.INFORMACION_INSUFICIENTE)

    def test_la_integridad_no_cambia_el_resultado_del_screening(self):
        rs = _estado()
        rs["screening_summary"]["outcomes"] = [
            {"subject_id": "s1", "source_id": "UN_CONSOLIDATED", "result": "NO_MATCH"},
            {"subject_id": "s1", "source_id": "OFAC_SDN", "result": "NO_MATCH"}]
        rs["screening_summary"]["evidence_chain_status"] = "FAILED"
        d = dd.construir(rs)
        cp = [g for g in d["decision_gates"] if g["gate"] == dd.COUNTERPARTY_GATE][0]
        # El resultado del screening sigue siendo «sin coincidencias relevantes».
        self.assertEqual(cp["decision"], dd.SIN_HALLAZGO_EN_FUENTE)
        ev = [g for g in d["decision_gates"] if g["gate"] == dd.EVIDENCE_GATE][0]
        self.assertEqual(ev["decision"], dd.EVIDENCIA_EN_CONFLICTO)
        self.assertTrue(any("sellad" in m.lower()
                            for m in list(ev["reasons"]) + list(ev["blocking_conditions"])))


class TestConflictosYAlturas(unittest.TestCase):
    """§14/§24/§43 · conflicto histórico y altura normativa ≠ física."""

    def test_conflicto_historico_no_produce_valor_definitivo(self):
        rs = _estado()
        # Orden real de la corrida: el motor de coherencia produce sus hallazgos
        # ANTES de construir el modelo (no se inventan en el documento).
        dse.agregar_findings_de_coherencia(rs, rs["historical_consistency"])
        d = dd.construir(rs)
        urb = [g for g in d["decision_gates"] if g["gate"] == dd.URBAN_GATE][0]
        self.assertEqual(urb["decision"], dd.NO_USAR_COMO_DEFINITIVO)
        self.assertTrue(any("altura_maxima" in b for b in urb["blocking_conditions"]))
        h = [f for f in d["findings"] if f["risk_class"] == dd.RIESGO_INFORMACION]
        self.assertTrue(h, "el conflicto entra como riesgo de CALIDAD DE INFORMACIÓN")
        self.assertTrue(all(f["decision"] == dd.NO_USAR_COMO_DEFINITIVO for f in h))

    def test_la_altura_normativa_no_es_la_altura_fisica(self):
        rs = _estado()
        m = dd.manifiesto_sombras(rs, rs["shadow_simulation"])
        h = m["height_concepts"]
        self.assertEqual(h[dd.REGULATORY_HEIGHT], rs["urban_context"]["altura_maxima"])
        self.assertEqual(h[dd.BUILDING_PHYSICAL_HEIGHT], 9.0)
        self.assertNotEqual(h[dd.MODEL_ASSUMED_HEIGHT], h[dd.REGULATORY_HEIGHT])
        self.assertIn("ASSUMED", json.dumps(m["dependencies"]))
        self.assertTrue(m["assumptions"])
        self.assertIn("SIMULACIÓN GEOMÉTRICA", m["nature"])

    def test_sin_altura_fisica_el_modelo_es_orientativo(self):
        rs = _estado()
        m = dd.manifiesto_sombras(rs, {})
        self.assertIn("PARTIAL", m["status"])
        self.assertIsNone(m["height_concepts"][dd.BUILDING_PHYSICAL_HEIGHT])

    def test_el_manifiesto_de_sombras_declara_todo_lo_exigido(self):
        rs = _estado()
        m = dd.manifiesto_sombras(rs, rs["shadow_simulation"])
        for campo in ("simulation_id", "generated_at", "location", "solar_model", "date",
                      "times", "geometry_source", "orientation_source",
                      "physical_height_source", "assumptions", "status", "result_hash"):
            self.assertIn(campo, m, f"falta {campo} en el manifiesto de sombras")
        self.assertEqual(len(m["times"]), 3)


class TestValoracionYEvidencia(unittest.TestCase):
    """§28/§12/§43 · valoración bloqueada y evidencia no sellada."""

    def test_valoracion_bloqueada_declara_causa_y_no_calcula(self):
        rs = _estado()
        rs["valuation_state"] = {"authorization": {"allowed": False,
                                                   "market_context_authorized": False},
                                 "motivo_no_aplica": "Contexto de mercado no autorizado."}
        rs["market_context"]["blockers"] = ["Contexto de mercado no autorizado"]
        d = dd.construir(rs)
        val = [g for g in d["decision_gates"] if g["gate"] == dd.VALUATION_GATE][0]
        self.assertEqual(val["decision"], dd.NO_EMITIR_VALORACION)
        self.assertTrue(val["blocking_conditions"])
        self.assertTrue(val["reasons"])
        # La observación conserva la clave del valor pero SIN cifra: null, nunca 0.
        valores = (val["observations"][0] or {}).get("value") or {}
        self.assertIsNone(valores.get("consolidado"))
        self.assertIsNone(valores.get("value_m2"))

    def test_hash_maestro_cambia_ante_una_decision_material(self):
        rs = _estado()
        modelo = dm.construir_documento_maestro(rs, historial=rs["historical_consistency"],
                                                folio=FOLIO)
        base = dm.master_hash(modelo)
        otro = copy.deepcopy(modelo)
        otro["decision_gates"][1]["decision"] = dd.INSUFICIENTE
        self.assertNotEqual(dm.master_hash(otro), base)
        otro2 = copy.deepcopy(modelo)
        otro2["observations"] = otro2["observations"][:-1]
        self.assertNotEqual(dm.master_hash(otro2), base)

    def test_el_modelo_incluye_los_bloques_de_decision(self):
        rs = _estado()
        modelo = dm.construir_documento_maestro(rs, historial=rs["historical_consistency"],
                                                folio=FOLIO)
        for bloque in ("observations", "recommendations", "decision_gates", "disposition",
                       "human_reviews", "decision_matrix", "shadow_manifest",
                       "visual_assets", "decision_findings"):
            self.assertIn(bloque, modelo, f"falta {bloque} en el modelo")
            self.assertIn(bloque, dm.BLOQUES_CANONICOS,
                          f"{bloque} debe entrar al hash maestro")
        # El hallazgo CON significado/motivos/afectados es un objeto distinto de la
        # lista legacy del expediente: si se mezclan, los motivos no entran al hash.
        self.assertNotEqual(modelo["decision_findings"], modelo["findings"])
        for f in modelo["decision_findings"]:
            self.assertTrue(f.get("meaning"))
            self.assertTrue(f.get("impact"))
            self.assertTrue(f.get("affected_parties"))

    def test_el_hash_cambia_si_cambia_el_motivo_de_un_hallazgo(self):
        rs = _estado()
        modelo = dm.construir_documento_maestro(rs, historial=rs["historical_consistency"],
                                                folio=FOLIO)
        base = dm.master_hash(modelo)
        otro = copy.deepcopy(modelo)
        otro["decision_findings"][0]["impact"] = "impacto distinto"
        self.assertNotEqual(dm.master_hash(otro), base)

    def test_compuerta_de_completitud_material(self):
        rs = _estado()
        modelo = dm.construir_documento_maestro(rs, historial=rs["historical_consistency"],
                                                folio=FOLIO)
        gate = dd.material_fact_gate(rs, modelo)
        self.assertEqual(gate["result"], "PASS", gate["losses"])
        degradado = copy.deepcopy(modelo)
        degradado["poi_summary"]["por_categoria"]["Salud"]["count"] = 0
        gate2 = dd.material_fact_gate(rs, degradado)
        self.assertEqual(gate2["result"], "FAIL")
        self.assertIn("POI Salud", [p["fact"] for p in gate2["losses"]])


def _estado_golden():
    """Estado real del Golden 040-646406, tal como lo dejó `scripts/dictus_run.py`."""
    ruta = GOLDEN / "dictus_2b" / "DICTUS_RUN_STATE_040-646406.json"
    if not ruta.exists():
        return None
    rs = json.loads(ruta.read_text(encoding="utf-8"))
    hist_p = GOLDEN / "dictus_2" / "HISTORICAL_CONSISTENCY_REPORT.json"
    hist = json.loads(hist_p.read_text(encoding="utf-8")) if hist_p.exists() else {}
    rs["historical_consistency"] = hist
    dse.agregar_findings_de_coherencia(rs, hist)
    dse.agregar_manifiesto_de_sombras(rs)
    return rs, hist


class TestDocumentoImpreso(unittest.TestCase):
    """El PDF físico dice lo mismo que la cadena de decisión.

    Se imprime el estado REAL del Golden: un fixture sintético no probaría que la
    retícula aguanta el expediente completo.
    """

    @classmethod
    def setUpClass(cls):
        salida = ROOT / "tmp_dictus_2d"
        salida.mkdir(exist_ok=True)
        par = _estado_golden()
        if par is None:
            raise unittest.SkipTest("falta el estado del Golden")
        rs, hist = par
        cls.rs = rs
        modelo = dm.construir_documento_maestro(rs, historial=hist, folio="040-646406")
        secciones = sec.desde_estado(rs, modelo, hist)
        cls.modelo, cls.secciones = modelo, secciones
        cls.pdf = salida / "DICTUS_EJECUTIVO_040-646406.pdf"
        del de.VIOLACIONES[:]
        de.render(modelo, secciones, cls.pdf)
        cls.violaciones = list(de.VIOLACIONES)
        from pypdf import PdfReader
        cls.paginas = [(p.extract_text() or "") for p in PdfReader(str(cls.pdf)).pages]
        cls.plano = " ".join(" ".join(p.split()) for p in cls.paginas)

    def test_seis_paginas_con_los_titulos_2d(self):
        self.assertEqual(len(self.paginas), 6)
        for i, titulo in enumerate(de.TITULOS_PAGINA, start=1):
            self.assertIn(titulo, self.paginas[i - 1])
        self.assertEqual(list(de.TITULOS_PAGINA), list(entrega.TITULOS_APROBADOS))

    def test_la_pagina_1_es_un_tablero_de_decision(self):
        p1 = self.paginas[0]
        for columna in ("TEMA", "QUÉ ENCONTRÓ DICTUS", "DECISIÓN DICTUS", "AFECTA A",
                        "ACCIÓN"):
            self.assertIn(columna, p1)
        for dominio in ("IDENTIDAD", "TÍTULOS", "CONTRAPARTES", "TERRITORIO", "ENTORNO",
                        "VALORACIÓN"):
            self.assertIn(dominio, p1.upper())
        self.assertIn("DISPOSICIÓN GLOBAL", p1.upper())
        # El vocabulario se imprime COMPLETO: ningún término de decisión abreviado.
        self.assertIn("NO UTILIZAR ESTE DATO COMO DEFINITIVO", p1)
        self.assertNotIn("COMO DEFI…", p1)
        # Los actores afectados no se truncan (§28).
        self.assertIn("BANCO / FINANCIADOR", p1)

    def test_el_tablero_no_duplica_hechos(self):
        filas = (self.secciones["decision"].get("board") or [])
        claves = [(f.get("tema"), f.get("decision")) for f in filas]
        self.assertEqual(len(claves), len(set(claves)), "el tablero repite un tema")
        # El tablero del PDF tiene exactamente una fila por tema/decsión del modelo.
        for tema, decision in claves:
            self.assertIn(str(decision), self.paginas[0])
        self.assertIn(f"AFECTA A: {filas[0].get('afecta')}", self.paginas[0])


    def test_el_documento_declara_supuestos_de_la_sombra(self):
        p5 = self.paginas[4]
        self.assertIn("PROYECCIÓN DE SOMBRAS", p5)
        self.assertIn("DEPENDENCIAS", p5)
        self.assertIn("SUPUESTO", p5)
        self.assertIn("SIMULACIÓN GEOMÉTRICA", p5)
        self.assertIn("altura física del edificio", p5.lower())

    def test_la_pagina_2_y_3_llevan_su_decision(self):
        self.assertIn("DECISIÓN DICTUS", self.paginas[1])
        self.assertIn("QUÉ REVISAMOS", self.paginas[1])
        self.assertIn("NOT_RUN", self.paginas[2].upper() + self.paginas[2])
        self.assertIn("INTEGRIDAD DE LA EVIDENCIA", self.paginas[2])

    def test_sin_valoracion_no_se_dice_que_se_calculo(self):
        """Variante del Golden con la valoración BLOQUEADA: el PDF debe declararlo."""
        rs = copy.deepcopy(self.rs)
        rs["valuation_state"] = {"authorization": {"allowed": False,
                                                   "market_context_authorized": False},
                                 "motivo_no_aplica": "Contexto de mercado no autorizado."}
        rs["market_context"]["blockers"] = ["Contexto de mercado no autorizado"]
        modelo = dm.construir_documento_maestro(rs, historial={}, folio="040-646406")
        secciones = sec.desde_estado(rs, modelo, {})
        pdf = ROOT / "tmp_dictus_2d" / "sin_valor.pdf"
        de.render(modelo, secciones, pdf)
        from pypdf import PdfReader
        paginas = [" ".join(" ".join((p.extract_text() or "").split()))
                   for p in PdfReader(str(pdf)).pages]
        p6 = paginas[5]
        # La página 6 se extrae con espaciado entre glifos: se compara sin espacios.
        p6_plano = p6.replace(" ", "")
        self.assertIn("NOEMITIRVALORACIÓN", p6_plano)
        self.assertIn("noseimprimeningúnmonto", p6_plano.lower())
        self.assertNotIn("seconstruyóelvalor", p6_plano.lower())
        # El único «$0» de la página es la propia advertencia de que no se imprime.
        self.assertEqual(p6_plano.count("$0"), 1)
        self.assertIn("ni$0", p6_plano)
        # Tampoco aparece la cifra del Golden enmascarada en otra página.
        self.assertNotIn("399.500.000", " ".join(paginas))
        gate = [g for g in modelo["decision_gates"] if g["gate"] == dd.VALUATION_GATE][0]
        self.assertEqual(gate["decision"], dd.NO_EMITIR_VALORACION)

    def test_reticula_sin_solapamientos(self):
        self.assertEqual(self.violaciones, [])
        self.assertEqual(de.verificar_retícula(), [])


class TestGolden2D(unittest.TestCase):
    """Artefactos del Golden 2.0D (se omiten si no se ha corrido)."""

    def test_el_estado_del_golden_trae_la_cadena_de_decision(self):
        ruta = GOLDEN / "dictus_2b" / "DICTUS_MANIFEST_040-646406.json"
        if not ruta.exists():
            self.skipTest("falta el manifest del Golden")
        man = json.loads(ruta.read_text(encoding="utf-8"))
        modelo = man["modelo"]
        self.assertTrue(modelo.get("observations"))
        self.assertTrue(modelo.get("decision_gates"))
        self.assertTrue(modelo.get("disposition"))
        self.assertEqual(len(modelo["decision_gates"]), 7)
        self.assertIn("shadow_manifest", modelo)
        self.assertEqual(man["master_manifest_version"], "dictus-master-manifest/1.2.0")
        self.assertEqual(dse.verify_dictus_master_hash(man, man["master_hash"])["result"],
                         dse.MATCH)


if __name__ == "__main__":
    unittest.main()

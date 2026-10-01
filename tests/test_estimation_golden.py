# -*- coding: utf-8 -*-
"""DICTUS ESTIMATION ENGINE v1.0 · FASE 3 — GOLDEN Y CONTRATOS DE IMPRESIÓN.

Cubre lo que la Fase 3 promete y nada más:

  §27 · el GOLDEN corre el motor sobre el estado REAL (no asume el resultado) y la
        decisión es REPRODUCIBLE: mismo expediente → misma compuerta, mismo estado,
        misma confianza, mismo rango (o la misma ausencia de rango).
  §39 · la aceptación dura: `manual inputs used = 0`, `legacy priors used = 0`,
        `399.500.000` no aparece ni como input ni como salida, y ningún monto se
        imprime cuando el motor no lo produjo.
  §28 · si el resultado es `CLOSED`, se entrega `MISSING_MARKET_EVIDENCE` +
        `informe_de_brecha` CONCRETO (qué fuente automática y con qué campos).
  §32 · la PÁGINA 1 imprime las tres ramas del contrato (`VALOR ESTIMADO` con cifra,
        rango y confianza · `ESTIMACIÓN INDICATIVA` + rango + confianza indicativa ·
        `ESTIMACIÓN NO DISPONIBLE` + «Sin evidencia de mercado suficiente»).
  §33 · la PÁGINA 6 imprime el bloque `ESTIMACIÓN ECONÓMICA` con sus OCHO campos y el
        TEXTO FIJO permitido, dentro del presupuesto (`PIE_Y`) y sin violaciones.
  §34 · el marco «norma + concepto técnico + validación profesional» NO se imprime:
        lo sustituye «fuentes disponibles + análisis técnico automatizado + metodología
        versionada».

Las pruebas del RENDER usan el estado REAL del Golden y le inyectan los contratos del
motor calculados con las fixtures del motor (comparables externos con procedencia
completa). Así se prueba el CABLEADO de las tres ramas sin fabricar un expediente de
mercado que no existe.
"""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "docs" / "forensics" / "040-646406"
SALIDA = ROOT / "tmp_dictus_estimacion"
for _p in (str(ROOT), str(ROOT / "api"), str(ROOT / "scripts"),
           str(Path(__file__).resolve().parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import dictus_ejecutivo as de           # noqa: E402
import dictus_estado as dse             # noqa: E402
import dictus_manifiesto as dm          # noqa: E402
import dictus_secciones as sec          # noqa: E402
import estimation as est                # noqa: E402
import estimation_state as egs          # noqa: E402
from _fixtures_estimation import (      # noqa: E402
    comparables_validos, entrada, estimar)

FOLIO = "040-646406"
RUN_STATE = GOLDEN / "dictus_2b" / f"DICTUS_RUN_STATE_{FOLIO}.json"
MANIFEST = GOLDEN / "dictus_2b" / f"DICTUS_MANIFEST_{FOLIO}.json"


def _cargar(ruta: Path):
    if not ruta.exists():
        return None
    return json.loads(ruta.read_text(encoding="utf-8"))


def _estado_real():
    """Estado REAL del Golden, sin tocar el disco: sólo lectura."""
    rs = _cargar(RUN_STATE)
    if rs is None:
        return None
    hist_p = GOLDEN / "dictus_2" / "HISTORICAL_CONSISTENCY_REPORT.json"
    hist = _cargar(hist_p) or {}
    rs = copy.deepcopy(rs)
    rs["historical_consistency"] = hist
    dse.agregar_findings_de_coherencia(rs, hist)
    dse.agregar_manifiesto_de_sombras(rs)
    return rs, hist


# ══════════════════════════════════════════════════════════════════════════════
# §27/§39 · GOLDEN
# ══════════════════════════════════════════════════════════════════════════════
class TestGoldenEstimacion(unittest.TestCase):
    """El motor corrido sobre el estado REAL: sin asumir, sin inventar, reproducible."""

    @classmethod
    def setUpClass(cls):
        cls.rs = _cargar(RUN_STATE)
        cls.man = _cargar(MANIFEST)
        if cls.rs is None or cls.man is None:
            raise unittest.SkipTest("falta el Golden 040-646406")
        cls.a = egs.ejecutar(cls.rs, cls.man)
        cls.b = egs.ejecutar(cls.rs, cls.man)
        cls.r = cls.a["resultado"]
        cls.gate = cls.r["estimation_gate"]
        cls.calidad = cls.r["evidence_quality"]
        cls.c = cls.a["contadores"]

    # ── §27 · reproducibilidad ────────────────────────────────────────────────
    def test_la_decision_es_reproducible(self):
        """Mismo expediente → misma compuerta, estado, calidad, rango y hash."""
        for campo in ("status", "range_low", "range_high", "central_estimate",
                      "value_m2_central", "confidence_label", "hash_payload"):
            self.assertEqual(self.r[campo], self.b["resultado"][campo],
                             f"«{campo}» no es reproducible")
        self.assertEqual(self.gate["gate_state"],
                         self.b["resultado"]["estimation_gate"]["gate_state"])
        self.assertEqual(self.calidad["level"],
                         self.b["resultado"]["evidence_quality"]["level"])
        self.assertEqual(self.c["manual_inputs_used"],
                         self.b["contadores"]["manual_inputs_used"])
        self.assertEqual(self.r["confidence_label"], self.calidad["level"])

    def test_el_resultado_cumple_el_contrato(self):
        v = est.validar_resultado(self.r)
        self.assertTrue(v["valido"], f"EstimationResult incompleto: {v}")
        self.assertIn(self.r["status"], est.ESTADOS_ESTIMACION)
        self.assertIn(self.gate["gate_state"], est.ESTADOS_ESTIMATION_GATE)
        # Una estimación NUNCA es un valor verificado, en ningún estado.
        self.assertFalse(est.es_valor_verificado(self.r["status"]))
        self.assertFalse(self.r["envelope"]["es_valor_verificado"])
        self.assertNotIn("norma + concepto técnico + validación profesional",
                         json.dumps(self.r["envelope"], ensure_ascii=False))

    # ── §39 · aceptación dura ────────────────────────────────────────────────
    def test_manual_inputs_used_es_cero(self):
        self.assertEqual(self.c["manual_inputs_used"], 0,
                         "un parámetro MANUAL_CONFIG participó del cálculo")
        self.assertIn(est.am.ORIGEN_MANUAL, self.c["declarados_y_excluidos"],
                      "la corrida declara el parámetro a mano y debe quedar EXCLUIDO")
        self.assertNotIn(est.am.ORIGEN_MANUAL,
                         list(self.r["origin_composition"]["clases_usadas"]))

    def test_legacy_priors_used_es_cero(self):
        self.assertEqual(self.c["legacy_priors_used"], 0,
                         "un prior legacy participó del cálculo")
        self.assertIn(est.ORIGEN_PRIOR_LEGACY, self.c["declarados_y_excluidos"])

    def test_399_500_000_no_es_input_ni_salida(self):
        """La cifra retirada no puede reaparecer: ni en la entrada ni en el resultado."""
        texto = json.dumps(self.a, ensure_ascii=False, default=str)
        self.assertNotIn("399.500.000", texto)
        self.assertNotIn("399500000", texto)
        self.assertIn(self.r["historical_estimate_reference"]["usado_como_input"], [False])
        for campo in ("range_low", "range_high", "central_estimate", "value_m2_central"):
            self.assertNotEqual(self.r[campo], 399_500_000)

    def test_no_se_inventa_rango_ni_cifra(self):
        """Cifra y rango son coherentes con el estado: si no hay método, no hay monto."""
        if not self.r["methods_used_ids"]:
            self.assertIn(self.r["status"], (est.STATUS_NOT_ESTIMABLE,
                                             est.STATUS_INDICATIVE_ESTIMATE))
        if self.r["status"] == est.STATUS_NOT_ESTIMABLE:
            for campo in ("central_estimate", "range_low", "range_high",
                          "value_m2_central", "value_m2_low", "value_m2_high"):
                self.assertIsNone(self.r[campo], f"«{campo}» no puede tener cifra")
        else:
            self.assertLessEqual(self.r["range_low"], self.r["central_estimate"])
            self.assertLessEqual(self.r["central_estimate"], self.r["range_high"])
            self.assertGreater(self.r["range_low"], 0)

    def test_los_metodos_se_evaluaron(self):
        """«No intentó» no es una opción: TODOS los métodos declararon su estado."""
        vistos = {m["method_id"] for m in self.r["methods_used"] + self.r["methods_rejected"]}
        self.assertEqual(vistos, set(est.METODOS))
        for m in self.r["methods_rejected"]:
            self.assertTrue(m.get("reason"), f"{m['method_id']} sin motivo declarado")

    # ── §22 · el nivel 3 produce rango, y ese rango es auditable ─────────────
    def test_el_nivel_3_produce_rango_derivado(self):
        """Con la referencia agregada de nivel 3: OPEN_WITH_LIMITATIONS + INDICATIVE."""
        estadisticas = self.a["entrada"].get("estadisticas_externas") or []
        if not estadisticas:
            self.skipTest("esta corrida no incorpora referencia agregada de nivel 3")
        self.assertEqual(self.gate["gate_state"], est.ESTIMATION_OPEN_WITH_LIMITATIONS)
        self.assertEqual(self.r["status"], est.STATUS_INDICATIVE_ESTIMATE)
        self.assertEqual(self.calidad["level"], est.QUALITY_INDICATIVE)
        # Nivel 3 agrega por sector y banda: NO puede abrir OPEN ni un valor verificado.
        self.assertNotEqual(self.gate["gate_state"], est.ESTIMATION_OPEN)
        self.assertFalse(self.r["envelope"]["es_valor_verificado"])
        # El rango se deriva del ancho (§15) sobre la referencia central (§12).
        semi = self.r["range"]["semi_ancho_relativo"]
        self.assertIsNotNone(semi)
        self.assertGreater(semi, 0)
        self.assertEqual(self.r["range"]["formula_version"], est.RANGE_WIDTH_VERSION)
        self.assertEqual(self.r["range"]["componentes"]["dispersion_origen"],
                         est.METODO_M5)
        self.assertEqual(
            self.r["central_estimate"],
            est.redondear_segun_evidencia(self.r["central_estimate"], semi))
        # La referencia central por m² es el CENTRO del rango declarado por la fuente…
        ref = (self.a["entrada"]["estadisticas_externas"] or [])[0]["rango_valor_m2"]
        self.assertAlmostEqual(self.r["value_m2_central"], (ref["min"] + ref["max"]) / 2,
                               places=2)
        # …y la cifra del inmueble es su producto por el área, redondeado por el ancho.
        self.assertEqual(
            self.r["central_estimate"],
            est.redondear_segun_evidencia(self.r["value_m2_central"]
                                          * self.r["inputs"]["area_m2"], semi))
        # La cifra central es GRUESA: el paso de redondeo lo impone el ancho, no el gusto.
        paso = next(p for umbral, p in est.PRECISION_POR_ANCHO if semi >= umbral)
        self.assertEqual(self.r["central_estimate"] % paso, 0)
        self.assertIn(est.METODO_M5, self.r["methods_used_ids"])

    def test_m5_no_declara_el_valor_de_la_fuente(self):
        """La fuente publica un RANGO: el motor NO fabrica un valor único de la fuente."""
        estadisticas = self.a["entrada"].get("estadisticas_externas") or []
        if not estadisticas:
            self.skipTest("esta corrida no incorpora referencia agregada de nivel 3")
        for ref in estadisticas:
            self.assertIsNone(ref.get("valor_m2"),
                              "la referencia agregada no publica un valor único")
            self.assertTrue(ref.get("rango_valor_m2"), "debe declarar su banda")
        m5 = [m for m in self.r["methods_used"] + self.r["methods_rejected"]
              if m["method_id"] == est.METODO_M5][0]
        self.assertEqual(m5["status"], est.STATUS_METHOD_AVAILABLE)
        self.assertTrue(m5["result"]["no_es_valor_de_la_fuente"])
        self.assertTrue(m5["result"]["no_es_valor_de_la_unidad"])
        self.assertTrue(m5["result"]["referencia_central_del_rango"])
        # El rango declarado por la fuente viaja ÍNTEGRO y sin tocar.
        rango_ref = estadisticas[0]["rango_valor_m2"]
        self.assertEqual(m5["result_range"]["low"], rango_ref["min"])
        self.assertEqual(m5["result_range"]["high"], rango_ref["max"])
        no_aplicados = {a["tipo"] for a in m5["adjustments"] if a["estado"] == "NO_APLICADO"}
        self.assertIn("promedio aritmético de los extremos", no_aplicados)
        self.assertIn("división por el área del sujeto", no_aplicados)
        self.assertEqual(self.r["origin_composition"]["clases_usadas"], ["EXTERNAL_SOURCE"])

    def test_el_rango_sale_directo_de_la_fuente(self):
        """§29 · `range_low`/`range_high` = rango OFICIAL aplicado al área, sin promedio."""
        estadisticas = self.a["entrada"].get("estadisticas_externas") or []
        if not estadisticas:
            self.skipTest("esta corrida no incorpora referencia agregada de nivel 3")
        ref = estadisticas[0]
        banda = ref["rango_valor_m2"]
        area = self.r["inputs"]["area_m2"]
        usada = self.r["range"]["banda_oficial_usada"]
        self.assertIsNotNone(usada, "el resultado debe publicar la banda oficial usada")
        self.assertEqual(usada["min"], banda["min"])
        self.assertEqual(usada["max"], banda["max"])
        semi = self.r["range"]["semi_ancho_relativo"]
        # Bordes = min/max literales × área, redondeados HACIA FUERA (nunca hacia dentro).
        self.assertEqual(self.r["range_low"], est._redondear_borde(banda["min"] * area, semi,
                                                                   abajo=True))
        self.assertEqual(self.r["range_high"], est._redondear_borde(banda["max"] * area, semi,
                                                                    abajo=False))
        # El rango nunca es más estrecho que la banda oficial que lo sostiene.
        self.assertLessEqual(self.r["range_low"], banda["min"] * area)
        self.assertGreaterEqual(self.r["range_high"], banda["max"] * area)
        # Y el ancho declarado es el EFECTIVO del rango publicado, no el calculado a secas.
        self.assertGreaterEqual(semi, self.r["range"]["componentes"]["semi_ancho_calculado"])
        self.assertAlmostEqual(semi, (self.r["range_high"] - self.r["range_low"])
                               / (2 * self.r["central_estimate"]), places=4)

    def test_el_verified_gate_sigue_cerrado_con_nivel_3(self):
        """§30 · dos compuertas que COEXISTEN: estimación abierta, evidencia no verificada."""
        estadisticas = self.a["entrada"].get("estadisticas_externas") or []
        if not estadisticas:
            self.skipTest("esta corrida no incorpora referencia agregada de nivel 3")
        vg = self.r["verified_market_evidence_gate"]
        self.assertEqual(vg["gate_state"], est.VERIFIED_CLOSED)
        self.assertEqual(self.gate["gate_state"], est.ESTIMATION_OPEN_WITH_LIMITATIONS)
        razones = " | ".join(vg["reasons"])
        self.assertIn("nivel 3", razones.lower())
        self.assertIn("NO acredita la unidad", razones)
        self.assertTrue(vg.get("evidencia_agregada_no_atribuible"))

    def test_m5_no_usa_una_referencia_que_no_cumple(self):
        """Fail-closed: sin procedencia completa, sin rango o sin banda que contenga el área."""
        base = entrada()
        ref_ok = {
            "origen_tipo": "EXTERNAL_SOURCE", "nivel": est.NIVEL_REFERENCIA_AGREGADA,
            "source_id": "BAQ_X", "proveedor": "Geoportal", "fecha": "2026-09-30",
            "referencia": "r", "sha256": "a" * 64,
            "rango_valor_m2": {"min": 2_000_000.0, "max": 8_000_000.0},
            "banda_area_m2": "36-60", "sample_size": None,
            "metodologia_declarada": "análisis de compraventas SNR",
            "provenance": {"source_id": "BAQ_X", "proveedor": "Geoportal",
                           "fecha": "2026-09-30", "referencia": "r", "sha256": "a" * 64,
                           "url": "https://ejemplo/query", "consultado_en": "2026-09-30T00:00:00+00:00",
                           "http": 200, "bytes": 740},
        }
        # 1 · sin declarar nada → NOT_APPLICABLE
        self.assertEqual(est.metodo_m5_referencia_agregada(base)["status"],
                         est.STATUS_METHOD_NOT_APPLICABLE)
        # 2 · declarada pero SIN procedencia HTTP → INSUFFICIENT_DATA, no se usa
        sin_prov = {k: v for k, v in ref_ok.items() if k != "provenance"}
        m = est.metodo_m5_referencia_agregada({**base, "estadisticas_externas": [sin_prov]})
        self.assertEqual(m["status"], est.STATUS_METHOD_INSUFFICIENT_DATA)
        self.assertIsNone(m["result"])
        # 3 · HTTP != 200 → INSUFFICIENT_DATA
        prov_500 = {**ref_ok["provenance"], "http": 500}
        m = est.metodo_m5_referencia_agregada(
            {**base, "estadisticas_externas": [{**ref_ok, "provenance": prov_500}]})
        self.assertEqual(m["status"], est.STATUS_METHOD_INSUFFICIENT_DATA)
        self.assertIn("http=200", " ".join(m["inputs"]["faltantes"]))
        # 4 · banda que NO contiene el área del sujeto (82,5 m²) → INSUFFICIENT_DATA
        m = est.metodo_m5_referencia_agregada({**base, "estadisticas_externas": [ref_ok]})
        self.assertEqual(m["status"], est.STATUS_METHOD_INSUFFICIENT_DATA)
        self.assertIn("no acredita contener el área del sujeto", m["reason"])
        # 5 · con el área del sujeto dentro de la banda → AVAILABLE y sin inventar valor_m2
        e = entrada(area={"valor_m2": 58.75, "origen_tipo": "EXTERNAL_SOURCE",
                          "provenance": {"source_id": "S", "proveedor": "P",
                                         "fecha": "2026-01-01", "referencia": "x",
                                         "sha256": "b" * 64}},
                    estadisticas_externas=[ref_ok])
        m = est.metodo_m5_referencia_agregada(e)
        self.assertEqual(m["status"], est.STATUS_METHOD_AVAILABLE)
        self.assertEqual(m["result_range"], {"low": 2_000_000.0, "high": 8_000_000.0,
                                            "basis": "banda oficial declarada por la fuente "
                                                     "(min/max LITERALES)"})
        self.assertEqual(m["result"]["origen_tipo"], est.ORIGEN_DERIVADO_EXTERNO)
        # §5.3 · CORRECCIÓN SEMÁNTICA: una transformación determinista de UNA sola
        # fuente externa NO puede etiquetarse `COMPUTED_FROM_SOURCES` (esa clase exige
        # ≥2 fuentes materiales). La aserción ENDURECE: además de exigir la clase
        # correcta, prohíbe explícitamente la clase que la doctrina reserva a ≥2 fuentes.
        self.assertEqual(m["origin"], est.am.ORIGEN_EXTERNO)
        self.assertNotEqual(m["origin"], est.am.ORIGEN_COMPUTADO)
        self.assertNotEqual(m["result"]["origen_tipo"], est.am.ORIGEN_COMPUTADO)
        self.assertEqual(m["derivation"]["type"], est.DERIVACION_PUNTO_MEDIO_RANGO)
        self.assertEqual(m["derivation"]["formula"], est.DERIVACION_FORMULA_PUNTO_MEDIO)
        self.assertEqual(m["derivation"]["source_count"], 1)
        self.assertEqual(m["derivation"]["source_ids"], [ref_ok["source_id"]])
        self.assertTrue(m["derivation"]["no_es_composicion_de_fuentes"])
        self.assertTrue(m["result"]["no_es_valor_de_la_fuente"])
        self.assertEqual(m["result"]["derivacion"],
                         "punto medio del rango oficial (min_valor_m2 + max_valor_m2) / 2")
        self.assertIsNone(m["inputs"]["sample_size"])
        self.assertFalse(m["inputs"]["sample_size_declarado"])

    def test_la_ausencia_de_muestra_no_impide_pero_degrada(self):
        """`sample_size=null` NO se rellena: no impide el método y viaja en limitations."""
        estadisticas = self.a["entrada"].get("estadisticas_externas") or []
        if not estadisticas:
            self.skipTest("esta corrida no incorpora referencia agregada de nivel 3")
        for ref in estadisticas:
            self.assertIsNone(ref.get("sample_size"))
        m5 = [m for m in self.r["methods_used"] + self.r["methods_rejected"]
              if m["method_id"] == est.METODO_M5][0]
        self.assertEqual(m5["status"], est.STATUS_METHOD_AVAILABLE)
        self.assertIsNone(m5["inputs"]["sample_size"])
        no_aplicados = {a["tipo"]: a["estado"] for a in m5["adjustments"]}
        self.assertEqual(no_aplicados.get("muestra (N) del análisis"), "NO_APLICADO")
        self.assertIn("muestra", " ".join(self.r["limitations"]).lower())
        self.assertIn(est.QUALITY_INDICATIVE, [self.calidad["level"]])
        # La calidad queda DEGRADADA, no insuficiente: hay estimación, no valor verificado.
        self.assertNotEqual(self.calidad["level"], est.QUALITY_INSUFFICIENT)
        self.assertNotEqual(self.calidad["level"], est.QUALITY_HIGH)

    def test_el_metodo_impreso_cita_fuente_y_rango(self):
        """§33 · el MÉTODO de la P6 nombra el método, la fuente y el rango oficial."""
        p6 = self.estimacion["p6"] if hasattr(self, "estimacion") else None
        if p6 is None:
            p6 = egs.contrato_p6(self.r, consulta=self.a["referencia"])
        metodo = str(p6["MÉTODO"])
        self.assertIn("REFERENCIA AGREGADA OFICIAL POR LOCALIDAD Y BANDA DE ÁREA", metodo)
        estadisticas = self.a["entrada"].get("estadisticas_externas") or []
        if estadisticas:
            self.assertIn(str(estadisticas[0]["source_id"]), metodo)
            self.assertIn("banda oficial", metodo)
            self.assertIn(egs.pesos(estadisticas[0]["rango_valor_m2"]["min"]), metodo)
            self.assertIn(egs.pesos(estadisticas[0]["rango_valor_m2"]["max"]), metodo)

    def test_lo_que_falta_para_subir_de_nivel(self):
        """Aun estimando, la corrida declara la evidencia automática que falta (§28)."""
        from estimation_golden import faltantes_economicos
        brecha = egs.cargar_brecha_de_cosecha()
        faltan = faltantes_economicos(self.r, brecha)
        texto = " | ".join(faltan)
        self.assertTrue(faltan, "debe declararse qué evidencia automática falta")
        if not brecha:
            self.skipTest("no hay cosecha municipal en esta corrida")
        # Las tres vías concretas que quedan abiertas.
        self.assertIn("sample_size", texto)
        self.assertIn("valorcompraventas", texto)
        self.assertIn("area_construida_m2", texto)
        self.assertIn("SNR", texto)

    # ── §39 · evidencia literal ───────────────────────────────────────────────
    def test_la_evidencia_literal_del_golden(self):
        from estimation_golden import bloque_de_evidencia, veredicto_de
        ev = bloque_de_evidencia(self.gate, self.calidad, self.r, self.c)
        self.assertEqual(ev["ESTIMATION_GATE"]["state"], self.gate["gate_state"])
        self.assertEqual(ev["EVIDENCE_QUALITY"]["level"], self.calidad["level"])
        self.assertEqual(ev["ESTIMATION_RESULT"]["status"], self.r["status"])
        self.assertTrue(ev["aceptacion"]["manual inputs used = 0"])
        self.assertTrue(ev["aceptacion"]["legacy priors used = 0"])
        self.assertEqual(ev["contadores"]["manual_inputs_used"], 0)
        self.assertEqual(ev["contadores"]["legacy_priors_used"], 0)
        esperado = {est.STATUS_ESTIMATED: "DICTUS ESTIMATION ENGINE — ESTIMATE PRODUCED",
                    est.STATUS_ESTIMATED_WITH_LIMITATIONS:
                        "DICTUS ESTIMATION ENGINE — ESTIMATE PRODUCED",
                    est.STATUS_INDICATIVE_ESTIMATE:
                        "DICTUS ESTIMATION ENGINE — INDICATIVE ESTIMATE PRODUCED",
                    est.STATUS_NOT_ESTIMABLE: "DICTUS ESTIMATION ENGINE — NOT ESTIMABLE"}
        self.assertEqual(veredicto_de(self.r), esperado[self.r["status"]])
        self.assertIn(egs.confianza_de(self.r),
                      ("ALTA", "MEDIA", "INDICATIVA", "NINGUNA"))

    # ── §39 · procedencia ────────────────────────────────────────────────────
    def test_procedencia_de_la_evidencia_agregada(self):
        """Lo que entra como evidencia externa trae procedencia auditable, o no entra."""
        estadisticas = self.a["entrada"].get("estadisticas_externas") or []
        for e in estadisticas:
            self.assertEqual(e["origen_tipo"], est.am.ORIGEN_EXTERNO)
            for campo in ("source_id", "proveedor", "fecha", "referencia", "sha256"):
                self.assertTrue(e.get(campo), f"referencia externa sin «{campo}»")
            cl = e.get("checklist_procedencia") or {}
            for campo in ("url", "consultado_en", "http", "bytes", "sha256"):
                self.assertTrue(cl.get(campo),
                                f"procedencia HTTP incompleta: falta «{campo}»")
            # lo que la fuente NO declara se declara como faltante (nunca se rellena)
            self.assertEqual(sorted(cl.keys()), sorted(egs.CHECKLIST_PROCEDENCIA))
            self.assertEqual(e.get("valor_m2"), None if e.get("rango_valor_m2") else None)
        cosecha = (self.a["entrada"]["auditoria_de_entrada"]
                   .get("cosecha_municipal") or {})
        self.assertIn(cosecha.get("estado"), ("INCORPORADA", "NO INCORPORADA"))
        if cosecha.get("estado") == "NO INCORPORADA":
            self.assertEqual(estadisticas, [],
                             "no se incorpora cosecha pero la entrada trae estadísticas")

    def test_la_tasa_manual_entra_declarada_y_excluida(self):
        """El parámetro a mano se declara (para poder auditarlo) y NO participa."""
        tm = self.a["entrada"].get("tasa_manual")
        if tm:
            self.assertEqual(tm["origen_tipo"], est.am.ORIGEN_MANUAL)
            self.assertTrue(tm.get("declarado_en"))
        comp = self.r["origin_composition"]
        self.assertNotIn(est.am.ORIGEN_MANUAL, comp["clases_usadas"])
        self.assertIn(est.am.ORIGEN_MANUAL, comp["clases_excluidas"])
        self.assertNotIn(comp["origin"], (est.am.ORIGEN_MANUAL, est.ORIGEN_NO_PRODUCTIVO))
        self.assertFalse(comp["sostiene_estimacion"]
                         and est.am.ORIGEN_MANUAL in comp["clases_usadas"])

    # ── §28 · cierre demostrado ──────────────────────────────────────────────
    def test_cierre_demostrado_con_brecha_concreta(self):
        """Sin soporte económico el motor CIERRA y demuestra por qué, con brecha concreta."""
        r = estimar(entrada())          # entrada real sin ninguna fuente de mercado
        gate = r["estimation_gate"]
        self.assertEqual(gate["gate_state"], est.ESTIMATION_CLOSED)
        self.assertEqual(r["status"], est.STATUS_NOT_ESTIMABLE)
        razones = " | ".join(gate["reasons"])
        self.assertIn("MISSING_MARKET_EVIDENCE", razones)
        self.assertTrue(gate["inputs_missing"], "el cierre debe declarar qué falta")
        gap = r["gap_report"]
        self.assertIsNotNone(gap, "un CLOSED exige informe_de_brecha")
        self.assertEqual(gap["motivo_cierre"], "MISSING_MARKET_EVIDENCE")
        self.assertTrue(gap["falta"], "la brecha debe nombrar QUÉ falta")
        self.assertTrue(gap["fuentes_automaticas_a_incorporar"])
        for f in gap["fuentes_automaticas_a_incorporar"]:
            self.assertEqual(f["estado"], "NO INCORPORADA")
            self.assertTrue(f["fuente"] and f["aporta"])
        # Y el mismo estado se imprime sin cifra.
        p6 = egs.contrato_p6(r, consulta="2026-07-01")
        self.assertEqual(p6["RANGO ESTIMADO"], "no disponible")
        self.assertEqual(p6["REFERENCIA CENTRAL"], "no disponible")

    def test_la_brecha_concreta_de_la_cosecha(self):
        """La petición trae capa, URL y campos: pedir «una fuente» en abstracto no sirve."""
        from estimation_golden import faltantes_economicos
        brecha = egs.cargar_brecha_de_cosecha()
        faltan = faltantes_economicos(self.r, brecha)
        self.assertTrue(faltan, "debe declararse qué evidencia automática falta")
        for f in faltan:
            self.assertIsInstance(f, str)
            self.assertTrue(f.strip())
        for peticion in brecha:
            self.assertTrue(peticion.get("fuente_automatica"))

    def test_el_contrato_de_impresion_no_imprime_cifra_inexistente(self):
        p1 = egs.contrato_p1(self.r)
        p6 = egs.contrato_p6(self.r, consulta=self.a["referencia"])
        if self.r["range_low"] is None:
            self.assertEqual(p6["RANGO ESTIMADO"], "no disponible")
            self.assertEqual(p6["REFERENCIA CENTRAL"], "no disponible")
            self.assertEqual(p6["VALOR/M²"], "no disponible")
            self.assertNotIn("$", p6["RANGO ESTIMADO"])
        else:
            # Con rango: se imprime EL DEL MOTOR, sin recalcular ni redondear de nuevo.
            self.assertIn(egs.pesos(self.r["range_low"]), p6["RANGO ESTIMADO"])
            self.assertIn(egs.pesos(self.r["range_high"]), p6["RANGO ESTIMADO"])
            self.assertIn(egs.pesos(self.r["central_estimate"]), p6["REFERENCIA CENTRAL"])
            self.assertIn(egs.pesos(self.r["range_low"]), p1["linea_2"])
            self.assertNotIn("399.500.000", p1["linea_2"] + p6["RANGO ESTIMADO"])
            self.assertNotIn("$399", p1["linea_2"] + p6["RANGO ESTIMADO"])
        if self.r["status"] == est.STATUS_NOT_ESTIMABLE:
            self.assertEqual(p1["etiqueta"], "ESTIMACIÓN NO DISPONIBLE")
            self.assertIn("Sin evidencia de mercado suficiente", p1["linea_2"])
            self.assertIsNone(p1["central"])
            self.assertIsNone(p1["rango"])


# ══════════════════════════════════════════════════════════════════════════════
# §32/§33 · CONTRATOS DE IMPRESIÓN (las tres ramas, con el motor real)
# ══════════════════════════════════════════════════════════════════════════════
class TestContratosDelMotor(unittest.TestCase):
    """Las tres ramas del contrato se derivan del ESTADO del motor, no de un literal."""

    @classmethod
    def setUpClass(cls):
        cls.estimado = estimar(entrada(comparables=comparables_validos(5)))
        cls.indicativo = estimar(entrada(comparables=comparables_validos(3)))
        # El cierre REAL se obtiene de una entrada SIN soporte económico: es el estado
        # que el motor declara cuando no hay ninguna fuente de mercado.
        cls.cerrado = estimar(entrada())

    def test_rama_estimated(self):
        r = self.estimado
        self.assertEqual(r["status"], est.STATUS_ESTIMATED)
        p1 = egs.contrato_p1(r)
        self.assertIn("VALOR ESTIMADO", p1["etiqueta"])
        self.assertEqual(p1["confianza"], "MEDIA")
        self.assertIn(egs.pesos(r["central_estimate"]), p1["linea_1"])
        self.assertIn("Rango: " + egs.pesos(r["range_low"]) + " – " + egs.pesos(r["range_high"]),
                      p1["linea_2"])
        self.assertIn("Confianza: MEDIA", p1["linea_2"])
        p6 = egs.contrato_p6(r, consulta="2026-07-01")
        self.assertIn("$", p6["RANGO ESTIMADO"])
        self.assertIn("$", p6["REFERENCIA CENTRAL"])
        self.assertTrue(p6["VALOR/M²"].endswith("/ m²"))
        self.assertEqual(p6["CONFIANZA"], "MEDIA")
        self.assertIn("MARKET COMPARISON", p6["MÉTODO"])
        self.assertNotIn("no disponible", p6["RANGO ESTIMADO"])

    def test_rama_indicative(self):
        r = self.indicativo
        self.assertEqual(r["status"], est.STATUS_INDICATIVE_ESTIMATE)
        p1 = egs.contrato_p1(r)
        self.assertEqual(p1["etiqueta"], "ESTIMACIÓN INDICATIVA")
        self.assertEqual(p1["confianza"], "INDICATIVA")
        self.assertIn("Rango: ", p1["linea_2"])
        self.assertIn("Confianza: INDICATIVA", p1["linea_2"])
        p6 = egs.contrato_p6(r, consulta="2026-07-01")
        self.assertIn("$", p6["RANGO ESTIMADO"])
        self.assertEqual(p6["CONFIANZA"], "INDICATIVA")

    def test_rama_closed(self):
        r = self.cerrado
        self.assertEqual(r["status"], est.STATUS_NOT_ESTIMABLE)
        self.assertEqual(r["estimation_gate"]["gate_state"], est.ESTIMATION_CLOSED)
        p1 = egs.contrato_p1(r)
        self.assertEqual(p1["etiqueta"], "ESTIMACIÓN NO DISPONIBLE")
        self.assertIn("Sin evidencia de mercado suficiente", p1["linea_2"])
        self.assertIn("Confianza: ", p1["linea_2"])
        self.assertNotIn("$", p1["linea_1"])
        self.assertNotIn("$", p1["linea_2"])
        p6 = egs.contrato_p6(r, consulta="2026-07-01")
        self.assertEqual(p6["estado"], est.ESTIMATION_CLOSED)
        self.assertEqual(p6["RANGO ESTIMADO"], "no disponible")
        self.assertEqual(p6["REFERENCIA CENTRAL"], "no disponible")
        self.assertEqual(p6["VALOR/M²"], "no disponible")
        self.assertEqual(p6["NOTA"], egs.NOTA_ESTIMACION_FIJA)

    def test_los_ocho_campos_del_bloque_p6(self):
        for r in (self.estimado, self.indicativo, self.cerrado):
            if r is None:
                continue
            p6 = egs.contrato_p6(r, consulta="2026-07-01")
            for campo in ("RANGO ESTIMADO", "REFERENCIA CENTRAL", "VALOR/M²", "CONFIANZA",
                          "MÉTODO", "EVIDENCIA UTILIZADA", "LIMITACIONES", "TRAZABILIDAD"):
                self.assertIn(campo, p6)
                self.assertTrue(str(p6[campo]).strip(), f"«{campo}» vacío")
            self.assertIn("TRAZABILIDAD · Fuentes:", p6["TRAZABILIDAD"])
            self.assertIn("Consulta: ", p6["TRAZABILIDAD"])

    def test_el_texto_fijo_permitido_es_el_unico_y_es_literal(self):
        esperado = ("Estimación automatizada de DICTUS basada en la información disponible "
                    "para esta corrida. No constituye un avalúo comercial certificado "
                    "cuando este sea legal o contractualmente requerido.")
        self.assertEqual(egs.NOTA_ESTIMACION_FIJA, esperado)
        self.assertEqual(de.NOTA_ESTIMACION, esperado)
        self.assertFalse(est.contiene_vocabulario_metodologico_prohibido(esperado))

    def test_la_confianza_es_derivada_no_escrita(self):
        self.assertEqual(egs.confianza_de(self.estimado), "MEDIA")
        self.assertEqual(egs.confianza_de(self.indicativo), "INDICATIVA")
        self.assertEqual(egs.ETIQUETA_CONFIANZA[est.QUALITY_HIGH], "ALTA")
        self.assertEqual(egs.ETIQUETA_CONFIANZA[est.QUALITY_INSUFFICIENT], "NINGUNA")
        for r in (self.estimado, self.indicativo):
            self.assertEqual(egs.confianza_de(r),
                             egs.ETIQUETA_CONFIANZA[r["evidence_quality"]["level"]])


class TestRenderizadorP1P6(unittest.TestCase):
    """El PDF imprime las tres ramas: el cableado, no el contrato en abstracto."""

    @classmethod
    def setUpClass(cls):
        par = _estado_real()
        if par is None:
            raise unittest.SkipTest("falta el estado del Golden")
        cls.rs, cls.hist = par
        SALIDA.mkdir(parents=True, exist_ok=True)
        cls.contratos = {
            "ESTIMATED": estimar(entrada(comparables=comparables_validos(5))),
            "INDICATIVE_ESTIMATE": estimar(entrada(comparables=comparables_validos(3))),
            # El cierre REAL del motor (sin soporte económico) se imprime también: las tres
            # ramas del contrato quedan cableadas y verificadas en el PDF.
            "CLOSED": estimar(entrada()),
        }
        cls.paginas = {}
        cls.violaciones = {}
        for etiqueta, r in cls.contratos.items():
            cls.paginas[etiqueta], cls.violaciones[etiqueta] = cls._render(etiqueta, r)

    @classmethod
    def _render(cls, etiqueta, resultado):
        rs = copy.deepcopy(cls.rs)
        modelo = dm.construir_documento_maestro(rs, historial=cls.hist, folio=FOLIO)
        secciones = sec.desde_estado(rs, modelo, cls.hist)
        secciones["estimacion"]["p1"] = egs.contrato_p1(resultado)
        secciones["estimacion"]["p6"] = egs.contrato_p6(
            resultado, consulta=secciones["estimacion"].get("referencia"))
        pdf = SALIDA / f"p1p6_{etiqueta}.pdf"
        del de.VIOLACIONES[:]
        de.render(modelo, secciones, pdf)
        from pypdf import PdfReader
        paginas = [(p.extract_text() or "") for p in PdfReader(str(pdf)).pages]
        return paginas, list(de.VIOLACIONES)

    def _plano(self, etiqueta, pagina):
        return " ".join(self.paginas[etiqueta][pagina].split())

    def test_p1_rama_estimated(self):
        p1 = self._plano("ESTIMATED", 0)
        r = self.contratos["ESTIMATED"]
        self.assertIn("ESTIMACIÓN ECONÓMICA DICTUS · VALOR ESTIMADO", p1)
        self.assertIn(egs.pesos(r["central_estimate"]), p1)
        self.assertIn("Rango: " + egs.pesos(r["range_low"]) + " – "
                      + egs.pesos(r["range_high"]), p1)
        self.assertIn("Confianza: MEDIA", p1)

    def test_p1_rama_indicativa(self):
        p1 = self._plano("INDICATIVE_ESTIMATE", 0)
        r = self.contratos["INDICATIVE_ESTIMATE"]
        self.assertIn("ESTIMACIÓN ECONÓMICA DICTUS · ESTIMACIÓN INDICATIVA", p1)
        self.assertIn("Rango: " + egs.pesos(r["range_low"]) + " – "
                      + egs.pesos(r["range_high"]), p1)
        self.assertIn("Confianza: INDICATIVA", p1)

    def test_p1_rama_cerrada(self):
        p1 = self._plano("CLOSED", 0)
        self.assertIn("ESTIMACIÓN ECONÓMICA DICTUS · ESTIMACIÓN NO DISPONIBLE", p1)
        self.assertIn("Sin evidencia de mercado suficiente", p1)
        # La tira de estimación NO lleva cifra ni rango cuando el motor no los produjo.
        tira = p1.split("ESTIMACIÓN ECONÓMICA DICTUS")[-1][:400]
        self.assertNotIn("$", tira.split("CONFIANZA")[0])
        self.assertNotIn("DICTUS · VALOR ESTIMADO", p1)

    def test_p6_bloque_estimacion_economica(self):
        for etiqueta in ("ESTIMATED", "INDICATIVE_ESTIMATE", "CLOSED"):
            p6 = self._plano(etiqueta, 5)
            self.assertIn("ESTIMACIÓN ECONÓMICA", p6)
            for campo in de.CAMPOS_ESTIMACION_P6:
                self.assertIn(campo, p6, f"{etiqueta}: falta «{campo}» en la P6")
            self.assertIn(egs.NOTA_ESTIMACION_FIJA, p6)
            self.assertIn("Metodología: fuentes disponibles + análisis técnico automatizado "
                          "+ metodología versionada", p6)
            self.assertNotIn("norma + concepto técnico + validación profesional", p6)

    def test_p6_cerrada_no_imprime_monto_de_estimacion(self):
        p6 = self._plano("CLOSED", 5)
        self.assertIn("RANGO ESTIMADO no disponible", p6)
        self.assertIn("REFERENCIA CENTRAL no disponible", p6)
        self.assertIn("VALOR/M² no disponible", p6)
        # La valoración declarada por la corrida sigue su propio carril y su propio estado.
        self.assertIn("COMPUERTA CLOSED", p6)
        self.assertIn("NO EMITIR VALORACIÓN", p6.upper())

    def test_sin_violaciones_de_layout_en_las_tres_ramas(self):
        for etiqueta, violaciones in self.violaciones.items():
            self.assertEqual(violaciones, [], f"{etiqueta}: violaciones {violaciones}")
            self.assertEqual(list(de.VIOLACIONES), [])
        self.assertEqual(de.verificar_retícula(), [])

    def test_el_presupuesto_de_pagina_se_respeta(self):
        for etiqueta in ("ESTIMATED", "INDICATIVE_ESTIMATE", "CLOSED"):
            for pagina in range(1, 7):
                b = de.page_budget(pagina)
                self.assertEqual(b["footer_limit"], de.PIE_Y)
                self.assertFalse(b["overflow"], f"{etiqueta}: P{pagina} desborda")
            self.assertGreaterEqual(de.page_budget(6)["remaining_height"], 65.0)

    def test_la_p1_y_la_p6_no_repiten_la_cifra_retirada(self):
        for etiqueta in self.contratos:
            plano = " ".join(self._plano(etiqueta, i) for i in (0, 5))
            self.assertNotIn("399.500.000", plano)
            self.assertNotIn("Lonja", plano)


class TestGoldenRealEnElPdf(unittest.TestCase):
    """El expediente REAL, SIN inyectar nada: lo que el motor dice es lo que se imprime."""

    @classmethod
    def setUpClass(cls):
        par = _estado_real()
        if par is None:
            raise unittest.SkipTest("falta el estado del Golden")
        cls.rs, cls.hist = par
        SALIDA.mkdir(parents=True, exist_ok=True)
        modelo = dm.construir_documento_maestro(copy.deepcopy(cls.rs), historial=cls.hist,
                                                folio=FOLIO)
        secciones = sec.desde_estado(cls.rs, modelo, cls.hist)
        cls.modelo, cls.secciones = modelo, secciones
        cls.estimacion = secciones.get("estimacion") or {}
        pdf = SALIDA / "golden_real.pdf"
        del de.VIOLACIONES[:]
        de.render(modelo, secciones, pdf)
        cls.violaciones = list(de.VIOLACIONES)
        from pypdf import PdfReader
        cls.paginas = [(p.extract_text() or "") for p in PdfReader(str(pdf)).pages]

    def _plano(self, pagina):
        return " ".join(self.paginas[pagina].split())

    def test_la_seccion_de_estimacion_viaja_en_el_estado(self):
        self.assertIn("p1", self.estimacion)
        self.assertIn("p6", self.estimacion)
        self.assertIn("resultado", self.estimacion)
        self.assertEqual(self.estimacion["contadores"]["manual_inputs_used"], 0)
        self.assertEqual(self.estimacion["contadores"]["legacy_priors_used"], 0)
        self.assertNotIn("399.500.000",
                         json.dumps(self.estimacion, ensure_ascii=False, default=str))

    def test_p1_y_p6_imprimen_la_estimacion_del_motor(self):
        r = self.estimacion["resultado"]
        p1 = self._plano(0)
        p6 = self._plano(5)
        etiqueta = egs.etiqueta_de(r)
        self.assertIn(f"ESTIMACIÓN ECONÓMICA DICTUS · {etiqueta}", p1)
        self.assertIn("ESTIMACIÓN ECONÓMICA", p6)
        self.assertIn(f"Confianza: {egs.confianza_de(r)}", p1)
        if r["range_low"] is not None:
            rango = f"Rango: {egs.pesos(r['range_low'])} – {egs.pesos(r['range_high'])}"
            self.assertIn(rango, p1)
            self.assertIn(f"{egs.pesos(r['range_low'])} – {egs.pesos(r['range_high'])}", p6)
            self.assertIn(egs.pesos(r["central_estimate"]), p6)
            self.assertIn(egs.METODOLOGIA_IMPRESA, p6)
        for campo in de.CAMPOS_ESTIMACION_P6:
            self.assertIn(campo, p6, f"falta «{campo}» en la P6")
        self.assertIn(egs.NOTA_ESTIMACION_FIJA, p6)
        self.assertNotIn("399.500.000", p1 + p6)
        self.assertNotIn("$399", p1 + p6)
        self.assertNotIn("Lonja", p1 + p6)

    def test_el_chip_del_bloque_concuerda_con_la_cifra(self):
        """El chip del panel no puede decir «NO DISPONIBLE» al lado de un rango impreso."""
        p6 = self._plano(5)
        p1 = self._plano(0)
        self.assertIn(f"ESTIMACIÓN ECONÓMICA DICTUS · {self.estimacion['p6']['etiqueta']}", p1)
        self.assertEqual(self.estimacion["p6"]["habilitado"],
                         self.estimacion["p6"]["RANGO ESTIMADO"] != "no disponible")
        if self.estimacion["p6"]["habilitado"]:
            self.assertIn("DISPONIBLE", p6)
            self.assertNotIn("NO DISPONIBLE ESTIMACIÓN INDICATIVA", p6)
            self.assertNotIn("NO DISPONIBLE ESTIMACIÓN NO", p6)
        else:
            self.assertIn("NO DISPONIBLE", p6)
        # La limitación impresa es la que el lector necesita primero: base agregada.
        self.assertIn("referencia AGREGADA", p6)
        self.assertIn("NO acredita la unidad", p6)

    def test_el_pdf_respeta_el_presupuesto(self):
        self.assertEqual(self.violaciones, [])
        self.assertEqual(de.verificar_retícula(), [])
        for pagina in range(1, 7):
            self.assertFalse(de.page_budget(pagina)["overflow"],
                             f"P{pagina} desborda")
        self.assertGreaterEqual(de.page_budget(6)["remaining_height"], 65.0)


class TestMetodologiaBaseEnElEjecutivo(unittest.TestCase):
    """§34 · el marco metodológico impreso es el vigente, no el retirado."""

    def test_el_renderizador_usa_el_marco_vigente(self):
        self.assertEqual(de.METODOLOGIA_VALORACION, egs.METODOLOGIA_IMPRESA)
        self.assertIn("fuentes disponibles + análisis técnico automatizado + metodología "
                      "versionada", de.METODOLOGIA_VALORACION)
        self.assertFalse(est.contiene_vocabulario_metodologico_prohibido(
            de.METODOLOGIA_VALORACION))
        self.assertTrue(est.contiene_vocabulario_metodologico_prohibido(
            "norma + concepto técnico + validación profesional"))
        # La revisión profesional sigue existiendo, como PRODUCTO SEPARADO.
        self.assertIn("DICTUS + REVIEW", est.resumen_metodologico()["revision_profesional"])


if __name__ == "__main__":
    unittest.main()

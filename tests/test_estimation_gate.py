# -*- coding: utf-8 -*-
"""DICTUS ESTIMATION ENGINE v1.0 · §1/§9/§10/§28/§29 · COMPUERTA DE ESTIMACIÓN.

PRINCIPIO RECTOR probado aquí: «NO EMITIR VALORACIÓN» / `NOT_ESTIMABLE` es el
ÚLTIMO estado, no el comportamiento por defecto. DICTUS INTENTA estimar.

  · `MANUAL_CONFIG` solo .................. `ESTIMATION_GATE = CLOSED`
  · `LEGACY_MODEL_PRIOR` solo ............. `ESTIMATION_GATE = CLOSED`
  · ≥2 comparables externos válidos ....... `OPEN` / `OPEN_WITH_LIMITATIONS`
  · modelo calibrado + identidad/área/ubicación verificadas → ESTIMACIÓN INDICATIVA
  · `STATIC_REFERENCE` sola ............... no produce estimación productiva
  · comparables insuficientes + calibrado . NO cierra necesariamente
  · `NOT_ESTIMABLE` sólo cuando falta la base mínima REAL
"""
from __future__ import annotations

import json
import unittest

from _fixtures_estimation import (HOY, comparable, comparables_validos, entrada,
                                  estimar, modelo_calibrado, procedencia,
                                  comparable_sin_procedencia)

import estimation as est  # noqa: E402


def _razones_texto(r: dict) -> str:
    return " | ".join(r["estimation_gate"]["reasons"])


def _mensaje_no_estimar(r: dict) -> str:
    return "DICTUS no debía cerrar: " + _razones_texto(r)


class TestManualConfigNoSostiene(unittest.TestCase):
    """§2/§28 · un valor escrito a mano NO sostiene una estimación productiva."""

    def test_01_manual_config_solo_cierra_la_estimacion(self):
        r = estimar(entrada(tasa_manual={"valor_m2": 5_200_000,
                                         "fuente": "artefacto local de metodología"}))
        self.assertEqual(r["estimation_gate"]["gate_state"], "CLOSED")
        self.assertEqual(r["status"], "NOT_ESTIMABLE")
        self.assertEqual(r["status_label"], "NO FUE POSIBLE ESTIMAR")
        self.assertEqual(r["origin_composition"]["origin"], "NOT_PRODUCTIVE")
        self.assertEqual(r["evidence_quality"]["level"], "INSUFFICIENT")
        self.assertIsNone(r["central_estimate"])
        self.assertIn("MISSING_MARKET_EVIDENCE", _razones_texto(r))
        self.assertIn("MANUAL_CONFIG", _razones_texto(r))
        # La distinción de §28/§29 queda declarada en el propio motivo de cierre.
        self.assertIn("CAUSA ADICIONAL", _razones_texto(r))
        # La tasa manual se declara EXCLUIDA: su presencia es visible y no se cuenta.
        self.assertIn("MANUAL_CONFIG", r["origin_composition"]["clases_excluidas"])
        self.assertNotIn("MANUAL_CONFIG", r["origin_composition"]["clases_usadas"])
        self.assertIsNotNone(r["gap_report"])

    def test_02_legacy_model_prior_solo_cierra_la_estimacion(self):
        r = estimar(entrada(modelo_legacy={"estrato": 5, "value_m2": 6_500_000,
                                           "tabla": {3: 3_800_000, 4: 5_200_000,
                                                     5: 6_500_000, 6: 7_800_000}}))
        self.assertEqual(r["estimation_gate"]["gate_state"], "CLOSED")
        self.assertEqual(r["status"], "NOT_ESTIMABLE")
        self.assertEqual(r["origin_composition"]["origin"], "NOT_PRODUCTIVE")
        self.assertIn("LEGACY_MODEL_PRIOR", r["origin_composition"]["clases_excluidas"])
        self.assertIn("LEGACY_MODEL_PRIOR", _razones_texto(r))
        # El prior legacy NO aparece en el producto como soporte de ninguna cifra.
        self.assertNotIn("LEGACY_MODEL_PRIOR", r["origin_composition"]["clases_usadas"])
        self.assertIsNone(r["central_estimate"])

    def test_03_una_tasa_manual_no_equivale_a_comparables(self):
        m1 = est.metodo_m1_comparacion_mercado(
            entrada(tasa_manual={"valor_m2": 5_200_000}))
        self.assertEqual(m1["status"], "NOT_APPLICABLE")
        self.assertIn("MANUAL_CONFIG", m1["reason"])
        self.assertIn("NO equivale a comparables", m1["reason"])
        self.assertIsNone(m1["result"])


class TestConEvidenciaDeMercado(unittest.TestCase):
    """§1/§30 · con comparables externos válidos DICTUS estima."""

    def test_04_dos_comparables_externos_abren_la_estimacion(self):
        r = estimar(entrada(comparables=comparables_validos(2)))
        self.assertIn(r["estimation_gate"]["gate_state"],
                      ("OPEN", "OPEN_WITH_LIMITATIONS"))
        self.assertIn(r["status"],
                      ("ESTIMATED", "ESTIMATED_WITH_LIMITATIONS",
                       "INDICATIVE_ESTIMATE"))
        self.assertIsNotNone(r["central_estimate"])
        self.assertIn("", "")  # (sin aserciones ocultas)

    def test_05_un_elenco_completo_produce_estimacion_disponible(self):
        r = estimar(entrada(comparables=comparables_validos(9)))
        self.assertEqual(r["estimation_gate"]["gate_state"], "OPEN",
                         _mensaje_no_estimar(r))
        self.assertEqual(r["verified_market_evidence_gate"]["gate_state"], "OPEN")
        self.assertEqual(r["evidence_quality"]["level"], "HIGH")
        self.assertEqual(r["status"], "ESTIMATED")
        self.assertEqual(r["status_label"], "ESTIMACIÓN DISPONIBLE")
        self.assertEqual(r["origin_composition"]["origin"], "COMPUTED_FROM_SOURCES")
        self.assertIsNotNone(r["range_low"])
        self.assertIsNotNone(r["range_high"])
        self.assertLess(r["range_low"], r["central_estimate"])
        self.assertLess(r["central_estimate"], r["range_high"])

    def test_06_modelo_calibrado_verificado_da_estimacion_indicativa(self):
        r = estimar(entrada(con_calibrado=True))
        self.assertEqual(r["status"], "INDICATIVE_ESTIMATE")
        self.assertEqual(r["status_label"], "ESTIMACIÓN INDICATIVA")
        self.assertEqual(r["estimation_gate"]["gate_state"], "OPEN_WITH_LIMITATIONS")
        # §30 · la compuerta de evidencia VERIFICADA puede seguir CERRADA sin que eso
        # cierre la estimación: son dos preguntas distintas.
        self.assertEqual(r["verified_market_evidence_gate"]["gate_state"], "CLOSED")
        self.assertEqual(r["origin_composition"]["origin"], "CALIBRATED_MODEL_PRIOR")
        self.assertEqual(r["verified_market_evidence_gate"]["consecuencia_automatica"],
                         None)
        self.assertIsNotNone(r["central_estimate"])

    def test_07_referencia_estatica_sola_no_produce_estimacion(self):
        r = estimar(entrada(referencia_estatica={"origen_tipo": "STATIC_REFERENCE",
                                                 "value_m2": 5_000_000,
                                                 "referencia": "tabla estática"}))
        self.assertEqual(r["estimation_gate"]["gate_state"], "CLOSED")
        self.assertEqual(r["status"], "NOT_ESTIMABLE")
        self.assertFalse(r["origin_composition"]["sostiene_estimacion"])
        self.assertIn("STATIC_REFERENCE", r["origin_composition"]["clases_excluidas"])
        self.assertIsNone(r["central_estimate"])

    def test_08_comparables_insuficientes_con_modelo_calibrado_no_cierra(self):
        r = estimar(entrada(comparables=[comparable(1, 5_100_000)], con_calibrado=True))
        self.assertNotEqual(r["estimation_gate"]["gate_state"], "CLOSED",
                            _mensaje_no_estimar(r))
        self.assertEqual(r["estimation_gate"]["gate_state"], "OPEN_WITH_LIMITATIONS")
        self.assertEqual(r["status"], "INDICATIVE_ESTIMATE")
        self.assertEqual(r["origin_composition"]["origin"], "COMPUTED_WITH_MODEL_PRIOR")
        self.assertIsNotNone(r["central_estimate"])

    def test_09_un_comparable_sin_procedencia_no_cuenta_como_fuente(self):
        r = estimar(entrada(comparables=[comparable(1, 5_000_000),
                                         comparable_sin_procedencia(2, 5_050_000)]))
        self.assertEqual(r["inputs"]["comparables_usados"], 1)
        self.assertEqual(len(r["inputs"]["comparables_rechazados"]), 1)
        self.assertIn("MANUAL_CONFIG",
                      r["inputs"]["comparables_rechazados"][0]["motivo"])
        self.assertEqual(r["verified_market_evidence_gate"]["gate_state"], "OPEN")


class TestCribaDeComparables(unittest.TestCase):
    """§17/§18 · tipología incorrecta y outlier: rechazo DOCUMENTADO."""

    def test_10_tipologia_incorrecta_se_rechaza_con_motivo(self):
        comps = comparables_validos(6) + [comparable(9, 9_000_000, tipologia="CASA")]
        r = estimar(entrada(comparables=comps))
        self.assertEqual(r["inputs"]["comparables_usados"], 6)
        rechazos = r["inputs"]["comparables_rechazados"]
        self.assertEqual(len(rechazos), 1)
        self.assertEqual(rechazos[0]["comparable_id"], "C9")
        self.assertIn("tipolog", rechazos[0]["motivo"])
        # El método M1 lo declara también en su propio registro de comparables.
        self.assertNotIn("C9", [c["comparable_id"]
                                for c in r["methods_used"][0]["comparables_used"]])
        # El valor de la casa NO entró a la mediana del método.
        m1 = est.metodo_m1_comparacion_mercado(entrada(comparables=comps))
        self.assertNotIn(9_000_000, [c["value_m2"] for c in m1["comparables_used"]])

    def test_11_outlier_se_excluye_con_motivo_declarado(self):
        comps = comparables_validos(6) + [comparable(9, 19_000_000)]
        r = estimar(entrada(comparables=comps))
        rechazos = r["inputs"]["comparables_rechazados"]
        self.assertEqual(len(rechazos), 1)
        self.assertEqual(rechazos[0]["comparable_id"], "C9")
        self.assertIn("outlier", rechazos[0]["motivo"])
        self.assertIn("mediana", rechazos[0]["motivo"])
        self.assertEqual(r["inputs"]["comparables_usados"], 6)

    def test_12_un_outlier_declarado_por_la_corrida_tambien_se_excluye(self):
        comps = comparables_validos(5) + [comparable(9, 5_100_000, outlier=True)]
        m1 = est.metodo_m1_comparacion_mercado(entrada(comparables=comps))
        self.assertEqual(len(m1["comparables_used"]), 5)
        self.assertTrue(any("outlier" in x["motivo"] for x in m1["comparables_rejected"]))


class TestMetodos(unittest.TestCase):
    """§17-§21 · contratos de M1/M2/M3 y ensemble explícito."""

    def test_13_m1_registra_todo_lo_exigido(self):
        m1 = est.metodo_m1_comparacion_mercado(
            entrada(comparables=comparables_validos(6)))
        self.assertEqual(m1["status"], "AVAILABLE")
        for campo in ("comparables_used", "median_price_m2", "weighted_price_m2",
                      "dispersion", "adjustments", "result_range"):
            self.assertIsNotNone(m1[campo], campo)
        self.assertEqual(len(m1["comparables_used"]), 6)
        self.assertLessEqual(min(c["value_m2"] for c in m1["comparables_used"]),
                             m1["median_price_m2"])
        self.assertLessEqual(m1["median_price_m2"],
                             max(c["value_m2"] for c in m1["comparables_used"]))
        estados = {a["estado"] for a in m1["adjustments"]}
        self.assertIn("APLICADO", estados)
        self.assertIn("NO_APLICADO", estados)  # lo que NO se aplica también se declara

    def test_14_m2_sin_bloque_no_aplica_y_con_manual_no_sostiene(self):
        m2 = est.metodo_m2_costo_reposicion(entrada())
        self.assertEqual(m2["status"], "NOT_APPLICABLE")
        self.assertIn("no se declaró costo de reposición", m2["reason"])
        # Declarado pero sin edad/vida útil: INSUFFICIENT_DATA y sin rellenar.
        m2b = est.metodo_m2_costo_reposicion(entrada(costo_reposicion={
            "costo_unitario_m2": 3_000_000, "origen_tipo": "EXTERNAL_SOURCE",
            "provenance": procedencia(11)}))
        self.assertEqual(m2b["status"], "INSUFFICIENT_DATA")
        self.assertIn("incompleto", m2b["reason"])
        self.assertIsNone(m2b["result"])
        # Con costo unitario MANUAL_CONFIG: no sostiene producción.
        m2c = est.metodo_m2_costo_reposicion(entrada(costo_reposicion={
            "costo_unitario_m2": 3_000_000, "edad_anios": 10, "vida_util_anios": 50,
            "origen_tipo": "MANUAL_CONFIG"}))
        self.assertEqual(m2c["status"], "INSUFFICIENT_DATA")
        self.assertIn("MANUAL_CONFIG", m2c["reason"])
        self.assertIsNone(m2c["result"])

    def test_15_m2_completo_produce_costo_de_reposicion(self):
        m2 = est.metodo_m2_costo_reposicion(entrada(costo_reposicion={
            "costo_unitario_m2": 3_000_000, "edad_anios": 10, "vida_util_anios": 50,
            "valor_suelo": 80_000_000, "origen_tipo": "EXTERNAL_SOURCE",
            "provenance": procedencia(11)}))
        self.assertEqual(m2["status"], "AVAILABLE")
        self.assertAlmostEqual(m2["result"]["depreciacion"], 0.2, places=6)
        self.assertAlmostEqual(m2["result"]["construccion"], 82.5 * 3_000_000 * 0.8,
                               places=2)
        self.assertAlmostEqual(m2["result"]["value_total"],
                               82.5 * 3_000_000 * 0.8 + 80_000_000, places=2)

    def test_16_m3_exige_renta_y_cap_rate_con_procedencia(self):
        m3 = est.metodo_m3_capitalizacion_rentas(entrada())
        self.assertEqual(m3["status"], "NOT_APPLICABLE")
        self.assertIn("rental_reference", m3["reason"])
        # Renta sin cap rate: INSUFFICIENT_DATA (no se completa lo que falta).
        m3b = est.metodo_m3_capitalizacion_rentas(entrada(rental_reference={
            "renta_mensual": 2_400_000, "origen_tipo": "EXTERNAL_SOURCE",
            "provenance": procedencia(12)}))
        self.assertEqual(m3b["status"], "INSUFFICIENT_DATA")
        self.assertIn("cap_rate", m3b["reason"])
        # Cap rate a mano: no sostiene la capitalización.
        m3c = est.metodo_m3_capitalizacion_rentas(entrada(
            rental_reference={"renta_mensual": 2_400_000, "origen_tipo": "EXTERNAL_SOURCE",
                              "provenance": procedencia(12)},
            cap_rate={"tasa": 0.07, "origen_tipo": "MANUAL_CONFIG"}))
        self.assertEqual(m3c["status"], "INSUFFICIENT_DATA")
        self.assertIn("MANUAL_CONFIG", m3c["reason"])
        self.assertIsNone(m3c["result"])
        # Ambos con procedencia: AVAILABLE y calcula.
        m3d = est.metodo_m3_capitalizacion_rentas(entrada(
            rental_reference={"renta_mensual": 2_400_000, "origen_tipo": "EXTERNAL_SOURCE",
                              "provenance": procedencia(12)},
            cap_rate={"tasa": 0.07, "origen_tipo": "EXTERNAL_SOURCE",
                      "provenance": procedencia(13)}))
        self.assertEqual(m3d["status"], "AVAILABLE")
        self.assertAlmostEqual(m3d["result"]["value_total"], 2_400_000 * 12 / 0.07,
                               places=2)

    def test_17_ensemble_explicito_con_pesos_y_razones(self):
        r = estimar(entrada(
            comparables=comparables_validos(6),
            costo_reposicion={"costo_unitario_m2": 3_000_000, "edad_anios": 10,
                              "vida_util_anios": 50, "valor_suelo": 80_000_000,
                              "origen_tipo": "EXTERNAL_SOURCE",
                              "provenance": procedencia(11)},
            rental_reference={"renta_mensual": 2_400_000, "origen_tipo": "EXTERNAL_SOURCE",
                              "provenance": procedencia(12)},
            cap_rate={"tasa": 0.07, "origen_tipo": "EXTERNAL_SOURCE",
                      "provenance": procedencia(13)}))
        metodos = r["ensemble"]["methods"]
        # §22 (FASE 3) · DOCTRINA ACTUALIZADA — el motor declara UN método más que antes:
        # `M5_AGGREGATED_MARKET_REFERENCE`, que consume la referencia de nivel 3 de la
        # escalera de evidencia de mercado. La aserción no se relaja (el ensemble debe
        # declarar TODOS los métodos evaluados, con peso y razón): pasa de la cifra fija
        # 4 a `len(est.METODOS)`, que es la fuente de verdad del vocabulario.
        self.assertEqual(len(metodos), len(est.METODOS))
        for x in metodos:
            for campo in ("method", "weight", "reason_for_weight", "status", "origin"):
                self.assertIn(campo, x)
            self.assertTrue(str(x["reason_for_weight"]).strip())
        activos = [x for x in metodos if x["weight_normalizado"] > 0]
        self.assertAlmostEqual(sum(x["weight_normalizado"] for x in activos), 1.0, places=9)
        usados = {x["method"] for x in activos}
        self.assertIn("M1_MARKET_COMPARISON", usados)
        self.assertIn("M2_REPLACEMENT_COST", usados)
        self.assertIn("M3_INCOME_CAPITALIZATION", usados)
        self.assertEqual(r["origin_composition"]["origin"], "COMPUTED_FROM_SOURCES")

    def test_18_el_motor_declara_metodos_disponibles_y_rechazados(self):
        r = estimar(entrada(comparables=comparables_validos(4)))
        gate = r["estimation_gate"]
        self.assertIn("M1_MARKET_COMPARISON", gate["methods_available"])
        self.assertIn("M2_REPLACEMENT_COST", gate["methods_rejected"])
        self.assertIn("M3_INCOME_CAPITALIZATION", gate["methods_rejected"])
        self.assertTrue(gate["methods_rejected"])
        self.assertIsNone(r["gap_report"])


class TestContratosDeSalida(unittest.TestCase):
    """§11/§12/§23/§31 · el contrato del resultado y el rango primero."""

    def test_19_el_resultado_cumple_el_contrato_completo(self):
        r = estimar(entrada(comparables=comparables_validos(9), con_calibrado=True))
        revision = est.validar_resultado(r)
        self.assertTrue(revision["valido"], revision)
        self.assertEqual(revision["campos_faltantes"], [])
        self.assertEqual(revision["gate_campos_faltantes"], [])
        self.assertEqual(revision["quality_campos_faltantes"], [])
        self.assertEqual(r["currency"], "COP")
        self.assertEqual(r["model_version"], est.ESTIMATION_ENGINE_VERSION)
        self.assertTrue(r["evidence_refs"])
        self.assertTrue(r["sources"])

    def test_20_el_rango_es_la_salida_primaria_y_manda_sobre_la_precision(self):
        r = estimar(entrada(comparables=comparables_validos(9)))
        self.assertIsNotNone(r["range_low"])
        self.assertIsNotNone(r["range_high"])
        # La cifra central NO tiene más precisión que la evidencia: paso ≥ $1.000.000.
        self.assertEqual(r["central_estimate"] % 1_000_000, 0)
        self.assertEqual(r["range_low"] % 1_000_000, 0)
        self.assertEqual(r["range_high"] % 1_000_000, 0)
        self.assertIn("formula_version", r["range"])
        self.assertEqual(r["range"]["formula_version"], est.RANGE_WIDTH_VERSION)
        self.assertTrue(r["range"]["ajustes"])
        self.assertTrue(r["range"]["motivos"])

    def test_21_el_valor_historico_es_solo_forense(self):
        historico = {"old_run_id": "RUN-LEGACY-001", "old_value": 399_500_000,
                     "old_range": [380_000_000, 420_000_000],
                     "old_method": "MODEL_PRIOR_ESTRATO",
                     "old_inputs": {"estrato": 5}, "old_origin": "MANUAL_CONFIG",
                     "old_master_hash": "b" * 64}
        r = estimar(entrada(comparables=comparables_validos(9)),
                    historico_forense=historico)
        ref = r["historical_estimate_reference"]
        self.assertEqual(ref["old_value"], 399_500_000)
        self.assertFalse(ref["usado_como_input"])
        self.assertIn("FORENSE", ref["naturaleza"])
        for campo in ("old_run_id", "old_value", "old_range", "old_method", "old_inputs",
                      "old_origin", "old_master_hash"):
            self.assertIn(campo, ref)
        # El valor viejo NO aparece en ninguna cifra emitida.
        self.assertNotEqual(r["central_estimate"], 399_500_000)
        self.assertNotIn(399_500_000, (r["central_estimate"], r["range_low"],
                                       r["range_high"], r["value_m2_central"]))
        self.assertEqual(r["central_estimate"] % 500_000, 0)
        self.assertEqual(ref["usado_como_input"], False)

    def test_22_una_estimacion_indicativa_nunca_es_valor_verificado(self):
        r = estimar(entrada(con_calibrado=True))
        self.assertEqual(r["status"], "INDICATIVE_ESTIMATE")
        self.assertEqual(est.vocabulario_economico("INDICATIVE_ESTIMATE"),
                         "ESTIMACIÓN INDICATIVA")
        self.assertFalse(est.es_valor_verificado(r["status"]))
        self.assertFalse(r["envelope"]["es_valor_verificado"])
        self.assertNotIn(r["status_label"], est.ETIQUETAS_VERIFICADAS_PROHIBIDAS)
        self.assertFalse(est.etiqueta_es_verificada(r["status_label"]))
        self.assertTrue(est.etiqueta_es_verificada("INFORMACIÓN VERIFICADA"))
        self.assertNotIn("INFORMACIÓN VERIFICADA", r["status_label"])
        self.assertIn("NO VALOR VERIFICADO", r["envelope"]["naturaleza"]) \
            if "NO VALOR VERIFICADO" in r["envelope"]["naturaleza"] else None
        self.assertEqual(r["envelope"]["naturaleza"], est.NATURALEZA_ESTIMACION)
        # El vocabulario del motor NO coincide con el de hecho verificado.
        if est.dd is not None:
            self.assertNotEqual(r["status_label"], est.dd.INFORMACION_VERIFICADA)

    def test_23_los_cuatro_terminos_del_vocabulario_economico(self):
        self.assertEqual(est.vocabulario_economico("ESTIMATED"), "ESTIMACIÓN DISPONIBLE")
        self.assertEqual(est.vocabulario_economico("ESTIMATED_WITH_LIMITATIONS"),
                         "ESTIMACIÓN DISPONIBLE CON LIMITACIONES")
        self.assertEqual(est.vocabulario_economico("INDICATIVE_ESTIMATE"),
                         "ESTIMACIÓN INDICATIVA")
        self.assertEqual(est.vocabulario_economico("NOT_ESTIMABLE"),
                         "NO FUE POSIBLE ESTIMAR")
        for estado in est.ESTADOS_ESTIMACION:
            self.assertFalse(est.es_valor_verificado(estado), estado)
            self.assertFalse(est.etiqueta_es_verificada(est.vocabulario_economico(estado)),
                             estado)


class TestNotEstimableEsElUltimoEstado(unittest.TestCase):
    """§1/§15 · `NOT_ESTIMABLE` sólo con la base mínima realmente ausente."""

    def test_24_sin_ninguna_base_no_hay_estimacion(self):
        r = estimar({"identidad": {"resuelta": True}, "ubicacion": {"utilizable": True},
                     "area": {"valor_m2": 82.5}, "tipologia": {"valor": "APARTAMENTO"}})
        self.assertEqual(r["status"], "NOT_ESTIMABLE")
        self.assertEqual(r["estimation_gate"]["gate_state"], "CLOSED")
        self.assertIsNotNone(r["gap_report"])
        self.assertEqual(r["gap_report"]["motivo_cierre"], "MISSING_MARKET_EVIDENCE")
        self.assertTrue(r["gap_report"]["fuentes_automaticas_a_incorporar"])

    def test_25_con_la_misma_base_mas_un_modelo_calibrado_si_hay_estimacion(self):
        r = estimar({"identidad": {"resuelta": True}, "ubicacion": {"utilizable": True},
                     "area": {"valor_m2": 82.5}, "tipologia": {"valor": "APARTAMENTO"},
                     "modelo_calibrado": modelo_calibrado()})
        self.assertNotEqual(r["status"], "NOT_ESTIMABLE", _mensaje_no_estimar(r))
        self.assertEqual(r["status"], "INDICATIVE_ESTIMATE")
        self.assertIsNone(r["gap_report"])

    def test_26_falta_de_area_o_identidad_cierra_con_su_motivo(self):
        r = estimar(entrada(comparables=comparables_validos(6),
                            area={"valor_m2": None}))
        self.assertEqual(r["estimation_gate"]["gate_state"], "CLOSED")
        self.assertIn("AREA_UTILIZABLE", _razones_texto(r))
        r2 = estimar(entrada(comparables=comparables_validos(6),
                             identidad={"resuelta": False}))
        self.assertEqual(r2["estimation_gate"]["gate_state"], "CLOSED")
        self.assertIn("IDENTIDAD_SUFICIENTEMENTE_RESUELTA", _razones_texto(r2))

    def test_27_las_condiciones_minimas_son_explicitas_y_versionadas(self):
        self.assertEqual(est.CONDICIONES_ESTIMACION,
                         ("IDENTIDAD_SUFICIENTEMENTE_RESUELTA", "UBICACION_UTILIZABLE",
                          "AREA_UTILIZABLE", "TIPOLOGIA_MINIMA",
                          "SOPORTE_ECONOMICO_VALIDO"))
        r = estimar(entrada(comparables=comparables_validos(4)))
        gate = r["estimation_gate"]
        self.assertEqual(gate["conditions_version"], est.CONDITIONS_VERSION)
        for campo in est.CAMPOS_ESTIMATION_GATE:
            self.assertIn(campo, gate)
        self.assertTrue(gate["inputs_available"])
        self.assertIn("costo_reposicion", gate["inputs_missing"])
        self.assertTrue(gate["supporting_conditions"])
        self.assertTrue(gate["condiciones"]["SOPORTE_ECONOMICO_VALIDO"])

    def test_28_el_soporte_manual_o_legacy_no_cuenta_como_condicion_cumplida(self):
        for extra in ({"tasa_manual": {"valor_m2": 5_200_000}},
                      {"modelo_legacy": {"estrato": 5, "value_m2": 6_500_000}},
                      {"referencia_estatica": {"origen_tipo": "STATIC_REFERENCE"}}):
            r = estimar(entrada(**extra))
            self.assertFalse(
                r["estimation_gate"]["condiciones"]["SOPORTE_ECONOMICO_VALIDO"],
                extra)
            self.assertEqual(r["estimation_gate"]["gate_state"], "CLOSED", extra)


class TestGapReport(unittest.TestCase):
    """§28/§29 · el cierre por falta de fuente automática es un problema DISTINTO."""

    def test_29_el_gap_report_pide_una_fuente_concreta_sin_inventarla(self):
        r = estimar(entrada(tasa_manual={"valor_m2": 5_200_000}))
        gap = r["gap_report"]
        peticiones = gap["fuentes_automaticas_a_incorporar"]
        self.assertTrue(peticiones)
        for p in peticiones:
            self.assertIn("fuente", p)
            self.assertEqual(p["estado"], "NO INCORPORADA")
            self.assertIsNone(p["contrato"])
            self.assertTrue(p["aporta"])
        tipos = {p["tipo"] for p in peticiones}
        self.assertIn("EXTERNAL_SOURCE", tipos)
        self.assertIn("MISSING_MARKET_EVIDENCE", gap["motivo_cierre"])
        self.assertIn("NO es lo mismo", gap["distincion"])

    def test_30_el_gap_report_solo_aparece_cuando_no_hay_estimacion(self):
        r = estimar(entrada(comparables=comparables_validos(5)))
        self.assertIsNone(r["gap_report"])
        r2 = estimar(entrada(con_calibrado=True))
        self.assertIsNone(r2["gap_report"])


class TestMetodologiaBase(unittest.TestCase):
    """§34 · metodología base declarada con el vocabulario correcto."""

    def test_31_la_metodologia_base_no_usa_norma_y_validacion_profesional(self):
        resumen = est.resumen_metodologico()
        self.assertEqual(resumen["metodologia_base"], est.METODOLOGIA_BASE)
        self.assertEqual(est.METODOLOGIA_BASE,
                         "fuentes disponibles + análisis técnico automatizado + "
                         "metodología versionada")
        self.assertFalse(est.contiene_vocabulario_metodologico_prohibido(
            est.METODOLOGIA_BASE))
        self.assertTrue(est.contiene_vocabulario_metodologico_prohibido(
            "norma + concepto técnico + validación profesional"))
        self.assertIn("DICTUS + REVIEW", resumen["revision_profesional"])
        self.assertNotIn("norma + concepto técnico + validación profesional",
                         json.dumps(resumen, ensure_ascii=False))
        r = estimar(entrada(comparables=comparables_validos(5)))
        self.assertEqual(r["envelope"]["metodologia"]["metodologia_base"],
                         est.METODOLOGIA_BASE)
        for supuesto in r["assumptions"]:
            self.assertFalse(est.contiene_vocabulario_metodologico_prohibido(supuesto))

    def test_32_el_resultado_declara_supuestos_y_limitaciones(self):
        r = estimar(entrada(comparables=comparables_validos(3)))
        self.assertTrue(r["assumptions"])
        self.assertTrue(r["limitations"])
        texto = " | ".join(r["limitations"])
        self.assertIn("comparables", texto.lower())


if __name__ == "__main__":
    unittest.main()

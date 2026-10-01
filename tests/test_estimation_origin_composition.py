# -*- coding: utf-8 -*-
"""DICTUS ESTIMATION ENGINE v1.0 · §2/§3 · COMPOSICIÓN DE `origin`.

Reglas duras probadas aquí:

  · `EXTERNAL_SOURCE + EXTERNAL_SOURCE`        → `COMPUTED_FROM_SOURCES`
  · `EXTERNAL_SOURCE + CALIBRATED_MODEL_PRIOR` → `COMPUTED_WITH_MODEL_PRIOR`
  · `EXTERNAL_SOURCE + STATIC_REFERENCE`       → `COMPUTED_WITH_STATIC_REFERENCE`
  · `EXTERNAL_SOURCE + MANUAL_CONFIG`          → `NOT_PRODUCTIVE` (jamás
    `COMPUTED_FROM_SOURCES`: un valor escrito a mano no se lava)
  · `MANUAL_CONFIG` / `LEGACY_MODEL_PRIOR`     → no sostienen estimación productiva
  · `STATIC_REFERENCE`                         → contexto de bajo peso, no sostiene sola
  · `CALIBRATED_MODEL_PRIOR`                   → contrato auditable; sólo él contribuye
    a INDICATIVE. `LEGACY_MODEL_PRIOR` (el hardcode por estrato) no abre nada.
"""
from __future__ import annotations

import json
import unittest

from _fixtures_estimation import (ROOT, comparable, comparables_validos, entrada,
                                  estimar, modelo_calibrado, procedencia)

import estimation as est  # noqa: E402

EXT_1 = {"origen_tipo": "EXTERNAL_SOURCE", "provenance": procedencia(1)}
EXT_2 = {"origen_tipo": "EXTERNAL_SOURCE", "provenance": procedencia(2)}
MANUAL = {"origen_tipo": "MANUAL_CONFIG", "value_m2": 5_200_000,
          "fuente": "artefacto local de metodología"}
ESTATICA = {"origen_tipo": "STATIC_REFERENCE", "value_m2": 5_000_000,
            "referencia": "tabla estática de referencia"}
CALIBRADO = {**modelo_calibrado(), "origen_tipo": "CALIBRATED_MODEL_PRIOR"}
LEGACY = {"origen_tipo": "LEGACY_MODEL_PRIOR", "estrato": 5, "value_m2": 6_500_000}
LEGACY_ESPELUZNANTE = {3: 3_800_000, 4: 5_200_000, 5: 6_500_000, 6: 7_800_000}


class TestTablaDeComposicion(unittest.TestCase):
    """Las cuatro reglas EXIGIDAS, una por prueba (§3)."""

    def test_01_dos_fuentes_externas_dan_computed_from_sources(self):
        c = est.componer_origen([EXT_1, EXT_2])
        self.assertEqual(c["origin"], "COMPUTED_FROM_SOURCES")
        self.assertEqual(c["regla"], "R5_FUENTES_MULTIPLES")
        self.assertTrue(c["sostiene_estimacion"])
        self.assertTrue(c["abre_verified_gate"])
        self.assertEqual(c["techo_calidad"], "HIGH")

    def test_02_externa_mas_prior_calibrado_da_computed_with_model_prior(self):
        c = est.componer_origen([EXT_1, CALIBRADO])
        self.assertEqual(c["origin"], "COMPUTED_WITH_MODEL_PRIOR")
        self.assertEqual(c["regla"], "R2_EXTERNA_MAS_PRIOR_CALIBRADO")
        # El techo baja a INDICATIVE: hay un modelo dentro del cálculo. Aunque haya
        # varias fuentes externas, la etiqueta NO puede declarar más de lo que entró.
        self.assertEqual(c["techo_calidad"], "INDICATIVE")
        self.assertFalse(c["abre_verified_gate"])
        self.assertTrue(c["sostiene_estimacion"])
        self.assertEqual(est.componer_origen([EXT_1, EXT_2, CALIBRADO])["origin"],
                         "COMPUTED_WITH_MODEL_PRIOR")

    def test_03_externa_mas_referencia_estatica_da_computed_with_static_reference(self):
        c = est.componer_origen([EXT_1, ESTATICA])
        self.assertEqual(c["origin"], "COMPUTED_WITH_STATIC_REFERENCE")
        self.assertEqual(c["regla"], "R4_EXTERNA_MAS_ESTATICA")
        self.assertEqual(c["techo_calidad"], "MEDIUM")
        self.assertEqual(est.componer_origen([EXT_1, EXT_2, ESTATICA])["origin"],
                         "COMPUTED_WITH_STATIC_REFERENCE")

    def test_04_externa_mas_manual_config_da_not_productive(self):
        c = est.componer_origen([EXT_1, EXT_2, MANUAL])
        self.assertEqual(c["origin"], "NOT_PRODUCTIVE")
        self.assertEqual(c["regla"], "R1_NO_LAVADO")
        self.assertNotEqual(c["origin"], "COMPUTED_FROM_SOURCES")
        self.assertFalse(c["sostiene_estimacion"])
        self.assertFalse(c["abre_verified_gate"])
        self.assertFalse(c["no_lavado"])
        self.assertIn("MANUAL_CONFIG", c["motivos"][0])


class TestNadaSeSostieneSolo(unittest.TestCase):
    """§2/§3 · quién puede sostener una cifra y quién no."""

    def test_05_manual_config_solo_no_sostiene(self):
        c = est.componer_origen([MANUAL])
        self.assertEqual(c["origin"], "NOT_PRODUCTIVE")
        self.assertFalse(c["sostiene_estimacion"])
        self.assertEqual(c["techo_calidad"], "INSUFFICIENT")

    def test_06_legacy_model_prior_solo_no_sostiene_ni_abre_nada(self):
        c = est.componer_origen([LEGACY])
        self.assertEqual(c["origin"], "NOT_PRODUCTIVE")
        self.assertFalse(c["sostiene_estimacion"])
        self.assertFalse(c["abre_verified_gate"])

    def test_07_static_reference_sola_no_sostiene_estimacion_productiva(self):
        c = est.componer_origen([ESTATICA])
        self.assertEqual(c["origin"], "STATIC_REFERENCE")
        self.assertFalse(c["sostiene_estimacion"])
        self.assertEqual(c["techo_calidad"], "MEDIUM")

    def test_08_estadistica_externa_sin_procedencia_no_es_fuente(self):
        c = est.componer_origen([{"origen_tipo": "EXTERNAL_SOURCE",
                                  "value_m2": 5_000_000}])
        self.assertNotEqual(c["origin"], "COMPUTED_FROM_SOURCES")
        self.assertEqual(c["origin"], "NOT_PRODUCTIVE")
        self.assertFalse(c["sostiene_estimacion"])

    def test_09_sin_insumos_la_composicion_no_es_productiva(self):
        c = est.componer_origen([])
        self.assertEqual(c["origin"], "NOT_PRODUCTIVE")
        self.assertEqual(c["regla"], "R0_SIN_INSUMOS")
        self.assertFalse(c["sostiene_estimacion"])


class TestPriorCalibradoVsLegacy(unittest.TestCase):
    """§9/§16 · el contrato calibrado es DISTINTO del legacy y no se confunde."""

    def test_10_model_prior_y_legacy_model_prior_son_la_misma_clase(self):
        for declarado in ("MODEL_PRIOR", "LEGACY_MODEL_PRIOR"):
            c = est.clasificar_origen_extendido({"origen_tipo": declarado})
            self.assertEqual(c["clase"], "LEGACY_MODEL_PRIOR", declarado)
            self.assertFalse(c["sostiene_estimacion"])
            self.assertFalse(c["abre_verified_gate"])

    def test_11_calibrado_valido_sostiene_con_techo_indicative(self):
        c = est.clasificar_origen_extendido(CALIBRADO)
        self.assertEqual(c["clase"], "CALIBRATED_MODEL_PRIOR")
        self.assertTrue(c["sostiene_estimacion"])
        self.assertFalse(c["abre_verified_gate"])
        self.assertEqual(c["techo_calidad"], "INDICATIVE")
        c2 = est.componer_origen([CALIBRADO])
        self.assertEqual(c2["origin"], "CALIBRATED_MODEL_PRIOR")
        self.assertTrue(c2["sostiene_estimacion"])

    def test_12_calibrado_incompleto_se_degrada_a_legacy(self):
        for falta in ("sample_size", "calibration_error", "model_version", "hash",
                      "reference_period", "effective_from"):
            incompleto = {k: v for k, v in modelo_calibrado().items() if k != falta}
            revision = est.validar_modelo_calibrado(incompleto)
            self.assertFalse(revision["valido"], falta)
            self.assertIn(falta, revision["faltantes"])
            c = est.clasificar_origen_extendido(
                {**incompleto, "origen_tipo": "CALIBRATED_MODEL_PRIOR"})
            self.assertEqual(c["clase"], "LEGACY_MODEL_PRIOR", falta)
            self.assertFalse(c["sostiene_estimacion"], falta)
        # Y la composición con ese insumo no puede ser productiva.
        incompleto = {k: v for k, v in modelo_calibrado().items() if k != "sample_size"}
        c = est.componer_origen([EXT_1, EXT_2,
                                 {**incompleto, "origen_tipo": "CALIBRATED_MODEL_PRIOR"}])
        self.assertEqual(c["origin"], "NOT_PRODUCTIVE")

    def test_13_muestra_o_error_fuera_de_rango_invalidan_el_contrato(self):
        self.assertFalse(est.validar_modelo_calibrado(
            modelo_calibrado(sample_size=5))["valido"])
        self.assertFalse(est.validar_modelo_calibrado(
            modelo_calibrado(calibration_error=0.9))["valido"])
        self.assertFalse(est.validar_modelo_calibrado(
            modelo_calibrado(low_value_m2=9_000_000, central_value_m2=5_000_000))["valido"])
        self.assertTrue(est.validar_modelo_calibrado(modelo_calibrado())["valido"])

    def test_14_el_contrato_declara_todos_los_campos_exigidos(self):
        for campo in ("city", "sector", "neighborhood", "property_type", "regime",
                      "area_band", "estrato", "central_value_m2", "low_value_m2",
                      "high_value_m2", "effective_from", "effective_to",
                      "reference_period", "sample_size", "calibration_error",
                      "model_version", "provenance", "hash"):
            self.assertIn(campo, est.CONTRATO_MODELO_CALIBRADO)

    def test_15_la_tabla_legacy_por_estrato_sigue_siendo_legacy(self):
        """El hardcode `{3:3.8M, 4:5.2M, 5:6.5M, 6:7.8M}` se conserva por
        compatibilidad: DICTUS lo declara LEGACY y NO lo usa para estimar."""
        for estrato, valor in LEGACY_ESPELUZNANTE.items():
            c = est.clasificar_origen_extendido(
                {"origen_tipo": "MODEL_PRIOR", "estrato": estrato, "value_m2": valor})
            self.assertEqual(c["clase"], "LEGACY_MODEL_PRIOR", estrato)
            self.assertFalse(c["sostiene_estimacion"], estrato)
        # Aunque la corrida declare el legacy, la estimación no cambia de estado.
        r = estimar(entrada(con_calibrado=True,
                            modelo_legacy={"estrato": 5, "value_m2": 6_500_000,
                                           "tabla": LEGACY_ESPELUZNANTE}))
        self.assertNotIn("LEGACY_MODEL_PRIOR",
                         r["origin_composition"]["clases_usadas"])
        self.assertIn("LEGACY_MODEL_PRIOR", r["origin_composition"]["clases_excluidas"])


class TestNoLavadoDeManualConfig(unittest.TestCase):
    """§11 · el MANUAL_CONFIG mezclado con fuentes NO se lava."""

    def test_16_mezcla_con_fuentes_no_se_etiqueta_como_computed_from_sources(self):
        mezclas = ([EXT_1, EXT_2, MANUAL],
                   [EXT_1, MANUAL],
                   [EXT_1, EXT_2, MANUAL, ESTATICA],
                   [EXT_1, EXT_2, MANUAL, LEGACY],
                   [EXT_1, EXT_2, MANUAL, CALIBRADO])
        for mezcla in mezclas:
            c = est.componer_origen(mezcla)
            self.assertEqual(c["origin"], "NOT_PRODUCTIVE", c["clases_usadas"])
            self.assertNotEqual(c["origin"], "COMPUTED_FROM_SOURCES")
            self.assertFalse(c["no_lavado"])
            self.assertEqual(c["regla"], "R1_NO_LAVADO")

    def test_17_el_motor_declara_la_exclusion_sin_contarla_como_fuente(self):
        r = estimar(entrada(comparables=comparables_validos(6),
                            tasa_manual={"valor_m2": 5_200_000}))
        comp = r["origin_composition"]
        self.assertEqual(comp["origin"], "COMPUTED_FROM_SOURCES")
        self.assertNotIn("MANUAL_CONFIG", comp["clases_usadas"])
        self.assertIn("MANUAL_CONFIG", comp["clases_excluidas"])
        self.assertTrue(comp["no_lavado"])
        self.assertTrue(any("MANUAL_CONFIG" in str(x.get("clase"))
                            for x in comp["excluidos"]))
        # La tasa manual no sostiene nada: el resultado se apoya en los comparables.
        self.assertEqual(r["inputs"]["comparables_usados"], 6)
        self.assertNotIn("MANUAL_CONFIG", r["origins"]["clases_usadas"])

    def test_18_una_tasa_manual_sola_nunca_produce_cifra(self):
        r = estimar(entrada(tasa_manual={"valor_m2": 5_200_000}))
        self.assertEqual(r["status"], "NOT_ESTIMABLE")
        self.assertIsNone(r["central_estimate"])
        self.assertEqual(r["origin_composition"]["origin"], "NOT_PRODUCTIVE")


class TestLonjaNuncaFuente(unittest.TestCase):
    """§14 · ninguna fuente del motor es la entidad no acreditada."""

    def test_19_ninguna_salida_nombra_una_fuente_no_acreditada(self):
        import atribucion_mercado as am
        r = estimar(entrada(comparables=comparables_validos(5), con_calibrado=True))
        texto = json.dumps(r, ensure_ascii=False, default=str)
        self.assertNotIn("lonja", texto.lower())
        for fuente in r["sources"]:
            self.assertFalse(am.contiene_atribucion_no_acreditada(fuente.get("proveedor")),
                             fuente)
            self.assertFalse(fuente["es_fuente_no_acreditada"])
        for ref in r["evidence_refs"]:
            self.assertFalse(am.contiene_atribucion_no_acreditada(ref.get("source")), ref)

    def test_20_el_gap_report_no_inventa_fuente_sustituta(self):
        r = estimar(entrada(tasa_manual={"valor_m2": 5_200_000}))
        gap = r["gap_report"]
        self.assertNotIn("lonja", json.dumps(gap, ensure_ascii=False).lower())
        for peticion in gap["fuentes_automaticas_a_incorporar"]:
            self.assertEqual(peticion["estado"], "NO INCORPORADA")
            self.assertIsNone(peticion["contrato"])

    def test_21_la_metodologia_base_no_atribuye_la_tasa_a_ninguna_entidad(self):
        import atribucion_mercado as am
        self.assertFalse(am.contiene_atribucion_no_acreditada(est.METODOLOGIA_BASE))


if __name__ == "__main__":
    unittest.main()

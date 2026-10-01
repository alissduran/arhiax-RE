# -*- coding: utf-8 -*-
"""DICTUS ESTIMATION ENGINE v1.0 · §13/§14/§15 · CALIDAD DE EVIDENCIA E INCERTIDUMBRE.

  · `EVIDENCE_QUALITY_GATE` ∈ {HIGH, MEDIUM, INDICATIVE, INSUFFICIENT}, SIN score 0-100.
  · Diez dimensiones cualitativas, cada una con su nivel y su razón.
  · El ANCHO del rango se DERIVA de la incertidumbre real (fórmula versionada):
    dispersión, nº de comparables, antigüedad, calidad del matching, tipo de evidencia
    y error del modelo. Menor calidad ⇒ rango más ancho.
  · Prohibido HIGH con ±20% o INDICATIVE con ±5% SIN razón explícita: la banda de la
    calidad manda y, si el ancho no cabe, se DEGRADA la calidad (no se estrecha el rango).
"""
from __future__ import annotations

import json
import unittest

from _fixtures_estimation import (comparable, comparables_validos, entrada, estimar,
                                  modelo_calibrado)

import estimation as est  # noqa: E402


def _ancho(**kw) -> dict:
    base = {"dispersion_cv": 0.05, "comparables_usados": 9, "antiguedad_meses": 2,
            "matching_quality": 1.0, "origen": "COMPUTED_FROM_SOURCES",
            "error_modelo": None, "evidence_quality": "MEDIUM"}
    base.update(kw)
    return est.ancho_de_rango(**base)


class TestDimensionesYAusenciaDeScore(unittest.TestCase):
    """§13/§14 · nivel + razones + diez dimensiones, sin score público."""

    def test_01_la_calidad_declara_sus_diez_dimensiones_con_nivel_cerrado(self):
        r = estimar(entrada(comparables=comparables_validos(9), con_calibrado=True))
        q = r["evidence_quality"]
        for campo in est.CAMPOS_DIMENSION_CALIDAD:
            self.assertIn(campo, q, campo)
        for campo in est.CAMPOS_DIMENSION_CALIDAD:
            if campo in ("comparable_count", "dispersion", "market_freshness"):
                continue
            self.assertIn(q[campo], est.ESTADOS_DIMENSION, campo)
        self.assertIn(q["market_freshness"]["level"], est.ESTADOS_DIMENSION)
        self.assertIn(q["dispersion"]["level"], est.ESTADOS_DIMENSION)
        self.assertIsInstance(q["comparable_count"], int)
        self.assertEqual(q["gate"], "EVIDENCE_QUALITY_GATE")
        self.assertIn(q["level"], est.ESTADOS_EVIDENCE_QUALITY)
        self.assertTrue(q["reasons"])
        for campo in est.CAMPOS_DIMENSION_CALIDAD:
            self.assertIn(campo, est.CAMPOS_EVIDENCE_QUALITY, campo)

    def test_02_no_hay_ningun_score_publico(self):
        r = estimar(entrada(comparables=comparables_validos(9)))
        self.assertTrue(r["evidence_quality"]["sin_score_publico"])
        self.assertIn("NO se publica ningún score", r["evidence_quality"]["nota"])

        def _claves(obj, ruta=""):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    yield f"{ruta}.{k}"
                    yield from _claves(v, f"{ruta}.{k}")
            elif isinstance(obj, (list, tuple)):
                for i, v in enumerate(obj):
                    yield from _claves(v, f"{ruta}[{i}]")

        for clave in _claves(r):
            bajo = clave.lower()
            if bajo.endswith("sin_score_publico"):
                continue  # la propia DECLARACIÓN de que no hay score
            for prohibido in ("score", "puntaje", "rating", "porcentaje_confianza",
                              "confianza_numerica", "indice_confianza"):
                self.assertNotIn(prohibido, bajo,
                                 f"no puede existir un campo tipo score: {clave}")
        # Las dimensiones de calidad son CUALITATIVAS, nunca un número 0-100.
        q = r["evidence_quality"]
        for campo in est.CAMPOS_DIMENSION_CALIDAD:
            if campo in ("comparable_count", "dispersion", "market_freshness"):
                continue
            self.assertIsInstance(q[campo], str, campo)

    def test_03_la_frescura_se_mide_en_meses_declarados(self):
        r = estimar(entrada(comparables=comparables_validos(6)))
        frescura = r["evidence_quality"]["market_freshness"]
        self.assertIn(frescura["level"], est.ESTADOS_DIMENSION)
        self.assertIsInstance(frescura["meses"], int)
        self.assertIn("evidencia de hace", frescura["detalle"])

    def test_04_la_calidad_de_comparables_refleja_los_rechazos(self):
        comps = comparables_validos(6) + [
            comparable(7, 5_000_000, tipologia="CASA"),
            comparable(8, 9_000_000)]
        r = estimar(entrada(comparables=comps))
        q = r["evidence_quality"]
        self.assertEqual(q["comparable_count"], 6)
        self.assertEqual(q["comparable_count_declarados"], 8)
        self.assertIn(q["comparable_quality"], ("MEDIUM", "LOW"))


class TestMenorCalidadRangoMasAncho(unittest.TestCase):
    """§15 · la incertidumbre se traduce SIEMPRE en ancho, de forma reproducible."""

    def test_05_mayor_dispersion_da_rango_mas_ancho(self):
        estrecho = _ancho(dispersion_cv=0.03)
        ancho = _ancho(dispersion_cv=0.20)
        self.assertLess(estrecho["semi_ancho_relativo"], ancho["semi_ancho_relativo"])
        comp_low = [comparable(i, 5_000_000 + i * 15_000) for i in range(1, 10)]
        comp_high = [comparable(i, 5_000_000 + (i - 5) * 320_000) for i in range(1, 10)]
        r_low = estimar(entrada(comparables=comp_low))
        r_high = estimar(entrada(comparables=comp_high))
        rel_low = (r_low["range_high"] - r_low["range_low"]) / r_low["central_estimate"]
        rel_high = (r_high["range_high"] - r_high["range_low"]) / r_high["central_estimate"]
        self.assertLess(rel_low, rel_high,
                        f"dispersión mayor debe dar rango más ancho ({rel_low} vs {rel_high})")
        self.assertLess(est.ORDEN_CALIDAD[r_high["evidence_quality"]["level"]],
                        est.ORDEN_CALIDAD[r_low["evidence_quality"]["level"]] + 1)

    def test_06_menos_comparables_da_rango_mas_ancho(self):
        pocos = _ancho(comparables_usados=2)
        muchos = _ancho(comparables_usados=12)
        self.assertLess(muchos["semi_ancho_relativo"], pocos["semi_ancho_relativo"])

    def test_07_evidencia_mas_antigua_da_rango_mas_ancho(self):
        nueva = _ancho(antiguedad_meses=3)
        vieja = _ancho(antiguedad_meses=30)
        self.assertLess(nueva["semi_ancho_relativo"], vieja["semi_ancho_relativo"])
        self.assertEqual(vieja["componentes"]["antiguedad"],
                         est.ANCHO_MAX_ANTIGUEDAD)  # tope declarado

    def test_08_peor_matching_y_error_del_modelo_ensanchan_el_rango(self):
        bueno = _ancho(matching_quality=1.0, error_modelo=0.0)
        malo = _ancho(matching_quality=0.4, error_modelo=0.15)
        self.assertLess(bueno["semi_ancho_relativo"], malo["semi_ancho_relativo"])
        self.assertGreater(malo["componentes"]["matching"], 0)
        self.assertGreater(malo["componentes"]["error_modelo"], 0)

    def test_09_el_tipo_de_evidencia_entra_en_la_formula(self):
        externa = _ancho(origen="COMPUTED_FROM_SOURCES", evidence_quality="INDICATIVE")
        calibrada = _ancho(origen="CALIBRATED_MODEL_PRIOR", evidence_quality="INDICATIVE")
        manual = _ancho(origen="MANUAL_CONFIG", evidence_quality="INDICATIVE")
        self.assertLess(externa["componentes"]["tipo_evidencia"],
                        calibrada["componentes"]["tipo_evidencia"])
        self.assertLess(calibrada["componentes"]["tipo_evidencia"],
                        manual["componentes"]["tipo_evidencia"])

    def test_10_menor_freshness_baja_la_calidad_de_evidencia(self):
        reciente = estimar(entrada(comparables=comparables_validos(9)))
        antiguo = estimar(entrada(comparables=comparables_validos(9, fecha="2022-06-01")))
        self.assertEqual(reciente["evidence_quality"]["market_freshness"]["level"], "HIGH")
        self.assertEqual(antiguo["evidence_quality"]["market_freshness"]["level"], "ABSENT")
        self.assertGreater(est.ORDEN_CALIDAD[reciente["evidence_quality"]["level"]],
                           est.ORDEN_CALIDAD[antiguo["evidence_quality"]["level"]])
        # Y la evidencia antigua, aunque peor, SIGUE permitiendo estimar (con aviso).
        self.assertNotEqual(antiguo["status"], "NOT_ESTIMABLE")
        self.assertEqual(antiguo["status"], "INDICATIVE_ESTIMATE")
        self.assertGreater(antiguo["range"]["semi_ancho_relativo"],
                           reciente["range"]["semi_ancho_relativo"])

    def test_11_la_formula_es_versionada_y_reproducible(self):
        a = _ancho()
        b = _ancho()
        self.assertEqual(a, b)
        self.assertEqual(a["formula_version"], est.RANGE_WIDTH_VERSION)
        for componente in ("base", "dispersion", "comparables", "antiguedad", "matching",
                           "tipo_evidencia", "error_modelo"):
            self.assertIn(componente, a["componentes"], componente)
        self.assertTrue(a["ajustes"])
        r1 = estimar(entrada(comparables=comparables_validos(9)))
        r2 = estimar(entrada(comparables=comparables_validos(9)))
        self.assertEqual(r1["hash_payload"], r2["hash_payload"])
        self.assertEqual(r1["range"]["semi_ancho_relativo"],
                         r2["range"]["semi_ancho_relativo"])

    def test_12_la_antiguedad_se_topa_y_no_crece_sin_limite(self):
        enorme = _ancho(antiguedad_meses=600)
        self.assertEqual(enorme["componentes"]["antiguedad"], est.ANCHO_MAX_ANTIGUEDAD)
        self.assertLessEqual(enorme["semi_ancho_relativo"], est.MAX_SEMI_ANCHO)


class TestBandasDeCalidad(unittest.TestCase):
    """§15 · prohibido HIGH con ±20% o INDICATIVE con ±5% SIN razón explícita."""

    def test_13_high_con_20_por_ciento_sin_razon_degrada_la_calidad(self):
        # base 0.06 + dispersión (cv 0.10) + nº comparables (5) = ±20% exactos.
        a = _ancho(dispersion_cv=0.10, comparables_usados=5, antiguedad_meses=0,
                   matching_quality=1.0, evidence_quality="HIGH")
        self.assertAlmostEqual(a["componentes"]["semi_ancho_calculado"], 0.20, places=9)
        self.assertEqual(a["calidad_declarada"], "HIGH")
        self.assertNotEqual(a["calidad_efectiva"], "HIGH")
        self.assertEqual(a["calidad_efectiva"], "MEDIUM")
        self.assertTrue(any("DEGRADA" in m for m in a["motivos"]))
        self.assertEqual(a["banda_calidad"], list(est.BANDAS_POR_CALIDAD["MEDIUM"]))

    def test_14_la_misma_high_con_20_por_ciento_y_razon_explicita_se_permite(self):
        a = _ancho(dispersion_cv=0.10, comparables_usados=5, antiguedad_meses=0,
                   matching_quality=1.0, evidence_quality="HIGH",
                   razon_explicita="sector con oferta atípica declarada por la corrida")
        self.assertEqual(a["calidad_efectiva"], "HIGH")
        self.assertAlmostEqual(a["semi_ancho_relativo"], 0.20, places=9)
        self.assertEqual(a["razon_explicita"],
                         "sector con oferta atípica declarada por la corrida")
        self.assertTrue(any("excepción justificada" in m for m in a["motivos"]))

    def test_15_indicative_con_5_por_ciento_sin_razon_se_eleva_al_minimo(self):
        a = _ancho(dispersion_cv=0.0, comparables_usados=12, antiguedad_meses=0,
                   matching_quality=1.0, evidence_quality="INDICATIVE")
        self.assertAlmostEqual(a["componentes"]["semi_ancho_calculado"], 0.06, places=9)
        self.assertEqual(a["calidad_efectiva"], "INDICATIVE")
        self.assertAlmostEqual(a["semi_ancho_relativo"],
                               est.BANDAS_POR_CALIDAD["INDICATIVE"][0], places=9)
        self.assertEqual(a["clamp"], "ELEVADO_AL_MINIMO")
        self.assertTrue(any("ELEVA al mínimo" in m for m in a["motivos"]))
        # Con razón explícita, la excepción se permite y queda documentada.
        b = _ancho(dispersion_cv=0.0, comparables_usados=12, antiguedad_meses=0,
                   matching_quality=1.0, evidence_quality="INDICATIVE",
                   razon_explicita="unidad con características idénticas verificadas")
        self.assertAlmostEqual(b["semi_ancho_relativo"], 0.06, places=9)
        self.assertEqual(b["clamp"], "DENTRO_DE_BANDA")

    def test_16_anchos_que_no_caben_degradan_hasta_indicative(self):
        a = _ancho(dispersion_cv=0.25, comparables_usados=12, antiguedad_meses=0,
                   matching_quality=1.0, evidence_quality="HIGH")
        self.assertEqual(a["calidad_efectiva"], "INDICATIVE")
        self.assertGreater(a["semi_ancho_relativo"], 0.30)
        degradaciones = [m for m in a["motivos"] if "DEGRADA" in m]
        self.assertGreaterEqual(len(degradaciones), 2)  # HIGH→MEDIUM y MEDIUM→INDICATIVE

    def test_17_calidad_insuficiente_no_emite_rango(self):
        a = _ancho(evidence_quality="INSUFFICIENT")
        self.assertIsNone(a["semi_ancho_relativo"])
        self.assertEqual(a["clamp"], "SIN_RANGO")
        self.assertEqual(a["calidad_efectiva"], "INSUFFICIENT")
        r = estimar({"identidad": {"resuelta": True}})
        self.assertIsNone(r["range_low"])
        self.assertIsNone(r["range_high"])

    def test_18_el_motor_declara_la_degradacion_por_ancho(self):
        """La calidad EFECTIVA del resultado viaja coherente con el ancho emitido."""
        comps = [comparable(i, 5_000_000 + (i - 5) * 320_000) for i in range(1, 10)]
        r = estimar(entrada(comparables=comps))
        ancho = r["range"]["semi_ancho_relativo"]
        calidad = r["evidence_quality"]["level"]
        minimo, maximo = est.BANDAS_POR_CALIDAD[calidad]
        self.assertGreaterEqual(ancho, minimo)
        self.assertLessEqual(ancho, maximo)

    def test_19_la_precision_de_la_cifra_se_deriva_del_ancho(self):
        """§12 · a más incertidumbre, menos dígitos significativos."""
        self.assertEqual(est.redondear_segun_evidencia(399_500_000, 0.05), 400_000_000)
        self.assertEqual(est.redondear_segun_evidencia(399_500_000, 0.10), 400_000_000)
        self.assertEqual(est.redondear_segun_evidencia(412_345_678, 0.20), 410_000_000)
        self.assertEqual(est.redondear_segun_evidencia(412_345_678, 0.45), 410_000_000)
        self.assertNotEqual(est.redondear_segun_evidencia(399_500_000, 0.10), 399_500_000)
        for semi in (0.05, 0.12, 0.3, 0.6):
            self.assertEqual(est.redondear_segun_evidencia(399_500_000, semi) % 1_000_000, 0)


class TestNivelesDeCalidad(unittest.TestCase):
    """§13 · la escalera de niveles responde a la evidencia REAL."""

    def test_20_mejor_evidencia_da_mejor_o_igual_nivel(self):
        combinaciones = [
            entrada(comparables=comparables_validos(9)),
            entrada(comparables=comparables_validos(4)),
            entrada(comparables=[comparable(1, 5_000_000)], con_calibrado=True),
            entrada(con_calibrado=True),
            entrada(),
        ]
        niveles = [estimar(e)["evidence_quality"]["level"] for e in combinaciones]
        orden = [est.ORDEN_CALIDAD[n] for n in niveles]
        self.assertEqual(orden, sorted(orden, reverse=True), niveles)
        self.assertEqual(niveles[0], "HIGH")
        self.assertEqual(niveles[-1], "INSUFFICIENT")

    def test_21_un_modelo_calibrado_valido_no_alcanza_high(self):
        r = estimar(entrada(con_calibrado=True))
        self.assertEqual(r["evidence_quality"]["level"], "INDICATIVE")
        self.assertEqual(r["evidence_quality"]["model_quality"], "HIGH")
        self.assertIn("CALIBRATED", r["origin_composition"]["origin"])

    def test_22_la_calidad_del_modelo_declara_su_contrato(self):
        r = estimar(entrada(con_calibrado=True))
        self.assertIn(r["evidence_quality"]["model_quality"], est.ESTADOS_DIMENSION)
        incompleto = {k: v for k, v in modelo_calibrado().items() if k != "sample_size"}
        r2 = estimar(entrada(modelo_calibrado=incompleto))
        self.assertEqual(r2["evidence_quality"]["model_quality"], "LOW")
        self.assertEqual(r2["status"], "NOT_ESTIMABLE")


if __name__ == "__main__":
    unittest.main()

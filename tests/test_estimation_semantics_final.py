# -*- coding: utf-8 -*-
"""DICTUS ESTIMATION ENGINE v1.0 — CIERRE SEMÁNTICO FINAL (§20).

Cubre, con nombre propio, lo que esta ronda cierra:

  §5.3 · ORIGIN de M5: una transformación determinista de **UNA** fuente externa NO es
         `COMPUTED_FROM_SOURCES` (esa clase exige **≥2** fuentes materiales). El arreglo
         NO relaja la regla: 2+ fuentes externas SIGUEN dando `COMPUTED_FROM_SOURCES`.
  §29  · El rango sale de los min/max LITERALES de la fuente aplicados al área del
         sujeto y JAMÁS se estrecha (se redondea hacia fuera).
  §5.4 · `central_reference_visibility`: política EXPLÍCITA y VERSIONADA
         (`VISIBLE`/`DEEMPHASIZED`/`HIDDEN`), sin umbrales escondidos.
  §7/§8 · La P6 ya no enfrenta «ESTIMACIÓN INDICATIVA» con «VALOR ESTIMADO POR LA CORRIDA
         · VALORACIÓN NO DISPONIBLE»: el bloque legacy nombra la compuerta que REALMENTE
         cierra (`VERIFIED_MARKET_EVIDENCE_GATE`), y la P1 muestra el resultado de
         `ESTIMATION_GATE` sin declarar a la vez que no hay estimación.
  §12/§13 · Golden REAL A/B sobre el MISMO expediente, sin fixtures para la aceptación.
"""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "api"), str(ROOT / "scripts"),
           str(Path(__file__).resolve().parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import estimation as est          # noqa: E402
import estimation_state as egs    # noqa: E402
from _fixtures_estimation import entrada, estimar, procedencia  # noqa: E402

FOLIO = "040-646406"
GOLDEN = ROOT / "docs" / "forensics" / FOLIO
RUN_STATE = GOLDEN / "dictus_2b" / f"DICTUS_RUN_STATE_{FOLIO}.json"
MANIFEST = GOLDEN / "dictus_2b" / f"DICTUS_MANIFEST_{FOLIO}.json"


def _referencia_nivel_3(*, minimo: float = 2_000_000.0, maximo: float = 8_000_000.0,
                        source_id: str = "BAQ_OBS_VALORESM2_AREA",
                        banda: str = "70-90", sample_size=None,
                        sha256: str = "a" * 64) -> dict:
    """Referencia de nivel 3 con procedencia HTTP completa (contrato de M5)."""
    return {
        "origen_tipo": "EXTERNAL_SOURCE", "nivel": est.NIVEL_REFERENCIA_AGREGADA,
        "source_id": source_id, "proveedor": "Geoportal municipal",
        "fecha": "2026-06-30", "referencia": "valoresm2_area/MapServer/1",
        "sha256": sha256, "reference_id": f"{source_id}/L1/Sector",
        "evidence_hash": "h" * 64, "content_hash": "c" * 64,
        "acquisition_id": f"ACQ-{source_id}-000000000000",
        "rango_valor_m2": {"min": minimo, "max": maximo, "unidad": "COP/m2"},
        "banda_area_m2": banda, "sample_size": sample_size,
        "metodologia_declarada": "análisis de compraventas SNR 2026",
        "provenance": {"source_id": source_id, "proveedor": "Geoportal municipal",
                       "fecha": "2026-06-30",
                       "referencia": "valoresm2_area/MapServer/1", "sha256": sha256,
                       "url": "https://geoportal/query", "http": 200, "bytes": 740,
                       "consultado_en": "2026-06-30T00:00:00+00:00"},
    }


def _cargar(ruta: Path):
    if not ruta.exists():
        return None
    return json.loads(ruta.read_text(encoding="utf-8"))


# ══════════════════════════════════════════════════════════════════════════════
# 1 · ORIGIN DE M5 (§5.3) — el defecto real de esta ronda
# ══════════════════════════════════════════════════════════════════════════════
class TestOriginDeM5(unittest.TestCase):

    def test_m5_single_source_origin_not_computed_from_sources(self):
        """UNA fuente + derivación determinista ≠ `COMPUTED_FROM_SOURCES`."""
        e = entrada(estadisticas_externas=[_referencia_nivel_3()])
        m5 = est.metodo_m5_referencia_agregada(e)
        self.assertEqual(m5["status"], est.STATUS_METHOD_AVAILABLE)
        # La EVIDENCIA BASE es la fuente externa citada…
        self.assertEqual(m5["origin"], est.am.ORIGEN_EXTERNO)
        # …y la TRANSFORMACIÓN viaja APARTE, con su tipo, su fórmula y su cardinal.
        self.assertEqual(m5["derivation"]["type"], est.DERIVACION_PUNTO_MEDIO_RANGO)
        self.assertEqual(m5["derivation"]["formula"], est.DERIVACION_FORMULA_PUNTO_MEDIO)
        self.assertEqual(m5["derivation"]["source_count"], 1)
        self.assertEqual(m5["derivation"]["source_ids"], ["BAQ_OBS_VALORESM2_AREA"])
        self.assertEqual(m5["result"]["origen_tipo"], est.ORIGEN_DERIVADO_EXTERNO)
        self.assertEqual(m5["result"]["origen_evidencia_base"], est.am.ORIGEN_EXTERNO)
        # El defecto: NINGUNA CLASE declarada por el método puede ser la composición de
        # fuentes. (El texto de `derivation.declaracion` la menciona SÓLO para negarla: se
        # comprueba que esa es la única mención.)
        self.assertNotEqual(m5["origin"], est.am.ORIGEN_COMPUTADO)
        self.assertNotEqual(m5["result"]["origen_tipo"], est.am.ORIGEN_COMPUTADO)
        self.assertNotEqual(m5["derivation"]["origin"], est.am.ORIGEN_COMPUTADO)
        self.assertNotIn(est.am.ORIGEN_COMPUTADO, {m5["origin"],
                                                   m5["result"]["origen_tipo"],
                                                   m5["derivation"]["origin"]})
        self.assertIn("exige ≥2", m5["derivation"]["declaracion"])
        self.assertTrue(m5["derivation"]["no_es_composicion_de_fuentes"])
        # La clase nueva está en el vocabulario extendido y NO es habilitante por sí sola.
        self.assertIn(est.ORIGEN_DERIVADO_EXTERNO, est.ORIGENES_EXTENDIDOS)
        clas = est.clasificar_origen_extendido({"origen_tipo": est.ORIGEN_DERIVADO_EXTERNO})
        self.assertEqual(clas["clase"], est.ORIGEN_DERIVADO_EXTERNO)
        self.assertFalse(clas["origin_gate"])
        self.assertFalse(clas["sostiene_estimacion"])
        self.assertNotEqual(clas["clase"], est.am.ORIGEN_MANUAL,
                            "una derivación declarada NO se degrada a MANUAL_CONFIG")
        # Y el vocabulario CERRADO de `atribucion_mercado` no se toca.
        self.assertNotIn(est.ORIGEN_DERIVADO_EXTERNO, est.am.ORIGENES)

    def test_m5_two_sources_can_be_computed_from_sources(self):
        """La regla NO se relajó: 2+ fuentes externas SIGUEN dando COMPUTED_FROM_SOURCES."""
        dos = est.componer_origen([{"origen_tipo": est.am.ORIGEN_EXTERNO,
                                    **procedencia(1)},
                                   {"origen_tipo": est.am.ORIGEN_EXTERNO,
                                    **procedencia(2)}])
        self.assertEqual(dos["origin"], est.am.ORIGEN_COMPUTADO)
        self.assertEqual(dos["regla"], "R5_FUENTES_MULTIPLES")
        # La autoridad de clasificación sigue exigiendo ≥2 fuentes para esa clase…
        una = est.am.clasificar_origen({"origen_tipo": est.am.ORIGEN_COMPUTADO,
                                        "fuentes": [procedencia(1)]})
        self.assertFalse(una["origin_gate"])
        self.assertEqual(una["origin"], est.am.ORIGEN_MANUAL)
        dos_completas = est.am.clasificar_origen(
            {"origen_tipo": est.am.ORIGEN_COMPUTADO,
             "fuentes": [procedencia(1), procedencia(2)]})
        self.assertTrue(dos_completas["origin_gate"])
        # …y tres fuentes también (no hay regresión de cardinal).
        tres = est.componer_origen([{"origen_tipo": est.am.ORIGEN_EXTERNO, **procedencia(i)}
                                    for i in (1, 2, 3)])
        self.assertEqual(tres["origin"], est.am.ORIGEN_COMPUTADO)

    def test_m5_level3_opens_estimation_with_limitations(self):
        """LEVEL 3 sostiene la ESTIMACIÓN (con limitaciones), no un valor verificado."""
        r = estimar(entrada(estadisticas_externas=[_referencia_nivel_3()]))
        self.assertEqual(r["estimation_gate"]["gate_state"],
                         est.ESTIMATION_OPEN_WITH_LIMITATIONS)
        self.assertEqual(r["status"], est.STATUS_INDICATIVE_ESTIMATE)
        self.assertEqual(r["evidence_quality"]["level"], est.QUALITY_INDICATIVE)
        self.assertIn(est.METODO_M5, r["methods_used_ids"])
        self.assertNotEqual(r["estimation_gate"]["gate_state"], est.ESTIMATION_OPEN)
        self.assertFalse(r["envelope"]["es_valor_verificado"])

    def test_m5_level3_never_opens_verified_market_gate(self):
        """§30 · las dos compuertas COEXISTEN: estimación abierta, evidencia NO verificada."""
        r = estimar(entrada(estadisticas_externas=[_referencia_nivel_3()]))
        self.assertEqual(r["verified_market_evidence_gate"]["gate_state"],
                         est.VERIFIED_CLOSED)
        self.assertEqual(r["estimation_gate"]["gate_state"],
                         est.ESTIMATION_OPEN_WITH_LIMITATIONS)
        razones = " | ".join(r["verified_market_evidence_gate"]["reasons"])
        self.assertIn("nivel 3", razones.lower())
        self.assertIn("NO acredita la unidad", razones)
        self.assertTrue(r["verified_market_evidence_gate"]["evidencia_agregada_no_atribuible"])
        # Y la P6 nombra la compuerta correcta sin cerrar la estimación.
        p6 = egs.contrato_p6(r, consulta="2026-07-01")
        self.assertEqual(p6["verified_market_evidence_gate"], est.VERIFIED_CLOSED)
        self.assertEqual(p6["estimation_gate"], est.ESTIMATION_OPEN_WITH_LIMITATIONS)


# ══════════════════════════════════════════════════════════════════════════════
# 2 · RANGO (§29) — literales de la fuente, nunca estrechados
# ══════════════════════════════════════════════════════════════════════════════
class TestRangoDelNivel3(unittest.TestCase):

    def _estimado(self, **kw):
        ref = _referencia_nivel_3(**kw)
        return ref, estimar(entrada(area={"valor_m2": 82.5,
                                          "origen_tipo": "EXTERNAL_SOURCE",
                                          "provenance": procedencia(9)},
                                    estadisticas_externas=[ref]))

    def test_m5_range_uses_literal_source_bounds(self):
        ref, r = self._estimado(minimo=2_000_000.0, maximo=8_000_000.0)
        area = r["inputs"]["area_m2"]
        _b = r["range"]["banda_oficial_usada"]
        self.assertEqual(_b["min"], ref["rango_valor_m2"]["min"])
        self.assertEqual(_b["max"], ref["rango_valor_m2"]["max"])
        # Los BORDES del rango publicable son los min/max LITERALES × área.
        self.assertLessEqual(r["range_low"], ref["rango_valor_m2"]["min"] * area)
        self.assertGreaterEqual(r["range_high"], ref["rango_valor_m2"]["max"] * area)
        # Y el redondeo es HACIA FUERA, nunca hacia dentro.
        self.assertEqual(r["range_low"], est._redondear_borde(
            ref["rango_valor_m2"]["min"] * area,
            r["range"]["semi_ancho_relativo"], abajo=True))
        self.assertEqual(r["range_high"], est._redondear_borde(
            ref["rango_valor_m2"]["max"] * area,
            r["range"]["semi_ancho_relativo"], abajo=False))
        # La cifra central NO es la media de los comparables ni una tasa manual.
        self.assertAlmostEqual(r["value_m2_central"],
                               (ref["rango_valor_m2"]["min"]
                                + ref["rango_valor_m2"]["max"]) / 2, places=2)

    def test_m5_range_never_narrows_source_range(self):
        """El ancho calculado puede declarar MÁS, jamás menos que la banda publicada."""
        _ref, r = self._estimado(minimo=1_000_000.0, maximo=12_000_000.0)
        semi_calc = r["range"]["componentes"]["semi_ancho_calculado"]
        semi_eff = r["range"]["semi_ancho_relativo"]
        self.assertGreaterEqual(semi_eff, semi_calc)
        self.assertGreater(semi_eff, 0.0)
        self.assertGreaterEqual(semi_eff, 0.30,
                                "una banda de 1M–12M no puede publicarse como estrecha")
        # El ancho efectivo es el del rango realmente publicado.
        self.assertAlmostEqual(semi_eff, (r["range_high"] - r["range_low"])
                               / (2 * r["central_estimate"]), places=3)

    def test_m5_sample_size_null_preserved(self):
        ref, r = self._estimado(sample_size=None)
        m5 = [m for m in r["methods_used"] + r["methods_rejected"]
              if m["method_id"] == est.METODO_M5][0]
        self.assertIsNone(ref["sample_size"])
        self.assertIsNone(m5["inputs"]["sample_size"])
        self.assertFalse(m5["inputs"]["sample_size_declarado"])
        self.assertIsNone(m5["dispersion"]["n"])
        # No se rellena en ninguna parte del resultado serializado.
        self.assertIsNone(r["inputs"].get("sample_size_estimado", None))
        ajustes = {a["tipo"]: a["estado"] for a in m5["adjustments"]}
        self.assertEqual(ajustes.get("muestra (N) del análisis"), "NO_APLICADO")
        self.assertIn("muestra", " ".join(r["limitations"]).lower())

    def test_m5_no_manual_market_rate(self):
        """La tasa escrita a mano entra DECLARADA y EXCLUIDA: no mueve ninguna cifra."""
        ref = _referencia_nivel_3()
        base = entrada(area={"valor_m2": 82.5, "origen_tipo": "EXTERNAL_SOURCE",
                             "provenance": procedencia(9)},
                       estadisticas_externas=[ref])
        sin_manual = estimar(copy.deepcopy(base))
        con_manual = {**copy.deepcopy(base),
                      "tasa_manual": {"origen_tipo": est.am.ORIGEN_MANUAL,
                                      "valor_m2": 9_999_999,
                                      "source": "parámetros de la corrida"}}
        r = estimar(con_manual)
        self.assertEqual(r["range_low"], sin_manual["range_low"])
        self.assertEqual(r["range_high"], sin_manual["range_high"])
        self.assertEqual(r["central_estimate"], sin_manual["central_estimate"])
        self.assertNotEqual(r["central_estimate"], 9_999_999 * 82.5)
        self.assertIn(est.am.ORIGEN_MANUAL, r["origin_composition"]["clases_excluidas"])
        self.assertNotIn(est.am.ORIGEN_MANUAL, r["origin_composition"]["clases_usadas"])
        c = egs.contadores(r, con_manual)
        self.assertEqual(c["manual_inputs_used"], 0)
        self.assertEqual(c["manual_inputs_declared"], 1)

    def test_m5_no_legacy_prior(self):
        """El prior legacy entra DECLARADO y EXCLUIDO: no mueve ninguna cifra."""
        base = entrada(area={"valor_m2": 82.5, "origen_tipo": "EXTERNAL_SOURCE",
                             "provenance": procedencia(9)},
                       estadisticas_externas=[_referencia_nivel_3()])
        sin_prior = estimar(copy.deepcopy(base))
        con_prior = {**copy.deepcopy(base),
                     "modelo_legacy": {"origen_tipo": est.ORIGEN_PRIOR_LEGACY,
                                       "parametros_declarados": {"factor": "5.2M"}}}
        r = estimar(con_prior)
        self.assertEqual(r["range_low"], sin_prior["range_low"])
        self.assertEqual(r["range_high"], sin_prior["range_high"])
        self.assertEqual(r["central_estimate"], sin_prior["central_estimate"])
        self.assertIn(est.ORIGEN_PRIOR_LEGACY,
                      r["origin_composition"]["clases_excluidas"])
        self.assertNotIn(est.ORIGEN_PRIOR_LEGACY,
                         r["origin_composition"]["clases_usadas"])
        c = egs.contadores(r, con_prior)
        self.assertEqual(c["legacy_priors_used"], 0)
        self.assertEqual(c["legacy_priors_declared"], 1)
        self.assertNotEqual(r["central_estimate"], 399_500_000)
        self.assertNotIn(399_500_000, (r["central_estimate"],
                                       r["range_low"], r["range_high"]))


# ══════════════════════════════════════════════════════════════════════════════
# 3 · VISIBILIDAD DE LA REFERENCIA CENTRAL (§5.4)
# ══════════════════════════════════════════════════════════════════════════════
class TestVisibilidadReferenciaCentral(unittest.TestCase):

    def _p(self, **kw):
        kw.setdefault("central", 300_000_000.0)
        kw.setdefault("low", 130_000_000.0)
        kw.setdefault("high", 490_000_000.0)
        return est.politica_visibilidad_referencia_central(**kw)

    def test_central_reference_visibility_policy(self):
        # 1 · la política es VERSIONADA, declara sus umbrales y NO se calibró con datos.
        p = self._p(low=270_000_000.0, high=330_000_000.0, semi_ancho_relativo=0.10,
                    sample_size=180, sample_size_declarado=True,
                    comparables_usados=9, evidence_quality=est.QUALITY_HIGH)
        self.assertEqual(p["policy_version"], est.CENTRAL_REFERENCE_VISIBILITY_VERSION)
        self.assertEqual(p["state"], est.VISIBILIDAD_VISIBLE)
        self.assertTrue(p["imprime_la_cifra"])
        self.assertFalse(p["calibrada_empiricamente"])
        self.assertTrue(p["fundamento"])
        self.assertEqual(set(p["umbrales_aplicados"]),
                         set(est.UMBRALES_VISIBILIDAD_CENTRAL))
        self.assertIn(p["state"], est.ESTADOS_VISIBILIDAD_CENTRAL)

        # 2 · el caso REAL del Golden: 0 comparables + referencia AGREGADA de nivel 3 +
        # `sample_size` NO declarado + rango muy amplio + evidencia INDICATIVE ⇒
        # DEEMPHASIZED (se publica SUBORDINADA, jamás como cifra de la unidad).
        real = self._p(semi_ancho_relativo=0.5806, sample_size=None,
                       sample_size_declarado=False, comparables_usados=0,
                       evidence_quality=est.QUALITY_INDICATIVE,
                       referencia_agregada_level_3=True)
        self.assertEqual(real["state"], est.VISIBILIDAD_DEENFATIZADA)
        self.assertTrue(real["imprime_la_cifra"])
        self.assertTrue(any("NO acredita esta unidad" in x for x in real["reasons"]))
        self.assertIn("no acredita la unidad", real["reason_short"])

        # 3 · a la amplitud máxima del motor (±60 %) el punto medio no informa ⇒ HIDDEN.
        oculta = self._p(semi_ancho_relativo=0.62, sample_size=None,
                         comparables_usados=0, evidence_quality=est.QUALITY_INDICATIVE)
        self.assertEqual(oculta["state"], est.VISIBILIDAD_OCULTA)
        self.assertFalse(oculta["imprime_la_cifra"])

        # 4 · un salto de 4× entre extremos también la oculta.
        salto = self._p(low=100_000_000.0, high=420_000_000.0, semi_ancho_relativo=0.20,
                        sample_size=200, sample_size_declarado=True, comparables_usados=9,
                        evidence_quality=est.QUALITY_HIGH)
        self.assertEqual(salto["state"], est.VISIBILIDAD_OCULTA)

        # 5 · sin cifra que publicar, HIDDEN (y se declara el motivo).
        self.assertEqual(self._p(central=None, low=None, high=None,
                                 semi_ancho_relativo=None)["state"],
                         est.VISIBILIDAD_OCULTA)

        # 6 · ninguna combinación devuelve un estado fuera del vocabulario, y el estado
        # viaja en el RESULTADO del motor.
        r = estimar(entrada(estadisticas_externas=[_referencia_nivel_3()]))
        vis = r["central_reference_visibility"]
        self.assertIn(vis["state"], est.ESTADOS_VISIBILIDAD_CENTRAL)
        self.assertEqual(vis["policy_version"], est.CENTRAL_REFERENCE_VISIBILITY_VERSION)
        self.assertFalse(vis["calibrada_empiricamente"])
        m5 = [m for m in r["methods_used"] if m["method_id"] == est.METODO_M5][0]
        self.assertEqual(m5["central_reference"]["visibility"], vis["state"])
        self.assertEqual(m5["central_reference_visibility"]["state"], vis["state"])
        # Y el contrato de impresión lo respeta: sin `imprime_la_cifra`, NO hay cifra.
        p6 = egs.contrato_p6(r, consulta="2026-07-01")
        if not vis["imprime_la_cifra"]:
            self.assertNotIn("$", p6["REFERENCIA CENTRAL"])
            self.assertIn("no publicada", p6["REFERENCIA CENTRAL"])


# ══════════════════════════════════════════════════════════════════════════════
# 4 · CONSISTENCIA P1/P6 Y RÓTULO DEL BLOQUE LEGACY (§7/§8)
# ══════════════════════════════════════════════════════════════════════════════
class TestConsistenciaDeImpresion(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.rs = _cargar(RUN_STATE)
        cls.man = _cargar(MANIFEST)
        if cls.rs is None or cls.man is None:
            raise unittest.SkipTest("falta el Golden 040-646406")
        cls.salida = egs.ejecutar(cls.rs, cls.man)
        cls.r = cls.salida["resultado"]
        cls.p1 = egs.contrato_p1(cls.r)
        cls.p6 = egs.contrato_p6(cls.r, consulta=cls.salida["referencia"])

    def test_p1_p6_estimation_consistency(self):
        """P1 == P6 == `EstimationResult` en estado y rango. Un solo hecho."""
        r = self.r
        self.assertEqual(self.p1["status"], r["status"])
        self.assertEqual(self.p6["status"], r["status"])
        self.assertEqual(self.p6["etiqueta"], self.p1["etiqueta"])
        self.assertEqual(self.p1["etiqueta"], egs.etiqueta_de(r))
        self.assertEqual(self.p1["confianza"], self.p6["CONFIANZA"])
        self.assertEqual(self.p1["confianza"], egs.confianza_de(r))
        if r["range_low"] is not None:
            rango = f"{egs.pesos(r['range_low'])} – {egs.pesos(r['range_high'])}"
            self.assertIn(rango, self.p1["linea_2"])
            self.assertIn(rango, self.p6["RANGO ESTIMADO"])
        # La valoración LEGACY puede tener otro estado de compuerta, pero NO puede
        # contradecir a `ESTIMATION_GATE`: son DOS hechos declarados por separado.
        self.assertEqual(self.p6["estimation_gate"], r["estimation_gate"]["gate_state"])
        self.assertEqual(self.p6["verified_market_evidence_gate"],
                         r["verified_market_evidence_gate"]["gate_state"])
        self.assertNotEqual(self.p6["estimation_gate"], "CLOSED")
        self.assertEqual(self.p6["verified_market_evidence_gate"], est.VERIFIED_CLOSED)
        # Cuatro hechos, cuatro nombres, ninguno sustituye a otro.
        self.assertIn(f"ESTIMATION_GATE = {r['estimation_gate']['gate_state']}",
                      self.p1["linea_3"])
        self.assertIn(est.METODO_M5, r["methods_used_ids"])

    def test_legacy_valuation_label_does_not_say_valor_estimado(self):
        """El bloque legacy NOMBRA la compuerta que cierra y NO dice «VALOR ESTIMADO»."""
        import dictus_ejecutivo as de
        bloque = de.bloque_estimacion_p6(self.p6, lambda *a, **k: None, 0.0)
        self.assertTrue(callable(bloque))
        # El rótulo vive en el render; su literal se fija aquí y se comprueba en el PDF
        # (test del expediente real, más abajo). Aquí se fija el CONTRATO de vocabulario.
        self.assertIn("EVIDENCIA DE MERCADO VERIFICADA · NO HABILITADA",
                      de.ROTULO_VALORACION_BLOQUEADA)
        self.assertNotIn("VALOR ESTIMADO", de.ROTULO_VALORACION_BLOQUEADA)
        self.assertIn("no se imprime ningún monto",
                      de.TEXTO_GARANTIA_SIN_CIFRA)
        self.assertEqual(
            de.RAZON_VERIFIED_MARKET_EVIDENCE_NO_HABILITADA,
            egs.razon_evidencia_verificada_no_habilitada())
        # La P1 imprime el resultado de ESTIMATION_GATE y NO declara a la vez que no hay
        # estimación: la etiqueta del motor manda.
        self.assertEqual(self.p1["etiqueta"], "ESTIMACIÓN INDICATIVA")
        self.assertNotIn("NO EMITIR VALORACIÓN", self.p1["linea_1"])
        self.assertNotIn("NO EMITIR VALORACIÓN", self.p1["linea_2"])
        self.assertNotIn("ESTIMACIÓN NO DISPONIBLE", self.p1["linea_1"])


# ══════════════════════════════════════════════════════════════════════════════
# 5 · GOLDEN REAL A/B (§12/§13) — el MISMO expediente, sin fixtures
# ══════════════════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════════════
# 6 · EL PDF REAL DEL GOLDEN (§8) — la contradicción, sobre el documento emitido
# ══════════════════════════════════════════════════════════════════════════════
class TestPdfRealDelGolden(unittest.TestCase):
    """Lo que el CLIENTE lee: P1 y P6 del ejecutivo regenerado por `dictus_run.py`."""

    @classmethod
    def setUpClass(cls):
        cls.pdf = GOLDEN / "dictus_2b" / f"DICTUS_EJECUTIVO_{FOLIO}.pdf"
        if not cls.pdf.exists():
            raise unittest.SkipTest("no hay ejecutivo regenerado del Golden")
        from pypdf import PdfReader
        paginas = PdfReader(str(cls.pdf)).pages
        cls.p1 = " ".join(str(paginas[0].extract_text() or "").split())
        cls.p6 = " ".join(str(paginas[5].extract_text() or "").split())

    def test_p6_legacy_block_names_the_gate_and_not_valor_estimado(self):
        self.assertIn("EVIDENCIA DE MERCADO VERIFICADA · NO HABILITADA", self.p6)
        self.assertIn("VERIFIED_MARKET_EVIDENCE_GATE = CLOSED", self.p6)
        self.assertIn("no existen comparables individualizados suficientes para "
                      "atribuir un valor verificado a esta unidad", self.p6)
        self.assertIn("no se imprime ningún monto, ni $0", self.p6)
        self.assertNotIn("VALOR ESTIMADO POR LA CORRIDA", self.p6)
        self.assertNotIn("VALORACIÓN NO DISPONIBLE", self.p6)
        # `COMPUERTA CLOSED` sigue impreso (es la compuerta nombrada justo arriba).
        self.assertIn("COMPUERTA CLOSED", self.p6)

    def test_p1_no_declara_a_la_vez_que_no_hay_estimacion(self):
        self.assertIn("ESTIMACIÓN ECONÓMICA DICTUS · ESTIMACIÓN INDICATIVA", self.p1)
        self.assertIn("ESTIMATION_GATE = OPEN_WITH_LIMITATIONS", self.p1)
        self.assertIn("Confianza: INDICATIVA", self.p1)
        self.assertNotIn("NO EMITIR VALORACIÓN", self.p1)
        # La valoración de la CORRIDA se nombra como NO HABILITADA por la evidencia (no
        # como ausencia de valor) y el dominio se llama «Valoración corrida»: las dos
        # ambigüedades que el cliente leía como «no hay estimación» desaparecen.
        self.assertIn("VALORACIÓN DE LA CORRIDA", self.p1.upper())
        self.assertIn("no habilitada", self.p1.lower())
        self.assertIn("VALORACIÓN CORRIDA", self.p1.upper())
        self.assertNotIn("VALOR NO DISPONIBLE", self.p1)
        self.assertNotIn("VALORACIÓN NO DISPONIBLE", self.p1)

    def test_p1_y_p6_comparten_rango_y_referencia(self):
        self.assertIn("Rango: $ 130.000.000 – $ 490.000.000", self.p1)
        self.assertIn("$ 130.000.000 – $ 490.000.000", self.p6)
        self.assertIn("$ 310.000.000", self.p6)
        self.assertNotIn("399.500.000", self.p1 + self.p6)


class TestGoldenRealAB(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rs = _cargar(RUN_STATE)
        cls.man = _cargar(MANIFEST)
        if cls.rs is None or cls.man is None:
            raise unittest.SkipTest("falta el Golden 040-646406")

    def _escenario(self, *, sin_cosecha: bool):
        original = egs.cargar_estadisticas_de_cosecha
        if sin_cosecha:
            egs.cargar_estadisticas_de_cosecha = lambda ruta=None: (
                [], {"estado": "NO INCORPORADA",
                     "motivo": "escenario de contraste: sin cosecha municipal"})
        try:
            return egs.ejecutar(copy.deepcopy(self.rs), copy.deepcopy(self.man))
        finally:
            egs.cargar_estadisticas_de_cosecha = original

    def test_golden_with_level3_indicative(self):
        """B · CON la referencia de nivel 3: `OPEN_WITH_LIMITATIONS` + INDICATIVE."""
        s = self._escenario(sin_cosecha=False)
        r = s["resultado"]
        self.assertTrue(s["entrada"].get("estadisticas_externas"),
                        "el Golden incorpora la referencia agregada de nivel 3")
        self.assertEqual(r["estimation_gate"]["gate_state"],
                         est.ESTIMATION_OPEN_WITH_LIMITATIONS)
        self.assertEqual(r["status"], est.STATUS_INDICATIVE_ESTIMATE)
        self.assertEqual(r["evidence_quality"]["level"], est.QUALITY_INDICATIVE)
        self.assertEqual(r["verified_market_evidence_gate"]["gate_state"],
                         est.VERIFIED_CLOSED)
        self.assertIsNotNone(r["range_low"])
        self.assertLess(r["range_low"], r["range_high"])
        m5 = [m for m in r["methods_used"] if m["method_id"] == est.METODO_M5][0]
        self.assertEqual(m5["origin"], est.am.ORIGEN_EXTERNO)
        self.assertEqual(m5["result"]["origen_tipo"], est.ORIGEN_DERIVADO_EXTERNO)
        self.assertEqual(s["contadores"]["manual_inputs_used"], 0)
        self.assertEqual(s["contadores"]["legacy_priors_used"], 0)
        self.assertEqual(s["contadores"]["origins_used"], ["EXTERNAL_SOURCE"])

    def test_golden_without_level3_closed(self):
        """A · SIN la referencia de nivel 3: `CLOSED` + NOT_ESTIMABLE, sin cifra."""
        s = self._escenario(sin_cosecha=True)
        r = s["resultado"]
        self.assertEqual(s["entrada"].get("estadisticas_externas"), [])
        self.assertEqual(r["estimation_gate"]["gate_state"], est.ESTIMATION_CLOSED)
        self.assertEqual(r["status"], est.STATUS_NOT_ESTIMABLE)
        self.assertEqual(r["evidence_quality"]["level"], est.QUALITY_INSUFFICIENT)
        self.assertIsNone(r["range_low"])
        self.assertIsNone(r["range_high"])
        self.assertIsNone(r["central_estimate"])
        self.assertEqual(r["central_reference_visibility"]["state"],
                         est.VISIBILIDAD_OCULTA)
        self.assertFalse(r["central_reference_visibility"]["imprime_la_cifra"])
        self.assertEqual(s["contadores"]["manual_inputs_used"], 0)
        self.assertEqual(s["contadores"]["legacy_priors_used"], 0)
        # La ÚNICA diferencia material con B es la evidencia de nivel 3.
        b = self._escenario(sin_cosecha=False)
        self.assertEqual(b["resultado"]["verified_market_evidence_gate"]["gate_state"],
                         r["verified_market_evidence_gate"]["gate_state"])
        self.assertEqual(b["contadores"]["manual_inputs_used"],
                         s["contadores"]["manual_inputs_used"])
        self.assertEqual(b["contadores"]["legacy_priors_used"],
                         s["contadores"]["legacy_priors_used"])


if __name__ == "__main__":
    unittest.main()

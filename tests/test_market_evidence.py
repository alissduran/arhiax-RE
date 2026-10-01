# -*- coding: utf-8 -*-
"""DICTUS ESTIMATION ENGINE v1.0 · FASE 1 — pruebas OFFLINE de los contratos de mercado.

Todo aquí corre SIN red y SIN escribir nada. Cubre:

  1. §5 MARKET EVIDENCE LADDER  → los 5 niveles, su orden, quién sostiene una cifra y la
     regla dura «la ausencia de LEVEL 1 NO implica CLOSED».
  2. §6 contrato `MarketObservation` → los 28 campos, desconocidos en `None` y NINGÚN
     valor inventado (el constructor no deriva `price_per_m2` ni rellena huecos).
  3. §7 `ComparableScore` → veredictos EXPLICABLES con motivo por comparable, sin score
     arbitrario; `parking`/`floor`/`condition` sólo si se conocen y nunca deciden.
  4. §8 control de outliers → extremos, área incompatible, tipología distinta, sector
     incorrecto, duplicados y datos vencidos → `excluded_comparables` + `exclusion_reason`,
     NUNCA borrado silencioso.
  5. §26 `blocking_por_propósito` → `required_for_estimation` SEPARADO de
     `required_for_decision`, con la altura POT como caso declarado.
  6. Guardas de doctrina sobre los artefactos REALES: origen no habilitante, ausencia de
     cualquier fuente de mercado en el pack, y que `399.500.000` no reaparezca.

Los datos de PRUEBA de los comparables son de laboratorio (no son datos del producto). Las
lecturas del registro, de la matriz de cobertura y del Golden son del producto REAL.
"""
import ast
import csv
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))

import market_evidence as me  # noqa: E402

RUN_STATE = (ROOT / "docs" / "forensics" / "040-646406" / "dictus_2b"
             / "DICTUS_RUN_STATE_040-646406.json")
MANIFEST = (ROOT / "docs" / "forensics" / "040-646406" / "dictus_2b"
            / "DICTUS_MANIFEST_040-646406.json")
REGISTRO = ROOT / "docs" / "source_pack" / "barranquilla_sources_v1.json"
COVERAGE = ROOT / "docs" / "source_pack" / "SOURCE_COVERAGE_MATRIX_040-646406.csv"
ACQUISITION = ROOT / "docs" / "source_pack" / "SOURCE_ACQUISITION_MATRIX_040-646406.csv"
AUDIT_JSON = ROOT / "docs" / "estimation" / "ESTIMATION_INPUT_AUDIT_040-646406.json"
MATRIX_CSV = ROOT / "docs" / "estimation" / "MARKET_EVIDENCE_MATRIX_040-646406.csv"

REGIMEN_PH = "Propiedad Horizontal"
SECTOR = "Miramar"


def _obs(oid: str, **kw) -> "me.MarketObservation":
    """Observación de laboratorio: sólo los campos que la prueba declara."""
    base = {"observation_id": oid, "source_id": "FIJO_PRUEBA",
            "origin": me.ORIGEN_EXTERNO}
    base.update(kw)
    return me.MarketObservation(**base)


def _comparable(**kw) -> "me.MarketObservation":
    """Comparable completo y compatible con el sujeto (ACCEPTED salvo que la prueba diga otra cosa)."""
    base = {"listing_or_record_id": "L-REF", "sector": SECTOR, "distance_to_subject_m": 120.0,
            "area_difference_pct": 3.0, "typology_match": True, "regime": REGIMEN_PH,
            "freshness_days": 30, "asking_price": 360_000_000.0, "area_m2": 60.0,
            "price_per_m2": 6_000_000.0}
    base.update(kw)
    return base


def _score(obs, **kw):
    kw.setdefault("regime_sujeto", REGIMEN_PH)
    kw.setdefault("sector_sujeto", SECTOR)
    return me.evaluar_comparable(obs, **kw)


# ══════════════════════════════════════════════════════════════════════════════
# 1 · §5 · MARKET EVIDENCE LADDER
# ══════════════════════════════════════════════════════════════════════════════
class TestEscaleraDeEvidencia(unittest.TestCase):

    def test_los_cinco_niveles_tienen_los_nombres_exactos_y_su_orden(self):
        self.assertEqual(me.NIVELES_EVIDENCIA_MERCADO, (
            "LEVEL_1_DIRECT_COMPARABLES",
            "LEVEL_2_LOCAL_MARKET_OBSERVATIONS",
            "LEVEL_3_AGGREGATED_MARKET_REFERENCES",
            "LEVEL_4_CALIBRATED_MODEL_PRIOR",
            "LEVEL_5_STATIC_REFERENCE",
        ))
        self.assertEqual([me.ORDEN_NIVEL[n] for n in me.NIVELES_EVIDENCIA_MERCADO],
                         [1, 2, 3, 4, 5])
        for nivel in me.NIVELES_EVIDENCIA_MERCADO:
            self.assertIn(nivel, me.DESCRIPCION_NIVELES)
            self.assertIn(nivel, me.REQUISITOS_NIVEL)

    def test_vocabulario_cerrado_de_niveles(self):
        self.assertTrue(me.es_nivel_valido(me.LEVEL_1_DIRECT_COMPARABLES))
        self.assertFalse(me.es_nivel_valido("LEVEL_6_INVENTADO"))
        self.assertFalse(me.es_nivel_valido(None))
        self.assertFalse(me.es_nivel_valido("LEVEL_1"))

    def test_nivel_5_y_prior_no_calibrado_nunca_sostienen(self):
        self.assertTrue(me.nivel_sostiene_estimacion(me.LEVEL_1_DIRECT_COMPARABLES))
        self.assertTrue(me.nivel_sostiene_estimacion(me.LEVEL_2_LOCAL_MARKET_OBSERVATIONS))
        self.assertTrue(me.nivel_sostiene_estimacion(me.LEVEL_3_AGGREGATED_MARKET_REFERENCES))
        self.assertFalse(me.nivel_sostiene_estimacion(me.LEVEL_5_STATIC_REFERENCE))
        # LEVEL 4 sólo con calibración Y dataset declarado.
        self.assertFalse(me.nivel_sostiene_estimacion(me.LEVEL_4_CALIBRATED_MODEL_PRIOR))
        self.assertFalse(me.nivel_sostiene_estimacion(
            me.LEVEL_4_CALIBRATED_MODEL_PRIOR, calibrado=True))
        self.assertFalse(me.nivel_sostiene_estimacion(
            me.LEVEL_4_CALIBRATED_MODEL_PRIOR, dataset_declarado="d.csv"))
        self.assertTrue(me.nivel_sostiene_estimacion(
            me.LEVEL_4_CALIBRATED_MODEL_PRIOR, calibrado=True,
            dataset_declarado="d.csv"))

    def test_regla_dura_sin_level_1_no_es_closed(self):
        """La aserción central de la §5: la ausencia de comparables NO cierra."""
        solo_agregado = me.evaluar_escalera([me.LEVEL_3_AGGREGATED_MARKET_REFERENCES])
        self.assertTrue(solo_agregado["sin_level_1"])
        self.assertFalse(solo_agregado["implica_closed"])
        self.assertFalse(solo_agregado["closed_por_ausencia_total_de_soporte"])
        self.assertEqual(solo_agregado["mejor_nivel_con_soporte"],
                         me.LEVEL_3_AGGREGATED_MARKET_REFERENCES)
        self.assertIn("NO queda cerrada", solo_agregado["lectura"])

        solo_local = me.evaluar_escalera([me.LEVEL_2_LOCAL_MARKET_OBSERVATIONS])
        self.assertTrue(solo_local["sin_level_1"])
        self.assertFalse(solo_local["implica_closed"])

        for niveles in ([], [me.LEVEL_5_STATIC_REFERENCE],
                        [me.LEVEL_4_CALIBRATED_MODEL_PRIOR],
                        [me.LEVEL_5_STATIC_REFERENCE, me.LEVEL_4_CALIBRATED_MODEL_PRIOR]):
            self.assertFalse(me.evaluar_escalera(niveles)["implica_closed"],
                             f"{niveles} no puede implicar CLOSED por ausencia de LEVEL 1")

    def test_escalera_sin_soporte_declara_el_unico_motivo_de_cierre(self):
        vacia = me.evaluar_escalera([])
        self.assertTrue(vacia["closed_por_ausencia_total_de_soporte"])
        self.assertEqual(vacia["niveles_con_soporte"], [])
        self.assertIsNone(vacia["mejor_nivel"])

        solo_estatica = me.evaluar_escalera([me.LEVEL_5_STATIC_REFERENCE])
        self.assertTrue(solo_estatica["closed_por_ausencia_total_de_soporte"])
        self.assertEqual(solo_estatica["niveles_con_soporte"], [])
        self.assertEqual(solo_estatica["mejor_nivel"], me.LEVEL_5_STATIC_REFERENCE)

    def test_escalera_con_level_1_es_la_mejor_evidencia(self):
        e = me.evaluar_escalera([me.LEVEL_3_AGGREGATED_MARKET_REFERENCES,
                                 me.LEVEL_1_DIRECT_COMPARABLES])
        self.assertFalse(e["sin_level_1"])
        self.assertEqual(e["mejor_nivel"], me.LEVEL_1_DIRECT_COMPARABLES)
        self.assertEqual(e["mejor_nivel_con_soporte"], me.LEVEL_1_DIRECT_COMPARABLES)

    def test_clasificacion_de_una_referencia_por_su_origen(self):
        # Ningún origen no habilitante puede ascender de nivel 5.
        for origen in (me.ORIGEN_MANUAL, me.ORIGEN_PRIOR, me.ORIGEN_LEGACY_PRIOR,
                       me.ORIGEN_ESTATICO, None, "INVENTADO"):
            self.assertEqual(
                me.nivel_referencia_de_origen(origen, agregado=True,
                                              metodologia_declarada="m.yaml"),
                me.LEVEL_5_STATIC_REFERENCE,
                f"{origen!r} no puede salir de LEVEL 5")
        # Un agregado con metodología y origen habilitante sí es nivel 3.
        self.assertEqual(
            me.nivel_referencia_de_origen(me.ORIGEN_EXTERNO, agregado=True,
                                          metodologia_declarada="m.yaml"),
            me.LEVEL_3_AGGREGATED_MARKET_REFERENCES)
        # Sin metodología declarada no asciende: no se presume agregación.
        self.assertEqual(
            me.nivel_referencia_de_origen(me.ORIGEN_EXTERNO, agregado=True),
            me.LEVEL_5_STATIC_REFERENCE)

    def test_nivel_de_observacion_no_adivina_sin_precio(self):
        sin_precio = _obs("O-SP", sector=SECTOR, listing_or_record_id="L-9")
        self.assertIsNone(me.nivel_de_observacion(sin_precio))
        with self.assertRaises(TypeError):
            me.nivel_de_observacion({"no": "es una observación"})

    def test_nivel_de_observacion_individual_vs_local(self):
        individual = _obs("O-1", **_comparable())
        self.assertEqual(me.nivel_de_observacion(individual),
                         me.LEVEL_1_DIRECT_COMPARABLES)
        local = _obs("O-2", asking_price=360_000_000.0, sector=SECTOR)
        self.assertEqual(me.nivel_de_observacion(local),
                         me.LEVEL_2_LOCAL_MARKET_OBSERVATIONS)
        manual = _obs("O-3", origin=me.ORIGEN_MANUAL, **_comparable())
        self.assertEqual(me.nivel_de_observacion(manual), me.LEVEL_5_STATIC_REFERENCE)


# ══════════════════════════════════════════════════════════════════════════════
# 2 · ORÍGENES
# ══════════════════════════════════════════════════════════════════════════════
class TestOrigenesNoSostienen(unittest.TestCase):

    def test_solo_external_y_computed_sostienen(self):
        self.assertTrue(me.origin_sostiene_estimacion(me.ORIGEN_EXTERNO))
        self.assertTrue(me.origin_sostiene_estimacion(me.ORIGEN_COMPUTADO))

    def test_manual_config_y_legacy_prior_no_son_soporte_economico(self):
        for origen in (me.ORIGEN_MANUAL, me.ORIGEN_LEGACY_PRIOR, me.ORIGEN_PRIOR,
                       me.ORIGEN_ESTATICO, None, "", "FUENTE_INVENTADA"):
            self.assertFalse(me.origin_sostiene_estimacion(origen),
                             f"{origen!r} NO puede sostener una cifra")

    def test_vocabulario_de_origenes_coincide_con_el_producto(self):
        self.assertEqual(me.ORIGEN_EXTERNO, "EXTERNAL_SOURCE")
        self.assertEqual(me.ORIGEN_COMPUTADO, "COMPUTED_FROM_SOURCES")
        self.assertEqual(me.ORIGEN_MANUAL, "MANUAL_CONFIG")
        self.assertEqual(me.ORIGEN_ESTATICO, "STATIC_REFERENCE")
        self.assertEqual(me.ORIGEN_PRIOR, "MODEL_PRIOR")
        self.assertEqual(me.ORIGEN_LEGACY_PRIOR, "LEGACY_MODEL_PRIOR")
        self.assertEqual(me.ORIGENES_HABILITANTES, {"EXTERNAL_SOURCE",
                                                    "COMPUTED_FROM_SOURCES"})
        self.assertTrue(me.ORIGENES_NO_HABILITANTES
                        & {"MANUAL_CONFIG", "LEGACY_MODEL_PRIOR", "MODEL_PRIOR"})


# ══════════════════════════════════════════════════════════════════════════════
# 3 · §6 · CONTRATO MarketObservation
# ══════════════════════════════════════════════════════════════════════════════
class TestContratoMarketObservation(unittest.TestCase):

    def test_los_28_campos_pedidos_estan_todos_y_en_orden(self):
        self.assertEqual(me.CAMPOS_MARKET_OBSERVATION, (
            "observation_id", "source_id", "origin", "listing_or_record_id", "queried_at",
            "effective_date", "city", "neighborhood", "sector", "latitude", "longitude",
            "property_type", "regime", "area_m2", "bedrooms", "bathrooms", "parking",
            "estrato", "asking_price", "transaction_price", "price_per_m2",
            "distance_to_subject_m", "area_difference_pct", "typology_match",
            "location_match", "freshness_days", "source_reliability", "evidence_hash",
        ))
        self.assertEqual(len(me.CAMPOS_MARKET_OBSERVATION), 28)
        # El dict del contrato publica EXACTAMENTE esos campos.
        d = _obs("O-1").to_dict()
        self.assertEqual(tuple(d.keys()), me.CAMPOS_MARKET_OBSERVATION)

    def test_desconocidos_viajan_en_none_y_se_declaran(self):
        o = _obs("O-1")
        self.assertEqual(len(o.campos_desconocidos()), 25)
        for campo in me.CAMPOS_MARKET_OBSERVATION:
            if campo in ("observation_id", "source_id", "origin"):
                continue
            self.assertIsNone(getattr(o, campo),
                              f"{campo} debe quedar en None si no se observó")
        self.assertEqual(o.campos_conocidos(), ("observation_id", "source_id", "origin"))

    def test_ningun_valor_inventado_price_per_m2_no_se_deriva(self):
        """Con precio y área presentes, `price_per_m2` sigue siendo None si no se observó."""
        o = _obs("O-1", asking_price=360_000_000.0, area_m2=60.0)
        self.assertIsNone(o.price_per_m2,
                          "el constructor NO puede derivar price_per_m2: sería inventar")

    def test_ningun_valor_inventado_no_se_copian_campos_del_sujeto(self):
        """El constructor no copia sector/ciudad/régimen del sujeto: no se rellena nada."""
        o = _obs("O-1", sector=None, city=None, regime=None, estrato=None)
        for campo in ("city", "neighborhood", "sector", "regime", "estrato",
                      "property_type", "source_reliability"):
            self.assertIsNone(getattr(o, campo))

    def test_identidad_obligatoria(self):
        for campo in ("observation_id", "source_id", "origin"):
            kw = {"observation_id": "O", "source_id": "S", "origin": me.ORIGEN_EXTERNO}
            kw[campo] = "" if campo != "origin" else ""
            with self.assertRaises(ValueError):
                me.MarketObservation(**kw)

    def test_origen_desconocido_se_rechaza(self):
        with self.assertRaises(ValueError):
            _obs("O-1", origin="INVENTADO")

    def test_un_no_dato_no_se_representa_con_cero_ni_negativo(self):
        with self.assertRaises(ValueError):
            _obs("O-1", area_m2=0)
        with self.assertRaises(ValueError):
            _obs("O-1", asking_price=-1)
        with self.assertRaises(ValueError):
            _obs("O-1", price_per_m2=0.0)

    def test_tipos_invalidos_se_rechazan(self):
        with self.assertRaises(ValueError):
            _obs("O-1", area_m2="60")           # texto no es un número observado
        with self.assertRaises(ValueError):
            _obs("O-1", typology_match=1)        # 1 no es True
        with self.assertRaises(ValueError):
            _obs("O-1", location_match="si")

    def test_unknown_no_es_false_en_los_booleanos(self):
        o = _obs("O-1")
        self.assertIsNone(o.typology_match)
        self.assertIsNone(o.location_match)
        self.assertIsNot(o.typology_match, False)

    def test_mapeo_desde_registros_convierte_centinelas_en_none(self):
        registros = [{"observation_id": "R-1", "sector": "Miramar", "estrato": "N/A",
                      "area_m2": 60.0, "bathrooms": "sin dato", "asking_price": None,
                      "latitude": "null"}]
        obs = me.observaciones_desde_registros(registros, source_id="S1",
                                               origin=me.ORIGEN_EXTERNO)
        self.assertEqual(len(obs), 1)
        o = obs[0]
        self.assertEqual(o.observation_id, "R-1")
        self.assertEqual(o.sector, "Miramar")
        self.assertEqual(o.area_m2, 60.0)
        for campo in ("estrato", "bathrooms", "asking_price", "latitude",
                      "price_per_m2", "typology_match"):
            self.assertIsNone(getattr(o, campo), f"{campo} debe quedar en None")
        # Un registro sin observation_id recibe uno determinista, no aleatorio.
        sin_id = me.observaciones_desde_registros([{"sector": SECTOR}], source_id="S2",
                                                  origin=me.ORIGEN_EXTERNO)
        self.assertEqual(sin_id[0].observation_id, "S2-0001")
        with self.assertRaises(ValueError):
            me.observaciones_desde_registros([{"x": 1}], source_id="S", origin="INVENTADO")

    def test_hash_del_registro_es_determinista_y_no_se_autoincluye(self):
        o = _obs("O-1", **_comparable())
        h1 = me.calcular_evidence_hash(o)
        self.assertEqual(h1, me.calcular_evidence_hash(o))
        self.assertEqual(len(h1), 64)
        con_hash = me.MarketObservation(**{**o.to_dict(), "evidence_hash": "x" * 64})
        self.assertEqual(me.calcular_evidence_hash(con_hash), h1,
                         "evidence_hash no puede formar parte de su propio cálculo")
        self.assertEqual(con_hash.con_evidence_hash().evidence_hash, "x" * 64,
                         "un hash ya declarado no se sobrescribe")
        self.assertEqual(o.con_evidence_hash().evidence_hash, h1)
        with self.assertRaises(TypeError):
            me.calcular_evidence_hash({"no": "es observación"})


# ══════════════════════════════════════════════════════════════════════════════
# 4 · §7 · ComparableScore
# ══════════════════════════════════════════════════════════════════════════════
class TestComparableScoreExplicable(unittest.TestCase):

    def test_comparable_completo_y_compatible_se_acepta_con_motivo(self):
        s = _score(_obs("C-1", **_comparable()))
        self.assertEqual(s.veredicto, me.VEREDICTO_ACEPTADO)
        self.assertEqual(s.version_reglas, me.VERSION_REGLAS_COMPARABLE)
        self.assertEqual(s.dimensiones_desconocidas, ())
        self.assertTrue(s.motivos)
        for m in s.motivos:
            self.assertTrue(m["regla"] and m["resultado"] and m["detalle"])

    def test_tipologia_distinta_se_rechaza_con_motivo(self):
        s = _score(_obs("C-1", **_comparable(typology_match=False)))
        self.assertEqual(s.veredicto, me.VEREDICTO_RECHAZADO)
        detalle = " ".join(m["detalle"] for m in s.motivos)
        self.assertIn("tipología", detalle.lower())

    def test_ubicacion_lejana_se_rechaza(self):
        s = _score(_obs("C-1", **_comparable(distance_to_subject_m=9000.0, sector="Riomar")))
        self.assertEqual(s.veredicto, me.VEREDICTO_RECHAZADO)
        self.assertEqual(s.location_similarity, me.SIMILITUD_BAJA)

    def test_regimen_distinto_se_rechaza(self):
        s = _score(_obs("C-1", **_comparable(regime="Lote individual")))
        self.assertEqual(s.veredicto, me.VEREDICTO_RECHAZADO)
        self.assertEqual(s.regime_similarity, me.SIMILITUD_BAJA)

    def test_area_incompatible_se_rechaza(self):
        s = _score(_obs("C-1", **_comparable(area_difference_pct=55.0)))
        self.assertEqual(s.veredicto, me.VEREDICTO_RECHAZADO)
        self.assertEqual(s.area_similarity, me.SIMILITUD_BAJA)

    def test_dato_vencido_se_rechaza(self):
        s = _score(_obs("C-1", **_comparable(freshness_days=400)))
        self.assertEqual(s.veredicto, me.VEREDICTO_RECHAZADO)
        self.assertEqual(s.freshness, me.SIMILITUD_BAJA)

    def test_desconocido_no_se_presume_coincidente(self):
        """Sin distancia ni sector declarados, NUNCA puede ser ACCEPTED."""
        s = _score(_obs("C-1", **_comparable(distance_to_subject_m=None, sector=None)))
        self.assertEqual(s.veredicto, me.VEREDICTO_DEBIL)
        self.assertIn("location_similarity", s.dimensiones_desconocidas)
        self.assertNotIn("location_similarity", s.dimensiones_conocidas)
        detalle = " ".join(m["detalle"] for m in s.motivos)
        self.assertIn("no se observó", detalle)

    def test_desconocido_en_critica_tampoco_acepta_con_area_o_frescura(self):
        for kw in ({"area_difference_pct": None}, {"freshness_days": None},
                   {"regime": None}, {"typology_match": None}):
            s = _score(_obs("C-1", **_comparable(**kw)))
            self.assertEqual(s.veredicto, me.VEREDICTO_DEBIL, f"{kw} debe dar WEAK")
            self.assertTrue(s.dimensiones_desconocidas)

    def test_dimension_en_media_da_weak_explicado(self):
        s = _score(_obs("C-1", **_comparable(distance_to_subject_m=900.0)))
        self.assertEqual(s.veredicto, me.VEREDICTO_DEBIL)
        self.assertEqual(s.location_similarity, me.SIMILITUD_MEDIA)
        self.assertTrue(any("MEDIA" in m["detalle"] for m in s.motivos))

    def test_opcionales_solo_si_se_conocen_y_nunca_deciden(self):
        sin_parking = _score(_obs("C-1", **_comparable()))
        con_parking = _score(_obs("C-2", **_comparable(parking=1)))
        sin_parqueadero = _score(_obs("C-3", **_comparable(parking=0)))
        self.assertEqual(sin_parking.veredicto, me.VEREDICTO_ACEPTADO)
        self.assertEqual(con_parking.veredicto, sin_parking.veredicto)
        self.assertEqual(sin_parqueadero.veredicto, sin_parking.veredicto)
        self.assertIsNone(sin_parking.parking_similarity)
        self.assertEqual(con_parking.parking_similarity, me.SIMILITUD_ALTA)
        self.assertEqual(sin_parqueadero.parking_similarity, me.SIMILITUD_BAJA)
        # floor/condition se puntúan sólo si la prueba los declara.
        con_piso = _score(_obs("C-4", **_comparable()), floor=8, condition="BUENO")
        self.assertEqual(con_piso.veredicto, me.VEREDICTO_ACEPTADO)
        self.assertIsNotNone(con_piso.floor_similarity)
        self.assertIsNotNone(con_piso.condition_similarity)
        self.assertIsNone(sin_parking.floor_similarity)

    def test_un_veredicto_sin_motivo_no_es_admisible(self):
        with self.assertRaises(ValueError):
            me.ComparableScore(comparable_id="C-1", veredicto=me.VEREDICTO_ACEPTADO,
                               motivos=[])

    def test_veredicto_fuera_del_vocabulario_se_rechaza(self):
        with self.assertRaises(ValueError):
            me.ComparableScore(comparable_id="C-1", veredicto="EXCELENTE",
                               motivos=[{"regla": "x", "resultado": "y", "detalle": "z"}])

    def test_etiqueta_de_similitud_invalida_se_rechaza(self):
        with self.assertRaises(ValueError):
            me.ComparableScore(comparable_id="C-1", location_similarity="PERFECTA",
                               motivos=[{"regla": "x", "resultado": "y", "detalle": "z"}])

    def test_umbrales_declarados_y_versiones_visibles(self):
        self.assertEqual(me.UMBRAL_DISTANCIA_ALTA_M, 500.0)
        self.assertEqual(me.UMBRAL_DISTANCIA_MEDIA_M, 1500.0)
        self.assertEqual(me.UMBRAL_AREA_ALTA_PCT, 10.0)
        self.assertEqual(me.UMBRAL_AREA_MEDIA_PCT, 25.0)
        self.assertEqual(me.UMBRAL_FRESCURA_ALTA_DIAS, 90)
        self.assertEqual(me.UMBRAL_FRESCURA_MEDIA_DIAS, 180)
        self.assertEqual(me.VEREDICTOS, ("ACCEPTED", "WEAK", "REJECTED"))
        self.assertEqual(me.VERSION_REGLAS_COMPARABLE, "comparable-score/1.0.0")

    def test_helpers_de_similitud_devuelven_none_sin_dato(self):
        self.assertIsNone(me.similitud_area(None))
        self.assertIsNone(me.similitud_tipologia(None))
        self.assertIsNone(me.nivel_frescura(None))
        self.assertIsNone(me.similitud_localizacion(None))
        self.assertIsNone(me.similitud_regimen(None, REGIMEN_PH))
        self.assertIsNone(me.similitud_regimen(REGIMEN_PH, None))
        self.assertEqual(me.similitud_tipologia(True), me.SIMILITUD_ALTA)
        self.assertEqual(me.similitud_tipologia(False), me.SIMILITUD_BAJA)


# ══════════════════════════════════════════════════════════════════════════════
# 5 · §8 · CONTROL DE OUTLIERS
# ══════════════════════════════════════════════════════════════════════════════
class TestControlDeOutliers(unittest.TestCase):

    def _set(self):
        return [
            _obs("OK-1", **_comparable(evidence_hash="h-ok")),
            _obs("DUP-1", **_comparable(evidence_hash="h-dup")),   # duplica a OK-1 (L-REF)
            _obs("PRECIO-1", **_comparable(listing_or_record_id="L-P", price_per_m2=25_000_000.0)),
            _obs("AREA-1", **_comparable(listing_or_record_id="L-A", area_difference_pct=80.0)),
            _obs("TIPO-1", **_comparable(listing_or_record_id="L-T", typology_match=False)),
            _obs("SECTOR-1", **_comparable(listing_or_record_id="L-S", sector="Riomar")),
            _obs("VIEJO-1", **_comparable(listing_or_record_id="L-V", freshness_days=500)),
            _obs("SINPRECIO-1", observation_id="SINPRECIO-1", source_id="FIJO_PRUEBA",
                 origin=me.ORIGEN_EXTERNO, listing_or_record_id="L-X", sector=SECTOR,
                 area_difference_pct=2.0, typology_match=True, regime=REGIMEN_PH,
                 freshness_days=10),
        ]

    def test_cada_categoria_de_outlier_se_excluye_con_su_motivo(self):
        obs = self._set()
        r = me.detectar_outliers(obs, sector_sujeto=SECTOR, banda_m2=[5_000_000, 9_000_000])
        codigos = {e["observation_id"]: set(e["exclusion_codes"]) for e in r["excluidas"]}
        self.assertIn(me.EXCLUSION_DUPLICADO, codigos["DUP-1"])
        self.assertIn(me.EXCLUSION_PRECIO_M2_INCOMPATIBLE, codigos["PRECIO-1"])
        self.assertIn(me.EXCLUSION_AREA_INCOMPATIBLE, codigos["AREA-1"])
        self.assertIn(me.EXCLUSION_TIPOLOGIA_DISTINTA, codigos["TIPO-1"])
        self.assertIn(me.EXCLUSION_SECTOR_INCORRECTO, codigos["SECTOR-1"])
        self.assertIn(me.EXCLUSION_DATO_VENCIDO, codigos["VIEJO-1"])
        self.assertIn(me.EXCLUSION_SIN_PRECIO, codigos["SINPRECIO-1"])
        for e in r["excluidas"]:
            self.assertTrue(e["exclusion_reason"].strip(),
                            "toda exclusión lleva motivo, sin excepción")
            self.assertTrue(e["conservada_para_auditoria"])
            self.assertTrue(set(e["exclusion_codes"]) <= set(me.CODIGOS_EXCLUSION))

    def test_nada_se_borra_en_silencio_la_suma_reconstruye_la_entrada(self):
        obs = self._set()
        r = me.detectar_outliers(obs, sector_sujeto=SECTOR)
        self.assertTrue(r["integridad"])
        self.assertEqual(r["total_entrada"], len(obs))
        self.assertEqual(r["total_aceptadas"] + r["total_excluidas"], len(obs))
        self.assertEqual(len(r["aceptadas"]) + len(r["excluidas"]), len(obs))
        # Todo excluido sigue siendo recuperable por id desde el resultado.
        ids_entrada = {o.observation_id for o in obs}
        ids_salida = ({o.observation_id for o in r["aceptadas"]}
                      | {e["observation_id"] for e in r["excluidas"]})
        self.assertEqual(ids_entrada, ids_salida)
        self.assertIn("silencio", r["declaracion"])

    def test_duplicado_detectado_y_apunta_al_conservado(self):
        obs = self._set()
        r = me.detectar_outliers(obs, sector_sujeto=SECTOR)
        dup = [e for e in r["excluidas"] if e["observation_id"] == "DUP-1"][0]
        self.assertEqual(dup["duplica_a"], "OK-1")
        self.assertIn("duplica a OK-1", dup["exclusion_reason"])
        # El conservado sobrevive: el duplicado no borra al original.
        self.assertIn("OK-1", [o.observation_id for o in r["aceptadas"]])

    def test_duplicado_por_hash_de_contenido(self):
        gemelos = [_obs("H-1", **_comparable(evidence_hash="mismo")),
                   _obs("H-2", **_comparable(listing_or_record_id="OTRO",
                                             evidence_hash="mismo"))]
        r = me.detectar_outliers(gemelos, sector_sujeto=SECTOR)
        self.assertEqual([o.observation_id for o in r["aceptadas"]], ["H-1"])
        self.assertEqual(r["excluidas"][0]["exclusion_codes"], [me.EXCLUSION_DUPLICADO])

    def test_sin_banda_declarada_se_usa_la_mediana_y_se_dice(self):
        precios = [6_000_000.0, 6_100_000.0, 5_900_000.0, 40_000_000.0]
        obs = [_obs(f"P-{i}", **_comparable(listing_or_record_id=f"L-{i}",
                                            price_per_m2=p))
               for i, p in enumerate(precios)]
        r = me.detectar_outliers(obs, sector_sujeto=SECTOR)
        self.assertEqual(r["metodo_precio"], "MEDIANA_ROBUSTA")
        self.assertIsNone(r["banda_declarada_m2"])
        self.assertIn(me.EXCLUSION_PRECIO_M2_EXTREMO, r["excluidas"][0]["exclusion_codes"])
        self.assertEqual(r["total_aceptadas"], 3)

    def test_con_banda_declarada_se_usa_la_banda(self):
        obs = [_obs("B-1", **_comparable(listing_or_record_id="L-1",
                                         price_per_m2=1_000_000.0))]
        r = me.detectar_outliers(obs, sector_sujeto=SECTOR, banda_m2=[5_000_000, 9_000_000],
                                 banda_origen="banda declarada de prueba")
        self.assertEqual(r["metodo_precio"], "BANDA_DECLARADA")
        self.assertEqual(r["banda_declarada_m2"], [5_000_000, 9_000_000])
        self.assertIn("banda declarada", r["excluidas"][0]["exclusion_reason"])

    def test_con_pocos_precios_no_se_aplica_regla_robusta(self):
        obs = [_obs("X-1", **_comparable(listing_or_record_id="L-1",
                                         price_per_m2=99_000_000.0))]
        r = me.detectar_outliers(obs, sector_sujeto=SECTOR)
        self.assertEqual(r["metodo_precio"], "SIN_REGLA_DE_PRECIO")
        self.assertEqual(r["total_aceptadas"], 1,
                         "sin base estadística no se excluye por extremo")

    def test_sector_declarado_distinto_del_sujeto_excluye(self):
        r = me.detectar_outliers([_obs("S-1", **_comparable(sector="Alto Prado"))],
                                 sector_sujeto=SECTOR)
        self.assertEqual(r["excluidas"][0]["exclusion_codes"],
                         [me.EXCLUSION_SECTOR_INCORRECTO])

    def test_entradas_invalidas_se_rechazan(self):
        with self.assertRaises(TypeError):
            me.detectar_outliers("no es una lista")
        with self.assertRaises(TypeError):
            me.detectar_outliers([{"no": "es observación"}])
        with self.assertRaises(ValueError):
            me.detectar_outliers([_obs("O-1", **_comparable())], banda_m2=[1, 2, 3])

    def test_lista_vacia_no_inventa_nada(self):
        r = me.detectar_outliers([], sector_sujeto=SECTOR)
        self.assertEqual(r["total_entrada"], 0)
        self.assertEqual(r["aceptadas"], [])
        self.assertEqual(r["excluidas"], [])
        self.assertTrue(r["integridad"])
        self.assertEqual(r["metodo_precio"], "SIN_REGLA_DE_PRECIO")

    def test_alias_del_contrato_y_version(self):
        r = me.detectar_outliers([])
        self.assertIs(r["excluded_comparables"], r["excluidas"])
        self.assertEqual(r["version_reglas"], "comparable-outlier-control/1.0.0")


# ══════════════════════════════════════════════════════════════════════════════
# 6 · §26 · BLOQUEO POR PROPÓSITO
# ══════════════════════════════════════════════════════════════════════════════
class TestBlockingPorProposito(unittest.TestCase):

    def test_los_dos_propositos_estan_separados(self):
        t = me.blocking_por_proposito()
        self.assertEqual(t["propositos"], ["ESTIMACION", "DECISION"])
        self.assertEqual(t["version"], "blocking-por-proposito/1.0.0")
        for attr, regla in t["atributos"].items():
            self.assertIn("required_for_estimation", regla, attr)
            self.assertIn("required_for_decision", regla, attr)
            self.assertIsInstance(regla["required_for_estimation"], bool)
            self.assertIsInstance(regla["required_for_decision"], bool)
            self.assertTrue(str(regla.get("motivo") or "").strip(), attr)
        # Las cuatro agrupaciones son coherentes con la tabla.
        for attr in t["solo_decision"]:
            self.assertTrue(t["atributos"][attr]["required_for_decision"])
            self.assertFalse(t["atributos"][attr]["required_for_estimation"])
        for attr in t["ambos"]:
            self.assertTrue(t["atributos"][attr]["required_for_estimation"])
            self.assertTrue(t["atributos"][attr]["required_for_decision"])
        self.assertTrue(t["solo_decision"], "debe haber atributos exigibles sólo para decidir")

    def test_altura_pot_es_critica_para_decidir_y_no_para_estimar(self):
        self.assertFalse(me.requerido_para("altura_maxima_pot", me.PROPOSITO_ESTIMACION))
        self.assertTrue(me.requerido_para("altura_maxima_pot", me.PROPOSITO_DECISION))
        self.assertIn("altura_maxima_pot", me.blocking_por_proposito()["solo_decision"])
        self.assertIn("CRÍTICA para urbanismo",
                      me.blocking_por_proposito()["declaracion_altura_pot"])
        self.assertIn("NO es necesariamente necesaria",
                      me.blocking_por_proposito()["declaracion_altura_pot"])

    def test_pot_source_unavailable_no_bloquea_por_si_solo_la_estimacion(self):
        entradas = {
            "altura_maxima_pot": {"estado": "SOURCE_UNAVAILABLE", "value": None},
            "tratamiento_pot": {"estado": "SOURCE_UNAVAILABLE", "value": None},
            "edificabilidad_pot": {"estado": "SOURCE_UNAVAILABLE", "value": None},
            "uso_pot": {"estado": "NOT_SUPPORTED", "value": None},
            # lo que la estimación SÍ exige, presente:
            "area_m2": 58.75, "regimen_ph": REGIMEN_PH, "tipologia": "Unidad PH",
            "barrio": SECTOR, "coordenadas": {"lat": 11.006, "lon": -74.837},
            "sector_mercado": SECTOR, "estrato": "4",
        }
        r = me.evaluar_blocking_por_proposito(entradas)
        self.assertFalse(r["estimacion"]["bloqueado"],
                         "un POT SOURCE_UNAVAILABLE no puede bloquear la estimación")
        self.assertTrue(r["decision"]["bloqueado"],
                        "el POT ausente sí bloquea la DECISIÓN")
        no_bloqueantes = r["estimacion"]["atributos_ausentes_no_bloqueantes"]
        for attr in ("altura_maxima_pot", "tratamiento_pot", "edificabilidad_pot", "uso_pot"):
            self.assertIn(attr, no_bloqueantes)
            self.assertIn(attr, [b["atributo"] for b in r["decision"]["bloqueos"]])
            self.assertFalse([b for b in r["decision"]["bloqueos"]
                              if b["atributo"] == attr][0]["bloquea_estimacion"])
        self.assertIn("NO bloquea por sí solo", r["regla_pot"])

    def test_falta_de_area_si_bloquea_la_estimacion(self):
        r = me.evaluar_blocking_por_proposito({
            "area_m2": None, "tipologia": "Unidad PH", "regimen_ph": REGIMEN_PH,
            "barrio": SECTOR, "soporte_de_mercado_utilizable": {"estado": "SOURCE_UNAVAILABLE",
                                                                "value": None},
        })
        self.assertTrue(r["estimacion"]["bloqueado"])
        bloqueados = {b["atributo"] for b in r["estimacion"]["bloqueos"]}
        self.assertIn("area_m2", bloqueados)
        self.assertIn("soporte_de_mercado_utilizable", bloqueados)

    def test_sin_soporte_de_mercado_la_estimacion_si_se_bloquea(self):
        r = me.evaluar_blocking_por_proposito({
            "area_m2": 58.75, "tipologia": "Unidad PH", "regimen_ph": REGIMEN_PH,
            "barrio": SECTOR, "estrato": "4", "coordenadas": {"lat": 1.0, "lon": 2.0},
            "sector_mercado": SECTOR, "tasa_mercado_m2": None,
        })
        self.assertTrue(r["estimacion"]["bloqueado"])
        self.assertIn("tasa_mercado_m2",
                      {b["atributo"] for b in r["estimacion"]["bloqueos"]})

    def test_comparables_ausentes_no_son_requisito_de_estimacion(self):
        """Coherente con la §5: sin LEVEL 1 no se cierra; el requisito es el SOPORTE."""
        self.assertFalse(me.requerido_para("comparables_directos",
                                           me.PROPOSITO_ESTIMACION))
        self.assertTrue(me.requerido_para("comparables_directos",
                                          me.PROPOSITO_DECISION))
        self.assertTrue(me.requerido_para("soporte_de_mercado_utilizable",
                                          me.PROPOSITO_ESTIMACION))

    def test_priors_no_son_requisito_de_ningun_proposito(self):
        self.assertFalse(me.requerido_para("model_priors", me.PROPOSITO_ESTIMACION))
        self.assertFalse(me.requerido_para("model_priors", me.PROPOSITO_DECISION))
        self.assertIn("model_priors", me.blocking_por_proposito()["ninguno"])

    def test_atributo_desconocido_no_bloquea_y_proposito_invalido_falla(self):
        self.assertFalse(me.requerido_para("atributo_que_no_existe",
                                           me.PROPOSITO_ESTIMACION))
        with self.assertRaises(ValueError):
            me.requerido_para("area_m2", "PROPOSITO_INVENTADO")
        with self.assertRaises(TypeError):
            me.evaluar_blocking_por_proposito(["no", "es", "un", "mapping"])

    def test_no_aplica_se_considera_ausente_y_se_declara(self):
        r = me.evaluar_blocking_por_proposito({
            "area_m2": {"estado": "SOURCE_UNAVAILABLE", "value": None},
            "barrio": {"estado": "NOT_SUPPORTED", "value": None},
        })
        self.assertIn("area_m2", r["atributos_ausentes"])
        self.assertIn("barrio", r["atributos_ausentes"])
        self.assertTrue(r["estimacion"]["bloqueado"])


# ══════════════════════════════════════════════════════════════════════════════
# 7 · GUARDAS DE DOCTRINA SOBRE LOS ARTEFACTOS REALES 040-646406
# ══════════════════════════════════════════════════════════════════════════════
class TestDoctrinaSobreArtefactosReales(unittest.TestCase):

    def test_el_pack_no_declara_ninguna_fuente_de_mercado(self):
        registro = json.loads(REGISTRO.read_text(encoding="utf-8"))
        fuentes = registro["sources"]
        self.assertNotIn("LONJA_MARKET_BAQ", fuentes,
                         "el identificador histórico NO puede estar en el registro vigente")
        roles = {(v or {}).get("product_role") for v in fuentes.values()
                 if isinstance(v, dict)}
        self.assertNotIn("CORE_MARKET", roles,
                         "si aparece CORE_MARKET hay que revisar la auditoría de mercado")
        retiradas = registro["no_fuentes_institucionales"]["aliados"]
        self.assertFalse(retiradas["LONJA_BAQ"]["es_fuente_de_datos"])
        self.assertFalse(retiradas["LONJA_BAQ"]["aporta_datos_a_dictus"])
        self.assertTrue(retiradas["LONJA_BAQ"]["retirada_del_registro"])
        self.assertEqual(retiradas["LONJA_BAQ"]["product_role"], "NOT_A_SOURCE")

    def test_la_matriz_de_cobertura_declara_el_mercado_ausente(self):
        filas = list(csv.DictReader(COVERAGE.open(encoding="utf-8-sig")))
        mercado = [f for f in filas if f["row"] == "18-mercado"]
        self.assertEqual(len(mercado), 1)
        self.assertEqual(mercado[0]["status"], "SOURCE_UNAVAILABLE")
        self.assertIn("SIN FUENTE DE MERCADO", mercado[0]["value_or_result"])
        filas_acq = list(csv.DictReader(ACQUISITION.open(encoding="utf-8-sig")))
        dominio = [f for f in filas_acq if f["domain"] == "mercado"]
        self.assertEqual(len(dominio), 1)
        self.assertEqual(dominio[0]["status"], "NOT_SUPPORTED")
        self.assertEqual(dominio[0]["product_role"], "CORE_MARKET")

    def test_el_golden_no_uso_ninguna_tasa_de_mercado(self):
        rs = json.loads(RUN_STATE.read_text(encoding="utf-8"))
        vs = rs["valuation_state"]
        self.assertIsNone(vs["value_m2"])
        self.assertEqual(vs["consolidado"], 0)
        self.assertFalse(vs["metodologia_aplica"])
        self.assertFalse(vs["origin_gate"])
        self.assertEqual(vs["origin"], "MANUAL_CONFIG")
        self.assertFalse(me.origin_sostiene_estimacion(vs["origin"]))
        for nombre, origen in vs["origins"].items():
            self.assertFalse(me.origin_sostiene_estimacion(origen),
                             f"{nombre}={origen} no puede sostener la estimación")
        # El sector sí resuelve: el nivel 1-3 está vacío, el mapeo no.
        self.assertEqual(rs["market_context"]["sector_metodologico"]["match_type"], "EXACT")

    def test_la_vigencia_declarada_esta_vencida_y_por_eso_no_se_presenta(self):
        rs = json.loads(RUN_STATE.read_text(encoding="utf-8"))
        from datetime import date
        corrida = date.fromisoformat(rs["generated_at"][:10])
        hasta = date.fromisoformat("2026-08-31")
        self.assertGreater(corrida, hasta,
                           "la tabla declara vigencia hasta 2026-08-31 y la corrida es "
                           "posterior: el valor está VENCIDO")

    def test_no_se_restaura_el_valor_historico_prohibido(self):
        """`399.500.000` puede seguir apareciendo en la traza histórica, NUNCA como cifra.

        La coherencia histórica del Golden SÍ registra que versiones anteriores imprimieron
        `$ 399.500.000` — eso es evidencia del cambio y no se borra. Lo que no puede volver
        es la CIFRA EMITIDA: la valoración de esta corrida está vacía y en cero.
        """
        rs = json.loads(RUN_STATE.read_text(encoding="utf-8"))
        vs = rs["valuation_state"]
        for campo in ("value_m2", "consolidado", "banda_baja", "banda_alta",
                      "m1", "m2", "m3"):
            valor = vs[campo]
            self.assertIn(valor, (None, 0), f"{campo}={valor!r} no puede reponer la cifra")
            texto = json.dumps(vs, ensure_ascii=False)
            self.assertNotIn("399.500.000", texto,
                             "valuation_state no puede reponer la cifra histórica")
        # El manifest tampoco la emite como valoración.
        mf = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertNotIn("399.500.000",
                         json.dumps(mf["modelo"]["valuation"], ensure_ascii=False))
        self.assertNotIn("399.500.000",
                         json.dumps(mf["evidence_manifest"], ensure_ascii=False))

    def test_auditoria_de_entradas_lleva_exactamente_los_11_campos(self):
        if not AUDIT_JSON.exists():
            self.skipTest("el artefacto de auditoría no está generado en este entorno")
        d = json.loads(AUDIT_JSON.read_text(encoding="utf-8"))
        esperados = ["attribute", "value", "origin", "source_id", "source_class",
                     "queried_at", "effective_date", "freshness", "provenance",
                     "usable_for_estimation", "reason"]
        self.assertTrue(d["entradas"])
        for e in d["entradas"]:
            self.assertEqual(list(e.keys()), esperados, e.get("attribute"))
            self.assertIsInstance(e["usable_for_estimation"], bool)
            self.assertTrue(str(e["reason"]).strip(), e["attribute"])
            if e["usable_for_estimation"]:
                self.assertIsNotNone(e["value"], e["attribute"])
                self.assertTrue(me.origin_sostiene_estimacion(e["origin"]), e["attribute"])
        self.assertEqual(d["conteo"]["total_inputs"], len(d["entradas"]))
        self.assertEqual(d["conteo"]["observaciones_de_mercado_reales"], 0)
        self.assertEqual(
            d["conteo"]["usable_for_estimation_true"],
            sum(1 for e in d["entradas"] if e["usable_for_estimation"]))
        # El inventario cubre los inputs que pide la misión.
        attrs = {e["attribute"] for e in d["entradas"]}
        for exigido in ("identidad_unidad", "matricula", "nupre", "numero_predial",
                        "area_construida_m2", "regimen_ph", "tipologia", "barrio",
                        "localidad", "estrato", "coordenadas", "sector_mercado",
                        "observaciones_de_mercado_comparables", "precios_m2_observados",
                        "rentas_observadas", "costos_observados", "referencias_historicas",
                        "model_priors_declarados"):
            self.assertIn(exigido, attrs)
        # Y declara explícitamente la ausencia de soporte de mercado.
        self.assertEqual(
            d["escalera_evidencia_mercado"]["evaluacion"]["niveles_con_soporte"], [])
        self.assertFalse(
            d["escalera_evidencia_mercado"]["evaluacion"]["implica_closed"])

    def test_matriz_de_evidencia_con_las_ocho_columnas_y_sin_uso(self):
        if not MATRIX_CSV.exists():
            self.skipTest("la matriz de evidencia no está generada en este entorno")
        filas = list(csv.DictReader(MATRIX_CSV.open(encoding="utf-8")))
        self.assertTrue(filas)
        self.assertEqual(list(filas[0].keys()),
                         ["fuente", "nivel_escalera", "status", "valor", "origin",
                          "provenance", "hash", "usada"])
        for f in filas:
            self.assertIn(f["nivel_escalera"], me.NIVELES_EVIDENCIA_MERCADO)
            self.assertEqual(f["usada"], "NO",
                             f"{f['fuente']}: nada de mercado se usó en esta corrida")
            self.assertTrue(f["hash"], f"{f['fuente']}: falta el hash de procedencia")

    def test_market_evidence_no_introduce_la_lonja_en_logica_activa(self):
        """Guarda de doctrina: ni un literal de cadena ni un identificador del módulo."""
        fuente = (ROOT / "api" / "market_evidence.py").read_text(encoding="utf-8")
        arbol = ast.parse(fuente)
        ofensas = []
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
                if "lonja" in nodo.value.lower():
                    ofensas.append(nodo.value[:60])
            elif isinstance(nodo, ast.Name) and "lonja" in nodo.id.lower():
                ofensas.append(nodo.id)
            elif isinstance(nodo, ast.Attribute) and "lonja" in nodo.attr.lower():
                ofensas.append(nodo.attr)
        self.assertEqual(ofensas, [],
                         "la lonja NO puede entrar en la lógica activa del contrato de mercado")


if __name__ == "__main__":
    unittest.main(verbosity=2)

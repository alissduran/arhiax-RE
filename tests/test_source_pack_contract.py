# -*- coding: utf-8 -*-
"""BARRANQUILLA SOURCE PACK v1.0 — pruebas BLOQUEANTES del contrato de fuentes (§32).

Cubren, sin red, las garantías que no pueden depender de que una fuente esté viva:
ausencia ≠ no coincidencia, binding canónico (nunca `features[0]`), destino catastral ≠
uso POT, altura normativa ≠ altura física, precedencia explícita de capas de riesgo y
procedencia en TODOS los resultados.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))

import dictus_sources as ds  # noqa: E402


def _fuente(**over):
    f = {"source_id": "TEST_FUENTE", "source_name": "Fuente de prueba",
         "institution": "Alcaldía de prueba", "authority_class": ds.AUTORITATIVA_OFICIAL,
         "service": "ArcGIS REST", "layer_id": 3, "query_method": "query",
         "failure_semantics": "HTTP!=200 o error ArcGIS -> SOURCE_UNAVAILABLE",
         "license_or_terms": "datos abiertos", "can_persist_raw": True, "enabled": True,
         "version_or_vigency": "vigente", "precedence": "CURRENT_OFFICIAL"}
    f.update(over)
    return f


class TestEstadosYAusencia(unittest.TestCase):
    """I · SOURCE_UNAVAILABLE nunca produce NO_MATCH."""

    def test_fuente_caida_no_es_sin_coincidencia(self):
        res = ds.consultar(_fuente(), lambda: None)
        self.assertEqual(res["status"], ds.FUENTE_NO_DISPONIBLE)
        self.assertNotEqual(res["status"], ds.SIN_COINCIDENCIA)

    def test_error_de_consulta_es_query_failed(self):
        def _explota():
            raise TimeoutError("sin respuesta")
        res = ds.consultar(_fuente(), _explota)
        self.assertEqual(res["status"], ds.CONSULTA_FALLIDA)
        self.assertNotEqual(res["status"], ds.SIN_COINCIDENCIA)

    def test_fuente_deshabilitada_es_not_supported(self):
        res = ds.consultar(_fuente(enabled=False), lambda: {"features": []})
        self.assertEqual(res["status"], ds.NO_SOPORTADA)

    def test_respuesta_vacia_si_es_no_match(self):
        res = ds.consultar(_fuente(), lambda: {"features": []}, normalizar=lambda c: [])
        self.assertEqual(res["status"], ds.SIN_COINCIDENCIA)
        self.assertEqual(res["result_count"], 0)

    def test_fuente_que_no_puede_afirmar_ausencia(self):
        res = ds.consultar(_fuente(puede_responder_sin_coincidencia=False),
                           lambda: {"features": []}, normalizar=lambda c: [])
        self.assertEqual(res["status"], ds.FUENTE_NO_DISPONIBLE)

    def test_estado_desconocido_cae_en_query_failed(self):
        self.assertEqual(ds.resultado("X", "INVENTADO")["status"], ds.CONSULTA_FALLIDA)
        self.assertEqual(len(ds.ESTADOS), 5)

    def test_todo_resultado_tiene_procedencia(self):
        """O · procedencia y hash en todos los resultados."""
        for crudo in ({"a": 1}, None):
            res = ds.consultar(_fuente(), (lambda c=crudo: c), persistir=False)
            prov = res["provenance"]
            self.assertEqual(prov["source_id"], "TEST_FUENTE")
            self.assertEqual(prov["authority_class"], ds.AUTORITATIVA_OFICIAL)
            self.assertIn("layer_id", prov)
            self.assertIn("query_id", res)
            self.assertIn("queried_at", res)
            self.assertIn("result_count", res)
            self.assertIn("binding_status", res)
            self.assertIn("payload_normalized", res)
        res = ds.consultar(_fuente(), lambda: {"ok": 1}, persistir=False)
        self.assertTrue(res["raw_hash"])


class TestBindingCanonico(unittest.TestCase):
    """C/D · nunca `features[0]`; el predio vecino no autoriza identidad."""

    def setUp(self):
        self.vecino = {"attributes": {"nupre": "AFT-OTRO", "numero_predial": "999",
                                      "direccion": "CALLE 9 # 9 - 9"}}
        self.propio = {"attributes": {"nupre": "AFT0005BOHA", "numero_predial": "0800",
                                      "direccion": "TV 43 # 100 - 50"}}

    def test_orden_de_features_no_decide(self):
        # El predio correcto va SEGUNDO: elegir features[0] daría el vecino.
        r = ds.elegir_predio_canonico([self.vecino, self.propio], nupre="aft0005boha")
        self.assertEqual(r["binding_status"], ds.BINDING_NUPRE)
        self.assertEqual(r["feature"]["nupre"], "AFT0005BOHA")

    def test_numero_predial_exacto(self):
        r = ds.elegir_predio_canonico([self.vecino, self.propio], numero_predial="0800")
        self.assertEqual(r["binding_status"], ds.BINDING_PREDIAL)

    def test_relacion_oficial(self):
        r = ds.elegir_predio_canonico([self.vecino, self.propio], relacionados=["AFT-OTRO"])
        self.assertEqual(r["binding_status"], ds.BINDING_RELACION)

    def test_direccion_ligada(self):
        r = ds.elegir_predio_canonico([self.vecino, self.propio],
                                      direccion_ligada="TV 43 # 100 - 50")
        self.assertEqual(r["binding_status"], ds.BINDING_DIRECCION)

    def test_sin_binding_no_se_elige_nada(self):
        r = ds.elegir_predio_canonico([self.vecino, self.propio], nupre="AFT-INEXISTENTE")
        self.assertIsNone(r["feature"])
        self.assertEqual(r["binding_status"], ds.SIN_BINDING)
        self.assertFalse(ds.identidad_autorizada_por_binding(r["binding_status"]))

    def test_espacial_solo_contexto_no_autoriza_identidad(self):
        self.assertFalse(ds.identidad_autorizada_por_binding(ds.BINDING_ESPACIAL_CONTEXTO))
        self.assertTrue(ds.identidad_autorizada_por_binding(ds.BINDING_NUPRE))


class TestDestinoVsUsoPOT(unittest.TestCase):
    """E/F · destino catastral ≠ uso normativo POT (contrato separado)."""

    def test_dos_fuentes_dos_objetos(self):
        catastro = ds.consultar(_fuente(source_id="CATASTRO_BAQ_PREDIO",
                                        layer_id=100),
                                lambda: {"attributes": {"destinacion_economica":
                                                        "HABITACIONAL"}},
                                normalizar=lambda c: c["attributes"])
        pot = ds.consultar(_fuente(source_id="POT_BAQ_AREAS_ACTIVIDAD", layer_id=85),
                           lambda: {"attributes": {"simb_activ": "AC", "actividad":
                                                   "ACTIVIDAD CENTRAL",
                                                   "nombre_uso": "ACTIVIDAD URBANA"}},
                           normalizar=lambda c: c["attributes"])
        self.assertIsNotNone(catastro["payload_normalized"].get("destinacion_economica"))
        self.assertNotIn("uso", catastro["payload_normalized"])
        self.assertNotIn("destinacion_economica", pot["payload_normalized"])
        self.assertNotEqual(catastro["source_id"], pot["source_id"])

    def test_uso_pot_no_se_copia_al_destino(self):
        pot = ds.consultar(_fuente(source_id="POT_BAQ_POLIGONOS_USO", layer_id=87),
                           lambda: {"attributes": {"uso": "ACTIVIDAD URBANA"}},
                           normalizar=lambda c: c["attributes"])
        self.assertNotIn("destinacion_economica", pot["payload_normalized"])


class TestAlturaNormativa(unittest.TestCase):
    """G · POT.altura_max NUNCA se usa como altura física del edificio."""

    def test_altura_pot_rechazada_como_fisica(self):
        r = ds.altura_fisica(11, height_source="POT_BAQ_EDIFICABILIDAD.altura_max",
                             altura_normativa_pot=11)
        self.assertIsNone(r["building_physical_height"])
        self.assertEqual(r["shadow_confidence"], "DEGRADED")
        self.assertIn("NORMATIVA", r["reason"])

    def test_altura_sin_fuente_rechazada(self):
        r = ds.altura_fisica(9.0)
        self.assertIsNone(r["building_physical_height"])
        self.assertEqual(r["shadow_confidence"], "DEGRADED")

    def test_sin_altura_no_bloquea_solo_degrada(self):
        r = ds.altura_fisica(None, altura_normativa_pot=11)
        self.assertIsNone(r["building_physical_height"])
        self.assertEqual(r["shadow_confidence"], "DEGRADED")
        self.assertNotEqual(r.get("blocking"), True)

    def test_altura_de_fuente_automatica_se_acepta_con_su_fuente(self):
        r = ds.altura_fisica(9.0, height_source="MS_BUILDINGS_FOOTPRINT.height")
        self.assertEqual(r["building_physical_height"], 9.0)
        self.assertEqual(r["height_source"], "MS_BUILDINGS_FOOTPRINT.height")
        self.assertEqual(r["shadow_confidence"], "OK")


class TestPrecedenciaRiesgo(unittest.TestCase):
    """H · una capa histórica nunca vence en silencio a la vigente."""

    def _candidatos(self):
        return [
            {"source_id": "POT_BAQ_REMOCION_71", "layer_id": 71,
             "precedence": ds.HISTORICAL_REFERENCE, "value": "BAJA"},
            {"source_id": "POT_BAQ_REMOCION_2024", "layer_id": 73,
             "precedence": ds.CURRENT_NORMATIVE, "value": "MEDIA"},
        ]

    def test_gana_la_vigente_y_se_declara_la_desplazada(self):
        r = ds.resolver_precedencia(self._candidatos())
        self.assertEqual(r["selected"]["source_id"], "POT_BAQ_REMOCION_2024")
        self.assertEqual([d["source_id"] for d in r["displaced"]], ["POT_BAQ_REMOCION_71"])
        self.assertFalse(r["silent_override"])
        self.assertEqual(r["precedence_order"],
                         ["CURRENT_NORMATIVE", "CURRENT_OFFICIAL", "HISTORICAL_REFERENCE"])

    def test_orden_invertido_no_cambia_el_ganador(self):
        cand = list(reversed(self._candidatos()))
        self.assertEqual(ds.resolver_precedencia(cand)["selected"]["source_id"],
                         "POT_BAQ_REMOCION_2024")

    def test_sin_vigente_declara_sin_dato_y_conserva_la_historica(self):
        # Con SOLO la capa histórica disponible, el sistema NO la asciende a vigente:
        # declara que no hay capa vigente y conserva la histórica como referencia.
        r = ds.resolver_precedencia([self._candidatos()[0]])
        self.assertIsNone(r["selected"])
        self.assertEqual([d["source_id"] for d in r["displaced"]],
                         ["POT_BAQ_REMOCION_71"])
        self.assertIn("SIN DATO", r["reason"])


class TestEquipamientoSeparado(unittest.TestCase):
    """N · POI oficial y OSM permanecen separados."""

    def test_no_se_mezclan_autoridades(self):
        oficial = ds.resultado("EQUIP_SALUD_27", ds.DISPONIBLE,
                               provenance={"authority_class": ds.AUTORITATIVA_OFICIAL})
        osm = ds.resultado("OSM_OVERPASS", ds.DISPONIBLE,
                           provenance={"authority_class": ds.CONTEXTUAL_EXTERNA})
        sep = ds.separar_equipamiento({"EQUIP_SALUD_27": oficial, "OSM_OVERPASS": osm})
        self.assertIn("EQUIP_SALUD_27", sep["official_equipment"])
        self.assertIn("OSM_OVERPASS", sep["contextual_services"])
        self.assertNotIn("OSM_OVERPASS", sep["official_equipment"])
        self.assertFalse(sep["mixed_authority"])

    def test_clases_de_autoridad_cerradas(self):
        self.assertEqual(len(ds.CLASES_AUTORIDAD), 4)
        self.assertNotIn(ds.CONTEXTUAL_EXTERNA, ds.CLASES_NORMATIVAS)
        self.assertNotIn(ds.CALCULADA, ds.CLASES_NORMATIVAS)


class TestRegistroYTransporte(unittest.TestCase):

    def test_registro_de_fuentes_existe_y_declara_lo_exigido(self):
        reg = ds.cargar_registro()
        if reg.get("_status") == ds.NO_SOPORTADA:
            self.skipTest("el registro aún no está generado")
        fuentes = reg.get("sources") or {}
        self.assertGreaterEqual(len(fuentes), 15)
        obligatorios = ("source_id", "source_name", "institution", "authority_class",
                        "base_url", "service", "layer_id", "layer_name", "geometry_type",
                        "query_method", "expected_fields", "primary_keys", "binding_fields",
                        "spatial_reference", "legal_or_normative_context",
                        "version_or_vigency", "precedence", "fallback_policy",
                        "freshness_policy", "failure_semantics", "license_or_terms",
                        "can_persist_raw", "can_embed_image", "provenance_fields", "enabled")
        for sid, f in fuentes.items():
            for campo in obligatorios:
                self.assertIn(campo, f, f"la fuente {sid} no declara {campo}")
            self.assertIn(f["authority_class"], ds.CLASES_AUTORIDAD)

    def test_transporte_al_run_state_no_toca_la_decision(self):
        rs = {"run_id": "x", "findings": [{"codigo": "H-01"}]}
        base = len(rs)
        ds.adjuntar_a_run_state(rs, {"A": ds.resultado("A", ds.FUENTE_NO_DISPONIBLE)})
        self.assertEqual(len(rs), base + 1)
        self.assertEqual(rs["source_pack"]["statuses"]["A"], ds.FUENTE_NO_DISPONIBLE)
        self.assertNotIn("decision_gates", rs)


if __name__ == "__main__":
    unittest.main()

# -*- coding: utf-8 -*-
"""RESOLUTION LADDER POR ATRIBUTO — pruebas BLOQUEANTES (offline, deterministas).

Cubren las garantías del «Barranquilla Source Pack» que NO pueden depender de que una
fuente esté viva:

  · múltiples capas NO son conflicto por defecto: se obtiene el MEJOR HECHO DISPONIBLE,
  · escalera por atributo con fallback AUTOMÁTICO y registro de cada intento,
  · ausencia (`SOURCE_UNAVAILABLE` / `NOT_SUPPORTED` / `QUERY_FAILED`) nunca se convierte
    en `NO_MATCH` en ningún punto de la escalera,
  · `CONFLICT` solo con la definición ESTRICTA (misma semántica, misma vigencia, autoridad
    comparable, mismo objeto, valores incompatibles e irresolubles por precedencia),
  · una capa HISTÓRICA nunca compite con la VIGENTE,
  · DICTUS ve solo el valor resuelto + provenance; las alternativas van al ANEXO,
  · determinismo total: permutar el orden de entrada de fuentes y consultas no cambia nada.

Ninguna prueba toca la red ni modifica archivos: el registro del pack se lee y, cuando la
prueba necesita una topología distinta, se INYECTA un registro/cobertura en memoria.
"""
import itertools
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))

import dictus_sources as ds  # noqa: E402
import source_resolution as sr  # noqa: E402

QUERY_ID = "2026-09-29T00:00:00+00:00"


def _ok(sid, payload):
    """`SourceResult` AVAILABLE determinista (sin reloj ni red)."""
    return ds.resultado(sid, ds.DISPONIBLE, payload_normalized=payload,
                        queried_at=QUERY_ID, provenance={"source_id": sid, "queried_at": QUERY_ID})


def _estado(sid, status):
    return ds.resultado(sid, status, queried_at=QUERY_ID)


def _registro_pack():
    reg = ds.cargar_registro()
    if reg.get("_status") == ds.NO_SOPORTADA:
        return None
    return reg


class BaseLadder(unittest.TestCase):
    """Registro real del pack; las pruebas se saltan solo si el pack no está generado."""

    @classmethod
    def setUpClass(cls):
        cls.reg = _registro_pack()
        if cls.reg is None:
            raise unittest.SkipTest("el registro del Source Pack aún no está generado")

    def resolver(self, atributo, consultas, **kw):
        return sr.resolver_atributo(atributo, consultas=consultas, registro=self.reg, **kw)


# ── 1 · sin conflicto por defecto ─────────────────────────────────────────────
class TestSinConflictoPorDefecto(BaseLadder):
    """Una capa vieja y una nueva para el MISMO atributo NO son un conflicto."""

    def setUp(self):
        self.r = self.resolver("remocion", {
            "POT_BAQ_REMOCION_2024": _ok("POT_BAQ_REMOCION_2024", {"amenaza": "MEDIA"}),
            "POT_BAQ_REMOCION_HIST": _ok("POT_BAQ_REMOCION_HIST", {"amenaza": "ALTA"}),
        })

    def test_resuelve_con_la_vigente(self):
        self.assertEqual(self.r["resolution_status"], sr.RESOLVED_PRIMARY)
        self.assertEqual(self.r["value"], "MEDIA")
        self.assertEqual(self.r["selected_source"], "POT_BAQ_REMOCION_2024")
        self.assertEqual(self.r["vigencia"], ds.CURRENT_NORMATIVE)

    def test_no_hay_conflicto(self):
        self.assertIsNone(self.r["conflict"])
        self.assertNotEqual(self.r["resolution_status"], sr.AMBIGUOUS)

    def test_la_historica_queda_en_attempts_y_anexo(self):
        intentos = {i["source_id"]: i for i in self.r["attempts"]}
        self.assertIn("POT_BAQ_REMOCION_HIST", intentos)
        self.assertEqual(intentos["POT_BAQ_REMOCION_HIST"]["value"], "ALTA")
        self.assertEqual(intentos["POT_BAQ_REMOCION_HIST"]["ladder_role"],
                         "REFERENCIA_HISTORICA")
        anexo = sr.anexo_alternativas({"remocion": self.r})["remocion"]
        self.assertIn("POT_BAQ_REMOCION_HIST", anexo["historical_references"])
        sids = [a["source_id"] for a in anexo["alternativas"]]
        self.assertIn("POT_BAQ_REMOCION_HIST", sids)
        self.assertNotIn("POT_BAQ_REMOCION_2024", sids)
        self.assertEqual(anexo["selected_source"], "POT_BAQ_REMOCION_2024")

    def test_la_historica_nunca_aporta_el_valor_operativo(self):
        """Con SOLO la capa histórica viva, NO se asciende a vigente: se declara ausencia."""
        r = self.resolver("remocion", {
            "POT_BAQ_REMOCION_2024": _estado("POT_BAQ_REMOCION_2024", ds.FUENTE_NO_DISPONIBLE),
            "POT_BAQ_REMOCION_HIST": _ok("POT_BAQ_REMOCION_HIST", {"amenaza": "ALTA"}),
        })
        self.assertEqual(r["resolution_status"], sr.SOURCE_UNAVAILABLE)
        self.assertIsNone(r["value"])
        self.assertIsNone(r["conflict"])
        self.assertEqual(r["provenance"], {})
        self.assertIn("HISTÓRICA", r["reason"])
        anexo = sr.anexo_alternativas({"remocion": r})["remocion"]
        self.assertIn("POT_BAQ_REMOCION_HIST", anexo["historical_references"])

    def test_orden_invertido_de_capas_no_cambia_el_ganador(self):
        r = self.resolver("remocion", {
            "POT_BAQ_REMOCION_HIST": _ok("POT_BAQ_REMOCION_HIST", {"amenaza": "ALTA"}),
            "POT_BAQ_REMOCION_2024": _ok("POT_BAQ_REMOCION_2024", {"amenaza": "MEDIA"}),
        })
        self.assertEqual(r, self.r)


# ── 2 · fallback automático ───────────────────────────────────────────────────
class TestFallbackAutomatico(BaseLadder):

    def test_la_primera_cae_y_la_siguiente_da_el_valor(self):
        r = self.resolver("destino_catastral", {
            "CATASTRO_BAQ_DESTINO_ECONOMICO": _estado("CATASTRO_BAQ_DESTINO_ECONOMICO",
                                                      ds.FUENTE_NO_DISPONIBLE),
            "CATASTRO_BAQ_PREDIO": _ok("CATASTRO_BAQ_PREDIO",
                                       {"destinacion_economica": "HABITACIONAL"}),
        })
        self.assertEqual(r["resolution_status"], sr.RESOLVED_FALLBACK)
        self.assertEqual(r["value"], "HABITACIONAL")
        self.assertEqual(r["selected_source"], "CATASTRO_BAQ_PREDIO")
        self.assertEqual(r["fallbacks_used"], ["CATASTRO_BAQ_DESTINO_ECONOMICO"])
        self.assertIsNone(r["conflict"])

    def test_las_fuentes_intentadas_quedan_registradas_con_su_estado(self):
        r = self.resolver("destino_catastral", {
            "CATASTRO_BAQ_DESTINO_ECONOMICO": _estado("CATASTRO_BAQ_DESTINO_ECONOMICO",
                                                      ds.FUENTE_NO_DISPONIBLE),
            "CATASTRO_BAQ_PREDIO": _ok("CATASTRO_BAQ_PREDIO",
                                       {"destinacion_economica": "HABITACIONAL"}),
        })
        sids = [i["source_id"] for i in r["attempts"]]
        self.assertEqual(sids, ["CATASTRO_BAQ_DESTINO_ECONOMICO", "CATASTRO_BAQ_PREDIO"])
        primero = r["attempts"][0]
        self.assertEqual(primero["status"], ds.FUENTE_NO_DISPONIBLE)
        self.assertTrue(primero["rejected_reason"])
        self.assertEqual(r["attempts"][1]["ladder_role"], "SELECCIONADA")

    def test_fallback_por_valor_no_utilizable(self):
        """La fuente responde, pero con un centinela: no es un dato → siguiente escalón.

        Ejercitado con `localidad` (POT_BAQ_LOCALIDADES → POT_BAQ_BARRIOS): el escalón de
        `mercado` está VACÍO por decisión de producto (la Lonja no es una fuente de datos),
        así que ningún atributo usa ya esa pieza como peldaño.
        """
        r = self.resolver("localidad", {
            "POT_BAQ_LOCALIDADES": _ok("POT_BAQ_LOCALIDADES", {"localidad": "NO DISPONIBLE"}),
            "POT_BAQ_BARRIOS": _ok("POT_BAQ_BARRIOS", {"localidad": "RIOMAR"}),
        })
        self.assertEqual(r["resolution_status"], sr.RESOLVED_FALLBACK)
        self.assertEqual(r["value"], "RIOMAR")
        self.assertEqual(r["selected_source"], "POT_BAQ_BARRIOS")
        self.assertIn("no es utilizable", r["attempts"][0]["rejected_reason"])

    def test_el_mercado_no_tiene_fuente_y_declara_la_ausencia(self):
        """DOCTRINA: la Lonja no es una fuente de datos ⇒ el escalón de mercado está VACÍO."""
        self.assertEqual(sr.escalon_para_atributo("mercado", registro=self.reg), [])
        r = self.resolver("mercado", {})
        self.assertEqual(r["resolution_status"], sr.SOURCE_UNAVAILABLE)
        self.assertIsNone(r["value"])
        self.assertIsNone(r["selected_source"])
        self.assertNotEqual(r["resolution_status"], ds.SIN_COINCIDENCIA)
        self.assertIn("MERCADO SIN FUENTE", r["reason"])
        self.assertIn("sin_fuente_declarada", r["ladder_notes"])
        # El mercado NO aparece como valor resuelto para DICTUS ni con un valor sustituido.
        self.assertNotIn("mercado", sr.solo_valor_resuelto({"mercado": r}))

    def test_provenance_del_fallback_declara_que_lo_es(self):
        r = self.resolver("destino_catastral", {
            "CATASTRO_BAQ_DESTINO_ECONOMICO": _estado("CATASTRO_BAQ_DESTINO_ECONOMICO",
                                                      ds.CONSULTA_FALLIDA),
            "CATASTRO_BAQ_PREDIO": _ok("CATASTRO_BAQ_PREDIO",
                                       {"destinacion_economica": "HABITACIONAL"}),
        })
        prov = r["provenance"]
        self.assertTrue(prov["is_fallback"])
        self.assertEqual(prov["escalon_source_id"], "CATASTRO_BAQ_PREDIO")
        self.assertEqual(prov["fallbacks_used"], ["CATASTRO_BAQ_DESTINO_ECONOMICO"])
        self.assertEqual(prov["resolution_status"], sr.RESOLVED_FALLBACK)
        self.assertEqual(prov["annex_reference"], r["annex_reference"])


# ── 3 · todas caídas ──────────────────────────────────────────────────────────
class TestTodasCaidas(BaseLadder):

    def test_ausencia_total_no_es_no_match_ni_cero(self):
        r = self.resolver("remocion", {
            "POT_BAQ_REMOCION_2024": _estado("POT_BAQ_REMOCION_2024", ds.FUENTE_NO_DISPONIBLE),
            "POT_BAQ_REMOCION_HIST": _estado("POT_BAQ_REMOCION_HIST", ds.NO_SOPORTADA),
        })
        self.assertEqual(r["resolution_status"], sr.SOURCE_UNAVAILABLE)
        self.assertIsNone(r["value"])
        self.assertNotEqual(r["resolution_status"], ds.SIN_COINCIDENCIA)
        self.assertNotEqual(r["value"], 0)
        self.assertIsNone(r["selected_source"])
        self.assertEqual(r["provenance"], {})
        self.assertEqual([i["status"] for i in r["attempts"]],
                         [ds.FUENTE_NO_DISPONIBLE, ds.NO_SOPORTADA])
        self.assertTrue(all(i["rejected_reason"] for i in r["attempts"]))

    def test_query_fallida_tambien_baja_el_escalon(self):
        r = self.resolver("riesgo", {
            "POT_BAQ_RIESGO_2024": _estado("POT_BAQ_RIESGO_2024", ds.CONSULTA_FALLIDA),
            "POT_BAQ_RIESGO_HIST": _estado("POT_BAQ_RIESGO_HIST", ds.CONSULTA_FALLIDA),
        })
        self.assertEqual(r["resolution_status"], sr.SOURCE_UNAVAILABLE)
        self.assertIn("QUERY_FAILED", r["reason"])

    def test_sin_consulta_no_se_declara_no_match(self):
        r = self.resolver("riesgo", {})
        self.assertEqual(r["resolution_status"], sr.SOURCE_UNAVAILABLE)
        self.assertTrue(all(i["status"] == sr.NOT_RUN for i in r["attempts"]))
        self.assertNotEqual(r["resolution_status"], ds.SIN_COINCIDENCIA)


# ── 4 · ninguna fuente cubre el atributo ─────────────────────────────────────
class TestSinCobertura(BaseLadder):

    def test_atributo_no_cubierto_es_unresolved(self):
        r = self.resolver("atributo_que_ninguna_fuente_del_pack_cubre", {})
        self.assertEqual(r["resolution_status"], sr.UNRESOLVED)
        self.assertEqual(r["resolution_status"], "UNRESOLVED")
        self.assertFalse(r["attribute_declared"])
        self.assertEqual(r["attempts"], [])
        self.assertEqual(r["value"], None)
        self.assertIsNone(r["conflict"])

    def test_escalon_vacio_no_es_conflicto_ni_no_match(self):
        self.assertEqual(sr.escalon_para_atributo("atributo_inexistente",
                                                  registro=self.reg), [])
        r = self.resolver("atributo_inexistente", {})
        self.assertNotEqual(r["resolution_status"], ds.SIN_COINCIDENCIA)
        self.assertNotEqual(r["resolution_status"], sr.AMBIGUOUS)

    def test_atributo_declarado_sin_fuentes_en_el_registro(self):
        r = sr.resolver_atributo("riesgo",
                                 consultas={},
                                 registro={"_status": ds.NO_SOPORTADA, "sources": {}})
        self.assertEqual(r["resolution_status"], sr.UNRESOLVED)
        self.assertEqual(r["registry_status"], ds.NO_SOPORTADA)
        self.assertEqual(r["unregistered_sources"], ["POT_BAQ_RIESGO_2024",
                                                     "POT_BAQ_RIESGO_HIST"])

    def test_atributo_cubierto_pero_no_consultado_no_es_unresolved(self):
        r = self.resolver("riesgo", {})
        self.assertNotEqual(r["resolution_status"], sr.UNRESOLVED)
        self.assertEqual(r["resolution_status"], sr.SOURCE_UNAVAILABLE)


# ── 5 · conflicto irresoluble ─────────────────────────────────────────────────
class TestConflictoIrresoluble(BaseLadder):
    """Dos fuentes equivalentes con valores incompatibles que la precedencia no resuelve.

    `estrato`: dos fuentes OFICIALES vigentes, mismo objeto (el predio), misma semántica
    (estrato socioeconómico) y SIN `source_priority` declarada por el pack para decidir.
    """

    def setUp(self):
        self.r = self.resolver("estrato", {
            "POT_BAQ_ESTRATIFICACION": _ok("POT_BAQ_ESTRATIFICACION", {"estrato": "4"}),
            "CATASTRO_BAQ_PREDIO": _ok("CATASTRO_BAQ_PREDIO", {"estrato": "5"}),
        })

    def test_estado_ambiguous_y_conflict_declarado(self):
        self.assertEqual(self.r["resolution_status"], sr.AMBIGUOUS)
        self.assertIsNone(self.r["value"])
        self.assertIsNone(self.r["selected_source"])
        self.assertEqual(self.r["provenance"], {})
        self.assertIsNotNone(self.r["conflict"])

    def test_el_conflicto_trae_motivo_y_candidatos(self):
        c = self.r["conflict"]
        self.assertEqual(c["label"], sr.CONFLICT)
        self.assertEqual(c["resolution_status"], sr.AMBIGUOUS)
        self.assertTrue(c["reason"])
        self.assertIn("CONFLICT", c["reason"])
        self.assertEqual(sorted(c["sources"]),
                         ["CATASTRO_BAQ_PREDIO", "POT_BAQ_ESTRATIFICACION"])
        self.assertEqual(sorted(v["value"] for v in c["values"]), ["4", "5"])
        self.assertEqual(c["semantics"], "ESTRATO_SOCIOECONOMICO")
        self.assertEqual(c["object_key"], "PREDIO")
        self.assertEqual(c["vigencia"], ds.CURRENT_OFFICIAL)

    def test_las_dos_fuentes_quedan_en_el_anexo_como_en_conflicto(self):
        anexo = sr.anexo_alternativas({"estrato": self.r})["estrato"]
        roles = {a["source_id"]: a["ladder_role"] for a in anexo["alternativas"]}
        self.assertEqual(set(roles.values()), {"EN_CONFLICTO"})
        self.assertEqual(len(roles), 2)
        self.assertIsNotNone(anexo["conflict"])
        self.assertNotIn("estrato", sr.solo_valor_resuelto({"estrato": self.r}))

    def test_es_conflicto_estricto_es_verdadero(self):
        a = sr.escalon_para_atributo("estrato", registro=self.reg)[0]
        b = sr.escalon_para_atributo("estrato", registro=self.reg)[1]
        a["value"], b["value"] = "4", "5"
        veredicto = sr.es_conflicto(a, b)
        self.assertTrue(veredicto)
        self.assertTrue(veredicto["conflict"])
        self.assertTrue(veredicto["reason"])
        self.assertTrue(all(veredicto["conditions"].values()))
        self.assertEqual(veredicto["unmet"], [])
        self.assertEqual(veredicto["sources"],
                         [a["source_id"], b["source_id"]])


# ── 6 · equivalentes con valores compatibles ──────────────────────────────────
class TestEquivalentesCompatibles(BaseLadder):

    def test_valores_iguales_normalizados_no_son_conflicto(self):
        r = self.resolver("estrato", {
            "POT_BAQ_ESTRATIFICACION": _ok("POT_BAQ_ESTRATIFICACION", {"estrato": 4}),
            "CATASTRO_BAQ_PREDIO": _ok("CATASTRO_BAQ_PREDIO", {"estrato": "4.0"}),
        })
        self.assertEqual(r["resolution_status"], sr.RESOLVED_PRIMARY)
        self.assertIsNone(r["conflict"])
        self.assertEqual(sr.normalizar_valor(r["value"]), "4")
        roles = {a["source_id"]: a["ladder_role"] for a in r["attempts"]}
        self.assertIn("CORROBORA", roles.values())
        self.assertEqual(r["provenance"]["corroborated_by"], ["POT_BAQ_ESTRATIFICACION"])

    def test_es_conflicto_devuelve_falso_con_valores_compatibles(self):
        v = sr.es_conflicto(
            {"source_id": "A", "value": "4", "vigencia": ds.CURRENT_OFFICIAL,
             "authority_class": ds.AUTORITATIVA_OFICIAL, "semantics": "S",
             "object_key": "PREDIO"},
            {"source_id": "B", "value": "4.0", "vigencia": ds.CURRENT_OFFICIAL,
             "authority_class": ds.AUTORITATIVA_OFICIAL, "semantics": "S",
             "object_key": "PREDIO"})
        self.assertFalse(v)
        self.assertFalse(v["conflict"])
        self.assertIn("valores_incompatibles", v["unmet"])

    def test_una_de_las_dos_sin_valor_utilizable_no_es_conflicto(self):
        v = sr.es_conflicto(
            {"source_id": "A", "value": "N/D", "vigencia": ds.CURRENT_OFFICIAL,
             "authority_class": ds.AUTORITATIVA_OFICIAL, "semantics": "S",
             "object_key": "PREDIO"},
            {"source_id": "B", "value": "4", "vigencia": ds.CURRENT_OFFICIAL,
             "authority_class": ds.AUTORITATIVA_OFICIAL, "semantics": "S",
             "object_key": "PREDIO"})
        self.assertFalse(v)


# ── 7 · no es conflicto aunque los valores difieran ───────────────────────────
class TestNoEsConflicto(BaseLadder):

    def _candidato(self, **over):
        base = {"source_id": "A", "value": "X", "vigencia": ds.CURRENT_OFFICIAL,
                "authority_class": ds.AUTORITATIVA_OFICIAL, "semantics": "SEM",
                "object_key": "OBJ", "rank": [0, 1, 100]}
        base.update(over)
        return base

    def test_distinta_vigencia_no_es_conflicto(self):
        v = sr.es_conflicto(self._candidato(source_id="VIG", value="MEDIA",
                                            vigencia=ds.CURRENT_NORMATIVE, rank=[0, 0, 100]),
                            self._candidato(source_id="HIST", value="ALTA",
                                            vigencia=ds.HISTORICAL_REFERENCE, rank=[0, 4, 100]))
        self.assertFalse(v)
        self.assertIn("misma_vigencia", v["unmet"])
        self.assertIn("histórica", v["reason"])

    def test_distinta_semantica_no_es_conflicto(self):
        v = sr.es_conflicto(self._candidato(semantics="DESTINO_ECONOMICO_CATASTRAL"),
                            self._candidato(source_id="B", value="Y",
                                            semantics="USO_NORMATIVO_POT"))
        self.assertFalse(v)
        self.assertIn("misma_semantica", v["unmet"])

    def test_distinto_objeto_no_es_conflicto(self):
        v = sr.es_conflicto(self._candidato(object_key="PREDIO"),
                            self._candidato(source_id="B", value="Y", object_key="BARRIO"))
        self.assertFalse(v)
        self.assertIn("mismo_objeto", v["unmet"])

    def test_destino_catastral_vs_uso_pot_nunca_es_conflicto(self):
        catastro = self.resolver("destino_catastral", {
            "CATASTRO_BAQ_DESTINO_ECONOMICO": _ok("CATASTRO_BAQ_DESTINO_ECONOMICO",
                                                  {"destinacion_economica": "HABITACIONAL"}),
        })
        uso = self.resolver("uso_pot", {
            "POT_BAQ_AREAS_ACTIVIDAD": _ok("POT_BAQ_AREAS_ACTIVIDAD",
                                           {"nombre_uso": "ACTIVIDAD URBANA"}),
        })
        self.assertIsNone(catastro["conflict"])
        self.assertIsNone(uso["conflict"])
        self.assertNotEqual(catastro["semantics"], uso["semantics"])
        v = sr.es_conflicto(catastro, uso, registro=self.reg)
        self.assertFalse(v)

    def test_autoridad_no_comparable_no_es_conflicto(self):
        v = sr.es_conflicto(self._candidato(),
                            self._candidato(source_id="CTX", value="Y",
                                            authority_class=ds.CONTEXTUAL_EXTERNA,
                                            rank=[2, 2, 100]))
        self.assertFalse(v)
        self.assertIn("autoridad_comparable", v["unmet"])

    def test_misma_autoridad_prioridad_distinta_es_precedencia_no_conflicto(self):
        v = sr.es_conflicto(self._candidato(rank=[0, 1, 10]),
                            self._candidato(source_id="B", value="Y", rank=[0, 1, 20]))
        self.assertFalse(v)
        self.assertIn("precedencia_no_resuelve", v["unmet"])

    def test_dos_oficiales_que_empatan_pero_con_prioridad_declarada_se_resuelven(self):
        """`destino_catastral` declara prioridad: la capa de anualidad manda y no hay conflicto."""
        r = self.resolver("destino_catastral", {
            "CATASTRO_BAQ_DESTINO_ECONOMICO": _ok("CATASTRO_BAQ_DESTINO_ECONOMICO",
                                                  {"destinacion_economica": "COMERCIAL"}),
            "CATASTRO_BAQ_PREDIO": _ok("CATASTRO_BAQ_PREDIO",
                                       {"destinacion_economica": "HABITACIONAL"}),
        })
        self.assertEqual(r["resolution_status"], sr.RESOLVED_PRIMARY)
        self.assertEqual(r["value"], "COMERCIAL")
        self.assertIsNone(r["conflict"])
        roles = {a["source_id"]: a["ladder_role"] for a in r["attempts"]}
        self.assertEqual(roles["CATASTRO_BAQ_PREDIO"], "DESPLAZADA_POR_PRECEDENCIA")


# ── 8 · determinismo ──────────────────────────────────────────────────────────
class TestDeterminismo(BaseLadder):

    IDS = ("CATASTRO_BAQ_ADOPCION_ANEXO1", "CATASTRO_BAQ_PREDIO", "CATASTRO_BAQ_TERRENO")

    def _consultas(self):
        return {
            "CATASTRO_BAQ_ADOPCION_ANEXO1": _ok("CATASTRO_BAQ_ADOPCION_ANEXO1",
                                                {"numero_predial": "0800101030000100400019"}),
            "CATASTRO_BAQ_PREDIO": _estado("CATASTRO_BAQ_PREDIO", ds.FUENTE_NO_DISPONIBLE),
            "CATASTRO_BAQ_TERRENO": _ok("CATASTRO_BAQ_TERRENO",
                                        {"name": "0800101030000100400019"}),
        }

    def test_permutar_registro_y_consultas_da_el_mismo_resultado(self):
        consultas = self._consultas()
        referencia = None
        combinaciones = 0
        for orden_reg in itertools.permutations(self.IDS):
            registro = {"registry_version": self.reg["registry_version"],
                        "sources": {sid: self.reg["sources"][sid] for sid in orden_reg}}
            for orden_con in itertools.permutations(self.IDS):
                r = sr.resolver_atributo("identidad_nupre",
                                         consultas={sid: consultas[sid] for sid in orden_con},
                                         registro=registro)
                combinaciones += 1
                if referencia is None:
                    referencia = r
                else:
                    self.assertEqual(r, referencia,
                                     f"resultado NO determinista con {orden_reg} / {orden_con}")
        self.assertEqual(combinaciones, 36)
        self.assertEqual(referencia["resolution_status"], sr.RESOLVED_PRIMARY)
        self.assertEqual(referencia["selected_source"], "CATASTRO_BAQ_ADOPCION_ANEXO1")

    def test_el_escalon_no_depende_del_orden_de_entrada(self):
        orden_natural = sr.escalon_para_atributo("identidad_nupre", registro=self.reg)
        esperado = [e["source_id"] for e in orden_natural]
        self.assertEqual(esperado, ["CATASTRO_BAQ_ADOPCION_ANEXO1", "CATASTRO_BAQ_PREDIO",
                                    "CATASTRO_BAQ_TERRENO"])
        for orden in itertools.permutations(self.IDS):
            registro = {"sources": {sid: self.reg["sources"][sid] for sid in orden}}
            obtenido = [e["source_id"]
                        for e in sr.escalon_para_atributo("identidad_nupre", registro=registro)]
            self.assertEqual(obtenido, esperado)

    def test_orden_derivado_de_autoridad_vigencia_prioridad_y_alfabeto(self):
        escalon = sr.escalon_para_atributo("estrato", registro=self.reg)
        self.assertEqual([e["source_id"] for e in escalon],
                         ["CATASTRO_BAQ_PREDIO", "POT_BAQ_ESTRATIFICACION"])
        self.assertEqual([e["rank"] for e in escalon], [[0, 1, 100], [0, 1, 100]])
        remocion = sr.escalon_para_atributo("remocion", registro=self.reg)
        self.assertEqual([e["source_id"] for e in remocion],
                         ["POT_BAQ_REMOCION_2024", "POT_BAQ_REMOCION_HIST"])
        self.assertEqual([e["role"] for e in remocion], [sr.ROL_OPERATIVA, sr.ROL_REFERENCIA])

    def test_resolver_dominio_es_determinista(self):
        consultas = self._consultas()
        primero = sr.resolver_dominio({"identidad_nupre": consultas,
                                       "estrato": {"CATASTRO_BAQ_PREDIO":
                                                   _ok("CATASTRO_BAQ_PREDIO", {"estrato": "3"})}},
                                      registro=self.reg)
        for orden in itertools.permutations(list(consultas)):
            segundo = sr.resolver_dominio(
                {"estrato": {"CATASTRO_BAQ_PREDIO": _ok("CATASTRO_BAQ_PREDIO",
                                                        {"estrato": "3"})},
                 "identidad_nupre": {sid: consultas[sid] for sid in orden}},
                registro=self.reg)
            self.assertEqual(segundo["resultados"]["identidad_nupre"],
                             primero["resultados"]["identidad_nupre"])
            self.assertEqual(segundo["resumen"], primero["resumen"])


# ── 9 · DICTUS ve solo el valor; el anexo lleva las alternativas ──────────────
class TestVistasDictusYAnexo(BaseLadder):

    def setUp(self):
        self.dominio = sr.resolver_dominio({
            "remocion": {
                "POT_BAQ_REMOCION_2024": _ok("POT_BAQ_REMOCION_2024", {"amenaza": "MEDIA"}),
                "POT_BAQ_REMOCION_HIST": _ok("POT_BAQ_REMOCION_HIST", {"amenaza": "ALTA"}),
            },
            "destino_catastral": {
                "CATASTRO_BAQ_DESTINO_ECONOMICO":
                    _estado("CATASTRO_BAQ_DESTINO_ECONOMICO", ds.FUENTE_NO_DISPONIBLE),
                "CATASTRO_BAQ_PREDIO": _ok("CATASTRO_BAQ_PREDIO",
                                           {"destinacion_economica": "HABITACIONAL"}),
            },
            "estrato": {
                "POT_BAQ_ESTRATIFICACION": _ok("POT_BAQ_ESTRATIFICACION", {"estrato": "4"}),
                "CATASTRO_BAQ_PREDIO": _ok("CATASTRO_BAQ_PREDIO", {"estrato": "5"}),
            },
            "mercado": {"LONJA_MARKET_BAQ": _estado("LONJA_MARKET_BAQ", ds.FUENTE_NO_DISPONIBLE)},
        }, registro=self.reg)

    def test_dictus_solo_recibe_valor_y_provenance(self):
        cuerpo = sr.solo_valor_resuelto(self.dominio)
        self.assertEqual(sorted(cuerpo), ["destino_catastral", "remocion"])
        for entrada in cuerpo.values():
            self.assertEqual(sorted(entrada), ["provenance", "value"])
            self.assertIn("source_id", entrada["provenance"])
            self.assertIn("resolution_status", entrada["provenance"])
            self.assertNotIn("attempts", entrada)
            self.assertNotIn("conflict", entrada)
        self.assertEqual(cuerpo["remocion"]["value"], "MEDIA")
        self.assertEqual(cuerpo["remocion"]["provenance"]["source_id"],
                         "POT_BAQ_REMOCION_2024")
        self.assertEqual(cuerpo["destino_catastral"]["provenance"]["is_fallback"], True)

    def test_lo_no_resuelto_no_llega_al_cuerpo(self):
        cuerpo = sr.solo_valor_resuelto(self.dominio)
        self.assertNotIn("estrato", cuerpo)
        self.assertNotIn("mercado", cuerpo)

    def test_el_anexo_lleva_las_alternativas_y_los_intentos(self):
        anexo = sr.anexo_alternativas(self.dominio)
        self.assertEqual(sorted(anexo), ["destino_catastral", "estrato", "mercado", "remocion"])
        remocion = anexo["remocion"]
        self.assertEqual(remocion["annex_reference"], "ANEXO-FUENTES-REMOCION")
        self.assertEqual(remocion["historical_references"], ["POT_BAQ_REMOCION_HIST"])
        self.assertEqual([a["source_id"] for a in remocion["alternativas"]],
                         ["POT_BAQ_REMOCION_HIST"])
        self.assertEqual(remocion["alternativas"][0]["value"], "ALTA")
        self.assertEqual(remocion["selected_source"], "POT_BAQ_REMOCION_2024")
        destino = anexo["destino_catastral"]
        self.assertEqual(destino["fallbacks_used"], ["CATASTRO_BAQ_DESTINO_ECONOMICO"])
        self.assertEqual(destino["sources_attempted"],
                         ["CATASTRO_BAQ_DESTINO_ECONOMICO", "CATASTRO_BAQ_PREDIO"])
        self.assertEqual(destino["alternativas"][0]["status"], ds.FUENTE_NO_DISPONIBLE)
        self.assertTrue(destino["alternativas"][0]["rejected_reason"])
        self.assertEqual(anexo["mercado"]["resolution_status"], sr.SOURCE_UNAVAILABLE)
        self.assertEqual(len(anexo["estrato"]["alternativas"]), 2)

    def test_la_referencia_de_anexo_es_estable(self):
        r = self.resolver("remocion", {})
        self.assertEqual(r["annex_reference"], "ANEXO-FUENTES-REMOCION")
        self.assertEqual(r["annex_reference"], sr.anexo_alternativas({"remocion": r})
                         ["remocion"]["annex_reference"])


# ── 10 · la ausencia nunca se convierte en NO_MATCH ───────────────────────────
class TestAusenciaNuncaEsNoMatch(BaseLadder):

    def _escenarios(self):
        return {
            "total": {
                "riesgo": {
                    "POT_BAQ_RIESGO_2024": _estado("POT_BAQ_RIESGO_2024",
                                                   ds.FUENTE_NO_DISPONIBLE),
                    "POT_BAQ_RIESGO_HIST": _estado("POT_BAQ_RIESGO_HIST", ds.NO_SOPORTADA),
                }},
            "parcial": {
                "destino_catastral": {
                    "CATASTRO_BAQ_DESTINO_ECONOMICO":
                        _estado("CATASTRO_BAQ_DESTINO_ECONOMICO", ds.CONSULTA_FALLIDA),
                    "CATASTRO_BAQ_PREDIO": _ok("CATASTRO_BAQ_PREDIO",
                                               {"destinacion_economica": "COMERCIAL"}),
                }},
            "sin_consulta": {"barrio": {}},
            "sin_cobertura": {"atributo_sin_fuentes": {}},
            "resuelto": {
                "remocion": {
                    "POT_BAQ_REMOCION_2024": _ok("POT_BAQ_REMOCION_2024", {"amenaza": "ALTA"}),
                }},
            "no_match": {
                "identidad_nupre": {
                    "CATASTRO_BAQ_ADOPCION_ANEXO1":
                        _estado("CATASTRO_BAQ_ADOPCION_ANEXO1", ds.SIN_COINCIDENCIA),
                }},
        }

    def test_ninguna_ausencia_es_no_match_en_ningun_punto(self):
        permitidos = set(ds.ESTADOS) | {sr.NOT_RUN}
        escenarios = self._escenarios()
        revisados = 0
        for nombre, dominio in escenarios.items():
            resueltos = sr.resolver_dominio(dominio, registro=self.reg)
            self.assertEqual(len(resueltos["resultados"]), len(dominio), nombre)
            for atributo, r in resueltos["resultados"].items():
                etiqueta = f"{nombre}/{atributo}"
                revisados += 1
                self.assertIn(r["resolution_status"], sr.ESTADOS_RESOLUCION, etiqueta)
                self.assertNotEqual(r["resolution_status"], ds.SIN_COINCIDENCIA, etiqueta)
                self.assertNotEqual(r["resolution_status"], sr.CONFLICT, etiqueta)
                for intento in r["attempts"]:
                    self.assertIn(intento["status"], permitidos, etiqueta)
                    if intento["status"] in ds.ESTADOS_SIN_DATO:
                        self.assertTrue(intento["rejected_reason"], etiqueta)
                        self.assertNotIn("NO_MATCH", intento["rejected_reason"].split(":")[0],
                                         etiqueta)
        self.assertEqual(revisados, sum(len(d) for d in escenarios.values()))
        self.assertEqual(revisados, 6)

    def test_resumen_del_dominio_cuenta_los_cinco_estados(self):
        unificado = {}
        for dominio in self._escenarios().values():
            unificado.update(dominio)
        self.assertEqual(len(unificado), 6)
        resumen = sr.resolver_dominio(unificado, registro=self.reg)["resumen"]
        for clave in ("resolved_primary", "resolved_fallback", "unresolved", "ambiguous",
                      "source_unavailable", "conflicts"):
            self.assertIn(clave, resumen)
            self.assertIsInstance(resumen[clave], int)
        self.assertEqual(resumen["total"], 6)
        self.assertEqual(resumen["resolved_primary"], 1)
        self.assertEqual(resumen["resolved_fallback"], 1)
        self.assertEqual(resumen["source_unavailable"], 2)
        self.assertEqual(resumen["unresolved"], 2)
        self.assertEqual(resumen["ambiguous"], 0)
        self.assertEqual(resumen["conflicts"], 0)

    def test_un_no_match_que_si_contesto_solo_baja_si_el_atributo_lo_admite(self):
        # `identidad_nupre` declara que la identidad canónica NO se sustituye.
        r = self.resolver("identidad_nupre", {
            "CATASTRO_BAQ_ADOPCION_ANEXO1":
                _estado("CATASTRO_BAQ_ADOPCION_ANEXO1", ds.SIN_COINCIDENCIA),
            "CATASTRO_BAQ_PREDIO": _ok("CATASTRO_BAQ_PREDIO",
                                       {"numero_predial_nacional": "OTRO"}),
        })
        self.assertEqual(r["resolution_status"], sr.UNRESOLVED)
        self.assertIsNone(r["value"])
        self.assertEqual([i["source_id"] for i in r["attempts"]],
                         ["CATASTRO_BAQ_ADOPCION_ANEXO1"])
        self.assertEqual(r["attempts"][0]["status"], ds.SIN_COINCIDENCIA)

    def test_un_no_match_en_atributo_que_admite_fallback_si_baja(self):
        # `localidad` admite fallback declarado (POT_BAQ_LOCALIDADES → POT_BAQ_BARRIOS).
        r = self.resolver("localidad", {
            "POT_BAQ_LOCALIDADES": _estado("POT_BAQ_LOCALIDADES", ds.SIN_COINCIDENCIA),
            "POT_BAQ_BARRIOS": _ok("POT_BAQ_BARRIOS", {"localidad": "RIOMAR"}),
        })
        self.assertEqual(r["resolution_status"], sr.RESOLVED_FALLBACK)
        self.assertEqual(r["value"], "RIOMAR")
        self.assertEqual(r["attempts"][0]["status"], ds.SIN_COINCIDENCIA)


# ── reglas de valor utilizable ────────────────────────────────────────────────
class TestValorUtilizable(unittest.TestCase):

    def test_centinelas_no_son_valor(self):
        for centinela in (None, "", [], {}, "NO DISPONIBLE", "N/D", "n/d", "  ",
                          "SIN DATO", "N/A", "NA", "NULL", "None", "-", "NO APLICA",
                          [None, ""], {"a": None}):
            self.assertFalse(sr.valor_utilizable(centinela), repr(centinela))

    def test_valores_contestados_si_son_valor(self):
        for valor in (0, 0.0, False, "0", "ALTA", 4, [1], {"a": 1}):
            self.assertTrue(sr.valor_utilizable(valor), repr(valor))

    def test_normalizacion_de_valores(self):
        self.assertEqual(sr.normalizar_valor(4), sr.normalizar_valor("4.0"))
        self.assertEqual(sr.normalizar_valor("Bajo"), sr.normalizar_valor(" BAJO "))
        self.assertEqual(sr.normalizar_valor(["a", "b"]), sr.normalizar_valor(["b", "a"]))
        self.assertTrue(sr.valores_compatibles("Media", "MEDIA"))
        self.assertFalse(sr.valores_compatibles("Media", "Alta"))


# ── escalera: orden, cobertura y ventana de vigencia ──────────────────────────
class TestEscalon(BaseLadder):

    def test_el_escalon_expande_comodines_y_ordena_alfabeticamente(self):
        escalon = sr.escalon_para_atributo("equipamiento_oficial", registro=self.reg)
        sids = [e["source_id"] for e in escalon]
        self.assertEqual(sids, sorted(sids))
        self.assertTrue(all(s.startswith("EQUIPAMIENTO_") for s in sids))
        self.assertEqual(sids[0], "EQUIPAMIENTO_18")

    def test_el_escalon_declara_semantica_objeto_y_prioridad(self):
        escalon = sr.escalon_para_atributo("identidad_nupre", registro=self.reg)
        self.assertEqual(escalon[0]["semantics"], "IDENTIDAD_PREDIAL_CANONICA")
        self.assertEqual(escalon[0]["object_key"], "PREDIO")
        self.assertEqual(escalon[0]["source_priority"], 10)
        self.assertEqual(escalon[0]["priority_origin"], "PER_ATTRIBUTE")
        self.assertEqual([e["escalon_step"] for e in escalon], [1, 2, 3])

    def test_prioridad_explicita_del_registro_se_respeta(self):
        reg = {"sources": {
            "S_A": {"source_id": "S_A", "authority_class": ds.AUTORITATIVA_OFICIAL,
                    "precedence": ds.CURRENT_OFFICIAL, "source_priority": 5},
            "S_B": {"source_id": "S_B", "authority_class": ds.AUTORITATIVA_OFICIAL,
                    "precedence": ds.CURRENT_OFFICIAL, "source_priority": 9},
        }}
        cobertura = {"attr": {"semantics": "S", "object_key": "O",
                              "fuentes": ["S_B", "S_A"]}}
        escalon = sr.escalon_para_atributo("attr", registro=reg, cobertura=cobertura)
        self.assertEqual([e["source_id"] for e in escalon], ["S_A", "S_B"])
        self.assertEqual([e["priority_origin"] for e in escalon], ["REGISTRY", "REGISTRY"])

    def test_ventana_de_vigencia_saca_la_fuente_del_escalon(self):
        escalon = sr.escalon_para_atributo("destino_catastral", registro=self.reg,
                                           fecha="2025-06-01")
        self.assertEqual([e["source_id"] for e in escalon], ["CATASTRO_BAQ_PREDIO"])
        r = self.resolver("destino_catastral", {
            "CATASTRO_BAQ_DESTINO_ECONOMICO": _ok("CATASTRO_BAQ_DESTINO_ECONOMICO",
                                                  {"destinacion_economica": "ANUALIDAD_2026"}),
            "CATASTRO_BAQ_PREDIO": _ok("CATASTRO_BAQ_PREDIO",
                                       {"destinacion_economica": "HABITACIONAL"}),
        }, fecha="2025-06-01")
        self.assertEqual(r["resolution_status"], sr.RESOLVED_FALLBACK)
        self.assertEqual(r["value"], "HABITACIONAL")
        self.assertEqual(r["attempts"][0]["status"], sr.NOT_RUN)
        self.assertEqual(r["fallbacks_used"], ["CATASTRO_BAQ_DESTINO_ECONOMICO"])

    def test_fecha_ilegible_no_excluye_ninguna_fuente(self):
        escalon = sr.escalon_para_atributo("destino_catastral", registro=self.reg,
                                           fecha="no-es-una-fecha")
        self.assertEqual(len(escalon), 2)

    def test_cobertura_inyectada_se_usa_cuando_se_pide(self):
        reg = {"sources": {
            "X1": {"source_id": "X1", "authority_class": ds.CONTEXTUAL_EXTERNA,
                   "precedence": "CONTEXTUAL_REFERENCE"},
            "X2": {"source_id": "X2", "authority_class": ds.AUTORITATIVA_OFICIAL,
                   "precedence": ds.CURRENT_OFFICIAL},
        }}
        cobertura = {"mi_atributo": {"semantics": "SEM", "object_key": "OBJ",
                                     "campos": ["valor"],
                                     "fuentes": {"X1": {}, "X2": {}}}}
        escalon = sr.escalon_para_atributo("mi_atributo", registro=reg, cobertura=cobertura)
        self.assertEqual([e["source_id"] for e in escalon], ["X2", "X1"])
        r = sr.resolver_atributo("mi_atributo", consultas={
            "X2": _estado("X2", ds.FUENTE_NO_DISPONIBLE),
            "X1": _ok("X1", {"valor": "contexto"}),
        }, registro=reg, cobertura=cobertura)
        self.assertEqual(r["resolution_status"], sr.RESOLVED_FALLBACK)
        self.assertEqual(r["value"], "contexto")

    def test_contexto_y_calculado_no_producen_conflicto(self):
        r = self.resolver("servicios_de_contexto", {
            "GOOGLE_STREET_VIEW": _ok("GOOGLE_STREET_VIEW", {"image_url": "g"}),
            "MAPILLARY": _ok("MAPILLARY", {"image_url": "m"}),
            "OSM_OVERPASS": _ok("OSM_OVERPASS", {"pois": ["colegio"]}),
        })
        self.assertIsNone(r["conflict"])
        self.assertNotEqual(r["resolution_status"], sr.AMBIGUOUS)
        roles = {a["source_id"]: a["ladder_role"] for a in r["attempts"]}
        self.assertEqual(r["selected_source"], "OSM_OVERPASS")
        self.assertEqual(roles["OSM_OVERPASS"], "SELECCIONADA")
        self.assertEqual(roles["MAPILLARY"], "COMPLEMENTARIA")
        self.assertEqual(roles["GOOGLE_STREET_VIEW"], "COMPLEMENTARIA")
        self.assertIn("admite_conflicto=False", " ".join(r["ladder_notes"]))

    def test_dos_contextuales_que_empatan_no_declaran_conflicto(self):
        """Mismo rango y valores distintos en un atributo `admite_conflicto=False`."""
        reg = {"sources": {
            "C1": {"source_id": "C1", "authority_class": ds.CONTEXTUAL_EXTERNA,
                   "precedence": "CONTEXTUAL_REFERENCE"},
            "C2": {"source_id": "C2", "authority_class": ds.CONTEXTUAL_EXTERNA,
                   "precedence": "CONTEXTUAL_REFERENCE"},
        }}
        cobertura = {"ctx": {"semantics": "S", "object_key": "O", "campos": ["v"],
                             "admite_conflicto": False, "fuentes": ["C1", "C2"]}}
        r = sr.resolver_atributo("ctx", consultas={"C1": _ok("C1", {"v": "uno"}),
                                                  "C2": _ok("C2", {"v": "dos"})},
                                 registro=reg, cobertura=cobertura)
        self.assertIsNone(r["conflict"])
        self.assertEqual(r["resolution_status"], sr.RESOLVED_PRIMARY)
        self.assertEqual(r["value"], "uno")
        roles = {a["source_id"]: a["ladder_role"] for a in r["attempts"]}
        self.assertEqual(roles["C2"], "DISCREPANCIA_SIN_CONFLICTO")
        # La misma topología con `admite_conflicto=True` SÍ es CONFLICT.
        cobertura["ctx"]["admite_conflicto"] = True
        r2 = sr.resolver_atributo("ctx", consultas={"C1": _ok("C1", {"v": "uno"}),
                                                   "C2": _ok("C2", {"v": "dos"})},
                                  registro=reg, cobertura=cobertura)
        self.assertEqual(r2["resolution_status"], sr.AMBIGUOUS)
        self.assertIsNotNone(r2["conflict"])

    def test_consulta_por_callable(self):
        def consultas(sid):
            return _ok(sid, {"tipo_predio": "LOTE"}) if sid == "CATASTRO_BAQ_PREDIO" else None
        r = self.resolver("predio", consultas)
        self.assertEqual(r["resolution_status"], sr.RESOLVED_PRIMARY)
        self.assertEqual(r["selected_source"], "CATASTRO_BAQ_PREDIO")

    def test_estado_de_registro_declara_ausencia(self):
        self.assertEqual(sr.estado_registro()["registry_status"], "AVAILABLE")
        self.assertEqual(sr.estado_registro({"_status": ds.NO_SOPORTADA})["registry_status"],
                         ds.NO_SOPORTADA)

    def test_todos_los_atributos_declarados_tienen_escalera_en_el_pack(self):
        for atributo in sr.atributos_declarados():
            with self.subTest(atributo=atributo):
                escalon = sr.escalon_para_atributo(atributo, registro=self.reg)
                if not escalon:
                    # DECISIÓN DE PRODUCTO: un atributo puede estar declarado SIN fuente de
                    # datos (`mercado`: la Lonja no es una fuente). Entonces la resolución
                    # declara la ausencia — NO DISPONIBLE — y nunca NO_MATCH ni un valor
                    # sustituido.
                    self.assertTrue(sr.COBERTURA_ATRIBUTOS[atributo].get("no_fuente"),
                                    f"{atributo} sin escalón y sin declarar `no_fuente`")
                    r = sr.resolver_atributo(atributo, consultas={}, registro=self.reg)
                    self.assertEqual(r["resolution_status"], sr.SOURCE_UNAVAILABLE)
                    self.assertIsNone(r["value"])
                    self.assertNotEqual(r["resolution_status"], ds.SIN_COINCIDENCIA)
                    continue
                self.assertTrue(escalon, f"el pack no registra fuentes para {atributo}")
                r = sr.resolver_atributo(atributo, consultas={}, registro=self.reg)
                self.assertIn(r["resolution_status"], sr.ESTADOS_RESOLUCION)
                self.assertNotEqual(r["resolution_status"], ds.SIN_COINCIDENCIA)

    def test_los_cinco_estados_estan_declarados_una_sola_vez(self):
        self.assertEqual(len(sr.ESTADOS_RESOLUCION), 5)
        self.assertEqual(len(set(sr.ESTADOS_RESOLUCION)), 5)
        self.assertEqual(sr.SOURCE_UNAVAILABLE, ds.FUENTE_NO_DISPONIBLE)
        self.assertNotIn(ds.SIN_COINCIDENCIA, sr.ESTADOS_RESOLUCION)

    def test_resolver_dominio_agrupa_por_dominio(self):
        resultado = sr.resolver_dominio({"territorio": ["barrio", "localidad"]},
                                        consultas={
                                            "POT_BAQ_BARRIOS": _ok("POT_BAQ_BARRIOS",
                                                                   {"barrio": "EL PRADO"}),
                                            "POT_BAQ_LOCALIDADES": _ok("POT_BAQ_LOCALIDADES",
                                                                       {"localidad": "RIOMAR"}),
                                        }, registro=self.reg)
        self.assertEqual(sorted(resultado["resultados"]), ["barrio", "localidad"])
        self.assertEqual(resultado["dominios"], {"territorio": ["barrio", "localidad"]})
        self.assertEqual(resultado["resumen"]["resolved_primary"], 2)


if __name__ == "__main__":
    unittest.main()

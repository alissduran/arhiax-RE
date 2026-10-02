# -*- coding: utf-8 -*-
"""BLOCK 1 · ESCALERA DE RESOLUCIÓN POR ATRIBUTO — pruebas BLOQUEANTES (offline).

Cubren los tres casos mínimos exigidos por la misión §29 sobre la escalera REAL del
Source Pack (`api/source_resolution` + `api/acquisition`) y sobre la PERSISTENCIA por
atributo (`api/attribute_truth`):

  1. fuente primaria disponible            → `RESOLVED_PRIMARY`
  2. primaria ausente + fallback válido    → `RESOLVED_FALLBACK`
  3. consulta en vivo caída + snapshot     → `RESOLVED_SNAPSHOT`
     fresco (mismo dato, misma autoridad original)

Ninguna prueba toca la red: el registro del pack se lee del repositorio y las consultas
se inyectan en memoria.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))

import acquisition as acq  # noqa: E402
import attribute_truth as at  # noqa: E402
import dictus_sources as ds  # noqa: E402
import source_resolution as sr  # noqa: E402

GOLDEN_RS = (ROOT / "docs" / "forensics" / "040-646406" / "dictus_2b"
             / "DICTUS_RUN_STATE_040-646406.json")
QUERY_ID = "2026-09-29T00:00:00+00:00"


def _ok(sid, payload):
    return ds.resultado(sid, ds.DISPONIBLE, payload_normalized=payload, queried_at=QUERY_ID,
                        provenance={"source_id": sid, "queried_at": QUERY_ID})


def _ausente(sid, status=ds.FUENTE_NO_DISPONIBLE):
    return ds.resultado(sid, status, queried_at=QUERY_ID)


def _run_state_minimo(valores=None, campos=None):
    """RunState mínimo: `valores` = campo del estado, `campos` = bloque declarado del modo."""
    valores = dict(valores or {})
    return {
        "run_state_version": "dictus-run-state/1.0.0",
        "generated_at": QUERY_ID,
        "property_identity": {"folio": "040-646406", "identity_verified": True,
                              "resolution_confidence": "VERIFIED_UNIT_IDENTITY",
                              "resolution_method": "nupre", "nupre": "AFT0005BOHA",
                              "codigo_catastral": "080010103000010040001908040002",
                              "unidad": "APARTAMENTO 430 TORRE 8",
                              "direccion_raw": "TV 43 # 100 - 50"},
        "urban_context": {"barrio": valores.get("barrio"),
                          "localidad": valores.get("localidad"),
                          "altura_maxima": valores.get("altura_maxima")},
        "market_context": {"urban_source_summary": {"campos": dict(campos or {})}},
    }


class TestEscaleraPorAtributo(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.reg = ds.cargar_registro()
        if cls.reg.get("_status") == ds.NO_SOPORTADA:
            raise unittest.SkipTest("el registro del Source Pack aún no está generado")
        cls.fecha = "2026-09-29"

    # ── 1 · primaria disponible ──────────────────────────────────────────────
    def test_primaria_disponible_resuelve_primary(self):
        r = sr.resolver_atributo("barrio", consultas={"POT_BAQ_BARRIOS":
                                                      _ok("POT_BAQ_BARRIOS",
                                                          {"barrio": "Miramar"})},
                                 registro=self.reg, fecha=self.fecha)
        self.assertEqual(r["resolution_status"], sr.RESOLVED_PRIMARY)
        self.assertEqual(r["selected_source"], "POT_BAQ_BARRIOS")
        self.assertEqual(r["value"], "Miramar")

    def test_la_corrida_declara_la_primaria_y_el_registro_lo_persiste(self):
        rs = _run_state_minimo(
            valores={"barrio": "Miramar"},
            campos={"barrio": {"value": "Miramar", "status": "VERIFIED_OFFICIAL",
                               "fuente": "official_urban_layer", "modo": "LIVE_OFFICIAL"}})
        reg = at.resolver_atributos(rs, registro=self.reg, fecha=self.fecha)
        ficha = reg["attributes"]["barrio"]
        self.assertEqual(ficha["resolution_status"], at.RESOLVED_PRIMARY)
        self.assertEqual(ficha["source_selected"], "POT_BAQ_BARRIOS")
        self.assertEqual(ficha["canonical_value"], "Miramar")
        self.assertTrue(ficha["source_authority"])
        self.assertTrue(ficha["source_vigency"])
        self.assertTrue(ficha["canonical_reason"])
        self.assertTrue(ficha["source_attempts"], "los intentos tienen que quedar registrados")

    # ── 2 · primaria ausente + fallback válido ───────────────────────────────
    def test_primaria_ausente_resuelve_fallback(self):
        r = sr.resolver_atributo(
            "destino_catastral",
            consultas={"CATASTRO_BAQ_DESTINO_ECONOMICO": _ausente("CATASTRO_BAQ_DESTINO_ECONOMICO"),
                       "CATASTRO_BAQ_PREDIO": _ok("CATASTRO_BAQ_PREDIO",
                                                  {"destinacion_economica": "HABITACIONAL"})},
            registro=self.reg, fecha=self.fecha)
        self.assertEqual(r["resolution_status"], sr.RESOLVED_FALLBACK)
        self.assertEqual(r["selected_source"], "CATASTRO_BAQ_PREDIO")

    def test_la_identidad_del_golden_se_resuelve_por_el_escalon_siguiente(self):
        """La primaria declarada del escalón de identidad no se consultó en la corrida:
        la escalera baja al siguiente escalón autorizado y lo DECLARA (fallback)."""
        rs = _run_state_minimo()
        reg = at.resolver_atributos(rs, registro=self.reg, fecha=self.fecha)
        ficha = reg["attributes"]["nupre"]
        self.assertEqual(ficha["resolution_status"], at.RESOLVED_FALLBACK)
        self.assertEqual(ficha["source_selected"], "CATASTRO_BAQ_PREDIO")
        self.assertEqual(ficha["canonical_value"], "AFT0005BOHA")
        intentos = {i["source_id"]: i["status"] for i in ficha["source_attempts"]}
        self.assertEqual(intentos.get("CATASTRO_BAQ_ADOPCION_ANEXO1"), sr.NOT_RUN)
        self.assertIn("No se ejecutó consulta", ficha["canonical_reason"] + " "
                      + str([i["rejected_reason"] for i in ficha["source_attempts"]]))

    # ── 3 · live caído + snapshot fresco ─────────────────────────────────────
    def test_live_caido_con_snapshot_fresco_es_snapshot(self):
        """El motor resuelve desde el snapshot DECLARADO y la verdad por atributo lo
        declara `RESOLVED_SNAPSHOT` (no `primary`: el dato no vino de una consulta)."""
        contexto = {"lat": 11.006055954316363, "lon": -74.8375696549899, "fecha": self.fecha}
        r = acq.resolver_con_acquisition_mode(
            "remocion",
            consultas={"POT_BAQ_REMOCION_2024": _ausente("POT_BAQ_REMOCION_2024")},
            registro=self.reg, fecha=self.fecha, contexto=contexto)
        self.assertEqual(r["resolution_status"], sr.RESOLVED_PRIMARY)
        seleccionado = r["acquisition"]["seleccionado"]
        self.assertTrue(seleccionado.get("snapshot"), "tiene que resolver por el snapshot")
        estado = at._estado_resolucion(r, "", bool(seleccionado.get("snapshot")))
        self.assertEqual(estado, at.RESOLVED_SNAPSHOT)
        self.assertIn(estado, at.ESTADOS_RESOLUCION)

    def test_el_golden_declara_remocion_y_riesgo_como_snapshot(self):
        if not GOLDEN_RS.exists():
            raise unittest.SkipTest("no está el run state del Golden")
        rs = json.loads(GOLDEN_RS.read_text(encoding="utf-8"))
        reg = at.resolver_atributos(rs, registro=self.reg, fecha="2026-10-01")
        for atributo in ("remocion", "riesgo"):
            ficha = reg["attributes"][atributo]
            self.assertEqual(ficha["resolution_status"], at.RESOLVED_SNAPSHOT, atributo)
            self.assertTrue(ficha["source_selected"], atributo)

    # ── vocabulario y persistencia mínima ────────────────────────────────────
    def test_el_vocabulario_de_resolucion_es_cerrado(self):
        for estado in (at.RESOLVED_PRIMARY, at.RESOLVED_FALLBACK, at.RESOLVED_SNAPSHOT,
                       at.UNRESOLVED, at.AMBIGUOUS, at.SOURCE_UNAVAILABLE, at.NOT_SUPPORTED):
            self.assertIn(estado, at.ESTADOS_RESOLUCION)

    def test_la_ficha_persiste_el_minimo_auditable(self):
        rs = _run_state_minimo(
            valores={"barrio": "Miramar", "altura_maxima": "11"},
            campos={"barrio": {"value": "Miramar", "status": "VERIFIED_OFFICIAL",
                               "fuente": "official_urban_layer", "modo": "LIVE_OFFICIAL"},
                    "altura_maxima": {"value": "11", "status": None, "fuente": None,
                                      "modo": "PACKAGED_REFERENCE"}})
        reg = at.resolver_atributos(rs, registro=self.reg, fecha=self.fecha)
        for atributo, ficha in reg["attributes"].items():
            for clave in ("resolution_status", "fact_status", "canonical_value",
                          "canonical_reason", "source_attempts"):
                self.assertIn(clave, ficha, f"{atributo}: falta {clave}")
        ficha = reg["attributes"]["barrio"]
        self.assertEqual(ficha["declared_mode"], "LIVE_OFFICIAL")
        self.assertEqual(ficha["acquisition_mode"], "LIVE_QUERY")
        self.assertEqual(reg["attributes"]["altura_normativa"]["resolution_status"],
                         at.RESOLVED_SNAPSHOT,
                         "un valor declarado como capa empaquetada es un SNAPSHOT")
        self.assertTrue(ficha["queried_at"])
        self.assertEqual(ficha["evidence_id"], "EV-URBANO")

    def test_la_escalera_no_consulta_fuentes_que_la_corrida_no_declaro(self):
        """Sin declaración de la corrida, ninguna fuente se da por consultada."""
        rs = _run_state_minimo()
        reg = at.resolver_atributos(rs, registro=self.reg, fecha=self.fecha)
        ficha = reg["attributes"]["inundacion"]
        self.assertEqual(ficha["resolution_status"], at.SOURCE_UNAVAILABLE)
        self.assertIsNone(ficha["source_selected"])
        for intento in ficha["source_attempts"]:
            self.assertNotEqual(intento["status"], ds.SIN_COINCIDENCIA)
            self.assertIn(intento["status"], (sr.NOT_RUN, ds.NO_SOPORTADA,
                                              ds.FUENTE_NO_DISPONIBLE))


if __name__ == "__main__":
    unittest.main()

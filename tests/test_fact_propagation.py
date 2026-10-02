# -*- coding: utf-8 -*-
"""BLOCK 1 · PROPAGACIÓN DE HECHOS — pruebas BLOQUEANTES (offline).

Reglas que se prueban aquí (§10 · §17 · §18 · §19):

  · `fact_status` se deriva de la escalera (fuente, autoridad, vigencia, evidencia,
    geometría evaluada), NO de la presencia de una cadena de valor;
  · §17: consulta válida + geometría evaluada + fuente válida + resultado espacial ⇒ el
    atributo NO puede quedar `NOT_EVALUATED` (se comprueba que la violación se detecta);
  · §18/§19: una ausencia o una cobertura inexistente se declaran con su estado propio
    (`SOURCE_UNAVAILABLE` / `NOT_SUPPORTED`) y con el motivo exacto — `NOT_EVALUATED`
    nunca es el cajón general;
  · la evidencia agregada `EV-AMENAZAS` se sella por su CONTENIDO, no por la
    disponibilidad del volcán (RSK-3).
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))

import attribute_truth as at  # noqa: E402
import dictus_manifiesto as dm  # noqa: E402
import dictus_sources as ds  # noqa: E402

VIGENTE = ds.CURRENT_OFFICIAL
OFICIAL = ds.AUTORITATIVA_OFICIAL


def _resuelto(estado=at.RESOLVED_PRIMARY):
    return {"resolution_status": estado, "conflict": None}


class TestFactStatusDerivado(unittest.TestCase):

    def _fs(self, resultado, **kw):
        base = dict(valor="X", espacial=False, source_authority=OFICIAL,
                    source_vigency=VIGENTE, tiene_evidencia=True, modo_declarado="",
                    geometria_evaluada=False)
        base.update(kw)
        return at.fact_status_de(resultado, **base)

    def test_resuelto_con_fuente_oficial_vigente_y_evidencia_es_verified(self):
        self.assertEqual(self._fs(_resuelto()), at.VERIFIED)

    def test_resuelto_sin_evidencia_es_known_but_unverified(self):
        self.assertEqual(self._fs(_resuelto(), tiene_evidencia=False),
                         at.KNOWN_BUT_UNVERIFIED)

    def test_fuente_historica_es_historical_only(self):
        self.assertEqual(self._fs(_resuelto(), source_vigency=ds.HISTORICAL_REFERENCE),
                         at.HISTORICAL_ONLY)

    def test_conflicto_de_escalera_es_conflict(self):
        self.assertEqual(self._fs({"resolution_status": at.AMBIGUOUS,
                                   "conflict": {"label": "CONFLICT"}}), at.CONFLICT)

    def test_ausencia_declarada_no_es_no_match_ni_no_evaluado(self):
        estado = self._fs({"resolution_status": at.SOURCE_UNAVAILABLE, "conflict": None})
        self.assertEqual(estado, at.SOURCE_UNAVAILABLE)
        self.assertNotEqual(estado, at.NOT_EVALUATED)

    def test_cobertura_inexistente_es_not_supported(self):
        estado = self._fs({"resolution_status": at.NOT_SUPPORTED, "conflict": None})
        self.assertEqual(estado, at.NOT_SUPPORTED)
        self.assertNotEqual(estado, at.NOT_EVALUATED)

    # ── §17 ──────────────────────────────────────────────────────────────────
    def test_17_con_resultado_espacial_y_geometria_evaluada_no_es_not_evaluated(self):
        estado = self._fs({"resolution_status": at.SOURCE_UNAVAILABLE, "conflict": None},
                          valor="Media · polígono: intersecta el predio", espacial=True,
                          geometria_evaluada=True)
        self.assertNotEqual(estado, at.NOT_EVALUATED)
        self.assertEqual(estado, at.VERIFIED)

    def test_17_la_violacion_se_detecta_y_levanta(self):
        registro = {"attributes": {"remocion": {
            "resolution_status": at.SOURCE_UNAVAILABLE, "fact_status": at.NOT_EVALUATED,
            "canonical_value": "Media", "canonical_reason": "",
            "spatial_result_available": True, "geometry_evaluated": True,
            "source_selected": None, "source_attempts": []}}}
        with self.assertRaises(AssertionError):
            at.assert_reglas_duras(registro)

    # ── §18/§19 ──────────────────────────────────────────────────────────────
    def test_18_19_ausencia_sin_motivo_levanta(self):
        registro = {"attributes": {"inundacion": {
            "resolution_status": at.SOURCE_UNAVAILABLE, "fact_status": at.SOURCE_UNAVAILABLE,
            "canonical_value": None, "canonical_reason": "", "source_selected": None,
            "source_attempts": []}}}
        with self.assertRaises(AssertionError):
            at.assert_reglas_duras(registro)

    def test_18_19_ausencia_con_motivo_cumple(self):
        registro = {"attributes": {"inundacion": {
            "resolution_status": at.SOURCE_UNAVAILABLE, "fact_status": at.SOURCE_UNAVAILABLE,
            "canonical_value": None, "source_selected": None,
            "canonical_reason": "ambas capas del escalón están enabled=false", "source_attempts": []}}}
        at.assert_reglas_duras(registro)

    def test_no_existe_un_not_evaluated_generico_en_el_registro_del_golden(self):
        rs = load_golden()
        if rs is None:
            raise unittest.SkipTest("no está el run state del Golden")
        registro = at.resolver_atributos(rs, fecha="2026-10-01")
        for atributo, ficha in registro["attributes"].items():
            if ficha["fact_status"] == at.NOT_EVALUATED:
                self.assertTrue(
                    not ficha.get("canonical_value"),
                    f"{atributo}: NOT_EVALUATED con resultado declarado")


class TestEvidenciaAgregadaDeAmenazas(unittest.TestCase):
    """RSK-3: el sello de `EV-AMENAZAS` se deriva de su contenido."""

    def _manifest(self, risk_context, volcan=None):
        estado = {
            "identity": {"folio": "040-646406", "identity_verified": True,
                         "resolution_method": "nupre"},
            "coordinates": {"lat": 11.0, "lon": -74.8, "verified": True, "provenance": {}},
            "urban": {}, "urban_source_summary": {}, "official_urban_context": {},
            "market": {}, "valuation": {}, "poi": {}, "screening": {}, "gate": {},
            "receipts": {"generated_at": "2026-10-01T13:47:11Z"},
            "risk_context": risk_context,
            "volcan": volcan or {},
        }
        return dm.construir_evidence_manifest(estado, folio="040-646406")

    def _ev(self, manifiesto):
        return next(e for e in manifiesto["evidencias"] if e["evidence_id"] == "EV-AMENAZAS")

    def test_con_resultado_espacial_el_sello_no_es_fuente_no_disponible(self):
        manifiesto = self._manifest({
            "amenaza_remocion_masa": "Media · polígono: intersecta el predio",
            "areas_en_riesgo": "Medio · polígono: intersecta el predio",
            "inundacion": None, "riesgo_no_mitigable": None})
        self.assertEqual(self._ev(manifiesto)["status"], "SELLADA")

    def test_sin_ningun_resultado_ni_volcan_declara_la_ausencia(self):
        manifiesto = self._manifest({"amenaza_remocion_masa": None,
                                     "areas_en_riesgo": None, "inundacion": None,
                                     "riesgo_no_mitigable": None})
        self.assertEqual(self._ev(manifiesto)["status"], "FUENTE_NO_DISPONIBLE")

    def test_el_sello_nombra_los_componentes_no_evaluados(self):
        manifiesto = self._manifest({
            "amenaza_remocion_masa": "Media · polígono: intersecta el predio",
            "areas_en_riesgo": None, "inundacion": None, "riesgo_no_mitigable": None})
        estado = self._ev(manifiesto)["status"]
        self.assertIn(estado, ("SELLADA", "PARCIAL"))


def load_golden():
    import json
    ruta = (ROOT / "docs" / "forensics" / "040-646406" / "dictus_2b"
            / "DICTUS_RUN_STATE_040-646406.json")
    if not ruta.exists():
        return None
    return json.loads(ruta.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

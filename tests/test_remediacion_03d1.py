# -*- coding: utf-8 -*-
"""
Remediation 03D.1 — closure patch: confianza de identidad normalizada, gate de
valoración PH y separación de identificadores (NUPRE vs código catastral).

Cubre: BLOCKER A (gate PH), BLOCKER B (no escalar PARTIAL a MATCH_BY_NUPRE),
BLOCKER C (nupre y código catastral separados), propagación de resolution_status/
method/confidence, y el caso dorado de unidad (TV 43 # 100-50 TO 8 AP 430).
Sin red: todo se prueba sobre el builder canónico (puro) y el gate.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = ROOT / "api"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(API))


def _analysis(**overrides):
    a = {
        "folio": None,
        "codigo_catastral": None,
        "nupre": None,
        "direccion": None,
        "direccion_base": None,
        "torre": None,
        "apartamento": None,
        "unidad": None,
        "titulares": None,
        "anotaciones_detalle": [],
        "texto_ctl": None,
    }
    a.update(overrides)
    return a


def _build(analysis, predio_real=None, nom=None, identidad=None,
           folio="040-646406", ciudad="barranquilla"):
    from canonical import build_canonical_property_identity
    return build_canonical_property_identity(
        analysis=analysis, folio=folio, predio_real=predio_real, nom=nom,
        identidad=identidad if identidad is not None else {"estado": None},
        ciudad=ciudad)


class TestIdentificadorSeparation(unittest.TestCase):
    """BLOCKER C: NUPRE (alfanumérico) y código catastral (número predial) NUNCA
    se mezclan ni se intercambian."""

    def test_nupre_y_codigo_catastral_separados(self):
        analysis = _analysis(
            codigo_catastral="080010102000001710004000000000",
            nupre="AFT0040BBHC")
        predio = {"disponible": True, "resolution_status": "EXACT",
                  "predio": {"numero_predial_nacional": "080010102000001710004000000000",
                             "nupre": "AFT0040BBHC"}}
        cid = _build(analysis, predio_real=predio)
        self.assertEqual(cid["codigo_catastral"], "080010102000001710004000000000")
        self.assertEqual(cid["nupre"], "AFT0040BBHC")
        self.assertNotEqual(cid["codigo_catastral"], cid["nupre"])

    def test_numero_predial_no_se_guarda_en_nupre(self):
        """Pasto nombra 'nupre' al número predial: se reclasifica a código."""
        analysis = _analysis(direccion="K 26 21 47 AP 101")
        nom = {"nupre": "520010102000000440902900000116",
               "nomenclatura": "K 26 21 47 AP 101", "es_ph": True}
        predio = {"disponible": True,
                  "predio": {"numero_predial_nacional": "520010102000000440902900000116",
                             "nupre": "520010102000000440902900000116"}}
        cid = _build(analysis, predio_real=predio, nom=nom,
                     identidad={"estado": "MATCH_BY_NOMENCLATURA"}, ciudad="pasto")
        self.assertIsNone(cid["nupre"])
        self.assertEqual(cid["codigo_catastral"], "520010102000000440902900000116")

    def test_identificadores_value_source_match_status(self):
        analysis = _analysis(codigo_catastral="080010102000001710004000000000")
        predio = {"disponible": True, "resolution_status": "EXACT",
                  "predio": {"numero_predial_nacional": "080010102000001710004000000000"}}
        cid = _build(analysis, predio_real=predio)
        ids = cid["identificadores"]
        self.assertEqual(ids["codigo_catastral"]["value"], "080010102000001710004000000000")
        self.assertEqual(ids["codigo_catastral"]["match_status"], "EXACT")
        self.assertIn("source", ids["codigo_catastral"])
        self.assertEqual(ids["nupre"]["value"], None)
        self.assertEqual(ids["nupre"]["match_status"], "UNRESOLVED")


class TestNoConfidenceEscalation(unittest.TestCase):
    """BLOCKER B: PARTIAL/UNRESOLVED no se promueven a identidad verificada solo
    porque el CTL contenga NUPRE."""

    def test_partial_no_se_promueve_a_match_by_nupre(self):
        from canonical import ESTADO_MATCH_BY_NUPRE, RESOLUTION_PARTIAL
        analysis = _analysis(nupre="AFT0040BBHC")
        predio = {"disponible": True, "resolution_status": "PARTIAL",
                  "predio": {"numero_predial_nacional": "080010102000001710004000000000",
                             "nupre": "AFT0040BBHC"}}
        cid = _build(analysis, predio_real=predio)
        self.assertNotEqual(cid["estado"], ESTADO_MATCH_BY_NUPRE)
        self.assertEqual(cid["resolution_confidence"], RESOLUTION_PARTIAL)

    def test_unresolved_no_se_promueve(self):
        from canonical import ESTADO_MATCH_BY_NUPRE, RESOLUTION_UNRESOLVED
        analysis = _analysis(nupre="AFT0040BBHC")
        predio = {"disponible": False, "resolution_status": "UNRESOLVED",
                  "predio": {"numero_predial_nacional": None, "nupre": "AFT0040BBHC"}}
        cid = _build(analysis, predio_real=predio)
        self.assertNotEqual(cid["estado"], ESTADO_MATCH_BY_NUPRE)
        self.assertEqual(cid["resolution_confidence"], RESOLUTION_UNRESOLVED)


class TestResolutionPropagation(unittest.TestCase):
    """BLOCKER #6: el resultado canónico conserva resolution_status / method /
    confidence con trazabilidad desde el resolver."""

    def test_propaga_resolution_status_method_confidence(self):
        from canonical import RESOLUTION_VERIFIED_UNIT
        analysis = _analysis(codigo_catastral="080010102000001710004000000000")
        predio = {"disponible": True, "resolution_status": "EXACT",
                  "predio": {"numero_predial_nacional": "080010102000001710004000000000"}}
        cid = _build(analysis, predio_real=predio)
        self.assertEqual(cid["resolution_status"], "EXACT")
        self.assertIn(cid["resolution_method"], ("nupre", "codigo_predial"))
        self.assertEqual(cid["resolution_confidence"], RESOLUTION_VERIFIED_UNIT)

    def test_sin_predio_confianza_unresolved(self):
        from canonical import RESOLUTION_UNRESOLVED
        cid = _build(_analysis(nupre="AFT0040BBHC"), predio_real=None)
        self.assertEqual(cid["resolution_confidence"], RESOLUTION_UNRESOLVED)


class TestPHValuationGate(unittest.TestCase):
    """BLOCKER A / #13: casos obligatorios del gate de valoración PH."""

    def _gate(self, **cid):
        from canonical import unidad_ph_no_resuelta
        base = {"torre": None, "apartamento": None, "unidad": None,
                "resolution_confidence": "UNRESOLVED"}
        base.update(cid)
        return unidad_ph_no_resuelta(base)

    def test_A_exact_procede(self):
        self.assertFalse(self._gate(apartamento="430",
                                    resolution_confidence="VERIFIED_UNIT_IDENTITY"))

    def test_B_partial_bloquea(self):
        self.assertTrue(self._gate(apartamento="430",
                                   resolution_confidence="PARTIAL_IDENTITY"))

    def test_C_none_bloquea(self):
        self.assertTrue(self._gate(apartamento="430", resolution_confidence=None))

    def test_D_ambiguous_bloquea(self):
        self.assertTrue(self._gate(torre="8", resolution_confidence="AMBIGUOUS"))

    def test_E_conflict_bloquea(self):
        self.assertTrue(self._gate(unidad="AP 430", resolution_confidence="CONFLICT"))

    def test_F_no_ph_no_bloquea(self):
        # Predio NO PH correctamente resuelto: comportamiento anterior permanece.
        self.assertFalse(self._gate(resolution_confidence="PARTIAL_IDENTITY"))
        self.assertFalse(self._gate(resolution_confidence="VERIFIED_UNIT_IDENTITY"))
        self.assertFalse(self._gate(resolution_confidence=None))


class TestNoResolverData(unittest.TestCase):
    """#15: torre/apartamento presentes + predio_real=None -> valoración bloqueada
    (resolution_status None NO debe convertirse en autorización)."""

    def test_unidad_ph_sin_resolver_bloquea(self):
        from canonical import unidad_ph_no_resuelta, RESOLUTION_UNRESOLVED
        analysis = _analysis(direccion="TV 43 # 100-50 TO 8 AP 430",
                             torre="8", apartamento="430")
        cid = _build(analysis, predio_real=None)
        self.assertEqual(cid["resolution_confidence"], RESOLUTION_UNRESOLVED)
        self.assertTrue(unidad_ph_no_resuelta(cid))


class TestGoldenUnit(unittest.TestCase):
    """#16: caso dorado de unidad PH (TV 43 # 100-50 TO 8 AP 430)."""

    def test_torre_apartamento_propagan_y_distinguen_unidad(self):
        a430 = _build(_analysis(direccion="TV 43 # 100-50 TO 8 AP 430",
                                torre="8", apartamento="430"),
                      predio_real={"disponible": True, "resolution_status": "EXACT",
                                   "predio": {"numero_predial_nacional": "080010102000001710004000000000"}})
        a431 = _build(_analysis(direccion="TV 43 # 100-50 TO 8 AP 431",
                                torre="8", apartamento="431"),
                      predio_real={"disponible": True, "resolution_status": "EXACT",
                                   "predio": {"numero_predial_nacional": "080010102000001710004000000001"}})
        self.assertEqual(a430["torre"], "8")
        self.assertEqual(a430["apartamento"], "430")
        self.assertEqual(a431["torre"], "8")
        self.assertEqual(a431["apartamento"], "431")
        # AP 430 != AP 431 a nivel de identidad de unidad.
        self.assertNotEqual(a430["apartamento"], a431["apartamento"])


if __name__ == "__main__":
    unittest.main()

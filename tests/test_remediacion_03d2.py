# -*- coding: utf-8 -*-
"""
Remediation 03D.2 — golden case closure: PH detection → canonical identity →
valuation authorization.

Reproduce el fallo observado en el Dictus 040-646406:
  canonical.estado = NO_RECORD + PH = True + torre/apartamento/unidad = None
  => ANTES se emitía $305.5M; AHORA debe bloquearse (ESTIMACIÓN NO EMITIDA).

Invariante: UNRESOLVED PROPERTY IDENTITY + PH + VALUATION EMITTED = INVALID.
Sin red: todo se prueba sobre builders puros.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = ROOT / "api"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(API))

_CTL_REAL = """
Certificado generado con el Pin No: 2605068168134531384Nro Matrícula: 040-646406
CIRCULO REGISTRAL: 040 - BARRANQUILLA  DEPTO: ATLANTICO  MUNICIPIO: BARRANQUILLA
DIRECCION DEL INMUEBLE: TV 43 # 100 - 50 CONJUNTO RESIDENCIAL NAPOLI APARTAMENTOS ETAPA 3
CODIGO CATASTRAL: 080010103000010040001908040002
NUPRE: AFT0005BOHA
AREA Y COEFICIENTE
AREA PRIVADA - METROS CUADRADOS: 58 CENTIMETROS CUADRADOS: 7500 / AREA CONSTRUIDA
"""


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
        "descripcion_ctl": None,
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


class TestPHDetection(unittest.TestCase):
    """#4: is_property_horizontal multi-fuente, sin depender del parser de unidad."""

    def test_ph_detectado_desde_ctl_sin_torre_apartamento(self):
        """La ausencia de torre/apartamento NO es evidencia de No PH."""
        analysis = _analysis(
            direccion="TV 43 # 100 - 50 CONJUNTO RESIDENCIAL NAPOLI APARTAMENTOS ETAPA",
            texto_ctl=_CTL_REAL)
        cid = _build(analysis, predio_real=None)
        self.assertIs(cid["propiedad_horizontal"], True)
        self.assertIsNone(cid["torre"])
        self.assertIsNone(cid["apartamento"])

    def test_sin_evidencia_no_inventa_ph(self):
        analysis = _analysis(direccion="CALLE 10 # 20-30")
        cid = _build(analysis, predio_real=None)
        self.assertIsNone(cid["propiedad_horizontal"])

    def test_condicion_catastral_no_ph(self):
        analysis = _analysis()
        predio = {"disponible": True,
                  "condicion": {"condicion_juridica": "No Propiedad Horizontal"},
                  "predio": {}}
        cid = _build(analysis, predio_real=predio)
        self.assertIs(cid["propiedad_horizontal"], False)


class TestValuationAuthorization(unittest.TestCase):
    """#5/#6: can_value_property -> {allowed, reason, identity_level}."""

    def _auth(self, cid):
        from canonical import can_value_property
        return can_value_property(cid)

    def test_ph_verificado_procede(self):
        analysis = _analysis(torre="8", apartamento="430")
        predio = {"disponible": True, "resolution_status": "EXACT",
                  "predio": {"numero_predial_nacional": "080010103000010040001908040002"}}
        cid = _build(analysis, predio_real=predio)
        auth = self._auth(cid)
        self.assertIs(auth["allowed"], True)
        self.assertEqual(auth["identity_level"], "VERIFIED_UNIT_IDENTITY")

    def test_ph_no_record_bloquea(self):
        """#8/#22: PH=True + NO_RECORD + torre/apartamento=None => bloqueado."""
        from canonical import ESTADO_NO_RECORD, RESOLUTION_UNRESOLVED
        analysis = _analysis(
            direccion="TV 43 # 100 - 50 CONJUNTO RESIDENCIAL NAPOLI APARTAMENTOS ETAPA",
            texto_ctl=_CTL_REAL)
        cid = _build(analysis, predio_real=None)
        self.assertEqual(cid["estado"], ESTADO_NO_RECORD)
        self.assertEqual(cid["resolution_confidence"], RESOLUTION_UNRESOLVED)
        self.assertIs(cid["propiedad_horizontal"], True)
        auth = self._auth(cid)
        self.assertIs(auth["allowed"], False)
        self.assertIn("PH", auth["reason"])
        self.assertEqual(auth["identity_level"], RESOLUTION_UNRESOLVED)

    def test_no_ph_procede(self):
        analysis = _analysis(direccion="CALLE 10 # 20-30")
        cid = _build(analysis, predio_real=None)
        self.assertIs(self._auth(cid)["allowed"], True)


class TestObservedFailure(unittest.TestCase):
    """#22: fixture exacto del fallo observado -> ESTIMACIÓN NO EMITIDA."""

    def test_observed_failure_bloquea_valoracion(self):
        from canonical import can_value_property
        from dictamen_data import get_valuation
        analysis = _analysis(
            direccion="TV 43 # 100 - 50 CONJUNTO RESIDENCIAL NAPOLI APARTAMENTOS ETAPA",
            texto_ctl=_CTL_REAL,
            nupre="AFT0005BOHA",
            codigo_catastral="080010103000010040001908040002")
        cid = _build(analysis, predio_real=None)
        auth = can_value_property(cid)
        self.assertIs(auth["allowed"], False)
        v = get_valuation(58.75, "Miramar", estrato=4, ciudad="barranquilla",
                          unidad_ph_no_resuelta=True)
        self.assertIs(v["metodologia_aplica"], False)
        self.assertEqual(v["consolidado"], 0)
        self.assertIn("PH", v["motivo_no_aplica"])


class TestIdentifierConsistency(unittest.TestCase):
    """#14/#16: nupre y codigo_catastral separados y coherentes con receipts."""

    def test_canonical_y_receipt_identifiers(self):
        from receipts import build_execution_receipts
        analysis = _analysis(
            texto_ctl=_CTL_REAL,
            nupre="AFT0005BOHA",
            codigo_catastral="080010103000010040001908040002")
        cid = _build(analysis, predio_real=None)
        self.assertEqual(cid["nupre"], "AFT0005BOHA")
        self.assertEqual(cid["codigo_catastral"], "080010103000010040001908040002")
        r = build_execution_receipts(
            ciudad="barranquilla", predio_real=None, volcan={}, pois={},
            titulux={}, geo_eval={}, canonical_identity=cid,
            versionado={}, lat=10.987, lon=-74.811, ctl_adjuntado=True,
            catastro_live={"disponible": True, "numero_predial": "080010103000009280001900000000"})
        self.assertEqual(r["identidad"]["nupre"], cid["nupre"])
        self.assertEqual(r["identidad"]["codigo_catastral"], cid["codigo_catastral"])
        # El número del terreno (bbox) NO se guarda como NUPRE.
        self.assertEqual(r["catastro"]["espacial"], True)


class TestValuationInvariant(unittest.TestCase):
    """#21: valuation.consolidado > 0 implica autorización; PH no resuelta => 0."""

    def test_invariante_bloquea_valor_sin_autorizacion(self):
        from consistency import _inv_valuation_coherente
        ok, _ = _inv_valuation_coherente({
            "valuation_authorization": {"allowed": False, "identity_level": "UNRESOLVED"},
            "res_avaluo": {"consolidado": 305500000, "metodologia_aplica": True},
        })
        self.assertFalse(ok)

    def test_invariante_ok_con_autorizacion(self):
        from consistency import _inv_valuation_coherente
        ok, _ = _inv_valuation_coherente({
            "valuation_authorization": {"allowed": True, "identity_level": "VERIFIED_UNIT_IDENTITY"},
            "res_avaluo": {"consolidado": 305500000, "metodologia_aplica": True},
        })
        self.assertTrue(ok)

    def test_invariante_ph_no_resuelta_no_emite(self):
        from consistency import _inv_valuation_coherente
        ok, _ = _inv_valuation_coherente({
            "valuation_authorization": {"allowed": False, "identity_level": "UNRESOLVED"},
            "res_avaluo": {"consolidado": 0, "metodologia_aplica": False},
        })
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()

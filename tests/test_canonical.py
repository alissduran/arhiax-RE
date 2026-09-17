# -*- coding: utf-8 -*-
"""
Tests del modelo canónico (api/canonical.py) — identidad predial y contexto
administrativo. Sin red: los builders son puros y solo normalizan insumos ya
resueltos.
"""
import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
API_DIR = ROOT_DIR / "api"
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(API_DIR))


def _analysis_aceptacion():
    """Caso de aceptación 240-211101 (CABRERA VIVEROS JUAN SEBASTIAN, CC 87070538)."""
    return {
        "folio": "240-211101",
        "codigo_catastral": None,
        "nupre": None,
        "direccion": "K 26 21 47 AP 101",
        "titulares": "CABRERA VIVEROS JUAN SEBASTIAN",
        "anotaciones_detalle": [
            {"num": "001", "tipo": "COMPRAVENTA", "estado": "VIGENTE",
             "texto": "A: CABRERA VIVEROS JUAN SEBASTIAN CC 87070538"},
        ],
        "hipoteca_vigente": None,
        "acreedor_snr": None,
    }


_NOM = {"nupre": "520010102000000440902900000116",
        "nomenclatura": "K 26 21 47 AP 101", "es_ph": True,
        "comuna": "Comuna 1", "estrato": "3"}

_PREDIO = {
    "disponible": True,
    "predio": {"numero_predial_nacional": "520010102000000440902900000116",
               "matricula_inmobiliaria": "240-211101",
               "direccion_oficial": "K 26 21 47 AP 101"},
    "entorno": {"comuna": "Comuna 1", "barrio": "Centro", "estrato": "3",
                "clase_suelo": "Urbano"},
    "riesgos": {}, "condicion": {},
}


class TestExtraerTitular(unittest.TestCase):

    def test_natural_person_con_documento(self):
        from canonical import extraer_titular_canonico, PERSONA_NATURAL
        t = extraer_titular_canonico(_analysis_aceptacion())
        self.assertEqual(t["nombre"], "CABRERA VIVEROS JUAN SEBASTIAN")
        self.assertEqual(t["tipo_documento"], "cc")
        self.assertEqual(t["numero_documento"], "87070538")
        self.assertEqual(t["tipo_persona"], PERSONA_NATURAL)

    def test_nit_es_persona_juridica(self):
        from canonical import extraer_titular_canonico, PERSONA_JURIDICA
        a = _analysis_aceptacion()
        a["anotaciones_detalle"][0]["texto"] = "A: INMOBILIARIA XYZ SAS NIT 900.123.456-7"
        t = extraer_titular_canonico(a)
        self.assertEqual(t["tipo_documento"], "nit")
        self.assertEqual(t["numero_documento"], "9001234567")
        self.assertEqual(t["tipo_persona"], PERSONA_JURIDICA)

    def test_sin_documento_no_asume_juridica(self):
        """Bug I: sin documento NO se deduce persona jurídica por defecto."""
        from canonical import extraer_titular_canonico
        a = _analysis_aceptacion()
        a["anotaciones_detalle"] = []
        a["titulares"] = "PEREZ GOMEZ MARIA"
        a["texto_ctl"] = None
        t = extraer_titular_canonico(a)
        self.assertEqual(t["nombre"], "PEREZ GOMEZ MARIA")
        self.assertIsNone(t["tipo_documento"])
        self.assertIsNone(t["tipo_persona"])


class TestBuildCanonicalIdentity(unittest.TestCase):

    def test_match_exact_caso_aceptacion(self):
        from canonical import build_canonical_property_identity, ESTADO_MATCH_EXACT
        cid = build_canonical_property_identity(
            analysis=_analysis_aceptacion(), folio="240-211101",
            predio_real=_PREDIO, nom=_NOM, identidad={"estado": None},
            ciudad="pasto")
        self.assertEqual(cid["estado"], ESTADO_MATCH_EXACT)
        self.assertEqual(cid["nupre"], "520010102000000440902900000116")
        self.assertEqual(cid["folio_snr"], "240-211101")
        self.assertEqual(cid["titular"]["tipo_persona"], "NATURAL_PERSON")

    def test_identity_conflict_se_preserva(self):
        from canonical import build_canonical_property_identity, ESTADO_IDENTITY_CONFLICT
        cid = build_canonical_property_identity(
            analysis=_analysis_aceptacion(), folio="240-211101",
            predio_real=_PREDIO, nom={"nupre": "OTRO"},
            identidad={"estado": "IDENTITY_CONFLICT", "detalle": "conflicto"},
            ciudad="pasto")
        self.assertEqual(cid["estado"], ESTADO_IDENTITY_CONFLICT)

    def test_no_record_sin_predio(self):
        from canonical import build_canonical_property_identity, ESTADO_NO_RECORD
        cid = build_canonical_property_identity(
            analysis=_analysis_aceptacion(), folio="240-211101",
            predio_real=None, nom=None, identidad={"estado": None},
            ciudad="pasto")
        self.assertEqual(cid["estado"], ESTADO_NO_RECORD)
        self.assertIsNone(cid["nupre"])


class TestAdministrativeContext(unittest.TestCase):

    def test_comuna_y_estrato_desde_geoportal(self):
        from canonical import build_administrative_context
        ctx = build_administrative_context(
            ciudad="pasto", predio_real=_PREDIO, nom=_NOM,
            barrio="Centro", estrato=3)
        self.assertEqual(ctx["comuna"], "Comuna 1")
        self.assertEqual(ctx["barrio"], "Centro")
        self.assertEqual(ctx["estrato"], "3")
        self.assertEqual(ctx["clase_suelo"], "Urbano")

    def test_comuna_desde_nomenclatura_si_geoportal_no_responde(self):
        from canonical import build_administrative_context
        ctx = build_administrative_context(
            ciudad="pasto", predio_real={"entorno": {}}, nom=_NOM,
            barrio="", estrato=None)
        self.assertEqual(ctx["comuna"], "Comuna 1")
        self.assertEqual(ctx["estrato"], "3")


if __name__ == "__main__":
    unittest.main()

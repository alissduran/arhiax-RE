# -*- coding: utf-8 -*-
"""03I.2B-A — OFFICIAL_PREDIO ↔ CANONICAL IDENTITY BINDING (040-646406).

`evaluar_geometria_oficial_predio()` (H-1) verificaba que la geometría estuviera
ligada **internamente** a `predio_real`, pero no que ese predio fuera el MISMO
`CanonicalPropertyIdentity` que gobierna el Dictus: con `canonical.nupre = AFT_X` y
`predio_real.nupre = AFT_Y` la coordenada podía declararse `OFFICIAL_PREDIO`.

Regla que se prueba aquí:

    OFFICIAL_PREDIO = geometría oficial válida
                      AND predio_real compatible con CanonicalPropertyIdentity

Secciones: §8.A–G (casos bloqueantes del prompt) y §R (regresión del render/receipt).
"""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT / "tests"))

TMP_DIR = ROOT / "tmp_pdf_03i2ba"

GOLDEN_GUID = "{GOLDEN-PREDIO-GUID}"
GOLDEN_CODIGO = "080010103000010040001908040002"
GOLDEN_NUPRE = "AFT0005BOHA"
OTRO_CODIGO = "080010103000010040001908040099"
OTRO_NUPRE = "AFT0009ZZZZ"
GOLDEN_LAT, GOLDEN_LON = 10.9870, -74.8115


def _canonical(*, nupre=GOLDEN_NUPRE, predial=GOLDEN_CODIGO, folio="040-646406",
               confidence="VERIFIED_UNIT_IDENTITY", con_identificadores=True) -> dict:
    """CanonicalPropertyIdentity mínimo pero REAL en su forma (mismas claves)."""
    cid = {
        "folio_snr": folio,
        "nupre": nupre,
        "codigo_catastral": predial,
        "resolution_confidence": confidence,
        "identity_verified": confidence == "VERIFIED_UNIT_IDENTITY",
    }
    if con_identificadores:
        cid["identificadores"] = {
            "nupre": {"value": nupre, "source": "CTL (NUPRE)"},
            "codigo_catastral": {"value": predial, "source": "CTL (CODIGO CATASTRAL)"},
        }
    return cid


def _predio(*, nupre=GOLDEN_NUPRE, predial=GOLDEN_CODIGO, prov_nupre=None,
            prov_predial=None, lat=GOLDEN_LAT, lon=GOLDEN_LON,
            feature_id_kind="cr_predio_guid", globalid=GOLDEN_GUID,
            predio_nupre=None, predio_predial=None, origen="DIRECCION_OFICIAL_LIGADA_AL_PREDIO"):
    """`predio_real` con geometría oficial internamente válida (H-1) de un predio B."""
    return {
        "disponible": True,
        "lat": lat, "lon": lon,
        "coordenada_origen": origen,
        "direccion_oficial": "Transversal 43 100 50 TO 8 AP 430",
        "predio": {
            "globalid": globalid,
            "numero_predial_nacional": predial if predio_predial is None else predio_predial,
            "nupre": nupre if predio_nupre is None else predio_nupre,
        },
        "coordenada_provenance": {
            "source_system": "CATASTRO_MUNICIPAL_BARRANQUILLA_ARCGIS",
            "layer": "105 · direccion",
            "feature_id": globalid,
            "feature_id_kind": feature_id_kind,
            "geometry_type": "Point",
            "resolution_method": "DIRECCION_OFICIAL_LIGADA_POR_GUID",
            "predio_globalid": globalid,
            "numero_predial": predial if prov_predial is None else prov_predial,
            "nupre": nupre if prov_nupre is None else prov_nupre,
            "link_verificado": True,
        },
    }


def _eval(predio_real, canonical_identity, **kw):
    from market_context import evaluar_geometria_oficial_predio
    return evaluar_geometria_oficial_predio(predio_real=predio_real,
                                            canonical_identity=canonical_identity,
                                            ciudad="barranquilla", **kw)


def _loc(predio_real, canonical_identity, **kw):
    from market_context import resolve_market_location
    base = dict(lat_geo=None, lon_geo=None, db_lat=None, db_lon=None,
                db_direccion=None, barrio="Miramar", es_bogota=False,
                es_medellin=False, es_pasto=False, ciudad="barranquilla",
                geocoder=lambda d, ciudad=None: None)
    base.update(kw)
    return resolve_market_location(canonical_identity=canonical_identity,
                                   predio_real=predio_real, **base)


class TestABindingCanonico(unittest.TestCase):
    """§8.A–G: el binding decide la promoción, y nunca elige en silencio."""

    # ── A ────────────────────────────────────────────────────────────────────
    def test_a_identificadores_iguales_promueve(self):
        """A. canónico NUPRE == predio NUPRE y predial == predial → OFFICIAL_PREDIO."""
        v = _eval(_predio(), _canonical())
        self.assertTrue(v["eligible"], v.get("reason"))
        self.assertEqual(v["canonical_binding"]["status"], "VERIFIED")
        self.assertEqual(sorted(v["canonical_binding"]["fields"]),
                         sorted(["nupre", "numero_predial"]))
        loc = _loc(_predio(), _canonical())
        self.assertEqual(loc["coordinate_source"], "OFFICIAL_PREDIO")
        self.assertIs(loc["coordinate_source_verified"], True)
        self.assertEqual(loc["canonical_binding_status"], "VERIFIED")
        self.assertEqual(sorted(loc["canonical_binding_fields"]),
                         sorted(["nupre", "numero_predial"]))
        self.assertIn("canonical_binding_status",
                      loc["coordinate_provenance"])

    # ── B ────────────────────────────────────────────────────────────────────
    def test_b_nupre_distinto_no_promueve(self):
        """B. canónico NUPRE != predio NUPRE → NO OFFICIAL_PREDIO."""
        pr = _predio(nupre=OTRO_NUPRE)
        v = _eval(pr, _canonical())
        self.assertFalse(v["eligible"])
        self.assertEqual(v["canonical_binding"]["status"], "MISMATCH")
        self.assertIn("CANONICAL_IDENTITY_MISMATCH", v["reason"])
        loc = _loc(pr, _canonical())
        self.assertNotEqual(loc["coordinate_source"], "OFFICIAL_PREDIO")
        self.assertIs(loc["coordinate_source_verified"], False)
        self.assertEqual(loc["canonical_binding_status"], "MISMATCH")

    # ── C ────────────────────────────────────────────────────────────────────
    def test_c_predial_distinto_no_promueve(self):
        """C. canónico predial != predio predial → NO OFFICIAL_PREDIO."""
        pr = _predio(predial=OTRO_CODIGO)
        v = _eval(pr, _canonical())
        self.assertFalse(v["eligible"])
        self.assertEqual(v["canonical_binding"]["status"], "MISMATCH")
        self.assertIn("numero_predial", v["reason"])
        loc = _loc(pr, _canonical())
        self.assertNotEqual(loc["coordinate_source"], "OFFICIAL_PREDIO")

    # ── D2 ───────────────────────────────────────────────────────────────────
    def test_d2_guid_de_enlace_no_se_compara_como_predial(self):
        """D2 (regresión de la corrida viva del Golden): el `predio_globalid` es la
        clave de ENLACE con la feature, no un número predial. Sus dígitos no pueden
        compararse con el número predial canónico (falso MISMATCH detectado en vivo)."""
        from market_context import _es_guid, _norm_predial
        pr = _predio()
        pr["coordenada_provenance"]["predio_globalid"] = \
            "6c663607-5509-401f-b57d-384d2beeeac1"
        pr["coordenada_provenance"]["feature_id"] = \
            "6c663607-5509-401f-b57d-384d2beeeac1"
        pr["predio"]["globalid"] = "{6C663607-5509-401F-B57D-384D2BEEEAC1}"
        self.assertTrue(_es_guid("6c663607-5509-401f-b57d-384d2beeeac1"))
        self.assertTrue(_es_guid("{6C663607-5509-401F-B57D-384D2BEEEAC1}"))
        self.assertFalse(_es_guid("080010103000010040001908040002"))
        self.assertEqual(_norm_predial("6c663607-5509-401f-b57d-384d2beeeac1"),
                         "666360755094015738421")  # lo que NO debe usarse
        v = _eval(pr, _canonical())
        self.assertTrue(v["eligible"], v.get("reason"))
        self.assertEqual(v["canonical_binding"]["status"], "VERIFIED")
        self.assertNotIn("666360755094015738421", str(v["canonical_binding"]))

    # ── D ────────────────────────────────────────────────────────────────────
    def test_d_provenance_en_desacuerdo_con_el_predio(self):
        """D. provenance NUPRE distinto de predio_real NUPRE → NO OFFICIAL_PREDIO.

        La geometría puede estar internamente bien documentada y aun así declarar
        dos predios distintos: no se elige uno, se declara el desacuerdo.
        """
        pr = _predio(prov_nupre=OTRO_NUPRE)
        v = _eval(pr, _canonical())
        self.assertFalse(v["eligible"])
        self.assertEqual(v["canonical_binding"]["status"], "MISMATCH")
        self.assertIn("CANONICAL_IDENTITY_MISMATCH", v["reason"])
        self.assertIn("discrepan", v["reason"])
        # También con el canónico ausente: el desacuerdo interno basta.
        self.assertFalse(_eval(pr, {})["eligible"])

    # ── E ────────────────────────────────────────────────────────────────────
    def test_e_identidad_verificada_de_un_predio_y_geometria_de_otro(self):
        """E. VERIFIED_UNIT_IDENTITY del predio A + geometría impecable del predio B
        → NO OFFICIAL_PREDIO. Es el caso que 03I.2B no cubría."""
        canon_a = _canonical(confidence="VERIFIED_UNIT_IDENTITY")
        geom_b = _predio(nupre=OTRO_NUPRE, predial=OTRO_CODIGO)
        # La geometría de B es intachable MIENTRAS se la evalúe contra B...
        self.assertTrue(_eval(geom_b, _canonical(nupre=OTRO_NUPRE,
                                                 predial=OTRO_CODIGO))["eligible"])
        # ...y NO promueve cuando la identidad canónica del caso es la de A.
        v = _eval(geom_b, canon_a)
        self.assertFalse(v["eligible"])
        self.assertIn("CANONICAL_IDENTITY_MISMATCH", v["reason"])
        loc = _loc(geom_b, canon_a)
        self.assertNotEqual(loc["coordinate_source"], "OFFICIAL_PREDIO")
        self.assertIs(loc["coordinate_source_verified"], False)
        self.assertIn("CANONICAL_IDENTITY_MISMATCH",
                      loc["official_predio_rejected_reason"])

    # ── G ────────────────────────────────────────────────────────────────────
    def test_g_fuentes_insuficientes_no_inventan_coincidencia(self):
        """G. Sin campos comparables NO se inventa coincidencia: NOT_COMPARABLE,
        que no es VERIFIED y por tanto no promueve."""
        casos = [
            (_predio(), {}),                                   # canónico sin ids
            (_predio(), {"folio_snr": "040-646406"}),           # canónico sin ids
        ]
        for pr, can in casos:
            v = _eval(pr, can)
            self.assertFalse(v["eligible"])
            self.assertEqual(v["canonical_binding"]["status"], "NOT_COMPARABLE")
            self.assertNotEqual(v["canonical_binding"]["status"], "VERIFIED")
            self.assertIn("CANONICAL_IDENTITY_NOT_COMPARABLE", v["reason"])
            self.assertEqual(v["canonical_binding"]["fields"], [])
            loc = _loc(pr, can)
            self.assertNotEqual(loc["coordinate_source"], "OFFICIAL_PREDIO")
            self.assertEqual(loc["canonical_binding_status"], "NOT_COMPARABLE")
        # Y sin `canonical_identity` en absoluto (no declarada) tampoco promueve.
        v = _eval(_predio(), None)
        self.assertFalse(v["eligible"])
        self.assertEqual(v["canonical_binding"]["status"], "NOT_COMPARABLE")

    def test_g2_canonico_sin_el_identificador_que_el_predio_si_declara(self):
        """G2. Si el canónico no declara el número predial, ese campo NO se exige ni
        se inventa: el binding se apoya SOLO en lo que ambas partes publican (NUPRE),
        y el campo no comparable queda declarado en el detalle."""
        can = _canonical(con_identificadores=False)
        can.pop("codigo_catastral")
        v = _eval(_predio(), can)
        self.assertTrue(v["eligible"], v.get("reason"))
        self.assertEqual(v["canonical_binding"]["fields"], ["nupre"])
        det = v["canonical_binding"]["detail"]
        self.assertNotIn("numero_predial", det,
                         "un identificador que el canónico no publica no se compara")
        self.assertEqual(sorted(det), ["nupre"])

    def test_g3_normalizacion_no_finge_equivalencias(self):
        """G3. NUPRE se compara sin espacios ni caja; el predial solo por dígitos
        (separadores no son información). Y un valor sin dígitos NO se hace pasar
        por número predial."""
        pr = _predio(nupre=" aft0005boha ", predial="0800 1010 3000 0100 4000 1908 0400 02")
        self.assertTrue(_eval(pr, _canonical())["eligible"])
        from market_context import _norm_predial
        self.assertIsNone(_norm_predial("LOTE-ABC"))
        self.assertEqual(_norm_predial("0800-1010"), "08001010")

    def test_r1_receipt_declara_binding_siempre(self):
        """§9. El recibo lleva el binding incluso cuando NO se promueve."""
        from receipts import build_execution_receipts
        pr = _predio(nupre=OTRO_NUPRE)
        loc = _loc(pr, _canonical())
        mc = {"coordinates": {"lat": loc["lat"], "lon": loc["lon"]},
              "coordinate_source": loc["coordinate_source"],
              "coordinate_source_verified": loc["coordinate_source_verified"],
              "coordinate_provenance": loc["coordinate_provenance"],
              "canonical_binding_status": loc["canonical_binding_status"],
              "canonical_binding_fields": loc["canonical_binding_fields"],
              "official_predio_rejected_reason": loc["official_predio_rejected_reason"]}
        rec = build_execution_receipts(
            ciudad="barranquilla", predio_real=pr, volcan={}, pois={}, titulux={},
            geo_eval={}, canonical_identity={"market_context": mc},
            versionado={}, lat=loc["lat"], lon=loc["lon"], ctl_adjuntado=True)
        geo = rec["geocodificacion"]
        self.assertEqual(geo["canonical_binding_status"], "MISMATCH")
        self.assertIn("canonical_binding_fields", geo)
        self.assertIn("official_predio_rejected_reason", geo)
        self.assertIsNotNone(geo["official_predio_rejected_reason"])
        # Y en el texto del recibo impreso se nombra el binding.
        from receipts import receipt_rows
        txt = " ".join(f"{k} {v}" for k, v in receipt_rows(rec))
        self.assertIn("binding canónico MISMATCH", txt)

    def test_r2_no_usa_not_comparable_como_verified(self):
        """§7. NINGÚN camino puede producir `coordinate_source = OFFICIAL_PREDIO`
        con `canonical_binding_status != VERIFIED`."""
        can_variants = [_canonical(), {}, {"nupre": OTRO_NUPRE},
                        {"codigo_catastral": OTRO_CODIGO},
                        {"nupre": GOLDEN_NUPRE, "codigo_catastral": OTRO_CODIGO}]
        pred_variants = [_predio(), _predio(nupre=OTRO_NUPRE),
                         _predio(predial=OTRO_CODIGO), _predio(prov_nupre=OTRO_NUPRE)]
        for can in can_variants:
            for pr in pred_variants:
                loc = _loc(pr, can)
                if loc["coordinate_source"] == "OFFICIAL_PREDIO":
                    self.assertEqual(loc["canonical_binding_status"], "VERIFIED",
                                     f"promoción sin binding verificado: can={can} "
                                     f"predio={pr['predio']}")


class TestBGoldenVivo(unittest.TestCase):
    """§8.F — Golden 040-646406: el binding se verifica con las fuentes REALES.

    Es un caso de red: se marca `network` para no depender de que el geoportal
    responda durante la suite offline; el resultado de la corrida de aceptación
    (CASO A, binding VERIFIED) queda registrado en el manifest del Golden.
    """

    @unittest.skipUnless(os.environ.get("ARHIAX_NETWORK_TESTS") == "1",
                         "requiere red: se ejecuta en la corrida de aceptación")
    def test_f_golden_binding_verificado(self):
        import catastro_predio as cp
        from catastro_predio import enriquecer_desde_ctl
        from legal_analyzer import analizar_certificado
        from canonical import build_canonical_property_identity
        ctl = (ROOT / "docs" / "forensics" / "040-646406" / "golden_03i1"
               / "inputs" / "CTL_040-646406_ORIGINAL.pdf")
        if not ctl.exists():
            self.skipTest("CTL original no disponible en el checkout")
        cp._CACHE.clear()
        analysis = analizar_certificado(str(ctl))
        predio_real = enriquecer_desde_ctl(analysis.get("codigo_catastral"),
                                           analysis.get("nupre"))
        cid = build_canonical_property_identity(
            analysis=analysis, folio=analysis.get("folio"), predio_real=predio_real,
            nom=None, identidad=None, ciudad="barranquilla", metodo_resolucion=None)
        loc = _loc(predio_real, cid)
        self.assertEqual(loc["coordinate_source"], "OFFICIAL_PREDIO")
        self.assertEqual(loc["canonical_binding_status"], "VERIFIED")
        self.assertIn("nupre", loc["canonical_binding_fields"])


def _compilar(tmp_name="03i2ba.pdf"):
    """Compila el caso Golden con fuentes mockeadas (sin red)."""
    import catastro_predio
    import geocoder
    import legal_analyzer
    import pdf_compiler
    import integrations.catastro_live as catastro_live
    from test_remediacion_03h2a import (FuentesMock, GOLDEN_CODIGO as _C,
                                        GOLDEN_DIRECCION, GOLDEN_LAT as _LA,
                                        GOLDEN_LON as _LO, GOLDEN_NUPRE as _N)
    fuentes = FuentesMock()
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    out_pdf = TMP_DIR / tmp_name
    if out_pdf.exists():
        out_pdf.unlink()
    analysis = dict(legal_analyzer.analizar_certificado(None))
    analysis.update({"folio": "040-646406", "direccion": GOLDEN_DIRECCION,
                     "codigo_catastral": _C, "nupre": _N,
                     "descripcion_ctl": ("APARTAMENTO 430 TORRE 8 CONJUNTO NAPOLI "
                                         "MIRAMAR PROPIEDAD HORIZONTAL"),
                     "texto_ctl": "APARTAMENTO 430 - PROPIEDAD HORIZONTAL",
                     "tipo_predio_snr": "APARTAMENTO"})
    record = {"id": 1, "folio_matricula": "040-646406", "direccion": GOLDEN_DIRECCION,
              "barrio": "Miramar", "estrato": 4, "area": 58.75,
              "valor_consolidado": None, "sombra_9am_cargada": 0,
              "sombra_3pm_cargada": 0, "mapa_cargado": 0, "acreedor_real": None,
              "certificado_path": None, "ciudad": "barranquilla"}
    catastro_predio._CACHE.clear()
    with mock.patch.object(legal_analyzer, "analizar_certificado", return_value=analysis), \
            mock.patch.object(catastro_predio, "_query_capa",
                              side_effect=fuentes.query_capa), \
            mock.patch.object(catastro_predio, "_query_punto",
                              side_effect=fuentes.query_punto), \
            mock.patch.object(geocoder, "geocodificar_direccion",
                              lambda d, ciudad=None: (_LA, _LO)), \
            mock.patch.object(pdf_compiler, "generate_maps", lambda *a, **k: None), \
            mock.patch.object(catastro_live, "verificar_catastro_barranquilla",
                              lambda *a, **k: {"disponible": False, "numero_predial": None,
                                               "error": "servicio sin respuesta",
                                               "fuente": {}}), \
            mock.patch.object(pdf_compiler, "get_poi_result",
                              lambda *a, **k: {
                                  "items": {c: [] for c in ("Salud", "Educacion",
                                                            "Comercio", "Recreacion")},
                                  "category_status": {c: "NO_MATCH" for c in (
                                      "Salud", "Educacion", "Comercio", "Recreacion")},
                                  "sources_attempted": 1, "sources_succeeded": 1}):
        pdf_compiler.compile_pdf(record, str(out_pdf), assets_dir=TMP_DIR)
    return out_pdf


class TestRGoldenImpreso(unittest.TestCase, ):
    """§9/§10 — el binding llega al dictamen impreso del caso real (sin red)."""

    def setUp(self):
        self._env = {k: os.environ.get(k) for k in ("ARHIAX_ENV",)}
        os.environ["ARHIAX_ENV"] = "development"

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_el_pdf_declara_el_binding_del_caso(self):
        import pymupdf
        pdf = _compilar("03i2ba_golden.pdf")
        txt = " ".join(p.get_text() for p in pymupdf.open(str(pdf)))
        self.assertIn("OFFICIAL_PREDIO", txt)
        self.assertIn("binding canónico VERIFIED", txt)
        self.assertNotIn("binding canónico NO DECLARADO", txt)


if __name__ == "__main__":
    unittest.main(verbosity=2)

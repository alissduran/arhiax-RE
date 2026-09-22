# -*- coding: utf-8 -*-
"""Remediation 03I.1 — DICTUS Product Coherence Closure.

Regresiones de los defectos F1–F8 y de los contratos nuevos del QA:

  * F1  TIT_B01 con estados de contraste (un área ausente != ambas ausentes).
  * F2  6.2/6.3 desde el mismo objeto; sin "CONSOLIDACION / DESARROLLO" fijo.
  * F3  severidad ÚNICA de riesgo (Titulux == Hallazgo == Score).
  * F4  estrato por MANZANA oficial del número predial (sin default ni inferencia).
  * F   metodología de mercado con id/versión/sha256 reales y gate propio.
  * F5  dirección oficial promovida al modelo canónico + unidad compuesta.
  * F7  forma societaria conservada (S.A.S.) en el analizador legal.
  * F8  estado único del riesgo volcánico (NO_INTERSECTION != LOW_HAZARD).
  * A   versionado del manifest (commit_sha y VERSION_MATRIX no vacíos).
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = ROOT / "api"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(API))


# ── F1: TIT_B01 con estados de contraste ─────────────────────────────────────

class TestTitB01Estados(unittest.TestCase):

    def _caso(self, area_reg, area_cat):
        from arhia_title.contracts import Caso, Predio
        return Caso(id="1", tipo="informe_base",
                    predio=Predio(folio_matricula="040-646406",
                                  codigo_catastral="080010103000010040001908040002",
                                  area_registral=area_reg, area_catastral=area_cat))

    def _h(self, area_reg, area_cat):
        from arhia_title.rules import identidad_inmueble
        return identidad_inmueble(self._caso(area_reg, area_cat))[0]

    def test_registral_only_no_niega_el_area_registral(self):
        """Golden: área registral 58.75 m² y catastral no disponible."""
        h = self._h(58.75, 0.0)
        self.assertIn("REGISTRAL_ONLY", h.descripcion)
        self.assertIn("58.75", h.descripcion)
        self.assertNotIn("No hay área registral ni catastral", h.descripcion)
        self.assertIn("catastral no disponible", h.descripcion.lower())

    def test_catastral_only(self):
        h = self._h(0.0, 60.0)
        self.assertIn("CATASTRAL_ONLY", h.descripcion)
        self.assertIn("registral no disponible", h.descripcion.lower())

    def test_both_unavailable(self):
        h = self._h(0.0, 0.0)
        self.assertIn("BOTH_UNAVAILABLE", h.descripcion)
        self.assertIn("no hay área registral ni catastral", h.descripcion.lower())

    def test_both_available_ok(self):
        h = self._h(58.75, 58.90)
        self.assertIn("BOTH_AVAILABLE", h.descripcion)
        self.assertEqual(h.estado, "OK")

    def test_both_available_mismatch(self):
        h = self._h(58.75, 90.0)
        self.assertIn("BOTH_AVAILABLE", h.descripcion)
        self.assertEqual(h.estado, "INCONSISTENTE")
        self.assertEqual(h.severidad, "alta")


# ── F3: severidad única de riesgo ────────────────────────────────────────────

class TestSeveridadUnica(unittest.TestCase):

    def test_tabla_baja_no_es_alta(self):
        from risk_severity import decidir
        d = decidir("Baja", intersecta=True, evaluado=True)
        self.assertEqual(d["severidad"], "MEDIO")
        self.assertEqual(d["peso_hidrologico"], 5)
        self.assertEqual(d["regla"], "RSK-SEV-1")
        self.assertTrue(d["regla_version"])

    def test_alta_es_alto(self):
        from risk_severity import decidir
        self.assertEqual(decidir("Alta")["severidad"], "ALTO")
        self.assertEqual(decidir("Media")["severidad"], "MEDIO")

    def test_no_evaluado_no_es_sin_afectacion(self):
        from risk_severity import decidir
        self.assertEqual(decidir(None, evaluado=False)["severidad"], "OBSERVACION")
        self.assertEqual(decidir("", intersecta=False)["severidad"], "INFORMATIVO")

    def test_nivel_no_tabulado_no_se_minimiza(self):
        from risk_severity import decidir
        d = decidir("Catastrofico")
        self.assertEqual(d["severidad"], "OBSERVACION")
        self.assertIsNone(d["peso_hidrologico"])

    def test_titulux_y_hallazgo_comparten_la_decision(self):
        """El mismo nivel produce la MISMA decisión de severidad en los dos
        productores (el vocabulario difiere por contrato: Titulux usa
        alta/media/baja, el capítulo de hallazgos usa ALTO/MEDIO/BAJO)."""
        from arhia_title.contracts import Caso, Predio
        from arhia_title.rules import amenazas_pot
        from pdf_compiler import _severidad_geo_desde_nivel
        from risk_severity import severidad_titulux
        for nivel in ("Baja", "Media", "Alta"):
            caso = Caso(id="1", tipo="informe_base",
                        predio=Predio(folio_matricula="040-646406",
                                      codigo_catastral="080000000000000000000000000000"),
                        amenazas=(nivel,))
            _tit = amenazas_pot(caso)[0].severidad
            _geo = _severidad_geo_desde_nivel(
                {"nivel": nivel, "intersecta": True},
                {"nivel": "", "intersecta": False})[0]
            self.assertEqual(_tit, severidad_titulux(_geo),
                             f"nivel {nivel}: Titulux={_tit} H-GEO={_geo}")

    def test_una_amenaza_baja_nunca_es_alta_en_ningun_productor(self):
        """F3: el defecto exacto del Golden (GEO_B01-Baja con severidad ALTA)."""
        from arhia_title.contracts import Caso, Predio
        from arhia_title.rules import amenazas_pot
        from pdf_compiler import _severidad_geo_desde_nivel
        caso = Caso(id="1", tipo="informe_base",
                    predio=Predio(folio_matricula="040-646406",
                                  codigo_catastral="080000000000000000000000000000"),
                    amenazas=("Baja",))
        self.assertNotEqual(amenazas_pot(caso)[0].severidad, "alta")
        self.assertNotEqual(_severidad_geo_desde_nivel(
            {"nivel": "Baja", "intersecta": True},
            {"nivel": "", "intersecta": False})[0], "ALTO")

    def test_score_usa_la_misma_tabla(self):
        """El peso del score hidrológico sale del contrato único."""
        from risk_severity import peso_hidrologico
        self.assertEqual(peso_hidrologico("Alta"), 15)
        self.assertEqual(peso_hidrologico("Media"), 8)
        self.assertEqual(peso_hidrologico("Baja"), 5)


# ── F2: 6.2/6.3 desde el mismo objeto y procedencia declarada ────────────────

class TestResumenPotBarranquilla(unittest.TestCase):

    def test_sin_cadena_fija_de_tratamiento(self):
        from dictamen_data import get_pot_summary_dt
        filas = dict(get_pot_summary_dt("Miramar", ciudad="barranquilla"))
        self.assertNotIn("CONSOLIDACION / DESARROLLO", filas["Tratamiento urbanistico"].upper())
        self.assertIn("PENDIENTE", filas["Tratamiento urbanistico"].upper())

    def test_muestra_el_valor_oficial_real(self):
        """El mismo objeto que alimenta 6.3 alimenta 6.2."""
        from dictamen_data import get_pot_summary_dt
        filas = dict(get_pot_summary_dt(
            "Miramar", ciudad="barranquilla", clase_suelo="Urbano",
            tratamiento="Desarrollo", tipo_tratamiento="Bajo", altura_maxima="8",
            fuente_modo="MIXED", fuente_detalle="Procedencia MIXTA: en vivo (barrio) · empaquetado (riesgo)"))
        self.assertEqual(filas["Tratamiento urbanistico"],
                         "Desarrollo (Bajo) -- polígono POT consultado en vivo")
        self.assertIn("Hasta 8 pisos", filas["Altura maxima segun tratamiento"])
        self.assertIn("MIXTA", filas["Fuente de capas"])
        self.assertNotIn("sin consulta en vivo", filas["Fuente de capas"])

    def test_urban_source_summary_modos(self):
        from market_context import (build_urban_source_summary, USM_LIVE, USM_MIXED,
                                    USM_PACKAGED, USM_UNAVAILABLE)
        vivo = build_urban_source_summary(official_urban_context={
            "barrio": "Miramar", "barrio_status": "VERIFIED_OFFICIAL",
            "tratamiento": "Desarrollo", "tratamiento_status": "VERIFIED_OFFICIAL",
            "source": "official_urban_layer"})
        self.assertEqual(vivo["source_mode"], USM_LIVE)
        self.assertEqual(vivo["campos"]["tratamiento"]["modo"], USM_LIVE)

        mixto = build_urban_source_summary(
            official_urban_context={"barrio": "Miramar", "barrio_status": "VERIFIED_OFFICIAL",
                                    "source": "official_urban_layer"},
            campos_empaquetados=["areas_en_riesgo"])
        self.assertEqual(mixto["source_mode"], USM_MIXED)
        self.assertIn("MIXTA", mixto["declaracion"])
        self.assertEqual(mixto["campos"]["areas_en_riesgo"]["modo"], USM_PACKAGED)
        self.assertEqual(build_urban_source_summary()["source_mode"], USM_UNAVAILABLE)
        self.assertEqual(
            build_urban_source_summary(campos_empaquetados=["x"])["source_mode"],
            USM_PACKAGED)

    def test_barrio_no_verificado_no_se_declara_en_vivo(self):
        from market_context import build_urban_source_summary, USM_PACKAGED
        s = build_urban_source_summary(official_urban_context={
            "barrio": "X", "barrio_status": "CONFLICT", "source": "official_urban_layer"})
        self.assertEqual(s["campos"]["barrio"]["modo"], USM_PACKAGED)


# ── F5: dirección oficial + unidad compuesta ─────────────────────────────────

class TestDireccionCanonica(unittest.TestCase):

    def test_unidad_declarada_compuesta(self):
        from unidad_inmobiliaria import extraer_unidad
        u = extraer_unidad("Transversal 43 100 50 TO 8 AP 430")
        self.assertEqual(u["torre"], "8")
        self.assertEqual(u["apartamento"], "430")
        self.assertEqual(u["unidad"], "TO 8 AP 430")
        self.assertEqual(u["direccion_base"], "Transversal 43 100 50")

    def test_identidad_direccion_promueve_registro_oficial(self):
        from unidad_inmobiliaria import identidad_direccion
        cid = {"identity_source": "OFFICIAL_ADOPTION_REGISTRY",
               "direccion_raw": "Pendiente de verificacion", "torre": None,
               "unidad": None,
               "adopcion_registro": {"direccion": "Transversal 43 100 50 TO 8 AP 430"}}
        out = identidad_direccion(cid)
        self.assertEqual(out["direccion_raw"], "Transversal 43 100 50 TO 8 AP 430")
        self.assertEqual(out["unidad"], "TO 8 AP 430")
        self.assertEqual(out["direccion_source"], "OFFICIAL_ADOPTION_REGISTRY")
        # No muta la entrada y no "arrastra" el placeholder como dirección previa.
        self.assertEqual(cid["direccion_raw"], "Pendiente de verificacion")
        self.assertNotIn("direccion_previa", out)

    def test_identidad_direccion_conserva_previo(self):
        from unidad_inmobiliaria import identidad_direccion
        out = identidad_direccion(
            {"direccion_raw": "CALLE 1 # 2-3"}, "Transversal 43 100 50 TO 8 AP 430")
        self.assertEqual(out["direccion_previa"], "CALLE 1 # 2-3")

    def test_sin_direccion_oficial_no_escribe_nada(self):
        from unidad_inmobiliaria import identidad_direccion
        self.assertEqual(identidad_direccion({}, ""), {})
        self.assertEqual(identidad_direccion({"adopcion_registro": {"direccion": "N/D"}}), {})


# ── F: metodología de mercado versionada ─────────────────────────────────────

class TestMetodologiaMercado(unittest.TestCase):

    def test_identidad_metodologica_real(self):
        from market_context import market_methodology
        m = market_methodology()
        self.assertEqual(m["id"], "lonja_baq_metodologia")
        self.assertTrue(m["version"])
        self.assertIsNotNone(m["sha256"])
        self.assertTrue(m["file"].endswith(".yaml"))

    def test_resolucion_de_sector_lleva_version(self):
        from market_context import resolve_market_sector
        r = resolve_market_sector("Miramar")
        self.assertEqual(r["match_type"], "EXACT")
        self.assertTrue(r["market_methodology_id"])
        self.assertTrue(r["market_methodology_version"])
        self.assertIn("methodology_sha256", r["provenance"])

    def test_contexto_sin_version_bloquea(self):
        from market_context import build_market_context, market_context_authorized
        mc = build_market_context(
            identity_verified=True, barrio="Miramar", barrio_status="VERIFIED_OFFICIAL",
            estrato="4", estrato_status="VERIFIED_OFFICIAL",
            tipologia="Apartamento -- Propiedad Horizontal", tipologia_status="VERIFIED_REGISTRAL",
            sector_resolution={"match_type": "EXACT", "matched_sector": "Miramar",
                               "value_m2": 6800000, "source": "constructora"})
        self.assertFalse(mc["ready"])
        self.assertTrue(any("metodolog" in b for b in mc["blockers"]))
        self.assertFalse(market_context_authorized(mc))

    def test_contexto_con_version_queda_listo(self):
        from market_context import build_market_context, resolve_market_sector
        mc = build_market_context(
            identity_verified=True, barrio="Miramar", barrio_status="VERIFIED_OFFICIAL",
            estrato="4", estrato_status="VERIFIED_OFFICIAL",
            tipologia="Apartamento -- Propiedad Horizontal", tipologia_status="VERIFIED_REGISTRAL",
            sector_resolution=resolve_market_sector("Miramar"))
        self.assertEqual(mc["blockers"], [])
        self.assertTrue(mc["ready"])
        self.assertTrue(mc["market_methodology_version"])


# ── F4: estrato por manzana oficial ──────────────────────────────────────────

class TestEstratoPorManzana(unittest.TestCase):

    def test_prefijo_unico_y_corroborado(self):
        from catastro_predio import resolver_manzana_y_estrato
        from tests._fakes_03i1 import patch_catastro  # noqa: WPS433
        with patch_catastro(numero_predial="080010103000010040001908040002",
                            manzana="08001010300001004", estrato="4",
                            barrio="Miramar", localidad="02", corroborada=True):
            r = resolver_manzana_y_estrato("080010103000010040001908040002",
                                          barrio_esperado="Miramar")
        self.assertEqual(r["estado"], "VERIFIED_OFFICIAL")
        self.assertEqual(r["estrato"], "4")
        self.assertEqual(r["codigo_manzana"], "08001010300001004")
        self.assertEqual(r["longitud_prefijo"], 17)

    def test_estrato_no_aplica_no_se_afirma(self):
        from catastro_predio import resolver_manzana_y_estrato
        from tests._fakes_03i1 import patch_catastro
        with patch_catastro(numero_predial="080010103000010040001908040002",
                            manzana="08001010300001006", estrato="No aplica",
                            barrio="Miramar", corroborada=True):
            r = resolver_manzana_y_estrato("080010103000010040001908040002")
        self.assertEqual(r["estado"], "UNRESOLVED")
        self.assertIsNone(r["estrato"])
        self.assertIn("NO_APLICA", r["motivo"])

    def test_barrio_discrepante_es_conflicto(self):
        from catastro_predio import resolver_manzana_y_estrato
        from tests._fakes_03i1 import patch_catastro
        with patch_catastro(numero_predial="080010103000010040001908040002",
                            manzana="08001010300001004", estrato="4",
                            barrio="Otro Barrio", corroborada=True):
            r = resolver_manzana_y_estrato("080010103000010040001908040002",
                                          barrio_esperado="Miramar")
        self.assertEqual(r["estado"], "CONFLICT")
        self.assertIsNone(r["estrato"])

    def test_manzana_inexistente_en_catastro_es_conflicto(self):
        from catastro_predio import resolver_manzana_y_estrato
        from tests._fakes_03i1 import patch_catastro
        with patch_catastro(numero_predial="080010103000010040001908040002",
                            manzana="08001010300001004", estrato="4",
                            barrio="Miramar", corroborada=False):
            r = resolver_manzana_y_estrato("080010103000010040001908040002")
        self.assertEqual(r["estado"], "CONFLICT")
        self.assertIsNone(r["estrato"])

    def test_servicio_caido_no_inventa(self):
        from catastro_predio import resolver_manzana_y_estrato
        from tests._fakes_03i1 import patch_catastro
        with patch_catastro(caido=True):
            r = resolver_manzana_y_estrato("080010103000010040001908040002")
        self.assertEqual(r["estado"], "SOURCE_UNAVAILABLE")
        self.assertIsNone(r["estrato"])

    def test_predial_corto_no_se_usa(self):
        from catastro_predio import resolver_manzana_y_estrato
        r = resolver_manzana_y_estrato("123")
        self.assertEqual(r["estado"], "UNRESOLVED")
        self.assertEqual(r["motivo"], "NUMERO_PREDIAL_INSUFICIENTE")


# ── F8: estado único del riesgo volcánico ───────────────────────────────────

class TestVolcanEstadoUnico(unittest.TestCase):

    def test_texto_low_hazard(self):
        from riesgo_volcanico import texto_volcanico, VOL_LOW
        t = texto_volcanico({"estado": VOL_LOW, "zonas": [
            {"grado": "Baja", "fenomeno": "caida de ceniza", "volcan": "Galeras"}]})
        self.assertIn("BAJA", t["fila"][1])
        self.assertIn("Amenaza volcanica BAJA", t["hallazgo"])
        self.assertEqual(t["alerta"], "verde")

    def test_texto_no_intersection_no_dice_amenaza_baja(self):
        from riesgo_volcanico import texto_volcanico, VOL_NO_INTERSECTION
        t = texto_volcanico({"estado": VOL_NO_INTERSECTION, "zonas": [],
                             "cobertura_confirmada": True})
        self.assertNotIn("BAJA", t["fila"][1].upper())
        self.assertNotIn("Amenaza volcanica BAJA", t["hallazgo"])
        self.assertIn("NO cae", t["fila"][1])

    def test_texto_no_coverage(self):
        from riesgo_volcanico import texto_volcanico, VOL_NO_COVERAGE
        t = texto_volcanico({"estado": VOL_NO_COVERAGE, "zonas": []})
        self.assertIn("fuera del area cartografiada", t["fila"][1])
        self.assertIn("SIN COBERTURA", t["hallazgo"])

    def test_texto_source_unavailable(self):
        from riesgo_volcanico import texto_volcanico, VOL_SOURCE_UNAVAILABLE
        t = texto_volcanico({"estado": VOL_SOURCE_UNAVAILABLE, "zonas": []})
        self.assertIn("NO DISPONIBLE", t["fila"][1])

    def test_filas_y_texto_son_una_sola_verdad(self):
        from riesgo_volcanico import filas_riesgo_volcanico, texto_volcanico, VOL_NO_INTERSECTION
        res = {"estado": VOL_NO_INTERSECTION, "zonas": [], "disponible": True,
               "cobertura_confirmada": True}
        self.assertEqual(dict(filas_riesgo_volcanico(res))["Riesgo volcanico (SGC)"],
                         texto_volcanico(res)["fila"][1])


# ── F7: forma societaria conservada ─────────────────────────────────────────

class TestConstructorFormaSociedad(unittest.TestCase):

    _TEXTO = (
        "Nro Matrícula: 040-646406\n"
        "DIRECCION DEL INMUEBLE:\nTV 43 # 100-50 TO 8 AP 430\n"
        "ANOTACION: Nro 001 Fecha: 22-01-2024\n"
        "ESPECIFICACION: COMPRAVENTA URBANIZADORA MARVAL S.A.S. -> DURAN BACCA ALISSON\n"
    )

    def test_conserva_sas(self):
        from legal_analyzer import analizar_texto_certificado
        res = analizar_texto_certificado(self._TEXTO)
        self.assertIn("MARVAL S.A.S.", res["constructor"])
        self.assertNotEqual(res["constructor"].strip(), "URBANIZADORA MARVAL S")

    def test_no_arrastra_la_contraparte(self):
        from legal_analyzer import analizar_texto_certificado
        res = analizar_texto_certificado(
            "ANOTACION: Nro 001 Fecha: 22-01-2024\n"
            "ESPECIFICACION: COMPRAVENTA URBANIZADORA MARVAL S.A.S. A DURAN BACCA ALISSON\n")
        self.assertNotIn("DURAN", res["constructor"].upper())

    def test_canonical_name_del_sujeto_conserva_siglas(self):
        from sanctions.subjects import canonical_name
        self.assertEqual(canonical_name("URBANIZADORA MARVAL S.A.S."),
                         "URBANIZADORA MARVAL S.A.S.")


# ── A: versionado del manifest ──────────────────────────────────────────────

class TestVersionadoManifest(unittest.TestCase):

    def test_versionado_estricto_devuelve_todo(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        from golden_run_03i1 import _versionado_estricto
        v = _versionado_estricto()
        self.assertTrue(len(v.get("GIT_COMMIT_SHA") or "") >= 7)
        for k in ("ARHIAX_RE_VERSION", "DICTUS_ENGINE_VERSION", "GIS_ADAPTER_VERSION",
                  "TITULUX_VERSION", "RULESET_VERSION"):
            self.assertTrue(v.get(k), f"versión ausente: {k}")

    def test_versionado_falla_si_falta_sha(self):
        import importlib
        sys.path.insert(0, str(ROOT / "scripts"))
        import versioning
        _orig = versioning.git_commit_sha
        versioning.git_commit_sha = lambda: ""
        try:
            mod = importlib.import_module("golden_run_03i1")
            with self.assertRaises(SystemExit):
                mod._versionado_estricto()
        finally:
            versioning.git_commit_sha = _orig


if __name__ == "__main__":
    unittest.main()

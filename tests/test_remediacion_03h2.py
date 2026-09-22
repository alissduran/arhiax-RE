# -*- coding: utf-8 -*-
"""
Remediation 03H.2 — CADASTRAL + URBAN CONTEXT RECOVERY (Golden 040-646406).

Recupera la riqueza catastral/urbanística sin perder las garantías de identidad
y provenance: contexto urbano completo, altura/tratamiento reales, estado de la
capa de construcción y semántica correcta del estrato.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = ROOT / "api"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(API))

from market_context import (
    resolve_official_urban_context, coordinate_source_verified,
    STATUS_VERIFIED_OFFICIAL, STATUS_CONFLICT, STATUS_UNRESOLVED,
    STATUS_SOURCE_UNAVAILABLE, COORD_OFFICIAL_ADDRESS_GEOCODE, COORD_CITY_CENTROID,
)

_URBANO_GOLDEN = {
    "disponible": True,
    "barrio": "Miramar",
    "localidad": "Norte Centro Histórico",
    "estrato": "4",
    "tratamiento": "Consolidación",
    "tipo_tratamiento": "Nivel 2",
    "altura_maxima": "11",
    "pieza_urbana": "Pieza Norte",
    "codigo_manzana": "08001010300001",
    "context_status": "OK",
    "campos_ambiguos": [],
}


class TestUrbanContextContract(unittest.TestCase):
    """#1/#2/#3: el contrato NO descarta atributos devueltos por la fuente."""

    def test_propaga_todos_los_atributos(self):
        out = resolve_official_urban_context(
            ciudad="barranquilla", lat=10.9870, lon=-74.8115,
            coordinate_source=COORD_OFFICIAL_ADDRESS_GEOCODE,
            consultar_entorno=lambda lat, lon: dict(_URBANO_GOLDEN))
        self.assertEqual(out["barrio"], "Miramar")
        self.assertEqual(out["barrio_status"], STATUS_VERIFIED_OFFICIAL)
        self.assertEqual(out["localidad"], "Norte Centro Histórico")
        self.assertEqual(out["estrato"], "4")
        self.assertEqual(out["estrato_status"], STATUS_VERIFIED_OFFICIAL)
        self.assertEqual(out["tratamiento"], "Consolidación")
        self.assertEqual(out["tratamiento_status"], STATUS_VERIFIED_OFFICIAL)
        self.assertEqual(out["tipo_tratamiento"], "Nivel 2")
        self.assertEqual(out["altura_maxima"], "11")
        self.assertEqual(out["altura_status"], STATUS_VERIFIED_OFFICIAL)
        self.assertEqual(out["codigo_manzana"], "08001010300001")
        self.assertEqual(out["coordinate_source"], COORD_OFFICIAL_ADDRESS_GEOCODE)

    def test_ambiguedad_no_marca_verificado(self):
        r = dict(_URBANO_GOLDEN)
        r["context_status"] = "AMBIGUOUS_CONTEXT"
        r["campos_ambiguos"] = ["estrato"]
        out = resolve_official_urban_context(
            ciudad="barranquilla", lat=10.9870, lon=-74.8115,
            coordinate_source=COORD_OFFICIAL_ADDRESS_GEOCODE,
            consultar_entorno=lambda lat, lon: r)
        self.assertEqual(out["estrato"], None)
        self.assertEqual(out["estrato_status"], STATUS_CONFLICT)
        self.assertEqual(out["barrio_status"], STATUS_VERIFIED_OFFICIAL)
        self.assertEqual(out["context_status"], "AMBIGUOUS_CONTEXT")


class TestEdificabilidadGolden(unittest.TestCase):
    """#3/#13: tratamiento y altura REALES (no hardcodeados)."""

    def test_tratamiento_y_altura_desde_la_fuente(self):
        from edificabilidad import filas_edificabilidad
        d = dict(filas_edificabilidad("barranquilla", _URBANO_GOLDEN, 11,
                                      construction_status="AVAILABLE"))
        self.assertEqual(d["Tratamiento urbanístico"], "Consolidación (Nivel 2)")
        self.assertEqual(d["Altura normativa máxima"],
                         "Hasta 11 pisos (POT Barranquilla)")
        self.assertEqual(d["Pisos construidos (catastro)"], "11 piso(s)")

    def test_sin_dato_no_inventa_altura(self):
        from edificabilidad import filas_edificabilidad
        ent = {"tratamiento": "Consolidación", "tipo_tratamiento": "Nivel 2"}
        d = dict(filas_edificabilidad("barranquilla", ent, None,
                                      construction_status="SOURCE_UNAVAILABLE"))
        self.assertEqual(d["Altura normativa máxima"], "N/D")
        self.assertEqual(d["Tratamiento urbanístico"], "Consolidación (Nivel 2)")


class TestNoPosibleLote(unittest.TestCase):
    """#6: distinguir NO_MATCH de SOURCE_UNAVAILABLE."""

    def test_source_unavailable_no_dice_posible_lote(self):
        from edificabilidad import filas_edificabilidad
        d = dict(filas_edificabilidad("barranquilla", _URBANO_GOLDEN, None,
                                      construction_status="SOURCE_UNAVAILABLE"))
        txt = d["Pisos construidos (catastro)"]
        self.assertNotIn("posible lote", txt.lower())
        self.assertIn("no disponible", txt)
        self.assertIn("fuente de construcción", d["Confrontación (construido vs. norma)"])

    def test_no_match_no_afirma_ausencia_de_edificacion(self):
        """03I.1 · F12: la capa respondió SIN REGISTRO en el punto != no hay edificio.

        El Golden real (CTL original, punto geocodificado de la dirección oficial)
        produjo 'capa de construcción consultada sin edificación registrada en el
        punto' para un apartamento en PH que el mismo dictamen identifica: el punto
        del geocodificador puede caer en la vía. Se declara el estado real.
        """
        from edificabilidad import filas_edificabilidad
        d = dict(filas_edificabilidad("barranquilla", _URBANO_GOLDEN, None,
                                      construction_status="NO_MATCH"))
        _t = d["Pisos construidos (catastro)"]
        self.assertIn("no devolvió registro", _t)
        self.assertNotIn("sin edificación registrada", _t)


class TestEstratoSemantico(unittest.TestCase):
    """#9: estrato faltante != uso no residencial."""

    def _estrato(self, **kw):
        from dictamen_data import get_catastral_dt
        return dict(get_catastral_dt("Miramar", 58.75, **kw))["Estrato"]

    def test_none_y_destino_none_pendiente(self):
        t = self._estrato(estrato=None, destino_economico=None)
        self.assertIn("PENDIENTE", t.upper())
        self.assertNotIn("No aplica", t)

    def test_habitacional_sin_estrato_pendiente_residencial(self):
        t = self._estrato(estrato=None, destino_economico="Habitacional")
        self.assertIn("residencial confirmado", t)
        self.assertNotIn("No aplica", t)

    def test_no_residencial_declarado_si_no_aplica(self):
        t = self._estrato(estrato=None, destino_economico="Industrial")
        self.assertIn("No aplica (uso no residencial declarado)", t)

    def test_estrato_presente_se_muestra(self):
        self.assertEqual(self._estrato(estrato="4",
                                       destino_economico="Habitacional"), "4")

    def test_barrio_label_oficial(self):
        from dictamen_data import get_catastral_dt
        filas = dict(get_catastral_dt("Miramar", 58.75))
        self.assertIn("Barrio / sector oficial", filas)


class TestNegativos(unittest.TestCase):
    """#14: nunca inventar contexto."""

    def test_urban_context_source_unavailable_no_inventa(self):
        out = resolve_official_urban_context(
            ciudad="barranquilla", lat=10.9870, lon=-74.8115,
            coordinate_source=COORD_OFFICIAL_ADDRESS_GEOCODE,
            consultar_entorno=lambda lat, lon: {"disponible": False})
        self.assertIsNone(out["barrio"])
        self.assertIsNone(out["estrato"])
        self.assertIsNone(out["altura_maxima"])
        self.assertEqual(out["context_status"], STATUS_SOURCE_UNAVAILABLE)
        self.assertNotEqual(out["barrio_status"], STATUS_VERIFIED_OFFICIAL)

    def test_coordenada_no_autorizada_no_consulta(self):
        out = resolve_official_urban_context(
            ciudad="barranquilla", lat=10.9870, lon=-74.8115,
            coordinate_source=COORD_CITY_CENTROID,
            consultar_entorno=lambda lat, lon: dict(_URBANO_GOLDEN))
        self.assertEqual(out["context_status"], "COORDINATE_SOURCE_NOT_AUTHORIZED")
        self.assertIsNone(out["altura_maxima"])

    def test_altura_ambigua_no_verificada(self):
        r = dict(_URBANO_GOLDEN)
        r["context_status"] = "AMBIGUOUS_CONTEXT"
        r["campos_ambiguos"] = ["tratamiento"]
        out = resolve_official_urban_context(
            ciudad="barranquilla", lat=10.9870, lon=-74.8115,
            coordinate_source=COORD_OFFICIAL_ADDRESS_GEOCODE,
            consultar_entorno=lambda lat, lon: r)
        self.assertIsNone(out["altura_maxima"])
        self.assertEqual(out["altura_status"], STATUS_CONFLICT)


class TestAutoridadUrbanaUnica(unittest.TestCase):
    """#4: el render 6.2/6.3 y el MarketContext consumen la MISMA verdad.

    03H.2A (#C): la precedencia es DETERMINISTA — VERIFIED_OFFICIAL manda y los
    desacuerdos quedan registrados como conflicto (nunca `setdefault`).
    """

    def _oficial(self, **over):
        out = resolve_official_urban_context(
            ciudad="barranquilla", lat=10.9870, lon=-74.8115,
            coordinate_source=COORD_OFFICIAL_ADDRESS_GEOCODE,
            consultar_entorno=lambda lat, lon: dict(_URBANO_GOLDEN))
        out.update(over)
        return out

    def test_capa500_vacia_se_llena_con_contexto_oficial(self):
        from pdf_compiler import _merge_contexto_urbano_oficial
        ent, trat, prov = _merge_contexto_urbano_oficial({}, self._oficial(), None)
        self.assertEqual(ent["tratamiento"], "Consolidación")
        self.assertEqual(ent["altura_maxima"], "11")
        self.assertEqual(ent["estrato"], "4")
        # La autoridad POT del render ya NO queda vacía: no cae al texto genérico.
        self.assertEqual(trat, "Consolidación")
        self.assertEqual(prov["conflictos"], [])
        self.assertEqual(prov["authority"], "OfficialUrbanContext")

    def test_oficial_gana_sobre_legacy_distinto_y_lo_registra(self):
        """#C: legacy altura 5 vs oficial VERIFIED_OFFICIAL 11 -> NUNCA queda 5."""
        from pdf_compiler import _merge_contexto_urbano_oficial
        ent, trat, prov = _merge_contexto_urbano_oficial(
            {"tratamiento": "Consolidación", "altura_maxima": "5"},
            self._oficial(), "Consolidación")
        self.assertEqual(ent["altura_maxima"], "11")
        self.assertEqual(ent["tratamiento"], "Consolidación")
        self.assertEqual(trat, "Consolidación")
        _conf = {c["campo"]: c for c in prov["conflictos"]}
        self.assertIn("altura_maxima", _conf)
        self.assertEqual(_conf["altura_maxima"]["valor_previo"], "5")
        self.assertEqual(_conf["altura_maxima"]["valor_oficial"], "11")
        # El valor idéntico no genera conflicto espurio.
        self.assertNotIn("tratamiento", _conf)

    def test_valor_identico_no_genera_conflicto(self):
        from pdf_compiler import _merge_contexto_urbano_oficial
        ent, _trat, prov = _merge_contexto_urbano_oficial(
            {"tratamiento": "Consolidación"}, self._oficial(), "Consolidación")
        self.assertEqual(prov["conflictos"], [])
        self.assertEqual(prov["aplicados"]["tratamiento"], "coincide")

    def test_ambiguo_no_se_afirma_en_el_render(self):
        from pdf_compiler import _merge_contexto_urbano_oficial
        oficial = self._oficial(
            tratamiento=None, tratamiento_status=STATUS_CONFLICT,
            tipo_tratamiento=None, tipo_tratamiento_status=STATUS_CONFLICT,
            altura_maxima=None, altura_status=STATUS_CONFLICT,
            context_status="AMBIGUOUS_CONTEXT")
        ent, trat, prov = _merge_contexto_urbano_oficial({}, oficial, None)
        self.assertIsNone(ent.get("tratamiento"))
        self.assertIsNone(ent.get("altura_maxima"))
        self.assertIsNone(trat)
        _noap = {x["campo"] for x in prov["no_aplicados"]}
        self.assertIn("altura_maxima", _noap)

    def test_sin_contexto_oficial_no_toca_el_entorno(self):
        from pdf_compiler import _merge_contexto_urbano_oficial
        ent, trat, _prov = _merge_contexto_urbano_oficial(
            {"clase_suelo": "Urbano"},
            {"context_status": STATUS_SOURCE_UNAVAILABLE}, None)
        self.assertEqual(ent, {"clase_suelo": "Urbano"})
        self.assertIsNone(trat)


class TestBuildingContextPorCoordenadas(unittest.TestCase):
    """#5: contexto de EDIFICIO por coordenadas autorizadas (no es identidad)."""

    _ARGS = dict(lat=10.9870, lon=-74.8115,
                 es_medellin=False, es_bogota=False, es_pasto=False)

    def test_no_consulta_sin_coordenada_autorizada(self):
        from unittest import mock
        import catastro_predio
        from pdf_compiler import _building_context_por_coordenadas
        with mock.patch.object(catastro_predio, "consultar_construccion") as m:
            out = _building_context_por_coordenadas(
                coordinate_verified=False,
                construction_status="NOT_EVALUATED", **self._ARGS)
        self.assertEqual(out, {})
        m.assert_not_called()

    def test_no_consulta_si_la_capa500_ya_respondio(self):
        from unittest import mock
        import catastro_predio
        from pdf_compiler import _building_context_por_coordenadas
        with mock.patch.object(catastro_predio, "consultar_construccion") as m:
            out = _building_context_por_coordenadas(
                coordinate_verified=True,
                construction_status="AVAILABLE", **self._ARGS)
        self.assertEqual(out, {})
        m.assert_not_called()

    def test_consulta_con_coordenada_autorizada(self):
        from unittest import mock
        import catastro_predio
        from pdf_compiler import _building_context_por_coordenadas
        _r = {"disponible": True, "tipo_construccion": "PH", "total_pisos": 12,
              "construction_status": "AVAILABLE"}
        with mock.patch.object(catastro_predio, "consultar_construccion",
                               return_value=dict(_r)) as m:
            out = _building_context_por_coordenadas(
                coordinate_verified=True,
                construction_status="NOT_EVALUATED", **self._ARGS)
        self.assertEqual(out["construction_status"], "AVAILABLE")
        self.assertEqual(out["total_pisos"], 12)
        m.assert_called_once_with(10.9870, -74.8115)

    def test_fuente_caida_no_inventa(self):
        from unittest import mock
        import catastro_predio
        from pdf_compiler import _building_context_por_coordenadas
        with mock.patch.object(catastro_predio, "consultar_construccion",
                               side_effect=RuntimeError("sin red")):
            out = _building_context_por_coordenadas(
                coordinate_verified=True,
                construction_status="NOT_EVALUATED", **self._ARGS)
        # {} -> el llamador conserva NOT_EVALUATED (nunca "sin edificación").
        self.assertEqual(out, {})

    def test_ciudades_con_capa_propia_no_se_consultan(self):
        from unittest import mock
        import catastro_predio
        from pdf_compiler import _building_context_por_coordenadas
        for _flag in ("es_medellin", "es_bogota", "es_pasto"):
            args = dict(self._ARGS)
            args[_flag] = True
            with mock.patch.object(catastro_predio, "consultar_construccion") as m:
                out = _building_context_por_coordenadas(
                    coordinate_verified=True,
                    construction_status="NOT_EVALUATED", **args)
            self.assertEqual(out, {})
            m.assert_not_called()


if __name__ == "__main__":
    unittest.main()

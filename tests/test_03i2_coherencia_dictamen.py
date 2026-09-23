# -*- coding: utf-8 -*-
"""03I.2 — Coherencia del dictamen: D-1, D-2 y D-3.

Defectos cerrados (los tres aparecieron cuando la capa catastral empezó a responder
en la corrida real del Golden, y los tres afectaban al gate de valoración):

  D-1 `identity_verified` solo lo fijaba el camino del registro de adopción; cuando la
      identidad se resolvía contra el catastro vivo (`MATCH_BY_NUPRE` con
      `VERIFIED_UNIT_IDENTITY`) el campo quedaba ausente y el gate de mercado bloqueaba
      la valoración por «identity_verified != True» mientras el modelo declaraba la
      identidad verificada. Dos verdades en el mismo objeto.

  D-2 el destino económico catastral («Habitacional») se escribía como TIPOLOGÍA
      («Uso Habitacional (Según catastro)»), tapando la evidencia registral de
      propiedad horizontal y cerrando el gate por «tipología no verificada».

  D-3 el área catastral del TERRENO (22.05 m² del lote) se comparaba con el área
      privada registral del apartamento (58.75 m²) y TIT_B01 emitía un hallazgo ALTO
      falso de inconsistencia registral-catastral.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))


class TestD1IdentidadVerificadaDerivada(unittest.TestCase):

    def test_la_confianza_canonica_manda(self):
        """identity_verified SIEMPRE es coherente con resolution_confidence."""
        from canonical import build_canonical_property_identity, RESOLUTION_VERIFIED_UNIT
        cid = build_canonical_property_identity(
            analysis={}, folio="040-646406",
            predio_real={"predio": {"numero_predial_nacional": "080010103000010040001908040002",
                                    "codigo_homologado": "AFT0005BOHA",
                                    "resolution_status": "EXACT"}},
            nom=None, identidad=None, ciudad="barranquilla", metodo_resolucion="nupre")
        self.assertEqual(cid["resolution_confidence"], RESOLUTION_VERIFIED_UNIT)
        self.assertIs(cid["identity_verified"], True,
                      "una identidad VERIFIED_UNIT_IDENTITY debe declararse verificada")

    def test_sin_registro_no_se_declara_verificada(self):
        from canonical import build_canonical_property_identity
        cid = build_canonical_property_identity(
            analysis={}, folio="040-646406", predio_real=None, nom=None,
            identidad=None, ciudad="barranquilla", metodo_resolucion=None)
        self.assertIs(cid["identity_verified"], False)

    def test_el_gate_de_mercado_lee_el_mismo_campo(self):
        """El invariante que consumía el gate: identity_verified == confianza."""
        from canonical import (build_canonical_property_identity,
                               RESOLUTION_VERIFIED_UNIT)
        cid = build_canonical_property_identity(
            analysis={}, folio="X",
            predio_real={"predio": {"nupre": "AFT0005BOHA", "resolution_status": "EXACT"}},
            nom=None, identidad=None, ciudad="barranquilla", metodo_resolucion="nupre")
        esperado = cid["resolution_confidence"] == RESOLUTION_VERIFIED_UNIT
        self.assertEqual(bool(cid.get("identity_verified")), esperado)


class TestD2TipologiaNoEsUso(unittest.TestCase):

    def _tip(self, **kw):
        from tipologia import tipologia_de_predio
        base = dict(destino_economico=None, descripcion_ctl=None,
                    condicion_juridica=None, condicion_source=None,
                    fuentes_tematicas=(), predio_resuelto=False, es_caso_demo=False,
                    tiene_ctl=True)
        base.update(kw)
        return tipologia_de_predio(**base)

    def test_uso_residencial_no_tapa_la_propiedad_horizontal(self):
        t = self._tip(destino_economico="Habitacional", predio_resuelto=True,
                      condicion_juridica="Propiedad Horizontal (inferido del CTL adjunto)")
        self.assertIn("Propiedad Horizontal", t)
        self.assertNotIn("Uso Habitacional", t)

    def test_condicion_catastral_se_etiqueta_como_tal(self):
        """Con evidencia física (tipo de predio SNR) la unidad se nombra y se etiqueta."""
        from tipologia import TIPOLOGIA_PH_CATASTRAL
        t = self._tip(destino_economico="Habitacional", predio_resuelto=True,
                      condicion_juridica="Propiedad Horizontal",
                      condicion_source="thematic_exact",
                      fuentes_tematicas=("thematic_exact", "thematic_spatial"),
                      tipologia_fisica_fuente="APARTAMENTO")
        self.assertEqual(t, TIPOLOGIA_PH_CATASTRAL)

    def test_ph_sin_evidencia_fisica_no_inventa_la_unidad(self):
        """03I.2A §18: sin evidencia registral/catastral de la unidad física, la
        tipología NO se inventa: se declara la unidad en PH y su uso."""
        t = self._tip(destino_economico="Habitacional", predio_resuelto=True,
                      condicion_juridica="Propiedad Horizontal",
                      condicion_source="thematic_exact",
                      fuentes_tematicas=("thematic_exact", "thematic_spatial"))
        self.assertIn("Propiedad Horizontal", t)
        self.assertIn("Unidad", t)

    def test_uso_industrial_no_borra_la_ph(self):
        """03I.2A §16: un uso industrial NO elimina el régimen de propiedad horizontal.

        Antes, ver «Industrial» en el destino económico bastaba para escribir «No
        Propiedad Horizontal» en la tipología, borrando evidencia registral válida.
        """
        t = self._tip(destino_economico="Industrial", predio_resuelto=True,
                      condicion_juridica="Propiedad Horizontal")
        self.assertIn("Propiedad Horizontal", t)
        self.assertNotIn("No Propiedad Horizontal", t)
        self.assertIn("Industrial", t)

    def test_bodega_solo_con_evidencia_registral(self):
        """La tipología Bodega aparece solo si la fuente la acredita."""
        from tipologia import TIPOLOGIA_BODEGA
        t = self._tip(destino_economico="Industrial", predio_resuelto=True,
                      descripcion_ctl="BODEGA 3 MANZANA 4")
        self.assertEqual(t, TIPOLOGIA_BODEGA)
        self.assertNotIn("No Propiedad Horizontal", t)

    def test_comercial_es_uso_y_se_declara_como_uso(self):
        t = self._tip(destino_economico="Comercial y Servicios", predio_resuelto=True)
        self.assertEqual(t, "Uso Comercial y Servicios (Según catastro)")

    def test_sin_evidencia_ni_catastro_queda_pendiente(self):
        from tipologia import TIPOLOGIA_SIN_CONSULTA
        self.assertEqual(self._tip(), TIPOLOGIA_SIN_CONSULTA)

    def test_la_tipologia_ph_contiene_propiedad_horizontal(self):
        """El gate de mercado exige que la tipología acredite PH."""
        t = self._tip(destino_economico="Habitacional", predio_resuelto=True,
                      condicion_juridica="Propiedad Horizontal (inferido del CTL)")
        self.assertIn("Propiedad Horizontal", t)


class TestD3AreaComparable(unittest.TestCase):

    def test_unidad_ph_no_compara_terreno_con_area_privada(self):
        from unidad_inmobiliaria import area_catastral_comparable
        self.assertIsNone(area_catastral_comparable(True, 22.05),
                          "el terreno del lote no es el área del apartamento")

    def test_predio_sin_unidad_si_compara(self):
        from unidad_inmobiliaria import area_catastral_comparable
        self.assertEqual(area_catastral_comparable(False, 120.0), 120.0)

    def test_area_vacia_o_cero_no_compara(self):
        from unidad_inmobiliaria import area_catastral_comparable
        self.assertIsNone(area_catastral_comparable(False, 0))
        self.assertIsNone(area_catastral_comparable(False, None))

    def test_el_contraste_queda_en_registral_only(self):
        """Con el terreno fuera del contraste, TIT_B01 declara REGISTRAL_ONLY."""
        from arhia_title.contracts import Caso, Predio
        from arhia_title.rules import identidad_inmueble
        from unidad_inmobiliaria import area_catastral_comparable
        area_cat = area_catastral_comparable(True, 22.05)
        caso = Caso(id="1", tipo="informe_base",
                    predio=Predio(folio_matricula="040-646406",
                                  codigo_catastral="080010103000010040001908040002",
                                  area_registral=58.75, area_catastral=area_cat or 0.0))
        h = identidad_inmueble(caso)[0]
        self.assertIn("REGISTRAL_ONLY", h.descripcion)
        self.assertEqual(h.severidad, "media")
        self.assertIn("58.75", h.descripcion)


if __name__ == "__main__":
    unittest.main()

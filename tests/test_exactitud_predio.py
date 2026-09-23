# -*- coding: utf-8 -*-
"""
Tests de regresión Sprint 2 (exactitud de datos reales del CTL).

Cubren el bug reportado por el usuario con el folio real 040-347004:
- El CTL del SNR trae CODIGO CATASTRAL + NUPRE que antes se ignoraban, y el
  dictamen caía al barrio/tipología de demostración (Miramar / Propiedad
  Horizontal) con NUPRE falso.
- Regla dura: cuando el CTL trae código/NUPRE, los datos del predio REAL
  (destino económico Industrial, Barrio Abajo, condición "No PH") deben
  resolverse del catastro en vivo; si el servicio no responde, el dictamen
  debe marcar PENDIENTE, nunca inventar.

Los casos de red usan mocks (offline, sin depender del servicio público).
"""
import sys
import unittest
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
API_DIR = ROOT_DIR / "api"
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(API_DIR))

# Texto mínimo de un CTL SNR real con los campos que hoy importan
_TEXTO_CTL_REAL = """
CERTIFICADO DE TRADICION Y LIBERTAD
MATRICULA INMOBILIARIA: 040-347004
CIRCULO REGISTRAL: 040 - BARRANQUILLA
FECHA APERTURA: 28-03-2001
CODIGO CATASTRAL: 080010102000001710004000000000
NUPRE: AFT0040BBHC
ESTADO DEL FOLIO: ACTIVO
DESCRIPCION: CABIDA Y LINDEROS
BODEGA NUMERO 3, CON AREA DE 570.9 MTS2.
DIRECCION DEL INMUEBLE
Tipo Predio: URBANO
2) CL 40 # 50 B - 62 BDGA 3
ANOTACION: Nro 001 Fecha: 21-03-2001
ESPECIFICACION: MODO DE ADQUISICION: 160 DIVISION MATERIAL
ANOTACION: Nro 002 Fecha: 03-03-2009
ESPECIFICACION: GRAVAMEN: 0205 HIPOTECA
ANOTACION: Nro 006 Fecha: 09-08-2017
Se cancela anotación No: 2
ESPECIFICACION: CANCELACION: 0843 CANCELACION HIPOTECA
NRO TOTAL DE ANOTACIONES: *6*
"""


class TestExactitudPredioReal(unittest.TestCase):

    def test_analizador_extrae_codigo_y_nupre_del_ctl(self):
        """El CTL del SNR (folio 040-347004) expone código catastral y NUPRE."""
        from legal_analyzer import analizar_texto_certificado
        res = analizar_texto_certificado(_TEXTO_CTL_REAL)
        self.assertEqual(res["codigo_catastral"], "080010102000001710004000000000")
        self.assertEqual(res["nupre"], "AFT0040BBHC")
        self.assertEqual(res["folio"], "040-347004")
        self.assertIn("BODEGA", (res.get("descripcion_ctl") or "").upper())

    def test_analizador_extrae_direccion_formato_snr(self):
        """La dirección del CTL real ('2) CL 40 # 50 B - 62 BDGA 3') se extrae."""
        from legal_analyzer import analizar_texto_certificado
        res = analizar_texto_certificado(_TEXTO_CTL_REAL)
        self.assertIn("40", res["direccion"])
        self.assertNotEqual(res["direccion"].lower(), "pendiente de verificacion")

    def test_cancelacion_hipoteca_marca_no_vigente(self):
        """Anotación 006 cancela la 002: el CTL queda sin gravámenes activos
        (regresión: antes la cancelación se clasificaba como nueva hipoteca)."""
        from legal_analyzer import analizar_texto_certificado
        res = analizar_texto_certificado(_TEXTO_CTL_REAL)
        hipotecas_vigentes = [a for a in res["anotaciones"]
                              if "Hipoteca" in a[2] and "CANCELADA" not in a[4]]
        self.assertEqual(hipotecas_vigentes, [])
        # El hallazgo honesto: tradición libre de gravámenes
        titulos = [h[3] for h in res["hallazgos"]]
        self.assertTrue(any("Libre de Gravamenes" in t for t in titulos))

    def test_catastro_predio_mock_resuelve_destino_industrial(self):
        """Con mocks del servicio, el predio real por código resuelve
        destino Industrial + condición No PH + Barrio Abajo."""
        import catastro_predio as cp

        def fake_predio(codigo, nupre):
            return {"disponible": True,
                    "numero_predial_nacional": "080010102000001710004000000000",
                    "nupre": "AFT0040BBHC",
                    "destino_economico": "Industrial",
                    "tipo_predio": "Predio_Privado",
                    "estrato": "No_Aplica",
                    "estado_fmi": "Activo",
                    "area_catastral_terreno": 475.0,
                    "globalid": "{CCE87699-1362-42F6-A612-EEEE8A35E4F3}"}

        original_predio = cp.consultar_predio_por_codigo
        original_dir = cp.consultar_direccion_y_punto
        original_cond = cp.consultar_condicion_destino
        original_ent = cp.consultar_entorno_urbano
        original_const = cp.consultar_construccion
        cp._CACHE.clear()
        try:
            cp.consultar_predio_por_codigo = fake_predio
            # 03I.2B · H-1: el productor REAL declara la procedencia de la
            # coordenada (capa 105 enlazada por cr_predio_guid == globalid del
            # predio). El fixture se completa con esa misma evidencia para
            # representar la respuesta oficial, no una promoción sin respaldo.
            cp.consultar_direccion_y_punto = lambda g, c: {
                "disponible": True, "direccion_oficial": "Calle 40 # 50B-64 BG 3",
                "lat": 10.99029, "lon": -74.78022,
                "source_system": "CATASTRO_MUNICIPAL_BARRANQUILLA_ARCGIS",
                "layer": "105 · direccion",
                "feature_id": "cce87699-1362-42f6-a612-eeee8a35e4f3",
                "feature_id_kind": "cr_predio_guid",
                "geometry_type": "Point",
                "resolution_method": "DIRECCION_OFICIAL_LIGADA_POR_GUID",
                "predio_globalid_consultado": "cce87699-1362-42f6-a612-eeee8a35e4f3",
                "link_verificado": True}
            cp.consultar_condicion_destino = lambda c, lat, lon: {
                "disponible": True, "condicion_juridica": "No propiedad horizontal",
                "destino_vigente": "Industrial"}
            cp.consultar_entorno_urbano = lambda lat, lon: {
                "disponible": True, "barrio": "Barrio Abajo", "localidad": "02",
                "estrato": "2", "tratamiento": "Renovacion"}
            cp.consultar_construccion = lambda lat, lon: {
                "disponible": True, "tipo_construccion": "Convencional",
                "total_pisos": 1, "area_construida": 474.34}

            r = cp.enriquecer_desde_ctl("080010102000001710004000000000", "AFT0040BBHC")
            self.assertTrue(r["disponible"])
            self.assertEqual(r["predio"]["destino_economico"], "Industrial")
            self.assertEqual(r["condicion"]["condicion_juridica"], "No propiedad horizontal")
            self.assertEqual(r["entorno"]["barrio"], "Barrio Abajo")
            self.assertAlmostEqual(r["lat"], 10.99029, places=3)
        finally:
            cp.consultar_predio_por_codigo = original_predio
            cp.consultar_direccion_y_punto = original_dir
            cp.consultar_condicion_destino = original_cond
            cp.consultar_entorno_urbano = original_ent
            cp.consultar_construccion = original_const
            cp._CACHE.clear()

    def test_sin_codigo_no_inventa_demo(self):
        """Sin código/NUPRE, la resolución devuelve disponible=False y el
        llamador decide PENDIENTE (nunca se fabrica el predio de Miramar)."""
        import catastro_predio as cp
        original = cp.consultar_predio_por_codigo
        cp._CACHE.clear()
        try:
            cp.consultar_predio_por_codigo = lambda c, n: {
                "disponible": False, "error": "predio no encontrado",
                "codigo_catastral": None, "nupre": None}
            r = cp.enriquecer_desde_ctl(None, None)
            self.assertFalse(r["disponible"])
            self.assertIn("error", r)
        finally:
            cp.consultar_predio_por_codigo = original
            cp._CACHE.clear()

    @pytest.mark.network
    def test_catastro_predio_vivo_folio_real(self):
        """En vivo (marcado network): el código catastral real del folio
        040-347004 resuelve el predio Industrial en Barrio Abajo."""
        import catastro_predio as cp
        r = cp.enriquecer_desde_ctl("080010102000001710004000000000", "AFT0040BBHC")
        if r.get("disponible"):
            self.assertEqual(r["predio"]["destino_economico"], "Industrial")
            self.assertEqual(r["entorno"]["barrio"], "Barrio Abajo")
        else:
            # Honestidad: sin servicio no se afirman datos (skip suave)
            self.skipTest("servicio catastral no disponible: " + str(r.get("error")))


if __name__ == "__main__":
    unittest.main()

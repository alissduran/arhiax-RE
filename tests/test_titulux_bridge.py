# -*- coding: utf-8 -*-
"""
Test del puente Titulux (arhiax-RE/api/titulux_bridge.py).

Sin red: se siembra una caché de listas determinista para verificar que
  * el mapeo CTL -> Caso Titulux es correcto (folio, código, partes, anotaciones),
  * el screening ONU/OFAC con fuentes OPERATIVA da "sin coincidencia" y completa,
  * la degradación honesta (UIAF sin feed público) marca screening incompleto y
    veredicto PREANALISIS_INCOMPLETO,
  * una coincidencia por documento dispara "coincidencia" y bloqueo precautorio.
"""
import json
import os
import shutil
import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
API_DIR = ROOT_DIR / "api"
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(API_DIR))

# Los tests no escriben en el /tmp del sistema (denegado por el sandbox):
# usan un directorio temporal dentro del repo, como el resto de la suite.
TMP_DIR = ROOT_DIR / "tmp_titulux_test"


def setUpModule():
    shutil.rmtree(TMP_DIR, ignore_errors=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)


def tearDownModule():
    shutil.rmtree(TMP_DIR, ignore_errors=True)


def _nuevo_cache_dir(nombre):
    d = TMP_DIR / nombre
    d.mkdir(parents=True, exist_ok=True)
    return str(d)


def _sembrar_cache(cache_dir, fuente, registros, estado="OPERATIVA"):
    """Escribe la caché en el formato que lee ingest.listas._leer_cache."""
    os.makedirs(cache_dir, exist_ok=True)
    meta = {
        "fuente": fuente, "nombre": fuente.upper(), "url": "", "formato": "xml",
        "fecha_emision": "", "version": "test-v1", "hash": "test-hash-" + fuente,
        "licencia": "public", "registros": len(registros), "estado": estado,
        "autoridad": "", "metodo": "", "vigencia": "",
    }
    with open(os.path.join(cache_dir, fuente + "_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)
    with open(os.path.join(cache_dir, fuente + "_registros.json"), "w", encoding="utf-8") as f:
        json.dump(registros, f, ensure_ascii=False)


def _registro(id, nombre, tipo_doc=None, num=None):
    return {"id": id, "nombre": nombre, "alias": [], "tipo_documento": tipo_doc,
            "numero_documento": num, "fecha_nacimiento": None, "programas": [],
            "fuente": "onu", "lista_version": "test-v1"}


_ANALYSIS = {
    "folio": "040-646406",
    "codigo_catastral": "080010103000010040001908040002",
    "direccion": "TORRE 8 APARTAMENTO 430 NAPOLI",
    "titulares": "DURAN BACCA ALISSON CC# 1045718995X 50%",
    "acreedor_snr": "BANCO DE BOGOTA S.A. NIT# 8600029644",
    "hipoteca_vigente": {"anotacion": "007", "fecha": "22-01-2024",
                         "acreedor": "BANCO DE BOGOTA S.A.", "cuantia_cop": 268516940},
    "anotaciones": [("007", "22-01-2024", "GRAVAMEN: HIPOTECA", "BANCO DE BOGOTA", "VIGENTE")],
    "anotaciones_detalle": [
        {"num": "004", "fecha": "22-01-2024", "tipo": "COMPRAVENTA",
         "partes": "DURAN BACCA ALISSON", "estado": "VIGENTE",
         "texto": "A: DURAN BACCA ALISSON CC# 1045718995"},
        {"num": "007", "fecha": "22-01-2024", "tipo": "GRAVAMEN: HIPOTECA",
         "partes": "BANCO DE BOGOTA", "estado": "VIGENTE",
         "texto": "HIPOTECA ABIERTA CUANTIA 268516940"},
    ],
}
_DB = {"folio_matricula": "040-646406", "area": 58.75, "direccion": "TORRE 8 APT 430"}
_VAL = {"consolidado": 399500000.0}


class TestConstruirCasoTitulux(unittest.TestCase):

    def test_mapeo_ctl_a_caso(self):
        from titulux_bridge import construir_caso_titulux
        caso = construir_caso_titulux(_ANALYSIS, _DB, _VAL, area_catastral=80.0)
        self.assertEqual(caso.tipo, "informe_base")
        self.assertEqual(caso.predio.folio_matricula, "040-646406")
        self.assertEqual(caso.predio.codigo_catastral, "080010103000010040001908040002")
        self.assertEqual(caso.predio.area_registral, 58.75)
        self.assertEqual(caso.predio.area_catastral, 80.0)
        self.assertAlmostEqual(caso.avaluo.valor, 399500000.0)
        # partes: titular (natural) + acreedor
        roles = {p.rol: p for p in caso.partes}
        self.assertIn("titular", roles)
        self.assertIn("acreedor", roles)
        self.assertEqual(roles["titular"].tipo_documento, "cc")
        self.assertEqual(roles["titular"].numero_documento, "1045718995")
        # anotación de compraventa mapea titular adquirente
        compras = [a for a in caso.anotaciones if a.tipo == "compraventa"]
        self.assertTrue(compras)
        self.assertIn("DURAN BACCA", compras[0].titular)


class TestEjecutarTituluxDeterminista(unittest.TestCase):

    def test_screening_sin_coincidencia_completo(self):
        """ONU/OFAC OPERATIVA sin coincidencias -> screening completo, sin coincidencia."""
        from titulux_bridge import ejecutar_titulux
        tmp = _nuevo_cache_dir("sin_coincidencia")
        _sembrar_cache(tmp, "onu", [_registro("o1", "JUAN PEREZ")])
        _sembrar_cache(tmp, "ofac", [_registro("f1", "MARIA LOPEZ")])
        res = ejecutar_titulux(_ANALYSIS, _DB, _VAL,
                               fuentes_activas=("onu", "ofac"),
                               cache_dir=tmp, timeout_listas=5)
        self.assertTrue(res["disponible"])
        self.assertTrue(res["screening_completo"])
        self.assertEqual(res["screening_agregado"], "sinCoincidencia")
        self.assertFalse(res["coincidencia"])
        self.assertEqual(res["fuentes_pendientes"], [])
        # Hipoteca vigente -> bloqueo precautorio por gravamen (no por screening)
        self.assertEqual(res["conclusion"]["veredicto"], "BLOQUEO_PRECAUTORIO")

    def test_uiaf_sin_feed_publico_marca_pendiente(self):
        """UIAF es canal oficial: screening incompleto + PREANALISIS_INCOMPLETO."""
        from titulux_bridge import ejecutar_titulux
        tmp = _nuevo_cache_dir("uiaf_pendiente")
        _sembrar_cache(tmp, "onu", [_registro("o1", "JUAN PEREZ")])
        res = ejecutar_titulux(_ANALYSIS, _DB, _VAL,
                               fuentes_activas=("onu", "uiaf"),
                               cache_dir=tmp, timeout_listas=5)
        self.assertTrue(res["disponible"])
        self.assertFalse(res["screening_completo"])
        self.assertIn("uiaf", res["fuentes_pendientes"])
        self.assertEqual(res["screening_agregado"], "pendiente")
        self.assertEqual(res["conclusion"]["veredicto"], "PREANALISIS_INCOMPLETO")

    def test_coincidencia_por_documento(self):
        """El documento del titular en la lista -> coincidencia -> bloqueo precautorio."""
        from titulux_bridge import ejecutar_titulux
        tmp = _nuevo_cache_dir("coincidencia")
        _sembrar_cache(tmp, "onu",
                       [_registro("o1", "ALISSON DURAN", "cc", "1045718995")])
        res = ejecutar_titulux(_ANALYSIS, _DB, _VAL,
                               fuentes_activas=("onu",),
                               cache_dir=tmp, timeout_listas=5)
        self.assertTrue(res["disponible"])
        self.assertTrue(res["coincidencia"])
        self.assertEqual(res["screening_agregado"], "coincidencia")
        self.assertEqual(res["conclusion"]["veredicto"], "BLOQUEO_PRECAUTORIO")

    def test_nunca_lanza_sin_titulux_importable(self):
        """El puente nunca debe romper el PDF: falla de datos -> disponible False."""
        from titulux_bridge import ejecutar_titulux
        # analysis sin anotaciones_detalle ni titulares: debe degradar sin lanzar
        res = ejecutar_titulux({}, _DB, _VAL, fuentes_activas=(), cache_dir=None)
        self.assertIsInstance(res, dict)
        self.assertIn("disponible", res)


if __name__ == "__main__":
    unittest.main()

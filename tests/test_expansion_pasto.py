# -*- coding: utf-8 -*-
"""
Tests de integración de Pasto (Nariño) como ciudad operativa (Sprint 3).

Verifican:
- Configuración de ciudad (nombre, DANE, círculo registral, centroide).
- Normalización: 'pasto' es operativa; 'cali' sigue rechazándose con 400.
- Geocoder: Pasto tiene centroide/bbox propios (NO los de Barranquilla).
- Valoración: Pasto usa referencia genérica por estrato (metodologia_local=False)
  y NO aplica la Lonja de Barranquilla (regla de honestidad).
- Dictamen: alcance/POT/catastro declaran PENDIENTE de fuente en vivo.
- Edificabilidad: altura por ficha normativa del POT (sin inventar número).
- GPV-F-77: departamento/municipio = Nariño/Pasto.
- Territorio: verificación honesta (sin endpoint en vivo verificado aún).

Sin red: todos los casos son offline.
"""
import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
API_DIR = ROOT_DIR / "api"
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(API_DIR))


class TestPastoConfig(unittest.TestCase):

    def test_ciudad_en_config(self):
        from config import get_ciudad
        cfg = get_ciudad("pasto")
        self.assertEqual(cfg.get("nombre"), "Pasto")
        self.assertEqual(cfg.get("departamento"), "Nariño")
        self.assertEqual(cfg.get("codigo_dane"), "52001")
        self.assertEqual(cfg.get("codigo_circulo"), "052")
        self.assertEqual(cfg.get("centroide"), {"lat": 1.2136, "lon": -77.2811})

    def test_listar_ciudades_incluye_pasto(self):
        from config import listar_ciudades
        self.assertIn("pasto", listar_ciudades())


class TestPastoNormalizacion(unittest.TestCase):

    def test_pasto_es_operativa(self):
        from index import _normalizar_ciudad
        self.assertEqual(_normalizar_ciudad("pasto"), "pasto")
        self.assertEqual(_normalizar_ciudad("Pasto"), "pasto")
        self.assertEqual(_normalizar_ciudad("  PASTO  "), "pasto")

    def test_cali_sigue_pendiente_400(self):
        from index import _normalizar_ciudad
        from fastapi import HTTPException
        with self.assertRaises(HTTPException):
            _normalizar_ciudad("cali")


class TestPastoGeocoder(unittest.TestCase):

    def test_es_pasto_y_centroide(self):
        from geocoder import _es_pasto, _centroide, _bbox
        self.assertTrue(_es_pasto("pasto"))
        self.assertTrue(_es_pasto("Pasto, Nariño"))
        self.assertFalse(_es_pasto("barranquilla"))
        self.assertEqual(_centroide("pasto"), (1.2136, -77.2811))
        self.assertNotEqual(_bbox("pasto"), _bbox("barranquilla"))


class TestPastoValuacion(unittest.TestCase):

    def test_valuation_pasto_sin_metodologia_local(self):
        from dictamen_data import get_valuation
        v = get_valuation(58.75, "Centro", estrato=4, ciudad="pasto")
        self.assertFalse(v.get("metodologia_local"))
        self.assertGreater(v.get("consolidado", 0), 0)

    def test_valuation_baq_usa_metodologia_local(self):
        from dictamen_data import get_valuation
        v = get_valuation(58.75, "Miramar", estrato=4, ciudad="barranquilla")
        self.assertTrue(v.get("metodologia_local"))

    def test_valoracion_alert_pasto_no_menciona_lonja_baq(self):
        from dictamen_data import get_valoracion_alert
        val = {"metodo_principal": "m1", "consolidado": 300000000}
        txt = get_valoracion_alert("Centro", val, lambda x: f"${x:,.0f}", ciudad="pasto")
        self.assertNotIn("Lonja de Barranquilla", txt)
        self.assertIn("Referencia genérica", txt)


class TestPastoDictamenData(unittest.TestCase):

    def test_alcance_pasto_honesto(self):
        from dictamen_data import get_alcance_dt
        filas = get_alcance_dt("Centro", ciudad="pasto")
        d = dict(filas)
        self.assertIn("Capa catastral Pasto", d)
        self.assertIn("PENDIENTE", d["Capa catastral Pasto"])
        self.assertIn("EJECUTADA", d["Geocodificacion del predio"])

    def test_pot_summary_pasto_pendiente(self):
        from dictamen_data import get_pot_summary_dt
        filas = get_pot_summary_dt("Centro", ciudad="pasto")
        d = dict(filas)
        self.assertIn("PENDIENTE", d["Clasificacion del suelo"])

    def test_catastral_dt_sigla_gc_pas(self):
        from dictamen_data import get_catastral_dt
        filas = get_catastral_dt("Centro", 58.75, ciudad="pasto")
        d = dict(filas)
        self.assertIn("GC-PAS", d["NUPRE"])


class TestPastoEdificabilidad(unittest.TestCase):

    def test_altura_pasto_ficha_pot(self):
        from edificabilidad import altura_permitida
        p, tipo, txt = altura_permitida("pasto", {})
        self.assertIsNone(p)
        self.assertEqual(tipo, "ficha_pot")

    def test_filas_edificabilidad_pasto_no_menciona_baq(self):
        from edificabilidad import filas_edificabilidad
        filas = filas_edificabilidad("pasto", {}, 5)
        texto = " | ".join(f"{k}: {v}" for k, v in filas)
        self.assertNotIn("Barranquilla", texto)
        self.assertIn("Pasto", texto)


class TestPastoGpvYTerritorio(unittest.TestCase):

    def test_gpv_ciudad_admin(self):
        from gpv_f77 import _CIUDAD_ADMIN
        self.assertEqual(_CIUDAD_ADMIN["pasto"], ("Nariño", "Pasto"))

    def test_territorio_pasto_honesto(self):
        from integrations.territorio import verificar_territorio
        res = verificar_territorio(1.2136, -77.2811, "pasto")
        self.assertFalse(res.get("disponible"))
        self.assertIn("Pasto", res.get("error") or "")


class TestPastoScoreNoEvaluado(unittest.TestCase):

    def test_score_hidrologico_no_evaluado_no_afirma_sin_afectacion(self):
        """Con capas de riesgo NO EVALUADAS, el score no dice 'Sin afectación'."""
        from score_engine import calcular_score_actuarial
        geo_eval = {
            "amenaza_remocion_masa": {"intersecta": False, "nivel": None},
            "areas_en_riesgo": {"intersecta": False, "nivel": None},
            "resumen_ejecutivo": "NO EVALUADO: sin fuente en vivo para Pasto",
        }
        analysis = {"anotaciones": [], "titulares": "PENDIENTE"}
        val_data = {"area": 58.75, "consolidado": 300000000}
        res = calcular_score_actuarial([], geo_eval, analysis, val_data)
        det = " ".join(res["detalle"]["hidrologico"])
        self.assertIn("no calificable", det.lower())
        self.assertNotIn("sin afectación", det.lower())


if __name__ == "__main__":
    unittest.main()

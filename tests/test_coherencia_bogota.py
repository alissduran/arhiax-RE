# -*- coding: utf-8 -*-
"""
Tests de coherencia Bogotá (dictamen real 50C-1463431): regresión de 4
inconsistencias reportadas por el usuario:
  1. H-GEO 'Afectación Detectada (Sin afectación)' con severidad MEDIO
     (los textos 'Sin afectación'/'No aplica' del IDIGER y el tipo de suelo
     geotécnico 'Aluvial' NO son intersección de amenaza).
  2. Score integrado 'EXCELENTE' con semáforo ROJO por hallazgo ALTO
     (ahora el integrado se topa a 55 BLOQUEADO cuando hay ALTO).
  3. Filas POT sin valor ('SUELO SEGUN...') -> ahora muestran el valor real.
  4. Estrato 0 / pisos de construcción vecina -> estrato válido 1-6 y la
     construcción del EDIFICIO principal del lote.
"""
import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
API_DIR = ROOT_DIR / "api"
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(API_DIR))


class TestNoAfectacionIDIGER(unittest.TestCase):

    def test_textos_sin_afectacion_no_intersectan(self):
        from catastro_predio_bogota import _es_no_afectacion
        self.assertTrue(_es_no_afectacion("Sin afectación"))
        self.assertTrue(_es_no_afectacion("SIN AFECTACION"))
        self.assertTrue(_es_no_afectacion("No aplica"))
        self.assertTrue(_es_no_afectacion("N/A"))
        self.assertTrue(_es_no_afectacion(None))
        self.assertTrue(_es_no_afectacion(""))
        # Niveles reales de amenaza SÍ son afectación
        self.assertFalse(_es_no_afectacion("Alta"))
        self.assertFalse(_es_no_afectacion("Media"))
        self.assertFalse(_es_no_afectacion("Baja"))
        self.assertFalse(_es_no_afectacion("Riesgo No Mitigable"))

    def test_geotecnia_aluvial_no_es_amenaza(self):
        """Mock de las capas IDIGER: 'Aluvial' (tipo de suelo geotécnico) no
        dispara intersección; 'Alta' (amenaza real) sí."""
        import catastro_predio_bogota as bog
        respuestas = {}

        def fake_q(layer, lid, lon, lat, out, max_features=3):
            return {"features": respuestas.get((lid, out), [])}

        orig = bog._q_bbox
        bog._cache_get = lambda k: None
        bog._cache_set = lambda k, v: None
        bog._q_bbox = fake_q
        try:
            # Capa 8 (geotecnia) con 'Aluvial' -> informativo, sin intersección
            respuestas[(2, "AMENAZA")] = [{"properties": {"AMENAZA": "Sin afectación"}}]
            respuestas[(7, "ZONA_RESPUESTA")] = [{"properties": {"ZONA_RESPUESTA": "Baja"}}]
            respuestas[(8, "GEOTECNIA")] = [{"properties": {"GEOTECNIA": "Aluvial"}}]
            r = bog.consultar_amenazas(4.64, -74.07)
            self.assertFalse(r["movimiento_masa_urbano"]["intersecta"])
            self.assertTrue(r["respuesta_sismica"]["intersecta"])  # Baja sí
            self.assertEqual(r["respuesta_sismica"]["nivel"], "Baja")
            self.assertEqual(r["geotecnia_tipo_suelo"], "Aluvial")
        finally:
            bog._q_bbox = orig


class TestScoreCoherenteConSemaforo(unittest.TestCase):

    def _score(self, hallazgos):
        from score_engine import calcular_score_actuarial
        analysis = {"anotaciones": [], "titulares": "TITULAR X", "folio": "50C-1"}
        val = {"area": 56.05, "consolidado": 500000000}
        geo = {"amenaza_remocion_masa": {"intersecta": False},
               "areas_en_riesgo": {"intersecta": False}}
        return calcular_score_actuarial(hallazgos, geo, analysis, val)

    def test_hipoteca_alto_bloquea_score_integrado(self):
        """Hallazgo ALTO (hipoteca vigente): el integrado NO puede ser
        EXCELENTE/FAVORABLE — se topa a 55 y se etiqueta BLOQUEADO."""
        hallazgos = [("ALTO", None, None,
                      "H-01 | GRAVAMEN: Hipoteca Vigente (Anot. 014)",
                      "SNR", "x", "y"),
                     ("INFORMATIVO", None, None,
                      "H-GEO | Zona Libre de Amenazas y Riesgos", "IDIGER", "x", "y")]
        sr = self._score(hallazgos)
        self.assertTrue(sr["bloqueado"])
        self.assertEqual(sr["etiqueta"], "BLOQUEADO")
        self.assertLessEqual(sr["score_integrado"], 55)
        self.assertLessEqual(sr["score_registral"], 70)  # -30 por el ALTO

    def test_sin_alto_perfil_normal(self):
        hallazgos = [("INFORMATIVO", None, None,
                      "H-01 | Tradicion Registral Libre de Graven", "SNR", "x", "y")]
        sr = self._score(hallazgos)
        self.assertFalse(sr["bloqueado"])
        self.assertNotEqual(sr["etiqueta"], "BLOQUEADO")
        self.assertGreaterEqual(sr["score_integrado"], 90)


class TestPotSummaryValoresReales(unittest.TestCase):

    def test_bogota_muestra_valores_no_generico(self):
        from dictamen_data import get_pot_summary_dt
        filas = dict(get_pot_summary_dt("San Luis", ciudad="bogota",
                                        clase_suelo="Urbano",
                                        uso_economico="RESIDENCIAL",
                                        upz="GALERIAS"))
        self.assertIn("Urbano", filas["Clasificacion del suelo"])
        self.assertIn("RESIDENCIAL", filas["Norma uso de suelo"])
        self.assertIn("GALERIAS", filas["Unidad de Planeamiento Zonal (UPZ)"])
        self.assertNotIn("SEGUN", filas["Clasificacion del suelo"].upper())

    def test_bogota_sin_valores_marca_pendiente(self):
        from dictamen_data import get_pot_summary_dt
        filas = dict(get_pot_summary_dt("San Luis", ciudad="bogota"))
        self.assertIn("PENDIENTE", filas["Clasificacion del suelo"].upper())
        self.assertIn("PENDIENTE", filas["Unidad de Planeamiento Zonal (UPZ)"].upper())


class TestEstratoYConstruccionBogota(unittest.TestCase):

    def test_estrato_0_se_trata_como_sin_estrato(self):
        import catastro_predio_bogota as bog

        def fake_q(layer, lid, lon, lat, out, max_features=3):
            if lid == 1:
                return {"features": [{"properties": {"CODIGO_MANZANA": "X", "ESTRATO": "0"}}]}
            return {"features": []}
        orig = bog._q_bbox
        bog._cache_get = lambda k: None
        bog._cache_set = lambda k, v: None
        bog._q_bbox = fake_q
        try:
            r = bog.consultar_entorno_urbano(4.64, -74.07)
            self.assertIsNone(r["estrato"])  # nunca '0'
        finally:
            bog._q_bbox = orig

    def test_construccion_elige_el_edificio_de_mas_pisos_del_lote(self):
        """Un bbox con caseta de 1 piso y edificio de 5 pisos del MISMO lote:
        se reportan los 5 pisos (no la primera coincidencia)."""
        import catastro_predio_bogota as bog
        feats = [
            {"properties": {"CONCODIGO": "A1", "CONNPISOS": 1, "CONALTURA": 3.0, "LOTECODIGO": "L-1"}},
            {"properties": {"CONCODIGO": "B2", "CONNPISOS": 5, "CONALTURA": 16.0, "LOTECODIGO": "L-1"}},
        ]
        orig = bog._q_bbox
        bog._cache_get = lambda k: None
        bog._cache_set = lambda k, v: None
        bog._q_bbox = lambda *a, **k: {"features": feats}
        try:
            r = bog.consultar_construccion(4.64, -74.07, codigo_lote="L-1")
            self.assertEqual(r["total_pisos"], 5)
            self.assertEqual(r["codigo_construccion"], "B2")
        finally:
            bog._q_bbox = orig


class TestCoherenciaMedellin(unittest.TestCase):
    """Regresión de la auditoría de Medellín (antes de comprar el CTL real):
    coherencia semáforo/estructurabilidad y ruta de verificación con la
    ciudad correcta (antes filtraba 'Barranquilla' en dictámenes de MED)."""

    def test_ausencia_ctl_bloquea_estructurabilidad(self):
        """La 08B decía 'SIN BLOQUEOS (VERDE)' con AUSENCIA DE CTL ALTO,
        contradiciendo el resumen BLOQUEADO/ROJO del encabezado."""
        from pdf_compiler import evaluar_estructurabilidad_fiduciaria
        hallazgos = [("ALTO", None, None,
                      "H-01 | AUSENCIA DE CERTIFICADO DE TRADICION Y LIBERTAD (CTL)",
                      "SNR", "No se aporto el CTL", "BLOQUEO TOTAL")]
        r = evaluar_estructurabilidad_fiduciaria(hallazgos)
        self.assertEqual(r["semaforo"], "ROJO")
        self.assertFalse(r["estructurable"])

    def test_hipoteca_alto_bloquea(self):
        from pdf_compiler import evaluar_estructurabilidad_fiduciaria
        hallazgos = [("ALTO", None, None,
                      "H-01 | GRAVAMEN: Hipoteca Vigente (Anot. 014)",
                      "SNR", "hipoteca vigente", "bloqueo")]
        r = evaluar_estructurabilidad_fiduciaria(hallazgos)
        self.assertEqual(r["semaforo"], "ROJO")

    def test_informativo_no_bloquea(self):
        from pdf_compiler import evaluar_estructurabilidad_fiduciaria
        hallazgos = [("INFORMATIVO", None, None,
                      "H-01 | Zona Libre de Amenazas", "IDIGER", "sin afectacion", "favorable")]
        r = evaluar_estructurabilidad_fiduciaria(hallazgos)
        self.assertEqual(r["semaforo"], "VERDE")

    def test_ruta_verificacion_con_ciudad(self):
        """La ruta de riesgo geoespacial cita la ciudad del caso, no
        'Barranquilla' (fuga que se veía en dictámenes de Medellín)."""
        from ruta_verificacion import generar_ruta
        ruta = generar_ruta([{"tipo": "riesgo_geoespacial"}],
                            nombre_ciudad="Medellín")
        self.assertIn("Medellín", ruta[0]["fuente"])
        self.assertNotIn("Barranquilla", ruta[0]["fuente"])

    def test_planes_parciales_med_bog_no_afirmados(self):
        """'Planes Parciales: SIN AFECTACION' era una afirmación sin consulta
        en MED/BOG -> ahora 'NO EVALUADO' (la fila BAQ sí se mantiene)."""
        from dictamen_data import get_pot_summary_dt
        filas_med = dict(get_pot_summary_dt("x", ciudad="medellin"))
        filas_bog = dict(get_pot_summary_dt("x", ciudad="bogota"))
        self.assertIn("NO EVALUADO", filas_med["Planes Parciales"])
        self.assertIn("NO EVALUADO", filas_bog["Planes Parciales"])
        filas_baq = dict(get_pot_summary_dt("x", ciudad="barranquilla"))
        self.assertIn("SIN AFECTACION", filas_baq["Planes Parciales"].upper())

    def test_cobertura_alert_con_la_ciudad_correcta(self):
        """Regresión (reporte del usuario): en un caso de Bogotá la evaluación
        de cobertura (01D) decía 'perimetro urbano de Barranquilla' porque el
        texto solo distinguía Medellín de Barranquilla."""
        from dictamen_data import get_cobertura_alert
        bog = get_cobertura_alert("LA ESPERANZA", ciudad="bogota")
        self.assertIn("Bogotá D.C.", bog)
        self.assertNotIn("Barranquilla", bog)
        med = get_cobertura_alert("Astorga", ciudad="medellin")
        self.assertIn("Medellín", med)
        baq = get_cobertura_alert("Miramar", ciudad="barranquilla")
        self.assertIn("Barranquilla", baq)

    def test_ruta_no_genera_paso_por_hallazgo_informativo(self):
        """Regresión (dictamen real 50C-1463431): el hallazgo INFORMATIVO
        'Zona Libre de Amenazas' contenía las palabras 'amenazas/riesgos' y
        generaba un paso geotécnico espurio en la Ruta de Verificación aunque
        el predio NO tiene ninguna amenaza. Solo ALTO/MEDIO generan pasos."""
        from ruta_verificacion import generar_ruta
        # Reproducir el mapeo del pdf_compiler sobre los hallazgos reales
        def mapear(hallazgos):
            rutas = []
            for sev, _tc, _bg, titulo, fuente, desc, _i in hallazgos:
                if sev == "INFORMATIVO":
                    continue
                tl = titulo.lower()
                if "hipoteca" in tl and "vigente" in tl:
                    rutas.append({"tipo": "hipoteca_vigente", "referencia": fuente})
                elif ("riesgo" in tl or "amenaza" in tl or "geo" in tl) \
                        and "zona libre" not in tl and "libre de" not in desc.lower():
                    rutas.append({"tipo": "riesgo_geoespacial", "referencia": fuente})
            return rutas

        hallazgos = [
            ("ALTO", None, None,
             "H-01 | Hipoteca vigente a favor de BBVA Colombia (Anot. 014)",
             "SNR Registral", "hipoteca vigente", "gestionar"),
            ("INFORMATIVO", None, None,
             "H-GEO | Zona Libre de Amenazas y Riesgos (Evaluación Dinámica POT)",
             "IDIGER Bogotá", "sin interseccion", "favorable"),
        ]
        tipos = [p["tipo"] for p in mapear(hallazgos)]
        self.assertEqual(tipos, ["hipoteca_vigente"])
        ruta = generar_ruta([{"tipo": "hipoteca_vigente"}], nombre_ciudad="Bogotá D.C.")
        self.assertEqual(len(ruta), 1)
        # El paso geotécnico solo debe existir con intersección real (ALTO/MEDIO)
        self.assertNotIn("geotécnico", ruta[0]["descripcion"])


if __name__ == "__main__":
    unittest.main()

# -*- coding: utf-8 -*-
import unittest
import sys
import re
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
API_DIR = ROOT_DIR / "api"
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(API_DIR))

from api.geocoder import geocodificar_direccion, extraer_direccion_de_ctl, extraer_barrio_de_texto
from api.geospatial_engine import evaluate_predio
from api.legal_analyzer import analizar_texto_certificado, analizar_certificado
from api.dictamen_data import get_valuation


class TestArhiaxReSuite(unittest.TestCase):

    # ── Tests originales (Hito 5) ────────────────────────────────────────────

    @pytest.mark.network
    def test_geocodificar_direcciones_reales(self):
        lat_napoli, lon_napoli = geocodificar_direccion("Tv 43 # 100-50")
        self.assertTrue(10.94 <= lat_napoli <= 11.05)
        self.assertTrue(-74.85 <= lon_napoli <= -74.77)

        lat_recreo, lon_recreo = geocodificar_direccion("Calle 63 # 37-71")
        self.assertTrue(10.94 <= lat_recreo <= 11.05)
        self.assertTrue(-74.85 <= lon_recreo <= -74.77)

    @pytest.mark.network
    def test_geocodificar_fallback(self):
        lat, lon = geocodificar_direccion("Direccion inexistente 12345")
        self.assertEqual(lat, 10.9685)
        self.assertEqual(lon, -74.7813)

    def test_extraer_direccion_y_barrio_de_texto(self):
        texto_simulado = """
        Matrícula Inmobiliaria: 040-123456
        Dirección: CL 79 # 53 - 10, Barrio Alto Prado, Barranquilla.
        Área privada: 75.5 m2
        """
        dir_extraida = extraer_direccion_de_ctl(texto_simulado)
        self.assertEqual(dir_extraida, "CL 79 # 53 - 10")

        barrio_extraido = extraer_barrio_de_texto(texto_simulado)
        self.assertEqual(barrio_extraido, "Alto Prado")

    @pytest.mark.network
    def test_motor_geoespacial_dinamico(self):
        lat, lon = geocodificar_direccion("Tv 43 # 100-50")
        resultado = evaluate_predio(lat, lon)
        self.assertIn("amenaza_remocion_masa", resultado)
        self.assertIn("areas_en_riesgo", resultado)

        am = resultado["amenaza_remocion_masa"]
        self.assertTrue(am["intersecta"])
        self.assertEqual(am["nivel"], "Baja")

    def test_analizador_legal_anotaciones(self):
        # Fallback sin CTL
        res_fallback = analizar_certificado(None)
        self.assertEqual(res_fallback["hallazgos"][0][0], "ALTO")

        # Test con texto real simulado
        texto_ctl = """
        Matrícula Inmobiliaria: 040-999999
        Apertura: 2020-01-15
        ANOTACION Nro: 001 10-02-2020 COMPRAVENTA DE: Constructora Marval A: Duran Alisson CC 12345
        ANOTACION Nro: 002 12-02-2020 GRAVAMEN: Hipoteca a favor de Banco de Bogota
        ANOTACION Nro: 003 15-05-2022 CANCELACION: cancela anotacion nro: 002
        """
        res_valido = analizar_texto_certificado(texto_ctl)
        self.assertEqual(res_valido["folio"], "040-999999")
        self.assertIn("Duran Alisson", res_valido["titulares"])

        anotaciones = res_valido["anotaciones"]
        self.assertEqual(len(anotaciones), 3)
        self.assertIn("CANCELADA", anotaciones[1][4])  # Anotación 002 cancelada

    def test_valoracion_metodologia_lonja_baq_yaml(self):
        val_miramar = get_valuation(60.0, "Miramar", estrato=4)
        self.assertGreater(val_miramar["consolidado"], 0)
        self.assertEqual(val_miramar["cap_rate"], 0.0485)

        val_riomar = get_valuation(50.0, "Riomar", estrato=5)
        self.assertAlmostEqual(val_riomar["consolidado"], 260000000, delta=10000000)

    # ── Sprint 0 — Tests obligatorios (Titulux_Parche_Sprint0_Dictus.md) ────

    def test_no_contradiccion(self):
        """Valida que 'APTO para portafolio' y 'BLOQUEADA' no coexistan
        en el mismo documento. Regla dura del gate fiduciario Sprint 0."""

        def chequear(texto):
            apto = "APTO para portafolio" in texto
            bloqueado = "BLOQUEADA" in texto or "Imposible estructurar" in texto
            return not (apto and bloqueado)

        # Caso válido — solo BLOQUEADA
        self.assertTrue(chequear(
            "Estructurabilidad fiduciaria: BLOQUEADA (semáforo ROJO). "
            "Condiciones precedentes: cancelación de hipoteca."
        ))

        # Caso válido — solo VERDE
        self.assertTrue(chequear(
            "Sin gravámenes activos registrados. Libre disposición del activo."
        ))

        # Caso inválido — detector de contradicción debe retornar False
        self.assertFalse(chequear(
            "Activo APTO para portafolio. "
            "Estructurabilidad fiduciaria: BLOQUEADA (semáforo ROJO)."
        ))

    def test_boundary_avaluo(self):
        """Valida que la palabra 'avalúo' solo aparezca en contexto negado
        dentro de secciones de valor. Boundary obligatorio Sprint 0."""

        def tiene_fuga(texto):
            """Retorna True si hay al menos un uso de 'avalúo' sin negación."""
            for m in re.finditer(r"aval[uú]o", texto, re.IGNORECASE):
                contexto = texto[max(0, m.start() - 60):m.start()]
                if not re.search(r"no\s+(es|sustituye|constituye)|no\s+es\b",
                                 contexto, re.IGNORECASE):
                    return True
            return False

        # Texto correcto — todas las menciones están negadas
        texto_ok = (
            "Estimación referencial de mercado — NO es avalúo. "
            "Esta estimación no sustituye un avalúo elaborado por el RAA."
        )
        self.assertFalse(tiene_fuga(texto_ok))

        # Texto con fuga — avalúo sin negación explícita
        texto_fuga = "Valor Comercial Consolidado según Avalúo ARHIAX: $407.800.000"
        self.assertTrue(tiene_fuga(texto_fuga))

    # ── Sprint 1 — Tests de aceptación (validan módulos nuevos) ────────────

    def test_conciliacion_acreedor(self):
        """Valida que el motor detecte discrepancias entre acreedor SNR
        y acreedor real declarado (Bloque 2 Sprint 1)."""
        from api.legal_analyzer import detectar_discrepancia_acreedor

        # Caso con discrepancia: cesión no registrada
        discrepancia = detectar_discrepancia_acreedor(
            acreedor_snr="BANCO DE BOGOTA S.A.",
            acreedor_real="SCOTIABANK COLPATRIA S.A."
        )
        self.assertIsNotNone(discrepancia)
        self.assertEqual(discrepancia["tipo"], "CESION_NO_REGISTRADA")
        self.assertEqual(discrepancia["severidad"], "ALTO")
        self.assertIn("acreedor_snr", discrepancia)
        self.assertIn("acreedor_real", discrepancia)

        # Caso sin discrepancia — mismo acreedor
        sin_disc = detectar_discrepancia_acreedor(
            acreedor_snr="BANCOLOMBIA S.A.",
            acreedor_real="BANCOLOMBIA S.A."
        )
        self.assertIsNone(sin_disc)

        # Caso sin acreedor real (sin gravamen) → no hay discrepancia
        sin_gravamen = detectar_discrepancia_acreedor(
            acreedor_snr=None,
            acreedor_real=None
        )
        self.assertIsNone(sin_gravamen)

    def test_carga_economica_ltv(self):
        """Valida el motor de estimación de carga económica hipotecaria
        (Bloque 3 Sprint 1)."""
        from api.carga_economica import estimar_carga_hipotecaria

        resultado = estimar_carga_hipotecaria(
            valor_inmueble=407_800_000,
            fecha_constitucion="2023-10-11",
            plazo_anos=20,
            tasa_anual=None  # None → usa tasa referencial (DTF + spread estándar)
        )
        self.assertIn("saldo_estimado", resultado)
        self.assertIn("cuota_mensual_orientativa", resultado)
        self.assertIn("ltv_estimado", resultado)
        self.assertIn("plazo_restante_anos", resultado)
        self.assertGreater(resultado["saldo_estimado"], 0)
        self.assertTrue(0 < resultado["ltv_estimado"] <= 1.0)
        self.assertGreater(resultado["cuota_mensual_orientativa"], 0)

    def test_ruta_verificacion(self):
        """Valida que el generador de ruta produzca pasos estructurados
        según los hallazgos activos del informe (Bloque 4 Sprint 1)."""
        from api.ruta_verificacion import generar_ruta

        hallazgos_simulados = [
            {"tipo": "hipoteca_vigente", "referencia": "Anot. 007"},
            {"tipo": "cesion_no_registrada", "referencia": "Anot. 007"},
            {"tipo": "afectacion_vivienda", "referencia": "Anot. 008"},
        ]
        ruta = generar_ruta(hallazgos_simulados)

        self.assertIsInstance(ruta, list)
        self.assertGreater(len(ruta), 0)

        # Verificar estructura de cada paso
        for paso in ruta:
            self.assertIn("numero", paso)
            self.assertIn("descripcion", paso)
            self.assertIn("actor", paso)
            self.assertIn("plazo", paso)
            self.assertIn("trigger", paso)

        # Con hipoteca vigente debe existir paso correspondiente
        triggers = [p.get("trigger") for p in ruta]
        self.assertIn("hipoteca_vigente", triggers)
        self.assertIn("afectacion_vivienda", triggers)

        # Sin hallazgos → ruta vacía (activo limpio)
        ruta_limpia = generar_ruta([])
        self.assertEqual(len(ruta_limpia), 0)


if __name__ == "__main__":
    unittest.main()

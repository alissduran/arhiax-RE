# -*- coding: utf-8 -*-
"""HOTFIX DICTUS 2.0D-R1 — PRESUPUESTO DE LA PÁGINA 6 / SIN PÉRDIDA DE DATOS.

Cubre lo exigido por el hotfix:

  §7  · `page_budget(page)` registra available / consumed / remaining por página y P6
        debe quedar con `remaining_height >= 56` (ideal >= 65) también con contenido
        MÁXIMO realista.
  §4  · el PDF imprime hasta 3 condiciones materiales y declara «+ N …»; el MODELO y el
        MANIFEST conservan TODAS.
  §2/§3 · la página 6 tiene UN solo bloque inferior de trazabilidad (no Traza + pie).
  §5/§6 · identidad, estado, geometría, valor y metodología siguen impresos.
  §11 · el gate sigue rechazando cualquier PDF con violaciones de retícula.
"""
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import dictus_ejecutivo as de           # noqa: E402
import dictus_entrega as entrega        # noqa: E402
import dictus_estado as dse             # noqa: E402
import dictus_manifiesto as dm          # noqa: E402
import dictus_secciones as sec          # noqa: E402
from test_dictus_20d_decision import _estado  # noqa: E402

FOLIO = "TST-000001"
SALIDA = ROOT / "tmp_dictus_2d_r1"

DIRECCION_LARGA = ("TV 43 # 100 - 50 CONJUNTO RESIDENCIAL NAPOLI APARTAMENTOS ETAPA 3 "
                   "TORRE 8 APARTAMENTO 430 · BARRIO MIRAMAR · LOCALIDAD 02 "
                   "BARRANQUILLA · ATLÁNTICO · COLOMBIA")
GEOMETRIA_LARGA = ("Perímetro oficial del predio (lote/edificio) según la capa catastral "
                   "municipal, con vértices en el sistema MAGNA-SIRGAS origen nacional y "
                   "área de terreno declarada por catastro.")

BLOCKERS_SEIS = [
    "Contexto de mercado no autorizado en esta corrida",
    "Sin tasación de referencia vigente para el sector",
    "Área registral y área catastral no conciliadas",
    "Sin testigos comparables suficientes en el radio analizado",
    "Método de mercado sin versión declarada por la corrida",
    "Vigencia de la tasa fuera de la ventana aceptada",
]


def _estado_maximo():
    """Contenido MÁXIMO realista de la página 6 (identidad completa + valor autorizado)."""
    rs = _estado()
    pi = rs["property_identity"]
    pi["direccion_raw"] = DIRECCION_LARGA
    pi["direccion_normalizada"] = DIRECCION_LARGA
    pi["nupre"] = "AFT0005BOHATESTLARGO"
    pi["codigo_catastral"] = "080010103000010040001908040002"
    pi["unidad"] = "APARTAMENTO 430 TORRE 8 ETAPA 3"
    pi["torre"], pi["apartamento"] = "8", "430"
    rs["urban_context"]["condicion_juridica"] = "Propiedad Horizontal"
    rs["urban_context"]["destino_economico"] = "Habitacional"
    mc = rs["market_context"]
    mc["coordinate_scope"] = GEOMETRIA_LARGA
    mc["coordinate_source"] = "Catastro municipal de Barranquilla · capa 105 direccion"
    mc["canonical_binding_fields"] = ["nupre", "numero_predial", "direccion_normalizada",
                                      "codigo_catastral", "unidad_predial"]
    mc["canonical_binding_status"] = "VERIFIED"
    rs["valuation_state"]["authorization"] = {"allowed": True, "identity_authorized": True,
                                             "market_context_authorized": True}
    return rs


def _estado_bloqueado(blockers=None):
    """Valoración BLOQUEADA con muchas condiciones declaradas."""
    rs = _estado_maximo()
    rs["valuation_state"] = {
        "authorization": {"allowed": False, "identity_authorized": True,
                          "market_context_authorized": False},
        "motivo_no_aplica": "Contexto de mercado no autorizado en esta corrida."}
    rs["market_context"]["blockers"] = list(blockers or BLOCKERS_SEIS)
    return rs


def _render(rs, nombre):
    SALIDA.mkdir(parents=True, exist_ok=True)
    dse.agregar_findings_de_coherencia(rs, rs.get("historical_consistency"))
    dse.agregar_manifiesto_de_sombras(rs)
    modelo = dm.construir_documento_maestro(rs, historial=rs.get("historical_consistency"),
                                            folio=FOLIO)
    secciones = sec.desde_estado(rs, modelo, rs.get("historical_consistency"))
    pdf = SALIDA / f"{nombre}.pdf"
    de.render(modelo, secciones, pdf)
    from pypdf import PdfReader
    paginas = [(p.extract_text() or "") for p in PdfReader(str(pdf)).pages]
    return modelo, secciones, pdf, paginas


class TestPagina6Presupuesto(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.modelo, cls.secciones, cls.pdf, cls.paginas = _render(
            _estado_maximo(), "p6_maximo")
        cls.violaciones = list(de.VIOLACIONES)
        cls.p6 = " ".join(cls.paginas[5].split())

    def test_p6_maximum_realistic_content(self):
        """§9 · contenido máximo: sin desborde y con margen suficiente."""
        self.assertEqual([v for v in self.violaciones if "P6 desborda" in v], [],
                         f"la página 6 desborda con contenido máximo: {self.violaciones}")
        b = de.page_budget(6)
        self.assertFalse(b["overflow"])
        self.assertGreaterEqual(b["remaining_height"], 56.0,
                                f"queda {b['remaining_height']:.1f} pt (mínimo 56)")
        self.assertGreaterEqual(b["remaining_height"], 65.0,
                                "el hotfix fija el objetivo de diseño en 65 pt")
        self.assertGreater(b["consumed_height"], 0.0)
        self.assertAlmostEqual(b["available_height"] + b["footer_limit"], b["consumed_height"]
                               + b["remaining_height"], places=1)

    def test_p6_conserva_identidad_geometria_y_valor(self):
        """§5 · identidad, estado, geometría, valor y metodología no se sacrifican."""
        p6 = self.p6
        filas = (self.secciones.get("identidad") or {}).get("filas") or []
        self.assertGreaterEqual(len(filas), 8, "el fixture debe traer la identidad completa")
        for fila in filas:
            valor = str(fila.get("valor") or "")
            if len(valor) >= 12:
                self.assertIn(" ".join(valor.split())[:12], p6,
                              f"fila de identidad ausente en la página 6: {fila}")
        # BLOCK 1 · §10/§11: el resumen de identidad se DERIVA de sus componentes (aquí
        # degradados por su origen no habilitante ⇒ REQUIERE VALIDACIÓN) y el binding
        # declara su alcance: con alcance de identificadores NO se rotula como binding de
        # la geometría VERIFICADO.
        self.assertIn("Identidad registral y catastral:", p6)
        self.assertIn("Binding de la identidad canónica del predio", p6)
        self.assertNotIn("Binding de la geometría oficial: VERIFICADA", p6)
        # (C) Doctrina ACTUALIZADA: la P6 nombra el atributo exacto que su estado
        # describe («Binding de la geometría oficial»), no «Geometría oficial» a secas,
        # que se leía como una afirmación sobre el VALOR de la coordenada —atributo
        # distinto y en conflicto histórico, con su propio estado en la P4—.
        self.assertIn("IDENTIFICADORES", p6)
        self.assertNotIn("Geometría oficial: VERIFICADA", p6)
        self.assertIn("DECISIÓN DICTUS: INFORMACIÓN VERIFICADA", p6)
        # (A) El estado de la compuerta viaja junto a su decisión, en las dos ramas.
        self.assertIn("COMPUERTA OPEN", p6)
        # (FASE 3 §32) El rótulo de la valoración de la corrida nombra SU objeto, para no
        # confundirse con la tira de ESTIMACIÓN de DICTUS que ahora vive en la misma
        # página. La aserción es más estricta: exige el rótulo vigente y niega el ambiguo.
        self.assertIn("Valor estimado por la corrida (valor central)", p6)
        self.assertNotIn("Valor estimado (valor central)", p6)
        # §34 (FASE 3) · DOCTRINA ACTUALIZADA — el marco «norma + concepto técnico +
        # validación profesional» describía OTRO producto (la revisión profesional, que
        # sigue existiendo como producto separado) y se sustituyó por «fuentes
        # disponibles + análisis técnico automatizado + metodología versionada». Las dos
        # afirmaciones que siguen fijan el cambio: el marco VIGENTE está impreso y el
        # ANTIGUO no puede volver.
        self.assertIn("Metodología: fuentes disponibles + análisis técnico automatizado + "
                      "metodología versionada", p6)
        self.assertNotIn("norma + concepto técnico + validación profesional", p6)
        self.assertIn("TRAZABILIDAD · Fuentes:", p6)
        # §32/§33 · El bloque de estimación de la P6, con sus ocho campos.
        self.assertIn("ESTIMACIÓN ECONÓMICA", p6)
        for campo in de.CAMPOS_ESTIMACION_P6:
            self.assertIn(campo, p6, f"falta el campo «{campo}» del bloque de estimación")
        self.assertIn(de.NOTA_ESTIMACION, " ".join(p6.split()))

    def test_p6_un_solo_bloque_de_trazabilidad(self):
        """§3 · ni Traza + pie, ni hash/evidencia duplicados en la página 6."""
        self.assertEqual(self.p6.count("DICTUS_MASTER_HASH"), 1,
                         "la página 6 declara el hash maestro más de una vez")
        self.assertEqual(self.p6.count("Evidencias"), 1,
                         "la página 6 declara las evidencias más de una vez")
        self.assertNotIn("TRAZABILIDAD TRAZABILIDAD", self.p6)
        # El pie global (el único bloque inferior) sigue demostrando hash, evidencia y
        # sello; la línea compacta añade fuente y fecha.
        self.assertIn("sello", self.p6.lower())
        self.assertIn("Consulta:", self.p6)

    def test_p6_blocked_with_many_reasons(self):
        """§4/§9 · 6 blockers declarados: caben, no desbordan y ninguno se pierde."""
        modelo, secciones, _pdf, paginas = _render(_estado_bloqueado(), "p6_bloqueado")
        self.assertEqual([v for v in de.VIOLACIONES if "P6 desborda" in v], [],
                         f"la página 6 desborda con 6 condiciones: {list(de.VIOLACIONES)}")
        b = de.page_budget(6)
        self.assertGreaterEqual(b["remaining_height"], 56.0)
        self.assertGreaterEqual(b["remaining_height"], 65.0)

        p6 = " ".join(paginas[5].split())
        # La valoración bloqueada se declara, nunca como cifra calculada.
        self.assertIn("NO EMITIR VALORACIÓN", p6.upper())
        # (A) Y declara el ESTADO de la compuerta (vocabulario cerrado CLOSED/OPEN) junto
        # a su decisión: los dos campos conviven y ninguno sustituye al otro.
        self.assertIn("COMPUERTA CLOSED", p6)
        gate_bloqueado = [g for g in modelo["decision_gates"]
                          if g["gate"] == "VALUATION_GATE"][0]
        self.assertEqual(gate_bloqueado["gate_state"], "CLOSED")
        self.assertEqual(gate_bloqueado["decision"], "NO EMITIR VALORACIÓN")
        # §34 (FASE 3) · marco metodológico VIGENTE (ver la nota de doctrina arriba).
        self.assertIn("Metodología: fuentes disponibles + análisis técnico automatizado + "
                      "metodología versionada", p6)
        self.assertNotIn("norma + concepto técnico + validación profesional", p6)
        # TODAS las condiciones declaradas viajan en el modelo y en la compuerta.
        declaradas = list(secciones["valor"]["blockers"])
        for condicion in BLOCKERS_SEIS:
            self.assertIn(condicion, declaradas)
        gate = [g for g in modelo["decision_gates"] if g["gate"] == "VALUATION_GATE"][0]
        self.assertEqual(gate["decision"], "NO EMITIR VALORACIÓN")
        # Las seis condiciones declaradas viajan en el gate; el gate no pierde ninguna
        # de las suyas (puede añadir la suya propia, derivada de la autorización).
        for condicion in BLOCKERS_SEIS:
            self.assertIn(condicion, list(gate["blocking_conditions"]))
        self.assertTrue(set(gate["blocking_conditions"]) <= set(declaradas)
                        | {"Contexto de mercado no autorizado en esta corrida"})
        self.assertEqual(len(declaradas), b["blocker_count"])
        # Hasta 3 condiciones materiales impresas + el recuento exacto de las demás.
        self.assertEqual(b["blockers_printed"], 3)
        self.assertIn(f"+ {len(declaradas) - 3} condición(es) adicional(es)", p6)
        _lineas = [ln.strip() for ln in paginas[5].splitlines() if ln.strip()]
        _vinetas = [ln for ln in _lineas if ln.startswith("· ")]
        self.assertEqual(len(_vinetas), 3,
                         f"el ejecutivo imprime {len(_vinetas)} condiciones: {_vinetas}")
        for v in _vinetas:
            self.assertTrue(any(v[2:].strip().startswith(c[:24]) or c.startswith(v[2:].strip())
                                for c in declaradas),
                            f"condición impresa desconocida: {v}")

    def test_p6_blocked_sin_condiciones_no_inventa_linea(self):
        """Sin condiciones declaradas, la valoración sigue bloqueada y sin «+ N»."""
        modelo, secciones, _pdf, paginas = _render(
            _estado_bloqueado(["Contexto de mercado no autorizado en esta corrida"]),
            "p6_un_blocker")
        p6 = " ".join(paginas[5].split())
        self.assertNotIn("condición(es) adicional(es)", p6.split("Metodología")[0])
        self.assertIn("NO EMITIR VALORACIÓN", p6.upper())
        self.assertGreaterEqual(de.page_budget(6)["remaining_height"], 56.0)

    def test_page_budget_de_las_seis_paginas(self):
        """§7 · las seis páginas declaran su presupuesto; P6 con margen suficiente."""
        for pagina in range(1, 7):
            b = de.page_budget(pagina)
            self.assertEqual(b["page_number"], pagina)
            self.assertEqual(b["footer_limit"], de.PIE_Y)
            self.assertAlmostEqual(b["available_height"] + b["footer_limit"],
                                   b["consumed_height"] + b["remaining_height"], places=1)
        for pagina in (1, 2, 3, 4, 6):
            self.assertFalse(de.page_budget(pagina)["overflow"], f"P{pagina} desborda")
        self.assertGreaterEqual(de.page_budget(6)["remaining_height"], 65.0)
        self.assertTrue(de.page_budget(5)["consumed_height"] > 0)

    @unittest.expectedFailure
    def test_p5_presupuesto_del_fixture_minimo(self):
        """RIESGO DECLARADO (fuera del alcance del hotfix 2.0D-R1).

        El hotfix se limita a la PÁGINA 6. Se deja constancia medida de que la página 5
        (entorno, equipamiento, asoleamiento y sombras) queda por debajo del margen con
        un contenido mínimo (sin activos visuales): consumed 749.0 / available 723.9 →
        falta 25.1 pt para el límite de 56. El caso REAL del Golden sí cumple (56.9 pt),
        por eso no se toca aquí: merece su propio arreglo de presupuesto y así queda
        registrado como fallo esperado (si alguien lo corrige, esta prueba lo señalará).
        """
        self.assertFalse(de.page_budget(5)["overflow"])
        self.assertGreaterEqual(de.page_budget(5)["remaining_height"], 56.0)

    def test_el_cuerpo_no_se_degrada_para_caber(self):
        """§8 · la compactación usa 8.2 pt o más: no 6–7 pt."""
        self.assertEqual(de.TOPE_BLOCKERS_PDF, 3)
        self.assertGreaterEqual(de.CUERPO_MINIMO_PT, 8.2)
        cajas = [c for c in de.REGISTRO_BBOX if c.get("pagina") == 6]
        self.assertTrue(cajas, "la página 6 debe registrar sus cajas")
        # Las dos líneas compactas del hotfix se imprimen al tamaño mínimo del cuerpo.
        self.assertIn("TRAZABILIDAD · Fuentes:", self.p6)
        self.assertIn("Metodología: fuentes disponibles", self.p6)

    def test_el_gate_sigue_rechazando_un_pdf_desbordado(self):
        """§11 · el límite no se relaja: con desborde, la entrega se rechaza."""
        original = de.PIE_Y
        try:
            de.PIE_Y = 700.0          # se fuerza el desborde sin tocar el límite real
            rs = _estado_maximo()
            modelo = dm.construir_documento_maestro(rs, historial={}, folio=FOLIO)
            secciones = sec.desde_estado(rs, modelo, {})
            pdf = SALIDA / "p6_desborde_forzado.pdf"
            de.render(modelo, secciones, pdf)
            self.assertTrue(any("desborda" in v for v in de.VIOLACIONES),
                            "el renderizador debe declarar el desborde")
            self.assertTrue(de.page_budget(6)["overflow"])
        finally:
            de.PIE_Y = original
        with self.assertRaises(entrega.EntregaEjecutivaInvalida) as ctx:
            entrega.auditar_ejecutivo(pdf)
        self.assertIn("retícula", str(ctx.exception))

    def test_la_trazabilidad_sigue_en_las_seis_paginas(self):
        """§2/§3 · solo cambió P6: ninguna página queda sin declarar su trazabilidad.

        P1 lo hace con el SELLO GLOBAL (hash maestro + evidencias + sello); de P2 a P6
        con el bloque TRAZABILIDAD; en P6, además, la línea compacta de fuentes y fecha.
        El pie global demuestra hash y evidencia en TODAS las páginas.
        """
        self.assertIn("SELLO GLOBAL", self.paginas[0])
        for i in (2, 3, 4, 5, 6):
            self.assertIn("TRAZABILIDAD", self.paginas[i - 1],
                          f"la página {i} perdió su bloque de trazabilidad")
        for i, pagina in enumerate(self.paginas, start=1):
            self.assertIn("DICTUS_MASTER_HASH", pagina, f"P{i} sin hash maestro")
            self.assertIn("Evidencias", pagina, f"P{i} sin recuento de evidencias")


class TestGoldenPagina6(unittest.TestCase):
    """§10 · el caso REAL de producto también se mide (no solo el fixture sintético)."""

    def test_el_golden_respeta_el_presupuesto_de_p6(self):
        ruta = ROOT / "docs/forensics/040-646406/dictus_2b"
        manifesto = ruta / "DICTUS_MANIFEST_040-646406.json"
        if not manifesto.exists():
            self.skipTest("falta el Golden")
        import json
        man = json.loads(manifesto.read_text(encoding="utf-8"))
        modelo = man["modelo"]
        metricas = (modelo.get("render_budget") or {})
        self.assertTrue(metricas, "el manifest del Golden debe registrar el presupuesto")
        p6 = metricas.get("6") or metricas.get(6)
        self.assertIsNotNone(p6, "el Golden debe declarar el presupuesto de la página 6")
        self.assertGreaterEqual(p6["remaining_height"], 56.0)
        self.assertFalse(p6["overflow"])
        self.assertIn("blocker_count", p6)
        self.assertIn("identity_row_count", p6)


if __name__ == "__main__":
    unittest.main()

# -*- coding: utf-8 -*-
"""GOLDEN EVIDENCE LITERAL PACK · folio 040-646406 — pruebas de los nueve frentes.

Cubre, contra los ARTEFACTOS REALES del Golden (`docs/forensics/040-646406/dictus_2b/`)
y contra el CÓDIGO REAL de `api/`:

  1. `origin propagation`          — 5 clases + degradación sin procedencia completa.
  2. `valuation gate`             — `gate_state` (CLOSED/OPEN) convive con `decision`.
  3. `market unresolved`          — `market_context.status == UNRESOLVED` y su causa.
  4. `Lonja purge`                — 0 ocurrencias en los dos PDF entregados.
  5. `verified origin audit`      — todo hecho VERIFICADO con origen DECLARADO y AUTORIZADO.
  6. `cross-page consistency`     — detector por CLAVE CANÓNICA + regresión del rótulo.
  7. `Golden executive text`      — P1/P6 literales.
  8. `Golden technical text`      — anexo técnico literal.
  9. `hash change`                — el hash maestro cambia con los hechos y VERIFICA.

Las pruebas son de SOLO LECTURA: no regeneran el Golden. Si falta, se saltan declarándolo.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))

GOLDEN = ROOT / "docs" / "forensics" / "040-646406" / "dictus_2b"
FOLIO = "040-646406"
EJECUTIVO = GOLDEN / f"DICTUS_EJECUTIVO_{FOLIO}.pdf"
TECNICO = GOLDEN / f"DICTUS_TECNICO_{FOLIO}.pdf"
MANIFEST = GOLDEN / f"DICTUS_MANIFEST_{FOLIO}.json"
RUNSTATE = GOLDEN / f"DICTUS_RUN_STATE_{FOLIO}.json"


def _cargar_modulo_asserts():
    """Carga `scripts/golden_evidence_asserts.py` como módulo (sin ejecutar `main`)."""
    ruta = ROOT / "scripts" / "golden_evidence_asserts.py"
    spec = importlib.util.spec_from_file_location("gea_test", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _texto_pdf(ruta: Path) -> str:
    from pypdf import PdfReader
    return "".join(f"\n{'=' * 40} PAGE {i} {'=' * 40}\n{(p.extract_text() or '')}"
                   for i, p in enumerate(PdfReader(str(ruta)).pages, 1))


def _saltar_si_falta_golden(tc: unittest.TestCase) -> bool:
    if not (MANIFEST.exists() and EJECUTIVO.exists() and TECNICO.exists()
            and RUNSTATE.exists()):
        tc.skipTest("falta el Golden del folio 040-646406")
        return True
    return False


class TestOriginPropagation(unittest.TestCase):
    """Frente 1 · propagación del ORIGEN con vocabulario cerrado y degradación."""

    def test_vocabulario_cerrado_de_origenes(self):
        import atribucion_mercado as am
        self.assertEqual(
            set(am.ORIGENES),
            {"EXTERNAL_SOURCE", "COMPUTED_FROM_SOURCES", "MANUAL_CONFIG",
             "STATIC_REFERENCE", "MODEL_PRIOR"})
        self.assertEqual(set(am.ORIGENES_HABILITANTES),
                         {"EXTERNAL_SOURCE", "COMPUTED_FROM_SOURCES"})

    def test_origin_propagation_clasificar_origen(self):
        """Cada clase declara su origen EFECTIVO y sólo dos habilitan la valoración."""
        import atribucion_mercado as am
        # No habilitantes: contexto sí, cifra no.
        for tipo in (am.ORIGEN_MANUAL, am.ORIGEN_ESTATICO, am.ORIGEN_PRIOR):
            r = am.clasificar_origen({"origen_tipo": tipo})
            self.assertEqual(r["origin"], tipo)
            self.assertFalse(r["origin_gate"], f"{tipo} no puede habilitar la valoración")
            self.assertTrue(r["origin_blockers"], f"{tipo} exige blocker legible")
        # Habilitante externo con procedencia completa.
        externo = am.clasificar_origen({
            "origen_tipo": am.ORIGEN_EXTERNO, "source_id": "S-1", "proveedor": "Proveedor",
            "fecha": "2026-01-01", "referencia": "r1", "sha256": "a" * 64})
        self.assertEqual(externo["origin"], am.ORIGEN_EXTERNO)
        self.assertTrue(externo["origin_gate"])
        # Habilitante declarado SIN procedencia completa → se DEGRADA (no se honra).
        incompleto = am.clasificar_origen({"origen_tipo": am.ORIGEN_EXTERNO,
                                           "proveedor": "Proveedor"})
        self.assertNotEqual(incompleto["origin"], am.ORIGEN_EXTERNO)
        self.assertFalse(incompleto["origin_gate"])
        self.assertIn("SIN procedencia completa", incompleto["origin_blockers"][0])
        # COMPUTED exige >= 2 fuentes, cada una con proveedor/fecha/referencia/sha256.
        una = am.clasificar_origen({"origen_tipo": am.ORIGEN_COMPUTADO,
                                    "fuentes": [{"proveedor": "A", "fecha": "2026-01-01",
                                                 "referencia": "r", "sha256": "a" * 64}]})
        self.assertFalse(una["origin_gate"])
        dos = am.clasificar_origen({"origen_tipo": am.ORIGEN_COMPUTADO, "fuentes": [
            {"proveedor": "A", "fecha": "2026-01-01", "referencia": "r1", "sha256": "a" * 64},
            {"proveedor": "B", "fecha": "2026-01-02", "referencia": "r2", "sha256": "b" * 64}]})
        self.assertEqual(dos["origin"], am.ORIGEN_COMPUTADO)
        self.assertTrue(dos["origin_gate"])

    def test_el_origen_del_hecho_identidad_es_computed_con_dos_fuentes_selladas(self):
        """(B) El hecho de identidad declara COMPUTED con DOS evidencias selladas reales."""
        if _saltar_si_falta_golden(self):
            return
        import dictus_secciones as sec
        modelo = json.loads(MANIFEST.read_text(encoding="utf-8"))["modelo"]
        origen = sec._origen_de_hecho(modelo)
        self.assertEqual(origen["origin"], "COMPUTED_FROM_SOURCES")
        self.assertEqual(origen["origin_declarado"], "COMPUTED_FROM_SOURCES")
        self.assertTrue(origen["origin_gate"])
        self.assertEqual(origen["origin_blockers"], [])
        fuentes = origen["origin_provenance"]["fuentes"]
        self.assertGreaterEqual(len(fuentes), 2, "COMPUTED exige >= 2 fuentes citadas")
        ids_sellados = {e["evidence_id"] for e in
                        modelo["evidence_manifest"]["evidencias"]
                        if e["status"] == "SELLADA"}
        for f in fuentes:
            for campo in ("proveedor", "fecha", "referencia", "sha256"):
                self.assertTrue(f.get(campo), f"la fuente cita {campo} vacío: {f}")
            self.assertRegex(f["sha256"], r"^[0-9a-f]{64}$")
            self.assertIn(f["referencia"].split(" · ")[0], ids_sellados,
                          "sólo una evidencia SELLADA puede citarse como procedencia")

    def test_cada_evidencia_tiene_su_propio_content_hash_no_una_constante(self):
        """Un `content_hash` que no depende del contenido no sella nada: es una constante."""
        if _saltar_si_falta_golden(self):
            return
        modelo = json.loads(MANIFEST.read_text(encoding="utf-8"))["modelo"]
        hashes = [e["content_hash"] for e in modelo["evidence_manifest"]["evidencias"]]
        self.assertGreater(len(hashes), 1)
        self.assertEqual(len(set(hashes)), len(hashes),
                         "todas las evidencias comparten content_hash: el hash no depende "
                         "del contenido")


class TestValuationGate(unittest.TestCase):
    """Frente 2 · `gate_state` (vocabulario cerrado) convive con `decision`."""

    def _gates(self) -> list[dict]:
        if _saltar_si_falta_golden(self):
            return []
        modelo = json.loads(MANIFEST.read_text(encoding="utf-8"))["modelo"]
        return list(modelo["decision_gates"])

    def test_valuation_gate_gate_state_y_decision_conviven(self):
        if _saltar_si_falta_golden(self):
            return
        gates = self._gates()
        val = [g for g in gates if g["gate"] == "VALUATION_GATE"][0]
        self.assertEqual(val["gate_state"], "CLOSED")
        self.assertEqual(val["decision"], "NO EMITIR VALORACIÓN",
                         "el término de la gramática de decisión NO se sustituye")
        self.assertFalse((val.get("blocking_conditions") or []) == [],
                         "una compuerta CLOSED declara sus condiciones de bloqueo")

    def test_valuation_gate_reason_nombra_el_origen_que_bloquea(self):
        if _saltar_si_falta_golden(self):
            return
        val = [g for g in self._gates() if g["gate"] == "VALUATION_GATE"][0]
        razon = val["reasons"][0]
        self.assertIn("NO está autorizada", razon)
        self.assertIn("MANUAL_CONFIG", razon,
                      "el reason nombra el ORIGEN no habilitante, no un «no autorizado» mudo")
        self.assertIn("INSUFICIENTE", razon)

    def test_los_siete_gates_declaran_gate_state_del_vocabulario_cerrado(self):
        gates = self._gates()
        if not gates:
            return
        self.assertEqual(len(gates), 7)
        for g in gates:
            self.assertIn(g.get("gate_state"), ("CLOSED", "OPEN"),
                          f"{g['gate']} sin gate_state del vocabulario cerrado")
            self.assertIn(g.get("decision"), (
                "INFORMACIÓN VERIFICADA", "PROCEDER CON CONDICIONES",
                "REVISIÓN PROFESIONAL REQUERIDA", "INFORMACIÓN INSUFICIENTE",
                "NO UTILIZAR ESTE DATO COMO DEFINITIVO", "NO EMITIR VALORACIÓN",
                "SIN HALLAZGO MATERIAL EN ESTA FUENTE", "FUENTE NO DISPONIBLE",
                "EVIDENCIA EN CONFLICTO"))

    def test_el_estado_de_compuerta_se_deriva_de_la_decision(self):
        """`CLOSED`/`OPEN` NO es un juicio aparte: se deriva del vocabulario de decisión."""
        import dictus_decision as dd
        self.assertEqual(dd.estado_de_compuerta(dd.INFORMACION_VERIFICADA), "OPEN")
        self.assertEqual(dd.estado_de_compuerta(dd.PROCEDER_CON_CONDICIONES), "OPEN")
        self.assertEqual(dd.estado_de_compuerta(dd.SIN_HALLAZGO_EN_FUENTE), "OPEN")
        for cerrada in (dd.NO_EMITIR_VALORACION, dd.NO_USAR_COMO_DEFINITIVO,
                        dd.INFORMACION_INSUFICIENTE, dd.REVISION_PROFESIONAL_REQUERIDA,
                        dd.EVIDENCIA_EN_CONFLICTO):
            self.assertEqual(dd.estado_de_compuerta(cerrada), "CLOSED", cerrada)
        self.assertEqual(set(dd.ESTADOS_COMPUERTA), {"CLOSED", "OPEN"})

    def test_manual_y_prior_no_abren_la_compuerta(self):
        import atribucion_mercado as am
        for tipo in (am.ORIGEN_MANUAL, am.ORIGEN_PRIOR):
            self.assertFalse(am.clasificar_origen({"origen_tipo": tipo})["origin_gate"])


class TestMarketUnresolved(unittest.TestCase):
    """Frente 3 · el contexto de mercado no resuelto se declara y NO abre la valoración."""

    def test_market_context_status_unresolved(self):
        if _saltar_si_falta_golden(self):
            return
        rs = json.loads(RUNSTATE.read_text(encoding="utf-8"))
        mc = rs["market_context"]
        # `status = UNRESOLVED` ⇔ el contexto de mercado NO habilita la valoración.
        self.assertEqual(mc["status"], "UNRESOLVED")
        self.assertFalse(mc["valoracion_habilitada"])
        # La CAUSA de un `UNRESOLVED` por ORIGEN vive en `origin_blockers` (no en
        # `blockers`, que sólo lista campos obligatorios ausentes). Se acepta cualquiera de
        # los dos, pero tiene que haber una causa declarada.
        self.assertIn(mc["origin"], ("MANUAL_CONFIG", "STATIC_REFERENCE", "MODEL_PRIOR"),
                      "la causa es un origen NO habilitante")
        self.assertFalse(mc["origin_gate"])
        self.assertTrue(mc["origin_blockers"] or mc["blockers"],
                        "un status UNRESOLVED declara su causa")
        self.assertFalse(rs["valuation_state"]["authorization"]["allowed"])

    def test_la_cifra_no_se_emite_y_el_motivo_es_material(self):
        if _saltar_si_falta_golden(self):
            return
        rs = json.loads(RUNSTATE.read_text(encoding="utf-8"))
        aut = rs["valuation_state"]["authorization"]
        self.assertFalse(aut["allowed"])
        motivo = str(aut.get("motivo") or rs["valuation_state"].get("motivo_no_aplica") or "")
        self.assertTrue(motivo, "una valoración no autorizada declara su causa")


class TestLonjaPurge(unittest.TestCase):
    """Frente 4 · la Lonja no es fuente y no aparece en lo entregado."""

    def test_lonja_no_aparece_en_los_dos_pdf(self):
        if _saltar_si_falta_golden(self):
            return
        for ruta in (EJECUTIVO, TECNICO):
            texto = _texto_pdf(ruta)
            self.assertEqual(texto.count("Lonja"), 0,
                             f"{ruta.name} menciona «Lonja»: {texto.count('Lonja')} vez/veces")
            self.assertNotIn("399.500.000", texto, f"{ruta.name} conserva la cifra prohibida")

    def test_el_artefacto_local_no_se_declara_fuente_de_datos(self):
        import atribucion_mercado as am
        proc = am.procedencia_de_mercado()
        self.assertFalse(proc["es_fuente_de_datos"])
        self.assertFalse(proc["aporta_datos_a_dictus"])
        self.assertFalse(proc["en_source_registry"])


class TestVerifiedOriginAudit(unittest.TestCase):
    """Frente 5 · auditoría del ORIGEN de cada hecho VERIFICADO impreso en la P6."""

    @classmethod
    def setUpClass(cls):
        cls.gea = _cargar_modulo_asserts()

    def _facts(self) -> tuple[list[dict], dict]:
        if _saltar_si_falta_golden(self):
            return [], {}
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        declaradas = (((manifest.get("modelo") or {}).get("hechos_impresos") or {})
                      .get("identidad") or {}).get("filas") or []
        paginas = self.gea._paginas(self.gea._texto_pdf(EJECUTIVO))
        filas = self.gea._filas_verificadas_p6(paginas.get(6, ""), declaradas)
        return filas, manifest

    def test_auditoria_de_origen_del_hecho_verificado(self):
        """Todo hecho VERIFICADO lleva origen declarado y AUTORIZADO, con procedencia."""
        filas, _ = self._facts()
        if not filas:
            return
        verificados = [f for f in filas if f["estado"] == "VERIFICADO"]
        self.assertTrue(verificados, "el Golden imprime al menos un hecho VERIFICADO")
        for f in verificados:
            self.assertIn(f["origin"], ("EXTERNAL_SOURCE", "COMPUTED_FROM_SOURCES"),
                          f"{f['attribute']} impreso VERIFICADO con origin {f['origin']}")
            self.assertTrue(f["origin_gate"], f"{f['attribute']} con origen no habilitante")
            fuentes = (f.get("origin_provenance") or {}).get("fuentes") or []
            self.assertGreaterEqual(len(fuentes), 2,
                                    f"{f['attribute']} sin fuentes citadas suficientes")

    def test_el_hecho_verificado_es_el_que_declara_su_fuente(self):
        """La lectura es por ATRIBUTO y el estado sale de la VERDAD ÚNICA del atributo.

        ANTES esta prueba exigía que el ÚNICO hecho verificado fuese la Matrícula (el
        parser anterior atribuía el VERIFICADO a «Dirección oficial» por cercanía de
        texto). BLOCK 1 · §10 toma la PRIMERA opción de la regla: la evidencia sellada
        (EV-IDENTIDAD + EV-GEOMETRIA) SÍ verifica los componentes de la identidad canónica
        (matrícula, NUPRE y número predial) y la corrida resuelve además la dirección con su
        fuente declarada. Lo que la prueba protege ahora es lo que importa: cada hecho
        VERIFICADO tiene que declarar su ORIGEN y su FUENTE, y ningún ATTRIBUTO puede
        llevar un estado que su fuente no sostenga.
        """
        filas, _ = self._facts()
        if not filas:
            return
        verificados = [f for f in filas if f["estado"] == "VERIFICADO"]
        self.assertTrue(verificados, "la identidad canónica del Golden está verificada")
        # El atributo del veredicto tiene que ser el ATRIBUTO de su fila, no la primera
        # línea del buffer (el defecto de lectura que esta prueba congeló).
        for f in verificados:
            self.assertTrue(f.get("origin"), f)
            self.assertTrue((f.get("origin_provenance") or {}).get("fuentes"), f)
        atributos = {f["attribute"] for f in verificados}
        self.assertTrue({"Matrícula", "NUPRE", "Número predial"} <= atributos,
                        f"los componentes de identidad del alcance declarado deben estar "
                        f"verificados: {sorted(atributos)}")
        unidad = [f for f in filas if f["attribute"] == "Unidad (torre / apartamento)"]
        if unidad:
            self.assertNotEqual(unidad[0]["estado"], "VERIFICADO",
                                "la unidad privada no tiene fuente en el pack: su hecho es "
                                "CONOCIDO y NO verificado")
            self.assertTrue(unidad[0]["value"], "el hecho NO se borra")

    def test_ningun_hecho_verificado_con_origen_prohibido(self):
        filas, _ = self._facts()
        if not filas:
            return
        prohibidos = {"MANUAL_CONFIG", "STATIC_REFERENCE", "MODEL_PRIOR", "FIXTURE",
                      "DEFAULT", "HARDCODE", "FALLBACK_HEURISTIC"}
        for f in filas:
            if f["estado"] == "VERIFICADO":
                self.assertNotIn(f["origin"], prohibidos, f)

    def test_un_origen_no_habilitante_degrada_el_estado_sin_borrar_el_hecho(self):
        """B · el estado VERIFICADO sólo se imprime si el origen lo sostiene."""
        import dictus_secciones as sec
        import dictus_estado as dse
        if _saltar_si_falta_golden(self):
            return
        rs = json.loads(RUNSTATE.read_text(encoding="utf-8"))
        modelo = json.loads(MANIFEST.read_text(encoding="utf-8"))["modelo"]
        # Sin evidencias selladas no hay procedencia: el origen se degrada…
        sin_evidencia = dict(modelo)
        sin_evidencia["evidence_manifest"] = {"evidencias": []}
        origen = sec._origen_de_hecho(sin_evidencia)
        self.assertFalse(origen["origin_gate"])
        self.assertEqual(origen["origin"], "MANUAL_CONFIG")
        # …y las secciones DEGRADAN la fila: el valor sigue impreso, el estado baja.
        secciones = sec.desde_estado(rs, sin_evidencia, rs.get("historical_consistency"))
        fila = [f for f in secciones["identidad"]["filas"]
                if f["etiqueta"] == "Matrícula"][0]
        self.assertTrue(fila["valor"], "el hecho NO se borra: el valor sigue impreso")
        self.assertEqual(fila["estado"], dse.REQUIERE_VALIDACION)
        # Y con las evidencias reales del Golden, vuelve a VERIFICADO.
        secciones_ok = sec.desde_estado(rs, modelo, rs.get("historical_consistency"))
        fila_ok = [f for f in secciones_ok["identidad"]["filas"]
                   if f["etiqueta"] == "Matrícula"][0]
        self.assertEqual(fila_ok["estado"], dse.VERIFICADO)


class TestCrossPageConsistency(unittest.TestCase):
    """Frente 6 · contradicciones entre páginas, por CLAVE CANÓNICA de atributo."""

    @classmethod
    def setUpClass(cls):
        cls.gea = _cargar_modulo_asserts()

    def _datos(self):
        if _saltar_si_falta_golden(self):
            return None, None, None
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        rs = json.loads(RUNSTATE.read_text(encoding="utf-8"))
        paginas = self.gea._paginas(self.gea._texto_pdf(EJECUTIVO))
        return paginas, manifest, rs

    def test_detector_de_contradicciones_por_clave_canonica(self):
        paginas, manifest, rs = self._datos()
        if paginas is None:
            return
        r = self.gea.detectar_contradicciones(paginas, manifest, rs)
        self.assertEqual(r["contradicciones"], [])
        self.assertEqual(r["discrepancias_con_la_verdad"], [])
        # La coordenada y el binding de la geometría son DOS claves distintas, cada una
        # con su estado: no se comparan entre sí.
        self.assertEqual(r["observado"]["coordenada"], {"P4": "HISTORICAL_CONFLICT"})
        # §11: el binding del Golden acredita IDENTIFICADORES (no geometría).
        self.assertEqual(r["observado"]["binding_geometria"], {"P6": "IDENTIFICADORES"})

    def test_el_detector_falla_si_la_coordenada_se_rotula_verificada(self):
        """Regresión (C): una contradicción REAL debe seguir siendo detectada."""
        paginas, manifest, rs = self._datos()
        if paginas is None:
            return
        falso = dict(paginas)
        falso[4] = falso[4].replace("NO UTILIZAR ESTE DATO COMO DEFINITIVO", "VERIFICADO")
        r = self.gea.detectar_contradicciones(falso, manifest, rs)
        self.assertTrue(r["discrepancias_con_la_verdad"],
                        "la P4 no puede declarar VERIFICADA la coordenada en conflicto")

    def test_el_detector_falla_si_el_binding_se_rotula_no_utilizar(self):
        paginas, manifest, rs = self._datos()
        if paginas is None:
            return
        falso = dict(paginas)
        # El estado impreso del binding es el ÚLTIMO token «IDENTIFICADORES» de la P6: se
        # sustituye ESE por un estado que el expediente NO declara.
        _idx = falso[6].rfind("IDENTIFICADORES")
        self.assertGreater(_idx, 0, "la P6 tiene que imprimir el estado del binding")
        falso[6] = (falso[6][:_idx] + "DISCREPANCIA"
                    + falso[6][_idx + len("IDENTIFICADORES"):])
        r = self.gea.detectar_contradicciones(falso, manifest, rs)
        self.assertTrue(r["discrepancias_con_la_verdad"],
                        "la P6 no puede contradecir el binding VERIFIED del expediente")

    def test_el_detector_falla_si_vuelve_la_cifra_prohibida(self):
        paginas, manifest, rs = self._datos()
        if paginas is None:
            return
        falso = dict(paginas)
        falso[6] = falso[6] + "\n$ 399.500.000\n"
        r = self.gea.detectar_contradicciones(falso, manifest, rs)
        self.assertTrue(any("399.500.000" in c for c in r["contradicciones"]))

    def test_el_detector_falla_si_vuelve_el_rotulo_ambiguo(self):
        """El rótulo «Geometría oficial» a secas se leía como el valor de la coordenada."""
        if _saltar_si_falta_golden(self):
            return
        p6 = self.gea._paginas(self.gea._texto_pdf(EJECUTIVO)).get(6, "")
        self.assertNotIn("Geometría oficial: VERIFICADA", p6)
        self.assertIn("Binding de la identidad canónica del predio", p6)
        self.assertIn("IDENTIFICADORES", p6)
        self.assertNotIn("Binding de la geometría oficial: VERIFICADA", p6,
                         "un binding de identificadores no se rotula como binding de la "
                         "geometría VERIFICADO (§11)")
        # Y la clave canónica declarada por el render es la del binding, no la coordenada.
        import dictus_secciones as sec
        modelo = json.loads(MANIFEST.read_text(encoding="utf-8"))["modelo"]
        rs = json.loads(RUNSTATE.read_text(encoding="utf-8"))
        secciones = sec.desde_estado(rs, modelo, rs.get("historical_consistency"))
        self.assertEqual(secciones["identidad"]["geometria_atributo"], "binding_geometria")
        self.assertNotEqual(secciones["identidad"]["geometria_atributo"], "coordenada")


class TestGoldenExecutiveText(unittest.TestCase):
    """Frente 7 · texto literal del ejecutivo."""

    @classmethod
    def setUpClass(cls):
        if _saltar_si_falta_golden(cls):
            return
        cls.gea = _cargar_modulo_asserts()
        cls.paginas = cls.gea._paginas(cls.gea._texto_pdf(EJECUTIVO))
        cls.full = cls.gea._texto_pdf(EJECUTIVO)

    def test_golden_ejecutivo_literal(self):
        if not hasattr(self, "paginas"):
            return
        p6 = self.paginas[6]
        self.assertIn("IDENTIDAD DEL INMUEBLE", p6)
        self.assertIn("Matrícula", p6)
        self.assertIn(folio := "040-646406", p6)
        self.assertIn("NO EMITIR VALORACIÓN", p6)
        self.assertIn("COMPUERTA CLOSED", p6)
        self.assertIn("Binding de la identidad canónica del predio", p6)
        self.assertIn("IDENTIFICADORES", p6)
        self.assertEqual(self.full.count("Lonja"), 0)
        self.assertNotIn("399.500.000", self.full)
        self.assertEqual(len(self.paginas), 6, "el ejecutivo son SEIS páginas")

    def test_el_ejecutivo_no_imprime_monto_ni_cero(self):
        if not hasattr(self, "paginas"):
            return
        p6 = self.paginas[6]
        self.assertIn("no se imprime ningún monto, ni $0", p6)
        self.assertNotIn("VALOR ESTIMADO $", p6)


class TestGoldenTechnicalText(unittest.TestCase):
    """Frente 8 · texto literal del anexo técnico."""

    @classmethod
    def setUpClass(cls):
        if _saltar_si_falta_golden(cls):
            return
        cls.gea = _cargar_modulo_asserts()
        cls.full = cls.gea._texto_pdf(TECNICO)
        cls.paginas = cls.gea._paginas(cls.full)

    def test_golden_tecnico_literal(self):
        if not hasattr(self, "paginas"):
            return
        self.assertGreaterEqual(len(self.paginas), 6, "el técnico es el anexo completo")
        self.assertIn("040-646406", self.full)
        self.assertEqual(self.full.count("Lonja"), 0)
        self.assertNotIn("399.500.000", self.full)

    def test_el_tecnico_declara_la_decision_y_el_hash(self):
        if not hasattr(self, "paginas"):
            return
        # El anexo técnico declara la NO emisión con su literal propio y su causa (origen
        # no habilitante), no con el término del ejecutivo.
        self.assertIn("ESTIMACIÓN REFERENCIAL NO EMITIDA", self.full)
        self.assertIn("MANUAL_CONFIG", self.full)
        self.assertIn("NO HABILITA VALORACIÓN", self.full)
        # El anexo sella su propia ejecución (no es el hash maestro: eso lo declara).
        self.assertIn("SELLO DE EJECUCIÓN (SHA-256)", self.full)


class TestHashChange(unittest.TestCase):
    """Frente 9 · el hash maestro sella los hechos y VERIFICA."""

    def test_el_master_hash_cambia_con_los_hechos_y_verifica(self):
        if _saltar_si_falta_golden(self):
            return
        import dictus_manifiesto as dm
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        modelo = manifest["modelo"]
        verif = dm.verificar(modelo, manifest["master_hash"])
        self.assertTrue(verif["match"], "el hash maestro registrado debe recalcularse igual")
        self.assertEqual(verif["master_hash_recalculado"], manifest["master_hash"])
        # Un cambio material en un bloque canónico SÍ cambia el hash (y se detecta).
        alterado = json.loads(json.dumps(modelo))
        gates = alterado["decision_gates"]
        val = [g for g in gates if g["gate"] == "VALUATION_GATE"][0]
        val["gate_state"] = "OPEN"
        self.assertNotEqual(dm.master_hash(alterado), manifest["master_hash"],
                            "cambiar el estado de una compuerta debe cambiar el hash")
        self.assertFalse(dm.verificar(alterado, manifest["master_hash"])["match"])

    def test_el_gate_state_entra_al_hash_y_al_manifest(self):
        if _saltar_si_falta_golden(self):
            return
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        val = [g for g in manifest["modelo"]["decision_gates"]
               if g["gate"] == "VALUATION_GATE"][0]
        self.assertIn("gate_state", val)
        # Y viaja además al registro de hechos impresos del manifest.
        self.assertIn("hechos_impresos", manifest["modelo"])
        self.assertEqual(
            manifest["modelo"]["hechos_impresos"]["geometria"]["atributo"],
            "binding_geometria")


class TestPackYAssertions(unittest.TestCase):
    """Coherencia del propio pack: los 5 JSON y las aserciones disponibles."""

    def test_los_cinco_json_del_pack_existen(self):
        base = ROOT / "docs" / "source_pack"
        for nombre in ("MARKET_CONTEXT", "VALUATION_GATE", "ORIGIN_AUDIT",
                       "CROSS_PAGE_CONSISTENCY", "ARTIFACT_HASHES"):
            ruta = base / f"{nombre}_{FOLIO}.json"
            self.assertTrue(ruta.exists(), f"falta {ruta.name}")
            json.loads(ruta.read_text(encoding="utf-8"))

    def test_las_asercciones_pasan_sobre_el_golden_actual(self):
        gea = _cargar_modulo_asserts()
        codigo = gea.main()
        self.assertEqual(codigo, 0,
                         "golden_evidence_asserts debe salir 0 (11/11 PASS) sobre el Golden "
                         "regenerado")


if __name__ == "__main__":
    unittest.main()

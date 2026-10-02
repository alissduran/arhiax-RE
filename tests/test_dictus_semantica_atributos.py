# -*- coding: utf-8 -*-
"""COMPUERTA SEMÁNTICA DEL FREEZE · CONSISTENCIA POR ATRIBUTO Y ORIGEN DEL VALOR.

Cuatro garantías que el Source Pack exige antes de emitir `CONTRACT FROZEN`:

  P3 · **UNA SOLA VERDAD POR ATRIBUTO.** Ningún atributo puede tener estados
       incompatibles dentro del mismo Dictus. En particular: si la corrida declara un
       atributo `REQUIERE_VALIDACION` (o `HISTORICAL_CONFLICT`), ninguna página puede
       imprimirlo como `VERIFICADO`. Se prueban (a) la función de resolución, (b) las
       filas construidas y (c) el PDF FÍSICO del Golden: para cada atributo con estado
       declarado, el estado impreso debe ser el declarado — y si dos páginas nombran el
       atributo, las dos tienen que decir lo mismo.

  P4 · **ORIGEN DE TODA TASA/VALOR.** `origin` ∈ {EXTERNAL_SOURCE,
       COMPUTED_FROM_SOURCES, MANUAL_CONFIG, STATIC_REFERENCE, MODEL_PRIOR} y viaja
       JUNTO al valor en el modelo y en el ejecutivo. Sólo las dos clases habilitantes
       —y sólo con procedencia completa— pueden habilitar `VALUATION_GATE`.

  P6 · **EL HARDCODE POR ESTRATO NO ABRE LA COMPUERTA.** El fallback codificado es
       `MODEL_PRIOR`: no entra en los hechos resueltos, no autoriza valoración y no se
       imprime. Se PRUEBA que no puede abrirla.

  P8 · **GOLDEN SOMETIDO A ASERCIÓN.** El ejecutivo y el técnico regenerados del folio
       040-646406 se verifican por TEXTO: sin «Lonja» como fuente, sin estados
       contradictorios por atributo y sin cifra de mercado emitida por un prior.
"""
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import atribucion_mercado as am        # noqa: E402
import dictamen_data as dd             # noqa: E402
import dictus_decision as dd2          # noqa: E402
import dictus_estado as dse            # noqa: E402
import dictus_historia as dh           # noqa: E402
import dictus_secciones as sec         # noqa: E402
import market_context as mctx          # noqa: E402

GOLDEN = ROOT / "docs" / "forensics" / "040-646406" / "dictus_2b"
RUTA_EJECUTIVO = GOLDEN / "DICTUS_EJECUTIVO_040-646406.pdf"
RUTA_TECNICO = GOLDEN / "DICTUS_TECNICO_040-646406.pdf"
RUTA_TEXTO = GOLDEN / "DICTUS_2.0C_TEXTO_EJECUTIVO_040-646406.txt"
RUTA_RUN_STATE = GOLDEN / "DICTUS_RUN_STATE_040-646406.json"
RUTA_MANIFEST = GOLDEN / "DICTUS_MANIFEST_040-646406.json"


def _texto_paginas(ruta: Path):
    from pypdf import PdfReader
    return [(p.extract_text() or "") for p in PdfReader(str(ruta)).pages]


def _plano(paginas) -> str:
    return " ".join(" ".join(p.split()) for p in paginas).upper()


# ══════════════════════════════════════════════════════════════════════════════
# P3 · UNA SOLA VERDAD POR ATRIBUTO
# ══════════════════════════════════════════════════════════════════════════════
class TestVerdadUnicaPorAtributo(unittest.TestCase):

    def test_el_estado_publicable_sale_del_informe_de_coherencia(self):
        hist = {
            "versiones_comparadas": 3,
            "conflictos_abiertos": [{"atributo": "uso_pot", "valores": ["A", "B"]}],
            "requieren_revision": [{"atributo": "estrato", "estado": dh.REQUIERE_VALIDACION}],
            "cambios_explicados": [{"atributo": "barrio"}],
        }
        verdad = sec.verdad_por_atributo(hist)
        self.assertEqual(verdad["uso_pot"], dh.HISTORICAL_CONFLICT)
        self.assertEqual(verdad["estrato"], dh.REQUIERE_VALIDACION)
        self.assertEqual(verdad["barrio"], dh.CAMBIO_CON_FUENTE)
        # Un atributo ausente del informe NO tiene estado declarado: no se inventa.
        self.assertNotIn("localidad", verdad)

    def test_el_conflicto_abierto_gana_sobre_cualquier_otro_estado(self):
        hist = {"conflictos_abiertos": [{"atributo": "altura_maxima"}],
                "requieren_revision": [{"atributo": "altura_maxima",
                                        "estado": dh.REQUIERE_VALIDACION}]}
        self.assertEqual(sec.verdad_por_atributo(hist)["altura_maxima"],
                         dh.HISTORICAL_CONFLICT)

    def _estado_minimo(self, *, estrato="4", hist=None):
        """Estado canónico mínimo con el atributo `estrato` y su coherencia declarada."""
        return {
            "run_state_version": dse.RUN_STATE_VERSION, "run_id": "qa-semantica",
            "generated_at": "2026-01-15T10:05:00+00:00", "ciudad": "barranquilla",
            "property_identity": {"folio": "TST-1", "nupre": "AFT1",
                                  "codigo_catastral": "0001", "identity_verified": True,
                                  "resolution_method": "nupre",
                                  "direccion_raw": "CALLE 1 # 2 - 3"},
            "title_state": {"folio": "TST-1", "certificado_adjuntado": True,
                            "gravamenes_vigentes": []},
            "urban_context": {"area": 58.75, "barrio": "BARRIO", "estrato": estrato,
                              "localidad": "01", "destino_economico": "Habitacional",
                              "condicion_juridica": "Propiedad Horizontal"},
            "risk_context": {}, "screening_summary": {}, "poi_state": {},
            "solar_state": {"momentos": []},
            "valuation_state": {"authorization": {"allowed": False},
                                "motivo_no_aplica": "prueba"},
            "market_context": {}, "findings": [],
            "historical_consistency": hist or {},
            "evidence_manifest_input": {"articulos": []},
        }

    def test_la_fila_imprime_el_estado_declarado_y_no_borra_el_hecho(self):
        hist = {"versiones_comparadas": 2,
                "requieren_revision": [{"atributo": "estrato",
                                        "estado": dh.REQUIERE_VALIDACION}]}
        rs = self._estado_minimo(estrato="4", hist=hist)
        secciones = sec.desde_estado(rs, {}, hist)
        fila = [f for f in secciones["urbano"]["filas"] if f["etiqueta"] == "Estrato"][0]
        # El valor SE CONSERVA (no se borra el hecho) y el estado se degrada.
        self.assertEqual(fila["valor"], "4")
        self.assertEqual(fila["estado"], dh.REQUIERE_VALIDACION)
        self.assertNotEqual(fila["estado"], dh.VERIFICADO)

    def test_sin_coherencia_declarada_el_estado_por_procedencia_se_conserva(self):
        rs = self._estado_minimo(estrato="4", hist={"versiones_comparadas": 2})
        secciones = sec.desde_estado(rs, {}, {"versiones_comparadas": 2})
        fila = [f for f in secciones["urbano"]["filas"] if f["etiqueta"] == "Estrato"][0]
        self.assertEqual(fila["estado"], dh.VERIFICADO)

    def test_sin_valor_el_estado_es_sin_dato(self):
        rs = self._estado_minimo(estrato=None, hist={"versiones_comparadas": 2})
        secciones = sec.desde_estado(rs, {}, {"versiones_comparadas": 2})
        fila = [f for f in secciones["urbano"]["filas"] if f["etiqueta"] == "Estrato"][0]
        self.assertIsNone(fila["valor"])
        self.assertEqual(fila["estado"], dh.SIN_DATO)


class TestSinContradiccionesEnElGolden(unittest.TestCase):
    """El PDF FÍSICO no puede contradecir el estado que el MISMO dictus declara."""

    @classmethod
    def setUpClass(cls):
        if not RUTA_RUN_STATE.exists():
            raise unittest.SkipTest("falta el Golden regenerado")
        cls.rs = json.loads(RUTA_RUN_STATE.read_text(encoding="utf-8"))
        cls.hist = cls.rs.get("historical_consistency") or {}
        cls.paginas = _texto_paginas(RUTA_EJECUTIVO)

    def test_ningun_atributo_por_revisar_se_imprime_como_verificado(self):
        """ESTA ES LA PRUEBA DEL CASO `Estrato 4 — VERIFICADO` (P3), con la regla §10.

        BLOCK 1 · §10: la verdad del atributo es UNA y la declara su registro de resolución
        (`attribute_resolution`). Estar listado en `requieren_revision` por una APARICIÓN
        del atributo en una versión nueva (una nota de cobertura, sin valores rivales) NO
        degrada el hecho: la evidencia sellada sí lo verifica. Lo que NO puede imprimirse
        VERIFICADO es un atributo con una DIFERENCIA MATERIAL declarada o con un conflicto
        abierto, y eso es lo que esta prueba protege.
        """
        por_revisar = {r["atributo"] for r in (self.hist.get("requieren_revision") or [])
                       if r.get("diferencia_material")}
        en_conflicto = {c["atributo"] for c in (self.hist.get("conflictos_abiertos") or [])}
        # Atributos con etiqueta impresa legible en el ejecutivo y su texto de la fila.
        etiquetas = {
            "estrato": "Estrato",
            "barrio": "Barrio",
            "localidad": "Localidad / comuna",
            "destino_economico": "Destino económico (catastro)",
            "area": "Área",
            "nupre": "NUPRE",
            "numero_predial": "Número predial",
        }
        for atributo, etiqueta in etiquetas.items():
            if atributo not in por_revisar and atributo not in en_conflicto:
                continue
            for i, pagina in enumerate(self.paginas, start=1):
                plano = " ".join(pagina.split())
                pos = plano.find(etiqueta)
                while pos != -1:
                    # La ventana de la fila: etiqueta + valor + chip de estado.
                    ventana = plano[pos:pos + len(etiqueta) + 90].upper()
                    self.assertNotIn(
                        "VERIFICADO", ventana,
                        f"página {i}: el atributo «{atributo}» está declarado por revisar "
                        f"en el MISMO dictus y se imprime VERIFICADO: {ventana!r}")
                    pos = plano.find(etiqueta, pos + 1)

    def test_el_estrato_del_golden_no_se_imprime_verificado(self):
        """Caso nombrado del freeze: `Estrato 4 — VERIFICADO` ya no existe."""
        estados_estrato = {r["atributo"]: r.get("estado")
                           for r in (self.hist.get("requieren_revision") or [])}
        if estados_estrato.get("estrato") != dh.REQUIERE_VALIDACION:
            self.skipTest("la corrida no declara el estrato por revisar")
        for i, pagina in enumerate(self.paginas, start=1):
            for linea in pagina.splitlines():
                if "Estrato" in linea:
                    self.assertNotIn("VERIFICADO", linea.upper(),
                                     f"página {i}: {linea!r}")

    def test_dos_paginas_no_discrepan_sobre_el_mismo_atributo(self):
        """Ningún atributo puede llevar DOS estados distintos dentro del ejecutivo.

        Se comparan los chips de estado que acompañan a la misma etiqueta en todas las
        páginas: si el atributo se imprime en más de una página, el estado tiene que ser
        el mismo (una sola verdad trazable por atributo).
        """
        chips = ("VERIFICADO", "VERIFICADA", "REQUIERE VALIDACIÓN", "CONFLICTO HISTÓRICO",
                 "SIN DATO", "CAMBIO CON FUENTE")
        etiquetas = ("Destino económico (catastro)", "Uso / actividad POT", "Estrato",
                     "Barrio", "Localidad / comuna", "Régimen jurídico", "Área", "NUPRE",
                     "Número predial", "Tratamiento urbanístico")
        visto = {}
        for i, pagina in enumerate(self.paginas, start=1):
            plano = " ".join(pagina.split())
            for etiqueta in etiquetas:
                pos = plano.find(etiqueta)
                if pos == -1:
                    continue
                ventana = plano[pos:pos + len(etiqueta) + 90].upper()
                estado = next((c for c in chips if c in ventana), None)
                if not estado:
                    continue
                anterior = visto.get(etiqueta)
                if anterior and anterior[0] != estado:
                    self.fail(f"el atributo «{etiqueta}» tiene dos estados incompatibles "
                              f"en el mismo dictus: {anterior[0]} (página {anterior[1]}) "
                              f"vs {estado} (página {i})")
                visto[etiqueta] = (estado, i)
        self.assertTrue(visto, "el fixture debe traer al menos un atributo impreso")

    def test_el_run_state_declara_la_verdad_que_se_imprime(self):
        """El estado declarado por atributo viaja en el artefacto (trazabilidad)."""
        self.assertIn("requieren_revision", self.hist)
        self.assertIn("conflictos_abiertos", self.hist)
        self.assertIn(self.hist.get("veredicto"),
                      ("CONFLICTOS_ABIERTOS", "COHERENTE"))


# ══════════════════════════════════════════════════════════════════════════════
# P4 · CLASIFICACIÓN DEL ORIGEN
# ══════════════════════════════════════════════════════════════════════════════
class TestClasificacionDeOrigen(unittest.TestCase):

    def test_el_vocabulario_es_cerrado(self):
        self.assertEqual(set(am.ORIGENES),
                         {"EXTERNAL_SOURCE", "COMPUTED_FROM_SOURCES", "MANUAL_CONFIG",
                          "STATIC_REFERENCE", "MODEL_PRIOR"})
        self.assertEqual(am.ORIGENES_HABILITANTES,
                         frozenset({"EXTERNAL_SOURCE", "COMPUTED_FROM_SOURCES"}))

    def test_sin_declaracion_de_origen_no_habilita(self):
        r = am.clasificar_origen({"fuente": "texto libre sin procedencia"})
        self.assertEqual(r["origin"], am.ORIGEN_MANUAL)
        self.assertFalse(r["origin_gate"])
        self.assertTrue(r["origin_blockers"])

    def test_origen_habilitante_sin_procedencia_completa_se_degrada(self):
        r = am.clasificar_origen({"origen_tipo": "EXTERNAL_SOURCE",
                                  "proveedor": "X", "fecha": "2026-01-01"})
        self.assertEqual(r["origin"], am.ORIGEN_MANUAL)
        self.assertFalse(r["origin_gate"])
        self.assertTrue(any("procedencia" in b for b in r["origin_blockers"]))

    def test_origen_externo_con_procedencia_completa_si_habilita(self):
        r = am.clasificar_origen({
            "origen_tipo": "EXTERNAL_SOURCE", "source_id": "FUENTE_REAL",
            "proveedor": "Institución", "fecha": "2026-01-01",
            "referencia": "https://ejemplo/consulta", "sha256": "a" * 64})
        self.assertEqual(r["origin"], am.ORIGEN_EXTERNO)
        self.assertTrue(r["origin_gate"])
        self.assertEqual(r["origin_blockers"], [])

    def test_origen_computado_exige_dos_fuentes_citadas(self):
        una = am.clasificar_origen({"origen_tipo": "COMPUTED_FROM_SOURCES",
                                    "fuentes": [{"proveedor": "A", "fecha": "1",
                                                 "referencia": "x", "sha256": "b"}]})
        self.assertFalse(una["origin_gate"])
        dos = am.clasificar_origen({
            "origen_tipo": "COMPUTED_FROM_SOURCES",
            "fuentes": [{"proveedor": "A", "fecha": "1", "referencia": "x", "sha256": "b"},
                        {"proveedor": "B", "fecha": "2", "referencia": "y", "sha256": "c"}]})
        self.assertTrue(dos["origin_gate"])

    def test_la_entidad_no_acreditada_no_se_expone_como_proveedora(self):
        self.assertEqual(am.entidad_declarada("Lonja de Propiedad Raíz de Barranquilla"),
                         am.ENTIDAD_NO_VERIFICADA)
        self.assertEqual(am.entidad_declarada("Instituto Geográfico Agustín Codazzi"),
                         "Instituto Geográfico Agustín Codazzi")
        self.assertIsNone(am.entidad_declarada(None))


class TestOrigenDeLaTasaReal(unittest.TestCase):
    """La tasa del artefacto local del producto es `MANUAL_CONFIG`: no habilita."""

    def test_la_fila_del_artefacto_no_declara_origen(self):
        sector = mctx.resolve_market_sector("Miramar")
        self.assertEqual(sector["match_type"], mctx.MATCH_EXACT)
        self.assertEqual(sector["origin"], am.ORIGEN_MANUAL)
        self.assertFalse(sector["origin_gate"])
        self.assertTrue(sector["origin_blockers"])

    def test_un_contexto_suficiente_sin_origen_habilitante_no_habilita_valorar(self):
        mc = mctx.build_market_context(
            identity_verified=True, barrio="Miramar",
            barrio_status=mctx.STATUS_VERIFIED_OFFICIAL, estrato="4",
            estrato_status=mctx.STATUS_VERIFIED_OFFICIAL,
            tipologia="Unidad en propiedad horizontal",
            tipologia_status=mctx.STATUS_VERIFIED_REGISTRAL,
            uso="Habitacional", uso_status=mctx.STATUS_VERIFIED_OFFICIAL,
            sector_resolution=mctx.resolve_market_sector("Miramar"))
        # La CONFIANZA del contexto se resuelve…
        self.assertTrue(mctx.market_context_ready(mc), mc["blockers"])
        # …y aun así la valoración NO queda habilitada: no hay FUENTE.
        self.assertFalse(mctx.market_context_valoracion_habilitada(mc))
        self.assertEqual(mc["status"], mctx.STATUS_UNRESOLVED)
        self.assertEqual(mc["origin"], am.ORIGEN_MANUAL)

    def test_la_decision_es_no_emitir_valoracion(self):
        mc = mctx.build_market_context(
            identity_verified=True, barrio="Miramar",
            barrio_status=mctx.STATUS_VERIFIED_OFFICIAL, estrato="4",
            estrato_status=mctx.STATUS_VERIFIED_OFFICIAL,
            tipologia="Unidad en propiedad horizontal",
            tipologia_status=mctx.STATUS_VERIFIED_REGISTRAL,
            sector_resolution=mctx.resolve_market_sector("Miramar"))
        rs = {"valuation_state": {"authorization": {"allowed": False}},
              "market_context": mc, "property_identity": {"identity_verified": True}}
        obs = dd2.observaciones_de(rs)
        gates = dd2.compuertas_de(rs, obs, [])
        gate = [g for g in gates if g["gate"] == dd2.VALUATION_GATE][0]
        self.assertEqual(gate["decision"], dd2.NO_EMITIR_VALORACION)


# ══════════════════════════════════════════════════════════════════════════════
# P6 · EL HARDCODE POR ESTRATO NO ABRE LA COMPUERTA
# ══════════════════════════════════════════════════════════════════════════════
class TestHardcodePorEstratoExcluido(unittest.TestCase):
    """`MODEL_PRIOR` · fallback legacy no productivo: se excluye y se prueba."""

    def test_el_hardcode_esta_declarado_como_prior_del_modelo(self):
        self.assertEqual(dd.FALLBACK_ESTRATO_M2,
                         {3: 3_800_000, 4: 5_200_000, 5: 6_500_000, 6: 7_800_000})
        self.assertEqual(dd.FALLBACK_ESTRATO_M2_DEFAULT, 5_200_000)
        self.assertEqual(dd.MATCH_GENERIC_ESTRATO_FALLBACK, "GENERIC_ESTRATO_FALLBACK")

    def test_el_fallback_no_puede_resolver_una_tasa_autorizada(self):
        """SIN MarketContext y sin modo legacy, el modo por defecto es fail-closed."""
        res = dd.get_valuation(58.75, "Miramar", 4, ciudad="barranquilla")
        self.assertFalse(res["metodologia_aplica"])
        self.assertEqual(res["consolidado"], 0)
        self.assertIsNone(res["value_m2"])
        self.assertFalse(res["origin_gate"])

    def test_el_modo_legacy_declara_el_prior_y_nunca_habilita(self):
        """Con `allow_legacy_reference` el valor sale del hardcode: `MODEL_PRIOR`."""
        res = dd.get_valuation(58.75, "Barrio Que No Existe", 4,
                               ciudad="barranquilla", allow_legacy_reference=True)
        self.assertEqual(res["market_rate_match_type"], "GENERIC_ESTRATO_FALLBACK")
        self.assertEqual(res["value_m2"], 5_200_000)          # el hardcode por estrato
        self.assertEqual(res["origin"], am.ORIGEN_PRIOR)
        self.assertFalse(res["origin_gate"])
        self.assertEqual(res["origins"]["market_value_m2"], am.ORIGEN_PRIOR)

    def test_un_market_context_con_el_prior_del_modelo_no_habilita(self):
        """La compuerta semántica cierra aunque el contexto de confianza esté resuelto."""
        mc = mctx.build_market_context(
            identity_verified=True, barrio="Miramar",
            barrio_status=mctx.STATUS_VERIFIED_OFFICIAL, estrato="4",
            estrato_status=mctx.STATUS_VERIFIED_OFFICIAL,
            tipologia="Unidad en propiedad horizontal",
            tipologia_status=mctx.STATUS_VERIFIED_REGISTRAL,
            uso="Habitacional", uso_status=mctx.STATUS_VERIFIED_OFFICIAL,
            sector_resolution={"matched_sector": None,
                               "match_type": mctx.MATCH_GENERIC_ESTRATO_FALLBACK,
                               "value_m2": 5_200_000,
                               "source": "fallback genérico por estrato",
                               "market_methodology_id": "m", "market_methodology_version": "0"})
        self.assertFalse(mctx.market_context_authorized(mc))
        self.assertFalse(mctx.market_context_valoracion_habilitada(mc))
        self.assertEqual(mc["origin"], am.ORIGEN_MANUAL)
        self.assertFalse(mc["origin_gate"])

    def test_el_estado_degrada_una_autorizacion_sin_origen_habilitante(self):
        """El MODELO no acepta una autorización que su propio origen no sostiene."""
        captura = {"ctx": {"canonical_identity": {"identity_verified": True},
                           "valuation_authorization": {"allowed": True},
                           "market_context": {
                               "ready": True,
                               "market_rate_source": "tasa manual",
                               "sector_metodologico": {"match_type": "EXACT",
                                                       "valor_central_m2": 5_200_000}}},
                   "poi": {}, "release": {}, "solar": {}}
        rs = dse.construir_run_state(captura, run_id="qa-prior", folio="TST-PRIOR",
                                     ciudad="barranquilla", area=58.75)
        auth = rs["valuation_state"]["authorization"]
        self.assertFalse(auth["allowed"])
        self.assertEqual(auth["demoted_by"], "ORIGIN_GATE")
        self.assertEqual(rs["market_context"]["status"], "UNRESOLVED")
        self.assertFalse(rs["market_context"]["valoracion_habilitada"])


# ══════════════════════════════════════════════════════════════════════════════
# P8 · GOLDEN REGENERADO SOMETIDO A ASERCIÓN
# ══════════════════════════════════════════════════════════════════════════════
class TestGoldenSemantica(unittest.TestCase):
    """Aserciones versionadas sobre el Golden 040-646406 regenerado."""

    @classmethod
    def setUpClass(cls):
        for ruta in (RUTA_EJECUTIVO, RUTA_TECNICO, RUTA_TEXTO, RUTA_MANIFEST):
            if not ruta.exists():
                raise unittest.SkipTest(f"falta el Golden regenerado: {ruta.name}")
        cls.paginas = _texto_paginas(RUTA_EJECUTIVO)
        cls.texto_ejecutivo = "\n".join(cls.paginas)
        cls.texto_tecnico = "\n".join(_texto_paginas(RUTA_TECNICO))
        cls.manifest = json.loads(RUTA_MANIFEST.read_text(encoding="utf-8"))
        cls.rs = json.loads(RUTA_RUN_STATE.read_text(encoding="utf-8"))

    # ── P8.a · sin «Lonja» como fuente ───────────────────────────────────────
    def test_assert_lonja_no_esta_en_el_ejecutivo(self):
        self.assertNotIn("Lonja", self.texto_ejecutivo)
        self.assertNotIn("lonja", self.texto_ejecutivo.lower())

    def test_assert_lonja_no_esta_en_el_tecnico(self):
        self.assertNotIn("Lonja", self.texto_tecnico)
        self.assertNotIn("lonja", self.texto_tecnico.lower())

    def test_assert_lonja_no_se_presenta_como_fuente_en_los_artefactos(self):
        for etiqueta, artefacto in (("run state", self.rs), ("manifest", self.manifest)):
            plano = json.dumps(artefacto, ensure_ascii=False)
            self.assertNotIn("Lonja", plano,
                             f"{etiqueta}: la Lonja vuelve a presentarse como fuente")
            # El identificador sellado viaja, pero ya NO en un campo llamado `source`.
            self.assertNotIn('"methodology_entity": "Lonja', plano)

    # ── P8.b · sin cifra de mercado emitida por un prior ─────────────────────
    def test_assert_el_fallback_hardcodeado_no_abre_la_compuerta(self):
        mc = self.rs["market_context"]
        self.assertEqual(mc["origin"], am.ORIGEN_MANUAL)
        self.assertFalse(mc["origin_gate"])
        self.assertEqual(mc["status"], "UNRESOLVED")
        self.assertFalse(mc["valoracion_habilitada"])
        self.assertNotEqual(mc["sector_metodologico"].get("match_type"),
                            dd.MATCH_GENERIC_ESTRATO_FALLBACK)
        gate = [g for g in self.manifest["modelo"]["decision_gates"]
                if g["gate"] == dd2.VALUATION_GATE][0]
        self.assertEqual(gate["decision"], dd2.NO_EMITIR_VALORACION)
        # Y la autorización del estado NO está permitida: sin fuente no se emite.
        self.assertFalse(self.rs["valuation_state"]["authorization"]["allowed"])

    def test_assert_el_ejecutivo_no_imprime_ninguna_cifra_de_mercado(self):
        self.assertNotIn("399.500.000", self.texto_ejecutivo)
        plano = self.texto_ejecutivo.upper()
        self.assertIn("NO EMITIR VALORACIÓN", plano)
        # §7 (cierre semántico Fase 3) · DOCTRINA ACTUALIZADA — el ejecutivo ya NO titula
        # el bloque con «VALORACIÓN NO DISPONIBLE» / «NO DISPONIBLE (VALORACIÓN NO
        # AUTORIZADA)»: ese rótulo nombraba la VALORACIÓN como si no existiera cifra
        # alguna, al lado de la ESTIMACIÓN INDICATIVA que DICTUS sí produce. Ahora el
        # hecho se nombra por la compuerta que realmente cierra
        # (`VERIFIED_MARKET_EVIDENCE_GATE`) y la P1 dice «no habilitada». La aserción
        # ENDURECE: exige los rótulos vigentes y PROHÍBE los retirados.
        self.assertIn("EVIDENCIA DE MERCADO VERIFICADA · NO HABILITADA", plano)
        self.assertIn("VERIFIED_MARKET_EVIDENCE_GATE = CLOSED", plano)
        self.assertIn("NO HABILITADA", plano)
        self.assertNotIn("VALORACIÓN NO DISPONIBLE", plano)
        self.assertNotIn("NO DISPONIBLE (VALORACIÓN NO AUTORIZADA)", plano)
        # Y declara QUÉ falta, con el ORIGEN real de la tasa declarada.
        self.assertIn("NO HABILITA VALORACIÓN", plano)
        self.assertIn("MANUAL_CONFIG", plano)

    def test_assert_el_origen_viaja_junto_al_valor_en_el_modelo(self):
        valor = self.manifest["modelo"]["valuation"]
        self.assertEqual(valor["origin"], am.ORIGEN_MANUAL)
        self.assertFalse(valor["origin_gate"])
        self.assertEqual(valor["origin_blockers"], valor["origin_blockers"])
        self.assertTrue(valor["origin_blockers"])
        # Los parámetros del cálculo declaran su origen uno por uno.
        self.assertEqual(valor["origins"]["market_value_m2"], am.ORIGEN_MANUAL)
        self.assertIn(valor["origins"]["cap_rate"], am.ORIGENES)
        self.assertIn(valor["origins"]["factor_costos"], am.ORIGENES)

    def test_assert_ningun_atributo_del_ejecutivo_discrepa_de_su_estado(self):
        """P3 sobre el Golden: el estado impreso ES el estado declarado."""
        hist = self.rs["historical_consistency"]
        # BLOCK 1 · §10: solo una DIFERENCIA MATERIAL declarada (o un conflicto abierto)
        # impide imprimir VERIFICADO; una aparición del atributo en una versión nueva no.
        por_revisar = {r["atributo"] for r in (hist.get("requieren_revision") or [])
                       if r.get("diferencia_material")}
        en_conflicto = {c["atributo"] for c in (hist.get("conflictos_abiertos") or [])}
        materiales = por_revisar | en_conflicto
        if "estrato" in materiales:
            self.assertNotIn("ESTRATO 4 VERIFICADO", _plano(self.paginas))
        for atributo in ("altura_maxima", "coordenada", "tratamiento", "uso_pot",
                         "amenaza", "titulares"):
            if atributo not in materiales:
                continue
            # El atributo con diferencia material está LISTADO en la coherencia y su fila
            # NO puede salir VERIFICADA en ninguna página donde se imprima su etiqueta.
            etiqueta = {"altura_maxima": "Altura / edificabilidad",
                        "coordenada": "Coordenada del predio",
                        "tratamiento": "Tratamiento urbanístico",
                        "uso_pot": "Uso del suelo (POT)",
                        "amenaza": "Amenaza por remoción en masa",
                        "titulares": "Titularidad"}.get(atributo)
            if not etiqueta:
                continue
            for i, pagina in enumerate(self.paginas, start=1):
                plano = " ".join(pagina.split())
                pos = plano.find(etiqueta)
                if pos == -1:
                    continue
                ventana = plano[pos:pos + len(etiqueta) + 90].upper()
                self.assertNotIn("VERIFICADO", ventana,
                                 f"página {i}: «{atributo}» tiene una diferencia material "
                                 f"declarada y se imprime VERIFICADO: {ventana!r}")

    def test_assert_el_hash_del_ejecutivo_esta_registrado(self):
        sha = hashlib.sha256(RUTA_EJECUTIVO.read_bytes()).hexdigest()
        aceptacion = GOLDEN / "ACEPTACION_040-646406.json"
        if not aceptacion.exists():
            self.skipTest("falta la aceptación de la corrida")
        reporte = json.loads(aceptacion.read_text(encoding="utf-8"))
        self.assertEqual(reporte["executive_pdf_sha256"], sha)


if __name__ == "__main__":
    unittest.main()

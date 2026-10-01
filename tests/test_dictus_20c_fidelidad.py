# -*- coding: utf-8 -*-
"""DICTUS 2.0C — FIDELIDAD MATERIAL Y COMPOSICIÓN DEL EJECUTIVO.

Verifica, sobre el PDF FÍSICO y sobre el estado de la corrida, las garantías que 2.0C
introduce:

  1. **Sin pérdidas materiales silenciosas** (§24): todo hecho que el estado/modelo
     conoce y es material se imprime, o el documento declara por qué no.
  2. **POI no degradado** (§4/§6): hasta 3 lugares por categoría con distancia y tiempo
     a pie; nunca «0 detectados» si la consulta no se completó.
  3. **Activos reales** (§7/§20): mapa y sombras de la MISMA corrida, o se declara.
  4. **Screening sin contradicción** (§14/§15): resultado de match e integridad de
     evidencia separados; el texto de seguro dice lo mismo que el sello.
  5. **Acciones jurídicas por tipo** (§12) y **modalidad de adquisición** del acto
     inscrito (§13).
  6. **POT con actual + histórico + coherencia + fuente** (§16/§17).
  7. **Composición verificable** (§25): cada componente registra su bounding box y
     ninguna caja intersecta otra; ninguna página desborda.
"""
import json
import hashlib
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))

import dictus_ejecutivo as de          # noqa: E402
import dictus_estado as dse            # noqa: E402
import dictus_manifiesto as dm         # noqa: E402
import dictus_secciones as sec         # noqa: E402

FOLIO = "TST-000001"
SALIDA = ROOT / "tmp_dictus_2c"
GOLDEN = ROOT / "docs" / "forensics" / "040-646406" / "dictus_2c"


# ── procedencia SINTÉTICA COMPLETA de la tasa del fixture de QA ───────────────
def procedencia_sintetica(referencia: str) -> dict:
    """Procedencia que la COMPUERTA SEMÁNTICA exige para habilitar la valoración.

    Un fixture que quiera probar la composición del ejecutivo CON una cifra tiene que
    declarar el origen de esa cifra, y declararlo con procedencia completa (id de
    fuente, proveedor, fecha, referencia y huella). La clave `synthetic: True` deja la
    naturaleza QA DENTRO del artefacto: nadie puede confundirla con una fuente real, y
    la corrida REAL del producto no la declara (por eso su compuerta queda CERRADA).
    """
    declaracion = f"QA_FIXTURE_MARKET::{referencia}"
    return {
        "origen_tipo": "EXTERNAL_SOURCE",
        "source_id": "QA_FIXTURE_MARKET",
        "proveedor": "Fixture sintético de QA (no es una institución real)",
        "fecha": "2026-01-15",
        "referencia": referencia,
        "sha256": hashlib.sha256(declaracion.encode("utf-8")).hexdigest(),
        "synthetic": True,
    }


# ── corrida sintética (misma FORMA que la corrida real) ───────────────────────
def _captura(*, cadena="SEALED", assets=None):
    ctx = {
        "canonical_identity": {
            "folio": FOLIO, "nupre": "AFT0000TEST", "codigo_catastral": "0000000000000",
            "direccion_raw": "CALLE 1 # 2 - 3 APARTAMENTO 101 TORRE 1",
            "unidad": "APARTAMENTO 101 TORRE 1", "torre": "1", "apartamento": "101",
            "estado": "MATCH_BY_NUPRE", "resolution_status": "EXACT",
            "resolution_method": "nupre", "identity_verified": True,
        },
        "predio_real": {
            "predio": {"destino_economico": "Habitacional"},
            "entorno": {"barrio": "BARRIO DE PRUEBA", "estrato": "3", "disponible": True,
                        "tratamiento": "Consolidacion", "tipo_tratamiento": "Nivel 2",
                        "altura_maxima": "11",
                        "amenaza_remocion_masa": {"nivel": "Media", "intersecta": True}},
            "condicion": {"condicion_juridica": "Propiedad Horizontal"},
            "disponible": True,
        },
        "administrative_context": {"barrio": "BARRIO DE PRUEBA", "comuna": "01",
                                  "estrato": "3"},
        "analysis": {
            "folio": FOLIO, "titulares": "TITULAR DE PRUEBA CC# 1000000000",
            "circulo_registral": "001 - PRUEBA",
            "anotaciones": [
                ["006", "01-01-2025", "COMPRAVENTA", "VENDEDOR -> TITULAR DE PRUEBA",
                 "VIGENTE"],
                ["007", "01-01-2026", "GRAVAMEN: Hipoteca",
                 "TITULAR DE PRUEBA -> BANCO DE PRUEBA S.A.", "VIGENTE"],
                ["008", "01-01-2026", "LIMITACION: Afectacion Vivienda",
                 "TITULAR DE PRUEBA", "VIGENTE"]],
            "anotaciones_detalle": [
                {"num": "006", "fecha": "01-01-2025", "tipo": "COMPRAVENTA",
                 "partes": "VENDEDOR -> TITULAR DE PRUEBA", "estado": "VIGENTE",
                 "texto": "Doc: ESCRITURA 100 DEL 01-01-2025 NOTARIA PRIMERA"},
                {"num": "007", "fecha": "01-01-2026", "tipo": "GRAVAMEN: Hipoteca",
                 "partes": "TITULAR DE PRUEBA -> BANCO", "estado": "VIGENTE",
                 "texto": "GRAVAMEN: hipoteca"},
                {"num": "008", "fecha": "01-01-2026", "tipo": "LIMITACION: Afectacion Vivienda",
                 "partes": "TITULAR DE PRUEBA", "estado": "VIGENTE",
                 "texto": "LIMITACION al dominio"},
            ],
            "texto_ctl": "certificado sintético",
        },
        "hallazgos": [
            ("ALTO", None, None, "H-01 | Hipoteca vigente a favor del acreedor",
             "CTL", "El folio declara una hipoteca abierta.",
             "Gestionar el saldo con el acreedor y tramitar la cancelación ante la ORIP."),
            ("MEDIO", None, None, "H-02 | Afectacion/Limitacion Vigente (Anot. 008)",
             "CTL", "El folio declara una limitación.",
             "Tramitar el levantamiento de la limitación con los titulares ante notaría."),
            ("MEDIO", None, None, "H-GEO | Afectación por Amenaza Detectada",
             "POT", "El predio intersecta la capa de amenaza.",
             "Verificación puntual por profesional competente."),
        ],
        "titulux": {"screening_summary": {
            "status": "SCREENING_COMPLETE", "coverage_status": "COVERAGE_COMPLETE",
            "subjects_declared": 2, "subjects_screened": 2,
            "subjects": [
                {"subject_id": "titular-1", "canonical_name": "TITULAR DE PRUEBA",
                 "person_type": "NATURAL_PERSON", "document_type": "cc",
                 "document_number": "1000000000", "roles": ["TITULAR_ACTUAL"]},
                {"subject_id": "acreedor-2", "canonical_name": "BANCO DE PRUEBA S.A.",
                 "person_type": "LEGAL_ENTITY", "document_type": "nit",
                 "document_number": "900000000", "roles": ["ACREEDOR_HIPOTECARIO"]},
            ],
            "outcomes": [
                {"subject_id": "titular-1", "source_id": "UN_CONSOLIDATED", "result": "NO_MATCH"},
                {"subject_id": "titular-1", "source_id": "OFAC_SDN", "result": "NO_MATCH"},
                {"subject_id": "titular-1", "source_id": "UK_SANCTIONS_LIST", "result": "NO_MATCH"},
                {"subject_id": "acreedor-2", "source_id": "UN_CONSOLIDATED", "result": "NO_MATCH"},
                {"subject_id": "acreedor-2", "source_id": "OFAC_SDN", "result": "NO_MATCH"},
                {"subject_id": "acreedor-2", "source_id": "UK_SANCTIONS_LIST", "result": "NO_MATCH"},
            ],
            "sources": ["UN_CONSOLIDATED", "OFAC_SDN", "UK_SANCTIONS_LIST"],
            "matched_subjects": [],
            "evidence_created_count": 6, "evidence_expected_count": 6,
            "evidence_chain_status": cadena,
        }},
        "res_avaluo": {"value_m2": 6000000, "consolidado": 352500000,
                       "banda_baja": 330000000, "banda_alta": 375000000,
                       "metodologia_aplica": True},
        "valuation_authorization": {"allowed": True, "identity_authorized": True,
                                    "market_context_authorized": True},
        "clasificacion": {
            "juridical_regime": {"value": "PROPIEDAD_HORIZONTAL", "status": "VERIFIED_REGISTRAL"},
            "economic_use": {"value": "HABITACIONAL", "status": "VERIFIED_REGISTRAL"},
            "physical_typology": {"value": "UNIDAD_EN_PROPIEDAD_HORIZONTAL",
                                  "status": "VERIFIED_REGISTRAL"},
        },
        "market_context": {
            "ready": True,
            # La tasa del fixture declara su ORIGEN con procedencia COMPLETA: es lo
            # único que habilita la valoración (compuerta semántica P4/P6/P7).
            "sector_metodologico": {
                "matched_sector": "SECTOR DE PRUEBA",
                "match_type": "EXACT",
                **procedencia_sintetica("tests/test_dictus_20c_fidelidad.py::_captura"),
            },
            "market_methodology_id": "lonja_prueba",
            "market_methodology_version": "0.9-test",
            "market_rate_source": "Tasa de prueba verificada",
            "uso": {"value": "Habitacional", "status": "VERIFIED_OFFICIAL"},
            "coordinates": {"lat": 11.0055, "lon": -74.8375},
            "coordinate_source": "OFFICIAL_PREDIO", "coordinate_source_verified": True,
            "coordinate_scope": ("geometría oficial del PREDIO (lote/edificio): NO acredita "
                                 "la posición del apartamento dentro de la edificación"),
            "canonical_binding_status": "VERIFIED",
            "canonical_binding_fields": ["nupre", "numero_predial"],
            "urban_source_summary": {"source_mode": "MIXED", "campos": {
                "tratamiento": {"value": "Consolidacion", "modo": "LIVE_OFFICIAL"},
                "altura_maxima": {"value": 11, "modo": "PACKAGED_REFERENCE"}}},
            "blockers": [],
        },
        "geo_eval": {"amenaza_remocion_masa": {"nivel": "Media", "intersecta": True},
                     "areas_en_riesgo": {"nivel": "Medio", "intersecta": True}},
        "assets_dir": str(assets) if assets else None,
    }
    poi = {
        "queried_at": "2026-01-15T10:00:00+00:00",
        "sources_attempted": ["OSM_OVERPASS"], "sources_succeeded": ["OSM_OVERPASS"],
        "category_status": {"Salud": "AVAILABLE", "Educacion": "AVAILABLE",
                            "Comercio": "AVAILABLE", "Recreacion": "SOURCE_UNAVAILABLE"},
        "items": {
            "Salud": [{"name": f"CENTRO MEDICO {i}", "type": "Salud (Clinic)",
                       "distance": 400.0 + i * 100, "source": "OSM_OVERPASS"}
                      for i in range(1, 4)],
            "Educacion": [{"name": f"COLEGIO {i}", "type": "Educacion (School)",
                           "distance": 260.0 + i * 90, "source": "OSM_OVERPASS"}
                          for i in range(1, 4)],
            "Comercio": [{"name": f"SUPERMERCADO {i}", "type": "Comercio (Supermarket)",
                          "distance": 180.0 + i * 70, "source": "OSM_OVERPASS"}
                         for i in range(1, 4)],
            "Recreacion": [],
        },
    }
    return {
        "ctx": ctx, "poi": poi,
        "receipts": {"generated_at": "2026-01-15T10:05:00+00:00"},
        "release": {"release_status": "VALID_FOR_RELEASE", "policy": "MARK"},
        "solar": {"momentos": [
            {"hora": "09:00 COT", "azimut": "102.33°", "elevacion": "45.98°",
             "estado": "Sol Directo"},
            {"hora": "12:00 COT", "azimut": "191.14°", "elevacion": "78.25°",
             "estado": "Sol Directo"},
            {"hora": "15:00 COT", "azimut": "259.25°", "elevacion": "41.62°",
             "estado": "Sombra (Orientación)"},
        ]},
    }


def _render(nombre="qa", *, cadena="SEALED", con_assets=True):
    """Construye estado → modelo → secciones → PDF y devuelve (ruta, piezas)."""
    salida = SALIDA / nombre
    salida.mkdir(parents=True, exist_ok=True)
    assets = salida / "assets"
    assets.mkdir(exist_ok=True)
    if con_assets:
        # Activos REALES de la corrida (PNG mínimo válido, generado por PIL/reportlab).
        from reportlab.pdfgen import canvas as _c
        from PIL import Image
        Image.new("RGB", (320, 200), (230, 226, 216)).save(assets / "poi_map.png")
        Image.new("RGB", (320, 200), (200, 205, 215)).save(assets / "sombra_9am.png")
        Image.new("RGB", (320, 200), (190, 200, 215)).save(assets / "sombra_3pm.png")
    captura = _captura(cadena=cadena, assets=assets if con_assets else None)
    rs = dse.construir_run_state(captura, run_id="qa-2c", folio=FOLIO,
                                 ciudad="barranquilla", area=58.75,
                                 tipo_unidad="URBANO")
    hist = {"version": "dictus-historical-consistency/1.0.0", "versiones_comparadas": 3,
            "conflictos_abiertos": [
                {"atributo": "altura_maxima", "valores": ["8", "11"],
                 "detalle": "El expediente produjo resultados distintos."},
                {"atributo": "tratamiento", "valores": ["Consolidacion", "Desarrollo"],
                 "detalle": "El expediente produjo resultados distintos."},
                {"atributo": "uso_pot", "valores": ["ACTIVIDAD CENTRAL", "ACTIVIDAD URBANA"],
                 "detalle": "El expediente produjo resultados distintos."},
                {"atributo": "coordenada", "valores": ["10.98, -74.81", "11.00, -74.83"],
                 "detalle": "El expediente produjo resultados distintos."},
                {"atributo": "titulares", "valores": ["2 titulares", "1 titular"],
                 "detalle": "El expediente produjo resultados distintos."},
                {"atributo": "amenaza", "valores": ["BAJA", "MEDIA"],
                 "detalle": "El expediente produjo resultados distintos."},
            ]}
    rs["historical_consistency"] = hist
    dse.agregar_findings_de_coherencia(rs, hist)
    modelo = dm.construir_documento_maestro(rs, historial=hist, folio=FOLIO)
    secciones = sec.desde_estado(rs, modelo, hist)
    pdf = salida / f"DICTUS_EJECUTIVO_{FOLIO}.pdf"
    de.render(modelo, secciones, pdf)
    from pypdf import PdfReader
    paginas = [(p.extract_text() or "") for p in PdfReader(str(pdf)).pages]
    return pdf, rs, modelo, secciones, paginas


class TestSinPerdidaMaterial(unittest.TestCase):
    """§24: ningún hecho material del estado/modelo se pierde en silencio."""

    @classmethod
    def setUpClass(cls):
        cls.pdf, cls.rs, cls.modelo, cls.secciones, cls.paginas = _render("fidelidad")
        cls.texto = "\n".join(cls.paginas)

    def _plano(self) -> str:
        return " ".join(self.texto.upper().split())

    def _imprime(self, aguja) -> bool:
        # El texto extraído parte las líneas: la comparación ignora los saltos.
        plano = " ".join(self.texto.upper().split())
        return " ".join(str(aguja).upper().split()) in plano

    def test_hechos_materiales_del_estado_estan_en_el_pdf(self):
        """La regresión que esta ronda existe para bloquear."""
        pi = self.rs["property_identity"]
        ts = self.rs["title_state"]
        urb = self.rs["urban_context"]
        mc = self.rs["market_context"]
        val = self.rs["valuation_state"]
        esenciales = {
            "dirección completa": "CALLE 1 # 2 - 3",
            "unidad/torre": "APARTAMENTO 101",
            "matrícula": pi["folio"],
            "NUPRE": pi["nupre"],
            "predial": pi["codigo_catastral"],
            "barrio": urb["barrio"],
            "estrato": str(urb["estrato"]),
            "área": "58.75",
            "régimen": urb["condicion_juridica"],
            "destino catastral": urb["destino_economico"],
            "tratamiento (valor actual)": urb["tratamiento"],
            "altura (valor actual)": urb["altura_maxima"],
            "titulares": "TITULAR DE PRUEBA",
            "forma de adquisición": ts["modalidad_adquisicion"],
            "acreedor/gravamen": "Hipoteca",
            "limitación": "Afectacion Vivienda",
            "contrapartes": "BANCO DE PRUEBA",
            "listas": "UK Sanctions List",
            "POI": "SUPERMERCADO 2",
            "distancia POI": "500 M",
            "tiempo a pie": "MIN A PIE",
            "asoleamiento": "09:00 COT",
            "valor": "352.500.000",
            "rango": "330.000.000",
            "valor/m²": "6.000.000",
            "sector de mercado": mc["sector_metodologico"]["matched_sector"],
            # DOCTRINA "la Lonja no es fuente" (decisión de producto): el IDENTIFICADOR
            # sellado (`market_methodology_id`) sigue viajando en el plano máquina
            # (modelo, run state, manifest) y NO se renombra, pero el PDF ya no lo
            # imprime como si fuera el nombre de una fuente: imprime la etiqueta
            # verdadera de la metodología declarada por la corrida.
            "metodología (etiqueta verdadera)":
                "Comparación de mercado (parámetros declarados por la corrida)",
            "tasa y fuente": mc["market_rate_source"],
            "coordenada oficial": "11.00550",
            "binding": "VERIFICADA",
        }
        faltan = {k: v for k, v in esenciales.items() if not self._imprime(str(v))}
        self.assertEqual(faltan, {}, f"hechos materiales no impresos: {faltan}")
        # El puente entre los dos planos: el id sigue en el plano máquina…
        self.assertEqual(mc["market_methodology_id"], "lonja_prueba")
        # …y NO se imprime en el ejecutivo como atribución de fuente.
        self.assertNotIn(str(mc["market_methodology_id"]).upper(), self._plano())
        self.assertNotIn("LONJA", self._plano())
        self.assertEqual(val["consolidado"], 352500000)

    def test_lo_que_no_existe_se_declara_no_se_inventa(self):
        # Recreación: la fuente no completó la consulta ⇒ NO «0 detectados».
        p5 = self.paginas[4]
        self.assertIn("Recreación", p5)
        self.assertIn("NO EVALUADO", p5.upper())
        self.assertNotIn("Recreación\n0\ndetectados", p5)
        # Mapa satelital: no aportado en la corrida sintética.
        self.assertTrue("satellite_map" in json.dumps(self.secciones.get("visual") or {}))
        self.assertNotIn("VISTA SATELITAL", p5.upper())

    def test_poi_tres_por_categoria_con_tiempo(self):
        p5 = self.paginas[4]
        for i in (1, 2, 3):
            self.assertIn(f"CENTRO MEDICO {i}", p5)
            self.assertIn(f"COLEGIO {i}", p5)
            self.assertIn(f"SUPERMERCADO {i}", p5)
        self.assertEqual(p5.count("min a pie"), 9,
                         "3 categorías × 3 lugares con tiempo a pie estimado")

    def test_activos_visuales_reales_de_la_corrida(self):
        p5 = self.paginas[4]
        self.assertIn("ENTORNO URBANO DEL INMUEBLE", p5)   # mapa de POI del run
        self.assertIn("SOMBRA DE LA CORRIDA · 09:00", p5)  # sombras reales del run
        self.assertIn("SOMBRA DE LA CORRIDA · 15:00", p5)
        self.assertEqual(
            self.secciones["visual"]["assets"]["shadow_09"]["status"], "AVAILABLE")

    def test_pot_actual_historico_y_coherencia(self):
        p4 = self.paginas[3]
        self.assertIn("ACTUAL: Hasta 11 pisos", p4)
        self.assertIn("HISTÓRICO: 8 / 11", p4)
        self.assertIn("CONFLICTO HISTÓRICO", p4)
        self.assertIn("empaquetada", p4)          # fuente del valor vigente
        self.assertIn("Consolidacion", p4)
        self.assertIn("fuente:", p4)

    def test_riesgos_con_estado_semantico(self):
        p4 = self.paginas[3]
        self.assertIn("Inundación: NO EVALUADO", p4)
        self.assertIn("Remoción en masa / amenaza del POT: Media", p4)

    def test_pagina1_separa_operacion_de_coherencia(self):
        p1 = self.paginas[0]
        # 2.0D: la separación se hace en el tablero de decisión por TEMA.
        self.assertIn("DECISION BOARD", p1)
        self.assertIn("TEMA", p1)
        self.assertIn("DECISIÓN DICTUS", p1)
        self.assertEqual(p1.count("H-COH"), 0,
                         "los conflictos de datos no se imprimen como hallazgos ALTO")
        self.assertIn("6 atributo(s) requieren reconciliación histórica", p1)
        self.assertIn("Detalle por atributo: página 4", p1)
        self.assertIn("AFECTA A:", p1)
        self.assertNotIn("sin actores declarados", p1.lower())

    def test_acciones_juridicas_por_tipo(self):
        p2 = self.paginas[1]
        self.assertIn("Forma de adquisición: Compraventa", p2)
        self.assertIn("Anot. 006", p2)
        # Hipoteca: gestión con el acreedor y cancelación.
        self.assertRegex(p2, r"ACCIÓN ESPECÍFICA:.*acreedor")
        # Limitación: su acción NO se resuelve con el acreedor hipotecario. El bloque de
        # decisión (2.0D) va después del detalle registral: la acción se corta ahí.
        bloque = p2.split("LIMITACION: Afectacion Vivienda")[-1]
        accion = (bloque.split("ACCIÓN ESPECÍFICA:")[1]
                  .split("DECISIÓN DICTUS · JURÍDICO")[0]
                  .split("El detalle registral")[0])
        self.assertTrue(accion.strip())
        self.assertNotIn("acreedor", accion.lower(),
                         f"la afectación no depende del acreedor: {accion[:120]}")

    def test_identidad_y_geometria_son_dos_conceptos(self):
        """(C) La P6 rotula el atributo que su estado describe, no «geometría» a secas.

        ANTES esta prueba exigía el literal «Geometría oficial: VERIFICADA». Ese rótulo
        era ambiguo: se leía como una afirmación sobre la COORDENADA (atributo
        `coordenada`, con conflicto histórico abierto y chip «NO UTILIZAR ESTE DATO COMO
        DEFINITIVO» en la P4) cuando en realidad afirmaba otra cosa: el BINDING de la
        geometría oficial contra la identidad canónica (atributo `binding_geometria`). El
        rótulo vigente nombra ese atributo y deja de fabricar la contradicción.
        """
        p6 = self.paginas[5]
        self.assertIn("Identidad registral y catastral: VERIFICADA", p6)
        self.assertIn("Binding de la geometría oficial: VERIFICADA", p6)
        self.assertNotIn("Geometría oficial: VERIFICADA", p6,
                         "el rótulo ambiguo (que se lee como el valor de la coordenada) "
                         "no debe volver")
        self.assertIn("NO acredita la posición del apartamento", p6)
        self.assertIn("Sector de mercado", p6)
        self.assertIn("Comparación de mercado", p6)
        self.assertIn("Tasa y parámetros", p6)


class TestSinContradiccionDeSellado(unittest.TestCase):
    """§14/§15: match ≠ integridad, y el texto dice lo mismo que el sello."""

    def test_sello_parcial_no_afirma_evidencia_sellada(self):
        pdf, rs, modelo, secciones, paginas = _render("sellado_parcial")
        p3 = paginas[2]
        self.assertIn("RESULTADO DE COINCIDENCIA", p3)
        self.assertIn("INTEGRIDAD DE LA EVIDENCIA", p3)
        self.assertIn("SIN COINCIDENCIAS RELEVANTES", p3)
        # El manifest sintético no está SELLADO ⇒ el seguro habla de evidencia trazable.
        sello = (modelo.get("evidence_manifest") or {}).get("estado")
        if sello != "SELLADO":
            self.assertIn("pendiente de sellado", p3)
            self.assertNotIn("evidencia sellada para el suscriptor", p3)

    def test_cadena_fallida_se_declara_sin_afirmar_sellado(self):
        pdf, rs, modelo, secciones, paginas = _render("sellado_fallido", cadena="FAILED")
        texto = "\n".join(paginas)
        self.assertIn("EVIDENCIA NO SELLADA", texto)
        self.assertNotIn("evidencia sellada para el suscriptor", texto)
        self.assertNotIn("RuntimeError", texto)
        self.assertNotIn("ARHIAX_EVIDENCE_HMAC_KEY", texto)


class TestComposicionVerificable(unittest.TestCase):
    """§11/§25: cada componente mide, dibuja y registra su caja; nada se solapa."""

    @classmethod
    def setUpClass(cls):
        cls.pdf, cls.rs, cls.modelo, cls.secciones, cls.paginas = _render("retícula")

    def test_sin_violaciones_del_motor_de_layout(self):
        self.assertEqual(list(de.VIOLACIONES), [])

    def test_cada_pagina_registra_bounding_boxes(self):
        paginas = {b["pagina"] for b in de.REGISTRO_BBOX}
        self.assertEqual(paginas, {1, 2, 3, 4, 5, 6})
        self.assertGreaterEqual(len(de.REGISTRO_BBOX), 30)
        for b in de.REGISTRO_BBOX:
            self.assertGreater(b["x1"], b["x0"])
            self.assertGreater(b["y1"], b["y0"])

    def test_ninguna_caja_intersecta_otra(self):
        self.assertEqual(de.verificar_retícula(), [])

    def test_ninguna_caja_de_texto_se_solapa_en_el_pdf(self):
        try:
            import pymupdf
        except Exception:  # noqa: BLE001
            self.skipTest("pymupdf no está instalado")
        def area(b):
            return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
        with pymupdf.open(str(self.pdf)) as doc:
            for i, pag in enumerate(doc, start=1):
                cajas = [w[:4] for w in pag.get_text("words")]
                for a in range(len(cajas)):
                    for b in range(a + 1, len(cajas)):
                        x0, y0 = max(cajas[a][0], cajas[b][0]), max(cajas[a][1], cajas[b][1])
                        x1, y1 = min(cajas[a][2], cajas[b][2]), min(cajas[a][3], cajas[b][3])
                        inter = max(0.0, x1 - x0) * max(0.0, y1 - y0)
                        if inter <= 0:
                            continue
                        menor = min(area(cajas[a]), area(cajas[b]))
                        self.assertFalse(menor > 0 and inter / menor > 0.35,
                                         f"página {i}: cajas de texto solapadas")

    def test_seis_paginas_y_titulos_aprobados(self):
        self.assertEqual(len(self.paginas), 6)
        for i, titulo in enumerate(de.TITULOS_PAGINA, start=1):
            self.assertIn(titulo, self.paginas[i - 1])


class TestModalidadDeAdquisicion(unittest.TestCase):

    def test_se_deriva_del_acto_inscrito_y_no_de_un_supuesto(self):
        actos = dse.actos_adquisicion({"anotaciones_detalle": [
            {"num": "006", "fecha": "01-01-2025", "tipo": "COMPRAVENTA",
             "texto": "Doc: ESCRITURA 100 DEL 01-01-2025 NOTARIA PRIMERA", "estado": "VIGENTE"},
            {"num": "007", "fecha": "01-01-2026", "tipo": "GRAVAMEN: Hipoteca",
             "texto": "hipoteca", "estado": "VIGENTE"}]})
        self.assertEqual(len(actos), 1)
        modalidad, evidencia = dse.modalidad_adquisicion(actos)
        self.assertEqual(modalidad, "Compraventa")
        self.assertIn("Anot. 006", evidencia)
        self.assertIn("ESCRITURA 100", evidencia)

    def test_sin_acto_no_se_afirma_modalidad(self):
        self.assertEqual(dse.modalidad_adquisicion([]), (None, None))


class TestGoldenFidelidadMaterial(unittest.TestCase):
    """Regresión sobre los artefactos del Golden (se omiten si no se ha corrido)."""

    @classmethod
    def setUpClass(cls):
        cls.matriz = GOLDEN / "MATERIAL_FACT_COMPLETENESS_MATRIX.json"
        cls.ejecutivo = GOLDEN / "DICTUS_EJECUTIVO_040-646406.pdf"

    def test_la_matriz_no_declara_perdidas_materiales(self):
        if not self.matriz.exists():
            self.skipTest("falta la matriz: ejecute scripts/dictus_auditoria_completitud_2c.py")
        datos = json.loads(self.matriz.read_text(encoding="utf-8"))
        perdidas = [p["campo"] for p in
                    json.loads((GOLDEN / "STATE_PROJECTION_LOSS_REPORT.json")
                               .read_text(encoding="utf-8"))["perdidas"]]
        self.assertEqual(perdidas, [], f"pérdidas materiales: {perdidas}")
        self.assertEqual(datos["resumen"]["perdidas"], 0)

    def test_el_ejecutivo_del_golden_tiene_seis_paginas_sin_violaciones(self):
        if not self.ejecutivo.exists():
            self.skipTest("falta el ejecutivo del Golden")
        from pypdf import PdfReader
        lector = PdfReader(str(self.ejecutivo))
        self.assertEqual(len(lector.pages), 6)


if __name__ == "__main__":
    unittest.main()

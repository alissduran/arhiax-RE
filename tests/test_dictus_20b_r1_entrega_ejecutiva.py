# -*- coding: utf-8 -*-
"""DICTUS 2.0B-R1 — LA ENTREGA: el EJECUTIVO es el documento principal.

Estas pruebas NO se conforman con que exista un `ExecutiveDocumentModel`: generan el
documento y **leen el PDF FÍSICO ya escrito** (§14). El criterio de aceptación es el
archivo, no la intención del código.

Cubren, en ese orden:
  1. El contrato del PDF entregado: ≤ 6 páginas, las seis páginas aprobadas en su
     orden, contenido mínimo por página y AUSENCIA de encabezados legacy y de fugas
     técnicas.
  2. Las aserciones duras: un PDF legacy (o con más de seis páginas) es RECHAZADO por
     la auditoría de la entrega — no se entrega un documento que no es el aprobado.
  3. La entrega del PRODUCTO: el archivo que sale por la API se llama
     `DICTUS_EJECUTIVO_<folio>.pdf` y el técnico viaja como ANEXO.
  4. La retícula: ninguna caja de texto se imprime sobre otra.

El estado de la corrida de estas pruebas es SINTÉTICO (no es el caso Golden): lo que
se verifica es el contrato del documento, no un valor de mercado.
"""
import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))

import dictus_entrega as entrega        # noqa: E402
import dictus_ejecutivo as de           # noqa: E402

FOLIO_QA = "TST-000001"
JOB_QA = "qa-test-20b-r1-0000-0000-000000000000"
SALIDA_QA = ROOT / "tmp_dictus_r1"


# ── corrida sintética (misma FORMA que la corrida real) ───────────────────────
def _captura_sintetica(*, cadena_evidencia="SEALED"):
    ctx = {
        "canonical_identity": {
            "folio": FOLIO_QA, "nupre": "AFT0000TEST", "codigo_catastral": "0000000000000000000",
            "direccion_normalizada": "CALLE 1 # 2 - 3 APARTAMENTO 101 TORRE 1",
            "unidad": "APARTAMENTO 101 TORRE 1", "torre": "1", "apartamento": "101",
            "estado": "MATCH_BY_NUPRE", "resolution_status": "EXACT",
            "resolution_method": "nupre", "identity_verified": True,
        },
        "predio_real": {
            "predio": {"destino_economico": "Habitacional"},
            "entorno": {"barrio": "BARRIO DE PRUEBA", "estrato": "3", "disponible": True,
                        "amenaza_remocion_masa": {"nivel": "Media", "intersecta": True}},
            "condicion": {"condicion_juridica": "Propiedad Horizontal"},
            "disponible": True,
        },
        "administrative_context": {"barrio": "BARRIO DE PRUEBA", "comuna": "01",
                                  "estrato": "3", "tratamiento": "Consolidacion"},
        "analysis": {
            "folio": FOLIO_QA, "titulares": "TITULAR DE PRUEBA CC# 1000000000",
            "modalidad_adquisicion": "N/D", "circulo_registral": "001 - PRUEBA",
            "anotaciones": [["007", "01-01-2026", "GRAVAMEN: Hipoteca",
                             "TITULAR DE PRUEBA -> BANCO DE PRUEBA S.A.", "VIGENTE"]],
            "texto_ctl": "certificado sintético de prueba",
        },
        "hallazgos": [
            ("ALTO", None, None, "H-01 | Hipoteca vigente a favor del acreedor",
             "Certificado de tradición y libertad",
             "El folio declara una hipoteca abierta sin cancelar.",
             "Gestionar saldo y levantamiento con el acreedor antes de la transferencia."),
            ("MEDIO", None, None, "H-02 | Limitación vigente declarada en el folio",
             "Certificado de tradición y libertad",
             "El folio declara una afectación vigente.",
             "Aportar el acto de levantamiento o la autorización aplicable."),
        ],
        "titulux": {"screening_summary": {
            "status": "SCREENING_COMPLETE", "executed": True,
            "coverage_status": "COVERAGE_COMPLETE",
            "subjects_declared": 2, "subjects_screened": 2,
            "subjects": [
                {"subject_id": "titular-1", "canonical_name": "TITULAR DE PRUEBA",
                 "person_type": "NATURAL_PERSON", "document_type": "cc",
                 "document_number": "1000000000", "roles": ["TITULAR_ACTUAL"],
                 "participation": "100%"},
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
            "evidence_chain_status": cadena_evidencia,
        }},
        "res_avaluo": {"value_m2": 6000000, "consolidado": 352500000,
                       "banda_baja": 330000000, "banda_alta": 375000000,
                       "sector": "SECTOR DE PRUEBA", "metodologia_aplica": True},
        "valuation_authorization": {"allowed": True, "identity_authorized": True,
                                    "market_context_authorized": True},
        "clasificacion": {
            "juridical_regime": {"value": "PROPIEDAD_HORIZONTAL", "status": "VERIFIED_REGISTRAL"},
            "economic_use": {"value": "HABITACIONAL", "status": "VERIFIED_REGISTRAL"},
            "physical_typology": {"value": "UNIDAD_EN_PROPIEDAD_HORIZONTAL",
                                  "status": "VERIFIED_REGISTRAL"},
        },
        "geo_eval": {"amenaza_remocion_masa": {"nivel": "Media", "intersecta": True},
                     "areas_en_riesgo": {"nivel": "Medio", "intersecta": False}},
        "predio_real_disponible": True,
    }
    poi = {
        "queried_at": "2026-01-15T10:00:00+00:00",
        "sources_attempted": ["OSM"], "sources_succeeded": ["OSM"],
        "category_status": {"Salud": "AVAILABLE", "Educacion": "AVAILABLE",
                            "Comercio": "AVAILABLE", "Recreacion": "NO_MATCH"},
        "items": {
            "Salud": [{"name": "CENTRO MEDICO DE PRUEBA", "type": "hospital",
                       "lat": 1.0, "lon": -1.0, "distance": 420.0, "source": "OSM"}],
            "Educacion": [{"name": "COLEGIO DE PRUEBA", "type": "school",
                           "lat": 1.0, "lon": -1.0, "distance": 260.0, "source": "OSM"}],
            "Comercio": [{"name": "SUPERMERCADO DE PRUEBA", "type": "supermarket",
                          "lat": 1.0, "lon": -1.0, "distance": 180.0, "source": "OSM"}],
            "Recreacion": [],
        },
    }
    return {
        "ctx": ctx, "poi": poi,
        "receipts": {"generated_at": "2026-01-15T10:05:00+00:00"},
        "release": {"release_status": "VALID_FOR_RELEASE", "policy": "MARK",
                    "environment": "test"},
        "solar": {"momentos": [
            {"hora": "09:00 COT", "azimut": "102.33°", "elevacion": "45.98°",
             "estado": "Sol Directo"},
            {"hora": "12:00 COT", "azimut": "191.14°", "elevacion": "78.25°",
             "estado": "Sol Directo"},
            {"hora": "15:00 COT", "azimut": "259.25°", "elevacion": "41.62°",
             "estado": "Sombra (Orientación)"},
        ]},
    }


def _generar(nombre="qa", *, cadena_evidencia="SEALED"):
    """Genera el EJECUTIVO en disco (con su auditoría) y devuelve (ruta, resultado)."""
    salida = SALIDA_QA / nombre
    salida.mkdir(parents=True, exist_ok=True)
    tecnico = salida / entrega.ARCHIVO_TECNICO.format(folio=FOLIO_QA)
    tecnico.write_bytes(b"%PDF-1.4\n% anexo sintetico de prueba\n")
    resultado = entrega.construir_entregables(
        _captura_sintetica(cadena_evidencia=cadena_evidencia), folio=FOLIO_QA,
        ciudad="barranquilla", tecnico=tecnico, salida_dir=salida, area=58.75,
        tipo_unidad="URBANO", run_id="qa-run-20b-r1")
    return Path(resultado["ejecutivo"]), resultado


def _paginas(ruta: Path):
    from pypdf import PdfReader
    return [p.extract_text() or "" for p in PdfReader(str(ruta)).pages]


class TestPdfEntregado(unittest.TestCase):
    """§3 · §4 · §5 · §6 · §8 · §14 — el contrato del archivo, no del código."""

    @classmethod
    def setUpClass(cls):
        cls.ruta, cls.resultado = _generar("contrato")
        cls.paginas = _paginas(cls.ruta)
        cls.texto = "\n".join(cls.paginas)

    def test_page_count_no_supera_seis(self):
        self.assertLessEqual(len(self.paginas), entrega.MAX_PAGINAS_EJECUTIVO,
                             "un ejecutivo de más de 6 páginas no es el entregable aprobado")
        self.assertEqual(len(self.paginas), 6)

    def test_las_seis_paginas_estan_en_el_orden_aprobado(self):
        for i, titulo in enumerate(entrega.TITULOS_APROBADOS, start=1):
            self.assertIn(titulo, self.paginas[i - 1],
                          f"la página {i} no dice «{titulo}»")

    def test_pagina1_resumen_hallazgos_y_sello(self):
        p1 = self.paginas[0]
        self.assertIn("RESUMEN DE DECISIÓN", p1)
        self.assertIn("hallazgos", p1)
        self.assertIn("INFORMACIÓN GENERAL", p1)
        self.assertIn("ESTADO GENERAL", p1)
        self.assertIn("SELLO GLOBAL", p1)
        for campo in ("Dirección", "Matrícula", "Ciudad", "Barrio", "Área", "Uso",
                      "Régimen", "Valor estimado"):
            self.assertIn(campo.upper(), p1.upper(), f"falta el campo «{campo}» en el bloque A")
        for columna in ("SEVERIDAD", "HALLAZGO", "AFECTA A", "ACCIÓN"):
            self.assertIn(columna, p1, f"falta la columna «{columna}» de hallazgos")
        self.assertIn("DICTUS_MASTER_HASH", p1)

    def test_pagina3_listas_consultadas_por_su_nombre(self):
        p3 = self.paginas[2]
        for lista in ("ONU", "OFAC SDN", "UK Sanctions List"):
            self.assertIn(lista, p3, f"la página 3 no acredita la lista «{lista}»")
        for columna in ("SUJETO", "ROL", "DOCUMENTO", "RESULTADO"):
            self.assertIn(columna, p3)
        self.assertIn("PREPARACIÓN PARA", p3)
        for destino in ("COMPRA / VENTA", "CRÉDITO HIPOTECARIO", "SEGURO DE TÍTULO"):
            self.assertIn(destino, p3)

    def test_pagina5_salud_educacion_y_asoleamiento(self):
        p5 = self.paginas[4]
        self.assertIn("Salud", p5)
        self.assertIn("Educación", p5)
        self.assertIn("Comercio", p5)
        self.assertIn("Recreación", p5)
        for hora in ("09:00", "12:00", "15:00"):
            self.assertIn(hora, p5)

    def test_pagina6_identidad_y_valor(self):
        p6 = self.paginas[5]
        self.assertIn("Valor estimado", p6)
        for campo in ("Dirección oficial", "Matrícula", "NUPRE", "Número predial",
                      "Unidad", "Área", "Régimen jurídico", "Estado de identidad"):
            self.assertIn(campo, p6, f"falta «{campo}» en la identidad del inmueble")
        self.assertIn("Valor/m²", p6)
        self.assertIn("Método principal", p6)

    def test_no_contiene_encabezados_legacy(self):
        mayus = self.texto.upper()
        for encabezado in entrega.ENCABEZADOS_LEGACY:
            self.assertNotIn(encabezado.upper(), mayus,
                             f"el ejecutivo no puede contener el capítulo legacy «{encabezado}»")

    def test_no_contiene_fugas_tecnicas(self):
        mayus = self.texto.upper()
        for patron in ("ARHIAX_EVIDENCE_HMAC_KEY", "RuntimeError".upper(),
                       "Traceback".upper(), "api/pdf_compiler.py".upper()):
            self.assertNotIn(patron, mayus, f"fuga técnica «{patron}» en el entregable")

    def test_el_manifiesto_verifica_y_es_el_del_pdf(self):
        man = self.resultado["manifest"]
        verif = entrega.verificar_entrega(man)
        self.assertEqual(verif["result"], "MATCH")
        self.assertIn(man["master_hash"], self.resultado["modelo"]["master_hash"])
        self.assertEqual(man["ejecutivo_paginas"], 6)
        self.assertEqual(man["ejecutivo_titulos"], list(entrega.TITULOS_APROBADOS))
        # El hash abreviado impreso es el del manifest (una sola verdad).
        self.assertIn(str(man["master_hash_abreviativo"] if "master_hash_abreviativo" in man
                          else man["master_hash_abreviado"]).upper()[:12], self.texto.upper())

    def test_sin_valoracion_no_se_imprime_ninguna_cifra(self):
        """Doctrina: nunca `$ 0` ni un monto sin autorización."""
        captura = _captura_sintetica()
        captura["ctx"]["valuation_authorization"] = {"allowed": False}
        captura["ctx"]["res_avaluo"] = {"motivo_no_aplica": "Contexto de mercado incompleto."}
        salida = SALIDA_QA / "sin_valoracion"
        salida.mkdir(parents=True, exist_ok=True)
        r = entrega.construir_entregables(
            captura, folio=FOLIO_QA, ciudad="barranquilla",
            tecnico=salida / entrega.ARCHIVO_TECNICO.format(folio=FOLIO_QA),
            salida_dir=salida, area=58.75, run_id="qa-sin-valoracion")
        p6 = _paginas(Path(r["ejecutivo"]))[5]
        self.assertIn("VALORACIÓN NO DISPONIBLE", p6)
        self.assertNotIn("$ 0", p6)
        self.assertIn("no se imprime ningún monto", p6.lower())


class TestAsercionesDuras(unittest.TestCase):
    """§3 §4 §5 §8: si el PDF físico no cumple, la entrega NO se produce."""

    def test_el_pdf_legacy_de_17_paginas_es_rechazado(self):
        legacy = ROOT / "docs" / "forensics" / "040-646406" / "dictus_2b" / "DICTUS_TECNICO_040-646406.pdf"
        if not legacy.exists():
            self.skipTest("no hay un PDF técnico generado para comparar")
        with self.assertRaises(entrega.EntregaEjecutivaInvalida) as ctx:
            entrega.auditar_ejecutivo(legacy)
        self.assertIn("page_count", str(ctx.exception))

    def test_un_pdf_con_encabezado_legacy_es_rechazado(self):
        from reportlab.pdfgen import canvas
        ruta = SALIDA_QA / "legacy_falso.pdf"
        ruta.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(ruta), pagesize=(595.28, 841.89))
        for _ in range(6):
            c.drawString(40, 800, "00 - Naturaleza de este Documento")
            c.showPage()
        c.save()
        with self.assertRaises(entrega.EntregaEjecutivaInvalida) as ctx:
            entrega.auditar_ejecutivo(ruta)
        mensaje = str(ctx.exception)
        self.assertIn("Naturaleza", mensaje)
        self.assertIn("RESUMEN DE DECISIÓN", mensaje)

    def test_un_ejecutivo_con_mas_de_seis_paginas_es_rechazado(self):
        from pypdf import PdfReader, PdfWriter
        ruta = SALIDA_QA / "doce_paginas.pdf"
        ruta.parent.mkdir(parents=True, exist_ok=True)
        base = PdfReader(str(Path(_generar("doce_base")[0])))
        escritor = PdfWriter()
        for _ in range(2):
            for pag in base.pages:
                escritor.add_page(pag)
        with open(ruta, "wb") as f:
            escritor.write(f)
        with self.assertRaises(entrega.EntregaEjecutivaInvalida) as ctx:
            entrega.auditar_ejecutivo(ruta)
        self.assertIn("page_count=12", str(ctx.exception))

    def test_la_retícula_no_declara_desbordes(self):
        self.assertEqual(list(de.VIOLACIONES), [],
                         "el renderer declaró desbordes: el documento no está apto")

    def test_un_desborde_declarado_bloquea_la_entrega(self):
        ruta, _ = _generar("desborde")
        de.VIOLACIONES.append("P1 prueba: desborda 10 pt")
        try:
            with self.assertRaises(entrega.EntregaEjecutivaInvalida) as ctx:
                entrega.auditar_ejecutivo(ruta)
            self.assertIn("retícula", str(ctx.exception))
        finally:
            del de.VIOLACIONES[:]


class TestSinFugasDeSellado(unittest.TestCase):
    """§8: si el sellado falla se imprime «EVIDENCIA NO SELLADA», nunca la excepción."""

    def test_el_limpiador_sustituye_cualquier_fuga(self):
        for sucio in ("RuntimeError: boom ARHIAX_EVIDENCE_HMAC_KEY",
                      "Traceback (most recent call last): ...",
                      "hmac key missing"):
            self.assertEqual(de.limpio(sucio), "EVIDENCIA NO SELLADA")

    def test_cadena_fallida_se_declara_sin_lenguaje_tecnico(self):
        ruta, resultado = _generar("cadena_fallida", cadena_evidencia="FAILED")
        texto = "\n".join(_paginas(ruta))
        self.assertIn("EVIDENCIA NO SELLADA", texto)
        self.assertEqual(resultado["manifest"]["evidence_manifest"]["estado"],
                         "EVIDENCIA NO SELLADA")
        for patron in ("FAILED", "RuntimeError", "ARHIAX_EVIDENCE_HMAC_KEY"):
            self.assertNotIn(patron.upper(), texto.upper())


class TestEntregaDelProducto(unittest.TestCase):
    """§2 §13: el documento que ENTREGA el producto es el Ejecutivo, no el técnico."""

    def setUp(self):
        os.environ.setdefault("ARHIAX_ENV", "test")
        os.environ.setdefault("ARHIAX_AUTH_SECRET", "qa-local-secret")
        os.environ.setdefault("ARHIAX_ADMIN_PASSWORD", "dev-only-not-a-real-password")
        import index
        self.index = index
        conn = index.get_db_connection()
        conn.execute("DELETE FROM trabajos_pdf WHERE id = ?", (JOB_QA,))
        conn.commit()
        conn.close()

    tearDown = setUp

    def test_las_cabeceras_declaran_el_documento_principal(self):
        ruta, resultado = _generar("cabeceras")
        cabeceras = self.index._cabeceras_entrega(resultado)
        self.assertIn(f'filename="{entrega.ARCHIVO_EJECUTIVO.format(folio=FOLIO_QA)}"',
                      cabeceras["Content-Disposition"])
        self.assertEqual(cabeceras["X-ARHIAX-Documento"], "DICTUS_EJECUTIVO")
        self.assertEqual(cabeceras["X-ARHIAX-Paginas-Ejecutivo"], "6")
        self.assertIn("DICTUS_TECNICO", cabeceras["X-ARHIAX-Anexo-Tecnico"])

    def test_el_nombre_entregado_nunca_es_pendiente(self):
        self.assertEqual(self.index._folio_entrega("040-646406"), "040-646406")
        self.assertEqual(self.index._folio_entrega("TST-000001"), "TST-000001")
        self.assertNotIn("Pendiente", self.index._folio_entrega("matrícula ilegible"))
        self.assertEqual(self.index._folio_entrega(None), "SIN-FOLIO")

    def test_el_trabajo_guarda_ejecutivo_anexo_y_manifest(self):
        ruta, resultado = _generar("trabajo")
        ejecutivo = Path(resultado["ejecutivo"]).read_bytes()
        self.index._actualizar_trabajo(
            JOB_QA, "listo", pdf_bytes=ejecutivo,
            tecnico_bytes=Path(resultado["tecnico"]).read_bytes(),
            manifest_json=json.dumps(resultado["manifest"], ensure_ascii=False),
            folio=FOLIO_QA)
        # El documento principal se sirve como EJECUTIVO, con su nombre de expediente.
        principal = self.index.obtener_trabajo_pdf(JOB_QA, {"username": "qa", "rol": "admin"})
        self.assertIn(f'filename="{entrega.ARCHIVO_EJECUTIVO.format(folio=FOLIO_QA)}"',
                      principal.headers["content-disposition"])
        self.assertEqual(principal.body, ejecutivo)
        # El técnico se sirve aparte y con nombre de ANEXO (nunca como principal).
        anexo = self.index.obtener_anexo_tecnico(JOB_QA, {"username": "qa", "rol": "admin"})
        self.assertIn(f'filename="ANEXO_TECNICO_{FOLIO_QA}.pdf"',
                      anexo.headers["content-disposition"])
        self.assertEqual(anexo.headers["x-arhiax-documento"], "ANEXO_TECNICO")
        # El manifest del trabajo es el mismo hash que imprime el documento.
        man = json.loads(self.index.obtener_manifest_dictus(
            JOB_QA, {"username": "qa", "rol": "admin"}).body)
        self.assertEqual(man["master_hash"], resultado["manifest"]["master_hash"])
        self.assertEqual(man["ejecutivo_paginas"], 6)

    def test_el_anexo_no_existe_si_no_se_genero(self):
        self.index._actualizar_trabajo(JOB_QA, "listo", pdf_bytes=b"%PDF-1.4\n")
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            self.index.obtener_anexo_tecnico(JOB_QA, {"username": "qa", "rol": "admin"})
        self.assertEqual(ctx.exception.status_code, 409)

    def test_el_producto_ya_no_entrega_el_tecnico_como_principal(self):
        fuente = (ROOT / "api" / "index.py").read_text(encoding="utf-8")
        self.assertNotIn("ARHIAX_Dictamen_{", fuente,
                         "el nombre del documento entregado no puede ser el legacy")
        self.assertIn("_iniciar_entrega()", fuente)
        self.assertIn("_generar_entrega(", fuente)
        self.assertIn("DICTUS_EJECUTIVO", fuente)

    def test_un_caso_legacy_no_entrega_el_tecnico_como_principal(self):
        """Un expediente sin Ejecutivo pide regenerarse: no se invierte el orden."""
        conn = self.index.get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM dictamenes WHERE id = ?", (-777,))
        cur.execute("INSERT INTO dictamenes (id, folio_matricula, direccion, barrio, "
                    "estrato, area, estado, fecha_creacion, pdf_path) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (-777, FOLIO_QA, "CALLE 1", "BARRIO", 3, 58.75, "COMPLETADO",
                     "2026-01-15T00:00:00", str(SALIDA_QA / "legacy" / "viejo.pdf")))
        conn.commit()
        conn.close()
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            self.index.download_pdf(-777, {"username": "qa", "rol": "admin"})
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("EJECUTIVO", ctx.exception.detail)


class TestRetículaSinSolapamientos(unittest.TestCase):
    """Ninguna caja de texto puede imprimirse encima de otra (documento legible)."""

    def test_cero_solapamientos_en_las_seis_paginas(self):
        try:
            import pymupdf
        except Exception:  # noqa: BLE001
            self.skipTest("pymupdf no está instalado en este entorno")
        ruta, _ = _generar("retícula")

        def area(b):
            return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])

        def inter(a, b):
            return area((max(a[0], b[0]), max(a[1], b[1]),
                         min(a[2], b[2]), min(a[3], b[3])))

        with pymupdf.open(str(ruta)) as doc:
            for i, pag in enumerate(doc, start=1):
                cajas = [w[:4] for w in pag.get_text("words")]
                for a in range(len(cajas)):
                    for b in range(a + 1, len(cajas)):
                        ia = inter(cajas[a], cajas[b])
                        if ia <= 0:
                            continue
                        menor = min(area(cajas[a]), area(cajas[b]))
                        self.assertFalse(
                            menor > 0 and ia / menor > 0.35,
                            f"página {i}: cajas de texto solapadas ({ia:.0f} pt²)")


class TestHistorialDelCaso(unittest.TestCase):
    """El insumo de coherencia es real: si el folio tiene auditoría, se lee."""

    def test_el_golden_tiene_informe_y_un_folio_inexistente_no(self):
        hist = entrega.historial_del_caso("040-646406")
        self.assertTrue(hist, "falta el informe de coherencia histórico del caso Golden")
        self.assertTrue(hist.get("conflictos_abiertos"))
        self.assertEqual(entrega.historial_del_caso("NO-EXISTE-999"), {})

    def test_sin_informe_no_se_afirma_sin_cambios(self):
        """Sin expediente histórico comparado, decir «sin cambios» sería un PASS falso."""
        ruta, _ = _generar("sin_historial")
        p4 = _paginas(ruta)[3]
        self.assertIn("sin expediente histórico comparado", p4.lower())
        self.assertNotIn("Sin cambios entre las versiones comparadas", p4)


if __name__ == "__main__":
    unittest.main()

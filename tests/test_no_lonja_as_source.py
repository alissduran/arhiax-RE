# -*- coding: utf-8 -*-
"""GUARDA DE DOCTRINA — la Lonja NO es una fuente de datos.

Decisión de producto (docs/source_pack/INSTITUTIONAL_PARTNERS.md,
`api/source_licenses_v2.py::PARTNERS_INSTITUCIONALES`): la Lonja **no aporta datos a
DICTUS**. No es `source_id` del Source Registry, no tiene dataset, ni contrato de datos,
ni URL, ni bloque de licencia, ni valor por m² suministrado por ella. El valor de mercado
que usa el producto es un **parámetro declarado por la corrida** (artefacto local de
metodología), **sin fuente externa automática verificable**.

Esta guarda FALLA si el EJECUTIVO o el TÉCNICO vuelven a afirmar o sugerir una fuente
Lonja. Hoy no existe ninguna fuente real que pueda marcarse como tal, de modo que la
prohibición es TOTAL en el texto de los dos documentos:

  · EJECUTIVO: se RENDERIZA el PDF con un contexto de mercado que inyecta la declaración
    problemática tal como la declaró el artefacto local (`+ Lonja BAQ referencial`) y el
    identificador sellado `lonja_baq_metodologia`, y se extrae el TEXTO de las páginas con
    `pypdf`. Ninguna página puede contener «Lonja» (ni en minúsculas), y la etiqueta
    verdadera (`parámetros declarados por la corrida`) sí debe imprimirse: el test no pasa
    por no imprimir nada.
  · TÉCNICO: se comprueba el texto REAL de la alerta de valoración (`get_valoracion_alert`)
    y se revisan los literales de cadena de los módulos que escriben DOCUMENTOS (no los
    comentarios): ninguno puede contener «Lonja».

Los identificadores sellados (`SOURCE_ID="LONJA_MARKET_BAQ"`, `METHODOLOGY_ID`) NO se
renombran y NO se imprimen: esta guarda protege el TEXTO, que es lo que lee el cliente.
"""
import ast
import csv
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "api"))

import atribucion_mercado as am    # noqa: E402
import dictamen_data as dd         # noqa: E402
import dictus_ejecutivo as de      # noqa: E402
import dictus_estado as dse        # noqa: E402
import dictus_manifiesto as dm     # noqa: E402
import dictus_secciones as sec     # noqa: E402
import market_context as mctx      # noqa: E402

FOLIO = "TST-000042"          # el folio se imprime: no puede contener la palabra vigilada
SALIDA = ROOT / "tmp_no_lonja"

# Declaración REAL del artefacto local en la corrida auditada
# (docs/source_pack/MARKET_CONTEXT_AUDIT.md, Anexo C · S3). Es la cadena que el ejecutivo
# imprimía en su línea «Tasa y parámetros: …».
DECLARACION_AUDITADA = ("Precio de venta verificado en la constructora del proyecto "
                        "(unidades ~58 m2 terminadas, 2026) + Lonja BAQ referencial")

# Módulos que escriben TEXTO de documento (PDF ejecutivo, PDF técnico, run state y manifest).
MODULOS_DE_DOCUMENTO = ("pdf_compiler", "dictamen_data", "dictus_ejecutivo", "dictus_secciones",
                        "dictus_estado", "dictus_decision", "dictus_manifiesto", "receipts")


def _fuente_declarada_cruda() -> str:
    """La `fuente` que declara HOY la fila del artefacto local (o la auditada, si se limpió).

    Se inyecta a propósito la versión CRUDA: la guarda debe probar el RENDERIZADOR, no la
    limpieza del artefacto. Si el YAML llegara a limpiarse, se usa la cadena auditada para
    que la regresión del renderizador siga siendo detectable.
    """
    try:
        y = mctx._load_lonja()
        cruda = ((y.get("valor_suelo_por_sector") or {}).get("Miramar") or {}).get("fuente")
    except Exception:  # noqa: BLE001 — sin artefacto se prueba con la cadena auditada
        cruda = None
    if not cruda or not am.contiene_atribucion_no_acreditada(cruda):
        return DECLARACION_AUDITADA
    return str(cruda)


def _literales(nombre: str):
    """Literales de cadena (incluidos docstrings) del módulo, con su número de línea."""
    ruta = ROOT / "api" / f"{nombre}.py"
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
            yield nodo.lineno, nodo.value


def _renderizar_ejecutivo(nombre: str):
    """Ejecutivo REAL: estado → modelo → secciones → PDF, con el mercado problemático."""
    import test_dictus_20c_fidelidad as fx    # fixture de corrida sintética (misma forma)

    salida = SALIDA / nombre
    salida.mkdir(parents=True, exist_ok=True)
    rs = dse.construir_run_state(fx._captura(cadena="SEALED", assets=None),
                                run_id="qa-no-lonja", folio=FOLIO,
                                ciudad="barranquilla", area=58.75, tipo_unidad="URBANO")
    # El mercado REAL de la corrida, con la declaración CRUDA y el identificador sellado.
    crudo = _fuente_declarada_cruda()
    assert am.contiene_atribucion_no_acreditada(crudo), "el fixture debe traer la atribución"
    mc = rs["market_context"]
    mc["market_methodology_id"] = mctx.METHODOLOGY_ID          # identificador sellado
    mc["market_methodology_version"] = "0.1-codiseno"
    mc["market_rate_source"] = crudo
    mc["sector_metodologico"] = {
        "matched_sector": "Miramar", "match_type": "EXACT",
        "value_m2": 6_800_000, "rango_min_m2": 5_500_000, "rango_max_m2": 8_000_000,
        "market_methodology_id": mctx.METHODOLOGY_ID,
        "market_methodology_version": "0.1-codiseno",
        "methodology_entity": "Lonja de Propiedad Raíz de Barranquilla",
    }
    rs["market_context"] = mc
    hist = {"version": "dictus-historical-consistency/1.0.0", "versiones_comparadas": 3,
            "conflictos_abiertos": []}
    rs["historical_consistency"] = hist
    dse.agregar_findings_de_coherencia(rs, hist)
    modelo = dm.construir_documento_maestro(rs, historial=hist, folio=FOLIO)
    secciones = sec.desde_estado(rs, modelo, hist)
    pdf = salida / f"DICTUS_EJECUTIVO_{FOLIO}.pdf"
    de.render(modelo, secciones, pdf)
    from pypdf import PdfReader
    paginas = [(p.extract_text() or "") for p in PdfReader(str(pdf)).pages]
    return pdf, rs, secciones, paginas


class TestEjecutivoNoAfirmaFuenteLonja(unittest.TestCase):
    """El ejecutivo RENDERIZADO no puede contener «Lonja» en ninguna página."""

    @classmethod
    def setUpClass(cls):
        (cls.pdf, cls.rs, cls.secciones,
         cls.paginas) = _renderizar_ejecutivo("guard")
        cls.texto = "\n".join(cls.paginas)
        cls.plano = " ".join(cls.texto.upper().split())

    def test_ninguna_pagina_del_ejecutivo_nombra_la_lonja(self):
        for i, pagina in enumerate(self.paginas, start=1):
            self.assertNotIn("lonja", pagina.lower(),
                             f"la página {i} del ejecutivo vuelve a afirmar/sugerir una "
                             f"fuente Lonja: {pagina[:400]!r}")

    def test_el_identificador_sellado_no_se_imprime(self):
        # El id sigue viajando en el plano máquina (`market_methodology_id`) y NO se imprime.
        self.assertEqual(self.rs["market_context"]["market_methodology_id"],
                         "lonja_baq_metodologia")
        self.assertEqual(self.secciones["valor"]["metodologia_version"], "0.1-codiseno")
        self.assertNotIn("LONJA_BAQ_METODOLOGIA", self.plano)

    def test_la_etiqueta_verdadera_si_se_imprime(self):
        # La guarda no pasa por no imprimir: el ejecutivo declara QUÉ es el valor y de
        # dónde NO viene.
        etiqueta = am.ETIQUETA_METODO.upper()
        self.assertIn(" ".join(etiqueta.split()), self.plano)
        self.assertIn("PARÁMETROS DECLARADOS POR LA CORRIDA", self.plano)
        self.assertIn("SIN FUENTE EXTERNA AUTOMÁTICA VERIFICADA", self.plano)

    def test_las_secciones_no_llevan_la_atribucion(self):
        valor = self.secciones["valor"]
        crudo = " ".join(str(valor["tasa_fuente"]).split())
        self.assertNotIn("lonja", crudo.lower())
        self.assertIn("parámetros declarados por la corrida", crudo.lower())
        self.assertNotIn("lonja", " ".join(str(valor["metodologia"]).split()).lower())
        # La fuente declarada del artefacto SÍ se conserva (sin la atribución): no se
        # borra el dato real («precio de venta verificado en la constructora»).
        self.assertIn("precio de venta verificado en la constructora", crudo.lower())

    def test_el_run_state_declara_el_mercado_sin_fuente_lonja(self):
        articulos = (self.rs["evidence_manifest_input"] or {}).get("articulos") or []
        valoracion = [a for a in articulos if a.get("tipo") == "VALORACION"]
        self.assertTrue(valoracion)
        for articulo in valoracion:
            self.assertNotIn("lonja", str(articulo.get("fuente")).lower())
        self.assertEqual(valoracion[0]["fuente"],
                         "parámetros de mercado declarados por la corrida")


class TestTecnicoNoAfirmaFuenteLonja(unittest.TestCase):
    """El técnico (alerta de valoración + literales del renderizador) tampoco."""

    @classmethod
    def setUpClass(cls):
        cls.alerta = dd.get_valoracion_alert(
            "Miramar", {"consolidado": 399_500_000, "metodo_principal": "m1"},
            lambda v: f"$ {v:,}".replace(",", "."))

    def test_la_alerta_de_valoracion_no_nombra_la_lonja(self):
        self.assertNotIn("Lonja", self.alerta)
        self.assertNotIn("lonja", self.alerta.lower())
        self.assertIn("metodología local de la corrida", self.alerta)
        self.assertIn("SINTESIS DE VALORACION", self.alerta)

    def test_los_modulos_de_documento_no_tienen_literales_con_lonja(self):
        for nombre in MODULOS_DE_DOCUMENTO:
            for linea, literal in _literales(nombre):
                self.assertNotIn("Lonja", literal,
                                 f"api/{nombre}.py:{linea} vuelve a nombrar la Lonja en un "
                                 f"literal de documento: {literal[:120]!r}")

    def test_el_texto_del_tecnico_sobre_mercado_no_atribuye_practica_a_la_lonja(self):
        # El bloque 07 del técnico es texto estático: se revisa tal cual se escribe.
        fuente = (ROOT / "api" / "pdf_compiler.py").read_text(encoding="utf-8")
        for aguja in ("practica de la Lonja", "Lonja de Barranquilla", "Lonja/IGAC"):
            self.assertNotIn(aguja, fuente)
        # Las etiquetas verdaderas que sí deben existir en el técnico.
        self.assertIn("practica declarada por la metodología local", fuente)
        self.assertIn("metodología local/IGAC", fuente)

    def test_el_tecnico_no_rotula_automatico_un_valor_configurado_a_mano(self):
        """P5 · CERRADO: la etiqueta `(AUTOMÁTICA)` sobre una constante se eliminó.

        La guarda anterior dejaba constancia del hallazgo SIN corregirlo («sobre-afirma
        automaticidad: el valor es una constante declarada por la corrida»). Hoy el
        técnico declara QUÉ es el valor (`parámetros declarados por la corrida`) y su
        ORIGEN real (`origin`), y no puede decir «automático» de un valor escrito a mano.
        """
        fuente = (ROOT / "api" / "pdf_compiler.py").read_text(encoding="utf-8")
        self.assertIn("FUENTE: ESTIMACIÓN REFERENCIAL DE MERCADO ARHIAX", fuente)
        self.assertNotIn("(AUTOMÁTICA)]", fuente)
        self.assertNotIn("de caracter automatico", fuente)
        self.assertIn("PARÁMETROS DECLARADOS", fuente)
        self.assertIn("ORIGEN: ", fuente)


class TestDoctrinaEnLosArtefactos(unittest.TestCase):
    """El Source Registry y los artefactos de doctrina son coherentes con la guarda."""

    def test_el_registro_no_declara_la_lonja_como_fuente(self):
        reg = json.loads((ROOT / "docs" / "source_pack"
                          / "barranquilla_sources_v1.json").read_text(encoding="utf-8"))
        self.assertNotIn("LONJA_MARKET_BAQ", reg["sources"])
        lonja = reg["no_fuentes_institucionales"]["aliados"]["LONJA_BAQ"]
        self.assertFalse(lonja["es_fuente_de_datos"])
        self.assertFalse(lonja["en_source_registry"])

    def test_el_manifest_no_declara_metadatos_de_fuente_lonja(self):
        man = json.loads((ROOT / "docs" / "source_pack"
                          / "BARRANQUILLA_SOURCE_PACK_MANIFEST.json").read_text(
                              encoding="utf-8"))
        for seccion in ("approved_sources", "source_metadata_hashes"):
            self.assertFalse([s for s in man[seccion] if "LONJA" in s.upper()], seccion)
        self.assertFalse([s for s in man["licenses"]["by_source"] if "LONJA" in s.upper()])

    def test_la_matriz_de_cobertura_no_atribuye_el_mercado_a_la_lonja(self):
        ruta = (ROOT / "docs" / "source_pack"
                / "SOURCE_COVERAGE_MATRIX_040-646406.csv")
        filas = [l for l in ruta.read_text(encoding="utf-8").splitlines()
                 if l.startswith("18-mercado")]
        self.assertEqual(len(filas), 1, "la matriz debe declarar la fila de mercado")
        campos = next(csv.reader([filas[0]]))
        # La columna `source` NO puede ser un `source_id` de la Lonja: se declara que no hay
        # fuente. (El identificador sellado y la explicación de la doctrina sí se nombran en
        # la procedencia/detalle: dicen justamente que NO es una fuente.)
        self.assertNotIn("LONJA", campos[1].upper())
        self.assertIn("SIN_FUENTE", campos[1].upper())
        self.assertEqual(campos[2], "SOURCE_UNAVAILABLE")
        self.assertIn("NO ES UNA FUENTE DE DATOS", campos[5].upper())


if __name__ == "__main__":
    unittest.main()

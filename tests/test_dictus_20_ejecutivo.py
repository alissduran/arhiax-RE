# -*- coding: utf-8 -*-
"""DICTUS 2.0 — Pruebas de consistencia del informe ejecutivo (§AP).

Cubren las quince comprobaciones del prompt maestro sobre los artefactos REALES de la
corrida del folio 040-646406, más las invariantes de la capa de historia y del hash
maestro. Son bloqueantes: si el ejecutivo volviera a imprimir una cifra en conflicto, o
a confundir el hash maestro con el del PDF, estas pruebas fallan.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))

import dictus_historia as dh          # noqa: E402
import dictus_manifiesto as dm        # noqa: E402

SALIDA = ROOT / "docs" / "forensics" / "040-646406" / "dictus_2"
PDF = SALIDA / "DICTUS_2.0_EXPEDIENTE_040-646406.pdf"


def _json(nombre):
    p = SALIDA / nombre
    if not p.exists():
        raise unittest.SkipTest(f"falta el artefacto {nombre}: ejecute "
                                "scripts/dictus_historia_atributos.py y "
                                "scripts/dictus_ejecutivo_040646406.py")
    return json.loads(p.read_text(encoding="utf-8"))


def _texto_paginas(n=6):
    import pymupdf
    with pymupdf.open(str(PDF)) as d:
        return [" ".join(p.get_text().split()) for p in list(d)[:n]]


class TestHistoriaYCoherencia(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.hist = _json("HISTORICAL_CONSISTENCY_REPORT.json")
        cls.matriz = _json("ATTRIBUTE_HISTORY_MATRIX.json")

    def _abierto(self, atributo):
        return next((c for c in self.hist["conflictos_abiertos"]
                     if c["atributo"] == atributo), None)

    # §AP 2 y 3
    def test_altura_con_valores_incompatibles_es_conflicto_historico(self):
        c = self._abierto("altura_maxima")
        self.assertIsNotNone(c, "altura con 8 y 11 pisos debe quedar en conflicto")
        self.assertEqual(set(c["valores"]), {"8", "11"})

    def test_tratamiento_distinto_es_conflicto_historico(self):
        c = self._abierto("tratamiento")
        self.assertIsNotNone(c, "CONSOLIDACIÓN y DESARROLLO no pueden pasar como VERIFICADO")
        self.assertIn("Desarrollo (Bajo) -- polígono POT consultado en vivo", c["valores"])

    # §AP 1: un dato material contradictorio no se renderiza VERIFIED
    def test_ningun_atributo_contradictorio_queda_verificado(self):
        for atributo in ("altura_maxima", "tratamiento"):
            info = dh.conflicto_de_atributo(self.matriz, atributo)
            self.assertEqual(info["estado"], dh.HISTORICAL_CONFLICT)
            self.assertFalse(dh.gate_urbanistico(self.matriz, atributo, "11")["puede_publicar"])

    # §AP 4: destino económico ≠ uso POT NO es conflicto (dimensiones distintas)
    def test_destino_y_uso_son_dimensiones_distintas(self):
        self.assertNotIn("destino_economico",
                         {c["atributo"] for c in self.hist["conflictos_abiertos"]
                          if c["atributo"] == "uso_pot"})

    # §AP 5: misma dimensión con dos valores incompatibles → CONFLICT
    def test_misma_dimension_incompatible_es_conflicto(self):
        datos_a = {"tratamiento": {"value": "Consolidación (Nivel 2)"},
                   "__globales__": {"fuente_pot": "capa oficial en vivo"}}
        datos_b = {"tratamiento": {"value": "Desarrollo (Bajo)"},
                   "__globales__": {"fuente_pot": "capa oficial en vivo"}}
        c = dh.clasificar_cambio("tratamiento", datos_a, datos_b)
        self.assertTrue(c["cambio"])
        self.assertEqual(c["clase"], dh.UNEXPLAINED_CONFLICT)

    # §AP 6: fuente no disponible no se sustituye en silencio
    def test_fuente_no_disponible_no_se_reemplaza_en_silencio(self):
        datos_a = {"estrato": {"value": "4"}, "__globales__": {}}
        datos_b = {"estrato": {"value": None, "motivo": "la capa oficial no respondió"}}
        c = dh.clasificar_cambio("estrato", datos_a, datos_b)
        self.assertTrue(c["cambio"])
        self.assertEqual(c["clase"], dh.SOURCE_UNAVAILABLE)
        self.assertIn("no está en la versión más reciente", c["motivo"])


class TestHashMaestro(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.modelo = _json("EXECUTIVE_DOCUMENT_MODEL.json")
        cls.hashes = _json("MASTER_HASH.json")

    # §AP 13
    def test_cambia_al_cambiar_cualquier_hecho_material(self):
        base = dm.master_hash(self.modelo)
        for ruta, valor in ((("valuation", "consolidado"), 1),
                            (("canonical_property_identity", "nupre"), "OTRO"),
                            (("urban_context", "tratamiento"), "OTRO")):
            import copy
            m = copy.deepcopy(self.modelo)
            m[ruta[0]][ruta[1]] = valor
            self.assertNotEqual(dm.master_hash(m), base,
                                f"el hash maestro no cambió al alterar {ruta}")

    # §AP 14
    def test_reproducible_con_el_mismo_manifest(self):
        # Los artefactos de `dictus_2/` pertenecen al esquema 1.0.0 del manifest: DICTUS
        # 2.0B cambió el esquema (1.1.0, con el estado canónico de corrida) y su
        # conjunto vigente es `dictus_2b/`, verificado por
        # `tests/test_dictus_20b_integracion.py`. Aquí se comprueba el determinismo de
        # este conjunto histórico sin exigirle el esquema nuevo.
        if self.hashes.get("master_manifest_version") != dm.MASTER_MANIFEST_VERSION:
            self.skipTest("artefactos del esquema anterior: el conjunto vigente es dictus_2b/")
        copia = json.loads(json.dumps(self.modelo))
        self.assertEqual(dm.master_hash(copia), dm.master_hash(self.modelo))
        self.assertEqual(self.hashes["master_hash"], dm.master_hash(self.modelo))

    # §AP 15
    def test_pdf_sha_no_es_el_hash_maestro(self):
        self.assertNotEqual(self.hashes["master_hash"], self.hashes["pdf_binary_sha256"])
        self.assertEqual(len(self.hashes["pdf_binary_sha256"]), 64)
        self.assertIn("pdf_binary_sha256", self.hashes)
        self.assertTrue(self.hashes["verify"]["match"])

    def test_un_solo_hash_maestro_visible_en_el_cuerpo_ejecutivo(self):
        paginas = _texto_paginas(6)
        apariciones = " ".join(paginas).count("DICTUS_MASTER_HASH")
        self.assertGreaterEqual(apariciones, 6, "el sello debe repetirse en las 6 páginas")
        self.assertNotIn(str(self.hashes["pdf_binary_sha256"])[:24], " ".join(paginas),
                         "el hash del PDF no se imprime en el cuerpo ejecutivo")


class TestEjecutivoImpreso(unittest.TestCase):
    """§AQ: lo que un banco, un comprador y un auditor deben poder leer."""

    @classmethod
    def setUpClass(cls):
        if not PDF.exists():
            raise unittest.SkipTest("falta el PDF ejecutivo")
        cls.paginas = _texto_paginas(6)
        cls.todo = " ".join(cls.paginas)

    def test_primera_pagina_contiene_la_decision(self):
        p1 = self.paginas[0]
        for obligatorio in ("DECISIÓN SOBRE EL INMUEBLE", "Estado general",
                            "Hallazgos que condicionan la decisión",
                            "SELLO GLOBAL DE TRAZABILIDAD", "AFECTA A", "Acción:"):
            self.assertIn(obligatorio, p1, f"falta en la página 1: {obligatorio}")

    def test_cada_hallazgo_indica_a_quien_afecta(self):
        p1 = self.paginas[0]
        self.assertGreaterEqual(p1.count("AFECTA A"), 3,
                                "los hallazgos materiales deben declarar actores afectados")
        for actor in ("COMPRADOR", "VENDEDOR", "INMOBILIARIA"):
            self.assertIn(actor, p1)

    def test_altura_no_se_imprime_como_hecho(self):
        for frase in ("Hasta 8 pisos", "Hasta 11 pisos", "8 pisos (capa oficial",
                      "11 pisos (capa oficial"):
            self.assertNotIn(frase, self.todo,
                             f"la altura se imprimió como hecho teniendo conflicto: {frase}")
        self.assertIn("CONFLICTO HISTÓRICO", self.todo)

    def test_pot_distingue_destino_y_uso(self):
        p4 = self.paginas[3]
        self.assertIn("Destino económico (catastro)", p4)
        self.assertIn("Uso / actividad POT", p4)
        self.assertIn("no es el uso normativo del POT", p4)

    def test_lista_de_screening_son_las_reales_y_uiaf_no_es_columna(self):
        """§O/§P/§Q: las columnas son las listas REALMENTE consultadas y UIAF no es lista."""
        p3 = self.paginas[2]
        # La cabecera de la matriz son las listas usadas (dinámicas desde el propio
        # dictamen), no una lista fija del renderer.
        cabecera = p3.split("RESULTADO")[0]
        for lista in ("ONU", "OFAC SDN", "UKSL"):
            self.assertIn(lista, cabecera, f"falta la columna de lista {lista}")
        self.assertNotIn("UIAF", cabecera, "UIAF/SIREL no puede ser una columna de lista")
        # Se explica como canal regulatorio, no como dataset de screening.
        self.assertIn("UIAF/SIREL es el canal regulatorio de reporte", p3)
        self.assertIn("no es una lista de screening", p3)
        # Sin vocabulario prohibido (§R).
        for vetado in ("SANCIONADO", "LIMPIO", "ASEGURABLE", "CRÉDITO APROBADO",
                       "SEGURO APROBADO"):
            self.assertNotIn(vetado, p3)

    def test_sin_falsa_precision(self):
        for patron in ("$0", "$ 0", "0,0 %", "LTV 0", "N/D N/D"):
            self.assertNotIn(patron, self.todo, f"falsa precisión: {patron}")

    def test_sombras_declaradas_como_simulacion(self):
        p5 = self.paginas[4]
        self.assertIn("SIMULACIÓN GEOMÉTRICA", p5)
        self.assertIn("no sustituye una inspección física", p5)

    def test_equipamiento_permanece_con_categorias_reales(self):
        p5 = self.paginas[4]
        for cat in ("SALUD", "EDUCACION", "COMERCIO", "RECREACION"):
            self.assertIn(cat, p5, f"falta la categoría de equipamiento {cat}")

    def test_asoleamiento_permanece(self):
        self.assertIn("ASOLEAMIENTO Y PROYECCIÓN DE SOMBRAS", self.paginas[4])

    def test_valoracion_permanece_sin_cero(self):
        p6 = self.paginas[5]
        self.assertTrue("VALOR ESTIMADO" in p6 or "VALORACIÓN NO DISPONIBLE" in p6)
        self.assertNotIn("$0", p6)
        self.assertIn("Cómo se obtuvo el valor", p6)

    def test_provenance_permanece_en_lenguaje_comprensible(self):
        for p in self.paginas:
            self.assertIn("TRAZABILIDAD", p, "cada página debe declarar su trazabilidad")
        self.assertIn("INCLUIDA EN HASH MAESTRO DICTUS", self.todo)
        for tecnico in ("feature_id", "parser_version", "snapshot_sha", "query_hash",
                        "http://", "https://"):
            self.assertNotIn(tecnico, self.todo,
                             f"detalle técnico en el cuerpo ejecutivo: {tecnico}")

    def test_alcance_remite_al_anexo_h(self):
        """§AH: el capítulo de alcance sale del cuerpo y se remite al Anexo H."""
        self.assertNotIn("Declaracion de Alcance", self.todo)
        self.assertIn("Alcance y limitaciones del documento: ver Anexo H", self.todo)


class TestEstructuraDelDocumento(unittest.TestCase):

    def test_seis_paginas_ejecutivas_y_anexos(self):
        import pymupdf
        if not PDF.exists():
            self.skipTest("falta el PDF ejecutivo")
        with pymupdf.open(str(PDF)) as d:
            self.assertGreater(d.page_count, 6, "el expediente debe incluir anexos")
            self.assertEqual("ANEXOS", " ".join(list(d)[6].get_text().split())[:6].upper())
            ejecutivo = " ".join(" ".join(p.get_text().split()) for p in list(d)[:6])
            self.assertNotIn("Anexo A", ejecutivo.split("TRAZABILIDAD")[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)

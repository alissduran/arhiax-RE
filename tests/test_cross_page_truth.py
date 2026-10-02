# -*- coding: utf-8 -*-
"""BLOCK 1 · PROPAGACIÓN CRUZADA P1 · P4 · P5 · P6 — prueba BLOQUEANTE (offline).

La auditoría midió, sobre el Golden, **0 divergencias de VALOR** y 6 de ESTADO. Esta
prueba fija las dos reglas:

  · el VALOR que la escalera resuelve es el MISMO en todas las páginas donde el atributo
    se imprime (una sola verdad proyectada);
  · la DIVERGENCIA DE ESTADO solo puede provenir de la verdad única del atributo: no se
    admite que la misma corrida imprima dos estados distintos del mismo atributo.

Se ejerce sobre las SECCIONES REALES del render, recalculadas offline desde el run state
y el manifest del Golden (sin red y sin escribir nada).
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))

import attribute_truth as at  # noqa: E402
import dictus_historia as dh  # noqa: E402
import dictus_secciones as dst  # noqa: E402

GOLDEN = ROOT / "docs" / "forensics" / "040-646406" / "dictus_2b"
RUN_STATE = GOLDEN / "DICTUS_RUN_STATE_040-646406.json"
MANIFEST = GOLDEN / "DICTUS_MANIFEST_040-646406.json"

# Atributos comparados entre páginas por su CLAVE canónica (nunca por cercanía de texto):
# dos etiquetas parecidas pueden ser atributos distintos (`coordenada` ≠ `binding_geometria`).
CLAVES = ("barrio", "localidad", "destino_economico", "uso_pot", "tratamiento",
          "altura_normativa", "estrato", "coordenada", "remocion", "riesgo")


def _valor_en_urbano(secciones, etiqueta):
    for fila in (secciones.get("urbano") or {}).get("filas") or []:
        if fila.get("etiqueta") == etiqueta:
            return fila.get("valor"), fila.get("estado")
    return None, None


def _valor_en_entorno(secciones, etiqueta):
    for fila in ((secciones.get("entorno") or {}).get("accesibilidad") or []):
        if isinstance(fila, (list, tuple)) and len(fila) >= 2 and fila[0] == etiqueta:
            return fila[1]
    return None


class TestCrossPageTruth(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not (RUN_STATE.exists() and MANIFEST.exists()):
            raise unittest.SkipTest("no están los artefactos del Golden")
        cls.rs = json.loads(RUN_STATE.read_text(encoding="utf-8"))
        cls.modelo = json.loads(MANIFEST.read_text(encoding="utf-8"))["modelo"]
        hist = dh.reclasificar_informe(
            cls.rs.get("historical_consistency") or {},
            dh.cargar_matriz_del_caso("040-646406"))
        cls.rs["historical_consistency"] = hist
        cls.registro = at.resolver_atributos(cls.rs, historial=hist, fecha="2026-10-01")
        at.aplicar_verdad_al_estado(cls.rs, cls.registro)
        cls.rs[at.CLAVE_RUN_STATE] = cls.registro
        cls.secciones = dst.desde_estado(cls.rs, cls.modelo, hist)

    def test_el_barrio_es_el_mismo_en_p1_p4_y_p5(self):
        ficha = self.registro["attributes"]["barrio"]
        valores = {
            "P1/P5(accesibilidad)": _valor_en_entorno(self.secciones, "Barrio / sector oficial"),
            "P4": _valor_en_urbano(self.secciones, "Barrio / sector oficial")[0],
        }
        distintos = {v for v in valores.values() if v is not None}
        self.assertEqual(len(distintos), 1, f"divergencia de valor entre páginas: {valores}")
        self.assertEqual(str(next(iter(distintos))), str(ficha["canonical_value"]))

    def test_la_localidad_es_la_misma_en_p4_y_p5(self):
        ficha = self.registro["attributes"]["localidad"]
        p4 = _valor_en_urbano(self.secciones, "Localidad / comuna")[0]
        p5 = _valor_en_entorno(self.secciones, "Localidad")
        self.assertEqual(str(p4), str(p5))
        self.assertEqual(str(p4), str(ficha["canonical_value"]))

    def test_cero_divergencias_de_valor_entre_paginas(self):
        """El valor CANÓNICO que la fila proyecta es el de la verdad única, en todas las
        secciones donde el atributo se imprime (la FORMA impresa puede diferir: «Hasta 11
        pisos» es la forma de 11)."""
        divergencias = []
        for seccion in ("urbano", "entorno"):
            bloque = self.secciones.get(seccion) or {}
            for fila in (bloque.get("filas") or []):
                clave = fila.get("atributo_clave")
                if not clave or "valor_canonico" not in fila:
                    continue
                esperado = (self.registro["attributes"].get(clave) or {}).get("canonical_value")
                if fila["valor_canonico"] != esperado:
                    divergencias.append((seccion, clave, fila["valor_canonico"], esperado))
        self.assertEqual(divergencias, [], f"divergencias de valor: {divergencias}")

    def test_el_estado_impreso_sale_de_la_verdad_unica(self):
        for clave in CLAVES:
            esperado = at.estado_de_coherencia(self.registro, clave)
            if esperado is None:
                continue
            for fila in ((self.secciones.get("urbano") or {}).get("filas") or []):
                if fila.get("atributo_clave") == clave and fila.get("estado"):
                    self.assertEqual(fila["estado"], esperado,
                                     f"{clave}: la página y la verdad única discrepan")

    def test_las_filas_urbanas_declaran_su_clave_canonica(self):
        filas = (self.secciones.get("urbano") or {}).get("filas") or []
        self.assertTrue(filas)
        con_clave = [f for f in filas if f.get("atributo_clave")]
        self.assertTrue(con_clave, "las filas tienen que declarar su atributo canónico")


if __name__ == "__main__":
    unittest.main()

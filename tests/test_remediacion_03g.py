# -*- coding: utf-8 -*-
"""
Remediation 03G — EXACT IDENTITY RECOVERY (precedencia del resolver).

Golden case 040-646406:
  codigo_catastral = 080010103000010040001908040002
  nupre            = AFT0005BOHA

Bug corregido: el prefix/fuzzy fallback ya no puede impedir que se ejecute el
identificador exacto NUPRE. Los identificadores EXACTOS se agotan ANTES del fuzzy.
"""
import sys
import unittest
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
API = ROOT / "api"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(API))

_CODIGO = "080010103000010040001908040002"
_NUPRE = "AFT0005BOHA"


def _feature(nacional=None, homologado=None):
    props = {}
    if nacional:
        props["numero_predial_nacional"] = nacional
    if homologado:
        props["codigo_homologado"] = homologado
    return {"properties": props}


class TestPrecedenciaResolver(unittest.TestCase):
    """#3/#4/#5/#6: exactos primero, fuzzy solo si ningún exacto resuelve."""

    def _run(self, code_features, nupre_features, prefix_features):
        import catastro_predio as cp
        cp._CACHE.clear()
        original = cp._query_capa
        llamadas = []

        def stub(base, capa, where, out_fields="*", max_features=5,
                 return_geometry=False, timeout=cp.TIMEOUT):
            llamadas.append(where)
            if where == f"numero_predial_nacional='{_CODIGO}'":
                return {"disponible": True, "features": code_features,
                        "total": len(code_features), "error": None}
            if where == f"codigo_homologado='{_NUPRE}'":
                return {"disponible": True, "features": nupre_features,
                        "total": len(nupre_features), "error": None}
            if where.startswith("numero_predial_nacional LIKE"):
                return {"disponible": True, "features": prefix_features,
                        "total": len(prefix_features), "error": None}
            return {"disponible": False, "features": [], "total": 0,
                    "error": "where inesperado: " + where}

        try:
            cp._query_capa = stub
            r = cp.consultar_predio_por_codigo(_CODIGO, _NUPRE)
            return r, llamadas
        finally:
            cp._query_capa = original
            cp._CACHE.clear()

    def test_exact_nupre_resuelve_sin_ser_saltado_por_prefix(self):
        """#4: exact code=[] + prefix=5 + exact NUPRE=1 => EXACT por NUPRE."""
        r, llamadas = self._run(
            code_features=[],
            nupre_features=[_feature(homologado=_NUPRE)],
            prefix_features=[_feature(nacional=f"{_CODIGO[:24]}00000{i}") for i in range(5)],
        )
        self.assertEqual(r["resolution_status"], "EXACT")
        self.assertEqual(r["resolution_method"], "nupre")
        self.assertEqual(r["nupre"], _NUPRE)
        # La query exact NUPRE se ejecutó y NO fue saltada por el prefix.
        self.assertIn(f"codigo_homologado='{_NUPRE}'", llamadas)
        # El prefix NO se ejecutó (porque un exacto ya resolvió).
        self.assertFalse(any("LIKE" in w for w in llamadas))
        # Trace registra la evidencia por query.
        self.assertTrue(any(t.get("query") == "B_exact_nupre" for t in r["resolution_trace"]))

    def test_sin_exactos_prefix_multiple_es_ambiguo(self):
        """#5: exact code=[] + exact NUPRE=[] + prefix=5 => AMBIGUOUS."""
        r, llamadas = self._run(
            code_features=[],
            nupre_features=[],
            prefix_features=[_feature(nacional=f"{_CODIGO[:24]}00000{i}") for i in range(5)],
        )
        self.assertEqual(r["resolution_status"], "AMBIGUOUS")
        self.assertFalse(r["disponible"])
        # El prefix sí se ejecutó (ningún exacto resolvió).
        self.assertTrue(any("LIKE" in w for w in llamadas))

    def test_exact_codigo_tiene_precedencia_sobre_nupre(self):
        """A (código) gana sobre B (NUPRE) cuando ambos resuelven."""
        r, _ = self._run(
            code_features=[_feature(nacional=_CODIGO, homologado="OTRO_NUPRE")],
            nupre_features=[_feature(homologado=_NUPRE)],
            prefix_features=[],
        )
        self.assertEqual(r["resolution_status"], "EXACT")
        self.assertEqual(r["resolution_method"], "codigo_catastral")
        self.assertEqual(r["numero_predial_nacional"], _CODIGO)

    def test_trace_registra_fuente_disponible(self):
        r, _ = self._run(
            code_features=[_feature(nacional=_CODIGO)],
            nupre_features=[],
            prefix_features=[],
        )
        for t in r["resolution_trace"]:
            if t.get("query") in ("A_exact_codigo", "B_exact_nupre", "E_prefix_codigo"):
                self.assertIn("source_disponible", t)
                self.assertIn("candidate_count", t)


class TestGoldenVivo(unittest.TestCase):
    """#7: test network del golden. NO skip silencioso: distingue
    SOURCE_UNAVAILABLE de NO_MATCH. (Ejecutar con acceso al servicio BAQ)."""

    @pytest.mark.network
    def test_catastro_predio_vivo_040_646406(self):
        import catastro_predio as cp
        cp._CACHE.clear()
        r = cp.consultar_predio_por_codigo(_CODIGO, _NUPRE)
        trace = r.get("resolution_trace") or []
        # Registrar evidencia (no ocultar).
        for t in trace:
            print(f"[03G][TRACE] {t}")

        _alguna_fuente = any(t.get("source_disponible") for t in trace)
        if not _alguna_fuente:
            # Fuente no disponible: no es "no match", es fallo de servicio.
            self.fail("SOURCE_UNAVAILABLE: el servicio catastral de Barranquilla "
                      "no respondió (ninguna query source_disponible=True)")

        if r.get("disponible"):
            self.assertEqual(r["resolution_status"], "EXACT")
            self.assertIn(r["resolution_method"], ("codigo_catastral", "nupre"))
        else:
            # Respondió pero sin match exacto: distinguir de SOURCE_UNAVAILABLE.
            self.fail(f"NO_MATCH: resolution_status={r.get('resolution_status')} "
                      f"(error={r.get('error')})")


if __name__ == "__main__":
    unittest.main()

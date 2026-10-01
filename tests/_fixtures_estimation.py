# -*- coding: utf-8 -*-
"""Fixtures compartidas de los tests del DICTUS ESTIMATION ENGINE v1.0 (Fase 2).

Construye entradas REALES en la forma del contrato de `api/estimation.py`, con
procedencia COMPLETA (source_id, proveedor, fecha, referencia, sha256) tal como la
exige el Source Pack. Ninguna fixture inventa una fuente: las que no declaran
procedencia existen a propósito para probar que se RECHAZAN.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "api")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import estimation as est  # noqa: E402

HOY = date(2026, 7, 1)
GENERADO = "2026-07-01T00:00:00+00:00"


def procedencia(n: int, fecha: str = "2026-05-01") -> dict:
    """Procedencia estructurada COMPLETA de una fuente externa citada."""
    return {"source_id": f"SRC-{n:03d}", "proveedor": f"Portal inmobiliario {n}",
            "fecha": fecha, "referencia": f"anuncio-{n}", "sha256": f"{n:064d}"}


def comparable(n: int, value_m2: float = 5_000_000, *, tipologia: str = "APARTAMENTO",
               fecha: str = "2026-05-01", area_m2: float = 80.0, **extra) -> dict:
    """Comparable externo con procedencia completa (pasa la criba por defecto)."""
    d = {"comparable_id": f"C{n}", "tipologia": tipologia, "value_m2": value_m2,
         "area_m2": area_m2, "fecha": fecha, "origen_tipo": "EXTERNAL_SOURCE",
         "provenance": procedencia(n, fecha)}
    d.update(extra)
    return d


def comparable_sin_procedencia(n: int, value_m2: float = 5_000_000, **extra) -> dict:
    """Comparable que AFIRMA ser externo pero NO aporta procedencia: debe RECHAZARSE."""
    d = {"comparable_id": f"CSP{n}", "tipologia": "APARTAMENTO", "value_m2": value_m2,
         "area_m2": 80.0, "fecha": "2026-05-01", "origen_tipo": "EXTERNAL_SOURCE"}
    d.update(extra)
    return d


def comparables_validos(n: int = 9, base: float = 5_000_000, paso: float = 30_000,
                        fecha: str = "2026-05-01") -> list:
    """`n` comparables externos con dispersión baja y vigencia reciente."""
    return [comparable(i, base + i * paso, fecha=fecha) for i in range(1, n + 1)]


def modelo_calibrado(**overrides) -> dict:
    """Modelo calibrado que CUMPLE el contrato §16 (todos los campos declarados)."""
    m = {"city": "barranquilla", "sector": "Alto Prado", "neighborhood": "Alto Prado",
         "property_type": "APARTAMENTO", "regime": "PH", "area_band": "70-90",
         "estrato": 5, "central_value_m2": 5_400_000, "low_value_m2": 4_800_000,
         "high_value_m2": 6_100_000, "effective_from": "2026-01-01",
         "effective_to": "2026-12-31", "reference_period": "2026-Q1", "sample_size": 180,
         "calibration_error": 0.09, "model_version": "cal-2026.1",
         "provenance": {"entity": "modelo interno calibrado", "referencia": "cal-2026.1",
                        "fecha": "2026-01-01"},
         "hash": "a" * 64}
    m.update(overrides)
    return m


def entrada(*, comparables=None, con_calibrado: bool = False, **extra) -> dict:
    """Entrada COMPLETA: identidad resuelta, ubicación oficial, área y tipología.

    Sólo varía el soporte económico, que es lo que cada prueba quiere aislar.
    """
    e = {
        "identidad": {"resuelta": True, "origen_tipo": "COMPUTED_FROM_SOURCES",
                      "fuentes": [procedencia(1), procedencia(2)]},
        "ubicacion": {"utilizable": True, "status": "VERIFIED_OFFICIAL"},
        "area": {"valor_m2": 82.5, "origen_tipo": "EXTERNAL_SOURCE",
                 "provenance": procedencia(9)},
        "tipologia": {"valor": "APARTAMENTO", "status": "VERIFIED_REGISTRAL"},
        "comparables": list(comparables) if comparables is not None else [],
        "contexto": {"ciudad": "barranquilla", "sector": "Alto Prado", "estrato": 5},
    }
    if con_calibrado:
        e["modelo_calibrado"] = modelo_calibrado()
    e.update(extra)
    return e


def estimar(e: dict, **kw) -> dict:
    """Ejecuta el motor con fecha fija (resultados reproducibles)."""
    kw.setdefault("generado_en", GENERADO)
    kw.setdefault("hoy", HOY)
    return est.estimar(e, **kw)

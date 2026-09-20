# -*- coding: utf-8 -*-
"""
ARHIAX RE — Estimación de costo del servicio profesional de avalúo (03F.1).

Contrato vacío/configurable. NO emite cifras hasta existir una fuente histórica
o documentada válida; la investigación forense (03F y 03F.1) NO encontró la
regla histórica de "cuánto cuesta contratar el avalúo profesional".

El costo del servicio profesional es INDEPENDIENTE de la autorización de
valoración de ARHIAX (valuation_authorization.allowed): es válido recomendar el
avalúo profesional aunque la estimación de mercado de ARHIAX esté BLOQUEADA.
"""

from typing import Any, Dict

# Resultado de la investigación histórica (sin regla documentada).
APPRAISAL_COST_HISTORICAL_RULE = "NOT_FOUND"


def build_appraisal_cost_estimate() -> Dict[str, Any]:
    """Devuelve un contrato vacío (available=False, sin cifras).

    Campos:
      available    bool      — True solo cuando exista una fuente válida.
      low_cop      int|None  — cota inferior orientativa (COP).
      central_cop  int|None  — cota central orientativa (COP).
      high_cop     int|None  — cota superior orientativa (COP).
      method       str|None  — metodología (una vez exista fuente).
      source       str|None  — fuente de la regla.
      source_date  str|None  — fecha de la fuente.
      assumptions  list[str] — supuestos documentados.
    """
    return {
        "available": False,
        "low_cop": None,
        "central_cop": None,
        "high_cop": None,
        "method": None,
        "source": None,
        "source_date": None,
        "assumptions": [],
    }

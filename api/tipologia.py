# -*- coding: utf-8 -*-
"""Tipología del predio (03I.2 · D-2) — función PURA y testeable.

USO ≠ TIPOLOGÍA. El destino económico catastral («Habitacional») describe un USO; la
tipología describe QUÉ es el inmueble (apartamento en propiedad horizontal, casa,
bodega, lote). Confundirlos produjo dos defectos reales en el mismo dictamen:

  · el capítulo 01 mostraba «Uso Habitacional (Según catastro)» como tipología,
    tapando la evidencia registral de propiedad horizontal del CTL, y
  · el gate de contexto de mercado cerraba la valoración por «tipología no
    verificada (requiere VERIFIED_REGISTRAL/CATASTRAL)», dejando el dictamen sin
    estimación económica.

REGLA: un uso catastral solo manda cuando CONTRADICE la propiedad horizontal
(industrial, bodega, comercial, oficina, lote, garaje). Si el destino es residencial
o vacío, manda la evidencia de PH del registro/CTL; y si no hay evidencia de PH, se
declara el uso COMO USO (nunca como tipología).
"""

from __future__ import annotations

from typing import Optional

TIPOLOGIA_SIN_CONSULTA = "PENDIENTE DE VERIFICACION (Requiere consulta catastral)"
TIPOLOGIA_BODEGA = "Bodega -- Uso Industrial (No Propiedad Horizontal)"
TIPOLOGIA_PH_CATASTRAL = "Apartamento -- Propiedad Horizontal (condición catastral)"
TIPOLOGIA_PH_CTL = "Apartamento -- Propiedad Horizontal (inferido del CTL)"
TIPOLOGIA_PH_DEMO = "Apartamento -- Propiedad Horizontal (NO VIS)"

_USOS_NO_RESIDENCIALES = ("COMERCIAL", "OFICINA", "LOTE", "GARAJE")


def tipologia_de_predio(*, destino_economico: Optional[str],
                        descripcion_ctl: Optional[str] = None,
                        condicion_juridica: Optional[str] = None,
                        condicion_source: Optional[str] = None,
                        fuentes_tematicas=(),
                        predio_resuelto: bool = False,
                        es_caso_demo: bool = False,
                        tiene_ctl: bool = True) -> str:
    """Devuelve la tipología del inmueble (texto único del dictamen)."""
    _desc = str(descripcion_ctl or "").upper()
    _dest = str(destino_economico or "").upper()

    if "INDUSTRIAL" in _dest or "BODEGA" in _desc:
        return TIPOLOGIA_BODEGA
    if predio_resuelto and _dest and ("COMERCIAL" in _dest or "OFICINA" in _dest
                                      or "LOTE" in _dest or "GARAJE" in _dest):
        return f"Uso {destino_economico} (Según catastro)"

    if "Propiedad Horizontal" in str(condicion_juridica or ""):
        if condicion_source and condicion_source in tuple(fuentes_tematicas):
            return TIPOLOGIA_PH_CATASTRAL
        return TIPOLOGIA_PH_CTL
    if es_caso_demo and not tiene_ctl:
        return TIPOLOGIA_PH_DEMO
    if predio_resuelto and destino_economico:
        # Sin evidencia de PH: el uso es lo único disponible y se declara COMO USO.
        return f"Uso {destino_economico} (Según catastro)"
    return TIPOLOGIA_SIN_CONSULTA

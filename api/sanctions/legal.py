# -*- coding: utf-8 -*-
"""Mapeo legal declarado (§27).

La Circular Externa 100-000020 del 2 de julio de 2026 es la Circular Básica
Jurídica (CBJ) vigente de referencia del proyecto. PERO los numerales concretos
NO se citan hasta verificarlos contra el PDF oficial vigente.

Regla de implementación: si `numeral_verified` es False, el numeral NO se
imprime en el dictamen; solo se cita el documento y el capítulo temático.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

CBJ_2026 = "Circular Externa 100-000020 del 2 de julio de 2026 (CBJ — Supersociedades)"


@dataclass(frozen=True)
class RequirementMapping:
    requirement_id: str
    source_document: str
    chapter: str
    numeral: str
    numeral_verified: bool
    text_summary: str
    verified_at: Optional[str] = None

    def cita(self) -> str:
        """Cita imprimible: el numeral SOLO si está verificado."""
        base = f"{self.source_document} ({self.chapter})"
        if self.numeral_verified and self.numeral:
            return f"{base}, numeral {self.numeral}"
        return base


# El estado por defecto es NO VERIFICADO: los numerales del proyecto (9.14.1,
# 9.15.1, 9.17, 9.19, 9.20, 9.22) no fueron confrontados con el PDF oficial en
# esta sesión, así que NO se imprimen.
_MAPPINGS: Tuple[RequirementMapping, ...] = (
    RequirementMapping(
        requirement_id="SAG_IDENTIFICACION_CONTRAPARTES",
        source_document=CBJ_2026, chapter="Cap. IX — identificación de contrapartes",
        numeral="9.14", numeral_verified=False,
        text_summary=("Debe identificarse a las contrapartes de la operación y "
                      "consultarlas contra listas restrictivas.")),
    RequirementMapping(
        requirement_id="SAG_LISTAS_VINCULANTES",
        source_document=CBJ_2026, chapter="Cap. IX — consulta de listas restrictivas",
        numeral="9.17", numeral_verified=False,
        text_summary=("Consulta de listas vinculantes; una coincidencia obliga a "
                      "debida diligencia intensificada y revisión humana.")),
    RequirementMapping(
        requirement_id="SAG_BENEFICIARIO_FINAL",
        source_document=CBJ_2026, chapter="Cap. IX — beneficiario final",
        numeral="9.15.1", numeral_verified=False,
        text_summary=("Identificación del beneficiario final de las personas jurídicas "
                      "(criterio de participación y regla subsidiaria).")),
    RequirementMapping(
        requirement_id="SAG_EVIDENCIA_TRAZABILIDAD",
        source_document=CBJ_2026, chapter="Cap. IX — conservación de evidencia",
        numeral="9.22", numeral_verified=False,
        text_summary=("Debe conservarse evidencia trazable de las verificaciones "
                      "realizadas, con versión de la fuente consultada.")),
    RequirementMapping(
        requirement_id="SAG_OPERACIONES_INUSUALES",
        source_document=CBJ_2026, chapter="Cap. IX — señales de alerta y reporte",
        numeral="9.19/9.20", numeral_verified=False,
        text_summary=("Identificación de operaciones inusuales/sospechosas y de las "
                      "señales de alerta aplicables.")),
    RequirementMapping(
        requirement_id="SAG_SUJETO_OBLIGADO",
        source_document=CBJ_2026, chapter="Cap. IX — sujetos obligados y régimen",
        numeral="", numeral_verified=False,
        text_summary=("La determinación de si una parte es sujeto obligado (y con qué "
                      "régimen) es una decisión jurídica; el dictamen no la asume.")),
    RequirementMapping(
        requirement_id="SAG_REPORTE_UIAF",
        source_document="Ley 526/1999 + canal UIAF (SIREL)",
        chapter="Reporte regulatorio (fuera del alcance de screening)",
        numeral="", numeral_verified=False,
        text_summary=("La presentación de reportes a la UIAF por el sujeto obligado se "
                      "atiende por el canal oficial; no es una lista de screening.")),
)

_BY_ID = {m.requirement_id: m for m in _MAPPINGS}


def mapping(requirement_id: str) -> Optional[RequirementMapping]:
    return _BY_ID.get(requirement_id)


def cita(requirement_id: str) -> str:
    """Cita imprimible de un requisito (sin numeral si no está verificado)."""
    m = _BY_ID.get(requirement_id)
    if m is None:
        return CBJ_2026
    return m.cita()


def base_legal(*requirement_ids: str) -> str:
    """Compone una base legal imprimible a partir de requisitos."""
    citas = []
    for rid in requirement_ids:
        c = cita(rid)
        if c and c not in citas:
            citas.append(c)
    return " + ".join(citas) if citas else CBJ_2026


def all_mappings() -> Tuple[RequirementMapping, ...]:
    return _MAPPINGS


def unverified_numerals() -> Tuple[str, ...]:
    return tuple(m.numeral for m in _MAPPINGS if m.numeral and not m.numeral_verified)

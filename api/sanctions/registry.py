# -*- coding: utf-8 -*-
"""SourceRegistry — catálogo auditable de fuentes y su estado (§6/§7/§8/§9/§10).

Reglas duras:
  * Solo fuentes OFICIALES entran como fuente de screening vigente.
  * UK: la fuente vigente es `UK_SANCTIONS_LIST` (FCDO, XML). El antiguo
    `ConList.xml` de OFSI queda como HISTORICAL_SOURCE (reproducibilidad).
  * UIAF/SIREL NO es fuente de screening: es REGULATORY_REPORTING y queda
    OUT_OF_SCOPE_FOR_SCREENING en 03S.1 (no se implementa SIREL).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from .contracts import (
    ACQ_FILE, ACQ_LIVE, ACQ_OUT_OF_SCOPE, CAT_ENFORCEMENT, CAT_PEP,
    CAT_REGULATORY_REPORTING, CAT_SANCTIONS,
)


@dataclass(frozen=True)
class SourceDefinition:
    source_id: str
    authority: str
    dataset_name: str
    category: str
    official_url: str
    current_or_historical: str          # CURRENT | HISTORICAL
    formato: str
    parser: str
    parser_version: str
    acquisition_policy: str
    refresh_policy: str
    cobertura: str
    notes: str = ""

    @property
    def es_screening(self) -> bool:
        """¿Cuenta como evidencia de screening de sanciones?"""
        return (self.category in (CAT_SANCTIONS, CAT_ENFORCEMENT)
                and self.current_or_historical == "CURRENT"
                and self.acquisition_policy != ACQ_OUT_OF_SCOPE)


# ── Fuentes vigentes (CURRENT) ───────────────────────────────────────────────
UN_CONSOLIDATED = SourceDefinition(
    source_id="UN_CONSOLIDATED",
    authority="United Nations Security Council",
    dataset_name="Security Council Consolidated List",
    category=CAT_SANCTIONS,
    official_url="https://scsanctions.un.org/resources/xml/en/consolidated.xml",
    current_or_historical="CURRENT", formato="xml", parser="onu_xml",
    parser_version="onu_xml/1.0",
    acquisition_policy=ACQ_LIVE,
    refresh_policy="diaria (el feed oficial se actualiza sin aviso; se versiona por SHA-256)",
    cobertura=("Personas y entidades designadas por el Consejo de Seguridad (todas las "
               "resoluciones consolidadas). NO cubre listas nacionales."),
)

OFAC_SDN = SourceDefinition(
    source_id="OFAC_SDN",
    authority="US Department of the Treasury — OFAC (Sanctions List Service)",
    dataset_name="Specially Designated Nationals and Blocked Persons (SDN)",
    category=CAT_SANCTIONS,
    official_url="https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.XML",
    current_or_historical="CURRENT", formato="xml", parser="ofac_sdn_xml",
    parser_version="ofac_sdn_xml/1.0",
    acquisition_policy=ACQ_LIVE,
    refresh_policy="diaria (publicación OFAC); versionado por SHA-256",
    cobertura=("Lista SDN: sancionados y bloqueados por OFAC. NO incluye las listas "
               "consolidadas no-SDN (ver OFAC_NON_SDN)."),
)

OFAC_NON_SDN = SourceDefinition(
    source_id="OFAC_NON_SDN",
    authority="US Department of the Treasury — OFAC (Sanctions List Service)",
    dataset_name="Consolidated Non-SDN Lists (SSI, NS-CMIC, FSE, ...)",
    category=CAT_SANCTIONS,
    official_url="https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/CONS_ADVANCED.XML",
    current_or_historical="CURRENT", formato="xml", parser="ofac_non_sdn_xml",
    parser_version="ofac_non_sdn_xml/1.0",
    acquisition_policy=ACQ_LIVE,
    refresh_policy="diaria; versionado por SHA-256",
    cobertura=("Listas no-SDN consolidadas de OFAC (nivel avanzado). Si NO se consulta, "
               "no puede afirmarse 'OFAC completo'."),
)

UK_SANCTIONS_LIST = SourceDefinition(
    source_id="UK_SANCTIONS_LIST",
    authority="UK FCDO / OFSI (UK Sanctions List)",
    dataset_name="UK Sanctions List (designaciones del Reino Unido)",
    category=CAT_SANCTIONS,
    official_url="https://sanctionslist.fcdo.gov.uk/docs/UK-Sanctions-List.xml",
    current_or_historical="CURRENT", formato="xml", parser="uk_sanctions_list_xml",
    parser_version="uk_sanctions_list_xml/1.0",
    acquisition_policy=ACQ_LIVE,
    refresh_policy=("diaria; el listado se republica con nuevo URL de medio en gov.uk, "
                    "por lo que la URL viva del FCDO es la estable"),
    cobertura=("Lista única de sanciones del Reino Unido (designaciones FCDO/OFSI). "
               "Sustituye al consolidated list del Tesoro (ConList.xml)."),
    notes="Migración 03S.1: la fuente vigente es la UK Sanctions List, no ConList.xml.",
)

# ── Fuentes históricas (solo reproducibilidad) ───────────────────────────────
UK_OFSI_CONLIST_HISTORICAL = SourceDefinition(
    source_id="UK_OFSI_CONLIST_HISTORICAL",
    authority="UK HM Treasury / OFSI (legado)",
    dataset_name="OFSI Consolidated List (ConList.xml) — histórico",
    category=CAT_SANCTIONS,
    official_url="https://ofsistorage.blob.core.windows.net/publishlive/2022format/ConList.xml",
    current_or_historical="HISTORICAL", formato="xml", parser="uk_ofsi_legacy_xml",
    parser_version="uk_ofsi_legacy_xml/1.0",
    acquisition_policy=ACQ_FILE,
    refresh_policy="no se refresca: congelada (sustituida por UK_SANCTIONS_LIST)",
    cobertura="Solo para reproducir dictámenes históricos. PROHIBIDA como fuente vigente.",
    notes="03S.1: prohibido obtener UK desde esta fuente en ejecución productiva.",
)

# ── Fuera de alcance de screening (§10/§11) ──────────────────────────────────
UIAF_SIREL = SourceDefinition(
    source_id="UIAF_SIREL",
    authority="UIAF (Unidad de Información y Análisis Financiero) — Colombia",
    dataset_name="Reporte de operaciones / listas cautelares (SIREL)",
    category=CAT_REGULATORY_REPORTING,
    official_url="https://www.uiaf.gov.co",
    current_or_historical="CURRENT", formato="web", parser="none",
    parser_version="",
    acquisition_policy=ACQ_OUT_OF_SCOPE,
    refresh_policy="n/a (canal oficial autenticado)",
    cobertura=("NO es una lista de screening. Es un canal de REPORTE regulatorio del "
               "sujeto obligado; su consulta/entrega se hará en 03S.x Regulatory Reporting."),
    notes="FUERA DE ALCANCE en 03S.1: nunca se imprime como columna ni como resultado.",
)

EU_CONSOLIDATED = SourceDefinition(
    source_id="EU_CONSOLIDATED",
    authority="European Union — DG FISMA / FSF",
    dataset_name="EU Consolidated Financial Sanctions List (XML 1.1)",
    category=CAT_SANCTIONS,
    official_url=("https://webgate.ec.europa.eu/fsd/fsf/public/files/"
                  "xmlFullSanctionsList_1_1/content"),
    current_or_historical="CURRENT", formato="xml", parser="ue_xml",
    parser_version="ue_xml/1.0",
    acquisition_policy=ACQ_FILE,
    refresh_policy="manual/institucional (el portal bloquea la descarga automatizada)",
    cobertura="Lista consolidada de sanciones de la UE. En 03S.1 queda OPCIONAL.",
    notes="03S.1: OPCIONAL/OFFICIAL_FILE_REQUIRED — no bloquea el cierre del slice.",
)

PEP_COLOMBIA = SourceDefinition(
    source_id="PEP_COLOMBIA",
    authority="Registros oficiales de servidores públicos (CO)",
    dataset_name="Personas Expuestas Políticamente (PEP)",
    category=CAT_PEP,
    official_url="",
    current_or_historical="CURRENT", formato="", parser="none", parser_version="",
    acquisition_policy=ACQ_OUT_OF_SCOPE,
    refresh_policy="n/a",
    cobertura="PEP avanzado queda fuera de 03S.1/03S.1A (se declara, no se simula).",
)

_REGISTRY: Dict[str, SourceDefinition] = {
    s.source_id: s for s in (
        UN_CONSOLIDATED, OFAC_SDN, OFAC_NON_SDN, UK_SANCTIONS_LIST,
        UK_OFSI_CONLIST_HISTORICAL, UIAF_SIREL, EU_CONSOLIDATED, PEP_COLOMBIA,
    )
}

# Fuentes de screening que 03S.1 ejecuta (core).
CORE_SOURCE_IDS: Tuple[str, ...] = ("UN_CONSOLIDATED", "OFAC_SDN", "UK_SANCTIONS_LIST")
# Fuente opcional: si no se consulta, el dictamen NO puede decir "OFAC completo".
OPTIONAL_SOURCE_IDS: Tuple[str, ...] = ("OFAC_NON_SDN",)

# Alias legado (nombres internos 'onu'/'ofac'/'uk') -> source_id.
_LEGACY_ALIAS = {
    "onu": "UN_CONSOLIDATED",
    "ofac": "OFAC_SDN",
    "uk": "UK_SANCTIONS_LIST",
    "uk_ofsi": "UK_OFSI_CONLIST_HISTORICAL",
    "ue": "EU_CONSOLIDATED",
    "uiaf": "UIAF_SIREL",
    "pep": "PEP_COLOMBIA",
}


def get_source(source_id: str) -> Optional[SourceDefinition]:
    return _REGISTRY.get(source_id)


def resolve_source_id(key: str) -> Optional[str]:
    if key in _REGISTRY:
        return key
    return _LEGACY_ALIAS.get(str(key or "").lower())


def current_source_id(key: str) -> Optional[str]:
    """source_id VIGENTE para una clave (legado incluido).

    03S.1 (§9): `current_source_id('uk') == 'UK_SANCTIONS_LIST'`; el ConList.xml
    legado NO puede ser la fuente vigente de UK.
    """
    sid = resolve_source_id(key)
    src = _REGISTRY.get(sid or "")
    if src is None or not src.es_screening:
        return None
    if src.current_or_historical != "CURRENT":
        return None
    return src.source_id


def all_sources() -> Tuple[SourceDefinition, ...]:
    return tuple(_REGISTRY[k] for k in sorted(_REGISTRY))


def screening_sources() -> Tuple[SourceDefinition, ...]:
    return tuple(s for s in all_sources() if s.es_screening)


def out_of_scope_sources() -> Tuple[SourceDefinition, ...]:
    return tuple(s for s in all_sources() if not s.es_screening)


def cobertura_declarada(source_ids) -> str:
    """Cobertura REALMENTE consultada (§8): no se afirma 'OFAC completo' sin non-SDN."""
    ids = set(source_ids or ())
    partes = []
    if "UN_CONSOLIDATED" in ids:
        partes.append("ONU (lista consolidada del Consejo de Seguridad)")
    if "OFAC_SDN" in ids:
        partes.append("OFAC — SDN" + (" + listas no-SDN consolidadas"
                                      if "OFAC_NON_SDN" in ids else " (solo SDN)"))
    elif "OFAC_NON_SDN" in ids:
        partes.append("OFAC — solo listas no-SDN")
    if "UK_SANCTIONS_LIST" in ids:
        partes.append("UK Sanctions List (FCDO/OFSI)")
    if "EU_CONSOLIDATED" in ids:
        partes.append("UE consolidada")
    return "; ".join(partes)

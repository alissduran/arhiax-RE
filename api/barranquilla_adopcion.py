# -*- coding: utf-8 -*-
"""
ARHIAX RE — Resolver estático AUTORITATIVO de identidad (03G.1).

Segunda ruta de resolución exacta de identidad predial basada en el Anexo 1 de
adopción catastral de Barranquilla (Resolución GGCD 003 del 07/03/2025). No
depende de la disponibilidad del ArcGIS MapServer: es fallback AUTORITATIVO
(exacto), nunca un fallback espacial/bbox.

La fuente se mantiene como una copia local normalizada (versionada + hash), no
se descarga en cada Dictus. Nunca hardcodea un inmueble: las filas son datos.

Regla dura (03G.1):
  - SOLO coincidencia EXACTA de los identificadores declara VERIFIED_UNIT_IDENTITY.
  - NUNCA fuzzy para identidad verificada.
  - Si cualquier identificador contradice a otro => CONFLICT (no elegir uno).
  - `area_terreno` NO se confunde con el área privada del CTL.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional

_DATA_PATH = Path(__file__).resolve().parent / "data" / "barranquilla_adopcion_anexo1.json"

# Estado de resolución de la fuente estática.
STATUS_EXACT_3 = "EXACT_3"      # numero_predial + codigo_homologado + fmi coinciden
STATUS_EXACT_2 = "EXACT_2"
STATUS_EXACT_1 = "EXACT_1"
STATUS_NO_MATCH = "NO_MATCH"
STATUS_CONFLICT = "CONFLICT"


def _load() -> Dict[str, Any]:
    with open(_DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def _sha256_registros(registros) -> str:
    payload = json.dumps(registros, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _fmi_de_folio(folio) -> tuple:
    """'040-646406' -> ('040', '646406')."""
    s = str(folio or "").strip()
    partes = s.split("-")
    if len(partes) >= 2:
        return partes[0].strip(), partes[1].strip()
    return "", s


def _provenance(data: Dict[str, Any], registros) -> Dict[str, Any]:
    return {
        "source_name": data.get("source_name"),
        "source_url": data.get("source_url"),
        "resolution_number": data.get("resolution_number"),
        "resolution_date": data.get("resolution_date"),
        "downloaded_at": data.get("downloaded_at"),
        "version": data.get("version"),
        "sha256": _sha256_registros(registros),
    }


def consultar_adopcion(*, folio: Optional[str] = None,
                       numero_predial: Optional[str] = None,
                       codigo_homologado: Optional[str] = None) -> Dict[str, Any]:
    """Consulta el registro oficial de adopción por identificadores EXACTOS.

    Identificadores CORE (para VERIFIED_UNIT_IDENTITY): numero_predial,
    codigo_homologado (NUPRE) y fmi (del folio). `codigo_registral` (del folio)
    es un cross-check adicional: si contradice => CONFLICT.

    Devuelve:
      {disponible, match_status (EXACT_3/EXACT_2/EXACT_1/NO_MATCH/CONFLICT),
       registro, coincidencias, provenance}
    """
    data = _load()
    registros = data.get("registros") or []
    cod_reg, fmi = _fmi_de_folio(folio)

    def _idx(key: str, val) -> set:
        if not val:
            return set()
        v = str(val).strip()
        return {i for i, r in enumerate(registros) if str(r.get(key) or "").strip() == v}

    m_predial = _idx("numero_predial", numero_predial)
    m_homologado = _idx("codigo_homologado", codigo_homologado)
    m_fmi = _idx("fmi", fmi)
    m_reg = _idx("codigo_registral", cod_reg)

    coincidencias = {
        "numero_predial": sorted(m_predial),
        "codigo_homologado": sorted(m_homologado),
        "fmi": sorted(m_fmi),
        "codigo_registral": sorted(m_reg),
    }
    prov = _provenance(data, registros)

    core = {"numero_predial": m_predial, "codigo_homologado": m_homologado, "fmi": m_fmi}
    non_empty_core = {k: s for k, s in core.items() if s}
    # cross-check incluye codigo_registral
    all_sets = {**core, "codigo_registral": m_reg}
    non_empty_all = {k: s for k, s in all_sets.items() if s}

    # CONFLICT: dos identificadores apuntan a registros disjuntos.
    for k1 in non_empty_all:
        for k2 in non_empty_all:
            if k1 < k2 and non_empty_all[k1].isdisjoint(non_empty_all[k2]):
                return {"disponible": True, "match_status": STATUS_CONFLICT,
                        "registro": None, "coincidencias": coincidencias,
                        "provenance": prov}

    if not non_empty_core:
        return {"disponible": True, "match_status": STATUS_NO_MATCH,
                "registro": None, "coincidencias": coincidencias, "provenance": prov}

    inter = set.intersection(*non_empty_core.values())
    if len(inter) == 1:
        grado = len(non_empty_core)
        status = {3: STATUS_EXACT_3, 2: STATUS_EXACT_2, 1: STATUS_EXACT_1}.get(grado, f"EXACT_{grado}")
        return {"disponible": True, "match_status": status,
                "registro": registros[next(iter(inter))],
                "coincidencias": coincidencias, "provenance": prov}

    # no single intersection (defensivo; ya cubierto por CONFLICT)
    return {"disponible": True, "match_status": STATUS_CONFLICT,
            "registro": None, "coincidencias": coincidencias, "provenance": prov}


def resolver_identidad_oficial(*, folio: Optional[str] = None,
                               numero_predial: Optional[str] = None,
                               codigo_homologado: Optional[str] = None) -> Dict[str, Any]:
    """Resolución autoritativa estática → fragmento canónico de identidad (03G.1).

    Solo EXACT_3 (numero_predial + codigo_homologado + fmi) produce
    VERIFIED_UNIT_IDENTITY. En ese caso `identity_verified=True` PERO
    `market_context_ready=False`: el registro estático NO aporta barrio/estrato/
    tipología, así que la valoración queda pendiente del segundo gate
    MARKET_CONTEXT_READY (no se habilita solo por identidad verificada).
    """
    r = consultar_adopcion(folio=folio, numero_predial=numero_predial,
                           codigo_homologado=codigo_homologado)
    status = r["match_status"]

    base = {
        "resolution_method": "official_adoption_registry",
        "identity_source": "OFFICIAL_ADOPTION_REGISTRY",
        "market_context_ready": False,
        "registro": r.get("registro"),
        "provenance": r.get("provenance"),
    }

    if status == STATUS_CONFLICT:
        return {**base, "estado": "IDENTITY_CONFLICT",
                "resolution_confidence": "CONFLICT", "identity_verified": False}
    if status == STATUS_EXACT_3:
        return {**base, "estado": "MATCH_EXACT",
                "resolution_confidence": "VERIFIED_UNIT_IDENTITY",
                "identity_verified": True}
    if status in (STATUS_EXACT_2, STATUS_EXACT_1):
        return {**base, "estado": "MATCH_BY_PREDIAL_CODE",
                "resolution_confidence": "PARTIAL_IDENTITY",
                "identity_verified": False}
    # NO_MATCH
    return {**base, "estado": "NO_MATCH",
            "resolution_confidence": "UNRESOLVED", "identity_verified": False}

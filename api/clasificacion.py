# -*- coding: utf-8 -*-
"""Clasificación del inmueble: uso ≠ régimen jurídico ≠ tipología física (03I.2A §16).

TRES DIMENSIONES INDEPENDIENTES
-------------------------------
    jurídica     PROPIEDAD_HORIZONTAL / NO_PROPIEDAD_HORIZONTAL   (régimen/condición)
    económica    HABITACIONAL / COMERCIAL / INDUSTRIAL / OFICINA …(uso/destinación)
    física       APARTAMENTO / CASA / LOCAL / OFICINA / BODEGA /
                 GARAJE / UNIDAD_EN_PROPIEDAD_HORIZONTAL          (tipología)

REGLA CAPITAL (lo que estaba mal): un USO nunca decide el RÉGIMEN. Una unidad bajo
propiedad horizontal puede tener uso habitacional, comercial, de oficina o garaje:
antes, ver «Comercial»/«Oficina»/«Industrial» en el destino económico bastaba para
escribir «No Propiedad Horizontal» en la tipología, borrando evidencia registral
válida. Ahora cada dimensión se resuelve con SU evidencia y con su propio estado.

CONTRADICCIÓN: solo se declara cuando dos evidencias incompatibles hablan de la MISMA
dimensión (PH registral vs NO PH catastral). «PH + uso comercial» NO es contradicción.

ESTADOS por campo: VERIFIED_REGISTRAL · VERIFIED_CATASTRAL · VERIFIED_CATASTRAL_TEMATICO ·
UNRESOLVED · CONFLICT.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple

ST_VERIFIED_REGISTRAL = "VERIFIED_REGISTRAL"
ST_VERIFIED_CATASTRAL = "VERIFIED_CATASTRAL"
ST_VERIFIED_TEMATICO = "VERIFIED_CATASTRAL_TEMATICO"
ST_UNRESOLVED = "UNRESOLVED"
ST_CONFLICT = "CONFLICT"

# ── Régimen jurídico ──────────────────────────────────────────────────────────
REG_PH = "PROPIEDAD_HORIZONTAL"
REG_NO_PH = "NO_PROPIEDAD_HORIZONTAL"

# ── Uso económico ────────────────────────────────────────────────────────────
USO_HABITACIONAL = "HABITACIONAL"
USO_COMERCIAL = "COMERCIAL"
USO_INDUSTRIAL = "INDUSTRIAL"
USO_OFICINA = "OFICINA"
USO_GARAJE = "GARAJE"
USO_MIXTO = "MIXTO"
USO_LOTE = "LOTE"

# ── Tipología física ─────────────────────────────────────────────────────────
TIP_APARTAMENTO = "APARTAMENTO"
TIP_CASA = "CASA"
TIP_LOCAL = "LOCAL"
TIP_OFICINA = "OFICINA"
TIP_BODEGA = "BODEGA"
TIP_GARAJE = "GARAJE"
TIP_UNIDAD_PH = "UNIDAD_EN_PROPIEDAD_HORIZONTAL"

_NO_PH_PATTERNS = (
    "NO PROPIEDAD HORIZONTAL", "NO ES PROPIEDAD HORIZONTAL", "SIN PROPIEDAD HORIZONTAL",
    "PROPIEDAD NO HORIZONTAL",
)
_PH_PATTERNS = ("PROPIEDAD HORIZONTAL", "PH ", " PH", "REGIMEN DE PROPIEDAD HORIZONTAL")


def _campo(valor=None, status: str = ST_UNRESOLVED, source: Optional[str] = None,
           detalle: Optional[str] = None) -> Dict[str, Any]:
    return {"value": valor, "status": status, "source": source, "detalle": detalle}


def _up(txt) -> str:
    return " ".join(str(txt or "").upper().split())


def uso_economico_de(destino) -> Optional[str]:
    """Normaliza el destino económico catastral a un uso (nunca a un régimen)."""
    d = _up(destino)
    if not d:
        return None
    if "INDUSTRIAL" in d or "BODEGA" in d:
        return USO_INDUSTRIAL
    if "OFICINA" in d:
        return USO_OFICINA
    if "GARAJE" in d or "PARQUEADERO" in d:
        return USO_GARAJE
    if "LOTE" in d or "TERRENO" in d:
        return USO_LOTE
    if "COMERCIAL" in d or "COMERCIO" in d or "SERVICIOS" in d:
        # «Comercial y Servicios» con vivienda es mixto; si no, comercial.
        return USO_MIXTO if ("RESIDENCIAL" in d or "VIVIENDA" in d) else USO_COMERCIAL
    if "RESIDENCIAL" in d or "HABITACIONAL" in d or "VIVIENDA" in d:
        # «Residencial y comercial» = mixto.
        return USO_MIXTO if "COMERCIAL" in d else USO_HABITACIONAL
    return d[:40]


def tipologia_fisica_de(descripcion: Optional[str], *, es_ph: bool = False) -> Optional[str]:
    """Tipología física SOLO con evidencia textual explícita en la fuente."""
    d = _up(descripcion)
    if not d:
        return None
    if "BODEGA" in d or "BODEGAS" in d:
        return TIP_BODEGA
    if re.search(r"\bAPARTAMENTO", d) or re.search(r"\bAPTO\b", d) or "APARTAMENTOS" in d:
        return TIP_APARTAMENTO
    if "GARAJE" in d or "PARQUEADERO" in d:
        return TIP_GARAJE
    if "OFICINA" in d:
        return TIP_OFICINA
    if "LOCAL" in d:
        return TIP_LOCAL
    if "CASA" in d:
        return TIP_CASA
    if es_ph:
        # Hay régimen PH pero la fuente no declara la unidad física: NO se inventa
        # «apartamento»; se declara que es una unidad en PH.
        return TIP_UNIDAD_PH
    return None


def clasificar_inmueble(*, condicion_juridica: Optional[str] = None,
                        condicion_source: Optional[str] = None,
                        destino_economico: Optional[str] = None,
                        uso_economico: Optional[str] = None,
                        descripcion_registral: Optional[str] = None,
                        descripcion_catastral: Optional[str] = None,
                        tipologia_fisica_fuente: Optional[str] = None,
                        tipologia_source: Optional[str] = None) -> Dict[str, Any]:
    """Clasifica el inmueble en sus tres dimensiones, sin mezclarlas.

    Returns:
        {"juridical_regime": {...}, "economic_use": {...},
         "physical_typology": {...}, "conflicts": [...], "ph": bool}
    """
    _cond = _up(condicion_juridica)
    _reg: Dict[str, Any]
    if _cond:
        _es_no_ph = any(p in _cond for p in _NO_PH_PATTERNS)
        _es_ph = (not _es_no_ph) and any(p in f" {_cond} " for p in _PH_PATTERNS)
        _status = ST_VERIFIED_REGISTRAL
        if condicion_source == "thematic_exact" or condicion_source == "thematic_spatial":
            _status = ST_VERIFIED_TEMATICO
        elif condicion_source == "capa_predio":
            _status = ST_VERIFIED_CATASTRAL
        if _es_ph:
            _reg = _campo(REG_PH, _status, condicion_source or "CTL",
                          "condición jurídica declarada por la fuente")
        elif _es_no_ph:
            _reg = _campo(REG_NO_PH, _status, condicion_source or "CTL",
                          "condición jurídica declarada por la fuente")
        else:
            _reg = _campo(None, ST_UNRESOLVED, condicion_source or "CTL",
                          f"condición declarada no clasificable: {condicion_juridica!r}")
    else:
        _reg = _campo(None, ST_UNRESOLVED, None, "sin condición jurídica en la fuente")

    _dest = uso_economico if uso_economico else destino_economico
    _uso_val = uso_economico_de(_dest)
    if _uso_val:
        _uso = _campo(_uso_val, ST_VERIFIED_CATASTRAL, "catastro (destino económico)",
                      f"destino declarado: {destino_economico!r}")
        # Se conserva la representación EXACTA de la fuente: el dictamen la muestra.
        _uso["raw"] = str(destino_economico or uso_economico or "").strip() or None
    else:
        _uso = _campo(None, ST_UNRESOLVED, None, "sin destino económico en la fuente")

    # ── Contradicciones: SOLO dentro de la MISMA dimensión ────────────────────
    # Se resuelven ANTES de derivar nada del régimen: un régimen en CONFLICTO no
    # autoriza a inferir tipología a partir de él (antes `_es_ph` quedaba calculado
    # con el valor previo y una unidad en conflicto se etiquetaba como PH).
    conflicts = []
    if condicion_juridica and descripcion_catastral:
        _cat = _up(descripcion_catastral)
        if _reg.get("value") == REG_PH and any(p in _cat for p in _NO_PH_PATTERNS):
            conflicts.append({
                "dimension": "juridical_regime",
                "detalle": ("el registro declara Propiedad Horizontal y el catastro "
                            "declara NO Propiedad Horizontal"),
            })
            _reg = _campo(None, ST_CONFLICT, "registro vs catastro",
                          "evidencias incompatibles sobre el régimen jurídico")

    _es_ph = _reg.get("value") == REG_PH
    _tip_txt = (tipologia_fisica_fuente or descripcion_registral
                or descripcion_catastral)
    # La tipología física es una dimensión INDEPENDIENTE: se deriva de la evidencia
    # textual aunque el régimen esté sin resolver o en conflicto (lo único que exige
    # régimen verificado es la etiqueta de relleno «Unidad en Propiedad Horizontal»).
    _tip_val = tipologia_fisica_de(_tip_txt, es_ph=_es_ph)
    if _tip_val:
        _src = tipologia_source or ("registro/CTL" if (tipologia_fisica_fuente
                                                       or descripcion_registral) else "catastro")
        _st = (ST_VERIFIED_REGISTRAL if (tipologia_fisica_fuente or descripcion_registral)
               else ST_VERIFIED_CATASTRAL)
        _tip = _campo(_tip_val, _st, _src, f"evidencia textual: {_tip_txt!r}"[:120])
    else:
        _tip = _campo(None, ST_UNRESOLVED, None,
                      "la fuente no acredita la unidad física")

    return {
        "juridical_regime": _reg,
        "economic_use": _uso,
        "physical_typology": _tip,
        "conflicts": conflicts,
        "ph": _es_ph,
    }


# ── Texto para el dictamen (compatibilidad con el render existente) ───────────

def texto_tipologia(clasificacion: Dict[str, Any]) -> str:
    """Texto único de tipología a partir de la clasificación (nunca mezcla uso)."""
    reg = (clasificacion or {}).get("juridical_regime") or {}
    uso = (clasificacion or {}).get("economic_use") or {}
    tip = (clasificacion or {}).get("physical_typology") or {}
    # Un conflicto se declara ANTES que cualquier texto afirmativo: dos evidencias
    # incompatibles sobre la misma dimensión no se resuelven eligiendo una.
    if (clasificacion or {}).get("conflicts") or reg.get("status") == ST_CONFLICT \
            or tip.get("status") == ST_CONFLICT:
        return "PENDIENTE DE VERIFICACION (conflicto de régimen jurídico entre fuentes)"
    _es_ph = reg.get("value") == REG_PH
    _sufijo_ph = ("(condición catastral)" if reg.get("status") == ST_VERIFIED_TEMATICO
                  else ("(inferido del CTL)" if _es_ph else ""))
    _tip_val = tip.get("value")

    if _tip_val == TIP_BODEGA:
        return "Bodega -- Uso Industrial"
    if _tip_val in (TIP_APARTAMENTO, TIP_UNIDAD_PH):
        if _es_ph:
            _unidad = "Apartamento" if _tip_val == TIP_APARTAMENTO else "Unidad"
            return f"{_unidad} -- Propiedad Horizontal {_sufijo_ph}".strip()
        return "Apartamento (sin régimen de propiedad horizontal declarado)"
    if _tip_val in (TIP_LOCAL, TIP_OFICINA, TIP_GARAJE, TIP_CASA):
        _nombre = {"LOCAL": "Local", "OFICINA": "Oficina", "GARAJE": "Garaje",
                   "CASA": "Casa"}[_tip_val]
        if _es_ph:
            return f"{_nombre} en Propiedad Horizontal {_sufijo_ph}".strip()
        return _nombre
    if tip.get("status") == ST_CONFLICT or reg.get("status") == ST_CONFLICT:
        return "PENDIENTE DE VERIFICACION (conflicto de régimen jurídico entre fuentes)"
    if uso.get("value"):
        # Sin evidencia de régimen ni de unidad física: se declara el USO como uso,
        # con la representación exacta que declaró la fuente.
        _etq = str(uso.get("raw") or str(uso["value"]).title())
        if _es_ph:
            return f"Unidad en Propiedad Horizontal -- uso {_etq}"
        return f"Uso {_etq} (Según catastro)"
    if _es_ph:
        return f"Unidad -- Propiedad Horizontal {_sufijo_ph}".strip()
    if reg.get("status") == ST_UNRESOLVED and uso.get("status") == ST_UNRESOLVED:
        return "PENDIENTE DE VERIFICACION (Requiere consulta catastral)"
    return "PENDIENTE DE VERIFICACION"


def estado_aceptable_para_mercado(clasificacion: Dict[str, Any]) -> Tuple[bool, str]:
    """¿La clasificación permite abrir el gate de contexto de mercado? (§20)

    Exige RÉGIMEN o TIPOLOGÍA FÍSICA verificados. Un uso declarado por sí solo NO
    habilita la valoración (antes, con «Uso X (Según catastro)» como tipología, el
    gate podía abrirse o cerrarse por un dato que no es tipología).
    """
    reg = (clasificacion or {}).get("juridical_regime") or {}
    tip = (clasificacion or {}).get("physical_typology") or {}
    _ok_reg_st = reg.get("status") in (ST_VERIFIED_REGISTRAL, ST_VERIFIED_CATASTRAL,
                                       ST_VERIFIED_TEMATICO)
    _ok_tip_st = tip.get("status") in (ST_VERIFIED_REGISTRAL, ST_VERIFIED_CATASTRAL,
                                       ST_VERIFIED_TEMATICO)
    if reg.get("status") == ST_CONFLICT or tip.get("status") == ST_CONFLICT:
        return False, "conflicto de régimen jurídico entre fuentes"
    if _ok_reg_st and reg.get("value"):
        return True, f"régimen {reg['value']} ({reg['status']})"
    if _ok_tip_st and tip.get("value"):
        return True, f"tipología física {tip['value']} ({tip['status']})"
    return False, "ni régimen jurídico ni tipología física verificados"

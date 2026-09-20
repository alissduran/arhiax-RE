# -*- coding: utf-8 -*-
"""
ARHIAX RE — Parser de unidad inmobiliaria (torre / apartamento / unidad).

Separación direccion_raw vs direccion_base (remediación forense 040-646406):

  * `direccion_raw`   = representación preservada (con unidad) de evidencia autoritativa.
  * `direccion_base`  = dirección del edificio/predio (sin complemento de unidad),
                        para integraciones externas que requieren eliminar complementos.

Regla de no destrucción: el parser DERIVA `direccion_base` desde `direccion_raw` pero
NUNCA sobrescribe la original. Si no hay certeza, devuelve None (no alucina).
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

# Orden importa: primero los tokens largos (APARTAMENTO) antes que los cortos (AP).
_PATRONES: Dict[str, list] = {
    "torre": [
        r"\bTORRE\s*[Nn]?[°º]?\s*([A-Z0-9\-]{1,6})\b",
        r"\bTO\s*[Nn]?[°º]?\s*([A-Z0-9\-]{1,6})\b",
        r"\bT\s*[Nn]?[°º]?\s*(\d{1,6})\b",
    ],
    "apartamento": [
        r"\bAPARTAMENTO\s*[Nn]?[°º]?\s*(\d{1,6})\b",
        r"\bAPTO\s*[Nn]?[°º]?\s*(\d{1,6})\b",
        r"\bAP\s*[Nn]?[°º]?\s*(\d{1,6})\b",
    ],
    "unidad": [
        r"\bUNIDAD\s*[Nn]?[°º]?\s*(\d{1,6})\b",
        r"\bUND\s*[Nn]?[°º]?\s*(\d{1,6})\b",
        r"\bINTERIOR\s*[Nn]?[°º]?\s*(\d{1,6})\b",
        r"\bINT\s*[Nn]?[°º]?\s*(\d{1,6})\b",
    ],
}

# Tokens a eliminar de la base (incluye el número capturado).
_TOKENS_BASE = [
    r"\bTORRE\s*[Nn]?[°º]?\s*[A-Z0-9\-]{1,6}\b",
    r"\bTO\s*[Nn]?[°º]?\s*[A-Z0-9\-]{1,6}\b",
    r"\bT\s*[Nn]?[°º]?\s*\d{1,6}\b",
    r"\bAPARTAMENTO\s*[Nn]?[°º]?\s*\d{1,6}\b",
    r"\bAPTO\s*[Nn]?[°º]?\s*\d{1,6}\b",
    r"\bAP\s*[Nn]?[°º]?\s*\d{1,6}\b",
    r"\bUNIDAD\s*[Nn]?[°º]?\s*\d{1,6}\b",
    r"\bUND\s*[Nn]?[°º]?\s*\d{1,6}\b",
    r"\bINTERIOR\s*[Nn]?[°º]?\s*\d{1,6}\b",
    r"\bINT\s*[Nn]?[°º]?\s*\d{1,6}\b",
]


def extraer_unidad(direccion: Optional[str]) -> Dict[str, Any]:
    """Extrae torre/apartamento/unidad y deriva la dirección base.

    Devuelve:
        {"direccion_raw": ..., "direccion_base": ..., "torre": ..., "apartamento": ..., "unidad": ...}
    Sin destruir la dirección original. Los campos ausentes quedan en None.
    """
    raw = (direccion or "").strip()
    out: Dict[str, Any] = {
        "direccion_raw": raw or None,
        "direccion_base": raw or None,
        "torre": None,
        "apartamento": None,
        "unidad": None,
    }
    if not raw:
        return out

    for tipo, patrones in _PATRONES.items():
        for p in patrones:
            m = re.search(p, raw, re.IGNORECASE)
            if m:
                out[tipo] = m.group(1).strip()
                break

    base = raw
    for p in _TOKENS_BASE:
        base = re.sub(p, " ", base, flags=re.IGNORECASE)
    base = " ".join(base.split()).strip(" .,;/")
    if base:
        out["direccion_base"] = base
    else:
        out["direccion_base"] = None
    return out

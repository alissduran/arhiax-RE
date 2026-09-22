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

# Tokens de COMPLEMENTO (torre/apartamento/unidad/interior) en el orden en que
# aparecen en la dirección: con ellos se compone la UNIDAD declarada
# ("TO 8 AP 430") en lugar de dejarla en None (03I.1 · F5).
_TOKENS_COMPLEMENTO = re.compile(
    r"\b(?:TORRE\s*[Nn]?[°º]?\s*[A-Z0-9\-]{1,6}"
    r"|TO\s*[Nn]?[°º]?\s*[A-Z0-9\-]{1,6}"
    r"|T\s*[Nn]?[°º]?\s*\d{1,6}"
    r"|APARTAMENTO\s*[Nn]?[°º]?\s*\d{1,6}"
    r"|APTO\s*[Nn]?[°º]?\s*\d{1,6}"
    r"|AP\s*[Nn]?[°º]?\s*\d{1,6}"
    r"|UNIDAD\s*[Nn]?[°º]?\s*\d{1,6}"
    r"|UND\s*[Nn]?[°º]?\s*\d{1,6}"
    r"|INTERIOR\s*[Nn]?[°º]?\s*\d{1,6}"
    r"|INT\s*[Nn]?[°º]?\s*\d{1,6})\b", re.IGNORECASE)


def extraer_unidad(direccion: Optional[str]) -> Dict[str, Any]:
    """Extrae torre/apartamento/unidad y deriva la dirección base.

    Devuelve:
        {"direccion_raw": ..., "direccion_base": ..., "torre": ..., "apartamento": ..., "unidad": ...}
    Sin destruir la dirección original. Los campos ausentes quedan en None.
    `unidad` es el COMPLEMENTO declarado tal como aparece en la dirección
    (p. ej. "TO 8 AP 430"), no un número adivinado (03I.1 · F5).
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

    # Complemento declarado, en el orden en que aparece ("TO 8 AP 430").
    _comp = [m.group(0).strip() for m in _TOKENS_COMPLEMENTO.finditer(raw)]
    if _comp:
        out["unidad"] = " ".join(_comp)

    base = raw
    for p in _TOKENS_BASE:
        base = re.sub(p, " ", base, flags=re.IGNORECASE)
    base = " ".join(base.split()).strip(" .,;/")
    if base:
        out["direccion_base"] = base
    else:
        out["direccion_base"] = None
    return out


def identidad_direccion(canonical_identity: Optional[Dict[str, Any]],
                        direccion_oficial: Optional[str] = None,
                        *, fuente: str = "OFFICIAL_ADOPTION_REGISTRY") -> Dict[str, Any]:
    """Promueve una dirección OFICIAL al modelo canónico (03I.1 · F5).

    Regresión (Golden 040-646406): la identidad quedaba en
    `resolution_confidence=VERIFIED_UNIT_IDENTITY` con
    `identity_source=OFFICIAL_ADOPTION_REGISTRY` —y el registro oficial traía la
    dirección "Transversal 43 100 50 TO 8 AP 430"— mientras el modelo canónico
    seguía mostrando `direccion_raw='Pendiente de verificacion'`, `torre=None` y
    `unidad=None`. Un modelo que se declara verificado no puede ignorar el dato
    que lo verifica.

    Función PURA: no muta la entrada; devuelve los campos a aplicar. Solo escribe
    si la dirección oficial existe y no es un placeholder, y conserva la
    procedencia (`direccion_source`) junto con el valor previo
    (`direccion_previa`) para no destruir evidencia.
    """
    reg = (canonical_identity or {}).get("adopcion_registro") or {}
    oficial = str(direccion_oficial or reg.get("direccion") or "").strip()
    if not oficial:
        return {}
    if oficial.upper() in ("", "N/D", "NA", "NONE", "PENDIENTE",
                           "PENDIENTE DE VERIFICACION", "PENDIENTE DE VERIFICACIÓN"):
        return {}
    u = extraer_unidad(oficial)
    actual = str((canonical_identity or {}).get("direccion_raw") or "").strip()
    out: Dict[str, Any] = {
        "direccion_raw": oficial,
        "direccion_base": u.get("direccion_base") or oficial,
        "direccion_normalizada": _normalizar_direccion(u.get("direccion_base") or oficial),
        "torre": u.get("torre"),
        "apartamento": u.get("apartamento"),
        "unidad": u.get("unidad"),
        "direccion_source": fuente,
        "direccion_status": "VERIFIED_OFFICIAL",
    }
    if actual and actual.upper() not in ("PENDIENTE", "PENDIENTE DE VERIFICACION",
                                         "PENDIENTE DE VERIFICACIÓN") and actual != oficial:
        out["direccion_previa"] = actual
    return out


def _normalizar_direccion(txt: str) -> Optional[str]:
    """Forma normalizada para cotejo (mayúsculas, sin puntuación redundante)."""
    t = " ".join(str(txt or "").upper().split())
    t = t.replace(" # ", " ").replace("# ", " ").replace("-", " ")
    t = re.sub(r"[.,;]+", " ", t)
    return " ".join(t.split()) or None

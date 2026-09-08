"""Normalización de documentos de identidad."""
import re

_ALIASES = {
    "cc": ("cc", "c.c", "cedula", "cédula", "cedula de ciudadania", "cédula de ciudadanía"),
    "nit": ("nit", "n.i.t"),
    "pasaporte": ("pasaporte", "passport"),
    "ce": ("ce", "c.e", "cedula de extranjeria", "cédula de extranjería"),
}


def normalize_documento(tipo, numero):
    t = _normalize_tipo(tipo)
    if numero is None:
        return t, None
    n = re.sub(r"[^0-9A-Za-z]", "", str(numero)).upper()
    return t, (n or None)


def _normalize_tipo(tipo):
    if not tipo:
        return None
    t = str(tipo).strip().lower()
    for canon, aliases in _ALIASES.items():
        if t == canon or t in aliases:
            return canon
    return t

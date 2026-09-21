"""Parser de OFAC SDN (XML) — agnóstico de namespace XML.

OFAC publica el SDN con un namespace por defecto, así que `root.iter("sdnEntry")`
no encuentra nada. Se resuelve por nombre local del elemento.
"""
import xml.etree.ElementTree as ET

from ..contracts import RegistroNormalizado


def _local(tag):
    return tag.split("}")[-1]


def _find(node, tag):
    for child in node:
        if _local(child.tag) == tag:
            return child
    return None


def _iter(node, tag):
    return (c for c in node.iter() if _local(c.tag) == tag)


def _iterall(node, tag):
    return [c for c in node.iter() if _local(c.tag) == tag]


def parse_ofac_sdn(xml_bytes, lista_version=""):
    root = ET.fromstring(xml_bytes)
    return [_to_registro(entry, lista_version) for entry in _iter(root, "sdnEntry")]


def _to_registro(entry, lista_version):
    uid = _text(_find(entry, "uid"))
    nombre = _compose_name(entry)
    ids = _identificadores(entry)
    _prim = ids[0] if ids else None
    tipo_doc, num_doc = _doc(entry)
    return RegistroNormalizado(
        id=("ofac-" + uid) if uid else ("ofac-" + nombre),
        nombre=nombre,
        alias=_aliases(entry),
        tipo_documento=(_prim or {}).get("type") or tipo_doc,
        numero_documento=(_prim or {}).get("value") or num_doc,
        fecha_nacimiento=_birth(entry),
        programas=_programs(entry),
        fuente="ofac",
        lista_version=lista_version,
        identifiers=ids,
    )


def _identificadores(entry):
    """TODOS los <id> del registro (03S.1A-4).

    Antes se conservaba solo el PRIMERO, perdiendo identificadores secundarios
    que sí pueden confirmar (o descartar) una coincidencia.
    """
    out = []
    for id_node in _iter(entry, "id"):
        num = _text(_find(id_node, "idNumber"))
        if not num:
            continue
        out.append({"type": _map_id_type(_text(_find(id_node, "idType"))),
                    "value": num, "source_field": "idList/id/idNumber"})
    return tuple(out)


def _compose_name(entry):
    first = _text(_find(entry, "firstName"))
    last = _text(_find(entry, "lastName"))
    return " ".join(p for p in (first, last) if p).strip()


def _aliases(entry):
    out = []
    for aka in _iter(entry, "aka"):
        first = _text(_find(aka, "firstName"))
        last = _text(_find(aka, "lastName"))
        name = " ".join(p for p in (first, last) if p).strip()
        if name:
            out.append(name)
    return tuple(out)


def _doc(entry):
    for id_node in _iter(entry, "id"):
        num = _text(_find(id_node, "idNumber"))
        if num:
            return _map_id_type(_text(_find(id_node, "idType"))), num
    return None, None


def _map_id_type(tipo):
    t = (tipo or "").lower()
    if "passport" in t:
        return "pasaporte"
    if "tax" in t or "vat" in t:
        return "nit"
    if "cedula" in t or "national" in t:
        return "cc"
    return tipo or None


def _birth(entry):
    for dob in _iter(entry, "dateOfBirthItem"):
        return _text(_find(dob, "dateOfBirth"))
    return None


def _programs(entry):
    return tuple(_text(p) for p in _iterall(entry, "program"))


def _text(node):
    return (node.text or "").strip() if node is not None else ""

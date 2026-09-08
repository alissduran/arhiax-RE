"""Parser de la ONU Consolidated List (XML)."""
import xml.etree.ElementTree as ET

from ..contracts import RegistroNormalizado


def parse_onu_xml(xml_bytes, lista_version=""):
    root = ET.fromstring(xml_bytes)
    registros = []
    for container_name in ("INDIVIDUALS", "ENTITIES"):
        container = root.find(container_name)
        if container is None:
            continue
        for item in container:
            registros.append(_to_registro(item, lista_version))
    return registros


def _to_registro(item, lista_version):
    nombre = _compose_name(item)
    dataid = _text(item.find("DATAID"))
    return RegistroNormalizado(
        id=("onu-" + dataid) if dataid else ("onu-" + nombre),
        nombre=nombre,
        alias=_aliases(item),
        tipo_documento=None,
        numero_documento=_doc_number(item),
        fecha_nacimiento=_birth_date(item),
        programas=_programs(item),
        fuente="onu",
        lista_version=lista_version,
    )


def _compose_name(item):
    parts = [_text(item.find(t)) for t in ("FIRST_NAME", "SECOND_NAME", "THIRD_NAME", "FOURTH_NAME")]
    return " ".join(p for p in parts if p).strip()


def _aliases(item):
    out = []
    for alias_node in item.iter("INDIVIDUAL_ALIAS"):
        name = _text(alias_node.find("ALIAS_NAME"))
        if name:
            out.append(name)
    for alias_node in item.iter("ENTITY_ALIAS"):
        name = _text(alias_node.find("ALIAS_NAME"))
        if name:
            out.append(name)
    return tuple(out)


def _doc_number(item):
    for note in item.iter("NOTE"):
        txt = _text(note)
        if txt and ("document" in txt.lower() or "passport" in txt.lower()):
            return txt
    return None


def _birth_date(item):
    for dob in item.iter("INDIVIDUAL_DATE_OF_BIRTH"):
        d = _text(dob.find("DATE"))
        if d:
            return d
    return None


def _programs(item):
    v = _text(item.find("UN_LIST_TYPE"))
    return (v,) if v else ()


def _text(node):
    return (node.text or "").strip() if node is not None else ""

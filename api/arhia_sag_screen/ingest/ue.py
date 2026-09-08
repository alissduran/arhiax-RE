"""Parser de la lista consolidada de sanciones financieras de la UE (FSD) — estructura real.

Estructura documentada del feed DG FISMA / FSF (XML 1.1):
    <export xmlns="http://eu.europa.ec/fpi/fsd/export" generationDate="..." globalFileId="...">
        <sanctionEntity designationDetails=.. unitedNationId=.. euReferenceNumber=.. logicalId=..>
            <remark/>
            <regulation regulationType=.. publicationDate=.. programme=.. numberTitle=../>
            <subjectType code="person|entity"/>
            <nameAlias firstName=.. middleName=.. lastName=.. wholeName=.. function=.. title=..
                       strong=.. regulationLanguage=.. logicalId=../>
            <citizenship/>
            <birthdate/>
            <identification/>   <-- (tipo + num)
            <address/>
        </sanctionEntity>
    </export>

El parser es namespace-agnóstico (por nombre local), hace streaming (`iterparse`) y es tolerante
a evolución del esquema. Adquisición en vivo: webgate bloquea (403 anti-bot) y el mirror devuelve
HTML, así que se usa **`ingestar_fichero`** con el XML obtenido por el canal oficial (crawler/robot
de FSF) o mirror institucional.
"""
import io
import re
import xml.etree.ElementTree as ET
from typing import Optional

from ..contracts import RegistroNormalizado


def _local(tag):
    return tag.split("}")[-1]


def _text(node):
    return (node.text or "").strip() if node is not None else ""


def _attr(elem, name):
    return (elem.get(name) or "").strip()


def _compose_alias(alias):
    whole = _attr(alias, "wholeName")
    if whole:
        return whole
    parts = [_attr(alias, "firstName"), _attr(alias, "middleName"), _attr(alias, "lastName")]
    return " ".join(p for p in parts if p).strip()


def _first_strong_alias(entity):
    aliases = [c for c in entity if _local(c.tag) == "nameAlias"]
    if not aliases:
        return None, ()
    strong = [a for a in aliases if _attr(a, "strong") in ("true", "True", "1")]
    main = (strong or aliases)[0]
    extras = tuple(_compose_alias(a) for a in aliases if a is not main and _compose_alias(a))
    return main, extras


def _id_from_entity(entity):
    """Busca identificador dentro de `<identification>` o de elementos con nombre tipo ID."""
    for c in entity:
        ln = _local(c.tag)
        if ln == "identification":
            num = _attr(c, "idNumber") or _attr(c, "number") or _text(c)
            tipo = _attr(c, "identificationTypeCode") or _attr(c, "type") or ""
            if num:
                t = tipo.lower()
                if "passport" in t:
                    return "pasaporte", num
                if "national" in t or "id" in t:
                    return "cc", num
                return (tipo or None), num
    # fallback: buscar atributo idNumber en cualquier descendiente
    for elem in entity.iter():
        for k in ("idNumber", "number", "documentNumber"):
            v = elem.get(k)
            if v:
                return "cc", v
    return None, None


def parse_ue_xml(xml_bytes, lista_version=""):
    """Devuelve RegistroNormalizado por cada `sanctionEntity` del XML FSD. Streaming."""
    regs = []
    for event, elem in ET.iterparse(io.BytesIO(xml_bytes), events=("end",)):
        if _local(elem.tag) == "sanctionEntity":
            alias, extras = _first_strong_alias(elem)
            nombre = _compose_alias(alias) if alias is not None else ""
            tipo_doc, num_doc = _id_from_entity(elem)
            programa = ""
            for c in elem:
                if _local(c.tag) == "regulation":
                    p = _attr(c, "programme") or _attr(c, "numberTitle")
                    if p:
                        programa = p
                        break
            if nombre:
                regs.append(RegistroNormalizado(
                    id="ue-" + (_attr(elem, "euReferenceNumber") or _attr(elem, "logicalId")
                                or re.sub(r"\W+", "", nombre)[:24] or "x"),
                    nombre=nombre, alias=extras, tipo_documento=tipo_doc, numero_documento=num_doc,
                    programas=(programa,) if programa else (),
                    fuente="ue", lista_version=lista_version))
            elem.clear()
    return regs

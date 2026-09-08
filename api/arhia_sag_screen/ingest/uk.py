"""Parser de la lista de sanciones financieras del Reino Unido (HMT/OFSI) — XML grande.

`ConList.xml` (~54 MB) es un `<ArrayOfFinancialSanctionsTarget>` con elementos
`FinancialSanctionsTarget`. Se parsea con `iterparse` (streaming) y por nombre local de
elemento, de modo que el namespace XML no interfiera y la memoria se libera por entrada.
"""
import io
import re
import xml.etree.ElementTree as ET
from typing import List

from ..contracts import RegistroNormalizado


def _local(tag):
    return tag.split("}")[-1]


def _text(node):
    return (node.text or "").strip() if node is not None else ""


def _collect(entry):
    """Agrupa por nombre local de tag (a cualquier profundidad): tag -> [textos]."""
    buckets = {}
    for elem in entry.iter():
        if elem is entry:
            continue
        if len(elem) == 0:  # hoja con texto
            buckets.setdefault(_local(elem.tag), []).append(_text(elem))
    return buckets


def _compose_name(buckets):
    items = []
    for k, vals in buckets.items():
        m = re.match(r"(?i)^name(\d+)$", k)
        if m:
            items.append((int(m.group(1)), vals))
    items.sort(key=lambda x: x[0])
    parts = []
    for _, vals in items:
        parts.extend(vals)
    return " ".join(p for p in parts if p).strip()


def _doc(buckets):
    """Intenta extraer un identificador tipo pasaporte/nacional de los elementos `id`/`idNumber`."""
    nums = buckets.get("idNumber") or buckets.get("id") or []
    if not nums:
        return None, None
    num = nums[0]
    tipos = buckets.get("idType") or buckets.get("type") or []
    tipo = tipos[0] if tipos else None
    t = (tipo or "").lower()
    if "passport" in t or "national" in t or "id" in t:
        return ("pasaporte" if "passport" in t else "cc"), num
    return tipo, num


def _to_registro(entry, lista_version):
    buckets = _collect(entry)
    nombre = _compose_name(buckets)
    tipo_doc, num_doc = _doc(buckets)
    alias = tuple(buckets.get("alias", []) or buckets.get("aka", []))
    return RegistroNormalizado(
        id="uk-" + (num_doc or re.sub(r"\W+", "", nombre)[:20]),
        nombre=nombre,
        alias=alias,
        tipo_documento=tipo_doc,
        numero_documento=num_doc,
        programas=tuple(buckets.get("program", [])),
        fuente="uk",
        lista_version=lista_version,
    )


def parse_uk_ofsi_xml(xml_bytes, lista_version=""):
    """Devuelve la lista de RegistroNormalizado del XML de OFSI. Streaming + limpieza."""
    regs = []
    for event, elem in ET.iterparse(io.BytesIO(xml_bytes), events=("end",)):
        if _local(elem.tag) == "FinancialSanctionsTarget":
            regs.append(_to_registro(elem, lista_version))
            elem.clear()
    return regs

# -*- coding: utf-8 -*-
"""Parsers de las fuentes oficiales (§7/§8/§9) → RegistroNormalizado.

Los parsers de ONU y OFAC SDN del subsistema ya existente se reutilizan; aquí
se añade el parser de la **UK Sanctions List** (FCDO, esquema 4.x), que es la
fuente vigente de UK tras la migración de 03S.1.

Agnósticos de namespace: se busca por nombre LOCAL del elemento, de modo que un
cambio de prefijo/namespace en la fuente no rompa el parseo (pero SÍ se detecta
si la estructura cambia: ver `esquema_reconocido`).
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any, List, Tuple

PARSER_VERSION = "sanctions-parsers/1.1"

# Tipos de documento normalizados (mapa de la fuente → vocabulario interno).
_TIPO_DOC = (
    (("passport", "pasaporte"), "pasaporte"),
    (("national id", "national identifier", "nationalid", "cedula", "cédula",
      "identity card", "national identification"), "cc"),
    (("tax", "vat", "ruc", "tax id", "nit"), "nit"),
    (("registration", "business registration", "company number", "reg no"), "registro"),
    (("imo",), "imo"),
    (("driving", "licencia de conduccion", "licence"), "licencia"),
    (("other", "otro"), "otro"),
)


def _normalizar_tipo_doc(tipo: str) -> str:
    t = str(tipo or "").strip().lower()
    if not t:
        return ""
    for claves, canon in _TIPO_DOC:
        if any(k in t for k in claves):
            return canon
    return t


def _ident(type_: str, value: str, source_field: str) -> dict:
    return {"type": _normalizar_tipo_doc(type_), "value": (value or "").strip(),
            "source_field": source_field}


class FuenteEstructuraNoReconocida(Exception):
    pass


def _local(tag: str) -> str:
    return str(tag).split("}")[-1]


def _text(node) -> str:
    return (node.text or "").strip() if node is not None else ""


def _find_local(node, nombre: str):
    for c in node:
        if _local(c.tag) == nombre:
            return c
    return None


def _iter_local(node, nombre: str):
    return (c for c in node.iter() if _local(c.tag) == nombre)


# ── ONU ──────────────────────────────────────────────────────────────────────

def parse_un_consolidated(xml_bytes: bytes, lista_version: str = "") -> List[Any]:
    from arhia_sag_screen.ingest.onu import parse_onu_xml
    regs = parse_onu_xml(xml_bytes, lista_version)
    if not regs:
        raise FuenteEstructuraNoReconocida(
            "UN_CONSOLIDATED: el XML no arrojó registros (estructura no reconocida)")
    return regs


# ── OFAC SDN ─────────────────────────────────────────────────────────────────

def parse_ofac_sdn(xml_bytes: bytes, lista_version: str = "") -> List[Any]:
    from arhia_sag_screen.ingest.ofac import parse_ofac_sdn as _p
    regs = _p(xml_bytes, lista_version)
    if not regs:
        raise FuenteEstructuraNoReconocida(
            "OFAC_SDN: el XML no arrojó registros (estructura no reconocida)")
    return regs


# ── UK Sanctions List (FCDO) ─────────────────────────────────────────────────

def parse_uk_sanctions_list(xml_bytes: bytes, lista_version: str = "") -> List[Any]:
    """Parser de la UK Sanctions List (`<Designations><Designation>`).

    Estructura oficial (esquema 4.x):
      Designation/UniqueID, Names/Name/(Name1..Name6, NameType),
      IndividualEntityShip (Individual|Entity|Ship), RegimeName,
      DesignationSource, IndividualDetails/Individual/DOBs/DOB,
      PassportDetails/Passport/PassportNumber,
      NationalIdentifierDetails/NationalIdentifier/NationalIdentifierNumber,
      EntityDetails/.../BusinessRegistrationNumbers/BusinessRegistrationNumber,
      ShipDetails/IMONumbers/IMONumber

    03S.1A-4: se conservan TODOS los identificadores soportados por el esquema,
    no solo el primer PassportNumber.
    """
    from arhia_sag_screen.contracts import RegistroNormalizado

    root = ET.fromstring(xml_bytes)
    if _local(root.tag) != "Designations":
        raise FuenteEstructuraNoReconocida(
            f"UK_SANCTIONS_LIST: raíz inesperada <{_local(root.tag)}>")
    fecha = _text(_find_local(root, "DateGenerated"))
    out: List[Any] = []
    for des in _iter_local(root, "Designation"):
        uid = _text(_find_local(des, "UniqueID"))
        nombres = _nombres_uk(des)
        if not nombres:
            continue
        principal, alias = nombres[0], nombres[1:]
        tipo = _text(_find_local(des, "IndividualEntityShip")).lower()
        ids = _identificadores_uk(des)
        _prim = ids[0] if ids else None
        programas = tuple(p for p in (
            _text(_find_local(des, "RegimeName")),
            _text(_find_local(des, "DesignationSource")),
            _text(_find_local(des, "UNReferenceNumber")),
        ) if p)
        out.append(RegistroNormalizado(
            id=("uk-" + uid) if uid else ("uk-" + principal),
            nombre=principal,
            alias=tuple(alias),
            tipo_documento=((_prim or {}).get("type")
                            or ("nit" if tipo in ("entity", "ship") else None)),
            numero_documento=(_prim or {}).get("value"),
            fecha_nacimiento=_dob_uk(des),
            programas=programas,
            fuente="uk",
            lista_version=lista_version or fecha,
            identifiers=ids,
        ))
    if not out:
        raise FuenteEstructuraNoReconocida(
            "UK_SANCTIONS_LIST: el XML no arrojó designaciones")
    return out


def _identificadores_uk(des) -> Tuple[dict, ...]:
    """Todos los identificadores de la designación (pasaportes, NIF nacionales,
    registros mercantiles, números IMO)."""
    out: List[dict] = []
    _mapa = (
        ("PassportNumber", "Passport", "PassportDetails/Passport/PassportNumber"),
        ("NationalIdentifierNumber", "National ID",
         "NationalIdentifierDetails/NationalIdentifier/NationalIdentifierNumber"),
        ("BusinessRegistrationNumber", "Business Registration",
         "EntityDetails/BusinessRegistrationNumbers/BusinessRegistrationNumber"),
        ("IMONumber", "IMO", "ShipDetails/IMONumbers/IMONumber"),
    )
    for tag, tipo, campo in _mapa:
        for nodo in _iter_local(des, tag):
            valor = _text(nodo)
            if valor:
                out.append(_ident(tipo, valor, campo))
    return tuple(out)


def _nombres_uk(des) -> List[str]:
    """[nombre principal, alias...] en el orden declarado por la fuente."""
    principal, alias = [], []
    contenedor = _find_local(des, "Names")
    if contenedor is None:
        return []
    for n in _iter_local(contenedor, "Name"):
        partes = []
        for i in range(1, 8):
            partes.append(_text(_find_local(n, f"Name{i}")))
        nombre = " ".join(p for p in partes if p).strip()
        if not nombre:
            continue
        tipo = _text(_find_local(n, "NameType")).lower()
        if tipo.startswith("primary"):
            principal.append(nombre)
        else:
            alias.append(nombre)
    return principal + alias


def _dob_uk(des):
    for dob in _iter_local(des, "DOB"):
        t = _text(dob)
        if t:
            return t
    return None


PARSERS = {
    "onu_xml": parse_un_consolidated,
    "ofac_sdn_xml": parse_ofac_sdn,
    "uk_sanctions_list_xml": parse_uk_sanctions_list,
}


def parse(source_parser: str, xml_bytes: bytes, lista_version: str = "") -> List[Any]:
    fn = PARSERS.get(source_parser)
    if fn is None:
        raise FuenteEstructuraNoReconocida(f"parser no implementado: {source_parser}")
    return fn(xml_bytes, lista_version)

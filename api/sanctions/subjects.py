# -*- coding: utf-8 -*-
"""Gate 1 — Canonical Subject Envelope (§1–§5).

El screening NUNCA se hace sobre strings sueltos del PDF: primero se resuelven
los sujetos a un envelope canónico y ese envelope es el ÚNICO insumo.

Reglas duras implementadas aquí:
  * `UNKNOWN != NATURAL_PERSON`: sin documento y sin forma societaria, el tipo
    queda UNKNOWN y se advierte; nunca se inventa "persona natural".
  * El tipo de persona de una persona jurídica NUNCA se decide solo porque el
    titulares sea una persona natural, ni por similitud de nombres.
  * Documento: se conserva la representación EXACTA extraída (p. ej.
    `1045718995X`) y, aparte, la forma normalizada para el cotejo.
  * Dos personas jurídicas NO se fusionan por similitud de nombre.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .contracts import (
    PERSON_LEGAL, PERSON_NATURAL, PERSON_UNKNOWN, SubjectEnvelope,
)

# ── Roles (§4) ───────────────────────────────────────────────────────────────
ROLE_TITULAR = "TITULAR_ACTUAL"
ROLE_VENDEDOR = "VENDEDOR"
ROLE_COMPRADOR = "COMPRADOR"
ROLE_ACREEDOR = "ACREEDOR_HIPOTECARIO"
ROLE_ACREEDOR_REAL = "ACREEDOR_REAL_DECLARADO"
ROLE_CONSTRUCTOR = "CONSTRUCTOR_ENAJENANTE"

# Roles que SÍ se screeningan en el dictamen inmobiliario (§4).
ROLES_SCREENED = (ROLE_TITULAR, ROLE_VENDEDOR, ROLE_COMPRADOR, ROLE_ACREEDOR,
                  ROLE_ACREEDOR_REAL, ROLE_CONSTRUCTOR)

MOTIVO_POR_ROL = {
    ROLE_TITULAR: "titular actual del inmueble (parte de la operación)",
    ROLE_VENDEDOR: "vendedor de la operación",
    ROLE_COMPRADOR: "comprador de la operación",
    ROLE_ACREEDOR: "acreedor hipotecario inscrito (contraparte financiera)",
    ROLE_ACREEDOR_REAL: "acreedor real declarado (posible cesión/no inscrito)",
    ROLE_CONSTRUCTOR: "constructor/enajenante original (material a la operación)",
}

# Advertencias de identidad (vocabulario cerrado).
W_DOC_MISSING = "DOCUMENT_MISSING"
W_PERSON_TYPE_UNKNOWN = "PERSON_TYPE_UNKNOWN"
W_PERSON_TYPE_FROM_LEGAL_FORM = "PERSON_TYPE_INFERRED_FROM_LEGAL_FORM"
W_DOC_NON_STANDARD = "DOCUMENT_NON_STANDARD_FORMAT"
W_NAME_PLACEHOLDER = "NAME_IS_PLACEHOLDER"
W_NOT_FUSED = "MULTIPLE_NAME_VARIANTS_NOT_FUSED"

_PLACEHOLDERS = {
    "", "N/D", "ND", "N.A", "NA", "NONE", "NULL", "PENDIENTE",
    "PENDIENTE DE VERIFICACION", "PENDIENTE DE VERIFICACIÓN",
    "PENDIENTE DE VERIFICACION (SIN CERTIFICADO CARGADO)",
    "PENDIENTE DE VERIFICACION (SIN PROPIETARIOS VIGENTES DETECTADOS)",
    "NO REGISTRA", "SIN DATO",
}

# Formas societarias / denominaciones que acreditan persona jurídica.
_LEGAL_TOKENS = {
    "SA", "SAS", "LTDA", "EU", "SCA", "SC", "CORP", "INC", "LLC", "GMBH",
    "FUNDACION", "SOCIEDAD", "BANCO", "BANCOLOMBIA", "FIDUCIARIA", "CORPORACION",
    "CONSTRUCTORA", "URBANIZADORA", "INMOBILIARIA", "COMPANIA", "CIA", "EMPRESA",
    "GRUPO", "COOPERATIVA", "ASOCIACION", "FONDO", "PATRIMONIO", "ENTIDAD",
    "SUCURSAL", "ESTABLECIMIENTO", "ALCALDIA", "MUNICIPIO", "NOTARIA",
    "MARVAL",  # marca usada como firma constructora en el caso Golden
}

_DOC_ALIASES = {
    "CC": "cc", "C.C": "cc", "CEDULA": "cc", "CEDULA DE CIUDADANIA": "cc",
    "NIT": "nit", "N.I.T": "nit",
    "CE": "ce", "C.E": "ce", "CEDULA DE EXTRANJERIA": "ce",
    "PASAPORTE": "pasaporte", "PASSPORT": "pasaporte",
    "TI": "ti", "T.I": "ti", "RC": "rc", "NUIP": "nuip",
}
_PERSONAL_DOCS = ("cc", "ce", "ti", "rc", "pasaporte", "nuip")

_RE_DOC = re.compile(
    r"(?i)\b(CC|C\.C\.?|CEDULA(?:\s+DE\s+CIUDADANIA)?|NIT|N\.I\.T\.?|CE|C\.E\.?|"
    r"PASAPORTE|PASSPORT|TI|T\.I\.?|RC|NUIP)\s*#?\s*[:.]?\s*([0-9][0-9A-Za-z\-]*)")
_RE_PARTICIPACION = re.compile(r"(\d{1,3}(?:[.,]\d{1,2})?)\s*%")


def strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def compact_abbrev(text: str) -> str:
    """'S.A.S.' -> 'SAS', 'C.C.' -> 'CC' (siglas con puntos intercalados)."""
    return re.sub(r"(?<=[A-Z])\.(?=[A-Z])", "", str(text or "").upper())


def match_key(name: str) -> str:
    """Clave de COTEJO: sin tildes, sin puntuación, mayúsculas."""
    t = compact_abbrev(strip_accents(name))
    t = re.sub(r"[^A-Z0-9\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def canonical_name(raw: str) -> str:
    """Nombre canónico para el DICTAMEN: como lo declara la fuente.

    Elimina documento y participación, colapsa espacios y quita separadores
    sobrantes, pero CONSERVA la representación declarada (tildes y el punto de
    las abreviaturas societarias: 'BANCO DE BOGOTÁ S.A.').
    """
    t = str(raw or "").strip()
    t = _RE_DOC.sub(" ", t)
    t = _RE_PARTICIPACION.sub(" ", t)
    t = re.sub(r"[\(\)\[\]]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t.strip(" ,;:-")


def _norm_tokens(name: str) -> set:
    return {tok for tok in match_key(name).split() if tok}


def normalize_document_number(tipo: Optional[str], numero: Optional[str]) -> Optional[str]:
    """Forma normalizada para cotejo (sin separadores, mayúsculas)."""
    if not numero:
        return None
    n = re.sub(r"[^0-9A-Za-z]", "", str(numero)).upper()
    if not n:
        return None
    # NIT con dígito de verificación "8600029644-4": el cotejo usa el cuerpo.
    if tipo == "nit" and "-" in str(numero):
        cuerpo = re.sub(r"[^0-9A-Za-z]", "", str(numero).split("-")[0]).upper()
        if cuerpo:
            return cuerpo
    return n


def document_variants(tipo: Optional[str], numero: Optional[str]) -> Tuple[str, ...]:
    """Variantes admisibles del documento para el cotejo (nunca inventa)."""
    base = normalize_document_number(tipo, numero)
    if not base:
        return ()
    out = [base]
    if tipo == "nit" and len(base) > 1:
        # NIT sin dígito de verificación y con él.
        out.append(base[:-1] if base[-1].isdigit() else base)
    return tuple(dict.fromkeys(v for v in out if v))


def person_type_from(name: str, tipo_documento: Optional[str]) -> Tuple[str, Tuple[str, ...]]:
    """Tipo de persona + advertencias. NUNCA asume 'natural' por defecto."""
    t = (tipo_documento or "").strip().lower()
    if t == "nit":
        return PERSON_LEGAL, ()
    if t in _PERSONAL_DOCS:
        return PERSON_NATURAL, ()
    tokens = _norm_tokens(name)
    if tokens & _LEGAL_TOKENS:
        return PERSON_LEGAL, (W_PERSON_TYPE_FROM_LEGAL_FORM,)
    if not tokens:
        return PERSON_UNKNOWN, (W_PERSON_TYPE_UNKNOWN, W_NAME_PLACEHOLDER)
    return PERSON_UNKNOWN, (W_PERSON_TYPE_UNKNOWN, W_DOC_MISSING)


def parse_person(raw: str) -> Dict[str, Any]:
    """Descompone un string del CTL en nombre/documento/participación.

    No corrige ni completa: conserva la representación EXACTA del número.
    """
    texto = str(raw or "").strip()
    participacion = None
    m_part = _RE_PARTICIPACION.search(texto)
    if m_part:
        participacion = f"{m_part.group(1)}%"
    m_doc = _RE_DOC.search(texto)
    tipo_doc = None
    numero = None
    if m_doc:
        clave = m_doc.group(1).upper().replace(".", "").strip()
        tipo_doc = _DOC_ALIASES.get(clave) or _DOC_ALIASES.get(m_doc.group(1).upper())
        numero = m_doc.group(2).strip()
    nombre = canonical_name(texto)
    warnings: List[str] = []
    if tipo_doc is None:
        warnings.append(W_DOC_MISSING)
    elif not re.fullmatch(r"\d{5,15}", numero or ""):
        warnings.append(W_DOC_NON_STANDARD)
    if "/" in nombre and len(nombre.split("/")[-1].split()) <= 3:
        # Dos denominaciones ("URBANIZADORA X / MARVAL"): NO se fusionan por
        # similitud; se conserva la cadena declarada y se advierte.
        warnings.append(W_NOT_FUSED)
    return {
        "raw_name": texto, "canonical_name": nombre, "document_type": tipo_doc,
        "document_number": numero,
        "document_normalized": normalize_document_number(tipo_doc, numero),
        "participation": participacion,
        "identity_warnings": tuple(dict.fromkeys(warnings)),
    }


def _es_placeholder(nombre: str) -> bool:
    return strip_accents(nombre).upper().strip() in _PLACEHOLDERS


def _subject_id(rol: str, nombre: str, doc: Optional[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", strip_accents(nombre).lower()).strip("-")[:40]
    return f"{rol.lower()}-{doc or base or 'sin-doc'}"

def _fuente_de_anotacion(analysis: Dict[str, Any], rol: str) -> Tuple[str, str]:
    """Provenance del sujeto dentro del CTL (anotación concreta, si se conoce)."""
    anots = analysis.get("anotaciones_detalle") or []
    for a in anots:
        tipo = str(a.get("tipo") or "").upper()
        if rol == ROLE_ACREEDOR and "HIPOTECA" in tipo:
            return "CTL — anotación con hipoteca vigente", str(a.get("num") or "")
        if rol == ROLE_TITULAR and "COMPRAVENTA" in tipo:
            return "CTL — anotación de compraventa vigente", str(a.get("num") or "")
    return "CTL — análisis del certificado", ""


def build_subject_envelopes(
    analysis: Dict[str, Any],
    identidad: Optional[Dict[str, Any]] = None,
    *,
    ciudad: str = "barranquilla",
) -> List[SubjectEnvelope]:
    """Resuelve el set canónico de sujetos del caso (Gate 1).

    Determinista y sin red. Devuelve SOLO envelopes; el llamador decide el
    screening (todos los de `ROLES_SCREENED` se screeningan).
    """
    analysis = analysis or {}
    identidad = identidad or {}
    crudos: List[Tuple[str, str, str, Optional[str]]] = []  # (rol, raw, conf, ref)

    # 1) Titular(es): análisis del CTL + modelo canónico (documento más fiable).
    _tit_can = identidad.get("titular") or {}
    if _tit_can.get("nombre"):
        _num = _tit_can.get("numero_documento")
        _tipo = _tit_can.get("tipo_documento")
        _raw = _tit_can["nombre"]
        if _num:
            _raw = f"{_raw} {str(_tipo or '').upper()}# {_num}".strip()
        crudos.append((ROLE_TITULAR, _raw, "VERIFIED_REGISTRAL", "modelo canónico (CTL)"))
    _titulares_txt = str(analysis.get("titulares") or "")
    if _titulares_txt and not _es_placeholder(_titulares_txt):
        for parte in re.split(r"\+|;", _titulares_txt):
            parte = parte.strip()
            if not parte or _es_placeholder(parte):
                continue
            _src, _ref = _fuente_de_anotacion(analysis, ROLE_TITULAR)
            crudos.append((ROLE_TITULAR, parte, "VERIFIED_REGISTRAL", f"{_src} {_ref}".strip()))

    # 2) Acreedor hipotecario (SNR) y acreedor real declarado (si difiere).
    _acr = str(analysis.get("acreedor_snr") or "").strip()
    if _acr and not _es_placeholder(_acr):
        _src, _ref = _fuente_de_anotacion(analysis, ROLE_ACREEDOR)
        crudos.append((ROLE_ACREEDOR, _acr, "VERIFIED_REGISTRAL",
                       f"{_src} {_ref}".strip()))
    _acr_real = str(analysis.get("acreedor_real") or "").strip()
    if _acr_real and not _es_placeholder(_acr_real) and _acr_real != _acr:
        crudos.append((ROLE_ACREEDOR_REAL, _acr_real, "VERIFIED_REGISTRAL",
                       "declaración del acreedor real (no inscrito)"))

    # 3) Constructor / enajenante (material a la operación).
    _const = str(analysis.get("constructor") or "").strip()
    if _const and _const.upper() not in ("N/D", "ND", "NONE", ""):
        crudos.append((ROLE_CONSTRUCTOR, _const, "VERIFIED_REGISTRAL",
                       "CTL — descripción del inmueble / enajenante original"))

    # ── Consolidación a envelopes ────────────────────────────────────────────
    envelopes: List[SubjectEnvelope] = []
    for rol, raw, conf, ref in crudos:
        datos = parse_person(raw)
        warnings = list(datos["identity_warnings"])
        tipo_persona, w_tipo = person_type_from(datos["canonical_name"],
                                                datos["document_type"])
        warnings.extend(w_tipo)
        if _es_placeholder(datos["canonical_name"]):
            warnings.append(W_NAME_PLACEHOLDER)
        crudo_tipo = (identidad.get("titular") or {}).get("tipo_persona")
        if rol == ROLE_TITULAR and crudo_tipo in (PERSON_NATURAL, PERSON_LEGAL):
            # El modelo canónico ya determinó el tipo (03D.1): es la autoridad.
            if crudo_tipo != tipo_persona:
                tipo_persona = crudo_tipo
                warnings = [w for w in warnings if w != W_PERSON_TYPE_UNKNOWN]
        screened = datos["canonical_name"] != "" and \
            not _es_placeholder(datos["canonical_name"])
        envelopes.append(SubjectEnvelope(
            subject_id=_subject_id(rol, datos["canonical_name"],
                                   datos["document_normalized"]),
            raw_name=datos["raw_name"], canonical_name=datos["canonical_name"],
            person_type=tipo_persona, document_type=datos["document_type"],
            document_number=datos["document_number"],
            document_normalized=datos["document_normalized"],
            roles=(rol,), participation=datos["participation"],
            source="CTL" if ref.startswith("CTL") else "MODELO_CANONICO",
            source_reference=ref,
            identity_confidence=conf if screened else "UNVERIFIED",
            identity_warnings=tuple(dict.fromkeys(warnings)),
            screened=screened,
            reason_for_screening=MOTIVO_POR_ROL.get(rol, "parte de la operación"),
            not_screened_reason=None if screened else "nombre no utilizable (N/D o marcador)",
        ))

    return _consolidar(envelopes)


def _documentos_compatibles(a: Optional[str], b: Optional[str]) -> bool:
    """¿Son el mismo documento declarado de dos formas? (1045718995 / 1045718995X)

    Solo se acepta cuando uno es prefijo del otro (mismo número, con un carácter
    adicional de la fuente). Nunca se "corrigen" documentos distintos.
    """
    if not a or not b:
        return False
    a, b = str(a).upper(), str(b).upper()
    corto, largo = (a, b) if len(a) <= len(b) else (b, a)
    return largo.startswith(corto) and len(largo) - len(corto) <= 2


def _mismo_sujeto(prev: SubjectEnvelope, env: SubjectEnvelope) -> bool:
    """¿Ambos envelopes son la MISMA contraparte?

    - Documento idéntico (o variantes del mismo número) -> misma contraparte.
    - Persona NATURAL con nombre canónico idéntico y documento compatible o
      ausente en alguno -> misma contraparte (mismo titular leído de dos fuentes:
      modelo canónico y texto del CTL).
    - Personas JURÍDICAS: JAMÁS por nombre. Solo por documento idéntico.
    """
    if prev.document_normalized and env.document_normalized:
        if prev.document_normalized == env.document_normalized:
            return True
        return (prev.person_type == PERSON_NATURAL
                and env.person_type == PERSON_NATURAL
                and match_key(prev.canonical_name) == match_key(env.canonical_name)
                and _documentos_compatibles(prev.document_normalized,
                                            env.document_normalized))
    if match_key(prev.canonical_name) and match_key(prev.canonical_name) == match_key(env.canonical_name):
        return (prev.person_type == PERSON_NATURAL and env.person_type == PERSON_NATURAL)
    return False


def _consolidar(envelopes: Sequence[SubjectEnvelope]) -> List[SubjectEnvelope]:
    """Fusiona la MISMA contraparte leída de varias fuentes, sumando roles."""
    out: List[SubjectEnvelope] = []
    for env in envelopes:
        _idx = None
        for i, prev in enumerate(out):
            if _mismo_sujeto(prev, env):
                _idx = i
                break
        if _idx is None:
            out.append(env)
            continue
        prev = out[_idx]
        roles = tuple(dict.fromkeys(prev.roles + env.roles))
        # Se conserva el documento MÁS COMPLETO de los dos declarados.
        _doc_num, _doc_norm = prev.document_number, prev.document_normalized
        if env.document_normalized and (not prev.document_normalized
                                        or len(env.document_normalized) > len(prev.document_normalized)):
            _doc_num, _doc_norm = env.document_number, env.document_normalized
        out[_idx] = SubjectEnvelope(
            subject_id=prev.subject_id, raw_name=prev.raw_name,
            canonical_name=prev.canonical_name,
            person_type=(prev.person_type if prev.person_type != PERSON_UNKNOWN
                         else env.person_type),
            document_type=prev.document_type or env.document_type,
            document_number=_doc_num, document_normalized=_doc_norm,
            roles=roles,
            participation=prev.participation or env.participation,
            source=prev.source, source_reference=prev.source_reference,
            identity_confidence=(prev.identity_confidence
                                 if prev.identity_confidence == "VERIFIED_REGISTRAL"
                                 else env.identity_confidence),
            identity_warnings=tuple(dict.fromkeys(
                prev.identity_warnings + env.identity_warnings)),
            screened=prev.screened or env.screened,
            reason_for_screening="; ".join(
                dict.fromkeys(MOTIVO_POR_ROL.get(r, "") for r in roles)).strip("; "),
            not_screened_reason=(prev.not_screened_reason or env.not_screened_reason),
        )
    # Orden determinista por rol y nombre (estable entre ejecuciones).
    _orden = {r: i for i, r in enumerate(ROLES_SCREENED)}
    out.sort(key=lambda e: (_orden.get(e.roles[0], 99), e.canonical_name))
    return out


def invitantes(envelopes: Sequence[SubjectEnvelope]) -> Dict[str, int]:
    """Invariante §5: declarados == screeningados + no_screeningados_con_motivo."""
    declarados = len(envelopes)
    screeningados = sum(1 for e in envelopes if e.screened)
    no_screeningados = declarados - screeningados
    return {"subjects_declared": declarados, "subjects_screened": screeningados,
            "subjects_not_screened_with_reason": no_screeningados}


def verificar_invariante(envelopes: Sequence[SubjectEnvelope]) -> None:
    """Lanza ValueError si el set canónico no cuadra (bloquea el dictamen)."""
    c = invitantes(envelopes)
    if c["subjects_declared"] != (c["subjects_screened"]
                                  + c["subjects_not_screened_with_reason"]):
        raise ValueError(
            "SUBJECT_SET_INVARIANT roto: declarados={} screeningados={} no_screeningados={}".format(
                c["subjects_declared"], c["subjects_screened"],
                c["subjects_not_screened_with_reason"]))
    for e in envelopes:
        if not e.screened and not e.not_screened_reason:
            raise ValueError(f"sujeto {e.subject_id} no screeningado sin motivo declarado")

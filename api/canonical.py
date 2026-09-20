# -*- coding: utf-8 -*-
"""
ARHIAX RE — Modelo canónico de identidad predial y contexto administrativo.

Este módulo es la ÚNICA fuente autoritativa que ensambla la identidad del predio
(canonical_property_identity) y su contexto administrativo
(administrative_context), con trazabilidad técnica por variable (provenance).

Consumido por: Titulux (pre-dictamen), GIS/riesgos, valoración, scoring y el
renderer del dictamen. El objetivo es que todos lean la MISMA identidad y no
cada módulo derive "su" folio/NUPRE/matrícula por su cuenta (lo que generaba
contradicciones como un TIT_B01 "falta folio/código" teniendo NUPRE resuelto).

Los builders son PURAS: reciben los insumos ya resueltos (análisis del CTL,
folio, predio real resuelto, candidato por nomenclatura, estado de identidad) y
no hacen llamadas de red. La red la hace el orquestador (compile_pdf); aquí solo
se normaliza, se elige la precedencia correcta y se documenta de dónde salió
cada valor.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

# ── Estados de resolución de identidad ────────────────────────────────────────
# Precedencia exigida (objetivo): NUPRE → código anterior → código corto →
# matrícula → nomenclatura → geometría (solo fallback) → nearest (último recurso).
ESTADO_MATCH_EXACT = "MATCH_EXACT"
ESTADO_MATCH_BY_NUPRE = "MATCH_BY_NUPRE"
ESTADO_MATCH_BY_PREDIAL_CODE = "MATCH_BY_PREDIAL_CODE"
ESTADO_MATCH_BY_MATRICULA = "MATCH_BY_MATRICULA"
ESTADO_MATCH_BY_NOMENCLATURA = "MATCH_BY_NOMENCLATURA"
ESTADO_MATCH_BY_GEOMETRY = "MATCH_BY_GEOMETRY"
ESTADO_NO_MATCH = "NO_MATCH"
ESTADO_MULTIPLE_MATCHES = "MULTIPLE_MATCHES"
ESTADO_IDENTITY_CONFLICT = "IDENTITY_CONFLICT"
ESTADO_NO_RECORD = "NO_RECORD"

# ── Confianza de identidad NORMALIZADA (única autoridad para el gate) ─────────
# Semántica mínima estable e independiente del vocabulario de cada ciudad. El
# gate de valoración (PH) y la trazabilidad consumen ESTOS valores, nunca los
# strings crudos del resolver (EXACT/PARTIAL/...) ni del orquestador por ciudad.
# (03D.1: `None`/`PARTIAL`/`AMBIGUOUS`/`UNRESOLVED`/`SPATIAL_CONTEXT_ONLY` NO
#  pueden convertirse silenciosamente en autorización para valorar una unidad PH.)
RESOLUTION_VERIFIED_UNIT = "VERIFIED_UNIT_IDENTITY"  # unidad específica verificada
RESOLUTION_PARTIAL = "PARTIAL_IDENTITY"              # candidato único sin match exacto
RESOLUTION_CONTEXT_ONLY = "CONTEXT_ONLY"             # solo contexto espacial (sin registro predial)
RESOLUTION_AMBIGUOUS = "AMBIGUOUS"                   # varios candidatos, ninguno exacto
RESOLUTION_UNRESOLVED = "UNRESOLVED"                 # sin registro / sin resolver
RESOLUTION_CONFLICT = "CONFLICT"                     # conflicto de identidad

# Estados del orquestador (Pasto) que equivalen a identidad VERIFICADA por
# identificador exacto o matrícula coincidente (no por proximidad).
_ESTADOS_VERIFICADOS = ("MATCH_EXACT", "MATCH_BY_NOMENCLATURA", "MATCH_BY_PREDIAL_CODE")

# ── Semántica de fallo por capa (GIS adapters, bug E/F) ───────────────────────
CAPA_MATCH_EXACT = "MATCH_EXACT"
CAPA_NO_MATCH = "NO_MATCH"
CAPA_NULL_VALUE = "NULL_VALUE"
CAPA_NOT_APPLICABLE = "NOT_APPLICABLE"
CAPA_NOT_EVALUATED = "NOT_EVALUATED"
CAPA_SOURCE_TIMEOUT = "SOURCE_TIMEOUT"
CAPA_SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
CAPA_SCHEMA_CHANGED = "SCHEMA_CHANGED"

# ── Tipo de persona ────────────────────────────────────────────────────────────
PERSONA_NATURAL = "NATURAL_PERSON"
PERSONA_JURIDICA = "LEGAL_ENTITY"

# Documentos de identidad que implican persona NATURAL (screening SAGRILAFT).
_DOC_NATURAL = {"cc", "ce", "ti", "rc", "pasaporte", "c.c.", "cédula", "cedula"}
_DOC_JURIDICA = {"nit", "n.i.t."}

# Expresión para "CC# 123" / "NIT 900.123.456-7" / "C.C. 123" en texto de CTL.
_DOC_RE = (
    r"(?i)\b(CC|C\.C\.?|C[ÉE]DULA|TI|T\.I\.?|RC|CE|PASAPORTE|NIT|N\.I\.T\.?)"
    r"\s*#?\s*([\d][\d\.\-]{3,20})"
)


def _norm_doc(tipo: str) -> str:
    t = (tipo or "").strip().lower().rstrip(".")
    if t in ("c.c", "cc", "cédula", "cedula"):
        return "cc"
    if t in ("t.i", "ti"):
        return "ti"
    if t == "rc":
        return "rc"
    if t == "ce":
        return "ce"
    if t == "pasaporte":
        return "pasaporte"
    if t in ("n.i.t", "nit"):
        return "nit"
    return t


def tipo_persona_de_documento(tipo_doc: str) -> Optional[str]:
    """NATURAL_PERSON / LEGAL_ENTITY a partir del documento canónico (o None)."""
    d = _norm_doc(tipo_doc)
    if not d:
        return None
    if d in ("cc", "ti", "rc", "ce", "pasaporte"):
        return PERSONA_NATURAL
    if d == "nit":
        return PERSONA_JURIDICA
    return None


def _extraer_sujeto_de_linea(linea: str) -> Optional[Dict[str, str]]:
    """De una línea 'NOMBRE ... CC# 123' extrae (nombre, tipo_documento, numero).

    Devuelve None si no hay documento identificable (sin documento NO se puede
    afirmar el tipo de persona; nunca se deduce NIT por defecto — bug I).
    """
    if not linea:
        return None
    m = re.search(_DOC_RE, linea)
    if not m:
        return None
    tipo = _norm_doc(m.group(1))
    numero = re.sub(r"[^0-9]", "", m.group(2))
    if not numero:
        return None
    # Nombre = lo que queda antes del documento, sin sufijos de porcentaje.
    nombre = linea[:m.start()]
    nombre = re.sub(r"\s*[XI]\s*$", "", nombre)
    nombre = re.sub(r"\s*\d{1,3}\s*%\s*$", "", nombre)
    nombre = " ".join(nombre.split()).strip(" .,;:")
    if len(nombre) < 3:
        return None
    return {"nombre": nombre, "tipo_documento": tipo, "numero_documento": numero}


def extraer_titular_canonico(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Titular canónico (nombre + documento + tipo de persona) desde el CTL.

    Prioridad:
      1) la anotación de COMPRAVENTA vigente más reciente (línea 'A:' con CC/NIT),
      2) el texto 'titulares' del analizador + el texto crudo del CTL.

    Regla de honestidad (bug I): si el documento NO aparece, se devuelve
    tipo_documento/tipo_persona en None (el screening NO asume persona jurídica
    por defecto; queda como sujeto de tipo indeterminado a verificar).
    """
    out: Dict[str, Any] = {
        "nombre": None, "tipo_documento": None, "numero_documento": None,
        "tipo_persona": None, "fuente": None,
    }

    # 1) Última compraventa vigente: de su bloque 'A:' extraer nombre + documento.
    for item in reversed(analysis.get("anotaciones_detalle") or []):
        if item.get("tipo") == "COMPRAVENTA" and "CANCELADA" not in (item.get("estado") or "").upper():
            texto = item.get("texto") or ""
            for line in texto.split("\n"):
                m = re.match(r"A\s*:\s*(.+)", line.strip(), re.IGNORECASE)
                if m:
                    sujeto = _extraer_sujeto_de_linea(m.group(1))
                    if sujeto and sujeto["tipo_documento"]:
                        out.update(sujeto)
                        out["fuente"] = f"anotacion compraventa {item.get('num')} (CTL)"
                        out["tipo_persona"] = tipo_persona_de_documento(sujeto["tipo_documento"])
                        return out
            break  # solo la última compraventa define al titular

    # 2) 'titulares' del analizador + texto crudo: buscar documento junto al nombre.
    titulares = (analysis.get("titulares") or "").strip()
    if titulares and not titulares.upper().startswith("PENDIENTE"):
        sujeto = _extraer_sujeto_de_linea(titulares)
        if sujeto:
            out.update(sujeto)
            out["fuente"] = "campo titulares del CTL"
            out["tipo_persona"] = tipo_persona_de_documento(sujeto["tipo_documento"])
            return out

    # 3) Buscar en el texto crudo cualquier 'NOMBRE ... CC# 123' (mejor esfuerzo).
    texto_ctl = analysis.get("texto_ctl") or ""
    m = re.search(_DOC_RE, texto_ctl or "")
    if m:
        # Tomar ~60 caracteres previos como candidato de nombre.
        ventana = texto_ctl[max(0, m.start() - 70):m.end()]
        lineas = [l for l in ventana.split("\n") if l.strip()]
        candidato = _extraer_sujeto_de_linea(lineas[-1] if lineas else ventana)
        if candidato:
            out.update(candidato)
            out["fuente"] = "texto crudo del CTL"
            out["tipo_persona"] = tipo_persona_de_documento(candidato["tipo_documento"])
            return out

    # 4) Nombre sin documento (lo que ya tenía el analizador): sin tipo de persona.
    if titulares and not titulares.upper().startswith("PENDIENTE"):
        out["nombre"] = " ".join(titulares.split()).strip(" .,;")
        out["fuente"] = "campo titulares del CTL (sin documento)"
    return out


def _traza(fuente: str, estado: str = "RESUELTO", metodo: Optional[str] = None,
           detalle: Optional[str] = None) -> Dict[str, Any]:
    """Registro de provenance por variable."""
    t: Dict[str, Any] = {"fuente": fuente, "estado": estado}
    if metodo:
        t["metodo"] = metodo
    if detalle:
        t["detalle"] = detalle
    return t


def _primero(*vals):
    for v in vals:
        if v not in (None, ""):
            return v
    return None


def _es_numero_predial(v: Any) -> bool:
    """True si el identificador tiene forma de número predial nacional (solo
    dígitos, 15-30): permite distinguirlo de un NUPRE alfanumérico (AFT...)."""
    s = str(v or "").strip()
    return bool(re.fullmatch(r"\d{15,30}", s))


def _resolver_status(predio_real: Optional[Dict[str, Any]]) -> Optional[str]:
    """Lee el resolution_status del resolver catastral (BAQ), normalizado.

    Puede vivir en `predio_real["predio"]["resolution_status"]` (BAQ) o en el
    nivel raíz. Devuelve None si el resolver de la ciudad no lo publica.
    """
    if not predio_real:
        return None
    s = (predio_real.get("predio") or {}).get("resolution_status")
    if s in (None, ""):
        s = predio_real.get("resolution_status")
    return s or None


def _estado_y_confianza(*, estado_identidad: Optional[str],
                        predio_real: Optional[Dict[str, Any]],
                        resolver_status: Optional[str],
                        resolucion: Optional[str],
                        metodo_resolucion: Optional[str],
                        matricula_coincide: bool) -> tuple:
    """Devuelve (estado, resolution_confidence) normalizados (03D.1).

    Reglas en orden de prioridad:
      1. conflicto explícito                         -> CONFLICT
      2. sin predio resuelto                         -> NO_RECORD / UNRESOLVED
      3. matrícula municipal == folio SNR            -> MATCH_EXACT / VERIFIED_UNIT
      4. resolver exacto por código/NUPRE            -> VERIFIED_UNIT
      5. estado del orquestador (Pasto) MATCH_*      -> VERIFIED_UNIT
      6. resolver PARTIAL                            -> PARTIAL (NO se promueve)
      7. resolver AMBIGUOUS                          -> AMBIGUOUS
      8. resolver UNRESOLVED                         -> UNRESOLVED
      9. solo espacial (punto / geometría)           -> CONTEXT_ONLY
     10. sin señal verificable                       -> UNRESOLVED (fail-closed)

    `estado` conserva la granularidad legada (ESTADO_*); `resolution_confidence`
    es la semántica normalizada ÚNICA que consume el gate de valoración.
    """
    if estado_identidad == ESTADO_IDENTITY_CONFLICT:
        return ESTADO_IDENTITY_CONFLICT, RESOLUTION_CONFLICT
    if predio_real is None:
        return ESTADO_NO_RECORD, RESOLUTION_UNRESOLVED
    if matricula_coincide:
        return ESTADO_MATCH_EXACT, RESOLUTION_VERIFIED_UNIT
    if resolver_status == "EXACT":
        estado = ESTADO_MATCH_BY_NUPRE if metodo_resolucion == "nupre" \
            else ESTADO_MATCH_BY_PREDIAL_CODE
        return estado, RESOLUTION_VERIFIED_UNIT
    if estado_identidad in _ESTADOS_VERIFICADOS:
        return estado_identidad, RESOLUTION_VERIFIED_UNIT
    if resolver_status == "PARTIAL":
        return ESTADO_MULTIPLE_MATCHES, RESOLUTION_PARTIAL
    if resolver_status == "AMBIGUOUS":
        return ESTADO_MULTIPLE_MATCHES, RESOLUTION_AMBIGUOUS
    if resolver_status == "UNRESOLVED":
        return ESTADO_NO_MATCH, RESOLUTION_UNRESOLVED
    if resolucion in ("por_punto", "por_punto_referencial") \
            or estado_identidad == "IDENTIDAD_PREDIAL_NO_RESUELTA":
        return ESTADO_MATCH_BY_GEOMETRY, RESOLUTION_CONTEXT_ONLY
    if metodo_resolucion == "nomenclatura_ct":
        return ESTADO_MATCH_BY_NOMENCLATURA, RESOLUTION_VERIFIED_UNIT
    if metodo_resolucion == "geometria":
        return ESTADO_MATCH_BY_GEOMETRY, RESOLUTION_CONTEXT_ONLY
    # Sin señal verificable (ciudad sin resolver_status ni estado del orquestador):
    # NO se afirma identidad por el solo hecho de tener NUPRE/código en el CTL.
    return ESTADO_NO_MATCH, RESOLUTION_UNRESOLVED


def _match_status(*, valor, resolver_status: Optional[str],
                  matricula_coincide: bool, estado_identidad: Optional[str],
                  es_espacial: bool) -> str:
    """Match status por identificador (03D.1): trazabilidad value/source/status."""
    if not valor:
        return "UNRESOLVED"
    if resolver_status in ("EXACT", "PARTIAL", "AMBIGUOUS", "UNRESOLVED"):
        return resolver_status
    if matricula_coincide:
        return "EXACT"
    if estado_identidad in _ESTADOS_VERIFICADOS:
        return "VERIFIED"
    if es_espacial or estado_identidad == "IDENTIDAD_PREDIAL_NO_RESUELTA":
        return "CONTEXT_ONLY"
    return "RESUELTO"


def _es_unidad_ph(cid: Dict[str, Any], ctx: Optional[Dict[str, Any]] = None) -> bool:
    """True si el activo es una UNIDAD de PH (03D.2).

    Señales (cualquiera basta): 'propiedad_horizontal' canónico True, o
    marcadores de unidad extraídos (torre/apartamento/unidad). La ausencia de
    marcadores de unidad NO desciende la exigencia de identidad.
    """
    if cid.get("propiedad_horizontal") is True:
        return True
    if ctx and ctx.get("propiedad_horizontal") is True:
        return True
    return bool(cid.get("torre") or cid.get("apartamento") or cid.get("unidad"))


def _detectar_ph(*, analysis: Dict[str, Any],
                 predio_real: Optional[Dict[str, Any]],
                 nom: Optional[Dict[str, Any]]) -> Optional[bool]:
    """Detección canónica de PH (03D.2): True / False / None (sin inventar).

    Evidencia autoritativa en orden de precedencia:
      1. candidato por nomenclatura (es_ph explícito del geoportal)
      2. condición jurídica del catastro (PROPIEDAD HORIZONTAL / NO ...)
      3. inferencia del CTL/SNR (inferir_condicion_juridica)
      4. marcadores de unidad extraídos (torre/apartamento/unidad)
      5. marcadores en dirección/descripción (APARTAMENTO/CONJUNTO/TORRE/...)

    Regla dura (03D.2): la AUSENCIA de extracción de torre/apartamento NO es
    evidencia de No PH. Sin evidencia positiva ni negativa se devuelve None.
    """
    # 1) nomenclatura municipal (explícito)
    if nom and nom.get("es_ph") is not None:
        return bool(nom.get("es_ph"))
    # 2) condición jurídica catastral
    _cond = ((predio_real or {}).get("condicion") or {}).get("condicion_juridica")
    if isinstance(_cond, str):
        _cu = _cond.upper()
        if "NO PROPIEDAD HORIZONTAL" in _cu:
            return False
        if "PROPIEDAD HORIZONTAL" in _cu:
            return True
    # 3) inferencia del CTL/SNR (fuente registral, todas las ciudades)
    from legal_analyzer import inferir_condicion_juridica
    _cond_ctl = inferir_condicion_juridica(
        analysis.get("texto_ctl"), analysis.get("descripcion_ctl"))
    if _cond_ctl:
        return "NO PROPIEDAD" not in _cond_ctl.upper()
    # 4) marcadores de unidad extraídos
    if analysis.get("torre") or analysis.get("apartamento") or analysis.get("unidad"):
        return True
    # 5) marcadores en dirección / descripción / nomenclatura
    _texto = " ".join([
        str(analysis.get("direccion") or ""),
        str(analysis.get("descripcion_ctl") or ""),
        str((nom or {}).get("nomenclatura") or ""),
    ]).upper()
    for _m in ("APARTAMENTO", "APTO", "CONJUNTO", "EDIFICIO", "TORRE",
               "UNIDAD", "P.H.", "PROPIEDAD HORIZONTAL"):
        if _m in _texto:
            return True
    return None


def can_value_property(canonical_identity: Optional[Dict[str, Any]],
                       property_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Autorización ÚNICA de valoración (03D.2).

    Devuelve {"allowed": bool, "reason": str|None, "identity_level": str}.
      * No PH (o sin evidencia de PH): procede (allowed=True); las precondiciones
        de tipología (suelo de protección / no construible / rural) son aparte.
      * PH: solo procede con identidad VERIFIED_UNIT_IDENTITY. NO_RECORD,
        NO_MATCH, PARTIAL, AMBIGUOUS, MULTIPLE_MATCHES, MATCH_BY_GEOMETRY,
        SPATIAL_CONTEXT_ONLY, IDENTITY_CONFLICT, UNKNOWN o None -> bloqueado.
    """
    cid = canonical_identity or {}
    es_ph = _es_unidad_ph(cid, property_context)
    conf = cid.get("resolution_confidence")
    nivel = conf or "UNKNOWN"
    if not es_ph:
        return {"allowed": True, "reason": None, "identity_level": nivel}
    if conf == RESOLUTION_VERIFIED_UNIT:
        return {"allowed": True, "reason": None,
                "identity_level": RESOLUTION_VERIFIED_UNIT}
    return {"allowed": False,
            "reason": "Identidad de la unidad inmobiliaria PH no resuelta de forma inequívoca.",
            "identity_level": nivel}


def unidad_ph_no_resuelta(canonical_identity: Optional[Dict[str, Any]]) -> bool:
    """Gate de valoración PH (03D.1/03D.2, única autoridad = identidad canónica).

    Devuelve True (bloquear estimación de mercado) cuando el activo es una
    UNIDAD PH y su identidad NO está verificada. Solo VERIFIED_UNIT_IDENTITY
    autoriza valorar. None / PARTIAL / AMBIGUOUS / UNRESOLVED / CONTEXT_ONLY /
    CONFLICT -> bloqueado (fail-closed).
    """
    return not can_value_property(canonical_identity)["allowed"]


def build_canonical_property_identity(
    *,
    analysis: Dict[str, Any],
    folio: str,
    predio_real: Optional[Dict[str, Any]],
    nom: Optional[Dict[str, Any]],
    identidad: Optional[Dict[str, Any]],
    ciudad: str,
    metodo_resolucion: Optional[str] = None,
) -> Dict[str, Any]:
    """Ensambla la identidad canónica del predio.

    Parámetros (todos ya resueltos por el orquestador, sin red aquí):
      analysis:      dict de legal_analyzer.analizar_certificado
      folio:         matrícula SNR resuelta (cadena '240-211101')
      predio_real:   dict de consultar_pasto/enriquecer_* (o None)
      nom:           candidato por nomenclatura del CTL (dict con 'nupre') o None
      identidad:     {'estado': ..., 'detalle': ...} del bloque de identidad
      ciudad:        'pasto' | 'barranquilla' | 'medellin' | 'bogota'
      metodo_resolucion: 'nupre' | 'codigo_predial' | 'nomenclatura_ct' |
                         'geometria' (si None se infiere).
    """
    predio = (predio_real or {}).get("predio") or {}

    # ── Separación de identificadores (03D.1 / BLOCKER C) ──────────────────────
    # 'nupre' y 'codigo_catastral' son identificadores DISTINTOS que nunca se
    # mezclan: número predial nacional (15-30 dígitos) vs NUPRE alfanumérico
    # (AFT.../NPR.../AAA...). Algunos geoportales (Pasto) nombran 'nupre' al
    # número predial; se detecta por su forma (solo dígitos) y se reclasifica a
    # codigo_catastral para no guardar un número predial dentro de 'nupre'.
    _p_nupre = predio.get("nupre")
    if _es_numero_predial(_p_nupre):
        _p_nupre = None
    _a_nupre = analysis.get("nupre")
    if _es_numero_predial(_a_nupre):
        _a_nupre = None
    _nom_nupre = (nom or {}).get("nupre")

    nupre = _primero(
        predio.get("codigo_homologado"),
        _p_nupre,
        _a_nupre,
    )
    if _nom_nupre and not _es_numero_predial(_nom_nupre):
        nupre = _primero(nupre, _nom_nupre)

    codigo_catastral = _primero(
        predio.get("numero_predial_nacional"),
        predio.get("numero_predial"),
        analysis.get("codigo_catastral"),
    )
    if _es_numero_predial(_nom_nupre):
        codigo_catastral = _primero(codigo_catastral, _nom_nupre)

    codigo_anterior = predio.get("codigo_predial_anterior")
    codigo_corto = predio.get("codigo_predial_corto")
    matricula_municipal = _primero(
        predio.get("matricula_inmobiliaria"),
        predio.get("matricula"),
    )
    nomenclatura = _primero(
        (nom or {}).get("nomenclatura"),
        predio.get("direccion_oficial"),
    )

    # ── Inferir método de resolución si no se pasó ──
    if metodo_resolucion is None:
        if nom and codigo_catastral and codigo_catastral == (nom or {}).get("nupre"):
            metodo_resolucion = "nomenclatura_ct"
        elif nupre:
            metodo_resolucion = "nupre"
        elif codigo_catastral:
            metodo_resolucion = "codigo_predial"
        elif predio_real is not None:
            metodo_resolucion = "geometria"
        else:
            metodo_resolucion = None

    # ── Estado + confianza normalizada (03D.1) ──────────────────────────────────
    detalle_identidad = (identidad or {}).get("detalle")
    estado_identidad = (identidad or {}).get("estado")
    resolver_status = _resolver_status(predio_real)
    resolucion = (predio_real or {}).get("resolucion")

    _m_muni = (matricula_municipal or "").replace(" ", "")
    _f = (str(folio) or "").replace(" ", "")
    matricula_coincide = bool(_m_muni and _f and _m_muni == _f)

    estado, resolution_confidence = _estado_y_confianza(
        estado_identidad=estado_identidad,
        predio_real=predio_real,
        resolver_status=resolver_status,
        resolucion=resolucion,
        metodo_resolucion=metodo_resolucion,
        matricula_coincide=matricula_coincide,
    )

    es_espacial = (resolucion in ("por_punto", "por_punto_referencial")
                   or metodo_resolucion == "geometria")

    titular = extraer_titular_canonico(analysis)

    # Propiedad horizontal (is_property_horizontal, 03D.2): detección canónica
    # multi-fuente. La ausencia de torre/apartamento extraídos NO es evidencia
    # de No PH (el parser pudo no encontrarlos).
    ph = _detectar_ph(analysis=analysis, predio_real=predio_real, nom=nom)

    # Identificadores con trazabilidad (value/source/match_status) — 03D.1.
    identificadores = {
        "nupre": {
            "value": nupre,
            "source": ("geoportal municipal (codigo_homologado)"
                       if (predio.get("codigo_homologado") or _p_nupre)
                       else ("CTL (NUPRE)" if _a_nupre else None)),
            "match_status": _match_status(
                valor=nupre, resolver_status=resolver_status,
                matricula_coincide=matricula_coincide,
                estado_identidad=estado_identidad, es_espacial=es_espacial),
        },
        "codigo_catastral": {
            "value": codigo_catastral,
            "source": ("geoportal municipal (numero_predial_nacional)"
                       if predio.get("numero_predial_nacional")
                       else ("CTL (CODIGO CATASTRAL)" if analysis.get("codigo_catastral")
                             else ("nomenclatura municipal" if _es_numero_predial(_nom_nupre) else None))),
            "match_status": _match_status(
                valor=codigo_catastral, resolver_status=resolver_status,
                matricula_coincide=matricula_coincide,
                estado_identidad=estado_identidad, es_espacial=es_espacial),
        },
    }

    trazas: Dict[str, Any] = {}
    trazas["nupre"] = _traza(
        "geoportal municipal (codigo_homologado)" if nupre else "no disponible",
        "RESUELTO" if nupre else "NULL_VALUE",
        metodo=metodo_resolucion,
    )
    trazas["codigo_catastral"] = _traza(
        "geoportal municipal (numero_predial_nacional)" if codigo_catastral else "no disponible",
        "RESUELTO" if codigo_catastral else "NULL_VALUE",
        metodo=metodo_resolucion,
    )
    trazas["matricula_snr"] = _traza(
        "CTL (SNR)" if folio and folio != "040-XXXXXX" else "no disponible",
        "RESUELTO" if folio and folio != "040-XXXXXX" else "NULL_VALUE",
    )
    trazas["matricula_municipal"] = _traza(
        "geoportal municipal (matricula_inmobiliaria)" if matricula_municipal else "no disponible",
        "RESUELTO" if matricula_municipal else "NULL_VALUE",
    )
    trazas["titular"] = _traza(
        titular.get("fuente") or "no disponible",
        "RESUELTO" if titular.get("nombre") else "NULL_VALUE",
    )

    return {
        "estado": estado,
        "metodo_resolucion": metodo_resolucion,
        # 03D.1: trazabilidad normalizada (resolver -> canonical -> gate).
        "resolution_status": resolver_status,
        "resolution_method": metodo_resolucion,
        "resolution_confidence": resolution_confidence,
        "ciudad": ciudad,
        "folio_snr": folio or None,
        "nupre": nupre,
        "codigo_catastral": codigo_catastral,
        "identificadores": identificadores,
        "codigo_anterior": codigo_anterior,
        "codigo_corto": codigo_corto,
        "matricula_municipal": matricula_municipal,
        "nomenclatura": nomenclatura,
        # Remediation 03D: dirección raw + base + unidad PH (sin pérdida de especificidad).
        "direccion_raw": analysis.get("direccion"),
        "direccion_base": analysis.get("direccion_base") or analysis.get("direccion"),
        "torre": analysis.get("torre"),
        "apartamento": analysis.get("apartamento"),
        "unidad": analysis.get("unidad"),
        "titular": titular,
        "propiedad_horizontal": ph,
        "detalle": detalle_identidad,
        "trazas": trazas,
    }


def build_administrative_context(
    *,
    ciudad: str,
    predio_real: Optional[Dict[str, Any]],
    nom: Optional[Dict[str, Any]],
    barrio: str = "",
    estrato=None,
) -> Dict[str, Any]:
    """Contexto administrativo canónico (comuna, barrio, estrato, suelo, uso).

    Fija la regla de precedencia administrativa: entorno resuelto del geoportal
    > candidato por nomenclatura (tabla de estratificación) > valor del registro
    > PENDIENTE (nunca se inventa). Con esto la comuna/estrato del dictamen y la
    de Titulux salen de la MISMA fuente (cierra bug B: 'Comuna N/D' vs 'Comuna 1').
    """
    entorno = (predio_real or {}).get("entorno") or {}

    comuna = _primero(
        entorno.get("comuna"),
        (nom or {}).get("comuna"),
    )
    barrio_final = _primero(
        entorno.get("barrio"),
        (nom or {}).get("barrio") or (nom or {}).get("sector"),
        barrio,
    )
    estrato_final = _primero(
        entorno.get("estrato"),
        (nom or {}).get("estrato"),
        estrato,
    )

    ctx = {
        "ciudad": ciudad,
        "comuna": comuna,
        "barrio": barrio_final,
        "estrato": estrato_final,
        "clase_suelo": entorno.get("clase_suelo"),
        "area_actividad": entorno.get("area_actividad"),
        "uso_economico": entorno.get("uso_economico"),
        "tratamiento": entorno.get("tratamiento"),
        "edificabilidad_texto": entorno.get("edificabilidad_texto"),
        "trazas": {
            "comuna": _traza(
                "geoportal (DPA / tabla estratificacion)" if comuna else "no disponible",
                "RESUELTO" if comuna else "NULL_VALUE",
            ),
            "barrio": _traza(
                "geoportal (DPA sector)" if entorno.get("barrio") else ("tabla estratificacion" if (nom or {}).get("barrio") else "registro"),
                "RESUELTO" if barrio_final else "NULL_VALUE",
            ),
            "estrato": _traza(
                "geoportal (tabla estratificacion)" if (entorno.get("estrato") or (nom or {}).get("estrato")) else ("registro" if estrato_final else "no disponible"),
                "RESUELTO" if estrato_final is not None else "NULL_VALUE",
            ),
        },
    }
    return ctx

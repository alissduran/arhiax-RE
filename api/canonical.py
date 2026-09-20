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

    nupre_resuelto = _primero(
        predio.get("numero_predial_nacional"),
        predio.get("nupre"),
        (nom or {}).get("nupre"),
    )
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
        if nom and nupre_resuelto and nupre_resuelto == (nom or {}).get("nupre"):
            metodo_resolucion = "nomenclatura_ct"
        elif analysis.get("nupre"):
            metodo_resolucion = "nupre"
        elif analysis.get("codigo_catastral"):
            metodo_resolucion = "codigo_predial"
        elif predio_real is not None:
            metodo_resolucion = "geometria"
        else:
            metodo_resolucion = None

    # ── Estado de resolución ──
    estado = None
    detalle_identidad = (identidad or {}).get("detalle")
    if identidad and identidad.get("estado") == ESTADO_IDENTITY_CONFLICT:
        estado = ESTADO_IDENTITY_CONFLICT
    elif predio_real is None:
        estado = ESTADO_NO_RECORD
    elif metodo_resolucion == "nupre":
        estado = ESTADO_MATCH_BY_NUPRE
    elif metodo_resolucion == "codigo_predial":
        estado = ESTADO_MATCH_BY_PREDIAL_CODE
    elif metodo_resolucion == "nomenclatura_ct":
        estado = ESTADO_MATCH_BY_NOMENCLATURA
    elif metodo_resolucion == "geometria":
        estado = ESTADO_MATCH_BY_GEOMETRY
    else:
        estado = ESTADO_NO_MATCH

    # MATCH_EXACT cuando la matrícula municipal coincide con el folio SNR.
    if estado not in (ESTADO_IDENTITY_CONFLICT, ESTADO_NO_RECORD):
        _m_muni = (matricula_municipal or "").replace(" ", "")
        _f = (folio or "").replace(" ", "")
        if _m_muni and _f and _m_muni == _f:
            estado = ESTADO_MATCH_EXACT

    titular = extraer_titular_canonico(analysis)

    # Propiedad horizontal: del candidato por nomenclatura o inferida del CTL.
    ph = None
    if nom and nom.get("es_ph") is not None:
        ph = bool(nom.get("es_ph"))
    elif predio_real is not None:
        _cond = (predio_real.get("condicion") or {}).get("condicion_juridica")
        if isinstance(_cond, str) and "PROPIEDAD HORIZONTAL" in _cond.upper():
            ph = True

    trazas: Dict[str, Any] = {}
    trazas["nupre"] = _traza(
        "geoportal municipal (codigo_predial_nacional)" if nupre_resuelto else "no disponible",
        "RESUELTO" if nupre_resuelto else "NULL_VALUE",
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
        "ciudad": ciudad,
        "folio_snr": folio or None,
        "nupre": nupre_resuelto,
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

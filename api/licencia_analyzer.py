# -*- coding: utf-8 -*-
"""
ARHIAX RE — Analizador de Licencias de Construcción (Sprint 3, mejora 5)
========================================================================
Extrae los parámetros autorizados de una licencia de construcción colombiana
(PDF) — número, modalidad, curaduría/entidad, PISOS aprobados, altura, área y
fecha — para que el dictamen compare lo LICENCIADO contra lo CONSTRUIDO
(catastro) y contra la norma urbanística del POT (sección 4.3).

Honestidad: las licencias de las curadurías urbanas NO tienen un formato
único nacional. Si un dato no se identifica con certeza queda None (el
dictamen lo marca PENDIENTE/verificación manual); nunca se inventa un número
de pisos autorizado. El dictamen NO sustituye la lectura de la licencia por
el profesional: es una alerta temprana de incoherencias.
"""
import re
from pathlib import Path

import pypdf

# Patrones de número de licencia (varía por curaduría): p. ej.
#   'LICENCIA DE CONSTRUCCION No. LC-19-000123'
#   'LICENCIA No. 01-2-1234-2019'
#   'LICENCIA URBANISTICA 2020-1234'
_RE_NUMERO = re.compile(
    r"LICENCIA\s+(?:DE\s+CONSTRUCCI[OÓ]N\s*|URBAN[IÍ]STICA\s*)?"
    r"(?:No\.?|N[°º]?\.?|NRO\.?|NUMERO|#)?\s*[:\-.\s]*"
    r"([A-Z0-9]{2,4}[-/]?\s*\d{2,4}[-/]?\s*\d{2,8}|[A-Z]{1,3}\d{3,12})",
    re.IGNORECASE)

_RE_MODALIDAD = re.compile(
    r"\b(obra nueva|ampliaci[oó]n|adecuaci[oó]n|remodelaci[oó]n|restauraci[oó]n|"
    r"modificaci[oó]n|cerramiento|urbanizaci[oó]n|parcelaci[oó]n|reforzamiento|"
    r"reconstrucci[oó]n)\b", re.IGNORECASE)

# Número de pisos/niveles/plantas autorizados (con o sin paréntesis):
#   'edificacion de (5) pisos', 'construccion de 4 niveles', 'hasta 12 pisos'
_RE_PISOS = re.compile(
    r"(?:de\s+|hasta\s+|m[aá]ximo\s+|m[aá]x\.?\s+|autoriza\s+(?:la\s+)?"
    r"construcci[oó]n\s+(?:de\s+)?|con\s+|por\s+)?"
    r"[(\[]?\s*(\d{1,2})\s*[)\]]?\s*"
    r"(?:pisos|niveles|plantas|pavimentos|alturas)", re.IGNORECASE)

# Altura aprobada: 'altura de 36 m', '36.5 metros de altura', 'h: 36 m'
_RE_ALTURA = re.compile(
    r"altura\s*(?:m[aá]xima\s*|aprobada\s*|de\s*|:\s*)?[(\[]?\s*"
    r"(\d{1,3}(?:[.,]\d{1,2})?)\s*[)\]]?\s*(?:m\b|metros|mts)",
    re.IGNORECASE)

# Curaduría urbana / entidad que expide
_RE_CURADURIA = re.compile(
    r"(?:curadur[ií]a urbana|curadur[ií]a)\s*(?:n[°º]?\.?\s*|no\.?\s*)?(\d{1,2})",
    re.IGNORECASE)

# Fecha de expedición (dd/mm/aaaa o dd-mm-aaaa cerca de 'expedida/fecha')
_RE_FECHA = re.compile(
    r"(?:expedid[oa]\s+(?:el\s+)?|fecha\s*(?:de\s+expedici[oó]n|expedici[oó]n)?\s*[:\-]?\s*)"
    r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})", re.IGNORECASE)


def _texto_de(pdf_path) -> str:
    reader = pypdf.PdfReader(str(pdf_path))
    partes = []
    for page in reader.pages:
        t = page.extract_text()
        if t:
            partes.append(t)
    return "\n".join(partes)


def _primer_grupo(patron, texto):
    m = patron.search(texto)
    if not m:
        return None
    for g in m.groups():
        if g:
            return g
    return m.group(0)


def analizar_licencia(pdf_path):
    """Analiza un PDF de licencia de construcción.

    Retorna dict:
      disponible, numero_licencia, modalidad, curaduria, pisos_aprobados,
      altura_aprobada_m, area_aprobada_m2, fecha_expedicion, error.
    Los campos no identificados quedan None (nunca se inventan).
    """
    res = {"disponible": False, "error": None, "numero_licencia": None,
           "modalidad": None, "curaduria": None, "pisos_aprobados": None,
           "altura_aprobada_m": None, "area_aprobada_m2": None,
           "fecha_expedicion": None}
    if not pdf_path or not Path(pdf_path).exists():
        res["error"] = "sin archivo de licencia"
        return res
    try:
        texto = _texto_de(pdf_path)
    except Exception as e:
        res["error"] = "no se pudo leer el PDF: {}".format(e)
        return res
    if not texto or not texto.strip():
        res["error"] = "PDF sin texto extraíble"
        return res

    res["numero_licencia"] = _primer_grupo(_RE_NUMERO, texto)
    res["modalidad"] = _primer_grupo(_RE_MODALIDAD, texto)
    res["curaduria"] = _primer_grupo(_RE_CURADURIA, texto)
    res["fecha_expedicion"] = _primer_grupo(_RE_FECHA, texto)

    # Pisos aprobados: validar que el número sea razonable (1-60) para no tomar
    # un número suelto del texto (p. ej. un año o un área).
    m_pisos = _RE_PISOS.search(texto)
    if m_pisos:
        try:
            n = int(m_pisos.group(1))
            if 1 <= n <= 60:
                res["pisos_aprobados"] = n
        except (TypeError, ValueError):
            pass

    m_alt = _RE_ALTURA.search(texto)
    if m_alt:
        try:
            a = float(m_alt.group(1).replace(",", "."))
            if 1.5 <= a <= 400:
                res["altura_aprobada_m"] = round(a, 2)
        except (TypeError, ValueError):
            pass

    # Área aprobada (m2) asociada a 'construccion/obra'
    m_area = re.search(
        r"(?:[aá]rea\s+(?:aprobada|de\s+construcci[oó]n|construida)\s*[:\-]?\s*)"
        r"(\d{2,6}(?:[.,]\d{1,2})?)\s*(?:m2|mts2|metros\s+cuadrados)",
        texto, re.IGNORECASE)
    if m_area:
        try:
            ar = float(m_area.group(1).replace(",", "."))
            if 5 <= ar <= 100000:
                res["area_aprobada_m2"] = round(ar, 2)
        except (TypeError, ValueError):
            pass

    res["disponible"] = bool(res["numero_licencia"] or res["pisos_aprobados"]
                             or res["modalidad"])
    return res

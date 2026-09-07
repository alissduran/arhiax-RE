# -*- coding: utf-8 -*-
"""
ARHIAX TMA — Ecosistema de Gobernanza de Datos
Módulo: Normalizador de Direcciones Urbanas para Catastro (Barranquilla)
Estándar de Codificación: ARHIAX-RE v1.0
"""

import re

# Sufijos de mejora/uso que en la nomenclatura SNR suelen acompañar la placa
# (p. ej. "CL 40 # 50B - 62 BDGA 3" o "... TORRE 2 APTO 501"). NO son parte de
# la placa catastral: se recorta todo lo que sigue a la primera palabra de
# mejora. "CASA" se excluye a propósito (puede ser parte real de la
# nomenclatura en desarrollos).
_RE_SUFIJO_MEJORA = re.compile(
    r"\s+(?:BDGA\b|BODEGAS?\b|LOCAL\b|LOC\b|OFICINA\b|OF\b|APTO\b|APARTAMENTO\b|APT\b|"
    r"TORRE\b|INTERIOR\b|INT\b|PISO\b|EDIFICIO\b|ED\b|BLOQUE\b|BL\b|CONJUNTO\b|CONJ\b|"
    r"UNIDAD\b|MEJORA\b|MEJ\b|MODULO\b|MOD\b).*$",
    re.IGNORECASE,
)

# Prefijos de listado que traen las direcciones del CTL/SNR ("2) ", "1. ", "- ")
_RE_PREFIJO_LISTADO = re.compile(r"^\s*(?:\d+\s*[\)\-\u2013.]|[-–—•·])\s*")

# Indicadores de número: "No. 61", "N° 61", "Nro 61" -> "# 61" (para catastro).
# Sin \b final: tras '.' o '°' no existe límite de palabra.
_RE_NO_INDICADOR = re.compile(
    r"\b(?:No\.?|N[°º]?\.?|Nro\.?|Número|NUMERO|Num)(?=\s|$)",
    re.IGNORECASE)


def limpiar_direccion_consulta(direccion: str) -> str:
    """Limpia una dirección para CONSULTA catastral sin alterar la original.

    Reglas (Sprint 3 — geocoder por dirección):
      1. Quita prefijos de listado del CTL/SNR: '2) ', '1. ', '- '.
      2. Quita sufijos de mejora tras la placa: 'BDGA 3', 'LOCAL 2', 'TORRE A'.
      3. Convierte indicadores de número ('No.', 'N°', 'Nro') en '#'.
      4. Compacta letras pegadas al guion de placa: '50 B - 62' -> '50B - 62'
         (el formato SNR separa la letra con espacios: '50 B - 62').
      5. Normaliza espacios múltiples.

    Ejemplos:
      '2) CL 40 # 50 B - 62 BDGA 3'  -> 'CL 40 # 50B - 62'
      'Calle 10 No. 43B - 43 Local 1' -> 'Calle 10 # 43B - 43'
    """
    if not direccion:
        return ""
    txt = direccion.strip()
    txt = _RE_PREFIJO_LISTADO.sub("", txt)
    txt = _RE_SUFIJO_MEJORA.sub("", txt)
    txt = _RE_NO_INDICADOR.sub("# ", txt)
    # '50 B - 62' -> '50B - 62'  (letra de placa pegada al número)
    txt = re.sub(r"(\d)\s+([A-Za-z])\s*[-–—]", r"\1\2 -", txt)
    txt = re.sub(r"\s*[-–—]\s*", " - ", txt)
    return " ".join(txt.split()).strip(" .,;")

def normalize_address_colombia(address: str) -> str:
    """
    Normaliza una dirección urbana colombiana al formato estándar requerido por
    los portales catastrales y prediales (especialmente Barranquilla).
    
    Aplica las siguientes reglas de estandarización:
    1. Conversión a mayúsculas y limpieza de espacios en blanco múltiples.
    2. Homogenización de abreviaturas principales (Calle -> CL, Carrera -> CRA, etc.).
    3. Remoción de palabras vacías o redundantes de nomenclatura (No, N°, No., Num).
    4. Estandarización de espaciado alrededor de caracteres especiales (# y -).
    5. Limpieza de caracteres de puntuación innecesarios (puntos, comas).
    """
    if not address:
        return ""
        
    # 1. Pasar a mayúsculas y decodificar caracteres raros
    addr = address.upper().strip()
    
    # 2. Reemplazar comas, puntos y caracteres especiales comunes
    addr = addr.replace(".", " ").replace(",", " ")
    
    # 3. Normalizar prefijos viales principales
    addr = re.sub(r"\b(CALLE|CLL|CLLE)\b", "CL", addr)
    addr = re.sub(r"\b(CARRERA|CRA|CABRERA|CR|KRA|KR)\b", "CRA", addr)
    addr = re.sub(r"\b(AVENIDA|AVE)\b", "AV", addr)
    addr = re.sub(r"\b(DIAGONAL|DIAG|DG)\b", "DG", addr)
    addr = re.sub(r"\b(TRANSVERSAL|TRANS|TRAV|TV)\b", "TV", addr)
    addr = re.sub(r"\b(AUTOPISTA|AUTOP|AP)\b", "AP", addr)
    
    # 4. Normalizar indicadores de número (No, N°, #, No., etc.)
    # Remove degree symbols and ordinal indicators first to avoid encoding issues
    addr = re.sub(r"[\u00b0\u00ba\u00aa\u00b2\u00b3]", " ", addr)
    # Remove words like "NUMERO", "NRO", "NUM", "NO", or "N" as standalone words
    addr = re.sub(r"\b(NUMERO|NRO|NUM|NO|N)\b", " ", addr)
    
    # 5. Asegurar que haya un símbolo '#' de separación
    if "#" not in addr:
        parts = addr.split()
        # Find indices of parts that contain digits
        digit_indices = [i for i, part in enumerate(parts) if re.search(r"\d", part)]
        
        if digit_indices:
            # If the first number is the second word (e.g. "CL 72 ...")
            if digit_indices[0] == 1 and len(digit_indices) > 1:
                # The first number is the street. The second number is the plate.
                # We insert '#' before the second number.
                idx_to_insert = digit_indices[1]
                parts.insert(idx_to_insert, "#")
            else:
                # The first number is the plate (e.g. "AV CIRCUNVALAR 110 ...")
                # We insert '#' before the first number.
                idx_to_insert = digit_indices[0]
                parts.insert(idx_to_insert, "#")
            addr = " ".join(parts)
 
    # 6. Estandarizar espaciado de '#' y '-'
    addr = re.sub(r"\s*#\s*", " # ", addr)
    # Insert hyphen if we have space-separated numbers after '#'
    addr = re.sub(r"#\s*(\d+[A-Z]?)\s+(\d+)\b", r"# \1 - \2", addr)
    addr = re.sub(r"\s*-\s*", " - ", addr)
    
    # 7. Colapsar espacios múltiples finales
    addr = " ".join(addr.split())
    
    return addr

# -*- coding: utf-8 -*-
"""DICTUS 2.0 — Capa de HISTORIA y CONSISTENCIA del expediente (§C, §D, §V).

Qué resuelve
------------
Un mismo inmueble puede haber sido dictaminado varias veces. Entre versiones pueden
cambiar hechos materiales (altura normativa, tratamiento, uso, valor, identidad…) **sin
que nadie lo declare**. Este módulo:

  1. extrae, de cada versión histórica disponible, un conjunto fijo de ATRIBUTOS
     (valor + la declaración de fuente que el propio documento imprime);
  2. construye la **ATTRIBUTE HISTORY MATRIX** con VERSION / VALUE / SOURCE /
     SOURCE_VERSION / QUERY_DATE / PROVENANCE / IDENTITY_BINDING / STATUS;
  3. clasifica cada cambio entre versiones (`SOURCE_UPDATE`, `METHODOLOGY_UPDATE`,
     `IDENTITY_CHANGE`, `GEOMETRY_CHANGE`, `SOURCE_UNAVAILABLE`, `PARSER_CHANGE`,
     `INTERPRETATION_CHANGE`, `UNEXPLAINED_CONFLICT`);
  4. emite el **HISTORICAL CONSISTENCY REPORT** y, para cualquier atributo material cuyo
     valor haya cambiado sin explicación verificable, lo marca
     **`HISTORICAL_CONFLICT`** — estado que el render ejecutivo NO puede presentar como
     `VERIFICADO` (Urban Consistency Gate, §D).

Principio: **no se elige un valor**. Si el expediente produjo resultados distintos para
el mismo predio, el conflicto se muestra; la cifra definitiva no se imprime como hecho.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

# ── Estados de coherencia (vocabulario cerrado) ────────────────────────────────
VERIFICADO = "VERIFICADO"
CAMBIO_CON_FUENTE = "CAMBIO_CON_FUENTE"
HISTORICAL_CONFLICT = "HISTORICAL_CONFLICT"
REQUIERE_VALIDACION = "REQUIERE_VALIDACION"
NO_COMPARABLE = "NO_COMPARABLE"
SIN_DATO = "SIN_DATO"

# ── Clases de cambio (§C) ─────────────────────────────────────────────────────
SOURCE_UPDATE = "SOURCE_UPDATE"
METHODOLOGY_UPDATE = "METHODOLOGY_UPDATE"
IDENTITY_CHANGE = "IDENTITY_CHANGE"
GEOMETRY_CHANGE = "GEOMETRY_CHANGE"
SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
PARSER_CHANGE = "PARSER_CHANGE"
INTERPRETATION_CHANGE = "INTERPRETATION_CHANGE"
UNEXPLAINED_CONFLICT = "UNEXPLAINED_CONFLICT"

# Atributos materiales: si cambian sin explicación, bloquean el estado VERIFICADO.
ATRIBUTOS_MATERIALES = frozenset({
    "altura_maxima", "tratamiento", "uso_pot", "destino_economico", "area",
    "regimen_juridico", "estrato", "riesgo", "amenaza", "valor_central",
    "numero_predial", "nupre", "matricula", "unidad", "coordenada", "barrio",
})

# Atributos urbanísticos: sujetos al Urban Consistency Gate (§D).
ATRIBUTOS_URBANISTICOS = frozenset({"altura_maxima", "tratamiento", "uso_pot",
                                    "clase_suelo", "planes_parciales"})

# Palabras que EXPLICAN un cambio de valor: la fuente o el método declarados cambian.
_MARCAS_EXPLICATIVAS = (
    "en vivo", "empaquetad", "capa oficial", "geojson", "demo", "simulad",
    "estimad", "referencial", "fallback", "matriz", "capa 500", "capa 105",
    "servicio", "arcgis", "lonja", "metodolog", "pendiente", "sin registrar",
)


def _norm(txt: Any) -> str:
    """Texto normalizado: sin tildes, en mayúsculas, espacios simples."""
    import unicodedata
    s = unicodedata.normalize("NFKD", str(txt or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.upper().split())


def _limpio(valor: Any) -> Optional[str]:
    """Valor legible y comparable. Los huecos DECLARADOS cuentan como AUSENCIA.

    Importante para la historia: «PENDIENTE (capa oficial sin resolver)» no es un valor
    distinto de «Habitacional»: es la ausencia de ese dato en esa ejecución. Tratarlo
    como valor generaba contradicciones falsas.
    """
    if valor is None:
        return None
    v = " ".join(str(valor).split()).strip(" .;,:|-")
    if not v:
        return None
    n = _norm(v)
    if n in ("N/D", "ND", "NO DISPONIBLE", "PENDIENTE", "SIN DATO", "NO APLICA", "N/A",
             "NONE", "NULL", "NO EVALUADO", "SIN REGISTRO"):
        return None
    for prefijo in ("PENDIENTE ", "PENDIENTE DE", "NO DISPONIBLE", "SIN DATO",
                    "SIN REGISTRO", "NO EVALUADO", "NO RESUELTO", "SIN RESOLVER"):
        if n.startswith(prefijo):
            return None
    return v


def _comparable(valor: Optional[str]) -> Optional[str]:
    """Forma canónica para COMPARAR dos valores del mismo atributo."""
    if valor is None:
        return None
    v = _norm(valor)
    v = re.sub(r"\(([^)]*)\)", r"\1", v)          # unifica "(Nivel 2)" y "Nivel 2"
    v = re.sub(r"[^0-9A-Z]+", " ", v)
    return " ".join(v.split())


# Marcas de PROCEDENCIA: dos valores solo se consideran "explicados" si la procedencia
# declarada cambia de verdad (no si cambia la redacción).
_MARCAS_DEMO = ("DEMO", "GMAPS", "SAT", "GEOCOD", "BARRIO", "CENTROID", "REFERENCIAL",
                "SIMULAD", "EMPAQUETAD", "GEOJSON", "ESTIMAD")
_MARCAS_OFICIAL = ("OFICIAL", "OFFICIAL_PREDIO", "CAPA 105", "CAPA 500", "ARCGIS",
                   "EN VIVO", "SERVICIO", "POT", "CAT ASTRO", "CATASTRO")
_MARCAS_DEMO_SET = frozenset(_MARCAS_DEMO)
_MARCAS_OFICIAL_SET = frozenset(_MARCAS_OFICIAL)


def _marcas(texto: Any) -> set:
    t = _norm(texto)
    return ({m for m in _MARCAS_DEMO if m in t} | {m for m in _MARCAS_OFICIAL if m in t})


def _clave(atributo: str, valor: Optional[str]) -> Any:
    """Clave de comparación del atributo (evita falsos cambios por redacción)."""
    if valor is None:
        return None
    if atributo == "altura_maxima":
        # Solo los NÚMEROS de pisos importan: "Hasta 8 pisos (capa oficial…)" → {8}
        nums = {int(n) for n in re.findall(r"(\d{1,3})\s*pisos", _norm(valor))}
        return frozenset(nums) or frozenset({_comparable(valor)})
    if atributo in ("tratamiento", "uso_pot", "clase_suelo", "regimen_juridico",
                    "destino_economico"):
        v = _norm(valor)
        v = re.split(r"--|\bSEGUN\b|\bSEGÚN\b|\(|\[", v)[0]
        v = re.sub(r"[^0-9A-Z]+", " ", v).strip()
        return frozenset({v}) if v else None
    if atributo == "coordenada":
        return frozenset(re.findall(r"-?\d+[\.,]\d+", _norm(valor)))
    return frozenset({_comparable(valor)})


# ── Extracción por atributo ───────────────────────────────────────────────────
# Cada entrada: nombre -> (patrones que capturan el valor, patrón de declaración)
_ATRIBUTOS: Dict[str, Dict[str, Any]] = {
    "direccion": {
        "patrones": [r"direccion(?: oficial)?\s*[:\-]\s*([^\n]{6,120})",
                     r"direcci[oó]n seg[uú]n ctl[^\n]*\n([^\n]{6,120})"],
    },
    "unidad": {"patrones": [r"unidad\s*[:\-]\s*((?:TO|TORRE|AP|APTO|APARTAMENTO|CASA|"
                            r"LOCAL|OFICINA|BODEGA|GARAJE|PARQUEADERO)\s*[\w\s]{0,20}\d+[^\n]{0,20})"],
               "derivado": r"\b(?:TO|TORRE)\s*(\d+)\s*(?:AP|APTO|APARTAMENTO)\s*(\d+)"},
    "matricula": {"patrones": [r"matr[ií]cula(?:\s+inmobiliaria)?\s*[:\-]?\s*([0-9]{2,3}[A-Z]?-\d{3,12})",
                               r"\b(\d{3}-\d{6})\b"]},
    "nupre": {"patrones": [r"nupre\s*[:\-]?\s*([A-Z]{3}[0-9A-Z]{4,20})"]},
    "numero_predial": {"patrones": [r"c[oó]digo catastral\s*[:\-]?\s*(\d{15,30})",
                                    r"n[uú]mero predial\s*[:\-]?\s*(\d{15,30})"]},
    "area": {"patrones": [r"area (?:privada|registrada|construida)\s*\n?\s*([\d]{1,5}[.,]\d{1,2})\s*m",
                          r"([\d]{1,5}[.,]\d{1,2})\s*m2\s*\(ph\)"]},
    "regimen_juridico": {"patrones": [r"condici[oó]n jur[ií]dica\s*\n?\s*([^\n]{6,80})",
                                      r"r[eé]gimen(?: jur[ií]dico)?\s*[:\-]\s*([^\n]{6,80})"]},
    "destino_economico": {"patrones": [r"destino econ[oó]mico(?: catastral)?\s*\n?\s*([^\n]{4,60})"]},
    "uso_pot": {"patrones": [r"norma uso de suelo\s*\n?\s*([^\n]{4,80})",
                             r"uso(?: normativo)? pot\s*[:\-]\s*([^\n]{4,80})"]},
    "tratamiento": {"patrones": [r"tratamiento urban[ií]stico\s*\n?\s*([^\n]{4,90})",
                                 r"tratamiento\s*[:\-]\s*([A-ZÁÉÍÓÚÑ][^\n]{4,60})"]},
    "altura_maxima": {"patrones": [r"hasta\s+(\d{1,3})\s*pisos[^\n]{0,60}",
                                   r"altura[^\n]{0,30}?(?:de\s+)?(\d{1,3})\s*pisos[^\n]{0,60}",
                                   r"(\d{1,3})\s*pisos\s*\([^)]{0,30}\)\s*a\s*(\d{1,3})\s*pisos",
                                   r"altura (?:normativa )?m[aá]xima[^\n]{0,40}?(\d{1,3})\s*pisos"]},
    "clase_suelo": {"patrones": [r"clasificaci[oó]n del suelo\s*\n?\s*([^\n]{4,60})"]},
    "planes_parciales": {"patrones": [r"planes parciales\s*\n?\s*([^\n]{4,80})"]},
    "estrato": {"patrones": [r"estrato\s*\n?\s*([0-9]{1,2})\b"]},
    "barrio": {"patrones": [r"barrio\s*/\s*sector oficial\s*\n?\s*([A-ZÁÉÍÓÚÑ][a-záéíóúñ ]{3,40})"],
               "excluir": ("catastral", "oficial", "pendiente", "no ")},
    "localidad": {"patrones": [r"comuna/localidad\s*\n?\s*([^\n]{3,60})"]},
    "amenaza": {"patrones": [r"(amenaza\s+(?:alta|media|baja))",
                             r"(sin afectaci[oó]n)",
                             r"(sin zona de amenaza[^\n]{0,40})",
                             r"(no se identific[^\n]{0,40})",
                             r"clasificaci[oó]n resultante\s*\n?\s*([^\n]{3,80})"]},
    "riesgo": {"patrones": [r"(sin zona de amenaza volc[aá]nica cartografiada)",
                            r"(fuera del [aá]rea cartografiada)",
                            r"riesgo volc[aá]nico \(sgc\)\s*\n?\s*([^\n]{4,90})"],
               "canon": [("CART OGRAFIADA|CARTOGRAFIADA|FUERA DEL AREA", "SIN_COBERTURA_SGC"),
                         ("NO EVALUADO", "NO_EVALUADO")]},
    "coordenada": {"patrones": [r"lat:\s*([-\d.,]+)\s*n?\s*\|\s*lon:\s*([-\d.,]+)",
                                r"coordenadas? (?:de ubicaci[oó]n|wgs84)\s*[:\-]?\s*([^\n]{6,60})"]},
    "valor_central": {"patrones": [r"valor central estimado(?: \(referencial\))?\s*\n?\s*(\$[^\n]{4,60})",
                                   r"valor comercial consolidado\s*\n?\s*(\$[^\n]{4,60})"]},
    "valor_m2": {"patrones": [r"(\$ ?[\d.,]{4,}\s*/\s*m2)"]},
    "titulares": {"patrones": [r"titulares vigentes\s*\n?\s*([^\n]{4,90})"]},
    # El hecho material es la EXISTENCIA y el tipo de carga (no el texto de la tabla).
    "gravamenes": {"patrones": [r"(hipoteca vigente)", r"(embargo vigente)",
                                r"(medida cautelar vigente)",
                                r"(tradici[oó]n registral libre de grav[aá]menes)"]},
    "screening": {"patrones": [r"estado del screening de contrapartes\s*\n?\s*([^\n]{4,90})"]},
    "evidencias": {"patrones": [r"evidencia:?\s*(\d+\s*/\s*\d+)",
                                r"evidencias\s*\n?\s*(\d+)"]},
}

# Declaraciones de FUENTE por atributo (se usan para explicar cambios).
_DECLARACIONES: Dict[str, List[str]] = {
    "altura_maxima": [r"altura[^\n]{0,120}"],
    "tratamiento": [r"tratamiento[^\n]{0,120}"],
    "uso_pot": [r"uso de suelo[^\n]{0,120}"],
    "estrato": [r"estrato[^\n]{0,80}"],
    "destino_economico": [r"destino econ[oó]mico[^\n]{0,80}"],
    "valor_central": [r"metodolog[íi]a[^\n]{0,120}", r"sector[^\n]{0,80}"],
    "coordenada": [r"coordenad[^\n]{0,120}"],
}

# Declaraciones GLOBALES del documento (versión de fuente/método y fecha).
_GLOBALES = {
    "metodologia": [r"lonja_baq_metodologia@[\w\.\-]+",
                    r"metodolog[íi]a[^\n]{0,90}"],
    "fuente_pot": [r"fuente de capas\s*\n?\s*([^\n]{0,120})",
                   r"POT[^\n]{0,100}"],
    "version_plataforma": [r"commit ([0-9a-f]{7,40})", r"ARHIAX RE v([\d\.]+)"],
    "fecha_emision": [r"emitido:\s*([^\n]{6,40})", r"generado\s*[:\-]?\s*([0-9]{4}-[0-9]{2}-[0-9]{2}[^\n]{0,20})"],
    "release_gate": [r"release_gate_status\s*\n?\s*([^\n]{4,60})"],
    "evidencia_cadena": [r"cadena\s+([A-Z_]{4,20})"],
    # Procedencia de la GEOMETRÍA: explica (o no) los cambios de coordenada.
    "geometria_oficial": [r"(OFFICIAL_PREDIO)", r"(OFFICIAL_ADOPTION_ADDRESS_GEOCODE)"],
    "coordenada_demo": [r"(GMAPS-SAT)", r"(BARRIO_DEMO)", r"(CITY_CENTROID)"],
}


def extraer_atributos(texto: str) -> Dict[str, Dict[str, Any]]:
    """Extrae los atributos de UNA versión a partir del texto de su documento."""
    t = str(texto or "")
    salida: Dict[str, Dict[str, Any]] = {}
    for nombre, cfg in _ATRIBUTOS.items():
        valor, declaracion = None, None
        for pat in cfg["patrones"]:
            m = re.search(pat, t, re.IGNORECASE)
            if m:
                crudo = " ".join(g for g in m.groups() if g)
                if any(x in _norm(crudo) for x in (cfg.get("excluir") or ())):
                    continue
                valor = _limpio(crudo)
                if valor:
                    break
        if valor is None and cfg.get("derivado"):
            m = re.search(cfg["derivado"], t, re.IGNORECASE)
            if m:
                valor = f"TO {m.group(1)} AP {m.group(2)}"
        for pat in _DECLARACIONES.get(nombre, []):
            m = re.search(pat, t, re.IGNORECASE)
            if m:
                declaracion = _limpio(m.group(0))
                break
        # Canonicalización del hecho (evita contradicciones por redacción).
        for pat_canon, etiqueta in (cfg.get("canon") or []):
            if valor and re.search(pat_canon, _norm(valor), re.IGNORECASE):
                valor = etiqueta
                break
        salida[nombre] = {"value": valor, "declaracion": declaracion}
    salida["__globales__"] = {}
    for nombre, patrones in _GLOBALES.items():
        for pat in patrones:
            m = re.search(pat, t, re.IGNORECASE)
            if m:
                salida["__globales__"][nombre] = _limpio(m.group(1) if m.groups() else m.group(0))
                break
    return salida


def _fuente_declarada(atributo: str, datos: Dict[str, Any]) -> Optional[str]:
    """Fuente/versión declarada para un atributo: la suya o la global del documento."""
    propia = (datos.get(atributo) or {}).get("declaracion")
    g = datos.get("__globales__") or {}
    if atributo in ATRIBUTOS_URBANISTICOS:
        return propia or g.get("fuente_pot")
    if atributo in ("valor_central", "valor_m2"):
        return g.get("metodologia")
    if atributo in ("matricula", "nupre", "numero_predial", "unidad", "direccion"):
        return g.get("release_gate") or propia
    return propia


def _explica_cambio(atributo: str, anterior: Dict[str, Any], actual: Dict[str, Any],
                    va: Optional[str] = None, vb: Optional[str] = None) -> Tuple[bool, str]:
    """¿El cambio tiene explicación VERIFICABLE, o solo cambió la redacción?

    Solo hay explicación cuando la PROCEDENCIA declarada cambia de forma material:
      · la coordenada pasa de punto de referencia/geocodificado a geometría oficial
        (o al contrario), o
      · el método/versión de la fuente declarada cambia (metodología, capa POT,
        versión de plataforma).
    Que cambie la ETIQUETA o la redacción NO explica nada: eso es precisamente un
    `UNEXPLAINED_CONFLICT` (el mismo predio produjo cifras distintas).
    """
    ma = _marcas(_fuente_declarada(atributo, anterior))
    mb = _marcas(_fuente_declarada(atributo, actual))
    ma |= _marcas((anterior.get(atributo) or {}).get("declaracion"))
    mb |= _marcas((actual.get(atributo) or {}).get("declaracion"))
    solo_demo_a = ma - _MARCAS_OFICIAL_SET
    solo_demo_b = mb - _MARCAS_OFICIAL_SET
    oficial_a = bool(ma & _MARCAS_OFICIAL_SET)
    oficial_b = bool(mb & _MARCAS_OFICIAL_SET)
    if atributo == "coordenada":
        # La procedencia de la geometría cambia de forma verificable: la versión nueva
        # usa la geometría OFICIAL del predio y la anterior un punto de referencia.
        ga = (anterior.get("__globales__") or {}).get("geometria_oficial")
        gb = (actual.get("__globales__") or {}).get("geometria_oficial")
        da = (anterior.get("__globales__") or {}).get("coordenada_demo")
        db = (actual.get("__globales__") or {}).get("coordenada_demo")
        if bool(ga) != bool(gb):
            return True, ("cambió la procedencia de la geometría: "
                          f"{'geometría oficial del predio' if gb else 'punto de referencia'}"
                          f" (antes: {'oficial' if ga else 'referencia/geocodificada'})")
        if bool(da) != bool(db):
            return True, f"cambió el origen declarado de la coordenada ({da or 'oficial'} → {db or 'oficial'})"
    if atributo == "coordenada" and (oficial_a != oficial_b):
        return True, ("la procedencia de la coordenada cambió: "
                      f"{'oficial' if oficial_a else 'de referencia/geocodificada'} → "
                      f"{'oficial' if oficial_b else 'de referencia/geocodificada'}")
    if atributo == "coordenada" and (solo_demo_a != solo_demo_b):
        return True, f"la fuente de la coordenada cambió ({sorted(ma)} → {sorted(mb)})"
    if (ma - mb) or (mb - ma):
        # Cambió alguna marca de procedencia: se acepta si además cambió la declaración
        # de fuente del atributo (no solo la etiqueta del campo).
        da = _norm(_fuente_declarada(atributo, anterior))
        db = _norm(_fuente_declarada(atributo, actual))
        if da and db and da != db and ((ma - mb) or (mb - ma)):
            return True, f"la fuente/método declarado cambió ({da[:50]} → {db[:50]})"
    ga = anterior.get("__globales__") or {}
    gb = actual.get("__globales__") or {}
    for clave in ("metodologia",):
        if _norm(ga.get(clave)) and _norm(gb.get(clave)) and _norm(ga.get(clave)) != _norm(gb.get(clave)):
            if atributo in ("valor_central", "valor_m2"):
                return True, (f"cambió la metodología declarada "
                              f"({str(ga.get(clave))[:40]} → {str(gb.get(clave))[:40]})")
    return False, "sin fuente ni método declarado que explique el cambio"


def _hallazgo_dimension_mezclada(atributo: str, anterior: Dict[str, Any],
                                 actual: Dict[str, Any]) -> Optional[str]:
    """Detecta la MEZCLA de dimensiones (defecto §T): el destino económico catastral
    impreso en la fila del uso POT. No es un conflicto histórico: es un defecto de
    interpretación del propio documento."""
    if atributo != "uso_pot":
        return None
    _pot_propio = ("ACTIVIDAD", "RESIDENCIAL", "DOTACIONAL", "MIXTO", "PROTECCION",
                   "PROTECCIÓN", "AMBIENTAL", "RURAL", "URBANIZABLE", "NORMATIVO",
                   "PLAN PARCIAL", "SUELO")
    for datos, etiqueta in ((anterior, "versión anterior"), (actual, "versión actual")):
        uso = _norm((datos.get("uso_pot") or {}).get("value"))
        destino = _norm((datos.get("destino_economico") or {}).get("value"))
        if not uso or not destino:
            continue
        nucleo_uso = uso.split()[0]
        if any(p in uso for p in _pot_propio):
            continue
        if nucleo_uso == destino.split()[0]:
            return (f"en la {etiqueta} la fila de uso POT imprime el DESTINO ECONÓMICO "
                    f"catastral ({nucleo_uso}): dimensiones distintas mezcladas en un "
                    "mismo campo")
    return None


def clasificar_cambio(atributo: str, anterior: Dict[str, Any], actual: Dict[str, Any]) -> Dict[str, Any]:
    """Clasifica el cambio de UN atributo entre dos versiones (§C)."""
    va = ((anterior.get(atributo) or {}).get("value"))
    vb = ((actual.get(atributo) or {}).get("value"))
    ka, kb = _clave(atributo, va), _clave(atributo, vb)
    detalle: Dict[str, Any] = {"atributo": atributo, "anterior": va, "actual": vb,
                               "clave_anterior": sorted(ka) if isinstance(ka, frozenset) else ka,
                               "clave_actual": sorted(kb) if isinstance(kb, frozenset) else kb}
    if ka is not None and kb is not None and ka == kb:
        detalle.update({"cambio": False, "clase": None, "explicado": None, "motivo": "sin cambio"})
        return detalle
    # ── BLOCK 1 · §3: DOS AUSENCIAS NO SON UN CAMBIO ──────────────────────────
    # Antes, la guarda de «sin cambio» exigía que AMBAS claves fuesen no-`None`, así que
    # `va = vb = None` caía en la rama siguiente y el informe declaraba `cambio: True`
    # con clase `SOURCE_UNAVAILABLE`. Medido: `area` acumulaba 13 «cambios» `null → null`
    # entre versiones que TAMPOCO traían el atributo, y esos trece falsos cambios metían
    # a `area` (y a nupre, numero_predial, unidad, regimen_juridico, direccion) en
    # `requieren_revision` ⇒ las filas de identidad de la página 6 salían
    # `REQUIERE VALIDACIÓN` por un cambio que nunca ocurrió.
    # Si NINGUNA de las dos versiones trae el atributo, no hay nada que comparar: no es
    # un cambio, no es un conflicto y no se declara ni uno ni otro.
    if va is None and vb is None:
        detalle.update({
            "cambio": False, "clase": None, "explicado": None, "sin_dato_en_ambas": True,
            "motivo": ("ninguna de las dos versiones declara el atributo: dos ausencias no "
                       "son un cambio (no se declara cambio ni conflicto)")})
        return detalle
    if va is None or vb is None:
        detalle.update({"cambio": True, "clase": SOURCE_UNAVAILABLE,
                        "explicado": False,
                        "motivo": ("el valor no está en la versión más reciente"
                                   if vb is None else
                                   "el valor no estaba en la versión anterior")})
        if va is None and vb is not None:
            detalle["clase"] = PARSER_CHANGE
            detalle["motivo"] = ("el atributo aparece recién en la versión nueva: puede ser "
                                 "fuente nueva o extracción nueva (revisar)")
        return detalle

    # Atributo urbanístico con conjuntos de números SOLAPADOS (p. ej. un rango
    # "5 a 11 pisos" frente a un valor único "11"): no es contradicción dura, pero
    # exige validar bajo qué polígono cae el predio.
    solapan = bool(ka and kb and isinstance(ka, frozenset) and isinstance(kb, frozenset)
                   and (ka & kb))
    mezcla = _hallazgo_dimension_mezclada(atributo, anterior, actual)

    if atributo in ("matricula", "nupre", "numero_predial", "unidad", "direccion"):
        clase = IDENTITY_CHANGE
    elif atributo == "coordenada":
        clase = GEOMETRY_CHANGE
    elif atributo in ("valor_central", "valor_m2"):
        clase = METHODOLOGY_UPDATE
    else:
        clase = SOURCE_UPDATE
    explicado, motivo = _explica_cambio(atributo, anterior, actual, va, vb)
    if mezcla:
        clase, explicado, motivo = INTERPRETATION_CHANGE, False, mezcla
    elif solapan and not explicado:
        clase, motivo = INTERPRETATION_CHANGE, (
            "los valores se solapan parcialmente (rango frente a valor único): exige "
            "validar bajo qué polígono/ficha cae el predio")
    elif not explicado:
        clase = UNEXPLAINED_CONFLICT
    detalle.update({"cambio": True, "clase": clase, "explicado": explicado, "motivo": motivo,
                    "solapan": solapan, "hallazgo": mezcla})
    return detalle


def construir_matriz(versiones: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """ATTRIBUTE HISTORY MATRIX: un registro por (versión, atributo) + cambios.

    `versiones`: [{version, fecha, origen, pdf_sha256, texto}] ordenadas de más antigua
    a más reciente (el orden se impone por `fecha` cuando existe).
    """
    vs = sorted(list(versiones), key=lambda v: (str(v.get("fecha") or ""), str(v.get("version"))))
    datos = []
    for v in vs:
        d = extraer_atributos(v.get("texto") or "")
        datos.append({"meta": v, "datos": d})

    filas: List[Dict[str, Any]] = []
    for i, item in enumerate(datos):
        meta, d = item["meta"], item["datos"]
        g = d.get("__globales__") or {}
        for atributo in _ATRIBUTOS:
            valor = (d.get(atributo) or {}).get("value")
            filas.append({
                "version": meta.get("version"),
                "fecha": meta.get("fecha"),
                "atributo": atributo,
                "value": valor,
                "status": SIN_DATO if valor is None else VERIFICADO,
                "source": _fuente_declarada(atributo, d),
                "source_version": g.get("version_plataforma") or g.get("fuente_pot"),
                "query_date": meta.get("fecha"),
                "provenance": {"origen": meta.get("origen"),
                               "pdf_sha256": meta.get("pdf_sha256"),
                               "declaracion": (d.get(atributo) or {}).get("declaracion")},
                "identity_binding": (meta.get("identity_binding") or "no declarado"),
            })

    cambios: List[Dict[str, Any]] = []
    for i in range(1, len(datos)):
        prev, cur = datos[i - 1], datos[i]
        for atributo in _ATRIBUTOS:
            c = clasificar_cambio(atributo, prev["datos"], cur["datos"])
            if c.get("cambio"):
                c["version_anterior"] = prev["meta"].get("version")
                c["version_actual"] = cur["meta"].get("version")
                c["material"] = atributo in ATRIBUTOS_MATERIALES
                cambios.append(c)

    conflictos = [c for c in cambios
                  if c.get("material") and c.get("clase") == UNEXPLAINED_CONFLICT]
    por_atributo: Dict[str, List[str]] = {}
    for c in cambios:
        por_atributo.setdefault(c["atributo"], []).append(
            f"{c['version_anterior']} → {c['version_actual']}: "
            f"{c['anterior']!r} → {c['actual']!r} [{c['clase']}]")
    return {
        "generado_en": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "versiones": [{"version": d["meta"].get("version"), "fecha": d["meta"].get("fecha"),
                       "origen": d["meta"].get("origen"),
                       "pdf_sha256": d["meta"].get("pdf_sha256")} for d in datos],
        "atributos": sorted(_ATRIBUTOS.keys()),
        "filas": filas,
        "cambios": cambios,
        "conflictos_historicos_abiertos": conflictos,
        "resumen_por_atributo": por_atributo,
    }


def conflicto_de_atributo(matriz: Dict[str, Any], atributo: str) -> Dict[str, Any]:
    """Estado de coherencia de un atributo según la historia (§V)."""
    cambios = [c for c in (matriz or {}).get("cambios", []) if c["atributo"] == atributo]
    abiertos = [c for c in cambios if c.get("clase") == UNEXPLAINED_CONFLICT]
    explicados = [c for c in cambios if c.get("explicado")]
    if abiertos:
        valores = []
        for c in abiertos:
            for v in (c.get("anterior"), c.get("actual")):
                if v not in valores:
                    valores.append(v)
        return {
            "atributo": atributo,
            "estado": HISTORICAL_CONFLICT,
            "valores": valores,
            "veces": len(abiertos),
            "detalle": ("El expediente ha producido resultados distintos para el mismo "
                        "predio en ejecuciones previas, sin fuente ni método que lo "
                        "explique. La cifra definitiva no se presenta hasta resolver qué "
                        "polígono/ficha normativa es aplicable."),
            "cambios": abiertos,
        }
    if explicados:
        return {"atributo": atributo, "estado": CAMBIO_CON_FUENTE,
                "valores": [c.get("actual") for c in explicados],
                "detalle": explicados[-1].get("motivo"), "cambios": explicados}
    if cambios:
        return {"atributo": atributo, "estado": REQUIERE_VALIDACION,
                "valores": [c.get("actual") for c in cambios],
                "detalle": cambios[-1].get("motivo"), "cambios": cambios}
    return {"atributo": atributo, "estado": VERIFICADO, "valores": [], "detalle":
            "sin cambios entre las versiones comparadas", "cambios": []}


def gate_urbanistico(matriz: Dict[str, Any], atributo: str,
                     valor_actual: Any) -> Dict[str, Any]:
    """URBAN CONSISTENCY GATE (§D): ¿puede imprimirse este valor como VERIFICADO?

    Devuelve `{puede_publicar, estado, valor_a_mostrar, mensaje, conflicto}`. Si el
    atributo tiene conflicto histórico abierto, `puede_publicar=False` y el render NO
    debe imprimir la cifra como hecho definitivo.
    """
    info = conflicto_de_atributo(matriz, atributo)
    if info["estado"] == HISTORICAL_CONFLICT:
        return {
            "puede_publicar": False,
            "estado": HISTORICAL_CONFLICT,
            "valor_a_mostrar": None,
            "mensaje": info["detalle"],
            "valores_en_conflicto": info["valores"],
            "conflicto": info,
        }
    return {"puede_publicar": True, "estado": info["estado"],
            "valor_a_mostrar": valor_actual, "mensaje": info.get("detalle"),
            "valores_en_conflicto": [], "conflicto": info}


def reporte_consistencia(matriz: Dict[str, Any]) -> Dict[str, Any]:
    """HISTORICAL CONSISTENCY REPORT: conflictos abiertos, explicados y por revisar.

    BLOCK 1 · §6 — el recuento de «conflictos abiertos» se DERIVA de `TRUE_CONFLICT`
    (las siete condiciones), no de `material == True and clase == UNEXPLAINED_CONFLICT`.
    Una diferencia entre versiones que el propio expediente explica —precedencia
    declarada, cambio de fuente, cascada del cambio de geometría, semántica distinta o
    simple normalización de caja— NO es un conflicto abierto: se declara con su CLASE y
    su MOTIVO (`clasificaciones_conflicto`), y el atributo sigue en revisión.
    """
    abiertos, explicados, revisar = [], [], []
    clasificaciones: Dict[str, Any] = {}
    for atributo in sorted(_ATRIBUTOS.keys()):
        info = conflicto_de_atributo(matriz, atributo)
        clas = clasificar_conflicto_historico(atributo, matriz)
        clasificaciones[atributo] = clas
        if info["estado"] == HISTORICAL_CONFLICT and clas["veredicto"] == TRUE_CONFLICT:
            info = {**info, "clase_conflicto": clas["veredicto"],
                    "condiciones": clas["condiciones"], "motivo_clasificacion": clas["motivo"]}
            abiertos.append(info)
        elif info["estado"] == HISTORICAL_CONFLICT:
            # Diferencia declarada MATERIAL pero explicada por una regla del expediente:
            # el atributo NO se imprime como conflicto abierto y NO se imprime VERIFICADO.
            revisar.append({
                **{k: v for k, v in info.items() if k != "estado"},
                "estado": REQUIERE_VALIDACION,
                "clase_conflicto": clas["veredicto"],
                # `diferencia_material`: el atributo TENÍA una diferencia material entre
                # versiones COMPARABLES (no una simple aparición en la versión nueva). El
                # panel de coherencia de la página 4 muestra estos atributos con su clase
                # declarada; los que solo «aparecieron» siguen fuera del panel.
                "diferencia_material": clas["veredicto"] in (
                    HISTORICAL_CHANGE, RESOLVED_BY_PRECEDENCE, SEMANTIC_DIFFERENCE,
                    NORMALIZATION_DIFFERENCE),
                "condiciones": clas["condiciones"],
                "condicion_que_decide": clas["condicion_que_decide"],
                "detalle": clas["motivo"] or info.get("detalle"),
            })
        elif info["estado"] == CAMBIO_CON_FUENTE:
            explicados.append({**info, "clase_conflicto": clas["veredicto"]})
        elif info["estado"] == REQUIERE_VALIDACION:
            revisar.append({**info, "clase_conflicto": clas["veredicto"],
                            "condiciones": clas["condiciones"]})
    veredicto = "CONFLICTOS_ABIERTOS" if abiertos else "COHERENTE"
    recuento = recuento_true_conflict(matriz)
    return {
        "generado_en": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "version": "dictus-historical-consistency/1.1.0",
        "versiones_comparadas": len((matriz or {}).get("versiones") or []),
        "conflictos_abiertos": abiertos,
        "cambios_explicados": explicados,
        "requieren_revision": revisar,
        "clasificaciones_conflicto": clasificaciones,
        "recuento_conflictos": recuento,
        "veredicto": veredicto,
    }


def sha256_texto(txt: str) -> str:
    return hashlib.sha256(str(txt).encode("utf-8")).hexdigest()


# ══════════════════════════════════════════════════════════════════════════════
# BLOCK 1 · §6 — CONFLICTO HISTÓRICO: las SIETE CONDICIONES
# ══════════════════════════════════════════════════════════════════════════════
# Un «conflicto histórico» NO es cualquier diferencia entre versiones: es una
# diferencia que cumple las SIETE condiciones. Si alguna falla, el expediente sabe POR
# QUÉ y lo declara con su clase y su motivo. El recuento de conflictos abiertos se
# deriva SOLO de `TRUE_CONFLICT` (puede subir o bajar: no se preserva por compatibilidad).

TRUE_CONFLICT = "TRUE_CONFLICT"
HISTORICAL_CHANGE = "HISTORICAL_CHANGE"
RESOLVED_BY_PRECEDENCE = "RESOLVED_BY_PRECEDENCE"
SEMANTIC_DIFFERENCE = "SEMANTIC_DIFFERENCE"
NORMALIZATION_DIFFERENCE = "NORMALIZATION_DIFFERENCE"
CASCADE_OF_GEOMETRY_CHANGE = "CASCADE_OF_GEOMETRY_CHANGE"
NOT_A_CONFLICT = "NOT_A_CONFLICT"

CONDICIONES_CONFLICTO = (
    "1_mismo_atributo",
    "2_misma_semantica",
    "3_mismo_objeto",
    "4_vigencia_comparable",
    "5_autoridad_comparable",
    "6_valores_incompatibles",
    "7_precedencia_no_resuelve",
)

# Severidad relativa SOLO para agregar los veredictos de par a nivel de atributo: el
# recuento de conflictos abiertos solo cuenta `TRUE_CONFLICT`.
_SEVERIDAD_CLASE = {
    NOT_A_CONFLICT: 0, NORMALIZATION_DIFFERENCE: 1, SEMANTIC_DIFFERENCE: 2,
    RESOLVED_BY_PRECEDENCE: 3, CASCADE_OF_GEOMETRY_CHANGE: 4,
    HISTORICAL_CHANGE: 5, TRUE_CONFLICT: 6,
}

# Tolerancia declarada de «mismo objeto observado»: dos puntos a más de 25 m NO son el
# mismo punto evaluado (una nomenclatura oficial y su punto catastral distan metros, no
# centenas). Medido en el Golden: los pares rivales distan 137.1 m y 144.7 m.
TOLERANCIA_MISMO_OBJETO_M = 25.0

# Atributos cuyo valor depende del PUNTO evaluado (punto-en-polígono): un cambio de
# coordenada entre las dos versiones EXPLICA su cambio (es cascada, no defecto propio).
# `altura_maxima` NO está aquí: su escalón es de fuente única y su binding es por
# tratamiento, de modo que la coordenada no lo explica (auditoría §6, medido).
_DEPENDE_DEL_PUNTO = frozenset({"tratamiento", "uso_pot", "clase_suelo", "amenaza",
                                "riesgo", "areas_en_riesgo", "estrato", "destino_economico"})

# Reglas de PRECEDENCIA DECLARADAS por el producto para el atributo (condición 7: la
# precedencia SÍ resuelve ⇒ la discrepancia no es un conflicto abierto).
_PRECEDENCIA_DECLARADA = {
    "amenaza": ("api/geospatial_engine.py::_clave — se elige la coincidencia de MAYOR "
                "severidad y, a igualdad, la de MENOR área (el predio cae en varios "
                "polígonos de la misma capa: uno de fondo y uno local)"),
    "riesgo": ("api/geospatial_engine.py::_clave — misma regla de desempate declarada "
               "para las capas de riesgo del POT"),
    "uso_pot": ("escalera del Source Pack: POT_BAQ_AREAS_ACTIVIDAD (prioridad 10) > "
                "POT_BAQ_POLIGONOS_USO (prioridad 20)"),
    "altura_fisica": "api/dictus_sources: la altura física del edificio no es la normativa",
}

# Marcadores de DIMENSIÓN que el propio valor declara (semántica del hecho). Dos valores
# con marcadores distintos no son el mismo hecho y no compiten.
_MARCADORES_DIMENSION = (
    ("capa 2", "CAPA_2_AREAS_ACTIVIDAD"), ("capa 3", "CAPA_3"),
    ("capa 4", "CAPA_4_TRATAMIENTOS"), ("capa 5", "CAPA_5_POLIGONOS"),
    ("en vivo", "CONSULTA_EN_VIVO"), ("según polígono", "SEGUN_POLIGONO"),
    ("segun poligono", "SEGUN_POLIGONO"), ("según catastro", "SEGUN_CATASTRO"),
    ("segun catastro", "SEGUN_CATASTRO"), ("ctl", "CTL"), ("snr", "SNR"),
)

_VALORES_INCOMPATIBLES_POR_ATRIBUTO = {
    "titulares": ("TITULARIDAD: los valores se comparan por SUJETO (nombre + documento), "
                  "no por su forma: 'Juan Pérez' y 'JUAN PEREZ' son el mismo titular"),
}


def _familia_declarada(texto: Any) -> str:
    """Familia de FUENTE declarada por el propio documento, sin el valor dentro.

    El texto de fuente de algunos atributos CONTIENE el valor (p. ej. «Coordenadas de
    ubicación: 11.00538 N, -74.83862 W»), así que se corta en el primer dígito: lo que
    queda es la fuente declarada («Coordenadas de ubicación:»), y dos versiones con la
    MISMA familia declaran la misma fuente aunque el valor cambie.
    """
    t = _norm(texto)
    m = re.search(r"\d", t)
    return (t[:m.start()] if m else t).strip(" .,:;-")


def _marcadores_semanticos(valor: Any) -> frozenset:
    """Dimensión(es) que el VALOR declara de sí mismo (capa, consulta en vivo, etc.)."""
    v = _norm(valor)
    return frozenset(clave for marca, clave in _MARCADORES_DIMENSION if _norm(marca) in v)


def _punto_de(texto: Any) -> Optional[Tuple[float, float]]:
    if texto is None:
        return None
    m = re.findall(r"-?\d+\.\d+", str(texto))
    if len(m) < 2:
        return None
    try:
        return float(m[0]), float(m[1])
    except ValueError:  # pragma: no cover — defensivo
        return None


def _metros(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """Distancia geodésica aproximada (haversine) en metros."""
    import math
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * 6371000.0 * math.asin(min(1.0, math.sqrt(h)))


def _sujeto_titular(texto: Any) -> frozenset:
    """Clave de SUJETO de un titular: nombre normalizado + documento (solo dígitos)."""
    t = _norm(texto)
    if not t:
        return frozenset()
    docs = set(re.findall(r"\d{6,}", t.replace(".", "").replace(" ", "")))
    letras = frozenset(p for p in re.findall(r"[A-Z]{3,}", t)
                       if p not in ("CC", "NIT", "COP", "PORC", "TITULAR"))
    return letras | frozenset(docs)


def _incompatibles(atributo: str, va: Any, vb: Any,
                   ka: Any, kb: Any) -> Tuple[bool, str]:
    """Condición 6: ¿los valores son INCOMPATIBLES (no pueden ser ambos verdaderos)?"""
    if atributo == "titulares":
        sa, sb = _sujeto_titular(va), _sujeto_titular(vb)
        if sa and sb and (sa & sb):
            return False, ("los valores NO son incompatibles: comparten el mismo sujeto "
                           f"({', '.join(sorted(sa & sb))[:60]}); la diferencia es de FORMA")
        return True, "titulares sin sujeto en común"
    if isinstance(ka, frozenset) and isinstance(kb, frozenset):
        if ka == kb:
            return False, "claves iguales"
        if ka & kb:
            return False, (f"los valores se SOLAPAN ({sorted(ka & kb)}) : un rango y un "
                           f"valor único no son incompatibles")
        return True, f"conjuntos disjuntos ({sorted(ka)} ∩ {sorted(kb)} = ∅)"
    return True, "valores distintos sin solape declarado"


def clasificar_conflicto_historico(atributo: str,
                                   matriz: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Evalúa las SIETE condiciones por PAR de versiones y agrega el veredicto.

    Devuelve `{atributo, veredicto, condiciones, condicion_que_decide, motivo, pares,
    abierto, clasificaciones}`: `abierto=True` SOLO si el veredicto es `TRUE_CONFLICT`.
    """
    pares: List[Dict[str, Any]] = []
    for c in (matriz or {}).get("cambios", []):
        if c.get("atributo") != atributo:
            continue
        pares.append(_clasificar_par(atributo, c, matriz))
    comparables = [p for p in pares if p["veredicto"] != NOT_A_CONFLICT]
    if not comparables:
        return {
            "atributo": atributo, "veredicto": NOT_A_CONFLICT, "abierto": False,
            "condiciones": {}, "condicion_que_decide": "",
            "motivo": ("sin diferencias comparables entre versiones (dos ausencias no son "
                       "un cambio)"),
            "pares": pares,
        }
    mejor = max(comparables, key=lambda p: (_SEVERIDAD_CLASE.get(p["veredicto"], 0),
                                           1 if p.get("cascada_de_geometria") else 0))
    return {
        "atributo": atributo,
        "veredicto": mejor["veredicto"],
        "abierto": mejor["veredicto"] == TRUE_CONFLICT,
        "condiciones": mejor["condiciones"],
        "condicion_que_decide": ("" if mejor["veredicto"] == TRUE_CONFLICT
                                 else mejor["condicion_que_decide"]),
        "motivo": mejor["motivo"],
        "cascada_de_geometria": bool(mejor.get("cascada_de_geometria")),
        "pares": pares,
    }


def _clasificar_par(atributo: str, cambio: Dict[str, Any],
                    matriz: Dict[str, Any]) -> Dict[str, Any]:
    """Veredicto de UN par de versiones consecutivas, con la condición que decide."""
    va, vb = cambio.get("anterior"), cambio.get("actual")
    ka, kb = cambio.get("clave_anterior"), cambio.get("clave_actual")
    cond = {c: True for c in CONDICIONES_CONFLICTO}
    base = {"atributo": atributo, "version_anterior": cambio.get("version_anterior"),
            "version_actual": cambio.get("version_actual"), "anterior": va, "actual": vb}
    # Una AUSENCIA en una de las dos versiones no es un valor rival: no es conflicto.
    if va is None or vb is None:
        return {**base, "veredicto": NOT_A_CONFLICT, "condiciones": cond,
                "condicion_que_decide": "6_valores_incompatibles",
                "motivo": ("una de las dos versiones no declara el atributo: una ausencia "
                           "no es un valor rival (no se fabrica un conflicto con el vacío)")}
    index = _fuentes_por_version(matriz, atributo)
    fa = _familia_declarada(index.get(cambio.get("version_anterior")))
    fb = _familia_declarada(index.get(cambio.get("version_actual")))
    # 2 · misma semántica: la dimensión que el propio valor declara.
    ma, mb = _marcadores_semanticos(va), _marcadores_semanticos(vb)
    cond["2_misma_semantica"] = ma == mb
    # 4 · vigencia comparable: ninguna de las dos declara ser una versión histórica.
    hist_a = any(t in _norm(va) for t in ("HISTORIC", "ANTERIOR", "VERSION ANTERIOR"))
    hist_b = any(t in _norm(vb) for t in ("HISTORIC", "ANTERIOR", "VERSION ANTERIOR"))
    cond["4_vigencia_comparable"] = not (hist_a or hist_b)
    # 5 · autoridad comparable: ninguna declara estimación/geocodificación sin fuente.
    _no_oficial = ("ESTIMAD", "REFERENCIAL", "GEOCODE", "NOMINATIM", "OPENSTREETMAP",
                   "SIN FUENTE", "NO DECLARADA")
    cond["5_autoridad_comparable"] = not any(
        t in (fa + " " + fb) for t in _no_oficial)
    # 6 · valores incompatibles (con la regla declarada de cada atributo).
    incompat, motivo_6 = _incompatibles(atributo, va, vb, ka, kb)
    cond["6_valores_incompatibles"] = incompat
    # 7 · precedencia que NO resuelve.
    tiene_precedencia = atributo in _PRECEDENCIA_DECLARADA
    cond["7_precedencia_no_resuelve"] = not tiene_precedencia
    # 3 · mismo objeto observado (solo para atributos punto-en-polígono).
    puntos = _puntos_por_version(matriz)
    pa = puntos.get(cambio.get("version_anterior"))
    pb = puntos.get(cambio.get("version_actual"))
    dist = _metros(pa, pb) if (pa and pb) else None
    depende_punto = atributo in _DEPENDE_DEL_PUNTO
    cond["3_mismo_objeto"] = bool(
        (not depende_punto) or dist is None or dist <= TOLERANCIA_MISMO_OBJETO_M)

    # ── decisión ordenada por la condición que DECIDE (declarada, no inferida) ──
    if not cond["6_valores_incompatibles"]:
        # Valores compatibles: no hay dos verdades rivales. Solo forma.
        veredicto = NORMALIZATION_DIFFERENCE if atributo == "titulares" \
            or (ka is not None and kb is not None and ka == kb) else SEMANTIC_DIFFERENCE
        return {**base, "veredicto": veredicto, "condiciones": cond,
                "condicion_que_decide": "6_valores_incompatibles", "motivo": motivo_6,
                "distancia_m": dist, "cascada_de_geometria": False}
    if fa != fb and (fa or fb):
        # La FUENTE declarada cambió entre las dos versiones: el cambio está explicado.
        return {**base, "veredicto": HISTORICAL_CHANGE, "condiciones": cond,
                "condicion_que_decide": "4_vigencia_comparable",
                "motivo": (f"la FUENTE declarada cambió entre las versiones "
                           f"(«{fa[:48]}» → «{fb[:48]}»): la diferencia está EXPLICADA por "
                           f"el cambio de fuente, no es un conflicto sin resolver"),
                "distancia_m": dist, "cascada_de_geometria": False}
    if not cond["2_misma_semantica"]:
        return {**base, "veredicto": SEMANTIC_DIFFERENCE, "condiciones": cond,
                "condicion_que_decide": "2_misma_semantica",
                "motivo": (f"los valores declaran SEMÁNTICAS distintas "
                           f"({sorted(ma) or 'sin marcador'} vs {sorted(mb) or 'sin marcador'}): "
                           f"no son el mismo hecho y no compiten"),
                "distancia_m": dist, "cascada_de_geometria": False}
    if not cond["7_precedencia_no_resuelve"]:
        return {**base, "veredicto": RESOLVED_BY_PRECEDENCE, "condiciones": cond,
                "condicion_que_decide": "7_precedencia_no_resuelve",
                "motivo": ("el producto declara y aplica una regla de precedencia para este "
                           f"atributo: {_PRECEDENCIA_DECLARADA[atributo]}"),
                "distancia_m": dist, "cascada_de_geometria": False}
    if not cond["3_mismo_objeto"]:
        return {**base, "veredicto": HISTORICAL_CHANGE, "condiciones": cond,
                "condicion_que_decide": "3_mismo_objeto", "cascada_de_geometria": True,
                "motivo": (f"las dos versiones evaluaron PUNTOS DISTINTOS ({dist:.1f} m): el "
                           f"cambio es CASCADA del cambio de geometría, no un defecto "
                           f"independiente del atributo (contarlo aparte duplicaría un solo "
                           f"defecto)"),
                "distancia_m": dist}
    if not (cond["4_vigencia_comparable"] and cond["5_autoridad_comparable"]):
        return {**base, "veredicto": HISTORICAL_CHANGE, "condiciones": cond,
                "condicion_que_decide": ("4_vigencia_comparable"
                                         if not cond["4_vigencia_comparable"]
                                         else "5_autoridad_comparable"),
                "motivo": ("las versiones comparadas no son vigentes/comparables en "
                           "autoridad: la diferencia es de HISTORIA, no un conflicto"),
                "distancia_m": dist, "cascada_de_geometria": False}
    # Las SIETE se cumplen.
    return {**base, "veredicto": TRUE_CONFLICT, "condiciones": cond,
            "condicion_que_decide": "", "cascada_de_geometria": False,
            "motivo": (f"las siete condiciones se cumplen: mismo atributo, misma semántica, "
                       f"mismo objeto, vigencia y autoridad comparables, valores "
                       f"INCOMPATIBLES ({motivo_6}) y ninguna regla de precedencia que los "
                       f"resuelva"),
            "distancia_m": dist}


def _fuentes_por_version(matriz: Dict[str, Any], atributo: str) -> Dict[str, Any]:
    return {str(f.get("version")): f.get("source")
            for f in (matriz or {}).get("filas", [])
            if f.get("atributo") == atributo}


def _puntos_por_version(matriz: Dict[str, Any]) -> Dict[str, Tuple[float, float]]:
    """Coordenada declarada por cada versión (atributo histórico `coordenada`)."""
    salida: Dict[str, Tuple[float, float]] = {}
    for f in (matriz or {}).get("filas", []):
        if f.get("atributo") != "coordenada":
            continue
        p = _punto_de(f.get("value"))
        if p:
            salida[str(f.get("version"))] = p
    return salida


def recuento_true_conflict(matriz: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Recuento DERIVADO de `TRUE_CONFLICT` (nunca de la etiqueta `material`).

    Devuelve el total, el desglose por atributo con su veredicto y la banda de
    sensibilidad declarada (estricta = solo TRUE_CONFLICT).
    """
    desglose: Dict[str, Dict[str, Any]] = {}
    for atributo in sorted(_ATRIBUTOS.keys()):
        clas = clasificar_conflicto_historico(atributo, matriz)
        desglose[atributo] = {
            "veredicto": clas["veredicto"],
            "condicion_que_decide": clas["condicion_que_decide"],
            "cascada_de_geometria": bool(clas.get("cascada_de_geometria")),
            "motivo": clas["motivo"],
            "pares_comparables": sum(1 for p in clas["pares"]
                                     if p["veredicto"] != NOT_A_CONFLICT),
        }
    abiertos = sorted(a for a, d in desglose.items() if d["veredicto"] == TRUE_CONFLICT)
    por_clase: Dict[str, List[str]] = {}
    for a, d in desglose.items():
        if d["veredicto"] == NOT_A_CONFLICT:
            continue
        por_clase.setdefault(d["veredicto"], []).append(a)
    return {
        "total": len(abiertos),
        "atributos": abiertos,
        "por_clase": {k: sorted(v) for k, v in sorted(por_clase.items())},
        "desglose": desglose,
        "criterio": ("el recuento se deriva SOLO de TRUE_CONFLICT (las siete condiciones); "
                     "no se preserva por compatibilidad"),
        "banda_sensibilidad": {
            "estricta_TRUE_CONFLICT": len(abiertos),
            "incluyendo_cascadas_de_geometria": len(
                set(abiertos) | {a for a, d in desglose.items()
                                 if d.get("cascada_de_geometria")}),
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# BLOCK 1.1 · A+B — UNA SOLA VERDAD CANÓNICA DEL RECUENTO DE CONFLICTOS
# ══════════════════════════════════════════════════════════════════════════════
# El ejecutivo imprimía DOS recuentos con la MISMA palabra («atributo(s)»): el de
# conflictos verdaderos (`TRUE_CONFLICT`) y el del panel de divergencias históricas,
# que agrupa además las diferencias materiales que el propio expediente ya EXPLICA
# (precedencia declarada, cambio histórico, semántica distinta, normalización). Son
# DOS métricas distintas: la segunda no es un recuento de conflictos.
#
# `get_true_conflict_summary` es la ÚNICA función que las resuelve. Todo consumidor
# (RunState, manifest, modelo de documento, secciones y PDF) lee su salida: ningún
# render vuelve a contar listas por su cuenta, y el número impreso en el PDF llega
# PREVIAMENTE RESUELTO (el renderer no calcula nada).
RESUMEN_CONFLICTOS_VERSION = "dictus-true-conflict-summary/1.0.0"

# Rótulos canónicos: viven AQUÍ y no en el renderer, para que dos métricas distintas
# no puedan volver a compartir el mismo rótulo por copia manual.
ROTULO_CONFLICTO_VERDADERO = "atributo(s) requieren reconciliación histórica"
# Rótulo de la métrica DISTINTA. Deliberadamente NO contiene «reconciliación»,
# «conflictos abiertos» ni «incompatibles»: el panel de la página 1 añade el desglose
# («· N conflicto(s) verdadero(s)») para que jamás se lea como un recuento de conflictos.
ROTULO_ATRIBUTOS_COMPARADOS = "atributo(s) comparados históricamente"
NOTA_ATRIBUTOS_COMPARADOS = ("el recuento de conflictos es SOLO el de TRUE_CONFLICT; las "
                             "diferencias materiales ya explicadas por su clase declarada NO "
                             "cuentan como conflicto abierto y no exigen reconciliación")

_CLASES_DECLARADAS = (HISTORICAL_CHANGE, RESOLVED_BY_PRECEDENCE, SEMANTIC_DIFFERENCE,
                      NORMALIZATION_DIFFERENCE, CASCADE_OF_GEOMETRY_CHANGE)


def get_true_conflict_summary(informe: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Resumen CANÓNICO del informe de coherencia histórica.

    Devuelve, resueltas una sola vez, las dos métricas que el ejecutivo imprime y todas
    las clasificaciones con que la corrida las justifica:

      · `true_conflicts` / `true_conflict_count` — conflictos VERDADEROS (las siete
        condiciones). Es el ÚNICO recuento de conflictos: sale de
        `len(conflictos_abiertos)`, nunca de `requieren_revision`, de `cambios`, del
        número de versiones comparadas ni de un contador legacy.
      · `attributes_compared` / `attributes_compared_count` — atributos con VERSIONES
        RIVALES comparadas y divergencia declarada (conflictos verdaderos + diferencias
        materiales explicadas). NO es un recuento de conflictos.

    INVARIANTE (se verifica aquí y no se delega al llamador):
        `true_conflict_count == len(true_conflicts)`
        `attributes_compared_count == len(attributes_compared)`
        `attributes_compared ⊇ true_conflicts ∪ (todas las clases declaradas)`
    Además, si el informe trae el contador histórico `recuento_conflictos.total`, se
    exige que coincida: dos contadores persistidos que puedan divergir es exactamente
    el defecto que este bloque cierra.
    """
    informe = informe or {}

    # ── conflictos VERDADEROS: la LISTA es la fuente; el contador se deriva de ella ──
    abiertos = [c for c in (informe.get("conflictos_abiertos") or [])
                if isinstance(c, dict) and c.get("atributo")]
    true_conflicts: List[str] = []
    for c in abiertos:
        atributo = str(c["atributo"])
        if atributo not in true_conflicts:
            true_conflicts.append(atributo)

    veredicto_por_atributo: Dict[str, str] = {}
    for atributo, clas in (informe.get("clasificaciones_conflicto") or {}).items():
        if isinstance(clas, dict) and clas.get("veredicto"):
            veredicto_por_atributo[str(atributo)] = str(clas["veredicto"])

    # ── atributos con VERSIONES RIVALES: la estructura del informe es la fuente ──────
    rivales = set(true_conflicts)
    for r in (informe.get("requieren_revision") or []):
        if isinstance(r, dict) and r.get("atributo") and r.get("diferencia_material"):
            rivales.add(str(r["atributo"]))

    def _por_clase(clase: str) -> List[str]:
        """Atributos RIVALES con esa clase declarada (los verdaderos van aparte)."""
        return sorted(a for a in rivales
                      if a not in true_conflicts and veredicto_por_atributo.get(a) == clase)

    resolved_by_precedence = _por_clase(RESOLVED_BY_PRECEDENCE)
    historical_changes = _por_clase(HISTORICAL_CHANGE)
    semantic_differences = _por_clase(SEMANTIC_DIFFERENCE)
    normalization_differences = _por_clase(NORMALIZATION_DIFFERENCE)
    cascades_of_geometry_change = _por_clase(CASCADE_OF_GEOMETRY_CHANGE)

    # Un atributo rival que la corrida declaró con una clase FUERA del vocabulario
    # cerrado no se pierde en silencio: entra en `attributes_compared` y se declara.
    clasificadas = (set(resolved_by_precedence) | set(historical_changes)
                    | set(semantic_differences) | set(normalization_differences)
                    | set(cascades_of_geometry_change))
    # (queda declarado para auditoría; no altera ninguna de las dos métricas)
    diferencias_sin_clase = sorted(rivales - set(true_conflicts) - clasificadas)

    attributes_compared = sorted(rivales)

    resumen: Dict[str, Any] = {
        "version": RESUMEN_CONFLICTOS_VERSION,
        "criterio": ("el recuento de conflictos se deriva SOLO de TRUE_CONFLICT (las siete "
                     "condiciones); `attributes_compared` es la métrica DISTINTA de atributos "
                     "con versiones rivales comparadas y no cuenta conflictos"),
        # ── métrica 1 · conflictos verdaderos (ÚNICO recuento de conflictos) ──────────
        "true_conflicts": list(true_conflicts),
        "true_conflict_count": len(true_conflicts),
        # ── métrica 2 · atributos con versiones rivales comparadas ───────────────────
        "attributes_compared": attributes_compared,
        "attributes_compared_count": len(attributes_compared),
        # ── clasificación declarada (con qué motivo la corrida decidió cada caso) ────
        "resolved_by_precedence": resolved_by_precedence,
        "historical_changes": historical_changes,
        "semantic_differences": semantic_differences,
        "normalization_differences": normalization_differences,
        "cascades_of_geometry_change": cascades_of_geometry_change,
        "diferencias_sin_clase": diferencias_sin_clase,
        "changes_explained_by_source": sorted(
            str(c["atributo"]) for c in (informe.get("cambios_explicados") or [])
            if isinstance(c, dict) and c.get("atributo")),
        # ── consecuencia declarada ──────────────────────────────────────────────────
        "requires_action": bool(true_conflicts),
        # ── rótulos canónicos (el renderer imprime ESTOS, no los suyos) ─────────────
        "rotulos": {
            "true_conflict": ROTULO_CONFLICTO_VERDADERO,
            "attributes_compared": ROTULO_ATRIBUTOS_COMPARADOS,
            "nota_attributes_compared": NOTA_ATRIBUTOS_COMPARADOS,
        },
    }

    # ── INVARIANTES (no se persiste nada que no las cumpla) ─────────────────────────
    if resumen["true_conflict_count"] != len(resumen["true_conflicts"]):
        raise AssertionError("BLOCK 1.1: true_conflict_count != len(true_conflicts)")
    if resumen["attributes_compared_count"] != len(resumen["attributes_compared"]):
        raise AssertionError("BLOCK 1.1: attributes_compared_count != len(attributes_compared)")
    if not set(true_conflicts) <= set(attributes_compared):
        raise AssertionError("BLOCK 1.1: true_conflicts ⊄ attributes_compared")
    _persistido = (informe.get("recuento_conflictos") or {}).get("total")
    if _persistido is not None and int(_persistido) != resumen["true_conflict_count"]:
        raise AssertionError(
            f"BLOCK 1.1: recuento_conflictos.total={_persistido} != "
            f"true_conflict_count={resumen['true_conflict_count']}: dos contadores "
            f"persistidos divergen")
    return resumen


def cargar_matriz_del_caso(folio: str, raiz: Optional[Path] = None) -> Dict[str, Any]:
    """ATTRIBUTE HISTORY MATRIX del folio, si el expediente la tiene versionada.

    Es un INSUMO de la corrida (igual que el informe de coherencia): si no existe, se
    devuelve `{}` y el informe almacenado se usa tal cual. Nunca se escribe aquí.
    """
    folio = str(folio or "").strip()
    if not folio or folio.lower() in ("pendiente", "sin-folio"):
        return {}
    base = Path(raiz) if raiz else Path(__file__).resolve().parent.parent
    candidatos = [
        base / "docs" / "forensics" / folio / "dictus_2" / "ATTRIBUTE_HISTORY_MATRIX.json",
        base / "docs" / "forensics" / folio / "ATTRIBUTE_HISTORY_MATRIX.json",
    ]
    for ruta in candidatos:
        try:
            if ruta.exists():
                return json.loads(ruta.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 — una matriz ilegible no rompe la corrida
            continue
    return {}


def reclasificar_informe(informe: Optional[Dict[str, Any]],
                         matriz: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Recalcula el informe de coherencia con las SIETE condiciones, sin tocar el archivo.

    El informe almacenado del expediente se produjo con el criterio anterior
    (`material and clase == UNEXPLAINED_CONFLICT`). Cuando la matriz histórica está
    disponible, el informe VIGENTE de la corrida se deriva de ella: así el número que
    imprime el ejecutivo sale de `TRUE_CONFLICT` y las clasificaciones quedan persistidas
    por atributo, sin reescribir `docs/forensics/**` (artefacto del expediente).
    """
    informe = informe or {}
    if not matriz or not (matriz.get("cambios") is not None):
        return informe
    recalculado = reporte_consistencia(matriz)
    recalculado["origen"] = "RECOMPUTADO_DESDE_ATTRIBUTE_HISTORY_MATRIX"
    recalculado["informe_almacenado"] = {
        "version": informe.get("version"),
        "veredicto": informe.get("veredicto"),
        "conflictos_abiertos": len(informe.get("conflictos_abiertos") or []),
        "requieren_revision": len(informe.get("requieren_revision") or []),
    }
    return recalculado

def cargar_texto_pdf(ruta: Path) -> str:
    import pymupdf
    with pymupdf.open(str(ruta)) as doc:
        return "\n".join(p.get_text() for p in doc)


def descubrir_versiones(raiz: Path, folio: str = "040-646406",
                        patrones: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Descubre las versiones históricas disponibles del folio en el repositorio."""
    import pymupdf
    patrones = patrones or [folio, folio.replace("-", "_")]
    encontrados: List[Dict[str, Any]] = []
    for p in sorted(raiz.rglob("*.pdf")):
        nombre = p.name
        if not any(x in nombre for x in patrones) and "golden_03i" not in str(p):
            continue
        if "CTL" in nombre or "certificado" in nombre.lower():
            continue
        try:
            with pymupdf.open(str(p)) as doc:
                texto = "\n".join(pg.get_text() for pg in doc)
                paginas = doc.page_count
        except Exception:
            continue
        if folio not in texto and folio.replace("-", " ") not in texto:
            continue
        encontrados.append({
            "version": nombre.replace(".pdf", ""),
            "fecha": datetime.datetime.fromtimestamp(p.stat().st_mtime).astimezone(
                datetime.timezone.utc).strftime("%Y-%m-%d"),
            "origen": str(p.relative_to(raiz)),
            "pdf_sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            "paginas": paginas,
            "texto": texto,
            "identity_binding": "VERIFICADO" if "OFFICIAL_PREDIO" in texto else "NO DECLARADO",
        })
    return encontrados


def escribir_matriz(matriz: Dict[str, Any], destino_json: Path, destino_md: Optional[Path] = None) -> Path:
    destino_json.parent.mkdir(parents=True, exist_ok=True)
    destino_json.write_text(json.dumps(matriz, ensure_ascii=False, indent=1), encoding="utf-8")
    if destino_md is not None:
        rep = reporte_consistencia(matriz)
        lineas = ["# ATTRIBUTE HISTORY MATRIX — folio 040-646406", "",
                  f"Versiones comparadas: **{len(matriz['versiones'])}** · "
                  f"atributos: **{len(matriz['atributos'])}** · "
                  f"cambios detectados: **{len(matriz['cambios'])}** · "
                  f"conflictos abiertos: **{len(matriz['conflictos_historicos_abiertos'])}**", "",
                  "## Versiones", ""]
        for v in matriz["versiones"]:
            lineas.append(f"- `{v['version']}` · {v['fecha']} · {v['origen']} · "
                          f"sha256 {str(v['pdf_sha256'])[:12]}…")
        lineas += ["", "## Conflictos históricos ABIERTOS (materiales, sin explicación)", ""]
        if rep["conflictos_abiertos"]:
            for c in rep["conflictos_abiertos"]:
                lineas += [f"### {c['atributo']} — {c['estado']}", "",
                           f"Valores en conflicto: {', '.join(repr(v) for v in c['valores'])}", "",
                           c["detalle"], ""]
                for k in c["cambios"]:
                    lineas.append(f"- {k['version_anterior']} → {k['version_actual']}: "
                                  f"`{k['anterior']}` → `{k['actual']}` · clase {k['clase']} · "
                                  f"{k['motivo']}")
                lineas.append("")
        else:
            lineas.append("Ninguno.")
        lineas += ["", "## Cambios EXPLICADOS por fuente o método", ""]
        for c in rep["cambios_explicados"]:
            lineas.append(f"- **{c['atributo']}**: {c['detalle']}")
        if not rep["cambios_explicados"]:
            lineas.append("Ninguno.")
        lineas += ["", "## Cambios que REQUIEREN REVISIÓN", ""]
        for c in rep["requieren_revision"]:
            lineas.append(f"- **{c['atributo']}**: {c['detalle']}")
        if not rep["requieren_revision"]:
            lineas.append("Ninguno.")
        destino_md.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return destino_json

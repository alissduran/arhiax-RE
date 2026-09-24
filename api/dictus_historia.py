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
    """HISTORICAL CONSISTENCY REPORT: conflictos abiertos, explicados y por revisar."""
    abiertos, explicados, revisar = [], [], []
    for atributo in sorted(_ATRIBUTOS.keys()):
        info = conflicto_de_atributo(matriz, atributo)
        if info["estado"] == HISTORICAL_CONFLICT:
            abiertos.append(info)
        elif info["estado"] == CAMBIO_CON_FUENTE:
            explicados.append(info)
        elif info["estado"] == REQUIERE_VALIDACION:
            revisar.append(info)
    veredicto = "CONFLICTOS_ABIERTOS" if abiertos else "COHERENTE"
    return {
        "generado_en": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "version": "dictus-historical-consistency/1.0.0",
        "versiones_comparadas": len((matriz or {}).get("versiones") or []),
        "conflictos_abiertos": abiertos,
        "cambios_explicados": explicados,
        "requieren_revision": revisar,
        "veredicto": veredicto,
    }


def sha256_texto(txt: str) -> str:
    return hashlib.sha256(str(txt).encode("utf-8")).hexdigest()


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

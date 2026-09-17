# -*- coding: utf-8 -*-
"""
ARHIAX RE — Territorio de Pasto (Nariño) EN VIVO
================================================

Conector al geoportal oficial del Municipio de Pasto, que publica la base
catastral y la normativa del POT por predio. Sustituye los "PENDIENTE" que tenía
Pasto y lo deja al nivel de Barranquilla/Medellín/Bogotá.

Servicio verificado EN VIVO (2026-09-16):
    https://geoportal.pasto.gov.co/server/rest/services/Planeacion/...

Capas usadas (todas consultables por punto o por código predial):
    Norma_Urbanistica_Riesgo_Suelo/2   Tratamientos: tratamiento_urbanistico,
                                       edificabilidad ("PEMP - 4 pisos - 11,20 metros"),
                                       unidad_territorial, sector_normativo
    Norma_Urbanistica_Riesgo_Suelo/28  Áreas de actividad: clase_de_suelo,
                                       area_actividad, zona ZAVA
    Norma_Urbanistica_Riesgo_Suelo/1   Riesgos por predio: riesgo_volcanico_ea27,
                                       inundacion_ea23, subsidencia_ea29,
                                       remocion_en_masa_ea19, flujos_de_lodo_ea22,
                                       zava_t_269_de_2015
    Estratificacion/4                  Código predial nacional (NUPRE) y matrícula

Medición real (Pasto centro, 1.2136/-77.2811): NUPRE
520010102000000770901900000000, tratamiento PEMP - Conservación del contexto con
ajuste arquitectónico, edificabilidad "4 pisos - 11,20 metros", clase de suelo
Urbano, riesgo volcánico "Bajo".

Postura honesta: cada campo sale de una consulta real; lo que no venga queda
None y el dictamen lo declara PENDIENTE. Nunca se inventan datos del predio.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import requests

BASE = "https://geoportal.pasto.gov.co/server/rest/services"
SRV_NORMA = f"{BASE}/Planeacion/Norma_Urbanistica_Riesgo_Suelo/MapServer"
SRV_ESTRATO = f"{BASE}/Planeacion/Estratificacion/MapServer"
SRV_DPA = f"{BASE}/Planeacion/Division_politico_administrativa/MapServer"

CAPA_TRATAMIENTOS = 2
CAPA_AREAS_ACTIVIDAD = 28
CAPA_RIESGOS_URBANO = 1
CAPA_PREDIOS = 4          # Estratificacion -> códigos prediales
# DPA (auditoría 2026-09-17): capa 1 = Barrios, capa 2 = Comunas. OJO: la capa de
# Barrios NO tiene campo 'barrio'; el nombre vive en el campo **`sector`**.
CAPA_DPA_BARRIOS = 1
CAPA_DPA_COMUNAS = 2
# Tablas de Estratificación: la table 1 se une por codigo_predial_nacional (30
# dígitos) y la table 2 por codigo_predial_corto (15). El estrato NO está en la
# capa predial; hay que traerlo de estas tablas.
TABLA_NOMENCLATURA = 1
TABLA_ESTRATO = 2

TIMEOUT = 15.0
TTL_CACHE = 3600
_UA = {"User-Agent": "ARHIAX-RE/1.0 (Sinergia Consulting Group)"}
_CACHE: Dict[tuple, tuple] = {}

# Campos de riesgo por predio (capa 1) y su etiqueta legible
CAMPOS_RIESGO = [
    ("riesgo_volcanico_ea27", "Riesgo volcanico (POT Pasto)"),
    ("zava_t_269_de_2015", "Zona de amenaza volcanica ZAVA (sentencia T-269/2015)"),
    ("flujos_de_lodo_ea22", "Amenaza por flujos de lodo"),
    ("restricciones_por_lujos_de_lodo", "Restricciones por flujos de lodo"),
    ("remocion_en_masa_ea19", "Amenaza por remocion en masa"),
    ("inundacion_ea23", "Amenaza por inundacion (areas afectadas y en riesgo)"),
    ("subsidencia_ea29", "Amenaza por subsidencia"),
    ("servidumbre_de_lineas_de_alta_t", "Servidumbre de lineas de alta tension"),
]

_NA = ("", None, "sin informacion", "sin información", "n/a", "none")
# En RIESGOS, "No aplica" es una RESPUESTA VÁLIDA y valiosa (el municipio evaluó
# el predio contra ese peligro y no aplica). Descartarla hacía desaparecer la
# fila del dictamen y parecía que el cruce nunca se hizo.
_NA_RIESGO = ("", None, "sin informacion", "sin información")


def _limpio(v) -> Optional[str]:
    """Normaliza valores basura ('Sin información', vacío, None) a None."""
    if v is None:
        return None
    s = str(v).strip()
    if not s or s.lower() in _NA:
        return None
    return s


def _valor_riesgo(v) -> Optional[str]:
    """Como _limpio pero CONSERVA 'No aplica' (respuesta válida en riesgos)."""
    if v is None:
        return None
    s = str(v).strip()
    if s.lower() in _NA_RIESGO:
        return None
    return s


def _estado_capa(filas: Optional[List[dict]]) -> str:
    """Estado independiente por capa (bug E/F): distingue los fallos.

    Semántica exigida por el modelo canónico:
      * None            -> SOURCE_UNAVAILABLE (HTTP != 200, timeout o error ArcGIS)
      * []              -> NO_MATCH (consultado, sin coincidencia)
      * filas sin valor -> NULL_VALUE (respondió pero atributos vacíos)
      * filas con valor -> MATCH_EXACT
    """
    if filas is None:
        return "SOURCE_UNAVAILABLE"
    if not filas:
        return "NO_MATCH"
    if any(any(v for v in (f or {}).values()) for f in filas):
        return "MATCH_EXACT"
    return "NULL_VALUE"


def _query(srv: str, capa: int, *, lat: float = None, lon: float = None,
           where: str = None, distancia_m: float = None,
           timeout: float = TIMEOUT) -> Optional[List[dict]]:
    """Consulta una capa por punto (point-in-polygon) o por expresión WHERE.

    `distancia_m`: si se indica, ArcGIS busca dentro de ese radio (útil cuando la
    dirección geocodificada cae en la CALLE y no dentro del polígono del predio).

    Devuelve la lista de atributos, o None si la consulta NO fue válida
    (HTTP != 200 o error de ArcGIS). Distinguir None de [] es clave: [] significa
    "consultado, sin coincidencia"; None significa "no se pudo consultar" y el
    dictamen debe declararlo PENDIENTE, nunca "sin dato".
    """
    params: Dict[str, Any] = {
        "where": where or "1=1",
        "outFields": "*",
        "returnGeometry": "false",
        "f": "json",
    }
    if lat is not None and lon is not None:
        params.update({
            "geometry": '{"x": %s, "y": %s, "spatialReference": {"wkid": 4326}}' % (lon, lat),
            "geometryType": "esriGeometryPoint",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
        })
        if distancia_m:
            params["distance"] = distancia_m
            params["units"] = "esriSRUnit_Meter"
    try:
        r = requests.get(f"{srv}/{capa}/query", params=params, headers=_UA, timeout=timeout)
    except Exception:
        return None
    if r.status_code != 200:
        return None
    data = r.json() or {}
    if isinstance(data, dict) and data.get("error"):
        return None
    return [f.get("attributes", {}) or {} for f in (data.get("features") or [])]


def _pisos_de_edificabilidad(txt: Optional[str]) -> Optional[int]:
    """Extrae los pisos de 'PEMP - 4 pisos - 11,20 metros' -> 4."""
    if not txt:
        return None
    import re
    m = re.search(r"(\d{1,2})\s*pisos?", str(txt), re.IGNORECASE)
    return int(m.group(1)) if m else None


def _barrio_y_comuna(lat: float, lon: float) -> Dict[str, Any]:
    """Barrio y comuna OFICIALES (División Político-Administrativa municipal).

    OJO (auditoría 2026-09-17): en la capa de Barrios **no existe el campo
    `barrio`**; el nombre vive en el campo **`sector`**. Un conector que busque
    `barrio` falla en silencio. En Comunas el valor viene como "Comuna 1".
    """
    out: Dict[str, Any] = {"barrio": None, "comuna": None,
                           "fuente": "Division_politico_administrativa (DPA)"}
    if lat is None or lon is None:
        return out
    for capa, campo, clave, dist in (
            (CAPA_DPA_BARRIOS, "sector", "barrio", None),
            (CAPA_DPA_BARRIOS, "sector", "barrio", 30),
            (CAPA_DPA_COMUNAS, "comuna", "comuna", None),
            (CAPA_DPA_COMUNAS, "comuna", "comuna", 30)):
        if out.get(clave):
            continue
        filas = _query(SRV_DPA, capa, lat=lat, lon=lon, distancia_m=dist) or []
        if filas:
            v = _limpio(filas[0].get(campo))
            if v:
                out[clave] = v
    return out


def _estrato_y_nomenclatura(nupre: Optional[str],
                            codigo_corto: Optional[str] = None) -> Dict[str, Any]:
    """Estrato y nomenclatura OFICIALES desde las TABLAS de Estratificación.

    El estrato NO está en la capa predial: vive en `Estratificacion` table 1
    (une por `codigo_predial_nacional`, 30 dígitos) y table 2 (une por
    `codigo_predial_corto`, 15 dígitos). `Barrios.estrato` es NULL en toda la
    capa, así que no sirve como fuente.
    """
    out: Dict[str, Any] = {"estrato": None, "nomenclatura_oficial": None,
                           "barrio_tabla": None, "comuna_tabla": None,
                           "fuente": "Estratificacion (tablas 1 y 2)"}
    fila = None
    if nupre:
        fila = (_query(SRV_ESTRATO, TABLA_NOMENCLATURA,
                       where="codigo_predial_nacional='%s'" % nupre) or [None])[0]
    if fila is None and codigo_corto:
        fila = (_query(SRV_ESTRATO, TABLA_NOMENCLATURA,
                       where="codigo_predial_corto='%s'" % codigo_corto) or [None])[0]
    if fila:
        out["estrato"] = _limpio(fila.get("estrato"))
        out["nomenclatura_oficial"] = (_limpio(fila.get("nomenclatura_igac"))
                                       or _limpio(fila.get("nomenclatura_secretaria_de_plan")))
        out["barrio_tabla"] = _limpio(fila.get("barrio"))
        out["comuna_tabla"] = _limpio(fila.get("comuna"))
    if not out["estrato"] and codigo_corto:
        f2 = _query(SRV_ESTRATO, TABLA_ESTRATO,
                    where="codigo_predial_corto='%s'" % codigo_corto)
        if f2:
            out["estrato"] = _limpio(f2[0].get("estrato"))
    return out


def _centroide_del_predio(nupre: str) -> Optional[tuple]:
    """Centroide del polígono del predio a partir de su NUPRE.

    Necesario porque barrio y comuna son capas de POLÍGONO: si ARHIAX resuelve el
    predio por código (lo correcto) no tiene coordenadas con las que consultarlas.
    Se pide la geometría en WGS84 (outSR=4326) y se calcula el centroide del
    primer anillo. Devuelve (lat, lon) o None.
    """
    if not nupre:
        return None
    try:
        r = requests.get(
            f"{SRV_ESTRATO}/{CAPA_PREDIOS}/query",
            params={"where": "codigo_predial_nacional='%s'" % nupre,
                    "outFields": "objectid", "returnGeometry": "true",
                    "outSR": "4326", "f": "json"},
            headers=_UA, timeout=TIMEOUT)
        if r.status_code != 200:
            return None
        data = r.json() or {}
        if data.get("error"):
            return None
        feats = data.get("features") or []
        if not feats:
            return None
        anillos = (feats[0].get("geometry") or {}).get("rings") or []
        if not anillos or not anillos[0]:
            return None
        anillo = anillos[0]
        xs = [p[0] for p in anillo if len(p) >= 2]
        ys = [p[1] for p in anillo if len(p) >= 2]
        if not xs or not ys:
            return None
        return (sum(ys) / len(ys), sum(xs) / len(xs))
    except Exception:
        return None


def _tokens_direccion(direccion: str):
    """Extrae (grupos numéricos de la nomenclatura, número de unidad) de una
    dirección colombiana.

    'CARRERA 26 Nº 21 - 55'          -> (['26','21','55'], None)
    'KR 26 # 21 - 47 APTO 101'       -> (['26','21','47'], '101')
    'K 26 21 47 AP 101'              -> (['26','21','47'], '101')
    """
    import re
    if not direccion:
        return [], None
    txt = str(direccion).upper()
    unidad = None
    m_u = re.search(r"(?:APTO|APARTAMENTO|AP|UNIDAD|UND|INT|INTERIOR|CASA|CS)\s*[:.]?\s*(\d{1,4})", txt)
    if m_u:
        unidad = m_u.group(1)
    cuerpo = txt[:m_u.start()] if m_u else txt
    # Se descartan los números de vía que son parte del nombre (p. ej. '26 ESTE')
    cuerpo = re.sub(r"\b(ESTE|OESTE|NORTE|SUR|E|O|N|S|BIS|A|B|C|D)\b", " ", cuerpo)
    toks = []
    for m in re.finditer(r"(\d{1,4})", cuerpo):
        n = m.group(1)
        if n and n != "0":
            toks.append(n)
    return toks, unidad


def nupre_por_nomenclatura(direccion: str, max_candidatos: int = 6) -> list:
    """Resuelve el NUPRE municipal a partir de una DIRECCIÓN/NOMENCLATURA.

    Es la ÚNICA vía que encuentra las **unidades de propiedad horizontal**, que no
    están en las capas de polígono: la tabla de nomenclatura sí las contiene
    (p. ej. `K 26 21 47 AP 101`). Auditoría 2026-09-17: sin esto, ARHIAX resolvía
    por coordenadas y tomaba un predio vecino.

    Devuelve una lista de candidatos ordenada por coincidencia (primero el que
    coincide con la unidad declarada) con: nupre, nomenclatura, es_ph, estrato,
    comuna, area_construida, coincide_unidad.
    """
    toks, unidad = _tokens_direccion(direccion)
    if len(toks) < 3:
        return []
    patron = "%s %s %s" % (toks[0], toks[-2], toks[-1])
    campos = ("objectid,codigo_predial_nacional,codigo_predial_corto,"
              "nomenclatura_igac,nomenclatura_secretaria_de_plan,"
              "uso_propiedad_horizontal,estrato,comuna,area_construida,"
              "numero_de_placa")
    candidatos = []
    for columna in ("nomenclatura_igac", "nomenclatura_secretaria_de_plan",
                    "nomenclatura_no_estandarizada"):
        filas = _query(SRV_ESTRATO, TABLA_NOMENCLATURA,
                       where="%s LIKE '%%%s%%'" % (columna, patron),
                       timeout=TIMEOUT) or []
        for f in filas:
            nom = _limpio(f.get(columna)) or ""
            nupre = _limpio(f.get("codigo_predial_nacional"))
            if not nupre:
                continue
            coincide = bool(unidad) and (unidad in nom)
            candidatos.append({
                "nupre": nupre,
                "nomenclatura": nom,
                "columna_match": columna,
                "es_ph": bool(_limpio(f.get("uso_propiedad_horizontal"))),
                "uso_ph": _limpio(f.get("uso_propiedad_horizontal")),
                "estrato": _limpio(f.get("estrato")),
                "comuna": _limpio(f.get("comuna")),
                "area_construida": _limpio(f.get("area_construida")),
                "coincide_unidad": coincide,
                "entrada": direccion,
                "patron_buscado": patron,
                "unidad_buscada": unidad,
            })
    # Unicidad por NUPRE, priorizando la coincidencia de unidad
    vistos, unicos = set(), []
    for c in sorted(candidatos, key=lambda x: (not x["coincide_unidad"],)):
        if c["nupre"] in vistos:
            continue
        vistos.add(c["nupre"])
        unicos.append(c)
    return unicos[:max_candidatos]


def consultar_pasto(*, lat: float = None, lon: float = None,
                    codigo_predial: str = None) -> Dict[str, Any]:
    """Datos territoriales de un predio de Pasto, por punto o por código.

    Returns:
        {
          "disponible": bool,
          "resolucion": "por_punto" | "por_codigo",
          "predio":  {numero_predial_nacional, codigo_predial_anterior, area_catastral_terreno, ...},
          "entorno": {barrio?, comuna?, clase_suelo, tratamiento, codigo_tratamiento,
                      altura_maxima, edificabilidad_texto, uso_economico, area_actividad, ...},
          "riesgos": {volcanico, zava, inundacion, remocion_masa, subsidencia,
                      flujos_lodo, ...},
          "fuente":  {...},
        }
    """
    clave = ("punto", round(lat, 4), round(lon, 4)) if (lat is not None and lon is not None) \
        else ("codigo", str(codigo_predial))
    ahora = time.time()
    if clave in _CACHE:
        ts, cacheado = _CACHE[clave]
        if ahora - ts < TTL_CACHE:
            return cacheado

    res: Dict[str, Any] = {
        "disponible": False,
        "resolucion": "por_punto" if lat is not None else "por_codigo",
        "predio": {},
        "entorno": {},
        "riesgos": {},
        "condicion": {},
        "fuente": {
            "nombre": "Geoportal Municipal de Pasto (Planeacion)",
            "url": BASE,
            "estado": "PENDIENTE",
        },
        # Estado independiente por capa (bug E/F). Default = SOURCE_UNAVAILABLE;
        # se sobrescribe al final con el estado real de cada capa consultada.
        "capas": {
            "tratamientos_urbanisticos": {"capa": CAPA_TRATAMIENTOS,
                                          "estado": "SOURCE_UNAVAILABLE"},
            "areas_de_actividad": {"capa": CAPA_AREAS_ACTIVIDAD,
                                   "estado": "SOURCE_UNAVAILABLE"},
            "riesgos_urbano": {"capa": CAPA_RIESGOS_URBANO,
                               "estado": "SOURCE_UNAVAILABLE"},
            "predios_estratificacion": {"capa": CAPA_PREDIOS,
                                        "estado": "SOURCE_UNAVAILABLE"},
            "dpa_barrios_comunas": {"estado": "SOURCE_UNAVAILABLE"},
            "tablas_estratificacion": {"estado": "SOURCE_UNAVAILABLE"},
        },
    }
    if lat is None and not _limpio(codigo_predial):
        res["fuente"]["estado"] = "sin coordenadas ni codigo predial"
        return res

    kwargs: Dict[str, Any] = {}
    if lat is not None and lon is not None:
        kwargs = {"lat": lat, "lon": lon}
    else:
        cod = _limpio(codigo_predial)
        kwargs = {"where": "codigo_predial_nacional='%s'" % cod.replace("'", "")}

    # Si el predio se busca por PUNTO y el primer intento no coincide, se
    # reintenta con 30 m de radio: una dirección geocodificada suele caer en la
    # CALLE (fuera del polígono del predio) y sin esto el dictamen quedaba sin
    # datos teniendo el municipio la información.
    def _q(srv: str, capa: int):
        r = _query(srv, capa, **kwargs)
        if r == [] and lat is not None and lon is not None:
            r2 = _query(srv, capa, lat=lat, lon=lon, distancia_m=30)
            if r2:
                return r2
        return r

    # ── Tratamientos urbanísticos (POT + edificabilidad) ──
    trat = _q(SRV_NORMA, CAPA_TRATAMIENTOS)
    # ── Áreas de actividad (clase de suelo, uso) ──
    act = _q(SRV_NORMA, CAPA_AREAS_ACTIVIDAD)
    # ── Riesgos por predio (incluye riesgo volcánico) ──
    rie = _q(SRV_NORMA, CAPA_RIESGOS_URBANO)
    # ── Códigos prediales (NUPRE) ──
    pre = _q(SRV_ESTRATO, CAPA_PREDIOS) if not codigo_predial else None

    respuestas = [x for x in (trat, act, rie, pre) if x is not None]
    if not respuestas:
        res["fuente"]["estado"] = "NO DISPONIBLE -- el geoportal de Pasto no respondio"
        _CACHE[clave] = (ahora, res)
        return res

    res["disponible"] = True
    t0 = (trat or [{}])[0] if trat else {}
    a0 = (act or [{}])[0] if act else {}
    r0 = (rie or [{}])[0] if rie else {}
    p0 = (pre or [{}])[0] if pre else {}

    cod_nac = (_limpio(p0.get("codigo_predial_nacional")) or _limpio(t0.get("codigo_predial"))
               or _limpio(a0.get("codigo_predial_nacional")) or _limpio(codigo_predial))
    res["predio"] = {
        "numero_predial_nacional": cod_nac,
        "nupre": cod_nac,
        "codigo_predial_anterior": _limpio(p0.get("codigo_predial_anterior"))
        or _limpio(a0.get("codigo_predial_anterior")),
        "codigo_predial_corto": _limpio(p0.get("codigo_predial_corto")),
        "codigo_manzana": _limpio(p0.get("codigo_de_manzana")),
        "sector_catastral": _limpio(p0.get("sector_catastral")),
        "direccion_oficial": _limpio(p0.get("direccion")),
        "matricula_inmobiliaria": _limpio(p0.get("matricula_inmobiliaria")),
        "area_catastral_terreno": p0.get("area_igac_m2") or p0.get("area_construida"),
        "avaluo_igac": _limpio(p0.get("avaluo_igac")),
    }

    edificabilidad = _limpio(t0.get("edificabilidad"))
    pisos_max = _pisos_de_edificabilidad(edificabilidad)
    res["entorno"] = {
        "clase_suelo": _limpio(a0.get("clase_de_suelo")),
        "uso_economico": _limpio(a0.get("area_actividad")) or _limpio(a0.get("clasificacion")),
        "area_actividad": _limpio(a0.get("area_actividad")),
        "codigo_area_actividad": _limpio(a0.get("codigo_area_actividad")),
        "tratamiento": _limpio(t0.get("tratamiento_urbanistico")),
        "codigo_tratamiento": _limpio(t0.get("sector_normativo")),
        "unidad_territorial": _limpio(t0.get("unidad_territorial")),
        # 'comuna': el dictamen ya lee entorno['comuna'] en la sección de
        # localización; en Pasto el equivalente es la unidad territorial.
        "comuna": _limpio(t0.get("unidad_territorial")) or _limpio(a0.get("ubicacion")),
        "ubicacion": _limpio(a0.get("ubicacion")),
        "edificabilidad_texto": edificabilidad,
        "altura_maxima": str(pisos_max) if pisos_max else None,
        "nivel_intervencion_pemp": _limpio(t0.get("nivel_intervencion_pemp")),
        "zona_especial_pemp": _limpio(a0.get("zona_especial_uso_pemp")),
    }

    riesgos: Dict[str, Any] = {}
    for campo, etiqueta in CAMPOS_RIESGO:
        v = _valor_riesgo(r0.get(campo))
        if v:
            riesgos[campo] = v
    res["riesgos"] = riesgos

    # ── Cierre de variables que estaban en PENDIENTE/N/D ──────────────────────
    # Barrio, comuna, estrato y nomenclatura oficial: la auditoría 2026-09-17
    # demostró que EXISTEN en fuentes oficiales del municipio (DPA y tablas de
    # Estratificación) y que ARHIAX no las consultaba.
    # Si se resolvió por CÓDIGO no hay coordenadas: se obtienen del centroide del
    # propio polígono para poder cruzar las capas de POLÍGONO (barrio/comuna).
    _lat_dpa, _lon_dpa = lat, lon
    if _lat_dpa is None and cod_nac:
        _centro = _centroide_del_predio(cod_nac)
        if _centro:
            _lat_dpa, _lon_dpa = _centro
            res["predio"]["centroide"] = {"lat": round(_centro[0], 7),
                                          "lon": round(_centro[1], 7)}
    _dpa = _barrio_y_comuna(_lat_dpa, _lon_dpa)
    if _dpa.get("barrio"):
        res["entorno"]["barrio"] = _dpa["barrio"]
    if _dpa.get("comuna"):
        res["entorno"]["comuna"] = _dpa["comuna"]
    else:
        res["entorno"]["comuna"] = res["entorno"].get("comuna") or None
    _est = _estrato_y_nomenclatura(cod_nac, (res["predio"] or {}).get("codigo_predial_corto"))
    if _est.get("estrato"):
        res["entorno"]["estrato"] = _est["estrato"]
    if _est.get("nomenclatura_oficial") and not (res["predio"] or {}).get("direccion_oficial"):
        res["predio"]["direccion_oficial"] = _est["nomenclatura_oficial"]
    if not res["entorno"].get("comuna") and _est.get("comuna_tabla"):
        res["entorno"]["comuna"] = _est["comuna_tabla"]
    if not res["entorno"].get("barrio") and _est.get("barrio_tabla"):
        res["entorno"]["barrio"] = _est["barrio_tabla"]
    res["entorno"]["fuente_administrativa"] = _dpa.get("fuente")
    res["entorno"]["fuente_estrato"] = _est.get("fuente") if _est.get("estrato") else None
    # OJO: un dict con todas las claves en None NO es "tener datos". Se comprueban
    # los VALORES, no que el dict sea no vacío (un punto fuera del municipio deja
    # predio/entorno llenos de None y antes se reportaba como "consultada").
    # Se excluyen las claves de PROCEDENCIA (fuente_*): son metadatos, no datos.
    _hay_datos = (any(v for k, v in res["predio"].items() if not k.startswith("fuente"))
                  or any(v for k, v in res["entorno"].items() if not k.startswith("fuente"))
                  or bool(riesgos))
    res["fuente"]["estado"] = ("CONSULTADA EN VIVO (Geoportal Municipal de Pasto)"
                              if _hay_datos else
                              "CONSULTADA -- sin coincidencia en el punto del predio")

    # ── Estado independiente por capa (bug E/F) ────────────────────────────────
    # Cada capa del geoportal declara su propio estado para que el dictamen y la
    # Declaración de Alcance puedan decir "esta capa respondió con coincidencia,
    # esta otra no, esta dio error" sin colapsar todo en un único 'CONSULTADA'.
    res["capas"] = {
        "tratamientos_urbanisticos": {"capa": CAPA_TRATAMIENTOS,
                                      "estado": _estado_capa(trat)},
        "areas_de_actividad": {"capa": CAPA_AREAS_ACTIVIDAD,
                               "estado": _estado_capa(act)},
        "riesgos_urbano": {"capa": CAPA_RIESGOS_URBANO,
                           "estado": _estado_capa(rie)},
        "predios_estratificacion": {
            "capa": CAPA_PREDIOS,
            "estado": "NOT_APPLICABLE" if pre is None else _estado_capa(pre),
        },
        "dpa_barrios_comunas": {
            "estado": ("MATCH_EXACT" if (_dpa.get("barrio") or _dpa.get("comuna"))
                       else "NO_MATCH"),
        },
        "tablas_estratificacion": {
            "estado": ("MATCH_EXACT" if (_est.get("estrato") or _est.get("nomenclatura_oficial")
                                         or _est.get("barrio_tabla") or _est.get("comuna_tabla"))
                       else "NO_MATCH"),
        },
    }

    _CACHE[clave] = (ahora, res)
    return res


def filas_pasto(res: Dict[str, Any]) -> List[tuple]:
    """Filas (label, valor) para las tablas catastral/urbanística del dictamen."""
    predio = (res or {}).get("predio") or {}
    ent = (res or {}).get("entorno") or {}
    filas = []
    if predio.get("numero_predial_nacional"):
        filas.append(("Codigo predial nacional (NUPRE)", predio["numero_predial_nacional"]))
    if predio.get("codigo_predial_anterior"):
        filas.append(("Codigo predial anterior", predio["codigo_predial_anterior"]))
    if predio.get("matricula_inmobiliaria"):
        filas.append(("Matricula inmobiliaria (municipio)", predio["matricula_inmobiliaria"]))
    if predio.get("area_catastral_terreno"):
        filas.append(("Area catastral (m2)", predio["area_catastral_terreno"]))
    if ent.get("clase_suelo"):
        filas.append(("Clasificacion del suelo (POT Pasto)", ent["clase_suelo"]))
    if ent.get("area_actividad"):
        filas.append(("Area de actividad (POT Pasto)", ent["area_actividad"]))
    if ent.get("tratamiento"):
        filas.append(("Tratamiento urbanistico (POT Pasto)", ent["tratamiento"]))
    if ent.get("edificabilidad_texto"):
        filas.append(("Edificabilidad (POT Pasto)", ent["edificabilidad_texto"]))
    if ent.get("unidad_territorial"):
        filas.append(("Unidad territorial", ent["unidad_territorial"]))
    return filas

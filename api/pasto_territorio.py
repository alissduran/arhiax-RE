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

CAPA_TRATAMIENTOS = 2
CAPA_AREAS_ACTIVIDAD = 28
CAPA_RIESGOS_URBANO = 1
CAPA_PREDIOS = 4          # Estratificacion -> códigos prediales

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
    # OJO: un dict con todas las claves en None NO es "tener datos". Se comprueban
    # los VALORES, no que el dict sea no vacío (un punto fuera del municipio deja
    # predio/entorno llenos de None y antes se reportaba como "consultada").
    _hay_datos = (any(res["predio"].values()) or any(res["entorno"].values())
                  or bool(riesgos))
    res["fuente"]["estado"] = ("CONSULTADA EN VIVO (Geoportal Municipal de Pasto)"
                              if _hay_datos else
                              "CONSULTADA -- sin coincidencia en el punto del predio")

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

# -*- coding: utf-8 -*-
"""
ARHIAX RE — Riesgo volcánico (Servicio Geológico Colombiano, EN VIVO)
=====================================================================

Consulta el servicio oficial del SGC para saber en qué ZONA DE AMENAZA
VOLCÁNICA cae un predio. Es determinante en ciudades como Pasto (Volcán
Galeras, a ~9 km), Manizales (Nevado del Ruiz), Popayán (Puracé) o Ipiales
(Chiles-Cerro Negro).

Servicio verificado en vivo (2026-09-16):
    https://srvags.sgc.gov.co/arcgis/rest/services/Amenaza_Volcanica/Amenaza_Volcanica/MapServer

Capas usadas (consulta point-in-polygon):
    19  'Amenaza_Volcanica_integrada'  -> grupo del VOLCÁN GALERAS
    64  'Amenaza_Volcanica_P'          -> consolidado (otros volcanes)
Cada consulta devuelve el volcán, el GRADO_AMENAZA (Alta/Media/Baja) y el
fenómeno (lahares, caída de piroclastos, flujos piroclásticos...).

Medición real en Pasto: el centro cae en "Amenaza Baja" por caída de
piroclastos, pero el sector norte (Torobajo) cae en **Amenaza Alta por
lahares** del Galeras.

Postura honesta: si el servicio no responde, `disponible=False` y el dictamen
lo declara PENDIENTE. NUNCA se asume "sin riesgo volcánico" por falta de datos.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import requests

BASE = ("https://srvags.sgc.gov.co/arcgis/rest/services/"
        "Amenaza_Volcanica/Amenaza_Volcanica/MapServer")

# (id de capa, etiqueta legible)
CAPAS = [
    (19, "Amenaza volcanica integrada (grupo Galeras)"),
    (64, "Amenaza volcanica consolidada"),
]

TIMEOUT = 12.0
TTL_CACHE = 3600          # 1 hora
_UA = {"User-Agent": "ARHIAX-RE/1.0 (Sinergia Consulting Group)"}

_CACHE: Dict[tuple, tuple] = {}

# Orden de severidad del grado de amenaza del SGC
_ORDEN = {"alta": 3, "media": 2, "baja": 1}
_NIVEL_ARHIAX = {3: "ALTO", 2: "MEDIO", 1: "BAJO", 0: "NO EVALUADO"}


def _celda(lat: float, lon: float) -> tuple:
    return (round(lat, 3), round(lon, 3))


def _severidad(grado: Optional[str]) -> int:
    """3 Alta | 2 Media | 1 Baja | 0 desconocido."""
    g = (grado or "").lower()
    for clave, valor in _ORDEN.items():
        if clave in g:
            return valor
    return 0


def _consultar_capa(capa_id: int, lat: float, lon: float):
    """Point-in-polygon contra una capa.

    Devuelve (respondio, zona|None, error|None):
      · (True,  dict, None)  el servicio contestó y el punto cae en esa zona
      · (True,  None, None)  el servicio contestó pero el punto NO cae en la capa
      · (False, None, str)   la consulta NO fue válida (HTTP != 200, o ArcGIS
        devolvió 200 con un objeto 'error')

    IMPORTANTE: ArcGIS responde 200 con {"error": ...} cuando la consulta es
    inválida (p. ej. un campo inexistente en outFields). Tratar eso como "sin
    zona" afirmaría que el predio no tiene amenaza volcánica cuando en realidad
    NUNCA se consultó. Por eso se detecta y se cuenta como fallo.
    """
    params = {
        "where": "1=1",
        # outFields=* : los nombres de campo cambian entre capas (19 y 64 tienen
        # esquemas distintos); pedir campos fijos provocaba el error mencionado.
        "outFields": "*",
        "geometry": '{"x": %s, "y": %s, "spatialReference": {"wkid": 4326}}' % (lon, lat),
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "returnGeometry": "false",
        "f": "json",
    }
    r = requests.get(f"{BASE}/{capa_id}/query", params=params,
                     headers=_UA, timeout=TIMEOUT)
    if r.status_code != 200:
        return False, None, f"HTTP {r.status_code}"
    data = r.json() or {}
    if isinstance(data, dict) and data.get("error"):
        msg = (data.get("error") or {}).get("message") or "error de ArcGIS"
        return False, None, str(msg)[:120]
    feats = data.get("features") or []
    if not feats:
        return True, None, None
    at = feats[0].get("attributes", {}) or {}
    # Algunas capas (p. ej. la consolidada) codifican el fenómeno como NÚMERO
    # (medido: FENOMENO_VOLCANICO=4). Mostrar "4" en el dictamen no dice nada:
    # en ese caso se usa la descripción textual.
    _fen = at.get("FENOMENO_VOLCANICO") or at.get("FENOMENOS")
    if _fen is None or str(_fen).strip().isdigit():
        _fen = (at.get("CATEGORIA_ESPECIFICA_FENOMENO") or at.get("DESCRIPCION")
                or at.get("LEYENDA_1") or "N/D")
    return True, {
        "capa_id": capa_id,
        "volcan": at.get("NOMBRE_VOLCAN") or at.get("VOLCAN") or "N/D",
        "grado": at.get("GRADO_AMENAZA") or at.get("AMENAZA") or "N/D",
        "fenomeno": _fen,
        "descripcion": (at.get("DESCRIPCION") or at.get("LEYENDA_1") or "").strip(),
        "zona": at.get("ZONA_SUBZONA"),
    }, None


def verificar_riesgo_volcanico(lat: float, lon: float) -> Dict[str, Any]:
    """Zona de amenaza volcánica oficial (SGC) del punto indicado.

    Returns:
        {
          "disponible": bool,
          "zonas": [ {volcan, grado, fenomeno, descripcion, capa_id} ],
          "peor_grado": str | None,
          "nivel": "ALTO" | "MEDIO" | "BAJO" | "NO EVALUADO",
          "fuente": {"nombre", "url", "estado"},
          "error": str | None,
        }
    """
    clave = _celda(lat, lon)
    ahora = time.time()
    if clave in _CACHE:
        ts, cacheado = _CACHE[clave]
        if ahora - ts < TTL_CACHE:
            return cacheado

    res: Dict[str, Any] = {
        "disponible": False,
        "zonas": [],
        "peor_grado": None,
        "nivel": "NO EVALUADO",
        "fuente": {
            "nombre": "Servicio Geológico Colombiano (SGC) — Mapa de amenaza volcánica",
            "url": BASE,
            "estado": "PENDIENTE",
        },
        "error": None,
    }

    hubo_respuesta = False
    for capa_id, etiqueta in CAPAS:
        try:
            respondio, zona, error = _consultar_capa(capa_id, lat, lon)
        except Exception as e:  # noqa: BLE001 — el dictamen nunca debe romperse
            res["error"] = (res["error"] or "") + f" capa {capa_id}: {str(e)[:60]};"
            continue
        if error:
            res["error"] = (res["error"] or "") + f" capa {capa_id}: {error};"
            continue
        if respondio:
            hubo_respuesta = True
        if zona:
            zona["etiqueta"] = etiqueta
            res["zonas"].append(zona)

    if hubo_respuesta:
        res["disponible"] = True
        res["fuente"]["estado"] = ("CONSULTADA EN VIVO (SGC)"
                                   if res["zonas"] else
                                   "CONSULTADA — el predio no cae en zona de amenaza volcánica cartografiada")
        if res["zonas"]:
            peor = max(res["zonas"], key=lambda z: _severidad(z.get("grado")))
            res["peor_grado"] = peor.get("grado")
            res["nivel"] = _NIVEL_ARHIAX.get(_severidad(peor.get("grado")), "NO EVALUADO")
        else:
            res["nivel"] = "BAJO"
    else:
        res["error"] = res["error"] or "el servicio del SGC no respondió"

    _CACHE[clave] = (ahora, res)
    return res


def filas_riesgo_volcanico(res: Dict[str, Any]) -> List[tuple]:
    """Filas (label, valor) para la tabla de riesgos del dictamen."""
    if not res or not res.get("disponible"):
        return [("Riesgo volcanico (SGC)", "NO DISPONIBLE -- el servicio del SGC no respondio "
                                           "al generar el dictamen (verificar en sgc.gov.co)")]
    zonas = res.get("zonas") or []
    if not zonas:
        return [("Riesgo volcanico (SGC)", "SIN ZONA DE AMENAZA VOLCANICA CARTOGRAFIADA "
                                           "en el punto del predio (mapa oficial SGC)")]
    filas = []
    for z in zonas:
        volcan = str(z.get("volcan") or "N/D")
        grado = str(z.get("grado") or "N/D")
        fen = str(z.get("fenomeno") or "N/D")
        filas.append((f"Riesgo volcanico -- {volcan}",
                      f"<b>{grado.upper()}</b> -- {fen}"))
    filas.append(("Fuente del riesgo volcanico",
                  "Servicio Geologico Colombiano (SGC) -- consulta en vivo"))
    return filas


def hallazgo_volcanico(res: Dict[str, Any]):
    """Hallazgo ARHIAX si el predio cae en amenaza volcánica Alta o Media.

    Devuelve la tupla (sev, color, fondo, titulo, fuente, desc, implicacion) o
    None si no hay amenaza Alta/Media (o si el servicio no respondió: no se
    afirma nada sin dato).
    """
    from reportlab.lib import colors

    if not res or not res.get("disponible"):
        return None
    zonas = res.get("zonas") or []
    if not zonas:
        return None
    peor = max(zonas, key=lambda z: _severidad(z.get("grado")))
    sev_n = _severidad(peor.get("grado"))
    if sev_n < 2:  # solo Alta o Media
        return None

    volcan = str(peor.get("volcan") or "N/D")
    grado = str(peor.get("grado") or "")
    fen = str(peor.get("fenomeno") or "N/D")
    es_alta = sev_n == 3
    sev = "ALTO" if es_alta else "MEDIO"
    tc = colors.HexColor("#D92C2C") if es_alta else colors.HexColor("#F08C2B")
    bg = colors.HexColor("#FFF0F0") if es_alta else colors.HexColor("#FFF5EB")

    detalle = []
    for z in zonas:
        detalle.append(f"{z.get('grado')} -- {z.get('fenomeno')} ({z.get('volcan')})")
    return (
        sev, tc, bg,
        f"H-VOL | Amenaza Volcanica {grado.replace('Amenaza ', '').upper()}: {fen} ({volcan})",
        "SGC -- Mapa oficial de amenaza volcanica (consulta en vivo)",
        ("El predio se ubica dentro de una zona de <b>{}</b> del volcan {} segun el mapa "
         "oficial del Servicio Geologico Colombiano, por el fenomeno: {}. "
         "Zonas detectadas: {}.").format(grado, volcan, fen, "; ".join(detalle)),
        ("Verificacion OBLIGATORIA con el plan de contingencia municipal y el SGC: la amenaza "
         "volcanica condiciona el uso del suelo, las polizas de seguros, la originacion "
         "hipotecaria y puede restringir licencias de construccion. Documentar el nivel de "
         "amenaza en el expediente de credito."),
    )

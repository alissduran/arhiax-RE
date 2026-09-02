# -*- coding: utf-8 -*-
"""
ARHIAX RE — Simulación geométrica automática de sombras (9:00 AM / 3:00 PM)

Genera las imágenes sombra_9am.png y sombra_3pm.png que el dictamen espera, SIN
ArcGIS Pro ni navegador:

  1. Huella del edificio  -> capa 310 (Construcción) del catastro en vivo de
     Barranquilla (con su altura real). Si el servicio no responde o no hay
     feature, se usa una huella estimada (rectángulo según área) marcada.
  2. Posición solar        -> api/solar_engine.py (azimut/elevación para la
     fecha y hora local, UTC-5).
  3. Sombra proyectada     -> la huella desplazada en la dirección opuesta al
     sol (azimut+180°) una longitud L = altura / tan(elevación); el polígono de
     sombra es el convex hull de huella y huella desplazada (shapely).
  4. Render PNG            -> Pillow (vista en planta con norte, escala métrica
     y leyenda).

Postura honesta: las imágenes son una SIMULACIÓN GEOMÉTRICA (no un render 3D
fotorrealista); el PDF lo indica cuando las imágenes provienen de este módulo.
"""

from __future__ import annotations

import datetime
import math
from pathlib import Path
from typing import Any, Optional

from PIL import Image, ImageDraw, ImageFont

from solar_engine import get_solar_position

# Fuentes para el render (multi-plataforma)
_FONT_CANDIDATAS = [
    "C:\\Windows\\Fonts\\arialbd.ttf",
    "C:\\Windows\\Fonts\\arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _fuente(size: int):
    for p in _FONT_CANDIDATAS:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _metros_por_grado_lat(lat: float) -> float:
    return 110540.0


def _huella_a_plano(coords, lat0: float, lon0: float):
    """Convierte coordenadas [lon, lat] (GeoJSON) a metros planos locales
    (x = este, y = norte) con origen en (lat0, lon0)."""
    m_lat = _metros_por_grado_lat(lat0)
    m_lon = 111320.0 * math.cos(math.radians(lat0))
    return [(round((lon - lon0) * m_lon, 2), round((lat - lat0) * m_lat, 2)) for lon, lat in coords]


def _obtener_construccion(lat: float, lon: float) -> dict:
    """Busca la construcción (capa 310) más cercana al punto en el catastro vivo.
    Retorna {huella_xy, altura_m, pisos, area_m2, fuente} o None si no hay datos."""
    from integrations.arcgis_client import query_layer_bbox
    base = "https://miciudad.barranquilla.gov.co/gis/rest/services/catastro/datosabiertos/MapServer"
    buff = 0.0015  # ~150 m
    bbox = (lon - buff, lat - buff, lon + buff, lat + buff)
    try:
        r = query_layer_bbox(base, 310, bbox, max_features=10, timeout=12.0, return_geometry=True)
    except Exception:
        r = {"disponible": False, "features": []}
    if not r.get("disponible") or not r.get("features"):
        return None

    mejor = None
    mejor_dist = None
    for feat in r["features"]:
        geom = feat.get("geometry")
        props = feat.get("properties", {}) or {}
        if not geom or geom.get("type") not in ("Polygon", "MultiPolygon"):
            continue
        try:
            coords = geom["coordinates"]
            if geom["type"] == "MultiPolygon":
                coords = coords[0]
            pts = _huella_a_plano(coords[0], lat, lon)
        except Exception:
            continue
        if len(pts) < 3:
            continue
        # Distancia del centroide de la huella al punto
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        dist = math.hypot(cx, cy)
        if mejor is None or dist < mejor_dist:
            mejor_dist = dist
            mejor = (pts, props)

    if not mejor:
        return None
    pts, props = mejor

    altura = float(props.get("altura_total_construccion") or 0)
    pisos = float(props.get("total_pisos") or 0)
    fuente_altura = "catastro (altura_total_construccion)"
    if altura <= 0:
        altura = pisos * 3.0 if pisos > 0 else 9.0
        fuente_altura = "catastro (estimada: pisos x 3m)" if pisos > 0 else "estimada 9 m (sin dato de altura)"
    area = float(props.get("st_area(shape)") or 0)

    return {
        "huella_xy": pts,
        "altura_m": round(altura, 1),
        "pisos": int(pisos or 0),
        "area_m2": round(area, 1),
        "fuente": f"Catastro Barranquilla capa 310 (distancia {round(mejor_dist, 1)} m)",
        "fuente_altura": fuente_altura,
    }


def _sombra_poligono(huella_xy, altura_m: float, az: float, el: float):
    """Devuelve el polígono de sombra (lista xy) o None si el sol está muy bajo."""
    if el <= 2.0:
        return None
    L = altura_m / math.tan(math.radians(el))
    if L > 5000:  # sol casi en el horizonte: sombra no razonable
        return None
    az_sombra = math.radians(az + 180.0)
    dx = L * math.sin(az_sombra)
    dy = L * math.cos(az_sombra)
    # Convex hull simple de huella + huella desplazada (shapely si está, si no manual)
    try:
        from shapely.geometry import Polygon, MultiPoint
        puntos = [tuple(p) for p in huella_xy] + [(p[0] + dx, p[1] + dy) for p in huella_xy]
        hull = MultiPoint(puntos).convex_hull
        return list(hull.exterior.coords)[:-1] if hull.geom_type == "Polygon" else None
    except Exception:
        # Fallback: rectángulo envolvente desplazado (aproximación)
        xs = [p[0] for p in huella_xy]
        ys = [p[1] for p in huella_xy]
        return [
            (min(xs) + dx, min(ys) + dy),
            (max(xs) + dx, min(ys) + dy),
            (max(xs) + dx, max(ys) + dy),
            (min(xs) + dx, max(ys) + dy),
        ]


def _render_imagen(huella_xy, sombra_xy, hora_txt, hora_corta, color_sombra, az, el,
                   altura_m, fuente_huella, out_path: Path) -> None:
    W, H = 1000, 680
    margen = 70
    img = Image.new("RGBA", (W, H), "#F7F8FC")
    d = ImageDraw.Draw(img)

    # Extents (metros) de huella + sombra
    puntos = list(huella_xy) + (list(sombra_xy) if sombra_xy else [])
    xs = [p[0] for p in puntos]
    ys = [p[1] for p in puntos]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    ancho_m = max(maxx - minx, 5.0)
    alto_m = max(maxy - miny, 5.0)
    escala = min((W - 2 * margen) / ancho_m, (H - 2 * margen - 40) / alto_m)

    def a_px(p):
        px = margen + (p[0] - minx) * escala
        py = H - margen - 40 - (p[1] - miny) * escala  # norte arriba
        return (px, py)

    # Grilla cada 10 m (sutil)
    paso = 10.0
    x0 = math.floor(minx / paso) * paso
    while x0 <= maxx:
        px = a_px((x0, miny))[0]
        d.line([(px, margen), (px, H - margen - 40)], fill="#E4E8F0", width=1)
        x0 += paso
    y0 = math.floor(miny / paso) * paso
    while y0 <= maxy:
        py = a_px((minx, y0))[1]
        d.line([(margen, py), (W - margen, py)], fill="#E4E8F0", width=1)
        y0 += paso

    # Sombra
    if sombra_xy:
        d.polygon([a_px(p) for p in sombra_xy], fill=color_sombra, outline=None)

    # Huella (relleno oscuro + borde)
    pts_img = [a_px(p) for p in huella_xy]
    d.polygon(pts_img, fill="#3A3F4B", outline="#1A1F2E", width=2)

    # Norte (flecha)
    d.text((W - 90, margen - 10), "N ↑", font=_fuente(18), fill="#0D2C6B")

    # Título / hora
    d.text((margen - 10, 14), f"Sombra proyectada — {hora_txt}", font=_fuente(22), fill="#0D2C6B")
    d.text((margen - 10, 44),
           f"Sol: azimut {az}° | elevación {el}° | altura edificio: {altura_m} m",
           font=_fuente(14), fill="#555555")

    # Leyenda inferior
    ly = H - 24
    d.rectangle([(margen - 10, ly - 10), (margen + 14, ly + 6)], fill="#3A3F4B")
    d.text((margen + 22, ly - 10), f"Edificio (huella) — {hora_corta}", font=_fuente(13), fill="#333333")
    lx = margen + 320
    d.rectangle([(lx, ly - 10), (lx + 24, ly + 6)], fill=color_sombra)
    d.text((lx + 32, ly - 10), f"Sombra {hora_corta}", font=_fuente(13), fill="#333333")

    # Escala métrica
    ex = W - margen - 150
    d.line([(ex, ly - 4), (ex + 100, ly - 4)], fill="#000000", width=2)
    d.text((ex + 30, ly - 26), "20 m", font=_fuente(12), fill="#333333")

    # Nota de origen
    d.text((margen - 10, H - 60),
           "Simulación geométrica ARHIAX (posición solar + huella/altura: " + fuente_huella + ")",
           font=_fuente(11), fill="#888888")

    img.save(out_path)
    print(f"[SHADOW] imagen generada: {out_path.name} (sombra {hora_corta})")


def generar_sombras_automaticas(lat: float, lon: float, assets_dir, fecha: Optional[datetime.date] = None) -> dict[str, Any]:
    """Genera sombra_9am.png y sombra_3pm.png en assets_dir.

    Retorna metadatos: {origen, altura_m, fuente_huella, fuente_altura, rutas, error?}.
    Nunca lanza: ante cualquier fallo devuelve error descriptivo (sin imágenes).
    """
    assets = Path(assets_dir)
    assets.mkdir(parents=True, exist_ok=True)
    fecha = fecha or datetime.date.today()

    const = _obtener_construccion(lat, lon)
    if const:
        huella_xy = const["huella_xy"]
        altura_m = const["altura_m"]
        fuente_huella = const["fuente"] + " | altura: " + const["fuente_altura"]
    else:
        # Huella estimada (rectángulo ~12x12 m) marcada como estimación
        lado = 12.0
        huella_xy = [(-lado / 2, -lado / 2), (lado / 2, -lado / 2),
                     (lado / 2, lado / 2), (-lado / 2, lado / 2)]
        altura_m = 9.0
        fuente_huella = "huella estimada 12x12 m y altura 9 m (sin feature catastral en el BBOX)"

    salidas = []
    for hora, label, corto, color in [
        (9, "9:00 AM (Manana)", "9 AM", (31, 79, 175, 110)),
        (15, "3:00 PM (Tarde)", "3 PM", (217, 125, 36, 110)),
    ]:
        dt_local = datetime.datetime(fecha.year, fecha.month, fecha.day, hora, 0, 0)
        az, el = get_solar_position(lat, lon, dt_local)
        sombra = _sombra_poligono(huella_xy, altura_m, az, el)
        out = assets / (f"sombra_{'9am' if hora == 9 else '3pm'}.png")
        try:
            _render_imagen(huella_xy, sombra, label, corto, color, az, el,
                           altura_m, fuente_huella, out)
            salidas.append(str(out))
        except Exception as e:
            return {"origen": "simulacion_geometrica", "error": f"render {label}: {e}"}

    return {
        "origen": "simulacion_geometrica",
        "altura_m": altura_m,
        "fuente_huella": fuente_huella,
        "imagenes": salidas,
        "fecha": fecha.isoformat(),
    }

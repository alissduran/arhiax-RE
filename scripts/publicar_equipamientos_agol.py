#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Publica los EQUIPAMIENTOS URBANOS de una ciudad en tu ArcGIS Online
====================================================================

QUÉ PROBLEMA RESUELVE
---------------------
La sección 03 del dictamen (equipamiento urbano) consulta OpenStreetMap EN VIVO
y Overpass —servicio público gratuito— se cae y limita las IPs de datacenter
(Vercel corre en AWS). Este script toma el MISMO dato de OpenStreetMap, lo
congela en un archivo y lo publica como **capa propia en tu ArcGIS Online**:
cobertura completa, sin caídas y sin límites. ARHIAx después consulta esa capa.

CÓMO USARLO (en tu PC)
----------------------
    pip install requests

    # 1) Ver qué saldría, sin publicar nada (recomendado la primera vez)
    python publicar_equipamientos_agol.py --ciudad pasto --solo-preparar

    # 2) Publicar en tu ArcGIS Online (pide usuario y contraseña por consola)
    python publicar_equipamientos_agol.py --ciudad pasto --publicar --usuario TU_USUARIO

    # Opcional: compartirla para que ARHIAx la lea sin token
    python publicar_equipamientos_agol.py --ciudad pasto --publicar \
        --usuario TU_USUARIO --compartir-org

FUENTES DE DATOS
----------------
  --fuente overpass   (por defecto) UNA consulta a Overpass por el área de la
                      ciudad. No descarga nada pesado y solo necesita 'requests'.
  --fuente geofabrik  Usa el extracto de Colombia de Geofabrik (772 MB, hay que
                      descargarlo y requiere 'pyshp'). Útil si Overpass falla.

SEGURIDAD
---------
La contraseña nunca se guarda ni se imprime: se pide por consola (oculta) o se
lee de ARCGIS_PASSWORD. Al terminar, el script imprime la URL del servicio:
eso es lo que hay que pasarle a ARHIAx para conectarla.
"""

from __future__ import annotations

import argparse
import csv
import getpass
import json
import os
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("Falta 'requests'. Instálalo con:  pip install requests")

PORTAL_DEFECTO = "https://www.arcgis.com"
URL_GEOFABRIK = "https://download.geofabrik.de/south-america/colombia-latest-free.shp.zip"
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

# (lon_min, lat_min, lon_max, lat_max)
CIUDADES = {
    "pasto": (-77.50, 1.00, -77.00, 1.45),
    "barranquilla": (-74.95, 10.85, -74.65, 11.10),
    "medellin": (-75.80, 5.98, -75.30, 6.50),
    "bogota": (-74.25, 4.45, -73.90, 4.85),
}

# valor de la etiqueta OSM -> categoría que usa ARHIAx en la sección 03
CATEGORIAS = {
    "Salud": {
        "hospital", "clinic", "doctors", "dentist", "pharmacy", "nursing_home",
    },
    "Educacion": {
        "school", "kindergarten", "college", "university", "library",
    },
    "Comercio": {
        "supermarket", "mall", "marketplace", "convenience", "department_store",
        "bakery", "butcher", "greengrocer", "clothes", "hardware",
    },
    "Recreacion": {
        "park", "playground", "pitch", "sports_centre", "stadium",
        "swimming_pool", "garden", "golf_course",
    },
}
CLAVES_OSM = ("amenity", "shop", "leisure")

CAMPOS_CSV = ["nombre", "categoria", "tipo_osm", "direccion", "lat", "lon"]


# ─────────────────────────────────────────────────────────────
# Lógica pura (fácil de probar, sin red)
# ─────────────────────────────────────────────────────────────
def clasificar_poi(tags: dict) -> str | None:
    """Devuelve la categoría ARHIAx de un elemento OSM, o None si no aplica."""
    if not isinstance(tags, dict):
        return None
    for clave in CLAVES_OSM:
        valor = str(tags.get(clave) or "").strip().lower()
        if not valor:
            continue
        for categoria, valores in CATEGORIAS.items():
            if valor in valores:
                return categoria
    return None


def dentro_del_area(lat: float, lon: float, bbox: tuple) -> bool:
    lon_min, lat_min, lon_max, lat_max = bbox
    return lon_min <= lon <= lon_max and lat_min <= lat <= lat_max


def fila_desde_elemento(elem: dict, bbox: tuple) -> dict | None:
    """Convierte un elemento de Overpass en una fila del CSV (o None)."""
    tags = elem.get("tags") or {}
    nombre = str(tags.get("name") or "").strip()
    if not nombre:
        return None
    categoria = clasificar_poi(tags)
    if not categoria:
        return None
    lat = elem.get("lat") or (elem.get("center") or {}).get("lat")
    lon = elem.get("lon") or (elem.get("center") or {}).get("lon")
    if lat is None or lon is None:
        return None
    if not dentro_del_area(float(lat), float(lon), bbox):
        return None
    tipo = next((str(tags[c]).lower() for c in CLAVES_OSM if tags.get(c)), "")
    direccion = " ".join(
        str(tags.get(k, "")) for k in ("addr_street", "addr_housenumber") if tags.get(k)
    ).strip()
    return {
        "nombre": nombre[:180],
        "categoria": categoria,
        "tipo_osm": tipo[:60],
        "direccion": direccion[:180],
        "lat": round(float(lat), 7),
        "lon": round(float(lon), 7),
    }


def deduplicar(filas: list) -> list:
    """Quita duplicados por (nombre, categoría) conservando el primero."""
    vistos, salida = set(), []
    for f in filas:
        clave = (f["nombre"].lower(), f["categoria"])
        if clave in vistos:
            continue
        vistos.add(clave)
        salida.append(f)
    return salida


def escribir_csv(filas: list, destino: Path) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CAMPOS_CSV)
        w.writeheader()
        w.writerows(filas)
    print(f"[OK] CSV preparado: {destino}  ({len(filas):,} filas)")
    conteo: dict = {}
    for f in filas:
        conteo[f["categoria"]] = conteo.get(f["categoria"], 0) + 1
    for cat in sorted(conteo):
        print(f"       {cat}: {conteo[cat]:,}")
    return destino


# ─────────────────────────────────────────────────────────────
# Fuente 1: Overpass (una sola consulta, sin descargas)
# ─────────────────────────────────────────────────────────────
def _consulta_overpass(bbox: tuple, timeout: int = 180) -> str:
    lon_min, lat_min, lon_max, lat_max = bbox
    area = f"{lat_min},{lon_min},{lat_max},{lon_max}"
    valores = "|".join(sorted({v for vs in CATEGORIAS.values() for v in vs}))
    partes = []
    for clave in CLAVES_OSM:
        partes.append(f'  node["{clave}"~"^({valores})$"]({area});')
        partes.append(f'  way["{clave}"~"^({valores})$"]({area});')
    return "[out:json][timeout:%d];\n(\n%s\n);\nout center;" % (timeout, "\n".join(partes))


def pois_desde_overpass(bbox: tuple, timeout: int = 180) -> list:
    consulta = _consulta_overpass(bbox, timeout)
    print(f"[i] Consultando Overpass una sola vez (área {bbox})...")
    ultimo_error = None
    for url in OVERPASS_ENDPOINTS:
        t0 = time.time()
        try:
            r = requests.post(url, data={"data": consulta},
                              headers={"User-Agent": "ARHIAX-RE/1.0"},
                              timeout=timeout + 30)
            if r.status_code != 200:
                ultimo_error = f"HTTP {r.status_code}"
                print(f"    {url} -> HTTP {r.status_code}, siguiente espejo")
                continue
            elementos = (r.json() or {}).get("elements") or []
            print(f"    {url} -> {len(elementos):,} elementos en {time.time()-t0:.0f}s")
            filas = [f for f in (fila_desde_elemento(e, bbox) for e in elementos) if f]
            return deduplicar(filas)
        except Exception as e:  # noqa: BLE001
            ultimo_error = str(e)[:80]
            print(f"    {url} -> fallo: {ultimo_error}")
    print(f"[!] Overpass no respondió ({ultimo_error}). "
          f"Puedes reintentar o usar --fuente geofabrik")
    return []


# ─────────────────────────────────────────────────────────────
# Fuente 2: Geofabrik (772 MB, requiere pyshp)
# ─────────────────────────────────────────────────────────────
def descargar_geofabrik(destino: Path) -> Path:
    if destino.exists() and destino.stat().st_size > 100_000_000:
        print(f"[=] Ya existe {destino.name} ({destino.stat().st_size/1e6:.0f} MB)")
        return destino
    print(f"[↓] Descargando {URL_GEOFABRIK} (~772 MB)")
    with requests.get(URL_GEOFABRIK, stream=True, timeout=120) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length") or 0)
        hecho = 0
        tmp = destino.with_suffix(".parcial")
        with open(tmp, "wb") as fh:
            for trozo in r.iter_content(1024 * 1024):
                fh.write(trozo)
                hecho += len(trozo)
                if total:
                    print(f"\r    {hecho/1e6:6.0f}/{total/1e6:.0f} MB "
                          f"({hecho*100//total}%)", end="", flush=True)
        print()
        tmp.replace(destino)
    return destino


def pois_desde_geofabrik(zip_path: Path, bbox: tuple) -> list:
    import zipfile
    try:
        import shapefile  # pyshp
    except ImportError:
        sys.exit("Esta fuente necesita 'pyshp'. Instálalo con:  pip install pyshp\n"
                 "O usa la fuente por defecto:  --fuente overpass")
    carpeta = Path("_osm_extraido")
    carpeta.mkdir(parents=True, exist_ok=True)
    print(f"[i] Extrayendo POIs de {zip_path.name}")
    with zipfile.ZipFile(zip_path) as z:
        nombres = [n for n in z.namelist() if n.endswith("gis_osm_pois_free_1.")]
        if not nombres:
            sys.exit(f"No se encontró gis_osm_pois_free_1.* en {zip_path.name}")
        for n in nombres:
            z.extract(n, carpeta)
    shp = next(carpeta.rglob("gis_osm_pois_free_1.shp"))
    lector = shapefile.Reader(str(shp))
    campos = [f[0] for f in lector.fields[1:]]
    idx = {n: i for i, n in enumerate(campos)}
    filas = []
    for sr in lector.iterShapeRecords():
        rec = sr.record
        try:
            lat, lon = sr.shape.points[0][1], sr.shape.points[0][0]
        except (IndexError, AttributeError):
            continue
        if not dentro_del_area(lat, lon, bbox):
            continue
        # En el shapefile de Geofabrik el valor OSM viene en el campo 'fclass'
        i_fclass, i_name = idx.get("fclass"), idx.get("name")
        nombre = str(rec[i_name] if i_name is not None else "").strip()
        fclass = str(rec[i_fclass] if i_fclass is not None else "").strip().lower()
        if not nombre:
            continue
        categoria = next((c for c, vals in CATEGORIAS.items() if fclass in vals), None)
        if not categoria:
            continue
        filas.append({
            "nombre": nombre[:180],
            "categoria": categoria,
            "tipo_osm": fclass[:60],
            "direccion": "",
            "lat": round(float(lat), 7),
            "lon": round(float(lon), 7),
        })
    print(f"[i] POIs dentro del área: {len(filas):,}")
    return deduplicar(filas)


# ─────────────────────────────────────────────────────────────
# Publicación en ArcGIS Online (REST, sin dependencias extra)
# ─────────────────────────────────────────────────────────────
def payload_publish(nombre_capa: str) -> dict:
    """Parámetros de publicación: CSV con lat/lon, SIN geocodificar."""
    return {
        "type": "csv",
        "locationType": "coordinates",
        "latitudeFieldName": "lat",
        "longitudeFieldName": "lon",
        "name": nombre_capa,
    }


def obtener_token(portal: str, usuario: str, password: str) -> str:
    r = requests.post(f"{portal}/sharing/rest/generateToken",
                      data={"username": usuario, "password": password,
                            "referer": portal, "expiration": 120, "f": "json"},
                      timeout=30)
    j = r.json()
    if "token" not in j:
        sys.exit(f"[X] No se pudo autenticar en {portal}: {j.get('error', j)}")
    print(f"[OK] Autenticado como {usuario}")
    return j["token"]


def subir_csv(portal, token, usuario, titulo, csv_path, descripcion, tags) -> str:
    with open(csv_path, "rb") as fh:
        r = requests.post(
            f"{portal}/sharing/rest/content/users/{usuario}/addItem",
            data={"title": titulo, "type": "CSV", "tags": tags,
                  "description": descripcion, "f": "json", "token": token},
            files={"file": (csv_path.name, fh, "text/csv")}, timeout=300)
    j = r.json()
    if not j.get("success"):
        sys.exit(f"[X] Error al subir el CSV: {j.get('error', j)}")
    print(f"[OK] CSV subido (item {j['id']})")
    return j["id"]


def publicar_capa(portal, token, usuario, nombre_capa: str) -> list:
    r = requests.post(
        f"{portal}/sharing/rest/content/users/{usuario}/publish",
        data={"filetype": "csv",
              "publishParameters": json.dumps(payload_publish(nombre_capa)),
              "f": "json", "token": token}, timeout=300)
    j = r.json()
    if not j.get("success"):
        sys.exit(f"[X] Error al publicar: {j.get('error', j)}")
    print(f"[OK] Capa publicada (item {j.get('itemId')})")
    return j.get("services") or []


def compartir(portal, token, item_id: str, todos: bool, organizacion: bool) -> None:
    data = {"f": "json", "token": token}
    if todos:
        data["everyone"] = "true"
    if organizacion:
        data["org"] = "true"
    if len(data) == 2:
        return
    requests.post(f"{portal}/sharing/rest/content/items/{item_id}/share",
                  data=data, timeout=60)
    print(f"[OK] Compartida con {'todos (público)' if todos else 'la organización'}")


# ─────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(
        description="Publica los equipamientos urbanos de OpenStreetMap en tu ArcGIS Online.")
    ap.add_argument("--ciudad", default="pasto", choices=sorted(CIUDADES))
    ap.add_argument("--fuente", default="overpass", choices=("overpass", "geofabrik"),
                    help="overpass (una consulta, por defecto) o geofabrik (zip de 772 MB)")
    ap.add_argument("--zip", dest="zip_path", default="colombia-latest-free.shp.zip")
    ap.add_argument("--descargar", action="store_true",
                    help="Descargar el zip de Geofabrik si falta")
    ap.add_argument("--salida", default=None, help="Ruta del CSV de salida")
    ap.add_argument("--solo-preparar", action="store_true",
                    help="Solo generar el CSV (no publica en ArcGIS)")
    ap.add_argument("--publicar", action="store_true",
                    help="Publicar el CSV como capa en ArcGIS Online")
    ap.add_argument("--usuario", default=os.environ.get("ARCGIS_USER"))
    ap.add_argument("--portal", default=PORTAL_DEFECTO)
    ap.add_argument("--titulo", default=None)
    ap.add_argument("--compartir-org", action="store_true")
    ap.add_argument("--compartir-publico", action="store_true")
    args = ap.parse_args()

    if not args.solo_preparar and not args.publicar:
        ap.error("Indica --solo-preparar (genera el CSV) o --publicar (sube a ArcGIS Online)")

    ciudad = args.ciudad
    bbox = CIUDADES[ciudad]
    salida = Path(args.salida or f"equipamientos_{ciudad}.csv")

    # 1) Datos
    if args.fuente == "overpass":
        filas = pois_desde_overpass(bbox)
    else:
        zip_path = Path(args.zip_path)
        if not zip_path.exists():
            if args.descargar:
                zip_path = descargar_geofabrik(zip_path)
            else:
                sys.exit(f"No existe {zip_path}. Descárgalo de {URL_GEOFABRIK}\n"
                         f"o ejecuta de nuevo con --descargar")
        filas = pois_desde_geofabrik(zip_path, bbox)

    if not filas:
        sys.exit("[X] No se obtuvieron equipamientos. Revisa la conexión o usa otra fuente.")
    escribir_csv(filas, salida)

    if not args.publicar:
        print("\n[i] CSV listo. Para publicarlo:")
        print(f"    python {Path(__file__).name} --ciudad {ciudad} --publicar --usuario TU_USUARIO")
        print("    (o súbelo a mano en ArcGIS Online: Content > New item > tu CSV > Publish)")
        return 0

    # 2) Publicación
    usuario = args.usuario or input("Usuario de ArcGIS Online: ").strip()
    if not usuario:
        sys.exit("[X] Falta el usuario de ArcGIS Online.")
    password = os.environ.get("ARCGIS_PASSWORD") or getpass.getpass(
        f"Contraseña de {usuario} (no se guarda ni se muestra): ")

    titulo = args.titulo or f"Equipamientos urbanos - {ciudad.title()} (OSM)"
    token = obtener_token(args.portal, usuario, password)
    item_csv = subir_csv(
        args.portal, token, usuario, f"{titulo} (datos)", salida,
        descripcion=("Equipamientos urbanos (salud, educacion, comercio y recreacion) "
                     "derivados de OpenStreetMap, publicados como capa estable para el "
                     "motor de dictamenes ARHIAX."),
        tags="ARHIAX,equipamientos,OSM," + ciudad)

    nombre_capa = f"Equipamientos_{ciudad.title()}".replace(" ", "_")
    servicios = publicar_capa(args.portal, token, usuario, nombre_capa)

    item_capa = next((s.get("serviceItemId") for s in servicios if s.get("serviceItemId")), None)
    url = next((s.get("serviceurl") for s in servicios if s.get("serviceurl")), None)
    if item_capa:
        compartir(args.portal, token, item_capa, args.compartir_publico, args.compartir_org)
    if item_capa and not url:
        for _ in range(30):
            r = requests.get(f"{args.portal}/sharing/rest/content/items/{item_capa}",
                             params={"f": "json", "token": token}, timeout=30)
            url = (r.json() or {}).get("url")
            if url:
                break
            time.sleep(3)

    print("\n" + "=" * 68)
    print("LISTO. Pásale esto a ARHIAx para conectar la capa:")
    print("=" * 68)
    print(f"  URL del servicio : {url}")
    print(f"  Item de la capa  : {item_capa}")
    print("  Campos           : nombre, categoria, tipo_osm, lat, lon")
    if url:
        print("\n  Prueba (debe devolver JSON con features):")
        print(f"  {url}/0/query?where=1%3D1&outFields=*&resultRecordCount=3&f=json")
    print("\n[i] Si la dejaste privada, ARHIAx necesita un token: genera una API key")
    print("    en ArcGIS Online y déjala en Vercel como ARHIAX_ESRI_TOKEN")
    print("    (nunca en el repositorio).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

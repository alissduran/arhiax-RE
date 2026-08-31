#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
HERRAMIENTA CLI ARHIAX RE: Consulta de Amenaza y Riesgo de Predios
Permite consultar la afectación por remoción en masa y áreas en riesgo en Barranquilla.

Uso:
    python check_predio_riesgo.py --lat 10.9985 --lon -74.8252
    python check_predio_riesgo.py --direccion "Tv 43 # 100-50, Barranquilla"
    python check_predio_riesgo.py --lat 10.9985 --lon -74.8252 --output resultado.json
"""

import sys
import json
import hashlib
import argparse
import datetime
from pathlib import Path

# Garantizar que api/ esté en el path
_API_DIR = str(Path(__file__).resolve().parent / "api")
if _API_DIR not in sys.path:
    sys.path.insert(0, _API_DIR)

from geospatial_engine import evaluate_predio


def print_banner():
    print("="*65)
    print("        A R H I A X   R E  -  EVALUADOR GEOESPACIAL DE RIESGO")
    print("        Sinergia Consulting Group · Gobierno Territorial")
    print("="*65)


def resolver_coordenadas_desde_direccion(direccion: str):
    """
    Convierte una dirección textual a coordenadas (lat, lon)
    usando el normalizador de direcciones ARHIAX + geocodificación Nominatim.
    """
    try:
        _root = str(Path(__file__).resolve().parent)
        if _root not in sys.path:
            sys.path.insert(0, _root)
        from address_normalizer import normalize_address_colombia
        direccion_norm = normalize_address_colombia(direccion)
    except Exception:
        direccion_norm = direccion

    # Geocodificación via Nominatim (OpenStreetMap) — sin API key requerida
    try:
        import urllib.request, urllib.parse
        query = urllib.parse.urlencode({"q": f"{direccion_norm}, Barranquilla, Colombia", "format": "json", "limit": "1"})
        url = f"https://nominatim.openstreetmap.org/search?{query}"
        req = urllib.request.Request(url, headers={"User-Agent": "ARHIAX-RE/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        if data:
            lat = float(data[0]["lat"])
            lon = float(data[0]["lon"])
            print(f"\n[OK] Direccion normalizada : {direccion_norm}")
            print(f"[OK] Geocodificacion       : Lat {lat:.5f}, Lon {lon:.5f}")
            return lat, lon
        else:
            print(f"\n[!] No se encontraron coordenadas para: {direccion_norm}")
            sys.exit(1)
    except Exception as e:
        print(f"\n[!] Error en geocodificación: {e}")
        sys.exit(1)


def main():
    print_banner()

    parser = argparse.ArgumentParser(
        description="Consulta de Amenaza y Riesgo por Coordenadas o Dirección",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--lat", type=float, help="Latitud del predio (ej. 10.9985)")
    parser.add_argument("--lon", type=float, help="Longitud del predio (ej. -74.8252)")
    parser.add_argument("--direccion", type=str, help="Dirección textual (ej. 'Tv 43 # 100-50, Barranquilla')")
    parser.add_argument("--output", type=str, help="Ruta de archivo JSON para exportar el diagnóstico (ej. resultado.json)")

    args = parser.parse_args()

    lat = args.lat
    lon = args.lon

    # Resolver coordenadas desde dirección si no se proporcionaron
    if (lat is None or lon is None) and args.direccion:
        lat, lon = resolver_coordenadas_desde_direccion(args.direccion)
    elif lat is None or lon is None:
        print("\n[?] Ingrese las coordenadas o dirección del predio a evaluar:")
        print("    Opciones: --lat / --lon  o  --direccion 'Dirección completa'")
        print("\n    Ingreso manual de coordenadas:")
        try:
            input_lat = input("    • Latitud  (ej: 10.9985): ").strip()
            input_lon = input("    • Longitud (ej: -74.8252): ").strip()
            lat = float(input_lat)
            lon = float(input_lon)
        except ValueError:
            print("\n[!] Error: Las coordenadas deben ser números decimales válidos.")
            sys.exit(1)

    print(f"\n[+] Procesando intersección espacial para: Lat {lat}, Lon {lon} ...")
    res = evaluate_predio(lat, lon)

    am = res['amenaza_remocion_masa']
    ri = res['areas_en_riesgo']

    print("\n" + "-"*65)
    print("                    RESULTADO DEL DIAGNÓSTICO")
    print("-" * 65)
    print(f" [*] Coordenadas: [{lat}, {lon}]")
    if args.direccion:
        print(f" [*] Dirección  : {args.direccion}")
    print()
    print(" [1] AMENAZA POR REMOCIÓN EN MASA:")
    print(f"     • Afectación:     {'SÍ (Dentro de zona)' if am['intersecta'] else 'NO (Sin afectación)'}")
    print(f"     • Nivel Amenaza:  {am['nivel']}")
    print(f"     • Clase de Suelo: {am['clase_suelo']}")
    print(f"     • Polígono ID:    {am['objectid'] or 'N/A'}")
    print(f"     • Área Polígono:  {am['area_poligono_m2']:,.2f} m²")
    print()
    print(" [2] ZONIFICACIÓN DE ÁREAS EN RIESGO:")
    print(f"     • Afectación:     {'SÍ (Dentro de zona)' if ri['intersecta'] else 'NO (Sin afectación)'}")
    print(f"     • Nivel Riesgo:   {ri['nivel']}")
    print(f"     • Clase de Suelo: {ri['clase_suelo']}")
    print(f"     • Polígono ID:    {ri['objectid'] or 'N/A'}")
    print(f"     • Área Polígono:  {ri['area_poligono_m2']:,.2f} m²")
    print("-" * 65)
    print("\n [!] RESUMEN EJECUTIVO ARHIAX:")
    print(f"    \"{res['resumen_ejecutivo']}\"\n")
    print("=" * 65)

    # Exportar JSON de auditoría si se solicitó
    if args.output:
        now = datetime.datetime.now(datetime.timezone.utc)
        export_data = {
            "arhiax_version": "RE-1.0",
            "timestamp_utc": now.isoformat(),
            "input": {
                "lat": lat,
                "lon": lon,
                "direccion": args.direccion or None
            },
            "resultado": res,
            "hash_integridad": hashlib.sha256(
                json.dumps(res, sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest()
        }
        output_path = Path(args.output)
        output_path.write_text(json.dumps(export_data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n[OK] Diagnostico exportado a: {output_path.resolve()}")


if __name__ == "__main__":
    main()


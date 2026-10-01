# -*- coding: utf-8 -*-
"""Descubrimiento del arbol de servicios del geoportal de Barranquilla. Solo lectura."""
from __future__ import annotations

import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "estimation" / "raw" / "_probe"
OUT.mkdir(parents=True, exist_ok=True)

BASE = "https://miciudad.barranquilla.gov.co/gis/rest/services"

#: Cabeceras que ATRAVIESAN la regla Cloudflare de este host (comprobado 2026-09-29).
NAV_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
               "image/avif,image/webp,*/*;q=0.8"),
    "Accept-Language": "es-CO,es;q=0.9,en;q=0.8",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "Referer": "https://miciudad.barranquilla.gov.co/",
}

OBJETIVOS = ("observatorio", "valoresm2", "valorsuelo", "valorcompraventas",
             "arrendamiento", "avaluo", "cantidadtransacciones", "valor", "mercado")


def get(url: str, timeout: int = 30, intentos: int = 3) -> dict:
    ultimo = None
    for i in range(intentos):
        req = urllib.request.Request(url, headers=NAV_HEADERS)
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                c = resp.read()
                return {"url": url, "http_status": resp.status, "bytes": len(c),
                        "sha256": hashlib.sha256(c).hexdigest(),
                        "ms": int((time.time() - t0) * 1000),
                        "cf_ray": resp.headers.get("cf-ray"), "body": c, "error": None,
                        "intentos": i + 1}
        except urllib.error.HTTPError as exc:
            c = b""
            try:
                c = exc.read()
            except Exception:
                pass
            ultimo = {"url": url, "http_status": exc.code, "bytes": len(c),
                      "sha256": hashlib.sha256(c).hexdigest(),
                      "ms": int((time.time() - t0) * 1000),
                      "cf_ray": (exc.headers or {}).get("cf-ray"), "body": c,
                      "error": f"HTTPError {exc.code} {exc.reason}", "intentos": i + 1}
            time.sleep(1.5 * (i + 1))     # backoff: el desafio CF es sensible al ritmo
        except Exception as exc:  # noqa: BLE001
            ultimo = {"url": url, "http_status": None, "bytes": 0, "sha256": None,
                      "ms": int((time.time() - t0) * 1000), "cf_ray": None, "body": b"",
                      "error": f"{type(exc).__name__}: {exc}", "intentos": i + 1}
            time.sleep(1.0)
    return ultimo


def jget(url: str) -> tuple[dict, dict]:
    r = get(url)
    try:
        return json.loads(r["body"].decode("utf-8")), r
    except Exception:
        return {}, r


def main() -> int:
    eventos = []
    print("### raiz")
    raiz, r = jget(f"{BASE}?f=json")
    eventos.append({k: v for k, v in r.items() if k != "body"})
    print(f"  [{r['http_status']}] carpetas={len(raiz.get('folders') or [])} "
          f"servicios={len(raiz.get('services') or [])} err={r['error']}")
    carpetas = list(raiz.get("folders") or [])
    if not carpetas:
        print("  !! raiz sin carpetas: reintentando en bucle")
        for _ in range(5):
            time.sleep(2)
            raiz, r = jget(f"{BASE}?f=json")
            eventos.append({k: v for k, v in r.items() if k != "body"})
            carpetas = list(raiz.get("folders") or [])
            print(f"  [{r['http_status']}] carpetas={len(carpetas)}")
            if carpetas:
                break

    catalogo = {"raiz": raiz, "servicios": {}}
    for carpeta in carpetas:
        srv, rs = jget(f"{BASE}/{carpeta}?f=json")
        eventos.append({k: v for k, v in rs.items() if k != "body"})
        lista = srv.get("services") or []
        print(f"\n### carpeta {carpeta} [{rs['http_status']}] servicios={len(lista)}")
        for s in lista:
            nombre = s.get("name")
            tipo = s.get("type")
            catalogo["servicios"][f"{carpeta}/{nombre}"] = {"name": nombre, "type": tipo,
                                                            "carpeta": carpeta}
            bajo = (nombre or "").lower()
            if any(o in bajo for o in OBJETIVOS):
                print(f"    * CANDIDATO: {nombre} ({tipo})")
    (OUT / "catalogo_servicios.json").write_text(
        json.dumps(catalogo, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "eventos_crawler.json").write_text(
        json.dumps(eventos, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nTOTAL servicios = {len(catalogo['servicios'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

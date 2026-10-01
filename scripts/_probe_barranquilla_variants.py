# -*- coding: utf-8 -*-
"""Control de red + variantes adicionales del geoportal. Solo lectura."""
from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "estimation" / "raw" / "_probe"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

CONTROLES = [
    ("control_example", "https://example.com/"),
    ("control_arcgis_com", "https://www.arcgis.com/sharing/rest?f=json"),
    ("control_ideam", "https://www.ideam.gov.co/"),
    ("control_datosegovco", "https://www.datos.gov.co/api/views?limit=1"),
]

VARIANTES = [
    ("geo_http", "http://miciudad.barranquilla.gov.co/gis/rest/services?f=json"),
    ("geo_trailing", "https://miciudad.barranquilla.gov.co/gis/rest/services/?f=json"),
    ("geo_observatorio", "https://miciudad.barranquilla.gov.co/gis/rest/services/observatorio/MapServer?f=json"),
    ("geo_observatorio_layer", "https://miciudad.barranquilla.gov.co/gis/rest/services/observatorio/MapServer/0?f=json"),
    ("geo_root", "https://miciudad.barranquilla.gov.co/"),
    ("geo_slash_gis", "https://miciudad.barranquilla.gov.co/gis/"),
    ("geo_rest_info", "https://miciudad.barranquilla.gov.co/gis/rest/info?f=json"),
    ("geo_generateToken", "https://miciudad.barranquilla.gov.co/gis/tokens?f=json"),
]


def fetch(url: str, timeout: int = 25, extra: dict | None = None) -> dict:
    headers = {"User-Agent": UA, "Accept": "application/json, text/plain, */*",
               "Accept-Language": "es-CO,es;q=0.9", "Referer": "https://miciudad.barranquilla.gov.co/"}
    headers.update(extra or {})
    req = urllib.request.Request(url, headers=headers)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            c = resp.read()
            return {"url": url, "http_status": resp.status, "bytes": len(c),
                    "sha256": hashlib.sha256(c).hexdigest(),
                    "ms": int((time.time() - t0) * 1000),
                    "server": resp.headers.get("server"),
                    "cf_ray": resp.headers.get("cf-ray"),
                    "body": c[:1200], "error": None}
    except urllib.error.HTTPError as exc:
        c = b""
        try:
            c = exc.read()
        except Exception:
            pass
        return {"url": url, "http_status": exc.code, "bytes": len(c),
                "sha256": hashlib.sha256(c).hexdigest(),
                "ms": int((time.time() - t0) * 1000),
                "server": (exc.headers or {}).get("server"),
                "cf_ray": (exc.headers or {}).get("cf-ray"),
                "body": c[:1200], "error": f"HTTPError {exc.code} {exc.reason}"}
    except Exception as exc:  # noqa: BLE001
        return {"url": url, "http_status": None, "bytes": 0, "sha256": None,
                "ms": int((time.time() - t0) * 1000), "server": None, "cf_ray": None,
                "body": b"", "error": f"{type(exc).__name__}: {exc}"}


def main() -> int:
    res = []
    print("=== CONTROLES DE RED (prueban que la red SI funciona) ===")
    for nombre, url in CONTROLES:
        r = fetch(url)
        r["nombre"] = nombre
        res.append(r)
        print(f"  {nombre:22s} [{r['http_status']}] {r['bytes']:>8} B  {r['ms']:>5} ms  "
              f"server={r['server']}  err={r['error']}")
    print()
    print("=== VARIANTES DEL GEOPORTAL (deteccion de la regla Cloudflare) ===")
    for nombre, url in VARIANTES:
        r = fetch(url)
        r["nombre"] = nombre
        res.append(r)
        marca = ""
        if r["body"]:
            t = r["body"].decode("utf-8", "replace")
            if "Just a moment" in t:
                marca = " <-- DESAFIO JS CLOUDFLARE"
            elif t.strip().startswith("{"):
                marca = " <-- JSON"
        print(f"  {nombre:22s} [{r['http_status']}] {r['bytes']:>8} B  {r['ms']:>5} ms  "
              f"cf-ray={r['cf_ray']}  err={r['error']}{marca}")

    # la variante con cabeceras de navegacion completas (Sec-Fetch / Upgrade-Insecure)
    print()
    print("=== VARIANTE CON CABECERAS NAVEGADOR COMPLETAS ===")
    r = fetch("https://miciudad.barranquilla.gov.co/gis/rest/services?f=json", extra={
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Sec-Fetch-Dest": "document", "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none", "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "Accept-Encoding": "identity",
        "Connection": "keep-alive",
    })
    r["nombre"] = "geo_navegacion_completa"
    res.append(r)
    print(f"  [{'?' if r['http_status'] is None else r['http_status']}] {r['bytes']} B "
          f"cf-ray={r['cf_ray']} err={r['error']}")

    (OUT / "probe_variantes.json").write_text(json.dumps(
        [{k: (v.decode("utf-8", "replace")[:400] if k == "body" else v) for k, v in r.items()}
         for r in res], ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

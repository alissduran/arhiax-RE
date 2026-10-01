# -*- coding: utf-8 -*-
"""Sonda de solo lectura del geoportal municipal de Barranquilla.

Recorre el arbol ArcGIS REST buscando las capas de mercado declaradas en la mision.
No escribe en el repo salvo el volcado de diagnostico en docs/estimation/raw/_probe/.
"""
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

BASES = [
    "https://miciudad.barranquilla.gov.co/gis/rest/services",
    "https://miciudad.barranquilla.gov.co/gis/rest/services?f=json",
    "https://miciudad.barranquilla.gov.co/arcgis/rest/services?f=json",
    "https://miciudad.barranquilla.gov.co/server/rest/services?f=json",
]

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

OBJETIVOS = ["observatorio", "valoresm2", "valorsuelo", "valorcompraventas",
             "arrendamiento", "avaluo", "cantidadtransacciones", "mercado", "valor"]


def fetch(url: str, timeout: int = 30) -> dict:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-CO,es;q=0.9,en;q=0.8",
    })
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            cuerpo = resp.read()
            return {"url": url, "http_status": resp.status, "bytes": len(cuerpo),
                    "sha256": hashlib.sha256(cuerpo).hexdigest(),
                    "ms": int((time.time() - t0) * 1000),
                    "headers": {k.lower(): v for k, v in resp.headers.items()},
                    "body": cuerpo, "error": None}
    except urllib.error.HTTPError as exc:
        cuerpo = b""
        try:
            cuerpo = exc.read()
        except Exception:
            pass
        return {"url": url, "http_status": exc.code, "bytes": len(cuerpo),
                "sha256": hashlib.sha256(cuerpo).hexdigest(),
                "ms": int((time.time() - t0) * 1000),
                "headers": {k.lower(): v for k, v in (exc.headers or {}).items()},
                "body": cuerpo, "error": f"HTTPError {exc.code} {exc.reason}"}
    except Exception as exc:  # noqa: BLE001
        return {"url": url, "http_status": None, "bytes": 0, "sha256": None,
                "ms": int((time.time() - t0) * 1000), "headers": {},
                "body": b"", "error": f"{type(exc).__name__}: {exc}"}


def main() -> int:
    informe = []
    for base in BASES:
        r = fetch(base)
        info = {k: v for k, v in r.items() if k != "body"}
        info["headers_subset"] = {k: v for k, v in r["headers"].items()
                                  if k in ("server", "cf-ray", "date", "content-type",
                                           "cf-cache-status", "set-cookie")}
        informe.append(info)
        print(f"[{r['http_status']}] {base} · {r['bytes']} B · {r['ms']} ms · "
              f"err={r['error']} · server={r['headers'].get('server')} · "
              f"cf-ray={r['headers'].get('cf-ray')}")
        if r["body"]:
            txt = r["body"][:400].decode("utf-8", "replace")
            print("      body[:400] =", txt.replace("\n", " ")[:400])
        # volcado
        nombre = base.replace("https://", "").replace("/", "_").replace("?", "_")
        (OUT / f"{nombre}.txt").write_bytes(r["body"][:200000])
    (OUT / "probe_bases.json").write_text(
        json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())

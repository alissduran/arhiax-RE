"""Probe: which header combination gets past the edge for the known catastro endpoints."""
from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

URLS = [
    "https://miciudad.barranquilla.gov.co/gis/rest/services/catastro/datosabiertos/MapServer?f=json",
    "https://miciudad.barranquilla.gov.co/gis/rest/services?f=json",
]

HEADER_SETS = {
    "ua_only": {"User-Agent": "Mozilla/5.0 ARHIAX-RE/1.0"},
    "browser_like": {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-CO,es;q=0.9,en;q=0.8",
        "Accept-Encoding": "identity",
        "Referer": "https://miciudad.barranquilla.gov.co/",
        "Origin": "https://miciudad.barranquilla.gov.co",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    },
    "python_default": {},
}

for url in URLS:
    for name, headers in HEADER_SETS.items():
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=40, context=CTX) as r:
                body = r.read()
                print(f"[{r.status}] {name} :: {url}")
                print("     head:", body[:180].decode("utf-8", errors="replace").replace("\n", " "))
        except urllib.error.HTTPError as e:
            print(f"[HTTP {e.code}] {name} :: {url}")
        except Exception as e:  # noqa: BLE001
            print(f"[ERR {type(e).__name__}] {name} :: {url} -> {e}")

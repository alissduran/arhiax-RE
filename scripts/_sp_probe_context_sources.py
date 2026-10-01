# -*- coding: utf-8 -*-
"""Sonda de fuentes contextuales/contractuales: Overpass, credenciales, Lonja."""
from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
LAT, LON = 11.005378, -74.8386199
_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE
UA = "ARHIAX-RE-SourcePack/1.0 (+https://arhiax.local)"

OVERPASS = ["https://overpass-api.de/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter",
            "https://maps.mail.ru/osm/tools/overpass/api/interpreter"]

Q = f"""[out:json][timeout:25];
(
  nwr(around:1500,{LAT},{LON})["amenity"~"school|hospital|clinic|pharmacy|bank|restaurant|place_of_worship"];
  nwr(around:1500,{LAT},{LON})["shop"~"supermarket|mall"];
);
out center 30;"""


def main() -> int:
    print("== OVERPASS ==")
    for url in OVERPASS:
        try:
            data = urllib.parse.urlencode({"data": Q}).encode()
            req = urllib.request.Request(url, data=data, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=40, context=_CTX) as r:
                body = json.loads(r.read().decode("utf-8", "replace"))
            els = body.get("elements") or []
            print(f"  OK {url} -> {len(els)} elementos")
            cats = {}
            for e in els:
                t = (e.get("tags") or {})
                k = t.get("amenity") or t.get("shop") or "otro"
                cats[k] = cats.get(k, 0) + 1
            print("   categorías:", json.dumps(dict(sorted(cats.items(), key=lambda x: -x[1])),
                                               ensure_ascii=False))
            break
        except urllib.error.HTTPError as exc:
            print(f"  HTTP {exc.code} {url}")
        except Exception as exc:  # noqa: BLE001
            print(f"  {type(exc).__name__}: {str(exc)[:90]} {url}")

    print("== CREDENCIALES ==")
    nombres = ["MAPILLARY_TOKEN", "MAPILLARY_ACCESS_TOKEN", "MAPILLARY_CLIENT_ID",
               "GOOGLE_MAPS_API_KEY", "GOOGLE_API_KEY", "GOOGLE_STREETVIEW_API_KEY",
               "STREET_VIEW_API_KEY", "PHOTON", "OSM_TOKEN"]
    for n in nombres:
        v = os.environ.get(n)
        print(f"  {n}: {'PRESENTE' if v else 'AUSENTE'}")
    env_files = [RAIZ / ".env", RAIZ / "api" / ".env", RAIZ / "public" / ".env"]
    for f in env_files:
        print(f"  {f.relative_to(RAIZ)}: {'existe' if f.exists() else 'no existe'}")
    cred = RAIZ / "api" / "street_imagery.py"
    print(f"  street_imagery.py: {'existe' if cred.exists() else 'no existe'}")

    print("== LONJA ==")
    yml = (RAIZ / "motor_tma_lonja_baq_v1.0" / "motor_tma_lonja_baq_v1.0" / "lonja_layer"
           / "lonja_baq_metodologia.yaml")
    print(f"  yaml: {yml} -> {'existe' if yml.exists() else 'NO EXISTE'}")
    if yml.exists():
        texto = yml.read_text(encoding="utf-8", errors="replace")
        print("  bytes:", len(texto))
        print("  primeras líneas:")
        for l in texto.splitlines()[:25]:
            print("   ", l)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

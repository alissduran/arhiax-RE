# -*- coding: utf-8 -*-
"""Captura cruda REAL de Overpass para el predio Golden (no sobrescribe nada).

Escribe `docs/source_pack/raw/golden/osm_overpass.json` solo si NO existe; si existe,
informa y no lo toca. La consulta es la misma que usa el Source Pack.
"""
from __future__ import annotations

import json
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DEST = RAIZ / "docs" / "source_pack" / "raw" / "golden" / "osm_overpass.json"
LAT, LON = 11.006055954316363, -74.8375696549899
_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE
UA = "ARHIAX-RE/1.0 (Sinergia Consulting Group; Source Pack v1.0)"
ESPEJOS = ["https://overpass-api.de/api/interpreter",
           "https://overpass.kumi.systems/api/interpreter",
           "https://maps.mail.ru/osm/tools/overpass/api/interpreter"]
Q = (f"[out:json][timeout:25];\n(\n"
     f'  nwr(around:1500,{LAT},{LON})["amenity"~'
     f'"school|hospital|clinic|pharmacy|bank|restaurant|place_of_worship"];\n'
     f'  nwr(around:1500,{LAT},{LON})["shop"~"supermarket|mall"];\n);\nout center 30;')


def main() -> int:
    if DEST.exists():
        print(f"YA EXISTE (no se sobrescribe): {DEST}")
        return 0
    intentos = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    for ronda in range(intentos):
        for url in ESPEJOS:
            try:
                req = urllib.request.Request(url,
                                             data=urllib.parse.urlencode({"data": Q}).encode(),
                                             headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=90, context=_CTX) as r:
                    data = json.loads(r.read().decode("utf-8", "replace"))
            except Exception as exc:  # noqa: BLE001
                print(f"  ronda {ronda + 1} fallo {url.split('/')[2]}: "
                      f"{type(exc).__name__}: {str(exc)[:70]}", flush=True)
                continue
            if not (data.get("elements") or []):
                print(f"  ronda {ronda + 1} {url.split('/')[2]}: respuesta sin elementos")
                continue
            captura = {
                "_capture": {
                    "source_id": "OSM_OVERPASS",
                    "endpoint": url,
                    "queried_at": datetime.now(timezone.utc).isoformat(),
                    "query": Q,
                    "point": {"lat": LAT, "lon": LON, "radio_m": 1500},
                    "note": ("Respuesta CRUDA de Overpass tal como llegó; no se modifica. Se "
                             "usa como fallback DECLARADO cuando la red no está disponible."),
                    "elements": len(data.get("elements") or []),
                },
                "response": data,
            }
            DEST.write_text(json.dumps(captura, ensure_ascii=False, indent=1),
                            encoding="utf-8")
            print(f"escrito {DEST} ({DEST.stat().st_size} bytes, "
                  f"{captura['_capture']['elements']} elementos)")
            return 0
    print("ningún espejo respondió en los intentos dados: no se escribe captura")
    return 1


if __name__ == "__main__":
    sys.exit(main())

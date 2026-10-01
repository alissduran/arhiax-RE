"""Capture the catastro/datosabiertos FeatureServer TABLES (500 Predio, 505, 545)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _fetch  # noqa: E402
from _fetch import fetch  # noqa: E402

_fetch.MIN_GAP = 0.25
ORDER = ["allorigins"] * 6 + ["codetabs", "cors_eu_org"]
FS = "https://miciudad.barranquilla.gov.co/gis/rest/services/catastro/datosabiertos/FeatureServer"

for lid in [int(x) for x in sys.argv[1:]] or [500, 505, 545]:
    a = fetch(f"{FS}/{lid}?f=json", budget=34, timeout=25, order=ORDER)
    d = a["data"] if a["ok"] else None
    if isinstance(d, dict) and isinstance(d.get("error"), dict):
        print(f"  {lid:>4} METADATA ARCGIS ERROR {json.dumps(d['error'])[:140]}", flush=True)
    elif isinstance(d, dict):
        print(f"  {lid:>4} {d.get('name')!r} type={d.get('type')} fields={len(d.get('fields') or [])}",
              flush=True)
    else:
        print(f"  {lid:>4} METADATA UNAVAILABLE (no transport delivered JSON)", flush=True)
    b = fetch(f"{FS}/{lid}/query?where=1=1&resultRecordCount=1&outFields=*&f=json",
              budget=34, timeout=25, order=ORDER)
    s = b["data"] if b["ok"] else None
    if isinstance(s, dict) and isinstance(s.get("error"), dict):
        print(f"       sample ARCGIS ERROR {json.dumps(s['error'])[:140]}", flush=True)
    elif isinstance(s, dict):
        print(f"       sample features={len(s.get('features') or [])}", flush=True)
    else:
        print("       sample UNAVAILABLE", flush=True)
print("done")

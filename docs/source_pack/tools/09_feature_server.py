"""Capture catastro/datosabiertos/FeatureServer layer metadata (MapServer is currently stopped)."""
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
IDS = [105, 110, 205, 305, 310, 315, 320, 500, 505, 545]

for lid in IDS:
    a = fetch(f"{FS}/{lid}?f=json", budget=30, timeout=25, order=ORDER)
    b = fetch(f"{FS}/{lid}/query?where=1=1&resultRecordCount=1&outFields=*&f=json",
              budget=30, timeout=25, order=ORDER)
    d = a["data"] if a["ok"] else None
    if isinstance(d, dict) and d.get("error"):
        print(f"  {lid:>4} METADATA ERROR {json.dumps(d['error'])[:120]}", flush=True)
    else:
        print(f"  {lid:>4} {d.get('name')!r} geom={d.get('geometryType')} "
              f"fields={len(d.get('fields') or [])}", flush=True)
    sb = b["data"] if b["ok"] else None
    if isinstance(sb, dict) and sb.get("error"):
        print(f"       sample ERROR {json.dumps(sb['error'])[:120]}", flush=True)
    elif isinstance(sb, dict):
        feats = sb.get("features") or []
        print(f"       sample features={len(feats)}", flush=True)
print("done")

"""STEP 2e — Focused capture of the REAL layers that serve the requested business concepts.

The business ids requested (0/3/4/100/105/83/85/87/89/91/92/18-27/71-81) do not exist in this
service; the real equivalents do. For each one this captures the layer metadata (full field list)
and one real sample row.
"""
from __future__ import annotations

import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _fetch  # noqa: E402
from _fetch import fetch  # noqa: E402

_fetch.MIN_GAP = 0.25
ORDER = ["allorigins"] * 6 + ["codetabs", "cors_eu_org"]

CAT = "https://miciudad.barranquilla.gov.co/gis/rest/services/catastro/datosabiertos/MapServer"
UNI = "https://miciudad.barranquilla.gov.co/gis/rest/services/ordenamiento/unidadesadministrativas/MapServer"
PLA = "https://miciudad.barranquilla.gov.co/gis/rest/services/ordenamiento/planeacion/MapServer"
AME = "https://miciudad.barranquilla.gov.co/gis/rest/services/riesgos/amenazas/MapServer"
EST = "https://miciudad.barranquilla.gov.co/gis/rest/services/ordenamiento/estratificacion/MapServer"
DIR = "https://miciudad.barranquilla.gov.co/gis/rest/services/ordenamiento/direcciones/MapServer"

TARGETS = [
    (CAT, 315), (CAT, 310), (CAT, 500), (CAT, 105), (CAT, 320), (CAT, 305), (CAT, 505), (CAT, 545),
    (UNI, 1), (UNI, 3), (UNI, 2), (UNI, 4),
    (PLA, 1), (PLA, 2), (PLA, 3), (PLA, 4), (PLA, 5),
    (AME, 1), (AME, 2),
    (EST, 1), (DIR, 1),
]

lock = threading.Lock()
state = {"ok": 0, "miss": 0}


def work(item):
    svc, lid = item
    a = fetch(f"{svc}/{lid}?f=json", budget=30, timeout=25, order=ORDER)
    b = fetch(f"{svc}/{lid}/query?where=1=1&resultRecordCount=1&outFields=*&f=json",
              budget=30, timeout=25, order=ORDER)
    with lock:
        state["ok" if a["ok"] else "miss"] += 1
        name = (a["data"] or {}).get("name") if a["ok"] else None
        print(f"  {'OK ' if a['ok'] else 'MISS'} {svc.split('/services/')[1]}/{lid} "
              f"{name!r} sample={'yes' if b['ok'] else 'no'}", flush=True)
    return {"service_url": svc, "layer_id": lid}


with ThreadPoolExecutor(max_workers=6) as ex:
    list(ex.map(work, TARGETS))

out = Path(__file__).resolve().parents[1] / "raw" / "golden" / "_critical_layers_run.json"
out.write_text(json.dumps(state, indent=2), encoding="utf-8")
print(f"\ndone: ok={state['ok']} miss={state['miss']}")

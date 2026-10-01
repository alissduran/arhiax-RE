"""STEP 2f — Capture the REAL equipment layers (metadata + one sample row each)."""
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
B = "https://miciudad.barranquilla.gov.co/gis/rest/services"

TARGETS = [
    (f"{B}/espaciopublico/infraestructuraespaciopublico/MapServer", 4),
    (f"{B}/espaciopublico/infraestructuraespaciopublico/MapServer", 3),
    (f"{B}/espaciopublico/infraestructuraespaciopublico/MapServer", 2),
    (f"{B}/educacion/infraestructuraeducativa/MapServer", 1),
    (f"{B}/educacion/infraestructuraeducativa/MapServer", 2),
    (f"{B}/salud/infraestructurasalud/MapServer", 1),
    (f"{B}/salud/infraestructurasalud/MapServer", 2),
    (f"{B}/recreacionydeporte/infraestructuradeporte/MapServer", 1),
    (f"{B}/recreacionydeporte/infraestructuradeporte/MapServer", 2),
    (f"{B}/sitios/sitiosdeinteres/MapServer", 2),
]

lock = threading.Lock()
state = {"ok": 0, "miss": 0}


def work(item):
    svc, lid = item
    a = fetch(f"{svc}/{lid}?f=json", budget=30, timeout=25, order=ORDER)
    b = fetch(f"{svc}/{lid}/query?where=1=1&resultRecordCount=1&outFields=*&f=json",
              budget=30, timeout=25, order=ORDER)
    with lock:
        d = a["data"] if a["ok"] else None
        err = isinstance(d, dict) and isinstance(d.get("error"), dict)
        state["miss" if (d is None or err) else "ok"] += 1
        nm = d.get("name") if isinstance(d, dict) and not err else None
        print(f"  {'OK ' if (d and not err) else 'MISS'} {svc.split('/services/')[1]}/{lid} "
              f"{nm!r} fields={len(d.get('fields') or []) if isinstance(d, dict) and not err else 0} "
              f"sample={'yes' if (b['ok'] and not (isinstance(b['data'], dict) and isinstance(b['data'].get('error'), dict))) else 'no'}",
              flush=True)


with ThreadPoolExecutor(max_workers=6) as ex:
    list(ex.map(work, TARGETS))

out = Path(__file__).resolve().parents[1] / "raw" / "golden" / "_equipment_layers_run.json"
out.write_text(json.dumps(state, indent=2), encoding="utf-8")
print(f"\ndone: ok={state['ok']} miss={state['miss']}")

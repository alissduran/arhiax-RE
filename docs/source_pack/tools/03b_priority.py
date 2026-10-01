"""STEP 2b — Priority fetch of the highest-value endpoints, independent of the full tree sweep.

Guarantees the critical artifacts (catastro layer/table index, POT + risk folders) even if the
long sweep is interrupted.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _fetch import fetch  # noqa: E402

BASE = "https://miciudad.barranquilla.gov.co/gis/rest/services"
GOLD = Path(__file__).resolve().parents[1] / "raw" / "golden"

PRIORITY = [
    f"{BASE}/catastro/datosabiertos/MapServer?f=json",
    f"{BASE}/catastro/datosabiertos/FeatureServer?f=json",
    f"{BASE}/ordenamiento?f=json",
    f"{BASE}/riesgos?f=json",
    f"{BASE}/ambiente?f=json",
    f"{BASE}/cultura?f=json",
    f"{BASE}/educacion?f=json",
]

results = []
for url in PRIORITY:
    r = fetch(url, budget=18)
    entry = {"url": url, "ok": r["ok"], "provenance": r["provenance"]}
    if r["ok"]:
        d = r["data"]
        if "layers" in d:
            entry["layers"] = [(l.get("id"), l.get("name")) for l in (d.get("layers") or [])]
            entry["tables"] = [(t.get("id"), t.get("name")) for t in (d.get("tables") or [])]
            entry["maxRecordCount"] = d.get("maxRecordCount")
            entry["capabilities"] = d.get("capabilities")
            print(f"OK  SERVICE {url}\n    layers({len(entry['layers'])}): {entry['layers']}\n"
                  f"    tables({len(entry['tables'])}): {entry['tables']}")
        else:
            entry["folders"] = d.get("folders")
            entry["services"] = [s.get("name") for s in (d.get("services") or [])]
            print(f"OK  FOLDER  {url}\n    subfolders={entry['folders']}\n    services={entry['services']}")
    else:
        print(f"FAIL {url} -> {json.dumps(r['provenance'].get('attempts'))[:300]}")
    results.append(entry)

(GOLD / "_priority_fetch.json").write_text(json.dumps(results, indent=2, ensure_ascii=False),
                                           encoding="utf-8")
print("\nwrote _priority_fetch.json")

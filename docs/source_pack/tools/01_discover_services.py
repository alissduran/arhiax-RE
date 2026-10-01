"""Discover the full ArcGIS REST service tree at miciudad.barranquilla.gov.co/gis/rest/services."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _http import BASE, dump, get_json  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "raw" / "golden"
TREE = {"root": BASE, "folders": {}, "services": []}
ERRORS = []


def walk(url: str, label: str, depth: int = 0) -> None:
    if depth > 4:
        return
    data = get_json(url, {"f": "json"})
    tr = data.pop("_transport", {})
    if not tr.get("ok"):
        ERRORS.append({"url": url, "label": label, "transport": tr})
        print(f"[FAIL] {label} -> {tr}")
        return
    folders = data.get("folders", []) or []
    services = data.get("services", []) or []
    print(f"[OK] {label}: {len(folders)} folders, {len(services)} services")
    for s in services:
        entry = {"folder_label": label, **s}
        TREE["services"].append(entry)
        print(f"    svc: {s.get('name')} ({s.get('type')})")
    for f in folders:
        child_label = f if label == "(root)" else f"{label}/{f}"
        walk(f"{BASE}/{f}", child_label, depth + 1)


walk(BASE, "(root)")

dump(OUT / "_service_tree.json", {"tree": TREE, "errors": ERRORS})
print(f"\nTOTAL services: {len(TREE['services'])}  errors: {len(ERRORS)}")

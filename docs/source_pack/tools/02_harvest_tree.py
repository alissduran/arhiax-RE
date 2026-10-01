"""STEP 1 — Enumerate the whole ArcGIS REST service tree at miciudad.barranquilla.gov.co/gis/rest/services."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _fetch import fetch_json  # noqa: E402

BASE = "https://miciudad.barranquilla.gov.co/gis/rest/services"
OUT = Path(__file__).resolve().parents[1] / "raw" / "golden"

tree = {"root_url": BASE, "nodes": [], "services": [], "errors": []}
seen = set()


def walk(url: str, label: str, depth: int = 0) -> None:
    if depth > 4 or url in seen:
        return
    seen.add(url)
    r = fetch_json(f"{url}?f=json")
    if r["data"] is None or not isinstance(r["data"], dict):
        tree["errors"].append({"url": url, "label": label, "provenance": r["provenance"]})
        print(f"[FAIL] {label} :: {json.dumps(r['provenance'].get('attempts'))[:200]}")
        return
    data = r["data"]
    folders = data.get("folders") or []
    services = data.get("services") or []
    tree["nodes"].append({"label": label, "url": url, "currentVersion": data.get("currentVersion"),
                          "folders": folders, "service_count": len(services),
                          "provenance": r["provenance"]})
    print(f"[OK] {label:34s} v={data.get('currentVersion')} folders={len(folders)} services={len(services)}")
    for s in services:
        tree["services"].append({"folder_label": label, **s})
    for f in folders:
        child = f if label == "(root)" else f"{label}/{f}"
        walk(f"{BASE}/{f}", child, depth + 1)


walk(BASE, "(root)")

dump_path = OUT / "_service_tree.json"
dump_path.write_text(json.dumps(tree, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\nservices={len(tree['services'])} nodes={len(tree['nodes'])} errors={len(tree['errors'])}")
print(f"wrote {dump_path}")

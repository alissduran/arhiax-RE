"""Report what the raw cache already contains, without touching the network."""
from __future__ import annotations

import json
import sys
from pathlib import Path

CACHE = Path(__file__).resolve().parents[1] / "raw" / "golden" / "_raw_cache"

rows = []
for f in sorted(CACHE.glob("*.json")):
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        rows.append({"file": f.name, "error": f"{type(e).__name__}: {e}"})
        continue
    prov = d.get("provenance") or {}
    url = prov.get("requested_url", "?")
    row = {"url": url, "ok": bool(d.get("ok")), "transport": prov.get("transport"),
           "attempts": prov.get("attempt_count")}
    data = d.get("data")
    if isinstance(data, dict):
        if "layers" in data:
            row["kind"] = "service_root"
            row["layers"] = [(l.get("id"), l.get("name")) for l in (data.get("layers") or [])]
            row["tables"] = [(t.get("id"), t.get("name")) for t in (data.get("tables") or [])]
        elif "fields" in data:
            row["kind"] = "layer"
            row["layer_name"] = data.get("name")
            row["geometryType"] = data.get("geometryType")
            row["n_fields"] = len(data.get("fields") or [])
        elif "features" in data:
            row["kind"] = "query"
            row["n_features"] = len(data.get("features") or [])
            feats = data.get("features") or []
            if feats:
                row["sample_attrs"] = list((feats[0].get("attributes") or {}).keys())[:40]
        elif "folders" in data or "currentVersion" in data:
            row["kind"] = "tree_node"
            row["folders"] = data.get("folders")
            row["services"] = [s.get("name") for s in (data.get("services") or [])]
        elif "error" in data:
            row["kind"] = "arcgis_error"
            row["error"] = str(data.get("error"))[:200]
        else:
            row["kind"] = "other:" + ",".join(list(data.keys())[:8])
    rows.append(row)

print(f"cache entries: {len(rows)}")
failed = [r for r in rows if not r.get("ok")]
print(f"FAILED entries: {len(failed)}")
for r in failed:
    print(f"  FAIL {r['url']}\n       attempts={r.get('attempts')}")
for r in rows:
    if r.get("kind") == "service_root":
        print(f"\nSERVICE {r['url']}\n   layers={r.get('layers')}\n   tables={r.get('tables')}")
    elif r.get("kind") in ("layer", "query", "arcgis_error"):
        print(f"{r.get('kind'):14s} {r['url']}\n   {json.dumps({k: v for k, v in r.items() if k not in ('url','kind')}, ensure_ascii=False)[:260]}")
    elif r.get("kind") == "tree_node":
        print(f"TREE {r['url']} folders={r.get('folders')} services={r.get('services')}")

out = Path(__file__).resolve().parents[1] / "raw" / "golden" / "_cache_report.json"
out.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\nwrote {out}")

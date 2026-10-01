"""Summarise ArcGIS error responses across the raw cache, grouped by error code and service."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

CACHE = Path(__file__).resolve().parents[1] / "raw" / "golden" / "_raw_cache"

by_code = Counter()
rows = []
for f in sorted(CACHE.glob("*.json")):
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        continue
    data = d.get("data")
    if not isinstance(data, dict):
        continue
    err = data.get("error")
    if isinstance(err, dict):
        url = (d.get("provenance") or {}).get("requested_url", "")
        by_code[err.get("code")] += 1
        rows.append({"url": url, "code": err.get("code"), "message": err.get("message")})

print("ArcGIS error responses by code:")
for code, n in sorted(by_code.items(), key=lambda t: -t[1]):
    print(f"  code {code}: {n}")

print("\nBy message:")
msgs = Counter(r["message"] for r in rows)
for m, n in msgs.most_common():
    print(f"  {n:3d}  {m}")

print("\nServices returning 'not started':")
svc = defaultdict(int)
for r in rows:
    if "not started" in str(r["message"]):
        svc[r["url"].split("/services/")[1].rsplit("/", 2)[0]] += 1
for s, n in sorted(svc.items()):
    print(f"  {n:3d}  {s}")

out = Path(__file__).resolve().parents[1] / "raw" / "golden" / "_arcgis_errors.json"
out.write_text(json.dumps({"by_code": dict(by_code), "rows": rows}, indent=2, ensure_ascii=False),
               encoding="utf-8")
print(f"\nwrote {out} ({len(rows)} error responses)")

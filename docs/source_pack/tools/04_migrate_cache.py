"""STEP 0b — Purge cache entries that were accepted by the buggy validator.

The first harvest accepted api.allorigins.win's own Cloudflare 522 JSON envelope as if it were
ArcGIS data (it parses as JSON and carries HTTP 200). Those entries are NOT evidence and must
never reach the Source Pack. Valid entries are kept so the harvest does not repeat work; the
rejected ones are moved to _raw_cache_invalidated/ for audit.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _fetch import CACHE, _looks_like_arcgis  # noqa: E402

INVALID = CACHE.parent / "_raw_cache_invalidated"
INVALID.mkdir(parents=True, exist_ok=True)

kept, moved = 0, 0
moved_urls = []
for f in sorted(CACHE.glob("*.json")):
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        shutil.move(str(f), str(INVALID / f.name))
        moved += 1
        continue
    if d.get("ok") and not _looks_like_arcgis(d.get("data")):
        moved_urls.append({"file": f.name,
                           "url": (d.get("provenance") or {}).get("requested_url"),
                           "why": "accepted earlier by the buggy validator; body is a proxy error envelope",
                           "data_head": json.dumps(d.get("data"))[:200]})
        shutil.move(str(f), str(INVALID / f.name))
        moved += 1
    else:
        kept += 1

(INVALID / "_moved_index.json").write_text(
    json.dumps(moved_urls, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"kept valid: {kept}   moved invalid: {moved}")
print(f"invalid archive: {INVALID}")

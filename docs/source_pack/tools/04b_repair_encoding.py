"""Repair pass: drop cache entries whose text was decoded with lossy replacement.

Those bodies contain U+FFFD, which means the decode mangled real accented characters
("Direccion" -> "Direcci<?>" for the official layer names). Deleting them makes the harvester
refetch and decode them properly.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _fetch import CACHE  # noqa: E402

QUARANTINE = CACHE.parent / "_raw_cache_lossy_decode"
QUARANTINE.mkdir(parents=True, exist_ok=True)

dropped = []
for f in sorted(CACHE.glob("*.json")):
    try:
        raw = f.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        continue
    if "\ufffd" in raw:
        try:
            url = (json.loads(raw).get("provenance") or {}).get("requested_url")
        except Exception:  # noqa: BLE001
            url = None
        dropped.append({"file": f.name, "url": url})
        shutil.move(str(f), str(QUARANTINE / f.name))

(QUARANTINE / "_dropped_index.json").write_text(
    json.dumps(dropped, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"dropped {len(dropped)} lossy-decoded entries for refetch:")
for d in dropped:
    print(f"  {d['url']}")

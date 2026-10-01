"""Print the layer/table index of a cached service root (id, name, geometry-bearing flag)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

CACHE = Path(__file__).resolve().parents[1] / "raw" / "golden" / "_raw_cache"

for pattern in sys.argv[1:] or ["*catastro-datosabiertos-MapServer.json"]:
    for f in sorted(CACHE.glob(pattern)):
        d = json.loads(f.read_text(encoding="utf-8"))
        prov = d.get("provenance") or {}
        print(f"\n=== {f.name}\n    url={prov.get('requested_url')}\n    ok={d.get('ok')} "
              f"transport={prov.get('transport')} http={prov.get('http_status')}")
        data = d.get("data")
        if not isinstance(data, dict):
            continue
        if "layers" in data or "tables" in data:
            print(f"    currentVersion={data.get('currentVersion')} "
                  f"maxRecordCount={data.get('maxRecordCount')} "
                  f"capabilities={data.get('capabilities')}")
            print(f"    spatialReference={data.get('spatialReference') or data.get('initialExtent', {}).get('spatialReference')}")
            print(f"    --- layers ({len(data.get('layers') or [])}) ---")
            for l in data.get("layers") or []:
                print(f"      {l.get('id'):>5} {l.get('name')!r} parent={l.get('parentLayerId')} "
                      f"sub={l.get('subLayerIds')}")
            print(f"    --- tables ({len(data.get('tables') or [])}) ---")
            for t in data.get("tables") or []:
                print(f"      {t.get('id'):>5} {t.get('name')!r}")
        elif "fields" in data:
            print(f"    LAYER {data.get('id')} {data.get('name')!r} geom={data.get('geometryType')} "
                  f"type={data.get('type')}")
            for fl in data.get("fields") or []:
                print(f"      {fl.get('name'):40s} {fl.get('type'):20s} alias={fl.get('alias')!r}")
        elif "features" in data:
            feats = data.get("features") or []
            print(f"    QUERY features={len(feats)}")
            if feats:
                print(f"      attrs={json.dumps(feats[0].get('attributes'), ensure_ascii=False)[:600]}")
        elif "folders" in data or "services" in data:
            print(f"    folders={data.get('folders')}")
            print(f"    services={[s.get('name') for s in (data.get('services') or [])]}")
        else:
            print(f"    keys={list(data.keys())}")

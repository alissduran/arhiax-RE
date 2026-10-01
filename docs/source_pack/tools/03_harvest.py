"""STEP 1/2 — Harvest the ArcGIS tree and the root metadata of every candidate service.

Writes:
  raw/golden/_tree.json     full folder/service tree with provenance per node
  raw/golden/_services.json root metadata of every service whose root could be read
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _fetch import fetch  # noqa: E402

BASE = "https://miciudad.barranquilla.gov.co/gis/rest/services"
OUT = Path(__file__).resolve().parents[1] / "raw" / "golden"

# keyword rank: higher = fetched first when the service budget is limited
KEYWORD_RANK = [
    ("ordenamiento", 100), ("catastro", 95), ("riesgo", 90), ("amenaza", 88),
    ("equipamiento", 85), ("planeacion", 80), ("estratificacion", 78),
    ("unidadesadministrativas", 76), ("uso", 60), ("tratamiento", 58),
    ("edificabilidad", 56), ("pot", 54), ("suelo", 52), ("remocion", 50),
    ("inundacion", 48), ("geolog", 46), ("movilidad", 30), ("observatorio", 25),
]


def rank(service_name: str, folder: str) -> int:
    hay = f"{folder}/{service_name}".lower()
    return max([w for kw, w in KEYWORD_RANK if kw in hay] or [10])


def main() -> None:
    tree = {"root_url": BASE, "root_provenance": None, "folders": [], "services": [], "errors": []}

    root = fetch(f"{BASE}?f=json")
    tree["root_provenance"] = root["provenance"]
    if not root["ok"]:
        OUT.joinpath("_tree.json").write_text(json.dumps(tree, indent=2, ensure_ascii=False), encoding="utf-8")
        print("FATAL: cannot read services root")
        print(json.dumps(root["provenance"].get("attempts"), indent=2)[:800])
        return
    rd = root["data"]
    tree["currentVersion"] = rd.get("currentVersion")
    tree["root_folders_raw"] = rd.get("folders")
    tree["root_services_raw"] = rd.get("services")
    folders = list(rd.get("folders") or [])
    for s in rd.get("services") or []:
        tree["services"].append({"folder": "(root)", **s})
    print(f"root: currentVersion={rd.get('currentVersion')} folders={len(folders)} "
          f"root_services={len(rd.get('services') or [])}")
    print("folders:", folders)

    for f in folders:
        r = fetch(f"{BASE}/{f}?f=json")
        node = {"folder": f, "url": f"{BASE}/{f}", "ok": r["ok"], "provenance": r["provenance"]}
        if r["ok"]:
            node["subfolders"] = r["data"].get("folders") or []
            node["service_count"] = len(r["data"].get("services") or [])
            for s in r["data"].get("services") or []:
                tree["services"].append({"folder": f, **s})
            for sf in node["subfolders"]:
                r2 = fetch(f"{BASE}/{f}/{sf}?f=json")
                node.setdefault("subfolder_nodes", []).append(
                    {"subfolder": sf, "ok": r2["ok"], "provenance": r2["provenance"]})
                if r2["ok"]:
                    for s in r2["data"].get("services") or []:
                        tree["services"].append({"folder": f"{f}/{sf}", **s})
                    for sf2 in r2["data"].get("folders") or []:
                        r3 = fetch(f"{BASE}/{f}/{sf}/{sf2}?f=json")
                        node["subfolder_nodes"].append(
                            {"subfolder": f"{sf}/{sf2}", "ok": r3["ok"],
                             "provenance": r3["provenance"]})
                        if r3["ok"]:
                            for s in r3["data"].get("services") or []:
                                tree["services"].append({"folder": f"{f}/{sf}/{sf2}", **s})
        else:
            tree["errors"].append({"folder": f, "provenance": r["provenance"]})
        tree["folders"].append(node)
        print(f"  folder {f:32s} ok={r['ok']} services={node.get('service_count', 0)} "
              f"subfolders={node.get('subfolders', [])}")

    OUT.joinpath("_tree.json").write_text(json.dumps(tree, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nTOTAL services discovered: {len(tree['services'])}")
    for s in sorted(tree["services"], key=lambda x: -rank(x.get("name", ""), x.get("folder", ""))):
        print(f"   [{s.get('folder')}] {s.get('name')}  ({s.get('type')})  rank={rank(s.get('name',''), s.get('folder',''))}")

    # ---- fetch service roots (root metadata incl. layer/table index) ----
    services = []
    ordered = sorted(tree["services"], key=lambda x: -rank(x.get("name", ""), x.get("folder", "")))
    for i, s in enumerate(ordered):
        # ArcGIS folder listings already qualify the service name with its folder
        # (e.g. "catastro/datosabiertos"); root-level listings are bare names.
        fq = f"{BASE}/{s.get('name')}/{s.get('type')}"
        r = fetch(f"{fq}?f=json")
        entry = {"service_url": fq, "folder": s.get("folder"), "name": s.get("name"),
                 "type": s.get("type"), "ok": r["ok"], "provenance": r["provenance"]}
        if r["ok"]:
            d = r["data"]
            entry["service_name"] = d.get("serviceDescription") or d.get("mapName") or d.get("name")
            entry["description"] = (d.get("serviceDescription") or "")[:200]
            entry["spatialReference"] = d.get("spatialReference") or d.get("initialExtent", {}).get("spatialReference")
            entry["maxRecordCount"] = d.get("maxRecordCount")
            entry["capabilities"] = d.get("capabilities")
            entry["layers"] = [{"id": l.get("id"), "name": l.get("name"),
                                "subLayerIds": l.get("subLayerIds")} for l in (d.get("layers") or [])]
            entry["tables"] = [{"id": t.get("id"), "name": t.get("name")} for t in (d.get("tables") or [])]
            print(f"  svc {s.get('name'):38s} layers={len(entry['layers'])} tables={len(entry['tables'])}")
        else:
            print(f"  svc {s.get('name'):38s} FAILED")
        services.append(entry)

    OUT.joinpath("_services.json").write_text(json.dumps(services, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote _tree.json and _services.json ({len(services)} service roots)")


if __name__ == "__main__":
    main()

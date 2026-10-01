"""STEP 2c — Persistent adaptive harvester.

The public fetchers that can reach Barranquilla are only intermittently usable: they mostly
return Cloudflare 522 / rate-limit pages and deliver genuine ArcGIS JSON in short windows.
This script keeps re-deriving the still-missing, highest-value targets and retrying them round
after round until the deadline, so the harvest rides those windows instead of giving up after
one pass.

Priority tiers:
  0  catastro/datosabiertos MapServer+FeatureServer roots  (layer/table index)
  1  folders that failed in the sweep (ordenamiento, riesgos, ambiente, ...)
  2  service roots belonging to POT / riesgo / catastro domains
  3  every other discovered service root
  4  business layer metadata
  5  one real sample query per business layer
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _fetch import CACHE, _looks_like_arcgis, _slug, fetch  # noqa: E402

BASE = "https://miciudad.barranquilla.gov.co/gis/rest/services"
GOLD = Path(__file__).resolve().parents[1] / "raw" / "golden"

DEADLINE_MIN = float(sys.argv[1]) if len(sys.argv) > 1 else 50.0
ROUND_BUDGET = 3
ROUND_SLEEP = 4.0
BATCH = 16

CRITICAL_FOLDERS = ["ordenamiento", "riesgos", "ambiente", "cultura", "educacion",
                    "participacionciudadana", "recreacionydeporte", "sitios"]
POT_RISK_KEYS = ("ordenamiento", "riesgo", "amenaza", "planeacion", "estratificacion",
                 "unidadesadministrativas", "catastro", "suelo", "edificabilidad",
                 "tratamiento", "uso")

BUSINESS_IDS = [0, 3, 4, 100, 105, 91, 92, 85, 87, 83, 89, 73, 77, 81, 71, 75, 79,
                18, 20, 21, 22, 23, 24, 25, 26, 27]


def read_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    except Exception:  # noqa: BLE001
        return None


def cached_payload(url: str):
    d = read_json(CACHE / f"{_slug(url)}.json")
    if d and d.get("ok") and _looks_like_arcgis(d.get("data")):
        return d["data"]
    return None


def tier_for(url: str) -> int:
    if url in (f"{BASE}/catastro/datosabiertos/MapServer?f=json",
               f"{BASE}/catastro/datosabiertos/FeatureServer?f=json"):
        return 0
    if url in {f"{BASE}/{f}?f=json" for f in CRITICAL_FOLDERS}:
        return 1
    if "/query?where=" in url:
        return 5
    if url.replace("?f=json", "").rsplit("/", 1)[-1].isdigit():
        return 4
    if any(k in url.lower() for k in POT_RISK_KEYS):
        return 2
    return 3


def collect_known() -> set[str]:
    known: set[str] = set()
    for folder in CRITICAL_FOLDERS:
        known.add(f"{BASE}/{folder}?f=json")
    known.add(f"{BASE}/catastro/datosabiertos/MapServer?f=json")
    known.add(f"{BASE}/catastro/datosabiertos/FeatureServer?f=json")

    tree = read_json(GOLD / "_tree.json")
    if tree:
        for f in tree.get("folders") or []:
            known.add(f"{f['url']}?f=json")
        for s in tree.get("services") or []:
            known.add(f"{BASE}/{s['name']}/{s['type']}?f=json".replace("/(root)", ""))

    # folders whose listing became readable in this run reveal their services
    for folder in CRITICAL_FOLDERS:
        d = cached_payload(f"{BASE}/{folder}?f=json")
        if isinstance(d, dict):
            for s in d.get("services") or []:
                known.add(f"{BASE}/{s.get('name')}/{s.get('type')}?f=json")

    # service roots we already read reveal their layers/tables -> business layer endpoints
    for svc_url in [u for u in known if not u.endswith("query?where=1=1&resultRecordCount=1&outFields=*&f=json")]:
        base = svc_url.replace("?f=json", "")
        if base.count("/") < 7 or base.startswith(f"{BASE}/") is False:
            continue
        d = cached_payload(svc_url)
        if not isinstance(d, dict):
            continue
        ids = {l.get("id") for l in (d.get("layers") or [])} | {t.get("id") for t in (d.get("tables") or [])}
        for bid in BUSINESS_IDS:
            if bid in ids:
                known.add(f"{base}/{bid}?f=json")
                known.add(f"{base}/{bid}/query?where=1=1&resultRecordCount=1&outFields=*&f=json")
    return known


def main() -> None:
    start = time.time()
    t_end = start + DEADLINE_MIN * 60
    rounds = gained_total = 0
    known = collect_known()
    print(f"initial known targets: {len(known)}", flush=True)

    while time.time() < t_end:
        rounds += 1
        known = collect_known() | known
        queue = sorted((u for u in known if cached_payload(u) is None), key=tier_for)
        if not queue:
            print("ALL KNOWN TARGETS ACQUIRED", flush=True)
            break
        gained = 0
        for url in queue[:BATCH]:
            r = fetch(url, budget=ROUND_BUDGET)
            if r["ok"]:
                gained += 1
                gained_total += 1
                print(f"[r{rounds}] OK   ({r['provenance'].get('transport')}) {url}", flush=True)
            else:
                print(f"[r{rounds}] miss       {url}", flush=True)
        left = len([u for u in known if cached_payload(u) is None])
        print(f"--- round {rounds}: gained={gained} total={gained_total} left={left} "
              f"elapsed={int(time.time() - start)}s", flush=True)
        time.sleep(ROUND_SLEEP)

    state = {"rounds": rounds, "gained": gained_total,
             "elapsed_s": round(time.time() - start, 1),
             "targets": [{"url": u, "tier": tier_for(u), "ok": cached_payload(u) is not None}
                         for u in sorted(known, key=tier_for)]}
    (GOLD / "_persistent_state.json").write_text(json.dumps(state, indent=2, ensure_ascii=False),
                                                 encoding="utf-8")
    ok = sum(1 for t in state["targets"] if t["ok"])
    print(f"\nDONE rounds={rounds} acquired={ok}/{len(state['targets'])}")


if __name__ == "__main__":
    main()

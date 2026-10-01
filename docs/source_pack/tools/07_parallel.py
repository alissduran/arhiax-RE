"""STEP 2d — Parallel harvester.

Only one third-party fetcher (api.allorigins.win) can reach Barranquilla, and it succeeds in
short windows, in a single attempt, from whichever backend instance happens to be up. Serial
retries waste that window, so this harvester runs several workers concurrently against a shared
priority queue and gives almost every attempt to the transport that actually works.

It targets the REAL schema: every folder, every service root, and for every service root read,
every layer/table metadata endpoint plus one real sample query for business-relevant layers.
"""
from __future__ import annotations

import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _fetch  # noqa: E402
from _fetch import CACHE, _looks_like_arcgis, _slug, fetch  # noqa: E402

BASE = "https://miciudad.barranquilla.gov.co/gis/rest/services"
GOLD = Path(__file__).resolve().parents[1] / "raw" / "golden"

DEADLINE_MIN = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0
WORKERS = int(sys.argv[2]) if len(sys.argv) > 2 else 5

# every attempt that is not allorigins is (as of this session) a known dead end
_fetch.MIN_GAP = 0.25
TRANSPORT_ORDER = ["allorigins"] * 6 + ["codetabs", "cors_eu_org"]

CRITICAL_FOLDERS = ["ordenamiento", "riesgos", "ambiente", "cultura", "educacion",
                    "participacionciudadana", "recreacionydeporte", "sitios", "SERVICIOS"]
RELEVANT = ("ordenamiento", "riesgo", "amenaza", "catastro", "planeacion", "estratificacion",
            "unidadesadministrativas", "suelo", "equipamiento", "huella", "uso", "tratamiento",
            "edificabilidad", "recreacion", "espaciopublico", "salud", "educacion")
BUSINESS_NAME_HINTS = ("terreno", "construccion", "construcción", "predio", "direccion", "dirección",
                       "manzana", "barrio", "localidad", "estrato", "uso", "tratamiento",
                       "edificabilidad", "riesgo", "remocion", "remoción", "inundacion", "inundación",
                       "actividad", "equipamiento", "gerencia")

lock = threading.Lock()
stats = {"ok": 0, "miss": 0, "by_transport": {}}


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
    if url in {f"{BASE}/{cs}?f=json" for cs in CANDIDATE_SERVICES}:
        return 1
    if url in {f"{BASE}/{f}?f=json" for f in CRITICAL_FOLDERS}:
        return 1
    if "/query?where=" in url:
        return 6
    if url.replace("?f=json", "").rsplit("/", 1)[-1].isdigit():
        return 5
    if any(k in url.lower() for k in RELEVANT):
        return 2
    return 3


def is_business_layer(name: str) -> bool:
    n = (name or "").lower()
    return any(h in n for h in BUSINESS_NAME_HINTS)


# The ordenamiento folder listing itself never came through the proxy, so the service roots that
# the POT/risk business needs are probed directly as candidates. The ArcGIS server answers
# concretely for existing and non-existing services alike, so every candidate yields evidence.
CANDIDATE_SERVICES = [
    "ordenamiento/unidadesadministrativas/MapServer",
    "ordenamiento/estratificacion/MapServer",
    "ordenamiento/planeacion/MapServer",
    "ordenamiento/direcciones/MapServer",
    "ordenamiento/pot/MapServer",
    "ordenamiento/tratamientos/MapServer",
    "ordenamiento/edificabilidad/MapServer",
    "ordenamiento/areasdeactividad/MapServer",
    "ordenamiento/usodelsuelo/MapServer",
    "ordenamiento/riesgo/MapServer",
    "riesgos/amenazas/MapServer",
    "riesgos/riesgos/MapServer",
    "riesgos/influencia/MapServer",
    "riesgos/atencionemergencias/MapServer",
]


def collect_known() -> set[str]:
    known: set[str] = set()
    for f in CRITICAL_FOLDERS:
        known.add(f"{BASE}/{f}?f=json")
    known.add(f"{BASE}/catastro/datosabiertos/MapServer?f=json")
    known.add(f"{BASE}/catastro/datosabiertos/FeatureServer?f=json")
    for cs in CANDIDATE_SERVICES:
        known.add(f"{BASE}/{cs}?f=json")

    tree = read_json(GOLD / "_tree.json")
    if tree:
        for f in tree.get("folders") or []:
            known.add(f"{f['url']}?f=json")
        for s in tree.get("services") or []:
            known.add(f"{BASE}/{s['name']}/{s['type']}?f=json".replace("/(root)", ""))

    # service roots discovered through folder listings read in this run
    for folder in CRITICAL_FOLDERS:
        d = cached_payload(f"{BASE}/{folder}?f=json")
        if isinstance(d, dict):
            for s in d.get("services") or []:
                known.add(f"{BASE}/{s.get('name')}/{s.get('type')}?f=json")

    # for every service root we could read, enumerate every layer/table endpoint
    for svc in list(known):
        if not svc.endswith("?f=json") or svc.endswith("/query?f=json"):
            continue
        d = cached_payload(svc)
        if not isinstance(d, dict) or "layers" not in d and "tables" not in d:
            continue
        base = svc.replace("?f=json", "")
        for l in (d.get("layers") or []) + (d.get("tables") or []):
            lid = l.get("id")
            if lid is None:
                continue
            known.add(f"{base}/{lid}?f=json")
            if is_business_layer(l.get("name") or ""):
                known.add(f"{base}/{lid}/query?where=1=1&resultRecordCount=1&outFields=*&f=json")
    return known


def main() -> None:
    start = time.time()
    t_end = start + DEADLINE_MIN * 60
    known = collect_known()
    print(f"initial targets: {len(known)}  workers={WORKERS} deadline={DEADLINE_MIN}min", flush=True)

    round_no = 0
    while time.time() < t_end:
        round_no += 1
        known = collect_known() | known
        queue = sorted((u for u in known if cached_payload(u) is None), key=tier_for)
        if not queue:
            print("ALL KNOWN TARGETS ACQUIRED", flush=True)
            break
        batch = queue[:WORKERS * 12]

        def work(u: str):
            r = fetch(u, budget=26, timeout=25, order=TRANSPORT_ORDER)
            with lock:
                if r["ok"]:
                    stats["ok"] += 1
                    tr = r["provenance"].get("transport")
                    stats["by_transport"][tr] = stats["by_transport"].get(tr, 0) + 1
                    print(f"[r{round_no}] OK   ({tr}) {u}", flush=True)
                else:
                    stats["miss"] += 1
            return r["ok"]

        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            list(ex.map(work, batch))

        left = len([u for u in known if cached_payload(u) is None])
        print(f"--- round {round_no}: total_ok={stats['ok']} miss={stats['miss']} left={left} "
              f"elapsed={int(time.time() - start)}s transports={stats['by_transport']}", flush=True)
        if not queue:
            break

    state = {"rounds": round_no, "ok": stats["ok"], "miss": stats["miss"],
             "by_transport": stats["by_transport"],
             "elapsed_s": round(time.time() - start, 1),
             "targets": [{"url": u, "tier": tier_for(u), "ok": cached_payload(u) is not None}
                         for u in sorted(known, key=tier_for)]}
    (GOLD / "_parallel_state.json").write_text(json.dumps(state, indent=2, ensure_ascii=False),
                                               encoding="utf-8")
    ok = sum(1 for t in state["targets"] if t["ok"])
    print(f"\nDONE acquired={ok}/{len(state['targets'])}", flush=True)


if __name__ == "__main__":
    main()

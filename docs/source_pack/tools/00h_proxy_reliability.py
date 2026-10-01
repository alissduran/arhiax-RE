"""Measure the success rate of the allorigins egress pool for the Barranquilla ArcGIS endpoints."""
from __future__ import annotations

import json
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0 Safari/537.36"}

TARGET = "https://miciudad.barranquilla.gov.co/gis/rest/services?f=json"
ENC = urllib.parse.quote(TARGET, safe="")

VARIANTS = {
    "allorigins_raw": f"https://api.allorigins.win/raw?url={ENC}",
    "allorigins_get": f"https://api.allorigins.win/get?url={ENC}",
    "codetabs": f"https://api.codetabs.com/v1/proxy?quest={ENC}",
    "corsfix": f"https://proxy.corsfix.com/?{TARGET}",
    "cors_workers_dev": f"https://test.cors.workers.dev/?{TARGET}",
    "cors_lol": f"https://api.cors.lol/?url={ENC}",
    "wayback_save": f"https://web.archive.org/save/{TARGET}",
}

N = 8
summary = {}
for name, url in VARIANTS.items():
    stats = Counter()
    samples = []
    for i in range(N):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=75, context=CTX) as r:
                body = r.read(400)
                text = body.decode("utf-8", errors="replace")
                st = r.status
        except urllib.error.HTTPError as e:
            try:
                text = e.read(400).decode("utf-8", errors="replace")
            except Exception:
                text = ""
            st = e.code
        except Exception as e:  # noqa: BLE001
            text = f"{type(e).__name__}: {e}"
            st = None
        kind = ("JSON_OK" if "currentVersion" in text
                else "CF_BLOCK" if "Attention Required" in text or "been blocked" in text
                else "CF_CHALLENGE" if "Just a moment" in text
                else f"OTHER({st})")
        stats[kind] += 1
        if len(samples) < 2:
            samples.append({"kind": kind, "head": text[:120]})
        time.sleep(1.0)
    summary[name] = {"counts": dict(stats), "samples": samples}
    print(f"{name:18s} {dict(stats)}")

out = Path(__file__).resolve().parents[1] / "raw" / "golden" / "_proxy_reliability.json"
out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\nwrote {out}")

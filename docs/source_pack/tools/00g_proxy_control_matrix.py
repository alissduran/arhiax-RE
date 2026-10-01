"""Decisive diagnostic: are the CORS proxies healthy, and what do THEY see for Barranquilla?

If a proxy returns 200 for a control URL but 522/403 for miciudad, the failure is at
Barranquilla's edge (blocked client IP or dead origin), not in our local network.
"""
from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0 Safari/537.36"}

CONTROL_OK = "https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/USA_Counties_Generalized_Boundaries/FeatureServer?f=json"
CONTROL_SIMPLE = "https://example.com"
BAQ = "https://miciudad.barranquilla.gov.co/gis/rest/services/catastro/datosabiertos/MapServer?f=json"
BAQ_ROOT = "https://miciudad.barranquilla.gov.co/gis/rest/services?f=json"

PROXIES = {
    "allorigins_raw": "https://api.allorigins.win/raw?url={}",
    "codetabs": "https://api.codetabs.com/v1/proxy?quest={}",
}

rows = []
for pname, tmpl in PROXIES.items():
    for label, target in [("control_arcgis_agol", CONTROL_OK),
                          ("control_example", CONTROL_SIMPLE),
                          ("baq_mapserver", BAQ),
                          ("baq_root", BAQ_ROOT)]:
        url = tmpl.format(urllib.parse.quote(target, safe=""))
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60, context=CTX) as r:
                body = r.read(500)
            res = {"proxy": pname, "target": label, "status": r.status,
                   "head": body[:220].decode("utf-8", errors="replace")}
        except urllib.error.HTTPError as e:
            b = b""
            try:
                b = e.read(220)
            except Exception:
                pass
            res = {"proxy": pname, "target": label, "status": e.code,
                   "head": b.decode("utf-8", errors="replace")[:220]}
        except Exception as e:  # noqa: BLE001
            res = {"proxy": pname, "target": label, "status": None,
                   "head": f"{type(e).__name__}: {e}"}
        rows.append(res)
        print(f"{pname:18s} {label:22s} -> {res['status']} | {res['head'][:150]!r}")

out = Path(__file__).resolve().parents[1] / "raw" / "golden" / "_proxy_control_matrix.json"
out.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\nwrote {out}")

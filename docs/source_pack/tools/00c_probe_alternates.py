"""Try alternate retrieval paths for the Cloudflare-blocked Barranquilla ArcGIS service."""
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

TARGET = "https://miciudad.barranquilla.gov.co/gis/rest/services/catastro/datosabiertos/MapServer?f=json"
ENC = urllib.parse.quote(TARGET, safe="")

CANDIDATES = {
    "direct": TARGET,
    "r_jina_ai": f"https://r.jina.ai/{TARGET}",
    "allorigins_raw": f"https://api.allorigins.win/raw?url={ENC}",
    "allorigins_get": f"https://api.allorigins.win/get?url={ENC}",
    "codetabs_proxy": f"https://api.codetabs.com/v1/proxy?quest={ENC}",
    "corsproxy_io": f"https://corsproxy.io/?url={ENC}",
    "thingproxy": f"https://thingproxy.freeboard.io/fetch/{TARGET}",
    "wayback_available": ("https://archive.org/wayback/available?url="
                          + urllib.parse.quote("miciudad.barranquilla.gov.co/gis/rest/services/catastro/datosabiertos/MapServer?f=json", safe="")),
    "wayback_cdx": ("http://web.archive.org/cdx/search/cdx?url=miciudad.barranquilla.gov.co/gis/rest/services*"
                    "&output=json&limit=40&collapse=urlkey"),
    "agol_search": ("https://www.arcgis.com/sharing/rest/search?q="
                    + urllib.parse.quote('"miciudad.barranquilla.gov.co"') + "&num=25&f=json"),
    "agol_search2": ("https://www.arcgis.com/sharing/rest/search?q="
                     + urllib.parse.quote('barranquilla catastro datosabiertos') + "&num=25&f=json"),
}

results = {}
for name, url in CANDIDATES.items():
    req = urllib.request.Request(url, headers={
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
        "Accept": "application/json, text/plain, */*",
    })
    try:
        with urllib.request.urlopen(req, timeout=60, context=CTX) as r:
            body = r.read()
        head = body[:300].decode("utf-8", errors="replace")
        results[name] = {"url": url, "status": r.status, "len": len(body), "head": head}
        print(f"[OK  {r.status}] {name} len={len(body)}\n     {head[:220]!r}")
    except urllib.error.HTTPError as e:
        b = b""
        try:
            b = e.read(200)
        except Exception:
            pass
        results[name] = {"url": url, "status": e.code, "error": f"HTTPError {e.code}",
                         "head": b.decode("utf-8", errors="replace")[:200]}
        print(f"[HTTP {e.code}] {name} -> {b[:120]!r}")
    except Exception as e:  # noqa: BLE001
        results[name] = {"url": url, "status": None, "error": f"{type(e).__name__}: {e}"}
        print(f"[ERR ] {name} -> {type(e).__name__}: {e}")

out = Path(__file__).resolve().parents[1] / "raw" / "golden" / "_retrieval_paths_probe.json"
out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\nwrote {out}")

"""Transport health check: which third-party fetchers are UP right now, and do they pass
Barranquilla through? Control URL first, so failures are attributable.
"""
from __future__ import annotations

import json
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")}

CONTROL = "https://httpbin.org/json"
BAQ = "https://miciudad.barranquilla.gov.co/gis/rest/services?f=json"
C = urllib.parse.quote(CONTROL, safe="")
B = urllib.parse.quote(BAQ, safe="")

BUILDERS = {
    "allorigins_raw": lambda u: f"https://api.allorigins.win/raw?url={u}",
    "allorigins_get": lambda u: f"https://api.allorigins.win/get?url={u}",
    "codetabs": lambda u: f"https://api.codetabs.com/v1/proxy?quest={u}",
    "codetabs_slash": lambda u: f"https://api.codetabs.com/v1/proxy/?quest={u}",
    "isomorphic_git": lambda u: f"https://cors.isomorphic-git.org/{urllib.parse.unquote(u)}",
    "cors_workers_dev": lambda u: f"https://test.cors.workers.dev/?{urllib.parse.unquote(u)}",
    "cors_lol": lambda u: f"https://api.cors.lol/?url={u}",
    "cors_eu_org": lambda u: f"https://cors.eu.org/{urllib.parse.unquote(u)}",
    "corsfix_q": lambda u: f"https://proxy.corsfix.com/?{urllib.parse.unquote(u)}",
    "corsfix_plain": lambda u: f"https://proxy.corsfix.com/{urllib.parse.unquote(u)}",
    "textise": lambda u: f"https://www.textise.net/showText.aspx?strURL={u}",
    "jina": lambda u: f"https://r.jina.ai/{urllib.parse.unquote(u)}",
    "microlink": lambda u: f"https://api.microlink.io/?url={u}&meta=false&data.text.selector=pre",
    "thingproxy": lambda u: f"https://thingproxy.freeboard.io/fetch/{urllib.parse.unquote(u)}",
    "yacdn": lambda u: f"https://yacdn.org/serve/{urllib.parse.unquote(u)}",
    "1secmail": lambda u: f"https://api.allorigins.win/raw?url={u}&charset=UTF-8",
}


def probe(url: str, timeout: int = 45) -> dict:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout, context=CTX) as r:
            body = r.read(600)
            st, text = r.status, body.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        try:
            text = e.read(600).decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            text = ""
        st = e.code
    except Exception as e:  # noqa: BLE001
        return {"status": None, "kind": f"ERR {type(e).__name__}", "head": str(e)[:160]}
    kind = ("ARCGIS_JSON" if "currentVersion" in text
            else "JSON" if text.lstrip().startswith(("{", "["))
            else "CF_BLOCK" if ("Attention Required" in text or "been blocked" in text)
            else "CF_CHALLENGE" if "Just a moment" in text
            else "HTML")
    return {"status": st, "kind": kind, "head": text[:200]}


rows = []
for name, build in BUILDERS.items():
    ctl = probe(build(C))
    time.sleep(0.6)
    baq = probe(build(B))
    time.sleep(0.6)
    rows.append({"transport": name, "control": ctl, "baq": baq})
    print(f"{name:18s} ctl={ctl['status']}/{ctl['kind']:12s} baq={baq['status']}/{baq['kind']:12s} | {baq['head'][:80]!r}")

out = Path(__file__).resolve().parents[1] / "raw" / "golden" / "_transport_health.json"
try:
    prev = json.loads(out.read_text(encoding="utf-8")) if out.exists() else []
except Exception:  # noqa: BLE001
    prev = []
prev.append({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "rows": rows})
out.write_text(json.dumps(prev, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\nwrote {out}")

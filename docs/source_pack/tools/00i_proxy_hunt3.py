"""Round 3: broad proxy hunt. Each candidate is validated with a CONTROL url first,
so a failure can be attributed to the proxy itself rather than to Barranquilla.
"""
from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
      "Accept": "application/json, text/plain, */*"}

CONTROL = "https://httpbin.org/json"
BAQ = "https://miciudad.barranquilla.gov.co/gis/rest/services?f=json"
BAQ_ENC = urllib.parse.quote(BAQ, safe="")
CTL_ENC = urllib.parse.quote(CONTROL, safe="")

# NOTE: correct translate.goog host derivation: dots -> dashes
TRANS = ("https://miciudad-barranquilla-gov-co.translate.goog/gis/rest/services"
         "?f=json&_x_tr_sl=en&_x_tr_tl=es&_x_tr_hl=en&_x_tr_pto=wapp")

CANDS = {
    "translate_goog_fixed": (TRANS, None),
    "translate_goog_root": ("https://miciudad-barranquilla-gov-co.translate.goog/?_x_tr_sl=en&_x_tr_tl=es&_x_tr_hl=en", None),
    "allorigins_raw": (f"https://api.allorigins.win/raw?url={BAQ_ENC}", f"https://api.allorigins.win/raw?url={CTL_ENC}"),
    "cors_eu_org": (f"https://cors.eu.org/{BAQ}", f"https://cors.eu.org/{CONTROL}"),
    "jsonp_afeld": (f"https://jsonp.afeld.me/?url={BAQ_ENC}", None),
    "yacdn": (f"https://yacdn.org/proxy/{BAQ}", None),
    "corsproxy_org": (f"https://corsproxy.org/?{BAQ_ENC}", None),
    "proxy_cors_sh": (BAQ, None),
    "cors_anywhere": (f"https://cors-anywhere.herokuapp.com/{BAQ}", None),
    "cors_lol_retry": (f"https://api.cors.lol/?url={BAQ_ENC}", None),
    "api_allorigins_win_get": (f"https://api.allorigins.win/get?url={BAQ_ENC}", None),
    "codetabs_retry": (f"https://api.codetabs.com/v1/proxy?quest={BAQ_ENC}", f"https://api.codetabs.com/v1/proxy?quest={CTL_ENC}"),
    "jina_retry": (f"https://r.jina.ai/{BAQ}", None),
    "thingproxy_alt": (f"https://cors.bridged.cc/{BAQ}", None),
    "whateverorigin": (f"http://www.whateverorigin.org/get?url={BAQ_ENC}", None),
    "walking_me": (f"https://api.microlink.io/?url={BAQ_ENC}&meta=false&data.status=true", None),
}

rows = []
for name, (target, control) in CANDS.items():
    entry = {"name": name, "target_url": target, "control_url": control}
    for label, url in (("control", control), ("baq", target)):
        if not url:
            continue
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60, context=CTX) as r:
                body = r.read(500)
                text = body.decode("utf-8", errors="replace")
                st = r.status
        except urllib.error.HTTPError as e:
            try:
                text = e.read(500).decode("utf-8", errors="replace")
            except Exception:
                text = ""
            st = e.code
        except Exception as e:  # noqa: BLE001
            text = f"{type(e).__name__}: {e}"
            st = None
        kind = ("ARCGIS_JSON" if "currentVersion" in text
                else "JSON" if text.strip().startswith(("{", "["))
                else "CF_BLOCK" if ("Attention Required" in text or "been blocked" in text)
                else "CF_CHALLENGE" if "Just a moment" in text
                else "HTML/OTHER")
        entry[label] = {"status": st, "kind": kind, "head": text[:200]}
        print(f"{name:24s} {label:8s} -> {st} {kind} | {text[:110]!r}")
        time.sleep(0.8)
    rows.append(entry)

out = Path(__file__).resolve().parents[1] / "raw" / "golden" / "_proxy_hunt_round3.json"
out.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\nwrote {out}")

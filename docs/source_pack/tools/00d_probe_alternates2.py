"""Second round of alternate retrieval paths (Google translate proxy, extra CORS proxies, wayback)."""
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

MAPS = "https://miciudad.barranquilla.gov.co/gis/rest/services/catastro/datosabiertos/MapServer"
ROOT = "https://miciudad.barranquilla.gov.co/gis/rest/services"
Q = f"{MAPS}?f=json"
ENC = urllib.parse.quote(Q, safe="")

TRANS = ("https://miciudad-barraquilla-gov-co.translate.goog/gis/rest/services/catastro/datosabiertos/MapServer"
         "?f=json&_x_tr_sl=en&_x_tr_tl=es&_x_tr_hl=en")

CANDS = {
    "translate_goog": TRANS,
    "translate_goog_root": ("https://miciudad-barraquilla-gov-co.translate.goog/gis/rest/services"
                            "?f=json&_x_tr_sl=en&_x_tr_tl=es&_x_tr_hl=en"),
    "wayback_domain": ("http://web.archive.org/cdx/search/cdx?url=miciudad.barranquilla.gov.co"
                       "&matchType=domain&output=json&limit=60"),
    "wayback_prefix": ("http://web.archive.org/cdx/search/cdx?url=miciudad.barranquilla.gov.co/gis/rest"
                       "&matchType=prefix&output=json&limit=60"),
    "wayback_any": ("http://web.archive.org/cdx/search/cdx?url=barranquilla.gov.co&matchType=domain"
                    "&output=json&limit=60&filter=urlkey:.*gis.*"),
    "timemap": f"http://web.archive.org/web/timemap/link/{ROOT}",
    "cors_lol": f"https://api.cors.lol/?url={ENC}",
    "whateverorigin": f"http://www.whateverorigin.org/get?url={ENC}",
    "codetabs_alt": f"https://api.codetabs.com/v1/proxy/?quest={Q}",
    "allorigins_alt": f"https://api.allorigins.win/raw?url={urllib.parse.quote(ROOT + '?f=json', safe='')}",
    "12ft": f"https://r.jina.ai/{ROOT}?f=json",
    "textise": f"https://api.scrapingant.com/v2/general?url={ENC}",
}

res = {}
for name, url in CANDS.items():
    req = urllib.request.Request(url, headers={
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
        "Accept": "application/json, text/plain, */*",
    })
    try:
        with urllib.request.urlopen(req, timeout=70, context=CTX) as r:
            body = r.read()
        head = body[:400].decode("utf-8", errors="replace")
        res[name] = {"url": url, "status": r.status, "len": len(body), "head": head}
        print(f"[OK  {r.status}] {name} len={len(body)}\n     {head[:300]!r}")
    except urllib.error.HTTPError as e:
        b = b""
        try:
            b = e.read(300)
        except Exception:
            pass
        res[name] = {"url": url, "status": e.code, "error": f"HTTPError {e.code}",
                     "head": b.decode("utf-8", errors="replace")[:300]}
        print(f"[HTTP {e.code}] {name} -> {b[:200]!r}")
    except Exception as e:  # noqa: BLE001
        res[name] = {"url": url, "status": None, "error": f"{type(e).__name__}: {e}"}
        print(f"[ERR ] {name} -> {type(e).__name__}: {e}")

out = Path(__file__).resolve().parents[1] / "raw" / "golden" / "_retrieval_paths_probe_round2.json"
out.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\nwrote {out}")

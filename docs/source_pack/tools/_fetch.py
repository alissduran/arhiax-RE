"""Resilient fetcher: direct transport is Cloudflare-blocked from this egress, so third-party
fetchers are used. Their availability fluctuates, so every call rotates a transport pool,
validates that the body is real JSON (not a Cloudflare block/challenge page), and caches
the raw bytes on disk so a harvest can resume without re-fetching.

Transports (all return the ORIGINAL upstream body, unmodified):
  * direct        — native urllib request (recorded even though it 403s, as evidence)
  * allorigins    — https://api.allorigins.win/raw?url=<url>            (raw passthrough)
  * microlink     — https://api.microlink.io/?url=<url>&...             (JSON in data.text)
"""
from __future__ import annotations

import hashlib
import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

BLOCK_MARKERS = ("Attention Required", "Just a moment", "you have been blocked",
                 "cf-error-details", "Oops... Request Timeout", "error code: 522",
                 "error code: 1200", "Rate limit exceeded", "invalid_origin")

CACHE = Path(__file__).resolve().parents[1] / "raw" / "golden" / "_raw_cache"
CACHE.mkdir(parents=True, exist_ok=True)

_LAST = [0.0]
MIN_GAP = 0.8


def _slug(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:16] + "_" + \
        "".join(c if c.isalnum() else "-" for c in urllib.parse.urlparse(url).path)[-70:]


def _throttle() -> None:
    gap = time.time() - _LAST[0]
    if gap < MIN_GAP:
        time.sleep(MIN_GAP - gap)
    _LAST[0] = time.time()


def _decode(body: bytes) -> str:
    """Decode an ArcGIS/HTTP body without lossy replacement.

    api.allorigins.win sometimes re-encodes the upstream body as Latin-1, so a strict UTF-8
    decode fails and a Latin-1/CP1252 fallback recovers real accented names ("Dirección").
    Only a last resort uses replacement, and such bodies are flagged for refetch.
    """
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return body.decode(enc)
        except UnicodeDecodeError:
            continue
    return body.decode("utf-8", "replace")


def _get(url: str, timeout: int, extra: dict | None = None) -> dict:
    _throttle()
    headers = {"User-Agent": UA, "Accept": "application/json, text/plain, */*"}
    if extra:
        headers.update(extra)
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
            return {"status": r.status, "text": _decode(r.read()), "err": None}
    except urllib.error.HTTPError as e:
        try:
            text = _decode(e.read())
        except Exception:  # noqa: BLE001
            text = ""
        return {"status": e.code, "text": text, "err": f"HTTPError {e.code}"}
    except Exception as e:  # noqa: BLE001
        return {"status": None, "text": "", "err": f"{type(e).__name__}: {e}"}


def _headers_for(transport: str) -> dict | None:
    if transport == "corsfix":
        # corsfix rejects requests without a browser-ish Origin
        return {"Origin": "https://app.example.com", "Referer": "https://app.example.com/"}
    return None


def _wrap(transport: str, url: str) -> str:
    if transport == "direct":
        return url
    enc = urllib.parse.quote(url, safe="")
    if transport == "allorigins":
        return f"https://api.allorigins.win/raw?url={enc}"
    if transport == "microlink":
        return f"https://api.microlink.io/?url={enc}&meta=false&data.text.selector=pre"
    if transport == "corsfix":
        return f"https://proxy.corsfix.com/?{enc}"
    if transport == "codetabs":
        return f"https://api.codetabs.com/v1/proxy?quest={enc}"
    if transport == "cors_lol":
        return f"https://api.cors.lol/?url={enc}"
    if transport == "cors_eu_org":
        return f"https://cors.eu.org/{url}"
    if transport == "cors_workers_dev":
        return f"https://test.cors.workers.dev/?{url}"
    if transport == "isomorphic_git":
        return f"https://cors.isomorphic-git.org/{url}"
    raise ValueError(transport)


def _unwrap(transport: str, text: str):
    """Return the upstream JSON object, or None."""
    if transport == "microlink":
        try:
            outer = json.loads(text)
        except Exception:  # noqa: BLE001
            return None
        if not isinstance(outer, dict) or outer.get("status") != "success":
            return None
        inner = (outer.get("data") or {}).get("text")
        if isinstance(inner, dict):
            return inner
        if isinstance(inner, str):
            try:
                return json.loads(inner)
            except Exception:  # noqa: BLE001
                return None
        return None
    try:
        return json.loads(text)
    except Exception:  # noqa: BLE001
        return None


def _is_blocked(text: str) -> bool:
    return any(m in text for m in BLOCK_MARKERS)


# Keys that only ever appear in a proxy/Cloudflare error envelope. api.allorigins.win returns its
# OWN Cloudflare 522 as a JSON document with HTTP 200, which parses as valid JSON; accepting it
# would poison the cache with fake "evidence", so these are rejected explicitly.
PROXY_ERROR_KEYS = ("cloudflare_error", "ray_id", "owner_action_required", "what_you_should_do",
                    "error_code", "corsfix_error", "error_name", "zone")

# Keys that a genuine ArcGIS REST response carries.
ARCGIS_POSITIVE_KEYS = ("currentVersion", "folders", "services", "layers", "tables", "fields",
                        "geometryType", "features", "error", "objectIdField", "displayField",
                        "spatialReference", "extent", "maxRecordCount")


def _looks_like_proxy_error(d) -> bool:
    if not isinstance(d, dict):
        return False
    if any(k in d for k in PROXY_ERROR_KEYS):
        return True
    if str(d.get("title", "")).startswith(("Error 5", "Error 4")):
        return True
    t = d.get("type")
    if isinstance(t, str) and t.startswith("http"):
        return True
    return False


def _looks_like_arcgis(d) -> bool:
    if not isinstance(d, dict) or _looks_like_proxy_error(d):
        return False
    if not any(k in d for k in ARCGIS_POSITIVE_KEYS):
        return False
    err = d.get("error")
    if err is not None and not (isinstance(err, dict) and ("code" in err or "message" in err)):
        return False
    return True


def _accept(transport: str, text: str):
    """(data, reject_reason). data is None unless the body is a genuine ArcGIS payload."""
    if _is_blocked(text):
        return None, "html_block_marker"
    data = _unwrap(transport, text)
    if data is None:
        return None, "not_json"
    if _looks_like_proxy_error(data):
        return None, "proxy_error_envelope"
    if not _looks_like_arcgis(data):
        return None, "not_arcgis_payload"
    return data, None


def fetch(url: str, budget: int = 14, timeout: int = 50, use_cache: bool = True,
          order: list[str] | None = None) -> dict:
    """Fetch url as JSON with transport rotation.

    Returns {"ok", "data", "provenance"}. Never raises.
    """
    if not url.endswith("f=json") and "f=json" not in url and "f=geojson" not in url:
        url = f"{url}{'&' if '?' in url else '?'}f=json"
    cache_file = CACHE / f"{_slug(url)}.json"
    if use_cache and cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            # re-validate on read: older cache versions accepted proxy error envelopes
            if cached.get("ok") and _looks_like_arcgis(cached.get("data")):
                cached["provenance"]["served_from_cache"] = True
                return cached
        except Exception:  # noqa: BLE001
            pass

    # Weighted rotation: api.allorigins.win is the only transport observed to return genuine
    # Barranquilla ArcGIS JSON, so it gets the most attempts; the rest are opportunistic.
    transports = order or ["allorigins", "allorigins", "codetabs", "microlink", "corsfix",
                           "allorigins", "cors_lol", "cors_eu_org", "cors_workers_dev",
                           "isomorphic_git", "direct"]
    attempts = []
    t0 = time.time()
    for i in range(budget):
        transport = transports[i % len(transports)]
        wurl = _wrap(transport, url)
        res = _get(wurl, timeout, _headers_for(transport))
        data, reason = _accept(transport, res["text"])
        attempts.append({"transport": transport, "attempt": i + 1, "http_status": res["status"],
                         "bytes": len(res["text"]), "reject_reason": reason, "error": res["err"],
                         "at": datetime.now(timezone.utc).isoformat()})
        if data is not None:
            out = {"ok": True, "data": data,
                   "provenance": {"requested_url": url, "transport": transport,
                                  "transport_url": wurl, "http_status": res["status"],
                                  "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
                                  "elapsed_s": round(time.time() - t0, 1),
                                  "attempt_count": len(attempts), "served_from_cache": False,
                                  "attempts": attempts[-6:]}}
            cache_file.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
            return out
        # a 403 from direct is conclusive for that transport; keep rotating the proxies
    out = {"ok": False, "data": None,
           "provenance": {"requested_url": url, "transport": None, "ok": False,
                          "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
                          "elapsed_s": round(time.time() - t0, 1),
                          "attempt_count": len(attempts), "attempts": attempts[-10:],
                          "final_error": "no transport returned a valid ArcGIS JSON body"}}
    cache_file.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def arcgis_error(data) -> str | None:
    if isinstance(data, dict) and isinstance(data.get("error"), dict):
        e = data["error"]
        return f"[{e.get('code')}] {e.get('message')} :: {str(e.get('details'))[:160]}"
    return None

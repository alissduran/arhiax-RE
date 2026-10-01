"""Shared HTTP helper for ArcGIS REST discovery (urllib, no curl)."""
from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://miciudad.barranquilla.gov.co/gis/rest/services"

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ARHIAX-RE-SourcePack/1.0"


def get_json(url: str, params: dict | None = None, timeout: int = 45, retries: int = 3) -> dict:
    """GET url (with params) and return parsed JSON + transport metadata."""
    if params:
        qs = urllib.parse.urlencode(params)
        sep = "&" if "?" in url else "?"
        full = f"{url}{sep}{qs}"
    else:
        full = url
    last_err = None
    for attempt in range(retries):
        req = urllib.request.Request(full, headers={"User-Agent": UA, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as resp:
                raw = resp.read()
                status = resp.status
            try:
                data = json.loads(raw.decode("utf-8", errors="replace"))
            except Exception as exc:  # noqa: BLE001
                return {"_transport": {"url": full, "http_status": status, "ok": True,
                                       "json_parse_error": str(exc),
                                       "body_head": raw[:2000].decode("utf-8", errors="replace")}}
            if isinstance(data, dict):
                data.setdefault("_transport", {})
                if isinstance(data["_transport"], dict):
                    data["_transport"].update({"url": full, "http_status": status, "ok": True})
            return data
        except urllib.error.HTTPError as exc:
            body = ""
            try:
                body = exc.read()[:2000].decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                pass
            last_err = {"url": full, "ok": False, "http_status": exc.code,
                        "error": f"HTTPError {exc.code}", "body_head": body}
            if exc.code in (400, 404, 403):
                return {"_transport": last_err}
        except Exception as exc:  # noqa: BLE001
            last_err = {"url": full, "ok": False, "error": f"{type(exc).__name__}: {exc}"}
        time.sleep(1.5 * (attempt + 1))
    return {"_transport": last_err or {"url": full, "ok": False, "error": "unknown"}}


def dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  wrote {path} ({path.stat().st_size} bytes)")

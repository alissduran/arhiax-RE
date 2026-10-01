"""Map exactly what the sandbox network allows: which hosts/transports reach the ArcGIS GIS."""
from __future__ import annotations

import json
import socket
import ssl
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

TARGETS = [
    "https://example.com",
    "https://httpbin.org/get",
    "https://miciudad.barranquilla.gov.co/gis/rest/services/catastro/datosabiertos/MapServer?f=json",
    "http://miciudad.barranquilla.gov.co/gis/rest/services/catastro/datosabiertos/MapServer?f=json",
    "https://www.barranquilla.gov.co/",
    "https://barranquilla.gov.co/",
    "https://arcgis.com/",
]


def via_urllib(url: str) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
        "Accept": "application/json, text/html, */*",
    })
    try:
        with urllib.request.urlopen(req, timeout=25, context=CTX) as r:
            body = r.read(400)
            return f"HTTP {r.status} | {body[:150]!r}"
    except urllib.error.HTTPError as e:
        body = b""
        try:
            body = e.read(300)
        except Exception:
            pass
        return f"HTTPError {e.code} | {body[:150]!r}"
    except Exception as e:  # noqa: BLE001
        return f"{type(e).__name__}: {e}"


def dns(host: str) -> str:
    try:
        return f"{host} -> {socket.gethostbyname(host)}"
    except Exception as e:  # noqa: BLE001
        return f"{host} -> DNS FAIL {e}"


def via_curl(url: str) -> str:
    """curl.exe writing to a file (no stdio pipe capture)."""
    out = Path(tempfile.gettempdir()) / "arhiax_curl_probe.txt"
    exe = "curl.exe"
    cmd = [exe, "-sS", "-o", str(out), "-w", "%{http_code}", "--max-time", "30",
           "-A", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0 Safari/537.36", url]
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=45, text=True)
        body = out.read_text(encoding="utf-8", errors="replace")[:200] if out.exists() else ""
        return f"code={p.stdout.strip()!r} rc={p.returncode} err={p.stderr.strip()[:120]!r} body={body[:150]!r}"
    except Exception as e:  # noqa: BLE001
        return f"curl probe failed: {type(e).__name__}: {e}"


print("== DNS ==")
for h in ["example.com", "miciudad.barranquilla.gov.co", "www.barranquilla.gov.co", "arcgis.com"]:
    print(" ", dns(h))

print("\n== urllib ==")
for u in TARGETS:
    print(f"  {u}\n      -> {via_urllib(u)}")

print("\n== curl.exe ==")
for u in ["https://example.com",
          "https://miciudad.barranquilla.gov.co/gis/rest/services/catastro/datosabiertos/MapServer?f=json"]:
    print(f"  {u}\n      -> {via_curl(u)}")

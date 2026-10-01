"""Look for a subdomain / origin IP of the Barranquilla GIS that is not behind the blocked Cloudflare edge."""
from __future__ import annotations

import json
import socket
from pathlib import Path

SUBS = ["miciudad", "gis", "sig", "geoportal", "arcgis", "geoserver", "mapas", "cartografia",
        "catastro", "pot", "datosabiertos", "servicios", "aplicaciones", "webgis", "portal",
        "www", "barranquilla", "geo", "ide", "spatial", "espacio", "observatorio"]

CF_RANGES_HINT = ("104.16.", "104.17.", "104.18.", "104.19.", "104.20.", "104.21.", "104.22.",
                  "104.23.", "104.24.", "104.25.", "104.26.", "104.27.",
                  "172.64.", "172.65.", "172.66.", "172.67.", "172.68.", "172.69.", "172.70.", "172.71.",
                  "188.114.", "190.93.", "197.234.", "198.41.", "162.158.", "162.159.", "173.245.",
                  "103.21.", "103.22.", "103.31.", "141.101.", "108.162.")

rows = []
for s in SUBS:
    host = f"{s}.barranquilla.gov.co"
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        ips = sorted({i[4][0] for i in infos})
        cf = all(any(ip.startswith(p) for p in CF_RANGES_HINT) for ip in ips)
        rows.append({"host": host, "ips": ips, "cloudflare_fronted": cf})
        flag = "CF" if cf else "*** NON-CLOUDFLARE ***"
        print(f"{host:52s} {','.join(ips):30s} {flag}")
    except Exception as e:  # noqa: BLE001
        rows.append({"host": host, "error": f"{type(e).__name__}: {e}"})
        print(f"{host:52s} DNS FAIL {e}")

out = Path(__file__).resolve().parents[1] / "raw" / "golden" / "_dns_probe_subdomains.json"
out.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\nwrote {out}")

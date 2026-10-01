"""Try to reach the ArcGIS origin directly at city-owned IPs, bypassing the Cloudflare edge.

portal.barranquilla.gov.co resolves to 181.49.136.170 / 190.248.57.39 (NOT Cloudflare),
so the ArcGIS server may be reachable there with SNI/Host = miciudad.barranquilla.gov.co.
"""
from __future__ import annotations

import json
import socket
import ssl
from pathlib import Path

IPS = ["181.49.136.170", "190.248.57.39"]
HOSTS = ["miciudad.barranquilla.gov.co", "portal.barranquilla.gov.co", "www.barranquilla.gov.co"]
PATHS = ["/gis/rest/services?f=json",
         "/gis/rest/services/catastro/datosabiertos/MapServer?f=json"]

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

results = []


def raw_https(ip: str, sni: str, path: str, port: int = 443, timeout: int = 20) -> str:
    try:
        sock = socket.create_connection((ip, port), timeout=timeout)
    except Exception as e:  # noqa: BLE001
        return f"TCP FAIL: {type(e).__name__}: {e}"
    try:
        if port == 443:
            ssock = CTX.wrap_socket(sock, server_hostname=sni)
        else:
            ssock = sock
        req = (f"GET {path} HTTP/1.1\r\nHost: {sni}\r\n"
               "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36\r\n"
               "Accept: application/json, */*\r\nConnection: close\r\n\r\n")
        ssock.sendall(req.encode())
        chunks = []
        while len(b"".join(chunks)) < 6000:
            b = ssock.recv(4096)
            if not b:
                break
            chunks.append(b)
        data = b"".join(chunks)
        ssock.close()
        head, _, body = data.partition(b"\r\n\r\n")
        status = head.split(b"\r\n")[0].decode("utf-8", "replace")
        return f"{status} | {body[:300].decode('utf-8', 'replace')!r}"
    except Exception as e:  # noqa: BLE001
        return f"TLS/READ FAIL: {type(e).__name__}: {e}"
    finally:
        try:
            sock.close()
        except Exception:
            pass


for ip in IPS:
    for sni in HOSTS:
        for path in PATHS:
            r = raw_https(ip, sni, path)
            print(f"[{ip}] sni={sni} {path}\n    -> {r}")
            results.append({"ip": ip, "sni": sni, "path": path, "result": r})

# also plain HTTP on 80 (some ArcGIS servers expose only http internally)
for ip in IPS:
    for sni in HOSTS:
        r = raw_https(ip, sni, "/gis/rest/services?f=json", port=80)
        print(f"[{ip}:80] sni={sni} /gis/rest/services?f=json\n    -> {r}")
        results.append({"ip": ip, "sni": sni, "path": "http:/gis/rest/services?f=json", "result": r})

out = Path(__file__).resolve().parents[1] / "raw" / "golden" / "_origin_ip_probe.json"
out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\nwrote {out}")

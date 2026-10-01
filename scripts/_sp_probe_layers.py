# -*- coding: utf-8 -*-
"""Sonda de capas del geoportal de Barranquilla (solo lectura).

Intenta obtener la metadata REAL de las capas exigidas por el Source Pack.
Escribe docs/source_pack/raw/golden/_layers_probe.json (no sobrescribe capturas
de fuentes ya existentes). Nunca inventa: si no hay respuesta, lo declara.
"""
from __future__ import annotations

import json
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DEST = RAIZ / "docs" / "source_pack" / "raw" / "golden" / "_layers_probe.json"

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36")

BASES = [
    "https://miciudad.barranquilla.gov.co/gis/rest/services/catastro/datosabiertos/MapServer",
    "https://miciudad.barranquilla.gov.co/gis/rest/services/ordenamiento",
]

LAYERS = [3, 4, 18, 20, 21, 22, 23, 24, 25, 26, 27, 71, 73, 75, 77, 79, 81, 83, 85, 87,
          89, 91, 92, 100, 105, 315, 310, 320, 500, 545]


def get(url: str, timeout: int = 25):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-CO,es;q=0.9,en;q=0.8",
        "Referer": "https://miciudad.barranquilla.gov.co/",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
            body = r.read()
        try:
            return {"ok": True, "status": 200, "json": json.loads(body.decode("utf-8", "replace"))}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "status": 200, "error": f"json: {exc}",
                    "head": body[:400].decode("utf-8", "replace")}
    except urllib.error.HTTPError as exc:
        try:
            head = exc.read()[:300].decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            head = ""
        return {"ok": False, "status": exc.code, "error": f"HTTPError {exc.code}", "head": head}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "status": None, "error": f"{type(exc).__name__}: {exc}"}


def main() -> int:
    out = {"probe": "layers", "bases": {}, "results": {}}
    for base in BASES:
        root = get(base + "?f=json")
        entry = {"service_url": base, "root_status": root.get("status"),
                 "root_ok": bool(root.get("ok")), "root_error": root.get("error"),
                 "layers": []}
        if root.get("ok"):
            data = root.get("json") or {}
            for lyr in data.get("layers", []) + data.get("tables", []):
                entry["layers"].append({"id": lyr.get("id"), "name": lyr.get("name"),
                                        "type": lyr.get("type")})
        out["bases"][base] = entry

    base_cat = BASES[0]
    for lid in LAYERS:
        for base in (base_cat, BASES[1] + "/unidadesadministrativas/MapServer",
                     BASES[1] + "/planeacion/MapServer",
                     BASES[1] + "/estratificacion/MapServer",
                     BASES[1] + "/ordenamientoterritorial/MapServer"):
            r = get(f"{base}/{lid}?f=json")
            if r.get("ok"):
                j = r["json"] or {}
                keys = ["name", "type", "geometryType", "description", "copyrightText",
                        "minScale", "maxScale", "hasZ", "hasM", "supportsStatistics"]
                out["results"][f"{base}/{lid}"] = {
                    "status": 200, "name": j.get("name"), "type": j.get("type"),
                    "geometryType": j.get("geometryType"),
                    "fields": [f.get("name") for f in (j.get("fields") or [])][:40],
                    "extent": (j.get("extent") or {}).get("spatialReference"),
                    "meta": {k: j.get(k) for k in keys if k in j},
                }
                break
            out["results"][f"{base}/{lid}"] = {"status": r.get("status"), "error": r.get("error"),
                                               "head": (r.get("head") or "")[:120]}
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    ok = sum(1 for v in out["results"].values() if v.get("status") == 200)
    print(f"probe escrito en {DEST}: {ok} capas con metadata de {len(out['results'])} intentos")
    return 0


if __name__ == "__main__":
    sys.exit(main())

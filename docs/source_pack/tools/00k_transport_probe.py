"""Probe every configured transport against one target and report which accept real data."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _fetch import _accept, _get, _headers_for, _wrap  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else \
    "https://miciudad.barranquilla.gov.co/gis/rest/services/ordenamiento?f=json"

TRANSPORTS = ["allorigins", "codetabs", "microlink", "corsfix", "cors_lol",
              "cors_eu_org", "cors_workers_dev", "isomorphic_git", "direct"]

for tr in TRANSPORTS:
    w = _wrap(tr, URL)
    r = _get(w, 40, _headers_for(tr))
    data, reason = _accept(tr, r["text"])
    print(f"{tr:18s} http={r['status']} bytes={len(r['text']):6d} "
          f"accept={'YES' if data else reason:22s} head={r['text'][:100]!r}")

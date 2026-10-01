# -*- coding: utf-8 -*-
"""Sonda: coordenada y claves útiles del run state Golden + disponibilidad de PyYAML."""
from __future__ import annotations

import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
RS = RAIZ / "docs" / "forensics" / "040-646406" / "dictus_2b" / "DICTUS_RUN_STATE_040-646406.json"

try:
    import yaml  # noqa: F401
    print("PyYAML:", yaml.__version__)
except Exception as exc:  # noqa: BLE001
    print("PyYAML NO disponible:", exc)


def main() -> int:
    d = json.loads(RS.read_text(encoding="utf-8"))
    print("top-level keys:", sorted(d.keys()))
    texto = json.dumps(d, ensure_ascii=False)
    for aguja in ("11.005", "-74.8386", "coordenada", "geometry", "lat", "lon"):
        print(f"  contiene {aguja!r}: {aguja in texto}")

    def walk(o, p=""):
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(v, (dict, list)):
                    walk(v, f"{p}.{k}")
                else:
                    kl = str(k).lower()
                    if any(t in kl for t in ("lat", "lon", "coord", "geom", "pieza",
                                             "manzana", "estrato", "barrio", "tratam",
                                             "riesgo", "amenaza", "inunda", "altura",
                                             "destino", "predial", "nupre", "fmi",
                                             "area", "visor", "fuente")):
                        print(f"  {p}.{k} = {str(v)[:110]!r}")
        elif isinstance(o, list):
            for i, v in enumerate(o[:4]):
                walk(v, f"{p}[{i}]")

    walk(d)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

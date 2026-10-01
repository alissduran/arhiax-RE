# -*- coding: utf-8 -*-
"""Sonda: estructura de solar_state.momentos + firmas reales de street_imagery."""
from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "api"))

RS = RAIZ / "docs" / "forensics" / "040-646406" / "dictus_2b" / "DICTUS_RUN_STATE_040-646406.json"


def main() -> int:
    rs = json.loads(RS.read_text(encoding="utf-8"))
    print("solar_state:", json.dumps(rs.get("solar_state"), ensure_ascii=False, indent=1)[:1200])
    print("shadow_simulation:", json.dumps(rs.get("shadow_simulation"), ensure_ascii=False)[:400])

    import street_imagery as si
    print("consultar_vista_automatica:", inspect.signature(si.consultar_vista_automatica))
    print("seleccionar_vista_automatica:", inspect.signature(si.seleccionar_vista_automatica))
    print("METODO_SELECCION:", si.METODO_SELECCION)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""Extrae la tabla del informe final desde el artefacto del harvest."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
d = json.loads((ROOT / "docs" / "estimation" / "MARKET_HARVEST_040-646406.json")
               .read_text(encoding="utf-8"))

print("folio", d["folio"], "| sujeto:", json.dumps(d["sujeto"], ensure_ascii=False))
print()
for k, c in d["capas"].items():
    print("CAPA", k)
    print("   nombre real :", c["layer_name"])
    print("   layer_id    :", c["layer_id"])
    print("   HTTP        :", c["http_status"], "| bytes:", c["bytes"],
          "| sha256(8):", str(c["sha256"])[:8])
    print("   status      :", c["status"], "| scope:", c["status_scope"],
          "| punto:", c["status_punto_sujeto"])
    print("   banda_36_60 :", c["usable_for_estimation"])
    print("   value/range :", json.dumps(c["value_or_range"], ensure_ascii=False))
    print("   vigencia    :", c["effective_from"], "->", c["effective_to"],
          "| precisión:", c.get("effective_precision"), "| sample:", c["sample_size"])
    print()

print("=== LEVEL 3 LITERAL ===")
print(json.dumps(d["level_3_referencias"], ensure_ascii=False, indent=2))
print()
print("=== TRANSICION DE COMPUERTA ===")
print(json.dumps(d["GAP_REPORT"]["transicion_de_compuerta"], ensure_ascii=False, indent=2))

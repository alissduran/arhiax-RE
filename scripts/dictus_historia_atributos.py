# -*- coding: utf-8 -*-
"""Auditoría histórica del expediente (§C): ATTRIBUTE HISTORY MATRIX + consistencia.

    python scripts/dictus_historia_atributos.py [--folio 040-646406]

Recorre las versiones históricas REALES del mismo inmueble que existen en el
repositorio, extrae los atributos de cada una y produce:

  docs/forensics/<folio>/dictus_2/ATTRIBUTE_HISTORY_MATRIX.json
  docs/forensics/<folio>/dictus_2/ATTRIBUTE_HISTORY_MATRIX.md
  docs/forensics/<folio>/dictus_2/HISTORICAL_CONSISTENCY_REPORT.json

Nada se inventa: lo que un documento no declara queda `SIN_DATO` y lo que cambia sin
fuente ni método que lo explique queda `HISTORICAL_CONFLICT`.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))

import dictus_historia as dh  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Attribute History Matrix (DICTUS 2.0)")
    ap.add_argument("--folio", default="040-646406")
    ap.add_argument("--raiz", default=str(ROOT))
    args = ap.parse_args(argv)

    raiz = Path(args.raiz)
    versiones = dh.descubrir_versiones(raiz, args.folio)
    if not versiones:
        print(f"[FAIL] no se encontró ninguna versión histórica del folio {args.folio}")
        return 1

    print(f"[historia] versiones encontradas: {len(versiones)}")
    for v in versiones:
        print(f"   · {v['version'][:52]:<52} {v['fecha']}  {v['paginas']:>3} pp  "
              f"sha256 {v['pdf_sha256'][:12]}…")

    matriz = dh.construir_matriz(versiones)
    salida = ROOT / "docs" / "forensics" / args.folio / "dictus_2"
    dh.escribir_matriz(matriz, salida / "ATTRIBUTE_HISTORY_MATRIX.json",
                       salida / "ATTRIBUTE_HISTORY_MATRIX.md")
    rep = dh.reporte_consistencia(matriz)
    (salida / "HISTORICAL_CONSISTENCY_REPORT.json").write_text(
        json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\n[historia] filas de matriz: {len(matriz['filas'])} · "
          f"cambios: {len(matriz['cambios'])}")
    print(f"[historia] conflictos abiertos: {len(rep['conflictos_abiertos'])} · "
          f"explicados: {len(rep['cambios_explicados'])} · "
          f"por revisar: {len(rep['requieren_revision'])}")
    for c in rep["conflictos_abiertos"]:
        print(f"\n   HISTORICAL_CONFLICT · {c['atributo']} · valores={c['valores']}")
        for k in c["cambios"]:
            print(f"      {k['version_anterior'][:34]} → {k['version_actual'][:34]}: "
                  f"{k['anterior']!r} → {k['actual']!r} ({k['motivo']})")
    for c in rep["cambios_explicados"]:
        print(f"   explicado · {c['atributo']}: {c['detalle']}")
    for c in rep["requieren_revision"]:
        print(f"   revisar · {c['atributo']}: {c['detalle']}")
    print(f"\n[historia] artefactos en {salida.relative_to(ROOT)}")
    print(f"[historia] veredicto: {rep['veredicto']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""DICTUS 2.0B-R1 — rasteriza las 6 páginas del EJECUTIVO para revisión visual.

    python scripts/dictus_render_ejecutivo.py [--folio 040-646406]

Deja las imágenes en `docs/forensics/<folio>/dictus_2b/paginas/ejecutivo_pN.png`
(directorio derivado y regenerable: `paginas/` está ignorado por git, igual que las
páginas rasterizadas de la corrida 03I.1) e imprime el índice de la evidencia:

  · PDF entregado y su sha256
  · número de páginas
  · los seis títulos aprobados, en orden
  · DICTUS_MASTER_HASH de la corrida

No modifica el PDF: solo lo lee (es la misma comprobación que hace el revisor humano).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))

import dictus_entrega as entrega  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Render del Ejecutivo para revisión")
    ap.add_argument("--folio", default="040-646406")
    ap.add_argument("--salida", default=None)
    ap.add_argument("--dpi", type=int, default=110)
    args = ap.parse_args(argv)

    salida = Path(args.salida) if args.salida else (
        ROOT / "docs" / "forensics" / args.folio / "dictus_2b")
    pdf = salida / entrega.ARCHIVO_EJECUTIVO.format(folio=args.folio)
    if not pdf.exists():
        print(f"[FAIL] no existe el Ejecutivo: {pdf}")
        return 1

    auditoria = entrega.auditar_ejecutivo(pdf)
    sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
    manifest_path = salida / entrega.ARCHIVO_MANIFEST.format(folio=args.folio)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}

    imagenes = []
    try:
        import pymupdf
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] pymupdf no disponible ({exc}): no se rasteriza")
    else:
        destino = salida / "paginas"
        destino.mkdir(parents=True, exist_ok=True)
        with pymupdf.open(str(pdf)) as doc:
            for i, pag in enumerate(doc, start=1):
                ruta = destino / f"ejecutivo_p{i}.png"
                pag.get_pixmap(dpi=args.dpi).save(str(ruta))
                imagenes.append(str(ruta.relative_to(ROOT)))

    print("=" * 72)
    print("ENTREGABLE PRINCIPAL (DICTUS 2.0B-R1)")
    print("=" * 72)
    print(f"archivo      : {pdf.relative_to(ROOT)}")
    print(f"sha256       : {sha}")
    print(f"páginas      : {auditoria['page_count']} (límite {entrega.MAX_PAGINAS_EJECUTIVO})")
    print(f"arquitectura : {'APROBADA' if auditoria['ok'] else 'NO APTA'}")
    for i, titulo in enumerate(auditoria["titulos"] or [], start=1):
        print(f"  P{i} {titulo}")
    print(f"master hash  : {manifest.get('master_hash', '—')}")
    print(f"dictus id    : {manifest.get('dictus_id', '—')}")
    print(f"evidencias   : {(manifest.get('evidence_manifest') or {}).get('evidence_count')} "
          f"({(manifest.get('evidence_manifest') or {}).get('estado')})")
    print(f"imágenes     : {len(imagenes)}")
    for img in imagenes:
        print(f"  {img}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

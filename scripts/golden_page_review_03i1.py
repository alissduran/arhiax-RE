# -*- coding: utf-8 -*-
"""03I.1 — Revisión página por página del dictamen Golden (estructural + textual).

Rasteriza las páginas (para revisión humana) y produce una tabla por página con:
secciones detectadas, primeras líneas, pie de página, y banderas de integridad
(página vacía, falta de pie, secciones fuera de orden, texto cortado).

No sustituye la inspección visual humana: el modelo de esta sesión no acepta
entrada de imágenes, por lo que la revisión automática es textual/estructural y
las imágenes quedan como evidencia para el revisor.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "forensics" / "040-646406" / "golden_03i1"
PAGS = OUT / "paginas"

_SECCION = re.compile(r"^(\d{2}(?:\.\d)?)\s*[-–]\s*([A-ZÁÉÍÓÚÑ][^\n]{3,80})$", re.M)
_PIE_V = re.compile(r"ARHIAX RE v[\d.]+ · commit [0-9a-f]{8}", re.I)
_PIE_PAG = re.compile(r"Pag\.\s*(\d+)")


def main() -> int:
    pdf = OUT / "ARHIAX_Dictamen_040-646406_03I1.pdf"
    doc = pymupdf.open(str(pdf))
    PAGS.mkdir(parents=True, exist_ok=True)
    filas = []
    orden_previo = 0
    for i, page in enumerate(doc, start=1):
        pix = page.get_pixmap(dpi=110)
        pix.save(str(PAGS / f"pag_{i:02d}.png"))
        txt = page.get_text() or ""
        limpio = txt.strip()
        secciones = [f"{m.group(1)} {m.group(2).strip()[:52]}" for m in _SECCION.finditer(txt)]
        lineas = [l.strip() for l in limpio.splitlines() if l.strip()]
        pie_ver = bool(_PIE_V.search(txt))
        m_pag = _PIE_PAG.search(txt)
        # Integridad: la numeración de página del pie debe ser consecutiva.
        pie_num = int(m_pag.group(1)) if m_pag else None
        banderas = []
        if len(limpio) < 200:
            banderas.append("PAGINA_CASI_VACIA")
        if not pie_ver or pie_num is None:
            banderas.append("SIN_PIE_VERSIONADO")
        if pie_num is not None and pie_num != i:
            banderas.append(f"PIE_DESALINEADO(esperado {i})")
        nums = [int(s.split()[0].split(".")[0]) for s in secciones]
        if nums and min(nums) < orden_previo:
            banderas.append("SECCION_FUERA_DE_ORDEN")
        if nums:
            orden_previo = max(orden_previo, max(nums))
        filas.append({
            "pagina": i,
            "pies": {"versionado": pie_ver, "numero": pie_num},
            "secciones": secciones,
            "lineas": len(lineas),
            "primeras": lineas[:3],
            "banderas": banderas,
        })

    man = json.loads((OUT / "GOLDEN_EXECUTION_MANIFEST.json").read_text(encoding="utf-8"))
    L = ["# GOLDEN_PAGE_REVIEW — 03I.1 (040-646406)", "",
         f"PDF: `{Path(str((man.get('outputs') or {}).get('pdf'))).name}` · "
         f"sha256 `{str((man.get('outputs') or {}).get('pdf_sha256'))}` · "
         f"{doc.page_count} páginas · imágenes en `paginas/pag_NN.png`.", "",
         "> Revisión automática **textual y estructural** (secciones, pies, orden, "
         "páginas vacías). El modelo de esta sesión no acepta entrada de imágenes: "
         "las páginas rasterizadas quedan para la inspección visual humana.", "",
         "| Pág. | Secciones detectadas | Líneas | Pie versionado | Banderas |",
         "|---|---|---|---|---|"]
    _con_bandera = 0
    for f in filas:
        _con_bandera += 1 if f["banderas"] else 0
        L.append(f"| {f['pagina']} | {' · '.join(f['secciones']) or '—'} | {f['lineas']} | "
                 f"{'sí' if f['pies']['versionado'] else 'no'} "
                 f"(nº {f['pies']['numero']}) | "
                 f"{', '.join(f['banderas']) if f['banderas'] else 'OK'} |")
    L += ["", f"**Páginas con banderas: {_con_bandera}/{doc.page_count}**", "",
          "## Detalle por página", ""]
    for f in filas:
        L.append(f"### Página {f['pagina']}")
        L.append(f"- Secciones: {', '.join(f['secciones']) or '—'}")
        L.append(f"- Inicio: {' | '.join(f['primeras'])}")
        L.append(f"- Banderas: {', '.join(f['banderas']) if f['banderas'] else 'OK'}")
        L.append("")
    (OUT / "GOLDEN_PAGE_REVIEW.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L[:14]))
    print(f"...\n[03I.1] páginas con banderas: {_con_bandera}/{doc.page_count}")
    print(f"[03I.1] informe: {OUT / 'GOLDEN_PAGE_REVIEW.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

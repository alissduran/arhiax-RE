# -*- coding: utf-8 -*-
"""DICTUS 2.0B-R1 — UNA corrida del producto → EJECUTIVO (principal) + TÉCNICO (anexo).

    python scripts/dictus_run.py --ctl <ruta\\al\\CTL.pdf> [--folio 040-646406]

Flujo (una sola verdad de corrida, sin duplicar consultas externas):

    FUENTES → compile_pdf (producto real, UNA vez)
                 │  observadores de solo lectura
                 ▼
            DictusRunState
                 ▼
        ExecutiveDocumentModel ──► EVIDENCE MANIFEST ──► DICTUS_MASTER_HASH
                 │                                          │
                 ├── DICTUS_EJECUTIVO_<folio>.pdf  ← PRINCIPAL
                 ├── DICTUS_TECNICO_<folio>.pdf    ← anexo técnico
                 └── DICTUS_MANIFEST_<folio>.json ──► /portal/ (sello)

El ejecutivo NO lee el PDF técnico: se construye desde el estado canónico, y su
entrega pasa por las aserciones duras de `dictus_entrega` (§3/§4/§5/§8).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))

import dictus_entrega as entrega            # noqa: E402
import dictus_estado as dse                 # noqa: E402

CTL_DEFECTO = (ROOT / "docs" / "forensics" / "040-646406" / "golden_03i1"
               / "inputs" / "CTL_040-646406_ORIGINAL.pdf")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="DICTUS 2.0B-R1 — corrida integrada")
    ap.add_argument("--ctl", default=str(CTL_DEFECTO))
    ap.add_argument("--folio", default="040-646406")
    ap.add_argument("--ciudad", default="barranquilla")
    ap.add_argument("--salida", default=None)
    args = ap.parse_args(argv)

    os.environ.setdefault("ARHIAX_ENV", "test")
    os.environ.setdefault("ARHIAX_AUTH_SECRET", "qa-local-secret")
    os.environ.setdefault("ARHIAX_ADMIN_PASSWORD", "dev-only-not-a-real-password")
    os.environ.setdefault("ARHIAX_EVIDENCE_HMAC_KEY", "qa-local-hmac-key")

    ctl = Path(args.ctl).expanduser()
    if not ctl.exists():
        print(f"[FAIL] falta el CTL: {ctl}")
        return 1
    salida = Path(args.salida) if args.salida else (
        ROOT / "docs" / "forensics" / args.folio / "dictus_2b")
    salida.mkdir(parents=True, exist_ok=True)
    run_id = str(uuid.uuid4())

    # ── 1 · Producto real: UNA corrida ────────────────────────────────────────
    from legal_analyzer import analizar_certificado
    from index import extraer_datos_de_pdf
    import pdf_compiler

    analysis = analizar_certificado(str(ctl))
    ext = extraer_datos_de_pdf(str(ctl), args.ciudad)
    if not ext.get("area"):
        print("[FAIL] el CTL no permite extraer el área por el camino del producto")
        return 1
    record = {
        "id": 1, "folio_matricula": ext.get("folio") or analysis.get("folio") or args.folio,
        "direccion": ext.get("direccion") or "", "barrio": ext.get("barrio") or "",
        "ciudad": args.ciudad, "area": ext.get("area"), "valor_consolidado": None,
        "sombra_9am_cargada": 0, "sombra_3pm_cargada": 0, "mapa_cargado": 0,
        "acreedor_real": None, "certificado_path": str(ctl), "estrato": None,
    }
    tecnico = salida / entrega.ARCHIVO_TECNICO.format(folio=args.folio)
    captura = entrega.iniciar_captura()          # solo lectura: no altera cálculos
    pdf_compiler.compile_pdf(record, str(tecnico), assets_dir=salida)

    # ── 2 · Estado canónico, modelo, ejecutivo y manifest de ESA corrida ──────
    from versioning import VERSION_MATRIX
    resultado = entrega.construir_entregables(
        captura, folio=args.folio, ciudad=args.ciudad, tecnico=tecnico,
        salida_dir=salida, area=record.get("area"),
        # Entrada del caso YA analizada por el producto (no una segunda extracción).
        tipo_unidad=analysis.get("tipo_predio_snr"),
        run_id=run_id, versionado=dict(VERSION_MATRIX or {}),
        publicar_manifest=ROOT / "public" / "dictus")

    ejecutivo = resultado["ejecutivo"]
    manifest = resultado["manifest"]
    auditoria = resultado["auditoria"]
    verif = entrega.verificar_entrega(manifest)
    pp_te = _paginas(tecnico)

    reporte = {
        "run_id": run_id, "dictus_id": manifest["dictus_id"],
        "generated_at": manifest["generated_at"], "master_hash": manifest["master_hash"],
        "master_manifest_version": manifest["master_manifest_version"],
        "documento_principal": str(ejecutivo.relative_to(ROOT)),
        "executive_pdf": str(ejecutivo.relative_to(ROOT)),
        "executive_pdf_sha256": hashlib.sha256(ejecutivo.read_bytes()).hexdigest(),
        "executive_page_count": auditoria["page_count"],
        "executive_titulos": auditoria["titulos"],
        "executive_auditoria_ok": auditoria["ok"],
        "technical_pdf": str(tecnico.relative_to(ROOT)),
        "technical_pdf_sha256": hashlib.sha256(tecnico.read_bytes()).hexdigest(),
        "technical_page_count": pp_te,
        "evidence_count": manifest["evidence_manifest"]["evidence_count"],
        "evidence_seal": manifest["evidence_manifest"]["estado"],
        "poi_items_in_state": resultado["run_state"]["poi_state"]["item_count"],
        "poi_distance_available": resultado["run_state"]["poi_state"]["distance_available"],
        "findings_in_page_1": len(resultado["secciones"]["hallazgos"]),
        "verify_master_hash": verif["result"],
        "layout_violations": list(entrega.de.VIOLACIONES),
        "nota_hash": ("DICTUS_MASTER_HASH sella hechos y evidencias; los SHA-256 de los PDFs "
                      "sellan el archivo entregado y NO son el hash visible."),
    }
    (salida / f"ACEPTACION_{args.folio}.json").write_text(
        json.dumps(reporte, ensure_ascii=False, indent=1), encoding="utf-8")

    # ── 3 · Artefactos versionables: texto del Golden + acceptance report ────
    texto = "\n\n".join(
        f"===== PAGINA {i + 1} =====\n" + " ".join(p.extract_text().split())
        for i, p in enumerate(_lector(ejecutivo).pages))
    (salida / f"DICTUS_2.0B_TEXTO_EJECUTIVO_{args.folio}.txt").write_text(texto + "\n",
                                                                         encoding="utf-8")
    md = [
        f"# DICTUS 2.0B-R1 — ACEPTACIÓN DE LA CORRIDA INTEGRADA ({args.folio})",
        "",
        "Una sola corrida del producto produjo el documento **ejecutivo** (el que ve el "
        "usuario) y el **técnico** (anexo), desde el mismo estado canónico y con un único "
        "hash maestro. La entrega se valida sobre el PDF FÍSICO antes de declararse apta.",
        "",
        "| Dato | Valor |",
        "|---|---|",
        f"| run_id | `{reporte['run_id']}` |",
        f"| DICTUS ID | **{reporte['dictus_id']}** |",
        f"| generado | {reporte['generated_at']} |",
        f"| **DICTUS_MASTER_HASH** | `{reporte['master_hash']}` |",
        f"| master manifest | `{reporte['master_manifest_version']}` |",
        f"| run state | `{dse.RUN_STATE_VERSION}` |",
        f"| **DOCUMENTO PRINCIPAL** | `{Path(reporte['documento_principal']).name}` · "
        f"**{reporte['executive_page_count']} páginas** · sha256 "
        f"`{reporte['executive_pdf_sha256']}` |",
        f"| Anexo técnico | `{Path(reporte['technical_pdf']).name}` · "
        f"{reporte['technical_page_count']} páginas · sha256 "
        f"`{reporte['technical_pdf_sha256']}` |",
        f"| Arquitectura del ejecutivo | {'APROBADA' if reporte['executive_auditoria_ok'] else 'NO APTA'} · "
        + " → ".join(f"P{i + 1} {t}" for i, t in enumerate(auditoria["titulos"] or [])) + " |",
        f"| Evidencias | {reporte['evidence_count']} ({reporte['evidence_seal']}) |",
        f"| Ítems de equipamiento en el estado | {reporte['poi_items_in_state']} "
        f"(distancias: {'sí' if reporte['poi_distance_available'] else 'no'}) |",
        f"| Hallazgos en la página 1 | {reporte['findings_in_page_1']} |",
        f"| Verificación del hash maestro | **{reporte['verify_master_hash']}** |",
        f"| Retícula | {'OK' if not reporte['layout_violations'] else reporte['layout_violations']} |",
        "",
        "> `DICTUS_MASTER_HASH` sella el conjunto canónico de hechos y evidencias. Los SHA-256 "
        "de los PDFs identifican el archivo entregado: **no son el hash visible** y no se "
        "sustituyen entre sí. Los PDFs no se versionan (política del repositorio); se "
        "reproducen con `python scripts/dictus_run.py`.",
        "",
    ]
    (salida / f"ACEPTACION_{args.folio}.md").write_text("\n".join(md), encoding="utf-8")

    print(f"[run] {run_id[:8]} · {reporte['dictus_id']} · master hash "
          f"{manifest['master_hash'][:16]}…")
    print(f"[run] PRINCIPAL {ejecutivo.name} · {auditoria['page_count']} páginas · "
          f"sha256 {reporte['executive_pdf_sha256'][:12]}…")
    print(f"[run]           arquitectura: "
          + " → ".join(f"P{i + 1} {t}" for i, t in enumerate(auditoria["titulos"] or [])))
    print(f"[run] ANEXO     {tecnico.name} · {pp_te} páginas · "
          f"sha256 {reporte['technical_pdf_sha256'][:12]}…")
    print(f"[run] evidencias {reporte['evidence_count']} ({reporte['evidence_seal']}) · "
          f"verificación {verif['result']} · retícula "
          f"{'OK' if not entrega.de.VIOLACIONES else entrega.de.VIOLACIONES}")
    print(f"[run] POI en el estado: {reporte['poi_items_in_state']} ítems · "
          f"distancias {'sí' if reporte['poi_distance_available'] else 'no'}")
    return 0


def _lector(ruta: Path):
    from pypdf import PdfReader
    return PdfReader(str(ruta))


def _paginas(ruta: Path) -> int:
    return len(_lector(ruta).pages)


if __name__ == "__main__":
    raise SystemExit(main())

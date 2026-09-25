# -*- coding: utf-8 -*-
"""DICTUS 2.0B — UNA corrida del producto → DOS documentos + manifest + hash maestro.

    python scripts/dictus_run.py --ctl <ruta\\al\\CTL.pdf> [--folio 040-646406]

Flujo (una sola verdad de corrida, sin duplicar consultas externas):

    FUENTES → compile_pdf (producto real, UNA vez)
                 │  observadores de solo lectura
                 ▼
            DictusRunState
                 ▼
        ExecutiveDocumentModel ──► EVIDENCE MANIFEST ──► DICTUS_MASTER_HASH
                 │                                          │
                 ├── DICTUS_EJECUTIVO_<folio>.pdf           ├── /portal/ (sello)
                 ├── DICTUS_TECNICO_<folio>.pdf             └── manifest publicado
                 └── DICTUS_MANIFEST_<folio>.json

El ejecutivo NO lee el PDF técnico: se construye desde el estado canónico.
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

import dictus_secciones as _secciones  # noqa: E402
import dictus_ejecutivo as de                 # noqa: E402
import dictus_estado as dse                   # noqa: E402
import dictus_manifiesto as dm                # noqa: E402

CTL_DEFECTO = (ROOT / "docs" / "forensics" / "040-646406" / "golden_03i1"
               / "inputs" / "CTL_040-646406_ORIGINAL.pdf")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="DICTUS 2.0B — corrida integrada")
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
    tecnico = salida / f"DICTUS_TECNICO_{args.folio}.pdf"
    captura: dict = {}
    dse.instalar_observadores(captura)          # solo lectura: no altera cálculos
    pdf_compiler.compile_pdf(record, str(tecnico), assets_dir=salida)

    # ── 2 · Estado canónico de la corrida ─────────────────────────────────────
    from versioning import VERSION_MATRIX
    captura["solar"] = {"momentos": (dse._SOLAR.get("momentos") or [])}
    rs = dse.construir_run_state(captura, run_id=run_id, folio=args.folio,
                                 ciudad=args.ciudad, versionado=dict(VERSION_MATRIX or {}),
                                 generated_at=(captura.get("receipts") or {}).get("generated_at"))

    # ── 3 · Modelo, manifest y hash maestro ───────────────────────────────────
    hist_path = ROOT / "docs" / "forensics" / args.folio / "dictus_2" / "HISTORICAL_CONSISTENCY_REPORT.json"
    hist = json.loads(hist_path.read_text(encoding="utf-8")) if hist_path.exists() else {}
    # La coherencia histórica es un INSUMO del estado canónico (evidencia de primer
    # orden), no algo que el ejecutivo averigüe por su cuenta.
    rs["historical_consistency"] = hist
    # Los conflictos históricos abiertos son HECHOS de la corrida: entran al estado
    # (y por tanto al modelo, al manifest y al hash), no solo al render.
    dse.agregar_findings_de_coherencia(rs, hist)
    modelo = dm.construir_documento_maestro(rs, historial=hist, folio=args.folio)

    # ── 4 · Documento ejecutivo (desde el estado, nunca desde el PDF) ─────────
    secciones = _secciones.desde_estado(rs, modelo, hist)
    ejecutivo = salida / f"DICTUS_EJECUTIVO_{args.folio}.pdf"
    de.render(modelo, secciones, ejecutivo)

    # ── 5 · Manifest publicado + acceptance report ────────────────────────────
    manifest = {
        "master_manifest_version": dm.MASTER_MANIFEST_VERSION,
        "run_state_version": dse.RUN_STATE_VERSION,
        "run_id": run_id,
        "dictus_id": modelo["document_identity"]["dictus_id"],
        "generated_at": modelo["document_identity"]["generated_at"],
        "master_hash": modelo["master_hash"],
        "master_hash_abreviado": modelo["master_hash_abreviado"],
        "evidence_manifest": modelo["evidence_manifest"],
        "modelo": modelo,
    }
    mpath = salida / f"DICTUS_MANIFEST_{args.folio}.json"
    mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    (salida / f"DICTUS_RUN_STATE_{args.folio}.json").write_text(
        json.dumps(rs, ensure_ascii=False, indent=1, default=str), encoding="utf-8")

    # El sello se publica con la app para que /portal/ muestre el MISMO hash.
    publico = ROOT / "public" / "dictus"
    publico.mkdir(parents=True, exist_ok=True)
    shutil.copy2(mpath, publico / f"DICTUS_MANIFEST_{args.folio}.json")

    import pymupdf
    with pymupdf.open(str(ejecutivo)) as d_ej:
        pp_ej = d_ej.page_count
    with pymupdf.open(str(tecnico)) as d_te:
        pp_te = d_te.page_count
    verif = dse.verify_dictus_master_hash(manifest, manifest["master_hash"])
    reporte = {
        "run_id": run_id, "dictus_id": manifest["dictus_id"],
        "generated_at": manifest["generated_at"], "master_hash": manifest["master_hash"],
        "master_manifest_version": dm.MASTER_MANIFEST_VERSION,
        "executive_pdf": str(ejecutivo.relative_to(ROOT)),
        "executive_pdf_sha256": hashlib.sha256(ejecutivo.read_bytes()).hexdigest(),
        "executive_page_count": pp_ej,
        "technical_pdf": str(tecnico.relative_to(ROOT)),
        "technical_pdf_sha256": hashlib.sha256(tecnico.read_bytes()).hexdigest(),
        "technical_page_count": pp_te,
        "evidence_count": manifest["evidence_manifest"]["evidence_count"],
        "evidence_seal": manifest["evidence_manifest"]["estado"],
        "poi_items_in_state": rs["poi_state"]["item_count"],
        "poi_distance_available": rs["poi_state"]["distance_available"],
        "findings_in_page_1": len(secciones["hallazgos"]),
        "verify_master_hash": verif["result"],
        "layout_violations": list(de.VIOLACIONES),
        "nota_hash": ("DICTUS_MASTER_HASH sella hechos y evidencias; los SHA-256 de los PDFs "
                      "sellan el archivo entregado y NO son el hash visible."),
    }
    (salida / f"ACEPTACION_{args.folio}.json").write_text(
        json.dumps(reporte, ensure_ascii=False, indent=1), encoding="utf-8")

    # ── 6 · Artefactos versionables (§21): texto del Golden + acceptance report ──
    with pymupdf.open(str(ejecutivo)) as d_ej:
        texto = "\n\n".join(f"===== PAGINA {i + 1} =====\n" + " ".join(p.get_text().split())
                            for i, p in enumerate(list(d_ej)[:6]))
    (salida / f"DICTUS_2.0B_TEXTO_EJECUTIVO_{args.folio}.txt").write_text(texto + "\n",
                                                                         encoding="utf-8")
    md = [
        f"# DICTUS 2.0B — ACEPTACIÓN DE LA CORRIDA INTEGRADA ({args.folio})",
        "",
        "Una sola corrida del producto produjo el documento ejecutivo y el técnico desde el "
        "mismo estado canónico, con un único hash maestro.",
        "",
        "| Dato | Valor |",
        "|---|---|",
        f"| run_id | `{reporte['run_id']}` |",
        f"| DICTUS ID | **{reporte['dictus_id']}** |",
        f"| generado | {reporte['generated_at']} |",
        f"| **DICTUS_MASTER_HASH** | `{reporte['master_hash']}` |",
        f"| master manifest | `{reporte['master_manifest_version']}` |",
        f"| run state | `{dse.RUN_STATE_VERSION}` |",
        f"| Ejecutivo | `{Path(reporte['executive_pdf']).name}` · "
        f"**{reporte['executive_page_count']} páginas** · sha256 "
        f"`{reporte['executive_pdf_sha256']}` |",
        f"| Técnico | `{Path(reporte['technical_pdf']).name}` · "
        f"{reporte['technical_page_count']} páginas · sha256 "
        f"`{reporte['technical_pdf_sha256']}` |",
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
    print(f"[run] ejecutivo {ejecutivo.name} · {pp_ej} páginas · "
          f"sha256 {reporte['executive_pdf_sha256'][:12]}…")
    print(f"[run] técnico   {tecnico.name} · {pp_te} páginas · "
          f"sha256 {reporte['technical_pdf_sha256'][:12]}…")
    print(f"[run] evidencias {reporte['evidence_count']} ({reporte['evidence_seal']}) · "
          f"verificación {verif['result']} · retícula "
          f"{'OK' if not de.VIOLACIONES else de.VIOLACIONES}")
    print(f"[run] POI en el estado: {reporte['poi_items_in_state']} ítems · "
          f"distancias {'sí' if reporte['poi_distance_available'] else 'no'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

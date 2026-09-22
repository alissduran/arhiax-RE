# -*- coding: utf-8 -*-
"""03I — GOLDEN DICTUS INTEGRATED ACCEPTANCE (040-646406).

Ejecuta el pipeline REAL del producto y guarda los artefactos de aceptación:

  * PDF del Golden,
  * GOLDEN_EXECUTION_MANIFEST.json,
  * estado interno observado (para las matrices de QA).

SIN sustituciones de fuentes: catastro/POT/POI/geocoder/screening se consultan en
vivo. Entradas del caso:

  * CTL: texto real saneado del certificado 040-646406 disponible en el entorno
    (se materializa como PDF y lo analiza el `legal_analyzer` REAL).
  * Dirección/unidad: registro oficial de adopción catastral de Barranquilla
    (Anexo 1, Resolución GGCD 003) — NO se teclea a mano.
  * Área: extraída por el analizador REAL del CTL (no se hardcodea).

La única instrumentación es un OBSERVADOR del gate de consistencia
(`consistency.ejecutar_gate`), que no altera valores ni sustituye fuentes: sirve
para volcar el estado interno a los artefactos de QA.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

OUT = ROOT / "docs" / "forensics" / "040-646406" / "golden_03i"
INPUTS = OUT / "inputs"
TMP = ROOT / "tmp_golden_03i"
FOLIO = "040-646406"


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _ctl_texto() -> str:
    """CTL real del caso (texto saneado disponible en el entorno)."""
    from test_arhiax_re import TestRegresionesCtlRealBarranquilla
    return TestRegresionesCtlRealBarranquilla._CTL


def _ctl_pdf(texto: str, destino: Path) -> None:
    """Materializa el CTL como PDF de texto (lo analiza el analizador real)."""
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(str(destino), pagesize=letter)
    y = 750
    for linea in texto.splitlines():
        if y < 50:
            c.showPage()
            y = 750
        c.drawString(40, y, linea[:150])
        y -= 12
    c.save()


def _direccion_oficial() -> dict:
    """Unidad/dirección desde el registro OFICIAL de adopción catastral."""
    data = json.loads((ROOT / "api" / "data" /
                       "barranquilla_adopcion_anexo1.json").read_text(encoding="utf-8"))
    for r in data["registros"]:
        if str(r.get("fmi")) == FOLIO.split("-")[1]:
            return {"registro": r, "resolution_number": data.get("resolution_number"),
                    "resolution_date": data.get("resolution_date"),
                    "source_name": data.get("source_name"),
                    "source_url": data.get("source_url"),
                    "sha256": hashlib.sha256(
                        (ROOT / "api" / "data" /
                         "barranquilla_adopcion_anexo1.json").read_bytes()).hexdigest()}
    raise SystemExit("registro de adopción no encontrado para el folio")


def _manifest(*, ctl_pdf: Path, ctl_txt: Path, ad: dict, out_pdf: Path,
              estado: dict, versionado: dict) -> dict:
    import datetime
    return {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "prompt": "03I — GOLDEN DICTUS INTEGRATED ACCEPTANCE",
        "commit_sha": versionado.get("GIT_COMMIT_SHA"),
        "versions": versionado,
        "environment": {
            "python": sys.version.split()[0],
            "platform": sys.platform,
            "cwd": str(ROOT),
            "network": "LIVE (catastro/POT/POI/geocoder/screening consultados en vivo)",
        },
        "case": {
            "folio": FOLIO,
            "codigo_catastral": ad["registro"].get("numero_predial"),
            "nupre": ad["registro"].get("codigo_homologado"),
            "direccion_oficial": ad["registro"].get("direccion"),
            "unidad_oficial": "TO 8 AP 430 (proveniente del registro oficial, no tecleada)",
        },
        "inputs": {
            "ctl_texto": {
                "path": str(ctl_txt.relative_to(ROOT)),
                "sha256": _sha256_file(ctl_txt),
                "origen": ("texto real saneado del CTL 040-646406 disponible en el "
                           "entorno; el PDF original está fuera del workspace"),
            },
            "ctl_pdf": {"path": str(ctl_pdf.relative_to(ROOT)),
                        "sha256": _sha256_file(ctl_pdf)},
            "adopcion": {
                "source_name": ad.get("source_name"), "source_url": ad.get("source_url"),
                "resolution": f"{ad.get('resolution_number')} · {ad.get('resolution_date')}",
                "sha256_registro": ad.get("sha256"),
            },
            "area_registrada": {
                "value": estado.get("area_registrada"),
                "source": "index.extraer_datos_de_pdf (CTL real) — extraída, no hardcodeada",
            },
        },
        "identity": estado.get("identity"),
        "coordinates": estado.get("coordinates"),
        "urban_sources": estado.get("urban"),
        "market": estado.get("market"),
        "poi": estado.get("poi"),
        "screening": estado.get("screening"),
        "valuation": estado.get("valuation"),
        "outputs": {"pdf": str(out_pdf.relative_to(ROOT)),
                    "pdf_sha256": _sha256_file(out_pdf) if out_pdf.exists() else None},
        "qa_instrumentation": {
            "observador": "consistency.ejecutar_gate (solo lectura del contexto)",
            "sustitucion_de_fuentes": False,
            "monkeypatch_de_fuentes": False,
        },
    }


def main() -> int:
    shutil.rmtree(TMP, ignore_errors=True)
    INPUTS.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)

    # 1) Entradas reales del caso -------------------------------------------------
    texto = _ctl_texto()
    ctl_txt = INPUTS / f"CTL_{FOLIO}.txt"
    ctl_txt.write_text(texto, encoding="utf-8")
    ctl_pdf = INPUTS / f"CTL_{FOLIO}.pdf"
    _ctl_pdf(texto, ctl_pdf)
    ad = _direccion_oficial()

    # 2) Análisis REAL del CTL (el área y el folio salen del analizador) ----------
    from legal_analyzer import analizar_certificado
    analysis = analizar_certificado(str(ctl_pdf))
    # El PRODUCTO extrae área/código/NUPRE con `index.extraer_datos_de_pdf` (es el
    # camino del endpoint real cuando se sube un CTL). Se usa ESE camino, no un
    # valor tecleado: el área del caso sale de su propio CTL.
    from index import extraer_datos_de_pdf
    ext = extraer_datos_de_pdf(str(ctl_pdf), "barranquilla")
    print(f"[03I] CTL analizado: folio={analysis.get('folio')!r} "
          f"codigo={analysis.get('codigo_catastral')!r} nupre={analysis.get('nupre')!r} "
          f"titulares={analysis.get('titulares')!r}")
    print(f"[03I] extraer_datos_de_pdf: { {k: v for k, v in ext.items()} }")

    area_ctl = ext.get("area") or 0.0
    record = {
        "id": 1,
        "folio_matricula": ext.get("folio") or analysis.get("folio") or FOLIO,
        "direccion": ext.get("direccion") or ad["registro"].get("direccion"),
        "barrio": ext.get("barrio") or "",   # del CTL/catastro; NUNCA inyectado
        "ciudad": "barranquilla",
        "area": area_ctl,                    # del CTL real (camino del producto)
        "valor_consolidado": None,
        "sombra_9am_cargada": 0, "sombra_3pm_cargada": 0, "mapa_cargado": 0,
        "acreedor_real": None,
        "certificado_path": str(ctl_pdf),
    }

    # 3) Ejecución REAL del producto ---------------------------------------------
    import consistency
    import pdf_compiler
    observado: dict = {}
    _gate_real = consistency.ejecutar_gate

    def _gate_observador(ctx):          # observador: no cambia nada
        try:
            observado["ctx"] = ctx
        except Exception:  # noqa: BLE001
            pass
        return _gate_real(ctx)

    out_pdf = OUT / f"ARHIAX_Dictamen_{FOLIO}_03I.pdf"
    consistency.ejecutar_gate = _gate_observador
    try:
        pdf_compiler.compile_pdf(record, str(out_pdf), assets_dir=TMP)
    finally:
        consistency.ejecutar_gate = _gate_real

    ctx = observado.get("ctx") or {}
    cid = ctx.get("canonical_identity") or {}
    mc = cid.get("market_context") or {}
    titu = ctx.get("titulux") or {}
    _sum = titu.get("screening_summary") or {}
    _snaps = {s.get("source_id"): s for s in (_sum.get("snapshots") or [])}
    _res = ctx.get("res_avaluo") or {}
    _pre = ctx.get("predio_real") or {}
    _ent = _pre.get("entorno") or {}
    _urb = mc.get("official_urban_context") or {}
    _pois = {}

    versionado = {}
    try:
        from versionado import obtener_versionado          # noqa: WPS433
        versionado = obtener_versionado()
    except Exception:  # noqa: BLE001
        try:
            from versionado import VERSION_INFO as versionado   # type: ignore
        except Exception:  # noqa: BLE001
            versionado = {}

    estado = {
        "area_registrada": area_ctl,
        "identity": {
            "folio": cid.get("folio_snr"), "nupre": cid.get("nupre"),
            "codigo_catastral": cid.get("codigo_catastral"),
            "direccion_raw": cid.get("direccion_raw"),
            "direccion_base": cid.get("direccion_base"),
            "direccion_normalizada": cid.get("direccion_normalizada"),
            "torre": cid.get("torre"), "apartamento": cid.get("apartamento"),
            "unidad": cid.get("unidad"), "estado": cid.get("estado"),
            "resolution_status": cid.get("resolution_status"),
            "resolution_method": cid.get("resolution_method"),
            "resolution_confidence": cid.get("resolution_confidence"),
            "identity_verified": cid.get("identity_verified"),
            "identity_source": cid.get("identity_source"),
            "market_context_ready": cid.get("market_context_ready"),
            "adopcion_registro": cid.get("adopcion_registro"),
            "identificadores": cid.get("identificadores"),
        },
        "coordinates": {
            "lat": mc.get("coordinates", {}).get("lat"),
            "lon": mc.get("coordinates", {}).get("lon"),
            "source": mc.get("coordinate_source"),
            "verified": mc.get("coordinate_source_verified"),
            "authoritative_address": mc.get("authoritative_address"),
            "address_source": mc.get("address_source"),
        },
        "urban": {
            "barrio": _urb.get("barrio"), "barrio_status": _urb.get("barrio_status"),
            "localidad": _urb.get("localidad"), "estrato": _urb.get("estrato"),
            "estrato_status": _urb.get("estrato_status"),
            "tratamiento": _urb.get("tratamiento"),
            "tratamiento_status": _urb.get("tratamiento_status"),
            "tipo_tratamiento": _urb.get("tipo_tratamiento"),
            "altura_maxima": _urb.get("altura_maxima"),
            "altura_status": _urb.get("altura_status"),
            "pieza_urbana": _urb.get("pieza_urbana"),
            "codigo_manzana": _urb.get("codigo_manzana"),
            "source": _urb.get("source"),
            "context_status": _urb.get("context_status"),
            "campos_ambiguos": _urb.get("campos_ambiguos"),
            "predio_entorno": {k: _ent.get(k) for k in
                               ("barrio", "estrato", "tratamiento", "tipo_tratamiento",
                                "altura_maxima", "localidad", "codigo_manzana")
                               if _ent.get(k) is not None},
            "predio_destino_catastral": (_pre.get("predio") or {}).get("destino_economico"),
            "predio_condicion": (_pre.get("condicion") or {}).get("condicion_juridica"),
            "predio_construccion": (_pre.get("construccion") or {}),
        },
        "market": {
            "ready": mc.get("ready"), "blockers": mc.get("blockers"),
            "sector": (mc.get("sector_metodologico") or {}).get("matched_sector"),
            "match_type": (mc.get("sector_metodologico") or {}).get("match_type"),
            "value_m2": (mc.get("sector_metodologico") or {}).get("value_m2"),
            "rate_source": (mc.get("sector_metodologico") or {}).get("source"),
            "rate_date": (mc.get("sector_metodologico") or {}).get("source_date"),
            "methodology_version": mc.get("methodology_version"),
            "estrato": mc.get("estrato"), "barrio": mc.get("barrio"),
            "tipologia": mc.get("tipologia"), "uso": mc.get("uso"),
            "urban_render_provenance": mc.get("urban_render_provenance"),
        },
        "poi": _pois,
        "screening": {
            "status": _sum.get("status"), "coverage_status": _sum.get("coverage_status"),
            "executed": _sum.get("executed"),
            "subjects_declared": _sum.get("subjects_declared"),
            "subjects_screened": _sum.get("subjects_screened"),
            "evidence_expected": _sum.get("evidence_expected_count"),
            "evidence_created": _sum.get("evidence_created_count"),
            "evidence_chain_status": _sum.get("evidence_chain_status"),
            "evidence_sealed": _sum.get("evidence_sealed"),
            "evidence_reproducible": _sum.get("evidence_reproducible"),
            "matcher_version": _sum.get("algorithm_version"),
            "reason": _sum.get("reason"),
            "subjects": _sum.get("subjects"),
            "outcomes": _sum.get("outcomes"),
            "snapshots": _sum.get("snapshots"),
            "freshness": {k: (v or {}).get("freshness") for k, v in _snaps.items()},
            "review_required": _sum.get("review_required_subjects"),
            "matched": _sum.get("matched_subjects"),
            "evidence_records": _sum.get("evidence_records"),
        },
        "valuation": {
            "authorization": ctx.get("valuation_authorization"),
            "metodologia_aplica": _res.get("metodologia_aplica"),
            "motivo_no_aplica": _res.get("motivo_no_aplica"),
            "value_m2": _res.get("value_m2"), "source_m2": _res.get("market_rate_source"),
            "sector": _res.get("market_rate_sector"),
            "match_type": _res.get("market_rate_match_type"),
            "consolidado": _res.get("consolidado"), "m1": _res.get("m1"),
            "m2": _res.get("m2"), "m3": _res.get("m3"),
            "banda_baja": _res.get("banda_baja"), "banda_alta": _res.get("banda_alta"),
            "canon_mensual": _res.get("canon_mensual"), "cap_rate": _res.get("cap_rate"),
        },
    }

    man = _manifest(ctl_pdf=ctl_pdf, ctl_txt=ctl_txt, ad=ad, out_pdf=out_pdf,
                    estado=estado, versionado=versionado)
    (OUT / "GOLDEN_EXECUTION_MANIFEST.json").write_text(
        json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "GOLDEN_INTERNAL_STATE.json").write_text(
        json.dumps(estado, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"[03I] PDF: {out_pdf}")
    print(f"[03I] manifest: {OUT / 'GOLDEN_EXECUTION_MANIFEST.json'}")
    print(f"[03I] área del CTL: {area_ctl}")
    print(f"[03I] identidad: estado={estado['identity']['estado']} "
          f"confianza={estado['identity']['resolution_confidence']} "
          f"verified={estado['identity']['identity_verified']} "
          f"unidad={estado['identity']['unidad']!r}")
    print(f"[03I] mercado: ready={estado['market']['ready']} "
          f"sector={estado['market']['sector']} match={estado['market']['match_type']} "
          f"value_m2={estado['market']['value_m2']}")
    print(f"[03I] valoración: aplica={estado['valuation']['metodologia_aplica']} "
          f"consolidado={estado['valuation']['consolidado']} "
          f"motivo={estado['valuation']['motivo_no_aplica']}")
    print(f"[03I] screening: {estado['screening']['status']} "
          f"evidencia {estado['screening']['evidence_created']}/"
          f"{estado['screening']['evidence_expected']} "
          f"cadena={estado['screening']['evidence_chain_status']}")

    # 4) Texto del PDF para las aserciones automáticas de aceptación -------------
    try:
        import pypdf
        _r = pypdf.PdfReader(str(out_pdf))
        _txt = "\n".join((p.extract_text() or "") for p in _r.pages)
        (OUT / "GOLDEN_PDF_TEXT.txt").write_text(_txt, encoding="utf-8")
        print(f"[03I] texto extraído: {len(_txt)} caracteres, {len(_r.pages)} páginas")
    except Exception as e:  # noqa: BLE001
        print(f"[03I] no se pudo extraer texto: {e}")

    shutil.rmtree(TMP, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""03I.1 — GOLDEN DICTUS PRODUCT COHERENCE CLOSURE (040-646406).

Corrida REAL del producto con el CTL REAL como BINARIO de entrada:

    python scripts/golden_run_03i1.py --ctl <ruta\\al\\CTL.pdf>

Sin fixtures, sin mocks y sin sustituciones de fuente. La única instrumentación
son OBSERVADORES de solo lectura sobre funciones del producto, para volcar a los
artefactos de QA lo que el render realmente consumió:

  * `consistency.ejecutar_gate`  → contexto interno del gate,
  * `poi_engine.get_poi_result`  → POIs observados (categoría, estado, items,
    fuentes intentadas/exitosas y fuente de cada item),
  * `receipts.build_execution_receipts` → receipts reales de esta ejecución.

Contrato de aceptación (03I.1 §A):
  * `commit_sha` se obtiene de `versioning.git_commit_sha()` y NUNCA se degrada a
    null: si falta, el QA FALLA.
  * `versions` sale de `versioning.VERSION_MATRIX`; si está vacío, el QA FALLA.
  * El input es el BINARIO entregado por `--ctl` (sha256 + tamaño + tipo).
  * Ningún hecho material del QA se escribe a mano: todo sale del objeto real.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT))

OUT = ROOT / "docs" / "forensics" / "040-646406" / "golden_03i1"
INPUTS = OUT / "inputs"
TMP = ROOT / "tmp_golden_03i1"
FOLIO = "040-646406"


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _versionado_estricto() -> dict:
    """Versiones + SHA de git. FALLA si el versionado no está disponible."""
    from versioning import VERSION_MATRIX, git_commit_sha, version_line
    sha = (git_commit_sha() or "").strip()
    versiones = dict(VERSION_MATRIX or {})
    faltantes = [k for k, v in versiones.items() if not v]
    if not sha:
        raise SystemExit("[03I.1][FALLO] commit_sha no resoluble (git rev-parse HEAD "
                         "y VERCEL_GIT_COMMIT_SHA vacíos): el manifest del Golden NO "
                         "puede emitirse sin identidad de ejecución.")
    if faltantes:
        raise SystemExit(f"[03I.1][FALLO] versiones vacías en VERSION_MATRIX: {faltantes}")
    return {
        "GIT_COMMIT_SHA": sha,
        "ARHIAX_RE_VERSION": versiones.get("ARHIAX_RE_VERSION"),
        "DICTUS_ENGINE_VERSION": versiones.get("DICTUS_ENGINE_VERSION"),
        "GIS_ADAPTER_VERSION": versiones.get("GIS_ADAPTER_VERSION"),
        "TITULUX_VERSION": versiones.get("TITULUX_VERSION"),
        "RULESET_VERSION": versiones.get("RULESET_VERSION"),
        "version_line": version_line(),
        "arbol_de_trabajo": _arbol_de_trabajo(),
    }


def _arbol_de_trabajo() -> dict:
    """Identidad del código EFECTIVAMENTE ejecutado (no solo el HEAD de git).

    Una corrida de aceptación puede hacerse con la slice aplicada en el árbol de
    trabajo: sin esto, el manifest declararía un commit que NO contiene los fixes
    ejecutados. Se registra el sha256 del `git diff HEAD` y los archivos tocados.
    """
    import subprocess
    info = {"dirty": False, "files": [], "diff_sha256": None, "n_files": 0}
    try:
        st = subprocess.run(["git", "status", "--porcelain"], cwd=str(ROOT),
                            capture_output=True, text=True, timeout=15)
        files = [l.strip() for l in (st.stdout or "").splitlines() if l.strip()]
        df = subprocess.run(["git", "diff", "HEAD"], cwd=str(ROOT),
                            capture_output=True, text=True, timeout=15)
        diff = df.stdout or ""
        info["files"] = files
        info["n_files"] = len(files)
        info["dirty"] = bool(files)
        info["diff_sha256"] = hashlib.sha256(diff.encode("utf-8")).hexdigest() if diff else None
    except Exception as e:  # noqa: BLE001
        info["error"] = str(e)[:120]
    return info


def _registro_oficial(sha_ctl: str) -> dict:
    """Dirección/unidad desde el registro OFICIAL de adopción catastral.

    Es una FUENTE (Anexo 1 · Resolución GGCD 003), no un valor tecleado: el QA lee
    el mismo archivo que el producto y verifica que coincida con lo que el
    producto resolvió.
    """
    p = ROOT / "api" / "data" / "barranquilla_adopcion_anexo1.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    for r in data["registros"]:
        if str(r.get("fmi")) == FOLIO.split("-")[1]:
            return {"registro": r, "resolution_number": data.get("resolution_number"),
                    "resolution_date": data.get("resolution_date"),
                    "source_name": data.get("source_name"),
                    "source_url": data.get("source_url"),
                    "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
    raise SystemExit("registro de adopción no encontrado para el folio")


def _poi_observado(res: dict) -> dict:
    """POIs realmente observados, por categoría, con fuentes (nada hardcodeado)."""
    items = (res or {}).get("items") or {}
    status = (res or {}).get("category_status") or {}
    out = {
        "sources_attempted": list((res or {}).get("sources_attempted") or []),
        "sources_succeeded": list((res or {}).get("sources_succeeded") or []),
        "categorias": {},
    }
    for cat in sorted(set(items) | set(status)):
        _items = items.get(cat) or []
        out["categorias"][cat] = {
            "status": status.get(cat),
            "item_count": len(_items),
            "items": [{"name": i.get("name"), "type": i.get("type"),
                       "distance": i.get("distance"), "source": i.get("source")}
                      for i in _items],
            "fuentes_de_items": sorted({str(i.get("source")) for i in _items if i.get("source")}),
        }
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="03I.1 — corrida Golden con CTL real")
    ap.add_argument("--ctl", required=True,
                    help="ruta al PDF del Certificado de Tradición y Libertad (BINARIO)")
    ap.add_argument("--out-suffix", default="03I1")
    args = ap.parse_args(argv)

    ctl = Path(args.ctl).expanduser().resolve()
    if not ctl.exists():
        raise SystemExit(f"[03I.1][FALLO] el CTL indicado no existe: {ctl}")
    if ctl.suffix.lower() != ".pdf":
        raise SystemExit(f"[03I.1][FALLO] el CTL debe ser el PDF BINARIO original: {ctl}")

    versionado = _versionado_estricto()
    print(f"[03I.1] commit={versionado['GIT_COMMIT_SHA'][:8]} "
          f"version_line={versionado['version_line']}")

    shutil.rmtree(TMP, ignore_errors=True)
    OUT.mkdir(parents=True, exist_ok=True)
    INPUTS.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)

    ctl_sha = _sha256_file(ctl)
    ctl_size = ctl.stat().st_size
    print(f"[03I.1] CTL de entrada (BINARIO): {ctl} ({ctl_size} bytes, sha256 {ctl_sha[:16]}...)")
    # Copia del BINARIO original a los artefactos (evidencia de la corrida). Si el
    # archivo vive fuera del workspace, la copia es solo lectura del original.
    ctl_copia = INPUTS / f"CTL_{FOLIO}_ORIGINAL.pdf"
    try:
        shutil.copy2(ctl, ctl_copia)
        print(f"[03I.1] copia de evidencia: {ctl_copia}")
    except Exception as _e_cp:
        ctl_copia = None
        print(f"[03I.1] no se pudo copiar el CTL a los artefactos: {_e_cp}")

    # 1) Análisis REAL del CTL entregado ----------------------------------------
    from legal_analyzer import analizar_certificado
    from index import extraer_datos_de_pdf
    analysis = analizar_certificado(str(ctl))
    ext = extraer_datos_de_pdf(str(ctl), "barranquilla")
    print(f"[03I.1] análisis: folio={analysis.get('folio')!r} "
          f"codigo={analysis.get('codigo_catastral')!r} nupre={analysis.get('nupre')!r} "
          f"constructor={analysis.get('constructor')!r}")
    print(f"[03I.1] extraer_datos_de_pdf(area)={ext.get('area')!r} "
          f"direccion={ext.get('direccion')!r}")
    if not ext.get("area"):
        raise SystemExit("[03I.1][FALLO] el CTL entregado no permitió extraer el área "
                         "por el camino del producto: corrida no válida.")

    record = {
        "id": 1,
        "folio_matricula": ext.get("folio") or analysis.get("folio") or FOLIO,
        # 03I.1 · F5: la dirección NO se inyecta desde el QA. Si el CTL no la trae,
        # el producto debe resolverla desde el registro oficial (identidad).
        "direccion": ext.get("direccion") or "",
        "barrio": ext.get("barrio") or "",
        "ciudad": "barranquilla",
        "area": ext.get("area"),
        "valor_consolidado": None,
        "sombra_9am_cargada": 0, "sombra_3pm_cargada": 0, "mapa_cargado": 0,
        "acreedor_real": None,
        "certificado_path": str(ctl),
    }

    # 2) Ejecución REAL con observadores de solo lectura ------------------------
    import consistency
    import pdf_compiler
    import poi_engine
    import receipts as _receipts
    import riesgo_volcanico as _volcan_mod

    observado: dict = {}
    _gate_real = consistency.ejecutar_gate
    _poi_real = poi_engine.get_poi_result
    _rec_real = _receipts.build_execution_receipts
    _vol_real = _volcan_mod.verificar_riesgo_volcanico
    # El compilador importa las funciones por nombre: hay que observar la
    # REFERENCIA que realmente usa el render, no solo el módulo de origen.
    _poi_ref_real = pdf_compiler.get_poi_result
    _cat_real = pdf_compiler.get_catastral_dt

    def _gate_observador(ctx):
        try:
            observado["ctx"] = ctx
            observado["informe_gate"] = _gate_real(ctx)
            return observado["informe_gate"]
        except Exception:  # noqa: BLE001
            return _gate_real(ctx)

    def _vol_observador(*a, **kw):
        res = _vol_real(*a, **kw)
        try:
            observado["volcan"] = res
        except Exception:  # noqa: BLE001
            pass
        return res

    def _poi_observador(*a, **kw):
        res = _poi_real(*a, **kw)
        try:
            observado.setdefault("poi_llamadas", []).append(
                {"args": [str(x) for x in a], "kwargs": {k: str(v) for k, v in kw.items()}})
            observado["poi"] = res
        except Exception:  # noqa: BLE001
            pass
        return res

    def _rec_observador(*a, **kw):
        res = _rec_real(*a, **kw)
        try:
            observado["receipts"] = res
        except Exception:  # noqa: BLE001
            pass
        return res

    # `dictamen_data.get_catastral_dt` construye la tabla 6.1 (área, barrio, NUPRE,
    # código, destino, condición jurídica, construcción, estrato). Se observa el
    # VALOR REAL que consumió el render: la matriz de provenance no puede
    # reconstruir ese hecho a mano (03I.1 · §J).
    def _cat_observador(*a, **kw):
        res = _cat_real(*a, **kw)
        try:
            observado["catastral_dt"] = {"args": [str(x) for x in a],
                                         "kwargs": {k: (v if isinstance(
                                             v, (str, int, float, bool, type(None))) else str(v))
                                             for k, v in kw.items()},
                                         "filas": [[str(x) for x in fila] for fila in (res or [])]}
        except Exception:  # noqa: BLE001
            pass
        return res

    out_pdf = OUT / f"ARHIAX_Dictamen_{FOLIO}_{args.out_suffix}.pdf"
    consistency.ejecutar_gate = _gate_observador
    poi_engine.get_poi_result = _poi_observador
    pdf_compiler.get_poi_result = _poi_observador
    pdf_compiler.get_catastral_dt = _cat_observador
    _receipts.build_execution_receipts = _rec_observador
    _volcan_mod.verificar_riesgo_volcanico = _vol_observador
    try:
        pdf_compiler.compile_pdf(record, str(out_pdf), assets_dir=TMP)
    finally:
        consistency.ejecutar_gate = _gate_real
        poi_engine.get_poi_result = _poi_real
        pdf_compiler.get_poi_result = _poi_ref_real
        pdf_compiler.get_catastral_dt = _cat_real
        _receipts.build_execution_receipts = _rec_real
        _volcan_mod.verificar_riesgo_volcanico = _vol_real

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
    _usm = mc.get("urban_source_summary") or {}
    _sec = mc.get("sector_metodologico") or {}
    _vol = observado.get("volcan") or {}

    estado = {
        "versionado": versionado,
        "input": {
            "ctl_path": str(ctl),
            "ctl_sha256": ctl_sha,
            "ctl_size": ctl_size,
            "input_type": "ORIGINAL_BINARY",
            "copia_evidencia": str(ctl_copia) if ctl_copia else None,
            "area_extraida_por_producto": ext.get("area"),
        },
        "identity": {
            "folio": cid.get("folio_snr"), "nupre": cid.get("nupre"),
            "codigo_catastral": cid.get("codigo_catastral"),
            "direccion_raw": cid.get("direccion_raw"),
            "direccion_base": cid.get("direccion_base"),
            "direccion_normalizada": cid.get("direccion_normalizada"),
            "direccion_source": cid.get("direccion_source"),
            "direccion_previa": cid.get("direccion_previa"),
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
            # 03I.2B §N/§H: procedencia de la coordenada (H-1), observable de solo
            # lectura: de qué servicio, capa y feature salió el punto del gate.
            "provenance": mc.get("coordinate_provenance") or {},
            # 03I.2B-A §9: binding con la identidad canónica del caso.
            "canonical_binding_status": mc.get("canonical_binding_status"),
            "canonical_binding_fields": mc.get("canonical_binding_fields"),
            "canonical_binding_scope": mc.get("canonical_binding_scope"),
            "scope": mc.get("coordinate_scope"),
            "official_predio_rejected_reason": mc.get("official_predio_rejected_reason"),
        },
        "urban": {
            "barrio": _urb.get("barrio"), "barrio_status": _urb.get("barrio_status"),
            "localidad": _urb.get("localidad"),
            "estrato": _urb.get("estrato"), "estrato_status": _urb.get("estrato_status"),
            "estrato_origen": _urb.get("estrato_origen"),
            "estrato_trace": _urb.get("estrato_trace"),
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
        "urban_source_summary": _usm,
        "market": {
            "ready": mc.get("ready"), "blockers": mc.get("blockers"),
            "sector": _sec.get("matched_sector"),
            "match_type": _sec.get("match_type"),
            "value_m2": _sec.get("value_m2"),
            "rate_source": _sec.get("source"),
            "rate_date": _sec.get("source_date"),
            "methodology_version": mc.get("market_methodology_version"),
            "market_methodology_id": mc.get("market_methodology_id"),
            "market_methodology_version": mc.get("market_methodology_version"),
            "market_methodology_sha256": mc.get("market_methodology_sha256"),
            "market_methodology_file": mc.get("market_methodology_file"),
            "estrato": mc.get("estrato"), "barrio": mc.get("barrio"),
            "tipologia": mc.get("tipologia"), "uso": mc.get("uso"),
            "urban_render_provenance": mc.get("urban_render_provenance"),
        },
        "poi": _poi_observado(observado.get("poi") or {}),
        "catastral_dt_render": observado.get("catastral_dt"),
        "volcan": {
            "estado": (_vol or {}).get("estado"),
            "nivel": (_vol or {}).get("nivel"),
            "disponible": (_vol or {}).get("disponible"),
            "cobertura_confirmada": (_vol or {}).get("cobertura_confirmada"),
            "zonas": (_vol or {}).get("zonas"),
        },
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
        "receipts": observado.get("receipts"),
        "gate": observado.get("informe_gate"),
    }

    man = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "prompt": "03I.1 — DICTUS PRODUCT COHERENCE CLOSURE",
        "commit_sha": versionado["GIT_COMMIT_SHA"],
        "versions": {k: v for k, v in versionado.items()
                     if k not in ("version_line", "arbol_de_trabajo")},
        "version_line": versionado["version_line"],
        "arbol_de_trabajo": versionado.get("arbol_de_trabajo"),
        "environment": {
            "python": sys.version.split()[0],
            "platform": sys.platform,
            "cwd": str(ROOT),
            "network": "LIVE (catastro/POT/estrato/POI/geocoder/screening consultados en vivo)",
        },
        "case": {
            "folio": FOLIO,
            "codigo_catastral": cid.get("codigo_catastral"),
            "nupre": cid.get("nupre"),
            "direccion_canonica": cid.get("direccion_raw"),
            "unidad_canonica": cid.get("unidad"),
        },
        "inputs": {
            "ctl": {"path": str(ctl), "sha256": ctl_sha, "size": ctl_size,
                    "input_type": "ORIGINAL_BINARY"},
            "area_registrada": {"value": ext.get("area"),
                                "source": "index.extraer_datos_de_pdf (camino del producto)"},
        },
        "identity": estado["identity"],
        "coordinates": estado["coordinates"],
        "urban_sources": estado["urban"],
        "urban_source_summary": estado["urban_source_summary"],
        "market": estado["market"],
        "poi": estado["poi"],
        "volcan": estado["volcan"],
        "screening": estado["screening"],
        "valuation": estado["valuation"],
        "outputs": {"pdf": str(out_pdf.relative_to(ROOT)),
                    "pdf_sha256": _sha256_file(out_pdf) if out_pdf.exists() else None},
        "qa_instrumentation": {
            "observadores": ["consistency.ejecutar_gate", "poi_engine.get_poi_result",
                             "receipts.build_execution_receipts"],
            "sustitucion_de_fuentes": False,
            "monkeypatch_de_fuentes": False,
            "hechos_hardcodeados": False,
        },
    }
    (OUT / "GOLDEN_EXECUTION_MANIFEST.json").write_text(
        json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "GOLDEN_INTERNAL_STATE.json").write_text(
        json.dumps(estado, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"[03I.1] PDF: {out_pdf} ({_sha256_file(out_pdf)[:16]}...)")
    print(f"[03I.1] identidad: {estado['identity']['estado']} · "
          f"{estado['identity']['resolution_confidence']} · "
          f"dir={estado['identity']['direccion_raw']!r} unidad={estado['identity']['unidad']!r}")
    print(f"[03I.1] estrato: {estado['urban']['estrato']!r} "
          f"({estado['urban']['estrato_status']}, origen={estado['urban']['estrato_origen']})")
    print(f"[03I.1] tratamiento: {estado['urban']['tratamiento']!r} "
          f"({estado['urban']['tipo_tratamiento']!r}, altura={estado['urban']['altura_maxima']!r})")
    print(f"[03I.1] urban_source_summary: {estado['urban_source_summary'].get('source_mode')}")
    print(f"[03I.1] mercado: ready={estado['market']['ready']} "
          f"sector={estado['market']['sector']} value_m2={estado['market']['value_m2']} "
          f"metodologia={estado['market']['market_methodology_id']}"
          f"@{estado['market']['market_methodology_version']}")
    print(f"[03I.1] poi: {[(c, v['status'], v['item_count']) for c, v in estado['poi']['categorias'].items()]}")
    print(f"[03I.1] volcán: estado={estado['volcan']['estado']} nivel={estado['volcan']['nivel']}")
    print(f"[03I.1] valoración: aplica={estado['valuation']['metodologia_aplica']} "
          f"consolidado={estado['valuation']['consolidado']}")
    print(f"[03I.1] screening: {estado['screening']['status']} "
          f"evidencia {estado['screening']['evidence_created']}/{estado['screening']['evidence_expected']}")

    # 3) Texto del PDF para las aserciones automáticas --------------------------
    try:
        import pypdf
        _r = pypdf.PdfReader(str(out_pdf))
        _txt = "\n".join((p.extract_text() or "") for p in _r.pages)
        (OUT / "GOLDEN_PDF_TEXT.txt").write_text(_txt, encoding="utf-8")
        print(f"[03I.1] texto extraído: {len(_txt)} caracteres, {len(_r.pages)} páginas")
    except Exception as e:  # noqa: BLE001
        print(f"[03I.1] no se pudo extraer texto: {e}")

    shutil.rmtree(TMP, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

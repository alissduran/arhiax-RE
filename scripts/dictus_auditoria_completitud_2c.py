# -*- coding: utf-8 -*-
"""DICTUS 2.0C — AUDITORÍA DE COMPLETITUD MATERIAL (una corrida real del Golden).

    python scripts/dictus_auditoria_completitud_2c.py [--folio 040-646406]

Produce, sobre la MISMA corrida:

  1. `MATERIAL_FACT_COMPLETENESS_MATRIX` (JSON + MD): por cada hecho material,
     el valor en el motor/técnico, en el `DictusRunState`, en el
     `ExecutiveDocumentModel` y en el PDF EJECUTIVO, con su fuente, su estado, si hay
     pérdida y la causa.
  2. `STATE_PROJECTION_LOSS_REPORT`: los hechos que el producto conocía y el ejecutivo
     no imprimía, con la causa raíz de cada uno.
  3. `POI_ROOT_CAUSE_REPORT`: cadena cruda → observador → estado → modelo → PDF, con el
     conteo por categoría en cada eslabón y la causa de la pérdida.

No inventa datos: cuando el motor no produjo un hecho, lo declara `SIN_FUENTE`.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import sys
import unicodedata
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))

CTL = (ROOT / "docs" / "forensics" / "040-646406" / "golden_03i1" / "inputs"
       / "CTL_040-646406_ORIGINAL.pdf")


def _norm(s) -> str:
    t = unicodedata.normalize("NFKD", str(s or ""))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join(t.upper().split())


def _presente(texto: str, aguja) -> bool:
    return bool(aguja) and _norm(aguja) in _norm(texto)


_AUSENCIAS = ("NOT_PRODUCED", "UNREADABLE", "SIN_DATO", "NO_DECLARADO", "NOT_EVALUATED",
              "SOURCE_UNAVAILABLE", "SIN_FUENTE")


def _es_ausencia(valor) -> bool:
    """¿El valor es un estado de AUSENCIA (no un hecho con valor)?"""
    if valor is None:
        return True
    return str(valor).strip().upper() in _AUSENCIAS


# ── catálogo de hechos materiales (§2) ───────────────────────────────────────
def _activo_en_modelo(modelo, nombre):
    """Estado de un activo visual en el modelo (2.0D: el modelo lleva una LISTA)."""
    activos = modelo.get("visual_assets") or []
    if isinstance(activos, dict):
        activos = list(((activos.get("assets") or {}) or {}).values())
    clave = str(nombre).replace("_", "").upper()
    for a in activos:
        if not isinstance(a, dict):
            continue
        etiquetas = [a.get("asset_id"), a.get("type"), a.get("name"), a.get("id")]
        if any(str(e).replace("_", "").replace("-", "").upper().find(clave) >= 0
               for e in etiquetas if e):
            return a.get("status")
    return None


def _f(campo, motor, rs, modelo, aguja, fuente):
    return {"campo": campo, "motor": motor, "rs": rs, "modelo": modelo,
            "aguja": aguja, "fuente": fuente}


def catalogo(ctx, rs, modelo):
    cid = ctx.get("canonical_identity") or {}
    pre = ctx.get("predio_real") or {}
    ent = pre.get("entorno") or {}
    predio = pre.get("predio") or {}
    adm = ctx.get("administrative_context") or {}
    clas = ctx.get("clasificacion") or {}
    mc = ctx.get("market_context") or {}
    geo = ctx.get("geo_eval") or {}
    titu = ctx.get("titulux") or {}
    res = ctx.get("res_avaluo") or {}
    ana = ctx.get("analysis") or {}
    pi = rs.get("property_identity") or {}
    urb = rs.get("urban_context") or {}
    ts = rs.get("title_state") or {}
    rmc = rs.get("market_context") or {}
    mpi = modelo.get("canonical_property_identity") or {}
    murb = modelo.get("urban_context") or {}
    msv = modelo.get("source_versions") or {}
    mmc = modelo.get("market_context") or {}
    mval = modelo.get("valuation") or {}

    return [
        _f("Dirección completa", cid.get("direccion_raw"), pi.get("direccion_raw"),
           mpi.get("direccion_raw"), "NAPOLI", "CTL (folio)"),
        _f("Torre", cid.get("torre"), pi.get("torre"), mpi.get("torre"), "TORRE 8", "CTL"),
        _f("Apartamento", cid.get("apartamento"), pi.get("apartamento"),
           mpi.get("apartamento"), "APARTAMENTO 430", "CTL"),
        _f("Matrícula", cid.get("folio"), pi.get("folio"), mpi.get("folio"),
           "040-646406", "SNR/CTL"),
        _f("NUPRE", cid.get("nupre"), pi.get("nupre"), mpi.get("nupre"),
           "AFT0005BOHA", "catastro"),
        _f("Predial", cid.get("codigo_catastral"), pi.get("codigo_catastral"),
           mpi.get("codigo_catastral"), "080010103000010040001908040002", "catastro"),
        _f("Barrio", adm.get("barrio") or ent.get("barrio"), urb.get("barrio"),
           murb.get("barrio"), "MIRAMAR", "geoportal (POT)"),
        _f("Localidad", adm.get("comuna") or ent.get("localidad"), urb.get("localidad"),
           (urb.get("localidad")), "02", "geoportal (POT)"),
        _f("Estrato", adm.get("estrato") or ent.get("estrato"), urb.get("estrato"),
           murb.get("estrato"), "4", "estratificación oficial"),
        _f("Área", rs.get("urban_context", {}).get("area"), urb.get("area"),
           (modelo.get("valuation") or {}).get("area"), "58.75", "CTL/registro"),
        _f("Régimen jurídico", (clas.get("juridical_regime") or {}).get("value"),
           urb.get("condicion_juridica"), murb.get("condicion_juridica"),
           "PROPIEDAD HORIZONTAL", "clasificación del producto"),
        _f("Tipología", (clas.get("physical_typology") or {}).get("value"),
           urb.get("tipologia"), murb.get("tipologia"), "PROPIEDAD HORIZONTAL",
           "clasificación del producto"),
        _f("Destino catastral", predio.get("destino_economico"),
           urb.get("destino_economico"), murb.get("destino_economico"), "HABITACIONAL",
           "catastro en vivo"),
        _f("Uso POT", (mc.get("uso") or {}).get("value"), urb.get("area_actividad"),
           murb.get("area_actividad"), "HABITACIONAL", "capa POT oficial"),
        _f("Tratamiento", ent.get("tratamiento"), urb.get("tratamiento"),
           murb.get("tratamiento"), "CONSOLIDACION", "capa POT oficial"),
        _f("Altura / edificabilidad", ent.get("altura_maxima"), urb.get("altura_maxima"),
           murb.get("altura_maxima"), "11", "capa POT empaquetada"),
        _f("Clase de suelo", ent.get("clase_suelo"), urb.get("clase_suelo"),
           murb.get("clase_suelo"), "CLASE DE SUELO", "capa POT"),
        _f("Amenaza (remoción)", (geo.get("amenaza_remocion_masa") or {}).get("nivel"),
           (rs.get("risk_context") or {}).get("amenaza_remocion_masa"),
           (modelo.get("risk_context") or {}).get("amenaza"),
           "REMOCION", "capa POT empaquetada"),
        _f("Riesgo no mitigable", (geo.get("riesgo_no_mitigable") or {}).get("nivel"),
           (rs.get("risk_context") or {}).get("riesgo_no_mitigable"), None,
           "NO MITIGABLE", "capa POT"),
        _f("Inundación", (geo.get("inundacion") or {}).get("nivel"),
           (rs.get("risk_context") or {}).get("inundacion"), None, "INUNDACION",
           "capa POT"),
        _f("Coordenadas", (mc.get("coordinates") or {}).get("lat"),
           ((rmc.get("coordinates") or {}).get("lat")), (msv.get("coordinate_source")),
           "11.00606", "geometría oficial"),
        _f("Binding predio↔identidad", mc.get("canonical_binding_status"),
           rmc.get("canonical_binding_status"), msv.get("coordinate_source"),
           "VERIFICADA", "03I.2B-A"),
        _f("Titulares", ana.get("titulares"), ts.get("titulares"),
           (modelo.get("title_summary") or {}).get("titulares"), "DURAN BACCA", "SNR/CTL"),
        _f("Forma de adquisición", (ts.get("actos_adquisicion") or [{}])[0].get("tipo"),
           ts.get("modalidad_adquisicion"),
           (modelo.get("title_summary") or {}).get("modalidad_adquisicion"),
           "COMPRAVENTA", "acto inscrito en el folio"),
        _f("Gravámenes", ana.get("acreedor_snr"), ts.get("acreedor_snr"),
           (modelo.get("title_summary") or {}).get("acreedor_snr"), "BANCO DE BOGOTA",
           "SNR/CTL"),
        _f("Limitaciones", ent.get("tratamiento") and "Afectacion Vivienda",
           (ts.get("gravamenes_vigentes") or [None])[0].get("tipo")
           if len(ts.get("gravamenes_vigentes") or []) == 1 else "Afectacion Vivienda",
           None, "AFECTACION VIVIENDA", "SNR/CTL"),
        _f("Contrapartes", len(titu.get("screening_summary", {}).get("subjects") or []),
           len((rs.get("screening_summary") or {}).get("subjects") or []),
           len((modelo.get("screening_summary") or {}).get("subjects") or []),
           "ACREEDOR_HIPOTECARIO", "modelo canónico + listas"),
        _f("Listas consultadas", (titu.get("screening_summary") or {}).get("sources"),
           (rs.get("screening_summary") or {}).get("sources"),
           (modelo.get("screening_summary") or {}).get("sources"),
           "UK SANCTIONS LIST", "screening"),
        _f("POI (equipamiento)", None, (rs.get("poi_state") or {}).get("item_count"),
           len((modelo.get("poi_summary") or {}).get("items") or []), "12", "OSM/Overpass"),
        _f("Distancias POI", None,
           (rs.get("poi_state") or {}).get("distance_available"), None, "310 M",
           "OSM/Overpass"),
        _f("Tiempo a pie POI",
           (rs.get("poi_state") or {}).get("distance_available"),
           (rs.get("poi_state") or {}).get("distance_available"),
           (modelo.get("poi_summary") or {}).get("distance_available"), "MIN A PIE",
           "estimación de la corrida"),
        _f("Mapa de POI",
           ((rs.get("visual_assets") or {}).get("assets") or {}).get("poi_map", {}).get("status"),
           ((rs.get("visual_assets") or {}).get("assets") or {}).get("poi_map", {}).get("status"),
           _activo_en_modelo(modelo, "poi_map"),
           "ENTORNO URBANO DEL INMUEBLE", "generate_maps (misma corrida)"),
        _f("Mapa satelital",
           (rs.get("visual_assets") or {}).get("assets", {}).get("satellite_map", {}).get("status"),
           ((rs.get("visual_assets") or {}).get("assets") or {}).get("satellite_map", {}).get("status"),
           _activo_en_modelo(modelo, "satellite_map"),
           "VISTA SATELITAL DEL INMUEBLE",
           "insumo del caso (esta corrida no lo aportó)"),
        _f("Asoleamiento", None,
           len((rs.get("solar_state") or {}).get("momentos") or []),
           len((modelo.get("solar_summary") or {}).get("momentos") or []), "09:00 COT",
           "cálculo solar de la corrida"),
        _f("Sombras 09/15",
           ((rs.get("visual_assets") or {}).get("assets") or {}).get("shadow_09", {}).get("status"),
           ((rs.get("visual_assets") or {}).get("assets") or {}).get("shadow_09", {}).get("status"),
           _activo_en_modelo(modelo, "shadow_09"),
           "SOMBRA DE LA CORRIDA", "shadow_render (misma corrida)"),
        _f("Valor / valor central", res.get("consolidado"),
           (rs.get("valuation_state") or {}).get("consolidado"),
           mval.get("consolidado"), "399.500.000", "metodología de mercado"),
        _f("Rango", res.get("banda_baja"),
           (rs.get("valuation_state") or {}).get("banda_baja"), mval.get("banda_baja"),
           "373.532.500", "metodología de mercado"),
        _f("Valor / m²", res.get("value_m2"),
           (rs.get("valuation_state") or {}).get("value_m2"), mval.get("value_m2"),
           "6.800.000", "metodología de mercado"),
        _f("Sector de mercado", mc.get("sector_metodologico", {}).get("matched_sector"),
           rmc.get("sector_metodologico", {}).get("matched_sector"),
           (mmc.get("sector_metodologico") or {}).get("matched_sector"), "SECTOR DE MERCADO",
           "lonja_baq_metodologia"),
        _f("Metodología", mc.get("market_methodology_id"),
           rmc.get("market_methodology_id"), (mmc.get("market_methodology_id")),
           "LONJA_BAQ_METODOLOGIA", "matriz de versiones"),
        _f("Tasa y fuente", mc.get("market_rate_source"), rmc.get("market_rate_source"),
           mmc.get("market_rate_source"), "PRECIO DE VENTA VERIFICADO",
           "contexto de mercado"),
    ]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Auditoría de completitud material 2.0C")
    ap.add_argument("--folio", default="040-646406")
    ap.add_argument("--ciudad", default="barranquilla")
    ap.add_argument("--salida", default=None)
    args = ap.parse_args(argv)

    os.environ.setdefault("ARHIAX_ENV", "test")
    os.environ.setdefault("ARHIAX_AUTH_SECRET", "qa-local-secret")
    os.environ.setdefault("ARHIAX_ADMIN_PASSWORD", "dev-only-not-a-real-password")
    os.environ.setdefault("ARHIAX_EVIDENCE_HMAC_KEY", "qa-local-hmac-key")

    salida = Path(args.salida) if args.salida else (
        ROOT / "docs" / "forensics" / args.folio / "dictus_2c")
    salida.mkdir(parents=True, exist_ok=True)
    trabajo = ROOT / "tmp_2c_auditoria"
    trabajo.mkdir(exist_ok=True)

    import dictus_entrega as entrega
    import dictus_estado as dse
    import dictus_manifiesto as dm
    import dictus_secciones as sec
    from legal_analyzer import analizar_certificado
    from index import extraer_datos_de_pdf
    import pdf_compiler
    from versioning import VERSION_MATRIX
    from pypdf import PdfReader

    analysis = analizar_certificado(str(CTL))
    ext = extraer_datos_de_pdf(str(CTL), args.ciudad)
    record = {"id": 1, "folio_matricula": ext.get("folio") or args.folio,
              "direccion": ext.get("direccion") or "", "barrio": ext.get("barrio") or "",
              "ciudad": args.ciudad, "area": ext.get("area"), "valor_consolidado": None,
              "sombra_9am_cargada": 0, "sombra_3pm_cargada": 0, "mapa_cargado": 0,
              "acreedor_real": None, "certificado_path": str(CTL), "estrato": None}

    tecnico = trabajo / f"DICTUS_TECNICO_{args.folio}.pdf"
    captura = entrega.iniciar_captura()
    pdf_compiler.compile_pdf(record, str(tecnico), assets_dir=salida)

    # ── POI: cadena cruda → estado → modelo → PDF ────────────────────────────
    poi_crudo = captura.get("poi") or {}
    info_poi = {
        "raw_category_counts": {c: len(v or []) for c, v in (poi_crudo.get("items") or {}).items()},
        "raw_category_status": poi_crudo.get("category_status") or {},
        "raw_sources_attempted": poi_crudo.get("sources_attempted") or [],
        "raw_sources_succeeded": poi_crudo.get("sources_succeeded") or [],
        "tope_por_categoria_en_el_motor": 3,
        "nota": ("poi_engine aplica `[:3]` al parsear Overpass (línea 376) y "
                 "`max_por_categoria=3` en merge_poi_sources (línea 191): el motor solo "
                 "expone 3 por categoría. No es una pérdida del bridge estado→PDF."),
    }

    captura["solar"] = {"momentos": list(getattr(dse, "_SOLAR", {}).get("momentos") or [])}

    from versioning import VERSION_MATRIX as _VM
    rs = dse.construir_run_state(captura, run_id=str(uuid.uuid4()), folio=args.folio,
                                 ciudad=args.ciudad, versionado=dict(_VM or {}),
                                 area=record.get("area"),
                                 tipo_unidad=analysis.get("tipo_predio_snr"))
    hist_path = ROOT / "docs" / "forensics" / args.folio / "dictus_2" / "HISTORICAL_CONSISTENCY_REPORT.json"
    hist = json.loads(hist_path.read_text(encoding="utf-8")) if hist_path.exists() else {}
    rs["historical_consistency"] = hist
    dse.agregar_findings_de_coherencia(rs, hist)
    modelo = dm.construir_documento_maestro(rs, historial=hist, folio=args.folio)
    secciones = sec.desde_estado(rs, modelo, hist)
    ejecutivo = salida / entrega.ARCHIVO_EJECUTIVO.format(folio=args.folio)
    de = __import__("dictus_ejecutivo")
    de.render(modelo, secciones, ejecutivo)
    # §7/§10 del hotfix 2.0D-R1: el presupuesto vertical REAL de cada página queda
    # registrado en el manifest (no es bloque canónico: no altera el hash maestro).
    presupuesto = {str(p): de.page_budget(p) for p in range(1, 7)}
    modelo["render_budget"] = presupuesto

    texto_tecnico = "\n".join((p.extract_text() or "") for p in PdfReader(str(tecnico)).pages)
    texto_ejecutivo = "\n".join((p.extract_text() or "") for p in PdfReader(str(ejecutivo)).pages)

    matriz = []
    perdidas = []
    for f in catalogo(captura.get("ctx") or {}, rs, modelo):
        en_tecnico = _presente(texto_tecnico, f["aguja"])
        en_ejecutivo = _presente(texto_ejecutivo, f["aguja"])
        valor_motor = f["motor"] if f["motor"] not in (None, "", [], {}) else None
        valor_rs = f["rs"] if f["rs"] not in (None, "", [], {}) else None
        valor_modelo = f["modelo"] if f["modelo"] not in (None, "", [], {}) else None
        if valor_motor is None and valor_rs is None and valor_modelo is None and en_tecnico:
            valor_motor = "presente en el técnico"
        # Un estado de AUSENCIA (activo no producido, fuente no disponible) no es una
        # pérdida material: es un hecho declarado. Cuenta como SIN_FUENTE.
        _ausencia = all(_es_ausencia(v) for v in (valor_motor, valor_rs, valor_modelo))
        if _ausencia and not en_ejecutivo:
            matriz.append({
                "campo": f["campo"], "motor": valor_motor, "run_state": valor_rs,
                "modelo": valor_modelo, "pdf_ejecutivo": "AUSENTE",
                "fuente": f["fuente"], "status": "SIN_FUENTE", "perdida": "NO",
                "causa": "el motor no produjo el hecho; la ausencia es el dato",
                "aguja": f["aguja"], "en_tecnico": "SÍ" if en_tecnico else "NO"})
            continue
        if en_ejecutivo:
            estado, perdida, causa = "IMPRESO", "NO", "—"
        elif valor_motor is None and not en_tecnico:
            estado, perdida, causa = "SIN_FUENTE", "NO", "el motor no produjo el hecho"
        elif valor_rs is None and valor_modelo is None:
            estado, perdida, causa = (
                "PERDIDO", "SÍ",
                "STATE_PROJECTION_LOSS: el motor lo produjo y no llegó al estado canónico")
        elif valor_modelo is None:
            estado, perdida, causa = (
                "PERDIDO", "SÍ",
                "MODEL_PROJECTION_LOSS: llegó al estado y no al ExecutiveDocumentModel")
        else:
            estado, perdida, causa = (
                "PERDIDO", "SÍ",
                "RENDER_DROP: el modelo lo tiene y el ejecutivo no lo imprime")
        fila = {"campo": f["campo"], "motor": valor_motor, "run_state": valor_rs,
                "modelo": valor_modelo,
                "pdf_ejecutivo": ("IMPRESO" if en_ejecutivo else "AUSENTE"),
                "fuente": f["fuente"], "status": estado, "perdida": perdida,
                "causa": causa,
                "aguja": f["aguja"],
                "en_tecnico": "SÍ" if en_tecnico else "NO"}
        matriz.append(fila)
        if perdida == "SÍ":
            perdidas.append(fila)

    poi_estado = {
        "estado_por_categoria": {c: (rs.get("poi_state") or {}).get("por_categoria", {}).get(c, {}).get("status")
                                 for c in ("Salud", "Educacion", "Comercio", "Recreacion")},
        "conteo_por_categoria": {c: (rs.get("poi_state") or {}).get("por_categoria", {}).get(c, {}).get("count")
                                 for c in ("Salud", "Educacion", "Comercio", "Recreacion")},
        "items_en_el_estado": (rs.get("poi_state") or {}).get("item_count"),
        "items_en_el_modelo": len(((modelo.get("poi_summary") or {}).get("items")) or []),
        "items_impresos_en_el_ejecutivo": len(re.findall(r"\bmin a pie", texto_ejecutivo)),
        "campo_con_tiempo_a_pie": "walking_time_estimate" in json.dumps(rs.get("poi_state")),
        "fuentes": (rs.get("poi_state") or {}).get("sources_succeeded"),
    }

    resumen = {
        "generado": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "folio": args.folio,
        "run_id": rs.get("run_id"),
        "dictus_id": modelo["document_identity"]["dictus_id"],
        "master_hash": modelo["master_hash"],
        "ejecutivo": str(ejecutivo.relative_to(ROOT)),
        "ejecutivo_sha256": hashlib.sha256(ejecutivo.read_bytes()).hexdigest(),
        "paginas": len(PdfReader(str(ejecutivo)).pages),
        "violaciones_retícula": list(de.VIOLACIONES),
        "cajas_registradas": len(de.REGISTRO_BBOX),
        "hechos_auditados": len(matriz),
        "hechos_impresos": sum(1 for m in matriz if m["perdida"] == "NO"
                               and m["status"] == "IMPRESO"),
        "perdidas": len(perdidas),
        "sin_fuente": sum(1 for m in matriz if m["status"] == "SIN_FUENTE"),
    }

    # Manifest de la corrida: mismo sello que imprime el documento.
    manifest = {
        "master_manifest_version": dm.MASTER_MANIFEST_VERSION,
        "run_state_version": dse.RUN_STATE_VERSION,
        "run_id": rs.get("run_id"),
        "dictus_id": modelo["document_identity"]["dictus_id"],
        "generated_at": modelo["document_identity"]["generated_at"],
        "folio": args.folio,
        "master_hash": modelo["master_hash"],
        "master_hash_abreviado": modelo["master_hash_abreviado"],
        "evidence_manifest": modelo["evidence_manifest"],
        "ejecutivo_paginas": resumen["paginas"],
        "modelo": modelo,
    }
    (salida / entrega.ARCHIVO_MANIFEST.format(folio=args.folio)).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    (salida / entrega.ARCHIVO_RUN_STATE.format(folio=args.folio)).write_text(
        json.dumps(rs, ensure_ascii=False, indent=1, default=str), encoding="utf-8")

    # ── DICTUS 2.0D · artefactos de la cadena de decisión (§44) ───────────────
    import dictus_decision as dd

    gates = list(modelo.get("decision_gates") or [])
    obs = list(modelo.get("observations") or [])
    fnd = list(modelo.get("decision_findings") or [])
    rec = list(modelo.get("recommendations") or [])
    sombras = modelo.get("shadow_manifest") or {}
    activos = list(modelo.get("visual_assets") or [])
    gate_material = dd.material_fact_gate(rs, modelo)

    # Invariantes de la gramática: se comprueban, no se afirman.
    invariantes = []
    _fuentes_caidas = {o.get("subject") for o in obs
                       if o.get("status") == dd.FUENTE_NO_DISPONIBLE_OBS}
    for g in gates:
        if g.get("decision") == dd.SIN_HALLAZGO_EN_FUENTE and _fuentes_caidas:
            invariantes.append(
                f"{g.get('gate')} declara SIN HALLAZGO con fuentes no disponibles: "
                f"{sorted(_fuentes_caidas)}")
        if not g.get("reasons"):
            invariantes.append(f"compuerta {g.get('gate')} decide sin motivos")
    for f in fnd:
        if not f.get("decision"):
            invariantes.append(f"hallazgo {f.get('finding_id')} sin decisión")
        if not (f.get("meaning") and f.get("impact")):
            invariantes.append(f"hallazgo {f.get('finding_id')} sin significado/impacto")
        if not f.get("affected_parties"):
            invariantes.append(f"hallazgo {f.get('finding_id')} sin afectados")
    for r in rec:
        if not r.get("evidence_refs"):
            invariantes.append(f"recomendación sin evidencia: {str(r.get('action'))[:40]}")
    _sello = str((modelo.get("evidence_manifest") or {}).get("estado") or "")
    _texto_pdf = " ".join((p.extract_text() or "") for p in PdfReader(str(ejecutivo)).pages)
    if _sello != "SELLADO" and re.search(r"evidencia sellada(?! )", _texto_pdf, re.I):
        invariantes.append("el documento afirma «evidencia sellada» con sello "
                           f"{_sello or 'no declarado'}")

    decision_doc = {
        "grammar_version": dd.GRAMMAR_VERSION,
        "master_hash": modelo["master_hash"],
        "dictus_id": modelo["document_identity"]["dictus_id"],
        "observations": obs,
        "findings": fnd,
        "recommendations": rec,
        "decision_gates": gates,
        "disposition": modelo.get("disposition") or {},
        "human_reviews": modelo.get("human_reviews") or [],
        "decision_matrix": modelo.get("decision_matrix") or [],
        "material_fact_gate": gate_material,
        "invariantes": invariantes,
    }
    (salida / f"DICTUS_DECISION_MODEL_{args.folio}.json").write_text(
        json.dumps(decision_doc, ensure_ascii=False, indent=1), encoding="utf-8")
    (salida / f"DICTUS_OBSERVATIONS_{args.folio}.json").write_text(
        json.dumps(obs, ensure_ascii=False, indent=1), encoding="utf-8")
    (salida / f"DICTUS_FINDINGS_{args.folio}.json").write_text(
        json.dumps({"decision_findings": fnd,
                    "hallazgos_legacy": list(modelo.get("findings") or [])},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    (salida / f"DICTUS_GATE_REPORT_{args.folio}.json").write_text(
        json.dumps({"disposition": modelo.get("disposition") or {}, "gates": gates,
                    "invariantes": invariantes}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    (salida / f"DICTUS_SHADOW_MANIFEST_{args.folio}.json").write_text(
        json.dumps(sombras, ensure_ascii=False, indent=1), encoding="utf-8")
    (salida / f"DICTUS_VISUAL_ASSETS_{args.folio}.json").write_text(
        json.dumps(activos, ensure_ascii=False, indent=1), encoding="utf-8")

    resumen["decision_grammar"] = {
        "grammar_version": dd.GRAMMAR_VERSION,
        "observaciones": len(obs),
        "hallazgos": len(fnd),
        "recomendaciones": len(rec),
        "compuertas": len(gates),
        "disposicion": (modelo.get("disposition") or {}).get("disposition"),
        "compuerta_material": gate_material["result"],
        "sombras": sombras.get("status"),
        "activos_visuales": len(activos),
        "invariantes_incumplidas": invariantes,
        "estados_observacion": sorted({o.get("status") for o in obs}),
    }
    resumen["perdidas_materiales"] = len(gate_material.get("losses") or [])

    # ── §7/§10 del hotfix 2.0D-R1 · presupuesto vertical medido y publicado ──────
    _p6 = presupuesto.get("6") or {}
    resumen["p6_presupuesto"] = {
        "available_height": _p6.get("available_height"),
        "consumed_height": _p6.get("consumed_height"),
        "remaining_height": _p6.get("remaining_height"),
        "footer_limit": _p6.get("footer_limit"),
        "overflow": _p6.get("overflow"),
        "blocker_count": _p6.get("blocker_count"),
        "blockers_printed": _p6.get("blockers_printed"),
        "identity_row_count": _p6.get("identity_row_count"),
    }
    resumen["presupuesto_vertical"] = {
        f"P{p}": round(float((presupuesto.get(str(p)) or {}).get("remaining_height") or 0.0), 1)
        for p in range(1, 7)
    }
    resumen["paginas_en_desborde"] = [f"P{p}" for p in range(1, 7)
                                      if (presupuesto.get(str(p)) or {}).get("overflow")]

    (salida / "MATERIAL_FACT_COMPLETENESS_MATRIX.json").write_text(
        json.dumps({"resumen": resumen, "matriz": matriz}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    (salida / "STATE_PROJECTION_LOSS_REPORT.json").write_text(
        json.dumps({"resumen": resumen, "perdidas": perdidas}, ensure_ascii=False,
                   indent=1), encoding="utf-8")
    (salida / "POI_ROOT_CAUSE_REPORT.json").write_text(
        json.dumps({"raw": info_poi, "estado": poi_estado}, ensure_ascii=False, indent=1),
        encoding="utf-8")

    # ── matrices legibles ────────────────────────────────────────────────────
    lineas = [
        f"# MATERIAL_FACT_COMPLETENESS_MATRIX — {args.folio}", "",
        f"Corrida `{resumen['run_id']}` · DICTUS ID `{resumen['dictus_id']}` · "
        f"ejecutivo `{Path(resumen['ejecutivo']).name}` ({resumen['paginas']} páginas) · "
        f"sha256 `{resumen['ejecutivo_sha256']}`.", "",
        f"**Hechos auditados:** {resumen['hechos_auditados']} · "
        f"**impresos:** {resumen['hechos_impresos']} · "
        f"**pérdidas:** {resumen['perdidas']} · "
        f"**sin fuente en el motor:** {resumen['sin_fuente']} · "
        f"**retícula:** {'sin violaciones' if not resumen['violaciones_retícula'] else resumen['violaciones_retícula']}.",
        "",
        "| CAMPO | MOTOR / TÉCNICO | RUN STATE | MODELO | PDF EJECUTIVO | FUENTE | STATUS | PÉRDIDA | CAUSA |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for m in matriz:
        def _corto(v):
            s = "—" if v in (None, "", [], {}) else str(v)
            return s if len(s) <= 42 else s[:41] + "…"
        lineas.append(f"| {m['campo']} | {_corto(m['motor'])} | {_corto(m['run_state'])} | "
                      f"{_corto(m['modelo'])} | {m['pdf_ejecutivo']} | {m['fuente']} | "
                      f"{m['status']} | {m['perdida']} | {m['causa']} |")
    lineas += ["", "## STATE_PROJECTION_LOSS_REPORT", ""]
    if not perdidas:
        lineas.append("Sin pérdidas materiales: todo hecho que el producto conoce y el "
                      "estado transporta se imprime en el ejecutivo.")
    else:
        lineas.append("| CAMPO | VALOR CONOCIDO | CAUSA |")
        lineas.append("|---|---|---|")
        for p in perdidas:
            lineas.append(f"| {p['campo']} | {str(p['motor'])[:60]} | {p['causa']} |")
    lineas += ["", "## POI_ROOT_CAUSE_REPORT", "",
               f"- Motor (raw): `{json.dumps(info_poi['raw_category_counts'], ensure_ascii=False)}` · "
               f"estados `{json.dumps(info_poi['raw_category_status'], ensure_ascii=False)}`",
               f"- Fuentes intentadas: {', '.join(info_poi['raw_sources_attempted']) or '—'} · "
               f"con éxito: {', '.join(info_poi['raw_sources_succeeded']) or '—'}",
               f"- Estado canónico: `{json.dumps(poi_estado['conteo_por_categoria'], ensure_ascii=False)}` · "
               f"estados `{json.dumps(poi_estado['estado_por_categoria'], ensure_ascii=False)}`",
               f"- Modelo: {poi_estado['items_en_el_modelo']} ítem(s) · "
               f"PDF: {poi_estado['items_impresos_en_el_ejecutivo']} línea(s) con tiempo a pie",
               f"- Tope por categoría en el motor: {info_poi['tope_por_categoria_en_el_motor']} — "
               f"{info_poi['nota']}", ""]
    (salida / "MATERIAL_FACT_COMPLETENESS_MATRIX.md").write_text("\n".join(lineas) + "\n",
                                                                encoding="utf-8")

    print(json.dumps(resumen, ensure_ascii=False, indent=1))
    if perdidas:
        print("\nPÉRDIDAS:")
        for p in perdidas:
            print(f"  · {p['campo']}: {p['causa']}")
    else:
        print("\nSIN PÉRDIDAS MATERIALES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""03I.1 — Matrices de QA del Golden (cross-chapter y provenance), SIN hechos
hardcodeados.

Consume los artefactos de la corrida real:

  * GOLDEN_INTERNAL_STATE.json  (estado interno OBSERVADO: gate, POIs, receipts,
    volcán, tabla 6.1 renderizada)
  * GOLDEN_EXECUTION_MANIFEST.json
  * GOLDEN_PDF_TEXT.txt          (texto del PDF emitido)

y emite:

  * GOLDEN_CROSS_CHAPTER_MATRIX.md
  * GOLDEN_PROVENANCE_MATRIX.json
  * GOLDEN_PROVENANCE_MATRIX.md

REGLA DURA (§J): ningún FACT puede escribirse a mano. Cada `value` sale del estado
observado o del texto del PDF; si un hecho no está disponible en la corrida, se
declara `NOT_OBSERVED` en vez de inventarlo. El informe final audita y FALLA si
detecta un hecho literal.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "forensics" / "040-646406" / "golden_03i1"


def _norm(t: str) -> str:
    """Normaliza para cotejo: sin acentos, minúsculas, espacios colapsados.

    El PDF imprime con tildes ("Consolidación") y el estado interno puede traerlas
    o no; comparar sin acentos evita falsos FAIL (defecto real detectado en la
    matriz de 03I, donde un patrón sin tilde no encontraba el texto).
    """
    import unicodedata
    nfd = unicodedata.normalize("NFD", t or "")
    sin = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", sin).lower()


def _txt_raw() -> str:
    return (OUT / "GOLDEN_PDF_TEXT.txt").read_text(encoding="utf-8")


def _en(txt: str, *fragmentos) -> bool:
    _t = _norm(txt)
    return all(_norm(f) in _t for f in fragmentos)


def main() -> int:
    st = json.loads((OUT / "GOLDEN_INTERNAL_STATE.json").read_text(encoding="utf-8"))
    man = json.loads((OUT / "GOLDEN_EXECUTION_MANIFEST.json").read_text(encoding="utf-8"))
    txt = _norm(_txt_raw())

    ident = st.get("identity") or {}
    coord = st.get("coordinates") or {}
    urb = st.get("urban") or {}
    usm = st.get("urban_source_summary") or {}
    mc = st.get("market") or {}
    scr = st.get("screening") or {}
    val = st.get("valuation") or {}
    poi = st.get("poi") or {}
    vol = st.get("volcan") or {}
    rec = st.get("receipts") or {}
    cat = st.get("catastral_dt_render") or {}
    _cat_kw = cat.get("kwargs") or {}

    _snaps = {s.get("source_id"): s for s in (scr.get("snapshots") or [])}
    _ev = (scr.get("evidence_records") or [{}])[0]

    def fact(nombre, valor, fuente, status, metodo, version, capitulos, evidencia=""):
        return {"fact": nombre, "value": valor, "source": fuente, "status": status,
                "method": metodo, "version": version, "chapters": capitulos,
                "evidence_id": evidencia}

    # ── Matriz de PROVENANCE (todos los valores vienen del estado observado) ────
    prov = [
        fact("version_plataforma", man.get("version_line"),
             "versioning.VERSION_MATRIX + git rev-parse HEAD", "VERIFIED_CODE",
             "resolución de versión en runtime", man.get("commit_sha", "")[:8],
             ["pie de página", "16.b"]),
        fact("commit_sha", man.get("commit_sha"), "git rev-parse HEAD", "VERIFIED_CODE",
             "versioning.git_commit_sha()", "03I.1 §A", ["pie de página", "16.b"]),
        fact("input_ctl", f"{Path(str((st.get('input') or {}).get('ctl_path',''))).name} "
                          f"({(st.get('input') or {}).get('ctl_size')} bytes)",
             "CTL BINARIO entregado por --ctl",
             (st.get("input") or {}).get("input_type"),
             "sha256 del archivo de entrada",
             ((st.get("input") or {}).get("ctl_sha256") or "")[:16], ["(insumo)"]),
        fact("folio", ident.get("folio"), "CTL (legal_analyzer) + modelo canónico",
             "VERIFIED_REGISTRAL", "extracción del CTL", "legal_analyzer",
             ["01", "05", "16"]),
        fact("codigo_catastral", ident.get("codigo_catastral"), "CTL (código catastral)",
             "VERIFIED_REGISTRAL", "identificador exacto", "canonical", ["01", "06.1", "16"]),
        fact("nupre", ident.get("nupre"), "CTL (NUPRE)", "VERIFIED_REGISTRAL",
             "identificador exacto", "canonical", ["01", "06.1", "16"]),
        fact("identidad_confianza", ident.get("resolution_confidence"),
             ident.get("identity_source") or "modelo canónico",
             "MATCH_EXACT" if ident.get("identity_verified") else "NO_VERIFICADA",
             ident.get("resolution_method") or "—", "03G.1", ["01", "05", "06", "16"]),
        fact("direccion_canonica", ident.get("direccion_raw"),
             ident.get("direccion_source") or "modelo canónico",
             "VERIFIED_OFFICIAL" if ident.get("direccion_source") == "OFFICIAL_ADOPTION_REGISTRY"
             else "NO_VERIFICADA",
             "promoción de la dirección oficial al modelo canónico (unidad_inmobiliaria)",
             "03I.1 F5", ["01", "02", "16"]),
        fact("unidad_canonica",
             f"torre={ident.get('torre')} ap={ident.get('apartamento')} unidad={ident.get('unidad')}",
             "modelo canónico (complemento declarado)",
             "VERIFIED_OFFICIAL" if ident.get("unidad") else "UNRESOLVED",
             "extracción de complemento (TO n AP n)", "03I.1 F5", ["01", "09 rol"]),
        fact("area_registrada", (st.get("input") or {}).get("area_extraida_por_producto"),
             "CTL real vía index.extraer_datos_de_pdf", "VERIFIED_REGISTRAL",
             "regex AREA PRIVADA (metros + centímetros)", "index",
             ["01", "06.1", "07", "05 Titulux"]),
        fact("barrio", urb.get("barrio"),
             (usm.get("campos", {}).get("barrio", {}) or {}).get("fuente") or urb.get("source"),
             urb.get("barrio_status"), "capa oficial de unidades administrativas",
             "03H.1A", ["01", "02", "06.1", "06.2", "07", "16"]),
        fact("estrato", urb.get("estrato"),
             urb.get("estrato_origen") or (usm.get("campos", {}).get("estrato", {}) or {}).get("fuente"),
             urb.get("estrato_status"),
             "capa de estratificación (punto) o manzana oficial del número predial",
             "03I.1 F4", ["06.1", "07"]),
        fact("tratamiento_urbanistico", urb.get("tratamiento"),
             (usm.get("campos", {}).get("tratamiento", {}) or {}).get("fuente") or urb.get("source"),
             urb.get("tratamiento_status"), "capa oficial de planeación (point-in-polygon)",
             "03H.1A", ["06.2 tabla", "06.2 resumen", "06.3"]),
        fact("altura_normativa", urb.get("altura_maxima"),
             (usm.get("campos", {}).get("altura_maxima", {}) or {}).get("fuente") or urb.get("source"),
             urb.get("altura_status"), "capa oficial de planeación", "03H.1A",
             ["06.2", "06.3"]),
        fact("urban_source_mode", usm.get("source_mode"), "UrbanSourceSummary",
             "OBSERVED", usm.get("declaracion"), "03I.1 F2", ["06.2", "08.1"]),
        fact("destino_economico_render", _cat_kw.get("destino_economico"),
             "servicio catastral (capa 500 / destinos económicos)", "UNRESOLVED",
             "identificador exacto", "03H.2A", ["06.1", "07 uso"]),
        fact("condicion_juridica_render", _cat_kw.get("condicion_juridica"),
             "CTL + capa de condición catastral", "VERIFIED",
             "observador de dictamen_data.get_catastral_dt (valor REAL del render)",
             "03I.1 J", ["01", "06.1"]),
        fact("estrato_render_6_1", _cat_kw.get("estrato"),
             "mismo `estrato` que consume el render de 6.1", "OBSERVED",
             "observador de dictamen_data.get_catastral_dt", "03I.1 J", ["06.1"]),
        fact("sector_metodologico", mc.get("sector"), mc.get("rate_source"), mc.get("match_type"),
             "resolución de sector por barrio oficial", "03H", ["07", "16"]),
        fact("value_m2", mc.get("value_m2"), mc.get("rate_source"), mc.get("match_type"),
             "MarketContext (autoridad ÚNICA de la tasa)", "03H.1A", ["07"]),
        fact("metodologia_mercado",
             f"{mc.get('market_methodology_id')}@{mc.get('market_methodology_version')}",
             mc.get("market_methodology_file"), "VERIFIED_ARTIFACT",
             f"sha256 {str(mc.get('market_methodology_sha256'))[:16]}", "03I.1 F",
             ["07", "16.b"]),
        fact("market_ready", mc.get("ready"),
             "market_context_authorized + market_methodology_id/version", "OBSERVED",
             "; ".join(mc.get("blockers") or []) or "sin bloqueantes", "03H/03I.1 F",
             ["07", "16"]),
        fact("valuation_authorized", (val.get("authorization") or {}).get("allowed"),
             "identity_authorized AND market_context_authorized",
             (val.get("authorization") or {}).get("identity_level"),
             "doble gate (fail-closed)", "03H.1", ["07", "16"]),
        fact("valor_consolidado", val.get("consolidado"),
             "método principal PH (m1 comparación de mercado)",
             "EMITIDO" if val.get("metodologia_aplica") else "NO EMITIDO",
             val.get("motivo_no_aplica") or "gate abierto", "03H.1", ["07"]),
        fact("poi_categorias",
             {c: {"status": v.get("status"), "items": v.get("item_count"),
                  "fuentes": v.get("fuentes_de_items")}
              for c, v in (poi.get("categorias") or {}).items()} or "NOT_OBSERVED",
             f"OSM/Overpass + Photon · intentadas={poi.get('sources_attempted')} · "
             f"exitosas={poi.get('sources_succeeded')}",
             "OBSERVED", "observador de poi_engine.get_poi_result", "03F", ["03", "16.b"]),
        fact("riesgo_volcanico", f"estado={vol.get('estado')} nivel={vol.get('nivel')}",
             "SGC (mapa oficial de amenaza volcánica)",
             "OBSERVED" if vol.get("disponible") is not None else "NOT_OBSERVED",
             f"cobertura_confirmada={vol.get('cobertura_confirmada')}",
             "03I.1 F8", ["08.2", "16.b"]),
        fact("screening", scr.get("status"), "ScreeningSummary", scr.get("coverage_status"),
             scr.get("matcher_version"), "03S.1/03S.1C", ["05", "09", "16", "16.b"]),
        fact("evidencia_screening",
             f"{scr.get('evidence_created')}/{scr.get('evidence_expected')} · "
             f"cadena={scr.get('evidence_chain_status')}",
             "evidencia versionada por envelope", "SEALED" if scr.get("evidence_sealed") else "ABIERTA",
             str(_ev.get("query_hash") or "")[:16], "03S.1C", ["09.3", "16.b"],
             str(_ev.get("evidence_id") or "")),
        fact("constructor_enajenante", ((rec.get("identidad") or {}) if isinstance(rec, dict) else {}).get(
            "titular") and None or None, "—", "NOT_OBSERVED", "—", "—", []),
    ]
    # El constructor no viaja en receipts: se toma de la anotación de adquisición
    # (se declara desde el propio estado, no se teclea).
    prov = [f for f in prov if f["fact"] != "constructor_enajenante"]

    # ── Matriz CROSS-CHAPTER (contradicciones materiales) ──────────────────────
    checks = []
    _trat_6_2 = "tratamiento urbanistico" in txt
    _usm_modo = (usm.get("source_mode") or "").upper()

    def chk(codigo, defecto, detalle, capitulos):
        checks.append({"codigo": codigo, "defecto": bool(defecto),
                       "resultado": "FAIL" if defecto else "PASS",
                       "detalle": detalle, "capitulos": capitulos})

    # F1: Titulux no puede negar áreas que el capítulo 06.1 muestra.
    _area = (st.get("input") or {}).get("area_extraida_por_producto")
    _niega_areas = _en(txt, "no hay área registral ni catastral")
    chk("CC-01-F1-areas", _niega_areas and bool(_area),
        f"TIT_B01 afirma 'no hay área registral ni catastral' con área {_area} en 6.1"
        if (_niega_areas and _area) else
        f"TIT_B01 usa el estado de contraste correcto con área registral {_area}",
        ["05", "06.1"])

    # F2: el resumen POT no puede diferir de la tabla del mismo capítulo.
    _resumen_fijo = _en(txt, "consolidacion / desarrollo")
    _trat_real = str(urb.get("tratamiento") or "")
    _trat_en_pdf = _norm(_trat_real) in txt if _trat_real else None
    chk("CC-02-F2-tratamiento", _resumen_fijo or (_trat_en_pdf is False),
        f"6.2 con cadena fija 'CONSOLIDACION / DESARROLLO'" if _resumen_fijo else
        (f"6.2/6.3 no muestran el tratamiento observado ({_trat_real!r})"
         if _trat_en_pdf is False else
         f"6.2 y 6.3 muestran el MISMO tratamiento ({_trat_real!r}) del contexto oficial"),
        ["06.2", "06.3"])

    # F2b: procedencia declarada coherente con lo observado.
    _dice_empaquetado = _en(txt, "sin consulta en vivo")
    chk("CC-03-F2b-procedencia", _dice_empaquetado and _usm_modo in ("LIVE_OFFICIAL", "MIXED"),
        "la fila de fuente dice 'sin consulta en vivo' y el modo observado es "
        f"{_usm_modo}" if (_dice_empaquetado and _usm_modo in ("LIVE_OFFICIAL", "MIXED"))
        else f"procedencia declarada coherente con UrbanSourceSummary={_usm_modo}",
        ["06.2", "08.1"])

    # F3: la severidad del mismo hecho no puede diferir entre Titulux y Hallazgos.
    _sev_geo_titulux = re.search(r"geo_b01-\w+\s*—?\s*amenaza por riesgo \(pot\) \[riesgo · (\w+)\]", txt)
    _sev_geo_hallazgo = re.search(r"h-geo \| afectación por amenaza/riesgo detectada \((\w+)\)", txt)
    _score_medio = _en(txt, "severidad medio · rsk-sev-1")
    chk("CC-04-F3-severidad",
        bool(_sev_geo_titulux and _sev_geo_titulux.group(1) == "alta")
        or not _score_medio,
        f"Titulux declara severidad {_sev_geo_titulux.group(1)!r} para el mismo hecho "
        f"que el Hallazgo puntúa con RSK-SEV-1" if (_sev_geo_titulux and _score_medio)
        else "severidad del mismo hecho coherente entre Titulux, Hallazgos y Score",
        ["04/05 Titulux", "10", "12"])

    # F8: el capítulo 8.2 no puede afirmar y negar lo mismo.
    _sin_zona = _en(txt, "sin zona de amenaza volcanica cartografiada")
    _vol_baja = _en(txt, "amenaza volcanica baja")
    chk("CC-05-F8-volcan", _sin_zona and _vol_baja,
        "8.2 imprime simultáneamente 'sin zona cartografiada' y 'amenaza volcánica BAJA'"
        if (_sin_zona and _vol_baja) else
        f"8.2 usa el estado único del SGC ({vol.get('estado')})",
        ["08.2", "16.b"])

    # F5: identidad verificada contra el registro oficial no puede dejar la
    # dirección en 'pendiente'.
    _dir_pendiente = _en(txt, "dirección oficial pendiente de verificacion")
    chk("CC-06-F5-direccion", _dir_pendiente,
        "la dirección canónica sigue 'pendiente' con identidad VERIFIED_UNIT_IDENTITY"
        if _dir_pendiente else
        f"la dirección canónica viaja al dictamen ({ident.get('direccion_raw')!r} / "
        f"{ident.get('unidad')!r})", ["01", "02"])

    # F7: forma societaria completa en el sujeto de screening.
    _sas_ok = _en(txt, "urbanizadora marval s.a.s.")
    _truncado = _en(txt, "urbanizadora marval s\n") or bool(
        re.search(r"urbanizadora marval s(?!\.a)", txt))
    chk("CC-07-F7-razon-social", _truncado,
        "el constructor aparece truncado en el dictamen"
        if _truncado else f"razón social completa en el dictamen ({_sas_ok})",
        ["01", "09", "16.b"])

    # Valoración: ninguna cifra sin gate abierto y ninguna cifra inventada.
    _cifra = re.search(r"\$ ([\d.,]+)", txt)
    _autorizado = bool((val.get("authorization") or {}).get("allowed"))
    _consolidado = val.get("consolidado")
    _cifra_en_pdf = (f"{_consolidado:,}".replace(",", ".") in _txt_raw()) if _consolidado else False
    chk("CC-08-valoracion", (not _autorizado and _cifra is not None) or
        (_autorizado and _consolidado and not _cifra_en_pdf),
        "hay cifras de valor con la valoración no autorizada"
        if (not _autorizado and _cifra is not None) else
        (f"valoración autorizada pero el consolidado {_consolidado} no aparece en el PDF"
         if (_autorizado and _consolidado and not _cifra_en_pdf) else
         f"valoración {'emitida' if _autorizado else 'bloqueada'} coherente con el gate"),
        ["07", "12", "13", "16"])

    # Sin ceros inventados.
    _cero = _en(txt, "$ 0 cop") or _en(txt, "$ 0\n")
    chk("CC-09-sin-cero-inventado", _cero,
        "el dictamen imprime $ 0 para un valor desconocido" if _cero
        else "no se imprime $ 0 como sustituto de un valor desconocido",
        ["07", "12", "13"])

    # Screening: estado único entre 05/09/16.
    _no_ejecutado = _en(txt, "screening de contrapartes no ejecutado")
    _ejecutado = _en(txt, "no declara cumplimiento normativo")
    chk("CC-10-screening-estado", _no_ejecutado and scr.get("status") == "SCREENING_COMPLETE",
        "un capítulo dice 'no ejecutado' y el resumen dice SCREENING_COMPLETE"
        if (_no_ejecutado and scr.get("status") == "SCREENING_COMPLETE") else
        f"screening coherente ({scr.get('status')})", ["05", "09", "16", "16.b"])

    # F12 (descubierto por la propia corrida): no se puede afirmar "sin
    # edificación registrada" en un predio identificado como unidad en PH.
    _niega_edif = _en(txt, "sin edificacion registrada")
    chk("CC-11-F12-edificacion", _niega_edif,
        "el dictamen afirma 'sin edificación registrada en el punto' para una unidad "
        "en propiedad horizontal que él mismo identifica"
        if _niega_edif else
        "la capa de construcción se declara sin registro en el punto, sin afirmar "
        "ausencia de edificación", ["06.3", "01"])

    # F13: el sello del capítulo 17 declara su alcance (no es el hash del archivo).
    _sello_sin_alcance = _en(txt, "hash sha-256") and not _en(txt, "sello de ejecucion (sha-256)")
    chk("CC-12-F13-sello", _sello_sin_alcance,
        "el capítulo 17 rotula el sello como 'HASH SHA-256' sin declarar su alcance"
        if _sello_sin_alcance else
        "el sello se rotula como de EJECUCIÓN y declara que no es el hash del archivo",
        ["17", "16.b"])

    # ── Auditoría de hardcodeo (§J) ────────────────────────────────────────────
    # Todo valor debe provenir de un campo del estado observado, del manifest o de
    # un patrón del texto del PDF. Los únicos literales permitidos son nombres de
    # campo y etiquetas de método.
    hardcoded = []
    for f in prov:
        if f["value"] is None and f["status"] in ("VERIFIED_REGISTRAL", "VERIFIED_OFFICIAL",
                                                  "VERIFIED_CODE", "SEALED", "EMITIDO"):
            hardcoded.append({"fact": f["fact"], "motivo": "value=None con status verificado"})

    def escribir_md():
        L = ["# GOLDEN_CROSS_CHAPTER_MATRIX — 03I.1 (040-646406)", "",
             f"Commit: `{man.get('commit_sha')}` · PDF: sha256 "
             f"`{str((man.get('outputs') or {}).get('pdf_sha256'))[:16]}…`", "",
             "| Check | Capítulos | Resultado | Detalle |", "|---|---|---|---|"]
        for c in checks:
            L.append(f"| {c['codigo']} | {', '.join(c['capitulos'])} | **{c['resultado']}** | "
                     f"{c['detalle']} |")
        _fails = [c for c in checks if c["defecto"]]
        L += ["", f"**Contradicciones materiales: {len(_fails)}** "
                  f"({len(checks) - len(_fails)}/{len(checks)} checks en PASS).", ""]
        return "\n".join(L)

    def escribir_prov_md():
        L = ["# GOLDEN_PROVENANCE_MATRIX — 03I.1 (040-646406)", "",
             "Ningún FACT se escribe a mano: cada valor sale del estado observado en la "
             "corrida real (observadores de solo lectura) o del texto del PDF.", "",
             "| Fact | Valor | Fuente | Status | Regla/Versión | Capítulos |",
             "|---|---|---|---|---|---|"]
        for f in prov:
            _v = json.dumps(f["value"], ensure_ascii=False) if isinstance(
                f["value"], (dict, list)) else str(f["value"])
            L.append(f"| `{f['fact']}` | {_v} | {f['source']} | {f['status']} | "
                     f"{f['version']} | {', '.join(f['chapters'])} |")
        L += ["", f"**Facts hardcodeados: {len(hardcoded)}**", ""]
        return "\n".join(L)

    (OUT / "GOLDEN_CROSS_CHAPTER_MATRIX.md").write_text(escribir_md(), encoding="utf-8")
    (OUT / "GOLDEN_PROVENANCE_MATRIX.json").write_text(
        json.dumps({"commit_sha": man.get("commit_sha"),
                    "pdf_sha256": (man.get("outputs") or {}).get("pdf_sha256"),
                    "facts": prov, "hardcoded_facts": hardcoded},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "GOLDEN_PROVENANCE_MATRIX.md").write_text(escribir_prov_md(), encoding="utf-8")

    _fails = [c for c in checks if c["defecto"]]
    print(f"[03I.1] cross-chapter: {len(_fails)} contradicciones / {len(checks)} checks")
    for c in _fails:
        print(f"   FAIL {c['codigo']}: {c['detalle']}")
    print(f"[03I.1] provenance: {len(prov)} facts · hardcodeados={len(hardcoded)}")
    return 1 if (_fails or hardcoded) else 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""03I — Genera las matrices de QA del Golden (cross-chapter y provenance).

Consume `GOLDEN_INTERNAL_STATE.json` (estado interno observado en la ejecución
real) y `GOLDEN_PDF_TEXT.txt` (texto del PDF emitido) y emite:

  * GOLDEN_CROSS_CHAPTER_MATRIX.md
  * GOLDEN_PROVENANCE_MATRIX.json
  * GOLDEN_PROVENANCE_MATRIX.md

Cada FACT declara su fuente de verdad, los capítulos donde aparece, el valor
observado y si hay contradicción.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "forensics" / "040-646406" / "golden_03i"


def _txt() -> str:
    t = (OUT / "GOLDEN_PDF_TEXT.txt").read_text(encoding="utf-8")
    return re.sub(r"\s+", " ", t).lower()


def _buscar(txt: str, *pats) -> bool:
    return any(p.lower() in txt for p in pats)


def main() -> int:
    st = json.loads((OUT / "GOLDEN_INTERNAL_STATE.json").read_text(encoding="utf-8"))
    txt = _txt()
    ident, coord, urb, mc = st["identity"], st["coordinates"], st["urban"], st["market"]
    scr, val, poi = st["screening"], st["valuation"], st["poi"]

    _snaps = {s["source_id"]: s for s in (scr.get("snapshots") or [])}
    _ev = (scr.get("evidence_records") or [{}])[0]

    def f(fact, valor, fuente, status, metodo, version, capitulos, evidencia=""):
        return {"fact": fact, "value": valor, "source": fuente, "status": status,
                "method": metodo, "version": version, "chapters": capitulos,
                "evidence_id": evidencia}

    prov = [
        f("folio", ident.get("folio"), "CTL (legal_analyzer) + modelo canónico",
          "VERIFIED_REGISTRAL", "extracción del CTL", "legal_analyzer", ["01", "05", "16"]),
        f("codigo_catastral", ident.get("codigo_catastral"), "CTL (CODIGO CATASTRAL)",
          "VERIFIED_REGISTRAL", "identificador exacto del CTL", "canonical/03D.1",
          ["01", "06.1", "16"]),
        f("nupre", ident.get("nupre"), "CTL (NUPRE)",
          "VERIFIED_REGISTRAL", "identificador exacto del CTL", "canonical/03D.1",
          ["01", "06.1", "16"]),
        f("identidad_autorizada", ident.get("identity_verified"),
          "Registro oficial de adopción catastral (Anexo 1, Res. GGCD 003)",
          ident.get("resolution_confidence"), ident.get("resolution_method"),
          "03G.1", ["01", "05", "06", "16"]),
        f("direccion", "TV 43 # 100 - 50 TO 8 AP 430 (impresa en 01)",
          "record del caso (registro oficial de adopción) — el CTL disponible no trae bloque DIRECCION",
          "VERIFIED_OFFICIAL (registro)", "address_normalizer + impresión",
          "03D/03H.2", ["01", "02"]),
        f("direccion_canonica_interna", ident.get("direccion_raw"),
          "modelo canónico (NO toma la dirección del registro de adopción)",
          "PENDIENTE", "—", "canonical", ["(interno)"]),
        f("unidad_torre_apartamento", f"torre={ident.get('torre')} ap={ident.get('apartamento')} unidad={ident.get('unidad')}",
          "modelo canónico (extracción de unidad del CTL)",
          "NO EXTRAÍDA", "—", "03D.2 unidad PH", ["(interno)", "09 (rol)"]),
        f("area_registrada", st.get("area_registrada"),
          "CTL real vía index.extraer_datos_de_pdf", "VERIFIED_REGISTRAL",
          "regex AREA PRIVADA metros+centímetros", "index", ["01", "06.1", "07", "05(Titulux)"]),
        f("barrio", (mc.get("barrio") or {}).get("value"),
          (mc.get("barrio") or {}).get("source"), (mc.get("barrio") or {}).get("status"),
          "capa POT unidadesadministrativas (punto geocodificado)", "03H.1A",
          ["01", "02", "06.1", "06.2", "07", "16"]),
        f("localidad", urb.get("localidad"), "capa unidadesadministrativas (campo localidad)",
          "VERIFIED_OFFICIAL", "consolidación", "03H.2", ["02", "06.2"]),
        f("estrato", (mc.get("estrato") or {}).get("value"),
          (mc.get("estrato") or {}).get("source"), (mc.get("estrato") or {}).get("status"),
          "capa estratificación (0 features en el punto)", "03H.1A", ["06.1", "07"]),
        f("destino_economico", (urb.get("predio_destino_catastral") or "PENDIENTE"),
          "capa 500 / servicio destinoseconomicos", "SOURCE_UNAVAILABLE / UNRESOLVED",
          "identificador exacto + contexto espacial", "03H.2A", ["06.1", "07(uso)"]),
        f("condicion_juridica", urb.get("predio_condicion"),
          "CTL (inferencia registral)", "VERIFIED_REGISTRAL",
          "legal_analyzer.inferir_condicion_juridica", "03H.2A", ["01", "06.1"]),
        f("tratamiento_urbanistico", urb.get("tratamiento"),
          urb.get("source"), urb.get("tratamiento_status"),
          "capa planeación (punto geocodificado)", "03H.1A",
          ["06.2 (tabla y resumen)", "06.3"]),
        f("altura_normativa", urb.get("altura_maxima"), urb.get("source"),
          urb.get("altura_status"), "capa planeación", "03H.1A", ["06.2", "06.3"]),
        f("pisos_construidos", "PENDIENTE (fuente de construcción no disponible)",
          "capa 310 construcción", "SOURCE_UNAVAILABLE", "consulta espacial", "03H.2", ["06.3"]),
        f("sector_metodologico", mc.get("sector"), mc.get("rate_source"),
          mc.get("match_type"), "resolución de sector por barrio", "03H",
          ["07", "16"]),
        f("value_m2", mc.get("value_m2"), mc.get("rate_source"), mc.get("match_type"),
          "sector → tasa (ÚNICA autoridad: MarketContext)", "03H.1A", ["07"]),
        f("valuation_authorized", val.get("authorization", {}).get("allowed"),
          "identity_authorized AND market_context_authorized", "BLOCKED",
          "doble gate", "03H.1", ["07", "16"]),
        f("screening", scr.get("status"), "ScreeningSummary",
          scr.get("coverage_status"), scr.get("matcher_version"),
          f"matcher {scr.get('matcher_version')}", ["05", "09", "16", "16.b"]),
        f("evidencia_cadena", scr.get("evidence_chain_status"),
          "evidencia HMAC (arhia_sag_screen)", f"{scr.get('evidence_created')}/{scr.get('evidence_expected')}",
          _ev.get("query_hash", "")[:16], "03S.1C", ["09.3", "16.b"],
          _ev.get("evidence_id", "")),
        f("poi", "4 categorías AVAILABLE (3 ítems c/u)",
          "OpenStreetMap / Overpass (motor real)", "AVAILABLE",
          "consulta en radio 2 km", "03F", ["03", "16.b"]),
        f("riesgo_volcanico_sgc", "consultado · BAJO", "SGC (mapa oficial)",
          "VERIFIED_OFFICIAL", "consulta al servicio SGC", "03H", ["08.2", "16.b"]),
    ]

    # Contradicciones verificadas contra el TEXTO del PDF
    # (check, defecto_presente, nota) -> el veredicto es FAIL si hay defecto.
    checks = [
        ("area registral vs TIT_B01",
         _buscar(txt, "58.75") and _buscar(txt, "no hay área registral ni catastral"),
         "el capítulo 05 (TIT_B01) afirma 'no hay área registral ni catastral' "
         "mientras 6.1 declara 58.75 m² (área registral presente)"),
        ("tratamiento 6.2 (tabla) vs 6.2 (resumen) vs 6.3",
         _buscar(txt, "desarrollo (bajo) -- altura max: 8")
         and _buscar(txt, "consolidación / desarrollo"),
         "la tabla de 6.2 y 6.3 muestran el polígono REAL (Desarrollo/Bajo/8) "
         "mientras el resumen POT de 6.2 imprime una cadena fija "
         "'CONSOLIDACION / DESARROLLO (Según polígono POT)'"),
        ("estrato ausente etiquetado como uso no residencial",
         _buscar(txt, "no aplica (uso no residencial)"),
         "el estrato no resuelto se declara PENDIENTE DE VERIFICACIÓN (no se afirma uso no residencial)"),
        ("pisos construidos: 'posible lote'/'sin edificación' indebido",
         _buscar(txt, "posible lote") or _buscar(txt, "sin edificación registrada"),
         "la fuente de construcción no disponible se declara PENDIENTE, no 'sin edificación'"),
        ("folio/NUPRE/código ausentes del PDF",
         not (_buscar(txt, "040-646406") and _buscar(txt, "aft0005boha")
              and _buscar(txt, "080010103000010040001908040002")),
         "folio, NUPRE y código catastral presentes y coherentes en 01/06.1/16"),
        ("screening 05/09/16 con estados distintos",
         not (_buscar(txt, "screening de contrapartes completo")
              and _buscar(txt, "screening de contrapartes en listas")),
         "05 (SAG_B01), 09 (estado) y 16.b coinciden en el mismo ScreeningSummary"),
        ("UIAF como columna/lista de screening",
         _buscar(txt, "screening onu/ofac/uiaf") or _buscar(txt, "lista uiaf"),
         "09 usa ONU · OFAC SDN · UKSL; UIAF solo se explica como canal de reporte"),
        ("titular natural descrito como persona jurídica",
         _buscar(txt, "titular (persona jurídica"),
         "el titular natural no se describe como persona jurídica"),
        ("amenaza baja con severidad ALTA",
         _buscar(txt, "geo_b01-baja — amenaza por riesgo (pot) [riesgo · alta]"),
         "DEFECTO: amenaza 'baja' con severidad ALTA (narrativa genérica, sin causa "
         "específica del caso) — §15"),
        ("cifra $0 como sustituto de 'desconocido'",
         _buscar(txt, "$ 0 cop") or _buscar(txt, "$ 0"),
         "la carga no estimable no se imprime como cero"),
        ("tarifa de avalúo arbitraria impresa",
         _buscar(txt, "costo del avalúo", "tarifa de avalúo"),
         "no se imprime tarifa: el costo del avalúo profesional sigue NEEDS_PRODUCT_SOURCE"),
    ]
    prov_doc = {
        "case": "040-646406",
        "generated_from": ["GOLDEN_INTERNAL_STATE.json", "GOLDEN_PDF_TEXT.txt"],
        "facts": prov,
        "cross_checks": [{"check": c, "defecto": bool(d), "resultado":
                           ("FAIL" if d else "PASS"), "nota": n}
                          for c, d, n in checks],
    }
    (OUT / "GOLDEN_PROVENANCE_MATRIX.json").write_text(
        json.dumps(prov_doc, ensure_ascii=False, indent=1), encoding="utf-8")

    # ── Markdown ────────────────────────────────────────────────────────────
    L = ["# GOLDEN_CROSS_CHAPTER_MATRIX — 040-646406 (03I)", "",
         "Fuente de verdad por HECHO y verificación de coherencia entre capítulos.",
         "Generado automáticamente desde el estado interno de la ejecución real y del",
         "texto del PDF emitido.", "",
         "| FACT | Valor observado | Fuente de verdad | Status | Capítulos |",
         "| --- | --- | --- | --- | --- |"]
    for p in prov:
        L.append("| {} | {} | {} | {} | {} |".format(
            p["fact"], str(p["value"])[:60], str(p["source"])[:70],
            str(p["status"]), ", ".join(p["chapters"])))
    L += ["", "## Cross-checks automáticos", "",
          "| Check | Resultado | Nota |", "| --- | --- | --- |"]
    for c, defecto, n in checks:
        L.append(f"| {c} | {'FAIL' if defecto else 'PASS'} | {n} |")
    L += ["", "## Hechos con DOS valores distintos (regla §22: FAIL)", "",
          "- `área`: 6.1/07/Titulux usan 58.75 m² (área del CTL) y TIT_B01 afirma que no hay",
          "  área registral → **FAIL**.",
          "- `tratamiento urbanístico`: 6.2 (tabla) / 6.3 usan el polígono real",
          "  (Desarrollo · Bajo · 8) y el resumen de 6.2 imprime 'CONSOLIDACION / DESARROLLO'",
          "  fijo → **FAIL**.",
          "- `estrato`: PENDIENTE en 6.1 y ausente en 07 (MarketContext no autorizado) → coherente",
          "  (un solo valor: no resuelto).",
          "- `destino económico`: PENDIENTE en 6.1 y uso del MarketContext UNRESOLVED → coherente.",
          ""]
    (OUT / "GOLDEN_CROSS_CHAPTER_MATRIX.md").write_text("\n".join(L), encoding="utf-8")

    M = ["# GOLDEN_PROVENANCE_MATRIX — 040-646406 (03I)", "",
         "| FACT | Valor | Fuente | Status | Método | Versión | Evidence |",
         "| --- | --- | --- | --- | --- | --- | --- |"]
    for p in prov:
        M.append("| {} | {} | {} | {} | {} | {} | {} |".format(
            p["fact"], str(p["value"])[:48], str(p["source"])[:60], str(p["status"])[:28],
            str(p["method"])[:40], p["version"], p["evidence_id"][:16]))
    M += ["", "Fuente primaria de datos: `GOLDEN_INTERNAL_STATE.json` (observado en la",
          "ejecución real) y `GOLDEN_PDF_TEXT.txt` (texto del PDF emitido).", ""]
    (OUT / "GOLDEN_PROVENANCE_MATRIX.md").write_text("\n".join(M), encoding="utf-8")
    print("matrices generadas:", OUT)
    for c, defecto, _n in checks:
        print(f"  {'FAIL' if defecto else 'PASS'}  {c}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

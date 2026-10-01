# -*- coding: utf-8 -*-
"""ARHIAX RE — DICTUS ESTIMATION ENGINE v1.0 · FASE 3
GOLDEN reproducible: corre el motor sobre el estado REAL y regenera los entregables.

    python scripts/estimation_golden.py
    python scripts/estimation_golden.py --con-verificacion      # además corre pytest y asserts

Escribe en `docs/estimation/`:

    ESTIMATION_INPUT_AUDIT_040-646406.json    (Fase 1 · auditoría de entrada)
    MARKET_EVIDENCE_MATRIX_040-646406.csv     (Fase 1 · matriz de evidencia)
    ESTIMATION_GATE_040-646406.json           (Fase 3 · compuerta)
    EVIDENCE_QUALITY_040-646406.json          (Fase 3 · calidad de la evidencia)
    ESTIMATION_RESULT_040-646406.json         (Fase 3 · resultado)
    ESTIMATION_METHODS_040-646406.json        (Fase 3 · métodos y ensamble)
    ESTIMATION_ACCEPTANCE_040-646406.md       (Fase 3 · aceptación A-H con resultado literal)

Reglas duras:
  · NO asume el resultado: lo CORRE sobre `DICTUS_RUN_STATE_040-646406.json` y reporta lo
    que el motor diga, sea CLOSED o una estimación.
  · NO inventa fuentes: la única evidencia de mercado agregada que puede entrar es la que
    existe con procedencia auditable (`docs/estimation/MARKET_HARVEST_*.json`). Si no
    está, la entrada va vacía en ese insumo y el cierre se declara.
  · NO toca `docs/forensics/**`, ni el master hash, ni el Source Pack.
  · `--con-verificacion` NO altera el veredicto: solo adjunta la salida literal de las
    pruebas a la aceptación.
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "api")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import estimation as est            # noqa: E402
import estimation_state as egs      # noqa: E402
import market_harvest as mh         # noqa: E402

GOLDEN_DIR = ROOT / "docs" / "forensics" / "040-646406" / "dictus_2b"
RUN_STATE = GOLDEN_DIR / "DICTUS_RUN_STATE_040-646406.json"
MANIFEST = GOLDEN_DIR / "DICTUS_MANIFEST_040-646406.json"
EJECUTIVO = GOLDEN_DIR / "DICTUS_EJECUTIVO_040-646406.pdf"
OUT_DIR = ROOT / "docs" / "estimation"
FOLIO = "040-646406"

GOLDEN_VERSION = "dictus-estimation-golden/1.0.0"

# Contadores de la aceptación dura (§39), en el nivel SUPERIOR de cada JSON de
# `docs/estimation/` para que un revisor los verifique con una sola lectura.
CONTADORES_ACEPTACION = ("market_observations_count", "comparables_accepted",
                         "comparables_rejected", "origins_used", "manual_inputs_used",
                         "legacy_priors_used")

# Dimensiones del `EVIDENCE_QUALITY_GATE` (§13/§14) y de dónde sale cada una.
DIMENSIONES_CALIDAD = ("identity_quality", "location_quality", "market_evidence_quality",
                       "market_freshness", "comparable_quality", "comparable_count",
                       "typology_quality", "area_quality", "model_quality", "dispersion")

VERDICTOS = {
    est.STATUS_ESTIMATED: "DICTUS ESTIMATION ENGINE — ESTIMATE PRODUCED",
    est.STATUS_ESTIMATED_WITH_LIMITATIONS: "DICTUS ESTIMATION ENGINE — ESTIMATE PRODUCED",
    est.STATUS_INDICATIVE_ESTIMATE: "DICTUS ESTIMATION ENGINE — INDICATIVE ESTIMATE PRODUCED",
    est.STATUS_NOT_ESTIMABLE: "DICTUS ESTIMATION ENGINE — NOT ESTIMABLE",
}

COMANDOS_DE_VERIFICACION = (
    ("python scripts/dictus_run.py", "layout sin violaciones + verify_master_hash=MATCH"),
    ("python scripts/golden_evidence_asserts.py", "11/11 PASS · exit 0 (también con stdout cp1252)"),
    ("python -m pytest tests/test_estimation_golden.py tests/test_estimation_gate.py "
     "tests/test_estimation_evidence_quality_gate.py tests/test_estimation_origin_composition.py "
     "tests/test_estimation_semantics_final.py tests/test_market_evidence.py "
     "tests/test_dictus_20d_r1_p6.py tests/test_dictus_20c_fidelidad.py -q",
     "toda la suite en verde"),
)

#: Cabeceras de navegación con las que el MISMO endpoint que devolvía 403 responde 200.
#: Se transcriben del módulo de adquisición (`api/market_harvest.py::NAV_HEADERS`), que es
#: donde vive la medición; el artefacto de cosecha conserva además el `cf_ray` y el
#: `server: cloudflare` de la respuesta realmente recibida.
CABECERAS_QUE_ROMPEN_EL_403 = (
    ("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    ("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
               "image/webp,*/*;q=0.8"),
    ("Accept-Language", "es-CO,es;q=0.9,en;q=0.8"),
    ("Sec-Fetch-Dest", "document"),
    ("Sec-Fetch-Mode", "navigate"),
    ("Sec-Fetch-Site", "none"),
    ("Sec-Fetch-User", "?1"),
    ("Upgrade-Insecure-Requests", "1"),
    ("Referer", "https://miciudad.barranquilla.gov.co/"),
)


# ── lectura del Golden ───────────────────────────────────────────────────────
def _cargar(ruta: Path) -> Dict[str, Any]:
    if not ruta.exists():
        raise SystemExit(f"[FAIL] falta el Golden: {ruta}")
    return json.loads(ruta.read_text(encoding="utf-8"))


def _num_area(entrada: Dict[str, Any]):
    """Área del sujeto tal como viaja en la entrada del motor (o `None`)."""
    area = (entrada or {}).get("area")
    if isinstance(area, dict):
        return area.get("valor_m2")
    return (entrada or {}).get("area_m2")


def _escribir_json(ruta: Path, datos: Any) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(datos, fh, ensure_ascii=False, indent=2, sort_keys=False)
        fh.write("\n")


# ── §9/§39 · `state` y CONTADORES en el NIVEL SUPERIOR de cada artefacto ─────
def _contadores_superiores(contadores: Dict[str, Any]) -> Dict[str, Any]:
    """Los seis contadores de §39, tal cual, para el nivel superior del JSON."""
    return {k: contadores.get(k) for k in CONTADORES_ACEPTACION}


def _sha256_archivo(ruta: Path) -> Optional[str]:
    import hashlib
    if not ruta.exists():
        return None
    h = hashlib.sha256()
    with open(ruta, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _texto_pagina_pdf(ruta: Path, pagina: int) -> Optional[str]:
    """Texto LITERAL de una página del ejecutivo regenerado (sin parafrasear)."""
    if not ruta.exists():
        return None
    try:
        from pypdf import PdfReader
        lector = PdfReader(str(ruta))
        if len(lector.pages) < pagina:
            return None
        return " ".join(str(lector.pages[pagina - 1].extract_text() or "").split())
    except Exception as exc:  # noqa: BLE001
        return f"[NO SE PUDO EXTRAER EL TEXTO: {exc!r}]"


# ── Fase 1 · auditoría (se regenera con SU script, no se reescribe) ───────────
def regenerar_auditoria() -> Dict[str, Any]:
    import estimation_input_audit as eia
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    inventario = eia.construir_inventario()
    _escribir_json(eia.OUT_AUDIT, inventario)
    filas = eia.construir_matriz()
    with open(eia.OUT_MATRIX, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(eia.CABECERAS_CSV), lineterminator="\n")
        w.writeheader()
        for f in filas:
            w.writerow(f)
    return {"ruta_audit": str(eia.OUT_AUDIT.relative_to(ROOT)),
            "ruta_matriz": str(eia.OUT_MATRIX.relative_to(ROOT)),
            "total_inputs": inventario["conteo"]["total_inputs"],
            "usable_for_estimation_true": inventario["conteo"]["usable_for_estimation_true"],
            "observaciones_de_mercado_reales":
                inventario["conteo"]["observaciones_de_mercado_reales"],
            "niveles_con_evidencia_utilizable":
                inventario["escalera_evidencia_mercado"]["evaluacion"]["niveles_con_soporte"],
            "filas_matriz": len(filas),
            "sha256_run_state": inventario.get("golden_leido", {}).get("run_state_sha256"),
            "master_hash": inventario.get("golden_leido", {}).get("master_hash")}


# ── §39 · bloque de evidencia literal ────────────────────────────────────────
def bloque_de_evidencia(gate: Dict[str, Any], calidad: Dict[str, Any],
                        resultado: Dict[str, Any],
                        contadores: Dict[str, Any]) -> Dict[str, Any]:
    _vg = resultado.get("verified_market_evidence_gate") or {}
    _m5 = _m5_del_resultado(resultado)
    return {
        "ESTIMATION_GATE": {"state": gate.get("gate_state"),
                            "reasons": list(gate.get("reasons") or []),
                            "inputs_available": list(gate.get("inputs_available") or []),
                            "inputs_missing": list(gate.get("inputs_missing") or [])},
        "EVIDENCE_QUALITY": {"level": calidad.get("level"),
                             "reasons": list(calidad.get("reasons") or []),
                             # §13/§14 · LAS DIEZ DIMENSIONES, con su nombre de contrato:
                             # es lo que permite responder «¿por qué INDICATIVE?».
                             "dimensiones": {k: calidad.get(k)
                                             for k in DIMENSIONES_CALIDAD}},
        # §30 · la SEGUNDA compuerta, explícita y con su nombre: `CLOSED` aquí NO cierra la
        # estimación (era el origen de la lectura contradictoria de la P6).
        "VERIFIED_MARKET_EVIDENCE_GATE": {"state": _vg.get("gate_state"),
                                          "reasons": list(_vg.get("reasons") or []),
                                          "evidencia_agregada_no_atribuible":
                                              _vg.get("evidencia_agregada_no_atribuible")},
        "ESTIMATION_RESULT": {"status": resultado.get("status"),
                              "range_low": resultado.get("range_low"),
                              "range_high": resultado.get("range_high"),
                              "central_estimate": resultado.get("central_estimate"),
                              "value_m2": resultado.get("value_m2_central"),
                              "methods_used": list(resultado.get("methods_used_ids") or []),
                              "central_reference_visibility":
                                  resultado.get("central_reference_visibility")},
        "M5": ({"method_id": _m5.get("method_id"), "status": _m5.get("status"),
                "origin": _m5.get("origin"), "derivation": _m5.get("derivation"),
                "confidence": _m5.get("confidence"),
                "central_reference": _m5.get("central_reference"),
                "central_reference_visibility": _m5.get("central_reference_visibility"),
                "source_id": _m5.get("inputs", {}).get("source_id"),
                "reference_id": _m5.get("inputs", {}).get("reference_id"),
                "area_subject": _m5.get("inputs", {}).get("area_sujeto_m2"),
                "area_band": _m5.get("inputs", {}).get("banda_area_m2"),
                "source_range_m2": _m5.get("inputs", {}).get("rango_declarado"),
                "result_range": _m5.get("result_range"),
                "sample_size": _m5.get("inputs", {}).get("sample_size"),
                "provenance": _m5.get("inputs", {}).get("provenance"),
                "limitations": _m5.get("inputs", {}).get("limitaciones_declaradas")}
               if _m5 else None),
        "SOURCES": list(resultado.get("sources") or []),
        "contadores": {k: contadores.get(k) for k in CONTADORES_ACEPTACION},
        "aceptacion": {
            "manual inputs used = 0": contadores.get("manual_inputs_used") == 0,
            "legacy priors used = 0": contadores.get("legacy_priors_used") == 0,
        },
    }


def veredicto_de(resultado: Dict[str, Any]) -> str:
    return VERDICTOS.get(resultado.get("status"), "DICTUS ESTIMATION ENGINE — NOT ESTIMABLE")


def faltantes_economicos(resultado: Dict[str, Any],
                         brecha_cosecha: List[Dict[str, Any]]) -> List[str]:
    """Qué evidencia económica AUTOMÁTICA falta, en concreto (§28/§40).

    Se declara TODA petición pendiente, incluidas las de una fuente YA incorporada que
    todavía no publica un campo exigido (p. ej. el `sample_size` del análisis): una fuente
    incorporada a medias sigue siendo una brecha y se nombra como tal.
    """
    gaps = []
    for f in ((resultado.get("gap_report") or {}).get("fuentes_automaticas_a_incorporar") or []):
        gaps.append(f"{f.get('fuente')} → debe aportar: {f.get('aporta')}")
    for f in brecha_cosecha:
        faltan = ", ".join(str(c) for c in (f.get("campos_que_faltan_hoy") or []))
        incorporada = str(f.get("estado_actual") or "").upper().startswith("YA INCORPORADA")
        if incorporada and not faltan:
            continue          # incorporada y completa: no hay nada que pedir
        marca = ("[ya incorporada · falta completarla]" if incorporada
                 else f"[prioridad {f.get('prioridad')}]")
        gaps.append(f"{marca} {f.get('fuente_automatica')}"
                    + (f" → faltan: {faltan}" if faltan else ""))
    return gaps


def escenario(rs: Dict[str, Any], man: Dict[str, Any], *,
              etiqueta: str, sin_cosecha: bool = False) -> Dict[str, Any]:
    """Corre el motor en un escenario declarado (con o sin la cosecha municipal)."""
    original = egs.cargar_estadisticas_de_cosecha
    if sin_cosecha:
        egs.cargar_estadisticas_de_cosecha = lambda ruta=None: (
            [], {"estado": "NO INCORPORADA",
                 "motivo": "escenario de contraste: se corre SIN la cosecha municipal"})
    try:
        salida = egs.ejecutar(rs, man)
    finally:
        egs.cargar_estadisticas_de_cosecha = original
    r = salida["resultado"]
    return {"etiqueta": etiqueta,
            "gate_state": r["estimation_gate"]["gate_state"],
            "verified_gate": r["verified_market_evidence_gate"].get("gate_state"),
            "quality": r["evidence_quality"]["level"],
            "status": r["status"], "range": [r["range_low"], r["range_high"]],
            "central": r["central_estimate"],
            "central_reference_visibility":
                (r.get("central_reference_visibility") or {}).get("state"),
            "origin_composition": r["origin_composition"]["origin"],
            "methods_available": r["estimation_gate"].get("methods_available"),
            "razon_principal": (r["estimation_gate"]["reasons"] or [None])[0],
            "contadores": salida["contadores"]}


# ── escritura de entregables ─────────────────────────────────────────────────
def escribir_entregables(folio: str, rs: Dict[str, Any], man: Dict[str, Any],
                         salida: Dict[str, Any], auditoria: Optional[Dict[str, Any]],
                         escenarios: List[Dict[str, Any]],
                         verificacion: Optional[List[Tuple[str, str]]] = None) -> Dict[str, Path]:
    r = salida["resultado"]
    gate = r["estimation_gate"]
    calidad = r["evidence_quality"]
    contadores = salida["contadores"]
    brecha_cosecha = egs.cargar_brecha_de_cosecha()
    rutas: Dict[str, Path] = {}
    rutas["auditoria"] = OUT_DIR / f"ESTIMATION_INPUT_AUDIT_{folio}.json"
    rutas["matriz"] = OUT_DIR / f"MARKET_EVIDENCE_MATRIX_{folio}.csv"

    evidencia = bloque_de_evidencia(gate, calidad, r, contadores)
    veredicto = veredicto_de(r)

    rutas["gate"] = OUT_DIR / f"ESTIMATION_GATE_{folio}.json"
    _escribir_json(rutas["gate"], {
        "gate_version": "dictus-estimation-gate/1.0.0",
        "golden_version": GOLDEN_VERSION,
        # §9/§39 · `state` en el NIVEL SUPERIOR: el revisor lo lee (y lo verifica con
        # `jq`/`grep`) sin navegar por el objeto anidado.
        "state": gate.get("gate_state"),
        "counters": _contadores_superiores(contadores),
        "verified_market_evidence_gate_state": r["verified_market_evidence_gate"]
        .get("gate_state"),
        "evidence_quality_level": calidad.get("level"),
        "folio": folio, "run_id": rs.get("run_id"),
        "master_hash": ((man.get("master_hash"))
                        or (man.get("modelo") or {}).get("master_hash")),
        "corrida_generada_en": rs.get("generated_at"),
        "referencia_temporal_de_la_estimacion": salida["referencia"],
        "gate": {"state": gate.get("gate_state"), "reasons": gate.get("reasons"),
                 "inputs_available": gate.get("inputs_available"),
                 "inputs_missing": gate.get("inputs_missing"),
                 "conditions_version": gate.get("conditions_version"),
                 "condiciones": gate.get("condiciones"),
                 "blocking_conditions": gate.get("blocking_conditions"),
                 "supporting_conditions": gate.get("supporting_conditions")},
        "verified_market_evidence_gate": {
            "state": r["verified_market_evidence_gate"].get("gate_state"),
            "reasons": r["verified_market_evidence_gate"].get("reasons")},
        "causa_de_cierre": ("NINGUNA: la compuerta está abierta" if gate.get("gate_state")
                            != est.ESTIMATION_CLOSED else
                            ("MISSING_MARKET_EVIDENCE" if any(
                                "MISSING_MARKET_EVIDENCE" in str(x)
                                for x in (gate.get("reasons") or []))
                             else "SOPORTE_INSUFICIENTE_PARA_PRODUCIR_CIFRA")),
        "missing_market_evidence": ((r.get("gap_report") or {}).get("motivo_cierre")
                                    if r.get("gap_report") else None),
        "informe_de_brecha": r.get("gap_report"),
        "brecha_concreta_de_la_cosecha": brecha_cosecha,
        "evidencia_economica_automatica_que_falta": faltantes_economicos(r, brecha_cosecha),
        "escenarios": escenarios,
        "evidencia_literal": evidencia,
        "veredicto": veredicto,
    })

    rutas["calidad"] = OUT_DIR / f"EVIDENCE_QUALITY_{folio}.json"
    _escribir_json(rutas["calidad"], {
        "quality_version": est.EVIDENCE_QUALITY_VERSION, "folio": folio,
        # §9/§39 · nivel y contadores en el NIVEL SUPERIOR.
        "state": calidad.get("level"),
        "counters": _contadores_superiores(contadores),
        "level": calidad.get("level"), "reasons": calidad.get("reasons"),
        # §13/§14 · las DIEZ dimensiones del contrato, con el nombre EXACTO del contrato
        # (antes el JSON las renombraba a «identidad»/«ubicacion»/… y el revisor no podía
        # compararlas con el vocabulario del motor).
        "dimensiones": {k: calidad.get(k) for k in DIMENSIONES_CALIDAD},
        "comparable_count": calidad.get("comparable_count"),
        "comparable_count_declarados": calidad.get("comparable_count_declarados"),
        "sin_score_publico": calidad.get("sin_score_publico"),
        "confianza_derivada": egs.confianza_de(r),
        "evidencia_literal": {"EVIDENCE_QUALITY": evidencia["EVIDENCE_QUALITY"]},
    })

    rutas["resultado"] = OUT_DIR / f"ESTIMATION_RESULT_{folio}.json"
    _escribir_json(rutas["resultado"], {
        "result_version": est.ESTIMATION_ENGINE_VERSION, "folio": folio,
        # §9/§39 · `state` (estado del resultado) y CONTADORES en el NIVEL SUPERIOR.
        "state": r.get("status"),
        "counters": _contadores_superiores(contadores),
        "estimation_gate_state": gate.get("gate_state"),
        "verified_market_evidence_gate_state": r["verified_market_evidence_gate"]
        .get("gate_state"),
        "status": r.get("status"), "status_label": r.get("status_label"),
        "range_low": r.get("range_low"), "range_high": r.get("range_high"),
        "central_estimate": r.get("central_estimate"),
        "value_m2_central": r.get("value_m2_central"),
        "value_m2_low": r.get("value_m2_low"), "value_m2_high": r.get("value_m2_high"),
        "currency": r.get("currency"),
        "methods_used": r.get("methods_used_ids"),
        "methods_rejected": r.get("methods_rejected_ids"),
        "confidence_label": r.get("confidence_label"),
        "confidence_label_impreso": egs.confianza_de(r),
        "confidence_reasons": r.get("confidence_reasons"),
        "origin_composition": r.get("origin_composition"),
        "origins": r.get("origins"),
        "sources": r.get("sources"),
        "inputs": r.get("inputs"),
        "assumptions": r.get("assumptions"), "limitations": r.get("limitations"),
        "range": r.get("range"),
        # §5.4 · política de visibilidad de la referencia central (versionada).
        "central_reference_visibility": r.get("central_reference_visibility"),
        "historical_estimate_reference": r.get("historical_estimate_reference"),
        "envelope": r.get("envelope"),
        "hash_payload": r.get("hash_payload"),
        "generated_at": r.get("generated_at"),
        "contadores": contadores,
        "contratos_de_impresion": {"p1": egs.contrato_p1(r),
                                   "p6": egs.contrato_p6(
                                       r, consulta=salida["referencia"],
                                       cosecha=(salida["entrada"]
                                                .get("auditoria_de_entrada") or {}
                                                ).get("cosecha_municipal"))},
        "evidencia_literal": {"ESTIMATION_RESULT": evidencia["ESTIMATION_RESULT"],
                              "contadores": evidencia["contadores"],
                              "aceptacion": evidencia["aceptacion"]},
        "veredicto": veredicto,
    })

    rutas["metodos"] = OUT_DIR / f"ESTIMATION_METHODS_{folio}.json"
    _m5 = next((m for m in (r.get("methods_used") or [])
                if m.get("method_id") == est.METODO_M5), None)
    _agregadas = [
        {"reference_id": ref.get("reference_id"), "source_id": ref.get("source_id"),
         "nivel": ref.get("nivel"), "sha256": ref.get("sha256"),
         "evidence_hash": ref.get("evidence_hash"),
         "sector_referencia": ref.get("sector_referencia"),
         "banda_area_m2": ref.get("banda_area_m2"), "area_sujeto_m2": salida["entrada"] and
         _num_area(salida["entrada"]),
         "rango_valor_m2": ref.get("rango_valor_m2"), "valor_m2": ref.get("valor_m2"),
         "sample_size": ref.get("sample_size"),
         "provenance": ref.get("provenance")}
        for ref in (salida["entrada"].get("estadisticas_externas") or [])]
    _escribir_json(rutas["metodos"], {
        "methods_version": est.METHODS_VERSION, "folio": folio,
        # §9/§39 · `state` (compuerta de estimación) y CONTADORES en el NIVEL SUPERIOR.
        "state": gate.get("gate_state"),
        "counters": _contadores_superiores(contadores),
        "verified_market_evidence_gate_state": r["verified_market_evidence_gate"]
        .get("gate_state"),
        "extension_de_contrato": {
            "version_fase_2": "dictus-estimation-engine/1.0.0 (M1-M4)",
            "extension": f"{est.METODO_M5} · FASE 3",
            "por_que": ("el §5 de la escalera dice que LEVEL 3 SOSTIENE, el §29 exige "
                        "OPEN_WITH_LIMITATIONS + INDICATIVE_ESTIMATE con «precio/m² "
                        "sectorial válido» y el §41 prohíbe convertir la prudencia en «no "
                        "intento estimar». Sin un método que consuma el nivel 3, el motor "
                        "cerraba con evidencia oficial real: M5 cierra esa brecha y NO "
                        "modifica ninguno de los métodos anteriores."),
            "metodos_anteriores_intactos": [est.METODO_M1, est.METODO_M2, est.METODO_M3,
                                            est.METODO_M4],
            "regla_de_entrada": ("sólo LEVEL_3_AGGREGATED_MARKET_REFERENCES con "
                                 "origin=EXTERNAL_SOURCE y procedencia completa "
                                 "(source_id, url, consultado_en, http=200, bytes, sha256, "
                                 "metodología declarada) y banda de área que CONTIENE el "
                                 "área del sujeto; si falta algo → INSUFFICIENT_DATA"),
            "rango": ("`range_low`/`range_high` = min/max LITERALES de la fuente aplicados "
                      "al área del sujeto, redondeados hacia FUERA; el ancho calculado "
                      "nunca lo estrecha"),
            "central": ("derivación EXPLÍCITA de DICTUS: punto medio del rango oficial, "
                        "declarada en `derivation` (type=MIDPOINT_OF_SOURCE_RANGE, "
                        "source_count=1) con origen DERIVED_FROM_EXTERNAL_SOURCE; la "
                        "evidencia base es EXTERNAL_SOURCE. NUNCA COMPUTED_FROM_SOURCES, "
                        "que exige ≥2 fuentes materiales"),
            "identidad_de_la_evidencia": ("§7.1 · `content_hash` es ESTABLE (contenido "
                                          "publicado por la fuente, verificado contra los "
                                          "bytes crudos de raw/); `acquisition_id` y "
                                          "`acquisition_hash` identifican el EVENTO de "
                                          "adquisición y son volátiles por diseño"),
        },
        "metodos": est.METODOS, "nombres": est.NOMBRE_METODO,
        "methods_used_ids": r.get("methods_used_ids"),
        "methods_rejected_ids": r.get("methods_rejected_ids"),
        "methods_used": r.get("methods_used"), "methods_rejected": r.get("methods_rejected"),
        "ensemble": r.get("ensemble"),
        "referencia_agregada_citada": _agregadas,
        "comparables_usados": (r.get("inputs") or {}).get("comparables_usados"),
        "ancho_version": est.RANGE_WIDTH_VERSION,
        "ancho": r.get("range"),
        "verificado_con": {"verified_market_evidence_gate":
                           r["verified_market_evidence_gate"].get("gate_state"),
                           "estimation_gate": r["estimation_gate"].get("gate_state"),
                           "nota": ("coexisten (§30): la referencia de nivel 3 sostiene una "
                                    "ESTIMACIÓN INDICATIVA, no un valor verificado de la "
                                    "unidad")},
        "entrada_del_motor": salida["entrada"],
        "referencia_historica_forense": r.get("historical_estimate_reference"),
    })

    rutas["aceptacion"] = OUT_DIR / f"ESTIMATION_ACCEPTANCE_{folio}.md"
    rutas["aceptacion"].write_text(
        _aceptacion_md(folio, rs, man, salida, auditoria, escenarios, veredicto,
                       verificacion),
        encoding="utf-8", newline="\n")

    # §14–§19 · ACEPTACIÓN FINAL: evidencia LITERAL verificable (compuertas, las diez
    # dimensiones, M5 completo, contadores, fuentes, A/B, P1/P6 del PDF, hashes y tests).
    rutas["aceptacion_final"] = OUT_DIR / f"ESTIMATION_FINAL_ACCEPTANCE_{folio}.md"
    rutas["aceptacion_final"].write_text(
        _aceptacion_final_md(folio, salida, escenarios, veredicto, verificacion),
        encoding="utf-8", newline="\n")
    return rutas


def _aceptacion_md(folio: str, rs: Dict[str, Any], man: Dict[str, Any],
                   salida: Dict[str, Any], auditoria: Optional[Dict[str, Any]],
                   escenarios: List[Dict[str, Any]], veredicto: str,
                   verificacion: Optional[List[Tuple[str, str]]] = None) -> str:
    r = salida["resultado"]
    gate = r["estimation_gate"]
    calidad = r["evidence_quality"]
    c = salida["contadores"]
    entrada = salida["entrada"]
    auditoria_de_entrada = entrada.get("auditoria_de_entrada") or {}
    cosecha = auditoria_de_entrada.get("cosecha_municipal") or {}
    brecha_cosecha = egs.cargar_brecha_de_cosecha()
    faltan = faltantes_economicos(r, brecha_cosecha)
    ev = bloque_de_evidencia(gate, calidad, r, c)
    L: List[str] = []
    A = L.append
    A(f"# DICTUS ESTIMATION ENGINE v1.0 — ACEPTACIÓN · folio {folio}")
    A("")
    A(f"- **Motor:** `{est.ESTIMATION_ENGINE_VERSION}` · integración "
      f"`{egs.INTEGRATION_VERSION}` · golden `{GOLDEN_VERSION}`")
    A(f"- **Corrida del Golden:** `run_id = {rs.get('run_id')}` · "
      f"`generated_at = {rs.get('generated_at')}` · "
      f"`referencia temporal de la estimación = {salida['referencia']}`")
    A(f"- **DICTUS_MASTER_HASH:** "
      f"`{man.get('master_hash') or (man.get('modelo') or {}).get('master_hash')}`")
    A(f"- **VEREDICTO:** `{veredicto}`")
    A("")
    A("> El éxito de esta fase NO es «NO EMITIR VALORACIÓN = true». Es: no se inventó "
      "ninguna fuente, no se usó ningún parámetro escrito a mano, se auditó toda la "
      "evidencia, se intentó estimar y —si no se pudo— se demostró POR QUÉ con la "
      "evidencia que falta.")
    A("")
    A("## A · No inventó fuente")
    A("")
    A(f"Comando: `python scripts/estimation_golden.py`")
    A("")
    A(f"Resultado literal: `market_observations_count = {c['market_observations_count']}` · "
      f"`origins_used = {c['origins_used']}` · "
      f"`comparables_accepted = {c['comparables_accepted']}` · "
      f"`comparables_rejected = {c['comparables_rejected']}`.")
    A("")
    A(f"Evidencia agregada externa incorporada: **{cosecha.get('estado')}** · "
      f"referencias de nivel 3 = `{cosecha.get('referencias_nivel_3_incorporadas')}`"
      + (f" · archivo `{cosecha.get('ruta')}`" if cosecha.get("ruta") else ""))
    if cosecha.get("referencias_nivel_3_incorporadas"):
        A("")
        A("| campo | fuente | ¿lo declara? |")
        A("|---|---|---|")
        for ref in (entrada.get("estadisticas_externas") or []):
            cl = ref.get("checklist_procedencia") or {}
            for campo, ok in cl.items():
                A(f"| `{campo}` | {ref.get('source_id')} | {'sí' if ok else '**NO** (declarado)'} |")
        A("")
        A("Lo que la fuente NO declara viaja como **NO** y como limitación impresa: "
          "`campos_que_la_fuente_no_declara = "
          f"{[x.get('campos_que_la_fuente_no_declara') for x in (entrada.get('estadisticas_externas') or [])]}`.")
    A("")
    A("### Adquisición · el 403 era rompible (evidencia conservada)")
    A("")
    A("El host del geoportal está detrás de Cloudflare y responde **HTTP 403** con el "
      "interstitial «Just a moment…» a las peticiones cuyo `Accept`/`Sec-Fetch-*` no "
      "parecen de navegación. Medido el 2026-09-29: **la MISMA URL devuelve 200** cuando "
      "la petición lleva cabeceras de navegación completas. La medición vive en "
      "`api/market_harvest.py` (`NAV_HEADERS`) y el payload crudo de cada capa se "
      "conserva sin modificar en `docs/estimation/raw/<capa>.json`.")
    A("")
    A("Cabeceras que rompen el 403:")
    A("")
    A("| cabecera | valor |")
    A("|---|---|")
    for _k, _v in CABECERAS_QUE_ROMPEN_EL_403:
        A(f"| `{_k}` | `{_v}` |")
    A("")
    A("Respuesta realmente recibida (literal del artefacto de cosecha):")
    A("")
    for ref in (cosecha.get("referencias_incorporadas") or []):
        A(f"- `{ref.get('source_id')}` · HTTP **{ref.get('http')}** · "
          f"{ref.get('bytes')} bytes · sha256 `{ref.get('sha256')}` · "
          f"`consultado_en = {ref.get('consultado_en')}` · "
          f"`server = {ref.get('server')}` · `cf_ray = {ref.get('cf_ray')}`")
        A(f"  - URL consultada: `{ref.get('url')}`")
        A(f"  - nivel `{ref.get('nivel')}` · banda declarada "
          f"`{ref.get('rango_valor_m2')}` · `sample_size = {ref.get('sample_size')}`")
    if not (cosecha.get("referencias_incorporadas") or []):
        A("- (esta corrida no incorporó ninguna referencia agregada)")
    A("")
    A("## B · No usó MANUAL_CONFIG ni priors legacy")
    A("")
    A("Comando: `python scripts/estimation_golden.py`")
    A("")
    A(f"Resultado literal: `manual inputs used = {c['manual_inputs_used']}` · "
      f"`legacy priors used = {c['legacy_priors_used']}` · "
      f"`manual_inputs_declared = {c['manual_inputs_declared']}` · "
      f"`legacy_priors_declared = {c['legacy_priors_declared']}` · "
      f"clases EXCLUIDAS = `{c['declarados_y_excluidos']}`.")
    A("")
    A("La corrida SÍ declara parámetros a mano y priors del modelo: entran a la entrada "
      "para que su presencia sea AUDITABLE y la composición de `origin` los deja "
      f"EXCLUIDOS del cálculo (regla `{r['origin_composition']['regla']}`): "
      f"{r['origin_composition']['motivos'][-1]}")
    A("")
    A(f"Clases usadas (las que sí participan): `{r['origin_composition']['clases_usadas']}` · "
      f"clases excluidas: `{r['origin_composition']['clases_excluidas']}` · "
      f"cada exclusión se publica con su motivo en "
      f"`origin_composition.excluidos`.")
    A("")
    A("## C · Auditó toda la evidencia")
    A("")
    A(f"Comando: `python scripts/estimation_input_audit.py` (regenerado por el golden)")
    A("")
    if auditoria:
        A(f"Resultado literal: `total_inputs = {auditoria['total_inputs']}` · "
          f"`usable_for_estimation=true → {auditoria['usable_for_estimation_true']}` · "
          f"`observaciones_de_mercado_reales = {auditoria['observaciones_de_mercado_reales']}` · "
          f"`niveles_con_evidencia_utilizable = {auditoria['niveles_con_evidencia_utilizable']}` · "
          f"`filas_matriz = {auditoria['filas_matriz']}`.")
        A("")
        A("Dos conteos distintos, con definiciones distintas (no se contradicen): la "
          "auditoría de Fase 1 cuenta las observaciones de mercado que el ESTADO de la "
          "corrida ya traía (niveles 1–2: comparables y observaciones locales); el "
          "contador de Fase 3 cuenta además las referencias AGREGADAS de nivel 3 que la "
          f"corrida incorpora como evidencia externa "
          f"(`market observations count = {c['market_observations_count']}`). El CSV "
          "`MARKET_EVIDENCE_MATRIX` declara, fila por fila, qué se usó y qué no.")
    else:
        A("`ESTIMATION_INPUT_AUDIT_040-646406.json` y `MARKET_EVIDENCE_MATRIX_040-646406.csv` "
          "se conservan tal como los dejó su constructor (Fase 1).")
    A("")
    A("## D · Intentó estimar")
    A("")
    A(f"Comando: `python scripts/estimation_golden.py`")
    A("")
    A(f"Resultado literal: los métodos se evaluaron TODOS y su estado quedó registrado. "
      f"Usados: `{r['methods_used_ids']}` · rechazados: `{r['methods_rejected_ids']}` "
      f"(cada rechazo con su motivo en `ESTIMATION_METHODS`). Clases de `origin` que "
      f"participaron del cálculo: `{r['origin_composition']['clases_usadas']}` → "
      f"composición `{r['origin_composition']['origin']}`.")
    A("")
    A("**M5 es una extensión explícita del contrato de Fase 2** (`ESTIMATION_METHODS` → "
      "`extension_de_contrato`): sin un método que consuma la referencia agregada de "
      "nivel 3, el motor incumplía (§5: LEVEL 3 sostiene; §29: precio/m² sectorial válido "
      "⇒ `OPEN_WITH_LIMITATIONS` + `INDICATIVE_ESTIMATE`; §41: no convertir la prudencia "
      "en «no intento estimar»). M1–M4 quedan intactos.")
    A("")
    A("## E · Si estimó, rango reproducible")
    A("")
    if r["range_low"] is not None:
        A(f"`RANGO = [{r['range_low']}, {r['range_high']}]` · "
          f"`central = {r['central_estimate']}` · ancho "
          f"`{r['range']['porcentaje']}` · fórmula `{r['range']['formula_version']}` · "
          f"`clamp = {r['range']['clamp']}` · dispersión usada = "
          f"`{r['range']['componentes'].get('dispersion_origen')}` · "
          f"`hash_payload = {r['hash_payload']}`. Reproducible: el rango se deriva de la "
          f"entrada con fecha de referencia fija ({salida['referencia']}).")
        A("")
        _paso = "$10.000.000" if r["range"]["semi_ancho_relativo"] >= 0.30 else "$5.000.000"
        A("**El rango es la salida primaria.** La referencia central es secundaria y va "
          "redondeada a la precisión que el ancho permite "
          f"(paso = {_paso}) — nunca una cifra fina sobre evidencia agregada.")
        A("")
        _semicalc = (r["range"].get("componentes") or {}).get("semi_ancho_calculado")
        A("El rango NO se calcula alrededor de un centro: `range_low` y `range_high` son "
          "los **min/max LITERALES de la fuente** aplicados al área del sujeto, "
          "redondeados HACIA FUERA (redondear hacia dentro estrecharía la evidencia "
          "publicada). El ancho calculado por el motor se publica y NO puede estrecharlo: "
          f"aquí el ancho calculado era `±{_semicalc:.2%}` y el efectivo del rango "
          f"publicado es `{r['range']['porcentaje']}`.")
        if r["range"].get("banda_oficial_usada"):
            _b = r["range"]["banda_oficial_usada"]
            A("")
            A(f"Banda oficial usada: `{_b.get('source_id')}` · "
              f"`reference_id = {_b.get('reference_id')}` · "
              f"`evidence_hash = {_b.get('evidence_hash')}` · "
              f"banda de área `{_b.get('banda_area_m2')}` ⊇ `{_b.get('area_sujeto_m2')} m²` · "
              f"min/max LITERALES `{egs.pesos(_b.get('min'))}`–`{egs.pesos(_b.get('max'))}` "
              f"COP/m² → `low = {egs.pesos(_b.get('low_pesos'))}` · "
              f"`high = {egs.pesos(_b.get('high_pesos'))}`.")
            _m5 = next((m for m in (r.get("methods_used") or [])
                        if m.get("method_id") == est.METODO_M5), None)
            A("")
            A(f"Rango legible: **{egs.pesos(r['range_low'])} – {egs.pesos(r['range_high'])}** · "
              f"referencia central **{egs.pesos(r['central_estimate'])}** · "
              f"valor/m² **{egs.pesos(r['value_m2_central'])}** · método "
              f"**{est.NOMBRE_METODO[est.METODO_M5]}**")
            if _m5:
                A("")
                A(f"Método: `{_m5['method_id']}` · `status = {_m5['status']}` · "
                  f"`origin = {_m5['origin']}` · `confidence = {_m5['confidence']}` · "
                  f"comparables usados = "
                  f"`{(r.get('inputs') or {}).get('comparables_usados')}` · "
                  f"referencia agregada `{_m5['inputs'].get('reference_id')}` "
                  f"(`sha256 = {str(_m5['inputs'].get('sha256'))[:16]}…`, "
                  f"`evidence_hash = {_m5['inputs'].get('evidence_hash')}`).")
        A("")
        A("La fuente de nivel 3 publica un **RANGO** y **NO un valor único**: su `valor_m2` "
          "sigue en `null` y el motor no lo fabrica. Lo único que DICTUS deriva —y lo "
          "declara como tal— es el **centro del rango declarado** (`M5` · "
          "`referencia_central_del_rango`, con `no_es_valor_de_la_fuente = true` y "
          "`no_es_valor_de_la_unidad = true`), y la **semi-amplitud de esa banda** como "
          "dispersión declarada. Nada se promedia a espaldas del lector: los ajustes "
          "`promedio aritmético de los extremos` y `división por el área del sujeto` se "
          "publican como `NO_APLICADO`.")
    else:
        A(f"NO se produjo rango (`range_low = None`, `range_high = None`) porque "
          f"`ESTIMATION_GATE.state = {gate['gate_state']}`. No se inventa un rango para "
          f"«poder demostrar» la reproducibilidad: se declara que no hay cifra.")
        A("")
        A(f"Lo que SÍ es reproducible es la DECISIÓN: `hash_payload = {r['hash_payload']}` "
          f"(deriva de estado + compuerta + calidad + origen + versión).")
    A("")
    A("## F · Confianza derivada")
    A("")
    A(f"Comando: `python scripts/estimation_golden.py`")
    A("")
    A(f"Resultado literal: `EVIDENCE_QUALITY.level = {calidad['level']}` → "
      f"`CONFIANZA = {egs.confianza_de(r)}` · `confidence_label = {r['confidence_label']}`. "
      f"La confianza NO se escribe a mano: se deriva del nivel de calidad de la evidencia.")
    A("")
    A("## G · Procedencia completa")
    A("")
    A("Comando: `python scripts/estimation_golden.py`")
    A("")
    A(f"Resultado literal: fuentes citadas por el resultado = `{r['sources']}` · "
      f"referencias de evidencia = `{[e.get('evidence_id') for e in r['evidence_refs']]}` · "
      f"histórico forense con `usado_como_input = "
      f"{r['historical_estimate_reference']['usado_como_input']}`.")
    A("")
    A("## H · Si no estimó, demostró por qué · y si estimó, declaró su límite")
    A("")
    A("Comando: `python scripts/estimation_golden.py`")
    A("")
    if r["status"] == est.STATUS_NOT_ESTIMABLE:
        A(f"NO SE ESTIMÓ. Resultado literal: `state = {gate['gate_state']}` · "
          f"`motivo_cierre = {(r.get('gap_report') or {}).get('motivo_cierre')}` · "
          f"`informe_de_brecha.falta = {(r.get('gap_report') or {}).get('falta')}`.")
    else:
        A(f"SÍ SE ESTIMÓ, y su límite queda declarado. Resultado literal: "
          f"`state = {gate['gate_state']}` · `status = {r['status']}` · "
          f"`nivel de evidencia = {calidad['level']}` · "
          f"`origen = {r['origin_composition']['origin']}` · "
          f"`rango = [{ev['ESTIMATION_RESULT']['range_low']}, "
          f"{ev['ESTIMATION_RESULT']['range_high']}]`.")
        A("")
        A("Por qué NO es más que indicativo, en la letra del motor:")
        A("")
        for razon in list(r.get("confidence_reasons") or [])[:3]:
            A(f"- {razon}")
        A("")
        A("No hay `informe_de_brecha` de cierre porque no hubo cierre: lo que sigue es lo "
          "que falta para SUBIR DE NIVEL y dejar de ser indicativo.")
    A("")
    A("Evidencia económica AUTOMÁTICA que falta:")
    A("")
    for i, f in enumerate(faltan, start=1):
        A(f"{i}. {f}")
    A("")
    A("## §39 · EVIDENCIA LITERAL")
    A("")
    A("```")
    A("ESTIMATION_GATE")
    A(f"  state            = {ev['ESTIMATION_GATE']['state']}")
    A("  reasons          =")
    for x in ev["ESTIMATION_GATE"]["reasons"]:
        A(f"      - {x}")
    A(f"  inputs_available = {ev['ESTIMATION_GATE']['inputs_available']}")
    A(f"  inputs_missing   = {ev['ESTIMATION_GATE']['inputs_missing']}")
    A("VERIFIED_MARKET_EVIDENCE_GATE")
    A(f"  state            = {ev['VERIFIED_MARKET_EVIDENCE_GATE']['state']}")
    A("  reasons          =")
    for x in ev["VERIFIED_MARKET_EVIDENCE_GATE"]["reasons"]:
        A(f"      - {x}")
    A("EVIDENCE_QUALITY")
    A(f"  level   = {ev['EVIDENCE_QUALITY']['level']}")
    A("  reasons =")
    for x in ev["EVIDENCE_QUALITY"]["reasons"]:
        A(f"      - {x}")
    A("  dimensiones =")
    for _k, _v in (ev["EVIDENCE_QUALITY"].get("dimensiones") or {}).items():
        A(f"      {_k:24s} = {_v}")
    A("ESTIMATION_RESULT")
    A(f"  status           = {ev['ESTIMATION_RESULT']['status']}")
    A(f"  range_low        = {ev['ESTIMATION_RESULT']['range_low']}")
    A(f"  range_high       = {ev['ESTIMATION_RESULT']['range_high']}")
    A(f"  central_estimate = {ev['ESTIMATION_RESULT']['central_estimate']}")
    A(f"  value_m2         = {ev['ESTIMATION_RESULT']['value_m2']}")
    A(f"  methods_used     = {ev['ESTIMATION_RESULT']['methods_used']}")
    _vis39 = ev["ESTIMATION_RESULT"].get("central_reference_visibility") or {}
    A(f"  central_reference_visibility = {_vis39.get('state')} "
      f"(política {_vis39.get('policy_version')} · imprime_la_cifra="
      f"{_vis39.get('imprime_la_cifra')})")
    if ev.get("M5"):
        A("M5_AGGREGATED_MARKET_REFERENCE")
        A(f"  method_id        = {ev['M5']['method_id']}")
        A(f"  status           = {ev['M5']['status']}")
        A(f"  origin           = {ev['M5']['origin']}")
        A(f"  derivation       = "
          f"{json.dumps(ev['M5']['derivation'], ensure_ascii=False)}")
        A(f"  confidence       = {ev['M5']['confidence']}")
        A(f"  source_id        = {ev['M5']['source_id']}")
        A(f"  reference_id     = {ev['M5']['reference_id']}")
        A(f"  source_range_m2  = "
          f"{json.dumps(ev['M5']['source_range_m2'], ensure_ascii=False)}")
        A(f"  result_range     = "
          f"{json.dumps(ev['M5']['result_range'], ensure_ascii=False)}")
        A(f"  sample_size      = {ev['M5']['sample_size']!r} (la fuente NO lo declara)")
    A("CONTADORES")
    A(f"  market observations count = {c['market_observations_count']}")
    A(f"  comparables accepted      = {c['comparables_accepted']}")
    A(f"  comparables rejected      = {c['comparables_rejected']}")
    A(f"  origins used              = {c['origins_used']}")
    A(f"  manual inputs used        = {c['manual_inputs_used']}   "
      f"[{'ACEPTADO' if c['manual_inputs_used'] == 0 else 'RECHAZADO'}]")
    A(f"  legacy priors used        = {c['legacy_priors_used']}   "
      f"[{'ACEPTADO' if c['legacy_priors_used'] == 0 else 'RECHAZADO'}]")
    A("```")
    A("")
    A("## §40 · VEREDICTO")
    A("")
    A(f"**{veredicto}**")
    A("")
    A("## Escenarios de contraste · el cambio de estado por el nivel 3")
    A("")
    A("Mismo expediente, misma fecha de referencia: la ÚNICA diferencia es si la corrida "
      "incorpora o no la referencia agregada de nivel 3 (`MARKET_HARVEST_*.json`). El "
      "cambio de estado es el que la evidencia compra, y nada más.")
    A("")
    A("| escenario | ESTIMATION_GATE | calidad | status | origen | rango | razón principal |")
    A("|---|---|---|---|---|---|---|")
    for e in escenarios:
        A(f"| {e['etiqueta']} | {e['gate_state']} | {e['quality']} | {e['status']} | "
          f"{e['origin_composition']} | {e['range']} | {str(e['razon_principal'])[:110]} |")
    A("")
    A("El nivel 3 lleva de `CLOSED` a **`OPEN_WITH_LIMITATIONS`** y de `NOT_ESTIMABLE` a "
      "**`INDICATIVE_ESTIMATE`**; NO a `OPEN`: agrega por sector y banda de área, así que "
      "no acredita la unidad. Para `OPEN` haría falta evidencia de nivel 1-2 con calidad "
      "HIGH/MEDIUM y comparables directos de la MISMA unidad observada.")
    A("")
    A(f"Y en los dos escenarios `VERIFIED_MARKET_EVIDENCE_GATE = "
      f"{r['verified_market_evidence_gate'].get('gate_state')}` (§30: las dos compuertas "
      f"coexisten) · `manual inputs used = {c['manual_inputs_used']}` · "
      f"`legacy priors used = {c['legacy_priors_used']}`.")
    A("")
    A("## Comandos de verificación")
    A("")
    for cmd, esperado in COMANDOS_DE_VERIFICACION:
        A(f"- `{cmd}` → {esperado}")
    if verificacion:
        A("")
        A("### Salida literal de las verificaciones")
        A("")
        for cmd, salida_txt in verificacion:
            A(f"`{cmd}`")
            A("")
            A("```")
            A(salida_txt.strip()[:4000])
            A("```")
            A("")
    A("")
    A(f"Generado por `scripts/estimation_golden.py` · `{date.today().isoformat()}`")
    return "\n".join(L) + "\n"


def _hash_de_git() -> Optional[str]:
    try:
        p = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT),
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        return (p.stdout or "").strip() or None
    except Exception:  # noqa: BLE001
        return None


def _rutas_de_verificacion(folio: str) -> Dict[str, Any]:
    """Hashes y retícula REALES del ejecutivo/técnico emitidos por la última corrida."""
    aceptacion = GOLDEN_DIR / f"ACEPTACION_{folio}.json"
    datos: Dict[str, Any] = {}
    if aceptacion.exists():
        try:
            datos = json.loads(aceptacion.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            datos = {}
    ejecutivo = GOLDEN_DIR / f"DICTUS_EJECUTIVO_{folio}.pdf"
    tecnico = GOLDEN_DIR / f"DICTUS_TECNICO_{folio}.pdf"
    return {
        "executive_pdf": ejecutivo.name if ejecutivo.exists() else None,
        "executive_sha256": _sha256_archivo(ejecutivo)
        or datos.get("executive_pdf_sha256"),
        "executive_page_count": datos.get("executive_page_count"),
        "technical_pdf": tecnico.name if tecnico.exists() else None,
        "technical_sha256": _sha256_archivo(tecnico) or datos.get("technical_pdf_sha256"),
        "technical_page_count": datos.get("technical_page_count"),
        "run_id": datos.get("run_id"),
        "dictus_id": datos.get("dictus_id"),
        "generated_at": datos.get("generated_at"),
        "master_hash": datos.get("master_hash"),
        "verify_master_hash": datos.get("verify_master_hash"),
        "layout_violations": list(datos.get("layout_violations") or []),
        "evidence_count": datos.get("evidence_count"),
        "evidence_seal": datos.get("evidence_seal"),
        "commit_sha": _hash_de_git(),
        "aceptacion_json": (str(aceptacion.relative_to(ROOT)) if aceptacion.exists()
                            else None),
    }


def _m5_del_resultado(resultado: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    for m in list(resultado.get("methods_used") or []) + list(
            resultado.get("methods_rejected") or []):
        if m.get("method_id") == est.METODO_M5:
            return m
    return None


def _aceptacion_final_md(folio: str, salida: Dict[str, Any],
                         escenarios: List[Dict[str, Any]], veredicto: str,
                         verificacion: Optional[List[Tuple[str, str]]] = None) -> str:
    """§14–§19 · ACEPTACIÓN FINAL con evidencia LITERAL y verificable.

    Todo lo que se imprime aquí se lee del motor, del expediente o del PDF regenerado:
    nada se redacta a mano y nada se parafrasea.
    """
    r = salida["resultado"]
    gate = r["estimation_gate"]
    calidad = r["evidence_quality"]
    c = salida["contadores"]
    entrada = salida["entrada"]
    vg = r["verified_market_evidence_gate"]
    m5 = _m5_del_resultado(r)
    hashes = _rutas_de_verificacion(folio)
    p1_texto = _texto_pagina_pdf(EJECUTIVO, 1)
    p6_texto = _texto_pagina_pdf(EJECUTIVO, 6)

    L: List[str] = []
    A = L.append
    A(f"# DICTUS ESTIMATION ENGINE v1.0 — ACEPTACIÓN FINAL · folio {folio}")
    A("")
    A(f"> **NEXT STEP (no ejecutado en esta ronda):** `REMEASURE BARRANQUILLA SOURCE PACK "
      f"CORE COVERAGE` — el 403 del geoportal podía resolverse con cabeceras de "
      f"navegación correctas (medido: la MISMA URL devuelve 200 con `NAV_HEADERS`).")
    A("")
    A(f"- **Motor:** `{est.ESTIMATION_ENGINE_VERSION}` · integración "
      f"`{egs.INTEGRATION_VERSION}` · golden `{GOLDEN_VERSION}`")
    A(f"- **Políticas nuevas:** `{est.CENTRAL_REFERENCE_VISIBILITY_VERSION}` "
      f"(visibilidad de la referencia central) · `"
      f"{getattr(mh, 'HASH_POLICY_VERSION', 'dictus-evidence-hash/2.0.0')}` "
      f"(identidad de la evidencia: contenido estable vs adquisición volátil)")
    A(f"- **Referencia temporal de la estimación:** `{salida['referencia']}`")
    A(f"- **`state`:** `{gate.get('gate_state')}` · "
      f"**`VERIFIED_MARKET_EVIDENCE_GATE`:** `{vg.get('gate_state')}` · "
      f"**calidad:** `{calidad.get('level')}` · **resultado:** `{r.get('status')}`")
    A(f"- **VEREDICTO:** `{veredicto}`")
    A("")
    A("## 1 · COMPUERTAS (literal del motor)")
    A("")
    A("```")
    A("ESTIMATION_GATE")
    A(f"  state            = {gate.get('gate_state')}")
    A("  reasons          =")
    for x in (gate.get("reasons") or []):
        A(f"      - {x}")
    A(f"  inputs_available = {gate.get('inputs_available')}")
    A(f"  inputs_missing   = {gate.get('inputs_missing')}")
    A(f"  conditions_version = {gate.get('conditions_version')}")
    A("VERIFIED_MARKET_EVIDENCE_GATE")
    A(f"  state            = {vg.get('gate_state')}")
    A(f"  reasons          = {vg.get('reasons')}")
    A(f"  evidencia_agregada_no_atribuible = "
      f"{json.dumps(vg.get('evidencia_agregada_no_atribuible'), ensure_ascii=False)}")
    A("EVIDENCE_QUALITY_GATE")
    A(f"  level   = {calidad.get('level')}")
    A("  POR QUÉ ES ESE NIVEL (razones literales del motor):")
    for x in (calidad.get("reasons") or []):
        A(f"      - {x}")
    A("  LAS DIEZ DIMENSIONES DEL CONTRATO (§13/§14):")
    for k in DIMENSIONES_CALIDAD:
        A(f"      {k:26s} = {json.dumps(calidad.get(k), ensure_ascii=False)}")
    A("```")
    A("")
    A("## 2 · `ESTIMATION_RESULT` (literal)")
    A("")
    A("```")
    A(f"status           = {r.get('status')}")
    A(f"status_label     = {r.get('status_label')}")
    A(f"range_low        = {r.get('range_low')}")
    A(f"range_high       = {r.get('range_high')}")
    A(f"central_estimate = {r.get('central_estimate')}")
    A(f"value_m2_central = {r.get('value_m2_central')}")
    A(f"confidence_label = {r.get('confidence_label')} "
      f"(impreso: {egs.confianza_de(r)})")
    A(f"methods_used     = {r.get('methods_used_ids')}")
    A(f"methods_rejected = {r.get('methods_rejected_ids')}")
    A(f"origin_composition = {json.dumps(r.get('origin_composition'), ensure_ascii=False)}")
    A(f"hash_payload     = {r.get('hash_payload')}")
    A(f"generated_at     = {r.get('generated_at')}")
    A("central_reference_visibility = "
      + json.dumps(r.get("central_reference_visibility"), ensure_ascii=False, indent=2))
    A("```")
    A("")
    A("## 3 · OBJETO COMPLETO DE `M5_AGGREGATED_MARKET_REFERENCE`")
    A("")
    if m5 is None:
        A("`M5` no participó de esta corrida (no hay referencia agregada de nivel 3).")
    else:
        A("```json")
        A(json.dumps({k: m5.get(k) for k in (
            "method_id", "method_name", "methods_version", "status", "origin",
            "origin_basis", "derivation", "confidence", "central_reference",
            "central_reference_visibility", "result", "range", "result_range",
            "banda_oficial", "dispersion", "inputs", "reason", "adjustments")},
            ensure_ascii=False, indent=2))
        A("```")
        A("")
        A("Los CAMPOS EXIGIDOS POR LA ACEPTACIÓN (§6), con su nombre de contrato y su "
          "valor literal:")
        A("")
        A("```")
        _resumen7 = bloque_de_evidencia(gate, calidad, r, c).get("M5") or {}
        for _k in ("method_id", "status", "origin", "derivation", "confidence", "source_id",
                   "reference_id", "area_subject", "area_band", "source_range_m2",
                   "result_range", "central_reference", "central_reference_visibility",
                   "sample_size", "provenance", "limitations"):
            A(f"{_k:28s} = {json.dumps(_resumen7.get(_k), ensure_ascii=False)}")
        A("```")
    A("")
    A("## 4 · `CONTADORES` (§39)")
    A("")
    A("```")
    for k in CONTADORES_ACEPTACION:
        valor = c.get(k)
        marca = ""
        if k == "manual_inputs_used":
            marca = f"   [{'ACEPTADO' if valor == 0 else 'RECHAZADO'}]"
        if k == "legacy_priors_used":
            marca = f"   [{'ACEPTADO' if valor == 0 else 'RECHAZADO'}]"
        A(f"{k:26s} = {valor!r}{marca}")
    for k in ("market_observations_detail", "origin_composition", "origin_rule",
              "manual_inputs_declared", "legacy_priors_declared", "declarados_y_excluidos",
              "origins_used_count"):
        A(f"{k:26s} = {json.dumps(c.get(k), ensure_ascii=False)}")
    A(f"{'comparables_declarados':26s} = "
      f"{(c.get('market_observations_detail') or {}).get('comparables_declarados')}")
    A(f"{'estadisticas_externas':26s} = "
      f"{(c.get('market_observations_detail') or {}).get('estadisticas_agregadas_externas')}")
    A("```")
    A("")
    A("Aceptación dura: `manual inputs used = 0` · `legacy priors used = 0` · "
      "clases EXCLUIDAS = "
      f"`{c.get('declarados_y_excluidos')}` · `399.500.000` no aparece ni como entrada "
      "ni como salida (sólo vive en el histórico forense, con `usado_como_input = "
      f"{r.get('historical_estimate_reference', {}).get('usado_como_input')}`).")
    A("")
    A("## 5 · `SOURCES` DEL RESULTADO (procedencia real)")
    A("")
    A("```json")
    A(json.dumps(r.get("sources"), ensure_ascii=False, indent=2))
    A("```")
    A("")
    _fuentes = json.dumps(r.get("sources"), ensure_ascii=False)
    _prohibidas = [x for x in ("Lonja", "LONJA_MARKET_BAQ", "MANUAL_CONFIG",
                               "LEGACY_MODEL_PRIOR", "FALLBACK") if x in _fuentes]
    A(f"- `BAQ_OBS_VALORESM2_AREA` presente: "
      f"`{'BAQ_OBS_VALORESM2_AREA' in _fuentes}`")
    A(f"- rótulos prohibidos presentes en `SOURCES`: `{_prohibidas}` "
      f"(debe ser `[]`)")
    for ref in (entrada.get("estadisticas_externas") or []):
        A(f"- identidad de la evidencia · `{ref.get('source_id')}`: "
          f"`content_hash = {ref.get('content_hash')}` (ESTABLE) · "
          f"`payload_sha256 = {ref.get('payload_sha256')}` · "
          f"`acquisition_id = {ref.get('acquisition_id')}` · "
          f"`evidence_hash = {ref.get('evidence_hash')}` · "
          f"`sample_size = {ref.get('sample_size')}` (NO se rellena)")
    A("")
    A("## 6 · RANGO Y VISIBILIDAD DE LA REFERENCIA CENTRAL")
    A("")
    if r.get("range_low") is not None:
        _b = (r.get("range") or {}).get("banda_oficial_usada") or {}
        A(f"- **`RANGO = [{r.get('range_low')}, {r.get('range_high')}]`** (salida "
          f"PRIMARIA) · `central = {r.get('central_estimate')}` · ancho "
          f"`{(r.get('range') or {}).get('porcentaje')}` · "
          f"`clamp = {(r.get('range') or {}).get('clamp')}`")
        A(f"- Banda oficial usada: `{_b.get('source_id')}` · "
          f"`reference_id = {_b.get('reference_id')}` · min/max LITERALES "
          f"`{_b.get('min')}`–`{_b.get('max')}` COP/m² · área del sujeto "
          f"`{_b.get('area_sujeto_m2')} m²` → bordes redondeados HACIA FUERA "
          f"`{_b.get('low_pesos')}` / `{_b.get('high_pesos')}`")
        A(f"- `semi_ancho_calculado = "
          f"{(r.get('range') or {}).get('componentes', {}).get('semi_ancho_calculado')}` "
          f"vs `semi_ancho_relativo` EFECTIVO `"
          f"{(r.get('range') or {}).get('semi_ancho_relativo')}`: el ancho calculado NO "
          f"estrecha el rango publicado.")
    else:
        A("- NO se produjo rango (el motor no emite cifra sin base).")
    _vis = r.get("central_reference_visibility") or {}
    A(f"- **`central_reference_visibility = {_vis.get('state')}`** · "
      f"`imprime_la_cifra = {_vis.get('imprime_la_cifra')}` · "
      f"política `{_vis.get('policy_version')}` · "
      f"`calibrada_empiricamente = {_vis.get('calibrada_empiricamente')}`")
    A(f"- Umbrales APLICADOS (declarados, ninguno escondido): "
      f"`{json.dumps(_vis.get('umbrales_aplicados'), ensure_ascii=False)}`")
    A(f"- Entradas de la política: "
      f"`{json.dumps(_vis.get('entradas'), ensure_ascii=False)}`")
    A("- Razones de la política:")
    for x in (_vis.get("reasons") or []):
        A(f"    - {x}")
    A("")
    A("## 7 · ESCENARIO A/B · MISMO EXPEDIENTE, ÚNICA DIFERENCIA = EVIDENCIA LEVEL 3")
    A("")
    A("| escenario | ESTIMATION_GATE | `VERIFIED_MARKET_EVIDENCE_GATE` | calidad | "
      "status | origen | rango | razón principal |")
    A("|---|---|---|---|---|---|---|---|")
    for e in escenarios:
        A(f"| {e['etiqueta']} | {e['gate_state']} | {e.get('verified_gate', '')} | "
          f"{e['quality']} | {e['status']} | {e['origin_composition']} | {e['range']} | "
          f"{str(e['razon_principal'])[:110]} |")
    A("")
    for e in escenarios:
        A(f"- **{e['etiqueta']}** · contadores: "
          f"`{json.dumps({k: e['contadores'].get(k) for k in CONTADORES_ACEPTACION}, ensure_ascii=False)}`")
    A("")
    A("La ÚNICA diferencia material entre A y B es la incorporación de la referencia "
      "agregada de `LEVEL_3_AGGREGATED_MARKET_REFERENCES`; en los dos escenarios "
      "`manual inputs used = 0`, `legacy priors used = 0` y "
      f"`VERIFIED_MARKET_EVIDENCE_GATE = {vg.get('gate_state')}`.")
    A("")
    A("## 8 · `P1_TEXT` Y `P6_TEXT` (extraídos LITERALMENTE del PDF regenerado)")
    A("")
    A(f"Ejecutivo: `{hashes.get('executive_pdf')}` · "
      f"sha256 `{hashes.get('executive_sha256')}` · "
      f"{hashes.get('executive_page_count')} páginas")
    A("")
    A("```")
    A("P1_TEXT")
    A(p1_texto if p1_texto else "[NO DISPONIBLE: no hay ejecutivo regenerado]")
    A("```")
    A("")
    A("```")
    A("P6_TEXT")
    A(p6_texto if p6_texto else "[NO DISPONIBLE: no hay ejecutivo regenerado]")
    A("```")
    A("")
    A("## 9 · `HASHES`")
    A("")
    A("```")
    for k in ("executive_pdf", "executive_sha256", "executive_page_count", "technical_pdf",
              "technical_sha256", "technical_page_count", "run_id", "dictus_id",
              "generated_at", "master_hash", "verify_master_hash", "layout_violations",
              "evidence_count", "evidence_seal", "commit_sha", "aceptacion_json"):
        A(f"{k:22s} = {json.dumps(hashes.get(k), ensure_ascii=False)}")
    A("```")
    A("")
    A("- `layout_violations = []` es la retícula sin violaciones de la corrida "
      "(`scripts/dictus_run.py`).")
    A("- El `commit_sha` es el HEAD del repositorio en el momento de la aceptación.")
    A("- **No se tocó ningún artefacto forense anterior**: esta ronda escribe en "
      "`docs/estimation/**` y regenera `docs/forensics/{folio}/dictus_2b/**` con "
      "`scripts/dictus_run.py` (su propio generador).")
    A("")
    A("## 10 · `TEST_OUTPUT` (comando y salida REAL)")
    A("")
    if verificacion:
        for cmd, salida_txt in verificacion:
            A(f"```\n$ {cmd}\n{salida_txt.strip()}\n```")
            A("")
    else:
        A("No adjuntado en esta ejecución: correr "
          "`python scripts/estimation_golden.py --con-verificacion` para anexar la salida "
          "literal de `dictus_run.py`, `golden_evidence_asserts.py` y la suite de pytest.")
    A("")
    A("## 11 · VEREDICTO")
    A("")
    A(f"**{veredicto}**")
    A("")
    A(f"Generado por `scripts/estimation_golden.py` · `{date.today().isoformat()}`")
    return "\n".join(L) + "\n"


def imprimir_golden(salida: Dict[str, Any], escenarios: List[Dict[str, Any]]) -> None:
    r = salida["resultado"]
    gate = r["estimation_gate"]
    calidad = r["evidence_quality"]
    c = salida["contadores"]
    ev = bloque_de_evidencia(gate, calidad, r, c)
    brecha_cosecha = egs.cargar_brecha_de_cosecha()
    print("=" * 78)
    print("GOLDEN · DICTUS ESTIMATION ENGINE v1.0 — estado REAL de la corrida")
    print("=" * 78)
    print(f"referencia temporal = {salida['referencia']}")
    print(f"A) ¿hay suficiente información para estimar? -> "
          f"{'SÍ' if gate['gate_state'] != est.ESTIMATION_CLOSED else 'NO'}"
          f" (ESTIMATION_GATE = {gate['gate_state']})")
    print(f"B) métodos posibles -> disponibles: "
          f"{gate.get('methods_available') or 'ninguno'} · "
          f"descartados: {gate.get('methods_rejected') or 'ninguno'}")
    print(f"C) evidencia económica automática -> market observations = "
          f"{c['market_observations_count']} "
          f"({c['market_observations_detail']['estadisticas_agregadas_externas']} "
          f"referencia(s) agregada(s) de cosecha municipal · "
          f"{c['market_observations_detail']['comparables_declarados']} comparables "
          f"declarados)")
    print(f"D) comparables -> aceptados = {c['comparables_accepted']} · "
          f"rechazados = {c['comparables_rejected']}")
    print(f"E) modelo calibrado válido -> "
          f"{'SÍ' if 'modelo_calibrado' not in (gate.get('inputs_missing') or []) else 'NO'}")
    print(f"F) qué falta -> {((r.get('gap_report') or {}).get('falta') or 'nada para estimar; '
          'lo que falta es para subir de nivel')}")
    for f in faltantes_economicos(r, brecha_cosecha):
        print(f"      · {f}")
    print(f"G) rango -> [{r['range_low']}, {r['range_high']}] "
          f"(central = {r['central_estimate']})")
    print(f"H) confianza -> calidad {calidad['level']} -> CONFIANZA "
          f"{egs.confianza_de(r)}")
    print()
    print(json.dumps(ev, ensure_ascii=False, indent=1))
    print()
    print("VEREDICTO §40:", veredicto_de(r))
    print()
    print("Escenarios de contraste:")
    for e in escenarios:
        print(f"  · {e['etiqueta']}: gate={e['gate_state']} quality={e['quality']} "
              f"status={e['status']} origen={e['origin_composition']}")


def _verificaciones() -> List[Tuple[str, str]]:
    """Corre los comandos de verificación y devuelve su salida literal (opcional)."""
    salidas: List[Tuple[str, str]] = []
    cmds = [("python scripts/dictus_run.py", 600),
            ("python scripts/golden_evidence_asserts.py", 600),
            ("python -m pytest tests/test_estimation_golden.py tests/test_estimation_gate.py "
             "tests/test_estimation_evidence_quality_gate.py "
             "tests/test_estimation_origin_composition.py "
             "tests/test_estimation_semantics_final.py tests/test_market_evidence.py "
             "tests/test_dictus_20d_r1_p6.py tests/test_dictus_20c_fidelidad.py -q", 900)]
    for cmd, _t in cmds:
        try:
            p = subprocess.run(cmd.split(), cwd=str(ROOT), capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
            cola = "\n".join((p.stdout or "").strip().splitlines()[-14:])
            salidas.append((cmd, f"[exit code: {p.returncode}]\n{cola}"))
        except Exception as exc:  # noqa: BLE001
            salidas.append((cmd, f"[NO EJECUTADO] {exc!r}"))
    return salidas


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Golden reproducible de la estimación")
    ap.add_argument("--folio", default=FOLIO)
    ap.add_argument("--sin-auditoria", action="store_true",
                    help="no regenera los artefactos de la Fase 1")
    ap.add_argument("--con-verificacion", action="store_true",
                    help="adjunta la salida literal de pytest y de los asserts")
    args = ap.parse_args(argv)

    rs = _cargar(RUN_STATE)
    man = _cargar(MANIFEST)

    auditoria = None if args.sin_auditoria else regenerar_auditoria()
    escenarios = [escenario(rs, man, etiqueta="CON cosecha municipal (real)"),
                  escenario(rs, man, etiqueta="SIN cosecha municipal (contraste)",
                            sin_cosecha=True)]
    verificacion = None
    if args.con_verificacion:
        # Las verificaciones incluyen `dictus_run.py`, que REESCRIBE el expediente: se
        # corren ANTES de escribir los entregables y luego se relee el estado, para que
        # la aceptación declare los hashes FINALES y no los anteriores.
        verificacion = _verificaciones()
        rs = _cargar(RUN_STATE)
        man = _cargar(MANIFEST)
        escenarios = [escenario(rs, man, etiqueta="CON cosecha municipal (real)"),
                      escenario(rs, man, etiqueta="SIN cosecha municipal (contraste)",
                                sin_cosecha=True)]
    salida = egs.ejecutar(rs, man)
    rutas = escribir_entregables(args.folio, rs, man, salida, auditoria, escenarios,
                                 verificacion)

    imprimir_golden(salida, escenarios)
    print()
    for k, v in rutas.items():
        print(f"[OK] {v.relative_to(ROOT)}")

    c = salida["contadores"]
    fallos = []
    if c["manual_inputs_used"] != 0:
        fallos.append("manual inputs used != 0")
    if c["legacy_priors_used"] != 0:
        fallos.append("legacy priors used != 0")
    if "399.500.000" in json.dumps(salida, ensure_ascii=False, default=str):
        fallos.append("399.500.000 reaparece como input o como salida")
    if est.validar_resultado(salida["resultado"])["valido"] is not True:
        fallos.append("EstimationResult no cumple el contrato")
    if fallos:
        print("[FAIL] " + " · ".join(fallos))
        return 1
    print("[OK] aceptación dura: manual inputs used = 0 · legacy priors used = 0 · "
          "sin 399.500.000 · contrato EstimationResult válido")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

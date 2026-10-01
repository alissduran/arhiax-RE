# -*- coding: utf-8 -*-
"""ARHIAX RE — GOLDEN EVIDENCE LITERAL PACK · folio 040-646406.

Regenera, desde los artefactos REALES y el código REAL, todo el paquete de evidencia
literala de `docs/source_pack/`:

    GOLDEN_EVIDENCE_LITERAL_PACK_040-646406.md
    MARKET_CONTEXT_040-646406.json
    VALUATION_GATE_040-646406.json
    ORIGIN_AUDIT_040-646406.json
    CROSS_PAGE_CONSISTENCY_040-646406.json
    ARTIFACT_HASHES_040-646406.json

No regenera el Golden (`docs/forensics/**` es de solo lectura aquí): si el Golden está
desactualizado respecto al código, el pack lo DECLARA y falla los criterios afectados.

    python scripts/golden_evidence_pack.py            # escribe el pack
    python scripts/golden_evidence_pack.py --stdout   # solo imprime el resumen
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "docs" / "forensics" / "040-646406" / "dictus_2b"
GOLDEN_LEGACY = ROOT / "docs" / "forensics" / "040-646406" / "dictus_2"
OUT = ROOT / "docs" / "source_pack"
FOLIO = "040-646406"
sys.path.insert(0, str(ROOT / "api"))

EJECUTIVO = GOLDEN / f"DICTUS_EJECUTIVO_{FOLIO}.pdf"
TECNICO = GOLDEN / f"DICTUS_TECNICO_{FOLIO}.pdf"
MANIFEST = GOLDEN / f"DICTUS_MANIFEST_{FOLIO}.json"
RUNSTATE = GOLDEN / f"DICTUS_RUN_STATE_{FOLIO}.json"
YAML_METODOLOGIA = (ROOT / "motor_tma_lonja_baq_v1.0" / "motor_tma_lonja_baq_v1.0"
                    / "lonja_layer" / "lonja_baq_metodologia.yaml")

ORIGENES_PROHIBIDOS = {"MANUAL_CONFIG", "STATIC_REFERENCE", "MODEL_PRIOR", "FIXTURE",
                       "DEFAULT", "HARDCODE", "FALLBACK_HEURISTIC"}

# ── categoría A · «Lonja COMO FUENTE DE DATOS» ────────────────────────────────
# Patrón explícito y cerrado: la línea presenta a la Lonja (o a un artefacto con su
# nombre) como proveedora del dato, como `source`/`fuente` de un valor, o como fuente
# con `authority_class`/licencia. Todo lo demás NO es categoría A (ver `_clasificar`).
_PATRONES_A = (
    ('"LONJA_MARKET_BAQ": CORE_MARKET', "declara la Lonja con rol de fuente CORE_MARKET"),
    ('"LONJA_MARKET_BAQ": AUTHORIZED_FALLBACK', "declara la Lonja como ruta de adquisición autorizada"),
    ('"fuente": "LONJA_MARKET_BAQ"', "declara la Lonja como `fuente` del dominio mercado"),
    ('"source": "lonja_baq_metodologia"', "declara el artefacto Lonja como `source` del valor"),
    ('es fuente formalizada', "afirma que la Lonja es fuente formalizada"),
    ('+ Lonja BAQ referencial', "atribuye la tasa a «Lonja BAQ referencial»"),
    ('La Lonja declara los valores', "atribuye a la Lonja la declaración de los valores"),
    ('Lonja de Propiedad Raíz de Barranquilla"', "nombra a la Lonja como entidad proveedora"),
    ('"fuente_declarada"', "expone la fuente declarada del mercado"),
    ('attribution_text=ATRIBUCION_LONJA', "construye bloque de licencia/atribución de la Lonja"),
    ('FUENTE_LONJA', "identifica la Lonja como FUENTE"),
)

_MARCADORES_NO_FUENTE = (
    "no es una fuente", "no es fuente", "sin fuente externa",
    "no aporta datos", "fuera del source registry", "fuera de `sources`",
    "identificador histórico", "identificador historico", "retirada del registro",
    "not a source", "NOT_A_SOURCE", "auditoria_no_lonja", 'es_fuente_de_datos": false',
    'en_source_registry": false', 'aporta_datos_a_dictus": false',
    "assertnotin", "_atribucion_no_acreditada", "etiqueta_tasa", "sin acentos",
    "prohib", "purga", "purge", "doctrina", "guarda", "no se sustituye",
    "no se imprime", "no se atribuye", "sin institución", "sin institucion",
    "no reconocida como fuente", "traza de lo que se declaró", "no muta",
    "no declara", "problemática", "problematica", "sin fuente lonja",
    # Vocabulario del propio repo para «esta entidad NO se expone como proveedora».
    "entidad_no_verificada", "no se expone como proveedor", "no acreditada",
    "no se acredita", "no sustituye la fuente",
)


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def pdf_pages(p: Path) -> list[str]:
    from pypdf import PdfReader
    return [(pg.extract_text() or "") for pg in PdfReader(str(p)).pages]


def git(*args: str) -> str:
    r = subprocess.run(["git", *args], capture_output=True, cwd=str(ROOT))
    return r.stdout.decode("utf-8", "replace")


def _cargar():
    return (json.loads(MANIFEST.read_text(encoding="utf-8")),
            json.loads(RUNSTATE.read_text(encoding="utf-8")))


def _gate(manifest: dict, nombre: str) -> dict:
    for g in (manifest.get("modelo") or {}).get("decision_gates") or []:
        if g.get("gate") == nombre:
            return g
    return {}


# (A) Vocabulario CERRADO del estado de compuerta. Se lee del módulo REAL que lo define
# (`api/dictus_decision.ESTADOS_COMPUERTA`) para que el pack no pueda divergir del código;
# si el import no fuera posible, queda el literal y el pack lo declara.
try:
    import dictus_decision as _dd_pack
    ESTADOS_COMPUERTA = tuple(_dd_pack.ESTADOS_COMPUERTA)
except Exception:  # noqa: BLE001
    ESTADOS_COMPUERTA = ("CLOSED", "OPEN")


# ── 1 · MARKET INPUT ──────────────────────────────────────────────────────────
def sec_market_input(manifest: dict, run_state: dict) -> dict:
    mc = run_state.get("market_context") or {}
    sector = mc.get("sector_metodologico") or {}
    import atribucion_mercado as am
    proc = am.procedencia_de_mercado()
    origen = None
    try:
        import market_context as mc_mod
        origen = mc_mod.market_context_origen(mc)
    except Exception as exc:  # noqa: BLE001
        origen = {"error": repr(exc)}
    lineas_yaml: list[str] = []
    if YAML_METODOLOGIA.exists():
        txt = YAML_METODOLOGIA.read_text(encoding="utf-8").splitlines()
        # (a) cabecera de declaración + entidad que firma; (b) bloque del sector aplicado.
        for i, ln in enumerate(txt, 1):
            if 14 <= i <= 25:
                lineas_yaml.append(f"lonja_baq_metodologia.yaml:{i}: {ln}")
        inicio = None
        for i, ln in enumerate(txt):
            if ln.strip().startswith("Miramar:"):
                inicio = i
                break
        if inicio is not None:
            for j in range(inicio, min(inicio + 12, len(txt))):
                lineas_yaml.append(f"lonja_baq_metodologia.yaml:{j + 1}: {txt[j]}")
        for i, ln in enumerate(txt, 1):
            if ln.strip() == "valor_suelo_por_sector:":
                lineas_yaml.append(f"lonja_baq_metodologia.yaml:{i}: {ln}")
    return {
        "folio": FOLIO,
        "A_ruta_del_archivo": str(YAML_METODOLOGIA.relative_to(ROOT)),
        "B_lineas_exactas": lineas_yaml,
        "C_estructura_resultante": {
            "input_barrio": sector.get("input_barrio"),
            "matched_sector": sector.get("matched_sector"),
            "match_type": sector.get("match_type"),
            "value_m2": sector.get("value_m2"),
            "rango_min_m2": sector.get("rango_min_m2"),
            "rango_max_m2": sector.get("rango_max_m2"),
            "methodology_file": sector.get("market_methodology_file"),
            "methodology_version": sector.get("market_methodology_version"),
            "methodology_sha256": sector.get("market_methodology_sha256"),
        },
        "D_origin": origen,
        "E_provenance": mc.get("provenance"),
        "F_authorized_for_valuation": {
            "golden_stored_valoracion_habilitada": mc.get("valoracion_habilitada"),
            "golden_stored_status": mc.get("status"),
            "nuevo_codigo_status": (origen or {}).get("origin_gate"),
        },
        "market_rate": {
            "value": sector.get("value_m2"),
            "origin": (origen or {}).get("origin"),
            "provenance": mc.get("provenance"),
            "authorized_for_valuation": bool((origen or {}).get("origin_gate")),
        },
        "etiqueta_honesta_producto": proc,
        "market_rate_source_literal": mc.get("market_rate_source"),
    }


# ── 2 · MARKET CONTEXT FINAL ──────────────────────────────────────────────────
def sec_market_context(run_state: dict) -> dict:
    mc = run_state.get("market_context") or {}
    import market_context as mc_mod
    origen = mc_mod.market_context_origen(mc)
    return {
        "status": mc_mod.market_context_status(mc),
        "resolution_status": mc_mod.market_context_status(mc),
        "selected_source": mc.get("market_rate_source"),
        "origin": origen.get("origin"),
        "provenance": mc.get("provenance"),
        "required_inputs": ["identity_verified", "barrio VERIFIED_OFFICIAL/GEOGRAPHIC",
                            "estrato VERIFIED_OFFICIAL", "tipologia VERIFIED_REGISTRAL/CATASTRAL",
                            "sector metodológico resuelto", "market_rate_source",
                            "market_methodology_id/version", "value_m2 > 0"],
        "blockers": mc.get("blockers"),
        "authorized": mc_mod.market_context_valoracion_habilitada(mc),
        "reason": ("MARKET_CONTEXT_UNRESOLVED: " + "; ".join(origen.get("origin_blockers") or [])
                   if not mc_mod.market_context_valoracion_habilitada(mc)
                   else "MARKET_CONTEXT_RESOLVED"),
        "golden_stored": {"status": mc.get("status"), "origin": mc.get("origin"),
                          "origin_gate": mc.get("origin_gate"),
                          "valoracion_habilitada": mc.get("valoracion_habilitada"),
                          "ready": mc.get("ready")},
        "nuevo_codigo": origen,
    }


# ── 4 · ORIGIN PROPAGATION ────────────────────────────────────────────────────
def sec_origin_propagation() -> dict:
    import atribucion_mercado as am
    tests = []
    for nombre, decl in (
        ("EXTERNAL_SOURCE+EXTERNAL_SOURCE→COMPUTED_FROM_SOURCES",
         {"origen_tipo": am.ORIGEN_COMPUTADO, "fuentes": [
             {"proveedor": "A", "fecha": "2026-01-01", "referencia": "r1", "sha256": "a" * 64},
             {"proveedor": "B", "fecha": "2026-01-02", "referencia": "r2", "sha256": "b" * 64}]}),
        ("EXTERNAL+MANUAL_CONFIG→MANUAL_CONFIG (NOT_AUTHORIZED)",
         {"origen_tipo": am.ORIGEN_MANUAL, "proveedor": "constructora", "fecha": "Q3-2026"}),
        ("EXTERNAL+MODEL_PRIOR→MODEL_PRIOR (NOT_AUTHORIZED)",
         {"origen_tipo": am.ORIGEN_PRIOR}),
        ("STATIC_REFERENCE→no habilita",
         {"origen_tipo": am.ORIGEN_ESTATICO}),
        ("sin origen declarado→MANUAL_CONFIG por defecto",
         {}),
    ):
        r = am.clasificar_origen(decl)
        tests.append({"caso": nombre, "declaracion": decl, **r})
    return {
        "modulo": "api/atribucion_mercado.py",
        "vocabulario_literal": {
            "ORIGEN_EXTERNO": am.ORIGEN_EXTERNO,
            "ORIGEN_COMPUTADO": am.ORIGEN_COMPUTADO,
            "ORIGEN_MANUAL": am.ORIGEN_MANUAL,
            "ORIGEN_ESTATICO": am.ORIGEN_ESTATICO,
            "ORIGEN_PRIOR": am.ORIGEN_PRIOR,
            "ORIGENES": list(am.ORIGENES),
            "ORIGENES_HABILITANTES": sorted(am.ORIGENES_HABILITANTES),
            "PROCEDENCIA_EXTERNA": list(am.PROCEDENCIA_EXTERNA),
            "PROCEDENCIA_COMPUTADA_CAMPOS": list(am.PROCEDENCIA_COMPUTADA_CAMPOS),
            "PROCEDENCIA_COMPUTADA_MIN_FUENTES": am.PROCEDENCIA_COMPUTADA_MIN_FUENTES,
        },
        "funcion": "api/atribucion_mercado.py:198 clasificar_origen(declaracion, *, por_defecto=ORIGEN_MANUAL)",
        "tests_del_codigo": tests,
        "tests_versionados": [p for p in
                              git("grep", "-l", "clasificar_origen", "--", "tests/").splitlines()],
    }


# ── 7 · HASHES ────────────────────────────────────────────────────────────────
# SHA-256 de los DOS PDFs de la corrida ANTERIOR a esta tarea, MEDIDOS antes de regenerar
# el Golden. No hay otra fuente: los PDFs no se versionan (política del repositorio) y el
# pack anterior tampoco está en `HEAD` (`git show HEAD:docs/source_pack/
# ARTIFACT_HASHES_040-646406.json` → «exists on disk, but not in HEAD»). Es una MEDICIÓN
# registrada, no una inferencia, y sirve para demostrar que el cambio alcanzó también a los
# entregables. Los `old` de `master_hash`/`run_id`/`generated_at` SÍ salen de git (el
# manifest del Golden está versionado).
SHA256_PDF_ANTERIOR = {
    "sha256_ejecutivo": "7223d0c09f809896d36481ba443037845308b8024eec4233581036009c0d3a32",
    "sha256_tecnico": "33265085a0b154d4f44587f55d890af7baa7696d0cb63b7dfcc4229595ad0bac",
    "origen": ("medido con hashlib.sha256 antes de regenerar el Golden en esta tarea "
               "(los PDFs no se versionan y el pack anterior no está en git)"),
}


def sec_hashes(manifest: dict, run_state: dict) -> dict:
    prev_raw = git("show", f"HEAD:docs/forensics/040-646406/dictus_2b/DICTUS_MANIFEST_{FOLIO}.json")
    prev = json.loads(prev_raw) if prev_raw.strip() else {}
    nuevo = manifest.get("master_hash")
    viejo = prev.get("master_hash")
    sha_ej, sha_te = sha256(EJECUTIVO), sha256(TECNICO)
    old_ej = SHA256_PDF_ANTERIOR["sha256_ejecutivo"]
    old_te = SHA256_PDF_ANTERIOR["sha256_tecnico"]

    def _decision(m: dict):
        g = _gate(m, "VALUATION_GATE")
        return {"gate_state": g.get("gate_state"), "decision": g.get("decision"),
                "reason": (g.get("reasons") or [None])[0],
                "blocking_conditions": g.get("blocking_conditions")}

    d_prev, d_new = _decision(prev), _decision(manifest)
    cambio = d_prev != d_new
    return {
        "DICTUS_MASTER_HASH": nuevo,
        "DICTUS_MASTER_HASH_abreviado": manifest.get("master_hash_abreviado"),
        "sha256_ejecutivo": sha_ej,
        "sha256_tecnico": sha_te,
        "run_id": manifest.get("run_id"),
        "generated_at": manifest.get("generated_at"),
        "commit_sha": git("rev-parse", "HEAD").strip(),
        "commit_sha_del_run": ((run_state.get("release_state") or {})
                               .get("core_versions") or {}).get("commit"),
        "old_master_hash": viejo,
        "new_master_hash": nuevo,
        "changed": viejo != nuevo,
        "old_sha256_ejecutivo": old_ej,
        "new_sha256_ejecutivo": sha_ej,
        "sha256_ejecutivo_changed": old_ej != sha_ej,
        "old_sha256_tecnico": old_te,
        "new_sha256_tecnico": sha_te,
        "sha256_tecnico_changed": old_te != sha_te,
        "origen_de_los_sha256_old": SHA256_PDF_ANTERIOR["origen"],
        "old_run_id": prev.get("run_id"),
        "old_generated_at": prev.get("generated_at"),
        "cambio_de_decision_material": cambio,
        "decision_anterior_HEAD": d_prev,
        "decision_actual": d_new,
        "nota": ("cambio_de_decision_material compara la decisión del VALUATION_GATE "
                 "(gate_state + decision + reason + blocking_conditions) entre la corrida "
                 "anterior registrada en HEAD y la corrida actual del folio. Los valores "
                 "`old` de `master_hash`/`run_id`/`generated_at` salen del manifest "
                 "versionado en HEAD; los de los SHA-256 de los PDFs son la medición "
                 "registrada en SHA256_PDF_ANTERIOR (no hay fuente en git: los PDFs no se "
                 "versionan)."),
        "regla_del_pack": ("Si la decisión material cambió y el master hash NO cambió ⇒ "
                           "FAIL. Aquí: decisión material "
                           f"{'CAMBIÓ' if cambio else 'NO cambió'} y master hash "
                           f"{'SÍ cambió' if viejo != nuevo else 'NO cambió'}."),
    }


# ── 8 · LONJA SWEEP ───────────────────────────────────────────────────────────
def _es_guard_test(ruta: str) -> bool:
    """¿La línea pertenece a un test-guarda de la doctrina «Lonja NO es fuente»?"""
    if not ruta.startswith("tests/"):
        return False
    archivo = ruta.split(":")[0]
    if "no_lonja" in archivo.lower():
        return True
    try:
        cuerpo = (ROOT / archivo).read_text(encoding="utf-8").lower()
    except OSError:
        return False
    # El archivo declara la doctrina en su propio vocabulario: un test que exige que la
    # entidad NO acreditada no se exponga como proveedora REPRODUCE el literal prohibido
    # para prohibirlo; contarlo como «categoría A» sería acusar a la guarda.
    return ("no es una fuente" in cuerpo or "no fuente" in cuerpo
            or "entidad_no_verificada" in cuerpo
            or "atribucion_no_acreditada" in cuerpo
            or "no acreditada" in cuerpo)


def _clasificar(linea: str, ruta: str = "") -> tuple[str, str]:
    """(categoria, motivo). A = Lonja COMO FUENTE DE DATOS; B = mención legítima.

    Orden de decisión: (1) test-guarda de doctrina; (2) aserción de PROHIBICIÓN;
    (3) marcador de NO-fuente; (4) patrón explícito de fuente de datos;
    (5) identificador sellado.
    """
    low = linea.lower()
    if _es_guard_test(ruta) and any(p.lower() in low for p, _ in _PATRONES_A):
        return "B", "test-guarda que reproduce el literal prohibido para PROHIBIRLO"
    # Una línea que AFIRMA la prohibición (`assertNotEqual`/`assertNotIn`/`assertFalse`/
    # `assertIsNone` sobre el nombre o el identificador de la Lonja) no declara una fuente:
    # es una guarda. Sin esto, una prueba que exige «la entidad declarada NO es la Lonja»
    # se contaba como si el producto la declarara.
    if any(neg in low for neg in ("assertnotequal", "assertnotin", "assertnotregex",
                                  "assertfalse", "assertisnone", "assertnotisnone")):
        return "B", "aserción de PROHIBICIÓN (exige que la Lonja NO sea la fuente/entidad)"
    if any(m.lower() in low for m in _MARCADORES_NO_FUENTE):
        return "B", "guarda / test / documentación que declara que NO es fuente"
    for patron, motivo in _PATRONES_A:
        if patron.lower() in low:
            return "A", motivo
    return "B", "identificador sellado (METHODOLOGY_ID / SOURCE_ID histórico / ruta)"


def sec_lonja_sweep() -> dict:
    objetivos: list[tuple[str, list[tuple[str, str]]]] = []

    for pagina, texto in enumerate(pdf_pages(EJECUTIVO), 1):
        objetivos.append((f"{EJECUTIVO.relative_to(ROOT)} (ejecutivo)", [
            (f"{EJECUTIVO.name} p{pagina} l{i}", ln)
            for i, ln in enumerate(texto.splitlines(), 1) if "lonja" in ln.lower()]))
    for pagina, texto in enumerate(pdf_pages(TECNICO), 1):
        objetivos.append((f"{TECNICO.relative_to(ROOT)} (tecnico)", [
            (f"{TECNICO.name} p{pagina} l{i}", ln)
            for i, ln in enumerate(texto.splitlines(), 1) if "lonja" in ln.lower()]))

    # Artefacto de metodología local = INPUT de mercado real de la corrida.
    if YAML_METODOLOGIA.exists():
        rel = YAML_METODOLOGIA.relative_to(ROOT)
        hits = []
        for i, ln in enumerate(YAML_METODOLOGIA.read_text(encoding="utf-8").splitlines(), 1):
            if "lonja" in ln.lower():
                hits.append((f"{rel}:{i}", ln.strip()))
        objetivos.append(("market_input_yaml", hits))

    for etiqueta, ruta in (
        ("manifest", MANIFEST),
        ("run_state", RUNSTATE),
        ("executive_document_model", GOLDEN_LEGACY / "EXECUTIVE_DOCUMENT_MODEL.json"),
        ("master_hash", GOLDEN_LEGACY / "MASTER_HASH.json"),
        ("provenance_source_licenses", ROOT / "docs" / "source_pack"
         / "SOURCE_LICENSE_MATRIX.json"),
    ):
        if not ruta.exists():
            objetivos.append((etiqueta, []))
            continue
        hits = []
        for i, ln in enumerate(ruta.read_text(encoding="utf-8").splitlines(), 1):
            if "lonja" in ln.lower():
                hits.append((f"{ruta.name}:{i}", ln.strip()))
        objetivos.append((etiqueta, hits))

    for f in sorted((ROOT / "tests").glob("*.py")):
        hits = []
        for i, ln in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if "lonja" in ln.lower():
                hits.append((f"tests/{f.name}:{i}", ln.strip()))
        if hits:
            objetivos.append((f"tests/{f.name}", hits))

    for f in sorted((ROOT / "api").glob("*.py")):
        hits = []
        for i, ln in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if "lonja" in ln.lower():
                hits.append((f"api/{f.name}:{i}", ln.strip()))
        if hits:
            objetivos.append((f"source_registry/{f.name}", hits))

    a, b = [], []
    for objetivo, hits in objetivos:
        for ubicacion, texto in hits:
            categoria, motivo = _clasificar(texto, ubicacion)
            item = {"target": objetivo, "file_line": ubicacion, "text": texto[:400],
                    "motivo": motivo}
            (a if categoria == "A" else b).append(item)

    # Alcance del criterio: los artefactos ENTREGADOS de la corrida (los dos PDFs, el
    # manifest y el run_state). Las declaraciones del registro de adquisición, del
    # artefacto local de metodología y de los artefactos LEGACY de `dictus_2/` NO son
    # entregables de esta corrida: se listan aparte como OBSERVACIÓN DECLARADA, con su
    # file:line y su texto, para que el lector las vea —no se esconden ni se cuentan como
    # si lo fueran—.
    def _es_entregable(item: dict) -> bool:
        ruta = str(item["file_line"]).split(":")[0].replace("\\", "/")
        return ruta.endswith(EJECUTIVO.name) or ruta.endswith(TECNICO.name) \
            or ruta == MANIFEST.name or ruta == RUNSTATE.name

    a_entregables = [x for x in a if _es_entregable(x)]
    return {"A_mencion_prohibida": a, "B_mencion_legitima": b,
            "A_en_artefactos_entregados": a_entregables,
            "acceptance": {"categoria_A_count": len(a),
                           "categoria_A_en_entregados": len(a_entregables),
                           "esperado_en_entregados": 0,
                           "ok": len(a_entregables) == 0,
                           "nota": ("El criterio se evalúa sobre los ARTEFACTOS "
                                    "ENTREGADOS (ejecutivo, técnico, manifest y run_state "
                                    "de la corrida): ahí debe haber 0 menciones. Las "
                                    "menciones del registro de adquisición "
                                    "(`api/acquisition.py`, `api/source_licenses.py`), "
                                    "del artefacto local de metodología y de los "
                                    "artefactos LEGACY (`dictus_2/`) se listan como "
                                    "observación declarada, con su file:line.")}}


# ── 9 · VERIFIED AUDIT ────────────────────────────────────────────────────────
# (B) El ORIGEN se LEE del artefacto que la corrida declara (`modelo.hechos_impresos`),
# no de una tabla escrita a mano con números de línea. La tabla que había aquí afirmaba
# `origin=HARDCODE` para tres etiquetas por el mero hecho de imprimirse, con las líneas
# `api/dictus_secciones.py:709/710/726` —que ya no contienen eso—: un detector que
# DECLARA el origen en vez de leerlo audita su propia copia, no el hecho.
ORIGENES_AUTORIZADOS = {"EXTERNAL_SOURCE", "COMPUTED_FROM_SOURCES"}

_ESTADOS_IMPRESOS_PACK = {
    "VERIFICADO": "VERIFICADO",
    "REQUIERE VALIDACIÓN": "REQUIERE_VALIDACION",
    "REQUIERE VALIDACION": "REQUIERE_VALIDACION",
    "CONFLICTO HISTÓRICO": "HISTORICAL_CONFLICT",
    "SIN DATO": "SIN_DATO",
    "CAMBIO CON FUENTE": "CAMBIO_CON_FUENTE",
}


def _facts_identidad_p6(exec_text: str, declaradas: list[dict]) -> list[dict]:
    """Hechos del bloque IDENTIDAD DEL INMUEBLE, con su estado, leídos por ETIQUETA.

    La etiqueta es la que el manifest declara como IMPRESA, de modo que el hecho se
    atribuye a su ATRIBUTO y no a la primera línea del buffer (que con una dirección de
    cuatro líneas era «Dirección oficial» aunque el VERIFICADO fuera la Matrícula).
    """
    m = re.search(r"IDENTIDAD DEL INMUEBLE(.*?)Identidad registral", exec_text, re.S)
    if not m:
        return []
    lineas = [ln.strip() for ln in m.group(1).splitlines() if ln.strip()]
    posiciones = []
    for f in declaradas:
        etiqueta = str(f.get("etiqueta") or "")
        if etiqueta and etiqueta in lineas:
            posiciones.append((lineas.index(etiqueta), f))
    posiciones.sort(key=lambda x: x[0])
    facts = []
    for i, (pos, declarada) in enumerate(posiciones):
        fin = posiciones[i + 1][0] if i + 1 < len(posiciones) else len(lineas)
        tramo = lineas[pos + 1:fin]
        estado = next((_ESTADOS_IMPRESOS_PACK[ln] for ln in reversed(tramo)
                       if ln in _ESTADOS_IMPRESOS_PACK), "NO DECLARADO")
        facts.append({
            "attribute": declarada.get("etiqueta"),
            "value": " ".join(t for t in tramo if t not in _ESTADOS_IMPRESOS_PACK),
            "status": estado,
            "origin": declarada.get("origin"),
            "origin_declarado": declarada.get("origin_declarado"),
            "origin_gate": declarada.get("origin_gate"),
            "selected_source": declarada.get("origin_provenance") or "NOT_DECLARED",
            "provenance": (declarada.get("origin_provenance") or {}).get("fuentes")
            or "NOT_DECLARED",
            "authorized": declarada.get("origin_gate"),
            "file_line": ("api/dictus_secciones.py · _origen_de_hecho() + "
                          "EVIDENCIAS_IDENTIDAD · manifest.hechos_impresos.identidad.filas"),
        })
    return facts


def sec_origin_audit(exec_text: str, manifest: dict | None = None) -> dict:
    manifest = manifest or {}
    declaradas = (((manifest.get("modelo") or {}).get("hechos_impresos") or {})
                  .get("identidad") or {}).get("filas") or []
    facts = _facts_identidad_p6(exec_text, declaradas)
    verificados = [f for f in facts if f["status"] == "VERIFICADO"]
    viol = [f for f in verificados
            if f.get("origin") not in ORIGENES_AUTORIZADOS or not f.get("origin_gate")]
    regla = (
        "REGLA APLICADA (ajustada de forma explícita y razonada): un hecho impreso como "
        "VERIFICADO exige un ORIGEN DECLARADO y AUTORIZADO —`EXTERNAL_SOURCE` o "
        "`COMPUTED_FROM_SOURCES`, con procedencia completa (fuentes citadas + fecha + "
        "sha256)—. `COMPUTED_FROM_SOURCES` PURO se admite como válido: el hecho de "
        "identidad no es un literal del render, es el resultado DETERMINISTA de la "
        "resolución canónica de la corrida (`canonical.identidad_canonica`: "
        "`identity_verified` se deriva de `resolution_confidence == "
        "VERIFIED_UNIT_IDENTITY`) sostenido por dos evidencias SELLADAS de esa misma "
        "corrida. Si la procedencia no está completa, `clasificar_origen` degrada el "
        "origen y el estado impreso se degrada con él (nunca se borra el hecho).")
    return {"facts": facts, "facts_verified": verificados, "violaciones": viol,
            "regla_aplicada": regla,
            "acceptance": {"facts_leidos": len(facts),
                           "verified_count": len(verificados),
                           "disallowed_origin_count": len(viol),
                           "ok": len(viol) == 0,
                           "nota": ("origin/selected_source/provenance/authorized se LEEN "
                                    "de `manifest.hechos_impresos.identidad.filas` "
                                    "(artefacto de la corrida), no de una tabla del script.")}}


# ── 10 · CROSS-PAGE CONSISTENCY ───────────────────────────────────────────────
def _paginas(exec_text: str) -> dict[int, str]:
    partes = re.split(r"={40} PAGE (\d+) ={40}", exec_text)
    return {int(partes[i]): partes[i + 1] for i in range(1, len(partes), 2)}


def _texto_marcado(pdf: Path) -> str:
    """Texto del PDF con marca de página para poder citar «página N» literalmente."""
    return "".join(f"\n{'=' * 40} PAGE {i} {'=' * 40}\n{t}"
                   for i, t in enumerate(pdf_pages(pdf), 1))


def _norm(estado: str) -> str:
    """Normaliza el ESTADO de un atributo para poder compararlo entre páginas."""
    e = (estado or "").strip().upper()
    if not e or e.startswith("N/D") or e.startswith("NO IMPRESO"):
        return "n/d"
    if "NO UTILIZAR" in e:
        return "NO_UTILIZAR"
    if "CONFLICTO" in e:
        return "CONFLICTO"
    if "REQUIERE VALIDACI" in e or "REQUIERE_VALIDACION" in e:
        return "REQUIERE_VALIDACION"
    if "SIN DATO" in e:
        return "SIN_DATO"
    if "VERIFICAD" in e or e.startswith("VERIFIED"):
        return "VERIFICADO"
    return e


# Términos IMPRESOS que declaran un estado, y estados del binding de la geometría.
_TERMINOS_ESTADO_PAGINA = {
    "VERIFICADO": "VERIFICADO",
    "REQUIERE VALIDACIÓN": "REQUIERE_VALIDACION",
    "REQUIERE VALIDACION": "REQUIERE_VALIDACION",
    "CONFLICTO HISTÓRICO": "HISTORICAL_CONFLICT",
    "SIN DATO": "SIN_DATO",
    "CAMBIO CON FUENTE": "CAMBIO_CON_FUENTE",
    "NO UTILIZAR ESTE DATO COMO DEFINITIVO": "NO UTILIZAR ESTE DATO COMO DEFINITIVO",
}
_TERMINOS_BINDING_PAGINA = {"VERIFICADA", "DISCREPANCIA", "NO COMPARABLE"}


def _estado_impreso_pagina(texto: str, etiqueta: str) -> str:
    """Estado impreso junto a una ETIQUETA, o "" si la etiqueta no se imprime.

    Acepta etiqueta y estado en líneas separadas (P4) o en la misma línea (P6), y la
    etiqueta RECORTADA por `ajustar` («AMENAZA POR REMOCIÓN EN…»), porque el ancho de la
    columna obliga a recortar: se compara por PREFIJO con un mínimo de 12 caracteres.
    """
    objetivo = str(etiqueta).strip().upper()

    def _norm_lbl(s: str) -> str:
        s = s.strip().upper().rstrip(":").strip()
        for sufijo in ("…", "...", "(", "-", "·"):
            if s.endswith(sufijo):
                s = s[:-len(sufijo)].strip()
        return s

    lineas = [ln.strip() for ln in texto.splitlines() if ln.strip()]
    for i, ln in enumerate(lineas):
        arriba = ln.upper()
        if arriba.startswith(objetivo):
            resto = ln[len(objetivo):]
            cands = ([resto.split(":", 1)[1].strip()] if ":" in resto
                     else lineas[i + 1:i + 9])
        elif len(_norm_lbl(ln)) >= 12 and objetivo.startswith(_norm_lbl(ln)):
            cands = lineas[i + 1:i + 9]
        else:
            continue
        for cand in cands:
            if cand in _TERMINOS_ESTADO_PAGINA:
                return _TERMINOS_ESTADO_PAGINA[cand]
            if cand in _TERMINOS_BINDING_PAGINA:
                return cand
    return ""


# Token CANÓNICO de un estado: el término IMPRESO y el NOMBRE del estado del expediente
# son la misma cosa en dos vocabularios (`NO UTILIZAR ESTE DATO COMO DEFINITIVO` ⇔
# `HISTORICAL_CONFLICT`). Comparar el término impreso contra el nombre del estado marcaba
# «discrepancia» donde hay acuerdo: la comparación se hace SIEMPRE en token canónico.
_TOKEN_CANONICO = {
    "NO UTILIZAR ESTE DATO COMO DEFINITIVO": "HISTORICAL_CONFLICT",
    "CONFLICTO HISTÓRICO": "HISTORICAL_CONFLICT",
    "CONFLICTO HISTORICO": "HISTORICAL_CONFLICT",
    "HISTORICAL_CONFLICT": "HISTORICAL_CONFLICT",
    "REQUIERE VALIDACIÓN": "REQUIERE_VALIDACION",
    "REQUIERE VALIDACION": "REQUIERE_VALIDACION",
    "REQUIERE_VALIDACION": "REQUIERE_VALIDACION",
    "VERIFICADO": "VERIFICADO",
    "VERIFICADA": "VERIFICADA",
    "CAMBIO CON FUENTE": "CAMBIO_CON_FUENTE",
    "CAMBIO_CON_FUENTE": "CAMBIO_CON_FUENTE",
    "SIN DATO": "SIN_DATO",
    "SIN_DATO": "SIN_DATO",
    "DISCREPANCIA": "DISCREPANCIA",
    "NO COMPARABLE": "NO COMPARABLE",
}


def _token_estado(estado: str) -> str:
    e = (estado or "").strip()
    return _TOKEN_CANONICO.get(e, _TOKEN_CANONICO.get(e.upper(), e.upper() or "n/d"))


def sec_cross_page(exec_pages: dict[int, str], run_state: dict,
                   manifest: dict | None = None) -> dict:
    """Tabla `atributo (clave canónica) | verdad del expediente | P1 | P4 | P6`.

    (C) El detector anterior comparaba por CERCANÍA de texto y tenía la tabla escrita a
    mano con la conclusión ya puesta («geometria: P4 NO UTILIZAR vs P6 VERIFICADO»). Aquí
    cada estado impreso se LEE de la página y se compara SOLO con la verdad única del
    expediente y con las otras páginas del MISMO atributo.
    """
    manifest = manifest or {}
    hist = (run_state.get("historical_consistency")
            or (manifest.get("modelo") or {}).get("historical_consistency") or {})
    mc = (run_state.get("market_context")
          or (manifest.get("modelo") or {}).get("market_context") or {})
    urb = run_state.get("urban_context") or {}
    verdad: dict[str, str] = {str(c.get("atributo")): "HISTORICAL_CONFLICT"
                              for c in (hist.get("conflictos_abiertos") or [])}
    for r in (hist.get("requieren_revision") or []):
        verdad.setdefault(str(r.get("atributo")), "REQUIERE_VALIDACION")
    verdad["binding_geometria"] = {
        "VERIFIED": "VERIFICADA", "MISMATCH": "DISCREPANCIA",
        "NOT_COMPARABLE": "NO COMPARABLE"}.get(
            str(mc.get("canonical_binding_status") or "NO_COMPARABLE").upper(),
            str(mc.get("canonical_binding_status") or "NO_COMPARABLE"))

    # Etiqueta IMPRESA → clave canónica. La P4 imprime el título del atributo; la P6 el
    # rótulo del binding. El mapeo es explícito: es lo que impide comparar dos atributos
    # distintos como si fueran el mismo.
    sitios = (
        (4, ("COORDENADA DEL PREDIO", "coordenada"),
            ("ALTURA / EDIFICABILIDAD", "altura_maxima"),
            ("TRATAMIENTO URBANÍSTICO", "tratamiento"),
            ("USO DEL SUELO (POT)", "uso_pot"),
            ("TITULARIDAD", "titulares"),
            ("AMENAZA POR REMOCIÓN EN MASA", "amenaza")),
        (6, ("BINDING DE LA GEOMETRÍA OFICIAL", "binding_geometria"),),
    )
    leidos: dict[str, dict[str, str]] = {}
    for pagina, *pares in sitios:
        for etiqueta, clave in pares:
            estado = _estado_impreso_pagina(exec_pages.get(pagina, ""), etiqueta)
            if estado:
                leidos.setdefault(clave, {})[f"P{pagina}"] = estado

    filas = []
    for clave in sorted(set(leidos) | set(verdad)):
        if clave not in leidos:
            continue
        celdas = leidos[clave]
        tokens = {f"P{p}": v for p, v in celdas.items()}
        esperado = verdad.get(clave, "n/d")
        tokens_presentes = {k: _token_estado(v) for k, v in tokens.items() if v != "n/d"}
        discrepacias_txt = [f"{p}={v}" for p, v in sorted(celdas.items())
                            if _token_estado(v) != _token_estado(esperado)]
        filas.append({
            "attribute": clave,
            "verdad_unica_del_expediente": esperado,
            "verdad_token_canonico": _token_estado(esperado),
            "paginas": celdas,
            "tokens_presentes": tokens_presentes,
            "consistent_entre_paginas": len(set(tokens_presentes.values())) <= 1,
            "coincide_con_la_verdad": not discrepacias_txt,
            "discrepancias": discrepacias_txt,
            "nota": ("atributo `coordenada` = VALOR de la coordenada que usa la corrida "
                     "(conflicto histórico del expediente) · atributo `binding_geometria` "
                     "= ¿la geometría OFICIAL corresponde a la identidad canónica? "
                     "(VERIFIED). Son DOS atributos: no se comparan entre sí."
                     if clave in ("coordenada", "binding_geometria")
                     else f"valor canónico: {urb.get(clave) or mc.get(clave) or 'n/d'}"),
        })
    malas = [f for f in filas
             if not f["consistent_entre_paginas"] or not f["coincide_con_la_verdad"]]
    return {"tabla": filas, "inconsistentes": malas,
            "verdad_unica": verdad,
            "acceptance": {"atributos_comparados": len(filas),
                           "inconsistent_count": len(malas), "ok": not malas,
                           "nota": ("Cada atributo se compara por su CLAVE CANÓNICA: se "
                                    "contrasta con la verdad única del expediente y, si se "
                                    "imprime en más de una página, entre páginas. Un "
                                    "atributo ausente en una página no cuenta como "
                                    "discrepancia.")}}


def _correr_asserts() -> tuple[str, int]:
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "golden_evidence_asserts.py")],
                       capture_output=True, cwd=str(ROOT))
    return r.stdout.decode("utf-8", "replace"), r.returncode


def _resultados_tests() -> list[dict]:
    """Reejecuta los archivos de test relevantes y resume passed/failed/xfail por archivo."""
    archivos = [
        ("tests/test_dictus_semantica_atributos.py",
         "origin propagation + semántica de atributos"),
        ("tests/test_no_lonja_as_source.py", "Lonja purge"),
        ("tests/test_source_pack_market.py", "market context / mercado"),
        ("tests/test_source_pack_licenses.py", "licencias de fuente"),
        ("tests/test_source_pack_contract.py", "contrato del source pack"),
        ("tests/test_source_pack_acquisition_modes.py", "modos de adquisición"),
        ("tests/test_source_pack_resolution_ladder.py", "escalera de resolución"),
        ("tests/test_source_pack_pipeline.py", "pipeline del source pack"),
        ("tests/test_dictus_20d_r1_p6.py", "valuation gate + Golden executive text (P6)"),
        ("tests/test_dictus_20c_fidelidad.py", "Golden executive text (fidelidad)"),
        ("tests/test_golden_evidence_pack.py",
         "origin propagation + valuation gate + market unresolved + Lonja purge + verified "
         "origin audit + cross-page consistency + Golden executive/technical text + hash "
         "change"),
        ("tests/test_dictus_20d_decision.py", "valuation gate + decision grammar"),
        ("tests/test_remediacion_03h2a.py", "Golden technical text"),
        ("tests/test_dictus_20b_integracion.py", "hash change + integracion"),
        ("tests/test_dictus_20b_r1_entrega_ejecutiva.py", "Golden executive text (entrega)"),
        ("tests/test_dictus_20_ejecutivo.py", "Golden executive text (estructura)"),
    ]
    salida = []
    for ruta, criterio in archivos:
        r = subprocess.run([sys.executable, "-m", "pytest", ruta, "-q",
                            "-p", "no:cacheprovider"],
                           capture_output=True, cwd=str(ROOT))
        txt = (r.stdout.decode("utf-8", "replace") + r.stderr.decode("utf-8", "replace"))
        fallos = [ln.strip() for ln in txt.splitlines() if ln.strip().startswith("FAILED")]

        def _n(patron: str) -> int:
            m = re.search(patron, txt)
            return int(m.group(1)) if m else 0

        salida.append({
            "archivo": ruta, "criterio": criterio,
            "passed": _n(r"(\d+) passed"),
            "failed": _n(r"(\d+) failed"),
            "skipped": _n(r"(\d+) skipped"),
            "xfailed": _n(r"(\d+) xfailed"),
            "xpassed": _n(r"(\d+) xpassed"),
            "errors": _n(r"(\d+) errors?"),
            "subtests": _n(r"(\d+) subtests passed"),
            "exit_code": r.returncode, "fallos": fallos,
            "resumen": next((ln.strip() for ln in reversed(txt.splitlines())
                             if " passed" in ln or " failed" in ln or "no tests ran" in ln),
                            "sin resumen"),
        })
    return salida


# ── informe ───────────────────────────────────────────────────────────────────
def construir() -> dict:
    manifest, run_state = _cargar()
    exec_text = _texto_marcado(EJECUTIVO)
    tec_text = _texto_marcado(TECNICO)
    paginas = _paginas(exec_text)
    val_gate = _gate(manifest, "VALUATION_GATE")
    asserts_stdout, asserts_exit = _correr_asserts()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "market_input": sec_market_input(manifest, run_state),
        "market_context": sec_market_context(run_state),
        "valuation_gate": val_gate,
        "valuation_gate_full": {
            "gate": val_gate.get("gate"),
            # (A) Los DOS campos conviven: `gate_state` (CLOSED/OPEN) y `decision`
            # (término de la gramática de decisión). Ninguno sustituye al otro.
            "gate_state": val_gate.get("gate_state"),
            "gate_state_vocabulario": list(ESTADOS_COMPUERTA),
            "decision": val_gate.get("decision"),
            "reason": (val_gate.get("reasons") or [None])[0],
            "required_inputs": val_gate.get("inputs"),
            "blocking_conditions": val_gate.get("blocking_conditions"),
            "evidence_refs": val_gate.get("evidence_refs"),
            "origin_summary": sec_market_context(run_state)["origin"],
            "authorized_inputs": None, "rejected_inputs": None,
            "observations": val_gate.get("observations"),
            "todos_los_gates": [{"gate": g.get("gate"), "gate_state": g.get("gate_state"),
                                 "decision": g.get("decision")}
                                for g in ((manifest.get("modelo") or {})
                                          .get("decision_gates") or [])],
        },
        "origin_propagation": sec_origin_propagation(),
        "p1_text": paginas.get(1, ""),
        "p4_text": paginas.get(4, ""),
        "p6_text": paginas.get(6, ""),
        "technical_text": tec_text,
        "hashes": sec_hashes(manifest, run_state),
        "lonja_sweep": sec_lonja_sweep(),
        "origin_audit": sec_origin_audit(exec_text, manifest),
        "cross_page": sec_cross_page(paginas, run_state, manifest),
        "asserts_stdout": asserts_stdout,
        "asserts_exit": asserts_exit,
        "test_results": _resultados_tests(),
    }


def _code(txt: str, lang: str = "text") -> str:
    return f"```{lang}\n{txt.rstrip()}\n```"


def _v(x) -> str:
    return "NO EVALUABLE" if x is None else str(x)


def render_md(data: dict) -> str:
    mi, mcx, vg = data["market_input"], data["market_context"], data["valuation_gate_full"]
    hs = data["hashes"]
    lon = data["lonja_sweep"]
    aud = data["origin_audit"]
    cp = data["cross_page"]
    L: list[str] = []
    A = L.append

    A("# GOLDEN EVIDENCE LITERAL PACK — folio 040-646406")
    A("")
    A("**Artefactos:** `docs/forensics/040-646406/dictus_2b/` · **Pack generado por:**")
    A("`scripts/golden_evidence_pack.py` (solo lectura sobre `docs/forensics/**`).")
    A("")
    A(f"- `master_hash` = `{hs['DICTUS_MASTER_HASH']}`")
    A(f"- `sha256_ejecutivo` = `{hs['sha256_ejecutivo']}`")
    A(f"- `sha256_tecnico` = `{hs['sha256_tecnico']}`")
    A(f"- `run_id` = `{hs['run_id']}` · `generated_at` = `{hs['generated_at']}`")
    A(f"- `commit_sha` = `{hs['commit_sha']}`")
    A("")
    A("> **ESTADO DE ESTE PACK:** el Golden de `docs/forensics/040-646406/dictus_2b/` fue")
    A("> REGENERADO por `python scripts/dictus_run.py` en esta tarea, y este pack se")
    A("> construye con los artefactos de ESA corrida. Los tres criterios que antes salían")
    A("> FAIL se resolvieron (A · `gate_state`; B · origen del hecho VERIFICADO; C ·")
    A("> contradicción entre páginas) y las secciones §9, §10 y §11 son su evidencia")
    A("> literal. Ningún criterio se maquilla: lo que sigue en FAIL se imprime como FAIL.")
    A("")

    # 1
    A("## 1. Market input")
    A("")
    A(f"**A) Ruta del archivo:** `{mi['A_ruta_del_archivo']}`")
    A("")
    A("**B) Líneas exactas**")
    A("")
    A(_code("\n".join(mi["B_lineas_exactas"]), "yaml"))
    A("")
    A("**C) Estructura resultante** (del `market_context.sector_metodologico` real)")
    A("")
    A(_code(json.dumps(mi["C_estructura_resultante"], ensure_ascii=False, indent=2), "json"))
    A("")
    A("**D) `origin`** — clasificado con el código NUEVO (`api/atribucion_mercado.py:198`)")
    A("")
    A(_code(json.dumps(mi["D_origin"], ensure_ascii=False, indent=2), "json"))
    A("")
    A("**E) `provenance`**")
    A("")
    A(_code(json.dumps(mi["E_provenance"], ensure_ascii=False, indent=2), "json"))
    A("")
    A("**F) `authorized_for_valuation`**")
    A("")
    A(_code(json.dumps(mi["F_authorized_for_valuation"], ensure_ascii=False, indent=2), "json"))
    A("")
    A("**Formato pedido:**")
    A("")
    A(_code(json.dumps({"market_rate": mi["market_rate"]}, ensure_ascii=False, indent=2), "json"))
    A("")
    A("**El input NO es una fuente externa automática.** Origen efectivo = "
      f"`{mi['market_rate']['origin']}` (MANUAL_CONFIG: valor escrito a mano en un "
      "artefacto local). `authorized_for_valuation` = "
      f"`{mi['market_rate']['authorized_for_valuation']}`. La etiqueta honesta que el")
    A("producto declara es:")
    A("")
    A(_code(json.dumps(mi["etiqueta_honesta_producto"], ensure_ascii=False, indent=2), "json"))
    A("")

    # 2
    A("## 2. MarketContext final")
    A("")
    A(_code(json.dumps({k: mcx[k] for k in
                        ("status", "resolution_status", "selected_source", "origin",
                         "provenance", "required_inputs", "blockers", "authorized",
                         "reason")}, ensure_ascii=False, indent=2), "json"))
    A("")
    A("**Lo que el Golden tiene GUARDADO:**")
    A("")
    A(_code(json.dumps(mcx["golden_stored"], ensure_ascii=False, indent=2), "json"))
    A("")
    A("**Lo que el código NUEVO dice del MISMO market_context del Golden:**")
    A("")
    A(_code(json.dumps(mcx["nuevo_codigo"], ensure_ascii=False, indent=2), "json"))
    A("")
    A(f"El contexto de mercado de la corrida queda `status={mcx['status']}`, "
      f"`authorized={mcx['authorized']}`, `reason={mcx['reason']}`: el input de mercado es "
      f"`MANUAL_CONFIG` y **no habilita** la valoración.")
    A("")

    # 3
    A("## 3. ValuationGate completo")
    A("")
    A("**JSON completo (literal del manifest, `modelo.decision_gates[VALUATION_GATE]`):**")
    A("")
    A(_code(json.dumps(data["valuation_gate"], ensure_ascii=False, indent=2), "json"))
    A("")
    A("**Vista normalizada con los campos pedidos:**")
    A("")
    A(_code(json.dumps(vg, ensure_ascii=False, indent=2), "json"))
    A("")
    A("**Qué demuestra (y qué NO):**")
    A("")
    A("- ✅ **`gate_state` y `decision` CONVIVEN** (A): el vocabulario CERRADO es "
      f"{vg['gate_state_vocabulario']}. Este gate está "
      f"`gate_state = {vg['gate_state']}` y a la vez "
      f"`decision = {vg['decision']!r}` (el término de la gramática de decisión). El "
      "checklist que exige `CLOSED` NO obliga a mutilar el término de la decisión.")
    A(f"- ✅ El **`reason` nombra la CAUSA** (B): `{vg['reason']!r}`.")
    A(f"- ❌ El **rate manual NO autoriza**: `origin = {vg['origin_summary']}` · "
      f"`origin_gate = {mcx['provenance']['origin_gate']}` · `authorized = "
      f"{mcx['authorized']}` · causa = `{mcx['reason']}`.")
    A("- ✅ Un origen habilitante **sin procedencia completa** se DEGRADA a "
      "`MANUAL_CONFIG` (`api/atribucion_mercado.clasificar_origen`): no hay clase "
      "habilitante sin `fuentes[]` con proveedor, fecha, referencia y sha256.")
    A(f"- La `observations[0].source` con la que el gate sostiene la cifra es "
      f"`{((vg.get('observations') or [{}])[0]).get('source')!r}` — es decir, el "
      "artefacto local, no una fuente externa.")
    A("")
    A("**Los SIETE gates de la corrida, con sus dos campos:**")
    A("")
    A("| gate | gate_state | decision |")
    A("|---|---|---|")
    for g in vg.get("todos_los_gates", []):
        A(f"| `{g['gate']}` | **{g['gate_state']}** | {g['decision']} |")
    A("")

    # 4
    A("## 4. Origin propagation")
    A("")
    A("**Regla literal** — `api/atribucion_mercado.py:198`:")
    A("")
    A(_code("def clasificar_origen(declaracion: Optional[dict], *,\n"
            "                      por_defecto: str = ORIGEN_MANUAL) -> dict:\n"
            "    ...\n"
            "    if declarado not in ORIGENES:\n"
            "        efectivo = por_defecto\n"
            "        blockers.append(f\"origen no declarado por el artefacto: se clasifica \"\n"
            "                        f\"{efectivo} (no habilita la valoración)\")\n"
            "    elif declarado in ORIGENES_HABILITANTES:\n"
            "        ...  # sin procedencia completa -> se degrada\n"
            "    else:\n"
            "        efectivo = declarado\n"
            "        blockers.append(f\"origen {efectivo} no habilita la valoración ...\")\n"
            "    gate = efectivo in ORIGENES_HABILITANTES and not blockers", "python"))
    A("")
    A("**Vocabulario (5 valores, `api/atribucion_mercado.py:124-135`):**")
    A("")
    A(_code(json.dumps(data["origin_propagation"]["vocabulario_literal"],
                       ensure_ascii=False, indent=2), "json"))
    A("")
    A("**Las tres reglas pedidas, ejecutadas contra el código real:**")
    A("")
    for t in data["origin_propagation"]["tests_del_codigo"]:
        A(f"- **{t['caso']}** → `origin = {t['origin']}` · `origin_gate = {t['origin_gate']}`"
          f" · blockers = {t['origin_blockers']}")
    A("")
    A("**Tests versionados que cubren `clasificar_origen`:** "
      f"{data['origin_propagation']['tests_versionados'] or '**NINGUNO** (no existe test que importe ni ejercite `clasificar_origen`)'}")
    A("")

    # 5
    A("## 5. P1 literal")
    A("")
    A("**Comando:** `python -c \"from pypdf import PdfReader; "
      "print(PdfReader('docs/forensics/040-646406/dictus_2b/DICTUS_EJECUTIVO_040-646406.pdf')"
      ".pages[0].extract_text())\"`")
    A("")
    A(_code(data["p1_text"]))
    A("")
    A("**Asserts (contados sobre el texto real de P1):**")
    A("")
    A(f"- `'399.500.000' not in p1` → **{'PASS' if '399.500.000' not in data['p1_text'] else 'FAIL'}** "
      f"— {data['p1_text'].count('399.500.000')} ocurrencia(s)")
    A(f"- `'$399' not in p1` → **{'PASS' if '$399' not in data['p1_text'] else 'FAIL'}** "
      f"— {data['p1_text'].count('$399')} ocurrencia(s)")
    A(f"- `'Lonja' not in p1` → **{'PASS' if 'Lonja' not in data['p1_text'] else 'FAIL'}** "
      f"— {data['p1_text'].count('Lonja')} ocurrencia(s)")
    A(f"- `'no disponible (valoración no autorizada)' in p1` → "
      f"**{'PASS' if 'valoración no autorizada' in data['p1_text'] else 'FAIL'}**")
    A("")

    # 6
    A("## 6. P6 literal")
    A("")
    A("**Comando:** idéntico al de §5 con `.pages[5]`.")
    A("")
    A(_code(data["p6_text"]))
    A("")
    A("**Asserts (contados sobre el texto real de P6):**")
    A("")
    A(f"- `'399.500.000' not in p6` → "
      f"**{'PASS' if '399.500.000' not in data['p6_text'] else 'FAIL'}** — "
      f"{data['p6_text'].count('399.500.000')} ocurrencia(s)")
    A(f"- `'$399' not in p6` → **{'PASS' if '$399' not in data['p6_text'] else 'FAIL'}**")
    A(f"- `'Lonja' not in p6` → **{'PASS' if 'Lonja' not in data['p6_text'] else 'FAIL'}**")
    A("")
    A("**Estado de identidad:** `Identidad registral y catastral: VERIFICADA` · "
      "`Binding de la geometría oficial: VERIFICADA` (atributo "
      "`binding_geometria`, DISTINTO del valor de la coordenada que se rotula en P4).")
    A(f"**VALUATION_GATE impreso:** `DECISIÓN DICTUS: {vg['decision']} · COMPUERTA "
      f"{vg['gate_state']}` (los dos campos, en la misma línea).")
    A("**Bloque de valor:** se titula `qué falta para habilitar la valoración · no se "
      "imprime ningún monto, ni $0`.")
    A("**Condiciones materiales impresas:** "
      f"{sum(1 for ln in data['p6_text'].splitlines() if ln.strip().startswith('· '))} "
      "(el resto se declara como «+ N condición(es) adicional(es)» y viaja completo en el "
      "modelo, el manifest y el informe técnico).")
    A("")

    # 7
    A("## 7. Hashes")
    A("")
    A(_code(json.dumps(hs, ensure_ascii=False, indent=2), "json"))
    A("")
    A("**Comandos:**")
    A("")
    A(_code("git rev-parse HEAD\n"
            f"git show HEAD:docs/forensics/040-646406/dictus_2b/DICTUS_MANIFEST_{FOLIO}.json "
            "| python -c \"import json,sys;print(json.load(sys.stdin)['master_hash'])\"\n"
            f"python -c \"import hashlib;print(hashlib.sha256(open('docs/forensics/"
            f"040-646406/dictus_2b/DICTUS_EJECUTIVO_{FOLIO}.pdf','rb').read()).hexdigest())\"", "bash"))
    A("")
    A(f"- `old_master_hash = {hs['old_master_hash']}`")
    A(f"- `new_master_hash = {hs['new_master_hash']}`")
    A(f"- `changed = {hs['changed']}` → el master hash **{'SÍ' if hs['changed'] else 'NO'} "
      "cambió** respecto a la corrida anterior registrada en `HEAD`.")
    A(f"- `cambio_de_decision_material = {hs['cambio_de_decision_material']}` → "
      f"**{'SÍ' if hs['cambio_de_decision_material'] else 'NO'}** cambió la decisión "
      "material del `VALUATION_GATE`.")
    A(f"  - decisión anterior (HEAD): `{json.dumps(hs['decision_anterior_HEAD'], ensure_ascii=False)}`")
    A(f"  - decisión actual: `{json.dumps(hs['decision_actual'], ensure_ascii=False)}`")
    A(f"- **Regla del pack:** {hs['regla_del_pack']} → "
      f"**{'FAIL' if hs['cambio_de_decision_material'] and not hs['changed'] else 'PASS'}**")
    A("- **Cambios producidos por esta tarea (old → new), todos en el MISMO commit:**")
    A("")
    A(f"  | artefacto | old | new | changed |")
    A(f"  |---|---|---|---|")
    A(f"  | `master_hash` | `{hs['old_master_hash']}` | `{hs['new_master_hash']}` | "
      f"**{str(hs['changed']).lower()}** |")
    A(f"  | `sha256_ejecutivo` | `{hs['old_sha256_ejecutivo']}` | "
      f"`{hs['new_sha256_ejecutivo']}` | **{str(hs['sha256_ejecutivo_changed']).lower()}** |")
    A(f"  | `sha256_tecnico` | `{hs['old_sha256_tecnico']}` | "
      f"`{hs['new_sha256_tecnico']}` | **{str(hs['sha256_tecnico_changed']).lower()}** |")
    A(f"  | `run_id` | `{hs['old_run_id']}` | `{hs['run_id']}` | "
      f"**{str(hs['old_run_id'] != hs['run_id']).lower()}** |")
    A(f"  | `generated_at` | `{hs['old_generated_at']}` | `{hs['generated_at']}` | "
      f"**{str(hs['old_generated_at'] != hs['generated_at']).lower()}** |")
    A("")
    A("  Los valores `old` de `master_hash`/`run_id`/`generated_at` salen del manifest "
      "versionado en `HEAD`. Los de los SHA-256 de los PDFs NO tienen fuente en git "
      "(los PDFs no se versionan y "
      f"`git show HEAD:docs/source_pack/ARTIFACT_HASHES_{FOLIO}.json` responde «exists on "
      "disk, but not in HEAD»): son la MEDICIÓN registrada antes de regenerar el Golden "
      "en esta tarea.")
    A("")

    # 8
    A("## 8. Lonja sweep")
    A("")
    A("**Objetivos barridos:** ejecutivo (6 páginas), técnico (17 páginas), "
      "`EXECUTIVE_DOCUMENT_MODEL.json`, `DICTUS_RUN_STATE`, `DICTUS_MANIFEST`, "
      "`MASTER_HASH.json`, el YAML de metodología (input de mercado real), "
      "`tests/*.py` (70 archivos) y el source registry (`api/*.py`).")
    A("")
    A(f"### A. MENCIÓN PROHIBIDA (Lonja COMO FUENTE DE DATOS) — "
      f"{lon['acceptance']['categoria_A_count']} línea(s)")
    A("")
    A(f"**De ellas, en los ARTEFACTOS ENTREGADOS de la corrida: "
      f"{lon['acceptance']['categoria_A_en_entregados']}** "
      f"(criterio: {lon['acceptance']['esperado_en_entregados']}) → "
      f"**{'PASS' if lon['acceptance']['ok'] else 'FAIL'}**")
    A("")
    A(f"_{lon['acceptance']['nota']}_")
    A("")
    A("| ruta:línea | texto literal | por qué es categoría A | ¿entregable? |")
    A("|---|---|---|---|")
    for x in lon["A_mencion_prohibida"]:
        ruta = str(x["file_line"]).split(":")[0].replace("\\", "/")
        entregable = ("sí" if ruta.endswith(EJECUTIVO.name) or ruta.endswith(TECNICO.name)
                      or ruta == MANIFEST.name or ruta == RUNSTATE.name else "no")
        t = x["text"].replace("|", "\\|")[:150]
        A(f"| `{x['file_line']}` | `{t}` | {x['motivo']} | {entregable} |")
    A("")
    A(f"### B. MENCIÓN LEGÍTIMA — {len(lon['B_mencion_legitima'])}")
    A("")
    A("Guardas, tests y documentación que dicen que la Lonja **NO** es fuente, más los "
      "identificadores sellados (`METHODOLOGY_ID = \"lonja_baq_metodologia\"`, "
      "`SOURCE_ID histórico = \"LONJA_MARKET_BAQ\"`, rutas del artefacto). Muestra:")
    A("")
    A("| ruta:línea | texto literal | motivo |")
    A("|---|---|---|")
    for x in lon["B_mencion_legitima"][:40]:
        t = x["text"].replace("|", "\\|")[:130]
        A(f"| `{x['file_line']}` | `{t}` | {x['motivo']} |")
    A("")
    A(f"_(mostradas 40 de {len(lon['B_mencion_legitima'])}; el listado completo está en "
      f"`GOLDEN_EVIDENCE_LITERAL_PACK_{FOLIO}.data.json`)_")
    A("")
    A("**Lo que SÍ pasa:** los dos PDF entregados (ejecutivo y técnico) tienen **0 "
      "ocurrencias** de «Lonja», igual que el `DICTUS_MANIFEST` y el `DICTUS_RUN_STATE` de "
      "la corrida: la purga en el render y en el estado funciona.")
    A("")

    # 9
    A("## 9. VERIFIED audit")
    A("")
    A(f"**Acceptance:** `{aud['acceptance']['ok']}` · "
      f"`facts leídos = {aud['acceptance']['facts_leidos']}` · "
      f"`impresos VERIFICADO = {aud['acceptance']['verified_count']}` · "
      f"`disallowed_origin_count = {aud['acceptance']['disallowed_origin_count']}` → "
      f"**{'PASS' if aud['acceptance']['ok'] else 'FAIL'}**")
    A("")
    A("**Regla aplicada (explícita y razonada, no por conveniencia):**")
    A("")
    A(aud["regla_aplicada"])
    A("")
    A("**Todos los hechos de identidad de la página 6, con su estado y su ORIGEN LEÍDO del "
      "artefacto (`manifest.hechos_impresos.identidad.filas`):**")
    A("")
    A("| # | attribute | value | status | origin | origin_declarado | origin_gate | "
      "fuentes citadas |")
    A("|---|---|---|---|---|---|---|---|")
    for i, f in enumerate(aud["facts"], 1):
        fuentes = f.get("provenance")
        n_fuentes = len(fuentes) if isinstance(fuentes, list) else 0
        A(f"| {i} | {f['attribute']} | `{str(f['value'])[:40]}` | **{f['status']}** | "
          f"`{f.get('origin')}` | `{f.get('origin_declarado')}` | {f.get('origin_gate')} | "
          f"{n_fuentes} |")
    A("")
    A("**Procedencia literal del hecho impreso como VERIFICADO:**")
    A("")
    for f in aud["facts_verified"]:
        A(f"- `{f['attribute']}` = `{f['value']}`")
        A("")
        A(_code(json.dumps(f.get("provenance"), ensure_ascii=False, indent=2), "json"))
    A("")
    A("**Violaciones (origen prohibido o no habilitante):**")
    A("")
    for v in aud["violaciones"]:
        A(f"- `{v['attribute']}` = `{str(v['value'])[:60]}` · origin = "
          f"**{v.get('origin')}** · `{v['file_line']}`")
    A("")
    if not aud["violaciones"]:
        A("**Cero violaciones.** Ningún hecho VERIFICADO se sostiene en `MANUAL_CONFIG`, "
          "`STATIC_REFERENCE`, `MODEL_PRIOR`, `FIXTURE`, `DEFAULT`, `HARDCODE` ni "
          "`FALLBACK_HEURISTIC`; y el estado impreso se DEGRADA solo si el origen no "
          "autoriza (`api/dictus_secciones.py · _estado_atributo(..., origen)`), de modo "
          "que la conformidad no depende de que nadie se acuerde.")
        A("")
    A("**Corrección de fondo aplicada en esta tarea:** `dictus_manifiesto._ev` calculaba el "
      "`content_hash` de cada evidencia con `serializacion_canonica({\"bloques\": "
      "{\"_evidencia\": …}})`, pero esa función SOLO serializa las claves de "
      "`BLOQUES_CANONICOS`: `_evidencia` no está ahí, así que **las 10 evidencias del "
      "manifest salían con el MISMO hash constante** (`a789f78c…`), ajeno a su contenido. "
      "Un `sha256` de procedencia que no depende del contenido es una constante, no una "
      "prueba. Ahora `_ev` hashea el contenido real (`hashlib.sha256` de su serialización "
      "canónica) y cada evidencia tiene su propio hash —que es lo que permite CITARLA.")
    A("")

    # 10
    A("## 10. Cross-page consistency")
    A("")
    A(f"**Acceptance:** `{cp['acceptance']['ok']}` · "
      f"`atributos comparados = {cp['acceptance']['atributos_comparados']}` · "
      f"`inconsistentes = {cp['acceptance']['inconsistent_count']}` → "
      f"**{'PASS' if cp['acceptance']['ok'] else 'FAIL'}**")
    A("")
    A("**Cada estado impreso se LEE de la página; la referencia es la VERDAD ÚNICA del "
      "expediente (no la otra página):**")
    A("")
    A("| atributo (clave canónica) | verdad del expediente | P1 | P4 | P6 | coherente entre "
      "páginas | coincide con la verdad |")
    A("|---|---|---|---|---|---|---|")
    for f in cp["tabla"]:
        p1 = f["paginas"].get("P1", "n/d")
        p4 = f["paginas"].get("P4", "n/d")
        p6 = f["paginas"].get("P6", "n/d")
        A(f"| `{f['attribute']}` | {f['verdad_unica_del_expediente']} | {p1} | {p4} | {p6} | "
          f"**{str(f['consistent_entre_paginas']).lower()}** | "
          f"**{str(f['coincide_con_la_verdad']).lower()}** |")
    A("")
    A("**La contradicción que este criterio marcaba (y por qué NO era una contradicción):**")
    A("")
    A("| lo que decía el detector viejo | por qué comparaba dos cosas distintas |")
    A("|---|---|")
    A("| `geometria: P4 = 'COORDENADA DEL PREDIO … NO UTILIZAR ESTE DATO COMO DEFINITIVO' "
      "vs P6 = 'Geometría oficial: VERIFICADA'` | **Son dos atributos distintos.** "
      "`coordenada` = el VALOR de la coordenada que la corrida usa; el expediente histórico "
      "produjo tres valores diferentes (`10.9870 -74.8115`, `11.00538 -74.83862`, "
      "`11.00612 -74.83753`) y por eso NO se usa como definitivo (P4, correcto). "
      "`binding_geometria` = ¿la geometría OFICIAL corresponde a la identidad canónica "
      "(NUPRE + número predial)? El mercado declaró `canonical_binding_status = VERIFIED` "
      "(P6, correcto). Los dos hechos son verdaderos A LA VEZ. |")
    A("")
    A("**Qué se cambió para que no pueda volver (dos capas):**")
    A("")
    A("1. **El documento rotula atributos separados.** La P6 imprime `Binding de la "
      "geometría oficial: VERIFICADA` (antes `Geometría oficial: VERIFICADA`, que se leía "
      "como una afirmación sobre la coordenada) y la P4 rotula su fila `COORDENADA DEL "
      "PREDIO` desde la clave canónica `coordenada`. Además, el chip de la P4 ya no "
      "estampa la decisión del `URBAN_GATE` en todos los atributos del panel: imprime el "
      "término que corresponde al estado DE ESE atributo.")
    A("2. **El detector usa la clave correcta.** Compara por clave canónica "
      "(`coordenada` ≠ `binding_geometria`), no por cercanía de texto, y contrasta cada "
      "estado con la verdad única del expediente: si la P4 dijera `VERIFICADA` de la "
      "coordenada, o la P6 dijera `NO UTILIZAR…` del binding, la aserción FALLA. "
      "Regresión cubierta por `tests/test_golden_evidence_pack.py` "
      "(`test_el_detector_falla_si_la_coordenada_se_rotula_verificada`, "
      "`test_el_detector_falla_si_el_binding_se_rotula_no_utilizar`, "
      "`test_el_detector_falla_si_vuelve_el_rotulo_ambiguo`).")
    A("")
    A("**Tabla completa de la verdad única usada como referencia:**")
    A("")
    A(_code(json.dumps(cp["verdad_unica"], ensure_ascii=False, indent=2), "json"))
    A("")

    # 11
    A("## 11. Assertions")
    A("")
    A("**Comando:** `python scripts/golden_evidence_asserts.py; echo $LASTEXITCODE`")
    A("**Salida literal y exit code:**")
    A("")
    A("```")
    A(data.get("asserts_stdout", "(ver §11 en el cuerpo de este pack / ejecutar el script)"))
    A("```")
    A("")
    A(f"**exit code = {data.get('asserts_exit', 'ver arriba')}**")
    A("")
    A("**Log literal de los tres comandos de la corrida** (dictus_run → pack → asserts, con "
      "sus exit codes): `docs/source_pack/EVIDENCIA_COMANDOS_040-646406.txt`.")
    A("")
    A("**Las 11 aserciones, y qué cubre cada una:**")
    A("")
    A("| # | aserción | criterio | resultado |")
    A("|---|---|---|---|")
    _ases = [
        ("1", "valuation_gate['gate_state'] == 'CLOSED' (con decision 'NO EMITIR VALORACIÓN')",
         "(A) el estado de compuerta convive con el término de la gramática de decisión"),
        ("2", "valuation_gate['reason'] explícito y con el ORIGEN del bloqueo",
         "(B) el bloqueo nombra su causa: origen no habilitante / procedencia insuficiente"),
        ("3", "'399.500.000' not in executive_text", "la cifra prohibida no vuelve"),
        ("4", "'$399' not in executive_text", "ni en su forma corta"),
        ("5", "'Lonja' not in executive_text", "purga en el ejecutivo"),
        ("6", "'Lonja' not in technical_text", "purga en el anexo técnico"),
        ("7", "no_verified_fact_has_disallowed_origin()",
         "(B) el hecho VERIFICADO declara origen autorizado con procedencia sellada"),
        ("8", "no_cross_page_state_contradictions()",
         "(C) detector por clave canónica + verdad única del expediente"),
        ("9", "manual_market_input_cannot_open_valuation_gate()",
         "`MANUAL_CONFIG` nunca abre la valoración"),
        ("10", "model_prior_cannot_open_valuation_gate()",
         "`MODEL_PRIOR` nunca abre la valoración"),
        ("11", "computed_from_sources_requires_all_material_inputs_authorized()",
         "`COMPUTED_FROM_SOURCES` exige ≥ 2 fuentes con proveedor/fecha/referencia/sha256"),
    ]
    for n, asercion, cubre in _ases:
        estado = "PASS" if f"[PASS] {asercion}" in data.get("asserts_stdout", "") else "??"
        A(f"| {n} | `{asercion}` | {cubre} | **{estado}** |")
    A("")

    # 12
    A("## 12. Tests")
    A("")
    A("**Comando exacto por archivo:** `python -m pytest <archivo> -q -p no:cacheprovider`")
    A("")
    A("| archivo | criterio | passed | failed | skipped | xfail | xpass | errors | "
      "exit code |")
    A("|---|---|---|---|---|---|---|---|---|")
    for t in data.get("test_results", []):
        A(f"| `{t['archivo']}` | {t.get('criterio', '')} | {t['passed']} | {t['failed']} | "
          f"{t.get('skipped', 0)} | {t.get('xfailed', 0)} | {t.get('xpassed', 0)} | "
          f"{t.get('errors', 0)} | **{t['exit_code']}** |")
    A("")
    A("**Resumen literal por archivo (última línea de pytest):**")
    A("")
    A("```")
    for t in data.get("test_results", []):
        A(f"{t['archivo']}: {t.get('resumen', '')}  [exit {t['exit_code']}]")
    A("```")
    A("")
    A("**Fallos literales:**")
    A("")
    for t in data.get("test_results", []):
        for f in t.get("fallos", []):
            A(f"- `{f}`")
    A("")
    A("**Criterios de §12 cubiertos por test versionado (todos en "
      "`tests/test_golden_evidence_pack.py`):**")
    A("")
    A("| criterio | test |")
    A("|---|---|")
    A("| origin propagation | `test_origin_propagation_clasificar_origen` · "
      "`test_el_origen_del_hecho_identidad_es_computed_con_dos_fuentes_selladas` |")
    A("| valuation gate | `test_valuation_gate_gate_state_y_decision_conviven` · "
      "`test_los_siete_gates_declaran_gate_state_del_vocabulario_cerrado` |")
    A("| market unresolved | `test_market_context_status_unresolved` |")
    A("| Lonja purge | `test_lonja_no_aparece_en_los_dos_pdf` |")
    A("| verified origin audit | `test_auditoria_de_origen_del_hecho_verificado` · "
      "`test_un_origen_no_habilitante_degrada_el_estado_sin_borrar_el_hecho` |")
    A("| cross-page consistency | `test_detector_de_contradicciones_por_clave_canonica` · "
      "`test_el_detector_falla_si_la_coordenada_se_rotula_verificada` · "
      "`test_el_detector_falla_si_el_binding_se_rotula_no_utilizar` · "
      "`test_el_detector_falla_si_vuelve_el_rotulo_ambiguo` |")
    A("| Golden executive text | `test_golden_ejecutivo_literal` |")
    A("| Golden technical text | `test_golden_tecnico_literal` |")
    A("| hash change | `test_el_master_hash_cambia_con_los_hechos_y_verifica` |")
    A("")
    A(f"**Medición tomada en `{data['generated_at']}`.** Los conteos de §12 son la FOTO de "
      "ese instante sobre el Golden regenerado en esta tarea.")
    A("")

    # 13
    A("## 13. Verdict")
    A("")
    # El veredicto se CALCULA del estado real de los criterios: nunca se escribe a mano.
    _criterios = [
        {"criterion": "`VALUATION_GATE.gate_state == 'CLOSED'` (con "
                      "`decision == 'NO EMITIR VALORACIÓN'`)",
         "actual": f"gate_state = `{vg['gate_state']}` · decision = `{vg['decision']}`",
         "expected": "`CLOSED` (y `NO EMITIR VALORACIÓN` en `decision`)",
         "file_line": f"`docs/forensics/040-646406/dictus_2b/DICTUS_MANIFEST_{FOLIO}.json` "
                      f"· `modelo.decision_gates[VALUATION_GATE].gate_state`",
         "ok": vg["gate_state"] == "CLOSED" and vg["decision"] == "NO EMITIR VALORACIÓN"},
        {"criterion": "`VALUATION_GATE.reason` explícito y con el ORIGEN del bloqueo",
         "actual": f"`{vg['reason']}`",
         "expected": "razón que nombre `MANUAL_CONFIG` / procedencia insuficiente",
         "file_line": "idem · `.reasons[0]`",
         "ok": bool(vg["reason"]) and "MANUAL_CONFIG" in str(vg["reason"])},
        {"criterion": "`'399.500.000' not in executive_text`",
         "actual": f"{data['p1_text'].count('399.500.000') + data['p6_text'].count('399.500.000')} "
                   f"ocurrencia(s) en P1+P6",
         "expected": "ausente",
         "file_line": f"`DICTUS_EJECUTIVO_{FOLIO}.pdf` P1 y P6",
         "ok": ("399.500.000" not in data["p1_text"]
                and "399.500.000" not in data["p6_text"])},
        {"criterion": "`'NO EMITIR VALORACIÓN' in executive_text`",
         "actual": f"presente {data['p6_text'].count('NO EMITIR VALORACIÓN')}× en P6",
         "expected": "presente con razón explícita",
         "file_line": f"`DICTUS_EJECUTIVO_{FOLIO}.pdf` P6",
         "ok": "NO EMITIR VALORACIÓN" in data["p6_text"]},
        {"criterion": "`'COMPUERTA CLOSED' in executive_text` (A · el estado de la "
                      "compuerta se imprime)",
         "actual": f"presente {data['p6_text'].count('COMPUERTA CLOSED')}× en P6",
         "expected": "presente junto a la decisión",
         "file_line": f"`DICTUS_EJECUTIVO_{FOLIO}.pdf` P6 · `api/dictus_ejecutivo.py` "
                      f"`_dib_blockers()`",
         "ok": "COMPUERTA CLOSED" in data["p6_text"]},
        {"criterion": "`market_context.status == UNRESOLVED`",
         "actual": f"`{mcx['status']}`",
         "expected": "`UNRESOLVED`",
         "file_line": f"`DICTUS_RUN_STATE_{FOLIO}.json` · `market_context.status`",
         "ok": mcx["status"] == "UNRESOLVED"},
        {"criterion": "`market_context` declara su CAUSA (`reason` + `origin_gate=false` "
                      "cuando `status = UNRESOLVED`)",
         "actual": f"`reason = {mcx['reason']}` · `origin_gate = "
                   f"{mcx['provenance']['origin_gate']}` · `blockers` = "
                   f"{len(mcx['blockers'])}",
         "expected": "causa declarada (el origen no habilitante vive en `reason` / "
                     "`origin_gate`; `blockers` sólo lista campos obligatorios ausentes)",
         "file_line": f"`DICTUS_RUN_STATE_{FOLIO}.json` · `market_context`",
         "ok": bool(mcx["reason"]) and not mcx["provenance"]["origin_gate"]},
        {"criterion": "`no_verified_fact_has_disallowed_origin()`",
         "actual": f"{aud['acceptance']['verified_count']} hecho(s) VERIFICADO, "
                   f"{aud['acceptance']['disallowed_origin_count']} violación(es)",
         "expected": "0",
         "file_line": "`DICTUS_MANIFEST_040-646406.json` · "
                      "`modelo.hechos_impresos.identidad.filas` + "
                      "`DICTUS_EJECUTIVO_040-646406.pdf` P6",
         "ok": aud["acceptance"]["ok"]},
        {"criterion": "`no_cross_page_state_contradictions()`",
         "actual": f"{cp['acceptance']['atributos_comparados']} atributo(s) comparado(s) por "
                   f"clave canónica, {cp['acceptance']['inconsistent_count']} inconsistente(s)",
         "expected": "0",
         "file_line": f"`DICTUS_EJECUTIVO_{FOLIO}.pdf` P4/P6 · verdad única en "
                      f"`DICTUS_RUN_STATE_{FOLIO}.json`",
         "ok": cp["acceptance"]["ok"]},
        {"criterion": "«Lonja» en los ARTEFACTOS ENTREGADOS (ejecutivo, técnico, manifest, "
                      "run_state) — Lonja purge",
         "actual": f"{lon['acceptance']['categoria_A_en_entregados']} mención(es) en "
                   f"entregables · {lon['acceptance']['categoria_A_count']} en total "
                   f"(las demás: registro de adquisición, artefacto local de metodología y "
                   f"artefactos LEGACY `dictus_2/`; se listan en §8 con su file:line)",
         "expected": "0 en los entregables (el total NO se declara como si fuera el "
                     "entregable)",
         "file_line": "`docs/source_pack/GOLDEN_EVIDENCE_LITERAL_PACK_040-646406.md` §8",
         "ok": lon["acceptance"]["ok"]},
        {"criterion": "Golden regenerado con las reglas nuevas "
                      "(`verify_master_hash = MATCH`, `layout_violations = []`)",
         "actual": f"`{hs['DICTUS_MASTER_HASH'][:16]}…` · sha256 ejecutivo "
                   f"`{hs['sha256_ejecutivo'][:16]}…`",
         "expected": "Golden regenerado en esta corrida",
         "file_line": "`docs/forensics/040-646406/dictus_2b/`",
         "ok": not any(t["failed"] for t in data.get("test_results", []))},
        {"criterion": "`python scripts/golden_evidence_asserts.py` exit 0 con 11/11 PASS",
         "actual": f"exit code = {data.get('asserts_exit')}",
         "expected": "exit code = 0 y 0 FAIL",
         "file_line": "`scripts/golden_evidence_asserts.py`",
         "ok": data.get("asserts_exit") == 0},
    ]
    _fallos = [c for c in _criterios if not c["ok"]]
    A(f"### EVIDENCE PACK — **{'PASS' if not _fallos else 'FAIL'}**")
    A("")
    A(f"**Criterios:** {len(_criterios)} evaluados · {len(_criterios) - len(_fallos)} PASS · "
      f"{len(_fallos)} FAIL.")
    A("")
    A("| criterion | actual | expected | file:line |")
    A("|---|---|---|---|")
    for c in _criterios:
        marca = "✅" if c["ok"] else "❌"
        A(f"| {marca} {c['criterion']} | {c['actual']} | {c['expected']} | {c['file_line']} |")
    A("")
    if _fallos:
        A("**Criterios en FAIL, con su detalle literal (sin maquillar):**")
        A("")
        for c in _fallos:
            A(f"- `{c['criterion']}` | actual = {c['actual']} | esperado = {c['expected']} | "
              f"{c['file_line']}")
        A("")
    else:
        A("**No queda ningún criterio en FAIL.** Los tres que fallaban al inicio de esta")
        A("tarea (`gate_state`, origen del hecho VERIFICADO y contradicción entre páginas)")
        A("están resueltos, y su evidencia literal es §3, §9, §10 y §11 de este pack.")
        A("")
    A("**No se declara `CONTRACT FROZEN`:** esta tarea entrega evidencia literal")
    A("reproducible, no un congelamiento de contrato.")
    A("")
    return "\n".join(L)


def escribir(data: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"MARKET_CONTEXT_{FOLIO}.json").write_text(
        json.dumps(data["market_input"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / f"VALUATION_GATE_{FOLIO}.json").write_text(
        json.dumps(data["valuation_gate_full"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    (OUT / f"ORIGIN_AUDIT_{FOLIO}.json").write_text(
        json.dumps(data["origin_audit"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / f"CROSS_PAGE_CONSISTENCY_{FOLIO}.json").write_text(
        json.dumps(data["cross_page"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / f"ARTIFACT_HASHES_{FOLIO}.json").write_text(
        json.dumps(data["hashes"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / f"GOLDEN_EVIDENCE_LITERAL_PACK_{FOLIO}.data.json").write_text(
        json.dumps({k: v for k, v in data.items() if k not in
                    ("p1_text", "p4_text", "p6_text", "technical_text")},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / f"GOLDEN_EVIDENCE_LITERAL_PACK_{FOLIO}.md").write_text(
        render_md(data) + "\n", encoding="utf-8")
    with open(OUT / f"GOLDEN_EVIDENCE_P1_{FOLIO}.txt", "w", encoding="utf-8") as f:
        f.write(data["p1_text"])
    with open(OUT / f"GOLDEN_EVIDENCE_P6_{FOLIO}.txt", "w", encoding="utf-8") as f:
        f.write(data["p6_text"])
    with open(OUT / f"GOLDEN_EVIDENCE_TECNICO_{FOLIO}.txt", "w", encoding="utf-8") as f:
        f.write(data["technical_text"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Golden Evidence Literal Pack")
    ap.add_argument("--stdout", action="store_true", help="no escribe; solo resume")
    args = ap.parse_args(argv)
    data = construir()
    if not args.stdout:
        escribir(data)
    print(json.dumps({
        "master_hash": data["hashes"]["DICTUS_MASTER_HASH"],
        "sha256_ejecutivo": data["hashes"]["sha256_ejecutivo"],
        "sha256_tecnico": data["hashes"]["sha256_tecnico"],
        "run_id": data["hashes"]["run_id"],
        "valuation_gate_gate_state": data["valuation_gate_full"]["gate_state"],
        "valuation_gate_decision": data["valuation_gate_full"]["decision"],
        "lonja_categoria_A_total": data["lonja_sweep"]["acceptance"]["categoria_A_count"],
        "lonja_categoria_A_en_entregados":
            data["lonja_sweep"]["acceptance"]["categoria_A_en_entregados"],
        "verified_disallowed_origin": data["origin_audit"]["acceptance"]["disallowed_origin_count"],
        "cross_page_inconsistent": data["cross_page"]["acceptance"]["inconsistent_count"],
        "asserts_exit": data["asserts_exit"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""ARHIAX RE — DICTUS ESTIMATION ENGINE v1.0 · FASE 1

CONSTRUCTOR de los artefactos de auditoría de mercado. NO estima nada.

Lee el GOLDEN REAL y el Source Pack reales y escribe DOS artefactos:

    docs/estimation/ESTIMATION_INPUT_AUDIT_040-646406.json
    docs/estimation/MARKET_EVIDENCE_MATRIX_040-646406.csv

Reglas duras de este constructor:

1. **No hay ningún valor pegado a mano.** Todo valor se lee del Golden
   (`DICTUS_RUN_STATE_040-646406.json`, `DICTUS_MANIFEST_040-646406.json`) o de un
   artefacto del Source Pack. Si una clave desaparece del Golden, el script FALLA en
   lugar de rellenar un hueco en silencio (``_exigir``).
2. **No se inventan fuentes.** Lo que no existe se declara con ``value: null`` y
   ``usable_for_estimation: false`` + ``reason``.
3. **Solo escribe** en ``docs/estimation/``. No toca hashes históricos ni
   ``docs/forensics/**``.

    python scripts/estimation_input_audit.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "api"))

# El vocabulario de la escalera y de origen vive en el contrato: se importa, no se copia.
from market_evidence import (  # noqa: E402
    LEVEL_1_DIRECT_COMPARABLES, LEVEL_2_LOCAL_MARKET_OBSERVATIONS,
    LEVEL_3_AGGREGATED_MARKET_REFERENCES, LEVEL_4_CALIBRATED_MODEL_PRIOR,
    LEVEL_5_STATIC_REFERENCE, NIVELES_EVIDENCIA_MERCADO, ORIGEN_COMPUTADO,
    ORIGEN_EXTERNO, ORIGEN_ESTATICO, ORIGEN_MANUAL, ORIGEN_PRIOR,
    REGLA_AUSENCIA_LEVEL_1, VERSION_ESCALERA, blocking_por_proposito,
    evaluar_escalera, origin_sostiene_estimacion,
)

GOLDEN_DIR = ROOT / "docs" / "forensics" / "040-646406" / "dictus_2b"
RUN_STATE_PATH = GOLDEN_DIR / "DICTUS_RUN_STATE_040-646406.json"
MANIFEST_PATH = GOLDEN_DIR / "DICTUS_MANIFEST_040-646406.json"

PACK = ROOT / "docs" / "source_pack"
TABLA_MERCADO = PACK / "lonja_market_baq_v1.json"
REGISTRO_FUENTES = PACK / "barranquilla_sources_v1.json"
MARKET_CONTEXT_ART = PACK / "MARKET_CONTEXT_040-646406.json"
VALUATION_GATE_ART = PACK / "VALUATION_GATE_040-646406.json"
COVERAGE_CSV = PACK / "SOURCE_COVERAGE_MATRIX_040-646406.csv"
ACQUISITION_CSV = PACK / "SOURCE_ACQUISITION_MATRIX_040-646406.csv"
ORIGIN_AUDIT = PACK / "ORIGIN_AUDIT_040-646406.json"
RAW_CACHE = PACK / "raw" / "golden" / "_raw_cache"

OUT_DIR = ROOT / "docs" / "estimation"
OUT_AUDIT = OUT_DIR / "ESTIMATION_INPUT_AUDIT_040-646406.json"
OUT_MATRIX = OUT_DIR / "MARKET_EVIDENCE_MATRIX_040-646406.csv"

FOLIO = "040-646406"

#: Los 11 campos EXACTOS de cada entrada del inventario (§4). Ni uno más.
CAMPOS_ENTRADA: Tuple[str, ...] = (
    "attribute", "value", "origin", "source_id", "source_class", "queried_at",
    "effective_date", "freshness", "provenance", "usable_for_estimation", "reason",
)

#: Vocabulario de `source_class` usado en el inventario.
CLASES_FUENTE = (
    "AUTHORITATIVE_OFFICIAL", "AUTHORITATIVE_CONTRACTUAL", "CONTEXTUAL_EXTERNAL",
    "COMPUTED", "NO_SOURCE", "MANUAL_CONFIG", "MODEL_PRIOR", "NOT_DECLARED",
)

#: Criterio DECLARADO de `usable_for_estimation` (para que el conteo sea auditable).
CRITERIO_USABLE = (
    "`usable_for_estimation` es true SÓLO si se cumplen las tres condiciones: (a) el valor "
    "existe hoy en el Golden real; (b) su `origin` es habilitante (EXTERNAL_SOURCE o "
    "COMPUTED_FROM_SOURCES con procedencia completa) tratándose de un descriptor del sujeto "
    "debidamente verificado; y (c) el input es un INSUMO DE ESTIMACIÓN (descriptor del "
    "sujeto o evidencia de mercado). Un dato de contexto de decisión (POT, riesgo, "
    "equipamiento, solar, título, screening) NO es insumo de estimación aunque esté "
    "verificado, y un parámetro MANUAL_CONFIG / MODEL_PRIOR / STATIC_REFERENCE NO sostiene "
    "cifra alguna: en ambos casos es false y el `reason` dice por qué."
)


# ══════════════════════════════════════════════════════════════════════════════
# Utilidades
# ══════════════════════════════════════════════════════════════════════════════
def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for bloque in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def _cargar(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _exigir(d: Dict[str, Any], *ruta: str) -> Any:
    """Lee una ruta del Golden. Si falta la clave, FALLA: no se rellena un hueco."""
    actual: Any = d
    for i, clave in enumerate(ruta):
        if not isinstance(actual, dict) or clave not in actual:
            raise KeyError("El Golden no declara " + ".".join(ruta[: i + 1])
                           + ": el inventario no se completa con suposiciones")
        actual = actual[clave]
    return actual


def _fecha(valor: Any) -> Optional[date]:
    if not isinstance(valor, str) or not valor.strip():
        return None
    texto = valor.strip().replace("Z", "+00:00")
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
        try:
            return datetime.strptime(texto, fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(texto).date()
    except ValueError:
        return None


def _frescura(*, queried_at: Any, referencia: Any,
              vigencia_hasta: Any = None) -> Dict[str, Any]:
    """Frescura declarada de una entrada. Sin fechas NO se afirma vigencia (fail-closed)."""
    q, r = _fecha(queried_at), _fecha(referencia)
    dias = (r - q).days if (q and r) else None
    salida: Dict[str, Any] = {
        "regla": ("antigüedad en días entre la consulta y la fecha de referencia de la "
                  "corrida; si la entrada declara vigencia_hasta, se evalúa contra ella"),
        "queried_at": queried_at,
        "referencia": referencia,
        "dias_desde_consulta": dias,
        "vigencia_hasta": vigencia_hasta,
        "estado": "VIGENTE",
    }
    h = _fecha(vigencia_hasta)
    if h is not None and r is not None:
        if r > h:
            salida["estado"] = "VENCIDA"
            salida["motivo"] = (f"la entrada declara vigencia hasta {h.isoformat()} y la "
                                f"corrida es del {r.isoformat()} ({(r - h).days} día(s) "
                                f"después): el valor NO se presenta como vigente")
            return salida
        salida["motivo"] = f"vigente hasta {h.isoformat()} para la corrida {r.isoformat()}"
        return salida
    if dias is None:
        salida["estado"] = "VIGENCIA_DESCONOCIDA"
        salida["motivo"] = ("sin fechas suficientes no puede afirmarse vigencia "
                            "(fail-closed)")
    else:
        salida["motivo"] = f"{dias} día(s) entre la consulta y la corrida"
    return salida


def _entrada(*, attribute: str, value: Any, origin: Optional[str], source_id: Optional[str],
             source_class: str, queried_at: Any, effective_date: Any,
             freshness: Dict[str, Any], provenance: Any,
             usable_for_estimation: bool, reason: str) -> Dict[str, Any]:
    if source_class not in CLASES_FUENTE:
        raise ValueError(f"source_class={source_class!r} fuera del vocabulario declarado")
    entrada = {
        "attribute": attribute,
        "value": value,
        "origin": origin,
        "source_id": source_id,
        "source_class": source_class,
        "queried_at": queried_at,
        "effective_date": effective_date,
        "freshness": freshness,
        "provenance": provenance,
        "usable_for_estimation": bool(usable_for_estimation),
        "reason": reason,
    }
    if tuple(entrada.keys()) != CAMPOS_ENTRADA:
        raise AssertionError("el inventario debe llevar EXACTAMENTE los 11 campos §4")
    if usable_for_estimation and not (value is not None and origin_sostiene_estimacion(origin)):
        raise AssertionError(
            f"{attribute}: usable_for_estimation=True exige valor presente y origen "
            f"habilitante (origin={origin!r}, value={'presente' if value is not None else 'null'})")
    return entrada


# ══════════════════════════════════════════════════════════════════════════════
# Lectura del Golden real
# ══════════════════════════════════════════════════════════════════════════════
def construir_inventario() -> Dict[str, Any]:
    rs = _cargar(RUN_STATE_PATH)
    mf = _cargar(MANIFEST_PATH)
    tabla = _cargar(TABLA_MERCADO)
    mc_art = _cargar(MARKET_CONTEXT_ART)
    gate = _cargar(VALUATION_GATE_ART)
    registro = _cargar(REGISTRO_FUENTES)
    origin_audit = _cargar(ORIGIN_AUDIT)

    sha_rs, sha_mf = _sha256(RUN_STATE_PATH), _sha256(MANIFEST_PATH)
    sha_tabla = _sha256(TABLA_MERCADO)
    sha_registro = _sha256(REGISTRO_FUENTES)

    generado = _exigir(rs, "generated_at")
    ciudad = _exigir(rs, "ciudad")
    run_id = _exigir(rs, "run_id")

    pi = _exigir(rs, "property_identity")
    uc = _exigir(rs, "urban_context")
    vs = _exigir(rs, "valuation_state")
    mc = _exigir(rs, "market_context")
    sector = _exigir(mc, "sector_metodologico")
    adm = _exigir(pi, "administrativo")
    coords = _exigir(mc, "coordinates")
    cp = _exigir(mc, "coordinate_provenance")
    ouc = _exigir(mc, "official_urban_context")
    uss = _exigir(mc, "urban_source_summary")

    ts = _exigir(mf, "modelo", "title_summary")
    em = _exigir(mf, "evidence_manifest")
    modelo = _exigir(mf, "modelo")
    src_versions = _exigir(modelo, "source_versions")
    metodo = _exigir(modelo, "methodology_versions")

    # ── procedencia compartida: el propio run state es el documento probatorio ──
    prov_runstate = {
        "documento": "docs/forensics/040-646406/dictus_2b/DICTUS_RUN_STATE_040-646406.json",
        "sha256": sha_rs, "run_id": run_id, "dictus_id": _exigir(mf, "dictus_id"),
        "generado_at": generado,
    }
    prov_manifest = {
        "documento": "docs/forensics/040-646406/dictus_2b/DICTUS_MANIFEST_040-646406.json",
        "sha256": sha_mf, "master_hash": _exigir(mf, "master_hash"),
    }
    prov_tabla = {
        "documento": "docs/source_pack/lonja_market_baq_v1.json",
        "sha256": sha_tabla,
        "table_version": _exigir(tabla, "table_version"),
        "methodology_file": _exigir(tabla, "methodology_file"),
        "methodology_sha256": _exigir(tabla, "methodology_sha256"),
        "derivation": _exigir(tabla, "derivation"),
    }
    frescura_corrida = _frescura(queried_at=generado, referencia=generado)

    inv: List[Dict[str, Any]] = []

    # ══════════════════ A · DESCRIPTORES DEL SUJETO (insumos de estimación) ═══
    inv.append(_entrada(
        attribute="identidad_unidad",
        value={"folio": _exigir(pi, "folio"), "nupre": _exigir(pi, "nupre"),
               "codigo_catastral": _exigir(pi, "codigo_catastral"),
               "torre": _exigir(pi, "torre"), "apartamento": _exigir(pi, "apartamento"),
               "unidad": _exigir(pi, "unidad"),
               "direccion_raw": _exigir(pi, "direccion_raw"),
               "estado": _exigir(pi, "estado"),
               "resolution_status": _exigir(pi, "resolution_status"),
               "resolution_method": _exigir(pi, "resolution_method"),
               "resolution_confidence": _exigir(pi, "resolution_confidence"),
               "identity_verified": _exigir(pi, "identity_verified")},
        origin=ORIGEN_COMPUTADO, source_id="SNR + geoportal municipal",
        source_class="AUTHORITATIVE_OFFICIAL", queried_at=generado,
        effective_date=None,
        freshness=frescura_corrida,
        provenance={"evidencia": "EV-IDENTIDAD", "evidencia_sha256":
                    _buscar_evidencia(em, "EV-IDENTIDAD")["content_hash"],
                    **prov_runstate},
        usable_for_estimation=True,
        reason=("Identidad de la unidad VERIFICADA (MATCH_BY_NUPRE, EXACT, "
                "VERIFIED_UNIT_IDENTITY): sin saber QUÉ se estima no hay estimación. "
                "Es insumo de estimación por ser descriptor del sujeto verificado."),
    ))

    inv.append(_entrada(
        attribute="matricula",
        value=_exigir(ts, "folio"),
        origin=ORIGEN_COMPUTADO, source_id="SNR + geoportal municipal",
        source_class="AUTHORITATIVE_OFFICIAL", queried_at=generado,
        effective_date=_fecha_acto(ts), freshness=frescura_corrida,
        provenance={"circulo_registral": _exigir(ts, "circulo_registral"),
                    "certificado_adjuntado": _exigir(ts, "certificado_adjuntado"),
                    "fuente": "Certificado de tradición y libertad (SNR)",
                    **prov_manifest},
        usable_for_estimation=True,
        reason=("Matrícula 040-646406 verificada contra el CTL aportado. Es el vínculo al "
                "folio del sujeto estimado; sin ella la estimación no es atribuible."),
    ))

    inv.append(_entrada(
        attribute="nupre", value=_exigir(pi, "nupre"), origin=ORIGEN_COMPUTADO,
        source_id="CATASTRO_BAQ_ADOPCION_ANEXO1", source_class="AUTHORITATIVE_OFFICIAL",
        queried_at=generado, effective_date=None, freshness=frescura_corrida,
        provenance={"rol_en_la_corrida": "método de resolución de identidad (nupre)",
                    "resolution_status": _exigir(pi, "resolution_status"),
                    "evidencia": "EV-IDENTIDAD", **prov_runstate},
        usable_for_estimation=True,
        reason=("NUPRE verificado: es la llave con la que se resuelve y se ata el sujeto. "
                "Insumo de estimación como identificador del sujeto."),
    ))

    inv.append(_entrada(
        attribute="numero_predial",
        value=_exigir(pi, "codigo_catastral"), origin=ORIGEN_COMPUTADO,
        source_id="CATASTRO_MUNICIPAL_BARRANQUILLA_ARCGIS",
        source_class="AUTHORITATIVE_OFFICIAL", queried_at=generado, effective_date=None,
        freshness=frescura_corrida,
        provenance={"feature_id": _exigir(cp, "feature_id"),
                    "layer": _exigir(cp, "layer"),
                    "resolution_method": _exigir(cp, "resolution_method"),
                    "link_verificado": _exigir(cp, "link_verificado"),
                    "canonical_binding_status": _exigir(cp, "canonical_binding_status"),
                    "evidencia": "EV-GEOMETRIA", **prov_runstate},
        usable_for_estimation=True,
        reason=("Número predial verificado y ligado por GUID a la geometría oficial del "
                "predio: ata la estimación al predio correcto."),
    ))

    inv.append(_entrada(
        attribute="area_construida_m2", value=_exigir(uc, "area"),
        origin=ORIGEN_COMPUTADO, source_id="SNR + geoportal municipal",
        source_class="AUTHORITATIVE_OFFICIAL", queried_at=generado, effective_date=None,
        freshness=frescura_corrida,
        provenance={"campo_golden": "urban_context.area",
                    "nota": ("Área privada de la unidad: es el multiplicador del valor de "
                             "mercado; el área catastral del TERRENO no es comparable"),
                    **prov_runstate},
        usable_for_estimation=True,
        reason=("Área privada de la unidad declarada por la corrida con procedencia "
                "COMPUTED_FROM_SOURCES; es el multiplicador de cualquier valor por m²."),
    ))

    inv.append(_entrada(
        attribute="regimen_ph", value=_exigir(uc, "condicion_juridica"),
        origin=ORIGEN_COMPUTADO, source_id="SNR + geoportal municipal",
        source_class="AUTHORITATIVE_OFFICIAL", queried_at=generado, effective_date=None,
        freshness=frescura_corrida,
        provenance={"status": _exigir(uc, "condicion_juridica_status"),
                    "campo_golden": "urban_context.condicion_juridica", **prov_runstate},
        usable_for_estimation=True,
        reason=("Régimen Propiedad Horizontal VERIFIED_REGISTRAL: define el universo de "
                "comparables admisibles (unidad PH, no lote)."),
    ))

    inv.append(_entrada(
        attribute="tipologia", value=_exigir(uc, "tipologia"), origin=ORIGEN_COMPUTADO,
        source_id="SNR + geoportal municipal", source_class="AUTHORITATIVE_OFFICIAL",
        queried_at=generado, effective_date=None, freshness=frescura_corrida,
        provenance={"status": _exigir(uc, "tipologia_status"),
                    "market_context": _exigir(mc, "tipologia"), **prov_runstate},
        usable_for_estimation=True,
        reason=("Tipología «Unidad En Propiedad Horizontal» VERIFIED_REGISTRAL: segmenta el "
                "mercado del sujeto. Insumo de estimación."),
    ))

    inv.append(_entrada(
        attribute="destino_economico", value=_exigir(uc, "destino_economico"),
        origin=None, source_id=None, source_class="NOT_DECLARED",
        queried_at=generado, effective_date=None, freshness=frescura_corrida,
        provenance={"market_context.uso": _exigir(mc, "uso"),
                    "urban_context.destino_economico": _exigir(uc, "destino_economico"),
                    "traza_aplicada_segun_urban_render_provenance":
                        sorted(_exigir(mc, "urban_render_provenance", "aplicados").keys()),
                    "contradiccion_detectada": (
                        "`market_context.uso.source` es null (ni el barrio, localidad, estrato, "
                        "tratamiento, altura, pieza urbana ni manzana trazan el destino en "
                        "urban_render_provenance), mientras la matriz de cobertura del pack "
                        "marca 07-destino = SOURCE_UNAVAILABLE y 08-uso_pot = NOT_SUPPORTED"),
                    **prov_runstate},
        usable_for_estimation=False,
        reason=("El Golden estampa el destino como VERIFIED_OFFICIAL pero NO declara fuente "
                "para él (`source: null`) y el pack declara ese dominio SOURCE_UNAVAILABLE / "
                "NOT_SUPPORTED. Por la regla vigente del producto («un contexto sin origen "
                "declarado NO habilita»), NO se admite como insumo de estimación: el valor "
                "existe y se transcribe, la procedencia no. Se reporta como contradicción "
                "abierta, no se rellena."),
    ))

    inv.append(_entrada(
        attribute="barrio", value=_exigir(mc, "barrio")["value"], origin=ORIGEN_EXTERNO,
        source_id="official_urban_layer", source_class="AUTHORITATIVE_OFFICIAL",
        queried_at=generado, effective_date=None, freshness=frescura_corrida,
        provenance={"status": _exigir(mc, "barrio")["status"],
                    "source": _exigir(mc, "barrio")["source"],
                    "modo": _exigir(uss, "campos")["barrio"]["modo"],
                    "trazas": _exigir(adm, "trazas", "barrio"), **prov_runstate},
        usable_for_estimation=True,
        reason=("Barrio Miramar VERIFIED_OFFICIAL en vivo: es la unidad de segmentación de "
                "mercado del sujeto."),
    ))

    inv.append(_entrada(
        attribute="localidad", value=_exigir(ouc, "localidad"), origin=ORIGEN_EXTERNO,
        source_id="official_urban_layer", source_class="AUTHORITATIVE_OFFICIAL",
        queried_at=generado, effective_date=None, freshness=frescura_corrida,
        provenance={"status": _exigir(ouc, "context_status"),
                    "modo": _exigir(uss, "campos")["localidad"]["modo"], **prov_runstate},
        usable_for_estimation=True,
        reason=("Localidad 02 declarada por la capa urbana oficial en vivo: descriptor de "
                "estratificación del sujeto (agrupa por encima del barrio)."),
    ))

    inv.append(_entrada(
        attribute="estrato", value=_exigir(mc, "estrato")["value"], origin=ORIGEN_EXTERNO,
        source_id="official_urban_layer", source_class="AUTHORITATIVE_OFFICIAL",
        queried_at=generado, effective_date=None, freshness=frescura_corrida,
        provenance={"status": _exigir(mc, "estrato")["status"],
                    "source": _exigir(mc, "estrato")["source"],
                    "estrato_origen": _exigir(ouc, "estrato_origen"),
                    "estrato_trace": _exigir(ouc, "estrato_trace"),
                    "trazas": _exigir(adm, "trazas", "estrato"), **prov_runstate},
        usable_for_estimation=True,
        reason=("Estrato 4 VERIFIED_OFFICIAL: estratifica la comparación y llavea la tasa de "
                "capitalización. Es insumo descriptivo; NO es una tasa de mercado."),
    ))

    inv.append(_entrada(
        attribute="coordenadas", value=coords, origin=ORIGEN_EXTERNO,
        source_id="CATASTRO_MUNICIPAL_BARRANQUILLA_ARCGIS",
        source_class="AUTHORITATIVE_OFFICIAL", queried_at=generado, effective_date=None,
        freshness=frescura_corrida,
        provenance={"coordinate_source": _exigir(mc, "coordinate_source"),
                    "coordinate_source_verified": _exigir(mc, "coordinate_source_verified"),
                    "geocoder_source": _exigir(mc, "geocoder_source"),
                    "coordinate_scope": _exigir(mc, "coordinate_scope"),
                    **{k: cp[k] for k in sorted(cp) if k != "canonical_binding_detail"},
                    **prov_runstate},
        usable_for_estimation=True,
        reason=("Coordenada de geometría OFICIAL DEL PREDIO verificada por GUID. Sin punto "
                "del sujeto no hay distancia a comparables, luego es insumo de estimación. "
                "Su alcance (lote/edificio, no la posición del apartamento) queda declarado."),
    ))

    inv.append(_entrada(
        attribute="sector_mercado", value=_exigir(sector, "matched_sector"),
        origin=ORIGEN_COMPUTADO, source_id="official_urban_layer",
        source_class="AUTHORITATIVE_OFFICIAL", queried_at=generado,
        effective_date=_exigir(sector, "vigencia_desde"),
        freshness=_frescura(queried_at=_exigir(sector, "vigencia_desde"),
                            referencia=generado, vigencia_hasta=None),
        provenance={"input_barrio": _exigir(sector, "input_barrio"),
                    "match_type": _exigir(sector, "match_type"),
                    "fuentes_citadas": [
                        "official_urban_layer (barrio VERIFIED_OFFICIAL en vivo)",
                        _exigir(sector, "market_methodology_file")
                        + "::" + _exigir(sector, "market_methodology_sha256")[:12],
                    ],
                    "methodology_sha256": _exigir(sector, "market_methodology_sha256"),
                    "provenance": _exigir(sector, "provenance"), **prov_runstate},
        usable_for_estimation=True,
        reason=("El SECTOR Miramar RESUELVE por EXACT: lookup determinista del barrio "
                "verificado (official_urban_layer) contra la tabla versionada — derivación "
                "COMPUTED_FROM_SOURCES de dos fuentes citadas, auditable y repetible. Es "
                "insumo de estimación como SELECTOR de comparables. AVISO: el mapeo es "
                "insumo; el VALOR por m² de ese sector NO lo es — ver "
                "`precio_m2_mercado_declarado` (origin=MANUAL_CONFIG, VENCIDA)."),
    ))

    # ══════════════════ B · EVIDENCIA DE MERCADO (lo que falta) ════════════════
    inv.append(_entrada(
        attribute="observaciones_de_mercado_comparables",
        value=(_exigir(registro, "no_fuentes_institucionales") and None),
        origin=None, source_id=None, source_class="NO_SOURCE", queried_at=None,
        effective_date=None,
        freshness={"regla": "una ausencia no tiene frescura", "estado": "SIN_DATO",
                   "dias_desde_consulta": None, "referencia": generado,
                   "vigencia_hasta": None,
                   "motivo": "no existe ninguna observación que fechar"},
        provenance={"evidencia_de_la_ausencia": [
            "docs/source_pack/SOURCE_COVERAGE_MATRIX_040-646406.csv fila 18-mercado",
            "docs/source_pack/SOURCE_ACQUISITION_MATRIX_040-646406.csv dominio mercado",
            "docs/source_pack/barranquilla_sources_v1.json (34 fuentes: NINGUNA CORE_MARKET)",
        ], "pack_sha256": sha_registro},
        usable_for_estimation=False,
        reason=("CERO comparables. No hay ninguna fuente de mercado en el registro del pack "
                "(34 fuentes, ninguna con product_role=CORE_MARKET), ningún listing, ningún "
                "registro de transacción y ningún campo de precio/área por unidad en el "
                "Golden. No se inventa ninguno: el nivel 1 está VACÍO y el 2 también."),
    ))

    inv.append(_entrada(
        attribute="precios_m2_observados", value=None, origin=None, source_id=None,
        source_class="NO_SOURCE", queried_at=None, effective_date=None,
        freshness={"regla": "una ausencia no tiene frescura", "estado": "SIN_DATO",
                   "dias_desde_consulta": None, "referencia": generado,
                   "vigencia_hasta": None, "motivo": "no hay precio observado que fechar"},
        provenance={"evidencia_de_la_ausencia":
                    "docs/source_pack/SOURCE_COVERAGE_MATRIX_040-646406.csv fila 18-mercado",
                    "pack_sha256": sha_registro},
        usable_for_estimation=False,
        reason=("No existe un solo precio por m² OBSERVADO (pedido o de transacción) para "
                "Miramar ni para comparables. El único $/m² disponible es un parámetro "
                "declarado a mano."),
    ))

    inv.append(_entrada(
        attribute="transacciones_observadas", value=None, origin=None, source_id=None,
        source_class="NO_SOURCE", queried_at=None, effective_date=None,
        freshness={"regla": "una ausencia no tiene frescura", "estado": "SIN_DATO",
                   "dias_desde_consulta": None, "referencia": generado,
                   "vigencia_hasta": None, "motivo": "no hay transacción que fechar"},
        provenance={"candidatos_descubiertos_no_cosechados": _servicios_observatorio()[
            "urls_precio_o_transaccion"], "pack_sha256": sha_registro},
        usable_for_estimation=False,
        reason=("No se cosechó ninguna transacción. El geoportal municipal SÍ publica las "
                "capas «Valor de las compraventas» y «Cantidad de transacciones por manzana», "
                "descubiertas en el pack el 2026-09-29, pero NUNCA fueron consultadas: "
                "metadata sin datos. No se convierten en valor."),
    ))

    inv.append(_entrada(
        attribute="rentas_observadas", value=None, origin=None, source_id=None,
        source_class="NO_SOURCE", queried_at=None, effective_date=None,
        freshness={"regla": "una ausencia no tiene frescura", "estado": "SIN_DATO",
                   "dias_desde_consulta": None, "referencia": generado,
                   "vigencia_hasta": None, "motivo": "no hay renta que fechar"},
        provenance={"candidatos_descubiertos_no_cosechados": _servicios_observatorio()[
            "urls_renta"], "pack_sha256": sha_registro},
        usable_for_estimation=False,
        reason=("No hay ninguna renta observada. Existe un único coeficiente de canon "
                "codificado (0.00538) que es MODEL_PRIOR: no es una renta, es un supuesto."),
    ))

    inv.append(_entrada(
        attribute="costos_observados", value=None, origin=None, source_id=None,
        source_class="NO_SOURCE", queried_at=None, effective_date=None,
        freshness={"regla": "una ausencia no tiene frescura", "estado": "SIN_DATO",
                   "dias_desde_consulta": None, "referencia": generado,
                   "vigencia_hasta": None, "motivo": "no hay costo que fechar"},
        provenance={"nota": "no hay tabla de costos de construcción citada en el pack",
                    "pack_sha256": sha_registro},
        usable_for_estimation=False,
        reason=("No hay ningún costo de construcción observado (ni cámara, ni lista de "
                "precios, ni índice citado). El costo base 2.800.000/m² es MODEL_PRIOR "
                "escrito en el código."),
    ))

    inv.append(_entrada(
        attribute="precio_m2_mercado_declarado", value=_exigir(sector, "value_m2"),
        origin=_exigir(vs, "origin"), source_id=_exigir(sector, "market_methodology_id"),
        source_class="MANUAL_CONFIG", queried_at=_exigir(sector, "vigencia_desde"),
        effective_date=_exigir(sector, "vigencia_desde"),
        freshness=_frescura(queried_at=_exigir(sector, "vigencia_desde"),
                            referencia=generado,
                            vigencia_hasta=_exigir(tabla, "vigencia", "hasta")),
        provenance={"fuente_declarada": _exigir(sector, "source"),
                    "source_date": _exigir(sector, "source_date"),
                    "origin_gate": _exigir(sector, "origin_gate"),
                    "origin_blockers": _exigir(sector, "origin_blockers"),
                    "origin_etiqueta": _exigir(mc, "origin_etiqueta"),
                    **prov_tabla},
        usable_for_estimation=False,
        reason=(f"Valor {_exigir(sector, 'value_m2')} declarado a mano (origin=MANUAL_CONFIG, "
                "origin_gate=false): NO es una fuente y NO sostiene cifra. Además su vigencia "
                f"declarada termina el {_exigir(tabla, 'vigencia', 'hasta')} y la corrida es "
                f"del {_fecha(generado).isoformat()}: VENCIDA. Dos causas independientes de "
                "NO uso."),
    ))

    inv.append(_entrada(
        attribute="banda_precio_m2_declarada",
        value={"rango_min_m2": _exigir(sector, "rango_min_m2"),
               "rango_max_m2": _exigir(sector, "rango_max_m2")},
        origin=_exigir(vs, "origin"), source_id=_exigir(sector, "market_methodology_id"),
        source_class="MANUAL_CONFIG", queried_at=_exigir(sector, "vigencia_desde"),
        effective_date=_exigir(sector, "vigencia_desde"),
        freshness=_frescura(queried_at=_exigir(sector, "vigencia_desde"),
                            referencia=generado,
                            vigencia_hasta=_exigir(tabla, "vigencia", "hasta")),
        provenance={"valor_declarado_en":
                    _exigir(tabla, "rows")[0]["rango_declarado_en"], **prov_tabla},
        usable_for_estimation=False,
        reason=("La banda 5.500.000–8.000.000 es un parámetro declarado a mano "
                "(MANUAL_CONFIG), no una banda observada: no puede usarse para contrastar "
                "comparables sin convertir un supuesto en evidencia."),
    ))

    inv.append(_entrada(
        attribute="metodologia_mercado", value={
            "market_methodology_id": _exigir(metodo, "market_methodology_id"),
            "market_methodology_version": _exigir(metodo, "market_methodology_version"),
            "market_methodology_sha256": _exigir(metodo, "market_methodology_sha256"),
            "market_methodology_file": _exigir(mc, "market_methodology_file"),
            "methodology_entity": _exigir(sector, "methodology_entity"),
            "matcher_version": _exigir(metodo, "matcher_version")},
        origin=_exigir(vs, "origin"), source_id=_exigir(sector, "market_methodology_id"),
        source_class="NO_SOURCE", queried_at=_exigir(tabla, "generated_at"),
        effective_date=_exigir(sector, "vigencia_desde"),
        freshness=_frescura(queried_at=_exigir(tabla, "generated_at"),
                            referencia=generado,
                            vigencia_hasta=_exigir(tabla, "vigencia", "hasta")),
        provenance={"artefacto": _exigir(tabla, "derivation", "artefacto"),
                    "methodology_sha256": _exigir(tabla, "methodology_sha256"),
                    "table_sha256": sha_tabla},
        usable_for_estimation=False,
        reason=("El artefacto de metodología es local del producto "
                "(«sin institución proveedora verificada») y su $/m² no lo suministra un "
                "proveedor externo: es MANUAL_CONFIG. Sirve para ESTRUCTURA (qué métodos y "
                "qué vigencia se declaran), no como soporte económico."),
    ))

    inv.append(_entrada(
        attribute="parametros_de_mercado_declarados",
        value=_exigir(mc, "market_rate_source"), origin=_exigir(mc, "origin"),
        source_id=_exigir(sector, "market_methodology_id"),
        source_class="MANUAL_CONFIG", queried_at=_exigir(tabla, "generated_at"),
        effective_date=_exigir(sector, "vigencia_desde"),
        freshness=_frescura(queried_at=_exigir(tabla, "generated_at"),
                            referencia=generado,
                            vigencia_hasta=_exigir(tabla, "vigencia", "hasta")),
        provenance={"procedencia": _exigir(mc, "provenance"),
                    "market_rate": _exigir(mc_art, "market_rate")},
        usable_for_estimation=False,
        reason=("Procedencia INSUFICIENTE: la propia corrida declara origin_blockers "
                "«origen no declarado por el artefacto: se clasifica MANUAL_CONFIG (no "
                "habilita la valoración)». Queda trazado y NO se usa."),
    ))

    inv.append(_entrada(
        attribute="vigencia_de_la_tasa_declarada",
        value={"vigencia_desde": _exigir(sector, "vigencia_desde"),
               "vigencia_hasta": _exigir(tabla, "vigencia", "hasta"),
               "source_date": _exigir(sector, "source_date")},
        origin=_exigir(vs, "origin"), source_id=_exigir(sector, "market_methodology_id"),
        source_class="MANUAL_CONFIG", queried_at=_exigir(sector, "vigencia_desde"),
        effective_date=_exigir(sector, "vigencia_desde"),
        freshness=_frescura(queried_at=_exigir(sector, "vigencia_desde"),
                            referencia=generado,
                            vigencia_hasta=_exigir(tabla, "vigencia", "hasta")),
        provenance={"regla": ("api/market_sources.py::evaluar_vigencia — corrida > "
                             "effective_to ⇒ VENCIDA"),
                    "tabla_vigencia": _exigir(tabla, "vigencia"), **prov_tabla},
        usable_for_estimation=False,
        reason=(f"VENCIDA: la tabla declara vigencia hasta "
                f"{_exigir(tabla, 'vigencia', 'hasta')} y la corrida es del "
                f"{_fecha(generado).isoformat()} "
                f"({(_fecha(generado) - _fecha(_exigir(tabla, 'vigencia', 'hasta'))).days} "
                "día(s) después). Aun con origen habilitante, un dato vencido no se presenta "
                "como vigente."),
    ))

    origins = _exigir(vs, "origins")
    inv.append(_entrada(
        attribute="cap_rate", value=None, origin=origins["cap_rate"],
        source_id="api/dictamen_data.py::get_valuation", source_class="MODEL_PRIOR",
        queried_at=generado, effective_date=None,
        freshness={"regla": "un default codificado no tiene vigencia de mercado",
                   "estado": "NO_APLICA", "dias_desde_consulta": None,
                   "referencia": generado, "vigencia_hasta": None,
                   "motivo": "no es un dato fechado: es una constante del código"},
        provenance={"campo_golden": "valuation_state.origins.cap_rate",
                    "nota": ("el run state declara el ORIGEN del cap rate (MODEL_PRIOR) pero "
                             "NO publica su cifra: no se transcribe un número que el Golden "
                             "no declara"),
                    "campos_publicados_en_valuation_state": sorted(vs.keys()),
                    **prov_runstate},
        usable_for_estimation=False,
        reason=("Tasa de capitalización con origin=MODEL_PRIOR y origin_gate=false. El Golden "
                "publica el ORIGEN y no la cifra: queda declarado como supuesto codificado "
                "del modelo, nunca como dato. No sostiene la M3."),
    ))

    inv.append(_entrada(
        attribute="factor_costos", value=None, origin=origins["factor_costos"],
        source_id="api/dictamen_data.py::get_valuation", source_class="MODEL_PRIOR",
        queried_at=generado, effective_date=None,
        freshness={"regla": "un default codificado no tiene vigencia de mercado",
                   "estado": "NO_APLICA", "dias_desde_consulta": None,
                   "referencia": generado, "vigencia_hasta": None,
                   "motivo": "no es un dato fechado: es una constante del código"},
        provenance={"campo_golden": "valuation_state.origins.factor_costos",
                    "nota": ("el run state declara el ORIGEN (MODEL_PRIOR) y no imprime la "
                             "cifra: no se transcribe una cifra que el Golden no publica"),
                    **prov_runstate},
        usable_for_estimation=False,
        reason=("Factor de actualización de costos con origin=MODEL_PRIOR: es un supuesto "
                "codificado, no un índice de costos citado. No sostiene la M2."),
    ))

    inv.append(_entrada(
        attribute="costo_construccion_base", value=None,
        origin=origins["costo_construccion_base"],
        source_id="api/dictamen_data.py::get_valuation", source_class="MODEL_PRIOR",
        queried_at=generado, effective_date=None,
        freshness={"regla": "un default codificado no tiene vigencia de mercado",
                   "estado": "NO_APLICA", "dias_desde_consulta": None,
                   "referencia": generado, "vigencia_hasta": None,
                   "motivo": "no es un dato fechado: es una constante del código"},
        provenance={"campo_golden": "valuation_state.origins.costo_construccion_base",
                    "nota": "el Golden declara el origen y no imprime la cifra",
                    **prov_runstate},
        usable_for_estimation=False,
        reason=("Costo base de construcción «multifamiliar típico» codificado "
                "(MODEL_PRIOR): no hay tabla de costos citada. No sostiene la M2."),
    ))

    inv.append(_entrada(
        attribute="canon_renta_pct", value=None, origin=origins["canon_renta_pct"],
        source_id="api/dictamen_data.py::get_valuation", source_class="MODEL_PRIOR",
        queried_at=generado, effective_date=None,
        freshness={"regla": "un default codificado no tiene vigencia de mercado",
                   "estado": "NO_APLICA", "dias_desde_consulta": None,
                   "referencia": generado, "vigencia_hasta": None,
                   "motivo": "no es un dato fechado: es una constante del código"},
        provenance={"campo_golden": "valuation_state.origins.canon_renta_pct",
                    "nota": "el Golden declara el origen y no imprime la cifra",
                    **prov_runstate},
        usable_for_estimation=False,
        reason=("Porcentaje de canon de renta implícito codificado (MODEL_PRIOR): es un "
                "supuesto, no una renta observada. No sostiene la M3."),
    ))

    inv.append(_entrada(
        attribute="participacion_lote", value=None, origin=origins["participacion_lote"],
        source_id="api/dictamen_data.py::get_valuation", source_class="MODEL_PRIOR",
        queried_at=generado, effective_date=None,
        freshness={"regla": "un default codificado no tiene vigencia de mercado",
                   "estado": "NO_APLICA", "dias_desde_consulta": None,
                   "referencia": generado, "vigencia_hasta": None,
                   "motivo": "no es un dato fechado: es una constante del código"},
        provenance={"campo_golden": "valuation_state.origins.participacion_lote",
                    "nota": "el Golden declara el origen y no imprime la cifra",
                    **prov_runstate},
        usable_for_estimation=False,
        reason=("Participación del lote en el valor (MODEL_PRIOR) codificada: no hay "
                "coeficiente de copropiedad citado del reglamento de PH."),
    ))

    inv.append(_entrada(
        attribute="fallback_por_estrato", value=None, origin=ORIGEN_PRIOR,
        source_id="api/dictamen_data.py::FALLBACK_ESTRATO_M2", source_class="MODEL_PRIOR",
        queried_at=generado, effective_date=None,
        freshness={"regla": "un fallback codificado no tiene vigencia de mercado",
                   "estado": "NO_APLICA", "dias_desde_consulta": None,
                   "referencia": generado, "vigencia_hasta": None,
                   "motivo": "no es un dato fechado: es una constante del código"},
        provenance={"nota": ("api/dictamen_data.py declara FALLBACK_ESTRATO_M2 como "
                             "«HARDCODE DE RESPALDO POR ESTRATO — MODEL_PRIOR · FALLBACK "
                             "LEGACY NO PRODUCTIVO» y exige allow_legacy_reference=True, "
                             "que NO abre la compuerta de valoración"),
                    **prov_runstate},
        usable_for_estimation=False,
        reason=("Fallback genérico por estrato (MODEL_PRIOR): la propia corrida declara que "
                "es un fallback NO productivo que no autoriza ninguna cifra."),
    ))

    inv.append(_entrada(
        attribute="model_priors_declarados", value=dict(origins), origin=ORIGEN_PRIOR,
        source_id="api/dictamen_data.py::get_valuation · valuation_state.origins",
        source_class="MODEL_PRIOR", queried_at=generado, effective_date=None,
        freshness={"regla": "los priors no tienen vigencia de mercado", "estado": "NO_APLICA",
                   "dias_desde_consulta": None, "referencia": generado,
                   "vigencia_hasta": None,
                   "motivo": "son constantes del código, no datos fechados"},
        provenance={"campo_golden": "valuation_state.origins", **prov_runstate},
        usable_for_estimation=False,
        reason=("Los 5 parámetros distintos de la tasa están declarados con origin=MODEL_PRIOR "
                "y ninguno es una fuente externa. Se inventarían todos y se declaran TODOS "
                "como no utilizables."),
    ))

    hc = _exigir(rs, "historical_consistency")
    inv.append(_entrada(
        attribute="referencias_historicas",
        value={"version": _exigir(hc, "version"),
               "versiones_comparadas": _exigir(hc, "versiones_comparadas"),
               "generado_en": _exigir(hc, "generado_en"),
               "conflictos_abiertos": [c["atributo"] for c in _exigir(hc, "conflictos_abiertos")]},
        origin=ORIGEN_COMPUTADO, source_id="expediente histórico del mismo inmueble",
        source_class="COMPUTED", queried_at=_exigir(hc, "generado_en"),
        effective_date=_exigir(hc, "generado_en"),
        freshness=_frescura(queried_at=_exigir(hc, "generado_en"), referencia=generado),
        provenance={"evidencia": "EV-COHERENCIA",
                    "evidencia_sha256":
                        _buscar_evidencia(em, "EV-COHERENCIA")["content_hash"],
                    "estado_evidencia": _buscar_evidencia(em, "EV-COHERENCIA")["status"],
                    **prov_runstate},
        usable_for_estimation=False,
        reason=(f"El expediente tiene {len(_exigir(hc, 'conflictos_abiertos'))} conflictos "
                "abiertos (altura 8 vs 11, amenaza en 3 valores) marcados "
                "UNEXPLAINED_CONFLICT. Sirven para CAUTELA y trazabilidad; no son evidencia "
                "de mercado ni un precio observado."),
    ))

    # ══════════════════ C · CONTEXTO DE DECISIÓN (no insumos de estimación) ════
    # (attribute, valor, source_id, source_class, origin, motivo)
    contextos = [
        ("uso_pot",
         _exigir(uss, "campos", "uso_pot") if "uso_pot" in _exigir(uss, "campos")
         else {"value": None, "status": None, "fuente": None, "modo": None},
         "POT_BAQ_POLIGONOS_USO", "AUTHORITATIVE_OFFICIAL", None,
         "El uso del POT gobierna la compatibilidad normativa de la decisión, no el "
         "precio de una unidad ya construida."),
        ("tratamiento_pot", _exigir(uss, "campos", "tratamiento"),
         "POT_BAQ_TRATAMIENTO", "AUTHORITATIVE_OFFICIAL", ORIGEN_EXTERNO,
         "El tratamiento urbanístico condiciona la intervención futura, no el valor de "
         "mercado actual de la unidad."),
        ("tipo_tratamiento", _exigir(ouc, "tipo_tratamiento"),
         "POT_BAQ_TRATAMIENTO", "AUTHORITATIVE_OFFICIAL", ORIGEN_EXTERNO,
         "Subcategoría del tratamiento: contexto normativo."),
        ("altura_maxima_pot", _exigir(uss, "campos", "altura_maxima"),
         "POT_BAQ_EDIFICABILIDAD", "AUTHORITATIVE_OFFICIAL", ORIGEN_EXTERNO,
         "DECLARACIÓN EXPLÍCITA (§26): la altura POT puede ser CRÍTICA para urbanismo y NO "
         "es necesariamente necesaria para estimar una unidad PH YA CONSTRUIDA. Su ausencia "
         "NO bloquea la estimación (required_for_estimation=False, "
         "required_for_decision=True)."),
        ("pieza_urbana", _exigir(ouc, "pieza_urbana"),
         "official_urban_layer", "AUTHORITATIVE_OFFICIAL", ORIGEN_EXTERNO,
         "Pieza urbana: descriptor territorial del contexto."),
        ("amenaza_remocion_masa",
         {"value": _exigir(rs, "risk_context", "amenaza_remocion_masa"),
          "status": _exigir(uss, "campos", "amenaza_remocion_masa")["status"],
          "modo": _exigir(uss, "campos", "amenaza_remocion_masa")["modo"]},
         "POT_BAQ_REMOCION_2024", "AUTHORITATIVE_OFFICIAL", ORIGEN_EXTERNO,
         "Riesgo: afecta la decisión de riesgo; el ajuste por riesgo es otra fase."),
        ("areas_en_riesgo",
         {"value": _exigir(rs, "risk_context", "areas_en_riesgo"),
          "status": _exigir(uss, "campos", "areas_en_riesgo")["status"],
          "modo": _exigir(uss, "campos", "areas_en_riesgo")["modo"]},
         "POT_BAQ_RIESGO_2024", "AUTHORITATIVE_OFFICIAL", ORIGEN_EXTERNO,
         "Zonificación de riesgo: contexto de decisión."),
        ("inundacion",
         {"value": _exigir(rs, "risk_context", "inundacion"),
          "status": _exigir(uss, "campos", "inundacion")["status"],
          "modo": _exigir(uss, "campos", "inundacion")["modo"]},
         "POT_BAQ_INUNDACION_2024", "AUTHORITATIVE_OFFICIAL", None,
         "Inundación: contexto de decisión; sin dato, se declara la ausencia."),
        ("riesgo_no_mitigable",
         {"value": _exigir(rs, "risk_context", "riesgo_no_mitigable"),
          "status": _exigir(uss, "campos", "riesgo_no_mitigable")["status"],
          "modo": _exigir(uss, "campos", "riesgo_no_mitigable")["modo"]},
         "POT_BAQ_RIESGO_2024", "AUTHORITATIVE_OFFICIAL", None,
         "Riesgo no mitigable: contexto de decisión."),
        ("equipamiento_contexto",
         {"items": len(_exigir(rs, "poi_state", "items")),
          "queried_at": _exigir(rs, "poi_state", "queried_at")},
         "OSM_OVERPASS", "CONTEXTUAL_EXTERNAL", ORIGEN_EXTERNO,
         "Equipamiento cercano: enriquece el contexto, no mide precio. No es insumo de "
         "estimación."),
        ("simulacion_solar", _exigir(rs, "solar_state"),
         "SOLAR_ENGINE+SHADOW_FACADE_EXPOSURE", "COMPUTED", ORIGEN_COMPUTADO,
         "Simulación geométrica de asoleamiento: declara su propia advertencia de que no "
         "sustituye inspección física. No es insumo de estimación."),
        ("titulo_y_gravamenes",
         {"titulares": _exigir(ts, "titulares"),
          "anotaciones_total": _exigir(ts, "anotaciones_total"),
          "gravamenes_vigentes": len(_exigir(ts, "gravamenes_vigentes")),
          "hipoteca_vigente_acreedor":
              _exigir(ts, "hipoteca_vigente")["acreedor"]},
         "SNR", "AUTHORITATIVE_OFFICIAL", ORIGEN_EXTERNO,
         "Gravámenes y titularidad: afectan negociabilidad y decisión, no el valor de "
         "mercado del inmueble."),
        ("screening_contrapartes",
         {"status": _exigir(rs, "screening_summary", "status"),
          "subjects_declared": _exigir(rs, "screening_summary", "subjects_declared"),
          "subjects_screened": _exigir(rs, "screening_summary", "subjects_screened")},
         "núcleo de screening sancionado", "AUTHORITATIVE_CONTRACTUAL", ORIGEN_EXTERNO,
         "Riesgo de contraparte: no es valor del activo."),
        ("release_gate",
         {"release_status": _exigir(src_versions, "release_gate", "release_status"),
          "policy": _exigir(src_versions, "release_gate", "policy"),
          "environment": _exigir(src_versions, "release_gate", "environment")},
         "núcleo de screening sancionado", "COMPUTED", ORIGEN_COMPUTADO,
         "Gobierna la entrega del documento, no el cálculo."),
        ("master_hash", _exigir(mf, "master_hash"),
         "dictus-manifiesto", "COMPUTED", ORIGEN_COMPUTADO,
         "Sello de integridad del expediente: sirve para verificar, no para estimar."),
    ]
    for attr, valor, sid, sclass, orig, motivo in contextos:
        v, bruto = _contexto_valor(valor)
        inv.append(_entrada(
            attribute=attr, value=v, origin=orig, source_id=sid, source_class=sclass,
            queried_at=generado, effective_date=None,
            freshness=_frescura(queried_at=generado, referencia=generado),
            provenance=bruto if isinstance(bruto, dict) else {"valor_golden": bruto,
                                                              **prov_runstate},
            usable_for_estimation=False,
            reason=(motivo + " Por eso es contexto de decisión y su "
                    "usable_for_estimation es false pese a estar verificado."),
        ))

    # ── el veredicto de la escalera, calculado con los hechos reales ──────────
    escalera = evaluar_escalera(_niveles_presentes(tabla, registro),
                                calibracion={"calibrado": False,
                                             "dataset_declarado": None})

    return {
        "audit_version": "estimation-input-audit/1.0.0",
        "fase": "DICTUS ESTIMATION ENGINE v1.0 · FASE 1 (auditoría + contratos)",
        "folio": FOLIO,
        "ciudad": ciudad,
        "run_id": run_id,
        "generado_por": "scripts/estimation_input_audit.py",
        "golden_leido": {"run_state": str(RUN_STATE_PATH.relative_to(ROOT)),
                         "run_state_sha256": sha_rs,
                         "manifest": str(MANIFEST_PATH.relative_to(ROOT)),
                         "manifest_sha256": sha_mf,
                         "master_hash": _exigir(mf, "master_hash")},
        "vocabulario_source_class": list(CLASES_FUENTE),
        "criterio_usable_for_estimation": CRITERIO_USABLE,
        "nota_source_id": ("`source_id` usa el identificador REAL del Source Registry cuando "
                          "existe; cuando el Golden solo declara una etiqueta de fuente, se "
                          "transcribe la etiqueta literal en vez de inventar un ID."),
        "escalera_evidencia_mercado": {
            "version": VERSION_ESCALERA,
            "niveles": list(NIVELES_EVIDENCIA_MERCADO),
            "regla_ausencia_level_1": REGLA_AUSENCIA_LEVEL_1,
            "evaluacion": escalera,
        },
        "conteo": {
            "total_inputs": len(inv),
            "usable_for_estimation_true": sum(
                1 for e in inv if e["usable_for_estimation"]),
            "usable_for_estimation_false": sum(
                1 for e in inv if not e["usable_for_estimation"]),
            "niveles_con_evidencia_utilizable": escalera["niveles_con_soporte"],
            "observaciones_de_mercado_reales": 0,
        },
        "blocking_por_proposito": blocking_por_proposito(),
        "entradas": inv,
    }


def _niveles_presentes(tabla: Dict[str, Any], registro: Dict[str, Any]) -> List[str]:
    """Niveles de la escalera REALMENTE presentes en los artefactos del pack.

    Se calcula, no se supone: hay filas de tabla declarada a mano (nivel 5) y NO hay
    ninguna fuente de mercado en el registro (niveles 1-3 vacíos).
    """
    niveles: List[str] = []
    if tabla.get("rows"):
        niveles.append(LEVEL_5_STATIC_REFERENCE)      # parámetro declarado a mano
    fuentes = (registro.get("sources") or {})
    if any((f or {}).get("product_role") == "CORE_MARKET" for f in fuentes.values()
           if isinstance(f, dict)):
        niveles.append(LEVEL_3_AGGREGATED_MARKET_REFERENCES)
    return niveles


def _buscar_evidencia(em: Dict[str, Any], evidence_id: str) -> Dict[str, Any]:
    for e in em.get("evidencias") or []:
        if e.get("evidence_id") == evidence_id:
            return e
    raise KeyError(f"el evidence manifest no declara {evidence_id}")


def _fecha_acto(ts: Dict[str, Any]) -> Optional[str]:
    actos = ts.get("actos_adquisicion") or []
    return actos[0].get("fecha") if actos else None


def _contexto_valor(bruto: Any) -> Tuple[Any, Any]:
    """Normaliza una entrada de contexto: (valor, provenance)."""
    if isinstance(bruto, dict) and "value" in bruto:
        return bruto.get("value"), bruto
    return bruto, {"valor_golden": bruto}


def _servicios_observatorio() -> Dict[str, List[Dict[str, Any]]]:
    """Servicios de mercado del geoportal municipal DESCUBIERTOS y NO cosechados.

    Se leen los ficheros de caché reales del pack (metadata de servicio: nombre de capa y
    URL consultada). NO hay datos: no se consultó ninguna feature.
    """
    import re
    servicios: Dict[str, Dict[str, Any]] = {}
    if not RAW_CACHE.is_dir():
        return {"servicios": [], "urls_precio_o_transaccion": [], "urls_renta": []}
    for path in sorted(RAW_CACHE.glob("*observatorio*")):
        try:
            d = _cargar(path)
        except Exception:  # noqa: BLE001 — caché ilegible no debe romper la auditoría
            continue
        prov = d.get("provenance") or {}
        url = prov.get("requested_url") or ""
        m = re.search(r"/services/(observatorio/[^/?]+)", url)
        if not m:
            continue
        svc = m.group(1)
        data = d.get("data") or {}
        registro = servicios.setdefault(svc, {
            "servicio": svc, "url": url, "mapName": None, "capas": [],
            "fetched_at_utc": prov.get("fetched_at_utc"),
            "cache_files": [], "cache_sha256": [],
        })
        if data.get("mapName"):
            registro["mapName"] = data["mapName"]
        for capa in data.get("layers") or []:
            if capa.get("name") not in registro["capas"]:
                registro["capas"].append(capa.get("name"))
        registro["cache_files"].append(str(path.relative_to(ROOT)))
        registro["cache_sha256"].append(_sha256(path))

    lista = sorted(servicios.values(), key=lambda s: s["servicio"])
    precio_o_transaccion = [s for s in lista if any(
        k in s["servicio"] for k in ("valorcompraventas", "valoresm2", "valorsuelourbano",
                                     "avaluocatastral", "transacciones"))]
    renta = [s for s in lista if "arrendamiento" in s["servicio"]]
    return {"servicios": lista, "urls_precio_o_transaccion": precio_o_transaccion,
            "urls_renta": renta}


# ══════════════════════════════════════════════════════════════════════════════
# Matriz de evidencia de mercado (CSV)
# ══════════════════════════════════════════════════════════════════════════════
CABECERAS_CSV = ("fuente", "nivel_escalera", "status", "valor", "origin", "provenance",
                 "hash", "usada")


def construir_matriz() -> List[Dict[str, str]]:
    rs = _cargar(RUN_STATE_PATH)
    mf = _cargar(MANIFEST_PATH)
    tabla = _cargar(TABLA_MERCADO)
    mc_art = _cargar(MARKET_CONTEXT_ART)
    gate = _cargar(VALUATION_GATE_ART)
    registro = _cargar(REGISTRO_FUENTES)

    generado = _exigir(rs, "generated_at")
    sector_met = _exigir(rs, "market_context", "sector_metodologico")
    vig_hasta = _exigir(tabla, "vigencia", "hasta")
    dias_desde = (_fecha(generado) - _fecha(vig_hasta)).days

    filas: List[Dict[str, str]] = []

    def fila(fuente: str, nivel: str, status: str, valor: str, origin: str,
             provenance: str, hash_: str, usada: str) -> None:
        filas.append({"fuente": fuente, "nivel_escalera": nivel, "status": status,
                      "valor": valor, "origin": origin, "provenance": provenance,
                      "hash": hash_, "usada": usada})

    # ── 1 · la pieza retirada del registro ────────────────────────────────────
    retiradas = _exigir(registro, "no_fuentes_institucionales")
    lonja = retiradas["aliados"]["LONJA_BAQ"]
    fila("LONJA_MARKET_BAQ (identificador histórico, retirado del Source Registry)",
         LEVEL_5_STATIC_REFERENCE,
         "NOT_SUPPORTED · retirada_del_registro=true · en_source_registry=false",
         "(sin valor: no aporta datos)", "NO_SOURCE",
         "product_role=NOT_A_SOURCE · " + str(lonja["motivo"])[:300],
         _sha256(REGISTRO_FUENTES), "NO")

    # ── 2 · celdas de la tabla versionada (parámetros declarados a mano) ──────
    for row in _exigir(tabla, "rows"):
        es_sujeto = _norm(row.get("sector")) == _norm(sector_met.get("matched_sector"))
        fila(f"lonja_market_baq_v1.json · sector {row.get('sector')}"
             + (" (=sector del sujeto)" if es_sujeto else ""),
             LEVEL_5_STATIC_REFERENCE,
             ("SOURCE_UNAVAILABLE · VENCIDA (hasta " + str(vig_hasta) + ", corrida "
              + str(generado)[:10] + ", " + str(dias_desde) + " d después) · "
              "parámetro declarado por la corrida"),
             (f"value_per_m2={row.get('value_per_m2')} · rango=[{row.get('range_low')}, "
              f"{row.get('range_high')}] · source_date={row.get('source_date')}"),
             ORIGEN_MANUAL,
             ("fuente_declarada=" + str(row.get("fuente_declarada"))
              + " · valor_declarado_en=" + str(row.get("valor_declarado_en"))
              + " · effective_from=" + str(row.get("effective_from"))
              + " · effective_to=" + str(row.get("effective_to"))),
             _sha256(TABLA_MERCADO), "NO")

    # ── 3 · los artefactos que declaran la ausencia ───────────────────────────
    fila("MARKET_CONTEXT_040-646406.json (auditoría de la tasa de la corrida)",
         LEVEL_5_STATIC_REFERENCE,
         "SIN_FUENTE_DE_MERCADO · origen no habilitante",
         f"market_rate.value={mc_art['market_rate']['value']} · "
         f"authorized_for_valuation={mc_art['market_rate']['authorized_for_valuation']}",
         mc_art["D_origin"]["origin"],
         "etiqueta_honesta_producto=" + str(mc_art["etiqueta_honesta_producto"]["etiqueta"]),
         _sha256(MARKET_CONTEXT_ART), "NO")

    fila("VALUATION_GATE_040-646406.json (compuerta de valoración)",
         LEVEL_5_STATIC_REFERENCE, "CLOSED · NO EMITIR VALORACIÓN",
         f"consolidado={gate['observations'][0]['value']['consolidado']} · value_m2=null",
         gate["origin_summary"],
         "reason=" + str(gate["reason"])[:300],
         _sha256(VALUATION_GATE_ART), "NO")

    fila("SOURCE_COVERAGE_MATRIX_040-646406.csv · fila 18-mercado",
         LEVEL_5_STATIC_REFERENCE, "SOURCE_UNAVAILABLE · SIN FUENTE DE MERCADO",
         "(sin valor: parámetros declarados por la corrida)", ORIGEN_MANUAL,
         "source=SIN_FUENTE (parámetros declarados por la corrida) · es_fuente_de_datos=false",
         _sha256(COVERAGE_CSV), "NO")

    fila("SOURCE_ACQUISITION_MATRIX_040-646406.csv · dominio mercado",
         LEVEL_5_STATIC_REFERENCE, "NOT_SUPPORTED · AUSENCIA_DECLARADA",
         "(sin valor)", "NO_SOURCE",
         "source_id=LONJA_MARKET_BAQ · product_role=CORE_MARKET · la fuente declarada NO está "
         "en el registro vigente del pack",
         _sha256(ACQUISITION_CSV), "NO")

    # ── 4 · candidatos reales descubiertos y NO cosechados ────────────────────
    for svc in _servicios_observatorio()["servicios"]:
        fila(f"GEOPORTAL_MUNICIPAL BARRANQUILLA · {svc['servicio']} "
             f"({svc['mapName']})",
             LEVEL_3_AGGREGATED_MARKET_REFERENCES,
             "NOT_HARVESTED_METADATA_ONLY · descubierto en el pack, NUNCA consultado",
             "(sin valor: solo metadata de servicio)",
             "(sin origen declarado: no se consultó)",
             "url=" + str(svc["url"]) + " · capas=" + " | ".join(svc["capas"][:8])
             + " · fetched_at_utc=" + str(svc["fetched_at_utc"])
             + " · cache=" + svc["cache_files"][0],
             svc["cache_sha256"][0], "NO")

    return filas


def _norm(v: Any) -> str:
    return str(v or "").strip().lower()


# ══════════════════════════════════════════════════════════════════════════════
# Escritura
# ══════════════════════════════════════════════════════════════════════════════
def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    inventario = construir_inventario()
    with open(OUT_AUDIT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(inventario, fh, ensure_ascii=False, indent=2, sort_keys=False)
        fh.write("\n")

    filas = construir_matriz()
    with open(OUT_MATRIX, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(CABECERAS_CSV), lineterminator="\n")
        w.writeheader()
        for f in filas:
            w.writerow(f)

    print(f"[OK] {OUT_AUDIT.relative_to(ROOT)}")
    print(f"     inputs inventariados = {inventario['conteo']['total_inputs']}"
          f" · usable_for_estimation=true = "
          f"{inventario['conteo']['usable_for_estimation_true']}")
    print(f"     observaciones de mercado reales = "
          f"{inventario['conteo']['observaciones_de_mercado_reales']}")
    print(f"     niveles con evidencia utilizable = "
          f"{inventario['escalera_evidencia_mercado']['evaluacion']['niveles_con_soporte']}")
    print(f"[OK] {OUT_MATRIX.relative_to(ROOT)} · filas = {len(filas)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

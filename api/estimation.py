# -*- coding: utf-8 -*-
"""ARHIAX RE — DICTUS ESTIMATION ENGINE v1.0 · FASE 2 (NÚCLEO).

Se construye ENCIMA de lo existente, sin big-bang y sin romper nada. Una sola
verdad por vocabulario:

  · `atribucion_mercado` es la ÚNICA definición del vocabulario de `origin` y de
    `ORIGENES_HABILITANTES`. Este módulo NO lo reimplementa: lo EXTIENDE con
    clases distinguidas (§2/§3) y delega la degradación por procedencia en él.
  · `dictus_decision` es la ÚNICA definición de la gramática de decisión y del
    vocabulario CERRADO `gate_state` (`OPEN`/`CLOSED`, §30).
  · `market_context` sigue siendo la autoridad del CONTEXTO de mercado.

PRINCIPIO RECTOR
----------------
«NO EMITIR VALORACIÓN» / `NOT_ESTIMABLE` es el ÚLTIMO estado, no el
comportamiento por defecto. DICTUS debe INTENTAR estimar: si hay información
suficiente para una estimación razonable —aunque NO alcance el estándar de
evidencia de mercado VERIFICADA— el motor emite una ESTIMACIÓN INDICATIVA con
sus limitaciones declaradas, en lugar de cerrar.

TRES CONCEPTOS QUE NO SE SUSTITUYEN (§1)
----------------------------------------
  1. `VERIFIED_MARKET_EVIDENCE_GATE`  → `OPEN` / `CLOSED`.
     Pregunta: ¿la evidencia de mercado tiene origen Y procedencia suficientes
     para tratar la cifra como sustentada por fuentes verificadas?
  2. `ESTIMATION_GATE`                → `OPEN` / `OPEN_WITH_LIMITATIONS` / `CLOSED`.
     Pregunta: ¿hay información suficiente para una ESTIMACIÓN RAZONABLE, aun
     cuando la evidencia no alcance el estándar anterior?
  3. `EVIDENCE_QUALITY_GATE`          → `HIGH` / `MEDIUM` / `INDICATIVE` / `INSUFFICIENT`.
     Pregunta: ¿qué CALIDAD tiene la evidencia disponible? (sin score 0-100).

REGLA §30: `VERIFIED_MARKET_EVIDENCE_GATE = CLOSED` PUEDE coexistir con
`ESTIMATION_GATE = OPEN_WITH_LIMITATIONS`. El primero NUNCA es consecuencia
automática del segundo, y `NO EMITIR VALORACIÓN` no se deriva del primero.

RANGO PRIMERO (§12)
-------------------
La salida primaria es el RANGO (`range_low`–`range_high`). La cifra central es
SECUNDARIA y no puede tener más precisión que la evidencia: el redondeo se
deriva del ancho del rango (nunca menos de $1.000.000 de paso), de modo que
ninguna corrida pueda imprimir una cifra como `399.500.000` si su evidencia no
la sostiene.

HISTÓRICO (§23): el valor de una corrida anterior es SOLO FORENSE. Viaja en
`historical_estimate_reference` y JAMÁS como input de la nueva estimación.

NO ES `Lonja`: en este módulo no existe ninguna fuente con ese nombre, ni
sustituta inventada. Donde no hay fuente externa se declara
`sin fuente externa automática verificada`.

NO toca PDF: esta fase entrega SOLO contrato de datos.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
from datetime import date, datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# ── dependencias internas: una sola verdad por vocabulario ────────────────────
try:  # `api/` está en sys.path cuando el producto importa estos módulos
    import atribucion_mercado as am
except Exception:  # noqa: BLE001 — carga determinista por ruta (import por paquete)
    import importlib.util as _ilu
    from pathlib import Path as _Path
    _spec = _ilu.spec_from_file_location(
        "_arhiax_atribucion_mercado",
        _Path(__file__).resolve().parent / "atribucion_mercado.py")
    am = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(am)

import importlib.util as _ilu2
from pathlib import Path as _Path2


def _cargar_hermano(nombre: str):
    """Carga determinista de un módulo hermano de `api/` (sin depender del cwd)."""
    try:
        return __import__(nombre)
    except Exception:  # noqa: BLE001
        try:
            _spec = _ilu2.spec_from_file_location(
                f"_arhiax_{nombre}", _Path2(__file__).resolve().parent / f"{nombre}.py")
            modulo = _ilu2.module_from_spec(_spec)
            _spec.loader.exec_module(modulo)
            return modulo
        except Exception:  # noqa: BLE001
            return None


dd = _cargar_hermano("dictus_decision")

# ══════════════════════════════════════════════════════════════════════════════
# VERSIONES (condiciones mínimas, fórmulas y contratos son EXPLÍCITOS y VERSIONADOS)
# ══════════════════════════════════════════════════════════════════════════════
ESTIMATION_ENGINE_VERSION = "dictus-estimation-engine/1.0.0"
CONDITIONS_VERSION = "dictus-estimation-conditions/1.0.0"
ORIGIN_COMPOSITION_VERSION = "dictus-origin-composition/1.0.0"
RANGE_WIDTH_VERSION = "dictus-range-width/1.0.0"
METHODS_VERSION = "dictus-estimation-methods/1.0.0"
EVIDENCE_QUALITY_VERSION = "dictus-evidence-quality/1.0.0"
CALIBRATED_PRIOR_CONTRACT_VERSION = "dictus-calibrated-model-prior/1.0.0"
METHODOLOGY_VERSION = "dictus-metodologia-base/1.0.0"

# ══════════════════════════════════════════════════════════════════════════════
# §1 · LAS TRES COMPUERTAS
# ══════════════════════════════════════════════════════════════════════════════
VERIFIED_MARKET_EVIDENCE_GATE = "VERIFIED_MARKET_EVIDENCE_GATE"
ESTIMATION_GATE = "ESTIMATION_GATE"
EVIDENCE_QUALITY_GATE = "EVIDENCE_QUALITY_GATE"

# §30 · vocabulario CERRADO de compuerta, idéntico al de `dictus_decision`.
VERIFIED_OPEN = "OPEN"
VERIFIED_CLOSED = "CLOSED"
ESTADOS_VERIFIED_MARKET_EVIDENCE = (VERIFIED_CLOSED, VERIFIED_OPEN)

# Estados de la compuerta de ESTIMACIÓN (tres estados, todos CERRADOS como vocabulario).
ESTIMATION_OPEN = "OPEN"
ESTIMATION_OPEN_WITH_LIMITATIONS = "OPEN_WITH_LIMITATIONS"
ESTIMATION_CLOSED = "CLOSED"
ESTADOS_ESTIMATION_GATE = (ESTIMATION_OPEN, ESTIMATION_OPEN_WITH_LIMITATIONS,
                           ESTIMATION_CLOSED)

# Niveles de calidad de evidencia (SIN score público 0-100, §14).
QUALITY_HIGH = "HIGH"
QUALITY_MEDIUM = "MEDIUM"
QUALITY_INDICATIVE = "INDICATIVE"
QUALITY_INSUFFICIENT = "INSUFFICIENT"
ESTADOS_EVIDENCE_QUALITY = (QUALITY_HIGH, QUALITY_MEDIUM, QUALITY_INDICATIVE,
                            QUALITY_INSUFFICIENT)
ORDEN_CALIDAD = {QUALITY_INSUFFICIENT: 0, QUALITY_INDICATIVE: 1,
                 QUALITY_MEDIUM: 2, QUALITY_HIGH: 3}
_ORDEN_A_CALIDAD = {v: k for k, v in ORDEN_CALIDAD.items()}

# ══════════════════════════════════════════════════════════════════════════════
# §2/§3 · COMPOSICIÓN DE ORIGIN — vocabulario EXTENDIDO
# ══════════════════════════════════════════════════════════════════════════════
# Clases NUEVAS (se suman a las cinco de `atribucion_mercado`, que no se tocan).
ORIGEN_COMPUTADO_CON_PRIOR = "COMPUTED_WITH_MODEL_PRIOR"
ORIGEN_COMPUTADO_CON_ESTATICA = "COMPUTED_WITH_STATIC_REFERENCE"
ORIGEN_NO_PRODUCTIVO = "NOT_PRODUCTIVE"
ORIGEN_PRIOR_LEGACY = "LEGACY_MODEL_PRIOR"
ORIGEN_PRIOR_CALIBRADO = "CALIBRATED_MODEL_PRIOR"
# §5.3 · DERIVACIÓN DETERMINISTA DE **UNA** FUENTE EXTERNA (nivel 3).
# `COMPUTED_FROM_SOURCES` exige **múltiples** fuentes materiales: una transformación
# matemática de UNA sola fuente NO es una composición de fuentes y NO puede
# etiquetarse así. La evidencia base queda `EXTERNAL_SOURCE` y la transformación se
# declara APARTE (`derivation`); si el derivado necesita su propia clase, es ÉSTA, y
# `COMPUTED_FROM_SOURCES` no se reutiliza nunca para una fuente única.
ORIGEN_DERIVADO_EXTERNO = "DERIVED_FROM_EXTERNAL_SOURCE"

#: Tipos de derivación reconocidos (vocabulario cerrado y explícito).
DERIVACION_PUNTO_MEDIO_RANGO = "MIDPOINT_OF_SOURCE_RANGE"
DERIVACION_FORMULA_PUNTO_MEDIO = "(min + max) / 2"

# `MODEL_PRIOR` (el valor por defecto del código) ES el prior legacy: un solo
# concepto con dos nombres. Se aceptan ambos y se declara la equivalencia.
# La tabla concreta del hardcode por estrato NO se duplica aquí: sigue siendo la única
# declarada en `api/dictamen_data.py` (`FALLBACK_ESTRATO_M2`), que se conserva por
# compatibilidad. Este motor la clasifica como `LEGACY_MODEL_PRIOR` y NUNCA la usa.
ORIGEN_PRIOR_ALIAS = frozenset({am.ORIGEN_PRIOR, ORIGEN_PRIOR_LEGACY})

ORIGENES_EXTENDIDOS = tuple(am.ORIGENES) + (
    ORIGEN_COMPUTADO_CON_PRIOR, ORIGEN_COMPUTADO_CON_ESTATICA, ORIGEN_NO_PRODUCTIVO,
    ORIGEN_PRIOR_LEGACY, ORIGEN_PRIOR_CALIBRADO, ORIGEN_DERIVADO_EXTERNO,
)

# Peso y capacidad de sostener una estimación, POR CLASE. Tabla única y explícita:
# no hay ninguna otra regla escondida en el código.
PESO_ALTO = "ALTO"
PESO_MEDIO = "MEDIO"
PESO_BAJO = "BAJO"
PESO_NULO = "NINGUNO"

CLASES_ORIGEN: Dict[str, Dict[str, Any]] = {
    am.ORIGEN_EXTERNO: {
        "peso": PESO_ALTO, "sostiene_estimacion": True, "abre_verified_gate": True,
        "techo_calidad": QUALITY_HIGH,
        "etiqueta": "fuente externa citada (verificable)",
    },
    am.ORIGEN_COMPUTADO: {
        "peso": PESO_ALTO, "sostiene_estimacion": True, "abre_verified_gate": True,
        "techo_calidad": QUALITY_HIGH,
        "etiqueta": "calculado a partir de fuentes citadas",
    },
    ORIGEN_COMPUTADO_CON_PRIOR: {
        "peso": PESO_MEDIO, "sostiene_estimacion": True, "abre_verified_gate": False,
        "techo_calidad": QUALITY_MEDIUM,
        "etiqueta": ("calculado a partir de fuentes citadas y de un modelo calibrado: "
                     "no es producto de fuentes verificadas"),
    },
    ORIGEN_COMPUTADO_CON_ESTATICA: {
        "peso": PESO_BAJO, "sostiene_estimacion": True, "abre_verified_gate": False,
        "techo_calidad": QUALITY_MEDIUM,
        "etiqueta": ("calculado a partir de fuentes citadas y de una referencia estática "
                     "de bajo peso"),
    },
    ORIGEN_PRIOR_CALIBRADO: {
        "peso": PESO_MEDIO, "sostiene_estimacion": True, "abre_verified_gate": False,
        "techo_calidad": QUALITY_INDICATIVE,
        "etiqueta": "modelo calibrado con muestra declarada (base indicativa)",
    },
    ORIGEN_DERIVADO_EXTERNO: {
        # §5.3 · Una derivación determinista de UNA sola fuente externa NO es una fuente
        # adicional: aporta la transformación, no la evidencia. Por eso NO sostiene por
        # sí sola una cifra ni abre la compuerta de evidencia verificada.
        "peso": PESO_BAJO, "sostiene_estimacion": False, "abre_verified_gate": False,
        "techo_calidad": QUALITY_INDICATIVE,
        "etiqueta": ("derivación determinista de UNA fuente externa citada (punto medio "
                     "de su rango publicado): NO es una fuente adicional"),
    },
    am.ORIGEN_ESTATICO: {
        "peso": PESO_BAJO, "sostiene_estimacion": False, "abre_verified_gate": False,
        "techo_calidad": QUALITY_MEDIUM,
        "etiqueta": ("referencia estática: aporta contexto de bajo peso y NO sostiene "
                     "por sí sola ninguna cifra"),
    },
    am.ORIGEN_MANUAL: {
        "peso": PESO_NULO, "sostiene_estimacion": False, "abre_verified_gate": False,
        "techo_calidad": QUALITY_INSUFFICIENT,
        "etiqueta": ("valor declarado a mano por la corrida: NO sostiene una estimación "
                     "productiva"),
    },
    ORIGEN_PRIOR_LEGACY: {
        "peso": PESO_NULO, "sostiene_estimacion": False, "abre_verified_gate": False,
        "techo_calidad": QUALITY_INSUFFICIENT,
        "etiqueta": ("prior legacy del modelo (hardcode por estrato): se conserva por "
                     "compatibilidad y NO produce ninguna cifra productiva"),
    },
    ORIGEN_NO_PRODUCTIVO: {
        "peso": PESO_NULO, "sostiene_estimacion": False, "abre_verified_gate": False,
        "techo_calidad": QUALITY_INSUFFICIENT,
        "etiqueta": "combinación no productiva: no sostiene ninguna cifra",
    },
}

# Clases que ENSUCIAN la composición si participan del cálculo (§3, §11).
# Un valor escrito a mano o un prior legacy NO se lava: si entra al cómputo, la
# composición entera es NO PRODUCTIVA. Nunca `COMPUTED_FROM_SOURCES`.
CLASES_NO_LAVABLES = frozenset({am.ORIGEN_MANUAL, ORIGEN_PRIOR_LEGACY, am.ORIGEN_PRIOR})

ETIQUETA_COMPOSICION = {
    am.ORIGEN_EXTERNO: "evidencia de una fuente externa citada",
    am.ORIGEN_COMPUTADO: "cálculo sobre fuentes externas citadas",
    ORIGEN_COMPUTADO_CON_PRIOR: "cálculo sobre fuentes externas + modelo calibrado",
    ORIGEN_COMPUTADO_CON_ESTATICA: "cálculo sobre fuentes externas + referencia estática",
    ORIGEN_PRIOR_CALIBRADO: "modelo calibrado (base indicativa)",
    ORIGEN_DERIVADO_EXTERNO: ("derivación determinista de una fuente externa citada "
                              "(no es una fuente adicional)"),
    am.ORIGEN_ESTATICO: "referencia estática (contexto de bajo peso)",
    am.ORIGEN_MANUAL: "parámetro declarado a mano por la corrida",
    ORIGEN_PRIOR_LEGACY: "prior legacy del modelo (hardcode por estrato)",
    ORIGEN_NO_PRODUCTIVO: "combinación no productiva",
}

# Reglas de composición (§3). Se aplican EN ORDEN y la primera que casa manda.
# ORDEN DELIBERADO: las clases que DEBILITAN la afirmación (modelo calibrado,
# referencia estática) tienen PRIORIDAD sobre la etiqueta pura de fuentes. Así la
# composición nunca declara más de lo que entró al cálculo.
REGLAS_COMPOSICION = (
    ("R0_SIN_INSUMOS",
     "no se declaró ningún insumo económico: la composición no es productiva"),
    ("R1_NO_LAVADO",
     "un insumo no habilitante (MANUAL_CONFIG / prior legacy) participa del cálculo: "
     "la composición NO se etiqueta como derivada de fuentes"),
    ("R2_EXTERNA_MAS_PRIOR_CALIBRADO",
     "una fuente externa + un modelo calibrado: COMPUTED_WITH_MODEL_PRIOR"),
    ("R3_SOLO_PRIOR_CALIBRADO",
     "modelo calibrado sin fuente externa (con referencia estática o no): "
     "COMPUTED_WITH_MODEL_PRIOR, con techo INDICATIVE"),
    ("R4_EXTERNA_MAS_ESTATICA",
     "una fuente externa + una referencia estática: COMPUTED_WITH_STATIC_REFERENCE"),
    ("R5_FUENTES_MULTIPLES",
     "≥2 fuentes externas citadas (o externas + calculado sobre fuentes): "
     "COMPUTED_FROM_SOURCES"),
    ("R6_CLASE_UNICA",
     "un solo insumo económico declarado: la composición es su propia clase"),
)

# ══════════════════════════════════════════════════════════════════════════════
# §31 · VOCABULARIO ECONÓMICO (lo que el lector lee)
# ══════════════════════════════════════════════════════════════════════════════
STATUS_ESTIMATED = "ESTIMATED"
STATUS_ESTIMATED_WITH_LIMITATIONS = "ESTIMATED_WITH_LIMITATIONS"
STATUS_INDICATIVE_ESTIMATE = "INDICATIVE_ESTIMATE"
STATUS_NOT_ESTIMABLE = "NOT_ESTIMABLE"
ESTADOS_ESTIMACION = (STATUS_ESTIMATED, STATUS_ESTIMATED_WITH_LIMITATIONS,
                      STATUS_INDICATIVE_ESTIMATE, STATUS_NOT_ESTIMABLE)

VOCABULARIO_ECONOMICO = {
    STATUS_ESTIMATED: "ESTIMACIÓN DISPONIBLE",
    STATUS_ESTIMATED_WITH_LIMITATIONS: "ESTIMACIÓN DISPONIBLE CON LIMITACIONES",
    STATUS_INDICATIVE_ESTIMATE: "ESTIMACIÓN INDICATIVA",
    STATUS_NOT_ESTIMABLE: "NO FUE POSIBLE ESTIMAR",
}

# Una estimación NUNCA es «INFORMACIÓN VERIFICADA», y menos aún una estimación
# indicativa. Estas etiquetas quedan PROHIBIDAS para cualquier estado estimativo.
ETIQUETAS_VERIFICADAS_PROHIBIDAS = frozenset({
    "INFORMACIÓN VERIFICADA", "INFORMACION VERIFICADA", "VALOR VERIFICADO",
    "VALOR VERIFICADO EN FUENTE", "INFORMACIÓN VERIFICADA DE MERCADO",
})
NATURALEZA_ESTIMACION = ("ESTIMACIÓN (análisis técnico automatizado), NO VALOR "
                         "VERIFICADO NI AVALÚO")

# §34 · metodología base: NO se apoya en «norma + concepto técnico + validación
# profesional»; la revisión profesional es un producto SEPARADO (DICTUS + REVIEW).
METODOLOGIA_BASE = ("fuentes disponibles + análisis técnico automatizado + "
                    "metodología versionada")
VOCABULARIO_METODOLOGICO_PROHIBIDO = (
    "norma + concepto técnico + validación profesional",
    "norma, concepto técnico y validación profesional",
    "norma + concepto tecnico + validacion profesional",
)
REVISION_PROFESIONAL_SEPARADA = ("DICTUS + REVIEW (producto separado): la revisión "
                                 "profesional NO forma parte de la metodología base")

# ══════════════════════════════════════════════════════════════════════════════
# §9/§10 · CONDICIONES MÍNIMAS DE LA COMPUERTA DE ESTIMACIÓN (explícitas, versionadas)
# ══════════════════════════════════════════════════════════════════════════════
CONDICIONES_ESTIMACION = (
    "IDENTIDAD_SUFICIENTEMENTE_RESUELTA",
    "UBICACION_UTILIZABLE",
    "AREA_UTILIZABLE",
    "TIPOLOGIA_MINIMA",
    "SOPORTE_ECONOMICO_VALIDO",
)
# MANUAL_CONFIG y el prior legacy NO cuentan como soporte económico válido.
SOPORTES_ECONOMICOS_VALIDOS = tuple(
    clase for clase, meta in CLASES_ORIGEN.items()
    if meta["sostiene_estimacion"] and clase not in (ORIGEN_NO_PRODUCTIVO,))

MIN_COMPARABLES_M1 = 2              # mínimo para una comparación de mercado
MIN_COMPARABLES_CALIDAD_ALTA = 8    # nº de comparables para aspirar a HIGH
MIN_COMPARABLES_CALIDAD_MEDIA = 5
UMBRAL_OUTLIER_RELATIVO = 0.35      # desviación relativa vs mediana
MAX_SEMI_ANCHO = 0.60               # techo absoluto de ±60% (nunca un rango absurdo)

# ══════════════════════════════════════════════════════════════════════════════
# §15 · ANCHO DE RANGO ↔ INCERTIDUMBRE · FÓRMULA VERSIONADA
# ══════════════════════════════════════════════════════════════════════════════
# semi_ancho = BASE
#            + 1.2 · cv                            (dispersión relativa, cap 0.25)
#            + AJUSTE_N[n]                         (nº de comparables usados)
#            + 0.02 · trimestres_antiguedad        (cap 0.10)
#            + 0.06 · (1 − matching_quality)
#            + AJUSTE_ORIGEN[composición]
#            + 1.0 · error_modelo                  (cap 0.15)
# semi_ancho = min(semi_ancho, 0.60)
# Después, la BANDA de la calidad manda: el ancho nunca es menor que el mínimo de
# su banda, y si supera el máximo de su banda la CALIDAD se degrada (no se
# estrecha el rango a la fuerza). Con `razon_explicita` la banda no se fuerza y la
# excepción queda documentada en el resultado.
ANCHO_BASE = 0.06
ANCHO_COEF_DISPERSION = 1.2
ANCHO_COEF_ANTIGUEDAD = 0.02
ANCHO_MAX_ANTIGUEDAD = 0.10
ANCHO_COEF_MATCHING = 0.06
ANCHO_COEF_ERROR_MODELO = 1.0
ANCHO_MAX_ERROR_MODELO = 0.15
ANCHO_MAX_DISPERSION = 0.25

AJUSTE_N_COMPARABLES = ((8, 0.00), (5, 0.02), (3, 0.05), (2, 0.08), (1, 0.12), (0, 0.15))
AJUSTE_POR_ORIGEN = {
    am.ORIGEN_EXTERNO: 0.00,
    am.ORIGEN_COMPUTADO: 0.00,
    ORIGEN_COMPUTADO_CON_PRIOR: 0.05,
    ORIGEN_COMPUTADO_CON_ESTATICA: 0.06,
    ORIGEN_PRIOR_CALIBRADO: 0.07,
    am.ORIGEN_ESTATICO: 0.10,
    am.ORIGEN_MANUAL: 0.15,
    ORIGEN_PRIOR_LEGACY: 0.15,
    ORIGEN_NO_PRODUCTIVO: 0.20,
}
# Banda obligatoria por nivel de calidad: [mínimo, máximo] del SEMI-ancho.
BANDAS_POR_CALIDAD = {
    QUALITY_HIGH: (0.06, 0.15),
    QUALITY_MEDIUM: (0.10, 0.30),
    QUALITY_INDICATIVE: (0.15, MAX_SEMI_ANCHO),
}
# §12 · precisión de la cifra central DERIVADA del ancho: la cifra no puede tener
# más precisión que la evidencia. El paso nunca es menor a $1.000.000.
PRECISION_POR_ANCHO = ((0.30, 10_000_000), (0.15, 5_000_000), (0.00, 1_000_000))

# ══════════════════════════════════════════════════════════════════════════════
# §17-§21 · MÉTODOS
# ══════════════════════════════════════════════════════════════════════════════
METODO_M1 = "M1_MARKET_COMPARISON"
METODO_M2 = "M2_REPLACEMENT_COST"
METODO_M3 = "M3_INCOME_CAPITALIZATION"
METODO_M4 = "M4_CALIBRATED_MODEL_PRIOR"
METODO_M5 = "M5_AGGREGATED_MARKET_REFERENCE"
METODOS = (METODO_M1, METODO_M2, METODO_M3, METODO_M4, METODO_M5)
NOMBRE_METODO = {
    METODO_M1: "MARKET COMPARISON",
    METODO_M2: "REPLACEMENT COST",
    METODO_M3: "INCOME CAPITALIZATION",
    METODO_M4: "MODELO CALIBRADO (base indicativa, §16)",
    METODO_M5: "REFERENCIA AGREGADA OFICIAL POR LOCALIDAD Y BANDA DE ÁREA",
}
# §22 · nivel de la escalera que M5 puede consumir. LEVEL 1/2 (observaciones de la
# unidad) NO entran por aquí: son M1.
NIVEL_REFERENCIA_AGREGADA = "LEVEL_3_AGGREGATED_MARKET_REFERENCES"
# §22 · procedencia HTTP mínima que se exige a una referencia agregada para que el motor
# la USE. Sin estos campos la referencia no se usa: `INSUFFICIENT_DATA`, nunca «dato
# aproximado».
CAMPOS_PROCEDENCIA_AGREGADA = ("source_id", "url", "consultado_en", "http", "bytes",
                               "sha256", "metodologia_declarada")
_BANDA_RE = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*-\s*(\d+(?:[.,]\d+)?)\s*$")
_BANDA_MAYOR_RE = re.compile(r"^\s*>\s*(\d+(?:[.,]\d+)?)\s*$")


def parsear_banda_m2(texto: Any) -> Optional[Tuple[float, float]]:
    """«36-60» → (36.0, 60.0); «>291» → (291.0, inf). `None` si no es una banda legible."""
    t = str(texto or "").strip().replace("m²", "").replace("m2", "").strip()
    m = _BANDA_RE.match(t)
    if m:
        return (float(m.group(1).replace(",", ".")), float(m.group(2).replace(",", ".")))
    m = _BANDA_MAYOR_RE.match(t)
    if m:
        return (float(m.group(1).replace(",", ".")), float("inf"))
    return None


def banda_contiene(banda: Any, area: Any) -> Optional[bool]:
    """¿la banda de área de la fuente CONTIENE el área del sujeto? `None` si no se sabe."""
    rango = parsear_banda_m2(banda)
    a = _num(area)
    if rango is None or a is None:
        return None
    return rango[0] <= a <= rango[1]

STATUS_METHOD_AVAILABLE = "AVAILABLE"
STATUS_METHOD_PARTIAL = "PARTIAL"
STATUS_METHOD_NOT_APPLICABLE = "NOT_APPLICABLE"
STATUS_METHOD_INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
ESTADOS_METODO = (STATUS_METHOD_AVAILABLE, STATUS_METHOD_PARTIAL,
                  STATUS_METHOD_NOT_APPLICABLE, STATUS_METHOD_INSUFFICIENT_DATA)

CONFIANZA_ALTA = "ALTA"
CONFIANZA_MEDIA = "MEDIA"
CONFIANZA_BAJA = "BAJA"
CONFIANZA_NULA = "NINGUNA"

# §16 · contrato del MODELO CALIBRADO (distinto del legacy).
CONTRATO_MODELO_CALIBRADO = (
    "city", "sector", "neighborhood", "property_type", "regime", "area_band", "estrato",
    "central_value_m2", "low_value_m2", "high_value_m2", "effective_from", "effective_to",
    "reference_period", "sample_size", "calibration_error", "model_version", "provenance",
    "hash",
)
MIN_MUESTRA_CALIBRACION = 20
MAX_ERROR_CALIBRACION = 0.25

# §23 · referencia histórica: SOLO FORENSE.
CAMPOS_REFERENCIA_HISTORICA = (
    "old_run_id", "old_value", "old_range", "old_method", "old_inputs", "old_origin",
    "old_master_hash",
)

# ══════════════════════════════════════════════════════════════════════════════
# §11/§13 · CONTRATOS DE SALIDA
# ══════════════════════════════════════════════════════════════════════════════
CAMPOS_ESTIMATION_RESULT = (
    "status", "central_estimate", "range_low", "range_high",
    "value_m2_central", "value_m2_low", "value_m2_high", "currency",
    "estimation_gate", "evidence_quality", "methods_used", "methods_rejected",
    "inputs", "origins", "sources", "assumptions", "limitations",
    "confidence_label", "confidence_reasons", "generated_at", "model_version",
    "evidence_refs",
)
CAMPOS_ESTIMATION_GATE = (
    "gate", "gate_state", "state", "reasons", "blocking_conditions",
    "supporting_conditions", "inputs_available", "inputs_missing",
    "methods_available", "methods_rejected", "conditions_version",
)
CAMPOS_EVIDENCE_QUALITY = (
    "gate", "level", "reasons", "identity_quality", "location_quality",
    "market_evidence_quality", "market_freshness", "comparable_quality",
    "comparable_count", "typology_quality", "area_quality", "model_quality", "dispersion",
)
# §13 · las DIEZ dimensiones de la calidad de evidencia. Ninguna es un score: cada una
# se declara con un nivel CUALITATIVO de este vocabulario cerrado.
DIM_HIGH = "HIGH"
DIM_MEDIUM = "MEDIUM"
DIM_LOW = "LOW"
DIM_ABSENT = "ABSENT"
ESTADOS_DIMENSION = (DIM_HIGH, DIM_MEDIUM, DIM_LOW, DIM_ABSENT)
CAMPOS_DIMENSION_CALIDAD = (
    "identity_quality", "location_quality", "market_evidence_quality", "market_freshness",
    "comparable_quality", "comparable_count", "typology_quality", "area_quality",
    "model_quality", "dispersion",
)
# La mejoría de un nivel cualitativo de DIMENSIÓN a un techo de CALIDAD global.
CAP_DIMENSION = {DIM_HIGH: QUALITY_HIGH, DIM_MEDIUM: QUALITY_MEDIUM,
                 DIM_LOW: QUALITY_INDICATIVE, DIM_ABSENT: QUALITY_INSUFFICIENT}


# ══════════════════════════════════════════════════════════════════════════════
# utilidades internas
# ══════════════════════════════════════════════════════════════════════════════
def _v(x, hueco=None):
    """Valor presente o `hueco` (nunca un 0 silencioso)."""
    return hueco if x in (None, "", [], {}) else x


def _num(x) -> Optional[float]:
    try:
        if x is None or isinstance(x, bool):
            return None
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if f == f and abs(f) != float("inf") else None


def _norm_txt(x) -> Optional[str]:
    return str(x).strip().upper() if x not in (None, "") else None


def _min_calidad(*niveles: str) -> str:
    presentes = [n for n in niveles if n in ORDEN_CALIDAD]
    if not presentes:
        return QUALITY_INSUFFICIENT
    return min(presentes, key=lambda n: ORDEN_CALIDAD[n])


def _degradar(nivel: str) -> str:
    return _ORDEN_A_CALIDAD.get(max(ORDEN_CALIDAD.get(nivel, 0) - 1, 0), QUALITY_INSUFFICIENT)


def _sha256(obj: Any) -> str:
    canon = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                       default=str)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _evidencia(evidence_id: str, source: str, *, tipo: str = "MARKET_EVIDENCE",
               when: Optional[str] = None, sha256: Optional[str] = None,
               detalle: Optional[str] = None) -> Dict[str, Any]:
    """`EvidenceReference` en el MISMO contrato que `dictus_decision.evidencia`."""
    if dd is not None:
        return dd.evidencia(evidence_id, source, tipo=tipo, when=when, sha256=sha256,
                            detalle=detalle)
    return {"evidence_id": evidence_id, "type": tipo, "source": source,
            "timestamp": when, "sha256": sha256, "detail": detalle}


def _fecha(x) -> Optional[date]:
    """Fecha ISO (`YYYY-MM-DD`) o `None`. NUNCA inventa una fecha."""
    if isinstance(x, datetime):
        return x.date()
    if isinstance(x, date):
        return x
    if not x:
        return None
    texto = str(x).strip()[:10]
    try:
        return datetime.strptime(texto, "%Y-%m-%d").date()
    except ValueError:
        return None


def _ahora() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _meses_entre(desde: date, hasta: date) -> int:
    return max((hasta.year - desde.year) * 12 + (hasta.month - desde.month), 0)


# ══════════════════════════════════════════════════════════════════════════════
# §2/§3 · CLASIFICACIÓN Y COMPOSICIÓN DE ORIGIN
# ══════════════════════════════════════════════════════════════════════════════
def _entrada_clasificada(d: Any) -> Optional[Dict[str, Any]]:
    """¿La entrada ya viene CLASIFICADA por `clasificar_origen_extendido`?

    Se acepta el resultado de la propia autoridad de clasificación (`clase` +
    `procedencia_validada`) para no obligar a repetir la procedencia en cada paso.
    NO es una puerta trasera: el motor (`estimar`) NUNCA la usa; siempre clasifica
    desde las declaraciones crudas.
    """
    if not isinstance(d, dict) or d.get("procedencia_validada") is not True:
        return None
    clase = d.get("clase")
    if clase not in CLASES_ORIGEN:
        return None
    meta = CLASES_ORIGEN[clase]
    return {"clase": clase, "clase_declarada": d.get("clase_declarada"),
            "peso": meta["peso"], "sostiene_estimacion": bool(meta["sostiene_estimacion"]),
            "abre_verified_gate": bool(meta["abre_verified_gate"]),
            "techo_calidad": meta["techo_calidad"], "etiqueta": meta["etiqueta"],
            "blockers": list(d.get("blockers") or []),
            "origin_gate": bool(d.get("origin_gate")),
            "provenance": dict(d.get("provenance") or {})}


def clasificar_origen_extendido(declaracion: Optional[Any], *,
                                por_defecto: str = am.ORIGEN_MANUAL) -> Dict[str, Any]:
    """Clase EXTENDIDA de UNA declaración de insumo económica.

    Acepta el vocabulario de `atribucion_mercado` (delegando en él la degradación
    por procedencia incompleta) y añade las clases distinguidas de §2/§3.

    Un insumo SIN `origen_tipo` declarado se clasifica `por_defecto`
    (`MANUAL_CONFIG`): la ausencia de declaración JAMÁS se interpreta como fuente.
    Un `CALIBRATED_MODEL_PRIOR` cuyo contrato (§16) esté incompleto se DEGRADA a
    `LEGACY_MODEL_PRIOR`: no se honra una calibración que no se puede auditar.

    Devuelve `{"clase", "clase_declarada", "peso", "sostiene_estimacion",
    "abre_verified_gate", "techo_calidad", "etiqueta", "blockers", "origin_gate",
    "provenance"}`.
    """
    if declaracion is None:
        return {"clase": None, "clase_declarada": None, "peso": PESO_NULO,
                "sostiene_estimacion": False, "abre_verified_gate": False,
                "techo_calidad": QUALITY_INSUFFICIENT, "etiqueta": None, "blockers": [],
                "origin_gate": False, "provenance": {}}
    if isinstance(declaracion, str):
        declaracion = {"origen_tipo": declaracion}
    d = dict(declaracion)
    prov = d.get("provenance") or d.get("procedencia") or {}
    if isinstance(prov, dict):
        # La procedencia puede venir ANIDADA (`provenance`) o PLANA. Se aceptan las dos
        # formas y se copian los campos que falten: exigir una sola forma obligaría a
        # cada llamador a reescribir su procedencia, y eso es donde se pierde la traza.
        for campo in am.PROCEDENCIA_EXTERNA:
            d.setdefault(campo, prov.get(campo))

    declarado = _norm_txt(d.get("origen_tipo") or d.get("origin"))
    blockers: List[str] = []

    # Las dos clases que `atribucion_mercado` gobierna: se delega (una sola verdad).
    if declarado in (am.ORIGEN_EXTERNO, am.ORIGEN_COMPUTADO):
        r = am.clasificar_origen(d, por_defecto=por_defecto)
        clase = r["origin"]
        blockers = list(r["origin_blockers"])
        provenance = dict(r["origin_provenance"])
        meta = CLASES_ORIGEN.get(clase, CLASES_ORIGEN[ORIGEN_NO_PRODUCTIVO])
        return {"clase": clase, "clase_declarada": declarado, "peso": meta["peso"],
                "sostiene_estimacion": bool(meta["sostiene_estimacion"]),
                "abre_verified_gate": bool(meta["abre_verified_gate"]),
                "techo_calidad": meta["techo_calidad"], "etiqueta": meta["etiqueta"],
                "blockers": blockers, "origin_gate": bool(r["origin_gate"]),
                "provenance": provenance, "procedencia_validada": True}

    if declarado == ORIGEN_PRIOR_CALIBRADO:
        revision = validar_modelo_calibrado(d)
        if revision["valido"]:
            clase, provenance = ORIGEN_PRIOR_CALIBRADO, dict(d.get("provenance") or {})
        else:
            # Se conserva por compatibilidad, pero NO se honra: sin contrato
            # auditable no hay calibración, hay un prior.
            clase = ORIGEN_PRIOR_LEGACY
            provenance = dict(d.get("provenance") or {})
            blockers = ["contrato de modelo calibrado incompleto: "
                        + "; ".join(revision["motivos"])]
    elif declarado in ORIGEN_PRIOR_ALIAS:
        clase, provenance = ORIGEN_PRIOR_LEGACY, dict(d.get("provenance") or {})
        blockers = ["prior legacy del modelo: se conserva por compatibilidad y NO "
                    "sostiene ninguna estimación productiva"]
    elif declarado == ORIGEN_COMPUTADO_CON_PRIOR:
        clase, provenance = ORIGEN_COMPUTADO_CON_PRIOR, dict(d.get("provenance") or {})
    elif declarado == ORIGEN_COMPUTADO_CON_ESTATICA:
        clase, provenance = ORIGEN_COMPUTADO_CON_ESTATICA, dict(d.get("provenance") or {})
    elif declarado == ORIGEN_DERIVADO_EXTERNO:
        # §5.3 · Se reconoce explícitamente para que NO se degrade a `MANUAL_CONFIG`
        # (que diría algo falso) y para que NO se confunda con `COMPUTED_FROM_SOURCES`:
        # una sola fuente externa transformada NO es una composición de fuentes.
        clase, provenance = ORIGEN_DERIVADO_EXTERNO, dict(d.get("provenance") or {})
        blockers = [("derivación determinista de UNA fuente externa citada: NO sostiene "
                     "por sí sola una cifra ni abre la compuerta de evidencia verificada, "
                     "y NO es COMPUTED_FROM_SOURCES (esa clase exige ≥2 fuentes)")]
    elif declarado == ORIGEN_NO_PRODUCTIVO:
        clase, provenance = ORIGEN_NO_PRODUCTIVO, {}
        blockers = ["combinación declarada NO PRODUCTIVA: no sostiene ninguna cifra"]
    elif declarado in (am.ORIGEN_ESTATICO, am.ORIGEN_MANUAL):
        clase, provenance = declarado, dict(d.get("provenance") or {})
        blockers = list(CLASES_ORIGEN[declarado]["etiqueta"] and
                        [CLASES_ORIGEN[declarado]["etiqueta"]])
    elif declarado is None:
        clase, provenance = por_defecto, dict(d.get("provenance") or {})
        blockers = [f"origen no declarado por el insumo: se clasifica {clase} "
                    f"(no abre la compuerta de evidencia verificada)"]
    else:
        clase, provenance = por_defecto, dict(d.get("provenance") or {})
        blockers = [f"origen {declarado!r} fuera del vocabulario: se clasifica {clase}"]

    meta = CLASES_ORIGEN.get(clase, CLASES_ORIGEN[ORIGEN_NO_PRODUCTIVO])
    return {"clase": clase, "clase_declarada": declarado, "peso": meta["peso"],
            "sostiene_estimacion": bool(meta["sostiene_estimacion"]),
            "abre_verified_gate": bool(meta["abre_verified_gate"]),
            "techo_calidad": meta["techo_calidad"], "etiqueta": meta["etiqueta"],
            "blockers": blockers,
            "origin_gate": bool(meta["abre_verified_gate"] and not blockers),
            "provenance": provenance, "procedencia_validada": True}


def componer_origen(declaraciones: Sequence[Any], *, excluidas: Sequence[Any] = (),
                    por_defecto: str = am.ORIGEN_MANUAL) -> Dict[str, Any]:
    """COMPOSICIÓN de origin de un cálculo, con reglas explícitas y sin engaño (§3).

    `declaraciones` son los insumos que PARTICIPAN del cálculo. `excluidas` son los
    declarados que NO participan: se reportan, jamás se cuentan como fuente. Cada
    entrada puede ser una declaración CON procedencia (se clasifica aquí, delegando
    la degradación en `atribucion_mercado`) o el resultado ya clasificado de
    `clasificar_origen_extendido`. Una declaración que AFIRMA
    `EXTERNAL_SOURCE` sin aportar procedencia completa NO se honra: se degrada a
    `MANUAL_CONFIG` y la composición pasa a `NOT_PRODUCTIVE`.

    Tabla de composición (primera regla que casa; versión `ORIGIN_COMPOSITION_VERSION`):

      · `usadas` vacío ................................ NOT_PRODUCTIVE
      · alguna NO LAVABLE (MANUAL_CONFIG / prior legacy) NOT_PRODUCTIVE
        — `EXTERNAL_SOURCE + MANUAL_CONFIG → NOT_PRODUCTIVE`, JAMÁS
          `COMPUTED_FROM_SOURCES`.
      · `EXTERNAL_SOURCE` + `CALIBRATED_MODEL_PRIOR` .. COMPUTED_WITH_MODEL_PRIOR
      · `CALIBRATED_MODEL_PRIOR` sin externas .......... COMPUTED_WITH_MODEL_PRIOR
      · `EXTERNAL_SOURCE` + `STATIC_REFERENCE` ........ COMPUTED_WITH_STATIC_REFERENCE
      · ≥2 `EXTERNAL_SOURCE` (o externas + `COMPUTED_FROM_SOURCES`)
        ............................................ COMPUTED_FROM_SOURCES
      · una sola clase ............................... esa clase

    El TECHO DE CALIDAD del resultado es el mínimo de los techos de las clases
    usadas: un modelo calibrado dentro del cálculo impide el nivel HIGH, y un
    parámetro a mano impide cualquier cifra productiva.
    """
    usadas: List[Dict[str, Any]] = []
    for d in (declaraciones or []):
        c = _entrada_clasificada(d) or clasificar_origen_extendido(d, por_defecto=por_defecto)
        if c["clase"]:
            usadas.append({**c, "declaracion": d})
    descartadas: List[Dict[str, Any]] = []
    for d in (excluidas or []):
        c = _entrada_clasificada(d) or clasificar_origen_extendido(d, por_defecto=por_defecto)
        if c["clase"]:
            descartadas.append({**c, "declaracion": d})

    clases = [c["clase"] for c in usadas]
    cuenta = {clase: clases.count(clase) for clase in set(clases)}
    ext = cuenta.get(am.ORIGEN_EXTERNO, 0) + cuenta.get(am.ORIGEN_COMPUTADO, 0)
    priors = cuenta.get(ORIGEN_PRIOR_CALIBRADO, 0)
    estaticas = cuenta.get(am.ORIGEN_ESTATICO, 0)
    no_lavables = [c for c in clases if c in CLASES_NO_LAVABLES]

    motivos: List[str] = []
    if not usadas:
        regla, origen = "R0_SIN_INSUMOS", ORIGEN_NO_PRODUCTIVO
    elif no_lavables:
        regla, origen = "R1_NO_LAVADO", ORIGEN_NO_PRODUCTIVO
        motivos.append("insumos no lavables en el cálculo: "
                       + ", ".join(sorted(set(no_lavables)))
                       + " → la composición NO se etiqueta como derivada de fuentes")
    elif ext >= 1 and priors >= 1:
        regla, origen = "R2_EXTERNA_MAS_PRIOR_CALIBRADO", ORIGEN_COMPUTADO_CON_PRIOR
    elif priors >= 1:
        if estaticas >= 1 or len(usadas) > 1:
            regla, origen = "R3_SOLO_PRIOR_CALIBRADO", ORIGEN_COMPUTADO_CON_PRIOR
        else:
            regla, origen = "R6_CLASE_UNICA", ORIGEN_PRIOR_CALIBRADO
    elif ext >= 1 and estaticas >= 1:
        regla, origen = "R4_EXTERNA_MAS_ESTATICA", ORIGEN_COMPUTADO_CON_ESTATICA
    elif ext >= 2:
        regla, origen = "R5_FUENTES_MULTIPLES", am.ORIGEN_COMPUTADO
    elif len(usadas) == 1:
        regla, origen = "R6_CLASE_UNICA", clases[0]
    else:
        # Mezcla de una sola clase sin fuente externa, sin prior ni estática.
        regla, origen = "R6_CLASE_UNICA", (clases[0] if clases else ORIGEN_NO_PRODUCTIVO)

    techo = _min_calidad(*[c["techo_calidad"] for c in usadas]) if usadas \
        else QUALITY_INSUFFICIENT
    sostiene = bool(usadas) and origen != ORIGEN_NO_PRODUCTIVO \
        and any(c["sostiene_estimacion"] for c in usadas)

    motivos.append(dict(REGLAS_COMPOSICION)[regla])
    if descartadas:
        motivos.append("insumos declarados que NO participan del cálculo: "
                       + ", ".join(sorted({c["clase"] for c in descartadas}))
                       + " (no se cuentan como fuente)")

    composicion = {
        "composicion_version": ORIGIN_COMPOSITION_VERSION,
        "origin": origen,
        "origin_etiqueta": ETIQUETA_COMPOSICION.get(origen, origen),
        "regla": regla,
        "regla_detalle": dict(REGLAS_COMPOSICION)[regla],
        "clases_usadas": clases,
        "cuenta_por_clase": cuenta,
        "clases_excluidas": [c["clase"] for c in descartadas],
        "peso_resultante": max(
            (c["peso"] for c in usadas),
            key=lambda p: {PESO_ALTO: 3, PESO_MEDIO: 2, PESO_BAJO: 1, PESO_NULO: 0}.get(p, 0),
            default=PESO_NULO) if usadas else PESO_NULO,
        "sostiene_estimacion": sostiene,
        # Sólo la CLASE COMPUESTA decide si la composición puede abrir la compuerta de
        # evidencia verificada: si entró un modelo o una referencia estática, NO puede
        # —aunque haya fuentes externas dentro—, porque la cifra ya no es sólo suya.
        "abre_verified_gate": (origen in (am.ORIGEN_EXTERNO, am.ORIGEN_COMPUTADO)
                               and not no_lavables),
        "techo_calidad": techo,
        "excluidos": [{"clase": c["clase"], "motivo": ("declarado y NO usado como insumo "
                                                       "del cálculo"),
                       "blockers": c["blockers"]} for c in descartadas],
        "no_lavado": (not no_lavables),
        "motivos": motivos,
    }
    composicion["hash"] = _sha256({k: composicion[k] for k in
                                   ("origin", "regla", "clases_usadas", "techo_calidad")})
    return composicion


# ══════════════════════════════════════════════════════════════════════════════
# §16 · CONTRATO DEL MODELO CALIBRADO (distinto del legacy)
# ══════════════════════════════════════════════════════════════════════════════
def validar_modelo_calibrado(declaracion: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """¿El `CALIBRATED_MODEL_PRIOR` cumple el contrato auditable de §16?

    Sólo un contrato COMPLETO puede contribuir a `INDICATIVE`. Si falta cualquier
    campo —muestra, error de calibración, vigencia, procedencia o hash— el insumo
    NO es un modelo calibrado y se conserva como `LEGACY_MODEL_PRIOR` (no
    productivo).
    """
    d = dict(declaracion or {})
    faltantes = [c for c in CONTRATO_MODELO_CALIBRADO if _v(d.get(c)) is None]
    motivos: List[str] = []
    if faltantes:
        motivos.append("faltan campos del contrato: " + ", ".join(faltantes))
    mu = _num(d.get("sample_size"))
    if mu is None:
        if "sample_size" not in faltantes:
            motivos.append("sample_size no numérico")
    elif mu < MIN_MUESTRA_CALIBRACION:
        motivos.append(f"muestra insuficiente ({mu:g} < {MIN_MUESTRA_CALIBRACION})")
    err = _num(d.get("calibration_error"))
    if err is None:
        if "calibration_error" not in faltantes:
            motivos.append("calibration_error no numérico")
    elif not (0.0 <= err <= MAX_ERROR_CALIBRACION):
        motivos.append(f"error de calibración fuera de rango ({err:g})")
    for campo, clave in (("central_value_m2", "central"), ("low_value_m2", "low"),
                         ("high_value_m2", "high")):
        v = _num(d.get(campo))
        if v is not None and v <= 0:
            motivos.append(f"{campo} debe ser > 0")
    c, lo, hi = (_num(d.get("central_value_m2")), _num(d.get("low_value_m2")),
                 _num(d.get("high_value_m2")))
    if None not in (c, lo, hi) and not (lo <= c <= hi):
        motivos.append("rango del modelo inconsistente (low ≤ central ≤ high)")
    prov = d.get("provenance")
    if not isinstance(prov, dict) or not prov:
        if "provenance" not in faltantes:
            motivos.append("provenance ausente o no es un objeto")
    elif not (_v(prov.get("proveedor")) or _v(prov.get("entity")) or _v(prov.get("fuente"))):
        motivos.append("provenance sin entidad que respalde la calibración")
    if _v(d.get("hash")) is None and "hash" not in faltantes:
        motivos.append("hash ausente")
    return {"contrato_version": CALIBRATED_PRIOR_CONTRACT_VERSION,
            "valido": not faltantes and not motivos,
            "faltantes": faltantes, "motivos": motivos,
            "clase": (ORIGEN_PRIOR_CALIBRADO if (not faltantes and not motivos)
                      else ORIGEN_PRIOR_LEGACY),
            "min_muestra": MIN_MUESTRA_CALIBRACION,
            "max_error": MAX_ERROR_CALIBRACION}


# ══════════════════════════════════════════════════════════════════════════════
# §28/§29 · GAP REPORT
# ══════════════════════════════════════════════════════════════════════════════
FUENTES_AUTOMATICAS_CANDIDATAS = {
    "comparables": {
        "fuente": "oferta inmobiliaria publicada de la ciudad (portal con contrato de datos)",
        "tipo": "EXTERNAL_SOURCE", "aporta": ("comparables con tipología, área, precio, "
                                              "fecha y procedencia completa (fuente, "
                                              "referencia y sha256)")},
    "estadisticas": {
        "fuente": "estadística agregada oficial de valor por m² (catastro municipal)",
        "tipo": "EXTERNAL_SOURCE", "aporta": ("referencia agregada por sector con vigencia "
                                              "declarada y descarga reproducible")},
    "modelo_calibrado": {
        "fuente": "modelo calibrado con muestra declarada",
        "tipo": ORIGEN_PRIOR_CALIBRADO, "aporta": ("central/low/high por m² con sample_size, "
                                                  "calibration_error, vigencia y hash")},
    "rentas": {
        "fuente": "referencia de arriendos publicados (portal con contrato de datos)",
        "tipo": "EXTERNAL_SOURCE", "aporta": "rental_reference con procedencia completa"},
    "costos": {
        "fuente": "publicación de costos de construcción (índice sectorial)",
        "tipo": "EXTERNAL_SOURCE", "aporta": "costo unitario por m² con vigencia declarada"},
}


def informe_de_brecha(entrada: Optional[Dict[str, Any]], *,
                      faltantes: Sequence[str] = ()) -> Dict[str, Any]:
    """GAP REPORT concreto: qué fuente AUTOMÁTICA habría que incorporar (§28/§29).

    Se declara con `estado: "NO INCORPORADA"` y `contrato: None`: el reporte pide
    una fuente, NO afirma que exista. Cerrar por falta de fuente de mercado
    automática es un problema DISTINTO de cerrar porque el único parámetro
    disponible sea `MANUAL_CONFIG`.
    """
    e = dict(entrada or {})
    faltan = list(faltantes)
    if not e.get("comparables"):
        faltan.append("comparables")
    if not e.get("estadisticas_externas"):
        faltan.append("estadisticas")
    if not e.get("modelo_calibrado"):
        faltan.append("modelo_calibrado")
    if not e.get("costo_reposicion"):
        faltan.append("costos")
    if not e.get("rental_reference"):
        faltan.append("rentas")
    vistas, peticiones = set(), []
    for clave in faltan:
        if clave in vistas or clave not in FUENTES_AUTOMATICAS_CANDIDATAS:
            continue
        vistas.add(clave)
        c = FUENTES_AUTOMATICAS_CANDIDATAS[clave]
        peticiones.append({**c, "estado": "NO INCORPORADA", "contrato": None,
                           "por_que_no_basta": ("un parámetro local escrito a mano "
                                                "(MANUAL_CONFIG) no es una fuente y no "
                                                "puede declararse como tal")})
    return {
        "gate": "EVIDENCE_GAP_REPORT",
        "motivo_cierre": "MISSING_MARKET_EVIDENCE",
        "ciudad": e.get("contexto", {}).get("ciudad") if isinstance(e.get("contexto"), dict)
        else None,
        "falta": sorted(vistas),
        "fuentes_automaticas_a_incorporar": peticiones,
        "distincion": ("Cerrar por AUSENCIA DE FUENTE DE MERCADO AUTOMÁTICA "
                       "(MISSING_MARKET_EVIDENCE) NO es lo mismo que cerrar porque el "
                       "parámetro local disponible sea MANUAL_CONFIG: lo primero pide una "
                       "fuente nueva; lo segundo declara que un valor escrito a mano no "
                       "sostiene una cifra."),
        "generado_en": _ahora(),
    }


# ══════════════════════════════════════════════════════════════════════════════
# §34 · METODOLOGÍA BASE
# ══════════════════════════════════════════════════════════════════════════════
def contiene_vocabulario_metodologico_prohibido(texto: Optional[str]) -> bool:
    """¿El texto apoya la metodología en «norma + concepto técnico + validación»?"""
    if not texto:
        return False
    bajo = str(texto).lower()
    return any(p in bajo for p in VOCABULARIO_METODOLOGICO_PROHIBIDO)


def resumen_metodologico() -> Dict[str, Any]:
    """§34 · la metodología base se declara con el vocabulario correcto."""
    return {
        "metodologia_version": METHODOLOGY_VERSION,
        "metodologia_base": METODOLOGIA_BASE,
        "componentes": ["fuentes disponibles", "análisis técnico automatizado",
                        "metodología versionada"],
        "revision_profesional": REVISION_PROFESIONAL_SEPARADA,
        "naturaleza_de_la_salida": NATURALEZA_ESTIMACION,
        "no_es": ["avalúo", "valor verificado", "dictamen firmado", "peritaje"],
    }


def vocabulario_economico(status: str) -> str:
    """§31 · término legible del estado de la estimación (vocabulario cerrado)."""
    return VOCABULARIO_ECONOMICO.get(status, "NO FUE POSIBLE ESTIMAR")


def es_valor_verificado(status: str) -> bool:
    """Una ESTIMACIÓN nunca es un valor verificado. Siempre `False`."""
    return False


def etiqueta_es_verificada(etiqueta: Optional[str]) -> bool:
    """¿La etiqueta afirma información verificada? (prohibido en estimación)."""
    return _norm_txt(etiqueta) in {_norm_txt(e) for e in ETIQUETAS_VERIFICADAS_PROHIBIDAS}


# ══════════════════════════════════════════════════════════════════════════════
# §23 · REFERENCIA HISTÓRICA (SOLO FORENSE)
# ══════════════════════════════════════════════════════════════════════════════
def referencia_historica_forense(historico: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """`historical_estimate_reference`: SOLO FORENSE, NUNCA input (§23).

    Devuelve el bloque con `usado_como_input = False` SIEMPRE. El motor lo escribe
    en el resultado y no lee su valor para calcular nada.
    """
    h = dict(historico or {})
    return {
        "old_run_id": h.get("old_run_id") or h.get("run_id"),
        "old_value": h.get("old_value"),
        "old_range": h.get("old_range"),
        "old_method": h.get("old_method"),
        "old_inputs": h.get("old_inputs"),
        "old_origin": h.get("old_origin"),
        "old_master_hash": h.get("old_master_hash"),
        "usado_como_input": False,
        "naturaleza": ("REFERENCIA FORENSE: se conserva para comparar corridas y NO es "
                       "input de la nueva estimación"),
        "campos_contrato": list(CAMPOS_REFERENCIA_HISTORICA),
    }


# ══════════════════════════════════════════════════════════════════════════════
# §15/§12 · ANCHO DE RANGO Y PRECISIÓN
# ══════════════════════════════════════════════════════════════════════════════
def _ajuste_n_comparables(n: int) -> Tuple[float, str]:
    for minimo, ajuste in AJUSTE_N_COMPARABLES:
        if n >= minimo:
            return ajuste, f"nº de comparables usados = {n} → +{ajuste:.2f}"
    return 0.15, f"nº de comparables usados = {n} → +0.15"


def ancho_de_rango(*, dispersion_cv: Optional[float] = None, comparables_usados: int = 0,
                   antiguedad_meses: Optional[int] = None,
                   matching_quality: Optional[float] = 1.0,
                   origen: Optional[str] = None, error_modelo: Optional[float] = None,
                   evidence_quality: str = QUALITY_MEDIUM,
                   razon_explicita: Optional[str] = None) -> Dict[str, Any]:
    """Ancho del rango DERIVADO de la incertidumbre real (§15), reproducible.

    Fórmula (`RANGE_WIDTH_VERSION`)::

        semi = 0.06
             + 1.2 · min(cv, 0.25)
             + AJUSTE_N[n]
             + 0.02 · trimestres_antiguedad        (cap 0.10)
             + 0.06 · (1 − matching_quality)
             + AJUSTE_ORIGEN[composición]
             + 1.0 · min(error_modelo, 0.15)
        semi = min(semi, 0.60)

    Luego la BANDA de la calidad manda: si `semi` supera el máximo de la banda, la
    CALIDAD se DEGRADA (el rango no se estrecha a la fuerza); si queda por debajo
    del mínimo, se ELEVA al mínimo. `razon_explicita` desactiva el forzado de banda
    y la excepción queda documentada.

    Menor calidad de evidencia ⇒ rango más ancho, siempre por la misma vía.
    """
    calidad = evidence_quality if evidence_quality in ORDEN_CALIDAD else QUALITY_INSUFFICIENT
    componentes: Dict[str, Any] = {"base": ANCHO_BASE}
    ajustes: List[str] = [f"base metodológica versionada = ±{ANCHO_BASE:.0%}"]

    cv = _num(dispersion_cv)
    cv_uso = 0.0 if cv is None else max(min(cv, ANCHO_MAX_DISPERSION), 0.0)
    componentes["dispersion"] = ANCHO_COEF_DISPERSION * cv_uso
    componentes["cv_usado"] = cv_uso
    ajustes.append(f"dispersión de comparables (cv = {cv:.4f} → {cv_uso:.4f}) "
                   f"→ +{componentes['dispersion']:.2%}"
                   if cv is not None else
                   f"dispersión no medible (sin comparables) → +0.00")

    aj_n, txt_n = _ajuste_n_comparables(int(comparables_usados or 0))
    componentes["comparables"] = aj_n
    ajustes.append(txt_n)

    meses = int(antiguedad_meses) if isinstance(antiguedad_meses, (int, float)) \
        and antiguedad_meses is not None else None
    trimestres = 0 if meses is None else max(meses // 3, 0)
    aj_ant = min(ANCHO_COEF_ANTIGUEDAD * trimestres, ANCHO_MAX_ANTIGUEDAD)
    componentes["antiguedad"] = aj_ant
    componentes["trimestres_antiguedad"] = trimestres
    ajustes.append(f"antigüedad de la evidencia = {meses} meses ({trimestres} trimestres) "
                   f"→ +{aj_ant:.2%}")

    mq = _num(matching_quality)
    mq = 1.0 if mq is None else max(min(mq, 1.0), 0.0)
    componentes["matching"] = ANCHO_COEF_MATCHING * (1.0 - mq)
    ajustes.append(f"calidad del matching = {mq:.2f} → "
                   f"+{componentes['matching']:.2%}")

    aj_or = AJUSTE_POR_ORIGEN.get(origen, AJUSTE_POR_ORIGEN.get(ORIGEN_NO_PRODUCTIVO, 0.20))
    componentes["tipo_evidencia"] = aj_or
    ajustes.append(f"tipo de evidencia ({origen or 'NO DECLARADO'}) → +{aj_or:.2%}")

    err = _num(error_modelo)
    aj_err = 0.0 if err is None else ANCHO_COEF_ERROR_MODELO * min(max(err, 0.0),
                                                                  ANCHO_MAX_ERROR_MODELO)
    componentes["error_modelo"] = aj_err
    ajustes.append(f"error declarado del modelo = {err} → +{aj_err:.2%}"
                   if err is not None else "error del modelo no declarado → +0.00")

    crudo = ANCHO_BASE + componentes["dispersion"] + componentes["comparables"] \
        + componentes["antiguedad"] + componentes["matching"] \
        + componentes["tipo_evidencia"] + componentes["error_modelo"]
    crudo = min(max(crudo, 0.0), MAX_SEMI_ANCHO)
    componentes["semi_ancho_calculado"] = crudo

    motivos: List[str] = []
    calidad_efectiva = calidad
    banda = BANDAS_POR_CALIDAD.get(calidad)
    clamp = "DENTRO_DE_BANDA"
    if calidad == QUALITY_INSUFFICIENT:
        return {"formula_version": RANGE_WIDTH_VERSION, "semi_ancho_relativo": None,
                "porcentaje": None, "componentes": componentes,
                "banda_calidad": None, "clamp": "SIN_RANGO",
                "calidad_efectiva": QUALITY_INSUFFICIENT, "ajustes": ajustes,
                "razon_explicita": razon_explicita,
                "motivos": ["calidad INSUFFICIENT: no se emite rango (no hay base mínima "
                            "para una estimación)"]}

    if razon_explicita:
        motivos.append("excepción justificada de banda: " + str(razon_explicita))
        semi = crudo
    else:
        while calidad_efectiva != QUALITY_INSUFFICIENT:
            banda = BANDAS_POR_CALIDAD[calidad_efectiva]
            if crudo <= banda[1]:
                break
            motivos.append(
                f"el ancho calculado ±{crudo:.1%} supera el máximo de la banda "
                f"{calidad_efectiva} (±{banda[1]:.0%}): la calidad se DEGRADA a "
                f"{_degradar(calidad_efectiva)} en lugar de estrechar el rango")
            calidad_efectiva = _degradar(calidad_efectiva)
        banda = BANDAS_POR_CALIDAD.get(calidad_efectiva, (0.15, MAX_SEMI_ANCHO))
        semi = crudo
        if semi < banda[0]:
            motivos.append(f"el ancho calculado ±{semi:.1%} es menor que el mínimo de la "
                           f"banda {calidad_efectiva} (±{banda[0]:.0%}): se ELEVA al mínimo "
                           f"(una calidad {calidad_efectiva} no puede publicar un rango "
                           f"más estrecho)")
            semi = banda[0]
            clamp = "ELEVADO_AL_MINIMO"
        if semi > banda[1]:
            semi = banda[1]
            clamp = "RECORTADO_AL_MAXIMO"

    semi = min(max(semi, 0.0), MAX_SEMI_ANCHO)
    motivos.append(f"semi-ancho final = ±{semi:.2%} con calidad efectiva {calidad_efectiva}")
    return {
        "formula_version": RANGE_WIDTH_VERSION,
        "semi_ancho_relativo": semi,
        "porcentaje": f"±{semi:.2%}",
        "componentes": componentes,
        "banda_calidad": list(banda) if banda else None,
        "calidad_declarada": calidad,
        "calidad_efectiva": calidad_efectiva,
        "clamp": clamp,
        "ajustes": ajustes,
        "razon_explicita": razon_explicita,
        "motivos": motivos,
    }


def redondear_segun_evidencia(valor: float, semi_ancho_relativo: Optional[float]) -> int:
    """§12 · la cifra central no puede tener más precisión que la evidencia.

    El paso de redondeo se deriva del semi-ancho: a más incertidumbre, menos
    dígitos significativos. El paso NUNCA es menor a $1.000.000, de modo que una
    cifra como `399.500.000` no puede emitirse.
    """
    if valor is None:
        return None  # type: ignore[return-value]
    semi = MAX_SEMI_ANCHO if semi_ancho_relativo is None else float(semi_ancho_relativo)
    paso = PRECISION_POR_ANCHO[-1][1]
    for umbral, p in PRECISION_POR_ANCHO:
        if semi >= umbral:
            paso = p
            break
    return int(round(float(valor) / paso) * paso)


# ══════════════════════════════════════════════════════════════════════════════
# §17 · M1 · MARKET COMPARISON
# ══════════════════════════════════════════════════════════════════════════════
def _valor_m2_de(c: Dict[str, Any]) -> Optional[float]:
    v = _num(c.get("value_m2") or c.get("valor_m2") or c.get("precio_m2"))
    if v is not None and v > 0:
        return v
    total = _num(c.get("valor_total") or c.get("precio_total") or c.get("valor"))
    area = _num(c.get("area_m2") or c.get("area"))
    if total and area and area > 0:
        return total / area
    return None


def _fecha_de(c: Dict[str, Any]) -> Optional[date]:
    return _fecha(c.get("fecha") or c.get("fecha_dato") or c.get("fecha_publicacion"))


def _cribar_comparables(comparables: Sequence[Any], *, tipologia: Optional[str] = None,
                        hoy: Optional[date] = None) -> Dict[str, Any]:
    """Criba de comparables: procedencia, tipología y outlier, con motivo DECLARADO.

    Un comparable sin `origen_tipo` y sin procedencia estructurada se clasifica
    `MANUAL_CONFIG` y se RECHAZA: no se inventa que sea una fuente. Una TASA MANUAL
    no equivale a un comparable (§17).
    """
    hoy = hoy or date.today()
    tip = _norm_txt(tipologia)
    aceptados: List[Dict[str, Any]] = []
    rechazados: List[Dict[str, Any]] = []
    declarados = list(comparables or [])

    for i, c in enumerate(declarados):
        c = dict(c or {})
        cid = str(c.get("comparable_id") or c.get("id") or f"C{i + 1}")
        # La clase del comparable se lee SOLO de lo que declara: sin procedencia
        # estructurada completa, `atribucion_mercado` degrada a `MANUAL_CONFIG` y el
        # comparable se RECHAZA. La ausencia de declaración JAMÁS se lee como fuente.
        clas = clasificar_origen_extendido(
            {"origen_tipo": c.get("origen_tipo") or c.get("origin"),
             **{k: c.get(k) for k in am.PROCEDENCIA_EXTERNA if k in c},
             "provenance": c.get("provenance") or c.get("procedencia")},
            por_defecto=am.ORIGEN_MANUAL)
        if clas["clase"] not in (am.ORIGEN_EXTERNO, am.ORIGEN_COMPUTADO) \
                or not clas["origin_gate"]:
            detalle_bloqueo = ("; ".join(clas["blockers"]) or
                               "sin procedencia completa (source_id, proveedor, fecha, "
                               "referencia, sha256)")
            rechazados.append({
                "comparable_id": cid, "clase_origen": clas["clase"],
                "motivo": ("origen " + str(clas["clase"]) + " no habilitante para evidencia "
                           "de mercado: " + detalle_bloqueo)})
            continue
        tip_c = _norm_txt(c.get("tipologia") or c.get("tipo"))
        if tip and tip_c and tip_c != tip:
            rechazados.append({"comparable_id": cid, "clase_origen": clas["clase"],
                               "tipologia": tip_c, "motivo":
                               f"tipología incompatible: comparable {tip_c} ≠ sujeto {tip}"})
            continue
        v_m2 = _valor_m2_de(c)
        if v_m2 is None:
            rechazados.append({"comparable_id": cid, "clase_origen": clas["clase"],
                               "motivo": "sin valor ni área: no es un comparable "
                                         "utilizable (no se rellena)"})
            continue
        aceptados.append({"comparable_id": cid, "value_m2": v_m2,
                          "tipologia": tip_c, "area_m2": _num(c.get("area_m2") or c.get("area")),
                          "fecha": (_fecha_de(c).isoformat() if _fecha_de(c) else None),
                          "clase_origen": clas["clase"], "origin": clas["clase"],
                          "provenance": dict(clas["provenance"]),
                          "outlier_declarado": bool(c.get("outlier") or c.get("es_outlier"))})

    # Outlier: desviación relativa contra la MEDIANA de los comparables utilizables.
    usados: List[Dict[str, Any]] = []
    if aceptados:
        valores = [a["value_m2"] for a in aceptados]
        mediana = statistics.median(valores)
        for a in aceptados:
            desv = abs(a["value_m2"] - mediana) / mediana if mediana else 0.0
            if a["outlier_declarado"]:
                a["motivo_outlier"] = "marcado como outlier por la corrida"
            elif desv > UMBRAL_OUTLIER_RELATIVO:
                a["motivo_outlier"] = (f"outlier: value_m2={a['value_m2']:,.0f} se desvía "
                                       f"{desv:.1%} de la mediana ({mediana:,.0f}) > "
                                       f"{UMBRAL_OUTLIER_RELATIVO:.0%}")
            if a.get("motivo_outlier"):
                rechazados.append({"comparable_id": a["comparable_id"],
                                   "clase_origen": a["clase_origen"],
                                   "value_m2": a["value_m2"],
                                   "motivo": a["motivo_outlier"]})
                continue
            usados.append(a)

    valores = [u["value_m2"] for u in usados]
    disp = None
    if len(valores) >= 2:
        media = sum(valores) / len(valores)
        disp = statistics.pstdev(valores) / media if media else None
    frescura = None
    antiguedad_max = None
    fechas = [_fecha(u["fecha"]) for u in usados if u.get("fecha")]
    fechas = [f for f in fechas if f]
    if fechas:
        mas_nueva = max(fechas)
        mas_vieja = min(fechas)
        frescura = _meses_entre(mas_nueva, hoy)          # meses desde la más reciente
        antiguedad_max = _meses_entre(mas_vieja, hoy)    # meses desde la más antigua
    return {"declarados": len(declarados), "usados": usados, "rechazados": rechazados,
            "dispersion_cv": disp, "frescura_meses": frescura,
            "antiguedad_meses": antiguedad_max}


def _pesos_por_frescura(usados: Sequence[Dict[str, Any]], hoy: date) -> List[float]:
    """Peso por antigüedad: la evidencia más reciente pesa más (mitad / año)."""
    pesos = []
    for u in usados:
        f = _fecha(u.get("fecha"))
        if f is None:
            pesos.append(0.5)                      # sin fecha declarada: peso reducido
            continue
        meses = _meses_entre(f, hoy)
        pesos.append(max(0.5 ** (meses / 12.0), 0.10))
    return pesos


def metodo_m1_comparacion_mercado(entrada: Dict[str, Any], *,
                                  criba: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """§17/§18 · M1 MARKET COMPARISON (método PRINCIPAL si hay comparables).

    Una TASA MANUAL **no** equivale a comparables: sin comparables declarados, M1
    es `NOT_APPLICABLE` y lo dice; no se rellena con la tasa del artefacto local.

    Registra `comparables_used`, `median_price_m2`, `weighted_price_m2`,
    `dispersion`, `adjustments` y `result_range`.
    """
    e = dict(entrada or {})
    hoy = e.get("_hoy") if isinstance(e.get("_hoy"), date) else date.today()
    tipologia = _norm_txt((e.get("tipologia") or {}).get("valor")
                          or e.get("tipologia_valor") or e.get("tipologia"))
    criba = criba if criba is not None else _cribar_comparables(
        e.get("comparables") or [], tipologia=tipologia, hoy=hoy)
    usados, rechazados = criba["usados"], criba["rechazados"]

    base = {"method_id": METODO_M1, "method_name": NOMBRE_METODO[METODO_M1],
            "methods_version": METHODS_VERSION, "inputs": {}, "result": None,
            "range": None, "result_range": None, "origin": None, "confidence": None,
            "comparables_used": [], "comparables_rejected": list(rechazados),
            "median_price_m2": None, "weighted_price_m2": None, "dispersion": None,
            "adjustments": []}

    if not criba["declarados"]:
        return {**base, "status": STATUS_METHOD_NOT_APPLICABLE,
                "reason": ("no se declararon comparables de mercado: M1 no aplica. Una "
                           "TASA MANUAL (MANUAL_CONFIG) NO equivale a comparables y no "
                           "puede sustituirlos.")}
    if not usados:
        return {**base, "status": STATUS_METHOD_INSUFFICIENT_DATA,
                "reason": (f"los {criba['declarados']} comparables declarados fueron "
                           f"rechazados: no queda ninguno utilizable (no se rellena con "
                           f"ningún valor sustituto)"),
                "comparables_rejected": list(rechazados)}

    valores = [u["value_m2"] for u in usados]
    mediana = statistics.median(valores)
    pesos = _pesos_por_frescura(usados, hoy)
    peso_total = sum(pesos) or 1.0
    ponderado = sum(v * p for v, p in zip(valores, pesos)) / peso_total
    ajustes = [
        {"tipo": "ponderación por vigencia", "estado": "APLICADO",
         "detalle": "peso = 0.5^(meses/12), mínimo 0.10; sin fecha declarada = 0.5",
         "pesos": [round(p, 4) for p in pesos]},
        {"tipo": "ajuste por diferencia de área", "estado": "NO_APLICADO",
         "detalle": "sin factor de ajuste con procedencia declarada: no se inventa"},
        {"tipo": "ajuste temporal (índice de mercado)", "estado": "NO_APLICADO",
         "detalle": ("sin índice de mercado con procedencia en esta corrida: la "
                     "antigüedad se refleja en el ANCHO del rango, no en un ajuste "
                     "inventado")},
    ]
    status = STATUS_METHOD_AVAILABLE if len(usados) >= MIN_COMPARABLES_M1 \
        else STATUS_METHOD_PARTIAL
    return {
        **base,
        "status": status,
        "result": {"value_m2": ponderado, "basis": "media ponderada por vigencia"},
        "range": {"low": min(valores), "high": max(valores),
                  "basis": "mín/máx de los comparables usados"},
        "result_range": {"low": min(valores), "high": max(valores),
                         "basis": "mín/máx de los comparables usados"},
        "origin": am.ORIGEN_COMPUTADO if len(usados) >= 2 else am.ORIGEN_EXTERNO,
        "confidence": (CONFIANZA_ALTA if len(usados) >= MIN_COMPARABLES_CALIDAD_ALTA
                       else CONFIANZA_MEDIA if len(usados) >= MIN_COMPARABLES_M1
                       else CONFIANZA_BAJA),
        "reason": (f"comparación de mercado con {len(usados)} comparables utilizables de "
                   f"{criba['declarados']} declarados"
                   + ("" if status == STATUS_METHOD_AVAILABLE else
                      f": por debajo del mínimo de {MIN_COMPARABLES_M1}, resultado PARCIAL")),
        "comparables_used": [{"comparable_id": u["comparable_id"],
                              "value_m2": u["value_m2"], "tipologia": u["tipologia"],
                              "fecha": u["fecha"], "origin": u["origin"],
                              "provenance": u["provenance"]} for u in usados],
        "median_price_m2": mediana,
        "weighted_price_m2": ponderado,
        "dispersion": {"cv": criba["dispersion_cv"], "n": len(usados),
                       "min": min(valores), "max": max(valores)},
        "adjustments": ajustes,
        "inputs": {"comparables_declarados": criba["declarados"],
                   "comparables_usados": len(usados),
                   "tipologia_sujeto": tipologia,
                   "frescura_meses": criba["frescura_meses"],
                   "antiguedad_meses": criba["antiguedad_meses"]},
    }


# ══════════════════════════════════════════════════════════════════════════════
# §19 · M2 · REPLACEMENT COST
# ══════════════════════════════════════════════════════════════════════════════
def metodo_m2_costo_reposicion(entrada: Dict[str, Any]) -> Dict[str, Any]:
    """§19 · M2 REPLACEMENT COST: sólo con área + costo unitario + depreciación/edad.

    Si falta cualquier insumo: `NOT_APPLICABLE` (no se declaró el bloque) o
    `INSUFFICIENT_DATA` (declarado incompleto), SIEMPRE sin rellenar. Un costo
    unitario declarado a mano (`MANUAL_CONFIG`) o un prior legacy NO sostienen un
    costo de reposición productivo.
    """
    e = dict(entrada or {})
    bloque = e.get("costo_reposicion")
    base = {"method_id": METODO_M2, "method_name": NOMBRE_METODO[METODO_M2],
            "methods_version": METHODS_VERSION, "inputs": {}, "result": None,
            "range": None, "result_range": None, "origin": None, "confidence": None,
            "adjustments": []}
    if not isinstance(bloque, dict) or not bloque:
        return {**base, "status": STATUS_METHOD_NOT_APPLICABLE,
                "reason": ("no se declaró costo de reposición (costo unitario, edad/vida "
                           "útil): M2 no aplica y NO se rellena con ningún valor")}

    area = _num((e.get("area") or {}).get("valor_m2") or e.get("area_m2"))
    costo = _num(bloque.get("costo_unitario_m2") or bloque.get("costo_m2"))
    edad = _num(bloque.get("edad_anios") or bloque.get("edad"))
    vida = _num(bloque.get("vida_util_anios") or bloque.get("vida_util"))
    depreciacion = _num(bloque.get("depreciacion"))
    suelo = _num(bloque.get("valor_suelo") or bloque.get("valor_terreno"))
    faltantes = [n for n, v in (("area utilizable", area), ("costo_unitario_m2", costo)) if not v]
    if not (edad is not None or vida is not None or depreciacion is not None):
        faltantes.append("edad_anios / vida_util_anios / depreciacion")
    if faltantes or area is None or costo is None:
        return {**base, "status": STATUS_METHOD_INSUFFICIENT_DATA,
                "reason": ("costo de reposición declarado pero incompleto: falta "
                           + ", ".join(faltantes) + " (no se rellena ningún insumo)"),
                "inputs": {"faltantes": faltantes}}

    clas = clasificar_origen_extendido(bloque, por_defecto=am.ORIGEN_MANUAL)
    if not clas["sostiene_estimacion"]:
        return {**base, "status": STATUS_METHOD_INSUFFICIENT_DATA,
                "origin": clas["clase"],
                "reason": (f"el costo unitario es {clas['clase']} "
                           f"({clas['etiqueta']}): no sostiene un costo de reposición "
                           f"productivo"),
                "inputs": {"clase_origen_costo": clas["clase"],
                           "blockers": clas["blockers"]}}
    if depreciacion is None:
        if vida and vida > 0 and edad is not None:
            depreciacion = min(max(edad, 0.0) / vida, 1.0)
            metodo_dep = "LINEAL_DECLARADA (edad / vida útil)"
        else:
            depreciacion = 0.0
            metodo_dep = "NO_APLICADA (sin edad ni vida útil declaradas)"
    else:
        metodo_dep = "DECLARADA por la corrida"
    construccion = area * costo * (1.0 - depreciacion)
    total = construccion + (suelo or 0.0)
    return {
        **base, "status": STATUS_METHOD_AVAILABLE,
        "result": {"value_total": total, "value_m2": total / area,
                   "construccion": construccion, "suelo": suelo,
                   "depreciacion": depreciacion},
        "range": {"low": construccion * (1 - UMBRAL_OUTLIER_RELATIVO),
                  "high": total, "basis": "banda declarada por el método"},
        "result_range": {"low": construccion * (1 - UMBRAL_OUTLIER_RELATIVO),
                         "high": total, "basis": "banda declarada por el método"},
        "origin": clas["clase"], "confidence": CONFIANZA_MEDIA,
        "reason": (f"costo de reposición = área {area:g} m² × costo {costo:,.0f}/m² × "
                   f"(1 − depreciación {depreciacion:.2f})"
                   + (f" + suelo {suelo:,.0f}" if suelo else " (sin valor de suelo declarado)")),
        "adjustments": [{"tipo": "depreciación", "estado": "APLICADO",
                         "detalle": metodo_dep,
                         "valor": depreciacion},
                        {"tipo": "valor del suelo", "estado": ("APLICADO" if suelo
                                                               else "NO_APLICADO"),
                         "detalle": ("declarado por la corrida" if suelo else
                                     "no declarado: no se estima por diferencia")}],
        "inputs": {"area_m2": area, "costo_unitario_m2": costo, "edad_anios": edad,
                   "vida_util_anios": vida, "depreciacion": depreciacion,
                   "valor_suelo": suelo, "clase_origen_costo": clas["clase"]},
    }


# ══════════════════════════════════════════════════════════════════════════════
# §20 · M3 · INCOME CAPITALIZATION
# ══════════════════════════════════════════════════════════════════════════════
def metodo_m3_capitalizacion_rentas(entrada: Dict[str, Any]) -> Dict[str, Any]:
    """§20 · M3 INCOME CAPITALIZATION: sólo con `rental_reference` Y `cap_rate`.

    Un CAP RATE declarado a mano (`MANUAL_CONFIG`) o un prior legacy NO sostiene la
    capitalización: `INSUFFICIENT_DATA` con el motivo. Sin renta: `NOT_APPLICABLE`.
    Vacancia y gastos NO se inventan: se declaran NO APLICADOS.
    """
    e = dict(entrada or {})
    base = {"method_id": METODO_M3, "method_name": NOMBRE_METODO[METODO_M3],
            "methods_version": METHODS_VERSION, "inputs": {}, "result": None,
            "range": None, "result_range": None, "origin": None, "confidence": None,
            "adjustments": []}
    renta = e.get("rental_reference")
    cap = e.get("cap_rate")
    if not renta:
        return {**base, "status": STATUS_METHOD_NOT_APPLICABLE,
                "reason": ("no se declaró rental_reference: M3 no aplica (sin renta de "
                           "referencia no hay capitalización posible)")}
    if not cap:
        return {**base, "status": STATUS_METHOD_INSUFFICIENT_DATA,
                "reason": ("hay rental_reference pero NO cap_rate: la capitalización "
                           "requiere ambos y no se completa el que falta")}

    def _tasa(d, claves):
        for k in claves:
            v = _num(d.get(k)) if isinstance(d, dict) else None
            if v:
                return v
        return None

    renta_m = _tasa(renta, ("renta_mensual", "valor_mensual", "renta")) if isinstance(renta, dict) \
        else _num(renta)
    tasa = _tasa(cap, ("tasa", "cap_rate", "tasa_central")) if isinstance(cap, dict) else _num(cap)
    if not renta_m:
        return {**base, "status": STATUS_METHOD_INSUFFICIENT_DATA,
                "reason": "rental_reference declarada sin valor de renta utilizable"}
    if not tasa or tasa <= 0:
        return {**base, "status": STATUS_METHOD_INSUFFICIENT_DATA,
                "reason": "cap_rate declarado sin tasa utilizable (> 0)"}

    clas_renta = clasificar_origen_extendido(renta, por_defecto=am.ORIGEN_MANUAL) \
        if isinstance(renta, dict) else clasificar_origen_extendido(
            {"origen_tipo": am.ORIGEN_MANUAL})
    clas_cap = clasificar_origen_extendido(cap, por_defecto=am.ORIGEN_MANUAL) \
        if isinstance(cap, dict) else clasificar_origen_extendido(
            {"origen_tipo": am.ORIGEN_MANUAL})
    if not clas_cap["sostiene_estimacion"]:
        return {**base, "status": STATUS_METHOD_INSUFFICIENT_DATA,
                "origin": clas_cap["clase"],
                "reason": (f"el cap_rate es {clas_cap['clase']} ({clas_cap['etiqueta']}): "
                           f"un cap rate declarado a mano no sostiene una producción"),
                "inputs": {"clase_origen_cap_rate": clas_cap["clase"],
                           "blockers": clas_cap["blockers"]}}
    if not clas_renta["sostiene_estimacion"]:
        return {**base, "status": STATUS_METHOD_INSUFFICIENT_DATA,
                "origin": clas_renta["clase"],
                "reason": (f"la rental_reference es {clas_renta['clase']} "
                           f"({clas_renta['etiqueta']}): no sostiene una producción"),
                "inputs": {"clase_origen_renta": clas_renta["clase"],
                           "blockers": clas_renta["blockers"]}}

    valor = renta_m * 12.0 / tasa
    origen = (ORIGEN_COMPUTADO_CON_PRIOR
              if ORIGEN_PRIOR_CALIBRADO in (clas_renta["clase"], clas_cap["clase"])
              else am.ORIGEN_COMPUTADO)
    return {
        **base, "status": STATUS_METHOD_AVAILABLE,
        "result": {"value_total": valor, "value_m2": None, "renta_anual": renta_m * 12.0,
                   "cap_rate": tasa},
        "range": {"low": valor * 0.85, "high": valor * 1.15,
                  "basis": "banda declarada por el método (±15%)"},
        "result_range": {"low": valor * 0.85, "high": valor * 1.15,
                         "basis": "banda declarada por el método (±15%)"},
        "origin": origen, "confidence": CONFIANZA_MEDIA,
        "reason": (f"capitalización: renta anual {renta_m * 12:,.0f} ÷ cap rate {tasa:.4f}"),
        "adjustments": [
            {"tipo": "vacancia y gastos", "estado": "NO_APLICADO",
             "detalle": "sin dato con procedencia: no se descuenta nada inventado"},
            {"tipo": "cap rate", "estado": "APLICADO",
             "detalle": f"clase {clas_cap['clase']}"}],
        "inputs": {"renta_mensual": renta_m, "cap_rate": tasa,
                   "clase_origen_renta": clas_renta["clase"],
                   "clase_origen_cap_rate": clas_cap["clase"]},
    }


# ══════════════════════════════════════════════════════════════════════════════
# §16 · M4 · BASE INDICATIVA DEL MODELO CALIBRADO
# ══════════════════════════════════════════════════════════════════════════════
def metodo_m4_modelo_calibrado(entrada: Dict[str, Any]) -> Dict[str, Any]:
    """§16 · base INDICATIVA del `CALIBRATED_MODEL_PRIOR` (contrato distinto del legacy).

    NO es un método de mercado: es la única vía por la que un modelo calibrado
    puede contribuir, y sólo hasta `INDICATIVE`. El prior legacy
    (`LEGACY_MODEL_PRIOR`, el hardcode por estrato) NUNCA entra aquí.
    """
    e = dict(entrada or {})
    base = {"method_id": METODO_M4, "method_name": NOMBRE_METODO[METODO_M4],
            "methods_version": METHODS_VERSION, "inputs": {}, "result": None,
            "range": None, "result_range": None, "origin": None, "confidence": None,
            "adjustments": []}
    decl = e.get("modelo_calibrado")
    if not decl:
        return {**base, "status": STATUS_METHOD_NOT_APPLICABLE,
                "reason": ("no se declaró modelo calibrado con contrato auditable (§16): "
                           "el prior legacy del modelo NO se usa")}
    rev = validar_modelo_calibrado(decl)
    if not rev["valido"]:
        return {**base, "status": STATUS_METHOD_INSUFFICIENT_DATA,
                "origin": ORIGEN_PRIOR_LEGACY,
                "reason": ("el modelo declarado no cumple el contrato de calibración: "
                           + "; ".join(rev["motivos"])),
                "inputs": {"faltantes": rev["faltantes"], "motivos": rev["motivos"]}}
    central = _num(decl.get("central_value_m2"))
    lo = _num(decl.get("low_value_m2")) or central
    hi = _num(decl.get("high_value_m2")) or central
    return {
        **base, "status": STATUS_METHOD_AVAILABLE,
        "result": {"value_m2": central, "basis": "modelo calibrado declarado"},
        "range": {"low": lo, "high": hi, "basis": "rango declarado por el modelo"},
        "result_range": {"low": lo, "high": hi, "basis": "rango declarado por el modelo"},
        "origin": ORIGEN_PRIOR_CALIBRADO, "confidence": CONFIANZA_BAJA,
        "reason": (f"modelo calibrado {decl.get('model_version')} "
                   f"(muestra {decl.get('sample_size')}, error "
                   f"{decl.get('calibration_error')}): base INDICATIVA"),
        "adjustments": [{"tipo": "ninguno", "estado": "NO_APLICADO",
                         "detalle": "el modelo se usa tal como está declarado"}],
        "inputs": {"model_version": decl.get("model_version"),
                   "sample_size": decl.get("sample_size"),
                   "calibration_error": _num(decl.get("calibration_error")),
                   "reference_period": decl.get("reference_period"),
                   "hash": decl.get("hash"), "provenance": decl.get("provenance")},
    }


# ══════════════════════════════════════════════════════════════════════════════
# §5.4 · VISIBILIDAD DE LA REFERENCIA CENTRAL (política EXPLÍCITA y VERSIONADA)
# ══════════════════════════════════════════════════════════════════════════════
# La referencia central es SECUNDARIA por doctrina (§12: «el rango es la salida»). El
# motor SIEMPRE puede calcular el punto medio de una banda, pero poder calcularlo no es
# razón para publicarlo con el mismo rango de voz. Esta política decide, con umbrales
# DECLARADOS (nada escondido), en qué estado se publica:
#
#   VISIBLE       · la referencia central se imprime normalmente.
#   DEEMPHASIZED  · se imprime SUBORDINADA y rotulada como secundaria: la evidencia que
#                   la sostiene no acredita la unidad o la muestra no está declarada.
#   HIDDEN        · NO se imprime: la amplitud del rango o el salto entre extremos hacen
#                   que el punto medio no informe nada, o no hay cifra que publicar.
#
# FUNDAMENTO (escrito, no calibrar empíricamente): los umbrales NO están ajustados con
# datos —no existe todavía un conjunto de casos con valor observado contra el cual
# calibrarlos— y por eso se declaran como DECISIÓN DE PRODUCTO versionada, revisable y
# auditable. Se apoyan en: amplitud relativa del rango (semi-ancho efectivo), salto
# entre extremos (`high / low`), `sample_size` declarado o ausente, nivel de calidad de
# la evidencia, número de comparables usados y naturaleza AGREGADA de la referencia de
# nivel 3 (que por definición NO acredita la unidad).
CENTRAL_REFERENCE_VISIBILITY_VERSION = "dictus-central-reference-visibility/1.0.0"

VISIBILIDAD_VISIBLE = "VISIBLE"
VISIBILIDAD_DEENFATIZADA = "DEEMPHASIZED"
VISIBILIDAD_OCULTA = "HIDDEN"
ESTADOS_VISIBILIDAD_CENTRAL = (VISIBILIDAD_VISIBLE, VISIBILIDAD_DEENFATIZADA,
                               VISIBILIDAD_OCULTA)

UMBRALES_VISIBILIDAD_CENTRAL: Dict[str, float] = {
    # Semi-ancho relativo EFECTIVO del rango publicado.
    "semi_ancho_oculta": MAX_SEMI_ANCHO,     # ±60 %: el techo absoluto del motor (§15)
    "semi_ancho_deenfatiza": 0.30,           # ±30 %: el punto medio ya es grueso
    # Salto entre extremos del rango publicado (`high / low`).
    "ratio_oculta": 4.0,
    "ratio_deenfatiza": 2.5,
    # Comparables usados (evidencia que SÍ acredita la unidad).
    "comparables_minimo_visible": 3,
}

FUNDAMENTO_VISIBILIDAD_CENTRAL = (
    "Política de producto VERSIONADA, declarada y auditable: la referencia central es "
    "secundaria respecto del rango (§12), así que su visibilidad depende de cuánto la "
    "sostiene la evidencia —amplitud relativa, salto entre extremos, `sample_size` "
    "declarado, nivel de calidad, nº de comparables y naturaleza AGREGADA de la "
    "referencia de nivel 3—. Los umbrales NO están calibrados empíricamente: son una "
    "decisión declarada, revisable en una versión posterior."
)


def politica_visibilidad_referencia_central(
        *, central: Optional[float] = None, low: Optional[float] = None,
        high: Optional[float] = None,
        semi_ancho_relativo: Optional[float] = None,
        sample_size: Optional[float] = None, sample_size_declarado: Optional[bool] = None,
        comparables_usados: int = 0, evidence_quality: Optional[str] = None,
        referencia_agregada_level_3: bool = False) -> Dict[str, Any]:
    """Estado de VISIBILIDAD de la referencia central, con sus umbrales declarados.

    Ningún umbral vive escondido en el código: los que se aplican viajan en
    `umbrales_aplicados` y su fundamento en `fundamento`. Los estados posibles son
    `VISIBLE` / `DEEMPHASIZED` / `HIDDEN`.
    """
    semi = _num(semi_ancho_relativo)
    ratio = (float(high) / float(low)) if (low and high and float(low) > 0) else None
    comparables = int(comparables_usados or 0)
    calidad = str(evidence_quality or "")
    muestra_declarada = bool(sample_size_declarado) and sample_size is not None
    motivos: List[str] = []
    cortos: List[str] = []

    if central is None or low is None or high is None:
        estado = VISIBILIDAD_OCULTA
        motivos.append("no hay cifra central ni rango que publicar: el motor no produjo "
                       "ninguno de los dos")
        cortos.append("sin cifra central")
    elif semi is not None and semi >= UMBRALES_VISIBILIDAD_CENTRAL["semi_ancho_oculta"]:
        estado = VISIBILIDAD_OCULTA
        motivos.append(f"amplitud relativa ±{semi:.2%} ≥ "
                       f"±{UMBRALES_VISIBILIDAD_CENTRAL['semi_ancho_oculta']:.0%}: a esa "
                       f"amplitud el punto medio del rango no aporta información")
        cortos.append(f"rango ±{semi:.2%}: el punto medio no informa")
    elif ratio is not None and ratio >= UMBRALES_VISIBILIDAD_CENTRAL["ratio_oculta"]:
        estado = VISIBILIDAD_OCULTA
        motivos.append(f"el extremo superior es {ratio:.2f}× el inferior (≥ "
                       f"{UMBRALES_VISIBILIDAD_CENTRAL['ratio_oculta']:g}×): el punto "
                       f"medio de esa banda es un artefacto aritmético")
        cortos.append(f"banda de {ratio:.2f}× entre extremos: el punto medio no informa")
    else:
        deenfatizar: List[str] = []
        deenfatizar_corto: List[str] = []
        if referencia_agregada_level_3:
            deenfatizar.append("la base es una referencia AGREGADA de nivel 3: agrega por "
                               "sector y banda de área y NO acredita esta unidad")
            deenfatizar_corto.append("no acredita la unidad")
            if not muestra_declarada:
                deenfatizar.append("la fuente NO declara el tamaño de la muestra (N) del "
                                   "análisis: no se rellena")
                deenfatizar_corto.append("sin muestra (N) declarada")
        if comparables == 0:
            deenfatizar.append("0 comparables usados: ninguna observación acredita la "
                               "unidad")
            deenfatizar_corto.append("sin comparables")
        if semi is not None and semi >= UMBRALES_VISIBILIDAD_CENTRAL["semi_ancho_deenfatiza"]:
            deenfatizar.append(f"amplitud relativa ±{semi:.2%} ≥ "
                               f"±{UMBRALES_VISIBILIDAD_CENTRAL['semi_ancho_deenfatiza']:.0%}")
            deenfatizar_corto.append(f"rango muy ancho (±{semi:.2%})")
        if ratio is not None and ratio >= UMBRALES_VISIBILIDAD_CENTRAL["ratio_deenfatiza"]:
            deenfatizar.append(f"el extremo superior es {ratio:.2f}× el inferior (≥ "
                               f"{UMBRALES_VISIBILIDAD_CENTRAL['ratio_deenfatiza']:g}×)")
            deenfatizar_corto.append(f"banda de {ratio:.2f}× entre extremos")
        if calidad in (QUALITY_INDICATIVE, QUALITY_INSUFFICIENT):
            deenfatizar.append(f"nivel de evidencia {calidad}: la cifra no es un valor "
                               f"verificado")
            deenfatizar_corto.append(f"evidencia {calidad}")
        if deenfatizar:
            estado = VISIBILIDAD_DEENFATIZADA
            motivos.extend(deenfatizar)
            cortos.extend(deenfatizar_corto)
        else:
            estado = VISIBILIDAD_VISIBLE
            motivos.append("evidencia atribuible a la unidad con muestra declarada, "
                           "amplitud contenida y calidad suficiente")
            cortos.append("evidencia atribuible a la unidad")

    return {
        "policy_version": CENTRAL_REFERENCE_VISIBILITY_VERSION,
        "state": estado,
        "imprime_la_cifra": estado != VISIBILIDAD_OCULTA,
        "reasons": motivos,
        "reasons_short": cortos,
        # Rótulo CORTO para imprimir en una línea de ancho fijo (la P1 es una tira de tres
        # líneas): el fundamento completo viaja en `reasons` y en el JSON.
        "reason_short": " · ".join(cortos[:2]) if cortos else "",
        "umbrales_aplicados": dict(UMBRALES_VISIBILIDAD_CENTRAL),
        "fundamento": FUNDAMENTO_VISIBILIDAD_CENTRAL,
        "calibrada_empiricamente": False,
        "entradas": {"semi_ancho_relativo": semi, "ratio_high_low": ratio,
                     "sample_size": sample_size,
                     "sample_size_declarado": bool(sample_size_declarado),
                     "comparables_usados": comparables,
                     "evidence_quality": calidad or None,
                     "referencia_agregada_level_3": bool(referencia_agregada_level_3),
                     "central": central, "low": low, "high": high},
    }


# ══════════════════════════════════════════════════════════════════════════════
# §22 · M5 · REFERENCIA AGREGADA DE MERCADO (nivel 3 de la escalera)
# ══════════════════════════════════════════════════════════════════════════════
def _procedencia_agregada(ref: Dict[str, Any]) -> List[str]:
    """Campos de procedencia que FALTAN para que la referencia agregada sea usable."""
    prov = ref.get("provenance") if isinstance(ref.get("provenance"), dict) else {}
    plano = {**prov, **{k: v for k, v in ref.items() if v not in (None, "", [], {})}}
    faltan: List[str] = []
    for campo in CAMPOS_PROCEDENCIA_AGREGADA:
        if campo == "url":
            valor = plano.get("url") or plano.get("url_consultada") or plano.get("service_url")
        elif campo == "consultado_en":
            valor = (plano.get("consultado_en") or plano.get("queried_at")
                     or plano.get("consulted_at"))
        elif campo == "http":
            valor = plano.get("http") if plano.get("http") is not None else plano.get("http_status")
        elif campo == "metodologia_declarada":
            valor = (plano.get("metodologia_declarada") or plano.get("metodologia")
                     or plano.get("referencia"))
        else:
            valor = plano.get(campo)
        if campo == "http":
            if str(valor) != "200":
                faltan.append("http=200")
            continue
        if valor in (None, "", [], {}):
            faltan.append(campo)
    return faltan


def _referencia_agregada(entrada: Dict[str, Any]) -> Dict[str, Any]:
    """Diagnóstico de la referencia AGREGADA de nivel 3 declarada en la entrada.

    Devuelve `{"estado", "ref", "min", "max", "clase", "faltantes", "motivos", "banda",
    "banda_contiene", "area"}`. `estado` es `SIN_DECLARAR` (no hay ninguna candidata),
    `SIN_NIVEL_3` (hay referencias externas pero ninguna declara su nivel) o `EVALUADA`.

    Fail-closed sin excepciones: una referencia sin procedencia HTTP completa, sin rango o
    cuya banda de área NO contiene el área del sujeto NO se usa.
    """
    candidatas = [r for r in (entrada.get("estadisticas_externas") or [])
                  if isinstance(r, dict)]
    if not candidatas:
        return {"estado": "SIN_DECLARAR", "ref": None, "motivos": [],
                "faltantes": [], "clase": None}
    niveladas = [r for r in candidatas
                 if str(r.get("nivel") or r.get("clasificacion_contrato") or ""
                        ).upper().startswith("LEVEL_3")]
    if not niveladas:
        return {"estado": "SIN_NIVEL_3", "ref": None, "clase": None, "faltantes": [],
                "motivos": ["las referencias declaradas no acreditan su nivel en la "
                            "escalera de evidencia de mercado"]}
    area = _num((entrada.get("area") or {}).get("valor_m2")
                if isinstance(entrada.get("area"), dict) else entrada.get("area_m2"))
    for ref in niveladas:
        clase = clasificar_origen_extendido(ref)
        if clase["clase"] != am.ORIGEN_EXTERNO or not clase["origin_gate"]:
            return {"estado": "EVALUADA", "ref": ref, "clase": clase, "area": area,
                    "faltantes": ["origin=EXTERNAL_SOURCE con procedencia completa"],
                    "motivos": [f"origen resuelto {clase['clase']}: "
                                + "; ".join(clase["blockers"] or ["sin origin_gate"])]}
        faltan = _procedencia_agregada(ref)
        rango = ref.get("rango_valor_m2") or {}
        lo, hi = _num(rango.get("min")), _num(rango.get("max"))
        valor = _num(ref.get("valor_m2") or ref.get("value_m2"))
        banda = ref.get("banda_area_m2")
        contiene = banda_contiene(banda, area)
        motivos: List[str] = []
        if faltan:
            motivos.append("procedencia incompleta: faltan " + ", ".join(faltan))
        if not lo and valor:
            lo = valor
        if not hi and valor:
            hi = valor
        if not lo or not hi or lo <= 0 or hi < lo:
            motivos.append("no declara un rango de valor por m² utilizable (min/max)")
        if contiene is not True:
            motivos.append("la banda de área declarada por la fuente no acredita contener "
                           f"el área del sujeto ({banda!r} vs {area!r})")
        return {"estado": "EVALUADA", "ref": ref, "clase": clase, "min": lo, "max": hi,
                "banda": banda, "banda_contiene": contiene, "area": area,
                "faltantes": faltan, "motivos": motivos}
    return {"estado": "SIN_DECLARAR", "ref": None, "clase": None, "faltantes": [],
            "motivos": []}


def metodo_m5_referencia_agregada(entrada: Dict[str, Any]) -> Dict[str, Any]:
    """§22/§29/§41 · M5 · REFERENCIA AGREGADA OFICIAL (nivel 3).

    EXTENSIÓN EXPLÍCITA DEL CONTRATO DE FASE 2. El §5 de la escalera dice que LEVEL 3
    **sostiene**, el §29 dice que «precio/m² sectorial válido + resto razonable ⇒
    `OPEN_WITH_LIMITATIONS` + `INDICATIVE_ESTIMATE`», y el §41 exige distinguir evidencia
    fuerte de débil **sin convertir la prudencia en «no intento estimar»**. Sin un método
    que consuma el nivel 3, el motor cerraba con evidencia oficial real: eso incumplía los
    tres. M5 es ese método, y no cambia ninguno de los anteriores.

    Qué consume (fail-closed)
    -------------------------
    Sólo `LEVEL_3_AGGREGATED_MARKET_REFERENCES` con `origin=EXTERNAL_SOURCE` y procedencia
    completa: `source_id`, URL, `consultado_en`, **HTTP 200**, `bytes`, `sha256` y
    metodología declarada. Además la banda de área de la fuente debe **contener** el área
    del sujeto. Si algo de eso falta → `INSUFFICIENT_DATA` con el campo que falta; el
    método NO se usa y NO se sustituye por nada.

    Doctrina del rango (§29)
    ------------------------
      · `range_low`/`range_high` salen **directamente del rango de la FUENTE**
        (`min_valor_m2`/`max_valor_m2` literales) aplicado al área del sujeto: NO de un
        promedio y NO del ancho calculado (que sólo puede declarar más, nunca menos);
      · el `valor_m2` **de la fuente** no existe y no se inventa
        (`no_es_valor_de_la_fuente = True`; la fuente sigue con `valor_m2 = null`);
      · la referencia central SÓLO existe como **derivación explícita** de DICTUS:
        `punto medio del rango oficial`, declarada en `derivation`
        (`type = MIDPOINT_OF_SOURCE_RANGE`, `source_count = 1`) con
        `origen = DERIVED_FROM_EXTERNAL_SOURCE` y sus fuentes citadas, y redondeada
        después por el ancho (§12);

    Doctrina del ORIGIN (§5.3 · corrección semántica)
    -------------------------------------------------
      · la EVIDENCIA BASE es **`EXTERNAL_SOURCE`**: es UNA referencia externa citada
        (la capa municipal con procedencia HTTP completa);
      · la TRANSFORMACIÓN se declara **aparte** en `derivation`. Una transformación
        matemática de UNA sola fuente **NO** es `COMPUTED_FROM_SOURCES`: esa clase
        exige **≥2 fuentes materiales**. Con 1 fuente + derivación determinista el
        origin es `DERIVED_FROM_EXTERNAL_SOURCE` (jamás `COMPUTED_FROM_SOURCES`);
      · `sample_size = null` de la fuente NO se rellena: degrada la calidad y viaja en
        `limitations`;
      · techo `INDICATIVE`: la referencia agrega por localidad y banda de área, así que
        **NO acredita la unidad** ni puede abrir `OPEN`.
    """
    e = dict(entrada or {})
    base = {"method_id": METODO_M5, "method_name": NOMBRE_METODO[METODO_M5],
            "methods_version": METHODS_VERSION, "inputs": {}, "result": None,
            "range": None, "result_range": None, "origin": None, "confidence": None,
            "adjustments": []}
    diag = _referencia_agregada(e)
    if diag["estado"] == "SIN_DECLARAR":
        return {**base, "status": STATUS_METHOD_NOT_APPLICABLE,
                "reason": ("no se declaró ninguna referencia agregada de mercado: sin "
                           "nivel 3 no hay nada que consumir y NO se rellena con la tasa "
                           "manual ni con un prior")}
    if diag["estado"] == "SIN_NIVEL_3":
        return {**base, "status": STATUS_METHOD_NOT_APPLICABLE,
                "reason": ("las referencias declaradas NO acreditan nivel 3 en la "
                           "escalera de evidencia de mercado: " + "; ".join(diag["motivos"]))}
    if diag["motivos"]:
        return {**base, "status": STATUS_METHOD_INSUFFICIENT_DATA,
                "origin": am.ORIGEN_EXTERNO,
                "reason": ("la referencia agregada NO cumple el contrato de nivel 3: "
                           + "; ".join(diag["motivos"])),
                "inputs": {"faltantes": list(diag["faltantes"]),
                           "reference_id": (diag["ref"] or {}).get("reference_id"),
                           "banda_area_m2": diag.get("banda"),
                           "area_sujeto_m2": diag.get("area"),
                           "rango_declarado": (diag["ref"] or {}).get("rango_valor_m2")}}

    ref, lo, hi = diag["ref"], float(diag["min"]), float(diag["max"])
    centro_oficial = (lo + hi) / 2.0                       # derivación explícita, declarada
    semi_banda = (hi - lo) / (2.0 * centro_oficial)
    prov = ref.get("provenance") if isinstance(ref.get("provenance"), dict) else {}
    fuentes_citadas = [{"proveedor": ref.get("proveedor") or prov.get("proveedor"),
                        "fecha": ref.get("fecha") or prov.get("fecha"),
                        "referencia": ref.get("referencia") or prov.get("referencia"),
                        "sha256": ref.get("sha256") or prov.get("sha256")}]
    # §5.3 · LA TRANSFORMACIÓN SE DECLARA APARTE DE LA EVIDENCIA.
    # La evidencia base es UNA fuente externa (`EXTERNAL_SOURCE`); lo que DICTUS hace con
    # ella —el punto medio de su rango publicado— es una DERIVACIÓN determinista de UNA
    # sola fuente y por eso NO se etiqueta `COMPUTED_FROM_SOURCES` (esa clase exige ≥2
    # fuentes materiales). `source_count = 1` lo dice de forma comprobable.
    _fuente_id = ref.get("source_id")
    derivacion = {
        "type": DERIVACION_PUNTO_MEDIO_RANGO,
        "formula": DERIVACION_FORMULA_PUNTO_MEDIO,
        "source_count": 1,
        "source_ids": [str(_fuente_id)] if _fuente_id else [],
        "origin": ORIGEN_DERIVADO_EXTERNO,
        "declaracion": ("punto medio del rango publicado por la fuente: DERIVACIÓN "
                        "determinista de UNA sola fuente externa. NO es una composición "
                        "de fuentes (COMPUTED_FROM_SOURCES exige ≥2) y NO es un valor "
                        "publicado por la fuente."),
        "no_es_composicion_de_fuentes": True,
        "no_es_valor_de_la_fuente": True,
    }
    return {
        **base, "status": STATUS_METHOD_AVAILABLE,
        # El VALOR es una derivación de DICTUS sobre fuentes citadas (§29): se declara su
        # origen y sus fuentes, y NO se atribuye a la fuente ni a la unidad.
        # §5.3 · La EVIDENCIA BASE es UNA fuente externa citada. Antes este campo decía
        # `COMPUTED_FROM_SOURCES`, que exige ≥2 fuentes materiales: una transformación
        # matemática de una sola fuente NO es una composición de fuentes. La
        # transformación viaja declarada APARTE en `derivation`.
        "origin": am.ORIGEN_EXTERNO,
        "origin_basis": ("la evidencia base es UNA referencia externa citada "
                         "(LEVEL_3_AGGREGATED_MARKET_REFERENCES con procedencia HTTP "
                         "completa); la transformación de DICTUS viaja en `derivation`"),
        "derivation": derivacion,
        "confidence": CONFIANZA_BAJA,
        "result": {"value_m2": centro_oficial,
                   "basis": ("punto medio del rango oficial aplicado al área del sujeto: "
                             "DERIVACIÓN EXPLÍCITA de DICTUS, no un valor de la fuente"),
                   "referencia_central_del_rango": True,
                   "derivation": derivacion,
                   "derivacion": "punto medio del rango oficial (min_valor_m2 + "
                                 "max_valor_m2) / 2",
                   "origen_tipo": ORIGEN_DERIVADO_EXTERNO,
                   "origen_evidencia_base": am.ORIGEN_EXTERNO,
                   "fuentes": fuentes_citadas,
                   "no_es_valor_de_la_fuente": True,
                   "no_es_valor_de_la_unidad": True},
        # §5 · la referencia central es un objeto propio: su valor, su derivación y su
        # VISIBILIDAD (política versionada, más abajo) viajan juntos.
        "central_reference": {"value_m2": centro_oficial, "moneda": "COP",
                              "unidad": "COP/m2", "derivation": derivacion,
                              "visibility": None, "visibility_policy": None,
                              "no_es_valor_de_la_fuente": True,
                              "no_es_valor_de_la_unidad": True},
        # El RANGO es el de la FUENTE, literal.
        "range": {"low": lo, "high": hi,
                  "basis": "banda oficial declarada por la fuente (min/max LITERALES)"},
        "result_range": {"low": lo, "high": hi,
                         "basis": "banda oficial declarada por la fuente (min/max LITERALES)"},
        # Aplicación al sujeto: el motor aplica la banda al área y redondea hacia FUERA.
        "banda_oficial": {"min": lo, "max": hi, "unidad": "COP/m2",
                          "banda_area_m2": diag["banda"], "area_sujeto_m2": diag["area"],
                          "contiene_el_area_del_sujeto": diag["banda_contiene"],
                          "reference_id": ref.get("reference_id"),
                          "source_id": ref.get("source_id"),
                          "evidence_hash": ref.get("evidence_hash"),
                          "sha256": ref.get("sha256")},
        "dispersion": {"cv": semi_banda, "n": None,
                       "basis": ("semi-amplitud relativa de la banda oficial: no se "
                                 "inventa una dispersión de comparables")},
        "dispersion_cv": semi_banda,
        "reason": (f"referencia agregada oficial {ref.get('source_id')} "
                   f"({ref.get('sector_referencia')} · banda {diag['banda']} m² ⊇ "
                   f"{diag['area']} m²): rango oficial {lo:,.2f}–{hi:,.2f} COP/m². Agrega "
                   f"por localidad y banda de área: NO acredita la unidad y su techo es "
                   f"INDICATIVE"),
        "adjustments": [
            {"tipo": "promedio aritmético de los extremos", "estado": "NO_APLICADO",
             "detalle": ("la fuente declara un rango: el rango de la fuente es el rango. "
                         "El punto medio se declara como DERIVACIÓN central de DICTUS "
                         f"({ORIGEN_DERIVADO_EXTERNO}: una sola fuente externa, "
                         "declarada en `derivation`), no como valor de la fuente")},
            {"tipo": "división por el área del sujeto", "estado": "NO_APLICADO",
             "detalle": ("no se deriva un precio/m² de ningún valor total: la referencia "
                         "ya está expresada por m²")},
            {"tipo": "traslado de la unidad al sector", "estado": "NO_APLICADO",
             "detalle": ("la referencia NO se corrige por posición, piso, vista ni estado: "
                         "esa incertidumbre la absorbe el ANCHO del rango, no un ajuste "
                         "inventado")},
            {"tipo": "muestra (N) del análisis", "estado": "NO_APLICADO",
             "detalle": ("la fuente NO publica el tamaño de muestra: no se rellena; la "
                         "ausencia degrada la calidad y viaja en las limitaciones")},
        ],
        "inputs": {"reference_id": ref.get("reference_id"),
                   "evidence_hash": ref.get("evidence_hash"),
                   "source_id": ref.get("source_id"), "nivel": ref.get("nivel"),
                   "service_url": prov.get("url") or ref.get("service_url"),
                   "consultado_en": prov.get("consultado_en"),
                   "http": prov.get("http"), "bytes": prov.get("bytes"),
                   "sha256": ref.get("sha256"),
                   "metodologia_declarada": ref.get("metodologia_declarada"),
                   "sector_referencia": ref.get("sector_referencia"),
                   "banda_area_m2": diag["banda"],
                   "area_sujeto_m2": diag["area"],
                   "rango_declarado": {"min": lo, "max": hi, "unidad": "COP/m2",
                                       "basis": "min/max literales de la fuente"},
                   "sample_size": ref.get("sample_size"),
                   "sample_size_declarado": ref.get("sample_size") is not None,
                   "vigencia_declarada": ref.get("vigencia_declarada"),
                   "provenance": prov or ref.get("procedencia"),
                   "limitaciones_declaradas": list(ref.get("limitaciones_declaradas") or [])},
    }


# ══════════════════════════════════════════════════════════════════════════════
# §21 · ENSEMBLE EXPLÍCITO
# ══════════════════════════════════════════════════════════════════════════════
PESOS_BASE_METODO = {
    METODO_M1: 1.00,   # método principal cuando hay comparables suficientes
    METODO_M2: 0.50,
    METODO_M3: 0.40,
    METODO_M4: 0.30,   # base indicativa: nunca compite de igual a igual
    METODO_M5: 0.35,   # referencia agregada: publicada, pero NO acredita la unidad
}
RAZON_PESO = {
    METODO_M1: ("método principal: mide el mercado con evidencia externa citada "
                "(§17); su peso baja si los comparables son escasos"),
    METODO_M2: "costo de reposición: contraste de sustitución, no observación de mercado (§19)",
    METODO_M3: "capitalización de rentas: contraste por rendimiento (§20)",
    METODO_M4: ("base INDICATIVA del modelo calibrado: peso deliberadamente bajo porque "
                "no es observación de mercado (§16)"),
    METODO_M5: ("referencia AGREGADA de nivel 3: agrega por sector y banda de área, así "
                "que NO acredita la unidad; peso bajo y techo INDICATIVE (§22)"),
}


def ensamblar_metodos(resultados: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """§21 · ENSEMBLE explícito: `method`, `weight`, `reason_for_weight` a la vista.

    Los pesos se derivan del estado y la confianza de cada método y se NORMALIZAN.
    Un método no disponible no pesa: se declara rechazado, no se rellena.
    """
    entradas: List[Dict[str, Any]] = []
    for r in resultados:
        mid = r.get("method_id")
        status = r.get("status")
        peso, razon = 0.0, RAZON_PESO.get(mid, "sin razón declarada")
        if status == STATUS_METHOD_AVAILABLE:
            peso = PESOS_BASE_METODO.get(mid, 0.0)
            if mid == METODO_M1:
                n = int((r.get("inputs") or {}).get("comparables_usados") or 0)
                if n < MIN_COMPARABLES_CALIDAD_MEDIA:
                    peso *= 0.7
                    razon += f" · reducido por muestra escasa ({n} comparables)"
            if mid == METODO_M4:
                razon += " · techo INDICATIVE"
        elif status == STATUS_METHOD_PARTIAL:
            peso = 0.4
            razon = "resultado PARCIAL: entra con peso reducido y eleva la incertidumbre"
        else:
            razon = f"NO entra en el ensemble (status {status}): {r.get('reason')}"
        entradas.append({"method": mid, "method_name": r.get("method_name"),
                         "status": status, "weight": peso, "reason_for_weight": razon,
                         "origin": r.get("origin"),
                         "value_m2": ((r.get("result") or {}) or {}).get("value_m2"),
                         "value_total": ((r.get("result") or {}) or {}).get("value_total"),
                         "confidence": r.get("confidence")})

    activos = [x for x in entradas if x["weight"] > 0
               and (x["value_m2"] is not None or x["value_total"] is not None)]
    total = sum(x["weight"] for x in activos)
    for x in entradas:
        x["weight_normalizado"] = (x["weight"] / total) if total else 0.0

    central_m2 = None
    central_total = None
    if activos:
        con_m2 = [x for x in activos if x["value_m2"] is not None]
        if con_m2:
            t = sum(x["weight"] for x in con_m2)
            central_m2 = sum(x["value_m2"] * x["weight"] for x in con_m2) / t
        con_total = [x for x in activos if x["value_total"] is not None]
        if con_total:
            t = sum(x["weight"] for x in con_total)
            central_total = sum(x["value_total"] * x["weight"] for x in con_total) / t
    return {"ensemble_version": METHODS_VERSION, "methods": entradas,
            "central_value_m2": central_m2, "central_value_total": central_total,
            "origins_usados": sorted({x["origin"] for x in activos if x.get("origin")}),
            "disponibles": [x["method"] for x in activos]}


# ══════════════════════════════════════════════════════════════════════════════
# §1/§13/§14 · COMPUERTAS
# ══════════════════════════════════════════════════════════════════════════════
def evaluar_verified_market_evidence_gate(evidencia_mercado: Sequence[Any]) -> Dict[str, Any]:
    """`VERIFIED_MARKET_EVIDENCE_GATE` (OPEN/CLOSED) — §1.

    Pregunta ÚNICA: ¿la evidencia de mercado tiene origen Y procedencia suficientes
    para tratar la cifra como sustentada por fuentes verificadas?

    Sólo `EXTERNAL_SOURCE` / `COMPUTED_FROM_SOURCES` con procedencia COMPLETA
    (delegado en `atribucion_mercado.clasificar_origen`) abren esta compuerta. Un
    `CALIBRATED_MODEL_PRIOR`, una referencia estática o un parámetro a mano NO.

    Estar `CLOSED` NO implica `NOT_ESTIMABLE`: es exactamente el caso que habilita
    `ESTIMATION_GATE = OPEN_WITH_LIMITATIONS` (§30).
    """
    apoyos, bloqueos, obstaculos = [], [], []
    for i, d in enumerate(evidencia_mercado or []):
        clas = clasificar_origen_extendido(d)
        if clas["clase"] in (am.ORIGEN_EXTERNO, am.ORIGEN_COMPUTADO) and clas["origin_gate"]:
            apoyos.append(clas["clase"])
        else:
            obstaculos.append({"clase": clas["clase"],
                               "declarado": clas["clase_declarada"],
                               "blockers": clas["blockers"]})
            bloqueos.append(f"insumo {i + 1}: {clas['clase'] or 'sin declarar'} no acredita "
                            f"procedencia completa")
    estado = VERIFIED_OPEN if apoyos else VERIFIED_CLOSED
    return {
        "gate": VERIFIED_MARKET_EVIDENCE_GATE,
        "gate_state": estado,
        "state": estado,
        "pregunta": ("¿la evidencia de mercado tiene origen y procedencia suficientes para "
                     "tratar la cifra como sustentada por fuentes verificadas?"),
        "evidencia_habilitante": apoyos,
        "reasons": (["la evidencia de mercado se sostiene en " + ", ".join(sorted(set(apoyos)))
                     + " con procedencia completa"] if apoyos else
                    ["ninguna evidencia de mercado alcanza el estándar de fuente externa "
                     "verificada con procedencia completa", *bloqueos]),
        "blocking_conditions": bloqueos,
        "supporting_conditions": ([f"origen habilitante: {c}" for c in sorted(set(apoyos))]
                                  if apoyos else []),
        "insumos_no_habilitantes": obstaculos,
        "consecuencia_automatica": None,
        "nota": ("CLOSED aquí NO produce «NO EMITIR VALORACIÓN» por sí mismo: la "
                 "estimación se decide en ESTIMATION_GATE (§30)."),
    }


def _calidad_identidad(idn: Dict[str, Any]) -> Tuple[str, str]:
    if not isinstance(idn, dict) or not idn:
        return "ABSENT", "no se declaró el bloque de identidad"
    resuelta = bool(idn.get("resuelta") is True or idn.get("identity_verified") is True
                    or _norm_txt(idn.get("estado")) in ("RESUELTA", "VERIFIED", "VERIFICADA"))
    clas = clasificar_origen_extendido(dict(idn)) if (idn.get("origen_tipo")
                                                      or idn.get("origin")) else None
    if not resuelta:
        return "ABSENT", "identidad del inmueble NO resuelta"
    if clas and clas["clase"] in (am.ORIGEN_EXTERNO, am.ORIGEN_COMPUTADO):
        return "HIGH", f"identidad resuelta con origen {clas['clase']}"
    return "MEDIUM", "identidad resuelta sin origen declarado"


def _calidad_ubicacion(ub: Dict[str, Any]) -> Tuple[str, str]:
    if not isinstance(ub, dict) or not ub:
        return "ABSENT", "no se declaró el bloque de ubicación"
    estado = _norm_txt(ub.get("status") or ub.get("estado"))
    verificadas = {"VERIFIED_OFFICIAL", "VERIFIED_GEOGRAPHIC", "VERIFIED_CATASTRAL",
                   "OFFICIAL_PREDIO", "OFFICIAL_ADOPTION_ADDRESS_GEOCODE",
                   "CTL_ADDRESS_GEOCODE"}
    if estado in verificadas:
        return "HIGH", f"ubicación con estado {estado}"
    if ub.get("utilizable") is True or estado in ("UTILIZABLE", "RESOLVED"):
        return "MEDIUM", "ubicación utilizable pero NO verificada"
    return "ABSENT", "ubicación no utilizable"


def _calidad_area(ar: Dict[str, Any]) -> Tuple[str, str]:
    valor = _num((ar or {}).get("valor_m2") if isinstance(ar, dict) else ar)
    if valor is None:
        return "ABSENT", "área no declarada o no numérica"
    if not (5.0 <= valor <= 100_000.0):
        return "ABSENT", f"área fuera de rango utilizable ({valor:g} m²)"
    clas = clasificar_origen_extendido(dict(ar)) \
        if ((ar or {}).get("origen_tipo") or (ar or {}).get("origin")) else None
    if clas and clas["clase"] in (am.ORIGEN_EXTERNO, am.ORIGEN_COMPUTADO):
        return "HIGH", f"área declarada con origen {clas['clase']}"
    return "MEDIUM", "área declarada sin origen verificable"


def _calidad_tipologia(tp: Dict[str, Any]) -> Tuple[str, str]:
    valor = _norm_txt((tp or {}).get("valor") if isinstance(tp, dict) else tp)
    if not valor:
        return "ABSENT", "tipología no declarada"
    estado = _norm_txt((tp or {}).get("status")) if isinstance(tp, dict) else None
    if estado in ("VERIFIED_REGISTRAL", "VERIFIED_CATASTRAL"):
        return "HIGH", f"tipología verificada ({estado})"
    clas = clasificar_origen_extendido(dict(tp)) if isinstance(tp, dict) and (
        tp.get("origen_tipo") or tp.get("origin")) else None
    if clas and clas["clase"] in (am.ORIGEN_EXTERNO, am.ORIGEN_COMPUTADO):
        return "HIGH", f"tipología declarada con origen {clas['clase']}"
    return "MEDIUM", "tipología declarada sin verificación registral"


def _calidad_frescura(meses: Optional[int]) -> Tuple[str, str]:
    if meses is None:
        return "ABSENT", "sin fecha declarada en la evidencia de mercado"
    if meses <= 6:
        return "HIGH", f"evidencia de hace {meses} meses"
    if meses <= 12:
        return "MEDIUM", f"evidencia de hace {meses} meses"
    if meses <= 24:
        return "LOW", f"evidencia de hace {meses} meses"
    return "ABSENT", f"evidencia de hace {meses} meses (caducada para el estándar)"


def _calidad_dispersion(cv: Optional[float], n: int) -> Tuple[str, str]:
    if n < 2 or cv is None:
        return ("ABSENT", "dispersión no medible (menos de 2 comparables)") if n < 2 else \
            ("ABSENT", "dispersión no medible")
    if cv <= 0.08:
        return "HIGH", f"dispersión baja (cv = {cv:.3f})"
    if cv <= 0.15:
        return "MEDIUM", f"dispersión media (cv = {cv:.3f})"
    if cv <= 0.30:
        return "LOW", f"dispersión alta (cv = {cv:.3f})"
    return "ABSENT", f"dispersión muy alta (cv = {cv:.3f})"


def evaluar_evidence_quality(entrada: Dict[str, Any], *, criba: Optional[Dict[str, Any]] = None,
                             composicion: Optional[Dict[str, Any]] = None,
                             revision_modelo: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """`EVIDENCE_QUALITY_GATE` (§13/§14): nivel + razones + dimensiones. SIN score 0-100."""
    e = dict(entrada or {})
    hoy = e.get("_hoy") if isinstance(e.get("_hoy"), date) else date.today()
    composicion = composicion or componer_origen([])
    idn = e.get("identidad") if isinstance(e.get("identidad"), dict) else {}
    ub = e.get("ubicacion") if isinstance(e.get("ubicacion"), dict) else {}
    ar = e.get("area") if isinstance(e.get("area"), dict) else {"valor_m2": e.get("area_m2")}
    tp = e.get("tipologia") if isinstance(e.get("tipologia"), dict) else {"valor": e.get("tipologia")}
    tipologia = _norm_txt(tp.get("valor"))
    criba = criba if criba is not None else _cribar_comparables(
        e.get("comparables") or [], tipologia=tipologia, hoy=hoy)

    q_id, r_id = _calidad_identidad(idn)
    q_ub, r_ub = _calidad_ubicacion(ub)
    q_ar, r_ar = _calidad_area(ar)
    q_tp, r_tp = _calidad_tipologia(tp)
    q_fr, r_fr = _calidad_frescura(criba.get("frescura_meses"))
    n = len(criba["usados"])
    q_di, r_di = _calidad_dispersion(criba.get("dispersion_cv"), n)

    # Calidad de la evidencia de MERCADO (comparables) — §13.
    if n >= MIN_COMPARABLES_CALIDAD_ALTA and q_di == "HIGH" and q_fr in ("HIGH", "MEDIUM"):
        q_me = "HIGH"
    elif n >= MIN_COMPARABLES_CALIDAD_MEDIA and q_di in ("HIGH", "MEDIUM") and q_fr != "ABSENT":
        q_me = "MEDIUM"
    elif n >= MIN_COMPARABLES_M1:
        q_me = "LOW"
    elif e.get("estadisticas_externas") or composicion.get("sostiene_estimacion"):
        # Sin comparables observados, pero CON un soporte económico válido (estadística
        # agregada externa o modelo calibrado): hay base para una ESTIMACIÓN
        # INDICATIVA, no para evidencia de mercado de nivel medio.
        q_me = "LOW"
    else:
        q_me = "ABSENT"
    declarados = criba["declarados"]
    q_cq = ("HIGH" if declarados and n / declarados >= 0.9 else
            "MEDIUM" if declarados and n / declarados >= 0.5 else
            "LOW" if n else "ABSENT")

    # Calidad del MODELO: alta sólo si el contrato está completo y la muestra es amplia.
    rev = revision_modelo if revision_modelo is not None else (
        validar_modelo_calibrado(e.get("modelo_calibrado")) if e.get("modelo_calibrado")
        else {"valido": False, "motivos": ["sin modelo calibrado declarado"]})
    if e.get("modelo_calibrado"):
        q_mo = "HIGH" if rev.get("valido") and _num(
            (e.get("modelo_calibrado") or {}).get("sample_size")) and \
            float((e.get("modelo_calibrado") or {}).get("sample_size") or 0) >= 100 else \
            ("MEDIUM" if rev.get("valido") else "LOW")
    else:
        q_mo = "ABSENT"

    razones = [f"identidad: {q_id} — {r_id}", f"ubicación: {q_ub} — {r_ub}",
               f"área: {q_ar} — {r_ar}", f"tipología: {q_tp} — {r_tp}",
               f"evidencia de mercado: {q_me} — {n} comparables usados de {declarados}"
               + (f" · {len(e['estadisticas_externas'])} referencia(s) agregada(s) de "
                  f"nivel 3 (agregan por sector y banda de área: NO acreditan la unidad)"
                  if e.get("estadisticas_externas") else ""),
               f"vigencia: {q_fr} — {r_fr}", f"dispersión: {q_di} — {r_di}",
               f"modelo: {q_mo}"
               + ("" if q_mo == "ABSENT" else f" — {'; '.join(rev.get('motivos') or []) or 'contrato completo'}")]

    if not composicion.get("sostiene_estimacion"):
        nivel = QUALITY_INSUFFICIENT
        razones.append("sin soporte económico válido: la calidad es INSUFFICIENT")
    else:
        caps = {
            "identidad": CAP_DIMENSION[q_id],
            "ubicacion": CAP_DIMENSION[q_ub],
            "area": CAP_DIMENSION[q_ar],
            "tipologia": CAP_DIMENSION[q_tp],
            "mercado": CAP_DIMENSION.get(q_me, QUALITY_INSUFFICIENT),
            "composicion": composicion.get("techo_calidad", QUALITY_INSUFFICIENT),
        }
        nivel = _min_calidad(*caps.values())
        razones.append("techo por dimensión: "
                       + ", ".join(f"{k}={v}" for k, v in sorted(caps.items())))

    return {
        "gate": EVIDENCE_QUALITY_GATE, "level": nivel, "reasons": razones,
        "quality_version": EVIDENCE_QUALITY_VERSION,
        "identity_quality": q_id, "location_quality": q_ub,
        "market_evidence_quality": q_me, "market_freshness": {
            "level": q_fr, "meses": criba.get("frescura_meses"), "detalle": r_fr},
        "comparable_quality": q_cq, "comparable_count": n,
        "comparable_count_declarados": declarados,
        "typology_quality": q_tp, "area_quality": q_ar, "model_quality": q_mo,
        "dispersion": {"level": q_di, "cv": criba.get("dispersion_cv"), "n": n,
                       "detalle": r_di},
        "sin_score_publico": True,
        "nota": ("nivel cualitativo y razonado: NO se publica ningún score 0-100"),
    }


def _condiciones_estimacion(entrada: Dict[str, Any], *,
                            criba: Optional[Dict[str, Any]] = None,
                            composicion: Optional[Dict[str, Any]] = None,
                            resultados_metodos: Sequence[Dict[str, Any]] = ()) -> Dict[str, Any]:
    """§9/§10 · condiciones mínimas explícitas de la compuerta de estimación."""
    e = dict(entrada or {})
    hoy = e.get("_hoy") if isinstance(e.get("_hoy"), date) else date.today()
    idn = e.get("identidad") if isinstance(e.get("identidad"), dict) else {}
    ub = e.get("ubicacion") if isinstance(e.get("ubicacion"), dict) else {}
    ar = e.get("area") if isinstance(e.get("area"), dict) else {"valor_m2": e.get("area_m2")}
    tp = e.get("tipologia") if isinstance(e.get("tipologia"), dict) else {"valor": e.get("tipologia")}

    q_id, r_id = _calidad_identidad(idn)
    q_ub, r_ub = _calidad_ubicacion(ub)
    q_ar, r_ar = _calidad_area(ar)
    q_tp, r_tp = _calidad_tipologia(tp)
    cumplidas, faltantes = {}, {}

    cumplidas["IDENTIDAD_SUFICIENTEMENTE_RESUELTA"] = q_id in ("HIGH", "MEDIUM")
    faltantes["IDENTIDAD_SUFICIENTEMENTE_RESUELTA"] = r_id
    cumplidas["UBICACION_UTILIZABLE"] = q_ub in ("HIGH", "MEDIUM")
    faltantes["UBICACION_UTILIZABLE"] = r_ub
    cumplidas["AREA_UTILIZABLE"] = q_ar in ("HIGH", "MEDIUM")
    faltantes["AREA_UTILIZABLE"] = r_ar
    cumplidas["TIPOLOGIA_MINIMA"] = q_tp in ("HIGH", "MEDIUM")
    faltantes["TIPOLOGIA_MINIMA"] = r_tp

    composicion = composicion or componer_origen([])
    sostiene = bool(composicion.get("sostiene_estimacion"))
    clases_sostienen = [c for c in (composicion.get("clases_usadas") or [])
                        if c in SOPORTES_ECONOMICOS_VALIDOS]
    cumplidas["SOPORTE_ECONOMICO_VALIDO"] = sostiene and bool(clases_sostienen)
    faltantes["SOPORTE_ECONOMICO_VALIDO"] = (
        "soporte económico: " + ", ".join(sorted(set(clases_sostienen)))
        if cumplidas["SOPORTE_ECONOMICO_VALIDO"] else
        "sin soporte económico válido: MANUAL_CONFIG y el prior legacy NO cuentan; "
        "se exige comparable externo, estadística externa, modelo calibrado o combinación")

    bloqueos = [f"{k}: {v}" for k, v in faltantes.items() if not cumplidas[k]]
    apoyos = [f"{k}: {v}" for k, v in faltantes.items() if cumplidas[k]]
    return {"cumplidas": cumplidas, "detalle": faltantes, "blocking_conditions": bloqueos,
            "supporting_conditions": apoyos, "clases_que_sostienen": sorted(set(clases_sostienen))}


def evaluar_estimation_gate(entrada: Dict[str, Any], *, composicion: Optional[Dict[str, Any]] = None,
                            evidence_quality: Optional[Dict[str, Any]] = None,
                            resultados_metodos: Sequence[Dict[str, Any]] = (),
                            criba: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """`ESTIMATION_GATE` (§9/§10): ¿hay información suficiente para estimar?

    Estados CERRADOS: `OPEN` / `OPEN_WITH_LIMITATIONS` / `CLOSED`.

    Condiciones mínimas (`CONDITIONS_VERSION`): identidad suficientemente resuelta,
    ubicación utilizable, área utilizable, tipología mínima y ALGÚN soporte económico
    válido. `MANUAL_CONFIG` y `LEGACY_MODEL_PRIOR` NO cuentan como soporte.

    `OPEN` exige además una fuente de mercado con evidencia de calidad HIGH/MEDIUM y
    al menos `MIN_COMPARABLES_M1` comparables usados (o un modelo calibrado válido con
    identidad/área/ubicación verificadas en el caso indicativo). Todo lo demás es
    `OPEN_WITH_LIMITATIONS`. `CLOSED` es el ÚLTIMO recurso.
    """
    e = dict(entrada or {})
    hoy = e.get("_hoy") if isinstance(e.get("_hoy"), date) else date.today()
    composicion = composicion or componer_origen([])
    if evidence_quality is None:
        evidence_quality = evaluar_evidence_quality(e, criba=criba, composicion=composicion)
    cond = _condiciones_estimacion(e, criba=criba, composicion=composicion,
                                   resultados_metodos=resultados_metodos)
    nivel = evidence_quality.get("level", QUALITY_INSUFFICIENT)
    _ = hoy

    disponibles = sorted({r.get("method_id") for r in resultados_metodos
                          if r.get("status") in (STATUS_METHOD_AVAILABLE,
                                                 STATUS_METHOD_PARTIAL)})
    rechazados = sorted({r.get("method_id") for r in resultados_metodos
                         if r.get("status") in (STATUS_METHOD_NOT_APPLICABLE,
                                                STATUS_METHOD_INSUFFICIENT_DATA)})
    razones: List[str] = []
    if cond["blocking_conditions"]:
        estado = ESTIMATION_CLOSED
        razones = ["no se cumplen las condiciones mínimas de estimación:",
                   *cond["blocking_conditions"]]
        if not cond["cumplidas"]["SOPORTE_ECONOMICO_VALIDO"]:
            razones.append("MISSING_MARKET_EVIDENCE: no hay ninguna fuente de mercado "
                           "(comparables, referencias agregadas o modelo calibrado) que "
                           "pueda sostener una estimación")
            # §28/§29 · distinguir las DOS causas de cierre: falta de fuente automática
            # vs. que el único parámetro disponible sea un valor escrito a mano.
            if e.get("tasa_manual"):
                razones.append("CAUSA ADICIONAL distinta: la corrida SÍ declara un "
                               "parámetro de mercado, pero es MANUAL_CONFIG (escrito a "
                               "mano) y NO participa del cálculo ni puede sustituir a una "
                               "fuente")
            if e.get("modelo_legacy"):
                razones.append("CAUSA ADICIONAL distinta: la corrida declara el prior "
                               "legacy del modelo (LEGACY_MODEL_PRIOR), que se conserva "
                               "por compatibilidad y NO abre esta compuerta ni produce "
                               "cifra")
    elif not disponibles:
        estado = ESTIMATION_CLOSED
        razones = ["hay condiciones mínimas pero NINGÚN método pudo producir un resultado: "
                   "no se emite estimación",
                   *[f"{r.get('method_id')}: {r.get('reason')}" for r in resultados_metodos]]

    elif nivel in (QUALITY_HIGH, QUALITY_MEDIUM):
        estado = ESTIMATION_OPEN
        razones = [f"condiciones mínimas cumplidas y evidencia de calidad {nivel}",
                   f"soporte económico: {', '.join(cond['clases_que_sostienen'])}",
                   f"métodos disponibles: {', '.join(disponibles)}"]
        if composicion.get("origin") not in (am.ORIGEN_EXTERNO, am.ORIGEN_COMPUTADO):
            razones.append(f"el origen de la cifra es {composicion.get('origin')}: la "
                           f"evidencia de mercado verificada sigue su propia compuerta")
    else:
        estado = ESTIMATION_OPEN_WITH_LIMITATIONS
        razones = [f"hay información suficiente para una ESTIMACIÓN RAZONABLE, pero la "
                   f"evidencia es {nivel} (no alcanza el estándar verificado)",
                   f"soporte económico: {', '.join(cond['clases_que_sostienen'])}",
                   f"métodos disponibles: {', '.join(disponibles)} (ninguno autoriza una "
                   f"cifra verificada)"]
        if nivel == QUALITY_INDICATIVE:
            razones.append("el resultado se emite como ESTIMACIÓN INDICATIVA con sus "
                           "limitaciones declaradas, no como valor verificado")

    return {
        "gate": ESTIMATION_GATE, "gate_state": estado, "state": estado,
        "conditions_version": CONDITIONS_VERSION,
        "condiciones": cond["cumplidas"],
        "reasons": razones,
        "blocking_conditions": list(cond["blocking_conditions"]),
        "supporting_conditions": list(cond["supporting_conditions"]),
        "inputs_available": sorted({k for k, v in (e or {}).items()
                                    if v not in (None, "", [], {}) and not k.startswith("_")}),
        "inputs_missing": sorted({k for k in REGISTRO_INSUMOS
                                  if e.get(k) in (None, "", [], {})}),
        "methods_available": disponibles,
        "methods_rejected": rechazados,
        "evidence_quality": nivel,
        "composicion_origin": composicion.get("origin"),
    }


REGISTRO_INSUMOS = ("identidad", "ubicacion", "area", "tipologia", "comparables",
                    "estadisticas_externas", "modelo_calibrado", "referencia_estatica",
                    "tasa_manual", "modelo_legacy", "costo_reposicion", "rental_reference",
                    "cap_rate")


# ══════════════════════════════════════════════════════════════════════════════
# §11 · ESTIMATION RESULT
# ══════════════════════════════════════════════════════════════════════════════
def _fuentes_de(declaraciones: Iterable[Any]) -> List[Dict[str, Any]]:
    """Fuentes citadas (procedencia estructurada) — nunca una entidad no acreditada."""
    vistas: Dict[str, Dict[str, Any]] = {}
    for d in declaraciones:
        if not isinstance(d, dict):
            continue
        prov = d.get("provenance") or d.get("procedencia") or {}
        prov = prov if isinstance(prov, dict) else {}
        fuente = {"source_id": d.get("source_id") or prov.get("source_id"),
                  "proveedor": d.get("proveedor") or prov.get("proveedor")
                  or prov.get("entity") or prov.get("fuente"),
                  "referencia": d.get("referencia") or prov.get("referencia")
                  or prov.get("reference"),
                  "fecha": d.get("fecha") or prov.get("fecha"),
                  "sha256": d.get("sha256") or prov.get("sha256") or prov.get("hash")}
        if not any(v for v in fuente.values()):
            continue
        partes = [str(c) for c in (d.get("fuentes") or []) if isinstance(c, dict)]
        clave = json.dumps(fuente, sort_keys=True, default=str) + "|".join(partes)
        if clave in vistas:
            continue
        fuente["es_fuente_no_acreditada"] = am.contiene_atribucion_no_acreditada(
            fuente.get("proveedor"))
        vistas[clave] = fuente
    return list(vistas.values())


def _assumptions_y_limitaciones(composicion: Dict[str, Any], calidad: Dict[str, Any],
                                entrada: Dict[str, Any],
                                resultados: Sequence[Dict[str, Any]]) -> Tuple[List[str], List[str]]:
    supuestos = [
        "El rango es la salida primaria; la cifra central es secundaria y se redondea "
        "según el ancho del rango (§12).",
        "La estimación se apoya en " + METODOLOGIA_BASE + ".",
    ]
    limitaciones: List[str] = []
    if composicion.get("origin") == ORIGEN_COMPUTADO_CON_PRIOR:
        limitaciones.append("El cálculo incluye un modelo calibrado: el resultado no es "
                            "producto de fuentes verificadas y no supera INDICATIVE.")
    if composicion.get("origin") == ORIGEN_PRIOR_CALIBRADO:
        limitaciones.append("La base es un modelo calibrado sin comparables de mercado "
                            "observados en esta corrida.")
    if composicion.get("origin") == ORIGEN_COMPUTADO_CON_ESTATICA:
        limitaciones.append("Parte del cálculo se apoya en una referencia estática de bajo "
                            "peso, que por sí sola no sostiene ninguna cifra.")
    for clase in (composicion.get("clases_excluidas") or []):
        limitaciones.append(f"Insumo declarado y NO usado como fuente ({clase}): no "
                           f"participa del cálculo ni lo sostiene.")
    if (calidad.get("market_freshness") or {}).get("level") in ("LOW", "ABSENT"):
        limitaciones.append("La evidencia de mercado es antigua o no declara fecha: el "
                            "rango se amplía por ello (no se ajusta con índices inventados).")
    if (calidad.get("dispersion") or {}).get("level") in ("LOW", "ABSENT"):
        limitaciones.append("La dispersión de los comparables es alta o no medible.")
    if (calidad.get("comparable_count") or 0) < MIN_COMPARABLES_CALIDAD_MEDIA:
        limitaciones.append(f"Pocos comparables utilizables "
                            f"({calidad.get('comparable_count')}): muestra insuficiente "
                            f"para un estándar verificado.")
    for r in resultados:
        if r.get("status") in (STATUS_METHOD_NOT_APPLICABLE, STATUS_METHOD_INSUFFICIENT_DATA):
            limitaciones.append(f"{r.get('method_id')} no entró: {r.get('reason')}")
        for a in (r.get("adjustments") or []):
            if a.get("estado") == "NO_APLICADO":
                limitaciones.append(f"{r.get('method_id')} · {a.get('tipo')} NO aplicado: "
                                   f"{a.get('detalle')}")
    if not entrada.get("rental_reference"):
        limitaciones.append("Sin rental_reference: no se pudo contrastar por capitalización "
                            "de rentas (§20).")
    if not entrada.get("costo_reposicion"):
        limitaciones.append("Sin costo de reposición declarado: no se pudo contrastar por "
                            "costo de sustitución (§19).")
    return supuestos, limitaciones


def _evidencia_atribuible(evidencia: Sequence[Any]) -> Tuple[List[Any], List[Dict[str, Any]]]:
    """Separa lo que ACREDITA LA UNIDAD de lo que sólo la RODEA (nivel 3 agregado).

    §1 · la compuerta de evidencia verificada pregunta si la cifra puede tratarse como
    sustentada por fuentes verificadas **de esta unidad**. Una referencia de nivel 3
    agrega por localidad y banda de área: tiene procedencia completa, pero NO acredita la
    unidad, así que NO abre esa compuerta. Se devuelve aparte para poder DECLARARLO.

    Una declaración sin `nivel` declarado conserva el comportamiento anterior (no se
    degrada por lo que no declara): sólo el nivel 3 explícito se aparta.
    """
    atribuibles: List[Any] = []
    agregadas: List[Dict[str, Any]] = []
    for d in (evidencia or []):
        nivel = ""
        if isinstance(d, dict):
            nivel = str(d.get("nivel") or d.get("clasificacion_contrato") or "").upper()
        if nivel.startswith("LEVEL_3"):
            agregadas.append({"clase": ("LEVEL_3_AGGREGATED_MARKET_REFERENCES"),
                              "declarado": d.get("source_id") if isinstance(d, dict) else None,
                              "blockers": ["nivel 3 agrega por localidad y banda de área: "
                                           "NO acredita la unidad"]})
            continue
        atribuibles.append(d)
    return atribuibles, agregadas


def _redondear_borde(valor: float, semi: Optional[float], *, abajo: bool) -> int:
    """Redondeo de un BORDE del rango oficial: hacia FUERA, nunca hacia dentro.

    Redondear hacia dentro estrecharía la evidencia publicada por la fuente, que es lo
    único que el motor tiene. El paso lo impone el ancho (misma escala que la cifra).
    """
    paso = PRECISION_POR_ANCHO[-1][1]
    for umbral, p in PRECISION_POR_ANCHO:
        if (MAX_SEMI_ANCHO if semi is None else float(semi)) >= umbral:
            paso = p
            break
    if abajo:
        return int(math.floor(float(valor) / paso) * paso)
    return int(math.ceil(float(valor) / paso) * paso)


def estimar(entrada: Dict[str, Any], *, historico_forense: Optional[Dict[str, Any]] = None,
            razon_ancho_explicita: Optional[str] = None,
            generado_en: Optional[str] = None, moneda: str = "COP",
            hoy: Optional[date] = None) -> Dict[str, Any]:
    """ESTIMATION ENGINE — produce el `EstimationResult` (§11).

    ORDEN DE OPERACIONES (explícito, sin atajos):

      1. criba de comparables (procedencia, tipología, outlier) y métodos M1-M4;
      2. composición de `origin` sobre los insumos que SÍ participan del cálculo
         (los no habilitantes se declaran EXCLUIDOS, jamás contados como fuente);
      3. `VERIFIED_MARKET_EVIDENCE_GATE` (evidencia de mercado verificada);
      4. `EVIDENCE_QUALITY_GATE` (nivel y dimensiones);
      5. ancho de rango (§15) y su efecto sobre la calidad;
      6. `ESTIMATION_GATE` (§9/§10) → estado;
      7. `EstimationResult` con rango PRIMERO y cifra central derivada (§12).

    `historico_forense` NUNCA entra al cálculo: se copia tal cual en
    `historical_estimate_reference` con `usado_como_input = False` (§23).
    """
    e = dict(entrada or {})
    e["_hoy"] = hoy or _fecha(e.get("hoy")) or date.today()
    hoy_ = e["_hoy"]
    generado = generado_en or e.get("generado_en") or _ahora()
    tipologia = _norm_txt((e.get("tipologia") or {}).get("valor") if isinstance(e.get("tipologia"), dict)
                          else e.get("tipologia"))

    criba = _cribar_comparables(e.get("comparables") or [], tipologia=tipologia, hoy=hoy_)
    m1 = metodo_m1_comparacion_mercado(e, criba=criba)
    m2 = metodo_m2_costo_reposicion(e)
    m3 = metodo_m3_capitalizacion_rentas(e)
    m4 = metodo_m4_modelo_calibrado(e)
    m5 = metodo_m5_referencia_agregada(e)
    resultados = [m1, m2, m3, m4, m5]
    ensemble = ensamblar_metodos(resultados)

    # ── composición de origin: sólo lo que PARTICIPA del cálculo ──────────────
    usadas: List[Any] = []
    for c in criba["usados"]:
        usadas.append({"origen_tipo": c["origin"],
                       **{k: (c["provenance"] or {}).get(k) for k in am.PROCEDENCIA_EXTERNA},
                       "provenance": c["provenance"]})
    if m4["status"] == STATUS_METHOD_AVAILABLE and e.get("modelo_calibrado"):
        usadas.append({**dict(e["modelo_calibrado"]),
                       "origen_tipo": ORIGEN_PRIOR_CALIBRADO})
    if m3["status"] == STATUS_METHOD_AVAILABLE:
        for d in (e.get("rental_reference"), e.get("cap_rate")):
            if isinstance(d, dict):
                usadas.append(d)
    if m2["status"] == STATUS_METHOD_AVAILABLE and isinstance(e.get("costo_reposicion"), dict):
        usadas.append(dict(e["costo_reposicion"]))
    for est_externo in (e.get("estadisticas_externas") or []):
        usadas.append(est_externo)
    # Un modelo calibrado declarado con contrato INVÁLIDO no se honra: entra como
    # prior legacy (no productivo) para que su presencia sea visible y NO se lave.
    if e.get("modelo_calibrado") and m4["status"] != STATUS_METHOD_AVAILABLE:
        usadas.append({**dict(e["modelo_calibrado"]), "origen_tipo": ORIGEN_PRIOR_LEGACY})

    excluidas: List[Any] = []
    # La REFERENCIA ESTÁTICA es CONTEXTO de bajo peso, no insumo del cálculo: no entra
    # en la composición (no afecta ninguna cifra) y se declara EXCLUIDA con su motivo.
    if e.get("referencia_estatica"):
        excluidas.append({**({"origen_tipo": am.ORIGEN_ESTATICO}
                             if isinstance(e.get("referencia_estatica"), dict)
                             else {"valor": e.get("referencia_estatica")}),
                          **(dict(e["referencia_estatica"])
                             if isinstance(e.get("referencia_estatica"), dict) else {})})
    tm = e.get("tasa_manual")
    if tm:
        # Una tasa escrita a mano NO participa del cálculo y NO se cuenta como fuente:
        # se declara EXCLUIDA para que su presencia quede a la vista (§3, §11).
        excluidas.append({**({"origen_tipo": am.ORIGEN_MANUAL} if isinstance(tm, dict)
                             else {"valor": tm}),
                          **(dict(tm) if isinstance(tm, dict) else {})})
    ml = e.get("modelo_legacy")
    if ml:
        excluidas.append({**dict(ml), "origen_tipo": ORIGEN_PRIOR_LEGACY})

    composicion = componer_origen(usadas, excluidas=excluidas)

    # §1 · La compuerta de evidencia VERIFICADA sólo ve lo que acredita la UNIDAD: una
    # referencia de nivel 3 (agregada por localidad y banda de área) tiene procedencia
    # completa pero NO acredita la unidad, así que no la abre. Las dos compuertas
    # COEXISTEN, como exige el §30: `VERIFIED_MARKET_EVIDENCE_GATE = CLOSED` junto a
    # `ESTIMATION_GATE = OPEN_WITH_LIMITATIONS`.
    _atribuibles, _agregadas = _evidencia_atribuible(
        [{"origen_tipo": c["origin"], **{k: (c["provenance"] or {}).get(k)
                                         for k in am.PROCEDENCIA_EXTERNA},
          "provenance": c["provenance"]} for c in criba["usados"]]
        + list(e.get("estadisticas_externas") or []))
    verified = evaluar_verified_market_evidence_gate(_atribuibles)
    if _agregadas:
        verified["evidencia_agregada_no_atribuible"] = _agregadas
        verified["reasons"] = list(verified["reasons"]) + [
            "referencia de nivel 3 fuera de esta compuerta: " + a["blockers"][0]
            for a in _agregadas]
        verified["nota"] = (str(verified.get("nota") or "") + " Una referencia agregada "
                            "de nivel 3 sostiene una ESTIMACIÓN INDICATIVA (compuerta de "
                            "estimación), no un valor verificado de la unidad.")
    calidad = evaluar_evidence_quality(e, criba=criba, composicion=composicion)
    gate = evaluar_estimation_gate(e, composicion=composicion, evidence_quality=calidad,
                                   resultados_metodos=resultados, criba=criba)

    error_modelo = None
    if e.get("modelo_calibrado"):
        error_modelo = _num((e["modelo_calibrado"] or {}).get("calibration_error"))
    # §15/§22 · dispersión para el ancho: la de los comparables si existe; si NO hay
    # comparables pero sí una referencia AGREGADA, la incertidumbre que la propia banda
    # declarada implica (semi-amplitud relativa). Nunca se inventa un cv: o viene de los
    # comparables, o viene de la banda publicada, o no hay y el ancho declara «no medible».
    dispersion_ancho = criba.get("dispersion_cv")
    dispersion_origen = "comparables" if dispersion_ancho is not None else None
    if dispersion_ancho is None and m5.get("status") == STATUS_METHOD_AVAILABLE:
        dispersion_ancho = m5.get("dispersion_cv")
        dispersion_origen = METODO_M5
    ancho = ancho_de_rango(
        dispersion_cv=dispersion_ancho, comparables_usados=len(criba["usados"]),
        antiguedad_meses=criba.get("antiguedad_meses"), matching_quality=(
            (len(criba["usados"]) / criba["declarados"]) if criba["declarados"] else None),
        origen=composicion.get("origin"), error_modelo=error_modelo,
        evidence_quality=calidad["level"], razon_explicita=razon_ancho_explicita)
    if dispersion_origen:
        ancho["componentes"]["dispersion_origen"] = dispersion_origen
    # El ancho puede DEGRADAR la calidad efectiva: el resultado viaja coherente.
    calidad_final = dict(calidad)
    if ancho.get("calidad_efectiva") and ancho["calidad_efectiva"] != calidad["level"]:
        calidad_final["level"] = ancho["calidad_efectiva"]
        calidad_final["reasons"] = list(calidad["reasons"]) + [
            f"el ancho de rango exigió degradar la calidad a {ancho['calidad_efectiva']} "
            f"({ancho.get('porcentaje')})"]

    valor_m2 = ensemble.get("central_value_m2")
    ar_block = e.get("area") if isinstance(e.get("area"), dict) else {}
    area = _num(ar_block.get("valor_m2") if ar_block else e.get("area_m2"))
    semi = ancho.get("semi_ancho_relativo")
    # §29 · Si un método declara una banda OFICIAL (nivel 3), el rango de salida sale de
    # ESA banda aplicada al área del sujeto: el ancho calculado no puede estrechar la
    # evidencia publicada (sólo puede declarar más incertidumbre, nunca menos).
    _banda = next((r.get("banda_oficial") for r in resultados
                   if r.get("method_id") == METODO_M5
                   and r.get("status") == STATUS_METHOD_AVAILABLE
                   and r.get("banda_oficial")), None)
    central = low = high = v_lo = v_hi = v_central = None
    if valor_m2 is not None and area and semi:
        # §12 · RANGO PRIMERO: se calcula el rango, y la cifra central se redondea
        # con la precisión que el ancho permite (nunca más fina que la evidencia).
        v_central = round(valor_m2, 2)
        central = redondear_segun_evidencia(valor_m2 * area, semi)
        low_ancho = redondear_segun_evidencia(central * (1 - semi), semi)
        high_ancho = redondear_segun_evidencia(central * (1 + semi), semi)
        if _banda:
            low_oficial = _redondear_borde(_banda["min"] * area, semi, abajo=True)
            high_oficial = _redondear_borde(_banda["max"] * area, semi, abajo=False)
            low = min(low_ancho, low_oficial)
            high = max(high_ancho, high_oficial)
            ancho["banda_oficial_usada"] = {**_banda, "low_pesos": low, "high_pesos": high,
                                            "low_ancho": low_ancho, "high_ancho": high_ancho,
                                            "basis": ("min/max LITERALES de la fuente "
                                                      "aplicados al área del sujeto")}
            _semi_efectivo = ((high - low) / (2.0 * central)) if central else semi
            if _semi_efectivo > semi:
                ancho["motivos"] = list(ancho.get("motivos") or []) + [
                    f"el rango oficial de la fuente es más ancho (±{_semi_efectivo:.2%}) "
                    f"que el ancho calculado (±{semi:.2%}): el rango NO se estrecha por "
                    f"debajo de la evidencia publicada"]
            ancho["semi_ancho_calculado"] = semi
            ancho["semi_ancho_relativo"] = _semi_efectivo
            ancho["porcentaje"] = f"±{_semi_efectivo:.2%}"
            semi = _semi_efectivo
        else:
            low, high = low_ancho, high_ancho
        v_lo = round(valor_m2 * (1 - semi), 2)
        v_hi = round(valor_m2 * (1 + semi), 2)
    elif valor_m2 is not None:
        v_central = round(valor_m2, 2)

    # §5.4 · VISIBILIDAD de la referencia central: política explícita, versionada y
    # auditable. Poder calcular el punto medio de una banda NO obliga a publicarlo con
    # el mismo rango de voz que el rango. El estado viaja en el resultado Y dentro del
    # método M5 (`central_reference.visibility`).
    _muestra = m5.get("inputs", {}).get("sample_size") if isinstance(m5.get("inputs"),
                                                                    dict) else None
    visibilidad = politica_visibilidad_referencia_central(
        central=central, low=low, high=high, semi_ancho_relativo=semi,
        sample_size=_muestra,
        sample_size_declarado=(m5.get("inputs", {}) or {}).get("sample_size_declarado")
        if isinstance(m5.get("inputs"), dict) else None,
        comparables_usados=len(criba["usados"]), evidence_quality=calidad_final["level"],
        referencia_agregada_level_3=bool(
            _banda and m5.get("status") == STATUS_METHOD_AVAILABLE))
    if m5.get("status") == STATUS_METHOD_AVAILABLE:
        m5["central_reference"] = {**(m5.get("central_reference") or {}),
                                   "value_m2": v_central if v_central is not None
                                   else m5.get("central_reference", {}).get("value_m2"),
                                   "visibility": visibilidad["state"],
                                   "visibility_policy": {
                                       "policy_version": visibilidad["policy_version"],
                                       "imprime_la_cifra": visibilidad["imprime_la_cifra"],
                                       "reasons": list(visibilidad["reasons"]),
                                       "umbrales_aplicados": visibilidad["umbrales_aplicados"],
                                       "calibrada_empiricamente": False}}
        m5["central_reference_visibility"] = visibilidad

    # ── ESTADO (§11/§31): NOT_ESTIMABLE es el ÚLTIMO estado, no el de partida ──
    razones_confianza: List[str] = []
    if gate["gate_state"] == ESTIMATION_CLOSED or (central is None and low is None) \
            or calidad_final["level"] == QUALITY_INSUFFICIENT:
        status = STATUS_NOT_ESTIMABLE
        razones_confianza = list(gate["reasons"]) + [
            "no hay base mínima real para una estimación: no se emite ninguna cifra"]
    elif calidad_final["level"] == QUALITY_INDICATIVE:
        status = STATUS_INDICATIVE_ESTIMATE
        razones_confianza = [f"evidencia {calidad_final['level']}: la cifra es una "
                             f"ESTIMACIÓN INDICATIVA, no un valor verificado"]
    elif gate["gate_state"] == ESTIMATION_OPEN and verified["gate_state"] == VERIFIED_OPEN:
        status = STATUS_ESTIMATED
        razones_confianza = ["condiciones mínimas cumplidas con evidencia de mercado "
                             "verificada"]
    else:
        status = STATUS_ESTIMATED_WITH_LIMITATIONS
        razones_confianza = ["estimación disponible con limitaciones declaradas"]

    supuestos, limitaciones = _assumptions_y_limitaciones(composicion, calidad_final, e,
                                                         resultados)
    # §22 · Si la cifra se apoya en una referencia AGREGADA, la limitación va PRIMERO: es
    # la que el lector necesita para no leer el rango como un valor de SU unidad.
    if any(r.get("method_id") == METODO_M5 and r.get("status") == STATUS_METHOD_AVAILABLE
           for r in resultados):
        limitaciones.insert(0, (
            "La base es una referencia AGREGADA de nivel 3 (agrega por sector y banda de "
            "área): NO acredita la unidad. El rango es la salida y la referencia central "
            "es el centro de la banda declarada por la fuente, no un valor de mercado de "
            "esta unidad."))
    if status == STATUS_NOT_ESTIMABLE:
        central = low = high = v_lo = v_hi = None
        v_central = None
        # Sin cifra publicable la visibilidad es HIDDEN por definición (y se declara que
        # el motivo es que el motor no produjo rango, no una decisión de estilo).
        visibilidad = politica_visibilidad_referencia_central(
            central=None, low=None, high=None, semi_ancho_relativo=semi,
            sample_size=_muestra,
            sample_size_declarado=(m5.get("inputs", {}) or {}).get(
                "sample_size_declarado") if isinstance(m5.get("inputs"), dict) else None,
            comparables_usados=len(criba["usados"]),
            evidence_quality=calidad_final["level"],
            referencia_agregada_level_3=bool(
                _banda and m5.get("status") == STATUS_METHOD_AVAILABLE))
        if isinstance(m5.get("central_reference"), dict):
            m5["central_reference"] = {**m5["central_reference"],
                                       "visibility": visibilidad["state"],
                                       "visibility_policy": {
                                           "policy_version": visibilidad["policy_version"],
                                           "imprime_la_cifra":
                                               visibilidad["imprime_la_cifra"],
                                           "reasons": list(visibilidad["reasons"]),
                                           "umbrales_aplicados":
                                               visibilidad["umbrales_aplicados"],
                                           "calibrada_empiricamente": False}}
            m5["central_reference_visibility"] = visibilidad

    refs = [_evidencia("EV-ESTIMACION", METODOLOGIA_BASE, tipo="ESTIMATION", when=generado,
                       sha256=composicion.get("hash"),
                       detalle=f"composición {composicion.get('origin')}")]
    for c in criba["usados"]:
        refs.append(_evidencia(f"EV-CMP-{c['comparable_id']}",
                               str((c["provenance"] or {}).get("proveedor")
                                   or "fuente externa citada"),
                               tipo="MARKET_COMPARABLE",
                               when=(c["provenance"] or {}).get("fecha") or c.get("fecha"),
                               sha256=(c["provenance"] or {}).get("sha256"),
                               detalle=f"value_m2={c['value_m2']:.0f}"))
    fuentes = _fuentes_de([c["provenance"] for c in criba["usados"]]
                          + list(e.get("estadisticas_externas") or [])
                          + ([e["modelo_calibrado"]] if m4["status"] == STATUS_METHOD_AVAILABLE
                             else []))

    referencias_historicas = referencia_historica_forense(historico_forense)
    ids_usados = [x["method"] for x in ensemble["methods"] if x["weight_normalizado"] > 0]
    resultado = {
        "status": status,
        "status_label": vocabulario_economico(status),
        "central_estimate": central,
        "range_low": low,
        "range_high": high,
        "value_m2_central": v_central,
        "value_m2_low": v_lo,
        "value_m2_high": v_hi,
        "currency": moneda,
        "estimation_gate": gate,
        "evidence_quality": calidad_final,
        "verified_market_evidence_gate": verified,
        # `methods_used` / `methods_rejected` llevan el RESULTADO completo de cada
        # método; los pesos y su razón viven en `ensemble` (§21).
        "methods_used": [m for m in resultados if m["method_id"] in ids_usados],
        "methods_rejected": [m for m in resultados if m["method_id"] not in ids_usados],
        "methods_used_ids": ids_usados,
        "methods_rejected_ids": [m["method_id"] for m in resultados
                                 if m["method_id"] not in ids_usados],
        "ensemble": ensemble,
        "origin_composition": composicion,
        "origins": {"composicion": composicion.get("origin"),
                    "clases_usadas": composicion.get("clases_usadas"),
                    "clases_excluidas": composicion.get("clases_excluidas"),
                    "abre_verified_gate": composicion.get("abre_verified_gate")},
        "sources": fuentes,
        "inputs": {"area_m2": area, "tipologia": tipologia,
                   "comparables_declarados": criba["declarados"],
                   "comparables_usados": len(criba["usados"]),
                   "comparables_rechazados": criba["rechazados"],
                   "insumos_disponibles": sorted(
                       {k for k in REGISTRO_INSUMOS if e.get(k) not in (None, "", [], {})})},
        "assumptions": supuestos,
        "limitations": limitaciones,
        "confidence_label": calidad_final["level"],
        "confidence_reasons": razones_confianza,
        "generated_at": generado,
        "model_version": ESTIMATION_ENGINE_VERSION,
        "evidence_refs": refs,
        "range": {"low": low, "high": high, "semi_ancho_relativo": semi,
                  "porcentaje": ancho.get("porcentaje"),
                  "formula_version": ancho.get("formula_version"),
                  "componentes": ancho.get("componentes"),
                  "ajustes": ancho.get("ajustes"), "motivos": ancho.get("motivos"),
                  "clamp": ancho.get("clamp"), "banda_calidad": ancho.get("banda_calidad"),
                  # §29 · cuando el rango sale de una banda OFICIAL (nivel 3) se publica
                  # cuál, con sus min/max literales y los bordes ya redondeados.
                  "banda_oficial_usada": ancho.get("banda_oficial_usada")},
        # §5.4 · Política de visibilidad de la referencia central (versionada).
        "central_reference_visibility": visibilidad,
        "historical_estimate_reference": referencias_historicas,
        "gap_report": None if status != STATUS_NOT_ESTIMABLE else informe_de_brecha(e),
        "envelope": {
            "naturaleza": NATURALEZA_ESTIMACION,
            "es_valor_verificado": es_valor_verificado(status),
            "etiqueta_prohibida_usada": False,
            "vocabulario": VOCABULARIO_ECONOMICO,
            "metodologia": resumen_metodologico(),
        },
        "hash_payload": None,
    }
    resultado["hash_payload"] = _sha256({
        "status": status, "central": central, "low": low, "high": high,
        "gate": gate["gate_state"], "quality": calidad_final["level"],
        "origin": composicion.get("origin"), "model_version": ESTIMATION_ENGINE_VERSION,
    })
    return resultado


def validar_resultado(resultado: Dict[str, Any]) -> Dict[str, Any]:
    """Verificación del contrato `EstimationResult` (§11) y de las tres compuertas."""
    faltan = [c for c in CAMPOS_ESTIMATION_RESULT if c not in (resultado or {})]
    gate = (resultado or {}).get("estimation_gate") or {}
    faltan_gate = [c for c in CAMPOS_ESTIMATION_GATE if c not in gate]
    calidad = (resultado or {}).get("evidence_quality") or {}
    faltan_cal = [c for c in CAMPOS_EVIDENCE_QUALITY if c not in calidad]
    return {"campos_faltantes": faltan, "gate_campos_faltantes": faltan_gate,
            "quality_campos_faltantes": faltan_cal,
            "valido": not (faltan or faltan_gate or faltan_cal)}

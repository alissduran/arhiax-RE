"""ARHIAX RE — DICTUS ESTIMATION ENGINE v1.0 · FASE 1

CONTRATOS DE EVIDENCIA DE MERCADO. Este módulo **NO estima**: define la escalera de
evidencia, el contrato de observación de mercado, la puntuación explicable de
comparables, el control de outliers y el bloqueo POR PROPÓSITO. Nada de aquí emite una
cifra ni abre una compuerta.

Reglas duras que este módulo hace cumplir:

1. **Nunca se inventa un valor.** Todo campo desconocido viaja como ``None`` y se declara.
   Ningún campo se rellena por defecto, ni con ``0``, ni con un promedio, ni con un prior.
2. **``MANUAL_CONFIG`` y ``LEGACY_MODEL_PRIOR`` NO son soporte económico.** Un parámetro
   escrito a mano o un default codificado no sostienen una cifra (``origin_sostiene_estimacion``).
3. **La ausencia de LEVEL 1 NO implica CLOSED.** Que no haya comparables directos baja la
   calidad de la evidencia; no cierra por sí sola el juicio económico. Ver
   ``REGLA_AUSENCIA_LEVEL_1`` y ``evaluar_escalera``.
4. **Nada se excluye en silencio.** Todo comparable descartado viaja en
   ``excluded_comparables`` con ``exclusion_reason``.
5. **Ningún veredicto es un score arbitrario.** `ACCEPTED` / `WEAK` / `REJECTED` se
   derivan de reglas versionadas y cada comparable lleva su motivo explícito.

Este módulo es puro: no lee archivos, no consulta red y no depende de otros módulos de
`api/`. Los hechos reales se leen en `scripts/estimation_input_audit.py`.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from statistics import median
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

__all__ = [
    # versiones
    "VERSION_ESCALERA", "VERSION_OBSERVACION", "VERSION_REGLAS_COMPARABLE",
    "VERSION_CONTROL_OUTLIERS", "VERSION_BLOCKING_PROPOSITO",
    # escalera
    "LEVEL_1_DIRECT_COMPARABLES", "LEVEL_2_LOCAL_MARKET_OBSERVATIONS",
    "LEVEL_3_AGGREGATED_MARKET_REFERENCES", "LEVEL_4_CALIBRATED_MODEL_PRIOR",
    "LEVEL_5_STATIC_REFERENCE",
    "NIVELES_EVIDENCIA_MERCADO", "ORDEN_NIVEL", "NIVELES_QUE_SOSTIENEN_ESTIMACION",
    "DESCRIPCION_NIVELES", "REQUISITOS_NIVEL", "REGLA_AUSENCIA_LEVEL_1",
    "REGLA_NIVEL_5_NO_SOSTIENE",
    "es_nivel_valido", "nivel_referencia_de_origen", "nivel_de_observacion",
    "nivel_sostiene_estimacion", "evaluar_escalera",
    # orígenes
    "ORIGEN_EXTERNO", "ORIGEN_COMPUTADO", "ORIGEN_MANUAL", "ORIGEN_ESTATICO",
    "ORIGEN_PRIOR", "ORIGEN_LEGACY_PRIOR",
    "ORIGENES", "ORIGENES_HABILITANTES", "ORIGENES_NO_HABILITANTES",
    "origin_sostiene_estimacion",
    # contrato §6
    "CAMPOS_MARKET_OBSERVATION", "MarketObservation", "calcular_evidence_hash",
    "observaciones_desde_registros",
    # contrato §7
    "VEREDICTOS", "VEREDICTO_ACEPTADO", "VEREDICTO_DEBIL", "VEREDICTO_RECHAZADO",
    "ComparableScore", "evaluar_comparable", "similitud_localizacion",
    "similitud_area", "similitud_tipologia", "nivel_frescura",
    # control de outliers §8
    "CODIGOS_EXCLUSION", "detectar_outliers",
    # bloqueo por propósito §26
    "PROPOSITO_ESTIMACION", "PROPOSITO_DECISION", "ATRIBUTOS_BLOCKING",
    "DECLARACION_ALTURA_POT", "REGLA_POT_NO_BLOQUEA_ESTIMACION",
    "blocking_por_proposito", "requerido_para", "evaluar_blocking_por_proposito",
    "CAMPO_REQUERIDO_POR_PROPOSITO",
]


# ══════════════════════════════════════════════════════════════════════════════
# 0 · VERSIONES (todo contrato explícito viaja versionado)
# ══════════════════════════════════════════════════════════════════════════════
VERSION_ESCALERA = "market-evidence-ladder/1.0.0"
VERSION_OBSERVACION = "market-observation/1.0.0"
VERSION_REGLAS_COMPARABLE = "comparable-score/1.0.0"
VERSION_CONTROL_OUTLIERS = "comparable-outlier-control/1.0.0"
VERSION_BLOCKING_PROPOSITO = "blocking-por-proposito/1.0.0"


# ══════════════════════════════════════════════════════════════════════════════
# 1 · VOCABULARIO DE ORIGEN
# ══════════════════════════════════════════════════════════════════════════════
# Mismo vocabulario que `api/atribucion_mercado.py` (se replica aquí para que este
# módulo sea puro y no dependa de otro módulo al importarse).
ORIGEN_EXTERNO = "EXTERNAL_SOURCE"           # fuente externa identificable y citada
ORIGEN_COMPUTADO = "COMPUTED_FROM_SOURCES"   # derivado de >= 2 fuentes citadas
ORIGEN_MANUAL = "MANUAL_CONFIG"              # escrito/configurado a mano
ORIGEN_ESTATICO = "STATIC_REFERENCE"         # tabla/constante de referencia estática
ORIGEN_PRIOR = "MODEL_PRIOR"                 # default o fallback codificado
ORIGEN_LEGACY_PRIOR = "LEGACY_MODEL_PRIOR"   # prior heredado de corridas históricas

ORIGENES: Tuple[str, ...] = (
    ORIGEN_EXTERNO, ORIGEN_COMPUTADO, ORIGEN_MANUAL, ORIGEN_ESTATICO,
    ORIGEN_PRIOR, ORIGEN_LEGACY_PRIOR,
)

#: Sólo estos dos orígenes pueden sostener una afirmación económica.
ORIGENES_HABILITANTES = frozenset({ORIGEN_EXTERNO, ORIGEN_COMPUTADO})

#: Orígenes que NO son soporte económico. Se declaran, se trazan y NO habilitan.
ORIGENES_NO_HABILITANTES = frozenset(
    {ORIGEN_MANUAL, ORIGEN_ESTATICO, ORIGEN_PRIOR, ORIGEN_LEGACY_PRIOR})


def origin_sostiene_estimacion(origin: Optional[str]) -> bool:
    """¿Puede este origen sostener una cifra económica? (fail-closed)

    ``MANUAL_CONFIG``, ``STATIC_REFERENCE``, ``MODEL_PRIOR`` y ``LEGACY_MODEL_PRIOR``
    devuelven **False**: un valor escrito a mano o un default codificado no es una
    fuente. Un origen ausente o desconocido también devuelve False: no se asume.
    """
    return origin in ORIGENES_HABILITANTES


# ══════════════════════════════════════════════════════════════════════════════
# 2 · §5 · MARKET EVIDENCE LADDER
# ══════════════════════════════════════════════════════════════════════════════
LEVEL_1_DIRECT_COMPARABLES = "LEVEL_1_DIRECT_COMPARABLES"
LEVEL_2_LOCAL_MARKET_OBSERVATIONS = "LEVEL_2_LOCAL_MARKET_OBSERVATIONS"
LEVEL_3_AGGREGATED_MARKET_REFERENCES = "LEVEL_3_AGGREGATED_MARKET_REFERENCES"
LEVEL_4_CALIBRATED_MODEL_PRIOR = "LEVEL_4_CALIBRATED_MODEL_PRIOR"
LEVEL_5_STATIC_REFERENCE = "LEVEL_5_STATIC_REFERENCE"

#: La escalera, de mejor a peor. El orden importa: es el orden de descenso.
NIVELES_EVIDENCIA_MERCADO: Tuple[str, ...] = (
    LEVEL_1_DIRECT_COMPARABLES,
    LEVEL_2_LOCAL_MARKET_OBSERVATIONS,
    LEVEL_3_AGGREGATED_MARKET_REFERENCES,
    LEVEL_4_CALIBRATED_MODEL_PRIOR,
    LEVEL_5_STATIC_REFERENCE,
)

ORDEN_NIVEL: Dict[str, int] = {n: i + 1 for i, n in enumerate(NIVELES_EVIDENCIA_MERCADO)}

DESCRIPCION_NIVELES: Dict[str, str] = {
    LEVEL_1_DIRECT_COMPARABLES: (
        "Comparables directos: observaciones de inmuebles CONCRETOS y comparables con el "
        "sujeto (registro de listing o de transacción), con precio y área de la MISMA unidad "
        "observada. Es la única evidencia que sostiene una estimación por comparación de "
        "mercado sin apelar a agregados."),
    LEVEL_2_LOCAL_MARKET_OBSERVATIONS: (
        "Observaciones de mercado locales NO atadas a un inmueble comparable concreto: precio "
        "de unidades del mismo proyecto/constructora, cotizaciones de corredor del sector, "
        "precios pedidos de un grupo identificado de unidades del mismo edificio o manzana."),
    LEVEL_3_AGGREGATED_MARKET_REFERENCES: (
        "Referencias agregadas de mercado: valor por m² de un sector/barrio publicado con "
        "metodología declarada, muestra declarada y vigencia declarada (observatorios, "
        "índices, tablas institucionales). Agrega; no acredita una unidad."),
    LEVEL_4_CALIBRATED_MODEL_PRIOR: (
        "Prior del modelo CALIBRADO contra un dataset declarado: el parámetro se ajustó con "
        "datos y se puede exhibir el dataset, la fecha, el método de ajuste y la bondad. Un "
        "parámetro codificado sin calibración NO es este nivel."),
    LEVEL_5_STATIC_REFERENCE: (
        "Referencia estática: constante escrita en el código, tabla de referencia sin fuente, "
        "parámetro declarado a mano (MANUAL_CONFIG) o prior sin calibrar (MODEL_PRIOR / "
        "LEGACY_MODEL_PRIOR). Se declara para trazabilidad y NO sostiene ninguna cifra."),
}

REQUISITOS_NIVEL: Dict[str, Tuple[str, ...]] = {
    LEVEL_1_DIRECT_COMPARABLES: (
        "registro individual identificable (listing_or_record_id)",
        "precio observado (asking_price o transaction_price)",
        "área de la unidad observada (area_m2)",
        "origin habilitante (EXTERNAL_SOURCE o COMPUTED_FROM_SOURCES)",
    ),
    LEVEL_2_LOCAL_MARKET_OBSERVATIONS: (
        "precio observado del conjunto local",
        "sector o proyecto identificado",
        "origin habilitante",
    ),
    LEVEL_3_AGGREGATED_MARKET_REFERENCES: (
        "metodología declarada",
        "muestra declarada",
        "vigencia declarada",
        "origin habilitante",
    ),
    LEVEL_4_CALIBRATED_MODEL_PRIOR: (
        "dataset de calibración declarado",
        "fecha de calibración declarada",
        "método de ajuste declarado",
        "bondad de ajuste declarada",
    ),
    LEVEL_5_STATIC_REFERENCE: (),
}

#: Niveles que pueden sostener una cifra. El 4 sólo si está CALIBRADO; el 5 nunca.
NIVELES_QUE_SOSTIENEN_ESTIMACION = frozenset({
    LEVEL_1_DIRECT_COMPARABLES,
    LEVEL_2_LOCAL_MARKET_OBSERVATIONS,
    LEVEL_3_AGGREGATED_MARKET_REFERENCES,
})

#: Regla dura y explícita (§5). Esta frase es el contrato.
REGLA_AUSENCIA_LEVEL_1 = (
    "La ausencia de LEVEL 1 (comparables directos) NO implica CLOSED. No tener comparables "
    "directos degrada la CALIDAD de la evidencia y obliga a declarar el nivel realmente "
    "usado y su límite; no cierra por sí sola el juicio económico. Cerrar exige que falte "
    "TODO soporte utilizable (niveles 1 a 3) o que falte un atributo con "
    "required_for_estimation=True."
)

REGLA_NIVEL_5_NO_SOSTIENE = (
    "LEVEL 5 (referencia estática) NUNCA sostiene una cifra: se declara y se traza, pero no "
    "habilita la estimación. Lo mismo vale para MANUAL_CONFIG y LEGACY_MODEL_PRIOR."
)


def es_nivel_valido(nivel: Any) -> bool:
    """¿El valor pertenece al vocabulario cerrado de niveles?"""
    return isinstance(nivel, str) and nivel in NIVELES_EVIDENCIA_MERCADO


def nivel_sostiene_estimacion(nivel: Any, *, calibrado: bool = False,
                              dataset_declarado: Optional[Any] = None) -> bool:
    """¿Este nivel puede sostener económicamente una estimación?

    LEVEL 4 sólo sostiene si ``calibrado`` es True **y** hay ``dataset_declarado``. Sin
    calibración verificable, un prior del modelo es LEVEL 5 a efectos de soporte.
    """
    if nivel in NIVELES_QUE_SOSTIENEN_ESTIMACION:
        return True
    if nivel == LEVEL_4_CALIBRATED_MODEL_PRIOR:
        return bool(calibrado) and bool(dataset_declarado)
    return False


def nivel_referencia_de_origen(origin: Optional[str], *, agregado: bool = False,
                               calibrado: bool = False,
                               dataset_declarado: Optional[Any] = None,
                               metodologia_declarada: Optional[Any] = None) -> str:
    """Clasifica una REFERENCIA (no una observación) en un nivel de la escalera.

    Fail-closed y sin adornos: lo que no puede probarse como agregado con metodología o
    como prior calibrado con dataset baja a LEVEL 5. ``MANUAL_CONFIG``,
    ``STATIC_REFERENCE``, ``MODEL_PRIOR`` y ``LEGACY_MODEL_PRIOR`` son LEVEL 5 siempre.
    """
    if origin in ORIGENES_HABILITANTES:
        if calibrado and dataset_declarado:
            return LEVEL_4_CALIBRATED_MODEL_PRIOR
        if agregado and metodologia_declarada:
            return LEVEL_3_AGGREGATED_MARKET_REFERENCES
    return LEVEL_5_STATIC_REFERENCE


def nivel_de_observacion(obs: "MarketObservation") -> Optional[str]:
    """Nivel de una observación de mercado, o ``None`` si no puede afirmarse.

    No adivina: sin precio observado no hay observación de mercado que clasificar.
    """
    if not isinstance(obs, MarketObservation):
        raise TypeError("nivel_de_observacion exige un MarketObservation")
    if not origin_sostiene_estimacion(obs.origin):
        # Un registro con origen no habilitante es una referencia estática declarada.
        return LEVEL_5_STATIC_REFERENCE
    tiene_precio = obs.asking_price is not None or obs.transaction_price is not None
    if not tiene_precio:
        return None
    if obs.listing_or_record_id and obs.area_m2 is not None:
        return LEVEL_1_DIRECT_COMPARABLES
    return LEVEL_2_LOCAL_MARKET_OBSERVATIONS


def evaluar_escalera(niveles_disponibles: Iterable[Any], *,
                     calibracion: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """Estado de la evidencia de mercado a partir de los niveles realmente disponibles.

    Devuelve el mejor nivel, los niveles que sostienen estimación y —explícitamente— que
    la ausencia de LEVEL 1 **no** implica CLOSED.
    """
    pedidos = [n for n in niveles_disponibles if es_nivel_valido(n)]
    validos = sorted(set(pedidos), key=lambda n: ORDEN_NIVEL[n])
    calibracion = dict(calibracion or {})
    calibrado = bool(calibracion.get("calibrado"))
    dataset = calibracion.get("dataset_declarado")

    utilizables = [n for n in validos
                   if nivel_sostiene_estimacion(n, calibrado=calibrado,
                                                dataset_declarado=dataset)]

    sin_level_1 = LEVEL_1_DIRECT_COMPARABLES not in validos
    hay_soporte = bool(utilizables)
    # La única causa de CLOSED que este contrato admite es la ausencia TOTAL de soporte.
    cerrado_por_falta_de_soporte = not hay_soporte

    if not validos:
        lectura = ("No hay NINGUNA evidencia de mercado declarada: falta todo soporte "
                   "(niveles 1 a 3). Este es el único caso en que la falta de evidencia "
                   "de mercado cierra la estimación.")
    elif not hay_soporte:
        lectura = ("Sólo hay evidencia de nivel 5 (estática) o un prior no calibrado: se "
                   "declara y NO sostiene ninguna cifra. La estimación no puede emitirse "
                   "con soporte económico.")
    elif sin_level_1:
        lectura = ("No hay comparables directos (LEVEL 1): la evidencia baja de nivel. La "
                   "estimación NO queda cerrada por eso; se emite declarando el nivel usado "
                   "y su límite.")
    else:
        lectura = "Hay comparables directos (LEVEL 1): mejor evidencia disponible."

    return {
        "version_escalera": VERSION_ESCALERA,
        "niveles_disponibles": validos,
        "niveles_con_soporte": utilizables,
        "mejor_nivel": validos[0] if validos else None,
        "mejor_nivel_con_soporte": utilizables[0] if utilizables else None,
        "sin_level_1": sin_level_1,
        # Contrato duro: sin LEVEL 1 NO se cierra. Nunca True por esta causa.
        "implica_closed": False,
        "closed_por_ausencia_total_de_soporte": cerrado_por_falta_de_soporte,
        "regla_ausencia_level_1": REGLA_AUSENCIA_LEVEL_1,
        "regla_level_5": REGLA_NIVEL_5_NO_SOSTIENE,
        "calibracion": calibracion or None,
        "lectura": lectura,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 3 · §6 · CONTRATO MarketObservation
# ══════════════════════════════════════════════════════════════════════════════
#: Los 28 campos del contrato, en orden. Ni uno más, ni uno menos.
CAMPOS_MARKET_OBSERVATION: Tuple[str, ...] = (
    "observation_id", "source_id", "origin", "listing_or_record_id", "queried_at",
    "effective_date", "city", "neighborhood", "sector", "latitude", "longitude",
    "property_type", "regime", "area_m2", "bedrooms", "bathrooms", "parking", "estrato",
    "asking_price", "transaction_price", "price_per_m2", "distance_to_subject_m",
    "area_difference_pct", "typology_match", "location_match", "freshness_days",
    "source_reliability", "evidence_hash",
)

#: Campos de identidad: sin ellos no hay observación. No admiten None.
CAMPOS_IDENTIDAD: Tuple[str, ...] = ("observation_id", "source_id", "origin")

#: Campos numéricos que, si existen, deben ser estrictamente positivos.
CAMPOS_POSITIVOS: Tuple[str, ...] = (
    "area_m2", "asking_price", "transaction_price", "price_per_m2", "latitude",
    "longitude", "freshness_days",
)

#: Campos booleanos (nunca 0/1 disfrazado: True/False o None).
CAMPOS_BOOLEANOS: Tuple[str, ...] = ("typology_match", "location_match")


@dataclass
class MarketObservation:
    """Observación de mercado individual (§6).

    Todos los campos desconocidos van en ``None``. El constructor **no rellena nada**: no
    deriva ``price_per_m2``, no copia el sector del sujeto, no estima el área. Un dato que
    no se observó se declara ausente y así viaja.
    """

    observation_id: str
    source_id: str
    origin: str
    listing_or_record_id: Optional[str] = None
    queried_at: Optional[str] = None
    effective_date: Optional[str] = None
    city: Optional[str] = None
    neighborhood: Optional[str] = None
    sector: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    property_type: Optional[str] = None
    regime: Optional[str] = None
    area_m2: Optional[float] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    parking: Optional[int] = None
    estrato: Optional[str] = None
    asking_price: Optional[float] = None
    transaction_price: Optional[float] = None
    price_per_m2: Optional[float] = None
    distance_to_subject_m: Optional[float] = None
    area_difference_pct: Optional[float] = None
    typology_match: Optional[bool] = None
    location_match: Optional[bool] = None
    freshness_days: Optional[int] = None
    source_reliability: Optional[str] = None
    evidence_hash: Optional[str] = None

    # ── validación: lo inválido se rechaza, no se corrige en silencio ──────────
    def __post_init__(self) -> None:
        for campo in CAMPOS_IDENTIDAD:
            valor = getattr(self, campo)
            if not isinstance(valor, str) or not valor.strip():
                raise ValueError(
                    f"MarketObservation.{campo} es obligatorio y no puede quedar vacío: "
                    f"una observación sin identidad no es auditable")
        if self.origin not in ORIGENES:
            raise ValueError(
                f"MarketObservation.origin={self.origin!r} no pertenece al vocabulario "
                f"{ORIGENES}: un origen desconocido no se admite (fail-closed)")
        for campo in CAMPOS_POSITIVOS:
            valor = getattr(self, campo)
            if valor is None:
                continue
            if isinstance(valor, bool) or not isinstance(valor, (int, float)):
                raise ValueError(f"MarketObservation.{campo} debe ser numérico o None")
            if valor <= 0:
                raise ValueError(
                    f"MarketObservation.{campo}={valor!r} no es un valor observado válido: "
                    f"un no-dato no se representa con {valor!r} sino con None")
        for campo in CAMPOS_BOOLEANOS:
            valor = getattr(self, campo)
            if valor is not None and not isinstance(valor, bool):
                raise ValueError(
                    f"MarketObservation.{campo} debe ser True, False o None "
                    f"(y None NO significa False)")

    # ── lectura ───────────────────────────────────────────────────────────────
    def to_dict(self) -> Dict[str, Any]:
        """Dict con los 28 campos del contrato, desconocidos incluidos como None."""
        return {campo: getattr(self, campo) for campo in CAMPOS_MARKET_OBSERVATION}

    def campos_desconocidos(self) -> Tuple[str, ...]:
        """Campos que quedaron en None: se DECLARAN, no se disimulan."""
        return tuple(c for c in CAMPOS_MARKET_OBSERVATION if getattr(self, c) is None)

    def campos_conocidos(self) -> Tuple[str, ...]:
        return tuple(c for c in CAMPOS_MARKET_OBSERVATION if getattr(self, c) is not None)

    def nivel_evidencia(self) -> Optional[str]:
        return nivel_de_observacion(self)

    def con_evidence_hash(self) -> "MarketObservation":
        """Copia con el hash del propio registro calculado. No inventa el hash de otro."""
        if self.evidence_hash:
            return self
        return MarketObservation(**{**self.to_dict(),
                                    "evidence_hash": calcular_evidence_hash(self)})


def calcular_evidence_hash(obs: MarketObservation) -> str:
    """sha256 canónico de los campos CONOCIDOS de la observación.

    Es el hash del registro observado, no el de una fuente ajena: calcularlo no fabrica
    procedencia. ``evidence_hash`` se excluye del cálculo.
    """
    if not isinstance(obs, MarketObservation):
        raise TypeError("calcular_evidence_hash exige un MarketObservation")
    datos = {c: v for c, v in obs.to_dict().items()
             if c != "evidence_hash" and v is not None}
    canonico = json.dumps(datos, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), default=str)
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def observaciones_desde_registros(registros: Iterable[Mapping[str, Any]], *,
                                  source_id: str,
                                  origin: str) -> Tuple[MarketObservation, ...]:
    """Mapea registros crudos al contrato, SIN rellenar huecos.

    Una clave ausente en el registro queda en ``None``. Una clave presente con centinela
    textual de no-dato también queda en ``None``: un centinela no es un valor.
    """
    if origin not in ORIGENES:
        raise ValueError(f"origin={origin!r} no pertenece a {ORIGENES}")
    salida: List[MarketObservation] = []
    for i, registro in enumerate(registros):
        if not isinstance(registro, Mapping):
            raise TypeError("cada registro debe ser un mapping")
        oid = registro.get("observation_id") or f"{source_id}-{i + 1:04d}"
        datos: Dict[str, Any] = {"observation_id": str(oid),
                                 "source_id": source_id,
                                 "origin": origin}
        for campo in CAMPOS_MARKET_OBSERVATION:
            if campo in datos or campo not in registro:
                continue
            datos[campo] = _limpiar_centinela(registro[campo])
        salida.append(MarketObservation(**datos))
    return tuple(salida)


_CENTINELAS = frozenset({
    "", "n/a", "na", "n.d.", "nd", "no disponible", "sin dato", "sin datos",
    "sin informacion", "no aplica", "null", "none", "desconocido", "-",
})


def _limpiar_centinela(valor: Any) -> Any:
    """Un centinela de no-dato es un desconocido: viaja como None, nunca como texto."""
    if isinstance(valor, str) and valor.strip().lower() in _CENTINELAS:
        return None
    return valor


# ══════════════════════════════════════════════════════════════════════════════
# 4 · §7 · ComparableScore — reglas VERSIONADAS y explicables
# ══════════════════════════════════════════════════════════════════════════════
VEREDICTO_ACEPTADO = "ACCEPTED"
VEREDICTO_DEBIL = "WEAK"
VEREDICTO_RECHAZADO = "REJECTED"
VEREDICTOS: Tuple[str, ...] = (VEREDICTO_ACEPTADO, VEREDICTO_DEBIL, VEREDICTO_RECHAZADO)

# ── Umbrales declarados (parte de las reglas versionadas: cambiarlos cambia la versión) ──
UMBRAL_DISTANCIA_ALTA_M = 500.0
UMBRAL_DISTANCIA_MEDIA_M = 1500.0
UMBRAL_AREA_ALTA_PCT = 10.0
UMBRAL_AREA_MEDIA_PCT = 25.0
UMBRAL_FRESCURA_ALTA_DIAS = 90
UMBRAL_FRESCURA_MEDIA_DIAS = 180

SIMILITUD_ALTA = "ALTA"
SIMILITUD_MEDIA = "MEDIA"
SIMILITUD_BAJA = "BAJA"

#: Dimensiones CRÍTICAS: sin ellas conocidas y en ALTA no hay ACCEPTED.
DIMENSIONES_CRITICAS: Tuple[str, ...] = (
    "location_similarity", "area_similarity", "property_type_similarity",
    "regime_similarity", "freshness",
)

#: Dimensiones OPCIONALES: se puntúan SÓLO si se conocen y nunca deciden el veredicto.
DIMENSIONES_OPCIONALES: Tuple[str, ...] = (
    "parking_similarity", "floor_similarity", "condition_similarity",
)


@dataclass
class ComparableScore:
    """Puntuación explicable de un comparable (§7).

    No es un score numérico arbitrario: cada dimensión es una etiqueta derivada de una
    regla declarada, y el veredicto se decide por reglas explícitas sobre esas etiquetas.
    ``motivos`` lleva el POR QUÉ por comparable, con la regla que lo produjo.
    """

    comparable_id: str
    location_similarity: Optional[str] = None
    area_similarity: Optional[str] = None
    property_type_similarity: Optional[str] = None
    regime_similarity: Optional[str] = None
    freshness: Optional[str] = None
    parking_similarity: Optional[str] = None
    floor_similarity: Optional[str] = None
    condition_similarity: Optional[str] = None
    dimensiones_conocidas: Tuple[str, ...] = ()
    dimensiones_desconocidas: Tuple[str, ...] = ()
    veredicto: str = VEREDICTO_DEBIL
    motivos: List[Dict[str, Any]] = field(default_factory=list)
    version_reglas: str = VERSION_REGLAS_COMPARABLE

    def __post_init__(self) -> None:
        if self.veredicto not in VEREDICTOS:
            raise ValueError(f"veredicto={self.veredicto!r} no pertenece a {VEREDICTOS}")
        for dim in DIMENSIONES_CRITICAS + DIMENSIONES_OPCIONALES:
            valor = getattr(self, dim)
            if valor is not None and valor not in (SIMILITUD_ALTA, SIMILITUD_MEDIA,
                                                   SIMILITUD_BAJA):
                raise ValueError(f"{dim}={valor!r} no es una etiqueta de similitud válida")
        self.dimensiones_conocidas = tuple(self.dimensiones_conocidas)
        self.dimensiones_desconocidas = tuple(self.dimensiones_desconocidas)
        # Un veredicto sin motivo no es explicable: se prohíbe.
        if not self.motivos:
            raise ValueError(
                "ComparableScore exige al menos un motivo: un veredicto sin motivo "
                "explicable no es auditable")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "comparable_id": self.comparable_id,
            "location_similarity": self.location_similarity,
            "area_similarity": self.area_similarity,
            "property_type_similarity": self.property_type_similarity,
            "regime_similarity": self.regime_similarity,
            "freshness": self.freshness,
            "parking_similarity": self.parking_similarity,
            "floor_similarity": self.floor_similarity,
            "condition_similarity": self.condition_similarity,
            "dimensiones_conocidas": list(self.dimensiones_conocidas),
            "dimensiones_desconocidas": list(self.dimensiones_desconocidas),
            "veredicto": self.veredicto,
            "motivos": list(self.motivos),
            "version_reglas": self.version_reglas,
        }


def similitud_localizacion(distance_to_subject_m: Optional[float], *,
                           same_sector: Optional[bool] = None,
                           location_match: Optional[bool] = None) -> Optional[str]:
    """Similaridad de ubicación. Sin dato de distancia NI sector declarado → None."""
    if location_match is False or same_sector is False:
        return SIMILITUD_BAJA
    if distance_to_subject_m is not None:
        if distance_to_subject_m <= UMBRAL_DISTANCIA_ALTA_M:
            return SIMILITUD_ALTA
        if distance_to_subject_m <= UMBRAL_DISTANCIA_MEDIA_M:
            return SIMILITUD_MEDIA
        return SIMILITUD_BAJA
    if same_sector is True or location_match is True:
        return SIMILITUD_MEDIA
    return None


def similitud_area(area_difference_pct: Optional[float]) -> Optional[str]:
    """Similaridad de área por DIFERENCIA RELATIVA declarada (nunca por el área absoluta)."""
    if area_difference_pct is None:
        return None
    try:
        diferencia = abs(float(area_difference_pct))
    except (TypeError, ValueError):
        return None
    if diferencia <= UMBRAL_AREA_ALTA_PCT:
        return SIMILITUD_ALTA
    if diferencia <= UMBRAL_AREA_MEDIA_PCT:
        return SIMILITUD_MEDIA
    return SIMILITUD_BAJA


def similitud_tipologia(typology_match: Optional[bool]) -> Optional[str]:
    """`None` (desconocido) NO es un desajuste y NO es una coincidencia."""
    if typology_match is None:
        return None
    return SIMILITUD_ALTA if typology_match else SIMILITUD_BAJA


def similitud_regimen(regime: Optional[str], regime_sujeto: Optional[str]) -> Optional[str]:
    """Régimen comparable, normalizado. Sin alguno de los dos → None (no se asume)."""
    a, b = _norm(regime), _norm(regime_sujeto)
    if not a or not b:
        return None
    return SIMILITUD_ALTA if a == b else SIMILITUD_BAJA


def nivel_frescura(freshness_days: Optional[int]) -> Optional[str]:
    """Frescura del dato. Sin antigüedad declarada → None (no se presume reciente)."""
    if freshness_days is None:
        return None
    if freshness_days <= UMBRAL_FRESCURA_ALTA_DIAS:
        return SIMILITUD_ALTA
    if freshness_days <= UMBRAL_FRESCURA_MEDIA_DIAS:
        return SIMILITUD_MEDIA
    return SIMILITUD_BAJA


def _norm(valor: Any) -> str:
    return str(valor or "").strip().lower()


def evaluar_comparable(obs: MarketObservation, *,
                       regime_sujeto: Optional[str] = None,
                       sector_sujeto: Optional[str] = None,
                       tipologia_sujeto: Optional[str] = None,
                       floor: Optional[Any] = None,
                       condition: Optional[Any] = None) -> ComparableScore:
    """Puntúa un comparable con reglas declaradas y devuelve su motivo.

    Reglas de decisión (orden estricto, sin pesos arbitrarios):

    1. Tipo de inmueble distinto, sector distinto o régimen distinto → ``REJECTED``.
    2. Alguna dimensión crítica en ``BAJA`` → ``REJECTED``.
    3. Todas las críticas conocidas y en ``ALTA`` → ``ACCEPTED``.
    4. Cualquier otro caso (crítica en ``MEDIA`` o desconocida) → ``WEAK``.

    ``parking``/``floor``/``condition`` se puntúan **sólo si se conocen** y nunca cambian
    el veredicto: se registran como contexto explicativo.
    """
    if not isinstance(obs, MarketObservation):
        raise TypeError("evaluar_comparable exige un MarketObservation")

    motivos: List[Dict[str, Any]] = []

    same_sector = None
    if obs.sector is not None and sector_sujeto is not None:
        same_sector = _norm(obs.sector) == _norm(sector_sujeto)

    loc = similitud_localizacion(obs.distance_to_subject_m, same_sector=same_sector,
                                 location_match=obs.location_match)
    area = similitud_area(obs.area_difference_pct)
    tipo = similitud_tipologia(obs.typology_match)
    regimen = similitud_regimen(obs.regime, regime_sujeto)
    frescura = nivel_frescura(obs.freshness_days)

    valores = {
        "location_similarity": loc,
        "area_similarity": area,
        "property_type_similarity": tipo,
        "regime_similarity": regimen,
        "freshness": frescura,
    }
    conocidas = tuple(d for d in DIMENSIONES_CRITICAS if valores[d] is not None)
    desconocidas = tuple(d for d in DIMENSIONES_CRITICAS if valores[d] is None)

    # ── dimensión por dimensión, con la regla que la produjo ──────────────────
    reglas_dim = {
        "location_similarity": "distancia/sector declarado vs sujeto",
        "area_similarity": "diferencia relativa de área declarada",
        "property_type_similarity": "typology_match declarado",
        "regime_similarity": "régimen normalizado vs régimen del sujeto",
        "freshness": "antigüedad declarada del dato",
    }
    for dim in DIMENSIONES_CRITICAS:
        motivos.append({
            "regla": reglas_dim[dim],
            "dimension": dim,
            "resultado": valores[dim] if valores[dim] is not None else "DESCONOCIDO",
            "detalle": ("dato observado" if valores[dim] is not None
                        else "el dato no se observó: no se asume coincidencia"),
        })

    # ── opcionales: sólo si se conocen, nunca deciden ─────────────────────────
    parking = None
    if obs.parking is not None:
        parking = SIMILITUD_ALTA if obs.parking and obs.parking > 0 else SIMILITUD_BAJA
        motivos.append({"regla": "parqueadero declarado en el registro",
                        "dimension": "parking_similarity", "resultado": parking,
                        "detalle": "contexto: no decide el veredicto"})
    floor_sim, cond_sim = None, None
    if floor is not None:
        floor_sim = SIMILITUD_ALTA  # se declara el piso; la regla de contraste llega en F2
        motivos.append({"regla": "piso declarado", "dimension": "floor_similarity",
                        "resultado": floor_sim,
                        "detalle": "contexto: no decide el veredicto"})
    if condition is not None:
        cond_sim = SIMILITUD_ALTA
        motivos.append({"regla": "estado de conservación declarado",
                        "dimension": "condition_similarity", "resultado": cond_sim,
                        "detalle": "contexto: no decide el veredicto"})

    # ── veredicto por reglas explícitas ───────────────────────────────────────
    disqualificadores: List[str] = []
    if tipo == SIMILITUD_BAJA:
        disqualificadores.append("tipología distinta a la del sujeto")
    if loc == SIMILITUD_BAJA:
        disqualificadores.append("ubicación fuera del sector o fuera del umbral admitido")
    if regimen == SIMILITUD_BAJA:
        disqualificadores.append("régimen jurídico distinto al del sujeto")
    bajas_criticas = [d for d in DIMENSIONES_CRITICAS
                      if valores[d] == SIMILITUD_BAJA and d not in (
                          "property_type_similarity", "location_similarity",
                          "regime_similarity")]
    if bajas_criticas:
        disqualificadores.extend(f"{d} en BAJA" for d in bajas_criticas)

    if disqualificadores:
        veredicto = VEREDICTO_RECHAZADO
        motivos.append({"regla": "regla de rechazo (tipo/ubicación/régimen o crítica en BAJA)",
                        "resultado": VEREDICTO_RECHAZADO,
                        "detalle": "; ".join(disqualificadores)})
    elif desconocidas:
        veredicto = VEREDICTO_DEBIL
        motivos.append({
            "regla": "no se acepta con dimensiones críticas desconocidas",
            "resultado": VEREDICTO_DEBIL,
            "detalle": ("desconocidas: " + ", ".join(desconocidas)
                        + " — un desconocido no se presume coincidente")})
    elif all(valores[d] == SIMILITUD_ALTA for d in DIMENSIONES_CRITICAS):
        veredicto = VEREDICTO_ACEPTADO
        motivos.append({
            "regla": "todas las dimensiones críticas conocidas y en ALTA",
            "resultado": VEREDICTO_ACEPTADO,
            "detalle": "comparable aceptado para comparación directa"})
    else:
        veredicto = VEREDICTO_DEBIL
        medias = [d for d in DIMENSIONES_CRITICAS if valores[d] == SIMILITUD_MEDIA]
        motivos.append({
            "regla": "alguna dimensión crítica en MEDIA",
            "resultado": VEREDICTO_DEBIL,
            "detalle": "en MEDIA: " + ", ".join(medias)})

    return ComparableScore(
        comparable_id=obs.observation_id,
        location_similarity=loc, area_similarity=area,
        property_type_similarity=tipo, regime_similarity=regimen, freshness=frescura,
        parking_similarity=parking, floor_similarity=floor_sim,
        condition_similarity=cond_sim,
        dimensiones_conocidas=conocidas, dimensiones_desconocidas=desconocidas,
        veredicto=veredicto, motivos=motivos, version_reglas=VERSION_REGLAS_COMPARABLE)


# ══════════════════════════════════════════════════════════════════════════════
# 5 · §8 · CONTROL DE OUTLIERS — nada se borra en silencio
# ══════════════════════════════════════════════════════════════════════════════
EXCLUSION_PRECIO_M2_EXTREMO = "PRECIO_M2_EXTREMO"
EXCLUSION_PRECIO_M2_INCOMPATIBLE = "PRECIO_M2_INCOMPATIBLE"
EXCLUSION_AREA_INCOMPATIBLE = "AREA_INCOMPATIBLE"
EXCLUSION_TIPOLOGIA_DISTINTA = "TIPOLOGIA_DISTINTA"
EXCLUSION_SECTOR_INCORRECTO = "SECTOR_INCORRECTO"
EXCLUSION_DUPLICADO = "DUPLICADO"
EXCLUSION_DATO_VENCIDO = "DATO_VENCIDO"
EXCLUSION_SIN_PRECIO = "SIN_PRECIO_OBSERVADO"

CODIGOS_EXCLUSION: Tuple[str, ...] = (
    EXCLUSION_PRECIO_M2_EXTREMO, EXCLUSION_PRECIO_M2_INCOMPATIBLE,
    EXCLUSION_AREA_INCOMPATIBLE, EXCLUSION_TIPOLOGIA_DISTINTA,
    EXCLUSION_SECTOR_INCORRECTO, EXCLUSION_DUPLICADO, EXCLUSION_DATO_VENCIDO,
    EXCLUSION_SIN_PRECIO,
)

#: Umbral duro de área: por encima, el comparable no es el mismo producto.
UMBRAL_AREA_INCOMPATIBLE_PCT = 40.0
#: Umbral duro de antigüedad: por encima, el dato no representa el mercado actual.
UMBRAL_FRESCURA_VENCIDA_DIAS = 365
#: Desvío relativo admitido frente a la mediana (regla robusta, sólo sin banda declarada).
FACTOR_DESVIO_ROBUSTO = 3.0
#: Mínimo de observaciones con precio para poder usar la regla robusta.
MINIMO_PARA_REGLA_ROBUSTA = 3


def detectar_outliers(observaciones: Sequence[MarketObservation], *,
                      sector_sujeto: Optional[str] = None,
                      banda_m2: Optional[Sequence[float]] = None,
                      banda_origen: Optional[str] = None,
                      reglas: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """Separa comparables utilizables de excluidos, SIEMPRE con motivo declarado.

    Comprueba: precio/m² extremo, área incompatible, tipología distinta, sector
    incorrecto, duplicados y datos vencidos. Devuelve ``aceptadas`` **y**
    ``excluidas``; la suma siempre reconstruye la entrada, de modo que ninguna
    observación desaparece sin constancia (no hay borrado silencioso).

    ``banda_m2`` es la banda de referencia DECLARADA (si existe). Sin banda, se usa una
    regla robusta sobre la mediana y se dice explícitamente cuál se aplicó.
    """
    if not isinstance(observaciones, (list, tuple)):
        raise TypeError("detectar_outliers exige una secuencia de MarketObservation")
    obs = list(observaciones)
    for o in obs:
        if not isinstance(o, MarketObservation):
            raise TypeError("cada elemento debe ser un MarketObservation")

    umbral_area = float((reglas or {}).get("umbral_area_incompatible_pct",
                                           UMBRAL_AREA_INCOMPATIBLE_PCT))
    umbral_vencido = int((reglas or {}).get("umbral_frescura_vencida_dias",
                                            UMBRAL_FRESCURA_VENCIDA_DIAS))
    factor = float((reglas or {}).get("factor_desvio_robusto", FACTOR_DESVIO_ROBUSTO))

    # ── regla de precio: banda declarada si la hay; si no, mediana robusta ────
    banda = None
    if banda_m2 is not None:
        valores_banda = [float(v) for v in banda_m2]
        if len(valores_banda) != 2:
            raise ValueError("banda_m2 debe ser [min, max]")
        banda = (min(valores_banda), max(valores_banda))
    precios = [o.price_per_m2 for o in obs if o.price_per_m2 is not None]
    mediana = median(precios) if precios else None
    if banda is not None:
        metodo_precio = "BANDA_DECLARADA"
    elif mediana is not None and len(precios) >= MINIMO_PARA_REGLA_ROBUSTA:
        metodo_precio = "MEDIANA_ROBUSTA"
    else:
        metodo_precio = "SIN_REGLA_DE_PRECIO"

    def _fuera_de_precio(precio: Optional[float]) -> Optional[Tuple[str, str]]:
        if precio is None:
            return None
        if banda is not None:
            if precio < banda[0] or precio > banda[1]:
                return (EXCLUSION_PRECIO_M2_INCOMPATIBLE,
                        f"precio/m² {precio} fuera de la banda declarada "
                        f"[{banda[0]}, {banda[1]}]"
                        + (f" (origen de la banda: {banda_origen})" if banda_origen else ""))
            return None
        if metodo_precio == "MEDIANA_ROBUSTA" and mediana:
            if precio > mediana * factor:
                return (EXCLUSION_PRECIO_M2_EXTREMO,
                        f"precio/m² {precio} supera {factor}× la mediana ({mediana})")
            if precio < mediana / factor:
                return (EXCLUSION_PRECIO_M2_EXTREMO,
                        f"precio/m² {precio} queda bajo la mediana/{factor} ({mediana})")
        return None

    aceptadas: List[MarketObservation] = []
    excluidas: List[Dict[str, Any]] = []
    vistos: Dict[Tuple[str, ...], str] = {}      # clave de duplicado -> id conservado

    for o in obs:
        codigos: List[Tuple[str, str]] = []

        # 1 · duplicado (por clave de registro y por hash de contenido)
        claves: List[Tuple[str, ...]] = []
        if o.listing_or_record_id:
            claves.append(("registro", o.source_id, str(o.listing_or_record_id)))
        if o.evidence_hash:
            claves.append(("hash", str(o.evidence_hash)))
        duplica_a = None
        for clave in claves:
            if clave in vistos:
                duplica_a = vistos[clave]
                codigos.append((EXCLUSION_DUPLICADO,
                                f"duplica a {duplica_a} (misma clave {clave[0]})"))
                break

        # 2 · sin precio observado: no hay comparable que comparar (pero se conserva)
        if o.asking_price is None and o.transaction_price is None and o.price_per_m2 is None:
            codigos.append((EXCLUSION_SIN_PRECIO,
                            "no declara asking_price, transaction_price ni price_per_m2"))

        # 3 · precio/m² extremo o fuera de banda
        fuera = _fuera_de_precio(o.price_per_m2)
        if fuera:
            codigos.append(fuera)

        # 4 · área incompatible
        if o.area_difference_pct is not None and abs(o.area_difference_pct) > umbral_area:
            codigos.append((EXCLUSION_AREA_INCOMPATIBLE,
                            f"diferencia de área |{o.area_difference_pct}%| > {umbral_area}%"))

        # 5 · tipología distinta
        if o.typology_match is False:
            codigos.append((EXCLUSION_TIPOLOGIA_DISTINTA,
                            "typology_match=False: no es la misma tipología"))

        # 6 · sector incorrecto
        if o.location_match is False:
            codigos.append((EXCLUSION_SECTOR_INCORRECTO,
                            "location_match=False: no está en la ubicación del sujeto"))
        elif sector_sujeto and o.sector and _norm(o.sector) != _norm(sector_sujeto):
            codigos.append((EXCLUSION_SECTOR_INCORRECTO,
                            f"sector observado {o.sector!r} ≠ sector del sujeto "
                            f"{sector_sujeto!r}"))

        # 7 · dato vencido
        if o.freshness_days is not None and o.freshness_days > umbral_vencido:
            codigos.append((EXCLUSION_DATO_VENCIDO,
                            f"antigüedad {o.freshness_days} d > {umbral_vencido} d"))

        if codigos:
            excluidas.append({
                "observation_id": o.observation_id,
                "source_id": o.source_id,
                "origin": o.origin,
                "price_per_m2": o.price_per_m2,
                "exclusion_reason": "; ".join(f"[{c}] {m}" for c, m in codigos),
                "exclusion_codes": [c for c, _ in codigos],
                "duplica_a": duplica_a,
                "conservada_para_auditoria": True,
            })
            continue

        aceptadas.append(o)
        for clave in claves:
            vistos.setdefault(clave, o.observation_id)

    return {
        "version_reglas": VERSION_CONTROL_OUTLIERS,
        "aceptadas": aceptadas,
        "excluidas": excluidas,
        "excluded_comparables": excluidas,     # nombre del contrato §8
        "total_entrada": len(obs),
        "total_aceptadas": len(aceptadas),
        "total_excluidas": len(excluidas),
        "integridad": len(aceptadas) + len(excluidas) == len(obs),
        "metodo_precio": metodo_precio,
        "banda_declarada_m2": list(banda) if banda else None,
        "banda_origen": banda_origen if banda else None,
        "umbral_area_incompatible_pct": umbral_area,
        "umbral_frescura_vencida_dias": umbral_vencido,
        "declaracion": ("Ninguna observación se elimina en silencio: toda exclusión viaja "
                        "en `excluded_comparables` con `exclusion_reason` y su código."),
    }


# ══════════════════════════════════════════════════════════════════════════════
# 6 · §26 · BLOQUEO POR PROPÓSITO — `required_for_estimation` ≠ `required_for_decision`
# ══════════════════════════════════════════════════════════════════════════════
PROPOSITO_ESTIMACION = "ESTIMACION"
PROPOSITO_DECISION = "DECISION"
PROPOSITOS: Tuple[str, ...] = (PROPOSITO_ESTIMACION, PROPOSITO_DECISION)

DECLARACION_ALTURA_POT = (
    "La altura máxima POT puede ser CRÍTICA para urbanismo (uso, edificabilidad, "
    "viabilidad de intervención) y NO es necesariamente necesaria para ESTIMAR el valor "
    "de mercado de una UNIDAD PH ya construida: la unidad ya existe, tiene área privada y "
    "régimen propios. Por eso required_for_decision=True y required_for_estimation=False. "
    "Mezclar ambos propósitos bloquearía la estimación por un dato que no la sostiene."
)

REGLA_POT_NO_BLOQUEA_ESTIMACION = (
    "`SOURCE_UNAVAILABLE` en POT/altura/tratamiento/edificabilidad/uso NO bloquea por sí "
    "solo la ESTIMACIÓN económica: degrada el semáforo urbanístico de la DECISIÓN y se "
    "declara como tal. Para bloquear la estimación tiene que faltar un atributo con "
    "`required_for_estimation=True` (área, tipología, régimen, ubicación, o el propio "
    "soporte de mercado)."
)

#: Tabla de bloqueo por propósito. Cada atributo declara si es exigible para ESTIMAR y si
#: lo es para DECIDIR, con el motivo de la diferencia cuando existe.
ATRIBUTOS_BLOCKING: Dict[str, Dict[str, Any]] = {
    "identidad_unidad": {
        "required_for_estimation": True, "required_for_decision": True,
        "motivo": "Sin unidad identificada no se sabe QUÉ se estima.",
    },
    "matricula": {
        "required_for_estimation": False, "required_for_decision": True,
        "motivo": ("Vincula el informe al folio correcto; no altera el valor de mercado "
                   "de una unidad ya identificada."),
    },
    "nupre": {
        "required_for_estimation": False, "required_for_decision": True,
        "motivo": "Identificador nacional de trazabilidad: no cambia el valor.",
    },
    "numero_predial": {
        "required_for_estimation": False, "required_for_decision": True,
        "motivo": "Identificador catastral de trazabilidad: no cambia el valor.",
    },
    "area_m2": {
        "required_for_estimation": True, "required_for_decision": True,
        "motivo": "El valor de una unidad es proporcional a su área privada.",
    },
    "regimen_ph": {
        "required_for_estimation": True, "required_for_decision": True,
        "motivo": "PH vs lote cambia el universo de comparables admisibles.",
    },
    "tipologia": {
        "required_for_estimation": True, "required_for_decision": True,
        "motivo": "Apartamento/PH/casa/bodega son mercados distintos.",
    },
    "destino": {
        "required_for_estimation": True, "required_for_decision": True,
        "motivo": "Habitacional vs comercial usan tasas distintas.",
    },
    "barrio": {
        "required_for_estimation": True, "required_for_decision": True,
        "motivo": "Es la unidad de segmentación de mercado.",
    },
    "localidad": {
        "required_for_estimation": False, "required_for_decision": True,
        "motivo": "Agrupa por encima del barrio: no segmenta el precio de una unidad.",
    },
    "estrato": {
        "required_for_estimation": True, "required_for_decision": True,
        "motivo": ("Estratifica la comparación y llavea la tasa de capitalización; no "
                   "sustituye a una tasa de mercado."),
    },
    "coordenadas": {
        "required_for_estimation": True, "required_for_decision": True,
        "motivo": "Sin geometría del sujeto no hay distancia ni matching espacial.",
    },
    "sector_mercado": {
        "required_for_estimation": True, "required_for_decision": True,
        "motivo": "Es el pivote entre el sujeto y cualquier comparación.",
    },
    "altura_maxima_pot": {
        "required_for_estimation": False, "required_for_decision": True,
        "motivo": DECLARACION_ALTURA_POT,
    },
    "tratamiento_pot": {
        "required_for_estimation": False, "required_for_decision": True,
        "motivo": ("Regula la intervención urbanística; una unidad PH terminada se estima "
                   "con su propio mercado."),
    },
    "edificabilidad_pot": {
        "required_for_estimation": False, "required_for_decision": True,
        "motivo": "Sostiene potencial constructivo futuro, no el valor actual de la unidad.",
    },
    "uso_pot": {
        "required_for_estimation": False, "required_for_decision": True,
        "motivo": "Compatibilidad normativa del uso, no precio observado.",
    },
    "referencias_historicas": {
        "required_for_estimation": False, "required_for_decision": True,
        "motivo": "Sirven para explicar deriva y contradicciones del expediente.",
    },
    "riesgo_amenaza": {
        "required_for_estimation": False, "required_for_decision": True,
        "motivo": "Afecta la decisión de riesgo; el ajuste por riesgo es otra fase.",
    },
    "titulo_gravamenes": {
        "required_for_estimation": False, "required_for_decision": True,
        "motivo": "Afecta la negociabilidad, no el valor de mercado del inmueble.",
    },
    "screening_contrapartes": {
        "required_for_estimation": False, "required_for_decision": True,
        "motivo": "Riesgo de contraparte, no valor del activo.",
    },
    "equipamiento_poi": {
        "required_for_estimation": False, "required_for_decision": False,
        "motivo": "Enriquecimiento de contexto; no bloquea ninguno de los dos propósitos.",
    },
    "release_gate": {
        "required_for_estimation": False, "required_for_decision": True,
        "motivo": "Gobierna la entrega del documento, no el cálculo.",
    },
    "comparables_directos": {
        "required_for_estimation": False, "required_for_decision": True,
        "motivo": REGLA_AUSENCIA_LEVEL_1,
    },
    "soporte_de_mercado_utilizable": {
        "required_for_estimation": True, "required_for_decision": True,
        "motivo": ("Es el único bloqueo de mercado que sí cierra la estimación: sin un "
                   "nivel 1-3 con origen habilitante no hay cifra sostenible."),
    },
    "tasa_mercado_m2": {
        "required_for_estimation": True, "required_for_decision": True,
        "motivo": ("Una tasa MANUAL_CONFIG/MODEL_PRIOR no es tasa: se exige origen "
                   "habilitante."),
    },
    "rentas_observadas": {
        "required_for_estimation": False, "required_for_decision": False,
        "motivo": "Sólo se exige si el método elegido es capitalización de rentas.",
    },
    "costos_construccion": {
        "required_for_estimation": False, "required_for_decision": False,
        "motivo": "Sólo se exige si el método elegido es reposición física.",
    },
    "model_priors": {
        "required_for_estimation": False, "required_for_decision": False,
        "motivo": ("Un prior del modelo no es un requisito: es un valor por defecto que no "
                   "sostiene cifra."),
    },
}


def blocking_por_proposito() -> Dict[str, Any]:
    """Tabla de bloqueo con los dos propósitos SEPARADOS y explícitos (§26)."""
    tabla = {attr: dict(regla) for attr, regla in ATRIBUTOS_BLOCKING.items()}
    return {
        "version": VERSION_BLOCKING_PROPOSITO,
        "propositos": list(PROPOSITOS),
        "atributos": tabla,
        "solo_estimacion": sorted(a for a, r in tabla.items()
                                  if r["required_for_estimation"]
                                  and not r["required_for_decision"]),
        "solo_decision": sorted(a for a, r in tabla.items()
                                if r["required_for_decision"]
                                and not r["required_for_estimation"]),
        "ambos": sorted(a for a, r in tabla.items()
                        if r["required_for_estimation"] and r["required_for_decision"]),
        "ninguno": sorted(a for a, r in tabla.items()
                          if not r["required_for_estimation"]
                          and not r["required_for_decision"]),
        "declaracion_altura_pot": DECLARACION_ALTURA_POT,
        "regla_pot": REGLA_POT_NO_BLOQUEA_ESTIMACION,
    }


#: Nombre EXACTO del campo de la tabla por propósito. Se declara explícitamente para no
#: depender de derivar la clave del literal del propósito (fuente histórica de un bug:
#: `ESTIMACION`→`required_for_estimacion` no existe en la tabla).
CAMPO_REQUERIDO_POR_PROPOSITO: Dict[str, str] = {
    PROPOSITO_ESTIMACION: "required_for_estimation",
    PROPOSITO_DECISION: "required_for_decision",
}


def requerido_para(atributo: str, proposito: str) -> bool:
    """¿El atributo es exigible para ese propósito? Atributo desconocido → False."""
    if proposito not in PROPOSITOS:
        raise ValueError(f"proposito={proposito!r} no pertenece a {PROPOSITOS}")
    regla = ATRIBUTOS_BLOCKING.get(atributo)
    if regla is None:
        return False
    return bool(regla.get(CAMPO_REQUERIDO_POR_PROPOSITO[proposito]))


#: Claves que identifican un descriptor de estado frente a un VALOR que es un dict.
CLAVES_DESCRIPTOR: Tuple[str, ...] = ("estado", "status", "value", "valor")

ESTADOS_AUSENCIA: Tuple[str, ...] = (
    "SOURCE_UNAVAILABLE", "NOT_SUPPORTED", "QUERY_FAILED", "FUENTE_NO_DISPONIBLE",
    "DATOS_AUSENTES", "NO_MATCH",
)


def _leer_descriptor(bruto: Any) -> Tuple[Any, Optional[str]]:
    """Separa (valor, estado) de una entrada.

    Un ``dict`` sólo es descriptor de estado si declara alguna de ``CLAVES_DESCRIPTOR``;
    si no (p. ej. unas coordenadas ``{"lat":…, "lon":…}``), el dict ES el valor. Sin esta
    distinción, un valor compuesto se leería como ausencia.
    """
    if isinstance(bruto, Mapping) and any(k in bruto for k in CLAVES_DESCRIPTOR):
        valor = bruto.get("value", bruto.get("valor"))
        estado = bruto.get("estado", bruto.get("status"))
        return valor, (str(estado) if estado is not None else None)
    return bruto, None


def evaluar_blocking_por_proposito(entradas: Mapping[str, Any]) -> Dict[str, Any]:
    """Evalúa ausencias por atributo y decide qué bloquea cada propósito.

    ``entradas`` mapea atributo → valor (``None`` = ausente) o atributo → descriptor con
    ``estado``/``value``. Un ``SOURCE_UNAVAILABLE`` en POT/altura NO bloquea la
    estimación por sí solo: se declara como límite de decisión.
    """
    if not isinstance(entradas, Mapping):
        raise TypeError("entradas debe ser un mapping atributo -> valor/estado")
    disponibles, ausentes, bloqueos_estimacion, bloqueos_decision = [], [], [], []

    for atributo, bruto in entradas.items():
        valor, estado = _leer_descriptor(bruto)
        presente = valor is not None and estado not in ESTADOS_AUSENCIA
        (disponibles if presente else ausentes).append(atributo)
        if presente:
            continue
        if requerido_para(atributo, PROPOSITO_ESTIMACION):
            bloqueos_estimacion.append({
                "atributo": atributo,
                "motivo": ATRIBUTOS_BLOCKING.get(atributo, {}).get("motivo"),
                "required_for_estimation": True,
            })
        if requerido_para(atributo, PROPOSITO_DECISION):
            bloqueos_decision.append({
                "atributo": atributo,
                "motivo": ATRIBUTOS_BLOCKING.get(atributo, {}).get("motivo"),
                "required_for_decision": True,
                "bloquea_estimacion": requerido_para(atributo, PROPOSITO_ESTIMACION),
            })

    return {
        "version": VERSION_BLOCKING_PROPOSITO,
        "estimacion": {
            "proposito": PROPOSITO_ESTIMACION,
            "bloqueado": bool(bloqueos_estimacion),
            "bloqueos": bloqueos_estimacion,
            "atributos_ausentes_no_bloqueantes": sorted(
                a for a in ausentes
                if not requerido_para(a, PROPOSITO_ESTIMACION)),
        },
        "decision": {
            "proposito": PROPOSITO_DECISION,
            "bloqueado": bool(bloqueos_decision),
            "bloqueos": bloqueos_decision,
        },
        "atributos_presentes": sorted(disponibles),
        "atributos_ausentes": sorted(ausentes),
        "declaracion_altura_pot": DECLARACION_ALTURA_POT,
        "regla_pot": REGLA_POT_NO_BLOQUEA_ESTIMACION,
    }

# DICTUS ESTIMATION ENGINE v1.0 · FASE 2 (NÚCLEO)

Contrato de datos de `api/estimation.py`. **Esta fase NO toca PDF**: entrega el motor
y sus compuertas. Las tres compuertas nuevas son ORTOGONALES a `VALUATION_GATE`
(vocabulario CERRADO `CLOSED`/`OPEN` de `dictus_decision`, §30) y **no lo sustituyen**.

Principio rector: **«NO EMITIR VALORACIÓN» / `NOT_ESTIMABLE` es el ÚLTIMO estado**, no
el comportamiento por defecto. DICTUS **INTENTA estimar**.

---

## 1 · Tres conceptos que no se sustituyen (§1)

| Compuerta | Pregunta | Estados |
|---|---|---|
| `VERIFIED_MARKET_EVIDENCE_GATE` | ¿la evidencia de mercado tiene origen **y** procedencia suficientes para tratar la cifra como sustentada por fuentes verificadas? | `OPEN` · `CLOSED` |
| `ESTIMATION_GATE` | ¿hay información suficiente para una **estimación razonable**, aunque la evidencia no alcance el estándar anterior? | `OPEN` · `OPEN_WITH_LIMITATIONS` · `CLOSED` |
| `EVIDENCE_QUALITY_GATE` | ¿qué **calidad** tiene la evidencia? (sin score 0-100) | `HIGH` · `MEDIUM` · `INDICATIVE` · `INSUFFICIENT` |

**Regla §30:** `VERIFIED_MARKET_EVIDENCE_GATE = CLOSED` **PUEDE** coexistir con
`ESTIMATION_GATE = OPEN_WITH_LIMITATIONS` (regresión viva en
`tests/test_estimation_gate.py::test_06_modelo_calibrado_verificado_da_estimacion_indicativa`).
`NO EMITIR VALORACIÓN` **no** es consecuencia automática de la primera.

Condiciones mínimas del `ESTIMATION_GATE` (`dictus-estimation-conditions/1.0.0`):
`IDENTIDAD_SUFICIENTEMENTE_RESUELTA` + `UBICACION_UTILIZABLE` + `AREA_UTILIZABLE` +
`TIPOLOGIA_MINIMA` + `SOPORTE_ECONOMICO_VALIDO`. **`MANUAL_CONFIG` y
`LEGACY_MODEL_PRIOR` NO cuentan** como soporte económico válido.

## 2 · Composición de `origin` (§2/§3) — `dictus-origin-composition/1.0.0`

Se suman cinco clases a las de `atribucion_mercado` (que sigue siendo la única
autoridad de degradación por procedencia): `COMPUTED_WITH_MODEL_PRIOR`,
`COMPUTED_WITH_STATIC_REFERENCE`, `NOT_PRODUCTIVE`, `LEGACY_MODEL_PRIOR`
(≡ `MODEL_PRIOR`), `CALIBRATED_MODEL_PRIOR`. Las reglas se aplican **en orden**;

| Insumos que PARTICIPAN del cálculo | Composición | Regla |
|---|---|---|
| `EXTERNAL_SOURCE` + `EXTERNAL_SOURCE` | `COMPUTED_FROM_SOURCES` | `R5_FUENTES_MULTIPLES` |
| `EXTERNAL_SOURCE` + `CALIBRATED_MODEL_PRIOR` | `COMPUTED_WITH_MODEL_PRIOR` | `R2_EXTERNA_MAS_PRIOR_CALIBRADO` |
| `EXTERNAL_SOURCE` + `STATIC_REFERENCE` | `COMPUTED_WITH_STATIC_REFERENCE` | `R4_EXTERNA_MAS_ESTATICA` |
| `EXTERNAL_SOURCE` + **`MANUAL_CONFIG`** | **`NOT_PRODUCTIVE`** | `R1_NO_LAVADO` |
| `CALIBRATED_MODEL_PRIOR` sola | `CALIBRATED_MODEL_PRIOR` | `R6_CLASE_UNICA` |
| `STATIC_REFERENCE` sola | `STATIC_REFERENCE` (no sostiene) | `R6_CLASE_UNICA` |
| nada | `NOT_PRODUCTIVE` | `R0_SIN_INSUMOS` |

Reglas duras:

* **`MANUAL_CONFIG` no lava**: si un valor escrito a mano participa del cálculo, la
  composición es `NOT_PRODUCTIVE`, **jamás** `COMPUTED_FROM_SOURCES` (se prueban cinco
  mezclas distintas). El motor **nunca** usa `MANUAL_CONFIG` como insumo de la cifra:
  lo declara en `clases_excluidas` y en `excluidos[]`.
* **Una clase que DEBILITA la afirmación manda sobre la etiqueta pura de fuentes**: si
  entró un modelo calibrado o una referencia estática, la composición lo declara aunque
  haya varias fuentes externas.
* El **techo de calidad** es el mínimo de los techos de las clases usadas: un modelo
  calibrado dentro del cálculo impide `HIGH`; un parámetro a mano impide cualquier cifra.
* Afirmar `EXTERNAL_SOURCE` **sin procedencia completa** no se honra: se degrada a
  `MANUAL_CONFIG` (delegado en `atribucion_mercado`) y la composición cae a
  `NOT_PRODUCTIVE`.
* `LEGACY_MODEL_PRIOR` se **conserva por compatibilidad** (el hardcode por estrato
  `{3:3.8M, 4:5.2M, 5:6.5M, 6:7.8M}` vive donde siempre, **no se duplica aquí**):
  no abre `ESTIMATION_GATE`, no aparece en producto y no produce cifra. Sólo un
  `CALIBRATED_MODEL_PRIOR` que cumpla el contrato de §16 (18 campos, muestra ≥ 20,
  error ≤ 0,25, vigencia, procedencia y hash) puede contribuir a `INDICATIVE`.

## 3 · Métodos (§17-§21) — `dictus-estimation-methods/1.0.0`

`M1 MARKET COMPARISON` · `M2 REPLACEMENT COST` · `M3 INCOME CAPITALIZATION` ·
`M4 MODELO CALIBRADO` (base **indicativa**, §16: no es un método de mercado y existe
para que el prior calibrado pueda contribuir sin disfrazarse de comparación).
Cada método declara `status` (`AVAILABLE`/`PARTIAL`/`NOT_APPLICABLE`/`INSUFFICIENT_DATA`),
`result`, `range`, `inputs`, `origin`, `confidence`, `reason` y sus `adjustments`
(incluidos los **NO aplicados**, con su motivo). Una **tasa manual NO equivale a
comparables**: sin comparables, `M1` es `NOT_APPLICABLE` y lo dice. El ensemble (§21) se
publica con `method` / `weight` / `reason_for_weight` a la vista y pesos normalizados.
Sin datos no se rellena: `M2` sin costo unitario y `M3` sin cap rate con procedencia
quedan como `NOT_APPLICABLE` / `INSUFFICIENT_DATA`.

## 4 · Rango primero e incertidumbre (§12/§15) — `dictus-range-width/1.0.0`

```
semi_ancho = 0.06
           + 1.2 · min(cv, 0.25)                     (dispersión de comparables)
           + AJUSTE_N[n]                             (8→0.00 · 5→0.02 · 3→0.05 · 2→0.08 · 1→0.12 · 0→0.15)
           + 0.02 · trimestres_antiguedad  (cap 0.10)
           + 0.06 · (1 − matching_quality)
           + AJUSTE_ORIGEN[composición]              (externa 0.00 … NOT_PRODUCTIVE 0.20)
           + 1.0 · min(error_modelo, 0.15)
semi_ancho = min(semi_ancho, 0.60)
```

* La **banda de la calidad manda**: `HIGH` ∈ [±6%, ±15%], `MEDIUM` ∈ [±10%, ±30%],
  `INDICATIVE` ∈ [±15%, ±60%]. Si el ancho calculado **no cabe**, se **DEGRADA la
  calidad** (el rango no se estrecha a la fuerza); si queda por debajo del mínimo, se
  **ELEVA** al mínimo. Por eso **`HIGH` con ±20%** y **`INDICATIVE` con ±5%** son
  imposibles **sin razón explícita**; con `razon_ancho_explicita` la excepción se
  permite y queda documentada en `range.razon_explicita` y en `range.motivos`.
* La **cifra central no puede tener más precisión que la evidencia**: el paso de
  redondeo se deriva del ancho (`±30% → 10M`, `±15% → 5M`, resto `→ 1M`) y **nunca es
  menor a $1.000.000**, de modo que una cifra como `399.500.000` no puede emitirse.

## 5 · Histórico, vocabulario y metodología (§23/§28/§29/§31/§34)

* `historical_estimate_reference` (`old_run_id`, `old_value`, `old_range`, `old_method`,
  `old_inputs`, `old_origin`, `old_master_hash`) viaja con `usado_como_input = False`:
  el valor de una corrida anterior es **sólo forense** y nunca input.
* Si no hay **ninguna** fuente de mercado, `ESTIMATION_GATE = CLOSED` con
  `MISSING_MARKET_EVIDENCE` y un `GAP REPORT` que pide fuentes automáticas concretas
  (`estado: "NO INCORPORADA"`, `contrato: null` — pide, no afirma que existan), y que
  **distingue** ese cierre del caso «el único parámetro es `MANUAL_CONFIG`»
  (`CAUSA ADICIONAL` en `reasons`).
* Vocabulario económico (§31): `ESTIMACIÓN DISPONIBLE` · `ESTIMACIÓN DISPONIBLE CON
  LIMITACIONES` · `ESTIMACIÓN INDICATIVA` · `NO FUE POSIBLE ESTIMAR`. Una estimación
  —y menos una indicativa— **nunca** se llama «INFORMACIÓN VERIFICADA»:
  `es_valor_verificado()` devuelve siempre `False` y `ETIQUETAS_VERIFICADAS_PROHIBIDAS`
  lo hace verificable.
* Metodología base (§34): «fuentes disponibles + análisis técnico automatizado +
  metodología versionada». La revisión profesional es el producto **separado**
  `DICTUS + REVIEW`; `contiene_vocabulario_metodologico_prohibido()` audita el texto.
* Sigue vigente: **`Lonja` no es una fuente de datos** y en este módulo no existe ni
  como nombre ni como sustituto inventado.

## 6 · §35 · Regresiones previas — reclasificación documental

No se borró ni se debilitó ninguna regresión existente. Las que hasta ahora se leían
como «la valoración está cerrada» se **reclasifican** como regresiones de
**`VERIFIED_MARKET_EVIDENCE`**, que es la compuerta que realmente gobiernan:

| Regresión existente | Lectura correcta tras la Fase 2 |
|---|---|
| `tests/test_no_lonja_as_source.py` | `VERIFIED_MARKET_EVIDENCE` (no hay fuente externa automática verificada) |
| `test_no_lonja_as_source` · etiqueta de la tasa | `VERIFIED_MARKET_EVIDENCE` + vocabulario de §31 (nunca «información verificada») |
| `scripts/golden_evidence_asserts.py` · `manual_market_input_cannot_open_valuation_gate` | `VERIFIED_MARKET_EVIDENCE_GATE = CLOSED` (la estimación es otra pregunta) |
| `... · model_prior_cannot_open_valuation_gate` | ídem, con `LEGACY_MODEL_PRIOR` |
| `... · computed_from_sources_requires_all_material_inputs_authorized` | ídem (procedencia completa) |
| `tests/test_source_pack_market.py`, `test_dictus_20d_decision.py`, `test_valoracion_tipologia.py` | sin cambios: el vocabulario y las compuertas previas siguen intactos |
| `tests/test_golden_evidence_pack.py` | sin cambios (11/11 PASS, exit 0, verificado) |

La Fase 2 **añade** `ESTIMATION_GATE` y `EVIDENCE_QUALITY_GATE` sin tocar
`VALUATION_GATE`, `atribucion_mercado`, `market_context` ni el render de PDF.

## 7 · Pruebas

```
python -m pytest tests/test_estimation_gate.py \
                 tests/test_estimation_evidence_quality_gate.py \
                 tests/test_estimation_origin_composition.py -q     # 75 passed
python scripts/golden_evidence_asserts.py                            # 11/11 · exit 0
```

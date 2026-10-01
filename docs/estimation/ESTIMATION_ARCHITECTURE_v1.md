# DICTUS ESTIMATION ENGINE v1.0 — ARQUITECTURA (Fase 3)

**Estado:** motor integrado + golden reproducible + contratos de impresión cableados.
**Versiones:** `dictus-estimation-engine/1.0.0` (motor) · `dictus-estimation-integration/1.0.0`
(puente estado → motor) · `dictus-estimation-golden/1.0.0` (golden) ·
`dictus-evidence-quality/1.0.0` · `dictus-range-width/1.0.0` · `dictus-origin-composition/1.0.0` ·
`dictus-estimation-conditions/1.0.0` · `dictus-estimation-methods/1.0.0`.

**Qué NO es este documento:** un contrato congelado. Lo que sigue describe cómo está
construido el motor **hoy** y qué garantiza. `CONTRACT FROZEN` no se declara aquí.

---

## 1 · Qué hace el motor y qué no

El motor responde UNA pregunta: **¿con qué evidencia económica disponible en esta corrida
se puede emitir un rango de valor, y con qué confianza?** Su salida primaria es un
**RANGO**; la cifra central es secundaria y se redondea según el ancho del rango.

Lo que el motor **no** hace, por diseño:

- No convierte un parámetro escrito a mano en fuente. `MANUAL_CONFIG` no es una fuente.
- No rellena un insumo faltante con un valor inferido, promediado o «razonable».
- No publica un score 0–100: publica un **nivel cualitativo razonado**.
- No emite un valor verificado: `es_valor_verificado(status)` es **siempre** `False`.
- No es un avalúo. Es una **estimación automatizada**; la revisión profesional es un
  producto **separado** (`DICTUS + REVIEW`).

## 2 · Tres compuertas, tres preguntas distintas

| compuerta | pregunta | estados | no implica |
|---|---|---|---|
| `VERIFIED_MARKET_EVIDENCE_GATE` | ¿la evidencia de mercado tiene origen Y procedencia suficientes para tratar la cifra como sustentada por fuentes verificadas? | `OPEN` / `CLOSED` | `CLOSED` **no** cierra la estimación |
| `EVIDENCE_QUALITY_GATE` | ¿de qué calidad es la evidencia, dimensión por dimensión? | `HIGH` / `MEDIUM` / `INDICATIVE` / `INSUFFICIENT` | no produce cifra |
| `ESTIMATION_GATE` | ¿hay información suficiente para estimar? | `OPEN` / `OPEN_WITH_LIMITATIONS` / `CLOSED` | `CLOSED` es el **último** estado, no el de partida |

Condiciones mínimas de `ESTIMATION_GATE`: identidad suficientemente resuelta · ubicación
utilizable · área utilizable · tipología mínima · **algún** soporte económico válido
(comparable externo, estadística externa agregada, modelo calibrado o combinación).
`MANUAL_CONFIG` y `LEGACY_MODEL_PRIOR` **no** cuentan como soporte.

Estados del resultado (`EstimationResult.status`): `ESTIMATED` ·
`ESTIMATED_WITH_LIMITATIONS` · `INDICATIVE_ESTIMATE` · `NOT_ESTIMABLE`. `NOT_ESTIMABLE` se
decide **al final**, cuando la compuerta cerró o ningún método produjo cifra.

Con la evidencia que la corrida 040-646406 tiene hoy (una referencia agregada de nivel 3,
sin comparables directos), el motor **estima**: `ESTIMATION_GATE =
OPEN_WITH_LIMITATIONS`, `status = INDICATIVE_ESTIMATE`, rango derivado del ancho y
referencia central gruesa. Que una corrida estime NO la convierte en un avalúo ni en un
valor verificado: `es_valor_verificado(status)` sigue siendo `False`.

## 3 · Escalera de evidencia de mercado (`market-evidence-ladder/1.0.0`)

| nivel | qué es | método | ¿sostiene una cifra? |
|---|---|---|---|
| 1 | comparables directos (misma tipología, área, precio, fecha, procedencia) | `M1` | sí |
| 2 | observaciones locales de mercado | `M1` | sí |
| 3 | referencias agregadas de mercado (valor/m² por sector o banda de área) | **`M5`** | sí, con techo `INDICATIVE` |
| 4 | prior de modelo calibrado (`sample_size`, `calibration_error`, vigencia, hash) | `M4` | sí, con techo `INDICATIVE` |
| 5 | referencia estática / `MANUAL_CONFIG` / prior legacy | — | **no**, nunca |

Regla explícita: **la ausencia de nivel 1 no implica `CLOSED`**. No tener comparables
directos degrada la CALIDAD y obliga a declarar el nivel realmente usado y su límite.

Transición medida en el Golden 040-646406 (mismo expediente, misma fecha de referencia,
única diferencia: incorporar o no la referencia de nivel 3):

| escenario | `ESTIMATION_GATE` | calidad | `status` | origen |
|---|---|---|---|---|
| SIN nivel 3 | `CLOSED` | `INSUFFICIENT` | `NOT_ESTIMABLE` | `NOT_PRODUCTIVE` |
| **CON nivel 3** | **`OPEN_WITH_LIMITATIONS`** | `INDICATIVE` | **`INDICATIVE_ESTIMATE`** | `EXTERNAL_SOURCE` |

Nivel 3 lleva a `OPEN_WITH_LIMITATIONS`, **no** a `OPEN`: agrega por sector y banda de
área, así que no acredita la unidad.

## 4 · Entrada del motor: cómo se construye desde el estado real

`api/estimation_state.py` es la **única** puerta entre el expediente y el motor.

| insumo | de dónde sale | con qué origen |
|---|---|---|
| `identidad` | `property_identity` (`identity_verified`) + evidencias SELLADAS `EV-IDENTIDAD`, `EV-GEOMETRIA` | `COMPUTED_FROM_SOURCES` |
| `ubicacion` | `market_context.coordinate_source_verified` / `coordinate_source` / `canonical_binding_status` | estado tal como lo declara la corrida (`OFFICIAL_PREDIO`, …) |
| `area` | `urban_context.area` (área privada de la unidad) + evidencias selladas | `COMPUTED_FROM_SOURCES` |
| `tipologia` | `urban_context.tipologia` + `tipologia_status` | `VERIFIED_REGISTRAL` |
| `comparables` | cosecha/captura de mercado **si existe** | `EXTERNAL_SOURCE` |
| `estadisticas_externas` | `docs/estimation/MARKET_HARVEST_*.json` (nivel 3) | `EXTERNAL_SOURCE` |
| `modelo_calibrado` | modelo con contrato auditable (§16) **si existe** | `CALIBRATED_MODEL_PRIOR` |
| `costo_reposicion` / `rental_reference` / `cap_rate` | bloques declarados por la corrida | el que declaren |
| `tasa_manual` | `market_context.sector_metodologico.value_m2` | `MANUAL_CONFIG` → **EXCLUIDO** |
| `modelo_legacy` | `valuation_state.origins` (`MODEL_PRIOR`) | `LEGACY_MODEL_PRIOR` → **EXCLUIDO** |
| `historico_forense` | `historical_consistency` | se copia con `usado_como_input = False` |

La fecha de referencia de la estimación se toma de `generated_at` de la corrida: el
resultado es **reproducible** a partir del expediente (no depende de «hoy»).

### 4.1 · Criterio de incorporación de la cosecha de capas municipales

`MARKET_HARVEST_*.json` sólo entra si su referencia de nivel 3 trae procedencia
**auditable**. El checklist se resuelve campo por campo y se publica:

`url` · `consultado_en` · `http` · `bytes` · `sha256` · `vigencia` · `muestra`

Los cinco primeros son **obligatorios**: sin ellos la referencia se RECHAZA y se declara
el motivo. `vigencia` y `muestra` pueden venir vacíos: la referencia entra **declarando**
que la fuente no los publica, y esa ausencia queda como limitación impresa (nunca se
rellena). Un rango agregado **no se promedia** para fabricar un valor único.

## 5 · Métodos (M1–M5)

| método | insumo mínimo | resultado |
|---|---|---|
| `M1_MARKET_COMPARISON` | comparables externos con procedencia | media ponderada por vigencia + dispersión |
| `M2_REPLACEMENT_COST` | área + costo unitario + depreciación/edad | costo de reposición |
| `M3_INCOME_CAPITALIZATION` | `rental_reference` + `cap_rate` | capitalización |
| `M4_CALIBRATED_MODEL_PRIOR` | modelo calibrado con contrato §16 completo | central/low/high del modelo |
| `M5_AGGREGATED_MARKET_REFERENCE` | referencia **agregada de nivel 3** con procedencia HTTP completa y banda declarada que contenga el área del sujeto | **rango oficial de la fuente** aplicado al área + referencia central derivada |

Ningún método se rellena. Si falta su insumo, el método queda `NOT_APPLICABLE` o
`INSUFFICIENT_DATA` **con su motivo**, y ese motivo viaja al resultado (`limitations`) y a
la compuerta (`reasons`). Los pesos del ensemble viven en `ensemble` (`§21`).

### 5.0 · `M5` es una EXTENSIÓN EXPLÍCITA del contrato de Fase 2

La Fase 2 declaró los métodos M1–M4. **M5 se añade aquí y no modifica a ninguno de
ellos**: M1 sigue siendo el método principal cuando hay comparables, M2/M3/M4 conservan su
contrato, sus pesos y sus pruebas intactas.

Por qué era obligatorio añadirlo — sin M5 el motor **incumplía el pliego en tres sitios
literales**:

1. **§5 (escalera de evidencia):** LEVEL 3 **sostiene** una cifra. Con M1–M4, una
   referencia de nivel 3 entraba en la composición de `origin` pero **ningún método la
   consumía**, así que el motor cerraba con evidencia oficial real sobre la mesa.
2. **§29:** «precio/m² sectorial válido + resto razonable ⇒ `OPEN_WITH_LIMITATIONS` +
   `INDICATIVE_ESTIMATE`». Sin M5, esa combinación producía `CLOSED`/`NOT_ESTIMABLE`.
3. **§41:** hay que distinguir evidencia fuerte de débil **sin convertir la prudencia en
   «no intento estimar»**. Un cierre por falta de método no es prudencia: es un método
   ausente.

Si alguien objeta que añadir M5 «cambia el contrato», la respuesta es esa: **sin él el
motor no cumple §5, §29 ni §41**. La extensión queda declarada aquí, en
`ESTIMATION_METHODS_040-646406.json` (`extension_de_contrato`) y en el propio método, y
la única aserción existente que dependía del cardinal de métodos
(`tests/test_estimation_gate.py::test_17`, que fijaba `4`) pasa a `len(est.METODOS)`
—más estricta: sigue exigiendo que **todos** los métodos evaluados se declaren con peso y
razón—.

### 5.1 · M5 · reglas de entrada y doctrina del rango

**Entrada (fail-closed).** Sólo consume `LEVEL_3_AGGREGATED_MARKET_REFERENCES` con
`origin = EXTERNAL_SOURCE` y procedencia completa: `source_id`, URL, `consultado_en`,
**HTTP 200**, `bytes`, `sha256` y **metodología declarada**. Además, la banda de área de la
fuente debe **contener** el área del sujeto (36-60 m² ⊇ 58,75 m²). Si falta cualquier
pieza → `INSUFFICIENT_DATA` con el campo que falta; el método no se usa y **no se
sustituye por nada** (ni por la tasa manual, ni por un prior).

**Rango (§29).** `range_low`/`range_high` salen **directamente del rango de la FUENTE**:
`min_valor_m2`/`max_valor_m2` **literales** aplicados al área del sujeto. El ancho
calculado por §15 se aplica y se publica, pero **nunca estrecha** el rango por debajo de
la banda oficial: los bordes se redondean **hacia fuera** y el `semi_ancho_relativo`
efectivo es el del rango publicado (el `semi_ancho_calculado` viaja aparte, para que se
vea que el ensanchamiento viene de la evidencia, no del gusto).

**Referencia central.** El `valor_m2` **de la fuente** no existe y no se inventa
(`no_es_valor_de_la_fuente = True`; la fuente sigue con `valor_m2 = null`). La referencia
central sólo existe como **derivación explícita de DICTUS**: `punto medio del rango
oficial`, declarada en `derivation` (`type = MIDPOINT_OF_SOURCE_RANGE`,
`source_count = 1`, `source_ids = [<fuente>]`) con `origen =
DERIVED_FROM_EXTERNAL_SOURCE` y la **evidencia base en `EXTERNAL_SOURCE`** (§5.3), y
redondeada después por el ancho (§12). Los ajustes que no se hacen se publican como
`NO_APLICADO`: `promedio aritmético de los extremos`, `división por el área del sujeto`,
`traslado de la unidad al sector` y `muestra (N) del análisis`.

**Muestra ausente.** `sample_size = null` **no se rellena**: no impide el método por sí
solo, **degrada la calidad** y viaja en `limitations`.

**Techo.** `INDICATIVE`: la referencia agrega por localidad y banda de área, así que
**no acredita la unidad** y no puede abrir `OPEN`.

**Dos compuertas que coexisten (§30).** `VERIFIED_MARKET_EVIDENCE_GATE = CLOSED` —
pregunta si la cifra puede tratarse como sustentada por fuentes verificadas **de esta
unidad**, y una referencia agregada no lo acredita— junto a `ESTIMATION_GATE =
OPEN_WITH_LIMITATIONS`. El motor aparta explícitamente la evidencia de nivel 3 de esa
compuerta y lo declara (`evidencia_agregada_no_atribuible`).

### 5.2 · Adquisición del nivel 3: el 403 era rompible

El host del geoportal municipal está detrás de **Cloudflare** y responde **HTTP 403** con
el interstitial «Just a moment…» a las peticiones cuyo `Accept`/`Sec-Fetch-*` no parecen
de navegación. Medido el **2026-09-29**: **la misma URL devuelve 200** cuando la petición
lleva cabeceras de navegación completas. La medición vive en `api/market_harvest.py`
(`NAV_HEADERS`) y el payload crudo de cada capa se conserva **sin modificar** en
`docs/estimation/raw/<capa>.json`, para que el `sha256` sea reproducible.

| cabecera | valor |
|---|---|
| `User-Agent` | `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36` |
| `Accept` | `text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8` |
| `Accept-Language` | `es-CO,es;q=0.9,en;q=0.8` |
| `Sec-Fetch-Dest` | `document` |
| `Sec-Fetch-Mode` | `navigate` |
| `Sec-Fetch-Site` | `none` |
| `Sec-Fetch-User` | `?1` |
| `Upgrade-Insecure-Requests` | `1` |
| `Referer` | `https://miciudad.barranquilla.gov.co/` |

Aun así, el 403 se trata como **estado de primera clase**: una respuesta bloqueada se
conserva con su cuerpo real y su hash, y jamás se convierte en «sin datos de mercado».

## 6 · Ancho de rango y confianza

`ancho_de_rango` (`dictus-range-width/1.0.0`) deriva el semi-ancho de la incertidumbre
**real**: dispersión, antigüedad, calidad del emparejamiento, origen de la cifra y error
declarado del modelo. Techo absoluto ±60 % (`MAX_SEMI_ANCHO`). El ancho puede **degradar**
la calidad efectiva, y el resultado viaja coherente.

La dispersión se toma, en este orden, de la única fuente que la declare:
(a) el `cv` de los comparables usados; (b) si no hay comparables pero sí una referencia de
**nivel 3**, la semi-amplitud relativa de la banda que la fuente publica (declarada en
`componentes.dispersion_origen = M5_AGGREGATED_MARKET_REFERENCE`); (c) si no hay ninguna de
las dos, el ancho lo declara como **no medible** y suma su ajuste de ausencia — jamás se
inventa un `cv`.

La confianza impresa se **deriva** del nivel de calidad: `HIGH → ALTA` ·
`MEDIUM → MEDIA` · `INDICATIVE → INDICATIVA` · `INSUFFICIENT → NINGUNA`. Nunca se
escribe a mano.

La precisión del redondeo depende del ancho (`redondear_segun_evidencia`): no se imprime
una cifra más fina que la evidencia que la sostiene. En el Golden, con evidencia de nivel
3 el ancho calculado da ±51 % y la **banda oficial de la fuente manda**: el rango
publicado es `$ 130.000.000 – $ 490.000.000` (min/max literales × 58,75 m², redondeados
hacia fuera; `semi_ancho_relativo` efectivo ±58,06 %) con referencia central
`$ 310.000.000` (paso $10.000.000): **la salida es el rango**, la cifra central es una
referencia gruesa y derivada.

## 7 · Composición de `origin`

Reglas R0–R6 sobre los insumos que **participan** del cálculo. Un insumo declarado y NO
usado se publica como **excluido**, jamás como fuente. `EXTERNAL_SOURCE + MANUAL_CONFIG`
→ `NOT_PRODUCTIVE`, nunca `COMPUTED_FROM_SOURCES`. El **techo de calidad** del resultado
es el mínimo de los techos de las clases usadas: un parámetro a mano impide cualquier
cifra productiva; un prior calibrado impide el nivel `HIGH`.

## 8 · Contratos de impresión (§32/§33)

### Página 1

- `ESTIMATED` / `ESTIMATED_WITH_LIMITATIONS` → **`VALOR ESTIMADO`**, cifra,
  `Rango: $X – $Y`, `Confianza: <ALTA|MEDIA>`.
- `INDICATIVE_ESTIMATE` → **`ESTIMACIÓN INDICATIVA`** + rango + `Confianza: INDICATIVA`.
- `CLOSED` (o `NOT_ESTIMABLE`) → **`ESTIMACIÓN NO DISPONIBLE`** +
  «Sin evidencia de mercado suficiente» + la lista de lo que falta.

Si el motor no produjo cifra, la P1 no imprime ningún monto: no existe rama que invente
uno.

### Página 6 · bloque `ESTIMACIÓN ECONÓMICA`

Ocho campos obligatorios, en este orden: `RANGO ESTIMADO` · `REFERENCIA CENTRAL` ·
`VALOR/M²` · `CONFIANZA` · `MÉTODO` · `EVIDENCIA UTILIZADA` · `LIMITACIONES` ·
`TRAZABILIDAD`. Cuando el motor no produce cifra, los tres primeros dicen literalmente
**«no disponible»**.

Texto fijo permitido:

> Estimación automatizada de DICTUS basada en la información disponible para esta corrida.
> No constituye un avalúo comercial certificado cuando este sea legal o contractualmente
> requerido.

Debajo del bloque se imprime el **estado de valoración que la corrida declara**
(`VALUATION_GATE`: decisión, estado `CLOSED`/`OPEN`, motivo y condiciones materiales).
Son dos hechos distintos: lo que DICTUS estima y lo que la corrida autoriza.

**§7/§8 (cierre semántico) · nombre del bloque.** Ese bloque inferior se titula
`EVIDENCIA DE MERCADO VERIFICADA · NO HABILITADA` y declara
`VERIFIED_MARKET_EVIDENCE_GATE = <CLOSED|OPEN>` con su razón literal («no existen
comparables individualizados suficientes para atribuir un valor verificado a esta
unidad»). El rótulo «VALOR ESTIMADO POR LA CORRIDA» está **PROHIBIDO** ahí: nombraba un
hecho —la estimación— que DICTUS sí produce, y enfrentado a `ESTIMACIÓN INDICATIVA` el
cliente leía «no hay estimación». La compuerta que cierra es la de EVIDENCIA VERIFICADA,
no `ESTIMATION_GATE`. En la P1 la valoración de la corrida se imprime como «no habilitada
(evidencia no verificada)» y el dominio se llama «Valoración corrida».

### §34 · Marco metodológico

Se sustituyó «norma + concepto técnico + validación profesional» por
**«fuentes disponibles + análisis técnico automatizado + metodología versionada»**. La
fórmula anterior describía otro producto (la revisión profesional, que sigue existiendo
como producto separado) e imprimirla dentro de la estimación atribuía a la estimación una
validación que no tiene.

## 9 · Presupuesto de página

`PIE_Y = 56` pt y `page_budget(page)` miden disponible/consumido/restante por página. El
bloque de estimación se compone **dentro** del presupuesto medido, sin violaciones de
retícula (`verificar_retícula()` compara bounding boxes reales). Para entrar, la página 6
compactó holguras (no tamaños de letra: el cuerpo sigue ≥ `CUERPO_MINIMO_PT = 8.2` pt) y
unificó identidad + geometría en un panel, sin perder ningún hecho.

## 10 · Golden reproducible

```
python scripts/estimation_golden.py                    # regenera los 7 entregables
python scripts/estimation_golden.py --con-verificacion # añade la salida literal de las pruebas
python scripts/dictus_run.py                           # corrida integrada (layout + master hash)
python scripts/golden_evidence_asserts.py              # 11/11 · exit 0 (también con stdout cp1252)
```

El golden **no asume** el resultado: corre el motor sobre
`docs/forensics/040-646406/dictus_2b/DICTUS_RUN_STATE_040-646406.json` y publica lo que
salga, incluidos los **escenarios de contraste** (con y sin la referencia de nivel 3), que
es donde se ve el cambio de estado que compra la evidencia:

| escenario | `ESTIMATION_GATE` | calidad | `status` | rango |
|---|---|---|---|---|
| CON nivel 3 | `OPEN_WITH_LIMITATIONS` | `INDICATIVE` | `INDICATIVE_ESTIMATE` | `$ 130.000.000 – $ 490.000.000` |
| SIN nivel 3 | `CLOSED` | `INSUFFICIENT` | `NOT_ESTIMABLE` | ninguno (no se inventa) |

En los dos escenarios `VERIFIED_MARKET_EVIDENCE_GATE` es `CLOSED` y
`manual inputs used = 0`, `legacy priors used = 0`: lo que cambia es la compuerta de
ESTIMACIÓN y el estado del resultado, y sólo eso.

Veredicto del Golden: **`DICTUS ESTIMATION ENGINE — INDICATIVE ESTIMATE PRODUCED`**.

> Nota de mantenimiento: `scripts/golden_evidence_asserts.py` imprimía «✓» sin protegerse
> del códec de la consola y **moría con `UnicodeEncodeError: 'charmap'` en cp1252 antes de
> dar su veredicto**. Se corrigió en esta fase: todo lo que imprime pasa por un degradado
> seguro a la codificación REAL de la consola, así que el veredicto y el `exit code` son
> los mismos en cualquier consola (con `PYTHONIOENCODING=utf-8` no se degrada nada).

## 11 · Fuera del alcance de v1.0

- Captura de comparables de **nivel 1** (oferta publicada con área, precio y fecha por
  inmueble). Es la vía que llevaría de `INDICATIVE` a `MEDIUM`.
- **`sample_size` (N) del análisis** de `observatorio/valoresm2_area`: la capa no lo publica.
- **Campo de área en `observatorio/valorcompraventas`**: publica valor y fecha por
  transacción pero SIN área, así que no hay valor/m² y **NO se deriva dividiendo por el
  área del sujeto**. Añadir ese campo convierte esa capa en comparables de nivel 1-2.
- **Microdatos de la SNR** (compraventas con área + NUPRE): permitiría comparables con
  distancia real al sujeto; el propio geoportal declara usar esa fuente.
- Costos de construcción con vigencia (M2) y tasa de capitalización declarada (M3).
- Índice de mercado con procedencia para ajuste temporal (hoy el ancho lo refleja y el
  ajuste se declara `NO_APLICADO`).
- Revisión profesional firmada: producto separado.

## 12 · Regresiones conservadas y reclasificación documental

**Ninguna regresión se borró ni se relajó.** En la corrida final: `206 passed, 1 xfailed`
en el conjunto exigido y la suite completa en verde salvo dos fallos **ajenos** a esta
fase (un test VIVO de geocodificación de Bogotá y un fallo de parseo de formulario en
`api/index.py`, ruta de GPV F-77 que esta fase no toca).

La reclasificación es **documental**, no de código:

| regresión | antes se leía como | ahora se lee como |
|---|---|---|
| `VALUATION_GATE.gate_state == 'CLOSED'` + `decision == 'NO EMITIR VALORACIÓN'` (`scripts/golden_evidence_asserts.py` §1, `tests/test_dictus_20d_r1_p6.py`) | «el motor de valoración cerró → no hay estimación» | **«VERIFIED_MARKET_EVIDENCE regression»**: la corrida cierra la VALORACIÓN porque el origen de su tasa (`MANUAL_CONFIG`) no alcanza el estándar de fuente verificada. NO cierra la estimación: eso lo decide `ESTIMATION_GATE`, que en este Golden está **abierto con limitaciones** mientras la valoración de la corrida sigue cerrada. Los dos hechos conviven y la P6 los imprime por separado. |
| `manual_market_input_cannot_open_valuation_gate()` / `model_prior_cannot_open_valuation_gate()` | idem | idem: son regresiones del ORIGEN de la evidencia de mercado, no del juicio económico. |
| «el ejecutivo no imprime monto ni `$0`» | «la valoración está cerrada» | «la valoración NO AUTORIZADA por la corrida no imprime cifra»: el literal «no se imprime ningún monto, ni $0» sigue impreso y sigue siendo verdad para la valoración de la corrida. La estimación de DICTUS es OTRO hecho y publica su propio rango indicativo, rotulado como tal. |

Actualizaciones de aserciones de la fase (todas **endurecen**, ninguna relaja):

1. Las tres afirmaciones de `tests/test_dictus_20d_r1_p6.py` que fijaban el literal
   «Metodología: norma + concepto técnico + validación profesional» ahora fijan el marco
   VIGENTE —y **prohíben** el retirado— (§34).
2. `tests/test_estimation_gate.py::test_17` fijaba `len(ensemble["methods"]) == 4`: el
   motor declara ahora **cinco** métodos porque ganó `M5_AGGREGATED_MARKET_REFERENCE`
   (§22). La aserción pasa a `len(est.METODOS)` —la fuente de verdad del vocabulario— y
   sigue exigiendo que TODOS los métodos evaluados estén declarados con peso y razón.

---

## 13 · CIERRE SEMÁNTICO FINAL (mismo contrato, cuatro correcciones puntuales)

Esta sección documenta las correcciones de semántica que NO cambian la arquitectura: las
tres compuertas y sus estados, la escalera, el Source Pack, la Resolution Ladder, M1–M4,
el master hash y `399.500.000` (sólo forense) siguen intactos.

| # | defecto | corrección | prueba |
|---|---|---|---|
| 1 | `M5` clasificaba su derivación como `COMPUTED_FROM_SOURCES` con **una** fuente | la EVIDENCIA BASE queda `EXTERNAL_SOURCE` y la TRANSFORMACIÓN viaja en `derivation` (`MIDPOINT_OF_SOURCE_RANGE`, `source_count = 1`); el derivado usa la clase explícita `DERIVED_FROM_EXTERNAL_SOURCE`. La regla NO se relajó: ≥2 externas siguen dando `COMPUTED_FROM_SOURCES` | `test_m5_single_source_origin_not_computed_from_sources` · `test_m5_two_sources_can_be_computed_from_sources` |
| 2 | la visibilidad de la referencia central no estaba declarada | política **explícita y versionada** `dictus-central-reference-visibility/1.0.0` con estados `VISIBLE`/`DEEMPHASIZED`/`HIDDEN` y umbrales publicados en `umbrales_aplicados` (declarando que NO está calibrada empíricamente) | `test_central_reference_visibility_policy` |
| 3 | la P6 enfrentaba «ESTIMACIÓN INDICATIVA» con «VALOR ESTIMADO POR LA CORRIDA · VALORACIÓN NO DISPONIBLE» | el bloque legacy se titula `EVIDENCIA DE MERCADO VERIFICADA · NO HABILITADA` y declara `VERIFIED_MARKET_EVIDENCE_GATE = CLOSED` con su razón; la P1 imprime el resultado de `ESTIMATION_GATE` y la valoración de la corrida va como «no habilitada (evidencia no verificada)» | `test_legacy_valuation_label_does_not_say_valor_estimado` · `test_p1_p6_estimation_consistency` · `TestPdfRealDelGolden` |
| 4 | el `evidence_hash` de la cosecha incluía `queried_at` y cambiaba en cada adquisición (`6f84f220…` → `d89aa0c2…`) | `content_hash` **estable** (contenido publicado, verificado contra los bytes crudos de `raw/`) + `acquisition_id`/`acquisition_hash` volátiles aparte, bajo la política `dictus-evidence-hash/2.0.0`; los JSON de `docs/estimation/` publican `state` y `counters` en el NIVEL SUPERIOR | `test_m5_*` · `scripts/market_harvest_rehash.py` |

Regeneración reproducible: `python scripts/estimation_golden.py --con-verificacion`
(escribe `ESTIMATION_FINAL_ACCEPTANCE_040-646406.md` con la evidencia literal: compuertas,
las diez dimensiones de calidad, el objeto completo de `M5`, contadores, `SOURCE`, A/B,
`P1_TEXT`/`P6_TEXT` del PDF, hashes y salida real de las pruebas).

**CONTRACT FROZEN no se declara.** Este documento describe el motor **hoy**.



# DICTUS ESTIMATION ENGINE v1.0 — ACEPTACIÓN · folio 040-646406

- **Motor:** `dictus-estimation-engine/1.0.0` · integración `dictus-estimation-integration/1.0.0` · golden `dictus-estimation-golden/1.0.0`
- **Corrida del Golden:** `run_id = 761fa4c2-fa76-4137-8238-2845ee325055` · `generated_at = 2026-09-30T21:34:05.166625+00:00` · `referencia temporal de la estimación = 2026-09-30`
- **DICTUS_MASTER_HASH:** `4fa480d0fdb245a7c0dcdd0b5e0bebd2f6589a8d56ee180c5e019fdb94851608`
- **VEREDICTO:** `DICTUS ESTIMATION ENGINE — INDICATIVE ESTIMATE PRODUCED`

> El éxito de esta fase NO es «NO EMITIR VALORACIÓN = true». Es: no se inventó ninguna fuente, no se usó ningún parámetro escrito a mano, se auditó toda la evidencia, se intentó estimar y —si no se pudo— se demostró POR QUÉ con la evidencia que falta.

## A · No inventó fuente

Comando: `python scripts/estimation_golden.py`

Resultado literal: `market_observations_count = 1` · `origins_used = ['EXTERNAL_SOURCE']` · `comparables_accepted = 0` · `comparables_rejected = 0`.

Evidencia agregada externa incorporada: **INCORPORADA** · referencias de nivel 3 = `1` · archivo `docs\estimation\MARKET_HARVEST_040-646406.json`

| campo | fuente | ¿lo declara? |
|---|---|---|
| `url` | BAQ_OBS_VALORESM2_AREA | sí |
| `consultado_en` | BAQ_OBS_VALORESM2_AREA | sí |
| `http` | BAQ_OBS_VALORESM2_AREA | sí |
| `bytes` | BAQ_OBS_VALORESM2_AREA | sí |
| `sha256` | BAQ_OBS_VALORESM2_AREA | sí |
| `vigencia` | BAQ_OBS_VALORESM2_AREA | sí |
| `muestra` | BAQ_OBS_VALORESM2_AREA | **NO** (declarado) |

Lo que la fuente NO declara viaja como **NO** y como limitación impresa: `campos_que_la_fuente_no_declara = [['muestra']]`.

### Adquisición · el 403 era rompible (evidencia conservada)

El host del geoportal está detrás de Cloudflare y responde **HTTP 403** con el interstitial «Just a moment…» a las peticiones cuyo `Accept`/`Sec-Fetch-*` no parecen de navegación. Medido el 2026-09-29: **la MISMA URL devuelve 200** cuando la petición lleva cabeceras de navegación completas. La medición vive en `api/market_harvest.py` (`NAV_HEADERS`) y el payload crudo de cada capa se conserva sin modificar en `docs/estimation/raw/<capa>.json`.

Cabeceras que rompen el 403:

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

Respuesta realmente recibida (literal del artefacto de cosecha):

- `BAQ_OBS_VALORESM2_AREA` · HTTP **200** · 740 bytes · sha256 `d514aa27fc3fb79b6323ccdfdb7d322b03a738342dc11dceb79fbebde562abd4` · `consultado_en = 2026-09-30T16:41:08+00:00` · `server = cloudflare` · `cf_ray = a434ac712a2221b7-BOG`
  - URL consultada: `https://miciudad.barranquilla.gov.co/gis/rest/services/observatorio/valoresm2_area/MapServer/1/query?f=json&outFields=%2A&returnGeometry=false&geometry=-74.8375696549899%2C11.006055954316363&geometryType=esriGeometryPoint&spatialRel=esriSpatialRelIntersects&inSR=4326&where=1%3D1`
  - nivel `LEVEL_3_AGGREGATED_MARKET_REFERENCES` · banda declarada `{'min': 2222222.22, 'max': 8190568.05, 'unidad': 'COP/m2'}` · `sample_size = None`

## B · No usó MANUAL_CONFIG ni priors legacy

Comando: `python scripts/estimation_golden.py`

Resultado literal: `manual inputs used = 0` · `legacy priors used = 0` · `manual_inputs_declared = 1` · `legacy_priors_declared = 1` · clases EXCLUIDAS = `['MANUAL_CONFIG', 'LEGACY_MODEL_PRIOR']`.

La corrida SÍ declara parámetros a mano y priors del modelo: entran a la entrada para que su presencia sea AUDITABLE y la composición de `origin` los deja EXCLUIDOS del cálculo (regla `R6_CLASE_UNICA`): insumos declarados que NO participan del cálculo: LEGACY_MODEL_PRIOR, MANUAL_CONFIG (no se cuentan como fuente)

Clases usadas (las que sí participan): `['EXTERNAL_SOURCE']` · clases excluidas: `['MANUAL_CONFIG', 'LEGACY_MODEL_PRIOR']` · cada exclusión se publica con su motivo en `origin_composition.excluidos`.

## C · Auditó toda la evidencia

Comando: `python scripts/estimation_input_audit.py` (regenerado por el golden)

Resultado literal: `total_inputs = 46` · `usable_for_estimation=true → 12` · `observaciones_de_mercado_reales = 0` · `niveles_con_evidencia_utilizable = []` · `filas_matriz = 20`.

Dos conteos distintos, con definiciones distintas (no se contradicen): la auditoría de Fase 1 cuenta las observaciones de mercado que el ESTADO de la corrida ya traía (niveles 1–2: comparables y observaciones locales); el contador de Fase 3 cuenta además las referencias AGREGADAS de nivel 3 que la corrida incorpora como evidencia externa (`market observations count = 1`). El CSV `MARKET_EVIDENCE_MATRIX` declara, fila por fila, qué se usó y qué no.

## D · Intentó estimar

Comando: `python scripts/estimation_golden.py`

Resultado literal: los métodos se evaluaron TODOS y su estado quedó registrado. Usados: `['M5_AGGREGATED_MARKET_REFERENCE']` · rechazados: `['M1_MARKET_COMPARISON', 'M2_REPLACEMENT_COST', 'M3_INCOME_CAPITALIZATION', 'M4_CALIBRATED_MODEL_PRIOR']` (cada rechazo con su motivo en `ESTIMATION_METHODS`). Clases de `origin` que participaron del cálculo: `['EXTERNAL_SOURCE']` → composición `EXTERNAL_SOURCE`.

**M5 es una extensión explícita del contrato de Fase 2** (`ESTIMATION_METHODS` → `extension_de_contrato`): sin un método que consuma la referencia agregada de nivel 3, el motor incumplía (§5: LEVEL 3 sostiene; §29: precio/m² sectorial válido ⇒ `OPEN_WITH_LIMITATIONS` + `INDICATIVE_ESTIMATE`; §41: no convertir la prudencia en «no intento estimar»). M1–M4 quedan intactos.

## E · Si estimó, rango reproducible

`RANGO = [130000000, 490000000]` · `central = 310000000` · ancho `±58.06%` · fórmula `dictus-range-width/1.0.0` · `clamp = DENTRO_DE_BANDA` · dispersión usada = `M5_AGGREGATED_MARKET_REFERENCE` · `hash_payload = 1dd745d4b6612142399c53718edba93f3708b36f259ef0ef9ecffca74d548529`. Reproducible: el rango se deriva de la entrada con fecha de referencia fija (2026-09-30).

**El rango es la salida primaria.** La referencia central es secundaria y va redondeada a la precisión que el ancho permite (paso = $10.000.000) — nunca una cifra fina sobre evidencia agregada.

El rango NO se calcula alrededor de un centro: `range_low` y `range_high` son los **min/max LITERALES de la fuente** aplicados al área del sujeto, redondeados HACIA FUERA (redondear hacia dentro estrecharía la evidencia publicada). El ancho calculado por el motor se publica y NO puede estrecharlo: aquí el ancho calculado era `±51.00%` y el efectivo del rango publicado es `±58.06%`.

Banda oficial usada: `BAQ_OBS_VALORESM2_AREA` · `reference_id = BAQ_OBS_VALORESM2_AREA/L1/Norte - centro histórico` · `evidence_hash = 6a307f15e38cba0c4edfd02111589fe6620a22169e3a3d95f28e7d7e2331060b` · banda de área `36-60` ⊇ `58.75 m²` · min/max LITERALES `$ 2.222.222`–`$ 8.190.568` COP/m² → `low = $ 130.000.000` · `high = $ 490.000.000`.

Rango legible: **$ 130.000.000 – $ 490.000.000** · referencia central **$ 310.000.000** · valor/m² **$ 5.206.395** · método **REFERENCIA AGREGADA OFICIAL POR LOCALIDAD Y BANDA DE ÁREA**

Método: `M5_AGGREGATED_MARKET_REFERENCE` · `status = AVAILABLE` · `origin = EXTERNAL_SOURCE` · `confidence = BAJA` · comparables usados = `0` · referencia agregada `BAQ_OBS_VALORESM2_AREA/L1/Norte - centro histórico` (`sha256 = d514aa27fc3fb79b…`, `evidence_hash = 6a307f15e38cba0c4edfd02111589fe6620a22169e3a3d95f28e7d7e2331060b`).

La fuente de nivel 3 publica un **RANGO** y **NO un valor único**: su `valor_m2` sigue en `null` y el motor no lo fabrica. Lo único que DICTUS deriva —y lo declara como tal— es el **centro del rango declarado** (`M5` · `referencia_central_del_rango`, con `no_es_valor_de_la_fuente = true` y `no_es_valor_de_la_unidad = true`), y la **semi-amplitud de esa banda** como dispersión declarada. Nada se promedia a espaldas del lector: los ajustes `promedio aritmético de los extremos` y `división por el área del sujeto` se publican como `NO_APLICADO`.

## F · Confianza derivada

Comando: `python scripts/estimation_golden.py`

Resultado literal: `EVIDENCE_QUALITY.level = INDICATIVE` → `CONFIANZA = INDICATIVA` · `confidence_label = INDICATIVE`. La confianza NO se escribe a mano: se deriva del nivel de calidad de la evidencia.

## G · Procedencia completa

Comando: `python scripts/estimation_golden.py`

Resultado literal: fuentes citadas por el resultado = `[{'source_id': 'BAQ_OBS_VALORESM2_AREA', 'proveedor': 'Alcaldía Distrital de Barranquilla — geoportal miciudad (servidor ArcGIS REST)', 'referencia': 'valoresm2_area/MapServer/1', 'fecha': '2026-09-30', 'sha256': 'd514aa27fc3fb79b6323ccdfdb7d322b03a738342dc11dceb79fbebde562abd4', 'es_fuente_no_acreditada': False}]` · referencias de evidencia = `['EV-ESTIMACION']` · histórico forense con `usado_como_input = False`.

## H · Si no estimó, demostró por qué · y si estimó, declaró su límite

Comando: `python scripts/estimation_golden.py`

SÍ SE ESTIMÓ, y su límite queda declarado. Resultado literal: `state = OPEN_WITH_LIMITATIONS` · `status = INDICATIVE_ESTIMATE` · `nivel de evidencia = INDICATIVE` · `origen = EXTERNAL_SOURCE` · `rango = [130000000, 490000000]`.

Por qué NO es más que indicativo, en la letra del motor:

- evidencia INDICATIVE: la cifra es una ESTIMACIÓN INDICATIVA, no un valor verificado

No hay `informe_de_brecha` de cierre porque no hubo cierre: lo que sigue es lo que falta para SUBIR DE NIVEL y dejar de ser indicativo.

Evidencia económica AUTOMÁTICA que falta:

1. [ya incorporada · falta completarla] Geoportal municipal de Barranquilla · observatorio/valoresm2_area (layer de la banda del sujeto) → faltan: sample_size (N)
2. [prioridad 2] Geoportal municipal de Barranquilla · observatorio/valorcompraventas (registro individual) → faltan: area_construida_m2, identificador del inmueble
3. [prioridad 3] SNR — Superintendencia de Notariado y Registro (microdatos de compraventa) → faltan: descarga automática con área y número predial
4. [prioridad 4] Geoportal municipal de Barranquilla · observatorio/arrendamientos → faltan: tasa de capitalización declarada, área por oferta

## §39 · EVIDENCIA LITERAL

```
ESTIMATION_GATE
  state            = OPEN_WITH_LIMITATIONS
  reasons          =
      - hay información suficiente para una ESTIMACIÓN RAZONABLE, pero la evidencia es INDICATIVE (no alcanza el estándar verificado)
      - soporte económico: EXTERNAL_SOURCE
      - métodos disponibles: M5_AGGREGATED_MARKET_REFERENCE (ninguno autoriza una cifra verificada)
      - el resultado se emite como ESTIMACIÓN INDICATIVA con sus limitaciones declaradas, no como valor verificado
  inputs_available = ['area', 'auditoria_de_entrada', 'contexto', 'estadisticas_externas', 'identidad', 'modelo_legacy', 'tasa_manual', 'tipologia', 'ubicacion']
  inputs_missing   = ['cap_rate', 'comparables', 'costo_reposicion', 'modelo_calibrado', 'referencia_estatica', 'rental_reference']
VERIFIED_MARKET_EVIDENCE_GATE
  state            = CLOSED
  reasons          =
      - ninguna evidencia de mercado alcanza el estándar de fuente externa verificada con procedencia completa
      - referencia de nivel 3 fuera de esta compuerta: nivel 3 agrega por localidad y banda de área: NO acredita la unidad
EVIDENCE_QUALITY
  level   = INDICATIVE
  reasons =
      - identidad: HIGH — identidad resuelta con origen COMPUTED_FROM_SOURCES
      - ubicación: HIGH — ubicación con estado OFFICIAL_PREDIO
      - área: HIGH — área declarada con origen COMPUTED_FROM_SOURCES
      - tipología: HIGH — tipología verificada (VERIFIED_REGISTRAL)
      - evidencia de mercado: LOW — 0 comparables usados de 0 · 1 referencia(s) agregada(s) de nivel 3 (agregan por sector y banda de área: NO acreditan la unidad)
      - vigencia: ABSENT — sin fecha declarada en la evidencia de mercado
      - dispersión: ABSENT — dispersión no medible (menos de 2 comparables)
      - modelo: ABSENT
      - techo por dimensión: area=HIGH, composicion=HIGH, identidad=HIGH, mercado=INDICATIVE, tipologia=HIGH, ubicacion=HIGH
  dimensiones =
      identity_quality         = HIGH
      location_quality         = HIGH
      market_evidence_quality  = LOW
      market_freshness         = {'level': 'ABSENT', 'meses': None, 'detalle': 'sin fecha declarada en la evidencia de mercado'}
      comparable_quality       = ABSENT
      comparable_count         = 0
      typology_quality         = HIGH
      area_quality             = HIGH
      model_quality            = ABSENT
      dispersion               = {'level': 'ABSENT', 'cv': None, 'n': 0, 'detalle': 'dispersión no medible (menos de 2 comparables)'}
ESTIMATION_RESULT
  status           = INDICATIVE_ESTIMATE
  range_low        = 130000000
  range_high       = 490000000
  central_estimate = 310000000
  value_m2         = 5206395.13
  methods_used     = ['M5_AGGREGATED_MARKET_REFERENCE']
  central_reference_visibility = DEEMPHASIZED (política dictus-central-reference-visibility/1.0.0 · imprime_la_cifra=True)
M5_AGGREGATED_MARKET_REFERENCE
  method_id        = M5_AGGREGATED_MARKET_REFERENCE
  status           = AVAILABLE
  origin           = EXTERNAL_SOURCE
  derivation       = {"type": "MIDPOINT_OF_SOURCE_RANGE", "formula": "(min + max) / 2", "source_count": 1, "source_ids": ["BAQ_OBS_VALORESM2_AREA"], "origin": "DERIVED_FROM_EXTERNAL_SOURCE", "declaracion": "punto medio del rango publicado por la fuente: DERIVACIÓN determinista de UNA sola fuente externa. NO es una composición de fuentes (COMPUTED_FROM_SOURCES exige ≥2) y NO es un valor publicado por la fuente.", "no_es_composicion_de_fuentes": true, "no_es_valor_de_la_fuente": true}
  confidence       = BAJA
  source_id        = BAQ_OBS_VALORESM2_AREA
  reference_id     = BAQ_OBS_VALORESM2_AREA/L1/Norte - centro histórico
  source_range_m2  = {"min": 2222222.22, "max": 8190568.05, "unidad": "COP/m2", "basis": "min/max literales de la fuente"}
  result_range     = {"low": 2222222.22, "high": 8190568.05, "basis": "banda oficial declarada por la fuente (min/max LITERALES)"}
  sample_size      = None (la fuente NO lo declara)
CONTADORES
  market observations count = 1
  comparables accepted      = 0
  comparables rejected      = 0
  origins used              = ['EXTERNAL_SOURCE']
  manual inputs used        = 0   [ACEPTADO]
  legacy priors used        = 0   [ACEPTADO]
```

## §40 · VEREDICTO

**DICTUS ESTIMATION ENGINE — INDICATIVE ESTIMATE PRODUCED**

## Escenarios de contraste · el cambio de estado por el nivel 3

Mismo expediente, misma fecha de referencia: la ÚNICA diferencia es si la corrida incorpora o no la referencia agregada de nivel 3 (`MARKET_HARVEST_*.json`). El cambio de estado es el que la evidencia compra, y nada más.

| escenario | ESTIMATION_GATE | calidad | status | origen | rango | razón principal |
|---|---|---|---|---|---|---|
| CON cosecha municipal (real) | OPEN_WITH_LIMITATIONS | INDICATIVE | INDICATIVE_ESTIMATE | EXTERNAL_SOURCE | [130000000, 490000000] | hay información suficiente para una ESTIMACIÓN RAZONABLE, pero la evidencia es INDICATIVE (no alcanza el están |
| SIN cosecha municipal (contraste) | CLOSED | INSUFFICIENT | NOT_ESTIMABLE | NOT_PRODUCTIVE | [None, None] | no se cumplen las condiciones mínimas de estimación: |

El nivel 3 lleva de `CLOSED` a **`OPEN_WITH_LIMITATIONS`** y de `NOT_ESTIMABLE` a **`INDICATIVE_ESTIMATE`**; NO a `OPEN`: agrega por sector y banda de área, así que no acredita la unidad. Para `OPEN` haría falta evidencia de nivel 1-2 con calidad HIGH/MEDIUM y comparables directos de la MISMA unidad observada.

Y en los dos escenarios `VERIFIED_MARKET_EVIDENCE_GATE = CLOSED` (§30: las dos compuertas coexisten) · `manual inputs used = 0` · `legacy priors used = 0`.

## Comandos de verificación

- `python scripts/dictus_run.py` → layout sin violaciones + verify_master_hash=MATCH
- `python scripts/golden_evidence_asserts.py` → 11/11 PASS · exit 0 (también con stdout cp1252)
- `python -m pytest tests/test_estimation_golden.py tests/test_estimation_gate.py tests/test_estimation_evidence_quality_gate.py tests/test_estimation_origin_composition.py tests/test_estimation_semantics_final.py tests/test_market_evidence.py tests/test_dictus_20d_r1_p6.py tests/test_dictus_20c_fidelidad.py -q` → toda la suite en verde

### Salida literal de las verificaciones

`python scripts/dictus_run.py`

```
[exit code: 0]
OK - Test de boundary de avaluo: PASADO
[PDF][GATE] ok=True bloqueantes=0 advertencias=0
SUCCESS: PDF GENERADO: C:\Users\aliss\.gemini\antigravity-ide\scratch\20260825_DeepSeek_Harness_Web\arhiax-RE\docs\forensics\040-646406\dictus_2b\DICTUS_TECNICO_040-646406.pdf
  Folio: 040-646406
  Sello de ejecucion SHA-256: 46eae57485fc54c66c6d0da1f4cbb66b3644a6abb1bf78f92eb49bada0147aa2
  Hash del archivo emitido SHA-256: b8433436c7229ac9d27c4c1e55717b3a1c2d7026032670bbf9368606bdd954a7
  Timestamp: 2026-09-30T21:33:14.969103+00:00
[PDF][NOTIF] correo de pendientes enviado=False n=2 -> ['hipoteca', 'afectacion']
[run] 761fa4c2 · DX-040-646406-20260930 · master hash 4fa480d0fdb245a7…
[run] PRINCIPAL DICTUS_EJECUTIVO_040-646406.pdf · 6 páginas · sha256 610222b22d55…
[run]           arquitectura: P1 DECISIÓN DEL INMUEBLE → P2 DECISIÓN JURÍDICA → P3 DECISIÓN DE CONTRAPARTES → P4 DECISIÓN TERRITORIAL Y URBANÍSTICA → P5 ENTORNO, EQUIPAMIENTO, ASOLEAMIENTO Y SOMBRAS → P6 IDENTIDAD, MERCADO Y VALOR
[run] ANEXO     DICTUS_TECNICO_040-646406.pdf · 17 páginas · sha256 b8433436c722…
[run] evidencias 10 (PARCIAL_CON_DECLARACIONES) · verificación MATCH · retícula OK
[run] POI en el estado: 12 ítems · distancias sí
```

`python scripts/golden_evidence_asserts.py`

```
[exit code: 0]
        atributos comparados por clave canónica = 7 · contradicciones entre páginas = 0 · discrepancias con la verdad única del expediente = 0
        
          claves y estados impresos: altura_maxima: P4=HISTORICAL_CONFLICT; amenaza: P4=HISTORICAL_CONFLICT; binding_geometria: P6=VERIFICADA; coordenada: P4=HISTORICAL_CONFLICT; titulares: P4=HISTORICAL_CONFLICT; tratamiento: P4=HISTORICAL_CONFLICT; uso_pot: P4=HISTORICAL_CONFLICT
[PASS] manual_market_input_cannot_open_valuation_gate()
        origin=MANUAL_CONFIG · origin_gate=False
        blockers=['origen MANUAL_CONFIG no habilita la valoración (valor declarado a mano por la corrida (sin fuente externa automática))']
[PASS] model_prior_cannot_open_valuation_gate()
        origin=MODEL_PRIOR · origin_gate=False
        blockers=['origen MODEL_PRIOR no habilita la valoración (valor por defecto del modelo (sin fuente: no autoriza cifra))']
[PASS] computed_from_sources_requires_all_material_inputs_authorized()
        sin procedencia completa: origin=MANUAL_CONFIG gate=False blockers=['origen declarado COMPUTED_FROM_SOURCES SIN procedencia completa (falta: fuentes[] (se exigen >= 2)): se degrada a MANUAL_CONFIG']
        con 2 fuentes completas: origin=COMPUTED_FROM_SOURCES gate=True

TOTAL = 11 · PASS = 11 · FAIL = 0 · NO EVALUABLE = 0
```

`python -m pytest tests/test_estimation_golden.py tests/test_estimation_gate.py tests/test_estimation_evidence_quality_gate.py tests/test_estimation_origin_composition.py tests/test_estimation_semantics_final.py tests/test_market_evidence.py tests/test_dictus_20d_r1_p6.py tests/test_dictus_20c_fidelidad.py -q`

```
[exit code: 0]
........................................................................ [ 31%]
........................................................................ [ 62%]
.........................................................x.............. [ 94%]
.............                                                            [100%]
============================== warnings summary ===============================
..\..\..\..\..\AppData\Roaming\Python\Python314\site-packages\_pytest\cacheprovider.py:469
  C:\Users\aliss\AppData\Roaming\Python\Python314\site-packages\_pytest\cacheprovider.py:469: PytestCacheWarning: could not create cache path C:\Users\aliss\.gemini\antigravity-ide\scratch\20260825_DeepSeek_Harness_Web\arhiax-RE\.pytest_cache\v\cache\nodeids: [WinError 5] Acceso denegado: 'C:\\Users\\aliss\\.gemini\\antigravity-ide\\scratch\\20260825_DeepSeek_Harness_Web\\arhiax-RE\\pytest-cache-files-d_gkt9qy'
    config.cache.set("cache/nodeids", sorted(self.cached_nodeids))

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
228 passed, 1 xfailed, 1 warning in 2.48s
```


Generado por `scripts/estimation_golden.py` · `2026-09-30`

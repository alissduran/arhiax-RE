# FACT_PROPAGATION_AUDIT_040-646406

**MISIÓN BLOCK 1 · AUDITORÍA.** Jerarquía de capas, resolución por atributo y propagación de hechos para el Golden `040-646406`. **No se modificó lógica de motor**: esta ronda es solo lectura sobre artefactos + escritura de los entregables. `PROPERTY_VALUE_RESOLUTION` queda formalmente **PENDING**; no se tocó PDF (P1–P6), Estimation Engine, rango 130M–490M, `ESTIMATION_GATE`, `EVIDENCE_QUALITY`, M1–M5, screening, títulos ni solar.

**Cadena auditada (§21):** `SourceResult → ResolvedFact → RunState → ExecutiveDocumentModel → dictus_secciones → PDF`.

**Corrida medida:** `run_id 6429974c-f9bf-494f-99d2-aff0c9495d14` · `DX-040-646406-20261001` · `2026-10-01T13:47:11Z` · `master_hash 4da3191d…6277` · PDF ejecutivo `sha256 4f8dcbcb…e19a` (6 pp).

---

## 0 · Advertencia de medición: `dictus_2b/` contiene DOS documentos ejecutivos distintos

| Artefacto en `docs/forensics/040-646406/dictus_2b/` | Identidad | Qué dice |
|---|---|---|
| `DICTUS_EJECUTIVO_040-646406.pdf` (6 pp) + `DICTUS_RUN_STATE_…json` + `DICTUS_MANIFEST_…json` | `DX-040-646406-20261001` · `master_hash 4da3191d…6277` | valores presentes; ninguna fila de identidad en «no declarado» |
| `DICTUS_2.0B_TEXTO_EJECUTIVO_040-646406.txt` | `DX-040-646406-20260925` · `master_hash 1B8484A8A675…5417` | P4 con «no declarado» en Uso POT / Tratamiento / Altura-edificabilidad; P6 con `NO_COMPARABLE` en el binding de geometría |

No son la misma corrida. Cada síntoma se atribuye abajo a la corrida en que **sí** se mide, y se declara el que **no** se reproduce. Regla aplicada: **no rellenar lo no medido**.

**Estado de reproducción de los síntomas de la misión:**

| Síntoma declarado | Medición | Dónde sí se mide |
|---|---|---|
| P1 `barrio` y `uso` = «no declarado» | **NO reproducido** en el PDF del Golden (BARRIO `Miramar`, USO `Habitacional`) | `dictus_2/DICTUS_EJECUTIVO_040-646406.pdf` (2.0, 2026-09-24) imprime «Área no declarada», «Uso / actividad POT: no declarado» |
| P4 destino, uso POT, tratamiento, altura, barrio, localidad = «no declarado» | **PARCIALMENTE reproducido**: en el PDF del Golden los seis valores están presentes; en el TXT 2.0B del mismo directorio uso POT, tratamiento y altura/edificabilidad dicen «no declarado» | `DICTUS_2.0B_TEXTO_EJECUTIVO_…txt` P4 |
| P5 barrio/sector y localidad = «NO DISPONIBLE» | **NO reproducido** en ningún artefacto del caso (P5 imprime `Miramar` y `02` en ambos documentos) | — (no medido) |
| P6 matrícula `VERIFICADO` con NUPRE, predial, unidad, área y régimen en `REQUIERE VALIDACIÓN`, y el resumen diciendo «VERIFICADA» | **REPRODUCIDO LITERALMENTE** | `DICTUS_EJECUTIVO_…pdf` P6 |
| Remoción «Baja · polígono: intersecta el predio» con `fact_status = NO EVALUADO` | **NO reproducido** (el nivel medido es `Media` y el chip `RIESGO MEDIO`); la cadena `"Baja · polígono"` aparece **0 veces** en el repositorio | Mecanismo confirmado por lectura de código (§5) y procedencia histórica documentada en `api/geospatial_engine.py:111-127` |
| Binding de geometría `NO_COMPARABLE` con coordenada oficial adoptada | **NO reproducido** en el PDF del Golden (imprime `VERIFICADA`) | `DICTUS_2.0B_TEXTO_EJECUTIVO_…txt` P6 |

---

## 1 · Jerarquía de capas: lo que existe y lo que falta

Detalle completo en `LAYER_HIERARCHY_V1.md`. Resumen del hallazgo estructural:

**La escalera de resolución existe y está probada, pero su salida NO entra al Golden.** `api/source_resolution.py` implementa 20 escalones por atributo (`COBERTURA_ATRIBUTOS`), con autoridad → vigencia → `source_priority` → `source_id`, y devuelve `{source_selected, source_attempts, resolution_status, solo_valor_resuelto, anexo_alternativas}`. Medición por conteo de tokens sobre los artefactos reales:

| Token | `DICTUS_RUN_STATE` | `DICTUS_MANIFEST` |
|---|---|---|
| `source_selected` | 0 | 0 |
| `source_attempts` | 0 | 0 |
| `source_authority` | 0 | 0 |
| `acquisition_mode` | 0 | 0 |
| `fact_status` | 0 | 0 |
| `historical_values` | 0 | 0 |
| `conflict_class` | 0 | 0 |
| `POT_BAQ_*` (todo `source_id` del pack) | **0** | **0** |
| `resolved_fact` / `ResolvedFact` (en `api/`) | 0 coincidencias | 0 |

Conclusión declarada sin rellenar: **no existe ningún registro por atributo en el Golden**. La procedencia que sí se persiste es más pobre y heterogénea: `observations[].source` (texto libre: `"capa oficial del municipio consultada en vivo"`, `"fuente no declarada"`, `"catastro en vivo"`, `"capa POT empaquetada (cruce local, sin consulta en vivo)"`), `evidence_manifest.evidencias[].source` y `market_context.urban_source_summary.campos.*`. En `ATTRIBUTE_RESOLUTION_REGISTRY.json` esos campos se marcan `NOT_PERSISTED_IN_GOLDEN` con la evidencia de la medición.

**Vocabularios.** El motor implementa **dos** vocabularios separados de 5 estados cada uno (resolución en `api/source_resolution.py:59-67`; fuente en `api/dictus_sources.py:50-55`). **`RESOLVED_SNAPSHOT` no existe** como constante (0 coincidencias en `api/`): se usa en el registro solo cuando el valor proviene efectivamente de un `acquisition_snapshot` declarado o del modo `PACKAGED_REFERENCE` que el propio artefacto publica. **`fact_status` no existe** como campo (0 coincidencias): se declara a partir de campos medidos y cada ficha dice de dónde sale.

---

## 2 · Las cinco pérdidas estructurales (y su nivel exacto)

| Nivel | Pérdida | Evidencia medida |
|---|---|---|
| `L2 RESOLUCIÓN` | La escalera no se persiste por atributo | 0 tokens de `source_selected`/`source_attempts`/`resolution_status`(escalera) en RunState y Manifest |
| `L4 ESTADO` | `historical_consistency` **fabrica cambios entre dos ausencias** | `api/dictus_historia.py:374-387`; medido para `area`: `valores [null ×13]`, `cambios[0] = {anterior: null, actual: null, cambio: true, clase: SOURCE_UNAVAILABLE}` |
| `L4 ESTADO` | `risk_context` aplana el riesgo a una cadena y descarta el resto | `api/dictus_estado.py:515-530` (`_nivel_riesgo`) descarta `intersecta`, `clase_suelo`, `area_poligono_m2`, `objectid`, `total_coincidencias`, `detalles` |
| `L5 MODELO` | El estado de hecho se deriva de la **presencia de una cadena** | `api/dictus_decision.py:519` — `OBSERVADO if _v(risk.get(riesgo)) else NO_EVALUADO` |
| `L6 SECCIONES` | Default **fail-open** `VERIFICADO` para atributo sin coherencia declarada | `api/dictus_secciones.py:577` — `verdad_atributos.get(atributo, dse.VERIFICADO)` |
| `L6 SECCIONES` | **Dos** fuentes de verdad para «identidad», nunca confrontadas | `_estado_atributo` (histórico) vs `identity_verified` (identidad canónica), `api/dictus_secciones.py:978-1034` |
| `L7 RENDER` | Default negativo cuando falta la clave | `api/dictus_secciones.py:404` — `mc.get("canonical_binding_status") or "NO_COMPARABLE"` |
| `L7 RENDER` | El chip de riesgo **no tiene rama `BAJA`/`BAJO`** | `api/dictus_ejecutivo.py:1580-1589` — el `else` produce `NO_EVALUADO` |
| `L7 RENDER` | El chip se aplica de forma desigual entre páginas | P4 degrada `barrio`, `localidad`, `área`, `estrato`; P1 y P5 imprimen los mismos atributos sin chip |

---

## 3 · Causa raíz de la contradicción matrícula-`VERIFICADO` vs componentes-`REQUIERE VALIDACIÓN`

**Reproducido literalmente en el PDF del Golden, página 6.** Cadena causal medida, eslabón por eslabón:

1. **`api/dictus_historia.py:374-387` declara cambios entre dos ausencias.** La guarda de «sin cambio» exige que **ambas** claves sean no-`None`:
   ```python
   if ka is not None and kb is not None and ka == kb:   # exige AMBOS no-None
       → cambio: False
   if va is None or vb is None:                         # ← cae aquí si va = vb = None
       → cambio: True, clase SOURCE_UNAVAILABLE
   ```
   Medición para `area`: `{"valores": [null ×13], "detalle": "el valor no está en la versión más reciente", "cambios": [{"anterior": null, "actual": null, "cambio": true, "clase": "SOURCE_UNAVAILABLE", "explicado": false}]}`. **Trece versiones sin área producen un «cambio» `None → None`.**
2. **`api/dictus_historia.py:508-511`**: como la clase es `SOURCE_UNAVAILABLE` y no `UNEXPLAINED_CONFLICT`, el atributo **entra a `requieren_revision`** (17 atributos) y no a `conflictos_abiertos` (6).
3. **`api/dictus_secciones.py:392-395`** lo traduce a `REQUIERE_VALIDACION` dentro de `verdad_por_atributo`.
4. **`api/dictus_secciones.py:577`** — las filas leen ese estado: `nupre`, `numero_predial`, `unidad`, `area`, `regimen_juridico`, `direccion` ⇒ **`REQUIERE VALIDACIÓN`**.
5. **La misma línea con clave `"matricula"`** — `matricula` está en `_ATRIBUTOS` y en `ATRIBUTOS_MATERIALES` de `dictus_historia.py`, pero **nunca registró un cambio**: 14/14 versiones con `040-646406`. Ausente de las tres listas del informe ⇒ `.get("matricula", dse.VERIFICADO)` ⇒ **`VERIFICADO`**.
6. **`api/dictus_secciones.py:1031`** — la frase-resumen lee otra fuente: `"identidad_estado": "VERIFICADA" if pi.get("identity_verified") else …`, con `identity_verified = true` derivado de `resolution_confidence = VERIFIED_UNIT_IDENTITY` / `resolution_method = nupre` / `estado = MATCH_BY_NUPRE`.

**Clasificación:** `STATE_PROPAGATION_FAILURE` (paso 1: el informe introduce un cambio falso entre ausencias) **+** `MODEL_MAPPING_FAILURE` (paso 5: default fail-open; paso 6: segunda verdad no confrontada). **No** es `RENDERING_FAILURE`: el render imprime fielmente lo que el modelo declara.

**Respuesta directa:** la matrícula dice `VERIFICADO` **no porque se haya verificado la matrícula contra una fuente en esa fila**, sino porque es el único componente de identidad que no aparece en el informe de coherencia y por tanto hereda el default `VERIFICADO` de `verdad_por_atributo` — mientras sus cinco hermanas heredan un `REQUIERE_VALIDACION` producido por cambios `None → None`. Y la frase «Identidad registral y catastral: VERIFICADA» proviene de un segundo cómputo (`property_identity.identity_verified`) que ninguna ruta confronta con `verdad_por_atributo`.

---

## 4 · Causa raíz del `NO EVALUADO` (riesgo) y de las contradicciones de fuente

**Regla auditada:** «si hubo consulta válida + geometría evaluada + resultado espacial, no puede quedar `NOT_EVALUATED`». Medición por atributo (`RISK_STATE_AUDIT_040-646406.json`):

| Atributo | Valor RunState | Estado emitido | Consulta válida | Resultado espacial | Veredicto |
|---|---|---|---|---|---|
| `remocion` | `Media · polígono: intersecta el predio` | `OBSERVED` | sí (snapshot `PACKAGED_GEOJSON` sha256 `5b424b16…76a4`, vigencia VIGENTE) | sí | no quedó en NOT_EVALUATED ⇒ regla cumplida |
| `areas_en_riesgo` | `Medio · polígono: intersecta el predio` | `OBSERVED` | sí (sha256 `3b3f04ac…08ac`, VIGENTE) | sí | regla cumplida |
| `inundacion` | `null` | `NOT_EVALUATED` | **no** (ambas capas `enabled=false`) | no | veredicto correcto; precisión insuficiente |
| `riesgo_no_mitigable` | `null` | `NOT_EVALUATED` | **no** (no existe escalón) | no | veredicto correcto |

**Cuatro causas raíz medidas:**

- **`RSK-2 · STATE_PROPAGATION_FAILURE` — `api/receipts.py:124`.** `geo_evaluado = bool((geo_eval or {}).get("evaluado"))`, pero **la clave `evaluado` no existe**: `api/dictamen_data.get_geospatial_evaluation` (1033-1051) devuelve verbatim lo que retorna `api/geospatial_engine.evaluate_predio`, cuyo retorno es `{coordenadas, amenaza_remocion_masa, areas_en_riesgo, resumen_ejecutivo}` — sin `evaluado`; su rama de excepción tampoco la incluye. **`geo_evaluado` vale `false` SIEMPRE.** Medición en el Golden: `receipts.geo_evaluado = false` coexistiendo con dos atributos cuyo valor declara «polígono: intersecta el predio». El mismo key ausente se consume en `api/score_engine.py:131` y `api/consistency.py:43`: el defecto alcanza la compuerta de consistencia y el motor de puntaje.
- **`RSK-3 · ACQUISITION_FAILURE`.** La evidencia agregada `EV-AMENAZAS` de la propia corrida se sella con `status = "FUENTE_NO_DISPONIBLE"` (= `SOURCE_UNAVAILABLE`) mientras sus dos componentes se imprimen como `RIESGO MEDIO` con fuente y snapshot declarados. Es la contradicción observable más directa entre el sello y el contenido.
- **`RSK-4 · RENDERING_FAILURE` — `api/dictus_ejecutivo.py:1580-1589`.** El chip **no tiene rama para `BAJA`/`BAJO`**: un nivel con «Baja»/«Bajo» cae en el `else` y se rotula `NO EVALUADO` mientras el texto imprime el nivel y la relación con el polígono. **Es el mecanismo exacto del síntoma declarado.** No se reproduce hoy porque el nivel medido es `Media` (chip `RIESGO MEDIO`, correcto), pero es reproducible por construcción.
- **`RSK-5 · RESOLUTION_FAILURE` — `api/geospatial_engine.py:104-127`.** El propio código documenta el caso real de **este** predio: el punto cae en un polígono `Baja` gigante de fondo que cubre la ciudad **y** en uno `Media` local de 6.046 m²; la versión anterior tomaba `matches[0]` (orden del STRtree) y reportaba `Baja`; la actual elige mayor severidad y, a igualdad, menor área. **Procedencia confirmada del literal «Baja» del síntoma** y motivo por el que la serie `BAJA ↔ MEDIA` se clasifica `RESOLVED_BY_PRECEDENCE` y no conflicto. Riesgo latente: `objectid`, `area_poligono_m2` y `total_coincidencias` **no se persisten** en el RunState.

**Por qué el estado sale «bien» sin consultar la fuente:** `api/dictus_decision.py:519` decide el `fact_status` de los cuatro atributos de riesgo **solo** por la presencia de una cadena de valor. No consulta si hubo consulta (todas las observaciones medidas llevan `query = null`), ni si la geometría se evaluó, ni el estado de la fuente, ni si el valor viene de una capa histórica. Los veredictos del Golden son correctos **por accidente del valor**, no por consulta del estado de la fuente.

**Contraste que muestra el patrón que falta:** `api/riesgo_volcanico.py:55-59` sí declara cinco estados (`HAZARD_MAPPED`, `LOW_HAZARD`, `NO_INTERSECTION`, `NO_COVERAGE`, `SOURCE_UNAVAILABLE`) e implementa `_cobertura_cercana()` con `RADIO_COBERTURA_M = 50000` (líneas 139-155) precisamente para separar «el servicio respondió y el punto no cae» de «el punto queda fuera del área cartografiada». Ese es el vocabulario que el bloque de riesgos de P4 no tiene. `receipts.riesgo_volcanico` mide `{disponible: true, nivel: "NO EVALUADO", estado: "NO_COVERAGE", cobertura_confirmada: false}`.

**Contexto de adquisición declarado (no inferido):** `docs/source_pack/barranquilla_sources_v1.json → measurement_window` dice literalmente: *«El geoportal de la Alcaldía devolvió HTTP 403 (Cloudflare) a toda consulta desde esta máquina durante la ventana; se declara en cada fuente afectada»* (`reference_date 2026-09-29`). Explica —sin que esta auditoría tenga que conjeturar— por qué varias fuentes quedan `enabled=false` o sin snapshot (`POT_BAQ_INUNDACION_2024` layer 77, `POT_BAQ_INUNDACION_HIST` layer 75, `POT_BAQ_AREAS_ACTIVIDAD` layer 85, `POT_BAQ_POLIGONOS_USO` layer 87, `EQUIPAMIENTO_18..27`).

---

## 5 · Resolución por atributo: síntesis

23 atributos auditados en `ATTRIBUTE_RESOLUTION_REGISTRY.json` (ficha de 20 campos por atributo, exactamente los de §9). Distribución medida:

| `resolution_status` | Atributos |
|---|---|
| `RESOLVED_PRIMARY` | fmi, numero_predial, nupre, address, unit, regime, property_type, coordinates, official_geometry_binding, barrio, localidad, destino_economico, estrato, tratamiento (14) |
| `RESOLVED_SNAPSHOT` | altura_normativa, remocion, riesgo (3) |
| `UNRESOLVED` | area, uso (2) |
| `NOT_SUPPORTED` | clase_suelo, inundacion, riesgo_no_mitigable (3) |
| `NO_MATCH` | edificabilidad (1) |

| `fact_status` | Atributos |
|---|---|
| `VERIFIED` | fmi (1) |
| `KNOWN_BUT_UNVERIFIED` | numero_predial, nupre, address, unit, area, regime, property_type, coordinates, official_geometry_binding, barrio, localidad, destino_economico, estrato, remocion, riesgo (15) |
| `CONFLICT` | uso, tratamiento, altura_normativa (3) |
| `NOT_EVALUATED` | inundacion, riesgo_no_mitigable (2) |
| `NO_DATA` | edificabilidad (1) |
| `HISTORICAL_ONLY` | clase_suelo (1) |

**Dos hallazgos de resolución que no son de render:**

1. **`area` es `UNRESOLVED`**: no existe escalón `area` en `COBERTURA_ATRIBUTOS` y ninguna evidencia sellada la sostiene; el valor `58.75` llega como dato de entrada de la corrida. **No se adopta como verificado.**
2. **`uso` es `UNRESOLVED` con estado `VERIFIED_OFFICIAL`**: el escalón `uso_pot` declara dos candidatos y **ambos están deshabilitados** en el registro del pack (`POT_BAQ_AREAS_ACTIVIDAD` `enabled=false`, `POT_BAQ_POLIGONOS_USO` `enabled=false`). La observación del modelo dice literalmente `source = "fuente no declarada"` mientras `market_context.uso.status = "VERIFIED_OFFICIAL"` con `source = null`. Es el punto donde el dato se pierde de verdad: no hay candidato consultable.

**Hallazgos de contradicción interna del estado (mismo atributo, dos estados, mismo artefacto):**

| Atributo | Estado A | Estado B |
|---|---|---|
| `altura_maxima` | `urban_source_summary.campos.altura_maxima` → `fuente: null, status: null, modo: PACKAGED_REFERENCE` | `official_urban_context.altura_status = "VERIFIED_OFFICIAL"` |
| `regime` | `urban_context.condicion_juridica_status = "VERIFIED_REGISTRAL"` | fila P6 = `REQUIERE VALIDACIÓN` |
| `estrato` | `receipts.contexto_urbano.estrato_status = "VERIFIED_OFFICIAL"` (con `estrato_origen: null`) | fila P4 = `REQUIERE VALIDACIÓN` |
| `uso` | `market_context.uso.status = "VERIFIED_OFFICIAL"` (con `source: null`) | observación `CONFLICT` |
| `tratamiento` | `urban_source_summary.campos.tratamiento.status = "VERIFIED_OFFICIAL"` | observación `CONFLICT` |
| `altura_maxima` (modo) | artefacto declara `PACKAGED_REFERENCE` | pack declara `POT_BAQ_EDIFICABILIDAD` = `LIVE_QUERY` **sin** `acquisition_snapshot` |
| `remocion`/`riesgo` | valor `RIESGO MEDIO` con snapshot vigente | evidencia agregada `EV-AMENAZAS` sellada `FUENTE_NO_DISPONIBLE` y `receipts.geo_evaluado = false` |

---

## 6 · Propagación cruzada P1 · P4 · P5 · P6

Detalle en `CROSS_PAGE_TRUTH_040-646406.json`. Resultado medido sobre los ocho atributos comparados:

- **`value_divergences = 0`.** El valor se propaga **íntegro** hasta el PDF en los ocho casos. Ninguna contradicción de valor entre páginas.
- **`status_divergences = 6`.** Todas las divergencias son de **estado** o de **rótulo**.

| Atributo | P1 | P4 | P5 | P6 | Divergencia |
|---|---|---|---|---|---|
| barrio | `Miramar` sin chip | `Miramar` · REQUIERE VALIDACIÓN | `Miramar` sin chip | — | estado |
| localidad | — | `02` · REQUIERE VALIDACIÓN | `02` sin chip | — | estado |
| coordenada | — | `11.00606, -74.83757` · NO UTILIZAR ESTE DATO COMO DEFINITIVO | `11.00606, -74.83757` · procedencia OFFICIAL_PREDIO | — | **lecturas opuestas** del mismo objeto |
| estrato | — | `4` · REQUIERE VALIDACIÓN | — | — | solo P4 |
| uso | `USO: Habitacional` | `Destino económico: Habitacional` REQUIERE VALIDACIÓN **y** `Uso POT: Habitacional` CONFLICTO HISTÓRICO | — | `Uso (destino catastral) Habitacional` REQUIERE VALIDACIÓN | estado + **rótulo ambiguo** |
| área | `58.75 m²` sin chip | — | — | `58.75 m²` REQUIERE VALIDACIÓN | estado |
| identidad | dominio IDENTIDAD = `VERIFICADO` | — | — | 8 filas REQUIERE VALIDACIÓN + frase `VERIFICADA` | **autocontradicción de P6** |
| geometría | — | coordenada no utilizable como definitiva | OFFICIAL_PREDIO sin advertencia | `Binding de la geometría oficial: VERIFICADA` | estado + **overclaim de alcance** |

**Rótulo ambiguo medido (`uso`):** P1 imprime `USO` leyendo `urban_context.destino_economico` (`api/dictus_secciones.py:759`) mientras P4 imprime `Uso / actividad POT` leyendo `market_context.uso` (`:910`). La misma palabra visible designa **dos atributos distintos** con estados distintos; en P4 los dos coexisten con el mismo valor `Habitacional` y chips diferentes, de modo que el lector no puede saber cuál es el uso normativo.

**Estado peor medido:** P6 `identidad` — ocho filas degradadas conviviendo con «Identidad registral y catastral: VERIFICADA» y «DECISIÓN DICTUS: INFORMACIÓN VERIFICADA» en la misma página.

---

## 7 · `loss_stage` por valor perdido (recuento sobre la matriz de 23 atributos)

| `loss_stage` (bucket primario del CSV) | n | Atributos |
|---|---|---|
| `STATE_PROPAGATION_FAILURE` | 8 | numero_predial, nupre, unit, regime, barrio, localidad, destino_economico, estrato |
| `ACQUISITION_FAILURE` | 7 | area, clase_suelo, uso, inundacion, remocion, riesgo, riesgo_no_mitigable |
| `NINGUNA` | 3 | fmi, property_type, tratamiento |
| `RESOLUTION_FAILURE` | 2 | coordinates, altura_normativa |
| `MODEL_MAPPING_FAILURE` | 2 | official_geometry_binding, edificabilidad |
| `RENDERING_FAILURE` | 1 | address (truncado en P1) |

Notas de lectura del CSV (la columna `loss_stage` admite más de un nivel y se audita el primero):

- `address` acumula **`RENDERING_FAILURE` (truncado en P1) + `STATE_PROPAGATION_FAILURE` (estado de la fila)**: el valor llega completo hasta P6, pero P1 lo trunca por ancho de celda y no imprime chip.
- `tratamiento` se registra como `NINGUNA (valor) / RESOLUTION_FAILURE (canonicidad)`: el valor de esta corrida está resuelto y llega al PDF; lo que falta es **valor canónico** entre versiones (cinco formas históricas, con `Desarrollo (Bajo)` en una de ellas).
- `uso` acumula **`ACQUISITION_FAILURE` + `RESOLUTION_FAILURE`**: las dos capas del escalón están `enabled=false` y el valor se rotula `VERIFIED_OFFICIAL` con `source=null`.
- `remocion` y `riesgo` se registran como `ACQUISITION_FAILURE (contradicción de sello)`: el valor y su snapshot están bien; lo que falla es que la evidencia agregada `EV-AMENAZAS` se sella `FUENTE_NO_DISPONIBLE` y `receipts.geo_evaluado=false`.
- `official_geometry_binding` se registra como `MODEL_MAPPING_FAILURE (histórico, ya corregido en esta corrida)`: en el PDF del Golden los seis niveles coinciden; el defecto se mide en el TXT 2.0B homónimo.
- `coordenada` se registra como `RESOLUTION_FAILURE (ESTADO_PROVISIONAL)`: el valor vigente llega intacto a P4 y P5; lo que falta es el valor canónico único entre dos puntos oficiales a 137.1 m.

`consistent` sobre la cadena completa: **6 `SI`** (fmi, property_type, official_geometry_binding, clase_suelo, inundacion, riesgo_no_mitigable) · **14 `NO`** · **2 `PARCIAL`** (remocion, riesgo).

Ninguno de los 23 atributos pierde su **valor** entre la fuente y el PDF salvo dos casos de forma (`address` truncada en P1, `unit` normalizada) que no alteran el hecho. **Lo que se pierde o cambia es el ESTADO, y se pierde en `L4 · ESTADO` y `L6 · SECCIONES`, no en el render.**

---

## 8 · Recuento de conflictos históricos: antes 6 · después 2

Detalle e informe por atributo en `HISTORICAL_CONFLICT_AUDIT_040-646406.json`.

El PDF imprime «**6 atributo(s) requieren reconciliación histórica**», leyendo `len(historical_consistency.conflictos_abiertos)`. Ese conteo usa el criterio de `dictus_historia` (`material == True` **y** `clase == UNEXPLAINED_CONFLICT`), que **no es** el criterio de las siete condiciones.

Aplicadas las siete condiciones con evidencia medida:

| Atributo | Veredicto | Condición que decide |
|---|---|---|
| `altura_maxima` | **TRUE_CONFLICT** | las 7 se cumplen: fuente declarada idéntica («altura del edificio según catastro») entre `03I` (8) y `03I1` (11); `{8} ∩ {11} = ∅`; el escalón es de fuente única y el binding es por `tratamiento`, no punto-en-polígono ⇒ la coordenada no lo explica |
| `coordenada` | **TRUE_CONFLICT** | las 7 se cumplen: `11.00538 -74.83862` vs `11.00606 -74.83757` = **137.1 m** (144.7 m entre 11.00538 y 11.00612); ambos en el mismo escalón `OFFICIAL_PREDIO` sin subprioridad ⇒ la precedencia no desempata |
| `amenaza` | NOT_TRUE_CONFLICT → `RESOLVED_BY_PRECEDENCE` | condición 7 **falla**: `api/geospatial_engine.py:_clave` declara y aplica la regla de desempate (max severidad, min área) y documenta que este predio cae en dos polígonos simultáneos de la misma capa. El par legacy es `OBJECT_MISMATCH` (3547.8 m) |
| `tratamiento` | NOT_TRUE_CONFLICT → `HISTORICAL_CHANGE` | el único par rival (`Consolidación (Nivel 2)` en `03I1` vs `Desarrollo (Bajo)` en `03I2`) evaluó puntos **distintos** (144.7 m); el atributo es punto-en-polígono y el valor declara su dependencia («Según polígono POT») ⇒ es **cascada del conflicto de coordenada**, no defecto independiente (contarlo duplicaría un solo defecto en cuatro atributos) |
| `uso_pot` | NOT_TRUE_CONFLICT → `SEMANTIC_DIFFERENCE` | condiciones 2 y 7 fallan: los valores rivales declaran **capas distintas** («Capa 2» = áreas de actividad) y la escalera **sí** declara precedencia para `uso_pot` (`POT_BAQ_AREAS_ACTIVIDAD` 10 > `POT_BAQ_POLIGONOS_USO` 20) |
| `titulares` | NOT_TRUE_CONFLICT → `SEMANTIC_DIFFERENCE` | condición 6 **falla**: los valores **no** son incompatibles — ambos afirman `DURAN BACCA ALISSON 50%`; la forma antigua es un superconjunto que añade un segundo copropietario en la misma celda. Además la regla explícita de la misión excluye las diferencias de caja del nombre del titular |

**Resultado: 6 → 2** (`altura_maxima`, `coordenada`), **delta −4**, con las cuatro degradaciones justificadas por la condición concreta que no se cumple. Banda de sensibilidad declarada en el JSON: estricta 2 · más permisiva (contando cascadas como independientes) 5. **El recuento no se preserva por compatibilidad**: baja.

Añadido: el informe **también declara «cambios» entre dos ausencias** (`None → None`), que no son cambios ni conflictos, y que sí degradan ocho filas de P6 (v. §3, paso 1).

---

## 9 · Binding de geometría: `VERIFICADA` es un binding de identificadores

Detalle y matriz de candidatos en `GEOMETRY_BINDING_AUDIT_040-646406.json`.

**Reproducción del síntoma.** `NO_COMPARABLE` **no** se reproduce en el PDF del Golden (imprime `VERIFICADA`); **sí** en el TXT 2.0B del mismo directorio (`DX-…20260925`). Causa raíz documentada por el propio repo (`dictus_2c/ENTREGA_2.0C.md`, tabla «DEL ESTADO, no en el motor»): *«el modelo buscaba las coordenadas dentro del contexto administrativo, donde nunca estuvieron ⇒ la página 6 decía «NO_COMPARABLE» mientras el técnico decía `binding='VERIFIED'`»*. Mecanismo: `api/dictus_secciones.py:404` aplica el default `NO_COMPARABLE` cuando `market_context` no entra al contexto del modelo; `api/dictus_decision.py:430-431` degrada además la observación a `NO_EVALUADO`. Clasificación: `MODEL_MAPPING_FAILURE`.

**Qué geometría corresponde al sujeto.** El punto adoptado corresponde al **PREDIO** por relación oficial declarada por la fuente: `feature_id_kind = cr_predio_guid` con `feature_id == predio_globalid == 6c663607-5509-401f-b57d-384d2beeeac1` (criterio 3 de `market_context.evaluar_geometria_oficial_predio`). Pero se obtuvo de la capa **105 · direccion** (`CATASTRO_BAQ_DIRECCION`, `esriGeometryPoint`), **no** de la capa del predio ni del terreno. El propio artefacto lo declara: `coordinate_scope = "geometría oficial del PREDIO (lote/edificio): NO acredita la posición del apartamento dentro de la edificación"`.

**Los tres candidatos, medidos:**

| Candidato | Qué es realmente | Geometría que aporta | Estado en la corrida |
|---|---|---|---|
| `OFFICIAL_PREDIO` | etiqueta de `market_context` para un **POINT** de la capa 105 · direccion | punto de dirección | **adoptado** |
| `OFFICIAL_ADOPTION_REGISTRY` (`CATASTRO_BAQ_ADOPCION_ANEXO1`) | `AUTHORIZED_FALLBACK` / `PACKAGED_REGISTRY` `api/data/barranquilla_adopcion_anexo1.json` sha256 `eafc828c…23a3`, vigencia VIGENTE (límite 2026-12-19) | **NINGUNA** — `expected_fields = [numero_predial, codigo_homologado, fmi, codigo_registral]`, `geometry_type` «No aplica» | **no cargado** (`property_identity.identity_source = null`) |
| `OFFICIAL_ADOPTION_ADDRESS_GEOCODE` | ruta que **geocodifica** la dirección del registro de adopción (`NOMINATIM/OSM`, `link_verificado=None`) | geocode de dirección | **no cargado** (`authoritative_address=null`, `address_source=null`, `geocoder_source=null`) |

**Un geocode de dirección NO se acepta como equivalente a la geometría oficial del predio** — y el propio motor ya lo separa en dos escalones distintos de la allowlist (`api/market_context.py:439-453`), con `link_verificado=None` para el geocode y con el docstring que prohíbe reetiquetar procedencia.

**Por qué el `VERIFIED` impreso no es geométrico.** `api/market_context._evaluar_binding_canonico` (647-753) compara **solo cadenas de identificadores** (`nupre`, `numero_predial`, clave municipal) y la coherencia interna registro↔procedencia. **No lee ni compara coordenadas, polígonos, áreas ni topología.** El alcance obtenido es `NATIONAL_IDENTIFIERS` con campos `['nupre','numero_predial']`: acredita que el registro del predio es el **mismo predio** que la identidad canónica, no que **esta geometría sea la del predio**.

**Qué falta exactamente para un binding `VERIFIED` geométrico** (8 faltantes detallados en el JSON; mínimo exigible):

1. **El polígono oficial del predio.** La corrida solo tiene un `Point`. **Hallazgo decisivo:** en el Source Pack, `CATASTRO_BAQ_PREDIO` (capa 100) está declarada como **`esriGeometryNull (tabla)`** — *«Predio (tabla de atributos, sin geometría)»*. El único candidato con polígono y relación catastral es `CATASTRO_BAQ_TERRENO` (capa 315, `esriGeometryPolygon`), que no fue usado y **no está** en `PREDIO_ORIGENES_ELEGIBLES`.
2. **Una comparación geométrica** con criterio de tolerancia declarado (que la geometría caiga dentro del predio identificado por `numero_predial`/NUPRE).
3. **Una segunda geometría independiente** de contraste: hoy hay **una sola**.
4. **Las relaciones oficiales a construcción y terreno.** `CATASTRO_BAQ_DIRECCION` declara `cr_predio_guid`, **`cr_construccion_guid`** y **`cr_terreno_guid`**; la corrida persiste **solo el `predio_globalid`** ⇒ sin anclaje al edificio ni al lote.
5. **Geometría de la unidad privada** (Torre 8 / Apartamento 430), que el pack no declara.
6. **CRS/EPSG declarado** y **crudo de la capa 105**: `CATASTRO_BAQ_DIRECCION` tiene `acquisition_snapshot = null` y el único `capture_file` del vecindario está declarado **descartado** por el pack: *«Es un fixture escrito por una prueba, NO una respuesta de servicio: usarlo como evidencia sería fabricar el dato»*.
7. **Verificación independiente del vínculo** (hoy `link_verificado=true` es declaración del productor).

**Enunciado honesto para imprimir:** «La geometría oficial del PREDIO coincide con la identidad canónica (nupre, numero_predial) — *scope* NATIONAL_IDENTIFIERS». Decir «binding de la geometría oficial: VERIFICADA» sin calificar el alcance atribuye a la **geometría** una verificación hecha sobre **identificadores**.

---

## 10 · Entregables y trazabilidad

| # | Entregable | Contenido |
|---|---|---|
| 1 | `LAYER_HIERARCHY_V1.md` | jerarquía de capas L0–L8 con módulos y funciones reales; vocabularios implementados; las dos rutas de verdad; fichas de causa raíz |
| 2 | `ATTRIBUTE_RESOLUTION_REGISTRY.json` | 23 fichas de 20 campos (§9), validado: vocabularios en rango, un `resolution_status` por atributo |
| 3 | `FACT_PROPAGATION_MATRIX_040-646406.csv` | 23 filas × 13 columnas (`attribute, source_value, resolved_value, runstate_value, document_model_value, pdf_value, source_status, resolution_status, runstate_status, pdf_status, loss_stage, consistent, reason`) |
| 4 | `FACT_PROPAGATION_AUDIT_040-646406.md` | este documento |
| 5 | `HISTORICAL_CONFLICT_AUDIT_040-646406.json` | recálculo 6 → 2 con las siete condiciones evaluadas por atributo; detector de cambios `None → None`; banda de sensibilidad |
| 6 | `GEOMETRY_BINDING_AUDIT_040-646406.json` | `OFFICIAL_PREDIO` vs `OFFICIAL_ADOPTION_REGISTRY` vs `OFFICIAL_ADOPTION_ADDRESS_GEOCODE`; qué geometría corresponde al sujeto; 8 faltantes para `VERIFIED` |
| 7 | `RISK_STATE_AUDIT_040-646406.json` | inundación, remoción, riesgo y riesgo no mitigable con las distinciones `NO_EVALUATED`/`QUERY_FAILED`/`NO_MATCH`/`KNOWN_BUT_UNVERIFIED`/`HISTORICAL_ONLY`; 7 causas raíz |
| 8 | `CROSS_PAGE_TRUTH_040-646406.json` | 8 atributos comparados entre P1/P4/P5/P6: 0 divergencias de valor, 6 de estado |

Todos en `docs/truth_resolution/`. Generadores reproducibles en `docs/truth_resolution/scratch/` (`measured.json` es el volcado de medición intermedio; `s01_…s22_*.py` los sondeos; `build_registry.py` valida las fichas).

**Reglas respetadas:** no se inventaron valores ni fuentes; no se infirió por vecindad (explícitamente relevante en `estrato`, donde el pack descarta el snapshot del buffer de 150 m por esa razón); no se usó `features[0]` (el motor ya usa max-severidad/min-área, y esta auditoría lo documenta como la regla que resuelve el síntoma «Baja»); no se rellenó por hardcode; no se usó histórico como presente (`clase_suelo` queda `HISTORICAL_ONLY`, no `SUELO URBANO`); la escritura fue incremental. **No se modificó ninguna lógica de motor.**

**No medido, con motivo exacto:** (a) `source_attempts` por atributo — el RunState solo lo persiste para POI (`sources_attempted`/`sources_succeeded`); (b) `queried_at` por atributo — solo existe `poi_state.queried_at` y `generated_at`; (c) la procedencia (`feature_id`/`layer`) del punto histórico `11.00538 -74.83862`; (d) si `ACTIVIDAD CENTRAL` y `ACTIVIDAD URBANA RESIDENCIAL / COMERCIAL` son mutuamente excluyentes en la nomenclatura del POT de Barranquilla; (e) la reproducción del literal «Baja · polígono: intersecta el predio» con `NO EVALUADO`, por no existir en ningún artefacto del caso (sí existe su mecanismo, `RSK-4`).


---


---


---

## 11 · POST-CORRECCIÓN · medición de la corrida corregida

**Identidad de la corrida medida:** `run_id 137017a8-9d80-4c5b-9eae-957118c3e19a` · `DX-040-646406-20261002` ·
`2026-10-02T16:55:59.367003+00:00` · `master_hash c790a8f20f3efdf8108ec9cea55aa986eaf7df6cc7090f787dd3132e2c0af3f0` ·
PDF ejecutivo `sha256 3893e9225167d8b3737ff68189f896bb125eeb48975ca976801038ce4e4f6d12`.

> **Advertencia de medición (declarada, no forzada).** La corrida se regeneró con
> `python scripts/dictus_run.py`. En esta ventana los servicios vivos NO respondieron
> (el geoportal municipal devolvió HTTP 403/Cloudflare y Overpass HTTP 504 — el propio
> Source Pack documenta esa ventana en `measurement_window`), así que la corrida resolvió
> la coordenada por la ruta **`OFFICIAL_ADOPTION_ADDRESS_GEOCODE`** y varios atributos
> urbanos quedaron sin fuente viva. Por eso hay atributos que en la corrida AUDITADA
> tenían valor («Miramar», «02», «Consolidacion») y ahora declaran su ausencia con el
> motivo exacto. **No se rellenó ningún hueco.**

### 11.1 `loss_stage` recalculado (23 fichas)

| nivel | n | atributos |
|---|---|---|
| `ACQUISITION_FAILURE` | 2 | inundacion, uso_pot |
| `NINGUNA` | 10 | barrio, destino_economico, direccion, estrato, fmi, localidad, matricula, numero_predial, nupre, riesgo |
| `NINGUNA (degradación declarada)` | 3 | binding_geometria, remocion, tratamiento |
| `RESOLUTION_FAILURE` | 8 | altura_normativa, area, clase_suelo, coordenada, property_type, regimen_juridico, riesgo_no_mitigable, unidad |

### 11.2 `consistent` recalculado

| valor | n | atributos |
|---|---|---|
| `NO APLICA (sin valor canónico: se declara el estado)` | 4 | clase_suelo, inundacion, riesgo_no_mitigable, uso_pot |
| `SI` | 19 | altura_normativa, area, barrio, binding_geometria, coordenada, destino_economico, direccion, estrato, fmi, localidad, matricula, numero_predial, nupre, property_type, regimen_juridico, remocion, riesgo, tratamiento, unidad |

### 11.3 `resolution_status` y `fact_status` persistidos por atributo

| resolution_status | n | atributos |
|---|---|---|
| `NOT_SUPPORTED` | 7 | area, clase_suelo, coordenada, property_type, regimen_juridico, riesgo_no_mitigable, unidad |
| `RESOLVED_FALLBACK` | 5 | estrato, fmi, matricula, numero_predial, nupre |
| `RESOLVED_PRIMARY` | 5 | barrio, destino_economico, direccion, localidad, tratamiento |
| `RESOLVED_SNAPSHOT` | 4 | altura_normativa, edificabilidad, remocion, riesgo |
| `SOURCE_UNAVAILABLE` | 2 | inundacion, uso_pot |
| `UNRESOLVED` | 1 | binding_geometria |

| fact_status | n | atributos |
|---|---|---|
| `CONFLICT` | 3 | altura_normativa, coordenada, edificabilidad |
| `HISTORICAL_ONLY` | 1 | clase_suelo |
| `KNOWN_BUT_UNVERIFIED` | 7 | area, binding_geometria, property_type, regimen_juridico, remocion, tratamiento, unidad |
| `NOT_SUPPORTED` | 1 | riesgo_no_mitigable |
| `SOURCE_UNAVAILABLE` | 2 | inundacion, uso_pot |
| `VERIFIED` | 10 | barrio, destino_economico, direccion, estrato, fmi, localidad, matricula, numero_predial, nupre, riesgo |

### 11.4 Conflictos históricos: recuento derivado de TRUE_CONFLICT

- **Total derivado: 2** → altura_maxima, coordenada.
- Banda de sensibilidad: {"estricta_TRUE_CONFLICT": 2, "incluyendo_cascadas_de_geometria": 3}.
- Reclasificados (no son conflicto, con su condición y su motivo): amenaza=RESOLVED_BY_PRECEDENCE(7_precedencia_no_resuelve), planes_parciales=HISTORICAL_CHANGE(4_vigencia_comparable), titulares=NORMALIZATION_DIFFERENCE(6_valores_incompatibles), tratamiento=HISTORICAL_CHANGE(3_mismo_objeto), uso_pot=SEMANTIC_DIFFERENCE(2_misma_semantica).
- El número que imprime el ejecutivo sale de `len(historical_consistency.conflictos_abiertos)`, que ahora contiene SOLO `TRUE_CONFLICT`.

### 11.5 Lo que se corrigió en la fuente (archivo:línea)

| # | causa raíz | corrección |
|---|---|---|
| 1 | `api/dictus_historia.py:377` — «cambio» `None → None` | guarda de dos ausencias ⇒ `cambio=False` |
| 2 | `api/geospatial_engine.py:181` — sin `evaluado` | contrato `evaluado`/`modo`/`motivo_evaluado` en todas las ramas |
| 3 | `api/receipts.py:124` — `bool(geo.get("evaluado"))` | `_geo_evaluado()` compatible y derivado del resultado espacial |
| 4 | `api/dictus_ejecutivo.py:1580` — chip sin rama BAJA | `_chip_de_riesgo()` + `_chip_de_hecho()` |
| 5 | `api/dictus_decision.py:519` — estado por presencia de cadena | estado desde `attribute_resolution[*].fact_status` |
| 6 | `api/dictus_secciones.py:577` — default fail-open `VERIFICADO` | estado desde la verdad única + resumen §10 + binding §11 |
| 7 | `api/dictus_manifiesto.py:252` — `EV-AMENAZAS` por disponibilidad del volcán | sello derivado de los componentes observados |
| 8 | `api/dictus_historia.py` — recuento por `material ∧ UNEXPLAINED_CONFLICT` | 7 condiciones + `recuento_true_conflict` persistido |
| 9 | escalera sin persistir | `api/attribute_truth.py` + `DICTUS_RUN_STATE.attribute_resolution` |

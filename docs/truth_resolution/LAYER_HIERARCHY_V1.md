# LAYER_HIERARCHY_V1 · DICTUS — jerarquía de capas, resolución por atributo y propagación de hechos

**Ámbito:** BLOCK 1 · AUDITORÍA (sin cambios de lógica de motor).
**Caso:** Golden FMI `040-646406` · dirección `TRANSVERSAL 43 100 50, Torre 8, Apartamento 430` · predial `080010103000010040001908040002` · NUPRE `AFT0005BOHA` · área `58.75 m²` · régimen `Propiedad Horizontal`.
**Artefactos medidos (no hardcodeados):**

| Artefacto | Ruta | Identidad de la corrida |
|---|---|---|
| RunState | `docs/forensics/040-646406/dictus_2b/DICTUS_RUN_STATE_040-646406.json` | `run_id 6429974c-f9bf-494f-99d2-aff0c9495d14` · `2026-10-01T13:47:11Z` · `dictus-run-state/1.0.0` |
| Master Manifest (ExecutiveDocumentModel) | `docs/forensics/040-646406/dictus_2b/DICTUS_MANIFEST_040-646406.json` | `dictus-master-manifest/1.2.0` · `master_hash 4da3191d…6277` |
| PDF ejecutivo 6 pp | `docs/forensics/040-646406/dictus_2b/DICTUS_EJECUTIVO_040-646406.pdf` | `DX-040-646406-20261001` · `sha256 4f8dcbcb…e19a` |
| PDF técnico 17 pp (anexo) | `docs/forensics/040-646406/dictus_2b/DICTUS_TECNICO_040-646406.pdf` | `sha256 586e6e56…82ac` |
| Texto ejecutivo 2.0B (corrida previa homónima, en el MISMO directorio) | `docs/forensics/040-646406/dictus_2b/DICTUS_2.0B_TEXTO_EJECUTIVO_040-646406.txt` | `DX-040-646406-20260925` · `master_hash 1B8484A8A675…5417` |
| Matriz histórica (14 versiones) | `docs/forensics/040-646406/dictus_2/ATTRIBUTE_HISTORY_MATRIX.json` | `dictus-historical-consistency/1.0.0` |
| Registro de fuentes del pack | `docs/source_pack/barranquilla_sources_v1.json` | `barranquilla-source-pack/1.0.0` · `reference_date 2026-09-29` |

> **Nota de medición obligatoria.** El directorio `dictus_2b/` contiene **dos** documentos ejecutivos distintos: el **PDF** (`DX-…20261001`, 6 pp, `sha256 4f8dcbcb…`) y el **TXT 2.0B** (`DX-…20260925`, `master_hash 1B8484A8…`). No son la misma corrida y no dicen lo mismo. Todo síntoma de la misión se atribuye abajo a la corrida concreta en que **sí** se mide, y se declara explícitamente el que **no** se reproduce.

---

## 1 · Jerarquía de capas real (medida en código, no supuesta)

```
L0 ADQUISICIÓN ────────── api/dictus_sources.py (contrato + registro de 34 fuentes)
                          api/acquisition.py · api/acquisition_http.py
                          api/integrations/{arcgis_client,catastro_live,territorio,wfs_client}.py
                          api/core_remeasure.py (remedición sobre snapshot empaquetado)
                          ↓ produce: SourceResult {source_id, estado ∈ 5, payload, sha256,
                                                    acquisition_mode, vigencia, queried_at}
L1 RESULTADO DE FUENTE ─── sin artefacto por-atributo persistido en el Golden  (§3)
                          ↓
L2 ESCALERA DE RESOLUCIÓN ─ api/source_resolution.py
                          COBERTURA_ATRIBUTOS (20 escalones declarados) · resolver_atributo()
                          escalon_para_atributo() · es_conflicto()/VeredictoConflicto
                          ↓ produce: {source_selected, source_attempts[], resolution_status,
                                      solo_valor_resuelto, anexo_alternativas}
L3 HECHO RESUELTO ──────── resolutores por dominio, NO un único ResolvedFact object:
                          api/canonical.py            → identidad canónica (folio/nupre/predial/unidad)
                          api/catastro_predio*.py     → registro catastral
                          api/market_context.py       → coordenada + binding + contexto urbano + mercado
                          api/edificabilidad.py       → altura normativa POT
                          api/geospatial_engine.py    → amenaza/riesgo (PUNTO_EN_POLIGONO)
                          api/geocoder*.py            → nomenclatura/geocode
                          api/clasificacion.py · api/unidad_inmobiliaria.py
                          api/barranquilla_adopcion.py→ OFFICIAL_ADOPTION_REGISTRY (Anexo 1)
                          ↓
L4 ESTADO DE CORRIDA ───── api/dictus_estado.py → DICTUS_RUN_STATE/1.0.0 (20 claves)
                          api/receipts.py       → receipts (14 claves)
                          api/dictus_historia.py→ historical_consistency (7 claves)
                          api/dictus_manifiesto.py → evidence_manifest (10 evidencias)
                          ↓
L5 MODELO DE DOCUMENTO ─── api/dictus_decision.py (observations con status, decision_gates,
                          decision_matrix, disposition, findings, human_reviews)
                          api/dictus_manifiesto.py → manifest.modelo (30 claves)
                          ↓
L6 SECCIONES ───────────── api/dictus_secciones.py
                          verdad_por_atributo() · _estado_atributo() · _estado_urb()
                          → hechos_impresos.identidad.filas[] (estado por fila)
                          ↓
L7 RENDER ──────────────── api/dictus_ejecutivo.py (6 pp) · api/pdf_compiler.py (17 pp anexo)
                          api/dictus_entrega.py (aserciones sobre el PDF físico ya escrito)
                          ↓
L8 PDF ─────────────────── DICTUS_EJECUTIVO_040-646406.pdf · DICTUS_TECNICO_040-646406.pdf
```

**Vocabularios realmente implementados (medidos):**

| Concepto | Vocabulario en código | Dónde | Cobertura del vocabulario pedido en §9 |
|---|---|---|---|
| estado de fuente | `AVAILABLE`, `NO_MATCH`, `SOURCE_UNAVAILABLE`, `NOT_SUPPORTED`, `QUERY_FAILED` (5) | `api/dictus_sources.py:50-55` | cubre 4 de 9 |
| estado de resolución | `RESOLVED_PRIMARY`, `RESOLVED_FALLBACK`, `UNRESOLVED`, `AMBIGUOUS`, `SOURCE_UNAVAILABLE` (5) | `api/source_resolution.py:59-67` | cubre 4 de 9 |
| marca de conflicto de resolución | `CONFLICT` (etiqueta; el estado asociado es `AMBIGUOUS`) | `api/source_resolution.py:70` | — |
| marca local de escalera | `NOT_RUN` (NO es estado de fuente; «no se ejecutó consulta») | `api/source_resolution.py:75` | — |
| estado de coherencia histórica | `VERIFICADO`, `REQUIERE_VALIDACION`, `HISTORICAL_CONFLICT`, `CAMBIO_CON_FUENTE`, `SIN_DATO`, `NO_COMPARABLE` | `api/dictus_historia.py:35-40` | — |
| clase de cambio histórico | `SOURCE_UPDATE`, `METHODOLOGY_UPDATE`, `IDENTITY_CHANGE`, `GEOMETRY_CHANGE`, `SOURCE_UNAVAILABLE`, `PARSER_CHANGE`, `INTERPRETATION_CHANGE`, `UNEXPLAINED_CONFLICT` | `api/dictus_historia.py:43-50` | no es el vocabulario de §9 |
| estado de hecho (observación) | `OBSERVED`, `NOT_EVALUATED`, `NO_MATCH`, `CONFLICT`, `SOURCE_UNAVAILABLE` | `api/dictus_decision.py` (usado en `observations[].status`) | cubre 4 de 6 |

**`RESOLVED_SNAPSHOT` NO EXISTE en el motor.** Medición: `grep -rn "RESOLVED_SNAPSHOT" api/` → 0 coincidencias. El concepto equivalente se expresa en el registro de fuentes con `acquisition_mode` (`LIVE_QUERY`, `AUTHORIZED_FALLBACK`, con `acquisition_snapshot.kind ∈ {PACKAGED_GEOJSON, PACKAGED_REGISTRY, RAW_CAPTURE}` y `modo ∈ {AUTOMATED_SNAPSHOT, AUTHORIZED_FALLBACK}`), y en el RunState como `urban_source_summary.campos.*.modo ∈ {LIVE_OFFICIAL, PACKAGED_REFERENCE}`. En las fichas de §9 se usa `RESOLVED_SNAPSHOT` **solo** cuando el valor del Golden proviene efectivamente de un `acquisition_snapshot` declarado, y se anota el `acquisition_mode` real.

---

## 2 · Dos rutas de verdad independientes para el MISMO atributo (causa estructural de la contradicción P6)

Medición en código: la página 6 del ejecutivo se construye con **dos** fuentes de estado que nunca se confrontan.

**Ruta A — estado por fila** (`api/dictus_secciones.py:566-581`, `978-1028`):

```python
def _estado_atributo(atributo, valor, origen=None):
    if not _dato(valor):                       # sin valor  → SIN_DATO
        return dse.SIN_DATO
    est = verdad_atributos.get(atributo, dse.VERIFICADO)   # ← DEFAULT fail-open
    if (est == dse.VERIFICADO and isinstance(origen, dict)
            and not origen.get("origin_gate")):            # origen no habilitante degrada
        return dse.REQUIERE_VALIDACION
    return est
```

`verdad_atributos` (`api/dictus_secciones.py:372-400`) se deriva **exclusivamente** del informe de coherencia histórica, indexado por **nombre de atributo**:

```python
for c in hist["conflictos_abiertos"]:  estado[c["atributo"]] = HISTORICAL_CONFLICT
for r in hist["requieren_revision"]:   estado[r["atributo"]] = REQUIERE_VALIDACION
for e in hist["cambios_explicados"]:   estado[e["atributo"]] = CAMBIO_CON_FUENTE
# atributo ausente del informe  →  .get(atributo, VERIFICADO)
```

**Ruta B — titular de la frase «Identidad registral y catastral»** (`api/dictus_secciones.py:1031-1034`):

```python
"identidad_estado": "VERIFICADA" if pi.get("identity_verified") else "REQUIERE VALIDACIÓN"
```

`pi` = `property_identity` del RunState. `identity_verified = True` proviene de `resolution_confidence == "VERIFIED_UNIT_IDENTITY"` con `resolution_method = "nupre"` y `estado = "MATCH_BY_NUPRE"` (`api/canonical.py`). **No consulta `verdad_atributos` ni el informe histórico.** Las dos rutas son ortogonales ⇒ una fila puede decir `VERIFICADO` y la frase-resumen `VERIFICADA` mientras cinco filas hermanas dicen `REQUIERE VALIDACIÓN`, sin que ninguna capa detecte la incoherencia.

**Medición del subconjunto que alimenta cada ruta** (RunState `historical_consistency`):

| Lista | Longitud medida | Atributos |
|---|---|---|
| `conflictos_abiertos` | **6** | `altura_maxima`, `amenaza`, `coordenada`, `titulares`, `tratamiento`, `uso_pot` |
| `requieren_revision` | **17** | `area`, `barrio`, `clase_suelo`, `destino_economico`, `direccion`, `estrato`, `evidencias`, `gravamenes`, `localidad`, `numero_predial`, `nupre`, `regimen_juridico`, `riesgo`, `screening`, `unidad`, `valor_central`, `valor_m2` |
| `cambios_explicados` | **1** | `planes_parciales` |
| `versiones_comparadas` | **14** | (v. §5) |

`matricula` **no aparece en ninguna de las tres listas** ⇒ Ruta A le asigna `VERIFICADO` por defecto. Ese es, medido, el origen exacto del contraste P6 (v. §4).

---

## 3 · El eslabón que NO existe en el Golden: `SourceResult` y `ResolvedFact` por atributo

Medición por conteo de tokens sobre los artefactos reales:

| Token | `DICTUS_RUN_STATE` | `DICTUS_MANIFEST` |
|---|---|---|
| `source_selected` | 0 | 0 |
| `source_attempts` | 0 | 0 |
| `source_authority` | 0 | 0 |
| `acquisition_mode` | 0 | 0 |
| `fact_status` | 0 | 0 |
| `historical_values` | 0 | 0 |
| `conflict_class` | 0 | 0 |
| `resolution_status` | 1 (`property_identity.resolution_status` = `"EXACT"`, vocabulario de IDENTIDAD, **no** el de la escalera) | 1 (el mismo) |
| `resolved_fact` / `ResolvedFact` | 0 (`grep` sobre `api/` ⇒ 0 coincidencias) | 0 |
| `OFFICIAL_ADOPTION_REGISTRY` / `OFFICIAL_ADOPTION_ADDRESS_GEOCODE` | 0 / 0 | 0 / 0 |
| `POT_BAQ_*` | **0** | **0** |

**Consecuencia de auditoría, declarada sin rellenar:** en el Golden **no existe ningún registro por atributo** que persista `source_attempts`, `source_selected`, `source_authority`, `source_vigency`, `acquisition_mode` ni `fact_status`. La escalera de `api/source_resolution.py` está implementada y probada (`tests/test_source_pack_resolution_ladder.py`, `tests/test_source_pack_acquisition_modes.py`) pero **su salida no entra al RunState del Golden**: ningún `source_id` del pack (`POT_BAQ_BARRIOS`, `CATASTRO_BAQ_PREDIO`, `POT_BAQ_EDIFICABILIDAD`, …) aparece en el RunState ni en el Manifest. La procedencia por atributo que **sí** se persiste es otra y más pobre: `observations[].source` (texto libre, p. ej. `"capa oficial del municipio consultada en vivo"`, `"fuente no declarada"`) y `evidence_manifest.evidencias[].source`.

En las fichas de §9 esos campos se llenan **solo** con lo que está medido; donde el artefacto no lo persiste se escribe `NOT_PERSISTED_IN_GOLDEN` con la evidencia de la medición.

---

## 4 · Causa raíz medida de la contradicción P6 (matrícula `VERIFICADO` vs componentes `REQUIERE VALIDACIÓN`)

**Síntoma — reproducido literalmente en el PDF del Golden** (`DICTUS_EJECUTIVO_040-646406.pdf`, p. 6):

```
Dirección oficial            … REQUIERE VALIDACIÓN
Matrícula                    040-646406            VERIFICADO
NUPRE                        AFT0005BOHA           REQUIERE VALIDACIÓN
Número predial               080010103000010040001908040002  REQUIERE VALIDACIÓN
Unidad (torre / apartamento) APARTAMENTO 430 TORRE 8          REQUIERE VALIDACIÓN
Área                         58.75 m²              REQUIERE VALIDACIÓN
Régimen jurídico             Propiedad Horizontal  REQUIERE VALIDACIÓN
Uso (destino catastral)      Habitacional          REQUIERE VALIDACIÓN
Tipología                    Unidad En Propiedad Horizontal     REQUIERE VALIDACIÓN
Identidad registral y catastral: VERIFICADA
```

**Cadena causal medida, eslabón por eslabón:**

1. **`api/dictus_historia.py:376-387` — un «cambio» entre DOS AUSENCIAS.**
   ```python
   if ka is not None and kb is not None and ka == kb:      # exige AMBOS no-None
       → cambio: False
   if va is None or vb is None:                            # ← cae aquí cuando va=vb=None
       → cambio: True, clase SOURCE_UNAVAILABLE
   ```
   Si las dos versiones comparadas **no** traen el atributo (`va = vb = None`), la guarda de «sin cambio» no aplica y se declara `cambio: True` con `clase: SOURCE_UNAVAILABLE`. Medición en el RunState para `area`:
   `{"atributo": "area", "valores": [null ×13], "detalle": "el valor no está en la versión más reciente", "cambios": [{"anterior": null, "actual": null, "cambio": true, "clase": "SOURCE_UNAVAILABLE", "explicado": false, …}]}` — **13 versiones sin área producen un «cambio» `None → None`**.
2. **`api/dictus_historia.py:508-511`** — como la clase es `SOURCE_UNAVAILABLE` (no `UNEXPLAINED_CONFLICT`), el atributo **entra a `requieren_revision`** y no a `conflictos_abiertos`.
3. **`api/dictus_secciones.py:392-395`** — `verdad_por_atributo` lo traduce a `REQUIERE_VALIDACION`.
4. **`api/dictus_secciones.py:577`** — las filas `nupre`, `numero_predial`, `unidad`, `area`, `regimen_juridico`, `direccion` leen ese estado ⇒ `REQUIERE VALIDACIÓN`.
5. **`api/dictus_secciones.py:577` con clave `"matricula"`** — `matricula` **no** está en ninguna lista del informe (la matriz histórica sí la extrae: `ATTRIBUTE_HISTORY_MATRIX.atributos` incluye `matricula`, pero nunca registró un «cambio») ⇒ `.get("matricula", dse.VERIFICADO)` ⇒ **`VERIFICADO`**.
6. **`api/dictus_secciones.py:1031`** — la frase-resumen lee `property_identity.identity_verified = True` (ruta independiente) ⇒ **`Identidad registral y catastral: VERIFICADA`**.

**Clasificación:** `STATE_PROPAGATION_FAILURE` (paso 1: el informe de coherencia introduce un cambio falso entre ausencias) **+** `MODEL_MAPPING_FAILURE` (paso 5: default `VERIFICADO` fail-open para un atributo sin información de coherencia; y paso 6: segunda fuente de verdad no confrontada). **No** es `RENDERING_FAILURE`: el render imprime fielmente lo que el modelo declara — el modelo ya venía con el contraste.

**Ubicación exacta:** el valor no se pierde entre fuente y PDF; se **fabrica** un estado en `L6 · SECCIONES`, sobre un insumo falso ya creado en `L4 · ESTADO DE CORRIJA (historical_consistency)`.

---

## 5 · Causa raíz medida del `NO EVALUADO` (riesgo) y de la contradicción de fuentes

**Medición — estado de hecho por riesgo en el Golden (RunState `risk_context` + Manifest `modelo.observations`):**

| Atributo | `risk_context` (RunState) | `observations[].status` | Evidencia | `evidence_manifest` status |
|---|---|---|---|---|
| `amenaza_remocion_masa` | `"Media · polígono: intersecta el predio"` | `OBSERVED` | `EV-RIESGO-AMENAZA_REMOCION_MASA` | — |
| `inundacion` | `null` | `NOT_EVALUATED` | `EV-RIESGO-INUNDACION` | — |
| `riesgo_no_mitigable` | `null` | `NOT_EVALUATED` | `EV-RIESGO-RIESGO_NO_MITIGABLE` | — |
| `areas_en_riesgo` | `"Medio · polígono: intersecta el predio"` | `OBSERVED` | `EV-RIESGO-AREAS_EN_RIESGO` | — |
| (agregado de amenazas) | — | — | `EV-AMENAZAS` | **`FUENTE_NO_DISPONIBLE`** |

**`api/dictus_decision.py:513-526` — la regla que se midió, literal:**

```python
OBSERVADO if _v(risk.get(riesgo)) else NO_EVALUADO
```

El `fact_status` de los cuatro atributos de riesgo se deriva **solo de la presencia de una cadena de valor**. No consulta: (a) si hubo consulta (`query` está `null` en todas las observaciones medidas), (b) si la geometría fue evaluada, (c) el estado de la fuente, (d) si el valor viene de una capa histórica. De ahí las dos direcciones del error, ambas medidas:

* **`KNOWN_BUT_UNVERIFIED` disfrazado de `OBSERVADO`:** `amenaza_remocion_masa` y `areas_en_riesgo` se imprimen como hechos `OBSERVED` (`RIESGO MEDIO`, «Nivel de la capa oficial aplicable al polígono del predio») mientras la evidencia agregada de amenazas que esta misma corrida sella declara `status = "FUENTE_NO_DISPONIBLE"` (`= SOURCE_UNAVAILABLE`).
* **`NOT_EVALUATED` que no distingue nada:** `inundacion` sale `NOT_EVALUATED` con `urban_source_summary.campos.inundacion = {value: null, status: null, fuente: "Geometrias oficiales del POT empaquetadas en la aplicacion (cruce local STRtree, sin consulta en vivo)", modo: "PACKAGED_REFERENCE"}`. Hay **fuente declarada y modo declarado**, pero el estado queda indistinguible de `NO_MATCH`, `QUERY_FAILED` y `NOT_SUPPORTED`.

**Contexto de fuente medido en el registro del pack (explica el «por qué no hay dato», sin inferir):**
`POT_BAQ_INUNDACION_2024` → `enabled: false`, `layer_name: "Inundación 2024 (id declarado, no observado)"`; `POT_BAQ_INUNDACION_HIST` → `enabled: false`; `POT_BAQ_REMOCION_2024` → `enabled: true` con `acquisition_snapshot` `PACKAGED_GEOJSON` (`api/data/amenaza_remocion_masa.geojson`, `consulta: PUNTO_EN_POLIGONO`, vigencia `VIGENTE` límite `2027-09-01`); `POT_BAQ_RIESGO_2024` → `enabled: true` con snapshot `api/data/areas_en_riesgo.geojson`. Y `measurement_window` del pack declara: *«El geoportal de la Alcaldía devolvió HTTP 403 (Cloudflare) a toda consulta desde esta máquina durante la ventana»* (`reference_date 2026-09-29`).

**Regla de auditoría aplicada:** «si hubo consulta válida + geometría evaluada + resultado espacial ⇒ no puede quedar `NOT_EVALUATED`». Medición: **`receipts.geo_evaluado = false`** en el Golden. Es decir, la corrida **no declara** geometría evaluada de forma agregada, mientras `amenaza_remocion_masa` y `areas_en_riesgo` **sí** traen resultado espacial explícito («polígono: intersecta el predio»). El flag agregado `geo_evaluado` y el estado por atributo son incoherentes entre sí. Clasificación: `STATE_PROPAGATION_FAILURE` (el flag no refleja la resolución espacial efectivamente obtenida) **+** `MODEL_MAPPING_FAILURE` (`OBSERVADO if _v(...)` no consulta el estado de la fuente).

**Síntoma literal «Baja · polígono: intersecta el predio» con `NO EVALUADO` — NO SE REPRODUCE.** Medición: la cadena `"Baja · polígono"` aparece **0 veces** en todo el repositorio (búsqueda sobre `*.json|*.md|*.txt|*.csv` excluyendo `.venv`, `pytest-cache`, `motor_tma_lonja*`, `ARHIAX RE files*`). En los dos documentos del Golden el nivel de remoción es **`Media`**, y su estado es `OBSERVED` / `RIESGO MEDIO`, nunca `NO EVALUADO`. Se declara como no medido en vez de rellenarse; el defecto estructural que lo haría posible está identificado arriba y es el mismo que produce el `OBSERVED` sobre `SOURCE_UNAVAILABLE`.

---

## 6 · Causa raíz medida del binding de geometría `NO_COMPARABLE` (y por qué hoy dice `VERIFICADA`)

**Dónde se lee el binding** (`api/dictus_secciones.py:403-406`):

```python
def _geometria_estado(mc):
    binding = str(mc.get("canonical_binding_status") or "NO_COMPARABLE").upper()
```

`mc` = `market_context`. El **default literal de ausencia es `NO_COMPARABLE`** (fail-to-negative), y la fuente es exclusivamente `market_context`.

**Síntoma reproducido** en el TXT 2.0B del mismo directorio (`DX-…20260925`, p. 6):
`«Geometría oficial del predio y binding predio ↔ identidad canónica: NO_COMPARABLE. Detalle geodésico y CRS en el Anexo F.»`, y en el modelo de esa corrida la observación `IDENTITY · Geometría oficial vs identidad canónica` caía en `NO_EVALUADO` por `api/dictus_decision.py:430-431` (`OBSERVED if binding == "VERIFIED" else (CONFLICTO if "MISMATCH" else NO_EVALUADO)`).

**Causa raíz documentada por el propio repo** (`docs/forensics/040-646406/dictus_2c/ENTREGA_2.0C.md`, tabla «DEL ESTADO, no en el motor»):
> *Geometría · procedencia de la coordenada oficial, alcance de esa geometría y **binding canónico (VERIFIED)** — el modelo buscaba las coordenadas dentro del contexto administrativo, donde nunca estuvieron ⇒ la página 6 decía «NO_COMPARABLE» mientras el técnico decía `binding='VERIFIED'`.*

**Clasificación:** `MODEL_MAPPING_FAILURE` — la ruta de datos `market_context` no formaba parte del contexto con que se construía el modelo/render, de modo que la clave estaba ausente y se aplicaba el default negativo.

**Estado medido hoy (PDF `DX-…20261001`, p. 6):** `market_context.canonical_binding_status = "VERIFIED"` (presente en RunState **y** en `manifest.modelo.market_context`), `_geometria_estado` ⇒ `VERIFICADA`; el PDF imprime `«Binding de la geometría oficial: VERIFICADA»`. El síntoma `NO_COMPARABLE` **no** se reproduce en el PDF del Golden; sí en el TXT 2.0B del mismo directorio.

**Pero `VERIFIED` no significa lo que la página sugiere** — medición de `_evaluar_binding_canonico` (`api/market_context.py:647-753`): compara **cadenas de identificadores** (`nupre`, `numero_predial`, `municipal`) entre `canonical_identity` y `predio_real`. **Nunca compara geometría.** `scope = "NATIONAL_IDENTIFIERS"`. El propio artefacto lo declara: `coordinate_scope = "geometría oficial del PREDIO (lote/edificio): NO acredita la posición del apartamento dentro de la edificación"`. Detalle completo y qué falta para un binding `VERIFIED` geométrico ⇒ `GEOMETRY_BINDING_AUDIT_040-646406.json`.

---

## 7 · Resumen de puntos de pérdida por nivel (mapa, detalle por atributo en la matriz CSV)

| Nivel | Qué puede perderse/cambiar aquí | Evidencia medida en el Golden |
|---|---|---|
| `L2 RESOLUCIÓN` | la salida de la escalera no se persiste por atributo | 0 tokens `source_selected`/`source_attempts`/`resolution_status`(escalera) en RunState y Manifest |
| `L4 ESTADO` | `historical_consistency` fabrica cambios entre ausencias | 13 versiones `null→null` para `area` ⇒ `cambio: true` |
| `L4 ESTADO` | `risk_context` reduce el riesgo a una cadena y pierde el estado de fuente | `EV-AMENAZAS = FUENTE_NO_DISPONIBLE` coexiste con `amenaza_remocion_masa = OBSERVED` |
| `L4 ESTADO` | `geo_evaluado` no refleja la resolución espacial obtenida | `geo_evaluado: false` con «polígono: intersecta el predio» en 2 atributos |
| `L5 MODELO` | `OBSERVADO if _v(valor) else NO_EVALUADO` ignora fuente/consulta/geometría | `api/dictus_decision.py:519` |
| `L6 SECCIONES` | default `VERIFICADO` para atributo sin coherencia declarada | `matricula` ⇒ `VERIFICADO` con 5 hermanas en `REQUIERE_VALIDACION` |
| `L6 SECCIONES` | dos fuentes de verdad para «identidad» no confrontadas | `_estado_atributo` (histórico) vs `identity_verified` (canónico) |
| `L7 RENDER` | default `NO_COMPARABLE` cuando falta la clave | `api/dictus_secciones.py:404` |
| `L7 RENDER` | la etiqueta de estado no nombra el atributo | `P4` rotula `RIESGO MEDIO` sin declarar de qué capa ni con qué estado de fuente |

---

## 8 · Consultas que esta auditoría NO pudo cerrar (declaradas, no rellenadas)

1. **`RESOLVED_SNAPSHOT` no existe en el motor** (0 coincidencias en `api/`). Se usa en el registro de atributos con la equivalencia declarada (`acquisition_snapshot` + `acquisition_mode`), anotando el `modo` real.
2. **`resolution_status` de §9 con 9 valores**: el motor implementa 5 (resolución) + 5 (fuente) en dos vocabularios separados. Ningún artefacto del Golden persiste ninguno de los dos por atributo. En el registro se declara el valor derivado de la evidencia medida y se marca `derived_from` cuando no está persistido.
3. **`fact_status`**: no existe como campo. Se usa el `observations[].status` del modelo cuando el atributo tiene observación, y el chip impreso en el PDF en el resto, declarando la fuente de cada uno.
4. **`source_attempts`**: solo medible donde el RunState lo persiste (POI: `sources_attempted`/`sources_succeeded`). Para el resto: `NOT_PERSISTED_IN_GOLDEN`.
5. **`historical_values`**: medibles para los 25 atributos de `ATTRIBUTE_HISTORY_MATRIX` (14 versiones). No medibles para `coordinates` como tal (el atributo histórico se llama `coordenada`) — se declara la correspondencia.
6. **`queried_at` por atributo**: el RunState solo persiste `poi_state.queried_at` y `generated_at`. No hay `queried_at` por atributo ⇒ se usa `generated_at` y se marca.
7. **`titleholders`/actos**: fuera del alcance §8 pedido; los conflictos históricos de `titulares` sí entran al recálculo de §5 del `HISTORICAL_CONFLICT_AUDIT`.
8. **`riesgo` (atributo POT agregado)**: el RunState del Golden **no** tiene clave `riesgo`; el lote de P4 imprime «Otras amenazas declaradas» = `areas_en_riesgo`. La correspondencia histórica `riesgo` ↔ `areas_en_riesgo` se declara como tal, no se asume.

---

*Auditoría de solo lectura: no se modificó lógica de motor, PDF, Estimation Engine, `ESTIMATION_GATE`, `EVIDENCE_QUALITY`, M1–M5, screening, títulos ni solar. `PROPERTY_VALUE_RESOLUTION` permanece `PENDING`.*


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

# MODOS DE ADQUISICIÓN — BARRANQUILLA SOURCE PACK v1.0 (`acquisition-modes/1`)

**Decisión de producto que este documento implementa.** El freeze de PRODUCCIÓN **no** se
autoriza aceptando que los dominios CORE queden simplemente `SOURCE_UNAVAILABLE`. Por eso el
pack separa dos estados que antes se mezclaban:

| Estado | Qué afirma | Qué NO afirma |
|---|---|---|
| **CONTRACT_FROZEN** | El CONTRATO está cerrado: registro completo con metadata real, `product_role` y `acquisition_mode` por fuente, snapshots reales descubiertos y hasheados, binding tipado, precedencia determinista, escalera de resolución, licencias documentadas. | No afirma que el dato pueda obtenerse HOY. |
| **OPERATIONAL_READY** | Además, **cada dominio CORE tiene una ruta automática válida hoy**: consulta en vivo que responde, snapshot automático dentro de su `freshness_policy`, o fallback autorizado vigente. | No se concede si algún CORE solo puede declararse `SOURCE_UNAVAILABLE`. |

Implementación: `api/acquisition.py` (módulo **nuevo**; no modifica `dictus_sources.py`,
`source_resolution.py` ni ningún otro módulo del pack). La escalera de resolución se
**orquesta**, nunca se reimplementa.

---

## 1 · Vocabulario cerrado de modos

| Modo | Significado | Ejemplos reales hoy |
|---|---|---|
| `LIVE_QUERY` | La fuente se consulta EN VIVO en cada corrida (servicio con URL). | Todas las capas ArcGIS/POT/catastro, Mapillary/Google, y las fuentes CALCULADAS (se recalculan por corrida). |
| `AUTOMATED_SNAPSHOT` | La ruta es una copia empaquetada y hasheada **de la respuesta de la MISMA fuente**, refrescada por un proceso automático. | `POT_BAQ_REMOCION_2024`, `POT_BAQ_RIESGO_2024` (capas POT empaquetadas), `OSM_OVERPASS` (captura cruda). |
| `AUTHORIZED_FALLBACK` | La ruta es un **instrumento autorizado distinto** de la respuesta del servicio (documento oficial o contractual). | `CATASTRO_BAQ_ADOPCION_ANEXO1` (registro de adopción: su `fallback_policy` lo declara como fallback autoritativo), `LONJA_MARKET_BAQ` (metodología contractual) — *ver §7 sobre su estado actual*. |

`acquisition_mode` **por fuente** = ruta **primaria** declarada (`modo_declarado_de_fuente`).
`acquisition_mode` **por resultado** = el modo **realmente usado** para obtener ese valor.

### 1.1 Regla de caída (dura)

```
LIVE_QUERY  →  si falla (SOURCE_UNAVAILABLE | NOT_SUPPORTED | QUERY_FAILED)
               y existe un SNAPSHOT AUTOMÁTICO declarado para ese (atributo, fuente)
               y el snapshot está DENTRO de su freshness_policy
            →  se resuelve DESDE EL SNAPSHOT.
```

* El dato **CONSERVA la `authority_class` de la fuente ORIGINAL**: no se degrada a
  `CONTEXTUAL_*` por venir de un snapshot. Se registra en
  `provenance.original_authority_class` y en el payload (`autoridad_preservada: true`).
* Si la consulta en vivo **no se ejecutó** (no hay `SourceResult`), el snapshot declarado se
  usa igualmente: la ausencia de consulta no es una excusa para no resolver.
* Si la consulta en vivo **responde**, el snapshot **no se usa** (queda declarado en el
  registro de modo con el motivo «no hay ausencia que cubrir»).

### 1.2 Regla del snapshot VENCIDO

Un snapshot **fuera de su `freshness_policy` NO resuelve**. Se declara con su estado
(`VENCIDO`, límite, motivo) en `acquisition.snapshots_vencidos` y **la escalera sigue su
curso**. Un snapshot vencido jamás se presenta como dato vigente, y su ausencia nunca se
convierte en `NO_MATCH`.

### 1.3 Registro por resultado

Cada resultado de `resolver_con_acquisition_mode(...)` lleva `resultado["acquisition"]`:

| Clave | Contenido |
|---|---|
| `seleccionado.original_source` | `source_id` de la fuente ORIGINAL que produjo el valor |
| `seleccionado.acquisition_mode` | modo **realmente usado** (`LIVE_QUERY`/`AUTOMATED_SNAPSHOT`/`AUTHORIZED_FALLBACK`) |
| `seleccionado.declared_mode` | modo declarado por la fuente en el registro |
| `seleccionado.snapshot_created_at` | fecha de creación/commit del snapshot |
| `seleccionado.source_queried_at` | cuándo se consultó la fuente (vivo) o se capturó el crudo |
| `seleccionado.freshness_limit` | límite de vigencia aplicado (mín. entre familia y artefacto) |
| `seleccionado.content_hash` | **sha256 del snapshot** (hash del contenido, no de la corrida) |
| `seleccionado.provenance.original_authority_class` | `authority_class` ORIGINAL (no degradada) |
| `modo_por_fuente` | el mismo registro por CADA fuente del escalón (con `usado`, `live_status`, `snapshot_status`) |
| `snapshots_vencidos` | snapshots declarados que NO resuelven, con su estado y motivo |
| `consultas_efectivas` | el `SourceResult` que la escalera realmente vio por fuente |

`provenance_adquisicion(resultado)` devuelve el bloque de la fuente **seleccionada**
(`{}` si la escalera no seleccionó valor: la ausencia vive en `attempts`).

---

## 2 · `product_role` por fuente (vocabulario cerrado de 6)

`CORE_IDENTITY` · `CORE_NORMATIVE` · `CORE_RISK` · `CORE_MARKET` · `DECISION_CONTEXT` ·
`OPTIONAL_ENRICHMENT`.

Regla **declarada** de derivación (no se inventa por fila):

| `product_role` | `required_for_decision` | `blocking_if_missing` |
|---|---|---|
| `CORE_IDENTITY` / `CORE_NORMATIVE` / `CORE_RISK` / `CORE_MARKET` | `true` | `true` |
| `DECISION_CONTEXT` | `true` | `false` |
| `OPTIONAL_ENRICHMENT` | `false` | `false` |
| *(cualquiera con `precedence = HISTORICAL_REFERENCE`)* | `false` | `false` — una capa histórica es REFERENCIA, nunca operativa |

Reparto por fuente (registro JSON+gemelo YAML): identidad → `CATASTRO_BAQ_ADOPCION_ANEXO1`,
`CATASTRO_BAQ_DIRECCION`, `CATASTRO_BAQ_PREDIO`, `CATASTRO_BAQ_TERRENO`; norma POT →
`POT_BAQ_AREAS_ACTIVIDAD`, `POT_BAQ_POLIGONOS_USO`, `POT_BAQ_TRATAMIENTO`,
`POT_BAQ_EDIFICABILIDAD`; riesgo → las seis capas `POT_BAQ_{REMOCION,INUNDACION,RIESGO}_*`;
mercado → `LONJA_MARKET_BAQ`; contexto administrativo/decisiones → catastro restante, barrio,
localidad, estratificación, equipamiento oficial, solar/sombras; enriquecimiento → OSM,
Mapillary, Google.

---

## 3 · `freshness_policy` cuantificada por familia

Declarada en `FRESHNESS_DEFAULT` (`api/acquisition.py`) — es una **decisión del pack**, no un
dato del proveedor:

| Familia | Días | Fundamento declarado |
|---|---|---|
| `CATASTRO` | 90 | El registro catastral se actualiza por resolución de adopción y por anualidad. |
| `POT` | 365 | El POT vigente (Decreto 893 de 2024) no cambia dentro del año. |
| `RIESGO` | 365 | Las capas de amenaza se publican con el POT. |
| `EQUIPAMIENTO` | 365 | Se publica por POT / anuario municipal. |
| `MERCADO` | 180 | La metodología declara vigencia trimestral/semestral. |
| `CONTEXTO` | 30 | El entorno (OSM) cambia de forma continua. |
| `CONTEXTO_IMAGEN` | 30 | Una imagen solo describe el inmueble en su fecha de captura. |
| `CALCULADA` | 1 | Un resultado calculado vale para la corrida que lo produjo. |

**Límite efectivo = el MENOR entre** (ancla de frescura + días de la familia) y **la vigencia
que el propio artefacto declara** (`declaracion.vigencia_hasta`). Sin ancla o sin límite, el
snapshot **no se da por vigente**.

### 3.1 Ancla de frescura — la ventana no puede depender del empaquetado

El ancla la decide `api/acquisition.py::ancla_de_frescura` con una precedencia **declarada**:

| Orden | Ancla | Qué es | ¿Congelable? |
|---|---|---|---|
| 1 | `_capture.queried_at` del artefacto (`fecha_de_captura_declarada`) | cuándo se capturó el **dato** | **SÍ** — está dentro del contenido versionado |
| 2 | `fecha_de_creacion` del archivo (`git_commit` / `mtime_sin_commit`) | un hecho del **EMPAQUETADO** | solo si el artefacto no declara nada |
| 3 | nada | — | **NO**: sin ancla no se afirma frescura (el snapshot no resuelve) |

**Por qué (defecto medido, misma familia que el `evidence_hash` volátil).**
`docs/source_pack/raw/golden/osm_overpass.json` declara su captura (2026-09-29) y se commiteó
el 2026-10-01. Anclando en la fecha de commit, la celda congelada
`servicios_contexto.provenance` de `SOURCE_ACQUISITION_MATRIX_040-646406.csv` pasaba de
«hasta 2026-10-29» a «hasta 2026-10-31» **sin que cambiara un solo byte del dato**: el
artefacto congelado fingía un contenido que dependía de cuándo se empaquetó, y la suite del
Source Pack quedaba verde antes de la corrida y roja después. Con el ancla declarada la ventana
vuelve a 2026-10-29 y se reproduce igual antes y después de `scripts/dictus_run.py`
(`TestFrescura::test_la_frescura_se_ancla_en_la_captura_que_declara_el_artefacto` y
`TestMatrizDeRoles::test_la_matriz_congelada_no_depende_de_la_fecha_de_empaquetado` lo exigen).

**Límite residual declarado (no oculto):** los artefactos que **no** declaran su fecha de
captura (`api/data/amenaza_remocion_masa.geojson`, `api/data/areas_en_riesgo.geojson`,
`api/data/barranquilla_adopcion_anexo1.json`) siguen anclados en la fecha de creación del
archivo, que es su doctrina declarada y probada (`TestFrescura`, límites 2027-09-01 y
2026-12-19). Sus commits son históricos y estables, así que la matriz congelada se reproduce;
si alguno se volviera a commitear **sin cambiar su contenido**, su ventana se movería y habría
que re-sellar la matriz — se declara aquí para que nadie lo descubra por sorpresa.

La fecha de referencia es `reference_date` del registro (**2026-09-29**): la frescura se mide
contra la ventana congelada del pack, no contra el reloj de la máquina. Así «¿sirve hoy?» es
determinista y auditable.

---

## 4 · Inventario de snapshots REALES (`descubrir_snapshots`)

Para cada artefacto se registra: **ruta**, **fecha de creación/commit**
(`git log -1 --format=%cI -- <ruta>`, con una sola pasada de git; si el archivo no está en
git, se declara el `mtime` con su origen), **bytes**, **sha256**, `kind`, **fuentes** que
puede sustituir, **atributos que puede satisfacer**, consulta declarada y **vigencia**.

| `artifact_id` | Ruta | Kind | Fuente | Atributos | Sirve |
|---|---|---|---|---|---|
| `SNAP_POT_REMOCION_MASA` | `api/data/amenaza_remocion_masa.geojson` | `PACKAGED_GEOJSON` | `POT_BAQ_REMOCION_2024` | `remocion` | **SÍ** (RIESGO 365 d → 2027-09-01) |
| `SNAP_POT_AREAS_EN_RIESGO` | `api/data/areas_en_riesgo.geojson` | `PACKAGED_GEOJSON` | `POT_BAQ_RIESGO_2024` | `riesgo` | **SÍ** (hasta 2027-09-01) |
| `SNAP_ADOPCION_CATASTRAL_ANEXO1` | `api/data/barranquilla_adopcion_anexo1.json` | `PACKAGED_REGISTRY` | `CATASTRO_BAQ_ADOPCION_ANEXO1` | `identidad_nupre` | **SÍ** (CATASTRO 90 d → 2026-12-19) |
| `SNAP_OSM_OVERPASS_CAPTURA` | `docs/source_pack/raw/golden/osm_overpass.json` | `RAW_CAPTURE` | `OSM_OVERPASS` | `servicios_de_contexto` | **SÍ** (CONTEXTO 30 d → 2026-10-29) |
| `SNAP_LONJA_METODOLOGIA` | `motor_tma_lonja_baq_v1.0/…/lonja_baq_metodologia.yaml` | `PACKAGED_YAML` | `LONJA_MARKET_BAQ` | `mercado` | **NO — VENCIDO** (el artefacto declara `vigencia_hasta = 2026-08-31`) |
| `SNAP_ESTRATO_PROBE_TRACES` | `docs/forensics/040-646406/golden_03i1/ESTRATO_PROBE_TRACE.json` | `PROBE_TRACE` | `POT_BAQ_ESTRATIFICACION` | *(ninguno)* | **NO — NO_UTILIZABLE** |
| `SNAP_CATASTRO_PREDIO_FIXTURE` | `docs/source_pack/raw/golden/catastro_baq_predio.json` | `TEST_FIXTURE` | `CATASTRO_BAQ_PREDIO` | *(ninguno)* | **NO — NO_UTILIZABLE** |

Exclusiones declaradas (nada se oculta y nada no declarado se usa):

* **Sonda de estratificación (`PROBE_TRACE`)**: la captura devuelve las manzanas del **buffer**
  de 150 m (`codigo_manzana …006/…007`) y el predio Golden está en la manzana `…004`. Usarla
  para afirmar el estrato del predio sería una **inferencia espacial por vecindad**, prohibida
  para un hecho oficial (`BINDING_ESPACIAL_CONTEXTO` no autoriza identidad ni hecho oficial).
* **`catastro_baq_predio.json` (`TEST_FIXTURE`)**: el propio registro lo declara
  `evidence.origin = ARTEFACTO_DE_PRUEBA` (lo escribe `tests/test_source_pack_contract.py`).
  Usarlo como evidencia sería **fabricar el dato**.
* **Resto de artefactos hallados** (ver `resumen.total_artefactos` en
  `SNAPSHOT_INVENTORY.json`: incluye `_raw_cache*`, `_tree.json`, sondas de red y salidas
  forenses): se listan en `SNAPSHOT_INVENTORY.json` con `declarado: false`, `usable: false` y
  motivo «usarlo exigiría inventar su autorización».

Anti-invención: la prueba `test_los_snapshots_declarados_citan_su_respaldo_en_el_registro`
verifica que **cada snapshot usable está respaldado por un campo del registro**
(`local_fallback` o `base_url` local), y `test_cada_snapshot_declarado_tiene_sha256_bytes_y_fecha_REALES`
recalcula el sha256 y los bytes de cada archivo.

---

## 5 · API pública

```python
# api/acquisition.py
modos_por_fuente(registro=None, *, fecha=None, inventario=None) -> {sid: {...}}
snapshot_para(atributo, *, registro=None, fecha=None, inventario=None) -> [snapshot...]
resolver_con_acquisition_mode(atributo, *, consultas, registro=None, fecha=None,
                              contexto=None, cobertura=None, inventario=None) -> resultado
provenance_adquisicion(resultado) -> {original_source, acquisition_mode, ...} | {}
FRESHNESS_DEFAULT: {familia: {dias, fundamento}}
```

Extensiones declaradas (necesarias para el E2E y la matriz):

```python
resolver_dominio_con_acquisition_mode(atributos, ...)         # varios atributos
resolver_identidad_canonica(entrada, ...)                     # dirección O matrícula
matriz_roles(...) / escribir_matriz(...) / leer_matriz(...)   # matriz de 11 columnas
estado_operativo(...)                                         # CONTRACT_FROZEN vs OPERATIONAL_READY
descubrir_snapshots() / inventario_snapshots()                # inventario real
sellar_registro() / escribir_registro_gemelo() / sellar_manifest()
payload_efectivo(resultado) / resultado_efectivo(resultado)    # evidencia de la consulta efectiva
partes_del_folio(folio) / marcadores_de_unidad(direccion)      # reglas declaradas de entrada
hash_contenido(payload)                                        # hash sin metadata de corrida
```

Comandos:

```bash
python -m api.acquisition --estado       # veredicto + cobertura CORE (offline)
python -m api.acquisition --inventario   # inventario de snapshots (JSON)
python -m api.acquisition --matriz       # matriz de adquisición (CSV a stdout)
python -m api.acquisition --escribir     # sella registro+gemelo, matriz, inventario y manifest
```

### 5.1 Entradas sin intervención manual (reglas declaradas)

* **Folio SNR** = `<código ORIP>-<FMI>` (p. ej. `040-646406` → `codigo_registral=040`,
  `fmi=646406`). Son **dos claves tipadas exactas** del registro de adopción: la matrícula
  entra por dos claves sin que nadie aporte nada más.
* **Nomenclatura municipal**: `TO 8 AP 430` → torre/apartamento, para que las dos entradas
  describan la MISMA unidad.
* `intervencion_manual` y `requiere_identificadores_manuales` son **siempre `False`**; lo que
  falte se declara («no se pide el dato a una persona»), nunca se solicita.

### 5.2 Identidad canónica por cualquiera de las dos entradas

`resolver_identidad_canonica` encadena la escalera y construye la identidad con
`api/canonical.build_canonical_property_identity` a partir de la evidencia **convergida** (el
registro oficial + las dos partes del folio), no de la forma de entrada: el mismo inmueble
alcanza la **MISMA** `CanonicalPropertyIdentity` por dirección o por matrícula.

Regla declarada de confianza (`GRADO_MINIMO_MATCH_EXACT = 2`): **dos o más claves EXACTAS
tipadas** que apuntan al MISMO registro → identificación exacta (`MATCH_EXACT`,
`VERIFIED_UNIT_IDENTITY`); **una sola** clave → `MATCH_BY_MATRICULA` y la identidad **NO** se
eleva. El grado real se publica siempre (`match_status`, `match_degree`,
`claves_exactas_usadas`) junto a `identity_verified_por_grado` (que es `true` solo con las
tres), de modo que ninguna de las dos semánticas queda oculta.

---

## 6 · Reproducibilidad

* Dos corridas con las **mismas respuestas crudas** producen los **mismos payloads
  normalizados**, los **mismos bindings**, la **misma precedencia** y los **mismos
  `content_hash`** (prueba `TestReproducibilidad`).
* `queried_at`, `run_id`, `query_id` y `generated_at` quedan **FUERA de todo hash de
  contenido** (`hash_contenido` los excluye); el `content_hash` de un snapshot es el **sha256
  del archivo**, no de la corrida.
* La matriz y el inventario son **calculados**: una prueba recalcula y compara con el archivo
  versionado (nada se escribe a mano).
* La **ventana de frescura** se ancla en la fecha de captura que el artefacto declara, no en
  la fecha de commit/mtime (hecho del empaquetado): mover el empaquetado no cambia una sola
  celda de la matriz congelada (ver §3.1).

---

## 7 · Estado declarado hoy (ventana 2026-09-29)

* **Geoportal HTTP 403 (Cloudflare) verificado**: sonda propia en la ventana (HTTP 403,
  `Server: cloudflare`) y evidencia congelada `raw/golden/_layers_probe.json` con **150/150
  intentos en 403**. Toda ausencia derivada de esto se declara `SOURCE_UNAVAILABLE`, **jamás**
  `NO_MATCH`.
* **`LONJA_MARKET_BAQ`**: al sellarse esta capa, el registro vigente **no la lista en
  `sources`**; la declara en el bloque `no_fuentes_institucionales` (identificador histórico
  sellado, `en_source_registry: false`, `aporta_datos_a_dictus: false`). El dominio `mercado`
  queda por tanto **sin fuente registrada** y así se declara en la matriz. Con independencia
  de esa decisión, el snapshot congelado de la metodología **está VENCIDO** por su propia
  vigencia (`hasta 2026-08-31` < corrida `2026-09-29`), así que **no resolvería mercado** en
  ningún caso.
* **Resumen de rutas** `fuente | modo | snapshot | frescura | ¿sirve hoy?`:

| Fuente | Modo declarado | Snapshot | Frescura | ¿Sirve hoy? |
|---|---|---|---|---|
| `CATASTRO_BAQ_ADOPCION_ANEXO1` | `AUTHORIZED_FALLBACK` | `api/data/barranquilla_adopcion_anexo1.json` | CATASTRO 90 d → 2026-12-19 | **SÍ** (identidad por matrícula) |
| `POT_BAQ_REMOCION_2024` | `LIVE_QUERY` | `api/data/amenaza_remocion_masa.geojson` | RIESGO 365 d → 2027-09-01 | **SÍ** (por `AUTOMATED_SNAPSHOT`) |
| `POT_BAQ_RIESGO_2024` | `LIVE_QUERY` | `api/data/areas_en_riesgo.geojson` | RIESGO 365 d → 2027-09-01 | **SÍ** (por `AUTOMATED_SNAPSHOT`) |
| `OSM_OVERPASS` | `LIVE_QUERY` | `docs/source_pack/raw/golden/osm_overpass.json` | CONTEXTO 30 d → 2026-10-29 | **SÍ** (contexto) |
| `CATASTRO_BAQ_DIRECCION`, `CATASTRO_BAQ_PREDIO`, `CATASTRO_BAQ_TERRENO`, `CATASTRO_BAQ_CONSTRUCCION`, `CATASTRO_BAQ_DESTINO_ECONOMICO`, `CATASTRO_BAQ_MANZANA` | `LIVE_QUERY` | — | — | **NO** (403, sin snapshot) |
| `POT_BAQ_AREAS_ACTIVIDAD`, `POT_BAQ_POLIGONOS_USO`, `POT_BAQ_TRATAMIENTO`, `POT_BAQ_EDIFICABILIDAD`, `POT_BAQ_BARRIOS`, `POT_BAQ_LOCALIDADES`, `POT_BAQ_ESTRATIFICACION`, `POT_BAQ_INUNDACION_2024`, `POT_BAQ_INUNDACION_HIST` | `LIVE_QUERY` | — (la sonda de estrato se **excluye** por vecindad) | — | **NO** (403 / deshabilitada) |
| `EQUIPAMIENTO_18…27` | `LIVE_QUERY` | — | — | **NO** (deshabilitadas) |
| `MAPILLARY`, `GOOGLE_STREET_VIEW` | `LIVE_QUERY` | — | — | **NO** (sin credenciales y fail-closed por términos) |
| `SOLAR_ENGINE`, `SHADOW_FACADE_EXPOSURE` | `LIVE_QUERY` (cálculo por corrida) | — | — | **SÍ** |
| `LONJA_MARKET_BAQ` | `AUTHORIZED_FALLBACK` | `…/lonja_baq_metodologia.yaml` | MERCADO 180 d **∩** artefacto `2026-08-31` | **NO — VENCIDO** |

* **Conclusión medida** (`python -m api.acquisition --estado`):

```
CORE cubiertos:      identidad, remocion, riesgo
CORE NO cubiertos:   direccion, predio, uso_pot, tratamiento, edificabilidad, inundacion, mercado
VEREDICTO:           CONTRACT_FROZEN / OPERATIONAL_NOT_READY
```

---

## 8 · Re-sellado y trazabilidad

```bash
python -m api.acquisition --escribir   # registro + gemelo + matriz + inventario + manifest
python -m api.acquisition --estado     # imprime el veredicto vigente
python -m pytest \
  tests/test_source_pack_acquisition_modes.py \
  tests/test_source_pack_resolution_ladder.py \
  tests/test_source_pack_contract.py -q
```

* `scripts/source_pack_build.py --check` valida el **constructor** del registro; **no** publica
  la capa de adquisición (`product_role`, `acquisition_mode`, `acquisition_snapshot`). Si se
  regenera el registro con el constructor, hay que re-sellar con `--escribir` para volver a
  publicarla. Es una limitación declarada, no un olvido: `scripts/` está fuera del alcance de
  esta misión.
* El manifest publica `acquisition_modes`, `product_roles`, `operational_readiness` y
  `snapshot_inventory`, y recalcula `source_metadata_hashes` sobre la entrada **sellada**.

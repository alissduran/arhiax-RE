# BARRANQUILLA SOURCE PACK v1.0 — PRECEDENCIA DE FUENTES

**Objeto.** Congelar el criterio con el que el pack decide **qué fuente gana** cuando dos o más declaran lo mismo, y **qué se declara** cuando ninguna gana. No reescribe el registro (lo produce `scripts/source_pack_build.py` → `docs/source_pack/barranquilla_sources_v1.json`): justifica el campo `precedence` que ese registro declara por fuente.

## 0. Evidencia leída

| Artefacto | Qué se toma |
|---|---|
| `api/dictus_sources.py` | constantes de autoridad/precedencia, `resolver_precedencia`, `elegir_predio_canonico`, `identidad_autorizada_por_binding`, `separar_equipamiento`, `altura_fisica`, `consultar` |
| `scripts/source_pack_build.py` | registro declarado (**35 fuentes**), `NORM_POT_2024 = "Decreto 893 de 2024"`, `precedence_rules` del manifest |
| `tests/test_source_pack_contract.py` | pruebas bloqueantes de precedencia, binding, altura y equipamiento |
| `docs/forensics/040-646406/dictus_2b/DICTUS_RUN_STATE_040-646406.json` | caso Golden (folio 040-646406) |
| `api/geospatial_engine.py`, `api/data/amenaza_remocion_masa.geojson`, `api/data/areas_en_riesgo.geojson` | capas POT de riesgo empaquetadas |
| `motor_tma_lonja_baq_v1.0/motor_tma_lonja_baq_v1.0/lonja_layer/lonja_baq_metodologia.yaml` | metodología contractual de la Lonja BAQ |
| `api/market_context.py`, `api/street_imagery.py`, `api/catastro_predio.py`, `api/barranquilla_adopcion.py` | consumidores que aplican la precedencia |

## 1. Principio: la precedencia es explícita, declarada y auditable

La precedencia **no se infiere en tiempo de ejecución**: viene declarada por fuente (`precedence`) y por clase (`authority_class`). Ninguna fuente sub-normativa puede ganar en silencio:

1. `resolver_precedencia` devuelve siempre `silent_override: False` (literal en el retorno, §12 de `api/dictus_sources.py`) y nunca descarta un candidato sin ponerlo en `displaced`.
2. El manifest publica la misma regla: `precedence_rules.silent_override = false` (`construir_manifest` en `scripts/source_pack_build.py`).
3. Regla dura del módulo: *«Ninguna fuente `CONTEXTUAL_EXTERNAL` ni `CALCULADA` se presenta como autoridad normativa»* (docstring de `api/dictus_sources.py`).
4. La ausencia nunca se convierte en negación: `ESTADOS_SIN_DATO = (SOURCE_UNAVAILABLE, NOT_SUPPORTED, QUERY_FAILED)` y `consultar()` jamás traduce una ausencia a `NO_MATCH`.
5. Una fuente deshabilitada (`enabled: false`) devuelve `NOT_SUPPORTED`, no un valor: la precedencia no habilita lo que no está verificado.

## 2. `authority_class` y `precedence` son dos ejes distintos

`authority_class` responde **quién habla**; `precedence` responde **qué versión de lo mismo rige**. Las clases son cerradas (`CLASES_AUTORIDAD`) y solo las normativas pueden sostener una afirmación normativa (`CLASES_NORMATIVAS = (AUTHORITATIVE_OFFICIAL, AUTHORITATIVE_CONTRACTUAL)`):

| Clase | Sostiene afirmación normativa | Fuentes del registro |
|---|---|---|
| `AUTHORITATIVE_OFFICIAL` | Sí | catastro, POT, equipamiento oficial |
| `AUTHORITATIVE_CONTRACTUAL` | Sí, pero **solo metodológica de valoración** | `LONJA_MARKET_BAQ` |
| `CONTEXTUAL_EXTERNAL` | **No** | `OSM_OVERPASS`, `MAPILLARY`, `GOOGLE_STREET_VIEW` |
| `COMPUTED` | **No** | `SOLAR_ENGINE`, `SHADOW_FACADE_EXPOSURE` |

## 3. Jerarquía de tres niveles para riesgo: `CURRENT_NORMATIVE` > `CURRENT_OFFICIAL` > `HISTORICAL_REFERENCE`

`PRECEDENCIA_RIESGO = (CURRENT_NORMATIVE, CURRENT_OFFICIAL, HISTORICAL_REFERENCE)`; `resolver_precedencia(candidatos)` devuelve `{selected, displaced, precedence_order, silent_override, reason}`.

**(a) Por qué gana lo vigente.** El POT vigente de Barranquilla es la norma aplicable: sus capas de amenaza son las que producen efectos jurídicos sobre el predio (determinantes de ordenamiento y zonas de riesgo no mitigable — marco que el pack declara como *«Ley 388 de 1997 (zonas de riesgo no mitigable; determinantes de ordenamiento)»* en `legal_context.ordenamiento_territorial` de `scripts/source_pack_build.py`, arts. 35 y ss.). Las capas 2024 se registran con `legal_or_normative_context = "Decreto 893 de 2024"` (`NORM_POT_2024`) y `precedence = CURRENT_NORMATIVE`, y el motivo devuelto es literal: *«La capa vigente del Decreto 893 de 2024 tiene precedencia normativa»*. El texto del articulado no se verificó en esta corrida (no hay copia local): la cita procede del marco declarado por el pack.

**(b) Una capa histórica no se asciende nunca.** `POT_BAQ_REMOCION_HIST`, `POT_BAQ_INUNDACION_HIST` y `POT_BAQ_RIESGO_HIST` son `HISTORICAL_REFERENCE` y están **deshabilitadas**: su función es ser referencia comparativa **declarada**, no fuente de decisión. En `resolver_precedencia` todo candidato que no sea `CURRENT_NORMATIVE`/`CURRENT_OFFICIAL` cae en `displaced`, y el orden de entrada no altera el ganador (`test_orden_invertido_no_cambia_el_ganador`, `test_gana_la_vigente_y_se_declara_la_desplazada`).

**(c) Si solo hay capa histórica, se declara SIN DATO.** Con un único candidato histórico, `selected` es `None`, el histórico viaja en `displaced` y el `reason` es *«No se pudo determinar capa vigente: se declara SIN DATO.»* (`test_sin_vigente_declara_sin_dato_y_conserva_la_historica`). El sistema **no** rellena el hueco con la versión anterior ni con un valor por defecto.

## 4. Identidad: binding catastral canónico > coincidencia espacial

`PRECEDENCIA_BINDING = (NUPRE_EXACTO, NUMERO_PREDIAL_EXACTO, RELACION_OFICIAL_PREDIO, DIRECCION_OFICIAL_LIGADA, ESPACIAL_SOLO_CONTEXTO)`, pero **solo los cuatro primeros autorizan identidad** (`BINDINGS_QUE_AUTORIZAN_IDENTIDAD`); `identidad_autorizada_por_binding()` devuelve `False` para `ESPACIAL_SOLO_CONTEXTO` y `NO_BINDING`.

| Nivel | Qué lo produce | Autoriza identidad |
|---|---|---|
| `NUPRE_EXACTO` | `nupre`/`codigo_homologado` normalizado, exacto | Sí |
| `NUMERO_PREDIAL_EXACTO` | `numero_predial` exacto | Sí |
| `RELACION_OFICIAL_PREDIO` | enlaces declarados por el propio servicio | Sí |
| `DIRECCION_OFICIAL_LIGADA` | dirección ligada al predio por el servicio | Sí |
| `ESPACIAL_SOLO_CONTEXTO` | buffer/intersección geométrica | **No: es contexto** |
| `NO_BINDING` | nada casó | No: la identidad no se afirma |

**Por qué.** La intersección espacial identifica **contexto**, no **identidad**: un vecino puede caer en el mismo buffer. Por eso `elegir_predio_canonico` **nunca elige `features[0]`** (`test_orden_de_features_no_decide`, con el predio correcto en segunda posición) y, si nada casa, devuelve `feature: None` con motivo explícito. Un identificador no sustituye a otro: `api/barranquilla_adopcion.py` solo produce identidad verificada con `EXACT_3` (`numero_predial` + `codigo_homologado` + `fmi`) y devuelve `IDENTITY_CONFLICT` con `identity_verified: False` cuando dos identificadores apuntan a registros disjuntos.

**Caso Golden `040-646406`.** La identidad se resolvió por NUPRE: `estado = MATCH_BY_NUPRE`, `resolution_status = EXACT`, `resolution_method = nupre`, `resolution_confidence = VERIFIED_UNIT_IDENTITY`, con `nupre AFT0005BOHA` y `codigo_catastral 080010103000010040001908040002`. Los recibos lo confirman: `receipts.catastro = {consultado: true, exacto: true, espacial: false}` — el camino espacial no autorizó nada. La coordenada oficial es del **predio**, no de la unidad: `coordinate_provenance` declara `source_system = CATASTRO_MUNICIPAL_BARRANQUILLA_ARCGIS`, `layer = "105 · direccion"`, `resolution_method = DIRECCION_OFICIAL_LIGADA_POR_GUID`, `canonical_binding_fields = [nupre, numero_predial]`, y `coordinate_scope` advierte que la geometría oficial *«NO acredita la posición del apartamento dentro de la edificación»*. El registro de adopción catastral confirma el mismo predio por triple identificador (`api/data/barranquilla_adopcion_anexo1.json`: predial `080010103000010040001908040002` · `codigo_homologado` AFT0005BOHA · `fmi` 646406).

## 5. Contractual vs. contextual

- `LONJA_MARKET_BAQ` es `AUTHORITATIVE_CONTRACTUAL`: sostiene una **afirmación metodológica de valoración** (vigencia, métodos, pesos, tolerancias, valor de sector), **no** una afirmación normativa territorial (riesgo, afectación, uso permitido). El manifest lo fija como regla: *«AUTHORITATIVE_CONTRACTUAL (Lonja) sostiene la metodología de valoración, no una afirmación normativa territorial»*. Del YAML: entidad *Lonja de Propiedad Raíz de Barranquilla*, `regla_consolidacion.version = "0.1-codiseno"`, autor *Junta Técnica de Avalúos Corporativos*, `pesos_default` M1 0.60 / M2 0.30 / M3 0.10, `tolerancia_coherencia_pct` 0.15, `coeficiente_variacion_max` 0.075, `redistribucion_fallback: true`, vigencia 2026-05-08 → 2026-08-31, marco propio (Ley 1673 de 2013; Decreto 556 de 2014; Decreto 1420 de 1998; Resolución IGAC 620 de 2008; Resolución IGAC 1040 de 2023 mod. 746 de 2024; NTS S 01/S 03/I 01/M 01). Su trazabilidad se sella con el sha256 del YAML (`api/market_context.py::market_methodology`), observado como `4ccd5832eacf3117424fa436765e80d3e9198b666d9e3c293063a5b207ebd348`.
- `OSM_OVERPASS`, `MAPILLARY` y `GOOGLE_STREET_VIEW` son `CONTEXTUAL_EXTERNAL` (`CONTEXTUAL_REFERENCE`) y **jamás autoridad**: no pueden sostener «uso permitido», «riesgo» ni «afectación». `api/street_imagery.py` declara `authority_class = CONTEXTUAL_EXTERNA` en la procedencia de todo proveedor de imagery, y la fachada se degrada a `FACADE_VIEW_CONTEXTUAL` cuando la imagen solo alcanza para contexto.
- `separar_equipamiento()` mantiene `official_equipment` separado de `contextual_services` (donde también cae `COMPUTED`) y devuelve `mixed_authority: False`: las dos procedencias no se funden en una lista única.

## 6. `COMPUTED`: cálculo propio, nunca norma

`SOLAR_ENGINE` y `SHADOW_FACADE_EXPOSURE` son `COMPUTED` (`COMPUTED_REFERENCE`): resultados de `api/solar_engine.py`, `api/facade_solar.py` y `api/shadow_render.py`, etiquetados como análisis automatizado (`ETIQUETA_ANALISIS_SOLAR = "ANÁLISIS SOLAR AUTOMATIZADO DE LA FACHADA VISIBLE"`) y nunca como norma. El run state Golden lo declara `tipo = SIMULACION_GEOMETRICA`, `altura_dependiente = true` y advertencia de que no sustituye inspección física.

**Regla bloqueante:** `POT.altura_max` es altura **normativa** en pisos (Golden: `altura_maxima` «11»); `altura_fisica()` la rechaza como altura física (`building_physical_height: null`, `shadow_confidence: DEGRADED`) y sin altura física declarada no se simula sombra con longitud exacta. Degradar no bloquea: baja la confianza y se declara.

## 7. Registro: 35 fuentes y su precedencia declarada

Verificado con `python scripts/source_pack_build.py --check`: *«OK registro: 35 fuentes (20 habilitadas, 15 deshabilitadas declaradas)»*, y corroborado contra el registro congelado `docs/source_pack/barranquilla_sources_v1.json` (35 fuentes) y su manifest (`approved_sources` 20 · `disabled_sources` 15 · `precedence_rules.silent_override: false`). El comentario del propio script dice «34 fuentes»: es desfase de comentario, no de registro.

| Fuentes (`source_id`) | `authority_class` | `precedence` | Estado declarado |
|---|---|---|---|
| `CATASTRO_BAQ_DIRECCION` (105) · `_TERRENO` (315) · `_CONSTRUCCION` (310) · `_PREDIO` (tabla 100) · `_MANZANA` (320) · `_DESTINO_ECONOMICO` (`catastro/destinoseconomicos`) · `_ADOPCION_ANEXO1` (Res. GGCD 003 del 07/03/2025) | `AUTHORITATIVE_OFFICIAL` | `CURRENT_OFFICIAL` | 7 habilitadas |
| `POT_BAQ_BARRIOS` · `_LOCALIDADES` · `_ESTRATIFICACION` · `_TRATAMIENTO` · `_EDIFICABILIDAD` | `AUTHORITATIVE_OFFICIAL` | `CURRENT_OFFICIAL` | habilitadas (`layer_id` 1 y 4; los ids del enunciado solo en `spec_layer_id` 91/92/83/89, no corroborados) |
| `POT_BAQ_AREAS_ACTIVIDAD` (85) · `POT_BAQ_POLIGONOS_USO` (87) | `AUTHORITATIVE_OFFICIAL` | `CURRENT_OFFICIAL` | **deshabilitadas** (`UNVERIFIED_LIVE`) → `NOT_SUPPORTED` |
| `POT_BAQ_REMOCION_2024` (73) · `POT_BAQ_RIESGO_2024` (81) | `AUTHORITATIVE_OFFICIAL` | `CURRENT_NORMATIVE` | habilitadas, con copia POT empaquetada como fallback declarado |
| `POT_BAQ_INUNDACION_2024` (77) | `AUTHORITATIVE_OFFICIAL` | `CURRENT_NORMATIVE` | **deshabilitada** (sin capa verificada ni copia empaquetada) → `NOT_SUPPORTED` |
| `POT_BAQ_REMOCION_HIST` (71) · `_INUNDACION_HIST` (75) · `_RIESGO_HIST` (79) | `AUTHORITATIVE_OFFICIAL` | `HISTORICAL_REFERENCE` | deshabilitadas: referencia comparativa declarada |
| `EQUIPAMIENTO_18`, `20`, `21`, `22`, `23`, `24`, `25`, `26`, `27` (`OFFICIAL_EQUIPMENT_CONTEXT`) | `AUTHORITATIVE_OFFICIAL` | `CURRENT_OFFICIAL` | deshabilitadas (9): contexto oficial aún no verificado |
| `OSM_OVERPASS` · `MAPILLARY` · `GOOGLE_STREET_VIEW` | `CONTEXTUAL_EXTERNAL` | `CONTEXTUAL_REFERENCE` | habilitadas: contexto, nunca autoridad |
| `LONJA_MARKET_BAQ` | `AUTHORITATIVE_CONTRACTUAL` | `CURRENT_OFFICIAL` | habilitada: metodología de valoración |
| `SOLAR_ENGINE` · `SHADOW_FACADE_EXPOSURE` | `COMPUTED` | `COMPUTED_REFERENCE` | habilitadas: cálculo propio etiquetado |

## 8. Tabla resumen: situación → quién gana → desplazadas → qué se declara

| Situación | Fuente que gana | Fuentes desplazadas | Qué se declara |
|---|---|---|---|
| Riesgo con capa vigente y anteriores | `CURRENT_NORMATIVE` (`POT_BAQ_REMOCION_2024`, `POT_BAQ_RIESGO_2024`) | las `_HIST` quedan en `displaced` | `selected`, `displaced`, `precedence_order`, `silent_override: false`, motivo del Decreto 893 de 2024 |
| Solo existe capa histórica | ninguna | la histórica queda en `displaced` | `selected: null` y «se declara SIN DATO» |
| Capa vigente sin dato (inundación) | ninguna | — | `NOT_SUPPORTED`; nunca «sin amenaza de inundación» |
| Varios polígonos de la MISMA capa contienen el punto | el de mayor severidad (a igualdad, menor área) | el resto va en `detalles` | `nivel`, `total_coincidencias`: no se elige en silencio |
| Identidad del predio | `NUPRE_EXACTO` (Golden: `MATCH_BY_NUPRE`) | predial, relación, dirección, espacial | identidad autorizada: `identidad_autorizada_por_binding()` → `True` |
| Solo coincidencia espacial | ninguna | — | `ESPACIAL_SOLO_CONTEXTO`: contexto, no identidad; si nada casa, `NO_BINDING` y jamás `features[0]` |
| Equipamiento oficial y POI de contexto | ninguno «gana»: se separan | — | `official_equipment` ≠ `contextual_services`, `mixed_authority: false` |
| Altura normativa POT para simular sombra | ninguna (rechazada) | — | `building_physical_height: null`, `shadow_confidence: DEGRADED` |
| Destino económico catastral vs. uso POT | ninguno: hechos distintos | — | dos objetos separados; uno no se copia sobre el otro |

## 9. Conflictos y cómo se declaran (sin resolverlos en silencio)

**9.1 «Capa vigente sin dato».** `POT_BAQ_INUNDACION_2024` es `CURRENT_NORMATIVE` pero está deshabilitada: `consultar()` devuelve `NOT_SUPPORTED` con detalle *«La fuente está deshabilitada en el Source Pack»*. Declararla vigente **no la vuelve disponible**, y la capa histórica de inundación (`_HIST`, 75) **no** se promueve a vigente: se declara ausencia de dato.

**9.2 «Identificadores contradictorios».** `elegir_predio_canonico` resuelve por nivel declarado (NUPRE y código homologado antes que predial; estos antes que relación oficial y dirección): manda el orden de los identificadores, no la posición en la respuesta. Cuando dos identificadores apuntan a registros **disjuntos**, `api/barranquilla_adopcion.py` devuelve `CONFLICT` / `IDENTITY_CONFLICT` con `identity_verified: False` — no se elige uno.

**9.3 «Barrio por dos capas distintas».** `_consolidar_valor()` (`api/catastro_predio.py`, 03D.1) consolida por campo: si todas las features expresan el mismo valor lo devuelve; si **discrepan** devuelve `(None, "AMBIGUOUS_CONTEXT")` y el campo se lista en `campos_ambiguos` — **no se elige la primera**. La ambigüedad viaja al consumidor (`api/market_context.py` propaga `campos_ambiguos` y marca `AMBIGUOUS_CONTEXT`) y se declara en el dictamen en vez de afirmarse.

## 10. Límites y contradicciones detectadas en esta corrida

1. **Comentario vs. registro (RESUELTO):** durante el ensamblaje el comentario de `scripts/source_pack_build.py` decía «34 fuentes» mientras el registro tiene **35**; el comentario se corrigió a «35 fuentes» y hoy coinciden (verificado con `--check`). Se conserva la nota como registro de la verificación cruzada.
2. **`precedence` compartido entre ejes:** `LONJA_MARKET_BAQ` es `AUTHORITATIVE_CONTRACTUAL` pero su `precedence` es `CURRENT_OFFICIAL`, un nivel de `PRECEDENCIA_RIESGO`. No hay override silencioso, pero el rótulo es de riesgo: la Lonja **no debe** pasar como candidata a `resolver_precedencia` (el filtro correcto es `authority_class`).
3. **Niveles sin constante:** `CONTEXTUAL_REFERENCE` y `COMPUTED_REFERENCE` existen como literales del registro, **no** como constantes de `api/dictus_sources.py`; en `resolver_precedencia` todo nivel desconocido cae en `displaced` (dirección segura, pero conflaciona niveles).
4. **Artefacto sin sello normativo:** las capas empaquetadas (`api/data/amenaza_remocion_masa.geojson`: `objectid`, `niveldeamenaza`, `clase_suelo`, `st_area(shape)`; `api/data/areas_en_riesgo.geojson`: `objectid`, `nivelderiesgo`, `clasesuelo`, `st_area(shape)`) **no** llevan campo de versión ni de decreto: la atribución «Decreto 893 de 2024» es del registro, no del artefacto. No verificable dentro del GeoJSON en esta corrida.
5. **Vigencia contractual vencida y no bloqueante:** el YAML de la Lonja declara `vigencia_hasta: 2026-08-31`, y el run state Golden se generó el `2026-09-28` con `market_context.ready: true` y `blockers: []`. `api/market_context.py` expone `vigencia_hasta` y `_evaluate_ready` no lo evalúa: **no se localizó consumidor que convierta el vencimiento en bloqueo**.
6. **Capa vigente sin copia local:** `POT_BAQ_INUNDACION_2024` figura como `PACKAGED_REFERENCE` en `urban_source_summary` del run state con valor `null`, pero no existe GeoJSON de inundación en `api/data/` (solo remoción y áreas en riesgo): la corrida declaró `risk_context.inundacion = null`, es decir **NO EVALUADO**.
7. **Localidad (RESUELTO):** la nota del registro para `POT_BAQ_LOCALIDADES` se corrigió: la corrida Golden **sí** resolvió `localidad = "02"` por la capa oficial en vivo (`urban_context.localidad` y `market_context.official_urban_context.localidad`); lo que quedó SIN DATO fue la **comuna** (`property_identity.administrativo.comuna` es `null`, traza `NULL_VALUE`). Comuna y localidad no se confunden.
8. **Rutas de red no verificables aquí:** el geoportal respondió HTTP 403 durante la ventana de congelación (`docs/source_pack/raw/golden/_layers_probe.json`): los `layer_id` declarados de POT y equipamiento quedan como *no verificado en esta corrida*.

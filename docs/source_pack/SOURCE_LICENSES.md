# SOURCE LICENSES — BARRANQUILLA SOURCE PACK v1.0

**Pack:** `barranquilla-source-pack/1.0.0` · **Registro:** `barranquilla-sources-v1` (`docs/source_pack/barranquilla_sources_v1.json`) · **Manifest:** `barranquilla-source-pack-manifest/1.0.0` (`docs/source_pack/BARRANQUILLA_SOURCE_PACK_MANIFEST.json`, `generated_at: 2026-09-29T14:04:58Z`). **Caso Golden:** folio `040-646406`, NUPRE `AFT0005BOHA`.

**Objeto:** documentar, por `source_id` (35 fuentes), los términos declarados (`license_or_terms`), la POLÍTICA DE PERSISTENCIA (`can_persist_raw`), la política de incrustación de imagen del proveedor (`can_embed_image`) y el estado declarado `provider_terms_status`. Los valores por fuente se transcriben de `manifest.licenses.by_source` y del registro; donde el manifest usa un descriptor largo, se cita la etiqueta canónica (§3.0) y se conserva el texto íntegro en el manifest.

## 1. Política general de persistencia

| # | Regla | Anclaje exacto |
|---|---|---|
| P1 | El crudo se persiste SOLO si la licencia lo permite: `preservar_raw()` devuelve `None` y **no escribe nada** cuando `licencia["can_persist_raw"] is False`. | `api/dictus_sources.py::preservar_raw` |
| P2 | El crudo **nunca se modifica** y la normalización vive aparte (`payload_normalized`). | `preservar_raw` + `consultar` |
| P3 | Ruta determinista del crudo: `docs/source_pack/raw/golden/<source_id.lower()>.json` (`DIR_RAW`). | `preservar_raw`, `dictus_sources.DIR_RAW` |
| P4 | Si NO puede persistirse, el resultado **declara estado y no escribe archivo**: `raw_path=None`, `raw_persisted=False`; el `raw_hash` puede existir igualmente (integridad sin almacenamiento). | `dictus_sources.resultado` (`raw_hash`, `raw_persisted`, `raw_path`) |
| P5 | Si la fuente no declara `can_persist_raw`, el valor efectivo es `True` (`fuente.get("can_persist_raw", True)`): omitir el campo equivale a permitir. | `consultar`, línea 205 |
| P6 | Ausencia ≠ no coincidencia. Fallo del geoportal (HTTP 403) → `SOURCE_UNAVAILABLE`, jamás `NO_MATCH`. | `dictus_sources.ESTADOS_SIN_DATO`, `consultar` |
| P7 | Fuente deshabilitada (`enabled: false`) → `NOT_SUPPORTED`, sin red y **sin persistir crudo**. | `consultar` (rama `enabled is False`) |
| P8 | Imagen de tercero: matriz CERRADA por defecto; sólo evidencia VERIFICADA (`evidence_url` + `retrieved_at` + `sha256`) la abre; la metadata de la imagen sólo puede RESTRINGIR, nunca ampliar. | `persistence_policy`, `registrar_evidencia_terminos`, `verificar_terminos` |
| P9 | Rutas de adquisición: los proxies CORS de terceros NO son método de obtención autorizado; las sondas los registran como evidencia de intento, no como vía productiva. | `raw/golden/_retrieval_paths_probe*.json`, `_proxy_control_matrix.json`, `_service_tree.json` |

Equivalencias: registro `can_persist_raw` ↔ `preservar_raw(licencia=...)` y `street_imagery` `can_persist`; registro `can_embed_image` ↔ `street_imagery` `can_embed_in_pdf`. El flujo de copia se declara en `FLUJO_PERSISTENCIA` (`COPIAR_BAJO_CC_BY_SA_4_0_CON_ATRIBUCION` en Mapillary; `NINGUNO` en Google).

## 2. Vocabulario de `provider_terms_status`

Estados cerrados de `api/street_imagery.py` (`ESTADOS_TERMINOS`) y equivalencia con el descriptor declarado en el manifest:

| Estado (código) | Significado | Efecto | Descriptor del manifest que lo representa |
|---|---|---|---|
| `VERIFIED` | Términos consultados y hasheados en esta corrida (`url` + fecha + `sha256`) | Puede abrir la matriz si la evidencia lo autoriza | — |
| `DECLARED` | Licencia declarada por el proveedor, sin evidencia hasheada | Mantiene la matriz declarada; se cierra con `ARHIAX_IMAGERY_STRICT_TERMS` | `ODbL 1.0 (términos públicos verificados)` (OSM_OVERPASS) |
| `UNVERIFIED` | No verificable → FAIL-CLOSED | Cierra toda la matriz | `UNVERIFIED (no publicados junto al servicio…)`; `UNVERIFIED (fail-closed…)`; `UNVERIFIED (licencia CC BY-SA 4.0 declarada…)` |
| `NOT_APPLICABLE` | No hay licencia de tercero | Sin efecto | `N/A (cálculo propio)` |
| (fuera del vocabulario) | Términos contractuales declarados | Restringe difusión e incrustación | `CONTRACTUAL (uso autorizado dentro del motor TMA; no redistribuible)` (LONJA_MARKET_BAQ) |

## 3. Política por fuente

**3.0 Textos canónicos** (verbatim de `manifest.licenses.by_source`): **L-A** = «Datos abiertos de la Alcaldía Distrital de Barranquilla (geoportal miciudad.barranquilla.gov.co). Uso permitido con atribución a la fuente oficial. Los términos específicos no se publican junto al servicio (provider_terms_status=UNVERIFIED).» · **L-A2** (ANEXO1) = «Certificado de Tradición y Libertad (SNR) y anexo de adopción catastral: documentos oficiales aportados por el usuario; se conserva copia normalizada con hash, no el original completo.» · **L-A3** (riesgo 2024) = «Capa POT oficial empaquetada localmente como copia normalizada (GeoJSON) del servicio de la Alcaldía; datos abiertos con atribución a la fuente oficial. Hash del archivo declarado en el manifest.» · **L-GSV** = «Google Maps Platform / Street View: sus términos prohíben almacenar o redistribuir las imágenes. provider_terms_status=UNVERIFIED → FAIL-CLOSED: no se persiste el crudo ni se incrusta la imagen.» · **L-MAP** = «CC BY-SA 4.0 — © Mapillary contributors. Atribución obligatoria y share-alike (texto de atribución declarado por api/street_imagery.py).» · **L-OSM** = «Open Database License (ODbL) 1.0 — © OpenStreetMap contributors. Atribución obligatoria; share-alike sobre bases derivadas.» · **L-LONJA** = «Metodología contractual de la Lonja de Propiedad Raíz de Barranquilla (lonja_baq_metodologia.yaml): documento de la Junta Técnica de Avalúos, no redistribuible sin contrato. Uso autorizado dentro del motor TMA de ARHIAX RE.» · **L-CMP** = «Cálculo propio de ARHIAX RE sobre entradas declaradas (coordenada, fecha, geometría oficial). Sin licencia de terceros sobre el resultado; reproducible y auditable.»
**3.0.b Estados canónicos:** **S-UNV** = `UNVERIFIED` (no publicados junto al servicio; uso con atribución a la fuente oficial) · **S-UNVf** = `UNVERIFIED` (fail-closed: no se persiste crudo ni se incrusta imagen) · **S-UNVm** = `UNVERIFIED` (licencia CC BY-SA 4.0 declarada por el proveedor; atribución obligatoria) · **S-ODbL** = `ODbL 1.0` (términos públicos verificados) · **S-CONTR** = `CONTRACTUAL` (uso autorizado dentro del motor TMA; no redistribuible) · **S-NA** = `N/A` (cálculo propio).

### 3.1 Catastro (Alcaldía Distrital de Barranquilla — Gerencia de Catastro Distrital)

| source_id | titular / proveedor | `license_or_terms` | `can_persist_raw` | `can_embed_image` | `provider_terms_status` | observación |
|---|---|---|---|---|---|---|
| CATASTRO_BAQ_DIRECCION | Alcaldía Distrital — Gerencia de Catastro Distrital | L-A | true | false | S-UNV | Capa vectorial: no hay imagen de proveedor. Persistir crudo con atribución; sin redistribución |
| CATASTRO_BAQ_TERRENO | ídem | L-A | true | false | S-UNV | ídem |
| CATASTRO_BAQ_CONSTRUCCION | ídem | L-A | true | false | S-UNV | Huella/altura usada por `api/shadow_render.py`; altura física regida por `dictus_sources.altura_fisica` |
| CATASTRO_BAQ_PREDIO | ídem | L-A | true | false | S-UNV | Crudo ya presente: `raw/golden/catastro_baq_predio.json` |
| CATASTRO_BAQ_MANZANA | ídem | L-A | true | false | S-UNV | ídem |
| CATASTRO_BAQ_DESTINO_ECONOMICO | ídem | L-A | true | false | S-UNV | Destino catastral NO se mapea a uso POT (`TestDestinoVsUsoPOT`) |
| CATASTRO_BAQ_ADOPCION_ANEXO1 | Alcaldía Distrital / IGAC — Resolución GGCD 003 de 2025 | L-A2 | true | false | S-UNV | Resolver `api/barranquilla_adopcion.py` sobre `api/data/barranquilla_adopcion_anexo1.json` (`GGCD 003`, 2025-03-07); se guarda copia normalizada con hash, no el original |

### 3.2 Ordenamiento / POT y riesgo (Alcaldía Distrital — Secretaría Distrital de Planeación)

| source_id | titular / proveedor | `license_or_terms` | `can_persist_raw` | `can_embed_image` | `provider_terms_status` | observación |
|---|---|---|---|---|---|---|
| POT_BAQ_BARRIOS | Alcaldía — Secretaría Distrital de Planeación | L-A | true | false | S-UNV | `precedence=CURRENT_OFFICIAL` |
| POT_BAQ_LOCALIDADES | ídem | L-A | true | false | S-UNV | Localidad del predio Golden quedó NO RESUELTA (`NULL_VALUE`): se declara |
| POT_BAQ_ESTRATIFICACION | ídem | L-A | true | false | S-UNV | Alimenta `api/market_context.py`; estrato faltante NO se sustituye |
| POT_BAQ_TRATAMIENTO | ídem | L-A | true | false | S-UNV | Tratamiento del Golden: `Consolidacion` |
| POT_BAQ_EDIFICABILIDAD | ídem | L-A | true | false | S-UNV | `altura_max` = altura NORMATIVA: prohibido usarla como altura física |
| POT_BAQ_AREAS_ACTIVIDAD | ídem | L-A | true | false | S-UNV | **`enabled: false`** → `NOT_SUPPORTED`, sin crudo. Crudo mínimo histórico: `raw/golden/pot_baq_areas_actividad.json` |
| POT_BAQ_POLIGONOS_USO | ídem | L-A | true | false | S-UNV | **`enabled: false`** → `NOT_SUPPORTED`, sin crudo |
| POT_BAQ_REMOCION_2024 | ídem — Decreto 893 de 2024 | L-A3 | true | false | S-UNV | `CURRENT_NORMATIVE`; paquete local `api/data/amenaza_remocion_masa.geojson` (8.160.494 B), hash en `manifest.source_metadata_hashes` |
| POT_BAQ_RIESGO_2024 | ídem — Decreto 893 de 2024 | L-A3 | true | false | S-UNV | `CURRENT_NORMATIVE`; paquete local `api/data/areas_en_riesgo.geojson` (6.176.524 B) |
| POT_BAQ_INUNDACION_2024 | ídem | L-A | true | false | S-UNV | **`enabled: false`**: sin capa verificada ni copia → `NOT_SUPPORTED`, nunca «sin amenaza» |
| POT_BAQ_REMOCION_HIST | ídem (capa anterior) | L-A | true | false | S-UNV | **`enabled: false`**; `HISTORICAL_REFERENCE`: referencia comparativa, no sustituye en silencio (`resolver_precedencia`, `silent_override=False`) |
| POT_BAQ_INUNDACION_HIST | ídem | L-A | true | false | S-UNV | **`enabled: false`**; `HISTORICAL_REFERENCE` |
| POT_BAQ_RIESGO_HIST | ídem | L-A | true | false | S-UNV | **`enabled: false`**; `HISTORICAL_REFERENCE` |

### 3.3 Equipamiento oficial (`OFFICIAL_EQUIPMENT_CONTEXT`)

| source_id | titular / proveedor | `license_or_terms` | `can_persist_raw` | `can_embed_image` | `provider_terms_status` | observación |
|---|---|---|---|---|---|---|
| EQUIPAMIENTO_18 | Alcaldía — capas de equipamiento oficial | L-A | true | false | S-UNV | **`enabled: false`**: `NOT_SUPPORTED` y sin crudo. El equipamiento que hoy reporta el pack proviene de OSM (contexto), no de la Alcaldía |
| EQUIPAMIENTO_20 | ídem | L-A | true | false | S-UNV | ídem `enabled: false` |
| EQUIPAMIENTO_21 | ídem | L-A | true | false | S-UNV | ídem |
| EQUIPAMIENTO_22 | ídem | L-A | true | false | S-UNV | ídem |
| EQUIPAMIENTO_23 | ídem | L-A | true | false | S-UNV | ídem |
| EQUIPAMIENTO_24 | ídem | L-A | true | false | S-UNV | ídem |
| EQUIPAMIENTO_25 | ídem | L-A | true | false | S-UNV | ídem |
| EQUIPAMIENTO_26 | ídem | L-A | true | false | S-UNV | ídem |
| EQUIPAMIENTO_27 | ídem | L-A | true | false | S-UNV | `authority_class=AUTHORITATIVE_OFFICIAL`: no se mezcla con POI contextuales (`separar_equipamiento`) |

### 3.4 Fuentes externas (`authority_class=CONTEXTUAL_EXTERNAL`)

| source_id | titular / proveedor | `license_or_terms` | `can_persist_raw` | `can_embed_image` | `provider_terms_status` | observación |
|---|---|---|---|---|---|---|
| OSM_OVERPASS | OpenStreetMap Foundation (datos colaborativos) | L-OSM | true | false | S-ODbL | Datos, no imágenes: no hay imagen de proveedor que incrustar. Ver §4.3 |
| MAPILLARY | Mapillary (Meta) — contributors | L-MAP | true | true | S-UNVm | Único proveedor con incrustación declarada; `FLUJO_PERSISTENCIA=COPIAR_BAJO_CC_BY_SA_4_0_CON_ATRIBUCION`. Ver §4.2 |
| GOOGLE_STREET_VIEW | Google LLC — Google Maps Platform | L-GSV | false | false | S-UNVf | FAIL-CLOSED: matriz cerrada, `FLUJO_PERSISTENCIA=NINGUNO`. Ver §4.1 |

### 3.5 Contractual / calculada

| source_id | titular / proveedor | `license_or_terms` | `can_persist_raw` | `can_embed_image` | `provider_terms_status` | observación |
|---|---|---|---|---|---|---|
| LONJA_MARKET_BAQ | Lonja de Propiedad Raíz de Barranquilla — Junta Técnica de Avalúos | L-LONJA | true | false | S-CONTR | Uso autorizado dentro del motor TMA; no redistribuible; se cita por id + versión + `sha256` (`market_methodology`). Ver §4.5 |
| SOLAR_ENGINE | ARHIAX RE — cálculo propio | L-CMP | true | false | S-NA | Resultado reproducible (`api/solar_engine.py`); sin licencia de terceros |
| SHADOW_FACADE_EXPOSURE | ARHIAX RE — cálculo propio | L-CMP | true | false | S-NA | `api/facade_solar.py` + `api/shadow_render.py`; la bandera `can_embed_image=false` significa «no hay imagen DE PROVEEDOR»: el PNG propio se rige por el manifiesto de activos visuales. Ver §4.6 |

## 4. Casos especiales

**4.1 Google Street View (prohibición de cachear/almacenar/derivar).** `GoogleStreetViewProvider` declara `LICENCIA_DECLARADA=""`, `TERMS_URL=https://cloud.google.com/maps-platform/terms`, `ATRIBUCION_TEXTO="© Google"`, `TERMS_STATUS_POR_DEFECTO=TERMS_UNVERIFIED` y matriz cerrada; el registro confirma `can_persist_raw=false`, `can_embed_image=false`. Consecuencia dura: `get_image()` **no descarga ni un byte** (`downloaded=False`, `bytes_written=0`) y devuelve `NOT_SUPPORTED` con motivo. La prohibición de almacenar/cachear es pública ([políticas Street View Static API](https://developers.google.com/maps/documentation/streetview/policies), [Maps Platform Terms](https://cloud.google.com/maps-platform/terms)); el estado objetivo tras verificación es `RESTRICTED` (prohibición explícita → matriz cerrada de forma permanente). `can_embed_image=false` mientras `provider_terms_status` sea `UNVERIFIED`.

**4.2 Mapillary (CC BY-SA 4.0).** Atribución obligatoria con texto EXACTO tomado del código (`MapillaryProvider.ATRIBUCION_TEXTO`): `© Mapillary contributors (CC BY-SA 4.0)`; `SHARE_ALIKE=True`. **Discrepancia declarada (no silenciada):** el manifest concede `can_persist_raw=true` y `can_embed_image=true` pero a la vez declara `provider_terms_status=UNVERIFIED` y lo lista en `licenses.unverified_terms` junto a Google; además `_estado_terminos()` del código devolvería `DECLARED` (`TERMS_STATUS_POR_DEFECTO=TERMS_DECLARED`). Bajo `persistence_policy`, `UNVERIFIED` cierra la matriz entera, y con `ARHIAX_IMAGERY_STRICT_TERMS` sólo `VERIFIED` habilita persistir: por tanto, mientras no se registre evidencia (url + fecha + `sha256`), el camino seguro es Mapillary efectivamente fail-closed. Licencia: [Mapillary terms](https://www.mapillary.com/terms), [CC BY-SA para datos abiertos](https://help.mapillary.com/hc/en-us/articles/115001770409-CC-BY-SA-license-for-open-data).

**4.3 OpenStreetMap / Overpass API (ODbL).** Atribución obligatoria «© OpenStreetMap contributors» y share-alike sobre bases derivadas; es la única fuente con términos públicos verificados declarados. Cada POI viaja con `source=OSM_OVERPASS` en su procedencia: [copyright OSM](https://www.openstreetmap.org/copyright), [guías de atribución OSMF](https://osmfoundation.org/wiki/Licence/Attribution_Guidelines).

**4.4 Datos abiertos de la Alcaldía (29 fuentes).** El Distrito publica apertura de datos ([Plan de Apertura de Datos](https://www.barranquilla.gov.co/documento/plan-de-apertura-de-datos/), [Gaceta 1150 — Artículo 3 Principios](https://www.barranquilla.gov.co/documento/gaceta-no-1150/?version=1), [Mi Ciudad — Catastro](https://catastro.barranquilla.gov.co/mi-ciudad/)), pero los términos específicos **no se publican junto al servicio**: todas las rutas probadas en la ventana devolvieron HTTP 403 de Cloudflare → `SOURCE_UNAVAILABLE`, nunca `NO_MATCH` (evidencia: `raw/golden/_retrieval_paths_probe.json`, `_layers_probe.json`, `_service_tree.json`, `_dns_probe_subdomains.json`, `_origin_ip_probe.json`, `_proxy_control_matrix.json`). Compensaciones declaradas: atribución obligatoria a la fuente oficial, `can_embed_image=false`, sin redistribución del crudo fuera del expediente y estado `UNVERIFIED` visible en la procedencia. Si el titular prefiere fail-closed estricto para el geoportal, basta declarar `can_persist_raw=false` en el registro: `preservar_raw` dejaría de escribir y el resultado informaría `raw_path=null` sin cambiar una línea de código.

**4.5 Lonja (contractual).** El estado declarado es `CONTRACTUAL`, no una licencia abierta: no hay incrustación de imagen (`can_embed_image=false`) ni redistribución sin contrato; la cita se hace por identidad versionada (`api/market_context.py::market_methodology` → id `lonja_baq_metodologia` + versión + `sha256`), lo que impide que una tasa viaje con `methodology_version = null`. Marco normativo declarado en `lonja_baq_metodologia.yaml`: Ley 1673 de 2013, Decreto 556 de 2014, Decreto 1420 de 1998, Resolución IGAC 620 de 2008, Resolución IGAC 1040 de 2023 mod. 746 de 2024, NTS S 01/S 03/I 01/M 01. **Observación de vigencia:** el YAML declara `vigencia_hasta: 2026-08-31` y revisión trimestral, anterior a la ventana de congelación (2026-09-29): el pack debe declarar la metodología como vencida/en revisión y no ampliar ninguna matriz con base en ella.

**4.6 COMPUTED (cálculo propio).** `SOLAR_ENGINE` y `SHADOW_FACADE_EXPOSURE` no tienen licencia de terceros: el resultado se persiste como evidencia reproducible y su PNG de sombra es render propio (`api/shadow_render.py`, Pillow). Límite declarado: si una imagen compuesta incorporara base cartográfica de tercero, deja de ser 100 % propia y `can_embed_image` debe re-evaluarse antes de publicar. Ninguna fuente `COMPUTED` ni `CONTEXTUAL_EXTERNAL` se presenta como autoridad normativa (`dictus_sources.CLASES_NORMATIVAS`).

## 5. Qué se persiste hoy de verdad (`docs/source_pack/raw/golden/`)

Inventario real: **11 archivos JSON**. No hay ningún crudo de las capas POT/equipamiento, ni de OSM, Mapillary, Google Street View o Lonja.

| Archivo | Naturaleza | Nota |
|---|---|---|
| `catastro_baq_predio.json` (69 B) | Crudo con nombre canónico de `preservar_raw` para `CATASTRO_BAQ_PREDIO` | Mínimo: atributo `destinacion_economica` |
| `pot_baq_areas_actividad.json` (122 B) | Crudo para `POT_BAQ_AREAS_ACTIVIDAD` | Fuente hoy `enabled: false` |
| `pot_baq_poligonos_uso.json` (55 B) | Crudo para `POT_BAQ_POLIGONOS_USO` | Fuente hoy `enabled: false` |
| `test_fuente.json` (21 B) | Crudo de la fuente de prueba `TEST_FUENTE` | Artefacto de contrato; NO es fuente del registro |
| `_layers_probe.json` | Descubrimiento de capas | `root_status: 403`; `layers: []` |
| `_retrieval_paths_probe.json` | Rutas alternativas (ronda 1) | Directo 403; proxies 401/522/429; Wayback sin capturas (`[]`) |
| `_retrieval_paths_probe_round2.json` | Rutas alternativas (ronda 2) | Sin respuesta utilizable en ningún camino |
| `_dns_probe_subdomains.json` | DNS de subdominios | `miciudad` y `catastro` tras Cloudflare; el resto no resuelve |
| `_origin_ip_probe.json` | Intento contra la IP de origen (`181.49.136.170`) | HTTP 404 en las rutas GIS: el origen no sirve la aplicación por ese camino |
| `_proxy_control_matrix.json` | Matriz proxy × objetivo con controles | Un objetivo raíz devolvió 200 con cuerpo ArcGIS, pero sin producir JSON utilizable persistible |
| `_service_tree.json` | Árbol `rest/services` (artefacto final) | `nodes: []`, `services: []`, `final_error: "no transport produced JSON"`: las respuestas 200 vía proxy traían marcador de bloqueo |

## 6. Riesgos y mitigaciones

| Riesgo | Mitigación implementada | Acción pendiente (fail-closed) |
|---|---|---|
| Términos del geoportal no verificados (403 Cloudflare en toda ruta) | `provider_terms_status=UNVERIFIED` por fuente; atribución obligatoria; sin incrustación; sin redistribución; estado `SOURCE_UNAVAILABLE` declarado | Obtener la licencia oficial de reutilización y registrarla como evidencia (url + fecha + sha256) antes de publicar el pack |
| Mapillary con banderas abiertas y estado `UNVERIFIED` | El manifest lo lista en `unverified_terms`; `persistence_policy` cierra la matriz ante `UNVERIFIED`; política estricta disponible | Registrar evidencia de la página de términos; hasta entonces, tratar la imagen como no incrustable |
| Google: imagen de tercero con prohibición de almacenar | Matriz cerrada; `get_image` no descarga bytes; estado objetivo `RESTRICTED` | No abrir la matriz sin documento contractual explícito |
| Metadata de imagen que contradice la licencia declarada | `license_info()` degrada a `UNVERIFIED` y cierra la matriz | Revisar licencia por `image_id` antes de incrustar |
| `can_persist_raw` omitido en el registro | Valor efectivo `True` (`consultar`) → persiste | Declarar el campo en las 35 fuentes; `tests/test_source_pack_contract.py` lo exige |
| Equipamiento oficial deshabilitado y sustituido por OSM | `separar_equipamiento` mantiene `official_equipment` y `contextual_services` separados (`mixed_authority=False`) | Verificar las capas 18/20-27 antes de presentar equipamiento como oficial |
| Metodología Lonja con vigencia vencida (2026-08-31) | Se cita por id + versión + `sha256`; `can_embed_image=false`; sin redistribución | Declarar el vencimiento y la revisión trimestral pendiente en el dictamen |
| Uso de proxies CORS de terceros para eludir el bloqueo | Las sondas se conservan como evidencia del intento; no como ruta productiva (P9) | Ninguna obtención por proxy entra al pack |
| Silencio ante término no verificado | Estados cerrados y motivos explícitos (`detail`, `observations`, `reasons`, `fail_closed`); `raw_persisted=false` cuando no se escribe | Ningún estado se omite: si falta el dato, se declara |

## 7. Fuentes externas consultadas (URLs)

- Alcaldía / geoportal: [Plan de Apertura de Datos](https://www.barranquilla.gov.co/documento/plan-de-apertura-de-datos/) · [Gaceta 1150 (Principios)](https://www.barranquilla.gov.co/documento/gaceta-no-1150/?version=1) · [Mi Ciudad — Catastro](https://catastro.barranquilla.gov.co/mi-ciudad/) · servicio consultado: `https://miciudad.barranquilla.gov.co/gis/rest/services/catastro/datosabiertos/MapServer` (HTTP 403 en esta ventana).
- OpenStreetMap: [copyright y licencia ODbL](https://www.openstreetmap.org/copyright) · [guías de atribución OSMF](https://osmfoundation.org/wiki/Licence/Attribution_Guidelines).
- Mapillary: [terms](https://www.mapillary.com/terms) · [CC BY-SA para datos abiertos](https://help.mapillary.com/hc/en-us/articles/115001770409-CC-BY-SA-license-for-open-data).
- Google: [políticas y atribuciones de Street View Static API](https://developers.google.com/maps/documentation/streetview/policies) · [Google Maps Platform Terms](https://cloud.google.com/maps-platform/terms).

Estas URLs **no** sustituyen evidencia: para pasar de `DECLARED`/`UNVERIFIED` a `VERIFIED` hay que registrar `evidence_url` + `retrieved_at` + `sha256` del contenido descargado mediante el mecanismo de evidencia de términos; sin esos tres campos la verificación no se acepta y el estado permanece `UNVERIFIED` (fail-closed). Mientras un término siga sin verificar, la regla es una sola: **se declara, no se silencia**.

---

# 8. Bloque v2 (2026-09-29) — licencia de IMÁGENES ≠ términos de API

**Pieza:** `api/source_licenses_v2.py` (`source-licenses-v2/2.0.0`) · **Evidencia de imágenes:**
`docs/source_pack/IMAGERY_LICENSES.md` · **Anexo v2 del registro de evidencia:**
`docs/source_pack/LICENSES_EVIDENCE.md` (§ ANEXO v2). Esta sección **no** reescribe nada de arriba: el pack v1 y
`api/source_licenses.py` siguen siendo la declaración auditada de las **35** fuentes.

## 8.1 Dos columnas, nunca una

| campo v2 | qué declara | qué gobierna |
|---|---|---|
| `IMAGERY_LICENSE_STATUS` | licencia de las **IMÁGENES** y sus obligaciones | DERECHOS: `can_persist` · `can_modify` · `can_embed` · `share_alike` |
| `API_TERMS_STATUS` | términos de la **API/plataforma** de acceso | ADQUISICIÓN: `client_id` · interfaces publicadas · sin scraping · throttling |

## 8.2 Estado v2 de las fuentes de imágenes

| `source_id` | `IMAGERY_LICENSE_STATUS` | `API_TERMS_STATUS` | `can_persist` / `can_modify` / `can_embed` | `product_role` | bloquea el pack |
|---|---|---|---|---|---|
| `MAPILLARY` | **`VERIFIED`** (CC BY-SA 4.0 con atribución visible con enlace + share-alike, evidenciado en los Términos de Uso vigentes del proveedor) | **`DECLARED`** (§11/§12 del documento general; **no** hay documento de términos de API dedicado y accesible) | `True` / `True` / `True` (con condiciones) | `CONTEXT` | no |
| `GOOGLE_STREET_VIEW` | **`RESTRICTED`** | **`RESTRICTED`** | `False` / `False` / `False` | **`OPTIONAL_ENRICHMENT`** | **no** |
| `OSM_OVERPASS` | `NOT_APPLICABLE` (datos, no imágenes) | **`VERIFIED`** (ODbL 1.0 impresa en el copyright de OSM) | `True` / `True` / `False` | `CONTEXT` | no |

Complemento a §4.2 de este documento (Mapillary): la v1 dejaba el estado en `DECLARED` porque la página que fijaba la
**versión** respondía 403. La v2 **registra evidencia accesible nueva** — los Términos de Uso vigentes (200, hasheados,
«Effective date: February 15, 2024») **enlazan** la licencia de las imágenes al deed canónico
`creativecommons.org/licenses/by-sa/4.0/` e **imprimen** el requisito de atribución para descargar y servir imágenes— y
por eso `IMAGERY_LICENSE_STATUS` pasa a `VERIFIED`, **con alcance declarado** y con lo que sigue faltando escrito
(`what_is_missing_for_verified` / `residual_gaps`): que la versión se imprima como texto, la confirmación por conjunto
de datos y la condición de uso comercial (§12). La columna de API se queda en `DECLARED`. La lectura conservadora de la
v1 **no se borra**: sigue vigente y es la que gobierna `persistence_policy` para cualquier consumidor de ese módulo.

## 8.3 Condiciones que NO se asumen

- **Por imagen**: `permitir_persistencia_imagen()` sólo persiste si la metadata declara CC BY-SA; licencia distinta,
  NC o **ausente** ⇒ esa imagen se cierra con motivo (la ausencia **no** equivale a permiso).
- **Atribución**: `© Mapillary contributors (CC BY-SA 4.0)` con enlace a Mapillary (y logo cuando el medio lo permita).
- **Google**: prohibición explícita consultada (pre-descarga, indexado, almacenamiento, caché, derivados) ⇒ matriz
  cerrada de forma permanente mientras el hash sea el vigente; `OPTIONAL_ENRICHMENT` **no** bloquea el Source Pack.

## 8.4 Qué **no** es evidencia (regla nueva de la v2)

`HTTP 200` con cuerpo de «página no encontrada» (`/terms/api`, `/terms/data`) es **`SOFT_404`**, no términos
consultados; una página accesible sin marcadores de licencia (`/open-data`, `/datasets`) no sostiene ningún `VERIFIED`;
una fuente **de terceros** (wiki de OSM) corrobora pero no verifica. Todo queda registrado con URL, fecha, HTTP, bytes
y `sha256` en `docs/source_pack/IMAGERY_LICENSES.md`.

## 8.5 Lonja: **no es una fuente** (corrige la lectura de §3.5/§4.5)

Decisión de producto de esta ronda: la Lonja **no** aporta datos a DICTUS, **no** es `source_id`, `authority_class`
ni proveedor de mercado, y **no** tiene contrato de datos, dataset ni ingesta en esta entrega. Se representa como
`institutional_partner` / `distribution_partner` / `stakeholder` en
`docs/source_pack/INSTITUTIONAL_PARTNERS.md`, y su ausencia **no** bloquea `CONTRACT_FROZEN` ni `OPERATIONAL_READY`.
La fila `LONJA_MARKET_BAQ` de §3.5 y el apartado §4.5 describen el pack **v1** (que sí la declara `CONTRACTUAL` /
`CORE_MARKET`): la divergencia se declara en `INSTITUTIONAL_PARTNERS.md` §3 y su retirada del registro v1 es acción
pendiente del titular del pack, no de esta entrega.

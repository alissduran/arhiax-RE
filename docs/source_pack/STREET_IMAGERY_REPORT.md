# STREET IMAGERY — REPORTE DE FUENTE (Barranquilla Source Pack v1.0)

**Predio de referencia (Golden):** 040-646406 — NUPRE `AFT0005BOHA` — número predial `080010103000010040001908040002`
**Dirección oficial:** TV 43 # 100 - 50 CONJUNTO RESIDENCIAL NAPOLI APARTAMENTOS ETAPA 3 APARTAMENTO 430 TORRE 8 — barrio Miramar
**Coordenada oficial:** lat `11.005378`, lon `-74.8386199`
**Módulo auditado:** `api/street_imagery.py` (1511 líneas) · contrato de vocabularios: `api/dictus_sources.py` (§19/§27/§28)
**Consumidor aguas abajo:** `api/facade_solar.py` (carga `street_imagery` como módulo hermano, línea 81)
**Especificación ejecutable:** `tests/test_source_pack_imagery_solar.py`
**Naturaleza de este documento:** auditoría de la implementación REAL. Nada se infiere de fuentes externas; lo no comprobado se rotula «no verificado en esta corrida».

---

## 1. Objetivo y contrato

Obtener una **vista callejera orientada hacia el inmueble** con procedencia completa, **sin ninguna selección humana** (`human_input_required = False` en todo resultado; `METODO_SELECCION = "AUTOMATICA_AZIMUT_CAMARA_A_INMUEBLE_SIN_INTERVENCION_HUMANA"`).

| Regla dura | Implementación verificable |
|---|---|
| Estados CERRADOS por consulta | `AVAILABLE \| NO_MATCH \| SOURCE_UNAVAILABLE \| NOT_SUPPORTED \| QUERY_FAILED` (`ESTADOS`, línea 103). Estado desconocido → `QUERY_FAILED` (`_resultado`, línea 676) |
| Una ausencia NUNCA es `NO_MATCH` | `ESTADOS_SIN_DATO = (SOURCE_UNAVAILABLE, NOT_SUPPORTED, QUERY_FAILED)` (línea 105). `NO_MATCH` sólo cuando el proveedor contestó y no había imagen en el punto (líneas 893-895) |
| Fail-closed de licencia | `PERSISTENCIA_POR_DEFECTO` cerrada (línea 600); sin evidencia VERIFICADA no se abre |
| Cero intervención humana | `human_input_required: False` (líneas 359, 664, 940); `consultar_vista_automatica` no acepta elección de imagen |
| Sin credenciales → no se toca la red | `credentials_status()["status"] == "MISSING"` corta antes del transporte (líneas 871-876) y registra `request_made: False` |
| Ausencia declarada, no silenciosa | Proveedor centinela `NoImageProvider` (`NO_IMAGE_AVAILABLE`) existe sólo para que la ausencia sea un ESTADO explícito |

**Vocabulario de texto:** la frase «fachada principal» está PROHIBIDA; `sanear_texto()` la sustituye por `TEXTO_VISTA_AUTORIZADO = "vista callejera orientada hacia el inmueble"` (líneas 130-131, 279-286).

## 2. Proveedores registrados (tabla de contrato)

Registro: `_CLASES` (línea 1322) + fábrica `obtener_proveedor()`; orden de intento `ORDEN_PROVEEDORES = (MAPILLARY, GOOGLE_STREET_VIEW)` y luego el centinela (líneas 1328, 1369-1370).

| id (`PROVIDER`) | `SOURCE_ID` | Clase | Endpoint / base URL real | Credencial requerida (nombre EXACTO) | Licencia / términos declarados | ¿Persistir el crudo? | `can_embed_in_pdf` | Estado real HOY |
|---|---|---|---|---|---|---|---|---|
| `MAPILLARY` | `IMAGERY_MAPILLARY` | `MapillaryProvider` | `https://graph.mapillary.com/images` (metadata/bbox, `limit=50`) · imagen: `thumb_1024_url` o `https://graph.mapillary.com/images/{id}?access_token=…&fields=thumb_1024_url` | `ARHIAX_MAPILLARY_TOKEN`, `MAPILLARY_TOKEN`, `MAPILLARY_ACCESS_TOKEN` (se usa la primera presente, en ese orden) | CC BY-SA 4.0 · `LICENCIA_URL = TERMS_URL = https://www.mapillary.com/terms` · estado por defecto `TERMS_DECLARED` · share-alike `True` · atribución obligatoria `"© Mapillary contributors (CC BY-SA 4.0)"` | Sí, por licencia declarada (`can_persist=True`, `FLUJO_PERSISTENCIA="COPIAR_BAJO_CC_BY_SA_4_0_CON_ATRIBUCION"`), con atribución y share-alike | `True` | `SOURCE_UNAVAILABLE` — credencial `MISSING`, `request_made=False` |
| `GOOGLE_STREET_VIEW` | `IMAGERY_GOOGLE_STREET_VIEW` | `GoogleStreetViewProvider` | metadata: `https://maps.googleapis.com/maps/api/streetview/metadata` · imagen: `https://maps.googleapis.com/maps/api/streetview` (`size=640x640` + `heading/pitch/fov`) | `ARHIAX_GOOGLE_MAPS_API_KEY`, `GOOGLE_MAPS_API_KEY`, `GOOGLE_STREETVIEW_API_KEY` (en ese orden) | Sin licencia declarada (`LICENCIA_DECLARADA = ""`) · `TERMS_URL = https://cloud.google.com/maps-platform/terms` · estado por defecto **`UNVERIFIED`** | **No** (`can_persist=False`) | **`False`** | `SOURCE_UNAVAILABLE` — credencial `MISSING`, `request_made=False` |
| `NO_IMAGE_AVAILABLE` | `IMAGERY_NONE` | `NoImageProvider` | `""` (no consulta ninguna fuente) | No requiere (`REQUIERE_CREDENCIAL = False`) | `TERMS_NOT_APPLICABLE` | No (no hay bytes) | `False` | `NOT_SUPPORTED` — ausencia declarada explícita |

Nota de vocabulario: `NO_IMAGE_AVAILABLE` es a la vez **id de proveedor centinela** y **valor del nivel de fachada** (`NIVELES_FACHADA`); es el mismo literal `"NO_IMAGE_AVAILABLE"` en ambos usos.

## 3. Selección automática de fachada (algoritmo determinista)

**Función determinista:** `seleccionar_vista_automatica()` (`api/street_imagery.py`, línea 332). Se invoca desde `StreetImageryProvider.get_best_view()` (línea 928). Auxiliares deterministas: `normalizar_candidato_crudo()`, `bearing_geodesico()`, `distancia_metros()` (haversine), `diferencia_angular()`, `centroide_huella()`.

| # | Paso | Regla exacta en el código |
|---|---|---|
| 1 | Normalizar candidatos | `normalizar_candidato_crudo()`: exige coordenada de cámara; sin ella el candidato se descarta. `candidate_count` = candidatos válidos (líneas 381-386) |
| 2 | Sin candidatos | Devuelve `facade_view_level = confidence = NO_IMAGE_AVAILABLE` con motivo explícito; no se inventa nada (líneas 387-390) |
| 3 | Punto objetivo | Centroide de la huella del edificio si existe (`target_source = "CENTROIDE_HUELLA_EDIFICIO"`); si no, coordenada oficial (`"COORDENADA_OFICIAL"`) (líneas 392-400) |
| 4 | Sin geometría del inmueble | `facade_view_level = confidence = FACADE_VIEW_CONTEXTUAL` y NO se afirma orientación (líneas 402-408) |
| 5 | Azimut y distancia por candidato | `bearing_camera_to_building_deg` = `bearing_geodesico(cámara → objetivo)`; `distance_m` = `distancia_metros()` (líneas 415-416) |
| 6 | Error de alineación | Panorama (`is_pano`) → `err = 0.0` (`PANORAMA_HEADING_SOLICITADO_HACIA_INMUEBLE`); sin compás → `err = None`; con compás → `diferencia_angular(compass_angle, azimut)` y `heading_source` verificado sólo si `err ≤ 25.0°` (líneas 417-427) |
| 7 | Descarte por orientación | Se descarta toda vista en perspectiva con `err > ERROR_ALINEACION_MAXIMO_DEG = 60.0°`: afirmar orientación que la cámara no tenía está prohibido (líneas 442-446) |
| 8 | Sin vistas utilizables | `FACADE_VIEW_CONTEXTUAL`; el elegido es `min` por `(distance_m, image_id)` con `heading_source = "SIN_VISTA_ORIENTADA_AL_INMUEBLE"` (líneas 458-467) |
| 9 | Desempate determinista | `min` con clave `(0 si err no es None, err, distance_m, image_id)` — el **orden de llegada de los candidatos no decide** (líneas 451-469; probado en `test_seleccion_determinista_independiente_del_orden`) |
| 10 | `heading` | Compás verificado (`AZIMUT_COMPAS_CAMARA_VERIFICADO`) → `compass_angle`; en cualquier otro caso → azimut cámara→inmueble (líneas 472-476) |
| 11 | `pitch` | Con altura física declarada: `atan(((altura/2) − 2.5 m) / distancia)` → `CALCULADO_CON_ALTURA_FISICA_DECLARADA`; sin altura: `0.0` → `HORIZONTAL_POR_DEFECTO_SIN_ALTURA_FISICA` (líneas 478-484) |
| 12 | `fov` | Del proveedor si lo trae; si no `DEFAULT_FOV_DEG = 80.0` → `DEFECTO_DECLARADO_SIN_MODELO_DE_CAMARA` (líneas 485-488) |
| 13 | Nivel de confianza | Ver tabla siguiente (líneas 490-499) |

| Nivel (`NIVELES_FACHADA`, idéntico en `dictus_sources.py` líneas 78-83 y `street_imagery.py` líneas 114-118) | Condición exacta |
|---|---|
| `FACADE_VIEW_VERIFIED` | `err ≤ 25.0°` **y** `distance_m ≤ 75.0` **y** existe `capture_date` |
| `FACADE_VIEW_PROBABLE` | (`err` es `None` **o** `err ≤ 45.0°`) **y** `distance_m ≤ 200.0` |
| `FACADE_VIEW_CONTEXTUAL` | Ninguna vista orientada al inmueble (paso 8) o geometría del inmueble ausente (paso 4) |
| `NO_IMAGE_AVAILABLE` | Sin candidatos del proveedor (paso 2) o ausencia declarada del centinela |

Parámetros geométricos declarados (no ajustados a ojo): `DEFAULT_FOV_DEG 80.0`, `ALTURA_CAMARA_DEFECTO_M 2.5`, `TOLERANCIA_ALINEACION_DEG 25.0`, `TOLERANCIA_ALINEACION_AMPLIA_DEG 45.0`, `ERROR_ALINEACION_MAXIMO_DEG 60.0`, `DISTANCIA_VERIFICADA_M 75.0`, `DISTANCIA_PROBABLE_M 200.0` (líneas 136-142).

## 4. Fail-closed de Google por términos no verificados

| Aspecto | Comportamiento REAL en el código |
|---|---|
| Cuándo `terms_status = "UNVERIFIED"` | Valor por defecto del proveedor: `GoogleStreetViewProvider.TERMS_STATUS_POR_DEFECTO = TERMS_UNVERIFIED` (línea 1175). Se resuelve en `_estado_terminos()` (líneas 754-759) y queda expuesto como `provider_terms_status` de toda procedencia (línea 660) |
| Qué devuelve | `persistence_policy()` cierra la matriz COMPLETA: `can_persist=False`, `can_download_bytes=False`, `can_embed_in_pdf=False`, `can_modify=False`, `can_redistribute=False`, `storage_flow="NINGUNO"`, `fail_closed=True` (líneas 839-864; probado en `test_google_politica_cerrada_por_defecto`) |
| Por qué es obligatorio | Una imagen de Google no puede asumirse descargable, guardable, modificable ni embebible en el PDF sin evidencia de términos VERIFICADA. La metadata de la imagen **sólo puede restringir, nunca ampliar** el permiso (líneas 811-818; `test_metadata_de_la_imagen_no_amplia_el_permiso`) |
| Efecto sobre bytes | `get_image()` retorna `NOT_SUPPORTED` con `downloaded=False`, `bytes_written=0`, `path=None`, `content_bytes=None` y **no intenta ninguna descarga** (`download_attempted=False`) |
| Qué NO bloquea el estado `UNVERIFIED` | `get_metadata()` y `get_best_view()` **no** evalúan `_estado_terminos()`: la consulta de metadata sólo se corta por credencial ausente. Con una API key presente, la consulta de metadata a Google SÍ se realizaría y podría seleccionarse una vista; lo que permanece cerrado es la descarga/persistencia/incrustación |
| Vía de apertura existente | `registrar_evidencia_terminos()` exige `evidence_url` + `retrieved_at` + `sha256` y `terms_status` del vocabulario; sólo `TERMS_VERIFIED` con `license_allows_persist=True` abre la matriz (líneas 761-773, 832-838). No ejercitada en esta corrida |
| Endurecimiento adicional | `ARHIAX_IMAGERY_STRICT_TERMS` (o `politica_estricta=True`) cierra la matriz para **cualquier** estado distinto de `VERIFIED`, incluida la licencia DECLARED de Mapillary (líneas 639-642, 843-845; `test_politica_estricta_cierra_tambien_la_licencia_declarada`) |

**Limitación estructural verificable:** `GoogleStreetViewProvider.LICENCIA_DECLARADA = ""` y `verificar_terminos()` sólo marca `VERIFIED` si el documento descargado contiene literalmente la licencia declarada (líneas 1475-1482). Con licencia declarada vacía, la auto-verificación de Google **nunca** puede alcanzar `VERIFIED`: el fail-closed de Google es de facto permanente salvo evidencia registrada por vía externa.

## 5. Estado real de credenciales (hecho verificado)

Sondas ejecutadas por el agente en esta sesión sobre el entorno de la corrida:

| Variable de entorno | ¿La lee `api/street_imagery.py`? | Estado |
|---|---|---|
| `ARHIAX_MAPILLARY_TOKEN` | Sí (1.ª preferencia Mapillary) | AUSENTE |
| `MAPILLARY_TOKEN` | Sí | AUSENTE |
| `MAPILLARY_ACCESS_TOKEN` | Sí | AUSENTE |
| `MAPILLARY_CLIENT_ID` | No (no figura en `VARIABLES_CREDENCIAL`) | AUSENTE |
| `ARHIAX_GOOGLE_MAPS_API_KEY` | Sí (1.ª preferencia Google) | AUSENTE |
| `GOOGLE_MAPS_API_KEY` | Sí | AUSENTE |
| `GOOGLE_API_KEY` | No | AUSENTE |
| `GOOGLE_STREETVIEW_API_KEY` | Sí | AUSENTE |
| `STREET_VIEW_API_KEY` | No | AUSENTE |
| `ARHIAX_IMAGERY_STRICT_TERMS` | Sí (endurecimiento de términos) | AUSENTE |

Archivos `.env` buscados en el repositorio (`arhiax-RE/.env`, `arhiax-RE/api/.env`, `arhiax-RE/public/.env`): **ninguno existe** (comprobado también con `glob "arhiax-RE/**/.env*"`: sin coincidencias).

**Consecuencia operativa obligatoria (estado declarado HOY para el predio Golden 040-646406):**

| Campo devuelto | Valor esperado |
|---|---|
| `status` consolidado (`consultar_vista_automatica`) | `SOURCE_UNAVAILABLE` |
| `statuses` por proveedor | `MAPILLARY: SOURCE_UNAVAILABLE`, `GOOGLE_STREET_VIEW: SOURCE_UNAVAILABLE`, `NO_IMAGE_AVAILABLE: NOT_SUPPORTED` |
| `attempts[*].credentials.status` | `"MISSING"` con `env_var = VARIABLES_CREDENCIAL[0]` (`ARHIAX_MAPILLARY_TOKEN` / `ARHIAX_GOOGLE_MAPS_API_KEY`) |
| `attempts[*].provenance.request_made` | `False` — la red NO se toca |
| `detail` | `MOTIVO_SIN_CREDENCIALES` (líneas 144-145) |
| `view` | `None` |
| `facade_view_level` | `NO_IMAGE_AVAILABLE` |
| `provider` | `None` (ningún proveedor contestó `AVAILABLE`) |

La ausencia de credencial/cobertura se declara como estado cerrado; **nunca** como fallo silencioso ni como imagen inventada. No existe evidencia cruda de imagery en `docs/source_pack/raw/golden/` (inspección de las 9 capturas presentes: `catastro_baq_predio.json`, `pot_baq_areas_actividad.json`, `pot_baq_poligonos_uso.json`, `test_fuente.json`, `_service_tree.json`, `_retrieval_paths_probe*.json`, `_layers_probe.json`, `_dns_probe_subdomains.json` — ninguna es de street imagery), y `grep "mapillary|street_?view|IMAGERY_"` sobre `docs/source_pack/` no produce coincidencias: **no verificado en esta corrida** ningún crudo de imagery.

## 6. Qué NO bloquea: jerarquía de degradación

| Nivel | Situación | Efecto |
|---|---|---|
| 1 | Vista disponible y persistible (Mapillary con token y licencia coincidente) | `AVAILABLE`, nivel `FACADE_VIEW_VERIFIED/PROBABLE/CONTEXTUAL`, crudo e imagen persistibles con atribución |
| 2 | Proveedor contesta y no hay imagen en el punto | `NO_MATCH` (ausencia real, jamás confundida con caída) |
| 3 | Sin credencial / cuota agotada / 401-403-429-5xx | `SOURCE_UNAVAILABLE` (`estado_por_http()`, líneas 540-551) |
| 4 | Proveedor centinela: no existe fuente de imagen | `NOT_SUPPORTED` |
| 5 | Fallo de consulta o estado fuera del vocabulario | `QUERY_FAILED` |

En todos los niveles 2-5: `facade_view_level = NO_IMAGE_AVAILABLE`, `view = None`, **`blocks_dictus = False`**, `dictus_gate_impact = "NONE"` y `human_input_required = False` (líneas 695, 1412-1418). Agregación fail-closed: `estado_consolidado()` prefiere `AVAILABLE → QUERY_FAILED → SOURCE_UNAVAILABLE → NOT_SUPPORTED` y sólo cae en `NO_MATCH` si todos coinciden (líneas 1340-1355); el centinela no vota (líneas 1401-1404). **La ausencia de imagen NO bloquea el resto del Source Pack.** El consumidor `api/facade_solar.py` degrada en consecuencia: sin vista callejera no promueve la exposición solar (`test_vista_callejera_ausente_no_promueve_la_exposicion`).

## 7. Limitaciones conocidas

1. **Panoramas sin verificación de compás:** un candidato `is_pano=True` recibe `alignment_error_deg = 0.0` (líneas 418-420). Un panorama dentro de 75 m y con fecha alcanza `FACADE_VIEW_VERIFIED` aunque la dirección real de captura nunca se verificó; el `heading` se *solicita* hacia el inmueble, no se comprueba.
2. **Google no expone compás ni licencia de reuso** en la Metadata API (`compass_angle=None`, `license=None`, líneas 1225-1231): la verificación de orientación por compás es imposible para ese proveedor.
3. **Sin altura física declarada no hay `pitch` real**: se usa `0.0` y se declara `HORIZONTAL_POR_DEFECTO_SIN_ALTURA_FISICA`. `POT.altura_max` es altura NORMATIVA y no puede usarse como física (`dictus_sources.altura_fisica()`, líneas 334-361).
4. **El `fov` por defecto (80°) no es un modelo de cámara**: queda rotulado como defecto declarado.
5. **Discrepancia de clave de licencia del crudo:** `street_imagery` decide con `can_persist`/`can_embed_in_pdf`, mientras `dictus_sources.preservar_raw()` consulta `can_persist_raw` (línea 151). Son claves distintas: un llamador que pase la política de `street_imagery` a `preservar_raw` no activa esa comprobación.
6. **Nombres de variables probados ≠ nombres leídos:** la sonda `scripts/_sp_probe_context_sources.py` (líneas 56-58) comprueba `MAPILLARY_CLIENT_ID`, `GOOGLE_API_KEY` y `STREET_VIEW_API_KEY`, que el módulo NO lee, y no comprueba `ARHIAX_MAPILLARY_TOKEN` ni `ARHIAX_GOOGLE_MAPS_API_KEY`, que son su primera preferencia (verificado aparte en esta corrida).
7. **Sin crudo de imagery persistido** en `docs/source_pack/raw/golden/` y sin entrada de registro para `IMAGERY_MAPILLARY` / `IMAGERY_GOOGLE_STREET_VIEW` en `docs/source_pack/` (no existe hoy `barranquilla_sources_v1.json` en el árbol de `docs/source_pack/`; donde se verificaría: `dictus_sources.RUTA_REGISTRO`).

## 8. Re-verificación (comandos concretos)

Comandos **propuestos y no ejecutados en esta corrida** (no se ejecutó Python para no generar artefactos fuera del alcance de esta tarea). Ejecutar desde `arhiax-RE`:

```powershell
# 1) Credenciales que el módulo realmente lee (debe imprimir AUSENTE en todas hoy)
foreach ($n in @("ARHIAX_MAPILLARY_TOKEN","MAPILLARY_TOKEN","MAPILLARY_ACCESS_TOKEN",
                 "ARHIAX_GOOGLE_MAPS_API_KEY","GOOGLE_MAPS_API_KEY","GOOGLE_STREETVIEW_API_KEY",
                 "ARHIAX_IMAGERY_STRICT_TERMS")) {
  "{0,-32} {1}" -f $n, $([string]::IsNullOrEmpty([Environment]::GetEnvironmentVariable($n)) ? "AUSENTE" : "PRESENTE") }

# 2) Estado declarado para el predio Golden (no debe tocar la red sin credenciales)
python -c "import sys,json; sys.path.insert(0,'api'); import street_imagery as si; \
a=si.consultar_vista_automatica(11.005378,-74.8386199,None,coordenada_oficial=(11.005378,-74.8386199)); \
print(json.dumps({'status':a['status'],'facade_view_level':a['facade_view_level'],'statuses':a['statuses'], \
'creds':{k:v['credentials'] for k,v in a['attempts'].items()},'blocks_dictus':a['blocks_dictus']},ensure_ascii=False,indent=1))"

# 3) Coherencia de vocabularios con el Source Pack (§19/§27) y matriz de persistencia
python -c "import sys,json; sys.path.insert(0,'api'); import street_imagery as si; \
print(si.verificar_vocabulario()); print(json.dumps(si.persistencias_permitidas(),ensure_ascii=False,indent=1))"

# 4) Suite de la especificación ejecutable de imagery + solar
python -m pytest tests/test_source_pack_imagery_solar.py -q
python -m pytest tests/test_source_pack_imagery_solar.py -q -k "sin_credenciales or google_politica_cerrada or centinela"
```

Ningún resultado de estos comandos se ha incorporado al documento: son el procedimiento de re-verificación, no evidencia de esta corrida.

---

## 9. Discrepancias entre la implementación real y las expectativas del encargo

| Expectativa | Realidad en el código | Impacto |
|---|---|---|
| Ids de proveedor `MAPILLARY` / `GOOGLE_STREET_VIEW` | **Coinciden exactamente** (`MAPILLARY = "MAPILLARY"`, `GOOGLE_STREET_VIEW = "GOOGLE_STREET_VIEW"`, línea 108-109) | Ninguno; existen además `NO_IMAGE_AVAILABLE` y los `SOURCE_ID` `IMAGERY_MAPILLARY` / `IMAGERY_GOOGLE_STREET_VIEW` / `IMAGERY_NONE` |
| «No se consulta a Google cuando los términos no están verificados» | El estado `UNVERIFIED` **no** impide `get_metadata`/`get_best_view`; sólo cierra descarga, persistencia e incrustación (`get_image` → `NOT_SUPPORTED`) | Importante: hoy no se consulta a Google **sólo** por la credencial ausente, no por los términos. Con una API key, la metadata sí se consultaría mientras la licencia de reuso seguiría cerrada |
| Función determinista de selección de fachada | Nombre exacto: **`seleccionar_vista_automatica()`** (no existe `seleccionar_fachada` ni similar) | El agregado es `consultar_vista_automatica()` |
| Credenciales probadas por sonda | `MAPILLARY_CLIENT_ID`, `GOOGLE_API_KEY`, `STREET_VIEW_API_KEY` no se leen; faltaba probar `ARHIAX_MAPILLARY_TOKEN` y `ARHIAX_GOOGLE_MAPS_API_KEY` | Cubierto en esta corrida: las 9 variables de credencial y las 2 primarias `ARHIAX_*` están AUSENTES |
| `terms_status` = `"UNVERIFIED"` | Cierto **para Google únicamente**; Mapillary declara `TERMS_DECLARED` (CC BY-SA 4.0) y el centinela `TERMS_NOT_APPLICABLE` | No generalizar el `UNVERIFIED` a todos los proveedores |
| Núcleo de licencia «crudo persistible» | La clave del módulo es `can_persist`/`can_embed_in_pdf`; `dictus_sources.preservar_raw` usa `can_persist_raw` | Ver limitación 5 |

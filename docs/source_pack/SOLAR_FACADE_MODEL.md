# MODELO SOLAR DE FACHADA Y SOMBRAS — REPORTE DE MÓDULO (Barranquilla Source Pack v1.0)

**Predio de referencia (Golden):** 040-646406 — barrio Miramar, estrato 4 · coordenada oficial lat `11.005378`, lon `-74.8386199`
**Módulos auditados:** `solar_engine.py` (raíz, 123 líneas, sha256 `177BED7CDA2E0AC5172A6D60488F2DE409360198DFD3AC887E2F00CEBFFE75C0`) · `api/facade_solar.py` (640 líneas) · `api/shadow_render.py` (270 líneas) · contrato de vocabularios `api/dictus_sources.py` (§22/§25) · consumidor del asoleamiento `api/pdf_compiler.py` + `api/dictus_decision.py`
**Especificación ejecutable:** `tests/test_source_pack_imagery_solar.py` (49 pruebas, offline)
**Naturaleza de este documento:** auditoría de la implementación REAL, con los resultados que SÍ se ejecutaron en esta corrida marcados como tales. Nada se infiere de fuentes externas; lo no comprobado se rotula «no verificado en esta corrida».

---

## 1 · Qué es el motor solar y por qué es `COMPUTED`

`solar_engine.py` es un cálculo **determinista del cielo**, no una fuente oficial: `api/facade_solar.py` lo declara `ES_MEDICION_FISICA = False` (línea 123), `TIPO_ANALISIS = "ANALISIS_SOLAR_AUTOMATIZADO_FACHADA_VISIBLE"` (línea 122) y la etiqueta obligatoria `ETIQUETA_ANALISIS_SOLAR = "ANÁLISIS SOLAR AUTOMATIZADO DE LA FACHADA VISIBLE"` (línea 121, idéntica en `dictus_sources.py` línea 93). **No es autoridad normativa**: no fija altura, no fija tratamiento, no fija POT; sólo ubica el sol y la geometría disponible.

| Entrada mínima real | Obligatoria | Valor por defecto en el código | Evidencia |
|---|---|---|---|
| Coordenada `lat`, `lon` | Sí | — | `solar_engine.get_solar_position(lat, lon, dt, tz_offset=-5)` (líneas 4-14) |
| Fecha (`fecha` ISO o `dt` datetime) | Sí | — | `_resolver_solar` (líneas 295-340) |
| Hora | **No** | `12.0` (`h = _num(hora, 12.0) or 12.0`, línea 323) | corrida verificada: `fecha="2026-09-28"` sin hora → `fecha_hora = 2026-09-28T12:00:00` |
| Huso horario | No | `tz_offset = -5.0` (COT) | línea 296, línea 340 |
| Intervención humana | **No existe** | `human_input_required: False` (líneas 455 y 590) | ninguna firma acepta selección humana |

**Verificado en esta corrida** (ejecutado): `get_solar_position(11.005378, -74.8386199, 2026-09-28 09:00 | 12:00 | 15:00)` → `(104.05, 45.89)`, `(191.32, 77.05)`, `(257.85, 41.04)`. Son **exactamente** los valores persistidos en `docs/forensics/040-646406/dictus_2b/DICTUS_RUN_STATE_040-646406.json`, bloque `solar_state.momentos` (líneas 989-1017). El motor funciona sólo con coordenada + fecha: **sí** (ver §7).

## 2 · Cálculo de azimut/altura solar y qué se necesita para la sombra

`get_solar_position()` (líneas 4-79) reproduce el algoritmo NOAA simplificado: día del año (línea 16) → `gamma` fraccional (línea 22) → ecuación del tiempo `eqt` (líneas 25-29) → declinación `delta` (líneas 32-38) → `time_offset = eqt + 4.0*lon - 60.0*tz_offset` (línea 43) → tiempo solar verdadero (línea 46) → ángulo horario `ha` (línea 49) → `cos_zenith` (líneas 55-59) → `elevation = 90 - grados(zenith)` (línea 61) → azimut con ajuste de cuadrante según `ha > 0` (líneas 65-77). Devuelve `(azimut, elevación)` redondeados a 2 decimales.

`analyze_facade_exposure(solar_az, solar_el, facade_az, obstructions)` (líneas 81-123) es el clasificador **del compilador de PDF** (vocabulario propio: `"Sol Directo" / "Sombra (Obstrucción)" / "Sombra (Orientación)" / "Noche"`), distinto del vocabulario §22 de §3.

| Para obtener… | Se necesita | Fórmula / regla real |
|---|---|---|
| Azimut y elevación solar | coordenada + fecha (hora por defecto 12:00) | `get_solar_position` |
| Sombra proyectada (largo) | elevación solar + **altura física** | `L = altura_m / tan(radians(el))` — `api/shadow_render.py` línea 127; `api/facade_solar.py` línea 499 |
| Huella de la sombra | huella del edificio + azimut del sol | desplazamiento a `az + 180°` y *convex hull* de huella y huella desplazada (`_sombra_poligono`, líneas 123-150) |
| Corte por sol rasante | — | `el <= 2.0` → sin polígono (línea 125); `L > 5000` m → sin polígono (líneas 128-129); en `facade_solar` el umbral es `ELEVACION_MINIMA_SOMBRA_M = 2.0` (línea 131) |
| Huella y altura del edificio | capa oficial en vivo | capa **310 (Construcción)** de `https://miciudad.barranquilla.gov.co/gis/rest/services/catastro/datosabiertos/MapServer` (`_obtener_construccion`, líneas 63-120); altura = `altura_total_construccion`, y si falta `pisos × 3.0` o `9.0` **declarado como estimación** (líneas 105-110) |

## 3 · `FACADE_SOLAR_EXPOSURE`: los 4 estados y su criterio exacto

> **Nombre del encargo vs. código:** el literal `FACADE_SOLAR_EXPOSURE` **no existe** en el repositorio (búsqueda de `FACADE_SOLAR` en todo el árbol: 0 coincidencias). Los símbolos reales son la tupla `ESTADOS_EXPOSICION` (`dictus_sources.py` líneas 90-91; `facade_solar.py` líneas 118-119), la clase `FacadeSolarExposure` (línea 357), la función `analizar_exposicion_fachada` (líneas 595-611) y el método `FacadeSolarExposure.exposicion` (líneas 408-515), con alias `analyze` (línea 518).

Ángulo relativo `delta = angulo_relativo_sol_fachada(solar_az, facade_az)` (línea 242) → `street_imagery.diferencia_angular` (líneas 183-186), diferencia mínima en `[0, 180]`.

| Estado exacto | Condición en el código (orden estricto de evaluación) | `motivo` real emitido |
|---|---|---|
| `FACADE_SHADED_OR_REARWARD` | (a) `solar_el <= 0` → línea 475; o (b) obstrucción declarada que cubre el sol → línea 478; o (c) `delta > 90.0°` → línea 490 | «El sol está bajo el horizonte a la fecha/hora analizada.» / «Obstrucción declarada en el sector 150°-210° hasta 70° de elevación.» / «El sol queda por detrás de la vista identificada (ángulo relativo 160.0° > 90.0°).» |
| `DIRECT_EXPOSURE_LIKELY` | `delta <= UMBRAL_INCIDENCIA_DIRECTA_DEG (45.0)` **y** `solar_el >= ELEVACION_MINIMA_DIRECTA_DEG (5.0)` → línea 481 | «El sol incide sobre la vista identificada con un ángulo relativo de 5.95° (≤ 45.0°).» |
| `OBLIQUE_EXPOSURE` | `delta <= UMBRAL_INCIDENCIA_OBLICUA_DEG (90.0)` → línea 485. Incluye elevación rasante (`0 < el < 5°`), que **jamás** asciende a directa | «Incidencia oblicua: el ángulo relativo sol-fachada es 70.0°.» / «…es 0.0° con elevación solar rasante.» |
| `INSUFFICIENT_GEOMETRY` | `faltantes` no vacío → líneas 459-467 (estado por defecto declarado en la línea 436) | «Geometría insuficiente (AZIMUT_FACHADA_VISIBLE): no se emite un estado de exposición. La falta de geometría NUNCA se promueve a DIRECT_EXPOSURE_LIKELY.» |

**Cuándo se declara `INSUFFICIENT_GEOMETRY`:** (i) no hay posición solar → `POSICION_SOLAR` (línea 417); (ii) además, si no hay coordenada → `COORDENADA_OFICIAL` (línea 419); (iii) no hay azimut de fachada visible → `AZIMUT_FACHADA_VISIBLE` (línea 423). El azimut de fachada sólo existe si lo declara el llamador (`facade_bearing`), si proviene de street imagery verificable (`bearing_fachada_visible`, líneas 247-272) o de un centroide de huella desde la coordenada oficial (líneas 550-557); **sin ninguno de los tres no se adivina**. Verificado en esta corrida: con coordenada + fecha y nada más, `estado = INSUFFICIENT_GEOMETRY`, `geometria_faltante = ['AZIMUT_FACHADA_VISIBLE']`, `angulo_relativo_sol_fachada_deg = None` y `direccion_incidencia_solar` **sí** calculada (`origen: solar_engine.get_solar_position`).

## 4 · Regla bloqueante: ALTURA NORMATIVA ≠ ALTURA FÍSICA

`POT.altura_max` es el campo `altura_maxima` de la capa oficial de tratamientos, expresado **en PISOS** («campo `altura_maxima` en PISOS (p. ej. '11', '40')» — `api/edificabilidad.py` líneas 11-13). En la corrida Golden vale `"11"` (`DICTUS_RUN_STATE_040-646406.json` línea 1205). **No es la altura del edificio**: es la altura permitida por la norma.

| Pieza de la regla | Ubicación exacta | Contenido |
|---|---|---|
| Decisión única (autoridad) | `api/dictus_sources.py` → `altura_fisica(building_height, *, height_source, altura_normativa_pot)` (líneas 334-361) | Rechaza si `"POT"`, `"NORMATIV"` o `"EDIFICABILIDAD"` están en `height_source` (líneas 346-347) y devuelve `building_physical_height: None`, `shadow_confidence: "DEGRADED"` |
| Mensaje exacto de rechazo | `dictus_sources.py` líneas 350-352 | `RECHAZADO: «POT.altura_max» es altura NORMATIVA (11); POT.altura_max no puede usarse como altura física del edificio.` |
| Frontera del sistema | `api/facade_solar.py` → `resolver_altura_fisica(...)` (líneas 155-239) | Delega en `dictus_sources.altura_fisica` (líneas 199-200 y 231-232) y añade `TOKENS_ALTURA_PROHIBIDOS = ("POT","NORMATIV","EDIFICABILIDAD","ALTURA_MAXIMA","ALTURA_MAX")` (líneas 136-137) vía `es_fuente_normativa` (líneas 149-152) |
| Modo estricto (falla en vez de degradar) | líneas 170-174; excepción `AlturaNormativaComoFisicaRechazada` (línea 144) | `PROHIBIDO: «POT.altura_max» es altura NORMATIVA y no puede convertirse en building_physical_height. POT.altura_max sólo describe la norma urbanística.` |
| Declaración en la procedencia | líneas 580-587 | `altura_normativa_pot_rechazada` = fuente rechazada · `pot_altura_max_usada_como_fisica: False` |
| Comprobación de vocabulario | `verificar_vocabulario()` (líneas 614-627) | `regla_altura_delegada: True`, `pot_rechazado: True` — **verificado en esta corrida: los 6 indicadores devuelven `True`** |

**Verificado en esta corrida** (ejecutado): `resolver_altura_fisica(building_height=11, height_source="POT.altura_max", altura_normativa_pot=11)` → `building_physical_height = None`, `shadow_confidence = DEGRADED`, `blocks_dictus = False`, `rejected_source = "POT.altura_max"`.

**Divergencia real detectada (leída en código y ejecutada):** una fuente llamada, p. ej., `CATASTRO.ALTURA_MAXIMA` es rechazada por `facade_solar.es_fuente_normativa` (contiene `ALTURA_MAXIMA`), pero `dictus_sources.altura_fisica(9.0, height_source="CATASTRO.ALTURA_MAXIMA")` la **acepta** con `shadow_confidence: "OK"`, porque el motor delegado sólo mira `POT`/`NORMATIV`/`EDIFICABILIDAD`. La protección ampliada vive sólo en la frontera `facade_solar`; quien llame directo a `dictus_sources.altura_fisica` no la tiene.

## 5 · Degradación, nunca bloqueo

Sin altura física el resultado degrada y **declara**: `shadow_confidence = "DEGRADED"` (`SHADOW_CONFIDENCE_DEGRADED`, línea 126), `MOTIVO_SIN_ALTURA` (líneas 139-141) textualmente: «No hay fuente automática de altura física: NO se simula longitud física exacta de sombra. El estado de exposición se declara como aproximado y `shadow_confidence` se degrada (nunca se bloquea DICTUS).», con `shadow_length_simulated = False`, `physical_shadow_length_m = None`, `simulacion_avanzada_habilitada = False`, `estado_aproximado = True` (línea 496), `blocks_dictus = False` y `dictus_gate_impact = "NONE"` (líneas 453-454). **No existe clave `blocking` en la salida** (aserción de la prueba `test_analisis_con_altura_pot_no_la_usa_y_no_bloquea_dictus`). La longitud teórica sólo se calcula si `advanced_simulation_enabled` **y** `solar_el > 2.0°` (líneas 498-501).

La misma postura aguas abajo: `api/dictus_decision.manifiesto_sombras` (líneas 232-312) separa `REGULATORY_HEIGHT`, `BUILDING_PHYSICAL_HEIGHT` y `MODEL_ASSUMED_HEIGHT` (líneas 283-290) y marca `shadow_model_status = "PARTIAL / ORIENTATIVE"` cuando no hay altura física o la normativa está en conflicto (líneas 272-274). En el artefacto real `docs/forensics/040-646406/dictus_2c/DICTUS_SHADOW_MANIFEST_040-646406.json`: `BUILDING_PHYSICAL_HEIGHT: null`, `MODEL_ASSUMED_HEIGHT: "11"`, `model_assumed_source: "altura normativa del POT usada como referencia"`, `physical_height_source: null`, `geometry_source: null`, `shadow_model_status: "PARTIAL / ORIENTATIVE"`. Es decir: la normativa puede declararse como *supuesto de referencia del modelo* —nunca como altura física del edificio.

## 6 · Tabla resumen: condición → qué se reporta, con qué confianza y qué NO se afirma

| Estado / condición | Se reporta | Confianza | **NO** se afirma |
|---|---|---|---|
| `DIRECT_EXPOSURE_LIKELY` (`delta ≤ 45°` y `el ≥ 5°`, sin obstrucción declarada) | `estado`, `direccion_incidencia_solar`, `fachada_visible` (con método), `angulo_relativo_sol_fachada_deg`, `motivo` | `shadow_confidence = OK` **sólo** si hay altura física con fuente automática identificada; si no, `DEGRADED` (verificado: `${delta}` = 5.95° con `DEGRADED`) | Que sea medición física; que valga para la unidad/balcón concreto; que no pueda haber una obstrucción no declarada |
| `OBLIQUE_EXPOSURE` (`delta ≤ 90°`, o sol rasante `el < 5°`) | Igual que arriba + marca de «elevación solar rasante» en `motivo` | Igual (OK/DEGRADED según altura) | Incidencia perpendicular; sombra real del entorno |
| `FACADE_SHADED_OR_REARWARD` (`el ≤ 0`, obstrucción declarada, o `delta > 90°`) | `estado`, `motivo` con el caso exacto, `direccion_incidencia_solar` | Igual; `estado_aproximado = True` sin altura física | Que la fachada esté en penumbra todo el día; que el sol «nunca» incida (sólo describe la fecha/hora analizada) |
| `INSUFFICIENT_GEOMETRY` (falta posición solar y/o azimut de fachada) | `estado`, `geometria_faltante`, `limitaciones`, `direccion_incidencia_solar` si el sol sí se pudo calcular | `DEGRADED`; `angulo_relativo_sol_fachada_deg = None` | **Ningún** estado de exposición (nunca se promueve a `DIRECT_EXPOSURE_LIKELY`); ninguna sombra simulada |
| Altura normativa (`POT.altura_max` = 11 pisos) usada como física | `altura_normativa_pot`, `altura_normativa_pot_rechazada`, `pot_altura_max_usada_como_fisica: False` | `DEGRADED` | Que sea altura construida; que habilite la simulación de sombra |
| Altura física con fuente automática (`MS_BUILDINGS_FOOTPRINT.height`, catastro) | `building_physical_height`, `height_source`, `derivation` si viene de niveles (3.0 m/piso, línea 132) | `OK`, `advanced_simulation_enabled = True` | Que sea medición: es altura **declarada** por una fuente automática (verificado: 21 m → `physical_shadow_length_m = 20.358`) |

## 7 · Cómo reproducir

Ejecutado desde `arhiax-RE` en esta corrida (`PYTHONDONTWRITEBYTECODE=1`; sin red):

```powershell
# 1) Posición solar sólo con coordenada + fecha (Golden 040-646406, 2026-09-28)
python -c "import sys,datetime; sys.path.insert(0,'.'); from solar_engine import get_solar_position as g; \
print([g(11.005378,-74.8386199,datetime.datetime(2026,9,28,h,0,0)) for h in (9,12,15)])"
# → [(104.05, 45.89), (191.32, 77.05), (257.85, 41.04)]  · idéntico a solar_state.momentos del run state

# 2) Vocabulario y regla bloqueante de altura
python -c "import sys,json; sys.path.insert(0,'api'); import facade_solar as fs; \
print(json.dumps(fs.verificar_vocabulario(),ensure_ascii=False)); \
print(fs.resolver_altura_fisica(building_height=11,height_source='POT.altura_max',altura_normativa_pot=11)['reason'])"
# → 6 indicadores True · "RECHAZADO: «POT.altura_max» es altura NORMATIVA (11.0); POT.altura_max no puede usarse como altura física del edificio."

# 3) Especificación ejecutable (offline, sin credenciales)
python -m pytest tests/test_source_pack_imagery_solar.py -q     # → 49 passed in 0.23s (esta corrida)
```

| Archivo de salida real | Qué contiene | Verificación |
|---|---|---|
| `docs/forensics/040-646406/dictus_2b/DICTUS_RUN_STATE_040-646406.json` | `solar_state.momentos` (líneas 989-1017) con 09:00 «Sol Directo» incidencia 6.0° · 12:00 «Sol Directo» · 15:00 «Sombra (Orientación)»; activos `shadow_09` / `shadow_15` (líneas 1334-1353) | coincidencia exacta con el paso 1 |
| `docs/forensics/040-646406/dictus_2b/sombra_9am.png` · `sombra_3pm.png` | renders reales de la simulación geométrica (29 995 B · 29 714 B) | sha256 recalculado en esta corrida: `5c3c361f075ee60e48011a5ad26b000f781b5accdfa1430075251f8d51cd5e50` y `c91a0995a63039d018162eefcdb1e87974f3b1a542374844bc73f54c096ccc0c` — **coinciden** con el run state |
| `docs/forensics/040-646406/dictus_2c/DICTUS_SHADOW_MANIFEST_040-646406.json` | `ShadowManifest` completo (`simulation_id SHW-473b9bebf24a`, `height_concepts`, `dependencies`, `status`) | leído íntegro |
| `docs/forensics/040-646406/dictus_2b/DICTUS_MANIFEST_040-646406.json` | `shadow_manifest` embebido (líneas 1664-1715) con `solar_model: "solar_engine.get_solar_position (posición solar geocéntrica)"` | leído |

End-to-end de una corrida completa: `python scripts/dictus_run.py` (documentado en `docs/forensics/040-646406/dictus_2b/ENTREGA_2.0B_R1.md` línea 78). Los PNG de sombra se generan desde `api/pdf_compiler.py` líneas 1455-1470 (`from shadow_render import generar_sombras_automaticas` → `generar_sombras_automaticas(lat, lon, assets_dir)`), que sólo actúa si el caso no trae ya `sombra_9am.png` / `sombra_3pm.png`.

## 8 · Discrepancias con el encargo y lo NO verificado en esta corrida

| Punto | Realidad verificada |
|---|---|
| El encargo nombra `FACADE_SOLAR_EXPOSURE` | No existe ese literal en el repo; use `ESTADOS_EXPOSICION` / `FacadeSolarExposure` / `analizar_exposicion_fachada` |
| «Azimut/altura + 4 estados» | El vocabulario §22 vive en `api/facade_solar.py`, pero el asoleamiento que las corridas Golden persisten lo produce **otro** camino: `api/pdf_compiler.py` líneas 2106-2111 con `solar_engine.analyze_facade_exposure`, `FACADE_AZIMUTH = 110` (orientación ESE **por defecto**, línea 1849) y `OBSTRUCTIONS = [(240, 280, 30)]` (línea 1850). Los estados del run state («Sol Directo» / «Sombra (Orientación)») son de ESE vocabulario, no del §22 |
| Salida de `api/facade_solar.py` en artefactos Golden | **No verificado / ausente**: `grep` de `DIRECT_EXPOSURE_LIKELY`, `INSUFFICIENT_GEOMETRY` y `shadow_confidence` sobre todo `docs/` → 0 coincidencias. El módulo está implementado y probado (49 pruebas), pero no aparece en los artefactos de las corridas 2.0B/2.0C |
| Metadatos por corrida de la simulación | **No verificado**: `shadow_simulation` está **vacío** (`{}`) en `dictus_2b/DICTUS_RUN_STATE_040-646406.json` línea 1361 y en `dictus_2c` línea 1544, por lo que la altura realmente usada por los PNG Golden no quedó declarada en el run state. Dónde se verificaría: el retorno de `generar_sombras_automaticas` (`api/pdf_compiler.py` línea 1464), capturado por el observador de `api/dictus_estado.py` líneas 365-382 |
| Contenido/leyenda interna de `sombra_9am.png` y `sombra_3pm.png` | **No verificado en esta corrida**: el modelo en uso no acepta entrada de imagen y los PNG no llevan metadatos `tEXt`/`iTXt` (comprobado). Dónde se verificaría: abrir el PNG (leyenda «Sol: azimut … elevación … altura edificio … m») o el punto anterior |
| Capa 310 del catastro en vivo | No se consultó la red en esta corrida: no verificado si el servicio respondió, ni la altura que aportó a los PNG Golden |
| `ELEVACION_MINIMA_SOMBRA_M` (línea 131) | El sufijo `_M` (metros) es engañoso: se compara contra **elevación en grados** (línea 498). Nombre heredado, no un factor de conversión |
| Diferencia de coordenada | La tarea da `11.005378, -74.8386199`; el manifiesto de sombras 2.0C registra `location` `11.006055954316363, -74.8375696549899`. Verificado en esta corrida: ambas producen la misma posición solar redondeada a 2 decimales en los tres momentos |

**Sin altura física el dictamen nunca se bloquea** (`blocks_dictus: False`, `dictus_gate_impact: "NONE"`, `shadow_model_status: "PARTIAL / ORIENTATIVE"`): la limitación se declara, la sombra no se simula y el resto del dictamen continúa.

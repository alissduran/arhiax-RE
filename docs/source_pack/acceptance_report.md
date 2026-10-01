# BARRANQUILLA SOURCE PACK v1.0 — REPORTE DE ACEPTACIÓN (§34) CON DOS ESTADOS

Caso Golden: **040-646406** · Ciudad: Barranquilla · Ventana: **2026-09-29** ·
Capa de adquisición: `acquisition-modes/1` (`api/acquisition.py`)
Registro: `barranquilla_sources_v1.json` / `.yaml` (gemelos) · Manifest:
`BARRANQUILLA_SOURCE_PACK_MANIFEST.json`
Matriz del **contrato** (7 col.): `SOURCE_COVERAGE_MATRIX_040-646406.csv` (intacta)
Matriz de **adquisición** (11 col.): `SOURCE_ACQUISITION_MATRIX_040-646406.csv`
Inventario de snapshots reales: `SNAPSHOT_INVENTORY.json` · Doctrina: `ACQUISITION_MODES.md`

> **Este reporte separa los dos estados y NO los mezcla.** `CONTRACT_FROZEN` es una afirmación
> sobre el CONTRATO (registro, roles, modos, snapshots, binding, precedencia, escalera,
> licencias). `OPERATIONAL_READY` es una afirmación sobre el DATO (que hoy exista una ruta
> automática válida para cada dominio CORE). **Hoy el primero es SÍ y el segundo es NO.**
>
> Todos los identificadores de entrada (dirección, NUPRE, número predial, folio, coordenada,
> fecha) se **LEEN** de `docs/forensics/040-646406/dictus_2b/DICTUS_RUN_STATE_040-646406.json`.
> Ninguno está codificado a mano en la matriz ni en las pruebas.
>
> **Aviso de concurrencia (transparencia).** Durante la ventana de esta misión, otro flujo de
> trabajo reescribió `docs/source_pack/barranquilla_sources_v1.{json,yaml}` (mtime
> 2026-09-29T11:55) retirando `LONJA_MARKET_BAQ` de `sources` y declarándola en el bloque
> `no_fuentes_institucionales` (`en_source_registry: false`, `aportan_datos_a_dictus: false`),
> y editó `api/market_sources.py` con esa misma doctrina (`product_role: "NOT_A_SOURCE"`).
> Este reporte describe el registro **tal como quedó sellado después** de esa reescritura, y
> re-sella la capa de adquisición encima con un solo comando (`python -m api.acquisition
> --escribir`). Los sellos de `product_role`/`acquisition_mode`/`acquisition_snapshot` por
> fuente sobreviven a esa reescritura (verificado). Ningún archivo de otro flujo fue
> modificado por esta misión.

---

## 1 · ESTADO 1 · **CONTRACT_FROZEN** — criterio por criterio (§O)

| # | Criterio | Comando | Resultado |
|---|---|---|---|
| 1 | **Registro sellado y re-verificable**: 34 fuentes declaradas (registro sellado `payload_sha256 96a69cbe…`); las 25 claves del contrato + `product_role` + `acquisition_mode` + `acquisition_snapshot` en CADA una | `python -m pytest tests/test_source_pack_acquisition_modes.py -q -k "tiene_rol_y_modo"` | `1 passed` — `product_role` ∈ 6 valores cerrados, `acquisition_mode` ∈ 3 valores cerrados, `product_role` == `rol_de_fuente(sid)`, sin excepciones |
| 2 | **Metadata real por fuente** (institución, servicio, capa, método, vigencia, licencia, `enabled`) y gemelo YAML idéntico | `python -m pytest tests/test_source_pack_acquisition_modes.py -q -k "gemelo or contrato_de_fuentes"` | `2 passed` — `json.loads(JSON) == yaml.safe_load(YAML)` con la capa de adquisición incluida |
| 3 | **Market formalizada**: `LONJA_MARKET_BAQ` (o, en el registro vigente, su retiro declarado en `no_fuentes_institucionales`) con su rol `CORE_MARKET` y su snapshot real hasheado | `python -m pytest tests/test_source_pack_acquisition_modes.py -q -k "roles_core_estan_poblados"` | `1 passed` — el dominio `mercado` declara `CORE_MARKET`; hoy su fuente **no está en `sources`** y el pack lo declara (no se inventa) |
| 4 | **Binding tipado**: un identificador solo coteja contra campos de SU tipo; `features[0]` jamás decide | `python -m pytest tests/test_source_pack_binding_typed.py -q` | `36 passed` |
| 5 | **Precedencia determinista** (autoridad → vigencia → prioridad → alfabeto), independiente del orden de entrada | `python -m pytest tests/test_source_pack_acquisition_modes.py -q -k "reproducibilidad or precedencia"` | `5 passed` — permutar consultas no cambia la fuente seleccionada |
| 6 | **Escalera por atributo** con fallback y registro de cada intento (no reimplementada por la capa de adquisición) | `python -m pytest tests/test_source_pack_resolution_ladder.py -q` | `59 passed` |
| 7 | **Licencias documentadas** por fuente y fail-closed | `python -m pytest tests/test_source_pack_market.py -q` | `60 passed` |
| 8 | **Modos de adquisición** declarados por fuente + regla de caída LIVE→SNAPSHOT con `authority_class` ORIGINAL conservada | `python -m pytest tests/test_source_pack_acquisition_modes.py -q -k "ReglaDeAdquisicion"` | `8 passed` |
| 9 | **Snapshots REALES descubiertos** (ruta, commit, bytes, sha256, atributos) y sin invención | `python -m api.acquisition --inventario` | `total_artefactos: 279 · declarados: 7 · usables: 5 · resuelven_en_la_ventana: 4 · no_usables: 274` — el único declarado que NO resuelve es `SNAP_LONJA_METODOLOGIA` (`VENCIDO`) |
| 10 | **Matriz de adquisición de 11 columnas CALCULADA** (no escrita a mano) | `python -m pytest tests/test_source_pack_acquisition_modes.py -q -k "MatrizDeRoles"` | `11 passed` — la matriz versionada == la recalculada, columna por columna |
| 11 | **Dos estados publicados en el manifest** | `python -m api.acquisition --estado` | `contract: CONTRACT_FROZEN (10 criterios)` · `operational: OPERATIONAL_NOT_READY` |
| 12 | **Constructor del contrato intacto** | `python scripts/source_pack_build.py --check` | `OK registro: 34 fuentes (19 habilitadas, 15 deshabilitadas declaradas)` |
| 13 | **Nada de lo PROHIBIDO fue tocado** | `git status --porcelain` | Este flujo solo creó `api/acquisition.py`, `tests/test_source_pack_acquisition_modes.py`, `docs/source_pack/ACQUISITION_MODES.md`, `docs/source_pack/SNAPSHOT_INVENTORY.json`, `docs/source_pack/SOURCE_ACQUISITION_MATRIX_040-646406.csv` y actualizó `acceptance_report.md`, el registro+gemelo y el manifest. `dictus_sources.py`, `source_resolution.py`, `street_imagery.py`, `facade_solar.py`, `market_sources.py`, `source_licenses.py`, el PDF, los motores, el gate y el hash **no** se tocaron |

**CONTRACT_FROZEN = SÍ** (13/13 criterios con comando y resultado).

---

## 2 · ESTADO 2 · **OPERATIONAL_READY** — E2E CORE con datos reales

| # | Criterio | Comando | Resultado |
|---|---|---|---|
| 1 | **E2E · SOLO DIRECCIÓN**: la escalera INTENTA `LIVE_QUERY`, registra cada `SourceResult` y no pide nada a una persona | `python -m pytest tests/test_source_pack_acquisition_modes.py -q -k "E2ESoloDireccion"` | `3 passed` — `CATASTRO_BAQ_DIRECCION` → `SOURCE_UNAVAILABLE` (HTTP 403, detalle íntegro), `intervencion_manual=False`, `requiere_identificadores_manuales=False`, cero frases que soliciten datos a una persona |
| 2 | **Caída a SNAPSHOT cuando procede**, con la respuesta documentada de la capa 105 (replay de la evidencia congelada del run state) | idem | `1 passed` — la dirección se resuelve por `LIVE_QUERY` y la identidad se confirma por modo autorizado **no** vivo (`AUTHORIZED_FALLBACK`), conservando `AUTHORITATIVA_OFICIAL` |
| 3 | **E2E · SOLO CTL/MATRÍCULA** alcanza la **MISMA** `CanonicalPropertyIdentity` que el camino de dirección | `python -m pytest tests/test_source_pack_acquisition_modes.py -q -k "E2ESoloMatricula"` | `3 passed` — objetos **idénticos** (mismo NUPRE, predio, folio, nomenclatura, torre, apartamento, PH y `VERIFIED_UNIT_IDENTITY`); entrada por `ORIP`+`FMI` (`EXACT_2`) |
| 4 | **Negativos**: predio vecino jamás liga la identidad del Golden | `python -m pytest tests/test_source_pack_acquisition_modes.py -q -k "Negativos"` | `5 passed` — vecino real del snapshot (`…003`/`AFT0005BORE`/`646407`) nunca liga el predio `…002`/`AFT0005BOHA`/`646406`; identificadores disjuntos → `CONFLICT` explícito |
| 5 | **Negativos**: `SOURCE_UNAVAILABLE` nunca se convierte en `NO_MATCH` | idem | `1 passed` (18 atributos, subpruebas) — ningún `attempt` con estado `NO_MATCH`; sin valor, el valor es `None` (jamás `0`) |
| 6 | **Negativos**: caso no-PH declarado | idem | declarado `propiedad_horizontal=False` con condición jurídica «NO PROPIEDAD HORIZONTAL» → no exige unidad verificada; el caso Golden (PH) sí exige `VERIFIED_UNIT_IDENTITY` |
| 7 | **Snapshot VENCIDO no resuelve** (se declara y la escalera sigue) | `... -q -k "Frescura"` | `7 passed` — la metodología de la Lonja declara `vigencia_hasta=2026-08-31` < corrida `2026-09-29` → `VENCIDO`, sin valor y sin `NO_MATCH`; caso controlado inyectado (creado en 2020) → límite `2020-12-31`, no resuelve |
| 8 | **Reproducibilidad (§N)**: mismas respuestas crudas ⇒ mismos payloads, bindings, precedencia y `content_hash`; `queried_at`/`run_id` fuera de todo hash | `... -q -k "Reproducibilidad"` | `5 passed` |
| 9 | **Cobertura CORE medida** | `python -m api.acquisition --estado` | `CORE cubiertos: identidad, remocion, riesgo` · `CORE NO cubiertos: direccion, predio, uso_pot, tratamiento, edificabilidad, inundacion, mercado` |

### 2.1 Qué dominios CORE quedan cubiertos por `AUTOMATED_SNAPSHOT` **dentro de frescura** y cuáles NO

**El geoportal responde HTTP 403 (Cloudflare) — VERIFICADO en esta ventana**: sonda propia
`2026-09-29T11:58:50-05:00` → `HTTP 403 | Server: cloudflare | CF-RAY: a42c88f5aba321b7-BOG |
Date: Tue, 29 Sep 2026 16:58:51 GMT`, y evidencia congelada
`raw/golden/_layers_probe.json` con **150/150 intentos en 403**.

| Dominio CORE | Fuente | Ruta válida HOY | ¿Cubierto? |
|---|---|---|---|
| `identidad` | `CATASTRO_BAQ_ADOPCION_ANEXO1` | `AUTHORIZED_FALLBACK` → `api/data/barranquilla_adopcion_anexo1.json` (creado 2026-09-20; CATASTRO 90 d → 2026-12-19) | **SÍ** |
| `remocion` | `POT_BAQ_REMOCION_2024` | LIVE 403 → `AUTOMATED_SNAPSHOT` → `api/data/amenaza_remocion_masa.geojson` (2026-09-01; RIESGO 365 d → 2027-09-01) | **SÍ** |
| `riesgo` | `POT_BAQ_RIESGO_2024` | LIVE 403 → `AUTOMATED_SNAPSHOT` → `api/data/areas_en_riesgo.geojson` (2026-09-01; RIESGO 365 d → 2027-09-01) | **SÍ** |
| `direccion` | `CATASTRO_BAQ_DIRECCION` (capa 105) | Solo LIVE (403). **No hay snapshot declarado** de la capa 105. | **NO** |
| `predio` | `CATASTRO_BAQ_PREDIO` (tabla 100) | Solo LIVE (403). El único artefacto hallado (`catastro_baq_predio.json`) es un **fixture de prueba**: se declara NO utilizable. | **NO** |
| `uso_pot` | `POT_BAQ_POLIGONOS_USO` | LIVE; fuente **deshabilitada** (capas 83/85/87/89/91/92 sin verificar) → `NOT_SUPPORTED`. | **NO** |
| `tratamiento` | `POT_BAQ_TRATAMIENTO` | Solo LIVE (403), sin snapshot. | **NO** |
| `edificabilidad` | `POT_BAQ_EDIFICABILIDAD` | Solo LIVE (403), sin snapshot. | **NO** |
| `inundacion` | `POT_BAQ_INUNDACION_2024` | LIVE; deshabilitada y **sin copia empaquetada** (no existe `api/data/*inundacion*`). | **NO** (no se afirma «sin amenaza») |
| `mercado` | `LONJA_MARKET_BAQ` | (a) el registro vigente **no la lista en `sources`** (retiro declarado); (b) además su snapshot congelado está **VENCIDO** (`2026-08-31`). | **NO** |

Declaraciones honestas, sin maquillaje:

1. **`CORE_IDENTITY` solo entra hoy por el camino de la MATRÍCULA** (folio SNR → `ORIP`+`FMI`
   → registro de adopción). El camino «solo dirección» **no** tiene ruta automática: depende de
   la capa 105 en vivo, que responde 403.
2. **`CORE_NORMATIVE` (uso, tratamiento, edificabilidad) no tiene NINGUNA ruta automática**
   hoy: no hay snapshot empaquetado de esas capas y varias están deshabilitadas por no poder
   verificarse su `layer_id`.
3. **`CORE_RISK` está incompleto**: remoción y riesgo sí (snapshots vigentes); **inundación no**.
4. **`CORE_MARKET` no está cubierto**: sin fuente registrada y con metodología vencida.
5. La sonda de estratificación **no se usa** aunque exista: devuelve manzanas **vecinas** del
   buffer, y afirmar con ella el estrato del predio sería una inferencia espacial prohibida.
6. `DECISION_CONTEXT` (barrio, localidad, estrato, construcción, destino, equipamiento
   oficial) y `OPTIONAL_ENRICHMENT` (OSM —cubierto por captura—, Mapillary/Google —sin
   credenciales—) tampoco tienen ruta viva: se declaran, no bloquean por sí solos.

**OPERATIONAL_READY = NO** (3 de 10 dominios CORE con ruta válida; 7 sin ruta).

---

## 3 · Resultado EXACTO de las suites

```
python -m pytest tests/test_source_pack_acquisition_modes.py tests/test_source_pack_resolution_ladder.py tests/test_source_pack_contract.py -q
158 passed, 1 warning, 39 subtests passed in 27.06s        (73 + 59 + 26; 0 skips, 0 fallos)

python -m pytest tests/test_source_pack_market.py tests/test_source_pack_imagery_solar.py tests/test_source_pack_pipeline.py tests/test_dictus_20d_r1_p6.py -q
155 passed, 1 xfailed, 1 warning in 2.46s                  (60 + 49 + 36 + 10 con 1 xfail declarado)

python -m pytest tests/test_source_pack_binding_typed.py -q
36 passed, 1 warning in 0.21s
```

La única advertencia es de `pytest` (no puede escribir su caché por permisos de la carpeta
temporal del entorno): no afecta al resultado.

---

## 4 · Matriz de adquisición (18 filas × 11 columnas, CALCULADA)

```
domain                source_id                        product_role        status              binding
identidad             CATASTRO_BAQ_ADOPCION_ANEXO1     CORE_IDENTITY       AVAILABLE           NUPRE_EXACTO
direccion             CATASTRO_BAQ_DIRECCION           CORE_IDENTITY       SOURCE_UNAVAILABLE  NO_BINDING
predio                CATASTRO_BAQ_PREDIO              CORE_IDENTITY       SOURCE_UNAVAILABLE  NO_BINDING
construccion          CATASTRO_BAQ_CONSTRUCCION        DECISION_CONTEXT    SOURCE_UNAVAILABLE  NO_APLICA…
barrio                POT_BAQ_BARRIOS                  DECISION_CONTEXT    SOURCE_UNAVAILABLE  NO_APLICA…
localidad             POT_BAQ_LOCALIDADES              DECISION_CONTEXT    SOURCE_UNAVAILABLE  NO_APLICA…
destino               CATASTRO_BAQ_DESTINO_ECONOMICO   DECISION_CONTEXT    SOURCE_UNAVAILABLE  NO_APLICA…
uso_pot               POT_BAQ_POLIGONOS_USO            CORE_NORMATIVE      NOT_SUPPORTED       NO_APLICA…
tratamiento           POT_BAQ_TRATAMIENTO              CORE_NORMATIVE      SOURCE_UNAVAILABLE  NO_APLICA…
edificabilidad        POT_BAQ_EDIFICABILIDAD           CORE_NORMATIVE      SOURCE_UNAVAILABLE  NO_APLICA…
remocion              POT_BAQ_REMOCION_2024            CORE_RISK           AVAILABLE           NO_APLICA…
inundacion            POT_BAQ_INUNDACION_2024          CORE_RISK           NOT_SUPPORTED       NO_APLICA…
riesgo                POT_BAQ_RIESGO_2024              CORE_RISK           AVAILABLE           NO_APLICA…
equipamiento_oficial  EQUIPAMIENTO_*                   DECISION_CONTEXT    NOT_SUPPORTED       NO_APLICA…
servicios_contexto    OSM_OVERPASS                     OPTIONAL_ENRICHMENT AVAILABLE           NO_APLICA…
street_imagery        MAPILLARY+GOOGLE_STREET_VIEW     OPTIONAL_ENRICHMENT SOURCE_UNAVAILABLE  NO_APLICA…
solar                 SOLAR_ENGINE+SHADOW_FACADE_EXP…  DECISION_CONTEXT    AVAILABLE           NO_APLICA…
mercado               LONJA_MARKET_BAQ                 CORE_MARKET         NOT_SUPPORTED       NO_APLICA…
```

4 `AVAILABLE` por ruta automática · 0 `NO_MATCH` (ninguna ausencia se disfrazó de «sin
coincidencia») · `required_for_decision`/`blocking_if_missing` **derivados del rol** (y
anulados para capas `HISTORICAL_REFERENCE`, que son referencia, no operativas).

La matriz del **contrato** de 7 columnas (`SOURCE_COVERAGE_MATRIX_040-646406.csv`) queda
**intacta**: la matriz de adquisición es un artefacto NUEVO, porque las 7 columnas están
fijadas por `tests/test_source_pack_pipeline.py` (prueba `test_matriz_tiene_18_filas_y_7_columnas`).
Extenderla en el mismo archivo habría roto una prueba congelada.

---

## 5 · Entregables y huellas (sha256, primeros 16 hex)

| Entregable | Ruta | sha256 |
|---|---|---|
| Módulo de adquisición (NUEVO) | `api/acquisition.py` | `DD63FD5AC3F3F225` |
| Pruebas BLOQUEANTES (NUEVO) | `tests/test_source_pack_acquisition_modes.py` | `7B18759009FA8BF8` |
| Registro sellado (JSON) | `docs/source_pack/barranquilla_sources_v1.json` | `6A1AF41E281ABE4E` |
| Registro sellado (YAML, gemelo) | `docs/source_pack/barranquilla_sources_v1.yaml` | `350E909B035D14D6` |
| Manifest (dos estados) | `docs/source_pack/BARRANQUILLA_SOURCE_PACK_MANIFEST.json` | `461D0D97B9102090` |
| Matriz de adquisición (11 col.) | `docs/source_pack/SOURCE_ACQUISITION_MATRIX_040-646406.csv` | `441F4007C6E166E6` |
| Inventario de snapshots | `docs/source_pack/SNAPSHOT_INVENTORY.json` | `627EEF862911B3A5` |
| Doctrina de modos | `docs/source_pack/ACQUISITION_MODES.md` | `90EC38B3E648CD02` |

`payload_sha256` del registro sellado (cabecera del gemelo YAML): `96a69cbe37712b9a…`.

> Las huellas de los artefactos **generados** cambian si se re-ejecuta
> `python -m api.acquisition --escribir` (el manifest lleva su `tested_at`). El contenido
> determinista que produce el comando es estable, y el `payload_sha256` del registro se publica
> en la cabecera del gemelo.

---

## 6 · Frase de estado final propuesta

> **CONTRACT FROZEN / OPERATIONAL NOT READY.**

**Justificación medida.** El CONTRATO está congelado: 34 fuentes con metadata real,
`product_role` y `acquisition_mode` declarados, snapshots reales descubiertos con su sha256 y
su fecha de commit, un inventario que excluye con motivo lo que no puede usarse, binding
tipado, precedencia determinista, escalera por atributo, licencias documentadas y una matriz
de adquisición calculada (158 pruebas en verde en la suite exigida). Pero **NO está listo para
producción**: de los 10 dominios CORE, solo **identidad, remoción y riesgo** tienen ruta
automática válida hoy (`AUTHORIZED_FALLBACK`/`AUTOMATED_SNAPSHOT` dentro de frescura);
**dirección, predio, uso POT, tratamiento, edificabilidad, inundación y mercado** NO la tienen
—el geoportal responde **HTTP 403 (Cloudflare) verificado** y no existe snapshot declarado
para esas capas—, y la identidad CORE solo entra por el camino de la matrícula (el camino
«solo dirección» depende de la capa 105 en vivo). No se autoriza, por tanto, declarar
PRODUCTION READY: hacerlo exigiría aceptar que dominios CORE queden en `SOURCE_UNAVAILABLE`,
que es exactamente lo que la decisión de producto prohíbe.

---

## 7 · LONJA: NO ES FUENTE — constancia de la aplicación (decisión de producto)

Aplicación de la decisión «la Lonja **no es** una fuente de datos» a los artefactos emisores,
con las sustituciones de `docs/source_pack/MARKET_CONTEXT_AUDIT.md` (Anexo C) que no tocan
fórmula, compuerta, `estrato_map` ni identificadores sellados. **No se mutó el artefacto
metodológico** (`lonja_baq_metodologia.yaml`): su `sha256` (`4ccd5832…`) y el `market_methodology_id`
siguen intactos, y la etiqueta verdadera se aplica al exponer/renderizar el texto.

### 7.a · MERCADO SIN FUENTE EXTERNA VERIFICABLE (hecho declarado, no maquillado)

- El valor por m² **no tiene fuente externa**: es una constante escrita a mano en
  `motor_tma_lonja_baq_v1.0/motor_tma_lonja_baq_v1.0/lonja_layer/lonja_baq_metodologia.yaml`
  (fila `Miramar`, `:214`), cuya `fuente` declaraba un origen real (precio verificado en la
  constructora) **más** un añadido sin soporte (`+ Lonja BAQ referencial`) — sin URL, sin fecha
  de consulta, sin `sample_size` y sin comparables.
- Su vigencia declarada (`vigencia_hasta: 2026-08-31`) estaba **VENCIDA** en la corrida Golden
  (`2026-09-28`): el pack lo declara (`vigencia_ok=False`, `VENCIDA`) y **no** lo convierte en
  bloqueo.
- **No existe ninguna fuente de mercado en el Source Registry**: `LONJA_MARKET_BAQ` fue retirada
  de `sources` y declarada en `no_fuentes_institucionales.aliados.LONJA_BAQ`
  (`es_fuente_de_datos: false`, `aporta_datos_a_dictus: false`, `en_source_registry: false`,
  `product_role: NOT_A_SOURCE`). El bloque `no_fuentes_institucionales.valor_de_mercado` declara
  el estado: **NO DISPONIBLE como fuente**; el valor es un parámetro declarado por la corrida.
- **La resolución de mercado es fail-closed y declarada**: `api/source_resolution.py` deja el
  escalón de `mercado` **vacío** (`SOURCE_UNAVAILABLE`, `value=None`,
  `ladder_notes=["sin_fuente_declarada"]`) y `api/market_sources.py::consultar_mercado` devuelve
  `SOURCE_UNAVAILABLE` con `value_per_m2 = None`; el valor declarado viaja **etiquetado** en
  `valor_declarado_por_la_corrida` (jamás como dato de fuente, jamás sustituido por otro dato,
  por el promedio de otros sectores ni por el fallback genérico por estrato).
- La **valoración sigue operando como hoy**: la tasa la resuelve `api/market_context.py` con la
  misma aritmética, umbrales, compuerta y gramática. **Ninguna fórmula, umbral ni hash cambió.**

### 7.b · MENCIONES «LONJA» ELIMINADAS DE LOS DOCUMENTOS

| # | Artefacto:línea | Antes | Ahora |
|---|---|---|---|
| S1 | `api/dictus_ejecutivo.py:1751` | `Fuentes: Metodología de mercado (Lonja)` | `Fuentes: Parámetros de mercado declarados por la corrida` |
| S2 | `api/dictus_secciones.py:521-523` | `Comparación de mercado · lonja_baq_metodologia v0.1-codiseno` (el id sellado **impreso**) | `Comparación de mercado (parámetros declarados por la corrida)`; el id sigue en su campo de máquina (`market_methodology_id`) |
| S3 | `api/dictus_secciones.py:733` + `api/market_context.py:189-195` | `Tasa y parámetros: … + Lonja BAQ referencial` | `… — parámetros declarados por la corrida (sin fuente externa automática verificada)`; la atribución no acreditada se **retira del texto** sin borrar el origen real declarado |
| S4 | `api/dictus_estado.py:599` | `{"tipo": "VALORACION", "fuente": "metodología de mercado (Lonja)"}` | `"fuente": "parámetros de mercado declarados por la corrida"` |
| S5 | `api/pdf_compiler.py:2848` | `(Lonja/IGAC)` / `los parametros de la Lonja de Barranquilla` | `(metodología local/IGAC)` / `los parametros de la metodología local de Barranquilla` |
| S6 | `api/pdf_compiler.py:2862` | `practica de la Lonja de Barranquilla` | `practica declarada por la metodología local de la corrida` |
| S8 | `api/dictamen_data.py:485` | `Práctica de la Lonja de Barranquilla: PH = 100% M1…` | `Práctica declarada por la metodología local de la corrida: PH = 100% M1…` |
| S9/S16/S17/S18/S19 | comentarios y docstrings en `api/dictamen_data.py`, `api/market_context.py`, `api/pdf_compiler.py` | nombrar la Lonja como origen de la práctica | metodología local declarada por la corrida |
| S10 | `api/market_sources.py:92-93` | `SOURCE_NAME/INSTITUTION` = Lonja de Propiedad Raíz | artefacto local, sin institución proveedora verificada; `PRODUCT_ROLE=NOT_A_SOURCE` |
| S13/S14 | `api/source_licenses.py:121,633,649` | atribución y `license_name` contractuales de la Lonja | artefacto local de metodología, licencia DECLARADA |
| S15 | `api/source_resolution.py:370` | «metodología contractual (Lonja)» | «parámetros declarados por la corrida (metodología local…)» |

**No aplicadas (y por qué):** **S7** (etiqueta `[FUENTE: ESTIMACIÓN REFERENCIAL DE MERCADO
ARHIAX (AUTOMÁTICA)]`) — prohibida por la misión: es un hallazgo para decisión de producto
(sigue vigente y marcada en `tests/test_no_lonja_as_source.py` como hallazgo reportado);
**S11/S12** (`entidad`/`autor` del YAML) y **S3-en-YAML** — no se muta el artefacto: cambiar su
`sha256` habría re-sellado `market_methodology_sha256` y el hash maestro; el arreglo se hizo en
el renderizador/exposición del texto; **S20** (`api/dictus_historia.py:67`) — es una aguja de
filtrado del histórico, no una afirmación de fuente.

### 7.c · LO QUE FALTA PARA `OPERATIONAL_READY` EN MERCADO

1. **Una fuente de mercado de tercero verificable**: URL, fecha de consulta, `sha256` de la
   respuesta, `sample_size` y comparables (hoy: `url: None`, `http_status: None`, `bytes: None`,
   `sample_size: null`).
2. **Vigencia honesta**: una metodología con `vigencia_hasta` posterior a la fecha de la corrida
   (hoy vencida desde `2026-08-31`).
3. **Contrato firmado de la metodología** (hoy `provider_terms_status = DECLARED`, no
   `VERIFIED`) o, en su defecto, la **validación firmada del avaluador RAA** sobre los
   parámetros declarados.
4. **Relajar el fail-closed NO es la salida**: `OPERATIONAL_READY` en mercado sólo pasa de NO a
   SÍ con (1)-(3); el escalón vacío y la ausencia declarada son el estado correcto mientras no
   exista esa fuente.

**Reportado, no corregido (decisión de producto pendiente):** la etiqueta `(AUTOMÁTICA)` del
técnico (§7.b, S7) y el `estrato_map = {3: 3.8M, 4: 5.2M, 5: 6.5M, 6: 7.8M}` con default
`5.2M` de `api/dictamen_data.py` (rama legacy `allow_legacy_reference`, marcada
`GENERIC_ESTRATO_FALLBACK` y excluida de la compuerta). Ninguno de los dos se tocó aquí.

### 7.d · GUARDA Y PRUEBAS

- **Nueva guarda**: `tests/test_no_lonja_as_source.py` (11 pruebas) — **renderiza** el ejecutivo
  con el contexto de mercado declarado tal cual (incluida `+ Lonja BAQ referencial` y el id
  sellado) y **extrae el texto** de las 6 páginas con `pypdf`: ninguna puede contener «lonja»;
  comprueba además el texto del técnico (`get_valoracion_alert`) y los literales de los módulos
  que escriben documentos. Falla si la doctrina se revierte.
- **Pruebas actualizadas a la doctrina nueva** (antes verificaban la vieja):
  `tests/test_source_pack_market.py` (`TestNoEsFuente`, consulta fail-closed, Golden: la fuente no
  resuelve y el parámetro declarado sí), `tests/test_source_pack_pipeline.py` (fuentes mínimas sin
  `LONJA_MARKET_BAQ`, fila de mercado `SOURCE_UNAVAILABLE`, manifiesto/registro coherentes),
  `tests/test_source_pack_resolution_ladder.py` (escalón de `mercado` vacío → `SOURCE_UNAVAILABLE`;
  fallback ejercitado con `localidad`), `tests/test_source_pack_licenses.py` (el registro del pack
  v1 ya no la declara fuente), `tests/test_dictus_20c_fidelidad.py` (el ejecutivo imprime la
  etiqueta verdadera y **no** el id sellado, que sigue en el plano máquina).

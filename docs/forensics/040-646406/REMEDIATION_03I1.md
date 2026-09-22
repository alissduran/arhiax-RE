# REMEDIATION 03I.1 — DICTUS Product Coherence Closure

**Estado: CLOSED — `03I.1 — DICTUS V1 PRODUCT COHERENCE ACCEPTED`**

Base: `03I — GOLDEN ACCEPTED WITH NON-BLOCKING FINDINGS`. **No se inició SLICE-002.**

## Qué cerró esta slice

Los siete defectos de coherencia que separaban al Golden integrado de un Dictus v1
comercialmente coherente, más el arnés de QA (que era el primero en incumplir su
propio contrato) y un defecto nuevo que la propia corrida real destapó.

| Ref | Defecto | Cierre |
|---|---|---|
| **A.1** | Manifest con `commit_sha=null` y `versions={}` | El runner obtiene el SHA de `git rev-parse HEAD` (`versioning.git_commit_sha()`) y las 5 versiones de `VERSION_MATRIX`; **falla** si falta cualquiera. Además registra la identidad del **árbol de trabajo** (`git diff HEAD` sha256 + archivos) porque la corrida se hace con la slice aplicada, no solo con el HEAD. |
| **A.2** | `GOLDEN_INTERNAL_STATE.poi = {}` y la matriz hardcodeaba "4 categorías AVAILABLE (3 ítems c/u)" | Un observador de `poi_engine.get_poi_result` (incluida la referencia que usa el compilador) vuelca categoría, estado, nº de ítems, fuente de cada ítem y fuentes intentadas/exitosas. La matriz y el §K **consumen** ese dato; hay un check que falla si aparece un conteo fijo. |
| **A.3** | El CTL de aceptación se reconstruía desde la constante `_CTL` de un test | El runner exige `--ctl <archivo.pdf>`, procesa ESE binario, registra `path`, `sha256`, `size` e `input_type=ORIGINAL_BINARY`, y copia el binario a los artefactos. La corrida definitiva usó el **CTL original** (124 345 B, sha256 `4493da88…`). |
| **B / F1** | `TIT_B01` decía "no hay área registral ni catastral" con 58.75 m² en 6.1 | Estados explícitos `BOTH_AVAILABLE` / `REGISTRAL_ONLY` / `CATASTRAL_ONLY` / `BOTH_UNAVAILABLE` / `MISMATCH`. Un área ausente nunca equivale a las dos. |
| **C / F2** | 6.2 imprimía "CONSOLIDACION / DESARROLLO" fijo y "Fuente de capas: GeoJSON empaquetados (sin consulta en vivo)" mientras 6.3 mostraba valores de la capa oficial viva | 6.2 y 6.3 consumen el **mismo** `OfficialUrbanContext`; se eliminó toda cadena fija de tratamiento/altura y la fila de fuente sale de un **`UrbanSourceSummary`** con `source_mode` (`LIVE_OFFICIAL` / `PACKAGED_REFERENCE` / `MIXED` / `SOURCE_UNAVAILABLE`) y procedencia **por campo**. |
| **D / F3** | Titulux declaraba `[Riesgo · Alta]` (severidad fija en código) para una amenaza **Baja** que el capítulo 10 puntuaba como MEDIO | Contrato único `risk_severity` (regla `RSK-SEV-1 v1.0.0`): la severidad se decide UNA vez desde el nivel declarado y la consumen Titulux, Hallazgos, Score y Resumen. Los pesos del score hidrológico viven en la misma tabla. Un nivel no tabulado **no** se degrada a "sin afectación": la componente se declara no calificable. |
| **E / F4** | Estrato UNRESOLVED → valoración bloqueada | Investigación de fuentes oficiales: la capa de estratificación **respondió** al punto geocodificado de la dirección oficial (estrato **4**), y se añadió una segunda vía determinista: la **manzana oficial del número predial** (prefijo de 17 dígitos, único, corroborado contra la capa catastral de manzanas y contra el registro de Dirección de la dirección exacta). Sin default, sin inferencia por barrio y sin copiar el histórico. |
| **F** | `methodology_version = null` con una tasa autorizable | `market_methodology_id` + `market_methodology_version` (**`lonja_baq_metodologia@0.1-codiseno`**, sha256 del YAML real) viajan de `MarketSectorResolution` → `MarketContext` → valoración → **manifest** → **receipt**; el gate bloquea una tasa sin id/versión trazable. |
| **G / F5** | `VERIFIED_UNIT_IDENTITY` con `direccion_raw='Pendiente de verificacion'`, `torre/apartamento/unidad=None` | Función pura `unidad_inmobiliaria.identidad_direccion()` promueve la dirección del registro oficial al modelo canónico (`raw`, `base`, `normalizada`, `torre=8`, `apartamento=430`, `unidad="TO 8 AP 430"`, procedencia `OFFICIAL_ADOPTION_REGISTRY`, valor previo conservado). Además el analizador legal **ya no trunca** la dirección del CTL (`.{4,60}` → `.{4,140}`, que destruía la unidad) y el capítulo 01 imprime la dirección canónica con su fuente y conserva la placa registral como evidencia aparte. |
| **H / F7** | "URBANIZADORA MARVAL S.A.S." → "URBANIZADORA MARVAL S" | El patrón conserva los puntos y los saltos de línea; y el constructor se toma del **enajenante de la anotación de adquisición vigente** (anotación 006, compraventa 22-01-2024), no de la primera mención del documento — con el CTL real la primera mención es el nombre **anterior** de la compañía ("URBANIZADORA MARIN VALENCIA S.A.", anotaciones 001–004). Resultado: **URBANIZADORA MARVAL S.A.S.** con `constructor_source=ANOTACION_ADQUISICION_VIGENTE`. |
| **I / F8** | 8.2 imprimía a la vez "SIN ZONA DE AMENAZA VOLCANICA CARTOGRAFIADA" y "H-VOL | Amenaza volcanica BAJA" | Un único `VolcanicRiskResult` con `estado` ∈ `HAZARD_MAPPED` / `LOW_HAZARD` / `NO_INTERSECTION` / `NO_COVERAGE` / `SOURCE_UNAVAILABLE` gobierna la tabla 8.2, el hallazgo y el receipt (`texto_volcanico()` es el único productor de redacción). `nivel` ya no se fija en "BAJO" cuando el servicio responde sin intersección. |
| **J** | Matrices de QA con hechos reconstruidos a mano (`condicion_juridica` incluida) | `golden_matrices_03i1.py` deriva **todos** los facts del estado observado/manifest/texto del PDF y audita el hardcodeo; para 6.1 se observa el valor REAL que consumió el render (`dictamen_data.get_catastral_dt`). Resultado: 28 facts, **0 hardcodeados**. |
| **F12** (nuevo) | La corrida real destapó que 6.3 afirmaba "capa de construcción consultada **sin edificación registrada** en el punto" y aplicaba "la norma para desarrollo nuevo" — para un apartamento en propiedad horizontal que el propio dictamen identifica | `_texto_pisos_construidos()` y `_confrontacion()` declaran "**no devolvió registro en el punto** (no se afirma ausencia de edificación)"; estado interno renombrado a `sin_registro_construccion`. Una respuesta sin features NO prueba que no exista edificación: el punto del geocodificador puede caer en la vía. |

## Verificación

- **Suite offline: 596 passed, 0 failed, 11 deselected** (556 previos + 40 nuevos en
  `tests/test_remediacion_03i1.py`). `compileall` limpio.
- **Cross-chapter: 0 contradicciones / 11 checks.**
- **Provenance: 28 facts · 0 hardcodeados.**
- **§K: 18/18 criterios en PASS** (`scripts/golden_coherence_03i1.py`).
- **Revisión página por página: 0/16 páginas con banderas**
  (`GOLDEN_PAGE_REVIEW.md` + 16 páginas rasterizadas en `paginas/`).

## Tests actualizados (doctrina, no regresión)

| Test | Por qué cambió |
|---|---|
| `test_riesgo_volcanico.py::test_punto_sin_zona_cartografiada` | Fijaba `nivel="BAJO"` para una respuesta SIN intersección: era la fuente de la contradicción F8. |
| `test_coherencia_bogota.py::test_planes_parciales_med_bog_no_afirmados` | Exigía que Barranquilla mantuviera "SIN AFECTACION" en Planes Parciales sin haber consultado esa capa. Ahora las tres ciudades declaran NO EVALUADO. |
| `test_remediacion_03h2.py`, `test_edificabilidad.py`, `test_remediacion_03h2a.py` | Afirmaban "sin edificación registrada" para `NO_MATCH` (defecto F12). La distinción con `SOURCE_UNAVAILABLE` se conserva, sin afirmar ausencia de edificación. |

## Insumo

El CTL original del caso (`certificado64640614546464261189306228pdf.pdf`, 5 páginas,
sha256 `4493da88f4231a6b…`) es el binario de entrada de la corrida; queda copiado en
`docs/forensics/040-646406/golden_03i1/inputs/CTL_040-646406_ORIGINAL.pdf`.
La corrida se ejecutó con la slice de 03I.1 aplicada en el árbol de trabajo sobre el
commit `7a49762`; el manifest registra ambos (SHA del HEAD + sha256 del diff del árbol).

## Garantías

- Cero cambios de fórmulas M1/M2/M3, de parámetros de mercado, de umbrales y de
  esquemas de sanciones.
- Ningún valor Golden se hardcodeó: `Consolidación (Nivel 2)`, altura 11, estrato 4 y
  la tasa de `$6.800.000/m²` salen de las fuentes (capa oficial de planeación,
  estratificación oficial, tabla metodológica de la Lonja). La coincidencia con el
  dictamen histórico es consecuencia de la fuente, no de copiar el histórico.
- La valoración se emite porque el gate se abre con fuentes oficiales; si el estrato
  no hubiera resuelto, habría seguido bloqueada (resultado igualmente válido).

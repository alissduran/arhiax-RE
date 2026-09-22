# GOLDEN_ACCEPTANCE_REPORT — 040-646406 (03I)

Ejecución REAL del producto (sin monkeypatch, sin fixtures de fuente, sin
inyección de hechos derivados) + revisión capítulo por capítulo.

- **Commit evaluado**: `acc8a9493a1cfe9dace5d638fb3bf9a0a74cf29f` (03S.1C), impreso en el pie
  del propio PDF y verificado con `git rev-parse HEAD`; el árbol de trabajo **no tenía
  cambios de código de producto** durante la corrida (solo artefactos 03I sin rastrear).
- **Ejecución**: 2026-09-22T14:40:45Z (manifest). **PDF evaluado**:
  `docs/forensics/040-646406/golden_03i/ARHIAX_Dictamen_040-646406_03I.pdf`
  (14 páginas, 288 966 B, sha256 `4285177665456a92b6023aef75225da7bf3b716a6f11479a4b43e3176dee4d82`,
  coincidente con `outputs.pdf_sha256` del manifest).
- **Manifest**: `GOLDEN_EXECUTION_MANIFEST.json` · **estado interno**: `GOLDEN_INTERNAL_STATE.json`
  · **texto del PDF**: `GOLDEN_PDF_TEXT.txt`.

---

## 1. Qué se ejecutó exactamente

| Aspecto | Detalle |
|---|---|
| Punto de entrada | `pdf_compiler.compile_pdf` (el mismo del endpoint de generación) |
| Entrada CTL | texto real saneado del certificado **040-646406** disponible en el entorno, materializado como PDF y analizado por el `legal_analyzer` REAL |
| Área registrada | **58.75 m²**, extraída por el camino del producto (`index.extraer_datos_de_pdf`), no tecleada |
| Identidad | resuelta por el **registro oficial de adopción** (Anexo 1 · Resolución GGCD 003) |
| Dirección/unidad | `Transversal 43 100 50 TO 8 AP 430` **del registro oficial** (no tecleada) |
| Barrio / estrato / tratamiento / altura | consultados EN VIVO (POT Alcaldía de Barranquilla) |
| Catastro | consultado EN VIVO (`miciudad.barranquilla.gov.co`) |
| Geocoder | Nominatim EN VIVO |
| POI | Overpass/OSM EN VIVO (4 categorías) |
| Screening | UN / OFAC SDN / UKSL **en vivo** (descarga real en la primera corrida; `CACHED_FRESH` en la evaluada) |
| Instrumentación | **solo** un observador de lectura sobre `consistency.ejecutar_gate`; 0 sustituciones de fuente |

**Limitación declarada del insumo**: el CTL disponible en el entorno es una
**copia parcial saneada** (tiene folio, código catastral, NUPRE, área privada,
titulares y anotaciones 006–008, pero **no** el bloque `DIRECCION DEL INMUEBLE`
ni el NIT del constructor). El PDF original está fuera del workspace. Esto explica
parte de las degradaciones observadas (dirección canónica interna y NIT del
constructor).

**Fuentes no disponibles en esta corrida**: capa 500 del catastro de Barranquilla
(`servicio sin respuesta` en las consultas exacta y por prefijo) y capa 310
(construcción). La capa de **estratificación respondió sin features** en el punto
geocodificado.

### 1.1 Nota de trazabilidad de los binarios

`ARHIAX_Dictamen_040-646406_03I.pdf` e `inputs/CTL_040-646406.pdf` **no se
rastrean en git**: la regla `.gitignore:20` (`*.pdf`) del repositorio ignora todos
los PDF (no hay ningún `.pdf` versionado en el proyecto). La trazabilidad se
mantiene porque (a) el `sha256` de cada uno está registrado en
`GOLDEN_EXECUTION_MANIFEST.json`, (b) el texto completo del dictamen está en
`GOLDEN_PDF_TEXT.txt`, y (c) ambos se regeneran ejecutando
`python scripts/golden_run_03i.py` a partir de `inputs/CTL_040-646406.txt`
(sí versionado, sha256 `3f30427f3e1728e30fb35689f4cf21f0455f23b185cb2ab09abd7d8076cd2c9c`).

## 2. Resultado por requisito (§1–§19)

| § | Requisito | Resultado | Evidencia |
|---|---|---|---|
| 1 | Ejecución real sin sustituciones | **PASS** | manifest `qa_instrumentation` |
| 2 | Execution manifest | **PASS** | `GOLDEN_EXECUTION_MANIFEST.json` (versiones, snapshots, hashes) |
| 3 | Identidad: `identity_authorized=True`, `resolution_confidence=VERIFIED_UNIT_IDENTITY`, dirección con unidad | **PASS con reserva** | `MATCH_EXACT`/`VERIFIED_UNIT_IDENTITY` por `official_adoption_registry`; el PDF imprime `TV 43 # 100 - 50 TO 8 AP 430`; **pero** el modelo canónico interno deja `direccion_raw='Pendiente de verificacion'` y `torre/apartamento/unidad = None` → F5 |
| 4 | Cross-identity (FMI ↔ predial ↔ NUPRE ↔ dirección ↔ unidad) | **PASS** | los tres identificadores coinciden exactamente con el registro oficial (`EXACT_3`); sin conflicto → no se bloquea por identidad |
| 5 | 6.1 datos catastrales | **PARCIAL** | área 58.75 ✓ · barrio Miramar ✓ · NUPRE ✓ · código ✓ · condición PH ✓ (inferida del CTL) · **destino PENDIENTE** (capa 500 sin respuesta) · **estrato PENDIENTE** (capa con 0 features) · tipo de construcción PENDIENTE. Prohibido "no aplica (uso no residencial)": **ausente** ✓ |
| 6 | 6.2 contexto territorial con el mismo OfficialUrbanContext | **FAIL** | barrio/localidad/pieza desde la capa oficial; pero el **resumen POT imprime un texto fijo** que contradice la tabla (F2) |
| 7 | 6.3 edificabilidad: valores de la fuente + ambigüedad + construidos | **PASS** | la capa viva devuelve **Desarrollo (Bajo), altura 8** → el dictamen muestra "Hasta 8 pisos"; no se forzó "Consolidación/Nivel 2/11"; pisos construidos = `SOURCE_UNAVAILABLE` (no "posible lote") ✓ |
| 8 | Market context: cadena real | **PARCIAL** | barrio Miramar `VERIFIED_OFFICIAL` → sector **Miramar** `EXACT` → `value_m2 = 6.800.000` (fuente: "Precio verificado en la constructora… Q3-2026 + Lonja BAQ referencial") ✓; **bloqueado** por `estrato no verificado` (F4) |
| 9 | Gate de valoración | **PASS** | `identity_authorized=True`, `market_context_authorized=False` → no se emite valoración; el MarketContext es la única autoridad de la tasa |
| 10 | Valuation output | **NO EMITIDO (declarado)** | sin `6.800.000` ni `399.500.000` en el PDF; motivo impreso "valoración no autorizada (identidad o contexto de mercado insuficiente)" |
| 11 | Independencia de métodos | **documentado** | ver §4 de este informe (M1/M3 son transformaciones del MISMO `value_m2`; M2 mezcla costo + 30 % de la tasa) |
| 12 | Carga económica sin `$0` | **PASS** | no aparece "$ 0" en el PDF; la carga no estimable no se imprime como cero |
| 13 | Costo del avalúo profesional | **PASS (NEEDS_PRODUCT_SOURCE)** | el dictamen no imprime ninguna tarifa; no confunde valor del inmueble con costo del servicio |
| 14 | POI: 4 categorías con fuente real | **PASS** | `Salud AVAILABLE (3); Educación AVAILABLE (3); Comercio AVAILABLE (3); Recreación AVAILABLE (3)` (Overpass real) |
| 15 | Riesgo/geo coherente | **FAIL (medio)** | amenaza "baja" con `severidad: alta` (F3) |
| 16 | Set canónico único | **PASS con nota** | 3 sujetos (`DURAN BACCA ALISSON` natural CC · `BANCO DE BOGOTÁ S.A.` jurídica N/D · `URBANIZADORA MARVAL S` jurídica N/D), mismos en 05/09/16.b; el nombre del constructor va truncado (F7) y el NIT del banco no está en el CTL disponible |
| 17 | Screening live/cache honesto | **PASS** | snapshots `CACHED_FRESH` (no se declara "en vivo"); primera corrida descargó en vivo. ONU 1011 · OFAC SDN 19 393 · UKSL 6 339 registros |
| 18 | Comportamiento esperado del screening | **PASS (sin candidato)** | el candidato `MARVAL`/OFAC **no se reproduce**: el sujeto real del CTL es `URBANIZADORA MARVAL S` (sin variante "/MARVAL") → `SCREENING_COMPLETE`; no se declara MATCH/SANCTIONED/CLEAN en ningún caso |
| 19 | Evidencia 3×3 | **PASS** | 9/9 envelopes · `SEALED` · matcher `sanctions-matcher/1.1.0` · parsers `onu_xml/1.1.0`, `ofac_sdn_xml/1.1.0`, `uk_sanctions_list_xml/1.1.0` (desde el snapshot) · `subject_hash`, `screening_input_hash`, `snapshot_sha256`, `query_hash`, `content_hash`, `evidence_hash` presentes en los 9 |

## 3. Assertions automáticas sobre el texto del PDF (§24)

**Presentes**: `040-646406` ✓ · `AFT0005BOHA` ✓ · `080010103000010040001908040002` ✓ ·
`AP 430` ✓ · `TO 8` ✓ · `58.75` ✓ · `Miramar` ✓ · `Propiedad Horizontal` ✓ ·
`Desarrollo (Bajo)` ✓ · `Hasta 8 pisos` ✓.

**No presentes (y correcto, porque las fuentes no lo soportan)**: `Habitacional`
(destino no resuelto) · `Estrato 4` (estrato no resuelto) · `Consolidación (Nivel 2)`
(la capa viva devuelve Desarrollo) · `11 pisos` (idem) · `6.800.000` y `399.500.000`
(valoración no autorizada).

**Términos prohibidos**: `uso no residencial` **ausente** ✓ · `posible lote sin
edificación` **ausente** ✓ · `SAGRILAFT: CUMPLE` **ausente** ✓ · `UIAF` como
columna de screening **ausente** ✓ · `titular (persona jurídica)` **ausente** ✓.

## 4. Independencia de métodos (§11) — clasificación (sin cambiar fórmulas)

| Método | Fórmula | Clasificación |
|---|---|---|
| **M1** | `area × value_m2 × 1.02` | **Transformación del `value_m2`** del sector (un solo input de mercado) |
| **M2** | `area × (2.800.000 × factor_costos × 0.85 + 0.30 × value_m2)` | **Parcialmente independiente**: el componente de costo de reposición es un input propio; el 30 % del lote depende de la misma tasa |
| **M3** | `(canon × 0.84 × 12) / cap_rate`, con `canon = area × value_m2 × 0.00538` | **Transformación del MISMO `value_m2`** (el canon se imputa como % fijo de la tasa) |
| consolidado | `m1_base` (PH ⇒ M1 100 %); banda `×0.935 / ×1.09` | derivado de M1 |
| cap rate | tabla por estrato/tipología (`0.0485` por defecto) | input propio del motor, no de mercado |

**Advertencia**: M1 y M3 comparten el mismo input fundamental (`value_m2`), por lo
que **no son tres validaciones independientes**. Solo M2 aporta un input externo
(costo de construcción). No se modificó nada: solo se clasifica y se documenta.

## 5. Revisión página por página (§25)

| Pág. | Capítulo | Resultado | Motivo |
|---|---|---|---|
| 1 | 00 Naturaleza · 01 Identificación | **PASS** | folio/NUPRE/código/dirección con unidad (TO 8 AP 430), área 58.75, tipología PH (inferido del CTL); "coeficiente de copropiedad: N/D" (no está en el CTL parcial) |
| 2 | 02 Localización · 03 POI (inicio) | **PASS** | coordenadas con fuente; barrio oficial Miramar; comuna/localidad 02; sombras calculadas |
| 3 | 03 POI · 04 Registral | **PASS** | 4 categorías con ítems reales; anotaciones 006/007/008 del CTL |
| 4 | 05 Titulux | **FAIL** | `TIT_B01` afirma "no hay área registral ni catastral para comparar" teniendo 58.75 m² (F1); el resto de reglas (TIT_B02/B03/B04/B05) coherentes con el CTL |
| 5 | 06.1–06.3 | **FAIL/WARNING** | 6.1 honesto (PENDIENTE donde no hay fuente) pero sin destino/estrato; 6.2 con **contradicción interna** (resumen fijo vs tabla) (F2); 6.3 correcto con la fuente viva (Desarrollo/Bajo/8, construidos SOURCE_UNAVAILABLE) |
| 6 | 07 Valoración · 08 Riesgos | **PASS con avisos** | 07: estimación NO emitida con motivo; 08: tabla de capas + SGC; mención volcánica confusa (F8) |
| 7 | 09 Screening (intro + 6.1/09.1) | **PASS** | título correcto, sin UIAF, tabla por contraparte con tipo/documento/rol |
| 8 | 09.2 · 09.3 | **PASS** | procedencia por fuente (autoridad, obtención, fecha, registros, sha256, **parser**) y evidencia 9/9 sellada con versiones |
| 9 | 10 Hallazgos (H-01, H-02) | **PASS** | H-01 ALTO por hipoteca vigente (anot. 007) y H-02 MEDIO por limitación al dominio / afectación a vivienda familiar (anot. 008), cada uno con fuente, lenguaje claro, implicación operacional y acción sugerida; ambos se apoyan en anotaciones reales del CTL |
| 10 | 10 Hallazgos (H-GEO) · 11 Resumen | **PASS con defecto (medio)** | 3 hallazgos en total (1 ALTO / 2 MEDIO / 0 INFORMATIVO, coherente con la tabla). Defecto: **H-GEO declara `severidad alta`** para una amenaza que el propio texto califica de **Baja** (F3) |
| 11 | 12 Score · 13 Estructurabilidad · Carga económica | **PASS** | Registral 46 · Jurídico 100 · Hidrológico 95 · Catastral 95 → **integrado 55 BLOQUEADO** (topeado por hallazgo ALTO, declarado en el texto); Catastral resta −5 por "valor referencial no calculado" en vez de imprimir 0; estructurabilidad **BLOQUEADA (ROJO)** con condiciones precedentes explícitas |
| 11 | 14–16 Declaración de alcance | **PASS** | capa catastral "NO DISPONIBLE" declarada; screening "ejecutado · cobertura completa · evidencia 9/9 · cadena SEALED" |
| 12 | 16.b Receipts · 17 Sello | **PASS** | versiones, identidad `MATCH_EXACT`, POI por categoría, screening con matcher/parsers |
| 13–14 | Anexo A + página Titulux | **PASS** | nota geodésica; marca Titulux con fuentes reales |

## 6. Comparación histórica (§26)

Contra `ARHIAX_Dictamen_040_646406_NAPOLI_v6_final.pdf` (11 págs., el artefacto
histórico más completo disponible en el repo; **no existe** un archivo rotulado
"Dictus 17" en el repositorio, se usa el más reciente).

| Hecho | Histórico (v6_final) | 03I (real) | Clasificación |
|---|---|---|---|
| folio | 040-646406 | 040-646406 | — |
| código / NUPRE | ausentes (UNKNOWN) | presentes desde el CTL | **EXPECTED_RECOVERY** |
| dirección | "TORRE 8 ETAPA 3", sin AP 430 | "TV 43 # 100 - 50 TO 8 AP 430" | **EXPECTED_RECOVERY** |
| área | 58,75 m² | 58.75 m² | — |
| destino económico | HABITACIONAL (GIS layer 5) | PENDIENTE | **EXPECTED_HONEST_DEGRADATION** (capa 500 sin respuesta hoy) + DATA_SOURCE_CHANGE |
| condición | PH | PH (inferido del CTL) | DATA_SOURCE_CHANGE (fuente distinta, mismo hecho) |
| barrio | ausente | Miramar (capa oficial viva) | **EXPECTED_RECOVERY** |
| estrato | ausente | PENDIENTE (capa sin features) | degradación honesta |
| tratamiento | "CONSOLIDACION -- niveles 1B, 2 y especial" (texto fijo) | **Desarrollo (Bajo)** (polígono real) + resumen fijo contradictorio | **DATA_SOURCE_CHANGE** + defecto de presentación (F2) |
| altura | "sujeta a ficha normativa" | **Hasta 8 pisos** (capa viva) | **EXPECTED_RECOVERY** |
| valor consolidado | $ 407.800.000 | **no emitido** (gate) | **EXPECTED_HONEST_DEGRADATION** (gate 03H fail-closed; el histórico usaba el fallback por estrato) |
| acreedor | BANCO DE BOGOTÁ S.A. (NIT 860.002.964-4) | BANCO DE BOGOTÁ S.A. (N/D) | DATA_SOURCE_CHANGE (el CTL disponible no trae el NIT) |
| constructor | URBANIZADORA MARVAL S.A.S. (NIT 830.012.053-3) | URBANIZADORA MARVAL S (N/D) | **REGRESSION (BAJA)**: truncamiento del nombre por regex (F7) |
| screening | ausente | sección 09 completa, 9/9 evidencia sellada | **EXPECTED_RECOVERY** |
| POI | tabla sin estado por categoría | 4 categorías con estado real | **EXPECTED_RECOVERY** |

No se restauró nada por el hecho de existir antes (ni el valor, ni el estrato, ni
"Consolidación/Nivel 2/11").

## 7. Findings residuales priorizados (§28.F)

| ID | Sev. | Hallazgo | Causa (código) | Impacto | Acción sugerida |
|---|---|---|---|---|---|
| **F1** | ALTA | `TIT_B01` afirma "no hay área registral ni catastral" con 58.75 m² presente | `arhia_title/rules.py::identidad_inmueble` (rama final cuando falta UNA de las dos áreas) | Contradicción con 6.1 y hallazgo falso de severidad media | Distinguir "falta área catastral" de "faltan ambas" |
| **F2** | ALTA | Resumen POT de 6.2 imprime "CONSOLIDACION / DESARROLLO (Según polígono POT)" fijo mientras la tabla/6.3 muestran **Desarrollo (Bajo) 8** | `dictamen_data.get_pot_summary_dt` (cadena fija Barranquilla, línea ~815) | Contradicción dentro del mismo capítulo; valor no derivado de la fuente | Construir el resumen desde el `OfficialUrbanContext` |
| **F3** | MEDIA | Amenaza **baja** con `severidad: alta` | `arhia_title/rules.py::amenazas_pot` (severidad fija "alta") | Severidad no proporcional al hecho (§15) | Derivar severidad del nivel (baja → media/baja) |
| **F4** | ALTA (operativa) | Sin valoración: `estrato no verificado` → `market_context_ready=False` | capa de estratificación devolvió **0 features** en el punto (fuente) | No se emite valor referencial pese a sector `EXACT` 6.8 M | Fuente alterna de estrato (manzana/ficha catastral) o resolución por manzana |
| **F5** | MEDIA | Dirección/unidad no llegan al modelo canónico (`direccion_raw='Pendiente de verificacion'`, `unidad=None`) aunque el registro oficial usado para la identidad sí las trae | `pdf_compiler` (03G.1) no promueve la dirección del registro de adopción al canónico | Dos fuentes para el mismo hecho; el PDF imprime la buena por otra vía | Promover la dirección del registro oficial al modelo canónico |
| **F6** | MEDIA | Capa 500 (catastro BAQ) `servicio sin respuesta` (exacta y prefijo) | servicio externo | Sin destino económico ni área catastral (arrastra F1) | Reintentos/verificación del servicio; declararlo (ya se declara) |
| **F7** | BAJA | Nombre del constructor truncado: "URBANIZADORA MARVAL S" (de "S.A.S.") | `legal_analyzer` regex `{3,30}` corta en los puntos | Nombre incompleto en ficha y screening | Aceptar puntos en el patrón |
| **F8** | BAJA | 8.2 dice "sin zona de amenaza volcánica cartografiada" y a la vez "zona de amenaza baja" | `zonas=0` vs clasificación SGC BAJO | Confusión de lectura | Unificar la frase |
| **F9** | INFO | El CTL del entorno es copia parcial (sin bloque DIRECCION ni NIT constructor) | PDF original fuera del workspace | Limita la fidelidad del insumo | Disponer el CTL completo para la corrida final |
| **F10** | INFO | El candidato `MARVAL`/OFAC no se reproduce con datos reales | el sujeto real es "URBANIZADORA MARVAL S" | Ninguno: `SCREENING_COMPLETE` honesto | — |
| **F11** | INFO | Costo del avalúo profesional | `appraisal_cost.py` = `NOT_FOUND` | Sin cifra impresa (correcto) | Definir regla de producto (`NEEDS_PRODUCT_SOURCE`) |

## 8. Veredicto

**03I — GOLDEN ACCEPTED WITH NON-BLOCKING FINDINGS**

Razones: la ejecución es **real, trazable y reproducible** (manifest + evidencia
9/9 sellada con versiones); la identidad se resuelve por fuente oficial
(`VERIFIED_UNIT_IDENTITY`) y el dictamen **no inventa** ningún dato: donde la
fuente no respondió (destino, estrato, pisos construidos, área catastral) lo
declara, y donde el riesgo era de inventar valor (estrato) **bloquea la
valoración**. Los hallazgos F1, F2 y F3 son contradicciones internas de
presentación/lógica que no afectan la validez de la identidad ni de la evidencia;
F4 es una brecha de **fuente** (estrato) que impide emitir el valor.

Ninguno de los hallazgos se corrigió en este paso (§27): la corrida es
diagnóstica.

**No se inició SLICE-002.**

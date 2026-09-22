# GOLDEN_ACCEPTANCE_REPORT — 03I.1 (040-646406)

**Veredicto: `03I.1 — DICTUS V1 PRODUCT COHERENCE ACCEPTED`**

Corrida REAL del producto con el **CTL original como binario de entrada**, después
de cerrar los defectos de coherencia de 03I. Sin mocks, sin fixtures de fuente y sin
sustituciones; la única instrumentación son **observadores de solo lectura** sobre
funciones del producto.

- **Commit del repositorio durante la corrida**: `7a49762` (03I).
- **Slice aplicada**: 03I.1 en el árbol de trabajo. El manifest registra **ambas**
  identidades: `commit_sha` (HEAD) y `arbol_de_trabajo` (sha256 del `git diff HEAD`
  `4b03ee077ac07c5b…`, 35 archivos). El pie del PDF imprime `commit 7a49762f`.
- **PDF**: `ARHIAX_Dictamen_040-646406_03I1.pdf` · 16 páginas · sha256
  `f7dfe003a3d66800a3cf9aeb5cb686142673b141706e1377046bff5a25268c72`.
- **Insumo**: `certificado64640614546464261189306228pdf.pdf` (5 páginas, 124 345 B,
  sha256 `4493da88f4231a6b…`), copiado a `inputs/CTL_040-646406_ORIGINAL.pdf`.

## 1. Resultado de la ejecución real

| Hecho | Valor observado | Fuente |
|---|---|---|
| Identidad | `MATCH_EXACT` · `VERIFIED_UNIT_IDENTITY` · `identity_verified=True` | registro oficial de adopción catastral (Anexo 1 · Res. GGCD 003) |
| Dirección canónica | `Transversal 43 100 50 TO 8 AP 430` · torre `8` · ap `430` · unidad `TO 8 AP 430` | registro oficial de adopción, promovida al modelo canónico |
| Folio / NUPRE / predial | `040-646406` · `AFT0005BOHA` · `080010103000010040001908040002` | CTL (analizador real) |
| Área registral | **58.75 m²** | `index.extraer_datos_de_pdf` (camino del producto) |
| Barrio / localidad | `Miramar` (`VERIFIED_OFFICIAL`) · `02` | capa oficial de unidades administrativas (en vivo) |
| **Estrato** | **`4`** (`VERIFIED_OFFICIAL`) | capa de estratificación oficial, punto geocodificado de la dirección oficial |
| Tratamiento / tipo / altura | **`Consolidación` (`Nivel 2`) · hasta 11 pisos** | capa oficial de planeación (point-in-polygon, en vivo) |
| Procedencia urbana | `MIXED` (barrio/estrato/localidad/pieza/tratamiento/altura EN VIVO · 5 capas de riesgo EMPAQUETADAS) | `UrbanSourceSummary` (por campo) |
| Sector / tasa | `Miramar` · `EXACT` · `$6.800.000/m²` | metodología Lonja BAQ |
| Metodología | `lonja_baq_metodologia@0.1-codiseno` · sha256 `4ccd5832eacf3117…` | YAML real de la Lonja |
| Gate de mercado | `ready=True`, sin bloqueantes | `MarketContext` + gate de metodología |
| Valoración | **autorizada** · consolidado `$399.500.000` (banda `373.532.500 – 435.455.000`) | resultado matemático real del motor (m1 PH) |
| Riesgo volcánico | `NO_COVERAGE` · nivel `NO EVALUADO` | SGC (mapa oficial, consulta en vivo) |
| POI | Salud `AVAILABLE` (3) · Educación `AVAILABLE` (2) · Comercio `NO_MATCH` · Recreación `NO_MATCH` · intentadas `OSM_OVERPASS, PHOTON_OSM` · exitosa `PHOTON_OSM` | Overpass (HTTP 504) + Photon |
| Screening | `SCREENING_COMPLETE` · cobertura completa · evidencia **9/9** · cadena `SEALED` · `sanctions-matcher/1.1.0` | fuentes ONU/OFAC/UKSL versionadas |
| Constructor / enajenante | `URBANIZADORA MARVAL S.A.S.` (`ANOTACION_ADQUISICION_VIGENTE`) | anotación 006 (compraventa 22-01-2024) del CTL |

## 2. Cierre de los defectos de 03I

| Ref | Defecto 03I | Estado 03I.1 | Evidencia |
|---|---|---|---|
| F1 | `TIT_B01`: "no hay área registral ni catastral" con 58.75 m² | **CERRADO** | el PDF muestra `Contraste REGISTRAL_ONLY: área registral disponible (58.75 m²). Área catastral no disponible…`; la negación falsa desapareció |
| F2 | 6.2 con "CONSOLIDACION / DESARROLLO" fijo y "Fuente: empaquetados (sin consulta en vivo)" | **CERRADO** | 6.2 (tabla y resumen) y 6.3 muestran el **mismo** objeto oficial; la fila de fuente declara `MIXED` con procedencia por campo |
| F3 | Titulux `[Riesgo · Alta]` vs Hallazgo MEDIO para la misma amenaza Baja | **CERRADO** | severidad única `RSK-SEV-1 v1.0.0`: Titulux `media` = H-GEO `MEDIO`, y la regla viaja impresa en la implicación y en el score |
| F4 | Estrato UNRESOLVED → valoración bloqueada | **CERRADO por fuente oficial** | estrato `4` `VERIFIED_OFFICIAL`; se añadió además la vía determinista por **manzana del número predial** (prefijo único de 17 dígitos, corroborado) como segunda línea |
| F5 | `direccion_raw='Pendiente de verificacion'`, `unidad=None` | **CERRADO** | dirección oficial promovida al modelo canónico con procedencia, impresa en 01 con su fuente; la placa registral del CTL se conserva aparte |
| F7 | `URBANIZADORA MARVAL S` (truncado) | **CERRADO** | `URBANIZADORA MARVAL S.A.S.` completo, tomado del enajenante de la adquisición vigente (con el CTL real la primera mención es el nombre anterior de la compañía) |
| F8 | 8.2 afirmaba "sin zona cartografiada" y "amenaza BAJA" a la vez | **CERRADO** | estado único `NO_COVERAGE`; un solo productor de texto para tabla, hallazgo y receipt |
| F9 | CTL del entorno era copia parcial saneada | **CERRADO** | la corrida usa el **binario original** (`input_type=ORIGINAL_BINARY`) |
| F10 | Candidato MARVAL no se reproducía | **sin cambio (correcto)** | outcome real: los 3 sujetos `NO_MATCH`; no se declara limpieza ni coincidencia |
| F11 | Costo del avalúo profesional | **abierto** (`NEEDS_PRODUCT_SOURCE`) | no se imprime ninguna tarifa |
| F6 | Capa 500 catastro BAQ | **confirmado distinto**: el servicio responde `404 Layer not found` (no un timeout) | sin destino económico ni área catastral (arrastra F1) |
| **F12** (nuevo) | 6.3 afirmaba "capa de construcción consultada **sin edificación registrada**" y aplicaba "norma para desarrollo nuevo" en un apartamento PH | **CERRADO** | ahora declara "no devolvió registro en el punto (no se afirma ausencia de edificación)" |
| **F13** (nuevo) | El capítulo 17 rotulaba "HASH SHA-256" el sello de ejecución, indistinguible del hash del archivo | **CERRADO** | el sello declara su alcance y el compilador imprime ambos (sello `79cee62c…` y archivo `f7dfe003…`, coincidente con el manifest) |

## 3. Puertas finales (§L)

| Puerta | Resultado |
|---|---|
| Cross-chapter matrix | **0 contradicciones / 12 checks** |
| Provenance matrix | **28 facts · 0 hardcodeados** |
| §K lista de coherencia | **19/19 criterios en PASS** (`golden_coherence_03i1.py`) |
| `compileall api scripts tests` | limpio |
| pytest offline | **596 passed, 0 failed, 11 deselected** |
| Revisión página por página | **0/16 páginas con banderas** (secciones, pies versionados y numerados, sin páginas vacías ni secciones fuera de orden) |

Las 16 páginas quedan rasterizadas en `paginas/pag_NN.png` para inspección humana.
La revisión automática es **textual y estructural**: el modelo de esta sesión no
acepta entrada de imágenes, por lo que no se afirma haber inspeccionado el render.

## 4. Comparación con el dictamen histórico

| Hecho | Histórico (`NAPOLI_v6_final`) | 03I.1 (real) | Clasificación |
|---|---|---|---|
| Área | 58,75 m² | 58.75 m² | — |
| Barrio / sector oficial | ausente | `Miramar` (capa oficial viva) | **EXPECTED_RECOVERY** |
| Estrato | ausente | `4` (estratificación oficial) | **EXPECTED_RECOVERY** |
| Tratamiento / niveles | "CONSOLIDACION — niveles 1B, 2 y especial" (texto fijo) | `Consolidación (Nivel 2)` + altura 11, desde la capa oficial del polígono | **EXPECTED_RECOVERY** (mismo hecho, ahora con fuente) |
| Altura | "sujeta a ficha normativa" | hasta 11 pisos (capa oficial) | **EXPECTED_RECOVERY** |
| Dirección | "TORRE 8 ETAPA 3" | `Transversal 43 100 50 TO 8 AP 430` (registro oficial) + placa registral del CTL | **EXPECTED_RECOVERY** |
| Valor comercial | `$407.800.000` | `$399.500.000` (banda 373.5–435.5 M) | **DATA_SOURCE_CHANGE**: el histórico no declaraba la tasa ni la metodología; ahora la tasa sale de la tabla metodológica de la Lonja (`Miramar`, `$6.8M/m²`) y el consolidado es el resultado del método principal PH (m1 base × área) |
| Constructor | `URBANIZADORA MARVAL S.A.S. (NIT 830.012.053-3)` | `URBANIZADORA MARVAL S.A.S.` (sin NIT: el CTL declara `83001205533` en la anotación 006 y `8300120533` en las anteriores) | **DATA_SOURCE_CHANGE** (el certificado trae dos NIT distintos; no se imprime ninguno) |
| Acreedor | `BANCO DE BOGOTÁ S.A. (NIT 860.002.964-4)` | `BANCO DE BOGOTA S.A.NIT# 8600029644` | **EXPECTED_RECOVERY** |
| Screening de contrapartes | ausente | sección 09 completa con evidencia 9/9 sellada | **EXPECTED_RECOVERY** |
| POI | tabla sin estado por categoría | 4 categorías con estado real y fuente por ítem | **EXPECTED_RECOVERY** |

Nada se restauró por el hecho de haber existido antes: los valores coincidentes
(Consolidación/Nivel 2/altura 11, estrato 4) provienen de consultas en vivo a las
capas oficiales sobre el punto geocodificado de la dirección oficial, y están
trazados campo por campo en `GOLDEN_PROVENANCE_MATRIX.json`.

Nota de trazabilidad: en la corrida de 03I el mismo predio aparecía como
`Desarrollo (Bajo)`, altura 8. La diferencia no es del motor: en 03I el punto salía
de Nominatim sobre la dirección del registro y caía fuera del polígono del predio;
en 03I.1 el geocodificador catastral oficial resolvió `TV 43 # 100 - 50` al punto
oficial `(11.006116, -74.837532)`, que sí cae en el polígono de tratamiento y en la
manzana de estratificación. Queda documentado porque es la causa de la diferencia.

## 5. Hallazgos residuales (no bloqueantes)

| ID | Sev. | Hallazgo | Acción sugerida |
|---|---|---|---|
| G1 | MEDIA | Capa 500 del catastro BAQ responde `404 Layer not found`: sin destino económico ni área catastral en la ejecución | Verificar el catálogo del servicio y usar la capa vigente (o el FeatureServer equivalente) |
| G2 | MEDIA | El CTL original declara **dos NIT** para el mismo constructor (`8300120533` y `83001205533`) y ninguno se imprime | Decidir doctrina: mostrar el NIT declarado en la anotación vigente, o no mostrarlo (hoy no se muestra) |
| G3 | BAJA | Overpass respondió `HTTP 504`; la sección 03 quedó con 3 ítems de Photon (Salud/Educación) y 2 categorías `NO_MATCH` | Reintento o espejo adicional; hoy se declara la fuente real por ítem |
| G4 | BAJA | El estrato se resolvió por punto; la vía por manzana del número predial quedó como respaldo probado pero no ejercitado en esta corrida | Forzar la vía por manzana cuando el punto no intersecte (ya implementado) y añadir prueba de integración con el caso Golden |
| G5 | INFO | Costo del avalúo profesional: `NEEDS_PRODUCT_SOURCE` | Definir la regla de producto |
| G6 | INFO | Los dos NIT/razón social podrían reconciliarse con el certificado de existencia y representación legal (documento ya presente en el caso) | Fuera del alcance de esta slice |

## 6. Garantías de la slice

- **Cero** cambios de fórmulas M1/M2/M3, de parámetros de mercado, de umbrales y del
  esquema de sanciones.
- **Ningún** valor Golden hardcodeado (auditado por script: 0 facts hardcodeados).
- **Ningún** dato histórico restaurado por el hecho de existir.
- La valoración se emite **porque** el gate se abrió con fuentes oficiales; con el
  estrato sin resolver habría continuado bloqueada (resultado igualmente válido).
- **NO se inició SLICE-002.**

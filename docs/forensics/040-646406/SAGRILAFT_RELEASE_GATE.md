# SAGRILAFT / SCREENING RELEASE GATE — 03I.2 (040-646406)

**Resultado: 10/10 puntos en PASS** sobre el código y sobre el dictamen real
generado con el CTL original.

- Verificador: `python scripts/sagrilaft_release_gate.py --pdf <dictamen.pdf>`
- Pruebas: `tests/test_release_gate_sagrilaft.py` (21 pruebas, una por punto y por
  prohibición) + `tests/test_03i2_coherencia_dictamen.py` (13 pruebas de D-1/D-2/D-3)
- Dictamen auditado: `docs/forensics/040-646406/golden_03i1/ARHIAX_Dictamen_040-646406_03I2.pdf`
- Núcleo sancionado: `sanctions-matcher/1.1.0` · `canonical-subjects/1.0.0` ·
  parsers `onu_xml/1.1.0`, `ofac_sdn_xml/1.1.0`, `uk_sanctions_list_xml/1.1.0` ·
  fuentes `UN_CONSOLIDATED`, `OFAC_SDN`, `UK_SANCTIONS_LIST`

## Política de liberación (decisión vigente)

**Marcar en producción.** Un núcleo anterior al sancionado no impide emitir el
dictamen: el PDF sale con el banderín **LEGACY / INVALID_FOR_RELEASE** y el motivo en
el capítulo 16 y en la traza 16.B, de modo que el negocio nunca se queda sin documento
y la marca impide que circule como vigente.

- La política vive en `sanctions.release_gate.POLITICA_POR_DEFECTO` (`"MARCAR"`) y hay
  una prueba que la fija: cambiarla exige decisión del producto y actualizar
  `tests/test_release_gate_sagrilaft.py`.
- El **bloqueo fail-closed** sigue disponible como override explícito con
  `ARHIAX_PERMITIR_LEGACY=0` (recomendado para entornos regulados o para probar un
  release). Con `=1` se fuerza marcar aunque la política cambiara.
- Comprobado con una **prueba de integración**: con un núcleo antiguo simulado, el PDF
  generado contiene el banderín, el motor declarado y la traza del núcleo.

## Los 10 puntos

| # | Punto | Estado | Evidencia |
|---|---|---|---|
| 1 | `NIT`, `NIT#`, `S.A.`, `S.A.S.`, `LTDA` → **nunca** `NATURAL_PERSON` | PASS | 3/3 casos → `LEGAL_ENTITY` (incluye `NIT#` y `(HOY)`) |
| 2 | `BANCO DE BOGOTÁ S.A.` → `LEGAL_ENTITY` | PASS | `person_type_from` por forma societaria, con advertencia `PERSON_TYPE_INFERRED_FROM_LEGAL_FORM` |
| 3 | `DURAN BACCA ALISSON` + `CC` → `NATURAL_PERSON` | PASS | `doc=cc`; `1045718995X` conservado tal como lo declara la fuente |
| 4 | Documento presente en el CTL → el PDF no imprime `ID=N/D` sin declarar el fallo de extracción | PASS | documento extraído → `NIT 8600029644`; sin documento en la fuente → `NO DECLARADO EN LA FUENTE`; extractor que falla con señal de documento → `NO EXTRAÍDO (fallo de extracción declarado)` (advertencia `DOCUMENT_EXTRACTION_FAILED`) |
| 5 | Tipo de sujeto igual en **05 = 09 = 16** | PASS | un solo productor (`sanctions.subjects.person_type_label` / `documento_para_dictamen`) consumido por `pdf_compiler` (09 y 16) y `titulux_bridge` (05) |
| 6 | 09 y 16 consumen la **misma** `ScreeningSummary` | PASS | ambos derivan de `summary_desde_dict(screening_summary)`; el recibo 16.B se construye del mismo resumen |
| 7 | UIAF/SIREL **no** es columna de screening | PASS | `fuentes_activas=("onu","ofac","uk")`; el PDF declara «Fuentes configuradas: ONU, OFAC SDN, UKSL» y solo menciona UIAF en la nota de alcance que explica que **no** es una lista |
| 8 | Sin encabezado legacy | PASS | el capítulo es **«Screening de Contrapartes y Debida Diligencia»**; la cadena «Cumplimiento SAGRILAFT (ficha estructural…)» no existe en el código ni en el PDF |
| 9 | Sin `PENDIENTE_PLATAFORMA_EXTERNA` con `SourceOutcomes` reales | PASS | el literal no existe en el código ni aparece en el PDF; los estados por fuente son reales (`CACHED_FRESH`, cobertura, parser) |
| 10 | Núcleo anterior al sancionado → `LEGACY / INVALID_FOR_RELEASE` o bloqueo | PASS | `api/sanctions/release_gate.py` evalúa matcher, modelo de sujetos, parsers y fuentes; si algo es menor, **marca** el PDF (banderín rojo en 16 + filas en 16.B) según la política vigente, y con `ARHIAX_PERMITIR_LEGACY=0` **bloquea** la generación. Además verifica la ancestría del commit (`acc8a949`) cuando hay repositorio; con `NOT_ANCESTOR` también marca |

## Trazabilidad del núcleo en el dictamen (16.B)

El PDF imprime, del propio núcleo en ejecución: motor de screening, modelo de sujetos,
parsers con su versión, fuentes del núcleo y ancestría. Medido en la corrida auditada:
`ancestría VERIFIED · 3ac0c3a6 desciende de acc8a949`, sin marca `LEGACY`.

## Defectos reales que destapó esta corrida

La capa catastral respondió en esta corrida (antes devolvía `404 Layer not found`), y
con ella aparecieron tres defectos que **cerraban el gate de valoración** o **emitían
un hallazgo falso**:

| Ref | Defecto | Cierre |
|---|---|---|
| **D-1** | `identity_verified` solo lo fijaba el camino del registro de adopción. Con la identidad resuelta contra el catastro vivo (`MATCH_BY_NUPRE` + `VERIFIED_UNIT_IDENTITY`) el campo quedaba ausente y el gate de mercado bloqueaba por «identity_verified != True» **mientras el modelo declaraba la identidad verificada**: dos verdades en el mismo objeto | `canonical.build_canonical_property_identity` **deriva** `identity_verified` de `resolution_confidence` (la semántica normalizada única que consume el gate) |
| **D-2** | El destino económico catastral («Habitacional») se escribía como **tipología** («Uso Habitacional (Según catastro)»), tapaba la evidencia registral de propiedad horizontal y cerraba el gate por «tipología no verificada» → dictamen **sin estimación económica** | `api/tipologia.py` (función pura): un uso solo manda cuando **contradice** la PH (industrial/bodega/comercial/oficina/lote/garaje); si hay PH registral, manda esa evidencia |
| **D-3** | TIT_B01 comparaba el área privada del apartamento (**58.75 m²**) con el área catastral del **terreno** del lote (**22.05 m²**) y emitía un hallazgo **ALTO falso** de inconsistencia registral-catastral | `unidad_inmobiliaria.area_catastral_comparable()`: para una unidad PH el área de terreno no es comparable (`REGISTRAL_ONLY` declarado, no inventado). El hallazgo espurio desapareció: 1 ALTO real (hipoteca) y 2 MEDIO |

## Estado del dictamen tras los cierres

- Identidad `MATCH_EXACT` / `VERIFIED_UNIT_IDENTITY` con unidad (`TO 8 AP 430`), estrato
  `4` `VERIFIED_OFFICIAL` (por manzana oficial del número predial cuando el punto no
  cae en polígono), POT desde la capa oficial, mercado `ready=True` con metodología
  trazable y **valoración emitida** (`$399.500.000`, banda 373.5–455.5 M).
- `TIT_B01` = `REGISTRAL_ONLY` (severidad media, sin la negación falsa y sin el falso ALTO).
- Screening `SCREENING_COMPLETE`, evidencia **9/9**, cadena `SEALED`.
- Gate de coherencia §K: **19/19** · matrices: **0 contradicciones / 12 checks** y
  **28 facts / 0 hardcodeados** · suite offline: **642 passed**.

## Nota de robustez (fuentes volátiles)

Entre corridas las fuentes externas responden distinto: la capa 500 del catastro a
veces contesta y a veces no, y el geocodificador a veces cae en la manzana vecina.
El dictamen se mantiene coherente en **todas** las combinaciones observadas (registro
de adopción o catastro vivo para la identidad; punto espacial o manzana del predial
para el estrato), que es el criterio de aceptación: **coherencia, no un valor fijo**.

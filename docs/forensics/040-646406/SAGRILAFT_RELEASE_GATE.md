# SAGRILAFT / SCREENING RELEASE GATE — 03I.2 y 03I.2A (040-646406)

**Resultado: 10/10 puntos en PASS** sobre el código y sobre el dictamen real generado
con el CTL original, con la política de liberación **fail-closed por entorno** (03I.2A).

- Verificador: `python scripts/sagrilaft_release_gate.py --pdf <dictamen.pdf>`
- Pruebas: `tests/test_release_gate_sagrilaft.py`, `tests/test_03i2_coherencia_dictamen.py`
  y `tests/test_03i2a_release_fail_closed.py` (33 pruebas: fail-closed por entorno,
  clasificación A–H, sujetos 05/09/16 y vocabulario de persona jurídica)
- Dictamen auditado: `docs/forensics/040-646406/golden_03i1/ARHIAX_Dictamen_040-646406_03I2A.pdf`
- Núcleo sancionado: `sanctions-matcher/1.1.0` · `canonical-subjects/1.0.0` ·
  parsers `onu_xml/1.1.0`, `ofac_sdn_xml/1.1.0`, `uk_sanctions_list_xml/1.1.0` ·
  fuentes `UN_CONSOLIDATED`, `OFAC_SDN`, `UK_SANCTIONS_LIST`

## Política de liberación por ENTORNO (03I.2A · sustituye la política anterior)

La política **ya no es global**: «marcar en producción» dejó de ser la política general.
Se lee de `ARHIAX_ENV` con `release_env` (módulo sin dependencias) como última línea de
defensa.

| Entorno | Núcleo anterior (legacy) | Gate NO evaluable |
|---|---|---|
| `development` | **MARK** | **MARK** (`INVALID_FOR_RELEASE`) |
| `test` | **MARK** | **MARK** (`INVALID_FOR_RELEASE`) |
| `staging` | **BLOCK** | **BLOCK** |
| `production` | **BLOCK** | **BLOCK** |

Un `ARHIAX_ENV` **ausente o desconocido** se trata de forma **conservadora**: como
`production` (BLOCK), y el recibo lo registra como «asumido conservador».

- **MARK = artefacto diagnóstico.** El PDF se emite, siempre marcado
  `LEGACY / INVALID_FOR_RELEASE` o `RELEASE GATE NOT EVALUABLE / INVALID_FOR_RELEASE`.
- **BLOCK = no existe documento liberable.** `compile_pdf` lanza
  `InconsistenciaBloqueante` **antes** de construir nada y **no se escribe ningún PDF
  final**: la escritura es atómica (temporal + `os.replace`, y el temporal se elimina
  ante excepción). Un gate que falla **jamás** produce un PDF vigente.
- **Override excepcional** `ARHIAX_ALLOW_LEGACY_RELEASE=1` (alias deprecado
  `ARHIAX_PERMITIR_LEGACY`): solo convierte un BLOCK en MARK, **nunca** en
  `VALID_FOR_RELEASE`, y su uso queda registrado (`override_used` + variable).

### Contrato seguro (§2)

`evaluar_release_seguro()` es la **única** función autorizada para decidir la liberación.
Nunca lanza y nunca devuelve `None`:

```
evaluation_status : EVALUATED | EVALUATION_FAILED
release_status    : VALID_FOR_RELEASE | LEGACY_INVALID_FOR_RELEASE | GATE_EVALUATION_FAILED
policy            : MARK | BLOCK
environment, environment_declared, environment_raw, assumed_conservative,
blocking, mark, marca, override_used, override_variable, reasons,
core_versions {matcher, subject_model, parsers, sources, commit}, ancestry
```

### Recibo de liberación (16.C, §12)

Se imprime siempre con los nombres exactos: `release_gate_evaluation_status`,
`release_gate_status`, `release_gate_policy`, `environment`, `blocking`,
`override_used`, `reasons`, `matcher_version`, `subject_model_version`,
`parser_versions`, `sources`, `ancestry`. **No se registran secretos** ni variables
completas.

> La corrección ortográfica del dictamen ahora respeta los identificadores de máquina:
> antes acentuaba tokens y corrompía el registro (`GATE_EVALUATION_STATUS` →
> `GATE_EVALUATIÓN_STATUS`, `matcher_version` → `matcher_versión`). Un token pegado a
> `_` o a dígitos se imprime **verbatim**.

## Clasificación: uso ≠ régimen jurídico ≠ tipología física (§16-§21)

`api/clasificacion.py` resuelve **tres dimensiones independientes** —régimen jurídico,
uso económico y tipología física— cada una con `value/source/status`:

- **PROPIEDAD HORIZONTAL es régimen**, no uso ni tipología; un uso (comercial, oficina,
  industrial, garaje) **nunca** lo elimina.
- La **tipología física** solo se afirma con evidencia textual; con régimen PH y sin
  evidencia de la unidad se declara «Unidad en Propiedad Horizontal» (no se inventa
  «apartamento»).
- **Contradicción solo dentro de la misma dimensión**: PH registral vs NO PH catastral →
  `CONFLICT` (no se elige en silencio); PH + uso comercial **no** es contradicción.
- El gate de contexto de mercado lee **régimen/tipología**, nunca el uso (§20): un «Uso
  Comercial» declarado por sí solo **no** habilita la valoración.
- `tipologia_de_predio()` se conserva como **adapter** de compatibilidad.

## Sujetos: 05 = 09 = 16 comprobado por VALOR (§13/§14)

`sanctions.subjects.fila_sujeto_dictamen()` es el productor único de la fila del sujeto
(nombre canónico, tipo, etiqueta, documento, roles y `subject_id`). Lo consumen el
capítulo 05 (ficha + tabla de contrapartes), el capítulo 09 (tabla 09.1) y el recibo
16.B/16.C. El verificador lo comprueba **sobre el PDF emitido**: para cada contraparte,
el nombre, la etiqueta de tipo y el documento aparecen juntos en los tres capítulos.

> «MARVAL» se eliminó de `_LEGAL_TOKENS`: es la firma del caso Golden, no una forma
> jurídica. El constructor se clasifica por `URBANIZADORA`, su NIT y su forma societaria.

## Los 10 puntos

| # | Punto | Estado | Evidencia |
|---|---|---|---|
| 1 | `NIT`, `NIT#`, `S.A.`, `S.A.S.`, `LTDA` → **nunca** `NATURAL_PERSON` | PASS | 3/3 casos → `LEGAL_ENTITY` (incluye `NIT#` y `(HOY)`) |
| 2 | `BANCO DE BOGOTÁ S.A.` → `LEGAL_ENTITY` | PASS | `person_type_from` por forma societaria, con advertencia `PERSON_TYPE_INFERRED_FROM_LEGAL_FORM` |
| 3 | `DURAN BACCA ALISSON` + `CC` → `NATURAL_PERSON` | PASS | `doc=cc`; `1045718995X` conservado tal como lo declara la fuente |
| 4 | Documento presente en el CTL → el PDF no imprime `ID=N/D` sin declarar el fallo de extracción | PASS | documento extraído → `NIT 8600029644`; sin documento en la fuente → `NO DECLARADO EN LA FUENTE`; extractor que falla con señal de documento → `NO EXTRAÍDO (fallo de extracción declarado)` (advertencia `DOCUMENT_EXTRACTION_FAILED`) |
| 5 | Tipo de sujeto igual en **05 = 09 = 16** | PASS (conductual) | `fila_sujeto_dictamen` lo consumen 05 (ficha + contrapartes), 09 (tabla 09.1) y 16.B/16.C; el verificador comprueba **sobre el PDF** que nombre + etiqueta + documento aparecen juntos en los tres |
| 6 | 09 y 16 consumen la **misma** `ScreeningSummary` | PASS | el resumen se deriva UNA vez (capítulo 05) y lo consumen 09 y 16; `_screening_receipt` deriva del mismo resumen |
| 7 | UIAF/SIREL **no** es columna de screening | PASS | `fuentes_activas=("onu","ofac","uk")`; el PDF declara «Fuentes configuradas: ONU, OFAC SDN, UKSL» y solo menciona UIAF en la nota de alcance que explica que **no** es una lista |
| 8 | Sin encabezado legacy | PASS | el capítulo es **«Screening de Contrapartes y Debida Diligencia»**; la cadena «Cumplimiento SAGRILAFT (ficha estructural…)» no existe en el código ni en el PDF |
| 9 | Sin `PENDIENTE_PLATAFORMA_EXTERNA` con `SourceOutcomes` reales | PASS | el literal no existe en el código ni aparece en el PDF; los estados por fuente son reales (`CACHED_FRESH`, cobertura, parser) |
| 10 | Núcleo anterior al sancionado o gate no evaluable → bloqueo o marca según entorno | PASS | `evaluar_release_seguro()` evalúa matcher, modelo de sujetos, parsers y fuentes; **BLOCK** en staging/producción (sin PDF final), **MARK** en desarrollo/prueba, override excepcional registrado y ancestría del commit cuando hay repositorio |

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

## Corrida de aceptación 03I.2A (producción, `ARHIAX_ENV=production`)

Ejecutada con el CTL ORIGINAL y política de producción (BLOCK). Artefacto:
`golden_03i1/ARHIAX_Dictamen_040-646406_03I2A.pdf`.

| Comprobación | Resultado |
|---|---|
| Release gate (código + PDF) | **10/10 PASS** · `entorno production (declarado=True) · política BLOCK · VALID_FOR_RELEASE · ancestría VERIFIED · PDF marcado: no` |
| Coherencia §K | **19/19** |
| Matrices | **0 contradicciones / 12 checks** · **28 facts / 0 hardcodeados** |
| Clasificación | régimen `PROPIEDAD_HORIZONTAL (VERIFIED_REGISTRAL)` · uso `HABITACIONAL` · tipología `UNIDAD_EN_PROPIEDAD_HORIZONTAL` (sin evidencia de la unidad física no se inventa «apartamento») |
| Sujetos 05 = 09 = 16 | `BANCO DE BOGOTA S.A. → Jurídica → NIT 8600029644` y `DURAN BACCA ALISSON → Natural → CC 1045718995X` en los tres capítulos |
| Constructor | `URBANIZADORA MARVAL S.A.S.` → `LEGAL_ENTITY` por señal genérica (`URBANIZADORA`), **sin** el token «MARVAL» |
| Screening | `SCREENING_COMPLETE`, evidencia **9/9** |
| Suite offline | **682 passed, 0 failed, 11 deselected** |

Requisitos de entorno observados (por diseño, no defectos):

- Sin `ARHIAX_AUTH_SECRET` / `ARHIAX_ADMIN_PASSWORD`, `api/index.py` **se niega a
  importar** en producción (guarda previa de configuración de seguridad).
- Sin `ARHIAX_EVIDENCE_HMAC_KEY`, el screening **declara** `evidence_chain_status=FAILED`
  y baja a `SCREENING_PARTIAL` con el motivo explícito (no hay degradación silenciosa).
  La corrida de aceptación usó claves **locales de QA**, no credenciales reales.

## Resultado observado y hallazgo residual (no bloqueante)

En la corrida auditada la valoración **no** se emitió: `coordinates.source =
FORM_ADDRESS_GEOCODE` (`verified=False`) → `context_status =
COORDINATE_SOURCE_NOT_AUTHORIZED` → sin barrio/estrato → gate de mercado cerrado. Es el
comportamiento **fail-closed** correcto (03H.1A: una dirección de formulario puede ser
una placa alternativa y llevar a otra manzana). El mismo código, en corridas donde la
fuente autorizada responde, emite la valoración con metodología trazable.

- **H-1 (seguimiento, no bloqueante)**: cuando la identidad se resuelve contra el
  catastro vivo (`MATCH_BY_NUPRE`) sin dirección del registro de adopción, la coordenada
  del predio puede quedar etiquetada `FORM_ADDRESS_GEOCODE`, que no está en la allowlist,
  y cierra el gate de mercado. Propuesta: promover el punto del predio catastral como
  `OFFICIAL_PREDIO` cuando `predio_real` lo aporte con geometría verificada.
- El dictamen nunca inventa el valor: bloquea y lo declara.

## Nota de robustez (fuentes volátiles)

Entre corridas las fuentes externas responden distinto: la capa 500 del catastro a
veces contesta y a veces no, el geocodificador a veces cae en la manzana vecina y la
capa de estratificación a veces no tiene registro en el punto. El dictamen se mantiene
coherente y **fail-closed** en todas las combinaciones observadas (registro de adopción
o catastro vivo para la identidad; punto espacial o manzana del predial para el
estrato; con y sin valoración), que es el criterio de aceptación: **coherencia y
seguridad, no un valor fijo**.

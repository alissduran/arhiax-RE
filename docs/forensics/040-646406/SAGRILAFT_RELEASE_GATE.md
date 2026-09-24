# SAGRILAFT / SCREENING RELEASE GATE — 03I.2, 03I.2A y 03I.2B (040-646406)

**Resultado: 10/10 puntos en PASS** sobre el código y sobre el dictamen real generado
con el CTL original, con la política de liberación **fail-closed por entorno** (03I.2A)
y el **contrato de decisión validado** por el compilador (03I.2B · R1).

- Verificador: `python scripts/sagrilaft_release_gate.py --pdf <dictamen.pdf>`
- Pruebas: `tests/test_release_gate_sagrilaft.py`, `tests/test_03i2_coherencia_dictamen.py`,
  `tests/test_03i2a_release_fail_closed.py` (33 pruebas: fail-closed por entorno,
  clasificación A–H, sujetos 05/09/16 y vocabulario de persona jurídica) y
  `tests/test_03i2b_contrato_tipologia_coordenadas.py` (29 pruebas: §C contrato C1–C7,
  §F render F1–F6, §M coordenadas M1–M11, §Q liberación end-to-end Q1–Q5) y
  `tests/test_03i2ba_canonical_binding.py` (12 pruebas: §8.A–G del binding canónico,
  regresión del GUID de enlace y render del recibo)
- Dictamen auditado: `docs/forensics/040-646406/golden_03i1/ARHIAX_Dictamen_040-646406_03I2BA.pdf`
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
`parser_versions`, `sources`, `ancestry`, y desde 03I.2B también
`release_gate_contract_valid` y `release_gate_contract_problems`. **No se registran
secretos** ni variables completas.

> La corrección ortográfica del dictamen ahora respeta los identificadores de máquina:
> antes acentuaba tokens y corrompía el registro (`GATE_EVALUATION_STATUS` →
> `GATE_EVALUATIÓN_STATUS`, `matcher_version` → `matcher_versión`). Un token pegado a
> `_` o a dígitos se imprime **verbatim**.

## 03I.2B · R1 — el contrato de liberación malformado ya no puede leerse como «no bloqueante»

**Defecto.** El compilador consumía el resultado del gate con `release_gate.get("blocking")`.
Si el contrato llegaba malformado **sin lanzar** (`None`, `{}`, un string, o un dict al
que le faltaban campos), `dict.get` devolvía `None` ⇒ *falsy* ⇒ **fail-open**: el dictamen
se emitía como si el gate hubiera decidido «no bloquear». El wrapper
`evaluar_release_seguro()` cubría excepciones, no contratos incompletos.

**Cierre.** `sanctions.release_gate.validate_release_decision(result)` valida el contrato
completo y **nunca asume válido lo inválido**:

- campos obligatorios `evaluation_status`, `release_status`, `policy`, `blocking`, `mark`,
  `environment`, `reasons`; enums cerrados (`EVALUATED|EVALUATION_FAILED`,
  `VALID_FOR_RELEASE|LEGACY_INVALID_FOR_RELEASE|GATE_EVALUATION_FAILED`, `MARK|BLOCK`);
  `blocking`/`mark` booleanos; `environment` no vacío; `reasons` lista;
- coherencia interna: `VALID_FOR_RELEASE` exige `EVALUATED`, `blocking=False` y `mark=False`;
- toda violación se convierte en fallo **explícito** (`EVALUATION_FAILED` /
  `GATE_EVALUATION_FAILED`, `marca = RELEASE GATE NOT EVALUABLE / INVALID_FOR_RELEASE`),
  se aplica la **política del entorno** (BLOCK en staging/producción, MARK en dev/test) y se
  devuelve `contract_valid=False` + `contract_problems=[…]`;
- el override `ARHIAX_ALLOW_LEGACY_RELEASE=1` solo degrada BLOCK→MARK: **jamás** produce
  `VALID_FOR_RELEASE` ni borra la marca.

`api/pdf_compiler._gate_liberacion_inicial()` pasa **siempre** el resultado del wrapper por
el validador (una sola evaluación, antes de construir el dictamen). Sus dos rutas de
emergencia (gate no importable / política no disponible) también declaran
`contract_valid=False` con el motivo, y el capítulo 16 imprime el aviso
**«CONTRATO DE LIBERACION INVALIDO»** cuando corresponde. En producción un contrato inválido
**bloquea**: no se construye historia y no se escribe ningún PDF.

## 03I.2B · R2 — el render de clasificación ya no inventa el uso

**Defecto.** `clasificacion.texto_tipologia()` devolvía `"Bodega -- Uso Industrial"` de
forma **fija** para toda bodega. Con `economic_use = COMERCIAL` el dictamen afirmaba un uso
industrial que ninguna fuente declaraba: un uso **inventado** en el documento que sostiene
la due diligence.

**Cierre.** El uso se imprime **si y solo si** la fuente lo declaró
(`etiqueta_uso()` / `sufijo_uso()` derivan de la dimensión `economic_use`, con la
representación exacta de la fuente cuando existe). El nombre de la tipología física nunca
se traduce a un uso y un uso ausente nunca se rellena con el «típico»:

| Entrada | Antes | Ahora |
|---|---|---|
| BODEGA + destino `Comercial` | `Bodega -- Uso Industrial` | **`Bodega -- Uso Comercial`** |
| BODEGA sin destino | `Bodega -- Uso Industrial` | **`Bodega`** |
| LOCAL + `Comercial` | `Local` | **`Local -- Uso Comercial`** |
| OFICINA + `Oficina` | `Oficina` | **`Oficina -- Uso Oficina`** |
| GARAJE + PH | `Garaje en Propiedad Horizontal` | `Garaje en Propiedad Horizontal` (sin inventar uso) |
| APARTAMENTO/UNIDAD en PH | `… -- Propiedad Horizontal (…))` | **sin cambio** (contrato `TIPOLOGIA_PH_*` de un artefacto Golden aceptado) |

## 03I.2B · H-1 (cerrado) — la geometría oficial del predio se promueve solo con evidencia

**Defecto.** `market_context.resolve_market_location()` promovía **cualquier**
`predio_real["lat"]/["lon"]` a la fuente autorizada `OFFICIAL_PREDIO`. Un «hint»
geocodificado o un punto referencial por cercanía entraban al gate de valoración
etiquetados como geometría oficial: **procedencia escalada sin evidencia**.

**Cierre (7 criterios).** `evaluar_geometria_oficial_predio()` decide la promoción:

1. hay un predio resuelto con `lat/lon` (y no declarado `disponible=False`);
2. el **productor** declara un origen elegible (`coordenada_origen` ∈
   {`DIRECCION_OFICIAL_LIGADA_AL_PREDIO`, `GEOMETRIA_OFICIAL_PREDIO`}) — nunca se deduce;
3. **vínculo verificado** con ESE predio (`feature_id` == globalid del predio, o
   `predio_globalid` == `feature_id` / identificador oficial del predio);
4. identificadores oficiales presentes (globalid, número predial + NUPRE, o clave de enlace
   oficial declarada: `cr_predio_guid`, `globalid`, `numero_predial_nacional`, `LOTCODIGO`);
5. **procedencia completa**: `source_system`, `layer`, `feature_id`, `geometry_type`,
   `resolution_method`, `predio_globalid`;
6. método y tipo de geometría admisibles (ni geocode, ni hint, ni centroide de referencia,
   ni demo; `Point`/`Polygon`/`MultiPolygon`);
7. **cordura espacial**: coordenadas finitas, no degeneradas y dentro de la caja del
   municipio del caso (una coordenada proyectada o de otra ciudad no pasa).

Sin `eligibility`, la ubicación cae a la siguiente fuente **autorizada** y el motivo queda
declarado (`official_predio_rejected_reason`). La procedencia viaja siempre
(`coordinate_provenance` en el MarketContext, en el receipt 16.B, en el manifest y en el
estado interno del QA) y el dictamen imprime la fila
**«Ubicación de mercado (coordenada)»**. Se declara además el **alcance**: la geometría
oficial acredita el **PREDIO (lote/edificio)**, no la posición del apartamento dentro de la
edificación.

Productores que declaran el origen: `catastro_predio` (Barranquilla, punto de la capa 105
enlazado por `cr_predio_guid` = globalid del predio, con la clave verificada contra el
globalid consultado), `catastro_predio_medellin` (punto del registro catastral consultado
por código/NUPRE) y `catastro_predio_bogota` (centroide de la geometría oficial del lote por
`LOTCODIGO`). Los «hints» de las tres ciudades se declaran `HINT_NO_OFICIAL` y **no**
promueven.

## 03I.2B-A · Binding con la identidad CANÓNICA (criterio 8)

**Defecto.** H-1 verificaba que la geometría estuviera ligada **internamente** a
`predio_real`, pero no que ese predio fuera el MISMO `CanonicalPropertyIdentity` que
gobierna el Dictus. Con `canonical_identity.nupre = AFT_X` y `predio_real.nupre = AFT_Y`
—geometría impecable, procedencia completa— la coordenada podía declararse
`OFFICIAL_PREDIO`: geometría **de otro predio** etiquetada como oficial del caso.

**Regla.**

```
OFFICIAL_PREDIO = geometría oficial válida (7 criterios H-1)
                  AND predio_real COMPATIBLE con CanonicalPropertyIdentity
```

`_evaluar_binding_canonico()` compara **solo lo que ambas partes publican** y **nunca elige
en silencio**:

| Situación | Resultado |
|---|---|
| canónico NUPRE == predio/procedencia NUPRE y predial == predial | `VERIFIED` |
| NUPRE canónico ≠ NUPRE del predio | `MISMATCH` (`CANONICAL_IDENTITY_MISMATCH`) |
| número predial canónico ≠ número predial del predio | `MISMATCH` |
| `provenance.nupre` ≠ `predio_real.predio.nupre` (desacuerdo interno) | `MISMATCH` |
| el canónico no publica los identificadores que el predio declara (o al revés) | `NOT_COMPARABLE` |
| sin `canonical_identity` | `NOT_COMPARABLE` |

- **`NOT_COMPARABLE` no es `VERIFIED`** y **no promueve**: sin campos comparables no hay
  compatibilidad acreditada (fail-closed), y el motivo queda declarado.
- **Normalización honesta**: NUPRE sin espacios ni caja; número predial **solo por
  dígitos**; un `predio_globalid` que es un **GUID** de enlace **no** se compara como
  número predial (sus dígitos no son el número predial del predio — falso `MISMATCH`
  detectado por la prueba viva del Golden y corregido).
- **Espacios de nombres (§5)**: los códigos MUNICIPALES (p. ej. `LOTCODIGO` de Bogotá) se
  comparan contra la clave municipal del canónico si existe (`matricula_municipal` /
  `codigo_anterior`) y se declaran con alcance `MUNICIPAL_KEY`. Comparar un `LOTCODIGO`
  contra un número predial de 30 dígitos sería fingir una equivalencia inexistente. En
  Bogotá, mientras el canónico no declare clave municipal, la geometría del lote queda
  `NOT_COMPARABLE` (no se promueve) y la ubicación sigue resolviéndose por una fuente
  **autorizada** (`CTL_ADDRESS_GEOCODE`): no se pierde el gate, se pierde la etiqueta que
  no estaba acreditada.

**Dónde se declara (§7/§9).** `canonical_binding_status`, `canonical_binding_fields`,
`canonical_binding_scope` y `canonical_binding_detail` viajan en
`coordinate_provenance`, en el objeto de ubicación, en el recibo 16.B (**«binding canónico
VERIFIED (nupre, numero_predial)»**), en el manifest y en el estado interno del QA. Se
declaran **siempre**, incluso cuando la geometría del predio NO se promovió (un `MISMATCH`
o un `NOT_COMPARABLE` también son auditables).

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
| 10 | Núcleo anterior al sancionado o gate no evaluable → bloqueo o marca según entorno | PASS | `evaluar_release_seguro()` evalúa matcher, modelo de sujetos, parsers y fuentes, y `validate_release_decision()` **valida el contrato** (campos, enums y coherencia interna; un contrato malformado es un fallo explícito, nunca «no bloqueante»). **BLOCK** en staging/producción (sin PDF final), **MARK** en desarrollo/prueba, override excepcional registrado que nunca produce `VALID_FOR_RELEASE`, y ancestría del commit cuando hay repositorio |

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

## Corrida de aceptación 03I.2B (producción real, `ARHIAX_ENV=production`)

Ejecutada con el CTL ORIGINAL (binario, `sha256 4493da88f4231a6b…`, 124 345 B) y política de
producción (BLOCK). Artefacto:
`golden_03i1/ARHIAX_Dictamen_040-646406_03I2B.pdf`
(`sha256 0aea190b0c6d9330…`), sello de ejecución `d860b6d9758c8ad3…`.

| Comprobación | Resultado |
|---|---|
| Release gate (código + PDF) | **10/10 PASS** · `entorno production · política BLOCK · VALID_FOR_RELEASE · ancestría VERIFIED · PDF marcado: no` |
| Contrato del gate en el recibo | `release_gate_contract_valid = True` · `release_gate_contract_problems = ninguno` |
| Coherencia §K | **19/19** |
| Matrices | **0 contradicciones / 12 checks** · **28 facts / 0 hardcodeados** |
| Coordenada (H-1) | **`OFFICIAL_PREDIO` (verificada)** · `source_system=CATASTRO_MUNICIPAL_BARRANQUILLA_ARCGIS` · `layer=105 · direccion` · `feature_id=6c663607-5509-401f-b57d-384d2beeeac1` · `método=DIRECCION_OFICIAL_LIGADA_POR_GUID` · `(11.006056, -74.837570)` · sin geocodificador externo |
| Binding canónico (03I.2B-A) | **`VERIFIED`** · campos `['nupre', 'numero_predial']` · alcance `NATIONAL_IDENTIFIERS` · impreso en el recibo: «binding canónico VERIFIED (nupre, numero_predial)» |
| Alcance declarado | «geometría oficial del PREDIO (lote/edificio): NO acredita la posición del apartamento dentro de la edificación» |
| Clasificación | régimen `PROPIEDAD_HORIZONTAL (VERIFIED_REGISTRAL)` · uso `HABITACIONAL` · tipología `UNIDAD_EN_PROPIEDAD_HORIZONTAL` (la unidad física no se inventa) |
| Valoración | **CASO A: emitida** (`$399.500.000`, banda 373.5–455.5 M; `identity_authorized=True`, `market_context_authorized=True`, `VERIFIED_UNIT_IDENTITY`) |
| Sujetos 05 = 09 = 16 | `BANCO DE BOGOTA S.A. → Jurídica → NIT 8600029644` y `DURAN BACCA ALISSON → Natural → CC 1045718995X` en los tres capítulos |
| Screening | `SCREENING_COMPLETE`, evidencia **9/9**, cadena `SEALED` |
| Suite offline | **723 passed, 0 failed, 1 skipped, 11 deselected** (línea base 682 + 29 de 03I.2B + 12 de 03I.2B-A; el omitido es la prueba de binding que exige red y se ejecuta con `ARHIAX_NETWORK_TESTS=1`: **PASS**) |
| `compileall api tests scripts` | limpio |

Artefacto de esta corrida: `golden_03i1/ARHIAX_Dictamen_040-646406_03I2BA.pdf`
(`sha256 de57fe14e4fa28b3…`, sello `d1cb939e2f3ad0d0…`).

> El criterio §O se cumple por el **caso A**: con geometría oficial exacta disponible la
> valoración se emitió **usando esa geometría**. No se usó `FORM_ADDRESS_GEOCODE` mientras
> existía geometría oficial del predio; el geocodificador de direcciones dejó de ser
> necesario para abrir el gate de mercado.

## Resultado observado en 03I.2A y hallazgo residual (cerrado en 03I.2B)

En la corrida auditada de 03I.2A la valoración **no** se emitió: `coordinates.source =
FORM_ADDRESS_GEOCODE` (`verified=False`) → `context_status =
COORDINATE_SOURCE_NOT_AUTHORIZED` → sin barrio/estrato → gate de mercado cerrado. Fue el
comportamiento **fail-closed** correcto (03H.1A: una dirección de formulario puede ser una
placa alternativa y llevar a otra manzana), pero dejaba la valoración a merced del
geocodificador.

- **H-1 — CERRADO en 03I.2B.** La geometría oficial del predio se promueve como
  `OFFICIAL_PREDIO` **solo** bajo los 7 criterios de evidencia (arriba), con procedencia
  completa y alcance declarado. En la corrida de aceptación de 03I.2B la fuente autorizada
  fue la geometría oficial del predio y la valoración se emitió sin depender de la red.
- Cuando ninguna fuente autorizada responde, el dictamen **bloquea y lo declara**: nunca
  inventa la coordenada ni el valor.

## Nota de robustez (fuentes volátiles)

Entre corridas las fuentes externas responden distinto: la capa 500 del catastro a
veces contesta y a veces no, el geocodificador a veces cae en la manzana vecina y la
capa de estratificación a veces no tiene registro en el punto. El dictamen se mantiene
coherente y **fail-closed** en todas las combinaciones observadas (registro de adopción
o catastro vivo para la identidad; punto espacial o manzana del predial para el
estrato; con y sin valoración), que es el criterio de aceptación: **coherencia y
seguridad, no un valor fijo**.

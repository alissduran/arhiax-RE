# DICTUS 2.0D — EXPEDIENTE DE DECISIÓN, EVIDENCIA TRAZABLE Y MOTOR DE COMPUERTAS

**Folio:** 040-646406 · **Dictus ID:** DX-040-646406-20260928 · **Run:** cb127755-b129-4452-a5b7-cc73cd88b227
**Gramática:** `dictus-decision-grammar/1.0.0` · **Modelo maestro:** `dictus-master-manifest/1.2.0`

| Artefacto | Valor |
|---|---|
| `DICTUS_MASTER_HASH` | `d1b03c7b3f788be648a6bda3eb0fe84c475faf3ba69eae012b05d0decea93eaf` |
| Ejecutivo (6 páginas) sha256 | `b0ad1665b6f397fefe3cf58878ab8ffbfc8078bd623eff9648b6712d9be33550` |
| Técnico (17 páginas) sha256 | `cb8ef15db1fa30445efabc4dbb4e5d8a068ba35b0f8c837c55707166d04a7bca` |
| Retícula | `sin violaciones` · 80 cajas registradas |
| Completitud material | `PASS` — 41 hechos auditados, 40 impresos, **0 pérdidas**, 1 `SIN_FUENTE` declarado |
| Invariantes de la gramática | `0 incumplidas` |
| Disposición global | **PROCEDER CON CONDICIONES IDENTIFICADAS** |

## 1. Qué se construyó

La corrida dejó de producir «un documento con datos» y produce una **cadena de decisión
auditable**, donde cada eslabón es un objeto distinto y trazable:

```
FUENTE → CONSULTA → EVIDENCIA → OBSERVACIÓN → HALLAZGO → RECOMENDACIÓN
       → COMPUERTA → DISPOSICIÓN → REVISIÓN HUMANA
```

* **36 observaciones** (una por hecho observado, con estado propio), **9 hallazgos** (con
  significado, severidad, afectados, decisión y evidencia), **9 recomendaciones** (cada una
  con `evidence_refs`), **7 compuertas** y **1 disposición global explicable**.
* Todo esto vive en el **modelo maestro** y por tanto **entra al hash**: ahora también el
  bloque `decision_findings` (antes los motivos del hallazgo quedaban fuera del hash).
* El sistema **no decide por la persona**: `human_review.status = PENDIENTE` y el
  vocabulario prohibido (COMPRE / NO COMPRE / CRÉDITO APROBADO / SEGURO APROBADO /
  TÍTULO GARANTIZADO) no aparece en ningún artefacto.

## 2. Compuertas y disposición (Golden 040-646406)

| Compuerta | Decisión | Bloqueos declarados |
|---|---|---|
| `IDENTITY_GATE` | INFORMACIÓN VERIFICADA | — |
| `TITLE_GATE` | PROCEDER CON CONDICIONES | GRAVAMEN: Hipoteca (Anot. 007) · LIMITACION: Afectacion Vivienda (Anot. 008) |
| `COUNTERPARTY_GATE` | SIN HALLAZGO MATERIAL EN ESTA FUENTE | — (3/3 sujetos × 3 listas) |
| `URBAN_GATE` | NO UTILIZAR ESTE DATO COMO DEFINITIVO | `altura_maxima`, `tratamiento`, `uso_pot` en conflicto histórico |
| `ENVIRONMENT_GATE` | INFORMACIÓN INSUFICIENTE | Inundación: sin dato de fuente · Riesgo no mitigable: sin dato |
| `VALUATION_GATE` | INFORMACIÓN VERIFICADA | — |
| `EVIDENCE_GATE` | INFORMACIÓN VERIFICADA | cadena 10/10 · `PARCIAL_CON_DECLARACIONES` |

**Disposición global: PROCEDER CON CONDICIONES IDENTIFICADAS.** Las compuertas críticas
(identidad, títulos, evidencia) están resueltas; la cobertura parcial de `ENVIRONMENT_GATE`
**no borra la conclusión ni se convierte en «sin riesgo»**: viaja como `coverage_notes`
(«ENVIRONMENT_GATE: Inundación: sin dato de fuente»). Las disposiciones por dominio nunca
se borran: se imprimen y viajan en `by_gate`.

## 3. Separaciones que ahora se sostienen (y se prueban)

| Par que se confundía | Cómo queda | Prueba |
|---|---|---|
| Evidencia ≠ Observación ≠ Hallazgo ≠ Decisión | objetos con campos disjuntos (una observación no tiene severidad ni decisión) | `test_la_cadena_tiene_objetos_distintos` |
| `SOURCE_UNAVAILABLE` ≠ `NO_MATCH` | fuente caída ⇒ `FUENTE NO DISPONIBLE` y la compuerta **no** puede decir «sin hallazgo» | `test_fuente_no_disponible_no_produce_no_match` |
| `NOT_RUN` ≠ `NO_MATCH` | consulta no ejecutada ⇒ `INFORMACIÓN INSUFICIENTE` | `test_consulta_no_ejecutada_no_es_sin_coincidencia` |
| Integridad ≠ resultado del screening | cadena sin sellar ⇒ `EVIDENCIA EN CONFLICTO`, el screening conserva su resultado | `test_la_integridad_no_cambia_el_resultado_del_screening` |
| `PROPERTY RISK` ≠ `INFORMATION QUALITY RISK` | el conflicto histórico entra como riesgo de **calidad de información** | `test_conflicto_historico_no_produce_valor_definitivo` |
| Altura normativa ≠ altura física ≠ altura del modelo | tres conceptos impresos por separado | `test_la_altura_normativa_no_es_la_altura_fisica` |
| Valoración bloqueada ≠ valor cero | `NO EMITIR VALORACIÓN` + bloqueos; ninguna cifra, ni `$0` | `test_sin_valoracion_no_se_dice_que_se_calculo` |
| «NO SELLADA» vs «evidencia sellada» | invariante de auditoría: si el sello no es `SELLADO`, el PDF no puede afirmar «evidencia sellada» | invariante `sellado` en `DICTUS_GATE_REPORT` |

## 4. Tablero de decisión (página 1)

La página 1 dejó de ser un resumen de datos: es un **tablero de decisión** con las
columnas `TEMA · HALLAZGO · DECISIÓN DICTUS`, y cada fila declara **a quién afecta** y
**qué hacer**:

| TEMA | DECISIÓN DICTUS | Agrupa |
|---|---|---|
| TÍTULO | PROCEDER CON CONDICIONES | 2 hallazgos (hipoteca Anot. 007 + limitación Anot. 008) |
| ENTORNO Y RIESGOS | PROCEDER CON CONDICIONES | amenaza del POT (polígono intersecta el predio) |
| POT / CALIDAD DE DATOS | NO UTILIZAR ESTE DATO COMO DEFINITIVO | 6 atributos con versiones incompatibles |

Correcciones de esta iteración:

* **No se duplican hechos**: antes el mismo hallazgo salía dos veces (una por los hallazgos
  sueltos y otra por la matriz). Ahora el tablero es la matriz por tema.
* **El vocabulario se imprime completo**: el chip ya no dice «NO UTILIZAR ESTE DATO COMO
  DEFI…».
* **Los afectados no se truncan** (§28): la fila declara la lista completa de actores.
* **Un tema con varios hallazgos no los pierde**: la fila declara «+N hallazgo(s) del mismo
  tema con su propia acción: página 2» y esa acción se imprime en el detalle (§2).
* **Se corrigió una mala atribución real**: la limitación registral (Anot. 008) estaba
  clasificada como riesgo de ENTORNO, y el tablero mostraba, para el riesgo geográfico, la
  acción de la limitación. Ahora cada hallazgo declara su dominio por su naturaleza y la
  acción impresa corresponde a su hallazgo.
* **Un actor, un nombre**: «ASEGURADORA» y «ASEGURADORA DE TÍTULO» ya no conviven.

## 5. Sombras: simulación geométrica, no medición

`ShadowManifest SHW-473b9bebf24a` · estado `PARTIAL / ORIENTATIVE` · hash
`5be70fae0128ff41…` · 5 supuestos declarados.

* **Naturaleza:** SIMULACIÓN GEOMÉTRICA basada en posición solar, orientación y geometría
  disponibles; **no sustituye** inspección física ni estudio de asoleamiento.
* **Dependencias con su estado:** `solar_position: VERIFIED` · `building_height: CONFLICT` ·
  `geometry: NOT_EVALUATED` · `orientation: ASSUMED`.
* **Tres alturas, tres nombres:** altura normativa (POT) 11 · altura física del edificio
  **no declarada** · altura usada por el modelo 11. El documento dice explícitamente que el
  POT no es la altura física.
* Orientación y obstrucción son supuestos declarados de la corrida (fachada ESE, obstáculo
  Torre 7), no hechos verificados.

## 6. Artefactos entregados

En `docs/forensics/040-646406/dictus_2b/` y `…/dictus_2c/`:

* `DICTUS_EJECUTIVO_040-646406.pdf` (6 páginas, arquitectura auditada) y su versión
  rasterizada en `paginas/`.
* `DICTUS_TECNICO_040-646406.pdf` (17 páginas).
* `DICTUS_DECISION_MODEL_040-646406.json` — cadena completa + invariantes.
* `DICTUS_OBSERVATIONS_…json` (36) · `DICTUS_FINDINGS_…json` (9 hallazgos de decisión + los
  legacy separados) · `DICTUS_GATE_REPORT_…json` (7 compuertas + disposición + invariantes).
* `DICTUS_SHADOW_MANIFEST_…json` · `DICTUS_VISUAL_ASSETS_…json` (4 activos).
* `DICTUS_MANIFEST_040-646406.json` (modelo maestro + hash) · `DICTUS_RUN_STATE_…json`.
* `MATERIAL_FACT_COMPLETENESS_MATRIX.{json,md}` · `STATE_PROJECTION_LOSS_REPORT.json` ·
  `POI_ROOT_CAUSE_REPORT.json` · `COMPARATIVO_ANTES_DESPUES.md`.

## 7. Pruebas

* **`tests/test_dictus_20d_decision.py` — 22 pruebas nuevas** (las 14 obligatorias de §43,
  incluida «el hash maestro cambia ante una decisión material» y la compuerta de completitud
  material).
* Se actualizaron a la gramática 2.0D las pruebas de 2.0B-R1/2.0C que describían la página 1
  anterior (título, columnas, cabecera legacy): **no se relajó ninguna** — las que exigían
  «todos los hallazgos visibles» ahora exigen recuento exacto y declaración de agrupación.

## 8. Compuerta de calidad visual (§40) — PARCIAL, declarada

**No se realizó inspección visual humana por mí**: el modelo de esta sesión no acepta entrada
de imágenes, así que **no afirmo un PASS visual**. La evidencia de composición es
programática: 80 cajas registradas, cero solapamientos entre cajas de texto, cero desbordes
de página (`retícula OK`), 6 páginas en el orden aprobado, extracción de texto de las 6
páginas revisada línea por línea. Los PNG quedaron en `tmp_2d_visual/p1..p6.png` (derivados,
no versionados) para que la revisión visual la firme una persona.

## 9. Preguntas de validación humana (§45)

1. **¿La disposición global «PROCEDER CON CONDICIONES IDENTIFICADAS» es la correcta para
   este folio?** La sostienen título (2 cargas vigentes) y la cobertura parcial de entorno.
2. **¿Las condiciones del `TITLE_GATE` están completas?** Hipoteca (Anot. 007) y limitación
   (Anot. 008), cada una con su acción y su responsable —no intercambiables—.
3. **¿Se acepta que `ENVIRONMENT_GATE` quede en INFORMACIÓN INSUFICIENTE** por inundación y
   riesgo no mitigable sin fuente, sin degradar la conclusión global?
4. **¿Se acepta `NO UTILIZAR ESTE DATO COMO DEFINITIVO` en altura, tratamiento y uso POT**
   mientras el expediente histórico no se reconcilie?
5. **¿El conflicto histórico (6 atributos) debe seguir abierto o alguno ya está resuelto por
   una fuente oficial posterior?**
6. **¿La altura física del edificio puede declararse** (Ficha técnica / licencia) para dejar
   de simular sombras con supuestos?
7. **¿Son aceptables los supuestos de orientación (fachada ESE) y obstrucción (Torre 7)**
   usados en la simulación?
8. **¿La valoración verificada ($399.500.000 · banda 373.532.500–435.455.000) es utilizable
   para originación**, entendiendo que DICTUS no la firma?
9. **¿El tablero de la página 1 resume los temas correctos** (TÍTULO, ENTORNO Y RIESGOS,
   POT/CALIDAD DE DATOS) o falta algún dominio con decisión propia?
10. **¿La agrupación por tema es aceptable** cuando un tema tiene varios hallazgos, sabiendo
    que la fila declara cuántos agrupa y remite a la página 2?
11. **¿Los actores declarados por hallazgo** (comprador, vendedor, inmobiliaria,
    banco/financiador, aseguradora de título) son los correctos en cada caso?
12. **¿El sello `PARCIAL_CON_DECLARACIONES` (10/10 evidencias, cadena sellada, 1 hecho sin
    fuente) es el estado correcto** para entregar el expediente?
13. **¿Firma la revisión humana** el expediente de 6 páginas como base de decisión, dejando
    `human_review.status = PENDIENTE` → `REVISADO`?

Ninguna de estas trece preguntas la responde DICTUS: son materia del profesional competente
(abogado, avaluador inscrito en el RAA, geodesta, analista de crédito).

## 10. Límites declarados (nada de esto se resuelve con este entregable)

* **Sin inspección física** ni estudio de asoleamiento especializado (sombras = simulación).
* **Sin certificado de tradición nuevo en esta corrida** más allá del CTL aportado.
* **La escena satelital no fue producida** por la corrida: el documento lo declara en lugar
  de mostrar una imagen de otro origen.
* **1 hecho sin fuente** (inundación) declarado `SIN_FUENTE`, nunca «sin riesgo».
* **6 conflictos históricos abiertos** en el expediente del mismo inmueble: no se
  «corrigen» a favor de ninguna versión.

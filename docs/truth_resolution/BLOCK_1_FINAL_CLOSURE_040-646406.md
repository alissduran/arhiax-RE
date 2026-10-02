# BLOCK 1 — CIERRE DEFINITIVO · TRUTH RESOLUTION · folio 040-646406

**Estado:** `BLOCK 1 — TRUTH RESOLUTION CLOSED`
**Corrida canónica:** `run_id = 04b364d4-7131-48b9-b81c-bd5a737fe3df` · `DICTUS ID = DX-040-646406-20261002`
**Generado en:** `2026-10-02T21:12:09.433884+00:00` · **DICTUS_MASTER_HASH:** `ddacf899bc59d8419a02e4fdba80a04545715719fd61204cfccf8bbae1cf0794`

---

## 1. Objeto y alcance del cierre

Cerrar **exactamente cuatro** asuntos y dejar el bloque versionado:

| # | Asunto | Resultado |
|---|---|---|
| A | El PDF ejecutivo contenía a la vez «2 atributo(s)» y «6 atributo(s)» | **CASO B** demostrado: dos métricas distintas, dos rótulos inequívocos |
| B | El recuento no aparecía donde el contrato dice | Una sola verdad canónica, propagada a las 4 etapas |
| C | `dictus_2b/` mezclaba ejecutivos de corridas distintas | Canónico en la raíz; históricos en `legacy/` con bytes preservados |
| D | Versionar | 3 commits lógicos + 1 de artefactos ajenos, push verificado |

**No se tocó:** Estimation Engine, rango 130M–490M, `ESTIMATION_GATE`, `EVIDENCE_QUALITY`, M1–M5,
screening, solar, adquisición, diseño general de páginas, ni la semántica de riesgo aceptada.
**No se ajustó ninguna categoría** para que el recuento diera 2: la reclasificación del Bloque 1
se mantiene tal cual (las 7 condiciones del conflicto histórico).

---

## 2. Ubicación y significado del antiguo «6»

Forense ejecutada sobre el **PDF REAL** `docs/forensics/040-646406/dictus_2b/DICTUS_EJECUTIVO_040-646406.pdf`
(6 páginas, texto extraído con `pymupdf`/`pypdf`, sin fixtures) y sobre el código real.

### 2.1 Todas las ocurrencias de `\d+ atributo(s)`, `conflicto`, `reconciliaci`, `coherencia`

| Página | Texto exacto | Sección | Clave semántica | Objeto fuente | `archivo:línea` |
|---|---|---|---|---|---|
| P1 | `CONFLICTOS entre versiones del expediente` | cabecera de coherencia | rótulo de sección | `secciones.coherencia` | `api/dictus_secciones.py:993` |
| P1 | `COHERENCIA DE INFORMACIÓN` | título de la tarjeta | rótulo | `TarjetaCoherencia` | `api/dictus_ejecutivo.py:1042` |
| P1 | `COHERENCIA DE INFORMACIÓN — 2 atributo(s) requieren reconciliación histórica · +4 diferencia(s) material(es) declarada(s) con su clase` | tarjeta de coherencia | **conflictos VERDADEROS** | `n_conflictos` ← `coherencia_resumen.true_conflict` | `api/dictus_ejecutivo.py:1009` (pre-fix) |
| P1 | `6 atributo(s) con resultados incompatibles entre versiones del expediente` | DECISION BOARD · fila `POT / CALIDAD DE DATOS` | **atributos con versiones rivales comparadas** | `len(coherencia_attrs)` | `api/dictus_secciones.py:747` (pre-fix) |
| P4 | `Distintos entre versiones · ver coherencia abajo.` | `DECISIÓN TERRITORIAL Y URBANÍSTICA` | nota por fila | `_nota_atributo` | `api/dictus_secciones.py:636` |
| P4 | `CONFLICTO HISTÓRICO` | chip de altura/edificabilidad | estado impreso | `TERMINO_IMPRESO_POR_ESTADO` | `api/dictus_secciones.py:352` |
| P4 | `COHERENCIA DE DATOS POR ATRIBUTO` | panel de 6 filas | rótulo | `coherencia_attrs` | `api/dictus_secciones.py:689` |
| P5 | `SUPUESTO — La altura normativa del POT está en CONFLICTO HISTÓRICO entre versiones del mismo expediente.` | asoleamiento | supuesto declarado | `shadow` | `api/dictus_ejecutivo.py` (panel solar) |

### 2.2 Qué significa el «6» — sin inferir

`api/dictus_secciones.py:689` construye `coherencia_attrs = _coherencia_detallada(hist, rs, mc)`
(`api/dictus_secciones.py:328-384`), que agrega **dos** conjuntos:

1. `hist.conflictos_abiertos` → estado `HISTORICAL_CONFLICT` (conflictos verdaderos);
2. `hist.requieren_revision` con `diferencia_material == True` → estado `REQUIERE_VALIDACION`
   (diferencias materiales que el expediente **ya explica** por su clase declarada).

Medición literal sobre el RunState real (no inferida):

```
len(_coherencia_detallada(hist, rs, mc)) = 6
    altura_maxima | HISTORICAL_CONFLICT   | clase=None                  → conflicto verdadero
    coordenada    | HISTORICAL_CONFLICT   | clase=None                  → conflicto verdadero
    amenaza       | REQUIERE_VALIDACION   | clase=RESOLVED_BY_PRECEDENCE
    titulares     | REQUIERE_VALIDACION   | clase=NORMALIZATION_DIFFERENCE
    tratamiento   | REQUIERE_VALIDACION   | clase=HISTORICAL_CHANGE
    uso_pot       | REQUIERE_VALIDACION   | clase=SEMANTIC_DIFFERENCE
```

⇒ **El «6» = `attributes_compared_count`**: atributos que la corrida **comparó entre versiones y
encontró divergentes**, cada uno con su clase declarada. Es decir `2 conflictos verdaderos + 4
diferencias materiales explicadas`.

Evidencia adicional (coincidencia exacta del conjunto, medida y no supuesta): el conjunto del «6»
es **idéntico** al del informe **almacenado** del expediente
(`docs/forensics/040-646406/dictus_2/HISTORICAL_CONSISTENCY_REPORT.json`, versión `1.0.0`), cuyo
`conflictos_abiertos` valía 6 con el criterio ANTERIOR (`estado == HISTORICAL_CONFLICT`).
El RunState lo persiste de forma explícita en
`historical_consistency.informe_almacenado.conflictos_abiertos = 6`.

⇒ El «6» **no es código muerto**: se calculaba en vivo (por eso el valor coincidía), pero arrastraba
el **rótulo legacy** («resultados incompatibles»), que afirmaba como incompatibles 4 atributos que el
criterio canónico ya había **explicado**. Ese rótulo competía con «2 atributo(s) requieren
reconciliación histórica» y hacía que dos métricas distintas se leyeran como la misma.

---

## 3. Ubicación del «2» y su contexto

| Página | Texto exacto | Sección | Clave semántica | Objeto fuente | `archivo:línea` |
|---|---|---|---|---|---|
| P1 | `COHERENCIA DE INFORMACIÓN — 2 atributo(s) requieren reconciliación histórica · +4 diferencia(s) material(es) declarada(s) con su clase` | tarjeta de coherencia | **conflictos verdaderos (`TRUE_CONFLICT`)** | `coherencia_resumen.true_conflict` | `api/dictus_secciones.py:999` (pre-fix) → `api/dictus_ejecutivo.py:978` → `TarjetaCoherencia` `api/dictus_ejecutivo.py:1009` (pre-fix) |

`2 = len(historical_consistency.conflictos_abiertos) = {altura_maxima, coordenada}`.
`+4` = `len([r for r in requieren_revision if r.diferencia_material])`.
El «2» está **correcto** y sale de la fuente canónica: no aplica el caso C.

### 3.1 Residuo legacy REAL detectado en el camino del «2» (y eliminado)

`api/dictus_ejecutivo.py:996` (pre-fix):

```python
self.n_conflictos = (len(self.atributos) if n_conflictos is None
                     else int(n_conflictos))
```

Ese sustituto legacy convertía la **longitud del panel de divergencias** en el recuento de
conflictos si el valor no llegaba resuelto. Es exactamente el defecto de origen de un «6» rotulado
como conflictos. Hoy **no existe**: si el recuento no llega resuelto se levanta
`RecuentoNoResuelto` (fail-closed) en vez de imprimir otra métrica.

---

## 4. Caso aplicable: **B**

| Caso | Enunciado | ¿Aplica? | Por qué (medido) |
|---|---|---|---|
| **A** | el «6» es residuo de lógica anterior ⇒ eliminarlo | **NO** | El «6» se computa en vivo desde el RunState de la corrida (`len(coherencia_detallada)`), no desde código muerto ni desde un literal. La métrica subyacente (atributos con versiones rivales comparadas) es válida y auditable: 6 filas reales del panel de la página 4. Eliminarlo borraría un hecho del expediente. |
| **B** | el «6» es una métrica distinta y válida ⇒ conservar ambos **solo** con rótulos inequívocamente distintos | **SÍ** | Dos métricas distintas (`true_conflict_count = 2`, `attributes_compared_count = 6`) compartían la palabra «atributo(s)» y el «6» usaba «resultados incompatibles» para atributos ya explicados. Se conservan AMBAS con rótulos disjuntos (§5). |
| **C** | el «2» está mal ⇒ corregirlo desde la fuente canónica | **NO** | `2 == len(conflictos_abiertos) == len(true_conflicts)` derivado del informe canónico; coincide con `recuento_conflictos.total` y con la lista persistida. El «2» nunca estuvo mal. |

### 4.1 Prohibición cumplida

Ninguna de las dos métricas comparte rótulo con la otra. Los rótulos viven en **un solo sitio**
(`api/dictus_historia.py`) y las páginas los **leen**:

* `ROTULO_CONFLICTO_VERDADERO = "atributo(s) requieren reconciliación histórica"` → **solo** el recuento 2.
* `ROTULO_ATRIBUTOS_COMPARADOS = "atributo(s) comparados históricamente"` → **solo** el recuento 6.

La frase legacy **«atributo(s) con resultados incompatibles»** ya no existe en `api/`
(verificado por búsqueda en todo `api/*.py`), y el rótulo «attributes_compared» **no contiene**
«reconciliación», «conflictos abiertos» ni «datos incompatibles».

---

## 5. Estructura canónica de una sola verdad

**Función única:** `dictus_historia.get_true_conflict_summary(informe)`
(`api/dictus_historia.py`), versión `dictus-true-conflict-summary/1.0.0`.
Todas las páginas, el modelo, el manifest y el RunState la consumen o **leen su salida ya resuelta**.

```json
{
  "version": "dictus-true-conflict-summary/1.0.0",
  "true_conflicts": ["altura_maxima", "coordenada"],
  "true_conflict_count": 2,
  "attributes_compared": ["altura_maxima", "amenaza", "coordenada",
                          "titulares", "tratamiento", "uso_pot"],
  "attributes_compared_count": 6,
  "resolved_by_precedence": ["amenaza"],
  "historical_changes": ["tratamiento"],
  "semantic_differences": ["uso_pot"],
  "normalization_differences": ["titulares"],
  "cascades_of_geometry_change": [],
  "diferencias_sin_clase": [],
  "changes_explained_by_source": ["planes_parciales"],
  "requires_action": true,
  "criterio": "el recuento de conflictos se deriva SOLO de TRUE_CONFLICT (las siete condiciones); `attributes_compared` es la métrica DISTINTA de atributos con versiones rivales comparadas y no cuenta conflictos",
  "rotulos": {
    "true_conflict": "atributo(s) requieren reconciliación histórica",
    "attributes_compared": "atributo(s) comparados históricamente",
    "nota_attributes_compared": "..."
  }
}
```

### 5.1 Invariantes verificadas DENTRO de la función (no delegadas)

```
true_conflict_count      == len(true_conflicts)              ✅ 2 == 2
attributes_compared_count == len(attributes_compared)        ✅ 6 == 6
true_conflicts           ⊆  attributes_compared              ✅
attributes_compared      == true_conflicts ∪ (5 clases)      ✅ {altura,coord}∪{amenaza}∪{tratamiento}∪{uso_pot}∪{titulares}
```

* `true_conflicts` se deriva de la **LISTA** `conflictos_abiertos`; el contador sale de
  `len(...)` de esa lista. **Nunca** de `len(requieren_revision)`, `len(cambios)`,
  `len(versiones)`, hardcode, parseo de string ni contador legacy.
* Si el informe trae el contador histórico `recuento_conflictos.total` y **diverge**, la función
  **levanta** `AssertionError`: dos contadores persistidos que puedan divergir es el defecto que
  este bloque cierra (probado en `test_legacy_persisted_counter_cannot_diverge`).
* `planes_parciales` (cambio **unilateral** de fuente, `CAMBIO_CON_FUENTE`) se declara aparte en
  `changes_explained_by_source` y **no** entra en `attributes_compared`, que exige **valores
  rivales** comparados.

### 5.2 Quién proyecta y quién lee

| Módulo | Rol | Línea (post-fix) |
|---|---|---|
| `api/dictus_historia.py` | **resuelve** (única función) + rótulos canónicos | `get_true_conflict_summary` |
| `api/dictus_entrega.py` | **resuelve UNA vez** y **persiste** en el RunState | `resumen_conflictos = dh.get_true_conflict_summary(hist)` |
| `api/dictus_manifiesto.py` | **proyecta** al modelo + manifest (no cuenta) | `_resumen_conflictos_canonico` |
| `api/dictus_secciones.py` | **lee** (RunState → modelo) | `resumen_conflictos = modelo.get(...) or rs.get(...)` |
| `api/dictus_ejecutivo.py` | **imprime**; no calcula; fail-closed | `_recuento_coherencia` / `TarjetaCoherencia` |

---

## 6. Dónde vivía el recuento antes y dónde vive ahora (RunState real)

### 6.1 RunState POST-BLOQUE 1 (estado real leído, no asumido)

Archivo real: `docs/forensics/040-646406/dictus_2b/DICTUS_RUN_STATE_040-646406.json`.
El recuento **no** aparecía donde el contrato decía. Vivía en:

| JSON path (post-Bloque 1) | Valor | Qué era |
|---|---|---|
| `historical_consistency.conflictos_abiertos` (longitud) | **2** | los conflictos verdaderos — única fuente correcta |
| `historical_consistency.recuento_conflictos.total` | **2** | contador derivado (mismo valor) |
| `historical_consistency.informe_almacenado.conflictos_abiertos` | **6** | el contador **legacy** del informe almacenado v1.0.0 |
| — (no existía) | — | `historical_consistency_summary` **no existía** |

⇒ El `6` también vivía persistido en el RunState como `informe_almacenado.conflictos_abiertos`,
lo que hacía posible que una página futura lo imprimiera como conflictos vigentes.

### 6.2 RunState AHORA (una sola verdad, un solo path)

**JSON path: `historical_consistency_summary`** (raíz del RunState) →
`true_conflict_count = 2`, `true_conflicts = ["altura_maxima", "coordenada"]`,
`attributes_compared_count = 6`.

El «2» canónico **no se duplica**: `historical_consistency.conflictos_abiertos` sigue siendo la
**lista fuente**, y `recuento_conflictos.total` se verifica contra el resumen en cada build
(§5.1). No hay dos contadores independientes.

---

## 7. Paths literales: RunState / Manifest / DocumentModel (y contrato del manifest)

| Etapa | Path literal | Valor |
|---|---|---|
| **RUNSTATE** | `docs/forensics/040-646406/dictus_2b/DICTUS_RUN_STATE_040-646406.json` → `historical_consistency_summary` | `true_conflict_count = 2`, `attributes_compared_count = 6`, `true_conflicts = ["altura_maxima","coordenada"]` |
| **MANIFEST** | `docs/forensics/040-646406/dictus_2b/DICTUS_MANIFEST_040-646406.json` → `historical_consistency_summary` | `true_conflict_count = 2`, `true_conflicts = ["altura_maxima","coordenada"]` |
| **DOCUMENT MODEL** | `docs/forensics/040-646406/dictus_2b/DICTUS_MANIFEST_040-646406.json` → `modelo.historical_consistency_summary` | `true_conflict_count = 2`, `true_conflicts = ["altura_maxima","coordenada"]` |
| **MODELO · lista fuente** | … → `modelo.historical_consistency.conflictos_abiertos` | `["altura_maxima","coordenada"]` (longitud 2) |
| **PDF** | `docs/forensics/040-646406/dictus_2b/DICTUS_EJECUTIVO_040-646406.pdf` → página 1 | `2 atributo(s) requieren reconciliación histórica` |

### 7.1 Contrato del manifest (documentado, no afirmado de más)

El **manifest NO replica** el informe de coherencia completo. Su contrato es:

* `manifest.modelo.historical_consistency` → `{veredicto, versiones_comparadas,
  conflictos_abiertos[], cambios_explicados[]}`.
  **No** contiene `requieren_revision` ni `clasificaciones_conflicto` ni `recuento_conflictos`
  (verificado por prueba: `test_manifest_projects_same_conflict_count` falla a propósito si el
  contrato cambia sin actualizar la prueba).
* `manifest.modelo.historical_consistency_summary` y `manifest.historical_consistency_summary`
  → **el MISMO objeto**, serializado dos veces por **proyección** (contrato de raíz para que un
  revisor lo lea sin abrir el modelo; y dentro del modelo porque el modelo es la entrada del
  **hash maestro**).
  No hay segundo cálculo: `dictus_entrega` resuelve **una vez** y entrega ese objeto; el manifest
  lo asigna tal cual (`manifest["historical_consistency_summary"] = modelo["historical_consistency_summary"]`).
  Las dos copias son iguales **por construcción**, y la prueba lo exige (`assertEqual(man, mod)`).

---

## 8. Página y texto del PDF (aceptación física sobre el PDF regenerado)

**Archivo:** `DICTUS_EJECUTIVO_040-646406.pdf` · 6 páginas ·
`sha256 = 6d2c0aa36d9164cee90629a6e598be006648f0655ba39e0e01082da6278062eb`
(texto extraído con `pypdf` del archivo físico, sin fixtures).

| Página | Texto exacto (línea extraída) |
|---|---|
| **1** | `COHERENCIA DE INFORMACIÓN — 2 atributo(s) requieren reconciliación histórica · +4 diferencia(s) material(es) declarada(s) con su clase` |
| **1** | `6 atributo(s) comparados históricamente · 2 conflicto(s) verdadero(s)` |

* El rótulo de **conflictos** aparece **una sola vez** como recuento vigente, y con el valor 2.
* La frase legacy `6 atributo(s) requieren reconciliación` **no aparece**.
* La frase legacy `atributo(s) con resultados incompatibles` **no aparece** en ninguna página.
* La fila del tablero declara su acción acotada al recuento verdadero:
  `ACCIÓN: Cruzar la ficha/polígono POT solo para los 2 conflicto(s) verdadero(s).`
* **El PDF no calcula el contador:** `_recuento_coherencia` levanta `RecuentoNoResuelto` si
  `coherencia_resumen.true_conflict` no llega resuelto, y `TarjetaCoherencia` ya no acepta
  `n_conflictos=None`. Probado en `test_pdf_does_not_recompute_the_counter`.

---

## 9. Tabla E2E de propagación

| stage | json_path / field | true_conflict_count | attributes | consistent |
|---|---|---|---|---|
| RUNSTATE | `historical_consistency_summary` | 2 | `["altura_maxima","coordenada"]` | ✅ |
| RUNSTATE (lista fuente) | `historical_consistency.conflictos_abiertos` | `len = 2` | `["altura_maxima","coordenada"]` | ✅ |
| MANIFEST | `historical_consistency_summary` | 2 | `["altura_maxima","coordenada"]` | ✅ |
| DOCUMENT MODEL | `modelo.historical_consistency_summary` | 2 | `["altura_maxima","coordenada"]` | ✅ |
| DOCUMENT MODEL (lista) | `modelo.historical_consistency.conflictos_abiertos` | `len = 2` | `["altura_maxima","coordenada"]` | ✅ |
| PDF | página 1 · tarjeta de coherencia | 2 | `altura_maxima`, `coordenada` (página 4) | ✅ |

`runstate_count == manifest_count == model_count == pdf_count == 2` con las mismas
`true_conflict_attributes`. Métrica distinta declarada aparte y consistente:
`attributes_compared_count = 6` en las tres etapas de estado y en el PDF (fila del tablero).

---

## 10. Canonicalización del juego de artefactos (C)

**Convención aplicada:** la **raíz** de `docs/forensics/040-646406/dictus_2b/` contiene
**únicamente** los artefactos de la corrida **canónica** (`DX-040-646406-20261002`); los de
corridas anteriores viven en `legacy/`, intactos, con `status: HISTORICAL_ONLY`.
**Sin borrar historia:** nada se eliminó; los bytes se preservaron.

| Original (raíz) | Destino (legacy/) | `run_id` | `generated_at` | `status` |
|---|---|---|---|---|
| `DICTUS_2.0B_TEXTO_EJECUTIVO_040-646406.txt` | `legacy/DICTUS_2.0B_TEXTO_EJECUTIVO_040-646406.txt` | `DX-040-646406-20260925` | 2026-09-25 | `HISTORICAL_ONLY` |
| `ENTREGA_2.0B_R1.md` | `legacy/ENTREGA_2.0B_R1.md` | `DX-040-646406-20260925` | 2026-09-25 | `HISTORICAL_ONLY` |
| `paginas/` (6 PNG, ejecutivo 2.0B) | `legacy/paginas_2.0B_20260925/` | `DX-040-646406-20260925` | 2026-09-25 | `HISTORICAL_ONLY` |

Se conservan en la raíz como canónicos, además de los contractuales: `poi_map.png/html` y
`sombra_9am/3pm.png`. Estos dos últimos son **declarados por el RunState canónico** como
`provenance: SAME_RUN` (su `generated_at` de asset es `2026-09-25`, un arrastre declarado por la
propia corrida): se mantienen porque el estado vigente los referencia; moverlos dejaría el RunState
apuntando a artefactos ausentes.

### 10.1 `ARTIFACT_INDEX_040-646406.json`

Creado por script reproducible `scripts/dictus_artifact_index.py`. Un revisor identifica el Dictus
vigente **sin ambigüedad** leyendo solo el índice:

| Campo | Valor |
|---|---|
| `canonical_run_id` | `04b364d4-7131-48b9-b81c-bd5a737fe3df` |
| `canonical_generated_at` | `2026-10-02T21:12:09.433884+00:00` |
| `canonical_dictus_id` | `DX-040-646406-20261002` |
| `canonical_master_hash` | `ddacf899bc59d8419a02e4fdba80a04545715719fd61204cfccf8bbae1cf0794` |
| `canonical_true_conflict_count` | `2` · `["altura_maxima","coordenada"]` |
| `executive_pdf` | `DICTUS_EJECUTIVO_040-646406.pdf` · sha256 `6d2c0aa36d91…62eb` |
| `technical_pdf` | `DICTUS_TECNICO_040-646406.pdf` · sha256 `d0dd6413ad42…eaaa` |
| `run_state` | `DICTUS_RUN_STATE_040-646406.json` · sha256 `249fef88b7da…4215` |
| `manifest` | `DICTUS_MANIFEST_040-646406.json` · sha256 `448ea52fde4b…80ee` |
| `acceptance_pack` | `ACEPTACION_040-646406.json` · sha256 `416d479731bb…ab14` |
| `legacy_artifacts[]` | 3 entradas con `path`, `run_id`, `generated_at`, `status: HISTORICAL_ONLY`, `sha256_before/after` |

> Nota de política del repositorio: `*.pdf` está en `.gitignore` (los PDFs no se versionan; se
> reproducen con `python scripts/dictus_run.py`). Por eso el índice declara su **sha256**: permite
> verificar que un PDF regenerado es exactamente el de la corrida canónica.

---

## 11. Hashes de legacy preservados (`sha256_before == sha256_after`)

Movimiento con `scripts/dictus_legacy_canonicalize.py` (copia + verificación de bytes).

| Artefacto (en `legacy/`) | `sha256_before` | `sha256_after` | iguales |
|---|---|---|---|
| `DICTUS_2.0B_TEXTO_EJECUTIVO_040-646406.txt` | `2b8406aa92f73f7ba20c1d2b568156847346cbe983d6ec732afa750804812739` | `2b8406aa92f73f7ba20c1d2b568156847346cbe983d6ec732afa750804812739` | ✅ |
| `ENTREGA_2.0B_R1.md` | `924bb7723bf119b2d6f64e5267f4f44d00c1718ae83617b5eb4fc00605d4b314` | `924bb7723bf119b2d6f64e5267f4f44d00c1718ae83617b5eb4fc00605d4b314` | ✅ |
| `paginas_2.0B_20260925/ejecutivo_p1.png` | `94945648636e4364523ed7a86ca74deb152e6d1b5dd0ea1cd18c6d8a70ec903b` | `94945648636e4364523ed7a86ca74deb152e6d1b5dd0ea1cd18c6d8a70ec903b` | ✅ |
| `paginas_2.0B_20260925/ejecutivo_p2.png` | `f926c480b8a38b8cf9fdb654a7b8bbed77cac4bd6207f64c694ecdd78d29358c` | `f926c480b8a38b8cf9fdb654a7b8bbed77cac4bd6207f64c694ecdd78d29358c` | ✅ |
| `paginas_2.0B_20260925/ejecutivo_p3.png` | `1adac690c03237165592a05c926e0bfab43492fc8cc0d197f29911fd622b9a0e` | `1adac690c03237165592a05c926e0bfab43492fc8cc0d197f29911fd622b9a0e` | ✅ |
| `paginas_2.0B_20260925/ejecutivo_p4.png` | `cbaafce54c82affde7cd7d331e5f01cce8b24a962662e74a6a477bcecb8aea97` | `cbaafce54c82affde7cd7d331e5f01cce8b24a962662e74a6a477bcecb8aea97` | ✅ |
| `paginas_2.0B_20260925/ejecutivo_p5.png` | `18d165d194292e364a0d116f52244e567f0aef9163b82305d0b4001db5d5dc74` | `18d165d194292e364a0d116f52244e567f0aef9163b82305d0b4001db5d5dc74` | ✅ |
| `paginas_2.0B_20260925/ejecutivo_p6.png` | `733b9cd2bbc206115b671a8747d291f7ea62a2d9791de0e3cc9a7b13e6d6a903` | `733b9cd2bbc206115b671a8747d291f7ea62a2d9791de0e3cc9a7b13e6d6a903` | ✅ |

**8/8 artefactos con bytes idénticos.** Registro completo en
`docs/forensics/040-646406/dictus_2b/legacy/LEGACY_ARTIFACTS.json`
(`sha256_preservados_todos: true`).

---

## 12. Pruebas ejecutadas (comando + resultado + exit code)

Todas sobre los artefactos **reales** de la corrida canónica, sin fixtures. `PYTHONIOENCODING=utf-8`.

| # | Comando | passed | failed | skipped | exit code |
|---|---|---|---|---|---|
| 1 | `python -m pytest tests/test_attribute_resolution_ladder.py tests/test_cross_page_truth.py tests/test_fact_propagation.py tests/test_geometry_binding.py tests/test_historical_conflict_eligibility.py tests/test_risk_state_semantics.py tests/test_single_truth_per_attribute.py -q` | **74** | 0 | 0 | **0** |
| 2 | `python -m pytest tests/test_conflict_count_single_truth.py -q` | **9** | 0 | 0 | **0** |
| 3 | `python -m pytest tests/test_dictus_canonical_artifact.py -q` | **5** | 0 | 0 | **0** |
| 4 | `python scripts/golden_evidence_asserts.py` | 11/11 PASS | 0 FAIL · 0 NO EVALUABLE | — | **0** |
| 5 | `python -m pytest tests -q` (regresión completa) | **1703** | **1** (pre-existente) | 2 (+1 xfailed, 141 subtests) | 1 |
| 6 | `python scripts/dictus_run.py` (regeneración, UNA corrida real) | — | — | — | **0** |
| 7 | `python scripts/dictus_artifact_index.py` | — | — | — | **0** |

### 12.1 El fallo de la suite completa es PRE-EXISTENTE (demostrado, no supuesto)

`tests/test_gpv_f77.py::TestGpvF77Endpoint::test_endpoint_genera_docx_con_certificado`
→ `AttributeError: 'Form' object has no attribute 'strip'` en `api/index.py:1134`.

Demostración: con **todos mis cambios retirados** (`git stash push --keep-index -- api tests
scripts docs public`) el mismo test **falla idéntico** (`1 failed`, exit 1) antes de restaurar.
`api/index.py` **no** está en el diff de este bloque. No pertenece al alcance del Bloque 1.

### 12.2 Pruebas exigidas por el contrato

* `tests/test_conflict_count_single_truth.py`: `test_true_conflict_count_equals_len_true_conflicts`,
  `test_runstate_persists_true_conflict_count`, `test_manifest_projects_same_conflict_count`,
  `test_document_model_uses_same_conflict_count`, `test_pdf_prints_canonical_true_conflict_count`,
  `test_pdf_does_not_print_legacy_conflict_count_as_current` + 3 adicionales
  (`test_pdf_does_not_recompute_the_counter`, `test_all_stages_report_the_same_pair`,
  `test_legacy_persisted_counter_cannot_diverge`).
* `tests/test_dictus_canonical_artifact.py`: un solo ejecutivo CURRENT, un solo `run_id` CURRENT,
  PDF/RunState/Manifest comparten corrida, y los legacy **no** se tratan como current.
* **Golden sin hardcode:** el recuento se **deriva** del objeto canónico
  (`n = canonico["true_conflict_count"]`) y se compara con el PDF; se exige
  `f"{n} {ROTULO_CONFLICTO_VERDADERO}"` en la página 1 en el contexto correcto y la **ausencia** de
  la frase legacy. No hay ningún `assert count == 2` literal.
* **No se borró ninguna prueba:** `test_cross_page_truth.py`, `test_attribute_resolution_ladder.py`,
  `test_risk_state_semantics.py`, `test_dictus_semantica_atributos.py` y
  `test_golden_evidence_pack.py` siguen existiendo y en verde (74 + adaptadas).

### 12.3 Verificación post-commit (re-ejecución de las suites bloqueantes)

Ejecutada **después de los commits**, sobre el árbol versionado:

| Comprobación | Resultado |
|---|---|
| Suite 1 (Bloque 1, 7 pruebas) | **74 passed**, exit **0** |
| Suite 2 (`test_conflict_count_single_truth.py`) | **9 passed**, exit **0** |
| Suite 3 (`test_dictus_canonical_artifact.py`) | **5 passed**, exit **0** |
| Suite 4 (`scripts/golden_evidence_asserts.py`) | **11/11 PASS**, exit **0** |
| `true_conflict_count` RUNSTATE / MANIFEST / MODEL | `2` / `2` / `2` (idénticos) |
| `true_conflict_attributes` RUNSTATE / MANIFEST / MODEL | `["altura_maxima","coordenada"]` ×3 (idénticos) |
| Resultado semántico del PDF | misma línea canónica en la página 1; frase legacy ausente; 6 páginas |
| `sha256` del índice vs disco (`executive_pdf`, `technical_pdf`, `run_state`, `manifest`, `acceptance_pack`) | **MATCH** en los 5 |
| `legacy` | `sha256_preservado = true` en los 3 artefactos (8 ficheros) |
| Ejecutivos en la raíz | exactamente **1**: `DICTUS_EJECUTIVO_040-646406.pdf` |

Sin cambios de artefactos: los `sha256` del índice siguen coincidiendo.

---

## 13. Commits y push

| # | SHA | Mensaje | Contenido |
|---|---|---|---|
| 1 | `92f5f91b77f1f204730d53ebc1681ddf63420e97` | `feat(truth-resolution): add canonical attribute resolution` | 34 ficheros: `api/attribute_truth.py`, `api/acquisition_http.py`, correcciones de causas raíz en `api/`, 7 pruebas nuevas, 4 pruebas adaptadas, `scripts/golden_evidence_asserts.py`, los 8 artefactos de `docs/truth_resolution/`, `.gitignore` |
| 2 | `97b771faa5ad1a75efb799ce6830235a20683829` | `fix(dictus): persist canonical conflict summary` | 7 ficheros: `tests/test_conflict_count_single_truth.py` + RunState, manifest, aceptación y texto del ejecutivo regenerados + manifest publicado |
| 3 | `880dd7dabf182b2541bedb34528dd9fdc84bb858` | `chore(forensics): canonicalize golden artifact set` | 14 ficheros: `legacy/` (3 artefactos, bytes preservados; git detecta los 2 ficheros movidos como **R100**), `ARTIFACT_INDEX_040-646406.json`, `scripts/dictus_artifact_index.py`, `scripts/dictus_legacy_canonicalize.py`, `tests/test_dictus_canonical_artifact.py`, este documento |
| 4 | `50e332daf883b0a5599275535593d3d1b45dc5bd` | `chore(estimation): version refreshed estimation artifacts (run-bound)` | `docs/estimation/**` (7 ficheros): refresco **pre-existente** de artefactos ligados al run `b680793e…`, no al canónico. **No se modificó una sola línea del motor de estimación** |
| 5 | *(este commit)* | `docs(truth-resolution): record closure SHAs and post-commit verification` | Resuelve los SHA del cierre y registra la evidencia post-commit y el hallazgo de auditoría §14.5 |

### 13.1 Separación de los commits 1 y 2: límite real y su trazabilidad

Block 1 y Block 1.1 **comparten ficheros** (`api/dictus_historia.py`, `dictus_manifiesto.py`,
`dictus_secciones.py`, `dictus_ejecutivo.py`, `dictus_entrega.py`) y **no existe instantánea
intermedia** recuperable: HEAD (`565a46e`) **no** contiene ni las siete condiciones
(`TRUE_CONFLICT` ausente en `HEAD:api/dictus_historia.py`) ni `get_true_conflict_summary`.
Separar por hunks produciría un commit 1 que **no importaría**. Por tanto los ficheros
compartidos van en el commit 1 y el commit 2 lleva lo específico de 1.1 (prueba nueva +
artefactos que **persisten** el resumen canónico). Los hunks de 1.1 quedan identificados aquí con
`archivo:línea` (los `archivo:línea` pre-fix de §2–§3), de modo que la separación es auditable.

### 13.2 Push

```
$ git push origin main
   565a46e..50e332d  main -> main                      (exit 0)

$ git ls-remote origin refs/heads/main
50e332daf883b0a5599275535593d3d1b45dc5bd	refs/heads/main
```

El `refs/heads/main` remoto coincide con `HEAD` local. El aviso
`sh.exe (…): fatal error - couldn't create signal pipe, Win32 error 5` es **inocuo**
(lo emite el `sh` de MSYS que invoca git para el credential helper; el push devolvió
exit 0 y la referencia remota quedó actualizada).

---

## 14. `git status` final y veredicto

### 14.1 `git status --short` final

Vacío. Lo único excluido son rutas **ignoradas** (nada borrado del disco), acotadas explícitamente
en `.gitignore` con su motivo:

* `docs/truth_resolution/scratch/` — sondeos temporales del cierre (no son evidencia contractual).
* `docs/source_pack/tools/b*.py`, `docs/source_pack/raw/phase_b/`, `api/core_remeasure.py` —
  andamiaje del **otro** bloque en curso (source pack / adquisición). `api/core_remeasure.py` tiene
  como **únicos** consumidores los sondeos `b9_run_remeasure.py` y `b14_paso1_mercado.py` (ningún
  módulo versionado lo importa), así que se acota en bloque con ellos.
* `docs/source_pack/tools/_piptmp/` y `pytest-cache-files-*/`, `tmp_*/` — temporales de pip/pytest
  con permisos restringidos, preexistentes.

`api/acquisition_http.py` **sí** se versiona (no se acota) porque el cambio pendiente de
`api/market_harvest.py` — un fichero ya versionado — lo importa: dejarlo fuera rompería el árbol.

### 14.2 `git diff --stat` y `git diff --check`

* `git diff --stat` — sin cambios sin preparar (`git status --short` vacío).
* `git diff --check` — **exit 0**, sin errores de espacios en blanco.

### 14.3 Auditoría previa al commit

* **Secretos:** barrido sobre todos los ficheros preparados (claves privadas, `AKIA…`, JWT,
  `sk-…`, bearer tokens, URIs con contraseña, `service_role_key`, asignaciones
  `secret|password|api_key|hmac_key|token` de ≥24 caracteres) → **0 hallazgos**. Ningún secreto real
  ⇒ no se activó el STOP. El PDF ejecutivo además pasa el control de fugas técnicas de
  `auditar_ejecutivo` (`§8 PATRONES_PROHIBIDOS`, incluido `ARHIAX_EVIDENCE_HMAC_KEY`).
  Barrido adicional sobre **todo el árbol versionado**
  (`git grep -E "gho_…|ghp_…|github_pat_" <commit>`): **sin coincidencias** ⇒ ninguna credencial
  quedó versionada (ver §14.5).
* **Temporales/cachés:** los ficheros de trabajo propios (`_*.py`, `_smoke_out/`) se eliminaron; los
  temporales preexistentes quedan ignorados.
* **Evidencia contractual:** no se borró ningún artefacto. Los tres desplazados a `legacy/`
  conservan sus bytes (§11).

### 14.4 Diferencia ambiental declarada (no es cambio de código)

La corrida canónica se ejecutó sin salida de red hacia `OSM_OVERPASS` (el contenedor de build no
alcanza ese host). El harvest de equipamiento cayó a `PHOTON_OSM` y el estado declara
`5 ítem(s)` en lugar de los 12 de la corrida previa. Es una **diferencia de entorno del
artefacto**, no una modificación de adquisición, screening, solar ni de ningún motor: el mismo
código, con red completa, reproduce el harvest. Se declara para que el revisor no lo interprete
como una pérdida de contenido introducida por este bloque.

### 14.5 HALLAZGO DE AUDITORÍA — credencial real en `.git/config` (ACCIÓN REQUERIDA)

La auditoría de secretos detectó una **credencial real** (token OAuth de GitHub, prefijo `gho_`)
embebida en la URL del remote:

```
.git/config:9   url = https://<usuario>:gho_…@github.com/alissduran/arhiax-RE.git
```

**No es una fuga de este bloque y no afecta al veredicto:**

* `.git/config` **no está versionado** y git lo excluye por diseño
  (`git ls-files --error-unmatch .git/config` → `did not match any file(s) known to git`).
* `git grep` sobre el commit publicado buscando `gho_…`/`ghp_…`/`github_pat_` → **0 coincidencias**:
  la credencial **no** viajó a ningún commit, ni a `docs/`, ni a los artefactos.
* El barrido de los ficheros preparados dio 0 hallazgos: **no se commitó ningún secreto**, por lo
  que no se activó el STOP.

**Acción recomendada (fuera del alcance del Bloque 1, decisión del titular):**
rotar `gho_WdTD…` en GitHub (Settings → Developer settings → Tokens) y sustituir la URL con
credencial embebida por un credential helper (`git config --global credential.helper manager`) o por
SSH, para que el token no quede en claro en el disco ni en `.git/config`.

### 14.6 VEREDICTO

```
BLOCK 1 — TRUTH RESOLUTION CLOSED
```

**Criterio · esperado · real · `file:line` · artefacto · prueba**

| Criterio | Esperado | Real | `file:line` | Artefacto | Prueba |
|---|---|---|---|---|---|
| Significado del «6» determinado sin inferir | métrica distinta y válida (caso B) | `attributes_compared_count = 6` = 2 conflictos verdaderos + 4 diferencias materiales explicadas | `api/dictus_secciones.py:328-384`, `:689`, `:747`; `api/dictus_historia.py` `get_true_conflict_summary` | `DICTUS_RUN_STATE_040-646406.json` | `test_true_conflict_count_equals_len_true_conflicts` |
| Dos rótulos inequívocamente distintos | «3 rótulos prohibidos» disjuntos entre métricas | «2 atributo(s) requieren reconciliación histórica» vs «6 atributo(s) comparados históricamente» | `api/dictus_historia.py:972,976` | `DICTUS_EJECUTIVO_040-646406.pdf` p.1 | `test_pdf_prints_canonical_true_conflict_count` |
| Frase legacy ausente | `atributo(s) con resultados incompatibles` no presente | ausente en las 6 páginas y en `api/*.py` | `api/dictus_secciones.py:762` | `DICTUS_EJECUTIVO_040-646406.pdf` | `test_pdf_does_not_print_legacy_conflict_count_as_current` |
| Una sola verdad canónica con la forma pedida | 9 campos + invariante | presente y verificada | `api/dictus_historia.py` `get_true_conflict_summary` | `historical_consistency_summary` | `test_true_conflict_count_equals_len_true_conflicts` |
| `true_conflict_count == len(true_conflicts)` siempre | igualdad | `2 == 2` en las 4 etapas | `api/dictus_historia.py` (assert interno) | RunState / Manifest / Modelo | `test_all_stages_report_the_same_pair` |
| El contador sale de `len(canonical_true_conflicts)` | nunca hardcode/string/legacy | derivado; el contador legacy divergente **levanta** | `api/dictus_historia.py`, `api/dictus_secciones.py:1017` | `historical_consistency_summary` | `test_legacy_persisted_counter_cannot_diverge` |
| Función única consumida por todas las páginas | un solo resolvedor | `get_true_conflict_summary` + rótulos leídos por las páginas | `api/dictus_entrega.py`, `api/dictus_manifiesto.py`, `api/dictus_secciones.py` | RunState → modelo → PDF | suites 1–4 |
| `runstate == manifest == model == pdf` y mismos atributos | igualdad 4×2 | `2 / 2 / 2 / 2` y `["altura_maxima","coordenada"]` | §7, §9 | 4 artefactos | `test_all_stages_report_the_same_pair` |
| El PDF no calcula el contador | sólo imprime valor resuelto | `RecuentoNoResuelto` si falta; sin sustituto legacy | `api/dictus_ejecutivo.py:984-999` (post-fix) | PDF p.1 | `test_pdf_does_not_recompute_the_counter` |
| Un solo Dictus vigente sin ambigüedad | 1 ejecutivo / 1 `run_id` | 1 (`DX-040-646406-20261002`, `04b364d4…`) | `scripts/dictus_artifact_index.py` | `ARTIFACT_INDEX_040-646406.json` | `test_un_solo_run_id_current` |
| Legacy conservado con bytes idénticos | `sha256_before == sha256_after` | 8/8 idénticos | `scripts/dictus_legacy_canonicalize.py` | `legacy/**` | `test_legacy_no_se_trata_como_current` |
| Suite bloqueante | todo PASS | 74 + 9 + 5 + 11/11, exit 0 | — | — | suites 1–4 |
| Árbol final limpio y pusheado | `git status --short` vacío | vacío; `git diff --check` exit 0 | — | — | — |

**Sin fallos abiertos del Bloque 1.** Los dos únicos elementos no verdes del repositorio están
declarados y fuera de alcance: (a) `test_gpv_f77` falla idéntico en el baseline (§12.1);
(b) `POI` degradado por red ausente en el entorno de build (§14.4).

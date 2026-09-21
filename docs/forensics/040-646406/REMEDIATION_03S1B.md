# REMEDIATION 03S.1B — MATCHING SAFETY MICRO-CLOSURE

Baseline: 03S.1A implementado. Cierra cuatro defectos residuales del core
sancionatorio antes de congelarlo. NO se amplió alcance (sin PEP, UE, SIREL,
catastro/valoración) y no se rediseñó el screening.

---

## 1-3. BLOCKER — MISMO VALOR ≠ IDENTIFICADOR COMPATIBLE

**Defecto reproducido**: `JUAN PEREZ` con `cc 12345678` frente a un registro de la
lista `JUAN PEREZ` con identificador `pasaporte 12345678` devolvía **STRONG_MATCH**
("documento coincidente").

Causa raíz: la unidad de comparación era la mera **intersección de valores
normalizados** en dos sitios:

```python
# _conflicto_identificadores: si los números coincidían, NO había conflicto
if rec_variants and subj_variants:
    if not (rec_variants & subj_variants):   # ← sin tipo
        ...
# _atributo_corroborante: cualquier intersección corroboraba
if rec_variants & subj_variants:
    return "documento coincidente"           # ← sin tipo
```

**Corregido** — la unidad de comparación ahora es
**(tipo-compatible, valor normalizado)**, con dos helpers explícitos:

- `_ids_compatibles_exactos(env, rec)`: identificadores del registro que coinciden
  en valor **y** en tipo (un tipo vacío en la lista sigue siendo comodín).
- `_ids_mismo_valor_tipo_incompatible(env, rec)`: identificadores con el mismo
  valor pero tipo **incompatible** (cédula vs pasaporte).

Reglas implementadas:
1. Si existe **al menos un identificador compatible exacto** → no hay conflicto
   (un ID incompatible adicional **no** invalida uno compatible: §5).
2. Si el **único** valor coincidente pertenece a un tipo incompatible →
   `conflict=True` con motivo `IDENTIFIER_TYPE_MISMATCH (<tipo>)`.
3. Si el registro trae identificadores y ninguno coincide en valor: mismo tipo →
   `DOCUMENT_MISMATCH`; tipos distintos → `IDENTIFIER_TYPE_MISMATCH`.
4. El paso de identificador exacto ya exigía compatibilidad de tipos; el paso de
   "variante de formato" numérica también (por eso el caso del blocker ya no cae a
   `STRONG_MATCH`).
5. `_atributo_corroborante` solo corrobora por documento cuando el valor coincide
   **y** el tipo es compatible (`"documento coincidente (tipo compatible)"`).
   `CC 123` frente a `PASSPORT 123` **no** es corroboración.

Resultado del caso reportado:

```
JUAN PEREZ / cc 12345678  vs  JUAN PEREZ / pasaporte 12345678
  → REVIEW_REQUIRED · conflict=True
    reasons = ("nombre exacto", "conflicto de identificadores: IDENTIFIER_TYPE_MISMATCH (pasaporte)")
```

Nunca `EXACT_MATCH` ni `STRONG_MATCH` "por documento coincidente".

## 4-5. Tests específicos

- **§4** nombre exacto + mismo número + tipo incompatible → `REVIEW_REQUIRED`,
  `conflict=True`, con `IDENTIFIER_TYPE_MISMATCH` y **sin** "documento
  coincidente"; se comprueba además que no aparece `STRONG_MATCH`.
- **§5** control multi-ID: `pasaporte ZZ999` + `cc DOC-2` frente a un sujeto
  `cc DOC-2` → `EXACT_MATCH` legítimo (`conflict=False`).
- Extras de la misma familia: mismo tipo con valor distinto → `DOCUMENT_MISMATCH`;
  tipo no declarado por la lista (comodín) → `EXACT_MATCH`; variante de formato
  numérica con tipo incompatible → nunca EXACT/STRONG.

## 6. `force_refresh` FALLIDO: la frescura es EDAD, no éxito del refresco

**Defecto**: en el fallback se aplicaba
`fresh = STALE_ALLOWED if permitir_stale else STALE_NOT_ALLOWED`, de modo que un
refresco fallido sobre una caché de 5 minutos reportaba `STALE_ALLOWED`.

**Corregido**: en el fallback se **vuelve a evaluar** la frescura real
(`evaluar_frescura`) y se aplica la política:

| caché | refresco | política | resultado |
|---|---|---|---|
| vigente (5 min) | falla | — | **CACHED_FRESH** + datos servidos |
| vencida | falla | stale permitido | **STALE_ALLOWED** + datos servidos |
| vencida | falla | stale prohibido | **STALE_NOT_ALLOWED** + sin datos |

Además se añade `SanctionsSnapshot.refresh_error`: el fallo del intento de
actualización se declara **aparte** de `error` (que queda en `None` cuando sí hay
dato). Se limpia cuando el refresco no se intenta o cuando el snapshot vigente se
sirve sin refrescar, y se expone en `ScreeningSummary.extra["refresh_errors"]` y
en una nota del capítulo 09.2 del dictamen.

## 7. SEMÁNTICA DE EVIDENCIA SEPARADA

Tres propiedades independientes (antes: dos, con `reproducible` atada al sellado):

| propiedad | definición |
|---|---|
| `evidence_complete` | `created == expected` (y `expected > 0`) |
| `evidence_sealed` | `evidence_chain_status == SEALED` |
| `evidence_reproducible` | `evidence_complete` **y** los hashes presentes en cada envelope (`subject_hash`, `snapshot_sha256`, `query_hash`, `evidence_hash`) |

- `NOT_REQUIRED_DEV`: `evidence_sealed = False` (**nunca** se describe como
  sellado) y `evidence_reproducible` puede ser `True`.
- `evidence_errors` es un campo del resumen y se declara en el dictamen
  (09.3) y en los receipts.

## 8. AISLAMIENTO DE LA CREACIÓN DE EVIDENCIA

La creación de envelopes ya no está dentro de un único `try`: cada outcome
sujeto×fuente se intenta **individualmente** y el fallo de uno no aborta los
siguientes. Se registra `evidence_errors = [{subject_id, source_id, error}]`.

Verificado: con un fallo en el 4.º de 9 → **8 EvidenceRecords creados**, 1 entrada
en `evidence_errors`, `evidence_complete=False`, `evidence_chain_status=FAILED`
(la cadena no puede sellarse con el conjunto incompleto), `evidence_sealed=False`,
`evidence_reproducible=False` como conjunto — cada uno de los 8 envelopes conserva
sus hashes — y el motivo lo declara ("N envelope(s) de evidencia no se pudieron
crear").

## 9. Tests bloqueantes

`tests/test_remediacion_03s1b.py` (16 casos) cubre A–G y los extras:

| # | caso | resultado verificado |
|---|---|---|
| A | nombre exacto + mismo número + tipo incompatible | `REVIEW_REQUIRED`, `conflict=True`, `IDENTIFIER_TYPE_MISMATCH` |
| B | mismo número + tipo compatible | `EXACT_MATCH` |
| C | un ID incompatible + un ID compatible exacto | `EXACT_MATCH` |
| D | refresco falla + caché vigente | `CACHED_FRESH` + `refresh_error` + datos |
| E | refresco falla + caché vencida | `STALE_ALLOWED` / `STALE_NOT_ALLOWED` según política |
| F | `NOT_REQUIRED_DEV` | `complete=True`, `sealed=False`, `reproducible=True` |
| G | falla 1 de 9 creaciones de evidencia | 8 envelopes creados, `evidence_errors` con el fallo |

Extras: sellado real exige `SEALED`; reproducibilidad exige los cuatro hashes;
`refresh_error` no contamina el snapshot guardado; sin intento de descarga no hay
`refresh_error`.

## 10. Regresión

- `python -m compileall api tests` → exit 0
- `python -m pytest -m "not network" tests/` → **540 passed, 0 failed,
  11 deselected** (línea base 524 → +16)

## 11. Verificación EN VIVO posterior

Se repitió la prueba de dos fases con las tres fuentes oficiales: fase 1
(`force_refresh`) `LIVE_FRESH` y fase 2 (sin refresh) `CACHED_FRESH`, sin cambios
de contrato. El screening del caso Golden conserva 3/3 sujetos, evidencia 9/9 y
cobertura completa.

## Lo que NO se tocó

Alcance sin cambios: `OFAC_NON_SDN` declarado y no consultado, `EU_CONSOLIDATED`
opcional por archivo, PEP/UE/SIREL/WorldCheck/Truora fuera, numerales de la CBJ
sin verificar y por tanto no impresos, PEP sigue `OUT_OF_SCOPE_FOR_SCREENING`
(aunque su categoría ya sea `PEP_REGISTRY`). No se tocó catastro, valoración ni
urbanismo. No se inició SLICE-002.

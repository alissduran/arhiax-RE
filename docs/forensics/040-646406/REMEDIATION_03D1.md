# REMEDIATION 03D.1 — Closure Patch: confianza de identidad + gate de valoración PH

Cierre de las inconsistencias restantes de la remediación forense 03D. No toca
constantes de mercado, no inicia SLICE-002 y no limpia artefactos ajenos.

## Bloqueos corregidos

### BLOCKER A — PH valuation gate (fail-closed)
Antes: `unidad_ph_no_resuelta = presente and (resolution_status not in (None, "EXACT", "PARTIAL"))`
— `None` y `PARTIAL` autorizaban valorar una unidad PH (error).

Ahora: el gate consume la **confianza normalizada** del modelo canónico
(`canonical.resolution_confidence`) y solo `VERIFIED_UNIT_IDENTITY` autoriza
valorar. `None / PARTIAL / AMBIGUOUS / UNRESOLVED / CONTEXT_ONLY / CONFLICT`
bloquean la estimación de mercado de precisión aparente.

### BLOCKER B — no escalar PARTIAL a identidad verificada
`build_canonical_property_identity` ya no infiere `MATCH_BY_NUPRE` por el solo
hecho de que el CTL contenga NUPRE. El estado y la confianza incorporan el
resultado real del resolver: `PARTIAL → PARTIAL_IDENTITY`, nunca `VERIFIED`.

### BLOCKER C — separación de identificadores
`nupre` (alfanumérico, AFT...) y `codigo_catastral` (número predial 15-30
dígitos) son campos distintos. Nunca se guarda un número predial dentro de
`nupre`. Cada identificador conserva `value / source / match_status`
(`canonical.identificadores`). Los geoportales que nombran `nupre` al número
predial (Pasto) se reclasifican por su forma (solo dígitos).

## Modelo de estado canónico (única autoridad)

```text
raw resolver result (resolution_status / resolucion / identidad)
        ↓
canonical identity (resolution_status + resolution_method + resolution_confidence)
        ↓
valuation gate (canonical.unidad_ph_no_resuelta)
```

Confianza normalizada (semántica mínima, independiente del vocabulario por ciudad):

| Confianza                  | Significado                              | ¿Valora unidad PH? |
|----------------------------|------------------------------------------|--------------------|
| VERIFIED_UNIT_IDENTITY     | unidad específica verificada (exacto/matrícula/nomenclatura) | sí |
| PARTIAL_IDENTITY           | candidato único sin match exacto         | no |
| CONTEXT_ONLY               | solo contexto espacial                   | no |
| AMBIGUOUS                  | varios candidatos                        | no |
| UNRESOLVED                 | sin registro / sin resolver              | no |
| CONFLICT                   | conflicto de identidad                   | no |

## Downstream features[0] — auditoría (semántica)

- `consultar_construccion`: `SAFE_SINGLE_LAYER` (huella de construcción). Proviene
  solo de geometría → `resolution_method = spatial`.
- `consultar_condicion_destino`: `VALUATION_CRITICAL`. Precedencia corregida:
  lookup EXACTO por identificador (`terreno='código'`) ANTES que intersección de
  punto; el fallback espacial se marca `resolution_method = spatial`.
- `consultar_entorno_urbano`: `SPATIAL_CONTEXT`. Si una capa devuelve features
  incompatibles, NO se elige la primera: se consolida solo cuando coinciden y si
  discrepan se marca `AMBIGUOUS_CONTEXT` (el valor queda None).

## Identificadores propagados

`canonical_property_identity` ahora expone: `resolution_status`,
`resolution_method`, `resolution_confidence`, `codigo_catastral`, `nupre` e
`identificadores`. Consumidores actualizados para no mezclar identificadores:
`consistency`, `finding_registry`, `receipts`, `titulux_bridge`.

## No se hizo

- No se cambió `valor_m2`, YAML Lonja, cap_rate, M1/M2/M3 ni bandas de mercado.
- No se restauró 70/30 ni se hardcodeó 040-646406 / Miramar / TO 8 AP 430 / 399.5M.
- No se eliminó `features[0]` mecánicamente (se clasificó por rol semántico).

## Tests

`tests/test_remediacion_03d1.py` (15 casos): separación de identificadores,
no-escalación de confianza, propagación de resolution_status/method/confidence,
gate PH (A–F), no-resolver-data y caso dorado de unidad.

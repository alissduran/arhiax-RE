# REMEDIATION 03G — EXACT IDENTITY RECOVERY

Golden 040-646406: `codigo_catastral = 080010103000010040001908040002`,
`nupre = AFT0005BOHA`. Objetivo: por qué dos identificadores exactos del CTL no
resuelven el predio, y recuperar identidad/valoración si la fuente oficial lo
confirma. **No bypass del gate, no hardcodeo.**

## 1. BUG DE PRECEDENCIA (corregido)

`consultar_predio_por_codigo()` ejecutaba: exact código → **prefix/fuzzy** → NUPRE
(solo si el prefix no traía features). Con exact código `[]` + prefix `5` + exact
NUPRE `1`, el NUPRE quedaba SALTADO (porque el prefix ya traía candidatos) y el
resolver devolvía `AMBIGUOUS` (5 candidatos) en vez de `EXACT` (por NUPRE).

**Fix:** jerarquía exactos-primero — A. exact código → B. exact NUPRE → (C/D no
aplican: la firma no recibe anterior/otros) → E. prefix/fuzzy SOLO si ningún
exacto produjo candidatos → F. contexto espacial fuera del resolver.

Ahora: `exact code=[] + exact NUPRE=1` → `EXACT` (method=nupre), sin ejecutar el
prefix. `exact code=[] + exact NUPRE=[] + prefix=5` → `AMBIGUOUS` (bloqueado).

## 2. RESOLUTION TRACE

Cada query registra evidencia en `res["resolution_trace"]`:
`{query, field, operator, value, source_disponible, error, candidate_count,
returned_*}` + una entrada `seleccion` con `resolution_status`/`resolution_method`.
`res["resolution_method"]` ∈ `codigo_catastral | nupre | prefix_unico_candidato`.

## 3. SCHEMA DE CAPA 500 — NO VERIFICADO

El código ASUME que `codigo_homologado` es el campo del NUPRE alfanumérico
(AFT...), y que `numero_predial_nacional` es el número de 30 dígitos. **No hay
documentación del schema real en el repo** (solo `docs/AUDITORIA_INTEGRACION_PASTO.md`
para el geoportal de PASTO, un servicio distinto). No se pudo consultar la
metadata en vivo (SOURCE_UNAVAILABLE).

**Hipótesis de root cause (no confirmadas, requieren red):**
- (a) bug de precedencia — **corregido y cubierto por tests**.
- (b) servicio no disponible — confirmado desde este sandbox (ver §4).
- (c) `AFT0005BOHA` vive en otro campo distinto de `codigo_homologado`
  (SCHEMA_MAPPING_ERROR) — pendiente de verificar contra la metadata.

## 4. LIVE GOLDEN TEST — SOURCE UNAVAILABLE

`test_catastro_predio_vivo_040_646406` (marcado `network`) consulta el servicio
real. Ejecutado en este entorno, el trace registra las 3 queries con
`source_disponible=False` y `error="servicio sin respuesta"`:

```text
A_exact_codigo  numero_predial_nacional='080010103000010040001908040002' -> 0 candidates (sin respuesta)
B_exact_nupre   codigo_homologado='AFT0005BOHA'                          -> 0 candidates (sin respuesta)
E_prefix_codigo numero_predial_nacional LIKE '...%'                      -> 0 candidates (sin respuesta)
seleccion       UNRESOLVED
```

El servicio catastral de Barranquilla NO es alcanzable desde este sandbox
(SOURCE_UNAVAILABLE). El test NO hace skip silencioso: distingue
SOURCE_UNAVAILABLE (sin respuesta) de NO_MATCH (respondió sin match).

## 5. RESULTADO

```text
SOURCE UNAVAILABLE
```

El bug de precedencia quedó corregido y verificado offline; la recuperación de
identidad exacta (y la validación del schema `codigo_homologado == NUPRE`)
requiere ejecutar el network test desde un entorno con acceso al servicio de
Barranquilla.

## Tests

`tests/test_remediacion_03g.py`:
- `test_exact_nupre_resuelve_sin_ser_saltado_por_prefix` (#4).
- `test_sin_exactos_prefix_multiple_es_ambiguo` (#5).
- `test_exact_codigo_tiene_precedencia_sobre_nupre`.
- `test_trace_registra_fuente_disponible`.
- `test_catastro_predio_vivo_040_646406` (network, loud SOURCE_UNAVAILABLE/NO_MATCH).

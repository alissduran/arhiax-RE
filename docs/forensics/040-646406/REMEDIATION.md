# REMEDIATION — 040-646406 (identidad predial → catastro determinista → gate de valoración)

Corrige la degradación de identidad demostrada en la investigación forense, sin
tocar constantes de mercado ni recuperar artificialmente el precio anterior.

## Cambios

### 1. Parser de unidad no destructivo — `api/unidad_inmobiliaria.py` (nuevo)

`extraer_unidad(direccion)` extrae `torre` / `apartamento` / `unidad` y DERIVA
`direccion_base` sin sobrescribir `direccion_raw`. `TV 43 # 100-50 TO 8 AP 430` →
base `TV 43 # 100-50`, torre `8`, apartamento `430`.

### 2. `legal_analyzer.py` — extracción de dirección no destructiva

Eliminado el `re.split(...)` destructivo. `res["direccion"]` conserva la dirección
COMPLETA (con unidad); se añaden `direccion_base`, `torre`, `apartamento`, `unidad`.

### 3. `canonical.py` — identidad extendida

`canonical_property_identity` añade `direccion_raw`, `direccion_base`, `torre`,
`apartamento`, `unidad` (de la evidencia del CTL). `SAME_BUILDING_DIFFERENT_UNIT`
queda representable.

### 4. `catastro_predio.py` — selección explícita de feature

Se sustituye `features[0]` por `_seleccionar_predio()`: match exacto de
`numero_predial_nacional` / `codigo_homologado` (EXACT) > único candidato (PARTIAL)
> múltiples sin exacto (AMBIGUOUS, NO elegir arbitrario). Se añade `resolution_status`
al resultado.

### 5. Gate de valoración — `dictamen_data.py` + `pdf_compiler.py`

Si hay evidencia de UNIDAD PH (torre/apartamento/unidad) y la resolución catastral no
es EXACT/PARTIAL, `get_valuation` devuelve `metodologia_aplica=False` y el dictus
muestra **"ESTIMACIÓN REFERENCIAL NO EMITIDA"** (no un precio de precisión aparente).

## Regla de no destrucción

```text
raw evidence  →  structured derivation  (OK)
raw evidence  →  destructive regex  →  information lost  (prohibido)
```

## Tests (tests/test_remediacion_03d.py)

- Preservación de dirección (raw + base + torre/apartamento).
- Unidades distintas (430 vs 431) no producen la misma identidad.
- Match exacto de código gana y es independiente del orden del array.
- Ambiguo sin match exacto → `AMBIGUOUS` (no `features[0]`).
- Gate: unidad PH no resuelta → `metodologia_aplica=False`.

### Tests de regresión CTL actualizados

`test_ctl_medellin_bogota.py::test_direccion_catastral_prioritaria` y
`test_carga_hipoteca_ctl.py::test_analisis_extrae_la_catastral_no_la_alternativa`
codificaban el comportamiento destructivo anterior (`direccion == "DG 61B 20 04"`).
Ahora verifican el nuevo contrato: `direccion == "DG 61B 20 04 AP 401"` (preservada),
`direccion_base == "DG 61B 20 04"` y `apartamento == "401"`, manteniendo la
preferencia por la etiqueta DIRECCION CATASTRAL sobre la placa alternativa.

## No se hizo

- No se restauró 70/30 (etiqueta histórica sin efecto en fórmula).
- No se cambió `price/m²`, comparables, cap_rate ni constantes de mercado.
- No se hardcodeó 040-646406, Miramar, TO 8 AP 430 ni 399.5M.

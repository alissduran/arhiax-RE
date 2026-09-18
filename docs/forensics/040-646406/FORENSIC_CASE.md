# FORENSIC CASE — 040-646406 (Torre 8, Napoli, Miramar)

Investigación de regresión: el mismo inmueble pasó de ~$399,5M a ~$305,5M.

## Resumen ejecutivo

La caída **NO es un cambio de algoritmo de valoración** (la fórmula de consolidado
fue siempre `área × precio/m²`, M1 100%). La caída es, íntegramente, una
**degradación de la identidad/contexto del inmueble**: el barrio pasó de **Miramar**
(`6.800.000 COP/m²`) a **PENDIENTE** (`5.200.000 COP/m²` por fallback de estrato).

Esa degradación es causada por la **pérdida de la unidad inmobiliaria** en la
dirección: `TV 43 # 100-50 TO 8 AP 430` → `TV 43 # 100-50`, que a su vez hace que la
resolución catastral deje de identificar el predio exacto (aparecen 5 features y se
degrada barrio/tipología/PH/estrato).

## Clasificación (ver ROOT_CAUSE.md)

```text
IDENTITY_REGRESSION          (primaria)
CATASTRO_RESOLUTION_REGRESSION
VALUATION_PARAMETER_CHANGE   (consecuencia: precio/m² 6.8M -> 5.2M)
REPORTING_ONLY_BUG           (etiqueta 70/30 -> 100/0, sin efecto en la fórmula)
```

## Evidencia clave

- `api/legal_analyzer.py:289-299` — extracción de dirección que **descarta la
  unidad/edificio** (split sobre `APARTAMENTO|APTO|AP|EDIFICIO|TORRE|...`).
- `api/dictamen_data.py:get_valuation` — `val_m2_mercado` por sector (Lonja BAQ) con
  fallback `estrato_map {4: 5_200_000}`.
- Timeline git: `f247a20` (07-Sep, "preferir la DIRECCION CATASTRAL") introduce la
  pérdida de unidad; `64dbb5c`/`3654681`/`e58eefd` (11-14-Sep) cambian la ETIQUETA de
  metodología (no la fórmula).

## Relación con SLICE-001

```text
UNRELATED_TO_SLICE001
```

El contrato canónico de Case **nunca** almacenó `torre/apartamento/tipología/PH`
(no existen como columnas de `dictamenes` ni como campos del objeto `localStorage`
previo). Esos atributos siempre se derivaron del CTL + catastro en el pipeline de
generación. La regresión fue introducida por commits de identidad/valoración de
07-14 Sep, anteriores a SLICE-001 (18 Sep).

## Ver el detalle

- `INPUT_DIFF.md` — variables que cambiaron entre los dos dictus.
- `PIPELINE_TRACE.md` — primer punto de divergencia (dirección).
- `VALUATION_DIFF.md` — descomposición matemática de M1 y M3.
- `ROOT_CAUSE.md` — cadena causal demostrada.

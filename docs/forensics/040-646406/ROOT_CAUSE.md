# ROOT_CAUSE — 040-646406

## Clasificación

```text
IDENTITY_REGRESSION               (primaria)
CATASTRO_RESOLUTION_REGRESSION    (secundaria, downstream)
VALUATION_PARAMETER_CHANGE        (consecuencia: precio/m²)
REPORTING_ONLY_BUG                (etiqueta 70/30, sin efecto)
```

## Cadena causal (demostrada en lo ejecutable)

```text
f247a20 "Direccion oficial: preferir la DIRECCION CATASTRAL del CTL"
  ↓
legal_analyzer.py:291-293 re.split descarta unidad/edificio/torre
  ↓
"TV 43 # 100-50 TO 8 AP 430"  ->  "TV 43 # 100-50"
  ↓
la identidad de la UNIDAD PH se pierde en la extracción
  ↓
catastro resuelve sin unidad (5 features, sin identidad exacta)
  ↓
barrio Miramar -> PENDIENTE; destino Habitacional -> PENDIENTE; estrato 4 -> "No aplica"
  ↓
get_valuation: sector Miramar (6.8M/m²) -> fallback estrato 4 (5.2M/m²)
  ↓
M1 407.49M -> 311.61M ; M3 446.7M -> 341.6M
  ↓
consolidado 399.5M -> 305.5M
```

## Relación con SLICE-001

```text
UNRELATED_TO_SLICE001
```

Evidencia: la tabla `dictamenes` **no tiene** columnas `torre/apartamento/tipologia/PH`;
el objeto Case del `localStorage` previo tampoco las tenía. Esos atributos se derivan
del CTL (`legal_analyzer`) y del catastro (`catastro_predio`) en el pipeline de
generación, no del Case. El commit `f247a20` (07-Sep) y los de valoración (11-14-Sep)
son **anteriores** a SLICE-001 (18-Sep).

## Hipótesis NO confirmadas (quedan abiertas)

1. La fecha exacta del dictus anterior (08-Sep es aproximada); el FDP `f247a20` es
   de 07-Sep, por lo que el dictus anterior pudo haberse generado antes de ese commit.
2. Por qué la resolución catastral degrada a 5 features (¿el CTL no traía código/NUPRE,
   o cambió el servicio externo de Barranquilla?). No se pudo reproducir sin el CTL real
   y el endpoint catastral en vivo.

## Qué se necesita para confirmar el 100% (fase siguiente)

- El CTL real de 040-646406 (hash) para ambos dictus.
- Un dump del Case + del `db_record` de cada generación.
- Traza de `enriquecer_desde_ctl` (¿código/NUPRE presente?, ¿cuántas features?, ¿cuál se eligió?).

## Regla de parada

No se modifica código de producto en esta fase. La remediación (`FORENSIC REMEDIATION`)
deberá partir exclusivamente de las causas aquí demostradas.

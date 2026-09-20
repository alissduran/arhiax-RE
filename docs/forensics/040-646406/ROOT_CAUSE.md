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

## Auditoría de resolución catastral (evidencia ejecutable)

`api/catastro_predio.py`:

- `_query_capa` / `_query_punto` usan `resultRecordCount = max_features = 5` → la
  consulta devuelve **hasta 5 features** (sin scoring de coincidencia; solo un límite).
- La selección de feature es `features[0]` (la primera, **sin criterio de identidad**):
  `consultar_predio_por_codigo` (línea 217), `consultar_construccion` (323),
  `consultar_condicion_destino` (353, 359, 368, 374), `consultar_entorno_urbano`
  (403, 413, 423).
- `enriquecer_desde_ctl`: si el lookup por código/NUPRE falla, el entorno se resuelve
  por coordenadas *hint* → `consultar_entorno_urbano(lat, lon)` por punto → intersecta
  el edificio y sus vecinos → `features[0]` elige uno arbitrario.

**Conclusión:** el patrón `exact lookup fails → fallback espacial → features[0]` EXISTE
y coincide con el "5 features" observado (límite `resultRecordCount=5`). Riesgo crítico.

## Auditoría de identidad predial (api/canonical.py)

`canonical_property_identity` NO distingue estructuralmente edificio / predio matriz /
unidad PH. Tiene `nomenclatura` (string que PUEDE incluir la unidad) y
`propiedad_horizontal` (bool), pero **no** campos `torre` / `apartamento` / `unidad`.
La unidad solo vive en la cadena de dirección, que `legal_analyzer` descarta.
→ `SAME_BUILDING_DIFFERENT_UNIT` no es representable hoy.

## Hipótesis NO confirmadas (quedan abiertas)

1. La fecha exacta del dictus anterior (08-Sep es aproximada); el FDP `f247a20` es
   de 07-Sep, por lo que el dictus anterior pudo haberse generado antes de ese commit.
2. Por qué la resolución catastral degrada a 5 features (¿el CTL no traía código/NUPRE,
   o cambió el servicio externo de Barranquilla?). No se pudo reproducir sin el CTL real
   y el endpoint catastral en vivo. (El "5 features" queda explicado como el límite
   `resultRecordCount=5` + selección `features[0]`; lo que falta confirmar es por qué
   falló el lookup exacto por código.)

## Qué se necesita para confirmar el 100% (fase siguiente)

- El CTL real de 040-646406 (hash) para ambos dictus.
- Un dump del Case + del `db_record` de cada generación.
- Traza de `enriquecer_desde_ctl` (¿código/NUPRE presente?, ¿cuántas features?, ¿cuál se eligió?).

## Regla de parada

No se modifica código de producto en esta fase. La remediación (`FORENSIC REMEDIATION`)
deberá partir exclusivamente de las causas aquí demostradas.

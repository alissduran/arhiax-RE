# REMEDIATION 03F.1 — POI truthful provenance + receipt semantics + appraisal cost

Cierra defectos residuales de 03F antes de regenerar el Golden Dictus.

## 1. RECEIPT POI (bug de join)

`receipt_rows()` hacía `", ".join(poi["categorias"])` sobre un **dict** (tras 03F),
imprimiendo las 4 claves como "CONSULTADO (Salud, Educacion, Comercio,
Recreacion)" aunque hubiera categorías NO_MATCH. Fix: se renderiza el estado real
por categoría:

```text
CONSULTADO · Salud AVAILABLE (3); Educacion AVAILABLE (2); Comercio NO_MATCH; Recreacion SOURCE_UNAVAILABLE
```

NO_MATCH ya no se presenta como "CONSULTADO CON RESULTADO".

## 2. SOURCE PROVENANCE en sección 03

`poi_source_label(pois)` deriva la fuente de los POI realmente renderizados:
- solo `OSM_OVERPASS` → `OpenStreetMap / Overpass API`
- solo `PHOTON_OSM` → `OpenStreetMap vía Photon`
- mixto → `OpenStreetMap / Overpass + Photon`

La sección 03 ya no imprime siempre `[FUENTE: OPENSTREETMAP OVERPASS API]`.

## 3. CATEGORY STATUS (NO_MATCH != SOURCE_UNAVAILABLE)

Nuevo contrato `POIResult`:

```text
get_poi_result(lat, lon, radius) -> {
  items, category_status, sources_attempted, sources_succeeded
}
```

- `AVAILABLE`: hay POIs.
- `NO_MATCH`: la fuente respondió correctamente y no encontró elementos compatibles.
- `SOURCE_UNAVAILABLE`: ninguna fuente completó una consulta confiable para esa categoría.

`get_nearby_pois()` queda como adapter backward-compatible (devuelve `items`).
`_pois_desde_photon()` devuelve `(resultado, ok_cats)` para transportar la
metadata de ejecución.

## 4. NARRATIVA

`get_cobertura_alert(..., pois, poi_status)` consume `category_status` y
diferencia:
- `NO_MATCH` → "No se encontraron equipamientos verificables de X dentro del radio consultado."
- `SOURCE_UNAVAILABLE` → "No fue posible completar la consulta de equipamientos de X durante esta ejecución."

## 5. COSTO DEL AVALÚO PROFESIONAL

Segunda investigación forense: una sola rama (`main`), sin tags, 185 commits;
grep de todo el árbol por `UVT|salario mínimo|porcentaje del valor|% del valor|
servicio profesional|costo del servicio|honorario|tarifa` → sin regla de costo
del servicio de avalúo (solo LTV 70% y componentes M2, no relacionados).

```text
APPRAISAL_COST_HISTORICAL_RULE = NOT_FOUND
```

Se prepara contrato vacío/configurable `api/appraisal_cost.py`
(`build_appraisal_cost_estimate()`) con `available/low_cop/central_cop/high_cop/
method/source/source_date/assumptions`, **sin cifras** (`available=False`) hasta
existir fuente. El costo del servicio es independiente de
`valuation_authorization.allowed`.

## 6. UNKNOWN/ZERO

Re-verificado: valuation bloqueada sin cuantía CTL → `Capital/Saldo/Cuota NO
ESTIMABLE`, `LTV NO CALCULABLE`; con cuantía CTL → capital/saldo/cuota estimables
pero `LTV NO CALCULABLE` (no 0%).

## Tests

`tests/test_remediacion_03f1.py` (13 casos): receipt con mezcla AVAILABLE/NO_MATCH/
SOURCE_UNAVAILABLE, source label (Overpass/Photon/mixto/vacío), NO_MATCH vs
SOURCE_UNAVAILABLE, unknown propagation (sin/con cuantía CTL), y contrato de
costo de avalúo vacío.

# REMEDIATION 03F — Product Capability Regression

Recupera capacidades útiles degradadas (sin revertir la regla PH gate, sin
tocar SLICE-002, sin cambiar parámetros de mercado).

## PROBLEM A — POI incompleto (completion per-category)

**Causa raíz:** `get_nearby_pois()` devolvía temprano ante la PRIMERA respuesta
Overpass válida; si Overpass traía solo algunas categorías (Salud/Educación) y
otras vacías (Comercio/Recreación), Photon nunca completaba las faltantes.

**Fix:**
- `merge_poi_sources(overpass, photon)`: preserva Overpass válido por categoría,
  rellena SOLO las categorías faltantes con Photon, deduplica por nombre
  normalizado, ordena por distancia y limita a 3 por categoría.
- `_pois_desde_photon(..., categorias=...)`: fallback PER-CATEGORY.
- `get_nearby_pois()` ahora completa las categorías faltantes con Photon antes
  de retornar (ya no devuelve temprano).
- Provenance: cada POI lleva `source = OSM_OVERPASS | PHOTON_OSM`.
- `poi_category_status(pois)`: estado por categoría `AVAILABLE | NO_MATCH`
  (una lista vacía NO se interpreta como "no existen parques").
- Receipt POI por categoría (`status + count`).

**Narrativa honesta:** `get_cobertura_alert(..., pois=...)` construye el texto
desde los resultados reales: lista solo las categorías verificadas y declara las
faltantes ("sin resultados verificables en las fuentes consultadas"), en vez de
afirmar siempre "comercio, salud, educacion y recreacion".

## PROBLEM B — Costo orientativo del avalúo profesional

**HISTORICAL APPRAISAL-COST FEATURE FOUND: NO.**

Búsqueda forense (git log `--grep` avaluo/honorarios/tarifa/RAA/costo, y grep de
todo el árbol por `honorario|tarifa|tarifario|costo orientativo|precio del aval|
servicio de aval`): no existe ninguna implementación histórica de una estimación
de "cuánto cuesta contratar el avalúo profesional". Los generadores legados
(`dictamen_napoli.py`, `dictamen_040314248.py`, `build_pdf2.py`,
`build_pdf_compiler.py`) solo referencian al "avaluador inscrito en el RAA" como
el profesional que firma, no un costo de su servicio.

**Acción:** NO se restaura (no se inventa una tarifa). Resultado:

```text
NEEDS_PRODUCT_SOURCE
```

Queda para decisión humana aportar la fuente/fórmula documentada si se desea
incluir "Costo orientativo del avalúo profesional".

## PROBLEM C — UNKNOWN convertido en ZERO

**Causa:** `estimar_carga_hipotecaria()` coaccionaba `valor_inmueble` inválido a
`0.0` y devolvía `capital=0, saldo=0, cuota=0, LTV=0`, que el Dictus mostraba como
deuda estimada de $0 (desinformación) cuando la valoración estaba bloqueada.

**Fix:**
- `estimar_carga_hipotecaria()` devuelve `available=False` y campos `None` cuando
  no hay base de valor (sin valor del inmueble ni cuantía del CTL).
- LTV: `None` (NO CALCULABLE) cuando no hay valor del inmueble, incluso si la
  cuantía del CTL permite estimar capital/saldo/cuota.
- `generar_tabla_carga()` renderiza "NO ESTIMABLE" / "NO CALCULABLE" en vez de $0.

`UNKNOWN != ZERO`: sin evidencia real de cero no se fabrica $0.

## No se hizo

- No se restauró "Parque Miramar" / "Centro Comercial Miramar" ni POIs fijos.
- No se inventó tarifa de avalúo.
- No se tocó: PH valuation gate, canonical identity, M1/M2/M3, cap rate, market
  YAML, catastro resolver, SLICE-001.

## Tests

`tests/test_remediacion_03f.py` (10 casos): merge POI per-category, dedup,
orden+limite, no-inventar, category status, receipt POI por categoría, y
UNKNOWN vs ZERO (sin base, valuation bloqueada, capital-conocido-LTV-no-calculable).
Actualizado `test_smoke_api.py` (UNKNOWN ya no es LTV 0).

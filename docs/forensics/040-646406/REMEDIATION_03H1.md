# REMEDIATION 03H.1 — MARKET CONTEXT INTEGRATION CLOSURE

Cierra las rutas que aún podían producir una valoración por fallback genérico.

## 1. BLOCKER corregido — LAT/LON order

`MarketContext` usaba `coordinates={"lat": lat, "lon": lon}` ANTES de que
`lat = lon = None` se inicializara (UnboundLocalError oculto por el except).
Se extrajo `resolve_market_location(...)` y se ejecuta ANTES de construir el
contexto; el bloque antiguo de resolución de coordenadas se eliminó (ya resuelto).

## 2. `resolve_market_location(...)` (market_context.py)

Devuelve `{authoritative_address, address_source, lat, lon, geocoder_source,
geocoder_confidence, coordinate_source}`. La dirección de mayor autoridad para
ubicación de MERCADO es la del registro oficial de adopción (si
`identity_source == OFFICIAL_ADOPTION_REGISTRY`); se geocodifica la BASE (sin
unidad PH) y se conserva la dirección completa.

`coordinate_source` ∈ {OFFICIAL_PREDIO, OFFICIAL_ADDRESS_GEOCODE,
FORM_ADDRESS_GEOCODE, DB_COORDINATES, BARRIO_DEMO, CITY_CENTROID}. Solo las
autorizadas (no demo/centroide) pueden alimentar el gate.

## 3. `get_valuation` fail-closed

Nuevo parámetro `valuation_authorized`:
- `False` → `metodologia_aplica=False` (motivo "valoración no autorizada…").
- `True` → calcula.
- `None` (default) → modo legacy (cálculo con fallback MARCADO), para adapters.

`pdf_compiler` pasa siempre `valuation_authorized=_valuation_authorized`
(explícito; fail-closed en producción).

## 4. Sin fallback 5.2M en sector exacto

Si `sector_match` existe pero `valor_central_m2` falta/inválido → `val_m2_mercado
= None` + `market_rate_match_type = MARKET_RATE_INVALID` → `get_valuation`
bloquea (nunca `.get("valor_central_m2", 5200000)`). El fallback por estrato
queda como referencia LEGACY marcada (`GENERIC_ESTRATO_FALLBACK`), nunca
autorizada.

## 5. Market rate value required

`_evaluate_ready` añade blocker `"market rate value missing/invalid"` cuando
`value_m2 is None or <= 0`.

## 6. Estrato 4

El estrato mágico 4 (`estrato = real_value or 4`) ya NO se propaga al
MarketContext: `estrato=(estrato if estrato_status==VERIFIED_OFFICIAL else None)`.
El contexto usa `estrato_status` (UNRESOLVED si no hay fuente oficial).

## Tests

`tests/test_remediacion_03h1.py` (7 casos): `resolve_market_location`
(authoritative address + centroide no verificado), golden pipeline (ready +
6.8M + address), golden negative (estrato SOURCE_UNAVAILABLE → blocked, no
default 4), malformed rate (value_m2 missing → blocked), y caller safety
(get_valuation sin autorización → bloqueado; autorizada → calcula con EXACT 6.8M).

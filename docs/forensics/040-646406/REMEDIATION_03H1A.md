# REMEDIATION 03H.1A — SINGLE-SOURCE MARKET CONTEXT CLOSURE

Cierra el wiring real del pipeline de contexto de mercado y elimina la autoridad
paralela/fallback implícito de la tasa.

## 1. `resolve_official_urban_context(ciudad, lat, lon, coordinate_source)`

Consulta OFICIAL de barrio/estrato/tratamiento (Barranquilla →
`catastro_predio.consultar_entorno_urbano`; Medellín → adapter equivalente). Es
CONTEXTO ESPACIAL, no identidad: funciona aunque `predio_real=None`. Solo se
ejecuta si `coordinate_source` está en la allowlist. Distingue:
`VERIFIED_OFFICIAL` / `CONFLICT` (AMBIGUOUS_CONTEXT) / `SOURCE_UNAVAILABLE`.

`consultar_entorno_urbano` ahora expone `campos_ambiguos` (qué campo discrepó).

## 2. Allowlist de coordenadas (corregida)

`coordinate_source_verified(s)` ahora es ALLOWLIST explícita (antes lista negra,
por lo que `None`/`"UNRESOLVED"` se colaban como verificadas):

- Autorizadas: `OFFICIAL_PREDIO`, `OFFICIAL_ADOPTION_ADDRESS_GEOCODE`,
  `CTL_ADDRESS_GEOCODE`.
- NO autorizadas: `None`, `UNRESOLVED`, `FORM_ADDRESS_GEOCODE`, `DB_COORDINATES`,
  `BARRIO_DEMO`, `CITY_CENTROID`.

## 3. No escalada de procedencia

`resolve_market_location` ya NO reetiqueta `lat_geo` preexistente como oficial.
Si el registro oficial aporta una dirección y no hay `OFFICIAL_PREDIO`, se
GEOCODIFICA ESA dirección (base, sin unidad PH) para marcarla
`OFFICIAL_ADOPTION_ADDRESS_GEOCODE`; si no se puede, se conserva el origen real
(`CTL_ADDRESS_GEOCODE`/`FORM_ADDRESS_GEOCODE`) y el gate bloqueará si no alcanza.

## 4. Única autoridad de la tasa de mercado

`get_valuation(..., market_context=..., valuation_authorized=...)` consume
exclusivamente `market_context.sector_metodologico` (value_m2 / matched_sector /
match_type) y `market_context.market_rate_source`. NO vuelve a abrir el YAML para
obtener value_m2; el YAML solo aporta cap_rate y factor de costos. Sin tasa
válida en el contexto → `MARKET_RATE_INVALID` (no 5.2M).

## 5. `get_valuation` fail-closed por defecto

`valuation_authorized=False` es el default: sin autorización explícita (o sin el
flag EXPLÍCITO `allow_legacy_reference=True`) → `metodologia_aplica=False`,
`consolidado=0`. El modo legacy exploratorio requiere `allow_legacy_reference=True`.

## 6. Estrato default eliminado del flujo canónico

El `estrato` mágico 4 ya no se propaga a MarketContext/valuation: se consume
exclusivamente el estrato VERIFICADO (contexto oficial o catastro en vivo). El
valor legacy queda solo para display.

## 7. Wiring en pdf_compiler

`resolve_market_location` (con `lat_geo_source=CTL_ADDRESS_GEOCODE`) →
`resolve_official_urban_context` → `build_market_context` (barrio/estrato
oficiales) → `get_valuation(market_context=...)`. Si el contexto oficial resuelve
barrio/estrato, se propagan a las variables de render (coherencia cross-chapter).

## Tests

`tests/test_remediacion_03h1a.py` (9 casos): allowlist, contexto oficial
resuelto / source-unavailable / coordenada-no-autorizada, E2E golden (identity →
location → context → rate 6.8M → valuation), negative y centroide-bloquea.
Actualizados los tests legacy de `get_valuation` con `allow_legacy_reference=True`.

# REMEDIATION 03H — MARKET CONTEXT RECOVERY

Identidad y contexto de mercado son DOS problemas distintos:

```text
WHAT PROPERTY?       → identity_verified        (03G.1, resuelto)
WHAT MARKET CONTEXT? → market_context_ready      (03H, este módulo)

valuation_authorized = identity_authorized AND market_context_authorized
```

## Módulo `api/market_context.py`

- `resolve_market_sector(barrio)` → `MarketSectorResolution` (lee el YAML Lonja
  `valor_suelo_por_sector`): `EXACT / NORMALIZED_EXACT / ALIAS / NO_MATCH / AMBIGUOUS`
  + `value_m2 / source / source_date / methodology_version / provenance`.
- `build_market_context(...)` → `MarketContext` (puro): cada campo conserva
  `value / status / source`; `ready` se evalúa por CONFIANZA, no por "existe string".
- `market_context_ready(mc)` / `market_context_authorized(mc)` / `market_context_blockers(mc)`.
- Criterio mínimo (PH residencial): identity_verified + barrio VERIFIED_OFFICIAL/
  GEOGRAPHIC + estrato VERIFIED_OFFICIAL + tipología VERIFIED_REGISTRAL/CATASTRAL
  + sector resuelto + `market_rate_source` no nulo.

## Hallazgo del YAML Lonja (leído, no asumido)

`valor_suelo_por_sector` SÍ contiene **Miramar**:

```text
Miramar: valor_central_m2 = 6800000 (rango 5.5M–8.0M), vigencia Q3-2026,
         fuente = "Precio de venta verificado en la constructora del proyecto
                   (unidades ~58 m2 terminadas, 2026) + Lonja BAQ referencial"
```

También: Riomar 5.2M, Villa_Country 4.8M, Alto_Prado 5.5M. `methodology_version`
= `regla_consolidacion.version` = "0.1-codiseno".

## Prohibición de fallback silencioso

- `get_valuation` ahora marca la tasa: `market_rate_match_type = EXACT` (sector
  resuelto) o `GENERIC_ESTRATO_FALLBACK` (fallback por estrato), con
  `market_rate_source` y `value_m2` en el resultado.
- `precondiciones_valoracion`/`get_valuation` aceptan `market_context_blocked`:
  cuando True → `metodologia_aplica=False` con motivo "contexto de mercado
  insuficiente…" (no se emite precio).
- El gate en `pdf_compiler` computa `market_context` y combina:
  `identity_authorized AND market_context_authorized`. El estrato faltante ya no
  se sustituye por 4 para el gate (`estrato_status=UNRESOLVED`).

## Golden trace (040-646406)

```text
Identity       → VERIFIED (AP 430, Official Adoption Registry)
Address        → Transversal 43 100 50 TO 8 AP 430
Barrio         → SOURCE_UNAVAILABLE (POT en vivo no accesible desde sandbox)
Estrato        → UNRESOLVED (estratificación en vivo no accesible)
Tipología      → VERIFIED_REGISTRAL (PH, AP 430 — CTL + registro oficial)
Uso            → UNRESOLVED
Market sector  → NO_MATCH (sin barrio resuelto no se puede match Miramar)
Value/m²       → None (sin sector)
Market context → READY=False
Valuation      → BLOCKED
```

## Capítulo 07

Cuando el bloqueo es por contexto (identidad verificada), el PDF ahora dice
"Identidad predial: VERIFICADA · Contexto de mercado: INCOMPLETO · Pendientes: …"
en vez de "identidad insuficiente".

## Resultado

```text
MARKET CONTEXT SOURCE UNAVAILABLE
```

La arquitectura del gate quedó correcta y sin fallback silencioso. El Golden
permanece bloqueado porque barrio/estrato requieren capas oficiales POT/
estratificación en vivo (no disponibles en este entorno). El sector Miramar
existe en la metodología (6.8M/m²); si el barrio se resolviera oficialmente, el
gate se abriría con esa tasa.

## Tests

`tests/test_remediacion_03h.py` (12 casos): Miramar EXACT 6.8M, NO_MATCH,
determinismo, no-estrato bloquea (#31), no-sector bloquea (#32), full verified
(#33), regresión $305.5M (#35: fallback marcado + bloqueado), sector Miramar no
es fallback, y no default estrato para el gate.

# REMEDIATION 03G.1 — AUTHORITATIVE STATIC IDENTITY RESOLVER

Segunda ruta autoritativa de resolución exacta de identidad, basada en el
Anexo 1 de adopción catastral de Barranquilla (Resolución GGCD 003 del
07/03/2025), sin depender del ArcGIS MapServer.

## Módulo `api/barranquilla_adopcion.py`

- Copia local normalizada + versionada en `api/data/barranquilla_adopcion_anexo1.json`
  (no se descarga en cada Dictus). Conserva `source_url/source_name/
  resolution_number/resolution_date/downloaded_at/version` y calcula `sha256`
  sobre los registros normalizados.
- `consultar_adopcion(folio, numero_predial, codigo_homologado)`: match EXACTO
  por `numero_predial` / `codigo_homologado` / `fmi` (del folio) + cross-check
  `codigo_registral`. Estados: `EXACT_3 / EXACT_2 / EXACT_1 / NO_MATCH / CONFLICT`.
- `resolver_identidad_oficial(...)`: fragmento canónico.

## Reglas

- Solo `EXACT_3` (los 3 identificadores core coinciden) → `MATCH_EXACT` +
  `resolution_method=official_adoption_registry` +
  `resolution_confidence=VERIFIED_UNIT_IDENTITY` + `identity_verified=True`.
- NUNCA fuzzy para identidad verificada.
- Si cualquier identificador contradice a otro → `CONFLICT` (no elegir uno).
- `area_terreno` ≠ área privada del CTL (campo separado, aquí `null`).

## Cross-check Golden (040-646406)

```text
CTL:            folio=040-646406  numero_predial=080010103000010040001908040002  NUPRE=AFT0005BOHA
Official:       codigo_registral=040  fmi=646406  numero_predial=...002  codigo_homologado=AFT0005BOHA  direccion=TV 43 100 50 TO 8 AP 430
Result:         all identifiers agree → EXACT_3 → VERIFIED_UNIT_IDENTITY
```

## Segundo gate: MARKET_CONTEXT_READY

`can_value_property` ahora bloquea cuando `market_context_ready` es
explícitamente `False`, AUNQUE la identidad esté verificada. El registro estático
NO aporta barrio/estrato/tipología, así que la valoración queda pendiente del
segundo gate (no se habilita solo por identidad verificada). Backward-compatible:
la ausencia del campo no bloquea.

## Integración (pdf_compiler)

Cuando el MapServer queda SOURCE_UNAVAILABLE (`predio_real is None`) y el CTL trae
código/NUPRE (Barranquilla), se consulta el Anexo oficial. Si resuelve
`MATCH_EXACT`/`IDENTITY_CONFLICT`, se fusiona sobre `canonical_identity` antes del
gate de valoración: `identity_verified=True`, `market_context_ready=False`,
`identity_source=OFFICIAL_ADOPTION_REGISTRY`.

```text
CTL identifiers → ArcGIS exact resolver → (SOURCE_UNAVAILABLE) → Official Adoption Registry → exact match → Canonical Identity
```

El resolver ArcGIS permanece como ruta de primera clase.

## Tests

`tests/test_remediacion_03g1.py` (10 casos): golden EXACT_3, discriminación de
unidad vecina (AP 430 ≠ AP 431), CONFLICT por identificador contradictorio,
NO_MATCH, provenance completa, fragmento canónico VERIFIED +
`market_context_ready=False`, y el segundo gate (bloquea con False, no bloquea
si ausente).

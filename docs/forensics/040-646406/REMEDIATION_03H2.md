# REMEDIATION 03H.2 — CADASTRAL + URBAN CONTEXT RECOVERY

Recupera la riqueza catastral/urbanística del Golden sin perder las garantías de
identidad y provenance (03G.1/03H.1A intactas).

## 1. Contrato de contexto urbano completo

`resolve_official_urban_context` ya NO descarta atributos: propaga
`barrio + status`, `localidad`, `estrato + status`, `tratamiento + status`,
`tipo_tratamiento`, `altura_maxima + status`, `pieza_urbana`, `codigo_manzana`,
`source`, `coordinate_source`, `context_status`, `campos_ambiguos`.

## 2. Altura / tratamiento — sin hardcode

La altura normativa (`altura_maxima`) y el `tipo_tratamiento` provienen de la
misma consulta oficial (planeación capa 4) y se propagan con
`altura_status=VERIFIED_OFFICIAL`. Si el tratamiento es ambiguo, la altura queda
`CONFLICT` (nunca verificada). `edificabilidad.filas_edificabilidad` ya mostraba
"Tratamiento urbanístico: Consolidación (Nivel 2)" y "Altura normativa máxima:
Hasta 11 pisos (POT Barranquilla)" cuando la fuente los devuelve.

## 3. Construcción: NO_MATCH != SOURCE_UNAVAILABLE

`consultar_construccion` ahora expone `construction_status`
(`AVAILABLE` / `NO_MATCH` / `SOURCE_UNAVAILABLE` / `NOT_EVALUATED`),
`source_disponible` y `source_error`. `filas_edificabilidad` y `_confrontacion`
distinguen:

- `SOURCE_UNAVAILABLE` → "PENDIENTE — fuente de construcción no disponible en
  esta ejecución." (nunca "posible lote sin edificación").
- `NOT_EVALUATED` → "PENDIENTE DE VERIFICACIÓN (capa no consultada)".
- `NO_MATCH` → "capa consultada sin edificación registrada en el punto".

## 4. Estrato — semántica corregida (`get_catastral_dt`)

```text
estrato=None + destino=None          -> PENDIENTE DE VERIFICACIÓN
destino=Habitacional + estrato=None  -> PENDIENTE — uso residencial confirmado; estrato no resuelto
destino exclusivamente no residencial-> No aplica (uso no residencial declarado)
```

Nunca se afirma "No aplica (uso no residencial)" por ausencia del dato.
`HABITACIONAL` cuenta como residencial.

## 5. Etiqueta de barrio

"Barrio catastral" → **"Barrio / sector oficial"** (el dato viene de la capa
oficial POT/unidades administrativas), en 6.1 y en 02.

## 6. Destino/condición desacoplados de la capa 500

Si el predio NO se resuelve en la capa 500 (`predio_real is None`) pero el CTL
trae código/NUPRE, se ejecuta igual `catastro_predio.consultar_condicion_destino`
(lookup EXACTO por identificador primero, punto después) y se registra
`resolution_method`.

## 7. 6.1 consume el estrato verificado

`get_catastral_dt` recibe el estrato del **contexto verificado** (oficial o
catastro vivo), no un default legacy.

## 8. Autoridad urbana ÚNICA para el render (6.2/6.3)

Antes había **dos verdades**: el render 6.2/6.3 leía `_ent2` (capa 500) mientras el
`MarketContext` leía el **contexto oficial**. Cuando la capa 500 no resolvía
(caso Golden), el dictamen mostraba `N/D` / "sin norma" aunque el contexto oficial
sí tuviera tratamiento y altura — y caía al texto genérico de respaldo.

Nuevo `_merge_contexto_urbano_oficial(entorno, oficial, predio_tratamiento)`:

- fusiona SOLO lo que la capa oficial marcó `VERIFIED_OFFICIAL`;
- los campos en `campos_ambiguos` / `STATUS_CONFLICT` **no se afirman**;
- no pisa lo que la capa 500 ya traía;
- si la capa 500 no trajo tratamiento, la autoridad POT del render
  (`_predio_tratamiento`) se toma del contexto oficial verificado, no del texto
  genérico.

Efecto: `filas_edificabilidad` / `_confrontacion` reciben la norma real
(tratamiento + altura máxima) en vez de `sin_norma`. **No** se propaga el estrato
hacia el bloque catastral: el estrato del catastro sigue teniendo su propia
procedencia (`_predio_estrato_catastral`), y 6.1 usa el estrato verificado.

## 9. Contexto de EDIFICIO por coordenadas autorizadas (#5)

`_building_context_por_coordenadas(...)`: consulta la capa de construcción
(layer 310) **solo** si (a) la capa 500 no aportó construcción
(`construction_status == "NOT_EVALUATED"`), (b) la coordenada está en la
allowlist (`coordinate_source_verified`), y (c) la ciudad usa `catastro_predio`
(no Medellín/Bogotá/Pasto, que tienen su propia capa).

Es **BUILDING_SPATIAL_CONTEXT, no identidad**: determina si el edificio existe y
su tipología/pisos, y **jamás** cambia la unidad — AP 430 sigue siendo AP 430.
Si la fuente cae, devuelve `{}` y el llamador conserva `NOT_EVALUATED` (nunca se
degrada a "sin edificación").

## 10. Gates intactos

No se tocó `identity_authorized AND market_context_authorized`. Estos cambios
solo recuperan información y provenance; no abren la valoración.

## Tests

`tests/test_remediacion_03h2.py` (23 casos): contrato urbano completo, ambigüedad,
tratamiento/altura reales, no-"posible lote" (SOURCE_UNAVAILABLE), NO_MATCH sí lo
dice, semántica de estrato (5 casos), autoridad urbana única (4 casos: capa 500
vacía se llena, no pisa la capa 500, ambiguo no se afirma, sin contexto no toca),
building context por coordenadas (5 casos: sin coordenada autorizada, capa 500 ya
respondió, consulta con coordenada autorizada, fuente caída no inventa, ciudades
con capa propia), y negativos (contexto caído no inventa, coordenada no
autorizada no consulta, altura ambigua no verificada).
Actualizado `test_edificabilidad.py` (estados `pendiente_fuente` / `pendiente`).

# REMEDIATION 03H.2A — CADASTRAL / URBAN CONTEXT CLOSURE PATCH

Caso Golden 040-646406 · Torre 8 Napoli Miramar · folio `040-646406` ·
`numero_predial = 080010103000010040001908040002` · `NUPRE = AFT0005BOHA`.

Cierre de cuatro fugas detectadas en la revisión de 03H.2, más las dos rutas
relacionadas que quedaban abiertas (E y F). NO se tocaron fórmulas, parámetros
de mercado, M1/M2/M3, `cap_rate`, YAML de mercado ni los gates de identidad.

---

## A. Altura / `tipo_tratamiento`: nunca `features[0]`

`catastro_predio.consultar_entorno_urbano()` consolidaba `tratamiento` con
`_consolidar_valor()`, pero tomaba `tipo_tratamiento` y `altura_maxima` de
`features[0]`. Con dos polígonos de la capa `planeacion` (Consolidación /
Nivel 2 / **11** y Consolidación / Nivel 2 / **15**) el dictamen afirmaba
"altura máxima 11" eligiendo en silencio la primera feature.

Ahora los **tres** atributos se consolidan INDEPENDIENTEMENTE:

| features | tratamiento | tipo_tratamiento | altura_maxima |
|---|---|---|---|
| Consolidación/N2/11 + Consolidación/N2/15 | Consolidación | Nivel 2 | **None** (+ `altura_maxima` en `campos_ambiguos`) |
| Consolidación/N1/11 + Consolidación/N2/11 | Consolidación | **None** (+ `tipo_tratamiento` en `campos_ambiguos`) | 11 |
| Consolidación/… + Renovación/… | **None** | **None** | **None** |

Regla añadida: si el propio `tratamiento` es ambiguo, el polígono del predio no
está determinado y `tipo_tratamiento`/`altura_maxima` **tampoco** se afirman
(no son atribuibles a un polígono concreto).

`market_context.resolve_official_urban_context()` consume ambigüedad **POR
CAMPO** (`campos_ambiguos`) y añade `tipo_tratamiento_status`:
`altura_status = VERIFIED_OFFICIAL` **solo** si la altura se consolidó sin
conflicto; en caso contrario queda `CONFLICT` y el valor es `None`.

## B. El estado de construcción no se puede perder

`enriquecer_desde_ctl()` conservaba `res["construccion"]` **solo** cuando
`disponible=True`, con lo que se perdían `construction_status`,
`source_disponible`, `source_error` y `resolution_method`. Aguas abajo,
`SOURCE_UNAVAILABLE` ("la capa no respondió") colapsaba a `NO_MATCH` ("no hay
edificación") y el dictamen insinuaba un lote sin construcción.

- `res["construccion"]` se guarda **siempre** (también con `disponible=False`).
- `pdf_compiler` usa el `construction_status` del productor **literalmente**;
  solo infiere un estado legacy si el productor antiguo no lo incluye, y nunca
  convierte `SOURCE_UNAVAILABLE` en `NO_MATCH` (ni en `NOT_EVALUATED`).
- `SOURCE_UNAVAILABLE` produce "PENDIENTE — fuente de construcción no disponible
  en esta ejecución." y `pendiente_fuente` en la confrontación. "posible lote" /
  "sin edificación" quedan reservados a `NO_MATCH` real (HTTP 200 sin features).

## C. Una sola autoridad urbana (sin `setdefault` silencioso)

`_merge_contexto_urbano_oficial()` usaba `setdefault()`, así que un valor legacy
presente en `_ent2` ganaba sobre el `OfficialUrbanContext` `VERIFIED_OFFICIAL`
(ej.: altura legacy 5 sobrevivía frente a altura oficial verificada 11).

Precedencia determinista y auditable:

1. `VERIFIED_OFFICIAL` es la **autoridad** del render para los campos POT:
   `barrio`, `estrato`, `tratamiento`, `tipo_tratamiento`, `altura_maxima`,
   `localidad`, `pieza_urbana`, `codigo_manzana`.
2. Valor previo idéntico → se conserva y se registra `"coincide"`.
3. Valor previo distinto → gana `VERIFIED_OFFICIAL` y el desacuerdo queda
   registrado como **conflicto** (`campo`, `valor_previo`, `valor_oficial`,
   `decision`).
4. Campo marcado `CONFLICT`/ambiguo por la fuente oficial **no se afirma**: se
   registra en `no_aplicados` y no reemplaza nada.

La decisión viaja en `market_context["urban_render_provenance"]`
(`aplicados` / `conflictos` / `no_aplicados`), serializable para la evidencia.

Efecto colateral en la misma línea (dos verdades): la comuna/localidad del
contexto oficial ya se muestra en 6.2 para cualquier ciudad (antes solo Bogotá
la leía y Barranquilla mostraba "N/D" teniendo el dato).

## D. Destino y condición: provenance POR CAMPO

`consultar_condicion_destino()` devolvía un único `resolution_method` global, lo
que presentaba como igualmente exactos dos atributos resueltos por vías
distintas. Ahora cada campo lleva su metadato:

```python
"condicion": {"value", "status", "resolution_method", "source"}
"destino":   {"value", "status", "resolution_method", "source"}
```

- `status`: `VERIFIED_CATASTRAL` (con valor), `UNRESOLVED` (el servicio respondió
  sin coincidencia) o `SOURCE_UNAVAILABLE` (no respondió). Nunca se confunden.
- `resolution_method`: `exact_identifier` o `spatial`, independiente por campo.
- Se conservan los campos planos (`condicion_juridica`, `destino_vigente`,
  `resolution_method`) por compatibilidad; la autoridad son los metadatos.

## E. El NUPRE no es número predial

Existía la ruta `codigo_catastral = analysis.codigo_catastral or analysis.nupre`,
que enviaba `terreno='AFT0005BOHA'` al servicio temático como si fuera un
identificador catastral: nunca podía coincidir y aparentaba una consulta exacta.

- `pdf_compiler` solo usa `analysis["codigo_catastral"]` como `terreno=`.
- `consultar_condicion_destino()` rechaza como identificador exacto cualquier
  valor que no sea numérico de 15–30 dígitos (`identificador_rechazado`), y cae a
  contexto espacial autorizado o queda `UNRESOLVED`. El NUPRE específico sigue su
  propia ruta (`codigo_homologado` en la capa 500, 03G).

## F. Destino/condición temáticos también con `predio_real`

Si la capa 500 resuelve el predio pero `predio.destino_economico` es `None` y el
servicio temático sí trae `destino_vigente`, el dato se usa **con su
procedencia** en lugar de quedar en PENDIENTE por depender de una sola capa.
Además, si el destino sigue faltando y la coordenada está en la allowlist, se
consulta la intersección de punto y se etiqueta **contexto espacial**.

## G. Origen real del destino económico en 6.1

`get_catastral_dt()` afirmaba "(Capa Predio GC-BAQ, en vivo)" para cualquier
destino. Ahora recibe `destino_source` y diferencia:

| `destino_source` | texto |
|---|---|
| `capa_predio` | `(Capa Predio GC-BAQ, en vivo)` |
| `thematic_exact` | `(Servicio Destinos Economicos -- identificador exacto)` |
| `thematic_spatial` | `(Servicio Destinos Economicos -- contexto espacial)` |
| `ctl_inferred` | `(inferido del CTL adjunto)` |
| `pot_context` | `(norma POT del poligono, en vivo)` |
| no declarado | `(fuente catastral en vivo)` — no se atribuye a una capa concreta |

Coherencia relacionada: la tipología ya no dice "inferido del CTL" cuando la
condición PH vino del servicio catastral (ahora "(condición catastral)", con
`tipologia_status = VERIFIED_CATASTRAL`).

## Tests (H) — 29 casos en `tests/test_remediacion_03h2a.py`

Los 11 tests bloqueantes del prompt, todos verdes:

1. tratamiento igual + alturas 11/15 → altura ambigua (nunca `features[0]`).
2. tratamiento igual + tipos Nivel 1/Nivel 2 → tipo ambiguo.
3. construcción `SOURCE_UNAVAILABLE` sobrevive a `enriquecer_desde_ctl()` y el
   PDF no dice `NO_MATCH` ni "posible lote".
4. HTTP 200 con 0 features → `NO_MATCH`.
5. altura legacy 5 + oficial `VERIFIED_OFFICIAL` 11 → nunca queda 5.
6. condición exacta + destino espacial → procedencia independiente por campo.
7. solo NUPRE `AFT...` → no se consulta `terreno='AFT...'`.
8. `predio_real` + `destino_economico=None` + `destino_vigente` → destino final
   con procedencia temática (unitario y E2E).
9. estrato `None` + destino `None` → PENDIENTE.
10. estrato `None` + destino Habitacional → PENDIENTE (uso residencial
    confirmado; estrato no resuelto).
11. Golden 6.1/6.3 en PDF.

Además: E2E del Golden con capas oficiales sustituidas por fixtures
(`TestGoldenPdf`, escenario real de la ejecución: capa 500 sin respuesta →
identidad por registro oficial de adopción), y E2E con **todas** las fuentes
caídas (`TestGoldenSinFuentes`) que exige degradación honesta a PENDIENTE con
causa y valoración bloqueada.

## Golden (I) — estado

PDF del Golden compilado con capas oficiales FIXTURE (sin red) y validado en sus
tres secciones pedidas:

- **6.1**: Barrio / sector oficial `Miramar` · Destino económico `Habitacional`
  `(Servicio Destinos Economicos -- identificador exacto)` · Condición jurídica
  `Propiedad Horizontal` · Estrato `4` · Comuna/Localidad `Norte Centro
  Histórico`.
- **6.3**: Tratamiento `Consolidación (Nivel 2)` · Altura normativa máxima
  `Hasta 11 pisos (POT Barranquilla)` · Pisos construidos `PENDIENTE — fuente de
  construcción no disponible en esta ejecución` (sin "posible lote").
- **07**: valor central `$ 399.500.000 COP` a `$ 6.800.000 /m2` (sector Miramar,
  match `EXACT`) — sin contradicción con 6.1/6.2/6.3.
- **16.b**: identidad `MATCH_EXACT · NUPRE AFT0005BOHA` (registro oficial).

**Lo que NO se puede cerrar desde este entorno:** regenerar el Golden contra las
capas VIVAS (catastro/geocoder/POT) y contra el CTL real del caso. Este sandbox
no tiene salida a `miciudad.barranquilla.gov.co` ni al geocoder, y el CTL real
vive fuera del workspace. En ese escenario el motor ya se comporta como exige el
prompt: `TestGoldenSinFuentes` verifica que sin fuentes el dictamen muestra
PENDIENTE con causa y **no** emite valoración (fail-closed), sin inventar
barrio/estrato/destino/tratamiento ni "$0".

## Gates intactos

`identity_authorized AND market_context_authorized` sin cambios. Ninguna
modificación abre la valoración por sí misma: solo recupera información y
provenance.

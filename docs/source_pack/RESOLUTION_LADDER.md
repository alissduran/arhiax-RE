# RESOLUTION LADDER POR ATRIBUTO — Barranquilla Source Pack v1.0

> Archivos de esta capacidad (SOLO aditivos, ningún archivo existente se modifica):
>
> | Artefacto | Rol |
> |---|---|
> | `api/source_resolution.py` | Implementación de la escalera por atributo. **Consume** `api/dictus_sources.py`; no lo modifica. |
> | `tests/test_source_pack_resolution_ladder.py` | Pruebas bloqueantes, offline y deterministas de la escalera. |
> | `docs/source_pack/RESOLUTION_LADDER.md` | Este documento: escalera, estados, definición de CONFLICT y tabla por atributo. |
>
> Insumo de entrada: el registro de fuentes `docs/source_pack/barranquilla_sources_v1.json`
> (35 fuentes) leído con `dictus_sources.cargar_registro()`, o un registro INYECTADO por
> parámetro cuando el pack no está generado.

---

## 1. Qué es la escalera (y qué NO es)

La escalera responde una sola pregunta por atributo: **¿cuál es el mejor hecho disponible
sobre este atributo, y exactamente de dónde salió?**

No es un detector de conflictos ni un árbitro de capas. El principio rector es:

> **Tener varias capas NO es un problema y NO es un conflicto por defecto.** Se consulta la
> fuente de mayor autoridad y vigencia **declarada para ese atributo** y, si no devuelve un
> dato utilizable, se baja automáticamente al siguiente escalón autorizado. Todo lo que se
> intentó queda registrado; lo que no se seleccionó queda en el **anexo**, no en el cuerpo.

Pasos normativos de la escalera, en orden:

1. Consultar la fuente de mayor autoridad/vigencia definida **para ese atributo**.
2. Si devuelve un **valor válido** → usarlo.
3. Si no devuelve dato utilizable → continuar **automáticamente** con la siguiente fuente
   autorizada del escalón.
4. Registrar **siempre** qué fuente fue seleccionada.
5. Registrar **qué fuentes se intentaron y con qué estado**.
6. DICTUS expone únicamente el **valor resuelto** y su **provenance**.
7. Las fuentes **alternativas / fallback** van al **anexo**.

---

## 2. Los cinco estados de resolución y cuándo se emite cada uno

`resolution_status` pertenece al vocabulario **cerrado** `ESTADOS_RESOLUCION`.
`NO_MATCH` **no** es un estado de resolución: es un estado de fuente (§27 de
`dictus_sources`) que solo puede aparecer dentro de `attempts`.

| Estado | Cuándo se emite | `value` | `provenance` |
|---|---|---|---|
| `RESOLVED_PRIMARY` | La fuente seleccionada es **la de mayor autoridad/vigencia declarada para el atributo** (`order_index == 0`) y devolvió un valor utilizable. Incluye el caso de dos fuentes equivalentes que **coinciden** (una corrobora a la otra): sigue siendo `RESOLVED_PRIMARY`, nunca conflicto. | el valor | completo |
| `RESOLVED_FALLBACK` | Se seleccionó un escalón **posterior al primario** porque los anteriores no aportaron valor utilizable (ausencia, centinela, o consulta no ejecutada). `fallbacks_used` lista las fuentes intentadas antes. | el valor | completo, con `is_fallback: true` |
| `UNRESOLVED` | El hecho **no se pudo resolver y no es ausencia**: (a) ninguna fuente del pack cubre el atributo (escalón vacío → `attribute_declared: false`); (b) la fuente que contestó devolvió `NO_MATCH` en un atributo que **no admite** que otra fuente lo aporte; (c) todas las fuentes aplicables que contestaron devolvieron `NO_MATCH`. | `None` | `{}` |
| `AMBIGUOUS` | Se declaró **CONFLICT** (ver §3): dos fuentes aplicables al mismo atributo, misma semántica, misma vigencia, autoridad comparable y mismo objeto devuelven valores incompatibles que la precedencia no resuelve. El detalle viaja en `conflict` (`label: "CONFLICT"`, `reason`, `sources`, `values`, `pairs`). | `None` | `{}` |
| `SOURCE_UNAVAILABLE` | Existe cobertura, pero **no hay dato obtenible**: ausencias declaradas (`SOURCE_UNAVAILABLE` / `NOT_SUPPORTED` / `QUERY_FAILED`), ninguna consulta ejecutada, o **solo capas históricas con valor** (no se ascienden a operativas). Es el mismo literal que `dictus_sources.FUENTE_NO_DISPONIBLE`. | `None` | `{}` |

Regla transversal (probada en `TestAusenciaNuncaEsNoMatch`):

> **Ningún estado de ausencia se convierte en `NO_MATCH` en ningún punto de la escalera.**
> `SOURCE_UNAVAILABLE`, `NOT_SUPPORTED` y `QUERY_FAILED` **solo bajan al siguiente
> escalón**. La ausencia tampoco se sustituye por `0`, `False` ni por un valor por defecto.

---

## 3. Definición ESTRICTA de `CONFLICT`

`es_conflicto(a, b)` devuelve un veredicto (dict con valor de verdad: es **falso** cuando no
hay conflicto y **verdadero** cuando lo hay, con `reason`, `sources`, `values`,
`conditions` y `unmet`). Es **CONFLICT solo si se cumplen las SEIS condiciones a la vez**:

| # | Condición | Significado operativo |
|---|---|---|
| 1 | **Misma semántica** | `semantics` declarada e **igual**: las dos fuentes miden lo mismo. |
| 2 | **Mismo objeto** | `object_key` declarado e **igual**: hablan del mismo hecho (p. ej. el `PREDIO`). |
| 3 | **Misma vigencia** | Mismo `precedence` (`CURRENT_NORMATIVE` / `CURRENT_OFFICIAL` / `HISTORICAL_REFERENCE` / …). Una vigente y una histórica **nunca** son conflicto. |
| 4 | **Autoridad comparable** | Misma `authority_class`, o ambas clases normativas (`AUTHORITATIVE_OFFICIAL` ↔ `AUTHORITATIVE_CONTRACTUAL`). Una fuente `CONTEXTUAL_EXTERNAL` o `COMPUTED` **no compite** con una oficial. |
| 5 | **Valores incompatibles** | Ambos valores son **utilizables** (ver §5) y su forma canónica **difiere**. |
| 6 | **La precedencia no resuelve** | Empatan en `(autoridad, vigencia, source_priority)`. Si una es estrictamente superior, **hay precedencia, no conflicto**. |

El desempate alfabético por `source_id` que usa el escalón es un criterio de
**determinismo del orden**, no una regla de valor: por eso dos fuentes que empatan en todo
lo demás y discrepan **sí** producen `CONFLICT` (no se elige «la primera por alfabeto»).

### 3.1 Qué NO es conflicto (y cómo se resuelve)

| Situación | Resultado | Por qué |
|---|---|---|
| Capa vieja y capa nueva para el mismo atributo | `RESOLVED_PRIMARY` con la vigente; la histórica queda en `attempts` y en el anexo | Vigencia distinta (condición 3). |
| Dos fuentes equivalentes con valores **iguales normalizados** (`4` vs `"4.0"`) | `RESOLVED_PRIMARY` + role `CORROBORA` | Valores compatibles (condición 5). |
| Destino catastral vs uso POT | Ninguno de los dos es conflicto | Semántica **y** objeto distintos (condiciones 1 y 2). |
| Fuente de contexto (OSM, Mapillary, Street View) vs fuente oficial | La oficial resuelve; el contexto va al anexo | Autoridad no comparable (condición 4). |
| Dos fuentes oficiales vigentes con **prioridad declarada** para el atributo | `RESOLVED_PRIMARY`; la otra queda `DESPLAZADA_POR_PRECEDENCIA` | La precedencia sí resuelve (condición 6). |
| Atributo declarado como `admite_conflicto: false` (contexto/calculadas) | Se selecciona una y la discrepancia se registra como `DISCREPANCIA_SIN_CONFLICTO` | Política declarada por atributo: el contexto no sostiene afirmación normativa (§15). |
| Atributo sin `semantics`/`object_key` declarados | **Nunca** conflicto (conservador) | Sin semántica declarada no puede probarse que midan lo mismo. |
| `estrato` (dos fuentes oficiales vigentes, mismo objeto, **sin** prioridad declarada) | **`CONFLICT` → `AMBIGUOUS`** | Es el caso real del pack: el registro no declara cuál manda, así que no se elige. |

---

## 4. Regla dura: una capa HISTÓRICA nunca compite con una VIGENTE

- La capa **vigente** produce el **valor operativo**.
- La capa **histórica** queda como **provenance / referencia** (`historical_references`) y en
  el **anexo**, con su valor, para contraste.
- Si la capa vigente **no está disponible** y la única con valor es la histórica, el
  resultado es `SOURCE_UNAVAILABLE` **sin valor**: la histórica **no se asciende** a
  vigente en silencio (coherente con `dictus_sources.resolver_precedencia` y
  `test_sin_vigente_declara_sin_dato_y_conserva_la_historica`).
- El mecanismo es declarativo: toda fuente con `precedence = HISTORICAL_REFERENCE` entra al
  escalón con role `SOLO_REFERENCIA`, salvo que el atributo declare
  `historica_como_fallback: true` (ningún atributo del pack lo declara: el paquete entero
  sigue §12).

---

## 5. Dato utilizable / no utilizable

`valor_utilizable(v)` define explícitamente qué es un dato (criterio por atributo, con la
lista de centinelas del pack):

- **NO son valor:** `None`, `""`, `[]`, `{}`, `"NO DISPONIBLE"`, `"N/D"`, `"N.D."`, `"NA"`,
  `"N/A"`, `"SIN DATO"`, `"SIN INFORMACION"`, `"NO APLICA"`, `"NULL"`, `"NONE"`,
  `"UNDEFINED"`, `"DESCONOCIDO"`, `"NO REPORTADO"`, `"-"`, `"PENDIENTE"`, `"TBD"`, cadenas
  en blanco, y contenedores cuyos elementos son todos centinelas.
- **SÍ son valor:** `0`, `0.0`, `False` y cualquier respuesta contestada. El cero es un
  valor legítimo: la escalera **jamás** lo inventa por ausencia.
- La extracción del valor usa los `campos` declarados del atributo (insensible a
  mayúsculas y acentos); si ninguno casa, **el payload completo ES el valor**.
- Un `SourceResult` `AVAILABLE` cuyo valor extraído es un centinela **no es un dato**:
  se registra como intento y se **baja al siguiente escalón**.
- `NO_MATCH` de una fuente que **sí contestó** solo baja al siguiente escalón si el atributo
  declara `admite_fallback_si_no_match: true` (por defecto). `identidad_nupre` lo declara en
  **falso**: la identidad canónica no se sustituye por otra capa.

---

## 6. El escalón: orden determinista

`escalon_para_atributo(atributo)` devuelve la lista **ordenada** de fuentes autorizadas:

1. `authority_class`: `AUTHORITATIVE_OFFICIAL` → `AUTHORITATIVE_CONTRACTUAL` →
   `CONTEXTUAL_EXTERNAL` → `COMPUTED`.
2. Vigencia (`precedence`): `CURRENT_NORMATIVE` → `CURRENT_OFFICIAL` →
   `CONTEXTUAL_REFERENCE` / `COMPUTED_REFERENCE` → `HISTORICAL_REFERENCE`.
3. `source_priority` explícita: la del atributo si el pack la declara para él; si no, la del
   registro; si no, `100`.
4. `source_id` **alfabético** (desempate ESTABLE, independiente del orden de entrada).

Consecuencias garantizadas:

- El orden **no depende** del orden de escritura de la tabla de cobertura ni del orden de
  las claves del registro: permutar ambos produce resultados idénticos
  (`TestDeterminismo`, 36 combinaciones con `itertools.permutations`).
- Los comodines se expanden contra el registro y se ordenan alfabéticamente
  (`EQUIPAMIENTO_*` → las 9 capas de equipamiento presentes).
- `order_index`/`escalon_step` se fijan sobre el escalón **completo**: «primario» significa
  «la fuente de mayor autoridad declarada para el atributo», no «la primera que quedó tras
  filtrar por fecha».
- Una **ventana de vigencia** declarada (`vigente_desde` / `vigente_hasta`) puede sacar una
  fuente del escalón para una `fecha` dada: se registra como `NOT_RUN` con su motivo y se
  **baja al siguiente escalón** (nunca como `NO_MATCH`). Con una fecha ilegible no se
  excluye nada.
- `NOT_RUN` es un marcador **local** de la escalera (no es un estado de fuente del contrato
  §27): significa «no se ejecutó consulta», no contiene dato y nunca se lee como `NO_MATCH`.

---

## 7. API pública (`api/source_resolution.py`)

```python
escalon_para_atributo(atributo, *, registro=None, cobertura=None, fecha=None) -> list[dict]

resolver_atributo(atributo, *, consultas, fecha=None, registro=None,
                  cobertura=None) -> dict
    # dict con: attribute, resolution_status, value, selected_source, selected_status,
    # attempts [{source_id, status, value, rejected_reason, escalon_step, ladder_role,
    #            authority_class, vigencia, semantics, object_key}],
    # fallbacks_used, conflict, provenance, annex_reference, semantics, object_key,
    # vigencia, reason, ladder_notes, unregistered_sources, registry_status,
    # attribute_declared, first_escalon_source, fecha, registry_version, description

resolver_dominio(atributos_por_dominio, *, consultas=None, fecha=None, registro=None,
                 cobertura=None) -> {"resultados": {atributo: resultado},
                                     "resumen": {...}, "dominios": {...},
                                     "annex_reference": ...}
    # resumen: resolved_primary, resolved_fallback, unresolved, ambiguous,
    #          source_unavailable, conflicts, resolved, total, registry_status

solo_valor_resuelto(resultados) -> {atributo: {"value": ..., "provenance": ...}}
anexo_alternativas(resultados) -> {atributo: {...alternativas, intentos, conflictos...}}
es_conflicto(a, b, *, registro=None, attribute=None, cobertura=None) -> dict veredicto
valor_utilizable(valor) -> bool          # qué es «dato» (§5)
normalizar_valor(valor) -> forma canónica  # 4 == "4.0"; listas como conjunto
valores_compatibles(a, b) -> bool
estado_registro(registro=None) -> {"registry_status", "registry_version",
                                   "source_count", "registry_path"}   # declara ausencia
atributos_declarados() -> list[str]
COBERTURA_ATRIBUTOS, ATRIBUTOS, ESTADOS_RESOLUCION, ORDEN_AUTORIDAD, ORDEN_VIGENCIA
RESOLVED_PRIMARY, RESOLVED_FALLBACK, UNRESOLVED, AMBIGUOUS, SOURCE_UNAVAILABLE, CONFLICT
```

`consultas` acepta **ambas** formas: mapa `source_id -> SourceResult` **o** un *callable* por
fuente (`consultas(source_id) -> SourceResult | None`). Una fuente del escalón sin consulta
declarada se registra como `NOT_RUN` y no aporta valor.

---

## 8. Tabla de ejemplo por atributo

La columna **primaria** es la **primera fuente del escalón** derivada del registro
`barranquilla_sources_v1.json` (35 fuentes, `registry_version: barranquilla-sources-v1`);
las de **fallback** son el resto del escalón, en orden. El registro **sí existe** en este
repo, así que las claves son las reales de negocio y **ninguna** queda declarada y ausente
(`unregistered_sources == []` en todos los atributos, verificado por prueba).

| Atributo | Objeto | Primaria | Fallback(s) del escalón | Deshabilitadas hoy en el registro |
|---|---|---|---|---|
| `identidad_nupre` | `PREDIO` | `CATASTRO_BAQ_ADOPCION_ANEXO1` | `CATASTRO_BAQ_PREDIO`, `CATASTRO_BAQ_TERRENO` | — |
| `predio` | `PREDIO` | `CATASTRO_BAQ_PREDIO` | `CATASTRO_BAQ_TERRENO`, `CATASTRO_BAQ_MANZANA` | — |
| `direccion_predio` | `PREDIO` | `CATASTRO_BAQ_DIRECCION` | `CATASTRO_BAQ_PREDIO` | — |
| `barrio` | `BARRIO` | `POT_BAQ_BARRIOS` | — (el barrio es un hecho oficial, no de mercado) | — |
| `localidad` | `LOCALIDAD` | `POT_BAQ_LOCALIDADES` | `POT_BAQ_BARRIOS` | — |
| `destino_catastral` | `PREDIO` | `CATASTRO_BAQ_DESTINO_ECONOMICO` (prioridad 10; vigente desde 2026-01-01) | `CATASTRO_BAQ_PREDIO` | — |
| `uso_pot` | `PREDIO` | `POT_BAQ_AREAS_ACTIVIDAD` | `POT_BAQ_POLIGONOS_USO` | ambas |
| `tratamiento` | `PREDIO` | `POT_BAQ_TRATAMIENTO` | — (sin fallback declarado) | — |
| `edificabilidad_altura_normativa` | `PREDIO` | `POT_BAQ_EDIFICABILIDAD` | — (sin fallback declarado) | — |
| `altura_fisica` | `PREDIO` | `CATASTRO_BAQ_CONSTRUCCION` | — (el POT **no** es altura física) | — |
| `remocion` | `PREDIO` | `POT_BAQ_REMOCION_2024` | `POT_BAQ_REMOCION_HIST` (referencia) | `POT_BAQ_REMOCION_HIST` |
| `inundacion` | `PREDIO` | `POT_BAQ_INUNDACION_2024` | `POT_BAQ_INUNDACION_HIST` (referencia) | ambas |
| `riesgo` | `PREDIO` | `POT_BAQ_RIESGO_2024` | `POT_BAQ_RIESGO_HIST` (referencia) | `POT_BAQ_RIESGO_HIST` |
| `equipamiento_oficial` | `ENTORNO` | `EQUIPAMIENTO_18` | `EQUIPAMIENTO_20` … `EQUIPAMIENTO_27` (8 capas) | las 9 |
| `servicios_de_contexto` | `ENTORNO` / `FACHADA` | `OSM_OVERPASS` (prioridad 10) | `MAPILLARY`, `GOOGLE_STREET_VIEW` | — |
| `mercado` | `ZONA_MERCADO` | **(ninguna: escalón VACÍO por decisión de producto)** | — (el mercado no se sustituye por contexto) | — |
| `estrato` | `PREDIO` | `CATASTRO_BAQ_PREDIO` | `POT_BAQ_ESTRATIFICACION` | — |
| `exposicion_solar_fachada` | `FACHADA` | `SHADOW_FACADE_EXPOSURE` | `SOLAR_ENGINE` | — |

Lecturas de la tabla que conviene tener presentes:

- **Riesgo (remoción / inundación / riesgo).** La vigente es `*_2024`
  (`CURRENT_NORMATIVE`) y las capas anteriores son `HISTORICAL_REFERENCE` con role
  `SOLO_REFERENCIA`: nunca aportan el valor operativo, solo la referencia del anexo. En
  `inundacion` **ambas** capas están deshabilitadas hoy, así que el resultado honesto es
  `SOURCE_UNAVAILABLE` (no «sin amenaza»).
- **Equipamiento oficial.** Las 9 capas `EQUIPAMIENTO_*` están **deshabilitadas** en el
  registro (`UNVERIFIED_LIVE`): el escalón existe y está ordenado, pero hoy producirá
  `SOURCE_UNAVAILABLE`. El equipamiento que DICTUS consume viene de OSM: por eso OSM vive en
  `servicios_de_contexto` y **jamás** se presenta como autoridad oficial (§15,
  `dictus_sources.separar_equipamiento`).
- **`estrato`.** Único atributo del pack con dos fuentes oficiales vigentes, mismo objeto y
  **sin prioridad declarada**: si discrepan, se declara `CONFLICT`/`AMBIGUOUS` con sus
  candidatos, en lugar de elegir una.
- **Destino catastral vs uso POT.** Atributos distintos, semánticas distintas y objetos
  distintos: **no** se comparan ni producen conflicto, aunque ambos sean «oficiales».
- **Altura normativa vs altura física.** `edificabilidad_altura_normativa` y `altura_fisica`
  son atributos separados y con semánticas separadas: la altura del POT nunca se resuelve
  como altura física del edificio (`dictus_sources.altura_fisica`).
- **`mercado` (DECISIÓN DE PRODUCTO: la Lonja no es una fuente).** El escalón de `mercado`
  está **VACÍO a propósito**: no se declara ninguna fuente porque no existe ninguna que
  aporte el valor por m². El valor de mercado que usa la valoración es un **parámetro
  declarado por la corrida** (artefacto local de metodología, `api/market_context.py`), **sin
  fuente externa automática verificable**. La resolución del atributo devuelve
  `SOURCE_UNAVAILABLE` con `value = None` y `ladder_notes = ["sin_fuente_declarada"]`:
  **nunca** `NO_MATCH`, **nunca** un valor sustituido por contexto ni por el promedio de
  otros sectores. El identificador `LONJA_MARKET_BAQ` se conserva como identificador
  histórico sellado (no se renombra) pero **no** es `source_id` del registro ni peldaño de
  ninguna escalera. Detalle: `docs/source_pack/INSTITUTIONAL_PARTNERS.md` y
  `docs/source_pack/acceptance_report.md` §7.
- **`barrio`.** El barrio es un hecho oficial (POT/catastro): su escalón ya **no** incluye
  ninguna pieza de mercado. El fallback declarado se ejercita con `localidad`
  (`POT_BAQ_LOCALIDADES` → `POT_BAQ_BARRIOS`).

---

## 9. Cuerpo DICTUS vs ANEXO

- **Cuerpo (`solo_valor_resuelto`)** — lo único que DICTUS imprime: por atributo,
  exactamente `{"value", "provenance"}`. Solo aparecen los atributos `RESOLVED_PRIMARY` y
  `RESOLVED_FALLBACK`; los no resueltos **no** llegan al cuerpo.
- **Anexo (`anexo_alternativas`)** — la trazabilidad completa: `annex_reference`
  (`ANEXO-FUENTES-<ATRIBUTO>`), `resolution_status`, `reason`, `selected_source`,
  `sources_attempted`, `alternativas` (cada intento con su `status`, `value`,
  `rejected_reason` y `ladder_role`), `fallbacks_used`, `historical_references`, `conflict`
  y `ladder_notes`.
- Roles del anexo: `SELECCIONADA`, `CORROBORA`, `COMPLEMENTARIA`,
  `DISCREPANCIA_SIN_CONFLICTO`, `DESPLAZADA_POR_PRECEDENCIA`, `REFERENCIA_HISTORICA`,
  `EN_CONFLICTO`, `NO_CONSULTADA`, `NO_SELECCIONADA`.

---

## 10. Pruebas

```
python -m pytest tests/test_source_pack_resolution_ladder.py -q     # 58 passed
python -m pytest tests/test_source_pack_contract.py -q              # sigue verde
python -m pytest tests/test_source_pack_imagery_solar.py -q         # sigue verde
```

Las 10 garantías exigidas por el pedido, con su prueba:

| # | Garantía | Prueba |
|---|---|---|
| 1 | Capa vieja + nueva para el mismo atributo → `RESOLVED_PRIMARY` con la vigente, histórica en `attempts`/anexo, **nunca** conflicto | `TestSinConflictoPorDefecto` |
| 2 | Primera fuente caída → siguiente autorizada da el valor → `RESOLVED_FALLBACK` con los intentos registrados | `TestFallbackAutomatico` |
| 3 | Todas caídas → `SOURCE_UNAVAILABLE` sin valor, nunca `NO_MATCH`, nunca cero | `TestTodasCaidas` |
| 4 | Ninguna fuente cubre el atributo → `UNRESOLVED` | `TestSinCobertura` |
| 5 | Dos fuentes equivalentes con valores incompatibles e irresolubles → `CONFLICT` (`AMBIGUOUS` + motivo + candidatos) | `TestConflictoIrresoluble` |
| 6 | Dos fuentes equivalentes con valores compatibles → **no** conflicto | `TestEquivalentesCompatibles` |
| 7 | Distinta vigencia / semántica / objeto → **no** conflicto aunque los valores difieran | `TestNoEsConflicto` |
| 8 | Determinismo: permutar el orden de fuentes y de consultas da el MISMO resultado (`itertools.permutations`) | `TestDeterminismo` |
| 9 | DICTUS ve solo el valor resuelto + provenance; el anexo lleva las alternativas | `TestVistasDictusYAnexo` |
| 10 | Ningún estado de ausencia se convierte en `NO_MATCH` en ningún punto | `TestAusenciaNuncaEsNoMatch` |

---

## 11. Supuestos declarados

1. **El registro del pack SÍ existe** en este repo
   (`docs/source_pack/barranquilla_sources_v1.json`, 35 fuentes, verificado). La tabla de §8
   usa por eso las claves reales de negocio. El camino «registro ausente / inyectado» también
   está implementado y probado: `cargar_registro()` devuelve `_status: NOT_SUPPORTED` cuando
   falta, la escalera lo propaga en `registry_status`, y las pruebas inyectan registros y
   coberturas en memoria (nunca se escribe en el pack ni en `docs/source_pack/raw/`).
2. **`source_priority` no existe hoy en el registro.** El orden usa, por tanto, la prioridad
   **declarada por atributo** en `COBERTURA_ATRIBUTOS` (`priority_origin: "PER_ATTRIBUTE"`) y,
   en su defecto, `source_priority` del registro (`priority_origin: "REGISTRY"`) y luego
   `100` (`"DEFAULT"`). Cuando el pack añada `source_priority` por fuente, la escalera lo
   respetará sin cambios de código.
3. **Prioridades declaradas por esta escalera** (no presentes en el registro):
   `identidad_nupre` Anexo1 10 / Predio 20 / Terreno 30; `predio` Predio 10 / Terreno 20 /
   Manzana 40; `direccion_predio` Dirección 10 / Predio 30; `barrio` Barrios 10 / Lonja 30;
   `localidad` Localidades 10 / Barrios 30; `destino_catastral` Anualidad 10 / Predio 30;
   `uso_pot` Áreas 10 / Polígonos 20; `servicios_de_contexto` OSM 10 / Mapillary 20 /
   Google 30. `estrato` queda **sin** prioridad a propósito (§3).
4. **`fecha`** se usa solo como filtro de ventana de vigencia declarada por atributo (hoy:
   la anualidad 2026 del destino económico, `vigente_desde: 2026-01-01`) y se registra en el
   resultado y en la provenance. Ningún atributo tiene `vigente_hasta`.
5. **No hay red, ni reloj, ni escritura** en la escalera ni en sus pruebas: es una función
   pura de (atributo, consultas, registro). Los estados de las fuentes llegan ya resueltos
   por el contrato §27 de `api/dictus_sources.py`, que en esta entrega **no** se modificó.

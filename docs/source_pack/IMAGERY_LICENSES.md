# IMAGERY LICENSES — licencia de las IMÁGENES ≠ términos de la API

**Módulo:** `api/source_licenses_v2.py` (`source-licenses-v2/2.0.0`) · **Evidencia consultada:** **2026-09-29** (UTC) ·
**Alcance:** licencias de **imágenes de terceros** del Source Pack (Mapillary, Google Street View) + una fuente de
**datos** sin imágenes (OSM/Overpass) como control de vocabulario.

**Decisión de producto que origina esta pieza:** la v1 (`api/source_licenses.py`, intacta) respondía con **un solo**
campo (`provider_terms_status`) dos preguntas distintas. La v2 las separa y **no las mezcla nunca**:

| campo | pregunta que responde | qué gobierna |
|---|---|---|
| `IMAGERY_LICENSE_STATUS` | ¿bajo qué licencia se comparten las **IMÁGENES** y qué obliga esa licencia? | los **DERECHOS**: persistir · modificar · incrustar · share-alike |
| `API_TERMS_STATUS` | ¿qué términos gobiernan la **API/plataforma** por la que se accede? | la **ADQUISICIÓN**: client_id · interfaces publicadas · sin scraping · throttling |

Un `API_TERMS_STATUS=VERIFIED` **no abre** la matriz de imágenes; un `IMAGERY_LICENSE_STATUS=VERIFIED` **no autoriza**
a scrapear la API. Los permisos operativos (`autorizar_persistencia`, `autorizar_modificacion`,
`autorizar_incrustacion`) se dictan **solo** con la columna de imágenes.

## 1. Evidencia registrada (URL · fecha · HTTP · bytes · sha256 · estado de la evidencia)

| id | URL consultada | fecha | HTTP | bytes | `sha256` (instantánea) | estado de la evidencia |
|---|---|---|---|---|---|---|
| `MAPILLARY_TERMS_OF_USE` | https://www.mapillary.com/terms | 2026-09-29 | 200 | 111094 | `e9ce3ac2fddf91013b86d5a3a7f56cf8424522e00e942dced10215331f330ea7` | `ACCESIBLE_VERIFICADA` (documento del proveedor, «Effective date: February 15, 2024») |
| `MAPILLARY_HELP_CC_BY_SA_4_0` | https://help.mapillary.com/hc/en-us/articles/115001770409-CC-BY-SA-license-for-open-data | 2026-09-29 | **403** | — | `None` (no descargada) | `INACCESIBLE_HTTP_ERROR` — **sigue inaccesible en vivo** |
| `MAPILLARY_HELP_CC_BY_SA_4_0_ARCHIVO` | copia archivada (Wayback, captura `20260724100858`) del artículo **oficial** anterior | 2026-09-29 | 200 | 32538 | `165ec7abfa0b8b122d3c3c5b20851dd96b5cc2f1a7745df52145b18e63a0b34f` | `COPIA_ARCHIVADA_DE_DOC_PROVEEDOR` (artículo «May 12, 2025 11:34 Updated») |
| `CC_BY_SA_4_0_DEED` | https://creativecommons.org/licenses/by-sa/4.0/ | 2026-09-29 | 200 | 35745 | `6acd86b2893060f04d2b8d8743ef12baf046bb46973374c6e077e366cad01d66` | `ACCESIBLE_VERIFICADA` (texto de la licencia a la que apunta el proveedor) |
| `CC_BY_SA_4_0_LEGALCODE` | https://creativecommons.org/licenses/by-sa/4.0/legalcode | 2026-09-29 | 200 | 51860 | `6c0f42e2d43700044349772d54265a315171f47d42f5e88cd380481bf18d814e` | `ACCESIBLE_VERIFICADA` |
| `MAPILLARY_TERMS_API` | https://www.mapillary.com/terms/api | 2026-09-29 | 200 | 74354 | `ba4abe7a8b8e7db39adbdc9500534c5a578734579f321c727855804cff30d025` | **`SOFT_404`** (200 con cuerpo «página no encontrada») |
| `MAPILLARY_TERMS_DATA` | https://www.mapillary.com/terms/data | 2026-09-29 | 200 | 74357 | `800bd2f8439e0b94ec18340e71b26a276d78eca198790f93ec222370eab3e168` | **`SOFT_404`** (idem) |
| `MAPILLARY_API_DOC` | https://www.mapillary.com/developer/api-documentation | 2026-09-29 | 200 | 131397 | `ed5e7b126c65c4139cdf94dbbf89526538189b820b0fd8d5f09aa24c8cb947c9` | `ACCESIBLE_SIN_MARCADORES_DE_LICENCIA` |
| `MAPILLARY_OPEN_DATA` | https://www.mapillary.com/open-data | 2026-09-29 | 200 | 83624 | `0df9989bb9810085f9a4a55e572ac5614f628b993145eb96bb97c8e1b0c0126f` | `ACCESIBLE_SIN_MARCADORES_DE_LICENCIA` |
| `MAPILLARY_DATASETS` | https://www.mapillary.com/datasets | 2026-09-29 | 200 | 81222 | `419521976f25c63dcd70406c354a8d8fec229d485f245fa13ce53f1ae82c5056` | `ACCESIBLE_SIN_MARCADORES_DE_LICENCIA` |
| `GOOGLE_STREETVIEW_POLICIES` | https://developers.google.com/maps/documentation/streetview/policies | 2026-09-29 | 200 | 195577 | `73d102bce3883cdf80fd8fe1f1c61f126c42cdc0af1d3bdb735c76038d6ee30c` | `ACCESIBLE_VERIFICADA` (prohibición explícita) |
| `GOOGLE_MAPS_PLATFORM_TERMS` | https://cloud.google.com/maps-platform/terms | 2026-09-29 | 200 | 2412689 | `4b68ffe664a3a808a4051541c63cfca681f61f5c65ca198dd29bb07f4b7a954e` | `ACCESIBLE_VERIFICADA` (prohibición explícita) |
| `OSM_COPYRIGHT` | https://www.openstreetmap.org/copyright | 2026-09-29 | 200 | 21314 | `1c0d3380b5abeb616644dd9be7adf5498035d63c92c211e4372d019f24d8c9a8` | `ACCESIBLE_VERIFICADA` (ODbL 1.0 impresa) |
| `MAPILLARY_WIKI_TERCEROS` | https://wiki.openstreetmap.org/wiki/Mapillary | 2026-09-29 | 200 | 78178 | `a6a6136450a881ebe27934074546916256daadae98569bebc39849efc01ec21c` | `TERCERO_NO_PROVEEDOR` — **corrobora, no verifica** |

**Búsqueda de evidencia accesible (lo que REALMENTE se consiguió, y lo que no).** La página del centro de ayuda de
Mapillary responde **403 en vivo** (confirmado otra vez en esta ronda). En su lugar se consiguieron **dos fuentes
accesibles del propio proveedor**:

1. **Términos de Uso vigentes** (`/terms`, 200): §3(b) sujeta el Contenido del usuario de otros usuarios a **CC BY-SA**
   y **enlaza** el nombre de la licencia al deed canónico **`creativecommons.org/licenses/by-sa/4.0/`** (la versión
   4.0 queda evidenciada por el enlace del proveedor, no impresa como texto); exige **atribución visible con enlace**
   para descargar y servir imágenes; y trae en §11/§12 los términos de **API/Developers**. El documento imprime
   **«Effective date: February 15, 2024»**.
2. **Copia archivada del propio artículo de ayuda** (Wayback, captura 2026-07-24; el artículo se lista «May 12, 2025
   11:34 Updated»): «**All images on Mapillary are shared under a CC-BY-SA license**, which in short means that anyone
   can look at and distribute your images, and even modify them a bit, **as long as they give attribution**» — con
   `CC-BY-SA` enlazado a `creativecommons.org/licenses/by-sa/4.0/`. Se registra como **copia archivada servida por un
   tercero**: evidencia corroborante, **no** acceso directo al documento oficial.

**No se consiguió** ningún documento de **términos de API** dedicado: `/terms/api`, `/terms/data` responden 200 con
cuerpo de «página no encontrada» (soft-404) y `/developer/api-documentation` es accesible pero **no** es un documento
de términos. Se declara, no se silencia.

## 2. MAPILLARY — las dos columnas, separadas

**`IMAGERY_LICENSE_STATUS = VERIFIED`** — alcance declarado (`verified_scope`): *licencia de las imágenes = familia
CC BY-SA 4.0 + obligación de atribución visible con enlace + share-alike*, evidenciada con documentos **del
proveedor** accesibles y hasheados.

- **Derechos:** `can_persist=True` · `can_modify=True` · `can_embed=True` · `share_alike=True` (los mismos tres
  permisos operativos que el registro del pack ya declaraba para Mapillary).
- **Cita de licencia (§3(b)):** «Your use of any User Content provided by other users is subject to the **Creative
  Commons Share Alike (CC BY-SA) license**, unless we indicate otherwise. For instance, we may provide access to
  certain User Content […] under a separate set of license terms (such as the Creative Commons **Attribution
  NonCommercial Share Alike (CC BY-NC-SA** license).»
- **Cita de atribución:** «You must adhere to the **attribution requirements** set forth below […]. If you are
  downloading individual images and serving them from your own servers, you must attribute the image(s) by visibly
  displaying the Mapillary logo and linking back to the Mapillary homepage or corresponding Mapillary image page.»
- **Cita de la versión (enlace del proveedor):** «Your use of any User Content provided by other users is subject to
  the `<a href="http://creativecommons.org/licenses/by-sa/4.0/">`Creative Commons Share Alike (CC BY-SA) license`</a>`».
- **Obligaciones de la licencia (deed 4.0):** «Share — copy and redistribute the material in any medium or format for
  any purpose, even commercially.» · «Attribution — You must give appropriate credit, provide a link to the license,
  and indicate if changes were made.» · «ShareAlike — If you remix, transform, or build upon the material, you must
  distribute your contributions under the same license as the original.»

**Condiciones declaradas (la licencia de IMAGEN manda por imagen, no el bloque):**

1. **Por imagen:** sólo si la metadata declara CC BY-SA (o el proveedor no indica otra licencia).
   `permitir_persistencia_imagen()` cierra la imagen concreta si la licencia es distinta, NC o **ausente**
   (la ausencia **no** equivale a permiso).
2. **Atribución visible con enlace** — `© Mapillary contributors (CC BY-SA 4.0)`, con logo Mapillary y enlace a la
   imagen/página de Mapillary cuando se sirven imágenes desde servidor propio.
3. **Share-alike** sobre obras derivadas (misma licencia).
4. **Uso comercial** sujeto a la **Sección 12** (salvaguardas contra reidentificación/desenfoque).
5. **Adquisición** sólo por interfaces publicadas de la API, con `client_id` y sin scraping (fila de API).

`what_is_missing_for_verified = []` para el alcance declarado; lo que **no** cubre se declara en `residual_gaps`:
(i) la versión **no** está impresa como texto «4.0» (se sostiene por el enlace del proveedor + la declaración del
código `MapillaryProvider.LICENCIA_DECLARADA="CC BY-SA 4.0"`); (ii) excepciones **por conjunto de datos** admitidas
(«unless we indicate otherwise», p. ej. CC BY-NC-SA) ⇒ confirmación por imagen; (iii) uso comercial condicionado a §12;
(iv) la página oficial del centro de ayuda responde **403** en vivo (se usó copia archivada).

**`API_TERMS_STATUS = DECLARED`** (columna independiente): los términos que gobiernan la API son §11 (*Additional Terms
for Developers*) y §12 (comercial) del documento de Términos de Uso vigente, consultado y hasheado. **No** existe
documento de términos de API dedicado y accesible ⇒ el estado **no** se cierra como `VERIFIED`. Obligaciones
declaradas: registrar la aplicación y obtener **`client_id`**; acceder **sólo** por las interfaces publicadas y
vigentes (**sin scraping** ni métodos de extracción no aprobados); respetar `robots.txt` y no eludir la
monitorización; el proveedor puede **limitar (throttle)** el uso y **revocar** `client_id`s; uso comercial sujeto a §12.
Efecto declarado: **restringe la adquisición**, no otorga derechos sobre las imágenes.
`what_is_missing_for_verified`: documento de términos de API propio, vigente y accesible (hoy `/terms/api` y
`/terms/data` son soft-404) + versión/fecha de los términos de API.

## 3. GOOGLE STREET VIEW — fail-closed, y **no bloquea nada**

| campo | valor |
|---|---|
| `IMAGERY_LICENSE_STATUS` | **`RESTRICTED`** |
| `API_TERMS_STATUS` | **`RESTRICTED`** |
| `can_persist` / `can_modify` / `can_embed` / `share_alike` | `False` / `False` / `False` / `False` |
| `product_role` | **`OPTIONAL_ENRICHMENT`** |
| `bloquea_source_pack` | **`False`** (tampoco `CONTRACT_FROZEN` ni `OPERATIONAL_READY`) |

Evidencia: «**Content pre-fetching, indexing, storing, or caching is generally prohibited**, except for place IDs and
panorama IDs.» (políticas de Street View) + *No Scraping / No Caching / No Creating Content From Google Maps Content*
(Maps Platform Terms). La licencia **CC BY 4.0** visible en la página de políticas es del **contenido de la
documentación**, no de las imágenes.

**Test negativo (fail-closed probado):** `autorizar_persistencia("GOOGLE_STREET_VIEW")`,
`autorizar_modificacion(...)` y `autorizar_incrustacion(...)` devuelven `permitido=False`, `flujo="NINGUNO"` y
`attribution_text=None`, con motivo: «el bloque declara `can_embed=False`: ningún flujo puede incrustar;
`IMAGERY_LICENSE_STATUS=RESTRICTED` no habilita incrustar». No hay ninguna vía alternativa: el bloqueo es estructural.

## 4. Qué **no** es evidencia (se declara para que nadie lo cuente)

- **HTTP 200 con soft-404**: `/terms/api`, `/terms/data` (y `/attribution`, `/developer/api-documentation` en la
  primera sonda) devuelven 200 con el cuerpo «No hemos podido encontrar la página que buscabas». Se registran como
  `SOFT_404`: **HTTP 200 no es evidencia**.
- **Página accesible sin marcadores de licencia**: `/open-data` y `/datasets` (200, del proveedor, sin licencia en el
  contenido servido) ⇒ `ACCESIBLE_SIN_MARCADORES_DE_LICENCIA`, **no** sostienen ningún `VERIFIED`.
- **Terceros**: el wiki de OpenStreetMap menciona CC BY-SA 4.0, pero es comunidad ⇒ `TERCERO_NO_PROVEEDOR`
  (corrobora, no verifica). La **copia archivada** del artículo oficial se acepta sólo como evidencia
  **corroborante** y para fijar el texto de atribución, porque el original responde 403 en vivo.

## 5. Limitaciones reales

1. **Los `sha256` son instantáneas fechadas, no artefactos estables.** Cuatro lecturas de `/terms` en esta misma
   sesión dieron hashes distintos (118251 B en español, y 111094/111095 B en inglés); el módulo guarda
   `hashes_observados` y `verificar_evidencia_registrada()` **declara** la discrepancia en lugar de fingir que el
   contenido no cambió.
2. **La versión de la licencia se sostiene por un ENLACE, no por texto impreso** («4.0» no aparece como cadena en los
   términos). Es evidencia verificable del proveedor, pero de menor fuerza que una versión escrita.
3. **No hay verificación por conjunto de datos ni por imagen**: los términos admiten excepciones y la metadata puede
   contradecir la licencia declarada; de ahí `permitir_persistencia_imagen()` (fail-closed por imagen).
4. **La fuente más específica sigue inaccesible** (403 en el centro de ayuda): la evidencia de ese artículo procede de
   una copia archivada servida por un tercero.
5. Este documento y el módulo **no amplían** ningún permiso del pack: la v1 (`api/source_licenses.py`) y el registro
   `barranquilla_sources_v1.json` siguen siendo la declaración auditada —la v1 mantiene `Mapillary=DECLARED`, lectura
   conservadora del **mismo** hecho—; la v2 añade la **separación** imágenes/API y la evidencia accesible de la versión.
6. Nada aquí condiciona `CONTRACT_FROZEN` ni `OPERATIONAL_READY`: **Google no bloquea** (OPTIONAL_ENRICHMENT) y la
   **Lonja no es una fuente** (`docs/source_pack/INSTITUTIONAL_PARTNERS.md`).

## 6. Reproducir la verificación

```bash
python api/source_licenses_v2.py --resumen            # ambas columnas + huecos
python api/source_licenses_v2.py --source MAPILLARY   # bloque canónico completo
python api/source_licenses_v2.py --auditoria          # bloques completos, sin Lonja-fuente
python api/source_licenses_v2.py --verificar-evidencia MAPILLARY_TERMS_OF_USE   # red
python -m pytest tests/test_source_pack_licenses.py -q
```

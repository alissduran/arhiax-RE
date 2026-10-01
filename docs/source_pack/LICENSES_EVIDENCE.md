# LICENSES EVIDENCE — SOURCE PACK v1.0-R1 · requisito G

**Alcance:** evidencia REAL de términos/licencias consultada el **2026-09-29** para las 35 fuentes
declaradas en `docs/source_pack/barranquilla_sources_v1.json`. Bloque canónico: `api/source_licenses.py`
(`licencia(source_id)`, `catalogo_licencias()`, `resumen()`, `autorizar_incrustacion()`).

**Regla del bloque:** `terms_hash = sha256(bytes descargados)`; si el contenido no se pudo descargar,
`terms_hash=None` **con motivo escrito**. Ningún permiso se asume: sin evidencia, el estado no es
`VERIFIED`.

## 1. Evidencia consultada (URL · fecha · HTTP · bytes · sha256 · resultado)

| # | id de evidencia | URL consultada | fecha | HTTP | bytes | `sha256` (instantánea) | resultado |
|---|---|---|---|---|---|---|---|
| 1 | `MAPILLARY_TERMS` | https://www.mapillary.com/terms | 2026-09-29 | 200 | 118250 | `61f11ac253d4f7c84c62b94799b89f285114af7e247f748f79a92919fa54e6b9` | **DECLARED** (CC BY-SA sin versión + excepciones por conjunto de datos + reserva de derechos) |
| 2 | `MAPILLARY_CC_BY_SA_4_0` | https://help.mapillary.com/hc/en-us/articles/115001770409-CC-BY-SA-license-for-open-data | 2026-09-29 | **403** | — | `None` (no descargado) | **UNVERIFIED** — es el hueco que impide VERIFIED |
| 3 | `GOOGLE_MAPS_PLATFORM_TERMS` | https://cloud.google.com/maps-platform/terms | 2026-09-29 | 200 | 2412706 | `40ab3eab2c4469d397397cc20f1018c00fc5f514143e3bc3736348fc05b287b0` | **RESTRICTED** (prohibición explícita de almacenar/cachear) |
| 4 | `GOOGLE_STREETVIEW_POLICIES` | https://developers.google.com/maps/documentation/streetview/policies | 2026-09-29 | 200 | 195577 | `b05384c507e67f8b5a3f69275c0a1fdbfeb64c1a8c36e753af8c52c58da9e389` | **RESTRICTED** (prohibición explícita de pre-descarga/caché) |
| 5 | `OSM_COPYRIGHT` | https://www.openstreetmap.org/copyright | 2026-09-29 | 200 | 21314 | `fd65145af733b0d170e0e33c340e59061cdba1f60803efb832477081516dca4c` | **VERIFIED** (ODbL publicada junto al dato; copiar/adaptar con atribución y share-alike) |
| 6 | `ALCALDIA_APERTURA_DATOS` | https://www.barranquilla.gov.co/documento/plan-de-apertura-de-datos/ | 2026-09-29 | **403** | — | `None` (no descargado) | **UNVERIFIED** (Cloudflare; coherente con `raw/golden/_retrieval_paths_probe*.json`) |
| 7 | `LONJA_METODOLOGIA_LOCAL` | `motor_tma_lonja_baq_v1.0/.../lonja_layer/lonja_baq_metodologia.yaml` (artefacto local, no URL) | 2026-09-29 | n/a | 13806 (medido) | `4ccd5832eacf3117424fa436765e80d3e9198b666d9e3c293063a5b207ebd348` | **DECLARED** (licencia CONTRACTUAL: se hashea el artefacto, no un término publicado) |

**Citas que sostienen cada dictamen**

- Mapillary (evidencia 1): «Tu uso de cualquier Contenido del usuario proporcionado por otros usuarios
  está sujeto a la licencia **Creative Commons Compartir Igual (CC BY-SA)**, salvo que indiquemos lo
  contrario.» → hay licencia, **no hay versión impresa** y hay excepciones por conjunto de datos ⇒
  `DECLARED`, no `VERIFIED`.
- Google (evidencia 3): «**No Scraping.** Customer will not export, extract, or otherwise scrape Google
  Maps Content… (i) **pre-fetch, index, store, reshare, or rehost** Google Maps Content outside the
  services; (ii) bulk download Google Maps tiles, **Street View images**…» · «**No Caching.** Customer
  will not cache Google Maps Content except as expressly permitted under the Maps Service Specific
  Terms.» · «**No Creating Content From Google Maps Content.**»
- Google (evidencia 4): «Content **pre-fetching, indexing, storing, or caching is generally
  prohibited**, except for place IDs and panorama IDs.» (La licencia CC BY 4.0 que aparece en esa
  página es del **contenido de la documentación**, no de las imágenes.)
- OSM (evidencia 5): «OpenStreetMap is open data, licensed under the **Open Data Commons Open Database
  License (ODbL)**… You are free to copy, distribute, transmit and adapt our data, as long as you
  credit OpenStreetMap and its contributors. If you alter or build upon our data, you may distribute
  the result only under the same licence.»

**Nota metodológica (páginas dinámicas).** Cuatro descargas consecutivas de la *misma* URL de Mapillary
devolvieron **cuatro `sha256` distintos** (`8d2d0d1e…`, `8364041c…`, `61f11ac2…`, `35e7243f…`; 118250 y
118254 bytes): el `sha256` identifica la **instantánea** consultada, no un artefacto estable del
proveedor. Por eso `verificar_evidencia_registrada()` re-descarga y **declara** la discrepancia en vez
de fingir que el contenido no cambió.

**Nota de tamaño del artefacto Lonja.** El registro del pack declara «10.466 bytes» para el YAML
metodológico; la medición real de esta ronda es de **13.806 bytes**. El `sha256` del archivo actual
(`4ccd5832…`) **sí coincide** con el que sella el estado de corrida del Golden, así que la divergencia
está en la nota de tamaño del registro (declaración desactualizada) y no en el artefacto que gobierna la
metodología: se declara aquí en lugar de silenciarse.

## 2. Estado por fuente (35 fuentes del registro)

| estado | nº | fuentes | efecto |
|---|---|---|---|
| `VERIFIED` | **1** | `OSM_OVERPASS` | término publicado + descargado + hasheado + autorización explícita |
| `DECLARED` | **2** | `MAPILLARY`, `LONJA_MARKET_BAQ` | hay licencia declarada/contractual: **no** habilita `VERIFIED`; `can_embed` sigue la declaración del registro (Mapillary sí, Lonja no) |
| `RESTRICTED` | **1** | `GOOGLE_STREET_VIEW` | prohibición explícita consultada: `can_persist=False`, `can_modify=False`, `can_embed=False` |
| `UNVERIFIED` | **29** | catastro (7), POT/riesgo (13), equipamiento (8), `CATASTRO_BAQ_ADOPCION_ANEXO1` | fail-closed: sin `VERIFIED` no se abre ninguna matriz ni se incrusta |
| `NOT_APPLICABLE` | **2** | `SOLAR_ENGINE`, `SHADOW_FACADE_EXPOSURE` | cálculo propio: no hay licencia de tercero |

**Nada se congela por un `DECLARED`** (`resumen()["congelado_por_licencia"] = False`). Lo único cerrado
es lo que la evidencia **prohíbe** (Google) y lo que no tiene permiso de incrustación declarado.

## 3. Qué falta para `VERIFIED` (declarado por fuente)

1. **`MAPILLARY`** — falta (a) descargar y hashear la página que fija la **versión** de la licencia
   (`CC BY-SA 4.0`), consultada hoy y bloqueada con **HTTP 403**, o (b) un documento del proveedor que
   confirme versión y alcance por conjunto de datos. Hasta entonces el uso de imágenes queda con
   atribución obligatoria + share-alike y, con `ARHIAX_IMAGERY_STRICT_TERMS=1`, la matriz **se cierra**
   (sólo `VERIFIED` incrusta).
2. **29 fuentes del Distrito** — falta la **licencia oficial de reutilización** publicada por la
   Alcaldía (la página de apertura de datos responde **403** y el geoportal responde 403 Cloudflare).
   Sin `URL + fecha + sha256` no hay `VERIFIED`. Compensación declarada: atribución obligatoria,
   `can_embed=False`, sin redistribución del crudo fuera del expediente.
3. **`CATASTRO_BAQ_ADOPCION_ANEXO1`** — es un documento aportado por el usuario, no una página de
   términos: falta la autorización de reutilización de la SNR.
4. **`LONJA_MARKET_BAQ`** — falta el **contrato firmado** de la Lonja BAQ que autorice uso y
   persistencia; hoy la autorización es declarada por el productor. El artefacto metodológico sí se
   hashea (`4ccd5832…`), y la fuente de mercado derivada (`LONJA_MARKET_BAQ`, `product_role=CORE_MARKET`,
   tabla `docs/source_pack/lonja_market_baq_v1.json`) viaja con ese hash.
5. **`GOOGLE_STREET_VIEW`** — **no hay nada que verificar para abrir**: la evidencia prohíbe almacenar y
   cachear. Sólo un documento contractual escrito de Google cambiaría el estado.

## 4. Fail-closed verificado (test negativo)

`autorizar_incrustacion()` es la **única** vía de incrustación y deniega cuando `can_embed=False`:

- `GOOGLE_STREET_VIEW` → `permitido=False`, `flujo="NINGUNO"`, motivo «el bloque declara
  can_embed=False…; provider_terms_status=RESTRICTED no habilita incrustación».
- Toda fuente del catálogo con `can_embed=False` (33 de 35, incluidas las 29 del Distrito) → denegada.
- `MAPILLARY` → `permitido=True` **sólo** porque el registro declara `can_embed_image=true` y el estado
  es `DECLARED`; con política estricta (`ARHIAX_IMAGERY_STRICT_TERMS=1`) se cierra igualmente.
- Un término **sin evidencia** nunca queda en `VERIFIED`: `terms_hash=None` exige motivo y el estado es
  `UNVERIFIED` (o `DECLARED`/`RESTRICTED` si el contenido consultado lo dicta).

## 5. Limitaciones reales

- Los hashes de las páginas de términos **no son reproducibles byte a byte** (contenido dinámico): sirven
  como instantánea fechada, y su re-descarga se declara en lugar de asumirse.
- Este documento **no modifica** `docs/source_pack/raw/`, ni PDF, valoración, fórmulas, compuerta, hash
  maestro ni `api/dictus_sources.py`; el pack v1.0 (`SOURCE_LICENSES.md`, manifest) sigue declarando
  Mapillary como `UNVERIFIED`/`DECLARED`: la divergencia es de **evidencia nueva**, y se declara aquí en
  lugar de silenciarse.
- Nada aquí habilita persistir imágenes de terceros fuera de lo ya declarado en el registro: el bloque
  de licencia **no amplía** permisos, sólo los declara y los cierra cuando falta evidencia.

---

# ANEXO v2 (2026-09-29) — licencia de IMÁGENES ≠ términos de API

**Pieza nueva:** `api/source_licenses_v2.py` (`source-licenses-v2/2.0.0`) · **Documento de evidencia:**
`docs/source_pack/IMAGERY_LICENSES.md` · **Aliados fuera del registry:**
`docs/source_pack/INSTITUTIONAL_PARTNERS.md`. **Este anexo NO modifica nada de lo anterior**: `api/source_licenses.py`
(v1) sigue intacto y su catálogo de 35 fuentes sigue siendo la declaración auditada del pack v1.

## A1. Por qué un bloque v2

La v1 responde con **un solo** campo (`provider_terms_status`) dos preguntas distintas. La v2 las separa y no las
mezcla: `IMAGERY_LICENSE_STATUS` (DERECHOS sobre las imágenes) y `API_TERMS_STATUS` (ADQUISICIÓN por la API). Los
permisos operativos se dictan **sólo** con la primera columna.

## A2. Evidencia nueva consultada el 2026-09-29 (URL · fecha · HTTP · bytes · sha256 · estado)

| id | URL | HTTP | bytes | `sha256` (instantánea) | estado de la evidencia |
|---|---|---|---|---|---|
| `MAPILLARY_TERMS_OF_USE` | https://www.mapillary.com/terms | 200 | 111094 | `e9ce3ac2fddf91013b86d5a3a7f56cf8424522e00e942dced10215331f330ea7` | `ACCESIBLE_VERIFICADA` (proveedor; «Effective date: February 15, 2024») |
| `MAPILLARY_HELP_CC_BY_SA_4_0` | https://help.mapillary.com/hc/en-us/articles/115001770409-CC-BY-SA-license-for-open-data | **403** | — | `None` | `INACCESIBLE_HTTP_ERROR` (sigue inaccesible, confirmado) |
| `MAPILLARY_HELP_CC_BY_SA_4_0_ARCHIVO` | Wayback captura `20260724100858` del mismo artículo oficial | 200 | 32538 | `165ec7abfa0b8b122d3c3c5b20851dd96b5cc2f1a7745df52145b18e63a0b34f` | `COPIA_ARCHIVADA_DE_DOC_PROVEEDOR` |
| `CC_BY_SA_4_0_DEED` | https://creativecommons.org/licenses/by-sa/4.0/ | 200 | 35745 | `6acd86b2893060f04d2b8d8743ef12baf046bb46973374c6e077e366cad01d66` | `ACCESIBLE_VERIFICADA` |
| `CC_BY_SA_4_0_LEGALCODE` | https://creativecommons.org/licenses/by-sa/4.0/legalcode | 200 | 51860 | `6c0f42e2d43700044349772d54265a315171f47d42f5e88cd380481bf18d814e` | `ACCESIBLE_VERIFICADA` |
| `MAPILLARY_TERMS_API` | https://www.mapillary.com/terms/api | 200 | 74354 | `ba4abe7a8b8e7db39adbdc9500534c5a578734579f321c727855804cff30d025` | **`SOFT_404`** (200 con «página no encontrada») |
| `MAPILLARY_TERMS_DATA` | https://www.mapillary.com/terms/data | 200 | 74357 | `800bd2f8439e0b94ec18340e71b26a276d78eca198790f93ec222370eab3e168` | **`SOFT_404`** |
| `MAPILLARY_API_DOC` | https://www.mapillary.com/developer/api-documentation | 200 | 131397 | `ed5e7b126c65c4139cdf94dbbf89526538189b820b0fd8d5f09aa24c8cb947c9` | `ACCESIBLE_SIN_MARCADORES_DE_LICENCIA` |
| `MAPILLARY_OPEN_DATA` | https://www.mapillary.com/open-data | 200 | 83624 | `0df9989bb9810085f9a4a55e572ac5614f628b993145eb96bb97c8e1b0c0126f` | `ACCESIBLE_SIN_MARCADORES_DE_LICENCIA` |
| `MAPILLARY_DATASETS` | https://www.mapillary.com/datasets | 200 | 81222 | `419521976f25c63dcd70406c354a8d8fec229d485f245fa13ce53f1ae82c5056` | `ACCESIBLE_SIN_MARCADORES_DE_LICENCIA` |
| `MAPILLARY_WIKI_TERCEROS` | https://wiki.openstreetmap.org/wiki/Mapillary | 200 | 78178 | `a6a6136450a881ebe27934074546916256daadae98569bebc39849efc01ec21c` | `TERCERO_NO_PROVEEDOR` (corrobora, no verifica) |

Los identificadores ya registrados en la v1 (Google, OSM, Alcaldía, Lonja) **no se renumeran**: el anexo añade
evidencia nueva y conserva intactos los registros 1–7 de arriba.

## A3. Hallazgo que cambia el estado de Mapillary **sólo para las IMÁGENES**

1. Los Términos de Uso **vigentes** (accesibles, hasheados) dicen en §3(b): «Your use of any **User Content provided
   by other users is subject to the Creative Commons Share Alike (CC BY-SA) license**, unless we indicate otherwise»
   y **enlazan** la licencia a `http://creativecommons.org/licenses/by-sa/4.0/` ⇒ la **versión 4.0** queda evidenciada
   por el propio proveedor (enlace, no texto impreso).
2. Los mismos términos **imprimen la obligación de atribución**, incluido el caso exacto que usamos: «If you are
   downloading individual images and serving them from your own servers, you must attribute the image(s) by visibly
   displaying the Mapillary logo and linking back to the Mapillary homepage or corresponding Mapillary image page.»
3. La página del centro de ayuda que la v1 registró como hueco (**403**) sigue dando **403** en vivo; su contenido se
   recuperó como **copia archivada** del artículo **oficial** («All images on Mapillary are shared under a CC-BY-SA
   license […] as long as they give attribution»), registrada como corroborante y **no** como acceso directo.
4. **No** hay documento de términos de **API** dedicado: `/terms/api` y `/terms/data` devuelven 200 con soft-404.

⇒ `IMAGERY_LICENSE_STATUS=VERIFIED` (alcance: familia CC BY-SA 4.0 + atribución visible con enlace + share-alike) y
`API_TERMS_STATUS=DECLARED` (los términos de API son §11/§12 del documento general; falta un documento dedicado).
La v1 mantiene `Mapillary=DECLARED`: es la lectura **conservadora del mismo hecho** y **no se contradice**, se
complementa (la v1 no separaba las dos preguntas ni registraba el enlace a la versión 4.0).

## A4. Google: sin cambios de política (sigue fail-closed) y ahora **sin bloqueo**

`IMAGERY_LICENSE_STATUS=API_TERMS_STATUS=RESTRICTED`, `can_persist/can_modify/can_embed=False` y
`product_role=OPTIONAL_ENRICHMENT` con `bloquea_source_pack=False`: un enriquecimiento opcional **no bloquea** nada
(ni `CONTRACT_FROZEN` ni `OPERATIONAL_READY`). Test negativo: persistir, modificar o incrustar se **deniega** con
motivo explícito.

## A5. Lonja: **no es una fuente** (vive fuera del Source Registry)

Esta pieza **no** crea `api/lonja_contract.py`, ni contrato de datos, ni `lonja_dataset_contract_v1.json`, y no
formaliza ningún dataset de Lonja: no hay archivo, columnas, periodicidad, vigencia ni valor por m² atribuidos a la
Lonja, y su ausencia **no** condiciona `CONTRACT_FROZEN` ni `OPERATIONAL_READY`. La Lonja se representa como
`institutional_partner` / `distribution_partner` / `stakeholder` en
`docs/source_pack/INSTITUTIONAL_PARTNERS.md`, con la divergencia del pack v1 declarada allí en lugar de silenciada.

## A6. Limitaciones del anexo

Los `sha256` son **instantáneas fechadas** de páginas dinámicas (cuatro lecturas de `/terms` dieron hashes distintos en
la misma sesión; el módulo guarda `hashes_observados` y declara la discrepancia al re-verificar). La versión 4.0 se
sostiene por un **enlace**. No hay verificación por conjunto de datos ni por imagen: de ahí
`permitir_persistencia_imagen()`, que cierra la imagen concreta cuando su licencia es distinta, NC o ausente.

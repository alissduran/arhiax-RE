# INSTITUTIONAL PARTNERS — aliados **fuera** del Source Registry

**Pieza declarante:** `api/source_licenses_v2.py::PARTNERS_INSTITUCIONALES`
(`source-licenses-v2/2.0.0`) · **Fecha:** 2026-09-29.

Este documento existe para una decisión de producto explícita: **la Lonja no es una fuente de datos**. No aporta datos
a DICTUS hoy, no es `source_id`, no es `authority_class`, no es proveedor de mercado y no tiene bloque de licencia,
estado de términos, contrato de datos ni ingesta. Si se necesita representarla, se representa **aquí**, como aliado
institucional / canal de distribución / *stakeholder*, **fuera** del Source Registry.

## 1. Aliados institucionales declarados

| `partner_id` | nombre | tipos | `es_fuente_de_datos` | aporta datos a DICTUS | en Source Registry | bloque de licencia | bloquea el pack |
|---|---|---|---|---|---|---|---|
| `LONJA_BAQ` | Lonja de Propiedad Raíz de Barranquilla — Junta Técnica de Avalúos | `institutional_partner`, `distribution_partner`, `stakeholder` | **`False`** | **`False`** | **`False`** | **no tiene** | **`False`** |

`partner_id` **no** es un `source_id`: no participa del catálogo de licencias (`catalogo()`), no aparece en
`matriz_permisos()`, no tiene `IMAGERY_LICENSE_STATUS` ni `API_TERMS_STATUS`, y **no** puede autorizar ni denegar
persistencia, modificación o incrustación, porque no aporta material licenciado de tercero.

## 2. Qué NO existe (y por qué)

- **No hay dataset de la Lonja**, ni contrato de datos, ni columna obligatoria, ni periodicidad, ni vigencia, ni valor
  por m² suministrado por la Lonja en esta pieza. Si un valor de mercado aparece hoy en el producto, su procedencia es
  **otra** (el artefacto metodológico propio y las fuentes declaradas en su propia fila), y se audita donde
  corresponde — no aquí.
- **No hay `api/lonja_contract.py`**, ni `docs/source_pack/LONJA_DATASET_CONTRACT.md`, ni
  `docs/source_pack/lonja_dataset_contract_v1.json`: no se formalizó ningún dataset de Lonja.
- **No hay estado `DATOS_AUSENTES` atribuido a la Lonja** desde esta pieza: un aliado institucional sin dataset no es
  una fuente con datos ausentes, es simplemente **no una fuente**.
- **No hay bloqueo de `CONTRACT_FROZEN` ni de `OPERATIONAL_READY`** por ausencia de datos de la Lonja
  (`bloquea_contract_frozen=False`, `bloquea_operational_ready=False`). La falta de datos de un aliado **no** congela
  el pack ni impide la operación.

## 3. Divergencia con el pack v1 — **RESUELTA** (2026-09-29)

El **pack v1** —`docs/source_pack/barranquilla_sources_v1.json`,
`docs/source_pack/lonja_market_baq_v1.json`, `api/market_sources.py`— declaraba
`LONJA_MARKET_BAQ` como fuente del registro (`PRODUCT_ROLE="CORE_MARKET"`) y
`tests/test_source_pack_market.py` lo exigía como fuente formalizada. Esa divergencia **ya no
existe**: la doctrina de esta pieza se aplicó al pack v1.

| artefacto | qué dice hoy sobre la Lonja | efecto |
|---|---|---|
| `api/source_licenses_v2.py` (esta pieza) | **no es fuente**; es `institutional_partner` | ninguna fuente de Lonja, ningún permiso, ningún bloqueo |
| `docs/source_pack/INSTITUTIONAL_PARTNERS.md` (este documento) | **no es fuente**, y no hay dataset | declaración de producto vigente |
| `docs/source_pack/barranquilla_sources_v1.{json,yaml}` | `LONJA_MARKET_BAQ` **retirada** de `sources` (34 fuentes) y declarada en `no_fuentes_institucionales.aliados.LONJA_BAQ` (**`es_fuente_de_datos: false`**, `aporta_datos_a_dictus: false`, `en_source_registry: false`, `product_role: NOT_A_SOURCE`) | **coherente** con esta pieza |
| `api/market_sources.py` | `SOURCE_ID` conservado por ser identificador histórico sellado, con `PRODUCT_ROLE="NOT_A_SOURCE"`, `ES_FUENTE_DE_DATOS=False` y consulta **fail-closed** (declara `SOURCE_UNAVAILABLE`; no sirve el valor como dato de fuente) | **coherente** con esta pieza |
| `docs/source_pack/BARRANQUILLA_SOURCE_PACK_MANIFEST.json` | sin `LONJA` en `approved_sources`, `source_metadata_hashes` ni `licenses.by_source`; limitación declarada «MERCADO SIN FUENTE EXTERNA VERIFICABLE» | **coherente** con esta pieza |
| `docs/source_pack/SOURCE_COVERAGE_MATRIX_040-646406.csv` | fila 18 de mercado con `source = SIN_FUENTE (parámetros declarados por la corrida)` y estado `SOURCE_UNAVAILABLE` | **coherente** con esta pieza |
| `api/source_resolution.py` | escalón de `mercado` **vacío** por decisión de producto → `SOURCE_UNAVAILABLE` declarado (nunca `NO_MATCH` ni valor sustituido) | **coherente** con esta pieza |
| Ejecutivo y técnico | sin ninguna mención a la Lonja como fuente ni como práctica (etiqueta verdadera: «parámetros declarados por la corrida … sin fuente externa automática verificada») | **coherente** con esta pieza |

Regla operativa vigente (sin excepciones): **ningún permiso ni estado de licencia se deriva de
la Lonja**, su ausencia **no bloquea** `CONTRACT_FROZEN` ni `OPERATIONAL_READY`, y **no existe**
una fuente de mercado en el Source Registry. Llegar a `OPERATIONAL_READY` en mercado exige una
fuente de mercado de tercero **verificable** (URL + fecha de consulta + `sha256` +
comparables) o la validación firmada del avaluador: mientras no exista, el valor de mercado se
declara como parámetro de la corrida (`docs/source_pack/acceptance_report.md` §7).

## 4. Cómo consultarlo

```bash
python api/source_licenses_v2.py --partners      # aliados institucionales (no fuentes)
python api/source_licenses_v2.py --auditoria     # verifica que la Lonja NO es fuente
python -m pytest tests/test_no_lonja_as_source.py -q   # guarda de doctrina (ejecutivo+técnico)
```

`auditoria_no_lonja()` devuelve `ok=True` mientras ningún `partner_id` se declare fuente ni entre en el catálogo; si
alguna vez apareciera `LONJA` como `source_id` del pack v2, la auditoría falla y lo lista en `sospechosos`.

# INVENTARIO DE MENCIONES «LONJA» · COMPUERTA SEMÁNTICA DEL FREEZE

**Objeto.** Cerrar el punto 1 de la compuerta: **CERO menciones a la Lonja COMO FUENTE**
en el ejecutivo, el técnico, el `ExecutiveDocumentModel`, el `DictusRunState`, la
procedencia, las pruebas y los manifiestos — distinguiendo y documentando la **única
excepción legítima**: las menciones que existen **PARA PROHIBIRLA**.

**Decisión de producto vigente** (`api/source_licenses_v2.py::PARTNERS_INSTITUCIONALES`,
`docs/source_pack/INSTITUTIONAL_PARTNERS.md`): la Lonja **no aporta datos a DICTUS**. No
es `source_id` del Source Registry, no tiene dataset, ni contrato de datos, ni URL, ni
bloque de licencia, ni valor por m² suministrado por ella. `LONJA_MARKET_BAQ` es un
**identificador histórico sellado** que viaja en hashes y NO se renombra.

---

## 1 · Taxonomía del veredicto

| veredicto | qué es | acción |
|---|---|---|
| `PROHIBICION_LEGITIMA` | texto/guarda/comentario que afirma que la Lonja **NO es fuente** | **CONSERVAR** |
| `IDENTIFICADOR_SELLADO` | id histórico que viaja en hashes (`SOURCE_ID`, `METHODOLOGY_ID`, `SNAP_*`, `artifact_id`, `partner_id`) y NO se imprime | **CONSERVAR** |
| `RUTA_O_PAQUETE_VENDOR` | ruta real del paquete `motor_tma_lonja_baq_v1.0/**` o nombre del YAML/carpeta leídos por el producto | **CONSERVAR** (renombrar rompe la lectura) |
| `OMISION_DE_ENTIDAD` | campo máquina que nombraba la institución como proveedora de la metodología | **ELIMINADO** — se declara `sin institución proveedora verificada` |
| `PRESENTA_COMO_FUENTE` | la menciona como fuente, proveedor, autoridad de datos, avaluador o práctica | **ELIMINADO** |
| `FUERA_DE_ALCANCE` | producto distinto (`api/arhia_title/*`, demo) o evidencia histórica congelada (`docs/forensics/**` ≠ `dictus_2b`) | declarado, NO tocado |

---

## 2 · Inventario final de los artefactos EN ALCANCE

Comando de verificación (repo raíz):

```
python -c "import json,pathlib,re;
for p in ['docs/forensics/040-646406/dictus_2b/DICTUS_RUN_STATE_040-646406.json',
          'docs/forensics/040-646406/dictus_2b/DICTUS_MANIFEST_040-646406.json']:
    t=pathlib.Path(p).read_text(encoding='utf-8')
    print(p, 'LONJA' if 'Lonja' in t else 'sin Lonja')"
```

| archivo | tipo de mención | veredicto | evidencia |
|---|---|---|---|
| `docs/forensics/040-646406/dictus_2b/DICTUS_EJECUTIVO_040-646406.pdf` | ninguna (6 páginas, texto extraído con `pypdf`) | **LIMPIO** | `tests/test_dictus_semantica_atributos.py::test_assert_lonja_no_esta_en_el_ejecutivo` |
| `docs/forensics/040-646406/dictus_2b/DICTUS_TECNICO_040-646406.pdf` | ninguna (17 páginas) | **LIMPIO** | `…::test_assert_lonja_no_esta_en_el_tecnico` |
| `docs/forensics/040-646406/dictus_2b/DICTUS_2.0C_TEXTO_EJECUTIVO_040-646406.txt` | ninguna | **LIMPIO** | `grep -i lonja` → 0 coincidencias |
| `DICTUS_RUN_STATE_040-646406.json` | `market_context.sector_metodologico.market_methodology_id` = `lonja_baq_metodologia` | `IDENTIFICADOR_SELLADO` | conservado (viaja en el hash maestro) |
| idem | `market_methodology_file` = `lonja_baq_metodologia.yaml` | `RUTA_O_PAQUETE_VENDOR` | conservado |
| idem | `sector_metodologico.methodology_entity` y `provenance.methodology_entity` | `OMISION_DE_ENTIDAD` → hoy `artefacto local de metodología (sin institución proveedora verificada)` | `api/market_context.py::resolve_market_sector` + `api/atribucion_mercado.py::entidad_declarada` |
| idem | `provenance.artifact_autor` | `OMISION_DE_ENTIDAD` → mismo texto honesto | ídem |
| `DICTUS_MANIFEST_040-646406.json` | mismos cuatro campos en `modelo.market_context` | `IDENTIFICADOR_SELLADO` ×2 + `OMISION_DE_ENTIDAD` ×2 | ídem |
| idem | `modelo.observations[OBS-VALUATION-*].source` = `lonja_baq_metodologia` | `PRESENTA_COMO_FUENTE` → **ELIMINADO**: la observación declara `parámetros de mercado declarados por la corrida` y el id sellado viaja en su propio campo `methodology_id` | `api/dictus_decision.py::observaciones_de` |
| `public/dictus/DICTUS_MANIFEST_040-646406.json` | copia byte a byte del manifiesto | igual que el manifiesto | `dictus_run.py` publica el mismo artefacto |
| `docs/source_pack/lonja_market_baq_v1.json` | `source_name`, `institution`, `methodology_entity` | `OMISION_DE_ENTIDAD` → **ELIMINADO** (regenerado) | `python api/market_sources.py --escribir-tabla` |
| idem | `source_id`, `methodology_id`, `table_version`, `source_version`, ruta del artefacto | `IDENTIFICADOR_SELLADO` / `RUTA_O_PAQUETE_VENDOR` | conservado |
| `docs/source_pack/SNAPSHOT_INVENTORY.json` | `snapshots[].artifact_id` = `SNAP_LONJA_METODOLOGIA`, `fuentes` = (`LONJA_MARKET_BAQ`,), ruta del YAML | `IDENTIFICADOR_SELLADO` + `RUTA_O_PAQUETE_VENDOR` | la fila se declara NO USABLE por vigencia vencida |
| idem | `origen_declarado` afirmaba «documento contractual autorizado dentro del motor TMA» | `PRESENTA_COMO_FUENTE` → **ELIMINADO**: hoy declara `NOT_A_SOURCE`, sin documento contractual ni institución verificada | `api/acquisition.py::SNAPSHOTS[SNAP_LONJA_METODOLOGIA]` |
| `docs/source_pack/BARRANQUILLA_SOURCE_PACK_MANIFEST.json` | criterio `market_formalizada` afirmaba «fuente formalizada (AUTHORITATIVE_CONTRACTUAL, CORE_MARKET)» | `PRESENTA_COMO_FUENTE` → **ELIMINADO**: el criterio declara que el dominio `mercado` NO tiene fuente y el id sellado es `NOT_A_SOURCE` | `api/acquisition.py::CRITERIOS_CONTRACT_FROZEN` |
| `docs/source_pack/SOURCE_ACQUISITION_MATRIX_040-646406.csv` | fila `mercado` con `source_id` sellado, rol `CORE_MARKET` y estado NO DISPONIBLE | `IDENTIFICADOR_SELLADO` (contrato probado en `test_source_pack_acquisition_modes.py`, que exige que la fuente esté FUERA de `sources` y que la fila NO sea DISPONIBLE) | conservado |
| `docs/source_pack/SOURCE_COVERAGE_MATRIX_040-646406.csv` | fila `18-mercado` → `SIN_FUENTE (parámetros declarados por la corrida)` | `PROHIBICION_LEGITIMA` | `test_no_lonja_as_source.py::test_la_matriz_de_cobertura_no_atribuye_el_mercado_a_la_lonja` |
| `docs/source_pack/barranquilla_sources_v1.json` / `.yaml` | `no_fuentes_institucionales.aliados.LONJA_BAQ` con `es_fuente_de_datos: false`, `en_source_registry: false`, `product_role: NOT_A_SOURCE` | `PROHIBICION_LEGITIMA` | `test_no_lonja_as_source.py::test_el_registro_no_declara_la_lonja_como_fuente` |
| `api/dictus_ejecutivo.py`, `api/dictus_secciones.py`, `api/dictus_estado.py`, `api/dictus_manifiesto.py`, `api/receipts.py` | **cero coincidencias** | **LIMPIO** | `grep -il lonja api/dictus_*.py` |
| `tests/**` | guardas de doctrina + ids sellados en fixtures | `PROHIBICION_LEGITIMA` / `IDENTIFICADOR_SELLADO` | `tests/test_no_lonja_as_source.py` (guarda), `test_source_pack_*.py` |
| `api/acquisition.py`, `api/market_context.py`, `api/market_sources.py`, `api/source_licenses*.py`, `api/source_resolution.py`, `api/atribucion_mercado.py` | comentarios, docstrings y banderas que PROHÍBEN la atribución + el vocabulario del filtro (`_ATRIBUCION_NO_ACREDITADA`, `limpiar_atribucion_no_acreditada`, `auditoria_no_lonja`) + rutas del paquete leído | `PROHIBICION_LEGITIMA` / `RUTA_O_PAQUETE_VENDOR` | `test_no_lonja_as_source.py::test_los_modulos_de_documento_no_tienen_literales_con_lonja` |
| `motor_tma_lonja_baq_v1.0/**/lonja_baq_metodologia.yaml` | **artefacto de donde SE LEE el valor** (`valor_suelo_por_sector.Miramar.valor_central_m2`) y su `declaracion.entidad` | el artefacto NO se muta (es la traza de lo que se declaró); el producto **reescribe la etiqueta al exponerla** y clasifica su origen como `MANUAL_CONFIG` | `api/atribucion_mercado.py` · `docs/source_pack/MARKET_CONTEXT_AUDIT.md` |
| `docs/forensics/**` ≠ `dictus_2b/**` | evidencia histórica congelada | `FUERA_DE_ALCANCE` (no se reescribe) | restricción de la compuerta |
| `api/arhia_title/demo.py` (`avaluador="Avaluador Lonja BAQ"`), `api/arhia_title/report_html.py` | producto DISTINTO (demo del Informe Preliminar) | `FUERA_DE_ALCANCE` — **declarado para decisión del titular** | no forma parte del DICTUS entregado |

---

## 3 · La única excepción legítima, en una frase

Sobreviven tres clases de mención y **ninguna afirma una fuente**:

1. **`PROHIBICION_LEGITIMA`** — la guarda (`tests/test_no_lonja_as_source.py`), los
   documentos de doctrina (`INSTITUTIONAL_PARTNERS.md`, `MARKET_CONTEXT_AUDIT.md`,
   `acceptance_report.md`) y el propio filtro de texto
   (`api/atribucion_mercado.py`), que existen **para prohibir** la atribución.
2. **`IDENTIFICADOR_SELLADO`** — `SOURCE_ID="LONJA_MARKET_BAQ"`, `METHODOLOGY_ID`,
   `SNAP_LONJA_METODOLOGIA`: identificadores que viajan en hashes y se conservan pero
   **no se imprimen** ni se declaran como fuente.
3. **`RUTA_O_PAQUETE_VENDOR`** — la ruta real del paquete vendorizado que el producto
   **lee**; renombrarla rompería la lectura del artefacto.

Todo lo demás — `OMISION_DE_ENTIDAD` y `PRESENTA_COMO_FUENTE` — fue **eliminado** en esta
compuerta, y las pruebas de `tests/test_dictus_semantica_atributos.py` fallan si vuelve.

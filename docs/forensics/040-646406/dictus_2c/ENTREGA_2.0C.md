# DICTUS 2.0C — ALTA FIDELIDAD EJECUTIVA (contrato del entregable)

**Veredicto:** `DICTUS 2.0C — EXECUTIVE HIGH-FIDELITY CLOSED`.
41 hechos materiales auditados · **40 impresos · 0 pérdidas** · 1 sin fuente en la corrida
(el mapa satelital no fue aportado) · 6 páginas · 0 solapamientos de texto · 0 desbordes.

## 1 · Qué estaba mal (el hecho, no la intención)

La reducción 17 → 6 páginas de 2.0B-R1 cumplió el límite físico, pero el estado canónico
**no transportaba hechos que el producto YA calculaba** y el renderer los sustituía por
placeholders. La auditoría de completitud (sección 3) localizó la causa en la PROYECCIÓN
DEL ESTADO, no en el motor:

| Familia | Hecho perdido | Dónde se perdía |
|---|---|---|
| Contexto de mercado | sector metodológico, tasa y su fuente, metodología y versión, blockers de la valoración | `market_context` se construía dentro de `compile_pdf` y **no entraba al contexto del gate** ⇒ no llegaba al estado ni al modelo |
| Geometría | procedencia de la coordenada oficial, alcance de esa geometría y **binding canónico (VERIFIED)** | el modelo buscaba las coordenadas dentro del contexto administrativo, donde nunca estuvieron ⇒ la página 6 decía «NO_COMPARABLE» mientras el técnico decía `binding='VERIFIED'` |
| Tracto registral | forma de adquisición con su acto inscrito | la modalidad se leía de un campo vacío; el técnico la *infería* del simple conteo de anotaciones (una etiqueta sin fuente) |
| Equipamiento | tipo de servicio y **tiempo a pie** de cada lugar | estaban en el estado (`walking_time_estimate`) y el renderer imprimía solo 2 ejemplos sin tiempo |
| Activos gráficos | mapa de puntos de interés y sombras de la corrida | se generaban en el directorio del run y **nadie los registraba en el estado**: la página 5 usaba esquemas |
| Procedencia urbana | fuente actual por atributo (LIVE_OFFICIAL / PACKAGED_REFERENCE) | en `urban_source_summary`, fuera del contexto del gate |

Además, por diseño de 2.0B-R1: la página 1 mostraba los 6 conflictos históricos como seis
hallazgos `ALTO` (dominando la narrativa), el bloque jurídico reutilizaba una sola acción
para la hipoteca y para la afectación, y el texto de seguro afirmaba «evidencia sellada»
mientras el pie imprimía un sello parcial.

## 2 · Causa raíz de la pérdida de equipamiento (POI)

Cadena medida en la corrida real:

| Eslabón | Contenido |
|---|---|
| Consulta (Overpass) | `out center 200`: la respuesta puede traer decenas de elementos |
| Motor (`poi_engine`) | **tope duro de 3 por categoría** (`[:3]` al parsear Overpass, línea 376; `max_por_categoria=3` en `merge_poi_sources`, línea 191) |
| Observador → `DictusRunState` | 12 ítems (3 por categoría) con `distance_m`, `type`, `walking_time_estimate`, `source`, `queried_at` |
| `ExecutiveDocumentModel` | el `poi_state` completo |
| PDF ejecutivo (2.0B-R1) | **solo 2 ejemplos por categoría, sin tipo ni tiempo a pie** |
| PDF ejecutivo (2.0C) | 3 lugares por categoría con **tipo, distancia y tiempo a pie**, más la distancia del más cercano |

**La pérdida no estaba en el bridge estado→PDF:** el motor expone como máximo 3 por
categoría (decisión de diseño de `poi_engine`, sin tocar) y era el **renderer** el que
descartaba el tercer ítem y el tiempo a pie. 2.0C no inventa resultados: cuando una
categoría no tiene datos **no imprime «0 detectados»** — declara `SIN COINCIDENCIA
(consulta completa)`, `FUENTE NO DISPONIBLE` o `NO EVALUADO` según el estado real, y si
hay ítems sin distancia imprime `DISTANCIA NO DISPONIBLE`.

## 3 · Informes de la ronda (artefactos versionados)

| Informe | Archivo |
|---|---|
| `MATERIAL_FACT_COMPLETENESS_MATRIX` (41 hechos × 4 capas + fuente, estado, pérdida y causa) | `MATERIAL_FACT_COMPLETENESS_MATRIX.md` / `.json` |
| `STATE_PROJECTION_LOSS_REPORT` | `STATE_PROJECTION_LOSS_REPORT.json` |
| `POI_ROOT_CAUSE_REPORT` | `POI_ROOT_CAUSE_REPORT.json` |
| Comparativo antes/después sobre los PDF | `COMPARATIVO_ANTES_DESPUES.md` |
| Manifest y estado de la corrida auditada | `DICTUS_MANIFEST_040-646406.json`, `DICTUS_RUN_STATE_040-646406.json` |

Reproducible con:

```
python scripts/dictus_auditoria_completitud_2c.py     # matriz + informes + PDF
python scripts/dictus_comparativo_2c.py               # antes (2.0B-R1) vs después (2.0C)
python scripts/dictus_render_ejecutivo.py --salida docs/forensics/040-646406/dictus_2c
python -m pytest tests/test_dictus_20c_fidelidad.py -q
```

## 4 · Composición y layout (§11/§25/§26)

* **Motor de layout real**: cada componente implementa `medir()` → `dibujar()` → altura
  consumida; las páginas se componen en flujo vertical y no queda ningún offset rígido
  después de un `wrap()`. El encabalgamiento del bloque «QUÉ DEBE HACERSE PARA CERRAR LA
  OPERACIÓN» (página 2) era exactamente ese patrón.
* **Trazabilidad de la retícula**: 84 bounding boxes registrados y verificados
  (`verificar_retícula()`); además la prueba comprueba el texto real con `pymupdf`.
  Resultado: **0 solapamientos y 0 desbordes** en las seis páginas.
* **Cuerpo tipográfico 8.5–10 pt** (títulos 11–13.5 pt), con columnas, tarjetas, mapa y
  mini-tablas en vez de reducir letra para meter datos.

## 5 · Artefacto de esta corrida

| Dato | Valor |
|---|---|
| Documento | `DICTUS_EJECUTIVO_040-646406.pdf` · **6 páginas** |
| sha256 | `b75c08c6083b3c362174276db9564aa2324fa90579ec1a20948d4ecb2a2dc10e` |
| DICTUS ID | `DX-040-646406-20260928` |
| DICTUS_MASTER_HASH | `b106972414db397b320a71213453ccadd59b31884251ee774ffb3d3e83819fdf` |
| run_id | `881ebf3d-4958-4892-978c-b7f62151a1e0` |
| Evidencias | 10 (`PARCIAL_CON_DECLARACIONES`) |
| Retícula | sin violaciones · 84 cajas registradas · 0 cajas de texto solapadas |
| Hechos auditados | 41 (impresos 40 · pérdidas 0 · sin fuente 1) |
| Renders | `paginas/ejecutivo_p1..p6.png` |

## 6 · Lo que NO se tocó

Identidad canónica, valoración (fórmulas y banda), POT, screening y sanciones, HMAC,
contexto de mercado (lógica), binding canónico, hallazgos, consultas POI y arquitectura de
hash. Los conflictos históricos de POT (8 vs 11 pisos, tratamiento, uso) **siguen
abiertos** y ahora se imprimen con **valor actual + valores históricos + estado de
coherencia + fuente actual**, sin elegir una de las dos cifras y sin esconder la vigente.

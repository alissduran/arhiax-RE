# DICTUS 2.0 — REPORTE ANTES / DESPUÉS

Folio: **040-646406** · DICTUS ID: **DX-040-646406-20260924** · hash maestro: `DC355D4553A8…9C4B`

## 1 · Estructura

| | Antes (DICTUS 1.x) | Ahora (DICTUS 2.0) |
|---|---|---|
| Páginas | **17** de cuerpo técnico mezclado | **6** ejecutivas + 1 hoja de anexos + **17** de anexos |
| Decisión | Dispersa en los capítulos 10, 11, 12 y 13 | **Página 1**: inmueble, valor, hallazgos, actores, acciones y sello |
| Hallazgos | Capítulo 10 (página 11) | **Página 1**, cada uno con actores afectados y acción |
| Hojas de ruta | Capítulos 14 y 15 | **Página 2** (condiciones para cerrar) y **3** (preparación de la operación) |
| Listas de screening | «listas restrictivas aplicables» sin nombrar | **Página 3**: columnas con las listas realmente consultadas |
| POT / uso | uso catastral impreso en la fila del uso POT | **Página 4**: destino catastral y uso normativo **separados** |
| Coherencia histórica | inexistente | **Página 4**: bloque *Coherencia del dato* + hallazgo cuando hay conflicto |
| Hash | sello de ejecución + hash por artefacto | **un solo** `DICTUS_MASTER_HASH` visible; el hash del PDF va al Anexo G |
| Provenance | JSON, feature_id, parser_version en el cuerpo | bloque **TRAZABILIDAD** en lenguaje llano; lo técnico al anexo |
| Falsa precisión | `$0`, cuota `$0`, «LTV 0%» posibles | estado + motivo; **nunca** un cero por ausencia |

## 2 · Tabla de contenidos: anterior vs nueva

**Cuerpo técnico anterior (ahora Anexos A–I):**

- 00 - Naturaleza de este Documento
- 01 - Identificacion del Activo
- 02 - Localizacion Geográfica del Inmueble
- 03 - Analisis de Equipamiento Urbano y Puntos de Interes (POI)
- 05 - Pre-dictamen jurídico (Titulux)
- 06 - Analisis Catastral y Urbanístico
- 07 - Estimación Referencial de Mercado (NO es avalúo)
- 08 - Analisis Hidrológico y de Riesgos
- 09 - Screening de Contrapartes y Debida Diligencia
- 10 - Hallazgos Clasificados por Severidad
- 11 - Resumen de Hallazgos
- 12 - Score Actuarial Integrado
- 13 - Estructurabilidad Fiduciaria y Carga Económica
- 14 - Recomendaciones Operacionales
- 15 - Ruta de Verificación Profesional
- 16 - Declaracion de Alcance
- 17 - Sello de Integridad del Insumo (Provenance)

**Cuerpo ejecutivo nuevo:**

| Página | Contenido |
|---|---|
| 1 | Información general + estado de decisión (5 indicadores) + hallazgos con actores + sello global |
| 2 | Títulos, condiciones jurídicas y acciones requeridas |
| 3 | Contrapartes, listas consultadas por sujeto y preparación de la operación |
| 4 | POT, uso, destino, edificabilidad, riesgos y **coherencia del dato** |
| 5 | Entorno: equipamiento, accesibilidad, asoleamiento y sombras |
| 6 | Identidad, geometría, binding y valoración con su metodología |
| Anexos | Hoja separadora + cuerpo técnico completo (A–I) |

## 3 · Información que salió del cuerpo hacia anexos

| Contenido | Anexo |
|---|---|
| URLs completas de servicios y endpoints | C, D, E |
| feature_id, layer y source_system de cada capa | B, C |
| Versiones de parser, matcher y algoritmo | D, F |
| Snapshots de listas y su SHA-256 | D |
| query_hash, content_hash y evidence_hash individuales | D, G |
| SHA-256 completo del PDF emitido | G |
| Recibos de ejecución completos | G |
| Tabla anexa de geometría, CTM12 y reproyección | C |
| Detalle de capas del POT consultadas (layer por layer) | C |
| Inventario completo de equipamientos y sus fuentes | E |
| Detalle técnico del motor de sombras y su geometría | E |
| Declaración de alcance y limitaciones | H |
| Matriz histórica de atributos y conflictos | I |

> Nada se eliminó: todo el detalle técnico sigue en el expediente. Lo que cambió es **dónde** vive cada cosa, aplicando la prueba de información material (¿puede cambiar la decisión de comprar, vender, financiar, asegurar o comercializar?).

## 4 · Verificación del entregable

- Páginas ejecutivas: **6** (máximo exigido: 6).
- Expediente total: **24** páginas.
- Evidencias en el manifest: **10** (estado PARCIAL_CON_DECLARACIONES).
- `DICTUS_MASTER_HASH`: `dc355d4553a80509cd84e3cdbb2888fb486b33cb4b067aae64fb0df7fc2e9c4b`
- `pdf_binary_sha256`: `51be125f7e25b2c40ac5a36f249e086d7b2489ff03eb9a467733973c8ff929e6` (hash distinto, por diseño).
- Atributos comparados en la historia: **25** en **14** versiones; cambios detectados **187**.

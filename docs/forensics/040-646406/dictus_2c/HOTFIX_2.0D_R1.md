# HOTFIX DICTUS 2.0D-R1 — PRESUPUESTO DE LA PÁGINA 6 / SIN PÉRDIDA DE DATOS

**Folio auditado:** 040-646406 (caso REAL de producto) · **Run:** `docs/forensics/040-646406/dictus_2b`
**Dictus ID:** DX-040-646406-20260928 · **Gramática:** `dictus-decision-grammar/1.0.0`

## 0. Resultado en una línea

`P6 remaining` pasó de **41 pt (desborde en producto)** a **128.8 pt**, con **un solo bloque
inferior de trazabilidad**, **hasta 3 condiciones impresas + recuento declarado**, y
**sin pérdida material** (matriz de completitud: 41 hechos, 40 impresos, **0 pérdidas**, 1
`SIN_FUENTE`). El gate **sigue rechazando** cualquier PDF desbordado.

## 1. Antes / después medido (reproducción fiel del fallo)

El fallo se reprodujo con el caso real llevado a la rama de valoración BLOQUEADA con 6
condiciones declaradas (misma clase que el reporte de producto):

| | antes | después |
|---|---|---|
| P6 `remaining_height` | **16.7 pt** ❌ (desborde) | **92.8 pt** ✅ |
| P6 `consumed_height` | 763.1 pt | 687.1 pt |
| Violaciones de retícula | `P6 desborda: quedan 17 pt` **+** `«traza» × «pie»` (10 073 pt²) | **ninguna** |
| Caso Golden real (valoración autorizada) | 78.7 pt | **128.8 pt** |
| P6 en producto (reporte del usuario) | 41 pt | ≥ 87 pt (mismo recorte de 46 pt + tope de blockers) |

Presupuesto vertical REAL de las seis páginas del Golden tras el hotfix:

`P1 = 112.8 · P2 = 161.6 · P3 = 82.6 · P4 = 92.8 · P5 = 56.9 · P6 = 128.8` (límite 56 pt · objetivo 65)

## 2. Cambio exacto de layout (solo página 6)

| # | Cambio | Δalto |
|---|---|---|
| 1 | **§2/§3 · Bloque `Traza` (46 pt) eliminado SOLO en P6.** Se sustituye por UNA línea compacta de 8.2 pt: `TRAZABILIDAD · Fuentes: Metodología de mercado (Lonja) · Catastro · Identidad canónica · Consulta: <fecha>`. El pie global ya demuestra ensayo, sello, hash maestro y recuento de evidencias en TODAS las páginas: **no se duplica nada**. | −46 +11 = **−35** |
| 2 | **§6 · Nota metodológica** (`NORMA · CONCEPTO TÉCNICO · VALIDACIÓN EXPERTA`, bloque de ~11 pt fuera del panel) pasa a ser la última línea del panel de valoración/bloqueos: `Metodología: norma + concepto técnico + validación profesional · detalle completo en el informe técnico.` | −11 (bloque) / +12 (dentro del panel) ≈ **0** neto en P6 autorizada |
| 3 | **§4 · Tope de condiciones impresas:** el panel de valoración bloqueada imprime **hasta 3** condiciones materiales y declara `+ N condición(es) adicional(es) · lista completa en el informe técnico (contexto de mercado) y en el expediente de decisión.` | −12 por condición extra |
| 4 | Panel de valoración autorizada: 78 → **92 pt** para alojar la línea de metodología sin recortar valor, rango, valor/m², área, vigencia, sector y método. | +14 |
| 5 | Panel de bloqueos: alto **calculado** (86 pt mínimo; 74 + líneas×12 + 12) en lugar de crecer sin control. | adaptativo |

**No se tocó:** `PIE_Y = 56` · `MAX_PAGINAS_EJECUTIVO = 6` · gramática de decisión ·
identidad · valoración · screening · POT · POI · modelo de sombras · hash maestro ·
manifest · release gate. **No se desactivó** `VIOLACIONES`.

## 3. Prioridad semántica de P6 (§5) — intacta

1. Identidad del inmueble (9 filas: dirección, matrícula, NUPRE, predial, unidad, área,
   régimen, uso, tipología) → 2. Estado de identidad + `DECISIÓN DICTUS` → 3. Geometría
   oficial (hasta 4 líneas) → 4. Valor estimado y su decisión (`INFORMACIÓN VERIFICADA` o
   `NO EMITIR VALORACIÓN`) → 5. Condiciones materiales → 6. Metodología en una línea →
   7. Provenance compacto. Nada de 1–5 se sacrificó: la prueba
   `test_p6_conserva_identidad_geometria_y_valor` verifica fila por fila contra el modelo.

## 4. `page_budget(page_number)` (§7)

Nueva API en `api/dictus_ejecutivo.py`:

```python
de.page_budget(6)
# {'page_number': 6, 'available_height': 723.89, 'consumed_height': 651.14,
#  'remaining_height': 128.75, 'footer_limit': 56.0, 'overflow': False,
#  'identity_row_count': 9, 'blocker_count': 0, 'blockers_printed': 0}
```

* `available_height` = `TOPE − PIE_Y` (banda de contenido real), `footer_limit` = `PIE_Y`.
* Invariante comprobada: `available + footer_limit = consumed + remaining`.
* El cierre de cada página pasa por `_cerrar_pagina()`, que registra el presupuesto **y**
  declara el desborde: un solo lugar, mismo mensaje (`P6 desborda: quedan N pt`).
* El presupuesto entra al **manifest del producto** (`render_budget`) y al informe de
  auditoría. **No es bloque canónico: no altera el hash maestro.**

## 5. Blindaje con pruebas (§9/§10/§11)

`tests/test_dictus_20d_r1_p6.py` (11 pruebas, 10 pasan y 1 fallo esperado declarado):

| Prueba | Qué exige |
|---|---|
| `test_p6_maximum_realistic_content` | identidad completa + dirección larga + NUPRE + predial + unidad + régimen + uso + geometría larga + valoración autorizada → **sin desborde** y `remaining ≥ 65` |
| `test_p6_conserva_identidad_geometria_y_valor` | cada fila de identidad del modelo se imprime (no se recorta contenido para caber) |
| `test_p6_un_solo_bloque_de_trazabilidad` | **un** `DICTUS_MASTER_HASH` y **un** `Evidencias` en P6 (fin del Traza+pie duplicado) |
| `test_p6_blocked_with_many_reasons` | 6 condiciones declaradas: `remaining ≥ 65`, se imprimen 3 y se declara `+ N`; el modelo y el `VALUATION_GATE` conservan **todas** |
| `test_p6_blocked_sin_condiciones_no_inventa_linea` | sin condiciones extra no aparece la línea `+ N` |
| `test_page_budget_de_las_seis_paginas` | las 6 páginas declaran su presupuesto; P1–P4 y P6 sin desborde |
| `test_el_cuerpo_no_se_degrada_para_caber` | `TOPE_BLOCKERS_PDF = 3` y `CUERPO_MINIMO_PT = 8.2` (nada de 6–7 pt) |
| `test_el_gate_sigue_rechazando_un_pdf_desbordado` | forzando el desborde, `auditar_ejecutivo` **rechaza** (`retícula`) |
| `test_la_trazabilidad_sigue_en_las_seis_paginas` | P1 con `SELLO GLOBAL`; P2–P6 con `TRAZABILIDAD`; hash y evidencias en las 6 |
| `test_el_golden_respeta_el_presupuesto_de_p6` | el **caso real** (manifest de producto) cumple `remaining ≥ 56` y registra `blocker_count` / `identity_row_count` |
| `test_p5_presupuesto_del_fixture_minimo` | **(xfail declarado)** ver §7 |

## 6. Smoke del producto (§12)

`python scripts/dictus_smoke_2d_r1.py` — mismo camino que la API
(`compile_pdf` → `construir_entregables` → `auditar_ejecutivo`) sobre la corrida real:

```
páginas               : 6 (límite 6)
auditoría arquitectura: ok=True · fallos=0
P1 DECISIÓN DEL INMUEBLE → P2 DECISIÓN JURÍDICA → P3 DECISIÓN DE CONTRAPARTES
→ P4 DECISIÓN TERRITORIAL Y URBANÍSTICA → P5 ENTORNO, EQUIPAMIENTO, ASOLEAMIENTO Y SOMBRAS
→ P6 IDENTIDAD, MERCADO Y VALOR
P6 consumido          : 651.1 pt
P6 restante           : 128.8 pt (límite 56 · objetivo 65)
P6 blockers           : 0 declarados · 0 impresos
P6 filas identidad    : 9
P6 desborda           : False
presupuesto por página: P1=112.8 · P2=161.6 · P3=82.6 · P4=92.8 · P5=56.9 · P6=128.8
RESULTADO: OK · entrega apta
```

**Límite declarado de este smoke:** no se ejecutó la UI desplegada en Vercel (no hay
credenciales en esta sesión y no se reutiliza la contraseña que se pegó en el chat en una
ronda anterior). El smoke corre el **mismo camino de código** que el POST del producto y
valida el PDF físico con la misma aserción dura (`auditar_ejecutivo`). Un POST real
desplegado sigue pendiente de quien tenga credenciales.

## 7. Riesgos declarados (no ocultos)

1. **P5 sigue siendo la página más ajustada: 56.9 pt** en el caso real (justo por encima
   del límite de 56). Con un contenido mínimo (fixture sin activos visuales) **desborda
   25.1 pt**. La prueba que lo exige queda como **fallo esperado** (`xfail`) documentado,
   porque el hotfix pedía **solo** P6 y eliminar el `Traza` de P5 iría contra esa
   instrucción. **Recomendación:** hotfix P5 con el mismo criterio o presupuesto adaptativo.
2. **Variabilidad de fuente observada durante el hotfix:** la corrida de producto de este
   hotfix recibió **5 ítems de POI** (algunas categorías declaradas sin fuente) y la
   corrida independiente de auditoría **12 ítems** con las cuatro categorías `AVAILABLE`.
   El documento **declara lo que la fuente devolvió** en cada caso; no se rellenó nada.
3. **Trazabilidad al «Anexo F»:** el producto no tiene un anexo rotulado F. No se inventó
   la referencia: la línea de desborde remite al **informe técnico (sección de contexto de
   mercado, que imprime la lista completa de pendientes)** y al **expediente de decisión**
   (`DICTUS_DECISION_MODEL_*.json`, `decision_gates[].blocking_conditions`). Si se quiere
   un anexo F físico, es una instrucción aparte.
4. **Inspección visual:** el modelo de esta sesión no acepta imágenes, así que **no firmo
   una revisión visual**. Evidencia adjunta: PNG de P6 y P1
   (`docs/forensics/040-646406/dictus_2c/paginas/hotfix_2.0d_r1_p6.png` y `…_p1.png`),
   79 cajas registradas, cero solapamientos y cero desbordes medidos.

## 8. Suite completa

```
897 passed, 2 skipped, 1 xfailed, 1 deselected  (4:24)
```

* `1 xfailed` = riesgo de P5 declarado en §7.1.
* `1 deselected` = `tests/test_remediacion_03g.py::TestGoldenVivo` (fallo deliberado y
  preexistente, `SOURCE_UNAVAILABLE`).
* `1 failed` **ajeno a este hotfix**: `tests/test_gpv_f77.py` (`AttributeError: 'Form' object
  has no attribute 'strip'` en `api/index.py:1134`). `api/index.py` **no está modificado**
  en este trabajo; es un fallo de entorno/versión previo.

## 9. Artefactos

* `docs/forensics/040-646406/dictus_2b/DICTUS_EJECUTIVO_040-646406.pdf` (6 páginas,
  `ok=True`, sha256 `b1e3e177d8f03dde…`) y `DICTUS_MANIFEST_040-646406.json` con
  `render_budget` por página.
* `docs/forensics/040-646406/dictus_2c/`: matriz de completitud, informe de auditoría con
  `presupuesto_vertical` / `p6_presupuesto` / `paginas_en_desborde`, artefactos de la
  cadena de decisión y las capturas PNG de P6/P1.
* `tests/test_dictus_20d_r1_p6.py` · `scripts/dictus_smoke_2d_r1.py`.

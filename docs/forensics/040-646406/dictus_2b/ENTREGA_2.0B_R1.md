# DICTUS 2.0B-R1 — ENTREGA DEL DOCUMENTO EJECUTIVO (contrato del entregable)

**Veredicto de esta ronda:** el artefacto que recibe el usuario es
`DICTUS_EJECUTIVO_<folio>.pdf`, de **seis páginas**, en el orden aprobado, y la
entrega se **falla** si el PDF físico no cumple ese contrato. El dictamen técnico
viaja como **anexo**, nunca como documento principal.

## 1 · Qué estaba mal (el hecho, no la intención)

2.0B construyó el `ExecutiveDocumentModel` y su renderer, pero el **producto** seguía
compilando y sirviendo el dictamen legacy:

| Camino del producto | Antes (2.0B) | Ahora (2.0B-R1) |
|---|---|---|
| `/api/dictamenes/generar` (síncrono) | `ARHIAX_Dictamen_<folio>_final.pdf` (17 pp) | `DICTUS_EJECUTIVO_<folio>.pdf` (6 pp) |
| worker `/api/v1/pdf/worker` | guardaba el técnico | guarda el **ejecutivo**; el técnico va aparte |
| `/api/v1/pdf/trabajos/{job_id}` | `ARHIAX_Dictamen_{job_id}.pdf` | `DICTUS_EJECUTIVO_<folio>.pdf` |
| `/api/dictamenes/{case_id}/pdf` | el archivo almacenado (técnico) | el **ejecutivo**, o 409 pidiendo regenerar |
| `/api/dictamenes/{case_id}/update` | `ARHIAX_Dictamen_..._final.pdf` | `DICTUS_EJECUTIVO_<folio>.pdf` |

El Ejecutivo existía en disco **solo** por el script de laboratorio
(`scripts/dictus_run.py`): el producto nunca lo generaba. Por eso «el PDF entregado
para revisión» seguía siendo el de 17 páginas.

## 2 · Arquitectura aprobada del entregable (§4)

| Página | Título exacto |
|---|---|
| 1 | RESUMEN DE DECISIÓN DEL INMUEBLE |
| 2 | TÍTULOS Y CONDICIONES JURÍDICAS |
| 3 | CONTRAPARTES Y PREPARACIÓN DE OPERACIÓN |
| 4 | POT, USO, EDIFICABILIDAD Y RIESGOS |
| 5 | ENTORNO, EQUIPAMIENTO Y ASOLEAMIENTO |
| 6 | IDENTIDAD Y VALOR |

La página 1 lleva los cuatro bloques: **INFORMACIÓN GENERAL** (Dirección, Matrícula,
Ciudad, Barrio, Área, Uso, Régimen, Valor estimado), **ESTADO GENERAL** (cinco
indicadores), **HALLAZGOS** (todos, con SEVERIDAD · HALLAZGO · AFECTA A · ACCIÓN) y
**SELLO GLOBAL** (DICTUS ID, Fecha, Evidencias, Estado y hash maestro abreviado).

## 3 · Aserciones duras (`api/dictus_entrega.py`)

Sobre el **PDF ya escrito** (se lee con `pypdf`, la misma librería con que lo lee un
revisor), y antes de entregar nada:

* `page_count <= 6` (§3);
* orden exacto de los seis títulos aprobados (§4);
* **ningún** encabezado legacy (`00 - Naturaleza` … `17 - Sello de Integridad`) (§5);
* ausencia de fugas técnicas (`ARHIAX_EVIDENCE_HMAC_KEY`, `RuntimeError`, trazas) (§8);
* contenido mínimo por página (§14): página 3 acredita ONU · OFAC SDN · UK Sanctions
  List por su nombre, página 5 las cuatro tarjetas (Salud · Educación · Comercio ·
  Recreación) y el asoleamiento, página 6 el valor estimado y su método;
* **retícula sin desbordes**: el renderer declara cualquier bloque que no quepa y la
  entrega se rechaza.

Si algo falla se levanta `EntregaEjecutivaInvalida`: no se entrega un documento que no
es el aprobado. En la API eso se traduce en `HTTP 500` con el motivo, **nunca** en la
devolución del técnico como si fuera el principal.

## 4 · Artefacto de esta corrida

| Dato | Valor |
|---|---|
| **Documento principal** | `DICTUS_EJECUTIVO_040-646406.pdf` · **6 páginas** |
| sha256 del Ejecutivo | `59b1b9c07aa569b82d9b3630192fa2501c19347f51adad38f948b02c227743d1` |
| Anexo técnico | `DICTUS_TECNICO_040-646406.pdf` · 17 páginas · sha256 `54b9b62375da0b72c09f44f41334fc5373ccc45f84217947d1d9be894e6f99c4` |
| **DICTUS_MASTER_HASH** | `1b8484a8a675879d9c458b386b85de346bb5d699e9760f272f50d6b240585417` |
| DICTUS ID | `DX-040-646406-20260925` |
| run_id | `57d12113-d466-49b5-be5f-0a4c6a4b9a42` |
| Evidencias | 10 (`PARCIAL_CON_DECLARACIONES`) |
| Hallazgos en la página 1 | 9 |
| Verificación del hash maestro | **MATCH** |
| Retícula | 0 desbordes · 0 cajas de texto solapadas |

Los PDFs no se versionan (política del repositorio). Se reproducen y se verifican con:

```
python scripts/dictus_run.py                 # una corrida → ejecutivo + anexo + manifest
python scripts/dictus_render_ejecutivo.py    # contrato + render de las 6 páginas
python -m pytest tests/test_dictus_20b_r1_entrega_ejecutiva.py -q
```

## 5 · Lo que NO se tocó

Identidad canónica, valoración, POT, screening/sanciones, HMAC, contexto de mercado,
binding predio ↔ identidad y arquitectura de hash **no** cambiaron. La única
instrumentación añadida al compilador es de **solo lectura**: la clasificación ya
calculada (régimen jurídico, uso y tipología) se expone al estado de la corrida para
que el Ejecutivo no tenga que inferirla por su cuenta (dos metodologías sobre el mismo
dato). Los conflictos históricos de POT (8 vs 11 pisos, tratamiento, uso) siguen
**abiertos** y se imprimen como `CONFLICTO HISTÓRICO · REQUIERE VALIDACIÓN`, sin
elegir una de las dos cifras: corregirlos es materia de 2.0C, no de esta ronda.

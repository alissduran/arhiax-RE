# ARHIAX RE — Security Findings (Security Baseline)

Este documento registra los hallazgos del inventario de seguridad previo al freeze
arquitectónico. No contiene valores de secretos. Los valores expuestos se redactaron
como `[REDACTED]`.

Fecha: baseline de seguridad (2026).

---

## FINDING-001

Classification:
SECURITY

Observation:
`api/index.py` definía `AUTH_SECRET` con un fallback conocido hardcodeado
(`os.environ.get("ARHIAX_AUTH_SECRET", <valor conocido>)`). Una instalación de
producción sin la variable de entorno arrancaba y firmaba tokens HMAC con esa
clave pública derivable del código.

Evidence:
`api/index.py` (definición de `AUTH_SECRET` en el bloque de autenticación).

Root cause:
Fallback de desarrollo copiado a producción sin distinción de entorno.

Impact:
Cualquiera con acceso al código podía firmar/forjar tokens de sesión válidos
(bypass de autenticación) si la variable de entorno no estaba definida.

Fix:
Detectar entorno (producción = `VERCEL` o `ARHIAX_ENV=production`). En producción
`ARHIAX_AUTH_SECRET` es obligatorio y la app lanza `RuntimeError` explícito si falta
(fail-closed). En desarrollo/test se usa un valor SINTÉTICO inequívoco
(`dev-only-not-a-real-secret`).

Verification:
compileall + suite offline; import de `index` en desarrollo no falla; en producción
sin `ARHIAX_AUTH_SECRET` la app no arranca.

Status:
FIXED

---

## FINDING-002

Classification:
SECURITY

Observation:
`api/index.py` definía `ACCESS_PASSWORD` (contraseña global / admin retrocompatible)
con un fallback conocido hardcodeado (`os.environ.get("ARHIAX_ACCESS_PASSWORD", <valor conocido>)`).
El usuario admin caía a esa contraseña cuando faltaba `ARHIAX_ADMIN_PASSWORD`.

Evidence:
`api/index.py` (definición de `ACCESS_PASSWORD` y construcción de `_USUARIOS`).

Root cause:
Mismo patrón de fallback de desarrollo sin gate de entorno.

Impact:
Acceso administrativo con credenciales conocidas si las variables de entorno no
estaban definidas.

Fix:
En producción `ARHIAX_ADMIN_PASSWORD` (o `ARHIAX_ACCESS_PASSWORD`) es obligatorio y
la app falla explícitamente si falta. En desarrollo/test se usa un valor SINTÉTICO
(`dev-only-not-a-real-password`).

Verification:
compileall + suite offline; tests de login usan el valor sintético de desarrollo.

Status:
FIXED

---

## FINDING-003

Classification:
SECURITY

Observation:
`README_PLAN.md` exponía credenciales reales de producción (usuario admin y operador)
en texto plano dentro de una tabla "Credenciales de acceso al portal".

Evidence:
`README_PLAN.md` (sección de credenciales de acceso).

Root cause:
Documentación de despliegue que incluyó valores reales en el repositorio.

Impact:
Cualquier lector del repositorio obtenía credenciales de producción.

Fix:
Redactado el bloque; ahora referencia únicamente los NOMBRES de variables de entorno
(`ARHIAX_ADMIN_USER`, `ARHIAX_ADMIN_PASSWORD`, etc.) y aclara que nunca se versionan.

Verification:
Búsqueda de los valores en el árbol actual: sin coincidencias.

Status:
FIXED (los valores quedan en el historial de git — ver EXTERNAL ACTIONS)

---

## FINDING-004

Classification:
SECURITY

Observation:
`docs/auditorias/2026-09-01_codigo.md` y `docs/auditorias/2026-09-01_seguridad.md`
exponían la contraseña histórica y el token estático histórico en texto plano.

Evidence:
`docs/auditorias/*.md` (referencias a los valores).

Root cause:
Informes de auditoría históricos que citaban los valores literalmente.

Impact:
Exposición de credenciales históricas en el árbol.

Fix:
Valores redactados a `[REDACTED]`; el resto del análisis de auditoría se conserva.

Verification:
Búsqueda de los valores en el árbol actual: sin coincidencias.

Status:
FIXED

---

## FINDING-005

Classification:
SECURITY (TECH_DEBT — resuelto en SLICE-001)

Observation:
`api/arhia_sag_screen/evidence/envelope.py` resolvía la clave HMAC de evidencia con un
UUID aleatorio por proceso si la variable no estaba definida.

Evidence:
`api/arhia_sag_screen/evidence/envelope.py` (función `_key()`).

Root cause:
Clave no determinista por diseño de demo.

Impact:
Los sobres de evidencia HMAC no eran verificables entre instancias/despliegues.

Fix:
SLICE-001: `ARHIAX_EVIDENCE_HMAC_KEY` (independiente del secreto de auth) obligatoria en
producción (fail-closed); en dev/test clave sintética estable. Se retiró `uuid4()` por proceso.

Verification:
`tests/test_slice001_case.py` (TestEvidenceHmac: estable, desde env, fail-closed prod).

Status:
RESOLVED

---

## FINDING-006

Classification:
INFO

Observation:
`api/notificaciones.py` usa un remitente por defecto de Resend cuando no hay
`RESEND_FROM`.

Evidence:
`api/notificaciones.py` (remitente por defecto).

Root cause:
Valor por defecto del servicio (no es una credencial).

Impact:
Ninguno de confidencialidad (es una dirección de remitente de onboarding).

Fix:
N/A.

Verification:
N/A.

Status:
OPEN (informativo)

---

## FINDING-007

Classification:
TECH_DEBT

Observation:
El frontend trata `localStorage` (`arhiax_cases`) como fuente de verdad de la lista de
casos, mientras el backend persiste en Neon/Postgres.

Evidence:
`public/index.html` (inicialización de `dictamenes` desde `localStorage`; comentario
explícito "la fuente de verdad del portal es localStorage; el servidor es un espejo opcional").

Hypothesis:
Divergencia de estado entre cliente y servidor (casos creados en el servidor que no
aparecen si `localStorage` está desincronizado, y viceversa).

Impact:
Dos fuentes de verdad para el mismo agregado; riesgo de pérdida/duplicación de casos.

Recommended treatment:
SLICE-001: mover la fuente de verdad al servidor; `localStorage` pasa a cache/sesión.

Status:
RESOLVED (SLICE-001: `cargarDictamenes` obtiene la lista de `GET /api/dictamenes`;
`localStorage` ya no guarda `arhiax_cases`; la sesión sigue en `localStorage`.)

---

## FINDING-008

Classification:
TECH_DEBT

Observation:
El esquema se crea/migra en CADA conexión (`CREATE TABLE IF NOT EXISTS` +
`ALTER TABLE ADD COLUMN` idempotente) y el DDL está duplicado entre SQLite y Postgres.

Evidence:
`api/database.py:init_db()` y `api/postgres_adapter.py:init_postgres()`.

Hypothesis:
Sin versionado de esquema, cualquier cambio futuro es frágil y propenso a drift entre dialectos.

Impact:
Overhead por conexión; dos fuentes de DDL; sin trazabilidad de migraciones.

Recommended treatment:
ADR-003: migraciones versionadas (`schema_migrations` + scripts ordenados), aplicadas una vez por despliegue.

Status:
RESOLVED (SLICE-001: `api/migrations.py` con `schema_migrations`, secuencia `001_initial`
+ `002_case_canonical_state`, runner idempotente cacheado por DSN.)

---

## FINDING-009

Classification:
TECH_DEBT

Observation:
No existe ownership de caso: la tabla `dictamenes` no tiene `owner_id`/`created_by` y
`GET /api/dictamenes` devuelve todos los casos sin filtrar por usuario.

Evidence:
DDL de `dictamenes` (`database.py` / `postgres_adapter.py`); `list_dictamenes` en `api/index.py`.

Hypothesis:
Todos los usuarios autenticados comparten los mismos casos; no hay aislamiento.

Impact:
Fuga de datos entre usuarios/roles si hay más de un operador.

Recommended treatment:
ADR-002: mínimo `created_by` + filtrado por rol; multi-tenancy queda como decisión de producto.

Status:
NEEDS_DECISION

---

## FINDING-010

Classification:
TECH_DEBT

Observation:
Los hallazgos conviven en dos representaciones: tuplas heterogéneas de 6/7 elementos
(pipeline del dictamen) y el dataclass `Hallazgo` (Titulux).

Evidence:
`api/legal_analyzer.py` / `api/pdf_compiler.py` (tuplas) vs `api/arhia_title/contracts.py` (dataclass).

Hypothesis:
La forma de tupla es frágil (índices posicionales) y dificulta el contrato único de hallazgo.

Impact:
Acoplamiento implícito; riesgo de "too many values to unpack" (ya ocurrió).

Recommended treatment:
SLICE-003: tipar hallazgos hacia `Hallazgo` (o un contrato único), conservando la tupla como adaptador temporal.

Status:
OPEN

---

## FINDING-011

Classification:
TECH_DEBT

Observation:
`api/pdf_compiler.py` concentra dominio + orquestación + infraestructura + presentación
(~3100 líneas, ~20 imports, side effects de red/PDF/email).

Evidence:
`api/pdf_compiler.py` (función `compile_pdf`).

Hypothesis:
Es el punto de mayor acoplamiento; dificulta testear y evolucionar el dictamen.

Impact:
Riesgo de regresión al tocar cualquier capacidad del dictamen.

Recommended treatment:
Strangler por slices (SLICE-002..005): extraer identidad, hallazgos/gate, receipts y render
sin reescribir el orquestador.

Status:
OPEN

---

## FINDING-012

Classification:
DOC_DEBT

Observation:
`README_PLAN.md` lista variables de entorno con "✅ CONFIGURADA" sin distinguir de forma
explícita obligatorias de opcionales en producción (parcialmente aclarado en el Security Baseline).

Evidence:
`README_PLAN.md` (tabla de variables).

Hypothesis:
Ambigüedad de configuración para un nuevo despliegue.

Impact:
Configuración incorrecta (p. ej. omitir un secreto obligatorio) en producción.

Recommended treatment:
Documentar matriz obligatorio/opcional por entorno (completar en docs).

Status:
OPEN

---

## FINDING-013

Classification:
TECH_DEBT

Observation:
`api/notificaciones.py` tiene una dirección de correo personal hardcodeada como
destinatario por defecto (`_DESTINATARIO_DEFAULT`).

Evidence:
`api/notificaciones.py` (constante `_DESTINATARIO_DEFAULT`).

Hypothesis:
PII en código; el destinatario real debería venir de configuración.

Impact:
Correos dirigidos a una persona fija; PII versionada.

Recommended treatment:
Mover a variable de entorno (`ARHIAX_NOTIFY_EMAIL`) sin fallback personal.

Status:
OPEN

---

## FINDING-014

Classification:
TECH_DEBT

Observation:
`public/index.html` conserva `sincronizarCasosConServidor()` con `return;` anticipado
(código muerto tras SLICE-001), y la función aún referencia `localStorage["arhiax_cases"]`
en su cuerpo no ejecutado.

Evidence:
`public/index.html` (función `sincronizarCasosConServidor`).

Hypothesis:
Resto del antiguo flujo offline-first; no se ejecuta (early-return), pero confunde.

Impact:
Mantenibilidad (código muerto); sin impacto funcional.

Recommended treatment:
Eliminar la función en un cleanup posterior (no en SLICE-001 para no tocar más superficie).

Status:
OPEN

---

## FINDING-015

Classification:
TECH_DEBT

Observation:
`api/listas_cache.py` crea su tabla (`listas_cache`) con `CREATE TABLE IF NOT EXISTS` en
cada `_conn()`; no está versionada en `migrations.py`.

Evidence:
`api/listas_cache.py:_crear_tabla`.

Hypothesis:
Mismo patrón pre-SLICE-001 (DDL por conexión) aún presente en la caché de listas.

Impact:
Overhead por conexión; fuera del alcance de SLICE-001 (Case persistence).

Recommended treatment:
Mover `listas_cache` a una migración versionada en un slice posterior.

Status:
OPEN (deferred)

---

## FINDING-016

Classification:
IDENTITY_REGRESSION

Observation:
`api/legal_analyzer.py` descarta la unidad/edificio de la dirección del CTL
(`re.split` sobre `APARTAMENTO|APTO|AP|EDIFICIO|TORRE|...`), de modo que
`"TV 43 # 100-50 TO 8 AP 430"` se convierte en `"TV 43 # 100-50"`.

Evidence:
`api/legal_analyzer.py:289-299`; commit `f247a20` "Direccion oficial: preferir la
DIRECCION CATASTRAL del CTL (Bogota real)". Caso 040-646406 (ver docs/forensics/040-646406/).

Hypothesis:
La pérdida de la unidad degrada la resolución catastral (5 features) y, aguas abajo,
el barrio/destino/estrato, lo que reduce el precio/m² de 6.8M a 5.2M.

Impact:
Identidad de unidad PH no preservada; valoración referencial cae ~24% por cambio de
contexto (no por algoritmo).

Recommended treatment:
Reconstruir la unidad (torre/apartamento) como parte de la identidad canónica del
inmueble sin descartarla en la extracción; definir fuente autoritativa por atributo.

Status:
OPEN (root cause parcialmente confirmada; requiere CTL real + traza catastral)

---

## FINDING-017

Classification:
REPORTING_ONLY_BUG

Observation:
El dictus anterior mostraba "Ponderación M1 70% / M3 30%", pero el consolidado en
código siempre fue `área × precio/m²` (M1 100%). El cambio a "M1 100% / M3 excepcional"
es una corrección de la ETIQUETA, no de la fórmula.

Evidence:
`git show 0a078c0^:api/dictamen_data.py` (consolidado = `int(area × val_m2)`, sin
70/30) y `git show e58eefd` (fórmula `m3 if metodo=="m3" else m1_base`, solo cambia
el comentario). Ver docs/forensics/040-646406/VALUATION_DIFF.md.

Hypothesis:
La etiqueta 70/30 nunca correspondió a la fórmula real; era texto de presentación.

Impact:
Confusión al comparar dictus; sin impacto en el valor calculado.

Recommended treatment:
Unificar la etiqueta de ponderación con la fórmula real y documentarlo.

Status:
OPEN

---

## FINDING-018

Classification:
CATASTRO_RESOLUTION_REGRESSION

Observation:
`api/catastro_predio.py` selecciona la feature catastral con `features[0]` (la primera,
sin scoring de coincidencia) y limita la consulta con `resultRecordCount=5`.

Evidence:
`api/catastro_predio.py` líneas 105-143 (`_query_capa`/`_query_punto`, `max_features=5`),
217, 323, 353, 359, 368, 374, 403, 413, 423 (`features[0]`).

Hypothesis:
Cuando el lookup exacto por código/NUPRE falla, el fallback espacial devuelve hasta 5
features (edificio + vecinos) y `features[0]` elige una arbitraria → barrio/destino/
estrato degradados → precio/m² cae.

Impact:
Identidad catastral no determinista; valoración dependiente del orden de features.

Recommended treatment:
Añadir criterio de identidad (código/NUPRE/dirección) y scoring antes de elegir feature.
(No arreglar en fase forense.)

Status:
OPEN

---

## FINDING-019

Classification:
TECH_DEBT

Observation:
`canonical_property_identity` no distingue estructuralmente edificio / predio matriz /
unidad PH: no tiene campos `torre` / `apartamento` / `unidad`; la unidad vive solo en
`nomenclatura` (string), que `legal_analyzer` descarta.

Evidence:
`api/canonical.py`; `api/legal_analyzer.py:289-299`.

Hypothesis:
Sin campos estructurados de unidad, el sistema no puede representar
`SAME_BUILDING_DIFFERENT_UNIT` y degrada la identidad al perder el complemento de dirección.

Impact:
Riesgo de valorar la torre/edificio en vez de la unidad; identidad de unidad inestable.

Recommended treatment:
Evaluar añadir `torre`/`apartamento`/`unidad`/`coeficiente` a la identidad canónica.

Status:
OPEN

---

## EXTERNAL ACTIONS REQUIRED (rotación y configuración)

Estas acciones NO pueden ejecutarse desde el código y requieren intervención humana.

1. **Rotar `ARHIAX_AUTH_SECRET`** — `ROTATE_NOW`. El valor de fallback conocido
   quedó en el historial de git.
2. **Rotar `ARHIAX_ADMIN_PASSWORD` (y `ARHIAX_ACCESS_PASSWORD`)** — `ROTATE_NOW`.
   Expuestos en `README_PLAN.md` y en el historial.
3. **Rotar `ARHIAX_OPERADOR_PASSWORD`** — `ROTATE_NOW`. Expuesto en `README_PLAN.md`.
4. **Verificar y rotar `QSTASH_TOKEN`** — `ROTATE_IF_EXPOSED`. No se halló expuesto en
   el árbol; confirmar en el historial y en el panel de Upstash.
5. **Verificar y rotar `QSTASH_CURRENT_SIGNING_KEY` / `QSTASH_NEXT_SIGNING_KEY`** —
   `ROTATE_IF_EXPOSED`. No se halló expuesto en el árbol.
6. **Verificar y rotar `RESEND_API_KEY`** — `ROTATE_IF_EXPOSED`. No se halló expuesto.
7. **Verificar y rotar `ARHIAX_DB_PATH` (DSN de Neon)** — `ROTATE_IF_EXPOSED`. No se
   halló expuesto; si el DSN estuvo en el historial, rotar la contraseña de Neon.
8. **`ARHIA_HMAC_KEY`** — `NO_ROTATION_REQUIRED` (aleatoria por proceso; definir una
   estable en producción si se requiere evidencia verificable entre instancias).

### Limpieza del historial de git (requiere autorización explícita)

Los secretos redactados del árbol SÍ permanecen en commits anteriores. La limpieza
controlada del historial (p. ej. `git filter-repo` / BFG + `--force`) NO se ejecutó
en esta sesión porque exige instrucción humana explícita y coordinación de rotación
primero. Orden recomendado: (1) rotar, (2) limpiar historial, (3) forzar push.

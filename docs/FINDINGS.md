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
SECURITY (TECH_DEBT — registrado, no resuelto en esta sesión)

Observation:
`api/arhia_sag_screen/evidence/envelope.py` resuelve la clave HMAC de evidencia
(`ARHIA_HMAC_KEY`) con un UUID aleatorio por proceso si la variable no está definida.

Evidence:
`api/arhia_sag_screen/evidence/envelope.py` (función `_key()`).

Root cause:
Clave no determinista por diseño de demo.

Impact:
Los sobres de evidencia HMAC no son verificables entre instancias/despliegues si no
se fija la clave. No es parte del blocker de autenticación (no es credencial de login).

Fix:
(No aplicado en esta sesión — fuera del alcance del blocker.) En producción definir
`ARHIA_HMAC_KEY` estable y gestionada fuera del código.

Verification:
N/A (registrado).

Status:
OPEN

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

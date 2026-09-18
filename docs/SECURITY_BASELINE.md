# ARHIAX RE — Security Baseline

> Estabilización de seguridad previa al freeze arquitectónico.
> No se reorganizó arquitectura, no se refactorizó negocio, no se cambió framework.
> Los secretos redactados se marcan como `[REDACTED]`; no se reproducen valores.

---

## 1. SECURITY INVENTORY

Inspeccionado (sin reproducir valores de secretos):

- **Autenticación / autorización** — `api/index.py` (login, `_firmar` / `_crear_token` / `_decodificar_token`, `require_auth` / `require_admin`, rate limiting, construcción de `_USUARIOS`).
- **Variables de entorno y fallbacks** — `api/index.py`, `api/database.py`, `api/cola_pdf.py`, `api/notificaciones.py`, `api/listas_cache.py`, `api/postgres_adapter.py`, `api/arhia_sag_screen/evidence/envelope.py`, `api/arhia_sag_screen/sirel.py`.
- **Documentación** — `README_PLAN.md`, `docs/auditorias/*.md`, resto de `docs/*.md`.
- **Configuración** — `vercel.json`, `.github/workflows/ci.yml`, `.gitignore`.
- **Tests de autenticación** — `tests/test_smoke_api.py`.
- **Patrones buscados** — `password`, `secret`, `token`, `key`, `bearer`, `auth`, `postgres://`, `postgresql://`, `qstash`, `api_key`, `access_password`, `signing_key`, `DSN`.

No existen archivos `.env` en el árbol.

---

## 2. FINDINGS

| ID | Classification | Component | Evidence | Status |
| -- | -------------- | --------- | -------- | ------ |
| FINDING-001 | SECURITY | `api/index.py` | `AUTH_SECRET` con fallback conocido hardcodeado | FIXED |
| FINDING-002 | SECURITY | `api/index.py` | `ACCESS_PASSWORD` con fallback conocido hardcodeado | FIXED |
| FINDING-003 | SECURITY | `README_PLAN.md` | Credenciales de producción en texto plano | FIXED |
| FINDING-004 | SECURITY | `docs/auditorias/*.md` | Contraseña/token históricos en texto plano | FIXED |
| FINDING-005 | SECURITY (TECH_DEBT) | `arhia_sag_screen/evidence/envelope.py` | Clave HMAC aleatoria por proceso (no determinista) | OPEN |
| FINDING-006 | INFO | `api/notificaciones.py` | Remitente Resend por defecto (no es secreto) | OPEN |

`SECRET_EXPOSED` → `api/index.py` (fallbacks), `README_PLAN.md`, `docs/auditorias/2026-09-01_codigo.md`, `docs/auditorias/2026-09-01_seguridad.md`.

Detalle de cada hallazgo en [`docs/FINDINGS.md`](FINDINGS.md).

---

## 3. CHANGES APPLIED

```text
api/index.py:
reason:  producción arrancaba con secretos fallback conocidos.
change:  detección de entorno (VERCEL / ARHIAX_ENV=production). En producción
         ARHIAX_AUTH_SECRET y ARHIAX_ADMIN_PASSWORD (o ARHIAX_ACCESS_PASSWORD)
         son OBLIGATORIOS -> RuntimeError explícito si faltan (fail-closed).
         En dev/test se usan valores SINTÉTICOS inequívocos.

tests/test_smoke_api.py:
reason:  los tests de login usaban la contraseña fallback conocida.
change:  ahora usan el secreto sintético de desarrollo.

README_PLAN.md:
reason:  exponía credenciales de producción en texto plano.
change:  bloque redactado; solo nombres de variables de entorno.

docs/auditorias/2026-09-01_codigo.md / 2026-09-01_seguridad.md:
reason:  exponían la contraseña/token históricos.
change:  valores redactados a [REDACTED] (se conserva el análisis).

docs/FINDINGS.md / docs/SECURITY_BASELINE.md:
reason:  entregable documental.
change:  inventario + clasificación + checklist de rotación.
```

---

## 4. EXTERNAL ACTIONS REQUIRED

1. `ARHIAX_AUTH_SECRET` → **ROTATE_NOW** (valor conocido en historial de git).
2. `ARHIAX_ADMIN_PASSWORD` / `ARHIAX_ACCESS_PASSWORD` → **ROTATE_NOW** (expuestos en README e historial).
3. `ARHIAX_OPERADOR_PASSWORD` → **ROTATE_NOW** (expuesto en README).
4. `QSTASH_TOKEN` → **ROTATE_IF_EXPOSED** (no hallado en árbol; verificar historial/Upstash).
5. `QSTASH_CURRENT_SIGNING_KEY` / `QSTASH_NEXT_SIGNING_KEY` → **ROTATE_IF_EXPOSED**.
6. `RESEND_API_KEY` → **ROTATE_IF_EXPOSED**.
7. `ARHIAX_DB_PATH` (DSN Neon) → **ROTATE_IF_EXPOSED** (rotar contraseña Neon si estuvo en historial).
8. `ARHIA_HMAC_KEY` → **NO_ROTATION_REQUIRED** (aleatoria por proceso; definir estable en prod si se requiere).

### Limpieza del historial de git

NO ejecutada (requiere instrucción humana explícita). Los secretos siguen en commits
anteriores. Orden recomendado: (1) rotar, (2) `git filter-repo`/BFG, (3) force-push.

### Verificación de despliegue

Al desplegarse el commit de baseline, producción exigirá `ARHIAX_AUTH_SECRET` y la
contraseña admin por variables de entorno. Confirmar que están definidas en Vercel
antes de que el deploy haga efectivo el fail-closed.

---

## 5. VERIFICATION

- `python -m compileall api tests` → **exit 0**.
- `pytest -m "not network" tests/` → **257 passed, 10 deselected**.
- `pip-audit -r requirements.txt` → **NO ejecutado localmente** (no instalado; el CI lo ejecuta en `.github/workflows/ci.yml`).
- Fail-closed verificado:
  - import en desarrollo: OK (`_IS_PROD=False`).
  - import con `VERCEL=1` sin `ARHIAX_AUTH_SECRET` → `RuntimeError: FALTA_CONFIGURACION_DE_SEGURIDAD: ARHIAX_AUTH_SECRET es obligatorio en producción`.
  - import con `VERCEL=1` + secretos presentes → pasa el bloque de auth.

---

## 6. REGRESSION CHECK

```
NO FUNCTIONAL DOMAIN BEHAVIOR CHANGED
```

No se modificó GIS, scoring, Titulux, valoración Lonja, reglas SARLAFT ni lógica
jurídica. Solo hardening de autenticación (mismo mecanismo HMAC), redacción de
documentación y actualización del secreto de test.

---

## 7. FINAL STATUS

```
SECURITY CODE BASELINE READY — EXTERNAL SECRET ROTATION REQUIRED
```

Gates S-01…S-07 satisfechos en código; S-08 (checklist) documentado. La rotación y
la limpieza del historial son acción humana externa. No se declara
`ARCHITECTURE BASELINE READY` (etapa del siguiente prompt).

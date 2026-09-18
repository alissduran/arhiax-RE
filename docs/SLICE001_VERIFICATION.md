# SLICE-001 — Acceptance & Verification Gate

> Verificación de aceptación de SLICE-001 (Canonical Case Persistence).
> Commit de referencia: `0cb331e`.
> Modo: VERIFY ONLY — sin cambios de código de producto.

---

## 1. ENVIRONMENT READINESS

| Variable | Estado |
| --- | --- |
| `ARHIAX_AUTH_SECRET` | UNKNOWN (sin acceso al entorno Vercel/Neon) |
| `ARHIAX_ADMIN_PASSWORD` | UNKNOWN |
| `ARHIAX_EVIDENCE_HMAC_KEY` | UNKNOWN |

`ROTATION_STATUS: UNKNOWN — HUMAN VERIFICATION REQUIRED`
(no se declara `ROTATED` sin evidencia administrativa; no se imprimen valores.)

---

## 2. LOCAL REGRESSION

```text
python -m compileall api tests      -> exit 0
pytest tests/test_slice001_case.py  -> 12 passed
pytest tests/test_smoke_api.py      -> verde
pytest -m "not network" tests/      -> 269 passed, 10 deselected
pip-audit                           -> NO ejecutado (no instalado localmente; el CI lo ejecuta)
```

Baseline confirmada: `269 passed, 10 deselected`. Sin regresión.

---

## 3. MIGRATION VERIFICATION (Gate B + C)

Sobre SQLite limpio:

- `schema_migrations` existe y registra `001_initial` + `002_case_canonical_state` **una sola vez**.
- Re-run del runner → `[]` (sin duplicados, sin pérdida de datos).
- Columnas `ciudad`, `created_by`, `updated_by` presentes; Case CRUD operativo tras migrar.

**Gate C — no Case DDL en conexión normal:**

| Escenario | Resultado |
| --- | --- |
| Mismo proceso, segunda conexión | READ ONLY (cache por DSN) — sin DDL de Case |
| Cold start sobre BD ya migrada | migración 001 omitida; solo `CREATE TABLE IF NOT EXISTS schema_migrations` (idempotente) |

`NORMAL CASE CONNECTION != SCHEMA MUTATION` — verificado por subproceso con marcador.

---

## 4. POSTGRES/NEON VERIFICATION

```text
POSTGRES_LIVE: NOT VERIFIED
```

Sin acceso seguro a Neon/staging. SQLite no es evidencia de Neon.

---

## 5. BROWSER E2E

```text
NOT VERIFIED
```

Sin infraestructura E2E (no se introduce Playwright/Cypress solo para esto).
Persistencia cross-session a nivel API verificada (Gate D).

E2E manual reproducible:
```text
login → crear caso → recargar → cerrar → reabrir → login → el caso viene de GET /api/dictamenes
```

---

## 6. LOCALSTORAGE AUTHORITY CHECK

`localStorage.setItem("arhiax_cases", ...)` → **0 escrituras autoritativas en código activo**.

Quedan 2 referencias dentro de `sincronizarCasosConServidor()`, que tiene `return;`
anticipado (dead code, no comportamiento activo). La lista canónica viene de
`GET /api/dictamenes`.

---

## 7. FAILURE PROPAGATION

```text
DB FAILURE → API ERROR → UI DOES NOT CLAIM SUCCESS
```

Verificado: `get_db_connection()` forzada a fallar → `create_case` lanza excepción.
Frontend create/delete muestran error y **no** crean/borran en memoria como fallback.

---

## 8. HMAC CROSS-PROCESS

| Prueba | Resultado |
| --- | --- |
| Proceso A firma con `K`; Proceso B verifica con `K` | VALID |
| Proceso B con clave distinta | INVALID |
| Cambiar `ARHIAX_AUTH_SECRET` sin tocar `ARHIAX_EVIDENCE_HMAC_KEY` | verificación sigue VALID |

Separación criptográfica entre autenticación e integridad de evidencia confirmada.

---

## 9. OPEN FINDINGS

- **FINDING-014** — `sincronizarCasosConServidor` (dead code en frontend) → OPEN (cleanup posterior).
- **FINDING-015** — `listas_cache` crea tabla por conexión → **OUTSIDE_SLICE_DEFER** (cache SAGRILAFT, no dominio Case; no bloquea SLICE-001).
- Observación (no bloqueante): `upload_image` escribe campos del Case por SQL directo al extraer el CTL → **DEFER** a SLICE-002/005.

---

## 10. ACCEPTANCE MATRIX

| Requirement | Evidence | Environment | Result |
| --- | --- | --- | --- |
| Create | `test_t1` | SQLite | PASS |
| Persist | `test_t1`, `test_t7` | SQLite | PASS |
| Reload | `test_t5` (cross-connection) | SQLite | PASS |
| Re-login | browser | Browser | NOT VERIFIED |
| No local canonical state | grep `arhiax_cases` (0 activos) | code | PASS |
| Neon canonical | — | Postgres | NOT VERIFIED |
| Migration zero→head | `test_t8` + Gate B | SQLite | PASS |
| Migration idempotency | `test_t9` + Gate B | SQLite | PASS |
| No normal Case DDL | Gate C | runtime | PASS |
| Auth | `test_t6` + suite | API | PASS |
| HMAC cross-process | Gate HMAC (subprocesos) | processes | PASS |

---

## 11. CODE CHANGES DURING VERIFICATION

```text
NO CODE CHANGES
```

(Solo un script QA temporal, no versionado, eliminado al final.)

---

## 12. FINAL STATUS

```text
SLICE-001 — IMPLEMENTED / NOT VERIFIED
```

No se declara `CLOSED / ACCEPTED` porque dos criterios del acceptance rule dependen de
acceso externo: **Postgres/Neon en vivo** y **browser E2E real**. Todo lo verificable desde
aquí está en **PASS** con evidencia ejecutada (migraciones, CRUD persistente cross-process,
HMAC cross-process, fallo de persistencia, localStorage no autoritativo, auth, regresión).

Detenido. No se inició SLICE-002. No se cambió arquitectura ni producto.

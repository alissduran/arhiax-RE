# SLICE-001 — Canonical Case Persistence (Implementación)

> Commit: `0cb331e` · `ARCHITECTURE BASELINE READY` → primer vertical slice.
> Estado final: `SLICE-001 — IMPLEMENTED / NOT VERIFIED`.

---

## 1. PRE-SLICE OBSERVATION

El flujo de Case (create/list/get/update/delete) vivía mezclado:

- `api/index.py` hacía SQL inline (`get_db_connection()` + INSERT/SELECT/UPDATE/DELETE).
- `public/index.html` usaba `localStorage["arhiax_cases"]` como **fuente de verdad**
  (comentario literal: "la fuente de verdad del portal es localStorage; el servidor
  es un espejo opcional").
- El esquema se creaba/migraba con `CREATE TABLE IF NOT EXISTS` + `ALTER TABLE`
  **en cada conexión**, con DDL duplicado entre SQLite y Postgres.

---

## 2. IMPLEMENTATION

| Layer | Previous | New | Files |
| ----- | -------- | --- | ----- |
| CONTRACT | dicts/tuplas sueltos | contrato Case en service/repository | `case_service.py`, `case_repository.py` |
| DOMAIN | — | `create/get/list/update/delete` | `case_service.py` |
| PERSISTENCE | SQL inline en endpoints | `CaseRepository` | `case_repository.py` |
| PERSISTENCE (schema) | DDL por conexión | migraciones versionadas | `migrations.py`, `database.py` |
| APPLICATION | lógica en endpoints | `CaseService` | `case_service.py` |
| HTTP/API | endpoints con SQL | endpoints delegan (compatibles) | `index.py` |
| FRONTEND | localStorage canónico | GET `/api/dictamenes` canónico | `public/index.html` |
| EVIDENCE HMAC | uuid4 por proceso | `ARHIAX_EVIDENCE_HMAC_KEY` | `envelope.py` |
| TESTS | — | T1–T9 + HMAC | `test_slice001_case.py` |

---

## 3. CANONICAL CASE CONTRACT

- **REQUIRED:** `id`, `folio_matricula`, `direccion`, `barrio`, `estrato`, `estado`.
- **OPTIONAL:** `area`, `valor_consolidado`, `ciudad`, `acreedor_real`, `lat`, `lon`, `fuente_geocod`.
- **DERIVED:** `fecha_creacion`.
- **LEGACY (insumo/generación, NO canónico del Case):** `sombra_9am_cargada`,
  `sombra_3pm_cargada`, `mapa_cargado`, `certificado_cargado`, `certificado_path`, `pdf_path`.
- **AUDIT (metadata, NO ownership):** `created_by`, `updated_by`.

**Identidad:** un único `case_id` (int/SERIAL). Distinto de: `job_id` (trabajo PDF),
`documento` (adjunto), `folio` (matrícula SNR).

---

## 4. PERSISTENCE

- **Canonical DB:** Postgres/Neon (o SQLite local en dev/test). `get_db_connection()` ya
  no ejecuta DDL por conexión: delega en `migrations.ensure_migrated()` (cacheada por DSN).
- **Migraciones:** `schema_migrations(id, applied_at)` + secuencia `001_initial`
  (reusa el DDL existente) y `002_case_canonical_state` (`created_by`/`updated_by`).
  Runner ordenado, idempotente, fallo detiene.
- **Repository boundary:** `CaseRepository` encapsula insert/get/list/update/delete +
  `_row_to_case` (no expone `pdf_path`/`certificado_path`).
- **Transacciones:** commit por operación (mismo patrón previo); sin transacciones complejas nuevas.

---

## 5. FRONTEND STATE

`localStorage` **dejó** de ser fuente autoritativa de casos:

- `cargarDictamenes()` ahora hace `GET /api/dictamenes`.
- create/update/delete escriben en el servidor y actualizan la UI desde la respuesta
  (sin `localStorage.setItem("arhiax_cases")`).
- `sincronizarCasosConServidor()` quedó retirada (early-return).

Sigue en `localStorage`: sesión (`arhiax_token/username/rol`). IndexedDB se mantiene
como cache binaria local (insumos).

**DB failure → API failure → UI error:** create y delete muestran error y **no**
aparentan éxito con fallback local.

---

## 6. HMAC INTEGRITY

`envelope._key()` usa `ARHIAX_EVIDENCE_HMAC_KEY` (independiente del secreto de
autenticación, NO derivada de `ARHIAX_AUTH_SECRET`). En producción
(`VERCEL`/`ARHIAX_ENV=production`) falla cerrada si falta; en dev/test usa clave
sintética estable. Se retiró la generación `uuid4()` por proceso. (Sin mostrar valores.)

---

## 7. TESTS ADDED

| Test | Demuestra |
| --- | --- |
| T1 create_persist_id | crear → persistido + id |
| T2 read_equivalent | crear → leer → datos equivalentes |
| T3 update_persist | crear → update → leer → valor persistido |
| T4 list | crear N → listar → N consistentes |
| T5 reload_nueva_conexion | nueva instancia de repo lee la misma BD |
| T6 auth_sigue_en_http | endpoints conservan `Depends(require_auth)` |
| T7 reconstruccion_crud | conexión cruda re-lee el Case |
| T8 empty_to_current | BD vacía → migraciones → schema actual |
| T9 idempotency | re-run de migraciones → sin duplicados |
| HMAC estable / desde env / fail-closed prod | clave estable, del entorno, falla cerrada |

---

## 8. REGRESSION

```text
compileall          -> exit 0
focused slice tests -> 12 passed (test_slice001_case.py) + smoke api verde
full offline pytest -> 269 passed, 10 deselected
pip-audit           -> NO ejecutado (no instalado localmente; el CI lo ejecuta)
```

---

## 9. FINDINGS

- Nuevos: `FINDING-014` (código muerto `sincronizarCasosConServidor` en frontend),
  `FINDING-015` (`listas_cache` aún crea tabla por conexión).
- Resueltos: `FINDING-005` (HMAC), `FINDING-007` (localStorage), `FINDING-008` (migraciones).
- Todo en `docs/FINDINGS.md`.

---

## 10. FILES CHANGED

- Nuevos: `api/case_service.py`, `api/case_repository.py`, `api/migrations.py`, `tests/test_slice001_case.py`.
- Modificados: `api/database.py`, `api/index.py`, `api/arhia_sag_screen/evidence/envelope.py`,
  `public/index.html`, `tests/test_smoke_api.py`, y docs (`SLICES.md`, `DECISIONS.md`,
  `CONTRACTS.md`, `FINDINGS.md`).

---

## 11. DEFINITION OF DONE

| Criterio | Estado |
| --- | --- |
| Case can be created | PASS |
| Case is persisted | PASS |
| Case can be read | PASS |
| Case can be updated | PASS |
| Case can be listed | PASS |
| Existing delete semantics remain functional | PASS |
| Browser reload does not lose canonical state | NOT VERIFIED (sin E2E; T5 cubre el nivel API) |
| Postgres/Neon is authoritative | PASS (código) / NOT VERIFIED (Neon live no en suite offline) |
| localStorage is not authoritative for Case | PASS |
| DB failure cannot become fake UI success | PASS |
| Auth remains enforced | PASS |
| migrations are versioned | PASS |
| schema migration not executed on every normal connection | PASS |
| migrations work from empty schema | PASS |
| migrations are idempotent | PASS |
| evidence HMAC is stable across processes | PASS |
| HMAC key is independent from auth secret | PASS |
| focused tests are green | PASS |
| complete offline regression suite is green | PASS |
| no unrelated domain behavior changed | PASS |

---

## 12. FINAL STATUS

```text
SLICE-001 — IMPLEMENTED / NOT VERIFIED
```

Pendiente de verificación externa (no automatizable aquí): **recarga real en navegador**
(E2E manual) y **Neon/Postgres en vivo** (la suite offline usa SQLite). El comportamiento
"borrar estado del navegador → login → fetch desde API → el Case sigue" ya está codificado
y probado a nivel de API.

Detenido. No se inició SLICE-002 ni refactor adicional.

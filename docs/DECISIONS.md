# ARHIAX RE — Architectural Decisions (ADR)

Propuestas de decisión. Ninguna está implementada todavía.

---

## ADR-001 — Source of Truth

**Problema:** el estado de un "caso" puede existir en Postgres/Neon, `localStorage`,
`IndexedDB` y memoria del proceso.

**Evidencia (comportamiento implementado):**
- `public/index.html:670-671` — `let dictamenes = JSON.parse(localStorage.getItem("arhiax_cases") || "[]")`. La lista de casos vive en `localStorage`.
- `public/index.html:1426-1427` — comentario explícito: "la fuente de verdad del portal es localStorage; el servidor es un espejo opcional".
- `public/index.html:685` — `indexedDB.open('arhiax_insumos', 1)` para binarios subidos (PNG/certificado) por caso.
- `api/index.py` CRUD `/api/dictamenes` — persiste en `database.get_db_connection()` (SQLite local o Neon/Postgres).
- `localStorage` guarda también `arhiax_token`, `arhiax_username`, `arhiax_rol` (sesión).

**Dónde está cada cosa (verificado):**
- Postgres/Neon: casos (tabla `dictamenes`), documentos (`documentos_caso`), trabajos PDF (`trabajos_pdf`), caché de listas (`listas_cache`).
- `localStorage`: sesión (token/username/rol) + **lista de casos** (`arhiax_cases`).
- `IndexedDB`: binarios subidos por caso (`arhiax_insumos`).
- Memoria del proceso: `_USUARIOS` (credenciales), cachés en módulos (`_POI_CACHE`, `_CACHE` de `pasto_territorio`).

**Decisión (confirmada por evidencia):**
```text
Postgres/Neon = canonical persistent state (fuente de verdad del Case)
localStorage   = session / preferences / optimistic cache ONLY (NO lista de casos canónica)
IndexedDB      = ephemeral/local binary cache where justified (insumos no persistidos aún)
memoria        = caches volátiles (sin autoridad)
```

**Implicación:** SLICE-001 debe mover la lista de casos de `localStorage` al servidor
(el servidor ya persiste; falta que el frontend lo trate como canónico y sincronice).

**Status:** DECIDED (pendiente de implementar en SLICE-001).

---

## ADR-002 — Case Ownership

**Problema:** ¿quién es dueño de un Case y quién lo ve?

**Evidencia (comportamiento actual):**
- Tabla `dictamenes` (`database.py` / `postgres_adapter.py`): NO tiene `owner_id`, `created_by`, `tenant_id`, `organization_id` ni `workspace_id`.
- `GET /api/dictamenes` (`index.py`): devuelve todos los casos sin filtrar por usuario.
- `_USUARIOS` solo tiene `username`/`rol` (`admin`/`operador`); no hay FK user↔case.
- Auth: `require_auth` (cualquier token válido) y `require_admin` (solo admin). No hay autorización por recurso.

**Conclusión:** hoy todos los usuarios autenticados comparten los MISMOS casos.
No existe multi-tenancy ni aislamiento por usuario.

**Documentación:**
```text
CURRENT SEMANTICS:        todos los usuarios autenticados comparten todos los casos (sin aislamiento).
TARGET MINIMUM SEMANTICS: caso asociado a un creador (created_by); visibilidad por rol (admin ve todo; operador ve los suyos).
UNRESOLVED PRODUCT DECISION: ¿multi-tenancy (organización/workspace) o single-tenant por usuario?
```

**Status:** NEEDS_PRODUCT_DECISION (no hay evidencia suficiente para elegir multi-tenancy; el mínimo técnico es `created_by` + filtrado por rol).

---

## ADR-003 — Database Migrations

**Problema:** ¿cómo se crea y evoluciona el esquema?

**Evidencia (comportamiento actual):**
- `database.py:init_db()` — `CREATE TABLE IF NOT EXISTS` + `ALTER TABLE ADD COLUMN` (idempotente) sobre SQLite; se ejecuta en CADA `get_db_connection()` (por conexión).
- `postgres_adapter.py:init_postgres()` — mismo patrón con `ADD COLUMN IF NOT EXISTS` sobre Postgres; se ejecuta en cada conexión.
- DDL duplicado manualmente entre SQLite y Postgres (dos fuentes de esquema).
- NO hay tabla de versionado de esquema, ni migraciones numeradas.
- SQLite y Postgres deben mantenerse equivalentes (la app corre sobre ambos).

**Propuesta (mínima, sin ORM):**
```text
- Tabla schema_migrations(version PK, applied_at).
- Directorio de migraciones versionadas (0001_..., 0002_...), aplicadas en orden
  una sola vez por despliegue/arranque (no en cada conexión).
- Un solo DDL canónico por migración que se adapte a SQLite/Postgres (o dos
  dialectos por migración), eliminando el ALTER idempotente en caliente.
- Prueba de arranque: schema vacío → aplicar migraciones → schema actual.
```

**Status:** DECIDED (estrategia); implementación en un slice de persistence (no en este prompt).

---

## ADR-004 — Evidence Integrity Key

**Problema:** la clave HMAC de evidencia se genera aleatoriamente por proceso.

**Evidencia (comportamiento actual):**
- `api/arhia_sag_screen/evidence/envelope.py:_key()`:
  ```text
  ARHIA_HMAC_KEY si está definida; si no, uuid4().hex (aleatoria por proceso)
  ```

**Impacto analizado:**
- **Serverless instances:** cada instancia arranca con una clave distinta → el HMAC de una evidencia no es verificable desde otra instancia.
- **Restart:** tras un reinicio la clave cambia → evidencia anterior inverificable.
- **Historical verification:** imposible re-verificar una evidencia firmada en un proceso anterior.
- **Multi-instance execution:** un sobre firmado en A no puede validarse en B.
- **Evidence reproducibility / auditability:** comprometidas mientras la clave no sea estable.

**Opciones (sin modificar código en esta sesión):**
1. **Variable de entorno estable** (`ARHIA_HMAC_KEY` obligatoria en producción) — mínima, determinista.
2. **Derivar de `ARHIAX_AUTH_SECRET`** (HKDF) — una sola fuente de secreto, reproducible.
3. **KMS/HSM** (Vercel Key Management / proveedor) — más robusta, mayor costo; diferible.

**Clasificación:**
```text
REQUIRED_BEFORE_SLICE  (antes de cualquier slice que emita/verifique evidencia HMAC
                        entre instancias; el dictamen actual firma receipts con SHA-256,
                        que sí es estable, así que no bloquea SLICE-001).
```

**Status:** DECIDED (opción 1 o 2; elegir 2 si se quiere una sola fuente de secreto). Sin cambio de código en esta sesión.

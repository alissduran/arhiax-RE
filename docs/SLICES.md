# ARHIAX RE — Vertical Slices (Roadmap)

Estrategia: **INCREMENTAL ARCHITECTURE + VERTICAL SLICES + STRANGLER PATTERN**.
Ningún slice está implementado; este es el roadmap. El sistema actual sigue
funcionando mientras las capacidades se trasladan hacia límites más claros.

---

## Roadmap (validado contra el código real)

| Slice | Capacidad | Estado en el código hoy | Orden |
| --- | --- | --- | --- |
| SLICE-001 | Canonical Case Persistence | CRUD existe en `/api/dictamenes` + tabla `dictamenes`, pero el frontend usa `localStorage` como fuente de verdad (divergencia) | 1 (base de todo) |
| SLICE-002 | CTL → Canonical Property Identity | Ya existe (`canonical.py` + resolución por nomenclatura/NUPRE); falta formalizar contrato + resolver unidad PH → matriz | 2 |
| SLICE-003 | Canonical Identity → Findings → Consistency Gate | Ya existe (`finding_registry.py` + `consistency.py`); falta tipar hallazgos (tuplas → `Hallazgo`) | 3 |
| SLICE-004 | External/GIS Sources → Execution Receipts | Ya existe (`receipts.py` + estado por capa); falta formalizar "Source/SourceState" | 4 |
| SLICE-005 | Validated Case → Dictamen/PDF | Ya existe (`compile_pdf`); es el orquestador monolítico a extraer gradualmente | 5 |
| SLICE-006 | Async generation → QStash → Persistence → Download | Ya existe (`cola_pdf.py` + worker + `trabajos_pdf`); falta formalizar contrato job↔case | 6 |

El orden refleja dependencias: primero la fuente de verdad (1), luego identidad (2),
hallazgos/gate (3), receipts (4), y al final la extracción del PDF (5) y la cola (6).
SLICE-005/006 son los más invasivos (tocan `pdf_compiler.py`); se dejan al final.

---

## SLICE-001 — Canonical Case Persistence (especificación completa)

### Goal
Un usuario autenticado crea/lee/actualiza un Case y, al recargar el navegador,
ve el MISMO Case desde la fuente canónica (servidor/Neon), sin estado divergente
en `localStorage`.

### User-visible behavior
```text
Authenticated user → Create Case → Persist → Read Case → Browser reload →
Same canonical Case → Update Case → Persist
```

### Entry point (endpoints actuales involucrados)
- `POST /api/dictamenes` — `create_dictamen(payload, background_tasks, auth)`.
- `GET /api/dictamenes` — `list_dictamenes(auth)`.
- `POST /api/dictamenes/{case_id}/update` — `update_dictamen`.
- `DELETE /api/dictamenes/{case_id}` — `delete_dictamen(require_admin)`.
- Frontend: `public/index.html` (bandeja de casos, `localStorage.arhiax_cases`).

### Current tables
- `dictamenes` (`id`, `folio_matricula`, `direccion`, `barrio`, `ciudad`, `estrato`, `area`, `estado`, `valor_consolidado`, flags de insumos, `pdf_path`, `acreedor_real`, `certificado_*`, `lat/lon`, `fuente_geocod`).

### Current frontend behavior (riesgo)
- `dictamenes` se inicializa desde `localStorage` y se persiste ahí; el servidor es
  "espejo opcional" (comentario explícito en `index.html:1426-1427`).
- Riesgo: dos clientes/recargas pueden divergir (un caso creado en el servidor no
  aparece si `localStorage` está desincronizado, y viceversa).

### Contracts
- Request/response de `create/update/list/delete` sin schema tipado (dicts). Se
  documentará un contrato `Case` (id, folio, direccion, ciudad, estrato, area, estado) explícito.
- `get_db_connection()` + tabla `dictamenes` como persistence contract.

### Domain
- Concepto `Case` (ver `docs/DOMAIN_MODEL.md`). No hay entidad Python tipada hoy.

### Persistence
- Neon/Postgres como canonical (ver ADR-001). Migración versionada (ver ADR-003) para
  añadir `created_by` (ver ADR-002).

### Application service
- Extraer un servicio `case_service` (create/list/get/update/delete) que encapsule el
  acceso a `database`; los endpoints lo invocan. Sin mover carpetas: se puede crear
  `api/application/` o mantener en `index.py` con funciones extraídas (decisión de implementación).

### Interface
- `index.py` expone los mismos endpoints; el contrato HTTP no cambia (retrocompatible).

### Evidence
- `receipts`/`versioning` no aplican directamente; el slice añade trazabilidad de
  quién creó/actualizó (opcional `created_by`, `updated_at`).

### Tests
- Crear/leer/actualizar contra BD de test; recarga de navegador simulada (el listado
  viene del servidor); no hay estado divergente en `localStorage`.

### Definition of Done (final)
```text
- Case created (POST) y persistido en Neon/Postgres.
- Case retrieved (GET) desde el servidor.
- Case updated (POST /update) y persistido.
- Browser reload preserva el estado (el frontend lee del servidor, no de localStorage).
- Server/DB es canónico (localStorage queda como cache/sesión, no como verdad).
- No existe estado divergente duplicado.
- Auth enforce en todos los endpoints del caso.
- Tests de regresión verdes + tests nuevos verdes.
- Sin cambios de comportamiento ajeno (GIS/scoring/Titulux/PDF no se tocan).
```

### Dependencies
- Ninguna (es el primer slice). Depende de ADR-001 (fuente de verdad) y ADR-003
  (migraciones) si se añade `created_by`.

### Risks
- Cambiar el frontend de "localStorage es la verdad" a "servidor es la verdad" puede
  afectar la experiencia offline actual (que es intencional). Mitigación: mantener
  `localStorage` como cache optimista, pero reconciliar SIEMPRE contra el servidor.
- `created_by` (ADR-002) requiere decisión de producto (single-tenant vs multi-tenant).

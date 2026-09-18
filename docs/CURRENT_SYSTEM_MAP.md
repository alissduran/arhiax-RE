# ARHIAX RE — Current System Map

Mapa del sistema **observado** (comportamiento implementado + tests), no del
declarado. Clasificación de evidencia: `DECLARED` / `IMPLEMENTED` / `TESTED` /
`VERIFIED`. Un comentario no demuestra comportamiento.

Fecha de inspección: baseline de arquitectura.

---

## 5.1 Entry Points

| Entry point | Tipo | Evidencia | Estado |
| --- | --- | --- | --- |
| `api/index.py` | Aplicación FastAPI (API + login + endpoints) | `app = FastAPI(...)`, ~30 endpoints `@app.*` | VERIFIED (257 tests + uso en producción) |
| `api/index.py` `/api/v1/pdf/worker` | Worker asíncrono (recibe el job QStash y compila el PDF) | `@app.post("/api/v1/pdf/worker")` | VERIFIED |
| `public/index.html` | Frontend SPA (login, bandeja de casos, subida de insumos, generación) | `fetch` a `/api/*`, `localStorage`, `indexedDB` | VERIFIED |
| `scripts/` | Scripts CLI (debug, publicación AGOL, verificación) | `scripts/*.py` | IMPLEMENTED (no todos TESTED) |
| `dictamen_napoli.py`, `dictamen_040314248.py`, `build_pdf*.py`, `generar_archivos.py`, `migrate.py`, `sprint1_igac_discovery.py`, `check_predio_riesgo.py` | Scripts históricos / generación directa por caso | archivos en la raíz | HISTORICAL (algunos con rutas absolutas de Windows) |
| `motor_tma_lonja_baq_v1.0/` | Paquete motor TMA + capa Lonja (valoración) | sub-repo con `run_dictamen.py`, YAML de metodología | IMPLEMENTED (TESTED parcialmente) |

**Servicios externos** (infraestructura, no entry points propios):
- Neon/Postgres (persistencia) — vía `api/database.py` + `api/postgres_adapter.py`.
- QStash/Upstash (cola async) — vía `api/cola_pdf.py`.
- Resend (correo) — vía `api/notificaciones.py`.
- Geoportales municipales (Barranquilla/Medellín/Bogotá/Pasto), SGC, IGAC, IDIGER, DAGRD — vía `api/integrations/*` y `api/*_territorio.py` / `api/catastro_predio*.py` / `api/riesgo_volcanico.py`.
- OpenStreetMap: Overpass + Photon (POI) y Nominatim (geocodificación) — vía `api/poi_engine.py`, `api/geocoder*.py`.

---

## 5.2 Component Map (capas conceptuales — sin mover archivos)

### INTERFACES (HTTP / API)
- `api/index.py` — endpoints de login, casos (CRUD), upload, generación, GPV-F-77, monitoreo, geo, config.
- Autenticación: tokens HMAC-SHA256 con expiración (`_firmar`/`_crear_token`/`_decodificar_token`), roles `admin`/`operador` (`require_auth`/`require_admin`), rate limiting de login.

### APPLICATION / ORCHESTRATION
- `api/index.py` — orquestación del flujo de caso: login → create/update → upload → generar (síncrono o QStash) → descargar.
- `api/pdf_compiler.py` — orquestación del dictamen: CTL → resolución de identidad → GIS/riesgos → valoración → scoring → Titulux → receipts → gate → PDF.
- `api/titulux_bridge.py` — orquestación del pre-dictamen Titulux + screening SAGRILAFT.
- `api/cola_pdf.py` — orquestación de la cola QStash.

### DOMAIN
- `api/legal_analyzer.py` — análisis del CTL (folio, titulares, anotaciones, gravámenes, condición PH).
- `api/canonical.py` — `canonical_property_identity` + `administrative_context` (fuente autoritativa de identidad).
- `api/finding_registry.py` — registro único de hallazgos + detección de contradicciones.
- `api/consistency.py` — invariantes + `PRE_RENDER_CONSISTENCY_GATE`.
- `api/receipts.py` — execution receipts (traza técnica por fuente).
- `api/dictamen_data.py` — datos del dictamen (valoración Lonja, alcance, catastro, POT).
- `api/score_engine.py` — score actuarial LAI v1.0.
- `api/carga_economica.py` — carga hipotecaria (amortización francesa, LTV).
- `api/edificabilidad.py`, `api/licencia_analyzer.py`, `api/solar_engine.py`, `api/geospatial_engine.py` — reglas POT/edificabilidad/licencia/sombras.
- `api/arhia_title/` — pre-dictamen jurídico (reglas TIT_B01..B05, VAL_B01, TRX_B01).
- `api/arhia_sag_screen/` — screening SAGRILAFT/PTEE (ingest de listas ONU/OFAC/UK/UE, matcher, KYB, SIREL, evidence).
- `api/arhia_expediente/` — expediente de confianza (títulos + integridad + conclusión).

### PERSISTENCE
- `api/database.py` — resolución del DSN + `init_db()` (SQLite) y despacho a Postgres.
- `api/postgres_adapter.py` — adaptador sqlite3→psycopg (`?`→`%s`, `lastrowid`→RETURNING).
- `api/listas_cache.py` — caché Neon de listas restrictivas (TTL 24h).

### EXTERNAL INFRASTRUCTURE (adapters GIS / servicios)
- `api/integrations/arcgis_client.py`, `wfs_client.py`, `catastro_live.py`, `territorio.py`.
- `api/pasto_territorio.py`, `api/riesgo_volcanico.py`, `api/catastro_predio*.py`, `api/geocoder*.py`, `api/poi_engine.py`.

### EVIDENCE / AUDITABILITY
- `api/arhia_sag_screen/evidence/envelope.py` + `versioning.py` (HMAC + SHA-256).
- `api/receipts.py`, `api/versioning.py` (matriz de versiones + git SHA).
- `api/finding_registry.py`, `api/consistency.py`.

### PRESENTATION
- `public/index.html` (SPA).
- `api/pdf_compiler.py` (ReportLab) + `api/dictamen_part1_styles.py`.
- `api/gpv_f77.py` (DOCX Estudio de Títulos).
- `api/map_generator.py`, `api/shadow_render.py` (figuras).

### TESTING
- `tests/` — 257 tests offline + tests `network` marcados (10 deselected).

---

## 5.3 Dependency Map

### `api/index.py` (el hub)
- Importa: `database`, `pdf_compiler`, `address_normalizer`, `geocoder`, `config`, `legal_analyzer`, `titulux_bridge`, `gpv_f77`, `cola_pdf`, `listas_cache`, `versioning`, `geospatial_engine`.
- Acceso a BD directo en: listar/crear/update/delete casos, upload, documentos, trabajos_pdf (`get_db_connection()` + SQL inline).
- Orquesta: login (HMAC), generación (`compile_pdf`), cola (QStash), monitoreo (`/api/v1/status`), geo en vivo (`/api/v1/geo/catastro`).

### `api/pdf_compiler.py` (el orquestador monolítico)
- Depende de casi todo: `legal_analyzer`, `canonical`, `consistency`, `receipts`, `versioning`, `titulux_bridge`, `score_engine`, `dictamen_data`, `edificabilidad`, `licencia_analyzer`, `pasto_territorio`, `riesgo_volcanico`, `poi_engine`, `map_generator`, `shadow_render`, `geospatial_engine`, `catastro_predio*`, `geocoder*`, `arhia_title/*`, `arhia_sag_screen/*`, `arhia_expediente/*`.
- Side effects: geocodificación, POIs (Overpass/Photon), generación de mapas/sombras, envío de correo (Resend), lectura del CTL (pypdf), escritura del PDF.

### Persistencia
- `database.get_db_connection()` → SQLite (`init_db`) o Postgres (`postgres_adapter`).
- `listas_cache` → solo Postgres (degradación a {} en SQLite).
- `trabajos_pdf` (cola) → `database` (SQLite /tmp efímero en Vercel, o Neon).
- `documentos_caso`, `dictamenes` → `database`.

### Frontend → API
- `public/index.html` → `fetch` a `/api/login`, `/api/dictamenes` (CRUD), `/api/dictamenes/{id}/upload/*`, `/api/dictamenes/{id}/update`, `/api/dictamenes/generar`, `/api/v1/pdf/trabajos/{id}`, `/api/dictamenes/gpv-f77`, `/api/v1/status`, `/api/v1/admin/usuarios`, `/api/v1/listas/refrescar`, `/api/v1/diagnostico/poi`, `/api/v1/geo/catastro`.
- **Estado de sesión/casos en el navegador**: `localStorage` (`arhiax_token`, `arhiax_username`, `arhiax_rol`, `arhiax_cases`) + `indexedDB` (`arhiax_insumos`, binarios).

### Acoplamiento y side-effects observados
- `pdf_compiler.py` es el punto de mayor acoplamiento: concentra dominio + orquestación + infraestructura + presentación.
- El esquema se crea/migra en cada conexión (`CREATE TABLE IF NOT EXISTS` + `ALTER TABLE ADD COLUMN` idempotente) — sin versionamiento.
- DDL duplicado entre `database.py` (SQLite) y `postgres_adapter.py` (Postgres).
- La lista de casos tiene doble fuente: `localStorage` (frontend, "fuente de verdad") vs Postgres/Neon (servidor, "espejo opcional").

### Dependencias circulares / implícitas
- No hay import circular duro (los módulos se importan bajo demanda dentro de funciones). El acoplamiento es **implícito por contrato de datos** (dicts y tuplas con forma asumida), no por tipos.

# ARHIAX RE — Current Contracts

Clasificación: `EXPLICIT CONTRACT` (tipado/dataclass/enum o endpoint documentado),
`IMPLICIT CONTRACT` (forma asumida por convención, sin tipo), `NO STABLE CONTRACT`.

---

## UI → API

| Contract | Type | Evidence |
| --- | --- | --- |
| `POST /api/login` `{username?, password}` → `{success, token, rol, username, expires_in_hours}` | EXPLICIT (por uso) | `login()` en `index.py`; frontend `fetch('/api/login')` |
| Bearer token en header `Authorization` para endpoints protegidos | EXPLICIT | `HTTPBearer` + `require_auth` |
| `GET/POST /api/dictamenes`, `POST /api/dictamenes/{id}/update`, `DELETE /api/dictamenes/{id}` | IMPLICIT | sin schema de request/response tipado (dicts `Body(...)`) |
| `POST /api/dictamenes/generar` (multipart `Form`) → PDF o `{encolado, job_id}` | IMPLICIT | `generar_dictamen_stateless` (Form fields) |
| `GET /api/v1/pdf/trabajos/{job_id}` → `{job_id, estado, error}` o PDF | IMPLICIT | `obtener_trabajo_pdf` |
| `POST /api/dictamenes/{id}/upload/{img_type}` (UploadFile) | IMPLICIT | `upload_image` |

## API → services

| Contract | Type | Evidence |
| --- | --- | --- |
| `compile_pdf(db_record, output_pdf_path, assets_dir)` | IMPLICIT (db_record dict con ~15 claves) | `pdf_compiler.compile_pdf` |
| `ejecutar_titulux(analysis, db_record, val_data, geo_eval, *, area_catastral, identidad, ...) → dict` | IMPLICIT | `titulux_bridge` |
| `calcular_score_actuarial(hallazgos, geo_eval, analysis, val_data) → dict` | EXPLICIT (retorno dict bien definido) | `score_engine` |
| `get_valuation(...) → dict` | EXPLICIT (retorno dict con claves m1/m2/m3/consolidado/metodologia_aplica) | `dictamen_data` |
| `analizar_certificado(path) → dict` (folio, titulares, anotaciones_detalle, ...) | IMPLICIT | `legal_analyzer` |

## services → persistence

| Contract | Type | Evidence |
| --- | --- | --- |
| `get_db_connection() → conn` con API sqlite3 (dict rows, `?` placeholders, `lastrowid`) | EXPLICIT (por adapter) | `database` + `postgres_adapter` |
| Tablas `dictamenes`, `trabajos_pdf`, `documentos_caso`, `listas_cache` | EXPLICIT (DDL) | `database.py`, `postgres_adapter.py`, `listas_cache.py` |
| SQL inline en endpoints (no repositorio) | IMPLICIT | `index.py` (CREATE/UPDATE/SELECT/DELETE directos) |

## pipeline → evidence

| Contract | Type | Evidence |
| --- | --- | --- |
| `receipts.build_execution_receipts(...) → dict` y `receipt_rows(dict) → [(label, valor)]` | EXPLICIT | `receipts.py` |
| `versioning.version_blob() → dict` (ARHIAX_RE_VERSION, GIT_COMMIT_SHA, ...) | EXPLICIT | `versioning.py` |
| Envelope HMAC (`arhia_sag_screen/evidence/envelope.py`) | IMPLICIT | clave por proceso (ADR-004) |

## pipeline → findings

| Contract | Type | Evidence |
| --- | --- | --- |
| Hallazgo legal/GIS como tupla de 6/7 `(sev, tc, bg, titulo, fuente, desc, impl)` | IMPLICIT | `legal_analyzer`, `pdf_compiler` |
| Hallazgo Titulux como dataclass `Hallazgo` | EXPLICIT | `arhia_title/contracts.py` |
| `finding_registry.coherencia(hallazgos, titulux, canonical_identity) → dict` | EXPLICIT | `finding_registry.py` |

## findings → consistency gate

| Contract | Type | Evidence |
| --- | --- | --- |
| `consistency.ejecutar_gate(contexto) → dict` con `{ok, bloqueantes, advertencias, resultados}` | EXPLICIT | `consistency.py` |
| `InconsistenciaBloqueante` (excepción) impide emitir el PDF | EXPLICIT | `consistency.py` |

## case → PDF

| Contract | Type | Evidence |
| --- | --- | --- |
| `db_record` (folio, direccion, barrio, ciudad, area, estrato, certificado_path, ...) → `compile_pdf` → PDF | IMPLICIT | `pdf_compiler.compile_pdf` |
| `canonical_identity` + `administrative_context` consumidos por el renderer y Titulux | EXPLICIT | `canonical.py` (dicts con estructura definida) |

## system → external source

| Contract | Type | Evidence |
| --- | --- | --- |
| `consultar_pasto(*, lat, lon, codigo_predial) → dict {disponible, predio, entorno, riesgos, fuente, capas}` | EXPLICIT | `pasto_territorio.py` |
| `verificar_riesgo_volcanico(lat, lon) → dict {disponible, nivel, zonas}` | EXPLICIT | `riesgo_volcanico.py` |
| `get_nearby_pois(lat, lon, radius) → {Salud, Educacion, Comercio, Recreacion}` | EXPLICIT | `poi_engine.py` |
| `enriquecer_desde_ctl` / `enriquecer_por_punto` (BAQ/Medellín/Bogotá) | IMPLICIT | `catastro_predio*.py` |
| Estados de capa `MATCH_EXACT/NO_MATCH/NULL_VALUE/NOT_APPLICABLE/SOURCE_UNAVAILABLE/...` | IMPLICIT (strings) | `pasto_territorio._estado_capa` |

## worker → queue

| Contract | Type | Evidence |
| --- | --- | --- |
| `cola_pdf.encolar_generacion(datos) → {encolado, message_id}` (QStash v2 `POST /v2/publish/{worker_url}`) | EXPLICIT | `cola_pdf.py` |
| Worker `/api/v1/pdf/worker` recibe `{job_id, folio_matricula, direccion, area, barrio, ciudad, certificado_b64?, licencia_b64?}` | IMPLICIT | `worker_generar_pdf` |
| Firma QStash (`Upstash-Signature`) o Bearer para autenticar el worker | EXPLICIT | `_verificar_firma_qstash` |

---

## Contratos con forma tipada real (reutilizables como contratos)

- `arhia_title/contracts.py`: `Anotacion`, `Avaluo`, `Caso`, `Parte`, `Predio`, `Pago`, `Evidencia`, `Hallazgo`.
- `arhia_sag_screen/contracts.py`: `Contraparte`, `ListaVersion`, `RegistroNormalizado`, `ResultadoConsulta`, `Accionista`, `RegistroJuridico`, `BeneficiarioFinal`.
- `arhia_expediente/expediente.py`: `FichaIntegridad`, `Expediente`; `conclusion.py`: `Conclusion`.

## SLICE-001 — Canonical Case Persistence (contratos nuevos)

| Contract | Type | Evidence |
| --- | --- | --- |
| `case_service.create_case(*, folio_matricula, direccion, barrio, estrato, area, ciudad, acreedor_real, created_by) → dict` | EXPLICIT | `api/case_service.py` |
| `case_service.get_case/list_cases/update_case/delete_case` | EXPLICIT | `api/case_service.py` |
| `case_repository.CaseRepository` (insert/get/list/update/delete + `_row_to_case` que NO expone `pdf_path`/`certificado_path`) | EXPLICIT | `api/case_repository.py` |
| `migrations.run_migrations(conn)` + `ensure_migrated(conn)` (versionado, idempotente) | EXPLICIT | `api/migrations.py` |
| `ARHIAX_EVIDENCE_HMAC_KEY` (clave de evidencia, independiente del secreto de auth) | EXPLICIT | `arhia_sag_screen/evidence/envelope.py` |

Campo canónico del Case (derivado del schema + API + frontend + domain model):
- REQUIRED: `id`, `folio_matricula`, `direccion`, `barrio`, `estrato`, `estado`.
- OPTIONAL: `area`, `valor_consolidado`, `ciudad`, `acreedor_real`, `lat`, `lon`, `fuente_geocod`.
- DERIVED: `fecha_creacion`.
- LEGACY (insumo/generación, no canónico del Case): `sombra_9am_cargada`, `sombra_3pm_cargada`,
  `mapa_cargado`, `certificado_cargado`, `certificado_path`, `pdf_path`.
- AUDIT (metadata, no ownership): `created_by`, `updated_by`.

## Contratos implícitos más frágiles (candidatos a formalizar)

1. `db_record` hacia `compile_pdf` (dict con claves asumidas).
2. `analysis` del `legal_analyzer` (dict con claves asumidas).
3. Hallazgos como tuplas de 6/7 (vs `Hallazgo` dataclass).
4. Estados de capa GIS como strings (sin enum).
5. `localStorage.arhiax_cases` como espejo del estado del servidor (fuente de divergencia).

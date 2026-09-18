# ARHIAX RE — Minimal Domain Model

Extraído SOLO de conceptos que existen en código/tests. Lo que no puede
demostrarse se marca `UNKNOWN`.

---

## Case / Caso

- **Evidence in code:** tabla `dictamenes` (`api/database.py`); endpoints CRUD `/api/dictamenes` (`api/index.py`); `dictamenes` en `localStorage` (frontend).
- **Current representation:** fila SQLite/Postgres (columnas `folio_matricula`, `direccion`, `barrio`, `ciudad`, `estrato`, `area`, `estado`, `valor_consolidado`, flags de insumos, `pdf_path`, `acreedor_real`) + espejo en `localStorage` (`arhiax_cases`).
- **Identity:** `id` (INTEGER/SERIAL AUTOINCREMENT).
- **Lifecycle/state:** `estado` (TEXT) — `pendiente`/`procesando`/`listo`/`error` (implícito por uso; `UNKNOWN` enumeración formal).
- **Relationships:** 1→N `documentos_caso`; 1→N `trabajos_pdf` (jobs de PDF); referencia a folio/predio.
- **Invariants:** `UNKNOWN` (no hay validación de estado central; el frontend y la API manipulan `estado` libremente).
- **Unknowns:** no existe entidad `Case` tipada en Python (solo filas DB + objetos JS); ownership no modelado (ver ADR-002).

## Property / Predio

- **Evidence in code:** `canonical_property_identity` (`api/canonical.py`); `Predio` dataclass en `arhia_title/contracts.py`; `predio_real` en `pdf_compiler.py`; `consultar_pasto`/`enriquecer_*`.
- **Current representation:** dict `canonical_property_identity` (estado, NUPRE, folio_snr, matrícula municipal, nomenclatura, titular, PH) + `Predio(folio_matricula, codigo_catastral, direccion, area_registral, area_catastral)`.
- **Identity:** NUPRE (`numero_predial_nacional`); matrícula SNR (folio); código predial anterior/corto.
- **Lifecycle/state:** estados de resolución: `MATCH_EXACT` / `MATCH_BY_NUPRE` / `MATCH_BY_PREDIAL_CODE` / `MATCH_BY_NOMENCLATURA` / `MATCH_BY_GEOMETRY` / `IDENTITY_CONFLICT` / `NO_RECORD`.
- **Relationships:** tiene `administrative_context` (comuna/barrio/estrato/clase_suelo/tratamiento); titular (Party); riesgos; tratamiento/área de actividad.
- **Invariants:** precedencia de resolución (NUPRE → código → matrícula → nomenclatura → geometría); IDENTITY_CONFLICT bloquea afirmación de datos prediales.
- **Unknowns:** relación formal "unidad PH → parcela matriz" (hallazgo del diagnóstico Pasto: la unidad no tiene polígono; resolver por MATRIZ aún no integrado).

## Folio (matrícula inmobiliaria)

- **Evidence in code:** `analysis["folio"]` (`legal_analyzer.py`), `folio_snr` (`canonical.py`), `_extraer_folio` (regex), `_detectar_discrepancia_circulo`.
- **Current representation:** string `"240-211101"` (círculo + número).
- **Identity:** el propio folio (clave registral SNR).
- **Lifecycle/state:** n/a (valor de identidad).
- **Relationships:** pertenece a un Property; valida contra `circulo_registral` de la ciudad.
- **Invariants:** el círculo del folio debe corresponder a la ciudad del caso (H-CTL).
- **Unknowns:** n/a.

## Party / Parte

- **Evidence in code:** `Parte(rol, nombre, tipo_documento, numero_documento, beneficiario_final)` (`arhia_title/contracts.py`); `_nombre_documento`, `extraer_titular_canonico` (`canonical.py`); `Contraparte` (`arhia_sag_screen/contracts.py`).
- **Current representation:** dataclasses `Parte` y `Contraparte`; dict `titular` en `canonical_property_identity`.
- **Identity:** `tipo_documento` + `numero_documento` (CC/NIT/CE/PASAPORTE).
- **Lifecycle/state:** n/a.
- **Relationships:** titular de un Property; acreedor (hipoteca); contraparte de screening.
- **Invariants:** tipo de persona coherente con documento (`NATURAL_PERSON`/`LEGAL_ENTITY` — bug I).
- **Unknowns:** n/a.

## Evidence / Evidencia

- **Evidence in code:** `Evidencia(id, documento, fragmento)` (`arhia_title/contracts.py`); `arhia_sag_screen/evidence/envelope.py` (HMAC + SHA-256), `versioning.py`.
- **Current representation:** dataclass `Evidencia`; envelope HMAC (`hmac_hex`, `sha256_hex`).
- **Identity:** `id` + documento.
- **Lifecycle/state:** n/a.
- **Relationships:** cuelga de Hallazgo.
- **Invariants:** `UNKNOWN` (el envelope HMAC usa clave por proceso — ver ADR-004).

## Finding / Hallazgo

- **Evidence in code:** `Hallazgo(id, titulo, estado, severidad, descripcion, base_legal, implicacion, regla, evidencia, accion, responsable)` (`arhia_title/contracts.py`); tuplas de 6/7 en `legal_analyzer.py`/`pdf_compiler.py`; `finding_registry.py`.
- **Current representation:** dataclass `Hallazgo` (Titulux) + tuplas heterogéneas (pipeline del dictamen) + `recs` (tuplas de 2).
- **Identity:** `id` (código `H-0X`, `TIT_B0X`, `I-XXX`).
- **Lifecycle/state:** `estado` (`OK`/`OBSERVACION`/`RIESGO`/`INFORMACION_INSUFICIENTE`/`INCONSISTENTE`/`REQUIERE_REVISION`) y `severidad`.
- **Relationships:** proviene de capas (legal, Titulux, GIS, identidad, score); se consolida en `finding_registry`; alimenta el gate de consistencia.
- **Invariants:** sin contradicciones entre capas (TIT_B04 "sin gravámenes" vs embargo legal; TIT_B01 "falta folio" vs NUPRE resuelto).
- **Unknowns:** no hay un único tipo de hallazgo (conviven dataclass y tuplas).

## Execution Receipt

- **Evidence in code:** `api/receipts.py` (`build_execution_receipts`, `receipt_rows`); `versioning.py`.
- **Current representation:** dict `receipts` (generated_at, versionado, identidad, gis.capas, riesgo_volcanico, poi, sarlaft, geocodificacion).
- **Identity:** por ejecución (`generated_at` + `GIT_COMMIT_SHA`).
- **Lifecycle/state:** n/a (registro inmutable de una ejecución).
- **Relationships:** vincula un Case/Dictamen con las fuentes y versiones usadas.
- **Invariants:** refleja lo que REALMENTE corrió (no afirmaciones estáticas).

## Dictamen

- **Evidence in code:** `compile_pdf` (`pdf_compiler.py`); secciones del PDF; `cert_num`, `p_hash`.
- **Current representation:** PDF generado (ReportLab) + `cert_num` (`ARHIAX-LAI-2026-{id}`) + `p_hash` (SHA-256).
- **Identity:** `cert_num` + hash.
- **Lifecycle/state:** n/a (artefacto derivado).
- **Relationships:** deriva de un Case validado; incluye hallazgos, receipts, score, versión.
- **Invariants:** el gate impide emitir un dictus inconsistente.
- **Unknowns:** no hay persistencia estructurada del dictamen generado (solo el PDF en BD/trabajos).

## Screening

- **Evidence in code:** `arhia_sag_screen` (ingest/listas, match/matcher, contracts); `ejecutar_titulux` → screening; `screening_por_sujeto`, `screening_agregado`.
- **Current representation:** `ListaVersion` + `RegistroNormalizado` + `ResultadoConsulta` (`sinCoincidencia`/`candidato`/`revisionManual`/`coincidencia`).
- **Identity:** por `contraparte_id` + `lista` + `lista_version`.
- **Lifecycle/state:** `completo`/`pendiente`; fuentes `OPERATIVA`/`SYNTHETIC_TEST_FIXTURE`/`NO_DISPONIBLE`.
- **Relationships:** contra Partes/Contrapartes; fuentes ONU/OFAC/UK (vivo) + UIAF/UE (canal oficial/fichero).
- **Invariants:** sin coincidencia contra lista vacía; degradación honesta (fuente no disponible → pendiente, no "sin coincidencia").

## Beneficial Owner

- **Evidence in code:** `BeneficiarioFinal` (`arhia_sag_screen/contracts.py`); `arhia_sag_screen/kyb/beneficiario_final.py`; `FichaIntegridad.beneficiario_final`.
- **Current representation:** dataclass `BeneficiarioFinal` (tipo_doc, numero_doc, nombre, participacion, criterio, ...).
- **Identity:** tipo_doc + numero_doc.
- **Lifecycle/state:** n/a.
- **Relationships:** pertenece a una Party jurídica (persona natural detrás).
- **Invariants:** `UNKNOWN` (regla de identificación ≥5% declarada, no implementada de forma completa en el flujo del dictamen).
- **Unknowns:** no se resuelve automáticamente desde fuentes; es un documento pendiente (RUB).

## Legal Record (registro/CTL)

- **Evidence in code:** `legal_analyzer.py` (`analizar_certificado`, `anotaciones_detalle`, `hipoteca_vigente`, `acreedor_snr`, `circulo_registral`); `_tipo_titulux` (hipoteca/embargo/medida_cautelar/gravamen/compraventa/cancelación).
- **Current representation:** dict `analysis` + lista `anotaciones_detalle` (num, fecha, tipo, partes, texto, estado).
- **Identity:** folio + número de anotación.
- **Lifecycle/state:** anotación `VIGENTE`/`CANCELADA`.
- **Relationships:** define titular, gravámenes, cronología.
- **Invariants:** tracto sucesivo; cancelación extingue la anotación; hipoteca/embargo/medida cautelar separados (bug J).

## Valuation

- **Evidence in code:** `dictamen_data.get_valuation` (M1/M2/M3), `precondiciones_valoracion`; `Avaluo` dataclass; `motor_tma_lonja_baq_v1.0` (YAML Lonja).
- **Current representation:** dict `val_data` (consolidado, m1/m2/m3, bandas, canon, cap_rate, metodologia_aplica).
- **Identity:** n/a (valor derivado de un Property).
- **Lifecycle/state:** n/a.
- **Relationships:** depende de barrio/estrato/ciudad/tipología.
- **Invariants:** precondiciones por tipología (suelo de protección / no construible / rural → NO procede comparación); PH terminada → M1 (100%).

## Risk

- **Evidence in code:** `geo_eval` (amenaza_remocion_masa, areas_en_riesgo), `riesgos` del predio (Pasto), `verificar_riesgo_volcanico` (SGC); `score_engine` (hidrológico).
- **Current representation:** dict `geo_eval` + dict `riesgos` por campo (riesgo_volcanico_ea27, inundacion_ea23, remocion_en_masa_ea19, ...).
- **Identity:** por campo/peligro + fuente.
- **Lifecycle/state:** `evaluado` (bool) → score null si NO EVALUADO.
- **Relationships:** asociado a un Property (predio/matriz).
- **Invariants:** NO EVALUADO ≠ SIN RIESGO; NO EVALUADO ⇒ score hidrológico null.

## Source (fuente)

- **Evidence in code:** `consultar_pasto` (`fuente.estado`, `capas`), `receipts` (`gis.capas`), `config/ciudades.yaml` (servicios), `ListaVersion` (screening).
- **Current representation:** dicts con `nombre`/`url`/`estado` + estado por capa.
- **Identity:** URL/servicio + capa.
- **Lifecycle/state:** `SourceState` (ver abajo).
- **Relationships:** alimenta Execution Receipts.
- **Invariants:** `SOURCE_UNAVAILABLE` ≠ `NO_MATCH` (distinguir fallo de "sin coincidencia").

## Source State

- **Evidence in code:** `pasto_territorio._estado_capa` y `res["capas"]`: `MATCH_EXACT` / `NO_MATCH` / `NULL_VALUE` / `NOT_APPLICABLE` / `SOURCE_UNAVAILABLE` / `SOURCE_TIMEOUT` / `SCHEMA_CHANGED` / `NOT_EVALUATED`.
- **Current representation:** strings (no hay enum tipado).
- **Identity:** (fuente, capa) → estado.
- **Lifecycle/state:** n/a (estado observado en una ejecución).
- **Relationships:** es el resultado de consultar una Source.
- **Invariants:** n/a.

## Document

- **Evidence in code:** tabla `documentos_caso` (`database.py`); endpoints `/api/dictamenes/{id}/documentos`; catálogo `_DOCUMENTOS` (`notificaciones.py`).
- **Current representation:** fila (`id`, `case_id`, `nombre`, `tipo`, `contenido` BLOB, `creado`).
- **Identity:** `id`.
- **Lifecycle/state:** n/a (subida/bajada).
- **Relationships:** adjunto a un Case.
- **Invariants:** n/a.

## Job

- **Evidence in code:** tabla `trabajos_pdf` (`id`, `estado`, `pdf`, `error`, `creado`, adjuntos BLOB); worker `/api/v1/pdf/worker`; `cola_pdf.py`.
- **Current representation:** fila `trabajos_pdf` + payload QStash (`job_id`).
- **Identity:** `job_id` (UUID).
- **Lifecycle/state:** `pendiente` → `procesando` → `listo`/`error`.
- **Relationships:** pertenece a un Case (por folio, no por FK formal — `UNKNOWN`).
- **Invariants:** n/a.

## User / Role

- **Evidence in code:** `_USUARIOS` (username→(password,rol)); `_crear_token` (exp|username|rol); `require_auth`/`require_admin`; `ARHIAX_ADMIN_USER/PASSWORD`, `ARHIAX_OPERADOR_USER/PASSWORD`.
- **Current representation:** dict `_USUARIOS` en memoria (no hay tabla de usuarios).
- **Identity:** `username`.
- **Lifecycle/state:** n/a.
- **Relationships:** roles `admin`/`operador`.
- **Invariants:** `require_admin` restringe monitoreo/borrado a `admin`.
- **Unknowns:** no hay persistencia de usuarios; no hay relación user↔case (ownership ausente — ADR-002).

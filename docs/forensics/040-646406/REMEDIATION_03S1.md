# REMEDIATION 03S.1 — SANCTIONS SCREENING TRUTH LAYER

Caso de referencia: 040-646406 (Torre 8 Napoli Miramar) · baseline `main @ f321d2b9`.

Objetivo: construir una capa de screening sancionatorio **defendible**, que demuestre
QUIÉN fue consultado, CONTRA QUÉ fuente, QUÉ versión, CUÁNDO, CON QUÉ
identificadores, CON QUÉ algoritmo y CUÁL fue el resultado — y no que declare
"SAGRILAFT cumplido".

```
SUJETOS CANÓNICOS → FUENTES OFICIALES → SNAPSHOTS VERSIONADOS →
MATCHING DETERMINISTA → EVIDENCIA → DICTUS HONESTO
```

NO se tocó catastro, urbanismo, valoración, M1/M2/M3, riesgo ni POI. No se
implementó SIREL. No se integró PEP/World-Check/Truora ni SLICE-002.

---

## 0. Línea base forense — defectos corregidos

| # | Defecto del Dictus anterior | Estado |
|---|---|---|
| A | Ficha estructural: 3 sujetos; tabla de screening: 2 (uno desaparecía) | **corregido** (mismo set canónico) |
| B | BANCO DE BOGOTÁ S.A. aparecía como "Persona natural" | **corregido** (LEGAL_ENTITY por NIT) |
| C | El titular DURAN BACCA ALISSON (persona natural) salía como "persona jurídica" | **corregido** |
| D | Documentos incrustados en strings, ficha con `ID: N/D` | **corregido** (CC 1045718995X / NIT 8600029644) |
| E | UIAF como columna de lista (ONU \| OFAC \| UK \| UIAF) | **corregido** (UIAF fuera del screening) |
| F | 09 decía "screening ONU/OFAC/UK en vivo" y 16 "NO EJECUTADA" | **corregido** (un solo `ScreeningSummary`) |

## 1. Gate 1 — Canonical Subject Envelope (`api/sanctions/subjects.py`)

`SubjectEnvelope{subject_id, raw_name, canonical_name, person_type, document_type,
document_number, roles[], participation, source, source_reference,
identity_confidence, identity_warnings[], screened, reason_for_screening,
not_screened_reason}`.

- El screening **nunca** se hace sobre strings del PDF: primero se resuelve el
  envelope y ese es el único insumo.
- `person_type ∈ {NATURAL_PERSON, LEGAL_ENTITY, UNKNOWN}`:
  `UNKNOWN != NATURAL_PERSON` — sin documento y sin forma societaria el tipo queda
  `UNKNOWN` con advertencia (`PERSON_TYPE_UNKNOWN`, `DOCUMENT_MISSING`).
  Una forma societaria (BANCO, S.A., URBANIZADORA, LTDA…) sí acredita
  LEGAL_ENTITY, dejando la inferencia registrada (`PERSON_TYPE_INFERRED_FROM_LEGAL_FORM`).
- Documento: se conserva la representación **exacta** del CTL
  (`1045718995X`, con advertencia `DOCUMENT_NON_STANDARD_FORMAT`) y aparte la
  forma normalizada para el cotejo.
- "URBANIZADORA MARIN VALENCIA / MARVAL": NO se fusiona por similitud de nombre
  (`MULTIPLE_NAME_VARIANTS_NOT_FUSED`); dos personas jurídicas solo se fusionan
  por documento idéntico.
- Deduplicación: mismo documento, o (persona natural) mismo nombre con documentos
  variantes del mismo número (`1045718995` / `1045718995X`) — se conserva el
  documento más completo. Nunca por nombre en personas jurídicas.

### Invariante del set de sujetos (§5)

`subjects_declared == subjects_screened + subjects_not_screened_with_reason`
(`verificar_invariante()` lanza si no cuadra). Un sujeto con nombre inservible no
desaparece: se declara no screeningado **con motivo**.

### Roles screeningados (§4)

`TITULAR_ACTUAL`, `VENDEDOR`, `COMPRADOR`, `ACREEDOR_HIPOTECARIO`,
`ACREEDOR_REAL_DECLARADO`, `CONSTRUCTOR_ENAJENANTE`, con
`reason_for_screening` por rol. No se screeninga a toda persona histórica de
todas las anotaciones.

## 2. SourceRegistry (`api/sanctions/registry.py`)

`{source_id, authority, dataset_name, category, official_url,
current_or_historical, format, parser, parser_version, acquisition_policy,
refresh_policy, cobertura}`.

| source_id | Autoridad | Estado | URL oficial |
|---|---|---|---|
| `UN_CONSOLIDATED` | UN Security Council | CURRENT | `scsanctions.un.org/resources/xml/en/consolidated.xml` |
| `OFAC_SDN` | OFAC Sanctions List Service | CURRENT | `sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.XML` |
| `UK_SANCTIONS_LIST` | UK FCDO / OFSI | CURRENT | `sanctionslist.fcdo.gov.uk/docs/UK-Sanctions-List.xml` |
| `OFAC_NON_SDN` | OFAC SLS (listas no-SDN) | CURRENT (OPCIONAL 03S.1) | `…/exports/CONS_ADVANCED.XML` |
| `UK_OFSI_CONLIST_HISTORICAL` | HMT/OFSI (legado) | **HISTORICAL** | `…/ConList.xml` |
| `UIAF_SIREL` | UIAF Colombia | **REGULATORY_REPORTING** | — (OUT_OF_SCOPE_FOR_SCREENING) |
| `EU_CONSOLIDATED` | UE DG FISMA | OPCIONAL / OFFICIAL_FILE_REQUIRED | `webgate.ec.europa.eu/...` |
| `PEP_COLOMBIA` | registros oficiales CO | fuera de 03S.1 | — |

- **Migración de UK (bloqueante)**: `current_source_id("uk") == "UK_SANCTIONS_LIST"`;
  el `ConList.xml` de OFSI queda como `HISTORICAL_SOURCE` (solo reproducibilidad) y
  está **prohibido** como fuente vigente.
- **UIAF no es fuente de screening**: se elimina de fuentes, tabla y resultados.
  SIREL = canal de **reporte regulatorio** del sujeto obligado (03S.x).
- **Cobertura honesta**: con solo SDN la cobertura dice "OFAC — SDN (solo SDN)";
  nunca "OFAC completo".

## 3. Snapshots versionados, historia y frescura (`snapshots.py`, `acquire.py`)

`SanctionsSnapshot{snapshot_id, source_id, authority, retrieved_at,
effective_date, source_url, sha256, record_count, parser_version,
acquisition_status}` — `effective_date` se lee de la **propia fuente**
(`dateGenerated` de la ONU, `Publish_Date` de OFAC, `DateGenerated` de UK); si la
fuente no la declara, queda vacío (nunca se inventa).

- **§14 — no se borra historia**: el store guarda por `(source_id, sha256)` en
  disco y, cuando hay Postgres/Neon, en `sanctions_snapshots` con
  `ON CONFLICT (source_id, sha256)` + puntero `is_current` movido por `UPDATE`
  (jamás `DELETE`+`INSERT`). Un dictamen de ayer se reproduce contra la misma lista.
- **§15 — frescura**: `LIVE_FRESH` / `CACHED_FRESH` / `STALE_ALLOWED` /
  `STALE_NOT_ALLOWED` / `SOURCE_UNAVAILABLE` / `NO_SNAPSHOT`. El TTL controla el
  **refresco**; al vencer, la evidencia sigue disponible.
- **§16 — "en vivo" tiene significado estricto**: solo `LIVE_FRESH` (adquisición
  real en esa ejecución) imprime "consultado en vivo". Un snapshot del store
  imprime "consultado contra snapshot oficial versionado" + fecha + hash.
  `permitir_descarga=False` (suite offline) impide cualquier acceso de red.

## 4. Matching determinista (`api/sanctions/matching.py`)

Jerarquía: 1) identificador exacto · 2) nombre normalizado exacto + atributo
corroborante · 3) alias exacto + atributos · 4) nombre difuso + atributos ·
5) nombre difuso solo (`sanctions-matcher/1.0`, umbrales 0.90 / 0.80).

- **Nunca** un match solo por nombre difuso produce coincidencia confirmada:
  `POTENTIAL_MATCH` (≥0.90) o `REVIEW_REQUIRED` (≥0.80).
- Variante de formato de documento (`1045718995` vs `1045718995X`): se confirma
  como `STRONG_MATCH` **en revisión**, con el motivo declarado; nunca exacto
  silencioso.
- **§19 conflicto de identificadores**: nombre exacto con documento/DOB
  incompatible → `REVIEW_REQUIRED` con `IDENTIFIER_CONFLICT`/`DOCUMENT_MISMATCH`/
  `BIRTHDATE_MISMATCH`. El nombre exacto no basta para confirmar una sanción.

Estados por fuente: `NO_MATCH`, `POTENTIAL_MATCH`, `STRONG_MATCH`, `EXACT_MATCH`,
`REVIEW_REQUIRED`, `NOT_SCREENED`, `SOURCE_UNAVAILABLE`. En el dictamen las celdas
usan MATCH / REVIEW / NO MATCH / UNAVAILABLE (+ "(CACHED)" si vino de snapshot).

## 5. Evidencia (`api/sanctions/evidence.py`)

Un `EvidenceRecord` por consulta sujeto × fuente: `evidence_id, subject_id,
canonical_name, document_type, document_number_masked, source_id,
snapshot_sha256, snapshot_effective_date, query_hash, screened_at,
algorithm_version, result, score, matched_record_ids, matching_reasons,
review_status`, más `subject_hash` y `evidence_hash`. Se encadena con el
mecanismo HMAC ya existente (`arhia_sag_screen.evidence.envelope.build_event`,
`previous_hash`/`chain_hash`).

**§21 semántica de hash (declarada en el PDF):** cada hash sella un artefacto
distinto (sujeto / snapshot de la lista / consulta / envelope de evidencia) y
prueba **integridad y reproducibilidad**; **no** prueba que la información de
origen sea verdadera. Se eliminó la frase "garantiza que los nombres no se alteren".

## 6. Dictus (05 / 09 / 16 / 16.B / receipts) — una sola verdad

- **Sección 09 renombrada**: "09 - Screening de Contrapartes y Debida
  Diligencia", subtítulo "Apoyo automatizado al proceso LA/FT/SAGRILAFT".
- **09.1** tabla por contraparte: `Sujeto | Tipo | Documento | Rol | ONU | OFAC SDN
  | UKSL | Resultado`. Sin columna UIAF.
- **09.2** procedencia por fuente: autoridad, obtención (frescura), fecha efectiva,
  registros y SHA-256 del artefacto consultado.
- Resultado global, revisión requerida / coincidencia y fuentes no disponibles se
  declaran con la redacción del §35: *"Sin coincidencias en las fuentes
  efectivamente consultadas. UKSL no estuvo disponible."* — jamás un "sin
  coincidencias" absoluto.
- `ScreeningSummary` (`SCREENING_COMPLETE / PARTIAL / NOT_EXECUTED /
  REVIEW_REQUIRED`) alimenta 05, 09, 16, 16.B y los receipts: la Declaración de
  Alcance ya no puede decir "NO EJECUTADA" mientras el 09 dice "ejecutado".
- `FichaIntegridad.regimen` dejó de afirmarse (`no_obligado` era una conclusión
  jurídica): el dictamen presta screening/due-diligence support, no determina
  sujeto obligado ni régimen (§28).
- Titulux: la tipología/SAG_B01 ya no dice "titular (persona jurídica)" cuando el
  envelope dice NATURAL_PERSON, y no menciona "ONU/OFAC/UIAF".

## 7. Mapeo legal (`api/sanctions/legal.py`)

`RequirementMapping{requirement_id, source_document, chapter, numeral,
numeral_verified, text_summary, verified_at}`. La Circular Externa 100-000020 del
2 de julio de 2026 es el documento de referencia, pero los numerales (9.14.1,
9.15.1, 9.17, 9.19, 9.20, 9.22) **no están verificados** contra el PDF oficial:
`numeral_verified=False` ⇒ **no se imprimen**. Un test del dictamen falla si
aparece cualquiera de ellos.

## 8. Aislamiento de datos de demostración (§12)

Los registros sintéticos (`uiaf-001`, `ue-001`, `pep-001`, `int-001`, …) salieron
del módulo productivo y viven en `tests/fixtures/screening/muestras_sinteticas.json`.
`arhia_sag_screen.ingest.sources` ya no contiene registros de listas (solo
catálogo) y `obtener_listas` **eliminó el fallback a muestras**: una fuente que no
se puede adquirir simplemente no aparece. Regla:
`SYNTHETIC_TEST_FIXTURE != SCREENING EVIDENCE`.

## 9. Tests — `tests/test_remediacion_03s1.py` (54 casos) + parsers

- Parsers (ONU/OFAC SDN/UK Sanctions List) contra **fixtures sanitizados con la
  estructura oficial** (`tests/fixtures/screening/*.xml`), incluida la detección
  de estructura no reconocida.
- Registry: UK vigente = `UK_SANCTIONS_LIST`; ConList histórico y prohibido;
  UIAF fuera del screening; cobertura sin "OFAC completo"; core sin UIAF.
- Sujetos: §29 titular natural · §30 banco jurídico · §31 constructor presente e
  invariante · sin documento ≠ natural · dedupe por documento/variante.
- Snapshots: historia preservada (3 versiones + CURRENT) · CACHED ≠ "en vivo" ·
  frescura (CACHED/STALE/NO_SNAPSHOT) · offline no inventa.
- Matching: documento exacto · nombre exacto corroborado · fuzzy solo nombre nunca
  confirma · conflicto de identificadores · variante de formato.
- Estado global: §35 PARTIAL con UK no disponible y su texto · COMPLETE ·
  NOT_EXECUTED · REVIEW_REQUIRED con candidato · EXACT con documento · cada
  NO_MATCH con fuente+snapshot+hash.
- Evidencia: envelope completo, documento enmascarado, hashes distintos.
- Demostración: los ids de muestra no están en `api/`, el fixture vive en tests,
  las fuentes productivas no incluyen muestras.
- Dictamen (PDF real compilado sin red, con CTL adjunto y snapshots sembrados):
  §22 sección renombrada · §32 sin columna UIAF · §23 tabla con tipo/documento/rol
  · §41 personas con tipo correcto, constructor presente, documentos extraídos,
  fuente+versión+fecha+hash trazables, **sin "en vivo"**, 05/09/16/16.B
  coherentes, semántica de hash, algoritmo declarado, sin numerales no
  verificados. Variantes: con coincidencia (se reporta sin acusar) y sin fuentes
  (NO EJECUTADO declarado).

## 10. Aceptación EN VIVO (§40) — ejecutada en esta sesión

`python scripts/screening_live_check.py --cache-dir <dir>` obtuvo las tres fuentes
oficiales (`acquisition_status=OPERATIVA`, `freshness=LIVE_FRESH`):

| fuente | registros | fecha efectiva (declarada por la fuente) | sha256 (16) | parser |
|---|---|---|---|---|
| `UN_CONSOLIDATED` | 1011 | 2026-09-19T23:00:03.787Z | `e00d452dec23b46d` | onu_xml/1.0 |
| `OFAC_SDN` | 19393 | 09/18/2026 | `30c2a70887d694f7` | ofac_sdn_xml/1.0 |
| `UK_SANCTIONS_LIST` | 6339 | 21/09/2026 | `50b83b8202daf366` | uk_sanctions_list_xml/1.0 |

El conteo de OFAC (19 393) coincide con el `Record_Count` que la propia fuente
declara en su cabecera: verificación cruzada de que el parser no pierde registros.
Los tres sujetos del Golden (titular, banco, constructor) dieron `NO_MATCH` contra
la lista de la ONU en esa corrida. Si no hubiera red, el script informa
`LIVE_SOURCES_NOT_VERIFIED` y **no** simula éxito.

## 11. SIREL — aplazado (ADR)

SIREL sirve para la **presentación de reportes** por los sujetos obligados, no
para screening. Futuro: 03S.x Regulatory Reporting. Prohibido por decisión:
bypass de CAPTCHA, credenciales embebidas y automatización no soportada. En 03S.1
`UIAF_SIREL = OUT_OF_SCOPE_FOR_SCREENING`.

## 12. Lo que NO se cerró

- `OFAC_NON_SDN` queda **declarado pero no consultado** en 03S.1 (opcional): la
  cobertura lo dice explícitamente ("solo SDN").
- `EU_CONSOLIDATED`: OPCIONAL / OFFICIAL_FILE_REQUIRED (el portal bloquea la
  descarga automatizada).
- PEP avanzado, World-Check/Refinitiv, Truora/TusDatos,
  Procuraduría/Contraloría/Policía, envío a SIREL y automatización de ROS: fuera
  de alcance por instrucción.
- Los numerales de la CBJ siguen sin verificar contra el PDF oficial.

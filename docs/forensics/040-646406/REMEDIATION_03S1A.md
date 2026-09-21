# REMEDIATION 03S.1A — SANCTIONS TRUTH LAYER: INTEGRITY CLOSURE

Baseline `main @ 9caac59`. Cierra cuatro defectos residuales del core
sancionatorio de 03S.1, más dos ajustes menores exigidos por la auditoría.

NO se amplió a PEP, UE, SIREL, WorldCheck, Truora ni antecedentes. No se tocó
catastro, valoración ni urbanismo. No se inició SLICE-002.

---

## 1. La frescura es LOCAL A LA EJECUCIÓN

**Defecto confirmado**: el snapshot se persistía con `freshness=LIVE_FRESH` y
`evaluar_frescura()` tenía el atajo

```python
if snap.freshness == FRESH_LIVE:
    return FRESH_LIVE          # ← propagaba "en vivo" a ejecuciones posteriores
```

**Corregido**:
- `evaluar_frescura()` **nunca** devuelve `LIVE_FRESH`: siempre calcula la EDAD
  real contra `retrieved_at` (y el TTL). Si la fecha de obtención no es fiable,
  se trata como vencido y decide la política.
- `LIVE_FRESH` solo lo produce la rama que acaba de ejecutar `fetch_bytes()` con
  éxito en esa ejecución (`adquirir_fuente`, paso 2).
- Al leer del store: `age <= TTL → CACHED_FRESH`; `age > TTL` y stale permitido →
  `STALE_ALLOWED`; stale prohibido → `STALE_NOT_ALLOWED`. El TTL manda el
  REFRESCO: si el snapshot venció y la descarga es posible, se intenta; si no,
  se sirve el snapshot con su estado real de frescura.

Test bloqueante (A/B/C) en `tests/test_remediacion_03s1a.py`:
descarga real (simulada con `fetch_bytes` parcheado) → `LIVE_FRESH` → guardar →
segunda ejecución `permitir_descarga=False` → **`CACHED_FRESH`** y
`es_en_vivo == False` → mismo snapshot con antigüedad > TTL → `STALE_ALLOWED` /
`STALE_NOT_ALLOWED` según política. Además: el dictamen compilado contra
snapshots del store no contiene ninguna fuente `LIVE_FRESH`.

## 2. La evidencia no puede desaparecer en silencio

**Defecto**: `encadenar_eventos()` devolvía `()` sin declararlo y el resumen no
llevaba contadores de evidencia; un fallo de la cadena HMAC era invisible.

**Corregido** — separación explícita entre creación y persistencia:

- Todo outcome sujeto×fuente produce **siempre** un `EvidenceRecord`
  serializable (no depende de la cadena).
- `ScreeningSummary` incorpora: `evidence_records`,
  `evidence_expected_count`, `evidence_created_count`, `evidence_chain_status`
  (`SEALED` / `FAILED` / `NOT_REQUIRED_DEV`), más `evidence_complete` y
  `evidence_reproducible`.
- El motor **intenta** la cadena y **declara** su estado; la verificación es
  explícita (`verificar_cadena`). `FAILED` añade al motivo "la evidencia no pudo
  sellarse".
- **Fail-closed en producción**: si `encadenar_evidencia=True` y la cadena falla
  (`ARHIAX_ENV=production` / `VERCEL`), el estado **no** puede ser
  `SCREENING_COMPLETE`: se degrada a `SCREENING_PARTIAL` y el motivo lo explica.
  En dev/test la degradación es explícita (`NOT_REQUIRED_DEV` cuando se opta por
  no encadenar), nunca silenciosa.
- Dictamen: nueva subsección **09.3 Evidencia de las consultas** con
  *consultas esperadas* / *envelopes creados* / *estado de la cadena*; si la
  cadena falla, aparece la alerta "EVIDENCIA NO SELLADA" y no se afirma
  reproducibilidad. Los receipts (16.B) reportan los mismos tres datos.

Tests: 3 sujetos × 3 fuentes = 9 outcomes → **9 EvidenceRecords**;
con la cadena forzada a fallar los 9 envelopes siguen existiendo,
`evidence_chain_status=FAILED` y el motivo lo declara; en producción sin clave
HMAC la cadena falla de forma real y el screening **no** se declara completo; con
clave, `SEALED` y `SCREENING_COMPLETE`.

## 3. COBERTURA != DECISIÓN

**Defecto**: `cobertura_completa` se derivaba del `status`
(`in (COMPLETE, REVIEW_REQUIRED)`), de modo que una fuente caída podía convivir
con "cobertura completa".

**Corregido**:
- `decision_status` (= `status`) y `coverage_status`
  (`COVERAGE_COMPLETE` / `COVERAGE_PARTIAL` / `COVERAGE_NOT_EXECUTED`) son
  dimensiones separadas.
- La cobertura se calcula de los **outcomes**: pares (sujeto screeningable ×
  fuente **solicitada**) que quedaron sin consulta ⇒ parcial. Una fuente caída
  deja la cobertura parcial aunque el resto responda.
- El motivo declara **las dos cosas**. Ejemplo verificado (ONU candidato, OFAC
  sin coincidencia, UK no disponible):
  *"Existe candidato que requiere revisión humana (ONU); una coincidencia por
  nombre no confirma una designación. Cobertura PARCIAL: UKSL no estuvo
  disponible."* con `status=SCREENING_REVIEW_REQUIRED`,
  `coverage_complete=False`, `sources_unavailable=('UK_SANCTIONS_LIST',)`.
- Nunca más `REVIEW_REQUIRED` + `coverage_complete=True` con algo sin consultar.
- `ScreeningSummary.cobertura_completa` se conserva como alias con la **nueva**
  derivación; los receipts y el capítulo 16 imprimen cobertura y evidencia.

## 4. Registros MULTI-IDENTIFICADOR

**Defecto**: se conservaba solo el primer documento (o el primero con un tipo
reconocido), perdiendo identificadores secundarios que sí pueden confirmar (o
descartar) una coincidencia.

**Corregido** — extensión backward-compatible de `RegistroNormalizado`:

```python
identifiers = ({"type", "value", "source_field"}, ...)
```

Los campos legacy `tipo_documento`/`numero_documento` se conservan y apuntan al
primer identificador (compatibilidad con todo lo anterior).

| fuente | identificadores que ahora se conservan |
|---|---|
| `UN_CONSOLIDATED` | todos los `INDIVIDUAL_DOCUMENT` / `ENTITY_DOCUMENT` (TYPE_OF_DOCUMENT + NUMBER) |
| `OFAC_SDN` | **todos** los `<id>` de `idList` (no solo el primero) |
| `UK_SANCTIONS_LIST` | todos los `PassportNumber`, `NationalIdentifierNumber`, `BusinessRegistrationNumber` e `IMONumber` del esquema |

Matcher: el paso de identificador exacto evalúa **todos** los identificadores del
registro con compatibilidad de tipos (cédula ≈ *national id*; pasaporte ≠
cédula; NIT ≈ *tax id*), y el conflicto del §19 solo se declara si **ninguno** es
compatible. El motivo cita el valor **crudo** de la fuente
(`documento=DOC-2 (normalizado DOC2, idList/id/idNumber)`).

Tests: multi-ID en los tres parsers (fixtures extendidos con DOC-1/2/3, dos
pasaportes y un *national identifier*, registros mercantiles y entidades);
sujeto con `DOC-2` → `EXACT_MATCH`; primer ID de tipo incompatible + segundo
exacto → `EXACT_MATCH` legítimo; mismo número con tipo incompatible (cédula vs
pasaporte) → NO confirma; y compatibilidad con registros legacy sin `identifiers`.

## 5. Variantes de nombre — sin búsqueda concatenada

`SubjectEnvelope` incorpora `declared_name_variants` y la propiedad
`nombres_a_consultar` (canónico + variantes). El motor consulta **cada nombre por
separado** contra cada fuente y agrega el resultado **más conservador**, con el
motivo etiquetado (`variante declarada 'MARVAL': …`).

- `URBANIZADORA MARIN VALENCIA / MARVAL` → 3 consultas (cadena declarada +
  `URBANIZADORA MARIN VALENCIA` + `MARVAL`).
- **No** se fusiona identidad jurídica por similitud: la advertencia
  `MULTIPLE_NAME_VARIANTS_NOT_FUSED` se mantiene y dos personas jurídicas con
  nombre parecido siguen siendo dos sujetos.
- Corrección colateral: un punto final ("BANCO DE BOGOTÁ S.A.") ya no genera una
  variante espuria (se compara por clave normalizada).
- Efecto real verificado en vivo: la variante `MARVAL` produce
  `REVIEW_REQUIRED` (similitud 0.833, franja de revisión) contra OFAC SDN — un
  candidato que la cadena concatenada **no** habría encontrado, y que se reporta
  como revisión, no como coincidencia.

## 6. Taxonomía menor

`PEP_COLOMBIA.category = CAT_PEP` (`"PEP_REGISTRY"`), no
`REGULATORY_REPORTING`; sigue `OUT_OF_SCOPE_FOR_SCREENING` en 03S.1A (no se
implementa PEP). `UIAF_SIREL` permanece como `REGULATORY_REPORTING`.

## 7. Tests

- `tests/test_remediacion_03s1a.py` (28 casos): frescura A/B/C, "nunca LIVE desde
  el store", dictamen sin fuentes en vivo; evidencia 9/9, cadena fallida visible,
  fail-closed en producción sin clave, `SEALED` con clave, `NOT_REQUIRED_DEV`
  explícito; cobertura parcial con candidato + fuente caída, cobertura completa
  sin pendientes, cobertura independiente del status, receipt con ambas
  dimensiones; multi-ID ONU/OFAC/UKSL, segundo identificador, tipo incompatible,
  legacy; variantes declaradas, no fusión de jurídicas, sin variante espuria; PEP
  y UIAF; 09.3/cobertura en el PDF.
- Fixtures oficiales sanitizados ampliados con múltiples identificadores.
- `python -m compileall api tests` → exit 0
- `python -m pytest -m "not network" tests/` → **523 passed, 0 failed,
  11 deselected** (línea base 496 → +27).

## 8. Prueba EN VIVO de dos fases (obligatoria) — ejecutada

`python scripts/screening_live_check.py --cache-dir <dir> --dos-fases`:

| fuente | fase 1 (`force_refresh`) | fase 2 (sin refresh) | registros | sha256 (16) |
|---|---|---|---|---|
| UN_CONSOLIDATED | **LIVE_FRESH** | **CACHED_FRESH** | 1011 | `e00d452dec23b46d` |
| OFAC_SDN | **LIVE_FRESH** | **CACHED_FRESH** | 19393 | `30c2a70887d694f7` |
| UK_SANCTIONS_LIST | **LIVE_FRESH** | **CACHED_FRESH** | 6339 | `50b83b8202daf366` |

`VEREDICTO DOS FASES: OK`. Y el screening completo del caso Golden contra las
listas reales (fase 2, desde snapshot): `SCREENING_REVIEW_REQUIRED` ·
`coverage_status=COVERAGE_COMPLETE` · 3 declarados / 3 screeningados / 0 no
screeningados · **evidencia 9/9 · cadena SEALED** · motivo con la decisión y la
cobertura; el único candidato es la variante declarada `MARVAL` contra OFAC SDN
(franja de revisión, 0.833).

## 9. Lo que NO se cerró (sin cambios respecto de 03S.1)

`OFAC_NON_SDN` declarado y no consultado (la cobertura lo dice: "OFAC — SDN (solo
SDN)"); `EU_CONSOLIDATED` opcional por archivo oficial; PEP avanzado, UE, SIREL,
World-Check/Refinitiv, Truora/TusDatos, Procuraduría/Contraloría/Policía y
automatización de ROS fuera de alcance; los numerales de la CBJ siguen sin
verificar contra el PDF oficial y no se imprimen.

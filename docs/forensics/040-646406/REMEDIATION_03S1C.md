# REMEDIATION 03S.1C — VERSIONED EXECUTION IDENTITY (FINAL FREEZE)

Baseline: 03S.1B implementado. Objetivo: que **dos ejecuciones capaces de producir
resultados distintos NUNCA compartan la misma identidad criptográfica de
consulta**. Sin ampliar alcance, sin cambiar reglas ni umbrales de matching y sin
tocar catastro/valoración (solo metadatos de evidencia en el PDF).

---

## 1. Versión del matcher

El matching cambió materialmente en 03S.1A (multi-identificador, variantes
declaradas) y en 03S.1B (mismo valor ≠ identificador compatible), pero seguía
declarando `sanctions-matcher/1.0` — incorrecto para reproducibilidad.

`ALGORITHM_VERSION = "sanctions-matcher/1.1.0"`. La evidencia histórica ya
emitida con 1.0 **no se modifica** (los envelopes guardados conservan su sello);
toda evidencia nueva registra 1.1.0.

## 2. Versión de los parsers

Los tres parsers conservan ahora multi-identificadores, así que su versión no
podía seguir representando la implementación antigua. Las versiones reales viven
en **un solo lugar** (`sanctions/parsers.py::PARSER_VERSIONS`) y el
`SourceRegistry` las consume con `parser_version(parser_id)`:

| parser | versión declarada |
|---|---|
| `onu_xml` | `onu_xml/1.1.0` |
| `ofac_sdn_xml` | `ofac_sdn_xml/1.1.0` |
| `uk_sanctions_list_xml` | `uk_sanctions_list_xml/1.1.0` |
| `uk_ofsi_legacy_xml` (histórico) | `uk_ofsi_legacy_xml/1.0.0` |

## 3. `query_hash` sella también el PARSER

```
query_hash = SHA256{
    screening_input_hash,
    subject_id,
    source_id,
    snapshot_sha256,
    parser_version,
    algorithm_version,
}
```

Mismo XML crudo (mismo `sha256`) procesado por un parser distinto produce una
representación normalizada potencialmente distinta y, por tanto, un resultado
potencialmente distinto: la versión del parser es parte de la identidad de la
consulta.

## 4. `screening_input_hash` (inputs efectivos del matcher)

Sustituye al uso exclusivo de `subject_hash` (que omite datos que afectan el
cotejo). Incluye **solo inputs materiales**:

- `canonical_match_key` (nombre normalizado que el matcher compara),
- `declared_name_variants` normalizadas (se consultan por separado),
- `document_type`, `document_normalized`,
- identificadores adicionales del sujeto (tipo + valor),
- `fecha_nacimiento` si alguna vez está disponible.

No incluye campos de presentación (nombre declarado crudo, participación,
provenance) porque no alteran el resultado. `subject_hash` se conserva como
identidad canónica del sujeto.

## 5/6. EvidenceRecord y evidence_hash

`EvidenceRecord` añade explícitamente `matcher_version`, `parser_version`,
`screening_input_hash` y `evidence_content_hash`, conservando `subject_hash`,
`snapshot_sha256`, `query_hash` y `evidence_hash`:

| hash | qué sella |
|---|---|
| `subject_hash` | identidad canónica del sujeto |
| `screening_input_hash` | inputs efectivos enviados al matcher |
| `snapshot_sha256` | bytes/versión de la lista oficial |
| `query_hash` | screening_input + snapshot + parser + matcher |
| `evidence_hash` | envelope completo (incluye el sello de tiempo) |
| `evidence_content_hash` | el mismo contenido **sin** el sello de tiempo |

`evidence_hash` cubre naturalmente las versiones, el input, el resultado, el
score, los IDs coincidentes y los motivos: cambiar cualquiera de ellos cambia el
sello (verificado por test para parser, matcher y snapshot).

## 7. Contrato de reproducibilidad ampliado

`evidence_reproducible = True` exige `evidence_complete` **y**, por cada
envelope, la identidad de ejecución completa: `subject_hash`,
`screening_input_hash`, `snapshot_sha256`, `parser_version`, `matcher_version`,
`query_hash` y `evidence_hash`. La presencia de los cuatro hashes antiguos ya no
basta (test explícito). Sigue sin exigir que la cadena esté sellada: en
`NOT_REQUIRED_DEV` la evidencia es reproducible pero NO sellada.

## 8-11. Tests bloqueantes

`tests/test_remediacion_03s1c.py` (16 casos):

| # | caso | resultado |
|---|---|---|
| 8 | mismo sujeto/snapshot/parser, matcher 1.0 vs 1.1 | `query_hash` distinto |
| 9 | mismo sujeto y sha, parser 1.0 vs 1.1 | `query_hash` distinto |
| 10 | misma `canonical_name`, variantes `()` vs `("URBANIZADORA MARIN VALENCIA","MARVAL")` | `screening_input_hash` y `query_hash` distintos |
| 11 | mismos inputs dos veces | `screening_input_hash`/`query_hash` idénticos; `evidence_content_hash` idéntico |

**Decisión documentada (§11)**: `evidence_hash` **incluye** el sello de tiempo de
la consulta, así que puede variar entre ejecuciones equivalentes; para
reproducibilidad binaria se añade `evidence_content_hash`, que sella exactamente
el mismo contenido sin `screened_at`. Test explícito: dos ejecuciones a 1 segundo
de distancia comparten `evidence_content_hash` y difieren en `evidence_hash`.

Extras: versiones declaradas == implementación real; el snapshot declara la
versión del parser usado; los identificadores (tipo/valor) cambian el input;
`subject_hash` no sustituye al input (mismo `subject_hash` con variantes distintas
→ inputs distintos); el evidence_hash cambia con parser/matcher/snapshot.

## 12. El parser viaja desde el SNAPSHOT

`SourceOutcome.parser_version` se toma del snapshot que produjo los registros y
`build_evidence` lo consume desde el outcome. **No** se infiere después del
registry: para reproducir evidencia histórica importa el parser usado en aquel
momento. Test: un snapshot sembrado con `onu_xml/0.9.0-hist` se conserva tal cual
en el outcome y en el envelope, sin ser sobrescrito por la versión vigente.

## 13. Golden live check

Ejecución en vivo de UN/OFAC/UKSL y verificación de la identidad versionada en los
evidence records del Golden (ver más abajo, sección de resultados). El outcome del
caso **no** se alteró: la variante declarada `MARVAL` sigue produciendo
`REVIEW_REQUIRED` contra OFAC SDN (franja de revisión). No se cambió nada para
conseguir otro Golden.

Metadatos de evidencia añadidos al dictamen (permitido por el alcance): en 09.2 la
celda de cada fuente declara ahora `parser <versión>`; en 09.3 se añaden "Versión
del matcher" y "Versión del parser por fuente". El receipt técnico (16.B) expone
`matcher_version` y `parser_versions` por fuente.

## 14. Regresión

- `python -m compileall api tests` → exit 0
- `python -m pytest -m "not network" tests/` → **556 passed, 0 failed,
  11 deselected** (línea base 540 → +16)

## Alcance respetado

Sin cambios en reglas ni umbrales de matching, sin PEP/UE/SIREL, sin tocar
catastro ni valoración. El único cambio de PDF son metadatos de evidencia
(versiones y contrato de reproducibilidad). No se inició SLICE-002.

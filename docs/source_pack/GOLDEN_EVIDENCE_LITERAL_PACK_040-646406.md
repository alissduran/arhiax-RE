# GOLDEN EVIDENCE LITERAL PACK — folio 040-646406

**Artefactos:** `docs/forensics/040-646406/dictus_2b/` · **Pack generado por:**
`scripts/golden_evidence_pack.py` (solo lectura sobre `docs/forensics/**`).

- `master_hash` = `c804dc02b223c9be905f9e3103ffa54f355b7aba2986759af2ca470c7f7eee71`
- `sha256_ejecutivo` = `4960b12a08f5b447c6cc364b5aee7bfeb905ccd5ce0d8421f8e1a92955908c6c`
- `sha256_tecnico` = `f480e4d78947f7908198421f478de6f71cf9928011f066e8973e436b439ed80e`
- `run_id` = `16019df2-a4fd-44db-860f-e50a5cdd3c2f` · `generated_at` = `2026-09-30T14:47:40.937950+00:00`
- `commit_sha` = `c22b1b9df6ee734101150aae0751203d2ff71ee9`

> **ESTADO DE ESTE PACK:** el Golden de `docs/forensics/040-646406/dictus_2b/` fue
> REGENERADO por `python scripts/dictus_run.py` en esta tarea, y este pack se
> construye con los artefactos de ESA corrida. Los tres criterios que antes salían
> FAIL se resolvieron (A · `gate_state`; B · origen del hecho VERIFICADO; C ·
> contradicción entre páginas) y las secciones §9, §10 y §11 son su evidencia
> literal. Ningún criterio se maquilla: lo que sigue en FAIL se imprime como FAIL.

## 1. Market input

**A) Ruta del archivo:** `motor_tma_lonja_baq_v1.0\motor_tma_lonja_baq_v1.0\lonja_layer\lonja_baq_metodologia.yaml`

**B) Líneas exactas**

```yaml
lonja_baq_metodologia.yaml:14: # y se propaga automáticamente a todos los dictámenes posteriores a la fecha
lonja_baq_metodologia.yaml:15: # de vigencia declarada.
lonja_baq_metodologia.yaml:16: # ═══════════════════════════════════════════════════════════════════════════════
lonja_baq_metodologia.yaml:17: 
lonja_baq_metodologia.yaml:18: declaracion:
lonja_baq_metodologia.yaml:19:   entidad: "Lonja de Propiedad Raíz de Barranquilla"
lonja_baq_metodologia.yaml:20:   representante_legal: "[A declarar por la Lonja]"
lonja_baq_metodologia.yaml:21:   presidente_comite_tecnico: "[A declarar por la Lonja]"
lonja_baq_metodologia.yaml:22:   vigencia_desde: "2026-05-08"
lonja_baq_metodologia.yaml:23:   vigencia_hasta: "2026-08-31"
lonja_baq_metodologia.yaml:24:   marco_normativo:
lonja_baq_metodologia.yaml:25:     - "Ley 1673 de 2013 — Régimen del avaluador"
lonja_baq_metodologia.yaml:208:   Miramar:
lonja_baq_metodologia.yaml:209:     # Actualizado Q3-2026 con precio real de mercado verificado por el
lonja_baq_metodologia.yaml:210:     # propietario en la constructora del proyecto (unidades ~58 m2 terminadas
lonja_baq_metodologia.yaml:211:     # en venta ~$420.000.000 ≈ $7.1M/m2). El valor anterior ($4.5M/m2, Q2-2026)
lonja_baq_metodologia.yaml:212:     # quedaba ~40% por debajo del mercado observado y el dictamen del folio real
lonja_baq_metodologia.yaml:213:     # 040-646406 (Napoli, Torre 8 apto 430) subestimaba el inmueble.
lonja_baq_metodologia.yaml:214:     valor_central_m2: 6800000
lonja_baq_metodologia.yaml:215:     rango_min_m2: 5500000
lonja_baq_metodologia.yaml:216:     rango_max_m2: 8000000
lonja_baq_metodologia.yaml:217:     vigencia: "Q3-2026"
lonja_baq_metodologia.yaml:218:     fuente: "Precio de venta verificado en la constructora del proyecto (unidades ~58 m2 terminadas, 2026) + Lonja BAQ referencial"
lonja_baq_metodologia.yaml:219:   Riomar:
lonja_baq_metodologia.yaml:207: valor_suelo_por_sector:
```

**C) Estructura resultante** (del `market_context.sector_metodologico` real)

```json
{
  "input_barrio": "Miramar",
  "matched_sector": "Miramar",
  "match_type": "EXACT",
  "value_m2": 6800000,
  "rango_min_m2": 5500000,
  "rango_max_m2": 8000000,
  "methodology_file": "lonja_baq_metodologia.yaml",
  "methodology_version": "0.1-codiseno",
  "methodology_sha256": "4ccd5832eacf3117424fa436765e80d3e9198b666d9e3c293063a5b207ebd348"
}
```

**D) `origin`** — clasificado con el código NUEVO (`api/atribucion_mercado.py:198`)

```json
{
  "origin": "MANUAL_CONFIG",
  "origin_declarado": null,
  "origin_gate": false,
  "origin_blockers": [
    "origen no declarado por el artefacto: se clasifica MANUAL_CONFIG (no habilita la valoración)"
  ],
  "origin_provenance": {},
  "origin_etiqueta": "valor declarado a mano por la corrida (sin fuente externa automática)"
}
```

**E) `provenance`**

```json
{
  "market_rate_source": "Precio de venta verificado en la constructora del proyecto (unidades ~58 m2 terminadas, 2026) — parámetros declarados por la corrida (sin fuente externa automática verificada)",
  "methodology_version": "0.1-codiseno",
  "market_methodology_id": "lonja_baq_metodologia",
  "market_methodology_version": "0.1-codiseno",
  "market_methodology_sha256": "4ccd5832eacf3117424fa436765e80d3e9198b666d9e3c293063a5b207ebd348",
  "methodology_entity": "artefacto local de metodología (sin institución proveedora verificada)",
  "origin": "MANUAL_CONFIG",
  "origin_declarado": null,
  "origin_gate": false
}
```

**F) `authorized_for_valuation`**

```json
{
  "golden_stored_valoracion_habilitada": false,
  "golden_stored_status": "UNRESOLVED",
  "nuevo_codigo_status": false
}
```

**Formato pedido:**

```json
{
  "market_rate": {
    "value": 6800000,
    "origin": "MANUAL_CONFIG",
    "provenance": {
      "market_rate_source": "Precio de venta verificado en la constructora del proyecto (unidades ~58 m2 terminadas, 2026) — parámetros declarados por la corrida (sin fuente externa automática verificada)",
      "methodology_version": "0.1-codiseno",
      "market_methodology_id": "lonja_baq_metodologia",
      "market_methodology_version": "0.1-codiseno",
      "market_methodology_sha256": "4ccd5832eacf3117424fa436765e80d3e9198b666d9e3c293063a5b207ebd348",
      "methodology_entity": "artefacto local de metodología (sin institución proveedora verificada)",
      "origin": "MANUAL_CONFIG",
      "origin_declarado": null,
      "origin_gate": false
    },
    "authorized_for_valuation": false
  }
}
```

**El input NO es una fuente externa automática.** Origen efectivo = `MANUAL_CONFIG` (MANUAL_CONFIG: valor escrito a mano en un artefacto local). `authorized_for_valuation` = `False`. La etiqueta honesta que el
producto declara es:

```json
{
  "es_fuente_de_datos": false,
  "aporta_datos_a_dictus": false,
  "en_source_registry": false,
  "fuente_externa_verificable": false,
  "etiqueta": "parámetros declarados por la corrida",
  "nota": "El valor de mercado es parámetros declarados por la corrida (artefacto local de metodología): sin fuente externa automática verificada. La Lonja no es una fuente de datos y no se sustituye por ninguna fuente inventada."
}
```

## 2. MarketContext final

```json
{
  "status": "UNRESOLVED",
  "resolution_status": "UNRESOLVED",
  "selected_source": "Precio de venta verificado en la constructora del proyecto (unidades ~58 m2 terminadas, 2026) — parámetros declarados por la corrida (sin fuente externa automática verificada)",
  "origin": "MANUAL_CONFIG",
  "provenance": {
    "market_rate_source": "Precio de venta verificado en la constructora del proyecto (unidades ~58 m2 terminadas, 2026) — parámetros declarados por la corrida (sin fuente externa automática verificada)",
    "methodology_version": "0.1-codiseno",
    "market_methodology_id": "lonja_baq_metodologia",
    "market_methodology_version": "0.1-codiseno",
    "market_methodology_sha256": "4ccd5832eacf3117424fa436765e80d3e9198b666d9e3c293063a5b207ebd348",
    "methodology_entity": "artefacto local de metodología (sin institución proveedora verificada)",
    "origin": "MANUAL_CONFIG",
    "origin_declarado": null,
    "origin_gate": false
  },
  "required_inputs": [
    "identity_verified",
    "barrio VERIFIED_OFFICIAL/GEOGRAPHIC",
    "estrato VERIFIED_OFFICIAL",
    "tipologia VERIFIED_REGISTRAL/CATASTRAL",
    "sector metodológico resuelto",
    "market_rate_source",
    "market_methodology_id/version",
    "value_m2 > 0"
  ],
  "blockers": [],
  "authorized": false,
  "reason": "MARKET_CONTEXT_UNRESOLVED: origen no declarado por el artefacto: se clasifica MANUAL_CONFIG (no habilita la valoración)"
}
```

**Lo que el Golden tiene GUARDADO:**

```json
{
  "status": "UNRESOLVED",
  "origin": "MANUAL_CONFIG",
  "origin_gate": false,
  "valoracion_habilitada": false,
  "ready": true
}
```

**Lo que el código NUEVO dice del MISMO market_context del Golden:**

```json
{
  "origin": "MANUAL_CONFIG",
  "origin_declarado": null,
  "origin_gate": false,
  "origin_blockers": [
    "origen no declarado por el artefacto: se clasifica MANUAL_CONFIG (no habilita la valoración)"
  ],
  "origin_provenance": {},
  "origin_etiqueta": "valor declarado a mano por la corrida (sin fuente externa automática)"
}
```

El contexto de mercado de la corrida queda `status=UNRESOLVED`, `authorized=False`, `reason=MARKET_CONTEXT_UNRESOLVED: origen no declarado por el artefacto: se clasifica MANUAL_CONFIG (no habilita la valoración)`: el input de mercado es `MANUAL_CONFIG` y **no habilita** la valoración.

## 3. ValuationGate completo

**JSON completo (literal del manifest, `modelo.decision_gates[VALUATION_GATE]`):**

```json
{
  "gate": "VALUATION_GATE",
  "inputs": [
    "autorización de identidad",
    "autorización de contexto de mercado",
    "método y vigencia"
  ],
  "observation_ids": [
    "OBS-VALUATION-78067"
  ],
  "observations": [
    {
      "observation_id": "OBS-VALUATION-78067",
      "domain": "VALUATION",
      "subject": "Valor estimado y su banda",
      "source": "parámetros de mercado declarados por la corrida",
      "status": "NOT_EVALUATED",
      "value": {
        "consolidado": 0,
        "banda_baja": 0,
        "banda_alta": 0,
        "value_m2": null,
        "origin": "MANUAL_CONFIG",
        "origin_gate": false
      },
      "detail": "no hay fuente de mercado que sostenga la cifra: la tasa de esta corrida proviene de parámetros declarados a mano (origin=MANUAL_CONFIG: valor declarado a mano por la corrida (sin fuente externa automática)), sin procedencia externa verificable",
      "observed_at": "2026-09-30T14:47:40.937950+00:00",
      "query": null,
      "evidence_refs": [
        {
          "evidence_id": "EV-VALOR",
          "type": "VALUATION",
          "source": "metodología de mercado",
          "timestamp": "2026-09-30T14:47:40.937950+00:00",
          "sha256": null,
          "detail": null
        }
      ],
      "methodology_id": "lonja_baq_metodologia",
      "origin": "MANUAL_CONFIG",
      "origin_gate": false
    }
  ],
  "blocking_conditions": [
    "no hay fuente de mercado que sostenga la cifra: la tasa de esta corrida proviene de parámetros declarados a mano (origin=MANUAL_CONFIG: valor declarado a mano por la corrida (sin fuente externa automática)), sin procedencia externa verificable"
  ],
  "decision": "NO EMITIR VALORACIÓN",
  "gate_state": "CLOSED",
  "reasons": [
    "La valoración NO está autorizada en esta corrida: el origen de la tasa es MANUAL_CONFIG y su procedencia es INSUFICIENTE para autorizar una cifra (se exige fuente externa citada o cálculo de fuentes citadas, con fecha y sha256). No se emite cifra y se declaran los bloqueos reales."
  ],
  "evidence_refs": [
    {
      "evidence_id": "EV-VALOR",
      "type": "VALUATION",
      "source": "metodología de mercado",
      "timestamp": "2026-09-30T14:47:40.937950+00:00",
      "sha256": null,
      "detail": null
    }
  ]
}
```

**Vista normalizada con los campos pedidos:**

```json
{
  "gate": "VALUATION_GATE",
  "gate_state": "CLOSED",
  "gate_state_vocabulario": [
    "CLOSED",
    "OPEN"
  ],
  "decision": "NO EMITIR VALORACIÓN",
  "reason": "La valoración NO está autorizada en esta corrida: el origen de la tasa es MANUAL_CONFIG y su procedencia es INSUFICIENTE para autorizar una cifra (se exige fuente externa citada o cálculo de fuentes citadas, con fecha y sha256). No se emite cifra y se declaran los bloqueos reales.",
  "required_inputs": [
    "autorización de identidad",
    "autorización de contexto de mercado",
    "método y vigencia"
  ],
  "blocking_conditions": [
    "no hay fuente de mercado que sostenga la cifra: la tasa de esta corrida proviene de parámetros declarados a mano (origin=MANUAL_CONFIG: valor declarado a mano por la corrida (sin fuente externa automática)), sin procedencia externa verificable"
  ],
  "evidence_refs": [
    {
      "evidence_id": "EV-VALOR",
      "type": "VALUATION",
      "source": "metodología de mercado",
      "timestamp": "2026-09-30T14:47:40.937950+00:00",
      "sha256": null,
      "detail": null
    }
  ],
  "origin_summary": "MANUAL_CONFIG",
  "authorized_inputs": null,
  "rejected_inputs": null,
  "observations": [
    {
      "observation_id": "OBS-VALUATION-78067",
      "domain": "VALUATION",
      "subject": "Valor estimado y su banda",
      "source": "parámetros de mercado declarados por la corrida",
      "status": "NOT_EVALUATED",
      "value": {
        "consolidado": 0,
        "banda_baja": 0,
        "banda_alta": 0,
        "value_m2": null,
        "origin": "MANUAL_CONFIG",
        "origin_gate": false
      },
      "detail": "no hay fuente de mercado que sostenga la cifra: la tasa de esta corrida proviene de parámetros declarados a mano (origin=MANUAL_CONFIG: valor declarado a mano por la corrida (sin fuente externa automática)), sin procedencia externa verificable",
      "observed_at": "2026-09-30T14:47:40.937950+00:00",
      "query": null,
      "evidence_refs": [
        {
          "evidence_id": "EV-VALOR",
          "type": "VALUATION",
          "source": "metodología de mercado",
          "timestamp": "2026-09-30T14:47:40.937950+00:00",
          "sha256": null,
          "detail": null
        }
      ],
      "methodology_id": "lonja_baq_metodologia",
      "origin": "MANUAL_CONFIG",
      "origin_gate": false
    }
  ],
  "todos_los_gates": [
    {
      "gate": "IDENTITY_GATE",
      "gate_state": "OPEN",
      "decision": "INFORMACIÓN VERIFICADA"
    },
    {
      "gate": "TITLE_GATE",
      "gate_state": "OPEN",
      "decision": "PROCEDER CON CONDICIONES"
    },
    {
      "gate": "COUNTERPARTY_GATE",
      "gate_state": "OPEN",
      "decision": "SIN HALLAZGO MATERIAL EN ESTA FUENTE"
    },
    {
      "gate": "URBAN_GATE",
      "gate_state": "CLOSED",
      "decision": "NO UTILIZAR ESTE DATO COMO DEFINITIVO"
    },
    {
      "gate": "ENVIRONMENT_GATE",
      "gate_state": "CLOSED",
      "decision": "INFORMACIÓN INSUFICIENTE"
    },
    {
      "gate": "VALUATION_GATE",
      "gate_state": "CLOSED",
      "decision": "NO EMITIR VALORACIÓN"
    },
    {
      "gate": "EVIDENCE_GATE",
      "gate_state": "OPEN",
      "decision": "INFORMACIÓN VERIFICADA"
    }
  ]
}
```

**Qué demuestra (y qué NO):**

- ✅ **`gate_state` y `decision` CONVIVEN** (A): el vocabulario CERRADO es ['CLOSED', 'OPEN']. Este gate está `gate_state = CLOSED` y a la vez `decision = 'NO EMITIR VALORACIÓN'` (el término de la gramática de decisión). El checklist que exige `CLOSED` NO obliga a mutilar el término de la decisión.
- ✅ El **`reason` nombra la CAUSA** (B): `'La valoración NO está autorizada en esta corrida: el origen de la tasa es MANUAL_CONFIG y su procedencia es INSUFICIENTE para autorizar una cifra (se exige fuente externa citada o cálculo de fuentes citadas, con fecha y sha256). No se emite cifra y se declaran los bloqueos reales.'`.
- ❌ El **rate manual NO autoriza**: `origin = MANUAL_CONFIG` · `origin_gate = False` · `authorized = False` · causa = `MARKET_CONTEXT_UNRESOLVED: origen no declarado por el artefacto: se clasifica MANUAL_CONFIG (no habilita la valoración)`.
- ✅ Un origen habilitante **sin procedencia completa** se DEGRADA a `MANUAL_CONFIG` (`api/atribucion_mercado.clasificar_origen`): no hay clase habilitante sin `fuentes[]` con proveedor, fecha, referencia y sha256.
- La `observations[0].source` con la que el gate sostiene la cifra es `'parámetros de mercado declarados por la corrida'` — es decir, el artefacto local, no una fuente externa.

**Los SIETE gates de la corrida, con sus dos campos:**

| gate | gate_state | decision |
|---|---|---|
| `IDENTITY_GATE` | **OPEN** | INFORMACIÓN VERIFICADA |
| `TITLE_GATE` | **OPEN** | PROCEDER CON CONDICIONES |
| `COUNTERPARTY_GATE` | **OPEN** | SIN HALLAZGO MATERIAL EN ESTA FUENTE |
| `URBAN_GATE` | **CLOSED** | NO UTILIZAR ESTE DATO COMO DEFINITIVO |
| `ENVIRONMENT_GATE` | **CLOSED** | INFORMACIÓN INSUFICIENTE |
| `VALUATION_GATE` | **CLOSED** | NO EMITIR VALORACIÓN |
| `EVIDENCE_GATE` | **OPEN** | INFORMACIÓN VERIFICADA |

## 4. Origin propagation

**Regla literal** — `api/atribucion_mercado.py:198`:

```python
def clasificar_origen(declaracion: Optional[dict], *,
                      por_defecto: str = ORIGEN_MANUAL) -> dict:
    ...
    if declarado not in ORIGENES:
        efectivo = por_defecto
        blockers.append(f"origen no declarado por el artefacto: se clasifica "
                        f"{efectivo} (no habilita la valoración)")
    elif declarado in ORIGENES_HABILITANTES:
        ...  # sin procedencia completa -> se degrada
    else:
        efectivo = declarado
        blockers.append(f"origen {efectivo} no habilita la valoración ...")
    gate = efectivo in ORIGENES_HABILITANTES and not blockers
```

**Vocabulario (5 valores, `api/atribucion_mercado.py:124-135`):**

```json
{
  "ORIGEN_EXTERNO": "EXTERNAL_SOURCE",
  "ORIGEN_COMPUTADO": "COMPUTED_FROM_SOURCES",
  "ORIGEN_MANUAL": "MANUAL_CONFIG",
  "ORIGEN_ESTATICO": "STATIC_REFERENCE",
  "ORIGEN_PRIOR": "MODEL_PRIOR",
  "ORIGENES": [
    "EXTERNAL_SOURCE",
    "COMPUTED_FROM_SOURCES",
    "MANUAL_CONFIG",
    "STATIC_REFERENCE",
    "MODEL_PRIOR"
  ],
  "ORIGENES_HABILITANTES": [
    "COMPUTED_FROM_SOURCES",
    "EXTERNAL_SOURCE"
  ],
  "PROCEDENCIA_EXTERNA": [
    "source_id",
    "proveedor",
    "fecha",
    "referencia",
    "sha256"
  ],
  "PROCEDENCIA_COMPUTADA_CAMPOS": [
    "proveedor",
    "fecha",
    "referencia",
    "sha256"
  ],
  "PROCEDENCIA_COMPUTADA_MIN_FUENTES": 2
}
```

**Las tres reglas pedidas, ejecutadas contra el código real:**

- **EXTERNAL_SOURCE+EXTERNAL_SOURCE→COMPUTED_FROM_SOURCES** → `origin = COMPUTED_FROM_SOURCES` · `origin_gate = True` · blockers = []
- **EXTERNAL+MANUAL_CONFIG→MANUAL_CONFIG (NOT_AUTHORIZED)** → `origin = MANUAL_CONFIG` · `origin_gate = False` · blockers = ['origen MANUAL_CONFIG no habilita la valoración (valor declarado a mano por la corrida (sin fuente externa automática))']
- **EXTERNAL+MODEL_PRIOR→MODEL_PRIOR (NOT_AUTHORIZED)** → `origin = MODEL_PRIOR` · `origin_gate = False` · blockers = ['origen MODEL_PRIOR no habilita la valoración (valor por defecto del modelo (sin fuente: no autoriza cifra))']
- **STATIC_REFERENCE→no habilita** → `origin = STATIC_REFERENCE` · `origin_gate = False` · blockers = ['origen STATIC_REFERENCE no habilita la valoración (referencia estática (no es una medición de la corrida))']
- **sin origen declarado→MANUAL_CONFIG por defecto** → `origin = MANUAL_CONFIG` · `origin_gate = False` · blockers = ['origen no declarado por el artefacto: se clasifica MANUAL_CONFIG (no habilita la valoración)']

**Tests versionados que cubren `clasificar_origen`:** **NINGUNO** (no existe test que importe ni ejercite `clasificar_origen`)

## 5. P1 literal

**Comando:** `python -c "from pypdf import PdfReader; print(PdfReader('docs/forensics/040-646406/dictus_2b/DICTUS_EJECUTIVO_040-646406.pdf').pages[0].extract_text())"`

```text

DICTUS
DECISIÓN DEL INMUEBLE
DX-040-646406-20260930
Página 1 de 6 · ejecutivo
DECISIÓN DEL INMUEBLE
TV 43 # 100 - 50 CONJUNTO RESIDENCIAL NAPOLI APARTAMENTOS ETAPA 3 APARTAMENTO 430 TORRE 8 E…
bloque a · identidad del inmueble
INFORMACIÓN GENERAL
DIRECCIÓN
TV 43 # 100 - 50 CONJUNTO RESIDENC…
MATRÍCULA
040-646406
CIUDAD
Barranquilla
BARRIO
Miramar
ÁREA
58.75 m²
USO
Habitacional
RÉGIMEN
Propiedad Horizontal
VALOR ESTIMADO
no disponible (valoración no autorizada)
identidad · títulos · contrapartes · territorio · entorno · valoración
ESTADO POR DOMINIO
IDENTIDAD
VERIFICADO
TÍTULOS
CON CONDICIONES
CONTRAPARTES
SIN COINCIDENCIAS
TERRITORIO
REQUIERE VALIDACIÓN
VALOR
NO DISPONIBLE
conflictos entre versiones del expediente
COHERENCIA DE LA INFORMACIÓN
COHERENCIA DE INFORMACIÓN — 6 atributo(s) requieren reconciliación histórica
AFECTA A: COMPRADOR, INMOBILIARIA, BANCO / FINANCIADOR, ASEGURADORA DE TÍTULO
Detalle por atributo: página 4 →
El expediente del mismo inmueble produjo valores distintos entre versiones. No es un riesgo del inmueble: es calidad de la información.
· Altura / edificabilidad: 8 / 11
· Amenaza por remoción en masa: Sin afectacion / AMENAZA BAJA
· Coordenada del predio: 10.9870 -74.8115 / 11.00538 -74.83862
· Titularidad: Duran Bacca Alisso / DURAN BACCA ALISSO
· Tratamiento urbanístico: CONSOLIDACION URBA / CONSOLIDACION -- N
· Uso del suelo (POT): ACTIVIDAD CENTRAL  / ACTIVIDAD URBANA R
qué encontró DICTUS · qué decisión produce · a quién afecta · qué hacer
DECISION BOARD
TEMA
HALLAZGO · QUÉ ENCONTRÓ DICTUS
DECISIÓN DICTUS
TÍTULO
ALTO · El folio registra una HIPOTECA VIGENTE inscrita el 22-01-2024 (anot. 007…
PROCEDER CON CONDICIONES
AFECTA A: COMPRADOR, VENDEDOR, INMOBILIARIA, BANCO / FINANCIADOR
ACCIÓN: Para vender, refinanciar o dar este inmueble en garantia, primero hay que gestionar el credito con BANCO DE BOGOTA S.A y tramitar la CANCELACION de la hipoteca ante la O…
+1 hallazgo(s) del mismo tema con su propia acción: página 2.
ENTORNO Y RIESGOS
MEDIO · Media · polígono: intersecta el predio
PROCEDER CON CONDICIONES
AFECTA A: COMPRADOR, VENDEDOR, INMOBILIARIA, BANCO / FINANCIADOR
ACCIÓN: Afectacion presente declarada por la fuente oficial: se recomienda verificacion puntual por profesional competente en caso de intervencion fisica del predio; impacto esperado men…
POT / CALIDAD DE DATOS
6 atributo(s) con resultados incompatibles entre versiones del expediente
NO UTILIZAR ESTE DATO COMO DEFINITIVO
AFECTA A: COMPRADOR, INMOBILIARIA, BANCO / FINANCIADOR, ASEGURADORA DE TÍTULO
ACCIÓN: Reconciliar con la ficha/polígono POT aplicable antes de usar la cifra.
DISPOSICIÓN GLOBAL: PROCEDER CON CONDICIONES IDENTIFICADAS · VALUATION_GATE: La valoración NO está autorizada en esta
corrida: el origen de la tasa es MANUAL_CONFIG y su procedencia es INSUFICIENTE para autorizar una cifra (se exige fuente externa citada
o cálculo de fuentes citadas, con fecha y sha256). No se emite cifra y se declaran los bloqueos reales. · Cobertura parcial declarada —
ENVIRONMENT_GATE: Inundación: sin dato de fuente
SELLO GLOBAL
DICTUS ID
DX-040-646406-20260930
Fecha: 2026-09-30
Evidencias: 10 · Estado: PARCIAL_CON_DECLARACIONES
Cadena de custodia del expediente: Anexo G.
DICTUS_MASTER_HASH
c804dc02b223c9be905f9e
…3103ffa54f355b7aba2986
Verificación: DICTUS ID + hash
maestro abreviado. El hash del archivo
PDF consta aparte (Anexo G).
DICTUS_MASTER_HASH C804DC02B223…EE71
Evidencias 10 · sello PARCIAL_CON_DECLARACIONES · verificación por DICTUS ID (Anexo G)
El hash del archivo PDF no es el hash maestro: consta en el anexo G.
```

**Asserts (contados sobre el texto real de P1):**

- `'399.500.000' not in p1` → **PASS** — 0 ocurrencia(s)
- `'$399' not in p1` → **PASS** — 0 ocurrencia(s)
- `'Lonja' not in p1` → **PASS** — 0 ocurrencia(s)
- `'no disponible (valoración no autorizada)' in p1` → **PASS**

## 6. P6 literal

**Comando:** idéntico al de §5 con `.pages[5]`.

```text

DICTUS
IDENTIDAD, MERCADO Y VALOR
DX-040-646406-20260930
Página 6 de 6 · ejecutivo
lo que se verificó y cuánto vale
IDENTIDAD, MERCADO Y VALOR
registral y catastral
IDENTIDAD DEL INMUEBLE
Dirección oficial
TV 43 # 100 - 50 CONJUNTO
RESIDENCIAL NAPOLI APARTAMENTOS
ETAPA 3 APARTAMENTO 430 TORRE 8
ETAPA 3 · Torre 8 · Apartamento 430
REQUIERE VALIDACIÓN
Matrícula
040-646406
VERIFICADO
NUPRE
AFT0005BOHA
REQUIERE VALIDACIÓN
Número predial
080010103000010040001908040002
REQUIERE VALIDACIÓN
Unidad (torre / apartamento)
APARTAMENTO 430 TORRE 8
REQUIERE VALIDACIÓN
Área
58.75 m²
REQUIERE VALIDACIÓN
Régimen jurídico
Propiedad Horizontal
REQUIERE VALIDACIÓN
Uso (destino catastral)
Habitacional
REQUIERE VALIDACIÓN
Tipología
Unidad En Propiedad Horizontal
REQUIERE VALIDACIÓN
Identidad registral y catastral: VERIFICADA
Matrícula, NUPRE y número predial resueltos y ligados entre sí (nupre).
DECISIÓN DICTUS: INFORMACIÓN VERIFICADA
Binding de la geometría oficial: VERIFICADA
La geometría oficial del predio coincide con la identidad canónica (nupre, numero_predial). Geometría oficial del PREDIO (lote/edificio):
NO acredita la posición del apartamento dentro de la edificación. Fuente: OFFICIAL_PREDIO.
qué falta para habilitar la valoración · no se imprime ningún monto, ni $0
VALOR ESTIMADO
NO DISPONIBLE
VALORACIÓN NO DISPONIBLE
DECISIÓN DICTUS: NO EMITIR VALORACIÓN · COMPUERTA CLOSED
no hay fuente de mercado que sostenga la cifra: la tasa de esta corrida proviene de parámetros declarados a mano (origin=MANUAL_CONFIG: valor declarado a mano por la corrida (sin fuente externa automática)), sin procedencia externa verificable
Origen de la tasa declarada: valor declarado a mano por la corrida (sin fuente externa automática) (MANUAL_CONFIG) · NO HABILITA VALORACIÓN
La valoración NO está autorizada en esta corrida: el origen de la tasa es MANUAL_CONFIG y su procedencia es INSUFICIENTE para autorizar una cifra (se…
· origen no declarado por el artefacto: se clasifica MANUAL_CONFIG (no habilita la valoración)
· no hay fuente de mercado que sostenga la cifra: la tasa de esta corrida proviene de parámetros declarados a mano (origin=MANUAL_CONFIG: valor declarado a mano por la corrida (sin fuente externa automática)), sin procedencia externa verificable
Metodología: norma + concepto técnico + validación profesional · detalle completo en el informe técnico.
TRAZABILIDAD · Fuentes: Parámetros de mercado declarados por la corrida · Catastro · Identidad canónica · Consulta: 2026-09-30
DICTUS_MASTER_HASH C804DC02B223…EE71
Evidencias 10 · sello PARCIAL_CON_DECLARACIONES · verificación por DICTUS ID (Anexo G)
El hash del archivo PDF no es el hash maestro: consta en el anexo G.
```

**Asserts (contados sobre el texto real de P6):**

- `'399.500.000' not in p6` → **PASS** — 0 ocurrencia(s)
- `'$399' not in p6` → **PASS**
- `'Lonja' not in p6` → **PASS**

**Estado de identidad:** `Identidad registral y catastral: VERIFICADA` · `Binding de la geometría oficial: VERIFICADA` (atributo `binding_geometria`, DISTINTO del valor de la coordenada que se rotula en P4).
**VALUATION_GATE impreso:** `DECISIÓN DICTUS: NO EMITIR VALORACIÓN · COMPUERTA CLOSED` (los dos campos, en la misma línea).
**Bloque de valor:** se titula `qué falta para habilitar la valoración · no se imprime ningún monto, ni $0`.
**Condiciones materiales impresas:** 2 (el resto se declara como «+ N condición(es) adicional(es)» y viaja completo en el modelo, el manifest y el informe técnico).

## 7. Hashes

```json
{
  "DICTUS_MASTER_HASH": "c804dc02b223c9be905f9e3103ffa54f355b7aba2986759af2ca470c7f7eee71",
  "DICTUS_MASTER_HASH_abreviado": "C804DC02B223…EE71",
  "sha256_ejecutivo": "4960b12a08f5b447c6cc364b5aee7bfeb905ccd5ce0d8421f8e1a92955908c6c",
  "sha256_tecnico": "f480e4d78947f7908198421f478de6f71cf9928011f066e8973e436b439ed80e",
  "run_id": "16019df2-a4fd-44db-860f-e50a5cdd3c2f",
  "generated_at": "2026-09-30T14:47:40.937950+00:00",
  "commit_sha": "c22b1b9df6ee734101150aae0751203d2ff71ee9",
  "commit_sha_del_run": "c22b1b9df6ee734101150aae0751203d2ff71ee9",
  "old_master_hash": "1843ec22d0d3a1cb2e63881dcbabc5f0ec1d977a0de5f2b3da3e503005aea865",
  "new_master_hash": "c804dc02b223c9be905f9e3103ffa54f355b7aba2986759af2ca470c7f7eee71",
  "changed": true,
  "old_sha256_ejecutivo": "7223d0c09f809896d36481ba443037845308b8024eec4233581036009c0d3a32",
  "new_sha256_ejecutivo": "4960b12a08f5b447c6cc364b5aee7bfeb905ccd5ce0d8421f8e1a92955908c6c",
  "sha256_ejecutivo_changed": true,
  "old_sha256_tecnico": "33265085a0b154d4f44587f55d890af7baa7696d0cb63b7dfcc4229595ad0bac",
  "new_sha256_tecnico": "f480e4d78947f7908198421f478de6f71cf9928011f066e8973e436b439ed80e",
  "sha256_tecnico_changed": true,
  "origen_de_los_sha256_old": "medido con hashlib.sha256 antes de regenerar el Golden en esta tarea (los PDFs no se versionan y el pack anterior no está en git)",
  "old_run_id": "a02a3c05-4887-4309-aa8f-51f8cc796a17",
  "old_generated_at": "2026-09-28T20:47:36.354726+00:00",
  "cambio_de_decision_material": true,
  "decision_anterior_HEAD": {
    "gate_state": null,
    "decision": "INFORMACIÓN VERIFICADA",
    "reason": "La valoración está autorizada y se imprime con su método y vigencia.",
    "blocking_conditions": []
  },
  "decision_actual": {
    "gate_state": "CLOSED",
    "decision": "NO EMITIR VALORACIÓN",
    "reason": "La valoración NO está autorizada en esta corrida: el origen de la tasa es MANUAL_CONFIG y su procedencia es INSUFICIENTE para autorizar una cifra (se exige fuente externa citada o cálculo de fuentes citadas, con fecha y sha256). No se emite cifra y se declaran los bloqueos reales.",
    "blocking_conditions": [
      "no hay fuente de mercado que sostenga la cifra: la tasa de esta corrida proviene de parámetros declarados a mano (origin=MANUAL_CONFIG: valor declarado a mano por la corrida (sin fuente externa automática)), sin procedencia externa verificable"
    ]
  },
  "nota": "cambio_de_decision_material compara la decisión del VALUATION_GATE (gate_state + decision + reason + blocking_conditions) entre la corrida anterior registrada en HEAD y la corrida actual del folio. Los valores `old` de `master_hash`/`run_id`/`generated_at` salen del manifest versionado en HEAD; los de los SHA-256 de los PDFs son la medición registrada en SHA256_PDF_ANTERIOR (no hay fuente en git: los PDFs no se versionan).",
  "regla_del_pack": "Si la decisión material cambió y el master hash NO cambió ⇒ FAIL. Aquí: decisión material CAMBIÓ y master hash SÍ cambió."
}
```

**Comandos:**

```bash
git rev-parse HEAD
git show HEAD:docs/forensics/040-646406/dictus_2b/DICTUS_MANIFEST_040-646406.json | python -c "import json,sys;print(json.load(sys.stdin)['master_hash'])"
python -c "import hashlib;print(hashlib.sha256(open('docs/forensics/040-646406/dictus_2b/DICTUS_EJECUTIVO_040-646406.pdf','rb').read()).hexdigest())"
```

- `old_master_hash = 1843ec22d0d3a1cb2e63881dcbabc5f0ec1d977a0de5f2b3da3e503005aea865`
- `new_master_hash = c804dc02b223c9be905f9e3103ffa54f355b7aba2986759af2ca470c7f7eee71`
- `changed = True` → el master hash **SÍ cambió** respecto a la corrida anterior registrada en `HEAD`.
- `cambio_de_decision_material = True` → **SÍ** cambió la decisión material del `VALUATION_GATE`.
  - decisión anterior (HEAD): `{"gate_state": null, "decision": "INFORMACIÓN VERIFICADA", "reason": "La valoración está autorizada y se imprime con su método y vigencia.", "blocking_conditions": []}`
  - decisión actual: `{"gate_state": "CLOSED", "decision": "NO EMITIR VALORACIÓN", "reason": "La valoración NO está autorizada en esta corrida: el origen de la tasa es MANUAL_CONFIG y su procedencia es INSUFICIENTE para autorizar una cifra (se exige fuente externa citada o cálculo de fuentes citadas, con fecha y sha256). No se emite cifra y se declaran los bloqueos reales.", "blocking_conditions": ["no hay fuente de mercado que sostenga la cifra: la tasa de esta corrida proviene de parámetros declarados a mano (origin=MANUAL_CONFIG: valor declarado a mano por la corrida (sin fuente externa automática)), sin procedencia externa verificable"]}`
- **Regla del pack:** Si la decisión material cambió y el master hash NO cambió ⇒ FAIL. Aquí: decisión material CAMBIÓ y master hash SÍ cambió. → **PASS**
- **Cambios producidos por esta tarea (old → new), todos en el MISMO commit:**

  | artefacto | old | new | changed |
  |---|---|---|---|
  | `master_hash` | `1843ec22d0d3a1cb2e63881dcbabc5f0ec1d977a0de5f2b3da3e503005aea865` | `c804dc02b223c9be905f9e3103ffa54f355b7aba2986759af2ca470c7f7eee71` | **true** |
  | `sha256_ejecutivo` | `7223d0c09f809896d36481ba443037845308b8024eec4233581036009c0d3a32` | `4960b12a08f5b447c6cc364b5aee7bfeb905ccd5ce0d8421f8e1a92955908c6c` | **true** |
  | `sha256_tecnico` | `33265085a0b154d4f44587f55d890af7baa7696d0cb63b7dfcc4229595ad0bac` | `f480e4d78947f7908198421f478de6f71cf9928011f066e8973e436b439ed80e` | **true** |
  | `run_id` | `a02a3c05-4887-4309-aa8f-51f8cc796a17` | `16019df2-a4fd-44db-860f-e50a5cdd3c2f` | **true** |
  | `generated_at` | `2026-09-28T20:47:36.354726+00:00` | `2026-09-30T14:47:40.937950+00:00` | **true** |

  Los valores `old` de `master_hash`/`run_id`/`generated_at` salen del manifest versionado en `HEAD`. Los de los SHA-256 de los PDFs NO tienen fuente en git (los PDFs no se versionan y `git show HEAD:docs/source_pack/ARTIFACT_HASHES_040-646406.json` responde «exists on disk, but not in HEAD»): son la MEDICIÓN registrada antes de regenerar el Golden en esta tarea.

## 8. Lonja sweep

**Objetivos barridos:** ejecutivo (6 páginas), técnico (17 páginas), `EXECUTIVE_DOCUMENT_MODEL.json`, `DICTUS_RUN_STATE`, `DICTUS_MANIFEST`, `MASTER_HASH.json`, el YAML de metodología (input de mercado real), `tests/*.py` (70 archivos) y el source registry (`api/*.py`).

### A. MENCIÓN PROHIBIDA (Lonja COMO FUENTE DE DATOS) — 13 línea(s)

**De ellas, en los ARTEFACTOS ENTREGADOS de la corrida: 0** (criterio: 0) → **PASS**

_El criterio se evalúa sobre los ARTEFACTOS ENTREGADOS (ejecutivo, técnico, manifest y run_state de la corrida): ahí debe haber 0 menciones. Las menciones del registro de adquisición (`api/acquisition.py`, `api/source_licenses.py`), del artefacto local de metodología y de los artefactos LEGACY (`dictus_2/`) se listan como observación declarada, con su file:line._

| ruta:línea | texto literal | por qué es categoría A | ¿entregable? |
|---|---|---|---|
| `motor_tma_lonja_baq_v1.0\motor_tma_lonja_baq_v1.0\lonja_layer\lonja_baq_metodologia.yaml:19` | `entidad: "Lonja de Propiedad Raíz de Barranquilla"` | nombra a la Lonja como entidad proveedora | no |
| `motor_tma_lonja_baq_v1.0\motor_tma_lonja_baq_v1.0\lonja_layer\lonja_baq_metodologia.yaml:205` | `# La Lonja declara los valores del suelo por sector. Estos pueden alinearse` | atribuye a la Lonja la declaración de los valores | no |
| `motor_tma_lonja_baq_v1.0\motor_tma_lonja_baq_v1.0\lonja_layer\lonja_baq_metodologia.yaml:218` | `fuente: "Precio de venta verificado en la constructora del proyecto (unidades ~58 m2 terminadas, 2026) + Lonja BAQ referencial"` | atribuye la tasa a «Lonja BAQ referencial» | no |
| `EXECUTIVE_DOCUMENT_MODEL.json:939` | `"source_m2": "Precio de venta verificado en la constructora del proyecto (unidades ~58 m2 terminadas, 2026) + Lonja BAQ referencial",` | atribuye la tasa a «Lonja BAQ referencial» | no |
| `EXECUTIVE_DOCUMENT_MODEL.json:990` | `"source": "Precio de venta verificado en la constructora del proyecto (unidades ~58 m2 terminadas, 2026) + Lonja BAQ referencial",` | atribuye la tasa a «Lonja BAQ referencial» | no |
| `EXECUTIVE_DOCUMENT_MODEL.json:1000` | `"source": "Precio de venta verificado en la constructora del proyecto (unidades ~58 m2 terminadas, 2026) + Lonja BAQ referencial",` | atribuye la tasa a «Lonja BAQ referencial» | no |
| `EXECUTIVE_DOCUMENT_MODEL.json:1061` | `"Precio de venta verificado en la constructora del proyecto (unidades ~58 m2 terminadas, 2026) + Lonja BAQ referencial",` | atribuye la tasa a «Lonja BAQ referencial» | no |
| `api/acquisition.py:161` | `"LONJA_MARKET_BAQ": CORE_MARKET,` | declara la Lonja con rol de fuente CORE_MARKET | no |
| `api/acquisition.py:198` | `"LONJA_MARKET_BAQ": AUTHORIZED_FALLBACK,` | declara la Lonja como ruta de adquisición autorizada | no |
| `api/acquisition.py:474` | `{"domain": "mercado", "fuente": "LONJA_MARKET_BAQ", "atributo": "mercado",` | declara la Lonja como `fuente` del dominio mercado | no |
| `api/source_licenses.py:111` | `FUENTE_LONJA = "LONJA_MARKET_BAQ"` | identifica la Lonja como FUENTE | no |
| `api/source_licenses.py:631` | `if sid == FUENTE_LONJA:` | identifica la Lonja como FUENTE | no |
| `api/source_licenses.py:643` | `attribution_text=ATRIBUCION_LONJA,` | construye bloque de licencia/atribución de la Lonja | no |

### B. MENCIÓN LEGÍTIMA — 286

Guardas, tests y documentación que dicen que la Lonja **NO** es fuente, más los identificadores sellados (`METHODOLOGY_ID = "lonja_baq_metodologia"`, `SOURCE_ID histórico = "LONJA_MARKET_BAQ"`, rutas del artefacto). Muestra:

| ruta:línea | texto literal | motivo |
|---|---|---|
| `motor_tma_lonja_baq_v1.0\motor_tma_lonja_baq_v1.0\lonja_layer\lonja_baq_metodologia.yaml:2` | `# DECLARACIÓN METODOLÓGICA — LONJA DE PROPIEDAD RAÍZ DE BARRANQUILLA` | identificador sellado (METHODOLOGY_ID / SOURCE_ID histórico / ruta) |
| `motor_tma_lonja_baq_v1.0\motor_tma_lonja_baq_v1.0\lonja_layer\lonja_baq_metodologia.yaml:5` | `# Este archivo declara la metodología que la Lonja BAQ aplica a sus avalúos` | identificador sellado (METHODOLOGY_ID / SOURCE_ID histórico / ruta) |
| `motor_tma_lonja_baq_v1.0\motor_tma_lonja_baq_v1.0\lonja_layer\lonja_baq_metodologia.yaml:9` | `# Quien firma este archivo: Junta Técnica de Avalúos Corporativos de la Lonja BAQ` | identificador sellado (METHODOLOGY_ID / SOURCE_ID histórico / ruta) |
| `motor_tma_lonja_baq_v1.0\motor_tma_lonja_baq_v1.0\lonja_layer\lonja_baq_metodologia.yaml:20` | `representante_legal: "[A declarar por la Lonja]"` | identificador sellado (METHODOLOGY_ID / SOURCE_ID histórico / ruta) |
| `motor_tma_lonja_baq_v1.0\motor_tma_lonja_baq_v1.0\lonja_layer\lonja_baq_metodologia.yaml:21` | `presidente_comite_tecnico: "[A declarar por la Lonja]"` | identificador sellado (METHODOLOGY_ID / SOURCE_ID histórico / ruta) |
| `motor_tma_lonja_baq_v1.0\motor_tma_lonja_baq_v1.0\lonja_layer\lonja_baq_metodologia.yaml:35` | `# La Lonja decide qué métodos aplicar y en qué orden. El motor solo ejecuta` | identificador sellado (METHODOLOGY_ID / SOURCE_ID histórico / ruta) |
| `motor_tma_lonja_baq_v1.0\motor_tma_lonja_baq_v1.0\lonja_layer\lonja_baq_metodologia.yaml:54` | `activo: false  # La Lonja decide cuándo activarlo (típicamente solo para lotes)` | identificador sellado (METHODOLOGY_ID / SOURCE_ID histórico / ruta) |
| `motor_tma_lonja_baq_v1.0\motor_tma_lonja_baq_v1.0\lonja_layer\lonja_baq_metodologia.yaml:58` | `# 2. REGLA DE CONSOLIDACIÓN DECLARADA POR LA LONJA` | identificador sellado (METHODOLOGY_ID / SOURCE_ID histórico / ruta) |
| `motor_tma_lonja_baq_v1.0\motor_tma_lonja_baq_v1.0\lonja_layer\lonja_baq_metodologia.yaml:60` | `# La Lonja declara qué peso le da a cada método. El motor NO inventa pesos.` | identificador sellado (METHODOLOGY_ID / SOURCE_ID histórico / ruta) |
| `motor_tma_lonja_baq_v1.0\motor_tma_lonja_baq_v1.0\lonja_layer\lonja_baq_metodologia.yaml:62` | `autor: "Junta Técnica de Avalúos Corporativos — Lonja BAQ"` | identificador sellado (METHODOLOGY_ID / SOURCE_ID histórico / ruta) |
| `motor_tma_lonja_baq_v1.0\motor_tma_lonja_baq_v1.0\lonja_layer\lonja_baq_metodologia.yaml:85` | `# La Lonja declara la fuente de costos a usar y el factor de actualización.` | identificador sellado (METHODOLOGY_ID / SOURCE_ID histórico / ruta) |
| `motor_tma_lonja_baq_v1.0\motor_tma_lonja_baq_v1.0\lonja_layer\lonja_baq_metodologia.yaml:131` | `# La Lonja declara las tasas de capitalización por tipología y zona.` | identificador sellado (METHODOLOGY_ID / SOURCE_ID histórico / ruta) |
| `motor_tma_lonja_baq_v1.0\motor_tma_lonja_baq_v1.0\lonja_layer\lonja_baq_metodologia.yaml:135` | `# Tasas por tipología — La Lonja edita estos valores trimestralmente` | identificador sellado (METHODOLOGY_ID / SOURCE_ID histórico / ruta) |
| `motor_tma_lonja_baq_v1.0\motor_tma_lonja_baq_v1.0\lonja_layer\lonja_baq_metodologia.yaml:175` | `# Corrimiento oferta-cierre declarado por la Lonja` | identificador sellado (METHODOLOGY_ID / SOURCE_ID histórico / ruta) |
| `motor_tma_lonja_baq_v1.0\motor_tma_lonja_baq_v1.0\lonja_layer\lonja_baq_metodologia.yaml:176` | `# La Lonja tiene los datos de cierre que el mercado abierto no tiene` | identificador sellado (METHODOLOGY_ID / SOURCE_ID histórico / ruta) |
| `motor_tma_lonja_baq_v1.0\motor_tma_lonja_baq_v1.0\lonja_layer\lonja_baq_metodologia.yaml:181` | `nota: "Estos porcentajes vienen de las series cerradas de la Lonja BAQ. Sinergia no los inventa."` | identificador sellado (METHODOLOGY_ID / SOURCE_ID histórico / ruta) |
| `motor_tma_lonja_baq_v1.0\motor_tma_lonja_baq_v1.0\lonja_layer\lonja_baq_metodologia.yaml:242` | `- rol: "representante_legal_lonja"` | identificador sellado (METHODOLOGY_ID / SOURCE_ID histórico / ruta) |
| `motor_tma_lonja_baq_v1.0\motor_tma_lonja_baq_v1.0\lonja_layer\lonja_baq_metodologia.yaml:243` | `nombre_placeholder: "[Representante Legal Lonja BAQ]"` | identificador sellado (METHODOLOGY_ID / SOURCE_ID histórico / ruta) |
| `motor_tma_lonja_baq_v1.0\motor_tma_lonja_baq_v1.0\lonja_layer\lonja_baq_metodologia.yaml:253` | `incluir_logo_lonja: true` | identificador sellado (METHODOLOGY_ID / SOURCE_ID histórico / ruta) |
| `motor_tma_lonja_baq_v1.0\motor_tma_lonja_baq_v1.0\lonja_layer\lonja_baq_metodologia.yaml:254` | `incluir_numero_consecutivo_lonja: true` | identificador sellado (METHODOLOGY_ID / SOURCE_ID histórico / ruta) |
| `DICTUS_MANIFEST_040-646406.json:1586` | `"market_methodology_id": "lonja_baq_metodologia",` | identificador sellado (METHODOLOGY_ID / SOURCE_ID histórico / ruta) |
| `DICTUS_MANIFEST_040-646406.json:1700` | `"market_methodology_id": "lonja_baq_metodologia",` | identificador sellado (METHODOLOGY_ID / SOURCE_ID histórico / ruta) |
| `DICTUS_MANIFEST_040-646406.json:1703` | `"market_methodology_file": "lonja_baq_metodologia.yaml",` | identificador sellado (METHODOLOGY_ID / SOURCE_ID histórico / ruta) |
| `DICTUS_MANIFEST_040-646406.json:1719` | `"methodology_file": "lonja_baq_metodologia.yaml",` | identificador sellado (METHODOLOGY_ID / SOURCE_ID histórico / ruta) |
| `DICTUS_MANIFEST_040-646406.json:1721` | `"methodology_id": "lonja_baq_metodologia",` | identificador sellado (METHODOLOGY_ID / SOURCE_ID histórico / ruta) |
| `DICTUS_MANIFEST_040-646406.json:1731` | `"market_methodology_id": "lonja_baq_metodologia",` | identificador sellado (METHODOLOGY_ID / SOURCE_ID histórico / ruta) |
| `DICTUS_MANIFEST_040-646406.json:1734` | `"market_methodology_file": "lonja_baq_metodologia.yaml",` | identificador sellado (METHODOLOGY_ID / SOURCE_ID histórico / ruta) |
| `DICTUS_MANIFEST_040-646406.json:1752` | `"market_methodology_id": "lonja_baq_metodologia",` | identificador sellado (METHODOLOGY_ID / SOURCE_ID histórico / ruta) |
| `DICTUS_MANIFEST_040-646406.json:2920` | `"methodology_id": "lonja_baq_metodologia",` | identificador sellado (METHODOLOGY_ID / SOURCE_ID histórico / ruta) |
| `DICTUS_MANIFEST_040-646406.json:4771` | `"methodology_id": "lonja_baq_metodologia",` | identificador sellado (METHODOLOGY_ID / SOURCE_ID histórico / ruta) |
| `DICTUS_RUN_STATE_040-646406.json:1307` | `"market_methodology_id": "lonja_baq_metodologia",` | identificador sellado (METHODOLOGY_ID / SOURCE_ID histórico / ruta) |
| `DICTUS_RUN_STATE_040-646406.json:1310` | `"market_methodology_file": "lonja_baq_metodologia.yaml",` | identificador sellado (METHODOLOGY_ID / SOURCE_ID histórico / ruta) |
| `DICTUS_RUN_STATE_040-646406.json:1326` | `"methodology_file": "lonja_baq_metodologia.yaml",` | identificador sellado (METHODOLOGY_ID / SOURCE_ID histórico / ruta) |
| `DICTUS_RUN_STATE_040-646406.json:1328` | `"methodology_id": "lonja_baq_metodologia",` | identificador sellado (METHODOLOGY_ID / SOURCE_ID histórico / ruta) |
| `DICTUS_RUN_STATE_040-646406.json:1338` | `"market_methodology_id": "lonja_baq_metodologia",` | identificador sellado (METHODOLOGY_ID / SOURCE_ID histórico / ruta) |
| `DICTUS_RUN_STATE_040-646406.json:1341` | `"market_methodology_file": "lonja_baq_metodologia.yaml",` | identificador sellado (METHODOLOGY_ID / SOURCE_ID histórico / ruta) |
| `DICTUS_RUN_STATE_040-646406.json:1359` | `"market_methodology_id": "lonja_baq_metodologia",` | identificador sellado (METHODOLOGY_ID / SOURCE_ID histórico / ruta) |
| `DICTUS_RUN_STATE_040-646406.json:1663` | `"metodologia_id": "lonja_baq_metodologia",` | identificador sellado (METHODOLOGY_ID / SOURCE_ID histórico / ruta) |
| `EXECUTIVE_DOCUMENT_MODEL.json:1120` | `"market_methodology_id": "lonja_baq_metodologia",` | identificador sellado (METHODOLOGY_ID / SOURCE_ID histórico / ruta) |
| `tests/test_arhiax_re.py:89` | `def test_valoracion_metodologia_lonja_baq_yaml(self):` | identificador sellado (METHODOLOGY_ID / SOURCE_ID histórico / ruta) |

_(mostradas 40 de 286; el listado completo está en `GOLDEN_EVIDENCE_LITERAL_PACK_040-646406.data.json`)_

**Lo que SÍ pasa:** los dos PDF entregados (ejecutivo y técnico) tienen **0 ocurrencias** de «Lonja», igual que el `DICTUS_MANIFEST` y el `DICTUS_RUN_STATE` de la corrida: la purga en el render y en el estado funciona.

## 9. VERIFIED audit

**Acceptance:** `True` · `facts leídos = 9` · `impresos VERIFICADO = 1` · `disallowed_origin_count = 0` → **PASS**

**Regla aplicada (explícita y razonada, no por conveniencia):**

REGLA APLICADA (ajustada de forma explícita y razonada): un hecho impreso como VERIFICADO exige un ORIGEN DECLARADO y AUTORIZADO —`EXTERNAL_SOURCE` o `COMPUTED_FROM_SOURCES`, con procedencia completa (fuentes citadas + fecha + sha256)—. `COMPUTED_FROM_SOURCES` PURO se admite como válido: el hecho de identidad no es un literal del render, es el resultado DETERMINISTA de la resolución canónica de la corrida (`canonical.identidad_canonica`: `identity_verified` se deriva de `resolution_confidence == VERIFIED_UNIT_IDENTITY`) sostenido por dos evidencias SELLADAS de esa misma corrida. Si la procedencia no está completa, `clasificar_origen` degrada el origen y el estado impreso se degrada con él (nunca se borra el hecho).

**Todos los hechos de identidad de la página 6, con su estado y su ORIGEN LEÍDO del artefacto (`manifest.hechos_impresos.identidad.filas`):**

| # | attribute | value | status | origin | origin_declarado | origin_gate | fuentes citadas |
|---|---|---|---|---|---|---|---|
| 1 | Dirección oficial | `TV 43 # 100 - 50 CONJUNTO RESIDENCIAL NA` | **REQUIERE_VALIDACION** | `COMPUTED_FROM_SOURCES` | `COMPUTED_FROM_SOURCES` | True | 2 |
| 2 | Matrícula | `040-646406` | **VERIFICADO** | `COMPUTED_FROM_SOURCES` | `COMPUTED_FROM_SOURCES` | True | 2 |
| 3 | NUPRE | `AFT0005BOHA` | **REQUIERE_VALIDACION** | `COMPUTED_FROM_SOURCES` | `COMPUTED_FROM_SOURCES` | True | 2 |
| 4 | Número predial | `080010103000010040001908040002` | **REQUIERE_VALIDACION** | `COMPUTED_FROM_SOURCES` | `COMPUTED_FROM_SOURCES` | True | 2 |
| 5 | Unidad (torre / apartamento) | `APARTAMENTO 430 TORRE 8` | **REQUIERE_VALIDACION** | `COMPUTED_FROM_SOURCES` | `COMPUTED_FROM_SOURCES` | True | 2 |
| 6 | Área | `58.75 m²` | **REQUIERE_VALIDACION** | `COMPUTED_FROM_SOURCES` | `COMPUTED_FROM_SOURCES` | True | 2 |
| 7 | Régimen jurídico | `Propiedad Horizontal` | **REQUIERE_VALIDACION** | `COMPUTED_FROM_SOURCES` | `COMPUTED_FROM_SOURCES` | True | 2 |
| 8 | Uso (destino catastral) | `Habitacional` | **REQUIERE_VALIDACION** | `COMPUTED_FROM_SOURCES` | `COMPUTED_FROM_SOURCES` | True | 2 |
| 9 | Tipología | `Unidad En Propiedad Horizontal` | **REQUIERE_VALIDACION** | `COMPUTED_FROM_SOURCES` | `COMPUTED_FROM_SOURCES` | True | 2 |

**Procedencia literal del hecho impreso como VERIFICADO:**

- `Matrícula` = `040-646406`

```json
[
  {
    "proveedor": "SNR + geoportal municipal",
    "fecha": "2026-09-30T14:47:40.937950+00:00",
    "referencia": "EV-IDENTIDAD · IDENTIDAD_CANONICA",
    "sha256": "e2ed9dac35bbd509289186ccfa529f99ee604ca8857026a6a1d5376fbd7defbf"
  },
  {
    "proveedor": "CATASTRO_MUNICIPAL_BARRANQUILLA_ARCGIS",
    "fecha": "2026-09-30T14:47:40.937950+00:00",
    "referencia": "EV-GEOMETRIA · GEOMETRIA_OFICIAL",
    "sha256": "95dca1e34ffeba3f61f035bc3991e02314a9d2c3674f056d3b687a427c79b41c"
  }
]
```

**Violaciones (origen prohibido o no habilitante):**


**Cero violaciones.** Ningún hecho VERIFICADO se sostiene en `MANUAL_CONFIG`, `STATIC_REFERENCE`, `MODEL_PRIOR`, `FIXTURE`, `DEFAULT`, `HARDCODE` ni `FALLBACK_HEURISTIC`; y el estado impreso se DEGRADA solo si el origen no autoriza (`api/dictus_secciones.py · _estado_atributo(..., origen)`), de modo que la conformidad no depende de que nadie se acuerde.

**Corrección de fondo aplicada en esta tarea:** `dictus_manifiesto._ev` calculaba el `content_hash` de cada evidencia con `serializacion_canonica({"bloques": {"_evidencia": …}})`, pero esa función SOLO serializa las claves de `BLOQUES_CANONICOS`: `_evidencia` no está ahí, así que **las 10 evidencias del manifest salían con el MISMO hash constante** (`a789f78c…`), ajeno a su contenido. Un `sha256` de procedencia que no depende del contenido es una constante, no una prueba. Ahora `_ev` hashea el contenido real (`hashlib.sha256` de su serialización canónica) y cada evidencia tiene su propio hash —que es lo que permite CITARLA.

## 10. Cross-page consistency

**Acceptance:** `True` · `atributos comparados = 7` · `inconsistentes = 0` → **PASS**

**Cada estado impreso se LEE de la página; la referencia es la VERDAD ÚNICA del expediente (no la otra página):**

| atributo (clave canónica) | verdad del expediente | P1 | P4 | P6 | coherente entre páginas | coincide con la verdad |
|---|---|---|---|---|---|---|
| `altura_maxima` | HISTORICAL_CONFLICT | n/d | HISTORICAL_CONFLICT | n/d | **true** | **true** |
| `amenaza` | HISTORICAL_CONFLICT | n/d | NO UTILIZAR ESTE DATO COMO DEFINITIVO | n/d | **true** | **true** |
| `binding_geometria` | VERIFICADA | n/d | n/d | VERIFICADA | **true** | **true** |
| `coordenada` | HISTORICAL_CONFLICT | n/d | NO UTILIZAR ESTE DATO COMO DEFINITIVO | n/d | **true** | **true** |
| `titulares` | HISTORICAL_CONFLICT | n/d | NO UTILIZAR ESTE DATO COMO DEFINITIVO | n/d | **true** | **true** |
| `tratamiento` | HISTORICAL_CONFLICT | n/d | HISTORICAL_CONFLICT | n/d | **true** | **true** |
| `uso_pot` | HISTORICAL_CONFLICT | n/d | NO UTILIZAR ESTE DATO COMO DEFINITIVO | n/d | **true** | **true** |

**La contradicción que este criterio marcaba (y por qué NO era una contradicción):**

| lo que decía el detector viejo | por qué comparaba dos cosas distintas |
|---|---|
| `geometria: P4 = 'COORDENADA DEL PREDIO … NO UTILIZAR ESTE DATO COMO DEFINITIVO' vs P6 = 'Geometría oficial: VERIFICADA'` | **Son dos atributos distintos.** `coordenada` = el VALOR de la coordenada que la corrida usa; el expediente histórico produjo tres valores diferentes (`10.9870 -74.8115`, `11.00538 -74.83862`, `11.00612 -74.83753`) y por eso NO se usa como definitivo (P4, correcto). `binding_geometria` = ¿la geometría OFICIAL corresponde a la identidad canónica (NUPRE + número predial)? El mercado declaró `canonical_binding_status = VERIFIED` (P6, correcto). Los dos hechos son verdaderos A LA VEZ. |

**Qué se cambió para que no pueda volver (dos capas):**

1. **El documento rotula atributos separados.** La P6 imprime `Binding de la geometría oficial: VERIFICADA` (antes `Geometría oficial: VERIFICADA`, que se leía como una afirmación sobre la coordenada) y la P4 rotula su fila `COORDENADA DEL PREDIO` desde la clave canónica `coordenada`. Además, el chip de la P4 ya no estampa la decisión del `URBAN_GATE` en todos los atributos del panel: imprime el término que corresponde al estado DE ESE atributo.
2. **El detector usa la clave correcta.** Compara por clave canónica (`coordenada` ≠ `binding_geometria`), no por cercanía de texto, y contrasta cada estado con la verdad única del expediente: si la P4 dijera `VERIFICADA` de la coordenada, o la P6 dijera `NO UTILIZAR…` del binding, la aserción FALLA. Regresión cubierta por `tests/test_golden_evidence_pack.py` (`test_el_detector_falla_si_la_coordenada_se_rotula_verificada`, `test_el_detector_falla_si_el_binding_se_rotula_no_utilizar`, `test_el_detector_falla_si_vuelve_el_rotulo_ambiguo`).

**Tabla completa de la verdad única usada como referencia:**

```json
{
  "altura_maxima": "HISTORICAL_CONFLICT",
  "amenaza": "HISTORICAL_CONFLICT",
  "coordenada": "HISTORICAL_CONFLICT",
  "titulares": "HISTORICAL_CONFLICT",
  "tratamiento": "HISTORICAL_CONFLICT",
  "uso_pot": "HISTORICAL_CONFLICT",
  "area": "REQUIERE_VALIDACION",
  "barrio": "REQUIERE_VALIDACION",
  "clase_suelo": "REQUIERE_VALIDACION",
  "destino_economico": "REQUIERE_VALIDACION",
  "direccion": "REQUIERE_VALIDACION",
  "estrato": "REQUIERE_VALIDACION",
  "evidencias": "REQUIERE_VALIDACION",
  "gravamenes": "REQUIERE_VALIDACION",
  "localidad": "REQUIERE_VALIDACION",
  "numero_predial": "REQUIERE_VALIDACION",
  "nupre": "REQUIERE_VALIDACION",
  "regimen_juridico": "REQUIERE_VALIDACION",
  "riesgo": "REQUIERE_VALIDACION",
  "screening": "REQUIERE_VALIDACION",
  "unidad": "REQUIERE_VALIDACION",
  "valor_central": "REQUIERE_VALIDACION",
  "valor_m2": "REQUIERE_VALIDACION",
  "binding_geometria": "VERIFICADA"
}
```

## 11. Assertions

**Comando:** `python scripts/golden_evidence_asserts.py; echo $LASTEXITCODE`
**Salida literal y exit code:**

```
[PASS] valuation_gate['gate_state'] == 'CLOSED' (con decision 'NO EMITIR VALORACIÓN')
        actual gate_state = 'CLOSED' · decision = 'NO EMITIR VALORACIÓN'
        vocabulario CLOSED/OPEN = True · coexisten ambos campos = True
        DICTUS_MANIFEST_040-646406.json · modelo.decision_gates[VALUATION_GATE]
[PASS] valuation_gate['reason'] explícito y con el ORIGEN del bloqueo
        actual = 'La valoración NO está autorizada en esta corrida: el origen de la tasa es MANUAL_CONFIG y su procedencia es INSUFICIENTE para autorizar una cifra (se exige fuente externa citada o cálculo de fuentes citadas, con fecha y sha256). No se emite cifra y se declaran los bloqueos reales.'
        nombra el origen no habilitante (MANUAL_CONFIG / procedencia insuficiente) = True
[PASS] '399.500.000' not in executive_text
        presente = False
        DICTUS_EJECUTIVO_040-646406.pdf · sha256 = 4960b12a08f5b447c6cc364b5aee7bfeb905ccd5ce0d8421f8e1a92955908c6c · ocurrencias = 0
[PASS] '$399' not in executive_text
        presente = False
        DICTUS_EJECUTIVO_040-646406.pdf · sha256 = 4960b12a08f5b447c6cc364b5aee7bfeb905ccd5ce0d8421f8e1a92955908c6c · ocurrencias = 0
[PASS] 'Lonja' not in executive_text
        presente = False
        DICTUS_EJECUTIVO_040-646406.pdf · sha256 = 4960b12a08f5b447c6cc364b5aee7bfeb905ccd5ce0d8421f8e1a92955908c6c · ocurrencias = 0
[PASS] 'Lonja' not in technical_text (salvo guardas/documentación de NO SOURCE)
        ocurrencias 'Lonja' = 0 en DICTUS_TECNICO_040-646406.pdf
[PASS] no_verified_fact_has_disallowed_origin()
        facts de identidad leídos = 9 · impresos VERIFICADO = 1 · violaciones = 0
        
          ✓ Matrícula = '040-646406' · origin=COMPUTED_FROM_SOURCES · fuentes=2
[PASS] no_cross_page_state_contradictions()
        atributos comparados por clave canónica = 7 · contradicciones entre páginas = 0 · discrepancias con la verdad única del expediente = 0
        
          claves y estados impresos: altura_maxima: P4=HISTORICAL_CONFLICT; amenaza: P4=HISTORICAL_CONFLICT; binding_geometria: P6=VERIFICADA; coordenada: P4=HISTORICAL_CONFLICT; titulares: P4=HISTORICAL_CONFLICT; tratamiento: P4=HISTORICAL_CONFLICT; uso_pot: P4=HISTORICAL_CONFLICT
[PASS] manual_market_input_cannot_open_valuation_gate()
        origin=MANUAL_CONFIG · origin_gate=False
        blockers=['origen MANUAL_CONFIG no habilita la valoración (valor declarado a mano por la corrida (sin fuente externa automática))']
[PASS] model_prior_cannot_open_valuation_gate()
        origin=MODEL_PRIOR · origin_gate=False
        blockers=['origen MODEL_PRIOR no habilita la valoración (valor por defecto del modelo (sin fuente: no autoriza cifra))']
[PASS] computed_from_sources_requires_all_material_inputs_authorized()
        sin procedencia completa: origin=MANUAL_CONFIG gate=False blockers=['origen declarado COMPUTED_FROM_SOURCES SIN procedencia completa (falta: fuentes[] (se exigen >= 2)): se degrada a MANUAL_CONFIG']
        con 2 fuentes completas: origin=COMPUTED_FROM_SOURCES gate=True

TOTAL = 11 · PASS = 11 · FAIL = 0 · NO EVALUABLE = 0

```

**exit code = 0**

**Log literal de los tres comandos de la corrida** (dictus_run → pack → asserts, con sus exit codes): `docs/source_pack/EVIDENCIA_COMANDOS_040-646406.txt`.

**Las 11 aserciones, y qué cubre cada una:**

| # | aserción | criterio | resultado |
|---|---|---|---|
| 1 | `valuation_gate['gate_state'] == 'CLOSED' (con decision 'NO EMITIR VALORACIÓN')` | (A) el estado de compuerta convive con el término de la gramática de decisión | **PASS** |
| 2 | `valuation_gate['reason'] explícito y con el ORIGEN del bloqueo` | (B) el bloqueo nombra su causa: origen no habilitante / procedencia insuficiente | **PASS** |
| 3 | `'399.500.000' not in executive_text` | la cifra prohibida no vuelve | **PASS** |
| 4 | `'$399' not in executive_text` | ni en su forma corta | **PASS** |
| 5 | `'Lonja' not in executive_text` | purga en el ejecutivo | **PASS** |
| 6 | `'Lonja' not in technical_text` | purga en el anexo técnico | **PASS** |
| 7 | `no_verified_fact_has_disallowed_origin()` | (B) el hecho VERIFICADO declara origen autorizado con procedencia sellada | **PASS** |
| 8 | `no_cross_page_state_contradictions()` | (C) detector por clave canónica + verdad única del expediente | **PASS** |
| 9 | `manual_market_input_cannot_open_valuation_gate()` | `MANUAL_CONFIG` nunca abre la valoración | **PASS** |
| 10 | `model_prior_cannot_open_valuation_gate()` | `MODEL_PRIOR` nunca abre la valoración | **PASS** |
| 11 | `computed_from_sources_requires_all_material_inputs_authorized()` | `COMPUTED_FROM_SOURCES` exige ≥ 2 fuentes con proveedor/fecha/referencia/sha256 | **PASS** |

## 12. Tests

**Comando exacto por archivo:** `python -m pytest <archivo> -q -p no:cacheprovider`

| archivo | criterio | passed | failed | skipped | xfail | xpass | errors | exit code |
|---|---|---|---|---|---|---|---|---|
| `tests/test_dictus_semantica_atributos.py` | origin propagation + semántica de atributos | 31 | 0 | 0 | 0 | 0 | 0 | **0** |
| `tests/test_no_lonja_as_source.py` | Lonja purge | 12 | 0 | 0 | 0 | 0 | 0 | **0** |
| `tests/test_source_pack_market.py` | market context / mercado | 60 | 0 | 0 | 0 | 0 | 0 | **0** |
| `tests/test_source_pack_licenses.py` | licencias de fuente | 51 | 0 | 0 | 0 | 0 | 0 | **0** |
| `tests/test_source_pack_contract.py` | contrato del source pack | 26 | 0 | 0 | 0 | 0 | 0 | **0** |
| `tests/test_source_pack_acquisition_modes.py` | modos de adquisición | 73 | 0 | 0 | 0 | 0 | 0 | **0** |
| `tests/test_source_pack_resolution_ladder.py` | escalera de resolución | 59 | 0 | 0 | 0 | 0 | 0 | **0** |
| `tests/test_source_pack_pipeline.py` | pipeline del source pack | 36 | 0 | 0 | 0 | 0 | 0 | **0** |
| `tests/test_dictus_20d_r1_p6.py` | valuation gate + Golden executive text (P6) | 10 | 0 | 0 | 1 | 0 | 0 | **0** |
| `tests/test_dictus_20c_fidelidad.py` | Golden executive text (fidelidad) | 20 | 0 | 0 | 0 | 0 | 0 | **0** |
| `tests/test_golden_evidence_pack.py` | origin propagation + valuation gate + market unresolved + Lonja purge + verified origin audit + cross-page consistency + Golden executive/technical text + hash change | 30 | 0 | 0 | 0 | 0 | 0 | **0** |
| `tests/test_dictus_20d_decision.py` | valuation gate + decision grammar | 22 | 0 | 0 | 0 | 0 | 0 | **0** |
| `tests/test_remediacion_03h2a.py` | Golden technical text | 33 | 0 | 0 | 0 | 0 | 0 | **0** |
| `tests/test_dictus_20b_integracion.py` | hash change + integracion | 14 | 0 | 0 | 0 | 0 | 0 | **0** |
| `tests/test_dictus_20b_r1_entrega_ejecutiva.py` | Golden executive text (entrega) | 26 | 0 | 0 | 0 | 0 | 0 | **0** |
| `tests/test_dictus_20_ejecutivo.py` | Golden executive text (estructura) | 22 | 0 | 1 | 0 | 0 | 0 | **0** |

**Resumen literal por archivo (última línea de pytest):**

```
tests/test_dictus_semantica_atributos.py: 31 passed in 0.55s  [exit 0]
tests/test_no_lonja_as_source.py: 12 passed in 0.53s  [exit 0]
tests/test_source_pack_market.py: 60 passed in 0.50s  [exit 0]
tests/test_source_pack_licenses.py: 51 passed in 2.47s  [exit 0]
tests/test_source_pack_contract.py: 26 passed in 0.11s  [exit 0]
tests/test_source_pack_acquisition_modes.py: 73 passed, 21 subtests passed in 41.87s  [exit 0]
tests/test_source_pack_resolution_ladder.py: 59 passed, 18 subtests passed in 0.16s  [exit 0]
tests/test_source_pack_pipeline.py: 36 passed in 1.30s  [exit 0]
tests/test_dictus_20d_r1_p6.py: 10 passed, 1 xfailed in 0.66s  [exit 0]
tests/test_dictus_20c_fidelidad.py: 20 passed in 0.97s  [exit 0]
tests/test_golden_evidence_pack.py: 30 passed in 1.24s  [exit 0]
tests/test_dictus_20d_decision.py: 22 passed in 0.68s  [exit 0]
tests/test_remediacion_03h2a.py: 33 passed in 20.13s  [exit 0]
tests/test_dictus_20b_integracion.py: 14 passed in 0.52s  [exit 0]
tests/test_dictus_20b_r1_entrega_ejecutiva.py: 26 passed in 2.32s  [exit 0]
tests/test_dictus_20_ejecutivo.py: 22 passed, 1 skipped in 0.20s  [exit 0]
```

**Fallos literales:**


**Criterios de §12 cubiertos por test versionado (todos en `tests/test_golden_evidence_pack.py`):**

| criterio | test |
|---|---|
| origin propagation | `test_origin_propagation_clasificar_origen` · `test_el_origen_del_hecho_identidad_es_computed_con_dos_fuentes_selladas` |
| valuation gate | `test_valuation_gate_gate_state_y_decision_conviven` · `test_los_siete_gates_declaran_gate_state_del_vocabulario_cerrado` |
| market unresolved | `test_market_context_status_unresolved` |
| Lonja purge | `test_lonja_no_aparece_en_los_dos_pdf` |
| verified origin audit | `test_auditoria_de_origen_del_hecho_verificado` · `test_un_origen_no_habilitante_degrada_el_estado_sin_borrar_el_hecho` |
| cross-page consistency | `test_detector_de_contradicciones_por_clave_canonica` · `test_el_detector_falla_si_la_coordenada_se_rotula_verificada` · `test_el_detector_falla_si_el_binding_se_rotula_no_utilizar` · `test_el_detector_falla_si_vuelve_el_rotulo_ambiguo` |
| Golden executive text | `test_golden_ejecutivo_literal` |
| Golden technical text | `test_golden_tecnico_literal` |
| hash change | `test_el_master_hash_cambia_con_los_hechos_y_verifica` |

**Medición tomada en `2026-09-30T14:47:46.430626+00:00`.** Los conteos de §12 son la FOTO de ese instante sobre el Golden regenerado en esta tarea.

## 13. Verdict

### EVIDENCE PACK — **PASS**

**Criterios:** 12 evaluados · 12 PASS · 0 FAIL.

| criterion | actual | expected | file:line |
|---|---|---|---|
| ✅ `VALUATION_GATE.gate_state == 'CLOSED'` (con `decision == 'NO EMITIR VALORACIÓN'`) | gate_state = `CLOSED` · decision = `NO EMITIR VALORACIÓN` | `CLOSED` (y `NO EMITIR VALORACIÓN` en `decision`) | `docs/forensics/040-646406/dictus_2b/DICTUS_MANIFEST_040-646406.json` · `modelo.decision_gates[VALUATION_GATE].gate_state` |
| ✅ `VALUATION_GATE.reason` explícito y con el ORIGEN del bloqueo | `La valoración NO está autorizada en esta corrida: el origen de la tasa es MANUAL_CONFIG y su procedencia es INSUFICIENTE para autorizar una cifra (se exige fuente externa citada o cálculo de fuentes citadas, con fecha y sha256). No se emite cifra y se declaran los bloqueos reales.` | razón que nombre `MANUAL_CONFIG` / procedencia insuficiente | idem · `.reasons[0]` |
| ✅ `'399.500.000' not in executive_text` | 0 ocurrencia(s) en P1+P6 | ausente | `DICTUS_EJECUTIVO_040-646406.pdf` P1 y P6 |
| ✅ `'NO EMITIR VALORACIÓN' in executive_text` | presente 1× en P6 | presente con razón explícita | `DICTUS_EJECUTIVO_040-646406.pdf` P6 |
| ✅ `'COMPUERTA CLOSED' in executive_text` (A · el estado de la compuerta se imprime) | presente 1× en P6 | presente junto a la decisión | `DICTUS_EJECUTIVO_040-646406.pdf` P6 · `api/dictus_ejecutivo.py` `_dib_blockers()` |
| ✅ `market_context.status == UNRESOLVED` | `UNRESOLVED` | `UNRESOLVED` | `DICTUS_RUN_STATE_040-646406.json` · `market_context.status` |
| ✅ `market_context` declara su CAUSA (`reason` + `origin_gate=false` cuando `status = UNRESOLVED`) | `reason = MARKET_CONTEXT_UNRESOLVED: origen no declarado por el artefacto: se clasifica MANUAL_CONFIG (no habilita la valoración)` · `origin_gate = False` · `blockers` = 0 | causa declarada (el origen no habilitante vive en `reason` / `origin_gate`; `blockers` sólo lista campos obligatorios ausentes) | `DICTUS_RUN_STATE_040-646406.json` · `market_context` |
| ✅ `no_verified_fact_has_disallowed_origin()` | 1 hecho(s) VERIFICADO, 0 violación(es) | 0 | `DICTUS_MANIFEST_040-646406.json` · `modelo.hechos_impresos.identidad.filas` + `DICTUS_EJECUTIVO_040-646406.pdf` P6 |
| ✅ `no_cross_page_state_contradictions()` | 7 atributo(s) comparado(s) por clave canónica, 0 inconsistente(s) | 0 | `DICTUS_EJECUTIVO_040-646406.pdf` P4/P6 · verdad única en `DICTUS_RUN_STATE_040-646406.json` |
| ✅ «Lonja» en los ARTEFACTOS ENTREGADOS (ejecutivo, técnico, manifest, run_state) — Lonja purge | 0 mención(es) en entregables · 13 en total (las demás: registro de adquisición, artefacto local de metodología y artefactos LEGACY `dictus_2/`; se listan en §8 con su file:line) | 0 en los entregables (el total NO se declara como si fuera el entregable) | `docs/source_pack/GOLDEN_EVIDENCE_LITERAL_PACK_040-646406.md` §8 |
| ✅ Golden regenerado con las reglas nuevas (`verify_master_hash = MATCH`, `layout_violations = []`) | `c804dc02b223c9be…` · sha256 ejecutivo `4960b12a08f5b447…` | Golden regenerado en esta corrida | `docs/forensics/040-646406/dictus_2b/` |
| ✅ `python scripts/golden_evidence_asserts.py` exit 0 con 11/11 PASS | exit code = 0 | exit code = 0 y 0 FAIL | `scripts/golden_evidence_asserts.py` |

**No queda ningún criterio en FAIL.** Los tres que fallaban al inicio de esta
tarea (`gate_state`, origen del hecho VERIFICADO y contradicción entre páginas)
están resueltos, y su evidencia literal es §3, §9, §10 y §11 de este pack.

**No se declara `CONTRACT FROZEN`:** esta tarea entrega evidencia literal
reproducible, no un congelamiento de contrato.


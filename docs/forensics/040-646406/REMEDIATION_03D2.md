# REMEDIATION 03D.2 — Golden Case Closure: PH Detection → Identity → Valuation Authorization

Cierra el fallo del acceptance gate del Dictus real 040-646406 (commit 36fabff):
`canonical.estado = NO_RECORD` + `PH = True` + `valuation = $305.5M`.

## Fallo raíz

El gate de valoración dependía de que se extrajeran `torre`/`apartamento`/
`unidad`. El parser no los extrajo (la dirección del CTL quedó
`TV 43 # 100 - 50 CONJUNTO RESIDENCIAL NAPOLI APARTAMENTOS ETAPA`), por lo que
`_unidad_ph_presente = False` y la valoración continuó pese a `NO_RECORD`.

## Invariante impuesto

```text
UNRESOLVED PROPERTY IDENTITY + PH + VALUATION EMITTED = INVALID SYSTEM STATE
```

## Cambios

### 1. Detección canónica de PH (`canonical._detectar_ph`)
`propiedad_horizontal` (is_property_horizontal) ahora se deriva de múltiples
fuentes, sin inventar PH: nomenclatura (es_ph) → condición jurídica catastral →
inferencia del CTL/SNR (`inferir_condicion_juridica`: PROPIEDAD HORIZONTAL /
COEFICIENTE / APARTAMENTO) → marcadores de unidad extraídos → marcadores en
dirección/descripción (APARTAMENTO/APTO/CONJUNTO/EDIFICIO/TORRE/UNIDAD/P.H.).

Regla dura: **la ausencia de torre/apartamento extraídos NO es evidencia de No PH**.

### 2. Autorización única de valoración (`canonical.can_value_property`)
Devuelve `{allowed, reason, identity_level}`. Para PH, solo
`VERIFIED_UNIT_IDENTITY` autoriza; `NO_RECORD / NO_MATCH / PARTIAL / AMBIGUOUS /
MULTIPLE_MATCHES / MATCH_BY_GEOMETRY / SPATIAL_CONTEXT_ONLY / IDENTITY_CONFLICT /
UNKNOWN / None` bloquean (fail-closed). `pdf_compiler` consume esta decisión (no
booleans dispersos); resultado: `metodologia_aplica=False` → **"ESTIMACIÓN
REFERENCIAL NO EMITIDA"** (nunca `$0` ni precio por fallback).

### 3. Invariante de valoración (`consistency._inv_valuation_coherente`)
Nuevo invariante bloqueante `I-VALUATION`: `consolidado > 0` implica
autorización; PH-no-resuelta implica `consolidado == 0` y `metodologia_aplica
False`. El `PRE_RENDER_CONSISTENCY_GATE` ahora recibe `valuation_authorization`
y `res_avaluo`.

### 4. Etiquetado de identificador (`catastro_live` + renderer)
`verificar_catastro_barranquilla` devolvía el atributo `name` del terreno (número
predial nacional de 30 dígitos) como `nupre`, y el capítulo 06 lo imprimía
"`NUPRE catastral`". Se renombra a `numero_predial` y se renderiza como
"`Codigo catastral (terreno, referencia espacial)`": es una intersección espacial
(bbox), no el NUPRE ni el identificador exacto del caso.

### 5. Fuente única de ejecución (`receipts` + alcance)
`build_execution_receipts` expone `catastro` (`exacto`/`espacial`/`consultado`) y
`ctl_adjuntado`. `get_alcance_dt` consume estos campos: la fila "Datos
registrales SNR" refleja el CTL adjuntado (antes decía "PENDIENTE -- Requiere CTL"
aunque el receipt dijera "CTL adjuntado: SÍ"), y "Capa catastral BAQ" refleja la
consulta real (exacto/espacial/no disponible) en vez del texto estático
"REFERENCIAL -- sin consulta en vivo".

### 6. Tipología coherente
La tipología del capítulo 01 refleja la PH detectada desde el CTL
("Apartamento -- Propiedad Horizontal (inferido del CTL)") en vez de "PENDIENTE".

## Dirección del CTL (trazabilidad)

El CTL real (PDF `certificado64640614546464261189306228pdf.pdf`) está en
`~/Downloads`, fuera del workspace; no se pudo capturar su bloque
`DIRECCION DEL INMUEBLE` en esta sesión. Lo que sí se verificó en el fixture
`tests/test_arhiax_re.py` (CTL real sanitizado): `CODIGO CATASTRAL:
080010103000010040001908040002`, `NUPRE: AFT0005BOHA`, `AREA Y COEFICIENTE`.
El fixture no incluye el bloque de dirección. La dirección observada
(`TV 43 # 100 - 50 CONJUNTO RESIDENCIAL NAPOLI APARTAMENTOS ETAPA`) demuestra PH
por "CONJUNTO/APARTAMENTOS" y por "COEFICIENTE" en el CTL. **No se inventa**
"TO 8 AP 430": su procedencia en el Dictus histórico es el dictamen demo
(`dictamen_napoli.py`/`insumos_napoli.py`), no el texto del CTL.

## No se hizo

- No se cambiaron `5.2M / 6.8M`, YAML Lonja, M1/M2/M3, cap_rate ni bandas.
- No se restauró $399.5M ni 70/30.
- No se inició SLICE-002.

## Tests

`tests/test_remediacion_03d2.py` (11 casos): detección de PH sin torre/apartamento,
can_value_property (verificado/no-record/no-ph), fallo observado exacto (PH +
NO_RECORD + unidad None → bloqueado), coherencia de identificadores con receipts e
invariante de valoración.

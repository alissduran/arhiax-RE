# REMEDIATION 03I — Golden Dictus Integrated Acceptance

**Estado: CLOSED — `03I — GOLDEN ACCEPTED WITH NON-BLOCKING FINDINGS`**

## Qué se hizo

Corrida **real** del producto sobre el caso Golden **040-646406** (sin mocks, sin
fixtures de fuente, sin inyección de hechos derivados) y revisión capítulo por
capítulo del dictamen resultante, con comparación contra el dictamen histórico
`ARHIAX_Dictamen_040_646406_NAPOLI_v6_final.pdf`.

- Runner: `scripts/golden_run_03i.py` (única instrumentación: observador de **solo
  lectura** sobre `consistency.ejecutar_gate`; 0 sustituciones de fuente).
- Matrices: `scripts/golden_matrices_03i.py` (cross-chapter + provenance).
- Salidas y evidencia: `docs/forensics/040-646406/golden_03i/`.
- Informe: `docs/forensics/040-646406/golden_03i/GOLDEN_ACCEPTANCE_REPORT.md`.

Ejecutado sobre el commit `acc8a9493a1cfe9dace5d638fb3bf9a0a74cf29f` (03S.1C) con
árbol de trabajo sin cambios de producto. PDF: 14 páginas,
sha256 `4285177665456a92b6023aef75225da7bf3b716a6f11479a4b43e3176dee4d82`.

## Resultado

- Identidad: `MATCH_EXACT` / `VERIFIED_UNIT_IDENTITY` por registro oficial de
  adopción (`identity_authorized=True`), con FMI + predial + NUPRE + dirección con
  unidad (`TO 8 AP 430`).
- Urbanismo: barrio `Miramar` (`VERIFIED_OFFICIAL`), tratamiento `Desarrollo`,
  tipo `Bajo`, altura `8` desde la capa POT viva (no se forzó Consolidación/Nivel 2/11).
- Market: sector `Miramar` `EXACT` a `$6.800.000/m²`, pero `ready=False` por
  **estrato no verificado** → valoración **no emitida** (gate 03H fail-closed).
- Screening: `SCREENING_COMPLETE`, cobertura completa, evidencia **9/9 SEALED**,
  matcher `sanctions-matcher/1.1.0`, parsers `onu/ofac/uk 1.1.0`, snapshots
  `CACHED_FRESH`, 3 sujetos `NO_MATCH`. Sin candidato `MARVAL`: el sujeto real es
  `URBANIZADORA MARVAL S` (sin la variante que lo producía).
- Sin valores inventados: ausentes `Habitacional`, `Estrato 4`, `Nivel 2`,
  `11 pisos`, `6.800.000`, `399.500.000`, `$ 0`, `uso no residencial`,
  `posible lote sin edificación`, `SAGRILAFT: CUMPLE`.

## Hallazgos (no corregidos en este paso: corrida diagnóstica, §27)

| ID | Sev. | Hallazgo |
|---|---|---|
| F1 | ALTA | `TIT_B01` dice "no hay área registral ni catastral" con 58.75 m² presente (`arhia_title/rules.py`) |
| F2 | ALTA | Resumen POT de 6.2 imprime "CONSOLIDACION / DESARROLLO" fijo vs tabla/6.3 `Desarrollo (Bajo) 8` (`dictamen_data.get_pot_summary_dt`) |
| F3 | MEDIA | H-GEO "amenaza baja" con `severidad alta` (`rules.amenazas_pot`) |
| F4 | ALTA (operativa) | Estrato sin resolver (capa con 0 features) → bloquea la valoración |
| F5 | MEDIA | La dirección/unidad del registro oficial no se promueve al modelo canónico |
| F6 | MEDIA | Capa 500 catastro BAQ "servicio sin respuesta" → sin destino económico ni área catastral |
| F7 | BAJA | Nombre del constructor truncado ("URBANIZADORA MARVAL S") por el regex de `legal_analyzer` |
| F8 | BAJA | 8.2 mezcla "sin zona cartografiada" con "amenaza baja" |
| F9 | INFO | El CTL del entorno es copia parcial saneada (sin DIRECCION ni NIT constructor) |
| F10 | INFO | Sin candidato MARVAL con datos reales (comportamiento correcto) |
| F11 | INFO | Costo del avalúo profesional `NEEDS_PRODUCT_SOURCE` (sin cifra impresa) |

## Garantías

- **Cero cambios de producto** en esta slice: solo se corrigió el runner de QA
  (extracción del área por el camino del producto, `index.extraer_datos_de_pdf`).
- Suite offline: **556 passed, 0 failed, 11 deselected**; `compileall` limpio.
- **NO se inició SLICE-002.**

# GOLDEN_CROSS_CHAPTER_MATRIX — 040-646406 (03I)

Fuente de verdad por HECHO y verificación de coherencia entre capítulos.
Generado automáticamente desde el estado interno de la ejecución real y del
texto del PDF emitido.

| FACT | Valor observado | Fuente de verdad | Status | Capítulos |
| --- | --- | --- | --- | --- |
| folio | 040-646406 | CTL (legal_analyzer) + modelo canónico | VERIFIED_REGISTRAL | 01, 05, 16 |
| codigo_catastral | 080010103000010040001908040002 | CTL (CODIGO CATASTRAL) | VERIFIED_REGISTRAL | 01, 06.1, 16 |
| nupre | AFT0005BOHA | CTL (NUPRE) | VERIFIED_REGISTRAL | 01, 06.1, 16 |
| identidad_autorizada | True | Registro oficial de adopción catastral (Anexo 1, Res. GGCD 003) | VERIFIED_UNIT_IDENTITY | 01, 05, 06, 16 |
| direccion | TV 43 # 100 - 50 TO 8 AP 430 (impresa en 01) | record del caso (registro oficial de adopción) — el CTL disponible no  | VERIFIED_OFFICIAL (registro) | 01, 02 |
| direccion_canonica_interna | Pendiente de verificacion | modelo canónico (NO toma la dirección del registro de adopción) | PENDIENTE | (interno) |
| unidad_torre_apartamento | torre=None ap=None unidad=None | modelo canónico (extracción de unidad del CTL) | NO EXTRAÍDA | (interno), 09 (rol) |
| area_registrada | 58.75 | CTL real vía index.extraer_datos_de_pdf | VERIFIED_REGISTRAL | 01, 06.1, 07, 05(Titulux) |
| barrio | Miramar | official POT / Alcaldía | VERIFIED_OFFICIAL | 01, 02, 06.1, 06.2, 07, 16 |
| localidad | 02 | capa unidadesadministrativas (campo localidad) | VERIFIED_OFFICIAL | 02, 06.2 |
| estrato | None | None | UNRESOLVED | 06.1, 07 |
| destino_economico | PENDIENTE | capa 500 / servicio destinoseconomicos | SOURCE_UNAVAILABLE / UNRESOLVED | 06.1, 07(uso) |
| condicion_juridica | None | CTL (inferencia registral) | VERIFIED_REGISTRAL | 01, 06.1 |
| tratamiento_urbanistico | Desarrollo | official_urban_layer | VERIFIED_OFFICIAL | 06.2 (tabla y resumen), 06.3 |
| altura_normativa | 8 | official_urban_layer | VERIFIED_OFFICIAL | 06.2, 06.3 |
| pisos_construidos | PENDIENTE (fuente de construcción no disponible) | capa 310 construcción | SOURCE_UNAVAILABLE | 06.3 |
| sector_metodologico | Miramar | Precio de venta verificado en la constructora del proyecto (unidades ~ | EXACT | 07, 16 |
| value_m2 | 6800000 | Precio de venta verificado en la constructora del proyecto (unidades ~ | EXACT | 07 |
| valuation_authorized | False | identity_authorized AND market_context_authorized | BLOCKED | 07, 16 |
| screening | SCREENING_COMPLETE | ScreeningSummary | COVERAGE_COMPLETE | 05, 09, 16, 16.b |
| evidencia_cadena | SEALED | evidencia HMAC (arhia_sag_screen) | 9/9 | 09.3, 16.b |
| poi | 4 categorías AVAILABLE (3 ítems c/u) | OpenStreetMap / Overpass (motor real) | AVAILABLE | 03, 16.b |
| riesgo_volcanico_sgc | consultado · BAJO | SGC (mapa oficial) | VERIFIED_OFFICIAL | 08.2, 16.b |

## Cross-checks automáticos

| Check | Resultado | Nota |
| --- | --- | --- |
| area registral vs TIT_B01 | FAIL | el capítulo 05 (TIT_B01) afirma 'no hay área registral ni catastral' mientras 6.1 declara 58.75 m² (área registral presente) |
| tratamiento 6.2 (tabla) vs 6.2 (resumen) vs 6.3 | FAIL | la tabla de 6.2 y 6.3 muestran el polígono REAL (Desarrollo/Bajo/8) mientras el resumen POT de 6.2 imprime una cadena fija 'CONSOLIDACION / DESARROLLO (Según polígono POT)' |
| estrato ausente etiquetado como uso no residencial | PASS | el estrato no resuelto se declara PENDIENTE DE VERIFICACIÓN (no se afirma uso no residencial) |
| pisos construidos: 'posible lote'/'sin edificación' indebido | PASS | la fuente de construcción no disponible se declara PENDIENTE, no 'sin edificación' |
| folio/NUPRE/código ausentes del PDF | PASS | folio, NUPRE y código catastral presentes y coherentes en 01/06.1/16 |
| screening 05/09/16 con estados distintos | PASS | 05 (SAG_B01), 09 (estado) y 16.b coinciden en el mismo ScreeningSummary |
| UIAF como columna/lista de screening | PASS | 09 usa ONU · OFAC SDN · UKSL; UIAF solo se explica como canal de reporte |
| titular natural descrito como persona jurídica | PASS | el titular natural no se describe como persona jurídica |
| amenaza baja con severidad ALTA | FAIL | DEFECTO: amenaza 'baja' con severidad ALTA (narrativa genérica, sin causa específica del caso) — §15 |
| cifra $0 como sustituto de 'desconocido' | PASS | la carga no estimable no se imprime como cero |
| tarifa de avalúo arbitraria impresa | PASS | no se imprime tarifa: el costo del avalúo profesional sigue NEEDS_PRODUCT_SOURCE |

## Hechos con DOS valores distintos (regla §22: FAIL)

- `área`: 6.1/07/Titulux usan 58.75 m² (área del CTL) y TIT_B01 afirma que no hay
  área registral → **FAIL**.
- `tratamiento urbanístico`: 6.2 (tabla) / 6.3 usan el polígono real
  (Desarrollo · Bajo · 8) y el resumen de 6.2 imprime 'CONSOLIDACION / DESARROLLO'
  fijo → **FAIL**.
- `estrato`: PENDIENTE en 6.1 y ausente en 07 (MarketContext no autorizado) → coherente
  (un solo valor: no resuelto).
- `destino económico`: PENDIENTE en 6.1 y uso del MarketContext UNRESOLVED → coherente.

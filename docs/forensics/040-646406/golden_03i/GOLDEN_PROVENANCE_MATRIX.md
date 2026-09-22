# GOLDEN_PROVENANCE_MATRIX — 040-646406 (03I)

| FACT | Valor | Fuente | Status | Método | Versión | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| folio | 040-646406 | CTL (legal_analyzer) + modelo canónico | VERIFIED_REGISTRAL | extracción del CTL | legal_analyzer |  |
| codigo_catastral | 080010103000010040001908040002 | CTL (CODIGO CATASTRAL) | VERIFIED_REGISTRAL | identificador exacto del CTL | canonical/03D.1 |  |
| nupre | AFT0005BOHA | CTL (NUPRE) | VERIFIED_REGISTRAL | identificador exacto del CTL | canonical/03D.1 |  |
| identidad_autorizada | True | Registro oficial de adopción catastral (Anexo 1, Res. GGCD 0 | VERIFIED_UNIT_IDENTITY | official_adoption_registry | 03G.1 |  |
| direccion | TV 43 # 100 - 50 TO 8 AP 430 (impresa en 01) | record del caso (registro oficial de adopción) — el CTL disp | VERIFIED_OFFICIAL (registro) | address_normalizer + impresión | 03D/03H.2 |  |
| direccion_canonica_interna | Pendiente de verificacion | modelo canónico (NO toma la dirección del registro de adopci | PENDIENTE | — | canonical |  |
| unidad_torre_apartamento | torre=None ap=None unidad=None | modelo canónico (extracción de unidad del CTL) | NO EXTRAÍDA | — | 03D.2 unidad PH |  |
| area_registrada | 58.75 | CTL real vía index.extraer_datos_de_pdf | VERIFIED_REGISTRAL | regex AREA PRIVADA metros+centímetros | index |  |
| barrio | Miramar | official POT / Alcaldía | VERIFIED_OFFICIAL | capa POT unidadesadministrativas (punto  | 03H.1A |  |
| localidad | 02 | capa unidadesadministrativas (campo localidad) | VERIFIED_OFFICIAL | consolidación | 03H.2 |  |
| estrato | None | None | UNRESOLVED | capa estratificación (0 features en el p | 03H.1A |  |
| destino_economico | PENDIENTE | capa 500 / servicio destinoseconomicos | SOURCE_UNAVAILABLE / UNRESOL | identificador exacto + contexto espacial | 03H.2A |  |
| condicion_juridica | None | CTL (inferencia registral) | VERIFIED_REGISTRAL | legal_analyzer.inferir_condicion_juridic | 03H.2A |  |
| tratamiento_urbanistico | Desarrollo | official_urban_layer | VERIFIED_OFFICIAL | capa planeación (punto geocodificado) | 03H.1A |  |
| altura_normativa | 8 | official_urban_layer | VERIFIED_OFFICIAL | capa planeación | 03H.1A |  |
| pisos_construidos | PENDIENTE (fuente de construcción no disponible) | capa 310 construcción | SOURCE_UNAVAILABLE | consulta espacial | 03H.2 |  |
| sector_metodologico | Miramar | Precio de venta verificado en la constructora del proyecto ( | EXACT | resolución de sector por barrio | 03H |  |
| value_m2 | 6800000 | Precio de venta verificado en la constructora del proyecto ( | EXACT | sector → tasa (ÚNICA autoridad: MarketCo | 03H.1A |  |
| valuation_authorized | False | identity_authorized AND market_context_authorized | BLOCKED | doble gate | 03H.1 |  |
| screening | SCREENING_COMPLETE | ScreeningSummary | COVERAGE_COMPLETE | sanctions-matcher/1.1.0 | matcher sanctions-matcher/1.1.0 |  |
| evidencia_cadena | SEALED | evidencia HMAC (arhia_sag_screen) | 9/9 | c73a3fee8fccce64 | 03S.1C | 09fff1d974a4c01e |
| poi | 4 categorías AVAILABLE (3 ítems c/u) | OpenStreetMap / Overpass (motor real) | AVAILABLE | consulta en radio 2 km | 03F |  |
| riesgo_volcanico_sgc | consultado · BAJO | SGC (mapa oficial) | VERIFIED_OFFICIAL | consulta al servicio SGC | 03H |  |

Fuente primaria de datos: `GOLDEN_INTERNAL_STATE.json` (observado en la
ejecución real) y `GOLDEN_PDF_TEXT.txt` (texto del PDF emitido).

# GOLDEN_PROVENANCE_MATRIX — 03I.1 (040-646406)

Ningún FACT se escribe a mano: cada valor sale del estado observado en la corrida real (observadores de solo lectura) o del texto del PDF.

| Fact | Valor | Fuente | Status | Regla/Versión | Capítulos |
|---|---|---|---|---|---|
| `version_plataforma` | ARHIAX RE v1.4.0 · commit a9e55719 · dictus v1.4.0 · GIS v1.2.0 · Titulux v1.1.0 · reglas v1.3.0 | versioning.VERSION_MATRIX + git rev-parse HEAD | VERIFIED_CODE | a9e55719 | pie de página, 16.b |
| `commit_sha` | a9e55719540f49764ca1ace16fcd9ac6e7a60f52 | git rev-parse HEAD | VERIFIED_CODE | 03I.1 §A | pie de página, 16.b |
| `input_ctl` | certificado64640614546464261189306228pdf.pdf (124345 bytes) | CTL BINARIO entregado por --ctl | ORIGINAL_BINARY | 4493da88f4231a6b | (insumo) |
| `folio` | 040-646406 | CTL (legal_analyzer) + modelo canónico | VERIFIED_REGISTRAL | legal_analyzer | 01, 05, 16 |
| `codigo_catastral` | 080010103000010040001908040002 | CTL (código catastral) | VERIFIED_REGISTRAL | canonical | 01, 06.1, 16 |
| `nupre` | AFT0005BOHA | CTL (NUPRE) | VERIFIED_REGISTRAL | canonical | 01, 06.1, 16 |
| `identidad_confianza` | VERIFIED_UNIT_IDENTITY | modelo canónico | MATCH_EXACT | 03G.1 | 01, 05, 06, 16 |
| `direccion_canonica` | TV 43 # 100 - 50 CONJUNTO RESIDENCIAL NAPOLI APARTAMENTOS ETAPA 3 APARTAMENTO 430 TORRE 8 ETAPA 3 | modelo canónico | NO_VERIFICADA | 03I.1 F5 | 01, 02, 16 |
| `unidad_canonica` | torre=8 ap=430 unidad=APARTAMENTO 430 TORRE 8 | modelo canónico (complemento declarado) | VERIFIED_OFFICIAL | 03I.1 F5 | 01, 09 rol |
| `area_registrada` | 58.75 | CTL real vía index.extraer_datos_de_pdf | VERIFIED_REGISTRAL | index | 01, 06.1, 07, 05 Titulux |
| `barrio` | None | None | UNRESOLVED | 03H.1A | 01, 02, 06.1, 06.2, 07, 16 |
| `estrato` | None | None | UNRESOLVED | 03I.1 F4 | 06.1, 07 |
| `tratamiento_urbanistico` | None | None | UNRESOLVED | 03H.1A | 06.2 tabla, 06.2 resumen, 06.3 |
| `altura_normativa` | None | None | UNRESOLVED | 03H.1A | 06.2, 06.3 |
| `urban_source_mode` | PACKAGED_REFERENCE | UrbanSourceSummary | OBSERVED | 03I.1 F2 | 06.2, 08.1 |
| `destino_economico_render` | Habitacional | servicio catastral (capa 500 / destinos económicos) | UNRESOLVED | 03H.2A | 06.1, 07 uso |
| `condicion_juridica_render` | None | CTL + capa de condición catastral | VERIFIED | 03I.1 J | 01, 06.1 |
| `estrato_render_6_1` | Medio_4 | mismo `estrato` que consume el render de 6.1 | OBSERVED | 03I.1 J | 06.1 |
| `sector_metodologico` | None | None | NO_MATCH | 03H | 07, 16 |
| `value_m2` | None | None | NO_MATCH | 03H.1A | 07 |
| `metodologia_mercado` | lonja_baq_metodologia@0.1-codiseno | lonja_baq_metodologia.yaml | VERIFIED_ARTIFACT | 03I.1 F | 07, 16.b |
| `market_ready` | False | market_context_authorized + market_methodology_id/version | OBSERVED | 03H/03I.1 F | 07, 16 |
| `valuation_authorized` | False | identity_authorized AND market_context_authorized | VERIFIED_UNIT_IDENTITY | 03H.1 | 07, 16 |
| `valor_consolidado` | 0 | método principal PH (m1 comparación de mercado) | NO EMITIDO | 03H.1 | 07 |
| `poi_categorias` | {"Comercio": {"status": "AVAILABLE", "items": 3, "fuentes": ["OSM_OVERPASS"]}, "Educacion": {"status": "AVAILABLE", "items": 3, "fuentes": ["OSM_OVERPASS"]}, "Recreacion": {"status": "AVAILABLE", "items": 3, "fuentes": ["OSM_OVERPASS"]}, "Salud": {"status": "AVAILABLE", "items": 3, "fuentes": ["OSM_OVERPASS"]}} | OSM/Overpass + Photon · intentadas=['OSM_OVERPASS'] · exitosas=['OSM_OVERPASS'] | OBSERVED | 03F | 03, 16.b |
| `riesgo_volcanico` | estado=NO_COVERAGE nivel=NO EVALUADO | SGC (mapa oficial de amenaza volcánica) | OBSERVED | 03I.1 F8 | 08.2, 16.b |
| `screening` | SCREENING_COMPLETE | ScreeningSummary | COVERAGE_COMPLETE | 03S.1/03S.1C | 05, 09, 16, 16.b |
| `evidencia_screening` | 9/9 · cadena=SEALED | evidencia versionada por envelope | SEALED | 03S.1C | 09.3, 16.b |

**Facts hardcodeados: 0**

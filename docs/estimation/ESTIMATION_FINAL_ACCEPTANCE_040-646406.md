# DICTUS ESTIMATION ENGINE v1.0 — ACEPTACIÓN FINAL · folio 040-646406

> **NEXT STEP (no ejecutado en esta ronda):** `REMEASURE BARRANQUILLA SOURCE PACK CORE COVERAGE` — el 403 del geoportal podía resolverse con cabeceras de navegación correctas (medido: la MISMA URL devuelve 200 con `NAV_HEADERS`).

- **Motor:** `dictus-estimation-engine/1.0.0` · integración `dictus-estimation-integration/1.0.0` · golden `dictus-estimation-golden/1.0.0`
- **Políticas nuevas:** `dictus-central-reference-visibility/1.0.0` (visibilidad de la referencia central) · `dictus-evidence-hash/2.0.0` (identidad de la evidencia: contenido estable vs adquisición volátil)
- **Referencia temporal de la estimación:** `2026-10-02`
- **`state`:** `OPEN_WITH_LIMITATIONS` · **`VERIFIED_MARKET_EVIDENCE_GATE`:** `CLOSED` · **calidad:** `INDICATIVE` · **resultado:** `INDICATIVE_ESTIMATE`
- **VEREDICTO:** `DICTUS ESTIMATION ENGINE — INDICATIVE ESTIMATE PRODUCED`

## 1 · COMPUERTAS (literal del motor)

```
ESTIMATION_GATE
  state            = OPEN_WITH_LIMITATIONS
  reasons          =
      - hay información suficiente para una ESTIMACIÓN RAZONABLE, pero la evidencia es INDICATIVE (no alcanza el estándar verificado)
      - soporte económico: EXTERNAL_SOURCE
      - métodos disponibles: M5_AGGREGATED_MARKET_REFERENCE (ninguno autoriza una cifra verificada)
      - el resultado se emite como ESTIMACIÓN INDICATIVA con sus limitaciones declaradas, no como valor verificado
  inputs_available = ['area', 'auditoria_de_entrada', 'contexto', 'estadisticas_externas', 'identidad', 'modelo_legacy', 'tasa_manual', 'tipologia', 'ubicacion']
  inputs_missing   = ['cap_rate', 'comparables', 'costo_reposicion', 'modelo_calibrado', 'referencia_estatica', 'rental_reference']
  conditions_version = dictus-estimation-conditions/1.0.0
VERIFIED_MARKET_EVIDENCE_GATE
  state            = CLOSED
  reasons          = ['ninguna evidencia de mercado alcanza el estándar de fuente externa verificada con procedencia completa', 'referencia de nivel 3 fuera de esta compuerta: nivel 3 agrega por localidad y banda de área: NO acredita la unidad']
  evidencia_agregada_no_atribuible = [{"clase": "LEVEL_3_AGGREGATED_MARKET_REFERENCES", "declarado": "BAQ_OBS_VALORESM2_AREA", "blockers": ["nivel 3 agrega por localidad y banda de área: NO acredita la unidad"]}]
EVIDENCE_QUALITY_GATE
  level   = INDICATIVE
  POR QUÉ ES ESE NIVEL (razones literales del motor):
      - identidad: HIGH — identidad resuelta con origen COMPUTED_FROM_SOURCES
      - ubicación: HIGH — ubicación con estado OFFICIAL_PREDIO
      - área: HIGH — área declarada con origen COMPUTED_FROM_SOURCES
      - tipología: HIGH — tipología verificada (VERIFIED_REGISTRAL)
      - evidencia de mercado: LOW — 0 comparables usados de 0 · 1 referencia(s) agregada(s) de nivel 3 (agregan por sector y banda de área: NO acreditan la unidad)
      - vigencia: ABSENT — sin fecha declarada en la evidencia de mercado
      - dispersión: ABSENT — dispersión no medible (menos de 2 comparables)
      - modelo: ABSENT
      - techo por dimensión: area=HIGH, composicion=HIGH, identidad=HIGH, mercado=INDICATIVE, tipologia=HIGH, ubicacion=HIGH
  LAS DIEZ DIMENSIONES DEL CONTRATO (§13/§14):
      identity_quality           = "HIGH"
      location_quality           = "HIGH"
      market_evidence_quality    = "LOW"
      market_freshness           = {"level": "ABSENT", "meses": null, "detalle": "sin fecha declarada en la evidencia de mercado"}
      comparable_quality         = "ABSENT"
      comparable_count           = 0
      typology_quality           = "HIGH"
      area_quality               = "HIGH"
      model_quality              = "ABSENT"
      dispersion                 = {"level": "ABSENT", "cv": null, "n": 0, "detalle": "dispersión no medible (menos de 2 comparables)"}
```

## 2 · `ESTIMATION_RESULT` (literal)

```
status           = INDICATIVE_ESTIMATE
status_label     = ESTIMACIÓN INDICATIVA
range_low        = 130000000
range_high       = 490000000
central_estimate = 310000000
value_m2_central = 5206395.13
confidence_label = INDICATIVE (impreso: INDICATIVA)
methods_used     = ['M5_AGGREGATED_MARKET_REFERENCE']
methods_rejected = ['M1_MARKET_COMPARISON', 'M2_REPLACEMENT_COST', 'M3_INCOME_CAPITALIZATION', 'M4_CALIBRATED_MODEL_PRIOR']
origin_composition = {"composicion_version": "dictus-origin-composition/1.0.0", "origin": "EXTERNAL_SOURCE", "origin_etiqueta": "evidencia de una fuente externa citada", "regla": "R6_CLASE_UNICA", "regla_detalle": "un solo insumo económico declarado: la composición es su propia clase", "clases_usadas": ["EXTERNAL_SOURCE"], "cuenta_por_clase": {"EXTERNAL_SOURCE": 1}, "clases_excluidas": ["MANUAL_CONFIG", "LEGACY_MODEL_PRIOR"], "peso_resultante": "ALTO", "sostiene_estimacion": true, "abre_verified_gate": true, "techo_calidad": "HIGH", "excluidos": [{"clase": "MANUAL_CONFIG", "motivo": "declarado y NO usado como insumo del cálculo", "blockers": ["valor declarado a mano por la corrida: NO sostiene una estimación productiva"]}, {"clase": "LEGACY_MODEL_PRIOR", "motivo": "declarado y NO usado como insumo del cálculo", "blockers": ["prior legacy del modelo: se conserva por compatibilidad y NO sostiene ninguna estimación productiva"]}], "no_lavado": true, "motivos": ["un solo insumo económico declarado: la composición es su propia clase", "insumos declarados que NO participan del cálculo: LEGACY_MODEL_PRIOR, MANUAL_CONFIG (no se cuentan como fuente)"], "hash": "f741b5dc32c2c6b90f66149a02aa239ac48fae9397c629471c53f378c78ba173"}
hash_payload     = 1dd745d4b6612142399c53718edba93f3708b36f259ef0ef9ecffca74d548529
generated_at     = 2026-10-02T16:54:30.576839+00:00
central_reference_visibility = {
  "policy_version": "dictus-central-reference-visibility/1.0.0",
  "state": "DEEMPHASIZED",
  "imprime_la_cifra": true,
  "reasons": [
    "la base es una referencia AGREGADA de nivel 3: agrega por sector y banda de área y NO acredita esta unidad",
    "la fuente NO declara el tamaño de la muestra (N) del análisis: no se rellena",
    "0 comparables usados: ninguna observación acredita la unidad",
    "amplitud relativa ±58.06% ≥ ±30%",
    "el extremo superior es 3.77× el inferior (≥ 2.5×)",
    "nivel de evidencia INDICATIVE: la cifra no es un valor verificado"
  ],
  "reasons_short": [
    "no acredita la unidad",
    "sin muestra (N) declarada",
    "sin comparables",
    "rango muy ancho (±58.06%)",
    "banda de 3.77× entre extremos",
    "evidencia INDICATIVE"
  ],
  "reason_short": "no acredita la unidad · sin muestra (N) declarada",
  "umbrales_aplicados": {
    "semi_ancho_oculta": 0.6,
    "semi_ancho_deenfatiza": 0.3,
    "ratio_oculta": 4.0,
    "ratio_deenfatiza": 2.5,
    "comparables_minimo_visible": 3
  },
  "fundamento": "Política de producto VERSIONADA, declarada y auditable: la referencia central es secundaria respecto del rango (§12), así que su visibilidad depende de cuánto la sostiene la evidencia —amplitud relativa, salto entre extremos, `sample_size` declarado, nivel de calidad, nº de comparables y naturaleza AGREGADA de la referencia de nivel 3—. Los umbrales NO están calibrados empíricamente: son una decisión declarada, revisable en una versión posterior.",
  "calibrada_empiricamente": false,
  "entradas": {
    "semi_ancho_relativo": 0.5806451612903226,
    "ratio_high_low": 3.769230769230769,
    "sample_size": null,
    "sample_size_declarado": false,
    "comparables_usados": 0,
    "evidence_quality": "INDICATIVE",
    "referencia_agregada_level_3": true,
    "central": 310000000,
    "low": 130000000,
    "high": 490000000
  }
}
```

## 3 · OBJETO COMPLETO DE `M5_AGGREGATED_MARKET_REFERENCE`

```json
{
  "method_id": "M5_AGGREGATED_MARKET_REFERENCE",
  "method_name": "REFERENCIA AGREGADA OFICIAL POR LOCALIDAD Y BANDA DE ÁREA",
  "methods_version": "dictus-estimation-methods/1.0.0",
  "status": "AVAILABLE",
  "origin": "EXTERNAL_SOURCE",
  "origin_basis": "la evidencia base es UNA referencia externa citada (LEVEL_3_AGGREGATED_MARKET_REFERENCES con procedencia HTTP completa); la transformación de DICTUS viaja en `derivation`",
  "derivation": {
    "type": "MIDPOINT_OF_SOURCE_RANGE",
    "formula": "(min + max) / 2",
    "source_count": 1,
    "source_ids": [
      "BAQ_OBS_VALORESM2_AREA"
    ],
    "origin": "DERIVED_FROM_EXTERNAL_SOURCE",
    "declaracion": "punto medio del rango publicado por la fuente: DERIVACIÓN determinista de UNA sola fuente externa. NO es una composición de fuentes (COMPUTED_FROM_SOURCES exige ≥2) y NO es un valor publicado por la fuente.",
    "no_es_composicion_de_fuentes": true,
    "no_es_valor_de_la_fuente": true
  },
  "confidence": "BAJA",
  "central_reference": {
    "value_m2": 5206395.13,
    "moneda": "COP",
    "unidad": "COP/m2",
    "derivation": {
      "type": "MIDPOINT_OF_SOURCE_RANGE",
      "formula": "(min + max) / 2",
      "source_count": 1,
      "source_ids": [
        "BAQ_OBS_VALORESM2_AREA"
      ],
      "origin": "DERIVED_FROM_EXTERNAL_SOURCE",
      "declaracion": "punto medio del rango publicado por la fuente: DERIVACIÓN determinista de UNA sola fuente externa. NO es una composición de fuentes (COMPUTED_FROM_SOURCES exige ≥2) y NO es un valor publicado por la fuente.",
      "no_es_composicion_de_fuentes": true,
      "no_es_valor_de_la_fuente": true
    },
    "visibility": "DEEMPHASIZED",
    "visibility_policy": {
      "policy_version": "dictus-central-reference-visibility/1.0.0",
      "imprime_la_cifra": true,
      "reasons": [
        "la base es una referencia AGREGADA de nivel 3: agrega por sector y banda de área y NO acredita esta unidad",
        "la fuente NO declara el tamaño de la muestra (N) del análisis: no se rellena",
        "0 comparables usados: ninguna observación acredita la unidad",
        "amplitud relativa ±58.06% ≥ ±30%",
        "el extremo superior es 3.77× el inferior (≥ 2.5×)",
        "nivel de evidencia INDICATIVE: la cifra no es un valor verificado"
      ],
      "umbrales_aplicados": {
        "semi_ancho_oculta": 0.6,
        "semi_ancho_deenfatiza": 0.3,
        "ratio_oculta": 4.0,
        "ratio_deenfatiza": 2.5,
        "comparables_minimo_visible": 3
      },
      "calibrada_empiricamente": false
    },
    "no_es_valor_de_la_fuente": true,
    "no_es_valor_de_la_unidad": true
  },
  "central_reference_visibility": {
    "policy_version": "dictus-central-reference-visibility/1.0.0",
    "state": "DEEMPHASIZED",
    "imprime_la_cifra": true,
    "reasons": [
      "la base es una referencia AGREGADA de nivel 3: agrega por sector y banda de área y NO acredita esta unidad",
      "la fuente NO declara el tamaño de la muestra (N) del análisis: no se rellena",
      "0 comparables usados: ninguna observación acredita la unidad",
      "amplitud relativa ±58.06% ≥ ±30%",
      "el extremo superior es 3.77× el inferior (≥ 2.5×)",
      "nivel de evidencia INDICATIVE: la cifra no es un valor verificado"
    ],
    "reasons_short": [
      "no acredita la unidad",
      "sin muestra (N) declarada",
      "sin comparables",
      "rango muy ancho (±58.06%)",
      "banda de 3.77× entre extremos",
      "evidencia INDICATIVE"
    ],
    "reason_short": "no acredita la unidad · sin muestra (N) declarada",
    "umbrales_aplicados": {
      "semi_ancho_oculta": 0.6,
      "semi_ancho_deenfatiza": 0.3,
      "ratio_oculta": 4.0,
      "ratio_deenfatiza": 2.5,
      "comparables_minimo_visible": 3
    },
    "fundamento": "Política de producto VERSIONADA, declarada y auditable: la referencia central es secundaria respecto del rango (§12), así que su visibilidad depende de cuánto la sostiene la evidencia —amplitud relativa, salto entre extremos, `sample_size` declarado, nivel de calidad, nº de comparables y naturaleza AGREGADA de la referencia de nivel 3—. Los umbrales NO están calibrados empíricamente: son una decisión declarada, revisable en una versión posterior.",
    "calibrada_empiricamente": false,
    "entradas": {
      "semi_ancho_relativo": 0.5806451612903226,
      "ratio_high_low": 3.769230769230769,
      "sample_size": null,
      "sample_size_declarado": false,
      "comparables_usados": 0,
      "evidence_quality": "INDICATIVE",
      "referencia_agregada_level_3": true,
      "central": 310000000,
      "low": 130000000,
      "high": 490000000
    }
  },
  "result": {
    "value_m2": 5206395.135,
    "basis": "punto medio del rango oficial aplicado al área del sujeto: DERIVACIÓN EXPLÍCITA de DICTUS, no un valor de la fuente",
    "referencia_central_del_rango": true,
    "derivation": {
      "type": "MIDPOINT_OF_SOURCE_RANGE",
      "formula": "(min + max) / 2",
      "source_count": 1,
      "source_ids": [
        "BAQ_OBS_VALORESM2_AREA"
      ],
      "origin": "DERIVED_FROM_EXTERNAL_SOURCE",
      "declaracion": "punto medio del rango publicado por la fuente: DERIVACIÓN determinista de UNA sola fuente externa. NO es una composición de fuentes (COMPUTED_FROM_SOURCES exige ≥2) y NO es un valor publicado por la fuente.",
      "no_es_composicion_de_fuentes": true,
      "no_es_valor_de_la_fuente": true
    },
    "derivacion": "punto medio del rango oficial (min_valor_m2 + max_valor_m2) / 2",
    "origen_tipo": "DERIVED_FROM_EXTERNAL_SOURCE",
    "origen_evidencia_base": "EXTERNAL_SOURCE",
    "fuentes": [
      {
        "proveedor": "Alcaldía Distrital de Barranquilla — geoportal miciudad (servidor ArcGIS REST)",
        "fecha": "2026-09-30",
        "referencia": "valoresm2_area/MapServer/1",
        "sha256": "d514aa27fc3fb79b6323ccdfdb7d322b03a738342dc11dceb79fbebde562abd4"
      }
    ],
    "no_es_valor_de_la_fuente": true,
    "no_es_valor_de_la_unidad": true
  },
  "range": {
    "low": 2222222.22,
    "high": 8190568.05,
    "basis": "banda oficial declarada por la fuente (min/max LITERALES)"
  },
  "result_range": {
    "low": 2222222.22,
    "high": 8190568.05,
    "basis": "banda oficial declarada por la fuente (min/max LITERALES)"
  },
  "banda_oficial": {
    "min": 2222222.22,
    "max": 8190568.05,
    "unidad": "COP/m2",
    "banda_area_m2": "36-60",
    "area_sujeto_m2": 58.75,
    "contiene_el_area_del_sujeto": true,
    "reference_id": "BAQ_OBS_VALORESM2_AREA/L1/Norte - centro histórico",
    "source_id": "BAQ_OBS_VALORESM2_AREA",
    "evidence_hash": "6a307f15e38cba0c4edfd02111589fe6620a22169e3a3d95f28e7d7e2331060b",
    "sha256": "d514aa27fc3fb79b6323ccdfdb7d322b03a738342dc11dceb79fbebde562abd4"
  },
  "dispersion": {
    "cv": 0.573174497444286,
    "n": null,
    "basis": "semi-amplitud relativa de la banda oficial: no se inventa una dispersión de comparables"
  },
  "inputs": {
    "reference_id": "BAQ_OBS_VALORESM2_AREA/L1/Norte - centro histórico",
    "evidence_hash": "6a307f15e38cba0c4edfd02111589fe6620a22169e3a3d95f28e7d7e2331060b",
    "source_id": "BAQ_OBS_VALORESM2_AREA",
    "nivel": "LEVEL_3_AGGREGATED_MARKET_REFERENCES",
    "service_url": "https://miciudad.barranquilla.gov.co/gis/rest/services/observatorio/valoresm2_area/MapServer/1/query?f=json&outFields=%2A&returnGeometry=false&geometry=-74.8375696549899%2C11.006055954316363&geometryType=esriGeometryPoint&spatialRel=esriSpatialRelIntersects&inSR=4326&where=1%3D1",
    "consultado_en": "2026-09-30T16:41:08+00:00",
    "http": 200,
    "bytes": 740,
    "sha256": "d514aa27fc3fb79b6323ccdfdb7d322b03a738342dc11dceb79fbebde562abd4",
    "metodologia_declarada": "Muestra el resultado del análisis de las compraventas inmobiliarias registradas por la Superintendencia de Notariado y Registro durante el periodo de enero a mayo de 2026. La información muestra, para cada localidad, los rangos de valores mínimos y máximos agrupados por áreas.",
    "sector_referencia": "Norte - centro histórico",
    "banda_area_m2": "36-60",
    "area_sujeto_m2": 58.75,
    "rango_declarado": {
      "min": 2222222.22,
      "max": 8190568.05,
      "unidad": "COP/m2",
      "basis": "min/max literales de la fuente"
    },
    "sample_size": null,
    "sample_size_declarado": false,
    "vigencia_declarada": {
      "effective_from": null,
      "effective_to": null,
      "basis": "descripción del servicio",
      "precision": "TEXTO",
      "texto_literal": "Muestra el resultado del análisis de las compraventas inmobiliarias registradas por la Superintendencia de Notariado y Registro durante el periodo de enero a mayo de 2026. La información muestra, para cada localidad, los rangos de valores mínimos y máximos agrupados por áreas."
    },
    "provenance": {
      "source_id": "BAQ_OBS_VALORESM2_AREA",
      "proveedor": "Alcaldía Distrital de Barranquilla — geoportal miciudad (servidor ArcGIS REST)",
      "fecha": "2026-09-30",
      "referencia": "valoresm2_area/MapServer/1",
      "sha256": "d514aa27fc3fb79b6323ccdfdb7d322b03a738342dc11dceb79fbebde562abd4",
      "url": "https://miciudad.barranquilla.gov.co/gis/rest/services/observatorio/valoresm2_area/MapServer/1/query?f=json&outFields=%2A&returnGeometry=false&geometry=-74.8375696549899%2C11.006055954316363&geometryType=esriGeometryPoint&spatialRel=esriSpatialRelIntersects&inSR=4326&where=1%3D1",
      "consultado_en": "2026-09-30T16:41:08+00:00",
      "http": 200,
      "bytes": 740,
      "server": "cloudflare",
      "cf_ray": "a434ac712a2221b7-BOG"
    },
    "limitaciones_declaradas": [
      "el rango agregado NO acredita una unidad: agrega por localidad y banda de área",
      "la fuente NO declara el tamaño de la muestra (N) del análisis",
      "la vigencia es a nivel de MES según el texto de la fuente, no una fecha exacta por registro"
    ]
  },
  "reason": "referencia agregada oficial BAQ_OBS_VALORESM2_AREA (Norte - centro histórico · banda 36-60 m² ⊇ 58.75 m²): rango oficial 2,222,222.22–8,190,568.05 COP/m². Agrega por localidad y banda de área: NO acredita la unidad y su techo es INDICATIVE",
  "adjustments": [
    {
      "tipo": "promedio aritmético de los extremos",
      "estado": "NO_APLICADO",
      "detalle": "la fuente declara un rango: el rango de la fuente es el rango. El punto medio se declara como DERIVACIÓN central de DICTUS (DERIVED_FROM_EXTERNAL_SOURCE: una sola fuente externa, declarada en `derivation`), no como valor de la fuente"
    },
    {
      "tipo": "división por el área del sujeto",
      "estado": "NO_APLICADO",
      "detalle": "no se deriva un precio/m² de ningún valor total: la referencia ya está expresada por m²"
    },
    {
      "tipo": "traslado de la unidad al sector",
      "estado": "NO_APLICADO",
      "detalle": "la referencia NO se corrige por posición, piso, vista ni estado: esa incertidumbre la absorbe el ANCHO del rango, no un ajuste inventado"
    },
    {
      "tipo": "muestra (N) del análisis",
      "estado": "NO_APLICADO",
      "detalle": "la fuente NO publica el tamaño de muestra: no se rellena; la ausencia degrada la calidad y viaja en las limitaciones"
    }
  ]
}
```

Los CAMPOS EXIGIDOS POR LA ACEPTACIÓN (§6), con su nombre de contrato y su valor literal:

```
method_id                    = "M5_AGGREGATED_MARKET_REFERENCE"
status                       = "AVAILABLE"
origin                       = "EXTERNAL_SOURCE"
derivation                   = {"type": "MIDPOINT_OF_SOURCE_RANGE", "formula": "(min + max) / 2", "source_count": 1, "source_ids": ["BAQ_OBS_VALORESM2_AREA"], "origin": "DERIVED_FROM_EXTERNAL_SOURCE", "declaracion": "punto medio del rango publicado por la fuente: DERIVACIÓN determinista de UNA sola fuente externa. NO es una composición de fuentes (COMPUTED_FROM_SOURCES exige ≥2) y NO es un valor publicado por la fuente.", "no_es_composicion_de_fuentes": true, "no_es_valor_de_la_fuente": true}
confidence                   = "BAJA"
source_id                    = "BAQ_OBS_VALORESM2_AREA"
reference_id                 = "BAQ_OBS_VALORESM2_AREA/L1/Norte - centro histórico"
area_subject                 = 58.75
area_band                    = "36-60"
source_range_m2              = {"min": 2222222.22, "max": 8190568.05, "unidad": "COP/m2", "basis": "min/max literales de la fuente"}
result_range                 = {"low": 2222222.22, "high": 8190568.05, "basis": "banda oficial declarada por la fuente (min/max LITERALES)"}
central_reference            = {"value_m2": 5206395.13, "moneda": "COP", "unidad": "COP/m2", "derivation": {"type": "MIDPOINT_OF_SOURCE_RANGE", "formula": "(min + max) / 2", "source_count": 1, "source_ids": ["BAQ_OBS_VALORESM2_AREA"], "origin": "DERIVED_FROM_EXTERNAL_SOURCE", "declaracion": "punto medio del rango publicado por la fuente: DERIVACIÓN determinista de UNA sola fuente externa. NO es una composición de fuentes (COMPUTED_FROM_SOURCES exige ≥2) y NO es un valor publicado por la fuente.", "no_es_composicion_de_fuentes": true, "no_es_valor_de_la_fuente": true}, "visibility": "DEEMPHASIZED", "visibility_policy": {"policy_version": "dictus-central-reference-visibility/1.0.0", "imprime_la_cifra": true, "reasons": ["la base es una referencia AGREGADA de nivel 3: agrega por sector y banda de área y NO acredita esta unidad", "la fuente NO declara el tamaño de la muestra (N) del análisis: no se rellena", "0 comparables usados: ninguna observación acredita la unidad", "amplitud relativa ±58.06% ≥ ±30%", "el extremo superior es 3.77× el inferior (≥ 2.5×)", "nivel de evidencia INDICATIVE: la cifra no es un valor verificado"], "umbrales_aplicados": {"semi_ancho_oculta": 0.6, "semi_ancho_deenfatiza": 0.3, "ratio_oculta": 4.0, "ratio_deenfatiza": 2.5, "comparables_minimo_visible": 3}, "calibrada_empiricamente": false}, "no_es_valor_de_la_fuente": true, "no_es_valor_de_la_unidad": true}
central_reference_visibility = {"policy_version": "dictus-central-reference-visibility/1.0.0", "state": "DEEMPHASIZED", "imprime_la_cifra": true, "reasons": ["la base es una referencia AGREGADA de nivel 3: agrega por sector y banda de área y NO acredita esta unidad", "la fuente NO declara el tamaño de la muestra (N) del análisis: no se rellena", "0 comparables usados: ninguna observación acredita la unidad", "amplitud relativa ±58.06% ≥ ±30%", "el extremo superior es 3.77× el inferior (≥ 2.5×)", "nivel de evidencia INDICATIVE: la cifra no es un valor verificado"], "reasons_short": ["no acredita la unidad", "sin muestra (N) declarada", "sin comparables", "rango muy ancho (±58.06%)", "banda de 3.77× entre extremos", "evidencia INDICATIVE"], "reason_short": "no acredita la unidad · sin muestra (N) declarada", "umbrales_aplicados": {"semi_ancho_oculta": 0.6, "semi_ancho_deenfatiza": 0.3, "ratio_oculta": 4.0, "ratio_deenfatiza": 2.5, "comparables_minimo_visible": 3}, "fundamento": "Política de producto VERSIONADA, declarada y auditable: la referencia central es secundaria respecto del rango (§12), así que su visibilidad depende de cuánto la sostiene la evidencia —amplitud relativa, salto entre extremos, `sample_size` declarado, nivel de calidad, nº de comparables y naturaleza AGREGADA de la referencia de nivel 3—. Los umbrales NO están calibrados empíricamente: son una decisión declarada, revisable en una versión posterior.", "calibrada_empiricamente": false, "entradas": {"semi_ancho_relativo": 0.5806451612903226, "ratio_high_low": 3.769230769230769, "sample_size": null, "sample_size_declarado": false, "comparables_usados": 0, "evidence_quality": "INDICATIVE", "referencia_agregada_level_3": true, "central": 310000000, "low": 130000000, "high": 490000000}}
sample_size                  = null
provenance                   = {"source_id": "BAQ_OBS_VALORESM2_AREA", "proveedor": "Alcaldía Distrital de Barranquilla — geoportal miciudad (servidor ArcGIS REST)", "fecha": "2026-09-30", "referencia": "valoresm2_area/MapServer/1", "sha256": "d514aa27fc3fb79b6323ccdfdb7d322b03a738342dc11dceb79fbebde562abd4", "url": "https://miciudad.barranquilla.gov.co/gis/rest/services/observatorio/valoresm2_area/MapServer/1/query?f=json&outFields=%2A&returnGeometry=false&geometry=-74.8375696549899%2C11.006055954316363&geometryType=esriGeometryPoint&spatialRel=esriSpatialRelIntersects&inSR=4326&where=1%3D1", "consultado_en": "2026-09-30T16:41:08+00:00", "http": 200, "bytes": 740, "server": "cloudflare", "cf_ray": "a434ac712a2221b7-BOG"}
limitations                  = ["el rango agregado NO acredita una unidad: agrega por localidad y banda de área", "la fuente NO declara el tamaño de la muestra (N) del análisis", "la vigencia es a nivel de MES según el texto de la fuente, no una fecha exacta por registro"]
```

## 4 · `CONTADORES` (§39)

```
market_observations_count  = 1
comparables_accepted       = 0
comparables_rejected       = 0
origins_used               = ['EXTERNAL_SOURCE']
manual_inputs_used         = 0   [ACEPTADO]
legacy_priors_used         = 0   [ACEPTADO]
market_observations_detail = {"comparables_declarados": 0, "estadisticas_agregadas_externas": 1, "cosecha_municipal_incorporada": true}
origin_composition         = "EXTERNAL_SOURCE"
origin_rule                = "R6_CLASE_UNICA"
manual_inputs_declared     = 1
legacy_priors_declared     = 1
declarados_y_excluidos     = ["MANUAL_CONFIG", "LEGACY_MODEL_PRIOR"]
origins_used_count         = 1
comparables_declarados     = 0
estadisticas_externas      = 1
```

Aceptación dura: `manual inputs used = 0` · `legacy priors used = 0` · clases EXCLUIDAS = `['MANUAL_CONFIG', 'LEGACY_MODEL_PRIOR']` · `399.500.000` no aparece ni como entrada ni como salida (sólo vive en el histórico forense, con `usado_como_input = False`).

## 5 · `SOURCES` DEL RESULTADO (procedencia real)

```json
[
  {
    "source_id": "BAQ_OBS_VALORESM2_AREA",
    "proveedor": "Alcaldía Distrital de Barranquilla — geoportal miciudad (servidor ArcGIS REST)",
    "referencia": "valoresm2_area/MapServer/1",
    "fecha": "2026-09-30",
    "sha256": "d514aa27fc3fb79b6323ccdfdb7d322b03a738342dc11dceb79fbebde562abd4",
    "es_fuente_no_acreditada": false
  }
]
```

- `BAQ_OBS_VALORESM2_AREA` presente: `True`
- rótulos prohibidos presentes en `SOURCES`: `[]` (debe ser `[]`)
- identidad de la evidencia · `BAQ_OBS_VALORESM2_AREA`: `content_hash = 6a307f15e38cba0c4edfd02111589fe6620a22169e3a3d95f28e7d7e2331060b` (ESTABLE) · `payload_sha256 = d514aa27fc3fb79b6323ccdfdb7d322b03a738342dc11dceb79fbebde562abd4` · `acquisition_id = ACQ-BAQ_OBS_VALORESM2_AREA-45be72ac6ef5` · `evidence_hash = 6a307f15e38cba0c4edfd02111589fe6620a22169e3a3d95f28e7d7e2331060b` · `sample_size = None` (NO se rellena)

## 6 · RANGO Y VISIBILIDAD DE LA REFERENCIA CENTRAL

- **`RANGO = [130000000, 490000000]`** (salida PRIMARIA) · `central = 310000000` · ancho `±58.06%` · `clamp = DENTRO_DE_BANDA`
- Banda oficial usada: `BAQ_OBS_VALORESM2_AREA` · `reference_id = BAQ_OBS_VALORESM2_AREA/L1/Norte - centro histórico` · min/max LITERALES `2222222.22`–`8190568.05` COP/m² · área del sujeto `58.75 m²` → bordes redondeados HACIA FUERA `130000000` / `490000000`
- `semi_ancho_calculado = 0.51` vs `semi_ancho_relativo` EFECTIVO `0.5806451612903226`: el ancho calculado NO estrecha el rango publicado.
- **`central_reference_visibility = DEEMPHASIZED`** · `imprime_la_cifra = True` · política `dictus-central-reference-visibility/1.0.0` · `calibrada_empiricamente = False`
- Umbrales APLICADOS (declarados, ninguno escondido): `{"semi_ancho_oculta": 0.6, "semi_ancho_deenfatiza": 0.3, "ratio_oculta": 4.0, "ratio_deenfatiza": 2.5, "comparables_minimo_visible": 3}`
- Entradas de la política: `{"semi_ancho_relativo": 0.5806451612903226, "ratio_high_low": 3.769230769230769, "sample_size": null, "sample_size_declarado": false, "comparables_usados": 0, "evidence_quality": "INDICATIVE", "referencia_agregada_level_3": true, "central": 310000000, "low": 130000000, "high": 490000000}`
- Razones de la política:
    - la base es una referencia AGREGADA de nivel 3: agrega por sector y banda de área y NO acredita esta unidad
    - la fuente NO declara el tamaño de la muestra (N) del análisis: no se rellena
    - 0 comparables usados: ninguna observación acredita la unidad
    - amplitud relativa ±58.06% ≥ ±30%
    - el extremo superior es 3.77× el inferior (≥ 2.5×)
    - nivel de evidencia INDICATIVE: la cifra no es un valor verificado

## 7 · ESCENARIO A/B · MISMO EXPEDIENTE, ÚNICA DIFERENCIA = EVIDENCIA LEVEL 3

| escenario | ESTIMATION_GATE | `VERIFIED_MARKET_EVIDENCE_GATE` | calidad | status | origen | rango | razón principal |
|---|---|---|---|---|---|---|---|
| CON cosecha municipal (real) | OPEN_WITH_LIMITATIONS | CLOSED | INDICATIVE | INDICATIVE_ESTIMATE | EXTERNAL_SOURCE | [130000000, 490000000] | hay información suficiente para una ESTIMACIÓN RAZONABLE, pero la evidencia es INDICATIVE (no alcanza el están |
| SIN cosecha municipal (contraste) | CLOSED | CLOSED | INSUFFICIENT | NOT_ESTIMABLE | NOT_PRODUCTIVE | [None, None] | no se cumplen las condiciones mínimas de estimación: |

- **CON cosecha municipal (real)** · contadores: `{"market_observations_count": 1, "comparables_accepted": 0, "comparables_rejected": 0, "origins_used": ["EXTERNAL_SOURCE"], "manual_inputs_used": 0, "legacy_priors_used": 0}`
- **SIN cosecha municipal (contraste)** · contadores: `{"market_observations_count": 0, "comparables_accepted": 0, "comparables_rejected": 0, "origins_used": [], "manual_inputs_used": 0, "legacy_priors_used": 0}`

La ÚNICA diferencia material entre A y B es la incorporación de la referencia agregada de `LEVEL_3_AGGREGATED_MARKET_REFERENCES`; en los dos escenarios `manual inputs used = 0`, `legacy priors used = 0` y `VERIFIED_MARKET_EVIDENCE_GATE = CLOSED`.

## 8 · `P1_TEXT` Y `P6_TEXT` (extraídos LITERALMENTE del PDF regenerado)

Ejecutivo: `DICTUS_EJECUTIVO_040-646406.pdf` · sha256 `0e2a87c15d60eeae62ec9f2da2d45fc9fdb40f7142fede084cb73c7b129d8bf7` · 6 páginas

```
P1_TEXT
DICTUS DECISIÓN DEL INMUEBLE DX-040-646406-20261002 Página 1 de 6 · ejecutivo DECISIÓN DEL INMUEBLE TV 43 # 100 - 50 CONJUNTO RESIDENCIAL NAPOLI APARTAMENTOS ETAPA 3 APARTAMENTO 430 TORRE 8 E… INFORMACIÓN GENERAL DIRECCIÓN TV 43 # 100 - 50 CONJUNTO RESIDENC… MATRÍCULA 040-646406 CIUDAD Barranquilla BARRIO Miramar ÁREA 58.75 m² USO Habitacional RÉGIMEN Propiedad Horizontal VALORACIÓN DE LA CORRIDA no habilitada (evidencia no verificada) identidad · títulos · contrapartes · territorio · entorno · valoración ESTADO POR DOMINIO IDENTIDAD VERIFICADO TÍTULOS CON CONDICIONES CONTRAPARTES SIN COINCIDENCIAS TERRITORIO REQUIERE VALIDACIÓN VALORACIÓN CORRIDA NO DISPONIBLE ESTIMACIÓN ECONÓMICA DICTUS · ESTIMACIÓN INDICATIVA Rango: $ 130.000.000 – $ 490.000.000 · Referencia central: $ 310.000.000 (secundaria · no acredita la unidad · sin muestra (N) declarada) · Confianza: INDICATIVA Base: ESTIMACIÓN INDICATIVA · ESTIMATION_GATE = OPEN_WITH_LIMITATIONS · evidencia utilizada: Alcaldía Distrital de Barranquilla — geoportal miciudad (servidor ArcGIS REST) conflictos entre versiones del expediente COHERENCIA DE LA INFORMACIÓN COHERENCIA DE INFORMACIÓN — 6 atributo(s) requieren reconciliación histórica AFECTA A: COMPRADOR, INMOBILIARIA, BANCO / FINANCIADOR, ASEGURADORA DE TÍTULO Detalle por atributo: página 4 → El expediente del mismo inmueble produjo valores distintos entre versiones. No es un riesgo del inmueble: es calidad de la información. · Altura / edificabilidad: 8 / 11 · Coordenada del predio: 10.9870 -74.8115 / 11.00538 -74.83862 · Amenaza por remoción en masa: Sin afectacion / AMENAZA BAJA · Titularidad: Duran Bacca Alisso / DURAN BACCA ALISSO · Tratamiento urbanístico: CONSOLIDACION URBA / CONSOLIDACION -- N · Uso del suelo (POT): ACTIVIDAD CENTRAL / ACTIVIDAD URBANA R qué encontró DICTUS · qué decisión produce · a quién afecta · qué hacer DECISION BOARD TEMA HALLAZGO · QUÉ ENCONTRÓ DICTUS DECISIÓN DICTUS TÍTULO ALTO · El folio registra una HIPOTECA VIGENTE inscrita el 22-01-2024 (anot. 007… PROCEDER CON CONDICIONES AFECTA A: COMPRADOR, VENDEDOR, INMOBILIARIA, BANCO / FINANCIADOR ACCIÓN: Para vender, refinanciar o dar este inmueble en garantia, primero hay que gestionar el credito con BANCO DE BOGOTA S.A y tramitar la CANCELACION de la hipoteca ante la O… +1 hallazgo(s) del mismo tema con su propia acción: página 2. ENTORNO Y RIESGOS MEDIO · Media · polígono: intersecta el predio PROCEDER CON CONDICIONES AFECTA A: COMPRADOR, VENDEDOR, INMOBILIARIA, BANCO / FINANCIADOR ACCIÓN: Afectacion presente declarada por la fuente oficial: se recomienda verificacion puntual por profesional competente en caso de intervencion fisica del predio; impacto esperado men… POT / CALIDAD DE DATOS 6 atributo(s) con resultados incompatibles entre versiones del expediente NO UTILIZAR ESTE DATO COMO DEFINITIVO AFECTA A: COMPRADOR, INMOBILIARIA, BANCO / FINANCIADOR, ASEGURADORA DE TÍTULO ACCIÓN: Reconciliar con la ficha/polígono POT aplicable antes de usar la cifra. DISPOSICIÓN GLOBAL: PROCEDER CON CONDICIONES IDENTIFICADAS · VALUATION_GATE: La valoración NO está autorizada en esta corrida: el origen de la tasa es MANUAL_CONFIG y su procedencia es INSUFICIENTE para autorizar una cifra (se exige fuente externa citada o cálculo de fuentes citadas, con fecha y sha256). No se emite cifra y se declaran los bloqueos reales. SELLO GLOBAL DICTUS ID DX-040-646406-20261002 Fecha: 2026-10-02 Evidencias: 10 · Estado: PARCIAL_CON_DECLARACIONES Cadena de custodia del expediente: Anexo G. DICTUS_MASTER_HASH 988e4aa6eebe05d6102bb0 …358407bf3e21d5b6422f55 Verificación: DICTUS ID + hash maestro abreviado. El hash del archivo PDF consta aparte (Anexo G). DICTUS_MASTER_HASH 988E4AA6EEBE…4C47 Evidencias 10 · sello PARCIAL_CON_DECLARACIONES · verificación por DICTUS ID (Anexo G) El hash del archivo PDF no es el hash maestro: consta en el anexo G.
```

```
P6_TEXT
DICTUS IDENTIDAD, MERCADO Y VALOR DX-040-646406-20261002 Página 6 de 6 · ejecutivo IDENTIDAD, MERCADO Y VALOR IDENTIDAD DEL INMUEBLE Dirección oficial TV 43 # 100 - 50 CONJUNTO RESIDENCIAL NAPOLI APARTAMENTOS ETAPA 3 APARTAMENTO 430 TORRE 8 ETAPA 3 · Torre 8 · Apartamento 430 VERIFICADO Matrícula 040-646406 VERIFICADO NUPRE AFT0005BOHA VERIFICADO Número predial 080010103000010040001908040002 VERIFICADO Unidad (torre / apartamento) APARTAMENTO 430 TORRE 8 REQUIERE VALIDACIÓN Área 58.75 m² REQUIERE VALIDACIÓN Régimen jurídico Propiedad Horizontal REQUIERE VALIDACIÓN Uso (destino catastral) Habitacional VERIFICADO Tipología Unidad En Propiedad Horizontal REQUIERE VALIDACIÓN Identidad registral y catastral: VERIFICADA Matrícula, NUPRE y número predial resueltos y ligados entre sí por la resolución canónica de la corrida. DECISIÓN DICTUS: INFORMACIÓN VERIFICADA Binding de la identidad canónica del predio (NO es la geometría del predio: el alcance declarado es el de IDENTIFICADORES): IDENTIFICADORES Geometría oficial del PREDIO (lote/edificio): NO acredita la posición del apartamento dentro de la edificación. Fuente: OFFICIAL_PREDIO. El binding acreditado compara solo CADENAS de identificadores (nupre, numero_predial); su alcance declarado es ESTIMACIÓN ECONÓMICA DISPONIBLE ESTIMACIÓN INDICATIVA RANGO ESTIMADO $ 130.000.000 – $ 490.000.000 REFERENCIA CENTRAL $ 310.000.000 (secundaria) VALOR/M² $ 5.206.395 / m² CONFIANZA INDICATIVA MÉTODO: REFERENCIA AGREGADA OFICIAL POR LOCALIDAD Y BANDA DE ÁREA · BAQ_OBS_VALORESM2_AREA · banda oficial $ 2.222.222–$ 8.190.568 COP/m² EVIDENCIA UTILIZADA: 1 fuente(s) con procedencia completa: Alcaldía Distrital de Barranquilla — geoportal miciudad (servidor ArcGIS REST) LIMITACIONES: La base es una referencia AGREGADA de nivel 3 (agrega por sector y banda de área): NO acredita la unidad. El rango es la salida y la referencia central es el centro de… TRAZABILIDAD: TRAZABILIDAD · Fuentes: BAQ_OBS_VALORESM2_AREA · Consulta: 2026-10-02 · motor dictus-estimation-engine/1.0.0 Metodología: fuentes disponibles + análisis técnico automatizado + metodología versionada · detalle completo en el informe técnico. Estimación automatizada de DICTUS basada en la información disponible para esta corrida. No constituye un avalúo comercial certificado cuando este sea legal o contractualmente requerido. NO DISPONIBLE EVIDENCIA DE MERCADO VERIFICADA · NO HABILITADA DECISIÓN DICTUS: NO EMITIR VALORACIÓN · COMPUERTA CLOSED · no se imprime ningún monto, ni $0 no hay fuente de mercado que sostenga la cifra: la tasa de esta corrida proviene de parámetros declarados a mano (origin=MANUAL_CONFIG: valor declarado a mano por la corrida (sin fuente externa automática)), sin procedencia externa verificable Origen de la tasa declarada: valor declarado a mano por la corrida (sin fuente externa automática) (MANUAL_CONFIG) · NO HABILITA VALORACIÓN VERIFIED_MARKET_EVIDENCE_GATE = CLOSED · no existen comparables individualizados suficientes para atribuir un valor verificado a esta unidad · origen no declarado por el artefacto: se clasifica MANUAL_CONFIG (no habilita la valoración) · no hay fuente de mercado que sostenga la cifra: la tasa de esta corrida proviene de parámetros declarados a mano (origin=MANUAL_CONFIG: valor declarado a mano por la corrida (sin fuente externa automática)), sin procedencia externa verificable DICTUS_MASTER_HASH 988E4AA6EEBE…4C47 Evidencias 10 · sello PARCIAL_CON_DECLARACIONES · verificación por DICTUS ID (Anexo G) El hash del archivo PDF no es el hash maestro: consta en el anexo G.
```

## 9 · `HASHES`

```
executive_pdf          = "DICTUS_EJECUTIVO_040-646406.pdf"
executive_sha256       = "0e2a87c15d60eeae62ec9f2da2d45fc9fdb40f7142fede084cb73c7b129d8bf7"
executive_page_count   = 6
technical_pdf          = "DICTUS_TECNICO_040-646406.pdf"
technical_sha256       = "c13b83b1413e8b719e9dce8fbb4dd87852458fd4dc7585714862dd391e4fe863"
technical_page_count   = 17
run_id                 = "b680793e-df16-464c-bae9-6e2df4733083"
dictus_id              = "DX-040-646406-20261002"
generated_at           = "2026-10-02T16:54:30.576839+00:00"
master_hash            = "988e4aa6eebe05d6102bb0358407bf3e21d5b6422f559beb158c3c9321814c47"
verify_master_hash     = "MATCH"
layout_violations      = []
evidence_count         = 10
evidence_seal          = "PARCIAL_CON_DECLARACIONES"
commit_sha             = "565a46e66980170841692f089ba3c859b2af1cfb"
aceptacion_json        = "docs\\forensics\\040-646406\\dictus_2b\\ACEPTACION_040-646406.json"
```

- `layout_violations = []` es la retícula sin violaciones de la corrida (`scripts/dictus_run.py`).
- El `commit_sha` es el HEAD del repositorio en el momento de la aceptación.
- **No se tocó ningún artefacto forense anterior**: esta ronda escribe en `docs/estimation/**` y regenera `docs/forensics/{folio}/dictus_2b/**` con `scripts/dictus_run.py` (su propio generador).

## 10 · `TEST_OUTPUT` (comando y salida REAL)

```
$ python scripts/dictus_run.py
[exit code: 0]
OK - Test de boundary de avaluo: PASADO
[PDF][GATE] ok=True bloqueantes=0 advertencias=0
SUCCESS: PDF GENERADO: C:\Users\aliss\.gemini\antigravity-ide\scratch\20260825_DeepSeek_Harness_Web\arhiax-RE\docs\forensics\040-646406\dictus_2b\DICTUS_TECNICO_040-646406.pdf
  Folio: 040-646406
  Sello de ejecucion SHA-256: d51e19e5028e03f90c8cfea08714ccc3eda5ffa26d6dc8f3bb0ecc633b6a366c
  Hash del archivo emitido SHA-256: c13b83b1413e8b719e9dce8fbb4dd87852458fd4dc7585714862dd391e4fe863
  Timestamp: 2026-10-02T16:53:37.921989+00:00
[PDF][NOTIF] correo de pendientes enviado=False n=2 -> ['hipoteca', 'afectacion']
[run] b680793e · DX-040-646406-20261002 · master hash 988e4aa6eebe05d6…
[run] PRINCIPAL DICTUS_EJECUTIVO_040-646406.pdf · 6 páginas · sha256 0e2a87c15d60…
[run]           arquitectura: P1 DECISIÓN DEL INMUEBLE → P2 DECISIÓN JURÍDICA → P3 DECISIÓN DE CONTRAPARTES → P4 DECISIÓN TERRITORIAL Y URBANÍSTICA → P5 ENTORNO, EQUIPAMIENTO, ASOLEAMIENTO Y SOMBRAS → P6 IDENTIDAD, MERCADO Y VALOR
[run] ANEXO     DICTUS_TECNICO_040-646406.pdf · 17 páginas · sha256 c13b83b1413e…
[run] evidencias 10 (PARCIAL_CON_DECLARACIONES) · verificación MATCH · retícula OK
[run] POI en el estado: 12 ítems · distancias sí
```

```
$ python scripts/golden_evidence_asserts.py
[exit code: 0]
        atributos comparados por clave canónica = 6 · contradicciones entre páginas = 0 · discrepancias con la verdad única del expediente = 0
        
          claves y estados impresos: altura_maxima: P4=HISTORICAL_CONFLICT; amenaza: P4=REQUIERE_VALIDACION; coordenada: P4=HISTORICAL_CONFLICT; titulares: P4=REQUIERE_VALIDACION; tratamiento: P4=REQUIERE_VALIDACION; uso_pot: P4=REQUIERE_VALIDACION
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

```
$ python -m pytest tests/test_estimation_golden.py tests/test_estimation_gate.py tests/test_estimation_evidence_quality_gate.py tests/test_estimation_origin_composition.py tests/test_estimation_semantics_final.py tests/test_market_evidence.py tests/test_dictus_20d_r1_p6.py tests/test_dictus_20c_fidelidad.py -q
[exit code: 0]
........................................................................ [ 31%]
........................................................................ [ 62%]
.........................................................x.............. [ 94%]
.............                                                            [100%]
============================== warnings summary ===============================
..\..\..\..\..\AppData\Roaming\Python\Python314\site-packages\_pytest\cacheprovider.py:469
  C:\Users\aliss\AppData\Roaming\Python\Python314\site-packages\_pytest\cacheprovider.py:469: PytestCacheWarning: could not create cache path C:\Users\aliss\.gemini\antigravity-ide\scratch\20260825_DeepSeek_Harness_Web\arhiax-RE\.pytest_cache\v\cache\nodeids: [WinError 5] Acceso denegado: 'C:\\Users\\aliss\\.gemini\\antigravity-ide\\scratch\\20260825_DeepSeek_Harness_Web\\arhiax-RE\\pytest-cache-files-elm12f85'
    config.cache.set("cache/nodeids", sorted(self.cached_nodeids))

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
228 passed, 1 xfailed, 1 warning in 4.84s
```


## 11 · VEREDICTO

**DICTUS ESTIMATION ENGINE — INDICATIVE ESTIMATE PRODUCED**

Generado por `scripts/estimation_golden.py` · `2026-10-02`

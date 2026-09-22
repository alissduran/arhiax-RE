# Mapa de contratos: pantalla → endpoint (03)

Regla: **cada dato de la interfaz viaja por un contrato existente o se declara
`CONTRATO_FALTANTE`**. Nada se rellena con valores de ejemplo.

## V1 · Consola de emisión

| Elemento de UI | Contrato | Estado | Observaciones |
|---|---|---|---|
| Sesión y rol | `POST /api/login` → `GET /api/me` | **existe** | devuelve `{usuario, rol}` con rol `admin`/`operador` |
| Ciudades operativas | `GET /api/v1/geo/ciudades` | **existe** | el selector debe deshabilitar las que no tengan POT integrado **con motivo** |
| Resolver dirección → folio | `GET /api/resolver-matricula?direccion=` | **existe, DEFECTUOSO** | ver **C-01** |
| Documentos del caso | `POST|GET /api/dictamenes/{id}/documentos`, `GET …/documentos/{doc_id}` | **existe** | binario con control de acceso |
| Crear caso | `POST /api/dictamenes` | **existe** | valida folio/dirección (`ValidationError`) |
| Editar datos manuales | `POST /api/dictamenes/{id}/update` | **existe** | — |
| Generar dictamen (con y sin CTL) | `POST /api/dictamenes/generar` | **existe** | modo *stateless*; el frontend sube el CTL |
| Avance de generación | `GET /api/v1/pdf/trabajos/{job_id}` | **existe** | encolar por QStash; la UI hace *polling* con `aria-live` |
| Descargar PDF | `GET /api/dictamenes/{id}/pdf` | **existe** | — |
| Ficha del predio (matrícula, predial, NUPRE, área, estrato) | *(derivado del caso + dictamen generado)* | **parcial** | hoy estos campos viven en la fila del caso (`folio_matricula`, `area`, `estrato`, `barrio`, `ciudad`, `lat`, `lon`, `fuente_geocod`); los estados de verdad (`VERIFIED_*`, `SOURCE_UNAVAILABLE`) **no se persisten por campo** → ver **C-02** |
| Pilares Catastro / POT / Amenazas | *(derivado)* | **parcial** | el motor calcula todo esto al generar; hoy se ve en el PDF, no en la consola. Propuesta C-02: endpoint de «ficha de verificación» |
| Mercado: sector, tasa, metodología | *(derivado)* | **parcial** | el `MarketContext` existe en memoria al generar; conviene exponerlo (C-02) |
| Screening: sujetos y evidencia | *(derivado)* | **parcial** | el `ScreeningSummary` existe al generar; conviene exponerlo (C-02) |
| Sello de ejecución | *(derivado)* | **existe al generar** | debe rotularse con su **alcance** (F13) |

### C-01 · `GET /api/resolver-matricula` — **DEFECTO REAL (alto)**

`api/index.py::resolver_matricula_por_direccion()` (líneas 439–463) hace lo
siguiente:

```python
if ("43" in normalized and "100" in normalized) or "NAPOLI" in normalized:
    return "040-646406", "Miramar", 4          # caso Golden HARDCODEADO
if ("63" in normalized and "37" in normalized) or "RECREO" in normalized:
    return "040-314248", "El Recreo", 4        # segundo caso hardcodeado
return "Pendiente", "", 4                      # estrato 4 por DEFECTO
```

Tres problemas que la interfaz **no puede maquillar**:

1. **Valor Golden hardcodeado**: la matrícula del caso de aceptación se devuelve por
   coincidencia de subcadenas («43» y «100»), no por consulta.
2. **Estrato por defecto 4** para cualquier dirección desconocida: el mismo default
   que 03H prohibió y que 03I.1 cerró en el camino de valoración. En la consola se
   vería como si fuera un dato del predio.
3. **Falso positivo por subcadenas**: una dirección que contenga «43» y «100» (p. ej.
   «Carrera 43 # 100-20, Medellín») devolvería la matrícula del Golden de Barranquilla.

**Contrato propuesto** (diseño de la pantalla, sin implementar aquí):

```http
GET /api/resolver-direccion?direccion=CL%2079B%2042%2045&ciudad=barranquilla
200 {
  "consulta": {"direccion_input": "CL 79B 42 45", "ciudad": "barranquilla",
               "normalizada": "CL 79B 42 45", "hora": "2026-09-22T17:52:08Z"},
  "campos": {
    "folio_matricula": {"value": null,               "status": "UNRESOLVED",
                        "source": null, "motivo": "no está en el registro de adopción ni en la capa de direcciones"},
    "numero_predial":  {"value": null,               "status": "SOURCE_UNAVAILABLE",
                        "source": "catastro/datosabiertos capa 105", "motivo": "servicio sin respuesta"},
    "barrio":          {"value": "CIUDAD JARDIN",    "status": "VERIFIED_OFFICIAL",
                        "source": "ordenamiento/unidadesadministrativas"},
    "estrato":         {"value": null,               "status": "UNRESOLVED",
                        "source": null, "motivo": "capa de estratificación sin registro en el punto y sin manzana resoluble"},
    "coordenada":      {"value": [10.9982, -74.8081],"status": "VERIFIED_OFFICIAL",
                        "source": "CTL_ADDRESS_GEOCODE"}
  },
  "candidatos": []
}
```

Reglas del contrato: **nunca** un valor por defecto; cada campo con `status` y
`source`; los candidatos múltiples se listan (no se elige el primero); y la
resolución reutiliza los módulos ya remediados
(`barranquilla_adopcion`, `catastro_predio.resolver_manzana_y_estrato`,
`unidad_inmobiliaria`, `market_context.resolve_market_location`).

### C-02 · `GET /api/dictamenes/{id}/verificacion` — **contrato faltante**

Hoy los estados de verdad solo existen **dentro** de la generación del dictamen. Para
que la consola los muestre sin inventarlos, se propone exponer el resultado estructurado
que el motor ya produce:

```json
{
  "case_id": 12, "generado_en": "2026-09-22T17:52:08Z",
  "identidad": {"estado": "MATCH_EXACT", "confidence": "VERIFIED_UNIT_IDENTITY",
                "identity_source": "OFFICIAL_ADOPTION_REGISTRY",
                "direccion": {"value": "Transversal 43 100 50 TO 8 AP 430",
                              "status": "VERIFIED_OFFICIAL",
                              "source": "OFFICIAL_ADOPTION_REGISTRY"}},
  "urbano": {"barrio": {"value": "Miramar", "status": "VERIFIED_OFFICIAL"},
             "estrato": {"value": "4", "status": "VERIFIED_OFFICIAL"},
             "tratamiento": {"value": "Consolidacion", "status": "VERIFIED_OFFICIAL"},
             "altura_maxima": {"value": "11", "status": "VERIFIED_OFFICIAL"},
             "urban_source_mode": "MIXED"},
  "mercado": {"ready": true, "sector": "Miramar", "value_m2": 6800000,
              "match_type": "EXACT",
              "methodology": {"id": "lonja_baq_metodologia", "version": "0.1-codiseno",
                              "sha256": "4ccd5832…"}},
  "valoracion": {"authorized": true, "consolidado": 399500000,
                 "banda": [373532500, 435455000]},
  "volcanico": {"estado": "NO_COVERAGE", "nivel": "NO EVALUADO"},
  "screening": {"status": "SCREENING_COMPLETE", "evidence": "9/9",
                "chain": "SEALED", "subjects": [/* … */]},
  "fuentes": [{"id": "catastro_baq", "status": "SOURCE_UNAVAILABLE",
               "detalle": "capa 500 · 404 Layer not found", "intento": "…Z"},
              {"id": "ordenamiento", "status": "OK", "detalle": "3 capas consultadas"}]
}
```

Implementación natural: **persistir** el `GOLDEN_INTERNAL_STATE`-equivalente (hoy ya se
produce en el runner de QA) al generar el dictamen, y servirlo. Sin esto, la consola
solo puede mostrar el PDF.

## V2 · Cartera

| Elemento | Contrato | Estado |
|---|---|---|
| Lista de casos | `GET /api/dictamenes` → `case_service.list_cases()` | **existe** |
| Campos por caso | `id, folio_matricula, direccion, barrio, estrato, area, estado, valor_consolidado, fecha_creacion, certificado_cargado, lat, lon, fuente_geocod, ciudad, acreedor_real, created_by, updated_by, pdf_path` | **existe** |
| Cuota de organización / consumo | — | **CONTRATO_FALTANTE** (demo) |
| Cobertura de seguro, crédito matricular | — | **CONTRATO_FALTANTE** (demo) |
| Agente asignado / cartera por usuario | `created_by` | **parcial**: hay autoría, no asignación ni ownership (migración 002 lo declara explícitamente como auditoría, no ownership) |

## V3 · Fuentes y diagnóstico

| Elemento | Contrato | Estado |
|---|---|---|
| Versiones y commit | `GET /api/v1/status`, `GET /api/config` | **existe** (admin) |
| Cola de PDF | `GET /api/v1/pdf/estado`, `GET /api/v1/pdf/trabajos` | **existe** (admin) |
| Refrescar listas de sanciones | `POST /api/v1/listas/refrescar` | **existe** (admin) |
| Frescura y hash por fuente | `GET /api/v1/listas/estado` | **CONTRATO_FALTANTE** sugerido: exponer `freshness` + `sha256` + `record_count` por fuente (los datos ya existen en los snapshots) |
| Diagnóstico POI | `GET /api/v1/diagnostico/poi?lat&lon` | **existe** (admin) |
| Catastro en vivo | `GET /api/v1/geo/catastro` | **existe** |

## V4 · Gobernanza (bloqueada)

| Elemento | Contrato propuesto | Estado |
|---|---|---|
| Organizaciones y miembros | `GET|POST /api/v1/orgs`, `/api/v1/orgs/{id}/members` | **CONTRATO_FALTANTE** |
| Cuotas por organización | `GET /api/v1/orgs/{id}/quota` | **CONTRATO_FALTANTE** |
| Interruptor de nodos catastrales | `GET|PUT /api/v1/admin/fuentes/{id}/estado` | **CONTRATO_FALTANTE** |
| Break-glass | `POST /api/v1/admin/break-glass` (motivo obligatorio) + `GET /api/v1/admin/break-glass/bitacora` | **CONTRATO_FALTANTE** |
| Auditoría | `GET /api/v1/auditoria?desde&hasta` | **CONTRATO_FALTANTE** |

Requisitos de diseño del break-glass (para cuando se implemente): sujeto, objeto,
motivo **obligatorio**, ventana temporal, autorizante, y bitácora **inmutable y
exportable**. La UI nunca debe conceder acceso por sí sola: solo solicitar y mostrar
el evento.

## Resultado del mapeo

| Superficie | Dato disponible hoy | Depende de contrato faltante |
|---|---|---|
| V1 Consola (formulario, resolver, documentos, emitir, PDF) | ~70 % | ficha de verificación estructurada (C-02) y resolución de dirección honesta (C-01) |
| V2 Cartera | ~90 % | cuotas/organizaciones (decorativo) |
| V3 Fuentes | ~80 % | frescura/hash por fuente |
| V4 Gobernanza | 0 % | todo |

**Consecuencia para el plan:** V1, V2 y V3 se pueden construir **ya** con lo que
existe, mostrando `FUENTE NO DISPONIBLE` donde corresponda; V4 espera. C-01 es un
defecto de producto que conviene corregir **antes** de llevar la consola a usuarios,
porque la consola lo haría visible y creíble.

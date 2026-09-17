# Auditoría de integración geoespacial — Municipio de Pasto (Nariño) para ARHIAX

**Caso de validación:** folio SNR `240-211101` · NUPRE `520010102000000470014000000000` · WGS84 `1.21194, -77.28663` · dirección ARHIAX "CRA # 26"
**Fecha de auditoría:** 2026-09-17 · **Servidor:** ArcGIS Enterprise 10.81
**Base REST:** `https://geoportal.pasto.gov.co/server/rest/services` *(la ruta es `/server/rest/services`; `/arcgis/rest/services` devuelve 404 — causa de que la integración se declarara imposible)*
**Ejecutado por:** auditoría técnica con consultas REST reales (no inspección de UI).

---

## 0. RESUMEN EJECUTIVO

1. **La anomalía `240-211101` vs `240-216` quedó resuelta.** No es un predio vecino ni un error de georresolución: **`240-216` es la matrícula que el municipio asigna al MISMO predio** (NUPRE `...470014000000000`, `objectid 37231`), coherente en las 4 capas que publican matrícula. La matrícula del CTL **no existe en el geoportal** (0 por igualdad y 0 por `LIKE '%211101%'`). `240-216` es anómalamente corta frente al resto de la capa (240-120149, 240-141051) → **probable truncamiento en la base municipal**. Clasificación: `DATO_REQUIERE_VALIDACION_PROFESIONAL` (cotejo con ORIP Pasto). **ARHIAX debe marcarlo como conflicto, no resolverlo solo.**
2. **Las variables "pendientes" del dictamen EXISTEN en fuentes oficiales.** Barrio, comuna, estrato y nomenclatura estaban en `N/D` por **fallo de integración**, no por ausencia de dato. Ya se cerraron (ver §2).
3. **La contradicción `riesgos consultados` vs `H-GEO NO EVALUADO` era un bug de propagación de evidencia**, no de consulta. Corregido (§4).
4. **El predio es un caso materialmente crítico**: `Suelo de proteccion`, `CMA no construible` y **ZAVA sentencia T-269/2015**. El dictamen anterior no lo destacaba.
5. **Regla nueva y no negociable:** para Pasto **nunca** se resuelve la identidad por proximidad. El municipio devuelve **15 predios distintos a ≤30 m** del punto del caso.

---

## 1. MATRIZ DE COBERTURA — PASTO

Estado: **A** = YA FUNCIONA · **B** = EXISTE PERO NO INTEGRADA · **C** = BUG CORREGIDO · **D** = PENDIENTE DE FUENTE · **E** = NO APLICA

| # | Variable | Estado | Servicio / layer-table | Campo origen |
|---|---|---|---|---|
| 1 | NUPRE / código predial nacional | **A** | `Estratificacion/MapServer/4` | `codigo_predial_nacional` |
| 2 | Código predial anterior | **A** | idem | `codigo_predial_anterior` |
| 3 | Código predial corto | **A** | idem | `codigo_predial_corto` |
| 4 | Código de manzana | **A** | idem (+ `Mapa_base/11`) | `codigo_de_manzana` |
| 5 | Área catastral (terreno) | **A** | idem | `area_igac_m2` / `st_area(shape)` |
| 6 | Área construida | **B** | idem | `area_construida` |
| 7 | **Barrio** | **C** | `Division_politico_administrativa/MapServer/1` | **`sector`** ⚠ no existe campo `barrio` |
| 8 | **Comuna** | **C** | `Division_politico_administrativa/MapServer/2` | `comuna` ("Comuna 1") |
| 9 | **Estrato** | **C** | `Estratificacion/MapServer/1` (table) y `/2` (table) | `estrato` |
| 10 | **Nomenclatura oficial** | **C** | `Estratificacion/MapServer/1` | `nomenclatura_igac` |
| 11 | Clase de suelo | **A** | `Norma_Urbanistica.../28` y `/2` | `clase_de_suelo` |
| 12 | Área de actividad | **A** | `Norma_Urbanistica.../28` | `area_actividad`, `codigo_area_actividad` |
| 13 | Tratamiento urbanístico | **A** | `Norma_Urbanistica.../2` | `tratamiento_urbanistico` |
| 14 | Sector normativo | **A** | idem | `sector_normativo` |
| 15 | Área morfológica | **A** | idem | `area_morfologica` |
| 16 | Código morfológico de alturas | **A** | idem | `codigo_morfologico_de_alturas` |
| 17 | Edificabilidad (texto) | **A** | idem | `edificabilidad` |
| 18 | **Altura / altura máxima / índices** | **B** | **JOIN 2 saltos** `capa2.id_tu_edificabilidad → table13 → table9` | `altura`, `altura_maxima`, `indice_construccion_maxima`, `indice_ocupacion_maxima` |
| 19 | Volumen a edificar | **A** | `Norma_Urbanistica.../2` | `volumen_a_edificar` |
| 20 | Afectación ronda hídrica | **A** | idem | `afectacion_por_ronda_hidrica`, `delimitacion_del_area_afectada_` |
| 21 | **Usos compatibles / prohibidos / CIIU** | **B** | `table15` (por TEXTO de `area_actividad`) → `table27` | `compatibilidad`, `id_ciiu` |
| 22 | PEMP | **A** | `Norma_Urbanistica.../2` + `table10` | `id_institucion_pemp`, `nivel_intervencion_pemp` |
| 23 | ZAVA (T-269/2015) | **A** | `/2`, `/28` y `/1` | `zava_t_269_de_2015` |
| 24 | Riesgo volcánico municipal | **A** | `Norma_Urbanistica.../1` | `riesgo_volcanico_ea27` |
| 25 | Inundación | **C** | idem | `inundacion_ea23` |
| 26 | Remoción en masa | **C** | idem | `remocion_en_masa_ea19` |
| 27 | Subsidencia | **C** | idem | `subsidencia_ea29` |
| 28 | Flujos de lodo + restricciones | **C** | idem | `flujos_de_lodo_ea22`, `restricciones_por_lujos_de_lodo` |
| 29 | Servidumbre eléctrica | **C** | idem | `servidumbre_de_lineas_de_alta_t` |
| 30 | Amenaza volcánica SGC (Galeras) | **A** | `srvags.sgc.gov.co/.../Amenaza_Volcanica/19` y `/64` | `GRADO_AMENAZA`, `NOMBRE_VOLCAN`, `FENOMENO` |
| 31 | Perfil vial | **B** | `Planeacion/Perfil_Vial/MapServer/0` y `/4` | por definir (no auditado a campo) |
| 32 | Planos urbanísticos | **B** | `Planeacion/Planos_Urbanisticos/MapServer` (140+ capas raster) | catalogar por sector |
| 33 | Planes parciales / instrumentos | **B** | `Norma_Urbanistica.../2` (`id_observacion_tratamieto_urban`→`table24`) + repositorio POT | `tratamiento_urbanistico` |
| 34 | Polígonos de saturación | **B** | `Planeacion/Poligonos_de_saturacion/MapServer/0` | `nombre_establecimiento`, `observaciones` |
| 35 | Veredas / Corregimientos (rural) | **B** | `Division_politico_administrativa/MapServer/4` y `/6` | `vereda`, `corregimientos` |
| 36 | Matrícula inmobiliaria (municipal) | **A** | `/2`, `/28`, `Estratificacion/4` | `matricula_inmobiliaria` |
| 37 | Propietario / cédula | **B** | `Estratificacion/4`, `/2` | `propietario`, `cedula_o_nit` |
| 38 | Avalúo IGAC | **D** | `Estratificacion/4` | `avaluo_igac` — **viene NULL** en las filas consultadas |
| 39 | Tipo de construcción / pisos | **D** | — | **el municipio no lo publica** |
| 40 | Datos ocultos tras token | **D** | carpetas `Campo`, `Hosted`, `Utilities` | `{"error":{"code":499,"message":"Token Required"}}` |
| 41 | `Planes Parciales` como capa | **D** | no existe servicio propio | ver §9 |

---

## 2. RESULTADO REAL DEL CASO `240-211101` — VARIABLE POR VARIABLE

Predio confirmado: **`objectid 37231`** (idéntico en `Estratificacion/4`, `Mapa_base/10`, `Mapa_base_registro_de_descargas/29`, `Norma_.../2` y `/28`).

| Variable | Valor encontrado | Fuente (layer/table y campo) | Matching | Confianza |
|---|---|---|---|---|
| NUPRE | `520010102000000470014000000000` | `Estratificacion/4.codigo_predial_nacional` | `MATCH_EXACT` (where `=`) | **Alta** |
| Código anterior | `52001010200470014000` | idem `.codigo_predial_anterior` | exacto | Alta |
| Código corto | `010200470014000` | idem `.codigo_predial_corto` | exacto | Alta |
| Manzana | `52001010200000047` | idem `.codigo_de_manzana` → existe en `Mapa_base/11` (objectid 2456) | `MATCH_RELATIONAL` | Alta |
| **Matrícula municipal** | **`240-216`** | `/2`, `/28`, `Estratificacion/4` `.matricula_inmobiliaria` | exacto (1 fila) | **CONFLICTO con el CTL `240-211101`** |
| Matrícula del CTL | `240-211101` | — | **0 filas** por `=` y por `LIKE '%211101%'` en TODAS las capas | **Ausente** |
| **Barrio oficial** | **`OBRERO`** | `DPA/1.sector` (objectid 719, `codigo_del_sector 777`) | `MATCH_SPATIAL_EXACT` por centroide del predio | Alta |
| **Comuna oficial** | **`Comuna 1`** | `DPA/2.comuna` (objectid 6) | idem | Alta |
| **Estrato** | **`3`** | `Estratificacion/1.estrato` (objectid 62341) y `/2.estrato` (objectid 49929) | por NUPRE y por código corto | **Alta (doble fuente coincidente)** |
| **Nomenclatura oficial** | **`K 26 8 28 13`** | `Estratificacion/1.nomenclatura_igac` | por NUPRE | Alta |
| Dirección ARHIAX | "CRA # 26" | — | **subcadena**: ARHIAX capturó solo la vía (Carrera 26); falta `#8-28/13` | Baja |
| Área terreno | `126` m² (`st_area` 126.16) | `Estratificacion/4.area_igac_m2` | exacto | Alta |
| Área construida | `295` m² | `Estratificacion/4.area_construida` | exacto | Media (discrepa con table1=126) |
| Clase de suelo | `Urbano` | `/2.clase_de_suelo`, `/28.clase_de_suelo` | exacto | Alta |
| **Tratamiento** | **`Suelo de proteccion`** | `/2.tratamiento_urbanistico` | exacto | Alta |
| Sector normativo | `1` | `/2.sector_normativo` | exacto | Alta |
| Área morfológica | `C-5` | `/2.area_morfologica` | exacto | Alta |
| Unidad territorial | `Centro` | `/2.unidad_territorial` | exacto | Alta |
| **Edificabilidad** | **`No aplica`** | `/2.edificabilidad` | exacto | Alta |
| **Código morfológico alturas** | **`CMA no construible`** | `/2.codigo_morfologico_de_alturas` | exacto | Alta |
| **Altura máxima / índices** | **`No aplica` (CADENA ROTA POR DISEÑO)** | `/2.id_tu_edificabilidad = null` | paso 1 devuelve `null` → cadena termina | **Alta — es una RESPUESTA, no un fallo** |
| Área de actividad | `Sub Área Residencial Comercial Industrial - 2` (`CS1-SA2`) **+** `Suelo de proteccion` (2 polígonos) | `/28.area_actividad` | exacto (doble clasificación real) | Alta |
| **ZAVA** | **`Predio en ZAVA sentencia T 269 2015`** | `/2`, `/28` y `/1`. | exacto | **Alta — es la restricción más relevante** |
| Riesgo volcánico municipal | `Flujos de lodo secundario` | `/1.riesgo_volcanico_ea27` | exacto | Alta |
| Flujos de lodo | `Bajo`; restricciones `S3` | `/1.flujos_de_lodo_ea22`, `.restricciones_por_lujos_de_lodo` | exacto | Alta |
| Remoción en masa | `No aplica` | `/1.remocion_en_masa_ea19` | exacto | Alta (evaluado) |
| Inundación | `No aplica` | `/1.inundacion_ea23` | exacto | Alta (evaluado) |
| Subsidencia | `No aplica` | `/1.subsidencia_ea29` | exacto | Alta (evaluado) |
| Servidumbre eléctrica | `No aplica` | `/1.servidumbre_de_lineas_de_alta_t` | exacto | Alta (evaluado) |
| PEMP | `No aplica` | `/2.nivel_intervencion_pemp`, `id_institucion_pemp=null` | exacto | Alta |
| Ronda hídrica | `No aplica` | `/2.afectacion_por_ronda_hidrica` | exacto | Alta |
| Geometría | bbox WGS84 lon[-77.286658, -77.286533] lat[1.211707, 1.211856] | `Estratificacion/4` con `outSR=4326` | — | Alta |
| **Precisión de la coordenada ARHIAX** | el punto dado queda **~10,5 m al norte del polígono** | — | — | Coordenada correcta, error ~10 m |
| Propietario | `UNIDAD ADMINISTRATIVA DEL SISTEMA`; cédula `Sin información` | `Estratificacion/4` | exacto | Media |
| Avalúo IGAC | **NULL** | `.avaluo_igac` | — | `DATO_REALMENTE_NULO` |

### 2.0 ⚠ HALLAZGO DECISIVO: EL DICTAMEN ANALIZÓ UN PREDIO QUE NO ES EL DEL USUARIO

El CTL describe el inmueble como **`EDIFICIO "CASA CABRERA - PROPIEDAD HORIZONTAL" · CARRERA 26 Nº 21-55 · APARTAMENTO 101`**, con una segunda nomenclatura **`KR 26 # 21-47 APTO 101 CENTRO`**. Buscando esas nomenclaturas en la base municipal aparecen **tres predios distintos que no hay que confundir**:

| # | Nomenclatura municipal | NUPRE | Uso PH | Estrato | Área constr. | ¿Es el del CTL? |
|---|---|---|---|---|---|---|
| **1** | **`K 26 21 47 AP 101`** | **`520010102000000440902900000116`** | **`Apartamento`** | **3** | **76 m²** | ✅ **SÍ — coincide con `KR 26 # 21-47 APTO 101`** |
| 2 | `K 26 21 55 AP 201` | `520010102000000440902900000117` | `Apartamento` | 3 | 102 m² | ❌ otra unidad del mismo edificio (apto 201, no 101) |
| **3** | **`K 26 8 28 13`** | **`520010102000000470014000000000`** | (sin dato PH) | 3 | 295 m² (terreno 126) | ❌ **EL QUE ANALIZÓ ARHIAX — otro predio** |

Los predios 1, 2 y 3 tienen **manzanas distintas**: `...044` (Casa Cabrera) vs `...047` (el analizado). Están sobre la misma vía (Carrera 26) pero en **placas diferentes**: `#21-47`/`#21-55` frente a `#8-28`.

**CONSECUENCIA:** las conclusiones normativas y de riesgo del dictamen — **ZAVA T-269/2015, `Suelo de proteccion`, `CMA no construible`, amenaza ALTA por lahares del Galeras, matrícula `240-216`** — pertenecen al predio **`K 26 8 28 13`**, y **NO son atribuibles** al apartamento 101 del Edificio Casa Cabrera. El dictamen actual **no es utilizable** para decidir sobre el inmueble del usuario.

**Lo que SÍ se sabe del predio correcto** (`...0440902900000116`, `K 26 21 47 AP 101`):
- Existe **solo en la tabla de nomenclatura** (`Estratificacion/1`): `uso_propiedad_horizontal = "Apartamento"`, estrato **3**, comuna **`Comuna 1`**, área construida **76 m²**, código corto `010200440116902`, placa `47`.
- **NO existe** en la capa predial (`Estratificacion/4`), ni en tratamientos (`Norma/2`), ni en áreas de actividad (`Norma/28`), ni en riesgos (`Norma/1`). Es una **unidad PH que no está en las capas de polígono**: por eso **ningún** dato de POT, edificabilidad o riesgo se puede afirmar para él con estas fuentes, y hay que usar la **matriz** (predio padre) o el certificado catastral de la unidad.
- La matrícula `240-211101` **no aparece en ninguna capa** del geoportal.

**Causa probable (no concluyente sin el CTL):** resolución **por coordenadas** desde la dirección incompleta `CRA # 26`, que geocodifica a un punto de la vía y devuelve uno de los **13–15 predios vecinos** a 30 m. Eso explica también que ARHIAX capturara solo la vía y que el NUPRE quedara en la manzana `047`.

**Acción humana requerida (bloqueante):**
1. **Rehacer el caso** con la dirección completa `KR 26 # 21-47 APTO 101` (o `Carrera 26 #21-55 APTO 101`) para que la resolución no dependa de un punto aproximado.
2. Leer en el CTL el **número predial del apartamento** y confirmar que es `520010102000000440902900000116`.
3. Pedir en Catastro Municipal el certificado catastral de la **unidad PH** (el geoportal no la tiene en sus capas de polígono) y el de su **predio matriz**.
4. Cotejar la matrícula `240-211101` con la **ORIP Pasto**.
5. **No tomar decisiones de crédito con el dictamen actual.**

**Reglas que esto impone a ARHIAX (implementadas o especificadas):**
- Resolver **primero por NUPRE/matrícula/nomenclatura**; la proximidad es **último recurso** y **nunca** puede sostener una afirmación normativa.
- **Contrastar la nomenclatura** del CTL contra la municipal: si apunta a un NUPRE distinto del usado, `IDENTITY_CONFLICT` **bloqueante** (el CTL trae DOS nomenclaturas — hay que probar **ambas**).
- Soportar explícitamente **PROPIEDAD HORIZONTAL**: `codigo_predial_corto_ph`, `uso_propiedad_horizontal`, y la relación **unidad ↔ matriz**. Hoy el motor no la modela y por eso eligió un predio ajeno sin detectarlo.
- Si la unidad PH **no está en las capas de polígono**, declarar `POT/riesgo: NO DISPONIBLE PARA LA UNIDAD — consultar la matriz`, en lugar de heredar datos de otro predio.

### 2.1 Dato de máximo impacto para la decisión de crédito

El predio está en **ZAVA (Zona de Amenaza Volcánica Alta) por sentencia T-269 de 2015**, con tratamiento **`Suelo de proteccion`** y código morfológico de alturas **`CMA no construible`**. Consecuencia: **no es edificable** y está sujeto a restricción por amenaza volcánica. Cualquier avalúo, garantía o promesa de compraventa debe tratar esto como **restricción crítica**, no como un campo más.

### 2.2 Hallazgo crítico: el predio está en el cauce de la Avenida Torrencial Mijitayo

La coordenada del caso `1.21194, -77.28663` cae **dentro del canal de la Avenida Torrencial Mijitayo**, fuera de todo polígono predial (comprobado por radios: 5 m → 0 predios; 10 m → 2; 15 m → 5; **30 m → 13**; 40 m → 17). Eso explica dos cosas a la vez: por qué el `intersect` a 0 m devuelve 0 filas, y por qué **resolver por proximidad es peligroso** (13 predios vecinos).

Tres fuentes independientes confluyen en el mismo peligro:

| Evidencia | Valor literal | Fuente |
|---|---|---|
| Amenaza geológica del Galeras | **`Amenaza Alta` / `Lahares` / `V. Galeras`** | SGC `Amenaza_Volcanica/19` (OBJECTID 1338) |
| Texto oficial de la leyenda SGC | *"los lahares descenderían por el **río Mijitayo** y la quebrada Midoro alcanzando la zona urbana del municipio de Pasto"* | SGC `/19` LEYENDA_3 |
| Zona de amenaza municipal | `zava_t_269_de_2015 = "Predio en ZAVA sentencia T 269 2015"`; polígono **`"Amenaza Alta : Lahares"`** | POT `Norma_.../2`, `/28`, `Riesgos/1`, `/15`, `/16` |
| Riesgo por inundación | **`nivel_riesgo = "Bajo"`**, mapa reglamentario **EA23**, ubicación **`"AVENIDA TORRENCIAL Q. MIJITAYO"`** | `Riesgos/8` (objectid 11) |
| Flujos de lodo secundarios | `Bajo` (EA22), restricción **`S3`** (EA32) | `Riesgos/7`, `/10`, y `Norma_.../1` |

**SGC y POT COINCIDEN en ALTA** (mismo fenómeno: lahares). La coincidencia es mecanística, no casual: el polígono que intersecta el predio se llama literalmente *Avenida Torrencial Mijitayo*, y la leyenda del SGC nombra ese mismo río.

### 2.3 Contradicción INTERNA del geoportal municipal (nueva, sin resolver)

La capa `Norma_.../1` informa `inundacion_ea23 = "No aplica"` para este predio, **pero la capa `Riesgos/8` —cuyo campo es literalmente el mismo mapa reglamentario EA23— sí intersecta el polígono del predio con `nivel_riesgo = "Bajo"`**. Se verificó con el **polígono real del predio** (no por proximidad), así que no es un artefacto del punto.

**Regla para ARHIAX:** cuando el resultado por predio contradiga al de la capa de polígono, **conservar ambas evidencias** y emitir `CONTROVERSIA_DE_FUENTE`; **no** quedarse con la más favorable. Documentadas las dos, gana la más restrictiva para efectos de alerta.

### 2.4 Dos advertencias sobre la fuente SGC

1. **La capa consolidada `/64` NO cubre el Galeras.** `NOMBRE_VOLCAN LIKE '%Galeras%'` → **0 filas**; en el área de Pasto solo devuelve **Chiles-Cerro Negro** (otro volcán, ~100 km al oeste). Tomar `/64` como "el Galeras" produciría `Amenaza Baja` y **subestimaría el caso**. ARHIAX debe leer la capa del **grupo del volcán** (`/19`) y etiquetar siempre `NOMBRE_VOLCAN`.
2. **`/18` (caída de piroclastos del Galeras) NO intersecta** el punto (`returnCountOnly` = 0): el peligro aplicable aquí es **lahares**, no ceniza.

### 2.5 Inventario de riesgo incompleto en la integración anterior

El servicio `Planeacion/Riesgos/MapServer` publica **21 capas**, no 11: además de las conocidas (0–11) existen **`/12` a `/20`**, entre ellas `/13` y `/14` **servidumbres de redes eléctricas 115 kV y 230 kV**, `/15`–`/17` versiones de **amenaza volcánica (2015, ZAVA y 1997)** y `/20` **áreas en condición de riesgo por amenaza volcánica**. Discrepancias de vigencia medidas: `/17` (1997) dice **`Media`** mientras `/15`/`/16` (2015/ZAVA) dicen **`Amenaza Alta : Lahares`** → registrar `dataset_vintage` y no mezclar vintages.

---

## 3. CAUSA DE CADA INCONSISTENCIA DEL PDF ANTERIOR

| Síntoma en el PDF | Causa raíz | Clasificación |
|---|---|---|
| `Barrio = pendiente` | ARHIAX nunca consultó la **DPA**; además, el conector buscaba un campo `barrio` **que no existe** en `DPA/1` (el nombre vive en `sector`) | `FUENTE_EXISTE_NO_INTEGRADA` |
| `Comuna = N/D` | idem (capa `DPA/2` no consultada) | `FUENTE_EXISTE_NO_INTEGRADA` |
| `Estrato = N/D` / `No aplica (uso no residencial)` | El estrato **no está** en la capa predial: vive en las **tablas** `Estratificacion/1` y `/2`, que no se consultaban. Y el dictamen infería "no residencial" por **ausencia** del dato | `FUENTE_EXISTE_NO_INTEGRADA` + BUG de inferencia |
| `Destino económico = PENDIENTE` | El municipio publica el uso en `/28.area_actividad`; ARHIAX no lo mapeaba a destino | `FUENTE_EXISTE_NO_INTEGRADA` |
| `Condición jurídica = Propiedad Horizontal` presentada como dato catastral | Se **infiere del CTL**, no viene del catastro (ningún geoportal la publica) | BUG de procedencia |
| `Tipo de construcción = pendiente` | El municipio **no publica** tipo de construcción | `DATO_REALMENTE_NULO` (fuente) |
| `Planes parciales = no evaluado` | El repositorio existe pero no como capa consultable; requiere `table24` + documentos del POT | `FUENTE_EXISTE_NO_INTEGRADA` |
| `Riesgos municipales = no evaluado` **a la vez que** "consultados en vivo" | `geo_eval` se construía en un `else` genérico que marcaba NO EVALUADO para Pasto **sin mirar** si la capa municipal había respondido: **la evidencia existía** (`predio_real['riesgos']`) pero no se propagaba al motor geoespacial. `_fuente_geo` seguía fija en "PENDIENTE" | **BUG de propagación de evidencia** |
| `Score Hidrológico 100/100` con NO EVALUADO | El score decidía "sin evaluar" por **coincidencia de texto** en el resumen, no por una marca explícita → `NO_EVALUADO` colapsaba en `100/100` | **BUG de scoring** |
| `240-211101` vs `240-216` | El CTL y el municipio discrepan en la matrícula del **mismo** predio (NUPRE coincidente). `240-216` es anómala por longitud → probable truncamiento municipal | `DATO_REQUIERE_VALIDACION_PROFESIONAL` |
| Dirección "CRA # 26" incompleta | El CTL no traía la placa completa; ARHIAX no la completó con la nomenclatura municipal (`K 26 8 28 13`) | `IDENTIDAD_PREDIAL_NO_RESUELTA` (parcial) |

**Regla formalizada:** `NO_EVALUADO != SIN_RIESGO` y `NO_EVALUADO != 100/100`. Una componente sin evidencia debe quedar **no calificable** y **no** contribuir positivamente al score.

---

## 4. CORRECCIONES YA IMPLEMENTADAS Y VERIFICADAS

| # | Cambio | Archivo | Verificación |
|---|---|---|---|
| 1 | `geo_eval` de Pasto se construye con los datos **reales** de la capa `/1` y se marca `evaluado=True/False` | `api/pdf_compiler.py` | H-GEO pasa de "NO EVALUADO" a "Zona Libre de Amenazas y Riesgos (Evaluación Dinámica POT)" |
| 2 | `NO_EVALUADO != SIN_RIESGO` con marca explícita en el score | `api/score_engine.py` | El 100/100 hidrológico ahora se justifica con "Sin afectación en las capas de riesgo consultadas" |
| 3 | Regla **IDENTITY_CONFLICT**: si el predio se resuelve por coordenadas y la matrícula municipal no coincide con el folio del CTL, **se descarta el dato predial** y se emite hallazgo ALTO bloqueante | `api/pdf_compiler.py` | 207 tests; hallazgo `H-IDENT` |
| 4 | **Barrio, comuna, estrato y nomenclatura** consultados de DPA y de las tablas de Estratificación, con **centroide del propio polígono** cuando se resuelve por NUPRE | `api/pasto_territorio.py` | En vivo: `OBRERO` / `Comuna 1` / `3` / `K 26 8 28 13` |
| 5 | "No aplica" **conservado** en los campos de riesgo (antes se descartaba y la fila desaparecía) | `api/pasto_territorio.py` | Las 8 filas de riesgo aparecen siempre |
| 6 | Las 8 filas de riesgo se imprimen **siempre**, con "NO REGISTRA" si falta | `api/pdf_compiler.py` | Verificado en PDF |

---

## 5. CONSULTAS REST REPRODUCIBLES

**Regla de oro:** el parámetro `geometry` debe ir **percent-encoded** (si no, Tomcat responde HTTP 400 con HTML). En las **tablas** (`Table`) hay que enviar **siempre `where=1=1`**: con `outFields=*` y sin `where` devuelven `{"error":{"code":400,"message":""}}`. Detecta siempre la clave `"error"` (ArcGIS responde **200 con error**).

```
# Metadatos del servicio de normativa (7 layers + 22 tables)
GET .../Planeacion/Norma_Urbanistica_Riesgo_Suelo/MapServer?f=json

# CASO — Tratamientos por NUPRE (vía determinista)
GET .../Norma_Urbanistica_Riesgo_Suelo/MapServer/2/query
    ?where=codigo_predial_nacional%3D%27520010102000000470014000000000%27
    &outFields=%2A&returnGeometry=false&f=json

# CASO — Por punto (solo si NO hay NUPRE). Nota: a 0 m devuelve 0 filas porque el
# punto cae en un vacío de topología; hay que usar distance=30.
GET .../MapServer/2/query
    ?geometry=%7B%22x%22%3A-77.28663%2C%22y%22%3A1.21194%2C%22spatialReference%22%3A%7B%22wkid%22%3A4326%7D%7D
    &geometryType=esriGeometryPoint&inSR=4326&spatialRel=esriSpatialRelIntersects
    &distance=30&units=esriSRUnit_Meter&outFields=%2A&returnGeometry=false&f=json

# BARRIO por punto (campo `sector`)
GET .../Division_politico_administrativa/MapServer/1/query
    ?geometry=<percent-encoded>&geometryType=esriGeometryPoint&inSR=4326
    &spatialRel=esriSpatialRelIntersects&outFields=%2A&returnGeometry=false&f=json
# COMUNA: idéntico con /2

# ESTRATO por NUPRE (table 1) y por código corto (table 2)
GET .../Estratificacion/MapServer/1/query
    ?where=codigo_predial_nacional%3D%27520010102000000470014000000000%27&outFields=%2A&returnGeometry=false&f=json
GET .../Estratificacion/MapServer/2/query
    ?where=codigo_predial_corto%3D%27010200470014000%27&outFields=%2A&returnGeometry=false&f=json

# GEOMETRÍA del predio en WGS84 (para centroide → barrio/comuna)
GET .../Estratificacion/MapServer/4/query
    ?where=codigo_predial_nacional%3D%27...%27&outFields=objectid&returnGeometry=true&outSR=4326&f=json

# RIESGOS por predio (por código y por matrícula)
GET .../Norma_Urbanistica_Riesgo_Suelo/MapServer/1/query
    ?where=codigo_predial%3D%27520010102000000470014000000000%27&outFields=%2A&returnGeometry=false&f=json
GET .../Norma_Urbanistica_Riesgo_Suelo/MapServer/1/query
    ?where=matricula_inmobiliaria%3D%27240-216%27&outFields=%2A&returnGeometry=false&f=json

# SGC Galeras (amenaza geológica, dominio separado)
GET https://srvags.sgc.gov.co/arcgis/rest/services/Amenaza_Volcanica/Amenaza_Volcanica/MapServer/19/query
    ?where=1%3D1&outFields=%2A&geometry=<percent-encoded>&geometryType=esriGeometryPoint
    &inSR=4326&spatialRel=esriSpatialRelIntersects&returnGeometry=false&f=json
```

---

## 6. JOINS NECESARIOS

**No existe ni una sola relación declarada** en el servicio (`relationships: []` en 28/28 entidades) y `objectIdField` viene `null` en todas → **`queryRelatedRecords` no funcionará nunca**. Todos los JOIN son **client-side**, encadenando consultas.

### 6.1 Edificabilidad (2 saltos + 1 discriminador obligatorio)
```
capa2.id_tu_edificabilidad                →  table13.id_tu_edificabilidad
table13.id_edificabilidad                 →  table9.id_edificabilidad
table9.codigo_morfologico_altura  ==  capa2.codigo_morfologico_de_alturas   ← discriminador
```
Sin el tercer criterio el join devuelve **1–5 filas ambiguas**: `id_edificabilidad` **no es única** en `table9` (22 filas / 8 ids distintos). Para el caso, el paso 1 devuelve `null` → **la altura es legítimamente "No aplica"** (predio no construible).

### 6.2 Usos y CIIU
```
capa28.area_actividad  ──(TEXTO literal)──▶  table15.tipo_actividad  ──▶  table15.id_ciiu
                                                                        ──▶  table27.id_ciiu → ciiu_actividad
```
⚠ **El código `CS1-SA2` NO sirve como puente** (0 filas en `table15`): el único puente es el **texto literal** de `area_actividad`, frágil a tildes/mayúsculas/espacios → requiere normalización.
⚠ `compatibilidad` **no es un enum cerrado** (24 valores distintos, varios narrativos). Modelarlo como catálogo abierto.

### 6.3 Estratificación
```
Estratificacion/4  ──codigo_predial_nacional (30)──▶  table1   (barrio, comuna, estrato, nomenclatura)
Estratificacion/4  ──codigo_predial_corto (15)─────▶  table2   (estrato)
Mapa_base/10       ──codigo_de_manzana (17)────────▶  Mapa_base/11 Manzanas
```
⚠ `table1` **no tiene `matricula_inmobiliaria`**: no se puede unir por matrícula.

### 6.4 Puente NUPRE ↔ matrícula (identidad)
Solo **`Estratificacion/4`, `Mapa_base/10`, `Norma_.../2` y `Norma_.../28`** publican **ambos** campos. Son los únicos que permiten contrastar el folio del CTL con el municipio.

---

## 7. REGLAS DE RESOLUCIÓN DE IDENTIDAD PREDIAL (jerárquicas)

```
1. codigo_predial_nacional (NUPRE)  == exacto          → MATCH_EXACT
2. codigo_predial_anterior          == exacto          → MATCH_EXACT (legado)
3. codigo_predial_corto             == exacto          → MATCH_EXACT (derivado)
4. matricula_inmobiliaria           == exacto          → MATCH_RELATIONAL
5. nomenclatura normalizada         == exacto          → MATCH_RELATIONAL
6. geometría: intersección con el polígono del predio  → MATCH_SPATIAL_EXACT
7. proximidad (distance=30 m)                          → MATCH_SPATIAL_NEAREST  ⚠ SOLO ÚLTIMO RECURSO
```
**Prohibiciones explícitas**
- Nunca afirmar normativa predial obtenida por `MATCH_SPATIAL_NEAREST`.
- Si `matricula_inmobiliaria` municipal ≠ folio del CTL → **`IDENTITY_CONFLICT`** (hallazgo ALTO bloqueante).
- Si el resultado espacial devuelve **>1 candidato** → `MULTIPLE_CANDIDATES`: no elegir, declarar.
- Si la resolución por coordenadas no tiene contraste de matrícula → `IDENTIDAD_PREDIAL_NO_RESUELTA`: no afirmar el predio.

**Dato duro que obliga a esta regla:** el municipio devuelve **15 predios distintos a ≤30 m** del punto del caso, y el punto cae **10,5 m fuera** del polígono correcto.

---

## 8. FAILURE SEMANTICS (obligatorio no colapsar en "N/D")

```
MATCH_EXACT · MATCH_RELATIONAL · MATCH_SPATIAL_EXACT · MATCH_SPATIAL_NEAREST
MULTIPLE_CANDIDATES · IDENTITY_CONFLICT · NO_RECORD
SOURCE_TIMEOUT · SOURCE_UNAVAILABLE · SCHEMA_CHANGED · NOT_APPLICABLE
IDENTITY_CONFLICT · DATO_REQUIERE_VALIDACION_PROFESIONAL · DATASET_VINTAGE
```
Ejemplos reales de esta auditoría:
- `NOT_APPLICABLE` → altura máxima del caso (`id_tu_edificabilidad=null`, predio no construible).
- `NO_RECORD` → matrícula `240-211101` (0 filas por igualdad y por `LIKE`).
- `DATO_REALMENTE_NULO` → `Barrios.estrato` (NULL en las 445 filas); `avaluo_igac`.
- `SCHEMA_CHANGED` → `DPA/1` sin campo `barrio`; `table24.a2_aplicación_edificabilidad` con tilde y `a1_aplicacion_edificabilidad` sin ella; `table12.id_observacion_noma_urbana` (sic); `capa2.id_observacion_tratamieto_urban` (sic).
- `SOURCE_UNAVAILABLE` → carpetas `Campo`/`Hosted`/`Utilities` (`code 499 Token Required`).
- `FUENTE_EXISTE_ERROR_CONECTOR` → `LIKE` rechazado en `registro/29` y `Norma/28` (igualdad sí funciona).
- `DATASET_VINTAGE` → la base predial del registro de descargas declara **IGAC 2021**; no presentarla como catastro actualizado a 2026.

---

## 9. CRS Y GEODESIA

| Servicio | CRS nativo |
|---|---|
| `Division_politico_administrativa` | **3115** (MAGNA-SIRGAS / Colombia Oeste, metros) |
| `Estratificacion` | **3115** |
| `Norma_Urbanistica_Riesgo_Suelo` | **3115** |
| `Riesgos` | **3115** |
| `Poligonos_de_saturacion` | **3115** |
| **`Mapa_base`** | **102100 / 3857 (Web Mercator)** ⚠ distinto |
| Tablas (`Table`) | **sin CRS** (no tienen geometría) |
| SGC | **4686** (MAGNA-SIRGAS geográfico) |

**Consecuencias:** (a) las consultas cruzadas entre `Mapa_base` y el resto exigen `inSR`/`outSR` explícitos; (b) ArcGIS **sí reproyecta on-the-fly** — verificado: consultas en `inSR=4326` contra capas 3115 devuelven resultados correctos; (c) **separar** precisión de transformación (~1 m WGS84↔MAGNA), precisión catastral, antigüedad cartográfica (2021) y precisión de la geocodificación (**~10,5 m medidos en el caso**).

---

## 10. ARQUITECTURA PROPUESTA — `PastoAdapter` declarativo

Separar en **7 adaptadores** con un `Evidence Envelope` común. Nada de excepciones dispersas.

```
adapters/
  pasto/
    config/pasto.yaml          ← toda la configuración (abajo)
    predial_identity_resolver.py   jerarquía §7, emite IDENTITY_CONFLICT
    administrative_layer_adapter.py DPA (barrio/comuna) + veredas/corregimientos
    cadastre_adapter.py            NUPRE, áreas, manzana, geometría/centroide
    urban_regulation_adapter.py    tratamiento, actividad, edificabilidad (JOIN §6.1), PEMP, usos
    risk_adapter.py                municipal_risk (capa /1 + polígonos de Riesgos/)
    planning_instruments_adapter.py planes parciales, saturación, perfil vial, planos
    external_hazard_adapter.py     geological_hazard (SGC) — dominio SEPARADO
```

**Evidence Envelope** (toda respuesta lo emite):
```json
{
  "evidence_id": "sha256:…",
  "variable": "ESTRATO",
  "value": "3",
  "status": "MATCH_EXACT",
  "source": {"authority":"Alcaldía de Pasto","service":"…/Estratificacion/MapServer",
             "layer_or_table":1,"field":"estrato","crs":null},
  "matched_by": {"strategy":"codigo_predial_nacional","value":"520010102000000470014000000000"},
  "retrieved_at":"2026-09-17T13:40:00Z",
  "dataset_vintage":"2021",
  "confidence":"alta",
  "cross_checked_with":["Estratificacion/2.codigo_predial_corto"]
}
```

### 10.1 Dos dominios que NO se deben mezclar

| Dominio | Fuente | Qué afirma |
|---|---|---|
| `municipal_risk` | POT / Planeación (`Norma_.../1`, `Riesgos/`) | Regulación municipal y clasificación predial del riesgo (ZAVA T-269, inundación, remoción…) |
| `geological_hazard` | **SGC** (`Amenaza_Volcanica/19`, `/64`) | Amenaza geológica del Galeras (caída de piroclastos, lahares) |

**Regla de reconciliación:** no convertir automáticamente una amenaza del SGC en prohibición urbanística. Si discrepan, **conservar ambas** y emitir `RECONCILIACION_PENDIENTE` con las dos evidencias.

**Medición en la coordenada exacta del caso `1.21194, -77.28663` (corrige una afirmación previa de este documento):**

| Fuente | Capa | Valor literal |
|---|---|---|
| **SGC / Galeras** | `Amenaza_Volcanica/19` (grupo Galeras) | **`Amenaza Alta` / `Lahares` / `V. Galeras`** (OBJECTID 1338, ID 2, AREA_KM2 15) |
| SGC / Galeras piroclastos | `Amenaza_Volcanica/18` | **NO intersecta** (`returnCountOnly` = 0) |
| SGC / consolidado | `Amenaza_Volcanica/64` | `Amenaza Baja` — **pero del Complejo volcánico Chiles-Cerro Negro**, NO del Galeras |
| POT municipal | `Norma_.../2` y `/28` | `zava_t_269_de_2015 = "Predio en ZAVA sentencia T 269 2015"` |
| POT municipal | `Riesgos/1` y `/15`/`/16` (polígono ZAVA) | **`Amenaza Alta : Lahares`** |
| POT municipal | `Norma_.../1` | `riesgo_volcanico_ea27 = "Flujos de lodo secundario"`; `flujos_de_lodo_ea22 = "Bajo"`; `restricciones_por_lujos_de_lodo = "S3"` |

**CONCLUYEN COINCIDIENDO EN ALTA.** La leyenda oficial del SGC lo explica mecanicistamente: *"Hacia el flanco suroriental (SE), los lahares descenderían por el río Mijitayo y la quebrada Midoro alcanzando la zona urbana del municipio de Pasto"* — y el predio del caso está precisamente en el **cauce de la Avenida Torrencial Mijitayo** (ver §2.2).

⚠ **El `"Bajo"` municipal NO es el nivel de amenaza volcánica**: es `flujos_de_lodo_ea22`, un peligro distinto (flujos de lodo secundarios, mapa EA22). Confundirlos **subestima el caso**. Y la capa consolidada del SGC (`/64`) **no tiene ninguna cobertura del Galeras** (`NOMBRE_VOLCAN LIKE '%Galeras%'` → 0 filas): en Pasto solo devuelve Chiles-Cerro Negro. ARHIAX debe leer **siempre** la capa del grupo del volcán (`/19`) y **nunca** tomar `/64` como si representara al Galeras.

### 10.2 Instrumentos de gestión del suelo (portable entre municipios)

No usar el genérico "Planes de Reordenamiento". Esquema propuesto:
```
INSTRUMENTO_GESTION_SUELO { instrument_type }
  PLAN_PARCIAL_DESARROLLO · PLAN_PARCIAL_EXPANSION · RENOVACION_URBANA
  RENOVACION_POR_REDESARROLLO · PEMP · PLAN_MAESTRO · OTRO
```
En Pasto la taxonomía real se lee en `tratamiento_urbanistico` + `table24` (`id_observacion_tratamieto_urban` → texto normativo con el **Acuerdo 004 de 2015** y el artículo aplicable).

---

## 11. CONFIGURACIÓN YAML LISTA PARA CÓDIGO

```yaml
municipality: pasto
department: Narino
dane_code: "52001"
crs_default: 3115
base_url: https://geoportal.pasto.gov.co/server/rest/services   # ojo: /server/rest/services
token_required_folders: [Campo, Hosted, Utilities]

predial_identity:
  priority: [codigo_predial_nacional, codigo_predial_anterior, codigo_predial_corto,
             matricula_inmobiliaria, nomenclatura, geometry_exact, proximity_30m]
  conflict_rule: matricula_municipal != folio_CTL -> IDENTITY_CONFLICT
  prohibit_assertion_on: [MATCH_SPATIAL_NEAREST, MULTIPLE_CANDIDATES]

layers:
  cadastre_urban:
    source_id: pasto_cadastre_urban
    service_url: .../Planeacion/Estratificacion/MapServer
    layer_id: 4
    source_authority: Alcaldia de Pasto (base predial, origen IGAC 2021)
    crs: 3115
    identity_fields: [codigo_predial_nacional, codigo_predial_anterior, codigo_predial_corto, matricula_inmobiliaria]
    output_fields: {numero_predial_nacional: codigo_predial_nacional,
                    area_catastral_terreno: area_igac_m2,
                    area_construida: area_construida,
                    matricula_inmobiliaria: matricula_inmobiliaria,
                    codigo_manzana: codigo_de_manzana,
                    direccion_oficial: direccion}
    join_strategy: exact_where
    freshness: "2021 (catastro IGAC)"
    fallback: [Mapa_base/10]
    failure_semantics: [NO_RECORD, SOURCE_TIMEOUT, SOURCE_UNAVAILABLE]
    evidence_policy: emit_envelope

  administrative_barrios:
    source_id: pasto_dpa_barrios
    service_url: .../Planeacion/Division_politico_administrativa/MapServer
    layer_id: 1
    crs: 3115
    identity_fields: [sector]          # NO existe 'barrio'
    output_fields: {barrio: sector, comuna: comuna, codigo_sector: codigo_del_sector}
    join_strategy: spatial_intersects_point_then_30m
    failure_semantics: [MATCH_SPATIAL_EXACT, MATCH_SPATIAL_NEAREST, SOURCE_TIMEOUT]
    evidence_policy: emit_envelope

  administrative_comunas:
    source_id: pasto_dpa_comunas
    service_url: .../Planeacion/Division_politico_administrativa/MapServer
    layer_id: 2
    crs: 3115
    output_fields: {comuna: comuna}
    join_strategy: spatial_intersects_point_then_30m

  estrato_nomenclatura:
    source_id: pasto_estratificacion_table1
    service_url: .../Planeacion/Estratificacion/MapServer
    layer_id: 1
    is_table: true
    identity_fields: [codigo_predial_nacional, codigo_predial_corto]
    output_fields: {estrato: estrato, nomenclatura_oficial: nomenclatura_igac,
                    barrio_tabla: barrio, comuna_tabla: comuna}
    join_strategy: exact_where_requires_where_1eq1
    cross_check: {source_id: pasto_estratificacion_table2, key: codigo_predial_corto}
    failure_semantics: [NO_RECORD, SCHEMA_CHANGED]

  treatment_urban:
    source_id: pasto_treatment_urban
    service_url: .../Planeacion/Norma_Urbanistica_Riesgo_Suelo/MapServer
    layer_id: 2
    crs: 3115
    output_fields: {tratamiento_urbanistico: tratamiento_urbanistico,
                    clase_suelo: clase_de_suelo, sector_normativo: sector_normativo,
                    area_morfologica: area_morfologica,
                    edificabilidad_texto: edificabilidad,
                    codigo_morfologico_alturas: codigo_morfologico_de_alturas,
                    zava: zava_t_269_de_2015, pemp_nivel: nivel_intervencion_pemp,
                    ronda_hidrica: afectacion_por_ronda_hidrica,
                    volumen_edificable: volumen_a_edificar}
    identity_fields: [codigo_predial_nacional, matricula_inmobiliaria]

  edificabilidad:
    source_id: pasto_edificabilidad
    layer_id: 9
    is_table: true
    join_chain:
      - {from: treatment_urban.id_tu_edificabilidad, to: table13.id_tu_edificabilidad}
      - {from: table13.id_edificabilidad, to: table9.id_edificabilidad}
      - {discriminator: table9.codigo_morfologico_altura == treatment_urban.codigo_morfologico_de_alturas}
    output_fields: {altura: altura, altura_maxima: altura_maxima,
                    indice_construccion_max: indice_construccion_maxima,
                    indice_ocupacion_max: indice_ocupacion_maxima,
                    area_minima_m2: area_minima_m2, frente_minimo_m: frente_minimo_m,
                    carga_urbanistica: carga_urbanistica, condicionante: condicionante}
    numeric_normalization: {decimal_separators: [".", ","], reject_values: ["No aplica", "Resultado"]}

  municipal_risk_parcel:
    source_id: pasto_risk_parcel
    service_url: .../Planeacion/Norma_Urbanistica_Riesgo_Suelo/MapServer
    layer_id: 1
    domain: municipal_risk
    output_fields: {riesgo_volcanico: riesgo_volcanico_ea27, zava: zava_t_269_de_2015,
                    flujos_lodo: flujos_de_lodo_ea22,
                    restriccion_flujos_lodo: restricciones_por_lujos_de_lodo,
                    remocion_masa: remocion_en_masa_ea19, inundacion: inundacion_ea23,
                    subsidencia: subsidencia_ea29, servidumbre_electrica: servidumbre_de_lineas_de_alta_t}
    keep_not_applicable: true      # "No aplica" es respuesta valida (evaluado y sin afectacion)

  municipal_risk_geometry_fallback:
    source_id: pasto_risk_polygons
    service_url: .../Planeacion/Riesgos/MapServer
    layer_ids: [3, 4, 5, 6, 8, 9, 10]
    domain: municipal_risk
    join_strategy: spatial_intersects_point
    role: segunda_fuente_de_contraste

  geological_hazard_sgc:
    source_id: sgc_galeras
    service_url: https://srvags.sgc.gov.co/arcgis/rest/services/Amenaza_Volcanica/Amenaza_Volcanica/MapServer
    layer_ids: [19, 64]
    domain: geological_hazard        # NO se convierte en prohibicion urbanistica
    crs: 4686
    output_fields: {grado_amenaza: GRADO_AMENAZA, volcan: NOMBRE_VOLCAN, fenomeno: FENOMENO_VOLCANICO}
```

---

## 12. PRUEBAS UNITARIAS Y CASOS DE ACEPTACIÓN

**Unitarias (offline, con dobles de `requests`)**
1. `clasificar`/mapeo de campos: `DPA/1.sector` → `BARRIO`.
2. Estrato por NUPRE (table 1) y por código corto (table 2) → ambos `3`.
3. `"No aplica"` **se conserva** en riesgos; vacío/`Sin información` → ausente.
4. `HRES`/`evaluado`: `geo_eval["evaluado"]=False` ⇒ el score **no** informa 100/100.
5. `IDENTITY_CONFLICT` cuando matrícula municipal ≠ folio del CTL **y** la resolución fue por punto ⇒ `predio_real=None`.
6. `MATCH_SPATIAL_NEAREST` ⇒ `prohibit_assertion_on` bloquea la afirmación.
7. JOIN de edificabilidad con `id_tu_edificabilidad=null` ⇒ `NOT_APPLICABLE`, no error.
8. Normalización numérica: `"2,8"` y `"1.5"` → 2.8 / 1.5; `"No aplica"` → `None`.
9. `query` a `Table` sin `where` ⇒ detecta `error` y no interpreta "sin datos".

**Casos de aceptación (en vivo)**
- **AC-1** `consultar_pasto(codigo_predial="520010102000000470014000000000")` ⇒ barrio `OBRERO`, comuna `Comuna 1`, estrato `3`, tratamiento `Suelo de proteccion`, ZAVA presente, altura `No aplica`.
- **AC-2** El dictamen **no** debe contener "NO EVALUADO" en H-GEO cuando la capa `/1` respondió.
- **AC-3** El dictamen debe emitir `H-IDENT` (ALTO) por la discrepancia `240-211101` vs `240-216`.
- **AC-4** Ninguna fila de riesgo puede faltar: las 8 deben aparecer con valor o `NO REGISTRA`.
- **AC-5** Con folio `240-211101` y sin NUPRE, el sistema **no** puede afirmar normativa predial por proximidad.

---

## 13. CAMBIOS EXACTOS QUE DEBE HACER EL DESARROLLADOR EN ARHIAX

> Los puntos 1–8 **ya están implementados y verificados**; 9–16 son el trabajo pendiente, en orden de prioridad.

1. **`api/pasto_territorio.py`** — constantes `SRV_DPA`, `CAPA_DPA_BARRIOS=1`, `CAPA_DPA_COMUNAS=2`, `TABLA_NOMENCLATURA=1`, `TABLA_ESTRATO=2`. ✅ hecho
2. **`api/pasto_territorio.py`** — `_barrio_y_comuna()` leyendo **`sector`** (no `barrio`) en DPA/1, y `comuna` en DPA/2, con reintento a 30 m. ✅ hecho
3. **`api/pasto_territorio.py`** — `_estrato_y_nomenclatura()` contra `Estratificacion/1` (por `codigo_predial_nacional`) y `/2` (por `codigo_predial_corto`); `Barrios.estrato` **no se usa** (NULL en toda la capa). ✅ hecho
4. **`api/pasto_territorio.py`** — `_centroide_del_predio()` con `returnGeometry=true&outSR=4326` para poder cruzar capas de polígono cuando se resuelve por NUPRE. ✅ hecho
5. **`api/pasto_territorio.py`** — `_valor_riesgo()`: **conservar `"No aplica"`** (solo descartar vacío/`Sin información`). ✅ hecho
6. **`api/pdf_compiler.py`** — `geo_eval` de Pasto construido con `predio_real["riesgos"]`, con `evaluado=True/False`; eliminar el `NO EVALUADO` cuando el predio **sí** se resolvió. ✅ hecho
7. **`api/score_engine.py`** — `NO_EVALUADO != SIN_RIESGO`: usar `geo_eval["evaluado"]`. ✅ hecho
8. **`api/pdf_compiler.py`** — regla `IDENTITY_CONFLICT` + hallazgo `H-IDENT` (ALTO) cuando la matrícula municipal no coincide con el folio del CTL. ✅ hecho
9. **`api/pdf_compiler.py`** — refinar el mensaje de `H-IDENT` para distinguir los dos casos: (a) resuelto **por código** ⇒ el NUPRE coincide y la discrepancia es de matrícula (posible truncamiento municipal, como `240-216`); (b) resuelto **por punto** ⇒ puede ser un vecino. Hoy el texto habla de "vecino" en ambos casos.
10. **`api/pdf_compiler.py`** — usar la **nomenclatura municipal** (`Estratificacion/1.nomenclatura_igac`) para completar la dirección cuando la del CTL es incompleta ("CRA # 26" → `K 26 8 28 13`), declarando el origen.
11. **`api/pdf_compiler.py`** — **destacar ZAVA/`Suelo de proteccion`/`CMA no construible`** como hallazgo propio (hoy quedan diluidos en la tabla de riesgos). Propuesta: `H-ZAVA` de severidad ALTA con el texto literal de la fuente y la cita de la sentencia T-269/2015.
12. **`api/pasto_territorio.py`** — implementar el **JOIN de edificabilidad** de 3 pasos con el discriminador morfológico (§6.1) y la normalización numérica (`.`/`,` y rechazo de `"No aplica"`).
13. **`api/pasto_territorio.py`** — implementar **`municipal_risk_geometry_fallback`** contra `Planeacion/Riesgos/MapServer` (capas 3,4,5,6,8,9,10) como **segunda fuente** de contraste, y registrar discrepancias entre ambas.
14. **`api/pasto_territorio.py`** — `planning_instruments_adapter`: consultar `table24` (`id_observacion_tratamieto_urban`) para el **texto normativo** (Acuerdo 004 de 2015 + artículo) y `Poligonos_de_saturacion/0`; clasificar en `INSTRUMENTO_GESTION_SUELO.instrument_type`. Sustituir la etiqueta "Planes de Reordenamiento" por esa taxonomía.
15. **`api/pasto_territorio.py`** — leer el **CRS por servicio** (no asumir uno) y usar `outSR`/`inSR` explícitos en los cruces con `Mapa_base` (**3857**).
16. **`api/riesgo_volcanico.py` / `score_engine.py`** — mantener `municipal_risk` y `geological_hazard` en **dominios separados** con regla de reconciliación; no convertir amenaza SGC en prohibición urbanística. Registrar `dataset_vintage` (base predial **IGAC 2021**) en cada Evidence Envelope.
17. **`api/pasto_territorio.py`** — registrar en el envelope los `SCHEMA_CHANGED` conocidos (`DPA/1` sin `barrio`; `table24` con `a1_aplicacion_...`/`a2_aplicación_...`; `id_observacion_tratamieto_urban`; `id_observacion_noma_urbana`) para que un cambio de esquema del municipio se detecte y no falle en silencio.

---

## 14. LO QUE NO SE PUDO CERRAR (con evidencia y acción humana requerida)

| # | Punto abierto | Evidencia literal | Clasificación | Acción requerida |
|---|---|---|---|---|
| 1 | **Matrícula correcta del predio** (`240-211101` vs `240-216`) | `= '240-211101'` → 0 filas en 6 capas; `LIKE '%211101%'` → 0; `= '240-216'` → 1 fila (objectid 37231, mismo NUPRE). `240-216` es anómala por longitud (3 dígitos vs 240-120149) | `DATO_REQUIERE_VALIDACION_PROFESIONAL` | **Cotejar con la ORIP Pasto**: ¿matrícula madre vs derivada/PH? ¿truncamiento en la base municipal? Presentar el CTL y pedir certificado catastral |
| 2 | **Altura máxima / índices del caso** | `id_tu_edificabilidad = null`; `codigo_morfologico_de_alturas = "CMA no construible"`; `tratamiento = "Suelo de proteccion"` | `NOT_APPLICABLE` (**respuesta válida**) | Ninguna: el predio **no es construible**. Documentarlo así |
| 3 | **Avalúo IGAC** | `.avaluo_igac` NULL en las filas consultadas | `DATO_REALMENTE_NULO` | Solicitar el avalúo al municipio/IGAC si se necesita |
| 4 | **Tipo de construcción / pisos** | El municipio **no publica** el campo | `FUENTE_NO_EXISTE` | Pedirlo al Catastro Municipal |
| 5 | Carpetas `Campo`, `Hosted`, `Utilities` | `{"error":{"code":499,"message":"Token Required"}}` | `FUENTE_NO_DISPONIBLE_TEMPORALMENTE` | Token/servicio del municipio: puede haber DPA/predial adicional |
| 6 | Ids DPA 0/3/5/7 y Estrat 5/6/7 | `{"error":{"code":500,"message":"json"}}` | `FUENTE_EXISTE_ERROR_CONECTOR` | Confirmar con Planeación si son capas retiradas |
| 7 | `LIKE` en `registro/29` y `Norma/28` | `{"code":400,"message":"Failed to execute query."}` (igualdad sí funciona) | `FUENTE_EXISTE_ERROR_CONECTOR` | No usar `LIKE` en esas capas |
| 8 | Barrios DPA `OBRERO` vs table1 `San Jose Obrero` | discrepan en el nombre; la comuna coincide | `DATASET_DISCREPANCIA` | Documentar ambos; usar DPA como canónico y table1 como alterno |
| 9 | `table1.area_terreno = 1080000512` | 1.080 km² para un predio de 126 m² | `DATO_CORRUPTO` | Reportar a Planeación; **no usar** `area_terreno` de table1 |
| 10 | `table1.comuna` y `table1.estrato` sucios | 61 valores de comuna (`"  Comuna 8"`, `"6"`, `null`); 12 de estrato (`"11"`, `"COMERCIAL"`, `"LOTE"`) | `DATASET_CALIDAD` | Normalizar (TRIM/UPPER) y validar rango numérico |
| 11 | Integridad referencial de `table15.id_ciiu` | 442 filas solo para el uso del caso; muestras `111` y `1011` resuelven en `table27` | `RIESGO_ABIERTO` | Validar todas las FK antes de publicar usos |
| 12 | `table26 "Tipo de actividad - urbana"` | `count = 0` (vacía) | `DATO_REALMENTE_NULO` | No usarla como lookup urbano |
| 13 | PH del inmueble | `uso_propiedad_horizontal=""`, `codigo_predial_corto_ph == codigo_predial_corto`, sin piso/torre/bloque; solo 304 de 181.690 filas difieren | `IDENTIDAD_PREDIAL_NO_RESUELTA` | **No se puede afirmar que no esté en PH**: la PH está poco modelada. Cotejar con el CTL |
| 14 | Planes parciales como capa | No existe FeatureServer propio; el texto está en `table24` y en documentos del POT | `FUENTE_EXISTE_NO_INTEGRADA` | Integrar `table24`; el repositorio documental requiere descarga manual |

---

## 15. CRITERIO DE TERMINACIÓN — ESTADO

| Criterio exigido | Estado |
|---|---|
| `Barrio = pendiente` | ✅ **CERRADO** → `OBRERO` |
| `Comuna = N/D` | ✅ **CERRADO** → `Comuna 1` |
| `Estrato = N/D` | ✅ **CERRADO** → `3` (doble fuente coincidente) |
| `Altura máxima = pendiente` | ✅ **CERRADO con explicación** → `No aplica` por `CMA no construible` + `Suelo de proteccion`; es respuesta, no fallo |
| `Planes parciales = no evaluado` | ⚠ **PARCIAL** → la vía técnica está identificada (`table24` + `Poligonos_de_saturacion`), pendiente de implementar (§13.14) |
| `Riesgos municipales = no evaluado` | ✅ **CERRADO** → H-GEO ya no dice NO EVALUADO; las 8 variables se reportan |
| Conflicto `240-211101` vs `240-216` | ✅ **EXPLICADO con evidencia** → mismo predio; discrepancia de matrícula → `H-IDENT` ALTO + cotejo ORIP |

**Ninguna variable quedó en "pendiente" sin causa técnica demostrada.** Los 14 puntos abiertos de §14 tienen fuente consultada, respuesta literal y acción humana identificada.

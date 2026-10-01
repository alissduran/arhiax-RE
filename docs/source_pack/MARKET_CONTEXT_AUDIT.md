# MARKET CONTEXT AUDIT — ¿Qué alimenta realmente `market_context`?

**Tipo de entrega:** auditoría READ-ONLY.
**Ámbito:** motor de valoración actual (`api/market_context.py`, `api/market_sources.py`,
`api/dictamen_data.py`, `api/pdf_compiler.py`, `api/dictus_ejecutivo.py`,
`motor_tma_lonja_baq_v1.0/**`, Golden `docs/forensics/040-646406/dictus_2b/**`, `tests/**`).
**Fecha de la corrida auditada (Golden 2.0B):** `2026-09-28T20:47:36Z`
(`DICTUS_RUN_STATE_040-646406.json` → `receipts.generated_at`).

**Declaración de alcance (no cumplida parcialmente, sino total):** NO se modificó ningún archivo
de `api/`, ningún PDF, ningún test, ningún YAML ni ningún JSON de `docs/forensics/`. El único
archivo creado por esta auditoría es este documento.

**Método:** lectura directa de código y artefactos; extracción de texto de los PDF con `pypdf`
6.10.2; recálculo propio de SHA-256 con `Get-FileHash`; grep exhaustivo de `lonja|Lonja|LONJA`
(incluido `-AllMatches`) sobre `api/`, `tests/`, `scripts/`, `motor_tma_lonja_baq_v1.0/` y
`docs/`.

### Nota de estabilidad de la evidencia (verificada antes de cerrar)

Durante esta auditoría se detectó que **otro proceso está escribiendo en el repositorio en
paralelo**. Se midió la antigüedad de cada archivo citado (`LastWriteTime`) para separar la
evidencia estable de la que se mueve:

| Evidencia citada | Antigüedad medida | Estado |
|---|---|---|
| `motor_tma_lonja_baq_v1.0/.../lonja_layer/lonja_baq_metodologia.yaml` | **~31.025 min (≈21,5 días)** | **ESTABLE** |
| `docs/forensics/040-646406/dictus_2b/DICTUS_RUN_STATE_040-646406.json` | ~1.170 min (≈19,5 h) | **ESTABLE** |
| `docs/forensics/040-646406/dictus_2b/DICTUS_MANIFEST_040-646406.json` | ~1.170 min | **ESTABLE** |
| `docs/forensics/040-646406/dictus_2b/DICTUS_EJECUTIVO_040-646406.pdf` | ~1.170 min | **ESTABLE** |
| `api/market_context.py` (~8.089 min) · `api/dictamen_data.py` (~9.890 min) · `api/pdf_compiler.py` (~1.543 min) · `api/dictus_ejecutivo.py` (~1.181 min) · `api/dictus_secciones.py` (~1.255 min) · `api/dictus_estado.py` (~1.263 min) | todas anteriores al inicio de esta auditoría (~11:04) | **ESTABLE** |
| `api/market_sources.py` (~99 min) · `api/source_licenses.py` (~88 min) · `docs/source_pack/lonja_market_baq_v1.json` (~100 min) | modificados ~09:36–09:40, **antes** del inicio de esta auditoría | **ESTABLE** |
| `api/source_licenses_v2.py` (creado 11:00) · `docs/source_pack/INSTITUTIONAL_PARTNERS.md` (11:02) · `api/acquisition.py` (creado 11:04, modificado 11:16:48) · `tests/test_source_pack_licenses.py` (creado 11:06) | **creados/modificados DURANTE esta sesión por un escritor concurrente** | **INESTABLE — ver aviso** |

> **AVISO IMPORTANTE.** Los cuatro archivos de la última fila **no fueron creados ni modificados
> por esta auditoría** (que sólo escribió `docs/source_pack/MARKET_CONTEXT_AUDIT.md`). Aparecieron
> en el workspace mientras se ejecutaba este análisis, y son precisamente las piezas que
> **implementan en paralelo la doctrina «la Lonja no es fuente»** (`api/source_licenses_v2.py`)
> y su prueba (`tests/test_source_pack_licenses.py`).
>
> Consecuencia práctica: el Anexo A.7, el Anexo D.2 y la sección final **«LONJA: NO ES FUENTE»**
> se apoyan en evidencia que está siendo escrita justo ahora. Su contenido se leyó y verificó
> (los números de línea citados son los reales del archivo en el momento de la lectura), pero
> **deben re-verificarse antes de actuar sobre las sustituciones del Anexo C**. Todo el resto de
> la auditoría (respuestas 1–5, Anexos A.1–A.6, B, C, D.1, D.3, D.4) se apoya en evidencia
> **estable** y no cambia.

---

## RESPUESTA 1 — ¿Qué fuente REAL alimenta hoy `market_context`?

**Respuesta corta: un único archivo YAML local del propio repositorio, versionado dentro del
producto.** No hay fuente externa. No hay base de datos. No hay servicio.

**La cadena completa, con evidencia:**

| Paso | Qué ocurre | Evidencia (ruta:línea) |
|---|---|---|
| 1 | Se fija la ruta del artefacto: un archivo **dentro del repo**, relativo a `api/` | `api/market_context.py:48-52` → `_YAML_PATH = Path(__file__).resolve().parent.parent / "motor_tma_lonja_baq_v1.0" / "motor_tma_lonja_baq_v1.0" / "lonja_layer" / "lonja_baq_metodologia.yaml"` |
| 2 | Se lee el YAML con `yaml.safe_load` | `api/market_context.py:55-58` → `def _load_lonja(...): with open(p, encoding="utf-8") as f: return yaml.safe_load(f)` |
| 3 | Se extrae la metadata de versión/vigencia **desde ese YAML** | `api/market_context.py:61-72` → `lonja_metadata()` lee `declaracion` y `regla_consolidacion` |
| 4 | Se extraen los valores por m² **desde ese YAML** | `api/market_context.py:116` → `sectores = y.get("valor_suelo_por_sector") or {}` |
| 5 | El barrio se convierte en sector por comparación de cadenas contra las claves del YAML | `api/market_context.py:148-163` |
| 6 | Se toma el valor central, los rangos y la `fuente` declarada **de la fila del YAML** | `api/market_context.py:174-182` → `"value_m2": sector.get("valor_central_m2")`, `"source": sector.get("fuente")` |
| 7 | Se calcula id + versión + **sha256 del archivo local** | `api/market_context.py:84-103` → `sha = hashlib.sha256(p.read_bytes()).hexdigest()` |
| 8 | `market_rate_source` cae a la `fuente` del YAML si el llamador no la pasa | `api/market_context.py:208-210` |
| 9 | **Llamador de producción** (el único real): el compilador de PDF | `api/pdf_compiler.py:1275` → `_sector = resolve_market_sector(_mc_barrio)`; `:1276-1285` → `build_market_context(..., sector_resolution=_sector, market_rate_source=None)` (comentario en `:1285`: `# derivada del sector por el builder`) |
| 10 | La valoración **solo** acepta la tasa del `MarketContext`, no vuelve a resolver el sector | `api/dictamen_data.py:127-134` → `val_m2_mercado = _sector.get("value_m2")`; `:64-67` docstring: *"ÚNICA AUTORIDAD de la tasa de mercado: `market_context` (`sector_metodologico.value_m2`)"* |

**El artefacto que es la única fuente** es
`motor_tma_lonja_baq_v1.0/motor_tma_lonja_baq_v1.0/lonja_layer/lonja_baq_metodologia.yaml`
(256 líneas). El valor aplicado al Golden está declarado a mano en `:207-218`:

```yaml
valor_suelo_por_sector:
  Miramar:
    # Actualizado Q3-2026 con precio real de mercado verificado por el
    # propietario en la constructora del proyecto (unidades ~58 m2 terminadas
    # en venta ~$420.000.000 ≈ $7.1M/m2). El valor anterior ($4.5M/m2, Q2-2026)
    # quedaba ~40% por debajo del mercado observado y el dictamen del folio real
    # 040-646406 (Napoli, Torre 8 apto 430) subestimaba el inmueble.
    valor_central_m2: 6800000
    rango_min_m2: 5500000
    rango_max_m2: 8000000
    vigencia: "Q3-2026"
    fuente: "Precio de venta verificado en la constructora del proyecto (unidades ~58 m2 terminadas, 2026) + Lonja BAQ referencial"
```

**Lo que NO alimenta `market_context` (verificado, no supuesto):**

- **`api/data/**` — no participa.** Contiene solo tres archivos, ninguno de mercado:
  `api/data/amenaza_remocion_masa.geojson` (8.160.494 B),
  `api/data/areas_en_riesgo.geojson` (6.176.524 B),
  `api/data/barranquilla_adopcion_anexo1.json` (838 B). Son capas de riesgo/adopción, no tasas.
- **El CTL — no aporta la tasa.** El CTL alimenta `tipologia` y `condicion_juridica`
  (`api/dictus_secciones.py:702-713`), es decir **identidad**, no precio. El YAML lo dice en su
  propia cabecera: el motor es un *"EJECUTOR de lo declarado aquí"* (`lonja_baq_metodologia.yaml:5-7`).
- **El catastro — no aporta la tasa.** Aporta `barrio`, `estrato`, `destino_economico` y
  coordenadas (`api/pdf_compiler.py:1240-1263`; `DICTUS_RUN_STATE_040-646406.json:1149-1158`
  → `source_system: CATASTRO_MUNICIPAL_BARRANQUILLA_ARCGIS`). Es la **clave de búsqueda**
  (el barrio) con la que se consulta el YAML, no el valor.
- **`api/market_sources.py` — no es una segunda fuente.** Es un derivador: construye una tabla
  versionada **a partir del mismo YAML**. `api/market_sources.py:263-273`:
  `metodologia = _mc._load_lonja()  # artefacto real (sin caché)`; `:294-301` copia
  `resolucion.get("value_m2")` del propio `resolve_market_sector`. El JSON resultante
  (`docs/source_pack/lonja_market_baq_v1.json:38` → `"value_per_m2": 6800000`) es una **copia
  derivada**, no un insumo independiente.

**Conclusión 1:** la "fuente de mercado" del producto es **un parámetro declarado dentro del
repositorio**, escrito a mano, cuya procedencia última declarada por el propio texto es *"precio
de venta verificado por el propietario en la constructora"* más un añadido no verificable
*"+ Lonja BAQ referencial"*.

---

## RESPUESTA 2 — ¿Qué datos EXTERNOS (red/servicio) utiliza hoy para mercado?

**Respuesta: NINGUNO. Cero endpoints. Cero servicios. El camino de mercado es 100 % local.**

Pruebas de ausencia (verificadas por grep de `requests|urllib|httpx|http.client|socket|aiohttp|urlopen|fetch|https?://`):

| Módulo | Import/uso de red | Resultado |
|---|---|---|
| `api/market_context.py` | grep del patrón | **0 coincidencias** |
| `api/market_sources.py` | grep de `http|url|urllib|requests|socket|endpoint` | **0 coincidencias** |

Declaración explícita del propio producto de que **no hay URL** ni descarga — el registro de
licencias del pack v1:

`api/source_licenses.py:239-251`
```python
"LONJA_METODOLOGIA_LOCAL": {
    "url": None,
    "ruta_local": str(RUTA_METODOLOGIA_LONJA.relative_to(_DIR_RAIZ)),
    "consulted_at": FECHA_CONSULTA,
    "http_status": None,
    "bytes": None,
    "sha256": None,       # se rellena en tiempo de ejecución (artefacto real)
    "descargado": True,
    "resultado": DECLARED,
    "motivo": ("La licencia es CONTRACTUAL y el documento vive en el repositorio: su "
               "contenido se puede hashear localmente, pero un contrato no se verifica "
               "contra una URL pública. ..."),
}
```

Y el campo que el pack llama `base_url` **no es una URL**: es un esquema `local:`

`docs/source_pack/barranquilla_sources_v1.json:826`
```json
"base_url": "local:motor_tma_lonja_baq_v1.0/motor_tma_lonja_baq_v1.0/lonja_layer/lonja_baq_metodologia.yaml",
```

**Servicios externos que SÍ existen en el producto, pero para OTRAS fuentes (no mercado):**

| Servicio | Endpoint | Qué alimenta | Evidencia |
|---|---|---|---|
| ArcGIS catastro municipal | `https://miciudad.barranquilla.gov.co/gis/rest/services/catastro/datosabiertos` | identidad/geometría catastral | `api/integrations/catastro_live.py:25`; `api/integrations/territorio.py:54` |
| Overpass API (OSM) | `https://overpass-api.de/api/interpreter`, `https://maps.mail.ru/osm/tools/overpass/api/interpreter`, `https://overpass.kumi.systems/api/interpreter` | equipamiento/POI (entorno) | `api/poi_engine.py:24-26` |
| Photon (Komoot) | `https://photon.komoot.io/api/` | geocodificación de direcciones | `api/poi_engine.py:45` |

Ninguno de los tres interviene en `market_context`. La separación está declarada en
`docs/source_pack/RESOLUTION_LADDER.md:231`:
`| mercado | ZONA_MERCADO | LONJA_MARKET_BAQ | — (el mercado no se sustituye por contexto) | — |`

**Conclusión 2:** si el YAML local desaparece o está corrupto, **no hay ninguna otra vía** de
obtener un valor de mercado. No hay red de respaldo porque no hay red.

---

## RESPUESTA 3 — ¿Qué parte es FUENTE y qué parte es CÁLCULO?

### 3.a · FUENTE (dato declarado, leído — no derivado)

Todo esto vive en el YAML local `lonja_baq_metodologia.yaml` y se **transcribe**, no se calcula:

| Dato declarado | Valor | Evidencia |
|---|---|---|
| Valor del suelo Miramar | `6800000` | `lonja_baq_metodologia.yaml:214` |
| Rango Miramar | `5500000` – `8000000` | `lonja_baq_metodologia.yaml:215-216` |
| `fuente` declarada de la fila Miramar | *"Precio de venta verificado en la constructora … + Lonja BAQ referencial"* | `lonja_baq_metodologia.yaml:218` |
| Valores Riomar / Villa_Country / Alto_Prado | `5200000` / `4800000` / `5500000` | `lonja_baq_metodologia.yaml:220, 225, 230` |
| Entidad declarante | `"Lonja de Propiedad Raíz de Barranquilla"` | `lonja_baq_metodologia.yaml:19` |
| Vigencia | `2026-05-08` → `2026-08-31` | `lonja_baq_metodologia.yaml:22-23` |
| Versión | `"0.1-codiseno"` | `lonja_baq_metodologia.yaml:63` |
| Autor declarado | `"Junta Técnica de Avalúos Corporativos — Lonja BAQ"` | `lonja_baq_metodologia.yaml:62` |
| Cap rate M3 estrato 4 | `0.0485` | `lonja_baq_metodologia.yaml:138` |
| Factor de costos M2 | `1.2576` | `lonja_baq_metodologia.yaml:91` |
| Pesos de consolidación | M1 `0.60` / M2 `0.30` / M3 `0.10` | `lonja_baq_metodologia.yaml:66-69` |
| Corrimiento oferta→cierre | `0.06 / 0.08 / 0.10` | `lonja_baq_metodologia.yaml:177-180` |
| Coeficientes Fitto-Corvini | tablas A/C por clase | `lonja_baq_metodologia.yaml:118-126` |

### 3.b · CÁLCULO / DERIVACIÓN (propio del producto)

| Derivación | Qué hace | Evidencia |
|---|---|---|
| Normalización barrio→sector | `str.replace(" ", "_").strip().title()` + comparación de igualdad | `api/market_context.py:148-163` |
| Identidad metodológica | id + versión + **sha256 del archivo local** | `api/market_context.py:84-103` |
| Evaluación de suficiencia (`ready`/`blockers`) | 6 criterios, incluido que la tasa exista y sea `> 0` | `api/market_context.py:244-283` |
| Autorización del contexto | rechaza `GENERIC_ESTRATO_FALLBACK` | `api/market_context.py:290-298` |
| Tabla versionada derivada | transcribe filas del YAML + declara atributos ausentes | `api/market_sources.py:263-337` |
| Aritmética de valoración (M1/M2/M3, bandas) | consolidación y bandas | `api/dictamen_data.py:185-230` |

**Frontera nítida:** el **barrio** llega de una fuente oficial (catastro/POT,
`DICTUS_RUN_STATE_040-646406.json:1077-1081` → `"source": "official POT / Alcaldía"`), pero la
**tasa $/m² no se calcula en ningún sitio**: se lee de la constante YAML. El Golden lo confirma:
`value_m2 = 6800000` en `DICTUS_RUN_STATE_040-646406.json:1108` es **idéntico** al literal de
`lonja_baq_metodologia.yaml:214`, sin transformación intermedia.

**Advertencia de honestidad (sobre la parte "declarada"):** el YAML no es un dato de tercero
recibido; es un archivo **borrador autorado por el proveedor**. Su propia cabecera lo dice:

- `lonja_baq_metodologia.yaml:11` → `# Versión: 0.1 — borrador para co-diseño con Sinergia (07-May-2026)`
- `lonja_baq_metodologia.yaml:20-21` → `representante_legal: "[A declarar por la Lonja]"` / `presidente_comite_tecnico: "[A declarar por la Lonja]"`

Y el motor original del que proviene declara explícitamente que la validación por la Lonja está
**pendiente**:

- `motor_tma_lonja_baq_v1.0/motor_tma_lonja_baq_v1.0/tma_engine/piezas/pieza_4_motor_consolidacion.py:35`
  → `autor="Metodología corporativa Sinergia LAI v1.0 (pendiente validación con metodología corporativa Lonja BAQ)"`
- `motor_tma_lonja_baq_v1.0/motor_tma_lonja_baq_v1.0/output_referencia/dictamen_napoli.html:557`
  → *"Metodología corporativa Sinergia LAI v1.0 (pendiente validación con metodología corporativa Lonja BAQ)"*

---

## RESPUESTA 4 — ¿Existe provenance VERIFICABLE?

**Respuesta: existe provenance VERIFICABLE DE INTEGRIDAD DEL ARCHIVO LOCAL, y NO existe
provenance verificable DE LA FUENTE DEL DATO.** Es un sello de cadena de custodia interna, no
una trazabilidad a un origen externo.

### 4.a · Lo que SÍ existe (campo concreto y valor en el Golden)

`docs/forensics/040-646406/dictus_2b/DICTUS_RUN_STATE_040-646406.json:1097-1121`
```json
"sector_metodologico": {
  "input_barrio": "Miramar",
  "matched_sector": "Miramar",
  "match_type": "EXACT",
  "methodology_version": "0.1-codiseno",
  "market_methodology_id": "lonja_baq_metodologia",
  "market_methodology_version": "0.1-codiseno",
  "market_methodology_sha256": "4ccd5832eacf3117424fa436765e80d3e9198b666d9e3c293063a5b207ebd348",
  "market_methodology_file": "lonja_baq_metodologia.yaml",
  "methodology_entity": "Lonja de Propiedad Raíz de Barranquilla",
  "vigencia_desde": "2026-05-08",
  "value_m2": 6800000,
  "source": "Precio de venta verificado en la constructora del proyecto (unidades ~58 m2 terminadas, 2026) + Lonja BAQ referencial",
  "source_date": "Q3-2026",
  "rango_min_m2": 5500000,
  "rango_max_m2": 8000000,
  "provenance": { ... }
}
```

Idéntico en `DICTUS_MANIFEST_040-646406.json:1450-1474` (`market_methodology_sha256` en `:1457`,
`source` en `:1462`, `source_date` en `:1463`). Bloque espejo del contexto completo en
`DICTUS_RUN_STATE_040-646406.json:1123-1140` y `DICTUS_MANIFEST_040-646406.json:1476-1493`.

| Campo de provenance | ¿Existe? | Valor en el Golden | Qué acredita realmente |
|---|---|---|---|
| `market_methodology_id` | SÍ | `"lonja_baq_metodologia"` | nombre de identificador local |
| `market_methodology_version` | SÍ | `"0.1-codiseno"` | versión **de borrador co-diseñado** |
| `market_methodology_file` | SÍ | `"lonja_baq_metodologia.yaml"` | nombre de archivo local |
| `market_methodology_sha256` | SÍ | `4ccd5832eacf3117…ebd348` | **integridad del archivo local** (no del origen) |
| `methodology_entity` | SÍ | `"Lonja de Propiedad Raíz de Barranquilla"` | **cadena escrita a mano** en el YAML `:19` |
| `artifact_autor` | SÍ | `"Junta Técnica de Avalúos Corporativos — Lonja BAQ"` | **cadena escrita a mano** en el YAML `:62` |
| `source_date` | SÍ, pero **es un trimestre** | `"Q3-2026"` | periodicidad declarada, **no una fecha de dato** |
| `vigencia_desde` / `vigencia_hasta` | SÓLO `desde` viaja | `"2026-05-08"` | el `hasta` (`2026-08-31`) **ya estaba vencido** en la corrida |
| `url` de la fuente | **NO** | `null` (`api/source_licenses.py:240`) | — |
| `http_status` | **NO** | `null` (`api/source_licenses.py:243`) | — |
| `bytes` descargados | **NO** | `null` (`api/source_licenses.py:244`) | — |
| `consulted_at` de la fuente | **NO** (sólo fecha de auditoría del pack) | `FECHA_CONSULTA` = `2026-09-29` (`api/source_licenses.py:242`, `:64` de v2) | fecha en que se hasheó el archivo local |
| `sample_size` / nº de comparables | **NO** | `null` (`docs/source_pack/lonja_market_baq_v1.json:43`) | — |
| Listado de testigos/comparables | **NO** | no existe en ningún artefacto | — |
| Licencia | **DECLARED, no VERIFIED** | `resultado: DECLARED` (`api/source_licenses.py:247`) | falta el contrato firmado |

### 4.b · El `sha256` que sí existe **no prueba la fuente**: prueba un archivo mutable local

Tres valores distintos de huella para el **mismo** artefacto, medidos en esta auditoría:

| Procedencia de la huella | Valor | Evidencia |
|---|---|---|
| Empaquetado declarado junto al motor | `b8d8f9383cd21b8e167364f7f392dc11d3bc0c76ae2eaefa2537e9279e902dae` | `motor_tma_lonja_baq_v1.0/motor_tma_lonja_baq_v1.0/MANIFEST.sha256:6` |
| **Archivo en disco hoy** (recalculado por esta auditoría con `Get-FileHash`) | `4ccd5832eacf3117424fa436765e80d3e9198b666d9e3c293063a5b207ebd348` | recálculo propio; coincide con `DICTUS_RUN_STATE_040-646406.json:1104` |
| "Hash YAML Lonja v0.1" declarado en el README del paquete | `e8071f829afdb4b69116da794068641f` | `motor_tma_lonja_baq_v1.0/motor_tma_lonja_baq_v1.0/README.md:152` |

**Interpretación verificable:** el `sha256` del runtime **no coincide** con el `MANIFEST.sha256`
del paquete del que proviene el artefacto. El archivo fue **editado en su sitio** después del
empaquetado (la edición está documentada en su propio comentario, `:209-213`: *"Actualizado
Q3-2026 … El valor anterior ($4.5M/m2, Q2-2026) quedaba ~40% por debajo del mercado observado"*).
Un `sha256` de un archivo que se edita a mano acredita **que el archivo no cambió desde la
corrida**, no **que el dato venga de un tercero**.

**Agravante adicional, verificable:** la metodología viajó **con la vigencia vencida**. El YAML
declara `vigencia_hasta: "2026-08-31"` (`lonja_baq_metodologia.yaml:23`) y la corrida es del
`2026-09-28` (`DICTUS_RUN_STATE_040-646406.json` → `receipts.generated_at`). El pack lo reconoce:
`docs/source_pack/BARRANQUILLA_SOURCE_PACK_MANIFEST.json:128` → *"La metodología de la Lonja
declara vigencia hasta 2026-08-31, anterior a esta corrida; ningún consumidor la convierte en
bloqueo"*. Un consumidor lo detecta correctamente: `api/market_sources.py` marca
`vigencia_ok=False` y `VENCIDA` (probado en `tests/test_source_pack_market.py:423-428`).

---

## RESPUESTA 5 — Si NO hay fuente automática suficiente, ¿se declara NO DISPONIBLE o se rellena?

**Respuesta: hay DOS comportamientos, y ambos son reales y verificables.** El camino autorizado
**falla cerrado**; existe además un camino legacy explícito que **sí hardcodea un valor por m²**.

### 5.a · El camino autorizado SÍ declara y NO rellena (fail-closed verificado)

| Punto | Comportamiento | Evidencia |
|---|---|---|
| Sin autorización → no se calcula nada | `get_valuation` devuelve bloqueado | `api/dictamen_data.py:101-103` → `if not valuation_authorized and not allow_legacy_reference: return _bloqueado("valoración no autorizada …")` |
| Sin tasa en el contexto → `MARKET_RATE_INVALID` | bloqueo | `api/dictamen_data.py:142-144` |
| Autorización sin `MarketContext` → bloqueo | bloqueo | `api/dictamen_data.py:180-183` |
| Blocker por fuente de tasa ausente | `"market_rate_source ausente (sin tasa de mercado autorizada)"` | `api/market_context.py:268-269` |
| Blocker por tasa ausente/≤0 | `"market rate value missing/invalid"` | `api/market_context.py:278-281` |
| Sin match de sector → `value_m2 = None` (no inventa sector) | `MATCH_NO_MATCH`, `None` | `api/market_context.py:119-146`, `:145-146`, `:162-163` |
| El ejecutivo **no imprime monto** si no está autorizado | *"no se imprime ningún monto, ni $0"* | `api/dictus_ejecutivo.py:1739-1741` |
| Tabla de mercado ausente → `SOURCE_UNAVAILABLE` sin sustituir | declara motivo | `api/market_sources.py:366-370` → *"la fuente declara SOURCE_UNAVAILABLE y NO se sustituye el valor por ningún otro dato ni por un valor por defecto"* |
| Tabla manipulada → no se usa | `NO_SOPORTADA`, `value_per_m2 = None` | `tests/test_source_pack_market.py:200-211` |

### 5.b · El camino legacy SÍ hardcodea un valor por m² (hallazgo explícito)

`api/dictamen_data.py:145-177` (rama `elif allow_legacy_reference:`), **dos veces**:

```python
# api/dictamen_data.py:149-152  (rama Pasto)
estrato_map = {3: 3800000, 4: 5200000, 5: 6500000, 6: 7800000}
val_m2_mercado = estrato_map.get(int(estrato), 5200000)
market_rate_match_type = "GENERIC_ESTRATO_FALLBACK"
market_rate_source = "referencia genérica por estrato (sin metodología local)"

# api/dictamen_data.py:173-177  (rama general, cuando no hay sector)
estrato_map = {3: 3800000, 4: 5200000, 5: 6500000, 6: 7800000}
val_m2_mercado = estrato_map.get(int(estrato), 5200000)
market_rate_source = ("fallback genérico por estrato (no específico de sector)")
market_rate_match_type = "GENERIC_ESTRATO_FALLBACK"
```

- **Sí es un valor/m² hardcodeado en código** (`3.8M`, `5.2M`, `6.5M`, `7.8M`) **con un default
  de `5.200.000`** aplicable a cualquier estrato fuera del mapa.
- **NO es silencioso:** se marca `GENERIC_ESTRATO_FALLBACK` y se le pone un texto de fuente
  honesto. El gate lo rechaza explícitamente: `api/market_context.py:294-297` →
  `if sector.get("match_type") == MATCH_GENERIC_ESTRATO_FALLBACK: return False`.
- **NO puede autorizar** una valoración de alta confianza (por diseño y por test:
  `tests/test_remediacion_03h.py:110-113`).
- **No está activo en el Golden**: la corrida usó el `MarketContext`
  (`DICTUS_RUN_STATE_040-646406.json:1030-1035` → `market_context_authorized: true`).

### 5.c · ¿Se inventa un sector? No. ¿Se edita a mano un valor? Sí.

- **Sector inventado: NO.** `resolve_market_sector` sólo devuelve un sector que exista como clave
  literal en el YAML (`api/market_context.py:150-152`, igualdad exacta o normalizada). Con barrio
  desconocido devuelve `NO_MATCH` y `value_m2 = None`
  (`api/market_context.py:145-146`); probado en `tests/test_remediacion_03h.py:40-44`.
- **Valor/m² hardcodeado en el YAML: SÍ, y documentado como tal.** El `68.000.000`… (en realidad
  `6.800.000`) del Golden es un **literal escrito a mano** cuya justificación está en el comentario
  del propio archivo (`lonja_baq_metodologia.yaml:209-213`), y cuya `fuente` mezcla un dato real
  con un añadido no acreditado: *"…+ Lonja BAQ referencial"* (`:218`).
- **Sobre-afirmación de automaticidad: SÍ, detectada.** El informe técnico imprime
  `[FUENTE: ESTIMACIÓN REFERENCIAL DE MERCADO ARHIAX (AUTOMÁTICA)]`
  (`api/pdf_compiler.py:2867`), pero el valor proviene de una constante YAML escrita a mano. La
  palabra **"AUTOMÁTICA"** describe el *cálculo*, no la *procedencia del dato*, y un lector razonable
  la lee como lo segundo.

---

## ANEXO A — Inventario exhaustivo de menciones «Lonja»

Recuento por línea coincidente (grep `lonja|Lonja|LONJA`, incluidos los archivos ignorados por
git — `api/acquisition.py` y `api/source_licenses_v2.py` no aparecen en `git ls-files api/`).

### A.1 Resumen por área

| Área | Líneas coincidentes | Naturaleza dominante |
|---|---|---|
| `api/**` | **102** | identificador de metodología + comentarios; **1 cadena visible en ejecutivo**, **8 en técnico** |
| `motor_tma_lonja_baq_v1.0/**` | **176** | nombre del paquete + identificadores + documentación del vendor |
| `docs/**` (source_pack, forensics) | **~230** (varios JSON con `lonja_baq_metodologia`) | identificadores de provenance + matrices de auditoría |
| `scripts/**` | **29** | construcción/cobertura del pack |
| `tests/**` | **47** | identificadores y una **clase de test que ya declara que la Lonja NO es fuente** |

### A.2 (a) EJECUTIVO — menciones visibles al lector

| # | Evidencia | Texto | ¿Afirma fuente Lonja? |
|---|---|---|---|
| 1 | `api/dictus_ejecutivo.py:1751-1752` | `Nota("TRAZABILIDAD · Fuentes: Metodología de mercado (Lonja) · " "Catastro · Identidad canónica · Consulta: " ...)` | **SÍ — afirma una fuente** |
| 2 | `api/dictus_secciones.py:521-523` | `metodo_txt = f"Comparación de mercado · {mc.get('market_methodology_id')} v{mc.get('market_methodology_version')}"` → imprime `lonja_baq_metodologia` | Imprime identificador con la palabra `lonja` como "Método principal" |
| 3 | `api/dictus_secciones.py:733` + `api/dictus_ejecutivo.py:1693-1694` | `"tasa_fuente": _dato(mc.get("market_rate_source"))` → `Nota("Tasa y parámetros: " + ...)` | Transcribe la `fuente` del YAML, que contiene `+ Lonja BAQ referencial` |
| 4 | `api/dictus_estado.py:599` | `{"tipo": "VALORACION", "fuente": "metodología de mercado (Lonja)"}` | **SÍ — afirma fuente**; llega al run state en `:1390` |

Texto exacto en el PDF (extraído con `pypdf`, ver Anexo B): líneas 451, 454 y 455 del texto de la
página 6.

### A.3 (b) TÉCNICO — menciones visibles

| # | Evidencia | Texto | ¿Afirma fuente Lonja? |
|---|---|---|---|
| 5 | `api/pdf_compiler.py:2848-2849` | `"aun no hay una metodologia local verificada (Lonja/IGAC): la estimacion se calcula con " "una <b>referencia generica por estrato</b> y NO con los parametros de la Lonja de " "Barranquilla (aplicarlos seria desinformacion)"` | **NO** — niega la Lonja para Pasto (pero nombra "la Lonja de Barranquilla" como si fuera su metodología) |
| 6 | `api/pdf_compiler.py:2862` | `"(practica de la Lonja de Barranquilla)"` | **SÍ, sugiere** que la práctica M1/M3 proviene de la Lonja |
| 7 | `api/pdf_compiler.py:2855` | `"[FUENTE: ESTIMACIÓN REFERENCIAL GENERICA POR ESTRATO - SIN METODOLOGIA LOCAL PASTO]"` | No (rama Pasto) |
| 8 | `api/pdf_compiler.py:2867` | `"[FUENTE: ESTIMACIÓN REFERENCIAL DE MERCADO ARHIAX (AUTOMÁTICA)]"` | **No nombra la Lonja, pero sobre-afirma "AUTOMÁTICA"** |
| 9 | `api/dictamen_data.py:485` | `"Práctica de la Lonja de Barranquilla: PH = 100% M1; M3 solo excepcional."` | **SÍ, sugiere** origen Lonja; se imprime vía `get_valoracion_alert` |
| 10 | `api/pdf_compiler.py:1023`, `:1113` | comentarios: `# Val data con metodologia Lonja BAQ …`, `# Metodo principal de valoracion (practica de la Lonja de Barranquilla, no de la Res. IGAC 941)` | No visible; sostiene la idea internamente |

Texto exacto en el técnico (17 páginas, extraído con `pypdf`): líneas 444 y 476 →
`"demostrable (practica de la Lonja de Barranquilla). El Método de Costo de Reposición M2 se calibra según parámetros de mercado"`
y `"Práctica de la Lonja de Barranquilla: PH = 100% M1; M3 solo excepcional."`

### A.4 (c) MODELO / MANIFEST / RUN STATE

| Evidencia | Campo | Valor |
|---|---|---|
| `DICTUS_RUN_STATE_040-646406.json:1102-1106` | `market_methodology_id` / `_version` / `_sha256` / `_file` / `methodology_entity` | `lonja_baq_metodologia` / `0.1-codiseno` / `4ccd5832…` / `lonja_baq_metodologia.yaml` / `Lonja de Propiedad Raíz de Barranquilla` |
| `DICTUS_RUN_STATE_040-646406.json:1109` | `sector_metodologico.source` | `"…+ Lonja BAQ referencial"` |
| `DICTUS_RUN_STATE_040-646406.json:1113-1121` | `provenance.*` | `methodology_id`, `methodology_sha256`, `methodology_entity`, `artifact_autor` |
| `DICTUS_RUN_STATE_040-646406.json:1123-1127,1134-1140` | espejo en `market_context.*` | mismos identificadores |
| `DICTUS_RUN_STATE_040-646406.json:1390` | `evidence_manifest_input.articulos[].fuente` (`tipo: VALORACION`) | `"metodología de mercado (Lonja)"` |
| `DICTUS_RUN_STATE_040-646406.json:1436-1438` | `receipts.mercado.metodologia_id/_version/_sha256` | `lonja_baq_metodologia` / `0.1-codiseno` / `4ccd5832…` |
| `DICTUS_MANIFEST_040-646406.json:1455-1493` | bloque `market_context` espejo | idénticos |
| `DICTUS_MANIFEST_040-646406.json:1341-1343` | `methodology_versions` | `lonja_baq_metodologia` / `0.1-codiseno` / `4ccd5832…` |
| `docs/forensics/040-646406/dictus_2c/DICTUS_MANIFEST_040-646406.json:1589-1594` | `methodology_file`/`_id`/`_entity`/`artifact_autor` | identificadores + `Lonja de Propiedad Raíz de Barranquilla` |

**Ninguno de estos campos es una FUENTE: son identificadores y sellos de un archivo local.**

### A.5 (d) MOTORES

`motor_tma_lonja_baq_v1.0/**` — 176 líneas coincidentes:

| Archivo | N | Qué es |
|---|---|---|
| `lonja_layer/ejecucion_lonja_baq.py` | 32 | pipeline del motor; `:64-68` inyecta `tasa_lonja` y `fuente="Tasa declarada por Junta Técnica Lonja BAQ …"` |
| `run_dictamen.py` | 31 | punto de entrada; imprime `AVALÚO CORPORATIVO LONJA BAQ` |
| `lonja_layer/lonja_baq_metodologia.yaml` | 23 | **el artefacto mismo** |
| `README.md` | 22 | doc del vendor; `:152` declara `Hash YAML Lonja v0.1: e8071f82…` (**no coincide** con el archivo actual) |
| `lonja_layer/road_test.py` | 20 | demo "la Lonja cambia pesos, el motor obedece" |
| `lonja_layer/lonja_adapter.py` | 17 | `class LonjaConfig`, `cargar_declaracion_lonja()` |
| `INSTRUCCIONES_ANTIGRAVITY.md` | 12 | doc |
| `CRITERIOS_ACEPTACION.md` | 8 | doc |
| `tma_engine/piezas/contrato_datos.py` | 2 | `:85, :89` — comentario y tipo del autor de la regla |
| `tma_engine/piezas/pieza_4_motor_consolidacion.py` | 1 | **`:35` — `"…(pendiente validación con metodología corporativa Lonja BAQ)"`** |
| `MANIFEST.sha256` | 4 | hashes de los archivos `lonja_layer/*` |
| `requirements.txt` | 2 | `PyYAML — Carga del YAML de la Lonja` |
| `output_referencia/dictamen_napoli.html` | 1 | `:557` — **"pendiente validación con metodología corporativa Lonja BAQ"** |

Fuera de ese paquete, los ⓜotores de valoración del producto son `api/dictamen_data.py`
(`:69, :117-125, :210, :480, :485`) y `api/pdf_compiler.py` (`:13, :16, :20, :1023, :1113`).

### A.6 (e) TESTS — 47 líneas en 11 archivos

| Archivo | N | Papel |
|---|---|---|
| `tests/test_source_pack_licenses.py` | 28 | **`TestLonjaNoEsFuente` (`:433-500`) — afirma que la Lonja NO es fuente** |
| `tests/test_source_pack_market.py` | 4 | **afirma que la Lonja SÍ es fuente formalizada** (`:110-119`) |
| `tests/test_source_pack_resolution_ladder.py` | 4 | usa `LONJA_MARKET_BAQ` como escalón de fallback (`:154, :158, :505, :641`) |
| `tests/test_source_pack_pipeline.py` | 2 | `:413` exige `LONJA_MARKET_BAQ` en el registro; `:433` su autoridad |
| `tests/test_expansion_pasto.py` | 3 | `:94-99` exige que el texto Pasto **no** mencione "Lonja de Barranquilla" |
| `tests/test_remediacion_03i1.py` | 1 | `:238` exige `id == "lonja_baq_metodologia"` |
| `tests/test_remediacion_03h.py` | 1 | `:29` docstring "leer el YAML Lonja" |
| `tests/test_arhiax_re.py` | 1 | `:89` nombre del test + uso del YAML |
| `tests/test_dictus_20d_r1_p6.py` | 1 | `:47` texto de fixture |
| `tests/test_dictus_20d_decision.py` | 1 | `:100` `"market_methodology_id": "lonja_prueba"` (fixture) |
| `tests/test_dictus_20c_fidelidad.py` | 1 | `:134` `"market_methodology_id": "lonja_prueba"` (fixture) |

### A.7 Veredicto A — ¿FUENTE real o sólo nombre de identificador?

| Aparición | ¿Es una fuente de datos? | Por qué |
|---|---|---|
| `market_methodology_id = "lonja_baq_metodologia"` | **NO** — identificador | `api/market_context.py:81` es una **constante de cadena**; `:84-103` devuelve `file` + `sha256` **del path local** |
| `market_methodology_file = "lonja_baq_metodologia.yaml"` | **NO** — nombre de archivo | `api/market_context.py:100` → `"file": p.name` |
| `LONJA_MARKET_BAQ` (`SOURCE_ID`) | **NO** — etiqueta declarada a mano | `api/market_sources.py:91`; sin URL (`api/source_licenses.py:240`); `base_url` = `local:` (`barranquilla_sources_v1.json:826`) |
| `methodology_entity` / `artifact_autor` | **NO** — texto declarado en el YAML | `lonja_baq_metodologia.yaml:19, :62` |
| Nombre del paquete `motor_tma_lonja_baq_v1.0/` | **NO** — ruta de directorio | `api/market_context.py:50-51` |
| `LONJA_METODOLOGIA_LOCAL` (evidencia de licencia) | **NO** — artefacto local | `api/source_licenses.py:239-247`: `url: None`, `http_status: None`, `resultado: DECLARED` |
| **El producto ya lo decidió**: `api/source_licenses_v2.py:1098-1121` | **NO** | `PARTNERS_INSTITUCIONALES["LONJA_BAQ"]` → `es_fuente_de_datos: False`, `aporta_datos_a_dictus: False`, `en_source_registry: False`, `product_role: PRODUCT_ROLE_NOT_A_SOURCE` |

---

## ANEXO B — Texto REAL del ejecutivo sobre mercado

`docs/forensics/040-646406/dictus_2b/DICTUS_EJECUTIVO_040-646406.pdf` — **6 páginas**
(confirmado: `PdfReader(...).pages` → 6). Texto extraído con `pypdf` 6.10.2. Se transcriben
**todas** las líneas de las 6 páginas que mencionan `mercado|valor|Lonja|metodología` (con su
número de línea en el texto extraído y la página de origen).

**Página 1** (portada)
```
L20: 58.75 m²
L25: VALOR ESTIMADO
L26: $ 399.500.000
L27: identidad · títulos · contrapartes · territorio · entorno · valoración
L37: VALOR
```

**Página 2**
```
L44: El expediente del mismo inmueble produjo valores distintos entre versiones. No es un riesgo del inmueble: es calidad de la información.
L101: Forma de adquisición: Compraventa  (Anot. 006 · 22-01-2024 · ESCRITURA 2875 DEL 11-10-2023 NOTARIA SEXTA DE BARRANQUILLAVALOR ACTO:)
```

**Página 3**
```
L210: El expediente reúne identidad, títulos, contrapartes y valor; las condiciones anteriores son del comprador y del vendedor.
```

**Página 4**
```
L235: valor vigente en esta corrida y su fuente
   (contexto: es el subtítulo de la sección "DECISIÓN TERRITORIAL Y URBANÍSTICA";
    el contenido que sigue —L236-254— es norma urbanística: destino catastral, uso POT,
    tratamiento, altura/edificabilidad, clase de suelo. NO aporta tasa de mercado.)
```

**Páginas 5 y 6 — el bloque de mercado y valor (lo relevante)**

```
L398: IDENTIDAD, MERCADO Y VALOR            ← Página 6, cabecera
L402: IDENTIDAD, MERCADO Y VALOR
L424: 58.75 m²
L441: valoración autorizada en esta corrida
L442: VALOR ESTIMADO
L443: Valor estimado (valor central)
L444: $ 399.500.000
L445: Rango $ 373.532.500 – $ 435.455.000 · Valor/m² $ 6.800.000 / m² · Área 58.75 m²
L446: Vigencia: 2026-09-28 · vigencia de la metodología aplicada · DECISIÓN DICTUS: INFORMACIÓN VERIFICADA
L447: Sector de mercado
L448: Miramar
L449: Método principal
L450: Comparación de mercado
L451: · lonja_baq_metodologia
L452: v0.1-codiseno
L453: Metodología: norma + concepto técnico + validación profesional · detalle completo en el informe técnico.
L454: Tasa y parámetros: Precio de venta verificado en la constructora del proyecto (unidades ~58 m2 terminadas, 2026) + Lonja BAQ referencial
L455: TRAZABILIDAD · Fuentes: Metodología de mercado (Lonja) · Catastro · Identidad canónica · Consulta: 2026-09-28
```

### B.1 Clasificación: ¿qué líneas AFIRMAN o SUGIEREN una fuente Lonja?

| Línea | Texto | Veredicto |
|---|---|---|
| **L455** | `TRAZABILIDAD · Fuentes: Metodología de mercado (Lonja) · Catastro · Identidad canónica · Consulta: 2026-09-28` | **AFIRMA** — lista "Metodología de mercado (Lonja)" como una **Fuente** más, al mismo nivel que Catastro. Origen: `api/dictus_ejecutivo.py:1751-1752` |
| **L454** | `Tasa y parámetros: Precio de venta verificado en la constructora del proyecto (unidades ~58 m2 terminadas, 2026) + Lonja BAQ referencial` | **AFIRMA (por agregación)** — la tasa se atribuye a dos orígenes; el segundo ("Lonja BAQ referencial") no tiene evidencia, no tiene URL y no tiene fecha. Origen: `api/dictus_secciones.py:733` + `api/dictus_ejecutivo.py:1694`, valor literal del YAML `:218` |
| **L451-452** | `· lonja_baq_metodologia` / `v0.1-codiseno` | **SUGIERE** — imprime el identificador `lonja_…` como "Método principal", con un lector no técnico leyendo "Lonja" como origen. Origen: `api/dictus_secciones.py:521-523`, render en `api/dictus_ejecutivo.py:1683-1687` |
| **L453** | `Metodología: norma + concepto técnico + validación profesional · detalle completo en el informe técnico.` | **SUGIERE (indirecto)** — "validación profesional" no está acreditada por ningún artefacto del expediente; el motor de origen declara la validación **pendiente** (`pieza_4_motor_consolidacion.py:35`). Constante: `api/dictus_ejecutivo.py:50` |
| L446 | `Vigencia: 2026-09-28 · vigencia de la metodología aplicada` | **Ambiguo/incorrecto** — se lee como si la metodología fuera vigente; su `vigencia_hasta` (`2026-08-31`) estaba vencida 28 días antes |
| L445 | `Valor/m² $ 6.800.000 / m²` | **No afirma fuente** — pero presenta como dato duro una constante escrita a mano sin `sample_size` ni comparables |
| L447-450 | `Sector de mercado` / `Miramar` / `Método principal` / `Comparación de mercado` | **No afirma** fuente Lonja (el sector sí viene del barrio oficial) |
| L235, L398, L402, L441-444 | etiquetas de sección y montos | **No afirman** fuente Lonja |

**Resumen B:** la afirmación de fuente Lonja en el ejecutivo es **explícita en 2 líneas (L455 y
L454)** y **sugerida en 2 más (L451-452 y L453)**. Nace de **4 puntos de código**:
`api/dictus_ejecutivo.py:1751-1752`, `api/dictus_secciones.py:733`, `api/dictus_secciones.py:521-523`
y `api/dictus_ejecutivo.py:50`.

---

## ANEXO C — Sustituciones de texto propuestas (numeradas)

**Reglas aplicadas (las exigidas por la misión):**
1. **No se inventa ninguna fuente.** Donde el dato es un parámetro declarado, se dice
   *"declarado por la corrida"*. Donde no hay fuente automática suficiente, se declara la
   valoración como **NO DISPONIBLE** / sin fuente externa automática.
2. **NO se propone ningún cambio de fórmula, de compuerta (`gate`), de hash ni de gramática.**
   No se cambia ningún identificador que viaje al hash maestro
   (`SOURCE_ID`, `METHODOLOGY_ID`, `market_methodology_id`, `metodología_id`, nombres de archivo,
   rutas). Sólo se toca **texto legible** y **atribución de procedencia**.
3. **Cada sustitución indica su efecto sobre el hash**, porque editar cualquier artefacto
   hasheado lo re-sella por definición: eso no es un "cambio de hash", es su consecuencia
   obligatoria, y quien lo aplique debe **re-sellar el pack y subir la versión de metodología**,
   no dejar el hash viejo.

### C.1 Grupo 1 — Texto visible en el EJECUTIVO (máxima prioridad)

| # | Archivo:línea | TEXTO ACTUAL | TEXTO DE REEMPLAZO propuesto | Efecto hash |
|---|---|---|---|---|
| **S1** | `api/dictus_ejecutivo.py:1751-1752` | `Nota("TRAZABILIDAD · Fuentes: Metodología de mercado (Lonja) · " "Catastro · Identidad canónica · Consulta: " ...)` | `Nota("TRAZABILIDAD · Fuentes: Parámetros de mercado declarados por la corrida · " "Catastro · Identidad canónica · Consulta: " ...)` | Ninguno (sólo texto de render); el ejecutivo del Golden se re-genera |
| **S2** | `api/dictus_secciones.py:521-523` | `metodo_txt = (f"Comparación de mercado · {mc.get('market_methodology_id')} " f"v{mc.get('market_methodology_version')}")` | `metodo_txt = ("Comparación de mercado (parámetros declarados por la corrida)")` — conserva `market_methodology_id`/`_version` en los campos de máquina (`:738` y provenance), que **no** se tocan | Ninguno en hashes (el id sigue viajando en su campo) |
| **S3** | `api/dictus_secciones.py:733` **+** `motor_tma_lonja_baq_v1.0/motor_tma_lonja_baq_v1.0/lonja_layer/lonja_baq_metodologia.yaml:218` | `"tasa_fuente": _dato(mc.get("market_rate_source"))` ← alimentado por `fuente: "Precio de venta verificado en la constructora del proyecto (unidades ~58 m2 terminadas, 2026) + Lonja BAQ referencial"` | En el YAML: `fuente: "Precio de venta verificado en la constructora del proyecto (unidades ~58 m2 terminadas, 2026), declarado por el analista de la corrida; sin fuente externa automática verificada"` | **SÍ cambia `market_methodology_sha256`** → obligatorio: regenerar `docs/source_pack/lonja_market_baq_v1.json` (`python api/market_sources.py --regenerar`) y actualizar `MANIFEST.sha256` del paquete |
| **S4** | `api/dictus_estado.py:599` | `{"tipo": "VALORACION", "fuente": "metodología de mercado (Lonja)"}` | `{"tipo": "VALORACION", "fuente": "parámetros de mercado declarados por la corrida"}` | Re-sella el manifest de la **próxima** corrida (campo descriptivo; afecta al run state en `:1390`) |

### C.2 Grupo 2 — Texto visible en el TÉCNICO

| # | Archivo:línea | TEXTO ACTUAL | TEXTO DE REEMPLAZO propuesto | Efecto hash |
|---|---|---|---|---|
| **S5** | `api/pdf_compiler.py:2848-2850` | `"aun no hay una metodologia local verificada (Lonja/IGAC): la estimacion se calcula con " "una <b>referencia generica por estrato</b> y NO con los parametros de la Lonja de " "Barranquilla (aplicarlos seria desinformacion). "` | `"aun no hay una metodologia local verificada (metodología local/IGAC): la estimacion se calcula con " "una <b>referencia generica por estrato</b> y NO con los parametros de la metodología local de " "Barranquilla (aplicarlos seria desinformacion). "` | Ninguno |
| **S6** | `api/pdf_compiler.py:2862` | `"renta demostrable (practica de la Lonja de Barranquilla). El Metodo de Costo de "` | `"renta demostrable (practica declarada por la metodología local de la corrida). El Metodo de Costo de "` | Ninguno |
| **S7** | `api/pdf_compiler.py:2867` | `"<b>[FUENTE: ESTIMACIÓN REFERENCIAL DE MERCADO ARHIAX (AUTOMÁTICA)]</b>"` | `"<b>[FUENTE: PARÁMETROS DECLARADOS POR LA CORRIDA — ARTEFACTO DE METODOLOGÍA LOCAL; SIN FUENTE EXTERNA AUTOMÁTICA]</b>"` | Ninguno |
| **S8** | `api/dictamen_data.py:485` | `metodo_ref = "Práctica de la Lonja de Barranquilla: PH = 100% M1; M3 solo excepcional."` | `metodo_ref = ("Práctica declarada por la metodología local de la corrida: PH = 100% M1; " "M3 solo excepcional.")` | Ninguno |
| **S9** | `api/dictamen_data.py:480` (comentario) | `# por estrato (nunca la Lonja de Barranquilla).` | `# por estrato (nunca la metodología de Barranquilla).` | Ninguno |

### C.3 Grupo 3 — Procedencia / registro (afirmación institucional)

| # | Archivo:línea | TEXTO ACTUAL | TEXTO DE REEMPLAZO propuesto | Efecto hash |
|---|---|---|---|---|
| **S10** | `api/market_sources.py:92-93` | `SOURCE_NAME = "Metodología de valoración — Lonja de Propiedad Raíz de Barranquilla"` / `INSTITUTION = "Lonja de Propiedad Raíz de Barranquilla — Junta Técnica de Avalúos"` | `SOURCE_NAME = "Parámetros de mercado declarados por la corrida — artefacto de metodología local"` / `INSTITUTION = "Artefacto local del producto (sin institución proveedora verificada)"` — **`SOURCE_ID` NO se toca** | **SÍ** → regenerar la tabla y `docs/source_pack/BARRANQUILLA_SOURCE_PACK_MANIFEST.json`; el `hash` de fuente en `:414` del manifest cambia |
| **S11** | `motor_tma_lonja_baq_v1.0/.../lonja_baq_metodologia.yaml:19` | `entidad: "Lonja de Propiedad Raíz de Barranquilla"` | `entidad: "Artefacto de metodología local — sin institución proveedora verificada"` | **SÍ** (mismo re-sellado que **S3**) |
| **S12** | `motor_tma_lonja_baq_v1.0/.../lonja_baq_metodologia.yaml:62` | `autor: "Junta Técnica de Avalúos Corporativos — Lonja BAQ"` | `autor: "Artefacto de metodología local — autor no verificado"` | **SÍ** (mismo re-sellado que **S3**) |
| **S13** | `api/source_licenses.py:121` | `ATRIBUCION_LONJA = ("Metodología de la Junta Técnica de Avalúos — Lonja de Propiedad Raíz de " "…")` | `ATRIBUCION_LONJA = ("Artefacto local de metodología de mercado del producto " "(sin institución proveedora verificada)")` | Ninguno (texto de atribución) |
| **S14** | `api/source_licenses.py:633` | `license_name=("Metodología contractual de la Lonja de Propiedad Raíz de " …)` | `license_name=("Artefacto local de metodología de mercado — licencia DECLARADA, contrato no verificado" …)` | Ninguno (bloque de licencia) |
| **S15** | `api/source_resolution.py:370` | `"description": ("Valor/mercado del suelo por metodología contractual (Lonja). " …)` | `"description": ("Valor/mercado del suelo por parámetros declarados por la corrida " "(metodología local). " …)` | Ninguno |

### C.4 Grupo 4 — Código interno / documentación (no visible al cliente)

| # | Archivo:línea | TEXTO ACTUAL | TEXTO DE REEMPLAZO propuesto | Efecto hash |
|---|---|---|---|---|
| **S16** | `api/pdf_compiler.py:1023` | `# Val data con metodologia Lonja BAQ (estrato e integracion YAML)` | `# Val data con parámetros de la metodología local de la corrida (estrato e integracion YAML)` | Ninguno |
| **S17** | `api/pdf_compiler.py:1113-1114` | `# Metodo principal de valoracion (practica de la Lonja de Barranquilla, no` / `# de la Res. IGAC 941)` | `# Metodo principal de valoracion (practica declarada por la metodología local de la` / `# corrida, no de la Res. IGAC 941)` | Ninguno |
| **S18** | `api/market_context.py:62, :79, :108` | `"""Metadata de metodología (versión + vigencia) desde el YAML Lonja."""` / `# … del YAML de la Lonja) y se sella con el` / `"""MarketSectorResolution: resuelve el sector metodológico de la Lonja por barrio.` | `… desde el artefacto de metodología local.` / `… del artefacto de metodología local) y se sella con el` / `resuelve el sector metodológico local declarado por la corrida, por barrio.` | Ninguno |
| **S19** | `api/dictamen_data.py:69-70` | `Regla de negocio (practica de la LONJA de Barranquilla, no de la Resolucion` / `IGAC 941/2026)` | `Regla de negocio (practica declarada por la metodología local de la corrida, no de la` / `Resolucion IGAC 941/2026)` | Ninguno |
| **S20** | `api/dictus_historia.py:67` | `"servicio", "arcgis", "lonja", "metodolog", "pendiente", "sin registrar",` | **NO cambiar** — es una aguja de filtrado de texto histórico; quitarla degradaría la detección. Se documenta como identificador de herramienta, no como fuente | Ninguno |

### C.5 Lo que NO se propone cambiar (y por qué)

| Elemento | Motivo |
|---|---|
| `SOURCE_ID = "LONJA_MARKET_BAQ"` (`api/market_sources.py:91`) | Identificador **sellado en hash** y exigido por `tests/test_source_pack_market.py:110`. Renombrarlo cambia el hash maestro. Debe declararse como **nombre histórico interno**, no como fuente |
| `METHODOLOGY_ID = "lonja_baq_metodologia"` (`api/market_context.py:81`) | Viaja a `run_state`, `manifest` y `receipts` (`:1102, :1436`). Igual razonamiento |
| Nombre del directorio `motor_tma_lonja_baq_v1.0/` y de `lonja_baq_metodologia.yaml` | `_YAML_PATH` (`api/market_context.py:48-52`), `api/pdf_compiler.py:13-20`, `api/index.py:39-46` y `api/dictamen_data.py:117-119` dependen de la ruta literal. Renombrar rompe la resolución → prohibido por "no cambiar la gramática" |
| `api/source_licenses.py:629-649` (bloque `if sid == FUENTE_LONJA:`) | Lógica, no texto: cambiar la condición altera el comportamiento del catálogo |
| `api/acquisition.py:158, :195` (`LONJA_MARKET_BAQ` → `CORE_MARKET` / `AUTHORIZED_FALLBACK`) | Clasificación funcional de adquisición; tocarla cambia la precedencia de fuentes, que es materia de compuerta |
| `api/source_licenses_v2.py:1098-1154` | **Ya es correcto**: declara que la Lonja NO es fuente. No se toca |

**Total de sustituciones propuestas: 20** (S1–S20). De ellas, **3 requieren re-sellar hashes**
(S3+S11+S12 se aplican juntas sobre el mismo YAML; S10 sobre el pack) y **17 son sólo texto.**

---

## ANEXO D — Riesgos: pruebas que fallarían si se elimina la mención a Lonja

**Ninguna de estas pruebas se ha modificado.** Se listan como riesgo, con su aserción concreta.

### D.1 FALLARÍAN con seguridad (afirman la Lonja como fuente formalizada)

| # | Prueba (`tests/...::test_...`) | Aserción concreta | Ruta:línea |
|---|---|---|---|
| 1 | `tests/test_source_pack_market.py::TestFuenteFormalizada::test_identidad_de_la_fuente` | `assertEqual(ms.SOURCE_ID, "LONJA_MARKET_BAQ")` · `assertEqual(ms.AUTHORITY_CLASS, "AUTHORITATIVE_CONTRACTUAL")` · `assertEqual(ms.PRODUCT_ROLE, "CORE_MARKET")` | `tests/test_source_pack_market.py:110-113` |
| 2 | `tests/test_source_pack_market.py::TestFuenteFormalizada::test_autoridad_contractual_no_es_oficial_y_es_normativa` | `assertIn(ms.AUTHORITY_CLASS, ds.CLASES_NORMATIVAS)` | `tests/test_source_pack_market.py:117` |
| 3 | `tests/test_source_pack_market.py::TestFuenteFormalizada::test_la_fuente_esta_en_el_registro_del_producto` | `assertIn(ms.SOURCE_ID, fuentes)` · `assertEqual(entrada["authority_class"], ds.AUTORITATIVA_CONTRACTUAL)` · `assertTrue(entrada["enabled"])` | `tests/test_source_pack_market.py:123-126` |
| 4 | `tests/test_source_pack_market.py::TestConsultarMercado::test_devuelve_source_result_con_procedencia_completa` | `assertEqual(r["source_id"], ms.SOURCE_ID)` · `assertEqual(prov["authority_class"], ds.AUTORITATIVA_CONTRACTUAL)` · `assertEqual(prov["product_role"], "CORE_MARKET")` | `tests/test_source_pack_market.py:329, 336-337` |
| 5 | `tests/test_source_pack_pipeline.py::…::test_registro_declara_las_fuentes_minimas_del_pack` | `assertTrue(minimas <= fuentes)` con `minimas ⊇ {"LONJA_MARKET_BAQ", …}` | `tests/test_source_pack_pipeline.py:413, :416` |
| 6 | `tests/test_source_pack_pipeline.py::…::test_el_equipamiento_oficial_no_es_contextual` | `assertEqual(fuentes["LONJA_MARKET_BAQ"]["authority_class"], ds.AUTORITATIVA_CONTRACTUAL)` | `tests/test_source_pack_pipeline.py:433-434` |
| 7 | `tests/test_source_pack_resolution_ladder.py::…::test_fallback_por_valor_no_utilizable` | `assertEqual(r["selected_source"], "LONJA_MARKET_BAQ")` | `tests/test_source_pack_resolution_ladder.py:158` (datos en `:154`) |
| 8 | `tests/test_source_pack_resolution_ladder.py::…` (case de mercado no disponible) | `"mercado": {"LONJA_MARKET_BAQ": _estado("LONJA_MARKET_BAQ", ds.FUENTE_NO_DISPONIBLE)}` — la clave debe existir | `tests/test_source_pack_resolution_ladder.py:505` |
| 9 | `tests/test_source_pack_resolution_ladder.py::…::test_un_no_match_en_atributo_que_admite_fallback_si_baja` | `assertEqual(r["value"], "EL PRADO")` con `"LONJA_MARKET_BAQ": _ok(...)` | `tests/test_source_pack_resolution_ladder.py:641, :644` |
| 10 | `tests/test_remediacion_03i1.py::TestMetodologiaMercado::test_identidad_metodologica_real` | `assertEqual(m["id"], "lonja_baq_metodologia")` | `tests/test_remediacion_03i1.py:238` |
| 11 | `tests/test_source_pack_market.py::TestTablaVersionada::test_valores_derivados_del_producto_y_no_inventados` | `assertEqual(fila["source_hash"], mc.market_methodology()["sha256"])` y `assertEqual(ds.hash_canonico(en_disco), ds.hash_canonico(derivada))` | `tests/test_source_pack_market.py:164, :172` |

**Nota sobre la #11:** fallaría **sólo si se aplica S3/S11/S12 (edición del YAML) sin regenerar
`docs/source_pack/lonja_market_baq_v1.json`**. Es el riesgo operativo más fácil de cometer.

### D.2 Contradicción interna ya existente (no es un riesgo futuro: es un hecho de hoy)

| Prueba | Qué afirma | Ruta:línea | Contradice a |
|---|---|---|---|
| `tests/test_source_pack_licenses.py::TestLonjaNoEsFuente::test_la_lonja_no_esta_en_el_catalogo_de_licencias` | `assertFalse(v.es_fuente_de_datos("LONJA_MARKET_BAQ"))` · `assertFalse(v.es_fuente_de_datos("LONJA_BAQ"))` | `tests/test_source_pack_licenses.py:445-446` | Pruebas #1–#11 de D.1 |
| ídem `::test_la_lonja_no_tiene_estado_de_licencia_ni_permisos` | `assertIsNone(v.bloque_licencia(c))` para `("LONJA_BAQ","LONJA_MARKET_BAQ","LONJA")` · `assertFalse(permiso["permitido"])` | `tests/test_source_pack_licenses.py:484-490` | `api/source_licenses.py:629-649` |
| ídem `::test_…auditoria…` | `assertTrue(lonja["ok"])` · `assertFalse(lonja["lonja_como_fuente"])` | `tests/test_source_pack_licenses.py:465-468` | `api/market_sources.py:91-95` |

`docs/source_pack/INSTITUTIONAL_PARTNERS.md:35-55` ya declara esta divergencia de forma explícita
y nombra la acción pendiente: *"retirar `LONJA_MARKET_BAQ` del registro y de la tabla de mercado,
y ajustar en consecuencia `api/market_sources.py` y sus pruebas bloqueantes."*

### D.3 FALLARÍA sólo si se elimina el valor/m² hardcodeado (decisión de producto, no de texto)

| Prueba | Aserción | Ruta:línea |
|---|---|---|
| `tests/test_remediacion_03h.py::TestValuationBlock::test_305_5M_regression_bloqueado` | `assertEqual(v_fallback["market_rate_match_type"], MATCH_GENERIC_ESTRATO_FALLBACK)` · `assertAlmostEqual(v_fallback["consolidado"], 305500000, delta=20000)` | `tests/test_remediacion_03h.py:112-113` |

Esta prueba **depende del `estrato_map` hardcodeado** de `api/dictamen_data.py:149-152`. Si la
política pasara a *"sin fuente automática → NO DISPONIBLE, sin fallback por estrato"*, habría que
revisarla. **No se propone tocarla aquí** (la misión lo prohíbe), pero el titular del producto debe
saber que es el punto de acoplamiento.

### D.4 Mencionan «Lonja» pero NO fallarían con las sustituciones propuestas

| Prueba | Por qué no falla | Ruta:línea |
|---|---|---|
| `tests/test_expansion_pasto.py::…::test_valoracion_alert_pasto_no_menciona_lonja_baq` | `assertNotIn("Lonja de Barranquilla", txt)` — la rama Pasto (`api/dictamen_data.py:482-483`) ya no la menciona; **pasaría igual** | `tests/test_expansion_pasto.py:94-99` |
| `tests/test_arhiax_re.py::…::test_valoracion_metodologia_lonja_baq_yaml` | Sólo asevera `consolidado > 0` y `cap_rate == 0.0485`; no depende del texto de `fuente` | `tests/test_arhiax_re.py:89-98` |
| `tests/test_dictus_20d_decision.py:100`, `tests/test_dictus_20c_fidelidad.py:134` | Usan `"lonja_prueba"` como **fixture de laboratorio**, no como aserción sobre el producto | `:100`, `:134` |
| `tests/test_dictus_20d_r1_p6.py:47` | Cadena de fixture inyectada como blocker de entrada | `tests/test_dictus_20d_r1_p6.py:47` |
| `tests/test_remediacion_03h.py:29` | Docstring | `tests/test_remediacion_03h.py:29` |

### D.5 Recuento

- **11 pruebas fallarían con seguridad** (D.1, #1–#11).
- **3 pruebas ya hoy afirman lo contrario** (D.2) — la contradicción es real y previa.
- **1 prueba acoplada al valor hardcodeado** (D.3) si se decide quitar el fallback.
- **5 pruebas mencionan «Lonja» y no se ven afectadas** (D.4).
- **Total de pruebas que un cambio de esta naturaleza obligaría a tocar o justificar: 12**
  (las 11 de D.1 + la de D.3).

### D.6 Discrepancia documental detectada (evidencia, no opinión)

`docs/source_pack/INSTITUTIONAL_PARTNERS.md:39-40` afirma:
> *"`tests/test_source_pack_market.py` / `tests/test_source_pack_contract.py` lo exigen como fuente formalizada."*

Verificado por grep: `tests/test_source_pack_market.py` **sí** lo exige (4 coincidencias), pero
`tests/test_source_pack_contract.py` **no contiene ninguna coincidencia** de `lonja|LONJA|MARKET`.
Es decir, la afirmación del documento es **inexacta en uno de sus dos términos**.

---

## LONJA: NO ES FUENTE

### La conclusión, en una frase

**`lonja_baq_metodologia` es el nombre de un archivo YAML local del repositorio, no una fuente de
datos: el producto nunca recibe, descarga ni verifica un solo dato procedente de la Lonja.**

### Las diez pruebas, con evidencia

1. **No hay URL.** `api/source_licenses.py:240` → `"url": None`. No hay nada que resolver.
2. **No hay descarga.** `api/source_licenses.py:243-244` → `"http_status": None`, `"bytes": None`.
   Nada se transfirió por red.
3. **No hay red en el camino de mercado.** `api/market_context.py` y `api/market_sources.py`:
   **0 coincidencias** de `requests|urllib|httpx|socket|urlopen|http.client`. Verificado por grep.
4. **El campo que se llama `base_url` no es una URL.** `docs/source_pack/barranquilla_sources_v1.json:826`
   → `"base_url": "local:motor_tma_lonja_baq_v1.0/…/lonja_baq_metodologia.yaml"`. El esquema es
   `local:`.
5. **Lo que se hashea es el archivo, no un origen.** `api/market_context.py:87-89` →
   `sha = hashlib.sha256(p.read_bytes()).hexdigest()` sobre una ruta del propio repo
   (`:48-52`). El sello acredita *"este archivo no cambió"*, no *"este dato vino del tercero X"*.
6. **El archivo es mutable y fue mutado.** Tres huellas distintas del mismo artefacto:
   `MANIFEST.sha256:6` → `b8d8f938…`; disco y Golden → `4ccd5832…`; `README.md:152` → `e8071f82…`.
   Y la mutación está confesada en el propio archivo (`:209-213`): *"Actualizado Q3-2026 … el valor
   anterior ($4.5M/m2, Q2-2026) quedaba ~40% por debajo del mercado observado"*.
7. **El artefacto es un borrador autorado por el proveedor, con huecos reservados a la Lonja.**
   `lonja_baq_metodologia.yaml:11` → *"Versión: 0.1 — borrador para co-diseño con Sinergia"*;
   `:20-21` → `"[A declarar por la Lonja]"`. Un documento cuyos firmantes están *"a declarar"* no
   puede ser la fuente firmada de una tasa.
8. **El motor de origen declara la validación PENDIENTE.**
   `motor_tma_lonja_baq_v1.0/.../tma_engine/piezas/pieza_4_motor_consolidacion.py:35` y
   `.../output_referencia/dictamen_napoli.html:557` → *"Metodología corporativa Sinergia LAI v1.0
   **(pendiente validación con metodología corporativa Lonja BAQ)**"*.
9. **El propio producto ya tomó la decisión, por escrito y con código.**
   `api/source_licenses_v2.py:1098` → `# 7 · LA LONJA **NO ES UNA FUENTE** (fuera del Source Registry)`;
   `:1100-1102` → *"Decisión de producto: la Lonja no aporta datos a DICTUS hoy. No es `source_id`,
   ni `authority_class`, ni proveedor de mercado."*; `:1108-1110` → `es_fuente_de_datos: False`,
   `aporta_datos_a_dictus: False`, `en_source_registry: False`; `:1112` →
   `product_role: PRODUCT_ROLE_NOT_A_SOURCE`. Y `:1139-1153` implementa
   `auditoria_no_lonja()`, cuya función es **demostrar que ningún artefacto la declara fuente**.
   El documento que lo formaliza es `docs/source_pack/INSTITUTIONAL_PARTNERS.md:6-9`:
   > *"Este documento existe para una decisión de producto explícita: **la Lonja no es una fuente
   > de datos**. No aporta datos a DICTUS hoy, no es `source_id`, no es `authority_class`, no es
   > proveedor de mercado…"*

   Y `:23-26`:
   > *"**No hay dataset de la Lonja**, ni contrato de datos, ni columna obligatoria, ni
   > periodicidad, ni vigencia, ni valor por m² suministrado por la Lonja en esta pieza. Si un valor
   > de mercado aparece hoy en el producto, su procedencia es **otra** (el artefacto metodológico
   > propio y las fuentes declaradas en su propia fila)…"*
10. **Lo que el dato realmente es.** La `fuente` de la fila que produjo el Golden declara, en su
    propio texto, un origen que **no es la Lonja**: *"Precio de venta verificado en la constructora
    del proyecto (unidades ~58 m2 terminadas, 2026)"*. El sufijo *"+ Lonja BAQ referencial"*
    (`lonja_baq_metodologia.yaml:218`) es una **atribución añadida sin soporte**: sin URL, sin
    fecha, sin `sample_size`, sin listado de comparables y sin contrato.

### Por qué el identificador de metodología NO es una fuente de datos

Un **identificador de metodología** responde a *"¿con qué reglas se calculó?"*. Una **fuente de
datos** responde a *"¿de dónde salió el número, y puedo ir a comprobarlo?"*. En este producto:

| Pregunta | Identificador | Fuente |
|---|---|---|
| Qué responde | con qué reglas se calculó | de dónde salió el número |
| Qué se puede verificar | que el archivo no cambió (`sha256` local) | que el tercero publicó ese número (URL + fecha + hash remoto) |
| Qué existe aquí | `market_methodology_id`, `market_methodology_version`, `market_methodology_sha256`, `market_methodology_file` (`DICTUS_RUN_STATE_040-646406.json:1102-1105`) | **NADA**: `url: None`, `http_status: None`, `bytes: None` (`api/source_licenses.py:240-244`) |

`market_methodology_sha256 = 4ccd5832…ebd348` **sella un archivo del repositorio**. Si el archivo
hubiera venido de la Lonja, habría además una URL de origen, una fecha de consulta de ese origen, un
hash de la respuesta HTTP y un `sample_size` — y ninguno existe. Confundir ambos planos es lo que
produce la afirmación del ejecutivo *"Fuentes: Metodología de mercado (Lonja)"*
(`api/dictus_ejecutivo.py:1751`), que presenta como **Fuente** —al mismo nivel que Catastro— algo
que es **el nombre de un archivo local en estado de borrador, con la vigencia vencida y con sus
propios firmantes aún "[A declarar por la Lonja]"**.

### Estado final declarado (no silenciado)

| Plano | Qué dice hoy | Coherente con «la Lonja no es fuente» |
|---|---|---|
| `api/source_licenses_v2.py` | la Lonja **no es fuente**; es `institutional_partner` | **SÍ** |
| `docs/source_pack/INSTITUTIONAL_PARTNERS.md` | la Lonja **no es fuente**; no hay dataset | **SÍ** |
| `tests/test_source_pack_licenses.py::TestLonjaNoEsFuente` | la Lonja **no es fuente** | **SÍ** |
| `api/market_sources.py` (`SOURCE_ID="LONJA_MARKET_BAQ"`, `CORE_MARKET`) | la Lonja **es** la fuente de mercado | **NO** — divergencia declarada (`INSTITUTIONAL_PARTNERS.md:50`) |
| `docs/source_pack/lonja_market_baq_v1.json` | tabla de la fuente Lonja | **NO** — divergencia declarada |
| Ejecutivo L455 / técnico L444, L476 | la Lonja **es** una Fuente | **NO** — pendiente de las sustituciones del Anexo C |
| `tests/test_source_pack_market.py:110-119` | la Lonja **debe** ser fuente formalizada | **NO** — bloquea el pack (ver Anexo D) |

**Conclusión:** la tesis "la Lonja no es una fuente de datos" **ya está decidida y escrita por el
propio producto** (`api/source_licenses_v2.py:1098`, `INSTITUTIONAL_PARTNERS.md:6`). Lo que falta
—y es exactamente el objeto de esta auditoría— es que los **artefactos emisores** (ejecutivo,
técnico, run state, manifest, tabla de mercado) dejen de presentarla como fuente, aplicando las 20
sustituciones del Anexo C y revisando las 12 pruebas del Anexo D.

---

## Resumen ejecutivo de la auditoría

| Pregunta | Respuesta |
|---|---|
| **1 · Fuente real de `market_context`** | Un único YAML local del repo: `motor_tma_lonja_baq_v1.0/.../lonja_layer/lonja_baq_metodologia.yaml` (`api/market_context.py:48-58, 106-184`) |
| **2 · Datos externos para mercado** | **NINGUNO.** 0 endpoints; `url: None`, `http_status: None` (`api/source_licenses.py:240-244`); `base_url` = esquema `local:` |
| **3 · Fuente vs cálculo** | FUENTE: 4 valores de suelo + cap rates + factor de costos + pesos + Fitto-Corvini, todos literales en el YAML. CÁLCULO: normalización de sector, sha256, `ready/blockers`, tabla derivada, aritmética M1/M2/M3 |
| **4 · Provenance verificable** | Parcial: **sí** integridad del archivo local (`market_methodology_sha256`); **no** procedencia del origen (sin URL, sin fecha de consulta, sin `sample_size`; `source_date` = `"Q3-2026"`, un trimestre). El YAML además divergió de su propio `MANIFEST.sha256` |
| **5 · NO DISPONIBLE o relleno** | Ambos: el camino autorizado **falla cerrado** (blockers + "no se imprime ningún monto"); existe un camino legacy explícito que **hardcodea** `{3:3.8M, 4:5.2M, 5:6.5M, 6:7.8M}` con default 5.2M (`api/dictamen_data.py:149-152, 173-177`), marcado como `GENERIC_ESTRATO_FALLBACK` y excluido del gate. No se inventa sector |
| **¿Hay fuente automática suficiente?** | **NO** |
| **Menciones «Lonja»** | `api/**` 102 · `motor_tma_lonja_baq_v1.0/**` 176 · `scripts/**` 29 · `tests/**` 47 · `docs/**` ~230 |
| **Sustituciones propuestas** | **20** (S1–S20); 3 requieren re-sellado de hash, 17 son sólo texto |
| **Pruebas a tocar/justificar** | **12** (11 fallarían con seguridad + 1 acoplada al valor hardcodeado); 3 ya hoy afirman lo contrario |

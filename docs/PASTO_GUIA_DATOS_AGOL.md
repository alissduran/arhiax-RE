# Guía: conectar los datos de Pasto (Nariño) a ARHIAx

> **ACTUALIZACIÓN 2026-09-16 — buena parte de esta guía ya no es necesaria.**
>
> Se descubrió que el **geoportal del Municipio de Pasto** publica la base
> catastral y la normativa del POT **en vivo**:
> `https://geoportal.pasto.gov.co/server/rest/services/Planeacion`
> (ojo: la ruta es `/server/rest/services`, no `/arcgis/rest/services`).
>
> Ya está conectado: NUPRE, dirección catastral, matrícula inmobiliaria, área,
> clase de suelo, área de actividad, tratamiento urbanístico, edificabilidad
> (pisos/metros) y **riesgos por predio** (volcánico, ZAVA, flujos de lodo,
> remoción, inundación, subsidencia). Ver `api/pasto_territorio.py`.
>
> También está conectado el **riesgo volcánico del SGC** (Galeras):
> ver `api/riesgo_volcanico.py`.
>
> **Lo único que sigue aplicando de esta guía es la sección de EQUIPAMIENTOS
> (POI)**, porque Overpass es un servicio público que se cae. Para eso usa el
> script `scripts/publicar_equipamientos_agol.py`, que publica los equipamientos
> como capa propia en tu ArcGIS Online. El resto del documento queda como
> referencia del procedimiento genérico.

---

Estado actual: **Pasto ya es una ciudad seleccionable en ARHIAx** (geocodificación
OSM/Nominatim, puntos de interés, análisis registral, jurídico y SAGRILAFT
funcionan). Lo que falta para completarla es la **capa catastral y el POT en vivo**,
que hoy se declaran `PENDIENTE` de forma honesta.

Este documento explica qué datos se necesitan, dónde pedirlos, cómo publicarlos en
ArcGIS Online y qué devolverle al motor para conectarlos (igual que hoy opera con
Medellín y Bogotá).

---

## 1. Qué datos se necesitan

Dos fuentes, publicadas cada una como **feature service** (capa consultable):

### 1.1 Catastro predial de Pasto (obligatorio)
Capa de **predios** (polígonos de terreno) con atributos por predio. Campos que
ARHIAx mapea (el nombre exacto lo ajustamos al publicar):

| Campo conceptual | Ejemplos de nombre en la fuente | Uso en ARHIAx |
|---|---|---|
| Código predial / NUPRE | `numero_predial`, `codigo_predial`, `nupre` | Identifica el predio exacto desde el CTL |
| Dirección catastral | `direccion`, `nomenclatura` | Dirección oficial del predio |
| Destino económico | `destino_economico`, `uso` | Tipología (habitacional, comercial…) |
| Estrato | `estrato` | Valoración y score |
| Área de terreno (m²) | `area_terreno`, `area` | Área catastral |
| Área de construcción (m²) | `area_construccion` | Área construida |
| Condición jurídica (si existe) | `condicion_juridica` | PH / No PH |

### 1.2 POT de Pasto (recomendado)
Capas de ordenamiento territorial para el cruce por punto:

| Campo conceptual | Uso en ARHIAx |
|---|---|
| Clasificación del suelo | Urbano / rural / expansión / protección |
| Tratamiento urbanístico | Altura y norma aplicable |
| Uso del suelo | Norma de uso |
| Estratificación (si el catastro no la trae) | Estrato |

> El POT vigente es **"Pasto Territorio Con-Sentido"**; se consulta en la
> Secretaría de Planeación Municipal de Pasto.

---

## 2. Dónde obtener los datos

| Dato | Fuente | Cómo pedirlo |
|---|---|---|
| Catastro predial | **IGAC – Dirección Territorial Nariño** (Pasto) | Solicitud formal de la base predial urbana en formato Shapefile o File Geodatabase (el IGAC administra el catastro de los 44 municipios de Nariño). Portal: `https://mapas.igac.gov.co` |
| POT (suelo/tratamiento) | **Secretaría de Planeación – Alcaldía de Pasto** | Solicitar las capas del POT "Pasto Territorio Con-Sentido" (clasificación de suelo, tratamientos, usos) en Shapefile/GDB. Portal: `https://www.pasto.gov.co` |
| Estratificación (alternativa) | Alcaldía de Pasto / IGAC | Capa de estratificación urbana |

> Consejo: pide **todo en coordenadas WGS84 o MAGNA-SIRGAS (EPSG:4326 o 4686)** y
> con el **código predial/NUPRE** como atributo. Es el dato que hace posible
> resolver "este CTL = este predio" con exactitud (como ya hace Barranquilla).

---

## 3. Publicar en ArcGIS Online (dos caminos)

### Camino A — ArcGIS Pro (recomendado si ya tienes el GDB/Shapefile)
1. Abre ArcGIS Pro y agrega la capa de predios al mapa.
2. Clic derecho en la capa → **Sharing → Share As Web Layer → Feature Layer**.
3. Nombre claro (p. ej. `Catastro_Pasto_Predios`), completa *summary* y *tags*.
4. En **Share with**: elige tu organización (o *Everyone* si va a ser pública).
5. **Publish**. Al terminar, copia la URL del servicio (`FeatureServer`).

### Camino B — Solo navegador (ArcGIS Online)
1. En tu organización: **Content → New item → Your device**.
2. Sube el **shapefile comprimido en .zip** (o el File Geodatabase en .zip).
3. En *Publish this file as a hosted layer* → **Publish**.
4. Copia la URL del **Feature Layer (hosted)**, que termina en `/FeatureServer`.

Repite el proceso para las capas del **POT**.

---

## 4. Compartir de forma segura

Los datos catastrales son sensibles: **no los dejes públicos a menos que sea
política de la entidad**. ARHIAx corre serverless en Vercel, así que la forma
correcta de autenticar es:

1. En ArcGIS Online: **Content → API keys → New API key**, con alcance solo a la
   capa del servicio.
2. Copia la API key.
3. Pégala **tú** en Vercel como variable de entorno `ARHIAX_ESRI_API_KEY`
   (Project → Settings → Environment Variables). **Nunca la pegues en el chat ni
   en el repositorio.**

Con eso, ARHIAx consulta el servicio pasando `token=` en cada query, sin exponer
credenciales.

---

## 5. Qué devolverle al motor (checklist final)

Para conectar el catastro/POT de Pasto solo necesito esto de vuelta:

- [ ] **URL del feature service de catastro** (termina en `/FeatureServer`).
- [ ] **Índice o nombre de la capa de predios** (p. ej. `0` o "predios").
- [ ] **URL del feature service de POT** + capa de clasificación de suelo/tratamiento.
- [ ] Si el servicio es **privado**: confirmación de que dejaste la API key en
      Vercel como `ARHIAX_ESRI_API_KEY` (yo no necesito verla).

---

## 6. Qué hará ARHIAx con eso (resultado)

Con la URL publicada, el motor:

1. **Resuelve el predio por NUPRE/código** cuando el CTL lo trae (dirección oficial,
   coordenadas, destino, estrato, área — como Barranquilla).
2. **Resuelve por coordenadas** (point-in-polygon) cuando no hay código.
3. **Cruza el POT** (suelo/tratamiento) en la sección 6.2.
4. **Deja de decir "PENDIENTE"** en catastro/POT/riesgos para Pasto y pasa a
   `CONSULTADA EN VIVO`, con fuente y fecha.

Mientras tanto, el dictamen de Pasto sigue siendo **correcto y honesto**: geocodifica
en Pasto, evalúa POI/registral/jurídico/SAGRILAFT, y declara el catastro/POT como
pendiente en lugar de inventar datos.

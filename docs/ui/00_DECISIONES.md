# Capa de interfaz ARHIAX RE — Decisiones (00)

Estado: **diseño en curso** (03I.1 cerrada; SLICE-002 **no** iniciada).
Insumos: `stitch_arhiax_re_portal_redesign (1)/` (`DESIGN.md`, `code.html`,
`screen.png`), `public/index.html` (portal actual, 1 591 líneas) y los contratos
reales de `api/index.py`.

> Las decisiones D1–D8 son las que **recomendé**; quedan registradas aquí para que
> puedas corregirlas. Están elegidas para no romper nada de lo que ya funciona y
> para que la interfaz nunca afirme un dato que el motor no pueda sostener.

## D1 — Stack: HTML/CSS/JS sin build, servido desde `public/`

**Decidido:** reimplementar el diseño con **CSS propio (variables de diseño) y JS
vanilla**, sin `cdn.tailwindcss.com` y sin framework.

Motivos:
1. El repo **ya sirve** `public/index.html` desde Vercel; añadir Next.js implicaría
   un segundo runtime, un segundo deploy y duplicar la autenticación por token.
2. El propio prototipo Stitch carga Tailwind por CDN: en producción eso es una
   dependencia externa que puede caerse, además de una CSP más laxa.
3. La estética pedida (0px de radio, densidad alta, tablas) se logra con ~300 líneas
   de CSS de tokens; un framework solo aportaría peso.

**Consecuencia:** el prototipo vive en `ui/prototipo/` y **no** toca
`public/index.html`. La promoción a producción será incremental (por vista), nunca
big-bang, para no dejar a los usuarios sin portal.

## D2 — Fuente de datos: solo contratos que existen

**Decidido:** cada dato de la interfaz viaja por un endpoint **existente**:

| Necesidad | Endpoint real |
|---|---|
| Sesión / rol / usuario | `POST /api/login` → `GET /api/me` |
| Listado de casos (cartera) | `GET /api/dictamenes` |
| Crear caso | `POST /api/dictamenes` |
| Editar / borrar | `POST /api/dictamenes/{id}/update` · `DELETE /api/dictamenes/{id}` |
| Resolver dirección → matrícula | `GET /api/resolver-matricula?direccion=` |
| Documentos del caso | `GET|POST /api/dictamenes/{id}/documentos` |
| Generar y descargar dictamen | `POST /api/dictamenes/generar` · `GET /api/dictamenes/{id}/pdf` |
| Progreso de generación | `GET /api/v1/pdf/trabajos/{job_id}` |
| Configuración de la plataforma | `GET /api/config` · `GET /api/v1/status` (admin) |
| Verificación territorial | `GET /api/v1/geo/catastro`, `/api/v1/geo/ciudades` |

**Lo que el prototipo Stitch muestra y el backend todavía NO tiene** se declara
`CONTRATO_FALTANTE` y en el prototipo aparece **etiquetado como `DEMO`** (nunca como
dato real): organizaciones multi-tenant, cuotas de consumo, cobertura de seguro,
firma digital, consola *break-glass*, bitácora de auditoría.

## D3 — Roles: no se inventan roles nuevos

**Decidido:** el backend tiene `admin` y `operador`. La interfaz se diseña para esos
dos roles **ahora**, y deja el *switcher* de personas del prototipo Stitch
(`admin_org` / perito independiente / meta administrador) únicamente como **modo
demo** del prototipo, con el mapeo propuesto documentado en `03_MAPA_CONTRATOS_API.md`
para cuando se decida el modelo multi-tenant.

Motivo: introducir roles que el backend no valida produce una interfaz que *parece*
gobernar permisos y no los gobierna: exactamente el tipo de incoherencia que 03I.1
acaba de cerrar en los datos.

## D4 — Los «estados de verdad» son ciudadanos de primera clase

**Decidido:** la interfaz hereda el vocabulario del motor y lo hace visible:

`VERIFIED_OFFICIAL` · `VERIFIED_REGISTRAL` · `VERIFIED_CATASTRAL` · `UNRESOLVED` ·
`SOURCE_UNAVAILABLE` · `CONFLICT` · `NOT_SCREENED` · `SCREENING_COMPLETE`

Reglas duras de UI:

1. **Vacío explicado:** ningún campo vacío sin causa. Donde no hay dato se muestra
   el estado y su motivo (`SOURCE_UNAVAILABLE · el servicio no respondió`), no un
   guion.
2. **Nunca `0` por desconocido:** si un valor no se calculó, se dice; no se pinta
   `$ 0`.
3. **`NO VERIFICADO` no se disfraza de `OK`:** el semáforo verde solo con
   `VERIFIED_*`; el ámbar es «pendiente/condicionado»; el rojo exige un hecho
   registral o una amenaza alta declarada por la fuente.
4. **Trazabilidad a un clic:** cada dato crítico (folio, NUPRE, estrato, tasa, valor)
   expone su fuente y su hash cuando existe.

## D5 — Sistema visual: el estándar catastral del Stitch, adoptado

**Decidido:** adopto `DESIGN.md` como sistema: 0px de radio en todo, paleta mineral,
`Inter` para narrativa + `IBM Plex Mono` para **identificadores, coordenadas, dinero
y citas legales**, tablas densas (encabezado 28px, fila 32px / 24px densa), elevación
**por bordes** y no por sombras.

Desvío explícito: el prototipo Stitch usa radios `rounded-lg` de Tailwind en tarjetas
y botones, contradiciendo su propio `DESIGN.md` (0px). La interfaz se implementa con
**radio 0** y lo declara aquí.

## D6 — Accesibilidad y operación real

**Decidido:** foco visible con **borde** de 1px (sin *glow*, coherente con el
sistema), navegación completa por teclado en tablas y diálogos, `aria-live` para el
avance de los trabajos de PDF, contraste ≥ 4.5:1 en los cuatro semáforos, y
`prefers-reduced-motion` respetado en la lista de casos.

## D7 — El prototipo no escribe en el producto

**Decidido:** el prototipo (`ui/prototipo/`) consume la API **solo con métodos de
lectura** mientras dure el diseño; las acciones de creación/borrado quedan
deshabilitadas con un aviso («acción deshabilitada en el prototipo»). Así se puede
abrir en producción sin riesgo de crear casos basura.

## D8 — Orden de construcción (por vistas, no por capas)

1. **V1 · Consola de emisión** (los «3 clics»): resolver dirección → verificación en
   vivo → emitir. Es el mayor valor y donde vive el riesgo de afirmar datos.
2. **V2 · Cartera**: tabla densa con estados de verdad y progreso de trabajos.
3. **V3 · Administración**: diagnóstico de fuentes (POI, listas, cola PDF, catastro)
   con los endpoints `admin` que ya existen.
4. **V4 · Gobernanza** (*break-glass*, cuotas, organizaciones): **bloqueada** hasta
   que existan los contratos; se diseña pero no se implementa.

## Riesgos aceptados

| Riesgo | Mitigación |
|---|---|
| El prototipo Stitch muestra datos de ejemplo (matrícula 040-646406, valores, cuotas) | En el prototipo todo dato de ejemplo va marcado `DEMO`; ningún valor de ejemplo se copia a código |
| La promoción a `public/index.html` puede romper el portal actual | Migración por vistas, con la vista vieja disponible hasta que la nueva pase las pruebas de la §Verificación |
| Diseñar gobernanza antes de que exista el modelo multi-tenant | V4 queda como diseño, no como implementación |

## Verificación del diseño

- Contraste y tokens: `ui/prototipo/tokens.css` es la fuente única; ninguna vista usa
  colores literales fuera de las variables.
- Cada vista declara, en `02_ARQUITECTURA_INFORMACION.md`, sus estados **vacío /
  cargando / error / sin permiso / fuente no disponible**.
- Cada dato declara, en `03_MAPA_CONTRATOS_API.md`, su endpoint o su estado
  `CONTRATO_FALTANTE`.

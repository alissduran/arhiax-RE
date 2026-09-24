# DICTUS · Portal de confianza inmobiliaria (experiencia de usuario)

Implementación del rediseño del portal (`stitch_arhiax_re_portal_redesign`) sobre el
sistema **ARHIAX RE Cadastral Standard** y sobre los contratos **que ya existen** en la
API. Es la cara del producto para compradores, vendedores e inmobiliarias; la consola
de emisión vive aparte (`ui/prototipo/`).

## Archivos

| Archivo | Qué es |
|---|---|
| `index.html` | La pantalla completa: mástil institucional, riel de navegación, búsqueda, inmueble activo, cinco tarjetas, expediente, tríada y nueve paneles |
| `portal.css` | Componentes del portal. Importa los tokens del sistema (`../prototipo/tokens.css`): no redefine ningún color ni medida |
| `portal.js` | Lógica de lectura contra la API real. **Sin escrituras** (la única es iniciar sesión) |
| `qa/dom_smoke.mjs` | Arnés que ejecuta `portal.js` en un DOM mínimo y recorre los caminos de pintado |

## Cómo abrirlo

**Ya publicado en la aplicación:** FastAPI sirve la carpeta `public/` en la raíz, así que
la experiencia vive en **`/portal/`** del despliegue (por ejemplo
`https://arhiax-re.vercel.app/portal/`) y la consola operativa enlaza «Portal DICTUS»
desde su barra de sesión. La copia desplegable se genera —no se edita a mano— con:

```powershell
python scripts/publicar_portal.py          # escribe public/portal/
python scripts/publicar_portal.py --check  # falla si está desincronizada
```

**Opción 1 — mismo origen (recomendada, igual que producción).** Copia `ui/portal/` y
`ui/prototipo/tokens.css` a un directorio servido por la app y abre `index.html`. Las
llamadas relativas funcionan sin CORS.

**Opción 2 — servidor local aparte:**

```powershell
python -m http.server 8000 --directory ui
# y abre: http://localhost:8000/portal/?api=https://arhiax-re.vercel.app
```

`http://localhost:8000` ya está en la lista blanca de CORS del backend.

## La experiencia

1. **Mástil institucional**: `DICTUS` (marca) + `ARHIAX RE` (motor) + insignia de
   **marca blanca** para la inmobiliaria aliada + selector de **perspectiva**:
   *Vista inmobiliaria* · *Titulux* · *Portal Lonja* · *Técnico*. La perspectiva es una
   **lente**: cambia qué se destaca y qué panel se abre, nunca qué es verdad.
2. **Búsqueda**: ciudad + dirección/matrícula + NUPRE (opcional). Resuelve contra las
   capas oficiales del municipio (`GET /api/resolver-matricula`).
3. **Inmueble activo**: banner con la dirección normalizada, el predial, el NUPRE, el
   folio y cuántas fuentes respondieron.
4. **Cinco tarjetas ejecutivas**: identidad · estimación económica · legal y títulos ·
   territorio y riesgos · contrapartes. Cada tarjeta muestra el **dato real** cuando el
   contrato existe y, cuando no, el **estado declarado con su motivo**.
5. **Expediente verificado**: sello de la ejecución, documento emitido y trazabilidad,
   con la explicación de qué demuestra el sello y qué no.
6. **Tríada estratégica**: qué habilita el expediente para **comprar/vender**, para el
   **crédito hipotecario** y para el **seguro de títulos**, con el estado real de cada
   pieza.
7. **Nueve paneles**: resumen y auditoría (marco de geometría + ledger de procedencia
   con estados fail-closed) · propiedad y catastro · legal y títulos · valor y mercado ·
   territorio · contrapartes · documentos · cartera · fuentes y diagnóstico.

## Reglas de honestidad que la experiencia demuestra

1. **Nada de valores por defecto** (D4): donde no hay dato se imprime el estado
   (`PENDIENTE`, `FUENTE NO DISPONIBLE`, `CONFLICTO`) **y el motivo**. El patrón vive en
   una sola función (`valorCampo`) para que no se pueda olvidar.
2. **Ningún valor de negocio en el código** (D2): folios, direcciones, montos, estratos
   y NIT llegan del endpoint. La interfaz no tiene un solo caso incrustado — hay una
   prueba que lo prohíbe.
3. **El portal LEE** (D7): la única escritura es autenticarse. No crea casos, no sube
   documentos ni emite dictámenes.
4. **El token vive en memoria**: no se persiste en `localStorage`, `sessionStorage` ni
   `document.cookie`.
5. **Lo que todavía no tiene contrato se declara, no se inventa**: la estimación
   económica (C-02) y el screening de contrapartes (C-03) se muestran como
   **CONTRATO FALTANTE** con su explicación y el enlace al documento emitido, en lugar
   de un monto o un resultado sin fuente.
6. **El ledger de procedencia es fail-closed**: cada fuente consultada aparece con su
   `id`, su resultado real (`OK`, `NO_MATCH`, `AMBIGUOUS`, `SOURCE_UNAVAILABLE`) y su
   detalle. Una consulta sin fuentes lo dice.
7. **La geometría se declara como marco de referencia**, no como levantamiento: se
   grafican las coordenadas informadas por la fuente, con su etiqueta y su estado.

## Verificación

```powershell
# 1 · QA estático: ids, accesibilidad, tokens, disciplina de datos, copia desplegable y ejecución
python -m pytest tests/test_portal_dictus_ui.py -q

# 2 · Contratos reales que el portal consume (offline)
python scripts/qa_portal_contratos.py
#     y con la resolución de dirección contra las capas oficiales:
python scripts/qa_portal_contratos.py --vivo --direccion "CL 79B 42 45"

# 3 · Ejecución del guion en un DOM mínimo (ocho caminos de pintado), fuente y desplegable
node ui/portal/qa/dom_smoke.mjs
node ui/portal/qa/dom_smoke.mjs --dir public/portal
```

Última corrida: **21 pruebas en PASS** · contratos **7/7** con las claves que el portal
lee · **8 caminos de pintado** sin errores en la fuente **y en la copia desplegable**.

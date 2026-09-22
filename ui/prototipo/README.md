# Prototipo de la capa de interfaz (solo lectura)

Prototipo navegable del rediseño del portal, construido sobre el sistema
«ARHIAX RE Cadastral Standard» (`docs/ui/01_DESIGN_SYSTEM.md`) y sobre los contratos
**que ya existen** (`docs/ui/03_MAPA_CONTRATOS_API.md`).

- `index.html` — estructura de las cuatro superficies.
- `tokens.css` — tokens de diseño (fuente única de color y medida). Radio 0px.
- `app.js` — lógica de lectura contra la API real. **Sin escrituras** (D7).

## Cómo abrirlo

**Opción 1 — mismo origen (recomendada, igual que producción):** copia los tres
archivos a un directorio servido por la app y abre `index.html`. En producción el
portal vive en `public/`, servido por FastAPI junto a `/api/*`, así que las llamadas
relativas funcionan sin CORS.

**Opción 2 — servidor local aparte:**

```powershell
python -m http.server 8000 --directory ui/prototipo
# y abre: http://localhost:8000/?api=https://arhiax-re.vercel.app
```

`http://localhost:8000` y `http://localhost:3000` ya están en la lista blanca de CORS
del backend (`ARHIAX_ALLOWED_ORIGINS`).

## Qué hace y qué NO hace

| Hace | No hace |
|---|---|
| Inicia sesión contra `/api/login` y lee `/api/me` + `/api/config` | No guarda el token en `localStorage` (vive en memoria) |
| Resuelve direcciones con `GET /api/resolver-matricula` (lectura real) | No crea casos, no sube documentos, no emite dictámenes (D7) |
| Lista la cartera con `GET /api/dictamenes`, con filtros y descarga de PDF | No edita ni elimina casos |
| Consulta `/api/config`, `/api/v1/status`, `/api/v1/pdf/estado`, `/api/v1/geo/ciudades` | No refresca listas de sanciones ni toca administración |
| Declara `CONTRATO_FALTANTE` donde el backend aún no expone el dato | No inventa cuotas, organizaciones, break-glass ni auditoría |

## Reglas de honestidad que el prototipo demuestra

1. **Nada de valores por defecto.** Donde no hay dato se imprime el estado
   (`PENDIENTE`, `FUENTE NO DISPONIBLE`) y el **motivo**; nunca un guion mudo.
2. **El estrato del endpoint de resolución se marca `NO CONFIABLE`.** El prototipo
   hace visible el defecto C-01 (`return "Pendiente", "", 4`) en lugar de mostrar «4»
   como si fuera un dato del predio.
3. **La ficha de verificación se declara `CONTRATO_FALTANTE (C-02)`** en vez de
   rellenarse con ejemplo.
4. **Gobernanza bloqueada**: la pestaña existe, está deshabilitada y explica por qué.
5. **El sello de ejecución no se rotula «HASH»** a secas (cierre F13 de 03I.1).

## Estados de verdad implementados

`PENDIENTE` (ámbar) · `FUENTE NO DISPONIBLE` (informativo) · `CONFLICTO` /
`NO CONFIABLE` (rojo) · `VERIFICADO *` (verde, **solo** con fuente declarada).

## Limitaciones conocidas del prototipo

- Los datos de ejemplo del prototipo Stitch (matrícula 040-646406, valores, cuotas)
  **no** se copiaron al código: nada en `ui/prototipo/` contiene valores de negocio.
- No incluye el mapa ni los polígonos (requiere el contrato C-02 para llevar la
  geometría y su fuente de coordenada).
- No hay pruebas automatizadas de UI todavía: la validación actual es sintáctica
  (`node --check app.js`) y estructural (balance de etiquetas del HTML).

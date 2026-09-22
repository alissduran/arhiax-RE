# Plan de implementación de la capa de interfaz (04)

Diseño entregado; esto es el plan para llevarlo a producción **sin romper el portal
actual**. Orden por valor y por riesgo (D8), no por capas técnicas.

## Antes de tocar producción: dos correcciones de backend

Sin estas dos, la consola haría **creíble** lo que hoy es un defecto:

| Ref | Corrección | Por qué bloquea la interfaz |
|---|---|---|
| **C-01** | `resolver_matricula_por_direccion()` devuelve el caso Golden hardcodeado y `estrato = 4` por defecto | La consola mostraría una matrícula inventada y un estrato que la fuente no declaró: es la misma familia de defecto que 03I.1 cerró en valoración |
| **C-02** | Exponer/persistir la **ficha de verificación estructurada** (identidad, urbano, mercado, valoración, volcánico, screening y estado por fuente) | Es la única forma de que la consola muestre los estados de verdad sin reconstruirlos del PDF |

C-01 es pequeño (reescribir el endpoint sobre los módulos ya remediados). C-02 es un
contrato nuevo con datos que el motor **ya produce** al generar.

## Slices

### UI-01 · Cimientos (sin tocar `public/`)

- Promover `ui/prototipo/tokens.css` a `ui/tokens.css` como fuente única y añadir la
  capa de utilidades (`.panel`, `.chip`, `.tbl-wrap`, `.state`) que ya usa el prototipo.
- Pruebas: verificación de tokens (ningún color literal fuera de `tokens.css`,
  §Verificación de `00_DECISIONES.md`), contraste ≥ 4.5:1 de los cuatro pares
  semánticos, y `node --check` del JS.
- Criterio de aceptación: el prototipo sigue funcionando idéntico y ninguna vista
  define colores propios.

### UI-02 · V1 Consola (la de mayor valor)

- Implementar el flujo 1→3 con datos reales: ciudades, resolver dirección, documentos,
  crear caso, generar, avance del trabajo, descarga del PDF.
- Sustituir el estado actual de «resolver» por la respuesta de **C-01**.
- Estados completos: vacío, cargando, error, sin permiso, parqueado (identidad no
  resuelta) y éxito.
- Criterio de aceptación: crear un caso real desde la consola, verlo en la cartera y
  descargar su PDF, con cero valores por defecto visibles y el motivo junto a cada
  dato faltante.

### UI-03 · V2 Cartera y V3 Fuentes

- Cartera: tabla densa, filtros, descarga de PDF, refresco de trabajos en cola.
- Fuentes: `/api/v1/status`, `/api/config`, cola de PDF, listas de sanciones
  (frescura + `sha256` por fuente cuando exista ese contrato), diagnóstico POI.
- Criterio de aceptación: la cartera refleja exactamente `GET /api/dictamenes` (mismo
  recuento), y en Fuentes ninguna fuente aparece «OK» sin respuesta del servicio.

### UI-04 · Promoción del portal

- Migrar `public/index.html` **por vistas**, dejando la versión anterior accesible
  hasta que la nueva pase la verificación; luego retirarla.
- Retirar del portal viejo la dependencia de cualquier CDN en producción.
- Criterio de aceptación: paridad funcional 1:1 (login, crear, editar, borrar,
  descargar PDF, diagnóstico POI, refresco de listas, verificación territorial) y
  ninguna acción perdida.

### UI-05 · Gobernanza (bloqueada)

Se implementa **solo** cuando existan los contratos de organizaciones, cuotas,
interruptor de fuentes, break-glass y auditoría (`docs/ui/03_MAPA_CONTRATOS_API.md`).
Requisito de diseño ya fijado: el evento de break-glass exige motivo, tiene ventana
temporal, registra autorizante y es **inmutable y exportable**.

## Riesgos

| Riesgo | Mitigación |
|---|---|
| Promover la consola antes de C-01/C-02 hace creíble un dato falso | C-01 y C-02 como precondición explícita de UI-02 |
| La interfaz nueva oculta funciones del portal actual (diagnóstico POI, verificación territorial, edición manual) | Paridad funcional como criterio de aceptación de UI-04 |
| Roles del prototipo Stitch que el backend no valida | D3: solo `admin`/`operador` hasta que exista el modelo multi-tenant |
| Densidad excesiva en móvil | Breakpoint ≤767px con flujo lineal y acciones en barra inferior |

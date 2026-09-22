# Arquitectura de información (02)

Cinco superficies. Las cuatro primeras se implementan; la quinta (gobernanza) queda
diseñada y **bloqueada** hasta que existan sus contratos.

```
┌ Shell: cabecera de sesión (usuario · rol · entorno · sincronía de fuentes) ─────┐
│ Barra de módulos:  V1 Consola │ V2 Cartera │ V3 Fuentes │ V4 Gobernanza*        │
├─────────────────────────────────────────────────────────────────────────────────┤
│                          área de trabajo (una vista activa)                     │
└─────────────────────────────────────────────────────────────────────────────────┘
* V4 visible solo si existe el contrato; hoy aparece deshabilitada con su motivo.
```

## V1 · Consola de emisión («3 clics»)

Objetivo: de una dirección a un dictamen emitido, sin afirmar jamás un dato no
verificado. Dos columnas (5/7) en escritorio; apiladas en tablet/móvil.

**Progreso superior (3 pasos, siempre visible):** 1 Municipio & Dirección ·
2 Resolución notarial/SNR · 3 Aptitud & emisión.

**Columna izquierda — iniciación**
1. **Jurisdicción**: selector con las cuatro ciudades operativas
   (`GET /api/v1/geo/ciudades`) y, si una no tiene POT integrado, aparece
   **deshabilitada con el motivo** (no se oculta).
2. **Dirección predial**: campo mono + botón `Resolver` →
   `GET /api/resolver-matricula?direccion=`. Devuelve normalización, barrio y folio.
   Chip de estado con la fuente real (`IGAC`/`VUR`/`catastro municipal`).
3. **Alcance**: Estudio de títulos (tradición 20 años) · Peritaje integral
   (títulos + POT + avalúo).
4. **Documentos del caso**: CTL, cédulas/NIT, certificado de existencia, extracto
   hipotecario → `POST /api/dictamenes/{id}/documentos`.
5. **Acción**: `Generar y protocolizar dictamen` → `POST /api/dictamenes/generar`,
   seguido de `GET /api/v1/pdf/trabajos/{job_id}` con barra de avance `aria-live`.
   Si el gate de valoración está cerrado, el botón **se mantiene habilitado** y el
   resultado se declara «emitido sin valoración» con el motivo — nunca se oculta.

**Columna derecha — motor de verificación en vivo**
- **Ficha del predio** (mono): matrícula · número predial · NUPRE · área privada ·
  destinación · estrato, cada uno con su chip de estado.
- **Mapa** con polígono predial y coordenada + **fuente de la coordenada**
  (`OFFICIAL_ADOPTION_ADDRESS_GEOCODE`, `CTL_ADDRESS_GEOCODE`, …). Si la fuente no
  está en la allowlist, el mapa se marca `COORDENADA NO AUTORIZADA` y el contexto de
  mercado queda bloqueado hasta que se resuelva.
- **Tres pilares**: Catastro (folio, anotaciones, gravámenes, medidas cautelares) ·
  POT & usos (tratamiento, altura, cesiones, patrimonio) · Amenazas (inundación,
  remoción, volcánico con su **estado** `NO_COVERAGE`/`NO_INTERSECTION`/`LOW_HAZARD`/
  `SOURCE_UNAVAILABLE`).
- **Mercado**: sector metodológico, tasa `$ /m²`, `match_type`, **metodología
  versionada** (`lonja_baq_metodologia@0.1-codiseno`) y bloqueantes del gate cuando
  el contexto no está listo.
- **Screening de contrapartes**: sujeto, tipo, documento, rol, resultado por fuente
  (ONU/OFAC/UKSL) y evidencia `n/n` con cadena `SEALED`; `NOT_SCREENED` cuando el
  sujeto no se pudo consultar, con motivo.
- **Procedencia**: listado por fuente con estado (`VERIFICADO 100%`, `NO VERIFICADO /
  PENDIENTE`) y **sello de ejecución con su alcance declarado**.

**Estados de la vista:** vacío inicial (formulario limpio, panel derecho con las tres
consultas en «sin ejecutar») · cargando (chip girando + `aria-live`) · error (fuente
no disponible con nombre y hora) · parqueado (identidad no resuelta: no se habilita
la emisión y se explica qué falta) · sin permiso (rol `operador` sin acciones de
administración) · éxito (resumen con folio, sello y enlace al PDF).

## V2 · Cartera

- **Indicadores**: total de casos, en cola de PDF, con PDF emitido, bloqueados por
  hallazgo alto. (Cuotas/organizaciones: **contrato faltante**, se muestran solo en
  modo demo).
- **Tabla densa** (`GET /api/dictamenes`): folio · dirección · ciudad · área ·
  estado del caso · aptitud (`Conforme`/`Pendiente`/`Bloqueado`) · valor referencial ·
  actualizado · acciones (`Abrir`, `PDF`, `Reprocesar`, `Eliminar` solo admin).
- **Filtros**: texto, ciudad, estado, aptitud, rango de fechas.
- **Progreso**: los casos cuyo PDF está en cola se refrescan solos contra
  `GET /api/v1/pdf/trabajos/{job_id}`.
- **Estados:** vacío (sin casos: explica cómo crear el primero) · cargando (esqueleto
  de filas) · error (no se pudo leer la cartera; reintentar) · sin permiso (borrado
  deshabilitado para `operador`).

## V3 · Fuentes y diagnóstico

Consola de operación (rol `admin`) con lo que ya existe en el backend:

- Estado de la plataforma: `GET /api/v1/status` + `GET /api/config` (versiones,
  commit, matriz de versiones).
- Cola de PDF: `GET /api/v1/pdf/estado`, `GET /api/v1/pdf/trabajos`.
- Listas restrictivas: `POST /api/v1/listas/refrescar` + frescura por fuente
  (`CACHED_FRESH`, `STALE_*`, `SOURCE_UNAVAILABLE`) y `sha256` del snapshot.
- POI: `GET /api/v1/diagnostico/poi?lat&lon` con estado por categoría y fuentes
  intentadas/exitosas.
- Catastro en vivo: `GET /api/v1/geo/catastro`.

**Estados:** cada fuente declara su último intento, su resultado y el motivo del
fallo (p. ej. «capa 500 · 404 Layer not found»).

## V4 · Gobernanza (diseñada, BLOQUEADA)

Del prototipo Stitch: organizaciones y asignación de cuotas, interruptor maestro de
nodos catastrales y **consola break-glass** (motivo judicial obligatorio, credencial
provisional de 30 min, registro en bitácora).

Estado: **no implementable hoy** (faltan contratos de organizaciones, cuotas,
auditoría y elevación temporal de privilegios). La vista aparece deshabilitada con el
motivo y el contrato propuesto en `03_MAPA_CONTRATOS_API.md`. Diseño de referencia:
el evento de break-glass debe ser **inmutable y exportable**, con sujeto, objeto,
motivo, inicio/fin y quién lo autorizó.

## Navegación y roles

| Elemento | `operador` | `admin` |
|---|---|---|
| V1 Consola (crear, resolver, emitir) | sí | sí |
| V2 Cartera (ver, abrir, descargar PDF) | sí | sí |
| V2 Eliminar caso | no (deshabilitado con motivo) | sí |
| V3 Fuentes y diagnóstico | no | sí |
| V4 Gobernanza | no | bloqueada por contrato |

La interfaz **no** inventa roles: oculta/atenúa lo que el backend rechazaría y
explica por qué, pero la autoridad sigue siendo el servidor (403 → aviso honesto).

## Responsive

- **≥1280px**: V1 en 5/7 con panel de verificación fijo; V2 tabla completa.
- **768–1279px**: columnas apiladas; cabecera de módulo fija; tabla con scroll.
- **≤767px**: flujo lineal (paso 1 → 3), pilares en acordeón, coordenada y matrícula
  siempre visibles en mono, acciones en barra inferior fija.

## Qué NO hace esta interfaz

No declara cumplimiento normativo, no firma como avaluador ni abogado, no afirma
ausencia de riesgo sin fuente, no sustituye al oficial de cumplimiento y no presenta
datos de demostración como reales.

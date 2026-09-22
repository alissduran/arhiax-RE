# Sistema de diseño ARHIAX RE — Estándar Catastral (01)

Base: `stitch_arhiax_re_portal_redesign (1)/DESIGN.md` («ARHIAX RE Cadastral
Standard»), adoptado con un desvío explícito: **radio 0px** (el prototipo Stitch usa
`rounded-lg` en tarjetas y botones, contradiciendo su propio documento).

Principio rector: **funcionalismo racional** — libro de registro notarial, folio SNR
y docket de avalúo. Densidad alta, jerarquía tipográfica estricta, cero decoración.

## 0. Marca del cliente (Igama)

La interfaz es de **Igama Financiera e Inmobiliaria** y el motor es **ARHIAX RE**. La
cabecera muestra el logo del cliente y el nombre del producto, en ese orden.

- Activo oficial: public/assets/igama-logo.png (copia de trabajo en
  ui/prototipo/assets/igama-logo.png), 192x162 px RGBA,
  sha256 1ef7ded741f84f565be387dc37bef2013feb7a6d69ff2f492fbc6012f6587a6b.
- Reglas: el logo **no** se recolorea, no se le aplican filtros ni sombras, no se
  estira (altura fija, ancho automático) y va sobre superficie blanca o alabastro.
  Alturas usadas: 56px (tarjeta de acceso), 42px (cabecera del portal), 34px
  (consola de la interfaz nueva).
- El rojo del logo es un acento de MARCA, no un color semántico: los cuatro estados
  legales siguen usando exclusivamente los pares definidos en la sección 1.

## 1. Tokens

Fuente única: `ui/prototipo/tokens.css`. Ninguna vista define colores literales.

| Rol | Token | Valor | Uso |
|---|---|---|---|
| Lienzo | `--c-canvas` | `#F7F7F5` | fondo de página |
| Superficie | `--c-surface` | `#FFFFFF` | tarjetas, tablas |
| Superficie sutil | `--c-surface-subtle` | `#F1F1EF` | encabezados de tabla, barras |
| Hueco / track | `--c-inset` | `#EBEBE8` | inputs en reposo, tracks |
| Borde | `--c-border` | `#E3E3DF` | rejilla y contornos |
| Borde fuerte | `--c-border-strong` | `#CFCFC9` | campos, marcos activos |
| Tinta primaria | `--c-ink` | `#2E3438` | títulos, botón primario |
| Tinta secundaria | `--c-ink-2` | `#5C646A` | etiquetas |
| Tinta muda | `--c-ink-3` | `#7E878D` | metadatos, deshabilitado |

### Semántica legal (4 estados, nunca más)

| Estado UI | Fondo | Borde | Texto | Significado exacto |
|---|---|---|---|---|
| **Conforme** | `--ok-bg #EDF3EF` | `#C5D8CC` | `--ok-fg #2F6B45` | solo con `VERIFIED_OFFICIAL` / `VERIFIED_REGISTRAL` / `VERIFIED_CATASTRAL` / `SCREENING_COMPLETE` |
| **Pendiente / Gravamen** | `--warn-bg #F7F1E3` | `#DFD2B4` | `--warn-fg #7A5B10` | `UNRESOLVED`, pendiente de verificación profesional, gravamen vigente |
| **Discrepancia / Embargo** | `--err-bg #F8ECEC` | `#E6BEBE` | `--err-fg #8C2F2F` | `CONFLICT`, embargo/medida cautelar, amenaza alta declarada |
| **Informativo / Registral** | `--info-bg #EEF1F4` | `#CDD5DD` | `--info-fg #3F4A5A` | contexto, `SOURCE_UNAVAILABLE`, notas de alcance |

Regla dura: **`SOURCE_UNAVAILABLE` es informativo + motivo explícito**, nunca
«conforme» ni «no aplica».

## 2. Tipografía

| Rol | Familia | Tamaño / peso | Notas |
|---|---|---|---|
| Marca | Crimson Pro | 20–28 / 600 | solo logotipo y cabecera de portada |
| Titulares | Inter | 28 / 22 (móvil) / 20 / 16 | `letter-spacing` negativo leve |
| Cuerpo | Inter | 14 / 13 / 12 | `font-feature-settings: "cv05","cv11","tnum"` |
| Identificadores | IBM Plex Mono | 13 / 11 / 10 · **techo 13px** | matrícula, NUPRE, cédula/NIT, coordenadas, dinero, citas legales |

Obligatorio mono para: folio de matrícula, número predial, NUPRE, documentos,
coordenadas WGS84/CTM12, cifras monetarias, hashes, versiones de parser y matcher.

## 3. Retícula y densidad

- 12 columnas fluidas, `max-width: 1600px`, canal de 12px, margen 16px.
- Base de espaciado 4px/8px. Padding interior compacto (`4–8px`).
- Breakpoints: **≥1280px** consola multipanel · **768–1279px** paneles apilados con
  cabecera fija · **≤767px** flujo lineal y tablas con desplazamiento horizontal.
- Alturas normalizadas: encabezado de tabla 28px, fila 32px (densa 24px), botón 32px
  (micro 24px), chip 20px.

## 4. Componentes

### Botones
`primario` (fondo tinta, texto blanco) · `secundario` (blanco con borde fuerte) ·
`sutil` (transparente, hover hueco). Altura 32px, padding `0 12px`, radio 0.

### Campos
Fondo blanco, borde `--c-border-strong`, foco = **borde 1px tinta** (sin ring con
glow). Etiqueta en 11px mono mayúsculas encima del campo.

### Tablas catastrales
Encabezado `--c-surface-subtle` con borde inferior fuerte y texto 11px mayúsculas;
filas alternas `#FAFAF9`; **números alineados a la derecha en mono tabular**.

### Chips de estado
20px de alto, padding `0 6px`, borde 1px sólido, sin radio. Pululan en fichas, tablas
y tarjetas de verificación; el color siempre viene de la tabla de 4 estados.

### Panel
Contenedor blanco con borde `--c-border`; cabecera interna con fondo
`--c-surface-subtle` y borde inferior. **Sin sombras**: la jerarquía es tonal.

### Elementos legales especializados
- **Nodo de línea de tiempo registral:** línea vertical de 1px (`#CFCFC9`) con
  marcadores cuadrados de 6×6 (`--c-ink`) — se usa en la cadena de tradición.
- **Etiqueta de coordenada catastral:** chip mono con fondo `--c-inset`.
- **Sello de ejecución:** bloque mono con el sello y su **alcance declarado** (F13:
  nunca rotular «HASH» a secas si es el sello de la ejecución y no del archivo).

## 5. Estados de verdad en la interfaz

| Estado del motor | Chip UI | Color | Texto obligatorio |
|---|---|---|---|
| `VERIFIED_OFFICIAL` | VERIFICADO OFICIAL | Conforme | fuente + fecha/versión |
| `VERIFIED_REGISTRAL` | VERIFICADO CTL | Conforme | anotación o folio |
| `VERIFIED_CATASTRAL` | VERIFICADO CATASTRO | Conforme | capa + servicio |
| `UNRESOLVED` | PENDIENTE | Pendiente | qué falta y quién lo resuelve |
| `SOURCE_UNAVAILABLE` | FUENTE NO DISPONIBLE | Informativo | nombre del servicio y hora del intento |
| `CONFLICT` | CONFLICTO | Discrepancia | los dos valores en pugna |
| `NOT_SCREENED` | NO SCREENING | Pendiente | motivo (sin documento/sujeto) |
| `SCREENING_COMPLETE` | SCREENING COMPLETO | Conforme | cobertura + evidencia `n/n` + cadena |

### Patrón «vacío explicado» (obligatorio)

```
┌ Fuente no disponible ────────────────────────────────┐
│ Destino económico catastral                           │
│ FUENTE NO DISPONIBLE · capa 500 (404 Layer not found) │
│ Verificado el 22-09-2026 17:52 UTC · reintentar       │
└───────────────────────────────────────────────────────┘
```

Nunca: `—`, `N/D` sin motivo, `$ 0`, «no aplica» sin declaración de la fuente.

## 6. Movimiento

Mínimo y funcional: transición de 120ms en hover/estado; `progress_activity` girando
solo mientras hay una consulta real en vuelo; `prefers-reduced-motion: reduce`
desactiva el giro y usa texto de estado.

## 7. Accesibilidad

- Foco visible por borde (no glow), orden de tabulación natural, `Esc` cierra
  diálogos, `Enter` confirma.
- Tablas: `<caption>` con el recuento, `scope="col"` en encabezados, filas
  navegables.
- `aria-live="polite"` en el chip de estado de resolución y en el avance de trabajos.
- Contraste verificado sobre los cuatro pares semánticos (≥ 4.5:1 texto/fondo).

## 8. Prohibiciones explícitas del sistema

1. Radio distinto de 0 en cualquier elemento.
2. Sombras difusas, degradados decorativos, glassmorphism.
3. Verde/rojo saturados; el semáforo solo usa los 4 pares definidos.
4. Poner un valor de ejemplo donde el motor no tiene dato.
5. Mostrar «OK»/«limpio» para un sujeto no screeningado (`NOT_SCREENED`).
6. Etiquetar «HASH» un sello de ejecución.

# ARHIAX RE — Módulo de Evaluación Geoespacial de Amenaza y Riesgo

Portal privado de dictámenes inmobiliarios con evaluación geoespacial (Barranquilla) y generación del **Informe Base LAI** en PDF.

**Deploy:** https://arhiax-re.vercel.app/ · **Repo:** github.com/alissduran/arhiax-RE (privado) · **Última actualización del README:** 2026-09-01

---

## 🏛️ Arquitectura del Sistema

```
[ Predio (Folio / Dirección) ]
          │
          ▼
┌──────────────────────────────────────────────────────────────┐
│  api/index.py (FastAPI serverless en Vercel)                 │
│   - Auth: token HMAC-SHA256 con expiración (Bearer)          │
│   - Subidas validadas (magic bytes PDF/PNG, máx 8 MB)        │
│   - Rate limiting en /api/login                              │
└───────┬──────────────────────────────┬───────────────────────┘
        ▼                              ▼
┌──────────────────┐        ┌─────────────────────────────┐
│ Motor geoespacial │        │ Compilador PDF (ReportLab)  │
│ api/geospatial_  │        │ api/pdf_compiler.py         │
│ engine.py        │        │  - Score actuarial LAI v1.0  │
│ (STRtree + capas │        │  - SARLAFT estructural       │
│  POT api/data/)  │        │  - Hallazgos dinámicos       │
└───────┬──────────┘        └──────────────┬──────────────┘
        ▼                                   ▼
┌──────────────────┐        ┌─────────────────────────────┐
│ Leaflet Overlay  │        │  Informe Base LAI (PDF)     │
│ (mapa interactivo)│        │  con semáforo ARHIAX        │
└──────────────────┘        └─────────────────────────────┘
```

**Stack:** Python 3.14 · FastAPI · ReportLab · Shapely/STRtree · pypdf · Pillow · SQLite (local) · Vercel (serverless).

---

## 🚀 Hitos de Ejecución

### Sprint 0 — Motor geoespacial base (Completado 2026-08-31)
- [x] **Hito 0: Definición y Alineación** — Aprobado por Aliss.
- [x] **Hito 1: Motor Geoespacial** (`api/geospatial_engine.py`) — STRtree + caché en memoria. Latencia < 10 ms en segundo acceso.
- [x] **Hito 2: CLI de Diagnóstico** (`check_predio_riesgo.py`) — `--lat/--lon`, `--direccion`, `--output` JSON con hash.
- [x] **Hito 3: Mapas Interactivos** (`api/map_generator.py`) — Tarjeta diagnóstico POT en Leaflet.
- [x] **Hito 4: Dictamen PDF** (`api/pdf_compiler.py`) — Motor geoespacial dinámico, hallazgo H-GEO.
- [x] **Hito 5: Pruebas de Calidad** — Suite 6/6.
- [x] **Closure Titulux** — Informe Base LAI, SCOPE_DISCLAIMER, gate fiduciario.

### Sprint 1 — Análisis legal y fiduciario (Completado 2026-08-31)
- [x] **S1-1 Conciliación Registral** (`api/legal_analyzer.py`) — NLP del CTL, detección de discrepancias de acreedor.
- [x] **S1-2 Cargas Económicas** (`api/carga_economica.py`) — Amortización francesa, LTV, semáforo. Sección 08B.
- [x] **S1-3 Ruta de Verificación** (`api/ruta_verificacion.py`) — Pasos con actor/plazo/fuente legal. Sección 11.
- [x] **S1-4 Semáforo Fiduciario** — Gate dinámico ROJO/VERDE. Suite **11/11**.

### Sprint 2 — Score actuarial, SARLAFT y multi-folio (Completado 2026-08-31)
- [x] **S2-1 Score Actuarial LAI v1.0** (`api/score_engine.py`) — Ponderación 40/30/20/10, semáforo cromático.
- [x] **S2-2 SARLAFT Estructural** (`api/sarlaft_engine.py`) — Ficha con hashes SHA-256 de integridad, postura honesta (sin falsa verificación de listas).
- [x] **S2-3 Multi-folio / dictamen stateless** (`POST /api/dictamenes/generar`) — Generación sin estado para Vercel.

### Sesión de Estabilización y Producción (Completado 2026-09-01)
Auditoría técnica integral (seguridad + lógica) y correcciones:

- [x] **Crash H-01 corregido** — `IndentationError` en `api/index.py` que impedía arrancar el backend (la API daba 404 en producción).
- [x] **Autenticación real** — Tokens HMAC-SHA256 firmados con expiración (8 h) verificados en **todos** los endpoints; contraseña por variable de entorno; rate limiting en login; CORS con lista blanca.
- [x] **Validación de subidas** — Magic bytes (PDF/PNG), límite 8 MB, folio sanitizado.
- [x] **Headers de seguridad** — CSP, X-Frame-Options DENY, HSTS, nosniff, Referrer-Policy, Permissions-Policy.
- [x] **PII eliminada del código** — Cédulas/titulares del caso demo retirados; titulares solo desde el CTL analizado.
- [x] **PDF con motores dinámicos reales** — Scores calculados (no fijos), ficha SARLAFT en Sección 07B, hallazgo geoespacial POSITIVO/ADVERSO/NO-EVALUADO honesto.
- [x] **Claims falsos eliminados** — Textos que afirmaban consultas en vivo (IGAC/geoportal) sin ejecutarlas; ahora declaran su fuente real.
- [x] **Capas POT empaquetadas** (`api/data/`) — El motor geoespacial funciona en Vercel (antes dependía de rutas Windows).
- [x] **Flujo frontend↔backend** — Los casos se crean en el servidor (antes: solo localStorage → update/delete en 404).
- [x] **Robustez** — Cálculos financieros protegidos, sin asserts que tumben el PDF, sin llamadas duplicadas a Overpass, fuentes multi-plataforma.
- [x] **Suite de tests: 21/21 PASSED** (`tests/test_arhiax_re.py` + `tests/test_smoke_api.py`).

### Sprint 3 — Integraciones institucionales en vivo y expansión a otros mercados (En curso)
Objetivo: pasar de capas estáticas empaquetadas a **consultas en vivo** y habilitar otras ciudades.

- [ ] **I-1: Conector WFS IGAC** — Consulta de capas catastrales/geográficas vía WFS (GetCapabilities/GetFeature) con trazabilidad.
- [ ] **I-2: Conector de geoportales municipales** — Barranquilla, Bogotá (IDECA), Medellín, Cali: capas POT/riesgo por ciudad.
- [ ] **I-3: Catastro multi-ciudad** — Configuración por ciudad (folios, círculos registrales, capas, metodología de valoración).
- [ ] **I-4: Consulta CTL SNR** — Evaluar integración con proveedor de certificados de tradición (API de pago autorizada).
- [ ] **I-5: Verificación SARLAFT real** — Integración con plataforma de listas restrictivas (si el cliente la provee).
- [ ] **I-6: Endpoints y trazabilidad** — Registro de cada consulta institucional (fuente, fecha, parámetros, hash) en el PDF.

### Futuro (Backlog)
- [ ] Persistencia gestionada (Postgres/Turso) en lugar de SQLite efímero.
- [ ] CI/CD: pipeline de tests + escaneo de dependencias (pip-audit) en cada push.
- [ ] Panel de administración con roles.
- [ ] Cola asíncrona para compilación de PDF (evitar timeouts en serverless).

---

## 🧪 Calidad y Tests

- **Suite:** 21 tests (unit + smoke + integración del PDF + motor geoespacial sin red).
- **Cobertura clave:** import del API (detecta regresiones de sintaxis), auth (tokens firmados/expiración), generación de PDF honesto, motor geoespacial con datos empaquetados, inputs financieros inválidos.
- Los tests de geocodificación dependen de Nominatim en vivo (3 tests); el resto es offline.

## 🔑 Configuración de producción (Vercel env vars)

| Variable | Descripción | Estado |
|---|---|---|
| `ARHIAX_ACCESS_PASSWORD` | Contraseña del portal | ⚠️ **PENDIENTE** — usar fallback por defecto |
| `ARHIAX_AUTH_SECRET` | Secreto para firmar tokens | ⚠️ **PENDIENTE** — usar fallback por defecto |
| `ARHIAX_TOKEN_TTL_HOURS` | Vigencia del token (default 8) | Opcional |

> ⚠️ Hasta configurar `ARHIAX_ACCESS_PASSWORD` y `ARHIAX_AUTH_SECRET`, la autenticación usa los valores de desarrollo. **Configurar antes de uso real con clientes.**

## 📁 Estructura del módulo API

| Archivo | Función |
|---|---|
| `api/index.py` | API FastAPI (login, dictámenes, upload, generar, descargar) |
| `api/pdf_compiler.py` | Compilador del Informe Base LAI (ReportLab) |
| `api/dictamen_data.py` | Datos del dictamen (valoración Lonja, alcance, localización) |
| `api/legal_analyzer.py` | Análisis del CTL (NLP, anotaciones, discrepancias) |
| `api/score_engine.py` | Score actuarial LAI v1.0 |
| `api/sarlaft_engine.py` | Ficha SARLAFT estructural |
| `api/carga_economica.py` | Cargas hipotecarias (amortización francesa, LTV) |
| `api/ruta_verificacion.py` | Ruta de verificación profesional |
| `api/geospatial_engine.py` | Motor STRtree + PIP sobre capas POT (`api/data/`) |
| `api/geocoder.py` | Geocodificación Nominatim con fallbacks |
| `api/poi_engine.py` / `api/map_generator.py` | POIs OSM y mapas Leaflet |
| `api/database.py` | SQLite (uso local; efímero en Vercel) |
| `public/index.html` | Frontend del portal |

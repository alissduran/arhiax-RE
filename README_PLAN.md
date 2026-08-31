# ARHIAX RE - Módulo de Evaluación Geoespacial de Amenaza y Riesgo

## Roadmap & Arquitectura de Integración

Este módulo integra los datasets de **Amenaza por Remoción en Masa** y **Áreas en Riesgo** del Plan de Ordenamiento Territorial (POT) de Barranquilla dentro del motor de dictámenes inmobiliarios de **ARHIAX RE**.

---

## 🏛️ Arquitectura del Sistema

```
[ Predio (Lat, Lon) ]
          │
          ▼
┌────────────────────────────────────────────────────────┐
│             api/geospatial_engine.py                   │
│  - Carga en caché GeoJSON (Shapely + STRtree)          │
│  - Evaluador de Intersección Point-in-Polygon (PIP)   │
└─────────────────────────┬──────────────────────────────┘
                          │
         ┌────────────────┴────────────────┐
         ▼                                 ▼
┌──────────────────┐             ┌─────────────────────┐
│  Leaflet Overlay │             │  Informe Base LAI   │
│ (Mapa Interactivo)│             │ (ReportLab / PDF)   │
└──────────────────┘             └─────────────────────┘
```

---

## 🚀 Hitos de Ejecución

### Sprint 0 (Completado 2026-08-31)
- [x] **Hito 0: Definición y Alineación (Fase 0)** - Aprobado por Aliss (`DEFINICIÓN COMPLETA`).
- [x] **Hito 1: Motor Geoespacial Base (`api/geospatial_engine.py`)** - STRtree, caché en memoria, semáforo cromático ARHIAX. Latencia < 10 ms en segundo acceso.
- [x] **Hito 2: Herramienta CLI de Diagnóstico (`check_predio_riesgo.py`)** - `--lat/--lon`, `--direccion`, `--output` JSON con hash de integridad.
- [x] **Hito 3: Integración en Mapas Interactivos (`api/map_generator.py`)** - Tarjeta diagnóstico POT en HTML/Leaflet con colores semáforo en tiempo real.
- [x] **Hito 4: Integración en Dictamen PDF (`api/pdf_compiler.py`)** - Motor geoespacial dinámico. Hallazgo H-GEO en tiempo real. Fallback limpio.
- [x] **Hito 5: Pruebas de Calidad y Validación** - Suite 6/6 tests en verde.
- [x] **Sprint 0 Closure (Titulux)** - Renombrado Informe Base LAI, SCOPE_DISCLAIMER, gate fiduciario, etiquetas neutrales, `test_no_contradiccion`, `test_boundary_avaluo` — todos en verde.

### Sprint 1 (Completado 2026-08-31)
- [x] **Hito S1-1: Conciliación Registral (`api/legal_analyzer.py`)** - `detectar_discrepancia_acreedor()` con normalización de entidades, grupos equivalentes y clasificación por tipo (CESION_NO_REGISTRADA, ACREEDOR_NO_REGISTRADO). Inferencia NLP automática del acreedor SNR desde el CTL.
- [x] **Hito S1-2: Análisis de Cargas Económicas (`api/carga_economica.py`)** - Motor de amortización francés con LTV, saldo insoluto, cuota mensual orientativa y semáforo de riesgo. Integrado en Sección 08B.
- [x] **Hito S1-3: Ruta de Verificación Profesional (`api/ruta_verificacion.py`)** - Generador dinámico de pasos con actor, plazo y fuente legal. Sección 11 del PDF. 9 tipos de hallazgo cubiertos.
- [x] **Hito S1-4: Semáforo Fiduciario Completo (Sección 08B)** - Gate dinámico sin hardcoding. Integra: gate ROJO/VERDE, discrepancia de acreedor (Bloque 2) y cargas económicas (Bloque 3) en sección unificada. Suite: **11/11 tests PASSED**.


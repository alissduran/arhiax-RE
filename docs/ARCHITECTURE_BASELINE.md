# ARHIAX RE — Architecture Baseline (mínima)

Objetivo: convertir progresivamente el conocimiento existente en un sistema
**comprensible → verificable → modular → evolucionable → reproducible**, SIN
reescribir lo que funciona. Estrategia: incremental + vertical slices + strangler.

---

## Layers (conceptuales — sin mover archivos aún)

| Layer | Componentes actuales que YA la cumplen | Se extraerán gradualmente de |
| --- | --- | --- |
| **Contracts** | dataclasses de `arhia_title/contracts.py`, `arhia_sag_screen/contracts.py`, `arhia_expediente/expediente.py`; dicts de `canonical.py`, `consistency.py`, `receipts.py`, `score_engine.py` | `db_record`, `analysis`, tuplas de hallazgos |
| **Domain** | `canonical.py`, `finding_registry.py`, `consistency.py`, `legal_analyzer.py` (reglas), `arhia_title/`, `arhia_sag_screen/`, `arhia_expediente/`, `score_engine.py`, `carga_economica.py`, `edificabilidad.py`/`licencia_analyzer.py`/`solar_engine.py`/`geospatial_engine.py` | `pdf_compiler.py` (lógica de dominio mezclada) |
| **Application / Use Cases** | (parcial) `titulux_bridge.py`, `cola_pdf.py`, flujo en `index.py` | `index.py` (endpoints con lógica inline), `pdf_compiler.py` (orquestación) |
| **Persistence** | `database.py` (factory), `postgres_adapter.py` (adapter), `listas_cache.py` | SQL inline en `index.py` |
| **Infrastructure** | `integrations/*`, `pasto_territorio.py`, `riesgo_volcanico.py`, `catastro_predio*.py`, `geocoder*.py`, `poi_engine.py`, `notificaciones.py`, `cola_pdf.py` | — (ya son infra) |
| **Interfaces** | `index.py` (rutas) | — (se afinan los contratos) |
| **Presentation** | `public/index.html`, `pdf_compiler.py` (ReportLab), `gpv_f77.py`, `map_generator.py`, `shadow_render.py` | `dictamen_data.py` (textos/tablas vs valoración) |
| **Evidence / Observability** | `receipts.py`, `versioning.py`, `finding_registry.py`, `arhia_sag_screen/evidence/` | `pdf_compiler.py` (sección de alcance/traza) |
| **Tests** | `tests/` (257 offline + network) | — |

---

## Principios de la baseline

1. **Source of truth:** Postgres/Neon es el estado canónico del Case (ADR-001).
   `localStorage` = sesión/preferencias/cache; `IndexedDB` = binarios efímeros.
2. **Case ownership:** mínimo `created_by` + visibilidad por rol (ADR-002); multi-tenancy
   queda como decisión de producto.
3. **Migrations:** versionadas (ADR-003); sin `ALTER` idempotente en cada conexión.
4. **Evidence:** clave HMAC estable (ADR-004) antes de cualquier slice de evidencia.
5. **Gate:** `PRE_RENDER_CONSISTENCY_GATE` (ya existente) permanece como barrera de
   calidad antes de emitir un dictus.
6. **Strangler:** `index.py` y `pdf_compiler.py` NO se reescriben; se extraen por
   slices (rutas finas → servicios de aplicación → dominio), manteniendo verde la suite.

---

## Qué se conserva / envuelve / refactoriza (resumen)

- **KEEP:** dominio ya aislado y testeado (canonical, finding_registry, consistency,
  receipts, versioning, legal_analyzer, arhia_title/sag_screen/expediente, score,
  carga, edificabilidad, gpv_f77) + tests + CI.
- **WRAP:** postgres_adapter, titulux_bridge, adapters GIS/geocoder/POI (detrás de puertos).
- **REFACTOR:** index.py, pdf_compiler.py, database.py, dictamen_data.py, public/index.html.
- **DEFER:** motor_tma_lonja_baq, duplicados históricos.
- **REPLACE:** ninguno identificado.

---

## What is still unknown

- Multi-tenancy vs single-tenant (ADR-002) — decisión de producto.
- Enumeración formal del campo `estado` de `dictamenes` (hoy TEXT libre).
- Persistencia estructurada del dictamen generado (hoy solo el PDF/bytes).
- Relación formal job↔case (hoy por `folio`, no por FK).

---

## What is SLICE-001

**Canonical Case Persistence** — mover la fuente de verdad del Case de `localStorage`
al servidor (Neon), con contrato de Case, service de aplicación y migración versionada.
Especificación completa y DoD en `docs/SLICES.md`.

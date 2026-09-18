# VALUATION_DIFF — 040-646406

Descomposición matemática del cambio. Fórmulas de `api/dictamen_data.py:get_valuation`.

```text
M1_base        = área × precio/m²
M1_central     = M1_base × 1.02
canon_mensual  = área × (precio/m² × 0.00538)
M3_central     = (canon_mensual × 0.84 × 12) / cap_rate     (cap_rate = 4.85%)
consolidado    = M1_base  (método principal m1, 100%)
```

## Inputs de valoración

| Variable valuatoria | Anterior | Actual | Changed? | Impact |
| --- | --- | --- | --- | --- |
| area | 58.75 m² | 58.75 m² | no | — |
| barrio | Miramar | PENDIENTE | sí | precio/m² |
| precio_m2_base | 6.800.000 | 5.200.000 | sí | dominante |
| cap_rate | 4.85% | 4.85% | no | — |
| renta_mensual | 2.149.310 | 1.643.590 | sí | derivada de precio/m² |
| M1 | 407.490.000 | 311.610.000 | sí | = área × precio/m² × 1.02 |
| M3 | 446.700.000 | 341.600.000 | sí | = renta × 0.84 × 12 / cap |
| consolidado | 399.500.000 | 305.500.000 | sí | = área × precio/m² |

## M1 decomposition (407.49M → 311.61M)

```text
M1_old = 58.75 × 6.800.000 × 1.02 = 407.490.000   ✓
M1_new = 58.75 × 5.200.000 × 1.02 = 311.610.000   ✓

ΔM1 = -95.880.000  = 100% explicado por Δprecio/m² (6.8M → 5.2M, -23.53%)
```

No cambió área ni comparables ni ajustes: el único factor es `precio/m²`, que a su vez
depende del barrio.

## M3 decomposition (446.7M → 341.6M)

```text
renta_old = 58.75 × 6.800.000 × 0.00538 = 2.149.310   ✓
renta_new = 58.75 × 5.200.000 × 0.00538 = 1.643.590   ✓

M3_old = 2.149.310 × 0.84 × 12 / 0.0485 = 446.701.954  ✓
M3_new = 1.643.590 × 0.84 × 12 / 0.0485 = 341.596.643  ✓

ΔM3 = -105.105.311  = 100% explicado por Δrenta (derivada de Δprecio/m²)
```

La tasa (4.85%) permanece constante; el cambio de M3 es íntegramente la renta, que a
su vez deriva del mismo `precio/m²` (no es independiente de M1).

## Metodología (70/30 → 100/0)

La etiqueta "Ponderación M1 70% / M3 30%" del dictus anterior es un **texto de
presentación**, no una fórmula: en código el consolidado fue siempre
`area × precio/m²` (M1 100%). El cambio a "M1 100% / M3 excepcional" es una
**corrección de la etiqueta** (commits `64dbb5c`/`3654681`/`e58eefd`), sin efecto en la
fórmula del consolidado.

## Attribución de magnitud

| Contribución | Δ | Estado |
| --- | --- | --- |
| Δ identity/context (barrio → precio/m²) | -94M (consolidado) | KNOWN (explica 100%) |
| Δ M1 algorithm | 0 | KNOWN (sin cambio) |
| Δ M3 algorithm | 0 | KNOWN (sin cambio) |
| Δ weighting (70/30→100/0) | 0 (solo etiqueta) | KNOWN (reporting) |
| Δ external data | UNKNOWN | no evidenciado |

**Conclusión:** la caída se explica 100% por la degradación de identidad/contexto
(barrio Miramar → PENDIENTE → precio/m² 6.8M → 5.2M). La metodología no contribuyó.

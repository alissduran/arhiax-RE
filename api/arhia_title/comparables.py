"""Comparables por similitud + detector de coherencia precio–avalúo — XN-3 (F-C / E5).

Reutiliza la idea de "aprender similitud entre inmuebles" (US2023/0020771) pero la ejecuta como un
**paquete de comparables + detección de divergencia precio–avalúo** que **escala al avaluador**
(genera demanda de avalúo). ARHIAX NO emite opinión de valor: sólo describe el rango de comparables y
señala cuándo la divergencia amerita un avaluador (independencia del avaluador intacta).
"""
from dataclasses import dataclass
from typing import Optional, Tuple

# Umbral convencional de divergencia que activa el escalamiento al avaluador.
TOLERANCIA_DIVERGENCIA = 0.15


@dataclass(frozen=True)
class Comparable:
    id: str
    direccion: str
    area: float
    precio: float
    precio_m2: float
    similitud: float
    fuente: str


@dataclass(frozen=True)
class AnalisisComparables:
    comparables: Tuple[Comparable, ...]
    precio_pactado_m2: Optional[float]
    mediana_precio_m2: Optional[float]
    divergencia: Optional[float]
    escalar_a_avaluador: bool
    motivo: str


def _mediana(vals):
    if not vals:
        return None
    s = sorted(vals)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2.0


def analizar_con_comparables(precio_pactado, area_pactada, comparables) -> AnalisisComparables:
    """Compara el precio pactado (por m²) contra la mediana de los comparables (por similitud)."""
    if not area_pactada or area_pactada <= 0:
        return AnalisisComparables(tuple(comparables), None, None, None, False,
                                   "Sin área del inmueble para normalizar el precio por m².")
    pactado_m2 = precio_pactado / area_pactada if precio_pactado is not None else None
    m2s = [c.precio_m2 for c in comparables if c.precio_m2 and c.precio_m2 > 0]
    mediana = _mediana(m2s)
    if pactado_m2 is None or mediana is None or mediana <= 0:
        return AnalisisComparables(tuple(comparables), pactado_m2, mediana, None, False,
                                   "Faltan comparables suficientes para estimar el rango.")
    divergencia = abs(pactado_m2 - mediana) / mediana
    escalar = divergencia > TOLERANCIA_DIVERGENCIA
    if escalar:
        motivo = (f"El precio pactado por m² (COP {pactado_m2:,.0f}) diverge {divergencia:.0%} de la "
                  f"mediana de los comparables (COP {mediana:,.0f}/m²). Se escala al avaluador.")
    else:
        motivo = (f"El precio pactado por m² (COP {pactado_m2:,.0f}) está dentro del rango de "
                  f"la mediana de los comparables (COP {mediana:,.0f}/m²).")
    return AnalisisComparables(tuple(comparables), pactado_m2, mediana, round(divergencia, 4),
                               escalar, motivo)

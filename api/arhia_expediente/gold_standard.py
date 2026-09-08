"""Harness de gold standard / corpus — XN-9 (gate PD-004: FNR ≤2%).

Mide la **cobertura de hallazgos críticos** del motor contra la adjudicación de una **doble
revisión jurídica** (gold standard). Calcula falsos negativos (críticos omitidos), falsos positivos
y cobertura, y aplica el **gate del protocolo** (`07_*`).

> Honestidad: el corpus real (casos adjudicados por abogados) es un **gate** que exige datos
> externos. Aquí se entrega el **harness** y un **fixture marcado ``SYNTHETIC_TEST_FIXTURE``**
> (no es un gold standard real, no se usa para afirmar desempeño).
"""
from dataclasses import dataclass
from typing import Optional, Tuple

UMBRAL_FNR = 0.02      # gate: falsos negativos críticos ≤ 2%
UMBRAL_COBERTURA = 0.95  # gate: cobertura crítica ≥ 95%
_ESTADO_FIXTURE = "SYNTHETIC_TEST_FIXTURE"


@dataclass(frozen=True)
class CasoGold:
    id: str
    hallazgos_gold: Tuple[str, ...]      # críticos identificados por la doble revisión
    hallazgos_sistema: Tuple[str, ...]   # críticos que el sistema detectó
    estado: str = _ESTADO_FIXTURE


@dataclass(frozen=True)
class ResultadoGold:
    casos: int
    tp: int
    fn: int
    fp: int
    fnr: float
    fdr: float
    cobertura: float
    gate_fnr_ok: bool
    gate_cobertura_ok: bool
    gate_pasa: bool
    detalle: Tuple[dict, ...]


def hallazgos_criticos(hallazgos) -> Tuple[str, ...]:
    """Ids de hallazgos con severidad alta/crítica (los que deben cubrirse en el gate)."""
    return tuple(h.id for h in hallazgos if getattr(h, "severidad", "") in ("alta", "critica"))


def evaluar_corpus(casos, *, umbral_fnr=UMBRAL_FNR, umbral_cobertura=UMBRAL_COBERTURA) -> ResultadoGold:
    tp = fn = fp = 0
    detalle = []
    for c in casos:
        gold = set(c.hallazgos_gold)
        sys = set(c.hallazgos_sistema)
        t = len(gold & sys)
        fneg = len(gold - sys)
        fpos = len(sys - gold)
        tp += t
        fn += fneg
        fp += fpos
        detalle.append({"id": c.id, "gold": len(gold), "sistema": len(sys),
                        "tp": t, "fn": fneg, "fp": fpos, "estado": c.estado})
    total_gold = tp + fn
    total_sys = tp + fp
    fnr = fn / max(total_gold, 1)
    fdr = fp / max(total_sys, 1)
    cobertura = tp / max(total_gold, 1)
    gate_fnr_ok = fnr <= umbral_fnr
    gate_cobertura_ok = cobertura >= umbral_cobertura
    return ResultadoGold(casos=len(casos), tp=tp, fn=fn, fp=fp,
                         fnr=round(fnr, 4), fdr=round(fdr, 4), cobertura=round(cobertura, 4),
                         gate_fnr_ok=gate_fnr_ok, gate_cobertura_ok=gate_cobertura_ok,
                         gate_pasa=(gate_fnr_ok and gate_cobertura_ok), detalle=tuple(detalle))


def corpus_sintetico() -> Tuple[CasoGold, ...]:
    """Fixture de control del harness. **NO es un gold standard real** (marcado SYNTHETIC_TEST_FIXTURE)."""
    return (
        CasoGold("S-01", ("TIT_B03", "TIT_B04", "TIT_B01"), ("TIT_B03", "TIT_B04", "TIT_B01")),  # 0 FN
        CasoGold("S-02", ("TIT_B04", "IDENT-04"), ("TIT_B04",)),                                   # 1 FN (omite IDENT-04)
        CasoGold("S-03", ("SAG-C01",), ("SAG-C01", "EXTRA")),                                     # 1 FP (extra)
    )

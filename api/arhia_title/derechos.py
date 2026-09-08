"""Mapa de derechos y limitaciones como capas temporales — XN-4 (F-A).

Un derecho/gravamen/limitación no es un elemento de una lista: es una **superficie sobre el
predio con vigencia**, que puede estar activa o extinta. Aquí se modela como **capas temporales**
(una por anotación) y se expone cuál bloquea la disposición. Inspirado en la lectura invertida de
US20250166406 (rights mapping) pero implementado como conciliación de anotaciones, no como registro
alterno.
"""
from dataclasses import dataclass
from typing import Optional, Tuple

from .contracts import Caso

# Tipos que conforman una capa de derecho/limitación sobre el predio.
TIPOS_CAPA = ("hipoteca", "embargo", "limitacion", "afectacion", "servidumbre", "usufructo")

# Severidad por tipo de capa (lectura de riesgo, no veredicto jurídico).
_SEVERIDAD = {"embargo": "critica", "hipoteca": "alta", "afectacion": "media",
              "limitacion": "media", "usufructo": "media", "servidumbre": "baja"}


@dataclass(frozen=True)
class CapaDerecho:
    tipo: str
    anotacion: int
    instrumento: str
    detalle: str
    vigente: bool
    inicio: str
    fin: Optional[str]            # None mientras la capa esté vigente
    afecta_comerciabilidad: bool
    severidad: str


@dataclass(frozen=True)
class MapaDerechos:
    capas: Tuple[CapaDerecho, ...]
    vigentes: Tuple[CapaDerecho, ...]
    bloquea_disposicion: bool
    resumen: str


def _afecta_comerciabilidad(tipo: str) -> bool:
    return tipo in ("hipoteca", "embargo", "limitacion", "afectacion")


def construir_capas(caso: Caso) -> MapaDerechos:
    """Construye las capas temporales de derechos/limitaciones a partir de las anotaciones."""
    capas = []
    for a in caso.anotaciones:
        if a.tipo not in TIPOS_CAPA:
            continue
        vigente = (a.estado == "vigente")
        capas.append(CapaDerecho(
            tipo=a.tipo, anotacion=a.numero, instrumento=a.instrumento, detalle=a.detalle,
            vigente=vigente, inicio=a.fecha,
            fin=None if vigente else (a.fecha or ""),
            afecta_comerciabilidad=_afecta_comerciabilidad(a.tipo),
            severidad=_SEVERIDAD.get(a.tipo, "baja")))
    vigentes = tuple(c for c in capas if c.vigente)
    bloquea = any(c.afecta_comerciabilidad and c.vigente for c in capas)
    if not capas:
        resumen = "Sin derechos ni limitaciones registrados dentro de las anotaciones recibidas."
    elif vigentes:
        resumen = (f"{len(vigentes)} capa(s) vigente(s) sobre el predio; disposición "
                   + ("RESTRINGIDA" if bloquea else "sin bloqueo por capas vigentes") + ".")
    else:
        resumen = "Derechos/limitaciones registrados pero ya extinguidos (sin capa vigente)."
    return MapaDerechos(capas=tuple(capas), vigentes=vigentes,
                        bloquea_disposicion=bloquea, resumen=resumen)

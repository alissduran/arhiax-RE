"""Flujo de cierre orquestado con estados — XN-6 (F-E).

El cierre no es un documento: es un **flujo con estados** (promesa → protocolo → escritura →
registro → pago). El dolor está en el *entre-etapas* (PD-008/PD-011), así que se modela cada etapa
con estado, responsable, evidencia y espera de terceros, y se detecta el cuello de botella.
"""
import datetime
from dataclasses import dataclass, replace
from typing import Optional, Tuple

ETAPAS_SECUENCIA = ("PROMESA", "PROTOCOLO", "ESCRITURA", "REGISTRO", "PAGO")


@dataclass(frozen=True)
class Etapa:
    nombre: str
    estado: str                      # pendiente | en_curso | completada
    responsable: str
    evidencia: Tuple[str, ...] = ()
    espera_terceros: Tuple[str, ...] = ()
    fecha: str = ""


@dataclass(frozen=True)
class FlujoCierre:
    operacion_id: str
    etapas: Tuple[Etapa, ...]
    progreso: float
    completado: bool
    cuello_botella: Optional[str]


def construir_flujo(operacion_id: str) -> FlujoCierre:
    etapas = []
    for i, nombre in enumerate(ETAPAS_SECUENCIA):
        estado = "en_curso" if i == 0 else "pendiente"
        etapas.append(Etapa(nombre, estado, _responsable_default(nombre)))
    return _actualizar(operacion_id, tuple(etapas))


def _responsable_default(nombre):
    return {"PROMESA": "inmobiliaria", "PROTOCOLO": "abogado", "ESCRITURA": "notaria",
            "REGISTRO": "registro/notaria", "PAGO": "comprador/banco"}.get(nombre, "—")


def avanzar(flujo: FlujoCierre, etapa: str, *, evidencia=(), espera_terceros=(),
            responsable="", fecha: str = "") -> FlujoCierre:
    """Marca la etapa EN CURSO como completada y pone la siguiente en curso.

    Estrictamente **secuencial**: solo la primera etapa sin completar puede avanzar (una etapa
    posterior no puede saltar si la anterior está pendiente). Idempotente.
    """
    etapas = list(flujo.etapas)
    idx_actual = next((i for i, e in enumerate(etapas) if e.estado != "completada"), None)
    if idx_actual is None or etapas[idx_actual].nombre != etapa:
        return flujo  # sin cambio: ya completado o no es la etapa en curso
    actual = etapas[idx_actual]
    etapas[idx_actual] = Etapa(actual.nombre, "completada", responsable or actual.responsable,
                               tuple(evidencia), tuple(espera_terceros), fecha or _hoy())
    if idx_actual + 1 < len(etapas):
        etapas[idx_actual + 1] = replace(etapas[idx_actual + 1], estado="en_curso")
    return _actualizar(flujo.operacion_id, tuple(etapas))


def _hoy():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


def _actualizar(operacion_id, etapas):
    total = len(etapas)
    completadas = sum(1 for e in etapas if e.estado == "completada")
    progreso = round(completadas / total, 3) if total else 0.0
    completado = completadas == total
    cuello = next((e.nombre for e in etapas if e.estado in ("en_curso", "pendiente")), None)
    return FlujoCierre(operacion_id, etapas, progreso, completado, cuello)

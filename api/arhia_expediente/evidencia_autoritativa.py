"""Núcleo de evidencia autoritativa — XN-1 (F-G / E2-E4).

Cada hallazgo, revisión y firma se modela como un **evento firmado con versión previa**, autor y
fundamento. La **autoridad la ejerce el profesional** (abogado / avaluador / oficial de cumplimiento);
el sistema conserva una cadena inalterable (envelope B18 con `hmacChain` + `chain_hash` encadenado)
de *que* ese profesional ejercitó su autoridad sobre ese hallazgo/conclusión.

Insight invertido de la patente US20240388457 (DLT/ledger que "cede la autoridad" al sistema): aquí la
autoridad queda en el profesional y el registro es evidencia de su ejercicio, no una fuente de autoridad.
"""
import datetime
from dataclasses import dataclass
from typing import Optional, Tuple

from arhia_sag_screen.evidence.envelope import build_event, verificar_cadena

# Tipos de evento del ciclo de vida de la autoridad.
EV_FINDING_ACCEPTED = "FINDING_ACCEPTED"
EV_FINDING_MODIFIED = "FINDING_MODIFIED"
EV_FINDING_REJECTED = "FINDING_REJECTED"
EV_CONCLUSION_DRAFTED = "CONCLUSION_DRAFTED"
EV_REPORT_SIGNED = "REPORT_SIGNED"

_CONTROL = "EXP-AUT-01"
_TIER = "Tier1"  # evidencia de autoridad: retención más alta por su valor probatorio


@dataclass
class EventoAutoridad:
    event_id: str
    event_type: str
    hallazgo_id: str
    autor_rol: str
    autor_nombre: str
    timestamp: str
    version: int
    previous_version: Optional[int]
    fundamento: str
    estado: str
    envelope: dict


class LibroEvidenciaAutoridad:
    """Libro de la autoridad profesional: emite eventos firmados con versiones encadenadas."""

    def __init__(self, hmac_key=None, now=None):
        self._hmac = hmac_key
        self._now = now
        self._versiones = {}
        self._eventos = []
        self._chain = ""

    def _next_version(self, hallazgo_id):
        v = self._versiones.get(hallazgo_id, 0) + 1
        self._versiones[hallazgo_id] = v
        return v

    def emitir(self, event_type: str, hallazgo_id: str, autor_rol: str, autor_nombre: str,
               fundamento: str, estado: str) -> EventoAutoridad:
        version = self._next_version(hallazgo_id)
        previous = (version - 1) if version > 1 else None
        now = self._now or datetime.datetime.now(datetime.timezone.utc)
        payload = {
            "eventType": event_type, "hallazgoId": hallazgo_id,
            "autorRol": autor_rol, "autorNombre": autor_nombre,
            "version": version, "versionPrevia": previous,
            "fundamento": fundamento, "estado": estado,
        }
        # Firma/autoridad del profesional (el "agente" del evento es el profesional, no el sistema).
        env = build_event(_CONTROL, event_type, autor_nombre, payload, now=now,
                          at_type="AUTHORITY", retention_tier=_TIER,
                          hmac_key=self._hmac, previous_hash=self._chain)
        self._chain = env["chain_hash"]
        ev = EventoAutoridad(event_id=env["eventId"], event_type=event_type, hallazgo_id=hallazgo_id,
                             autor_rol=autor_rol, autor_nombre=autor_nombre, timestamp=env["timestamp"],
                             version=version, previous_version=previous, fundamento=fundamento,
                             estado=estado, envelope=env)
        self._eventos.append(ev)
        return ev

    def eventos(self) -> Tuple[EventoAutoridad, ...]:
        return tuple(self._eventos)

    def participantes(self, hallazgo_id: str) -> Tuple[EventoAutoridad, ...]:
        return tuple(e for e in self._eventos if e.hallazgo_id == hallazgo_id)

    def cadena_integra(self) -> bool:
        return verificar_cadena([e.envelope for e in self._eventos])

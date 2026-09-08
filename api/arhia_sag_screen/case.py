"""Corredor event-driven de cumplimiento: alerta -> caso -> análisis -> decisión -> reporte.

Estado máquina SAG (estrategia §3.6): no confundir detección con decisión, ni preparado
con enviado. Cada transición emite un evento de evidencia con hmacChain (envelope B18).
"""
import datetime

from .evidence.envelope import build_event, DEFAULT_HMAC_KEY

# estados alcanzables desde cada estado (cadena válida)
TRANSICIONES = {
    "ALERTA_GENERADA": ["CASO_ABIERTO"],
    "CASO_ABIERTO": ["ANALISIS_REALIZADO"],
    "ANALISIS_REALIZADO": ["SOSPECHOSA_CONFIRMADA", "DESCARTADO"],
    "SOSPECHOSA_CONFIRMADA": ["DECISION_REPORTE"],
    "DECISION_REPORTE": ["ROS_PREPARADO"],
    "ROS_PREPARADO": ["ROS_ENVIADO"],
    "ROS_ENVIADO": ["ROS_ACUSE_RECIBIDO"],
    "DESCARTADO": [],
    "ROS_ACUSE_RECIBIDO": [],
}

CONTROL_POR_ESTADO = {
    "ALERTA_GENERADA": "SAG-C06",
    "CASO_ABIERTO": "SAG-C06",
    "ANALISIS_REALIZADO": "SAG-C06",
    "SOSPECHOSA_CONFIRMADA": "SAG-C06",
    "DESCARTADO": "SAG-C06",
    "DECISION_REPORTE": "SAG-C07",
    "ROS_PREPARADO": "SAG-C07",
    "ROS_ENVIADO": "SAG-C07",
    "ROS_ACUSE_RECIBIDO": "SAG-C07",
}


class TransicionInvalida(Exception):
    pass


class CasoLAFT:
    """Caso de cumplimiento derivado de una alerta; avanza por estados con evidencia."""

    def __init__(self, id, contraparte_id, operacion_id, now=None):
        self.id = id
        self.contraparte_id = contraparte_id
        self.operacion_id = operacion_id
        self.estado = "ALERTA_GENERADA"
        self.historial = []
        self._emitir("ALERTA_GENERADA", "sistema", {"contraparteId": contraparte_id, "operacionId": operacion_id}, now)

    def _ts(self, now):
        return (now or datetime.datetime.now(datetime.timezone.utc)).isoformat()

    def _emitir(self, estado, agente, payload, now=None, hmac_key=DEFAULT_HMAC_KEY):
        ts = self._ts(now)
        ev = build_event(CONTROL_POR_ESTADO.get(estado, "SAG-C10"), estado, agente, payload, now=now, at_type="LOG", retention_tier="Tier2", hmac_key=hmac_key)
        self.historial.append({"timestamp": ev["timestamp"], "evento": estado, "agente": agente, "payload": payload, "hmacChain": ev["hmacChain"]})
        return ev

    def transicion(self, estado_destino, agente, payload=None, now=None, hmac_key=DEFAULT_HMAC_KEY):
        if estado_destino not in TRANSICIONES.get(self.estado, []):
            raise TransicionInvalida(f"{self.estado} -> {estado_destino} no permitida")
        payload = dict(payload or {})
        payload.setdefault("contraparteId", self.contraparte_id)
        payload.setdefault("operacionId", self.operacion_id)
        payload.setdefault("casoId", self.id)
        ev = self._emitir(estado_destino, agente, payload, now, hmac_key)
        self.estado = estado_destino
        return ev

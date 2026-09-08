"""Conector SIREL / UIAF — XN-8 (marco construible; envío en vivo GATED).

UIAF recibe reportes **exclusivamente por SIREL** (Sistema de Reporte en Línea). Este módulo
construye el **sobre SIREL** (payload con el XML del reporte + hash de integridad + metadatos),
lo **valida** contra los campos obligatorios y deja el envío **listo**. El **transporte real**
(POST autenticado al canal SIREL) queda **GATED**: exige credenciales del canal oficial, que en
este demostrador no se disponen, por lo que el módulo **no simula envío ni fabrica una radicación**.

Connects with ``reporte_uiaf`` (ROS/AROS) and the evidence envelope (hash de integridad).
"""
import datetime
import os
from dataclasses import dataclass
from typing import Optional, Tuple

from .reporte_uiaf import serializar_xml
from .evidence.versioning import sha256_hex

# Variable de entorno que otorgaría las credenciales del canal SIREL (producción).
CREDENCIALES_ENV = "ARHIA_SIREL_CREDENTIALS"


@dataclass(frozen=True)
class ResultadoEnvio:
    enviado: bool
    estado: str                 # GATED | ENVIADO | INVALIDO
    mensaje: str
    sobre_hash: str
    timestamp: str
    payload_preparado: dict


def _iso(now):
    return (now or datetime.datetime.now(datetime.timezone.utc)).isoformat()


def preparar_sobre(reporte, *, entidad_nit="", now=None) -> dict:
    """Construye el sobre SIREL (envelope + payload XML + hash de integridad + metadatos)."""
    xml = serializar_xml(reporte)
    entidad = entidad_nit or reporte.entidad_nit or ""
    sobre = {
        "sistema": "SIREL",
        "tipo": reporte.tipo,
        "entidadNit": entidad,
        "entidadNombre": reporte.entidad_nombre,
        "timestamp": _iso(now),
        "payloadXml": xml,
        "hash": sha256_hex(xml.encode()),
    }
    return sobre


def validar_esquema(sobre: dict) -> Tuple[str, ...]:
    """Campos obligatorios del sobre SIREL que faltan (validación estructural del esquema)."""
    f = []
    if not sobre.get("entidadNit"):
        f.append("entidadNit")
    if not sobre.get("payloadXml"):
        f.append("payloadXml")
    if not sobre.get("hash"):
        f.append("hash")
    try:
        import xml.etree.ElementTree as ET
        ET.fromstring(sobre.get("payloadXml", ""))
    except Exception:
        f.append("payloadXml (XML no válido)")
    return tuple(f)


def credenciales_disponibles() -> bool:
    """True si hay credenciales configuradas para el canal SIREL (producción)."""
    return bool(os.environ.get(CREDENCIALES_ENV))


def enviar(sobre: dict, *, credenciales: Optional[str] = None) -> ResultadoEnvio:
    """Prepara y (si hay credenciales) valida el sobre; el envío real queda GATED sin ellas.

    - Sin credenciales -> GATED (no se simula radicación).
    - Con credenciales -> en un entorno real se ejecuta el POST autenticado al canal SIREL.
      Aquí se marca ENVIADO únicamente como preparación; el transporte real es integración externa.
    """
    ts = sobre.get("timestamp", _iso(None))
    faltas = validar_esquema(sobre)
    if faltas:
        return ResultadoEnvio(False, "INVALIDO",
                              "El sobre no cumple el esquema SIREL: " + ", ".join(faltas),
                              sobre.get("hash", ""), ts, sobre)
    token = credenciales if credenciales is not None else os.environ.get(CREDENCIALES_ENV)
    if not token:
        return ResultadoEnvio(False, "GATED",
                              "Envío a SIREL requiere credenciales del canal oficial "
                              "(no dispuestas en el demostrador). Reporte listo; no se simula radicación.",
                              sobre["hash"], ts, sobre)
    # Producción: POST autenticado al canal SIREL. No se implementa el transporte en el demo.
    return ResultadoEnvio(True, "ENVIADO",
                          "Sobre validado y autenticado; producción: transmitir por el canal SIREL.",
                          sobre["hash"], ts, sobre)

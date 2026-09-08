"""Reloj de retención documental + legal hold (corrige P0-7 en runtime).

Aplica el término MÁS EXIGENTE concurrente (matriz Retencion_Documental_SAG.md)
y suspende la eliminación con legal hold ante litigio/investigación.

Además, la retención responde a **disparadores jurídicos**: ciertos eventos (un
ROS/AROS radicado, una sospechosa confirmada, una denuncia registrada o un litigio
declarado) congelan automáticamente TODO el expediente (legal hold automático),
porque esa es la conducta prudente de un oficial de cumplimiento y evita destruir
evidencia en plena controversia.
"""
import datetime
from dataclasses import dataclass
from typing import Dict, List, Tuple

# Término mínimo por clase documental (años)
TERMINO_ANIOS: Dict[str, int] = {
    "dd": 5,          # DD/identificación/BF/screening (5 años post-relación)
    "reportes": 5,    # ROS/AROS + acuse
    "matriz": 5,      # matriz de riesgo (vigencia + 5)
    "denuncias": 5,   # canal de denuncias
    "habeas_data": 5, # autorizaciones Habeas Data
    "libros": 10,     # libros y papeles de comercio
    "gobierno": 10,   # gobierno (manuales, políticas, oficial)
}

# Mapa evento -> clase documental (33 eventos del schema)
EVENTO_CLASE: Dict[str, str] = {
    "CONTRAPARTE_CREADA": "dd", "VERIFICACION_REALIZADA": "dd", "BENEFICIARIO_FINAL_REGISTRADO": "dd",
    "LISTA_CONSULTADA": "dd", "COINCIDENCIA_REVISADA": "dd",
    "DD_ACTUALIZADA": "dd", "DD_VENCIDA_DETECTADA": "dd", "DD_ACTUALIZACION_REQUERIDA": "dd", "APROBACION_DD_INTENSIFICADA": "dd",
    "ALERTA_GENERADA": "dd", "ANALISIS_REALIZADO": "dd", "SENAL_REGISTRADA": "dd",
    "ROS_DETECTADO": "reportes", "ROS_DECIDIDO": "reportes", "ROS_PREPARADO": "reportes", "ROS_ENVIADO": "reportes", "ROS_ACUSE_RECIBIDO": "reportes",
    "AROS_REQUERIDO": "reportes", "AROS_PREPARADO": "reportes", "AROS_ENVIADO": "reportes", "AROS_ACUSE_RECIBIDO": "reportes",
    "SOSPECHOSA_CONFIRMADA": "reportes",
    "PERFIL_ASIGNADO": "matriz", "MATRIZ_VALIDADA": "matriz",
    "DENUNCIA_REGISTRADA": "denuncias", "AUSENCIA_DENUNCIAS_DETECTADA": "denuncias",
    "OFICIAL_NOMBRADO": "gobierno", "CURSO_REALIZADO": "gobierno", "RM_CONFIG": "gobierno",
}

# Disparador jurídico -> regla. La presencia de un evento de este tipo congela el expediente.
DISPARADOR_JURIDICO: Dict[str, str] = {
    "ROS_ENVIADO": "reporte_uiaf_radicado",
    "AROS_ENVIADO": "reporte_uiaf_radicado",
    "SOSPECHOSA_CONFIRMADA": "caso_sospechoso_confirmado",
    "DENUNCIA_REGISTRADA": "denuncia_registrada",
    "LITIGIO_DECLARADO": "litigio_o_investigacion",
}


@dataclass
class EventoEvidencia:
    id: str
    event_type: str
    timestamp: datetime.datetime
    legal_hold: bool = False


def retencion_anios(event_type: str) -> int:
    return TERMINO_ANIOS.get(EVENTO_CLASE.get(event_type, "dd"), 5)


def vence(evento: EventoEvidencia, now: datetime.datetime) -> bool:
    if evento.legal_hold:
        return False
    return now >= evento.timestamp + datetime.timedelta(days=retencion_anios(evento.event_type) * 365)


def elegibles_purga(eventos: List[EventoEvidencia], now: datetime.datetime) -> List[EventoEvidencia]:
    """Eventos pasados su término y NO en legal hold."""
    return [e for e in eventos if vence(e, now)]


def activar_legal_hold(eventos: List[EventoEvidencia], ids: List[str]) -> None:
    """Legal hold suspende la eliminación de los eventos indicados."""
    for e in eventos:
        if e.id in ids:
            e.legal_hold = True


def disparadores_juridicos(eventos: List[EventoEvidencia]) -> Tuple[str, ...]:
    """Reglas jurídicas activadas por la presencia de eventos disparadores."""
    reglas: List[str] = []
    for e in eventos:
        regla = DISPARADOR_JURIDICO.get(e.event_type)
        if regla and regla not in reglas:
            reglas.append(regla)
    return tuple(reglas)


def aplicar_legal_hold_por_disparador(eventos: List[EventoEvidencia]) -> Tuple[str, ...]:
    """Congela TODO el expediente si hay un disparador jurídico (ret. por disparador).

    Devuelve las reglas aplicadas (vacío si no hay disparadores). Esta es la conducta
    prudente del oficial de cumplimiento: ante litigio/investigación/reportes radicados,
    no se elimina evidencia mientras la controversia esté viva.
    """
    reglas = disparadores_juridicos(eventos)
    if reglas:
        for e in eventos:
            e.legal_hold = True
    return reglas

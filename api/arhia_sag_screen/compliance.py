"""Pipeline de cumplimiento SAGRILAFT+PTEE — fachada sobre el pipeline único.

`compliance.py` queda como fachada estable sobre `pipeline.ejecutar_pipeline`,
el orquestador único integrado (operación → régimen → screening → BF → matriz →
señales → DD → detección → ROS/AROS → reporte). Conserva el dataclass
`ReporteCumplimiento` y el contrato de `evaluar_operacion` para no romper
llamadas/demos/tests previos.
"""
import datetime
from dataclasses import dataclass
from typing import Optional, Tuple

from .contracts import Contraparte, RegistroJuridico
from .pipeline import ejecutar_pipeline


@dataclass(frozen=True)
class ReporteCumplimiento:
    contraparte_id: str
    nombre: str
    regimen: str
    screening: str
    beneficiarios_finales: Tuple[str, ...]
    senales: Tuple[str, ...]
    operacion_inusual: bool
    perfil: str
    eventos: Tuple[dict, ...]


def evaluar_operacion(contraparte: Contraparte, operacion: dict, *,
                      registro: Optional[RegistroJuridico] = None,
                      registros_lista: tuple = (),
                      catalogo_senales: tuple = (),
                      patron_normal: float = 1.0,
                      umbral_deteccion: float = 2.0,
                      umbral_bf: float = 0.05,
                      now: Optional[datetime.datetime] = None,
                      hmac_key: str = ""):
    """Evalúa una operación a través del pipeline único de cumplimiento."""
    res = ejecutar_pipeline(
        contraparte, operacion, registro=registro, registros_lista=registros_lista,
        catalogo_senales=catalogo_senales, patron_normal=patron_normal,
        umbral_deteccion=umbral_deteccion, umbral_bf=umbral_bf, now=now, hmac_key=hmac_key)
    bf_nombres = tuple(b.nombre for b in res.beneficiarios_finales)
    return ReporteCumplimiento(
        contraparte_id=res.contraparte_id, nombre=res.nombre, regimen=res.regimen,
        screening=res.screening, beneficiarios_finales=bf_nombres, senales=res.senales,
        operacion_inusual=res.operacion_inusual, perfil=res.perfil, eventos=res.eventos)

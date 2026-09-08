"""Salida ciudadana — PD-009 (comprensión y accionabilidad del ciudadano).

Traduce el expediente a un resumen por capas (qué está verificado, qué falta, qué riesgo y
cuál es el siguiente paso) en lenguaje claro, con un **aviso anti-falsa-certeza** explícito.
El gate PD-009 pide ≥80% de comprensión y **sin falsa seguridad**.
"""
from dataclasses import dataclass
from typing import Tuple

from arhia_expediente.expediente import Expediente, FichaIntegridad
from arhia_expediente.conclusion import Conclusion
from arhia_sag_screen.kyb.uso_suelo import FichaUsoSuelo


def _estados(hallazgos, *estados):
    return tuple(h.titulo for h in hallazgos if h.estado in estados)


@dataclass(frozen=True)
class MensajeCiudadano:
    verificado: Tuple[str, ...]
    falta: Tuple[str, ...]
    riesgo: Tuple[str, ...]
    proximo_paso: Tuple[str, ...]
    lenguaje_plano: str
    aviso: str


def construir_mensaje_ciudadano(expediente: Expediente, integridad: FichaIntegridad,
                                conclusion: Conclusion, ficha_uso_suelo=None) -> MensajeCiudadano:
    h = expediente.hallazgos
    verificado = _estados(h, "OK")
    falta = _estados(h, "INFORMACION_INSUFICIENTE", "REQUIERE_REVISION", "INCONSISTENTE")
    riesgo = _estados(h, "RIESGO", "OBSERVACION")
    proximo = list(conclusion.recomendaciones[:3])

    if integridad.operacion_inusual:
        riesgo = tuple(riesgo) + ("Operación con características inusuales (posible LA/FT).",)
    if integridad.bf_coincidencia:
        riesgo = tuple(riesgo) + ("Un beneficiario final aparece en una lista vinculante.",)
    if ficha_uso_suelo and ficha_uso_suelo.actividad_resultado == "no_permitida":
        riesgo = tuple(riesgo) + (f"La actividad '{ficha_uso_suelo.actividad_consultada}' no está permitida en este predio.",)
        proximo += ("Verificar el uso permitido del suelo con planeación/curaduría.",)

    plano = ("Este análisis organiza y verifica la evidencia del inmueble (identidad, título, "
             "cargas, valor y cumplimiento). Dice qué está comprobado, qué falta y qué necesita "
             "revisión, para que usted y su profesional decidan con la información ordenada. "
             "Encontró " + str(len(riesgo)) + " punto(s) que requieren atención.")
    aviso = ("Análisis preliminar automático. NO certifica la perfección del título, NO garantiza "
             "la aprobación de crédito o seguro, y NO sustituye el concepto del abogado, el "
             "avaluador o la institución. La conclusión la emite el profesional autorizado.")

    return MensajeCiudadano(verificado=tuple(verificado), falta=tuple(falta), riesgo=tuple(riesgo),
                            proximo_paso=tuple(proximo), lenguaje_plano=plano, aviso=aviso)

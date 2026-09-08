"""Motor de conclusión profesional (simulado) para el dictamen completo.

En un entorno real la conclusión la emite el profesional competente (abogado
especializado, avaluador RAA, oficial de cumplimiento). En este demo se **simula
el comportamiento de un profesional autorizado** a partir de los hallazgos
objetivos (estado/severidad) y del resultado del pipeline SAGRILAFT+PTEE, de
forma determinista y trazable.
"""
from dataclasses import dataclass
from typing import Optional, Tuple

from arhia_title.contracts import Hallazgo
from arhia_expediente.expediente import FichaIntegridad, Expediente

# Estados que constituyen riesgo directo
_RIESGO = {"RIESGO", "INCONSISTENTE"}
# Estados que constituyen observación / información a completar
_OBSERVACION = {"OBSERVACION", "INFORMACION_INSUFICIENTE", "REQUIERE_REVISION"}
_SEVERO = {"alta", "critica"}


@dataclass(frozen=True)
class Conclusion:
    veredicto: str                    # FAVORABLE | FAVORABLE CON OBSERVACIONES | DESFAVORABLE | SUSPENDER
    fundamento: str
    riesgos_prioritarios: Tuple[str, ...]
    observaciones: Tuple[str, ...]
    recomendaciones: Tuple[str, ...]
    soporte_compliance: str
    firmantes: Tuple[dict, ...]


def _clasificar(hallazgos):
    # Bloqueante: defecto de fondo en título/valor (no de cumplimiento), severo.
    # Los hallazgos de cumplimiento (EXP-INT, p. ej. operación inusual/LA-FT) son
    # sospechas que REQUIEREN ANÁLISIS, no defectos confirmados: van a observaciones.
    def is_blocking(h):
        return (h.estado in _RIESGO and h.severidad in _SEVERO and not h.regla.startswith("EXP-INT"))

    def is_observation(h):
        return (h.estado in _OBSERVACION
                or (h.estado in _RIESGO and (h.severidad not in _SEVERO or h.regla.startswith("EXP-INT"))))

    riesgos = [h for h in hallazgos if is_blocking(h)]
    observaciones = [h for h in hallazgos if is_observation(h)]
    return riesgos, observaciones


def concluir(expediente: Expediente, integridad: FichaIntegridad, *,
             firmantes: Optional[Tuple[dict, ...]] = None,
             ficha_ptee=None,  # FichaPtee (kyb.ptee) — riesgo de corrupción/soborno
             ficha_uso_suelo=None,  # FichaUsoSuelo (kyb.uso_suelo) — polígono POT
             base: str = "Circular 100-000020 (Cap. IX) + Ley 1579/2012 + Código Civil") -> Conclusion:
    """Simula la conclusión del profesional autorizado para el dictamen completo."""
    riesgos, observaciones = _clasificar(expediente.hallazgos)
    screening = integridad.screening
    inusual = bool(integridad.operacion_inusual)
    requiere = bool(integridad.requiere_analisis)
    senales = tuple(integridad.senales)

    riesgos_txt = tuple(h.id + " · " + h.titulo for h in riesgos)
    obs_txt = tuple(h.id + " · " + h.titulo for h in observaciones)

    # 0) Screening incompleto (fuente no disponible) -> preanálisis incompleto -> bloqueo
    if not getattr(integridad, "screening_completo", True):
        veredicto = "PREANALISIS_INCOMPLETO"
        fundamento = ("El screening no se completó: una o más fuentes de listas no están disponibles "
                      "(FUENTE_NO_DISPONIBLE). El expediente está incompleto y la decisión queda "
                      "bloqueada de forma precautoria.")
        recomendaciones = ("Completar la consulta de fuentes vinculantes antes de decidir.",)
    # 1) Coincidencia en screening (contraparte o BF) -> bloqueo precautorio
    elif screening == "coincidencia" or integridad.bf_coincidencia:
        veredicto = "BLOQUEO_PRECAUTORIO"
        fundamento = ("Coincidencia en screening de listas vinculantes (9.17), sea de la contraparte "
                      "o de un beneficiario final: antes de decidir procede revisión humana y debida "
                      "diligencia intensificada.")
        recomendaciones = tuple(h.accion for h in expediente.hallazgos if h.accion and h.responsable in ("abogado", "sistema"))
    # 1b) Indicadores de soborno / corrupción (PTEE, Ley 1778) -> bloqueo precautorio
    elif (ficha_ptee is not None and ("pagoFuncionarioPublico" in ficha_ptee.senales
                                      or "comisionIrregular" in ficha_ptee.senales)):
        veredicto = "BLOQUEO_PRECAUTORIO"
        fundamento = ("Indicadores de soborno/corrupción (PTEE, Ley 1778/2016): pago a funcionario público "
                      "o comisión irregular detectada. Procede suspender y escalar al oficial de cumplimiento.")
        recomendaciones = tuple(ficha_ptee.recomendaciones)
    # 1c) Actividad no permitida por el polígono POT -> no procede
    elif (ficha_uso_suelo is not None and ficha_uso_suelo.actividad_resultado == "no_permitida"):
        veredicto = "BLOQUEO_PRECAUTORIO"
        fundamento = ("La actividad consultada ('" + (ficha_uso_suelo.actividad_consultada or "—")
                      + "') NO está permitida en el polígono del POT de este predio (zona "
                      + ficha_uso_suelo.zona + " · " + ficha_uso_suelo.zona_nombre + "). "
                      + ficha_uso_suelo.base)
        recomendaciones = ("Verificar con la curaduría/secretaría de planeación el uso permitido y "
                           "el licenciamiento aplicable; considerar un uso autorizado.")
    # 2) Riesgo alto/crítico en título o identidad -> bloqueo precautorio
    elif riesgos:
        veredicto = "BLOQUEO_PRECAUTORIO"
        fundamento = ("Riesgos altos/críticos en la titularidad, gravámenes o identidad del inmueble "
                      "o de la operación; la operación no procede sin subsanarlos.")
        recomendaciones = tuple(h.accion for h in riesgos if h.accion) or tuple(
            h.accion for h in expediente.hallazgos if h.accion)
    # 3) Operación inusual (posible LA/FT) -> requiere revisión
    elif inusual:
        veredicto = "REQUIERE_REVISION"
        fundamento = ("La operación presenta características inusuales (posible LA/FT, señales detectadas). "
                      "Procede con análisis del oficial de cumplimiento y diligencias ampliadas antes del cierre.")
        recomendaciones = ("Revisar origen de fondos y relación del pagador.", "Verificar justificación de la divergencia de valor.",
                           "Registrar la evidencia del análisis (9.22) y, si procede, reporte a la UIAF.")
    # 3b) Riesgo de corrupción alto (sin soborno directo) -> requiere revisión
    elif ficha_ptee is not None and ficha_ptee.riesgo_corrupcion == "alto":
        veredicto = "REQUIERE_REVISION"
        fundamento = ("La operación presenta alto riesgo de corrupción (PTEE, Ley 1778/2016): relación con "
                      "funcionarios, uso de intermediarios o sector sensible. Procede diligencia ampliada "
                      "y revisión del oficial de cumplimiento.")
        recomendaciones = tuple(ficha_ptee.recomendaciones) or ("Aplicar diligencia ampliada y verificar el canal de denuncias.",)
    # 4) Observaciones / información por completar -> requiere revisión
    elif observaciones:
        veredicto = "REQUIERE_REVISION"
        fundamento = ("Existen observaciones y datos por completar/verificar; la operación es viable "
                      "con salvaguardas y documentos de soporte.")
        recomendaciones = tuple(h.accion for h in observaciones if h.accion) or (
            "Completar documentación y validar con el profesional competente.")
    # 5) Sin hallazgo automático en el alcance analizado
    else:
        veredicto = "SIN_HALLAZGO_AUTOMATICO"
        fundamento = ("El preanálisis no identificó hallazgos automáticos dentro del alcance analizado. "
                      "Esto NO equivale a un concepto favorable del título ni a una aprobación; la "
                      "conclusión la emite el profesional competente.")
        recomendaciones = ("Conservar la evidencia del análisis y del cumplimiento.",
                           "Solicitar la revisión del profesional (abogado / avaluador / oficial de cumplimiento).")

    if senales:
        extra = "; ".join(senales)
        fundamento = fundamento + " Señales registradas: " + extra + "."

    firmantes = firmantes or _firmantes_por_defecto(base)
    soporte = _soporte_compliance(integridad)
    return Conclusion(
        veredicto=veredicto, fundamento=fundamento, riesgos_prioritarios=riesgos_txt,
        observaciones=obs_txt, recomendaciones=tuple(recomendaciones),
        soporte_compliance=soporte, firmantes=firmantes)


def _soporte_compliance(integridad: FichaIntegridad) -> str:
    partes = []
    if integridad.regimen:
        partes.append("régimen estimado " + integridad.regimen)
    if integridad.sarlaft:
        partes.append("cumplimiento " + integridad.sarlaft)
    if integridad.screening:
        partes.append("screening " + integridad.screening)
    if integridad.beneficiario_final:
        partes.append("BF " + integridad.beneficiario_final)
    if integridad.bf_coincidencia:
        partes.append("BF en listas (coincidencia)")
    if integridad.perfil:
        partes.append("perfil " + integridad.perfil)
    return " · ".join(partes) or "sin datos de cumplimiento"


def _firmantes_por_defecto(base: str) -> Tuple[dict, ...]:
    # La auditoría exige NO fabricar atestaciones profesionales. El sistema no simula firmas:
    # la firma y la opinión son del profesional competente.
    return ()

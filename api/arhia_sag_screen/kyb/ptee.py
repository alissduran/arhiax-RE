"""Evaluación de riesgo de corrupción / soborno — PTEE (Programa de Transparencia y Ética Empresarial).

Complementa el SAGRILAFT (LA/FT) con la capa de **corrupción y soborno transnacional**
(Ley 1778 de 2016 + Circular 100-000020, Cap. IX). El PTEE exige identificar el riesgo de
corrupción, aplicar debida diligencia y detectar señales de soborno, con un canal de denuncias.

Se determinan factores de riesgo y señales propias del PTEE (distintas de las LA/FT), se
clasifica el riesgo (alto/medio/bajo) y se decide si procede **diligencia ampliada**.
"""
from dataclasses import dataclass
from typing import Tuple

from .canal import Denuncia

# Señales de corrupción / soborno (PTEE). Catálogo versionado; distinto de las señales LA/FT.
SENALES_PTEE = (
    "pagoFuncionarioPublico",
    "usoIntermediario",
    "pagoNoDocumentado",
    "licenciaAutorizacionTercero",
    "donacionPolitica",
    "conflictoInteres",
    "regaloHospitalidadExcesivo",
    "comisionIrregular",
)

# Sectores con mayor exposición a corrupción / soborno transnacional.
SECTORES_ALTO_RIESGO = {"construccion", "infraestructura", "hidrocarburos", "mineria",
                        "farmaceutico", "salud", "aduanas", "logistica", "defensa"}

BASE_PTEE = "Ley 1778/2016 (soborno transnacional) + Circular 100-000020 (Cap. IX, PTEE)."


@dataclass(frozen=True)
class FichaPtee:
    riesgo_corrupcion: str          # alto | medio | bajo
    factores: Tuple[str, ...]
    senales: Tuple[str, ...]
    funcionario_publico: bool
    uso_intermediario: bool
    diligencia_ampliada: bool
    canal_denuncias: str            # implementado | no_verificado | con_denuncia
    denuncias: Tuple[Denuncia, ...]
    base: str
    recomendaciones: Tuple[str, ...]


def _canal_estado(operacion, denuncias):
    if denuncias:
        return "con_denuncia"
    if operacion.get("canalDenuncias"):
        return "implementado"
    return "no_verificado"


def evaluar_ptee(contraparte, operacion, *, catalogo=SENALES_PTEE,
                 sector_riesgo=SECTORES_ALTO_RIESGO, denuncias=()):
    """Evalúa el riesgo de corrupción/soborno de la contraparte y la operación."""
    operacion = dict(operacion or {})
    senales = tuple(s for s in operacion.get("senalesPTEE", ()) if s in catalogo)
    es_funcionario = bool(operacion.get("esFuncionarioPublico") or operacion.get("esPEP"))
    usa_intermediario = bool(operacion.get("usaIntermediario") or "usoIntermediario" in senales)
    sector = (operacion.get("sector") or "").strip().lower()

    factores = []
    if es_funcionario:
        factores.append("relacion_con_funcionario_publico")
    if usa_intermediario:
        factores.append("uso_de_intermediario")
    if operacion.get("licenciaAutorizacion"):
        factores.append("licencia_o_autorizacion_de_terceros")
    if sector in sector_riesgo:
        factores.append("sector_alto_riesgo_corrupcion")
    if "pagoNoDocumentado" in senales or operacion.get("pagoNoDocumentado"):
        factores.append("pago_no_documentado")
    if "comisionIrregular" in senales:
        factores.append("comision_irregular")
    if "regaloHospitalidadExcesivo" in senales or operacion.get("regaloHospitalidadExcesivo"):
        factores.append("regalos_u_hospitalidad_excesivos")
    if "conflictoInteres" in senales or operacion.get("conflictoInteres"):
        factores.append("conflicto_de_interes")

    # Riesgo alto: relación directa con funcionario, intermediario, pago a funcionario o comisión irregular.
    riesgo = ("alto" if (es_funcionario or usa_intermediario
                         or "pagoFuncionarioPublico" in senales or "comisionIrregular" in senales)
              else ("medio" if factores else "bajo"))
    diligencia = riesgo == "alto"
    canal = _canal_estado(operacion, tuple(denuncias))

    recomendaciones = ()
    if es_funcionario:
        recomendaciones += ("Confirmar identidad del funcionario público y la naturaleza de la relación.",)
    if usa_intermediario:
        recomendaciones += ("Aplicar DD ampliada al intermediario/agente y verificar su comisión.",)
    if "pagoNoDocumentado" in senales or operacion.get("pagoNoDocumentado"):
        recomendaciones += ("Documentar el pago y su justificación; prohibir pagos no documentados.",)
    if riesgo == "alto":
        recomendaciones += ("Aplicar diligencia ampliada y escalar al oficial de cumplimiento.",)
    if canal == "no_verificado":
        recomendaciones += ("Asegurar la existencia de un canal de denuncias anónimo (PTEE 9.21.4).",)

    return FichaPtee(
        riesgo_corrupcion=riesgo, factores=tuple(factores), senales=senales,
        funcionario_publico=es_funcionario, uso_intermediario=usa_intermediario,
        diligencia_ampliada=diligencia, canal_denuncias=canal,
        denuncias=tuple(denuncias), base=BASE_PTEE, recomendaciones=recomendaciones)

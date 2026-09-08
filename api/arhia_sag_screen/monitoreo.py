"""Monitoreo continuo de la cartera — barrido batch de cumplimiento SAGRILAFT+PTEE.

Complementa el dictamen por-operación con la **capa operativa**: recorre todas las
entidades/contrapartes y sus operaciones, re-ejecuta el pipeline (screening, DD, señales,
perfil, BF) y el PTEE, y produce:
  - un **estado por entidad** (régimen, screening, perfil, señales, DD, inusual, BF, PTEE);
  - **alertas** priorizadas (coincidencia, BF en listas, DD vencida, perfil alto, inusual,
    señales LA/FT, riesgo de corrupción alto);
  - un **tablero** de KPIs (los indicadores que alimentan F1h/F11).
"""
import datetime
from dataclasses import dataclass
from typing import Optional, Tuple

from .contracts import Contraparte, RegistroJuridico
from .pipeline import ResultadoPipeline, ejecutar_pipeline
from .kyb.ptee import FichaPtee, evaluar_ptee


@dataclass(frozen=True)
class EstadoCartera:
    contraparte_id: str
    nombre: str
    regimen: str
    screening: str
    perfil: str
    senales: Tuple[str, ...]
    dd_vencida: bool
    operacion_inusual: bool
    bf_coincidencia: bool
    riesgo_ptee: str
    alertas: Tuple[str, ...]


@dataclass(frozen=True)
class ReporteMonitoreo:
    total: int
    con_coincidencia: int
    dd_vencidas: int
    perfil_alto: int
    con_senales: int
    inusuales: int
    bf_coincidencias: int
    ptee_alto: int
    entidades: Tuple[EstadoCartera, ...]
    tablero: Tuple[dict, ...]
    alertas: Tuple[dict, ...]


def _alertas_de(r: ResultadoPipeline, ficha: Optional[FichaPtee]) -> Tuple[str, ...]:
    a = []
    if r.screening == "coincidencia":
        a.append("ALERTA: coincidencia en listas (9.17)")
    if r.bf_coincidencia:
        a.append("ALERTA: beneficiario final en listas")
    if r.dd_vencida:
        a.append("ALERTA: debida diligencia vencida (9.15/9.17)")
    if r.perfil == "alto":
        a.append("ATENCION: perfil de riesgo alto")
    if r.operacion_inusual:
        a.append("ATENCION: operacion inusual (posible LA/FT)")
    if r.senales:
        a.append("ATENCION: senales LA/FT: " + "; ".join(r.senales))
    if ficha is not None and ficha.riesgo_corrupcion == "alto":
        a.append("ATENCION: riesgo de corrupcion alto (PTEE, Ley 1778)")
    return tuple(a)


def _entidades_desde_dicts(items):
    for it in items:
        yield it["contraparte"], it.get("registro"), it.get("operacion", {})


def monitorear_cartera(items, *,
                       listas_por_fuente: dict = (),
                       registros_lista: tuple = (),
                       catalogo_senales: tuple = (),
                       catalogo_ptee: tuple = (),
                       now: Optional[datetime.datetime] = None,
                       hmac_key: str = "",
                       engine: str = "python",
                       ) -> ReporteMonitoreo:
    """Recorre la cartera y produce el estado, alertas y tablero de cumplimiento.

    `items`: iterable de dicts {'contraparte','registro','operacion'}.
    `listas_por_fuente`: fuente -> (registros, version, hash) para screening multifuente.
    """
    now = now or datetime.datetime.now(datetime.timezone.utc)
    estados = []
    tablero = {"total": 0, "coincidencia": 0, "dd_vencida": 0, "perfil_alto": 0,
               "senales": 0, "inusual": 0, "bf_coincidencia": 0, "ptee_alto": 0}
    alertas = []

    for contraparte, registro, operacion in _entidades_desde_dicts(items):
        res = ejecutar_pipeline(contraparte, operacion, registro=registro,
                                registros_lista=() if listas_por_fuente else registros_lista,
                                listas_por_fuente=listas_por_fuente,
                                catalogo_senales=catalogo_senales, now=now, hmac_key=hmac_key,
                                engine=engine)
        ficha = None
        if res.regimen and res.regimen != "no_obligado":
            op_ptee = dict(operacion)
            op_ptee.update({"senalesPTEE": tuple(operacion.get("senalesPTEE", ())),
                            "esFuncionarioPublico": operacion.get("esFuncionarioPublico", False),
                            "usaIntermediario": operacion.get("usaIntermediario", False),
                            "canalDenuncias": operacion.get("canalDenuncias", True),
                            "sector": (registro.sector if registro else "")})
            ficha = evaluar_ptee(contraparte, op_ptee, catalogo=catalogo_ptee, denuncias=operacion.get("denunciasPTEE", ()))

        estado = EstadoCartera(
            contraparte_id=contraparte.contraparte_id, nombre=contraparte.nombre,
            regimen=res.regimen, screening=res.screening, perfil=res.perfil, senales=res.senales,
            dd_vencida=res.dd_vencida, operacion_inusual=res.operacion_inusual,
            bf_coincidencia=res.bf_coincidencia,
            riesgo_ptee=(ficha.riesgo_corrupcion if ficha else "no_evaluado"),
            alertas=_alertas_de(res, ficha))
        estados.append(estado)

        tablero["total"] += 1
        tablero["coincidencia"] += int(res.screening == "coincidencia")
        tablero["dd_vencida"] += int(res.dd_vencida)
        tablero["perfil_alto"] += int(res.perfil == "alto")
        tablero["senales"] += int(bool(res.senales))
        tablero["inusual"] += int(res.operacion_inusual)
        tablero["bf_coincidencia"] += int(res.bf_coincidencia)
        tablero["ptee_alto"] += int(bool(ficha and ficha.riesgo_corrupcion == "alto"))
        for al in estado.alertas:
            alertas.append({"contraparteId": contraparte.contraparte_id, "nombre": contraparte.nombre, "alerta": al})

    # Tablero resumido (KPIs en el formato de indicadores 9.11)
    ts = [{"indicador": "Entidades analizadas", "valor": tablero["total"]},
          {"indicador": "Con coincidencia en listas", "valor": tablero["coincidencia"]},
          {"indicador": "DD vencida", "valor": tablero["dd_vencida"]},
          {"indicador": "Perfil alto", "valor": tablero["perfil_alto"]},
          {"indicador": "Con senales LA/FT", "valor": tablero["senales"]},
          {"indicador": "Operaciones inusuales", "valor": tablero["inusual"]},
          {"indicador": "BF en listas", "valor": tablero["bf_coincidencia"]},
          {"indicador": "Riesgo PTEE alto", "valor": tablero["ptee_alto"]}]

    return ReporteMonitoreo(total=tablero["total"], con_coincidencia=tablero["coincidencia"],
                            dd_vencidas=tablero["dd_vencida"], perfil_alto=tablero["perfil_alto"],
                            con_senales=tablero["senales"], inusuales=tablero["inusual"],
                            bf_coincidencias=tablero["bf_coincidencia"], ptee_alto=tablero["ptee_alto"],
                            entidades=tuple(estados), tablero=tuple(ts), alertas=tuple(alertas))

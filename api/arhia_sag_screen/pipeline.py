"""Pipeline único integrado SAGRILAFT+PTEE.

Encadena la cadena completa de cumplimiento de UNA operación:
    operación → régimen → screening → beneficiario final → matriz/perfil
    → señales → DD (calendario) → detección → ROS/AROS → reporte (+ corredor de caso).

A diferencia de `compliance.evaluar_operacion` (evaluación parcial), aquí cada control
C01..C12 produce su evento de evidencia (envelope B18 con hmacChain) y la decisión
normativa la emiten los bundes Rego (B20..B30) vía `opaclient`, con paridad Python
cuando OPA no está disponible. La cadena es un único punto de entrada.
"""
import datetime
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

from .contracts import BeneficiarioFinal, Contraparte, RegistroJuridico, ResultadoConsulta
from .evidence.envelope import build_event, DEFAULT_HMAC_KEY
from .kyb.beneficiario_final import derivar_beneficiario_final
from .kyb.regimen import clasificar_regimen
from .match.matcher import consultar
from .case import CasoLAFT
from . import opaclient


@dataclass(frozen=True)
class ResultadoPipeline:
    """Resultado completo del pipeline único de cumplimiento."""
    contraparte_id: str
    nombre: str
    tipo: str
    regimen: str
    fundamento_regimen: str
    screening: str
    screening_detalle: Optional[ResultadoConsulta]
    screening_por_fuente: Tuple[dict, ...]
    fuentes_no_disponibles: Tuple[str, ...]
    screening_completo: bool
    beneficiarios_finales: Tuple[BeneficiarioFinal, ...]
    bf_resultados: Tuple[ResultadoConsulta, ...]
    bf_coincidencia: bool
    perfil: str
    factores: Tuple[str, ...]
    senales: Tuple[str, ...]
    dd_vencida: bool
    dd_inmediata: bool
    dd_exceso: bool
    operacion_inusual: bool
    requiere_analisis: bool
    aros_requerido: bool
    ausencia_denuncias: bool
    contraparte_ok: bool
    caso_id: Optional[str]
    caso_estado: Optional[str]
    caso_historial: Tuple[dict, ...]
    eventos: Tuple[dict, ...]


def _hoy(now):
    return now or datetime.datetime.now(datetime.timezone.utc)


def _epoch(dt) -> int:
    return int(dt.timestamp())


def _campos_contraparte(cp: Contraparte, operacion: dict) -> Dict[str, Any]:
    """Los 8 campos del 9.15.1 (+ flags) para el bundle B24 (C01)."""
    return {
        "contraparteId": cp.contraparte_id,
        "nombre": cp.nombre,
        "identificacion": cp.numero_documento or "",
        "domicilio": operacion.get("domicilio", ""),
        "beneficiarioFinal": operacion.get("beneficiarioFinal", "NO"),
        "representanteLegal": operacion.get("representanteLegal", ""),
        "personaContacto": operacion.get("personaContacto", ""),
        "cargo": operacion.get("cargo", ""),
        "fechaConocimiento": operacion.get("fechaConocimiento", ""),
        "esContraparteInterna": bool(operacion.get("esContraparteInterna", False)),
        "estadoVerificacion": operacion.get("estadoVerificacion", "verificado"),
    }


_CAMPOS_REQ_C01 = ["nombre", "identificacion", "domicilio", "beneficiarioFinal",
                   "representanteLegal", "personaContacto", "cargo", "fechaConocimiento"]


def _contraparte_ok(campos: dict) -> bool:
    return all(campos.get(c) for c in _CAMPOS_REQ_C01)


def _build_opa_input(cp, operacion, registro, screening_resultado, consulta,
                     perfil, factores, senales, *, now, agent_id,
                     ultima_actualizacion_ts, solicitudes_dd,
                     ultimo_ros_ts, ultimo_aros_ts, trimestre,
                     denuncias_periodo, monitoreo_canal, periodo) -> Dict[str, Any]:
    accionistas = []
    rep_legal = ""
    if registro is not None:
        rep_legal = registro.representante_legal or ""
        accionistas = [
            {"participacion": a.participacion, "nombre": a.nombre,
             "tipoDocumento": a.tipo_documento, "numeroDocumento": a.numero_documento}
            for a in registro.composicion_accionaria
        ]
    campos = _campos_contraparte(cp, operacion)
    sn = senales[0] if senales else operacion.get("senal", "")
    now_epoch = _epoch(now)
    return {
        "agentId": agent_id,
        "context": {"currentTime": now_epoch},
        "operacion": {
            "operacionId": operacion.get("operacionId", ""),
            "contraparteId": cp.contraparte_id,
            "monto": operacion.get("monto", 0.0),
            "patronNormal": operacion.get("patronNormal", 1.0),
            "senal": sn,
        },
        "contraparte": {
            **campos,
            "perfil": perfil,
            "factores": list(factores),
            "ultimaActualizacion": ultima_actualizacion_ts or now_epoch,
            "senalActiva": bool(senales),
            "solicitudesDD": solicitudes_dd,
            "representanteLegal": rep_legal,
            "accionistas": accionistas,
        },
        "consulta": {
            "contraparteId": cp.contraparte_id,
            "lista": consulta.lista if consulta else "",
            "listaVersion": consulta.lista_version if consulta else "",
            "listaHash": consulta.lista_hash if consulta else "",
            "resultado": screening_resultado,
            "revision": "confirmada" if screening_resultado == "coincidencia" else "",
        },
        "sujeto": {
            "ultimoRosTimestamp": ultimo_ros_ts or now_epoch,
            "ultimoArosTimestamp": ultimo_aros_ts or now_epoch,
            "trimestre": trimestre,
        },
        "canal": {
            "denunciasEnPeriodo": denuncias_periodo,
            "monitoreoRealizado": monitoreo_canal,
            "periodo": periodo,
        },
    }


def ejecutar_pipeline(contraparte: Contraparte, operacion: dict, *,
                      registro: Optional[RegistroJuridico] = None,
                      registros_lista: tuple = (),
                      listas_por_fuente: dict = (),   # fuente -> (registros, version, hash)
                      lista_fuente: str = "onu",
                      lista_version: str = "2026-09-01",
                      lista_hash: str = "hash-seed",
                      catalogo_senales: tuple = (),
                      patron_normal: float = 1.0,
                      umbral_deteccion: float = 2.0,
                      umbral_bf: float = 0.05,
                      now: Optional[datetime.datetime] = None,
                      hmac_key: str = DEFAULT_HMAC_KEY,
                      opa_dir: Optional[str] = None,
                      opa_bin: Optional[str] = None,
                      agent_id: str = "agente",
                      engine: str = "auto",          # "auto" | "opa" | "python"
                      ultima_actualizacion: Optional[datetime.datetime] = None,
                      solicitudes_dd: int = 0,
                      ultimo_ros_ts: Optional[int] = None,
                      ultimo_aros_ts: Optional[int] = None,
                      trimestre: str = "2026-T3",
                      denuncias_periodo: int = 0,
                      monitoreo_canal: bool = True,
                      periodo: str = "2026-T3",
                      ) -> ResultadoPipeline:
    """Ejecuta la cadena completa de cumplimiento para una operación."""
    now = _hoy(now)
    eventos: list = []
    usar_opa = (engine != "python") and bool(opa_dir)

    # 1 — Operación (entrada) + régimen (2)
    if registro is not None:
        cl = clasificar_regimen(registro.ingresos, registro.activos, registro.sector)
        regimen, fundamento = cl.regimen, cl.fundamento
    else:
        regimen, fundamento = "no_obligado", "sin registro"

    # 3 — Screening (C03): a través de una o varias fuentes
    screening = "sin_consulta"
    consulta = None
    consultas_contraparte: Tuple[Tuple[str, ResultadoConsulta], ...] = tuple()
    fuentes_no_disponibles: Tuple[str, ...] = tuple()

    def _screening_multifuente(sujeto, fuentes):
        """Devuelve (resultados, fuentes_no_disponibles). No consulta contra fixtures sintéticos."""
        resul = []
        no_disp = []
        for f in sorted(fuentes):
            item = fuentes[f]
            regs, lv, lh = item[0], item[1], item[2]
            estado = item[3] if len(item) > 3 else "OPERATIVA"
            if estado == "SYNTHETIC_TEST_FIXTURE":
                no_disp.append(f)
                continue
            r = consultar(sujeto, regs, f, lv, lh)
            resul.append((f, r))
        return tuple(resul), tuple(no_disp)

    def _peor(resul):
        if any(r[1].resultado == "coincidencia" for r in resul):
            return "coincidencia"
        if any(r[1].resultado == "candidato" for r in resul):
            return "candidato"
        if any(r[1].resultado == "revisionManual" for r in resul):
            return "revisionManual"
        return "sinCoincidencia"

    if listas_por_fuente:
        consultas_contraparte, fuentes_no_disponibles = _screening_multifuente(contraparte, listas_por_fuente)
        screening = _peor(consultas_contraparte) if consultas_contraparte else "sin_consulta"
        consulta = consultas_contraparte[0][1] if consultas_contraparte else None
    elif registros_lista:
        consulta = consultar(contraparte, registros_lista, lista_fuente, lista_version, lista_hash)
        screening = consulta.resultado
        consultas_contraparte = ((lista_fuente, consulta),)

    # 4 — Beneficiario final (C02)
    bf = tuple()
    if registro is not None:
        bf = derivar_beneficiario_final(registro, umbral=umbral_bf)

    # 4b — Screening de beneficiarios finales (personas naturales, 9.17)
    bf_resultados = tuple()
    bf_coincidencia = False
    fuentes_bf = listas_por_fuente or ({lista_fuente: (registros_lista, lista_version, lista_hash, "OPERATIVA")}
                                       if registros_lista else {})
    if fuentes_bf and bf:
        resul = []
        for b in bf:
            if not b.nombre:
                continue
            bcp = Contraparte("bf-" + b.nombre, "natural", b.nombre, b.tipo_documento, b.numero_documento)
            rc, nd = _screening_multifuente(bcp, fuentes_bf)
            fuentes_no_disponibles = tuple(sorted(set(fuentes_no_disponibles) | set(nd)))
            for f, r in rc:
                resul.append((b.nombre, f, r))
                if r.resultado == "coincidencia":
                    bf_coincidencia = True
        bf_resultados = tuple(resul)
    screening_completo = not fuentes_no_disponibles

    # 6 — Señales (C09)
    senales = tuple(s for s in operacion.get("senales", ()) if s in catalogo_senales)

    # 8 — Detección (C06): inusual / requiere_analisis
    monto = operacion.get("monto", 0.0)
    inusual = monto > patron_normal * (umbral_deteccion or 1.0)
    requiere_analisis = bool(inusual and senales)

    # 5 — Matriz / perfil (C04)
    es_pep = bool(operacion.get("esPEP", False))
    factores = []
    if screening == "coincidencia" or bf_coincidencia:
        factores.append("coincidencia_lista")
    elif screening == "candidato":
        factores.append("candidato_lista")   # probable, requiere revisión humana (Fase 1)
    elif screening == "revisionManual":
        factores.append("revision_manual_lista")
    if bf:
        factores.append("beneficiario_final")
    if senales:
        factores.append("senal_registrada")
    if inusual:
        factores.append("operacion_inusual")
    if es_pep:
        factores.append("pep")
    if regimen == "pleno_reforzado":
        factores.append("sector_reforzado")
    es_alto = (screening in ("coincidencia", "candidato") or bf_coincidencia or bool(senales)
               or inusual or es_pep or regimen == "pleno_reforzado")
    perfil = "alto" if es_alto else ("medio" if regimen != "no_obligado" else "bajo")

    # 7 — DD (C05) calendario
    periodo_requerido = 365 if perfil == "alto" else 730
    dd_vencida = False
    dd_inmediata = bool(senales)
    dd_exceso = bool(perfil == "bajo" and solicitudes_dd > 3)
    if ultima_actualizacion is not None:
        dias = (now - ultima_actualizacion).total_seconds() / 86400
        dd_vencida = dias > periodo_requerido

    # 9 — ROS/AROS (C07/C08) simetría del silencio
    aros_requerido = False
    ausencia_denuncias = bool(denuncias_periodo == 0 and monitoreo_canal)
    if ultimo_ros_ts is not None and ultimo_aros_ts is not None:
        dias_ros = (now.timestamp() - ultimo_ros_ts) / 86400
        aros_requerido = dias_ros > 90 and (now.timestamp() - ultimo_aros_ts) > 80 * 86400

    # Input OPA único, reutilizado por todos los bundes
    ultima_actualizacion_ts = _epoch(ultima_actualizacion) if ultima_actualizacion is not None else None
    opa_input = _build_opa_input(
        contraparte, operacion, registro, screening, consulta, perfil, factores, senales,
        now=now, agent_id=agent_id, ultima_actualizacion_ts=ultima_actualizacion_ts,
        solicitudes_dd=solicitudes_dd, ultimo_ros_ts=ultimo_ros_ts, ultimo_aros_ts=ultimo_aros_ts,
        trimestre=trimestre, denuncias_periodo=denuncias_periodo,
        monitoreo_canal=monitoreo_canal, periodo=periodo)

    campos_cp = _campos_contraparte(contraparte, operacion)
    cp_ok = _contraparte_ok(campos_cp)

    def _emitir(control_id, event_type, payload, *, bundle_query=None, at_type="LOG", tier="Tier2"):
        ev = None
        if usar_opa and bundle_query:
            ev_opa = opaclient.evaluar(bundle_query, opa_dir, opa_input, opa_bin)
            if isinstance(ev_opa, dict) and ev_opa.get("payload"):
                ev = build_event(
                    ev_opa.get("controlId", control_id),
                    ev_opa["payload"].get("eventType", event_type),
                    ev_opa.get("agentId", agent_id), ev_opa["payload"], now=now,
                    at_type=ev_opa.get("@type", at_type),
                    retention_tier=ev_opa.get("retentionTier", tier), hmac_key=hmac_key)
        if ev is None:
            ev = build_event(control_id, event_type, agent_id, payload, now=now,
                             at_type=at_type, retention_tier=tier, hmac_key=hmac_key)
        eventos.append(ev)
        return ev

    # C01 — Contraparte (si campos completos)
    if cp_ok:
        _emitir("SAG-C01", "CONTRAPARTE_CREADA",
                {"contraparteId": contraparte.contraparte_id, "camposCompletos": True,
                 "esContraparteInterna": campos_cp["esContraparteInterna"]},
                bundle_query="data.arhia.sag.contraparte.evidence")

    # C03 — Screening (una emisión por fuente de la contraparte)
    for f, con in consultas_contraparte:
        _emitir("SAG-C03", "LISTA_CONSULTADA",
                {"contraparteId": contraparte.contraparte_id, "lista": con.lista,
                 "listaVersion": con.lista_version, "listaHash": con.lista_hash,
                 "resultado": con.resultado},
                bundle_query="data.arhia.sag.screening.evidence")

    # C03 — Screening por beneficiario final (por fuente)
    for nombre, f, r in bf_resultados:
        _emitir("SAG-C03", "LISTA_CONSULTADA",
                {"contraparteId": contraparte.contraparte_id, "sujeto": nombre,
                 "lista": r.lista, "listaVersion": r.lista_version, "listaHash": r.lista_hash,
                 "resultado": r.resultado})

    # C02 — Beneficiario final
    if bf:
        bf_nombres = ";".join(b.nombre for b in bf) if any(b.nombre for b in bf) else "LIMITACION"
        _emitir("SAG-C02", "BENEFICIARIO_FINAL_REGISTRADO",
                {"contraparteId": contraparte.contraparte_id, "beneficiarioFinalId": bf_nombres},
                bundle_query="data.arhia.sag.bf.evidence")

    # C04 — Matriz / perfil
    _emitir("SAG-C04", "PERFIL_ASIGNADO",
            {"contraparteId": contraparte.contraparte_id, "perfil": perfil, "factores": list(factores)},
            bundle_query="data.arhia.sag.matriz.evidence")

    # C09 — Señales (una por señal conocida)
    for s in senales:
        _emitir("SAG-C09", "SENAL_REGISTRADA",
                {"operacionId": operacion.get("operacionId", ""), "senal": s},
                bundle_query="data.arhia.sag.senales.evidence")

    # C05 — DD actualización requerida
    if dd_vencida or dd_inmediata or dd_exceso:
        _emitir("SAG-C05", "DD_ACTUALIZACION_REQUERIDA",
                {"contraparteId": contraparte.contraparte_id, "perfil": perfil,
                 "ddVencida": dd_vencida, "inmediataRequerida": dd_inmediata, "excesoDD": dd_exceso},
                bundle_query="data.arhia.sag.dd.evidence")

    # C07/C08 — ROS/AROS + ausencia de denuncias
    if aros_requerido:
        _emitir("SAG-C07", "AROS_REQUERIDO",
                {"trimestre": trimestre, "diasDesdeUltimoRos": round((now.timestamp() - (ultimo_ros_ts or 0)) / 86400, 1)},
                bundle_query="data.arhia.sag.silence.evidence_aros")
    if ausencia_denuncias:
        _emitir("SAG-C08", "AUSENCIA_DENUNCIAS_DETECTADA",
                {"periodo": periodo, "resultado": "sinDenuncias"},
                bundle_query="data.arhia.sag.silence.evidence_canal")

    # 10 — Corredor de caso (si inusual): el motor SOLO alerta y abre el caso. La calificación como
    #     sospechosa y la decisión de reportar exigen análisis humano firmado (P0-2). No se auto-confirma
    #     ni se prepara ROS automáticamente.
    caso_id = caso_estado = None
    caso_historial: Tuple[dict, ...] = tuple()
    if inusual:
        _emitir("SAG-C06", "ALERTA_GENERADA",
                {"contraparteId": contraparte.contraparte_id,
                 "operacionId": operacion.get("operacionId", ""), "tipo": "inusual",
                 "requiereAnalisis": requiere_analisis})
        caso = CasoLAFT(f"Caso-{operacion.get('operacionId', contraparte.contraparte_id)}",
                        contraparte.contraparte_id, operacion.get("operacionId", ""), now=now)
        caso_id = caso.id
        ev = caso.transicion("CASO_ABIERTO", "agente", {"analista": "oficial_cumplimiento"}, now=now, hmac_key=hmac_key)
        eventos.append(ev)
        caso_estado = "REQUIERE_ANALISIS_HUMANO"
        caso_historial = tuple(dict(e) for e in caso.historial)

    # 11 — Reporte
    screening_por_fuente = tuple(
        {"fuente": f, "lista": c.lista, "listaVersion": c.lista_version,
         "listaHash": c.lista_hash, "resultado": c.resultado}
        for f, c in consultas_contraparte)
    return ResultadoPipeline(
        contraparte_id=contraparte.contraparte_id, nombre=contraparte.nombre, tipo=contraparte.tipo,
        regimen=regimen, fundamento_regimen=fundamento, screening=screening, screening_detalle=consulta,
        screening_por_fuente=screening_por_fuente,
        fuentes_no_disponibles=fuentes_no_disponibles, screening_completo=screening_completo,
        beneficiarios_finales=bf, bf_resultados=bf_resultados, bf_coincidencia=bf_coincidencia,
        perfil=perfil, factores=tuple(factores), senales=senales,
        dd_vencida=dd_vencida, dd_inmediata=dd_inmediata, dd_exceso=dd_exceso,
        operacion_inusual=inusual, requiere_analisis=requiere_analisis,
        aros_requerido=aros_requerido, ausencia_denuncias=ausencia_denuncias,
        contraparte_ok=cp_ok, caso_id=caso_id, caso_estado=caso_estado, caso_historial=caso_historial,
        eventos=tuple(eventos))

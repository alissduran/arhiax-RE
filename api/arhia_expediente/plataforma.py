"""Integrador de la plataforma: produce el Dictamen Completo.

Une la cadena completa en un solo punto de entrada:
    1) Título (arhia_title): identidad, cronología, titularidad, gravámenes, precio, pagos.
    2) Cumplimiento (arhia_sag_screen.pipeline): SAGRILAFT+PTEE de la contraparte
       (régimen, screening, beneficiario final, perfil, señales, DD, detección, ROS/AROS).
    3) Expediente de Confianza (arhia_expediente): unifica hallazgos + integridad.
    4) Conclusión profesional (simulada) + dictamen (Markdown/HTML).

Todo queda como evidencia trazable (envelope B18 + hmacChain) para el 9.22.
"""
import datetime
import html
from dataclasses import dataclass, replace
from typing import Optional, Tuple

from arhia_title.contracts import Anotacion, Avaluo, Caso, Pago, Parte, Predio
from arhia_title.rules import ejecutar as ejecutar_titulos
from arhia_sag_screen.contracts import Accionista, Contraparte, RegistroJuridico, RegistroNormalizado
from arhia_sag_screen.pipeline import ResultadoPipeline, ejecutar_pipeline
from arhia_sag_screen.evidence.envelope import build_event
from arhia_sag_screen.ingest.siis import buscar_por_nit
from arhia_sag_screen.ingest.listas import obtener_listas
from arhia_sag_screen.kyb.beneficiario_final import reporte_rub
from arhia_sag_screen.kyb.ptee import evaluar_ptee, FichaPtee
from arhia_sag_screen.kyb.uso_suelo import analizar_uso_suelo, FichaUsoSuelo
from arhia_sag_screen.kyb.identidad import conciliar_identidad, FichaIdentidad
from arhia_sag_screen.kyb.mensaje_ciudadano import construir_mensaje_ciudadano, MensajeCiudadano
from arhia_sag_screen.kyb.portabilidad import generar_paquete_portable, PaquetePortable, registrar_consentimiento, Consentimiento
from arhia_expediente.expediente import Expediente, FichaIntegridad, construir as construir_expediente
from arhia_expediente.conclusion import Conclusion, concluir
from arhia_expediente.evidencia_autoritativa import LibroEvidenciaAutoridad
from arhia_expediente.flujo_cierre import construir_flujo, FlujoCierre
from arhia_title.derechos import construir_capas, MapaDerechos
from arhia_title.comparables import analizar_con_comparables, AnalisisComparables, Comparable

CATALOGO_SENALES = ("pagoPorTercero", "pagoFraccionado")

_REGIMEN_CORTO = {"pleno_general": "pleno", "pleno_reforzado": "pleno",
                  "rmm": "rmm", "no_obligado": "no_obligado"}


@dataclass(frozen=True)
class DictamenCompleto:
    caso: Caso
    integridad: FichaIntegridad
    expediente: Expediente
    conclusion: Conclusion
    compliance_eventos: Tuple[dict, ...]
    rub_reporte: Tuple[dict, ...] = ()
    ficha_ptee: Optional[FichaPtee] = None
    ptee_eventos: Tuple[dict, ...] = ()
    ficha_uso_suelo: Optional[FichaUsoSuelo] = None
    ficha_identidad: Optional[FichaIdentidad] = None
    mensaje_ciudadano: Optional[MensajeCiudadano] = None
    paquete_portable: Optional[PaquetePortable] = None
    # XN (skills 1 y 2): capa científica/patentométrica del MVP mejorado.
    libro_autoridad: Optional[LibroEvidenciaAutoridad] = None
    mapa_derechos: Optional[MapaDerechos] = None
    flujo_cierre: Optional[FlujoCierre] = None
    analisis_comparables: Optional[AnalisisComparables] = None
    consentimiento: Optional[Consentimiento] = None


def _partes_por_rol(caso: Caso):
    return {p.rol: p for p in caso.partes}


def _contraparte_de_parte(parte: Parte) -> Contraparte:
    doc_t = parte.tipo_documento or "nit"
    return Contraparte(f"{parte.rol}-{parte.numero_documento or parte.nombre}", "juridica",
                       parte.nombre, doc_t, parte.numero_documento)


def _ptee_eventos(contraparte, ficha, *, now, hmac_key):
    """Eventos de evidencia del PTEE (canal + matriz + señales + DD ampliada)."""
    if ficha is None:
        return ()
    cid = contraparte.contraparte_id if contraparte is not None else ""
    evs = []

    def e(control, event_type, payload, at_type="LOG", tier="Tier2"):
        evs.append(build_event(control, event_type, "agente", payload, now=now,
                               at_type=at_type, retention_tier=tier, hmac_key=hmac_key))

    e("PTEE-C01", "PTEE_MATRIZ_RIESGO", {"contraparteId": cid, "riesgo": ficha.riesgo_corrupcion,
                                         "factores": list(ficha.factores), "base": ficha.base}, at_type="ATT")
    if ficha.diligencia_ampliada:
        e("PTEE-C02", "PTEE_DD_AMPLIADA", {"contraparteId": cid, "motivo": "riesgo_alto_corrupcion"})
    for s in ficha.senales:
        e("PTEE-C03", "PTEE_SENAL_REGISTRADA", {"contraparteId": cid, "senal": s})
    if ficha.canal_denuncias == "con_denuncia" and ficha.denuncias:
        for d in ficha.denuncias:
            e("PTEE-C04", "DENUNCIA_REGISTRADA", {"contraparteId": cid, "denunciaId": d.id,
                                                  "categoria": d.categoria, "anonima": d.anonima})
    else:
        e("PTEE-C04", "PTEE_CANAL_DENUNCIAS", {"contraparteId": cid, "estado": ficha.canal_denuncias})
    return tuple(evs)


def _registro_para_parte(parte: Parte, siis_path, accionistas, representante, caso_tipo) -> Optional[RegistroJuridico]:
    """Registro de la contraparte: prioriza el dato explícito, luego el auto-cruce SIIS por NIT."""
    if siis_path:
        reg = buscar_por_nit(siis_path, parte.numero_documento)
        if reg is not None:
            return RegistroJuridico(nit=reg.nit, razon_social=reg.razon_social or parte.nombre,
                                    sector=reg.sector or "inmobiliario", ingresos=reg.ingresos,
                                    activos=reg.activos, vigilada_por=reg.vigilada_por, fuente=reg.fuente,
                                    representante_legal=representante or reg.representante_legal,
                                    composicion_accionaria=tuple(accionistas))
    if caso_tipo == "informe_base":
        return None
    return RegistroJuridico(nit=parte.numero_documento or "N/A", razon_social=parte.nombre,
                            sector="inmobiliario", representante_legal=representante,
                            composicion_accionaria=tuple(accionistas))


def _senales_desde_caso(caso: Caso) -> Tuple[str, ...]:
    s = []
    if any(p.es_tercero for p in caso.pagos):
        s.append("pagoPorTercero")
    if len(caso.pagos) > 1:
        s.append("pagoFraccionado")
    return tuple(s)


def _ficha_desde_pipeline(res: ResultadoPipeline) -> FichaIntegridad:
    screening_map = {"sinCoincidencia": "ok", "coincidencia": "coincidencia",
                     "candidato": "revisionManual", "revisionManual": "revisionManual",
                     "sin_consulta": "pendiente"}
    bf_nombres = "; ".join(b.nombre for b in res.beneficiarios_finales if b.nombre)
    sarlaft = "verificado" if res.screening != "sin_consulta" else "pendiente"
    return FichaIntegridad(
        screening=screening_map.get(res.screening, "pendiente"),
        beneficiario_final=bf_nombres,
        regimen=_REGIMEN_CORTO.get(res.regimen, res.regimen),
        sarlaft=sarlaft,
        perfil=res.perfil,
        senales=res.senales,
        operacion_inusual=res.operacion_inusual,
        requiere_analisis=res.requiere_analisis,
        dd_requerida=bool(res.dd_vencida or res.dd_inmediata or res.dd_exceso),
        bf_coincidencia=res.bf_coincidencia,
        bf_resultados=res.bf_resultados,
        screening_por_fuente=res.screening_por_fuente,
        screening_completo=res.screening_completo,
        fuentes_no_disponibles=res.fuentes_no_disponibles,
        eventos=res.eventos,
    )


def ejecutar_plataforma(caso: Caso, *,
                        rol_contraparte: str = "",
                        registro_contraparte: Optional[RegistroJuridico] = None,
                        siis_path: Optional[str] = None,
                        accionistas: tuple = (),
                        representante_legal: str = "",
                        rub_sociedades: dict = (),
                        rub_fecha: str = "",
                        rub_pais: str = "",
                        senales_ptee: tuple = (),
                        es_funcionario_publico: bool = False,
                        usa_intermediario: bool = False,
                        licencia_autorizacion: bool = False,
                        canal_denuncias: bool = True,
                        denuncias_ptee: tuple = (),
                        zona_predio: str = "",
                        actividad_predio: str = "",
                        mapeo_zonas: dict = (),
                        receptor_institucional: str = "banco",
                        entidad_institucional_nit: str = "",
                        entidad_institucional_nombre: str = "",
                        comparables: tuple = (),   # XN-3: inmuebles comparables para coherencia precio–avalúo
                        registros_lista: tuple = (),
                        fuentes_activas: tuple = (),   # fuentes SARLAFT (onu, ofac, uiaf, ue, uk, pep, interpol)
                        lista_fuente: str = "onu",
                        lista_version: str = "2026-09-01",
                        lista_hash: str = "hash-seed",
                        catalogo_senales: tuple = CATALOGO_SENALES,
                        patron_normal: Optional[float] = None,
                        umbral_deteccion: float = 2.0,
                        umbral_bf: float = 0.05,
                        now: Optional[datetime.datetime] = None,
                        hmac_key: str = "",
                        opa_dir: Optional[str] = None,
                        opa_bin: Optional[str] = None,
                        engine: str = "auto",
                        ultima_actualizacion: Optional[datetime.datetime] = None,
                        solicitudes_dd: int = 0,
                        ultimo_ros_ts: Optional[int] = None,
                        ultimo_aros_ts: Optional[int] = None,
                        trimestre: str = "2026-T3",
                        denuncias_periodo: int = 0,
                        monitoreo_canal: bool = True,
                        periodo: str = "2026-T3",
                        ) -> DictamenCompleto:
    """Produce el Dictamen Completo integrando título + SAGRILAFT + expediente + conclusión."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    partes = _partes_por_rol(caso)

    # 1) Título
    hallazgos_titulo = list(ejecutar_titulos(caso))

    # 2) Cumplimiento SAGRILAFT de la contraparte (por defecto: parte jurídica de la operación)
    rol = rol_contraparte
    if not rol:
        rol = ("comprador" if "comprador" in partes else
               ("vendedor" if "vendedor" in partes else (tuple(partes)[0] if partes else "")))
    parte = partes.get(rol)
    contraparte = registro = None
    compliance_eventos: Tuple[dict, ...] = tuple()
    operacion = {"operacionId": caso.id}
    if parte is not None:
        contraparte = _contraparte_de_parte(parte)
        registro = (registro_contraparte
                    if registro_contraparte is not None
                    else _registro_para_parte(parte, siis_path, accionistas, representante_legal, caso.tipo))
        monto = caso.precio_pactado or (caso.avaluo.valor if caso.avaluo else 0)
        patron = patron_normal if patron_normal is not None else (monto if monto else 1.0)
        operacion = {
            "operacionId": caso.id,
            "monto": monto,
            "patronNormal": patron,
            "senales": _senales_desde_caso(caso),
            "domicilio": caso.predio.direccion,
            "beneficiarioFinal": "SI" if (registro and any(a.participacion >= umbral_bf for a in registro.composicion_accionaria)) else "NO",
            "representanteLegal": (registro.representante_legal or "") if registro else "",
            "personaContacto": parte.nombre,
            "cargo": rol,
            "fechaConocimiento": now.date().isoformat(),
            "esContraparteInterna": False,
        }
        # Multi-fuente SARLAFT: si se activan fuentes, se resuelven (live->muestra) y se
        # screeninga contra todas; si no, se usa `registros_lista` (fuente única).
        listas_por_fuente = {}
        if fuentes_activas:
            for f, (lista, regs) in obtener_listas(fuentes_activas).items():
                listas_por_fuente[f] = (regs, lista.version, lista.hash, lista.estado)
        res = ejecutar_pipeline(contraparte, operacion,
                                registro=registro,
                                registros_lista=() if listas_por_fuente else registros_lista,
                                listas_por_fuente=listas_por_fuente,
                                lista_fuente=lista_fuente, lista_version=lista_version, lista_hash=lista_hash,
                                catalogo_senales=catalogo_senales,
                                patron_normal=patron, umbral_deteccion=umbral_deteccion,
                                umbral_bf=umbral_bf, now=now, hmac_key=hmac_key,
                                opa_dir=opa_dir, opa_bin=opa_bin, engine=engine,
                                ultima_actualizacion=ultima_actualizacion, solicitudes_dd=solicitudes_dd,
                                ultimo_ros_ts=ultimo_ros_ts, ultimo_aros_ts=ultimo_aros_ts,
                                trimestre=trimestre, denuncias_periodo=denuncias_periodo,
                                monitoreo_canal=monitoreo_canal, periodo=periodo)
        compliance_eventos = res.eventos
        integridad = _ficha_desde_pipeline(res)
    else:
        integridad = FichaIntegridad()

    # 3) Expediente (título + integridad)
    exp = construir_expediente(caso, integridad)

    # 4) Conclusión profesional (simulada) + PTEE (corrupción/soborno)
    ficha_ptee = None
    ptee_eventos: Tuple[dict, ...] = tuple()
    if integridad.regimen or contraparte is not None:
        op_ptee = dict(operacion)
        op_ptee.update({
            "senalesPTEE": tuple(senales_ptee),
            "esFuncionarioPublico": es_funcionario_publico,
            "usaIntermediario": usa_intermediario,
            "licenciaAutorizacion": licencia_autorizacion,
            "canalDenuncias": canal_denuncias,
            "sector": (registro.sector if registro else ""),
        })
        ficha_ptee = evaluar_ptee(contraparte, op_ptee, denuncias=denuncias_ptee)
        ptee_eventos = _ptee_eventos(contraparte, ficha_ptee, now=now, hmac_key=hmac_key)
    # Análisis de uso del suelo / polígono POT (qué se puede / no se puede hacer)
    ficha_uso_suelo = None
    if zona_predio or mapeo_zonas:
        ficha_uso_suelo = analizar_uso_suelo(caso.predio, actividad_predio,
                                             zona=(zona_predio or None),
                                             mapeo=(dict(mapeo_zonas) if mapeo_zonas else None))
    conclusion = concluir(exp, integridad, ficha_ptee=ficha_ptee, ficha_uso_suelo=ficha_uso_suelo)

    # 5) Reporte RUB de beneficiarios finales (estructura del Registro Único)
    rub_reporte = tuple()
    if registro is not None:
        rub_reporte = tuple(reporte_rub(registro, sociedades=rub_sociedades,
                                        fecha=rub_fecha, pais=rub_pais))

    d = DictamenCompleto(caso=caso, integridad=integridad, expediente=exp,
                         conclusion=conclusion, compliance_eventos=compliance_eventos,
                         rub_reporte=rub_reporte, ficha_ptee=ficha_ptee,
                         ptee_eventos=ptee_eventos, ficha_uso_suelo=ficha_uso_suelo)
    # Conciliación de identidad (PD-007) + salida ciudadana (PD-009)
    d = replace(d, ficha_identidad=conciliar_identidad(caso, registro))
    d = replace(d, mensaje_ciudadano=construir_mensaje_ciudadano(d.expediente, d.integridad, d.conclusion, d.ficha_uso_suelo))
    # XN-5 — consentimiento auditado (evento) del ciudadano para el paquete institucional
    comprador_p = partes.get("comprador")
    cons = None
    if comprador_p and comprador_p.nombre:
        cons = registrar_consentimiento(comprador_p.nombre, "transferir evidencia del expediente",
                                        ahora=now, hmac_key=(hmac_key or None))
    d = replace(d, paquete_portable=generar_paquete_portable(
        d.expediente, d.integridad, d.conclusion, d.rub_reporte, d.ficha_uso_suelo,
        consentimiento=cons,
        entidad_nit=entidad_institucional_nit or (contraparte.contraparte_id if contraparte else ""),
        entidad_nombre=entidad_institucional_nombre or (contraparte.nombre if contraparte else ""),
        receptor=receptor_institucional))
    # XN (skills 1 y 2): capas de derechos (F-A), coherencia precio–avalúo con comparables (F-C),
    # flujo de cierre (F-E) y núcleo de evidencia autoritativa (F-G).
    d = replace(d, mapa_derechos=construir_capas(caso),
                analisis_comparables=analizar_con_comparables(
                    caso.precio_pactado, (caso.predio.area_registral or caso.predio.area_catastral),
                    tuple(comparables)),
                flujo_cierre=construir_flujo(caso.id),
                libro_autoridad=LibroEvidenciaAutoridad(hmac_key=(hmac_key or None), now=now),
                consentimiento=cons)
    return d


def _respuestas_preguntas(d: DictamenCompleto) -> dict:
    """Respuestas de las 5 preguntas del Expediente de Confianza."""
    partes = "; ".join(f"{p.rol}: {p.nombre}" for p in d.caso.partes) or d.caso.titular or "—"
    bf = d.integridad.beneficiario_final or "por verificar"
    grav = [h for h in d.expediente.hallazgos if "gravamen" in h.titulo.lower() and h.estado in ("RIESGO", "OBSERVACION")]
    val = next((h for h in d.expediente.hallazgos if h.regla == "VAL_B01"), None)
    pag = "; ".join(f"{p.monto:,.0f} {p.medio} por {p.pagador}{' (tercero)' if p.es_tercero else ''}"
                    for p in d.caso.pagos) or "sin pagos registrados"
    p2 = f"{d.caso.predio.folio_matricula} · catastro {d.caso.predio.codigo_catastral} · {d.caso.predio.direccion}. "
    p2 += ("Restricción: " + grav[0].titulo + ".") if grav else "Sin gravámenes vigentes detectados."
    p3 = f"Avalúo {d.caso.avaluo.valor:,.0f} · precio pactado {d.caso.precio_pactado:,.0f}." if d.caso.avaluo else "Sin avalúo documentado."
    p3 += " " + (val.descripcion if val else "Coherencia no evaluada.")
    return {
        "P1": f"Intervienen: {partes}. Se beneficia realmente: {bf}.",
        "P2": p2,
        "P3": p3,
        "P4": f"Pagó: {pag}.",
        "P5": ("Veredicto: " + d.conclusion.veredicto + " — suscrito por "
               + ", ".join(f"{f['rol']} ({f['matricula']})" for f in d.conclusion.firmantes) + "."),
    }


def generar_dictamen_markdown(d: DictamenCompleto) -> str:
    L = []
    a = L.append
    a("# DEMOSTRADOR TÉCNICO DE PREANÁLISIS · Expediente de Confianza Precontractual (OPA)")
    a("")
    a("> **DATOS SINTÉTICOS — NO USAR PARA DECIDIR.** Este es un demostrador técnico de "
      "preanálisis con datos de prueba. No constituye dictamen, cumplimiento, SIREL-compatible "
      "ni expediente operable. Las conclusiones las emite el profesional competente.")
    a("")
    a(f"**Caso:** {d.caso.id} · **Tipo:** {d.caso.tipo} · **Preanálisis integrado** (título + integridad SAGRILAFT/PTEE + valor + uso de suelo).")
    a("**Estado del preanálisis:** " + d.conclusion.veredicto)
    a("")
    a("**Las 5 preguntas del Expediente:**")
    for k, v in _respuestas_preguntas(d).items():
        a(f"- **{k}** — {v}")
    a("")
    a("**Índice:** 1. Resumen para el ciudadano · 2. Conclusión · 3. Inmueble y partes · 4. Cumplimiento SAGRILAFT+PTEE · 5. RUB · 6. POT · 7. Conciliación de identidad · 8. Autoría separada · 9. Hallazgos")
    a("")
    a("## 1. Resumen para el ciudadano")
    if d.mensaje_ciudadano:
        m = d.mensaje_ciudadano
        a("**Verificado:** " + ("; ".join(m.verificado) if m.verificado else "—"))
        a("**Por completar / en revisión:** " + ("; ".join(m.falta) if m.falta else "—"))
        a("**Riesgo detectado:** " + ("; ".join(m.riesgo) if m.riesgo else "sin riesgo relevante"))
        a("**Siguiente paso:** " + ("; ".join(m.proximo_paso) if m.proximo_paso else "proceder con la revisión del profesional."))
        a("")
        a("_" + m.lenguaje_plano + "_")
        a("")
        a("> **Aviso:** " + m.aviso)
        a("")
    a("## 2. Conclusión del profesional")
    a("**Veredicto:** " + d.conclusion.veredicto)
    a("")
    a("**Fundamento:** " + d.conclusion.fundamento)
    a("")
    if d.conclusion.riesgos_prioritarios:
        a("**Riesgos prioritarios:**")
        for r in d.conclusion.riesgos_prioritarios:
            a("- " + r)
        a("")
    if d.conclusion.observaciones:
        a("**Observaciones:**")
        for o in d.conclusion.observaciones:
            a("- " + o)
        a("")
    a("**Recomendaciones:**")
    for r in d.conclusion.recomendaciones:
        a("- " + r)
    a("")
    a("**Soporte de cumplimiento:** " + d.conclusion.soporte_compliance)
    a("")
    a("**Autoría:** el sistema solo produce el preanálisis (determinista). La conclusión, el concepto "
      "de valor y la decisión de cumplimiento NO están firmados: los emite el profesional competente "
      "(abogado / avaluador RAA / oficial de cumplimiento). Este demostrador no simula firmas.")
    a("")
    a("## 3. Inmueble y partes")
    p = d.caso.predio
    a(f"- Folio: {p.folio_matricula} · Catastro: {p.codigo_catastral} · Dir: {p.direccion}")
    if p.area_registral:
        a(f"- Área registral: {p.area_registral} m² · catastral: {p.area_catastral} m²")
    for pp in d.caso.partes:
        a(f"- {pp.rol}: {pp.nombre}")
    a("")
    a("## 4. Cumplimiento SAGRILAFT+PTEE")
    i = d.integridad
    a(f"- Régimen: {i.regimen} · Screening (agregado): {i.screening} · BF: {i.beneficiario_final or '—'}")
    a(f"- Perfil: {i.perfil} · Señales: {list(i.senales)} · Inusual: {i.operacion_inusual} · DD requerida: {i.dd_requerida}")
    if i.fuentes_no_disponibles:
        a(f"- **Fuentes NO disponibles (screening incompleto):** {', '.join(i.fuentes_no_disponibles)} — el expediente queda incompleto.")
    if i.screening_por_fuente:
        a("- Screening por fuente:")
        a("  | Fuente | Resultado | Versión |")
        a("  |---|---|---|")
        for s in i.screening_por_fuente:
            a(f"  | {s.get('fuente')} | {s.get('resultado')} | {s.get('listaVersion')} |")
    if d.compliance_eventos:
        a("- Eventos de evidencia (envelope B18 + hmacChain):")
        for e in d.compliance_eventos:
            a(f"  - [{e.get('controlId')}] {e.get('eventType')} · hmacChain={bool(e.get('hmacChain'))}")
    a("")
    a("## 5. Registro Único de Beneficiarios Finales (RUB)")
    if d.rub_reporte:
        a("| Criterio | Identificación | Nombre | % | Vínculo | Calidad | Base legal |")
        a("|---|---|---|---|---|---|---|")
        for r in d.rub_reporte:
            a(f"| {r.get('criterio')} | {r.get('tipo_documento')} {r.get('numero_documento')} | "
              f"{r.get('nombre')} | {r.get('participacion')*100:.0f}% | {r.get('vinculo')} | "
              f"{r.get('calidad')} | {r.get('base_legal')} |")
    else:
        a("- Sin beneficiarios finales reportados.")
    a("")
    a("## 6. Riesgo de corrupción / soborno — PTEE (Ley 1778)")
    if d.ficha_ptee:
        p = d.ficha_ptee
        a(f"- Riesgo de corrupción: **{p.riesgo_corrupcion}** · Funcionario público: {p.funcionario_publico} · "
          f"Intermediario: {p.uso_intermediario} · DD ampliada: {p.diligencia_ampliada}")
        a(f"- Canal de denuncias: **{p.canal_denuncias}**")
        if p.factores:
            a("- Factores de riesgo: " + ", ".join(p.factores))
        if p.senales:
            a("- Señales PTEE: " + ", ".join(p.senales))
        if p.recomendaciones:
            a("- Recomendaciones:")
            for rec in p.recomendaciones:
                a(f"  - {rec}")
        if d.ptee_eventos:
            a("- Eventos de evidencia PTEE:")
            for e in d.ptee_eventos:
                a(f"  - [{e.get('controlId')}] {e.get('eventType')} · hmacChain={bool(e.get('hmacChain'))}")
    else:
        a("- Sin evaluación de corrupción.")
    a("")
    a("## 7. Uso de suelo / POLÍGONO del POT (qué se puede y qué no)")
    if d.ficha_uso_suelo and d.ficha_uso_suelo.zona != "no_mapeado":
        u = d.ficha_uso_suelo
        a(f"- Zona POT: **{u.zona} · {u.zona_nombre}** · Uso principal: {u.uso_principal}")
        a(f"- Usos permitidos: {', '.join(u.usos_permitidos)}")
        a(f"- Usos NO permitidos: {', '.join(u.usos_no_permitidos) if u.usos_no_permitidos else '—'}")
        if u.edificabilidad:
            a("- Edificabilidad: " + "; ".join(f"{e['indice']} {e['valor']}" for e in u.edificabilidad))
        if u.retiros:
            a(f"- Retiros: {u.retiros}")
        if u.restricciones:
            a(f"- Restricciones: {', '.join(u.restricciones)}")
        a(f"- Actividad consultada: **{u.actividad_consultada or '—'}** → **{u.actividad_resultado}**")
    else:
        a("- Sin mapa de zona POT (falta el polígono/código catastral) — verificar en la curaduría o planeación.")
    a("")
    a("## 8. Conciliación de identidad (PD-007)")
    if d.ficha_identidad:
        fi = d.ficha_identidad
        a(f"- Predio identificado: {fi.predio_identificado} · Áreas consistentes: {fi.areas_consistentes} · "
          f"Dirección: {fi.direccion_presente}")
        a(f"- Vendedor = titular: {fi.vendedor_es_titular} · Comprador identificado: {fi.comprador_identificado} · "
          f"BF identificado: {fi.bf_identificado}")
        a(f"- Conciliado: **{fi.conciliado}** · Discordancias escaladas: **{fi.escaladas}**")
        if fi.discordancias:
            a("- Discordancias:")
            for disc in fi.discordancias:
                a(f"  - {disc}")
    a("")
    a("## 9. Autoría separada (PD-003)")
    a("- **Producido por el sistema (determinista):** identificación, cronología, gravámenes, "
      "cumplimiento SAGRILAFT/PTEE, uso de suelo. Es un pre-análisis automático con fuente y regla.")
    a("- **Decidido y firmado por el profesional:** la conclusión y la firma.") 
    for f in d.conclusion.firmantes:
        a(f"  - *{f['rol']}* — {f['nombre']} (mat. {f['matricula']}) [{f['estado']}]")
    a("- **Regla de producto:** la tecnología prepara y señaliza; el profesional conserva la última palabra "
      "y la responsabilidad.")
    a("")
    a("## 10. Expediente institucional / sala de datos (PF-017)")
    if d.paquete_portable:
        pp = d.paquete_portable
        a(f"- Receptor: **{pp.receptor}** · Entidad: {pp.entidad_nombre} ({pp.entidad_nit})")
        a(f"- Campos reutilizables: {len(pp.campos_reutilizables)} · **% reutilizable: {pp.pct_reutilizable}%**")
        a(f"- Consentimiento: {pp.consentimiento} · Permisos: {', '.join(pp.permisos)}")
        a("- Campos:")
        for c in pp.campos_reutilizables:
            a(f"  - {c['campo']}: {c['valor']} ({c['fuente']})")
        a(f"- Procedencia (evidencia): {len(pp.evidencia_procedencia)} elementos")
        a("> " + pp.aviso)
    a("")
    a("## 11. Hallazgos del expediente")
    for h in d.expediente.hallazgos:
        a(f"### {h.id} · {h.titulo} — [{h.estado} · {h.severidad}]")
        if h.descripcion:
            a("- **Evidencia:** " + h.descripcion)
        if h.base_legal:
            a("- **Base legal:** " + h.base_legal)
        if h.implicacion:
            a("- **Implicación:** " + h.implicacion)
        if h.accion:
            a("- **Acción:** " + h.accion)
        a("- **Responsable:** " + h.responsable)
        a("")
    a("---")
    a("## Anexo A · Capa científica y patentométrica (soporte XN)")
    a("El MVP mejorado integra los elementos seleccionados del escaneo cienciométrico (clústeres A–D, "
      "elementos E1–E8) y del panorama de patentes (features F-A..F-H); ver `11_Diseno_Contribucion_Integrado.md`. "
      "Es una capa de **diseño de evidencia**, no una afirmación de desempeño.")
    a("")
    if d.mapa_derechos:
        md = d.mapa_derechos
        a("- **XN-4 · Derechos como capas temporales (F-A):** " + md.resumen)
        for c in md.vigentes:
            a(f"  - {c.tipo} (anot. {c.anotacion}) · severidad {c.severidad} · vigente desde {c.inicio}"
              + (f" · {c.detalle}" if c.detalle else ""))
    if d.analisis_comparables:
        ac = d.analisis_comparables
        a("- **XN-3 · Coherencia precio–avalúo–predio + comparables (F-C):** " + ac.motivo
          + (f" · Comparables: {len(ac.comparables)}" if ac.comparables else ""))
        if ac.escalar_a_avaluador:
            a("  - → **Escala al avaluador** (genera demanda de avalúo; ARHIAX no emite opinión de valor).")
    if d.flujo_cierre:
        fc = d.flujo_cierre
        a(f"- **XN-6 · Flujo de cierre (F-E):** progreso {fc.progreso:.0%} · cuello de botella: {fc.cuello_botella or 'ninguno'}")
        for et in fc.etapas:
            a(f"  - {et.nombre}: {et.estado} · responsable {et.responsable}")
    if d.libro_autoridad:
        la = d.libro_autoridad
        a(f"- **XN-1 · Núcleo de evidencia autoritativa (F-G):** {len(la.eventos())} evento(s) de autoridad; "
          f"la autoridad la ejerce el profesional, el sistema conserva la cadena inalterable.")
    if d.consentimiento:
        cons = d.consentimiento
        a(f"- **XN-5 · Consentimiento auditado (F-D):** {cons.quien} autorizó «{cons.que_autoriza}» "
          f"(base: {cons.base_juridica}) — evento firmado.")
    a("- **XN-8 · Integración (GATED):** conector SIREL/UIAF (`arhia_sag_screen/sirel`) construye y valida "
      "el sobre XML; el envío en vivo exige credenciales. Capas POT por polígono disponibles "
      "(`uso_suelo.poligonos`); el dataset POT real por polígono es GATED.")
    a("- **XN-9 · Gold standard (GATED):** harness `arhia_expediente/gold_standard` (FNR ≤2% / cobertura) "
      "listo; el corpus judicial real es GATED (protocolo `07_*`).")
    a("")
    a("---")
    a("_Dictamen generado por la plataforma ARHIAX (demo). La conclusión es simulada a partir de hallazgos objetivos; en un entorno productivo la suscribe el profesional competente con firma electrónica._")
    return "\n".join(L)


def generar_dictamen_html(d: DictamenCompleto) -> str:
    cards = []
    for h in d.expediente.hallazgos:
        piece = '<div class="exp"><b>' + _esc(h.id) + ' · ' + _esc(h.titulo) + ' [' + _esc(h.estado) + ' · ' + _esc(h.severidad) + ']</b>'
        if h.descripcion:
            piece += '<div>' + _esc(h.descripcion) + '</div>'
        if h.base_legal:
            piece += '<div><i>Base legal: ' + _esc(h.base_legal) + '</i></div>'
        if h.accion:
            piece += '<div><i>Acción: ' + _esc(h.accion) + '</i></div>'
        piece += '<div>Responsable: ' + _esc(h.responsable) + '</div></div>'
        cards.append(piece)
    events = []
    for e in d.compliance_eventos:
        events.append('<li>[' + _esc(e.get("controlId")) + '] ' + _esc(e.get("eventType"))
                      + ' · hmac=' + _esc(bool(e.get('hmacChain'))) + '</li>')
    firmas = []
    for f in d.conclusion.firmantes:
        firmas.append('<div class="exp"><b>' + _esc(f["rol"]) + '</b> — ' + _esc(f["nombre"])
                      + ' (mat. ' + _esc(f["matricula"]) + ') [' + _esc(f["estado"]) + ']'
                      + '<div><i>' + _esc(f["opinion"]) + '</i></div></div>')
    recs = []
    for r in d.conclusion.recomendaciones:
        recs.append('<li>' + _esc(r) + '</li>')

    body = []
    body.append('<h1>DEMOSTRADOR TÉCNICO DE PREANÁLISIS — ' + _esc(d.caso.id) + '</h1>')
    body.append('<p style="background:#ffe;border:1px solid #cc0;padding:8px 12px;border-radius:6px"><b>DATOS SINTÉTICOS — NO USAR PARA DECIDIR.</b> Demostrador de preanálisis; no dictamen, no cumplimiento, no SIREL-compatible, no expediente operable.</p>')
    body.append('<p><span class="tag">' + _esc(d.conclusion.veredicto) + '</span></p>')
    resp = _respuestas_preguntas(d)
    body.append('<h2>Las 5 preguntas</h2>')
    for k, v in resp.items():
        body.append('<div class="q"><b>' + k + '</b> ' + _esc(v) + '</div>')
    body.append('<h2>Conclusión profesional</h2><p>' + _esc(d.conclusion.fundamento) + '</p>')
    body.append('<h3>Recomendaciones</h3><ul>' + "".join(recs) + '</ul>')
    body.append('<h3>Autoría</h3><p>El sistema solo produce el preanálisis (determinista). La conclusión y la firma las emite el profesional competente; este demostrador no simula firmas.</p>')
    body.append('<h2>Cumplimiento SAGRILAFT+PTEE</h2>')
    body.append('<p>Régimen: ' + _esc(d.integridad.regimen) + ' · Screening: ' + _esc(d.integridad.screening)
                + ' · BF: ' + _esc(d.integridad.beneficiario_final or '—') + ' · Perfil: ' + _esc(d.integridad.perfil) + '</p>')
    body.append('<ul>' + "".join(events) + '</ul>')
    filas = []
    for r in d.rub_reporte:
        filas.append('<tr><td>' + _esc(r.get("criterio")) + '</td><td>' + _esc(r.get("tipo_documento"))
                     + ' ' + _esc(r.get("numero_documento")) + '</td><td>' + _esc(r.get("nombre"))
                     + '</td><td>' + _esc(r.get("participacion")*100) + '%</td><td>' + _esc(r.get("vinculo"))
                     + '</td><td>' + _esc(r.get("calidad")) + '</td><td>' + _esc(r.get("base_legal")) + '</td></tr>')
    body.append('<h2>Registro Único de Beneficiarios Finales (RUB)</h2>')
    body.append('<table border="1" cellspacing="0" cellpadding="4"><tr><th>Criterio</th><th>Identificación</th>'
                '<th>Nombre</th><th>%</th><th>Vínculo</th><th>Calidad</th><th>Base legal</th></tr>'
                + "".join(filas) + '</table>')
    if d.ficha_ptee:
        p = d.ficha_ptee
        pev = "".join('<li>[' + _esc(e.get("controlId")) + '] ' + _esc(e.get("eventType"))
                      + ' · hmac=' + _esc(bool(e.get('hmacChain'))) + '</li>' for e in d.ptee_eventos)
        body.append('<h2>Riesgo de corrupción / soborno — PTEE (Ley 1778)</h2>')
        body.append('<p>Riesgo: <span class="tag">' + _esc(p.riesgo_corrupcion) + '</span> · Funcionario público: '
                    + _esc(p.funcionario_publico) + ' · Intermediario: ' + _esc(p.uso_intermediario)
                    + ' · DD ampliada: ' + _esc(p.diligencia_ampliada) + '</p>')
        body.append('<p>Canal de denuncias: <b>' + _esc(p.canal_denuncias) + '</b>'
                    + (' · Señales: ' + _esc(", ".join(p.senales)) if p.senales else '') + '</p>')
        if p.factores:
            body.append('<p>Factores: ' + _esc(", ".join(p.factores)) + '</p>')
        body.append('<ul>' + pev + '</ul>')
    if d.ficha_uso_suelo and d.ficha_uso_suelo.zona != "no_mapeado":
        u = d.ficha_uso_suelo
        body.append('<h2>Uso de suelo / POLÍGONO del POT</h2>')
        body.append('<p>Zona: <span class="tag">' + _esc(u.zona) + ' · ' + _esc(u.zona_nombre) + '</span> · Uso principal: '
                    + _esc(u.uso_principal) + '</p>')
        body.append('<p><b>Permitidos:</b> ' + _esc(", ".join(u.usos_permitidos))
                    + ' · <b>NO permitidos:</b> ' + _esc(", ".join(u.usos_no_permitidos) or '—') + '</p>')
        if u.edificabilidad:
            body.append('<p><b>Edificabilidad:</b> ' + _esc("; ".join(e["indice"] + " " + str(e["valor"]) for e in u.edificabilidad)) + '</p>')
        if u.restricciones:
            body.append('<p><b>Restricciones:</b> ' + _esc(", ".join(u.restricciones)) + '</p>')
        body.append('<p><b>Actividad consultada:</b> ' + _esc(u.actividad_consultada or '—')
                    + ' → <span class="tag">' + _esc(u.actividad_resultado) + '</span></p>')
    if d.ficha_identidad:
        fi = d.ficha_identidad
        body.append('<h2>Conciliación de identidad (PD-007)</h2>')
        body.append('<p>Conciliado: <span class="tag">' + _esc(fi.conciliado) + '</span> · Predio: '
                    + _esc(fi.predio_identificado) + ' · Vendedor=titular: ' + _esc(fi.vendedor_es_titular)
                    + ' · BF: ' + _esc(fi.bf_identificado) + ' · Discordancias escaladas: ' + _esc(fi.escaladas) + '</p>')
        if fi.discordancias:
            body.append('<p>Discordancias: ' + _esc("; ".join(fi.discordancias)) + '</p>')
    body.append('<h2>Autoría separada (PD-003)</h2>')
    body.append('<p><b>Sistema (determinista):</b> pre-análisis automático con fuente y regla. '
                '<b>Profesional:</b> decide, concluye y firma. La tecnología prepara; el profesional responde.</p>')
    if d.paquete_portable:
        pp = d.paquete_portable
        body.append('<h2>Expediente institucional / sala de datos (PF-017)</h2>')
        body.append('<p>Receptor: <b>' + _esc(pp.receptor) + '</b> · % reutilizable: <span class="tag">'
                    + _esc(pp.pct_reutilizable) + '%</span> · Consentimiento: ' + _esc(pp.consentimiento) + '</p>')
        body.append('<p>' + _esc(", ".join(c["campo"] for c in pp.campos_reutilizables)[:300]) + '</p>')
        body.append('<p style="color:#666;font-size:12px">' + _esc(pp.aviso) + '</p>')
    body.append('<h2>Hallazgos</h2>' + "".join(cards))
    body.append('<p style="color:#666;font-size:12px">Conclusión simulada (demo). En producción la suscribe el profesional competente.</p>')

    return ('<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>Dictamen ' + _esc(d.caso.id) + '</title>'
            '<style>body{font-family:Arial;margin:24px auto;max-width:900px;padding:8px}h1,h2{color:#10243f}'
            '.exp{border:1px solid #ddd;border-left:4px solid #10243f;padding:10px 14px;margin:10px 0;border-radius:6px}'
            '.tag{display:inline-block;background:#10243f;color:#fff;padding:3px 10px;border-radius:12px;font-size:12px}'
            '.q{background:#eef;padding:8px 12px;border-radius:5px;margin:6px 0}'
            'table{border-collapse:collapse;width:100%;font-size:12px}th,td{border:1px solid #ccc;padding:4px;text-align:left}'
            'li{list-style:none}</style></head><body>'
            + "".join(body)
            + '</body></html>')


def caso_desde_json(j: dict) -> Caso:
    p = j.get("predio", {})
    predio = Predio(folio_matricula=p.get("folio", ""), codigo_catastral=p.get("catastro", ""),
                    direccion=p.get("direccion", ""), area_registral=p.get("areaRegistral", 0.0),
                    area_catastral=p.get("areaCatastral", 0.0))
    partes = tuple(Parte(rol=x.get("rol", ""), nombre=x.get("nombre", ""),
                         tipo_documento=x.get("tipoDocumento", ""), numero_documento=x.get("numeroDocumento", ""),
                         beneficiario_final=x.get("beneficiarioFinal", "")) for x in j.get("partes", ()))
    anot = tuple(Anotacion(numero=x.get("numero", 0), tipo=x.get("tipo", ""), fecha=x.get("fecha", ""),
                           instrumento=x.get("instrumento", ""), titular=x.get("titular", ""),
                           detalle=x.get("detalle", ""), estado=x.get("estado", "vigente"))
                 for x in j.get("anotaciones", ()))
    av = j.get("avaluo")
    avaluo = Avaluo(valor=av.get("valor", 0.0), metodo=av.get("metodo", ""),
                    fecha=av.get("fecha", ""), avaluador=av.get("avaluador", "")) if av else None
    pagos = tuple(Pago(monto=x.get("monto", 0.0), medio=x.get("medio", ""), pagador=x.get("pagador", ""),
                       es_tercero=x.get("esTercero", False)) for x in j.get("pagos", ()))
    return Caso(id=j.get("id", ""), tipo=j.get("tipo", "compraventa"), predio=predio, partes=partes,
                anotaciones=anot, avaluo=avaluo, precio_pactado=j.get("precioPactado"),
                pagos=pagos, titular=j.get("titular", ""), amenazas=tuple(j.get("amenazas", ())),
                sarlaft_estado=j.get("sarlaftEstado", ""))


def _registro_desde_json(j):
    if not j:
        return None
    acc = tuple(Accionista(tipo_documento=a.get("tipoDocumento"), numero_documento=a.get("numeroDocumento"),
                           nombre=a.get("nombre", ""), participacion=a.get("participacion", 0.0))
                for a in j.get("accionistas", ()))
    return RegistroJuridico(nit=j.get("nit", ""), razon_social=j.get("razonSocial", ""),
                            ingresos=j.get("ingresos"), activos=j.get("activos"), sector=j.get("sector", ""),
                            representante_legal=j.get("representanteLegal", ""), composicion_accionaria=acc)


def _listas_desde_json(arr):
    return tuple(RegistroNormalizado(id=x.get("id", ""), nombre=x.get("nombre", ""),
                                     alias=tuple(x.get("alias", ())), tipo_documento=x.get("tipoDocumento"),
                                     numero_documento=x.get("numeroDocumento"), fuente=x.get("fuente", ""),
                                     lista_version=x.get("listaVersion", "")) for x in arr)


def _desde_iso(s, default):
    if not s:
        return default
    try:
        return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return default


def ejecutar_desde_json(payload: dict) -> DictamenCompleto:
    """Construye el caso y los parámetros desde un payload JSON y ejecuta la plataforma."""
    caso = caso_desde_json(payload.get("caso", {}))
    scr = payload.get("screening", {})
    now0 = _desde_iso(payload.get("now"), None)
    return ejecutar_plataforma(
        caso,
        rol_contraparte=payload.get("rolContraparte", ""),
        registro_contraparte=_registro_desde_json(payload.get("registroContraparte")),
        siis_path=payload.get("siisCsv"),
        accionistas=tuple(payload.get("accionistas", ())),
        representante_legal=payload.get("representanteLegal", ""),
        registros_lista=_listas_desde_json(payload.get("registrosLista", [])),
        lista_fuente=scr.get("fuente", "onu"),
        lista_version=scr.get("version", "2026-09-01"),
        lista_hash=scr.get("hash", "hash-seed"),
        catalogo_senales=tuple(payload.get("catalogoSenales", CATALOGO_SENALES)),
        patron_normal=payload.get("patronNormal"),
        umbral_deteccion=payload.get("umbralDeteccion", 2.0),
        umbral_bf=payload.get("umbralBf", 0.05),
        now=now0, hmac_key=payload.get("hmacKey", ""),
        opa_dir=payload.get("opaDir"),
        engine=payload.get("engine", "auto"),
        solicitudes_dd=payload.get("solicitudesDD", 0),
        ultimo_ros_ts=payload.get("ultimoRosTs"),
        ultimo_aros_ts=payload.get("ultimoArosTs"),
        trimestre=payload.get("trimestre", "2026-T3"),
        denuncias_periodo=payload.get("denunciasPeriodo", 0),
        monitoreo_canal=payload.get("monitoreoCanal", True),
        periodo=payload.get("periodo", "2026-T3"),
    )


def dictamen_a_json(d: DictamenCompleto) -> dict:
    return {
        "id": d.caso.id, "tipo": d.caso.tipo,
        "veredicto": d.conclusion.veredicto,
        "fundamento": d.conclusion.fundamento,
        "riesgos": list(d.conclusion.riesgos_prioritarios),
        "observaciones": list(d.conclusion.observaciones),
        "recomendaciones": list(d.conclusion.recomendaciones),
        "cumplimiento": {"regimen": d.integridad.regimen, "screening": d.integridad.screening,
                         "beneficiario_final": d.integridad.beneficiario_final,
                         "perfil": d.integridad.perfil, "senales": list(d.integridad.senales),
                         "operacion_inusual": d.integridad.operacion_inusual,
                         "bf_coincidencia": d.integridad.bf_coincidencia,
                         "dd_requerida": d.integridad.dd_requerida},
        "eventos": [{"controlId": e.get("controlId"), "eventType": e.get("eventType"),
                     "hmacChain": bool(e.get("hmacChain"))} for e in d.compliance_eventos],
        "rub": list(d.rub_reporte),
        "ptee": ({"riesgo": d.ficha_ptee.riesgo_corrupcion, "factores": list(d.ficha_ptee.factores),
                  "senales": list(d.ficha_ptee.senales), "funcionario_publico": d.ficha_ptee.funcionario_publico,
                  "uso_intermediario": d.ficha_ptee.uso_intermediario, "diligencia_ampliada": d.ficha_ptee.diligencia_ampliada,
                  "canal_denuncias": d.ficha_ptee.canal_denuncias,
                  "recomendaciones": list(d.ficha_ptee.recomendaciones)}
                 if d.ficha_ptee else None),
        "uso_suelo": ({"zona": d.ficha_uso_suelo.zona, "zona_nombre": d.ficha_uso_suelo.zona_nombre,
                       "uso_principal": d.ficha_uso_suelo.uso_principal,
                       "usos_permitidos": list(d.ficha_uso_suelo.usos_permitidos),
                       "usos_no_permitidos": list(d.ficha_uso_suelo.usos_no_permitidos),
                       "edificabilidad": list(d.ficha_uso_suelo.edificabilidad),
                       "retiros": d.ficha_uso_suelo.retiros,
                       "restricciones": list(d.ficha_uso_suelo.restricciones),
                       "actividad": d.ficha_uso_suelo.actividad_consultada,
                       "resultado": d.ficha_uso_suelo.actividad_resultado}
                      if d.ficha_uso_suelo else None),
        "identidad": ({"conciliado": d.ficha_identidad.conciliado, "escaladas": d.ficha_identidad.escaladas,
                       "predio_identificado": d.ficha_identidad.predio_identificado,
                       "areas_consistentes": d.ficha_identidad.areas_consistentes,
                       "vendedor_es_titular": d.ficha_identidad.vendedor_es_titular,
                       "comprador_identificado": d.ficha_identidad.comprador_identificado,
                       "bf_identificado": d.ficha_identidad.bf_identificado,
                       "discordancias": list(d.ficha_identidad.discordancias),
                       "coord_consistentes": d.ficha_identidad.coord_consistentes,
                       "fuentes_temporales": list(d.ficha_identidad.fuentes_temporales),
                       "correccion_silenciosa": d.ficha_identidad.correccion_silenciosa}
                      if d.ficha_identidad else None),
        "ciudadano": ({"verificado": list(d.mensaje_ciudadano.verificado), "falta": list(d.mensaje_ciudadano.falta),
                       "riesgo": list(d.mensaje_ciudadano.riesgo),
                       "proximo_paso": list(d.mensaje_ciudadano.proximo_paso),
                       "aviso": d.mensaje_ciudadano.aviso} if d.mensaje_ciudadano else None),
        "portabilidad": ({"receptor": d.paquete_portable.receptor,
                          "pct_reutilizable": d.paquete_portable.pct_reutilizable,
                          "campos": [c["campo"] for c in d.paquete_portable.campos_reutilizables],
                          "consentimiento": d.paquete_portable.consentimiento,
                          "permisos": list(d.paquete_portable.permisos),
                          "aviso": d.paquete_portable.aviso} if d.paquete_portable else None),
        "xn_capa": ({"derechos": {"resumen": d.mapa_derechos.resumen,
                                  "vigentes": len(d.mapa_derechos.vigentes),
                                  "bloquea_disposicion": d.mapa_derechos.bloquea_disposicion}
                     if d.mapa_derechos else None,
                     "comparables": {"motivo": d.analisis_comparables.motivo,
                                     "escalar_a_avaluador": d.analisis_comparables.escalar_a_avaluador,
                                     "divergencia": d.analisis_comparables.divergencia}
                     if d.analisis_comparables else None,
                     "flujo_cierre": {"progreso": d.flujo_cierre.progreso,
                                      "cuello_botella": d.flujo_cierre.cuello_botella}
                     if d.flujo_cierre else None,
                     "autoridad": {"eventos": len(d.libro_autoridad.eventos())}
                     if d.libro_autoridad else None,
                     "consentimiento": {"quien": d.consentimiento.quien,
                                        "base": d.consentimiento.base_juridica}
                     if d.consentimiento else None}
                    if any([d.mapa_derechos, d.analisis_comparables, d.flujo_cierre,
                            d.libro_autoridad, d.consentimiento]) else None),
        "hallazgos": [{"id": h.id, "titulo": h.titulo, "estado": h.estado,
                       "severidad": h.severidad, "responsable": h.responsable}
                      for h in d.expediente.hallazgos],
        "firmantes": list(d.conclusion.firmantes),
    }


def _esc(s):
    return html.escape(str(s))

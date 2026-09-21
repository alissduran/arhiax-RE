"""Reglas deterministas del pre-dictamen, con análisis técnico + base legal + implicación.

Los hallazgos son insumo preliminar (con disclaimer). Cada uno cita qué detecta,
su sustento normativo y su consecuencia operacional, para que el profesional valide.
"""
import unicodedata

from .contracts import Evidencia, Hallazgo

TOLERANCIA_AREA = 0.05
TOLERANCIA_DIVERGENCIA = 0.15

# Actos que transfieren titularidad (P1-2): no solo compraventa.
ACTOS_TRANSFERENCIA = ("compraventa", "adjudicacion", "sucesion", "aporte", "dacion", "fiducia",
                      "donacion", "permuta", "remate", "usucapion")
_SUFIJOS_SOC = ("S.A.S", "S.A", "S.EN C.", "LTDA", "S.C.S", "S.C.A", "SAS", "SA", "LTDA", "EN C")


def _norm(s):
    nfd = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn").upper().strip()


def _norm_razon(s):
    """Normaliza y elimina sufijos societarios para comparar razón social sin falsos substrings."""
    s = _norm(s)
    for suf in _SUFIJOS_SOC:
        s = s.replace(suf, "")
    return " ".join(s.split())


def ejecutar(caso):
    return (
        identidad_inmueble(caso)
        + cronologia_registral(caso)
        + titularidad(caso)
        + gravamenes(caso)
        + cancelaciones(caso)
        + precio_vs_avaluo(caso)
        + pagos_y_terceros(caso)
        + amenazas_pot(caso)
        + verificacion_sarlaft(caso)
    )


def identidad_inmueble(caso):
    p = caso.predio
    if not p.folio_matricula or not p.codigo_catastral:
        return [Hallazgo("TIT_B01", "Identidad del inmueble", "INFORMACION_INSUFICIENTE", "alta",
            "No fue posible determinar la identidad plena del inmueble: falta folio de matrícula o código catastral.",
            base_legal="Principio de especialidad registral (Ley 1579/2012): cada inmueble debe estar individualizado por matrícula y referencia catastral.",
            implicacion="Sin identidad canónica no es viable analizar la cadena de tradición, verificar gravámenes ni estructurar garantía.",
            regla="TIT_B01", accion="Solicitar folio de matrícula (Certificado de Tradición y Libertad) y cédula catastral.", responsable="abogado")]
    if p.area_registral and p.area_catastral:
        diff = abs(p.area_registral - p.area_catastral) / max(p.area_registral, 1.0)
        if diff > TOLERANCIA_AREA:
            return [Hallazgo("TIT_B01", "Consistencia registral-catastral (área)", "INCONSISTENTE", "alta",
                f"Diferencia de {abs(p.area_registral - p.area_catastral):.1f} m² ({diff:.0%}) entre el área registral ({p.area_registral:.1f} m²) y la catastral ({p.area_catastral:.1f} m²).",
                base_legal="Principio de especialidad (Ley 1579/2012, art. 10 y ss.) y concordancia registral-catastral; Código Civil art. 749 (el cuerpo cierto debe individualizarse). La rectificación de área y linderos es un trámite registral/catastral.",
                implicacion="El área es elemento esencial del objeto en compraventa e hipoteca. Una inconsistencia del {:.0%} pone en duda la superficie real, puede reflejar un desenglobe/englobe o segregación no inscrita, y compromete la individualización. Riesgo de falsa tradición o de que el bien entregado/gravado no coincida con lo registrado.".format(diff),
                evidencia=(Evidencia("fol", p.folio_matricula), Evidencia("cat", p.codigo_catastral)),
                regla="TIT_B01", accion="Verificar folio completo, resolución catastral y, si procede, trámite de rectificación de área y linderos con el IGAC.", responsable="abogado")]
        return [Hallazgo("TIT_B01", "Consistencia registral-catastral (área)", "OK", "baja",
            f"Área registral ({p.area_registral:.1f} m²) y catastral ({p.area_catastral:.1f} m²) consistentes (dif. {diff:.0%}).",
            base_legal="Principio de especialidad (Ley 1579/2012); concordancia registral-catastral.",
            implicacion="Consistencia de área declarada como insumo; NO concluye por sí sola la correspondencia física-jurídica ni la realidad del inmueble.", regla="TIT_B01")]
    return [Hallazgo("TIT_B01", "Consistencia registral-catastral (área)", "INFORMACION_INSUFICIENTE", "media",
        "No hay área registral ni catastral para comparar.", base_legal="Principio de especialidad registral.",
        implicacion="Sin áreas no es posible validar la concordancia física-jurídica.", regla="TIT_B01",
        accion="Completar áreas (registral y catastral).", responsable="abogado")]


def cronologia_registral(caso):
    fechas = [a.fecha for a in caso.anotaciones if a.fecha]
    if not fechas:
        return [Hallazgo("TIT_B02", "Cronología registral", "INFORMACION_INSUFICIENTE", "media",
            "Sin anotaciones registrales procesadas.", base_legal="Ley 1579/2012 — la inscripción se practica en orden de radicación.",
            implicacion="Si el folio está vacío o no se adjuntó, no es posible reconstruir la cadena de tradición.", regla="TIT_B02",
            accion="Adjuntar el Certificado de Tradición y Libertad completo.", responsable="abogado")]
    if fechas != sorted(fechas):
        return [Hallazgo("TIT_B02", "Cronología registral", "REQUIERE_REVISION", "media",
            "Anotaciones fuera de orden cronológico.", base_legal="Ley 1579/2012; tracto sucesivo continuo.",
            implicacion="Un orden alterado puede indicar omisión o anotación fuera de secuencia; verificar la cadena eslabón por eslabón.", regla="TIT_B02",
            accion="Revisar la secuencia de anotaciones y el tracto sucesivo.", responsable="abogado")]
    return [Hallazgo("TIT_B02", "Cronología registral", "OK", "baja",
        f"{len(fechas)} anotaciones inscritas en orden cronológico ({fechas[0]} · {fechas[-1]}).",
        base_legal="Ley 1579/2012 — inscripción por orden de radicación; tracto sucesivo continuo.",
        implicacion="Favorable para la reconstrucción de la cadena de tradición; procede verificar la continuidad de cada eslabón.", regla="TIT_B02")]


def titularidad(caso):
    if caso.tipo == "informe_base":
        if not caso.titular:
            return [Hallazgo("TIT_B03", "Titularidad registrada", "INFORMACION_INSUFICIENTE", "alta",
                "No se identificó un titular registrado vigente.", base_legal="Modos de adquirir el dominio (Código Civil arts. 673, 680 — tradición); Ley 1579/2012.",
                implicacion="Sin titular determinado no es viable validar la capacidad de disposición ni estructurar la operación.", regla="TIT_B03",
                accion="Verificar el folio y la última compraventa registrada.", responsable="abogado")]
        return [Hallazgo("TIT_B03", "Titularidad registrada", "OK", "baja",
            f"Titular vigente: {caso.titular} (adquiriente en la última compraventa registrada).",
            base_legal="Modos de adquirir el dominio (Código Civil arts. 673, 680); Ley 1579/2012 — el titular registral es quien puede disponer.",
            implicacion="Al ser persona jurídica, verificar capacidad, representación legal y beneficiario final (SAGRILAFT/PTEE, control C02).", regla="TIT_B03")]
    transferencias = [a for a in caso.anotaciones if a.tipo in ACTOS_TRANSFERENCIA]
    vendedor = next((p for p in caso.partes if p.rol == "vendedor"), None)
    if not transferencias:
        # Puede haber anotaciones cuya naturaleza no se clasificó (P1-2).
        no_clasif = [a for a in caso.anotaciones if a.tipo not in
                     ("hipoteca", "embargo", "cancelacion", "limitacion", "afectacion", "aclaracion", "otro")]
        if no_clasif:
            return [Hallazgo("TIT_B03", "Titularidad", "NO_CLASIFICADO", "media",
                "Existen anotaciones cuya naturaleza no fue clasificada; no se pudo determinar el acto de transferencia.",
                base_legal="Ley 1579/2012; principio de especialidad y clasificación del acto.",
                implicacion="La titularidad no puede afirmarse ni negarse sin clasificar las anotaciones.", regla="TIT_B03",
                accion="Clasificar los actos y reconstruir la cadena de tradición.", responsable="abogado")]
        return [Hallazgo("TIT_B03", "Titularidad vs vendedor", "INFORMACION_INSUFICIENTE", "alta",
            "No hay acto de transferencia registrado y clasificado.", base_legal="Ley 1579/2012; modos de adquirir.",
            implicacion="Sin un acto de transferencia clasificado no se puede acreditar la titularidad del vendedor.", regla="TIT_B03",
            accion="Reconstruir la cadena de tradición del folio.", responsable="abogado")]
    ultima = max(transferencias, key=lambda a: (a.fecha, a.numero))
    titular = ultima.titular
    if not vendedor:
        return [Hallazgo("TIT_B03", "Titularidad vs vendedor", "REQUIERE_REVISION", "alta",
            f"Titular registrado: '{titular or '?'}' (último acto: {ultima.tipo}). No se identificó vendedor.",
            base_legal="Ley 1579/2012; título de disposición (art. 673 C.C.).",
            implicacion="La coherencia vendedor-titular es condición para la transmisión válida de la propiedad.", regla="TIT_B03",
            accion="Identificar al vendedor y su poder de disposición.", responsable="abogado")]
    if titular and _norm_razon(vendedor.nombre) == _norm_razon(titular):
        return [Hallazgo("TIT_B03", "Coherencia vendedor-titular", "OK", "baja",
            f"El vendedor coincide con el titular registrado (último acto {ultima.tipo} {ultima.fecha}).",
            base_legal="Ley 1579/2012; art. 673 C.C. (el titular puede disponer del bien).",
            implicacion="El vendedor tiene titularidad aparente para disponer; verificar poder de disposición y representación.", regla="TIT_B03",
            evidencia=(Evidencia("anot", f"Anotación {ultima.numero}", ultima.instrumento),))]
    return [Hallazgo("TIT_B03", "Coherencia vendedor-titular", "RIESGO", "alta",
        f"El vendedor {vendedor.nombre} NO coincide con el titular registrado '{titular}'.",
        base_legal="Ley 1579/2012; art. 673 C.C.; inexistencia de título de disposición del no titular.",
        implicacion="Riesgo de que el vendedor no sea el propietario, lo que puede invalidar la transferencia o generar falsa tradición y responsabilidad.", regla="TIT_B03",
        evidencia=(Evidencia("anot", f"Anotación {ultima.numero}", ultima.instrumento),),
        accion="Verificar la cadena de tradición, el poder de disposición y, si procede, el acto por quien no ostenta la titularidad.", responsable="abogado")]


def _base_gravamen(tipo):
    return {
        "hipoteca": "Código Civil arts. 2432 y ss. (hipoteca); Ley 1579/2012. La carga exige cancelación para liberar el inmueble.",
        "embargo": "Medida cautelar de embargo (arts. 593, 601 C.G.P.); Ley 1579/2012. El embargo restringe la disponibilidad del bien.",
        "medida_cautelar": "Medida cautelar (inscripción de demanda, prohibición de enajenar, comiso, extinción de dominio — arts. 590 y ss. C.G.P.); Ley 1579/2012.",
        "gravamen": "Gravamen real (servidumbre, usufructo u otro — Código Civil arts. 823 y ss., 879 y ss.); Ley 1579/2012.",
        "afectacion": "Afectación/limitación al dominio (norma especial, p. ej. vivienda familiar — Ley 258/1996; patrimonio familiar).",
        "limitacion": "Limitación al dominio por la norma aplicable (p. ej. afectación a vivienda familiar, patrimonio inembargable).",
    }.get(tipo, "Carga o limitación registrada; Ley 1579/2012.")


def gravamenes(caso):
    h = []
    for a in caso.anotaciones:
        if a.tipo in ("hipoteca", "embargo", "medida_cautelar", "gravamen",
                      "limitacion", "afectacion") and a.estado == "vigente":
            h.append(Hallazgo(f"TIT_B04-{a.numero}", f"Gravamen vigente: {a.tipo}", "RIESGO", "alta",
                f"Anotación {a.numero}: {a.tipo} vigente — {a.detalle or a.instrumento}.",
                base_legal=_base_gravamen(a.tipo),
                implicacion="Una carga o limitación vigente afecta la comerciabilidad y puede restringir la disposición o la garantía en primer grado; en embargos, la disponibilidad del bien.",
                evidencia=(Evidencia(f"anot{a.numero}", f"Anotación {a.numero}", a.instrumento),),
                regla="TIT_B04", accion="Calificar vigencia y prelación; plan de cancelación o levantamiento.", responsable="abogado"))
    if not h:
        h.append(Hallazgo("TIT_B04", "Gravámenes y limitaciones", "OK", "baja",
            "No se identificaron hipotecas, embargos ni afectaciones vigentes dentro de las anotaciones recibidas y clasificadas.",
            base_legal="Las cargas se extinguen por cancelación registrada (Código Civil art. 2457) o cumplimiento.",
            implicacion="Favorable para la transferencia del dominio o la constitución de garantía; verificar que no existan medidas cautelares en curso.", regla="TIT_B04"))
    return h


def cancelaciones(caso):
    hipotecas = [a for a in caso.anotaciones if a.tipo == "hipoteca"]
    vigentes = [a for a in hipotecas if a.estado == "vigente"]
    canceladas = [a for a in hipotecas if a.estado == "cancelada"]
    if vigentes:
        return [Hallazgo("TIT_B05", "Cancelaciones de hipoteca", "RIESGO", "alta",
            f"{len(vigentes)} hipoteca(s) vigente(s) sin cancelación registrada.",
            base_legal="Cancelación de hipoteca (Código Civil art. 2457); Ley 1579/2012.",
            implicacion="Para constituir una nueva garantía en primer grado se requiere la cancelación previa de la carga vigente.", regla="TIT_B05",
            accion="Obtener título de cancelación y verificar su inscripción.", responsable="abogado")]
    if canceladas:
        return [Hallazgo("TIT_B05", "Cancelaciones de hipoteca", "OK", "baja",
            f"Se identificó(n) {len(canceladas)} cancelación(es) de hipoteca registrada(s) en las anotaciones recibidas.",
            base_legal="Cancelación de hipoteca (Código Civil art. 2457): la cancelación extingue la garantía; Ley 1579/2012.",
            implicacion="La cancelación registrada indica extinción de la garantía; verificar el título de cancelación como evidencia.", regla="TIT_B05")]
    return []


def precio_vs_avaluo(caso):
    if caso.tipo == "informe_base":
        return []
    if caso.avaluo is None or caso.precio_pactado is None:
        return [Hallazgo("VAL_B01", "Precio vs avalúo", "INFORMACION_INSUFICIENTE", "media",
            "Falta avalúo o precio pactado para comparar.", base_legal="No hay norma de valor mínimo (art. 1602 C.C., autonomía de la voluntad), pero la coherencia económica es relevante en LA/FT (SAGRILAFT 9.20) y crédito.",
            implicacion="Sin precio ni avalúo no es posible evaluar la coherencia económica de la operación.", regla="VAL_B01",
            accion="Solicitar avalúo (avaluador RAA) y precio pactado.", responsable="avaluador")]
    diff = abs(caso.precio_pactado - caso.avaluo.valor) / max(caso.avaluo.valor, 1.0)
    if diff > TOLERANCIA_DIVERGENCIA:
        return [Hallazgo("VAL_B01", "Precio vs avalúo", "OBSERVACION", "media",
            f"Divergencia de {diff:.0%} entre precio pactado ({caso.precio_pactado:,.0f}) y avalúo referencial ({caso.avaluo.valor:,.0f}).",
            base_legal="Autonomía de la voluntad (art. 1602 C.C.); señal SAGRILAFT/PTEE 9.20 (valor formalizado claramente superior/inferior al de mercado); relación préstamo/valor (LTV) en crédito.",
            implicacion="Una divergencia alta puede indicar sobreprecio o subvaloración: señal de LA/FT y afecta el LTV que el banco exige.", regla="VAL_B01",
            accion="Documentar la justificación de la divergencia y su coherencia con el mercado.", responsable="avaluador")]
    return [Hallazgo("VAL_B01", "Precio vs avalúo", "OK", "baja", f"Divergencia {diff:.0%} dentro del rango esperado.",
        base_legal="Coherencia económica; art. 1602 C.C.", implicacion="El precio es coherente con el valor de mercado referencial.", regla="VAL_B01")]


def pagos_y_terceros(caso):
    if caso.tipo == "informe_base":
        return []
    terceros = [p for p in caso.pagos if p.es_tercero]
    h = []
    if terceros:
        h.append(Hallazgo("TRX_B01", "Pagos por terceros", "RIESGO", "media",
            f"{len(terceros)} pago(s) efectuado(s) por terceros a la operación de {sum(1 for p in terceros)}.",
            base_legal="SAGRILAFT/PTEE (Circular 100-000020) — señales de alerta 9.20: pago fraccionado o efectuado por terceros.",
            implicacion="El pago por tercero es una señal clásica de posible LA/FT: exige identificar el origen de los fondos y la relación del pagador con la operación.", regla="TRX_B01",
            evidencia=tuple(Evidencia("pago", f"Pago {i}", f"{p.monto:,.0f} por {p.pagador}") for i, p in enumerate(terceros)),
            accion="Verificar origen de fondos, identidad del pagador y su relación con la operación (diligencia ampliada).", responsable="abogado"))
    if caso.pagos and not terceros:
        h.append(Hallazgo("TRX_B01", "Pagos y terceros", "OK", "baja", "Pagos efectuados por las partes de la operación.",
            base_legal="SAGRILAFT/PTEE — flujo de pagos coherente con las partes.", implicacion="Sin señal de pago por terceros; el flujo es coherente.", regla="TRX_B01"))
    if not caso.pagos:
        h.append(Hallazgo("TRX_B01", "Pagos y terceros", "INFORMACION_INSUFICIENTE", "media",
            "Sin registro de pagos.", base_legal="SAGRILAFT/PTEE — el flujo de pagos es objeto de análisis.",
            implicacion="Sin pagos documentados no es posible evaluar la coherencia económica ni las señales de LA/FT.", regla="TRX_B01",
            accion="Completar el flujo de pagos (monto, medio, pagador).", responsable="abogado"))
    return h


def amenazas_pot(caso):
    return [
        Hallazgo(f"GEO_B01-{a}", "Amenaza por riesgo (POT)", "RIESGO", "alta",
            f"El predio intersecta la capa de amenaza por remoción en masa ({a}).",
            base_legal="Ley 388/1997 (ordenamiento territorial) y POT de Barranquilla; las zonas de amenaza condicionan licencias, pólizas y originación.",
            implicacion=f"Aunque la amenaza sea '{a}', la entidad financiera puede exigir concepto geotécnico para originación hipotecaria y aseguradoras aplicar recargos. No es necesariamente bloqueante, pero debe documentarse.",
            regla="GEO_B01", accion="Solicitar concepto de ingeniero geotécnico y verificar el polígono exacto de riesgo del POT.", responsable="abogado")
        for a in caso.amenazas
    ]


def _tipo_titular_txt(caso) -> str:
    """Tipo de la contraparte según su DOCUMENTO (nunca se asume)."""
    _tit = next((p for p in getattr(caso, "partes", ()) if getattr(p, "rol", "") == "titular"), None)
    _doc = (getattr(_tit, "tipo_documento", "") or "").lower() if _tit is not None else ""
    if _doc == "nit":
        return "persona jurídica"
    if _doc in ("cc", "ce", "ti", "rc", "pasaporte", "nuip"):
        return "persona natural"
    return "contraparte sin tipo de documento declarado"


def verificacion_sarlaft(caso):
    try:
        from sanctions.legal import cita as _cita_legal
        _base = _cita_legal("SAG_LISTAS_VINCULANTES")
    except Exception:  # noqa: BLE001
        _base = "Circular Externa 100-000020 del 2 de julio de 2026 (CBJ)"
    if caso.sarlaft_estado == "pendiente":
        return [Hallazgo("SAG_B01", "Screening de contrapartes en listas", "OBSERVACION", "media",
            f"El screening de listas de sanciones de la contraparte ({_tipo_titular_txt(caso)}) "
            f"está PENDIENTE o INCOMPLETO en esta ejecución.",
            base_legal=_base + " + Ley 1581.",
            implicacion="Cumplimiento pendiente: sin screening completo y evidencia versionada, la verificación de contrapartes no queda trazable.",
            regla="SAG_B01", accion="Completar el screening contra las fuentes oficiales de sanciones con snapshot versionado y documentar la evidencia.", responsable="abogado")]
    if caso.sarlaft_estado == "verificado":
        return [Hallazgo("SAG_B01", "Screening de contrapartes en listas", "OK", "baja",
                         "Screening ejecutado con evidencia de la versión de cada fuente.", regla="SAG_B01")]
    return []

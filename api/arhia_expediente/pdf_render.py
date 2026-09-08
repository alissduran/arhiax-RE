"""Render del Dictamen Completo a PDF (reportlab / platypus).

Genera un documento legible y trazable a partir de `DictamenCompleto`. La firma
es simulada (demo). Reemplaza caracteres fuera de cp1252 para asegurar el render.
"""
import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle, HRFlowable)

from arhia_expediente.plataforma import DictamenCompleto, _respuestas_preguntas

_NAVY = colors.HexColor("#10243f")
_GRAY = colors.HexColor("#666666")


def _sane(s):
    """Solo cp1252 (Helvetica). Reemplaza caracteres fuera de rango."""
    try:
        return str(s).encode("cp1252", "replace").decode("cp1252")
    except Exception:
        return str(s).encode("ascii", "replace").decode("ascii")


def _estilos():
    ss = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("t", parent=ss["Title"], fontName="Helvetica-Bold", fontSize=16, textColor=_NAVY, spaceAfter=4),
        "sub": ParagraphStyle("s", parent=ss["Normal"], fontSize=9, textColor=_GRAY, spaceAfter=8, alignment=TA_LEFT),
        "h2": ParagraphStyle("h2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=12, textColor=_NAVY, spaceBefore=10, spaceAfter=4),
        "h3": ParagraphStyle("h3", parent=ss["Heading3"], fontName="Helvetica-Bold", fontSize=10, textColor=_NAVY, spaceBefore=6, spaceAfter=2),
        "body": ParagraphStyle("b", parent=ss["Normal"], fontSize=9.5, leading=13, alignment=TA_JUSTIFY),
        "small": ParagraphStyle("sm", parent=ss["Normal"], fontSize=8, textColor=_GRAY),
        "badge": ParagraphStyle("badge", parent=ss["Normal"], fontName="Helvetica-Bold", fontSize=11, textColor=colors.white, backColor=_NAVY, borderRadius=6, padding=6),
    }


def generar_dictamen_pdf(d: DictamenCompleto, out_path: str) -> str:
    """Escribe el dictamen a `out_path` y devuelve la ruta."""
    st = _estilos()
    doc = SimpleDocTemplate(out_path, pagesize=LETTER,
                            leftMargin=2.2 * cm, rightMargin=2.2 * cm,
                            topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                            title="Demostrador preanálisis " + d.caso.id)
    flow = []
    flow.append(Paragraph(_sane("DEMOSTRADOR TÉCNICO DE PREANÁLISIS · Expediente de Confianza Precontractual (OPA)"), st["title"]))
    flow.append(Paragraph(_sane("DATOS SINTÉTICOS — NO USAR PARA DECIDIR. No es dictamen, ni cumplimiento, ni SIREL-compatible, ni expediente operable."), st["sub"]))
    flow.append(Paragraph(_sane(f"Caso: {d.caso.id} · Tipo: {d.caso.tipo} · Preanálisis (título + integridad SAGRILAFT/PTEE + valor + uso de suelo)."), st["sub"]))
    flow.append(Paragraph(_sane("ESTADO DEL PREANÁLISIS: " + d.conclusion.veredicto), st["badge"]))
    flow.append(Spacer(1, 8))

    flow.append(Paragraph("Portada — Las 5 preguntas del Expediente", st["h2"]))
    for k, v in _respuestas_preguntas(d).items():
        flow.append(Paragraph(_sane("<b>" + k + " —</b> " + v), st["small"]))
    flow.append(Spacer(1, 6))

    flow.append(Paragraph("1. Conclusión del profesional", st["h2"]))
    flow.append(Paragraph(_sane("<b>Fundamento:</b> " + d.conclusion.fundamento), st["body"]))
    flow.append(Spacer(1, 4))
    if d.conclusion.riesgos_prioritarios:
        flow.append(Paragraph("Riesgos prioritarios", st["h3"]))
        for r in d.conclusion.riesgos_prioritarios:
            flow.append(Paragraph("<bullet>&bull;</bullet> " + _sane(r), st["body"]))
    if d.conclusion.observaciones:
        flow.append(Paragraph("Observaciones", st["h3"]))
        for o in d.conclusion.observaciones:
            flow.append(Paragraph("<bullet>&bull;</bullet> " + _sane(o), st["body"]))
    flow.append(Paragraph("Recomendaciones", st["h3"]))
    for r in d.conclusion.recomendaciones:
        flow.append(Paragraph("<bullet>&bull;</bullet> " + _sane(r), st["body"]))
    flow.append(Paragraph(_sane("<b>Soporte de cumplimiento:</b> " + d.conclusion.soporte_compliance), st["body"]))
    flow.append(Spacer(1, 6))

    flow.append(Paragraph("Autoría", st["h3"]))
    flow.append(Paragraph(_sane("El sistema solo produce el preanálisis (determinista). La conclusión, el concepto de valor y la decisión de cumplimiento NO están firmados: los emite el profesional competente. Este demostrador no simula firmas."), st["body"]))
    flow.append(Spacer(1, 6))

    flow.append(Paragraph("2. Inmueble y partes", st["h2"]))
    p = d.caso.predio
    flow.append(Paragraph(_sane(f"Folio: {p.folio_matricula} · Catastro: {p.codigo_catastral} · Dir: {p.direccion}"), st["body"]))
    if p.area_registral:
        flow.append(Paragraph(_sane(f"Área registral: {p.area_registral} m² · catastral: {p.area_catastral} m²"), st["body"]))
    for pp in d.caso.partes:
        flow.append(Paragraph(_sane(f"{pp.rol}: {pp.nombre}"), st["body"]))
    flow.append(Spacer(1, 6))

    flow.append(Paragraph("3. Cumplimiento SAGRILAFT+PTEE", st["h2"]))
    i = d.integridad
    flow.append(Paragraph(_sane(f"Régimen: {i.regimen} · Screening: {i.screening} · BF: {i.beneficiario_final or '—'} · Perfil: {i.perfil}"), st["body"]))
    flow.append(Paragraph(_sane(f"Señales: {list(i.senales)} · Inusual: {i.operacion_inusual} · DD requerida: {i.dd_requerida}"), st["body"]))
    if d.compliance_eventos:
        flow.append(Paragraph("Eventos de evidencia (envelope B18 + hmacChain):", st["h3"]))
        for e in d.compliance_eventos:
            flow.append(Paragraph(_sane(f"[{e.get('controlId')}] {e.get('eventType')} · hmacChain={bool(e.get('hmacChain'))}"), st["small"]))
    flow.append(Spacer(1, 6))

    flow.append(Paragraph("4. Registro Único de Beneficiarios Finales (RUB)", st["h2"]))
    if d.rub_reporte:
        rub_tab = [[Paragraph(_sane("<b>Criterio</b>"), st["body"]), Paragraph(_sane("<b>Identificación</b>"), st["body"]),
                    Paragraph(_sane("<b>Nombre</b>"), st["body"]), Paragraph(_sane("<b>%</b>"), st["body"]),
                    Paragraph(_sane("<b>Vínculo</b>"), st["body"]), Paragraph(_sane("<b>Calidad</b>"), st["body"])]]
        for r in d.rub_reporte:
            rub_tab.append([Paragraph(_sane(r.get("criterio")), st["small"]),
                            Paragraph(_sane(f"{r.get('tipo_documento')} {r.get('numero_documento')}"), st["small"]),
                            Paragraph(_sane(r.get("nombre")), st["small"]),
                            Paragraph(_sane(f"{round(r.get('participacion')*100)}%"), st["small"]),
                            Paragraph(_sane(r.get("vinculo")), st["small"]),
                            Paragraph(_sane(r.get("calidad")), st["small"])])
        trf = Table(rub_tab, colWidths=[2.6 * cm, 3.0 * cm, 4.0 * cm, 1.2 * cm, 2.2 * cm, 2.0 * cm])
        trf.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                                 ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef1f6")),
                                 ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 4)]))
        flow.append(trf)
    else:
        flow.append(Paragraph(_sane("Sin beneficiarios finales reportados."), st["body"]))
    flow.append(Spacer(1, 6))

    if d.ficha_ptee:
        p = d.ficha_ptee
        flow.append(Paragraph("5. Riesgo de corrupción / soborno — PTEE (Ley 1778)", st["h2"]))
        flow.append(Paragraph(_sane("Riesgo: " + p.riesgo_corrupcion + " · Funcionario público: "
                                    + str(p.funcionario_publico) + " · Intermediario: " + str(p.uso_intermediario)
                                    + " · DD ampliada: " + str(p.diligencia_ampliada)), st["body"]))
        flow.append(Paragraph(_sane("Canal de denuncias: " + p.canal_denuncias
                                    + (" · Señales: " + "; ".join(p.senales) if p.senales else "")), st["body"]))
        if p.factores:
            flow.append(Paragraph(_sane("Factores: " + "; ".join(p.factores)), st["small"]))
        if p.recomendaciones:
            for rec in p.recomendaciones:
                flow.append(Paragraph(_sane("<bullet>&bull;</bullet> " + rec), st["small"]))
        for e in d.ptee_eventos:
            flow.append(Paragraph(_sane(f"[{e.get('controlId')}] {e.get('eventType')} · hmacChain={bool(e.get('hmacChain'))}"), st["small"]))
        flow.append(Spacer(1, 6))

    if d.ficha_uso_suelo and d.ficha_uso_suelo.zona != "no_mapeado":
        u = d.ficha_uso_suelo
        flow.append(Paragraph("6. Uso de suelo / POLÍGONO del POT", st["h2"]))
        flow.append(Paragraph(_sane("Zona: " + u.zona + " · " + u.zona_nombre + " · Uso principal: " + u.uso_principal), st["body"]))
        flow.append(Paragraph(_sane("Permitidos: " + ", ".join(u.usos_permitidos)
                                    + " · NO permitidos: " + (", ".join(u.usos_no_permitidos) or "—")), st["body"]))
        if u.edificabilidad:
            flow.append(Paragraph(_sane("Edificabilidad: " + "; ".join(e["indice"] + " " + str(e["valor"]) for e in u.edificabilidad)), st["body"]))
        if u.restricciones:
            flow.append(Paragraph(_sane("Restricciones: " + ", ".join(u.restricciones)), st["small"]))
        flow.append(Paragraph(_sane("Actividad consultada: " + (u.actividad_consultada or "—") + " → " + u.actividad_resultado), st["body"]))
        flow.append(Spacer(1, 6))

    if d.ficha_identidad:
        fi = d.ficha_identidad
        flow.append(Paragraph("Conciliación de identidad (PD-007)", st["h2"]))
        flow.append(Paragraph(_sane("Conciliado: " + str(fi.conciliado) + " · Predio identificado: " + str(fi.predio_identificado)
                                    + " · Vendedor=titular: " + str(fi.vendedor_es_titular)
                                    + " · BF identificado: " + str(fi.bf_identificado)
                                    + " · Discordancias escaladas: " + str(fi.escaladas)), st["body"]))
        if fi.discordancias:
            flow.append(Paragraph(_sane("Discordancias: " + "; ".join(fi.discordancias)), st["small"]))
        flow.append(Spacer(1, 6))

    flow.append(Paragraph("Autoría separada (PD-003)", st["h2"]))
    flow.append(Paragraph(_sane("El sistema (determinista) produce el pre-análisis (fuente + regla). "
                                "El profesional decide, concluye y firma. La tecnología prepara; el profesional responde."), st["body"]))
    flow.append(Spacer(1, 6))

    if d.paquete_portable:
        pp = d.paquete_portable
        flow.append(Paragraph("Expediente institucional / sala de datos (PF-017)", st["h2"]))
        flow.append(Paragraph(_sane("Receptor: " + pp.receptor + " · Entidad: " + pp.entidad_nombre
                                    + " (" + pp.entidad_nit + ") · % reutilizable: " + str(pp.pct_reutilizable)
                                    + "% · Consentimiento: " + str(pp.consentimiento)), st["body"]))
        for c in pp.campos_reutilizables:
            flow.append(Paragraph(_sane("  - " + c["campo"] + ": " + c["valor"] + " (" + c["fuente"] + ")"), st["small"]))
        flow.append(Paragraph(_sane("Aviso: " + pp.aviso), st["small"]))
        flow.append(Spacer(1, 6))

    flow.append(Paragraph("7. Hallazgos del expediente", st["h2"]))
    for h in d.expediente.hallazgos:
        flow.append(Paragraph(_sane(f"{h.id} · {h.titulo} — [{h.estado} · {h.severidad}]"), st["h3"]))
        if h.descripcion:
            flow.append(Paragraph(_sane("Evidencia: " + h.descripcion), st["body"]))
        if h.base_legal:
            flow.append(Paragraph(_sane("<i>Base legal: " + h.base_legal + "</i>"), st["small"]))
        if h.accion:
            flow.append(Paragraph(_sane("Acción: " + h.accion), st["small"]))
        flow.append(Paragraph(_sane("Responsable: " + h.responsable), st["small"]))
        flow.append(Spacer(1, 3))

    flow.append(HRFlowable(width="100%", thickness=0.5, color=_GRAY))
    flow.append(Spacer(1, 6))
    flow.append(Paragraph(_sane("Dictamen generado por la plataforma ARHIAX (demo). La conclusión es simulada a partir de hallazgos objetivos; en un entorno productivo la suscribe el profesional competente con firma electrónica."), st["small"]))

    def _pie(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(_GRAY)
        canvas.drawString(2.2 * cm, 1.0 * cm, "ARHIAX · Demostrador — DATOS SINTÉTICOS, NO USAR PARA DECIDIR")
        canvas.drawRightString(LETTER[0] - 2.2 * cm, 1.0 * cm, "Página %d" % doc_.page)
        canvas.restoreState()

    doc.build(flow, onFirstPage=_pie, onLaterPages=_pie)
    return os.path.abspath(out_path)

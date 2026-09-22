# -*- coding: utf-8 -*-
"""ARHIAX RE — Presentación empresarial (5 láminas, 16:9).

Objetivo: dos apuestas estratégicas —
  1. profundizar el crédito hipotecario,
  2. establecer las bases del seguro de títulos.

Estructura:
  P1  Portada y tesis (dos objetivos + cobertura de ciudades)
  P2  El problema, con doble perspectiva (compradores/vendedores · inmobiliarias)
  P3  La solución: el Expediente Verificado (5 capas)
  P4  Metodología: norma + concepto + validación del experto
  P5  Beneficios y los tres canales de ingreso

Salida:
  presentacion/ARHIAX_RE_Presentacion_Empresarial.pdf   (5 láminas, 1280 × 720)

El deck NO menciona lo que falta por construir: es una pieza comercial. Las brechas
técnicas viven en `docs/ui/` (uso interno) y no viajan al material de cliente.
"""
from __future__ import annotations

import sys
from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfgen import canvas

HERE = Path(__file__).resolve().parent
LOGO = HERE / "assets" / "igama-logo.png"

W, H = 1280, 720
M = 64                      # margen
TOTAL = 5

INK = HexColor("#0E1116")
INK2 = HexColor("#39424E")
MUTED = HexColor("#6B7480")
LINE = HexColor("#DFE3E8")
LINE2 = HexColor("#EDEFF2")
PAPER = HexColor("#FFFFFF")
MIST = HexColor("#F6F7F9")
MIST2 = HexColor("#FBFBFC")
RED = HexColor("#EC2B2F")          # rojo de marca (logo Igama)
RED_SOFT = HexColor("#FDECEC")
NAVY = HexColor("#0B1622")
OK = HexColor("#1B8A5A")
OK_SOFT = HexColor("#E8F5EF")

F, FB, FO = "Helvetica", "Helvetica-Bold", "Helvetica-Oblique"


# ── primitivas ────────────────────────────────────────────────────────────────
def txt(c, x, y, s, font=F, size=10, color=INK, align="left"):
    c.setFont(font, size)
    c.setFillColor(color)
    if align == "right":
        c.drawRightString(x, y, s)
    elif align == "center":
        c.drawCentredString(x, y, s)
    else:
        c.drawString(x, y, s)


def wrap(c, x, y, s, font=F, size=9.5, color=INK2, maxw=300, leading=None,
         align="left"):
    leading = leading or size * 1.45
    lines = simpleSplit(str(s), font, size, maxw)
    if align == "center":
        for i, ln in enumerate(lines):
            txt(c, x, y - i * leading, ln, font, size, color, "center")
    elif align == "right":
        for i, ln in enumerate(lines):
            txt(c, x, y - i * leading, ln, font, size, color, "right")
    else:
        for i, ln in enumerate(lines):
            txt(c, x, y - i * leading, ln, font, size, color)
    return y - (len(lines) - 1) * leading


def alto_wrap(s, font, size, maxw):
    return len(simpleSplit(str(s), font, size, maxw))


def card(c, x, y, w, h, fill=MIST, stroke=None, r=10, lw=0.9):
    c.setLineWidth(lw)
    if fill is not None:
        c.setFillColor(fill)
    if stroke is not None:
        c.setStrokeColor(stroke)
    c.roundRect(x, y, w, h, r, stroke=1 if stroke is not None else 0,
                fill=1 if fill is not None else 0)


def rule(c, x1, y1, x2, y2, color=LINE, lw=0.9):
    c.setStrokeColor(color)
    c.setLineWidth(lw)
    c.line(x1, y1, x2, y2)


def chip(c, x, y, s, fg=RED, bg=RED_SOFT):
    w = c.stringWidth(s, FB, 7.4) + 16
    card(c, x, y, w, 17, fill=bg, stroke=None, r=3)
    txt(c, x + 8, y + 5.4, s, FB, 7.4, fg)
    return w


def bullets(c, x, y, items, maxw, size=9.6, color=INK2, gap=15.5,
            marca="—", mcolor=RED):
    for it in items:
        txt(c, x, y, marca, FB, size, mcolor)
        y = wrap(c, x + 16, y, it, F, size, color, maxw - 16, leading=13.4)
        y -= gap
    return y


def chrome(c, num, titulo, kicker):
    """Encabezado estándar: número, marca, título y logo del cliente."""
    top = H - M
    txt(c, M, top - 6, f"P{num}", FB, 12, RED)
    c.setFillColor(RED)
    c.rect(M + 30, top - 8, 2, 17, stroke=0, fill=1)
    txt(c, M + 44, top - 6, "ARHIAX RE", FB, 10.5, INK)
    txt(c, M + 44 + c.stringWidth("ARHIAX RE", FB, 10.5) + 12, top - 6,
        kicker.upper(), F, 7.8, MUTED)
    try:
        img = ImageReader(str(LOGO))
        lw = 68
        c.drawImage(img, W - M - lw, top - lw * 162 / 192 + 14,
                    width=lw, height=lw * 162 / 192, mask="auto")
    except Exception:  # noqa: BLE001
        pass
    rule(c, M, top - 22, W - M, top - 22)
    y = top - 62
    for ln in simpleSplit(titulo, FB, 25, W - 2 * M - 120):
        txt(c, M, y, ln, FB, 25, INK)
        y -= 29
    return y - 6


def footer(c, page, total=TOTAL, nota=""):
    rule(c, M, 46, W - M, 46)
    txt(c, M, 32, nota or ("ARHIAX RE · Igama Financiera e Inmobiliaria · "
                           "infraestructura de confianza para la transacción inmobiliaria"),
        F, 7.6, MUTED)
    txt(c, W - M, 32, f"{page} / {total}", F, 7.6, MUTED, "right")


def fondo(c):
    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, stroke=0, fill=1)


# ── P1 · Portada y tesis ──────────────────────────────────────────────────────
def pag1(c):
    fondo(c)
    c.setFillColor(RED)
    c.rect(M, H - 168, 52, 4, stroke=0, fill=1)

    txt(c, M, H - 226, "ARHIAX RE", FB, 52, INK)
    wrap(c, M, H - 268, "Del inmueble publicado al inmueble verificable", FB, 24,
         INK2, 760, leading=30)

    try:
        img = ImageReader(str(LOGO))
        lw = 132
        c.drawImage(img, W - M - lw, H - 250, width=lw,
                    height=lw * 162 / 192, mask="auto")
    except Exception:  # noqa: BLE001
        pass

    rule(c, M, H - 306, W - M, H - 306)

    # Dos objetivos estratégicos
    y = H - 350
    txt(c, M, y, "DOS OBJETIVOS ESTRATÉGICOS", FB, 9, RED)
    y -= 20

    cw = (W - 2 * M - 24) / 2
    ch = 128
    for i, (titulo, cuerpo) in enumerate([
        ("1 · Profundizar el crédito hipotecario",
         "Más originación sobre riesgo verificado: el banco presta contra un inmueble "
         "cuya identidad, área, norma urbanística y valor están sustentados en fuentes "
         "oficiales y evidencia trazable, no en declaraciones del vendedor."),
        ("2 · Establecer las bases del seguro de títulos",
         "Un expediente verificable y reutilizable es la materia prima del seguro: "
         "cobertura sobre hechos comprobados, con historial auditable que permite "
         "suscribir, tarifar y reclamar con sustentos."),
    ]):
        x = M + i * (cw + 24)
        card(c, x, y - ch, cw, ch, fill=MIST2, stroke=LINE)
        c.setFillColor(RED)
        c.rect(x, y - ch, 3.4, ch, stroke=0, fill=1)
        yy = y - 26
        yy = wrap(c, x + 18, yy, titulo, FB, 13.5, INK, cw - 36, leading=17)
        wrap(c, x + 18, yy - 12, cuerpo, F, 9.4, INK2, cw - 36, leading=13)

    # Cobertura
    y = y - ch - 34
    txt(c, M, y, "COBERTURA · MODELO MUNICIPAL REPLICABLE", FB, 9, MUTED)
    y -= 22
    x = M
    for ciudad in ("BARRANQUILLA", "MEDELLÍN", "BOGOTÁ", "PASTO", "BUCARAMANGA"):
        x += chip(c, x, y, ciudad, fg=INK, bg=MIST) + 8

    y -= 34
    rule(c, M, y, W - M, y, LINE2)
    wrap(c, M, y - 18,
         "Cada municipio aporta sus capas oficiales (catastro, ordenamiento, "
         "estratificación y gestión del riesgo) y su registro; el método es el mismo "
         "y la evidencia queda sellada igual en todos.",
         F, 9, MUTED, W - 2 * M, leading=12.5)
    footer(c, 1)


# ── P2 · El problema (doble perspectiva) ──────────────────────────────────────
def pag2(c):
    fondo(c)
    y = chrome(c, 2, "El problema: certeza que hoy no existe en ninguna orilla",
               "diagnóstico")

    cw = (W - 2 * M - 26) / 2
    top = y - 6
    ch = 300
    for i, (titulo, kicker, items) in enumerate([
        ("Compradores y vendedores",
         "Deciden sin estimación económica ni respaldo técnico",
         ["No saben cuánto vale realmente su **lote, casa o apartamento**: el precio "
          "se fija por referencia de vecinos o portales, no por método.",
          "Asumen riesgo de **falsa tradición, gravámenes vigentes, medidas "
          "cautelares o áreas inconsistentes** sin que nadie lo haya verificado.",
          "No cuentan con **asesoría legal ni geodésica**: linderos, cabida y "
          "afectaciones quedan sin concepto profesional.",
          "Pagan por certeza y reciben un documento que no pueden auditar."]),
        ("Inmobiliarias",
         "Verifican caso por caso, sin poder vender confianza",
         ["La **verificación de títulos es manual**: cada operación consume horas "
          "del equipo jurídico y frena el cierre.",
          "El **expediente se arma distinto cada vez**: sin formato único, sin "
          "trazabilidad y sin evidencia reutilizable.",
          "Sin evidencia de origen lícito ni consulta de **listas restrictivas "
          "conforme a los requerimientos del SAGRILAFT**, el cierre se expone a "
          "riesgo reputacional y regulatorio.",
          "No pueden ofrecer al comprador una garantía o un seguro porque no tienen "
          "el sustento documental para respaldarlo."]),
    ]):
        x = M + i * (cw + 26)
        card(c, x, top - ch, cw, ch, fill=PAPER, stroke=LINE)
        c.setFillColor(RED if i == 0 else NAVY)
        c.rect(x, top - 34, cw, 34, stroke=0, fill=1)
        txt(c, x + 16, top - 23, titulo, FB, 13, white)
        yy = top - 56
        yy = wrap(c, x + 16, yy, kicker, FO, 9.2, MUTED, cw - 32, leading=12)
        _items = [it.replace("**", "") for it in items]
        bullets(c, x + 16, yy - 14, _items, cw - 32, size=9.1, gap=13)

    y = top - ch - 30
    card(c, M, y - 56, W - 2 * M, 56, fill=MIST, stroke=None)
    txt(c, M + 18, y - 22, "EL COSTO COMÚN", FB, 8.4, RED)
    wrap(c, M + 18, y - 40,
         "La información existe —registro, catastro, POT, estratificación, riesgo, "
         "avalúo y listas— pero está dispersa, en lenguajes distintos y sin sello que "
         "permita reutilizarla. El resultado: operaciones lentas, precios sin sustento "
         "y una confianza que se declara en lugar de demostrarse.",
         F, 9.8, INK2, W - 2 * M - 36, leading=13.2)
    footer(c, 2)


# ── P3 · La solución ──────────────────────────────────────────────────────────
def pag3(c):
    fondo(c)
    y = chrome(c, 3, "El Expediente Verificado: una sola verdad, cinco capas",
               "solución")

    top = y - 4
    cw = (W - 2 * M - 4 * 10) / 5
    ch = 216
    capas = [
        ("1 · Identidad", "Matrícula, número predial, NUPRE y unidad (torre / "
         "apartamento) resueltos contra fuentes oficiales.", "oficial"),
        ("2 · Registral", "Tradición, gravámenes, medidas cautelares y afectaciones "
         "leídos del certificado del folio.", "registro"),
        ("3 · Territorial", "Catastro, POT (tratamiento y altura), estratificación y "
         "amenazas del municipio, capa por capa.", "municipio"),
        ("4 · Estimación económica", "Valor del lote, la casa o el apartamento por "
         "método declarado, con banda de valor.", "método"),
        ("5 · Listas restrictivas", "Consulta a las listas obligatorias conforme a "
         "los requerimientos del SAGRILAFT, por contraparte y con evidencia.",
         "cumplimiento"),
    ]
    for i, (titulo, cuerpo, etq) in enumerate(capas):
        x = M + i * (cw + 10)
        card(c, x, top - ch, cw, ch, fill=PAPER, stroke=LINE)
        c.setFillColor(RED)
        c.rect(x, top - 4, cw, 4, stroke=0, fill=1)
        wrap(c, x + 12, top - 26, titulo, FB, 11.4, INK, cw - 24, leading=14)
        wrap(c, x + 12, top - 62, cuerpo, F, 8.8, INK2, cw - 24, leading=11.6)
        chip(c, x + 12, top - ch + 14, etq.upper(), fg=MUTED, bg=MIST2)

    # Sello y atributos de la evidencia
    y = top - ch - 26
    card(c, M, y - 118, W - 2 * M, 118, fill=MIST2, stroke=LINE)
    txt(c, M + 18, y - 24, "EVALUACIÓN AUDITABLE · SELLO INMUTABLE", FB, 9, RED)
    yy = wrap(c, M + 18, y - 44,
              "Cada consulta queda sellada con el hash de la consulta, la versión de "
              "la fuente y la fecha de ejecución. El sello es inmutable y viaja con el "
              "expediente: permite demostrar qué se consultó, contra qué versión y con "
              "qué resultado, y habilita el reuso de la verificación en una segunda "
              "operación sin repetir el trabajo.",
              F, 9.6, INK2, W - 2 * M - 300, leading=13)
    atr = [("hash de la consulta", ""), ("versión de la fuente", ""),
           ("sello inmutable", ""), ("reuso autorizado", "")]
    yy = y - 30
    for nombre, _ in atr:
        chip(c, W - M - 268, yy, nombre.upper(), fg=INK, bg=PAPER)
        yy -= 23

    y = y - 118 - 26
    rule(c, M, y, W - M, y, LINE2)
    wrap(c, M, y - 20,
         "El resultado no es un dato suelto: es un expediente con la misma estructura "
         "para el comprador, el vendedor, la inmobiliaria, el banco y la aseguradora.",
         FO, 9.4, MUTED, W - 2 * M, leading=12.5)
    footer(c, 3)


# ── P4 · Metodología ──────────────────────────────────────────────────────────
def pag4(c):
    fondo(c)
    y = chrome(c, 4, "Metodología: la norma manda, el experto decide", "método")

    top = y - 4
    cw = (W - 2 * M - 2 * 20) / 3
    ch = 268
    bloques = [
        ("LA NORMA", "Marco al que se amarra cada afirmación",
         ["Principio de especialidad registral y concordancia registral-catastral "
          "(Ley 1579 de 2012).",
          "Régimen del avaluador y metodología de avalúo conforme a las resoluciones "
          "vigentes del IGAC (Ley 1673 de 2013).",
          "Ordenamiento territorial y gestión del riesgo del municipio (Ley 388 de "
          "1997 y POT aplicable).",
          "Debida diligencia de contrapartes conforme a los requerimientos del "
          "SAGRILAFT y protección de datos personales (Ley 1581 de 2012)."]),
        ("EL CONCEPTO", "Lo que el motor ejecuta, de forma determinista",
         ["Resuelve identidad y contexto contra capas oficiales y **no afirma nada "
          "sin fuente**: si la fuente no responde, lo declara.",
          "Aplica los métodos de comparación de mercado, costo de reposición y "
          "capitalización de rentas, con sus parámetros declarados.",
          "Contrasta norma urbanística, área y realidad registral-catastral, y "
          "detecta inconsistencias.",
          "Consulta listas restrictivas por contraparte y deja la evidencia "
          "versionada de cada consulta."]),
        ("LA VALIDACIÓN", "El juicio profesional, explícito y firmado",
         ["El resultado es un **insumo**: se entrega señalado, con sus fuentes, "
          "huecos y advertencias.",
          "El **avaluador inscrito en el RAA** selecciona el método, fija supuestos "
          "y firma el valor.",
          "El **abogado** concluye sobre titularidad, gravámenes y estructuración "
          "de la operación.",
          "El **ingeniero geodesta / topógrafo** valida linderos, cabida y "
          "afectaciones físicas."]),
    ]
    for i, (titulo, sub, items) in enumerate(bloques):
        x = M + i * (cw + 20)
        card(c, x, top - ch, cw, ch, fill=PAPER, stroke=LINE)
        c.setFillColor(RED)
        c.rect(x, top - ch, 3.4, ch, stroke=0, fill=1)
        txt(c, x + 18, top - 26, titulo, FB, 10, RED)
        wrap(c, x + 18, top - 44, sub, FO, 9.2, MUTED, cw - 36, leading=12)
        bullets(c, x + 18, top - 74,
                [it.replace("**", "") for it in items], cw - 36, size=8.9, gap=12)

    y = top - ch - 28
    card(c, M, y - 74, W - 2 * M, 74, fill=MIST, stroke=None)
    txt(c, M + 18, y - 24, "TRES PREGUNTAS, TRES RESPUESTAS VERIFICABLES", FB, 9, RED)
    wrap(c, M + 18, y - 44,
         "¿Dónde está el inmueble y cuánto vale?  ·  ¿Qué dice el registro sobre su "
         "titularidad y sus cargas?  ·  ¿Quiénes son las contrapartes y qué riesgo "
         "representan?  Cada respuesta se emite con su fuente, su fecha y su sello; "
         "lo que no se pudo verificar se declara como no verificado, nunca se "
         "presenta como cierto.",
         F, 9.6, INK2, W - 2 * M - 36, leading=13)
    footer(c, 4)


# ── P5 · Beneficios y canales de ingreso ──────────────────────────────────────
def pag5(c):
    fondo(c)
    y = chrome(c, 5, "Beneficios y los tres canales de ingreso", "modelo de negocio")

    top = y - 4
    cw = (W - 2 * M - 26) / 2
    ch = 176

    # Beneficios por actor
    card(c, M, top - ch, cw, ch, fill=PAPER, stroke=LINE)
    c.setFillColor(NAVY)
    c.rect(M, top - 32, cw, 32, stroke=0, fill=1)
    txt(c, M + 16, top - 21, "Para inmobiliarias", FB, 12, white)
    bullets(c, M + 16, top - 54, [
        "Verificación automatizada de títulos: el expediente se arma solo, con "
        "formato único y trazabilidad completa.",
        "Expediente verificado entregable al comprador como respaldo de la operación.",
        "Estimación económica del lote, la casa o el apartamento para sustentar el "
        "precio publicado.",
        "Menos tiempo por operación, menos riesgo reputacional y evidencia lista "
        "para auditoría o para ofrecer garantía.",
    ], cw - 32, size=9.2, gap=13.4)

    card(c, M + cw + 26, top - ch, cw, ch, fill=PAPER, stroke=LINE)
    c.setFillColor(RED)
    c.rect(M + cw + 26, top - 32, cw, 32, stroke=0, fill=1)
    txt(c, M + cw + 42, top - 21, "Para compradores y vendedores", FB, 12, white)
    bullets(c, M + cw + 42, top - 54, [
        "Saber cuánto vale su inmueble con un método declarado, no con un supuesto.",
        "Asesoría legal y geodésica: linderos, cabida, gravámenes y afectaciones con "
        "concepto profesional.",
        "Cerrar con certeza: áreas, norma y cargas verificadas antes de firmar.",
        "Un insumo que el banco y la aseguradora pueden aceptar sin rehacer el "
        "trabajo.",
    ], cw - 32, size=9.2, gap=13.4)

    # Canales de ingreso
    y = top - ch - 30
    txt(c, M, y, "TRES CANALES DE INGRESO", FB, 9, RED)
    y -= 22
    cw3 = (W - 2 * M - 2 * 16) / 3
    ch3 = 158
    canales = [
        ("1 · Dictamen por inmueble",
         "Pago por expediente verificado (caso o bolsa de créditos para "
         "inmobiliarias). Ingreso transaccional, ligado a cada operación.",
         "por operación"),
        ("2 · Suscripción de verificación de títulos",
         "Verificación automatizada y tablero de cartera para inmobiliarias y "
         "fiduciarias. Ingreso recurrente por cupo mensual.",
         "recurrente"),
        ("3 · Licenciamiento de evidencia verificable",
         "Acceso al expediente sellado para bancos y aseguradoras: originación "
         "hipotecaria y bases del seguro de títulos. Ingreso por licencia y consulta.",
         "por licencia"),
    ]
    for i, (titulo, cuerpo, etq) in enumerate(canales):
        x = M + i * (cw3 + 16)
        card(c, x, y - ch3, cw3, ch3, fill=MIST2, stroke=LINE)
        c.setFillColor(RED)
        c.rect(x, y - 4, cw3, 4, stroke=0, fill=1)
        wrap(c, x + 14, y - 26, titulo, FB, 11.6, INK, cw3 - 28, leading=14)
        wrap(c, x + 14, y - 60, cuerpo, F, 9, INK2, cw3 - 28, leading=12.4)
        chip(c, x + 14, y - ch3 + 14, etq.upper(), fg=MUTED, bg=PAPER)

    # Cierre: los dos objetivos se habilitan aquí
    y = y - ch3 - 26
    card(c, M, y - 76, W - 2 * M, 76, fill=MIST, stroke=None)
    c.setFillColor(RED)
    c.rect(M, y - 76, 3.4, 76, stroke=0, fill=1)
    txt(c, M + 18, y - 22, "LO QUE HABILITA", FB, 9, RED)
    wrap(c, M + 18, y - 42,
         "Con el expediente sellado, el banco origina sobre riesgo verificado "
         "(más crédito hipotecario) y la aseguradora suscribe sobre hechos "
         "comprobados y reutilizables (bases del seguro de títulos). La inmobiliaria "
         "deja de vender una promesa y entrega un expediente verificado.",
         F, 9.7, INK2, W - 2 * M - 36, leading=13.4)
    footer(c, 5)


# ── render ────────────────────────────────────────────────────────────────────
def build(destino: Path) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(destino), pagesize=(W, H))
    c.setTitle("ARHIAX RE — Presentación empresarial · Igama Financiera e Inmobiliaria")
    c.setAuthor("ARHIAX RE · Sinergia Consulting Group")
    c.setSubject("Crédito hipotecario y bases del seguro de títulos")

    c.setFillColor(RED)
    c.rect(0, H - 14, W, 14, stroke=0, fill=1)
    pag1(c)
    c.showPage()
    for fn in (pag2, pag3, pag4, pag5):
        fn(c)
        c.showPage()
    c.save()
    return destino


def main(argv=None) -> int:
    argv = argv or sys.argv[1:]
    sufijo = ""
    if "--sufijo" in argv:
        sufijo = argv[argv.index("--sufijo") + 1]
    destino = HERE / f"ARHIAX_RE_Presentacion_Empresarial{sufijo}.pdf"
    build(destino)
    print(f"[deck] {destino} ({destino.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

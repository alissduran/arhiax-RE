# -*- coding: utf-8 -*-
"""
ARHIAX RE — Presentación comercial (5 slides + speech del presentador).

PDF premium PropTech/FinTech: mucho espacio en blanco, una idea dominante por
página, pocas palabras, diagramas simples, sin tablas densas.

Salida: presentacion/ARHIAX_RE_Confianza_Transactional.pdf
"""

from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfgen import canvas

HERE = Path(__file__).resolve().parent
OUT = HERE / "ARHIAX_RE_Confianza_Transactional.pdf"
LOGO = HERE / "assets" / "igama-logo.png"

W, H = 960, 700
M = 54

INK = HexColor("#101828")
INK2 = HexColor("#344054")
ACCENT = HexColor("#D6001C")
GRAY = HexColor("#667085")
LIGHT = HexColor("#F4F5F7")
LIGHT2 = HexColor("#FBFBFC")
LINE = HexColor("#D8DCE3")

F, FB, FO = "Helvetica", "Helvetica-Bold", "Helvetica-Oblique"

# franjas fijas en la parte inferior de cada slide
Y_PROPUESTA = 232          # tarjeta 232-262
Y_SPEECH_TOP = 222         # caja 62-222
ALTO_SPEECH = 160
Y_CONTENIDO_FIN = 278      # el contenido nunca baja de aquí


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
    leading = leading or size * 1.42
    lines = simpleSplit(str(s), font, size, maxw)
    for i, ln in enumerate(lines):
        txt(c, x, y - i * leading, ln, font, size, color, align)
    return y - (len(lines) - 1) * leading


def card(c, x, y, w, h, fill=LIGHT, stroke=None, r=12, lw=0.8):
    c.setLineWidth(lw)
    if fill is not None:
        c.setFillColor(fill)
    if stroke is not None:
        c.setStrokeColor(stroke)
    c.roundRect(x, y, w, h, r, stroke=1 if stroke is not None else 0,
                fill=1 if fill is not None else 0)


def rule(c, x1, y1, x2, y2, color=LINE, lw=0.8):
    c.setStrokeColor(color)
    c.setLineWidth(lw)
    c.line(x1, y1, x2, y2)


def arrow(c, x1, y, x2, color=LINE, lw=1.4, head=6):
    c.setStrokeColor(color)
    c.setLineWidth(lw)
    c.line(x1, y, x2 - head, y)
    c.setFillColor(color)
    p = c.beginPath()
    p.moveTo(x2, y)
    p.lineTo(x2 - head, y + head * 0.62)
    p.lineTo(x2 - head, y - head * 0.62)
    p.close()
    c.drawPath(p, stroke=0, fill=1)


# ── iconografía lineal ────────────────────────────────────────────────────────
def ic_doc(c, cx, cy, s, col):
    w, h = s * 0.74, s
    x, y, fold = cx - w / 2, cy - h / 2, w * 0.30
    c.setStrokeColor(col); c.setLineWidth(1.5); c.setFillColor(white)
    p = c.beginPath()
    p.moveTo(x, y); p.lineTo(x, y + h); p.lineTo(x + w - fold, y + h)
    p.lineTo(x + w, y + h - fold); p.lineTo(x + w, y); p.close()
    c.drawPath(p, stroke=1, fill=1)
    c.line(x + w - fold, y + h, x + w - fold, y + h - fold)
    c.line(x + w - fold, y + h - fold, x + w, y + h - fold)
    for i in range(3):
        yy = y + h * 0.60 - i * h * 0.17
        c.line(x + w * 0.18, yy, x + w * 0.82, yy)


def ic_balanza(c, cx, cy, s, col):
    h = s
    top = cy + h / 2
    c.setStrokeColor(col); c.setLineWidth(1.5)
    c.line(cx, cy - h / 2, cx, top)
    c.line(cx - s * 0.40, top - h * 0.14, cx + s * 0.40, top - h * 0.14)
    for dx in (-s * 0.40, s * 0.40):
        c.line(cx + dx, top - h * 0.14, cx + dx, top - h * 0.34)
        p = c.beginPath()
        p.moveTo(cx + dx - s * 0.14, top - h * 0.34)
        p.lineTo(cx + dx + s * 0.14, top - h * 0.34)
        p.lineTo(cx + dx, top - h * 0.52)
        p.close()
        c.drawPath(p, stroke=1, fill=0)
    c.line(cx - s * 0.20, cy - h / 2, cx + s * 0.20, cy - h / 2)


def ic_mapa(c, cx, cy, s, col):
    w, h = s, s * 0.82
    x, y = cx - w / 2, cy - h / 2
    c.setStrokeColor(col); c.setLineWidth(1.5); c.setFillColor(white)
    c.roundRect(x, y, w, h, 3, stroke=1, fill=1)
    c.line(x + w * 0.34, y, x + w * 0.34, y + h)
    c.line(x + w * 0.68, y, x + w * 0.68, y + h)
    c.setFillColor(col)
    c.circle(cx + w * 0.12, cy + h * 0.06, s * 0.11, stroke=0, fill=1)
    c.setFillColor(white)
    c.circle(cx + w * 0.12, cy + h * 0.06, s * 0.045, stroke=0, fill=1)


def ic_valor(c, cx, cy, s, col):
    c.setStrokeColor(col); c.setLineWidth(1.5); c.setFillColor(white)
    c.circle(cx, cy, s / 2, stroke=1, fill=1)
    txt(c, cx, cy - s * 0.20, "$", FB, s * 0.54, col, "center")


def ic_escudo(c, cx, cy, s, col):
    w, h = s * 0.84, s
    x, y = cx - w / 2, cy - h / 2
    c.setStrokeColor(col); c.setLineWidth(1.5); c.setFillColor(white)
    p = c.beginPath()
    p.moveTo(x, y + h); p.lineTo(x + w, y + h)
    p.lineTo(x + w, y + h * 0.42)
    p.curveTo(x + w, y + h * 0.05, cx, y - h * 0.02, cx, y - h * 0.02)
    p.curveTo(cx, y - h * 0.02, x, y + h * 0.05, x, y + h * 0.42)
    p.close()
    c.drawPath(p, stroke=1, fill=1)
    c.line(cx - w * 0.16, cy + h * 0.06, cx - w * 0.02, cy - h * 0.10)
    c.line(cx - w * 0.02, cy - h * 0.10, cx + w * 0.18, cy + h * 0.20)


def ic_banco(c, cx, cy, s, col):
    w, h = s, s * 0.86
    x, y = cx - w / 2, cy - h / 2
    c.setStrokeColor(col); c.setLineWidth(1.5); c.setFillColor(white)
    p = c.beginPath()
    p.moveTo(x, y + h * 0.62); p.lineTo(cx, y + h); p.lineTo(x + w, y + h * 0.62)
    p.close()
    c.drawPath(p, stroke=1, fill=1)
    for i in range(4):
        xx = x + w * (0.14 + i * 0.24)
        c.line(xx, y + h * 0.10, xx, y + h * 0.54)
    c.rect(x, y + h * 0.02, w, h * 0.08, stroke=1, fill=1)


def ic_hash(c, cx, cy, s, col):
    r = s / 2
    c.setStrokeColor(col); c.setLineWidth(1.5); c.setFillColor(white)
    c.circle(cx, cy, r, stroke=1, fill=1)
    txt(c, cx, cy - r * 0.34, "#", FB, r * 1.08, col, "center")


def ic_reuso(c, cx, cy, s, col):
    r = s / 2
    c.setStrokeColor(col); c.setLineWidth(1.6)
    c.arc(cx - r, cy - r, cx + r, cy + r, 40, 280)
    c.setFillColor(col)
    p = c.beginPath()
    p.moveTo(cx + r * 0.72, cy + r * 0.78)
    p.lineTo(cx + r * 0.22, cy + r * 0.66)
    p.lineTo(cx + r * 0.74, cy + r * 0.26)
    p.close()
    c.drawPath(p, stroke=0, fill=1)


# ── marco ─────────────────────────────────────────────────────────────────────
def chrome(c, n_slide, titulo, kicker):
    top = H - M
    txt(c, M, top - 4, n_slide, FB, 11, ACCENT)
    c.setFillColor(ACCENT)
    c.rect(M + 30, top - 6, 2, 16, stroke=0, fill=1)
    txt(c, M + 44, top - 4, "ARHIAX RE", FB, 10, INK)
    txt(c, M + 44 + c.stringWidth("ARHIAX RE", FB, 10) + 10, top - 4,
        kicker.upper(), F, 7.6, GRAY)
    try:
        img = ImageReader(str(LOGO))
        lw = 62
        c.drawImage(img, W - M - lw, top - lw * 162 / 192 + 12,
                    width=lw, height=lw * 162 / 192, mask="auto")
    except Exception:
        pass
    rule(c, M, top - 20, W - M, top - 20)
    y = top - 58
    for ln in simpleSplit(titulo, FB, 22, W - 2 * M):
        txt(c, M, y, ln, FB, 22, INK)
        y -= 26
    return y + 26 - 28


def footer(c, page, total, note=""):
    rule(c, M, M - 10, W - M, M - 10)
    txt(c, M, M - 26, note or
        "ARHIAX RE · Infraestructura de confianza para la transacción "
        "inmobiliaria", F, 7.4, GRAY)
    txt(c, W - M, M - 26, f"{page} / {total}", F, 7.4, GRAY, "right")


def propuesta(c, texto):
    y = Y_PROPUESTA
    card(c, M, y, W - 2 * M, 30, fill=LIGHT, stroke=None, r=8)
    txt(c, M + 12, y + 10.5, "PROPUESTA VISUAL", FB, 7.2, GRAY)
    wrap(c, M + 118, y + 10.5, texto, FO, 8.2, GRAY, W - 2 * M - 136,
         leading=10)


def speech(c, segundos, texto):
    y = Y_SPEECH_TOP - ALTO_SPEECH
    card(c, M, y, W - 2 * M, ALTO_SPEECH, fill=LIGHT2, stroke=LINE, r=10)
    c.setFillColor(ACCENT)
    c.rect(M, y + 10, 3, ALTO_SPEECH - 20, stroke=0, fill=1)
    txt(c, M + 16, Y_SPEECH_TOP - 22, f"SPEECH · {segundos} s", FB, 8, ACCENT)
    wrap(c, M + 16, Y_SPEECH_TOP - 42, texto, F, 9.3, INK2, W - 2 * M - 34,
         leading=13.4)


# ── PORTADA ───────────────────────────────────────────────────────────────────
def pag_portada(c):
    c.setFillColor(white)
    c.rect(0, 0, W, H, stroke=0, fill=1)
    c.setFillColor(ACCENT)
    c.rect(M, H - 150, 46, 4, stroke=0, fill=1)

    txt(c, M, H - 198, "ARHIAX RE", FB, 46, INK)
    y = H - 242
    for ln in simpleSplit("Infraestructura de confianza para la transacción "
                          "inmobiliaria", FB, 21, 600):
        txt(c, M, y, ln, FB, 21, INK2)
        y -= 27
    y -= 16
    rule(c, M, y, M + 300, y, LINE)
    y -= 32
    txt(c, M, y, "Del inmueble publicado al inmueble verificable.", FO, 15,
        ACCENT)
    y -= 46
    wrap(c, M, y,
         "Un expediente verificable, reutilizable y validable profesionalmente "
         "para compradores, vendedores, inmobiliarias, bancos y aseguradoras.",
         F, 11.5, GRAY, 540, leading=16)

    try:
        c.drawImage(ImageReader(str(LOGO)), W - M - 156, H - 262, width=156,
                    height=132, mask="auto")
    except Exception:
        pass

    card(c, M, M + 40, W - 2 * M, 78, fill=LIGHT, stroke=LINE, r=12)
    txt(c, M + 22, M + 90, "PREPARADO PARA", FB, 7.4, GRAY)
    txt(c, M + 22, M + 66, "SOCIOS COMERCIALES, INMOBILIARIAS, BANCA Y SEGUROS",
        FB, 11, INK)
    txt(c, W - M - 22, M + 66, "Barranquilla · Colombia", F, 9.5, GRAY, "right")
    footer(c, 1, 7, "ENTREGA 1 / 7 · TÍTULO GENERAL DE LA PRESENTACIÓN")


# ── SLIDE 1 ───────────────────────────────────────────────────────────────────
S1 = (
    "Permítanme empezar con algo que todos hemos vivido. Alguien encuentra el "
    "inmueble, negocia, se entusiasma con las fotos… y a mitad del proceso "
    "aparecen los problemas: una anotación que limita la venta, un lindero que "
    "no coincide, un precio que nadie puede sustentar. En ese momento ya hay "
    "tiempo, dinero y confianza comprometidos. La pregunta no es si esos "
    "riesgos existen: existen. La pregunta es cuándo los descubrimos. Comprar, "
    "vender o financiar exige responder tres cosas antes de firmar: qué "
    "inmueble es exactamente, cuánto puede valer razonablemente y qué "
    "condiciones territoriales lo afectan. Cuando esas respuestas viven "
    "dispersas en fuentes distintas, la transacción avanza a ciegas. ARHIAX RE "
    "hace lo contrario: convierte esa información dispersa en un expediente "
    "verificable del inmueble."
)


def pag_slide1(c):
    y0 = chrome(c, "01", "Antes de comprar, vender o financiar, hay que saber "
                 "qué se está transando", "El problema")
    cols = [
        (ic_balanza, "IDENTIDAD Y LEGALIDAD",
         "¿Qué inmueble es exactamente y quién puede venderlo?"),
        (ic_valor, "VALOR", "¿El precio que se pacta está dentro de mercado?"),
        (ic_mapa, "TERRITORIO", "¿Dónde está y qué condiciones lo afectan?"),
    ]
    cw, gap, hc = 268, 24, 178
    x = M
    for icon, tit, preg in cols:
        card(c, x, y0 - hc, cw, hc, fill=LIGHT2, stroke=LINE, r=12)
        c.setFillColor(ACCENT)
        c.rect(x, y0 - 14, cw, 3, stroke=0, fill=1)
        icon(c, x + cw / 2, y0 - 68, 46, ACCENT)
        txt(c, x + cw / 2, y0 - 116, tit, FB, 11.5, INK, "center")
        wrap(c, x + cw / 2, y0 - 146, preg, F, 10.5, GRAY, cw - 48, leading=15,
             align="center")
        x += cw + gap

    yb = y0 - hc - 14
    card(c, M, yb - 62, W - 2 * M, 62, fill=LIGHT, stroke=None, r=12)
    ic_doc(c, M + 40, yb - 31, 30, INK)
    txt(c, M + 70, yb - 27, "Información dispersa", F, 10.5, GRAY)
    arrow(c, M + 196, yb - 31, M + 262, GRAY)
    txt(c, M + 276, yb - 27, "EXPEDIENTE VERIFICABLE DEL INMUEBLE", FB, 13, INK)
    txt(c, W - M - 22, yb - 27,
        "Del inmueble publicado al inmueble verificable.", FO, 11.5, ACCENT,
        "right")

    propuesta(c, "Tres incertidumbres en columnas —balanza, valor y mapa— que "
              "convergen en un único expediente. Blanco dominante, un solo "
              "acento rojo.")
    speech(c, 65, S1)
    footer(c, 2, 7, "ENTREGA 2 / 7 · SLIDE 1 · TEXTO + PROPUESTA VISUAL + SPEECH")


# ── SLIDE 2 ───────────────────────────────────────────────────────────────────
S2 = (
    "¿Qué recibe una persona cuando pide un Dictus ARHIAX? No un documento "
    "más: una lectura ordenada del inmueble en tres dimensiones. En lo "
    "económico, una estimación referencial de valor con precio por metro "
    "cuadrado de referencia, rango, estimación central y canon cuando aplica. "
    "En lo legal, la cadena de tradición, gravámenes, limitaciones y alertas "
    "que pueden afectar la operación. En lo territorial y geodésico, la "
    "identificación espacial del predio, su lectura catastral y urbanística, "
    "los riesgos y el entorno. Y nada de esto sale de una caja negra: hay "
    "metodología, contraste normativo, un concepto consolidado y una ruta de "
    "verificación profesional. Quiero ser explícito: esto no sustituye al "
    "abogado, al avaluador ni al ingeniero. Hace algo más útil: entrega al "
    "experto un expediente ya estructurado, trazable y verificable."
)


def pag_slide2(c):
    y0 = chrome(c, "02", "Un Dictus para tomar mejores decisiones",
                "Comprador · Vendedor")
    cols = [
        (ic_valor, "ECONÓMICO", ["Estimación económica referencial",
                                 "Precio / m² de referencia",
                                 "Rango de valor",
                                 "Canon de renta cuando aplique"]),
        (ic_balanza, "LEGAL", ["Título y tradición", "Gravámenes",
                               "Limitaciones", "Señales jurídicas y alertas"]),
        (ic_mapa, "TERRITORIAL / GEODÉSICO", ["Identificación espacial",
                                              "Catastro", "Urbanismo y POT",
                                              "Riesgos y entorno"]),
    ]
    cw, gap, hc = 268, 24, 218
    x = M
    for icon, tit, items in cols:
        card(c, x, y0 - hc, cw, hc, fill=white, stroke=LINE, r=12)
        c.setFillColor(LIGHT)
        c.roundRect(x, y0 - 56, cw, 46, 12, stroke=0, fill=1)
        c.setFillColor(white)
        c.rect(x, y0 - 56, cw, 12, stroke=0, fill=1)
        icon(c, x + 30, y0 - 34, 24, ACCENT)
        txt(c, x + 52, y0 - 30, tit, FB, 10.4, INK)
        yy = y0 - 86
        for it in items:
            c.setFillColor(ACCENT)
            c.circle(x + 26, yy + 3, 2.2, stroke=0, fill=1)
            txt(c, x + 36, yy, it, F, 10, GRAY)
            yy -= 31
        x += cw + gap

    yb = y0 - hc - 16
    card(c, M, yb - 58, W - 2 * M, 58, fill=LIGHT, stroke=None, r=12)
    txt(c, W / 2, yb - 24,
        "METODOLOGÍA    ·    NORMA    ·    CONCEPTO    ·    VALIDACIÓN EXPERTA",
        FB, 11.5, INK, "center")
    txt(c, W / 2, yb - 43,
        "No sustituye al experto: hace que el experto empiece varios pasos "
        "adelante.", FO, 10.5, ACCENT, "center")

    propuesta(c, "Tres columnas balanceadas con icono y lista corta; franja "
              "inferior que une metodología, norma, concepto y validación "
              "profesional.")
    speech(c, 70, S2)
    footer(c, 3, 7, "ENTREGA 3 / 7 · SLIDE 2 · TEXTO + PROPUESTA VISUAL + SPEECH")


# ── SLIDE 3 ───────────────────────────────────────────────────────────────────
S3 = (
    "Ahora pensemos en la inmobiliaria. Hoy su activo comercial es un inmueble "
    "publicado: fotos, metraje, precio. ARHIAX le permite ofrecer algo "
    "distinto: un inmueble verificado, con un expediente previo de confianza. "
    "Eso cambia la conversación con el comprador, reduce fricción, acelera el "
    "cierre, diferencia la vitrina y prepara el inmueble para crédito antes de "
    "que el banco lo pida. Y abre tres canales de ingreso. Primero, la "
    "verificación del inmueble como servicio premium previo a la negociación. "
    "Segundo, los servicios asociados a la transacción: estudio de títulos, "
    "asesoría jurídica, avalúo profesional, crédito y seguros. Y tercero, la "
    "infraestructura de confianza para bancos, aseguradoras, fondos y "
    "constructoras. La inmobiliaria no solo vende metros cuadrados: vende "
    "certeza."
)


def pag_slide3(c):
    y0 = chrome(c, "03", "Una nueva capacidad comercial para la inmobiliaria",
                "Inmobiliarias")
    pasos = ["INMUEBLE\nPUBLICADO", "INMUEBLE\nVERIFICADO",
             "TRANSACCIÓN MEJOR\nPREPARADA", "CRÉDITO /\nCIERRE"]
    cw, gap = 190, 34
    x = M
    for i, p in enumerate(pasos):
        last = i == len(pasos) - 1
        card(c, x, y0 - 68, cw, 60, fill=LIGHT if last else white,
             stroke=None if last else LINE, r=10)
        for j, ln in enumerate(p.split("\n")):
            txt(c, x + cw / 2, y0 - 34 - j * 15, ln, FB, 10.2, INK, "center")
        if not last:
            arrow(c, x + cw + 6, y0 - 38, x + cw + gap - 6, ACCENT, 1.6, 7)
        x += cw + gap

    yb = y0 - 94
    txt(c, M, yb, "BENEFICIOS PARA LA INMOBILIARIA", FB, 8, GRAY)
    bens = ["Confianza del comprador", "Mayor conversión", "Cierre más rápido",
            "Diferenciación comercial", "Menos reprocesos", "Nuevos servicios"]
    cw2, gap2 = 133, 12
    x = M
    for b in bens:
        card(c, x, yb - 44, cw2, 32, fill=LIGHT2, stroke=LINE, r=8)
        wrap(c, x + cw2 / 2, yb - 28, b, F, 8.4, INK2, cw2 - 14, leading=10.4,
             align="center")
        x += cw2 + gap2

    yb2 = yb - 62
    txt(c, M, yb2, "TRES CANALES DE INGRESO", FB, 8, GRAY)
    canals = [
        ("1", "VERIFICACIÓN DEL INMUEBLE",
         "Expediente predial previo a la negociación, como servicio premium."),
        ("2", "SERVICIOS ASOCIADOS A LA TRANSACCIÓN",
         "Títulos, asesoría jurídica, avalúo, crédito, seguros y trámites."),
        ("3", "INFRAESTRUCTURA DE CONFIANZA B2B",
         "Bancos, aseguradoras, fondos, constructoras y fiduciarias."),
    ]
    cw3, gap3 = 268, 24
    x = M
    for num, tit, desc in canals:
        card(c, x, yb2 - 86, cw3, 76, fill=white, stroke=LINE, r=10)
        c.setFillColor(ACCENT)
        c.roundRect(x + 14, yb2 - 38, 22, 22, 11, stroke=0, fill=1)
        txt(c, x + 25, yb2 - 32, num, FB, 11, white, "center")
        wrap(c, x + 44, yb2 - 30, tit, FB, 9.4, INK, cw3 - 58, leading=11.6)
        wrap(c, x + 14, yb2 - 56, desc, F, 8.6, GRAY, cw3 - 28, leading=11.4)
        x += cw3 + gap3

    propuesta(c, "Flujo horizontal de cuatro pasos con flechas; franja de "
              "beneficios y tres tarjetas de canales de ingreso. Sin cifras ni "
              "tarifas.")
    speech(c, 68, S3)
    footer(c, 4, 7, "ENTREGA 4 / 7 · SLIDE 3 · TEXTO + PROPUESTA VISUAL + SPEECH")


# ── SLIDE 4 ───────────────────────────────────────────────────────────────────
S4 = (
    "Aquí está, en mi opinión, la parte más valiosa de todo esto. Cada vez que "
    "analizamos un inmueble consultamos registro, catastro, territorio y "
    "mercado. Ese trabajo debería servir más de una vez, y hoy se repite en "
    "cada etapa. ARHIAX cambia eso. Cada evidencia conserva su origen, su "
    "fecha, el método con el que se obtuvo y una huella digital verificable "
    "que permite detectar alteraciones y facilita su reutilización durante la "
    "vida de la transacción. Lo resumimos en cuatro palabras: consultar una "
    "vez, verificar, sellar y reutilizar. ¿Qué significa en la práctica? Que "
    "el comprador, el vendedor, la inmobiliaria, el abogado, el avaluador, el "
    "banco o la aseguradora no tengan que empezar de cero cada vez que el "
    "inmueble cambia de etapa."
)


def pag_slide4(c):
    y0 = chrome(c, "04", "La evidencia no debería empezar de cero en cada "
                 "etapa", "Trazabilidad")

    # A. fuentes -> ARHIAX
    fuentes = ["REGISTRO", "CATASTRO", "TERRITORIO", "MERCADO"]
    cwf, gapf = 118, 12
    x = M
    for f in fuentes:
        card(c, x, y0 - 54, cwf, 48, fill=white, stroke=LINE, r=10)
        txt(c, x + cwf / 2, y0 - 31, f, FB, 8.4, INK2, "center")
        x += cwf + gapf
    arrow(c, x + 4, y0 - 30, x + 44, GRAY)
    xn = x + 50
    card(c, xn, y0 - 54, 104, 48, fill=INK, stroke=None, r=10)
    txt(c, xn + 52, y0 - 31, "ARHIAX", FB, 12.5, white, "center")

    # B. cadena de evidencia
    yb = y0 - 74
    chain = [("EVIDENCIA VERIFICADA", ic_doc),
             ("HUELLA / SELLO DE INTEGRIDAD", ic_hash),
             ("REUSO", ic_reuso)]
    cwc, gapc = 244, 44
    x = M
    for i, (tit, icon) in enumerate(chain):
        card(c, x, yb - 62, cwc, 58, fill=LIGHT2, stroke=LINE, r=10)
        icon(c, x + 30, yb - 33, 26, ACCENT)
        wrap(c, x + 52, yb - 27, tit, FB, 8.6, INK, cwc - 64, leading=10.6)
        if i < len(chain) - 1:
            arrow(c, x + cwc + 8, yb - 33, x + cwc + gapc - 8, ACCENT, 1.4, 6)
        x += cwc + gapc

    # C. actores
    yc = yb - 78
    card(c, M, yc - 104, W - 2 * M, 104, fill=white, stroke=LINE, r=12)
    txt(c, M + 22, yc - 24, "LA MISMA EVIDENCIA, REUTILIZADA POR TODOS",
        FB, 8, GRAY)
    actores = ["Comprador", "Vendedor", "Inmobiliaria", "Abogado", "Avaluador",
               "Banco", "Aseguradora"]
    x = M + 22
    for a in actores:
        w = c.stringWidth(a, F, 9.6) + 24
        card(c, x, yc - 64, w, 26, fill=LIGHT, stroke=None, r=13)
        txt(c, x + w / 2, yc - 55, a, F, 9.6, INK2, "center")
        x += w + 10
    txt(c, M + 22, yc - 88,
        "Consultar una vez. Verificar. Sellar. Reutilizar.", FB, 13, ACCENT)

    propuesta(c, "Cadena de valor de izquierda a derecha; debajo, la "
              "constelación de actores que reutilizan la misma evidencia; "
              "frase central en grande.")
    speech(c, 70, S4)
    footer(c, 5, 7, "ENTREGA 5 / 7 · SLIDE 4 · TEXTO + PROPUESTA VISUAL + SPEECH")


# ── SLIDE 5 ───────────────────────────────────────────────────────────────────
S5 = (
    "Cerremos con la visión. ARHIAX RE persigue dos objetivos. El primero es "
    "profundizar el crédito hipotecario: mejor información significa menos "
    "incertidumbre, expedientes mejor preparados y más inmuebles y compradores "
    "que llegan listos a la financiación. El segundo es construir las bases "
    "tecnológicas y probatorias para futuros productos de seguro de títulos: "
    "identidad, cadena jurídica, evidencia, trazabilidad y validación "
    "profesional. No afirmamos que hoy emitamos ese seguro: estamos "
    "construyendo la infraestructura que lo hace posible. Empezamos en "
    "Barranquilla, con red de despliegue en Bogotá, Medellín, Cali y "
    "Bucaramanga, y expansión progresiva hacia Pasto. Y lo hacemos con una "
    "propuesta simple: no agregar otro trámite a la compraventa, sino "
    "transformar la información del inmueble en confianza reutilizable."
)


def pag_slide5(c):
    y0 = chrome(c, "05", "De la transacción inmobiliaria al activo financiable "
                 "y asegurable", "Visión")
    objs = [
        (ic_banco, "1", "PROFUNDIZACIÓN DEL CRÉDITO HIPOTECARIO",
         ["Mejor información", "Menor incertidumbre",
          "Expediente mejor preparado", "Mayor capacidad de originación"]),
        (ic_escudo, "2", "BASES PARA EL SEGURO DE TÍTULOS",
         ["Identidad y cadena jurídica", "Evidencia y trazabilidad",
          "Validación profesional",
          "Infraestructura futura de asegurabilidad del título"]),
    ]
    cw, gap, hc = 412, 28, 162
    x = M
    for icon, num, tit, items in objs:
        card(c, x, y0 - hc, cw, hc, fill=white, stroke=LINE, r=12)
        c.setFillColor(ACCENT)
        c.rect(x, y0 - 10, cw, 3, stroke=0, fill=1)
        icon(c, x + 34, y0 - 48, 30, ACCENT)
        txt(c, x + 58, y0 - 41, num, FB, 15, ACCENT)
        wrap(c, x + 78, y0 - 40, tit, FB, 11.4, INK, cw - 100, leading=13.6)
        yy = y0 - 82
        for it in items:
            c.setFillColor(ACCENT)
            c.circle(x + 26, yy + 3, 2.2, stroke=0, fill=1)
            txt(c, x + 38, yy, it, F, 9.8, GRAY)
            yy -= 22
        x += cw + gap

    yb = y0 - hc - 12
    card(c, M, yb - 58, W - 2 * M, 58, fill=LIGHT, stroke=None, r=12)
    txt(c, M + 20, yb - 18, "RED DE DESPLIEGUE", FB, 7.6, GRAY)
    ciudades = ["Barranquilla", "Bogotá", "Medellín", "Cali", "Bucaramanga"]
    x = M + 20
    for i, ciu in enumerate(ciudades):
        w = c.stringWidth(ciu, FB, 10) + 26
        card(c, x, yb - 50, w, 24, fill=white, stroke=LINE, r=12)
        c.setFillColor(ACCENT)
        c.circle(x + 11, yb - 38, 3, stroke=0, fill=1)
        txt(c, x + 19, yb - 41, ciu, FB, 10, INK)
        x += w + 9
        if i < len(ciudades) - 1:
            rule(c, x - 7, yb - 38, x - 2, yb - 38, LINE)
    txt(c, W - M - 20, yb - 38, "EXPANSIÓN PROGRESIVA: PASTO", FB, 8.6, GRAY,
        "right")

    yc = yb - 64
    card(c, M, yc - 52, W - 2 * M, 52, fill=white, stroke=LINE, r=12)
    wrap(c, M + 20, yc - 20,
         "ARHIAX RE no busca agregar otro trámite a la compraventa. Busca "
         "transformar la información del inmueble en confianza reutilizable.",
         FB, 10.6, INK, W - 2 * M - 40, leading=14)
    wrap(c, M + 20, yc - 40,
         "Seleccionemos un grupo inicial de inmuebles y midamos impacto en "
         "confianza, conversión y preparación para crédito.",
         F, 9.4, ACCENT, W - 2 * M - 40, leading=12)

    propuesta(c, "Dos tarjetas de objetivo; franja inferior con la red de "
              "ciudades como nodos conectados; cierre y llamado a la acción.")
    speech(c, 72, S5)
    footer(c, 6, 7, "ENTREGA 6 / 7 · SLIDE 5 · TEXTO + PROPUESTA VISUAL + SPEECH")


# ── CIERRE ────────────────────────────────────────────────────────────────────
def pag_cierre(c):
    c.setFillColor(white)
    c.rect(0, 0, W, H, stroke=0, fill=1)
    txt(c, W / 2, H / 2 + 74, "ARHIAX RE", FB, 20, ACCENT, "center")
    y = H / 2 + 20
    for ln in simpleSplit("Convertimos la información del inmueble en confianza "
                          "reutilizable para toda la transacción.", FB, 25, 700):
        txt(c, W / 2, y, ln, FB, 25, INK, "center")
        y -= 33
    rule(c, W / 2 - 60, y - 2, W / 2 + 60, y - 2, ACCENT, 1.6)
    try:
        c.drawImage(ImageReader(str(LOGO)), W / 2 - 56, M + 46, width=112,
                    height=94, mask="auto")
    except Exception:
        pass
    footer(c, 7, 7, "ENTREGA 7 / 7 · FRASE FINAL DE CIERRE")
    txt(c, W - M, M - 26, "", F, 7.4, GRAY, "right")


def build():
    c = canvas.Canvas(str(OUT), pagesize=(W, H))
    c.setTitle("ARHIAX RE — Infraestructura de confianza para la transacción "
               "inmobiliaria")
    c.setAuthor("ARHIAX RE")
    c.setSubject("Presentación comercial — confianza transaccional reutilizable")
    for fn in (pag_portada, pag_slide1, pag_slide2, pag_slide3, pag_slide4,
               pag_slide5, pag_cierre):
        fn(c)
        c.showPage()
    c.save()
    print(f"OK -> {OUT}")


if __name__ == "__main__":
    build()

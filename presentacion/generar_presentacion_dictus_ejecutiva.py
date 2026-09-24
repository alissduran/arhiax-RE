# -*- coding: utf-8 -*-
"""DICTUS / ARHIAX RE — Presentación ejecutiva comercial (5 láminas, 16:9).

Audiencia: compradores, vendedores e inmobiliarias.
Objetivos estratégicos que la pieza debe dejar sentados:

  1. Profundizar el crédito hipotecario.
  2. Sentar las bases técnicas del seguro de títulos.

Estructura (una idea dominante por lámina):

  P1  Portada: «DICTUS: confianza verificable para comprar, vender y financiar
      inmuebles» + los dos objetivos estratégicos + cobertura municipal.
  P2  Problema y oportunidad: la incertidumbre de cada orilla y la capa de
      confianza que el mercado necesita antes de la promesa de compraventa.
  P3  Solución DICTUS: las cinco capacidades integradas + el expediente
      verificable (hash, sello inmutable, trazabilidad) y su reuso.
  P4  Metodología y confianza: norma · concepto técnico · validación experta.
  P5  Modelo de valor para inmobiliarias: tres canales de ingresos + ciudades.

Reglas de la pieza:
  * máximo cinco láminas, muy visual, poco texto, lenguaje ejecutivo;
  * nada de pendientes, limitaciones ni roadmap: es material de cliente;
  * las listas se nombran como «listas restrictivas y sancionatorias
    aplicables» (no se citan fuentes concretas);
  * el logo del cliente va en la cabecera de cada lámina.

Salida: presentacion/DICTUS_Presentacion_Ejecutiva.pdf
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
M = 64
TOTAL = 5

INK = HexColor("#0E1116")
INK2 = HexColor("#39424E")
MUTED = HexColor("#6B7480")
LINE = HexColor("#DFE3E8")
LINE2 = HexColor("#EDEFF2")
PAPER = HexColor("#FFFFFF")
MIST = HexColor("#F6F7F9")
MIST2 = HexColor("#FBFBFC")
RED = HexColor("#EC2B2F")
RED_SOFT = HexColor("#FDECEC")
NAVY = HexColor("#0B1622")
OK = HexColor("#1B8A5A")
OK_SOFT = HexColor("#E8F5EF")

F, FB, FO = "Helvetica", "Helvetica-Bold", "Helvetica-Oblique"

CIUDADES = ("BARRANQUILLA", "MEDELLÍN", "BOGOTÁ", "BUCARAMANGA", "PASTO")
CIERRE = "Menos incertidumbre. Más crédito. Más cierres. Más confianza."


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


def alto(s, font, size, maxw) -> int:
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


def chip(c, x, y, s, fg=RED, bg=RED_SOFT, size=7.6, pad=9, h=17):
    w = c.stringWidth(s, FB, size) + 2 * pad
    card(c, x, y, w, h, fill=bg, stroke=None, r=3)
    txt(c, x + pad, y + (h - size) / 2 + 1.1, s, FB, size, fg)
    return w


def bullets(c, x, y, items, maxw, size=9.4, color=INK2, gap=13, marca="—",
            mcolor=RED, leading=None):
    leading = leading or size * 1.42
    for it in items:
        txt(c, x, y, marca, FB, size, mcolor)
        y = wrap(c, x + 15, y, it, F, size, color, maxw - 15, leading=leading)
        y -= gap
    return y


def chrome(c, num, titulo, kicker, subtitulo=""):
    top = H - M
    txt(c, M, top - 6, f"P{num}", FB, 12, RED)
    c.setFillColor(RED)
    c.rect(M + 30, top - 8, 2, 17, stroke=0, fill=1)
    txt(c, M + 44, top - 4, "DICTUS", FB, 12, INK)
    txt(c, M + 44 + c.stringWidth("DICTUS", FB, 12) + 9, top - 3.4,
        "BY ARHIAX RE", F, 8, MUTED)
    txt(c, M + 44, top - 18, kicker.upper(), F, 8.4, MUTED)
    try:
        img = ImageReader(str(LOGO))
        lw = 72
        c.drawImage(img, W - M - lw, top - lw * 162 / 192 + 14,
                    width=lw, height=lw * 162 / 192, mask="auto")
    except Exception:  # noqa: BLE001
        pass
    rule(c, M, top - 28, W - M, top - 28)
    y = top - 66
    for ln in simpleSplit(titulo, FB, 25, W - 2 * M - 150):
        txt(c, M, y, ln, FB, 25, INK)
        y -= 29
    if subtitulo:
        y = wrap(c, M, y - 4, subtitulo, F, 10.4, INK2, W - 2 * M - 150,
                 leading=13.5)
    return y - 14


def footer(c, page, total=TOTAL, nota=""):
    rule(c, M, 46, W - M, 46)
    txt(c, M, 32, nota or ("DICTUS · ARHIAX RE · Igama Financiera e Inmobiliaria · "
                           "infraestructura de confianza para la transacción inmobiliaria"),
        F, 7.6, MUTED)
    txt(c, W - M, 32, f"{page} / {total}", F, 7.6, MUTED, "right")


def fondo(c):
    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, stroke=0, fill=1)


# ── glifos vectoriales (sin dependencias de imagen) ───────────────────────────
def glifo(c, x, y, tipo, size=22, color=RED, bg=None):
    """Icono simple y legible a tamaño pequeño."""
    if bg is not None:
        card(c, x, y, size, size, fill=bg, stroke=None, r=5)
    cx, cy = x + size / 2, y + size / 2
    c.setStrokeColor(color)
    c.setFillColor(color)
    c.setLineWidth(1.5)
    if tipo == "precio":
        txt(c, x + size * 0.22, y + size * 0.26, "$", FB, size * 0.62, color)
    elif tipo == "balanza":
        rule(c, x + size * 0.16, cy + 3, x + size * 0.84, cy + 3, color, 1.4)
        rule(c, cx, y + size * 0.2, cx, cy + 3, color, 1.4)
        c.circle(cx, y + size * 0.18, 1.7, stroke=0, fill=1)
        c.circle(x + size * 0.2, cy + 1, 3.1, stroke=0, fill=1)
        c.circle(x + size * 0.8, cy + 1, 3.1, stroke=0, fill=1)
    elif tipo == "pin":
        c.circle(cx, cy + size * 0.13, size * 0.21, stroke=1, fill=0)
        c.setFillColor(color)
        c.circle(cx, cy + size * 0.13, size * 0.075, stroke=0, fill=1)
        c.line(cx - size * 0.13, cy - size * 0.02, cx, y + size * 0.16)
        c.line(cx + size * 0.13, cy - size * 0.02, cx, y + size * 0.16)
    elif tipo == "escudo":
        p = c.beginPath()
        p.moveTo(cx, y + size * 0.2)
        p.lineTo(x + size * 0.8, y + size * 0.3)
        p.lineTo(x + size * 0.8, cy + size * 0.06)
        p.lineTo(cx, y + size * 0.82)
        p.lineTo(x + size * 0.2, cy + size * 0.06)
        p.lineTo(x + size * 0.2, y + size * 0.3)
        p.close()
        c.drawPath(p, stroke=1, fill=0)
    elif tipo == "sello":
        c.circle(cx, cy, size * 0.32, stroke=1, fill=0)
        c.circle(cx, cy, size * 0.19, stroke=1, fill=0)
        # Marca de verificación VECTORIAL: un glifo de texto fuera de WinAnsi se
        # imprimiría como caja vacía en el PDF.
        c.setLineWidth(1.5)
        c.line(cx - size * 0.12, cy + size * 0.005, cx - size * 0.03,
               cy - size * 0.085)
        c.line(cx - size * 0.03, cy - size * 0.085, cx + size * 0.13,
               cy + size * 0.11)
    elif tipo == "documento":
        c.rect(x + size * 0.22, y + size * 0.18, size * 0.56, size * 0.66,
               stroke=1, fill=0)
        for k in range(3):
            rule(c, x + size * 0.3, cy + size * 0.14 - k * size * 0.15,
                 x + size * 0.7, cy + size * 0.14 - k * size * 0.15, color, 1.1)
    elif tipo == "banco":
        c.rect(x + size * 0.18, y + size * 0.2, size * 0.64, size * 0.34,
               stroke=1, fill=0)
        rule(c, x + size * 0.12, y + size * 0.54, x + size * 0.88, y + size * 0.54,
             color, 1.5)
        for k in range(3):
            rule(c, x + size * 0.3 + k * size * 0.2, y + size * 0.2,
                 x + size * 0.3 + k * size * 0.2, y + size * 0.54, color, 1.1)


# ══ P1 · PORTADA ══════════════════════════════════════════════════════════════
def pag1(c):
    fondo(c)
    c.setFillColor(RED)
    c.rect(M, H - 150, 54, 4, stroke=0, fill=1)
    txt(c, M, H - 196, "DICTUS", FB, 58, INK)
    txt(c, M + c.stringWidth("DICTUS", FB, 58) + 14, H - 196, "BY ARHIAX RE",
        F, 15, MUTED)

    try:
        img = ImageReader(str(LOGO))
        lw = 150
        c.drawImage(img, W - M - lw, H - 232, width=lw,
                    height=lw * 162 / 192, mask="auto")
    except Exception:  # noqa: BLE001
        pass

    y = H - 244
    for ln in simpleSplit("Confianza verificable para comprar, vender y financiar "
                          "inmuebles", FB, 30, 820):
        txt(c, M, y, ln, FB, 30, INK)
        y -= 34
    y = wrap(c, M, y - 2,
             "Estimación económica  +  análisis legal  +  contexto geodésico  +  "
             "evidencia reutilizable", FB, 14.5, RED, 820, leading=19)

    rule(c, M, y - 26, W - M, y - 26)

    # Los dos objetivos estratégicos
    yy = y - 62
    cw = (W - 2 * M - 26) / 2
    ch = 118
    for i, (n, titulo, cuerpo, color) in enumerate([
        ("1", "Profundizar el crédito hipotecario",
         "Más originación sobre riesgo verificado: identidad, área, norma urbanística "
         "y valor sustentados en fuentes oficiales y evidencia trazable.", NAVY),
        ("2", "Sentar las bases del seguro de títulos",
         "Un expediente verificable y reutilizable es la materia prima del seguro: "
         "hechos comprobados para suscribir, tarifar y reclamar.", RED),
    ]):
        x = M + i * (cw + 26)
        card(c, x, yy - ch, cw, ch, fill=MIST2, stroke=LINE)
        c.setFillColor(color)
        c.rect(x, yy - ch, 3.4, ch, stroke=0, fill=1)
        c.setFillColor(color)
        c.circle(x + 30, yy - 32, 12, stroke=0, fill=1)
        txt(c, x + 30, yy - 35.5, n, FB, 12, white, "center")
        wrap(c, x + 52, yy - 27, titulo, FB, 14, INK, cw - 74, leading=17)
        wrap(c, x + 52, yy - 62, cuerpo, F, 9.5, INK2, cw - 74, leading=12.6)

    # Cobertura municipal
    yb = yy - ch - 42
    txt(c, M, yb, "COBERTURA · MODELO MUNICIPAL REPLICABLE", FB, 8.6, MUTED)
    x = M
    for ciudad in CIUDADES:
        x += chip(c, x, yb - 28, ciudad, fg=INK, bg=MIST) + 8

    yc = yb - 62
    rule(c, M, yc, W - M, yc, LINE2)
    c.setFillColor(INK)
    c.roundRect(M, yc - 62, W - 2 * M, 46, 8, stroke=0, fill=1)
    txt(c, M + 20, yc - 34,
        "Comprar, vender y financiar con hechos verificables, no con declaraciones.",
        FB, 15.5, white)
    txt(c, W - M - 20, yc - 34, "Un expediente. Cinco usuarios. Una sola verdad.",
        FO, 10, HexColor("#B9C2CC"), "right")
    footer(c, 1)


# ══ P2 · PROBLEMA Y OPORTUNIDAD ═══════════════════════════════════════════════
def pag2(c):
    fondo(c)
    y = chrome(c, 2, "La operación avanza sobre supuestos, no sobre hechos",
               "problema y oportunidad")

    top = y
    cw = (W - 2 * M - 26) / 2
    ch = 288
    for i, (titulo, kicker, gl, items) in enumerate([
        ("Compradores y vendedores", "Deciden sin certeza", "pin",
         ["Precio sin método: no se sabe cuánto vale realmente el lote, la casa o el "
          "apartamento.",
          "Títulos y cargas sin verificar: tradición, gravámenes y medidas cautelares.",
          "Riesgos y ubicación sin concepto técnico: norma, linderos, afectaciones.",
          "Viabilidad hipotecaria incierta: el crédito se cae cuando aparece el "
          "hallazgo."]),
        ("Inmobiliarias", "Venden más rápido cuando pueden demostrar", "escudo",
         ["Más fricción comercial: cada operación exige verificación manual.",
          "Más reprocesos: el expediente se arma distinto en cada caso.",
          "Menor cierre: la negociación se enfría mientras se aclara la información.",
          "Mayor riesgo reputacional y de cumplimiento frente a las contrapartes."]),
    ]):
        x = M + i * (cw + 26)
        card(c, x, top - ch, cw, ch, fill=PAPER, stroke=LINE)
        c.setFillColor(RED if i == 0 else NAVY)
        c.rect(x, top - 42, cw, 42, stroke=0, fill=1)
        txt(c, x + 16, top - 27, titulo, FB, 13.5, white)
        glifo(c, x + cw - 40, top - 35, gl, 22, white)
        yy = wrap(c, x + 16, top - 66, kicker, FO, 10, MUTED, cw - 32, leading=12.5)
        bullets(c, x + 16, yy - 16, items, cw - 32, size=9.4, gap=13)

    yb = top - ch - 30
    card(c, M, yb - 96, W - 2 * M, 96, fill=MIST, stroke=None)
    c.setFillColor(RED)
    c.rect(M, yb - 96, 3.4, 96, stroke=0, fill=1)
    txt(c, M + 20, yb - 26, "LA OPORTUNIDAD", FB, 8.8, RED)
    wrap(c, M + 20, yb - 46,
         "El mercado necesita una capa de confianza previa a la promesa de compraventa.",
         FB, 15, INK, W - 2 * M - 40, leading=19)
    wrap(c, M + 20, yb - 72,
         "Quien la entregue primero con evidencia —y no con promesas— captura la "
         "operación, acelera el cierre y habilita el crédito y la garantía sobre "
         "hechos comprobados.", F, 9.8, INK2, W - 2 * M - 40, leading=13)
    footer(c, 2)


# ══ P3 · SOLUCIÓN ═════════════════════════════════════════════════════════════
def pag3(c):
    fondo(c)
    y = chrome(c, 3, "DICTUS integra, en un solo expediente, lo que hoy está disperso",
               "solución", "Una plataforma, cinco capacidades, un documento que el "
               "banco y la aseguradora pueden aceptar.")

    top = y - 2
    cw = (W - 2 * M - 4 * 12) / 5
    ch = 210
    capas = [
        ("precio", "Estimación económica",
         "Valor del predio, lote, apartamento o casa por método declarado, con banda "
         "de valor."),
        ("balanza", "Revisión jurídica y de títulos",
         "Tradición, titularidad, gravámenes, medidas cautelares y afectaciones del "
         "folio."),
        ("pin", "Análisis geodésico y urbano",
         "Identidad del predio, catastro, POT, estratificación, riesgos y linderos "
         "con criterio técnico."),
        ("escudo", "Contrapartes y listas restrictivas",
         "Consulta de contrapartes frente a las listas restrictivas y sancionatorias "
         "aplicables, conforme al SAGRILAFT."),
        ("sello", "Expediente verificable",
         "Hash, sello inmutable y trazabilidad: qué se consultó, con qué versión y "
         "con qué resultado."),
    ]
    for i, (gl, titulo, cuerpo) in enumerate(capas):
        x = M + i * (cw + 12)
        card(c, x, top - ch, cw, ch, fill=PAPER, stroke=LINE)
        c.setFillColor(RED)
        c.rect(x, top - 4, cw, 4, stroke=0, fill=1)
        glifo(c, x + 14, top - 48, gl, 26, RED, bg=RED_SOFT)
        txt(c, x + 14, top - 62, str(i + 1), FB, 8.4, MUTED)
        wrap(c, x + 14, top - 92, titulo, FB, 11.6, INK, cw - 28, leading=13.6)
        wrap(c, x + 14, top - 132, cuerpo, F, 8.7, INK2, cw - 28, leading=11.4)

    # Reuso
    yr = top - ch - 26
    card(c, M, yr - 92, W - 2 * M, 92, fill=MIST2, stroke=LINE)
    txt(c, M + 18, yr - 24, "UN SOLO EXPEDIENTE, CINCO USUARIOS", FB, 8.8, RED)
    wrap(c, M + 18, yr - 42,
         "El mismo documento sellado sirve a quien compra, a quien vende, a quien "
         "intermedia, a quien financia y a quien asegura: nadie repite el trabajo y "
         "todos leen la misma verdad.", F, 9.5, INK2, W - 2 * M - 40, leading=12.6)
    x = M + 18
    for u in ("COMPRADOR", "VENDEDOR", "INMOBILIARIA", "BANCO", "ASEGURADORA"):
        x += chip(c, x, yr - 84, u, fg=INK, bg=PAPER) + 8

    yz = yr - 92 - 26
    card(c, M, yz - 76, W - 2 * M, 76, fill=NAVY, stroke=None)
    txt(c, M + 20, yz - 28, "REUTILIZABLE POR DISEÑO", FB, 9, white)
    wrap(c, M + 20, yz - 48,
         "Evidencia sellada para el crédito hipotecario y para las bases del seguro de "
         "títulos: lo verificado una vez se aprovecha en la siguiente operación, con "
         "la misma trazabilidad.", F, 9.8, HexColor("#C9D2DB"), W - 2 * M - 40,
         leading=13)
    footer(c, 3)


# ══ P4 · METODOLOGÍA ══════════════════════════════════════════════════════════
def pag4(c):
    fondo(c)
    y = chrome(c, 4, "Tres capas de rigor: la norma, el concepto y el experto",
               "metodología y confianza")

    top = y
    cw = (W - 2 * M - 2 * 22) / 3
    ch = 262
    bloques = [
        ("LA NORMA", "El marco que manda",
         ["Lectura conforme a las exigencias legales, urbanísticas, registrales y de "
          "debida diligencia.",
          "Cada afirmación se ancla en la norma aplicable, no en la costumbre del "
          "mercado.",
          "Trazabilidad documental lista para auditoría, comité de crédito o "
          "aseguradora."]),
        ("EL CONCEPTO TÉCNICO", "Lo que el motor resuelve",
         ["Estimación económica referencial con método y parámetros declarados.",
          "Contexto territorial: catastro, POT, estratificación, riesgos y cargas.",
          "Contraste de área, norma y realidad registral-catastral antes de firmar."]),
        ("LA VALIDACIÓN EXPERTA", "El criterio que firma",
         ["Revisión por profesional jurídico y técnico que convierte datos en "
          "criterio.",
          "El avaluador selecciona el método, fija supuestos y respalda el valor.",
          "El abogado concluye sobre titularidad, cargas y estructuración de la "
          "operación."]),
    ]
    for i, (titulo, sub, items) in enumerate(bloques):
        x = M + i * (cw + 22)
        card(c, x, top - ch, cw, ch, fill=PAPER, stroke=LINE)
        c.setFillColor(RED)
        c.rect(x, top - ch, 3.4, ch, stroke=0, fill=1)
        glifo(c, x + 18, top - 44, ("documento", "pin", "sello")[i], 24, RED,
              bg=RED_SOFT)
        txt(c, x + 52, top - 30, f"CAPA {i + 1}", FB, 8.4, MUTED)
        wrap(c, x + 52, top - 46, titulo, FB, 10.6, RED, cw - 74, leading=13)
        yb = wrap(c, x + 18, top - 82, sub, FO, 10, MUTED, cw - 36, leading=12.5)
        bullets(c, x + 18, yb - 18, items, cw - 36, size=9, gap=12.4)

    yb2 = top - ch - 30
    card(c, M, yb2 - 88, W - 2 * M, 88, fill=MIST, stroke=None)
    txt(c, M + 20, yb2 - 26, "LA REGLA DE ORO", FB, 8.8, RED)
    wrap(c, M + 20, yb2 - 46,
         "DICTUS no declara lo que no puede demostrar: cada dato viaja con su fuente, "
         "su fecha y su sello de integridad, y el documento final lo firma un "
         "profesional. Eso es lo que lo hace aceptable para un banco, para una "
         "aseguradora y para un tribunal.", F, 9.8, INK2, W - 2 * M - 40, leading=13)
    footer(c, 4)


# ══ P5 · MODELO DE VALOR ══════════════════════════════════════════════════════
def pag5(c):
    fondo(c)
    y = chrome(c, 5, "Tres canales de ingresos", "modelo de valor para inmobiliarias")

    top = y
    cw = (W - 2 * M - 2 * 18) / 3
    ch = 196
    canales = [
        ("1", "Dictus para compradores y vendedores",
         "Informe previo de confianza: qué se compra, cuánto vale y qué riesgo tiene, "
         "antes de comprometer el negocio.", "por informe"),
        ("2", "Inmuebles captados",
         "Verificación automatizada de títulos y expediente verificado para cada "
         "inmueble del portafolio, listo para mostrar.", "por captación"),
        ("3", "Servicios B2B para bancos, aseguradoras y aliados",
         "Expediente reutilizable para el crédito hipotecario y como base técnica del "
         "seguro de títulos.", "por licencia"),
    ]
    for i, (n, titulo, cuerpo, etq) in enumerate(canales):
        x = M + i * (cw + 18)
        card(c, x, top - ch, cw, ch, fill=MIST2, stroke=LINE)
        c.setFillColor(RED if i < 2 else NAVY)
        c.rect(x, top - 4, cw, 4, stroke=0, fill=1)
        c.setFillColor(RED if i < 2 else NAVY)
        c.circle(x + 34, top - 36, 14, stroke=0, fill=1)
        txt(c, x + 34, top - 40.5, n, FB, 14, white, "center")
        wrap(c, x + 60, top - 26, titulo, FB, 12.4, INK, cw - 76, leading=15)
        wrap(c, x + 18, top - 76, cuerpo, F, 9.4, INK2, cw - 36, leading=12.6)
        chip(c, x + 18, top - ch + 16, etq.upper(), fg=MUTED, bg=PAPER)

    # Beneficio para la inmobiliaria
    yb = top - ch - 28
    card(c, M, yb - 92, W - 2 * M, 92, fill=PAPER, stroke=LINE)
    c.setFillColor(NAVY)
    c.rect(M, yb - 92, 3.4, 92, stroke=0, fill=1)
    txt(c, M + 20, yb - 26, "POR QUÉ CONVIENE A LA INMOBILIARIA", FB, 8.8, RED)
    wrap(c, M + 20, yb - 46,
         "Vende más rápido con un expediente que respalda el precio y la titularidad; "
         "reduce reprocesos jurídicos; protege su reputación; y suma un ingreso por "
         "cada verificación que ya tenía que hacer.", F, 9.8, INK2,
         W - 2 * M - 40, leading=13)

    # Ciudades
    yc = yb - 92 - 26
    txt(c, M, yc, "DISPONIBLE EN", FB, 8.6, MUTED)
    x = M + c.stringWidth("DISPONIBLE EN", FB, 8.6) + 14
    for ciudad in CIUDADES:
        x += chip(c, x, yc - 5, ciudad, fg=INK, bg=MIST) + 8
    txt(c, W - M, yc + 2, "Y el mismo método para cada nuevo municipio.", FO, 8.6,
        MUTED, "right")

    yz = yc - 34
    c.setFillColor(INK)
    c.roundRect(M, yz - 54, W - 2 * M, 50, 8, stroke=0, fill=1)
    c.setFillColor(RED)
    c.rect(M, yz - 54, 3.4, 50, stroke=0, fill=1)
    txt(c, M + 22, yz - 32, CIERRE, FB, 16.5, white)
    footer(c, 5)


# ── render + QA ───────────────────────────────────────────────────────────────
def build(destino: Path) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(destino), pagesize=(W, H))
    c.setTitle("DICTUS — confianza verificable para comprar, vender y financiar inmuebles")
    c.setAuthor("ARHIAX RE · Igama Financiera e Inmobiliaria")
    c.setSubject("Crédito hipotecario y bases técnicas del seguro de títulos")
    c.setKeywords("DICTUS, ARHIAX RE, crédito hipotecario, seguro de títulos, "
                  "inmobiliarias, confianza verificable")
    c.setFillColor(RED)
    c.rect(0, H - 14, W, 14, stroke=0, fill=1)
    pag1(c)
    c.showPage()
    for fn in (pag2, pag3, pag4, pag5):
        fn(c)
        c.showPage()
    c.save()
    return destino


OBLIGATORIO = [
    "DICTUS", "confianza verificable", "Estimación económica", "análisis legal",
    "contexto geodésico", "evidencia reutilizable", "crédito hipotecario",
    "seguro de títulos", "Compradores y vendedores", "Inmobiliarias",
    "capa de confianza previa a la promesa de compraventa", "Estimación económica",
    "Revisión jurídica", "geodésico", "listas restrictivas", "SAGRILAFT",
    "hash", "sello inmutable", "trazabilidad", "COMPRADOR", "VENDEDOR",
    "INMOBILIARIA", "BANCO", "ASEGURADORA", "LA NORMA", "CONCEPTO TÉCNICO",
    "VALIDACIÓN EXPERTA", "Tres canales de ingresos", "informe previo de confianza",
    "Verificación automatizada de títulos", "expediente verificado", "B2B",
    "BARRANQUILLA", "MEDELLÍN", "BOGOTÁ", "BUCARAMANGA", "PASTO",
    "Menos incertidumbre. Más crédito. Más cierres. Más confianza.",
]
VETADO = ["pendiente", "falta", "no disponible", "roadmap", "limitación",
          "OFAC", "ONU", "UKSL", "por construir", "en desarrollo", "próximamente",
          "TBD", "SAGRILAFT y OFAC"]


def qa(pdf: Path) -> int:
    """QA de la pieza: 5 láminas, contenido obligatorio y lenguaje sin pendientes."""
    import pymupdf
    doc = pymupdf.open(str(pdf))
    paginas = [" ".join(" ".join(p.get_text().split()) for p in [pg]) for pg in doc]
    plano = " ".join(paginas)
    fallos = []
    if doc.page_count != 5:
        fallos.append(f"láminas={doc.page_count} (deben ser 5)")
    faltan = [t for t in OBLIGATORIO if t.lower() not in plano.lower()]
    if faltan:
        fallos.append(f"falta contenido obligatorio: {faltan}")
    vetados = [v for v in VETADO if v.lower() in plano.lower()]
    if vetados:
        fallos.append(f"lenguaje vetado presente: {vetados}")
    # La frase de cierre es la ÚLTIMA: vive solo en la lámina 5.
    if CIERRE.lower() not in paginas[-1].lower():
        fallos.append("la frase de cierre no está en la última lámina")
    repetida = [i + 1 for i, t in enumerate(paginas[:-1]) if CIERRE.lower() in t.lower()]
    if repetida:
        fallos.append(f"la frase de cierre se repite fuera de la última lámina: {repetida}")
    print(f"[deck] {pdf.name} · {doc.page_count} láminas · "
          f"obligatorio {len(OBLIGATORIO) - len(faltan)}/{len(OBLIGATORIO)} · "
          f"vetados {len(vetados)} · cierre en última lámina: sí")
    if fallos:
        for f in fallos:
            print(f"[FAIL] {f}")
        return 1
    print("[OK] QA de la pieza en PASS")
    return 0


def main(argv=None) -> int:
    argv = argv or sys.argv[1:]
    sufijo = ""
    if "--sufijo" in argv:
        sufijo = argv[argv.index("--sufijo") + 1]
    destino = HERE / f"DICTUS_Presentacion_Ejecutiva{sufijo}.pdf"
    build(destino)
    print(f"[deck] {destino} ({destino.stat().st_size} bytes)")
    return qa(destino)


if __name__ == "__main__":
    raise SystemExit(main())

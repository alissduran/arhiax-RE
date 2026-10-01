# -*- coding: utf-8 -*-
"""
ARHIAX RE — Documento de ENTREGA de la presentación comercial.

Formato documento (A4 vertical) con los 7 ítems exactos de la entrega:
  1. Título general
  2-6. Slide 1..5: texto + propuesta visual + speech
  7. Frase final de cierre

Salida: presentacion/ARHIAX_RE_Entrega_Completa.pdf
"""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (BaseDocTemplate, Frame, Image, KeepTogether,
                                PageTemplate, Paragraph, Spacer, Table,
                                TableStyle)

HERE = Path(__file__).resolve().parent
OUT = HERE / "ARHIAX_RE_Entrega_Completa.pdf"
LOGO = HERE / "assets" / "igama-logo.png"

ACCENT = colors.HexColor("#D6001C")
INK = colors.HexColor("#101828")
INK2 = colors.HexColor("#344054")
GRAY = colors.HexColor("#667085")
LIGHT = colors.HexColor("#F4F5F7")
LINE = colors.HexColor("#D8DCE3")

TITULO_GENERAL = "ARHIAX RE"
SUBTITULO = "Infraestructura de confianza para la transacción inmobiliaria"
BAJADA = "Del inmueble publicado al inmueble verificable."
CONTEXTO = ("Un expediente verificable, reutilizable y validable profesionalmente "
            "para compradores, vendedores, inmobiliarias, bancos y aseguradoras.")

SLIDES = [
    {
        "n": 1,
        "titulo": "Antes de comprar, vender o financiar, hay que saber qué se "
                  "está transando",
        "texto": [
            ("IDENTIDAD Y LEGALIDAD", "¿Qué inmueble es exactamente y quién "
                                      "puede venderlo?"),
            ("VALOR", "¿El precio que se pacta está dentro de mercado?"),
            ("TERRITORIO", "¿Dónde está y qué condiciones lo afectan?"),
            ("CIERRE", "Información dispersa → Expediente verificable del "
                       "inmueble."),
            ("FRASE FUERTE", "Del inmueble publicado al inmueble verificable."),
        ],
        "visual": "Tres columnas con icono —balanza, valor y mapa— que convergen "
                  "en una única franja de expediente verificable. Blanco "
                  "dominante, un solo acento rojo, una idea por página.",
        "seg": 65,
        "speech": (
            "Permítanme empezar con algo que todos hemos vivido. Alguien "
            "encuentra el inmueble, negocia, se entusiasma con las fotos… y a "
            "mitad del proceso aparecen los problemas: una anotación que limita "
            "la venta, un lindero que no coincide, un precio que nadie puede "
            "sustentar. En ese momento ya hay tiempo, dinero y confianza "
            "comprometidos. La pregunta no es si esos riesgos existen: existen. "
            "La pregunta es cuándo los descubrimos. Comprar, vender o financiar "
            "exige responder tres cosas antes de firmar: qué inmueble es "
            "exactamente, cuánto puede valer razonablemente y qué condiciones "
            "territoriales lo afectan. Cuando esas respuestas viven dispersas en "
            "fuentes distintas, la transacción avanza a ciegas. ARHIAX RE hace "
            "lo contrario: convierte esa información dispersa en un expediente "
            "verificable del inmueble."),
    },
    {
        "n": 2,
        "titulo": "Un Dictus para tomar mejores decisiones",
        "texto": [
            ("ECONÓMICO", "Estimación económica referencial · Precio / m² de "
                          "referencia · Rango de valor · Canon de renta cuando "
                          "aplique"),
            ("LEGAL", "Título y tradición · Gravámenes · Limitaciones · Señales "
                      "jurídicas y alertas"),
            ("TERRITORIAL / GEODÉSICO", "Identificación espacial · Catastro · "
                                        "Urbanismo y POT · Riesgos y entorno"),
            ("BASE METODOLÓGICA", "Metodología + Norma + Concepto + Validación "
                                  "experta"),
            ("MENSAJE", "No sustituye al experto: hace que el experto empiece "
                        "varios pasos adelante."),
        ],
        "visual": "Tres columnas balanceadas con icono y lista corta; franja "
                  "inferior que une metodología, norma, concepto y validación "
                  "profesional como una sola capa de confianza.",
        "seg": 70,
        "speech": (
            "¿Qué recibe una persona cuando pide un Dictus ARHIAX? No un "
            "documento más: una lectura ordenada del inmueble en tres "
            "dimensiones. En lo económico, una estimación referencial de valor "
            "con precio por metro cuadrado de referencia, rango, estimación "
            "central y canon cuando aplica. En lo legal, la cadena de tradición, "
            "gravámenes, limitaciones y alertas que pueden afectar la operación. "
            "En lo territorial y geodésico, la identificación espacial del "
            "predio, su lectura catastral y urbanística, los riesgos y el "
            "entorno. Y nada de esto sale de una caja negra: hay metodología, "
            "contraste normativo, un concepto consolidado y una ruta de "
            "verificación profesional. Quiero ser explícito: esto no sustituye "
            "al abogado, al avaluador ni al ingeniero. Hace algo más útil: "
            "entrega al experto un expediente ya estructurado, trazable y "
            "verificable."),
    },
    {
        "n": 3,
        "titulo": "Una nueva capacidad comercial para la inmobiliaria",
        "texto": [
            ("TRANSFORMACIÓN", "Inmueble publicado → Inmueble verificado → "
                               "Transacción mejor preparada → Crédito / cierre"),
            ("BENEFICIOS", "Confianza del comprador · Mayor conversión · Cierre "
                           "más rápido · Diferenciación comercial · Menos "
                           "reprocesos · Nuevos servicios"),
            ("CANAL 1 · VERIFICACIÓN DEL INMUEBLE", "Expediente predial previo a "
                                                    "la negociación, como "
                                                    "servicio premium."),
            ("CANAL 2 · SERVICIOS ASOCIADOS A LA TRANSACCIÓN", "Títulos, "
                                                               "asesoría "
                                                               "jurídica, "
                                                               "avalúo, crédito, "
                                                               "seguros y "
                                                               "trámites."),
            ("CANAL 3 · INFRAESTRUCTURA DE CONFIANZA B2B", "Bancos, "
                                                           "aseguradoras, "
                                                           "fondos, constructoras "
                                                           "y fiduciarias."),
        ],
        "visual": "Flujo horizontal de cuatro pasos con flechas; franja de "
                  "beneficios y tres tarjetas de canales de ingreso. Sin cifras "
                  "ni tarifas.",
        "seg": 68,
        "speech": (
            "Ahora pensemos en la inmobiliaria. Hoy su activo comercial es un "
            "inmueble publicado: fotos, metraje, precio. ARHIAX le permite "
            "ofrecer algo distinto: un inmueble verificado, con un expediente "
            "previo de confianza. Eso cambia la conversación con el comprador, "
            "reduce fricción, acelera el cierre, diferencia la vitrina y prepara "
            "el inmueble para crédito antes de que el banco lo pida. Y abre tres "
            "canales de ingreso. Primero, la verificación del inmueble como "
            "servicio premium previo a la negociación. Segundo, los servicios "
            "asociados a la transacción: estudio de títulos, asesoría jurídica, "
            "avalúo profesional, crédito y seguros. Y tercero, la infraestructura "
            "de confianza para bancos, aseguradoras, fondos y constructoras. La "
            "inmobiliaria no solo vende metros cuadrados: vende certeza."),
    },
    {
        "n": 4,
        "titulo": "La evidencia no debería empezar de cero en cada etapa",
        "texto": [
            ("FUENTES", "Registro · Catastro · Territorio · Mercado"),
            ("PROCESO", "Fuentes → ARHIAX → Evidencia verificada → Huella / "
                        "sello de integridad → Reuso"),
            ("ACTORES", "Comprador · Vendedor · Inmobiliaria · Abogado · "
                        "Avaluador · Banco · Aseguradora"),
            ("CONCEPTO CENTRAL", "Consultar una vez. Verificar. Sellar. "
                                 "Reutilizar."),
            ("TRAZABILIDAD", "Cada evidencia conserva origen, fecha y huella "
                             "digital verificable, lo que permite detectar "
                             "alteraciones y facilita su reutilización durante "
                             "la vida de la transacción."),
        ],
        "visual": "Cadena de valor de izquierda a derecha; debajo, la "
                  "constelación de actores que reutilizan la misma evidencia; "
                  "frase central en grande.",
        "seg": 70,
        "speech": (
            "Aquí está, en mi opinión, la parte más valiosa de todo esto. Cada "
            "vez que analizamos un inmueble consultamos registro, catastro, "
            "territorio y mercado. Ese trabajo debería servir más de una vez, y "
            "hoy se repite en cada etapa. ARHIAX cambia eso. Cada evidencia "
            "conserva su origen, su fecha, el método con el que se obtuvo y una "
            "huella digital verificable que permite detectar alteraciones y "
            "facilita su reutilización durante la vida de la transacción. Lo "
            "resumimos en cuatro palabras: consultar una vez, verificar, sellar "
            "y reutilizar. ¿Qué significa en la práctica? Que el comprador, el "
            "vendedor, la inmobiliaria, el abogado, el avaluador, el banco o la "
            "aseguradora no tengan que empezar de cero cada vez que el inmueble "
            "cambia de etapa."),
    },
    {
        "n": 5,
        "titulo": "De la transacción inmobiliaria al activo financiable y "
                  "asegurable",
        "texto": [
            ("OBJETIVO 1 · PROFUNDIZACIÓN DEL CRÉDITO HIPOTECARIO",
             "Mejor información → Menor incertidumbre → Expediente mejor "
             "preparado → Mayor capacidad de originación."),
            ("OBJETIVO 2 · BASES PARA EL SEGURO DE TÍTULOS",
             "Identidad + Cadena jurídica + Evidencia + Trazabilidad + "
             "Validación profesional → Infraestructura futura de asegurabilidad "
             "del título."),
            ("RED DE DESPLIEGUE", "Barranquilla · Bogotá · Medellín · Cali · "
                                  "Bucaramanga. Expansión progresiva: Pasto."),
            ("CIERRE", "ARHIAX RE no busca agregar otro trámite a la "
                       "compraventa. Busca transformar la información del "
                       "inmueble en confianza reutilizable."),
            ("CALL TO ACTION", "Seleccionemos un grupo inicial de inmuebles y "
                               "midamos impacto en confianza, conversión y "
                               "preparación para crédito."),
        ],
        "visual": "Dos tarjetas de objetivo; franja inferior con la red de "
                  "ciudades como nodos conectados; cierre y llamado a la acción "
                  "en tarjeta propia.",
        "seg": 72,
        "speech": (
            "Cerremos con la visión. ARHIAX RE persigue dos objetivos. El "
            "primero es profundizar el crédito hipotecario: mejor información "
            "significa menos incertidumbre, expedientes mejor preparados y más "
            "inmuebles y compradores que llegan listos a la financiación. El "
            "segundo es construir las bases tecnológicas y probatorias para "
            "futuros productos de seguro de títulos: identidad, cadena jurídica, "
            "evidencia, trazabilidad y validación profesional. No afirmamos que "
            "hoy emitamos ese seguro: estamos construyendo la infraestructura "
            "que lo hace posible. Empezamos en Barranquilla, con red de "
            "despliegue en Bogotá, Medellín, Cali y Bucaramanga, y expansión "
            "progresiva hacia Pasto. Y lo hacemos con una propuesta simple: no "
            "agregar otro trámite a la compraventa, sino transformar la "
            "información del inmueble en confianza reutilizable."),
    },
]

FRASE_FINAL = ("Convertimos la información del inmueble en confianza "
               "reutilizable para toda la transacción.")

# ── estilos ───────────────────────────────────────────────────────────────────
S = {
    "marca": ParagraphStyle("marca", fontName="Helvetica-Bold", fontSize=9,
                            textColor=ACCENT, leading=12),
    "item": ParagraphStyle("item", fontName="Helvetica-Bold", fontSize=8,
                           textColor=GRAY, leading=11),
    "h1": ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=26,
                         textColor=INK, leading=30),
    "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=17,
                         textColor=INK, leading=22),
    "h3": ParagraphStyle("h3", fontName="Helvetica-Bold", fontSize=10.5,
                         textColor=INK, leading=14),
    "body": ParagraphStyle("body", fontName="Helvetica", fontSize=10,
                           textColor=INK2, leading=15),
    "small": ParagraphStyle("small", fontName="Helvetica", fontSize=9,
                            textColor=GRAY, leading=13),
    "lbl": ParagraphStyle("lbl", fontName="Helvetica-Bold", fontSize=8.5,
                          textColor=ACCENT, leading=12),
    "speech": ParagraphStyle("speech", fontName="Helvetica", fontSize=9.6,
                             textColor=INK2, leading=14.4),
    "cierref": ParagraphStyle("cierref", fontName="Helvetica-Bold", fontSize=17,
                              textColor=INK, leading=24, alignment=1),
}


def _box(flowables, fill=LIGHT, pad=10):
    t = Table([[flowables]], colWidths=[17.2 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), fill),
        ("LEFTPADDING", (0, 0), (-1, -1), pad),
        ("RIGHTPADDING", (0, 0), (-1, -1), pad),
        ("TOPPADDING", (0, 0), (-1, -1), pad),
        ("BOTTOMPADDING", (0, 0), (-1, -1), pad),
        ("LINEBEFORE", (0, 0), (0, 0), 2.5, ACCENT),
    ]))
    return t


def _hline():
    t = Table([[""]], colWidths=[17.2 * cm], rowHeights=[0.4])
    t.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), 0.6, LINE)]))
    return t


def _texto_tabla(item):
    rows = [[Paragraph(f"<b>{k}</b>", S["h3"]), Paragraph(v, S["body"])]
            for k, v in item["texto"]]
    t = Table(rows, colWidths=[5.4 * cm, 11.8 * cm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, LINE),
    ]))
    return t


def build():
    doc = BaseDocTemplate(str(OUT), pagesize=A4,
                          leftMargin=2.1 * cm, rightMargin=2.1 * cm,
                          topMargin=1.7 * cm, bottomMargin=1.7 * cm,
                          title="ARHIAX RE — Presentación comercial "
                                "(entrega completa)",
                          author="ARHIAX RE")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height,
                  id="f")

    def pie(c, d):
        c.saveState()
        c.setStrokeColor(LINE)
        c.setLineWidth(0.6)
        c.line(d.leftMargin, 1.35 * cm, d.leftMargin + d.width, 1.35 * cm)
        c.setFont("Helvetica", 7.4)
        c.setFillColor(GRAY)
        c.drawString(d.leftMargin, 1.05 * cm,
                     "ARHIAX RE · Infraestructura de confianza para la "
                     "transacción inmobiliaria")
        c.drawRightString(d.leftMargin + d.width, 1.05 * cm, f"{d.page}")
        c.restoreState()

    doc.addPageTemplates([PageTemplate(id="p", frames=[frame], onPage=pie)])

    st = []

    # ── 1. TÍTULO GENERAL ──
    st.append(Paragraph("ENTREGA 1 / 7 · TÍTULO GENERAL", S["item"]))
    st.append(Spacer(1, 6))
    if LOGO.exists():
        st.append(Image(str(LOGO), width=2.6 * cm, height=2.6 * cm * 162 / 192))
        st.append(Spacer(1, 10))
    st.append(Paragraph(TITULO_GENERAL, S["h1"]))
    st.append(Spacer(1, 4))
    st.append(Paragraph(SUBTITULO, S["h2"]))
    st.append(Spacer(1, 10))
    st.append(_hline())
    st.append(Spacer(1, 12))
    st.append(Paragraph(f"<i>{BAJADA}</i>", ParagraphStyle(
        "b", parent=S["body"], fontSize=12, textColor=ACCENT)))
    st.append(Spacer(1, 10))
    st.append(Paragraph(CONTEXTO, S["body"]))
    st.append(Spacer(1, 16))
    st.append(_box([Paragraph(
        "<b>Audiencia:</b> compradores y vendedores de inmuebles · inmobiliarias "
        "· ecosistema financiero y asegurador (bancos, originadores de crédito, "
        "aseguradoras y futuros operadores de seguro de títulos).", S["small"])]))

    # ── 2..6. SLIDES ──
    for it in SLIDES:
        st.append(Spacer(1, 26))
        st.append(Paragraph(f"ENTREGA {it['n'] + 1} / 7 · SLIDE {it['n']}",
                            S["item"]))
        st.append(Spacer(1, 6))
        st.append(Paragraph(it["titulo"], S["h2"]))
        st.append(Spacer(1, 12))
        st.append(Paragraph("TEXTO", S["lbl"]))
        st.append(Spacer(1, 6))
        st.append(_texto_tabla(it))
        st.append(Spacer(1, 14))
        st.append(Paragraph("PROPUESTA VISUAL", S["lbl"]))
        st.append(Spacer(1, 4))
        st.append(Paragraph(it["visual"], ParagraphStyle(
            "pv", parent=S["small"], fontName="Helvetica-Oblique")))
        st.append(Spacer(1, 14))
        st.append(KeepTogether(_box([
            Paragraph(f"SPEECH · {it['seg']} s", S["lbl"]),
            Spacer(1, 5),
            Paragraph(it["speech"], S["speech"]),
        ], fill=colors.HexColor("#FBFBFC"))))

    # ── 7. FRASE FINAL ──
    st.append(Spacer(1, 30))
    st.append(Paragraph("ENTREGA 7 / 7 · FRASE FINAL DE CIERRE", S["item"]))
    st.append(Spacer(1, 18))
    st.append(Paragraph(f"“{FRASE_FINAL}”", S["cierref"]))
    st.append(Spacer(1, 18))
    st.append(_hline())

    doc.build(st)
    print(f"OK -> {OUT}")


if __name__ == "__main__":
    build()

# dictamen_part1_styles.py
# Estilos, colores y helpers compartidos para el Informe Base LAI (ARHIAX RE)
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import Paragraph, Spacer, HRFlowable, Table, TableStyle

# ── Paleta institucional ARHIAX ────────────────────────────────────────────────
C_AZUL_OSC   = colors.HexColor("#0D2C6B")
C_AZUL_MED   = colors.HexColor("#1B4FAF")
C_DORADO     = colors.HexColor("#C9A84C")
C_VERDE      = colors.HexColor("#1A6B3A")
C_ROJO       = colors.HexColor("#8B1A1A")
C_NARANJA    = colors.HexColor("#7A4000")
C_GRIS_TEXTO = colors.HexColor("#2D3748")
C_GRIS_CLARO = colors.HexColor("#F7F8FC")
C_BORDE      = colors.HexColor("#D0D8E8")
C_NEGRO_MONO = colors.HexColor("#0D1F3C")
C_CYAN_MONO  = colors.HexColor("#4FC3F7")
C_AMARILLO   = colors.HexColor("#F9A825")
C_ALERTA_BG  = colors.HexColor("#FEF6E4")
C_RIESGO_BG  = colors.HexColor("#FBE9E9")
C_OK_BG      = colors.HexColor("#E8F5EE")

# ── Estilos de párrafo ──────────────────────────────────────────────────────────
def build_styles():
    base = {
        "fontName": "Helvetica",
        "fontSize": 9,
        "leading": 13,
        "textColor": C_GRIS_TEXTO,
    }
    s = {}

    s["h1"] = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=18,
                              textColor=colors.white, leading=22)
    s["h2"] = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=11,
                              textColor=colors.white, leading=14)
    s["sec"] = ParagraphStyle("sec", fontName="Helvetica-Bold", fontSize=9,
                               textColor=C_AZUL_MED, leading=12,
                               spaceBefore=14, spaceAfter=4)
    s["subsec"] = ParagraphStyle("subsec", fontName="Helvetica-Bold", fontSize=8,
                                  textColor=C_AZUL_OSC, leading=11,
                                  spaceBefore=8, spaceAfter=3)
    s["body"] = ParagraphStyle("body", fontName="Helvetica", fontSize=8.5,
                                textColor=C_GRIS_TEXTO, leading=13,
                                spaceAfter=4, alignment=TA_JUSTIFY)
    s["body_bold"] = ParagraphStyle("body_bold", parent=None,
                                     fontName="Helvetica-Bold", fontSize=8.5,
                                     textColor=C_GRIS_TEXTO, leading=13)
    s["mono"] = ParagraphStyle("mono", fontName="Courier", fontSize=7,
                                textColor=C_CYAN_MONO, leading=11)
    s["mono_hash"] = ParagraphStyle("mono_hash", fontName="Courier-Bold",
                                     fontSize=7, textColor=C_AMARILLO, leading=11)
    s["label"] = ParagraphStyle("label", fontName="Helvetica-Bold", fontSize=8,
                                 textColor=C_GRIS_TEXTO, leading=11)
    s["value"] = ParagraphStyle("value", fontName="Helvetica", fontSize=8,
                                 textColor=C_GRIS_TEXTO, leading=11)
    s["footer"] = ParagraphStyle("footer", fontName="Helvetica", fontSize=7,
                                  textColor=colors.HexColor("#718096"),
                                  alignment=TA_CENTER, leading=10)
    s["alert_rojo"] = ParagraphStyle("alert_rojo", fontName="Helvetica-Bold",
                                      fontSize=8.5, textColor=C_ROJO, leading=12)
    s["alert_naranja"] = ParagraphStyle("alert_naranja", fontName="Helvetica-Bold",
                                         fontSize=8.5, textColor=C_NARANJA, leading=12)
    s["alert_verde"] = ParagraphStyle("alert_verde", fontName="Helvetica-Bold",
                                       fontSize=8.5, textColor=C_VERDE, leading=12)
    s["center"] = ParagraphStyle("center", fontName="Helvetica", fontSize=8,
                                  textColor=C_GRIS_TEXTO, leading=11,
                                  alignment=TA_CENTER)
    return s

# ── Helpers de layout ───────────────────────────────────────────────────────────
def hr(color=None, thickness=1):
    return HRFlowable(width="100%", thickness=thickness,
                      color=color or C_BORDE, spaceAfter=4, spaceBefore=2)

def sp(h=0.2):
    from reportlab.lib.units import cm
    return Spacer(1, h * 28.35)

def section_header(title, s):
    return Paragraph(title.upper(), s["sec"])

def data_table(rows_kv, s, col_w=None):
    """rows_kv: list of (key, value) tuples"""
    data = [[Paragraph(f"<b>{k}</b>", s["label"]),
             Paragraph(str(v), s["value"])] for k, v in rows_kv]
    t = Table(data, colWidths=col_w or ["40%", "60%"])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), C_GRIS_CLARO),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1),
         [colors.white, colors.HexColor("#F0F4FB")]),
        ("GRID", (0, 0), (-1, -1), 0.4, C_BORDE),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return t

def badge_table(items, s):
    """items: list of (label, value, bg_color, text_color)"""
    data = []
    row = []
    for i, (label, value, bg, tc) in enumerate(items):
        cell_content = [
            Paragraph(f"<b>{value}</b>",
                      ParagraphStyle("bv", fontName="Helvetica-Bold",
                                     fontSize=14, textColor=tc,
                                     alignment=TA_CENTER, leading=16)),
            Paragraph(label,
                      ParagraphStyle("bl", fontName="Helvetica", fontSize=7,
                                     textColor=tc, alignment=TA_CENTER,
                                     leading=9, spaceAfter=0)),
        ]
        row.append(cell_content)
        if (i + 1) % 4 == 0:
            data.append(row)
            row = []
    if row:
        while len(row) < 4:
            row.append([Paragraph("", s["body"])])
        data.append(row)

    col_w = ["25%"] * 4
    t = Table(data, colWidths=col_w)
    style_cmds = [
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, C_BORDE),
    ]
    for i, (_, _, bg, _) in enumerate(items):
        col = i % 4
        row_i = i // 4
        style_cmds.append(("BACKGROUND", (col, row_i), (col, row_i), bg))
    t.setStyle(TableStyle(style_cmds))
    return t

# -*- coding: utf-8 -*-
"""DICTUS 2.0 — EXECUTIVE RENDERER (§E–§AI).

Convierte el `ExecutiveDocumentModel` (`dictus_manifiesto.construir_documento_maestro`)
en un **documento ejecutivo de decisión de 6 páginas** (A4 vertical). Los anexos con el
detalle técnico completo se adjuntan aparte, tal cual: **no se elimina información**.

Reglas que el render cumple (y que las pruebas bloquean):
  · Página 1 se entiende SIN leer las demás: qué inmueble, cuánto vale, qué problemas
    tiene, a quién afectan, qué debe hacerse y qué tan confiable es la información.
  · Los hallazgos viven en la página 1 con `affected_parties` e `impact_by_party`.
  · Los atributos urbanísticos pasan por el **Urban Consistency Gate**: si el expediente
    produjo valores distintos sin explicación, NO se imprime la cifra como hecho (se
    declara el conflicto).
  · **Un solo hash maestro visible** (`DICTUS_MASTER_HASH`), abreviado en el sello y en
    el pie de todas las páginas. El hash del PDF NO se imprime aquí.
  · Nada de falsa precisión: `$0`, `0%`, `N/D` mudo no existen; se declara el estado y
    el motivo.
  · Lo técnico (URLs, feature_id, parser_version, snapshots, receipts completos, hashes
    individuales) NO entra al cuerpo: va a los anexos.
"""
from __future__ import annotations

import datetime
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from reportlab.lib.colors import HexColor, white
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas

from dictus_historia import (ATRIBUTOS_URBANISTICOS, CAMBIO_CON_FUENTE,
                             HISTORICAL_CONFLICT, REQUIERE_VALIDACION, SIN_DATO,
                             VERIFICADO, gate_urbanistico)

W, H = 595.28, 841.89          # A4 vertical
M = 36.0
ANCHO = W - 2 * M
TOP = H - M

# Paleta mineral (misma familia que el resto del producto: tinta + marfil + oro)
INK = HexColor("#0B1C2B")
INK_2 = HexColor("#16303F")
INK_3 = HexColor("#1B3A50")
HAIR = HexColor("#D8D3C8")
HAIR_2 = HexColor("#EAE6DD")
CARD = HexColor("#FFFFFF")
PAPER = HexColor("#F5F2EC")
TEXT = HexColor("#16222E")
TEXT_2 = HexColor("#4C5A66")
TEXT_3 = HexColor("#7C8792")
GOLD = HexColor("#A97F2E")
GOLD_2 = HexColor("#D8C08A")

OK_BG, OK_BD, OK_FG = HexColor("#EAF2EC"), HexColor("#BFD3C5"), HexColor("#2C6244")
WARN_BG, WARN_BD, WARN_FG = HexColor("#F8F2E4"), HexColor("#DCCBA6"), HexColor("#7A5A12")
ERR_BG, ERR_BD, ERR_FG = HexColor("#FAECEC"), HexColor("#E2BFBF"), HexColor("#8C2E2E")
INFO_BG, INFO_BD, INFO_FG = HexColor("#EDF0F4"), HexColor("#C8D1DA"), HexColor("#3E4A5A")

F, FB, FO = "Helvetica", "Helvetica-Bold", "Helvetica-Oblique"

TOTAL_EJECUTIVO = 6
VIOLACIONES: List[str] = []

# Arquitectura APROBADA del entregable (§4 de DICTUS 2.0B-R1). El índice es la
# página (1-based) y el valor su título EXACTO: la página N dice, y solo, el título N.
TITULOS_PAGINA = (
    "RESUMEN DE DECISIÓN DEL INMUEBLE",
    "TÍTULOS Y CONDICIONES JURÍDICAS",
    "CONTRAPARTES Y PREPARACIÓN DE OPERACIÓN",
    "POT, USO, EDIFICABILIDAD Y RIESGOS",
    "ENTORNO, EQUIPAMIENTO Y ASOLEAMIENTO",
    "IDENTIDAD Y VALOR",
)

# Nombres visibles de las cuatro tarjetas de equipamiento (§10). Las claves del
# estado viajan sin tilde (Salud/Educacion/Comercio/Recreacion) para que el motor no
# dependa de la ortografía del rótulo.
ROTULO_CATEGORIA = {
    "SALUD": "Salud",
    "EDUCACION": "Educación",
    "COMERCIO": "Comercio",
    "RECREACION": "Recreación",
}

# Patrones que NUNCA pueden imprimirse en el cuerpo ejecutivo (§8): si el sellado
# de evidencia falla, el usuario lee «EVIDENCIA NO SELLADA», no una traza.
_FUGAS = ("ARHIAX_EVIDENCE_HMAC_KEY", "RuntimeError", "Traceback", "hmac", "stack trace")


def limpio(valor, hueco="NO DISPONIBLE") -> str:
    """Texto del documento saneado: sin fugas técnicas y sin vacíos mudos.

    Además de sanear, esta función es el punto único por el que pasa todo texto que
    imprimen el sello, la traza y las páginas ejecutivas, de modo que una excepción
    del sellado HMAC no pueda llegar al PDF entregado.
    """
    s = _v(valor, hueco)
    if any(f.lower() in s.lower() for f in _FUGAS):
        return "EVIDENCIA NO SELLADA"
    return s


# ── primitivas ────────────────────────────────────────────────────────────────
def txt(c, x, y, s, font=F, size=9, color=TEXT, align="left", esp=0.0):
    """Texto del documento.

    NOTA de diseño: el parámetro `esp` (espaciado entre letras) se acepta por
    compatibilidad de firma pero **no se aplica**. Un documento con espaciado falso
    deja de ser extraíble y buscable («DECISIÓN» se lee «D EC I S I Ó N»), y este
    expediente debe poder auditarse: la jerarquía visual se logra con tamaño, color y
    mayúsculas, no rompiendo la cadena de texto.
    """
    c.setFont(font, size)
    c.setFillColor(color)
    s = str(s)
    if align == "right":
        c.drawRightString(x, y, s)
    elif align == "center":
        c.drawCentredString(x, y, s)
    else:
        c.drawString(x, y, s)


def wrap(c, x, y, s, font=F, size=9, color=TEXT_2, maxw=300, leading=None,
         align="left", esp=0.0):
    leading = leading or size * 1.35
    lineas = simpleSplit(str(s), font, size, maxw)
    for i, ln in enumerate(lineas):
        txt(c, x, y - i * leading, ln, font, size, color, align, esp)
    return y - (len(lineas) - 1) * leading


def panel(c, x, y, w, h, fill=CARD, stroke=HAIR):
    c.setLineWidth(0.8)
    c.setFillColor(fill)
    c.setStrokeColor(stroke)
    c.rect(x, y, w, h, stroke=1, fill=1)


def banda(c, x, y, w, h, fill=INK):
    c.setFillColor(fill)
    c.rect(x, y, w, h, stroke=0, fill=1)


def rule(c, x1, y1, x2, y2, color=HAIR, lw=0.7):
    c.setStrokeColor(color)
    c.setLineWidth(lw)
    c.line(x1, y1, x2, y2)


def chip(c, x, y, s, clase="info", size=7.4, h=14, pad=6):
    parejas = {"ok": (OK_BG, OK_BD, OK_FG), "warn": (WARN_BG, WARN_BD, WARN_FG),
               "err": (ERR_BG, ERR_BD, ERR_FG), "info": (INFO_BG, INFO_BD, INFO_FG),
               "ink": (INK, INK, white), "oro": (GOLD, GOLD, white)}
    bg, bd, fg = parejas.get(clase, parejas["info"])
    w = c.stringWidth(s, FB, size) + 2 * pad
    c.setFillColor(bg)
    c.setStrokeColor(bd)
    c.setLineWidth(0.7)
    c.rect(x, y, w, h, stroke=1, fill=1)
    txt(c, x + pad, y + (h - size) / 2 + 1.2, s, FB, size, fg)
    return w


def chip_estado(c, x, y, estado: str):
    """Estado de verdad -> chip. La traducción es conservadora y cerrada."""
    clase, etiqueta = _estado_legible(estado)
    return chip(c, x, y, etiqueta, clase)


# Estados del vocabulario de coherencia -> (clase visual, etiqueta legible).
_ESTADOS_VISUALES = {
    VERIFICADO: ("ok", "VERIFICADO"),
    CAMBIO_CON_FUENTE: ("info", "VERIFICADO · CAMBIÓ CON FUENTE"),
    REQUIERE_VALIDACION: ("warn", "REQUIERE VALIDACIÓN"),
    HISTORICAL_CONFLICT: ("err", "CONFLICTO HISTÓRICO"),
    "CON_CONDICIONES": ("warn", "CON CONDICIONES"),
    "REQUIERE_REVISION": ("warn", "REQUIERE REVISIÓN"),
    "DISPONIBLE": ("ok", "DISPONIBLE"),
    "NO_DISPONIBLE": ("warn", "NO DISPONIBLE"),
    "INCOMPLETO": ("warn", "EXPEDIENTE INCOMPLETO"),
    "PREPARADA": ("ok", "INFORMACIÓN PREPARADA PARA EVALUACIÓN"),
    "COINCIDENCIA": ("err", "COINCIDENCIA REQUIERE REVISIÓN"),
    "SIN_COINCIDENCIAS": ("ok", "SIN COINCIDENCIAS RELEVANTES"),
    "INCOMPLETA": ("warn", "VERIFICACIÓN INCOMPLETA"),
    SIN_DATO: ("info", "SIN DATO"),
}

# Rótulo COMPACTO para las tarjetas de indicador: la etiqueta larga no cabe en un
# quinto de página y un chip que se desborda invade la tarjeta vecina (se veía
# «RELEVANTES» encima de «REQUIERE»). El texto completo sigue en la matriz de
# screening (página 3), que es donde se acredita el resultado.
_ESTADOS_COMPACTOS = {
    CAMBIO_CON_FUENTE: "CAMBIÓ CON FUENTE",
    "SIN_COINCIDENCIAS": "SIN COINCIDENCIAS",
    "INCOMPLETA": "INCOMPLETA",
    "PREPARADA": "PREPARADA",
    "INCOMPLETO": "INCOMPLETO",
}


def _estado_legible(estado: str):
    return _ESTADOS_VISUALES.get(estado, ("info", str(estado)))


def caja_estado(c, x, y, w, estado: str, size=6.4, h=13):
    """Etiqueta de estado AJUSTADA al ancho de su tarjeta.

    Se reduce el tamaño de letra (nunca por debajo de 5.0) hasta que el rótulo cabe:
    un estado no puede imprimirse encima del contenido vecino.
    """
    clase, etiqueta = _estado_legible(estado)
    etiqueta = _ESTADOS_COMPACTOS.get(estado, etiqueta)
    bg, bd, fg = {"ok": (OK_BG, OK_BD, OK_FG), "warn": (WARN_BG, WARN_BD, WARN_FG),
                  "err": (ERR_BG, ERR_BD, ERR_FG), "info": (INFO_BG, INFO_BD, INFO_FG),
                  "ink": (INK, INK, white), "oro": (GOLD, GOLD, white)}[clase]
    while size > 5.0 and c.stringWidth(etiqueta, FB, size) + 8 > w:
        size -= 0.15
    c.setFillColor(bg)
    c.setStrokeColor(bd)
    c.setLineWidth(0.7)
    c.rect(x, y - h, w, h, stroke=1, fill=1)
    txt(c, x + 4, y - h + (h - size) / 2 + 1.0, etiqueta, FB, size, fg)
    return h


def ajustar(c, texto, fuente, size, maxw, minimo=6.0):
    """Texto que CABE en su columna: reduce tamaño y, si aún no cabe, recorta con «…».

    Devuelve `(texto, tamaño)`. Se usa en las filas de columnas fijas (identidad,
    norma urbanística), donde un valor largo se imprimía debajo del chip de estado.
    """
    s = str(texto)
    _size = size
    while _size > minimo and c.stringWidth(s, fuente, _size) > maxw:
        _size -= 0.2
    if c.stringWidth(s, fuente, _size) > maxw:
        while len(s) > 4 and c.stringWidth(s + "…", fuente, _size) > maxw:
            s = s[:-1]
        s = s.rstrip() + "…"
    return s, _size


def fit(nombre, y_final, y_limite):
    if y_final < y_limite - 1:
        VIOLACIONES.append(f"{nombre}: desborda {y_limite - y_final:.0f} pt")


def _v(valor, hueco="NO DISPONIBLE") -> str:
    """Valor legible: nunca un guion mudo ni un cero falso."""
    if valor is None or valor == "" or (isinstance(valor, str) and not valor.strip()):
        return hueco
    return str(valor)


def _corto(texto, limite: int) -> str:
    """Recorta sin mutilar: si se recorta, se ve que se recortó (…)."""
    s = str(texto)
    return s if len(s) <= limite else s[:limite - 1].rstrip() + "…"


# ── cromo de página ───────────────────────────────────────────────────────────
def cabecera(c, modelo, pagina, subtitulo=None):
    """Cromo de página. El subtítulo es el TÍTULO APROBADO de esa página: así el
    encabezado y el cuerpo dicen lo mismo y el contrato de §4 es verificable."""
    subtitulo = subtitulo or TITULOS_PAGINA[pagina - 1]
    banda(c, 0, H - 54, W, 54, INK)
    txt(c, M, H - 26, "DICTUS", FB, 15, white, esp=1.4)
    txt(c, M + 52, H - 26, subtitulo, F, 7.4, GOLD_2, esp=0.8)
    banda(c, M, H - 40, 52, 2, GOLD)
    ident = (modelo.get("document_identity") or {})
    txt(c, W - M, H - 24, str(ident.get("dictus_id") or ""), FB, 8, white, "right")
    txt(c, W - M, H - 36, f"Página {pagina} de {TOTAL_EJECUTIVO} · ejecutivo",
        F, 7, GOLD_2, "right")


def pie(c, modelo, pagina):
    mh = str(modelo.get("master_hash_abreviado") or "")
    ev = (modelo.get("evidence_manifest") or {})
    rule(c, M, 40, W - M, 40, HAIR)
    txt(c, M, 29, f"DICTUS_MASTER_HASH {mh}", FB, 7, TEXT_2, esp=0.4)
    txt(c, M, 20, f"Evidencias {ev.get('evidence_count')} · sello {limpio(ev.get('estado'))} · "
                  f"verificación por DICTUS ID (Anexo G)", F, 6.6, TEXT_3)
    txt(c, W - M, 20, "El hash del archivo PDF no es el hash maestro: consta en el anexo G.",
        F, 6.6, TEXT_3, "right")


def traza(c, y, fuentes: Iterable[str], fecha: str, estado: str, n_ev: int) -> float:
    """Bloque TRAZABILIDAD (§M): lenguaje comprensible, sin códigos técnicos."""
    h = 40
    panel(c, M, y - h, ANCHO, h, PAPER, HAIR)
    txt(c, M + 8, y - 13, "TRAZABILIDAD", FB, 7, GOLD, esp=1.0)
    # La línea de fuentes se ajusta: la derecha lleva el aviso de inclusión en el
    # hash maestro y no puede quedar debajo del texto de fuentes.
    _fuentes, _fsz = ajustar(c, "Fuentes principales: " + ", ".join(list(fuentes)[:4]),
                             F, 7.4, ANCHO - 16 - 210)
    txt(c, M + 8, y - 25, _fuentes, F, _fsz, TEXT_2)
    _consulta, _csz = ajustar(c, f"Consulta: {fecha or 'no declarada'} · "
                                 f"Estado: {limpio(estado)} · Evidencias: {n_ev}",
                              F, 7.4, ANCHO - 16 - 210)
    txt(c, M + 8, y - 35, _consulta, F, _csz, TEXT_2)
    txt(c, W - M - 8, y - 25, "Evidencia INCLUIDA EN HASH MAESTRO DICTUS", FB, 7, TEXT_2, "right")
    txt(c, W - M - 8, y - 35, "Detalle técnico: Anexos", FO, 7, TEXT_3, "right")
    return y - h - 8


def titulo_seccion(c, y, texto, kicker="", upper=True):
    """Rótulo de sección: antetítulo (kicker) + título. El antetítulo va en un cuerpo
    menor y con separación suficiente para que las cajas de texto NO se toquen.

    `upper=False` conserva la caja del antetítulo cuando es una FRASE (p. ej. «9
    hallazgos materiales · todos en esta página»): leerla en mayúsculas la vuelve
    ilegible y además impide citar el término tal como se escribe.
    """
    if kicker:
        txt(c, M, y, kicker.upper() if upper else kicker, FB, 6.6, GOLD, esp=0.8)
        y -= 18
    txt(c, M, y, texto, FB, 13, INK)
    rule(c, M, y - 6, W - M, y - 6, HAIR)
    return y - 20


# ── Página 1 · RESUMEN DE DECISIÓN ────────────────────────────────────────────
def _general_de_respaldo(ident, urb, ctx) -> List[Tuple[str, str]]:
    """Bloque A cuando el estado no trae el bloque ya armado (compatibilidad)."""
    return [
        ("Dirección", _v(ident.get("direccion_normalizada") or ident.get("direccion_raw"),
                         "no declarada")),
        ("Matrícula", _v(ident.get("folio"), "no declarada")),
        ("Ciudad", _v(ctx.get("ciudad"), "no declarada")),
        ("Barrio", _v(urb.get("barrio"), "no declarado")),
        ("Área", f"{ctx.get('area')} m²" if ctx.get("area") else "no declarada"),
        ("Uso", _v(ctx.get("uso"), "no declarado")),
        ("Régimen", _v(ctx.get("regimen"), "no declarado")),
        ("Valor estimado", _v(ctx.get("valor_estimado"), "no disponible")),
    ]


def pagina1(c, modelo, hallazgos, indicadores, ctx):
    cabecera(c, modelo, 1)
    ident = modelo.get("canonical_property_identity") or {}
    urb = modelo.get("urban_context") or {}
    y = H - 74

    txt(c, M, y, TITULOS_PAGINA[0], FB, 13, INK)
    rule(c, M, y - 6, W - M, y - 6, HAIR)
    y -= 22
    y = wrap(c, M, y, limpio(ident.get("direccion_normalizada") or ident.get("direccion_raw"),
                             "Dirección no declarada"), FB, 12, INK, ANCHO, leading=14)
    y -= 12

    # ── BLOQUE A · INFORMACIÓN GENERAL (§6) ───────────────────────────────────
    y = titulo_seccion(c, y, "INFORMACIÓN GENERAL", "bloque a")
    campos = list(ctx.get("general") or _general_de_respaldo(ident, urb, ctx))
    cw = (ANCHO - 3 * 5) / 4
    for i, (etiqueta, valor) in enumerate(campos[:8]):
        col, fila = i % 4, i // 4
        x = M + col * (cw + 5)
        yt = y - fila * 29
        panel(c, x, yt - 26, cw, 26, CARD)
        txt(c, x + 5, yt - 10, str(etiqueta).upper(), FB, 5.9, TEXT_3, esp=0.4)
        txt(c, x + 5, yt - 21, _corto(valor, 30), FB, 7.8, INK)
    y -= (2 * 29) + 8

    # ── BLOQUE B · ESTADO GENERAL (§6): cinco indicadores de decisión ────────
    y = titulo_seccion(c, y, "ESTADO GENERAL", "cinco indicadores")
    cw = (ANCHO - 4 * 6) / 5
    for i, (nombre, estado, motivo) in enumerate(indicadores):
        x = M + i * (cw + 6)
        panel(c, x, y - 68, cw, 68)
        banda(c, x, y - 3, cw, 3, GOLD if estado in (VERIFICADO, "DISPONIBLE") else INK_3)
        txt(c, x + 6, y - 15, nombre.upper(), FB, 6.6, TEXT_3, esp=0.6)
        # La etiqueta de estado se AJUSTA a la tarjeta: no puede invadir la vecina.
        caja_estado(c, x + 5, y - 31, cw - 10, estado, 6.4, 13)
        wrap(c, x + 6, y - 49, motivo, F, 6.2, TEXT_2, cw - 12, leading=7.6)
    y -= 76

    # ── BLOQUE C · HALLAZGOS (§6): todos, con severidad, actor y acción ──────
    y = titulo_seccion(c, y, "HALLAZGOS",
                       f"{len(hallazgos)} hallazgos materiales · todos en esta página",
                       upper=False)
    cw = (ANCHO - 6) / 2
    panel(c, M, y - 13, ANCHO, 13, PAPER, HAIR)
    for col in range(2):
        x = M + col * (cw + 6)
        txt(c, x + 7, y - 9, "SEVERIDAD", FB, 5.6, TEXT_3, esp=0.4)
        txt(c, x + 48, y - 9, "HALLAZGO", FB, 5.6, TEXT_3, esp=0.4)
    y -= 13
    alto_fila = 38
    for i, h in enumerate(hallazgos):
        col, fila = i % 2, i // 2
        x = M + col * (cw + 6)
        yt = y - fila * (alto_fila + 3)
        panel(c, x, yt - alto_fila, cw, alto_fila)
        sev = str(h.get("severidad", "")).upper()
        color = {"ALTO": ERR_FG, "MEDIO": WARN_FG, "INFORMATIVO": OK_FG}.get(sev, TEXT)
        banda(c, x, yt - alto_fila, 3, alto_fila, color)
        chip(c, x + 7, yt - 13, sev[:7] or "—",
             {"ALTO": "err", "MEDIO": "warn", "INFORMATIVO": "ok"}.get(sev, "info"), 5.8, 11, 5)
        # El título va a UNA línea ajustada: la fila tiene offsets fijos para
        # afectados y acción, y un título de dos líneas se imprimía encima de ellos.
        _tit, _tsz = ajustar(c, f"{_v(h.get('codigo'), '')} {_v(h.get('titulo'), '')}",
                             FB, 7.2, cw - 54)
        txt(c, x + 47, yt - 10, _tit, FB, _tsz, INK)
        afectados = ", ".join((h.get("afectados") or [])[:3]) or "sin actores declarados"
        txt(c, x + 7, yt - 22, f"AFECTA A: {afectados}"[:112], F, 6.0, TEXT_3)
        wrap(c, x + 7, yt - 31, ("ACCIÓN: " + _v(h.get("accion"), "por definir"))[:128],
             F, 6.0, TEXT_2, cw - 14, leading=7.0)
    y -= ((len(hallazgos) + 1) // 2) * (alto_fila + 3) + 6

    # ── BLOQUE D · SELLO GLOBAL (§6) ──────────────────────────────────────────
    # Si los hallazgos consumieron la página, el sello NO se imprime encima: se
    # declara el desborde (la auditoría de la entrega lo convierte en FAIL).
    if y - 68 < 118:
        VIOLACIONES.append(f"P1 sello global sin espacio ({y - 68:.0f} pt útiles)")
    y = max(y, 156)
    ev = modelo.get("evidence_manifest") or {}
    di = modelo.get("document_identity") or {}
    sello_h = 68
    y = titulo_seccion(c, y, "SELLO GLOBAL", "trazabilidad del expediente") + 4
    panel(c, M, y - sello_h, ANCHO, sello_h, INK, INK)
    banda(c, M, y - sello_h, 4, sello_h, GOLD)
    txt(c, M + 12, y - 14, "DICTUS ID", FB, 6.4, GOLD_2, esp=0.6)
    txt(c, M + 12, y - 27, limpio(di.get("dictus_id")), FB, 10, white)
    txt(c, M + 12, y - 40, f"Fecha: {_v(str(di.get('generated_at') or '')[:10], 'sin fecha declarada')}",
        F, 7, GOLD_2)
    txt(c, M + 12, y - 50, f"Evidencias: {ev.get('evidence_count')} · "
                           f"Estado: {limpio(ev.get('estado'))}", F, 7, GOLD_2)
    txt(c, M + 12, y - 60, "Cadena de custodia del expediente: Anexo G.", FO, 6.4, GOLD_2)
    txt(c, M + 250, y - 14, "DICTUS_MASTER_HASH", FB, 6.4, GOLD_2, esp=0.6)
    _hash = str(modelo.get("master_hash") or "")
    txt(c, M + 250, y - 28, _hash[:26], "Courier-Bold", 8, white)
    txt(c, M + 250, y - 40, f"…{_hash[26:52]}", "Courier-Bold", 8, GOLD_2)
    wrap(c, W - M - 132, y - 14,
         "Verificación: DICTUS ID + hash maestro abreviado. El hash del archivo PDF "
         "consta aparte (Anexo G).", FO, 6.2, GOLD_2, 124, leading=7.4)
    y -= sello_h + 8

    y = traza(c, y, ev.get("fuentes") or [], str(di.get("generated_at") or "")[:10],
              limpio(ev.get("estado")), int(ev.get("evidence_count") or 0))
    txt(c, M, y - 2, "Alcance y limitaciones del documento: ver Anexo H.", FO, 7, TEXT_3)
    fit("P1 cierre", y, 60)
    pie(c, modelo, 1)


# ── Página 2 · TÍTULOS Y CONDICIONES JURÍDICAS ────────────────────────────────
def pagina2(c, modelo, legal, ctx):
    cabecera(c, modelo, 2)
    y = H - 74
    y = titulo_seccion(c, y, TITULOS_PAGINA[1],
                       "¿qué puede impedir o condicionar la transacción?")

    y = wrap(c, M, y, "TITULARIDAD", FB, 8, GOLD, ANCHO, esp=0.8) - 14
    if legal.get("titulares"):
        for t in legal["titulares"][:4]:
            panel(c, M, y - 30, ANCHO, 30, CARD)
            txt(c, M + 8, y - 11, _v(t.get("nombre")), FB, 9, INK)
            txt(c, M + 8, y - 21, f"{_v(t.get('tipo'), 'tipo no declarado')} · "
                                  f"{_v(t.get('documento'), 'documento no declarado')} · "
                                  f"participación {_v(t.get('participacion'), 'no declarada')}",
                F, 7.2, TEXT_2)
            txt(c, M + 8, y - 28, f"Forma de adquisición: "
                                  f"{_v(t.get('adquisicion'), 'no declarada en el folio')}",
                F, 6.6, TEXT_3)
            chip(c, W - M - 8 - 96, y - 20, _v(t.get("verificacion", "")).upper() or "POR VERIFICAR",
                 "ok" if t.get("verificacion") == VERIFICADO else "warn", 6.6, 13, 5)
            y -= 34
    else:
        panel(c, M, y - 34, ANCHO, 34, PAPER, HAIR)
        wrap(c, M + 8, y - 14, "Titularidad no declarada en esta ejecución.", F, 8, WARN_FG,
             ANCHO - 16)
        wrap(c, M + 8, y - 26, "Acción: aportar el certificado de tradición y libertad "
                               "vigente (Anexo A).", F, 7.4, TEXT_2, ANCHO - 16)
        y -= 42

    y = wrap(c, M, y - 4, "TRADICIÓN Y GRAVÁMENES", FB, 8, GOLD, ANCHO, esp=0.8) - 14
    for g in (legal.get("gravamenes") or []):
        panel(c, M, y - 30, ANCHO, 30, CARD)
        banda(c, M, y - 30, 3, 30, ERR_FG if g.get("severidad") == "ALTO" else WARN_FG)
        txt(c, M + 8, y - 12, _v(g.get("titulo")), FB, 8.6, INK)
        wrap(c, M + 8, y - 22, _v(g.get("detalle")), F, 7.2, TEXT_2, ANCHO - 130, leading=8.4)
        accion = g.get("accion")
        if accion:
            txt(c, W - M - 8, y - 12, "Acción", FB, 6.4, TEXT_3, "right", esp=0.6)
            wrap(c, W - M - 120, y - 22, accion, F, 7, TEXT_2, 112, leading=8.2)
        y -= 34
    if not legal.get("gravamenes"):
        panel(c, M, y - 28, ANCHO, 28, PAPER, HAIR)
        txt(c, M + 8, y - 17, "Sin cargas declaradas en esta ejecución.", F, 8, TEXT_2)
        y -= 36

    y = wrap(c, M, y - 2, "QUÉ DEBE HACERSE PARA CERRAR LA OPERACIÓN", FB, 8, GOLD,
             ANCHO, esp=0.8) - 14
    for i, cond in enumerate((legal.get("condiciones") or [])[:5], 1):
        txt(c, M, y, f"{i}.", FB, 8, GOLD)
        y = wrap(c, M + 14, y, cond, F, 8, TEXT_2, ANCHO - 14, leading=9.6) - 8
    if not legal.get("condiciones"):
        y = wrap(c, M, y, "No hay condiciones registradas: el expediente no declara "
                          "cargas activas ni requerimientos pendientes.", F, 8, TEXT_2,
                 ANCHO, leading=9.6) - 8

    y = wrap(c, M, y, "Ver detalle registral completo — Anexo A.", FO, 7.4, TEXT_3, ANCHO) - 10
    # El estado que se declara es el del MANIFEST de la corrida: una sola verdad por
    # documento (la traza no puede afirmar «VERIFICADO» mientras el sello dice parcial).
    y = traza(c, y, ["Registro (SNR/CTL)", "Titulux"],
              str((modelo.get("evidence_manifest") or {}).get("generated_at") or "")[:10],
              limpio((modelo.get("evidence_manifest") or {}).get("estado")),
              int((modelo.get("evidence_manifest") or {}).get("evidence_count") or 0))
    fit("P2 cierre", y, 52)
    pie(c, modelo, 2)


# ── Página 3 · CONTRAPARTES Y PREPARACIÓN DE OPERACIÓN ────────────────────────
def _encabezado_columnas(c, x, y, texto, ancho, size=5.6):
    """Rótulo de columna en hasta dos líneas (las listas se llaman por su nombre)."""
    partes = str(texto).split(" ")
    if len(partes) > 1 and c.stringWidth(texto, FB, size) > ancho - 4:
        medio = len(partes) // 2
        lineas = [" ".join(partes[:medio]), " ".join(partes[medio:])]
    else:
        lineas = [str(texto)]
    for i, ln in enumerate(lineas[:2]):
        txt(c, x, y + i * 6.4, ln, FB, size, TEXT_3, esp=0.3)


def pagina3(c, modelo, contrapartes, preparacion):
    cabecera(c, modelo, 3)
    y = H - 74
    y = titulo_seccion(c, y, TITULOS_PAGINA[2], "contrapartes y listas restrictivas")
    scr = modelo.get("screening_summary") or {}

    # Columnas DINÁMICAS: las listas realmente utilizadas (nunca hardcodeadas). El
    # rótulo es el NOMBRE de la lista; la sigla se usa solo como clave de datos.
    listas = list(contrapartes.get("listas") or [])
    columnas = list(contrapartes.get("columnas") or listas)
    # Reparto EXACTO del ancho: ninguna columna puede invadir la siguiente. El
    # rótulo de resultado es corto a propósito; la frase completa consta en la
    # tarjeta de contrapartes (página 1) y en el acta del screening (Anexo D).
    a_sujeto, a_rol, a_doc, a_res = 118.0, 90.0, 80.0, 115.0
    a_lista = (ANCHO - a_sujeto - a_rol - a_doc - a_res) / max(1, len(listas))
    x_rol = M + a_sujeto
    x_doc = x_rol + a_rol
    x_listas = x_doc + a_doc

    panel(c, M, y - 20, ANCHO, 20, PAPER, HAIR)
    txt(c, M + 6, y - 9, "SUJETO", FB, 6.2, TEXT_3, esp=0.5)
    txt(c, x_rol + 4, y - 9, "ROL", FB, 6.2, TEXT_3, esp=0.5)
    txt(c, x_doc + 4, y - 9, "DOCUMENTO", FB, 6.2, TEXT_3, esp=0.5)
    for i, li in enumerate(columnas):
        _encabezado_columnas(c, x_listas + i * a_lista + 4, y - 15, str(li).upper(), a_lista)
    txt(c, W - M - 6, y - 9, "RESULTADO", FB, 6.2, TEXT_3, "right", esp=0.5)
    y -= 20

    for s in (contrapartes.get("sujetos") or [])[:6]:
        alto = 32
        panel(c, M, y - alto, ANCHO, alto, CARD)
        wrap(c, M + 6, y - 12, _v(s.get("nombre")), FB, 8, INK, a_sujeto - 12, leading=9.4)
        _rol, _rol_sz = ajustar(c, _v(s.get("rol")), F, 7, a_rol - 8)
        txt(c, x_rol + 4, y - 12, _rol, F, _rol_sz, TEXT_2)
        _doc, _doc_sz = ajustar(c, _v(s.get("documento"), "no declarado"), F, 7, a_doc - 8)
        txt(c, x_doc + 4, y - 12, _doc, F, _doc_sz, TEXT_2)
        for i, li in enumerate(listas):
            estado = (s.get("por_lista") or {}).get(li) or "SIN_DATO"
            chip(c, x_listas + i * a_lista + 3, y - 19,
                 {"SIN_COINCIDENCIAS": "SIN COINC.", "COINCIDENCIA": "COINCIDE",
                  "INCOMPLETA": "NO CONSULT.", "SIN_DATO": "NO CONSULT."}.get(estado, estado)[:11],
                 {"SIN_COINCIDENCIAS": "ok", "COINCIDENCIA": "err",
                  "INCOMPLETA": "warn"}.get(estado, "info"), 5.2, 12, 3)
        resultado = s.get("resultado") or "SIN_DATO"
        chip(c, W - M - 6 - 108, y - 19,
             {"SIN_COINCIDENCIAS": "SIN COINCIDENCIAS",
              "COINCIDENCIA": "COINCIDENCIA",
              "INCOMPLETA": "INCOMPLETA"}.get(resultado, "SIN DATO"),
             {"SIN_COINCIDENCIAS": "ok", "COINCIDENCIA": "err"}.get(resultado, "warn"), 5.6, 12, 4)
        y -= alto + 4

    # Nombres completos de las listas consultadas (§8): la sigla de la columna no
    # basta para acreditar QUÉ lista se consultó.
    detalle_listas = contrapartes.get("listas_detalle") or []
    if detalle_listas:
        y = wrap(c, M, y - 2,
                 "Listas efectivamente consultadas: "
                 + "; ".join(f"{d.get('sigla')} = {d.get('nombre')}" for d in detalle_listas)
                 + ".", F, 6.8, TEXT_2, ANCHO, leading=8.2) - 6

    y -= 4
    y = titulo_seccion(c, y, "Estado del screening", "cobertura y evidencia")
    _ev = modelo.get("evidence_manifest") or {}
    scr_evid = (f"{_v(scr.get('evidence_created_count') or scr.get('evidence_created'), '0')}/"
                f"{_v(scr.get('evidence_expected_count') or scr.get('evidence_expected'), '—')}")
    metricas = [
        ("Sujetos declarados", _v(scr.get("subjects_declared"), "—")),
        ("Sujetos revisados", _v(scr.get("subjects_screened"), "—")),
        ("Listas consultadas", str(len(listas))),
        ("Verificaciones", str(len(listas) * max(1, int(scr.get("subjects_screened") or 1)))),
        ("Evidencias", scr_evid),
        # Cobertura y sello se dicen en palabras del decisor; el valor íntegro del
        # sello consta en el pie de página y en el sello global de la página 1.
        ("Cobertura", {"COVERAGE_COMPLETE": "COMPLETA",
                       "COVERAGE_PARTIAL": "PARCIAL",
                       "COVERAGE_INCOMPLETE": "INCOMPLETA"}.get(
                           str(scr.get("coverage_status") or "").upper(),
                           _v(scr.get("coverage_status"), "no declarada"))),
        # El estado de la evidencia es el del MANIFEST de la corrida (una sola
        # verdad). Si el sellado no se pudo completar dice exactamente eso: nunca
        # el nombre de la variable de entorno ni la excepción que lo causó (§8).
        ("Sello de evidencia", {"SELLADO": "SELLADO",
                                "PARCIAL_CON_DECLARACIONES": "PARCIAL",
                                "EVIDENCIA NO SELLADA": "NO SELLADA"}.get(
                                    str(_ev.get("estado") or "").upper(),
                                    limpio(_ev.get("estado")))),
    ]
    cw = (ANCHO - 6 * 4) / 7
    for i, (k, v) in enumerate(metricas):
        x = M + i * (cw + 4)
        panel(c, x, y - 38, cw, 38, PAPER, HAIR)
        txt(c, x + 5, y - 11, k.upper(), FB, 5.6, TEXT_3, esp=0.4)
        txt(c, x + 5, y - 25, str(v)[:16], FB, 7.8, INK)
    y -= 46

    y = titulo_seccion(c, y, "PREPARACIÓN PARA", "no sustituye la decisión de terceros")
    for etiqueta, estado, nota in preparacion:
        panel(c, M, y - 38, ANCHO, 38, CARD)
        txt(c, M + 8, y - 13, etiqueta, FB, 8.6, INK)
        chip_estado(c, W - M - 8 - 200, y - 17, estado)
        wrap(c, M + 8, y - 26, nota, F, 7, TEXT_2, ANCHO - 16, leading=8.2)
        y -= 42

    y = wrap(c, M, y, "UIAF/SIREL es el canal regulatorio de reporte del sujeto obligado: "
                      "no es una lista de screening y no se imprime como fuente. "
                      "Detalle de consultas y hashes — Anexo D.",
             FO, 7.2, TEXT_3, ANCHO, leading=8.6) - 10
    y = traza(c, y, ["Listas restrictivas aplicables"],
              str((modelo.get("evidence_manifest") or {}).get("generated_at") or "")[:10],
              limpio((modelo.get("evidence_manifest") or {}).get("estado")),
              int((modelo.get("evidence_manifest") or {}).get("evidence_count") or 0))
    fit("P3 cierre", y, 52)
    pie(c, modelo, 3)


# ── Página 4 · POT, USO, EDIFICABILIDAD Y RIESGOS ─────────────────────────────
def pagina4(c, modelo, urbano, riesgos, coherencia):
    cabecera(c, modelo, 4)
    y = H - 74
    y = titulo_seccion(c, y, TITULOS_PAGINA[3],
                       "dimensiones separadas: destino catastral ≠ uso POT")

    filas = urbano.get("filas") or []
    for f in filas[:8]:
        alto = 24
        panel(c, M, y - alto, ANCHO, alto, CARD)
        txt(c, M + 8, y - 11, _v(f.get("etiqueta")), F, 7.6, TEXT_3)
        _txt, _sz = ajustar(c, _v(f.get("valor"), "no declarado"), FB, 8.4,
                            (W - M - 8 - 150) - (M + 150) - 6)
        txt(c, M + 150, y - 11, _txt, FB, _sz, INK)
        chip_estado(c, W - M - 8 - 150, y - 18, f.get("estado") or SIN_DATO)
        if f.get("nota"):
            txt(c, M + 150, y - 20, str(f["nota"])[:90], F, 6.4, TEXT_3)
        y -= alto + 3

    y -= 8
    y = titulo_seccion(c, y, "Coherencia del dato", "histórico del expediente")
    for atributo, info in (coherencia or {}).items():
        conflicto = info.get("estado") == HISTORICAL_CONFLICT
        alto = 34
        panel(c, M, y - alto, ANCHO, alto,
              ERR_BG if conflicto else CARD, ERR_BD if conflicto else HAIR)
        txt(c, M + 8, y - 12, atributo.replace("_", " ").upper(), FB, 7, TEXT_3, esp=0.5)
        chip_estado(c, M + 130, y - 18, info.get("estado"))
        # §9: un atributo en conflicto NO se imprime como cifra. Se declaran las dos
        # condiciones exigidas —conflicto histórico y necesidad de validación— sin
        # elegir entre los valores que el propio expediente produjo.
        if conflicto:
            chip(c, M + 246, y - 18, "REQUIERE VALIDACIÓN", "warn", 6.4, 13, 6)
        wrap(c, M + 8, y - 26, _v(info.get("mensaje")), F, 7, TEXT_2, ANCHO - 20, leading=8.2)
        if info.get("valores"):
            # Los valores históricos van a la derecha de los dos chips: el texto se
            # ajusta al hueco real (antes se imprimía debajo de «REQUIERE VALIDACIÓN»).
            _vtxt, _vsz = ajustar(c, "valores históricos: " +
                                  " · ".join(str(v)[:26] for v in info["valores"][:3]),
                                  F, 6.4, 172)
            txt(c, W - M - 8, y - 12, _vtxt, F, _vsz, TEXT_3, "right")
        y -= alto + 3

    y -= 6
    y = titulo_seccion(c, y, "Riesgos territoriales", "amenazas y su implicación")
    for r in (riesgos or [])[:6]:
        panel(c, M, y - 30, ANCHO, 30, CARD)
        banda(c, M, y - 30, 3, 30, WARN_FG if str(r.get("nivel", "")).upper() in ("MEDIO", "ALTO")
              else OK_FG)
        txt(c, M + 8, y - 13, f"{_v(r.get('tipo'))}: {_v(r.get('nivel'), 'no evaluado')}",
            FB, 8.2, INK)
        wrap(c, M + 8, y - 22, _v(r.get("implicacion")), F, 6.8, TEXT_2, ANCHO - 20, leading=8.0)
        y -= 33

    y = wrap(c, M, y, "Detalle de capas, polígonos y versiones POT — Anexo C.", FO, 7.2,
             TEXT_3, ANCHO) - 8
    y = traza(c, y, ["POT / ordenamiento municipal", "Catastro", "Gestión del riesgo"],
              str((modelo.get("evidence_manifest") or {}).get("generated_at") or "")[:10],
              limpio((modelo.get("evidence_manifest") or {}).get("estado")),
              int((modelo.get("evidence_manifest") or {}).get("evidence_count") or 0))
    fit("P4 cierre", y, 52)
    pie(c, modelo, 4)


# ── Página 5 · ENTORNO, EQUIPAMIENTO Y ASOLEAMIENTO ───────────────────────────
def _esquema_sombra(c, x, y, w, h, momento):
    """Esquema geométrico compacto del asoleamiento (§10, máximo dos).

    Se dibuja con lo que el estado YA calculó (azimut y elevación): es un esquema de
    dirección, NO una fotografía ni un render de sombras del edificio, y así se rotula.
    """
    az = _num_grados(momento.get("azimut"))
    el = _num_grados(momento.get("elevacion"))
    panel(c, x, y - h, w, h, CARD)
    txt(c, x + 6, y - 10, f"ESQUEMA {_v(momento.get('hora'), '—')}", FB, 6.2, TEXT_3, esp=0.4)
    cx, cy, r = x + w / 2.0, y - h / 2.0 - 3, min(w, h) / 2.0 - 16
    c.setStrokeColor(HAIR_2)
    c.setLineWidth(0.6)
    c.circle(cx, cy, r, stroke=1, fill=0)
    txt(c, cx, cy - r - 2, "N", FB, 5.4, TEXT_3, "center")
    if az is None or el is None:
        txt(c, cx, cy - 2, "sin dato de fuente", F, 6.0, TEXT_3, "center")
        return
    rad = math.radians(90.0 - az)          # 0° = Norte geográfico
    dx, dy = math.cos(rad), math.sin(rad)
    c.setStrokeColor(GOLD)
    c.setLineWidth(1.1)
    c.line(cx, cy, cx + dx * r, cy + dy * r)
    c.setFillColor(GOLD)
    c.circle(cx + dx * r, cy + dy * r, 2.4, stroke=0, fill=1)
    txt(c, x + 6, y - h + 8, f"azimut {_v(momento.get('azimut'), '—')} · elevación "
                             f"{_v(momento.get('elevacion'), '—')}", F, 5.8, TEXT_3)
    txt(c, x + 6, y - h + 2, "esquema de dirección solar (no es una fotografía)",
        "Helvetica-Oblique", 5.4, TEXT_3)


def _num_grados(valor):
    """Grados de un valor del estado tipo «212.4°» o «212.4». None si no es numérico."""
    try:
        return float(str(valor or "").replace("°", "").strip())
    except (TypeError, ValueError):
        return None


def pagina5(c, modelo, entorno, solar, ctx):
    cabecera(c, modelo, 5)
    y = H - 74
    y = titulo_seccion(c, y, TITULOS_PAGINA[4], "equipamiento, entorno y asoleamiento")

    y = wrap(c, M, y, "EQUIPAMIENTO URBANO", FB, 8, GOLD, ANCHO, esp=0.8) - 14
    categorias = entorno.get("categorias") or []
    cw = (ANCHO - 3 * 6) / 4
    for i, cat in enumerate(categorias[:4]):
        x = M + i * (cw + 6)
        panel(c, x, y - 78, cw, 78, CARD)
        _estado = str(cat.get("estado") or "")
        # Vocabulario REAL del motor: AVAILABLE / NO_MATCH / SOURCE_UNAVAILABLE /
        # NOT_EVALUATED. Un mapeo estrecho dejaba sin imprimir la distancia existente.
        _disp = _estado in ("DISPONIBLE", "AVAILABLE")
        _desconocido = _estado in ("SOURCE_UNAVAILABLE", "NOT_EVALUATED", "")
        banda(c, x, y - 3, cw, 3, OK_FG if _disp else WARN_FG)
        _clave = str(cat.get("nombre") or "").upper()
        txt(c, x + 6, y - 15, ROTULO_CATEGORIA.get(_clave, _v(cat.get("nombre"))),
            FB, 8, INK)
        _conteo = cat.get("conteo")
        txt(c, x + 6, y - 33, "—" if (_desconocido and not _conteo)
            else _v(_conteo, "0"), FB, 15, INK)
        txt(c, x + 6, y - 42, "detectados" if not _desconocido else "sin dato de fuente",
            F, 6.4, TEXT_3)
        # §10: cantidad, más cercano y distancia REAL del ítem más próximo.
        _mas = cat.get("mas_cercano_m")
        _nombre_cercano = cat.get("mas_cercano")
        if _mas is not None:
            txt(c, x + 6, y - 54, f"más cercano: {int(round(float(_mas)))} m", FB, 7.2, INK)
        elif _disp:
            txt(c, x + 6, y - 54, "DISTANCIA NO DISPONIBLE", FB, 6.4, WARN_FG)
        else:
            txt(c, x + 6, y - 54, {"NO_MATCH": "SIN COINCIDENCIA",
                                   "SOURCE_UNAVAILABLE": "FUENTE NO DISPONIBLE",
                                   "NOT_EVALUATED": "NO EVALUADO"}.get(_estado, "SIN DATO"),
                FB, 6.4, WARN_FG)
        if _nombre_cercano:
            txt(c, x + 6, y - 63, str(_nombre_cercano)[:30], F, 6.0, TEXT_2)
        for j, it in enumerate((cat.get("ejemplos") or [])[:2]):
            _d = it.get("distance_m")
            txt(c, x + 6, y - 71 - j * 7.4,
                f"· {str(it.get('name') or '—')[:20]}"
                + (f" — {int(round(float(_d)))} m" if _d is not None else ""),
                F, 5.8, TEXT_2)
    y -= 86
    txt(c, M, y, "Lista completa de equipamientos (nombre, coordenada, distancia, fuente "
                 "y fecha de consulta) — Anexo E.", FO, 7, TEXT_3)
    y -= 14

    y = wrap(c, M, y, "ACCESIBILIDAD Y CONTEXTO", FB, 8, GOLD, ANCHO, esp=0.8) - 14
    for k, v in (entorno.get("accesibilidad") or []):
        txt(c, M, y, k, F, 7.4, TEXT_3)
        y = wrap(c, M + 130, y, _v(v, "no declarado"), FB, 7.8, INK, ANCHO - 130, leading=9.0) - 7

    y -= 4
    y = wrap(c, M, y, "ASOLEAMIENTO", FB, 8, GOLD, ANCHO, esp=0.8) - 14
    momentos = (solar.get("momentos") or [])
    if momentos:
        cw = (ANCHO - 2 * 6) / 3
        for i, m in enumerate(momentos[:3]):
            x = M + i * (cw + 6)
            panel(c, x, y - 50, cw, 50, CARD)
            txt(c, x + 6, y - 15, _v(m.get("hora")), FB, 11, INK)
            wrap(c, x + 6, y - 27, _v(m.get("estado")), F, 7.0, TEXT_2, cw - 12, leading=8.2)
            txt(c, x + 6, y - 43, f"azimut {_v(m.get('azimut'), '—')} · elevación "
                                  f"{_v(m.get('elevacion'), '—')}", F, 6.2, TEXT_3)
        y -= 56
        # Máximo DOS visualizaciones compactas de sombras (§10).
        _dos = [momentos[0], momentos[-1]] if len(momentos) > 1 else [momentos[0]]
        cw2 = (ANCHO - 6) / 2
        for i, m in enumerate(_dos[:2]):
            _esquema_sombra(c, M + i * (cw2 + 6), y, cw2, 78, m)
        y -= 86
    else:
        panel(c, M, y - 26, ANCHO, 26, PAPER, HAIR)
        txt(c, M + 8, y - 16, "Asoleamiento no declarado en esta ejecución.", F, 7.6, WARN_FG)
        y -= 32

    panel(c, M, y - 42, ANCHO, 42, PAPER, HAIR)
    wrap(c, M + 8, y - 13,
         "La proyección de sombras corresponde a una SIMULACIÓN GEOMÉTRICA calculada con la "
         "huella y la altura del edificio disponibles; no sustituye una inspección física ni "
         "una observación real en sitio.", F, 7.2, TEXT_2, ANCHO - 16, leading=8.4)
    if solar.get("altura_dependiente"):
        wrap(c, M + 8, y - 31,
             "La simulación depende de la altura del edificio: si esa cifra requiere validación "
             "de coherencia (véase página 4), la sombra es referencial.", FO, 6.8, WARN_FG,
             ANCHO - 16, leading=8.2)
    y -= 50
    y = traza(c, y, ["Proveedor de mapas abierto", "Fotografía satelital", "Cálculo solar"],
              str((modelo.get("evidence_manifest") or {}).get("generated_at") or "")[:10],
              limpio((modelo.get("evidence_manifest") or {}).get("estado")),
              int((modelo.get("evidence_manifest") or {}).get("evidence_count") or 0))
    fit("P5 cierre", y, 52)
    pie(c, modelo, 5)


# ── Página 6 · IDENTIDAD Y VALOR ──────────────────────────────────────────────
def pagina6(c, modelo, identidad, valor):
    cabecera(c, modelo, 6)
    y = H - 74
    y = titulo_seccion(c, y, TITULOS_PAGINA[5], "lo que se verificó y cuánto vale")

    y = wrap(c, M, y, "IDENTIDAD", FB, 8, GOLD, ANCHO, esp=0.8) - 14
    filas = identidad.get("filas") or []
    for f in filas[:9]:
        panel(c, M, y - 22, ANCHO, 22, CARD)
        txt(c, M + 8, y - 14, _v(f.get("etiqueta")), F, 7.6, TEXT_3)
        _txt, _sz = ajustar(c, _v(f.get("valor"), "no declarado"), FB, 8.2,
                            (W - M - 8 - 140) - (M + 160) - 6)
        txt(c, M + 160, y - 14, _txt, FB, _sz, INK)
        chip_estado(c, W - M - 8 - 140, y - 17, f.get("estado") or SIN_DATO)
        y -= 25
    if identidad.get("nota_tecnica"):
        y = wrap(c, M, y - 1, identidad["nota_tecnica"], FO, 6.8, TEXT_3, ANCHO, leading=8.0) - 6

    y -= 6
    y = titulo_seccion(c, y, "VALOR ESTIMADO", "solo si la valoración está autorizada")
    aut = bool(valor.get("autorizado"))
    panel(c, M, y - 66, ANCHO, 66, CARD if aut else PAPER, HAIR)
    if aut:
        txt(c, M + 10, y - 15, "Valor estimado (valor central)", FB, 6.6, TEXT_3, esp=0.3)
        txt(c, M + 10, y - 37, _v(valor.get("consolidado")), FB, 17, INK)
        _resumen, _rsz = ajustar(
            c, f"Rango {_v(valor.get('rango'), '—')} – {_v(valor.get('rango_alto'), '—')} · "
               f"Valor/m² {_v(valor.get('valor_m2'), '—')} · Área {_v(valor.get('area'), '—')}",
            F, 7.4, 228)
        txt(c, M + 10, y - 53, _resumen, F, _rsz, TEXT_2)
        for i, (k, v) in enumerate([("Método principal", valor.get("metodologia")),
                                    ("Sector de mercado", valor.get("sector")),
                                    ("Fecha / vigencia", valor.get("vigencia"))]):
            x = M + 250 + i * 92
            txt(c, x, y - 19, k, FB, 6.4, TEXT_3, esp=0.3)
            wrap(c, x, y - 30, _v(v, "no declarado"), FB, 7.2, INK, 88, leading=8.4)
    else:
        txt(c, M + 10, y - 20, "VALORACIÓN NO DISPONIBLE", FB, 13, WARN_FG)
        wrap(c, M + 10, y - 38, _v(valor.get("motivo"),
                                  "El expediente no declara por qué no se autorizó: requiere "
                                  "revisión."), F, 8, TEXT_2, ANCHO - 20, leading=9.6)
        txt(c, M + 10, y - 58, "No se imprime ningún monto, ni $0, mientras la valoración no "
                               "esté autorizada.", FO, 7.2, TEXT_3)
    y -= 74

    y = titulo_seccion(c, y, "Cómo se obtuvo el valor", "cadena de método")
    pasos = valor.get("pasos") or []
    for i, p in enumerate(pasos[:6], 1):
        txt(c, M, y, f"{i}.", FB, 8, GOLD)
        # El interlineado SIEMPRE supera al cuerpo: bajar 5 pt con letra de 7.6 pt
        # imprimía los pasos unos sobre otros.
        y = wrap(c, M + 14, y, p, F, 7.6, TEXT_2, ANCHO - 14, leading=9.4) - 10
    y -= 2
    panel(c, M, y - 44, ANCHO, 44, PAPER, HAIR)
    wrap(c, M + 8, y - 14, "NORMA · CONCEPTO TÉCNICO · VALIDACIÓN EXPERTA: DICTUS prepara y "
                           "señala; el valor y su interpretación los firma el profesional "
                           "competente (avaluador inscrito en el RAA, abogado, geodesta).",
         F, 7.6, TEXT_2, ANCHO - 16, leading=9.2)
    y -= 52
    y = traza(c, y, ["Metodología de mercado (Lonja)", "Catastro", "Identidad canónica"],
              str((modelo.get("evidence_manifest") or {}).get("generated_at") or "")[:10],
              limpio((modelo.get("evidence_manifest") or {}).get("estado")),
              int((modelo.get("evidence_manifest") or {}).get("evidence_count") or 0))
    fit("P6 cierre", y, 52)
    pie(c, modelo, 6)


# ── render ────────────────────────────────────────────────────────────────────
def render(modelo: Dict[str, Any], secciones: Dict[str, Any], destino: Path) -> Path:
    """Genera el documento ejecutivo: SEIS páginas, en el orden aprobado (§4)."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    del VIOLACIONES[:]
    c = canvas.Canvas(str(destino), pagesize=(W, H))
    di = modelo.get("document_identity") or {}
    c.setTitle(f"DICTUS — {TITULOS_PAGINA[0]} {di.get('folio')}")
    c.setAuthor("ARHIAX RE · DICTUS")
    c.setSubject("Informe ejecutivo de decisión inmobiliaria + expediente verificable")

    pagina1(c, modelo, secciones.get("hallazgos") or [],
            secciones.get("indicadores") or [], secciones.get("ctx") or {})
    c.showPage()
    pagina2(c, modelo, secciones.get("legal") or {}, secciones.get("ctx") or {})
    c.showPage()
    pagina3(c, modelo, secciones.get("contrapartes") or {},
            secciones.get("preparacion") or [])
    c.showPage()
    pagina4(c, modelo, secciones.get("urbano") or {}, secciones.get("riesgos") or [],
            secciones.get("coherencia") or {})
    c.showPage()
    pagina5(c, modelo, secciones.get("entorno") or {}, secciones.get("solar") or {},
            secciones.get("ctx") or {})
    c.showPage()
    pagina6(c, modelo, secciones.get("identidad") or {}, secciones.get("valor") or {})
    c.showPage()
    c.save()
    return destino


def hoja_anexos(destino: Path, mapa: List[Tuple[str, str, str]]) -> Path:
    """Hoja separadora de ANEXOS con el mapa de contenidos (§AG, §AH)."""
    c = canvas.Canvas(str(destino), pagesize=(W, H))
    banda(c, 0, H - 120, W, 120, INK)
    banda(c, M, H - 132, 60, 3, GOLD)
    txt(c, M, H - 56, "ANEXOS", FB, 26, white, esp=2.0)
    txt(c, M, H - 78, "EVIDENCIA TÉCNICA COMPLETA DEL EXPEDIENTE", F, 9, GOLD_2, esp=0.8)
    txt(c, M, H - 96, "El cuerpo ejecutivo no elimina información: la reubica. Aquí está el "
                      "detalle auditable de cada afirmación.", F, 8, GOLD_2)
    y = H - 170
    for letra, titulo, contenido in mapa:
        panel(c, M, y - 46, ANCHO, 46, CARD, HAIR)
        banda(c, M, y - 46, 3, 46, GOLD)
        txt(c, M + 10, y - 18, f"ANEXO {letra}", FB, 9, GOLD, esp=0.8)
        txt(c, M + 90, y - 18, titulo, FB, 9.5, INK)
        wrap(c, M + 90, y - 32, contenido, F, 7.4, TEXT_2, ANCHO - 100, leading=8.6)
        y -= 52
    txt(c, M, 60, "El detalle técnico (URLs, identificadores de capa, versiones de parser, "
                  "snapshots, hashes individuales y recibos completos) vive en estos anexos: "
                  "no se imprime en el cuerpo ejecutivo.", FO, 7.2, TEXT_3, )
    c.save()
    return destino

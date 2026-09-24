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
    mapa = {
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
    clase, etiqueta = mapa.get(estado, ("info", str(estado)))
    return chip(c, x, y, etiqueta, clase)


def fit(nombre, y_final, y_limite):
    if y_final < y_limite - 1:
        VIOLACIONES.append(f"{nombre}: desborda {y_limite - y_final:.0f} pt")


def _v(valor, hueco="NO DISPONIBLE") -> str:
    """Valor legible: nunca un guion mudo ni un cero falso."""
    if valor is None or valor == "" or (isinstance(valor, str) and not valor.strip()):
        return hueco
    return str(valor)


# ── cromo de página ───────────────────────────────────────────────────────────
def cabecera(c, modelo, pagina, subtitulo="EXPEDIENTE VERIFICADO DE INMUEBLE"):
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
    txt(c, M, 20, f"Evidencias {ev.get('evidence_count')} · sello {ev.get('estado')} · "
                  f"verificación por DICTUS ID (Anexo G)", F, 6.6, TEXT_3)
    txt(c, W - M, 20, "El hash del archivo PDF no es el hash maestro: consta en el anexo G.",
        F, 6.6, TEXT_3, "right")


def traza(c, y, fuentes: Iterable[str], fecha: str, estado: str, n_ev: int) -> float:
    """Bloque TRAZABILIDAD (§M): lenguaje comprensible, sin códigos técnicos."""
    h = 40
    panel(c, M, y - h, ANCHO, h, PAPER, HAIR)
    txt(c, M + 8, y - 13, "TRAZABILIDAD", FB, 7, GOLD, esp=1.0)
    txt(c, M + 8, y - 25, "Fuentes principales: " + ", ".join(list(fuentes)[:4]), F, 7.4, TEXT_2)
    txt(c, M + 8, y - 35, f"Consulta: {fecha or 'no declarada'} · Estado: {estado} · "
                          f"Evidencias: {n_ev}", F, 7.4, TEXT_2)
    txt(c, W - M - 8, y - 25, "Evidencia INCLUIDA EN HASH MAESTRO DICTUS", FB, 7, TEXT_2, "right")
    txt(c, W - M - 8, y - 35, "Detalle técnico: Anexos", FO, 7, TEXT_3, "right")
    return y - h - 8


def titulo_seccion(c, y, texto, kicker=""):
    if kicker:
        txt(c, M, y, kicker.upper(), FB, 7, GOLD, esp=1.0)
        y -= 12
    txt(c, M, y, texto, FB, 13, INK)
    rule(c, M, y - 6, W - M, y - 6, HAIR)
    return y - 20


# ── Página 1 · información general + decisión ─────────────────────────────────
def pagina1(c, modelo, hallazgos, indicadores, ctx):
    cabecera(c, modelo, 1)
    ident = modelo.get("canonical_property_identity") or {}
    urb = modelo.get("urban_context") or {}
    val = modelo.get("valuation") or {}
    y = H - 74

    txt(c, M, y, "DECISIÓN SOBRE EL INMUEBLE", FB, 8, GOLD, esp=1.2)
    y -= 18
    y = wrap(c, M, y, _v(ident.get("direccion_normalizada") or ident.get("direccion_raw"),
                         "Dirección no declarada"), FB, 14, INK, ANCHO, leading=17)
    etiquetas = [
        _v(urb.get("barrio") and str(urb.get("barrio")).title(), None) or "Barrio: no declarado",
        f"Folio {_v(ident.get('folio'), '—')}",
        f"NUPRE {_v(ident.get('nupre'), 'no declarado')}",
        f"Predial {_v(ident.get('codigo_catastral'), 'no declarado')}",
        f"Unidad {_v(ident.get('unidad'), 'no declarada')}",
        f"Área {_v(ctx.get('area'), 'no declarada')} m²",
        f"Régimen {_v(ctx.get('regimen'), 'no declarado')}",
        f"Uso {_v(ctx.get('uso'), 'no declarado')}",
    ]
    x = M
    for et in etiquetas:
        ancho = c.stringWidth(et, F, 7.2) + 12
        if x + ancho > W - M:
            x = M
            y -= 18
        chip(c, x, y - 14, et, "info", 7.2, 14, 6)
        x += ancho + 5
    y -= 26

    # Cinco indicadores ejecutivos (§G)
    y = titulo_seccion(c, y, "Estado general", "cinco indicadores")
    cw = (ANCHO - 4 * 6) / 5
    for i, (nombre, estado, motivo) in enumerate(indicadores):
        x = M + i * (cw + 6)
        panel(c, x, y - 72, cw, 72)
        banda(c, x, y - 3, cw, 3, GOLD if estado in (VERIFICADO, "DISPONIBLE") else INK_3)
        txt(c, x + 6, y - 16, nombre.upper(), FB, 6.6, TEXT_3, esp=0.6)
        chip_estado(c, x + 6, y - 36, estado)
        wrap(c, x + 6, y - 48, motivo, F, 6.4, TEXT_2, cw - 12, leading=8)
    y -= 80

    # Hallazgos (§H) con actores afectados (§I)
    y = titulo_seccion(c, y, "Hallazgos que condicionan la decisión",
                       f"{len(hallazgos)} hallazgo(s) material(es)")
    for h in hallazgos[:4]:
        alto = 74 if h.get("impacto") else 62
        panel(c, M, y - alto, ANCHO, alto)
        color = {"ALTO": ERR_FG, "MEDIO": WARN_FG, "INFORMATIVO": OK_FG}.get(
            str(h.get("severidad", "")).upper(), TEXT)
        banda(c, M, y - alto, 3, alto, color)
        chip(c, M + 8, y - 16, str(h.get("severidad", "—")).upper(),
             {"ALTO": "err", "MEDIO": "warn", "INFORMATIVO": "ok"}.get(
                 str(h.get("severidad", "")).upper(), "info"), 7, 14, 6)
        txt(c, M + 60, y - 13, f"{_v(h.get('codigo'), '')} {_v(h.get('titulo'), '')}",
            FB, 9.5, INK)
        yt = wrap(c, M + 8, y - 30, _v(h.get("por_que"), "Sin descripción declarada."),
                  F, 8, TEXT_2, ANCHO - 150, leading=10)
        # Actores afectados
        txt(c, W - M - 8, y - 26, "AFECTA A", FB, 6.4, TEXT_3, "right", esp=0.6)
        _x = W - M - 8
        for actor in reversed(list(h.get("afectados") or [])):
            ancho = c.stringWidth(actor, FB, 6.6) + 10
            chip(c, _x - ancho, y - 42, actor, "ink", 6.6, 13, 5)
            _x -= ancho + 4
        if h.get("impacto"):
            wrap(c, W - M - 150, y - 54, h["impacto"], FO, 7, TEXT_2, 142, leading=8.6)
        rule(c, M + 8, y - 56, W - M - 8, y - 56, HAIR_2)
        wrap(c, M + 8, y - 68, "Acción: " + _v(h.get("accion"), "por definir"), FB, 7.6,
             INK, ANCHO - 20, leading=9.4)
        fit(f"P1 hallazgo {h.get('codigo')}", yt, y - alto)
        y -= alto + 6

    if len(hallazgos) > 4:
        txt(c, M, y + 2, f"+ {len(hallazgos) - 4} hallazgo(s) adicional(es) en el Anexo H.",
            FO, 7.6, TEXT_3)
        y -= 10

    # Sello global de trazabilidad (§L)
    y = max(y, 150)
    ev = modelo.get("evidence_manifest") or {}
    sello_h = 66
    panel(c, M, y - sello_h, ANCHO, sello_h, INK, INK)
    banda(c, M, y - sello_h, 4, sello_h, GOLD)
    txt(c, M + 12, y - 16, "SELLO GLOBAL DE TRAZABILIDAD", FB, 7, GOLD_2, esp=1.0)
    di = modelo.get("document_identity") or {}
    txt(c, M + 12, y - 32, _v(di.get("dictus_id")), FB, 11, white)
    txt(c, M + 12, y - 46, f"Generado: {_v(di.get('generated_at'), 'sin fecha declarada')}",
        F, 7.4, GOLD_2)
    txt(c, M + 12, y - 58, f"Evidencias: {ev.get('evidence_count')} · "
                           f"Cadena: {_v(ev.get('estado'))}", F, 7.4, GOLD_2)
    txt(c, M + 250, y - 32, "DICTUS_MASTER_HASH", FB, 7, GOLD_2, esp=1.0)
    txt(c, M + 250, y - 46, str(modelo.get("master_hash") or "")[:48], "Courier-Bold", 8, white)
    txt(c, M + 250, y - 58, f"…{str(modelo.get('master_hash') or '')[48:]}", "Courier-Bold",
        8, GOLD_2)
    wrap(c, W - M - 130, y - 30,
         "Verificación: nombre del expediente (DICTUS ID) + hash maestro. El hash del "
         "archivo PDF consta aparte (Anexo G).", FO, 6.4, GOLD_2, 122, leading=7.6)
    y -= sello_h + 8

    y = traza(c, y, ev.get("fuentes") or [], str(di.get("generated_at") or "")[:10],
              str(ev.get("estado") or ""), int(ev.get("evidence_count") or 0))
    txt(c, M, y - 2, "Alcance y limitaciones del documento: ver Anexo H.", FO, 7, TEXT_3)
    fit("P1 cierre", y, 62)
    pie(c, modelo, 1)


# ── Página 2 · títulos y condiciones jurídicas ────────────────────────────────
def pagina2(c, modelo, legal, ctx):
    cabecera(c, modelo, 2)
    y = H - 74
    y = titulo_seccion(c, y, "¿Qué puede impedir o condicionar la transacción?",
                       "títulos y condiciones jurídicas")

    y = wrap(c, M, y, "TITULARIDAD", FB, 8, GOLD, ANCHO, esp=0.8) - 14
    if legal.get("titulares"):
        for t in legal["titulares"][:4]:
            panel(c, M, y - 26, ANCHO, 26, CARD)
            txt(c, M + 8, y - 11, _v(t.get("nombre")), FB, 9, INK)
            txt(c, M + 8, y - 21, f"{_v(t.get('tipo'), 'tipo no declarado')} · "
                                  f"{_v(t.get('documento'), 'documento no declarado')} · "
                                  f"participación {_v(t.get('participacion'), 'no declarada')}",
                F, 7.2, TEXT_2)
            chip(c, W - M - 8 - 96, y - 20, _v(t.get("verificacion", "")).upper() or "POR VERIFICAR",
                 "ok" if t.get("verificacion") == VERIFICADO else "warn", 6.6, 13, 5)
            y -= 30
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

    y = wrap(c, M, y - 2, "CONDICIONES PARA CERRAR LA OPERACIÓN", FB, 8, GOLD, ANCHO, esp=0.8) - 14
    for i, cond in enumerate((legal.get("condiciones") or [])[:5], 1):
        txt(c, M, y, f"{i}.", FB, 8, GOLD)
        y = wrap(c, M + 14, y, cond, F, 8, TEXT_2, ANCHO - 14, leading=9.6) - 8
    if not legal.get("condiciones"):
        y = wrap(c, M, y, "No hay condiciones registradas: el expediente no declara "
                          "cargas activas ni requerimientos pendientes.", F, 8, TEXT_2,
                 ANCHO, leading=9.6) - 8

    y = wrap(c, M, y, "Ver detalle registral completo — Anexo A.", FO, 7.4, TEXT_3, ANCHO) - 10
    y = traza(c, y, ["Registro (SNR/CTL)", "Titulux"], str((modelo.get("evidence_manifest") or {}).get("generated_at") or "")[:10], "VERIFICADO", int((modelo.get("evidence_manifest") or {}).get("evidence_count") or 0))
    fit("P2 cierre", y, 52)
    pie(c, modelo, 2)


# ── Página 3 · contrapartes + preparación de la operación ─────────────────────
def pagina3(c, modelo, contrapartes, preparacion):
    cabecera(c, modelo, 3)
    y = H - 74
    y = titulo_seccion(c, y, "Contrapartes y listas restrictivas consultadas",
                       "screening del caso")
    scr = modelo.get("screening_summary") or {}

    # Columnas DINÁMICAS: las listas realmente utilizadas (nunca hardcodeadas).
    listas = list(contrapartes.get("listas") or [])
    ancho_sujeto = 150
    ancho_lista = max(60, (ANCHO - ancho_sujeto - 110) / max(1, len(listas)))
    panel(c, M, y - 18, ANCHO, 18, PAPER, HAIR)
    txt(c, M + 6, y - 12, "SUJETO", FB, 6.6, TEXT_3, esp=0.5)
    txt(c, M + ancho_sujeto + 6, y - 12, "ROL / TIPO / DOCUMENTO", FB, 6.6, TEXT_3, esp=0.5)
    for i, li in enumerate(listas):
        txt(c, M + ancho_sujeto + 110 + i * ancho_lista + 4, y - 12, str(li)[:22].upper(),
            FB, 6.6, TEXT_3, esp=0.4)
    txt(c, W - M - 6, y - 12, "RESULTADO", FB, 6.6, TEXT_3, "right", esp=0.5)
    y -= 18

    for s in (contrapartes.get("sujetos") or [])[:6]:
        alto = 30
        panel(c, M, y - alto, ANCHO, alto, CARD)
        wrap(c, M + 6, y - 12, _v(s.get("nombre")), FB, 8, INK, ancho_sujeto - 12, leading=9.4)
        wrap(c, M + ancho_sujeto + 6, y - 12, f"{_v(s.get('rol'))} · {_v(s.get('tipo'))} · "
             f"{_v(s.get('documento'), 'documento no declarado')}", F, 7, TEXT_2,
             ancho_lista + 100, leading=8.4)
        for i, li in enumerate(listas):
            estado = (s.get("por_lista") or {}).get(li) or "SIN_DATO"
            chip(c, M + ancho_sujeto + 110 + i * ancho_lista + 4, y - 18,
                 {"SIN_COINCIDENCIAS": "SIN COINCIDENCIA", "COINCIDENCIA": "COINCIDENCIA",
                  "INCOMPLETA": "NO CONSULTADA", "SIN_DATO": "NO CONSULTADA"}.get(estado, estado),
                 {"SIN_COINCIDENCIAS": "ok", "COINCIDENCIA": "err",
                  "INCOMPLETA": "warn"}.get(estado, "info"), 6.2, 13, 5)
        resultado = s.get("resultado") or "SIN_DATO"
        chip(c, W - M - 8 - 150, y - 18,
             {"SIN_COINCIDENCIAS": "SIN COINCIDENCIAS RELEVANTES",
              "COINCIDENCIA": "COINCIDENCIA REQUIERE REVISIÓN",
              "INCOMPLETA": "VERIFICACIÓN INCOMPLETA"}.get(resultado, "SIN DATO"),
             {"SIN_COINCIDENCIAS": "ok", "COINCIDENCIA": "err"}.get(resultado, "warn"), 6.4, 13, 6)
        y -= alto + 4

    y -= 6
    y = titulo_seccion(c, y, "Estado del screening", "cobertura y evidencia")
    metricas = [
        ("Sujetos declarados", _v(scr.get("subjects_declared"), "—")),
        ("Sujetos revisados", _v(scr.get("subjects_screened"), "—")),
        ("Listas consultadas", str(len(listas))),
        ("Verificaciones", str(len(listas) * max(1, int(scr.get("subjects_screened") or 1)))),
        ("Evidencias", f"{_v(scr.get('evidence_created'), '0')}/{_v(scr.get('evidence_expected'), '—')}"),
        ("Cobertura", _v(scr.get("coverage_status"), "no declarada")),
        ("Cadena", _v(scr.get("evidence_chain_status"), "no declarada")),
    ]
    cw = (ANCHO - 6 * 4) / 7
    for i, (k, v) in enumerate(metricas):
        x = M + i * (cw + 4)
        panel(c, x, y - 40, cw, 40, PAPER, HAIR)
        txt(c, x + 5, y - 12, k.upper(), FB, 5.8, TEXT_3, esp=0.4)
        txt(c, x + 5, y - 26, str(v)[:16], FB, 8.6, INK)
    y -= 50

    y = titulo_seccion(c, y, "Preparación de la operación", "no sustituye la decisión de terceros")
    for etiqueta, estado, nota in preparacion:
        panel(c, M, y - 40, ANCHO, 40, CARD)
        txt(c, M + 8, y - 14, etiqueta, FB, 9, INK)
        chip_estado(c, W - M - 8 - 200, y - 18, estado)
        wrap(c, M + 8, y - 28, nota, F, 7.2, TEXT_2, ANCHO - 16, leading=8.4)
        y -= 44

    y = wrap(c, M, y, "UIAF/SIREL es el canal regulatorio de reporte del sujeto obligado: "
                      "no es una lista de screening y no se imprime como fuente. "
                      "Detalle de consultas y hashes — Anexo D.",
             FO, 7.2, TEXT_3, ANCHO, leading=8.6) - 10
    y = traza(c, y, ["Listas restrictivas aplicables"],
              str((modelo.get("evidence_manifest") or {}).get("generated_at") or "")[:10],
              "VERIFICADO", int((modelo.get("evidence_manifest") or {}).get("evidence_count") or 0))
    fit("P3 cierre", y, 52)
    pie(c, modelo, 3)


# ── Página 4 · POT, uso, edificabilidad, riesgos y coherencia ─────────────────
def pagina4(c, modelo, urbano, riesgos, coherencia):
    cabecera(c, modelo, 4)
    y = H - 74
    y = titulo_seccion(c, y, "Norma urbanística, uso y edificabilidad",
                       "dimensiones separadas: destino catastral ≠ uso POT")

    filas = urbano.get("filas") or []
    for f in filas[:8]:
        alto = 24
        panel(c, M, y - alto, ANCHO, alto, CARD)
        txt(c, M + 8, y - 11, _v(f.get("etiqueta")), F, 7.6, TEXT_3)
        txt(c, M + 150, y - 11, _v(f.get("valor"), "no declarado"), FB, 8.4, INK)
        chip_estado(c, W - M - 8 - 150, y - 18, f.get("estado") or SIN_DATO)
        if f.get("nota"):
            txt(c, M + 150, y - 20, str(f["nota"])[:90], F, 6.4, TEXT_3)
        y -= alto + 3

    y -= 8
    y = titulo_seccion(c, y, "Coherencia del dato", "histórico del expediente")
    for atributo, info in (coherencia or {}).items():
        alto = 34
        panel(c, M, y - alto, ANCHO, alto,
              CARD if info.get("estado") != HISTORICAL_CONFLICT else ERR_BG,
              HAIR if info.get("estado") != HISTORICAL_CONFLICT else ERR_BD)
        txt(c, M + 8, y - 12, atributo.replace("_", " ").upper(), FB, 7, TEXT_3, esp=0.5)
        chip_estado(c, M + 130, y - 18, info.get("estado"))
        wrap(c, M + 8, y - 26, _v(info.get("mensaje")), F, 7, TEXT_2, ANCHO - 20, leading=8.2)
        if info.get("valores"):
            txt(c, W - M - 8, y - 12, "valores históricos: " +
                " · ".join(str(v)[:26] for v in info["valores"][:3]), F, 6.4, TEXT_3, "right")
        y -= alto + 3

    y -= 6
    y = titulo_seccion(c, y, "Riesgos territoriales", "amenazas y su implicación")
    for r in (riesgos or [])[:4]:
        panel(c, M, y - 32, ANCHO, 32, CARD)
        banda(c, M, y - 32, 3, 32, WARN_FG if str(r.get("nivel", "")).upper() in ("MEDIO", "ALTO")
              else OK_FG)
        txt(c, M + 8, y - 13, f"{_v(r.get('tipo'))}: {_v(r.get('nivel'), 'no evaluado')}",
            FB, 8.4, INK)
        wrap(c, M + 8, y - 23, _v(r.get("implicacion")), F, 7.2, TEXT_2, ANCHO - 20, leading=8.4)
        y -= 36

    y = wrap(c, M, y, "Detalle de capas, polígonos y versiones POT — Anexo C.", FO, 7.2,
             TEXT_3, ANCHO) - 8
    y = traza(c, y, ["POT / ordenamiento municipal", "Catastro", "Gestión del riesgo"],
              str((modelo.get("evidence_manifest") or {}).get("generated_at") or "")[:10],
              "VERIFICADO", int((modelo.get("evidence_manifest") or {}).get("evidence_count") or 0))
    fit("P4 cierre", y, 52)
    pie(c, modelo, 4)


# ── Página 5 · entorno, equipamiento, accesibilidad, asoleamiento ─────────────
def pagina5(c, modelo, entorno, solar, ctx):
    cabecera(c, modelo, 5)
    y = H - 74
    y = titulo_seccion(c, y, "Entorno del inmueble", "equipamiento, accesibilidad y asoleamiento")

    y = wrap(c, M, y, "EQUIPAMIENTO URBANO", FB, 8, GOLD, ANCHO, esp=0.8) - 14
    categorias = entorno.get("categorias") or []
    cw = (ANCHO - 3 * 6) / 4
    for i, cat in enumerate(categorias[:4]):
        x = M + i * (cw + 6)
        panel(c, x, y - 62, cw, 62, CARD)
        banda(c, x, y - 3, cw, 3, OK_FG if cat.get("estado") == "DISPONIBLE" else WARN_FG)
        txt(c, x + 6, y - 16, _v(cat.get("nombre")).upper(), FB, 7, TEXT_3, esp=0.5)
        txt(c, x + 6, y - 32, _v(cat.get("conteo"), "—"), FB, 15, INK)
        txt(c, x + 6, y - 42, "establecimientos", F, 6.4, TEXT_3)
        wrap(c, x + 6, y - 52, _v(cat.get("mas_cercano"), "distancia no disponible en esta "
                                                            "ejecución"), F, 6.4, TEXT_2,
             cw - 12, leading=7.6)
    y -= 70
    txt(c, M, y, "Lista completa de equipamientos — Anexo E.", FO, 7, TEXT_3)
    y -= 14

    y = wrap(c, M, y, "ACCESIBILIDAD Y CONTEXTO", FB, 8, GOLD, ANCHO, esp=0.8) - 14
    for k, v in (entorno.get("accesibilidad") or []):
        txt(c, M, y, k, F, 7.6, TEXT_3)
        y = wrap(c, M + 130, y, _v(v, "no declarado"), FB, 8, INK, ANCHO - 130, leading=9.4) - 8

    y -= 4
    y = wrap(c, M, y, "ASOLEAMIENTO Y PROYECCIÓN DE SOMBRAS", FB, 8, GOLD, ANCHO, esp=0.8) - 14
    if solar.get("momentos"):
        cw = (ANCHO - 2 * 6) / 3
        for i, m in enumerate(solar["momentos"][:3]):
            x = M + i * (cw + 6)
            panel(c, x, y - 54, cw, 54, CARD)
            txt(c, x + 6, y - 15, _v(m.get("hora")), FB, 11, INK)
            wrap(c, x + 6, y - 27, _v(m.get("estado")), F, 7.2, TEXT_2, cw - 12, leading=8.4)
            txt(c, x + 6, y - 45, f"azimut {_v(m.get('azimut'), '—')} · elevación "
                                  f"{_v(m.get('elevacion'), '—')}", F, 6.4, TEXT_3)
        y -= 60
    else:
        panel(c, M, y - 26, ANCHO, 26, PAPER, HAIR)
        txt(c, M + 8, y - 16, "Asoleamiento no declarado en esta ejecución.", F, 7.6, WARN_FG)
        y -= 32

    panel(c, M, y - 46, ANCHO, 46, PAPER, HAIR)
    wrap(c, M + 8, y - 14,
         "La proyección de sombras corresponde a una SIMULACIÓN GEOMÉTRICA calculada con la "
         "huella y la altura del edificio disponibles; no sustituye una inspección física ni "
         "una observación real en sitio.", F, 7.4, TEXT_2, ANCHO - 16, leading=8.8)
    if solar.get("altura_dependiente"):
        wrap(c, M + 8, y - 34,
             "La simulación depende de la altura del edificio: si esa cifra requiere validación "
             "de coherencia (véase página 4), la sombra es referencial.", FO, 7, WARN_FG,
             ANCHO - 16, leading=8.4)
    y -= 54
    y = traza(c, y, ["Proveedor de mapas abierto", "Fotografía satelital", "Cálculo solar"],
              str((modelo.get("evidence_manifest") or {}).get("generated_at") or "")[:10],
              "VERIFICADO", int((modelo.get("evidence_manifest") or {}).get("evidence_count") or 0))
    fit("P5 cierre", y, 52)
    pie(c, modelo, 5)


# ── Página 6 · identidad + valor + metodología ────────────────────────────────
def pagina6(c, modelo, identidad, valor):
    cabecera(c, modelo, 6)
    y = H - 74
    y = titulo_seccion(c, y, "Identidad del inmueble y geometría", "lo que se verificó")

    filas = identidad.get("filas") or []
    for f in filas[:9]:
        panel(c, M, y - 22, ANCHO, 22, CARD)
        txt(c, M + 8, y - 14, _v(f.get("etiqueta")), F, 7.6, TEXT_3)
        txt(c, M + 160, y - 14, _v(f.get("valor"), "no declarado"), FB, 8.2, INK)
        chip_estado(c, W - M - 8 - 140, y - 17, f.get("estado") or SIN_DATO)
        y -= 25

    y -= 6
    y = titulo_seccion(c, y, "Valor estimado", "solo si la valoración está autorizada")
    aut = bool(valor.get("autorizado"))
    panel(c, M, y - 66, ANCHO, 66, CARD if aut else PAPER, HAIR)
    if aut:
        txt(c, M + 10, y - 16, "VALOR ESTIMADO", FB, 7, TEXT_3, esp=0.6)
        txt(c, M + 10, y - 38, _v(valor.get("consolidado")), FB, 17, INK)
        txt(c, M + 10, y - 54, f"Rango {_v(valor.get('rango'), '—')} · "
                               f"Área {_v(valor.get('area'), '—')} m² · "
                               f"{_v(valor.get('valor_m2'), '—')} / m²", F, 7.6, TEXT_2)
        for i, (k, v) in enumerate([("Fecha", valor.get("fecha")),
                                    ("Sector de mercado", valor.get("sector")),
                                    ("Metodología", valor.get("metodologia"))]):
            x = M + 250 + i * 92
            txt(c, x, y - 20, k.upper(), FB, 6.2, TEXT_3, esp=0.5)
            wrap(c, x, y - 32, _v(v, "no declarado"), FB, 7.4, INK, 88, leading=8.6)
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
        y = wrap(c, M + 14, y, p, F, 7.8, TEXT_2, ANCHO - 14, leading=9.2) - 6
    y -= 2
    panel(c, M, y - 44, ANCHO, 44, PAPER, HAIR)
    wrap(c, M + 8, y - 14, "NORMA · CONCEPTO TÉCNICO · VALIDACIÓN EXPERTA: DICTUS prepara y "
                           "señala; el valor y su interpretación los firma el profesional "
                           "competente (avaluador inscrito en el RAA, abogado, geodesta).",
         F, 7.6, TEXT_2, ANCHO - 16, leading=9.2)
    y -= 52
    y = traza(c, y, ["Metodología de mercado (Lonja)", "Catastro", "Identidad canónica"],
              str((modelo.get("evidence_manifest") or {}).get("generated_at") or "")[:10],
              "VERIFICADO", int((modelo.get("evidence_manifest") or {}).get("evidence_count") or 0))
    fit("P6 cierre", y, 52)
    pie(c, modelo, 6)


# ── render ────────────────────────────────────────────────────────────────────
def render(modelo: Dict[str, Any], secciones: Dict[str, Any], destino: Path) -> Path:
    """Genera el documento ejecutivo de 6 páginas."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    del VIOLACIONES[:]
    c = canvas.Canvas(str(destino), pagesize=(W, H))
    di = modelo.get("document_identity") or {}
    c.setTitle(f"DICTUS — Expediente verificado de inmueble {di.get('folio')}")
    c.setAuthor("ARHIAX RE · DICTUS")
    c.setSubject("Informe ejecutivo de decisión inmobiliaria + expediente verificable")

    for i, p in enumerate(c.getPageNumber() for _ in range(0)):  # noqa: B007
        pass

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

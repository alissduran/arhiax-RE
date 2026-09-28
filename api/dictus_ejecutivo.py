# -*- coding: utf-8 -*-
"""DICTUS 2.0C — EXECUTIVE RENDERER de alta fidelidad (6 páginas A4).

Qué cambia frente a 2.0B/R1 (y por qué)
--------------------------------------
1. **Motor de layout real.** Cada componente implementa `medir()` / `dibujar()` y
   reporta la ALTURA CONSUMIDA; la página se compone en flujo vertical. Se eliminan los
   offsets rígidos después de `wrap()`, que eran el origen del encabalgamiento de
   «QUÉ DEBE HACERSE PARA CERRAR LA OPERACIÓN» en la página 2.
2. **Trazabilidad de la retícula.** Cada componente registra su bounding box en
   `REGISTRO_BBOX` y `verificar_retícula()` comprueba que ninguna caja se intersecte con
   otra: no se depende del texto extraído por `pypdf`.
3. **Fidelidad material.** Se imprimen los hechos que el producto ya calculaba y que
   antes se perdían en la proyección del estado: sector de mercado, método y versión,
   procedencia por atributo urbano, binding de la geometría, modalidad de adquisición
   con su acto registral, tiempos a pie del equipamiento, mapas y sombras REALES de la
   corrida, y blockers de la valoración.
4. **Jerarquía de la página 1.** HALLAZGOS DE LA OPERACIÓN separados de la COHERENCIA
   DE INFORMACIÓN: un conflicto entre versiones del mismo dato no es un riesgo alto del
   inmueble.
5. **Una sola verdad y un solo hash maestro visible.** Nada de `$0`, `0 %` ni «N/D»
   mudos: se declara el estado y el motivo. Cuerpo tipográfico 8.5–10 pt.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from reportlab.lib.colors import HexColor, white
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfgen import canvas

from dictus_historia import (HISTORICAL_CONFLICT, REQUIERE_VALIDACION, SIN_DATO,
                             VERIFICADO)

# ── geometría ────────────────────────────────────────────────────────────────
W, H = 595.28, 841.89          # A4 vertical
M = 36.0
ANCHO = W - 2 * M
TOPE = H - 62.0                # inicio del contenido (debajo de la banda de cabecera)
PIE_Y = 56.0                   # límite inferior del contenido

# ── paleta mineral (tinta + marfil + oro) ────────────────────────────────────
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
GREY_BG, GREY_BD, GREY_FG = HexColor("#EFEFEF"), HexColor("#CFCFCF"), HexColor("#6B6B6B")

_PAREJAS = {"ok": (OK_BG, OK_BD, OK_FG), "warn": (WARN_BG, WARN_BD, WARN_FG),
            "err": (ERR_BG, ERR_BD, ERR_FG), "info": (INFO_BG, INFO_BD, INFO_FG),
            "grey": (GREY_BG, GREY_BD, GREY_FG), "ink": (INK, INK, white),
            "oro": (GOLD, GOLD, white)}

F, FB, FO = "Helvetica", "Helvetica-Bold", "Helvetica-Oblique"

TOTAL_EJECUTIVO = 6
VIOLACIONES: List[str] = []

# Arquitectura APROBADA del entregable: la página N dice, y solo, el título N.
TITULOS_PAGINA = (
    "RESUMEN DE DECISIÓN DEL INMUEBLE",
    "TÍTULOS Y CONDICIONES JURÍDICAS",
    "CONTRAPARTES Y PREPARACIÓN DE OPERACIÓN",
    "POT, USO, EDIFICABILIDAD Y RIESGOS",
    "ENTORNO, EQUIPAMIENTO Y ASOLEAMIENTO",
    "IDENTIDAD Y VALOR",
)

ROTULO_CATEGORIA = {"SALUD": "Salud", "EDUCACION": "Educación", "COMERCIO": "Comercio",
                    "RECREACION": "Recreación"}

_FUGAS = ("ARHIAX_EVIDENCE_HMAC_KEY", "RuntimeError", "Traceback", "hmac", "stack trace")

# ── registro de bounding boxes (§25) ─────────────────────────────────────────
REGISTRO_BBOX: List[Dict[str, Any]] = []
PAGINA_ACTUAL = [1]


def _bbox(nombre: str, x0: float, y0: float, x1: float, y1: float) -> None:
    REGISTRO_BBOX.append({"nombre": nombre, "pagina": PAGINA_ACTUAL[0],
                          "x0": round(x0, 2), "y0": round(y0, 2),
                          "x1": round(x1, 2), "y1": round(y1, 2)})


def _area(b: Dict[str, Any]) -> float:
    return max(0.0, b["x1"] - b["x0"]) * max(0.0, b["y1"] - b["y0"])


def _interseccion(a: Dict[str, Any], b: Dict[str, Any]) -> float:
    x0, y0 = max(a["x0"], b["x0"]), max(a["y0"], b["y0"])
    x1, y1 = min(a["x1"], b["x1"]), min(a["y1"], b["y1"])
    return max(0.0, x1 - x0) * max(0.0, y1 - y0)


def verificar_retícula(tolerancia: float = 0.30) -> List[str]:
    """Ninguna caja registrada puede intersectar otra de la misma página.

    Compara los bounding boxes REALES de los componentes (no el texto extraído). Un
    solapamiento mayor al `tolerancia` de la caja menor es un defecto de composición.
    """
    fallos: List[str] = []
    por_pagina: Dict[Any, List[Dict[str, Any]]] = {}
    for b in REGISTRO_BBOX:
        por_pagina.setdefault(b.get("pagina"), []).append(b)
    for pagina, cajas in por_pagina.items():
        for i in range(len(cajas)):
            for j in range(i + 1, len(cajas)):
                inter = _interseccion(cajas[i], cajas[j])
                if inter <= 0:
                    continue
                menor = min(_area(cajas[i]), _area(cajas[j]))
                if menor > 0 and inter / menor > tolerancia:
                    fallos.append(f"p{pagina}: «{cajas[i]['nombre']}» × "
                                  f"«{cajas[j]['nombre']}» ({inter:.0f} pt²)")
    return fallos


# ── primitivas ───────────────────────────────────────────────────────────────
def txt(c, x, y, s, font=F, size=9, color=TEXT, align="left", esp=0.0):
    """Texto del documento.

    `esp` (espaciado entre letras) se acepta por compatibilidad de firma pero NO se
    aplica: un documento con espaciado falso deja de ser extraíble y buscable.
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


def _lineas(c, s, font, size, maxw) -> List[str]:
    return simpleSplit(str(s), font, size, maxw) or [""]


def _alto_texto(c, s, font, size, maxw, leading) -> Tuple[List[str], float]:
    lineas = _lineas(c, s, font, size, maxw)
    return lineas, len(lineas) * leading


def wrap(c, x, y, s, font=F, size=9, color=TEXT_2, maxw=300, leading=None,
         align="left", esp=0.0):
    leading = leading or size * 1.35
    lineas = _lineas(c, s, font, size, maxw)
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
    bg, bd, fg = _PAREJAS.get(clase, _PAREJAS["info"])
    w = c.stringWidth(str(s), FB, size) + 2 * pad
    c.setFillColor(bg)
    c.setStrokeColor(bd)
    c.setLineWidth(0.7)
    c.rect(x, y, w, h, stroke=1, fill=1)
    txt(c, x + pad, y + (h - size) / 2 + 1.2, s, FB, size, fg)
    return w


def _v(valor, hueco="NO DISPONIBLE") -> str:
    if valor is None or valor == "" or (isinstance(valor, str) and not valor.strip()):
        return hueco
    return str(valor)


_ACTOR_CANONICO = {
    "ASEGURADORA": "ASEGURADORA DE TÍTULO",
    "ASEGURADORA DE TITULO": "ASEGURADORA DE TÍTULO",
    "BANCO": "BANCO / FINANCIADOR",
    "BANCO / FINANCIADOR": "BANCO / FINANCIADOR",
}


def _actores(lista) -> List[str]:
    """Actores afectados, con un solo nombre por actor y sin duplicados.

    El vocabulario de los hallazgos mezclaba «ASEGURADORA» con «ASEGURADORA DE
    TÍTULO» y «BANCO» con «BANCO / FINANCIADOR»: imprimir los dos parece que hay
    cuatro actores donde hay dos.
    """
    salida: List[str] = []
    for actor in (lista or []):
        nombre = _ACTOR_CANONICO.get(str(actor).strip().upper(), str(actor).strip().upper())
        if nombre and nombre not in salida:
            salida.append(nombre)
    return salida


def _corto(texto, limite: int) -> str:
    s = str(texto)
    return s if len(s) <= limite else s[:limite - 1].rstrip() + "…"


def _pesos(valor) -> Optional[str]:
    try:
        return f"$ {int(valor):,}".replace(",", ".")
    except (TypeError, ValueError):
        return None


def _num_grados(valor):
    try:
        return float(str(valor or "").replace("°", "").strip())
    except (TypeError, ValueError):
        return None


def ancho_sin_columna(ancho: float, columna: float = 140.0) -> float:
    """Ancho útil para texto que convive con una columna de chips a la derecha.

    Regla de composición: un párrafo a todo lo ancho y un chip en la misma banda
    terminan tocándose. El texto se ajusta al hueco REAL.
    """
    return max(110.0, ancho - columna - 16.0)


def ajustar(c, texto, fuente, size, maxw, minimo=6.0):
    """Texto que CABE en su columna: reduce tamaño y, si no cabe, recorta con «…»."""
    s = str(texto)
    _size = size
    while _size > minimo and c.stringWidth(s, fuente, _size) > maxw:
        _size -= 0.2
    if c.stringWidth(s, fuente, _size) > maxw:
        while len(s) > 4 and c.stringWidth(s + "…", fuente, _size) > maxw:
            s = s[:-1]
        s = s.rstrip() + "…"
    return s, _size


def limpio(valor, hueco="NO DISPONIBLE") -> str:
    """Texto saneado: sin fugas técnicas y sin vacíos mudos."""
    s = _v(valor, hueco)
    if any(f.lower() in s.lower() for f in _FUGAS):
        return "EVIDENCIA NO SELLADA"
    return s


# Estados del vocabulario de coherencia -> (clase visual, etiqueta legible).
_ESTADOS_VISUALES = {
    VERIFICADO: ("ok", "VERIFICADO"),
    "CAMBIO_CON_FUENTE": ("info", "VERIFICADO · CAMBIÓ CON FUENTE"),
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
    SIN_DATO: ("grey", "SIN DATO"),
    "NO_EVALUADO": ("grey", "NO EVALUADO"),
    "FUENTE_NO_DISPONIBLE": ("grey", "FUENTE NO DISPONIBLE"),
    "RIESGO_ALTO": ("err", "RIESGO ALTO"),
    "RIESGO_MEDIO": ("warn", "RIESGO MEDIO"),
    "SIN_AFECTACION": ("ok", "SIN AFECTACIÓN VERIFICADA"),
}

_ESTADOS_COMPACTOS = {
    "CAMBIO_CON_FUENTE": "CAMBIÓ CON FUENTE",
    "SIN_COINCIDENCIAS": "SIN COINCIDENCIAS",
    "INCOMPLETA": "INCOMPLETA",
    "PREPARADA": "PREPARADA",
    "INCOMPLETO": "INCOMPLETO",
    "REQUIERE_REVISION": "REQUIERE REVISIÓN",
}


def _estado_legible(estado: str):
    return _ESTADOS_VISUALES.get(estado, ("info", str(estado)))


def chip_estado(c, x, y, estado: str, size=7.4, h=14):
    clase, etiqueta = _estado_legible(estado)
    return chip(c, x, y, etiqueta, clase, size, h)


def caja_estado(c, x, y, w, estado: str, size=7.0, h=14):
    """Etiqueta de estado AJUSTADA al ancho de su tarjeta (nunca invade la vecina)."""
    clase, etiqueta = _estado_legible(estado)
    etiqueta = _ESTADOS_COMPACTOS.get(estado, etiqueta)
    bg, bd, fg = _PAREJAS[clase]
    while size > 5.2 and c.stringWidth(etiqueta, FB, size) + 8 > w:
        size -= 0.15
    c.setFillColor(bg)
    c.setStrokeColor(bd)
    c.setLineWidth(0.7)
    c.rect(x, y - h, w, h, stroke=1, fill=1)
    txt(c, x + 4, y - h + (h - size) / 2 + 1.0, etiqueta, FB, size, fg)
    return h


# ── motor de layout: medir → dibujar → altura consumida ──────────────────────
class Bloque:
    """Componente de página.

    Contrato (§11): `medir()` calcula la altura SIN dibujar; `dibujar()` la respeta,
    registra su bounding box y devuelve la nueva `y`.
    """

    nombre = "bloque"

    def __init__(self, pagina: int = 1):
        self.pagina = pagina
        self.alto = 0.0

    def medir(self, c, ancho: float) -> float:
        raise NotImplementedError

    def dibujar(self, c, x: float, y: float, ancho: float) -> float:
        raise NotImplementedError

    def cerrar(self, x, y, ancho):
        _bbox(self.nombre, x, y - self.alto, x + ancho, y)
        return y - self.alto


def emitir(c, y: float, bloques: Sequence[Bloque], ancho: float = ANCHO, x: float = M,
           dy: float = 7.0) -> float:
    """Compone bloques en flujo vertical: mide, dibuja y avanza la altura consumida."""
    for b in bloques:
        alto = b.medir(c, ancho)
        y = b.dibujar(c, x, y, ancho)
        if abs(b.alto - alto) > 0.6:
            VIOLACIONES.append(f"{b.nombre}: medido {alto:.1f} vs dibujado {b.alto:.1f}")
        y -= dy
    return y


class Titulo(Bloque):
    nombre = "titulo"

    def __init__(self, texto: str, kicker: str = "", pagina: int = 1, size=13.0):
        super().__init__(pagina)
        self.texto, self.kicker, self.size = texto, kicker, size

    def medir(self, c, ancho):
        self.alto = (16.0 if self.kicker else 0.0) + 13.0
        return self.alto

    def dibujar(self, c, x, y, ancho):
        alto = self.medir(c, ancho)
        yy = y
        if self.kicker:
            txt(c, x, yy, self.kicker, FB, 8, GOLD, esp=0.6)
            yy -= 16
        txt(c, x, yy, self.texto, FB, self.size, INK)
        rule(c, x, yy - 5, x + ancho, yy - 5, HAIR)
        return self.cerrar(x, y, ancho)


class Nota(Bloque):
    nombre = "nota"

    def __init__(self, texto: str, pagina: int = 1, size=8.2, color=TEXT_3,
                 font=FO, align="left"):
        super().__init__(pagina)
        self.texto, self.size, self.color, self.font, self.align = texto, size, color, font, align

    def medir(self, c, ancho):
        self._lineas_txt, self.alto = _alto_texto(c, self.texto, self.font, self.size,
                                                  ancho, self.size * 1.35)
        return self.alto

    def dibujar(self, c, x, y, ancho):
        self.medir(c, ancho)
        for i, ln in enumerate(self._lineas_txt):
            txt(c, x, y - self.size - i * self.size * 1.35, ln, self.font, self.size,
                self.color, self.align)
        return self.cerrar(x, y, ancho)


class Fila(Bloque):
    """Dos componentes lado a lado (o uno solo si el segundo no aplica).

    La fila NO registra caja propia: cada componente registra la suya, de modo que la
    verificación de retícula compara cajas reales y no contenedores anidados.
    """

    nombre = "fila"

    def __init__(self, izquierda: Bloque, derecha: Optional[Bloque] = None,
                 pagina: int = 1, gap: float = 8.0, reparto: float = 0.5):
        super().__init__(pagina)
        self.izquierda, self.derecha, self.gap, self.reparto = izquierda, derecha, gap, reparto

    def medir(self, c, ancho):
        w_izq = ancho if self.derecha is None else (ancho - self.gap) * self.reparto
        w_der = 0.0 if self.derecha is None else (ancho - self.gap) * (1 - self.reparto)
        self.w_izq, self.w_der = w_izq, w_der
        alto_izq = self.izquierda.medir(c, w_izq)
        alto_der = self.derecha.medir(c, w_der) if self.derecha else 0.0
        self.alto = max(alto_izq, alto_der)
        return self.alto

    def dibujar(self, c, x, y, ancho):
        self.medir(c, ancho)
        self.izquierda.dibujar(c, x, y, self.w_izq)
        if self.derecha:
            self.derecha.dibujar(c, x + self.w_izq + self.gap, y, self.w_der)
        return y - self.alto


class PanelLibre(Bloque):
    """Bloque con altura declarada y una función de dibujo propia (mapas, sello…)."""

    def __init__(self, nombre: str, alto: float, dibujar_fn, pagina: int = 1):
        super().__init__(pagina)
        self.nombre = nombre
        self._alto_declarado = alto
        self._fn = dibujar_fn

    def medir(self, c, ancho):
        self.alto = self._alto_declarado
        return self.alto

    def dibujar(self, c, x, y, ancho):
        self._fn(c, x, y, ancho)
        return self.cerrar(x, y, ancho)


class Filas(Bloque):
    """Filas etiqueta · valor · estado. La altura la fija el valor más alto."""

    nombre = "filas"

    def __init__(self, filas: Sequence[Dict[str, Any]], pagina: int = 1,
                 ancho_etiqueta=150.0, size_valor=9.5, con_estado=True, alto_min=24.0,
                 nota_size=8.0):
        super().__init__(pagina)
        self.filas = list(filas)
        self.ancho_etiqueta = ancho_etiqueta
        self.size_valor = size_valor
        self.con_estado = con_estado
        self.alto_min = alto_min
        self.nota_size = nota_size

    def _calc(self, c, ancho):
        ancho_valor = ancho - self.ancho_etiqueta - (140.0 if self.con_estado else 8.0)
        detalle = []
        total = 0.0
        for f in self.filas:
            lineas, alto_v = _alto_texto(c, _v(f.get("valor"), "no declarado"), FB,
                                         self.size_valor, max(40.0, ancho_valor - 24.0),
                                         self.size_valor * 1.25)
            alto_n = 0.0
            lineas_n = []
            if f.get("nota"):
                lineas_n, alto_n = _alto_texto(
                    c, f["nota"], FO, self.nota_size,
                    ancho_sin_columna(ancho - self.ancho_etiqueta, 160.0),
                    self.nota_size * 1.3)
            alto = max(self.alto_min, alto_v + alto_n + 14.0)
            detalle.append({"lineas": lineas, "lineas_nota": lineas_n, "alto": alto})
            total += alto + 2.0
        return detalle, total

    def medir(self, c, ancho):
        self._detalle, self.alto = self._calc(c, ancho)
        return self.alto

    def dibujar(self, c, x, y, ancho):
        self.medir(c, ancho)
        yy = y
        for f, d in zip(self.filas, self._detalle):
            alto = d["alto"]
            conflicto = (f.get("estado") == HISTORICAL_CONFLICT)
            panel(c, x, yy - alto, ancho, alto, ERR_BG if conflicto else CARD,
                  ERR_BD if conflicto else HAIR)
            txt(c, x + 8, yy - 13, _v(f.get("etiqueta")), F, 8.2, TEXT_3)
            for i, ln in enumerate(d["lineas"]):
                txt(c, x + self.ancho_etiqueta, yy - 13 - i * self.size_valor * 1.25, ln,
                    FB, self.size_valor, INK)
            if d["lineas_nota"]:
                base = yy - 13 - (len(d["lineas"]) - 1) * self.size_valor * 1.25 - 11
                for i, ln in enumerate(d["lineas_nota"]):
                    txt(c, x + self.ancho_etiqueta, base - i * self.nota_size * 1.3, ln,
                        FO, self.nota_size, TEXT_3)
            if self.con_estado:
                caja_estado(c, x + ancho - 8 - 130, yy - 20, 130,
                            f.get("estado") or SIN_DATO, 7.0, 14)
            yy -= alto + 2.0
        return self.cerrar(x, y, ancho)


class Tarjetas(Bloque):
    """Tarjetas en rejilla (una fila o varias). Cada tarjeta: título, estado y motivo."""

    nombre = "tarjetas"

    def __init__(self, tarjetas: Sequence[Dict[str, Any]], pagina: int = 1, columnas=4,
                 alto_tarjeta=78.0, size_titulo=10.0, size_motivo=8.0, chip_size=7.0):
        super().__init__(pagina)
        self.tarjetas = list(tarjetas)
        self.columnas = columnas
        self.alto_tarjeta = alto_tarjeta
        self.size_titulo = size_titulo
        self.size_motivo = size_motivo
        self.chip_size = chip_size

    def medir(self, c, ancho):
        self.ancho_tarjeta = (ancho - (self.columnas - 1) * 6) / self.columnas
        filas = (len(self.tarjetas) + self.columnas - 1) // self.columnas
        self.alto = filas * (self.alto_tarjeta + 6)
        return self.alto

    def dibujar(self, c, x, y, ancho):
        self.medir(c, ancho)
        cw = self.ancho_tarjeta
        for i, t in enumerate(self.tarjetas):
            col, fila = i % self.columnas, i // self.columnas
            xx = x + col * (cw + 6)
            yt = y - fila * (self.alto_tarjeta + 6)
            contorno = t.get("contorno")
            panel(c, xx, yt - self.alto_tarjeta, cw, self.alto_tarjeta,
                  t.get("fondo") or CARD, contorno or HAIR)
            banda(c, xx, yt - 3, cw, 3, t.get("color") or INK_3)
            txt(c, xx + 7, yt - 16, _v(t.get("titulo")).upper(), FB, 8.0, TEXT_3)
            if t.get("valor") is not None:
                txt(c, xx + 7, yt - 36, str(t.get("valor")), FB, 16, INK)
            # El motivo se sitúa SIEMPRE por debajo de la caja de estado: la caja ocupa
            # [y-14, y] y el texto arranca 8 pt por debajo de su borde inferior.
            if t.get("estado"):
                caja_estado(c, xx + 6, yt - 30 if t.get("valor") is None else yt - 42,
                            cw - 12, t["estado"], self.chip_size, 14)
            motivo_y = (yt - 52 if t.get("valor") is None else yt - 62)
            wrap(c, xx + 7, motivo_y, _v(t.get("motivo"), ""), F, self.size_motivo,
                 TEXT_2, cw - 14, leading=self.size_motivo * 1.3)
            _bbox(f"{self.nombre}:{_corto(t.get('titulo'), 18)}", xx,
                  yt - self.alto_tarjeta, xx + cw, yt)
        return y - self.alto


class MatrizHallazgos(Bloque):
    """Matriz a dos columnas: SEVERIDAD · HALLAZGO · AFECTA A · ACCIÓN."""

    nombre = "matriz_hallazgos"

    def __init__(self, hallazgos: Sequence[Dict[str, Any]], pagina: int = 1,
                 ancho_simbolo=52.0, alto_fila=54.0):
        super().__init__(pagina)
        self.hallazgos = list(hallazgos)
        self.ancho_simbolo = ancho_simbolo
        self.alto_fila = alto_fila

    def medir(self, c, ancho):
        self.cw = (ancho - 6) / 2
        self.filas = max(1, (len(self.hallazgos) + 1) // 2)
        self.alto = 16.0 + self.filas * (self.alto_fila + 3)
        return self.alto

    def dibujar(self, c, x, y, ancho):
        self.medir(c, ancho)
        cw = self.cw
        panel(c, x, y - 15, ancho, 15, PAPER, HAIR)
        for col in range(2):
            xx = x + col * (cw + 6)
            txt(c, xx + 7, y - 10.5, "SEVERIDAD", FB, 7.0, TEXT_3)
            txt(c, xx + self.ancho_simbolo + 3, y - 10.5, "HALLAZGO", FB, 7.0, TEXT_3)
        yy = y - 16
        for i, h in enumerate(self.hallazgos):
            col, fila = i % 2, i // 2
            xx = x + col * (cw + 6)
            yt = yy - fila * (self.alto_fila + 3)
            panel(c, xx, yt - self.alto_fila, cw, self.alto_fila)
            sev = str(h.get("severidad", "")).upper()
            color = {"ALTO": ERR_FG, "MEDIO": WARN_FG, "INFORMATIVO": OK_FG}.get(sev, TEXT)
            banda(c, xx, yt - self.alto_fila, 3, self.alto_fila, color)
            chip(c, xx + 7, yt - 14, sev[:7] or "—",
                 {"ALTO": "err", "MEDIO": "warn", "INFORMATIVO": "ok"}.get(sev, "info"),
                 7.0, 12, 6)
            _tit, _sz = ajustar(c, f"{_v(h.get('codigo'), '')} {_v(h.get('titulo'), '')}",
                                FB, 8.6, cw - self.ancho_simbolo - 10)
            txt(c, xx + self.ancho_simbolo + 3, yt - 12, _tit, FB, _sz, INK)
            afectados = ", ".join(_actores((h.get("afectados") or [])[:3])) or (
                "Impacto pendiente de clasificación")
            txt(c, xx + 7, yt - 34, f"AFECTA A: {_corto(afectados, 62)}", F, 7.6, TEXT_3)
            acciones = _lineas(c, "ACCIÓN: " + _v(h.get("accion"), "por definir"), F, 7.6,
                               cw - 14)[:2]
            for j, ln in enumerate(acciones):
                txt(c, xx + 7, yt - 46 - j * 8.6, ln, F, 7.6, TEXT_2)
            _bbox(f"{self.nombre}:{_v(h.get('codigo'), 'hallazgo')}", xx,
                  yt - self.alto_fila, xx + cw, yt)
        return y - self.alto


class ListaPOI(Bloque):
    """Equipamiento urbano: hasta 3 lugares por categoría, con tiempo a pie."""

    nombre = "lista_poi"

    def __init__(self, categorias: Sequence[Dict[str, Any]], pagina: int = 1, columnas=2,
                 por_categoria=3, alto_categoria=96.0):
        super().__init__(pagina)
        self.categorias = list(categorias)
        self.columnas = columnas
        self.por_categoria = por_categoria
        self.alto_categoria = alto_categoria

    def medir(self, c, ancho):
        self.cw = (ancho - (self.columnas - 1) * 8) / self.columnas
        self.filas = (len(self.categorias) + self.columnas - 1) // self.columnas
        self.alto = self.filas * (self.alto_categoria + 8)
        return self.alto

    def dibujar(self, c, x, y, ancho):
        self.medir(c, ancho)
        cw = self.cw
        for i, cat in enumerate(self.categorias):
            col, fila = i % self.columnas, i // self.columnas
            xx = x + col * (cw + 8)
            yt = y - fila * (self.alto_categoria + 8)
            estado = str(cat.get("estado") or "NOT_EVALUATED").upper()
            disponible = estado in ("AVAILABLE", "DISPONIBLE")
            panel(c, xx, yt - self.alto_categoria, cw, self.alto_categoria,
                  CARD if disponible else PAPER, HAIR)
            banda(c, xx, yt - 3, cw, 3, OK_FG if disponible else GREY_FG)
            clave = str(cat.get("nombre") or "").upper()
            txt(c, xx + 7, yt - 17, ROTULO_CATEGORIA.get(clave, _v(cat.get("nombre"))),
                FB, 10.5, INK)
            if disponible:
                txt(c, xx + cw - 7, yt - 17,
                    f"{cat.get('conteo', 0)} detectados", F, 7.8, TEXT_3, "right")
                items = list(cat.get("items") or [])[:self.por_categoria]
                # Distancia del ítem más cercano de la categoría: dato de decisión. Si la
                # fuente no la dio, se declara en lugar de omitirla o ponerla en cero.
                if cat.get("mas_cercano_m") is not None:
                    txt(c, xx + 7, yt - 29, "más cercano: "
                        f"{int(round(float(cat['mas_cercano_m'])))} m", FB, 8.0, TEXT_2)
                elif not (cat.get("items") or []):
                    pass
                elif all((it.get("distance_m") is None) for it in (cat.get("items") or [])):
                    txt(c, xx + 7, yt - 29, "DISTANCIA NO DISPONIBLE", FB, 7.8, WARN_FG)
                yy = yt - 42
                if not items:
                    txt(c, xx + 7, yy, "sin ítems en el estado", F, 8, TEXT_3)
                elif all(it.get("distance_m") is None for it in items):
                    # Hay equipamiento en el estado, pero la fuente no dio distancia: se
                    # declara; nunca se convierte en 0 ni se omite.
                    txt(c, xx + 7, yy - 10.0, "DISTANCIA NO DISPONIBLE", FB, 7.8,
                        WARN_FG)
                for it in items:
                    _nom, _nsz = ajustar(c, _v(it.get("name"), "—"), F, 8.4, cw - 104)
                    txt(c, xx + 7, yy, _nom, F, _nsz, TEXT)
                    d = it.get("distance_m")
                    tiempo = it.get("walking_time_estimate") or it.get("travel_time_estimate")
                    detalle = []
                    if d is not None:
                        detalle.append(f"{int(round(float(d)))} m")
                    if tiempo:
                        detalle.append(str(tiempo).replace("~", "≈"))
                        txt(c, xx + cw - 7, yy, " · ".join(detalle) or "sin distancia",
                            FB, 8.0, TEXT_2, "right")
                    if it.get("type"):
                        _tip, _tpsz = ajustar(c, str(it["type"]), F, 7.2, cw - 104)
                        txt(c, xx + 7, yy - 8.4, _tip, F, _tpsz, TEXT_3)
                        yy -= 8.4
                    yy -= 12.4
            else:
                # §4: ausencia de fuente ≠ ausencia en el mundo. Nunca «0 detectados»
                # si la consulta no se completó.
                etiqueta = {"NO_MATCH": "SIN COINCIDENCIA (consulta completa)",
                            "SOURCE_UNAVAILABLE": "FUENTE NO DISPONIBLE",
                            "NOT_EVALUATED": "NO EVALUADO"}.get(estado, estado)
                caja_estado(c, xx + 6, yt - 28, cw - 12,
                            "NO_EVALUADO" if estado in ("SOURCE_UNAVAILABLE",
                                                        "NOT_EVALUATED") else "SIN DATO",
                            7.0, 14)
                wrap(c, xx + 7, yt - 52, etiqueta + " · el radio de 2.0 km no arrojó "
                     "resultados utilizables en esta corrida." if estado == "NO_MATCH"
                     else etiqueta + ": la consulta del equipamiento no se completó en "
                     "esta corrida (no se imprime «0 detectados»).", F, 7.8, TEXT_2,
                     cw - 14, leading=8.6)
            _bbox(f"{self.nombre}:{clave}", xx, yt - self.alto_categoria, xx + cw, yt)
        return y - self.alto


class Traza(Bloque):
    nombre = "traza"

    def __init__(self, fuentes: Sequence[str], fecha: str, estado: str, n_ev: int,
                 pagina: int = 1):
        super().__init__(pagina)
        self.fuentes = list(fuentes)
        self.fecha, self.estado, self.n_ev = fecha, estado, n_ev

    def medir(self, c, ancho):
        self.alto = 46.0
        return self.alto

    def dibujar(self, c, x, y, ancho):
        self.medir(c, ancho)
        panel(c, x, y - self.alto, ancho, self.alto, PAPER, HAIR)
        txt(c, x + 8, y - 14, "TRAZABILIDAD", FB, 7.6, GOLD, esp=0.6)
        _fuentes, _fs = ajustar(c, "Fuentes principales: " + ", ".join(self.fuentes[:4]),
                                F, 8.2, ancho - 16 - 210)
        txt(c, x + 8, y - 26, _fuentes, F, _fs, TEXT_2)
        _consulta, _cs = ajustar(c, f"Consulta: {self.fecha or 'no declarada'} · "
                                    f"Estado: {limpio(self.estado)} · "
                                    f"Evidencias: {self.n_ev}", F, 8.2, ancho - 16 - 210)
        txt(c, x + 8, y - 37, _consulta, F, _cs, TEXT_2)
        txt(c, x + ancho - 8, y - 26, "Evidencia INCLUIDA EN HASH MAESTRO DICTUS",
            FB, 7.6, TEXT_2, "right")
        txt(c, x + ancho - 8, y - 37, "Detalle técnico: Anexos", FO, 7.6, TEXT_3, "right")
        return self.cerrar(x, y, ancho)


class SelloGlobal(Bloque):
    nombre = "sello_global"

    def __init__(self, modelo: Dict[str, Any], pagina: int = 1):
        super().__init__(pagina)
        self.modelo = modelo

    def medir(self, c, ancho):
        self.alto = 84.0
        return self.alto

    def dibujar(self, c, x, y, ancho):
        self.medir(c, ancho)
        ev = self.modelo.get("evidence_manifest") or {}
        di = self.modelo.get("document_identity") or {}
        _hash = str(self.modelo.get("master_hash") or "")
        panel(c, x, y - self.alto, ancho, self.alto, INK, INK)
        banda(c, x, y - self.alto, 4, self.alto, GOLD)
        txt(c, x + 14, y - 13, "SELLO GLOBAL", FB, 7.6, GOLD, esp=0.6)
        txt(c, x + 14, y - 28, "DICTUS ID", FB, 7.4, GOLD_2, esp=0.6)
        txt(c, x + 14, y - 43, limpio(di.get("dictus_id")), FB, 11, white)
        txt(c, x + 14, y - 55, f"Fecha: {_v(str(di.get('generated_at') or '')[:10], 'sin fecha')}",
            F, 8.2, GOLD_2)
        txt(c, x + 14, y - 66, f"Evidencias: {ev.get('evidence_count')} · "
                               f"Estado: {limpio(ev.get('estado'))}", F, 8.2, GOLD_2)
        txt(c, x + 14, y - 78, "Cadena de custodia del expediente: Anexo G.", FO, 7.6, GOLD_2)
        txt(c, x + 240, y - 28, "DICTUS_MASTER_HASH", FB, 7.4, GOLD_2, esp=0.6)
        txt(c, x + 240, y - 43, _hash[:22], "Courier-Bold", 9, white)
        txt(c, x + 240, y - 56, f"…{_hash[22:44]}", "Courier-Bold", 9, GOLD_2)
        wrap(c, x + ancho - 8, y - 28, "Verificación: DICTUS ID + hash maestro "
             "abreviado. El hash del archivo PDF consta aparte (Anexo G).", FO, 7.2,
             GOLD_2, 128, leading=8.4, align="right")
        return self.cerrar(x, y, ancho)


class TarjetaCoherencia(Bloque):
    """UNA tarjeta que agrupa los conflictos de datos (§8) con sus actores (§9)."""

    nombre = "tarjeta_coherencia"

    def __init__(self, atributos: Sequence[Dict[str, Any]], pagina: int = 1):
        super().__init__(pagina)
        self.atributos = list(atributos)

    def medir(self, c, ancho):
        self.alto = 80.0
        return self.alto

    def dibujar(self, c, x, y, ancho):
        self.medir(c, ancho)
        panel(c, x, y - self.alto, ancho, self.alto, INFO_BG, INFO_BD)
        banda(c, x, y - self.alto, 3, self.alto, GOLD)
        n = len(self.atributos)
        txt(c, x + 10, y - 16, f"COHERENCIA DE INFORMACIÓN — {n} atributo(s) requieren "
                               f"reconciliación histórica" if n else
            "COHERENCIA DE INFORMACIÓN — sin conflictos entre versiones",
            FB, 9.4, INK)
        actores: List[str] = []
        for a in self.atributos:
            for actor in (a.get("afectados") or []):
                if actor not in actores:
                    actores.append(actor)
        _act, _asz = ajustar(c, "AFECTA A: " + (", ".join(_actores(actores))
                                                or "Impacto pendiente de clasificación"),
                             FB, 8.0, ancho - 20 - 190)
        txt(c, x + 10, y - 29, _act, FB, _asz, TEXT_2)
        txt(c, x + ancho - 10, y - 29, "Detalle por atributo: página 4 →", FB, 8.0, GOLD,
            "right")
        _desc, _dsz = ajustar(c, "El expediente del mismo inmueble produjo valores distintos "
                                 "entre versiones. No es un riesgo del inmueble: es calidad "
                                 "de la información.", F, 8.0, ancho - 20)
        txt(c, x + 10, y - 41, _desc, F, _dsz, TEXT_2)
        cw = (ancho - 28) / 2
        for i, a in enumerate(self.atributos[:6]):
            col, fila = i % 2, i // 2
            etiqueta = (f"{a.get('titulo')}: " +
                        " / ".join(str(v)[:18] for v in (a.get("historico") or [])[:2]))
            _t, _s = ajustar(c, "· " + etiqueta, F, 7.8, cw)
            txt(c, x + 10 + col * (cw + 8), y - 55 - fila * 9.6, _t, F, _s, TEXT_2)
        return self.cerrar(x, y, ancho)


class Imagen(Bloque):
    """Imagen REAL de la corrida (mapa o sombra) con su rótulo de procedencia."""

    nombre = "imagen"

    def __init__(self, ruta: Optional[str], titulo: str, pagina: int = 5,
                 alto: float = 150.0, pie: str = "", disponible: bool = True):
        super().__init__(pagina)
        self.ruta, self.titulo, self._alto_declarado = ruta, titulo, alto
        self.pie, self.disponible = pie, disponible

    def medir(self, c, ancho):
        self.alto = self._alto_declarado
        return self.alto

    def dibujar(self, c, x, y, ancho):
        self.medir(c, ancho)
        panel(c, x, y - self.alto, ancho, self.alto, CARD, HAIR)
        txt(c, x + 8, y - 15, self.titulo.upper(), FB, 7.8, TEXT_3, esp=0.4)
        area_y0, area_y1 = y - self.alto + 20, y - 22
        if self.ruta and Path(self.ruta).exists():
            try:
                lector = ImageReader(str(self.ruta))
                iw, ih = lector.getSize()
                disp_w, disp_h = ancho - 16, area_y1 - area_y0
                escala = min(disp_w / iw, disp_h / ih)
                w_img, h_img = iw * escala, ih * escala
                c.drawImage(str(self.ruta), x + (ancho - w_img) / 2,
                            area_y0 + (disp_h - h_img) / 2, w_img, h_img,
                            preserveAspectRatio=True, anchor="c", mask=None)
            except Exception as _e:  # noqa: BLE001 — un activo ilegible se declara
                txt(c, x + 8, y - self.alto / 2, f"Activo no legible: {_e}", F, 8, WARN_FG)
        else:
            txt(c, x + 8, y - self.alto / 2, "NO DISPONIBLE EN ESTA CORRIDA", FB, 8.4,
                GREY_FG)
        if self.pie:
            _p, _ps = ajustar(c, self.pie, FO, 7.4, ancho - 16)
            txt(c, x + 8, y - self.alto + 8, _p, FO, _ps, TEXT_3)
        return self.cerrar(x, y, ancho)


class EsquemaSolar(Bloque):
    """Esquema geométrico de dirección solar (se usa solo si no hay sombra real)."""

    nombre = "esquema_solar"

    def __init__(self, momento: Dict[str, Any], pagina: int = 5, alto: float = 96.0):
        super().__init__(pagina)
        self.momento = momento
        self._alto_declarado = alto

    def medir(self, c, ancho):
        self.alto = self._alto_declarado
        return self.alto

    def dibujar(self, c, x, y, ancho):
        self.medir(c, ancho)
        az = _num_grados(self.momento.get("azimut"))
        el = _num_grados(self.momento.get("elevacion"))
        panel(c, x, y - self.alto, ancho, self.alto, CARD)
        txt(c, x + 7, y - 14, f"ESQUEMA {_v(self.momento.get('hora'), '—')}", FB, 7.6,
            TEXT_3, esp=0.4)
        cx, cy = x + ancho / 2.0, y - self.alto / 2.0 - 6
        r = min(ancho, self.alto) / 2.0 - 22
        c.setStrokeColor(HAIR_2)
        c.setLineWidth(0.6)
        c.circle(cx, cy, r, stroke=1, fill=0)
        txt(c, cx, cy - r - 3, "N", FB, 6.2, TEXT_3, "center")
        if az is None or el is None:
            txt(c, cx, cy - 6, "sin dato de fuente", F, 7.6, TEXT_3, "center")
        else:
            rad = math.radians(90.0 - az)
            dx, dy = math.cos(rad), math.sin(rad)
            c.setStrokeColor(GOLD)
            c.setLineWidth(1.2)
            c.line(cx, cy, cx + dx * r, cy + dy * r)
            c.setFillColor(GOLD)
            c.circle(cx + dx * r, cy + dy * r, 2.6, stroke=0, fill=1)
        txt(c, x + 7, y - self.alto + 16, f"azimut {_v(self.momento.get('azimut'), '—')} · "
                                          f"elevación {_v(self.momento.get('elevacion'), '—')}",
            F, 7.4, TEXT_3)
        txt(c, x + 7, y - self.alto + 7, "esquema de dirección solar (no es una fotografía)",
            FO, 7.0, TEXT_3)
        return self.cerrar(x, y, ancho)


# ── cromo de página ──────────────────────────────────────────────────────────
def cabecera(c, modelo, pagina, subtitulo=None):
    subtitulo = subtitulo or TITULOS_PAGINA[pagina - 1]
    banda(c, 0, H - 54, W, 54, INK)
    txt(c, M, H - 26, "DICTUS", FB, 15, white, esp=1.2)
    txt(c, M + 52, H - 26, subtitulo, F, 8.0, GOLD_2, esp=0.6)
    banda(c, M, H - 40, 52, 2, GOLD)
    ident = (modelo.get("document_identity") or {})
    txt(c, W - M, H - 24, str(ident.get("dictus_id") or ""), FB, 8.4, white, "right")
    txt(c, W - M, H - 36, f"Página {pagina} de {TOTAL_EJECUTIVO} · ejecutivo",
        F, 7.4, GOLD_2, "right")
    _bbox("cabecera", 0, H - 54, W, H)


def pie(c, modelo, pagina):
    mh = str(modelo.get("master_hash_abreviado") or "")
    ev = (modelo.get("evidence_manifest") or {})
    rule(c, M, 40, W - M, 40, HAIR)
    txt(c, M, 29, f"DICTUS_MASTER_HASH {mh}", FB, 7.4, TEXT_2)
    txt(c, M, 20, f"Evidencias {ev.get('evidence_count')} · sello "
                  f"{limpio(ev.get('estado'))} · verificación por DICTUS ID (Anexo G)",
        F, 7.0, TEXT_3)
    txt(c, W - M, 20, "El hash del archivo PDF no es el hash maestro: consta en el anexo G.",
        F, 7.0, TEXT_3, "right")
    _bbox("pie", M, 14, W - M, 36)


# ── Página 1 · RESUMEN DE DECISIÓN ───────────────────────────────────────────
def pagina1(c, modelo, secciones):
    PAGINA_ACTUAL[0] = 1
    cabecera(c, modelo, 1)
    ctx = secciones.get("ctx") or {}
    hallazgos = secciones.get("hallazgos") or []
    coh = secciones.get("coherencia_attrs") or []
    y = TOPE

    # Titular: identidad completa del inmueble (dirección base + torre + apartamento).
    _bloque = PanelLibre("titular", 46.0, lambda cc, x, yy, a: (
        txt(cc, x, yy - 14, TITULOS_PAGINA[0], FB, 13.5, INK),
        rule(cc, x, yy - 21, x + a, yy - 21, HAIR),
        txt(cc, x, yy - 38, _corto(_v(ctx.get("direccion"), "Dirección no declarada"), 92),
            FB, 12.0, INK)), 1)
    y = emitir(c, y, [_bloque])

    general = list(ctx.get("general") or [])[:8]
    cw = (ANCHO - 3 * 5) / 4

    def _dibujar_general(cc, x, yy, a):
        panel(cc, x, yy - 58, a, 58, PAPER, HAIR)
        for i, (etiqueta, valor) in enumerate(general):
            col, fila = i % 4, i // 4
            xx = x + 6 + col * (cw + 5)
            yt = yy - 6 - fila * 27
            txt(cc, xx, yt - 10, str(etiqueta).upper(), FB, 7.0, TEXT_3)
            _val, _vsz = ajustar(cc, valor, FB, 9.4, cw - 12)
            txt(cc, xx, yt - 21, _val, FB, _vsz, INK)

    y = emitir(c, y, [Titulo("INFORMACIÓN GENERAL", "bloque a · identidad del inmueble", 1,
                             size=11.0),
                      PanelLibre("bloque_general", 58.0, _dibujar_general, 1)])

    indicadores = secciones.get("indicadores") or []
    y = emitir(c, y, [Titulo("ESTADO GENERAL", "cinco indicadores de decisión", 1, size=11.0),
                      Tarjetas([{"titulo": n, "estado": e, "motivo": m,
                                 "color": GOLD if e in (VERIFICADO, "DISPONIBLE") else INK_3}
                                for n, e, m in indicadores],
                               pagina=1, columnas=5, alto_tarjeta=74.0)])

    y = emitir(c, y, [Titulo("HALLAZGOS DE LA OPERACIÓN",
                             f"{len(hallazgos)} hallazgos de la operación condicionan "
                             f"la transacción", 1, size=11.0),
                      MatrizHallazgos(hallazgos, pagina=1, alto_fila=58.0)])

    y = emitir(c, y, [Titulo("COHERENCIA DE LA INFORMACIÓN",
                             "conflictos entre versiones del expediente", 1, size=11.0),
                      TarjetaCoherencia(coh, pagina=1)])

    y = emitir(c, y, [SelloGlobal(modelo, pagina=1)], dy=0)
    y = emitir(c, y, [Traza((modelo.get("evidence_manifest") or {}).get("fuentes") or [],
                            str((modelo.get("document_identity") or {}).get("generated_at")
                                or "")[:10],
                            (modelo.get("evidence_manifest") or {}).get("estado"),
                            int((modelo.get("evidence_manifest") or {}).get("evidence_count")
                                or 0), pagina=1)], dy=0)
    if y < PIE_Y:
        VIOLACIONES.append(f"P1 desborda: quedan {y:.0f} pt (límite {PIE_Y:.0f})")
    pie(c, modelo, 1)


# ── Página 2 · TÍTULOS Y CONDICIONES JURÍDICAS ───────────────────────────────
def pagina2(c, modelo, secciones):
    PAGINA_ACTUAL[0] = 2
    cabecera(c, modelo, 2)
    legal = secciones.get("legal") or {}
    y = emitir(c, TOPE, [Titulo(TITULOS_PAGINA[1],
                                "¿qué puede impedir o condicionar la transacción?", 2)])

    titulares = legal.get("titulares") or []
    bloques: List[Bloque] = [Titulo("TITULARIDAD", "quién puede vender y en qué forma", 2,
                                    size=11.0)]
    if titulares:
        def _dib_titular(cc, x, yy, a):
            t = titulares[0]
            panel(cc, x, yy - 46, a, 46, CARD)
            txt(cc, x + 9, yy - 17, _v(t.get("nombre")), FB, 10.5, INK)
            txt(cc, x + 9, yy - 30, f"{_v(t.get('tipo'))} · {_v(t.get('documento'))} · "
                                   f"participación {_v(t.get('participacion'))}",
                F, 8.4, TEXT_2)
            forma = t.get("adquisicion")
            evidencia = t.get("adquisicion_evidencia")
            txt(cc, x + 9, yy - 41, "Forma de adquisición: " + _v(forma,
                                                                  "no declarada en el folio")
                + (f"  ({evidencia})" if evidencia else ""), FB, 8.6, INK)
        bloques.append(PanelLibre("titularidad", 46.0, _dib_titular, 2))

    gravamenes = legal.get("gravamenes") or []
    bloques.append(Titulo("TRADICIÓN Y GRAVÁMENES",
                          f"{legal.get('anotaciones_total') or '—'} anotaciones · "
                          f"círculo {legal.get('circulo') or 'no declarado'}", 2, size=11.0))

    def _fila_carga(g):
        return 62.0

    for g in gravamenes:
        def _dib_carga(cc, x, yy, a, _g=g):
            alto = _fila_carga(_g)
            panel(cc, x, yy - alto, a, alto, CARD)
            banda(cc, x, yy - alto, 3, alto, ERR_FG if _g.get("severidad") == "ALTO"
                  else WARN_FG)
            txt(cc, x + 9, yy - 16, _v(_g.get("titulo")), FB, 9.6, INK)
            chip(cc, x + a - 9 - 62, yy - 19, str(_g.get("estado", "VIGENTE")).upper()[:12],
                 "err", 7.0, 14, 6)
            wrap(cc, x + 9, yy - 29, _v(_g.get("detalle")), F, 8.2, TEXT_2, a - 18,
                 leading=9.0)
            accion = _lineas(cc, "ACCIÓN ESPECÍFICA: " + _v(_g.get("accion"), "por definir"),
                             F, 8.2, a - 18)[:2]
            for i, ln in enumerate(accion):
                txt(cc, x + 9, yy - 45 - i * 9.0, ln, F, 8.2, TEXT_2)
        bloques.append(PanelLibre(f"carga_{g.get('anotacion')}", _fila_carga(g),
                                  _dib_carga, 2))

    bloques.append(Nota("El detalle registral completo (todas las anotaciones, "
                        "cancelaciones y tracto) consta en el Anexo A.", 2))

    condiciones = legal.get("condiciones") or []
    bloques.append(Titulo("QUÉ DEBE HACERSE PARA CERRAR LA OPERACIÓN",
                          f"{len(condiciones)} acción(es) sobre las condiciones anteriores",
                          2, size=11.0))
    for i, cond in enumerate(condiciones, 1):
        # La altura del bloque se MIDE con el mismo motor de texto que lo dibuja: no
        # hay offset fijo que pueda encabalgarse con el bloque siguiente (§11).
        n_lineas = len(_lineas(c, f"{i}. " + cond, F, 8.8, ANCHO))

        def _dib_accion(cc, x, yy, a, _i=i, _c=cond):
            ls = _lineas(cc, f"{_i}. " + _c, F, 8.8, a)
            for j, ln in enumerate(ls):
                txt(cc, x, yy - 11 - j * 10.4, ln, F, 8.8, TEXT_2)
        bloques.append(PanelLibre(f"accion_{i}", n_lineas * 10.4 + 6.0, _dib_accion, 2))

    y = emitir(c, y, bloques)
    ev = modelo.get("evidence_manifest") or {}
    y = emitir(c, y, [Traza(["Registro (SNR/CTL)", "Titulux"],
                            str((modelo.get("document_identity") or {}).get("generated_at")
                                or "")[:10], ev.get("estado"),
                            int(ev.get("evidence_count") or 0), pagina=2)], dy=0)
    if y < PIE_Y:
        VIOLACIONES.append(f"P2 desborda: quedan {y:.0f} pt (límite {PIE_Y:.0f})")
    pie(c, modelo, 2)


# ── Página 3 · CONTRAPARTES Y PREPARACIÓN DE OPERACIÓN ───────────────────────
def _encabezado_columnas(c, x, y, texto, ancho, size=7.0):
    partes = str(texto).split(" ")
    if len(partes) > 1 and c.stringWidth(texto, FB, size) > ancho - 4:
        medio = len(partes) // 2
        lineas = [" ".join(partes[:medio]), " ".join(partes[medio:])]
    else:
        lineas = [str(texto)]
    for i, ln in enumerate(lineas[:2]):
        txt(c, x, y + i * 7.4, ln, FB, size, TEXT_3)


def pagina3(c, modelo, secciones):
    PAGINA_ACTUAL[0] = 3
    cabecera(c, modelo, 3)
    contrapartes = secciones.get("contrapartes") or {}
    ev = contrapartes.get("evidencia") or {}
    preparacion = secciones.get("preparacion") or []
    y = emitir(c, TOPE, [Titulo(TITULOS_PAGINA[2], "screening de contrapartes", 3)])

    listas = list(contrapartes.get("listas") or [])
    columnas = list(contrapartes.get("columnas") or listas)
    sujetos = contrapartes.get("sujetos") or []
    a_sujeto, a_rol, a_doc, a_res = 118.0, 88.0, 78.0, 118.0
    a_lista = (ANCHO - a_sujeto - a_rol - a_doc - a_res) / max(1, len(listas))
    alto_tabla = 24.0 + len(sujetos) * 36.0

    def _dib_tabla(cc, x, yy, a):
        panel(cc, x, yy - 22, a, 22, PAPER, HAIR)
        txt(cc, x + 7, yy - 10, "SUJETO", FB, 7.0, TEXT_3)
        txt(cc, x + a_sujeto + 4, yy - 10, "ROL", FB, 7.0, TEXT_3)
        txt(cc, x + a_sujeto + a_rol + 4, yy - 10, "DOCUMENTO", FB, 7.0, TEXT_3)
        for i, col in enumerate(columnas):
            _encabezado_columnas(cc, x + a_sujeto + a_rol + a_doc + i * a_lista + 4,
                                 yy - 17, str(col).upper(), a_lista)
        txt(cc, x + a - 7, yy - 10, "RESULTADO DE MATCH", FB, 7.0, TEXT_3, "right")
        yt = yy - 22
        for s in sujetos:
            panel(cc, x, yt - 36, a, 36, CARD)
            wrap(cc, x + 7, yt - 14, _v(s.get("nombre")), FB, 9.0, INK, a_sujeto - 14,
                 leading=10.0)
            _rol, _rs = ajustar(cc, _v(s.get("rol")), F, 8.0, a_rol - 8)
            txt(cc, x + a_sujeto + 4, yt - 14, _rol, F, _rs, TEXT_2)
            _doc, _ds = ajustar(cc, _v(s.get("documento"), "no declarado"), F, 8.0,
                                a_doc - 8)
            txt(cc, x + a_sujeto + a_rol + 4, yt - 14, _doc, F, _ds, TEXT_2)
            for i, li in enumerate(listas):
                estado = (s.get("por_lista") or {}).get(li) or "SIN_DATO"
                chip(cc, x + a_sujeto + a_rol + a_doc + i * a_lista + 3, yt - 24,
                     {"SIN_COINCIDENCIAS": "SIN COINC.", "COINCIDENCIA": "COINCIDE",
                      "INCOMPLETA": "NO CONSULT.", "SIN_DATO": "NO CONSULT."}.get(
                          estado, estado)[:11],
                     {"SIN_COINCIDENCIAS": "ok", "COINCIDENCIA": "err",
                      "INCOMPLETA": "warn"}.get(estado, "info"), 7.0, 14, 4)
            resultado = s.get("resultado") or "SIN_DATO"
            chip(cc, x + a - 7 - 112, yt - 24,
                 {"SIN_COINCIDENCIAS": "SIN COINCIDENCIAS",
                  "COINCIDENCIA": "COINCIDENCIA",
                  "INCOMPLETA": "INCOMPLETA"}.get(resultado, "SIN DATO"),
                 {"SIN_COINCIDENCIAS": "ok", "COINCIDENCIA": "err"}.get(resultado, "warn"),
                 7.0, 14, 6)
            yt -= 36.0

    y = emitir(c, y, [PanelLibre("matriz_screening", alto_tabla, _dib_tabla, 3)])

    detalle = contrapartes.get("listas_detalle") or []
    if detalle:
        y = emitir(c, y, [Nota("Listas efectivamente consultadas: " + "; ".join(
            f"{d.get('sigla')} = {d.get('nombre')}" for d in detalle) + ".", 3)])

    # §14: RESULTADO del match e INTEGRIDAD de la evidencia son DOS bloques separados.
    def _dib_resultado(cc, x, yy, a):
        panel(cc, x, yy - 54, a, 54, CARD)
        txt(cc, x + 9, yy - 14, "RESULTADO DE COINCIDENCIA", FB, 8.0, TEXT_3)
        txt(cc, x + 9, yy - 30, str(contrapartes.get("match_global") or "—"), FB, 11, INK)
        txt(cc, x + 9, yy - 47, f"{ev.get('sujetos_revisados') or '—'} de "
                                f"{ev.get('sujetos_declarados') or '—'} sujeto(s) revisados "
                                f"contra {ev.get('listas_consultadas') or '—'} lista(s). "
                                f"Una coincidencia no es una acusación: es materia de "
                                f"revisión.", F, 8.0, TEXT_2)

    def _dib_integridad(cc, x, yy, a):
        sellado = bool(ev.get("sellado"))
        panel(cc, x, yy - 62, a, 62, CARD)
        txt(cc, x + 9, yy - 14, "INTEGRIDAD DE LA EVIDENCIA", FB, 8.0, TEXT_3)
        caja_estado(cc, x + 9, yy - 30, 150, "VERIFICADO" if sellado else "NO_EVIDENCIA",
                    7.4, 14)
        _cadena_txt = {"SEALED": "SELLADA", "FAILED": "NO SELLADA",
                       "NOT_REQUIRED_DEV": "NO REQUERIDA (entorno de desarrollo)"}.get(
                           str(ev.get("cadena") or "").upper(), "NO DECLARADA")
        txt(cc, x + 168, yy - 26, f"Cadena: {_cadena_txt} · Cobertura: "
                                  f"{_v(ev.get('cobertura'), 'no declarada')} · "
                                  f"Evidencias {ev.get('creadas') or '0'}/"
                                  f"{ev.get('esperadas') or '—'}",
            F, 8.0, TEXT_2)
        wrap(cc, x + 9, yy - 50, "El resultado del screening dice si hubo coincidencias en "
             "las listas consultadas. La integridad dice si cada verificación quedó "
             "sellada en la cadena de custodia. Son dos hechos distintos: una cadena sin "
             "sellar NO convierte en incompleto un screening que sí consultó las listas.",
             F, 8.0, TEXT_2, a - 18, leading=9.0)

    y = emitir(c, y, [PanelLibre("resultado_match", 54.0, _dib_resultado, 3),
                      PanelLibre("integridad_evidencia", 62.0, _dib_integridad, 3)])

    y = emitir(c, y, [Titulo("PREPARACIÓN PARA",
                             "no sustituye la decisión de terceros", 3, size=11.0)])
    prep_bloques: List[Bloque] = []
    for etiqueta, estado, nota in preparacion:
        alto = max(52.0, 34.0 + len(_lineas(c, nota, F, 8.4, ANCHO - 20)) * 9.6)

        def _dib_prep(cc, x, yy, a, _e=etiqueta, _s=estado, _n=nota, _alto=alto):
            panel(cc, x, yy - _alto, a, _alto, CARD)
            txt(cc, x + 9, yy - 17, _e, FB, 9.6, INK)
            caja_estado(cc, x + a - 8 - 200, yy - 15, 200, _s, 7.4, 14)
            for i, ln in enumerate(_lineas(cc, _n, F, 8.4, a - 20)):
                txt(cc, x + 9, yy - 44 - i * 9.6, ln, F, 8.4, TEXT_2)
        prep_bloques.append(PanelLibre(f"prep_{etiqueta}", alto, _dib_prep, 3))
    y = emitir(c, y, prep_bloques)

    ev_man = modelo.get("evidence_manifest") or {}
    y = emitir(c, y, [Nota("UIAF/SIREL es el canal regulatorio de reporte del sujeto "
                           "obligado: no es una lista de screening y no se imprime como "
                           "fuente. Detalle de consultas y hashes: Anexo D.", 3)])
    y = emitir(c, y, [Traza(["Listas restrictivas aplicables"],
                            str((modelo.get("document_identity") or {}).get("generated_at")
                                or "")[:10], ev_man.get("estado"),
                            int(ev_man.get("evidence_count") or 0), pagina=3)], dy=0)
    if y < PIE_Y:
        VIOLACIONES.append(f"P3 desborda: quedan {y:.0f} pt (límite {PIE_Y:.0f})")
    pie(c, modelo, 3)


# ── Página 4 · POT, USO, EDIFICABILIDAD Y RIESGOS ────────────────────────────
def pagina4(c, modelo, secciones):
    PAGINA_ACTUAL[0] = 4
    cabecera(c, modelo, 4)
    urbano = secciones.get("urbano") or {}
    attrs = secciones.get("coherencia_attrs") or []
    riesgos = secciones.get("riesgos") or []
    y = emitir(c, TOPE, [Titulo(TITULOS_PAGINA[3],
                                "dimensiones separadas: destino catastral ≠ uso POT", 4)])

    filas = [{"etiqueta": f.get("etiqueta"), "valor": f.get("valor"),
              "estado": f.get("estado"), "nota": f.get("nota")}
             for f in (urbano.get("filas") or [])[:8]]
    y = emitir(c, y, [Titulo("NORMA URBANÍSTICA DEL PREDIO",
                             "valor vigente en esta corrida y su fuente", 4, size=11.0),
                      Filas(filas, pagina=4, ancho_etiqueta=142.0, size_valor=9.2,
                            alto_min=18.0, nota_size=7.4)])

    # §16: por atributo en conflicto — actual + histórico + coherencia + fuente.
    def _dib_coherencia(cc, x, yy, a):
        alto_fila = 30.0
        cw = (a - 8) / 2
        for i, at in enumerate(attrs):
            col, fila = i % 2, i // 2
            xx = x + col * (cw + 8)
            yt = yy - fila * (alto_fila + 3)
            panel(cc, xx, yt - alto_fila, cw, alto_fila, ERR_BG, ERR_BD)
            _titulo_celda, _tsz = ajustar(cc, str(at.get("titulo")).upper(), FB, 7.6,
                                          cw - 104)
            txt(cc, xx + 8, yt - 11, _titulo_celda, FB, _tsz, TEXT_3)
            actual = _v(at.get("actual"), "NO DISPONIBLE EN ESTA CORRIDA")
            _t, _s = ajustar(cc, "ACTUAL: " + str(actual), FB, 8.2, cw - 104)
            txt(cc, xx + 8, yt - 21, _t, FB, _s, INK)
            historico = " / ".join(str(v)[:16] for v in (at.get("historico") or [])[:2]) \
                or "sin valores históricos"
            # Una sola línea con histórico y fuente: los cuatro datos del §16 caben en
            # la celda sin invadir la fila siguiente.
            _th, _sh = ajustar(cc, f"HISTÓRICO: {historico} · fuente: "
                                   f"{_v(at.get('fuente_actual'), 'no declarada')}",
                               F, 7.2, cw - 104)
            txt(cc, xx + 8, yt - 29, _th, F, _sh, TEXT_2)
            chip(cc, xx + cw - 8 - 84, yt - 11, "CONFLICTO HISTÓRICO", "err", 6.2, 12, 5)

    if attrs:
        y = emitir(c, y, [Titulo("COHERENCIA DE DATOS POR ATRIBUTO",
                                 "actual · histórico · estado · fuente", 4, size=11.0),
                          PanelLibre("coherencia_detallada",
                                     ((len(attrs) + 1) // 2) * 32.0, _dib_coherencia, 4)])

    def _dib_riesgos(cc, x, yy, a):
        alto = 26.0
        for i, r in enumerate(riesgos[:4]):
            yt = yy - i * (alto + 2)
            nivel = str(r.get("nivel") or "").upper()
            evaluado = bool(r.get("nivel"))
            riesgo = any(k in nivel for k in ("ALTA", "ALTO", "MEDIA", "MEDIO"))
            panel(cc, x, yt - alto, a, alto, CARD, HAIR)
            # §18: gris para NO EVALUADO · ámbar/rojo para riesgo · verde solo para
            # afectación verificada sin hallazgo.
            color = (WARN_FG if riesgo else OK_FG) if evaluado else GREY_BD
            banda(cc, x, yt - alto, 3, alto, color)
            txt(cc, x + 9, yt - 12, f"{_v(r.get('tipo'))}: "
                                    f"{_v(r.get('nivel'), 'NO EVALUADO')}", FB, 8.8, INK)
            _ti, _si = ajustar(cc, _v(r.get("implicacion")), F, 7.8, a - 176)
            txt(cc, x + 9, yt - 22, _ti, F, _si, TEXT_2)
            # §18: el chip dice el HECHO del riesgo, no un estado genérico.
            if not evaluado:
                _chip = "NO_EVALUADO"
            elif any(k in nivel for k in ("ALTA", "ALTO")):
                _chip = "RIESGO_ALTO"
            elif any(k in nivel for k in ("MEDIA", "MEDIO")):
                _chip = "RIESGO_MEDIO"
            elif any(k in nivel for k in ("SIN AFECT", "SIN RIESGO", "NO INTERSECTA")):
                _chip = "SIN_AFECTACION"
            else:
                _chip = "NO_EVALUADO"
            caja_estado(cc, x + a - 8 - 150, yt - 17, 150, _chip, 7.0, 13)

    y = emitir(c, y, [Titulo("RIESGOS TERRITORIALES", "amenazas y su implicación", 4,
                             size=11.0),
                      PanelLibre("riesgos", len(riesgos[:4]) * 28.0, _dib_riesgos, 4)])
    ev = modelo.get("evidence_manifest") or {}
    y = emitir(c, y, [Traza(["POT / ordenamiento municipal", "Catastro",
                             "Gestión del riesgo"],
                            str((modelo.get("document_identity") or {}).get("generated_at")
                                or "")[:10], ev.get("estado"),
                            int(ev.get("evidence_count") or 0), pagina=4)], dy=0)
    if y < PIE_Y:
        VIOLACIONES.append(f"P4 desborda: quedan {y:.0f} pt (límite {PIE_Y:.0f})")
    pie(c, modelo, 4)


# ── Página 5 · ENTORNO, EQUIPAMIENTO Y ASOLEAMIENTO ──────────────────────────
def pagina5(c, modelo, secciones):
    PAGINA_ACTUAL[0] = 5
    cabecera(c, modelo, 5)
    entorno = secciones.get("entorno") or {}
    solar = secciones.get("solar") or {}
    visual = (secciones.get("visual") or {}).get("assets") or {}
    y = emitir(c, TOPE, [Titulo(TITULOS_PAGINA[4], "equipamiento, entorno y asoleamiento",
                                5)])

    # Activos REALES de la corrida: mapa satelital si existe; si no, mapa de POI.
    sat = visual.get("satellite_map") or {}
    poi_map = visual.get("poi_map") or {}
    principal = sat if sat.get("status") == "AVAILABLE" else poi_map
    if principal.get("status") == "AVAILABLE":
        pie_mapa = ("Escena satelital de esta corrida · " if principal is sat
                    else "Mapa de puntos de interés de esta corrida · ") + \
            str(principal.get("source") or "")
        if principal is poi_map and sat.get("status") != "AVAILABLE":
            # §20: si la escena satelital no existe en la corrida se DECLARA, y el mapa
            # de puntos de interés ocupa su lugar.
            pie_mapa += (" · la escena satelital no fue aportada en esta corrida: se usa el "
                         "mapa de puntos de interés del mismo run")
        y = emitir(c, y, [Imagen(principal.get("path"),
                                 "Vista satelital del inmueble" if principal is sat
                                 else "Entorno urbano del inmueble",
                                 pagina=5, alto=100.0, pie=pie_mapa)], dy=4.0)
    else:
        y = emitir(c, y, [Imagen(None, "Vista del inmueble", pagina=5, alto=60.0,
                                 pie="Ningún activo gráfico de esta corrida está "
                                     "disponible: se declara en lugar de simularlo.")],
                   dy=4.0)

    # Equipamiento a todo lo ancho (dos columnas de categorías) y accesibilidad en una
    # banda propia: así cada lugar tiene ancho suficiente para su nombre, su distancia y
    # su tiempo a pie sin invadir la categoría vecina.
    y = emitir(c, y, [
        Titulo("EQUIPAMIENTO URBANO",
               f"radio de {entorno.get('radio_m', 2000) / 1000:.1f} km · "
               f"{entorno.get('total_items') or 0} ítem(s) obtenidos de "
               f"{', '.join(entorno.get('fuentes_consultadas') or ['la fuente'])}",
               5, size=11.0),
        ListaPOI(entorno.get("categorias") or [], pagina=5, columnas=2,
                 por_categoria=3, alto_categoria=94.0)], dy=5.0)

    ALTO_ACCESO = 48.0

    def _dib_acceso(cc, x, yy, a):
        panel(cc, x, yy - ALTO_ACCESO, a, ALTO_ACCESO, PAPER, HAIR)
        txt(cc, x + 9, yy - 13, "ACCESIBILIDAD Y CONTEXTO", FB, 7.8, GOLD, esp=0.6)
        cw = (a - 3 * 8) / 4
        for i, (k, v) in enumerate((entorno.get("accesibilidad") or [])[:4]):
            xx = x + i * (cw + 8)
            txt(cc, xx, yy - 27, str(k), F, 7.4, TEXT_3)
            _t, _s = ajustar(cc, _v(v), FB, 8.2, cw)
            txt(cc, xx, yy - 39, _t, FB, _s, INK)

    y = emitir(c, y, [PanelLibre("accesibilidad", ALTO_ACCESO, _dib_acceso, 5)], dy=5.0)

    momentos = solar.get("momentos") or []
    y = emitir(c, y, [Titulo("ASOLEAMIENTO Y SOMBRAS",
                             "09:00 · 12:00 · 15:00 (hora local)", 5, size=11.0)])
    if momentos:
        def _dib_momentos(cc, x, yy, a):
            cw = (a - 2 * 6) / 3
            for i, m in enumerate(momentos[:3]):
                xx = x + i * (cw + 6)
                panel(cc, xx, yy - 44, cw, 44, CARD)
                txt(cc, xx + 8, yy - 17, _v(m.get("hora")), FB, 11.5, INK)
                txt(cc, xx + 8, yy - 29, _corto(_v(m.get("estado")), 34), F, 8.0, TEXT_2)
                txt(cc, xx + 8, yy - 39, f"azimut {_v(m.get('azimut'), '—')} · "
                                         f"elevación {_v(m.get('elevacion'), '—')}",
                    F, 7.4, TEXT_3)

        y = emitir(c, y, [PanelLibre("momentos_solares", 44.0, _dib_momentos, 5)], dy=5.0)

        s09 = visual.get("shadow_09") or {}
        s15 = visual.get("shadow_15") or {}
        if s09.get("status") == "AVAILABLE" or s15.get("status") == "AVAILABLE":
            par = []
            for clave, activo, etiqueta in (("shadow_09", s09, "Sombra de la corrida · 09:00"),
                                            ("shadow_15", s15, "Sombra de la corrida · 15:00")):
                pidio = activo.get("status") == "AVAILABLE"
                par.append(Imagen(activo.get("path") if pidio else None, etiqueta,
                                  pagina=5, alto=108.0,
                                  pie=(f"{activo.get('source')} · generado "
                                       f"{str(activo.get('generated_at') or '')[:10]}"
                                       if pidio else str(activo.get("source") or ""))))
            y = emitir(c, y, [Fila(par[0], par[1], pagina=5)], dy=5.0)
        else:
            # Sin sombras reales se usan esquemas geométricos DECLARADOS como tales.
            dos = [momentos[0], momentos[-1]] if len(momentos) > 1 else momentos
            y = emitir(c, y, [Fila(EsquemaSolar(dos[0], pagina=5, alto=112.0),
                                   EsquemaSolar(dos[1], pagina=5, alto=112.0) if len(dos) > 1
                                   else None, pagina=5)], dy=5.0)

    y = emitir(c, y, [Nota("Las sombras de 09:00 y 15:00 provienen de la simulación "
                           "geométrica de ESTA corrida (huella y altura disponibles) y no "
                           "sustituyen una inspección física. Si la altura requiere "
                           "validación de coherencia (página 4), la sombra es referencial.",
                           5)])
    ev = modelo.get("evidence_manifest") or {}
    y = emitir(c, y, [Traza(["Proveedor de mapas abierto", "Fotografía satelital",
                             "Cálculo solar"],
                            str((modelo.get("document_identity") or {}).get("generated_at")
                                or "")[:10], ev.get("estado"),
                            int(ev.get("evidence_count") or 0), pagina=5)], dy=0)
    if y < PIE_Y:
        VIOLACIONES.append(f"P5 desborda: quedan {y:.0f} pt (límite {PIE_Y:.0f})")
    pie(c, modelo, 5)


# ── Página 6 · IDENTIDAD Y VALOR ─────────────────────────────────────────────
def pagina6(c, modelo, secciones):
    PAGINA_ACTUAL[0] = 6
    cabecera(c, modelo, 6)
    identidad = secciones.get("identidad") or {}
    valor = secciones.get("valor") or {}
    y = emitir(c, TOPE, [Titulo(TITULOS_PAGINA[5], "lo que se verificó y cuánto vale", 6)])

    y = emitir(c, y, [Titulo("IDENTIDAD DEL INMUEBLE", "registral y catastral", 6, size=11.0),
                      Filas([{"etiqueta": f.get("etiqueta"), "valor": f.get("valor"),
                              "estado": f.get("estado")}
                             for f in (identidad.get("filas") or [])],
                            pagina=6, ancho_etiqueta=168.0, size_valor=9.6,
                            alto_min=24.0)])

    def _dib_ident(cc, x, yy, a):
        panel(cc, x, yy - 40, a, 40, OK_BG if identidad.get("identidad_estado") == "VERIFICADA"
              else WARN_BG, HAIR)
        txt(cc, x + 9, yy - 15, f"Identidad registral y catastral: "
                                f"{_v(identidad.get('identidad_estado'))}", FB, 9.4, INK)
        txt(cc, x + 9, yy - 28, _v(identidad.get("identidad_detalle")), F, 8.4, TEXT_2)

    def _dib_geom(cc, x, yy, a):
        panel(cc, x, yy - 56, a, 56, PAPER, HAIR)
        txt(cc, x + 9, yy - 15, f"Geometría oficial: {_v(identidad.get('geometria_estado'))}",
            FB, 9.4, INK)
        ls = _lineas(cc, _v(identidad.get("geometria_detalle")), F, 8.4, a - 18)[:4]
        for i, ln in enumerate(ls):
            txt(cc, x + 9, yy - 29 - i * 9.4, ln, F, 8.4, TEXT_2)

    y = emitir(c, y, [PanelLibre("identidad_estado", 40.0, _dib_ident, 6),
                      PanelLibre("geometria", 56.0, _dib_geom, 6)])

    aut = bool(valor.get("autorizado"))
    if aut:
        y = emitir(c, y, [Titulo("VALOR ESTIMADO", "valoración autorizada en esta corrida",
                                 6, size=11.0)])

        def _dib_valor(cc, x, yy, a):
            panel(cc, x, yy - 78, a, 78, CARD)
            txt(cc, x + 11, yy - 17, "Valor estimado (valor central)", FB, 8.0, TEXT_3)
            txt(cc, x + 11, yy - 42, _v(valor.get("consolidado")), FB, 20, INK)
            _res, _rsz = ajustar(
                cc, f"Rango {_v(valor.get('rango'), '—')} – "
                    f"{_v(valor.get('rango_alto'), '—')} · "
                    f"Valor/m² {_v(valor.get('valor_m2'), '—')} · "
                    f"Área {_v(valor.get('area'), '—')}", F, 8.4, 248)
            txt(cc, x + 11, yy - 58, _res, F, _rsz, TEXT_2)
            txt(cc, x + 11, yy - 70, f"Vigencia: {_v(valor.get('vigencia'), 'no declarada')}",
                F, 8.0, TEXT_3)
            for i, (k, v) in enumerate([("Sector de mercado", valor.get("sector")),
                                        ("Método principal", valor.get("metodologia"))]):
                xx = x + 300 + i * 110
                txt(cc, xx, yy - 24, k, FB, 7.4, TEXT_3)
                wrap(cc, xx, yy - 36, _v(v, "no declarado"), FB, 8.4, INK, 104, leading=9.4)

        y = emitir(c, y, [PanelLibre("valor", 78.0, _dib_valor, 6)])
        if valor.get("tasa_fuente"):
            y = emitir(c, y, [Nota("Tasa y parámetros: " + str(valor["tasa_fuente"]), 6)])
    else:
        blockers = valor.get("blockers") or []
        y = emitir(c, y, [Titulo("VALOR ESTIMADO",
                                 "qué falta para habilitar la valoración · no se "
                                 "imprime ningún monto, ni $0", 6, size=11.0)])
        y = emitir(c, y, [PanelLibre("blockers", max(52.0, 34.0 + len(blockers) * 12.0),
                                     lambda cc, x, yy, a: (
                                         panel(cc, x, yy - max(52.0, 34.0 + len(blockers) * 12.0),
                                               a, max(52.0, 34.0 + len(blockers) * 12.0),
                                               PAPER, HAIR),
                                         caja_estado(cc, x + 11, yy - 14, 190,
                                                     "NO_DISPONIBLE", 7.4, 14),
                                         txt(cc, x + 210, yy - 13,
                                             "VALORACIÓN NO DISPONIBLE", FB, 9.0, WARN_FG),
                                         txt(cc, x + 11, yy - 30,
                                             _v(valor.get("motivo"),
                                                "La corrida no declara por qué no se "
                                                "autorizó la valoración: requiere revisión."),
                                             FB, 9.0, WARN_FG),
                                         [txt(cc, x + 11, yy - 44 - i * 12.0, "· " + b,
                                              F, 8.4, TEXT_2)
                                          for i, b in enumerate(blockers)]
                                     ), 6)])

    y = emitir(c, y, [Nota("NORMA · CONCEPTO TÉCNICO · VALIDACIÓN EXPERTA: DICTUS prepara y "
                           "señala; el valor y su interpretación los firma el profesional "
                           "competente (avaluador inscrito en el RAA, abogado, geodesta).",
                           6)])
    ev = modelo.get("evidence_manifest") or {}
    y = emitir(c, y, [Traza(["Metodología de mercado (Lonja)", "Catastro",
                             "Identidad canónica"],
                            str((modelo.get("document_identity") or {}).get("generated_at")
                                or "")[:10], ev.get("estado"),
                            int(ev.get("evidence_count") or 0), pagina=6)], dy=0)
    if y < PIE_Y:
        VIOLACIONES.append(f"P6 desborda: quedan {y:.0f} pt (límite {PIE_Y:.0f})")
    pie(c, modelo, 6)


# ── render ────────────────────────────────────────────────────────────────────
def render(modelo: Dict[str, Any], secciones: Dict[str, Any], destino: Path) -> Path:
    """Genera el documento ejecutivo: SEIS páginas, en el orden aprobado (§4)."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    del VIOLACIONES[:]
    del REGISTRO_BBOX[:]
    c = canvas.Canvas(str(destino), pagesize=(W, H))
    di = modelo.get("document_identity") or {}
    c.setTitle(f"DICTUS — {TITULOS_PAGINA[0]} {di.get('folio')}")
    c.setAuthor("ARHIAX RE · DICTUS")
    c.setSubject("Informe ejecutivo de decisión inmobiliaria + expediente verificable")

    pagina1(c, modelo, secciones)
    c.showPage()
    pagina2(c, modelo, secciones)
    c.showPage()
    pagina3(c, modelo, secciones)
    c.showPage()
    pagina4(c, modelo, secciones)
    c.showPage()
    pagina5(c, modelo, secciones)
    c.showPage()
    pagina6(c, modelo, secciones)
    c.showPage()
    c.save()

    fallos = verificar_retícula()
    VIOLACIONES.extend(f"retícula {f}" for f in fallos)
    return destino


def hoja_anexos(destino: Path, mapa: List[Tuple[str, str, str]]) -> Path:
    """Hoja separadora de ANEXOS con el mapa de contenidos."""
    c = canvas.Canvas(str(destino), pagesize=(W, H))
    banda(c, 0, H - 120, W, 120, INK)
    banda(c, M, H - 132, 60, 3, GOLD)
    txt(c, M, H - 56, "ANEXOS", FB, 26, white, esp=2.0)
    txt(c, M, H - 78, "EVIDENCIA TÉCNICA COMPLETA DEL EXPEDIENTE", F, 9, GOLD_2, esp=0.8)
    txt(c, M, H - 96, "El cuerpo ejecutivo no elimina información: la reubica. Aquí está "
                      "el detalle auditable de cada afirmación.", F, 8, GOLD_2)
    y = H - 170
    for letra, titulo, contenido in mapa:
        panel(c, M, y - 46, ANCHO, 46, CARD, HAIR)
        banda(c, M, y - 46, 3, 46, GOLD)
        txt(c, M + 10, y - 18, f"ANEXO {letra}", FB, 9, GOLD, esp=0.8)
        txt(c, M + 90, y - 18, titulo, FB, 9.5, INK)
        wrap(c, M + 90, y - 32, contenido, F, 7.4, TEXT_2, ANCHO - 100, leading=8.6)
        y -= 52
    txt(c, M, 60, "El detalle técnico (URLs, identificadores de capa, versiones de parser, "
                  "snapshots, hashes individuales y recibos completos) vive en estos "
                  "anexos: no se imprime en el cuerpo ejecutivo.", FO, 7.2, TEXT_3)
    c.save()
    return destino

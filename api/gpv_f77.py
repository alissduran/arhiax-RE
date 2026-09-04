# -*- coding: utf-8 -*-
"""
ARHIAX RE — GPV-F-77: Formato Estudio de Títulos Artículo 276 Ley 1955 de 2019
==============================================================================
Genera un DOCX pre-diligenciado a partir de la plantilla oficial del Ministerio
de Vivienda (GPV-F-77) usando los datos reales del caso ARHIAX: el Certificado
de Tradición y Libertad (CTL/SNR) analizado por legal_analyzer y el
enriquecimiento catastral en vivo de la ciudad.

Reglas del instructivo GPV-I-20 (v4.0) que se respetan:
  * Cuando un ítem no puede diligenciarse se escribe "NO APLICA (N/A)" o
    "NO REGISTRA" (cuando la fuente no lo trae). Nunca se inventan datos.
  * El tracto sucesivo se describe de forma cronológica (modo de adquisición,
    escritura/acto, notaría/juzgado y fechas según consten en el CTL).
  * El resultado es un BORRADOR DE TRABAJO: la Sección 4 (datos del profesional
    jurídico que diligencia y firma) queda en blanco para diligenciamiento
    manual. Las secciones jurídicas requieren validación del profesional.
"""
import os
import re
from datetime import datetime
from io import BytesIO
from pathlib import Path

_AYER = None  # inyectable en tests

_MESES_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
             "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

_MESES_ABREV = ["ene", "feb", "mar", "abr", "may", "jun",
                "jul", "ago", "sep", "oct", "nov", "dic"]

_CIUDAD_ADMIN = {
    "barranquilla": ("Atlántico", "Barranquilla"),
    "medellin": ("Antioquia", "Medellín"),
    "bogota": ("Bogotá D.C.", "Bogotá D.C."),
}

_PLANTILLA = "GPV-F-77_Estudio_Titulos_Art276_Ley1955_2019.docx"


def _ruta_plantilla():
    """Localiza la plantilla oficial: api/plantillas/ (Vercel empaqueta api/)."""
    aqui = Path(__file__).resolve().parent
    candidatas = [
        aqui / "plantillas" / _PLANTILLA,
        aqui.parent / "plantillas" / _PLANTILLA,
    ]
    for c in candidatas:
        if c.exists():
            return str(c)
    raise FileNotFoundError(
        "No se encontró la plantilla GPV-F-77. Buscada en: " +
        " | ".join(str(c) for c in candidatas))


def _hoy():
    if _AYER is not None:
        return _AYER
    return datetime.now()


def _fecha_dd_mmm_aaaa(dt=None):
    """Fecha en formato dd-mmm-aaaa (p. ej. 12-ago-2026) como pide la plantilla."""
    dt = dt or _hoy()
    return "{:02d}-{}-{}".format(dt.day, _MESES_ABREV[dt.month - 1], dt.year)


def _fecha_larga(dt=None):
    """12 de agosto de 2026 (para textos narrativos del documento)."""
    dt = dt or _hoy()
    return "{} de {} de {}".format(dt.day, _MESES_ES[dt.month - 1], dt.year)


# ── Helpers de edición del DOCX ──────────────────────────────────────────────

def _set_parrafo(p, texto):
    """Reemplaza TODO el contenido del párrafo por un run de texto plano."""
    for r in list(p.runs):
        r._element.getparent().remove(r._element)
    if texto:
        p.add_run(texto)


def _set_parrafo_multilinea(p, texto):
    """Escribe texto con saltos de línea reales dentro del mismo párrafo."""
    for r in list(p.runs):
        r._element.getparent().remove(r._element)
    if not texto:
        return
    lineas = texto.split("\n")
    for i, ln in enumerate(lineas):
        run = p.add_run(ln)
        if i < len(lineas) - 1:
            run.add_break()


def _escribir_celda(cell, texto):
    """Escribe texto en el primer párrafo de una celda (multi-línea si aplica)."""
    if not cell.paragraphs:
        cell.add_paragraph()
    _set_parrafo_multilinea(cell.paragraphs[0], texto)


# ── Redacción de secciones (texto plano, honesto) ───────────────────────────

def _seleccionar_anotaciones(ctx):
    """Anotaciones con detalle (num, fecha, tipo, partes, estado, texto)."""
    det = ctx.get("anotaciones_detalle") or []
    # tolera tanto dicts como tuplas del formato anterior
    out = []
    for a in det:
        if isinstance(a, dict):
            out.append(a)
        else:
            out.append({
                "num": a[0], "fecha": a[1], "tipo": a[2],
                "partes": a[3], "estado": a[4], "texto": ""})
    return out


_ESPEC_ADQUISICION = re.compile(
    r"COMPRAVENTA|MODO\s+DE\s+ADQUISICION|DIVISION\s+MATERIAL|ADJUDICACION|"
    r"PERMUTA|FUSION|VENTA\s+PARCIAL|SEGREGACION|SUCESION|CESION\s+DE\s+DOMINIO|"
    r"REMAT[EÓ]|LICITACION|DACION", re.IGNORECASE)

_ESPEC_HISTORIA = re.compile(
    r"DIVISION\s+MATERIAL|VENTA\s+PARCIAL|SEGREGACION|LOTEO|RELOTEO|"
    r"DESENGLOBE|FUSION|DIVISION\s+FISICA", re.IGNORECASE)

_ESPEC_GRAVAMEN = re.compile(
    r"GRAVAMEN|HIPOTECA|EMBARGO|MEDIDA\s+CAUTELAR|LIMITACION|AFECTACION|"
    r"VIVIENDA\s+FAMILIAR|PATRIMONIO\s+FAMILIA|SERVIDUMBRE|USUFRUCTO|"
    r"CONDICION\s+RESOLUTORIA", re.IGNORECASE)


def _extraer_escritura_y_notaria(texto):
    """Intenta extraer 'Escritura No. X del dd-mm-aaaa, Notaría Y' del texto
    crudo de una anotación SNR. Devuelve '' si no se identifica (sin inventar)."""
    if not texto:
        return ""
    sup = texto
    m_esc = re.search(
        r"(?:ESCRITURA\s+(?:PUBLICA\s+)?(?:No?\.?\s*)?(\d+)|"
        r"\bE\.?\s*P\.?\s*(?:No?\.?\s*)?(\d+))", sup, re.IGNORECASE)
    # Fecha de la escritura (buscar tras la palabra ESCRITURA, no la del encabezado)
    m_esc_fecha = re.search(
        r"ESCRITURA[^\n]*?(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})", sup, re.IGNORECASE)
    m_not = re.search(r"NOTAR[IÍ]A\s+(?:DEL\s+)?([A-ZÁÉÍÓÚÑ0-9 ]{2,40})", sup, re.IGNORECASE)
    partes = []
    if m_esc:
        num = m_esc.group(1) or m_esc.group(2)
        partes.append("Escritura No. {}".format(num))
    if m_esc_fecha:
        partes.append("del {}".format(m_esc_fecha.group(1)))
    if m_not:
        notaria = m_not.group(1).strip()
        if notaria and len(notaria) > 1:
            partes.append("Notaría {}".format(notaria))
    return " ".join(partes) if partes else ""


def _es_modo_adquisicion(tipo, texto):
    sup_t = (tipo or "").upper()
    sup_x = (texto or "").upper()
    return ("COMPRAVENTA" in sup_t or "ADQUISICION" in sup_x or
            "DIVISION MATERIAL" in sup_x or "MODO DE ADQUISICION" in sup_x or
            bool(_ESPEC_ADQUISICION.search(sup_x)))


def _modo_anotacion(a):
    """Modo de adquisición legible de una anotación (sin inventar si no consta)."""
    texto = a.get("texto") or ""
    m_esp = re.search(r"(?:MODO\s+DE\s+ADQUISICION|ESPECIFICACION)\s*:?\s*"
                      r"([^\n]{0,80})", texto, re.IGNORECASE)
    if m_esp:
        modo = re.sub(r"\s+", " ", m_esp.group(1)).strip(" -:")
        if modo:
            return modo
    return (a.get("tipo") or "").strip() or ""


def _formatear_partes(partes):
    """'X -> Y' -> 'De: X, a favor de: Y'."""
    if not partes or "->" not in partes:
        return ""
    de, a = partes.split("->", 1)
    de = re.sub(r"\s+", " ", de).strip(" .")
    a = re.sub(r"\s+", " ", a).strip(" .")
    if de and a:
        return "De: {}, a favor de: {}".format(de, a)
    return partes.strip()


def _es_limitacion_registral(a):
    """True si la anotación representa un gravamen/limitación VIGENTE real
    (excluye cancelaciones y anotaciones ya canceladas)."""
    tipo = (a.get("tipo") or "").upper()
    estado = (a.get("estado") or "").upper()
    if "CANCELACION" in tipo or "CANCELADA" in estado:
        return False
    sup = ((a.get("texto") or "") + " " + tipo).upper()
    return bool(_ESPEC_GRAVAMEN.search(sup))


def _estado_cancelacion_legible(estado):
    """'CANCELADA -- Anot. 006 la extingue' -> 'cancelada por la anotación Nro. 006'."""
    if not estado:
        return ""
    m = re.search(r"CANCELADA\s*--\s*Anot\.?\s*(\d+)", estado, re.IGNORECASE)
    if m:
        return "cancelada por la anotación Nro. {}".format(m.group(1))
    return "cancelada"


def _redactar_tracto(ctx):
    """Descripción cronológica del tracto sucesivo a partir de las anotaciones
    de mutación de dominio registradas en el CTL."""
    anots = _seleccionar_anotaciones(ctx)
    dominio = [a for a in anots if _es_modo_adquisicion(a.get("tipo"), a.get("texto"))]
    if not dominio:
        if ctx.get("sin_ctl"):
            return ("NO REGISTRA — no se aportó Certificado de Tradición y "
                    "Libertad (CTL); sin fuente para describir el tracto sucesivo.")
        return ("NO REGISTRA — el CTL analizado no presenta anotaciones de "
                "mutación de dominio extraíbles.")
    lineas = []
    apertura = (ctx.get("apertura") or "N/D").strip()
    if apertura and apertura != "N/D":
        lineas.append("Folio abierto el {}.".format(apertura))
    for a in sorted(dominio, key=lambda x: (x.get("num") or "")):
        num = a.get("num") or "?"
        fecha = (a.get("fecha") or "N/D").strip()
        esc = _extraer_escritura_y_notaria(a.get("texto"))
        partes = _formatear_partes(a.get("partes"))
        modo = _modo_anotacion(a)
        linea = "Anotación Nro. {} ({})".format(num, fecha)
        if modo and "CANCELADA" not in (a.get("estado") or ""):
            linea += ": {}".format(modo)
        elif "CANCELADA" not in (a.get("estado") or ""):
            linea += ": mutación de dominio"
        if esc:
            linea += " — " + esc
        if partes:
            linea += "; " + partes
        lineas.append(linea + ".")
    return "\n".join(lineas)


def _redactar_historia_fisica(ctx):
    """Ventas parciales, divisiones materiales y/o segregaciones visibles en el CTL."""
    anots = _seleccionar_anotaciones(ctx)
    if not anots:
        if ctx.get("sin_ctl"):
            return "NO REGISTRA — sin CTL no hay fuente para la historia física del inmueble."
        return "NO REGISTRA — el CTL analizado no presenta anotaciones extraíbles."
    hitos = []
    for a in anots:
        sup = ((a.get("texto") or "") + " " + (a.get("tipo") or "")).upper()
        if _ESPEC_HISTORIA.search(sup):
            num = a.get("num") or "?"
            fecha = (a.get("fecha") or "N/D").strip()
            esc = _extraer_escritura_y_notaria(a.get("texto"))
            texto = "Anotación Nro. {} ({}): {}".format(
                num, fecha, _modo_anotacion(a) or "división/segregación registrada")
            if esc:
                texto += " — " + esc
            hitos.append(texto + ".")
    if not hitos:
        return ("NO REGISTRA — el folio consultado no evidencia ventas parciales, "
                "divisiones materiales ni segregaciones en el CTL analizado.")
    return "\n".join(hitos)


def _redactar_limitaciones(ctx):
    """Gravámenes, medidas cautelares y afectaciones vigentes + cancelaciones."""
    anots = _seleccionar_anotaciones(ctx)
    if ctx.get("sin_ctl") or not anots:
        return "NO REGISTRA — no se aportó CTL; sin fuente registral para limitaciones al dominio."
    vigentes = []
    canceladas = []
    for a in anots:
        tipo = (a.get("tipo") or "").strip()
        estado = (a.get("estado") or "")
        sup_tipo = tipo.upper()
        es_gravamen = (("GRAVAMEN" in sup_tipo or "LIMITACION" in sup_tipo) or
                       bool(_ESPEC_GRAVAMEN.search(((a.get("texto") or "") + " " + sup_tipo).upper())))
        if not es_gravamen or "CANCELACION" in sup_tipo:
            continue
        num = a.get("num") or "?"
        fecha = (a.get("fecha") or "N/D").strip()
        desc = tipo
        if desc.startswith("GRAVAMEN: "):
            desc = desc[len("GRAVAMEN: "):]
        elif desc.startswith("LIMITACION: "):
            desc = desc[len("LIMITACION: "):]
        linea = "Anotación Nro. {} ({}): {}".format(num, fecha, desc)
        if "CANCELADA" in estado:
            linea += " [{}]".format(_estado_cancelacion_legible(estado))
            canceladas.append(linea)
        else:
            vigentes.append(linea)
    out = []
    if vigentes:
        out.append("Limitaciones vigentes registradas en el folio:")
        out.extend(vigentes)
    else:
        out.append("NO REGISTRA gravámenes, medidas cautelares ni afectaciones "
                   "vigentes en el folio consultado.")
    if canceladas:
        out.append("")
        out.append("Historial de limitaciones canceladas:")
        out.extend(canceladas)
    return "\n".join(out)


def _redactar_documentos(ctx):
    """Devuelve dict: prefijo de línea de la plantilla -> texto de reemplazo."""
    folio = ctx.get("folio") or "XXXXXXX"
    sin_ctl = ctx.get("sin_ctl")
    fecha = _fecha_larga()
    docs = {}

    if sin_ctl:
        docs["Consulta VUR FMI"] = "Consulta VUR FMI — NO REGISTRA (no se aportó CTL)"
    else:
        docs["Consulta VUR FMI"] = "Consulta VUR FMI {} — Certificado de Tradición y Libertad (CTL) del SNR analizado el {}".format(folio, fecha)

    # Escritura: usar la primera escritura detectada en el tracto, si existe
    anots = _seleccionar_anotaciones(ctx)
    escrituras = []
    for a in anots:
        if _es_modo_adquisicion(a.get("tipo"), a.get("texto")) and "CANCELADA" not in (a.get("estado") or ""):
            esc = _extraer_escritura_y_notaria(a.get("texto") or "")
            if esc:
                escrituras.append("{} (según anotación Nro. {})".format(esc, a.get("num")))
    if sin_ctl:
        docs["Escritura pública No."] = "Escritura pública No. — NO REGISTRA (sin CTL)"
    elif escrituras:
        docs["Escritura pública No."] = "Escritura pública No. — " + "; ".join(escrituras)
    else:
        docs["Escritura pública No."] = ("Escritura pública No. — NO REGISTRA: el CTL no detalla el número de "
                                         "escritura en las anotaciones extraíbles; verificar en el folio.")

    docs["Resolución No."] = ("Resolución No. — N/A (resolución de incorporación no aportada; "
                              "si aplica, diligenciar manualmente)")
    docs["Paz y salvo"] = ("Paz y salvo por concepto de impuesto predial unificado No. — NO REGISTRA: "
                           "debe ser allegado por la entidad pública (ver sección Impuestos).")
    docs["Estudio Técnico"] = ("Estudio Técnico elaborado por ARHIAX RE (módulo automático de "
                               "valoración y dictamen) el {}.".format(fecha))
    return docs


def _redactar_consideraciones(ctx):
    """Notas honestas de contexto: origen, fuentes, pendientes y advertencias."""
    folio = ctx.get("folio") or "XXXXXXX"
    fecha = _fecha_larga()
    notas = []
    notas.append(
        "El presente Estudio de Títulos se genera como BORRADOR AUTOMÁTICO por el "
        "módulo ARHIAX RE el {}, a partir del Certificado de Tradición y Libertad "
        "(FMI {}) y de la información catastral pública de la ciudad indicada en la "
        "Sección 1. Requiere revisión, complementación y firma del profesional "
        "jurídico responsable (Sección 4).".format(fecha, folio))
    cod = ctx.get("codigo_catastral")
    nupre = ctx.get("nupre")
    if cod or nupre:
        det = []
        if cod:
            det.append("código catastral {} (30 dígitos)".format(cod))
        if nupre:
            det.append("NUPRE {}".format(nupre))
        notas.append("Identificadores del CTL: " + "; ".join(det) + ".")
    if ctx.get("area_juridica") and ctx.get("area_catastral"):
        try:
            aj = float(ctx.get("area_juridica"))
            ac = float(ctx.get("area_catastral"))
            if abs(aj - ac) > 1.0:
                notas.append(
                    "Se observa diferencia entre el área jurídica del folio ({:.2f} m²) y el área "
                    "catastral ({:.2f} m²); corresponde al estudio técnico/jurídico precisar su "
                    "incidencia.".format(aj, ac))
        except (TypeError, ValueError):
            pass
    if ctx.get("sin_ctl"):
        notas.append(
            "ADVERTENCIA: el estudio se genera sin Certificado de Tradición y Libertad. "
            "Sin el CTL no puede verificarse la titularidad ni los gravámenes del inmueble; "
            "este documento NO es apto para soportar la transferencia de dominio del "
            "Artículo 276 de la Ley 1955 de 2019.")
    else:
        notas.append(
            "Regla de diligenciamiento GPV-I-20: los ítems sin fuente se marcan "
            "'NO REGISTRA' o 'NO APLICA (N/A)'; no se asumen datos no verificados.")
    return "\n".join(notas)


def _redactar_recomendacion(ctx):
    if ctx.get("sin_ctl"):
        return ("NO APTO — no se aportó Certificado de Tradición y Libertad. Se recomienda "
                "obtener el CTL vigente del folio en la Oficina de Registro (SNR) y repetir "
                "el estudio antes de cualquier trámite de transferencia.")
    anots = _seleccionar_anotaciones(ctx)
    vigentes = [a for a in anots if _es_limitacion_registral(a)]
    if vigentes:
        nums = ", ".join("anot. " + str(a.get("num")) for a in vigentes)
        return ("De la revisión automática del folio se detectan gravámenes o limitaciones "
                "VIGENTES ({}) que restringen la libre disposición. NO se recomienda tramitar "
                "la transferencia de dominio del Artículo 276 de la Ley 1955 de 2019 mientras "
                "no se levanten o aclaren dichas limitaciones. Validar por el profesional "
                "jurídico.".format(nums))
    return ("De la revisión automática del folio no se evidencian gravámenes, medidas "
            "cautelares ni afectaciones vigentes. Viabilidad preliminar POSITIVA para la "
            "transferencia de dominio del Artículo 276 de la Ley 1955 de 2019, sujeta a la "
            "verificación del paz y salvo de impuestos y a la validación del profesional "
            "jurídico.")


# ── Generación principal ─────────────────────────────────────────────────────

def generar_docx_gpv_f77(ctx, plantilla_path=None):
    """
    Rellena la plantilla GPV-F-77 con `ctx` y devuelve los bytes del DOCX.

    ctx (dict) admite: folio, ciudad, direccion, barrio, area_juridica,
    area_catastral, codigo_catastral, nupre, apertura, titulares,
    descripcion_ctl, anotaciones_detalle, sin_ctl, expediente.
    """
    from docx import Document

    path = plantilla_path or _ruta_plantilla()
    doc = Document(path)
    ciudad = (ctx.get("ciudad") or "barranquilla").lower().strip()
    if ciudad not in _CIUDAD_ADMIN:
        ciudad = "barranquilla"
    departamento, municipio = _CIUDAD_ADMIN[ciudad]
    sin_ctl = bool(ctx.get("sin_ctl"))
    folio = ctx.get("folio") or "XXXXXXX"

    # ── Tabla 0: IDENTIFICACIÓN DEL PREDIO ─────────────────────────────────
    t0 = doc.tables[0]
    # [1,1] Expediente No. (si aplica) — sin expediente ICT–INURBE no se afirma
    _escribir_celda(t0.rows[1].cells[1],
                    ctx.get("expediente") or "N/A — expediente interno ICT–INURBE no suministrado")
    # [1,3] Fecha de elaboración (dd-mmm-aaaa)
    _escribir_celda(t0.rows[1].cells[3], _fecha_dd_mmm_aaaa())
    # [2,1] Departamento / [2,3] Municipio
    _escribir_celda(t0.rows[2].cells[1], departamento)
    _escribir_celda(t0.rows[2].cells[3], municipio)
    # [3,1] Dirección / [3,3] Urbanización/Barrio
    direccion = (ctx.get("direccion") or "").strip()
    _escribir_celda(t0.rows[3].cells[1],
                    direccion or "NO REGISTRA — dirección no identificada en el CTL")
    barrio = (ctx.get("barrio") or "").strip()
    _escribir_celda(t0.rows[3].cells[3],
                    barrio or ("N/A — sin urbanización/barrio identificado"
                               if not sin_ctl else "NO REGISTRA — sin CTL"))
    # [4,1] Matrícula Mayor Extensión / [4,3] Matrícula Individual
    _escribir_celda(t0.rows[4].cells[1], folio if not sin_ctl else "NO REGISTRA — sin CTL")
    ind = ctx.get("matricula_individual")
    if ind:
        _escribir_celda(t0.rows[4].cells[3], ind)
    elif sin_ctl:
        _escribir_celda(t0.rows[4].cells[3], "NO REGISTRA — sin CTL")
    else:
        _escribir_celda(t0.rows[4].cells[3],
                        "N/A — el CTL no evidencia loteo, reloteo, desenglobe ni segregación; "
                        "no se identifica matrícula individual derivada")
    # [5,1] Código Catastral (30 dígitos) — se usa el del CTL; si no, NUPRE
    cod = (ctx.get("codigo_catastral") or "").strip()
    nupre = (ctx.get("nupre") or "").strip()
    if cod:
        _escribir_celda(t0.rows[5].cells[1], cod)
    elif nupre:
        _escribir_celda(t0.rows[5].cells[1],
                        "NO REGISTRA código de 30 dígitos en el CTL; NUPRE: {}".format(nupre))
    else:
        _escribir_celda(t0.rows[5].cells[1],
                        "NO REGISTRA" if not sin_ctl else "NO REGISTRA — sin CTL")
    # [6,1] Área del inmueble (M2): jurídica (FMI) y catastral cuando están
    aj = ctx.get("area_juridica")
    ac = ctx.get("area_catastral")
    partes_area = []
    if aj not in (None, "", 0):
        partes_area.append("Jurídica (FMI): {} m²".format(aj))
    if ac not in (None, "", 0):
        partes_area.append("Catastral: {} m²".format(ac))
    _escribir_celda(t0.rows[6].cells[1],
                    (" — ".join(partes_area)) if partes_area
                    else ("NO REGISTRA" if not sin_ctl else "NO REGISTRA — sin CTL"))

    # ── Tabla 1: INFORMACIÓN JURÍDICA Y ESTUDIO DE TÍTULOS ─────────────────
    t1 = doc.tables[1]
    # R2 = celda grande con subtítulos: tracto (párr. 3 vacío tras boilerplate),
    # linderos (párr. 7 vacío), historia física (párr. 11 vacío).
    cell_tradicion = t1.rows[2].cells[0]
    ps = cell_tradicion.paragraphs

    def _escribir_despues_de(ps, idx_titulo, texto):
        """Escribe `texto` en el primer párrafo vacío posterior a idx_titulo."""
        for i in range(idx_titulo + 1, len(ps)):
            if not ps[i].text.strip():
                _set_parrafo_multilinea(ps[i], texto)
                return
        # sin párrafo vacío: agregar al final de la celda
        _escribir_celda(cell_tradicion, texto)

    # párrafos: 1=título tracto, 6=linderos, 10=historia (ver inspección)
    idx_tracto = next((i for i, p in enumerate(ps) if "TRACTO SUCESIVO" in p.text.upper()), 1)
    idx_linderos = next((i for i, p in enumerate(ps) if "LINDEROS GENERALES" in p.text.upper()), 6)
    idx_historia = next((i for i, p in enumerate(ps) if "HISTORIA F" in p.text.upper()), 10)

    tracto = _redactar_tracto(ctx)
    _escribir_despues_de(ps, idx_tracto, tracto)

    linderos = (ctx.get("descripcion_ctl") or "").strip()
    if not linderos:
        linderos = ("NO REGISTRA — el CTL no trae descripción de linderos extraíble"
                    if not sin_ctl else "NO REGISTRA — sin CTL")
    _escribir_despues_de(ps, idx_linderos, linderos)

    historia = _redactar_historia_fisica(ctx)
    _escribir_despues_de(ps, idx_historia, historia)

    # R3/R4 Titularidad actual
    titulares = (ctx.get("titulares") or "").strip()
    if sin_ctl or not titulares or titulares.startswith("PENDIENTE"):
        _escribir_celda(t1.rows[4].cells[0],
                        "NO REGISTRA — no se identificó titular vigente en el CTL analizado"
                        if not sin_ctl else "NO REGISTRA — sin CTL")
    else:
        _escribir_celda(t1.rows[4].cells[0], titulares)
    # R5/R6 Impuestos, tasas y contribuciones (paz y salvo lo allega la entidad)
    _escribir_celda(t1.rows[6].cells[0],
                    "NO REGISTRA — el certificado de paz y salvo de impuestos, tasas y "
                    "contribuciones del bien debe ser remitido por la entidad pública al "
                    "Ministerio; no disponible en la consulta automática.")
    # R7/R8 Limitaciones al dominio
    _escribir_celda(t1.rows[8].cells[0], _redactar_limitaciones(ctx))
    # R9/R10 Consideraciones finales
    _escribir_celda(t1.rows[10].cells[0], _redactar_consideraciones(ctx))
    # R11 Documentos y/o herramientas utilizadas (lista con viñetas de la plantilla)
    docs = _redactar_documentos(ctx)
    cell_docs = t1.rows[11].cells[1]
    for p in cell_docs.paragraphs:
        txt = p.text.strip()
        for prefijo, reemplazo in docs.items():
            if txt.startswith(prefijo):
                _set_parrafo(p, reemplazo)
                break
    # R12 Recomendaciones
    _escribir_celda(t1.rows[12].cells[1], _redactar_recomendacion(ctx))

    # ── Tabla 2: DATOS DE DILIGENCIAMIENTO (firma manual del profesional) ──
    t2 = doc.tables[2]
    _escribir_celda(t2.rows[1].cells[1], "")   # Diligenciado por (nombre)
    _escribir_celda(t2.rows[2].cells[1], "")   # Profesión
    _escribir_celda(t2.rows[2].cells[3], "")   # Tarjeta profesional

    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()

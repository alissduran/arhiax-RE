"""Expediente de Confianza de la Operación Inmobiliaria (el producto reencuadrado).

Une la capa de integridad (SAGRILAFT) con la de predio (títulos) y precio (avalúo),
respondiendo las 5 preguntas del expediente.
"""
from dataclasses import dataclass
from typing import Optional, Tuple

from arhia_title.contracts import Hallazgo
from arhia_title.rules import ejecutar as ejecutar_titulos


def _CBJ(*requirement_ids: str) -> str:
    """Base legal citada desde el mapeo verificado (SIN numerales no verificados)."""
    try:
        from sanctions.legal import base_legal
        return base_legal(*requirement_ids)
    except Exception:  # noqa: BLE001
        return "Circular Externa 100-000020 del 2 de julio de 2026 (CBJ — Supersociedades)"


@dataclass(frozen=True)
class FichaIntegridad:
    screening: str = ""      # ok | coincidencia | pendiente | revisionManual
    beneficiario_final: str = ""
    regimen: str = ""        # pleno | rmm | no_obligado
    sarlaft: str = ""        # verificado | pendiente
    # --- enriquecido desde el pipeline SAGRILAFT+PTEE ---
    perfil: str = ""         # alto | medio | bajo
    senales: Tuple[str, ...] = ()
    operacion_inusual: bool = False
    requiere_analisis: bool = False
    dd_requerida: bool = False
    bf_coincidencia: bool = False   # algún beneficiario final coincide con listas
    bf_resultados: Tuple[tuple, ...] = ()
    screening_por_fuente: Tuple[tuple, ...] = ()
    screening_completo: bool = True
    fuentes_no_disponibles: Tuple[str, ...] = ()
    eventos: Tuple[dict, ...] = ()


@dataclass(frozen=True)
class Expediente:
    id: str
    tipo: str
    hallazgos: Tuple[Hallazgo, ...]
    integridad: FichaIntegridad


PREGUNTAS = {
    "P1": "¿Quiénes intervienen y quién se beneficia realmente?",
    "P2": "¿Qué inmueble es y qué derechos/restricciones lo afectan?",
    "P3": "¿Cómo se sustentó el precio?",
    "P4": "¿Quién paga, por qué medio y con qué coherencia?",
    "P5": "¿Quién verificó, decidió y asumió responsabilidad?",
}


def _hallazgo_integridad(integridad):
    h = []
    if integridad.sarlaft in ("pendiente", "incompleto") or integridad.screening == "pendiente":
        h.append(Hallazgo("EXP-INT-1", "Verificación SARLAFT / screening", "OBSERVACION", "media",
            "Screening de listas y verificación SARLAFT pendientes de validar en plataforma externa.",
            base_legal=_CBJ("SAG_LISTAS_VINCULANTES", "SAG_BENEFICIARIO_FINAL", "SAG_EVIDENCIA_TRAZABILIDAD"),
            implicacion="Cumplimiento pendiente: la operación no queda trazable sin screening + beneficiario final documentados.",
            regla="EXP-INT", accion="Ejecutar el screening contra las fuentes oficiales de sanciones y registrar beneficiario final.", responsable="abogado"))
    if integridad.screening == "coincidencia":
        h.append(Hallazgo("EXP-INT-0", "Coincidencia en listas", "RIESGO", "alta",
            "Se detectó coincidencia en screening; requiere revisión humana y DD intensificada.",
            base_legal=_CBJ("SAG_LISTAS_VINCULANTES"),
            implicacion="Riesgo elevado; la operación requiere diligencia ampliada.", regla="EXP-INT", responsable="abogado"))
    if integridad.bf_coincidencia:
        h.append(Hallazgo("EXP-INT-0-BF", "Coincidencia de beneficiario final en listas", "RIESGO", "alta",
            "Un beneficiario final (persona natural) coincide en alguna lista vinculante.",
            base_legal=_CBJ("SAG_BENEFICIARIO_FINAL", "SAG_LISTAS_VINCULANTES"),
            implicacion="Riesgo elevado: el beneficiario final está en una lista; requiere revisión y, en su caso, reporte.",
            regla="EXP-INT", responsable="cumplimiento"))
    if integridad.regimen:
        h.append(Hallazgo("EXP-INT-2", "Régimen estimado: " + integridad.regimen, "INFORMATIVO", "baja",
            "Sujeto obligado estimado en régimen " + integridad.regimen + " por tamaño (proxy).",
            base_legal=_CBJ("SAG_SUJETO_OBLIGADO"),
            implicacion="Determina la carga de cumplimiento aplicable.", regla="EXP-INT", responsable="abogado"))
    if integridad.beneficiario_final:
        h.append(Hallazgo("EXP-INT-3", "Beneficiario final identificado", "OK", "baja",
            "Beneficiario final: " + integridad.beneficiario_final + ".",
            base_legal=_CBJ("SAG_BENEFICIARIO_FINAL"),
            implicacion="La identidad del dueño real está establecida; alimenta el screening.", regla="EXP-INT", responsable="sistema"))
    if integridad.perfil:
        h.append(Hallazgo("EXP-INT-4", "Perfil de riesgo de la contraparte: " + integridad.perfil, "INFORMATIVO", "baja",
            "Perfil " + integridad.perfil + " asignado por el motor (screening, beneficiario final, señales, dimensiones).",
            base_legal=_CBJ("SAG_IDENTIFICACION_CONTRAPARTES"),
            implicacion="Determina la profundidad de la debida diligencia y las medidas de control.", regla="EXP-INT", responsable="sistema"))
    if integridad.operacion_inusual:
        h.append(Hallazgo("EXP-INT-5", "Operación inusual (posible LA/FT)", "RIESGO", "alta",
            "La operación presenta características inusuales; se recomienda análisis del oficial de cumplimiento."
            + (" Señales: " + "; ".join(integridad.senales) + "." if integridad.senales else ""),
            base_legal=_CBJ("SAG_OPERACIONES_INUSUALES"),
            implicacion="Procede análisis humano y, si procede, reporte a la UIAF; la operación no debe cerrarse sin que el oficial de cumplimiento se pronuncie.",
            regla="EXP-INT", accion="Revisar origen de fondos, señales y relación con la operación; registrar la evidencia.",
            responsable="cumplimiento"))
    if integridad.dd_requerida:
        h.append(Hallazgo("EXP-INT-6", "Debida diligencia requerida/vencida", "OBSERVACION", "media",
            "El calendario de DD marca actualización requerida o vencida para la contraparte.",
            base_legal=_CBJ("SAG_IDENTIFICACION_CONTRAPARTES", "SAG_LISTAS_VINCULANTES"),
            implicacion="Actualizar la debida diligencia antes del cierre para no incumplir el deber de identificación.",
            regla="EXP-INT", accion="Ejecutar la DD y registrar la actualización con evidencia.", responsable="cumplimiento"))
    return h


def construir(caso, integridad=None):
    """Construye el Expediente uniendo hallazgos de títulos (predio + precio) e integridad."""
    integridad = integridad or FichaIntegridad()
    hallazgos = list(ejecutar_titulos(caso)) + _hallazgo_integridad(integridad)
    return Expediente(id=caso.id, tipo=caso.tipo, hallazgos=tuple(hallazgos), integridad=integridad)


def generar_markdown(exp):
    L = []
    a = L.append
    a("# Expediente de Confianza de la Operación Inmobiliaria")
    a("")
    a(f"**Caso:** {exp.id} · **Tipo:** {exp.tipo} · **Insumo preliminar** — no sustituye concepto profesional.")
    a("")
    a("## Las 5 preguntas")
    a("- **P1 ¿Quiénes intervienen y quién se beneficia?** -> " + (exp.integridad.beneficiario_final or "por verificar (BF)") + " — ver hallazgos de titularidad/integridad.")
    a("- **P2 ¿Qué inmueble y qué restricciones?** -> ver hallazgos de identidad, cronología, gravámenes.")
    a("- **P3 ¿Cómo se sustentó el precio?** -> ver hallazgos de precio vs avalúo.")
    a("- **P4 ¿Quién paga y con qué coherencia?** -> ver hallazgos de pagos/terceros.")
    a("- **P5 ¿Quién decidió y respondió?** -> responsable de validar por hallazgo + conclusión del profesional.")
    a("")
    a("## Hallazgos")
    for h in exp.hallazgos:
        a(f"### {h.id} · {h.titulo} — [{h.estado}]")
        if h.descripcion:
            a("- **Qué evidencia:** " + h.descripcion)
        if h.base_legal:
            a("- **Base legal:** " + h.base_legal)
        if h.implicacion:
            a("- **Implicación:** " + h.implicacion)
        if h.accion:
            a("- **Acción:** " + h.accion)
        a("- **Responsable:** " + h.responsable)
        a("")
    a("## Conclusión profesional")
    a("_(Reservado al abogado / avaluador. El análisis automático es insumo.)_")
    return "\n".join(L)


def generar_html(exp):
    cards = "".join(
        '<div class="exp"><b>' + _esc(h.id) + ' · ' + _esc(h.titulo) + ' [' + _esc(h.estado) + ']</b>'
        + ('<div>' + _esc(h.descripcion) + '</div>' if h.descripcion else '')
        + ('<div><i>Base legal: ' + _esc(h.base_legal) + '</i></div>' if h.base_legal else '')
        + ('<div><i>Implicación: ' + _esc(h.implicacion) + '</i></div>' if h.implicacion else '')
        + '</div>'
        for h in exp.hallazgos
    )
    return ('<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>Expediente ' + _esc(exp.id) + '</title>'
        '<style>body{font-family:Arial;margin:24px auto;max-width:900px;padding:8px}h1{color:#10243f}'
        '.exp{border:1px solid #ddd;border-left:4px solid #10243f;padding:10px 14px;margin:10px 0;border-radius:6px}'
        '.q{background:#eef;padding:8px 12px;border-radius:5px;margin:6px 0}</style></head><body>'
        '<h1>Expediente de Confianza — ' + _esc(exp.id) + '</h1>'
        '<p><b>Las 5 preguntas</b></p>'
        '<div class="q">P1 ' + _esc(PREGUNTAS["P1"]) + '</div>'
        '<div class="q">P2 ' + _esc(PREGUNTAS["P2"]) + '</div>'
        '<div class="q">P3 ' + _esc(PREGUNTAS["P3"]) + '</div>'
        '<div class="q">P4 ' + _esc(PREGUNTAS["P4"]) + '</div>'
        '<div class="q">P5 ' + _esc(PREGUNTAS["P5"]) + '</div>'
        '<h2>Hallazgos</h2>' + cards +
        '<p style="color:#666;font-size:12px">Insumo preliminar. No sustituye concepto profesional; la conclusión la emite el profesional competente.</p>'
        '</body></html>')


def _esc(s):
    import html
    return html.escape(str(s))

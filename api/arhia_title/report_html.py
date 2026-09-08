"""Render del Informe Preliminar a HTML autocontenido (demo Lonja, sin servidor)."""
import html
from collections import Counter

from .contracts import Caso

ESTADO_COLOR = {
    "RIESGO": "#d32f2f",
    "OBSERVACION": "#f57c00",
    "INCONSISTENTE": "#e65100",
    "INFORMACION_INSUFICIENTE": "#757575",
    "REQUIERE_REVISION": "#f9a825",
    "OK": "#2e7d32",
}

CSS = """
:root{--navy:#10243f;--ink:#1c2733;--muted:#5b6b7a;--line:#e3e8ee;--bg:#f4f6f9}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;background:var(--bg);color:var(--ink);line-height:1.55}
.wrap{max-width:980px;margin:0 auto;padding:32px 24px 64px}
header{background:var(--navy);color:#fff;padding:28px 32px;border-radius:14px 14px 0 0}
.brand{font-size:12px;letter-spacing:.14em;text-transform:uppercase;opacity:.75}
header h1{margin:8px 0 4px;font-size:26px;font-weight:700}
.meta{font-size:13px;opacity:.85}
.disclaimer{margin-top:14px;font-size:12px;background:rgba(255,255,255,.10);border:1px solid rgba(255,255,255,.18);padding:10px 12px;border-radius:8px}
.card{background:#fff;border:1px solid var(--line);margin-bottom:14px;padding:24px 30px;border-radius:0 0 10px 10px}
h2{font-size:15px;letter-spacing:.04em;text-transform:uppercase;color:var(--navy);margin:0 0 16px;border-bottom:2px solid var(--line);padding-bottom:8px}
.pills{display:flex;flex-wrap:wrap;gap:10px}
.pill{color:#fff;font-size:13px;font-weight:600;padding:5px 12px;border-radius:999px}
.kv{display:grid;grid-template-columns:180px 1fr;gap:6px 16px;font-size:14px}
.kv b{color:var(--muted);font-weight:600}
.timeline{list-style:none;margin:0;padding:0;border-left:3px solid var(--line);margin-left:6px}
.timeline li{padding:6px 0 6px 16px;position:relative;font-size:14px}
.timeline li::before{content:'';position:absolute;left:-7px;top:12px;width:11px;height:11px;border-radius:50%;background:var(--navy)}
.timeline .tipo{font-weight:600}
.timeline .cancelada{color:var(--muted)}
.hallazgo{border:1px solid var(--line);border-left:5px solid #607d8b;border-radius:10px;padding:18px 22px;margin-bottom:16px;background:#fff}
.hallazgo .head{display:flex;align-items:center;gap:10px;margin-bottom:6px}
.hallazgo .head h3{margin:0;flex:1;font-size:16px;color:var(--ink)}
.badge{color:#fff;font-size:11px;font-weight:700;padding:3px 9px;border-radius:999px;white-space:nowrap}
.sev{font-size:12px;color:var(--muted);font-weight:600}
.campo{margin:8px 0;font-size:14px}
.campo b{color:var(--navy);font-weight:700;display:block;font-size:11px;text-transform:uppercase;letter-spacing:.05em;margin-bottom:2px}
.reco{list-style:none;padding:0}
.reco li{padding:7px 0;border-bottom:1px dashed var(--line);font-size:14px}
.conclusion{background:#fff8e6;border:1px solid #f0e0b0;border-radius:10px;padding:16px 18px;font-size:14px;color:#6b5518}
footer{margin-top:24px;font-size:12px;color:var(--muted);text-align:center}
"""


def _esc(s):
    return html.escape(str(s))


def _badge(estado):
    return '<span class="badge" style="background:' + ESTADO_COLOR.get(estado, "#607d8b") + '">' + _esc(estado) + '</span>'


def _pill(estado, n):
    return '<span class="pill" style="background:' + ESTADO_COLOR.get(estado, "#607d8b") + '">' + _esc(estado) + ' · ' + str(n) + '</span>'


def _hallazgo_card(h):
    borde = ESTADO_COLOR.get(h.estado, "#607d8b")
    parts = []
    parts.append('<div class="hallazgo" style="border-left-color:' + borde + '">')
    parts.append('<div class="head"><h3>' + _esc(h.id) + ' · ' + _esc(h.titulo) + '</h3>' + _badge(h.estado) + '</div>')
    parts.append('<div class="sev">Severidad: ' + _esc(h.severidad) + ' · Responsable de validar: ' + _esc(h.responsable) + '</div>')
    if h.descripcion:
        parts.append('<div class="campo"><b>Qué evidencia el motor</b>' + _esc(h.descripcion) + '</div>')
    if h.base_legal:
        parts.append('<div class="campo"><b>Base legal</b>' + _esc(h.base_legal) + '</div>')
    if h.implicacion:
        parts.append('<div class="campo"><b>Implicación</b>' + _esc(h.implicacion) + '</div>')
    if h.evidencia:
        parts.append('<div class="campo"><b>Evidencia citada</b>' + "<br>".join(_esc(e.documento) for e in h.evidencia) + '</div>')
    if h.accion:
        parts.append('<div class="campo"><b>Acción recomendada</b>' + _esc(h.accion) + '</div>')
    parts.append('</div>')
    return "".join(parts)


def render(caso, hallazgos):
    conteo = Counter(h.estado for h in hallazgos)
    orden = ("RIESGO", "OBSERVACION", "INCONSISTENTE", "INFORMACION_INSUFICIENTE", "REQUIERE_REVISION", "OK")
    pills = "".join(_pill(e, conteo[e]) for e in orden if conteo.get(e))
    p = caso.predio
    kv = ('<div class="kv">'
          '<div><b>Folio</b></div><div>' + _esc(p.folio_matricula) + '</div>'
          '<div><b>Catastro</b></div><div>' + _esc(p.codigo_catastral) + '</div>'
          '<div><b>Dirección</b></div><div>' + _esc(p.direccion) + '</div>'
          '<div><b>Área registral</b></div><div>' + str(p.area_registral) + ' m²</div>'
          '<div><b>Área catastral</b></div><div>' + str(p.area_catastral) + ' m²</div>'
          '</div>')
    if caso.tipo == "informe_base":
        partes = '<div class="kv"><div><b>Titular vigente</b></div><div>' + _esc(caso.titular or "—") + '</div></div>'
    else:
        filas = "".join('<div><b>' + _esc(pp.rol) + '</b></div><div>' + _esc(pp.nombre) + '</div>' for pp in caso.partes)
        partes = '<div class="kv">' + filas + '</div>'
    if caso.anotaciones:
        _li = []
        for a in sorted(caso.anotaciones, key=lambda x: x.fecha):
            cancelada = ' <span class="cancelada">(cancelada)</span>' if a.estado == "cancelada" else ""
            _li.append('<li><span class="tipo">' + _esc(a.tipo) + '</span>' + cancelada + ' — <span class="sev">' + a.fecha + ' · Anotación ' + str(a.numero) + '</span></li>')
        cron = '<ul class="timeline">' + "".join(_li) + '</ul>'
    else:
        cron = "<p>Sin anotaciones.</p>"
    tarjetas = "".join(_hallazgo_card(h) for h in hallazgos)
    rec = [h for h in hallazgos if h.estado in ("RIESGO", "OBSERVACION", "INCONSISTENTE", "REQUIERE_REVISION")]
    reco_items = "".join('<li><b>' + _esc(h.titulo) + ':</b> ' + _esc(h.accion or h.descripcion) + '</li>' for h in rec) if rec else "<li>Sin observaciones críticas.</li>"
    return ('<!DOCTYPE html>\n<html lang="es">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            '<title>Informe Preliminar — ' + _esc(caso.id) + '</title>\n<style>' + CSS + '</style>\n</head>\n<body>\n'
            '<div class="wrap">\n'
            '  <header>\n    <div class="brand">ARHIAX · Pre-Dictamen Determinista</div>\n'
            '    <h1>Informe Preliminar de Observaciones y Riesgos</h1>\n'
            '    <div class="meta">Caso ' + _esc(caso.id) + ' · ' + _esc(caso.tipo) + ' · Análisis preliminar automático</div>\n'
            '    <div class="disclaimer">Este es un análisis preliminar insumo. No constituye concepto jurídico, certificación de comerciabilidad ni asegurabilidad del título. Debe ser validado por el profesional competente.</div>\n'
            '  </header>\n\n'
            '  <div class="card"><h2>Resumen</h2><div class="pills">' + pills + '</div></div>\n'
            '  <div class="card"><h2>Inmueble</h2>' + kv + '</div>\n'
            '  <div class="card"><h2>Partes y titularidad</h2>' + partes + '</div>\n'
            '  <div class="card"><h2>Cronología registral</h2>' + cron + '</div>\n'
            '  <div class="card"><h2>Análisis preliminar de cada hallazgo</h2>' + tarjetas + '</div>\n'
            '  <div class="card"><h2>Acciones recomendadas</h2><ul class="reco">' + reco_items + '</ul></div>\n'
            '  <div class="card"><h2>Conclusión profesional</h2>\n'
            '    <div class="conclusion">Reservado al abogado / avaluador. El análisis automático es insumo; la conclusión la emite el profesional competente.</div>\n'
            '  </div>\n'
            '  <footer>ARHIAX · evidencia reconstruible · cada regla con dueño y vigencia · ' + _esc(caso.id) + '</footer>\n'
            '</div>\n</body>\n</html>')


def escribir(caso, hallazgos, ruta):
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(render(caso, hallazgos))
    return ruta

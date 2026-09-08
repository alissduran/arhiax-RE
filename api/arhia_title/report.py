"""Generador del Informe Preliminar (Markdown) — análisis preliminar profundo."""
from collections import Counter


def generar_informe(caso, hallazgos):
    conteo = Counter(h.estado for h in hallazgos)
    L = []
    a = L.append
    a("# Informe Preliminar de Observaciones y Riesgos Jurídico-Inmobiliarios")
    a("")
    a(f"**Caso:** {caso.id} · **Tipo:** {caso.tipo} · **Análisis preliminar automático. No constituye concepto jurídico, certificación de comerciabilidad ni asegurabilidad del título.**")
    a("")
    a("## Resumen")
    for estado in ("RIESGO", "OBSERVACION", "INCONSISTENTE", "INFORMACION_INSUFICIENTE", "REQUIERE_REVISION", "OK"):
        n = conteo.get(estado)
        if n:
            a(f"- {estado}: {n}")
    a("")
    a("## Inmueble")
    p = caso.predio
    a(f"- Folio: {p.folio_matricula} · Catastro: {p.codigo_catastral}")
    if p.direccion:
        a(f"- Dirección: {p.direccion}")
    if p.area_registral:
        a(f"- Área registral: {p.area_registral} m² · Área catastral: {p.area_catastral} m²")
    a("")
    a("## Parte(s) y titularidad")
    if caso.tipo == "informe_base":
        a(f"- Titular vigente: {caso.titular or '—'}")
    else:
        for pp in caso.partes:
            extra = f" ({pp.tipo_documento} {pp.numero_documento})" if pp.numero_documento else ""
            a(f"- {pp.rol}: {pp.nombre}{extra}")
    a("")
    a("## Cronología registral")
    if caso.anotaciones:
        for an in sorted(caso.anotaciones, key=lambda x: x.fecha):
            estado = f" **({an.estado})**" if an.estado != "vigente" else ""
            inst = f" — {an.instrumento}" if an.instrumento else ""
            a(f"- [{an.fecha}] Anotación {an.numero}: {an.tipo}{estado}{inst}")
    else:
        a("- Sin anotaciones.")
    a("")
    a("## Hallazgos preliminares")
    for h in hallazgos:
        a(f"### {h.id} · {h.titulo} — [{h.estado} · {h.severidad}]")
        if h.descripcion:
            a(f"- **Qué evidencia el motor:** {h.descripcion}")
        if h.base_legal:
            a(f"- **Base legal:** {h.base_legal}")
        if h.implicacion:
            a(f"- **Implicación:** {h.implicacion}")
        if h.evidencia:
            a("- **Evidencia citada:** " + "; ".join(f"{e.documento}" for e in h.evidencia))
        if h.accion:
            a(f"- **Acción recomendada:** {h.accion}")
        a(f"- **Responsable de validar:** {h.responsable}")
        a("")
    a("## Conclusión profesional")
    a("_(Reservado al abogado / avaluador. El análisis preliminar automático es insumo; la conclusión la emite el profesional competente.)_")
    return "\n".join(L)

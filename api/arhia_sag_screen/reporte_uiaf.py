"""Reportes a la UIAF — ROS / AROS (estructura SIREL-compatible).

El envío de reportes a la UIAF es **exclusivamente por SIREL** (Sistema de Reporte en Línea).
Este módulo genera los **reportes estructurados** (ROS = Operación Sospechosa; AROS = Ausencia
de Operaciones Sospechosas) con los campos esenciales, los valida y los exporta a XML/JSON,
para que el reporte quede **listo para SIREL** (la integración al canal SIREL/UIAF con
credenciales y el esquema XML vigente es trabajo de conexión aparte).

Campos de referencia (formato UIAF "Anexo ROS"): identificación del reportante, tipo de
reporte, periodo/fecha, y el detalle de operaciones con la identificación del sujeto.
"""
import datetime
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class OperacionSospechosa:
    tipo_documento: str
    numero_documento: str
    nombre: str
    tipo_persona: str        # natural | juridica
    tipo_operacion: str
    cuantia: float
    moneda: str
    senales: Tuple[str, ...]
    descripcion: str
    fecha_operacion: str


@dataclass(frozen=True)
class ReporteROS:
    tipo: str = "ROS"
    entidad_nit: str = ""
    entidad_nombre: str = ""
    periodo: str = ""                  # fecha de generación de la operación (o trimestre)
    fecha_generacion: str = ""
    operaciones: Tuple[OperacionSospechosa, ...] = ()
    nota: str = ""


@dataclass(frozen=True)
class ReporteAROS:
    tipo: str = "AROS"
    entidad_nit: str = ""
    entidad_nombre: str = ""
    trimestre: str = ""
    periodo_inicio: str = ""
    periodo_fin: str = ""
    fecha_generacion: str = ""
    certificacion_ausencia: bool = True
    nota: str = ""


def _iso(now):
    return (now or datetime.datetime.now(datetime.timezone.utc)).isoformat()


def operacion_sospechosa(contraparte, operacion, resultado, *, descripcion="", now=None):
    """Construye una OperacionSospechosa desde la contraparte y la operación detectada."""
    senales = tuple(operacion.get("senales", ()))
    return OperacionSospechosa(
        tipo_documento=contraparte.tipo_documento or "",
        numero_documento=contraparte.numero_documento or "",
        nombre=contraparte.nombre,
        tipo_persona=contraparte.tipo,
        tipo_operacion=operacion.get("tipoOperacion", "compraventa"),
        cuantia=float(operacion.get("monto", 0.0) or 0.0),
        moneda=operacion.get("moneda", "COP"),
        senales=senales,
        descripcion=descripcion or (resultado or ""),
        fecha_operacion=_iso(now),
    )


def generar_ros(entidad_nit, entidad_nombre, operaciones, *, periodo="", now=None) -> ReporteROS:
    now = now or datetime.datetime.now(datetime.timezone.utc)
    return ReporteROS(entidad_nit=entidad_nit, entidad_nombre=entidad_nombre,
                      periodo=periodo or _iso(now), fecha_generacion=_iso(now),
                      operaciones=tuple(operaciones))


def generar_aros(entidad_nit, entidad_nombre, trimestre, *,
                 inicio="", fin="", now=None) -> ReporteAROS:
    return ReporteAROS(entidad_nit=entidad_nit, entidad_nombre=entidad_nombre, trimestre=trimestre,
                       periodo_inicio=inicio, periodo_fin=fin, fecha_generacion=_iso(now))


def validar(reporte) -> Tuple[str, ...]:
    """Devuelve los campos obligatorios que faltan para que el reporte sea válido."""
    f = []
    if not reporte.entidad_nit:
        f.append("entidad_nit")
    if not reporte.entidad_nombre:
        f.append("entidad_nombre")
    if reporte.tipo == "ROS":
        if not reporte.operaciones:
            f.append("operaciones (sin operación sospechosa)")
        for i, op in enumerate(reporte.operaciones):
            if not op.nombre:
                f.append(f"operaciones[{i}].nombre")
            if not op.numero_documento:
                f.append(f"operaciones[{i}].numero_documento")
    else:
        if not reporte.trimestre:
            f.append("trimestre")
    return tuple(f)


def generar_reporte_uiaf(contraparte, operacion, res, *, entidad_nit="", entidad_nombre="",
                         trimestre="2026-T3", inicio="", fin="", now=None,
                         tipo_operacion="compraventa", descripcion="", sospechosa_confirmada=False):
    """Genera un **borrador de reporte** UIAF.

    NO clasifica automáticamente: solo produce ROS si existe una **coincidencia confirmable**
    (screening coincidencia o BF en listas) — nunca por `requiere_analisis` — y de forma
    explícita como **borrador prellenado** que requiere la validación y el envío por el
    oficial de cumplimiento. El esquema XML oficial vigente NO está integrado.
    """
    sospechosa = sospechosa_confirmada or (res.screening == "coincidencia") or res.bf_coincidencia
    if sospechosa:
        motivo = descripcion or ("Coincidencia en screening" if res.screening == "coincidencia"
                                 else "Beneficiario final en listas")
        op = operacion_sospechosa(contraparte, dict(operacion, tipoOperacion=tipo_operacion),
                                  None, descripcion=motivo, now=now)
        rep = generar_ros(entidad_nit, entidad_nombre, (op,), now=now)
        return _con_nota(rep, "BORRADOR prellenado. Requiere validación y envío por SIREL con el esquema oficial vigente (no integrado).")
    return _con_nota(generar_aros(entidad_nit, entidad_nombre, trimestre, inicio=inicio, fin=fin, now=now),
                     "BORRADOR. El AROS es una obligación periódica; verificar el universo del periodo con el oficial de cumplimiento.")


def _con_nota(rep, nota):
    import dataclasses
    return rep.__class__(**{**dataclasses.asdict(rep), "nota": nota})


def _esc(x):
    import html
    return html.escape(str(x))


def serializar_xml(reporte) -> str:
    """Exporta el reporte a XML (estructura SIREL-like, validable por el esquema vigente)."""
    if reporte.tipo == "ROS":
        sujetos = "".join(
            "<operacion>"
            f"<tipoDocumento>{_esc(op.tipo_documento)}</tipoDocumento>"
            f"<numeroDocumento>{_esc(op.numero_documento)}</numeroDocumento>"
            f"<nombre>{_esc(op.nombre)}</nombre>"
            f"<tipoPersona>{_esc(op.tipo_persona)}</tipoPersona>"
            f"<tipoOperacion>{_esc(op.tipo_operacion)}</tipoOperacion>"
            f"<cuantia>{op.cuantia}</cuantia><moneda>{_esc(op.moneda)}</moneda>"
            f"<senales>{_esc(';'.join(op.senales))}</senales>"
            f"<descripcion>{_esc(op.descripcion)}</descripcion>"
            f"<fechaOperacion>{_esc(op.fecha_operacion)}</fechaOperacion>"
            "</operacion>" for op in reporte.operaciones)
        return ('<?xml version="1.0" encoding="UTF-8"?>\n'
                f'<reporte tipo="ROS" entidadNit="{_esc(reporte.entidad_nit)}" '
                f'entidadNombre="{_esc(reporte.entidad_nombre)}" periodo="{_esc(reporte.periodo)}" '
                f'fechaGeneracion="{_esc(reporte.fecha_generacion)}"><operaciones>{sujetos}</operaciones></reporte>')
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<reporte tipo="AROS" entidadNit="{_esc(reporte.entidad_nit)}" '
            f'entidadNombre="{_esc(reporte.entidad_nombre)}" trimestre="{_esc(reporte.trimestre)}" '
            f'periodoInicio="{_esc(reporte.periodo_inicio)}" periodoFin="{_esc(reporte.periodo_fin)}" '
            f'fechaGeneracion="{_esc(reporte.fecha_generacion)}">'
            f'<certificacionAusencia>{str(reporte.certificacion_ausencia).lower()}</certificacionAusencia></reporte>')


def serializar_json(reporte) -> dict:
    if reporte.tipo == "ROS":
        return {"tipo": "ROS", "entidadNit": reporte.entidad_nit, "entidadNombre": reporte.entidad_nombre,
                "periodo": reporte.periodo, "fechaGeneracion": reporte.fecha_generacion,
                "operaciones": [{"tipoDocumento": o.tipo_documento, "numeroDocumento": o.numero_documento,
                                 "nombre": o.nombre, "tipoPersona": o.tipo_persona,
                                 "tipoOperacion": o.tipo_operacion, "cuantia": o.cuantia, "moneda": o.moneda,
                                 "senales": list(o.senales), "descripcion": o.descripcion,
                                 "fechaOperacion": o.fecha_operacion} for o in reporte.operaciones]}
    return {"tipo": "AROS", "entidadNit": reporte.entidad_nit, "entidadNombre": reporte.entidad_nombre,
            "trimestre": reporte.trimestre, "periodoInicio": reporte.periodo_inicio,
            "periodoFin": reporte.periodo_fin, "fechaGeneracion": reporte.fecha_generacion,
            "certificacionAusencia": reporte.certificacion_ausencia}

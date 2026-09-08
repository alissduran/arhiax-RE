"""Marco documental SAGRILAFT+PTEE — manual, código de ética, política y matriz de riesgo.

La Circular 100-000020 (Cap. IX) exige que el programa cuente con un **marco documental**:
manual, código de ética, política de riesgos y matriz de riesgo documental. Este módulo los
**genera como artefactos estructurados** (Markdown) parametrizados por la entidad y el régimen,
y construye la **matriz de riesgo** (factores LA/FT y PTEE -> probabilidad/impacto/control/
responsable/riesgo residual) de forma determinista y trazable.
"""
from dataclasses import dataclass
from typing import Tuple

# Catálogo versionado de factores de riesgo LA/FT y PTEE.
RIESGOS = (
    {"id": "R-LAFT-01", "categoria": "LA/FT", "factor": "Lavado de activos (origen ilícito)",
     "probabilidad": "media", "impacto": "alta", "control": "SAG-C06", "responsable": "oficial_cumplimiento"},
    {"id": "R-LAFT-02", "categoria": "LA/FT", "factor": "Financiamiento del terrorismo",
     "probabilidad": "baja", "impacto": "critica", "control": "SAG-C06", "responsable": "oficial_cumplimiento"},
    {"id": "R-LAFT-03", "categoria": "LA/FT", "factor": "Financiamiento de proliferación de armas",
     "probabilidad": "baja", "impacto": "critica", "control": "SAG-C07", "responsable": "oficial_cumplimiento"},
    {"id": "R-LAFT-04", "categoria": "LA/FT", "factor": "Pagos fraccionados o por terceros",
     "probabilidad": "media", "impacto": "media", "control": "SAG-C09", "responsable": "oficial_cumplimiento"},
    {"id": "R-LAFT-05", "categoria": "LA/FT", "factor": "Contraparte PEP o relacionada con funcionario",
     "probabilidad": "media", "impacto": "alta", "control": "SAG-C04", "responsable": "oficial_cumplimiento"},
    {"id": "R-LAFT-06", "categoria": "LA/FT", "factor": "Sector sensible (inmobiliario / construcción)",
     "probabilidad": "alta", "impacto": "media", "control": "SAG-C04", "responsable": "oficial_cumplimiento"},
    {"id": "R-PTEE-01", "categoria": "PTEE", "factor": "Soborno transnacional",
     "probabilidad": "media", "impacto": "critica", "control": "PTEE-C01..C04", "responsable": "oficial_cumplimiento"},
    {"id": "R-PTEE-02", "categoria": "PTEE", "factor": "Conflicto de interés no gestionado",
     "probabilidad": "media", "impacto": "alta", "control": "PTEE-C03", "responsable": "oficial_cumplimiento"},
    {"id": "R-PTEE-03", "categoria": "PTEE", "factor": "Uso de intermediarios / agentes",
     "probabilidad": "media", "impacto": "alta", "control": "PTEE-C02", "responsable": "oficial_cumplimiento"},
    {"id": "R-PTEE-04", "categoria": "PTEE", "factor": "Donaciones políticas o regalos excesivos",
     "probabilidad": "baja", "impacto": "media", "control": "PTEE-C03", "responsable": "oficial_cumplimiento"},
)

_PUNTOS_PROB = {"baja": 1, "media": 2, "alta": 3}
_PUNTOS_IMP = {"baja": 1, "media": 2, "alta": 3, "critica": 4}


def _nivel(prob, imp):
    s = _PUNTOS_PROB.get(prob, 1) * _PUNTOS_IMP.get(imp, 1)
    if s >= 8:
        return "alto"
    if s >= 4:
        return "medio"
    return "bajo"


def _residual(nivel):
    return {"alto": "medio", "medio": "bajo", "bajo": "bajo"}[nivel]


def matriz_riesgo(riesgos=RIESGOS):
    """Construye la matriz de riesgo (inherente -> control -> residual)."""
    out = []
    for r in riesgos:
        inherente = _nivel(r["probabilidad"], r["impacto"])
        out.append({
            "id": r["id"], "categoria": r["categoria"], "factor": r["factor"],
            "probabilidad": r["probabilidad"], "impacto": r["impacto"],
            "riesgo_inherente": inherente, "control": r["control"],
            "riesgo_residual": _residual(inherente), "responsable": r["responsable"],
        })
    return tuple(out)


@dataclass(frozen=True)
class MarcoDocumental:
    entidad_nit: str
    entidad_nombre: str
    regimen: str
    manual: str
    codigo_etica: str
    politica_riesgos: str
    matriz: Tuple[dict, ...]


def _enc(name):
    import html
    return html.escape(name or "")


def generar_manual(entidad_nombre, regimen, *, entidad_nit="", base="Circular 100-000020 (Cap. IX)") -> str:
    reg = regimen or "sujeto obligado"
    return "\n".join([
        "# Manual SAGRILAFT+PTEE",
        "",
        f"**Entidad:** {entidad_nombre} ({entidad_nit}) · **Régimen:** {reg}",
        "",
        "## 1. Objeto y alcance",
        f"Establecer el programa de cumplimiento SAGRILAFT+PTEE (LA/FT y soborno) de {entidad_nombre}, "
        f"en los términos de la {base}, aplicable a socios, administradores, empleados, "
        "contrapartes, intermediarios y terceros vinculados.",
        "",
        "## 2. Gobierno",
        "La junta/administrador aprueba el programa. El **representante legal** y el **oficial de "
        "cumplimiento** son responsables de su implementación y monitoreo. Los controles C01–C12 "
        "(LA/FT) y PTEE-C01..C04 (soborno) son gestionados por el oficial de cumplimiento.",
        "",
        "## 3. Debida diligencia de contrapartes",
        "Identificación (8 campos, 9.15.1), beneficiario final (≥5%, regla subsidiaria), screening "
        "multifuente, matriz de riesgo por perfil y calendario de DD por perfil.",
        "",
        "## 4. Detección y reporte",
        "Señales (9.20) y detección de operaciones inusuales (9.19). El ROS se reporta por SIREL; "
        "si no hay operaciones sospechosas, se presenta el AROS del trimestre.",
        "",
        "## 5. Evidencia y trazabilidad",
        "Cada evento nace con quién/fecha/hora y `hmacChain` (9.22). El expediente y el dictamen "
        "son re-re-producciones del log de evidencia.",
        "",
        "## 6. Canal de denuncias y sanciones",
        "Canal interno anónimo (9.21.4). El incumplimiento acarrea sanciones disciplinarias y "
        "contractuales, sin perjuicio de las legales.",
    ])


def generar_codigo_etica(entidad_nombre) -> str:
    return "\n".join([
        "# Código de Ética",
        "",
        f"**Entidad:** {entidad_nombre}",
        "",
        "1. **Legalidad:** cumplir la ley y las políticas de la entidad.",
        "2. **Integridad:** no ofrecer, prometer ni recibir sobornos o ventajas indebidas.",
        "3. **Conflicto de interés:** declarar y evitar toda situación que comprometa la objetividad.",
        "4. **Debida diligencia:** conocer la identidad y origen de fondos de contrapartes.",
        "5. **Confidencialidad:** proteger la información de la entidad y de terceros.",
        "6. **Canal de denuncias:** reportar conductas ilícitas o sospechosas de buena fe.",
        "",
        "La violación de este código se sanciona sin perjuicio de las responsabilidades legales.",
    ])


def generar_politica_riesgos(entidad_nombre) -> str:
    return "\n".join([
        "# Política de Riesgos (LA/FT y Soborno)",
        "",
        f"**Entidad:** {entidad_nombre}",
        "",
        "**Apetito de riesgo:** bajo. La entidad no acepta operar con contrapartes no identificadas, "
        "con señales de LA/FT o de soborno sin la debida diligencia ampliada.",
        "",
        "**Gestión:** identificación -> evaluación (probabilidad × impacto) -> control -> monitoreo. "
        "Los riesgos se clasifican por perfil (alto/medio/bajo) con intensidad de DD proporcional.",
        "",
        "**Roles:** el oficial de cumplimiento evalúa y controla; la alta gerencia aprueba y responde "
        "por la implementación.",
    ])


def generar_marco_documental(entidad_nombre, regimen, *, entidad_nit="") -> MarcoDocumental:
    return MarcoDocumental(
        entidad_nit=entidad_nit, entidad_nombre=entidad_nombre, regimen=regimen,
        manual=generar_manual(entidad_nombre, regimen, entidad_nit=entidad_nit),
        codigo_etica=generar_codigo_etica(entidad_nombre),
        politica_riesgos=generar_politica_riesgos(entidad_nombre),
        matriz=matriz_riesgo(),
    )

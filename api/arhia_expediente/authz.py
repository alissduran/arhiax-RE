"""RBAC / ABAC — modelo de autorización del expediente (seguridad, auditoría).

RBAC: roles con permisos (quién puede qué). ABAC: decisiones por **atributos** del sujeto,
del recurso y del contexto (qué dato, con qué clasificación, para qué fin). Es el modelo de
política que la capa de acceso del producto debe adoptar; en el demo la API es localhost-only
(no autenticada, P0-6) y aquí se entrega **el motor de políticas** testeable.

Roles (RBAC):
  - ``oficial_cumplimiento``   : expediente completo + compliance + ruta a UIAF.
  - ``abogado`` / ``avaluador`` : lectura del caso y ejercicio de autoría sobre su dominio.
  - ``analista``               : lectura des-identificada / agregada.
  - ``ciudadano``               : solo su propio expediente (dato propio).
"""
from dataclasses import dataclass, field
from typing import Optional, Tuple

# Permisos por rol (RBAC).
_ROLES = {
    "oficial_cumplimiento": {"leer", "leer_sensible", "gestionar_caso", "rutear_uiaf"},
    "abogado": {"leer", "leer_sensible", "autorizar_hallazgo", "firmar_conclusion"},
    "avaluador": {"leer", "leer_sensible", "firmar_avaluo"},
    "analista": {"leer"},
    "ciudadano": {"leer_propio"},
}

# Atributos que exigen permiso elevado (ABAC) sobre recursos sensibles.
_SENSIBLES = ("beneficiario_final", "datos_personales", "screening", "documento_identidad")


@dataclass(frozen=True)
class Sujeto:
    id: str
    rol: str


@dataclass(frozen=True)
class Recurso:
    tipo: str               # expediente | hallazgo | conclusion | reporte
    id: str
    clasificacion: str = ""  # "" | sensible
    titular: str = ""        # id del titular (para acceso ciudadano)


@dataclass(frozen=True)
class Contexto:
    proposito: str = "consulta"
    exige_rol_elevado: bool = False


@dataclass
class Decision:
    permitido: bool
    motivo: str
    reglas_aplicadas: Tuple[str, ...] = field(default_factory=tuple)


def _clasificacion_sensible(recurso: Recurso) -> bool:
    return recurso.clasificacion == "sensible" or recurso.tipo in ("beneficiario_final", "screening")


def evaluar(sujeto: Sujeto, recurso: Recurso, accion: str, contexto: Optional[Contexto] = None) -> Decision:
    """Decide si el ``sujeto`` puede hacer ``accion`` sobre ``recurso`` (RBAC + ABAC)."""
    contexto = contexto or Contexto()
    reglas = []
    permisos = _ROLES.get(sujeto.rol, set())
    # RBAC: el rol no tiene el permiso -> denegado.
    if accion not in permisos:
        return Decision(False, "El rol '" + sujeto.rol + "' no tiene el permiso '" + accion + "'.", ("rbac",))
    reglas.append("rbac")
    # ABAC: dato sensible exige permiso elevado.
    if _clasificacion_sensible(recurso) and "leer_sensible" not in permisos and accion != "leer_propio":
        return Decision(False, "Recurso sensible (datos personales/beneficiario final) exige rol con acceso sensible.",
                        tuple(reglas + ["abac_sensible"]))
    reglas.append("abac_sensible")
    # ABAC: ciudadano solo sobre su propio expediente.
    if sujeto.rol == "ciudadano" and accion == "leer_propio":
        if recurso.titular and recurso.titular != sujeto.id:
            return Decision(False, "El ciudadano solo puede acceder a su propio expediente.", tuple(reglas + ["abac_titular"]))
        reglas.append("abac_titular")
    return Decision(True, "Acceso concedido.", tuple(reglas))

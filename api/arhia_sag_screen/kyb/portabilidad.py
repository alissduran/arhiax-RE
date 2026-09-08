"""Portabilidad institucional — PF-017 (expediente portable / sala de datos).

Empaqueta el expediente de confianza en un **paquete portable** para banco / fiduciaria /
aseguradora: campos reutilizables (+% reutilizable, gate PD-010 ≥60%), evidencia con procedencia
(hashes/hmacChain), **consentimiento** del ciudadano, **permisos** del receptor y un **aviso** de
que el receptor debe revalidar (no se promete aprobación ni cobertura).

XN-5 (F-D): el **consentimiento** no es un dato plan: es un **evento auditado** (quién, qué, cuándo,
base jurídica, alcance, huella). Se captura con `registrar_consentimiento` y queda en el paquete.
"""
import datetime
from dataclasses import dataclass
from typing import Optional, Tuple

from arhia_expediente.expediente import Expediente, FichaIntegridad
from arhia_expediente.conclusion import Conclusion
from arhia_sag_screen.kyb.uso_suelo import FichaUsoSuelo
from arhia_sag_screen.evidence.envelope import build_event


@dataclass(frozen=True)
class Consentimiento:
    quien: str
    que_autoriza: str
    cuando: str
    base_juridica: str
    alcance: str
    evento: dict  # envelope firmado (B18)


@dataclass(frozen=True)
class PaquetePortable:
    receptor: str
    entidad_nit: str
    entidad_nombre: str
    campos_reutilizables: Tuple[dict, ...]
    evidencia_procedencia: Tuple[dict, ...]
    consentimiento: bool
    permisos: Tuple[str, ...]
    pct_reutilizable: float
    aviso: str
    consentimiento_evento: Optional[dict] = None


def registrar_consentimiento(quien: str, que_autoriza: str, *,
                             base_juridica: str = "Ley 1581/2012 (protección de datos)",
                             alcance: str = "transferencia de evidencia del expediente",
                             ahora=None, hmac_key=None) -> Consentimiento:
    """Registra el consentimiento como evento auditado (quién, qué, cuándo, base jurídica, alcance)."""
    now = ahora or datetime.datetime.now(datetime.timezone.utc)
    payload = {"quien": quien, "que_autoriza": que_autoriza, "baseJuridica": base_juridica,
               "alcance": alcance}
    env = build_event("DAT-C01", "CONSENTIMIENTO_REGISTRADO", quien, payload, now=now,
                      at_type="CONSENT", retention_tier="Tier2", hmac_key=hmac_key)
    return Consentimiento(quien, que_autoriza, env["timestamp"], base_juridica, alcance, env)


def _campo(clave, valor, fuente, reutilizable=True):
    return {"campo": clave, "valor": str(valor), "fuente": fuente, "reutilizable": reutilizable}


def generar_paquete_portable(expediente: Expediente, integridad: FichaIntegridad,
                             conclusion: Conclusion, rub_reporte=(),
                             ficha_uso_suelo=None, *,
                             consentimiento: Optional[Consentimiento] = None,
                             entidad_nit="", entidad_nombre="", receptor="banco"):
    """Construye el paquete portable institucional (PF-017)."""
    campos = [
        _campo("Folio de matrícula", getattr(expediente, "id", ""), "expediente"),
        _campo("Régimen", integridad.regimen, "SAGRILAFT/PTEE"),
        _campo("Screening (agregado)", integridad.screening, "listas vinculantes"),
        _campo("Perfil de riesgo", integridad.perfil, "matriz"),
        _campo("Beneficiario final", integridad.beneficiario_final or "", "RUB"),
    ]
    # Coherencia precio–avalúo–predio (PF-012) como campo reutilizable
    val = next((h for h in expediente.hallazgos if h.regla == "VAL_B01"), None)
    if val:
        campos.append(_campo("Coherencia precio–avalúo", val.estado, "valoración"))
    # Uso de suelo / POT
    if ficha_uso_suelo and ficha_uso_suelo.zona != "no_mapeado":
        campos.append(_campo("Zona POT", ficha_uso_suelo.zona, "ordenamiento territorial"))
        campos.append(_campo("Actividad consultada", ficha_uso_suelo.actividad_resultado, "POT"))
    # RUB beneficiarios
    for r in rub_reporte:
        campos.append(_campo("Beneficiario final (RUB)", r.get("nombre"), "RUB"))
    # Procedencia de la evidencia
    proc = [{"tipo": "evento", "controlId": e.get("controlId"), "eventType": e.get("eventType"),
             "hmacChain": bool(e.get("hmacChain"))} for e in integridad.eventos]
    if not proc:
        proc = [{"tipo": "hallazgo", "id": h.id, "estado": h.estado, "responsable": h.responsable}
                for h in expediente.hallazgos]
    reutil = [c for c in campos if c["reutilizable"]]
    pct = round(100 * len(reutil) / max(len(campos), 1), 1)
    aviso = ("Paquete portable de evidencia. NO garantiza aprobación de crédito ni cobertura de seguro; "
             "el receptor debe revalidar los campos frente a sus políticas (derecho a revalidar).")

    return PaquetePortable(receptor=receptor, entidad_nit=entidad_nit, entidad_nombre=entidad_nombre,
                           campos_reutilizables=tuple(campos), evidencia_procedencia=tuple(proc),
                           consentimiento=bool(consentimiento), permisos=("lectura_usuario_autorizado", receptor),
                           pct_reutilizable=pct, aviso=aviso,
                           consentimiento_evento=consentimiento.evento if consentimiento else None)

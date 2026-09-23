# -*- coding: utf-8 -*-
"""Gate de release SAGRILAFT — versión mínima del núcleo sancionado (punto #10).

REGLA
-----
Un dictamen generado con un núcleo de screening ANTERIOR al mínimo sancionado no
puede salir como si estuviera vigente: debe llevar la marca **LEGACY /
INVALID_FOR_RELEASE** o la generación debe bloquearse.

QUÉ ES EL «NÚCLEO SAGRILAFT SANCIONADO»
---------------------------------------
No es la versión de la plataforma (1.4.0), sino el conjunto de versiones que
determinan QUÉ se consultó y CÓMO se comparó:

  · motor de screening   · sanctions-matcher/1.1.0
  · modelo de sujetos    · canonical-subjects/1.0.0
  · parsers por fuente   · onu_xml/ofac_sdn_xml/uk_sanctions_list (>= 1.1.0)
  · fuentes cubiertas    · UN_CONSOLIDATED, OFAC_SDN, UK_SANCTIONS_LIST

La comparación es de VERSIONES (constantes que viajan en el bundle), no de fechas ni
de commits: en Vercel el `.git` puede no existir y una comprobación por commit
fallaría en silencio. Cuando el repositorio SÍ está disponible (local/CI), además se
verifica que el commit actual descienda del commit que estableció el núcleo, y el
resultado viaja en `ancestria` con estado `VERIFIED` / `NOT_ANCESTOR` / `UNKNOWN`.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── Núcleo sancionado (mínimos) ────────────────────────────────────────────────
SAGRILAFT_CORE_MIN = {
    "matcher": "sanctions-matcher/1.1.0",
    "subject_model": "canonical-subjects/1.0.0",
    "parsers": {
        "onu_xml": "1.1.0",
        "ofac_sdn_xml": "1.1.0",
        "uk_sanctions_list_xml": "1.1.0",
    },
    "sources": ("UN_CONSOLIDATED", "OFAC_SDN", "UK_SANCTIONS_LIST"),
}

# Commit que estableció el núcleo (03S.1C). Solo se usa cuando hay repositorio.
SAGRILAFT_CORE_COMMIT = "acc8a9493a1cfe9dace5d638fb3bf9a0a74cf29f"

STATUS_VALID = "VALID_FOR_RELEASE"
STATUS_LEGACY = "LEGACY_INVALID_FOR_RELEASE"
STATUS_GATE_FAILED = "GATE_EVALUATION_FAILED"

EVAL_OK = "EVALUATED"
EVAL_FAILED = "EVALUATION_FAILED"

MARCA_LEGACY = "LEGACY / INVALID_FOR_RELEASE"
MARCA_GATE_NO_EVALUABLE = "RELEASE GATE NOT EVALUABLE / INVALID_FOR_RELEASE"

# ── Política de liberación por ENTORNO (03I.2A) ───────────────────────────────
# La política ya NO es global: depende de `ARHIAX_ENV` y vive en `release_env`
# (módulo sin dependencias, para que la última línea de defensa esté siempre
# disponible). Resumen: DEV/TEST marcan, STAGING/PRODUCTION bloquean.
try:
    from release_env import (  # type: ignore
        ENTORNO_CONSERVADOR, ENV_DEVELOPMENT, ENV_PRODUCTION, ENV_STAGING, ENV_TEST,
        ENTORNOS, OVERRIDE_VAR, OVERRIDE_VAR_LEGACY, POLICY_BLOCK, POLICY_MARK,
        POLITICA_POR_ENTORNO, matriz_legible, normalizar_entorno, override_activo,
        politica_para,
    )
except ImportError:  # pragma: no cover — api/ no está en sys.path (import como paquete)
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
    from release_env import (  # type: ignore
        ENTORNO_CONSERVADOR, ENV_DEVELOPMENT, ENV_PRODUCTION, ENV_STAGING, ENV_TEST,
        ENTORNOS, OVERRIDE_VAR, OVERRIDE_VAR_LEGACY, POLICY_BLOCK, POLICY_MARK,
        POLITICA_POR_ENTORNO, matriz_legible, normalizar_entorno, override_activo,
        politica_para,
    )

__all__ = [
    "SAGRILAFT_CORE_MIN", "SAGRILAFT_CORE_COMMIT", "STATUS_VALID", "STATUS_LEGACY",
    "STATUS_GATE_FAILED", "EVAL_OK", "EVAL_FAILED", "MARCA_LEGACY",
    "MARCA_GATE_NO_EVALUABLE", "POLITICA_POR_ENTORNO", "normalizar_entorno",
    "politica_para", "override_activo", "evaluar_nucleo", "evaluar_release_seguro",
    "validate_release_decision", "filas_release_gate", "filas_receipt_liberacion",
    "matriz_legible",
]


@dataclass
class NúcleoVigente:
    """Versiones que el código en ejecución declara."""

    matcher: Optional[str] = None
    subject_model: Optional[str] = None
    parsers: Dict[str, str] = field(default_factory=dict)
    sources: Tuple[str, ...] = ()
    commit: Optional[str] = None


def nucleo_vigente() -> NúcleoVigente:
    """Lee las versiones REALES del código en ejecución (sin inventar ninguna)."""
    nu = NúcleoVigente()
    try:
        from sanctions.matching import ALGORITHM_VERSION
        nu.matcher = ALGORITHM_VERSION
    except Exception:  # noqa: BLE001
        nu.matcher = None
    try:
        from sanctions.subjects import SUBJECT_MODEL_VERSION
        nu.subject_model = SUBJECT_MODEL_VERSION
    except Exception:  # noqa: BLE001
        nu.subject_model = None
    try:
        from sanctions.parsers import PARSER_VERSIONS
        nu.parsers = dict(PARSER_VERSIONS or {})
    except Exception:  # noqa: BLE001
        nu.parsers = {}
    try:
        from sanctions.registry import CORE_SOURCE_IDS
        nu.sources = tuple(sorted(CORE_SOURCE_IDS))
    except Exception:  # noqa: BLE001
        nu.sources = ()
    try:
        from versioning import git_commit_sha
        nu.commit = git_commit_sha() or None
    except Exception:  # noqa: BLE001
        nu.commit = None
    return nu


def _parse_ver(v: Optional[str]) -> Tuple[int, ...]:
    """'sanctions-matcher/1.1.0' -> (1, 1, 0). Sin versión legible -> ()."""
    if not v:
        return ()
    txt = str(v).split("/")[-1]
    partes: List[int] = []
    for trozo in txt.replace("-", ".").split("."):
        if trozo.isdigit():
            partes.append(int(trozo))
        else:
            break
    return tuple(partes)


def _menor(actual: Optional[str], minimo: str) -> bool:
    a, b = _parse_ver(actual), _parse_ver(minimo)
    if not a:
        return True          # sin versión legible = no acredita el mínimo
    return a < b


def ancestria_del_nucleo(commit: Optional[str] = None) -> Dict[str, Any]:
    """¿El commit actual desciende del commit que estableció el núcleo?

    Devuelve {'estado': 'VERIFIED'|'NOT_ANCESTOR'|'UNKNOWN', 'detalle': str}.
    """
    commit = commit or (nucleo_vigente().commit)
    repo = Path(__file__).resolve().parent.parent.parent
    if not commit:
        return {"estado": "UNKNOWN", "detalle": "sin SHA de git en el entorno"}
    if not (repo / ".git").exists():
        return {"estado": "UNKNOWN",
                "detalle": "sin repositorio git (bundle de producción): se decide por versiones"}
    try:
        r = subprocess.run(
            ["git", "merge-base", "--is-ancestor", SAGRILAFT_CORE_COMMIT, commit],
            cwd=str(repo), capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            return {"estado": "VERIFIED",
                    "detalle": f"{commit[:8]} desciende de {SAGRILAFT_CORE_COMMIT[:8]}"}
        return {"estado": "NOT_ANCESTOR",
                "detalle": f"{commit[:8]} NO desciende de {SAGRILAFT_CORE_COMMIT[:8]}"}
    except Exception as e:  # noqa: BLE001
        return {"estado": "UNKNOWN", "detalle": f"git no disponible: {str(e)[:80]}"}


def evaluar_nucleo(permitir_legacy: Optional[bool] = None) -> Dict[str, Any]:
    """Evalúa si el dictamen puede emitirse como VIGENTE.

    Returns:
        {
          "status": VALID_FOR_RELEASE | LEGACY_INVALID_FOR_RELEASE,
          "marca": None | "LEGACY / INVALID_FOR_RELEASE",
          "motivos": [...],
          "minimos": {...}, "vigente": {...}, "ancestria": {...},
          "bloquear": bool,
        }
    """
    nu = nucleo_vigente()
    motivos: List[str] = []

    if _menor(nu.matcher, SAGRILAFT_CORE_MIN["matcher"]):
        motivos.append(f"motor de screening {nu.matcher!r} < mínimo "
                       f"{SAGRILAFT_CORE_MIN['matcher']!r}")
    if _menor(nu.subject_model, SAGRILAFT_CORE_MIN["subject_model"]):
        motivos.append(f"modelo de sujetos {nu.subject_model!r} < mínimo "
                       f"{SAGRILAFT_CORE_MIN['subject_model']!r}")
    for fuente, minimo in SAGRILAFT_CORE_MIN["parsers"].items():
        actual = nu.parsers.get(fuente)
        if _menor(actual, minimo):
            motivos.append(f"parser {fuente} {actual!r} < mínimo {minimo!r}")
    faltantes = [s for s in SAGRILAFT_CORE_MIN["sources"] if s not in (nu.sources or ())]
    if faltantes:
        motivos.append(f"fuentes del núcleo ausentes: {', '.join(faltantes)}")

    anc = ancestria_del_nucleo(nu.commit)
    if anc["estado"] == "NOT_ANCESTOR":
        motivos.append(f"el commit en ejecución no desciende del núcleo sancionado ({anc['detalle']})")

    legacy = bool(motivos)
    if permitir_legacy is None:
        # Compatibilidad: sin argumento se aplica la política del ENTORNO
        # (DEV/TEST marcan; STAGING/PRODUCTION bloquean). El camino del dictamen NO
        # usa esto: usa `evaluar_release_seguro()`, que es el único autorizado.
        permitir_legacy = politica_para(normalizar_entorno()["environment"]) == POLICY_MARK

    return {
        "status": STATUS_LEGACY if legacy else STATUS_VALID,
        "marca": MARCA_LEGACY if legacy else None,
        "motivos": motivos,
        "minimos": SAGRILAFT_CORE_MIN,
        "vigente": {"matcher": nu.matcher, "subject_model": nu.subject_model,
                    "parsers": nu.parsers, "sources": list(nu.sources),
                    "commit": nu.commit},
        "ancestria": anc,
        "bloquear": bool(legacy and not permitir_legacy),
    }


def evaluar_release_seguro(*, permitir_legacy=None, entorno: Optional[str] = None,
                           evaluador=None) -> Dict[str, Any]:
    """ÚNICA función autorizada para decidir la liberación de un dictamen (03I.2A).

    Nunca lanza y nunca devuelve None: si la evaluación del núcleo falla, devuelve
    `EVALUATION_FAILED` / `GATE_EVALUATION_FAILED` con el motivo saneado y aplica la
    política del entorno. Un fallo interno del gate JAMÁS puede producir un PDF
    vigente.

    Returns:
        {
          evaluation_status: EVALUATED | EVALUATION_FAILED,
          release_status: VALID_FOR_RELEASE | LEGACY_INVALID_FOR_RELEASE |
                          GATE_EVALUATION_FAILED,
          policy: MARK | BLOCK,
          environment, environment_declared, environment_raw, assumed_conservative,
          blocking: bool, mark: bool, marca: str|None,
          override_used: bool, override_variable: str|None, override_deprecated: bool,
          reasons: [...], core_versions: {...}, ancestry: {...},
        }
    """
    env = normalizar_entorno(entorno)
    _eval = evaluador or evaluar_nucleo

    core: Dict[str, Any] = {}
    ancestry: Dict[str, Any] = {"estado": "UNKNOWN", "detalle": "no evaluable"}
    reasons: List[str] = []
    try:
        base = _eval(permitir_legacy=True) or {}
        evaluation_status = EVAL_OK
        release_status = base.get("status") or STATUS_GATE_FAILED
        if release_status not in (STATUS_VALID, STATUS_LEGACY):
            evaluation_status = EVAL_FAILED
            release_status = STATUS_GATE_FAILED
            reasons.append(f"estado de núcleo no reconocido: {base.get('status')!r}")
        reasons.extend(base.get("motivos") or [])
        core = base.get("vigente") or {}
        ancestry = base.get("ancestria") or ancestry
    except Exception as e:  # noqa: BLE001 — fail-closed: nunca se propaga, nunca es válido
        evaluation_status = EVAL_FAILED
        release_status = STATUS_GATE_FAILED
        reasons = [_sanitizar_motivo(e)]
        core, ancestry = {}, {"estado": "UNKNOWN", "detalle": "evaluación fallida"}

    policy = politica_para(env["environment"])
    override = {"activo": False, "variable": None, "deprecada": False}
    if release_status != STATUS_VALID and policy == POLICY_BLOCK:
        if permitir_legacy is False:
            policy = POLICY_BLOCK                     # forzado explícitamente
        else:
            override = override_activo()
            if override["activo"]:
                policy = POLICY_MARK                  # excepcional y registrado

    blocking = (release_status != STATUS_VALID) and (policy == POLICY_BLOCK)
    mark = release_status != STATUS_VALID
    marca = (MARCA_GATE_NO_EVALUABLE if release_status == STATUS_GATE_FAILED
             else (MARCA_LEGACY if release_status == STATUS_LEGACY else None))

    return {
        "evaluation_status": evaluation_status,
        "release_status": release_status,
        "policy": policy,
        "environment": env["environment"],
        "environment_declared": env["declared"],
        "environment_raw": env["raw"],
        "assumed_conservative": env["assumed_conservative"],
        "blocking": blocking,
        "mark": mark,
        "marca": marca,
        "override_used": bool(override["activo"] and policy == POLICY_MARK
                              and release_status != STATUS_VALID),
        "override_variable": override["variable"] if override["activo"] else None,
        "override_deprecated": bool(override.get("deprecada")),
        "reasons": reasons,
        "core_versions": core,
        "ancestry": ancestry,
    }


def _sanitizar_motivo(exc: BaseException) -> str:
    """Motivo legible y saneado de la excepción (sin rutas ni secretos)."""
    nombre = type(exc).__name__
    texto = str(exc) or ""
    texto = texto.replace("\\", "/").split("/")[-1]     # nunca rutas completas
    return f"evaluación del núcleo fallida: {nombre}: {texto[:160]}"


# ── Validación del CONTRATO de decisión (03I.2B · R1) ─────────────────────────
# El wrapper ya maneja excepciones; lo que faltaba era defenderse de un contrato
# MALFORMADO que NO lanza: `{}`, `None`, un string, o un dict al que le faltan campos
# (p. ej. `{"release_status": "VALID_FOR_RELEASE"}`). Sin esta validación, un contrato
# incompleto podía leerse como «no bloqueante» = fail-open.

CONTRATO_CAMPOS = ("evaluation_status", "release_status", "policy", "blocking", "mark",
                   "environment", "reasons")


def validate_release_decision(result: Any = None, *, entorno: Optional[str] = None,
                              permitir_legacy=None) -> Dict[str, Any]:
    """Valida y normaliza el contrato del gate. NUNCA asume válido lo inválido.

    Cualquier violación se convierte en un fallo EXPLÍCITO (`EVALUATION_FAILED` /
    `GATE_EVALUATION_FAILED`, `mark=True`) y se aplica la política del entorno: MARK en
    development/test, BLOCK en staging/production (entorno ausente o desconocido ⇒
    production conservador).

    Returns:
        El contrato normalizado + `contract_valid` (bool) + `contract_problems` (lista).
    """
    problemas: List[str] = []

    if not isinstance(result, dict):
        problemas.append(f"el contrato no es un dict: {type(result).__name__}")
        base: Dict[str, Any] = {}
    else:
        base = dict(result)
        for campo in CONTRATO_CAMPOS:
            if campo not in base:
                problemas.append(f"campo obligatorio ausente: {campo}")

        _eval_st = base.get("evaluation_status")
        if _eval_st not in (EVAL_OK, EVAL_FAILED):
            problemas.append(f"evaluation_status inválido: {_eval_st!r}")
        _rel_st = base.get("release_status")
        if _rel_st not in (STATUS_VALID, STATUS_LEGACY, STATUS_GATE_FAILED):
            problemas.append(f"release_status inválido: {_rel_st!r}")
        _pol = base.get("policy")
        if _pol not in (POLICY_MARK, POLICY_BLOCK):
            problemas.append(f"policy inválida: {_pol!r}")
        for campo in ("blocking", "mark"):
            if campo in base and not isinstance(base.get(campo), bool):
                problemas.append(f"{campo} no es bool: {base.get(campo)!r}")
        if base.get("environment") in (None, ""):
            problemas.append("environment ausente o vacío")
        _reasons = base.get("reasons")
        if _reasons is not None and not isinstance(_reasons, (list, tuple)):
            problemas.append(f"reasons no es lista/tupla: {type(_reasons).__name__}")
        # Coherencia interna: VALID_FOR_RELEASE exige evaluación OK, sin bloqueo, sin marca.
        if _rel_st == STATUS_VALID:
            if _eval_st != EVAL_OK:
                problemas.append("VALID_FOR_RELEASE con evaluation_status != EVALUATED")
            if base.get("blocking") is not False:
                problemas.append("VALID_FOR_RELEASE con blocking != False")
            if base.get("mark") is not False:
                problemas.append("VALID_FOR_RELEASE con mark != False")

    if not problemas:
        base["reasons"] = list(base.get("reasons") or [])
        base["contract_valid"] = True
        base["contract_problems"] = []
        return base

    # ── Contrato inválido: fallo explícito + política del entorno ─────────────
    env = normalizar_entorno(entorno)
    policy = politica_para(env["environment"])
    override = {"activo": False, "variable": None, "deprecada": False}
    if policy == POLICY_BLOCK and permitir_legacy is not False:
        override = override_activo()
        if override["activo"]:
            policy = POLICY_MARK
    return {
        "evaluation_status": EVAL_FAILED,
        "release_status": STATUS_GATE_FAILED,
        "policy": policy,
        "environment": env["environment"],
        "environment_declared": env["declared"],
        "environment_raw": env["raw"],
        "assumed_conservative": env["assumed_conservative"],
        "blocking": policy == POLICY_BLOCK,
        "mark": True,
        "marca": MARCA_GATE_NO_EVALUABLE,
        "override_used": bool(override["activo"] and policy == POLICY_MARK),
        "override_variable": override["variable"] if override["activo"] else None,
        "override_deprecated": bool(override.get("deprecada")),
        "reasons": ["contrato de liberación INVÁLIDO: " + "; ".join(problemas)],
        "core_versions": base.get("core_versions") or {},
        "ancestry": base.get("ancestry") or {"estado": "UNKNOWN",
                                            "detalle": "contrato inválido"},
        "contract_valid": False,
        "contract_problems": problemas,
    }


def filas_release_gate(evaluacion: Optional[Dict[str, Any]] = None) -> List[Tuple[str, str]]:
    """Filas legibles para el capítulo 16.B (traza técnica)."""
    ev = evaluacion or evaluar_release_seguro()
    vig = ev.get("core_versions") or ev.get("vigente") or {}
    filas = [
        ("Núcleo Sagrilaft", ev.get("marca") or "VIGENTE · núcleo sancionado"),
        ("Motor de screening", str(vig.get("matcher") or "no declarado")),
        ("Modelo de sujetos", str(vig.get("subject_model") or "no declarado")),
        ("Parsers", " · ".join(f"{k} {v}" for k, v in sorted((vig.get("parsers") or {}).items()))
         or "no declarados"),
        ("Fuentes del núcleo", " · ".join(vig.get("sources") or []) or "no declaradas"),
        ("Ancestría del núcleo", f"{(ev.get('ancestry') or ev.get('ancestria') or {}).get('estado')} · "
         f"{(ev.get('ancestry') or ev.get('ancestria') or {}).get('detalle')}"),
    ]
    if ev.get("reasons") or ev.get("motivos"):
        filas.append(("Motivos de la marca", "; ".join(ev.get("reasons") or ev["motivos"])))
    return filas


def filas_receipt_liberacion(evaluacion: Dict[str, Any]) -> List[Tuple[str, str]]:
    """Receipt de liberación (03I.2A §12): todo lo que decide el gate, sin secretos.

    No se registran variables de entorno completas ni credenciales: solo el NOMBRE de
    la variable de override y su uso.
    """
    ev = evaluacion or {}
    vig = ev.get("core_versions") or {}
    anc = ev.get("ancestry") or {}
    return [
        # Nombres EXACTOS exigidos por el release gate (03I.2A §12).
        ("release_gate_evaluation_status", str(ev.get("evaluation_status") or "—")),
        ("release_gate_status", str(ev.get("release_status") or "—")),
        ("release_gate_policy", str(ev.get("policy") or "—")),
        ("environment", f"{ev.get('environment')}"
                        + ("" if ev.get("environment_declared") else
                           f" (asumido conservador; ARHIAX_ENV={ev.get('environment_raw')!r})")),
        ("blocking", str(bool(ev.get("blocking")))),
        ("override_used", str(bool(ev.get("override_used")))
         + (f" · variable {ev.get('override_variable')}" if ev.get("override_used") else "")),
        ("reasons", "; ".join(ev.get("reasons") or []) or "sin motivos"),
        ("matcher_version", str(vig.get("matcher") or "—")),
        ("subject_model_version", str(vig.get("subject_model") or "—")),
        ("parser_versions", " · ".join(f"{k}={v}" for k, v in sorted((vig.get("parsers") or {}).items()))
         or "—"),
        ("sources", " · ".join(vig.get("sources") or []) or "—"),
        ("ancestry", f"{anc.get('estado')} · {anc.get('detalle')}"),
        # 03I.2B §N: procedencia de la DECISIÓN del gate (no solo del núcleo).
        # Un contrato inválido queda registrado como tal en el recibo: nunca se
        # imprime un recibo que oculte que la decisión no era verificable.
        ("release_gate_contract_valid",
         "True" if ev.get("contract_valid") is True
         else ("False" if ev.get("contract_valid") is False else "no declarado")),
        ("release_gate_contract_problems",
         "; ".join(ev.get("contract_problems") or []) or "ninguno"),
    ]

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

MARCA_LEGACY = "LEGACY / INVALID_FOR_RELEASE"


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
        permitir_legacy = os.environ.get("ARHIAX_PERMITIR_LEGACY", "1") == "1"

    return {
        "status": STATUS_LEGACY if legacy else STATUS_VALID,
        "marca": MARCA_LEGACY if legacy else None,
        "motivos": motivos,
        "minimos": SAGRILAFT_CORE_MIN,
        "vigente": {"matcher": nu.matcher, "subject_model": nu.subject_model,
                    "parsers": nu.parsers, "sources": list(nu.sources),
                    "commit": nu.commit},
        "ancestria": anc,
        # Por defecto el PDF se emite MARCADO (no se bloquea): el negocio necesita el
        # documento, y la marca impide que circule como vigente. Con
        # ARHIAX_PERMITIR_LEGACY=0 la generación se bloquea.
        "bloquear": bool(legacy and not permitir_legacy),
    }


def filas_release_gate(evaluacion: Optional[Dict[str, Any]] = None) -> List[Tuple[str, str]]:
    """Filas legibles para el capítulo 16.B (traza técnica)."""
    ev = evaluacion or evaluar_nucleo()
    vig = ev.get("vigente") or {}
    filas = [
        ("Núcleo Sagrilaft", ev.get("marca") or "VIGENTE · núcleo sancionado"),
        ("Motor de screening", str(vig.get("matcher") or "no declarado")),
        ("Modelo de sujetos", str(vig.get("subject_model") or "no declarado")),
        ("Parsers", " · ".join(f"{k} {v}" for k, v in sorted((vig.get("parsers") or {}).items()))
         or "no declarados"),
        ("Fuentes del núcleo", " · ".join(vig.get("sources") or []) or "no declaradas"),
        ("Ancestría del núcleo", f"{(ev.get('ancestria') or {}).get('estado')} · "
                                 f"{(ev.get('ancestria') or {}).get('detalle')}"),
    ]
    if ev.get("motivos"):
        filas.append(("Motivos de marca LEGACY", "; ".join(ev["motivos"])))
    return filas

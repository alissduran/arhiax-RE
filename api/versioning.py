# -*- coding: utf-8 -*-
"""
ARHIAX RE — Versionado de plataforma (single source of truth).

Cada capa de la plataforma declara su versión para poder auditar, en el propio
dictamen o vía API, QUÉ código produjo un resultado. Esto corta de raíz la
disputa "¿llegó o no llegó el arreglo a producción?".

Versiones (se incrementan a mano en cada release; nunca se deducen de nada):

  * ARHIAX_RE_VERSION      — versión de la plataforma (shell + API).
  * DICTUS_ENGINE_VERSION  — motor del dictamen (compile_pdf / dictamen_data).
  * GIS_ADAPTER_VERSION    — adapters GIS por ciudad (territorio, pasto, riesgo).
  * TITULUX_VERSION        — puente/pre-dictamen Titulux + screening SAGRILAFT.
  * RULESET_VERSION        — reglas de identidad/valoración/consistencia.

El SHA de git se resuelve en este orden (robusto en Vercel, donde .git puede no
existir en el bundle de la función):
  1) $VERCEL_GIT_COMMIT_SHA (inyectado por Vercel en cada deploy),
  2) `git rev-parse HEAD` en el checkout local,
  3) cadena vacía (desconocido) — nunca se inventa un SHA.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

# ── Versiones de plataforma ────────────────────────────────────────────────────
# 1.4.0 = modelo canónico canonical_property_identity + administrative_context
#         (fuente autoritativa única consumida por Titulux/GIS/valoración/scoring).
ARHIAX_RE_VERSION = "1.4.0"
DICTUS_ENGINE_VERSION = "1.4.0"
GIS_ADAPTER_VERSION = "1.2.0"
TITULUX_VERSION = "1.1.0"
RULESET_VERSION = "1.3.0"

# Matriz de versiones consumible por el status endpoint y el pie del dictamen.
VERSION_MATRIX = {
    "ARHIAX_RE_VERSION": ARHIAX_RE_VERSION,
    "DICTUS_ENGINE_VERSION": DICTUS_ENGINE_VERSION,
    "GIS_ADAPTER_VERSION": GIS_ADAPTER_VERSION,
    "TITULUX_VERSION": TITULUX_VERSION,
    "RULESET_VERSION": RULESET_VERSION,
}

_GIT_SHA_CACHE = None


def git_commit_sha() -> str:
    """SHA del commit actual (mejor esfuerzo, sin lanzar, sin inventar)."""
    global _GIT_SHA_CACHE
    if _GIT_SHA_CACHE is not None:
        return _GIT_SHA_CACHE

    sha = os.environ.get("VERCEL_GIT_COMMIT_SHA", "").strip()
    if not sha:
        try:
            repo_root = Path(__file__).resolve().parent.parent
            out = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(repo_root), capture_output=True, text=True, timeout=5,
            )
            if out.returncode == 0:
                sha = out.stdout.strip()
        except Exception:
            sha = ""
    _GIT_SHA_CACHE = sha or ""
    return _GIT_SHA_CACHE


def version_blob() -> dict:
    """Dict con la matriz de versiones + SHA (serializable para API/PDF)."""
    blob = dict(VERSION_MATRIX)
    blob["GIT_COMMIT_SHA"] = git_commit_sha()
    return blob


def version_line(separador: str = " · ") -> str:
    """Línea legible para el pie del dictamen."""
    partes = [f"ARHIAX RE v{ARHIAX_RE_VERSION}"]
    sha = git_commit_sha()
    if sha:
        partes.append(f"commit {sha[:8]}")
    partes.append(f"dictus v{DICTUS_ENGINE_VERSION}")
    partes.append(f"GIS v{GIS_ADAPTER_VERSION}")
    partes.append(f"Titulux v{TITULUX_VERSION}")
    partes.append(f"reglas v{RULESET_VERSION}")
    return separador.join(partes)

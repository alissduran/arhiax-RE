# -*- coding: utf-8 -*-
"""ARHIAX RE — Entorno de ejecución y política de liberación (03I.2A).

Módulo SIN dependencias (importable aunque el resto de la capa falle), porque define
la última línea de defensa: si el gate de liberación no se puede evaluar, la política
del entorno decide si el dictamen se emite marcado o si NO se emite.

ENTORNOS
--------
`ARHIAX_ENV` ∈ {development, test, staging, production}. Un valor **desconocido** o
**ausente** se trata de forma CONSERVADORA: como `production`, que es el entorno más
estricto. Preferimos bloquear de más en un entorno mal declarado que emitir un
dictamen liberable sin haber podido comprobar el núcleo SAGRILAFT.

POLÍTICA
--------
    development  legacy → MARCAR    gate no evaluable → MARCAR (INVALID_FOR_RELEASE)
    test         legacy → MARCAR    gate no evaluable → MARCAR (INVALID_FOR_RELEASE)
    staging      legacy → BLOQUEAR  gate no evaluable → BLOQUEAR
    production   legacy → BLOQUEAR  gate no evaluable → BLOQUEAR

MARK  = se emite un artefacto DIAGNÓSTICO, siempre marcado INVALID_FOR_RELEASE.
BLOCK = no existe documento liberable (no se escribe ningún PDF final).

OVERRIDE
--------
`ARHIAX_ALLOW_LEGACY_RELEASE=1` permite, de forma EXCEPCIONAL, convertir un BLOCK en
MARK. Nunca convierte un artefacto en VALID_FOR_RELEASE: solo autoriza producir un
diagnóstico marcado. Su uso queda siempre registrado en la traza de liberación.
Se acepta el nombre antiguo `ARHIAX_PERMITIR_LEGACY` como alias deprecado.
"""

from __future__ import annotations

import os
from typing import Dict, Optional

ENV_DEVELOPMENT = "development"
ENV_TEST = "test"
ENV_STAGING = "staging"
ENV_PRODUCTION = "production"

ENTORNOS = (ENV_DEVELOPMENT, ENV_TEST, ENV_STAGING, ENV_PRODUCTION)

# Entorno que se asume cuando la variable falta o trae un valor desconocido.
ENTORNO_CONSERVADOR = ENV_PRODUCTION

POLICY_MARK = "MARK"
POLICY_BLOCK = "BLOCK"

POLITICA_POR_ENTORNO: Dict[str, str] = {
    ENV_DEVELOPMENT: POLICY_MARK,
    ENV_TEST: POLICY_MARK,
    ENV_STAGING: POLICY_BLOCK,
    ENV_PRODUCTION: POLICY_BLOCK,
}

# Override excepcional (nunca convierte en válido: solo permite MARK).
OVERRIDE_VAR = "ARHIAX_ALLOW_LEGACY_RELEASE"
OVERRIDE_VAR_LEGACY = "ARHIAX_PERMITIR_LEGACY"   # alias deprecado


def normalizar_entorno(valor: Optional[str] = None) -> Dict[str, object]:
    """Normaliza `ARHIAX_ENV`. Devuelve entorno efectivo + trazabilidad.

    Returns:
        {"environment": "production"|..., "declared": bool, "raw": str|None,
         "assumed_conservative": bool}
    """
    raw = valor if valor is not None else os.environ.get("ARHIAX_ENV")
    limpio = str(raw or "").strip().lower()
    if limpio in POLITICA_POR_ENTORNO:
        return {"environment": limpio, "declared": True, "raw": clean_raw(raw),
                "assumed_conservative": False}
    return {"environment": ENTORNO_CONSERVADOR, "declared": False,
            "raw": clean_raw(raw), "assumed_conservative": True}


def clean_raw(valor) -> Optional[str]:
    """Valor crudo saneado para la traza (sin secretos: el entorno no lo es)."""
    if valor in (None, ""):
        return None
    return str(valor).strip()[:40]


def politica_para(entorno: str) -> str:
    """Política declarada para un entorno (MARK | BLOCK); desconocido -> BLOCK."""
    return POLITICA_POR_ENTORNO.get(str(entorno or "").strip().lower(), POLICY_BLOCK)


def override_activo() -> Dict[str, object]:
    """¿Hay un override excepcional activo? Devuelve su variable y su valor crudo."""
    for var, deprecada in ((OVERRIDE_VAR, False), (OVERRIDE_VAR_LEGACY, True)):
        val = os.environ.get(var)
        if val is not None and str(val).strip() == "1":
            return {"activo": True, "variable": var, "valor": "1",
                    "deprecada": deprecada}
    return {"activo": False, "variable": None, "valor": None, "deprecada": False}


def matriz_legible() -> str:
    """Matriz de política en texto (para documentación/traza)."""
    return " · ".join(f"{env.upper()} -> {POLITICA_POR_ENTORNO[env]}"
                      for env in ENTORNOS)

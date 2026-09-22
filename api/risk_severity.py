# -*- coding: utf-8 -*-
"""ARHIAX RE — Contrato ÚNICO de severidad de riesgo (03I.1 · hallazgo F3).

PROBLEMA QUE CIERRA
-------------------
El mismo hecho físico aparecía con dos severidades distintas en el mismo
dictamen:

    Titulux (pág. 4):  GEO_B01-Baja — Amenaza por riesgo (POT) [Riesgo · ALTA]
    Hallazgos (pág. 10): H-GEO ... (Baja)                    [Severidad MEDIO]

La causa era que Titulux fijaba `severidad="alta"` en el código
(`rules.amenazas_pot`) mientras el capítulo de hallazgos derivaba la severidad
del NIVEL real de la amenaza. Dos productores = dos verdades.

REGLA
-----
La severidad se decide UNA sola vez, aquí, en función del NIVEL de amenaza
declarado por la fuente oficial, y la consumen los CUATRO productores:
Titulux (pre-dictamen), Hallazgos, Score y Resumen de hallazgos.

Un nivel BAJA con intersección es una AFECTACIÓN PRESENTE: exige verificación
puntual por profesional competente (severidad MEDIO), pero NUNCA equivale a una
amenaza ALTA. La severidad tampoco puede saltar a ALTO sin un nivel ALTO/MUY ALTO
declarado por la fuente: la severidad no es una opinión, es una función del dato.

Este módulo NO valora riesgo ni cambia umbrales: solo publica la tabla de
decisión y su regla versionada, para que la inconsistencia sea imposible.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

# Identidad de la regla (viaja al dictamen y a las matrices de QA).
RULE_ID = "RSK-SEV-1"
RULE_VERSION = "1.0.0"

# Severidades canónicas (vocabulario cerrado, consumido por hallazgos/score).
SEV_ALTO = "ALTO"
SEV_MEDIO = "MEDIO"
SEV_BAJO = "BAJO"
SEV_INFORMATIVO = "INFORMATIVO"
SEV_OBSERVACION = "OBSERVACION"

# Orden de gravedad (para la decisión "peor nivel").
_ORDEN_SEV = {SEV_ALTO: 4, SEV_MEDIO: 3, SEV_BAJO: 2,
              SEV_OBSERVACION: 1, SEV_INFORMATIVO: 0}

# Tabla de decisión: nivel declarado por la fuente -> severidad + peso del score
# hidrológico. El peso vive aquí para que el score NO tenga su propia copia de la
# tabla (mismos números que ya usaba el motor: 15/8/5).
_TABLA: Dict[str, Dict[str, Any]] = {
    "MUY ALTA": {"severidad": SEV_ALTO, "peso_hidrologico": 15,
                 "fundamento": "Amenaza de nivel MUY ALTA declarada por la fuente oficial."},
    "MUY ALTO": {"severidad": SEV_ALTO, "peso_hidrologico": 15,
                 "fundamento": "Amenaza de nivel MUY ALTO declarada por la fuente oficial."},
    "ALTA": {"severidad": SEV_ALTO, "peso_hidrologico": 15,
             "fundamento": "Amenaza de nivel ALTA declarada por la fuente oficial."},
    "ALTO": {"severidad": SEV_ALTO, "peso_hidrologico": 15,
             "fundamento": "Amenaza de nivel ALTO declarada por la fuente oficial."},
    "MEDIA": {"severidad": SEV_MEDIO, "peso_hidrologico": 8,
              "fundamento": "Amenaza de nivel MEDIA declarada por la fuente oficial."},
    "MEDIO": {"severidad": SEV_MEDIO, "peso_hidrologico": 8,
              "fundamento": "Amenaza de nivel MEDIO declarada por la fuente oficial."},
    "MODERADA": {"severidad": SEV_MEDIO, "peso_hidrologico": 8,
                 "fundamento": "Amenaza de nivel MODERADA declarada por la fuente oficial."},
    "BAJA": {"severidad": SEV_MEDIO, "peso_hidrologico": 5,
             "fundamento": ("Afectación PRESENTE de nivel BAJA: exige verificación puntual "
                            "y no puede reportarse como amenaza alta.")},
    "BAJO": {"severidad": SEV_MEDIO, "peso_hidrologico": 5,
             "fundamento": ("Afectación PRESENTE de nivel BAJO: exige verificación puntual "
                            "y no puede reportarse como amenaza alta.")},
    "MUY BAJA": {"severidad": SEV_BAJO, "peso_hidrologico": 5,
                 "fundamento": "Amenaza de nivel MUY BAJA declarada por la fuente oficial."},
    "MUY BAJO": {"severidad": SEV_BAJO, "peso_hidrologico": 5,
                 "fundamento": "Amenaza de nivel MUY BAJO declarada por la fuente oficial."},
    "LEVE": {"severidad": SEV_BAJO, "peso_hidrologico": 5,
             "fundamento": "Amenaza de nivel LEVE declarada por la fuente oficial."},
}

_SIN_AFECTACION = {"severidad": SEV_INFORMATIVO, "peso_hidrologico": 0,
                   "fundamento": "Sin intersección con las capas consultadas."}
_NO_EVALUADO = {"severidad": SEV_OBSERVACION, "peso_hidrologico": None,
                "fundamento": ("Componente NO EVALUADO: no se afirma ausencia de riesgo "
                               "sin fuente oficial.")}

_ALIAS_SIN_AFECTACION = ("SIN AFECTACION", "SIN AFECTACIÓN", "NO INTERSECTA",
                         "SIN RIESGO", "SIN RIESGO IDENTIFICADO", "NO APLICA")
_ALIAS_NO_EVALUADO = ("", "NO EVALUADO", "PENDIENTE", "INDETERMINADO", "N/D",
                      "NA", "DESCONOCIDO", "SIN DATO", "NO DISPONIBLE")


def _clave(nivel: Optional[str]) -> str:
    return " ".join(str(nivel or "").strip().upper().split())


def normalizar_nivel(nivel: Optional[str]) -> str:
    """Devuelve la clave de decisión para un nivel declarado por la fuente."""
    k = _clave(nivel)
    if k in _TABLA:
        return k
    if k in _ALIAS_SIN_AFECTACION:
        return "SIN_AFECTACION"
    if k in _ALIAS_NO_EVALUADO:
        return "NO_EVALUADO"
    # Nivel declarado pero no tabulado: NO se degrada a "sin afectación".
    return "DESCONOCIDO"


def decidir(nivel: Optional[str] = None, *, intersecta: bool = True,
            evaluado: bool = True) -> Dict[str, Any]:
    """Decisión ÚNICA de severidad para un hecho de amenaza/riesgo.

    Args:
        nivel: nivel declarado por la fuente (Alta/Media/Baja/Muy alta...).
        intersecta: si el predio intersecta la capa (hecho material).
        evaluado: si la capa pudo consultarse.

    Returns:
        {"regla", "regla_version", "nivel_input", "nivel", "severidad",
         "peso_hidrologico", "fundamento", "intersecta", "evaluado"}
    """
    if not evaluado:
        base, nivel_norm = dict(_NO_EVALUADO), "NO_EVALUADO"
    elif not intersecta:
        base, nivel_norm = dict(_SIN_AFECTACION), "SIN_AFECTACION"
    else:
        clave = normalizar_nivel(nivel)
        if clave in _TABLA:
            base, nivel_norm = dict(_TABLA[clave]), clave
        elif clave == "SIN_AFECTACION":
            # La fuente declara explícitamente "sin afectación" en el polígono.
            base, nivel_norm = dict(_SIN_AFECTACION), "SIN_AFECTACION"
        elif clave == "NO_EVALUADO":
            base, nivel_norm = dict(_NO_EVALUADO), "NO_EVALUADO"
        else:
            # Nivel no tabulado: se declara como observación, nunca como ALTO ni
            # como "sin afectación" (no se inventa ni se minimiza).
            base = {"severidad": SEV_OBSERVACION, "peso_hidrologico": None,
                    "fundamento": (f"Nivel de amenaza declarado no tabulado "
                                   f"({nivel!r}): requiere verificación; no se minimiza "
                                   f"ni se equipara a amenaza alta.")}
            nivel_norm = "NO_TABULADO"
    return {
        "regla": RULE_ID,
        "regla_version": RULE_VERSION,
        "nivel_input": nivel,
        "nivel": nivel_norm,
        "severidad": base["severidad"],
        "peso_hidrologico": base["peso_hidrologico"],
        "fundamento": base["fundamento"],
        "intersecta": bool(intersecta),
        "evaluado": bool(evaluado),
    }


def severidad(nivel: Optional[str] = None, *, intersecta: bool = True,
              evaluado: bool = True) -> str:
    """Severidad canónica (ALTO|MEDIO|BAJO|INFORMATIVO|OBSERVACION)."""
    return decidir(nivel, intersecta=intersecta, evaluado=evaluado)["severidad"]


def peso_hidrologico(nivel: Optional[str] = None, *, intersecta: bool = True,
                     evaluado: bool = True) -> Optional[int]:
    """Peso del score hidrológico asociado a la MISMA decisión de severidad."""
    return decidir(nivel, intersecta=intersecta, evaluado=evaluado)["peso_hidrologico"]


def severidad_titulux(sev: str) -> str:
    """Traduce la severidad canónica al vocabulario del pre-dictamen Titulux."""
    return {SEV_ALTO: "alta", SEV_MEDIO: "media", SEV_BAJO: "baja",
            SEV_INFORMATIVO: "informativo",
            SEV_OBSERVACION: "observacion"}.get(str(sev or "").upper(), "media")


def peor_severidad(*severidades: str) -> str:
    """La más grave de un conjunto (para títulos que combinan dos capas)."""
    mejor = SEV_INFORMATIVO
    for s in severidades:
        if _ORDEN_SEV.get(str(s or "").upper(), 0) >= _ORDEN_SEV.get(mejor, 0):
            if s:
                mejor = str(s).upper()
    return mejor

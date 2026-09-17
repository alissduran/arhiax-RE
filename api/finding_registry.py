# -*- coding: utf-8 -*-
"""
ARHIAX RE — Finding registry (bug K).

Un registro ÚNICO y coherente de hallazgos, que normaliza las salidas de las
distintas capas (legal_analyzer, Titulux, GIS, identidad, score) y detecta:

  * DUPLICADOS  — el mismo hallazgo emitido dos veces (mismo código/título).
  * CONTRADICCIONES — hallazgos mutuamente excluyentes entre capas, p. ej.
      - Titulux TIT_B01 "falta folio/código" coexistir con un NUPRE resuelto,
      - Titulux TIT_B04 "sin gravámenes" coexistir con un embargo/hipoteca
        vigente del analizador legal,
      - "sin afectación de riesgo" coexistir con una amenaza ALTA/ALTA.

El gate de consistencia consume `coherencia()` para impedir emitir un dictus
donde las capas se contradigan.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def _id_estable(titulo: str) -> str:
    """ID estable de un hallazgo a partir de su título (primer token 'H-0X')."""
    import re
    m = re.match(r"(H-\d+|H-IDENT|TIT_\w+|SAG_\w+|GEO_\w+|EXP-\w+-\d+|I-[\w-]+)", (titulo or "").strip())
    return m.group(1) if m else (titulo or "").strip()[:40]


def normalizar_hallazgos(hallazgos) -> List[Dict[str, Any]]:
    """Normaliza los hallazgos legales/GIS (tuplas de 6/7) a dicts."""
    out = []
    for h in hallazgos or []:
        if not isinstance(h, (tuple, list)) or len(h) < 4:
            continue
        sev = h[0]
        titulo = h[3]
        fuente = h[4] if len(h) > 4 else ""
        desc = h[5] if len(h) > 5 else ""
        out.append({"id": _id_estable(titulo), "severidad": sev, "titulo": titulo,
                    "fuente": fuente, "descripcion": desc, "origen": "legal_gis"})
    return out


def normalizar_titulux(pre_dictamen) -> List[Dict[str, Any]]:
    """Normaliza los hallazgos del pre-dictamen Titulux a dicts."""
    out = []
    for h in pre_dictamen or []:
        if not isinstance(h, dict):
            continue
        out.append({"id": h.get("id") or _id_estable(h.get("titulo") or ""),
                    "severidad": h.get("severidad") or "",
                    "titulo": h.get("titulo") or "",
                    "fuente": "Titulux",
                    "descripcion": h.get("descripcion") or "",
                    "estado": h.get("estado") or "",
                    "origen": "titulux"})
    return out


def detectar_duplicados(registro: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Hallazgos con el mismo id estable (mismo código repetido)."""
    vistos: Dict[str, str] = {}
    dups = []
    for f in registro:
        iid = f.get("id") or ""
        if not iid:
            continue
        if iid in vistos and vistos[iid] != f.get("titulo"):
            # mismo código pero distinto título -> duplicado real
            dups.append({"codigo": iid, "a": vistos[iid], "b": f.get("titulo")})
        vistos.setdefault(iid, f.get("titulo"))
    return dups


def detectar_contradicciones(
    hallazgos: Optional[List],
    titulux: Optional[List[Dict[str, Any]]],
    canonical_identity: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Detecta contradicciones ENTRE capas (Titulux vs legal vs identidad)."""
    reg = normalizar_hallazgos(hallazgos) + normalizar_titulux(titulux)
    contradicciones: List[Dict[str, Any]] = []

    nupre = (canonical_identity or {}).get("nupre")

    # TIT_B01 "falta folio/código" vs NUPRE resuelto (regresión de bug A)
    for f in reg:
        if f.get("id") == "TIT_B01" and f.get("origen") == "titulux":
            if nupre and ("falta folio de matrícula o código" in (f.get("descripcion") or "")
                          or "falta" in (f.get("titulo") or "").lower()):
                contradicciones.append({
                    "codigo": "FR-TITB01-NUPRE",
                    "detalle": f"Titulux TIT_B01 dice 'falta folio/código' pero hay NUPRE resuelto ({nupre})",
                })

    # TIT_B04 "sin gravámenes" vs gravamen vigente del analizador legal
    legal_cargas = [f for f in reg
                    if f.get("origen") == "legal_gis" and f.get("severidad") == "ALTO"
                    and any(k in (f.get("titulo") or "").lower()
                            for k in ("hipoteca", "embargo", "medida cautelar", "gravamen"))]
    titulux_sin_cargas = [f for f in reg
                          if f.get("id") == "TIT_B04" and f.get("origen") == "titulux"
                          and "ok" in (f.get("estado") or "").lower()]
    if legal_cargas and titulux_sin_cargas:
        contradicciones.append({
            "codigo": "FR-TITB04-CARGAS",
            "detalle": ("Titulux TIT_B04 declara 'sin gravámenes' pero el analizador legal "
                        "detectó carga(s) vigente(s): " + "; ".join(c["titulo"] for c in legal_cargas[:3])),
        })

    # "sin afectación" vs amenaza/riesgo ALTA/ALTO en el mismo registro
    sin_afectacion = [f for f in reg
                      if "sin afectacion" in (f.get("titulo") or "").lower()
                      or "sin afectación" in (f.get("descripcion") or "").lower()]
    riesgo_alto = [f for f in reg
                   if f.get("severidad") == "ALTO"
                   and any(k in (f.get("titulo") or "").lower()
                           for k in ("amenaza", "riesgo", "remocion", "inundacion"))]
    if sin_afectacion and riesgo_alto:
        contradicciones.append({
            "codigo": "FR-RIESGO-CONTRADICCION",
            "detalle": "coexisten 'sin afectación' y una amenaza/riesgo ALTO",
        })

    return contradicciones


def coherencia(hallazgos, titulux, canonical_identity) -> Dict[str, Any]:
    """Informe de coherencia del finding registry."""
    reg = normalizar_hallazgos(hallazgos) + normalizar_titulux(titulux)
    dups = detectar_duplicados(reg)
    contra = detectar_contradicciones(hallazgos, titulux, canonical_identity)
    return {
        "coherente": not dups and not contra,
        "duplicados": dups,
        "contradicciones": contra,
        "total": len(reg),
    }

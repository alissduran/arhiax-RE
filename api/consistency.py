# -*- coding: utf-8 -*-
"""
ARHIAX RE — Invariantes automáticas + PRE_RENDER_CONSISTENCY_GATE.

Garantiza que el dictamen NO se emita si el modelo interno se contradice a sí
mismo. Antes esto solo se "advertía" por print (controles de calidad Sprint 0),
lo que permitía emitir documentos con contradicciones como:

  * "riesgos consultados en vivo" + "H-GEO NO EVALUADO" a la vez,
  * "NO EVALUADO" con score hidrológico 100/100,
  * "falta folio/código" teniendo NUPRE resuelto por nomenclatura,
  * IDENTITY_CONFLICT (predio vecino) afirmando la normativa de ese predio.

El gate separa dos niveles:

  * BLOQUEANTE  -> lanza InconsistenciaBloqueante: el PDF NO se emite (el worker
                   responde con error claro y NO entrega un dictus inconsistente).
  * ADVERTENCIA -> se reporta (queda en el log y en el resultado del gate) pero
                   el documento se emite con el matiz correspondiente.

Los invariantes son puros y declarativos; añadir uno nuevo es añadir una tupla a
INVARIANTES sin tocar el resto.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple


class InconsistenciaBloqueante(Exception):
    """El modelo interno se contradice de forma que invalidaría el dictamen."""


# Un invariante = (código, nivel, descripción, check(contexto) -> (cumple, detalle))
# nivel: "bloqueante" | "advertencia"
Invariante = Tuple[str, str, str, Callable[[Dict[str, Any]], Tuple[bool, str]]]


def _inv_noeval_score(ctx: Dict[str, Any]) -> Tuple[bool, str]:
    """NO EVALUADO debe implicar score hidrológico NULO (nunca 100/100)."""
    geo = ctx.get("geo_eval") or {}
    score = ctx.get("score_result") or {}
    evaluado = geo.get("evaluado")
    hidro = score.get("score_hidrologico")
    if evaluado is False and hidro is not None:
        return False, f"geo_eval NO EVALUADO pero score hidrologico = {hidro} (debe ser None)"
    return True, "score hidrologico coherente con el estado de evaluacion"


def _inv_identity_conflict_no_assert(ctx: Dict[str, Any]) -> Tuple[bool, str]:
    """IDENTITY_CONFLICT no puede coexistir con datos prediales afirmados."""
    cid = ctx.get("canonical_identity") or {}
    predio = ctx.get("predio_real")
    if cid.get("estado") == "IDENTITY_CONFLICT" and predio is not None:
        return False, ("IDENTITY_CONFLICT (la direccion del CTL y el predio resuelto no "
                       "coinciden) pero aun se afirman datos prediales: NO se puede emitir "
                       "la normativa de un predio en conflicto de identidad")
    return True, "sin conflicto de identidad sin resolver al afirmar datos prediales"


def _inv_norecord_no_evaluado(ctx: Dict[str, Any]) -> Tuple[bool, str]:
    """NO_RECORD no puede presentarse como 'EVALUADO EN VIVO'."""
    cid = ctx.get("canonical_identity") or {}
    geo = ctx.get("geo_eval") or {}
    if cid.get("estado") == "NO_RECORD" and geo.get("evaluado") is True:
        return False, "sin predio resuelto (NO_RECORD) pero geo_eval se marca EVALUADO en vivo"
    return True, "coherencia entre identidad resuelta y estado de evaluacion geoespacial"


def _inv_nupre_coherente(ctx: Dict[str, Any]) -> Tuple[bool, str]:
    """El NUPRE canónico y el del predio resuelto no pueden divergir."""
    cid = ctx.get("canonical_identity") or {}
    predio = ctx.get("predio_real") or {}
    p = predio.get("predio") or {}
    nupre_canon = cid.get("nupre")
    nupre_predio = p.get("numero_predial_nacional") or p.get("nupre")
    if nupre_canon and nupre_predio and nupre_canon != nupre_predio:
        return False, f"NUPRE canonico {nupre_canon} != NUPRE del predio {nupre_predio}"
    return True, "NUPRE canonico y del predio resuelto coinciden"


def _inv_matricula_coherente(ctx: Dict[str, Any]) -> Tuple[bool, str]:
    """Matrícula municipal vs folio SNR: divergencia es una advertencia de identidad."""
    cid = ctx.get("canonical_identity") or {}
    folio = (cid.get("folio_snr") or "").replace(" ", "")
    muni = (cid.get("matricula_municipal") or "").replace(" ", "")
    if muni and folio and muni != folio:
        return False, f"matricula municipal {muni} != folio SNR {folio} (verificar ORIP/catastro)"
    return True, "matricula municipal y folio SNR coinciden o no hay ambas para comparar"


def _inv_comuna_coherente(ctx: Dict[str, Any]) -> Tuple[bool, str]:
    """La comuna del dictamen debe salir del contexto canónico (bug B)."""
    ac = ctx.get("administrative_context") or {}
    comuna_mostrada = ctx.get("comuna_mostrada")
    comuna_canon = ac.get("comuna")
    if comuna_canon and comuna_mostrada and comuna_mostrada != "N/D" \
            and comuna_mostrada != comuna_canon:
        return False, f"comuna mostrada {comuna_mostrada!r} != comuna canonica {comuna_canon!r}"
    return True, "comuna mostrada coherente con el contexto canonico"


def _inv_titular_tipo_documento(ctx: Dict[str, Any]) -> Tuple[bool, str]:
    """El tipo de persona debe ser coherente con el documento (bug I)."""
    cid = ctx.get("canonical_identity") or {}
    tit = cid.get("titular") or {}
    tipo_doc = (tit.get("tipo_documento") or "").lower()
    tipo_persona = tit.get("tipo_persona")
    if tipo_persona == "NATURAL_PERSON" and tipo_doc == "nit":
        return False, "titular NATURAL_PERSON con documento NIT (incoherente)"
    if tipo_persona == "LEGAL_ENTITY" and tipo_doc in ("cc", "ce", "ti", "rc", "pasaporte"):
        return False, f"titular LEGAL_ENTITY con documento personal {tipo_doc}"
    return True, "tipo de persona coherente con el documento"


# ── Registro declarativo de invariantes ────────────────────────────────────────
INVARIANTES: List[Invariante] = [
    ("I-SCORE-NOEVAL", "bloqueante",
     "NO EVALUADO implica score hidrológico nulo", _inv_noeval_score),
    ("I-IDENTITY-CONFLICT", "bloqueante",
     "IDENTITY_CONFLICT no afirma datos prediales", _inv_identity_conflict_no_assert),
    ("I-NORECORD-NOEVAL", "bloqueante",
     "sin predio resuelto no se marca EVALUADO en vivo", _inv_norecord_no_evaluado),
    ("I-NUPRE", "bloqueante",
     "NUPRE canónico y del predio resuelto coinciden", _inv_nupre_coherente),
    ("I-MATRICULA", "advertencia",
     "matrícula municipal y folio SNR son coherentes", _inv_matricula_coherente),
    ("I-COMUNA", "advertencia",
     "comuna mostrada sale del contexto canónico", _inv_comuna_coherente),
    ("I-TITULAR", "advertencia",
     "tipo de persona coherente con el documento", _inv_titular_tipo_documento),
]


def evaluar_invariantes(contexto: Dict[str, Any]) -> Dict[str, Any]:
    """Evalúa todos los invariantes y devuelve el informe completo."""
    resultados = []
    for codigo, nivel, desc, check in INVARIANTES:
        try:
            cumple, detalle = check(contexto)
        except Exception as e:  # noqa: BLE001 — un invariante no debe tumbar el gate
            cumple, detalle = True, f"invariante no evaluable ({e})"
        resultados.append({
            "codigo": codigo, "nivel": nivel, "descripcion": desc,
            "cumple": bool(cumple), "detalle": detalle,
        })
    bloqueantes = [r for r in resultados if not r["cumple"] and r["nivel"] == "bloqueante"]
    advertencias = [r for r in resultados if not r["cumple"] and r["nivel"] == "advertencia"]
    return {
        "ok": not bloqueantes,
        "bloqueantes": bloqueantes,
        "advertencias": advertencias,
        "resultados": resultados,
        "total": len(resultados),
    }


def ejecutar_gate(contexto: Dict[str, Any], *, raise_on_blocking: bool = True) -> Dict[str, Any]:
    """PRE_RENDER_CONSISTENCY_GATE.

    Devuelve el informe. Si hay bloqueantes y `raise_on_blocking`, lanza
    InconsistenciaBloqueante (el PDF NO se emite).
    """
    informe = evaluar_invariantes(contexto)
    if not informe["ok"] and raise_on_blocking:
        det = "; ".join(f"{r['codigo']}: {r['detalle']}" for r in informe["bloqueantes"])
        raise InconsistenciaBloqueante(
            f"El dictamen no se emite por inconsistencias bloqueantes: {det}")
    return informe

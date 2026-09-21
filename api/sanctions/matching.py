# -*- coding: utf-8 -*-
"""Matching determinista con jerarquía explícita (§17–§19).

Jerarquía (de mayor a menor fuerza):
  1. identificador exacto (documento)
  2. nombre normalizado exacto + identificador/atributo corroborante
  3. alias exacto + atributos corroborantes
  4. nombre difuso + atributos secundarios (fecha de nacimiento)
  5. nombre difuso solo

Regla dura: un match SOLO por nombre difuso NUNCA produce MATCH confirmado;
queda como POTENTIAL_MATCH/REVIEW_REQUIRED (§17/§36).

Política de conflicto de identificadores (§19): nombre exacto NO basta para
confirmar sanción si el identificador del registro de la lista es incompatible
(p. ej. pasaporte distinto, cédula de otro número, fecha de nacimiento
incompatible) -> REVIEW_REQUIRED con motivo `IDENTIFIER_CONFLICT`.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from typing import Any, Optional, Sequence, Tuple

from .contracts import (
    RESULT_EXACT, RESULT_NO_MATCH, RESULT_POTENTIAL, RESULT_REVIEW,
    RESULT_STRONG,
)
from .subjects import document_variants, match_key

ALGORITHM_VERSION = "sanctions-matcher/1.0"

UMBRAL_ALERTA = 0.90      # nombre muy parecido
UMBRAL_REVISION = 0.80    # nombre parecido -> revisión manual


@dataclass(frozen=True)
class MatchResult:
    result: str
    score: float
    rule: str
    matched_record_ids: Tuple[str, ...] = ()
    reasons: Tuple[str, ...] = ()
    conflict: bool = False

    @property
    def requiere_revision(self) -> bool:
        return self.result in (RESULT_POTENTIAL, RESULT_STRONG, RESULT_REVIEW)


def _g(rec: Any, key: str, default=None):
    """Lee un campo del registro (objeto con atributos o dict)."""
    if isinstance(rec, dict):
        return rec.get(key, default)
    return getattr(rec, key, default)


def _rec_doc_variants(rec: Any) -> Tuple[str, ...]:
    tipo = _g(rec, "tipo_documento")
    num = _g(rec, "numero_documento")
    return document_variants(tipo, num)


def _rec_names(rec: Any) -> Tuple[Tuple[str, str], ...]:
    """[(campo, nombre)] del registro: nombre principal + alias."""
    out = []
    nombre = _g(rec, "nombre")
    if nombre:
        out.append(("nombre", str(nombre)))
    for a in (_g(rec, "alias") or ()):
        if a:
            out.append(("alias", str(a)))
    return tuple(out)


def _mejor_nombre(env, registros) -> Optional[Tuple[Any, float, str, str]]:
    """Mejor coincidencia de nombre (exacta o difusa) y cómo se obtuvo."""
    objetivo = match_key(env.canonical_name)
    objetivo_ts = " ".join(sorted(objetivo.split()))
    mejor = None
    for r in registros:
        for campo, cand in _rec_names(r):
            cand_key = match_key(cand)
            if not cand_key:
                continue
            if cand_key == objetivo or " ".join(sorted(cand_key.split())) == objetivo_ts:
                return r, 1.0, campo, "nombre_exacto"
            score = difflib.SequenceMatcher(None, objetivo, cand_key).ratio()
            if mejor is None or score > mejor[1]:
                mejor = (r, score, campo, "nombre_difuso")
    return mejor


def _conflicto_identificadores(env, rec) -> Tuple[bool, Tuple[str, ...]]:
    """§19: ¿el registro trae un identificador INCOMPATIBLE con el sujeto?"""
    motivos = []
    rec_variants = _rec_doc_variants(rec)
    subj_variants = document_variants(env.document_type, env.document_normalized)
    rec_tipo = (_g(rec, "tipo_documento") or "").strip().lower()
    if rec_variants and subj_variants:
        if not set(rec_variants) & set(subj_variants):
            motivos.append("DOCUMENT_MISMATCH")
        elif rec_tipo and env.document_type and rec_tipo != env.document_type:
            motivos.append("DOCUMENT_TYPE_MISMATCH")
    elif rec_variants and not subj_variants:
        # La lista aporta documento y el sujeto no: no es conflicto, es falta de
        # corroboración (lo resuelve la jerarquía de nombres).
        pass
    elif subj_variants and not rec_variants:
        pass
    # Fecha de nacimiento: solo se compara si AMBOS la tienen.
    dob_rec = _g(rec, "fecha_nacimiento")
    dob_sub = getattr(env, "fecha_nacimiento", None)
    if dob_rec and dob_sub:
        if str(dob_rec)[:4] != str(dob_sub)[:4]:
            motivos.append("BIRTHDATE_MISMATCH")
    return (bool(motivos), tuple(motivos))


def _core_numerico(doc: Optional[str]) -> Optional[str]:
    """Parte numérica inicial del documento (>=6 dígitos), sin separadores."""
    if not doc:
        return None
    m = re.match(r"(\d{6,})", str(doc))
    return m.group(1) if m else None


def consultar(env, registros: Sequence[Any]) -> MatchResult:
    """Aplica la jerarquía completa a UN sujeto contra UNA fuente."""
    registros = list(registros or ())
    if not registros:
        return MatchResult(RESULT_NO_MATCH, 0.0, "lista_vacia")

    # ── 1. Identificador exacto ──────────────────────────────────────────────
    subj_variants = document_variants(env.document_type, env.document_normalized)
    if subj_variants:
        for r in registros:
            comunes = set(_rec_doc_variants(r)) & set(subj_variants)
            if comunes:
                rec_tipo = (_g(r, "tipo_documento") or "").strip().lower()
                if not rec_tipo or not env.document_type or rec_tipo == env.document_type:
                    return MatchResult(
                        RESULT_EXACT, 1.0, "identificador_exacto",
                        (str(_g(r, "id") or ""),),
                        ("documento exacto", f"documento={sorted(comunes)[0]}"))
        # 1b. Mismo NÚCLEO numérico con variante de formato (1045718995 vs
        #     1045718995X): NO es exacto silencioso — se confirma quedando en
        #     revisión, con el motivo declarado.
        _core = _core_numerico(env.document_normalized)
        if _core:
            for r in registros:
                for v in _rec_doc_variants(r):
                    if v != env.document_normalized and _core_numerico(v) == _core:
                        rec_tipo = (_g(r, "tipo_documento") or "").strip().lower()
                        if rec_tipo and env.document_type and rec_tipo != env.document_type:
                            continue
                        return MatchResult(
                            RESULT_STRONG, 1.0, "documento_variante_de_formato",
                            (str(_g(r, "id") or ""),),
                            (f"documento coincidente con variante de formato "
                             f"({env.document_normalized} vs {v})",))

    # ── 2-5. Nombre (exacto o difuso) ────────────────────────────────────────
    mejor = _mejor_nombre(env, registros)
    if mejor is None:
        return MatchResult(RESULT_NO_MATCH, 0.0, "sin_nombre_comparable")
    r, score, campo, via = mejor
    rid = str(_g(r, "id") or "")
    conflicto, motivos = _conflicto_identificadores(env, r)

    if via == "nombre_exacto":
        if conflicto:
            # §19: nombre exacto + identificador incompatible -> NO se confirma.
            return MatchResult(
                RESULT_REVIEW, score, "nombre_exacto_con_conflicto", (rid,),
                ("nombre exacto", "conflicto de identificadores: "
                 + ", ".join(motivos)), conflict=True)
        atributo = _atributo_corroborante(env, r, campo)
        if atributo:
            return MatchResult(RESULT_STRONG, score,
                               "nombre_exacto_corroborado", (rid,),
                               ("nombre exacto", atributo))
        # Nombre exacto (incluido alias) sin atributo independiente: señal fuerte
        # de probable identidad, exige revisión humana (nunca MATCH confirmado).
        return MatchResult(RESULT_POTENTIAL, score, "nombre_exacto_sin_corroborar",
                           (rid,), ("nombre exacto sin atributo corroborante",))

    if score >= UMBRAL_ALERTA:
        return MatchResult(RESULT_POTENTIAL, score, f"nombre_difuso_{campo}",
                           (rid,), (f"nombre difuso {score:.3f} en {campo}",))
    if score >= UMBRAL_REVISION:
        return MatchResult(RESULT_REVIEW, score, f"nombre_difuso_{campo}",
                           (rid,), (f"nombre difuso moderado {score:.3f} en {campo}",))
    return MatchResult(RESULT_NO_MATCH, score, "sin_coincidencia",
                       (), (f"mejor similitud {score:.3f} (bajo umbral)",))


def _atributo_corroborante(env, rec, campo_coincidente) -> Optional[str]:
    """Segundo atributo independiente del MISMO registro que corrobora (§17)."""
    # (a) documento presente en la lista que coincide en al menos la parte común
    rec_variants = set(_rec_doc_variants(rec))
    subj_variants = set(document_variants(env.document_type, env.document_normalized))
    if rec_variants and subj_variants and (rec_variants & subj_variants):
        return "documento coincidente"
    # (b) otro nombre/alias del registro que coincide exactamente
    objetivo = match_key(env.canonical_name)
    for c, cand in _rec_names(rec):
        if c == campo_coincidente:
            continue
        if match_key(cand) == objetivo:
            return f"{c} coincidente"
    # (c) fecha de nacimiento idéntica (si ambos la tienen)
    dob_rec = _g(rec, "fecha_nacimiento")
    dob_sub = getattr(env, "fecha_nacimiento", None)
    if dob_rec and dob_sub and str(dob_rec) == str(dob_sub):
        return "fecha de nacimiento coincidente"
    return None


def peor_resultado(a: str, b: str) -> str:
    """Combina resultados priorizando el riesgo (determinista)."""
    orden = {RESULT_EXACT: 6, RESULT_STRONG: 5, RESULT_POTENTIAL: 4,
             RESULT_REVIEW: 3, RESULT_NO_MATCH: 2, RESULT_SOURCE_UNAVAILABLE: 1,
             "NOT_SCREENED": 0}
    return a if orden.get(a, 0) >= orden.get(b, 0) else b

# -*- coding: utf-8 -*-
"""ARHIAX RE — BARRANQUILLA SOURCE PACK v1.0 · contrato de fuentes (ZERO MANUAL DEPENDENCY).

Este módulo NO rediseña el documento ni toca la gramática de decisión: define el
CONTRATO de adquisición automática, el registro de fuentes, la procedencia y el
transporte al run state.

Reglas duras (§1/§2/§27/§28):

  · Toda consulta devuelve el `SourceResult` de §27 con estados CERRADOS:
    `AVAILABLE | NO_MATCH | SOURCE_UNAVAILABLE | NOT_SUPPORTED | QUERY_FAILED`.
  · JAMÁS se convierte una ausencia en `NO_MATCH`, ni un `NOT_RUN` en `NO_MATCH`.
  · La evidencia cruda se preserva (cuando la licencia lo permite) y NUNCA se modifica:
    la normalización vive en un objeto aparte.
  · Ninguna fuente `CONTEXTUAL_EXTERNAL` ni `COMPUTED` se presenta como autoridad
    normativa.
  · `POT.altura_max` es ALTURA NORMATIVA: no puede mapearse a altura física del edificio.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

PACK_VERSION = "barranquilla-source-pack/1.0.0"
REGISTRY_VERSION = "barranquilla-sources-v1"

RAIZ = Path(__file__).resolve().parent.parent
DIR_PACK = RAIZ / "docs" / "source_pack"
RUTA_REGISTRO = DIR_PACK / "barranquilla_sources_v1.json"
RUTA_REGISTRO_YAML = DIR_PACK / "barranquilla_sources_v1.yaml"
RUTA_MANIFEST = DIR_PACK / "BARRANQUILLA_SOURCE_PACK_MANIFEST.json"
DIR_RAW = DIR_PACK / "raw" / "golden"

# ── §2 · modelo de autoridad ──────────────────────────────────────────────────
AUTORITATIVA_OFICIAL = "AUTHORITATIVE_OFFICIAL"
AUTORITATIVA_CONTRACTUAL = "AUTHORITATIVE_CONTRACTUAL"
CONTEXTUAL_EXTERNA = "CONTEXTUAL_EXTERNAL"
CALCULADA = "COMPUTED"
CLASES_AUTORIDAD = (AUTORITATIVA_OFICIAL, AUTORITATIVA_CONTRACTUAL, CONTEXTUAL_EXTERNA,
                    CALCULADA)
# Solo las dos primeras pueden sostener una afirmación normativa.
CLASES_NORMATIVAS = (AUTORITATIVA_OFICIAL, AUTORITATIVA_CONTRACTUAL)

# ── §27 · estados cerrados ────────────────────────────────────────────────────
DISPONIBLE = "AVAILABLE"
SIN_COINCIDENCIA = "NO_MATCH"
FUENTE_NO_DISPONIBLE = "SOURCE_UNAVAILABLE"
NO_SOPORTADA = "NOT_SUPPORTED"
CONSULTA_FALLIDA = "QUERY_FAILED"
ESTADOS = (DISPONIBLE, SIN_COINCIDENCIA, FUENTE_NO_DISPONIBLE, NO_SOPORTADA, CONSULTA_FALLIDA)
# Estados que significan «no se pudo saber», nunca «no existe».
ESTADOS_SIN_DATO = (FUENTE_NO_DISPONIBLE, NO_SOPORTADA, CONSULTA_FALLIDA)

# ── §12 · precedencia de riesgo ───────────────────────────────────────────────
CURRENT_NORMATIVE = "CURRENT_NORMATIVE"
CURRENT_OFFICIAL = "CURRENT_OFFICIAL"
HISTORICAL_REFERENCE = "HISTORICAL_REFERENCE"
PRECEDENCIA_RIESGO = (CURRENT_NORMATIVE, CURRENT_OFFICIAL, HISTORICAL_REFERENCE)

# ── §6 · precedencia de binding catastral (nunca features[0]) ─────────────────
BINDING_NUPRE = "NUPRE_EXACTO"
BINDING_PREDIAL = "NUMERO_PREDIAL_EXACTO"
BINDING_MUNICIPAL_KEY = "MUNICIPAL_KEY_EXACTO"
BINDING_RELACION = "RELACION_OFICIAL_PREDIO"
BINDING_DIRECCION = "DIRECCION_OFICIAL_LIGADA"
BINDING_ESPACIAL_CONTEXTO = "ESPACIAL_SOLO_CONTEXTO"
SIN_BINDING = "NO_BINDING"
# Orden publicado en el manifest v1.0 del pack (no se altera aquí: la clave municipal
# es un nivel canónico ADICIONAL que se resuelve entre predial y relación oficial).
PRECEDENCIA_BINDING = (BINDING_NUPRE, BINDING_PREDIAL, BINDING_RELACION, BINDING_DIRECCION,
                       BINDING_ESPACIAL_CONTEXTO)
# El binding espacial NO autoriza identidad: es contexto declarado.
BINDINGS_QUE_AUTORIZAN_IDENTIDAD = (BINDING_NUPRE, BINDING_PREDIAL, BINDING_MUNICIPAL_KEY,
                                    BINDING_RELACION, BINDING_DIRECCION)

# ══════════════════════════════════════════════════════════════════════════════
# §6 · CONTRATO DE TIPOS DE IDENTIFICADOR (binding TIPADO)
# ══════════════════════════════════════════════════════════════════════════════
# PROHIBIDO comparar un identificador contra un tipo incompatible. Un identificador
# de tipo T SOLO puede cotejarse con los campos declarados del tipo T: cotejar «a
# varias claves a la vez» permitía que un NUPRE casara con un `numero_predial` por
# mera coincidencia de texto. Eso ya no puede ocurrir.
TIPO_NUPRE = "NUPRE"
TIPO_NUMERO_PREDIAL = "NUMERO_PREDIAL"
TIPO_MUNICIPAL_KEY = "MUNICIPAL_KEY"
TIPO_RELACION_OFICIAL = "RELACION_OFICIAL"
TIPO_DIRECCION_LIGADA = "DIRECCION_LIGADA"
TIPO_NUMERO_PREDIAL_ANTERIOR = "NUMERO_PREDIAL_ANTERIOR"
TIPO_DESCONOCIDO = "UNKNOWN"

TIPOS_IDENTIFICADOR = (TIPO_NUPRE, TIPO_NUMERO_PREDIAL, TIPO_MUNICIPAL_KEY,
                       TIPO_RELACION_OFICIAL, TIPO_DIRECCION_LIGADA,
                       TIPO_NUMERO_PREDIAL_ANTERIOR, TIPO_DESCONOCIDO)

# ── compatibilidad declarada: cada CAMPO del servicio pertenece a UN solo tipo ──
CAMPO_A_TIPO = {
    "nupre": TIPO_NUPRE,
    "codigo_homologado": TIPO_NUPRE,
    "numero_predial": TIPO_NUMERO_PREDIAL,
    "numero_predial_nacional": TIPO_NUMERO_PREDIAL,
    "numero_predial_anterior": TIPO_NUMERO_PREDIAL_ANTERIOR,
    "municipal_key": TIPO_MUNICIPAL_KEY,
    "guid": TIPO_RELACION_OFICIAL,
    "globalid": TIPO_RELACION_OFICIAL,
    "predio_guid": TIPO_RELACION_OFICIAL,
    "direccion": TIPO_DIRECCION_LIGADA,
}
# Campos admisibles por tipo: nunca se cruzan entre tipos distintos.
TIPO_A_CAMPOS = {t: tuple(sorted(c for c, tt in CAMPO_A_TIPO.items() if tt == t))
                 for t in TIPOS_IDENTIFICADOR if t != TIPO_DESCONOCIDO}
# Pares declarados INCOMPATIBLES (documentación ejecutable: la prueba los verifica).
PARES_INCOMPATIBLES_DECLARADOS = (
    (TIPO_NUPRE, TIPO_NUMERO_PREDIAL),
    (TIPO_NUMERO_PREDIAL, TIPO_NUPRE),
    (TIPO_NUPRE, TIPO_NUMERO_PREDIAL_ANTERIOR),
    (TIPO_NUMERO_PREDIAL, TIPO_NUMERO_PREDIAL_ANTERIOR),
    (TIPO_MUNICIPAL_KEY, TIPO_NUPRE),
    (TIPO_MUNICIPAL_KEY, TIPO_NUMERO_PREDIAL),
    (TIPO_DIRECCION_LIGADA, TIPO_NUPRE),
    (TIPO_RELACION_OFICIAL, TIPO_NUMERO_PREDIAL),
)
# Tipo que DECLARA cada argumento del resolutor de binding.
TIPO_POR_SLOT = {
    "nupre": TIPO_NUPRE,
    "codigo_homologado": TIPO_NUPRE,
    "numero_predial": TIPO_NUMERO_PREDIAL,
    "municipal_key": TIPO_MUNICIPAL_KEY,
    "direccion_ligada": TIPO_DIRECCION_LIGADA,
    "relacion_oficial": TIPO_RELACION_OFICIAL,
}
# ── formas DECLARADAS: heurística explícita de clasificación por FORMA ────────
FORMATO_NUPRE = r"^A[A-Z]{2}[A-Z0-9]{4,}$"                # p. ej. AFT0005BOHA
FORMATO_NUMERO_PREDIAL = r"^[0-9]{22,30}$"                # predial nacional 22-30 dígitos
FORMATO_MUNICIPAL_KEY = r"^[0-9]{5}[-_][0-9A-Z]{3,}$"     # DANE (5 dígitos) + clave
FORMATO_RELACION_OFICIAL = r"^[0-9A-F]{32}$"              # GUID/GlobalID (32 hex)
FORMATOS_POR_TIPO = {
    TIPO_NUPRE: FORMATO_NUPRE,
    TIPO_NUMERO_PREDIAL: FORMATO_NUMERO_PREDIAL,
    TIPO_MUNICIPAL_KEY: FORMATO_MUNICIPAL_KEY,
    TIPO_RELACION_OFICIAL: FORMATO_RELACION_OFICIAL,
}
# Tipos que NO se infieren por forma: una dirección es texto libre (inferirla
# produciría falsos positivos) y el número predial ANTERIOR comparte la forma del
# vigente sin poder distinguirse de él. Ambos exigen declaración explícita.
TIPOS_NO_INFERIBLES_POR_FORMA = (TIPO_DIRECCION_LIGADA, TIPO_NUMERO_PREDIAL_ANTERIOR)

# ── §19 · niveles de confianza de fachada ─────────────────────────────────────
FACADE_VIEW_VERIFIED = "FACADE_VIEW_VERIFIED"
FACADE_VIEW_PROBABLE = "FACADE_VIEW_PROBABLE"
FACADE_VIEW_CONTEXTUAL = "FACADE_VIEW_CONTEXTUAL"
NO_IMAGE_AVAILABLE = "NO_IMAGE_AVAILABLE"
NIVELES_FACHADA = (FACADE_VIEW_VERIFIED, FACADE_VIEW_PROBABLE, FACADE_VIEW_CONTEXTUAL,
                   NO_IMAGE_AVAILABLE)

# ── §22 · exposición solar de fachada ─────────────────────────────────────────
DIRECT_EXPOSURE_LIKELY = "DIRECT_EXPOSURE_LIKELY"
OBLIQUE_EXPOSURE = "OBLIQUE_EXPOSURE"
FACADE_SHADED_OR_REARWARD = "FACADE_SHADED_OR_REARWARD"
INSUFFICIENT_GEOMETRY = "INSUFFICIENT_GEOMETRY"
ESTADOS_EXPOSICION = (DIRECT_EXPOSURE_LIKELY, OBLIQUE_EXPOSURE,
                      FACADE_SHADED_OR_REARWARD, INSUFFICIENT_GEOMETRY)

ETIQUETA_ANALISIS_SOLAR = "ANÁLISIS SOLAR AUTOMATIZADO DE LA FACHADA VISIBLE"


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(texto: Any) -> str:
    t = unicodedata.normalize("NFKD", str(texto or ""))
    return " ".join(t.encode("ascii", "ignore").decode().upper().split())


def hash_canonico(payload: Any) -> str:
    """`content_hash` de la evidencia (§28): canónico y estable."""
    if isinstance(payload, (bytes, bytearray)):
        return hashlib.sha256(bytes(payload)).hexdigest()
    crudo = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                       default=str)
    return hashlib.sha256(crudo.encode("utf-8")).hexdigest()


# ── §27 · contrato de resultado ───────────────────────────────────────────────
def resultado(source_id: str, status: str, *, query_id: str = "",
              payload_normalized: Any = None, raw: Any = None, queried_at: str = "",
              binding_status: str = SIN_BINDING, provenance: Optional[Dict] = None,
              result_count: Optional[int] = None, detail: str = "",
              raw_path: Optional[Path] = None) -> Dict[str, Any]:
    """`SourceResult` de §27. Todo resultado lleva procedencia y hash de la respuesta."""
    if status not in ESTADOS:
        status = CONSULTA_FALLIDA            # estado no declarado = fallo declarado
    if result_count is None:
        result_count = (len(payload_normalized)
                        if isinstance(payload_normalized, (list, tuple, dict)) else 0)
    return {
        "source_id": source_id,
        "query_id": query_id or f"QRY-{source_id}-{hash_canonico([source_id, queried_at,
                                                                    provenance])[:12]}",
        "status": status,
        "queried_at": queried_at or ahora(),
        "raw_hash": hash_canonico(raw) if raw is not None else None,
        "result_count": int(result_count),
        "binding_status": binding_status,
        "payload_normalized": payload_normalized,
        "provenance": dict(provenance or {}),
        "detail": detail,
        "raw_persisted": bool(raw_path),
        "raw_path": str(raw_path.relative_to(RAIZ)) if raw_path else None,
    }


def preservar_raw(source_id: str, raw: Any, *, destino: Optional[Path] = None,
                  licencia: Optional[Dict] = None) -> Optional[Path]:
    """§28 · guarda la respuesta CRUDA sin modificar, si la licencia lo permite.

    Devuelve la ruta escrita (o None si el proveedor no permite persistir). El objeto
    normalizado se construye por separado: aquí no se toca ni se corrige el crudo.
    """
    politica = licencia or {}
    if politica and politica.get("can_persist_raw") is False:
        return None
    carpeta = Path(destino or DIR_RAW)
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"{source_id.lower()}.json"
    if isinstance(raw, (bytes, bytearray)):
        ruta.write_bytes(bytes(raw))
    else:
        ruta.write_text(json.dumps(raw, ensure_ascii=False, indent=1, sort_keys=False,
                                   default=str), encoding="utf-8")
    return ruta


def consultar(fuente: Dict[str, Any], ejecutar: Callable[[], Any], *,
              persistir: bool = True, destino_raw: Optional[Path] = None,
              binding_status: str = SIN_BINDING,
              normalizar: Optional[Callable[[Any], Any]] = None,
              vacio_significa_sin_coincidencia: Optional[bool] = None) -> Dict[str, Any]:
    """Ejecuta una consulta y la envuelve en el contrato §27.

    `ejecutar` debe devolver la respuesta cruda. Los fallos NO se silencian:
      · excepción                    → QUERY_FAILED
      · lista vacía                  → NO_MATCH (solo si la fuente consultada CONTESTÓ)
      · fuente deshabilitada/sin URL → NOT_SUPPORTED
      · `failure_semantics` del registro decide qué significa «sin dato».
    """
    sid = str(fuente.get("source_id") or "SIN_ID")
    prov = {"source_id": sid, "source_name": fuente.get("source_name"),
            "institution": fuente.get("institution"),
            "authority_class": fuente.get("authority_class"),
            "service": fuente.get("service"), "layer_id": fuente.get("layer_id"),
            "query_method": fuente.get("query_method"),
            "version_or_vigency": fuente.get("version_or_vigency"),
            "precedence": fuente.get("precedence"),
            "license_or_terms": fuente.get("license_or_terms")}
    if fuente.get("enabled") is False:
        return resultado(sid, NO_SOPORTADA, provenance=prov,
                         detail="La fuente está deshabilitada en el Source Pack.",
                         binding_status=binding_status)
    try:
        crudo = ejecutar()
    except Exception as exc:  # noqa: BLE001 — el fallo es un estado, no una excepción
        return resultado(sid, CONSULTA_FALLIDA, provenance=prov,
                         detail=f"Fallo de consulta: {type(exc).__name__}: {exc}",
                         binding_status=binding_status)
    if crudo is None:
        estado = FUENTE_NO_DISPONIBLE
        sem = str(fuente.get("failure_semantics") or "").upper()
        if "NOT_SUPPORTED" in sem:
            estado = NO_SOPORTADA
        return resultado(sid, estado, provenance=prov,
                         detail="La fuente no devolvió respuesta utilizable.",
                         binding_status=binding_status)
    ruta = preservar_raw(sid, crudo, destino=destino_raw,
                         licencia={"can_persist_raw": fuente.get("can_persist_raw", True)}) \
        if persistir else None
    normalizado = normalizar(crudo) if normalizar else crudo
    _vacio = (isinstance(normalizado, (list, tuple, dict)) and len(normalizado) == 0)
    if _vacio:
        permite_nm = (fuente.get("puede_responder_sin_coincidencia", True)
                      if vacio_significa_sin_coincidencia is None
                      else vacio_significa_sin_coincidencia)
        estado = SIN_COINCIDENCIA if permite_nm else FUENTE_NO_DISPONIBLE
        return resultado(sid, estado, raw=crudo, payload_normalized=normalizado,
                         provenance=prov, raw_path=ruta,
                         detail=("La fuente respondió sin coincidencias." if permite_nm
                                 else "La fuente respondió sin dato y no puede afirmarse "
                                      "ausencia."),
                         binding_status=binding_status)
    return resultado(sid, DISPONIBLE, raw=crudo, payload_normalized=normalizado,
                     provenance=prov, raw_path=ruta, binding_status=binding_status)


# ── §6 · binding tipado: tipado, saneado por tipo, clasificación y cotejo ──────
def tipos_compatibles(tipo_identificador: str, tipo_campo: str) -> bool:
    """CONTRATO de compatibilidad: un identificador SOLO casa con campos de SU tipo.

    `NUPRE` NUNCA es compatible con `NUMERO_PREDIAL` (ni al revés) aunque el texto
    normalizado coincida; `NUMERO_PREDIAL` tampoco con `NUMERO_PREDIAL_ANTERIOR`
    (un número anterior identifica a otro predio). `UNKNOWN` no es compatible con
    nada: un tipo no determinable NO se compara a ciegas.
    """
    a, b = str(tipo_identificador or ""), str(tipo_campo or "")
    if not a or not b or TIPO_DESCONOCIDO in (a, b):
        return False
    return a == b


def normalizar_por_tipo(valor: Any, tipo: str) -> str:
    """Saneado ESPECÍFICO por tipo: no existe una normalización única que cruce tipos.

    NUPRE / clave municipal → alfanumérico sin separadores (mayúsculas, sin acentos).
    Número predial → SOLO dígitos (nunca se compara con texto). Relación oficial →
    GUID/GlobalID sin llaves ni guiones. Dirección ligada → texto normalizado.
    UNKNOWN → cadena vacía: no hay valor comparable, luego no se compara.
    """
    if tipo == TIPO_DESCONOCIDO:
        return ""
    texto = "" if valor is None else str(valor)
    if tipo in (TIPO_NUMERO_PREDIAL, TIPO_NUMERO_PREDIAL_ANTERIOR):
        # Un número predial NO contiene letras: si las trae, no es comparable como
        # predial (evita que «AFT0005BOHA» se coteje como «0005»).
        if re.search(r"[A-Za-z]", texto):
            return ""
        return re.sub(r"[^0-9]", "", texto)
    if tipo == TIPO_DIRECCION_LIGADA:
        return _norm(texto)
    return re.sub(r"[^0-9A-Z]", "", _norm(texto))


def clasificar_identificador(valor: Any) -> str:
    """Clasifica un valor por su FORMA con las formas DECLARADAS de arriba.

    Orden de la heurística (del formato más específico al más genérico):
      1. clave municipal  = 5 dígitos DANE + '-'/'_' + clave alfanumérica,
      2. número predial   = 22-30 dígitos,
      3. relación oficial = GUID/GlobalID (32 hex, con o sin guiones/llaves),
      4. NUPRE            = prefijo alfabético tipo AFT/AAA… + ≥4 alfanuméricos.
    Si nada casa → `UNKNOWN` y el valor NO se compara (jamás a ciegas).
    """
    if valor is None or not str(valor).strip():
        return TIPO_DESCONOCIDO
    crudo = _norm(valor)
    limpio = re.sub(r"[^0-9A-Z]", "", crudo)
    if not limpio:
        return TIPO_DESCONOCIDO
    if re.match(FORMATO_MUNICIPAL_KEY, crudo.replace(" ", "")):
        return TIPO_MUNICIPAL_KEY
    if re.match(FORMATO_NUMERO_PREDIAL, limpio):
        return TIPO_NUMERO_PREDIAL
    if re.match(FORMATO_RELACION_OFICIAL, limpio):
        return TIPO_RELACION_OFICIAL
    if re.match(FORMATO_NUPRE, limpio):
        return TIPO_NUPRE
    return TIPO_DESCONOCIDO


def resolver_tipo_identificador(valor: Any, *, slot: str = "") -> Dict[str, Any]:
    """Tipo EFECTIVO de un identificador entrante: forma + declaración del llamador.

    · forma determinable y coherente con la declaración → ese tipo;
    · forma determinable y CONTRADICTORIA con la declaración → `UNKNOWN` (conflicto
      de tipo: PROHIBIDO comparar; no se liga aunque el texto coincida);
    · forma no concluyente → tipo DECLARADO por el llamador (la declaración manda:
      p. ej. `numero_predial="0800"` sigue siendo un número predial);
    · sin forma concluyente NI declaración → `UNKNOWN` y no se compara.
    """
    forma = clasificar_identificador(valor)
    declarado = TIPO_POR_SLOT.get(str(slot or ""), TIPO_DESCONOCIDO)
    conflicto = bool(forma != TIPO_DESCONOCIDO and declarado != TIPO_DESCONOCIDO
                     and forma != declarado)
    if conflicto:
        tipo = TIPO_DESCONOCIDO
        motivo = (f"CONFLICTO DE TIPO: el valor tiene forma de {forma} pero se declaró "
                  f"como {declarado}. PROHIBIDO comparar: no se liga.")
    elif forma != TIPO_DESCONOCIDO:
        tipo = forma
        motivo = f"Tipo determinado por la FORMA del valor: {forma}."
    elif declarado != TIPO_DESCONOCIDO:
        tipo = declarado
        motivo = (f"Forma no concluyente; se usa el tipo DECLARADO por el llamador: "
                  f"{declarado}.")
    else:
        tipo = TIPO_DESCONOCIDO
        motivo = ("Tipo NO determinable (ni por forma ni por declaración): el valor NO "
                  "se compara a ciegas.")
    normalizado = normalizar_por_tipo(valor, tipo)
    return {"identifier_type": tipo, "value_normalized": normalizado,
            "shape_identifier_type": forma, "declared_identifier_type": declarado,
            "type_conflict": conflicto,
            "comparable": bool(tipo != TIPO_DESCONOCIDO and normalizado),
            "reason": motivo}


def _cotejar_por_tipo(atributos: Sequence[Dict[str, Any]], tipo: str,
                      valor_normalizado: str) -> List[tuple]:
    """Coteja `valor_normalizado` SOLO contra los campos del mismo `tipo`.

    Devuelve `[(indice, campo, atributo)]`. Un tipo desconocido o un valor sin nada
    que comparar devuelven lista vacía: no hay comparación cruzada posible.
    """
    if tipo == TIPO_DESCONOCIDO or not valor_normalizado:
        return []
    campos = TIPO_A_CAMPOS.get(tipo, ())
    hallados: List[tuple] = []
    for indice, atributo in enumerate(atributos):
        for campo in campos:
            actual = normalizar_por_tipo(atributo.get(campo), tipo)
            if actual and actual == valor_normalizado:
                hallados.append((indice, campo, atributo))
    return hallados


def _desempatar_por_hash(hallados: Sequence[tuple]) -> tuple:
    """Desempate ESTABLE, nunca por posición: hash canónico de la fila y luego campo."""
    return sorted(hallados, key=lambda h: (hash_canonico(h[2]), str(h[1]), h[0]))[0]


def _resultado_binding(feature: Optional[Dict[str, Any]], binding_status: str, *,
                       identifier_type: str, matched_field: Optional[str],
                       feature_hash: str, intentos: List[Dict[str, Any]], matches: int,
                       reason: str) -> Dict[str, Any]:
    """Resultado del binding: declara SIEMPRE el tipo y el campo usados (§6 tipado)."""
    return {"feature": feature, "feature_hash": feature_hash,
            "binding_status": binding_status, "identifier_type": identifier_type,
            "matched_field": matched_field, "matches_found": int(matches),
            "ambiguous_match": bool(matches > 1),
            "attempted_identifiers": list(intentos),
            "spatial_used_as_identity": False, "silent_choice": False,
            "reason": reason}


def elegir_predio_canonico(features: Sequence[Dict[str, Any]], *,
                           nupre: str = "", numero_predial: str = "",
                           codigo_homologado: str = "", municipal_key: str = "",
                           relacionados: Optional[Iterable[Any]] = None,
                           direccion_ligada: str = "") -> Dict[str, Any]:
    """Resuelve el predio por IDENTIFICADORES CANÓNICOS TIPADOS y relaciones OFICIALES.

    Precedencia (§6): NUPRE/código homologado → número predial → clave municipal →
    relación oficial → dirección ligada. Cada identificador se coteja SOLO contra los
    campos de SU tipo: NUNCA NUPRE ↔ numero_predial, ni siquiera cuando el texto
    normalizado coincide. El orden de las features no decide nada: si varias filas
    casan con el mismo identificador se desempata por hash canónico y se declara
    (`ambiguous_match`). La coincidencia ESPACIAL es CONTEXTO y jamás autoriza
    identidad; `features[0]` no se elige nunca. El resultado declara el
    `identifier_type` y el `matched_field` usados, o `UNKNOWN` + `None` si nada ligó.
    """
    atributos = [dict(f.get("attributes") or f) for f in (features or [])
                 if isinstance(f, dict)]
    intentos: List[Dict[str, Any]] = []

    def _intento_identificador(slot: str, valor: Any,
                               modo: str) -> Optional[Dict[str, Any]]:
        info = resolver_tipo_identificador(valor, slot=slot)
        hallados = _cotejar_por_tipo(atributos, info["identifier_type"],
                                     info["value_normalized"])
        intento = {"origin": slot, "normalized_value": info["value_normalized"],
                   "shape_identifier_type": info["shape_identifier_type"],
                   "declared_identifier_type": info["declared_identifier_type"],
                   "identifier_type": info["identifier_type"],
                   "type_conflict": info["type_conflict"],
                   "fields_allowed": list(TIPO_A_CAMPOS.get(info["identifier_type"], ())),
                   "matches": len(hallados), "motivo": info["reason"]}
        intentos.append(intento)
        if not hallados:
            return None
        _, campo, atributo = _desempatar_por_hash(hallados)
        intento["matched_field"] = campo
        return _resultado_binding(
            atributo, modo, identifier_type=info["identifier_type"], matched_field=campo,
            feature_hash=hash_canonico(atributo), intentos=intentos, matches=len(hallados),
            reason=(f"Coincidencia EXACTA de `{campo}` con el identificador canónico "
                    f"TIPADO {info['identifier_type']} (origen: {slot}); cotejado solo "
                    f"contra {list(TIPO_A_CAMPOS.get(info['identifier_type'], ()))}."))

    # 1 · identificadores canónicos, en el orden declarado de §6
    for slot, valor, modo in (("codigo_homologado", codigo_homologado, BINDING_NUPRE),
                              ("nupre", nupre, BINDING_NUPRE),
                              ("numero_predial", numero_predial, BINDING_PREDIAL),
                              ("municipal_key", municipal_key, BINDING_MUNICIPAL_KEY)):
        if not str(valor or "").strip():
            continue
        resuelto = _intento_identificador(slot, valor, modo)
        if resuelto:
            return resuelto

    # 2 · relaciones OFICIALES declaradas por el SERVICIO: la referencia viene del
    #     propio servicio como enlace de predio relacionado. Se coteja contra las
    #     columnas de relación oficial (guid/globalid/predio_guid) y, si su forma
    #     identifica un tipo canónico, también contra ESE tipo — nunca contra tipos
    #     incompatibles (p. ej. una referencia no se liga por `numero_predial`).
    refs = [r for r in (relacionados or []) if str(r or "").strip()]
    hallados_rel: List[tuple] = []
    for ref in refs:
        forma = clasificar_identificador(ref)
        tipos = [TIPO_RELACION_OFICIAL]
        if forma != TIPO_DESCONOCIDO and forma != TIPO_RELACION_OFICIAL:
            tipos.append(forma)
        intento = {"origin": "relacionados", "normalized_value": str(ref),
                   "shape_identifier_type": forma,
                   "declared_identifier_type": TIPO_RELACION_OFICIAL,
                   "identifier_type": TIPO_RELACION_OFICIAL,
                   "type_conflict": False,
                   "fields_allowed": [c for t in tipos
                                      for c in TIPO_A_CAMPOS.get(t, ())],
                   "matches": 0,
                   "motivo": ("Referencia declarada por el servicio como relación "
                              f"oficial; forma del valor: {forma}. Cotejada solo contra "
                              "las columnas de relación oficial"
                              + (f" y del tipo {forma}" if len(tipos) > 1 else "")
                              + ".")}
        coincidencias_ref = 0
        for tipo in tipos:
            coincidencias = _cotejar_por_tipo(atributos, tipo,
                                              normalizar_por_tipo(ref, tipo))
            for indice, campo, atributo in coincidencias:
                hallados_rel.append((indice, campo, atributo, tipo))
            coincidencias_ref += len(coincidencias)
            if coincidencias:
                intento["identifier_type"] = tipo
        intento["matches"] = coincidencias_ref
        intentos.append(intento)
    if hallados_rel:
        _, campo, atributo, tipo_ref = sorted(
            hallados_rel, key=lambda h: (hash_canonico(h[2]), str(h[1]), h[0]))[0]
        return _resultado_binding(
            atributo, BINDING_RELACION, identifier_type=tipo_ref, matched_field=campo,
            feature_hash=hash_canonico(atributo), intentos=intentos,
            matches=len(hallados_rel),
            reason=("Enlace por la relación OFICIAL declarada por el servicio "
                    f"(campo `{campo}`); la referencia se cotejó solo contra campos "
                    f"de tipo compatible ({tipo_ref})."))

    # 3 · dirección ligada al predio POR EL SERVICIO (último recurso, tipo propio)
    if str(direccion_ligada or "").strip():
        resuelto = _intento_identificador("direccion_ligada", direccion_ligada,
                                          BINDING_DIRECCION)
        if resuelto:
            resuelto["reason"] = ("Dirección oficial ligada al predio por el propio "
                                  "servicio (campo `direccion`).")
            return resuelto

    return _resultado_binding(
        None, SIN_BINDING, identifier_type=TIPO_DESCONOCIDO, matched_field=None,
        feature_hash="", intentos=intentos, matches=0,
        reason=("Ningún identificador canónico TIPADO ni relación oficial resolvió el "
                "predio. NO se elige features[0]: la coincidencia espacial es CONTEXTO "
                f"({BINDING_ESPACIAL_CONTEXTO}) y no autoriza identidad."))


def identidad_autorizada_por_binding(binding_status: str) -> bool:
    """Solo un binding canónico/relacional autoriza usar el predio como identidad."""
    return str(binding_status) in BINDINGS_QUE_AUTORIZAN_IDENTIDAD


# ── §12 · precedencia de riesgo: selección DETERMINISTA (no depende del orden) ─
PRECEDENCIA_RESUELTA = "RESOLVED_CURRENT_SOURCE"
PRECEDENCIA_AMBIGUA = "AMBIGUOUS_CURRENT_SOURCE"
SIN_DATO = "SIN_DATO"


def _nivel_de_precedencia(candidato: Dict[str, Any]) -> str:
    return str((candidato or {}).get("precedence") or HISTORICAL_REFERENCE).upper()


def _prioridad_declarada(candidato: Dict[str, Any]) -> Optional[int]:
    """`source_priority` EXPLÍCITO (entero, menor = mayor prioridad). Si no se declara
    o no es un entero, devuelve None: no se inventa jerarquía."""
    valor = (candidato or {}).get("source_priority")
    if isinstance(valor, bool) or valor is None:
        return None
    if isinstance(valor, int):
        return valor
    if isinstance(valor, str) and valor.strip().lstrip("+-").isdigit():
        return int(valor.strip())
    return None


def _orden_estable(candidato: Dict[str, Any]) -> tuple:
    """Clave de orden canónica: nivel, prioridad declarada, source_id y hash de la
    candidata. Garantiza que ninguna salida dependa del orden de entrada."""
    nivel = _nivel_de_precedencia(candidato)
    escala = (PRECEDENCIA_RIESGO.index(nivel) if nivel in PRECEDENCIA_RIESGO
              else len(PRECEDENCIA_RIESGO))
    prioridad = _prioridad_declarada(candidato)
    return (escala, 10 ** 9 if prioridad is None else prioridad,
            str(candidato.get("source_id") or ""), hash_canonico(candidato))


def _desempatar_por_prioridad(grupo: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Elige UNA candidata de un nivel homogéneo, sin mirar el orden de entrada.

    · una sola candidata → se selecciona (aunque no declare `source_priority`);
    · varias → `source_priority` menor gana; empate o prioridad NO declarada →
      ambigüedad declarada, NUNCA una elección silenciosa.
    """
    if len(grupo) == 1:
        return {"winner": grupo[0], "ambiguous": [], "priority": _prioridad_declarada(
            grupo[0]), "reason": "Única candidata declarada en el nivel de precedencia."}
    prioridades = [_prioridad_declarada(c) for c in grupo]
    if any(p is None for p in prioridades):
        return {"winner": None, "ambiguous": list(grupo), "priority": None,
                "reason": (f"{len(grupo)} candidatas de precedencia equivalente y alguna "
                           "NO declara `source_priority`: no puede desempatarse sin "
                           "inventar jerarquía.")}
    minima = min(prioridades)
    finalistas = [c for c, p in zip(grupo, prioridades) if p == minima]
    if len(finalistas) == 1:
        return {"winner": finalistas[0], "ambiguous": [], "priority": minima,
                "reason": (f"`source_priority` explícito ({minima}) desempata de forma "
                           f"estable entre {len(grupo)} candidatas equivalentes.")}
    return {"winner": None, "ambiguous": list(finalistas), "priority": minima,
            "reason": (f"EMPATE de `source_priority` ({minima}) entre "
                       f"{len(finalistas)} candidatas equivalentes: no se elige ninguna "
                       "en silencio.")}


def resolver_precedencia(candidatos: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Selecciona la fuente de riesgo VIGENTE sin depender del orden de entrada.

    Regla declarada (§12):
      1. si hay EXACTAMENTE una CURRENT_NORMATIVE → se selecciona;
      2. si hay VARIAS → desempata `source_priority` explícito (menor = mayor
         prioridad); empate, o prioridad no declarada, → `AMBIGUOUS_CURRENT_SOURCE`;
      3. sin CURRENT_NORMATIVE utilizable → la MISMA regla sobre CURRENT_OFFICIAL;
      4. sin ninguna de las dos → `selected=None`, status `SIN_DATO`.
    Las HISTORICAL_REFERENCE se conservan SOLO como referencia comparativa: nunca se
    ascienden. Devuelve siempre `selected`, `displaced`, `precedence_order`, `status`,
    `ambiguous_candidates`, `reason` y `silent_override=False`.
    """
    entradas = [(i, dict(c)) for i, c in enumerate(candidatos or [])
                if isinstance(c, dict)]
    historicas = sorted([c for _, c in entradas
                         if _nivel_de_precedencia(c) == HISTORICAL_REFERENCE],
                        key=_orden_estable)
    seleccionado: Optional[Dict[str, Any]] = None
    indice_elegido: Optional[int] = None
    ambiguos: List[Dict[str, Any]] = []
    nivel_usado: Optional[str] = None
    prioridad_usada: Optional[int] = None
    motivo_nivel = ""

    for nivel in (CURRENT_NORMATIVE, CURRENT_OFFICIAL):
        grupo = sorted([c for _, c in entradas if _nivel_de_precedencia(c) == nivel],
                       key=_orden_estable)
        if not grupo:
            continue
        nivel_usado = nivel
        veredicto = _desempatar_por_prioridad(grupo)
        motivo_nivel = veredicto["reason"]
        if veredicto["winner"] is None:
            ambiguos = sorted(veredicto["ambiguous"], key=_orden_estable)
            prioridad_usada = veredicto["priority"]
            break
        seleccionado = veredicto["winner"]
        prioridad_usada = veredicto["priority"]
        indice_elegido = next(i for i, c in entradas if c is seleccionado)
        break

    desplazados = sorted([c for i, c in entradas
                          if indice_elegido is None or i != indice_elegido],
                         key=_orden_estable)
    if seleccionado is not None:
        estado = PRECEDENCIA_RESUELTA
        motivo = (f"Precedencia {nivel_usado}: {motivo_nivel} La capa vigente "
                  "(Decreto 893 de 2024) manda sobre las históricas; las capas "
                  "anteriores se conservan como referencia comparativa y se declaran en "
                  "`displaced`. Ninguna capa histórica sustituye a la vigente en "
                  "silencio.")
    elif ambiguos:
        estado = PRECEDENCIA_AMBIGUA
        motivo = (f"AMBIGUOUS_CURRENT_SOURCE en el nivel {nivel_usado}: {motivo_nivel} "
                  "No se selecciona ninguna: se declaran las candidatas ambiguas y se "
                  "conservan las históricas solo como referencia comparativa.")
    else:
        estado = SIN_DATO
        motivo = ("No hay capa vigente (CURRENT_NORMATIVE) ni oficial vigente "
                  "(CURRENT_OFFICIAL) utilizables: se declara SIN DATO. Las capas "
                  "históricas se conservan SOLO como referencia comparativa y NO se "
                  "ascienden nunca.")
    return {
        "selected": seleccionado,
        "selected_source_id": (seleccionado or {}).get("source_id"),
        "selected_tier": nivel_usado if seleccionado is not None else None,
        "source_priority_used": prioridad_usada,
        "displaced": desplazados,
        "historical_reference": historicas,
        "precedence_order": list(PRECEDENCIA_RIESGO),
        "status": estado,
        "ambiguous_candidates": ambiguos,
        "ambiguous_tier": nivel_usado if ambiguos else None,
        "reason": motivo,
        "silent_override": False,
    }


# ── §E · riesgo Barranquilla: vigentes (Decreto 893 de 2024) vs históricas ─────
NORMA_POT_2024 = "Decreto 893 de 2024"
_MOTIVO_VIGENTE = ("Capa vigente del POT adoptado por el " + NORMA_POT_2024 +
                   ": sostiene la afirmación normativa de riesgo.")
_MOTIVO_HISTORICA = ("Versión ANTERIOR del POT: referencia comparativa DECLARADA. No es "
                     "vigente y nunca se asciende a vigente.")
# `source_priority` declarado: orden de evaluación cuando varias capas VIGENTES
# compiten por la misma pregunta. Menor = mayor prioridad. Las desplazadas no se
# descartan: quedan declaradas en `displaced`. Cada amenaza se resuelve con su propia
# capa vigente (`candidatos_riesgo_barranquilla(amenaza=...)`).
_RIESGO_BARRANQUILLA: tuple = (
    {"source_id": "POT_BAQ_REMOCION_2024", "layer_id": 73, "amenaza": "REMOCION_EN_MASA",
     "precedence": CURRENT_NORMATIVE, "source_priority": 10,
     "legal_or_normative_context": NORMA_POT_2024,
     "version_or_vigency": NORMA_POT_2024 + " (capa vigente)",
     "referencia_de": None, "motivo": _MOTIVO_VIGENTE + " Amenaza por remoción en masa."},
    {"source_id": "POT_BAQ_INUNDACION_2024", "layer_id": 77, "amenaza": "INUNDACION",
     "precedence": CURRENT_NORMATIVE, "source_priority": 20,
     "legal_or_normative_context": NORMA_POT_2024,
     "version_or_vigency": NORMA_POT_2024 + " (capa vigente)",
     "referencia_de": None, "motivo": _MOTIVO_VIGENTE + " Amenaza por inundación."},
    {"source_id": "POT_BAQ_RIESGO_2024", "layer_id": 81, "amenaza": "RIESGO_MULTIPLE",
     "precedence": CURRENT_NORMATIVE, "source_priority": 30,
     "legal_or_normative_context": NORMA_POT_2024,
     "version_or_vigency": NORMA_POT_2024 + " (capa vigente)",
     "referencia_de": None, "motivo": _MOTIVO_VIGENTE + " Áreas en riesgo (compuesto)."},
    {"source_id": "POT_BAQ_REMOCION_HIST", "layer_id": 71, "amenaza": "REMOCION_EN_MASA",
     "precedence": HISTORICAL_REFERENCE, "source_priority": 90,
     "legal_or_normative_context": "POT anterior (no vigente)",
     "version_or_vigency": "POT anterior (referencia comparativa)",
     "referencia_de": "POT_BAQ_REMOCION_2024",
     "motivo": _MOTIVO_HISTORICA + " Compara contra POT_BAQ_REMOCION_2024."},
    {"source_id": "POT_BAQ_INUNDACION_HIST", "layer_id": 75, "amenaza": "INUNDACION",
     "precedence": HISTORICAL_REFERENCE, "source_priority": 91,
     "legal_or_normative_context": "POT anterior (no vigente)",
     "version_or_vigency": "POT anterior (referencia comparativa)",
     "referencia_de": "POT_BAQ_INUNDACION_2024",
     "motivo": _MOTIVO_HISTORICA + " Compara contra POT_BAQ_INUNDACION_2024."},
    {"source_id": "POT_BAQ_RIESGO_HIST", "layer_id": 79, "amenaza": "RIESGO_MULTIPLE",
     "precedence": HISTORICAL_REFERENCE, "source_priority": 92,
     "legal_or_normative_context": "POT anterior (no vigente)",
     "version_or_vigency": "POT anterior (referencia comparativa)",
     "referencia_de": "POT_BAQ_RIESGO_2024",
     "motivo": _MOTIVO_HISTORICA + " Compara contra POT_BAQ_RIESGO_2024."},
)


def candidatos_riesgo_barranquilla(*, amenaza: str = "") -> List[Dict[str, Any]]:
    """Candidatas de riesgo del pack con `precedence` y `source_priority` EXPLÍCITOS.

    Vigentes (Decreto 893 de 2024): 73 remoción en masa, 77 inundación, 81 áreas en
    riesgo. Históricas conservadas para comparación: 71, 75, 79. Las históricas NUNCA
    son candidatas a vigente: `resolver_precedencia` no las selecciona jamás.
    `amenaza` filtra por familia de amenaza (REMOCION_EN_MASA | INUNDACION |
    RIESGO_MULTIPLE) para resolver cada pregunta con su propia capa vigente.
    Devuelve copias: mutar el resultado no altera el estado del módulo.
    """
    filtro = _norm(amenaza)
    return [dict(c) for c in _RIESGO_BARRANQUILLA
            if not filtro or _norm(c["amenaza"]) == filtro]


# ── §15 · dos niveles de equipamiento que NO se mezclan ───────────────────────
def separar_equipamiento(resultados: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """`official_equipment` (autoridad oficial) vs `contextual_services` (OSM y similares)."""
    oficial, contextual = {}, {}
    for sid, res in (resultados or {}).items():
        clase = str(((res.get("provenance") or {}).get("authority_class") or "")).upper()
        if clase == AUTORITATIVA_OFICIAL:
            oficial[sid] = res
        elif clase in (CONTEXTUAL_EXTERNA, CALCULADA):
            contextual[sid] = res
    return {"official_equipment": oficial, "contextual_services": contextual,
            "mixed_authority": False}


# ── §25 · altura normativa ≠ altura física (regla bloqueante) ─────────────────
def altura_fisica(building_height: Any = None, *, height_source: str = "",
                  altura_normativa_pot: Any = None) -> Dict[str, Any]:
    """Devuelve la altura FÍSICA solo si viene de una fuente automática declarada.

    Regla bloqueante: `POT.altura_max` (altura normativa) NO puede convertirse en altura
    física. Si alguien intenta pasar la normativa como física, se rechaza y se declara.
    """
    intento = str(height_source or "").upper()
    if building_height is not None and not height_source:
        return {"building_physical_height": None, "height_source": None,
                "shadow_confidence": "DEGRADED",
                "reason": "Altura sin fuente declarada: no se acepta como altura física."}
    if building_height is not None and ("POT" in intento or "NORMATIV" in intento
                                        or "EDIFICABILIDAD" in intento):
        return {"building_physical_height": None, "height_source": None,
                "shadow_confidence": "DEGRADED",
                "reason": (f"RECHAZADO: «{height_source}» es altura NORMATIVA "
                           f"({altura_normativa_pot}); POT.altura_max no puede usarse "
                           f"como altura física del edificio."),
                "rejected_source": height_source}
    if building_height is None:
        return {"building_physical_height": None, "height_source": None,
                "shadow_confidence": "DEGRADED",
                "reason": "No hay fuente automática de altura física: no se simula sombra "
                          "con longitud física exacta."}
    return {"building_physical_height": building_height, "height_source": height_source,
            "shadow_confidence": "OK",
            "reason": "Altura física declarada por una fuente automática identificada."}


# ── transporte al run state (§1: SOLO transporte) ─────────────────────────────
def adjuntar_a_run_state(rs: Dict[str, Any], resultados: Dict[str, Dict[str, Any]],
                         *, pack_version: str = PACK_VERSION,
                         manifest_hash: str = "") -> Dict[str, Any]:
    """Añade la evidencia de fuentes al estado de corrida sin tocar la decisión."""
    rs = rs if isinstance(rs, dict) else {}
    rs["source_pack"] = {
        "pack_version": pack_version,
        "registry_version": REGISTRY_VERSION,
        "manifest_hash": manifest_hash or None,
        "generated_at": ahora(),
        "results": resultados,
        "statuses": {sid: (r or {}).get("status") for sid, r in (resultados or {}).items()},
    }
    return rs


def cargar_registro(ruta: Optional[Path] = None) -> Dict[str, Any]:
    """Carga el registro de fuentes (JSON canónico del YAML versionado)."""
    p = Path(ruta or RUTA_REGISTRO)
    if not p.exists():
        return {"registry_version": REGISTRY_VERSION, "sources": {},
                "_status": NO_SOPORTADA, "reason": f"No existe el registro: {p}"}
    return json.loads(p.read_text(encoding="utf-8"))


def fuentes_por_clase(registro: Dict[str, Any], clase: str) -> List[Dict[str, Any]]:
    return [f for f in (registro.get("sources") or {}).values()
            if str(f.get("authority_class")) == clase]

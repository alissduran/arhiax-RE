# -*- coding: utf-8 -*-
"""DICTUS 2.0D — GRAMÁTICA DE DECISIÓN (`RealEstateDecisionEngine`).

Convierte el estado canónico de la corrida en una CADENA EXPLICABLE:

    FUENTE → CONSULTA → EVIDENCIA → OBSERVACIÓN → HALLAZGO →
    RECOMENDACIÓN → COMPUERTA → DISPOSICIÓN → REVISIÓN HUMANA

Principios (tomados de la disciplina de SAGRILAFT, NO de su dominio):

  A. El sistema NO sustituye la decisión humana: puede ordenar, comparar, validar,
     bloquear, autorizar el uso de un dato y recomendar; **no** afirma «compre»,
     «crédito aprobado», «seguro aprobado» ni «título garantizado».
  B. Lo que no se puede probar no se afirma: `SOURCE_UNAVAILABLE`, `NOT_RUN`,
     `QUERY_FAILED` y `CONFLICT` NO son `NO_MATCH`.
  C. Los objetos semánticos NO se mezclan: una observación no es un hallazgo, un
     hallazgo no es una decisión y una decisión no es una disposición humana.

Todo se deriva del `DictusRunState`: este módulo no consulta fuentes ni recalcula
motores. `Observation`, `Finding`, `DecisionGate` y `Disposition` son los objetos que
viajan al modelo, al hash maestro y al documento.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

GRAMMAR_VERSION = "dictus-decision-grammar/1.0.0"

# ── §4 · vocabulario de DECISIÓN (no de severidad) ───────────────────────────
INFORMACION_VERIFICADA = "INFORMACIÓN VERIFICADA"
PROCEDER_CON_CONDICIONES = "PROCEDER CON CONDICIONES"
REVISION_PROFESIONAL_REQUERIDA = "REVISIÓN PROFESIONAL REQUERIDA"
INFORMACION_INSUFICIENTE = "INFORMACIÓN INSUFICIENTE"
NO_USAR_COMO_DEFINITIVO = "NO UTILIZAR ESTE DATO COMO DEFINITIVO"
NO_EMITIR_VALORACION = "NO EMITIR VALORACIÓN"
SIN_HALLAZGO_EN_FUENTE = "SIN HALLAZGO MATERIAL EN ESTA FUENTE"
FUENTE_NO_DISPONIBLE_DEC = "FUENTE NO DISPONIBLE"
EVIDENCIA_EN_CONFLICTO = "EVIDENCIA EN CONFLICTO"

VOCABULARIO_DECISION = (
    INFORMACION_VERIFICADA, PROCEDER_CON_CONDICIONES, REVISION_PROFESIONAL_REQUERIDA,
    INFORMACION_INSUFICIENTE, NO_USAR_COMO_DEFINITIVO, NO_EMITIR_VALORACION,
    SIN_HALLAZGO_EN_FUENTE, FUENTE_NO_DISPONIBLE_DEC, EVIDENCIA_EN_CONFLICTO,
)

# ── §2.B/§11 · estados de OBSERVACIÓN (consulta) ─────────────────────────────
OBSERVADO = "OBSERVED"
NO_MATCH = "NO_MATCH"
NO_CONSULTADO = "NOT_RUN"
FUENTE_NO_DISPONIBLE_OBS = "SOURCE_UNAVAILABLE"
CONSULTA_FALLIDA = "QUERY_FAILED"
CONFLICTO_OBS = "CONFLICT"
NO_EVALUADO = "NOT_EVALUATED"

ESTADOS_OBSERVACION = (OBSERVADO, NO_MATCH, NO_CONSULTADO, FUENTE_NO_DISPONIBLE_OBS,
                       CONSULTA_FALLIDA, CONFLICTO_OBS, NO_EVALUADO)

# ── §30.B · ESTADO DE LA COMPUERTA · vocabulario CERRADO, ortogonal a la decisión ──
# `decision` usa el vocabulario de la GRAMÁTICA DE DECISIÓN («NO EMITIR VALORACIÓN»,
# «NO UTILIZAR ESTE DATO COMO DEFINITIVO», «INFORMACIÓN VERIFICADA»…): dice QUÉ se
# decidió. `gate_state` responde a UNA sola pregunta con DOS únicos valores: ¿la
# compuerta AUTORIZA el uso de lo que gobierna?
#
#     OPEN   → el dominio de la compuerta se puede usar (con sus condiciones declaradas)
#     CLOSED → no se autoriza: no se usa el dato / no se emite la cifra
#
# Los dos campos CONVIVEN y no se sustituyen: un lector (o un checklist) que exija
# `CLOSED`/`OPEN` no obliga a mutilar el término de la gramática de decisión.
ESTADO_COMPUERTA_ABIERTO = "OPEN"
ESTADO_COMPUERTA_CERRADO = "CLOSED"
ESTADOS_COMPUERTA = (ESTADO_COMPUERTA_CERRADO, ESTADO_COMPUERTA_ABIERTO)

# Términos del vocabulario de decisión que NO bloquean el uso del dominio. Todo lo
# demás —NO EMITIR VALORACIÓN, NO UTILIZAR ESTE DATO COMO DEFINITIVO, INFORMACIÓN
# INSUFICIENTE, REVISIÓN PROFESIONAL REQUERIDA, EVIDENCIA EN CONFLICTO— cierra la
# compuerta. La tabla NO introduce umbrales nuevos: deriva de la decisión ya tomada.
DECISIONES_QUE_ABREN_COMPUERTA = frozenset({
    INFORMACION_VERIFICADA,        # dato verificado: se usa
    SIN_HALLAZGO_EN_FUENTE,        # fuente revisada sin hallazgo material: no bloquea
    PROCEDER_CON_CONDICIONES,      # se usa, con las condiciones declaradas
})


def estado_de_compuerta(decision: str) -> str:
    """`CLOSED`/`OPEN` DERIVADO de la decisión: no es un juicio aparte ni un umbral."""
    return (ESTADO_COMPUERTA_ABIERTO if decision in DECISIONES_QUE_ABREN_COMPUERTA
            else ESTADO_COMPUERTA_CERRADO)


# ── §30 · compuertas ─────────────────────────────────────────────────────────
IDENTITY_GATE = "IDENTITY_GATE"
TITLE_GATE = "TITLE_GATE"
COUNTERPARTY_GATE = "COUNTERPARTY_GATE"
URBAN_GATE = "URBAN_GATE"
ENVIRONMENT_GATE = "ENVIRONMENT_GATE"
VALUATION_GATE = "VALUATION_GATE"
EVIDENCE_GATE = "EVIDENCE_GATE"
COMPUERTAS = (IDENTITY_GATE, TITLE_GATE, COUNTERPARTY_GATE, URBAN_GATE,
              ENVIRONMENT_GATE, VALUATION_GATE, EVIDENCE_GATE)

# ── §8 · clase de riesgo: no mezclar calidad de información con riesgo del predio ──
RIESGO_PREDIO = "PROPERTY_RISK"
RIESGO_INFORMACION = "INFORMATION_QUALITY_RISK"

# ── §31 · disposición global (sin score artificial) ──────────────────────────
SUFICIENTE = "INFORMACIÓN SUFICIENTE PARA CONTINUAR"
CONDICIONES = "PROCEDER CON CONDICIONES IDENTIFICADAS"
VALIDACION_PROFESIONAL = "REQUIERE VALIDACIÓN PROFESIONAL"
INSUFICIENTE = "INFORMACIÓN INSUFICIENTE PARA EMITIR CONCLUSIÓN"

# ── §24 · altura: tres conceptos distintos que NO se sustituyen ──────────────
REGULATORY_HEIGHT = "REGULATORY_HEIGHT"
BUILDING_PHYSICAL_HEIGHT = "BUILDING_PHYSICAL_HEIGHT"
MODEL_ASSUMED_HEIGHT = "MODEL_ASSUMED_HEIGHT"


def _sha256(obj: Any) -> str:
    canon = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                       default=str)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _v(x, hueco=None):
    return hueco if x in (None, "", [], {}) else x


# ── objetos de dominio (§3) ──────────────────────────────────────────────────
def evidencia(evidence_id: str, source: str, *, tipo: str = "SOURCE_RESULT",
              when: Optional[str] = None, sha256: Optional[str] = None,
              detalle: Optional[str] = None) -> Dict[str, Any]:
    """`EvidenceReference`: a qué evidencia se ancla una observación."""
    return {"evidence_id": evidence_id, "type": tipo, "source": source,
            "timestamp": when, "sha256": sha256, "detail": detalle}


def observacion(dominio: str, sujeto: str, fuente: str, estado: str, *,
                valor: Any = None, detalle: Optional[str] = None,
                cuando: Optional[str] = None, evidencia_refs: Sequence[Dict] = (),
                consulta: Optional[str] = None) -> Dict[str, Any]:
    """`Observation`: QUÉ se observó, SOBRE QUÉ, DESDE QUÉ fuente, CUÁNDO y con qué ESTADO."""
    if estado not in ESTADOS_OBSERVACION:
        estado = NO_EVALUADO
    return {"observation_id": f"OBS-{dominio}-{abs(hash((dominio, sujeto, fuente, estado,
                                                         str(valor)))) % 100000:05d}",
            "domain": dominio, "subject": sujeto, "source": fuente, "status": estado,
            "value": valor, "detail": detalle, "observed_at": cuando,
            "query": consulta, "evidence_refs": list(evidencia_refs)}


_ACTOR_CANONICO = {
    "ASEGURADORA": "ASEGURADORA DE TÍTULO",
    "ASEGURADORA DE TITULO": "ASEGURADORA DE TÍTULO",
    "BANCO": "BANCO / FINANCIADOR",
}

# Dominio al que pertenece un hallazgo de OPERACIÓN según su TÍTULO. Antes se adivinaba
# por una sola palabra («hipoteca»): una LIMITACIÓN registral caía en ENTORNO y la
# acción impresa en el tablero era la del riesgo geográfico, no la suya.
_DOMINIO_POR_TITULO = (
    # Primero la naturaleza GEOGRÁFICA: el hallazgo de amenaza se titula «Afectación por
    # Amenaza/Riesgo», y leer «AFECTACIÓN» antes que «AMENAZA» lo mandaba a TÍTULOS.
    ("AMENAZA", "ENVIRONMENT"), ("REMOCION", "ENVIRONMENT"), ("INUNDACION", "ENVIRONMENT"),
    ("RIESGO", "ENVIRONMENT"), ("ARROYO", "ENVIRONMENT"), ("GEO", "ENVIRONMENT"),
    ("HIPOTECA", "TITLE"), ("LIMITACION", "TITLE"), ("GRAVAMEN", "TITLE"),
    ("EMBARGO", "TITLE"), ("CAUTELAR", "TITLE"), ("TITULARIDAD", "TITLE"),
    ("CERTIFICADO", "TITLE"), ("AFECTACION", "TITLE"),
)


def _dominio_de_titulo(titulo: str) -> str:
    t = str(titulo or "").upper().replace("Ó", "O").replace("Í", "I")
    for clave, dominio in _DOMINIO_POR_TITULO:
        if clave in t:
            return dominio
    return "TITLE"


def _actores_canonicos(afectados) -> List[str]:
    """Un solo nombre por actor, sin anidamiento («ASEGURADORA» ≠ otra aseguradora)."""
    salida: List[str] = []
    for a in (afectados or []):
        nombre = _ACTOR_CANONICO.get(str(a).strip().upper(), str(a).strip().upper())
        if nombre and nombre not in salida:
            salida.append(nombre)
    return salida


def hallazgo(observacion_: Dict[str, Any], significado: str, *, severidad: str,
             confianza: str, afectados: Sequence[str], impacto: str,
             accion: str, decision: str, clase_riesgo: str = RIESGO_PREDIO,
             codigo: Optional[str] = None) -> Dict[str, Any]:
    """`Finding`: QUÉ SIGNIFICA la observación, su severidad, confianza y a quién afecta.

    `clase_riesgo` separa el RIESGO DEL PREDIO de la CALIDAD DE LA INFORMACIÓN (§8):
    un conflicto técnico no es un riesgo alto del inmueble.
    """
    return {"finding_id": codigo or f"FND-{abs(hash((significado, str(afectados)))) % 100000:05d}",
            "domain": observacion_["domain"], "observation_id": observacion_["observation_id"],
            "observation": observacion_, "meaning": significado,
            "severity": severidad, "confidence": confianza,
            "affected_parties": _actores_canonicos(afectados), "impact": impacto,
            "recommended_action": accion, "decision": decision,
            "risk_class": clase_riesgo,
            "evidence_refs": list(observacion_.get("evidence_refs") or [])}


def recomendacion(texto: str, *, dominio: str, afectados: Sequence[str],
                  evidencia_refs: Sequence[Dict], prioridad: str = "MEDIA",
                  no_sustituye: str = "") -> Dict[str, Any]:
    """`DecisionRecommendation`: qué debería hacerse (y qué NO decide el sistema)."""
    return {"recommendation_id": f"REC-{dominio}-{abs(hash(texto)) % 100000:05d}",
            "domain": dominio, "action": texto, "priority": prioridad,
            "affected_parties": list(afectados),
            "evidence_refs": list(evidencia_refs),
            "does_not_replace": no_sustituye or
            ("DICTUS no aprueba crédito, no asegura el título ni ordena la compra: "
             "la decisión es del profesional competente.")}


def compuerta(nombre: str, entradas: Sequence[str], observaciones: Sequence[Dict],
              bloqueos: Sequence[str], decision: str, motivos: Sequence[str],
              evidencia_refs: Sequence[Dict]) -> Dict[str, Any]:
    """`DecisionGate`: qué puede usarse, qué no, qué está bloqueado y qué requiere revisión.

    Declara DOS campos que no se sustituyen: `decision` (vocabulario de la gramática) y
    `gate_state` (`CLOSED`/`OPEN`, derivado de la decisión con `estado_de_compuerta`).
    """
    if decision not in VOCABULARIO_DECISION:
        decision = INFORMACION_INSUFICIENTE
    return {"gate": nombre, "inputs": list(entradas),
            "observation_ids": [o["observation_id"] for o in observaciones],
            "observations": list(observaciones),
            "blocking_conditions": list(bloqueos), "decision": decision,
            "gate_state": estado_de_compuerta(decision),
            "reasons": list(motivos), "evidence_refs": list(evidencia_refs)}


def revision_humana(*, reviewer: Optional[str] = None,
                    professional_role: Optional[str] = None,
                    reviewed_at: Optional[str] = None, decision: Optional[str] = None,
                    comments: Optional[str] = None, scope: Optional[str] = None,
                    required: bool = True) -> Dict[str, Any]:
    """`HumanReview`: contrato de la revisión humana (la firma la pone la persona).

    El sistema NO firma: deja el modelo preparado y declara qué debe revisarse.
    """
    return {"review_required": required, "reviewer": reviewer,
            "professional_role": professional_role, "reviewed_at": reviewed_at,
            "decision": decision, "comments": comments, "scope": scope,
            "status": "PENDIENTE" if reviewer is None else "REGISTRADA"}


def disposicion(global_: str, *, motivos: Sequence[str], por_compuerta: Dict[str, str],
                no_sustituye: Optional[str] = None) -> Dict[str, Any]:
    """`Disposition`: estado operativo resultante, explicable y sin score.

    Nunca borra las disposiciones específicas: las contiene.
    """
    return {"disposition": global_, "reasons": list(motivos),
            "by_gate": dict(por_compuerta), "specific_dispositions": dict(por_compuerta),
            "does_not_replace": no_sustituye or
            ("La disposición global ordena la lectura; NO sustituye las disposiciones "
             "por dominio ni la decisión humana.")}


# ── §36 · manifiesto de sombras con sus dependencias ─────────────────────────
def manifiesto_sombras(rs: Dict[str, Any], captura_sombras: Optional[Dict[str, Any]] = None,
                       *, fecha: Optional[str] = None) -> Dict[str, Any]:
    """`ShadowManifest`: la sombra es una SIMULACIÓN GEOMÉTRICA con supuestos declarados.

    Distingue —y no mezcla— la altura NORMATIVA del POT, la altura FÍSICA del edificio y
    la altura SUPUESTA por el modelo (§24). Si la altura física no existe, la simulación
    es ORIENTATIVA: la incertidumbre de la altura no se convierte en precisión falsa (§23).
    """
    rs = rs or {}
    urb = rs.get("urban_context") or {}
    hist = rs.get("historical_consistency") or {}
    solar = rs.get("solar_state") or {}
    sombras = captura_sombras or {}
    conflictos = {c.get("atributo") for c in (hist.get("conflictos_abiertos") or [])}

    altura_normativa = _v(urb.get("altura_maxima"))
    altura_fisica = _v(sombras.get("altura_m"))
    fuente_altura_fisica = _v(sombras.get("fuente_altura")) or _v(sombras.get("fuente_huella"))

    supuestos: List[str] = []
    if not fuente_altura_fisica:
        supuestos.append("La corrida no declaró la fuente de la altura física del edificio.")
    if "altura_maxima" in conflictos:
        supuestos.append("La altura normativa del POT está en CONFLICTO HISTÓRICO entre "
                         "versiones del mismo expediente.")
    if altura_normativa and (not altura_fisica):
        supuestos.append("La altura usada por el modelo NO es la altura física construida: "
                         "es la referencia disponible en la corrida.")
    supuestos.append("La orientación de fachada es un SUPUESTO del producto (azimut por "
                     "defecto), no una medición de la unidad.")
    supuestos.append("La huella modelada corresponde al predio/edificio oficial; no a la "
                     "posición del apartamento dentro de la edificación.")

    dependencias = {
        "solar_position_status": "VERIFIED" if (solar.get("momentos") or []) else NO_EVALUADO,
        "building_height_status": (CONFLICTO_OBS if "altura_maxima" in conflictos
                                   else (OBSERVADO if altura_fisica else NO_EVALUADO)),
        "geometry_status": ("VERIFIED" if (sombras.get("fuente_huella") or altura_fisica)
                            else NO_EVALUADO),
        "orientation_status": "ASSUMED",
        "shadow_model_status": ("PARTIAL / ORIENTATIVE"
                                if ("altura_maxima" in conflictos or not altura_fisica)
                                else "REFERENTIAL"),
    }
    manifest = {
        "grammar_version": GRAMMAR_VERSION,
        "simulation_id": None,
        "generated_at": _v(sombras.get("generado_en")) or _v(rs.get("generated_at")),
        "date": fecha or _v(sombras.get("fecha")),
        "location": _v(((rs.get("market_context") or {}).get("coordinates")) or {}),
        "solar_model": "solar_engine.get_solar_position (posición solar geocéntrica)",
        "height_concepts": {
            REGULATORY_HEIGHT: altura_normativa,
            BUILDING_PHYSICAL_HEIGHT: altura_fisica,
            MODEL_ASSUMED_HEIGHT: altura_fisica or altura_normativa,
            "model_assumed_source": ("altura física declarada por la corrida"
                                     if altura_fisica else
                                     "altura normativa del POT usada como referencia"),
        },
        "orientation_source": "azimut de fachada por defecto del producto (SUPUESTO)",
        "physical_height_source": fuente_altura_fisica,
        "geometry_source": _v(sombras.get("fuente_huella")),
        "times": [{"time": m.get("hora"), "azimuth": m.get("azimut"),
                   "elevation": m.get("elevacion"), "incidence": m.get("estado")}
                  for m in (solar.get("momentos") or [])],
        "assumptions": supuestos,
        "dependencies": dependencias,
        "status": dependencias["shadow_model_status"],
        "nature": ("SIMULACIÓN GEOMÉTRICA basada en posición solar, orientación y geometría "
                   "disponibles. No sustituye una inspección física ni un estudio "
                   "especializado de asoleamiento."),
        "assets": [],
    }
    manifest["simulation_id"] = "SHW-" + _sha256({k: manifest[k] for k in
                                                  ("date", "times", "height_concepts",
                                                   "dependencies")})[:12]
    manifest["result_hash"] = _sha256({k: manifest[k] for k in
                                       ("simulation_id", "date", "location", "times",
                                        "height_concepts", "assumptions", "dependencies",
                                        "status")})
    return manifest


# ── §37 · activos visuales formalizados ─────────────────────────────────────
TIPO_ACTIVO = {"satellite_map": "SATELLITE_MAP", "poi_map": "POI_MAP",
               "shadow_09": "SHADOW_09", "shadow_15": "SHADOW_15"}


def activos_visuales(rs: Dict[str, Any]) -> List[Dict[str, Any]]:
    """`VisualAsset[]`: cada activo con id, tipo, estado, fuente, fecha y huella."""
    assets = ((rs.get("visual_assets") or {}).get("assets") or {})
    salida: List[Dict[str, Any]] = []
    for clave, datos in assets.items():
        salida.append({
            "asset_id": f"AST-{TIPO_ACTIVO.get(clave, clave.upper())}",
            "type": TIPO_ACTIVO.get(clave, clave.upper()),
            "status": datos.get("status"),
            "source": datos.get("source"),
            "generated_at": datos.get("generated_at"),
            "content_hash": datos.get("sha256"),
            "bytes": datos.get("bytes"),
            "path": datos.get("path"),
            "evidence_refs": [evidencia(f"EV-{TIPO_ACTIVO.get(clave, clave.upper())}",
                                        str(datos.get("source") or "corrida"),
                                        tipo="VISUAL_ASSET",
                                        when=datos.get("generated_at"),
                                        sha256=datos.get("sha256"))],
        })
    return salida


# ── construcción de la cadena completa ──────────────────────────────────────
def _fuente_urbana(mc: Dict[str, Any], atributo: str) -> str:
    campos = ((mc.get("urban_source_summary") or {}).get("campos") or {})
    c = campos.get(atributo) or {}
    modo = str(c.get("modo") or "NO_DECLARADO")
    return {"LIVE_OFFICIAL": "capa oficial del municipio consultada en vivo",
            "PACKAGED_REFERENCE": "capa POT empaquetada (cruce local, sin consulta en vivo)",
            }.get(modo, "fuente no declarada")


def _ev_identidad(rs: Dict[str, Any]) -> List[Dict]:
    pi = rs.get("property_identity") or {}
    return [evidencia("EV-IDENTIDAD", "SNR/CTL + catastro", tipo="IDENTITY",
                      when=rs.get("generated_at")),
            evidencia("EV-COORD", str(((rs.get("market_context") or {})
                                       .get("coordinate_source")) or "geometría oficial"),
                      tipo="GEOMETRY", when=rs.get("generated_at"))]


def observaciones_de(rs: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Todas las observaciones de la corrida, por dominio. NO recalcula nada."""
    rs = rs or {}
    pi = rs.get("property_identity") or {}
    ts = rs.get("title_state") or {}
    urb = rs.get("urban_context") or {}
    scr = rs.get("screening_summary") or {}
    poi = rs.get("poi_state") or {}
    risk = rs.get("risk_context") or {}
    solar = rs.get("solar_state") or {}
    val = rs.get("valuation_state") or {}
    mc = rs.get("market_context") or {}
    hist = rs.get("historical_consistency") or {}
    cuando = rs.get("generated_at")
    obs: List[Dict[str, Any]] = []

    # El atributo del REGISTRO que corresponde a cada riesgo del estado (los nombres
    # difieren entre capas: la página dice `amenaza_remocion_masa`, el registro `remocion`).
    _ATRIBUTO_DE_RIESGO = {"amenaza_remocion_masa": "remocion",
                           "areas_en_riesgo": "riesgo",
                           "inundacion": "inundacion",
                           "riesgo_no_mitigable": "riesgo_no_mitigable"}

    # IDENTIDAD
    obs.append(observacion("IDENTITY", "Matrícula inmobiliaria", "SNR / Certificado de "
                         "tradición y libertad", OBSERVADO if pi.get("folio") else NO_MATCH,
                         valor=pi.get("folio"), cuando=cuando,
                         detalle=f"Resolución: {_v(pi.get('resolution_method'), 'no declarada')}",
                         evidencia_refs=_ev_identidad(rs)))
    obs.append(observacion("IDENTITY", "NUPRE y número predial", "Catastro municipal",
                           OBSERVADO if (pi.get("nupre") and pi.get("codigo_catastral"))
                           else NO_MATCH,
                           valor={"nupre": pi.get("nupre"),
                                  "predial": pi.get("codigo_catastral")},
                           cuando=cuando, evidencia_refs=_ev_identidad(rs)))
    # Geometría oficial vs identidad canónica: el estado se lee del ALCANCE REAL del
    # binding (§11). Un binding de IDENTIFICADORES (`NATIONAL_IDENTIFIERS`) acredita que
    # el registro es el MISMO predio, NO que ESTA geometría sea la del predio: no se
    # publica como geometría verificada.
    binding_info = {}
    try:
        import attribute_truth as _at_mod
        binding_info = _at_mod.binding_geometria(mc)
    except Exception:  # noqa: BLE001 — el módulo es opcional para el modelo de decisión
        binding_info = {}
    geometrico = bool(binding_info.get("es_binding_geometrico"))
    binding = str(mc.get("canonical_binding_status") or "").upper()
    if geometrico and binding == "VERIFIED":
        _estado_binding = OBSERVADO
    elif binding == "MISMATCH":
        _estado_binding = CONFLICTO_OBS
    elif binding or binding_info:
        # El binding existe, pero su alcance no es geométrico: el hecho está CONOCIDO y
        # su alcance declarado (nunca `NO EVALUADO`: sí se evaluó, con otro alcance).
        _estado_binding = OBSERVADO
    else:
        _estado_binding = NO_EVALUADO
    obs.append(observacion("IDENTITY", "Geometría oficial vs identidad canónica",
                           _v(mc.get("coordinate_source"), "geometría del municipio"),
                           _estado_binding,
                           valor={"binding": binding or "NO_COMPARABLE",
                                  "fields": mc.get("canonical_binding_fields"),
                                  "scope": mc.get("coordinate_binding_scope")
                                  or mc.get("canonical_binding_scope"),
                                  "es_binding_geometrico": geometrico,
                                  "alcance_acreditado": (binding_info.get("etiqueta")
                                                         if binding_info else None)},
                           cuando=cuando,
                           detalle=(binding_info.get("detalle")
                                    or _v(mc.get("coordinate_scope"))),
                           evidencia_refs=_ev_identidad(rs)))

    # TÍTULOS
    obs.append(observacion("TITLE", "Titularidad y participaciones",
                           "Certificado de tradición y libertad (SNR)",
                           OBSERVADO if ts.get("titulares") else NO_MATCH,
                           valor=ts.get("titulares"), cuando=cuando,
                           evidencia_refs=[evidencia("EV-TITULOS", "SNR/CTL",
                                                     tipo="TITLE", when=cuando)]))
    obs.append(observacion("TITLE", "Forma de adquisición", "Acto inscrito en el folio",
                           OBSERVADO if ts.get("modalidad_adquisicion") else NO_MATCH,
                           valor=ts.get("modalidad_adquisicion"),
                           detalle=ts.get("modalidad_evidencia"), cuando=cuando,
                           evidencia_refs=[evidencia("EV-TITULOS", "SNR/CTL",
                                                     tipo="TITLE", when=cuando)]))
    for g in (ts.get("gravamenes_vigentes") or []):
        obs.append(observacion("TITLE", f"Carga vigente {g.get('tipo')}",
                               "Certificado de tradición y libertad (SNR)", OBSERVADO,
                               valor={"tipo": g.get("tipo"), "anotacion": g.get("anotacion"),
                                      "partes": g.get("partes"), "estado": g.get("estado")},
                               cuando=cuando,
                               evidencia_refs=[evidencia(f"EV-CARGA-{g.get('anotacion')}",
                                                         "SNR/CTL", tipo="TITLE",
                                                         when=cuando)]))

    # CONTRAPARTES (§10/§11): el estado de cada consulta es el del MOTOR
    listas = scr.get("sources") or []
    outcomes = scr.get("outcomes") or []
    for s in (scr.get("subjects") or []):
        por_lista: Dict[str, str] = {}
        for o in outcomes:
            if o.get("subject_id") != s.get("subject_id"):
                continue
            sid = str(o.get("source_id") or "")
            por_lista[sid] = {"NO_MATCH": NO_MATCH, "POTENTIAL_MATCH": OBSERVADO,
                              "STRONG_MATCH": OBSERVADO, "EXACT_MATCH": OBSERVADO,
                              "REVIEW_REQUIRED": OBSERVADO,
                              "NOT_SCREENED": NO_CONSULTADO,
                              "SOURCE_UNAVAILABLE": FUENTE_NO_DISPONIBLE_OBS}.get(
                                  str(o.get("result") or "").upper(), NO_EVALUADO)
        for sid in listas:
            estado = por_lista.get(sid, NO_CONSULTADO)
            obs.append(observacion("COUNTERPARTY",
                                   f"{s.get('canonical_name') or '—'} · {sid}",
                                   "Listas restrictivas aplicables", estado,
                                   valor=s.get("roles"), cuando=cuando,
                                   detalle=("Consulta de listas ejecutada por el motor de "
                                            "screening"),
                                   evidencia_refs=[evidencia(f"EV-SCR-{s.get('subject_id')}",
                                                             "screening", tipo="SCREENING",
                                                             when=cuando)]))

    # URBANO
    campos = [("destino_economico", "Destino económico (catastro)", urb.get("destino_economico"),
               "catastro en vivo" if urb.get("destino_economico") else "fuente no declarada"),
              ("uso", "Uso del suelo (POT)", (mc.get("uso") or {}).get("value"),
               _fuente_urbana(mc, "uso")),
              ("clase_suelo", "Clase de suelo", urb.get("clase_suelo"),
               _fuente_urbana(mc, "clase_suelo")),
              ("tratamiento", "Tratamiento urbanístico", urb.get("tratamiento"),
               _fuente_urbana(mc, "tratamiento")),
              ("altura_maxima", "Altura / edificabilidad normativa", urb.get("altura_maxima"),
               _fuente_urbana(mc, "altura_maxima")),
              ("estrato", "Estrato", urb.get("estrato"), _fuente_urbana(mc, "estrato")),
              ("barrio", "Barrio", urb.get("barrio"), _fuente_urbana(mc, "barrio")),
              ("localidad", "Localidad / comuna", urb.get("localidad"),
               _fuente_urbana(mc, "localidad"))]
    conflictos = {c.get("atributo"): c for c in (hist.get("conflictos_abiertos") or [])}
    for clave, etiqueta, valor, fuente in campos:
        estado = (CONFLICTO_OBS if clave in conflictos
                  else (OBSERVADO if _v(valor) else NO_EVALUADO))
        obs.append(observacion("URBAN", etiqueta, fuente, estado, valor=valor,
                               cuando=cuando,
                               detalle=(conflictos.get(clave) or {}).get("detalle"),
                               evidencia_refs=[evidencia(f"EV-URB-{clave.upper()}",
                                                         fuente, tipo="URBAN",
                                                         when=cuando)]))
    for riesgo, etiqueta in (("amenaza_remocion_masa", "Remoción en masa / amenaza del POT"),
                             ("inundacion", "Inundación"),
                             ("riesgo_no_mitigable", "Riesgo no mitigable"),
                             ("areas_en_riesgo", "Otras amenazas declaradas")):
        # ── BLOCK 1 · §17/§18/§19 ─────────────────────────────────────────────
        # El estado del riesgo NO se deriva solo de la PRESENCIA de una cadena
        # (`OBSERVADO if _v(risk.get(riesgo)) else NO_EVALUADO`, la regla anterior): se
        # consulta la VERDAD ÚNICA por atributo de esta corrida (escalera → hecho), que
        # declara si hubo consulta, fuente, geometría evaluada y resultado espacial. Si el
        # atributo no está en el registro, se conserva la regla por presencia de valor.
        estado_reg = None
        ficha = ((rs.get("attribute_resolution") or {}).get("attributes") or {}).get(
            _ATRIBUTO_DE_RIESGO.get(riesgo, riesgo))
        if isinstance(ficha, dict):
            estado_reg = {
                "VERIFIED": OBSERVADO, "KNOWN_BUT_UNVERIFIED": OBSERVADO,
                "CONFLICT": CONFLICTO_OBS, "NOT_EVALUATED": NO_EVALUADO,
                "NO_DATA": NO_MATCH, "HISTORICAL_ONLY": OBSERVADO,
                "SOURCE_UNAVAILABLE": FUENTE_NO_DISPONIBLE_OBS,
                "NOT_SUPPORTED": FUENTE_NO_DISPONIBLE_OBS,
            }.get(str(ficha.get("fact_status") or ""))
        estado = estado_reg if estado_reg else (
            OBSERVADO if _v(risk.get(riesgo)) else NO_EVALUADO)
        detalle = None
        if not _v(risk.get(riesgo)):
            detalle = ("La capa no se evaluó en esta corrida: se declara NO EVALUADO, no "
                       "«sin riesgo».")
            if isinstance(ficha, dict) and ficha.get("canonical_reason"):
                detalle = str(ficha["canonical_reason"])
        obs.append(observacion("ENVIRONMENT", etiqueta,
                               _fuente_urbana(mc, riesgo),
                               estado,
                               valor=risk.get(riesgo), cuando=cuando,
                               detalle=detalle,
                               evidencia_refs=[evidencia(f"EV-RIESGO-{riesgo.upper()}",
                                                         "capa POT del municipio",
                                                         tipo="RISK", when=cuando)]))

    # ENTORNO: equipamiento, asoleamiento
    for c, d in (poi.get("por_categoria") or {}).items():
        estado = str(d.get("status") or NO_EVALUADO).upper()
        estado_obs = {"AVAILABLE": OBSERVADO, "NO_MATCH": NO_MATCH,
                      "SOURCE_UNAVAILABLE": FUENTE_NO_DISPONIBLE_OBS,
                      "NOT_EVALUATED": NO_EVALUADO}.get(estado, NO_EVALUADO)
        obs.append(observacion("ENVIRONMENT", f"Equipamiento · {c}",
                               "OpenStreetMap (Overpass/Photon)" if poi.get("sources_succeeded")
                               else "proveedor de mapas abierto", estado_obs,
                               valor={"count": d.get("count"),
                                      "nearest_m": d.get("mas_cercano_m"),
                                      "items": [i.get("name") for i in (d.get("items") or [])]},
                               cuando=poi.get("queried_at"),
                               evidencia_refs=[evidencia(f"EV-POI-{c.upper()}",
                                                         "OpenStreetMap", tipo="POI",
                                                         when=poi.get("queried_at"))]))
    for m in (solar.get("momentos") or []):
        obs.append(observacion("ENVIRONMENT", f"Asoleamiento {m.get('hora')}",
                               "cálculo solar de la corrida",
                               OBSERVADO if m.get("estado") else NO_EVALUADO,
                               valor={"azimut": m.get("azimut"), "elevacion": m.get("elevacion")},
                               detalle=m.get("estado"), cuando=cuando,
                               evidencia_refs=[evidencia("EV-SOLAR", "solar_engine",
                                                         tipo="SOLAR", when=cuando)]))

    # VALORACIÓN
    aut = bool((val.get("authorization") or {}).get("allowed"))
    # El `source` de la observación NO es el identificador sellado del artefacto
    # metodológico: la observación declara QUÉ sostiene la cifra y con qué ORIGEN. El
    # identificador sellado viaja en su propio campo (`methodology_id`), donde no se
    # lee como el nombre de una fuente.
    _origen_val = _v(val.get("origin"), "NO_DECLARADO")
    obs.append(observacion("VALUATION", "Valor estimado y su banda",
                           "parámetros de mercado declarados por la corrida",
                           OBSERVADO if aut else NO_EVALUADO,
                           valor={"consolidado": val.get("consolidado"),
                                  "banda_baja": val.get("banda_baja"),
                                  "banda_alta": val.get("banda_alta"),
                                  "value_m2": val.get("value_m2"),
                                  "origin": _origen_val,
                                  "origin_gate": bool(val.get("origin_gate"))},
                           cuando=cuando,
                           detalle=(None if aut else _v(val.get("motivo_no_aplica"),
                                                        "valoración no autorizada")),
                           evidencia_refs=[evidencia("EV-VALOR", "metodología de mercado",
                                                     tipo="VALUATION", when=cuando)]))
    obs[-1]["methodology_id"] = mc.get("market_methodology_id")
    obs[-1]["origin"] = _origen_val
    obs[-1]["origin_gate"] = bool(val.get("origin_gate"))
    return obs


def hallazgos_de(rs: Dict[str, Any], obs: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Hallazgos de OPERACIÓN (riesgo del predio) y de CALIDAD DE INFORMACIÓN (§8)."""
    rs = rs or {}
    ts = rs.get("title_state") or {}
    findings = list(rs.get("findings") or [])
    hist = rs.get("historical_consistency") or {}
    por_id = {o["observation_id"]: o for o in obs}
    salida: List[Dict[str, Any]] = []

    def _obs(dominio, aguja):
        for o in obs:
            if o["domain"] == dominio and aguja.lower() in str(o["subject"]).lower():
                return o
        return obs[0]

    for f in findings:
        titulo = str(f.get("titulo") or "")
        clase = (RIESGO_INFORMACION if str(f.get("codigo") or "").upper() == "H-COH"
                 else RIESGO_PREDIO)
        if clase == RIESGO_INFORMACION:
            decision = NO_USAR_COMO_DEFINITIVO
            obs_base = _obs("URBAN", titulo.split(":")[-1].strip()[:12])
            significado = (f"El expediente del mismo inmueble produjo valores distintos "
                           f"entre versiones para {titulo.split(':')[-1].strip()}: es una "
                           f"inconsistencia de CALIDAD DE INFORMACIÓN, no un riesgo del "
                           f"inmueble.")
            impacto = "Calidad de la información con la que se decide"
        else:
            decision = PROCEDER_CON_CONDICIONES
            obs_base = (_obs("TITLE", "Carga vigente")
                        if _dominio_de_titulo(titulo) == "TITLE"
                        else _obs("ENVIRONMENT", "remoción"))
            significado = f.get("por_que") or titulo
            impacto = f.get("impacto") or "Condiciona la operación"
        salida.append(hallazgo(obs_base, significado,
                               severidad=str(f.get("severidad") or "MEDIO").upper(),
                               confianza="VERIFICADO" if clase == RIESGO_PREDIO
                               else "REQUIERE RECONCILIACIÓN",
                               afectados=f.get("afectados") or [],
                               impacto=impacto,
                               accion=f.get("accion") or "Verificar con el profesional "
                                                         "competente.",
                               decision=decision, clase_riesgo=clase,
                               codigo=f.get("codigo")))
    if not ts.get("gravamenes_vigentes"):
        salida.append(hallazgo(_obs("TITLE", "Titularidad"),
                               "El folio no declara cargas vigentes en esta corrida.",
                               severidad="INFORMATIVO", confianza="VERIFICADO",
                               afectados=["COMPRADOR", "VENDEDOR"],
                               impacto="Sin condiciones registrales pendientes",
                               accion="Ninguna por esta fuente.",
                               decision=SIN_HALLAZGO_EN_FUENTE, clase_riesgo=RIESGO_PREDIO,
                               codigo="H-00"))
    return salida


def compuertas_de(rs: Dict[str, Any], obs: Sequence[Dict[str, Any]],
                  findings: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Las siete compuertas (§30). Cada una declara su decisión, motivos y bloqueos."""
    rs = rs or {}
    pi = rs.get("property_identity") or {}
    ts = rs.get("title_state") or {}
    scr = rs.get("screening_summary") or {}
    poi = rs.get("poi_state") or {}
    val = rs.get("valuation_state") or {}
    mc = rs.get("market_context") or {}
    hist = rs.get("historical_consistency") or {}
    solar = rs.get("solar_state") or {}
    ev_id = _ev_identidad(rs)
    ev_tit = [evidencia("EV-TITULOS", "SNR/CTL", tipo="TITLE", when=rs.get("generated_at"))]
    ev_scr = [evidencia("EV-SCREENING", "listas restrictivas aplicables",
                        tipo="SCREENING", when=rs.get("generated_at"))]
    ev_val = [evidencia("EV-VALOR", "metodología de mercado", tipo="VALUATION",
                        when=rs.get("generated_at"))]
    gates: List[Dict[str, Any]] = []

    # IDENTITY_GATE
    verificado_id = bool(pi.get("identity_verified"))
    gates.append(compuerta(
        IDENTITY_GATE, ["matrícula", "NUPRE", "número predial", "geometría oficial"],
        [o for o in obs if o["domain"] == "IDENTITY"],
        [] if verificado_id else ["Identidad del inmueble no verificada"],
        INFORMACION_VERIFICADA if verificado_id else INFORMACION_INSUFICIENTE,
        [f"Resolución de identidad: {_v(pi.get('resolution_method'), 'no declarada')}",
         f"Binding de la geometría: "
         f"{_v(mc.get('canonical_binding_status'), 'NO_COMPARABLE')}"], ev_id))

    # TITLE_GATE
    cargas = ts.get("gravamenes_vigentes") or []
    if cargas:
        dec_tit = PROCEDER_CON_CONDICIONES
        bloques = [f"{g.get('tipo')} (Anot. {g.get('anotacion')})" for g in cargas]
        motivos = ["El folio declara cargas vigentes: la operación es posible con "
                   "condiciones registradas."]
    elif ts.get("certificado_adjuntado"):
        dec_tit, bloques = SIN_HALLAZGO_EN_FUENTE, []
        motivos = ["Se revisó el folio y no se hallaron cargas vigentes."]
    else:
        dec_tit, bloques = INFORMACION_INSUFICIENTE, ["Sin certificado de tradición y libertad"]
        motivos = ["Sin CTL no se puede afirmar nada sobre titularidad o cargas."]
    gates.append(compuerta(TITLE_GATE, ["titulares", "actos de adquisición",
                                        "gravámenes y limitaciones"],
                           [o for o in obs if o["domain"] == "TITLE"], bloques,
                           dec_tit, motivos, ev_tit))

    # COUNTERPARTY_GATE (§11/§12: la consulta y el sello son hechos distintos)
    cadena = str(scr.get("evidence_chain_status") or "")
    no_consultadas = [o["subject"] for o in obs if o["domain"] == "COUNTERPARTY"
                      and o["status"] in (NO_CONSULTADO, FUENTE_NO_DISPONIBLE_OBS,
                                          CONSULTA_FALLIDA)]
    coincidencias = scr.get("matched_subjects") or []
    if coincidencias:
        dec_cp, bloques_cp = REVISION_PROFESIONAL_REQUERIDA, [
            f"Coincidencia en lista para {len(coincidencias)} sujeto(s): requiere revisión "
            f"humana y no constituye una acusación."]
        motivos_cp = ["Una coincidencia de listas es materia de revisión, no una conclusión."]
    elif no_consultadas:
        dec_cp, bloques_cp = INFORMACION_INSUFICIENTE, [
            f"Consultas incompletas: {len(no_consultadas)} verificación(es) sin ejecutar "
            f"o con fuente no disponible"]
        motivos_cp = ["Una consulta no ejecutada NO es «sin coincidencias» (NOT_RUN ≠ "
                      "NO_MATCH)."]
    else:
        dec_cp, bloques_cp = SIN_HALLAZGO_EN_FUENTE, []
        motivos_cp = ["Consultas ejecutadas contra las listas declaradas: sin coincidencias "
                      "relevantes."]
    if cadena and cadena != "SEALED":
        motivos_cp.append("La cadena de evidencia NO está sellada: es un hecho de INTEGRIDAD "
                          "probatoria y no cambia el resultado del screening.")
    gates.append(compuerta(COUNTERPARTY_GATE, ["sujetos", "listas consultadas",
                                               "resultados por lista"],
                           [o for o in obs if o["domain"] == "COUNTERPARTY"],
                           bloques_cp, dec_cp, motivos_cp, ev_scr))

    # URBAN_GATE
    conflictos = hist.get("conflictos_abiertos") or []
    sin_comparar = not (hist and int(hist.get("versiones_comparadas") or 0) > 0)
    atributos_conf = {c.get("atributo") for c in conflictos}
    if {"altura_maxima", "tratamiento", "uso_pot"} & atributos_conf:
        dec_urb = NO_USAR_COMO_DEFINITIVO
        bloques_urb = [f"{a} (CONFLICTO HISTÓRICO)" for a in
                       sorted({"altura_maxima", "tratamiento", "uso_pot"} & atributos_conf)]
        motivos_urb = ["El expediente produjo valores distintos entre versiones para estos "
                       "atributos: no se usa ninguna cifra como definitiva hasta reconciliar."]
    elif sin_comparar:
        dec_urb, bloques_urb = REVISION_PROFESIONAL_REQUERIDA, []
        motivos_urb = ["Sin expediente histórico comparado en esta corrida: no se afirma que "
                       "los atributos hayan permanecido iguales."]
    else:
        dec_urb, bloques_urb = INFORMACION_VERIFICADA, []
        motivos_urb = ["Atributos urbanísticos tomados de capas oficiales del municipio."]
    gates.append(compuerta(URBAN_GATE, ["destino económico", "uso POT", "clase de suelo",
                                        "tratamiento", "altura", "estrato"],
                           [o for o in obs if o["domain"] == "URBAN"], bloques_urb, dec_urb,
                           motivos_urb, [evidencia("EV-URBAN", "capas POT del municipio",
                                                   tipo="URBAN", when=rs.get("generated_at"))]))

    # ENVIRONMENT_GATE
    cats_sin = [o["subject"] for o in obs if o["domain"] == "ENVIRONMENT"
                and "Equipamiento" in str(o["subject"])
                and o["status"] in (FUENTE_NO_DISPONIBLE_OBS, NO_EVALUADO)]
    riesgos_sin = [o["subject"] for o in obs if o["domain"] == "ENVIRONMENT"
                   and o["status"] == NO_EVALUADO and "Equipamiento" not in str(o["subject"])]
    if cats_sin or riesgos_sin:
        dec_env = INFORMACION_INSUFICIENTE
        bloques_env = [f"{x}: sin dato de fuente" for x in (cats_sin + riesgos_sin)][:6]
        motivos_env = ["Hay capas de entorno no evaluadas en esta corrida: se declaran como "
                       "tales, no como «sin riesgo»."]
    else:
        dec_env, bloques_env = INFORMACION_VERIFICADA, []
        motivos_env = ["Equipamiento y amenazas consultados en esta corrida."]
    gates.append(compuerta(ENVIRONMENT_GATE, ["equipamiento por categoría", "distancias",
                                              "asoleamiento", "sombras"],
                           [o for o in obs if o["domain"] == "ENVIRONMENT"], bloques_env,
                           dec_env, motivos_env,
                           [evidencia("EV-ENTORNO", "proveedor de mapas abierto",
                                      tipo="ENVIRONMENT", when=rs.get("generated_at"))]))

    # VALUATION_GATE
    # El `reason` nombra la CAUSA del bloqueo con el vocabulario CERRADO de ORIGEN
    # (`atribucion_mercado`): un «no autorizado» sin causa obliga al lector a adivinar.
    # No cambia ningún umbral: solo hace explícito lo que la corrida ya declaró.
    aut = bool((val.get("authorization") or {}).get("allowed"))
    blockers = [b for b in (mc.get("blockers") or []) if isinstance(b, str)]
    _origen_val = str(val.get("origin") or mc.get("origin") or "NO_DECLARADO")
    _origen_gate_val = bool(val.get("origin_gate") or mc.get("origin_gate"))
    if aut:
        dec_val, bloques_val = INFORMACION_VERIFICADA, []
        motivos_val = [f"La valoración está autorizada: la tasa se sostiene en "
                       f"{_origen_val} con procedencia completa y se imprime con su "
                       f"método y vigencia."]
    else:
        dec_val = NO_EMITIR_VALORACION
        bloques_val = blockers or [_v(val.get("motivo_no_aplica"),
                                      "la corrida no declaró la causa")]
        if _origen_gate_val:
            motivos_val = [
                f"La valoración NO está autorizada en esta corrida: su origen "
                f"({_origen_val}) sí habilita una cifra, pero hay bloqueos materiales "
                f"declarados. No se emite valor."]
        else:
            motivos_val = [
                f"La valoración NO está autorizada en esta corrida: el origen de la tasa "
                f"es {_origen_val} y su procedencia es INSUFICIENTE para autorizar una "
                f"cifra (se exige fuente externa citada o cálculo de fuentes citadas, con "
                f"fecha y sha256). No se emite cifra y se declaran los bloqueos reales."]
    gates.append(compuerta(VALUATION_GATE, ["autorización de identidad",
                                            "autorización de contexto de mercado",
                                            "método y vigencia"],
                           [o for o in obs if o["domain"] == "VALUATION"], bloques_val,
                           dec_val, motivos_val, ev_val))

    # EVIDENCE_GATE (§12)
    sellado = str((rs.get("release_state") or {}).get("release_status") or "")
    creadas = scr.get("evidence_created_count") or scr.get("evidence_created")
    esperadas = scr.get("evidence_expected_count") or scr.get("evidence_expected")
    if cadena == "SEALED":
        dec_ev, bloques_ev = INFORMACION_VERIFICADA, []
        motivos_ev = [f"Cadena de evidencia sellada ({creadas}/{esperadas} evidencias)."]
    elif cadena:
        dec_ev = EVIDENCIA_EN_CONFLICTO
        bloques_ev = [f"Cadena de evidencia en estado {cadena}: la evidencia es trazable pero "
                      f"no está sellada"]
        motivos_ev = ["La integridad probatoria no alcanzó el estado sellado; esto NO "
                      "convierte en incompleto un screening que sí consultó las listas."]
    else:
        dec_ev, bloques_ev = INFORMACION_INSUFICIENTE, ["Sin estado de cadena declarado"]
        motivos_ev = ["La corrida no declaró el estado de su cadena de evidencia."]
    if sellado and sellado != "VALID_FOR_RELEASE":
        bloques_ev.append(f"Gate de liberación: {sellado}")
    gates.append(compuerta(EVIDENCE_GATE, ["cadena de custodia", "conteo de evidencias",
                                           "gate de liberación"],
                           [o for o in obs if o["domain"] in ("COUNTERPARTY", "IDENTITY")][:6],
                           bloques_ev, dec_ev, motivos_ev,
                           [evidencia("EV-CADENA", "cadena de custodia DICTUS",
                                      tipo="EVIDENCE", when=rs.get("generated_at"))]))
    return gates


def disposicion_global(gates: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Disposición global EXPLICABLE (§31): no hay score, hay razones.

    Regla: una compuerta CRÍTICA (identidad, títulos, evidencia) insuficiente impide
    concluir; la cobertura PARCIAL de un dominio auxiliar (entorno, urbanismo) NO borra
    la conclusión ni se convierte en «sin riesgo»: se declara como cobertura parcial.
    Las disposiciones específicas nunca se borran: viajan en `by_gate`.
    """
    por_compuerta = {g["gate"]: g["decision"] for g in gates}
    criticas = [g for g in gates if g["gate"] in (IDENTITY_GATE, TITLE_GATE, EVIDENCE_GATE)]
    auxiliares = [g for g in gates if g not in criticas]

    cobertura_parcial = [f"{g['gate']}: {g['blocking_conditions'][0]}"
                         for g in auxiliares
                         if g["decision"] == INFORMACION_INSUFICIENTE
                         and g["blocking_conditions"]]
    motivos: List[str] = []

    if any(g["decision"] == INFORMACION_INSUFICIENTE for g in criticas):
        disp = INSUFICIENTE
        motivos = [f"{g['gate']}: {g['blocking_conditions'][0] if g['blocking_conditions'] else 'información insuficiente'}"
                   for g in criticas if g["decision"] == INFORMACION_INSUFICIENTE]
    elif any(g["decision"] in (NO_EMITIR_VALORACION, EVIDENCIA_EN_CONFLICTO)
             for g in gates):
        disp = CONDICIONES
        motivos = [f"{g['gate']}: {g['reasons'][0]}" for g in gates
                   if g["decision"] in (NO_EMITIR_VALORACION, EVIDENCIA_EN_CONFLICTO)]
    elif any(g["decision"] == PROCEDER_CON_CONDICIONES for g in gates):
        disp = CONDICIONES
        motivos = [f"{g['gate']}: {g['reasons'][0]}" for g in gates
                   if g["decision"] == PROCEDER_CON_CONDICIONES]
    elif any(g["decision"] in (REVISION_PROFESIONAL_REQUERIDA, NO_USAR_COMO_DEFINITIVO)
             for g in gates):
        disp = VALIDACION_PROFESIONAL
        motivos = [f"{g['gate']}: {g['reasons'][0]}" for g in gates
                   if g["decision"] in (REVISION_PROFESIONAL_REQUERIDA,
                                        NO_USAR_COMO_DEFINITIVO)]
    else:
        disp = SUFICIENTE
        motivos = ["Todas las compuertas quedaron en información verificada o sin hallazgo "
                   "material en su fuente."]

    motivos += [f"Cobertura parcial declarada — {c}" for c in cobertura_parcial[:4]]
    resultado = disposicion(disp, motivos=motivos, por_compuerta=por_compuerta)
    resultado["coverage_notes"] = cobertura_parcial
    resultado["critical_gates"] = [g["gate"] for g in criticas]
    return resultado


def matriz_de_decision(findings: Sequence[Dict[str, Any]],
                       gates: Sequence[Dict[str, Any]] | None = None) -> List[Dict[str, Any]]:
    """§5 · MATRIZ DOMAIN · SOURCE · OBSERVATION · FINDING · DECISION · AFECTA · ACCIÓN · EVIDENCIA."""
    filas = []
    for f in findings:
        o = f.get("observation") or {}
        filas.append({
            "domain": f.get("domain"), "source": o.get("source"),
            "observation": o.get("value") if o.get("value") is not None else o.get("subject"),
            "observation_status": o.get("status"),
            "finding": f.get("meaning"), "severity": f.get("severity"),
            "confidence": f.get("confidence"),
            "decision": f.get("decision"), "affected_parties": f.get("affected_parties"),
            "action": f.get("recommended_action"), "risk_class": f.get("risk_class"),
            "evidence_refs": [e.get("evidence_id") for e in (f.get("evidence_refs") or [])],
        })
    return filas


def recomendaciones_de(findings: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    salida = []
    for f in findings:
        accion = _v(f.get("recommended_action"))
        if not accion:
            continue
        salida.append(recomendacion(accion, dominio=f.get("domain") or "GENERAL",
                                    afectados=f.get("affected_parties") or [],
                                    evidencia_refs=f.get("evidence_refs") or [],
                                    prioridad=("ALTA" if f.get("severity") == "ALTO"
                                               else "MEDIA")))
    return salida


def construir(rs: Dict[str, Any], *, captura_sombras: Optional[Dict[str, Any]] = None,
              fecha_simulacion: Optional[str] = None) -> Dict[str, Any]:
    """Cadena completa de decisión derivada del estado canónico de la corrida."""
    obs = observaciones_de(rs)
    findings = hallazgos_de(rs, obs)
    gates = compuertas_de(rs, obs, findings)
    disp = disposicion_global(gates)
    sombras = manifiesto_sombras(rs, captura_sombras, fecha=fecha_simulacion)
    activos = activos_visuales(rs)
    return {
        "grammar_version": GRAMMAR_VERSION,
        "observations": obs,
        "findings": findings,
        "recommendations": recomendaciones_de(findings),
        "decision_gates": gates,
        "disposition": disp,
        "human_review": revision_humana(scope="Expediente completo (6 páginas)"),
        "shadow_manifest": sombras,
        "visual_assets": activos,
        "decision_matrix": matriz_de_decision(findings, gates),
    }


# ── §38/§39 · compuerta de completitud material ─────────────────────────────
HECHOS_MATERIALES = (
    ("identidad", lambda rs, m: (rs.get("property_identity") or {}).get("folio"),
     lambda m: (m.get("canonical_property_identity") or {}).get("folio")),
    ("NUPRE", lambda rs, m: (rs.get("property_identity") or {}).get("nupre"),
     lambda m: (m.get("canonical_property_identity") or {}).get("nupre")),
    ("predial", lambda rs, m: (rs.get("property_identity") or {}).get("codigo_catastral"),
     lambda m: (m.get("canonical_property_identity") or {}).get("codigo_catastral")),
    ("unidad", lambda rs, m: (rs.get("property_identity") or {}).get("unidad"),
     lambda m: (m.get("canonical_property_identity") or {}).get("unidad")),
    ("régimen", lambda rs, m: (rs.get("urban_context") or {}).get("condicion_juridica"),
     lambda m: (m.get("urban_context") or {}).get("condicion_juridica")),
    ("tratamiento", lambda rs, m: (rs.get("urban_context") or {}).get("tratamiento"),
     lambda m: (m.get("urban_context") or {}).get("tratamiento")),
    ("altura", lambda rs, m: (rs.get("urban_context") or {}).get("altura_maxima"),
     lambda m: (m.get("urban_context") or {}).get("altura_maxima")),
    ("titulares", lambda rs, m: (rs.get("title_state") or {}).get("titulares"),
     lambda m: (m.get("title_summary") or {}).get("titulares")),
    ("modalidad de adquisición",
     lambda rs, m: (rs.get("title_state") or {}).get("modalidad_adquisicion"),
     lambda m: (m.get("title_summary") or {}).get("modalidad_adquisicion")),
    ("POI (ítems)", lambda rs, m: (rs.get("poi_state") or {}).get("item_count"),
     lambda m: ((m.get("poi_summary") or {}).get("item_count"))),
    ("POI (distancias)", lambda rs, m: (rs.get("poi_state") or {}).get("distance_available"),
     lambda m: ((m.get("poi_summary") or {}).get("distance_available"))),
    ("asoleamiento", lambda rs, m: len((rs.get("solar_state") or {}).get("momentos") or []),
     lambda m: len((m.get("solar_summary") or {}).get("momentos") or [])),
    ("valor", lambda rs, m: (rs.get("valuation_state") or {}).get("consolidado"),
     lambda m: (m.get("valuation") or {}).get("consolidado")),
    ("sector de mercado",
     lambda rs, m: ((rs.get("market_context") or {}).get("sector_metodologico") or {}).get(
         "matched_sector"),
     lambda m: ((m.get("market_context") or {}).get("sector_metodologico") or {}).get(
         "matched_sector")),
    ("binding de la geometría",
     lambda rs, m: (rs.get("market_context") or {}).get("canonical_binding_status"),
     lambda m: ((m.get("market_context") or {}).get("canonical_binding_status"))),
    ("activos visuales",
     lambda rs, m: len(((rs.get("visual_assets") or {}).get("assets") or {})),
     lambda m: len(m.get("visual_assets") or [])),
)


def material_fact_gate(rs: Dict[str, Any], modelo: Dict[str, Any]) -> Dict[str, Any]:
    """§38/§39 · si el estado conoce un hecho material y el modelo lo pierde: FAIL.

    Es una compuerta de COMPLETITUD, no un aviso: su veredicto entra al documento.
    """
    perdidas = []
    for nombre, get_rs, get_m in HECHOS_MATERIALES:
        v_rs = get_rs(rs, modelo)
        v_m = get_m(modelo)
        if _v(v_rs) is None:
            continue
        if _v(v_m) is None:
            perdidas.append({"fact": nombre, "in_run_state": v_rs, "in_model": v_m,
                             "cause": "MODEL_PROJECTION_LOSS"})
    poi_rs = (rs.get("poi_state") or {}).get("por_categoria") or {}
    poi_m = (modelo.get("poi_summary") or {}).get("por_categoria") or {}
    for cat, d in poi_rs.items():
        esperado = d.get("count") or 0
        recibido = (poi_m.get(cat) or {}).get("count")
        if esperado and (recibido or 0) < esperado:
            perdidas.append({"fact": f"POI {cat}", "in_run_state": esperado,
                             "in_model": recibido,
                             "cause": "STATE_PROJECTION_LOSS (equipamiento degradado)"})
    return {"gate": "MATERIAL_FACT_COMPLETENESS_GATE", "result": "FAIL" if perdidas else "PASS",
            "losses": perdidas, "checked_facts": len(HECHOS_MATERIALES) + len(poi_rs),
            "rule": ("Si el estado conoce un hecho material y el ExecutiveDocumentModel lo "
                     "pierde, la corrida FALLA.")}

# -*- coding: utf-8 -*-
"""DICTUS 2.0 — EVIDENCE MANIFEST y DICTUS_MASTER_HASH (§J, §K, §AN, §AO).

Qué es
------
`DICTUS_MASTER_HASH` es **un solo** hash visible que representa el conjunto canónico de
hechos y evidencias con el que se produjo el Dictus. No es el hash del PDF (ese es
`PDF_BINARY_SHA256`, que vive en el manifest y en el servicio de verificación): un
archivo no puede contener su propio hash.

Garantías implementadas
-----------------------
· **Determinista**: la serialización ordena claves y normaliza números; no depende del
  orden accidental de diccionarios ni listas (las listas se ordenan por su contenido
  canónico).
· **Versionada**: `MASTER_MANIFEST_VERSION` viaja dentro del propio hash, de modo que un
  cambio de formato no puede confundirse con un cambio de hechos.
· **Reproducible**: mismo manifest ⇒ mismo hash, en cualquier equipo y momento.
· **Sensible a hechos materiales**: cambiar cualquier hecho incluido cambia el hash.
· **Separado del PDF**: el hash maestro NO incluye el binario del PDF ni su hash.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Iterable, List, Optional

MASTER_MANIFEST_VERSION = "dictus-master-manifest/1.2.0"

# Bloques canónicos que entran al hash maestro (§J + §6 de 2.0B). El orden de esta
# tupla es parte del contrato: NO se reordena sin cambiar la versión del manifest.
# 1.1.0 incorpora el ESTADO CANÓNICO DE CORRIDA: run_id, title_state, risk_context,
# poi_state (con ítems y distancias reales) y solar_state.
BLOQUES_CANONICOS = (
    "document_identity",
    "run_id",
    "canonical_property_identity",
    "title_summary",
    "findings",
    "screening_summary",
    "urban_context",
    "risk_context",
    "poi_summary",
    "solar_summary",
    "valuation",
    "evidence_manifest",
    "source_versions",
    "methodology_versions",
    "release_state",
    "historical_consistency",
    # 1.2.0 (DICTUS 2.0D): la GRAMÁTICA DE DECISIÓN entra al hash maestro: qué se
    # observó, qué significa, qué se recomienda, qué compuertas se evaluaron, cuál es la
    # disposición, el manifiesto de sombras (con sus supuestos) y los activos visuales.
    "observations",
    "recommendations",
    "decision_gates",
    "disposition",
    "human_reviews",
    "decision_matrix",
    "shadow_manifest",
    "visual_assets",
    # Los HALLAZGOS con significado, decisión, afectados, motivos y evidencia son un
    # bloque PROPIO: `findings` es la lista legacy del expediente y mezclarlas hacía
    # que los motivos del hallazgo no entraran al hash maestro.
    "decision_findings",
)


# ── Serialización canónica ────────────────────────────────────────────────────
def _canonico(obj: Any) -> Any:
    """Normaliza a una forma determinista: dicts ordenados, listas ordenadas, números
    redondeados, texto sin espacios accidentales."""
    if obj is None or isinstance(obj, (bool, int, str)):
        return obj
    if isinstance(obj, float):
        return round(obj, 4)
    if isinstance(obj, dict):
        return {str(k): _canonico(v) for k, v in sorted(obj.items(), key=lambda kv: str(kv[0]))
                if v is not None}
    if isinstance(obj, (list, tuple, set, frozenset)):
        normalizados = [_canonico(x) for x in obj]
        try:
            return sorted(normalizados, key=lambda x: json.dumps(x, ensure_ascii=False,
                                                                 sort_keys=True))
        except Exception:  # noqa: BLE001 — tipos no comparables: se conserva el orden
            return normalizados
    return str(obj)


def serializacion_canonica(modelo: Dict[str, Any]) -> str:
    """JSON canónico (sin espacios, claves ordenadas) de los bloques del hash."""
    bloques = {b: _canonico((modelo or {}).get(b)) for b in BLOQUES_CANONICOS}
    payload = {"master_manifest_version": MASTER_MANIFEST_VERSION, "bloques": bloques}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def master_hash(modelo: Dict[str, Any]) -> str:
    """DICTUS_MASTER_HASH = SHA-256 de la serialización canónica."""
    return hashlib.sha256(serializacion_canonica(modelo).encode("utf-8")).hexdigest()


def master_hash_abreviado(h: str) -> str:
    """Forma corta para el sello visible: `DE57FE14E4FA…28B3`."""
    h = str(h or "")
    return f"{h[:12].upper()}…{h[-4:].upper()}" if len(h) >= 16 else h.upper()


def dictus_id(folio: str, fecha_iso: str) -> str:
    """Identificador legible del expediente: DX-<folio>-<AAAAMMDD>."""
    f = str(fecha_iso or "")[:10].replace("-", "")
    return f"DX-{str(folio or 'SIN-FOLIO').strip()}-{f}"


# ── Evidence manifest (§AN) ───────────────────────────────────────────────────
def _ev(evidence_id: str, tipo: str, source: Optional[str], source_version: Optional[str],
        subject: Optional[str], timestamp: Optional[str], contenido: Any,
        status: str = "SELLADA") -> Dict[str, Any]:
    # `content_hash` = SHA-256 del CONTENIDO de ESTA evidencia.
    #
    # Antes se calculaba con `serializacion_canonica({"bloques": {"_evidencia": ...}})`,
    # pero `serializacion_canonica` sólo serializa las claves de `BLOQUES_CANONICOS`:
    # `_evidencia` no está ahí, así que TODAS las evidencias del manifest salían con el
    # MISMO hash constante (`a789f78c…`), ajeno a su contenido. Un `content_hash` que no
    # depende del contenido no sella nada: es una constante. Aquí se hashea el contenido
    # de verdad, con la MISMA normalización determinista (`_canonico` + JSON ordenado).
    cuerpo = json.dumps(_canonico({"evidencia": contenido}), ensure_ascii=False,
                        sort_keys=True, separators=(",", ":"))
    return {
        "evidence_id": evidence_id,
        "evidence_type": tipo,
        "source": source,
        "source_version": source_version,
        "subject": subject,
        "timestamp": timestamp,
        "content_hash": hashlib.sha256(cuerpo.encode("utf-8")).hexdigest(),
        "status": status,
    }


def construir_evidence_manifest(estado: Dict[str, Any], *,
                                folio: Optional[str] = None,
                                timestamp: Optional[str] = None) -> Dict[str, Any]:
    """Manifest canónico de evidencias a partir del ESTADO REAL de la ejecución.

    Cada evidencia sale de un dato que la ejecución produjo (coordenada y su procedencia,
    capas urbanas, contrapartes consultadas, POI, volcán, mercado, valoración, gate de
    liberación y recibos). Lo que no se ejecutó NO se declara como evidencia: se declara
    su estado.
    """
    e = estado or {}
    ident = e.get("identity") or {}
    coords = e.get("coordinates") or {}
    prov = coords.get("provenance") or {}
    urb = e.get("urban") or {}
    usm = e.get("urban_source_summary") or {}
    market = e.get("market") or {}
    val = e.get("valuation") or {}
    poi = e.get("poi") or {}
    vol = e.get("volcan") or {}
    scr = e.get("screening") or {}
    gate = e.get("gate") or {}
    rec = e.get("receipts") or {}
    folio = folio or ident.get("folio") or "SIN-FOLIO"
    ts = timestamp or (rec.get("generated_at") if isinstance(rec, dict) else None)
    sujeto = f"predio {folio}"

    items: List[Dict[str, Any]] = []
    items.append(_ev("EV-IDENTIDAD", "IDENTIDAD_CANONICA", "SNR + geoportal municipal",
                     ident.get("resolution_method"), sujeto, ts,
                     {"folio": ident.get("folio"), "nupre": ident.get("nupre"),
                      "codigo_catastral": ident.get("codigo_catastral"),
                      "estado": ident.get("estado"),
                      "confianza": ident.get("resolution_confidence"),
                      "unidad": ident.get("unidad")},
                     "SELLADA" if ident.get("identity_verified") else "PARCIAL"))
    items.append(_ev("EV-GEOMETRIA", "GEOMETRIA_OFICIAL", prov.get("source_system"),
                     prov.get("resolution_method"), sujeto, ts,
                     {"lat": coords.get("lat"), "lon": coords.get("lon"),
                      "coordinate_source": coords.get("source"),
                      "verified": coords.get("verified"),
                      "feature_id": prov.get("feature_id"), "layer": prov.get("layer"),
                      "binding": prov.get("canonical_binding_status")},
                     "SELLADA" if coords.get("verified") else "NO_VERIFICADA"))
    # El estado de la evidencia urbana se lee del contexto OFICIAL de la corrida (donde
    # el estado realmente vive), sin inventarlo ni degradarlo por una clave ausente.
    _ouc = e.get("official_urban_context") or {}
    _urb_estado = (_ouc.get("barrio_status") or urb.get("barrio_status")
                   or (usm.get("source_mode") if usm.get("source_mode") == "LIVE_OFFICIAL"
                       else None))
    items.append(_ev("EV-URBANO", "CAPAS_OFICIALES_MUNICIPALES",
                     _ouc.get("barrio_source") or urb.get("source"),
                     usm.get("source_mode"), sujeto, ts,
                     {"barrio": urb.get("barrio"), "estrato": urb.get("estrato"),
                      "tratamiento": urb.get("tratamiento"),
                      "altura_maxima": urb.get("altura_maxima"),
                      "barrio_status": _ouc.get("barrio_status"),
                      "estrato_status": _ouc.get("estrato_status"),
                      "clase_suelo": urb.get("predio_entorno", {}).get("clase_suelo")
                      if isinstance(urb.get("predio_entorno"), dict) else None,
                      "modo": usm.get("source_mode")},
                     "SELLADA" if _urb_estado == "VERIFIED_OFFICIAL" else "PARCIAL"))
    # ── La evidencia de MERCADO y de VALORACIÓN dependen del ORIGEN de la tasa ──
    # Una tasa escrita a mano en un artefacto local NO es una fuente sellable: la
    # evidencia se declara como PARÁMETRO DECLARADO y la valoración como no autorizada
    # por falta de FUENTE (no por falta de umbral). Es la misma verdad que imprime el
    # ejecutivo.
    _origen_mercado = str(market.get("origin") or "").upper()
    _origen_gate = bool(market.get("origin_gate"))
    _estado_mercado = ({"EXTERNAL_SOURCE": "SELLADA",
                        "COMPUTED_FROM_SOURCES": "SELLADA",
                        "MANUAL_CONFIG": "PARAMETRO_DECLARADO",
                        "STATIC_REFERENCE": "PARAMETRO_DECLARADO",
                        "MODEL_PRIOR": "PRIOR_DEL_MODELO"}.get(_origen_mercado)
                       or "SIN_ORIGEN_DECLARADO")
    items.append(_ev("EV-MERCADO", "METODOLOGIA_DE_MERCADO",
                     market.get("market_rate_source") or market.get("rate_source"),
                     market.get("market_methodology_version"), sujeto, ts,
                     {"sector": market.get("sector"), "match_type": market.get("match_type"),
                      "value_m2": market.get("value_m2"),
                      "origin": _origen_mercado or None,
                      "origin_gate": _origen_gate,
                      "origin_blockers": market.get("origin_blockers") or [],
                      "metodologia_sha256": market.get("market_methodology_sha256")},
                     _estado_mercado))
    items.append(_ev("EV-VALORACION", "VALORACION", val.get("source_m2"),
                     market.get("market_methodology_version"), sujeto, ts,
                     {"autorizada": (val.get("authorization") or {}).get("allowed"),
                      "consolidado": val.get("consolidado"),
                      "value_m2": val.get("value_m2"),
                      "origin": val.get("origin") or _origen_mercado or None,
                      "origin_gate": bool(val.get("origin_gate")) or _origen_gate,
                      "motivo_no_aplica": val.get("motivo_no_aplica")},
                     ("SELLADA" if ((val.get("authorization") or {}).get("allowed")
                                    and _origen_gate)
                      else "NO_AUTORIZADA_SIN_FUENTE")))
    items.append(_ev("EV-CONTRAPARTES", "SCREENING_CONTRAPARTES",
                     "listas restrictivas y sancionatorias aplicables",
                     scr.get("matcher_version"), "contrapartes del caso", ts,
                     {"estado": scr.get("status"), "sujetos": scr.get("subjects_screened"),
                      "evidencias": f"{scr.get('evidence_created')}/{scr.get('evidence_expected')}",
                      "cadena": scr.get("evidence_chain_status"),
                      "sujetos_detalle": scr.get("subjects")},
                     "SELLADA" if scr.get("evidence_chain_status") == "SEALED" else "PARCIAL"))
    categorias = poi.get("categorias") or {}
    items.append(_ev("EV-EQUIPAMIENTO", "EQUIPAMIENTO_URBANO", "proveedor de mapas abierto",
                     None, sujeto, ts,
                     {"categorias": {k: (v.get("status") if isinstance(v, dict) else v)
                                     for k, v in categorias.items()},
                      "intentadas": poi.get("sources_attempted"),
                      "exitosas": poi.get("sources_succeeded")},
                     "SELLADA" if poi.get("sources_succeeded") else "FUENTE_NO_DISPONIBLE"))
    items.append(_ev("EV-AMENAZAS", "AMENAZAS_Y_RIESGO", "servicios municipales y SGC",
                     None, sujeto, ts,
                     {"volcan_estado": vol.get("estado"), "volcan_nivel": vol.get("nivel"),
                      "amenaza": urb.get("predio_entorno", {}).get("amenaza_remocion_masa")
                      if isinstance(urb.get("predio_entorno"), dict) else None},
                     "SELLADA" if vol.get("disponible") else "FUENTE_NO_DISPONIBLE"))
    items.append(_ev("EV-LIBERACION", "RELEASE_GATE", "núcleo de screening sancionado",
                     gate.get("matcher_version"), "documento", ts,
                     {"release_status": gate.get("release_status"),
                      "policy": gate.get("policy"), "environment": gate.get("environment"),
                      "contract_valid": gate.get("contract_valid")},
                     "SELLADA" if str(gate.get("release_status")) == "VALID_FOR_RELEASE"
                     else "NO_LIBERADO"))

    # Historial de coherencia: si hay conflictos abiertos, es evidencia de PRIMER orden.
    hist = e.get("historical_consistency") or {}
    if hist:
        items.append(_ev("EV-COHERENCIA", "COHERENCIA_HISTORICA",
                         "expediente histórico del mismo inmueble",
                         hist.get("version"), sujeto, ts,
                         {"veredicto": hist.get("veredicto"),
                          "conflictos_abiertos": [c.get("atributo")
                                                  for c in (hist.get("conflictos_abiertos") or [])]},
                         "CONFLICTO_ABIERTO" if hist.get("conflictos_abiertos") else "SELLADA"))

    fuentes = sorted({str(i["source"]) for i in items if i.get("source")})
    # §17: si la cadena de evidencia NO se pudo sellar, el ejecutivo dice exactamente
    # «EVIDENCIA NO SELLADA»: sin variables de entorno, sin trazas ni excepciones.
    _cadena = str((scr or {}).get("evidence_chain_status") or "")
    if _cadena.upper() in ("FAILED", "ERROR", "BROKEN"):
        estado_global = "EVIDENCIA NO SELLADA"
    elif all(i["status"] == "SELLADA" for i in items):
        estado_global = "SELLADO"
    else:
        estado_global = "PARCIAL_CON_DECLARACIONES"
    return {
        "master_manifest_version": MASTER_MANIFEST_VERSION,
        "dictus_id": dictus_id(folio, str(ts or "")),
        "property": sujeto,
        "generated_at": ts,
        "evidencias": items,
        "evidence_count": len(items),
        "fuentes": fuentes,
        "selladas": sum(1 for i in items if i["status"] == "SELLADA"),
        "estado": estado_global,
    }


# ── Documento maestro (§J) y verificación futura (§AO) ────────────────────────
def estado_legacy_desde_run_state(rs: Dict[str, Any]) -> Dict[str, Any]:
    """Adapta el `DictusRunState` (2.0B) a la forma que consumen los constructores.

    Una sola corrida produce una sola verdad: el estado canónico. Este adaptador evita
    dos caminos de lectura (no hay segunda extracción ni segunda consulta).
    """
    rs = rs or {}
    pi = dict(rs.get("property_identity") or {})
    adm = pi.pop("administrativo", None) or {}
    # DICTUS 2.0C: el contexto de mercado (sector, tasa, procedencia/binding de la
    # coordenada, procedencia urbana, bloqueos) es un hecho de la corrida y viaja en
    # el estado. Antes se buscaba solo dentro del contexto administrativo, donde no
    # está: el ejecutivo perdía el sector, el método, la geometría y el binding.
    mc = rs.get("market_context") or adm.get("market_context") or {}
    if not isinstance(mc, dict):
        mc = {}
    return {
        "versionado": (rs.get("evidence_manifest_input") or {}).get("versionado"),
        "run_id": rs.get("run_id"),
        "input": {"ciudad": rs.get("ciudad")},
        "identity": {**pi, **{k: adm.get(k) for k in
                              ("barrio", "comuna", "estrato", "tratamiento",
                               "edificabilidad_texto") if adm.get(k)}},
        # La procedencia REAL de la coordenada vive en el market_context (fuente, si está
        # verificada y su binding canónico). Antes se pasaba solo `coordinates`, que no
        # trae `verified` ni `provenance`: la evidencia de geometría salía con
        # `source: null` y «NO_VERIFICADA» mientras el ejecutivo de la MISMA corrida
        # imprimía «Geometría oficial: VERIFICADA». Un dato, un estado (P3).
        "coordinates": {
            **(mc.get("coordinates") or {}),
            "source": mc.get("coordinate_source"),
            "verified": bool(mc.get("coordinate_source_verified")),
            "coordinate_scope": mc.get("coordinate_scope"),
            "canonical_binding_status": mc.get("canonical_binding_status"),
            "provenance": mc.get("coordinate_provenance") or {},
        },
        "urban": rs.get("urban_context") or {},
        "urban_source_summary": mc.get("urban_source_summary") or {},
        # El estado urbano oficial vive en `market_context.official_urban_context`;
        # `urban_context` no tiene `barrio_status`, de modo que la evidencia urbana
        # nacía «PARCIAL» para siempre mientras la página 4 imprimía VERIFICADO.
        "official_urban_context": mc.get("official_urban_context") or {},
        "market": mc,
        "poi": rs.get("poi_state") or {},
        "volcan": (rs.get("risk_context") or {}).get("volcan") or {},
        "screening": rs.get("screening_summary") or {},
        "valuation": rs.get("valuation_state") or {},
        "gate": rs.get("release_state") or {},
        "receipts": rs.get("receipts") or {},
        "title_summary": rs.get("title_state") or {},
        "findings": rs.get("findings") or [],
        "solar": rs.get("solar_state") or {},
        "risk_context": rs.get("risk_context") or {},
        "historical_consistency": rs.get("historical_consistency") or {},
        # DICTUS 2.0C: activos gráficos de la corrida (mapa/sombras) con su huella.
        "visual_assets": rs.get("visual_assets") or {},
        "market_context": mc,
        "shadow_simulation": rs.get("shadow_simulation") or {},
        "shadow_manifest": rs.get("shadow_manifest") or {},
    }


def _estado_para_decision(origen: Dict[str, Any], plano: Dict[str, Any]) -> Dict[str, Any]:
    """Estado que consume el motor de decisión.

    Si la corrida trae `DictusRunState`, se usa TAL CUAL (una sola verdad). Si el
    llamador entregó un estado plano (compatibilidad), se reconstruye la forma de corrida
    a partir de los bloques del modelo, sin recalcular nada.
    """
    origen = origen or {}
    if origen.get("run_state_version"):
        return origen
    plano = plano or {}
    ident = dict(plano.get("canonical_property_identity") or {})
    return {
        "generated_at": (origen.get("receipts") or {}).get("generated_at"),
        "ciudad": (origen.get("input") or {}).get("ciudad"),
        "property_identity": ident,
        "title_state": plano.get("title_summary") or {},
        "urban_context": plano.get("urban_context") or {},
        "screening_summary": plano.get("screening_summary") or {},
        "poi_state": plano.get("poi_summary") or {},
        "solar_state": plano.get("solar_summary") or {},
        "valuation_state": plano.get("valuation") or {},
        "risk_context": plano.get("risk_context") or {},
        "market_context": plano.get("market_context") or {},
        "visual_assets": plano.get("visual_assets") or {},
        "shadow_simulation": origen.get("shadow_simulation") or {},
        "findings": plano.get("findings") or [],
        "historical_consistency": plano.get("historical_consistency") or {},
        "release_state": plano.get("release_state") or {},
    }


def construir_documento_maestro(estado: Dict[str, Any], *,
                                hallazgos: Optional[Iterable[Dict[str, Any]]] = None,
                                historial: Optional[Dict[str, Any]] = None,
                                folio: Optional[str] = None,
                                solar: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Modelo canónico del expediente: es la entrada del hash maestro y del render.

    Acepta el `DictusRunState` de 2.0B (recomendado) o el estado plano anterior.
    No recalcula nada: organiza lo que la ejecución ya produjo y declara lo que falta.
    """
    _origen = estado or {}          # estado de corrida (o plano) tal como llegó
    if (estado or {}).get("run_state_version"):
        estado = estado_legacy_desde_run_state(estado)
    e = estado or {}
    ident = e.get("identity") or {}
    urb = e.get("urban") or {}
    usm = e.get("urban_source_summary") or {}
    market = e.get("market") or {}
    val = e.get("valuation") or {}
    scr = e.get("screening") or {}
    coords = e.get("coordinates") or {}
    gate = e.get("gate") or {}
    rec = e.get("receipts") or {}
    folio = folio or ident.get("folio") or "SIN-FOLIO"
    ts = rec.get("generated_at")
    hist = historial or e.get("historical_consistency") or {}

    manifiesto = construir_evidence_manifest(e, folio=folio, timestamp=ts)
    modelo: Dict[str, Any] = {
        "run_id": e.get("run_id"),
        "document_identity": {
            "producto": "DICTUS · Expediente verificado de inmueble",
            "dictus_id": dictus_id(folio, str(ts or "")),
            "folio": folio,
            "generated_at": ts,
            "ciudad": (e.get("urban") or {}).get("barrio") and (e.get("input") or {}).get("ciudad")
            or (e.get("input") or {}).get("ciudad"),
            "versionado": e.get("versionado"),
            "maestro_version": MASTER_MANIFEST_VERSION,
        },
        "canonical_property_identity": {
            "folio": ident.get("folio"), "nupre": ident.get("nupre"),
            "codigo_catastral": ident.get("codigo_catastral"),
            "direccion_raw": ident.get("direccion_raw"),
            "direccion_normalizada": ident.get("direccion_normalizada"),
            "unidad": ident.get("unidad"), "torre": ident.get("torre"),
            "apartamento": ident.get("apartamento"),
            "estado": ident.get("estado"),
            "resolution_status": ident.get("resolution_status"),
            "resolution_method": ident.get("resolution_method"),
            "resolution_confidence": ident.get("resolution_confidence"),
            "identity_verified": ident.get("identity_verified"),
            "identity_source": ident.get("identity_source"),
        },
        "title_summary": e.get("title_summary") or {},
        "findings": list(hallazgos or e.get("findings") or []),
        "screening_summary": scr,
        "urban_context": urb,
        "risk_context": {"volcan": e.get("volcan"),
                         "amenaza": (urb.get("predio_entorno") or {}).get("amenaza_remocion_masa")
                         if isinstance(urb.get("predio_entorno"), dict) else None},
        "poi_summary": e.get("poi"),
        "solar_summary": solar or e.get("solar") or {},
        "valuation": val,
        "poi_summary": e.get("poi"),
        "evidence_manifest": manifiesto,
        "source_versions": {
            "urban_source_mode": usm.get("source_mode"),
            "coordinate_source": coords.get("source"),
            "coordinate_provenance": coords.get("provenance"),
            "release_gate": {"release_status": gate.get("release_status"),
                             "policy": gate.get("policy"),
                             "environment": gate.get("environment")},
        },
        "methodology_versions": {
            "market_methodology_id": market.get("market_methodology_id"),
            "market_methodology_version": market.get("market_methodology_version"),
            "market_methodology_sha256": market.get("market_methodology_sha256"),
            "matcher_version": scr.get("matcher_version"),
        },
        # DICTUS 2.0C: hechos materiales que el ejecutivo debe poder imprimir sin
        # volver a calcularlos (y que antes se perdían en la proyección del estado).
        "visual_assets": e.get("visual_assets") or {},
        "market_context": market,
        "shadow_manifest": e.get("shadow_manifest") or {},
        "historical_consistency": {
            "veredicto": hist.get("veredicto"),
            "versiones_comparadas": hist.get("versiones_comparadas"),
            "conflictos_abiertos": [{"atributo": c.get("atributo"), "valores": c.get("valores"),
                                     "detalle": c.get("detalle")}
                                    for c in (hist.get("conflictos_abiertos") or [])],
            "cambios_explicados": [{"atributo": c.get("atributo"), "detalle": c.get("detalle")}
                                   for c in (hist.get("cambios_explicados") or [])],
        },
    }
    # 2.0D: la cadena de decisión se deriva del estado canónico y entra al modelo (y por
    # tanto al hash maestro). No recalcula motores: organiza lo ya producido.
    try:
        import dictus_decision as _dd
        _fuente = _estado_para_decision(_origen, modelo)
        _decision = _dd.construir(_fuente,
                                  captura_sombras=(_fuente.get("shadow_simulation") or {}))
        modelo["observations"] = _decision["observations"]
        modelo["decision_findings"] = _decision["findings"]
        modelo["recommendations"] = _decision["recommendations"]
        modelo["decision_gates"] = _decision["decision_gates"]
        modelo["disposition"] = _decision["disposition"]
        modelo["human_reviews"] = [_decision["human_review"]]
        modelo["decision_matrix"] = _decision["decision_matrix"]
        modelo["shadow_manifest"] = _decision["shadow_manifest"]
        modelo["visual_assets"] = _decision["visual_assets"] or modelo.get("visual_assets")
        modelo["decision_grammar_version"] = _decision["grammar_version"]
    except Exception as _e_dec:  # noqa: BLE001 — la gramática no puede tumbar el documento
        print(f"[DICTUS][DECISION] no evaluable: {_e_dec}")
    h = master_hash(modelo)
    modelo["master_hash"] = h
    modelo["master_hash_abreviado"] = master_hash_abreviado(h)
    return modelo


def verificar(modelo: Dict[str, Any], hash_registrado: str) -> Dict[str, Any]:
    """Contrato de VERIFY DICTUS (§AO): recalcula y compara. No implementa
    infraestructura externa; solo el contrato y su resultado."""
    recalculado = master_hash(modelo)
    return {
        "master_hash_registrado": hash_registrado,
        "master_hash_recalculado": recalculado,
        "match": bool(hash_registrado) and recalculado == hash_registrado,
        "generated_at": (modelo.get("document_identity") or {}).get("generated_at"),
        "evidence_count": (modelo.get("evidence_manifest") or {}).get("evidence_count"),
        "seal_status": (modelo.get("evidence_manifest") or {}).get("estado"),
        "master_manifest_version": MASTER_MANIFEST_VERSION,
    }

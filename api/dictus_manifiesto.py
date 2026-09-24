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

MASTER_MANIFEST_VERSION = "dictus-master-manifest/1.0.0"

# Bloques canónicos que entran al hash maestro (§J). El orden de esta tupla es parte
# del contrato: NO se reordena sin cambiar la versión del manifest.
BLOQUES_CANONICOS = (
    "document_identity",
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
    "historical_consistency",
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
    cuerpo = serializacion_canonica({"bloques": {"_evidencia": contenido}})
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
    items.append(_ev("EV-URBANO", "CAPAS_OFICIALES_MUNICIPALES", urb.get("source"),
                     usm.get("source_mode"), sujeto, ts,
                     {"barrio": urb.get("barrio"), "estrato": urb.get("estrato"),
                      "tratamiento": urb.get("tratamiento"),
                      "altura_maxima": urb.get("altura_maxima"),
                      "clase_suelo": urb.get("predio_entorno", {}).get("clase_suelo")
                      if isinstance(urb.get("predio_entorno"), dict) else None,
                      "modo": usm.get("source_mode")},
                     "SELLADA" if urb.get("barrio_status") == "VERIFIED_OFFICIAL" else "PARCIAL"))
    items.append(_ev("EV-MERCADO", "METODOLOGIA_DE_MERCADO", market.get("rate_source"),
                     market.get("market_methodology_version"), sujeto, ts,
                     {"sector": market.get("sector"), "match_type": market.get("match_type"),
                      "value_m2": market.get("value_m2"),
                      "metodologia_sha256": market.get("market_methodology_sha256")},
                     "SELLADA" if market.get("ready") else "PARCIAL"))
    items.append(_ev("EV-VALORACION", "VALORACION", val.get("source_m2"),
                     market.get("market_methodology_version"), sujeto, ts,
                     {"autorizada": (val.get("authorization") or {}).get("allowed"),
                      "consolidado": val.get("consolidado"),
                      "value_m2": val.get("value_m2"),
                      "motivo_no_aplica": val.get("motivo_no_aplica")},
                     "SELLADA" if (val.get("authorization") or {}).get("allowed") else "NO_AUTORIZADA"))
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
    return {
        "master_manifest_version": MASTER_MANIFEST_VERSION,
        "dictus_id": dictus_id(folio, str(ts or "")),
        "property": sujeto,
        "generated_at": ts,
        "evidencias": items,
        "evidence_count": len(items),
        "fuentes": fuentes,
        "selladas": sum(1 for i in items if i["status"] == "SELLADA"),
        "estado": ("SELLADO" if all(i["status"] == "SELLADA" for i in items)
                   else "PARCIAL_CON_DECLARACIONES"),
    }


# ── Documento maestro (§J) y verificación futura (§AO) ────────────────────────
def construir_documento_maestro(estado: Dict[str, Any], *,
                                hallazgos: Optional[Iterable[Dict[str, Any]]] = None,
                                historial: Optional[Dict[str, Any]] = None,
                                folio: Optional[str] = None,
                                solar: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Modelo canónico del expediente: es la entrada del hash maestro y del render.

    No recalcula nada: organiza lo que la ejecución ya produjo y declara lo que falta.
    """
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

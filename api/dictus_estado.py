# -*- coding: utf-8 -*-
"""DICTUS 2.0B — ESTADO CANÓNICO DE CORRIDA (`DictusRunState`).

Una sola corrida del producto produce **una sola verdad**: este estado. De él derivan el
`ExecutiveDocumentModel`, el `EVIDENCE MANIFEST`, el `DICTUS_MASTER_HASH` y los dos
documentos (ejecutivo y técnico). El ejecutivo **NO** lee el PDF técnico ni extrae texto:
consume este estado.

Cómo se obtiene sin duplicar consultas
--------------------------------------
El producto ya pasa por un único borde estructurado: el contexto del
`PRE_RENDER_CONSISTENCY_GATE`, que contiene `canonical_identity`, `predio_real`,
`administrative_context`, `analysis`, `hallazgos`, `titulux`, `res_avaluo` y la
autorización de valoración. Los OBSERVADORES de este módulo (solo lectura) capturan ese
contexto, el resultado de POI, el riesgo volcánico, los recibos, el resultado del gate de
liberación y el asoleamiento calculado — todos producidos por la MISMA corrida.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

# Estados de coherencia compartidos con la capa de historia (un solo vocabulario).
from dictus_historia import (CAMBIO_CON_FUENTE, HISTORICAL_CONFLICT,
                             REQUIERE_VALIDACION, SIN_DATO, VERIFICADO)

RUN_STATE_VERSION = "dictus-run-state/1.0.0"

# Contrato del ítem de equipamiento (§9). Orden canónico de campos.
POI_ITEM_FIELDS = ("category", "name", "type", "lat", "lon", "distance_m",
                   "walking_time_estimate", "travel_time_estimate", "source",
                   "queried_at", "status")

# Velocidad peatonal de referencia para la estimación de tiempo a pie (m/min).
VELOCIDAD_PEATONAL_M_MIN = 80.0


# ── utilidades ────────────────────────────────────────────────────────────────
def _norm(txt: Any) -> str:
    s = unicodedata.normalize("NFKD", str(txt or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.upper().split())


def _ahora() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _num(v, tipos=(int, float)):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f


# ── POI: normalización al contrato del estado (§9) ────────────────────────────
def normalizar_poi_items(poi_result: Optional[Dict[str, Any]], *,
                         queried_at: Optional[str] = None) -> Dict[str, Any]:
    """Convierte el resultado crudo de `get_poi_result` en `poi_state` canónico.

    Devuelve `{"items": [...], "por_categoria": {...}, "sources_attempted": [...],
    "sources_succeeded": [...], "queried_at": ...}`.

    Reglas:
      · `distance_m` SOLO si la fuente la devolvió (el motor la calcula con haversine
        desde la coordenada autorizada). Ausente ⇒ `None` y el render dice
        «DISTANCIA NO DISPONIBLE». **Nunca se convierte en 0**.
      · `walking_time_estimate` se deriva de `distance_m` con velocidad peatonal de
        referencia y se declara como ESTIMACIÓN (no medición).
      · `status` por ítem: `OBTENIDO` (vino de la fuente) — no se fabrican ítems.
    """
    r = poi_result or {}
    items_raw = r.get("items") or {}
    status_cat = r.get("category_status") or {}
    ts = queried_at or r.get("queried_at") or _ahora()
    items: List[Dict[str, Any]] = []
    por_categoria: Dict[str, Dict[str, Any]] = {}

    for categoria in sorted(items_raw.keys()):
        lista = items_raw.get(categoria) or []
        detalle: List[Dict[str, Any]] = []
        for p in lista:
            if not isinstance(p, dict):
                continue
            dist = _num(p.get("distance"))
            if dist is None:
                dist = _num(p.get("distance_m"))
            item = {
                "category": categoria,
                "name": p.get("name") or p.get("nombre"),
                "type": p.get("type") or p.get("tipo") or categoria,
                "lat": _num(p.get("lat")),
                "lon": _num(p.get("lon")),
                "distance_m": round(dist, 1) if dist is not None else None,
                "walking_time_estimate": (f"~{max(1, int(round(dist / VELOCIDAD_PEATONAL_M_MIN)))} min a pie"
                                          if dist is not None else None),
                "travel_time_estimate": (f"~{max(1, int(round(dist / VELOCIDAD_PEATONAL_M_MIN)))} min a pie"
                                         if dist is not None else None),
                "source": p.get("source") or r.get("source"),
                "queried_at": ts,
                "status": "OBTENIDO",
            }
            items.append(item)
            detalle.append(item)
        detalle.sort(key=lambda x: (x["distance_m"] is None, x["distance_m"] or 0.0))
        por_categoria[categoria] = {
            "status": status_cat.get(categoria) or ("AVAILABLE" if detalle else "NO_MATCH"),
            "count": len(detalle),
            "items": detalle,
            "mas_cercano_m": detalle[0]["distance_m"] if detalle else None,
            "mas_cercano": detalle[0]["name"] if detalle else None,
            "distance_available": any(d["distance_m"] is not None for d in detalle),
        }

    return {
        "version": RUN_STATE_VERSION,
        "queried_at": ts,
        "items": items,
        "por_categoria": por_categoria,
        "sources_attempted": list(r.get("sources_attempted") or []),
        "sources_succeeded": list(r.get("sources_succeeded") or []),
        "item_count": len(items),
        "distance_available": any(i["distance_m"] is not None for i in items),
    }


# ── hallazgos: normalización con actores (§H/§I) ──────────────────────────────
def afectados_de_finding(titulo: str, codigo: str = "") -> Tuple[List[str], str]:
    """Actores afectados e impacto por actor, derivados del TIPO de hallazgo."""
    t = _norm(f"{titulo} {codigo}")
    if any(k in t for k in ("HIPOTECA", "EMBARGO", "CAUTELAR", "GRAVAMEN", "LIMITACION",
                            "AFECTACION")):
        return (["COMPRADOR", "VENDEDOR", "INMOBILIARIA", "BANCO / FINANCIADOR"],
                "Comprador: la carga se hereda con el inmueble. Vendedor: condición para "
                "transferir. Inmobiliaria: riesgo de retraso o caída. Banco: afecta la "
                "garantía y la prelación.")
    if "AUSENCIA DE CERTIFICADO" in t or "AUSENCIA DE CTL" in t:
        return (["COMPRADOR", "VENDEDOR", "BANCO / FINANCIADOR", "ASEGURADORA DE TÍTULO"],
                "Sin certificado no se verifica titularidad ni cargas: el banco y el "
                "asegurador de títulos no pueden suscribir y el comprador asume riesgo no "
                "medido.")
    if any(k in t for k in ("RIESGO", "AMENAZA", "GEO", "HIDROLOG", "REMOCION")):
        return (["COMPRADOR", "BANCO / FINANCIADOR", "ASEGURADORA"],
                "Puede exigir verificación técnica específica y condicionar la financiación "
                "o la póliza.")
    if "TITULARIDAD" in t or "CONTRAPARTE" in t or "SCREENING" in t:
        return (["COMPRADOR", "VENDEDOR", "INMOBILIARIA", "ASEGURADORA DE TÍTULO"],
                "Quién puede vender y con quién se contrata es condición de la operación.")
    if "AREA" in t or "METRAJE" in t or "INCONSISTENCIA" in t:
        return (["COMPRADOR", "BANCO / FINANCIADOR"],
                "El área sustenta el valor y la garantía: una inconsistencia afecta el "
                "crédito y la tasación.")
    return ([], "")


def normalizar_findings(hallazgos: Any) -> List[Dict[str, Any]]:
    """Hallazgos del producto (tuplas del render) al contrato ejecutivo.

    Acepta las tuplas reales `(severidad, color, bg, titulo, fuente, descripcion,
    implicacion)` y también dicts ya normalizados. No inventa hallazgos.
    """
    salida: List[Dict[str, Any]] = []
    for h in (hallazgos or []):
        if isinstance(h, dict):
            titulo = h.get("titulo") or h.get("title") or ""
            salida.append({
                "severidad": str(h.get("severidad") or h.get("severity") or "").upper(),
                "codigo": h.get("codigo") or h.get("code") or "",
                "titulo": titulo, "fuente": h.get("fuente") or h.get("source"),
                "por_que": h.get("por_que") or h.get("descripcion") or "",
                "accion": h.get("accion") or h.get("implicacion") or "",
                "afectados": h.get("afectados") or [],
                "impacto": h.get("impacto") or "",
            })
            continue
        if isinstance(h, (list, tuple)) and len(h) >= 6:
            _sev, _c, _bg, titulo, fuente, desc = h[0], h[1], h[2], h[3], h[4], h[5]
            impl = h[6] if len(h) > 6 else ""
            codigo = str(titulo).split("|")[0].strip() if "|" in str(titulo) else ""
            titulo_txt = str(titulo).split("|", 1)[1].strip() if "|" in str(titulo) else str(titulo)
            afectados, impacto = afectados_de_finding(titulo_txt, codigo)
            salida.append({"severidad": str(_sev).upper(), "codigo": codigo,
                           "titulo": titulo_txt, "fuente": str(fuente or ""),
                           "por_que": " ".join(str(desc or "").split()),
                           "accion": " ".join(str(impl or "").split()),
                           "afectados": afectados, "impacto": impacto})
    orden = {"ALTO": 0, "MEDIO": 1, "INFORMATIVO": 2}
    salida.sort(key=lambda x: orden.get(str(x["severidad"]).upper(), 3))
    return salida


# ── observadores (solo lectura) ───────────────────────────────────────────────
def instalar_observadores(destino: Dict[str, Any]) -> Dict[str, Any]:
    """Instrumenta el producto con OBSERVADORES de solo lectura.

    No altera ningún cálculo: guarda lo que la corrida ya produjo en `destino`.
    Devuelve `destino` para encadenar.
    """
    import consistency
    import pdf_compiler
    import poi_engine
    import receipts as receipts_mod
    try:
        import volcan_engine as volcan_mod  # type: ignore
    except Exception:  # noqa: BLE001
        volcan_mod = None

    _gate_real = consistency.ejecutar_gate

    def _gate_observado(contexto, **kw):
        destino["ctx"] = contexto
        return _gate_real(contexto, **kw)

    consistency.ejecutar_gate = _gate_observado
    pdf_compiler.ejecutar_gate = _gate_observado

    _poi_real = poi_engine.get_poi_result
    pdf_compiler.get_poi_result = _poi_real

    def _poi_observado(*a, **k):
        r = _poi_real(*a, **k)
        destino["poi"] = r
        return r

    poi_engine.get_poi_result = _poi_observado
    pdf_compiler.get_poi_result = _poi_observado

    _rec_real = receipts_mod.build_execution_receipts

    def _rec_observado(*a, **k):
        r = _rec_real(*a, **k)
        destino["receipts"] = r
        return r

    receipts_mod.build_execution_receipts = _rec_observado

    _gate_rel_real = pdf_compiler._gate_liberacion_inicial

    def _gate_rel_observado(*a, **k):
        r = _gate_rel_real(*a, **k)
        destino["release"] = r
        return r

    pdf_compiler._gate_liberacion_inicial = _gate_rel_observado

    if volcan_mod is not None and hasattr(volcan_mod, "verificar_riesgo_volcanico"):
        _vol_real = volcan_mod.verificar_riesgo_volcanico

        def _vol_observado(*a, **k):
            r = _vol_real(*a, **k)
            destino["volcan"] = r
            return r

        volcan_mod.verificar_riesgo_volcanico = _vol_observado

    return destino


def registrar_solar(resultados: List[Tuple[Any, ...]]) -> None:
    """El compilador expone el asoleamiento que YA calculó (sin recalcular nada)."""
    _SOLAR["momentos"] = [
        {"hora": str(r[0]), "azimut": str(r[1]), "elevacion": str(r[2]),
         "estado": str(r[3]), "descripcion": str(r[4]) if len(r) > 4 else None}
        for r in (resultados or [])
    ]


_SOLAR: Dict[str, Any] = {}


# ── estado canónico de corrida (§3) ───────────────────────────────────────────
def construir_run_state(captura: Dict[str, Any], *, run_id: str, folio: str,
                        ciudad: str = "barranquilla",
                        versionado: Optional[Dict[str, Any]] = None,
                        generated_at: Optional[str] = None,
                        area: Any = None,
                        tipo_unidad: Optional[str] = None) -> Dict[str, Any]:
    """`DictusRunState`: la verdad única de la corrida, sin recalcular nada.

    `captura` es lo que dejaron los observadores: `{"ctx", "poi", "receipts",
    "volcan", "release"}`. `area` y `tipo_unidad` vienen de la entrada del caso (el
    CTL ya analizado por el producto), no de ninguna extracción posterior.
    """
    captura = captura or {}
    ctx = captura.get("ctx") or {}
    cid = ctx.get("canonical_identity") or {}
    pre = ctx.get("predio_real") or {}
    predio = pre.get("predio") or {}
    ent = pre.get("entorno") or {}
    adm = ctx.get("administrative_context") or {}
    analysis = ctx.get("analysis") or {}
    titu = ctx.get("titulux") or {}
    res = ctx.get("res_avaluo") or {}
    receipts = captura.get("receipts") or {}

    anotaciones = analysis.get("anotaciones") or []
    gravamenes = [{"anotacion": a[0], "fecha": a[1], "tipo": a[2], "partes": a[3],
                   "estado": a[4]}
                  for a in anotaciones
                  if isinstance(a, (list, tuple)) and len(a) >= 5
                  and ("GRAVAMEN" in str(a[2]).upper() or "MEDIDA CAUTELAR" in str(a[2]).upper()
                       or "LIMITACION" in str(a[2]).upper())
                  and "CANCELADA" not in str(a[4]).upper()]

    return {
        "run_state_version": RUN_STATE_VERSION,
        "run_id": run_id,
        "generated_at": generated_at or _ahora(),
        "ciudad": ciudad,
        "property_identity": {
            "folio": folio, "nupre": cid.get("nupre"),
            "codigo_catastral": cid.get("codigo_catastral"),
            "direccion_raw": cid.get("direccion_raw"),
            "direccion_normalizada": cid.get("direccion_normalizada"),
            "torre": cid.get("torre"), "apartamento": cid.get("apartamento"),
            "unidad": cid.get("unidad"),
            "estado": cid.get("estado"),
            "resolution_status": cid.get("resolution_status"),
            "resolution_method": cid.get("resolution_method"),
            "resolution_confidence": cid.get("resolution_confidence"),
            "identity_verified": cid.get("identity_verified"),
            "identity_source": cid.get("identity_source"),
            "administrativo": adm,
        },
        "title_state": {
            "folio": analysis.get("folio"),
            "titulares": analysis.get("titulares"),
            "modalidad_adquisicion": analysis.get("modalidad_adquisicion"),
            "circulo_registral": analysis.get("circulo_registral"),
            "anotaciones_total": len(anotaciones),
            "gravamenes_vigentes": gravamenes,
            "acreedor_snr": analysis.get("acreedor_snr"),
            "hipoteca_vigente": analysis.get("hipoteca_vigente"),
            "certificado_adjuntado": bool(analysis.get("texto_ctl")),
        },
        "findings": normalizar_findings(ctx.get("hallazgos")),
        "screening_summary": titu.get("screening_summary") or {},
        "urban_context": {
            "area": _num(area),
            "tipo_unidad": tipo_unidad,
            "barrio": adm.get("barrio") or ent.get("barrio"),
            "localidad": adm.get("comuna") or ent.get("localidad"),
            "estrato": adm.get("estrato") or ent.get("estrato"),
            "tratamiento": ent.get("tratamiento"),
            "tipo_tratamiento": ent.get("tipo_tratamiento"),
            "altura_maxima": ent.get("altura_maxima"),
            "clase_suelo": ent.get("clase_suelo"),
            "area_actividad": adm.get("area_actividad"),
            "destino_economico": predio.get("destino_economico"),
            "condicion_juridica": (pre.get("condicion") or {}).get("condicion_juridica")
            or adm.get("condicion_juridica"),
            "predio_disponible": pre.get("disponible"),
            "entorno_disponible": ent.get("disponible"),
        },
        "risk_context": {
            "volcan": captura.get("volcan"),
            "amenaza_remocion_masa": ent.get("amenaza_remocion_masa"),
            "areas_en_riesgo": ent.get("areas_en_riesgo"),
            "inundacion": ent.get("inundacion"),
            "riesgo_no_mitigable": ent.get("riesgo_no_mitigable"),
        },
        "poi_state": normalizar_poi_items(captura.get("poi")),
        "solar_state": {"momentos": (captura.get("solar") or {}).get("momentos") or [],
                        "altura_dependiente": True,
                        "tipo": "SIMULACION_GEOMETRICA",
                        "advertencia": ("La proyección corresponde a una simulación "
                                        "geométrica y no sustituye una inspección física."),
                        "habitacion_ambigua": {}},
        "valuation_state": {
            **{k: res.get(k) for k in ("value_m2", "consolidado", "banda_baja", "banda_alta",
                                       "sector", "match_type", "metodologia_aplica",
                                       "motivo_no_aplica", "m1", "m2", "m3")},
            "authorization": ctx.get("valuation_authorization") or {},
        },
        "release_state": captura.get("release") or {},
        "evidence_manifest_input": {
            "articulos": [
                {"tipo": "IDENTIDAD_CANONICA", "fuente": cid.get("identity_source") or "SNR/geoportal"},
                {"tipo": "TITULOS", "fuente": "Certificado de tradición y libertad (SNR)"},
                {"tipo": "SCREENING_CONTRAPARTES",
                 "fuente": "listas restrictivas y sancionatorias aplicables"},
                {"tipo": "URBANO", "fuente": "capas oficiales del municipio"},
                {"tipo": "EQUIPAMIENTO", "fuente": "proveedor de mapas abierto"},
                {"tipo": "AMENAZAS", "fuente": "servicios municipales y SGC"},
                {"tipo": "VALORACION", "fuente": "metodología de mercado (Lonja)"},
            ],
            "versionado": versionado or {},
        },
        "receipts": receipts,
    }


def agregar_findings_de_coherencia(run_state: Dict[str, Any],
                                   historial: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Incorpora al ESTADO los hallazgos de coherencia histórica abiertos.

    Un conflicto histórico del mismo predio es un hecho de la corrida: si se inyectara
    solo en el render, el documento impreso y el estado canónico dirían cosas distintas
    (dos verdades). Aquí entra al estado —y por tanto al modelo, al manifest y al hash—
    antes de construir cualquier documento.
    """
    rs = run_state or {}
    hist = historial or {}
    existentes = {f.get("codigo") + (f.get("titulo") or "") for f in (rs.get("findings") or [])}
    for c in (hist.get("conflictos_abiertos") or []):
        atributo = str(c.get("atributo") or "").replace("_", " ")
        titulo = f"Coherencia histórica: {atributo}"
        if "H-COH" + titulo in existentes:
            continue
        afectados, impacto = afectados_de_finding(titulo, "H-COH")
        rs.setdefault("findings", []).append({
            "severidad": "ALTO", "codigo": "H-COH", "titulo": titulo,
            "fuente": "Expediente histórico del mismo inmueble",
            "por_que": c.get("detalle") or "",
            "accion": c.get("accion") or ("Resolver con la ficha/polígono aplicable antes de "
                                          "usar la cifra."),
            "afectados": afectados, "impacto": impacto,
        })
    orden = {"ALTO": 0, "MEDIO": 1, "INFORMATIVO": 2}
    rs["findings"] = sorted(rs.get("findings") or [],
                            key=lambda x: orden.get(str(x.get("severidad")).upper(), 3))
    return rs


def huella_estado(estado: Dict[str, Any]) -> str:
    """Huella determinista del estado (para comparar corridas)."""
    canon = json.dumps(estado, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                       default=str)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


# ── verificación del hash maestro (§13) ──────────────────────────────────────
MATCH = "MATCH"
MISMATCH = "MISMATCH"
INVALID_MANIFEST = "INVALID_MANIFEST"


def verify_dictus_master_hash(manifest: Any, expected_hash: str) -> Dict[str, Any]:
    """Verifica el hash maestro del manifest (§13).

    Acepta el manifest publicado (con su modelo dentro) o el modelo canónico directo.
    Devuelve `{"result": MATCH|MISMATCH|INVALID_MANIFEST, ...}`. No crea servicios
    externos: contrato interno listo para exponerse cuando exista infraestructura.
    """
    import dictus_manifiesto as dm
    if not isinstance(manifest, dict):
        return {"result": INVALID_MANIFEST, "detalle": "el manifest no es un objeto"}
    modelo = manifest.get("modelo") if isinstance(manifest.get("modelo"), dict) else manifest
    _bloques_presentes = [b for b in ("document_identity", "canonical_property_identity",
                                      "findings", "evidence_manifest") if b in modelo]
    if not _bloques_presentes:
        return {"result": INVALID_MANIFEST,
                "detalle": "el manifest no contiene bloques canónicos reconocibles",
                "master_manifest_version": dm.MASTER_MANIFEST_VERSION}
    recalculado = dm.master_hash(modelo)
    return {
        "result": MATCH if recalculado == expected_hash else MISMATCH,
        "master_hash_recalculado": recalculado,
        "master_hash_esperado": expected_hash,
        "master_manifest_version": dm.MASTER_MANIFEST_VERSION,
        "dictus_id": (modelo.get("document_identity") or {}).get("dictus_id"),
        "evidence_count": (modelo.get("evidence_manifest") or {}).get("evidence_count"),
        "bloques_verificados": _bloques_presentes,
    }

# -*- coding: utf-8 -*-
"""DICTUS ESTIMATION ENGINE v1.0 · FASE 3 — INTEGRACIÓN CON EL ESTADO DE CORRIDA.

Este módulo es la ÚNICA puerta entre el estado canónico de una corrida
(`DICTUS_RUN_STATE_*.json`, `DICTUS_MANIFEST_*.json`) y el motor de estimación
(`api/estimation.py`, Fase 2). No estima por su cuenta: construye la ENTRADA en la
forma del contrato y llama a `estimation.estimar(...)`.

Reglas duras que este módulo respeta (Fase 3 §32/§33/§39):

  · NO inventa fuentes. Cada insumo económico viaja con la procedencia REAL que la
    corrida declara (evidencias SELLADAS del manifest, `origin` del run state). Si la
    corrida no declara una fuente de mercado automática, la entrada va vacía en ese
    insumo y el motor cierra: la ausencia se DECLARA, no se rellena.
  · Los parámetros escritos a mano (`MANUAL_CONFIG`) y los priors del modelo
    (`MODEL_PRIOR`) entran a la entrada —para que su presencia sea auditable— pero
    EXCLUIDOS del cálculo. Por eso `manual inputs used = 0` y `legacy priors used = 0`
    no son una promesa: son el resultado de la composición de `origin` del motor.
  · El histórico forense entra por `historico_forense` y el motor lo copia con
    `usado_como_input = False`: NUNCA es insumo del cálculo (y por eso no puede
    reabrir la cifra retirada).

La cosecha de las capas municipales de mercado (`docs/estimation/MARKET_HARVEST_*.json`)
se incorpora SOLO si existe y trae procedencia completa. Si no existe, se declara su
ausencia: no se simula.
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

_AQUI = Path(__file__).resolve().parent
if str(_AQUI) not in sys.path:
    sys.path.insert(0, str(_AQUI))

import atribucion_mercado as am   # noqa: E402
import estimation as est          # noqa: E402

ROOT = _AQUI.parent

INTEGRATION_VERSION = "dictus-estimation-integration/1.0.0"
HARVEST_GLOB = "MARKET_HARVEST_*.json"
ORIGEN_PRIOR_LEGACY_LOCAL = est.ORIGEN_PRIOR_LEGACY    # LEGACY_MODEL_PRIOR (no productivo)

# Evidencias SELLADAS que sostienen la identidad/área de la unidad (Fase 1 · auditoría).
EVIDENCIAS_IDENTIDAD = ("EV-IDENTIDAD", "EV-GEOMETRIA")
EVIDENCIAS_AREA = ("EV-IDENTIDAD", "EV-GEOMETRIA")

# Campos mínimos que debe traer una observación de la cosecha municipal para entrar
# como evidencia AGREGADA externa (nivel 3 de la escalera).
CAMPOS_COSECHA = ("url", "consultado_en", "http", "bytes", "sha256", "vigencia", "muestra")
# Capas municipales de mercado que la corrida puede incorporar (Source Pack · nivel 3).
CAPAS_MERCADO_ESPERADAS = (
    "observatorio/valoresm2_area",
    "observatorio/valorcompraventas",
    "observatorio/valorsuelourbano",
    "observatorio/arrendamientos",
    "observatorio/avaluocatastral",
    "observatorio/cantidadtransacciones",
)


# ── utilidades ───────────────────────────────────────────────────────────────
def _num(x: Any) -> Optional[float]:
    try:
        if x is None or x == "":
            return None
        return float(x)
    except (TypeError, ValueError):
        return None


def _fecha(x: Any) -> Optional[date]:
    if isinstance(x, datetime):
        return x.date()
    if isinstance(x, date):
        return x
    texto = str(x or "").strip()
    if not texto:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(texto, fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(texto).date()
    except ValueError:
        return None


def _iso(x: Any) -> Optional[str]:
    f = _fecha(x)
    return f.isoformat() if f else (str(x) if x else None)


def fuentes_selladas(modelo: Optional[Dict[str, Any]],
                     ids: Sequence[str]) -> List[Dict[str, Any]]:
    """Procedencia estructurada de evidencias SELLADAS del manifest (no de un literal).

    Sólo una evidencia con `status = SELLADA` y proveedor declarado puede sostener un
    insumo `COMPUTED_FROM_SOURCES`: su `content_hash` es el sha256 de la procedencia.
    Lo que no cumple el contrato simplemente NO entra (y el insumo degrada su origen).
    """
    evidencias = (((modelo or {}).get("evidence_manifest") or {}).get("evidencias")
                  or ((modelo or {}).get("evidencias")) or [])
    por_id = {str(e.get("evidence_id")): e for e in evidencias if isinstance(e, dict)}
    fuentes: List[Dict[str, Any]] = []
    for eid in ids:
        e = por_id.get(str(eid))
        if not e or str(e.get("status") or "").upper() != "SELLADA":
            continue
        proveedor = e.get("source")
        if not proveedor:
            continue   # un sello sin entidad declarada no acredita procedencia
        fuentes.append({"proveedor": str(proveedor),
                        "fecha": _iso(e.get("timestamp")),
                        "referencia": f"{eid} · {e.get('evidence_type')}",
                        "sha256": str(e.get("content_hash") or "")})
    return fuentes


# ── cosecha de capas municipales (opcional, NUNCA simulada) ──────────────────
# Checklist de procedencia (§39 · G). Una referencia agregada sólo entra como
# evidencia EXTERNA si su procedencia HTTP es auditable; lo que la fuente NO declara
# se registra como faltante y se declara (nunca se rellena).
CHECKLIST_PROCEDENCIA = ("url", "consultado_en", "http", "bytes", "sha256",
                         "vigencia", "muestra")


def _ruta_cosecha(ruta: Optional[Path] = None) -> Optional[Path]:
    if ruta is not None:
        return Path(ruta)
    candidatos = sorted((ROOT / "docs" / "estimation").glob(HARVEST_GLOB))
    return candidatos[0] if candidatos else None


def _procedencia_http(prov: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza la procedencia de una observación de cosecha al contrato del pack."""
    url = prov.get("url") or prov.get("url_consultada")
    consultado = prov.get("queried_at") or prov.get("consultado_en") or prov.get("fecha")
    return {"source_id": prov.get("source_id"), "proveedor": prov.get("proveedor"),
            "fecha": _iso(prov.get("fecha") or consultado), "referencia": prov.get("referencia"),
            "sha256": prov.get("sha256") or prov.get("payload_sha256"),
            "url": url, "consultado_en": consultado,
            "http": prov.get("http_status") or prov.get("http"),
            "bytes": prov.get("bytes"), "server": prov.get("server"),
            # `cf_ray` es la huella del borde de Cloudflare que sirvió la respuesta: es la
            # prueba de que el 200 vino del MISMO frente que devolvía 403 sin cabeceras
            # de navegación (ver el módulo de cosecha).
            "cf_ray": prov.get("cf_ray")}


def _checklist_de(prov: Dict[str, Any], *, vigencia: Any,
                  muestra: Any) -> Dict[str, bool]:
    return {"url": bool(prov.get("url")),
            "consultado_en": bool(prov.get("consultado_en")),
            "http": prov.get("http") in (200, "200"),
            "bytes": bool(prov.get("bytes")),
            "sha256": bool(prov.get("sha256")),
            "vigencia": bool(vigencia),
            "muestra": muestra not in (None, "", [], {})}


def cargar_estadisticas_de_cosecha(ruta: Optional[Path] = None) -> Tuple[List[Dict[str, Any]],
                                                                         Dict[str, Any]]:
    """Evidencia AGREGADA externa desde la cosecha municipal, si existe y es válida.

    Devuelve `(estadisticas, declaracion)`. La declaración incluye, por observación, el
    checklist de procedencia (`url`, `consultado_en`, `http`, `bytes`, `sha256`,
    `vigencia`, `muestra`) resuelto campo por campo: es la prueba de qué se incorporó y
    qué la fuente NO declara. Nunca se rellena un campo que la fuente calla.
    """
    archivo = _ruta_cosecha(ruta)
    if archivo is None or not archivo.exists():
        return [], {"estado": "NO INCORPORADA",
                    "ruta_esperada": f"docs/estimation/{HARVEST_GLOB}",
                    "motivo": ("la corrida no incorpora cosecha de las capas municipales de "
                               "mercado: no hay archivo de cosecha que cumpla el contrato"),
                    "capas_esperadas": list(CAPAS_MERCADO_ESPERADAS),
                    "checklist": {c: False for c in CHECKLIST_PROCEDENCIA}}
    try:
        datos = json.loads(Path(archivo).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [], {"estado": "NO INCORPORADA", "ruta": str(archivo),
                    "motivo": f"la cosecha existe pero no se pudo leer: {exc!r}",
                    "checklist": {c: False for c in CHECKLIST_PROCEDENCIA}}
    if not isinstance(datos, dict):
        datos = {"observaciones": datos}

    crudas: List[Dict[str, Any]] = []
    for ref in (datos.get("level_3_referencias") or []):
        if isinstance(ref, dict):
            crudas.append(ref)
    for obs in (datos.get("observaciones") or []):
        if isinstance(obs, dict):
            crudas.append(obs)
    if not crudas:
        for capa in (datos.get("capas") or {}).values():
            if isinstance(capa, dict):
                crudas.append(capa)

    validas: List[Dict[str, Any]] = []
    rechazadas: List[Dict[str, Any]] = []
    for o in crudas:
        prov = _procedencia_http(o.get("provenance") or o)
        rango = o.get("rango_valor_m2") or {}
        vigencia = o.get("vigencia_declarada") or o.get("vigencia")
        muestra = o.get("sample_size", o.get("muestra"))
        checklist = _checklist_de(prov, vigencia=vigencia, muestra=muestra)
        valor = _num(o.get("valor_m2") or o.get("value_m2"))
        usable = o.get("usable_for_estimation")
        if usable is False:
            rechazadas.append({"reference_id": o.get("reference_id") or o.get("source_id"),
                               "motivo": o.get("reason") or "la cosecha la declara NO usable",
                               "checklist": checklist})
            continue
        faltan = [c for c in CHECKLIST_PROCEDENCIA if not checklist.get(c)]
        if not all(checklist.get(c) for c in ("url", "consultado_en", "http", "bytes",
                                              "sha256")):
            rechazadas.append({"reference_id": o.get("reference_id") or o.get("source_id"),
                               "motivo": ("procedencia HTTP incompleta: no se incorpora una "
                                          "referencia que no se puede auditar"),
                               "faltan": faltan, "checklist": checklist})
            continue
        if valor is None and not (rango.get("min") and rango.get("max")):
            rechazadas.append({"reference_id": o.get("reference_id") or o.get("source_id"),
                               "motivo": "no declara valor por m² ni rango agregado",
                               "checklist": checklist})
            continue
        validas.append({
            "origen_tipo": am.ORIGEN_EXTERNO,
            "nivel": o.get("nivel") or o.get("clasificacion_contrato")
            or "LEVEL_3_AGGREGATED_MARKET_REFERENCES",
            # Identificadores de la referencia tal como la publica la cosecha: se citan
            # para que el lector pueda volver al payload crudo (`docs/estimation/raw/`).
            "reference_id": o.get("reference_id"),
            # §7.1 · DOS hechos separados: el CONTENIDO (estable) y la ADQUISICIÓN
            # (volátil). `evidence_hash` es alias del `content_hash` estable.
            "evidence_hash": o.get("content_hash") or o.get("evidence_hash"),
            "content_hash": o.get("content_hash"),
            "acquisition_id": o.get("acquisition_id"),
            "acquisition_hash": o.get("acquisition_hash"),
            "payload_sha256": o.get("payload_sha256") or o.get("sha256"),
            "hash_policy": o.get("hash_policy"),
            "source_id": prov.get("source_id"), "proveedor": prov.get("proveedor"),
            "fecha": prov.get("fecha"), "referencia": prov.get("referencia"),
            "sha256": prov.get("sha256"),
            # procedencia COMPLETA tal como la publica la fuente (se conserva literal)
            "provenance": {**{k: v for k, v in prov.items() if v not in (None, "")},
                           "url": prov.get("url"), "consultado_en": prov.get("consultado_en"),
                           "http": prov.get("http"), "bytes": prov.get("bytes")},
            "valor_m2": valor,
            "rango_valor_m2": ({"min": _num(rango.get("min")), "max": _num(rango.get("max")),
                                "unidad": rango.get("unidad") or "COP/m2"}
                               if rango else None),
            "sample_size": muestra,
            "vigencia_declarada": vigencia,
            "metodologia_declarada": o.get("metodologia_declarada"),
            "sector_referencia": o.get("sector_referencia"),
            "banda_area_m2": o.get("banda_area_m2"),
            "limitaciones_declaradas": list(o.get("limitaciones_declaradas") or []),
            "checklist_procedencia": checklist,
            "campos_que_la_fuente_no_declara": faltan,
            "valor_m2_no_promediado": (o.get("motivo_valor_m2_ausente")
                                       if valor is None else None),
        })
    declaracion = {"estado": "INCORPORADA" if validas else "NO INCORPORADA",
                   "ruta": str(Path(archivo).relative_to(ROOT))
                   if Path(archivo).is_relative_to(ROOT) else str(archivo),
                   "version_cosecha": datos.get("version_harvest"),
                   "proveedor": datos.get("proveedor"), "portal": datos.get("portal"),
                   "referencias_nivel_3_incorporadas": len(validas),
                   "observaciones_rechazadas": rechazadas,
                   "capas_consultadas": list((datos.get("capas") or {}).keys()),
                   # Evidencia HTTP LITERAL de lo incorporado: URL exacta, estado, bytes,
                   # sha256 del payload y la huella del borde que sirvió la respuesta.
                   "referencias_incorporadas": [
                       {"source_id": v.get("source_id"), "url": (v.get("provenance") or {}).get("url"),
                        "http": (v.get("provenance") or {}).get("http"),
                        "bytes": (v.get("provenance") or {}).get("bytes"),
                        "sha256": v.get("sha256"),
                        # §7.1 · identidad de hash: CONTENIDO estable vs ADQUISICIÓN volátil.
                        "content_hash": v.get("content_hash"),
                        "payload_sha256": v.get("payload_sha256"),
                        "acquisition_id": v.get("acquisition_id"),
                        "acquisition_hash": v.get("acquisition_hash"),
                        "consultado_en": (v.get("provenance") or {}).get("consultado_en"),
                        "server": (v.get("provenance") or {}).get("server"),
                        "cf_ray": (v.get("provenance") or {}).get("cf_ray"),
                        "nivel": v.get("nivel"),
                        "rango_valor_m2": v.get("rango_valor_m2"),
                        "sample_size": v.get("sample_size"),
                        "campos_que_la_fuente_no_declara": list(
                            v.get("campos_que_la_fuente_no_declara") or [])}
                       for v in validas],
                   "declaracion_de_la_cosecha": datos.get("declaracion")}
    return validas, declaracion


def cargar_brecha_de_cosecha(ruta: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Peticiones CONCRETAS campo a campo que la cosecha declara necesarias (§28).

    Se leen del `GAP_REPORT` de la propia cosecha: pedir «una fuente» en abstracto no
    sirve; lo que sirve es «esta capa, con estos campos, publicada por esta URL».
    """
    archivo = _ruta_cosecha(ruta)
    if archivo is None or not archivo.exists():
        return []
    try:
        datos = json.loads(Path(archivo).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    gap = (datos.get("GAP_REPORT") or {}) if isinstance(datos, dict) else {}
    return [dict(f) for f in (gap.get("fuentes_que_hay_que_incorporar") or [])
            if isinstance(f, dict)]



# ── entrada del motor ────────────────────────────────────────────────────────
def _estado_ubicacion(mc: Dict[str, Any]) -> Optional[str]:
    """Estado de ubicación en el vocabulario que el motor reconoce como verificado."""
    if not mc:
        return None
    if mc.get("coordinate_source_verified") is True:
        return str(mc.get("coordinate_source") or "VERIFIED_OFFICIAL")
    if mc.get("coordinate_source") and mc.get("canonical_binding_status") == "VERIFIED":
        return str(mc.get("coordinate_source"))
    return "RESOLVED" if mc.get("coordinates") else None


def _parametros_no_habilitantes(rs: Dict[str, Any]) -> Dict[str, Any]:
    """Lo que la corrida declara a mano o como prior: se DECLARA y NO se usa."""
    val = rs.get("valuation_state") or {}
    mc = rs.get("market_context") or {}
    met = mc.get("sector_metodologico") or {}
    origen_val = val.get("origins") or {}
    tasa = _num(met.get("value_m2"))
    tasa_manual = None
    if tasa is not None or met:
        tasa_manual = {
            "origen_tipo": am.ORIGEN_MANUAL,
            "valor": tasa,
            "valor_m2": tasa,
            "rango": [met.get("rango_min_m2"), met.get("rango_max_m2")],
            "source": mc.get("market_rate_source"),
            "fuente_declarada": met.get("source"),
            "vigencia_desde": met.get("vigencia_desde"),
            "vigencia_hasta": val.get("authorization", {}).get("vigencia_hasta")
            or met.get("effective_to"),
            "declarado_en": "market_context.sector_metodologico.value_m2",
            "metodologia_id": met.get("market_methodology_id"),
        }
    legacy = {k: v for k, v in origen_val.items() if str(v) in am.ORIGENES}
    modelo_legacy = None
    if legacy:
        modelo_legacy = {"origen_tipo": ORIGEN_PRIOR_LEGACY_LOCAL,
                         "parametros_declarados": legacy,
                         "valores": {k: _num(v) for k, v in legacy.items()},
                         "motivo": ("priors del modelo declarados por la corrida por "
                                    "parámetro, sin valores numéricos: no hay un modelo "
                                    "calibrado con muestra, error y vigencia"),
                         "sample_size": None, "calibration_error": None}
    return {"tasa_manual": tasa_manual, "modelo_legacy": modelo_legacy,
            "origenes_declarados": dict(origen_val),
            "referencia_estatica": None}


def construir_entrada(rs: Dict[str, Any],
                      modelo: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Entrada del contrato `estimation.estimar` desde el estado REAL de la corrida."""
    rs = rs or {}
    pi = rs.get("property_identity") or {}
    urb = rs.get("urban_context") or {}
    mc = rs.get("market_context") or {}
    met = mc.get("sector_metodologico") or {}
    fuentes_id = fuentes_selladas(modelo, EVIDENCIAS_IDENTIDAD)
    fuentes_area = fuentes_selladas(modelo, EVIDENCIAS_AREA)
    estadisticas, cosecha = cargar_estadisticas_de_cosecha()
    no_habilitantes = _parametros_no_habilitantes(rs)

    entrada: Dict[str, Any] = {
        "identidad": {
            "resuelta": bool(pi.get("identity_verified")) and bool(pi.get("folio")),
            "origen_tipo": am.ORIGEN_COMPUTADO,
            "fuentes": fuentes_id,
            "estado": pi.get("resolution_status") or pi.get("estado"),
            "metodo_resolucion": pi.get("resolution_method"),
            "folio": pi.get("folio"),
            "declarado_en": "property_identity (identity_verified)",
        },
        "ubicacion": {
            "utilizable": bool(mc.get("coordinate_source_verified")),
            "status": _estado_ubicacion(mc),
            "coordinate_source": mc.get("coordinate_source"),
            "canonical_binding_status": mc.get("canonical_binding_status"),
            "declarado_en": "market_context.coordinate_source_verified",
        },
        "area": {
            "valor_m2": _num(urb.get("area")),
            "origen_tipo": am.ORIGEN_COMPUTADO,
            "fuentes": fuentes_area,
            "fuente_declarada": "urban_context.area (área privada de la unidad)",
            "declarado_en": "urban_context.area",
        },
        "tipologia": {
            "valor": urb.get("tipologia") or (mc.get("tipologia") or {}).get("value"),
            "status": urb.get("tipologia_status") or (mc.get("tipologia") or {}).get("status"),
            "declarado_en": "urban_context.tipologia",
        },
        # ── soporte económico: lo que la corrida REALMENTE trae ───────────────
        "comparables": [],
        "estadisticas_externas": estadisticas,
        "modelo_calibrado": None,
        "costo_reposicion": None,
        "rental_reference": None,
        "cap_rate": None,
        "referencia_estatica": no_habilitantes["referencia_estatica"],
        "tasa_manual": no_habilitantes["tasa_manual"],
        "modelo_legacy": no_habilitantes["modelo_legacy"],
        # ── contexto de segmentación (no decide nada por sí solo) ─────────────
        "contexto": {"ciudad": rs.get("ciudad"),
                     "sector": met.get("matched_sector"),
                     "barrio": urb.get("barrio"),
                     "localidad": urb.get("localidad"),
                     "estrato": urb.get("estrato"),
                     "match_type": met.get("match_type")},
        "auditoria_de_entrada": {
            "integracion_version": INTEGRATION_VERSION,
            "cosecha_municipal": cosecha,
            "cosas_que_no_se_hicieron": [
                "no se convirtió la tasa declarada a mano en comparables ni en estadística",
                "no se rellenó ningún insumo con un valor inferido o supuesto",
                "no se incorporó la cosecha municipal porque no está disponible",
            ],
            "origenes_declarados_por_la_corrida": no_habilitantes["origenes_declarados"],
        },
    }
    return entrada


# ── ejecución ────────────────────────────────────────────────────────────────
def ejecutar(rs: Dict[str, Any], modelo: Optional[Dict[str, Any]] = None, *,
             hoy: Optional[date] = None, generado_en: Optional[str] = None,
             historico_forense: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Corre el motor sobre el estado real. Devuelve entrada, resultado y contadores.

    La fecha de referencia (`hoy`) se toma —si no se indica otra— de `generated_at` de
    la corrida: así el resultado es REPRODUCIBLE byte a byte a partir del expediente.
    """
    rs = rs or {}
    generado = generado_en or str(rs.get("generated_at") or "") or None
    referencia = hoy or _fecha(generado) or _fecha((rs.get("receipts") or {})
                                                   .get("generated_at")) or date.today()
    entrada = construir_entrada(rs, modelo)
    if historico_forense is None:
        historico_forense = rs.get("historical_consistency") or {}
    resultado = est.estimar(entrada, historico_forense=historico_forense,
                            generado_en=generado or None, hoy=referencia)
    return {"entrada": entrada, "resultado": resultado, "referencia": referencia.isoformat(),
            "contadores": contadores(resultado, entrada)}


def contadores(resultado: Dict[str, Any],
               entrada: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Contadores de aceptación (§39), DERIVADOS del resultado — nunca autoinformados."""
    r = resultado or {}
    e = entrada or {}
    comp = r.get("origin_composition") or {}
    cuenta = dict(comp.get("cuenta_por_clase") or {})
    insumos = r.get("inputs") or {}
    comparables_accepted = int(insumos.get("comparables_usados") or 0)
    comparables_rejected = len(insumos.get("comparables_rechazados") or [])
    estadisticas = len(e.get("estadisticas_externas") or [])
    declarados = int(insumos.get("comparables_declarados") or 0)
    return {
        # Observaciones de mercado REALES (nivel 1-3) disponibles en el expediente.
        "market_observations_count": declarados + estadisticas,
        "market_observations_detail": {
            "comparables_declarados": declarados,
            "estadisticas_agregadas_externas": estadisticas,
            "cosecha_municipal_incorporada": bool(estadisticas),
        },
        "comparables_accepted": comparables_accepted,
        "comparables_rejected": comparables_rejected,
        # Clases de `origin` que PARTICIPARON del cálculo (composición R0-R6).
        "origins_used": list(comp.get("clases_usadas") or []),
        "origins_used_count": len(set(comp.get("clases_usadas") or [])),
        "origin_composition": comp.get("origin"),
        "origin_rule": comp.get("regla"),
        # Aceptación dura: un parámetro a mano o un prior legacy NO pueden participar.
        "manual_inputs_used": int(cuenta.get(am.ORIGEN_MANUAL, 0)),
        "legacy_priors_used": int(cuenta.get(est.ORIGEN_PRIOR_LEGACY, 0)
                                  + cuenta.get(am.ORIGEN_PRIOR, 0)),
        "manual_inputs_declared": int(bool(e.get("tasa_manual"))),
        "legacy_priors_declared": int(bool(e.get("modelo_legacy"))),
        "declarados_y_excluidos": list(comp.get("clases_excluidas") or []),
    }


# ── contratos de impresión (§32/§33) ─────────────────────────────────────────
ETIQUETA_CONFIANZA = {est.QUALITY_HIGH: "ALTA", est.QUALITY_MEDIUM: "MEDIA",
                      est.QUALITY_INDICATIVE: "INDICATIVA",
                      est.QUALITY_INSUFFICIENT: "NINGUNA"}
TERMINO_ESTIMACION = {
    est.STATUS_ESTIMATED: "VALOR ESTIMADO",
    est.STATUS_ESTIMATED_WITH_LIMITATIONS: "VALOR ESTIMADO",
    est.STATUS_INDICATIVE_ESTIMATE: "ESTIMACIÓN INDICATIVA",
    est.STATUS_NOT_ESTIMABLE: "ESTIMACIÓN NO DISPONIBLE",
}
SIN_EVIDENCIA = "Sin evidencia de mercado suficiente"
NOTA_ESTIMACION_FIJA = ("Estimación automatizada de DICTUS basada en la información "
                        "disponible para esta corrida. No constituye un avalúo comercial "
                        "certificado cuando este sea legal o contractualmente requerido.")
METODOLOGIA_IMPRESA = ("Metodología: fuentes disponibles + análisis técnico automatizado + "
                       "metodología versionada · detalle completo en el informe técnico.")


def pesos(valor: Any) -> Optional[str]:
    """Formato monetario del ejecutivo («$ 352.500.000»). NUNCA inventa un cero."""
    try:
        return f"$ {int(round(float(valor))):,}".replace(",", ".")
    except (TypeError, ValueError):
        return None


def confianza_de(resultado: Dict[str, Any]) -> str:
    """Confianza DERIVADA del nivel de calidad de la evidencia (§13/§14)."""
    nivel = ((resultado or {}).get("evidence_quality") or {}).get("level")
    return ETIQUETA_CONFIANZA.get(nivel, "NINGUNA")


def etiqueta_de(resultado: Dict[str, Any]) -> str:
    return TERMINO_ESTIMACION.get((resultado or {}).get("status"),
                                  "ESTIMACIÓN NO DISPONIBLE")


def rango_de(resultado: Dict[str, Any]) -> Optional[str]:
    """«Rango: $ X – $ Y» sólo si el motor produjo rango. Si no, None (no se rellena)."""
    low, high = (resultado or {}).get("range_low"), (resultado or {}).get("range_high")
    if low is None or high is None:
        return None
    return f"Rango: {pesos(low)} – {pesos(high)}"


def _fuentes_nombradas(resultado: Dict[str, Any], limite: int = 2) -> List[str]:
    nombres: List[str] = []
    for s in ((resultado or {}).get("sources") or []):
        nombre = s.get("proveedor") or s.get("source_id")
        if nombre and str(nombre) not in nombres:
            nombres.append(str(nombre))
    return nombres[:limite]


def _fuentes_ids(resultado: Dict[str, Any], limite: int = 3) -> List[str]:
    """Identificadores cortos de las fuentes citadas (para la línea de trazabilidad)."""
    ids: List[str] = []
    for s in ((resultado or {}).get("sources") or []):
        nombre = s.get("source_id") or s.get("referencia") or s.get("proveedor")
        if nombre and str(nombre) not in ids:
            ids.append(str(nombre))
    return ids[:limite]


def visibilidad_central(resultado: Dict[str, Any]) -> Dict[str, Any]:
    """Política de visibilidad de la referencia central, ya evaluada por el motor (§5.4).

    Si el resultado no la trae (entradas antiguas o resultado construido a mano), se
    declara el estado conservador `HIDDEN` CON su motivo: nunca se asume `VISIBLE`.
    """
    v = (resultado or {}).get("central_reference_visibility")
    if isinstance(v, dict) and v.get("state"):
        return v
    return {"policy_version": est.CENTRAL_REFERENCE_VISIBILITY_VERSION,
            "state": est.VISIBILIDAD_OCULTA,
            "imprime_la_cifra": False, "calibrada_empiricamente": False,
            "reasons": ["el resultado no declara la política de visibilidad de la "
                        "referencia central: se publica como HIDDEN (conservador)"],
            "reason_short": ("el resultado no declara la política de visibilidad de la "
                             "referencia central"),
            "umbrales_aplicados": dict(est.UMBRALES_VISIBILIDAD_CENTRAL),
            "fundamento": est.FUNDAMENTO_VISIBILIDAD_CENTRAL, "entradas": {}}


def central_imprimible(resultado: Dict[str, Any]) -> bool:
    """¿La política permite imprimir la cifra central?"""
    return bool(visibilidad_central(resultado).get("imprime_la_cifra"))


def texto_referencia_central(resultado: Dict[str, Any], *, prefijo: str = "",
                             sufijo: str = "", detalle: bool = True) -> str:
    """Texto de la REFERENCIA CENTRAL según la política de visibilidad.

    `VISIBLE` → la cifra; `DEEMPHASIZED` → la cifra, rotulada como SECUNDARIA y (con
    `detalle=True`) con el motivo corto de la política; `HIDDEN` → NO se imprime cifra:
    se declara que no se publica y por qué. (Devolver la cifra «por si acaso» sería
    desobedecer la política.) `detalle=False` se usa donde el hueco es estrecho (la
    rejilla de cuatro campos de la P6) y el motivo ya viaja en LIMITACIONES.
    """
    r = resultado or {}
    v = visibilidad_central(r)
    estado = v.get("state")
    valor = pesos(r.get("central_estimate"))
    if estado == est.VISIBILIDAD_OCULTA or not r.get("central_estimate"):
        return (f"{prefijo}no publicada{sufijo} · "
                + str(v.get("reason_short") or "política de visibilidad"))
    if estado == est.VISIBILIDAD_DEENFATIZADA:
        # El rótulo es CORTO a propósito: la P1 es una tira de tres líneas de ancho fijo y
        # el detalle de la política viaja en `reasons` y en la P6/JSON. Dejarlo largo
        # empujaba «Confianza: …» fuera de la línea (el lector perdía el dato).
        cola = f" · {v.get('reason_short')}" if detalle else ""
        return f"{prefijo}{valor} (secundaria{sufijo}{cola})"
    return f"{prefijo}{valor}{sufijo}"


def contrato_p1(resultado: Dict[str, Any]) -> Dict[str, Any]:
    """Lo que la PÁGINA 1 imprime del contrato de estimación (§32).

    Tres ramas explícitas: `VALOR ESTIMADO` (con cifra, rango y confianza),
    `ESTIMACIÓN INDICATIVA` (rango y confianza indicativa) y `ESTIMACIÓN NO DISPONIBLE`
    (con el literal «Sin evidencia de mercado suficiente»). Nunca se imprime un monto
    que el motor no haya producido, y la REFERENCIA CENTRAL sólo se imprime si la
    POLÍTICA DE VISIBILIDAD lo permite (§5.4): si no, se declara que no se publica.
    """
    r = resultado or {}
    status = r.get("status")
    etiqueta = etiqueta_de(r)
    confianza = confianza_de(r)
    central = r.get("central_estimate") if central_imprimible(r) else None
    rango = rango_de(r)
    vis = visibilidad_central(r)
    fila1 = f"ESTIMACIÓN ECONÓMICA DICTUS · {etiqueta}"
    if status in (est.STATUS_ESTIMATED, est.STATUS_ESTIMATED_WITH_LIMITATIONS) and central \
            and vis.get("state") == est.VISIBILIDAD_VISIBLE:
        fila1 += f" · {pesos(central)}"
    if status == est.STATUS_INDICATIVE_ESTIMATE:
        fila2 = (f"{rango or 'Rango: no disponible'} · "
                 f"Referencia central: {texto_referencia_central(r)} · "
                 f"Confianza: {confianza}")
        fila3 = (f"Base: {r.get('status_label') or ''} · "
                 f"ESTIMATION_GATE = {gate_de_estimacion(r)} · evidencia utilizada: "
                 f"{', '.join(_fuentes_nombradas(r)) or 'ninguna fuente de mercado'}")
    elif status == est.STATUS_NOT_ESTIMABLE:
        fila2 = (f"{SIN_EVIDENCIA} · Rango: no disponible · "
                 f"Referencia central: no disponible · Confianza: {confianza}")
        faltan = ((r.get("gap_report") or {}).get("falta") or [])
        traducido = {"comparables": "comparables de mercado",
                     "estadisticas": "estadística agregada oficial de valor/m²",
                     "modelo_calibrado": "modelo calibrado con muestra declarada",
                     "costos": "costos de construcción con vigencia",
                     "rentas": "referencias de arriendo"}
        fila3 = ("Falta: " + " · ".join(traducido.get(f, f) for f in faltan)
                 if faltan else "Falta: soporte económico de mercado")
    else:
        fila2 = (f"{rango or 'Rango: no disponible'} · "
                 f"Valor/m²: {pesos(r.get('value_m2_central')) or 'no disponible'} / m² · "
                 f"Confianza: {confianza}")
        fila3 = ("Método: " + (", ".join(r.get("methods_used_ids") or [])
                               or "sin método aplicable"))
    return {"etiqueta": etiqueta, "status": status, "confianza": confianza,
            "central": central, "rango": rango,
            "central_reference_visibility": vis,
            "linea_1": fila1, "linea_2": fila2, "linea_3": fila3,
            "sin_evidencia": SIN_EVIDENCIA}


def gate_de_estimacion(resultado: Dict[str, Any]) -> str:
    """Estado de `ESTIMATION_GATE` tal como lo declara el motor (§9)."""
    return str(((resultado or {}).get("estimation_gate") or {}).get("gate_state")
               or est.ESTIMATION_CLOSED)


def gate_de_evidencia_verificada(resultado: Dict[str, Any]) -> str:
    """Estado de `VERIFIED_MARKET_EVIDENCE_GATE` (§30).

    Es una compuerta DISTINTA de `ESTIMATION_GATE`: `CLOSED` aquí NO cierra la
    estimación. Confundirlas es exactamente lo que producía la contradicción de la P6.
    """
    return str(((resultado or {}).get("verified_market_evidence_gate") or {})
               .get("gate_state") or est.VERIFIED_CLOSED)


def razon_evidencia_verificada_no_habilitada() -> str:
    """Razón impresa cuando la valoración con evidencia fuerte no está disponible."""
    return ("no existen comparables individualizados suficientes para atribuir un valor "
            "verificado a esta unidad")


def contrato_p6(resultado: Dict[str, Any], *,
                cosecha: Optional[Dict[str, Any]] = None,
                consulta: Optional[str] = None) -> Dict[str, Any]:
    """Los ocho campos obligatorios del bloque `ESTIMACIÓN ECONÓMICA` (§33).

    Añade, además, los DOS hechos que impiden la lectura contradictoria (§7/§8):
    `ESTIMATION_GATE` (¿hay información para estimar?) y
    `VERIFIED_MARKET_EVIDENCE_GATE` (¿la evidencia acredita esta unidad?). Y la
    REFERENCIA CENTRAL respeta la política de visibilidad (§5.4).
    """
    r = resultado or {}
    status = r.get("status")
    usa_cifra = status in (est.STATUS_ESTIMATED, est.STATUS_ESTIMATED_WITH_LIMITATIONS,
                           est.STATUS_INDICATIVE_ESTIMATE)
    metodos = [m.get("method_name") or m.get("method_id")
               for m in (r.get("methods_used") or [])]
    # §33 · el MÉTODO impreso dice QUÉ se usó y CON QUÉ: la referencia agregada oficial
    # va con su fuente y su rango oficial, no como una etiqueta suelta.
    _m5 = next((m for m in (r.get("methods_used") or [])
                if m.get("method_id") == est.METODO_M5), None)
    if _m5:
        _banda = _m5.get("banda_oficial") or {}
        metodos = [
            f"{est.NOMBRE_METODO[est.METODO_M5]} · {_banda.get('source_id')} · "
            f"banda oficial {pesos(_banda.get('min'))}–{pesos(_banda.get('max'))} COP/m²"]
    fuentes = _fuentes_nombradas(r, limite=3)
    limitaciones = list(r.get("limitations") or [])
    gaps = ((r.get("gap_report") or {}).get("fuentes_automaticas_a_incorporar") or [])
    if status == est.STATUS_NOT_ESTIMABLE and gaps:
        limitaciones = ["Sin soporte económico de mercado: " + "; ".join(
            str(g.get("fuente")) for g in gaps[:3])] + limitaciones
    # La limitación impresa es la PRIMERA que el lector necesita: si la base es agregada,
    # esa manda (el rango no es un valor de esta unidad); si no, manda la que declara el
    # insumo excluido (un parámetro a mano que no sostiene nada).
    def _prioridad(t: str) -> int:
        bajo = str(t).lower()
        if "agregada" in bajo or "no acredita la unidad" in bajo:
            return 0
        if "no usado como fuente" in bajo or "manual_config" in bajo:
            return 1
        return 2
    limitaciones = sorted(limitaciones, key=_prioridad)
    vis = visibilidad_central(r)
    return {
        "estado": gate_de_estimacion(r),
        "estimation_gate": gate_de_estimacion(r),
        "verified_market_evidence_gate": gate_de_evidencia_verificada(r),
        "razon_verified_market_evidence_gate": razon_evidencia_verificada_no_habilitada(),
        "central_reference_visibility": vis,
        "etiqueta": etiqueta_de(r),
        # ¿el bloque lleva cifra? Es lo que decide el chip del panel: sin esto, un estado de
        # compuerta «OPEN_WITH_LIMITATIONS» se leería como «NO DISPONIBLE» al lado de un
        # rango impreso.
        "habilitado": bool(usa_cifra),
        "RANGO ESTIMADO": (rango_de(r).replace("Rango: ", "") if usa_cifra and rango_de(r)
                           else "no disponible"),
        # §5.4 · la REFERENCIA CENTRAL sólo se imprime si la política lo permite:
        # `HIDDEN` no publica cifra (y lo declara con su motivo).
        "REFERENCIA CENTRAL": (texto_referencia_central(r, detalle=False) if usa_cifra
                               and r.get("central_estimate") else "no disponible"),
        "VALOR/M²": ((pesos(r.get("value_m2_central")) or "no disponible") + " / m²"
                     if usa_cifra else "no disponible"),
        "CONFIANZA": confianza_de(r),
        "MÉTODO": (", ".join([str(m) for m in metodos if m]) or
                   "ninguno aplicable: no hay insumo económico que sostenga un método"),
        "EVIDENCIA UTILIZADA": (f"{len(fuentes)} fuente(s) con procedencia completa: "
                                + "; ".join(fuentes)) if fuentes else
        ("ninguna: la corrida no aporta comparables, estadística agregada ni modelo "
         "calibrado"),
        "LIMITACIONES": (" ".join(limitaciones[:1]) if limitaciones else
                         "sin limitaciones declaradas"),
        "TRAZABILIDAD": (f"TRAZABILIDAD · Fuentes: "
                         f"{', '.join(_fuentes_ids(r)) or 'ninguna fuente de mercado'} · "
                         f"Consulta: {consulta or 'no declarada'} · "
                         f"motor {r.get('model_version')}"),
        "NOTA": NOTA_ESTIMACION_FIJA,
        "METODOLOGIA": METODOLOGIA_IMPRESA,
        "cosecha": dict(cosecha or {}),
        "status": status, "confianza": confianza_de(r),
    }

# -*- coding: utf-8 -*-
"""BLOCK 1 · VERDAD ÚNICA POR ATRIBUTO — escalera de resolución + propagación de hechos.

PROBLEMA QUE CIERRA
-------------------
`api/source_resolution.py` implementa y prueba 20 escalones de resolución por atributo,
pero su SALIDA no entraba al `DictusRunState`: medido, el Golden tenía **0** tokens de
`source_selected`, `source_attempts`, `source_authority`, `acquisition_mode`,
`fact_status`, `conflict_class` y de cualquier `source_id` del pack (`POT_BAQ_*`). La
procedencia que sí se persistía era texto libre (`observations[].source`) y, por eso,
ningún consumidor podía decidir con ella.

ESTE MÓDULO
-----------
Resuelve, PARA CADA ATRIBUTO AUDITADO, la escalera REAL del Source Pack
(`api/acquisition.resolver_con_acquisition_mode`, que orquesta `source_resolution` y
resuelve desde el snapshot declarado cuando la consulta en vivo no aportó dato) y
persiste el mínimo auditable por atributo:

    source_attempts · source_selected · source_authority · source_vigency ·
    acquisition_mode · resolution_status · fact_status · canonical_value ·
    canonical_reason · evidence_id · content_hash · queried_at

REGLAS DURAS (§10, §17, §18, §19) — ninguna es heurística de render:

  §10 · Una sola verdad por atributo: un atributo tiene UN `canonical_value` y UN
        `canonical_fact_status`. P1, P4, P5 y P6 PROYECTAN esa verdad; no la recrean.
        Un resumen de identidad no puede decir «VERIFIED» mientras un componente de su
        ALCANCE DECLARADO no lo está.
  §17 · Si hubo consulta válida + geometría evaluada + fuente válida + resultado
        espacial, el atributo NO puede quedar `NOT_EVALUATED`.
  §18 · Un atributo no evaluado NO se presenta como riesgo ni como ausencia: recibe su
        estado propio (`NOT_SUPPORTED` / `SOURCE_UNAVAILABLE`) con el motivo exacto.
  §19 · `NO_DATA`/`NOT_SUPPORTED` describen cobertura inexistente; NUNCA se usa
        `NOT_EVALUATED` como cajón general de lo que no se consultó.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:  # importable como `api.attribute_truth` y como módulo plano (patrón de los tests)
    from . import dictus_historia as dh
    from . import dictus_sources as ds
    from . import source_resolution as sr
except ImportError:  # pragma: no cover
    import dictus_historia as dh  # type: ignore[no-redef]
    import dictus_sources as ds  # type: ignore[no-redef]
    import source_resolution as sr  # type: ignore[no-redef]

REGISTRO_VERSION = "dictus-attribute-resolution/1.0.0"
CLAVE_RUN_STATE = "attribute_resolution"

# ── vocabulario de RESOLUCIÓN (el de la escalera + el estado de ausencia declarada) ──
RESOLVED_PRIMARY = sr.RESOLVED_PRIMARY
RESOLVED_FALLBACK = sr.RESOLVED_FALLBACK
# `RESOLVED_SNAPSHOT`: la escalera resuelve con una fuente cuyo dato llega de un
# `acquisition_snapshot` DECLARADO (capa empaquetada / registro autorizado) porque la
# consulta en vivo no aportó dato. Es un modo de adquisición, no un estado nuevo de la
# escalera (que conserva sus 5 estados probados): por eso se deriva aquí.
RESOLVED_SNAPSHOT = "RESOLVED_SNAPSHOT"
UNRESOLVED = sr.UNRESOLVED
AMBIGUOUS = sr.AMBIGUOUS
SOURCE_UNAVAILABLE = sr.SOURCE_UNAVAILABLE
NOT_SUPPORTED = ds.NO_SOPORTADA            # "NOT_SUPPORTED"
ESTADOS_RESOLUCION = (RESOLVED_PRIMARY, RESOLVED_FALLBACK, RESOLVED_SNAPSHOT,
                      UNRESOLVED, AMBIGUOUS, SOURCE_UNAVAILABLE, NOT_SUPPORTED)

# ── vocabulario de HECHO (`fact_status`) ─────────────────────────────────────
VERIFIED = "VERIFIED"
KNOWN_BUT_UNVERIFIED = "KNOWN_BUT_UNVERIFIED"
CONFLICT = "CONFLICT"
NOT_EVALUATED = "NOT_EVALUATED"
NO_DATA = "NO_DATA"
HISTORICAL_ONLY = "HISTORICAL_ONLY"
ESTADOS_HECHO = (VERIFIED, KNOWN_BUT_UNVERIFIED, CONFLICT, NOT_EVALUATED, NO_DATA,
                 HISTORICAL_ONLY, SOURCE_UNAVAILABLE, NOT_SUPPORTED)

# Modos de adquisición que significan «el dato viene de un artefacto EMPAQUETADO».
MODOS_EMPAQUETADOS = frozenset({
    "PACKAGED_REFERENCE", "PACKAGED_GEOJSON", "PACKAGED_REGISTRY", "AUTOMATED_SNAPSHOT",
    "AUTOMATED_SNAPSHOT_ARTIFACT", "AUTHORIZED_FALLBACK", "RAW_CAPTURE", "PACKAGED",
})

# ── ATRIBUTOS AUDITADOS (§9) ─────────────────────────────────────────────────
# `escalon`: atributo de la escalera del Source Pack que lo resuelve (None = no existe
# escalón: la cobertura es inexistente y se declara, nunca se confunde con NO_MATCH).
# `ruta`: dónde vive el valor en el `DictusRunState`.
# `campo`: clave en `market_context.urban_source_summary.campos` que declara el MODO con
# que la corrida obtuvo ese valor (LIVE_OFFICIAL / PACKAGED_REFERENCE / ...).
# `impreso`: dónde lo imprime el ejecutivo (para la matriz de propagación).
ATRIBUTOS: Dict[str, Dict[str, Any]] = {
    "fmi": {"escalon": "identidad_nupre", "ruta": ("property_identity", "folio"),
            "impreso": "P6", "dominio": "IDENTIDAD", "evidencia": "EV-IDENTIDAD"},
    "matricula": {"escalon": "identidad_nupre", "ruta": ("property_identity", "folio"),
                  "impreso": "P6", "dominio": "IDENTIDAD", "evidencia": "EV-IDENTIDAD"},
    "nupre": {"escalon": "identidad_nupre", "ruta": ("property_identity", "nupre"),
              "impreso": "P6", "dominio": "IDENTIDAD", "evidencia": "EV-IDENTIDAD"},
    "numero_predial": {"escalon": "identidad_nupre",
                       "ruta": ("property_identity", "codigo_catastral"),
                       "impreso": "P6", "dominio": "IDENTIDAD", "evidencia": "EV-IDENTIDAD"},
    "direccion": {"escalon": "direccion_predio",
                  "ruta": ("property_identity", "direccion_normalizada"),
                  "rutas": [("property_identity", "direccion_normalizada"),
                            ("property_identity", "direccion_raw")],
                  "impreso": "P1/P6", "dominio": "IDENTIDAD", "evidencia": "EV-IDENTIDAD"},
    "unidad": {"escalon": None, "ruta": ("property_identity", "unidad"),
               "impreso": "P6", "dominio": "IDENTIDAD", "evidencia": "EV-IDENTIDAD",
               "fuente_citada": ("resolución canónica de identidad de la corrida "
                                 "(torre/apartamento de la nomenclatura oficial) + CTL")},
    "regimen_juridico": {"escalon": None,
                         "ruta": ("urban_context", "condicion_juridica"),
                         "impreso": "P6", "dominio": "IDENTIDAD",
                         "evidencia": "EV-IDENTIDAD",
                         "fuente_citada": ("CTL adjunto (SNR) + clasificación del régimen de "
                                           "la corrida")},
    "property_type": {"escalon": None, "ruta": ("urban_context", "tipo_unidad"),
                      "impreso": "P1", "dominio": "IDENTIDAD",
                      "evidencia": "EV-IDENTIDAD",
                      "fuente_citada": "tipo de predio declarado por el CTL (SNR)"},
    # `area` NO se adopta como verificada: el valor llega como dato de ENTRADA del caso
    # (el CTL analizado) y ninguna evidencia sellada de la corrida lo sustenta. El pack
    # declara el registro catastral del PREDIO, no el área de la UNIDAD privada: se declara
    # la cobertura que falta (nunca `NO_MATCH` ni una adopción silenciosa).
    "area": {"escalon": None, "ruta": ("urban_context", "area"), "impreso": "P1/P6",
             "dominio": "IDENTIDAD", "evidencia": "EV-IDENTIDAD",
             "fuente_citada": "entrada del caso (área del CTL)",
             "solo_entrada_del_caso": True},
    "barrio": {"escalon": "barrio", "ruta": ("urban_context", "barrio"), "campo": "barrio",
               "impreso": "P1/P4/P5", "dominio": "URBANO", "evidencia": "EV-URBANO"},
    "localidad": {"escalon": "localidad", "ruta": ("urban_context", "localidad"),
                  "campo": "localidad", "impreso": "P4/P5", "dominio": "URBANO",
                  "evidencia": "EV-URBANO"},
    "estrato": {"escalon": "estrato", "ruta": ("urban_context", "estrato"),
                "campo": "estrato", "impreso": "P4", "dominio": "URBANO",
                "evidencia": "EV-URBANO"},
    "destino_economico": {"escalon": "destino_catastral",
                          "ruta": ("urban_context", "destino_economico"),
                          "impreso": "P1/P4/P6", "dominio": "URBANO",
                          "evidencia": "EV-URBANO",
                          # El propio modelo de decisión declara de dónde sale este campo
                          # («Destino económico (catastro)» → «catastro en vivo»). Es una
                          # declaración medida de la corrida, no una inferencia.
                          "declaracion_literal": ("catastro en vivo",
                                                  "declarado por el modelo de decisión para "
                                                  "este campo: catastro en vivo")},
    "uso_pot": {"escalon": "uso_pot", "ruta": ("market_context", "uso", "value"),
                "campo": "uso", "impreso": "P4", "dominio": "URBANO",
                "evidencia": "EV-URBANO"},
    "tratamiento": {"escalon": "tratamiento", "ruta": ("urban_context", "tratamiento"),
                    "campo": "tratamiento", "impreso": "P4", "dominio": "URBANO",
                    "evidencia": "EV-URBANO"},
    "altura_normativa": {"escalon": "edificabilidad_altura_normativa",
                         "ruta": ("urban_context", "altura_maxima"),
                         "campo": "altura_maxima", "impreso": "P4", "dominio": "URBANO",
                         "evidencia": "EV-URBANO"},
    "edificabilidad": {"escalon": "edificabilidad_altura_normativa",
                       "ruta": ("urban_context", "altura_maxima"), "impreso": "ANEXO",
                       "dominio": "URBANO", "evidencia": "EV-URBANO",
                       "alias_de": "altura_normativa"},
    "clase_suelo": {"escalon": None, "ruta": ("urban_context", "clase_suelo"),
                    "impreso": "P4", "dominio": "URBANO", "evidencia": "EV-URBANO",
                    "historico_si_sin_fuente": True,
                    "fuente_citada": ("clase de suelo declarada por versiones anteriores del "
                                      "expediente (no se adopta como vigente)")},
    "coordenada": {"escalon": None, "ruta": ("market_context", "coordinates"),
                   "impreso": "P4/P5", "dominio": "GEOMETRIA", "evidencia": "EV-GEOMETRIA"},
    "binding_geometria": {"escalon": None, "especial": "binding_geometria",
                          "impreso": "P6", "dominio": "GEOMETRIA",
                          "evidencia": "EV-GEOMETRIA"},
    "remocion": {"escalon": "remocion", "ruta": ("risk_context", "amenaza_remocion_masa"),
                 "campo": "amenaza_remocion_masa", "impreso": "P4", "dominio": "RIESGO",
                 "evidencia": "V-AMENAZAS", "espacial": True},
    "riesgo": {"escalon": "riesgo", "ruta": ("risk_context", "areas_en_riesgo"),
               "campo": "areas_en_riesgo", "impreso": "P4", "dominio": "RIESGO",
               "evidencia": "V-AMENAZAS", "espacial": True},
    "inundacion": {"escalon": "inundacion", "ruta": ("risk_context", "inundacion"),
                   "campo": "inundacion", "impreso": "P4", "dominio": "RIESGO",
                   "evidencia": "V-AMENAZAS", "espacial": True},
    "riesgo_no_mitigable": {"escalon": None,
                            "ruta": ("risk_context", "riesgo_no_mitigable"),
                            "campo": "riesgo_no_mitigable", "impreso": "P4",
                            "dominio": "RIESGO", "evidencia": "V-AMENAZAS",
                            "espacial": True},
}
# El identificador real de la evidencia de amenazas (el guion se normaliza abajo).
for _spec in ATRIBUTOS.values():
    if _spec.get("evidencia") == "V-AMENAZAS":
        _spec["evidencia"] = "EV-AMENAZAS"

# ── NOMBRES DEL MISMO ATRIBUTO EN CADA CAPA ──────────────────────────────────
# El informe de coherencia histórica nombra los atributos con su clave histórica y las
# páginas los imprimen con la suya. El registro es la ÚNICA verdad: estos alias permiten
# leer el mismo hecho desde cada capa sin crear una segunda verdad.
ALIAS_HISTORICO = {          # clave del registro → clave del informe histórico
    "altura_normativa": "altura_maxima",
    "edificabilidad": "altura_maxima",
    "remocion": "amenaza",
    "riesgo": "riesgo",
    "direccion": "direccion",
}
ALIAS_PAGINA = {             # clave de la página → clave del registro
    "altura_maxima": "altura_normativa",
    "amenaza": "remocion",
    "areas_en_riesgo": "riesgo",
    "coordenada": "coordenada",
    "matricula": "matricula",
    "tipologia": "tipologia",
}

# La FUENTE que la corrida declara con este literal para los campos urbanos que obtuvo
# **en vivo** de la capa oficial del municipio (medido en el RunState del Golden:
# `urban_render_provenance.authority = OfficialUrbanContext`, prefijo `official_`).
FUENTE_LIVE_OFICIAL = "official_urban_layer"

# ── FUENTE DEL PACK QUE CORRESPONDE A CADA ATRIBUTO DECLARADO POR LA CORRIDA ──
# La corrida declara QUÉ obtuvo y con qué MODO; el pack declara QUÉ capa sirve ese
# atributo. Este cuadro empareja las dos declaraciones: sin él, la escalera podría
# resolver por una fuente que la corrida NO usó (y eso sería atribuir un valor a una
# fuente ajena: fabricar procedencia).
FUENTE_DECLARADA = {
    "identidad_nupre": ("CATASTRO_BAQ_PREDIO",
                        "catastro municipal (CATASTRO_MUNICIPAL_BARRANQUILLA_ARCGIS, "
                        "capa del predio) declarado por la corrida como origen de la "
                        "identidad canónica"),
    "direccion_predio": ("CATASTRO_BAQ_DIRECCION",
                         "capa 105 · direccion del catastro municipal, declarada por la "
                         "corrida como procedencia de la nomenclatura y del punto"),
    "barrio": ("POT_BAQ_BARRIOS", "capa oficial de barrios del municipio (LIVE_OFFICIAL)"),
    "localidad": ("POT_BAQ_LOCALIDADES", "campo `localidad` de la capa oficial (LIVE_OFFICIAL)"),
    "estrato": ("POT_BAQ_ESTRATIFICACION",
                "estratificación oficial del municipio (LIVE_OFFICIAL)"),
    "tratamiento": ("POT_BAQ_TRATAMIENTO", "capa POT de tratamientos (LIVE_OFFICIAL)"),
    "edificabilidad_altura_normativa": (
        "POT_BAQ_EDIFICABILIDAD", "capa POT empaquetada de edificabilidad (PACKAGED_REFERENCE)"),
    "remocion": ("POT_BAQ_REMOCION_2024",
                 "capa POT empaquetada de amenaza por remoción (PACKAGED_REFERENCE)"),
    "riesgo": ("POT_BAQ_RIESGO_2024",
               "capa POT empaquetada de áreas en riesgo (PACKAGED_REFERENCE)"),
    "destino_catastral": ("CATASTRO_BAQ_DESTINO_ECONOMICO",
                          "destino económico catastral declarado por la corrida"),
}

# Campo del escalón al que corresponde el valor declarado (para que la escalera resuelva
# con SU campo y no con el payload entero).
CAMPO_EN_ESCALON = {
    "fmi": "fmi", "matricula": "fmi", "nupre": "nupre",
    "numero_predial": "numero_predial_nacional", "direccion": "direccion",
    "barrio": "barrio", "localidad": "localidad", "estrato": "estrato",
    "tratamiento": "tratamiento", "destino_economico": "destino_economico",
    "altura_normativa": "altura_max", "edificabilidad": "altura_max",
    "remocion": "amenaza", "riesgo": "riesgo", "inundacion": "amenaza",
}

# Motivo declarado por el pack para una fuente DESHABILITADA (contrato de fallo §27:
# «capa inexistente o fuente deshabilitada → NOT_SUPPORTED»).
MOTIVO_DESHABILITADA = ("La fuente está declarada `enabled=false` en el registro vigente "
                        "del Source Pack: no es NO_MATCH ni una ausencia del predio — la "
                        "capa no se pudo verificar en la ventana de medición (ver `notes` "
                        "de la fuente).")


# ══════════════════════════════════════════════════════════════════════════════
# utilidades de lectura del estado (nunca calculan: LEEN lo declarado)
# ══════════════════════════════════════════════════════════════════════════════
def dato(valor: Any) -> bool:
    """¿Es un DATO utilizable? (None/""/centinelas NO lo son; el cero SÍ.)"""
    return sr.valor_utilizable(valor)


def _ruta(estado: Dict[str, Any], camino: Sequence[str]) -> Any:
    actual: Any = estado
    for clave in camino:
        if not isinstance(actual, dict):
            return None
        actual = actual.get(clave)
    return actual


def _valor(rs: Dict[str, Any], spec: Dict[str, Any]) -> Any:
    """Valor declarado del atributo: la PRIMERA de sus rutas declaradas que traiga dato.

    Varios atributos tienen más de una ruta legítima en el estado (p. ej. la dirección se
    declara normalizada o cruda): se leen en el orden declarado y nunca se inventa una.
    """
    for camino in (spec.get("rutas") or [spec.get("ruta") or ()]):
        valor = _ruta(rs, camino)
        if valor is not None and valor != "":
            return valor
    return None


def _campo_urbano(rs: Dict[str, Any], campo: Optional[str]) -> Dict[str, Any]:
    campos = (((rs.get("market_context") or {}).get("urban_source_summary") or {})
              .get("campos") or {})
    bloque = campos.get(str(campo)) or {}
    return bloque if isinstance(bloque, dict) else {}


def _evidencias_selladas(rs: Dict[str, Any]) -> Dict[str, Any]:
    """Evidencias declaradas por la corrida (id → {status, hash}) si viajan al estado."""
    salida: Dict[str, Any] = {}
    modelo = rs.get("modelo") or {}
    for e in ((modelo.get("evidence_manifest") or {}).get("evidencias") or []):
        if isinstance(e, dict) and e.get("evidence_id"):
            salida[str(e["evidence_id"])] = e
    for e in ((rs.get("evidence_manifest") or {}).get("evidencias") or []):
        if isinstance(e, dict) and e.get("evidence_id"):
            salida.setdefault(str(e["evidence_id"]), e)
    return salida


def _identidad_verificada(rs: Dict[str, Any]) -> bool:
    pi = rs.get("property_identity") or {}
    return bool(pi.get("identity_verified")) or str(
        pi.get("resolution_confidence") or "").upper() == "VERIFIED_UNIT_IDENTITY"


def evidencia_declarada(rs: Dict[str, Any], spec: Dict[str, Any]) -> Dict[str, Any]:
    """Evidencia que la corrida DECLARA para el dominio del atributo (no se inventa).

    Es la condición que permite que un hecho resuelto llegue a `VERIFIED`: no basta con
    «hay un valor», tiene que haber una declaración de procedencia verificable en el
    propio artefacto de la corrida.
    """
    dominio = str(spec.get("dominio") or "")
    fuentes: List[str] = []
    if dominio == "IDENTIDAD":
        if _identidad_verificada(rs):
            fuentes = ["EV-IDENTIDAD", "EV-GEOMETRIA"]
    elif dominio == "URBANO":
        uss = (rs.get("market_context") or {}).get("urban_source_summary") or {}
        ouc = (rs.get("market_context") or {}).get("official_urban_context") or {}
        if str(ouc.get("context_status") or "").upper() == "OK" or uss.get("source_mode"):
            fuentes = ["EV-URBANO"]
    elif dominio == "RIESGO":
        geo = rs.get("geometry_state") or {}
        if geo.get("evaluado"):
            fuentes = ["EV-AMENAZAS"]
    elif dominio == "GEOMETRIA":
        mc = rs.get("market_context") or {}
        if mc.get("coordinate_source_verified"):
            fuentes = ["EV-GEOMETRIA"]
    return {"evidence_id": (fuentes[0] if fuentes else spec.get("evidencia")),
            "evidence_ids": fuentes,
            "declarada": bool(fuentes)}


def _evidencia_del_registro(rs: Dict[str, Any], evidencias: Dict[str, Any],
                            spec: Dict[str, Any]) -> Dict[str, Any]:
    """Evidencia declarada + su sello real cuando el manifest viaja en el estado."""
    decl = evidencia_declarada(rs, spec)
    for eid in decl["evidence_ids"]:
        ev = evidencias.get(eid)
        if isinstance(ev, dict):
            decl["evidence_status"] = ev.get("status")
            decl["content_hash"] = ev.get("content_hash")
            break
    return decl


# ══════════════════════════════════════════════════════════════════════════════
# CONSULTAS DECLARADAS POR LA CORRIDA (lo que la corrida SÍ obtuvo de una fuente)
# ══════════════════════════════════════════════════════════════════════════════
def _primer_escalon(atributo: str, registro: Optional[Dict[str, Any]],
                    cobertura: Optional[Dict[str, Any]] = None) -> Optional[str]:
    try:
        escalon = sr.escalon_para_atributo(atributo, registro=registro,
                                           cobertura=cobertura)
    except Exception:  # noqa: BLE001 — el registro ausente es un estado, no un crash
        return None
    return escalon[0]["source_id"] if escalon else None


def consultas_declaradas(rs: Dict[str, Any], *, registro: Optional[Dict[str, Any]] = None,
                         fecha: Optional[str] = None) -> Dict[str, Any]:
    """`SourceResult` de las consultas que ESTA corrida declara haber obtenido.

    No se inventa ninguna consulta: se declara la que el RunState documenta, con su
    MODO (`LIVE_OFFICIAL` / `PACKAGED_REFERENCE`) y su literal de fuente. El valor se
    entrega en el `payload_normalized` que la escalera sabe leer, con los campos
    declarados por la cobertura del pack. Todo lo demás NO se declara: la escalera lo
    verá como «sin consulta» y lo dirá con ese motivo (nunca como NO_MATCH).
    """
    import acquisition as acq  # local: mantiene ligero el import del estado

    # LAS CONSULTAS VAN POR ATRIBUTO (`{atributo: {source_id: SourceResult}}`). Una fuente
    # puede servir a varios atributos con CAMPOS distintos: si se compartiera un único
    # resultado por fuente, un atributo leería el payload de otro (la escalera cae al
    # payload completo cuando ningún campo declarado casa) y se declararían discrepancias
    # entre valores que ninguna fuente comparó.
    consultas: Dict[str, Dict[str, Dict[str, Any]]] = {}
    modos: Dict[str, Dict[str, Any]] = {}
    _registro = registro if registro is not None else acq._registro(registro)
    _fuentes_pack = (_registro.get("sources") or {})

    def _declarar(atributo: str, escalon: str, valor: Any, modo: str,
                  fuente_txt: Any) -> None:
        """Declara la consulta de la corrida en la fuente del pack que le corresponde."""
        pareja = FUENTE_DECLARADA.get(escalon)
        campo = CAMPO_EN_ESCALON.get(atributo)
        if not pareja or not campo:
            modos[atributo] = {"declarado_por": "SIN_FUENTE_DEL_PACK",
                               "motivo": ("la corrida declara el valor, pero el Source Pack "
                                          "no declara la fuente de este atributo: no se "
                                          "atribuye a ninguna capa")}
            return
        sid, justificacion = pareja
        if sid not in _fuentes_pack:
            modos[atributo] = {"declarado_por": "FUENTE_NO_REGISTRADA",
                               "motivo": (f"la fuente declarada para el atributo ({sid}) no "
                                          f"está en el registro vigente del pack")}
            return
        consultas.setdefault(atributo, {})[sid] = ds.resultado(
            sid, ds.DISPONIBLE, queried_at=str(rs.get("generated_at") or ""),
            payload_normalized={campo: valor, "value": valor},
            detail=(f"La corrida declara este campo obtenido de {sid} (" + modo + "): "
                    + justificacion + "."))
        modos[atributo] = {"declarado_por": "CORRIDA", "modo": modo, "source_id": sid,
                           "campo": campo, "fuente": fuente_txt,
                           "justificacion": justificacion}

    for atributo, spec in ATRIBUTOS.items():
        escalon = spec.get("escalon")
        if not escalon or spec.get("solo_entrada_del_caso"):
            # El valor existe en el estado, pero NO lo aportó ninguna fuente del pack: no
            # se declara consulta (y la escalera no lo resolverá con un dato de entrada).
            if spec.get("solo_entrada_del_caso"):
                modos[atributo] = {"declarado_por": "ENTRADA_DEL_CASO",
                                   "motivo": ("el valor proviene de la entrada del caso y no "
                                              "de una fuente consultada")}
            continue
        valor = _valor(rs, spec)
        campo = spec.get("campo")
        bloque = _campo_urbano(rs, campo) if campo else {}
        modo = str(bloque.get("modo") or "").upper()
        fuente_txt = bloque.get("fuente")
        if not dato(valor):
            continue
        if modo == "LIVE_OFFICIAL" or str(fuente_txt or "") == FUENTE_LIVE_OFICIAL:
            _declarar(atributo, escalon, valor, "LIVE_OFFICIAL", fuente_txt)
        elif modo in MODOS_EMPAQUETADOS:
            _declarar(atributo, escalon, valor, modo, fuente_txt)
        elif spec.get("declaracion_literal"):
            # La corrida declara el origen de este campo con una etiqueta literal propia
            # (p. ej. «catastro en vivo» para el destino económico catastral).
            etiqueta, justificacion = spec["declaracion_literal"]
            _declarar(atributo, escalon, valor, "LIVE_OFFICIAL", etiqueta)
            modos[atributo]["justificacion"] = justificacion
    # Identidad canónica: la corrida declara la resolución de la identidad del predio
    # contra el catastro municipal (EV-GEOMETRIA sellada) y contra el registro de
    # identidad del expediente (EV-IDENTIDAD sellada). Se declara solo si la corrida lo
    # declara como VERIFICADO, con el método que ella misma nombra.
    pi = rs.get("property_identity") or {}
    if _identidad_verificada(rs) and dato(pi.get("folio")):
        pareja = FUENTE_DECLARADA.get("identidad_nupre")
        sid = pareja[0] if pareja else None
        if sid and sid in _fuentes_pack:
            campos = {"nupre": pi.get("nupre"), "numero_predial": pi.get("codigo_catastral"),
                      "numero_predial_nacional": pi.get("codigo_catastral"),
                      "codigo_homologado": pi.get("nupre"), "fmi": pi.get("folio")}
            for attr in ("fmi", "matricula", "nupre", "numero_predial"):
                campo = CAMPO_EN_ESCALON.get(attr)
                if not campo:
                    continue
                consultas.setdefault(attr, {})[sid] = ds.resultado(
                    sid, ds.DISPONIBLE, queried_at=str(rs.get("generated_at") or ""),
                    payload_normalized={campo: campos.get(campo), "value": campos.get(campo)},
                    detail=("El registro catastral municipal resolvió la identidad del predio "
                            f"({pi.get('resolution_method') or 'método declarado'}) y la "
                            "corrida la declaró VERIFICADA con su evidencia sellada."))
                modos.setdefault(attr, {"declarado_por": "CORRIDA",
                                        "modo": "LIVE_OFFICIAL", "source_id": sid,
                                        "campo": campo,
                                        "fuente": pi.get("resolution_method")})
    direccion = _valor(rs, ATRIBUTOS["direccion"])
    if dato(direccion):
        pareja = FUENTE_DECLARADA.get("direccion_predio")
        sid = pareja[0] if pareja else None
        if sid and sid in _fuentes_pack:
            consultas.setdefault("direccion", {})[sid] = ds.resultado(
                sid, ds.DISPONIBLE, queried_at=str(rs.get("generated_at") or ""),
                payload_normalized={"direccion": direccion, "value": direccion},
                detail="Nomenclatura declarada por la corrida para el predio.")
            modos.setdefault("direccion", {"declarado_por": "CORRIDA",
                                           "modo": "LIVE_OFFICIAL", "source_id": sid,
                                           "campo": "direccion"})
    return {"consultas": consultas, "modos": modos}


# ══════════════════════════════════════════════════════════════════════════════
# RESOLUCIÓN POR ATRIBUTO
# ══════════════════════════════════════════════════════════════════════════════
def _estado_resolucion(resultado: Dict[str, Any], modo_declarado: str,
                       hubo_snapshot: bool) -> str:
    """Estado de RESOLUCIÓN del atributo (vocabulario de `ESTADOS_RESOLUCION`)."""
    estado = str(resultado.get("resolution_status") or UNRESOLVED)
    if estado not in (RESOLVED_PRIMARY, RESOLVED_FALLBACK):
        return estado if estado in ESTADOS_RESOLUCION else UNRESOLVED
    # El valor viene de un artefacto EMPAQUETADO declarado (o la escalera resolvió desde
    # el snapshot de la fuente porque la consulta en vivo no aportó dato): eso ES
    # `RESOLVED_SNAPSHOT`, y se declara como tal en vez de llamarlo «primary».
    if hubo_snapshot or str(modo_declarado or "").upper() in MODOS_EMPAQUETADOS:
        return RESOLVED_SNAPSHOT
    return estado


def _fuente_declarada(resultado: Dict[str, Any]) -> Dict[str, Any]:
    """Registro del pack de la fuente SELECCIONADA (autoridad y vigencia declaradas)."""
    prov = resultado.get("provenance") or {}
    return {
        "source_id": prov.get("escalon_source_id") or resultado.get("selected_source"),
        "source_name": prov.get("source_name"),
        "institution": prov.get("institution"),
        "authority_class": prov.get("authority_class"),
        "layer_id": prov.get("layer_id"),
        "layer_name": prov.get("layer_name"),
        "version_or_vigency": prov.get("version_or_vigency"),
        "precedence": prov.get("precedence"),
        "escalon_step": prov.get("escalon_step"),
    }


def _acquisition_de(resultado: Dict[str, Any]) -> Dict[str, Any]:
    acq = resultado.get("acquisition") or {}
    seleccionado = acq.get("seleccionado") or {}
    return seleccionado if isinstance(seleccionado, dict) else {}


def fact_status_de(resultado: Dict[str, Any], *, valor: Any, espacial: bool,
                   source_authority: Optional[str], source_vigency: Optional[str],
                   tiene_evidencia: bool, modo_declarado: str,
                   geometria_evaluada: bool) -> str:
    """Estado del HECHO, con las reglas §10/§17/§18/§19 declaradas una sola vez."""
    estado = str(resultado.get("resolution_status") or UNRESOLVED)
    if estado == AMBIGUOUS or resultado.get("conflict"):
        return CONFLICT
    if estado in (RESOLVED_PRIMARY, RESOLVED_FALLBACK, RESOLVED_SNAPSHOT):
        if str(source_vigency or "").upper() == ds.HISTORICAL_REFERENCE:
            return HISTORICAL_ONLY
        oficial = str(source_authority or "").upper() in (
            ds.AUTORITATIVA_OFICIAL, ds.AUTORITATIVA_CONTRACTUAL)
        vigente = str(source_vigency or "").upper() in (ds.CURRENT_NORMATIVE,
                                                        ds.CURRENT_OFFICIAL)
        if oficial and vigente and (tiene_evidencia or str(modo_declarado or "").upper()
                                    in MODOS_EMPAQUETADOS):
            return VERIFIED
        return KNOWN_BUT_UNVERIFIED
    if estado == UNRESOLVED:
        return NO_DATA if not dato(valor) else KNOWN_BUT_UNVERIFIED
    if estado == NOT_SUPPORTED:
        # §19: cobertura inexistente declarada. NUNCA `NOT_EVALUATED` como cajón.
        return NOT_SUPPORTED
    # §17: consulta válida + geometría evaluada + fuente válida + resultado espacial ⇒
    # no puede quedar NOT_EVALUATED.
    if espacial and geometria_evaluada and dato(valor):
        return VERIFIED
    return SOURCE_UNAVAILABLE


def _intento_declarado(intento: Dict[str, Any],
                       registro: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Intento de fuente con la semántica que el REGISTRO declara para su estado.

    El escalón conserva su marcador `NOT_RUN` («no se ejecutó consulta»), que describe lo
    que el motor hizo. Pero el registro del pack declara, para una fuente deshabilitada, su
    propia semántica de fallo (`failure_semantics`: «capa inexistente o fuente
    deshabilitada → NOT_SUPPORTED»): la verdad por atributo NO puede quedarse con «no se
    ejecutó consulta» cuando la causa declarada es que la cobertura no está soportada.
    Se declara el estado del contrato, con su motivo, y se conserva el marcador original.
    """
    salida = {
        "source_id": intento.get("source_id"), "status": intento.get("status"),
        "value": intento.get("value"), "rejected_reason": intento.get("rejected_reason"),
        "ladder_role": intento.get("ladder_role"),
        "authority_class": intento.get("authority_class"),
        "vigencia": intento.get("vigencia"), "escalon_step": intento.get("escalon_step"),
    }
    sid = str(intento.get("source_id") or "")
    fuente = ((registro or {}).get("sources") or {}).get(sid) or {}
    if fuente.get("enabled") is False:
        salida["ladder_status"] = intento.get("status")
        salida["status"] = ds.NO_SOPORTADA
        salida["declarado_por"] = "REGISTRO_DEL_PACK (failure_semantics)"
        salida["rejected_reason"] = (
            "La fuente está declarada `enabled=false` en el registro vigente del Source "
            "Pack: la cobertura de este atributo NO está soportada en esta ventana. El "
            "contrato del propio registro declara esa semántica («capa inexistente o fuente "
            "deshabilitada → NOT_SUPPORTED») y NO es un NO_MATCH ni una ausencia del predio."
            + (f" {intento.get('rejected_reason')}" if intento.get("rejected_reason") else ""))
    return salida


def resolver_atributos(rs: Dict[str, Any], *, registro: Optional[Dict[str, Any]] = None,
                       fecha: Optional[str] = None,
                       historial: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Resuelve y PERSISTE la verdad por atributo de ESTA corrida.

    Devuelve `{"registry_version", "generated_at", "attributes": {…}, "summary": {…}}`.
    Cada ficha declara, como mínimo: `canonical_value`, `resolution_status`,
    `fact_status`, `source_attempts`, `source_selected`, `source_authority`,
    `source_vigency`, `acquisition_mode`, `canonical_reason`, `evidence_id`,
    `content_hash` y `queried_at` (estos tres últimos cuando existen).
    """
    import acquisition as acq  # local

    rs = rs or {}
    _reg = registro if registro is not None else acq._registro(registro)
    declarado = consultas_declaradas(rs, registro=_reg, fecha=fecha)
    consultas = declarado["consultas"]
    modos = declarado["modos"]
    geo = rs.get("geometry_state") or rs.get("geo_eval") or {}
    geometria_evaluada = bool(geo.get("evaluado"))
    riesgos = rs.get("risk_context") or {}
    evidencias = _evidencias_selladas(rs)
    historial = historial or rs.get("historical_consistency") or {}
    clasificaciones = historial.get("clasificaciones_conflicto") or {}

    fichas: Dict[str, Dict[str, Any]] = {}
    for atributo, spec in ATRIBUTOS.items():
        if spec.get("alias_de"):
            # El atributo comparte ESCALÓN y VALOR con otro (p. ej. `edificabilidad` y
            # `altura_normativa`): se copia la MISMA ficha al final para que no existan dos
            # verdades del mismo hecho con estados distintos.
            continue
        valor = _valor(rs, spec)
        ficha: Dict[str, Any] = {
            "attribute": atributo,
            "domain": spec.get("dominio"),
            "printed_at": spec.get("impreso"),
            "ladder_attribute": spec.get("escalon"),
            "canonical_value": valor,
            "canonical_reason": "",
            "resolution_status": UNRESOLVED,
            "fact_status": NO_DATA,
            "declared_status": _status_declarado(rs, atributo),
            "source_selected": None,
            "source_attempts": [],
            "source_authority": None,
            "source_vigency": None,
            "acquisition_mode": None,
            "evidence_id": spec.get("evidencia"),
            "content_hash": None,
            "queried_at": None,
            "declared_mode": (modos.get(atributo) or {}).get("modo"),
            "geometry_evaluated": geometria_evaluada if spec.get("espacial") else None,
        }
        if spec.get("especial") == "binding_geometria":
            binding = binding_geometria(rs.get("market_context") or {})
            ficha.update({
                "canonical_value": binding["etiqueta"],
                "resolution_status": binding["resolution_status"],
                "fact_status": binding["fact_status"],
                "canonical_reason": binding["detalle"],
                "binding": binding,
                "source_selected": (rs.get("market_context") or {}).get("coordinate_source"),
                "source_authority": "AUTHORITATIVE_OFFICIAL",
                "source_vigency": None,
                "geometry_evaluated": geometria_evaluada,
            })
            fichas[atributo] = ficha
            continue
        escalon = spec.get("escalon")
        if not escalon:
            # §19 — cobertura INEXISTENTE: se declara como tal (nunca NO_MATCH, nunca
            # `NOT_EVALUATED` como cajón general). Si la corrida cita una fuente que no
            # forma parte del Source Pack, se nombra: el lector sabe QUÉ falta.
            ficha["resolution_status"] = NOT_SUPPORTED
            ficha["source_selected"] = None
            citada = spec.get("fuente_citada")
            ficha["fuente_citada"] = citada
            if not dato(valor):
                ficha["fact_status"] = (HISTORICAL_ONLY if spec.get("historico_si_sin_fuente")
                                        else NOT_SUPPORTED)
                ficha["canonical_value"] = None
            elif spec.get("historico_si_sin_fuente"):
                # Solo hay valor en versiones anteriores del expediente: es HISTÓRICO, no
                # presente. No se asciende a hecho actual.
                ficha["fact_status"] = HISTORICAL_ONLY
            else:
                ficha["fact_status"] = KNOWN_BUT_UNVERIFIED
            ficha["canonical_reason"] = (
                "El Source Pack NO declara escalón de resolución para este atributo "
                "(`COBERTURA_ATRIBUTOS`): la cobertura es INEXISTENTE para él. "
                + (f"La corrida cita como fuente: {citada}. " if citada else "")
                + "No es NO_MATCH (no hubo consulta que contestara), no es un conflicto y NO "
                  "se declara `NOT_EVALUATED` como cajón general: se declara la cobertura "
                  "que falta y, si el valor existe, queda como hecho CONOCIDO y NO "
                  "VERIFICADO (el valor nunca se borra).")
            ficha["source_attempts"] = []
            if spec.get("historico_si_sin_fuente") and dato(valor):
                ficha["historical_values"] = list(
                    ((historial.get("clasificaciones_conflicto") or {}).get(
                        ALIAS_HISTORICO.get(atributo, atributo)) or {}).get("pares") or [])
            fichas[atributo] = ficha
            continue
        resultado = acq.resolver_con_acquisition_mode(
            escalon, consultas=(consultas.get(atributo) or {}), registro=_reg,
            fecha=fecha,
            # `inventario=[]`: la escalera NO resuelve por snapshots que la corrida no haya
            # declarado. Un snapshot sólo entra si la corrida declara ese modo (ver
            # `consultas_declaradas`); si no, atribuir el valor a un artefacto que la
            # corrida no usó sería fabricar procedencia.
            inventario=[],
            contexto={"lat": _ruta(rs, ("market_context", "coordinates", "lat")),
                      "lon": _ruta(rs, ("market_context", "coordinates", "lon")),
                      "fecha": str(rs.get("generated_at") or "")[:10]})
        acq_sel = _acquisition_de(resultado)
        fuente = _fuente_declarada(resultado)
        modo = (modos.get(atributo) or {}).get("modo") or ""
        ficha["resolution_status"] = _estado_resolucion(
            resultado, modo, bool(acq_sel.get("snapshot")))
        ficha["source_selected"] = resultado.get("selected_source")
        ficha["source_authority"] = (acq_sel.get("provenance") or {}).get(
            "original_authority_class") or acq_sel.get("authority_class") \
            or fuente.get("authority_class")
        ficha["source_vigency"] = (fuente.get("precedence")
                                   or fuente.get("version_or_vigency"))
        ficha["acquisition_mode"] = acq_sel.get("acquisition_mode") or modo or None
        ficha["source_attempts"] = [
            _intento_declarado(i, _reg) for i in (resultado.get("attempts") or [])]
        ficha["canonical_reason"] = resultado.get("reason") or ""
        ficha["source_detail"] = fuente
        ficha["semantics"] = resultado.get("semantics")
        ficha["annex_reference"] = resultado.get("annex_reference")
        ficha["content_hash"] = (acq_sel.get("content_hash")
                                 or (resultado.get("provenance") or {}).get("content_hash"))
        ficha["queried_at"] = (acq_sel.get("source_queried_at")
                               or str(rs.get("generated_at") or "") or None)
        ficha["conflict"] = resultado.get("conflict")
        if resultado.get("selected_source") and not ficha["canonical_value"]:
            ficha["canonical_value"] = resultado.get("value")
        ev = _evidencia_del_registro(rs, evidencias, spec)
        ficha["evidence_id"] = ev.get("evidence_id")
        ficha["evidence_ids"] = ev.get("evidence_ids") or []
        ficha["evidence_declarada"] = bool(ev.get("declarada"))
        if ev.get("evidence_status"):
            ficha["evidence_status"] = ev["evidence_status"]
        if ev.get("content_hash"):
            ficha["evidence_content_hash"] = ev["content_hash"]
        tiene_evidencia = bool(
            ev.get("declarada")
            or str(ev.get("evidence_status") or "").upper() == "SELLADA"
            or ficha["content_hash"])
        ficha["fact_status"] = fact_status_de(
            resultado, valor=valor, espacial=bool(spec.get("espacial")),
            source_authority=ficha["source_authority"],
            source_vigency=ficha["source_vigency"],
            tiene_evidencia=bool(tiene_evidencia),
            modo_declarado=modo, geometria_evaluada=geometria_evaluada)
        if spec.get("espacial"):
            # §17 — veredicto espacial declarado por la corrida (nivel + relación con el
            # polígono): si existe, el atributo NO puede quedar `NOT_EVALUATED`.
            ficha["spatial_result"] = _ruta(rs, spec.get("ruta") or ())
            ficha["spatial_result_available"] = dato(ficha["spatial_result"])
            if ficha["spatial_result_available"] and geometria_evaluada \
                    and ficha["fact_status"] == NOT_EVALUATED:
                raise AssertionError(
                    f"§17 violado en `{atributo}`: hay resultado espacial y geometría "
                    f"evaluada, y el hecho quedó NOT_EVALUATED")
        # La clasificación histórica se aplica en el POST-PASE (uniforme para todas las
        # fichas, incluidas las que no tienen escalón).
        fichas[atributo] = ficha

    # Post-pase: los atributos que son ALIAS de otro comparten su verdad exacta (una sola
    # verdad por hecho, proyectada en dos nombres: la clave del escalón y la de la página).
    for atributo, spec in ATRIBUTOS.items():
        origen_alias = spec.get("alias_de")
        if not origen_alias:
            continue
        base = fichas.get(str(origen_alias))
        if not isinstance(base, dict):
            continue
        fichas[atributo] = {**base, "attribute": atributo, "alias_de": str(origen_alias),
                            "printed_at": spec.get("impreso")}

    # Post-pase §10: el informe histórico de la corrida es un INSUMO de la verdad única,
    # no una segunda verdad. Se aplica sobre TODAS las fichas (incluidas las que no tienen
    # escalón):
    #   (a) un `TRUE_CONFLICT` convierte el hecho en `CONFLICT` — ningún atributo con
    #       conflicto abierto se imprime verificado;
    #   (b) una DIFERENCIA MATERIAL explicada (precedencia, cambio de fuente, cascada,
    #       semántica, normalización) impide imprimir el hecho como `VERIFIED`, aunque la
    #       fuente actual esté resuelta: la diferencia entre versiones del MISMO inmueble
    #       está abierta y se declara.
    # Una APARICIÓN del atributo en una versión nueva (o una ausencia) NO es una diferencia
    # de valores: no fabrica un estado degradado — se declara como nota de cobertura en su
    # atributo, y el hecho sigue la verdad de su fuente.
    for atributo, ficha in fichas.items():
        clas = clasificaciones.get(ALIAS_HISTORICO.get(atributo, atributo))
        if not clas:
            continue
        veredicto = clas.get("veredicto")
        ficha["historical_conflict"] = {
            "veredicto": veredicto,
            "condicion_que_decide": clas.get("condicion_que_decide"),
            "motivo": clas.get("motivo"),
        }
        if veredicto == dh.TRUE_CONFLICT and ficha["fact_status"] in (VERIFIED,
                                                                     KNOWN_BUT_UNVERIFIED):
            ficha["fact_status"] = CONFLICT
            ficha["canonical_reason"] = (str(ficha["canonical_reason"] or "") + " " + str(
                clas.get("motivo") or "")).strip()
        elif veredicto and veredicto != dh.NOT_A_CONFLICT:
            ficha["historial_diferencia_material"] = True
            if ficha["fact_status"] == VERIFIED:
                ficha["fact_status"] = KNOWN_BUT_UNVERIFIED
                ficha["canonical_reason"] = (
                    "El expediente declara una DIFERENCIA MATERIAL entre versiones del mismo "
                    f"inmueble ({veredicto}: {clas.get('motivo') or ''}) y la revisión está "
                    "abierta: el valor está resuelto con fuente declarada, pero no se "
                    "imprime como verificado. " + str(ficha["canonical_reason"] or "")).strip()

    resumen = _resumen(fichas)
    return {
        "registry_version": REGISTRO_VERSION,
        "ladder_version": sr.PACK_ETIQUETA,
        "generated_at": rs.get("generated_at"),
        "source": ("resuelto por la escalera del Source Pack "
                   "(`api/acquisition.resolver_con_acquisition_mode`) sobre las consultas "
                   "que ESTA corrida declara; ninguna consulta se inventa"),
        "attributes": fichas,
        "summary": resumen,
    }


# ── RUTA DEL ESTADO DECLARADO POR CAMPO (para no dejar «verificado» sin fuente) ──────
# Dónde declara la corrida el ESTADO del valor de cada atributo. Solo se usa para
# detectar y degradar una declaración de «verificado» SIN fuente seleccionada: nunca
# para fabricar un estado.
STATUS_DECLARADO = {
    "uso_pot": ("market_context", "uso", "status"),
    "destino_economico": ("market_context", "urban_source_summary", "campos",
                          "destino_economico", "status"),
    "barrio": ("market_context", "barrio", "status"),
    "estrato": ("market_context", "estrato", "status"),
    "tratamiento": ("market_context", "official_urban_context", "tratamiento_status"),
    "altura_normativa": ("market_context", "official_urban_context", "altura_status"),
    "edificabilidad": ("market_context", "official_urban_context", "altura_status"),
}


def _status_declarado(rs: Dict[str, Any], atributo: str) -> Optional[str]:
    camino = STATUS_DECLARADO.get(atributo)
    if not camino:
        return None
    valor = _ruta(rs, camino)
    return str(valor) if valor else None


def aplicar_verdad_al_estado(rs: Dict[str, Any],
                             registro: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Aplica la verdad ÚNICA al estado: ningún valor queda «verificado» sin fuente.

    Regla (misión §4): «no puede quedar un valor con estado verificado y `source=null`: o
    se resuelve por la escalera (con `source_selected`) o queda sin estado verificado».
    Cuando la escalera NO seleccionó fuente y el estado declara `VERIFIED_*`, la
    declaración se DEGRADA al estado real de resolución y el valor pasa a
    `declared_value` (deja de ser canónico). La degradación queda registrada con el valor
    que la corrida había declarado: no es un borrado silencioso.

    Devuelve la lista de degradaciones aplicadas.
    """
    degradaciones: List[Dict[str, Any]] = []
    for atributo, ficha in ((registro or {}).get("attributes") or {}).items():
        declarado = ficha.get("declared_status") or _status_declarado(rs, atributo)
        if not declarado or not str(declarado).upper().startswith("VERIFIED"):
            continue
        camino = STATUS_DECLARADO.get(atributo)
        if not camino:
            continue
        if ficha.get("source_selected"):
            continue
        nuevo = str(ficha.get("resolution_status") or UNRESOLVED)
        nodo: Any = rs
        for clave in camino[:-1]:
            if not isinstance(nodo, dict) or clave not in nodo:
                nodo = None
                break
            nodo = nodo[clave]
        if not isinstance(nodo, dict):
            continue
        nodo[camino[-1]] = nuevo
        nodo.setdefault("status_declarado_por_la_corrida", declarado)
        nodo.setdefault("status_motivo", (
            f"El estado declarado era «{declarado}» sin fuente seleccionada por la escalera "
            f"del Source Pack: se degrada a «{nuevo}» y el valor queda como "
            f"`declared_value` (no canónico). {ficha.get('canonical_reason') or ''}").strip())
        if ficha.get("canonical_value") is not None:
            ficha["declared_value"] = ficha["canonical_value"]
            ficha["canonical_value"] = None
        degradaciones.append({
            "attribute": atributo,
            "campo": ".".join(camino),
            "estado_declarado": declarado,
            "estado_aplicado": nuevo,
            "motivo": nodo.get("status_motivo"),
        })
    if degradaciones:
        (registro.setdefault("summary", {}))["estados_declarados_degradados"] = [
            d["attribute"] for d in degradaciones]
    return degradaciones


def _resumen(fichas: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    por_estado: Dict[str, List[str]] = {}
    por_hecho: Dict[str, List[str]] = {}
    for attr, f in fichas.items():
        por_estado.setdefault(str(f["resolution_status"]), []).append(attr)
        por_hecho.setdefault(str(f["fact_status"]), []).append(attr)
    return {
        "total": len(fichas),
        "por_resolution_status": {k: sorted(v) for k, v in sorted(por_estado.items())},
        "por_fact_status": {k: sorted(v) for k, v in sorted(por_hecho.items())},
        "sin_source_selected": sorted(a for a, f in fichas.items()
                                      if not f["source_selected"]),
        "con_evidencia": sorted(a for a, f in fichas.items() if f.get("evidence_id")),
        "not_evaluated": sorted(a for a, f in fichas.items()
                                if f["fact_status"] == NOT_EVALUATED),
    }


# ══════════════════════════════════════════════════════════════════════════════
# PROYECCIÓN DE LA VERDAD ÚNICA HACIA LAS PÁGINAS (P1/P4/P5/P6)
# ══════════════════════════════════════════════════════════════════════════════
_ESTADO_COHERENCIA_POR_HECHO = {
    VERIFIED: dh.VERIFICADO,
    KNOWN_BUT_UNVERIFIED: dh.REQUIERE_VALIDACION,
    CONFLICT: dh.HISTORICAL_CONFLICT,
    NOT_EVALUATED: dh.REQUIERE_VALIDACION,
    NO_DATA: dh.REQUIERE_VALIDACION,
    HISTORICAL_ONLY: dh.REQUIERE_VALIDACION,
    SOURCE_UNAVAILABLE: dh.REQUIERE_VALIDACION,
    NOT_SUPPORTED: dh.REQUIERE_VALIDACION,
}


def estado_de_coherencia(registro: Optional[Dict[str, Any]],
                         atributo: str) -> Optional[str]:
    """Estado de coherencia que la verdad ÚNICA del atributo proyecta en las páginas.

    Acepta tanto la clave del registro como la clave con que la página nombra el mismo
    atributo (`ALIAS_PAGINA`). `None` cuando el atributo no está en el registro (el render
    conserva su criterio por procedencia): así este módulo NUNCA inventa un estado para lo
    que no auditó.
    """
    clave = str(atributo)
    ficha = ((registro or {}).get("attributes") or {}).get(clave)
    if ficha is None:
        clave = ALIAS_PAGINA.get(clave, clave)
        ficha = ((registro or {}).get("attributes") or {}).get(clave)
    if not isinstance(ficha, dict):
        return None
    hecho = str(ficha.get("fact_status") or "")
    if hecho == CONFLICT:
        hist = ficha.get("historical_conflict") or {}
        if hist.get("veredicto") == dh.TRUE_CONFLICT:
            return dh.HISTORICAL_CONFLICT
        return dh.REQUIERE_VALIDACION
    return _ESTADO_COHERENCIA_POR_HECHO.get(hecho, dh.REQUIERE_VALIDACION)


# ── §10 · RESUMEN DE IDENTIDAD vs COMPONENTES ────────────────────────────────
# El resumen «Identidad registral y catastral» NO cubre toda la tabla: cubre los
# componentes de la IDENTIDAD CANÓNICA que la corrida compara y sella (EV-IDENTIDAD +
# EV-GEOMETRIA) — matrícula, NUPRE y número predial. Los demás atributos de la tabla
# (área, régimen, unidad, dirección, tipología, destino) llevan su PROPIO estado por fila.
# La regla deja de ser implícita: si el resumen dice VERIFICADA y algún componente de su
# alcance declarado no lo está, el resumen se DEGRADA. Nunca coexisten un componente
# «unverified» y un resumen «VERIFIED» sin regla explícita declarada.
IDENTIDAD_RESUMEN_ALCANCE = ("matricula", "nupre", "numero_predial")
IDENTIDAD_RESUMEN_REGLA = (
    "El resumen cubre SOLO los componentes de la identidad canónica que la corrida "
    "compara y sella (matrícula, NUPRE y número predial); los demás atributos de la tabla "
    "llevan su propio estado por fila y no se agregan al resumen.")


def resumen_identidad(registro: Optional[Dict[str, Any]],
                      componentes: Optional[Dict[str, str]] = None,
                      *, identity_verified: bool = False) -> Dict[str, Any]:
    """§10 — resumen de identidad derivado de su ALCANCE declarado, no de otra verdad.

    `componentes`: `{atributo: estado_impreso}` de las filas cuyo estado declara el
    render. Si el registro por atributo está disponible, MANDA el registro (una sola
    verdad): el resumen se degrada cuando un componente de su alcance no está verificado.
    """
    estados: Dict[str, str] = {}
    if registro:
        for attr in (registro.get("attributes") or {}):
            est = estado_de_coherencia(registro, attr)
            if est:
                estados[attr] = est
    for attr, est in (componentes or {}).items():
        estados.setdefault(str(attr), str(est))
    del_alcance = {a: estados.get(a) for a in IDENTIDAD_RESUMEN_ALCANCE}
    cumplen = [a for a, e in del_alcance.items() if e == dh.VERIFICADO]
    faltan = [a for a, e in del_alcance.items() if e != dh.VERIFICADO]
    no_verificados = sorted(a for a, e in estados.items()
                            if e != dh.VERIFICADO and a not in IDENTIDAD_RESUMEN_ALCANCE)
    estado = "VERIFICADA" if (not faltan and (identity_verified or cumplen)) \
        else "REQUIERE VALIDACIÓN"
    motivo = ("Matrícula, NUPRE y número predial resueltos y ligados entre sí por la "
              "resolución canónica de la corrida." if estado == "VERIFICADA" else
              ("El resumen NO puede decir VERIFICADA: sus componentes declarados no lo "
               "están (" + ", ".join(f"{a}={del_alcance[a]}" for a in faltan) + ")."))
    return {
        "estado": estado,
        "alcance_declarado": list(IDENTIDAD_RESUMEN_ALCANCE),
        "regla": IDENTIDAD_RESUMEN_REGLA,
        "componentes": estados,
        "componentes_del_alcance": del_alcance,
        "componentes_no_verificados_fuera_del_alcance": no_verificados,
        "motivo": motivo,
        "degradado_por": (None if estado == "VERIFICADA" else faltan),
    }


# ── §11 · BINDING DE GEOMETRÍA ───────────────────────────────────────────────
# Un binding de IDENTIFICADORES (nupre / numero_predial) NO acredita que la GEOMETRÍA sea
# la del predio, y un GEOCODE de dirección NUNCA equivale a geometría oficial del predio.
# Mientras no exista polígono oficial del predio (la capa 100 del catastro de Barranquilla
# se declara `esriGeometryNull`, tabla sin geometría) + comparación geométrica con
# criterio + segunda geometría independiente + relaciones `cr_construccion_guid` /
# `cr_terreno_guid` + geometría de la unidad + CRS declarado, el rótulo NO puede say
# «binding de la geometría oficial: VERIFICADA».
ALCANCE_IDENTIFICADORES = "NATIONAL_IDENTIFIERS"
GEOMETRIA_OFICIAL_PREDIO = "OFFICIAL_PREDIO"
GEOCODE_DIRECCION = "GEOCODE_DIRECCION"
PUNTO_OFICIAL_DE_DIRECCION = "PUNTO_OFICIAL_DE_DIRECCION"
SIN_GEOMETRIA = "SIN_GEOMETRIA"

FUENTES_DE_GEOCODE = ("NOMINATIM", "OSM", "OPENSTREETMAP", "PHOTON", "GEOCODE",
                      "GEOCODIFICAD", "GOOGLE", "MAPBOX")

FALTANTES_PARA_BINDING_GEOMETRICO = (
    "El POLÍGONO oficial del predio: la corrida solo tiene un `Point` y la capa del predio "
    "(`CATASTRO_BAQ_PREDIO`, capa 100) se declara `esriGeometryNull` (tabla de atributos, "
    "sin geometría) en el Source Pack.",
    "Una COMPARACIÓN GEOMÉTRICA con criterio de tolerancia declarado (que la geometría caiga "
    "dentro del predio identificado por `numero_predial`/NUPRE): el binding actual compara "
    "solo CADENAS de identificadores.",
    "Una SEGUNDA geometría INDEPENDIENTE de contraste: hoy hay una sola.",
    "Las relaciones oficiales a construcción y terreno: la capa 105 · direccion declara "
    "`cr_construccion_guid` y `cr_terreno_guid`, y la corrida persiste solo `predio_globalid`.",
    "La geometría de la UNIDAD privada (torre/apartamento), que el pack no declara.",
    "El CRS/EPSG declarado y el crudo de la capa 105: `CATASTRO_BAQ_DIRECCION` no declara "
    "`acquisition_snapshot`.",
    "Verificación independiente del vínculo: hoy `link_verificado` es declaración del "
    "productor.",
    "Una fuente geométrica distinta del punto de dirección (`OFFICIAL_ADOPTION_REGISTRY` no "
    "aporta geometría: `geometry_type` «No aplica»; `OFFICIAL_ADOPTION_ADDRESS_GEOCODE` "
    "aporta un GEOCODE de dirección, que NUNCA equivale a geometría oficial del predio).",
)


def clasificar_procedencia_geometrica(mc: Dict[str, Any]) -> Dict[str, Any]:
    """Categoría REAL de la coordenada adoptada, a partir de lo que el artefacto declara.

    Regla dura: un punto de capa de DIRECCIÓN o un GEOCODE de dirección NO pueden
    clasificarse como `OFFICIAL_PREDIO` (la geometría del predio). `OFFICIAL_PREDIO` solo
    se acepta con geometría de predio/terreno y su relación oficial declarada.
    """
    mc = mc or {}
    prov = mc.get("coordinate_provenance") or {}
    declarado = str(mc.get("coordinate_source") or "").upper()
    sistema = str(prov.get("source_system") or "").upper()
    capa = str(prov.get("layer") or "")
    tipo = str(prov.get("geometry_type") or "").lower()
    metodo = str(prov.get("resolution_method") or "").upper()
    es_geocode = (any(t in sistema or t in metodo for t in FUENTES_DE_GEOCODE)
                  or "GEOCODE" in declarado or "GEOCODIF" in declarado)
    if es_geocode:
        categoria = GEOCODE_DIRECCION
        motivo = ("La coordenada es un GEOCODE de dirección: NO es la geometría oficial del "
                  "predio y no puede clasificarse como `OFFICIAL_PREDIO`.")
    elif "direccion" in capa.lower() or metodo.startswith("DIRECCION"):
        categoria = PUNTO_OFICIAL_DE_DIRECCION
        motivo = (f"La geometría adoptada es un PUNTO de la capa de DIRECCIÓN "
                  f"({capa or 'capa no declarada'}): se ligó al predio por "
                  f"`{prov.get('feature_id_kind') or 'relación no declarada'}` "
                  f"({prov.get('predio_globalid') or 'sin guid'}), no es el polígono del "
                  f"predio.")
    elif tipo.startswith("polygon") and declarado:
        categoria = GEOMETRIA_OFICIAL_PREDIO
        motivo = "La geometría adoptada es un POLÍGONO de la capa oficial del predio."
    elif not prov:
        categoria = SIN_GEOMETRIA
        motivo = "La corrida no declara procedencia de la coordenada."
    else:
        categoria = PUNTO_OFICIAL_DE_DIRECCION
        motivo = (f"La geometría adoptada es un `{prov.get('geometry_type') or 'tipo'}` "
                  f"sin polígono del predio declarado.")
    return {
        "categoria": categoria,
        "declarado_por_la_corrida": mc.get("coordinate_source"),
        "layer": capa or None,
        "geometry_type": prov.get("geometry_type"),
        "resolution_method": prov.get("resolution_method"),
        "motivo": motivo,
        "es_geometria_del_predio": categoria == GEOMETRIA_OFICIAL_PREDIO,
        "es_geocode_de_direccion": categoria == GEOCODE_DIRECCION,
    }


def binding_geometria(mc: Dict[str, Any]) -> Dict[str, Any]:
    """§11 — qué acredita REALMENTE el binding declarado, y qué falta para el geométrico."""
    mc = mc or {}
    procedencia = clasificar_procedencia_geometrica(mc)
    binding = str(mc.get("canonical_binding_status") or "").upper()
    scope = str(mc.get("canonical_binding_scope") or "").upper()
    campos = mc.get("canonical_binding_fields") or []
    geometrico = bool(procedencia["es_geometria_del_predio"]) and binding == "VERIFIED" \
        and scope != ALCANCE_IDENTIFICADORES
    if geometrico:
        etiqueta = "Binding de la geometría oficial del predio"
        estado = "VERIFICADA"
        fact = VERIFIED
        res = RESOLVED_PRIMARY
        detalle = ("El binding se realizó sobre GEOMETRÍA del predio con criterio declarado "
                   f"({scope or 'alcance declarado'}).")
    else:
        etiqueta = ("Binding de la identidad canónica del predio (NO es la geometría "
                    "del predio: el alcance declarado es el de IDENTIFICADORES)")
        estado = "IDENTIFICADORES"
        fact = KNOWN_BUT_UNVERIFIED
        res = UNRESOLVED
        # ORDEN DEL TEXTO: primero lo que el binding REALMENTE acredita y el ALCANCE que la
        # propia fuente declara para la coordenada (es lo que el lector necesita para no
        # atribuir a la geometría una verificación hecha sobre identificadores); después la
        # procedencia y, al final, la lista de lo que FALTA para un binding geométrico
        # `VERIFIED` (que vive completa en el modelo y en el anexo: el render recorta).
        alcance = str(mc.get("coordinate_scope") or "").strip()
        fuente = str(mc.get("coordinate_source") or "").strip()
        # El ALCANCE declarado por la fuente va PRIMERO: es la matización que el lector
        # necesita y la que el render imprime de verdad (el resto del detalle se recorta).
        detalle = (" ".join(filter(None, [
            (alcance[:1].upper() + alcance[1:] + ".") if alcance else "",
            (f"Fuente: {fuente}." if fuente else ""),
        ])) + " ").lstrip()
        detalle = (alcance[:1].upper() + alcance[1:] + "." if alcance else "")
        if fuente:
            detalle = (detalle + f" Fuente: {fuente}.").strip()
        detalle += (
            " El binding acreditado compara "
            + ("solo CADENAS de identificadores "
               f"({', '.join(str(c) for c in campos)})" if campos else "solo identificadores")
            + f"; su alcance declarado es `{scope or 'no declarado'}`. "
              "Un binding de identificadores NO acredita que esta geometría sea la del "
              "predio: por eso NO se rotula como binding de geometría.")
        detalle += f" Geometría adoptada: {procedencia['motivo']}"
        if procedencia["es_geocode_de_direccion"]:
            detalle += (" ATENCIÓN: la procedencia es un GEOCODE de dirección, que NUNCA "
                        "equivale a geometría oficial del predio.")
        detalle += (" Para un binding GEOMÉTRICO `VERIFIED` falta: "
                    + " ".join(f"({i + 1}) {t}"
                               for i, t in enumerate(FALTANTES_PARA_BINDING_GEOMETRICO)))
    return {
        "attribute": "binding_geometria",
        "etiqueta": etiqueta,
        "estado": estado,
        "binding_declarado": binding or "NOT_COMPARABLE",
        "scope": scope or None,
        "fields": list(campos),
        "es_binding_geometrico": geometrico,
        "procedencia": procedencia,
        "faltantes_para_verified_geometrico": list(FALTANTES_PARA_BINDING_GEOMETRICO),
        "resolution_status": res,
        "fact_status": fact,
        "detalle": detalle,
    }


# ══════════════════════════════════════════════════════════════════════════════
# ASERCIONES DE VERDAD ÚNICA (§10/§17/§18/§19) — usadas por los tests y por la corrida
# ══════════════════════════════════════════════════════════════════════════════
def assert_single_truth_per_attribute(registro: Dict[str, Any]) -> None:
    """Un atributo → UN `canonical_value` y UN `canonical_fact_status`."""
    attrs = (registro or {}).get("attributes") or {}
    assert attrs, "el registro por atributo está vacío: no hay verdad que verificar"
    for atributo, f in attrs.items():
        assert "canonical_value" in f, f"{atributo}: sin `canonical_value`"
        assert "fact_status" in f, f"{atributo}: sin `canonical_fact_status`"
        assert f["fact_status"] in ESTADOS_HECHO, \
            f"{atributo}: `fact_status` fuera del vocabulario: {f['fact_status']!r}"
        assert f["resolution_status"] in ESTADOS_RESOLUCION, \
            f"{atributo}: `resolution_status` fuera del vocabulario: {f['resolution_status']!r}"
        # Un valor no puede estar «verificado» sin fuente seleccionada Y sin motivo.
        if f["fact_status"] == VERIFIED:
            assert f.get("source_selected") or f.get("canonical_reason"), \
                (f"{atributo}: VERIFIED sin `source_selected` ni motivo declarado: un hecho "
                 f"verificado tiene que declarar de dónde sale")


def assert_reglas_duras(registro: Dict[str, Any]) -> None:
    """§17/§18/§19 — ninguna de las tres puede violarse en el registro."""
    for atributo, f in ((registro or {}).get("attributes") or {}).items():
        if f.get("spatial_result_available") and f.get("geometry_evaluated"):
            assert f["fact_status"] != NOT_EVALUATED, (
                f"§17 violado en `{atributo}`: hay resultado espacial y geometría evaluada "
                f"y el hecho quedó NOT_EVALUATED")
        if f.get("resolution_status") in (SOURCE_UNAVAILABLE, NOT_SUPPORTED):
            assert f.get("canonical_reason") or f.get("source_attempts"), (
                f"§18/§19 violado en `{atributo}`: ausencia/cobertura declarada sin motivo "
                f"exacto")
            assert f["fact_status"] != NOT_EVALUATED, (
                f"§18/§19 violado en `{atributo}`: la ausencia no se declara NOT_EVALUATED")


def assert_resumen_identidad_cumple(registro: Dict[str, Any],
                                    resumen: Dict[str, Any]) -> None:
    """§10 — el resumen VERIFICADA exige que TODO su alcance declarado esté verificado."""
    if str(resumen.get("estado", "")).startswith("VERIFICADA"):
        for atributo in resumen.get("alcance_declarado") or []:
            est = (resumen.get("componentes_del_alcance") or {}).get(atributo)
            assert est == dh.VERIFICADO, (
                f"§10 violado: el resumen de identidad dice VERIFICADA y el componente "
                f"`{atributo}` de su alcance declarado está {est!r}")


__all__ = [
    "REGISTRO_VERSION", "CLAVE_RUN_STATE", "ATRIBUTOS", "ESTADOS_RESOLUCION",
    "ESTADOS_HECHO", "RESOLVED_SNAPSHOT", "source_attempts_de", "ALIAS_HISTORICO",
    "ALIAS_PAGINA", "STATUS_DECLARADO", "aplicar_verdad_al_estado",
    "consultas_declaradas", "resolver_atributos", "fact_status_de",
    "estado_de_coherencia", "resumen_identidad", "binding_geometria",
    "clasificar_procedencia_geometrica", "IDENTIDAD_RESUMEN_ALCANCE",
    "IDENTIDAD_RESUMEN_REGLA", "assert_single_truth_per_attribute",
    "assert_reglas_duras", "assert_resumen_identidad_cumple",
]


def source_attempts_de(registro: Optional[Dict[str, Any]],
                       atributo: str) -> List[Dict[str, Any]]:
    """Intentos de fuente declarados para un atributo (lista vacía si no hay ficha)."""
    ficha = ((registro or {}).get("attributes") or {}).get(str(atributo)) or {}
    return list(ficha.get("source_attempts") or [])

# -*- coding: utf-8 -*-
"""
ARHIAX RE — Puente Titulux (Confianza Predial)

Traduce el análisis del CTL real (legal_analyzer) y los datos del dictamen al
modelo del prototipo Titulux (`arhia_title`, `arhia_sag_screen`,
`arhia_expediente`) y ejecuta:

  * Pre-dictamen jurídico determinista (reglas TIT_B01..B05 / VAL_B01 / TRX_B01).
  * Screening SAGRILAFT de listas restrictivas EN VIVO (ONU/OFAC descargadas del
    feed oficial, con caché versionada por SHA-256), con degradación honesta:
      - ONU/OFAC son la base vinculante: si su feed no se puede descargar y no
        hay caché, el screening queda INCOMPLETO (nunca se afirma "sin
        coincidencia" contra una lista vacía/sintética).
      - UIAF no tiene feed público limpio: se declara PENDIENTE por canal oficial
        (no se simula su lista vinculante).

Regla de honestidad: Titulux es un PRE-dictamen. La conclusión profesional NO la
emite el sistema; el dictamen la presenta como insumo preliminar separado de la
decisión (autoría separada). Nunca lanza: ante cualquier error devuelve un
resultado honesto con screening PENDIENTE y hallazgos vacíos (NO EVALUADO).
"""

from __future__ import annotations

import datetime
import os
import re
from typing import Any, Dict, Optional, Tuple

# ── Mapeo de tipo de anotación del analizador legal → tipo Titulux ────────────
# Bug J: hipoteca, embargo, MEDIDA CAUTELAR y gravamen genérico son categorías
# DISTINTAS (no se funden en un único 'gravamen').
_TIPO_MAP = {
    "GRAVAMEN: HIPOTECA": "hipoteca",
    "GRAVAMEN: EMBARGO": "embargo",
    "MEDIDA CAUTELAR": "medida_cautelar",
    "GRAVAMEN": "gravamen",
    "LIMITACION: AFECTACION VIVIENDA": "afectacion",
    "LIMITACION: PATRIMONIO FAMILIA": "limitacion",
    "LIMITACION: PATRIMONIO": "limitacion",
    "COMPRAVENTA": "compraventa",
    "CANCELACION": "cancelacion",
    "OTRO: ACLARACION": "aclaracion",
    "ACLARACION": "aclaracion",
}

# Fuentes de screening VIGENTES (03S.1): ids del SourceRegistry de `sanctions`.
# UIAF queda FUERA del screening (es canal de reporte regulatorio, §10/§11).
FUENTES_VINCULANTES_VIVO = ("UN_CONSOLIDATED", "OFAC_SDN", "UK_SANCTIONS_LIST")
FUENTES_POR_FICHERO = ("EU_CONSOLIDATED",)
FUENTES_CANAL_OFICIAL = ()  # legado: UIAF/SIREL ya no es fuente de screening


def _source_ids(fuentes_activas) -> tuple:
    """Traduce claves (legado 'onu'/'ofac'/'uk' o source_id) a source_id vigentes."""
    from sanctions.registry import current_source_id
    out = []
    for f in (fuentes_activas or FUENTES_VINCULANTES_VIVO):
        sid = current_source_id(f)
        if sid and sid not in out:
            out.append(sid)
    return tuple(out)


def _permitir_descarga_default() -> bool:
    """La suite offline fija ARHIAX_SCREENING_OFFLINE=1 y NO debe tocar la red."""
    return (os.environ.get("ARHIAX_SCREENING_OFFLINE") or "").strip().lower() \
        not in ("1", "true", "yes", "si", "sí")


def _tipo_titulux(tipo_legal: str) -> str:
    t = (tipo_legal or "").strip().upper()
    if t in _TIPO_MAP:
        return _TIPO_MAP[t]
    if "HIPOTECA" in t:
        return "hipoteca"
    if "EMBARGO" in t:
        return "embargo"
    if "MEDIDA CAUTELAR" in t or "INSCRIPCION DE DEMANDA" in t \
            or "PROHIBICION" in t or "COMISO" in t or "EXTINCION DE DOMINIO" in t:
        return "medida_cautelar"
    if "SERVIDUMBRE" in t or "USUFRUCTO" in t or "GRAVAMEN" in t:
        return "gravamen"
    if "AFECTACION" in t or "VIVIENDA" in t:
        return "afectacion"
    if "PATRIMONIO" in t:
        return "limitacion"
    if "COMPRAVENTA" in t or "ADQUISICION" in t or "MODO DE ADQUISICION" in t:
        return "compraventa"
    if "CANCELACION" in t:
        return "cancelacion"
    if "ACLARACION" in t or "CORRECCION" in t:
        return "aclaracion"
    return "otro"


def _iso_fecha(fecha: str) -> str:
    """'22-01-2024' -> '2024-01-22'; tolera ya-ISO y fechas con texto."""
    if not fecha:
        return ""
    m = re.search(r"(\d{2})[-/](\d{2})[-/](\d{4})", str(fecha))
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    m2 = re.search(r"(\d{4})[-/](\d{2})[-/](\d{2})", str(fecha))
    if m2:
        return f"{m2.group(1)}-{m2.group(2)}-{m2.group(3)}"
    return str(fecha)


def _nombre_documento(titulares_texto: str) -> Tuple[str, str, str]:
    """Del texto de titulares ('NOMBRE CC# 123') extrae (nombre, tipo_doc, num)."""
    t = (titulares_texto or "").strip()
    t = re.sub(r"\s+\d{1,3}\s*%\s*$", "", t)
    m = re.search(r"(?i)\b(CC|NIT|CE|PASAPORTE|C\.C\.|N\.I\.T\.)\s*#?\s*([\d\.\-]+)", t)
    doc = m.group(1).upper() if m else ""
    num = re.sub(r"[^0-9]", "", m.group(2)) if m else ""
    nombre = re.sub(r"(?i)\b(CC|NIT|CE|PASAPORTE|C\.C\.|N\.I\.T\.)\s*#?\s*[\d\.\-]+", "", t)
    nombre = " ".join(nombre.split()).strip(" .,;")
    tipo_doc = ("nit" if doc in ("NIT", "N.I.T.") else
                ("cc" if doc in ("CC", "C.C.") else (doc.lower() if doc else "")))
    return nombre, tipo_doc, num


def _titular_de_anotacion(texto: str) -> str:
    """Adquirente 'A: ...' de una anotación, sin documentos ni porcentajes."""
    if not texto:
        return ""
    for line in (texto or "").split("\n"):
        ls = line.strip()
        m = re.match(r"A\s*:\s*(.+)", ls, re.IGNORECASE)
        if m:
            nombre = m.group(1).strip()
            nombre = re.sub(r"\s*\d{1,3}\s*%\s*$", "", nombre)
            nombre = re.sub(r"(?i)\b(CC|NIT|CE|C\.C\.|N\.I\.T\.)\s*#?\s*[\d\.\-]+", "", nombre)
            nombre = " ".join(nombre.split()).strip(" .,;")
            if len(nombre) >= 3:
                return nombre
    return ""


def construir_caso_titulux(
    analysis: Dict[str, Any],
    db_record: Dict[str, Any],
    val_data: Dict[str, Any],
    geo_eval: Optional[Dict[str, Any]] = None,
    *,
    area_catastral: float = 0.0,
    identidad: Optional[Dict[str, Any]] = None,
    sarlaft_estado: Optional[str] = None,
) -> Any:
    """Construye el `Caso` de Titulux desde el análisis del CTL real.

    Es un `informe_base` (no una operación de compraventa): VAL_B01 y TRX_B01 no
    aplican (no hay precio pactado ni pagos), coherente con no inventar datos de
    operación que el CTL no aporta.

    `identidad` (modelo canónico canonical_property_identity) es la fuente
    autoritativa de folio/NUPRE/código/titular. Sin ella Titulux derivaba el
    código solo del CTL crudo y, si el CTL no traía código aunque el motor SÍ
    había resuelto el NUPRE por nomenclatura, emitía un TIT_B01 falso de
    "falta folio/código catastral" (bug A).
    """
    from arhia_title.contracts import Anotacion, Avaluo, Caso, Parte, Predio

    identidad = identidad or {}
    folio = (identidad.get("folio_snr")
             or analysis.get("folio")
             or db_record.get("folio_matricula") or "040-XXXXXX")
    # Código canónico: NUPRE > código catastral > anterior > corto > CTL crudo.
    # (03D.1: 'nupre' y 'codigo_catastral' son identificadores distintos; se
    #  conservan separados y ambos sirven como código para Titulux.)
    codigo = (identidad.get("nupre")
              or identidad.get("codigo_catastral")
              or identidad.get("codigo_anterior")
              or identidad.get("codigo_corto")
              or analysis.get("codigo_catastral")
              or analysis.get("nupre")
              or "")
    direccion = analysis.get("direccion") or db_record.get("direccion") or ""
    area_registral = float(db_record.get("area") or 0.0)
    if area_catastral is None:
        area_catastral = float(db_record.get("area_catastral") or 0.0)
    area_catastral = float(area_catastral or 0.0)

    anotaciones = []
    for a in analysis.get("anotaciones_detalle") or []:
        num = str(a.get("num") or "").zfill(3)
        estado_raw = (a.get("estado") or "VIGENTE").upper()
        estado = "cancelada" if "CANCELADA" in estado_raw else "vigente"
        texto = a.get("texto") or ""
        tipo = _tipo_titulux(a.get("tipo") or "")
        titular = _titular_de_anotacion(texto) if tipo == "compraventa" else ""
        detalle = " ".join(texto.split())[:160]
        anotaciones.append(Anotacion(
            numero=int(num), tipo=tipo, fecha=_iso_fecha(a.get("fecha") or ""),
            instrumento=(a.get("partes") or "")[:80], titular=titular,
            detalle=detalle, estado=estado,
        ))

    # Titular: el modelo canónico recupera nombre + DOCUMENTO + tipo de persona
    # desde el CTL (la extracción del analizador pierde el 'CC 87070538' y Titulux
    # clasificaba a la persona natural como 'juridica' sin documento — bug I).
    _titular_can = (identidad.get("titular") or {}) if identidad else {}
    nombre_tit = (_titular_can.get("nombre")
                  or _nombre_documento(analysis.get("titulares") or "")[0])
    tipo_doc = _titular_can.get("tipo_documento")
    num_doc = _titular_can.get("numero_documento")
    if not tipo_doc or not num_doc:
        _nombre_doc = _nombre_documento(analysis.get("titulares") or "")
        tipo_doc = tipo_doc or _nombre_doc[1]
        num_doc = num_doc or _nombre_doc[2]
    partes = []
    if nombre_tit:
        partes.append(Parte("titular", nombre_tit, tipo_doc or "", num_doc or ""))
    hip = analysis.get("hipoteca_vigente") or {}
    acreedor = (hip.get("acreedor") or analysis.get("acreedor_snr") or "").strip()
    if acreedor and len(acreedor) >= 4:
        partes.append(Parte("acreedor", acreedor))

    avaluo = Avaluo(
        float(val_data.get("consolidado") or 0.0) if val_data else 0.0,
        metodo="consolidado ARHIAX (M1·M2·M3)", fecha=datetime.date.today().isoformat(),
        avaluador="ARHIAX referencial (no es avalúo RAA)",
    )

    amenazas = []
    if geo_eval:
        am = geo_eval.get("amenaza_remocion_masa") or {}
        ri = geo_eval.get("areas_en_riesgo") or {}
        if am.get("intersecta") and am.get("nivel"):
            amenazas.append(str(am.get("nivel")))
        if ri.get("intersecta") and ri.get("nivel"):
            amenazas.append(str(ri.get("nivel")))

    return Caso(
        id=f"TIT-{folio}", tipo="informe_base",
        predio=Predio(folio, codigo, direccion,
                      area_registral=area_registral, area_catastral=area_catastral),
        partes=tuple(partes), anotaciones=tuple(anotaciones),
        avaluo=avaluo, titular=nombre_tit or (analysis.get("titulares") or ""),
        amenazas=tuple(amenazas),
        # 03S.1: el estado del screening NO se asume: lo aporta el motor de
        # screening (pendiente por defecto si aún no corrió).
        sarlaft_estado=(sarlaft_estado or "pendiente"),
    )


def _sujetos_del_caso(caso, identidad: Optional[Dict[str, Any]] = None) -> list:
    """Sujetos a screening: titular y acreedor (si existen).

    El tipo ('natural'/'juridica') sale del DOCUMENTO del sujeto, no de un
    default NIT. Un titular sin documento queda 'natural' como sujeto a
    identificar por nombre (nunca se le asigna una calidad jurídica que no
    tiene — bug I: NATURAL_PERSON en SAGRILAFT).
    """
    from arhia_sag_screen.contracts import Contraparte
    identidad = identidad or {}
    _titular_can = identidad.get("titular") or {}
    out = []
    for p in caso.partes:
        doc_t = p.tipo_documento or ""
        if p.rol == "titular":
            tipo_persona = _titular_can.get("tipo_persona")
            doc_t = doc_t or _titular_can.get("tipo_documento") or ""
        else:
            tipo_persona = None
        if tipo_persona == "NATURAL_PERSON":
            tipo = "natural"
        elif tipo_persona == "LEGAL_ENTITY":
            tipo = "juridica"
        elif doc_t in ("cc", "ce", "ti", "rc", "pasaporte"):
            tipo = "natural"
        elif doc_t in ("nit",):
            tipo = "juridica"
        else:
            tipo = "natural"  # sin documento: persona física a identificar por nombre
        out.append(Contraparte(
            f"{p.rol}-{p.numero_documento or p.nombre}",
            tipo,
            p.nombre, doc_t, p.numero_documento,
        ))
    return out


# Severidad ordinal para el agregado de screening (vocabulario LEGADO).
_ORDEN = {"coincidencia": 4, "candidato": 3, "revisionManual": 2,
          "sinCoincidencia": 1, "pendiente": 0}


def _peor(a: str, b: str) -> str:
    return a if _ORDEN.get(a, 0) >= _ORDEN.get(b, 0) else b


# Mapeo estado 03S.1 → vocabulario legado (consumido por expediente/conclusion
# y por los capítulos del dictamen).
_LEGADO_POR_RESULTADO = {
    "EXACT_MATCH": "coincidencia",
    "STRONG_MATCH": "coincidencia",
    "POTENTIAL_MATCH": "candidato",
    "REVIEW_REQUIRED": "revisionManual",
    "NO_MATCH": "sinCoincidencia",
    "SOURCE_UNAVAILABLE": "pendiente",
    "NOT_SCREENED": "pendiente",
}


def _agregado_legado(summary) -> str:
    """Vocabulario legado derivado del estado canónico del screening."""
    peor = "sinCoincidencia"
    for o in summary.outcomes:
        peor = _peor(peor, _LEGADO_POR_RESULTADO.get(o.result, "pendiente"))
    if summary.status in ("SCREENING_PARTIAL", "SCREENING_NOT_EXECUTED"):
        peor = "pendiente"
    return peor


def _screening_legado(summary) -> list:
    """Vista legada por sujeto (compatibilidad de consumidores), derivada del
    resumen único. La autoridad es `screening_summary`."""
    from sanctions.engine import sigla
    # 03I.2 · gates 4 y 5: productor único de tipo y documento del sujeto (compartido
    # con los capítulos 09 y 16).
    from sanctions.subjects import person_type_label, documento_para_dictamen

    out = []
    for e in summary.subjects:
        fuentes = []
        peor = "sinCoincidencia"
        for o in summary.outcomes_de(e.subject_id):
            legado = _LEGADO_POR_RESULTADO.get(o.result, "pendiente")
            peor = _peor(peor, legado)
            fuentes.append({
                "fuente": o.source_id,
                "fuente_sigla": sigla(o.source_id),
                "resultado": legado,
                "resultado_canonico": o.result,
                "estado": o.freshness,
                "version": o.snapshot_sha256[:16],
                "freshness": o.freshness,
                "score": o.score,
                "coincidencia_id": (o.matched_record_ids[0] if o.matched_record_ids else None),
                "motivos": list(o.matching_reasons),
                "snapshot_id": o.snapshot_id,
            })
        out.append({
            "sujeto": e.canonical_name,
            # 03I.2 · gates 4 y 5: MISMO productor que el capítulo 09 y el 16. Antes este
            # capítulo construía su propio tipo («natural»/«juridica») y su propio
            # documento («N/D»), y podía divergir del resto del dictamen.
            "tipo": person_type_label(e).lower(),
            "sujeto_id": e.subject_id, "person_type": e.person_type,
            "documento": documento_para_dictamen(e),
            "roles": list(e.roles), "participacion": e.participation,
            "resultado": peor, "fuentes": fuentes,
            "completo": (summary.status == "SCREENING_COMPLETE"),
        })
    return out


def ejecutar_titulux(
    analysis: Dict[str, Any],
    db_record: Dict[str, Any],
    val_data: Dict[str, Any],
    geo_eval: Optional[Dict[str, Any]] = None,
    *,
    area_catastral: float = 0.0,
    identidad: Optional[Dict[str, Any]] = None,
    fuentes_activas: Tuple[str, ...] = FUENTES_VINCULANTES_VIVO,
    cache_dir: Optional[str] = None,
    timeout_listas: int = 90,
    permitir_descarga: Optional[bool] = None,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """Ejecuta el pre-dictamen Titulux + screening SAGRILAFT sobre el CTL real.

    Devuelve un dict serializable:
      * pre_dictamen: hallazgos (id, titulo, estado, severidad, descripcion,
        base_legal, implicacion, accion, responsable)
      * screening: por sujeto (sujeto, tipo, resultado, fuentes, completo)
      * fuentes_pendientes: fuentes no consultadas en vivo (canal oficial / error)
      * conclusion: veredicto, fundamento, riesgos, observaciones, recomendaciones
      * disponible: False si no se pudo ejecutar (degradación honesta)
    """
    resultado: Dict[str, Any] = {
        "disponible": False, "error": None,
        "pre_dictamen": [], "screening": [],
        "fuentes_pendientes": [], "conclusion": None,
        "screening_completo": False, "coincidencia": False,
    }
    try:
        from arhia_expediente.expediente import FichaIntegridad, construir
        from arhia_expediente.conclusion import concluir
    except Exception as e:  # noqa: BLE001
        resultado["error"] = f"Titulux no disponible: {e}"
        return resultado

    if permitir_descarga is None:
        permitir_descarga = _permitir_descarga_default()

    # 1) Screening de contrapartes (03S.1) — PRIMERO: su resultado determina el
    #    estado SARLAFT del caso y el veredicto, y es la ÚNICA verdad que
    #    consumen los capítulos 05/09/16/16.B y los receipts.
    #    SUJETOS CANÓNICOS → FUENTES OFICIALES → SNAPSHOTS → MATCHING → EVIDENCIA.
    from sanctions.engine import ejecutar_screening, summary_a_dict

    _source_ids_activos = _source_ids(fuentes_activas)
    summary = ejecutar_screening(
        analysis=analysis, identidad=identidad,
        source_ids=_source_ids_activos or FUENTES_VINCULANTES_VIVO,
        cache_dir=cache_dir, timeout=timeout_listas,
        force_refresh=bool(force_refresh),
        permitir_descarga=bool(permitir_descarga),
        ciudad=str(db_record.get("ciudad") or "barranquilla"))
    resultado["screening_summary"] = summary_a_dict(summary)
    _sarlaft_estado = ("verificado" if summary.status == "SCREENING_COMPLETE"
                       else "pendiente")

    try:
        caso = construir_caso_titulux(analysis, db_record, val_data, geo_eval,
                                      area_catastral=area_catastral,
                                      identidad=identidad,
                                      sarlaft_estado=_sarlaft_estado)
    except Exception as e:  # noqa: BLE001
        resultado["error"] = f"No se pudo construir el caso Titulux: {e}"
        return resultado

    sujetos = list(summary.subjects)
    screening_por_sujeto = _screening_legado(summary)
    fuentes_pendientes = set(summary.sources_unavailable)
    _revision = any(o.result in ("POTENTIAL_MATCH", "STRONG_MATCH", "REVIEW_REQUIRED",
                                 "EXACT_MATCH") for o in summary.outcomes)
    coincidencia_total = bool(summary.matched_subjects) or any(
        o.result == "STRONG_MATCH" for o in summary.outcomes)
    screening_completo = summary.cobertura_completa
    agregado = _agregado_legado(summary)

    # 2) Integridad + expediente + conclusión (determinista, autoría separada).
    conclusion = None
    try:
        perfil = "alto" if coincidencia_total else ("medio" if (agregado != "sinCoincidencia") else "bajo")
        screening_ficha = {
            "coincidencia": "coincidencia", "candidato": "revisionManual",
            "revisionManual": "revisionManual", "sinCoincidencia": "ok",
            "pendiente": "pendiente",
        }.get(agregado, "pendiente")
        fuentes_pend = tuple(sorted(fuentes_pendientes))
        integridad = FichaIntegridad(
            screening=screening_ficha,
            # 03S.1 (§28): el dictamen NO determina si una parte es sujeto
            # obligado ni su régimen (decisión jurídica aparte). No se afirma.
            regimen="",
            # Se declara lo que REALMENTE ocurrió: el screening se completó o no.
            sarlaft=("completo" if screening_completo else "incompleto"),
            perfil=perfil,
            screening_completo=screening_completo,
            fuentes_no_disponibles=fuentes_pend,
            screening_por_fuente=tuple(
                {"fuente": x["fuente"], "resultado": x["resultado_canonico"],
                 "listaVersion": x.get("version", ""), "freshness": x.get("freshness", "")}
                for s in screening_por_sujeto for x in s["fuentes"]
            ),
        )
        expediente = construir(caso, integridad)
        conclusion = concluir(expediente, integridad)
        resultado["conclusion"] = {
            "veredicto": conclusion.veredicto,
            "fundamento": conclusion.fundamento,
            "riesgos": list(conclusion.riesgos_prioritarios),
            "observaciones": list(conclusion.observaciones),
            "recomendaciones": list(conclusion.recomendaciones),
            "soporte_compliance": conclusion.soporte_compliance,
        }
        # Pre-dictamen: todos los hallazgos del expediente (títulos + integridad).
        resultado["pre_dictamen"] = [
            {
                "id": h.id, "titulo": h.titulo, "estado": h.estado,
                "severidad": h.severidad, "descripcion": h.descripcion,
                "base_legal": h.base_legal, "implicacion": h.implicacion,
                "accion": h.accion, "responsable": h.responsable,
            }
            for h in expediente.hallazgos
        ]
    except Exception as e:  # noqa: BLE001
        resultado["error"] = (resultado["error"] or "") + f"; conclusión: {e}"

    resultado["screening"] = screening_por_sujeto
    resultado["fuentes_pendientes"] = sorted(fuentes_pendientes)
    resultado["screening_completo"] = screening_completo
    resultado["coincidencia"] = coincidencia_total
    resultado["screening_agregado"] = agregado
    resultado["disponible"] = True
    return resultado


def calentar_cache_listas(fuentes=FUENTES_VINCULANTES_VIVO, cache_dir=None,
                          timeout: int = 45) -> Dict[str, Any]:
    """Descarga las fuentes de screening y las versiona como SNAPSHOTS.

    Pensado para un endpoint administrativo. En Vercel Hobby la función completa
    tiene 60 s, así que la generación del dictamen NO puede gastar ese tiempo
    bajando ~52 MB (ONU/OFAC/UKSL). Ejecutado aparte (una vez al día; el TTL de
    los snapshots es 24 h), el screening del dictamen corre contra los snapshots
    versionados y no consume el presupuesto de la generación.

    Postura honesta (03S.1): cada descarga se guarda como snapshot por
    (source_id, sha256) SIN borrar los anteriores; solo se aceptan fuentes
    OPERATIVA (datos reales). Nunca se cachea una muestra como si fuera oficial.
    """
    from sanctions.acquire import adquirir_fuente
    from sanctions.registry import current_source_id
    from sanctions.snapshots import SnapshotStore

    ids = [sid for sid in (current_source_id(f) for f in (fuentes or
                                                          FUENTES_VINCULANTES_VIVO))
           if sid]
    store = SnapshotStore(cache_dir=cache_dir)
    res: Dict[str, Any] = {
        "fuentes": ids, "descargadas": [], "persistidas": [], "estados": {},
        "detalle": {}, "ok": False, "error": None,
    }
    for sid in ids:
        try:
            snap, regs = adquirir_fuente(sid, store=store, timeout=timeout,
                                         force_refresh=True)
        except Exception as e:  # noqa: BLE001
            res["estados"][sid] = "ERROR"
            res["detalle"][sid] = {"error": f"{type(e).__name__}: {str(e)[:160]}"}
            continue
        res["estados"][sid] = snap.acquisition_status
        res["detalle"][sid] = {
            "acquisition_status": snap.acquisition_status,
            "freshness": snap.freshness, "effective_date": snap.effective_date,
            "record_count": snap.record_count, "sha256": snap.sha256,
            "parser_version": snap.parser_version, "error": snap.error,
        }
        if snap.acquisition_status == "OPERATIVA":
            res["descargadas"].append(sid)
            res["persistidas"].append(sid)
    res["ok"] = bool(res["descargadas"])
    if not res["ok"]:
        res["error"] = ("ninguna fuente quedó OPERATIVA (sin datos reales que "
                        "versionar; se reintentará en la próxima ejecución)")
    return res

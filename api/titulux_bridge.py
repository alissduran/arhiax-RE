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
import re
from typing import Any, Dict, Optional, Tuple

# ── Mapeo de tipo de anotación del analizador legal → tipo Titulux ────────────
_TIPO_MAP = {
    "GRAVAMEN: HIPOTECA": "hipoteca",
    "GRAVAMEN: EMBARGO": "embargo",
    "LIMITACION: AFECTACION VIVIENDA": "afectacion",
    "LIMITACION: PATRIMONIO FAMILIA": "limitacion",
    "LIMITACION: PATRIMONIO": "limitacion",
    "COMPRAVENTA": "compraventa",
    "CANCELACION": "cancelacion",
    "OTRO: ACLARACION": "aclaracion",
    "ACLARACION": "aclaracion",
}

# Fuentes vinculantes que requieren datos reales (OPERATIVA) para contar en el
# screening. onu/ofac/uk se descargan en vivo (feed oficial); ue se ingesta por
# archivo (su portal webgate bloquea la automatización con 403 anti-bot).
FUENTES_VINCULANTES_VIVO = ("onu", "ofac", "uk")
FUENTES_POR_FICHERO = ("ue",)
# Fuentes sin feed público limpio: se reportan como pendientes por canal oficial.
FUENTES_CANAL_OFICIAL = ("uiaf",)


def _tipo_titulux(tipo_legal: str) -> str:
    t = (tipo_legal or "").strip().upper()
    if t in _TIPO_MAP:
        return _TIPO_MAP[t]
    if "HIPOTECA" in t:
        return "hipoteca"
    if "EMBARGO" in t:
        return "embargo"
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
    # Código canónico: NUPRE resuelto > código anterior > código corto > CTL crudo.
    codigo = (identidad.get("nupre")
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
        amenazas=tuple(amenazas), sarlaft_estado="pendiente",
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


# Severidad ordinal para el agregado de screening.
_ORDEN = {"coincidencia": 4, "candidato": 3, "revisionManual": 2,
          "sinCoincidencia": 1, "pendiente": 0}


def _peor(a: str, b: str) -> str:
    return a if _ORDEN.get(a, 0) >= _ORDEN.get(b, 0) else b


def ejecutar_titulux(
    analysis: Dict[str, Any],
    db_record: Dict[str, Any],
    val_data: Dict[str, Any],
    geo_eval: Optional[Dict[str, Any]] = None,
    *,
    area_catastral: float = 0.0,
    identidad: Optional[Dict[str, Any]] = None,
    fuentes_activas: Tuple[str, ...] = ("onu", "ofac", "uiaf", "uk"),
    cache_dir: Optional[str] = None,
    timeout_listas: int = 90,
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
        from arhia_sag_screen.ingest.listas import obtener_listas
        from arhia_sag_screen.match.matcher import consultar
        from arhia_expediente.expediente import FichaIntegridad, construir
        from arhia_expediente.conclusion import concluir
    except Exception as e:  # noqa: BLE001
        resultado["error"] = f"Titulux no disponible: {e}"
        return resultado

    try:
        caso = construir_caso_titulux(analysis, db_record, val_data, geo_eval,
                                      area_catastral=area_catastral,
                                      identidad=identidad)
    except Exception as e:  # noqa: BLE001
        resultado["error"] = f"No se pudo construir el caso Titulux: {e}"
        return resultado

    # 1) Screening SAGRILAFT multifuente. Primero la caché persistente (Neon)
    # para no re-descargar ONU/OFAC/UK (~54 MB) en cada generación; lo que falte
    # se descarga/ingesta en vivo con degradación honesta y se persiste a Neon.
    listas: Dict[str, Any] = {}
    try:
        from listas_cache import leer_todas as _leer_cache_neon
        listas = _leer_cache_neon(list(fuentes_activas))
    except Exception:
        listas = {}

    _faltantes = [f for f in fuentes_activas if f not in listas]
    if _faltantes:
        try:
            _obtenidas = obtener_listas(_faltantes, cache_dir=cache_dir,
                                        timeout=timeout_listas)
            listas.update(_obtenidas)
            # Persistir solo las OPERATIVA (datos reales); nunca muestras.
            _persistir = {f: _obtenidas[f] for f in _obtenidas
                          if getattr(_obtenidas[f][0], "estado", "") == "OPERATIVA"}
            if _persistir:
                try:
                    from listas_cache import escribir_todas as _escribir_cache_neon
                    _escribir_cache_neon(_persistir)
                except Exception:
                    pass
        except Exception as e:  # noqa: BLE001
            resultado["error"] = (resultado["error"] or "") + f"; listas: {e}"

    # Estado por fuente según su política y resultado de descarga.
    estado_fuente: Dict[str, str] = {}
    for f in listas:
        lv = listas[f][0]
        estado = getattr(lv, "estado", "") or ""
        estado_fuente[f] = estado

    sujetos = _sujetos_del_caso(caso, identidad)
    screening_por_sujeto = []
    fuentes_pendientes = set()

    # Fuentes de canal oficial (sin feed público limpio): pendientes, no se simulan.
    for f in FUENTES_CANAL_OFICIAL:
        if f in fuentes_activas:
            fuentes_pendientes.add(f)

    # Fuentes vinculantes (en vivo o por fichero) que no quedaron OPERATIVA:
    # pendientes (no se acepta "sin coincidencia" contra una muestra sintética).
    for f in FUENTES_VINCULANTES_VIVO + FUENTES_POR_FICHERO:
        if f not in fuentes_activas:
            continue
        if estado_fuente.get(f) != "OPERATIVA":
            fuentes_pendientes.add(f)

    # Otras fuentes pedidas (muestra determinista) que no llegaron a OPERATIVA:
    for f in fuentes_activas:
        if f in FUENTES_CANAL_OFICIAL or f in FUENTES_VINCULANTES_VIVO or f in FUENTES_POR_FICHERO:
            continue
        if estado_fuente.get(f) not in ("OPERATIVA", "SYNTHETIC_TEST_FIXTURE"):
            fuentes_pendientes.add(f)

    screening_completo = not fuentes_pendientes
    coincidencia_total = False

    for cp in sujetos:
        res_fuentes = []
        peor = "sinCoincidencia"
        for f in sorted(listas):
            lv, regs = listas[f]
            estado = getattr(lv, "estado", "") or ""
            if estado != "OPERATIVA":
                # Muestra sintética o fuente no vinculante: NO es evidencia de
                # "sin coincidencia"; se reporta aparte.
                res_fuentes.append({
                    "fuente": f, "resultado": "pendiente",
                    "estado": estado, "version": getattr(lv, "version", ""),
                    "nota": "muestra no vinculante / canal oficial requerido",
                })
                continue
            try:
                r = consultar(cp, regs, f, getattr(lv, "version", ""),
                              getattr(lv, "hash", ""))
                res_fuentes.append({
                    "fuente": f, "resultado": r.resultado,
                    "estado": estado, "version": getattr(lv, "version", ""),
                    "score": round(float(r.score), 4),
                    "coincidencia_id": r.coincidencia_id,
                })
                peor = _peor(peor, r.resultado)
            except Exception:  # noqa: BLE001
                res_fuentes.append({
                    "fuente": f, "resultado": "pendiente",
                    "estado": estado, "version": getattr(lv, "version", ""),
                    "nota": "error en la consulta",
                })
                fuentes_pendientes.add(f)
        if peor == "coincidencia":
            coincidencia_total = True
        screening_por_sujeto.append({
            "sujeto": cp.nombre, "tipo": cp.tipo, "resultado": peor,
            "fuentes": res_fuentes,
            "completo": (peor != "pendiente" and not fuentes_pendientes),
        })

    screening_completo = screening_completo and not fuentes_pendientes
    # Agregado del screening (peor entre sujetos).
    agregado = "sinCoincidencia"
    for s in screening_por_sujeto:
        agregado = _peor(agregado, s["resultado"])
    if not screening_completo:
        agregado = "pendiente"

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
            regimen="no_obligado",           # persona natural (titular) + acreedor; sin persona jurídica registrada
            sarlaft="verificado" if screening_completo else "pendiente",
            perfil=perfil,
            screening_completo=screening_completo,
            fuentes_no_disponibles=fuentes_pend,
            screening_por_fuente=tuple(
                {"fuente": x["fuente"], "resultado": x["resultado"],
                 "listaVersion": x.get("version", "")}
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


def calentar_cache_listas(fuentes=("onu", "ofac", "uk"), cache_dir=None,
                          timeout: int = 45) -> Dict[str, Any]:
    """Descarga las listas de screening y las persiste en la caché Neon.

    Pensado para un endpoint administrativo. En Vercel Hobby la función completa
    tiene 60 s, así que la generación del dictamen NO puede gastar ese tiempo
    bajando ~54 MB (ONU/OFAC/UK). Ejecutado aparte (una vez al día; la caché
    dura 24 h), el screening del dictamen corre contra la caché y no consume el
    presupuesto de la generación.

    Postura honesta: solo se persisten listas con estado OPERATIVA (datos
    reales); las muestras/ficheros nunca se cachean como si fueran oficiales.
    """
    res: Dict[str, Any] = {
        "fuentes": list(fuentes), "descargadas": [], "persistidas": [],
        "estados": {}, "ok": False, "error": None,
    }
    from arhia_sag_screen.ingest.listas import obtener_listas as _obtener

    try:
        from listas_cache import leer_todas as _leer
        ya = _leer(list(fuentes)) or {}
    except Exception as e:  # noqa: BLE001
        ya = {}
        res["error"] = f"cache no disponible: {e}"[:300]

    for f in ya:
        res["estados"][f] = "EN CACHE"

    faltantes = [f for f in fuentes if f not in ya]
    if not faltantes:
        res["ok"] = True
        return res

    try:
        obtenidas = _obtener(faltantes, cache_dir=cache_dir, timeout=timeout)
    except Exception as e:  # noqa: BLE001
        res["error"] = f"descarga: {e}"[:300]
        return res

    for f, par in (obtenidas or {}).items():
        try:
            estado = getattr(par[0], "estado", "") or "DESCONOCIDO"
        except Exception:  # noqa: BLE001
            estado = "DESCONOCIDO"
        res["estados"][f] = estado
        if estado == "OPERATIVA":
            res["descargadas"].append(f)

    _persistir = {f: v for f, v in (obtenidas or {}).items()
                  if getattr(v[0], "estado", "") == "OPERATIVA"}
    if _persistir:
        try:
            from listas_cache import escribir_todas as _escribir
            _escribir(_persistir)
            res["persistidas"] = sorted(_persistir.keys())
            res["ok"] = True
        except Exception as e:  # noqa: BLE001
            res["error"] = f"persistencia: {e}"[:300]
    elif not res["error"]:
        res["error"] = ("ninguna fuente quedó OPERATIVA (sin datos reales que cachear; "
                        "se reintentará en la próxima generación)")
    return res

# -*- coding: utf-8 -*-
"""ARHIAX RE — Ficha estructural de contrapartes (screening)

Genera la ficha auditable de los sujetos del caso (titular, acreedor,
constructor/enajenante) con huella de integridad por sujeto.

03S.1 (Sanctions Screening Truth Layer):
  * Los sujetos de la ficha son EXACTAMENTE los mismos `SubjectEnvelope` que se
    screeningan (invariante §5): la ficha no puede decir "3 sujetos" y la tabla
    de screening mostrar 2.
  * El tipo de persona se declara (natural / jurídica / no determinado) y nunca
    se inventa.
  * UIAF NO es una fuente de screening: es canal de REPORTE regulatorio y no se
    imprime como lista ni como resultado.
  * La semántica de los hashes se declara con precisión: sellan artefactos
    (integridad y reproducibilidad), NO certifican que la información de origen
    sea verdadera.

Postura: honesta y auditada. No fingir verificación que no se hace.
"""

import datetime
import hashlib
import re
import unicodedata

# Semántica de hash (§21): qué sella cada hash y qué NO prueba.
SEMANTICA_HASH = (
    "Cada hash SHA-256 sella un ARTEFACTO concreto: el sujeto canónico, el snapshot "
    "de la lista oficial, la consulta y el envelope de evidencia. Prueban integridad "
    "y reproducibilidad (que el artefacto no cambió y que la consulta puede repetirse "
    "contra la misma versión); NO prueban que la información de origen sea verdadera "
    "ni equivalen a una verificación del oficial de cumplimiento."
)

NO_ES_SANCIONES = (
    "UIAF/SIREL no es una lista de screening: es el canal de reporte regulatorio del "
    "sujeto obligado y se atiende por el canal oficial autorizado. No se imprime como "
    "fuente de screening ni se simula su resultado."
)


def _normalizar_nombre(nombre: str) -> str:
    """Normaliza un nombre para hashing consistente:
    - Mayúsculas
    - Sin tildes
    - Sin puntuación
    - Sin espacios dobles
    """
    if not nombre:
        return ""
    nfkd = unicodedata.normalize("NFKD", nombre.upper())
    texto = "".join(c for c in nfkd if not unicodedata.combining(c))
    texto = re.sub(r"[^A-Z0-9\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def _hash_nombre(nombre: str) -> str:
    """Genera SHA-256 truncado (primeros 16 hex) del nombre normalizado."""
    norm = _normalizar_nombre(nombre)
    if not norm:
        return "N/A"
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16].upper()


_PERSONA_TXT = {
    "NATURAL_PERSON": "Natural",
    "LEGAL_ENTITY": "Jurídica",
    "UNKNOWN": "No determinado",
}


def _sujetos_desde_envelopes(subjects):
    """Ficha por sujeto desde los envelopes canónicos (misma fuente que la tabla).

    03I.2A §13: la ficha del capítulo 05 usa el MISMO productor de fila que los
    capítulos 09 y 16 (`sanctions.subjects.fila_sujeto_dictamen`), de modo que nombre,
    tipo, etiqueta, documento y `subject_id` son idénticos en los tres. Antes esta
    ficha escribía su propia etiqueta («Persona jurídica») y su propio documento
    («N/D»), y podía divergir del resto del dictamen (gate #4).
    """
    from sanctions.subjects import fila_sujeto_dictamen  # import local: capa de sanciones
    out = []
    for e in subjects:
        fila = fila_sujeto_dictamen(e)
        out.append({
            "rol": " / ".join(e.roles) or "PARTE",
            "nombre_declarado": fila["canonical_name"],
            "nombre_normalizado": _normalizar_nombre(fila["canonical_name"]),
            "hash_sha256_16": _hash_nombre(fila["canonical_name"]),
            "tipo_persona": fila["person_type"],
            "tipo_persona_txt": fila["person_type_label"],
            "identificacion": fila["document"],
            "subject_id": fila["subject_id"],
            "participacion": e.participation,
            "motivo": e.reason_for_screening,
            "identidad_confianza": e.identity_confidence,
            "advertencias": list(e.identity_warnings),
            "estado_verificacion": ("SCREENINGADO" if e.screened
                                    else "NO SCREENINGADO: "
                                         + (e.not_screened_reason or "sin motivo declarado")),
        })
    return out


def _sujetos_desde_texto(titulares, acreedor_snr, acreedor_real, constructor):
    """Camino LEGADO (sin envelopes): mantiene compatibilidad con llamadas viejas."""
    from sanctions.subjects import build_subject_envelopes
    analysis = {
        "titulares": titulares or "", "acreedor_snr": acreedor_snr,
        "acreedor_real": acreedor_real, "constructor": constructor,
    }
    return _sujetos_desde_envelopes(build_subject_envelopes(analysis, {}))


def generar_ficha_sarlaft(
    titulares: str,
    acreedor_snr: str = None,
    acreedor_real: str = None,
    constructor: str = None,
    folio: str = "N/D",
    *,
    subjects=None,
    screening_status: str = None,
    screening_label: str = None,
    sources=None,
    subjects_declared: int = None,
    subjects_screened: int = None,
    subjects_not_screened: int = None,
) -> dict:
    """Ficha estructural de contrapartes (insumo del screening).

    `subjects` (SubjectEnvelope) es la vía canónica: la ficha y la tabla de
    screening comparten el mismo set. Sin envelopes, se resuelven desde los
    textos del CTL con el mismo parser (compatibilidad).
    """
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    if subjects is not None:
        sujetos = _sujetos_desde_envelopes(subjects)
    else:
        sujetos = _sujetos_desde_texto(titulares, acreedor_snr, acreedor_real, constructor)

    # Hash de la ficha completa (integridad del artefacto "ficha").
    ficha_raw = folio + timestamp + "".join(s["hash_sha256_16"] for s in sujetos)
    hash_ficha = hashlib.sha256(ficha_raw.encode("utf-8")).hexdigest()[:24].upper()

    n = len(sujetos)
    estado_screening = screening_label or "NO EJECUTADO"
    if screening_status and not screening_label:
        estado_screening = screening_status
    return {
        "folio": folio,
        "timestamp_utc": timestamp,
        "total_sujetos": n,
        "sujetos": sujetos,
        "hash_ficha": hash_ficha,
        "screening_status": screening_status,
        "screening_label": estado_screening,
        "subjects_declared": (n if subjects_declared is None else int(subjects_declared)),
        "subjects_screened": subjects_screened,
        "subjects_not_screened": subjects_not_screened,
        "sources": list(sources or ()),
        "estado_global": (
            "SUJETOS IDENTIFICADOS -- resultado de screening: " + estado_screening
            if sujetos else "SIN_SUJETOS_IDENTIFICADOS"),
        "instruccion_oficial_cumplimiento": (
            "Esta ficha es un insumo estructural de carácter automático generado "
            "por el motor ARHIAX. El oficial de cumplimiento DEBE validar el "
            "resultado del screening y las contrapartes en la plataforma autorizada "
            "de su institución antes de tomar cualquier decisión de crédito, "
            "garantía o transferencia."
        ),
        "semantica_hash": SEMANTICA_HASH,
        "no_es_sanciones": NO_ES_SANCIONES,
        "disclaimer": SEMANTICA_HASH + " " + NO_ES_SANCIONES,
    }


def generar_tabla_sarlaft(ficha: dict) -> list:
    """Filas (label, valor) para la tabla PDF de la ficha de contrapartes."""
    n_sujetos = ficha["total_sujetos"]
    _decl = ficha.get("subjects_declared")
    estado_sujetos = "{} sujeto(s) identificado(s)".format(
        n_sujetos if _decl is None else _decl)
    _scr = ficha.get("subjects_screened")
    _noscr = ficha.get("subjects_not_screened")
    _detalle_scr = ""
    if _scr is not None:
        _detalle_scr = " · {} screeningado(s) · {} no screeningado(s)".format(
            _scr, 0 if _noscr is None else _noscr)
    filas = [
        ("Estado del screening de contrapartes",
         "{} — {}{}".format(ficha.get("screening_label") or "NO EJECUTADO",
                            estado_sujetos, _detalle_scr)),
        ("Fuentes consultadas",
         " · ".join(ficha.get("sources") or ()) or "Ninguna (screening no ejecutado)"),
        ("Hash de integridad de la ficha", ficha["hash_ficha"]),
        ("Timestamp de generación (UTC)", ficha["timestamp_utc"]),
    ]
    for s in ficha["sujetos"]:
        _extra = " | Participación: {}".format(s["participacion"]) if s.get("participacion") else ""
        _adv = (" | Advertencias: " + ", ".join(s["advertencias"])) if s.get("advertencias") else ""
        filas.append((
            "{}: {}".format(s["rol"], s["nombre_declarado"]),
            "{} | Documento: {} | Hash: {} | {}{}{}".format(
                s.get("tipo_persona_txt") or "No determinado", s["identificacion"],
                s["hash_sha256_16"], s["estado_verificacion"], _extra, _adv)
        ))
    filas.append(("Semántica de los hashes", ficha.get("semantica_hash") or SEMANTICA_HASH))
    filas.append(("Alcance", ficha.get("no_es_sanciones") or NO_ES_SANCIONES))
    return filas

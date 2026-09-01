# -*- coding: utf-8 -*-
"""
ARHIAX RE — Motor SARLAFT Estructural
Bloque B Sprint 2

Genera una ficha SARLAFT auditada con hashes de integridad para cada
sujeto vinculado al activo (titulares, acreedor, constructor).

ALCANCE DECLARADO:
Este módulo NO accede a listas restrictivas externas (OFAC, ONU, UIAF,
WorldCheck). Genera la ficha estructural que el oficial de cumplimiento
debe usar como insumo para ejecutar la verificación en la plataforma
autorizada de su institución.

Postura: honesta y auditada. No fingir verificación que no se hace.
"""

import hashlib
import datetime
import re
import unicodedata


# ── Constantes ────────────────────────────────────────────────────────────────

PLATAFORMAS_RECOMENDADAS = [
    "UIAF Colombia — https://www.uiaf.gov.co",
    "Listas OFAC (US Treasury) — https://ofac.treasury.gov/sdn-list",
    "Listas ONU — https://www.un.org/securitycouncil/sanctions/materials",
    "WorldCheck / Refinitiv (suscripción institucional)",
    "Comisión de Regulación — Lista PEP DIAN/RUES",
]


# ── Normalización de nombres ──────────────────────────────────────────────────

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


# ── Motor principal ───────────────────────────────────────────────────────────

def generar_ficha_sarlaft(
    titulares: str,
    acreedor_snr: str = None,
    acreedor_real: str = None,
    constructor: str = None,
    folio: str = "N/D",
) -> dict:
    """Genera la ficha SARLAFT estructural para todos los sujetos vinculados.

    Args:
        titulares:    String con nombres de los titulares (separados por +).
        acreedor_snr: Nombre del acreedor según el SNR.
        acreedor_real: Nombre del acreedor real declarado.
        constructor:  Nombre del constructor/enajenante original.
        folio:        Matrícula inmobiliaria del activo.

    Returns:
        Dict con: sujetos (list), timestamp, folio, estado, instrucciones.
    """
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    sujetos = []

    # Procesar titulares (pueden venir como "Nombre1 + Nombre2")
    if titulares and "PENDIENTE" not in str(titulares).upper():
        for nombre_raw in re.split(r"\+|,|;", str(titulares)):
            nombre = nombre_raw.strip()
            if not nombre:
                continue
            # Separar nombre de CC si viene concatenado (ej. "Nombre (CC 123)")
            cc_match = re.search(r"\(CC\s*([\d\.]+)\)", nombre)
            cc = cc_match.group(1) if cc_match else None
            nombre_limpio = re.sub(r"\(CC.*?\)", "", nombre).strip()
            sujetos.append({
                "rol": "TITULAR",
                "nombre_declarado": nombre_limpio,
                "nombre_normalizado": _normalizar_nombre(nombre_limpio),
                "hash_sha256_16": _hash_nombre(nombre_limpio),
                "identificacion": cc or "N/D",
                "estado_verificacion": "PENDIENTE_PLATAFORMA_EXTERNA",
            })

    # Acreedor SNR
    if acreedor_snr:
        sujetos.append({
            "rol": "ACREEDOR_SNR",
            "nombre_declarado": acreedor_snr,
            "nombre_normalizado": _normalizar_nombre(acreedor_snr),
            "hash_sha256_16": _hash_nombre(acreedor_snr),
            "identificacion": "N/D",
            "estado_verificacion": "PENDIENTE_PLATAFORMA_EXTERNA",
        })

    # Acreedor real (si difiere)
    if acreedor_real and acreedor_real != acreedor_snr:
        sujetos.append({
            "rol": "ACREEDOR_REAL_DECLARADO",
            "nombre_declarado": acreedor_real,
            "nombre_normalizado": _normalizar_nombre(acreedor_real),
            "hash_sha256_16": _hash_nombre(acreedor_real),
            "identificacion": "N/D",
            "estado_verificacion": "PENDIENTE_PLATAFORMA_EXTERNA",
        })

    # Constructor
    if constructor and constructor != "N/D":
        nombre_const = re.sub(r"\(NIT.*?\)", "", str(constructor)).strip()
        sujetos.append({
            "rol": "CONSTRUCTOR_ENAJENANTE",
            "nombre_declarado": nombre_const,
            "nombre_normalizado": _normalizar_nombre(nombre_const),
            "hash_sha256_16": _hash_nombre(nombre_const),
            "identificacion": "N/D",
            "estado_verificacion": "PENDIENTE_PLATAFORMA_EXTERNA",
        })

    # Hash de la ficha completa (integridad)
    ficha_raw = folio + timestamp + "".join(s["hash_sha256_16"] for s in sujetos)
    hash_ficha = hashlib.sha256(ficha_raw.encode("utf-8")).hexdigest()[:24].upper()

    return {
        "folio": folio,
        "timestamp_utc": timestamp,
        "total_sujetos": len(sujetos),
        "sujetos": sujetos,
        "hash_ficha": hash_ficha,
        "estado_global": (
            "PENDIENTE_VERIFICACION_EXTERNA" if sujetos else "SIN_SUJETOS_IDENTIFICADOS"
        ),
        "instruccion_oficial_cumplimiento": (
            "Esta ficha es un insumo estructural de carácter automático generado "
            "por el motor ARHIAX. El oficial de cumplimiento DEBE ejecutar la "
            "verificación de cada sujeto contra las listas restrictivas vigentes "
            "en la plataforma autorizada de su institución antes de tomar cualquier "
            "decisión de crédito, garantía o transferencia."
        ),
        "plataformas_recomendadas": PLATAFORMAS_RECOMENDADAS,
        "disclaimer": (
            "ARHIAX no tiene acceso a listas OFAC, ONU, UIAF ni WorldCheck. "
            "Los hashes SHA-256 garantizan la trazabilidad y no-alteración de "
            "los nombres auditados en este insumo. No constituye verificación SARLAFT."
        ),
    }


def generar_tabla_sarlaft(ficha: dict) -> list:
    """Genera filas para la tabla PDF de la ficha SARLAFT.

    Returns:
        List of (label, valor) tuples para data_table().
    """
    filas = [
        ("Estado de verificación SARLAFT",
         f"⚠ PENDIENTE VERIFICACIÓN EXTERNA — {ficha['total_sujetos']} sujetos identificados"),
        ("Hash de integridad de la ficha", ficha["hash_ficha"]),
        ("Timestamp de generación (UTC)", ficha["timestamp_utc"]),
    ]
    for s in ficha["sujetos"]:
        filas.append((
            f"{s['rol']}: {s['nombre_declarado']}",
            f"Hash: {s['hash_sha256_16']} | ID: {s['identificacion']} | Estado: {s['estado_verificacion']}"
        ))
    filas.append((
        "Plataformas de verificación",
        " · ".join(ficha["plataformas_recomendadas"][:2]) + " (y otras)"
    ))
    return filas

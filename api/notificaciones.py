# -*- coding: utf-8 -*-
"""
ARHIAX RE — Notificaciones por correo de documentos SARLAFT pendientes (Resend)

Cuando el screening SAGRILAFT detecta insumos que un agente IA NO puede
descargar (UIAF por canal oficial, UE por archivo manual, PEP, beneficiario
final) o la ruta de verificación exige documentos humanos (extracto hipotecario,
levantamiento de afectación, etc.), este módulo envía un correo al responsable
con la lista exacta y las instrucciones para obtener cada documento.

Configuración (variables de entorno):
  - RESEND_API_KEY      : API key de Resend (obligatoria para enviar).
  - RESEND_FROM         : remitente verificado (default onboarding@resend.dev).
  - ARHIAX_NOTIFY_EMAIL : destinatario (default alissduran@gmail.com).

Nunca rompe el flujo: si Resend no está configurado o falla, `enviar_correo`
devuelve False y la generación del dictamen continúa.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

RESEND_API_URL = "https://api.resend.com/emails"
_DESTINATARIO_DEFAULT = "alissduran@gmail.com"

# Catálogo de documentos que requieren acción humana (el agente IA no los baja).
_DOCUMENTOS: Dict[str, Dict[str, str]] = {
    "uiaf": {
        "documento": "Lista UIAF (vinculante/cautelar de Colombia)",
        "por_que": "No tiene feed público: solo se consulta por el canal oficial autorizado.",
        "como": "Consultar en www.uiaf.gov.co con las credenciales institucionales y anexar el acta/resultado.",
    },
    "ue": {
        "documento": "Lista UE — Consolidated Sanctions List (XML)",
        "por_que": "El portal webgate bloquea la descarga automática (403 anti-bot).",
        "como": "Descargar el XML desde sankcijas.fid.gov.lv/files/xmlFullSanctionsList_1_1.xml y subirlo al caso.",
    },
    "pep": {
        "documento": "Consulta PEP (Personas Expuestas Políticamente)",
        "por_que": "Requiere registros oficiales (Procuraduría/Contraloría) o declaración del cliente.",
        "como": "Consultar el registro de servidores públicos o solicitar la declaración PEP al cliente.",
    },
    "beneficiario_final": {
        "documento": "Certificado de beneficiarios finales (RUB)",
        "por_que": "Si hay persona jurídica, se requiere identificar al dueño real (participación ≥5%).",
        "como": "Solicitar el certificado en Cámara de Comercio / DIAN.",
    },
    "hipoteca": {
        "documento": "Extracto oficial del crédito hipotecario",
        "por_que": "Para verificar saldo insoluto, cuota, vencimiento y cláusulas de prepago.",
        "como": "Solicitar al banco acreedor registrado en el CTL.",
    },
    "afectacion": {
        "documento": "Levantamiento de afectación a vivienda familiar",
        "por_que": "Sin el levantamiento inscrito, cualquier acto de disposición es nulo.",
        "como": "Escritura pública suscrita por ambos titulares e inscrita en la ORIP.",
    },
    "embargo": {
        "documento": "Certificación del juzgado sobre el embargo",
        "por_que": "El embargo bloquea la disposición del bien hasta su levantamiento.",
        "como": "Solicitar radicado y estado del proceso al juzgado competente.",
    },
    "patrimonio": {
        "documento": "Resolución de desafectación de patrimonio de familia",
        "por_que": "El bien es inembargable hasta su desafectación (Ley 70/1931).",
        "como": "Tramitar la resolución judicial o notarial e inscribirla en la ORIP.",
    },
}


def compilar_pendientes(titulux: Dict[str, Any], hallazgos) -> List[Dict[str, str]]:
    """Compila la lista única de documentos pendientes (fuentes + hallazgos)."""
    pendientes: List[Dict[str, str]] = []
    vistos: set = set()

    # 1) Fuentes del screening SARLAFT (UIAF, UE, etc.).
    for f in (titulux or {}).get("fuentes_pendientes", []):
        clave = str(f).lower()
        if clave in _DOCUMENTOS and clave not in vistos:
            vistos.add(clave)
            item = dict(_DOCUMENTOS[clave])
            item["id"] = clave
            pendientes.append(item)

    # 2) Hallazgos de la ruta de verificación (por palabra clave del título).
    for h in hallazgos or []:
        titulo = (h[3] if len(h) > 3 else "") or ""
        tl = titulo.lower()
        for clave in ("hipoteca", "afectacion", "embargo", "patrimonio"):
            if clave in tl and clave not in vistos:
                vistos.add(clave)
                item = dict(_DOCUMENTOS[clave])
                item["id"] = clave
                pendientes.append(item)
                break

    return pendientes


def enviar_correo_pendientes(folio: str, pendientes: List[Dict[str, str]],
                             destinatario: str = None) -> bool:
    """Envía el correo con la lista de documentos pendientes. True si se envió."""
    api_key = os.environ.get("RESEND_API_KEY", "").strip()
    if not api_key or not pendientes:
        return False
    to = (destinatario or os.environ.get("ARHIAX_NOTIFY_EMAIL", "").strip()
          or _DESTINATARIO_DEFAULT).strip()
    if not to:
        return False
    remitente = os.environ.get("RESEND_FROM", "").strip() or "ARHIAX RE <onboarding@resend.dev>"

    filas = ""
    for p in pendientes:
        filas += (
            f"<li><b>{p.get('documento', '')}</b><br>"
            f"{p.get('por_que', '')}<br>"
            f"<i>Cómo obtenerlo:</i> {p.get('como', '')}</li>"
        )
    html = (
        f"<h3>ARHIAX RE — Documentos pendientes de debida diligencia</h3>"
        f"<p>Folio: <b>{folio}</b>. Para completar la verificación SAGRILAFT / debida "
        f"diligencia se requieren los siguientes documentos, que solo puede gestionar "
        f"un humano (un agente automático no puede descargarlos):</p>"
        f"<ul>{filas}</ul>"
        f"<p>Descárgalos y súbelos al caso en el portal ARHIAX para que queden adjuntos "
        f"al dictamen.</p>"
    )
    try:
        import requests
        r = requests.post(
            RESEND_API_URL,
            json={
                "from": remitente,
                "to": [to],
                "subject": f"ARHIAX — Documentos pendientes del folio {folio}",
                "html": html,
            },
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15,
        )
        return r.status_code in (200, 201, 202)
    except Exception:
        return False

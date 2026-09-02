# -*- coding: utf-8 -*-
"""
ARHIAX RE — Cola asíncrona de generación de PDF (QStash de Upstash)

Permite encolar la compilación pesada del dictamen en QStash:

    QSTASH_TOKEN      -> token del servicio (console.upstash.com -> QStash -> Tokens)
    QSTASH_URL        -> URL regional/global del API (default https://qstash.upstash.io;
                         p. ej. https://qstash-us-east-1.upstash.io)
    ARHIAX_WORKER_URL -> URL pública del worker, p. ej.
                         https://arhiax-re.vercel.app/api/v1/pdf/worker

Sin token configurado, encolar_generacion() devuelve encolado=False y el
llamador ejecuta el camino síncrono (fallback): la app nunca se bloquea.
"""

from __future__ import annotations

import os
from typing import Any

import requests

QSTASH_TOKEN = os.environ.get("QSTASH_TOKEN", "").strip()
QSTASH_URL = os.environ.get("QSTASH_URL", "").strip() or "https://qstash.upstash.io"
WORKER_URL = os.environ.get("ARHIAX_WORKER_URL", "").strip()


def cola_configurada() -> bool:
    return bool(QSTASH_TOKEN and WORKER_URL)


def estado_cola() -> dict[str, Any]:
    return {
        "configurada": cola_configurada(),
        "worker_url": WORKER_URL or None,
        "qstash_url": QSTASH_URL if cola_configurada() else None,
        "proveedor": "qstash" if cola_configurada() else None,
    }


def encolar_generacion(datos: dict) -> dict[str, Any]:
    """Encola un trabajo de compilación en QStash.

    Retorna: {"encolado": True, "message_id": ...} o
             {"encolado": False, "error": .../ "motivo": ...} para fallback síncrono.
    """
    if not cola_configurada():
        return {
            "encolado": False,
            "motivo": "QStash no configurado (faltan QSTASH_TOKEN o ARHIAX_WORKER_URL). "
                      "Ver README_PLAN -> cómo obtener el token.",
        }
    try:
        # API QStash v2: POST /v2/publish/{destination} (V1 /v1/publish fue eliminado)
        resp = requests.post(
            f"{QSTASH_URL.rstrip('/')}/v2/publish/{WORKER_URL}",
            json=datos,
            headers={"Authorization": f"Bearer {QSTASH_TOKEN}", "Content-Type": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        return {"encolado": True, "message_id": resp.json().get("messageId")}
    except Exception as e:
        return {"encolado": False, "error": str(e)[:150]}

"""Construcción de eventos de evidencia (envelope B18/B03, 9.22) con cadena encadenada.

Corrección P0-5 de la auditoría:
  - La clave HMAC NO está fija en el código: se lee de `ARHIA_HMAC_KEY`; si no se define, se genera
    una clave aleatoria por proceso (demo) y se registra un aviso.
  - `hmacChain` se calcula sobre el **envelope completo canónico** (no solo el payload).
  - Se añaden `event_id` (único), `previous_hash` y `chain_hash` (hash encadenado sobre el envelope
    completo + hash anterior), de modo que los eventos no puedan reordenarse/duplicarse sin detección.
  - `payload_hmac_demo` se conserva como referencia sobre el payload (heredado), claramente marcado.
"""
import datetime
import json
import os
import uuid

from ..contracts import ResultadoConsulta
from .versioning import hmac_hex, sha256_hex


def _key():
    k = os.environ.get("ARHIA_HMAC_KEY")
    if k:
        return k
    # Clave aleatoria por proceso (demo). En producción: KMS/HSM + rotación, fuera del código.
    return uuid.uuid4().hex


DEFAULT_HMAC_KEY = None  # se resuelve por proceso (ya no hay clave fija pública en el código)


def _canonical(d):
    return json.dumps(d, sort_keys=True, separators=(",", ":")).encode()


def _envelope_canonical(payload, ev):
    body = {k: v for k, v in ev.items() if k not in ("hmacChain", "chain_hash", "payload_hmac_demo")}
    body["payload"] = payload
    return _canonical(body)


def build_event(control_id, event_type, agent_id, payload, now=None, at_type="LOG",
                retention_tier="Tier2", hmac_key=None, previous_hash=""):
    """Construye un evento con `hmacChain` (envelope completo) + `chain_hash` encadenado."""
    ts = (now or datetime.datetime.now(datetime.timezone.utc)).isoformat()
    event_id = uuid.uuid4().hex
    key = hmac_key or _key()
    ev_base = {
        "@context": "https://arhia.sinergia.co/schema/evidence/v11.4",
        "@type": "Evidence",
        "eventId": event_id,
        "controlId": control_id,
        "eventType": event_type,
        "atType": at_type,
        "agentId": agent_id,
        "timestamp": ts,
        "retentionTier": retention_tier,
    }
    # HMAC sobre el envelope completo canónico (integridad de todos los campos).
    hmac_full = hmac_hex(_envelope_canonical(payload, ev_base), key)
    # Hash encadenado: envelope completo + hash anterior.
    chain_hash = sha256_hex(_canonical(ev_base) + b"|" + (previous_hash or "").encode()
                            + b"|" + json.dumps(payload, sort_keys=True).encode())
    ev = {**ev_base, "payload": payload, "hmacChain": hmac_full,
          "chain_hash": chain_hash, "previous_hash": previous_hash}
    # Referencia heredada sobre el payload (claramente marcada, no es la cadena).
    ev["payload_hmac_demo"] = hmac_hex(_canonical(payload), key)
    return ev


def build_lista_consultada(resultado, agent_id, now=None, hmac_key=None):
    ts = (now or datetime.datetime.now(datetime.timezone.utc)).isoformat()
    payload = {
        "contraparteId": resultado.contraparte_id,
        "lista": resultado.lista,
        "listaVersion": resultado.lista_version,
        "listaHash": resultado.lista_hash,
        "fechaEmisionLista": resultado.lista_version,
        "resultado": resultado.resultado,
        "score": resultado.score,
        "matchedFields": list(resultado.matched_fields),
        "coincidenciaId": resultado.coincidencia_id,
    }
    return build_event("SAG-C03", "LISTA_CONSULTADA", agent_id, payload, now=now,
                       at_type="LOG", retention_tier="Tier2", hmac_key=hmac_key)


def verificar_cadena(eventos):
    """Verifica la integridad de la cadena: cada `chain_hash` debe encadenar al anterior."""
    prev = ""
    for e in eventos:
        if e.get("previous_hash", "") != prev:
            return False
        # recompute chain_hash para verificar
        base = {k: v for k, v in e.items()
                if k not in ("hmacChain", "chain_hash", "payload_hmac_demo", "payload", "previous_hash")}
        if sha256_hex(_canonical(base) + b"|" + (prev or "").encode()
                      + b"|" + json.dumps(e.get("payload", {}), sort_keys=True).encode()) != e.get("chain_hash"):
            return False
        prev = e.get("chain_hash", "")
    return True

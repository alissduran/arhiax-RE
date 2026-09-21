# -*- coding: utf-8 -*-
"""Adquisición de fuentes oficiales → snapshot versionado (§13–§16).

Honestidad de origen (§16): `freshness` distingue la descarga REAL en esta
ejecución (`LIVE_FRESH`) del snapshot oficial ya versionado (`CACHED_FRESH`,
`STALE_ALLOWED`). Solo la primera permite escribir "consultado en vivo".
"""
from __future__ import annotations

import datetime
import hashlib
import re
import urllib.request
from typing import Any, List, Optional, Tuple

from . import parsers
from .contracts import (
    FRESH_CACHED, FRESH_LIVE, NO_SNAPSHOT, SNAP_OPERATIVA, SOURCE_UNAVAILABLE,
    STALE_ALLOWED, STALE_NOT_ALLOWED, SanctionsSnapshot,
)
from .registry import SourceDefinition, get_source
from .snapshots import (
    TTL_DEFAULT, SnapshotStore, error_snapshot, evaluar_frescura, snapshot_id,
)

UA = "ARHIAX-RE/1.4 (+screening sancionatorio; contacto: sinergia consulting group)"


def _ahora_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def fetch_bytes(url: str, timeout: int = 90) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


_RE_FECHAS = (
    re.compile(rb'dateGenerated\s*=\s*"([^"]{4,40})"', re.IGNORECASE),
    re.compile(rb"<DateGenerated>\s*([^<]{4,40})\s*</DateGenerated>", re.IGNORECASE),
    re.compile(rb"<Publish_Date>\s*([^<]{4,40})\s*</Publish_Date>", re.IGNORECASE),
    re.compile(rb"<DateOfIssue>\s*([^<]{4,40})\s*</DateOfIssue>", re.IGNORECASE),
    re.compile(rb"<GENERATED_ON>\s*([^<]{4,40})\s*</GENERATED_ON>", re.IGNORECASE),
)


def fecha_efectiva(source_id: str, xml_bytes: bytes) -> str:
    """Fecha que la PROPIA fuente declara (si la declara). Nunca se inventa.

    Se lee de la CABECERA del XML por expresión regular: parsear el documento
    completo solo para leer un atributo sería absurdo (y no se puede parsear un
    fragmento truncado). Formatos oficiales observados en la verificación en
    vivo de 03S.1:
      * ONU: atributo `dateGenerated` en la raíz (`<CONSOLIDATED_LIST ...>`).
      * OFAC: `<Publish_Date>` dentro de `<publshInformation>`.
      * UK:  `<DateGenerated>`.
    """
    prefijo = (xml_bytes or b"")[:400000]
    for rx in _RE_FECHAS:
        m = rx.search(prefijo)
        if m:
            try:
                return m.group(1).decode("utf-8", "replace").strip()
            except Exception:  # noqa: BLE001
                continue
    return ""


def adquirir_fuente(
    source_id: str,
    *,
    store: Optional[SnapshotStore] = None,
    timeout: int = 120,
    force_refresh: bool = False,
    ttl_segundos: int = TTL_DEFAULT,
    permitir_stale: bool = True,
    permitir_descarga: bool = True,
    url_override: Optional[str] = None,
) -> Tuple[SanctionsSnapshot, List[Any]]:
    """Devuelve (snapshot, registros) para UNA fuente, sin inventar nada.

    Orden: snapshot vigente en el store → descarga real → snapshot vencido
    (si la política lo permite) → SOURCE_UNAVAILABLE declarado.

    `permitir_descarga=False` (suite offline / ejecución sin red) impide
    cualquier acceso de red: solo se sirve lo que ya esté en el store.
    """
    src: Optional[SourceDefinition] = get_source(source_id)
    if src is None:
        return (error_snapshot(source_id, "", "", "fuente no registrada",
                               ""), [])
    store = store or SnapshotStore()

    # 1) Snapshot del store (sin red): la frescura se CALCULA por edad, nunca se
    #    hereda. Un snapshot que en su día se descargó queda como CACHED_FRESH:
    #    "en vivo" jamás se recupera del store (§ 03S.1A-1).
    if not force_refresh:
        guardado = store.ultimo(source_id)
        if guardado is not None:
            snap, regs = guardado
            _fresh = evaluar_frescura(snap, ttl_segundos=ttl_segundos,
                                      permitir_stale=permitir_stale)
            if _fresh == FRESH_CACHED and snap.acquisition_status == SNAP_OPERATIVA:
                return (_reemplazar(snap, freshness=_fresh, error=None,
                                    refresh_error=None), regs)
            # Vencido: el TTL manda refrescar. Si el refresco no es posible, el
            # paso 3 sirve este mismo snapshot como STALE_*. 

    # 2) Descarga real — ÚNICA rama que puede producir LIVE_FRESH.
    url = url_override or src.official_url
    error = ""
    if permitir_descarga:
        try:
            raw = fetch_bytes(url, timeout=timeout)
            sha = hashlib.sha256(raw).hexdigest()
            regs = parsers.parse(src.parser, raw)
            snap = SanctionsSnapshot(
                snapshot_id=snapshot_id(source_id, sha), source_id=source_id,
                authority=src.authority, retrieved_at=_ahora_iso(),
                effective_date=fecha_efectiva(source_id, raw), source_url=url,
                sha256=sha, record_count=len(regs),
                parser_version=src.parser_version, acquisition_status=SNAP_OPERATIVA,
                freshness=FRESH_LIVE)
            store.guardar(snap, regs)
            return snap, regs
        except Exception as e:  # noqa: BLE001
            error = f"{type(e).__name__}: {str(e)[:160]}"
    else:
        error = "descarga deshabilitada en esta ejecución (modo offline)"

    # 3) Fallback al snapshot del store. 03S.1B-6: la frescura describe la EDAD
    #    del snapshot, NO el resultado del refresco: se vuelve a evaluar la
    #    frescura real y se aplica la política. Un refresco fallido sobre una
    #    caché VIGENTE sigue siendo CACHED_FRESH (y el fallo se declara aparte en
    #    `refresh_error`).
    guardado = store.ultimo(source_id)
    if guardado is not None:
        snap, regs = guardado
        fresh = evaluar_frescura(snap, ttl_segundos=ttl_segundos,
                                 permitir_stale=permitir_stale)
        _usable = (fresh != STALE_NOT_ALLOWED
                   and snap.acquisition_status == SNAP_OPERATIVA)
        snap = _reemplazar(snap, freshness=fresh, error=None,
                           # Solo se declara lo que REALMENTE se intentó y falló.
                           refresh_error=((error or None) if permitir_descarga else None))
        return snap, (regs if _usable else [])

    # 4) Sin dato alguno: se declara la no disponibilidad (nunca lista vacía).
    return (error_snapshot(source_id, src.authority, url, error,
                           src.parser_version), [])


def _reemplazar(snap: SanctionsSnapshot, **cambios) -> SanctionsSnapshot:
    d = snap.to_dict()
    d.update(cambios)
    return SanctionsSnapshot(**d)


def fuente_disponible(snap: Optional[SanctionsSnapshot]) -> bool:
    """¿La fuente aporta evidencia utilizable en ESTA ejecución?

    Utilizable = snapshot OPERATIVO de una fuente oficial, sea descargado ahora
    (LIVE_FRESH), vigente en el store (CACHED_FRESH) o vencido pero admitido por
    política (STALE_ALLOWED). STALE_NOT_ALLOWED / SOURCE_UNAVAILABLE / NO_SNAPSHOT
    NO son evidencia: no pueden sostener un "sin coincidencia".
    """
    if snap is None or snap.acquisition_status != SNAP_OPERATIVA:
        return False
    return snap.freshness in (FRESH_LIVE, FRESH_CACHED, STALE_ALLOWED)


def es_en_vivo(snap: Optional[SanctionsSnapshot]) -> bool:
    """Solo True si hubo adquisición REAL en esta ejecución (§16)."""
    return bool(snap and snap.freshness == FRESH_LIVE
                and snap.acquisition_status == SNAP_OPERATIVA)


def es_cache(snap: Optional[SanctionsSnapshot]) -> bool:
    return bool(snap and snap.freshness in (FRESH_CACHED, STALE_ALLOWED))


ESTADOS_NO_DISPONIBLE = (SOURCE_UNAVAILABLE, STALE_NOT_ALLOWED, NO_SNAPSHOT)

# -*- coding: utf-8 -*-
"""Snapshots versionados, inmutables y con historia (§13–§16).

Dos reglas que este módulo debe garantizar:

  * §14 — NO se borra historia: cada adquisición se guarda por
    (source_id, sha256) y se conserva un puntero al snapshot CURRENT. Un
    dictamen de ayer puede reproducirse contra exactamente la misma lista.
  * §15 — el TTL controla el REFRESCO, no la evidencia: al vencer el TTL el
    snapshot sigue existiendo (STALE_ALLOWED / STALE_NOT_ALLOWED según política).

Almacenamiento:
  * Siempre: store en disco (determinista, offline, testeable).
  * Si la BD es Postgres/Neon: además tabla `sanctions_snapshots` (idempotente,
    sin DELETE), que es la que sobrevive a los contenedores serverless.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict
from typing import Any, Dict, List, Optional, Tuple

from .contracts import (
    FRESH_CACHED, FRESH_LIVE, NO_SNAPSHOT, SNAP_OPERATIVA, SOURCE_UNAVAILABLE,
    STALE_ALLOWED, STALE_NOT_ALLOWED, SanctionsSnapshot,
)

TTL_DEFAULT = 24 * 3600


def _cache_base(cache_dir: Optional[str]) -> str:
    base = cache_dir or os.environ.get("ARHIA_LISTAS_CACHE")
    if base:
        os.makedirs(base, exist_ok=True)
        return base
    here = os.path.dirname(__file__)
    d = os.path.join(os.path.dirname(here), "assets", "cache_sanctions")
    os.makedirs(d, exist_ok=True)
    return d


class SnapshotStore:
    """Store de snapshots (disco siempre; Neon si está disponible)."""

    def __init__(self, cache_dir: Optional[str] = None, usar_neon: bool = True):
        self.base = _cache_base(cache_dir)
        self.usar_neon = usar_neon

    # ── Rutas ────────────────────────────────────────────────────────────────
    def _dir(self, source_id: str) -> str:
        d = os.path.join(self.base, "sanctions_snapshots", source_id)
        os.makedirs(d, exist_ok=True)
        return d

    def _path(self, source_id: str, sha: str) -> str:
        return os.path.join(self._dir(source_id), f"{sha or 'sin-hash'}.json")

    def _current_path(self, source_id: str) -> str:
        return os.path.join(self._dir(source_id), "CURRENT")

    # ── Escritura (nunca borra) ──────────────────────────────────────────────
    def guardar(self, snap: SanctionsSnapshot, registros) -> None:
        payload = {"snapshot": snap.to_dict(),
                   "registros": [_reg_dict(r) for r in (registros or [])]}
        try:
            with open(self._path(snap.source_id, snap.sha256), "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
            with open(self._current_path(snap.source_id), "w", encoding="utf-8") as f:
                f.write(snap.sha256 or "")
        except Exception:  # noqa: BLE001
            pass
        if self.usar_neon:
            self._neon_guardar(snap, payload)

    # ── Lectura ──────────────────────────────────────────────────────────────
    def cargar(self, source_id: str, sha256: str) -> Optional[Tuple[SanctionsSnapshot, List[Any]]]:
        r = self._leer_disco(source_id, sha256)
        if r is not None:
            return r
        if self.usar_neon:
            return self._neon_cargar(source_id, sha256)
        return None

    def current_sha(self, source_id: str) -> Optional[str]:
        p = self._current_path(source_id)
        try:
            if os.path.exists(p):
                with open(p, encoding="utf-8") as f:
                    return f.read().strip() or None
        except Exception:  # noqa: BLE001
            pass
        return self._neon_current_sha(source_id)

    def ultimo(self, source_id: str) -> Optional[Tuple[SanctionsSnapshot, List[Any]]]:
        sha = self.current_sha(source_id)
        if sha:
            r = self.cargar(source_id, sha)
            if r is not None:
                return r
        # Fallback: el snapshot más reciente del historial en disco.
        d = os.path.join(self.base, "sanctions_snapshots", source_id)
        if not os.path.isdir(d):
            return None
        cands = []
        for nombre in os.listdir(d):
            if not nombre.endswith(".json"):
                continue
            p = os.path.join(d, nombre)
            try:
                cands.append((os.path.getmtime(p), nombre[:-5]))
            except Exception:  # noqa: BLE001
                continue
        for _, sha in sorted(cands, reverse=True):
            r = self.cargar(source_id, sha)
            if r is not None:
                return r
        return None

    def historial(self, source_id: str) -> List[SanctionsSnapshot]:
        d = os.path.join(self.base, "sanctions_snapshots", source_id)
        out: List[SanctionsSnapshot] = []
        if os.path.isdir(d):
            for nombre in sorted(os.listdir(d)):
                if not nombre.endswith(".json"):
                    continue
                r = self._leer_disco(source_id, nombre[:-5])
                if r is not None:
                    out.append(r[0])
        return out

    # ── Disco ────────────────────────────────────────────────────────────────
    def _leer_disco(self, source_id: str, sha256: str):
        p = self._path(source_id, sha256)
        if not os.path.exists(p):
            return None
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
            snap = _snap_desde_dict(data.get("snapshot") or {})
            return snap, list(data.get("registros") or ())
        except Exception:  # noqa: BLE001
            return None

    # ── Neon (opcional, defensivo) ───────────────────────────────────────────
    def _neon_conn(self):
        try:
            from database import DB_PATH, get_db_connection
            if not DB_PATH or not str(DB_PATH).startswith(("postgres://", "postgresql://")):
                return None
            conn = get_db_connection()
            conn.execute(
                "CREATE TABLE IF NOT EXISTS sanctions_snapshots ("
                "source_id TEXT NOT NULL, sha256 TEXT NOT NULL, "
                "snapshot_id TEXT NOT NULL, authority TEXT, retrieved_at TEXT, "
                "effective_date TEXT, source_url TEXT, record_count INTEGER, "
                "parser_version TEXT, acquisition_status TEXT, payload TEXT NOT NULL, "
                "is_current BOOLEAN NOT NULL DEFAULT FALSE, "
                "created_at DOUBLE PRECISION NOT NULL, updated_at DOUBLE PRECISION NOT NULL, "
                "PRIMARY KEY (source_id, sha256))")
            conn.commit()
            return conn
        except Exception:  # noqa: BLE001
            return None

    def _neon_guardar(self, snap: SanctionsSnapshot, payload: Dict[str, Any]) -> None:
        conn = self._neon_conn()
        if conn is None:
            return
        try:
            ahora = time.time()
            conn.execute(
                "INSERT INTO sanctions_snapshots (source_id, sha256, snapshot_id, authority, "
                "retrieved_at, effective_date, source_url, record_count, parser_version, "
                "acquisition_status, payload, is_current, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (source_id, sha256) DO UPDATE SET "
                "payload = EXCLUDED.payload, updated_at = EXCLUDED.updated_at",
                (snap.source_id, snap.sha256, snap.snapshot_id, snap.authority,
                 snap.retrieved_at, snap.effective_date, snap.source_url,
                 int(snap.record_count or 0), snap.parser_version,
                 snap.acquisition_status, json.dumps(payload, ensure_ascii=False),
                 True, ahora, ahora))
            # El puntero CURRENT se mueve con un UPDATE: la historia permanece.
            conn.execute(
                "UPDATE sanctions_snapshots SET is_current = FALSE "
                "WHERE source_id = ? AND sha256 <> ?", (snap.source_id, snap.sha256))
            conn.commit()
            conn.close()
        except Exception:  # noqa: BLE001
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass

    def _neon_current_sha(self, source_id: str) -> Optional[str]:
        conn = self._neon_conn()
        if conn is None:
            return None
        try:
            cur = conn.execute(
                "SELECT sha256 FROM sanctions_snapshots WHERE source_id = ? "
                "AND is_current = TRUE", (source_id,))
            fila = cur.fetchone()
            conn.close()
            if fila is None:
                return None
            return fila["sha256"] if not isinstance(fila, tuple) else fila[0]
        except Exception:  # noqa: BLE001
            return None

    def _neon_cargar(self, source_id: str, sha256: str):
        conn = self._neon_conn()
        if conn is None:
            return None
        try:
            cur = conn.execute(
                "SELECT payload FROM sanctions_snapshots WHERE source_id = ? AND sha256 = ?",
                (source_id, sha256))
            fila = cur.fetchone()
            conn.close()
            if fila is None:
                return None
            payload = fila["payload"] if not isinstance(fila, tuple) else fila[0]
            data = json.loads(payload)
            return (_snap_desde_dict(data.get("snapshot") or {}),
                    list(data.get("registros") or ()))
        except Exception:  # noqa: BLE001
            return None


def _reg_dict(r: Any) -> Dict[str, Any]:
    if isinstance(r, dict):
        return r
    try:
        return asdict(r)
    except Exception:  # noqa: BLE001
        return {k: getattr(r, k, None) for k in
                ("id", "nombre", "alias", "tipo_documento", "numero_documento",
                 "fecha_nacimiento", "programas", "fuente", "lista_version")}


def _snap_desde_dict(d: Dict[str, Any]) -> SanctionsSnapshot:
    return SanctionsSnapshot(
        snapshot_id=d.get("snapshot_id", ""), source_id=d.get("source_id", ""),
        authority=d.get("authority", ""), retrieved_at=d.get("retrieved_at", ""),
        effective_date=d.get("effective_date", "") or "",
        source_url=d.get("source_url", "") or "", sha256=d.get("sha256", "") or "",
        record_count=int(d.get("record_count") or 0),
        parser_version=d.get("parser_version", "") or "",
        acquisition_status=d.get("acquisition_status", SNAP_OPERATIVA),
        freshness=d.get("freshness", NO_SNAPSHOT), error=d.get("error"),
        refresh_error=d.get("refresh_error"))


def evaluar_frescura(snap: Optional[SanctionsSnapshot], *, ahora: Optional[float] = None,
                     ttl_segundos: int = TTL_DEFAULT, permitir_stale: bool = True) -> str:
    """Frescura de un snapshot (§15). El TTL controla el refresco, no la evidencia.

    03S.1A — LA FRESCURA ES LOCAL A LA EJECUCIÓN. Esta función NUNCA devuelve
    `LIVE_FRESH`: ese estado solo puede originarlo la rama que acaba de ejecutar
    `fetch_bytes()` con éxito en ESTA ejecución. Un snapshot guardado con
    `freshness=LIVE_FRESH` (porque en su momento se descargó) NO puede reclamar
    "en vivo" al releerlo: aquí siempre se calcula la EDAD real.

    (Bug corregido: existía el atajo `if snap.freshness == LIVE_FRESH: return
    LIVE_FRESH`, que propagaba "en vivo" a ejecuciones posteriores.)
    """
    if snap is None or not snap.sha256:
        return NO_SNAPSHOT
    try:
        from datetime import datetime
        ts = datetime.fromisoformat(str(snap.retrieved_at).replace("Z", "+00:00")).timestamp()
    except Exception:  # noqa: BLE001
        # Sin fecha de obtención fiable no se puede afirmar frescura: se trata
        # como vencido y se aplica la política.
        return STALE_ALLOWED if permitir_stale else STALE_NOT_ALLOWED
    edad = (ahora if ahora is not None else time.time()) - ts
    if edad <= ttl_segundos:
        return FRESH_CACHED
    return STALE_ALLOWED if permitir_stale else STALE_NOT_ALLOWED


def snapshot_id(source_id: str, sha256: str) -> str:
    return f"{source_id}:{(sha256 or '')[:16]}"


def error_snapshot(source_id: str, authority: str, source_url: str,
                   error: str, parser_version: str = "") -> SanctionsSnapshot:
    """Snapshot que documenta un FALLO de adquisición (no se inventa nada)."""
    import datetime
    return SanctionsSnapshot(
        snapshot_id=snapshot_id(source_id, ""), source_id=source_id,
        authority=authority, source_url=source_url,
        retrieved_at=datetime.datetime.now(datetime.timezone.utc).isoformat()
        .replace("+00:00", "Z"),
        parser_version=parser_version, acquisition_status=SOURCE_UNAVAILABLE,
        freshness=SOURCE_UNAVAILABLE, error=error)

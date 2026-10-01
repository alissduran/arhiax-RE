# -*- coding: utf-8 -*-
"""ARHIAX RE — RE-HASH OFFLINE de las referencias de nivel 3 de la cosecha municipal.

Cierra el DEFECTO de verificabilidad del `evidence_hash`: con la política anterior el
hash incluía `queried_at`, así que la MISMA evidencia producía hashes distintos en cada
adquisición (`6f84f220…` → `d89aa0c2…`) y ningún revisor podía comprobarlo contra el
payload crudo. Este script NO consulta la red: recalcula la identidad de hash sobre el
artefacto ya adquirido (`docs/estimation/MARKET_HARVEST_*.json`) y —cuando el payload
crudo está preservado— VERIFICA que el `payload_sha256` declarado sea el sha256 real de
los bytes guardados en `docs/estimation/raw/<capa>.json`.

    python scripts/market_harvest_rehash.py                 # reescribe el artefacto
    python scripts/market_harvest_rehash.py --dry-run        # sólo informa

Qué escribe, y sólo eso:

  · por referencia: `content_hash` (ESTABLE), `acquisition_id` y `acquisition_hash`
    (VOLÁTILES), `hash_policy` (versionada) y `evidence_hash` = `content_hash`;
  · en el artefacto: `hash_policy` + `rehash` (cuándo, con qué política y con qué
    verificación de payload).

NO toca: `docs/forensics/**`, el Source Pack, la Resolution Ladder, el master hash ni
ningún valor publicado por la fuente.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "api"))

import market_harvest as mh  # noqa: E402

ARTEFACTO = ROOT / "docs" / "estimation" / "MARKET_HARVEST_040-646406.json"
RAW_DIR = ROOT / "docs" / "estimation" / "raw"


def _sha256_archivo(ruta: Path) -> Optional[str]:
    if not ruta.exists():
        return None
    h = hashlib.sha256()
    with open(ruta, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _verificar_payload(fuente: str, servicio: str, declarado: Optional[str]
                       ) -> Dict[str, Any]:
    """¿El `payload_sha256` declarado es el sha256 REAL de los bytes preservados?"""
    for candidato in (RAW_DIR / f"{servicio}.json", RAW_DIR / f"{fuente}.json"):
        real = _sha256_archivo(candidato)
        if real is not None:
            return {"archivo": str(candidato.relative_to(ROOT)), "sha256_real": real,
                    "sha256_declarado": declarado,
                    "coincide": bool(declarado) and real == declarado}
    return {"archivo": None, "sha256_real": None, "sha256_declarado": declarado,
            "coincide": None,
            "motivo": "el payload crudo de esta capa no está preservado en raw/"}


def rehashear(folio: str = "040-646406", *, ruta: Optional[Path] = None,
              dry_run: bool = False) -> Dict[str, Any]:
    archivo = Path(ruta) if ruta else ARTEFACTO
    if not archivo.exists():
        raise SystemExit(f"[FAIL] falta el artefacto de cosecha: {archivo}")
    datos = json.loads(archivo.read_text(encoding="utf-8"))

    detalles: List[Dict[str, Any]] = []
    referencias = list(datos.get("level_3_referencias") or [])
    nuevas: List[Dict[str, Any]] = []
    for ref in referencias:
        antes = {c: ref.get(c) for c in ("evidence_hash", "content_hash", "acquisition_id")}
        nueva = mh.rehashear_referencia(ref)
        servicio = str((ref.get("provenance") or {}).get("referencia") or "").split("/")[0]
        verificacion = _verificar_payload(str(ref.get("source_id") or ""), servicio,
                                          nueva.get("payload_sha256"))
        detalles.append({
            "source_id": ref.get("source_id"),
            "reference_id": ref.get("reference_id"),
            "evidence_hash_antes": antes["evidence_hash"],
            "content_hash": nueva["content_hash"],
            "evidence_hash_estable": nueva["evidence_hash"] == nueva["content_hash"],
            "acquisition_id": nueva["acquisition_id"],
            "acquisition_hash": nueva["acquisition_hash"],
            "queried_at": nueva.get("queried_at"),
            "payload_sha256": nueva.get("payload_sha256"),
            "payload_verificado": verificacion,
        })
        nuevas.append(nueva)

    # Las capas conservan su adquisición literal; sólo se les añade el hash de
    # CONTENIDO del payload crudo cuando éste se puede verificar (nada se reescribe).
    capas = datos.get("capas") or {}
    for clave, capa in capas.items():
        if not isinstance(capa, dict):
            continue
        sha = capa.get("sha256")
        verificacion = _verificar_payload(str(capa.get("source_id") or clave), str(clave),
                                          sha)
        capa["content_hash"] = sha if verificacion.get("coincide") is not False else None
        capa["content_hash_verificado_contra_raw"] = verificacion.get("coincide")

    salida: Dict[str, Any] = {
        **datos,
        "level_3_referencias": nuevas,
        "capas": capas,
        "hash_policy": mh.politica_de_hash(),
        "rehash": {
            "version_politica": mh.HASH_POLICY_VERSION,
            "defecto_cerrado": ("el `evidence_hash` incluía `queried_at` y cambiaba en cada "
                               "adquisición de la MISMA evidencia: se separó en "
                               "`content_hash` (estable) + `acquisition_id`/"
                               "`acquisition_hash` (volátiles)"),
            "offline": True,
            "referencias": detalles,
        },
    }
    if not dry_run:
        archivo.write_text(json.dumps(salida, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    return {"archivo": str(archivo.relative_to(ROOT)), "referencias": detalles,
            "escrito": not dry_run}


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Re-hash offline de la evidencia de nivel 3")
    ap.add_argument("--folio", default="040-646406")
    ap.add_argument("--artefacto", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    r = rehashear(args.folio, ruta=Path(args.artefacto) if args.artefacto else None,
                  dry_run=args.dry_run)
    print(f"artefacto: {r['archivo']} · escrito={r['escrito']}")
    for d in r["referencias"]:
        print(f"  {d['source_id']} · {d['reference_id']}")
        print(f"    evidence_hash (antes) = {d['evidence_hash_antes']}")
        print(f"    content_hash (estable) = {d['content_hash']}")
        print(f"    acquisition_id          = {d['acquisition_id']}")
        print(f"    acquisition_hash         = {d['acquisition_hash']}")
        print(f"    payload_sha256           = {d['payload_sha256']} · verificado contra "
              f"raw = {d['payload_verificado'].get('coincide')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

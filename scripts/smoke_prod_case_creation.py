# -*- coding: utf-8 -*-
"""SMOKE PRODUCTIVO — creación de caso (hotfix 2.0B-R1.1).

    set ARHIAX_ACCESS_PASSWORD=...      # o --password-file <ruta>
    python scripts/smoke_prod_case_creation.py [--url https://arhiax-re.vercel.app] [--borrar]

Qué hace, en orden y contra el despliegue REAL:

  1. POST /api/login           -> token (nunca se imprime)
  2. POST /api/dictamenes      -> debe responder 200 con id, folio, dirección, ciudad y estado
  3. GET  /api/dictamenes      -> el caso creado debe aparecer en el listado
  4. DELETE /api/dictamenes/{id}  (solo con --borrar) -> deja la base como estaba

Evidencia que imprime: códigos HTTP, el cuerpo del caso (sin token) y el veredicto.
Con el defecto anterior (migration 003 con BLOB en Postgres) el paso 2 devolvía 500.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

FOLIO_SMOKE = "000-000999"
DIRECCION_SMOKE = "SMOKE 2.0B-R1.1 PRUEBA DE CREACION DE CASO"


def _peticion(url: str, metodo="GET", payload=None, token=None, timeout=60):
    datos = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=datos, method=metodo)
    req.add_header("Accept", "application/json")
    if datos is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            cuerpo = r.read().decode("utf-8", "replace")
            return r.status, cuerpo
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001 — red: se declara, no se inventa
        return None, f"{type(e).__name__}: {e}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Smoke productivo de creación de caso")
    ap.add_argument("--url", default=os.environ.get("ARHIAX_PROD_URL",
                                                   "https://arhiax-re.vercel.app"))
    ap.add_argument("--password", default=os.environ.get("ARHIAX_ACCESS_PASSWORD"))
    ap.add_argument("--password-file", default=None,
                    help="archivo con la contraseña (evita repetir el secreto en la línea de comandos)")
    ap.add_argument("--usuario", default="admin")
    ap.add_argument("--borrar", action="store_true",
                    help="elimina el caso de prueba al terminar (deja la base limpia)")
    ap.add_argument("--borrar-id", action="append", type=int, default=[],
                    help="elimina además un caso concreto (limpieza de corridas interrumpidas)")
    ap.add_argument("--ciudad", default="barranquilla")
    args = ap.parse_args(argv)

    if not args.password and args.password_file:
        from pathlib import Path
        args.password = Path(args.password_file).read_text(encoding="utf-8").strip()
    if not args.password:
        print("[SKIP] falta la contraseña de acceso (ARHIAX_ACCESS_PASSWORD, --password o "
              "--password-file).")
        return 2

    base = args.url.rstrip("/")
    print(f"destino: {base} · usuario: {args.usuario}")

    # 1 · login real
    st, cuerpo = _peticion(f"{base}/api/login", "POST",
                           {"username": args.usuario, "password": args.password})
    print(f"POST /api/login -> {st} {('' if st == 200 else cuerpo[:160])}")
    if st != 200:
        print("[FAIL] no se pudo autenticar: el smoke no puede continuar.")
        return 1
    token = json.loads(cuerpo).get("token")
    if not token:
        print("[FAIL] el login no devolvió token.")
        return 1

    # 2 · creación de caso (el endpoint del incidente)
    caso_payload = {"folio_matricula": FOLIO_SMOKE, "direccion": DIRECCION_SMOKE,
                    "ciudad": args.ciudad}
    st, cuerpo = _peticion(f"{base}/api/dictamenes", "POST", caso_payload, token)
    print(f"POST /api/dictamenes -> {st}")
    if st != 200:
        print(f"    respuesta: {cuerpo[:300]}")
        print("[FAIL] la creación de caso NO está restaurada en el despliegue.")
        return 1
    caso = json.loads(cuerpo)
    print("    caso creado: " + json.dumps(
        {k: caso.get(k) for k in ("id", "folio_matricula", "direccion", "ciudad",
                                  "estado", "created_by")}, ensure_ascii=False))
    for campo in ("id", "folio_matricula", "direccion", "ciudad", "estado"):
        if caso.get(campo) in (None, ""):
            print(f"[FAIL] la respuesta no trae «{campo}».")
            return 1

    # 3 · el caso aparece en el listado
    st, cuerpo = _peticion(f"{base}/api/dictamenes", "GET", None, token)
    print(f"GET /api/dictamenes -> {st}")
    if st != 200:
        print(f"    respuesta: {cuerpo[:200]}")
        return 1
    crudo = json.loads(cuerpo)
    # El endpoint devuelve la LISTA de casos (no un objeto envoltorio).
    if isinstance(crudo, list):
        listado = crudo
    elif isinstance(crudo, dict):
        listado = (crudo.get("casos") or crudo.get("dictamenes") or crudo.get("items")
                   or [])
    else:
        listado = []
    ids = [c.get("id") for c in listado if isinstance(c, dict)]
    encontrado = caso["id"] in ids
    print(f"    casos en el listado: {len(ids)} · ¿está el creado ({caso['id']})? "
          f"{'SÍ' if encontrado else 'NO'}")
    if not encontrado:
        print("[FAIL] el caso creado no aparece en GET /api/dictamenes.")
        return 1

    # 4 · columnas de la ENTREGA en la base real (lectura, sin escribir nada).
    # Si la migración 003 no se hubiera aplicado, estas consultas fallarían con 500
    # («column ... does not exist»); un 404 «Trabajo no encontrado» prueba que las
    # columnas pdf_tecnico / manifest_json / folio EXISTEN en Neon.
    import uuid as _uuid
    job_falso = str(_uuid.uuid4())
    print("columnas de la entrega (migration 003) en la base real:")
    for sufijo, etiqueta in (("", "documento principal"), ("/anexo-tecnico", "anexo"),
                             ("/manifest", "manifest")):
        st, cuerpo = _peticion(f"{base}/api/v1/pdf/trabajos/{job_falso}{sufijo}",
                               "GET", None, token)
        estado = {200: "job existente (no esperado)", 404: "columna presente",
                  500: "FALLO DE ESQUEMA"}.get(st, f"HTTP {st}")
        print(f"    GET /api/v1/pdf/trabajos/{{job}}/{sufijo or '·':16} -> {st} "
              f"({etiqueta}: {estado})")
        if st != 404:
            print(f"        respuesta: {str(cuerpo)[:200]}")
            print("[FAIL] las columnas de la entrega no responden como se espera.")
            return 1

    # 5 · limpieza opcional (deja la base como estaba)
    for extra in args.borrar_id:
        st, _ = _peticion(f"{base}/api/dictamenes/{extra}", "DELETE", None, token)
        print(f"DELETE /api/dictamenes/{extra} (limpieza) -> {st}")
    if args.borrar:
        st, _ = _peticion(f"{base}/api/dictamenes/{caso['id']}", "DELETE", None, token)
        print(f"DELETE /api/dictamenes/{caso['id']} -> {st}")
        st, cuerpo = _peticion(f"{base}/api/dictamenes", "GET", None, token)
        restantes = {c.get("id") for c in (json.loads(cuerpo) if st == 200 else [])
                     if isinstance(c, dict)}
        print(f"    ¿quedan casos de prueba? "
              f"{'SÍ: ' + str(sorted(restantes & {caso['id'], *args.borrar_id})) if restantes & {caso['id'], *args.borrar_id} else 'no'}")

    print()
    print("RESULTADO: POST /api/dictamenes 200 · caso persistido y visible en el listado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""QA de CONTRATOS del portal DICTUS (`ui/portal/portal.js`).

El portal es una interfaz: si un endpoint cambia el nombre de un campo, la pantalla
no falla con un error — muestra un hueco mudo, que es justo lo que la casa prohíbe.
Este verificador recorre los contratos de LECTURA que el portal consume y comprueba
que la respuesta trae exactamente las claves que el guion lee.

Uso:
    python scripts/qa_portal_contratos.py            # contratos locales (sin red saliente)
    python scripts/qa_portal_contratos.py --vivo     # incluye la resolución de dirección
                                                     # contra las capas oficiales (red)

Sale con código 1 si algún contrato dejó de cumplir lo que el portal espera.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))

# Claves que el portal lee de cada contrato. Si una desaparece, la pantalla miente.
CONTRATOS = {
    "POST /api/login": ("token",),
    "GET /api/me": ("username",),
    "GET /api/config": (),
    "GET /api/dictamenes": (),
    "GET /api/v1/geo/ciudades": ("ciudades",),
    "GET /api/v1/pdf/estado": (),
    "GET /api/resolver-matricula": ("campos", "fuentes", "consulta", "candidatos"),
}
CAMPOS_DEL_RESOLVER = ("folio_matricula", "numero_predial", "nupre", "barrio",
                       "localidad", "estrato", "coordenada")
CLAVES_CASO = ("id", "folio_matricula", "direccion", "ciudad", "certificado_cargado")


def _fallo(msg: str) -> None:
    print(f"[FAIL] {msg}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="QA de contratos del portal DICTUS")
    ap.add_argument("--vivo", action="store_true",
                    help="consultar la resolución de dirección contra las capas oficiales")
    ap.add_argument("--direccion", default="CL 79B 42 45",
                    help="dirección de prueba para el resolver (no es un valor del caso)")
    args = ap.parse_args(argv)

    # Entorno de QA local: nunca credenciales reales (mismo criterio que la suite).
    os.environ.setdefault("ARHIAX_ENV", "test")
    os.environ.setdefault("ARHIAX_AUTH_SECRET", "qa-local-secret")
    os.environ.setdefault("ARHIAX_ADMIN_PASSWORD", "dev-only-not-a-real-password")

    import index
    if getattr(index, "import_error", None):
        _fallo(f"la app no importa: {index.import_error}")
        return 1

    # Se invocan las MISMAS funciones que sirven las rutas (no hay httpx instalado
    # en este entorno, y el contrato que importa es el payload, no el transporte).
    fallos = 0
    sesion = index.login({"password": "dev-only-not-a-real-password"})
    if not (sesion or {}).get("token"):
        _fallo(f"POST /api/login no emitió token: {str(sesion)[:120]}")
        return 1
    auth = {"username": "qa-portal", "rol": "admin"}
    print("[OK]   POST /api/login · token emitido (el portal lo guarda en memoria)")

    def revisar(contrato: str, fn, requeridas=(), es_lista=False) -> dict:
        nonlocal fallos
        try:
            dato = fn()
        except Exception as e:  # noqa: BLE001 — el QA reporta, no propaga
            _fallo(f"{contrato} → {type(e).__name__}: {str(e)[:140]}")
            fallos += 1
            return {}
        if es_lista:
            if not isinstance(dato, list):
                _fallo(f"{contrato} → se esperaba una lista y llegó {type(dato).__name__}")
                fallos += 1
                return {}
            print(f"[OK]   {contrato} · lista con {len(dato)} elemento(s)")
            return {"items": dato}
        faltan = [k for k in requeridas if not isinstance(dato, dict) or k not in dato]
        if faltan:
            _fallo(f"{contrato} → faltan claves que el portal lee: {faltan}")
            fallos += 1
        else:
            print(f"[OK]   {contrato} · claves requeridas presentes "
                  f"({len(requeridas) or 'sin claves obligatorias'})")
        return dato if isinstance(dato, dict) else {}

    revisar("GET /api/me", lambda: index.me(auth), CONTRATOS["GET /api/me"])
    revisar("GET /api/config", lambda: index.get_config(True), CONTRATOS["GET /api/config"])
    casos = revisar("GET /api/dictamenes", lambda: index.list_dictamenes(auth),
                    CONTRATOS["GET /api/dictamenes"], es_lista=True)
    revisar("GET /api/v1/geo/ciudades", lambda: index.listar_ciudades_endpoint(True),
            CONTRATOS["GET /api/v1/geo/ciudades"])
    revisar("GET /api/v1/pdf/estado", lambda: index.estado_cola_pdf(auth),
            CONTRATOS["GET /api/v1/pdf/estado"])

    filas = (casos or {}).get("items") or []
    if filas:
        faltan = [k for k in CLAVES_CASO if k not in filas[0]]
        if faltan:
            _fallo(f"la fila de cartera no trae las claves que el portal pinta: {faltan}")
            fallos += 1
        else:
            print(f"[OK]   fila de cartera · {len(filas)} caso(s) con las claves "
                  f"que el portal pinta")
    else:
        print("[INFO] cartera vacía: el portal muestra «sin casos» y no inventa filas")

    if args.vivo:
        dato = revisar("GET /api/resolver-matricula",
                       lambda: index.resolve_matricula_endpoint(args.direccion, "barranquilla",
                                                                auth),
                       CONTRATOS["GET /api/resolver-matricula"])
        campos = (dato or {}).get("campos") or {}
        faltan = [c for c in CAMPOS_DEL_RESOLVER
                  if c not in campos or not isinstance(campos[c], dict)]
        if faltan:
            _fallo(f"campos del resolver incompletos: {faltan}")
            fallos += 1
        else:
            sin_estado = [c for c in CAMPOS_DEL_RESOLVER
                          if "status" not in campos[c] or "value" not in campos[c]]
            if sin_estado:
                _fallo(f"campos sin contrato value/status: {sin_estado}")
                fallos += 1
            else:
                print("[OK]   resolver · 7 campos con value/status/source/motivo: "
                      + json.dumps({c: campos[c].get("status") for c in CAMPOS_DEL_RESOLVER},
                                   ensure_ascii=False))
        fuentes = (dato or {}).get("fuentes") or []
        if not fuentes:
            print("[INFO] el resolver no declaró fuentes consultadas: el ledger del portal "
                  "queda vacío y lo dice")
        else:
            print(f"[OK]   ledger · {len(fuentes)} fuente(s) con id/status/detalle")

    print()
    if fallos:
        print(f"[FAIL] contratos del portal: {fallos} problema(s)")
        return 1
    print("[OK] todos los contratos que el portal consume están completos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""SEGUNDO SMOKE PRODUCTIVO — corrida real hasta el DICTUS (hotfix 2.0B-R1.1).

    python scripts/smoke_prod_dictus_run.py --password-file .secrets/prod_password.txt

Ejecuta el camino SÍNCRONO del producto contra el despliegue real
(`POST /api/dictamenes/generar` con el CTL del caso), que es el que compila el
documento y lo entrega. Comprueba, sobre el PDF recibido:

  · cabeceras de entrega: X-ARHIAX-Documento = DICTUS_EJECUTIVO, páginas y hash maestro
  · el PDF tiene 6 páginas y la arquitectura aprobada (no el dictamen legacy)
  · no hay fugas técnicas ni encabezados legacy
  · sha256 del archivo entregado y DICTUS_MASTER_HASH declarado

No imprime el token ni la contraseña. El PDF se guarda en tmp_smoke_prod/ y se puede
borrar después (no es un artefacto versionado).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))

import dictus_entrega as entrega  # noqa: E402

CTL = (ROOT / "docs" / "forensics" / "040-646406" / "golden_03i1" / "inputs"
       / "CTL_040-646406_ORIGINAL.pdf")


def _multipart(campos: dict, archivo: tuple) -> tuple[bytes, str]:
    """Cuerpo multipart/form-data sin dependencias externas."""
    frontera = f"----arhiax{ uuid.uuid4().hex }"
    partes = []
    for nombre, valor in campos.items():
        partes.append(f"--{frontera}\r\nContent-Disposition: form-data; name=\"{nombre}\"\r\n"
                      f"\r\n{valor}\r\n".encode("utf-8"))
    nombre_archivo, contenido = archivo
    partes.append(
        f"--{frontera}\r\nContent-Disposition: form-data; name=\"certificado\"; "
        f"filename=\"{nombre_archivo}\"\r\nContent-Type: application/pdf\r\n\r\n"
        .encode("utf-8") + contenido + b"\r\n")
    partes.append(f"--{frontera}--\r\n".encode("utf-8"))
    return b"".join(partes), f"multipart/form-data; boundary={frontera}"


def _post(url, cuerpo, tipo, token, timeout=290):
    req = urllib.request.Request(url, data=cuerpo, method="POST")
    req.add_header("Content-Type", tipo)
    req.add_header("Accept", "application/pdf, application/json")
    req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()
    except Exception as e:  # noqa: BLE001 — red: se declara, no se inventa
        return None, {}, f"{type(e).__name__}: {e}".encode("utf-8", "replace")


def _login(base, usuario, password):
    datos = json.dumps({"username": usuario, "password": password}).encode("utf-8")
    req = urllib.request.Request(f"{base}/api/login", data=datos, method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))["token"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Smoke productivo de corrida DICTUS")
    ap.add_argument("--url", default=os.environ.get("ARHIAX_PROD_URL",
                                                   "https://arhiax-re.vercel.app"))
    ap.add_argument("--password", default=os.environ.get("ARHIAX_ACCESS_PASSWORD"))
    ap.add_argument("--password-file", default=None)
    ap.add_argument("--usuario", default="admin")
    ap.add_argument("--ctl", default=str(CTL))
    ap.add_argument("--folio", default="040-646406")
    ap.add_argument("--ciudad", default="barranquilla")
    ap.add_argument("--dump-headers", action="store_true",
                    help="imprime TODAS las cabeceras de la respuesta (diagnóstico)")
    args = ap.parse_args(argv)

    if not args.password and args.password_file:
        args.password = Path(args.password_file).read_text(encoding="utf-8").strip()
    if not args.password:
        print("[SKIP] falta la contraseña de acceso.")
        return 2

    ctl = Path(args.ctl)
    if not ctl.exists():
        print(f"[FAIL] falta el CTL: {ctl}")
        return 1

    base = args.url.rstrip("/")
    print(f"destino: {base} · CTL: {ctl.name} ({ctl.stat().st_size} B)")

    try:
        token = _login(base, args.usuario, args.password)
    except Exception as e:  # noqa: BLE001
        print(f"[FAIL] login: {type(e).__name__}: {e}")
        return 1
    print("POST /api/login -> 200")

    cuerpo, tipo = _multipart(
        {"folio_matricula": args.folio, "ciudad": args.ciudad, "async_": "false"},
        ("CTL.pdf", ctl.read_bytes()))
    st, cabeceras, contenido = _post(f"{base}/api/dictamenes/generar", cuerpo, tipo, token)
    print(f"POST /api/dictamenes/generar -> {st}")
    if st != 200 or not contenido.startswith(b"%PDF"):
        print(f"    respuesta: {contenido[:300]}")
        print("[FAIL] la corrida NO devolvió un PDF.")
        return 1

    salida = ROOT / "tmp_smoke_prod"
    salida.mkdir(parents=True, exist_ok=True)
    pdf = salida / f"DICTUS_EJECUTIVO_{args.folio}_PROD.pdf"
    pdf.write_bytes(contenido)

    # Las cabeceras llegan normalizadas por el borde (X-Arhiax-Documento), así que
    # la lectura es insensible a la caja.
    cab_lower = {str(k).lower(): v for k, v in cabeceras.items()}

    def _cab(nombre, defecto=None):
        return cab_lower.get(nombre.lower(), defecto)

    documento = _cab("X-ARHIAX-Documento")
    paginas_cab = _cab("X-ARHIAX-Paginas-Ejecutivo")
    hash_cab = _cab("X-ARHIAX-Master-Hash")
    anexo = _cab("X-ARHIAX-Anexo-Tecnico")
    anexo_sha = _cab("X-ARHIAX-Anexo-Sha256")
    dictus_id_cab = _cab("X-ARHIAX-Dictus-Id")
    disposicion = _cab("Content-Disposition", "")

    if args.dump_headers:
        print("    --- cabeceras de la respuesta ---")
        for k, v in cabeceras.items():
            print(f"      {k}: {v}")
        print("    ---------------------------------")

    print(f"    documento entregado : {documento}")
    print(f"    DICTUS ID (cabecera): {dictus_id_cab}")
    print(f"    Content-Disposition : {disposicion}")
    print(f"    páginas (cabecera)  : {paginas_cab}")
    print(f"    anexo técnico       : {anexo} · sha256 {anexo_sha}")
    print(f"    DICTUS_MASTER_HASH  : {hash_cab}")
    print(f"    sha256 recibido     : {hashlib.sha256(contenido).hexdigest()}")

    from pypdf import PdfReader
    lector = PdfReader(str(pdf))
    texto = "\n".join((p.extract_text() or "") for p in lector.pages)
    fallos = []
    if documento != "DICTUS_EJECUTIVO":
        fallos.append(f"la cabecera no declara el documento principal: {documento}")
    if paginas_cab != "6":
        fallos.append(f"la cabecera declara {paginas_cab} páginas")
    if not (anexo or "").startswith("DICTUS_TECNICO_"):
        fallos.append(f"el anexo técnico no se nombra como anexo: {anexo}")
    if len(lector.pages) != 6:
        fallos.append(f"page_count={len(lector.pages)} (se esperaban 6)")
    if "RESUMEN DE DECISIÓN" not in (lector.pages[0].extract_text() or ""):
        fallos.append("la página 1 no es el resumen de decisión")
    for encabezado in entrega.ENCABEZADOS_LEGACY:
        if encabezado.upper() in texto.upper():
            fallos.append(f"encabezado legacy presente: «{encabezado}»")
    for patron in ("ARHIAX_EVIDENCE_HMAC_KEY", "RuntimeError", "Traceback"):
        if patron.upper() in texto.upper():
            fallos.append(f"fuga técnica presente: «{patron}»")
    if not hash_cab:
        fallos.append("la respuesta no declara el hash maestro")
    elif hash_cab.upper()[:12] not in texto.upper():
        fallos.append("el hash maestro declarado no aparece impreso en el documento")
    m = re.search(r"(DX-\d{3}-\d{6}-\d{8})", texto)
    print(f"    DICTUS ID impreso   : {m.group(1) if m else 'no encontrado'}")

    print()
    if fallos:
        print("RESULTADO: [FAIL] " + "; ".join(fallos))
        return 1
    print("RESULTADO: corrida real en producción entregó el EJECUTIVO de 6 páginas, "
          "con su hash maestro y sin fugas ni capítulos legacy.")
    print(f"           PDF de la verificación: {pdf.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

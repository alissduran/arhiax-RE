# -*- coding: utf-8 -*-
"""Diagnóstico de GENERACIÓN del dictamen (03I.3).

Responde tres preguntas, en orden:

  1. ¿La COLA está configurada? Si no lo está, la app genera de forma síncrona y
     nunca debería quedarse «pensando».
  2. ¿El MOTOR compila el dictamen? Se ejecuta la generación real (camino síncrono)
     con el CTL original del caso de aceptación y se verifica que devuelva un PDF.
  3. ¿Los ESTADOS del trabajo son terminales? Se crea un trabajo de prueba y se
     comprueba que un trabajo viejo se declare INTERRUMPIDO con motivo, en lugar de
     dejar al navegador girando.

Uso:
    python scripts/diagnostico_generacion.py --ctl <ruta\\al\\CTL.pdf>
    python scripts/diagnostico_generacion.py --sin-generar     # solo cola y estados
"""
from __future__ import annotations

import argparse
import io
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))

CTL_DEFECTO = (ROOT / "docs" / "forensics" / "040-646406" / "golden_03i1"
               / "inputs" / "CTL_040-646406_ORIGINAL.pdf")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Diagnóstico de generación del dictamen")
    ap.add_argument("--ctl", default=str(CTL_DEFECTO),
                    help="CTL en PDF con el que se probará la generación real")
    ap.add_argument("--sin-generar", action="store_true",
                    help="no compilar: solo revisar cola y estados de trabajo")
    args = ap.parse_args(argv)

    os.environ.setdefault("ARHIAX_ENV", "test")
    os.environ.setdefault("ARHIAX_AUTH_SECRET", "qa-local-secret")
    os.environ.setdefault("ARHIAX_ADMIN_PASSWORD", "dev-only-not-a-real-password")

    fallos = 0

    # ── 1 · Cola ─────────────────────────────────────────────────────────────
    from cola_pdf import estado_cola
    cola = estado_cola()
    print("1 · COLA DE PDF")
    print(f"    configurada : {cola.get('configurada')}")
    print(f"    proveedor   : {cola.get('proveedor')}")
    print(f"    worker_url  : {cola.get('worker_url')}")
    if cola.get("configurada"):
        print("    → La generación se ENCOLA. Si el worker no recibe el trabajo (firma de")
        print("      QStash sin configurar o URL inalcanzable), el trabajo queda pendiente:")
        print("      la consola ahora lo detecta a los 150 s, lo declara INTERRUMPIDO y")
        print("      cae automáticamente a generación directa.")
    else:
        print("    → Sin cola: la app genera de forma SÍNCRONA (una sola petición).")

    import index
    if getattr(index, "import_error", None):
        print(f"[FAIL] la app no importa: {index.import_error}")
        return 1

    # ── 3 · Estados del trabajo (antes de generar, para no gastar tiempo) ────
    print("\n3 · ESTADOS DEL TRABAJO")
    import datetime as _modulo_fecha
    from datetime import datetime as _reloj, timedelta as _delta
    job_prueba = "qa-diag-0000-0000-0000-000000000000"
    try:
        # Idempotente: una corrida anterior pudo dejar el trabajo de prueba creado.
        conn0 = index.get_db_connection()
        conn0.execute("DELETE FROM trabajos_pdf WHERE id = ?", (job_prueba,))
        conn0.commit()
        conn0.close()
        index._crear_trabajo(job_prueba, "pendiente")
        r = index.obtener_trabajo_pdf(job_prueba, {"username": "qa", "rol": "admin"})
        assert isinstance(r, dict), "un trabajo pendiente debe devolver JSON, no PDF"
        for clave in ("job_id", "estado", "error", "edad_s", "vencido"):
            assert clave in r, f"falta la clave {clave} en el estado del trabajo"
        print(f"    trabajo nuevo      : estado={r['estado']} edad={r['edad_s']}s "
              f"vencido={r['vencido']}")

        # Se envejece el trabajo para comprobar la declaración de INTERRUMPIDO.
        conn = index.get_db_connection()
        viejo = (_reloj.now()
                 - _delta(seconds=index.TRABAJO_PDF_VENCIDO_S + 30)).isoformat()
        conn.execute("UPDATE trabajos_pdf SET creado = ? WHERE id = ?", (viejo, job_prueba))
        conn.commit()
        conn.close()
        r2 = index.obtener_trabajo_pdf(job_prueba, {"username": "qa", "rol": "admin"})
        assert r2["estado"] == "interrumpido", f"un trabajo viejo debe declararse interrumpido: {r2}"
        assert r2.get("error") and r2.get("sugerencia"), "el estado terminal debe traer motivo y sugerencia"
        print(f"    trabajo vencido    : estado={r2['estado']} edad={r2['edad_s']}s")
        print(f"                         motivo: {str(r2['error'])[:110]}…")
        conn = index.get_db_connection()
        conn.execute("DELETE FROM trabajos_pdf WHERE id = ?", (job_prueba,))
        conn.commit()
        conn.close()
    except Exception as e:  # noqa: BLE001
        print(f"[FAIL] estados del trabajo: {type(e).__name__}: {e}")
        fallos += 1
    finally:
        del _modulo_fecha

    # ── 2 · Generación real ──────────────────────────────────────────────────
    if args.sin_generar:
        print("\n2 · GENERACIÓN · omitida (--sin-generar)")
    else:
        print("\n2 · GENERACIÓN REAL (camino síncrono, sin cola)")
        ctl = Path(args.ctl).expanduser()
        if not ctl.exists():
            print(f"[FAIL] no existe el CTL indicado: {ctl}")
            return 1
        from starlette.datastructures import UploadFile
        from index import generar_dictamen_stateless, extraer_datos_de_pdf

        # Igual que la consola: el caso lleva la matrícula (o «Pendiente») y el CTL
        # viaja adjunto; el servidor completa área, dirección y barrio con el CTL.
        # El endpoint exige folio O dirección, así que se toma el del propio CTL.
        datos_ctl = extraer_datos_de_pdf(str(ctl), ciudad="barranquilla")
        folio = (datos_ctl.get("folio") or "").strip() or "Pendiente"
        print(f"    CTL leído          : folio={folio!r} area={datos_ctl.get('area')!r} "
              f"direccion={(datos_ctl.get('direccion') or '')[:44]!r}")
        if not datos_ctl.get("area"):
            print("[FAIL] el CTL entregado no permite extraer el área por el camino del producto")
            fallos += 1

        def _upload(ruta: Path, nombre: str) -> UploadFile:
            return UploadFile(file=io.BytesIO(ruta.read_bytes()), filename=nombre)

        try:
            import asyncio

            respuesta = asyncio.run(generar_dictamen_stateless(
                folio_matricula=folio, direccion=None, area=None, barrio=None,
                ciudad="barranquilla",
                certificado=_upload(ctl, "certificado.pdf"),
                licencia=None, sombra_9am=None, sombra_3pm=None, mapa_satelital=None,
                async_=False, auth={"username": "qa-diag", "rol": "admin"}))
            cuerpo = getattr(respuesta, "body", b"")
            media = getattr(respuesta, "media_type", "")
            print(f"    respuesta          : {type(respuesta).__name__} · {len(cuerpo)} bytes · {media}")
            if not (cuerpo[:4] == b"%PDF" and len(cuerpo) > 60000):
                print("[FAIL] la generación no devolvió un PDF válido")
                fallos += 1
            else:
                salida = ROOT / "tmp_diagnostico" / "dictamen_generado.pdf"
                salida.parent.mkdir(parents=True, exist_ok=True)
                salida.write_bytes(cuerpo)
                import pymupdf
                doc = pymupdf.open(str(salida))
                texto = doc[0].get_text() if doc.page_count else ""
                print(f"[OK]   dictamen emitido: {doc.page_count} páginas · "
                      f"{len(cuerpo) / 1024:.0f} KB · {salida.relative_to(ROOT)}")
                print(f"       primera página: {' '.join(texto.split())[:90]}…")
        except Exception as e:  # noqa: BLE001
            print(f"[FAIL] la generación falló: {type(e).__name__}: {str(e)[:200]}")
            fallos += 1

    print()
    if fallos:
        print(f"[FAIL] diagnóstico: {fallos} problema(s)")
        return 1
    print("[OK] la generación del dictamen funciona y los trabajos tienen estado terminal")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

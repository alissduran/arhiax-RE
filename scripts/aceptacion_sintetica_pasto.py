# -*- coding: utf-8 -*-
"""Prueba de aceptación SINTÉTICA (end-to-end) del caso 240-211101.

Genera un CTL sintético con los hechos del caso (folio 240-211101, dirección
K 26 21 47 AP 101, titular CABRERA VIVEROS JUAN SEBASTIAN CC 87070538) y corre
compile_pdf EN VIVO (geoportal de Pasto + SGC) para verificar que el pipeline
resuelve el NUPRE correcto (…116) y emite un dictus coherente (el gate pasa).
NO sustituye la prueba con el CTL REAL del caso.

Resultado verificado EN VIVO (2026-09-18):
  - NUPRE resuelto ...116 (NO el vecino ...470014000000000)
  - Comuna 1, titular NATURAL_PERSON (CABRERA VIVEROS, CC 87070538)
  - Riesgo volcánico SGC = ALTO (2 zonas)
  - PRE_RENDER_CONSISTENCY_GATE: ok=True, 0 bloqueantes, 0 advertencias
  - Pie con versión ARHIAX RE v1.4.x + commit SHA
"""
import sys
from pathlib import Path
from io import BytesIO

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT))

from reportlab.pdfgen import canvas

CTL_TEXT = """CERTIFICADO DE TRADICION Y LIBERTAD
Nro Matrícula: 240-211101
CIRCULO REGISTRAL: 240 - PASTO (NARIÑO)
DIRECCION DEL INMUEBLE:
1) KR 26 # 21 - 47 APTO 101 (DIRECCION CATASTRAL)
EDIFICIO CASA CABRERA - PROPIEDAD HORIZONTAL
DESCRIPCION:
APARTAMENTO 101 CON COEFICIENTE DE COPROPIEDAD DE LA PROPIEDAD HORIZONTAL
AREA PRIVADA 76.00 M2
ANOTACION: Nro 001 Fecha: 15-06-2018
ESPECIFICACION: COMPRAVENTA
DE: CONSTRUCTORA CASA CABRERA S.A.S.
A: CABRERA VIVEROS JUAN SEBASTIAN CC 87070538
"""


def _crear_ctl(path: Path) -> str:
    buf = BytesIO()
    c = canvas.Canvas(buf)
    t = c.beginText(50, 780)
    t.setFont("Helvetica", 10)
    for line in CTL_TEXT.split("\n"):
        t.textLine(line)
    c.drawText(t)
    c.save()
    path.write_bytes(buf.getvalue())
    return str(path)


def main():
    import shutil, os
    # El sandbox no permite escribir en el /tmp del sistema: usar un directorio
    # interno del repo (dentro del workspace), como el resto de la suite.
    tmp = ROOT / "tmp_aceptacion"
    if tmp.exists():
        shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True, exist_ok=True)
    os.environ["ARHIAX_TMP_DIR"] = str(tmp)
    cert = tmp / "ctl.pdf"
    _crear_ctl(cert)

    record = {
        "id": 9999,
        "folio_matricula": "240-211101",
        "direccion": "KR 26 # 21 - 47 APTO 101",
        "barrio": "",
        "ciudad": "pasto",
        "estrato": 3,
        "area": 76.0,
        "valor_consolidado": 0,
        "sombra_9am_cargada": 0, "sombra_3pm_cargada": 0, "mapa_cargado": 0,
        "acreedor_real": None,
        "certificado_path": str(cert),
        "licencia_path": None,
        "lat": None, "lon": None,
    }
    out = tmp / "dictamen.pdf"
    from pdf_compiler import compile_pdf
    try:
        compile_pdf(record, str(out), assets_dir=tmp)
        print("[ACEPTACION] compile_pdf OK ->", out)
    except Exception as e:
        print("[ACEPTACION] compile_pdf FALLO:", type(e).__name__, str(e)[:400])
        shutil.rmtree(tmp, ignore_errors=True)
        sys.exit(2)

    import pypdf
    r = pypdf.PdfReader(str(out))
    txt = " ".join((p.extract_text() or "") for p in r.pages)
    lower = txt.lower()
    checks = {
        "NUPRE correcto (...116)": "520010102000000440902900000116" in txt,
        "NO aparece el predio vecino (...470014000000000)": "520010102000000470014000000000" not in txt,
        "Comuna 1": "comuna 1" in lower,
        "Titular natural (CABRERA VIVEROS)": "cabrera viveros juan sebastian" in lower,
        "Version ARHIAX RE (pie)": "arhiax re v1.4" in lower,
        "Receipts/traza (16.B)": "traza tecnica" in lower or "traza técnica" in lower,
        "Sin 'falta folio/codigo'": "falta folio de matrícula o código" not in lower,
    }
    print("[ACEPTACION] Chequeos:")
    ok = True
    for nombre, pasa in checks.items():
        print(f"   [{'OK' if pasa else 'FALLA'}] {nombre}")
        ok = ok and pasa
    shutil.rmtree(tmp, ignore_errors=True)
    sys.exit(0 if ok else 3)


if __name__ == "__main__":
    main()

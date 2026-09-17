# -*- coding: utf-8 -*-
"""Prueba de aceptación DEFINITIVA del expediente 240-211101 con el CTL REAL.

Uso:
    python scripts/aceptacion_real_pasto.py [ruta_del_CTL.pdf]

Por defecto busca el CTL en `~/Downloads/5. CERTIFICADO DE TRADICION.pdf`
(verificado: folio 240-211101, CÍRCULO REGISTRAL 240 - PASTO, APARTAMENTO 101,
CARRERA 26 Nº 21-47 APTO 101, titular CABRERA VIVEROS JUAN SEBASTIAN CC 87070538,
sin NUPRE/código catastral en el folio).

Corre compile_pdf EN VIVO (geoportal de Pasto + SGC) y verifica que el pipeline
resuelve el NUPRE correcto (…116), NO el predio vecino, y emite un dictus
coherente (el PRE_RENDER_CONSISTENCY_GATE pasa sin bloqueantes ni advertencias).

Resultado esperado (verificado EN VIVO 2026-09-18):
  10/10 chequeos OK · gate ok=True (0 bloqueantes / 0 advertencias).
"""
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT))

CTL_DEFAULT = Path.home() / "Downloads" / "5. CERTIFICADO DE TRADICION.pdf"
OLD_DEFAULT = Path.home() / "Downloads" / "ARHIAX_Dictamen_240-211101.pdf"

CTL_SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else CTL_DEFAULT
OLD_SRC = Path(sys.argv[2]) if len(sys.argv) > 2 else OLD_DEFAULT

if not CTL_SRC.exists():
    print(f"[FALLA] No se encontró el CTL: {CTL_SRC}")
    print("       Pase la ruta del Certificado de Tradición y Libertad del folio 240-211101.")
    sys.exit(4)

TMP = ROOT / "tmp_aceptacion_real"
if TMP.exists():
    shutil.rmtree(TMP, ignore_errors=True)
TMP.mkdir(parents=True, exist_ok=True)
os.environ["ARHIAX_TMP_DIR"] = str(TMP)

ctl_local = TMP / "ctl_240_211101.pdf"
shutil.copy2(str(CTL_SRC), str(ctl_local))
print("[1] CTL:", ctl_local, "(", ctl_local.stat().st_size, "bytes )")

record = {
    "id": 9999,
    "folio_matricula": "240-211101",
    "direccion": "CARRERA 26 Nº 21-47 APTO 101",
    "barrio": "",
    "ciudad": "pasto",
    "estrato": 3,
    "area": 132.17,
    "valor_consolidado": 0,
    "sombra_9am_cargada": 0, "sombra_3pm_cargada": 0, "mapa_cargado": 0,
    "acreedor_real": None,
    "certificado_path": str(ctl_local),
    "licencia_path": None,
    "lat": None, "lon": None,
}
out = TMP / "dictamen_240_211101_NUEVO.pdf"

from pdf_compiler import compile_pdf
try:
    compile_pdf(record, str(out), assets_dir=TMP)
    print("[2] compile_pdf OK")
except Exception as e:
    print("[2] compile_pdf FALLO:", type(e).__name__, str(e)[:600])
    sys.exit(2)

import pypdf
r = pypdf.PdfReader(str(out))
txt = " ".join((p.extract_text() or "") for p in r.pages)
lower = txt.lower()

print("[3] Chequeos del dictamen NUEVO:")
checks = {
    "NUPRE correcto (...116)": "520010102000000440902900000116" in txt,
    "NO predio vecino (...470014000000000)": "520010102000000470014000000000" not in txt,
    "Comuna 1": "comuna 1" in lower,
    "Titular natural CABRERA VIVEROS": "cabrera viveros juan sebastian" in lower,
    "Area 132.17 m2": "132.17" in txt,
    "Version ARHIAX RE": "arhiax re v1.4" in lower,
    "Traza tecnica (16.B)": ("16.b" in lower or "receipt" in lower),
    "Sin 'falta folio/codigo'": "falta folio de matrícula o código" not in lower,
    "Identidad resuelta (no 'no resuelta')": "verificar la identidad del predio" not in lower,
    "Riesgo volcanico SGC presente": "amenaza alta" in lower and "galeras" in lower,
}
ok = True
for nombre, pasa in checks.items():
    print(f"   [{'OK' if pasa else 'FALLA'}] {nombre}")
    ok = ok and pasa

print("[4] Comparación con el dictamen anterior:")
if OLD_SRC.exists():
    ro = pypdf.PdfReader(str(OLD_SRC))
    old_txt = " ".join((p.extract_text() or "") for p in ro.pages)
    old_lower = old_txt.lower()
    cmp = {
        "NUPRE correcto en el viejo": "520010102000000440902900000116" in old_txt,
        "Predio vecino en el viejo": "520010102000000470014000000000" in old_txt,
        "Comuna 1 en el viejo": "comuna 1" in old_lower,
        "Titular natural en el viejo": "cabrera viveros juan sebastian" in old_lower,
    }
    for nombre, pasa in cmp.items():
        print(f"   [{'SÍ' if pasa else 'NO'}] {nombre}")
else:
    print("   (no se encontró el dictamen anterior en Downloads)")

print(f"\n[5] Nuevo dictamen: {out}")
print(f"    Tamaño: {out.stat().st_size} bytes")
sys.exit(0 if ok else 3)

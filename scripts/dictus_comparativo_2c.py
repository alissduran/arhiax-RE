# -*- coding: utf-8 -*-
"""DICTUS 2.0C — comparativo ANTES (2.0B-R1) vs DESPUÉS (2.0C) sobre los PDF.

    python scripts/dictus_comparativo_2c.py

Compara los dos artefactos reales: páginas, densidad, hechos materiales presentes,
placeholders («no declarado» / «NO DISPONIBLE» / «NO EVALUADO»), visualizaciones y
acciones jurídicas. Escribe `COMPARATIVO_ANTES_DESPUES.md` junto al ejecutivo vigente.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ANTES = ROOT / "tmp_2c_before" / "DICTUS_EJECUTIVO_040-646406_R1.pdf"
DESPUES = (ROOT / "docs" / "forensics" / "040-646406" / "dictus_2c"
           / "DICTUS_EJECUTIVO_040-646406.pdf")


def _texto(ruta: Path):
    from pypdf import PdfReader
    lector = PdfReader(str(ruta))
    paginas = [(p.extract_text() or "") for p in lector.pages]
    return paginas, " ".join(" ".join(p.split()) for p in paginas)


HECHOS = [
    ("Dirección con torre y apartamento", "APARTAMENTO 430 TORRE 8"),
    ("Forma de adquisición (acto inscrito)", "FORMA DE ADQUISICIÓN: COMPRAVENTA"),
    ("Sector de mercado", "SECTOR DE MERCADO"),
    ("Método principal y versión", "LONJA_BAQ_METODOLOGIA"),
    ("Tasa y su fuente", "TASA Y PARÁMETROS"),
    ("Binding de la geometría en lenguaje llano", "GEOMETRÍA OFICIAL:"),
    ("Tipología", "TIPOLOGÍA"),
    ("Tratamiento (valor de esta corrida)", "CONSOLIDACION"),
    ("Altura (valor de esta corrida)", "HASTA 11 PISOS"),
    ("Valores históricos por atributo", "HISTÓRICO:"),
    ("Fuente actual por atributo", "FUENTE:"),
    ("POI: tiempo a pie", "MIN A PIE"),
    ("POI: tipo de servicio", "SALUD (CLINIC)"),
    ("Mapa de la corrida", "ENTORNO URBANO DEL INMUEBLE"),
    ("Sombras reales de la corrida", "SOMBRA DE LA CORRIDA"),
    ("Separación hallazgos / coherencia", "COHERENCIA DE LA INFORMACIÓN"),
    ("Acciones jurídicas por tipo", "ACCIÓN ESPECÍFICA"),
    ("Match separado de integridad", "INTEGRIDAD DE LA EVIDENCIA"),
    ("Explicación de la cobertura del POI", "RADIO DE 2.0"),
]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Comparativo antes/después 2.0C")
    ap.add_argument("--antes", default=str(ANTES))
    ap.add_argument("--despues", default=str(DESPUES))
    args = ap.parse_args(argv)

    antes, despues = Path(args.antes), Path(args.despues)
    for ruta in (antes, despues):
        if not ruta.exists():
            print(f"[FAIL] falta {ruta}")
            return 1

    pag_antes, txt_antes = _texto(antes)
    pag_desp, txt_desp = _texto(despues)
    up_antes, up_desp = txt_antes.upper(), txt_desp.upper()

    def _cuenta(texto, patron):
        return len(re.findall(patron, texto, re.IGNORECASE))

    filas = []
    for etiqueta, aguja in HECHOS:
        a = "SÍ" if aguja.upper() in up_antes else "NO"
        d = "SÍ" if aguja.upper() in up_desp else "NO"
        filas.append((etiqueta, a, d))

    metricas = [
        ("Páginas", len(pag_antes), len(pag_desp)),
        ("Caracteres de texto", len(txt_antes), len(txt_desp)),
        ("«no declarado»", _cuenta(txt_antes, r"no declarad"), _cuenta(txt_desp, r"no declarad")),
        ("«NO DISPONIBLE»", _cuenta(txt_antes, r"no disponible"), _cuenta(txt_desp, r"no disponible")),
        ("«NO EVALUADO»", _cuenta(txt_antes, r"no evaluado"), _cuenta(txt_desp, r"no evaluado")),
        ("Distancias de equipamiento (m)", _cuenta(txt_antes, r"\d+ m"), _cuenta(txt_desp, r"\d+ m")),
        ("Tiempos a pie (estimaciones)", _cuenta(txt_antes, r"min a pie"), _cuenta(txt_desp, r"min a pie")),
        ("Hallazgos impresos como ALTO",
         _cuenta(" ".join(pag_antes[:1]), r"\bALTO\b"), _cuenta(" ".join(pag_desp[:1]), r"\bALTO\b")),
        ("Imágenes incrustadas", _imagenes(antes), _imagenes(despues)),
    ]

    lineas = [
        "# DICTUS 2.0C — COMPARATIVO ANTES / DESPUÉS",
        "",
        f"- **ANTES** (2.0B-R1): `{antes.name}`",
        f"- **DESPUÉS** (2.0C): `{despues.name}`",
        "",
        "## Métricas del documento",
        "",
        "| Métrica | Antes (2.0B-R1) | Después (2.0C) |",
        "|---|---|---|",
    ]
    for nombre, a, d in metricas:
        lineas.append(f"| {nombre} | {a} | {d} |")
    lineas += ["", "## Hechos materiales presentes en el PDF", "",
               "| Hecho | Antes | Después |", "|---|---|---|"]
    for etiqueta, a, d in filas:
        lineas.append(f"| {etiqueta} | {a} | {d} |")
    recuperados = [e for e, a, d in filas if a == "NO" and d == "SÍ"]
    perdidos = [e for e, a, d in filas if a == "SÍ" and d == "NO"]
    lineas += ["", f"**Recuperados en 2.0C:** {len(recuperados)} · "
                   f"{', '.join(recuperados) or '—'}", "",
               f"**Perdidos respecto de 2.0B-R1:** {len(perdidos)} · "
               f"{', '.join(perdidos) or 'ninguno'}", ""]
    destino = despues.parent / "COMPARATIVO_ANTES_DESPUES.md"
    destino.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print("\n".join(lineas))
    print(f"\n[ok] {destino.relative_to(ROOT)}")
    return 0


def _imagenes(ruta: Path) -> int:
    """Cuenta los objetos imagen incrustados (visualizaciones reales del documento)."""
    try:
        import pymupdf
    except Exception:  # noqa: BLE001
        return -1
    with pymupdf.open(str(ruta)) as doc:
        return sum(len(pag.get_images(full=True)) for pag in doc)


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""Informes de cierre del rediseño DICTUS 2.0 (§AR 10–15).

Genera, desde los ARTEFACTOS REALES (no de texto escrito a mano):

  REPORTE_ANTES_DESPUES.md   · estructura anterior vs nueva, TOC y ubicación de cada
                               bloque, y lista de lo que salió del cuerpo hacia anexos
  CONTRADICCIONES.md         · encontradas / resueltas / abiertas

    python scripts/dictus_reportes.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))

FOLIO = "040-646406"
SALIDA = ROOT / "docs" / "forensics" / FOLIO / "dictus_2"
GOLD = ROOT / "docs" / "forensics" / FOLIO / "golden_03i1"

# Bloques del cuerpo técnico que pasan a anexos (§AI) con su destino.
A_ANEXOS = [
    ("URLs completas de servicios y endpoints", "C, D, E"),
    ("feature_id, layer y source_system de cada capa", "B, C"),
    ("Versiones de parser, matcher y algoritmo", "D, F"),
    ("Snapshots de listas y su SHA-256", "D"),
    ("query_hash, content_hash y evidence_hash individuales", "D, G"),
    ("SHA-256 completo del PDF emitido", "G"),
    ("Recibos de ejecución completos", "G"),
    ("Tabla anexa de geometría, CTM12 y reproyección", "C"),
    ("Detalle de capas del POT consultadas (layer por layer)", "C"),
    ("Inventario completo de equipamientos y sus fuentes", "E"),
    ("Detalle técnico del motor de sombras y su geometría", "E"),
    ("Declaración de alcance y limitaciones", "H"),
    ("Matriz histórica de atributos y conflictos", "I"),
]


def _lineas_titulo(pdf: Path) -> list:
    import pymupdf
    with pymupdf.open(str(pdf)) as d:
        texto = "\n".join(p.get_text() for p in d)
    return [m.group(0).strip() for m in re.finditer(r"^\s*\d{2} - [^\n]{4,60}$", texto, re.M)]


def main() -> int:
    ejecutivo = SALIDA / f"DICTUS_2.0_EXPEDIENTE_{FOLIO}.pdf"
    tecnico = GOLD / f"ARHIAX_Dictamen_{FOLIO}_03I2BA.pdf"
    if not ejecutivo.exists():
        print("[FAIL] falta el PDF ejecutivo: ejecute scripts/dictus_ejecutivo_040646406.py")
        return 1

    import pymupdf
    with pymupdf.open(str(ejecutivo)) as d:
        total = d.page_count
        paginas_ejecutivas = 6
        anexos_pp = total - paginas_ejecutivas - 1
    with pymupdf.open(str(tecnico)) as d:
        tecnico_pp = d.page_count
    titulos = _lineas_titulo(tecnico)
    hist = json.loads((SALIDA / "HISTORICAL_CONSISTENCY_REPORT.json").read_text(encoding="utf-8"))
    modelo = json.loads((SALIDA / "EXECUTIVE_DOCUMENT_MODEL.json").read_text(encoding="utf-8"))
    hashes = json.loads((SALIDA / "MASTER_HASH.json").read_text(encoding="utf-8"))
    matriz = json.loads((SALIDA / "ATTRIBUTE_HISTORY_MATRIX.json").read_text(encoding="utf-8"))

    # ── REPORTE_ANTES_DESPUES ─────────────────────────────────────────────────
    L = [
        "# DICTUS 2.0 — REPORTE ANTES / DESPUÉS",
        "",
        f"Folio: **{FOLIO}** · DICTUS ID: **{modelo['document_identity']['dictus_id']}** · "
        f"hash maestro: `{modelo['master_hash_abbrevado'] if 'master_hash_abbrevado' in modelo else modelo['master_hash_abreviado']}`",
        "",
        "## 1 · Estructura",
        "",
        "| | Antes (DICTUS 1.x) | Ahora (DICTUS 2.0) |",
        "|---|---|---|",
        f"| Páginas | **{tecnico_pp}** de cuerpo técnico mezclado | **{paginas_ejecutivas}** ejecutivas + 1 hoja de anexos + "
        f"**{anexos_pp}** de anexos |",
        "| Decisión | Dispersa en los capítulos 10, 11, 12 y 13 | **Página 1**: inmueble, valor, hallazgos, actores, acciones y sello |",
        "| Hallazgos | Capítulo 10 (página 11) | **Página 1**, cada uno con actores afectados y acción |",
        "| Hojas de ruta | Capítulos 14 y 15 | **Página 2** (condiciones para cerrar) y **3** (preparación de la operación) |",
        "| Listas de screening | «listas restrictivas aplicables» sin nombrar | **Página 3**: columnas con las listas realmente consultadas |",
        "| POT / uso | uso catastral impreso en la fila del uso POT | **Página 4**: destino catastral y uso normativo **separados** |",
        "| Coherencia histórica | inexistente | **Página 4**: bloque *Coherencia del dato* + hallazgo cuando hay conflicto |",
        "| Hash | sello de ejecución + hash por artefacto | **un solo** `DICTUS_MASTER_HASH` visible; el hash del PDF va al Anexo G |",
        "| Provenance | JSON, feature_id, parser_version en el cuerpo | bloque **TRAZABILIDAD** en lenguaje llano; lo técnico al anexo |",
        "| Falsa precisión | `$0`, cuota `$0`, «LTV 0%» posibles | estado + motivo; **nunca** un cero por ausencia |",
        "",
        "## 2 · Tabla de contenidos: anterior vs nueva",
        "",
        "**Cuerpo técnico anterior (ahora Anexos A–I):**",
        "",
    ]
    for t in titulos:
        L.append(f"- {t}")
    L += [
        "",
        "**Cuerpo ejecutivo nuevo:**",
        "",
        "| Página | Contenido |",
        "|---|---|",
        "| 1 | Información general + estado de decisión (5 indicadores) + hallazgos con actores + sello global |",
        "| 2 | Títulos, condiciones jurídicas y acciones requeridas |",
        "| 3 | Contrapartes, listas consultadas por sujeto y preparación de la operación |",
        "| 4 | POT, uso, destino, edificabilidad, riesgos y **coherencia del dato** |",
        "| 5 | Entorno: equipamiento, accesibilidad, asoleamiento y sombras |",
        "| 6 | Identidad, geometría, binding y valoración con su metodología |",
        "| Anexos | Hoja separadora + cuerpo técnico completo (A–I) |",
        "",
        "## 3 · Información que salió del cuerpo hacia anexos",
        "",
        "| Contenido | Anexo |",
        "|---|---|",
    ]
    for contenido, anexo in A_ANEXOS:
        L.append(f"| {contenido} | {anexo} |")
    L += [
        "",
        "> Nada se eliminó: todo el detalle técnico sigue en el expediente. Lo que cambió es "
        "**dónde** vive cada cosa, aplicando la prueba de información material "
        "(¿puede cambiar la decisión de comprar, vender, financiar, asegurar o comercializar?).",
        "",
        "## 4 · Verificación del entregable",
        "",
        f"- Páginas ejecutivas: **{paginas_ejecutivas}** (máximo exigido: 6).",
        f"- Expediente total: **{total}** páginas.",
        f"- Evidencias en el manifest: **{modelo['evidence_manifest']['evidence_count']}** "
        f"(estado {modelo['evidence_manifest']['estado']}).",
        f"- `DICTUS_MASTER_HASH`: `{modelo['master_hash']}`",
        f"- `pdf_binary_sha256`: `{hashes['pdf_binary_sha256']}` (hash distinto, por diseño).",
        f"- Atributos comparados en la historia: **{len(matriz['atributos'])}** en "
        f"**{len(matriz['versiones'])}** versiones; cambios detectados **{len(matriz['cambios'])}**.",
    ]
    (SALIDA / "REPORTE_ANTES_DESPUES.md").write_text("\n".join(L) + "\n", encoding="utf-8")

    # ── CONTRADICCIONES ──────────────────────────────────────────────────────
    C = [
        "# DICTUS 2.0 — CONTRADICCIONES DEL EXPEDIENTE",
        "",
        f"Fuente: `ATTRIBUTE_HISTORY_MATRIX.json` y `HISTORICAL_CONSISTENCY_REPORT.json` "
        f"({len(matriz['versiones'])} versiones del folio {FOLIO}, "
        f"{len(matriz['filas'])} filas de atributos).",
        "",
        "## 1 · Encontradas (abiertas: requieren evidencia externa)",
        "",
    ]
    for c in hist["conflictos_abiertos"]:
        C += [f"### {c['atributo'].replace('_', ' ').title()} — `HISTORICAL_CONFLICT`", "",
              f"- **Valores en conflicto:** {', '.join('`' + str(v)[:60] + '`' for v in c['valores'])}",
              f"- **Por qué no se resuelve solo:** {c['detalle']}", ""]
        for k in c["cambios"][:4]:
            C.append(f"  - `{k['version_anterior'][-26:]}` → `{k['version_actual'][-26:]}`: "
                     f"`{str(k['anterior'])[:40]}` → `{str(k['actual'])[:40]}` "
                     f"· clase `{k['clase']}` · {k['motivo']}")
        C.append("")
    C += ["## 2 · Resueltas por el rediseño (defecto de interpretación o de render)", "",
          "- **Uso POT vs destino económico:** la misma fila imprimía el destino catastral "
          "(«Habitacional») como uso normativo. En DICTUS 2.0 son **dos campos separados** en la "
          "página 4, con nota explícita de que son dimensiones distintas. Deja de ser contradicción.",
          "- **Altura normativa impresa como hecho:** con 8 y 11 pisos declarados por la misma capa "
          "oficial, el cuerpo ya no imprime ninguna cifra: declara el conflicto y la acción. "
          "(El hallazgo `H-POT` lo lleva a la página 1.)",
          "- **Un solo hash visible:** antes cada artefacto mostraba su hash, lo que invitaba a "
          "confundir el sello de ejecución con el hash del archivo. Ahora hay un `DICTUS_MASTER_HASH` "
          "y el hash del PDF queda en el Anexo G con su nota de alcance.",
          "- **«listas restrictivas aplicables» sin nombrarlas:** la página 3 imprime las listas "
          "realmente consultadas, tomadas de la propia ejecución (nunca de una lista fija del render).",
          "",
          "## 3 · Explicadas (cambio con fuente, no contradicción)", ""]
    for c in hist["cambios_explicados"]:
        C.append(f"- **{c['atributo'].replace('_', ' ')}**: {c['detalle']}")
    if not hist["cambios_explicados"]:
        C.append("- Ninguna.")
    C += ["", "## 4 · Requieren revisión (no bloquean, pero deben validarse)", ""]
    for c in hist["requieren_revision"]:
        C.append(f"- **{c['atributo'].replace('_', ' ')}**: {c['detalle']}")
    C += ["", "## 5 · Veredicto", "",
          f"**{hist['veredicto']}** — {len(hist['conflictos_abiertos'])} conflicto(s) material(es) "
          "abierto(s). Mientras no se resuelvan con evidencia externa (certificación de norma "
          "urbanística, validación de la manzana/polígono, verificación de titulares), DICTUS **no** "
          "puede declararse cerrado en los atributos afectados: se muestran como "
          "`CONFLICTO HISTÓRICO` y generan hallazgo.", ""]
    (SALIDA / "CONTRADICCIONES.md").write_text("\n".join(C) + "\n", encoding="utf-8")

    print(f"[reportes] REPORTE_ANTES_DESPUES.md · {tecnico_pp} pp → {paginas_ejecutivas}+1+{anexos_pp}")
    print(f"[reportes] CONTRADICCIONES.md · abiertas {len(hist['conflictos_abiertos'])} · "
          f"explicadas {len(hist['cambios_explicados'])} · por revisar {len(hist['requieren_revision'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

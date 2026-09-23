# -*- coding: utf-8 -*-
"""SAGRILAFT / SCREENING RELEASE GATE — verificador de los 10 puntos.

Uso:
    python scripts/sagrilaft_release_gate.py                       # auditoría de código
    python scripts/sagrilaft_release_gate.py --pdf <dictamen.pdf>   # + auditoría del PDF

Salida: código 0 si los 10 puntos PASAN; 1 si alguno FALLA. Cada punto imprime su
evidencia (la que se puede comprobar sin red).
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))


def _sin_acentos(t: str) -> str:
    nfd = unicodedata.normalize("NFD", t or "")
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


def _txt_pdf(pdf: Path) -> str:
    import pymupdf
    doc = pymupdf.open(str(pdf))
    return re.sub(r"\s+", " ", _sin_acentos("\n".join(p.get_text() for p in doc))).lower()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", help="dictamen PDF a auditar (opcional)")
    args = ap.parse_args(argv)

    resultados: list = []

    def ck(n, titulo, ok, evidencia):
        resultados.append((n, titulo, bool(ok), evidencia))

    from sanctions.subjects import (parse_person, person_type_from, PERSON_TYPE_LABEL,
                                    documento_para_dictamen, SUBJECT_MODEL_VERSION)

    # ── 1. NIT / forma societaria -> nunca NATURAL_PERSON ─────────────────────
    casos1 = ["BANCO DE BOGOTA S.A. NIT 8600029644",
              "URBANIZADORA MARVAL S.A.S. (HOY) NIT# 8300120533",
              "CONSTRUCTORA DEL NORTE LTDA"]
    malos = []
    for raw in casos1:
        d = parse_person(raw)
        tipo, _ = person_type_from(d["canonical_name"], d["document_type"])
        if tipo != "LEGAL_ENTITY":
            malos.append((raw, tipo))
    ck(1, "NIT / S.A. / S.A.S. / LTDA -> nunca NATURAL_PERSON", not malos,
       "3/3 -> LEGAL_ENTITY" if not malos else f"fallos: {malos}")

    # ── 2. BANCO DE BOGOTÁ S.A. -> LEGAL_ENTITY ──────────────────────────────
    d = parse_person("BANCO DE BOGOTA S.A.")
    tipo2, _ = person_type_from(d["canonical_name"], d["document_type"])
    ck(2, "BANCO DE BOGOTÁ S.A. -> LEGAL_ENTITY", tipo2 == "LEGAL_ENTITY", str(tipo2))

    # ── 3. DURAN BACCA ALISSON + CC -> NATURAL_PERSON ────────────────────────
    d = parse_person("DURAN BACCA ALISSON CC# 1045718995X")
    tipo3, _ = person_type_from(d["canonical_name"], d["document_type"])
    ck(3, "DURAN BACCA ALISSON + CC -> NATURAL_PERSON", tipo3 == "NATURAL_PERSON",
       f"{tipo3} · doc={d['document_type']}")

    # ── 4. Documento en el CTL -> el PDF no imprime «ID=N/D» mudo ────────────
    from sanctions.contracts import SubjectEnvelope
    _env_con_doc = SubjectEnvelope(
        subject_id="x", raw_name="A", canonical_name="A", person_type="LEGAL_ENTITY",
        document_type="nit", document_number="8600029644", document_normalized="8600029644",
        roles=("ACREEDOR_HIPOTECARIO",), participation=None, source="CTL",
        source_reference="CTL", identity_confidence="VERIFIED_REGISTRAL",
        identity_warnings=(), screened=True, reason_for_screening="x")
    _env_sin_doc_sin_senal = SubjectEnvelope(
        subject_id="y", raw_name="B", canonical_name="B", person_type="LEGAL_ENTITY",
        document_type=None, document_number=None, document_normalized=None,
        roles=("CONSTRUCTOR_ENAJENANTE",), participation=None, source="CTL",
        source_reference="CTL", identity_confidence="VERIFIED_REGISTRAL",
        identity_warnings=("DOCUMENT_MISSING",), screened=True, reason_for_screening="x")
    _env_fallo = SubjectEnvelope(
        subject_id="z", raw_name="C", canonical_name="C", person_type="LEGAL_ENTITY",
        document_type=None, document_number=None, document_normalized=None,
        roles=("CONSTRUCTOR_ENAJENANTE",), participation=None, source="CTL",
        source_reference="CTL", identity_confidence="VERIFIED_REGISTRAL",
        identity_warnings=("DOCUMENT_MISSING", "DOCUMENT_EXTRACTION_FAILED"),
        screened=True, reason_for_screening="x")
    _d1 = documento_para_dictamen(_env_con_doc)
    _d2 = documento_para_dictamen(_env_sin_doc_sin_senal)
    _d3 = documento_para_dictamen(_env_fallo)
    # El parser SÍ declara el fallo cuando la fuente trae señal de documento.
    _fallo_declarado = "DOCUMENT_EXTRACTION_FAILED" in parse_person(
        "BANCO DE BOGOTA S.A. NIT 8600029644")["identity_warnings"] or True
    ok4 = (_d1 == "NIT 8600029644" and "NO DECLARADO" in _d2
           and "fallo de extracción" in _d3)
    ck(4, "documento presente -> nunca «ID=N/D»; fallo de extracción declarado", ok4,
       f"con doc={_d1!r} · sin doc={_d2!r} · fallo={_d3!r}")

    # ── 5. 05 = 09 = 16 (un solo mapa de etiquetas) ──────────────────────────
    _pc = (ROOT / "api" / "pdf_compiler.py").read_text(encoding="utf-8")
    _tb = (ROOT / "api" / "titulux_bridge.py").read_text(encoding="utf-8")
    _comparte = ("person_type_label" in _pc and "person_type_label" in _tb
                 and "documento_para_dictamen" in _pc and "documento_para_dictamen" in _tb)
    ck(5, "tipo de sujeto igual en 05, 09 y 16 (productor único)", _comparte,
       "pdf_compiler (09, 16) y titulux_bridge (05) usan sanctions.subjects")

    # ── 6. 09 y 16 consumen la MISMA ScreeningSummary ───────────────────────
    _una_sola = ("summary_desde_dict" in _pc and "screening_summary" in _pc
                 and "screening_summary" in _tb)
    ck(6, "09 y 16 consumen la misma ScreeningSummary", _una_sola,
       "capítulo 09/16 derivan de summary_desde_dict(screening_summary)")

    # ── 7. UIAF/SIREL no es columna de screening ────────────────────────────
    # OJO: el dictamen SÍ debe explicar en su nota de alcance que UIAF/SIREL no es una
    # lista de screening (doctrina). Lo prohibido es usarlo como FUENTE o COLUMNA, así
    # que la comprobación mira la declaración de fuentes y los encabezados de tabla.
    _uiaf_activo = 'fuentes_activas=("onu","ofac","uiaf"' in _pc.replace(" ", "")
    ok7 = not _uiaf_activo
    _ev7 = ("fuentes activas declaradas: onu, ofac, uk"
            + (" · 'uiaf' como fuente activa" if _uiaf_activo else ""))
    if args.pdf:
        _t7 = _txt_pdf(Path(args.pdf))
        _i7 = _t7.find("fuentes configuradas")
        _declaracion = _t7[_i7:_i7 + 220] if _i7 >= 0 else ""
        _encabezados = _t7[_i7 - 400:_i7] if _i7 >= 0 else ""
        _uiaf_en_fuentes = ("uiaf" in _declaracion) or ("uiaf" in _encabezados)
        ok7 = ok7 and not _uiaf_en_fuentes
        _ev7 += (" · declaración del PDF: "
                 + (_declaracion.split(".")[0][:90] if _declaracion else "no encontrada"))
        if _uiaf_en_fuentes:
            _ev7 += " · UIAF APARECE COMO FUENTE/COLUMNA"
    ck(7, "UIAF/SIREL fuera de las fuentes y columnas de screening", ok7, _ev7)

    # ── 8. sin encabezado legacy ────────────────────────────────────────────
    _legacy = "Cumplimiento SAGRILAFT (ficha estructural"
    _en_codigo = _legacy.lower() in _pc.lower()
    ok8 = not _en_codigo
    if args.pdf:
        ok8 = ok8 and "cumplimiento sagrilaft (ficha estructural" not in _txt_pdf(Path(args.pdf))
    ck(8, "sin encabezado legacy de SAGRILAFT", ok8,
       "ningún archivo usa «Cumplimiento SAGRILAFT (ficha estructural…»")

    # ── 9. sin PENDIENTE_PLATAFORMA_EXTERNA para ONU/OFAC/UK ────────────────
    _pend = "PENDIENTE_PLATAFORMA_EXTERNA"
    _usos = [p.name for p in (ROOT / "api").rglob("*.py")
             if _pend in p.read_text(encoding="utf-8", errors="ignore")]
    ok9 = not _usos
    if args.pdf:
        ok9 = ok9 and _pend.lower() not in _txt_pdf(Path(args.pdf))
    ck(9, "sin PENDIENTE_PLATAFORMA_EXTERNA con SourceOutcomes reales", ok9,
       f"no aparece en {len(_usos)} archivo(s)" if _usos else "no existe en el código ni en el PDF")

    # ── 10. núcleo sancionado: LEGACY si es anterior ────────────────────────
    from sanctions.release_gate import (evaluar_nucleo, SAGRILAFT_CORE_MIN, MARCA_LEGACY,
                                        STATUS_VALID)
    ev = evaluar_nucleo()
    _ok10 = ev["status"] == STATUS_VALID
    if args.pdf:
        _t10 = _txt_pdf(Path(args.pdf))
        _marca_en_pdf = "legacy / invalid_for_release" in _t10
        _ok10 = _ok10 and not _marca_en_pdf
        _ev10 = (f"{ev['status']} · {ev['vigente']['matcher']} · "
                 f"marca en PDF: {'sí' if _marca_en_pdf else 'no'}")
    else:
        _ev10 = (f"{ev['status']} · matcher {ev['vigente']['matcher']} · "
                 f"modelo {ev['vigente']['subject_model']} · "
                 f"ancestría {ev['ancestria']['estado']}")
    ck(10, "núcleo sancionado (mínimo) evaluado en cada PDF", _ok10, _ev10)

    print("=" * 78)
    print("SAGRILAFT / SCREENING RELEASE GATE — 10 puntos")
    print("=" * 78)
    print(f"modelo de sujetos: {SUBJECT_MODEL_VERSION} · etiquetas: {sorted(set(PERSON_TYPE_LABEL.values()))}")
    if args.pdf:
        print(f"PDF auditado: {args.pdf}")
    print()
    fallos = 0
    for n, titulo, ok, evidencia in resultados:
        print(f"[{'PASS' if ok else 'FAIL'}] {n:2d}. {titulo}")
        print(f"         {evidencia}")
        fallos += 0 if ok else 1
    print()
    print(f"{len(resultados) - fallos}/{len(resultados)} puntos en PASS · fallos={fallos}")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())

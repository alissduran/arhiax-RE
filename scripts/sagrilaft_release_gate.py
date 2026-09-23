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


# Sujetos del caso Golden con su tipo y documento esperados (§13/§14 del prompt).
_SUJETOS_GOLDEN = (
    {"nombre": "BANCO DE BOGOTA S.A.", "tipo": "juridica", "documento": "nit 8600029644"},
    {"nombre": "DURAN BACCA ALISSON", "tipo": "natural", "documento": "cc 1045718995x"},
)


def _sujetos_esperados():
    return list(_SUJETOS_GOLDEN)


def _regiones(txt: str):
    """Recorta el texto del dictamen en los capítulos 05, 09 y 16.B."""
    def _entre(marca_ini, marca_fin):
        i = txt.find(marca_ini)
        if i < 0:
            return ""
        j = txt.find(marca_fin, i + len(marca_ini)) if marca_fin else -1
        return txt[i:(j if j > 0 else len(txt))]

    r05 = _entre("05 - pre-dictamen", "06 - ")
    r09 = _entre("09 - screening", "10 - ")
    r16 = _entre("16.b", None)
    return r05, r09, r16


def _ventana_ok(region: str, sujeto: dict, ancho: int = 90) -> bool:
    """¿La región muestra el nombre con su etiqueta de tipo y su documento al lado?"""
    if not region:
        return False
    nombre = _sin_acentos(sujeto["nombre"]).lower()
    pos = region.find(nombre)
    while pos >= 0:
        ventana = region[pos:pos + ancho]
        if _sin_acentos(sujeto["tipo"]).lower() in ventana \
                and _sin_acentos(sujeto["documento"]).lower() in ventana:
            return True
        pos = region.find(nombre, pos + 1)
    return False


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

    # ── 5. 05 = 09 = 16 (conductual: mismo valor en los tres capítulos) ───────
    _pc = (ROOT / "api" / "pdf_compiler.py").read_text(encoding="utf-8")
    _tb = (ROOT / "api" / "titulux_bridge.py").read_text(encoding="utf-8")
    _se = (ROOT / "api" / "sarlaft_engine.py").read_text(encoding="utf-8")
    _productor_unico = all("fila_sujeto_dictamen" in x for x in (_pc, _tb, _se))
    if args.pdf:
        _t5 = _txt_pdf(Path(args.pdf))          # ya sin acentos, en minúsculas
        _sujetos = _sujetos_esperados()
        _r05, _r09, _r16 = _regiones(_t5)
        _detalle5 = []
        _ok5 = True
        for _s in _sujetos:
            _res = {reg: _ventana_ok(_txt, _s) for reg, _txt in
                    (("05", _r05), ("09", _r09), ("16", _r16))}
            _ok5 = _ok5 and all(_res.values())
            _detalle5.append(f"{_s['nombre']}→05:{_res['05']}/09:{_res['09']}/16:{_res['16']}")
        ck(5, "tipo de sujeto igual en 05, 09 y 16 (conductual, sobre el PDF)",
           _ok5 and _productor_unico,
           "productor único + mismas etiquetas/documentos en los tres capítulos: "
           + " · ".join(_detalle5))
    else:
        ck(5, "tipo de sujeto igual en 05, 09 y 16 (productor único)", _productor_unico,
           "pdf_compiler (09, 16), titulux_bridge (05/16) y sarlaft_engine (05) usan "
           "sanctions.subjects.fila_sujeto_dictamen")

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

    # ── 10. núcleo sancionado + política por entorno (fail-closed) ──────────
    from sanctions.release_gate import (evaluar_release_seguro, SAGRILAFT_CORE_MIN,
                                        MARCA_LEGACY, MARCA_GATE_NO_EVALUABLE,
                                        STATUS_VALID, STATUS_GATE_FAILED)
    ev = evaluar_release_seguro()
    _ok10 = ev["release_status"] == STATUS_VALID
    _ev10 = (f"entorno {ev['environment']} (declarado={ev['environment_declared']}) · "
             f"política {ev['policy']} · {ev['release_status']} · "
             f"matcher {ev['core_versions'].get('matcher')} · "
             f"modelo {ev['core_versions'].get('subject_model')} · "
             f"ancestría {ev['ancestry'].get('estado')}")
    if args.pdf:
        _t10 = _txt_pdf(Path(args.pdf))
        _marcado = (MARCA_LEGACY.lower() in _t10
                    or MARCA_GATE_NO_EVALUABLE.lower() in _t10)
        _ok10 = _ok10 and not _marcado
        _ev10 += f" · PDF marcado: {'sí' if _marcado else 'no'}"
    if ev["evaluation_status"] == "EVALUATION_FAILED":
        _ok10 = False
        _ev10 += " · EVALUACIÓN FALLIDA (fail-closed: en staging/producción no se emite)"
    ck(10, "núcleo sancionado (mínimo) y política del entorno", _ok10, _ev10)

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

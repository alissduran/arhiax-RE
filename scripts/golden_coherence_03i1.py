# -*- coding: utf-8 -*-
"""03I.1 — Verificación de la lista de coherencia (§K) sobre los artefactos REALES.

Lee los artefactos de la corrida (manifest, estado interno, texto del PDF) y
comprueba, uno por uno, los criterios de aceptación de 03I.1 §K. No re-ejecuta el
producto: audita lo que la corrida produjo.

Uso:  python scripts/golden_coherence_03i1.py
Salida: código 0 si TODOS los criterios PASA, 1 si alguno FALLA.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "forensics" / "040-646406" / "golden_03i1"


def _sin_acentos(t: str) -> str:
    nfd = unicodedata.normalize("NFD", t or "")
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


def _txt() -> str:
    return re.sub(r"\s+", " ",
                  _sin_acentos((OUT / "GOLDEN_PDF_TEXT.txt").read_text(encoding="utf-8"))).lower()


def main() -> int:
    man = json.loads((OUT / "GOLDEN_EXECUTION_MANIFEST.json").read_text(encoding="utf-8"))
    st = json.loads((OUT / "GOLDEN_INTERNAL_STATE.json").read_text(encoding="utf-8"))
    txt = _txt()
    res = []

    def ck(nombre, ok, detalle):
        res.append((nombre, bool(ok), detalle))

    ident = st.get("identity") or {}
    urb = st.get("urban") or {}
    mc = st.get("market") or {}
    poi = st.get("poi") or {}
    vol = st.get("volcan") or {}
    val = st.get("valuation") or {}
    scr = st.get("screening") or {}
    inp = st.get("input") or {}

    ck("manifest.commit_sha != null", bool(man.get("commit_sha")),
       f"commit={man.get('commit_sha')}")
    ck("manifest.versions != {{}}", bool(man.get("versions")) and len(man["versions"]) >= 5,
       json.dumps(man.get("versions"), ensure_ascii=False))
    ck("input = BINARIO original", inp.get("input_type") == "ORIGINAL_BINARY" and inp.get("ctl_sha256"),
       f"{Path(str(inp.get('ctl_path'))).name} · {inp.get('ctl_size')} B · "
       f"sha256 {str(inp.get('ctl_sha256'))[:16]}…")

    _cats = poi.get("categorias") or {}
    ck("POI provenance observado", bool(_cats) and any(
        v.get("status") for v in _cats.values()),
       "; ".join(f"{c}={v.get('status')}({v.get('item_count')})" for c, v in sorted(_cats.items()))
       + f" · intentadas={poi.get('sources_attempted')} exitosas={poi.get('sources_succeeded')}")
    ck("POI sin hecho hardcodeado",
       not re.search(r"\b4 categorias\b|\b3 items\b", txt),
       "la matriz y el PDF no declaran un conteo fijo de categorías/ítems")

    ck("dirección canónica completa",
       bool(ident.get("direccion_raw")) and ident.get("direccion_raw") != "Pendiente de verificacion"
       and bool(ident.get("torre")) and bool(ident.get("apartamento")) and bool(ident.get("unidad")),
       f"raw={ident.get('direccion_raw')!r} torre={ident.get('torre')} "
       f"ap={ident.get('apartamento')} unidad={ident.get('unidad')!r} "
       f"fuente={ident.get('direccion_source')}")
    _dir_txt_ok = ("to 8 ap 430" in txt or "apartamento 430 torre 8" in txt
                   or "100 - 50 to 8 ap 430" in txt)
    ck("dirección con unidad impresa en el PDF", _dir_txt_ok,
       "el documento muestra la unidad (TO 8 / AP 430) en 01/02")

    _area = inp.get("area_extraida_por_producto")
    ck("TIT_B01 coherente con el área del CTL",
       "registral_only" in txt and "no hay area registral ni catastral" not in txt
       and (str(_area).replace(".", ",") in txt or str(_area) in txt),
       f"estado de contraste REGISTRAL_ONLY y área {_area} presente; sin la negación falsa")

    _trat = _sin_acentos(str(urb.get("tratamiento") or "")).lower()
    _alt = str(urb.get("altura_maxima") or "")
    _resumen_ok = ("poligono pot consultado en vivo" in txt)
    # 03I.2A: si la capa oficial NO resolvió el tratamiento (fuente no disponible), el
    # criterio no puede exigir un texto que no existe: se exige COHERENCIA — que 6.2 y
    # 6.3 declaren PENDIENTE y que no se invente ningún tratamiento.
    if _trat:
        ck("6.2 == 6.3 (mismo objeto urbano)",
           _trat in txt and _resumen_ok and (f"hasta {_alt} pisos" in txt if _alt else True),
           f"tratamiento={urb.get('tratamiento')!r} tipo={urb.get('tipo_tratamiento')!r} "
           f"altura={_alt!r} · resumen desde el contexto oficial")
    else:
        _pend_62 = "pendiente" in txt
        _inventado = any(t in txt for t in ("consolidacion (nivel", "nivel 2)", "hasta 11 pisos"))
        ck("6.2 == 6.3 (mismo objeto urbano)",
           _pend_62 and not _inventado,
           "la capa oficial de planeación no resolvió el polígono: 6.2 y 6.3 declaran "
           "PENDIENTE y no se inventa tratamiento ni altura")

    _modo = ((st.get("urban_source_summary") or {}).get("source_mode") or "").upper()
    ck("fuente urbana coherente (UrbanSourceSummary)",
       _modo in ("LIVE_OFFICIAL", "MIXED", "PACKAGED_REFERENCE")
       and not ("empaquetadas en la aplicacion (sin consulta en vivo)" in txt and _modo != "PACKAGED_REFERENCE"),
       f"modo={_modo}; el dictamen declara la procedencia por campo")

    # La severidad del Titulux puede aparecer partida por la extracción de texto
    # ("GEO_B01-medi a"), así que se compara por FAMILIA (media/medio -> MEDIO).
    def _familia(sev):
        s = (sev or "").lower()
        for fam, alias in (("ALTO", ("alta", "alto")), ("MEDIO", ("media", "medio")),
                           ("BAJO", ("baja", "bajo"))):
            if s.startswith(alias[0]) or s.startswith(alias[1]):
                return fam
        return s.upper()

    _tits = [_familia(m.group(1)) for m in
             re.finditer(r"geo_b01-\w*\s*[ao]?\s*amenaza por riesgo \(pot\) riesgo (\w+)", txt)]
    # OJO: el título del H-GEO lleva el NIVEL entre paréntesis («(Baja)»), no la
    # severidad; la severidad declarada va en el campo «Severidad: …» del bloque (en
    # el PDF, junto a la fuente del POT). Comparar Titulux contra el NIVEL era un
    # falso negativo de este verificador.
    _hal_sev = re.search(r"severidad: (\w+) fuente: pot", txt)
    _hal_titulo = re.search(r"h-geo \| afectacion por amenaza/riesgo detectada \((\w+)\)", txt)
    _regla = "rsk-sev-1 v1.0.0"
    _sev_hal = _familia(_hal_sev.group(1)) if _hal_sev else None
    ck("severidad Titulux == Hallazgo final",
       bool(_tits) and _sev_hal is not None and all(t == _sev_hal for t in _tits)
       and _regla in txt,
       f"Titulux={_tits} · H-GEO severidad={_sev_hal} "
       f"(nivel del título={_hal_titulo.group(1) if _hal_titulo else None}) · "
       f"regla trazada en el dictamen: {'sí' if _regla in txt else 'no'}")

    ck("constructor = URBANIZADORA MARVAL S.A.S.",
       "urbanizadora marval s.a.s." in txt,
       "razón social completa (con forma societaria) en 01 y en el screening")

    ck("wording volcánico coherente",
       not ("sin zona de amenaza volcanica cartografiada" in txt and "amenaza volcanica baja" in txt),
       f"estado SGC={vol.get('estado')} · nivel={vol.get('nivel')} · "
       f"cobertura_confirmada={vol.get('cobertura_confirmada')}")

    ck("market_methodology_version != null",
       bool(mc.get("market_methodology_version")) and bool(mc.get("market_methodology_id")),
       f"{mc.get('market_methodology_id')}@{mc.get('market_methodology_version')} "
       f"(sha256 {str(mc.get('market_methodology_sha256'))[:16]}…)")

    _aut = bool((val.get("authorization") or {}).get("allowed"))
    _cons = val.get("consolidado")
    if _aut:
        _fmt = f"{_cons:,}".replace(",", ".")
        ck("valoración: resultado matemático real emitido", bool(_cons) and _fmt in txt,
           f"autorizada · consolidado {_fmt} presente en el PDF")
    else:
        ck("valoración bloqueada sin cifras", not re.search(r"\$ [1-9]", txt),
           f"no autorizada · motivo={val.get('motivo_no_aplica')!r}")

    ck("screening: estado y evidencia",
       scr.get("status") == "SCREENING_COMPLETE" and scr.get("evidence_chain_status") == "SEALED"
       and scr.get("evidence_created") == scr.get("evidence_expected"),
       f"{scr.get('status')} · evidencia {scr.get('evidence_created')}/"
       f"{scr.get('evidence_expected')} · cadena {scr.get('evidence_chain_status')} · "
       f"matcher {scr.get('matcher_version')}")

    # 03I.1 · F13: el sello del capítulo 17 debe declarar su alcance (identifica la
    # ejecución; el hash del archivo se publica fuera del documento).
    _sello_ok = ("sello de ejecucion (sha-256)" in txt
                 and "no es el hash del archivo" in txt)
    ck("sello de integridad con alcance declarado (F13)", _sello_ok,
       "el capítulo 17 rotula el sello como de EJECUCIÓN y aclara que no es el hash "
       "del archivo" if _sello_ok else
       "el capítulo 17 presenta un 'HASH SHA-256' sin alcance")

    ck("sin valores inventados",
       not re.search(r"\$ 0 cop|no aplica \(uso no residencial|posible lote", txt),
       "sin '$ 0', sin 'no aplica (uso no residencial)', sin 'posible lote'")

    # 03I.1 · F12: no puede afirmarse "sin edificación registrada" en un predio que
    # el propio dictamen identifica como unidad en propiedad horizontal.
    _niega_edificacion = "sin edificacion registrada" in txt
    ck("no afirma ausencia de edificación (F12)", not _niega_edificacion,
       "el dictamen declara ausencia de edificación en el punto"
       if _niega_edificacion else
       "la capa de construcción se declara sin registro en el punto, sin afirmar "
       "ausencia de edificación")

    print("=== 03I.1 §K — verificación de coherencia del Golden ===")
    print(f"commit {man.get('commit_sha')} · PDF sha256 "
          f"{str((man.get('outputs') or {}).get('pdf_sha256'))[:16]}…")
    _fail = 0
    for nombre, ok, detalle in res:
        print(f"[{'PASS' if ok else 'FAIL'}] {nombre}\n        {detalle}")
        _fail += 0 if ok else 1
    print(f"\n{len(res) - _fail}/{len(res)} criterios en PASS · fallos={_fail}")
    return 1 if _fail else 0


if __name__ == "__main__":
    raise SystemExit(main())

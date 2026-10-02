# -*- coding: utf-8 -*-
"""ARHIAX RE — GOLDEN EVIDENCE ASSERTIONS (folio 040-646406).

Script de SOLO LECTURA. Ejecuta las 11 aserciones del GOLDEN EVIDENCE LITERAL PACK
contra los artefactos REALES de `docs/forensics/040-646406/dictus_2b/` y contra el
código REAL de `api/`. Imprime PASS/FAIL literal por aserción y devuelve exit code:

    0  → todas las aserciones ejecutables pasaron
    1  → al menos una falló
    2  → alguna aserción NO EVALUABLE (el artefacto no declara lo necesario)

No regenera nada, no escribe en `docs/forensics/**`.

    python scripts/golden_evidence_asserts.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "docs" / "forensics" / "040-646406" / "dictus_2b"
sys.path.insert(0, str(ROOT / "api"))

EJECUTIVO = GOLDEN / "DICTUS_EJECUTIVO_040-646406.pdf"
TECNICO = GOLDEN / "DICTUS_TECNICO_040-646406.pdf"
MANIFEST = GOLDEN / "DICTUS_MANIFEST_040-646406.json"
RUNSTATE = GOLDEN / "DICTUS_RUN_STATE_040-646406.json"

# ── salida a prueba de consola (defecto preexistente corregido en Fase 3) ──────
# Este script imprime «✓» y «·» en sus detalles. En una consola Windows en cp1252 el
# `print` lanzaba `UnicodeEncodeError: 'charmap' codec can't encode character '\u2713'`
# y el script moría ANTES de devolver su veredicto: la verificación dependía del entorno.
# Ahora TODO lo que se imprime pasa por `_seguro`, que degrada el texto a la codificación
# REAL de la consola (sustituyendo solo lo que esa consola no puede representar) en vez de
# lanzar. El veredicto (PASS/FAIL por aserción y el exit code) es idéntico en cualquier
# consola; con `PYTHONIOENCODING=utf-8` no se degrada nada.
def _seguro(texto: str) -> str:
    """Texto imprimible en la codificación REAL de la consola (nunca lanza)."""
    codificacion = (getattr(sys.stdout, "encoding", None) or "utf-8")
    try:
        texto.encode(codificacion)
        return texto
    except (UnicodeEncodeError, LookupError):
        return texto.encode(codificacion, "replace").decode(codificacion, "replace")


def _escribir(texto: str = "") -> None:
    print(_seguro(texto))


# Orígenes que NUNCA pueden sostener un hecho VERIFICADO ni abrir la valoración.
ORIGENES_PROHIBIDOS = {
    "MANUAL_CONFIG", "STATIC_REFERENCE", "MODEL_PRIOR", "FIXTURE", "DEFAULT",
    "HARDCODE", "FALLBACK_HEURISTIC",
}
# Clases que SÍ sostienen un hecho: fuente externa identificable o cálculo determinista
# sobre fuentes citadas. Ninguna otra clase puede acompañar a un estado VERIFICADO.
ORIGENES_AUTORIZADOS = {"EXTERNAL_SOURCE", "COMPUTED_FROM_SOURCES"}

# Estados de atributo REALES del vocabulario cerrado (`dictus_historia`), tal como se
# imprimen (con acento y sin guion bajo), y los TÉRMINOS DE DECISIÓN que la página 4
# estampa por atributo (mismo vocabulario de `dictus_decision`).
_ESTADOS_IMPRESOS = {
    "VERIFICADO": "VERIFICADO",
    "REQUIERE VALIDACIÓN": "REQUIERE_VALIDACION",
    "REQUIERE VALIDACION": "REQUIERE_VALIDACION",
    "CONFLICTO HISTÓRICO": "HISTORICAL_CONFLICT",
    "CONFLICTO HISTORICO": "HISTORICAL_CONFLICT",
    "SIN DATO": "SIN_DATO",
    "CAMBIO CON FUENTE": "CAMBIO_CON_FUENTE",
    "CON CONDICIONES": "CON_CONDICIONES",
    "NO UTILIZAR ESTE DATO COMO DEFINITIVO": "HISTORICAL_CONFLICT",
}

# Estados del BINDING (vocabulario de `attribute_truth.binding_geometria`, BLOCK 1 §11).
# El binding declara su ALCANCE: un binding de IDENTIFICADORES no se rotula como binding
# de geometría, así que su estado impreso es `IDENTIFICADORES` (no `VERIFICADA`).
_ESTADOS_BINDING = {
    "VERIFICADA": "VERIFICADA",
    "IDENTIFICADORES": "IDENTIFICADORES",
    "DISCREPANCIA": "DISCREPANCIA",
    "NO COMPARABLE": "NO COMPARABLE",
}

# CLAVE CANÓNICA POR ETIQUETA IMPRESA (C). Dos etiquetas que parecen «lo mismo» pueden
# ser atributos DISTINTOS: la coordenada que la corrida usa (atributo `coordenada`, con
# conflicto histórico abierto) NO es el binding de la geometría oficial contra la
# identidad canónica (atributo `binding_geometria`, verificado). Compararlos como si
# fueran el mismo atributo fabrica una contradicción que el expediente no tiene.
_ATRIBUTO_POR_ETIQUETA = {
    "COORDENADA DEL PREDIO": "coordenada",
    "ALTURA / EDIFICABILIDAD": "altura_maxima",
    "TRATAMIENTO URBANÍSTICO": "tratamiento",
    "USO DEL SUELO (POT)": "uso_pot",
    "TITULARIDAD": "titulares",
    "AMENAZA POR REMOCIÓN EN MASA": "amenaza",
    "BINDING DE LA GEOMETRÍA OFICIAL": "binding_geometria",
    # BLOCK 1 · §11: el rótulo vigente declara el ALCANCE del binding (identificadores vs
    # geometría) y sigue siendo el MISMO atributo canónico.
    "BINDING DE LA IDENTIDAD CANÓNICA DEL PREDIO": "binding_geometria",
    "GEOMETRÍA OFICIAL": "binding_geometria",
}

# Clave canónica de cada fila de identidad de la página 6.
_ATRIBUTO_IDENTIDAD = {
    "Dirección oficial": "direccion",
    "Matrícula": "matricula",
    "NUPRE": "nupre",
    "Número predial": "numero_predial",
    "Unidad (torre / apartamento)": "unidad",
    "Área": "area",
    "Régimen jurídico": "regimen_juridico",
    "Uso (destino catastral)": "destino_economico",
    "Tipología": "tipologia",
}

# Etiquetas de las filas de identidad de la página 6 (orden de impresión).
_ETIQUETAS_IDENTIDAD = (
    "Dirección oficial", "Matrícula", "NUPRE", "Número predial",
    "Unidad (torre / apartamento)", "Área", "Régimen jurídico",
    "Uso (destino catastral)", "Tipología",
)

_PASS, _FAIL, _NOEVAL = "PASS", "FAIL", "NO EVALUABLE"
_resultados: list[tuple[str, str, str]] = []


def _check(nombre: str, estado: str, detalle: str) -> None:
    _resultados.append((nombre, estado, detalle))
    _escribir(f"[{estado}] {nombre}")
    for linea in str(detalle).splitlines():
        _escribir(f"        {linea}")


def _sha256(ruta: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _texto_pdf(ruta: Path) -> str:
    """Texto del PDF CON marca de página, para poder comparar estados P1/P4/P6."""
    from pypdf import PdfReader
    return "".join(f"\n{'=' * 40} PAGE {i} {'=' * 40}\n{(p.extract_text() or '')}"
                   for i, p in enumerate(PdfReader(str(ruta)).pages, 1))


def _cargar():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    run_state = json.loads(RUNSTATE.read_text(encoding="utf-8"))
    return manifest, run_state


def _gate(manifest: dict, nombre: str) -> dict:
    for g in (manifest.get("modelo") or {}).get("decision_gates") or []:
        if g.get("gate") == nombre:
            return g
    return {}


def _paginas(texto: str) -> dict:
    partes = re.split(r"={40} PAGE (\d+) ={40}", texto)
    return {int(partes[i]): partes[i + 1] for i in range(1, len(partes), 2)}


def _bloque_identidad_p6(texto_p6: str) -> list[str]:
    """Líneas del bloque IDENTIDAD DEL INMUEBLE de la página 6."""
    m = re.search(r"IDENTIDAD DEL INMUEBLE(.*?)Identidad registral", texto_p6, re.S)
    if not m:
        return []
    return [ln.strip() for ln in m.group(1).splitlines() if ln.strip()]


def _filas_verificadas_p6(texto_p6: str, filas_declaradas: list[dict]) -> list[dict]:
    """Facts de identidad con su ESTADO impreso, leídos por ATRIBUTO (no por proximidad).

    `texto_p6` es la PÁGINA 6 completa: el bloque de identidad se extrae aquí. Cada fila
    se localiza por su ETIQUETA literal (la que el manifest declara como impresa) y su
    estado se lee en el tramo que va hasta la etiqueta siguiente. Antes se acumulaba
    texto hasta el primer token VERIFICADO y se atribuía la fila a la PRIMERA línea del
    buffer: con la dirección envolviendo 4 líneas, el hecho VERIFICADO (Matrícula) se
    leía como «Dirección oficial» y el auditor apuntaba al atributo equivocado.
    """
    lineas = _bloque_identidad_p6(texto_p6)
    if not lineas:
        return []
    etiquetas = [str(f.get("etiqueta")) for f in filas_declaradas if f.get("etiqueta")]
    etiquetas = etiquetas or list(_ETIQUETAS_IDENTIDAD)
    posiciones = []
    for etiqueta in etiquetas:
        try:
            posiciones.append((lineas.index(etiqueta), etiqueta))
        except ValueError:
            continue
    posiciones.sort()
    filas = []
    for i, (pos, etiqueta) in enumerate(posiciones):
        fin = posiciones[i + 1][0] if i + 1 < len(posiciones) else len(lineas)
        tramo = lineas[pos + 1:fin]
        declarada = next((f for f in filas_declaradas
                          if str(f.get("etiqueta")) == etiqueta), {})
        estado = next((_ESTADOS_IMPRESOS[ln] for ln in reversed(tramo)
                       if ln in _ESTADOS_IMPRESOS), "NO DECLARADO")
        filas.append({"attribute": etiqueta,
                      "atributo_clave": declarada.get("atributo_clave")
                      or _ATRIBUTO_IDENTIDAD.get(etiqueta),
                      "value": " ".join(t for t in tramo if t not in _ESTADOS_IMPRESOS),
                      "estado": estado,
                      "origin": declarada.get("origin"),
                      "origin_declarado": declarada.get("origin_declarado"),
                      "origin_gate": declarada.get("origin_gate"),
                      "origin_etiqueta": declarada.get("origin_etiqueta"),
                      "origin_provenance": declarada.get("origin_provenance")})
    return filas


def _estado_impreso(texto: str, etiqueta: str) -> str:
    """Estado impreso de una ETIQUETA, resuelto por CLAVE CANÓNICA de atributo.

    Acepta las tres formas del render: etiqueta y estado en líneas separadas (panel de
    coherencia de la P4), etiqueta y estado en la MISMA línea («Binding de la geometría
    oficial: VERIFICADA», P6) y etiqueta RECORTADA por `ajustar` («AMENAZA POR REMOCIÓN
    EN…»), porque el ancho de esa columna obliga a recortar. Por eso la etiqueta impresa
    se compara por PREFIJO contra la etiqueta declarada, con un mínimo de 12 caracteres
    para que el prefijo no sea ambiguo. Si la etiqueta no aparece, devuelve "" y el
    atributo NO se compara (nunca se inventa su estado).
    """
    clave = _ATRIBUTO_POR_ETIQUETA.get(str(etiqueta).upper())
    if not clave:
        return ""
    objetivo = str(etiqueta).upper()

    def _normalizar(s: str) -> str:
        s = s.strip().upper().rstrip(":").strip()
        for sufijo in ("…", "...", "(", "-", "·"):
            if s.endswith(sufijo):
                s = s[:-len(sufijo)].strip()
        return s

    minimo = 12
    lineas = [ln.strip() for ln in texto.splitlines() if ln.strip()]
    for i, ln in enumerate(lineas):
        arriba = ln.upper()
        if objetivo in arriba and arriba.startswith(objetivo):
            resto = ln[len(objetivo):]
            # La etiqueta puede llevar un PARÉNTESIS con su alcance antes del estado
            # («… (NO es la geometría del predio: el alcance declarado es el de
            # IDENTIFICADORES): IDENTIFICADORES») y el render puede ENVOLVER la línea: se
            # prueban las dos lecturas de la propia línea y las líneas siguientes.
            candidatas = ([resto.split(":", 1)[1].strip(),
                           resto.rsplit(":", 1)[1].strip()] if ":" in resto else [])
            candidatas += lineas[i + 1:i + 9]
        elif _normalizar(ln) and objetivo.startswith(_normalizar(ln)) \
                and len(_normalizar(ln)) >= minimo:
            candidatas = lineas[i + 1:i + 9]      # etiqueta RECORTADA con «…»
        else:
            continue
        for cand in candidatas:
            if cand in _ESTADOS_IMPRESOS:
                return _ESTADOS_IMPRESOS[cand]
            if cand in _ESTADOS_BINDING:
                return _ESTADOS_BINDING[cand]
    return ""


def _verdad_unica(manifest: dict, run_state: dict) -> dict:
    """Verdad ÚNICA por atributo canónico, tomada del expediente (no del render)."""
    hist = (run_state.get("historical_consistency")
            or (manifest.get("modelo") or {}).get("historical_consistency") or {})
    verdad = {str(c.get("atributo")): "HISTORICAL_CONFLICT"
              for c in (hist.get("conflictos_abiertos") or [])}
    for r in (hist.get("requieren_revision") or []):
        verdad.setdefault(str(r.get("atributo")), "REQUIERE_VALIDACION")
    mc = (run_state.get("market_context")
          or (manifest.get("modelo") or {}).get("market_context") or {})
    binding = str(mc.get("canonical_binding_status") or "NO_COMPARABLE").upper()
    scope = str(mc.get("canonical_binding_scope") or "").upper()
    # El estado que el expediente declara para el binding es el MISMO que imprime la P6:
    # si el alcance acreditado es de identificadores, el binding NO es geométrico.
    if binding == "VERIFIED" and scope and scope != "NATIONAL_IDENTIFIERS":
        estado_binding = "VERIFICADA"
    elif binding == "VERIFIED":
        estado_binding = "IDENTIFICADORES"
    else:
        estado_binding = {"MISMATCH": "DISCREPANCIA",
                          "NOT_COMPARABLE": "NO COMPARABLE"}.get(binding, binding)
    verdad["binding_geometria"] = estado_binding
    return verdad


# Etiquetas que el render imprime por atributo. La CLAVE canónica es lo que permite
# comparar: dos etiquetas pueden parecer «el mismo dato» y ser atributos distintos.
_ETIQUETAS_POR_PAGINA = {
    4: ("COORDENADA DEL PREDIO", "ALTURA / EDIFICABILIDAD", "TRATAMIENTO URBANÍSTICO",
        "USO DEL SUELO (POT)", "TITULARIDAD", "AMENAZA POR REMOCIÓN EN MASA"),
    # El rótulo VIGENTE declara el ALCANCE del binding; el anterior se conserva en la lista
    # para que el detector siga funcionando si un artefacto antiguo lo imprime.
    6: ("BINDING DE LA IDENTIDAD CANÓNICA DEL PREDIO", "BINDING DE LA GEOMETRÍA OFICIAL"),
}


def detectar_contradicciones(paginas: dict, manifest: dict, run_state: dict) -> dict:
    """(C) Detector de contradicciones POR CLAVE CANÓNICA DE ATRIBUTO.

    Devuelve `{"observado", "contradicciones", "discrepancias_con_la_verdad"}`. Función
    pura y testeable: `tests/test_golden_evidence_pack.py` la ejercita con texto
    manipulado para comprobar que FALLA si vuelve la discrepancia.
    """
    p1 = paginas.get(1, "")
    p6 = paginas.get(6, "")
    verdad = _verdad_unica(manifest, run_state)

    observado: dict[str, dict[str, str]] = {}
    for pagina, etiquetas in _ETIQUETAS_POR_PAGINA.items():
        texto = paginas.get(pagina, "")
        for etiqueta in etiquetas:
            clave = _ATRIBUTO_POR_ETIQUETA.get(etiqueta)
            estado = _estado_impreso(texto, etiqueta)
            if clave and estado:
                observado.setdefault(clave, {})[f"P{pagina}"] = estado

    contradicciones, discrepancias = [], []
    for clave, por_pagina in observado.items():
        if len(set(por_pagina.values())) > 1:
            contradicciones.append(
                f"atributo `{clave}`: " + " vs ".join(
                    f"{p} = {e!r}" for p, e in sorted(por_pagina.items())))
        esperado = verdad.get(clave)
        if esperado:
            for pagina, estado in sorted(por_pagina.items()):
                if estado != esperado:
                    discrepancias.append(
                        f"atributo `{clave}`: {pagina} imprime {estado!r} y el expediente "
                        f"declara {esperado!r}")
    # Hechos que siguen vigentes: la cifra no puede volver, ni con estado DISPONIBLE.
    p4 = paginas.get(4, "")
    for pagina, texto, nombre in ((1, p1, "P1"), (6, p6, "P6"), (4, p4, "P4")):
        if "$ 399.500.000" in texto:
            contradicciones.append(
                f"valoracion: {nombre} imprime '$ 399.500.000' y la valoración está "
                f"CERRADA (NO EMITIR VALORACIÓN)")
        if "NO UTILIZAR ESTE DATO COMO DEFINITIVO" in texto and "VALOR: DISPONIBLE" in texto:
            contradicciones.append(
                f"valoracion: {nombre} declara 'VALOR: DISPONIBLE' y a la vez "
                f"'NO UTILIZAR ESTE DATO COMO DEFINITIVO'")
    return {"observado": observado, "contradicciones": contradicciones,
            "discrepancias_con_la_verdad": discrepancias}


def main() -> int:
    manifest, run_state = _cargar()
    exec_text = _texto_pdf(EJECUTIVO)
    tec_text = _texto_pdf(TECNICO)
    val_gate = _gate(manifest, "VALUATION_GATE")
    paginas = _paginas(exec_text)
    p1, p4, p6 = paginas.get(1, ""), paginas.get(4, ""), paginas.get(6, "")

    # ── 1 ─────────────────────────────────────────────────────────────────────
    # (A) Los DOS campos de la compuerta conviven: `gate_state` (vocabulario CERRADO
    # CLOSED/OPEN) y `decision` (término de la gramática de decisión). Ninguno sustituye
    # al otro: la valoración está CERRADA y su decisión es «NO EMITIR VALORACIÓN».
    gate_state = val_gate.get("gate_state")
    decision = val_gate.get("decision")
    vocab_ok = gate_state in ("CLOSED", "OPEN")
    coexiste = (gate_state == "CLOSED" and decision == "NO EMITIR VALORACIÓN")
    _check("valuation_gate['gate_state'] == 'CLOSED' (con decision 'NO EMITIR VALORACIÓN')",
           _PASS if (vocab_ok and coexiste) else _FAIL,
           f"actual gate_state = {gate_state!r} · decision = {decision!r}\n"
           f"vocabulario CLOSED/OPEN = {vocab_ok} · coexisten ambos campos = {coexiste}\n"
           f"DICTUS_MANIFEST_040-646406.json · modelo.decision_gates[VALUATION_GATE]")

    # ── 2 ─────────────────────────────────────────────────────────────────────
    # El `reason` debe nombrar la CAUSA del bloqueo: el ORIGEN no habilitante.
    reason = (val_gate.get("reasons") or [None])[0]
    txt_reason = str(reason or "")
    explicito = bool(reason) and any(
        t in txt_reason for t in ("NO EMITIR", "UNRESOLVED", "no resol", "sin fuente",
                                  "no autoriza", "bloque")) and any(
        t in txt_reason for t in ("MANUAL_CONFIG", "INSUFICIENTE", "procedencia"))
    _check("valuation_gate['reason'] explícito y con el ORIGEN del bloqueo", _PASS
           if explicito else _FAIL,
           f"actual = {reason!r}\n"
           f"nombra el origen no habilitante (MANUAL_CONFIG / procedencia "
           f"insuficiente) = {any(t in txt_reason for t in ('MANUAL_CONFIG', 'INSUFICIENTE', 'procedencia'))}")

    # ── 3 / 4 / 5 ─────────────────────────────────────────────────────────────
    sha_ejecutivo = _sha256(EJECUTIVO)
    for etiqueta, aguja in (("399.500.000", "399.500.000"),
                            ("$399", "$399"),
                            ("Lonja", "Lonja")):
        presente = aguja in exec_text
        _check(f"'{etiqueta}' not in executive_text", _PASS if not presente else _FAIL,
               f"presente = {presente}\n"
               f"{EJECUTIVO.name} · sha256 = {sha_ejecutivo} · "
               f"ocurrencias = {exec_text.count(aguja)}")

    # ── 6 ─────────────────────────────────────────────────────────────────────
    ocurrencias_tec = tec_text.count("Lonja")
    _check("'Lonja' not in technical_text (salvo guardas/documentación de NO SOURCE)",
           _PASS if ocurrencias_tec == 0 else _FAIL,
           f"ocurrencias 'Lonja' = {ocurrencias_tec} en {TECNICO.name}")

    # ── 7 ─────────────────────────────────────────────────────────────────────
    # (B) Ningún hecho impreso como VERIFICADO puede llevar un ORIGEN prohibido.
    #
    # El ORIGEN se lee del ARTEFACTO que la corrida declara (`manifest.hechos_impresos`),
    # no de una tabla escrita a mano con números de línea: la tabla anterior afirmaba
    # «origin=HARDCODE» para tres etiquetas por el simple hecho de estar impresas, aunque
    # el código ya las derivara del estado. Un detector que declara el origen en vez de
    # leerlo no audita el origen: audita su propia copia.
    #
    # Regla aplicada (ajustada de forma explícita): un hecho VERIFICADO exige un origen
    # DECLARADO y AUTORIZADO —`EXTERNAL_SOURCE` o `COMPUTED_FROM_SOURCES`, con procedencia
    # completa (fuentes citadas + fecha + sha256)—; `COMPUTED_FROM_SOURCES` puro es válido
    # porque el hecho de identidad es el resultado determinista de la resolución canónica
    # de la corrida sobre dos evidencias SELLADAS de esa misma corrida, no un literal.
    # Si el origen no autoriza, el estado impreso debe estar DEGRADADO (nunca VERIFICADO).
    declaradas = (((manifest.get("modelo") or {}).get("hechos_impresos") or {})
                  .get("identidad") or {}).get("filas") or []
    _m_p6 = re.search(r"IDENTIDAD DEL INMUEBLE(.*?)Identidad registral", p6, re.S)
    bloque_p6 = _m_p6.group(1) if _m_p6 else ""
    filas = _filas_verificadas_p6(p6, declaradas)
    violaciones = []
    verificados = [f for f in filas if f["estado"] == "VERIFICADO"]
    for f in verificados:
        origin = f.get("origin")
        if origin is None:
            violaciones.append({**f, "motivo": "SIN ORIGEN DECLARADO en el manifest"})
        elif origin in ORIGENES_PROHIBIDOS:
            violaciones.append({**f, "motivo": f"origen PROHIBIDO ({origin})"})
        elif origin not in ORIGENES_AUTORIZADOS:
            violaciones.append({**f, "motivo": f"origen FUERA del vocabulario ({origin})"})
        elif not f.get("origin_gate"):
            violaciones.append({**f, "motivo": "origen no habilitante (origin_gate=False)"})
    if not filas:
        _check("no_verified_fact_has_disallowed_origin()", _NOEVAL,
               "no se pudo extraer ningún hecho de identidad de la página 6")
    else:
        _check("no_verified_fact_has_disallowed_origin()",
               _PASS if not violaciones else _FAIL,
               f"facts de identidad leídos = {len(filas)} · impresos VERIFICADO = "
               f"{len(verificados)} · violaciones = {len(violaciones)}\n"
               + "\n".join(
                   f"  · {f['attribute']} | value={f['value'][:40]!r} | "
                   f"estado={f['estado']} | origin={f.get('origin')} "
                   f"(declarado {f.get('origin_declarado')}) | gate={f.get('origin_gate')} | "
                   f"{f['motivo']}" for f in violaciones[:12])
               + (f"\n  ✓ {verificados[0]['attribute']} = {verificados[0]['value'][:32]!r} · "
                  f"origin={verificados[0].get('origin')} · "
                  f"fuentes={len(((verificados[0].get('origin_provenance') or {}).get('fuentes')) or [])}"
                  if len(verificados) == 1 else ""))

    # ── 8 ─────────────────────────────────────────────────────────────────────
    # (C) CONTRADICCIONES ENTRE PÁGINAS, POR CLAVE CANÓNICA DE ATRIBUTO.
    #
    # La versión anterior comparaba por CERCANÍA de texto: si P4 contenía
    # «NO UTILIZAR ESTE DATO COMO DEFINITIVO» y P6 contenía «Geometría oficial:
    # VERIFICADA», declaraba contradicción. Esos dos textos hablan de ATRIBUTOS
    # DISTINTOS:
    #
    #   · P4 · «COORDENADA DEL PREDIO» → atributo `coordenada`:
    #     el expediente histórico abrió conflicto sobre el VALOR de la coordenada
    #     (10.9870 -74.8115 / 11.00538 -74.83862 / 11.00612 -74.83753), así que NO se usa
    #     como dato definitivo. Correcto, y así queda impreso.
    #   · P6 · «Binding de la geometría oficial: VERIFICADA» → atributo
    #     `binding_geometria`: ¿el polígono/coordenada OFICIAL corresponde a la identidad
    #     canónica del predio (NUPRE + número predial)? El mercado declaró
    #     `canonical_binding_status = VERIFIED`. También correcto.
    #
    # Los dos hechos son verdaderos a la vez. El detector compara ahora SOLO atributos con
    # la MISMA clave canónica entre páginas, y además contrasta cada estado impreso con la
    # VERDAD ÚNICA del expediente (no con el texto de otra página).
    deteccion = detectar_contradicciones(paginas, manifest, run_state)
    contradicciones = deteccion["contradicciones"]
    discrepancias_con_la_verdad = deteccion["discrepancias_con_la_verdad"]
    observado = deteccion["observado"]

    _check("no_cross_page_state_contradictions()",
           _PASS if not contradicciones and not discrepancias_con_la_verdad else _FAIL,
           f"atributos comparados por clave canónica = {len(observado)} · "
           f"contradicciones entre páginas = {len(contradicciones)} · "
           f"discrepancias con la verdad única del expediente = "
           f"{len(discrepancias_con_la_verdad)}\n"
           + "\n".join(f"  · {c}" for c in contradicciones + discrepancias_con_la_verdad)
           + "\n  claves y estados impresos: "
           + "; ".join(f"{k}: {' / '.join(f'{p}={e}' for p, e in sorted(v.items()))}"
                       for k, v in sorted(observado.items())))

    # ── 9 / 10 / 11 ───────────────────────────────────────────────────────────
    try:
        import atribucion_mercado as am
        import market_context as mc_mod
    except Exception as exc:  # noqa: BLE001
        _check("manual_market_input_cannot_open_valuation_gate()", _NOEVAL,
               f"no se pudo importar el módulo de origen: {exc!r}")
        _check("model_prior_cannot_open_valuation_gate()", _NOEVAL, "idem")
        _check("computed_from_sources_requires_all_material_inputs_authorized()", _NOEVAL,
               "idem")
    else:
        manual = am.clasificar_origen({"origen_tipo": am.ORIGEN_MANUAL,
                                       "proveedor": "constructora", "fecha": "Q3-2026"})
        _check("manual_market_input_cannot_open_valuation_gate()",
               _PASS if not manual["origin_gate"] else _FAIL,
               f"origin={manual['origin']} · origin_gate={manual['origin_gate']}\n"
               f"blockers={manual['origin_blockers']}")

        prior = am.clasificar_origen({"origen_tipo": am.ORIGEN_PRIOR})
        _check("model_prior_cannot_open_valuation_gate()",
               _PASS if not prior["origin_gate"] else _FAIL,
               f"origin={prior['origin']} · origin_gate={prior['origin_gate']}\n"
               f"blockers={prior['origin_blockers']}")

        incompleto = am.clasificar_origen({"origen_tipo": am.ORIGEN_COMPUTADO,
                                           "fuentes": [{"proveedor": "X"}]})
        completo = am.clasificar_origen({"origen_tipo": am.ORIGEN_COMPUTADO,
                                         "fuentes": [
                                             {"proveedor": "A", "fecha": "2026-01-01",
                                              "referencia": "r1", "sha256": "a" * 64},
                                             {"proveedor": "B", "fecha": "2026-01-02",
                                              "referencia": "r2", "sha256": "b" * 64}]})
        ok = (not incompleto["origin_gate"]) and completo["origin_gate"]
        _check("computed_from_sources_requires_all_material_inputs_authorized()",
               _PASS if ok else _FAIL,
               f"sin procedencia completa: origin={incompleto['origin']} "
               f"gate={incompleto['origin_gate']} blockers={incompleto['origin_blockers']}\n"
               f"con 2 fuentes completas: origin={completo['origin']} "
               f"gate={completo['origin_gate']}")

    # ── informe ───────────────────────────────────────────────────────────────
    fallos = [r for r in _resultados if r[1] == _FAIL]
    noeval = [r for r in _resultados if r[1] == _NOEVAL]
    _escribir()
    _escribir(f"TOTAL = {len(_resultados)} · PASS = "
              f"{len([r for r in _resultados if r[1] == _PASS])} · FAIL = {len(fallos)} · "
              f"NO EVALUABLE = {len(noeval)}")
    for nombre, _, detalle in fallos:
        _escribir(f"  FAIL: {nombre} | {detalle.splitlines()[0]}")
    if fallos:
        return 1
    if noeval:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""DICTUS 2.0C — Secciones del ejecutivo derivadas del ESTADO CANÓNICO.

El ejecutivo NO lee el PDF técnico ni extrae texto: todo lo que imprime sale del
`DictusRunState` (y del informe de coherencia histórica que la corrida referencia).

2.0C recupera los hechos materiales que el producto YA calculaba y el estado no
transportaba (§1 STATE_PROJECTION_LOSS):

  · `market_context` — sector metodológico, tasa y su fuente, procedencia y binding
    de la coordenada oficial, alcance de esa geometría, procedencia por atributo
    urbano (LIVE_OFFICIAL / PACKAGED_REFERENCE) y blockers de la valoración.
  · modalidad de adquisición DERIVADA del acto inscrito en el tracto (no de un
    supuesto) con su evidencia registral.
  · activos gráficos REALES de la corrida (mapa de POI, sombras, mapa satelital si
    existe) con su huella.
  · acciones jurídicas POR TIPO de carga (la hipoteca y la afectación no comparten
    acción) y actores por atributo.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import dictus_decision as dd
import dictus_estado as dse

try:  # `api/` está en sys.path cuando el producto importa estos módulos
    import atribucion_mercado as _am
except Exception:  # noqa: BLE001 — carga determinista por ruta
    import importlib.util as _ilu
    from pathlib import Path as _Path
    _spec = _ilu.spec_from_file_location(
        "_arhiax_atribucion_mercado",
        _Path(__file__).resolve().parent / "atribucion_mercado.py")
    _am = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_am)

try:
    import estimation_state as _egs   # §32/§33 · puente estado → motor de estimación
except Exception:  # noqa: BLE001 — carga determinista por ruta
    import importlib.util as _ilu2
    from pathlib import Path as _Path2
    _spec2 = _ilu2.spec_from_file_location(
        "_arhiax_estimation_state",
        _Path2(__file__).resolve().parent / "estimation_state.py")
    _egs = _ilu2.module_from_spec(_spec2)
    _spec2.loader.exec_module(_egs)

LISTAS_FALLBACK = ("Lista Consolidada ONU", "OFAC SDN", "UK Sanctions List")

ETIQUETA_LISTA = {
    "UN_CONSOLIDATED": "ONU",
    "OFAC_SDN": "OFAC SDN",
    "UK_SANCTIONS_LIST": "UKSL",
    "UK_SANCTIONS": "UKSL",
}

NOMBRE_LISTA = {
    "ONU": "Lista Consolidada ONU (Consejo de Seguridad)",
    "OFAC SDN": "OFAC SDN (EE. UU.)",
    "UKSL": "UK Sanctions List (Reino Unido)",
}

COLUMNA_LISTA = {"ONU": "ONU", "OFAC SDN": "OFAC SDN", "UKSL": "UK SANCTIONS LIST"}

NOMBRE_CIUDAD = {
    "barranquilla": "Barranquilla", "bogota": "Bogotá", "medellin": "Medellín",
    "pasto": "Pasto", "cali": "Cali",
}

TITULO_ATRIBUTO = {
    "altura_maxima": "Altura / edificabilidad",
    "tratamiento": "Tratamiento urbanístico",
    "uso_pot": "Uso del suelo (POT)",
    # C · DOS ATRIBUTOS DISTINTOS, DOS ETIQUETAS DISTINTAS. El conflicto histórico del
    # expediente es sobre el VALOR de la coordenada que la corrida usa (`coordenada`);
    # el «binding de la geometría oficial» —¿el polígono oficial corresponde a este
    # predio?— es OTRO atributo y su estado viaja aparte, rotulado sin ambigüedad en la
    # página 6 («Binding de la geometría oficial»). La etiqueta de esta fila NO se alarga
    # con un calificativo: la columna de título del panel mide 95.6 pt a 7.6 pt y
    # cualquier sufijo se RECORTA («COORDENADA DEL PREDIO (…»), que es precisamente lo que
    # hacía ilegible el atributo. La separación se sostiene en la CLAVE canónica
    # (`coordenada` ≠ `binding_geometria`), no en un texto truncado.
    "coordenada": "Coordenada del predio",
    "titulares": "Titularidad",
    "amenaza": "Amenaza por remoción en masa",
}

# Clave canónica del atributo del BINDING de la geometría. No es `coordenada`: es la
# pregunta «¿el polígono/coordenada OFICIAL corresponde a la identidad canónica de este
# predio?». Su estado NO se degrada por el conflicto del valor de la coordenada.
ATRIBUTO_GEOMETRIA_BINDING = "binding_geometria"

# (C) Término IMPRESO por estado de atributo (vocabulario de decisión, sin abreviaturas).
# Es la ÚNICA traducción estado→texto de la página 4: un atributo se rotula con SU
# estado, nunca con el de la compuerta de otro dominio.
TERMINO_IMPRESO_POR_ESTADO = {
    dse.HISTORICAL_CONFLICT: dd.NO_USAR_COMO_DEFINITIVO,
    dse.REQUIERE_VALIDACION: "REQUIERE VALIDACIÓN",
    dse.CAMBIO_CON_FUENTE: "CAMBIO CON FUENTE",
    dse.VERIFICADO: dd.INFORMACION_VERIFICADA,
    dse.SIN_DATO: "SIN DATO",
}

# Actores que la DECISIÓN de cada atributo afecta realmente (§9). Un conflicto de
# datos no es «un riesgo alto del inmueble»: afecta a quien decide con ese dato.
AFECTADOS_POR_ATRIBUTO = {
    "altura_maxima": ["COMPRADOR", "INMOBILIARIA", "BANCO / FINANCIADOR"],
    "tratamiento": ["COMPRADOR", "INMOBILIARIA", "BANCO / FINANCIADOR"],
    "uso_pot": ["COMPRADOR", "INMOBILIARIA", "BANCO / FINANCIADOR"],
    "coordenada": ["COMPRADOR", "INMOBILIARIA"],
    "titulares": ["COMPRADOR", "INMOBILIARIA", "BANCO / FINANCIADOR",
                  "ASEGURADORA DE TÍTULO"],
    "amenaza": ["COMPRADOR", "BANCO / FINANCIADOR", "ASEGURADORA DE TÍTULO"],
}

# Acción jurídica POR TIPO de carga (§12). No se reutiliza la del acreedor en una
# afectación que no depende de él.
ACCION_POR_TIPO = {
    "HIPOTECA": ("Gestionar la obligación con el acreedor (saldo, prelación y cláusulas) "
                 "y tramitar la cancelación o el levantamiento con su registro en el folio."),
    "LIMITACION": ("Tramitar la desafectación o el levantamiento de la limitación ante la "
                   "autoridad o los titulares que la impusieron —no ante el acreedor "
                   "hipotecario— y registrar el acto en el folio."),
    "AFECTACION": ("Tramitar la desafectación o el levantamiento de la afectación ante la "
                   "entidad que la impuso y registrar el acto en el folio."),
    "EMBARGO": ("Verificar el estado del proceso ante la autoridad judicial y tramitar el "
                "desembargo con su registro en el folio."),
    "MEDIDA CAUTELAR": ("Verificar el proceso que la origina ante la autoridad competente y "
                        "tramitar su cancelación con registro en el folio."),
    "PATRIMONIO": ("Verificar el acto de afectación patrimonial y su vigencia con la entidad "
                   "competente antes de transferir."),
}

_ESTADO_POR_RESULTADO = {
    "NO_MATCH": "SIN_COINCIDENCIAS",
    "POTENTIAL_MATCH": "COINCIDENCIA",
    "STRONG_MATCH": "COINCIDENCIA",
    "EXACT_MATCH": "COINCIDENCIA",
    "REVIEW_REQUIRED": "COINCIDENCIA",
    "NOT_SCREENED": "INCOMPLETA",
    "SOURCE_UNAVAILABLE": "INCOMPLETA",
}

_AUSENCIAS = ("n/d", "n/a", "na", "no aplica", "no_aplica", "none", "null", "-", "—")


def _v(x, hueco="no declarado"):
    return hueco if x in (None, "", []) else x


def _dato(x, hueco=None):
    if x is None or (isinstance(x, str) and (not x.strip() or x.strip().lower() in _AUSENCIAS)):
        return hueco
    return x


def _pesos(v):
    return f"$ {int(v):,}".replace(",", ".") if v else None


def _actores_de_atributos(atributos) -> List[str]:
    """Actores afectados por los atributos en conflicto, sin duplicados ni anidamiento."""
    salida: List[str] = []
    for a in (atributos or []):
        for actor in AFECTADOS_POR_ATRIBUTO.get(a.get("atributo"), []):
            if actor not in salida:
                salida.append(actor)
    return salida


def _coherencia_de(atributo: str, filas: List[Dict[str, Any]]) -> Optional[str]:
    for f in filas or []:
        if f.get("atributo") == atributo:
            return f.get("estado")
    return None


# ── screening ─────────────────────────────────────────────────────────────────
def _listas_de_screening(screening: Dict[str, Any]) -> List[str]:
    nombres: List[str] = []
    for f in (screening.get("sources") or screening.get("fuentes") or []):
        sid = f if isinstance(f, str) else (f.get("source_id") or f.get("id") or "")
        etiqueta = ETIQUETA_LISTA.get(str(sid).upper(), str(sid).replace("_", " ").title())
        if etiqueta and etiqueta not in nombres:
            nombres.append(etiqueta)
    return nombres or list(LISTAS_FALLBACK)


def _por_lista(screening: Dict[str, Any], sujeto: Dict[str, Any],
               listas: List[str]) -> Dict[str, str]:
    """Resultado del sujeto en CADA lista, tomado de los `outcomes` del motor.

    Sin outcome declarado para ese par (sujeto, lista) el estado es «NO CONSULTADA»:
    nunca se afirma «sin coincidencia» de algo que no se consultó.
    """
    salida = {li: "INCOMPLETA" for li in listas}
    sujeto_id = sujeto.get("subject_id")
    for o in (screening.get("outcomes") or []):
        if not isinstance(o, dict) or o.get("subject_id") != sujeto_id:
            continue
        sid = str(o.get("source_id") or "").upper()
        etiqueta = ETIQUETA_LISTA.get(sid, str(o.get("source_id") or "").replace("_", " ").title())
        if etiqueta not in salida:
            continue
        estado = _ESTADO_POR_RESULTADO.get(str(o.get("result") or "").upper(), "SIN_DATO")
        if estado == "COINCIDENCIA" or salida[etiqueta] == "INCOMPLETA":
            salida[etiqueta] = estado
    return salida


def _documento_de_sujeto(s: Dict[str, Any]) -> Optional[str]:
    numero = s.get("document") or s.get("documento") or s.get("document_number")
    if not numero:
        return None
    tipo = str(s.get("document_type") or "").upper()
    try:
        from sanctions.contracts import mask_document
        return f"{tipo} {mask_document(s.get('document_type'), str(numero))}".strip()
    except Exception:  # noqa: BLE001 — máscara local idéntica en forma
        n = str(numero)
        return f"{tipo} {n[:4]}{'*' * (len(n) - 5)}{n[-1]}".strip() if len(n) > 4 else "****"


def _sujetos_de_screening(screening: Dict[str, Any], listas: List[str]) -> List[Dict[str, Any]]:
    salida = []
    for s in (screening.get("subjects") or screening.get("sujetos") or []):
        if not isinstance(s, dict):
            continue
        estado_global = str(screening.get("status") or "")
        resultado = ("SIN_COINCIDENCIAS"
                     if estado_global == "SCREENING_COMPLETE"
                     and screening.get("evidence_chain_status") == "SEALED"
                     else "INCOMPLETA")
        if screening.get("matched_subjects") and s.get("subject_id") in (
                screening.get("matched_subjects") or []):
            resultado = "COINCIDENCIA"
        salida.append({
            "subject_id": s.get("subject_id"),
            "nombre": s.get("canonical_name") or s.get("nombre") or "—",
            "rol": ", ".join(s.get("roles") or []) or "contraparte del caso",
            "tipo": s.get("person_type_label") or s.get("person_type") or "No determinado",
            "documento": _documento_de_sujeto(s),
            "por_lista": _por_lista(screening, s, listas),
            "resultado": resultado,
        })
    return salida


# ── acciones jurídicas y coherencia ───────────────────────────────────────────
def _accion_para_carga(carga: Dict[str, Any], findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Acción ESPECÍFICA de la carga: la del hallazgo que la identifica o la del tipo.

    Antes todas las cargas recibían la misma frase («cancelación con el acreedor»),
    que además es incorrecta para una afectación a vivienda familiar (§12).
    """
    anot = str(carga.get("anotacion") or "").strip()
    for f in findings:
        texto = f"{f.get('codigo') or ''} {f.get('titulo') or ''}".upper()
        if anot and (f"ANOT. {anot}" in texto or f"ANOTACIÓN {anot}" in texto
                     or f"ANOTACION {anot}" in texto):
            return {"accion": f.get("accion") or None, "origen": "HALLAZGO",
                    "codigo": f.get("codigo")}
    tipo_norm = str(carga.get("tipo") or "").upper()
    for clave, accion in ACCION_POR_TIPO.items():
        if clave in tipo_norm:
            return {"accion": accion, "origen": "TIPO_DE_CARGA", "codigo": None}
    return {"accion": ("Verificar el acto inscrito y su vigencia con la entidad que lo "
                       "origina; registrar su cancelación cuando proceda."),
            "origen": "TIPO_NO_DECLARADO", "codigo": None}


def _actual_de_atributo(atributo: str, rs: Dict[str, Any], mc: Dict[str, Any]) -> Dict[str, Any]:
    """Valor OBSERVADO EN ESTA CORRIDA del atributo, con su fuente y su modo.

    §16: no se esconde el valor actual porque exista un conflicto histórico; se
    declaran las tres cosas —actual, histórico y coherencia— y de dónde sale.
    """
    urb = rs.get("urban_context") or {}
    ts = rs.get("title_state") or {}
    risk = rs.get("risk_context") or {}
    campos = ((mc.get("urban_source_summary") or {}).get("campos") or {})

    def _modo(clave):
        c = campos.get(clave) or {}
        return c.get("modo"), c.get("fuente")

    if atributo == "altura_maxima":
        modo, _f = _modo("altura_maxima")
        valor = _dato(urb.get("altura_maxima"))
        return {"valor": f"Hasta {valor} pisos" if valor else None,
                "fuente": ("capa POT empaquetada del municipio (cruce local, sin consulta "
                           "en vivo)" if modo == "PACKAGED_REFERENCE"
                           else "capa POT oficial en vivo"),
                "modo": modo or "NO_DECLARADO"}
    if atributo == "tratamiento":
        modo, _f = _modo("tratamiento")
        base = _dato(urb.get("tratamiento"))
        tipo = _dato(urb.get("tipo_tratamiento"))
        return {"valor": f"{base} ({tipo})" if base and tipo else base,
                "fuente": ("capa POT oficial en vivo" if modo == "LIVE_OFFICIAL"
                           else "capa POT empaquetada (sin consulta en vivo)"),
                "modo": modo or "NO_DECLARADO"}
    if atributo == "uso_pot":
        uso = mc.get("uso") or {}
        return {"valor": _dato(uso.get("value")) or _dato(urb.get("area_actividad")),
                "fuente": "capa oficial de uso del suelo (POT)",
                "modo": str(uso.get("status") or "NO_DECLARADO")}
    if atributo == "coordenada":
        coords = mc.get("coordinates") or {}
        lat, lon = coords.get("lat"), coords.get("lon")
        return {"valor": (f"{lat:.5f}, {lon:.5f}" if lat and lon else None),
                "fuente": f"geometría oficial ({mc.get('coordinate_source') or 'sin fuente'})",
                "modo": ("VERIFIED_OFFICIAL" if mc.get("coordinate_source_verified")
                         else "NO_VERIFICADA")}
    if atributo == "titulares":
        return {"valor": _dato(ts.get("titulares")),
                "fuente": "certificado de tradición y libertad (SNR/CTL)",
                "modo": "VERIFIED_REGISTRAL"}
    if atributo == "amenaza":
        return {"valor": _dato(risk.get("amenaza_remocion_masa")),
                "fuente": "capa de amenaza del POT (cruce local, sin consulta en vivo)",
                "modo": "PACKAGED_REFERENCE"}
    return {"valor": None, "fuente": None, "modo": "NO_DECLARADO"}


def _coherencia_detallada(hist: Dict[str, Any], rs: Dict[str, Any],
                          mc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Un registro por ATRIBUTO con su estado: el chip de la página 4 sale de AQUÍ.

    (C) Antes la página 4 estampaba la decisión del `URBAN_GATE` en TODOS los atributos
    del panel, incluidos los que no son urbanísticos (`coordenada`, `titulares`,
    `amenaza`). Coincidía por casualidad —todos están en conflicto histórico—, pero un
    atributo con otro estado habría salido rotulado con el estado ajeno. Ahora cada fila
    declara `estado_impreso`, derivado de SU estado, y el render lo imprime tal cual.
    """
    filas: List[Dict[str, Any]] = []
    for c in (hist.get("conflictos_abiertos") or []):
        atributo = str(c.get("atributo") or "")
        actual = _actual_de_atributo(atributo, rs, mc)
        estado = dse.HISTORICAL_CONFLICT
        filas.append({
            "atributo": atributo,
            "titulo": TITULO_ATRIBUTO.get(atributo, atributo.replace("_", " ").title()),
            "actual": actual.get("valor"),
            "fuente_actual": actual.get("fuente"),
            "modo_actual": actual.get("modo"),
            "historico": list(c.get("valores") or []),
            "detalle": c.get("detalle"),
            "estado": estado,
            "estado_impreso": TERMINO_IMPRESO_POR_ESTADO.get(estado, estado),
            "decision": TERMINO_IMPRESO_POR_ESTADO.get(estado, estado),
            "afectados": AFECTADOS_POR_ATRIBUTO.get(atributo, []),
        })
    return filas


def _tipologia_inferida(mc: Dict[str, Any], urb: Dict[str, Any]) -> bool:
    """¿La tipología física de esta corrida es una INFERENCIA, no un dato de la fuente?

    El producto la deriva de la condición registral/catastral y lo dice con todas las
    letras en su propio valor («(inferido del CTL)»). Un hecho inferido no es un hecho
    verificado: se declara como tal.
    """
    for valor in (_dato(urb.get("tipologia")),
                  _dato((mc.get("tipologia") or {}).get("value"))):
        if valor and "INFERID" in str(valor).upper():
            return True
    return False


def verdad_por_atributo(hist: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """UNA sola verdad por atributo: el estado que ESTA corrida sostiene.

    El informe de coherencia histórica ya declara, atributo por atributo, qué se puede
    afirmar (`dictus_historia.conflicto_de_atributo`):

      · `conflictos_abiertos`  → `HISTORICAL_CONFLICT`   (no se usa como definitivo)
      · `requieren_revision`   → `REQUIERE_VALIDACION`   (cambió sin explicación)
      · `cambios_explicados`   → `CAMBIO_CON_FUENTE`     (cambió y la fuente lo explica)

    Esta función es el ÚNICO lugar donde ese estado se resuelve para las páginas: así la
    página 4, la página 6 y el bloque de coherencia no pueden discrepar sobre el mismo
    atributo. Un atributo ausente del informe conserva su estado por procedencia.
    """
    estado: Dict[str, str] = {}
    hist = hist or {}
    for c in hist.get("conflictos_abiertos") or []:
        atributo = c.get("atributo")
        if atributo:
            estado[str(atributo)] = dse.HISTORICAL_CONFLICT
    for r in hist.get("requieren_revision") or []:
        atributo = r.get("atributo")
        if atributo and str(atributo) not in estado:
            estado[str(atributo)] = str(r.get("estado") or dse.REQUIERE_VALIDACION)
    for e in hist.get("cambios_explicados") or []:
        atributo = e.get("atributo")
        if atributo and str(atributo) not in estado:
            estado[str(atributo)] = dse.CAMBIO_CON_FUENTE
    return estado


def _geometria_estado(mc: Dict[str, Any]) -> str:
    binding = str(mc.get("canonical_binding_status") or "NO_COMPARABLE").upper()
    return {"VERIFIED": "VERIFICADA", "MISMATCH": "DISCREPANCIA",
            "NOT_COMPARABLE": "NO COMPARABLE"}.get(binding, binding)


def _geometria_detalle(mc: Dict[str, Any]) -> str:
    """Explica en lenguaje llano qué acredita (y qué no) la geometría de la corrida."""
    binding = str(mc.get("canonical_binding_status") or "").upper()
    campos = mc.get("canonical_binding_fields") or []
    alcance = _dato(mc.get("coordinate_scope"))
    fuente = _dato(mc.get("coordinate_source"))
    partes = []
    if binding == "VERIFIED":
        partes.append("La geometría oficial del predio coincide con la identidad canónica"
                      + (f" ({', '.join(str(c) for c in campos)})" if campos else "") + ".")
    elif binding == "MISMATCH":
        partes.append("La geometría oficial NO coincide con la identidad canónica: revise el "
                      "polígono antes de usarla.")
    elif binding == "NOT_COMPARABLE":
        partes.append("La identidad registral está verificada, pero la geometría no se pudo "
                      "comparar con ella en esta corrida.")
    else:
        partes.append("La corrida no declaró el binding de la geometría.")
    if alcance:
        partes.append(str(alcance)[:1].upper() + str(alcance)[1:] + ".")
    if fuente:
        partes.append(f"Fuente: {fuente}.")
    return " ".join(partes)


# ── B · ORIGEN DE UN HECHO IMPRESO ───────────────────────────────────────────
# Un hecho que el documento imprime como VERIFICADO tiene que declarar DE DÓNDE SALE,
# igual que una tasa de mercado: no basta con etiquetarlo «verificado». La procedencia
# se toma del MANIFEST DE EVIDENCIAS de ESTA corrida —cada fuente cita su proveedor
# declarado, su fecha y el `content_hash` SELLADO de esa evidencia, nunca una constante
# escrita a mano—. Sin evidencia sellada no hay procedencia: `clasificar_origen` degrada
# el origen y la fila se imprime DEGRADADA; el hecho nunca se borra.
#
# POR QUÉ ESTAS DOS FUENTES (y no un literal del render): el estado VERIFICADO de la
# matrícula no lo decide el renderizador, lo decide la RESOLUCIÓN CANÓNICA de identidad
# de la corrida (`canonical.identidad_canonica`): `identity_verified` se deriva de
# `resolution_confidence == VERIFIED_UNIT_IDENTITY`, es decir del ACUERDO entre los dos
# dominios que la corrida sí comparó y selló como evidencia:
#
#   · `EV-IDENTIDAD`  (SELLADA) — el registro canónico de identidad de ESTA corrida:
#                      su contenido lleva `folio` (la matrícula que se imprime), `nupre`,
#                      `codigo_catastral`, `estado` y `confianza`.
#   · `EV-GEOMETRIA`  (SELLADA) — el registro oficial del catastro municipal
#                      (`CATASTRO_MUNICIPAL_BARRANQUILLA_ARCGIS`) que liga NUPRE y número
#                      predial al predio con `binding=VERIFIED`.
#
# Las dos viajan con proveedor, fecha y `sha256` REALES (el `content_hash` sellado de la
# evidencia), así que el hecho es `COMPUTED_FROM_SOURCES`: un cálculo determinista de la
# corrida sobre fuentes citadas. NO es hardcode (ningún literal del render), NO es
# `MODEL_PRIOR` (no hay default) y NO es `MANUAL_CONFIG` (no lo escribió una persona).
# Si esas evidencias no estuvieran selladas, `clasificar_origen` lo degrada solo.
EVIDENCIAS_IDENTIDAD = ("EV-IDENTIDAD", "EV-GEOMETRIA")


def _fuentes_selladas(modelo: Dict[str, Any],
                      ids: Sequence[str]) -> List[Dict[str, Any]]:
    """Fuentes citables: sólo evidencias SELLADAS, con su hash real de contenido."""
    evidencias = ((modelo.get("evidence_manifest") or {}).get("evidencias") or [])
    por_id = {str(e.get("evidence_id")): e for e in evidencias if isinstance(e, dict)}
    fuentes: List[Dict[str, Any]] = []
    for eid in ids:
        e = por_id.get(str(eid))
        if not e or str(e.get("status") or "").upper() != "SELLADA":
            continue  # una evidencia no sellada no sostiene un hecho verificado
        fuentes.append({
            "proveedor": str(e.get("source") or ""),
            "fecha": str(e.get("timestamp") or ""),
            "referencia": f"{eid} · {e.get('evidence_type')}",
            "sha256": str(e.get("content_hash") or ""),
        })
    return fuentes


def _origen_de_hecho(modelo: Dict[str, Any],
                     ids: Sequence[str] = EVIDENCIAS_IDENTIDAD) -> Dict[str, Any]:
    """Origen EFECTIVO de un hecho, con la procedencia REAL de la corrida.

    El hecho de identidad no se lee de un literal del render: es el resultado
    DETERMINISTA de la resolución de identidad de la corrida (folio ↔ NUPRE ↔ número
    predial) sostenido por dos evidencias selladas de la MISMA corrida. Por eso se
    declara `COMPUTED_FROM_SOURCES`; si esa procedencia no estuviera completa, la propia
    función lo degrada a `MANUAL_CONFIG` y el hecho pierde el VERIFICADO.
    """
    return _am.clasificar_origen(
        {"origen_tipo": _am.ORIGEN_COMPUTADO,
         "fuentes": _fuentes_selladas(modelo, ids)},
        por_defecto=_am.ORIGEN_MANUAL)


def _seccion_estimacion(rs: Dict[str, Any], modelo: Dict[str, Any],
                        hist: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """§32/§33 · ESTIMACIÓN: corre el motor sobre el estado y expone sus contratos.

    El ejecutivo NO redacta la estimación: la PIDE. Aquí se ejecuta
    `estimation.estimar(...)` con la entrada construida desde el estado real (con su
    procedencia) y se devuelven los dos contratos de impresión —`p1` y `p6`— junto al
    resultado completo y sus contadores, para que el render los imprima literales.
    """
    salida = _egs.ejecutar(rs, modelo, historico_forense=hist or {})
    resultado = salida["resultado"]
    consulta = str((modelo.get("document_identity") or {}).get("generated_at")
                   or rs.get("generated_at") or "")[:10]
    cosecha = (salida["entrada"].get("auditoria_de_entrada") or {}).get("cosecha_municipal")
    return {"p1": _egs.contrato_p1(resultado),
            "p6": _egs.contrato_p6(resultado, cosecha=cosecha,
                                   consulta=consulta or None),
            "status": resultado.get("status"),
            "estado": (resultado.get("estimation_gate") or {}).get("gate_state"),
            "confianza": _egs.confianza_de(resultado),
            "hash_payload": resultado.get("hash_payload"),
            "contadores": salida["contadores"],
            "resultado": resultado,
            "entrada": salida["entrada"],
            "referencia": salida["referencia"]}


def desde_estado(rs: Dict[str, Any], modelo: Dict[str, Any],
                 historial: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Construye las secciones de las 6 páginas desde el estado canónico."""
    rs = rs or {}
    pi = rs.get("property_identity") or {}
    ts = rs.get("title_state") or {}
    urb = rs.get("urban_context") or {}
    val = rs.get("valuation_state") or {}
    scr = rs.get("screening_summary") or {}
    poi = rs.get("poi_state") or {}
    risk = rs.get("risk_context") or {}
    solar = rs.get("solar_state") or {}
    mc = rs.get("market_context") or {}
    vis = rs.get("visual_assets") or {}
    findings = list(rs.get("findings") or [])
    hist = historial or {}

    orden = {"ALTO": 0, "MEDIO": 1, "INFORMATIVO": 2}
    findings.sort(key=lambda x: orden.get(str(x.get("severidad")).upper(), 3))
    # HALLAZGOS DE LA OPERACIÓN vs COHERENCIA DE INFORMACIÓN (§8): un conflicto entre
    # versiones del mismo dato no es un riesgo alto del inmueble.
    operacion = [f for f in findings if str(f.get("codigo") or "").upper() != "H-COH"]

    con_carga = bool(ts.get("gravamenes_vigentes"))
    hay_conf_urb = any(c.get("atributo") in ("altura_maxima", "tratamiento", "uso_pot")
                       for c in hist.get("conflictos_abiertos", []))
    aut = bool((val.get("authorization") or {}).get("allowed"))
    # Sin comparación histórica NO se puede afirmar que el atributo haya permanecido
    # igual: se declara que no hay expediente comparado (PASS falso prohibido).
    # ¿Hubo comparación histórica REAL? Sin informe, decir «verificado»
    # sería un PASS falso.
    hist_comparado = bool(hist) and int(hist.get("versiones_comparadas") or 0) > 0
    _conf_urb = {c.get("atributo"): c for c in (hist.get("conflictos_abiertos") or [])}

    # ── UNA SOLA VERDAD POR ATRIBUTO (P3) ─────────────────────────────────────
    # El MISMO dictus declara, en su informe de coherencia, el estado de cada atributo.
    # Imprimir «VERIFICADO» un atributo que la corrida declara `REQUIERE_VALIDACION`
    # (o `HISTORICAL_CONFLICT`) es una contradicción INTERNA del documento, no una
    # opinión: aquí se vuelve imposible, porque las filas leen esa única verdad.
    verdad_atributos = verdad_por_atributo(hist)

    def _estado_atributo(atributo: str, valor: Any,
                         origen: Optional[Dict[str, Any]] = None) -> str:
        """Estado de UNA fila: sin valor -> SIN_DATO; con valor -> la verdad única.

        Nunca se imprime VERIFICADO un atributo que el expediente marca por revisar, y
        nunca se borra el hecho: el VALOR se sigue imprimiendo con su estado degradado.
        (B) Tampoco se imprime VERIFICADO un hecho cuyo ORIGEN declarado no lo sostiene:
        un origen no habilitante DEGRADA el estado; no lo esconde.
        """
        if not _dato(valor):
            return dse.SIN_DATO
        est = verdad_atributos.get(atributo, dse.VERIFICADO)
        if (est == dse.VERIFICADO and isinstance(origen, dict)
                and not origen.get("origin_gate")):
            return dse.REQUIERE_VALIDACION
        return est

    def _nota_atributo(atributo: str, base: Optional[str] = None) -> Optional[str]:
        est = verdad_atributos.get(atributo)
        if est == dse.HISTORICAL_CONFLICT:
            return base or "Distintos entre versiones · ver coherencia abajo."
        # `REQUIERE_VALIDACION` NO lleva nota por fila: el chip ya lo declara y el
        # presupuesto de la página 4 no admite una línea más por atributo. La causa
        # viaja en el MODELO (`historical_consistency.requieren_revision`), que es
        # donde el lector técnico la consulta.
        if est == dse.REQUIERE_VALIDACION:
            return base
        if not hist_comparado:
            return base or "Sin expediente histórico comparado."
        return base

    def _estado_urb(atributo: str) -> str:
        if not hist_comparado and atributo not in verdad_atributos:
            return dse.REQUIERE_VALIDACION
        return verdad_atributos.get(atributo, dse.VERIFICADO)

    def _nota_urb(atributo: str) -> Optional[str]:
        # Nota de UNA línea: el detalle completo vive en el bloque «Coherencia de datos
        # por atributo» de esta misma página.
        return _nota_atributo(atributo)

    def _valor_tipologia():
        return (_dato(urb.get("tipologia"))
                or _dato((mc.get("tipologia") or {}).get("value")))

    def _estado_tipologia() -> str:
        """La tipología física que la fuente no declara se INFIERE: se declara como tal."""
        valor = _valor_tipologia()
        if not valor:
            return dse.SIN_DATO
        est = verdad_atributos.get("tipologia")
        if est:
            return est
        return (dse.REQUIERE_VALIDACION if _tipologia_inferida(mc, urb) else dse.VERIFICADO)
    # §15: «sellado» significa que el SELLO DEL EXPEDIENTE está completo — el estado
    # del manifest—, no que la cadena técnica interna esté cerrada. El sello es el que
    # se imprime en el pie y en la página 1: el texto no puede decir otra cosa.
    sello_manifiesto = str((modelo.get("evidence_manifest") or {}).get("estado") or "")
    sellado = sello_manifiesto.upper() == "SELLADO"
    cadena_cerrada = str(scr.get("evidence_chain_status") or "") == "SEALED"
    coherencia_attrs = _coherencia_detallada(hist, rs, mc)
    # (B) ORIGEN de los hechos de identidad, resuelto UNA vez por corrida desde las
    # evidencias selladas de su propio manifest.
    origen_identidad = _origen_de_hecho(modelo)

    indicadores = [
        ("Identidad", dse.VERIFICADO if pi.get("identity_verified") else dse.REQUIERE_VALIDACION,
         f"Matrícula, NUPRE y predial resueltos ({_v(pi.get('resolution_method'))})."),
        ("Títulos", "CON_CONDICIONES" if con_carga else dse.VERIFICADO,
         ("Cargas vigentes declaradas en el folio." if con_carga
          else "Sin cargas vigentes declaradas.")),
        # El indicador habla del SCREENING (¿se revisaron los sujetos contra las
        # listas?), no del sellado de la evidencia: son dos hechos distintos (§14).
        ("Contrapartes", "SIN_COINCIDENCIAS" if cadena_cerrada else "INCOMPLETA",
         f"{len(scr.get('subjects') or [])} sujeto(s) · evidencia "
         f"{_v(scr.get('evidence_created_count') or scr.get('evidence_created'), '0')}/"
         f"{_v(scr.get('evidence_expected_count') or scr.get('evidence_expected'), '—')}."),
        ("Territorio", dse.REQUIERE_VALIDACION if hay_conf_urb else dse.VERIFICADO,
         ("Coherencia histórica abierta en atributos urbanísticos." if hay_conf_urb
          else "Capas oficiales del municipio consultadas.")),
        # §7 · El indicador se llama «Valoración corrida» (no «Valor»): el estado
        # «NO DISPONIBLE» de este dominio es el de la VALORACIÓN QUE DECLARA LA CORRIDA,
        # no la ausencia de estimación —DICTUS estima e imprime su tira aparte—. Imprimir
        # «VALOR NO DISPONIBLE» al lado de «ESTIMACIÓN INDICATIVA» era la contradicción
        # visual que el lector leía como «no hay valor».
        ("Valoración corrida", "DISPONIBLE" if aut else "NO_DISPONIBLE",
         "Valoración autorizada." if aut else
         f"No autorizada: {_v(val.get('motivo_no_aplica'), 'se declara el blocker, sin cifras')}"),
    ]

    # ── 2.0D · cadena de decisión (ya construida en el modelo) ───────────────
    disposicion_ = (modelo.get("disposition") or {})
    compuertas = {g.get("gate"): g for g in (modelo.get("decision_gates") or [])}
    matriz = list(modelo.get("decision_matrix") or [])
    TEMA = {"IDENTITY": "IDENTIDAD", "TITLE": "TÍTULO", "COUNTERPARTY": "CONTRAPARTES",
            "URBAN": "POT / URBANISMO", "ENVIRONMENT": "ENTORNO Y RIESGOS",
            "VALUATION": "VALORACIÓN"}

    def _tema(fila):
        return TEMA.get(str(fila.get("domain") or "").upper(), str(fila.get("domain") or "—"))

    tablero = []
    for fila in matriz:
        if fila.get("risk_class") == "INFORMATION_QUALITY_RISK":
            continue
        tablero.append({"tema": _tema(fila),
                        "severity": fila.get("severity"),
                        "encontro": fila.get("observation") if isinstance(
                            fila.get("observation"), str) else fila.get("finding"),
                        "decision": fila.get("decision"),
                        "afecta": ", ".join(fila.get("affected_parties") or []) or
                        "Impacto pendiente de clasificación",
                        "accion": fila.get("action")})
    if coherencia_attrs:
        _coh = [f for f in findings if str(f.get("codigo") or "").upper() == "H-COH"]
        tablero.append({
            "tema": "POT / CALIDAD DE DATOS",
            "severity": next((f.get("severity") for f in _coh if f.get("severity")), None),
            "encontro": (f"{len(coherencia_attrs)} atributo(s) con resultados incompatibles "
                         f"entre versiones del expediente"),
            "decision": dd.NO_USAR_COMO_DEFINITIVO,
            "afecta": ", ".join(_actores_de_atributos(coherencia_attrs)) or
            "COMPRADOR, INMOBILIARIA, BANCO / FINANCIADOR",
            "accion": "Reconciliar con la ficha/polígono POT aplicable antes de usar la cifra."})
    # los temas no se repiten: el tablero resume la decisión por tema. Si un tema tiene
    # varios hallazgos, la fila declara CUÁNTOS agrupa (nunca los oculta sin decirlo).
    _vistos = {}
    tablero_unico = []
    for fila in tablero:
        clave = (fila["tema"], fila["decision"])
        if clave in _vistos:
            _vistos[clave]["agregados"] = _vistos[clave].get("agregados", 0) + 1
            continue
        fila["agregados"] = 0
        _vistos[clave] = fila
        tablero_unico.append(fila)

    indicadores_6 = list(indicadores) + [
        ("Entorno", (dse.VERIFICADO if (compuertas.get(dd.ENVIRONMENT_GATE) or {}).get("decision")
                     == dd.INFORMACION_VERIFICADA else dse.REQUIERE_VALIDACION),
         f"{_v((poi.get('item_count')), '0')} equipamiento(s) en el radio analizado · "
         f"asoleamiento {'declarado' if (solar.get('momentos')) else 'no declarado'}.")]

    listas = _listas_de_screening(scr)
    area_txt = (f"{urb.get('area'):.2f}".rstrip("0").rstrip(".") + " m²"
                if urb.get("area") else None)

    # ── dirección ejecutiva: identidad canónica completa (§10) ────────────────
    base_dir = _dato(pi.get("direccion_normalizada")) or _dato(pi.get("direccion_raw"))
    torre = _dato(pi.get("torre"))
    apto = _dato(pi.get("apartamento"))
    unidad = _dato(pi.get("unidad"))
    sufijo = None
    if torre or apto:
        sufijo = " · ".join(x for x in (f"Torre {torre}" if torre else None,
                                        f"Apartamento {apto}" if apto else None) if x)
    elif unidad:
        sufijo = str(unidad)
    # La dirección que viene del folio puede incluir ya la torre y el apartamento:
    # repetirlas («… APARTAMENTO 430 TORRE 8 … · Torre 8 · Apartamento 430») ensucia la
    # cabecera sin añadir información.
    _base_norm = " ".join(str(base_dir or "").upper().split())
    _ya_incluye = bool(sufijo) and all(
        tok in _base_norm for tok in
        [t for t in str(sufijo).upper().replace("·", " ").split() if t.isdigit()])
    direccion_ejecutiva = " · ".join(
        x for x in (base_dir, None if _ya_incluye else sufijo) if x)

    # El rótulo de la P1 nombra SU objeto: es la valoración que declara LA CORRIDA, no la
    # estimación de DICTUS (que imprime su propia tira, con su etiqueta y su confianza).
    # Antes se llamaba «Valor estimado» y convivía confundiendo con esa tira.
    # §7 (Fase 3 · cierre semántico): cuando la valoración de la corrida está bloqueada,
    # el texto nombra la COMPUERTA que realmente cierra (`VERIFIED_MARKET_EVIDENCE_GATE`
    # = evidencia de mercado verificada) y NO deja leer «no hay valor» al lado de la
    # ESTIMACIÓN INDICATIVA de DICTUS, que es OTRO hecho.
    _estado_verif = str(val.get("gate_state") or val.get("verified_market_evidence_gate")
                        or "CLOSED")
    # El texto cabe en la celda de la P1 (24 caracteres útiles a 9,4 pt): nombra el hecho
    # —evidencia NO verificada— sin el rótulo ambiguo «VALORACIÓN NO DISPONIBLE», que el
    # lector cruzaba con la ESTIMACIÓN INDICATIVA de DICTUS impresa justo debajo.
    valor_corrida_txt = (
        _pesos(val.get("consolidado")) if aut else
        "no habilitada (evidencia no verificada)")
    valor_estimado_txt = valor_corrida_txt     # nombre histórico del mismo hecho
    fecha_consulta = str(rs.get("generated_at") or "")[:10] or None

    general = [
        ("Dirección", direccion_ejecutiva or "no declarada"),
        ("Matrícula", _v(pi.get("folio"), "no declarada")),
        ("Ciudad", NOMBRE_CIUDAD.get(str(rs.get("ciudad") or "").lower(),
                                     _v(rs.get("ciudad"), "no declarada"))),
        ("Barrio", _v(urb.get("barrio"), "no declarado")),
        ("Área", _v(area_txt, "no declarada")),
        ("Uso", _v(urb.get("destino_economico") or (mc.get("uso") or {}).get("value"),
                   "no declarado")),
        ("Régimen", _v(urb.get("condicion_juridica"), "no declarado")),
        ("Valoración de la corrida", valor_corrida_txt),
    ]

    # ── condiciones para cerrar la operación (§7/§12) ─────────────────────────
    condiciones: List[str] = []
    for f in operacion:
        accion = _dato(f.get("accion"))
        if accion and accion not in condiciones:
            condiciones.append(str(accion))
    condiciones = condiciones[:5]

    # ── valoración: valor o blockers reales (§22/§23) ─────────────────────────
    blockers = [b for b in (mc.get("blockers") or []) if isinstance(b, str)]
    auth = val.get("authorization") or {}
    if not aut:
        for clave, etiqueta in (("identity_authorized", "Identidad del inmueble no autorizada"),
                                ("market_context_authorized",
                                 "Contexto de mercado no autorizado")):
            if auth.get(clave) is False and etiqueta not in blockers:
                blockers.append(etiqueta)
        # P7 · el ORIGEN no habilitante entra a las condiciones declaradas: el lector
        # ve qué falta exactamente (una fuente de mercado), no un bloqueo sin causa.
        for etiqueta in (auth.get("origin_blockers") or mc.get("origin_blockers") or []):
            if isinstance(etiqueta, str) and etiqueta not in blockers:
                blockers.append(etiqueta)
        if val.get("motivo_no_aplica") and str(val["motivo_no_aplica"]) not in blockers:
            blockers.append(str(val["motivo_no_aplica"]))
    sector_met = (mc.get("sector_metodologico") or {})
    if aut and mc.get("market_methodology_id"):
        # S2 · El identificador sellado (`market_methodology_id`) sigue viajando en su
        # campo de máquina (`:738` y provenance) y NO se renombra; lo que NO se imprime
        # es como si fuera el nombre de una fuente: el lector lee la verdad.
        metodo_txt = _am.ETIQUETA_METODO
    elif aut:
        metodo_txt = "Comparación de mercado (metodología declarada por la corrida)"
    else:
        metodo_txt = _dato(val.get("motivo_no_aplica"), "Metodología no aplicada")

    return {
        "decision": {
            "observations": list(modelo.get("observations") or []),
            "findings": list(modelo.get("findings") or []),
            "decision_gates": list(modelo.get("decision_gates") or []),
            "disposition": disposicion_,
            "recommendations": list(modelo.get("recommendations") or []),
            "human_review": (modelo.get("human_reviews") or [{}])[0],
            "shadow_manifest": (modelo.get("shadow_manifest") or {}),
            "visual_assets": list(modelo.get("visual_assets") or []),
            "matrix": matriz,
            "board": tablero_unico[:5],
            "gate_decisions": {g: (c.get("decision")) for g, c in compuertas.items()},
            # (A) `gate_state` viaja junto a `decision`: vocabulario CERRADO CLOSED/OPEN.
            # Los dos campos conviven; ninguno sustituye al otro.
            "gate_states": {g: (c.get("gate_state")) for g, c in compuertas.items()},
            "gate_reasons": {g: (c.get("reasons") or [None])[0] for g, c in compuertas.items()},
            "gate_blocking": {g: list(c.get("blocking_conditions") or [])
                              for g, c in compuertas.items()},
        },
        "indicadores": indicadores_6,
        "hallazgos": operacion,
        "coherencia": [f for f in findings if str(f.get("codigo") or "").upper() == "H-COH"],
        "coherencia_attrs": coherencia_attrs,
        "indicadores": indicadores,
        "ctx": {"area": urb.get("area"), "ciudad": rs.get("ciudad"),
                "regimen": urb.get("condicion_juridica"),
                "uso": urb.get("destino_economico"),
                "valor_estimado": valor_estimado_txt,
                "direccion": direccion_ejecutiva,
                "torre": torre, "apartamento": apto, "unidad": unidad,
                "general": general},
        "legal": {
            "titulares": ([{
                "nombre": ts.get("titulares"),
                "tipo": "declarado en el folio",
                "documento": "en el certificado",
                "participacion": "según el folio",
                "adquisicion": _dato(ts.get("modalidad_adquisicion")),
                "adquisicion_evidencia": _dato(ts.get("modalidad_evidencia")),
                # Un literal «VERIFICADO» aquí afirmaba como hecho un atributo que el
                # MISMO dictus declara en conflicto abierto (P2/P3): el estado sale de
                # la única verdad por atributo.
                "verificacion": verdad_atributos.get("titulares", dse.VERIFICADO),
            }] if ts.get("titulares") else []),
            "gravamenes": [
                {"severidad": "ALTO",
                 "titulo": f"{_v(g.get('tipo'))} (Anot. {_v(g.get('anotacion'))})",
                 "detalle": _v(g.get("partes")),
                 "estado": _v(g.get("estado"), "vigente"),
                 "accion": _accion_para_carga(g, findings)["accion"],
                 "accion_origen": _accion_para_carga(g, findings)["origen"]}
                for g in (ts.get("gravamenes_vigentes") or [])],
            "condiciones": condiciones,
            "anotaciones_total": ts.get("anotaciones_total"),
            "circulo": _dato(ts.get("circulo_registral")),
            "actos_adquisicion": ts.get("actos_adquisicion") or [],
        },
        "contrapartes": {
            "listas": listas,
            "columnas": [COLUMNA_LISTA.get(li, li) for li in listas],
            "listas_detalle": [{"sigla": li, "nombre": NOMBRE_LISTA.get(li, li)}
                               for li in listas],
            "sujetos": _sujetos_de_screening(scr, listas) or [{
                "nombre": "Sin contrapartes declaradas en esta corrida", "tipo": "—",
                "documento": None, "rol": "—", "por_lista": {}, "resultado": "INCOMPLETA"}],
            # §14: el RESULTADO del match depende de la consulta (¿se revisaron los
            # sujetos contra las listas?) y NO del sellado de la evidencia. Mezclarlos
            # convertía una cadena sin sellar en «resultado incompleto».
            "match_global": ("COINCIDENCIA REQUIERE REVISIÓN"
                             if scr.get("matched_subjects")
                             else "SIN COINCIDENCIAS RELEVANTES"
                             if cadena_cerrada
                             else "VERIFICACIÓN INCOMPLETA"),
            # §14: el RESULTADO del match y la INTEGRIDAD de la evidencia son dos
            # conceptos distintos: la cadena sin sellar no vuelve «incompleto» un
            # screening que sí consultó las tres listas.
            "evidencia": {
                "sello": sello_manifiesto,
                "cadena": str(scr.get("evidence_chain_status") or "no declarada"),
                "sellado": sellado,
                "cadena_cerrada": str(scr.get("evidence_chain_status") or "") == "SEALED",
                "creadas": scr.get("evidence_created_count") or scr.get("evidence_created"),
                "esperadas": scr.get("evidence_expected_count") or scr.get("evidence_expected"),
                "cobertura": scr.get("coverage_status"),
                "sujetos_revisados": scr.get("subjects_screened"),
                "sujetos_declarados": scr.get("subjects_declared"),
                "listas_consultadas": len(listas),
            },
        },
        "preparacion": [
            ("COMPRA / VENTA", "PREPARADA" if not operacion else "REQUIERE_REVISION",
             "El expediente reúne identidad, títulos, contrapartes y valor; las condiciones "
             "anteriores son del comprador y del vendedor."),
            ("CRÉDITO HIPOTECARIO", "PREPARADA" if aut else "INCOMPLETO",
             "DICTUS no aprueba crédito: entrega el expediente verificable para que el banco "
             "evalúe garantía, prelación y riesgo."),
            ("SEGURO DE TÍTULO", "PREPARADA" if sellado else "REQUIERE_REVISION",
             # §15: el texto dice lo MISMO que el sello impreso tres bloques más arriba.
             ("DICTUS no asegura ni declara asegurable: entrega hechos comprobados y su "
              "evidencia sellada para el suscriptor." if sellado else
              "DICTUS no asegura ni declara asegurable: entrega hechos comprobados con "
              "evidencia trazable, pendiente de sellado.")),
        ],
        "urbano": {"filas": [
            {"etiqueta": "Destino económico (catastro)",
             "valor": urb.get("destino_economico"),
             "estado": _estado_atributo("destino_economico", urb.get("destino_economico")),
             "nota": _nota_atributo("destino_economico")},
            {"etiqueta": "Uso / actividad POT",
             "valor": _dato((mc.get("uso") or {}).get("value")) or urb.get("area_actividad"),
             "estado": _estado_urb("uso_pot"), "nota": _nota_urb("uso_pot")},
            {"etiqueta": "Tratamiento urbanístico",
             "valor": _dato(urb.get("tratamiento")),
             "estado": _estado_urb("tratamiento"), "nota": _nota_urb("tratamiento")},
            {"etiqueta": "Altura / edificabilidad",
             "valor": (f"Hasta {urb.get('altura_maxima')} pisos"
                       if _dato(urb.get("altura_maxima")) else None),
             "estado": _estado_urb("altura_maxima"), "nota": _nota_urb("altura_maxima")},
            {"etiqueta": "Clase de suelo", "valor": _dato(urb.get("clase_suelo")),
             "estado": _estado_atributo("clase_suelo", urb.get("clase_suelo")),
             "nota": (None if urb.get("clase_suelo") else
                      "La capa de clase de suelo no viene en las capas POT de esta corrida: "
                      "sin dato de fuente.")},
            {"etiqueta": "Estrato", "valor": _dato(urb.get("estrato")),
             "estado": _estado_atributo("estrato", urb.get("estrato")),
             "nota": _nota_atributo("estrato")},
            {"etiqueta": "Barrio", "valor": _dato(urb.get("barrio")),
             "estado": _estado_atributo("barrio", urb.get("barrio")),
             "nota": _nota_atributo("barrio")},
            {"etiqueta": "Localidad / comuna", "valor": _dato(urb.get("localidad")),
             "estado": _estado_atributo("localidad", urb.get("localidad")),
             "nota": _nota_atributo("localidad")},
        ]},
        "riesgos": [
            {"tipo": "Inundación", "nivel": _dato(risk.get("inundacion")),
             "implicacion": "La capa de inundación del POT no se evaluó en esta corrida: se "
                            "declara NO EVALUADO, no «sin riesgo»."},
            {"tipo": "Remoción en masa / amenaza del POT",
             "nivel": _dato(risk.get("amenaza_remocion_masa")),
             "implicacion": "Nivel de la capa oficial aplicable al polígono del predio."},
            {"tipo": "Riesgo no mitigable", "nivel": _dato(risk.get("riesgo_no_mitigable")),
             "implicacion": "Un riesgo no mitigable condiciona el uso, la financiación y la "
                            "póliza: se declara con la fuente que lo establece."},
            {"tipo": "Otras amenazas declaradas", "nivel": _dato(risk.get("areas_en_riesgo")),
             "implicacion": "Zonificación de riesgo del POT aplicable al predio."},
        ],
        "entorno": {
            "categorias": [
                {"nombre": c,
                 "conteo": (poi.get("por_categoria", {}).get(c) or {}).get("count", 0),
                 "estado": ((poi.get("por_categoria", {}).get(c) or {}).get("status")
                            or "NOT_EVALUATED"),
                 "mas_cercano_m": (poi.get("por_categoria", {}).get(c) or {}).get("mas_cercano_m"),
                 "mas_cercano": (poi.get("por_categoria", {}).get(c) or {}).get("mas_cercano"),
                 "items": (poi.get("por_categoria", {}).get(c) or {}).get("items") or []}
                for c in ("Salud", "Educacion", "Comercio", "Recreacion")],
            "radio_m": 2000,
            "fuentes_consultadas": poi.get("sources_succeeded") or [],
            "fuentes_intentadas": poi.get("sources_attempted") or [],
            "consulta": poi.get("queried_at"),
            "total_items": poi.get("item_count"),
            "accesibilidad": [
                ("Barrio / sector oficial", _dato(urb.get("barrio"))),
                ("Localidad", _dato(urb.get("localidad"))),
                ("Coordenada oficial",
                 (lambda c: f"{c['lat']:.5f}, {c['lon']:.5f}" if c.get("lat") else None)(
                     mc.get("coordinates") or {})),
                ("Procedencia de la coordenada", _dato(mc.get("coordinate_source"))),
            ],
        },
        "solar": solar,
        "visual": vis,
        "identidad": {
            # (B) El ORIGEN de cada hecho de identidad viaja declarado con su procedencia
            # real (evidencias selladas de esta corrida). Es el mismo contrato que ya
            # exige la valoración: un hecho sin origen no puede imprimirse VERIFICADO.
            "origen": origen_identidad,
            "filas": [
                {"etiqueta": "Dirección oficial",
                 "valor": (base_dir + (f" · {sufijo}" if sufijo else "")) if base_dir else None,
                 "estado": _estado_atributo("direccion", base_dir, origen_identidad),
                 "nota": _nota_atributo("direccion"),
                 "origin": origen_identidad},
                {"etiqueta": "Matrícula", "valor": pi.get("folio"),
                 # §El certificado adjunto es lo que sostiene la matrícula: sin CTL la
                 # fila NO puede decir VERIFICADO (antes era un literal incondicional).
                 "estado": _estado_atributo(
                     "matricula", pi.get("folio") if ts.get("certificado_adjuntado") else None,
                     origen_identidad),
                 "nota": (None if ts.get("certificado_adjuntado") else
                          "Sin certificado de tradición y libertad adjunto en esta corrida."),
                 "origin": origen_identidad},
                {"etiqueta": "NUPRE", "valor": pi.get("nupre"),
                 "estado": _estado_atributo("nupre", pi.get("nupre"), origen_identidad),
                 "nota": _nota_atributo("nupre"),
                 "origin": origen_identidad},
                {"etiqueta": "Número predial", "valor": pi.get("codigo_catastral"),
                 "estado": _estado_atributo("numero_predial", pi.get("codigo_catastral"),
                                            origen_identidad),
                 "nota": _nota_atributo("numero_predial"),
                 "origin": origen_identidad},
                {"etiqueta": "Unidad (torre / apartamento)", "valor": pi.get("unidad"),
                 "estado": _estado_atributo("unidad", pi.get("unidad"), origen_identidad),
                 "nota": _nota_atributo("unidad"),
                 "origin": origen_identidad},
                {"etiqueta": "Área", "valor": area_txt,
                 "estado": _estado_atributo("area", urb.get("area"), origen_identidad),
                 "nota": _nota_atributo(
                     "area", None if urb.get("area") else "Sin área declarada en la entrada."),
                 "origin": origen_identidad},
                {"etiqueta": "Régimen jurídico", "valor": urb.get("condicion_juridica"),
                 "estado": _estado_atributo("regimen_juridico", urb.get("condicion_juridica"),
                                            origen_identidad),
                 "nota": _nota_atributo("regimen_juridico"),
                 "origin": origen_identidad},
                {"etiqueta": "Uso (destino catastral)", "valor": urb.get("destino_economico"),
                 "estado": _estado_atributo("destino_economico", urb.get("destino_economico"),
                                            origen_identidad),
                 "nota": _nota_atributo("destino_economico"),
                 "origin": origen_identidad},
                {"etiqueta": "Tipología",
                 "valor": _valor_tipologia(),
                 "estado": _estado_tipologia(),
                 "nota": ("Inferida del régimen/condición registral: la fuente no declara la "
                          "unidad física. Requiere validación."
                          if _tipologia_inferida(mc, urb) else None),
                 "origin": origen_identidad},
            ],
            # §21: identidad y geometría son DOS conceptos; el binding se explica en
            # lenguaje llano en vez de imprimirse como contradicción.
            "identidad_estado": ("VERIFICADA" if pi.get("identity_verified")
                                 else "REQUIERE VALIDACIÓN"),
            "identidad_detalle": ("Matrícula, NUPRE y número predial resueltos y ligados "
                                  f"entre sí ({_v(pi.get('resolution_method'))})."),
            # (C) La etiqueta nombra el ATRIBUTO EXACTO que el estado describe: el
            # BINDING de la geometría oficial contra la identidad canónica. NO es el
            # valor de la coordenada (atributo `coordenada`, con su propio estado en P4).
            "geometria_atributo": ATRIBUTO_GEOMETRIA_BINDING,
            "geometria_etiqueta": "Binding de la geometría oficial",
            "geometria_estado": _geometria_estado(mc),
            "geometria_detalle": _geometria_detalle(mc),
        },
        # §32/§33 · ESTIMACIÓN ECONÓMICA (Fase 3): la salida del motor, con su contrato
        # de impresión para la P1 y la P6. Es un hecho DISTINTO del estado de valoración
        # de la corrida (`valor`): aquí vive lo que DICTUS estima; allí, lo que la
        # corrida autoriza.
        "estimacion": _seccion_estimacion(rs, modelo, hist),
        "valor": {
            "autorizado": aut,
            "consolidado": _pesos(val.get("consolidado")),
            "rango": _pesos(val.get("banda_baja")),
            "rango_alto": _pesos(val.get("banda_alta")),
            "area": area_txt,
            "valor_m2": (_pesos(val.get("value_m2")) + " / m²" if val.get("value_m2") else None),
            "sector": _dato(sector_met.get("matched_sector")) or _dato(val.get("sector")),
            "sector_match": sector_met.get("match_type"),
            # S3 · `market_rate_source` sale del artefacto local de metodología. NO se
            # muta el YAML: la etiqueta verdadera se aplica al RENDERIZAR (idempotente).
            "tasa_fuente": _am.etiqueta_tasa(_dato(mc.get("market_rate_source"))),
            # ── P4 · ORIGEN junto al valor ────────────────────────────────────
            # `origin` es el origen EFECTIVO de la tasa (vocabulario cerrado) y
            # `origin_gate` dice si esa procedencia HABILITA emitir la cifra. Los dos
            # viajan juntos: un valor sin origen habilitante no se imprime.
            "origin": (val.get("origin") or mc.get("origin") or auth.get("origin")),
            "origin_etiqueta": (mc.get("origin_etiqueta") or auth.get("origin_etiqueta")),
            "origin_gate": bool(val.get("origin_gate") is True
                                or auth.get("origin_gate") is True),
            "origin_blockers": list(auth.get("origin_blockers")
                                    or mc.get("origin_blockers") or []),
            "precio_m2_origin": ((val.get("origins") or {}).get("market_value_m2")),
            "fecha": fecha_consulta,
            "vigencia": (f"{fecha_consulta} · vigencia de la metodología aplicada"
                         if fecha_consulta else None),
            "metodologia": metodo_txt,
            "metodologia_version": mc.get("market_methodology_version"),
            "blockers": blockers,
            "motivo": val.get("motivo_no_aplica"),
            "decision": ((compuertas.get(dd.VALUATION_GATE) or {}).get("decision")),
            "identidad_decision": ((compuertas.get(dd.IDENTITY_GATE) or {}).get("decision")),
        },
    }

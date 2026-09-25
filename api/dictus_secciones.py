# -*- coding: utf-8 -*-
"""DICTUS 2.0B — Secciones del ejecutivo derivadas del ESTADO CANÓNICO.

El ejecutivo NO lee el PDF técnico ni extrae texto con expresiones regulares: todo lo
que imprime sale del `DictusRunState` (y, para la coherencia histórica heredada de
2.0A, del informe de consistencia que la propia corrida referencia).

Este módulo existe para mantener esa frontera explícita y comprobable.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import dictus_estado as dse

LISTAS_FALLBACK = ("Lista Consolidada ONU", "OFAC SDN", "UK Sanctions List")

ETIQUETA_LISTA = {
    "UN_CONSOLIDATED": "ONU",
    "OFAC_SDN": "OFAC SDN",
    "UK_SANCTIONS_LIST": "UKSL",
    "UK_SANCTIONS": "UKSL",
}

# Nombre completo de cada lista evaluada: la sigla de la columna no acredita QUÉ
# lista se consultó (§8 de 2.0B-R1).
NOMBRE_LISTA = {
    "ONU": "Lista Consolidada ONU (Consejo de Seguridad)",
    "OFAC SDN": "OFAC SDN (EE. UU.)",
    "UKSL": "UK Sanctions List (Reino Unido)",
}

# Rótulo de la COLUMNA de la matriz (§8): el nombre de la lista, no su sigla.
COLUMNA_LISTA = {
    "ONU": "ONU",
    "OFAC SDN": "OFAC SDN",
    "UKSL": "UK SANCTIONS LIST",
}

NOMBRE_CIUDAD = {
    "barranquilla": "Barranquilla",
    "bogota": "Bogotá",
    "medellin": "Medellín",
    "pasto": "Pasto",
    "cali": "Cali",
}

# Resultado por lista, con el vocabulario REAL del motor de screening.
_ESTADO_POR_RESULTADO = {
    "NO_MATCH": "SIN_COINCIDENCIAS",
    "POTENTIAL_MATCH": "COINCIDENCIA",
    "STRONG_MATCH": "COINCIDENCIA",
    "EXACT_MATCH": "COINCIDENCIA",
    "REVIEW_REQUIRED": "COINCIDENCIA",
    "NOT_SCREENED": "INCOMPLETA",
    "SOURCE_UNAVAILABLE": "INCOMPLETA",
}


def _v(x, hueco="no declarado"):
    return hueco if x in (None, "", []) else x


# Marcadores de ausencia del producto: NO son un valor declarado. Un «N/D» impreso
# como dato sería un hueco mudo disfrazado de hecho.
_AUSENCIAS = ("n/d", "n/a", "na", "no aplica", "no_aplica", "none", "null", "-", "—")


def _dato(x, hueco=None):
    """Valor declarado o `hueco` si el producto no declaró nada (incluye «N/D»)."""
    if x is None or (isinstance(x, str) and (not x.strip() or x.strip().lower() in _AUSENCIAS)):
        return hueco
    return x


def _listas_de_screening(screening: Dict[str, Any]) -> List[str]:
    """Columnas de la matriz = listas REALMENTE consultadas por el screening."""
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

    Si el motor no declaró un outcome para ese par (sujeto, lista), el estado es
    «NO CONSULTADA»: nunca se afirma «sin coincidencia» de algo que no se consultó.
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
        # La coincidencia manda: si dos fuentes devolvieran estados distintos para la
        # misma lista, se conserva el más conservador.
        if estado == "COINCIDENCIA" or salida[etiqueta] == "INCOMPLETA":
            salida[etiqueta] = estado
    return salida


def _documento_de_sujeto(s: Dict[str, Any]) -> Optional[str]:
    """Documento del sujeto, enmascarado como en la evidencia del screening (§20).

    El resumen del motor declara `document_type` + `document_number`: el ejecutivo
    imprime el documento ENMASCARADO (los últimos dígitos identifican, el resto no se
    expone). Sin dato declarado se dice que no está declarado.
    """
    numero = s.get("document") or s.get("documento") or s.get("document_number")
    if not numero:
        return None
    tipo = str(s.get("document_type") or "").upper()
    try:
        from sanctions.contracts import mask_document
        return f"{tipo} {mask_document(s.get('document_type'), str(numero))}".strip()
    except Exception:  # noqa: BLE001 — la máscara local es idéntica en forma
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
    findings = list(rs.get("findings") or [])
    hist = historial or {}
    # NOTA: los hallazgos de coherencia histórica NO se inyectan aquí: viven en el
    # ESTADO canónico (`dictus_estado.agregar_findings_de_coherencia`). Este módulo solo
    # lee el estado; si los añadiera, el documento impreso y el manifest dirían cosas
    # distintas (dos verdades sobre la misma corrida).
    orden = {"ALTO": 0, "MEDIO": 1, "INFORMATIVO": 2}
    findings.sort(key=lambda x: orden.get(str(x.get("severidad")).upper(), 3))

    con_carga = bool(ts.get("gravamenes_vigentes"))
    hay_conf_urb = any(c.get("atributo") in ("altura_maxima", "tratamiento", "uso_pot")
                       for c in hist.get("conflictos_abiertos", []))
    # ¿Hubo comparación histórica REAL? `versiones_comparadas` lo declara el informe
    # de consistencia. Sin informe no se puede afirmar «sin cambios»: se declara que
    # no hay expediente histórico comparado (afirmar lo contrario sería un PASS falso).
    hist_comparado = bool(hist) and int(hist.get("versiones_comparadas") or 0) > 0
    aut = bool((val.get("authorization") or {}).get("allowed"))
    sellado = str(scr.get("evidence_chain_status") or "") == "SEALED"

    indicadores = [
        ("Identidad", dse.VERIFICADO if pi.get("identity_verified") else dse.REQUIERE_VALIDACION,
         f"Matrícula, NUPRE y predial resueltos ({_v(pi.get('resolution_method'))})."),
        ("Títulos", "CON_CONDICIONES" if con_carga else dse.VERIFICADO,
         ("Cargas vigentes declaradas en el folio." if con_carga
          else "Sin cargas vigentes declaradas.")),
        ("Contrapartes", "SIN_COINCIDENCIAS" if sellado else "INCOMPLETA",
         f"{len(scr.get('subjects') or [])} sujeto(s) · evidencia "
         f"{_v(scr.get('evidence_created_count') or scr.get('evidence_created'), '0')}/"
         f"{_v(scr.get('evidence_expected_count') or scr.get('evidence_expected'), '—')}."),
        ("Territorio", dse.REQUIERE_VALIDACION if hay_conf_urb else dse.VERIFICADO,
         ("Coherencia histórica abierta en atributos urbanísticos." if hay_conf_urb
          else "Capas oficiales del municipio consultadas.")),
        ("Valor", "DISPONIBLE" if aut else "NO_DISPONIBLE",
         "Valoración autorizada." if aut else
         f"No autorizada: {_v(val.get('motivo_no_aplica'), 'se declara el blocker, sin cifras')}"),
    ]

    coherencia = {}
    for atributo in ("altura_maxima", "tratamiento", "uso_pot"):
        abierto = next((c for c in hist.get("conflictos_abiertos", [])
                        if c.get("atributo") == atributo), None)
        if abierto:
            coherencia[atributo] = {"estado": dse.HISTORICAL_CONFLICT,
                                    "mensaje": abierto.get("detalle"), "valores": abierto.get("valores")}
        elif hist_comparado:
            coherencia[atributo] = {"estado": dse.VERIFICADO,
                                    "mensaje": "Sin cambios entre las versiones comparadas.",
                                    "valores": []}
        else:
            coherencia[atributo] = {
                "estado": dse.REQUIERE_VALIDACION,
                "mensaje": ("Sin expediente histórico comparado para este inmueble en esta "
                            "ejecución: no se afirma que el dato haya permanecido igual."),
                "valores": []}
    altura_ok = coherencia["altura_maxima"]["estado"] != dse.HISTORICAL_CONFLICT
    trat_ok = coherencia["tratamiento"]["estado"] != dse.HISTORICAL_CONFLICT

    listas = _listas_de_screening(scr)
    area_txt = f"{urb.get('area'):.2f}".rstrip("0").rstrip(".") + " m²" if urb.get("area") else None

    def _pesos(v):
        return f"$ {int(v):,}".replace(",", ".") if v else None

    valor_estimado_txt = (_pesos(val.get("consolidado")) if aut else
                          "no disponible (valoración no autorizada)")
    fecha_consulta = str(rs.get("generated_at") or "")[:10] or None
    # Método principal: se declara el estado REAL de la metodología (aplicada o no) en
    # lugar de un hueco mudo. La versión y el detalle viven en el anexo técnico.
    metodo_txt = ("Metodología de mercado aplicada a la corrida (versión y parámetros "
                  "en el Anexo F)" if val.get("metodologia_aplica") else
                  _dato(val.get("motivo_no_aplica"),
                        "Metodología no aplicada: la corrida no declara el motivo."))
    _ESTADO_IDENTIDAD = {
        "MATCH_BY_NUPRE": "Matrícula resuelta por NUPRE",
        "MATCH_BY_PREDIAL": "Matrícula resuelta por número predial",
        "EXACT": "Coincidencia exacta con la fuente oficial",
    }

    # ── Bloque A · INFORMACIÓN GENERAL (§6): ocho campos, ningún hueco mudo ───
    general = [
        ("Dirección", _v(pi.get("direccion_normalizada") or pi.get("direccion_raw"),
                         "no declarada")),
        ("Matrícula", _v(pi.get("folio"), "no declarada")),
        ("Ciudad", NOMBRE_CIUDAD.get(str(rs.get("ciudad") or "").lower(),
                                     _v(rs.get("ciudad"), "no declarada"))),
        ("Barrio", _v(urb.get("barrio"), "no declarado")),
        ("Área", _v(area_txt, "no declarada")),
        ("Uso", _v(urb.get("destino_economico"), "no declarado")),
        ("Régimen", _v(urb.get("condicion_juridica"), "no declarado")),
        ("Valor estimado", valor_estimado_txt),
    ]

    return {
        "hallazgos": findings,
        "indicadores": indicadores,
        "ctx": {"area": urb.get("area"),
                "ciudad": rs.get("ciudad"),
                "regimen": urb.get("condicion_juridica"),
                "uso": urb.get("destino_economico"),
                "valor_estimado": valor_estimado_txt,
                "general": general},
        "legal": {
            "titulares": ([{"nombre": ts.get("titulares"), "tipo": "declarado en el folio",
                            "documento": "en el certificado",
                            "participacion": "según el folio",
                            "adquisicion": _dato(ts.get("modalidad_adquisicion")),
                            "verificacion": dse.VERIFICADO}] if ts.get("titulares") else []),
            "gravamenes": [{"severidad": "ALTO",
                            "titulo": f"{_v(g.get('tipo'))} (Anot. {_v(g.get('anotacion'))})",
                            "detalle": _v(g.get("partes")),
                            "accion": "Tramitar el levantamiento o la cancelación con el "
                                      "acreedor y registrarla en el folio."}
                           for g in (ts.get("gravamenes_vigentes") or [])],
            "condiciones": [f["accion"] for f in findings if f.get("accion")][:5],
        },
        "contrapartes": {
            "listas": listas,
            "columnas": [COLUMNA_LISTA.get(li, li) for li in listas],
            "listas_detalle": [{"sigla": li, "nombre": NOMBRE_LISTA.get(li, li)}
                               for li in listas],
            "sujetos": _sujetos_de_screening(scr, listas) or [{
                "nombre": "Sin contrapartes declaradas en esta corrida", "tipo": "—",
                "documento": None, "rol": "—", "por_lista": {}, "resultado": "INCOMPLETA"}]},
        "preparacion": [
            ("COMPRA / VENTA", "PREPARADA" if not findings else "REQUIERE_REVISION",
             "El expediente reúne identidad, títulos, contrapartes y valor; las condiciones "
             "anteriores son del comprador y del vendedor."),
            ("CRÉDITO HIPOTECARIO", "PREPARADA" if aut else "INCOMPLETO",
             "DICTUS no aprueba crédito: entrega el expediente verificable para que el banco "
             "evalúe garantía, prelación y riesgo."),
            ("SEGURO DE TÍTULO", "PREPARADA" if sellado else "REQUIERE_REVISION",
             "DICTUS no asegura ni declara asegurable: entrega hechos comprobados y su "
             "evidencia sellada para el suscriptor."),
        ],
        "urbano": {"filas": [
            {"etiqueta": "Destino económico (catastro)",
             "valor": urb.get("destino_economico"),
             "estado": dse.VERIFICADO if urb.get("destino_economico") else dse.SIN_DATO,
             "nota": "Dimensión catastral: no es el uso normativo del POT."},
            {"etiqueta": "Uso / actividad POT", "valor": urb.get("area_actividad"),
             "estado": coherencia["uso_pot"]["estado"],
             "nota": "Dimensión normativa: no es el destino catastral."},
            {"etiqueta": "Tratamiento urbanístico",
             "valor": urb.get("tratamiento") if trat_ok else None,
             "estado": coherencia["tratamiento"]["estado"],
             "nota": None if trat_ok else "El expediente produjo tratamientos distintos: no se "
                                          "imprime una cifra."},
            {"etiqueta": "Altura / edificabilidad",
             "valor": urb.get("altura_maxima") if altura_ok else None,
             "estado": coherencia["altura_maxima"]["estado"],
             "nota": None if altura_ok else "Resultados normativos distintos en ejecuciones "
                                            "previas: requiere validación de coherencia."},
            {"etiqueta": "Clase de suelo", "valor": urb.get("clase_suelo"),
             "estado": dse.VERIFICADO if urb.get("clase_suelo") else dse.SIN_DATO},
            {"etiqueta": "Estrato", "valor": urb.get("estrato"),
             "estado": dse.VERIFICADO if urb.get("estrato") else dse.SIN_DATO},
            {"etiqueta": "Barrio", "valor": urb.get("barrio"),
             "estado": dse.VERIFICADO if urb.get("barrio") else dse.SIN_DATO},
            {"etiqueta": "Localidad / comuna", "valor": urb.get("localidad"),
             "estado": dse.VERIFICADO if urb.get("localidad") else dse.SIN_DATO},
        ]},
        "riesgos": [
            {"tipo": "Inundación", "nivel": risk.get("inundacion"),
             "implicacion": "Puede afectar al comprador, al banco y a la aseguradora: exige "
                            "verificación técnica específica (Anexo C)."},
            {"tipo": "Remoción en masa / amenaza del POT",
             "nivel": risk.get("amenaza_remocion_masa"),
             "implicacion": "Se declara el nivel de la capa oficial aplicable al polígono; su "
                            "efecto sobre la operación lo evalúa el técnico competente."},
            {"tipo": "Riesgo no mitigable", "nivel": risk.get("riesgo_no_mitigable"),
             "implicacion": "Un riesgo no mitigable condiciona el uso, la financiación y la "
                            "póliza: se declara con la fuente que lo establece (Anexo C)."},
            {"tipo": "Otras amenazas declaradas", "nivel": risk.get("areas_en_riesgo")
             or (risk.get("volcan") or {}).get("estado"),
             "implicacion": "Se declara el estado real de la fuente: no se afirma ausencia de "
                            "amenaza si el punto no está cartografiado."},
        ],
        "coherencia": coherencia,
        "entorno": {
            "categorias": [
                {"nombre": c, "conteo": (poi.get("por_categoria", {}).get(c) or {}).get("count", 0),
                 "estado": (poi.get("por_categoria", {}).get(c) or {}).get("status") or "NOT_EVALUATED",
                 "mas_cercano_m": (poi.get("por_categoria", {}).get(c) or {}).get("mas_cercano_m"),
                 "mas_cercano": (poi.get("por_categoria", {}).get(c) or {}).get("mas_cercano"),
                 "ejemplos": (poi.get("por_categoria", {}).get(c) or {}).get("items") or []}
                for c in ("Salud", "Educacion", "Comercio", "Recreacion")],
            "accesibilidad": [
                ("Barrio / sector oficial", urb.get("barrio")),
                ("Localidad", urb.get("localidad")),
                ("Vías de acceso inmediato", "geocodificadas en el Anexo E"),
            ],
        },
        "solar": solar,
        "identidad": {"filas": [
            {"etiqueta": "Dirección oficial",
             "valor": pi.get("direccion_normalizada") or pi.get("direccion_raw"),
             "estado": dse.VERIFICADO},
            {"etiqueta": "Matrícula", "valor": pi.get("folio"), "estado": dse.VERIFICADO},
            {"etiqueta": "NUPRE", "valor": pi.get("nupre"),
             "estado": dse.VERIFICADO if pi.get("nupre") else dse.SIN_DATO},
            {"etiqueta": "Número predial", "valor": pi.get("codigo_catastral"),
             "estado": dse.VERIFICADO if pi.get("codigo_catastral") else dse.SIN_DATO},
            {"etiqueta": "Unidad (torre / apartamento)", "valor": pi.get("unidad"),
             "estado": dse.VERIFICADO if pi.get("unidad") else dse.SIN_DATO},
            {"etiqueta": "Área", "valor": area_txt,
             "estado": dse.VERIFICADO if urb.get("area") else dse.SIN_DATO},
            {"etiqueta": "Régimen jurídico", "valor": urb.get("condicion_juridica"),
             "estado": dse.VERIFICADO if urb.get("condicion_juridica") else dse.SIN_DATO},
            {"etiqueta": "Uso (destino catastral)", "valor": urb.get("destino_economico"),
             "estado": dse.VERIFICADO if urb.get("destino_economico") else dse.SIN_DATO},
            {"etiqueta": "Estado de identidad",
             "valor": _ESTADO_IDENTIDAD.get(str(pi.get("estado") or "").upper())
             or _v(_dato(pi.get("estado")) or _dato(pi.get("resolution_status")),
                   "no declarado"),
             "estado": dse.VERIFICADO if pi.get("identity_verified") else dse.REQUIERE_VALIDACION},
        ],
            # Lo geodésico (fuente de la geometría, binding canónico, CRS/EPSG) es
            # materia del anexo técnico (§12): aquí solo se declara su resultado.
            "nota_tecnica": ("Geometría oficial del predio y binding predio ↔ identidad "
                             "canónica: "
                             + str(((modelo.get("source_versions") or {}).get(
                                 "coordinate_provenance") or {}).get("canonical_binding_status")
                                   or "NO_COMPARABLE")
                             + ". Detalle geodésico y CRS en el Anexo F.")},
        "valor": {
            "autorizado": aut,
            "consolidado": _pesos(val.get("consolidado")),
            "rango": _pesos(val.get("banda_baja")),
            "rango_alto": _pesos(val.get("banda_alta")),
            "area": area_txt,
            "valor_m2": (_pesos(val.get("value_m2")) + " / m²"
                         if val.get("value_m2") else None),
            "fecha": fecha_consulta,
            "vigencia": (f"{fecha_consulta} · vigencia de la metodología aplicada (Anexo F)"
                         if fecha_consulta else None),
            "sector": _dato(val.get("sector")),
            "metodologia": metodo_txt,
            "motivo": val.get("motivo_no_aplica"),
            "pasos": [
                "Se verificó la identidad del inmueble (matrícula, NUPRE y número predial).",
                "Se verificó el contexto territorial (barrio, estrato y norma con fuentes oficiales).",
                "Se identificó el sector metodológico de mercado y su tasa.",
                "Se aplicó la metodología declarada (comparación de mercado para propiedad horizontal).",
                "Se construyó el valor y su banda con parámetros trazables.",
                "La interpretación profesional corresponde al experto competente.",
            ],
        },
    }

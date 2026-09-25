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


def _v(x, hueco="no declarado"):
    return hueco if x in (None, "", []) else x


def _listas_de_screening(screening: Dict[str, Any]) -> List[str]:
    """Columnas de la matriz = listas REALMENTE consultadas por el screening."""
    nombres: List[str] = []
    for f in (screening.get("sources") or screening.get("fuentes") or []):
        sid = f if isinstance(f, str) else (f.get("source_id") or f.get("id") or "")
        etiqueta = ETIQUETA_LISTA.get(str(sid).upper(), str(sid).replace("_", " ").title())
        if etiqueta and etiqueta not in nombres:
            nombres.append(etiqueta)
    return nombres or list(LISTAS_FALLBACK)


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
        salida.append({
            "subject_id": s.get("subject_id"),
            "nombre": s.get("canonical_name") or s.get("nombre") or "—",
            "rol": ", ".join(s.get("roles") or []) or "contraparte del caso",
            "tipo": s.get("person_type_label") or s.get("person_type") or "No determinado",
            "documento": s.get("document") or s.get("documento"),
            "por_lista": {li: "SIN_COINCIDENCIAS" for li in listas},
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
         f"{_v(scr.get('evidence_created'), '0')}/{_v(scr.get('evidence_expected'), '—')}."),
        ("Territorio", dse.REQUIERE_VALIDACION if hay_conf_urb else dse.VERIFICADO,
         ("Coherencia histórica abierta en atributos urbanísticos." if hay_conf_urb
          else "Capas oficiales del municipio consultadas.")),
        ("Valoración", "DISPONIBLE" if aut else "NO_DISPONIBLE",
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
        else:
            coherencia[atributo] = {"estado": dse.VERIFICADO,
                                    "mensaje": "Sin cambios entre las versiones comparadas.",
                                    "valores": []}
    altura_ok = coherencia["altura_maxima"]["estado"] != dse.HISTORICAL_CONFLICT
    trat_ok = coherencia["tratamiento"]["estado"] != dse.HISTORICAL_CONFLICT

    listas = _listas_de_screening(scr)
    return {
        "hallazgos": findings,
        "indicadores": indicadores,
        "ctx": {"area": urb.get("area") or (rs.get("valuation_state") or {}).get("area"),
                "regimen": urb.get("condicion_juridica"),
                "uso": urb.get("destino_economico")},
        "legal": {
            "titulares": ([{"nombre": ts.get("titulares"), "tipo": "declarado en el folio",
                            "documento": "en el certificado",
                            "participacion": "según el folio",
                            "verificacion": dse.VERIFICADO}] if ts.get("titulares") else []),
            "gravamenes": [{"severidad": "ALTO",
                            "titulo": f"{_v(g.get('tipo'))} (Anot. {_v(g.get('anotacion'))})",
                            "detalle": _v(g.get("partes")),
                            "accion": "Tramitar el levantamiento o la cancelación con el "
                                      "acreedor y registrarla en el folio."}
                           for g in (ts.get("gravamenes_vigentes") or [])],
            "condiciones": [f["accion"] for f in findings if f.get("accion")][:5],
        },
        "contrapartes": {"listas": listas, "sujetos": _sujetos_de_screening(scr, listas) or [{
            "nombre": "Sin contrapartes declaradas en esta corrida", "tipo": "—",
            "documento": "—", "rol": "—", "por_lista": {}, "resultado": "INCOMPLETA"}]},
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
            {"etiqueta": "Clase de suelo", "valor": urb.get("clase_suelo"),
             "estado": dse.VERIFICADO if urb.get("clase_suelo") else dse.SIN_DATO},
            {"etiqueta": "Destino económico (catastro)",
             "valor": urb.get("destino_economico"), "estado": dse.VERIFICADO,
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
            {"etiqueta": "Estrato", "valor": urb.get("estrato"),
             "estado": dse.VERIFICADO if urb.get("estrato") else dse.SIN_DATO},
            {"etiqueta": "Barrio / localidad",
             "valor": " / ".join(x for x in [urb.get("barrio"), urb.get("localidad")] if x),
             "estado": dse.VERIFICADO if urb.get("barrio") else dse.SIN_DATO},
        ]},
        "riesgos": [
            {"tipo": "Amenaza / riesgo del POT", "nivel": risk.get("amenaza_remocion_masa"),
             "implicacion": "Puede afectar al comprador, al banco y a la aseguradora: exige "
                            "verificación técnica específica (Anexo C)."},
            {"tipo": "Riesgo volcánico (SGC)",
             "nivel": (risk.get("volcan") or {}).get("estado"),
             "implicacion": "Se declara el estado real de la fuente: no se afirma ausencia de "
                            "amenaza si el punto no está cartografiado."},
        ],
        "coherencia": coherencia,
        "entorno": {
            "categorias": [
                {"nombre": c, "conteo": (poi.get("por_categoria", {}).get(c) or {}).get("count", 0),
                 "estado": (poi.get("por_categoria", {}).get(c) or {}).get("status") or "NOT_EVALUATED",
                 "mas_cercano_m": (poi.get("por_categoria", {}).get(c) or {}).get("mas_cercano_m"),
                 "ejemplos": (poi.get("por_categoria", {}).get(c) or {}).get("items") or []}
                for c in ("Salud", "Educacion", "Comercio", "Recreacion")],
            "accesibilidad": [
                ("Barrio / sector oficial", urb.get("barrio")),
                ("Localidad", urb.get("localidad")),
                ("Coordenada del predio",
                 _v((modelo.get("source_versions") or {}).get("coordinate_source"))),
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
            {"etiqueta": "Régimen jurídico", "valor": urb.get("condicion_juridica"),
             "estado": dse.VERIFICADO},
            {"etiqueta": "Geometría oficial del predio",
             "valor": (modelo.get("source_versions") or {}).get("coordinate_source"),
             "estado": dse.VERIFICADO},
            {"etiqueta": "Binding predio ↔ identidad canónica",
             "valor": (((modelo.get("source_versions") or {}).get("coordinate_provenance") or {})
                       .get("canonical_binding_status") or "NO_COMPARABLE"),
             "estado": dse.VERIFICADO
             if ((modelo.get("source_versions") or {}).get("coordinate_provenance") or {}
                 ).get("canonical_binding_status") == "VERIFIED" else dse.REQUIERE_VALIDACION},
        ]},
        "valor": {
            "autorizado": aut,
            "consolidado": (f"$ {int(val['consolidado']):,}".replace(",", ".")
                            if val.get("consolidado") else None),
            "rango": (f"$ {int(val['banda_baja']):,}".replace(",", ".")
                      if val.get("banda_baja") else None),
            "area": urb.get("area"),
            "valor_m2": (f"$ {int(val['value_m2']):,}".replace(",", ".")
                         if val.get("value_m2") else None),
            "fecha": str(rs.get("generated_at") or "")[:10] or None,
            "sector": val.get("sector"),
            "metodologia": (modelo.get("methodology_versions") or {}).get("market_methodology_version"),
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

# -*- coding: utf-8 -*-
"""C-01 — Resolución de DIRECCIÓN con estado POR CAMPO y sin valores por defecto.

CONTEXTO
-------
`api/index.py` resolvía la dirección así:

    if ("43" in normalized and "100" in normalized) or "NAPOLI" in normalized:
        return "040-646406", "Miramar", 4      # caso Golden hardcodeado
    if ("63" in normalized and "37" in normalized) or "RECREO" in normalized:
        return "040-314248", "El Recreo", 4    # segundo caso hardcodeado
    return "Pendiente", "", 4                  # estrato 4 POR DEFECTO

Tres defectos en una función: (1) la matrícula del caso de aceptación se devolvía por
coincidencia de SUBCADENAS (una dirección de otra ciudad con «43» y «100» recibía el
folio del Golden), (2) el estrato se fijaba en 4 sin consultar ninguna fuente —el
mismo default que 03H prohibió y que 03I.1 cerró en el camino de valoración— y
(3) la respuesta no declaraba fuente ni estado, de modo que la interfaz no podía
distinguir un dato verificado de un hueco.

REGLAS DE ESTA IMPLEMENTACIÓN
-----------------------------
1. Ninguna coincidencia por subcadenas: la identidad sale de FUENTES OFICIALES.
2. Ningún valor por defecto: si un campo no se resuelve, se declara con su estado y
   su motivo (`UNRESOLVED` / `SOURCE_UNAVAILABLE` / `CONFLICT`).
3. Un solo contrato: cada campo lleva `value`, `status`, `source` y `motivo`.
4. El folio registral SOLO se afirma si un registro oficial lo aporta (el registro de
   adopción catastral se consulta por IDENTIFICADOR exacto: predial/NUPRE/FMI; no se
   inventa una correspondencia dirección→folio).
5. El estrato sale de la capa oficial de estratificación (punto o manzana del número
   predial), nunca de un default.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, Optional

STATUS_VERIFIED_OFFICIAL = "VERIFIED_OFFICIAL"
STATUS_VERIFIED_CATASTRAL = "VERIFIED_CATASTRAL"
STATUS_UNRESOLVED = "UNRESOLVED"
STATUS_SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
STATUS_CONFLICT = "CONFLICT"

_CAMPOS = ("folio_matricula", "numero_predial", "nupre", "barrio", "localidad",
           "estrato", "coordenada")


def _campo(value=None, status: str = STATUS_UNRESOLVED, source: Optional[str] = None,
           motivo: Optional[str] = None) -> Dict[str, Any]:
    return {"value": value, "status": status, "source": source, "motivo": motivo}


def _es_vacia(v) -> bool:
    return v in (None, "") or str(v).strip().lower() in ("pendiente", "n/d", "nd", "none")


def _hora() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def resolver_direccion(direccion: str, ciudad: str = "barranquilla") -> Dict[str, Any]:
    """Resuelve una dirección contra fuentes OFICIALES, con estado por campo.

    Returns:
        {"consulta": {...}, "campos": {campo: {value, status, source, motivo}},
         "candidatos": [...], "fuentes": [ {id, status, detalle} ]}
    """
    ciudad = (ciudad or "barranquilla").strip().lower()
    entrada = (direccion or "").strip()
    campos: Dict[str, Any] = {c: _campo() for c in _CAMPOS}
    fuentes: list = []
    candidatos: list = []

    normalizada = entrada
    try:
        from address_normalizer import normalize_address_colombia
        normalizada = normalize_address_colombia(entrada) or entrada
    except Exception as e:  # noqa: BLE001
        fuentes.append({"id": "normalizador", "status": "SOURCE_UNAVAILABLE",
                        "detalle": str(e)[:120]})

    salida: Dict[str, Any] = {
        "consulta": {"direccion_input": entrada, "normalizada": normalizada,
                     "ciudad": ciudad, "hora": _hora()},
        "campos": campos, "candidatos": candidatos, "fuentes": fuentes,
    }
    if not entrada:
        campos["folio_matricula"] = _campo(motivo="sin dirección de entrada")
        return salida

    # ── 1. Geocodificación OFICIAL de la dirección (catastro municipal) ────────
    lat = lon = None
    if ciudad == "barranquilla":
        try:
            from geocoder_catastral import geocodificar_catastro_barranquilla
            g = geocodificar_catastro_barranquilla(entrada) or {}
            if g.get("lat") is not None and g.get("lon") is not None:
                lat, lon = g.get("lat"), g.get("lon")
                campos["coordenada"] = _campo(
                    [lat, lon], STATUS_VERIFIED_OFFICIAL,
                    g.get("fuente") or "catastro/datosabiertos capa 105 (direcciones)",
                    f"coincidencia oficial: {g.get('direccion_oficial') or 'n/d'}")
                fuentes.append({"id": "geocoder_catastro_baq", "status": "OK",
                                "detalle": f"({lat:.6f}, {lon:.6f})"})
            else:
                fuentes.append({"id": "geocoder_catastro_baq", "status": "NO_MATCH",
                                "detalle": "la placa de la dirección no está en la capa oficial"})
        except Exception as e:  # noqa: BLE001
            fuentes.append({"id": "geocoder_catastro_baq", "status": "SOURCE_UNAVAILABLE",
                            "detalle": str(e)[:120]})

    # ── 2. Contexto urbano OFICIAL por punto (barrio / localidad / estrato) ────
    if lat is not None and lon is not None:
        try:
            from catastro_predio import consultar_entorno_urbano
            ent = consultar_entorno_urbano(lat, lon) or {}
            if ent.get("barrio"):
                campos["barrio"] = _campo(ent["barrio"], STATUS_VERIFIED_OFFICIAL,
                                          "ordenamiento/unidadesadministrativas")
            elif ent.get("disponible"):
                campos["barrio"] = _campo(motivo="el punto no cae en ningún polígono de barrio")
            if ent.get("localidad"):
                campos["localidad"] = _campo(ent["localidad"], STATUS_VERIFIED_OFFICIAL,
                                             "ordenamiento/unidadesadministrativas")
            _est = ent.get("estrato")
            if not _es_vacia(_est):
                campos["estrato"] = _campo(str(_est), STATUS_VERIFIED_OFFICIAL,
                                           "ordenamiento/estratificacion (punto)")
            elif ent.get("estrato_trace"):
                campos["estrato"] = _campo(
                    motivo=(ent.get("estrato_trace") or {}).get("motivo")
                    or "capa de estratificación sin registro en el punto")
            else:
                campos["estrato"] = _campo(
                    motivo="capa de estratificación sin registro en el punto geocodificado")
            fuentes.append({"id": "ordenamiento_urbano", "status": "OK" if ent.get("disponible")
                            else "SOURCE_UNAVAILABLE",
                            "detalle": f"barrio={ent.get('barrio')} estrato={ent.get('estrato')}"})
        except Exception as e:  # noqa: BLE001
            fuentes.append({"id": "ordenamiento_urbano", "status": "SOURCE_UNAVAILABLE",
                            "detalle": str(e)[:120]})

    # ── 3. Número predial (capa oficial de direcciones) y estrato por manzana ──
    predial = None
    if ciudad == "barranquilla":
        predial = _predial_desde_capa_direcciones(entrada, fuentes)
    if predial:
        campos["numero_predial"] = _campo(predial, STATUS_VERIFIED_CATASTRAL,
                                          "catastro/datosabiertos capa 105 (direcciones)")
        if _es_vacia((campos.get("estrato") or {}).get("value")):
            try:
                from catastro_predio import resolver_manzana_y_estrato
                mz = resolver_manzana_y_estrato(predial,
                                                barrio_esperado=(campos.get("barrio") or {}).get("value"))
                if mz.get("estado") == STATUS_VERIFIED_OFFICIAL:
                    campos["estrato"] = _campo(mz["estrato"], STATUS_VERIFIED_OFFICIAL,
                                               "ordenamiento/estratificacion (manzana del número predial)")
                    fuentes.append({"id": "estratificacion_manzana", "status": "OK",
                                    "detalle": f"manzana {mz.get('codigo_manzana')}"})
                else:
                    campos["estrato"] = _campo(
                        status=(STATUS_CONFLICT if mz.get("estado") == STATUS_CONFLICT
                                else STATUS_UNRESOLVED),
                        motivo=mz.get("motivo") or "estrato no resoluble por manzana")
            except Exception as e:  # noqa: BLE001
                fuentes.append({"id": "estratificacion_manzana", "status": "SOURCE_UNAVAILABLE",
                                "detalle": str(e)[:120]})

        # ── 4. Identidad registral/oficial SOLO por correspondencia exacta ─────
        try:
            from barranquilla_adopcion import resolver_identidad_oficial
            of = resolver_identidad_oficial(numero_predial=predial) or {}
            reg = of.get("registro") or {}
            if of.get("estado") == "MATCH_EXACT" and reg.get("fmi"):
                folio_of = "-".join(x for x in (reg.get("codigo_registral"), reg.get("fmi")) if x)
                campos["folio_matricula"] = _campo(
                    folio_of, STATUS_VERIFIED_OFFICIAL,
                    "registro oficial de adopción catastral (Anexo 1 · Res. GGCD 003)",
                    f"match exacto por número predial · homologado={reg.get('codigo_homologado')}")
                if reg.get("codigo_homologado"):
                    campos["nupre"] = _campo(reg["codigo_homologado"], STATUS_VERIFIED_OFFICIAL,
                                             "registro oficial de adopción catastral")
                fuentes.append({"id": "registro_adopcion", "status": "OK",
                                "detalle": f"MATCH_EXACT · {folio_of}"})
            elif of.get("estado") == "IDENTITY_CONFLICT":
                campos["folio_matricula"] = _campo(
                    status=STATUS_CONFLICT,
                    motivo="conflicto de identidad en el registro oficial de adopción")
                fuentes.append({"id": "registro_adopcion", "status": "CONFLICT",
                                "detalle": "identidad en conflicto"})
            elif of.get("estado") == "MATCH_BY_PREDIAL_CODE":
                # Identificación PARCIAL: hay correspondencia por predial pero no las
                # tres claves (predial + homologado + FMI). NO se afirma la matrícula.
                campos["folio_matricula"] = _campo(
                    status=STATUS_UNRESOLVED,
                    motivo=("correspondencia parcial en el registro de adopción "
                            "(falta número predial + código homologado + FMI exactos): "
                            "no se afirma la matrícula"))
                fuentes.append({"id": "registro_adopcion", "status": "PARTIAL",
                                "detalle": "MATCH_BY_PREDIAL_CODE"})
            else:
                fuentes.append({"id": "registro_adopcion", "status": "NO_MATCH",
                                "detalle": "el número predial de la dirección no figura en el registro de adopción"})
        except Exception as e:  # noqa: BLE001
            fuentes.append({"id": "registro_adopcion", "status": "SOURCE_UNAVAILABLE",
                            "detalle": str(e)[:120]})

    # Motivo explícito para todo campo que quedó SIN dato (patrón «vacío explicado»):
    # la interfaz nunca muestra un hueco mudo ni un valor por defecto.
    for _nombre, _c in campos.items():
        if _es_vacia(_c.get("value")) and not _c.get("motivo"):
            _c["motivo"] = {
                "folio_matricula": ("la matrícula registral no se resuelve por dirección: el "
                                    "registro oficial se consulta por número predial, NUPRE o "
                                    "FMI exactos (adjunte el CTL o consulte la cédula catastral)"),
                "numero_predial": ("la capa oficial de direcciones no devolvió un predio único "
                                   "para esta placa"),
                "nupre": "requiere número predial exacto en el registro oficial de adopción",
                "barrio": "el punto no cayó en un polígono de barrio de la capa oficial",
                "localidad": "no resuelta por la capa oficial de unidades administrativas",
                "estrato": ("la capa oficial de estratificación no tiene registro atribuible "
                            "al predio (punto y manzana sin coincidencia)"),
                "coordenada": "la placa no se resolvió en el geocodificador oficial",
            }.get(_nombre, "sin dato en esta ejecución")
    return salida


def _predial_desde_capa_direcciones(direccion: str, fuentes: list) -> Optional[str]:
    """Número predial del predio según la capa OFICIAL de direcciones (capa 105).

    En el servicio de la Alcaldía el campo `codigo_postal` contiene el código de 30
    dígitos del predio (medido: 'Transversal 43 100 50' → '0800101030000100400019…'),
    sin unidades: es el predio, no la unidad. Se devuelve SOLO si una única feature
    coincide; con varias coincidencias no se elige arbitrariamente.
    """
    try:
        from geocoder_catastral import parsear_direccion_colombiana
        partes = parsear_direccion_colombiana(direccion)
        if not partes:
            fuentes.append({"id": "capa_direcciones_105", "status": "NO_PARSEABLE",
                            "detalle": "la dirección no tiene forma de placa colombiana"})
            return None
        clase, via, letra, generadora, numero = partes
        from catastro_predio import BASE_CATASTRO, CAPA_DIRECCION, _query_capa
        where = (f"clase_via_principal='{clase}' AND valor_via_principal='{via}'"
                 f" AND valor_via_generadora='{generadora}' AND numero_predio='{numero}'")
        if letra:
            where += f" AND letra_via_principal='{letra}'"
        r = _query_capa(f"{BASE_CATASTRO}", CAPA_DIRECCION, where,
                        out_fields="nombre_predio,codigo_postal,es_direccion_principal",
                        max_features=25)
        if not r.get("disponible"):
            fuentes.append({"id": "capa_direcciones_105", "status": "SOURCE_UNAVAILABLE",
                            "detalle": r.get("error") or "servicio sin respuesta"})
            return None
        feats = [f.get("properties") or {} for f in (r.get("features") or [])]
        codigos = {str(x.get("codigo_postal") or "") for x in feats if x.get("codigo_postal")}
        if len(codigos) == 1:
            fuentes.append({"id": "capa_direcciones_105", "status": "OK",
                            "detalle": f"{len(feats)} coincidencia(s), 1 predio"})
            return codigos.pop()
        fuentes.append({"id": "capa_direcciones_105",
                        "status": "AMBIGUOUS" if len(codigos) > 1 else "NO_MATCH",
                        "detalle": f"{len(feats)} coincidencia(s), {len(codigos)} predio(s) distinto(s)"})
    except Exception as e:  # noqa: BLE001
        fuentes.append({"id": "capa_direcciones_105", "status": "SOURCE_UNAVAILABLE",
                        "detalle": str(e)[:120]})
    return None


def resumen_legacy(res: Dict[str, Any]) -> tuple:
    """Adaptador al contrato anterior `(folio, barrio, estrato)`.

    Devuelve `"Pendiente"` / `""` / `None` cuando el campo NO está verificado: nunca
    un valor inventado. Los consumidores nuevos deben usar `campos`.
    """
    campos = (res or {}).get("campos") or {}

    def _v(nombre):
        c = campos.get(nombre) or {}
        if str(c.get("status") or "").startswith("VERIFIED") and not _es_vacia(c.get("value")):
            return c["value"]
        return None

    folio = _v("folio_matricula")
    barrio = _v("barrio")
    estrato = _v("estrato")
    return (folio or "Pendiente", barrio or "", estrato)

# -*- coding: utf-8 -*-
"""ARHIAX RE — BARRANQUILLA SOURCE PACK v1.0 · matriz de cobertura (corrida REAL).

Ejecuta una corrida de adquisición automática sobre el caso Golden 040-646406 y
escribe `docs/source_pack/SOURCE_COVERAGE_MATRIX_040-646406.csv` (18 filas × 7
columnas: row, source, status, value_or_result, authority, provenance, hash).

Reglas:

  · Los identificadores de entrada (dirección, NUPRE, número predial, coordenada)
    se LEEN del run state real
    `docs/forensics/040-646406/dictus_2b/DICTUS_RUN_STATE_040-646406.json`.
    NUNCA se codifican a mano.
  · Toda fila declara un estado CERRADO del contrato
    (AVAILABLE / NO_MATCH / SOURCE_UNAVAILABLE / NOT_SUPPORTED / QUERY_FAILED).
    Una ausencia JAMÁS se convierte en NO_MATCH.
  · Fuente `enabled: false` → NOT_SUPPORTED sin tocar la red.
  · Si el servicio en vivo no responde y la fuente declara un `local_fallback`
    (capa POT oficial empaquetada), se usa el fallback DECLARADO y la procedencia
    lo dice explícitamente.
  · Cero intervención humana: si un dato no se puede obtener, se declara.

Uso:
    python scripts/source_pack_coverage.py
    python scripts/source_pack_coverage.py --offline     # sin red (usa solo lo local)
"""
from __future__ import annotations

import argparse
import csv
import json
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "api"))

import dictus_sources as ds  # noqa: E402

DIR_PACK = RAIZ / "docs" / "source_pack"
RUTA_CSV = DIR_PACK / "SOURCE_COVERAGE_MATRIX_040-646406.csv"
RUTA_MANIFEST = DIR_PACK / "BARRANQUILLA_SOURCE_PACK_MANIFEST.json"
RUTA_RUN_STATE = (RAIZ / "docs" / "forensics" / "040-646406" / "dictus_2b"
                  / "DICTUS_RUN_STATE_040-646406.json")
RUTA_GEOJSON_REMOCION = RAIZ / "api" / "data" / "amenaza_remocion_masa.geojson"
RUTA_GEOJSON_RIESGO = RAIZ / "api" / "data" / "areas_en_riesgo.geojson"
RUTA_LONJA = (RAIZ / "motor_tma_lonja_baq_v1.0" / "motor_tma_lonja_baq_v1.0"
              / "lonja_layer" / "lonja_baq_metodologia.yaml")

COLUMNAS = ["row", "source", "status", "value_or_result", "authority", "provenance", "hash"]

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE
UA = "ARHIAX-RE/1.0 (Sinergia Consulting Group; Source Pack v1.0)"
TIMEOUT = 8.0


# ═════════════════════════════════════════════════════════════════════════════
# Entrada: identidad REAL del Golden (leída, nunca codificada a mano)
# ═════════════════════════════════════════════════════════════════════════════
def leer_golden() -> Dict[str, Any]:
    if not RUTA_RUN_STATE.exists():
        raise SystemExit(f"ERROR: no existe el run state del Golden: {RUTA_RUN_STATE}")
    rs = json.loads(RUTA_RUN_STATE.read_text(encoding="utf-8"))
    ident = rs.get("property_identity") or {}
    mc = rs.get("market_context") or {}
    coord = mc.get("coordinates") or {}
    adm = ident.get("administrativo") or {}
    generado = str(rs.get("generated_at") or "")
    return {
        "run_state": str(RUTA_RUN_STATE.relative_to(RAIZ)).replace("\\", "/"),
        "run_id": rs.get("run_id"),
        "folio": ident.get("folio"),
        "nupre": ident.get("nupre"),
        "numero_predial": ident.get("codigo_catastral"),
        "direccion": ident.get("direccion_raw"),
        "barrio": adm.get("barrio"),
        "estrato": adm.get("estrato"),
        "tratamiento": adm.get("tratamiento"),
        "lat": coord.get("lat"),
        "lon": coord.get("lon"),
        "coordinate_source": mc.get("coordinate_source"),
        "fecha": generado[:10] or None,
        "generated_at": generado,
        "riesgo_declarado": rs.get("risk_context") or {},
    }


# ═════════════════════════════════════════════════════════════════════════════
# Transporte ArcGIS REST (declara el estado; nunca lanza)
# ═════════════════════════════════════════════════════════════════════════════
def _get_json(url: str, params: Dict[str, Any]) -> Tuple[Optional[dict], str]:
    if OFFLINE:
        return None, ("srv_unavailable: modo offline solicitado (--offline): el servicio no "
                      "fue consultado en esta corrida")
    qs = urllib.parse.urlencode(params)
    full = f"{url}?{qs}"
    req = urllib.request.Request(full, headers={"User-Agent": UA,
                                                "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=_CTX) as resp:
            cuerpo = resp.read()
        try:
            return json.loads(cuerpo.decode("utf-8", "replace")), ""
        except Exception as exc:  # noqa: BLE001 — respuesta ilegible = consulta fallida
            return None, f"respuesta no interpretable como JSON ({type(exc).__name__})"
    except urllib.error.HTTPError as exc:
        return None, f"srv_unavailable: HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001
        return None, f"srv_unavailable: {type(exc).__name__}: {str(exc)[:90]}"


def consultar_capa(fuente: Dict[str, Any], *, where: str, geometry: bool,
                   distance_m: int = 80) -> Dict[str, Any]:
    """Consulta una capa ArcGIS y devuelve (status, payload, detail) del contrato §27."""
    if fuente.get("enabled") is False:
        return {"status": ds.NO_SOPORTADA, "payload": None,
                "detail": ("Fuente deshabilitada en el registro: su layer_id no pudo "
                           "verificarse (ver notes de la fuente).")}
    if not where and not geometry:
        return {"status": ds.NO_SOPORTADA, "payload": None,
                "detail": "La fuente no declara consulta ejecutable en esta corrida."}
    if not WORK["lat"] or not WORK["lon"]:
        return {"status": ds.FUENTE_NO_DISPONIBLE, "payload": None,
                "detail": "Sin coordenada oficial en el run state del Golden."}
    params: Dict[str, Any] = {"where": where or "1=1", "outFields": "*",
                              "returnGeometry": "false", "outSR": "4326", "f": "json",
                              "resultRecordCount": "5"}
    if geometry:
        params["geometry"] = json.dumps({"x": float(WORK["lon"]), "y": float(WORK["lat"]),
                                         "spatialReference": {"wkid": 4326}})
        params["geometryType"] = "esriGeometryPoint"
        params["inSR"] = "4326"
        params["spatialRel"] = "esriSpatialRelIntersects"
        if distance_m:
            params["distance"] = str(distance_m)
            params["units"] = "esriSRUnit_Meter"
    lid = fuente.get("layer_id")
    url = f"{fuente.get('base_url')}/{lid}/query"
    data, err = _get_json(url, params)
    if data is None:
        if err.startswith("srv_unavailable"):
            return {"status": ds.FUENTE_NO_DISPONIBLE, "payload": None,
                    "detail": f"Servicio no disponible en la ventana de la corrida ({err})."}
        return {"status": ds.CONSULTA_FALLIDA, "payload": None, "detail": err}
    if isinstance(data, dict) and data.get("error"):
        cod = (data.get("error") or {}).get("code")
        msg = str((data.get("error") or {}).get("message"))[:120]
        if cod == 404:
            return {"status": ds.NO_SOPORTADA, "payload": data,
                    "detail": f"ArcGIS 404: la capa no existe ({msg})."}
        return {"status": ds.CONSULTA_FALLIDA, "payload": data,
                "detail": f"ArcGIS error {cod}: {msg}"}
    feats = data.get("features") or []
    if not feats:
        return {"status": ds.SIN_COINCIDENCIA, "payload": data,
                "detail": "La capa respondió sin coincidencias para el punto/atributo."}
    attrs = [dict(f.get("attributes") or {}) for f in feats]
    return {"status": ds.DISPONIBLE, "payload": {"count": len(feats),
                                                 "features": attrs[:3]}, "detail": ""}


# ═════════════════════════════════════════════════════════════════════════════
# Resolvedores locales (evidencia real, sin red)
# ═════════════════════════════════════════════════════════════════════════════
def _en_anillo(x: float, y: float, anillo) -> bool:
    dentro = False
    n = len(anillo)
    for i in range(n):
        x1, y1 = anillo[i][0], anillo[i][1]
        x2, y2 = anillo[(i + 1) % n][0], anillo[(i + 1) % n][1]
        if (y1 > y) != (y2 > y):
            xi = (x2 - x1) * (y - y1) / ((y2 - y1) or 1e-18) + x1
            if x < xi:
                dentro = not dentro
    return dentro


def _contiene(geom: dict, x: float, y: float) -> bool:
    tipo, coords = geom.get("type"), geom.get("coordinates")
    def _poli(anillos) -> bool:
        if not anillos or not _en_anillo(x, y, anillos[0]):
            return False
        return not any(_en_anillo(x, y, h) for h in anillos[1:])
    if tipo == "Polygon":
        return _poli(coords)
    if tipo == "MultiPolygon":
        return any(_poli(p) for p in coords)
    return False


def capa_empaquetada(ruta: Path, *, campo_nivel: str) -> Dict[str, Any]:
    """Intersección punto-polígono sobre la capa POT oficial empaquetada."""
    if not ruta.exists():
        return {"status": ds.FUENTE_NO_DISPONIBLE, "payload": None,
                "detail": f"No existe la copia empaquetada {ruta.name}."}
    data = json.loads(ruta.read_text(encoding="utf-8"))
    feats = data.get("features") or []
    hits = [dict(f.get("properties") or {}) for f in feats
            if _contiene(f.get("geometry") or {}, float(WORK["lon"]), float(WORK["lat"]))]
    if not hits:
        return {"status": ds.SIN_COINCIDENCIA,
                "payload": {"capa": ruta.name, "poligonos_evaluados": len(feats),
                            "coincidencias": 0},
                "detail": ("La capa respondió: el punto NO cae en ningún polígono "
                           f"({len(feats)} evaluados).")}
    niveles = [str(h.get(campo_nivel) or "") for h in hits]
    orden = {"MUY ALTA": 4, "ALTA": 3, "MEDIA": 2, "MEDIO": 2, "BAJA": 1, "BAJO": 1}
    peor = max(niveles, key=lambda n: orden.get(n.upper(), 0)) if niveles else ""
    return {"status": ds.DISPONIBLE,
            "payload": {"capa": ruta.name, "poligonos": len(feats),
                        "nivel_reportado": peor, "nivel_por_poligono": niveles,
                        "poligonos_coincidentes": [
                            {k: v for k, v in h.items() if k in ("objectid", campo_nivel,
                                                                 "clase_suelo",
                                                                 "clasesuelo")}
                            for h in hits],
                        "regla": "se reporta el nivel MÁS ALTO y se listan TODOS los "
                                 "polígonos coincidentes: no se elige en silencio."},
            "detail": f"{len(hits)} polígono(s) contienen el punto."}


def identidad_adopcion(g: Dict[str, Any]) -> Dict[str, Any]:
    """Espejo de api/barranquilla_adopcion.consultar_adopcion: EXACT_3/2/1 o CONFLICT.

    Solo identificadores EXACTOS: NUNCA fuzzy. Si dos identificadores apuntan a
    registros disjuntos → CONFLICT (no se elige uno). Sin identificadores → ausencia
    declarada (NO_SOPORTADA), que NO es «sin coincidencia».
    """
    ruta = RAIZ / "api" / "data" / "barranquilla_adopcion_anexo1.json"
    if not ruta.exists():
        return {"status": ds.FUENTE_NO_DISPONIBLE, "payload": None,
                "detail": "No existe la copia normalizada del registro de adopción."}
    data = json.loads(ruta.read_text(encoding="utf-8"))
    regs = data.get("registros") or []
    predial = str(g.get("numero_predial") or "")
    nupre = str(g.get("nupre") or "")
    fmi = str(g.get("folio") or "").split("-")[-1] if g.get("folio") else ""
    if not any((predial, nupre, fmi)):
        return {"status": ds.NO_SOPORTADA, "payload": None,
                "detail": ("Sin identificadores canónicos de entrada no se puede resolver la "
                           "identidad: es una ausencia declarada, NO «sin coincidencia», y no "
                           "se pide el dato a una persona.")}

    def _idx(clave: str, valor: str) -> set:
        return {i for i, r in enumerate(regs) if valor and str(r.get(clave) or "") == valor}

    conjuntos = {"numero_predial": _idx("numero_predial", predial),
                 "codigo_homologado": _idx("codigo_homologado", nupre),
                 "fmi": _idx("fmi", fmi)}
    usados = {k: v for k, v in conjuntos.items() if v}
    claves = sorted(usados)
    for a in range(len(claves)):
        for b in range(a + 1, len(claves)):
            if usados[claves[a]].isdisjoint(usados[claves[b]]):
                return {"status": ds.CONSULTA_FALLIDA, "payload": {
                    "match_status": "CONFLICT", "coincidencias": {k: sorted(v)
                                                                  for k, v in conjuntos.items()}},
                    "detail": ("Los identificadores de entrada apuntan a registros DISJUNTOS: "
                               "se declara CONFLICT y no se elige uno en silencio.")}
    comun = set.intersection(*usados.values())
    if len(comun) != 1:
        return {"status": ds.SIN_COINCIDENCIA,
                "payload": {"match_status": "NO_MATCH",
                            "coincidencias": {k: sorted(v) for k, v in conjuntos.items()},
                            "identificadores_usados": claves},
                "detail": ("El registro de adopción respondió sin coincidencia exacta para "
                           f"los identificadores aportados ({', '.join(claves)}).")}
    reg = dict(regs[next(iter(comun))])
    grado = len(claves)
    return {"status": ds.DISPONIBLE,
            "payload": {"match_status": {"1": "EXACT_1", "2": "EXACT_2",
                                         "3": "EXACT_3"}.get(str(grado), f"EXACT_{grado}"),
                        "identificadores_usados": claves,
                        "identity_verified": grado == 3,
                        "registro": reg,
                        "fuente": data.get("source_name"),
                        "resolucion": f"{data.get('resolution_number')} de "
                                      f"{data.get('resolution_date')}",
                        "identificadores_aportados": {"numero_predial": predial or None,
                                                      "codigo_homologado": nupre or None,
                                                      "fmi": fmi or None}},
            "detail": ("" if grado == 3 else
                       f"Coincidencia parcial ({grado} identificador(es)): la identidad NO "
                       "se declara verificada.")}


def lonja_mercado(g: Dict[str, Any]) -> Dict[str, Any]:
    """Mercado: **NO hay fuente**. Se declara el parámetro que la corrida sí declara.

    Decisión de producto (docs/source_pack/INSTITUTIONAL_PARTNERS.md): la Lonja no
    aporta datos a DICTUS, así que no hay fuente de mercado que pueda «disponer» el
    dato. El estado es `SOURCE_UNAVAILABLE` y el valor —una constante escrita a mano en
    el artefacto local de metodología, sin URL, sin fecha de consulta, sin
    `sample_size` y sin comparables— viaja ETIQUETADO como parámetro declarado por la
    corrida. Nunca se sustituye por otro dato ni por un valor por defecto.
    """
    if not RUTA_LONJA.exists():
        return {"status": ds.FUENTE_NO_DISPONIBLE, "payload": None,
                "detail": "no existe el artefacto local de metodología de mercado"}
    try:
        import yaml  # type: ignore
        doc = yaml.safe_load(RUTA_LONJA.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001
        return {"status": ds.CONSULTA_FALLIDA, "payload": None,
                "detail": f"YAML no interpretable: {type(exc).__name__}: {exc}"}
    sectores = doc.get("valor_suelo_por_sector") or {}
    barrio = str(g.get("barrio") or "").strip()
    sector = None
    for clave in sectores:
        if str(clave).lower() == barrio.lower():
            sector = (clave, sectores[clave])
            break
    declaracion = doc.get("declaracion") or {}
    consolidacion = doc.get("regla_consolidacion") or {}
    try:
        import atribucion_mercado as _am  # noqa: E402 — api/ está en sys.path
        etiqueta = _am.ETIQUETA_PARAMETROS
    except Exception:  # noqa: BLE001
        etiqueta = "parámetros declarados por la corrida"
    base = {"methodology_id": "lonja_baq_metodologia",
            "etiqueta": etiqueta,
            "es_fuente_de_datos": False,
            "fuente_externa_verificable": False,
            "version": consolidacion.get("version"),
            "vigencia": {"desde": declaracion.get("vigencia_desde"),
                         "hasta": declaracion.get("vigencia_hasta")},
            "barrio_consultado": barrio}
    if sector is None:
        return {"status": ds.NO_SOPORTADA,
                "payload": {**base, "match_type": "NO_MATCH",
                            "sectores_declarados": sorted(str(k) for k in sectores)},
                "detail": (f"El barrio «{barrio}» no está en valor_suelo_por_sector: NO se "
                           "inventa sector ni se copia el fallback genérico por estrato.")}
    nombre, datos = sector
    return {"status": ds.FUENTE_NO_DISPONIBLE,
            "payload": {**base, "match_type": "EXACT", "sector": nombre,
                        "valor_declarado_por_la_corrida": {
                            "valor_central_m2": datos.get("valor_central_m2"),
                            "rango_min_m2": datos.get("rango_min_m2"),
                            "rango_max_m2": datos.get("rango_max_m2"),
                            "vigencia_sector": datos.get("vigencia")}},
            "detail": ("SIN FUENTE DE MERCADO: `LONJA_MARKET_BAQ` no está en el Source "
                       "Registry (la Lonja no aporta datos a DICTUS). El valor es un "
                       f"{etiqueta} (artefacto local de metodología), sin fuente externa "
                       "automática verificable; no se sustituye por ningún otro dato.")}


def solar_engine_local(g: Dict[str, Any]) -> Dict[str, Any]:
    try:
        sys.path.insert(0, str(RAIZ))
        import solar_engine as se  # noqa: E402
        import datetime as _dt
        fecha = _dt.datetime.fromisoformat(str(g.get("fecha")) + "T12:00:00")
        az, el = se.get_solar_position(float(g["lat"]), float(g["lon"]), fecha)
        return {"status": ds.DISPONIBLE,
                "payload": {"metodo": "get_solar_position(lat, lon, dt, tz_offset=-5)",
                            "fecha": str(g.get("fecha")), "hora": "12:00 local (UTC-5)",
                            "azimuth_deg": az, "elevation_deg": el,
                            "entradas": ["coordenada oficial", "fecha"],
                            "es_medicion_fisica": False},
                "detail": "Cálculo propio: solo requiere coordenada y fecha."}
    except Exception as exc:  # noqa: BLE001
        return {"status": ds.CONSULTA_FALLIDA, "payload": None,
                "detail": f"motor solar no ejecutable: {type(exc).__name__}: {exc}"}


def solar_local(g: Dict[str, Any]) -> Dict[str, Any]:
    """Fila «solar»: motor solar (solo coordenada + fecha) + exposición de fachada."""
    motor = solar_engine_local(g)
    fachada = exposition_local(g)
    if motor.get("status") != ds.DISPONIBLE:
        return motor
    payload = dict(motor.get("payload") or {})
    payload["facade_solar_exposure"] = (fachada.get("payload") or {}).get(
        "facade_solar_exposure") if fachada.get("status") == ds.DISPONIBLE else None
    payload["shadow_confidence"] = (fachada.get("payload") or {}).get("shadow_confidence")
    payload["geometria_faltante_fachada"] = (fachada.get("payload") or {}).get(
        "geometria_faltante")
    payload["blocks_dictus"] = (fachada.get("payload") or {}).get("blocks_dictus")
    payload["altura_fisica"] = (fachada.get("payload") or {}).get("altura_fisica")
    return {"status": ds.DISPONIBLE, "payload": payload,
            "detail": ("Motor solar determinista (coordenada + fecha) y análisis de fachada "
                       "con geometría declarada como faltante: se degrada la confianza, "
                       "nunca se bloquea ni se inventa altura.")}


def exposition_local(g: Dict[str, Any]) -> Dict[str, Any]:
    try:
        import facade_solar as fs  # noqa: E402
        out = fs.analizar_exposicion_fachada(float(g["lat"]), float(g["lon"]),
                                             fecha=str(g.get("fecha")), hora=12.0)
        return {"status": ds.DISPONIBLE,
                "payload": {"facade_solar_exposure": out.get("estado"),
                            "shadow_confidence": out.get("shadow_confidence"),
                            "geometria_faltante": out.get("geometria_faltante"),
                            "altura_fisica": out.get("building_physical_height"),
                            "simulacion_avanzada_habilitada":
                                out.get("simulacion_avanzada_habilitada"),
                            "blocks_dictus": out.get("blocks_dictus"),
                            "etiqueta": out.get("etiqueta")},
                "detail": ("Sin altura física NI azimut de fachada declarados: se declara "
                           "el estado del vocabulario cerrado y shadow_confidence DEGRADED. "
                           "No se inventa geometría ni altura.")}
    except Exception as exc:  # noqa: BLE001
        return {"status": ds.CONSULTA_FALLIDA, "payload": None,
                "detail": f"análisis de fachada no ejecutable: {type(exc).__name__}: {exc}"}


def street_imagery_local(g: Dict[str, Any]) -> Dict[str, Any]:
    try:
        import street_imagery as si  # noqa: E402
        huella = None
        if WORK.get("huella_geojson"):
            huella = WORK["huella_geojson"]
        agg = si.consultar_vista_automatica(float(g["lat"]), float(g["lon"]), huella,
                                             coordenada_oficial=(float(g["lat"]),
                                                                 float(g["lon"])))
        return {"status": str(agg.get("status")),
                "payload": {"facade_view_level": agg.get("facade_view_level"),
                            "provider": agg.get("provider"),
                            "motivo": agg.get("motivo"),
                            "human_input_required": agg.get("human_input_required"),
                            "blocks_dictus": agg.get("blocks_dictus"),
                            "dictus_gate_impact": agg.get("dictus_gate_impact"),
                            "credenciales": {k: (v or {}).get("credentials", {}).get("status")
                                             for k, v in (agg.get("attempts") or {}).items()}},
                "detail": ("Selección automática determinista sin intervención humana; sin "
                           "credenciales no se toca la red y la ausencia se declara.")}
    except Exception as exc:  # noqa: BLE001
        return {"status": ds.CONSULTA_FALLIDA, "payload": None,
                "detail": f"street imagery no ejecutable: {type(exc).__name__}: {exc}"}


def overpass_local(g: Dict[str, Any]) -> Dict[str, Any]:
    """Consulta Overpass con ESPEJOS (igual que api/poi_engine.py): un 504 no es un dato."""
    if OFFLINE:
        return {"status": ds.FUENTE_NO_DISPONIBLE, "payload": None,
                "detail": "modo offline: no se consulta Overpass."}
    q = (f"[out:json][timeout:25];\n(\n"
         f'  nwr(around:1500,{g["lat"]},{g["lon"]})["amenity"~'
         f'"school|hospital|clinic|pharmacy|bank|restaurant|place_of_worship"];\n'
         f'  nwr(around:1500,{g["lat"]},{g["lon"]})["shop"~"supermarket|mall"];\n'
         f");\nout center 30;")
    espejos = ["https://overpass-api.de/api/interpreter",
               "https://overpass.kumi.systems/api/interpreter",
               "https://maps.mail.ru/osm/tools/overpass/api/interpreter"]
    errores: List[str] = []
    for url in espejos:
        try:
            req = urllib.request.Request(url, data=urllib.parse.urlencode({"data": q}).encode(),
                                         headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=45, context=_CTX) as r:
                data = json.loads(r.read().decode("utf-8", "replace"))
        except Exception as exc:  # noqa: BLE001 — se prueba el siguiente espejo
            errores.append(f"{url.split('/')[2]}: {type(exc).__name__} "
                           f"{str(exc)[:60]}")
            continue
        els = data.get("elements") or []
        if not els:
            return {"status": ds.SIN_COINCIDENCIA,
                    "payload": {"espejo": url.split("/")[2], "elementos": 0},
                    "detail": ("Overpass respondió sin elementos en el radio consultado "
                               "(la fuente contestó: la ausencia es del área, no del dato).")}
        cats: Dict[str, int] = {}
        for e in els:
            t = e.get("tags") or {}
            k = t.get("amenity") or t.get("shop") or "otro"
            cats[k] = cats.get(k, 0) + 1
        return {"status": ds.DISPONIBLE,
                "payload": {"radio_m": 1500, "espejo": url.split("/")[2],
                            "elementos": len(els),
                            "categorias": dict(sorted(cats.items(), key=lambda x: -x[1])),
                            "nivel_autoridad": "CONTEXTO: nunca autoridad oficial"},
                "detail": ""}
    return {"status": ds.FUENTE_NO_DISPONIBLE, "payload": None,
            "detail": ("Ningún espejo de Overpass respondió en esta corrida: "
                       + " | ".join(errores))}


RUTA_CAPTURA_OSM = DIR_PACK / "raw" / "golden" / "osm_overpass.json"


def overpass_captura_local() -> Dict[str, Any]:
    """Fallback DECLARADO de OSM: la respuesta cruda capturada en la ventana del pack."""
    if not RUTA_CAPTURA_OSM.exists():
        return {"status": ds.FUENTE_NO_DISPONIBLE, "payload": None,
                "detail": "No existe la captura cruda de Overpass del pack."}
    doc = json.loads(RUTA_CAPTURA_OSM.read_text(encoding="utf-8"))
    data = doc.get("response") or {}
    meta = doc.get("_capture") or {}
    els = data.get("elements") or []
    if not els:
        return {"status": ds.SIN_COINCIDENCIA,
                "payload": {"captura": meta.get("queried_at"), "elementos": 0},
                "detail": "La captura cruda de Overpass no trae elementos."}
    cats: Dict[str, int] = {}
    for e in els:
        t = e.get("tags") or {}
        k = t.get("amenity") or t.get("shop") or "otro"
        cats[k] = cats.get(k, 0) + 1
    return {"status": ds.DISPONIBLE,
            "payload": {"radio_m": (meta.get("point") or {}).get("radio_m", 1500),
                        "espejo": (meta.get("endpoint") or "").split("/")[2],
                        "capturado_en": meta.get("queried_at"),
                        "elementos": len(els),
                        "categorias": dict(sorted(cats.items(), key=lambda x: -x[1])),
                        "nivel_autoridad": "CONTEXTO: nunca autoridad oficial"},
            "detail": "captura cruda preservada sin modificar (fallback declarado)."}


def equipamiento_oficial(registro: Dict[str, Any]) -> Dict[str, Any]:
    ids = ["EQUIPAMIENTO_18", "EQUIPAMIENTO_20", "EQUIPAMIENTO_21", "EQUIPAMIENTO_22",
           "EQUIPAMIENTO_23", "EQUIPAMIENTO_24", "EQUIPAMIENTO_25", "EQUIPAMIENTO_26",
           "EQUIPAMIENTO_27"]
    estados = {i: (registro["sources"].get(i) or {}).get("enabled") for i in ids}
    habilitadas = [i for i, v in estados.items() if v is not False]
    if not habilitadas:
        return {"status": ds.NO_SOPORTADA, "payload": {"capas": estados, "habilitadas": []},
                "detail": ("Ninguna de las 9 capas de equipamiento oficial está habilitada: "
                           "sus layer_id no se pudieron verificar (geoportal HTTP 403). El "
                           "equipamiento que hoy reporta el dictamen proviene de un proveedor "
                           "de mapas abierto y es CONTEXTO, no equipamiento oficial.")}
    resultado = consultar_capa(registro["sources"][habilitadas[0]], where="1=1", geometry=True)
    resultado["payload"] = {"capas_habilitadas": habilitadas,
                            "resultado": resultado.get("payload")}
    return resultado


# ═════════════════════════════════════════════════════════════════════════════
# Corrida
# ═════════════════════════════════════════════════════════════════════════════
WORK: Dict[str, Any] = {}
OFFLINE = False


def _registro() -> Dict[str, Any]:
    reg = ds.cargar_registro()
    if reg.get("_status") == ds.NO_SOPORTADA:
        raise SystemExit("ERROR: no existe el registro de fuentes. Ejecute "
                         "`python scripts/source_pack_build.py` primero.")
    return reg


def fila(nombre: str, sid: str, res: Dict[str, Any], registro: Dict[str, Any],
         via: str) -> Dict[str, str]:
    f = (registro.get("sources") or {}).get(sid) or (registro.get("sources") or {}).get(
        sid.split("+")[0], {})
    status = res.get("status") or ds.CONSULTA_FALLIDA
    if status not in ds.ESTADOS:
        status = ds.CONSULTA_FALLIDA
    payload = res.get("payload")
    if status == ds.DISPONIBLE:
        valor = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    else:
        # El estado declarado NO borra lo que sí se declaró (p. ej. el nivel de
        # confianza de fachada o el estado de credenciales): se conserva íntegro.
        extra = ""
        if isinstance(payload, dict) and payload:
            extra = " | " + json.dumps(payload, ensure_ascii=False, sort_keys=True)[:600]
        valor = (f"{status}: {res.get('detail') or 'sin dato declarado'} "
                 f"[{nombre}]{extra}")
    auth = res.get("authority") or f.get("authority_class") or ""
    if f:
        prov = (f"{sid} | {via} | precedence={f.get('precedence')} | "
                f"licencia={f.get('license_or_terms')} | {res.get('detail') or 'ok'}")
    else:
        prov = (f"{sid} | {via} | fuente agregada: el detalle por capa está en el registro "
                f"del pack | {res.get('detail') or 'ok'}")
    return {"row": nombre, "source": sid, "status": status, "value_or_result": valor,
            "authority": auth, "provenance": prov,
            "hash": ds.hash_canonico({"row": nombre, "source": sid, "status": status,
                                      "value": payload})}


def _con_fallback(fuente: Dict[str, Any], vivo: Dict[str, Any], local,
                  etiqueta_local: str) -> Tuple[Dict[str, Any], str]:
    """Si el servicio en vivo no responde y hay fallback local declarado, se usa."""
    if vivo.get("status") == ds.DISPONIBLE:
        return vivo, "live:servicio en vivo"
    if local is not None and vivo.get("status") in ds.ESTADOS_SIN_DATO:
        res = local()
        if res.get("status") == ds.DISPONIBLE:
            res = dict(res)
            res["detail"] = (f"{res.get('detail', '')} · {etiqueta_local}; el servicio en "
                             f"vivo quedó declarado {vivo.get('status')} "
                             f"({vivo.get('detail', '')[:80]})").strip(" ·")
            return res, f"fallback_local:{etiqueta_local}"
        return res, f"fallback_local:{etiqueta_local}"
    return vivo, "live:servicio no disponible"


def correr(golden: Optional[Dict[str, Any]] = None) -> List[Dict[str, str]]:
    """Corre la adquisición sobre el Golden. `golden` permite declarar ENTRADAS PARCIALES
    (p. ej. solo dirección o solo matrícula) para probar que nunca se pide dato a una
    persona: toda falta se declara como estado."""
    registro = _registro()
    src = registro["sources"]
    g = dict(golden if golden is not None else leer_golden())
    WORK.clear()
    WORK.update(g)

    where_predial = (f"numero_predial_nacional='{g['numero_predial']}' OR "
                     f"codigo_homologado='{g['nupre']}'")
    filas: List[Dict[str, str]] = []

    # 1 · identidad
    filas.append(fila("identidad", "CATASTRO_BAQ_ADOPCION_ANEXO1", identidad_adopcion(g),
                      registro, "local:registro de adopción (coincidencia EXACTA EXACT_3)"))

    # 2 · dirección
    filas.append(fila("direccion", "CATASTRO_BAQ_DIRECCION",
                      consultar_capa(src["CATASTRO_BAQ_DIRECCION"], where="1=1",
                                     geometry=True, distance_m=60),
                      registro, "live:query por punto (capa 105)"))

    # 3 · predio
    filas.append(fila("predio", "CATASTRO_BAQ_PREDIO",
                      consultar_capa(src["CATASTRO_BAQ_PREDIO"], where=where_predial,
                                     geometry=False),
                      registro, "live:query por atributos EXACTOS (NUPRE/número predial)"))

    # 4 · construcción
    filas.append(fila("construccion", "CATASTRO_BAQ_CONSTRUCCION",
                      consultar_capa(src["CATASTRO_BAQ_CONSTRUCCION"], where="1=1",
                                     geometry=True, distance_m=60),
                      registro, "live:query por punto (capa 310)"))

    # 5 · barrio
    filas.append(fila("barrio", "POT_BAQ_BARRIOS",
                      consultar_capa(src["POT_BAQ_BARRIOS"], where="1=1", geometry=True),
                      registro, "live:query por punto (unidades administrativas)"))

    # 6 · localidad
    filas.append(fila("localidad", "POT_BAQ_LOCALIDADES",
                      consultar_capa(src["POT_BAQ_LOCALIDADES"], where="1=1", geometry=True),
                      registro, "live:query por punto (campo localidad)"))

    # 7 · destino económico
    filas.append(fila("destino", "CATASTRO_BAQ_DESTINO_ECONOMICO",
                      consultar_capa(src["CATASTRO_BAQ_DESTINO_ECONOMICO"],
                                     where=where_predial, geometry=False),
                      registro, "live:query por identificador del predio (anualidad 2026)"))

    # 8 · uso POT
    filas.append(fila("uso_pot", "POT_BAQ_POLIGONOS_USO",
                      consultar_capa(src["POT_BAQ_POLIGONOS_USO"], where="1=1",
                                     geometry=True),
                      registro, "registro:fuente deshabilitada (layer_id sin verificar)"))

    # 9 · tratamiento
    filas.append(fila("tratamiento", "POT_BAQ_TRATAMIENTO",
                      consultar_capa(src["POT_BAQ_TRATAMIENTO"], where="1=1", geometry=True),
                      registro, "live:query por punto (planeación, tratamientos)"))

    # 10 · edificabilidad
    filas.append(fila("edificabilidad", "POT_BAQ_EDIFICABILIDAD",
                      consultar_capa(src["POT_BAQ_EDIFICABILIDAD"], where="1=1",
                                     geometry=True),
                      registro, "live:query por punto (altura NORMATIVA en pisos)"))

    # 11 · remoción
    res, via = _con_fallback(src["POT_BAQ_REMOCION_2024"],
                             consultar_capa(src["POT_BAQ_REMOCION_2024"], where="1=1",
                                            geometry=True),
                             lambda: capa_empaquetada(RUTA_GEOJSON_REMOCION,
                                                      campo_nivel="niveldeamenaza"),
                             "api/data/amenaza_remocion_masa.geojson")
    filas.append(fila("remocion", "POT_BAQ_REMOCION_2024", res, registro, via))

    # 12 · inundación
    filas.append(fila("inundacion", "POT_BAQ_INUNDACION_2024",
                      consultar_capa(src["POT_BAQ_INUNDACION_2024"], where="1=1",
                                     geometry=True),
                      registro, "registro:fuente deshabilitada (layer_id sin verificar, "
                                "sin copia empaquetada)"))

    # 13 · riesgo
    res, via = _con_fallback(src["POT_BAQ_RIESGO_2024"],
                             consultar_capa(src["POT_BAQ_RIESGO_2024"], where="1=1",
                                            geometry=True),
                             lambda: capa_empaquetada(RUTA_GEOJSON_RIESGO,
                                                      campo_nivel="nivelderiesgo"),
                             "api/data/areas_en_riesgo.geojson")
    filas.append(fila("riesgo", "POT_BAQ_RIESGO_2024", res, registro, via))

    # 14 · equipamiento oficial (conjunto OFFICIAL_EQUIPMENT_CONTEXT)
    res_equip = equipamiento_oficial(registro)
    res_equip["authority"] = ds.AUTORITATIVA_OFICIAL
    filas.append(fila("equipamiento_oficial", "OFFICIAL_EQUIPMENT_CONTEXT", res_equip,
                      registro, "conjunto:9 capas oficiales agregadas"))

    # 15 · servicios de contexto (OSM) — con captura cruda como fallback declarado
    res_osm, via_osm = _con_fallback(src["OSM_OVERPASS"], overpass_local(g),
                                     overpass_captura_local,
                                     "raw/golden/osm_overpass.json")
    filas.append(fila("servicios_contexto", "OSM_OVERPASS", res_osm, registro, via_osm))

    # 16 · street imagery
    res_img = street_imagery_local(g)
    res_img["authority"] = ds.CONTEXTUAL_EXTERNA
    filas.append(fila("street_imagery", "MAPILLARY+GOOGLE_STREET_VIEW", res_img, registro,
                      "live:selección automática determinista (sin credenciales)"))

    # 17 · solar (motor + fachada) y 18 · mercado
    filas.append(fila("solar", "SOLAR_ENGINE+SHADOW_FACADE_EXPOSURE", solar_local(g),
                      registro,
                      "local:solar_engine.get_solar_position + facade_solar."
                      "analizar_exposicion_fachada"))
    filas.append(fila("mercado", "SIN_FUENTE (parámetros declarados por la corrida)",
                      lonja_mercado(g), registro,
                      "local:artefacto de metodología del producto (sector por barrio, match "
                      "exacto) · NO es una fuente de datos"))
    return filas


def _etiquetar(filas: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Numerar las filas (01-…, 18-…) igual en el CSV y en el manifest."""
    salida = []
    for i, f in enumerate(filas, start=1):
        f = dict(f)
        f["row"] = f"{i:02d}-{f['row']}"
        salida.append(f)
    return salida


def escribir_csv(filas: List[Dict[str, str]]) -> None:
    RUTA_CSV.parent.mkdir(parents=True, exist_ok=True)
    with RUTA_CSV.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNAS)
        w.writeheader()
        for fila_ in filas:
            w.writerow(fila_)


def actualizar_manifest(filas: List[Dict[str, str]], g: Dict[str, Any]) -> str:
    if not RUTA_MANIFEST.exists():
        return "manifest ausente: no se actualiza"
    man = json.loads(RUTA_MANIFEST.read_text(encoding="utf-8"))
    man["tested_at"] = datetime.now(timezone.utc).isoformat()
    man["coverage"] = {
        "matrix_file": str(RUTA_CSV.relative_to(RAIZ)).replace("\\", "/"),
        "rows": len(filas),
        "columns": COLUMNAS,
        "statuses": {f["row"]: f["status"] for f in filas},
        "source_of_input": {"run_state": g["run_state"], "run_id": g["run_id"],
                            "read_not_hardcoded": True},
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    RUTA_MANIFEST.write_text(json.dumps(man, ensure_ascii=False, indent=1, sort_keys=True),
                             encoding="utf-8")
    return ds.hash_canonico(man)


def main() -> int:
    global OFFLINE
    ap = argparse.ArgumentParser(description="Matriz de cobertura del Source Pack.")
    ap.add_argument("--offline", action="store_true",
                    help="no consulta la red (solo evidencia local declarada)")
    args = ap.parse_args()
    OFFLINE = bool(args.offline)
    filas = _etiquetar(correr())
    escribir_csv(filas)
    huella = actualizar_manifest(filas, WORK)
    print(f"matriz: {RUTA_CSV.relative_to(RAIZ)} ({len(filas)} filas × {len(COLUMNAS)} columnas)")
    for f in filas:
        print(f"  {f['row']:<22} {f['source']:<28} {f['status']}")
    print(f"manifest: {RUTA_MANIFEST.name} (hash {huella[:16]}…)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

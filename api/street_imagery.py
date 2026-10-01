# -*- coding: utf-8 -*-
"""
ARHIAX RE — STREET IMAGERY · abstracción automática de proveedores de vista
callejera (§19 / §21 del contrato de fuentes).

Objetivo: obtener una VISTA CALLEJERA ORIENTADA HACIA EL INMUEBLE sin ninguna
selección humana, con procedencia completa y estados fail-closed.

Reglas duras de este módulo
───────────────────────────
1. Estados CERRADOS por consulta (§27): ``AVAILABLE | NO_MATCH |
   SOURCE_UNAVAILABLE | NOT_SUPPORTED | QUERY_FAILED``. Un estado desconocido
   cae en ``QUERY_FAILED``. **Nunca** se convierte una ausencia (fuente caída,
   sin credenciales, no soportada) en ``NO_MATCH``: ``NO_MATCH`` sólo se declara
   cuando el proveedor CONTESTÓ y no había imagen en el punto.
2. Selección de fachada 100 % automática y determinista: se calcula
   ``bearing_camera→building`` a partir de (a) la coordenada oficial del predio,
   (b) el centroide de la huella del edificio (si existe) y (c) la coordenada
   del panorama/cámara; de ahí salen ``heading``, ``pitch`` y ``fov``. El orden
   de llegada de los candidatos NO decide: el desempate es determinista
   (alineación → distancia → ``image_id``). ``human_input_required = False``.
3. Vocabulario de texto: una vista orientada al inmueble se rotula SIEMPRE
   «vista callejera orientada hacia el inmueble». La frase «fachada principal»
   está PROHIBIDA en cualquier texto generado (``sanear_texto`` la sustituye).
4. Licencias: se registra ``provider_terms_status`` y una política de
   persistencia por proveedor. Una imagen de Google **no** puede asumirse
   descargable/persistible/embebible: ``can_persist=False`` y
   ``can_embed_in_pdf=False`` salvo evidencia de términos VERIFICADA. Sin
   verificación → ``terms_status="UNVERIFIED"`` y fail-closed. Mapillary es el
   candidato principal de persistencia (licencia declarada CC BY-SA 4.0), con
   atribución obligatoria y share-alike.
5. Sin credenciales/token → ``SOURCE_UNAVAILABLE`` (o ``NOT_SUPPORTED``) con
   motivo explícito y SIN tocar la red. Nunca se inventan imágenes.
6. ``get_image`` respeta la política: si ``can_persist`` es False NO descarga ni
   guarda bytes (``downloaded=False``, ``bytes_written=0``).

Este módulo NO toca valoración, fórmulas, release gate, master hash, identity
rules, screening thresholds ni la gramática de decisión.
"""
from __future__ import annotations

import abc
import hashlib
import importlib
import importlib.util
import json
import math
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

_DIR_API = Path(__file__).resolve().parent
_DIR_RAIZ = _DIR_API.parent


# ── carga de módulos hermanos sin depender del cwd ni de sys.path ─────────────
def _cargar_modulo(nombre: str, *rutas: Path):
    """Importa un módulo hermano de ``api/`` de forma determinista.

    Evita que un homónimo en la raíz del repositorio (p. ej. ``solar_engine.py``)
    gane por accidente el ``sys.path``.
    """
    try:
        return importlib.import_module(nombre)
    except Exception:
        pass
    for ruta in rutas:
        if not ruta.exists():
            continue
        alias = f"_arhiax_{nombre}"
        ya = sys.modules.get(alias)
        if ya is not None:
            return ya
        spec = importlib.util.spec_from_file_location(alias, ruta)
        if spec is None or spec.loader is None:
            continue
        mod = importlib.util.module_from_spec(spec)
        sys.modules[alias] = mod
        try:
            spec.loader.exec_module(mod)
        except Exception:
            sys.modules.pop(alias, None)
            raise
        return mod
    raise ImportError(f"No se pudo cargar el módulo requerido: {nombre}")


_ds = _cargar_modulo("dictus_sources", _DIR_API / "dictus_sources.py")

# ── §27 · estados cerrados ────────────────────────────────────────────────────
AVAILABLE = "AVAILABLE"
NO_MATCH = "NO_MATCH"
SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
NOT_SUPPORTED = "NOT_SUPPORTED"
QUERY_FAILED = "QUERY_FAILED"
ESTADOS: Tuple[str, ...] = (AVAILABLE, NO_MATCH, SOURCE_UNAVAILABLE, NOT_SUPPORTED, QUERY_FAILED)
# Estados que significan «no se pudo saber», NUNCA «no existe».
ESTADOS_SIN_DATO: Tuple[str, ...] = (SOURCE_UNAVAILABLE, NOT_SUPPORTED, QUERY_FAILED)

# ── proveedores iniciales ─────────────────────────────────────────────────────
MAPILLARY = "MAPILLARY"
GOOGLE_STREET_VIEW = "GOOGLE_STREET_VIEW"
NO_IMAGE_AVAILABLE = "NO_IMAGE_AVAILABLE"
PROVEEDORES: Tuple[str, ...] = (MAPILLARY, GOOGLE_STREET_VIEW, NO_IMAGE_AVAILABLE)

# ── §19 · niveles de confianza de fachada ─────────────────────────────────────
FACADE_VIEW_VERIFIED = "FACADE_VIEW_VERIFIED"
FACADE_VIEW_PROBABLE = "FACADE_VIEW_PROBABLE"
FACADE_VIEW_CONTEXTUAL = "FACADE_VIEW_CONTEXTUAL"
NIVELES_FACHADA: Tuple[str, ...] = (FACADE_VIEW_VERIFIED, FACADE_VIEW_PROBABLE,
                                    FACADE_VIEW_CONTEXTUAL, NO_IMAGE_AVAILABLE)

# ── términos / licencias (vocabulario cerrado) ────────────────────────────────
TERMS_VERIFIED = "VERIFIED"          # términos consultados y hasheados en esta corrida
TERMS_DECLARED = "DECLARED"          # licencia declarada por el contrato del proveedor
TERMS_UNVERIFIED = "UNVERIFIED"      # no se pudo verificar → FAIL-CLOSED
TERMS_RESTRICTED = "RESTRICTED"      # términos consultados que PROHÍBEN persistir
TERMS_NOT_APPLICABLE = "NOT_APPLICABLE"
ESTADOS_TERMINOS: Tuple[str, ...] = (TERMS_VERIFIED, TERMS_DECLARED, TERMS_UNVERIFIED,
                                     TERMS_RESTRICTED, TERMS_NOT_APPLICABLE)

# ── vocabulario de texto exigido ──────────────────────────────────────────────
TEXTO_VISTA_AUTORIZADO = "vista callejera orientada hacia el inmueble"
TEXTO_PROHIBIDO_FACHADA_PRINCIPAL = "fachada principal"

METODO_SELECCION = "AUTOMATICA_AZIMUT_CAMARA_A_INMUEBLE_SIN_INTERVENCION_HUMANA"

# ── parámetros geométricos (declarados, no ajustados a ojo) ───────────────────
DEFAULT_FOV_DEG = 80.0
ALTURA_CAMARA_DEFECTO_M = 2.5
TOLERANCIA_ALINEACION_DEG = 25.0
TOLERANCIA_ALINEACION_AMPLIA_DEG = 45.0
ERROR_ALINEACION_MAXIMO_DEG = 60.0
DISTANCIA_VERIFICADA_M = 75.0
DISTANCIA_PROBABLE_M = 200.0

MOTIVO_SIN_CREDENCIALES = ("Sin credenciales/token configurados: la fuente no puede "
                           "consultarse. Se declara el estado; NO se inventan imágenes.")

_ENV_STRICT_TERMS = "ARHIAX_IMAGERY_STRICT_TERMS"


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def hash_canonico(payload: Any) -> str:
    """Hash canónico y estable de la evidencia (mismo criterio que §28)."""
    if isinstance(payload, (bytes, bytearray)):
        return hashlib.sha256(bytes(payload)).hexdigest()
    crudo = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                       default=str)
    return hashlib.sha256(crudo.encode("utf-8")).hexdigest()


# ── geometría ─────────────────────────────────────────────────────────────────
def bearing_geodesico(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Azimut inicial (0-360°, Norte=0, sentido horario) del punto 1 al punto 2."""
    f1, f2 = math.radians(float(lat1)), math.radians(float(lat2))
    dl = math.radians(float(lon2) - float(lon1))
    y = math.sin(dl) * math.cos(f2)
    x = math.cos(f1) * math.sin(f2) - math.sin(f1) * math.cos(f2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def distancia_metros(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia haversine (m) entre dos coordenadas."""
    r = 6371008.8
    f1, f2 = math.radians(float(lat1)), math.radians(float(lat2))
    df = f2 - f1
    dl = math.radians(float(lon2) - float(lon1))
    a = math.sin(df / 2.0) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(dl / 2.0) ** 2
    return 2.0 * r * math.asin(min(1.0, math.sqrt(a)))


def diferencia_angular(a: float, b: float) -> float:
    """Diferencia angular mínima (0-180°) entre dos azimuts."""
    d = abs((float(a) - float(b)) % 360.0)
    return 360.0 - d if d > 180.0 else d


def _float_o_none(v: Any) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _coord_de(valor: Any) -> Optional[Tuple[float, float]]:
    """Normaliza (lat, lon) desde dict/tuple/lista."""
    if valor is None:
        return None
    if isinstance(valor, dict):
        lat, lon = _float_o_none(valor.get("lat")), _float_o_none(valor.get("lon"))
        if lat is None:  # tolerar latitud/longitud en español
            lat, lon = _float_o_none(valor.get("latitud")), _float_o_none(valor.get("longitud"))
    elif isinstance(valor, (tuple, list)) and len(valor) >= 2:
        lat, lon = _float_o_none(valor[0]), _float_o_none(valor[1])
    else:
        return None
    if lat is None or lon is None:
        return None
    return lat, lon


def centroide_huella(geometria: Any, *, orden: str = "lon_lat") -> Optional[Dict[str, Any]]:
    """Centroide de la huella del edificio (GeoJSON Polygon/MultiPolygon o lista de pares).

    Devuelve ``{lat, lon, metodo, n_vertices}`` o ``None`` si no hay geometría
    interpretable. No se estima ninguna huella: si no hay dato, se declara.
    """
    if not geometria:
        return None
    orden = (orden or "lon_lat").lower()
    if isinstance(geometria, dict) and geometria.get("type") and geometria.get("coordinates"):
        tipo = str(geometria.get("type"))
        try:
            if tipo == "Polygon":
                anillos = [geometria["coordinates"][0]]
            elif tipo == "MultiPolygon":
                anillos = [p[0] for p in geometria["coordinates"] if p]
            else:
                return None
            # Centroide real si shapely está disponible; si no, media de vértices.
            try:
                from shapely.geometry import shape  # type: ignore
                centro = shape(geometria).centroid
                return {"lat": float(centro.y), "lon": float(centro.x),
                        "metodo": "SHAPELY_CENTROID", "n_vertices": len(anillos[0])}
            except Exception:
                pts = [p for a in anillos for p in a]
                if not pts:
                    return None
                lon = sum(float(p[0]) for p in pts) / len(pts)
                lat = sum(float(p[1]) for p in pts) / len(pts)
                return {"lat": lat, "lon": lon, "metodo": "MEDIA_VERTICES_ANILLO_EXTERIOR",
                        "n_vertices": len(pts)}
        except Exception:
            return None
    if isinstance(geometria, (list, tuple)):
        pares = [p for p in geometria if isinstance(p, (list, tuple)) and len(p) >= 2]
        if not pares:
            return None
        try:
            if orden == "lon_lat":
                lon = sum(float(p[0]) for p in pares) / len(pares)
                lat = sum(float(p[1]) for p in pares) / len(pares)
            else:
                lat = sum(float(p[0]) for p in pares) / len(pares)
                lon = sum(float(p[1]) for p in pares) / len(pares)
        except (TypeError, ValueError):
            return None
        return {"lat": lat, "lon": lon, "metodo": "MEDIA_VERTICES_LISTA", "n_vertices": len(pares)}
    if isinstance(geometria, dict):
        return _coord_de_dict_centro(geometria)
    return None


def _coord_de_dict_centro(geometria: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    lat, lon = _float_o_none(geometria.get("centro_lat")), _float_o_none(geometria.get("centro_lon"))
    if lat is None or lon is None:
        return None
    return {"lat": lat, "lon": lon, "metodo": "CENTRO_DECLARADO", "n_vertices": None}


# ── texto: prohibición de «fachada principal» ─────────────────────────────────
_PATRON_FACHADA_PRINCIPAL = re.compile(r"fachada\s+principal", re.IGNORECASE)


def sanear_texto(texto: Any) -> str:
    """Sustituye cualquier «fachada principal» por el rótulo autorizado.

    El sistema sólo identifica una vista orientada al inmueble; no puede afirmar
    que sea la fachada principal, así que nunca lo escribe.
    """
    t = "" if texto is None else str(texto)
    return _PATRON_FACHADA_PRINCIPAL.sub(TEXTO_VISTA_AUTORIZADO, t)


def etiqueta_vista_callejera(proveedor: str = "", azimut_camara_inmueble: Optional[float] = None,
                             distancia_m: Optional[float] = None,
                             nivel: str = "") -> str:
    """Rótulo canónico de la vista, siempre saneado."""
    partes = [TEXTO_VISTA_AUTORIZADO.capitalize()]
    if proveedor:
        partes.append(f"proveedor {proveedor}")
    if azimut_camara_inmueble is not None:
        partes.append(f"azimut cámara→inmueble {float(azimut_camara_inmueble):.1f}°")
    if distancia_m is not None:
        partes.append(f"distancia {float(distancia_m):.1f} m")
    if nivel:
        partes.append(f"nivel de confianza {nivel}")
    return sanear_texto(" — ".join(partes))


# ── §19 · selección AUTOMÁTICA de la vista orientada al inmueble ──────────────
def normalizar_candidato_crudo(c: Dict[str, Any], *, proveedor: str = "") -> Optional[Dict[str, Any]]:
    """Normaliza un candidato a la forma que consume el selector (contrato estable)."""
    if not isinstance(c, dict):
        return None
    cam = _coord_de(c) or _coord_de({"lat": c.get("camera_lat"), "lon": c.get("camera_lon")})
    if cam is None:
        cam = _coord_de({"lat": c.get("lat"), "lon": c.get("lon")})
    if cam is None:
        return None
    return {
        "image_id": str(c.get("image_id") or c.get("id") or ""),
        "panorama_id": c.get("panorama_id") or c.get("pano_id"),
        "camera_lat": cam[0], "camera_lon": cam[1],
        "compass_angle": _float_o_none(c.get("compass_angle")),
        "is_pano": bool(c.get("is_pano")),
        "capture_date": c.get("capture_date"),
        "attribution": c.get("attribution"),
        "provider": c.get("provider") or proveedor,
        "width": c.get("width"), "height": c.get("height"),
        "fov": _float_o_none(c.get("fov")),
        "license": c.get("license"),
        "url": c.get("url"),
        "metadata": dict(c),
    }


def seleccionar_vista_automatica(
    candidatos: Sequence[Dict[str, Any]],
    *,
    coordenada_oficial: Any = None,
    centroide_edificio: Any = None,
    altura_edificio_m: Any = None,
    altura_camara_m: float = ALTURA_CAMARA_DEFECTO_M,
    proveedor: str = "",
    fov_defecto: float = DEFAULT_FOV_DEG,
    tolerancia_alineacion_deg: float = TOLERANCIA_ALINEACION_DEG,
    distancia_verificada_m: float = DISTANCIA_VERIFICADA_M,
    distancia_probable_m: float = DISTANCIA_PROBABLE_M,
) -> Dict[str, Any]:
    """Elige la mejor vista hacia el inmueble SIN intervención humana.

    Entradas: candidatos (panoramas/imágenes del proveedor), coordenada oficial
    del predio y, si existe, el centroide de la huella del edificio. Se calcula
    ``bearing_camera→building``, y de ahí ``heading``, ``pitch`` y ``fov``.

    Determinista: el resultado no depende del orden de los candidatos (desempate
    por alineación → distancia → ``image_id``).
    """
    base: Dict[str, Any] = {
        "status": AVAILABLE,
        "facade_view_level": NO_IMAGE_AVAILABLE,
        "confidence": NO_IMAGE_AVAILABLE,
        "selection_method": METODO_SELECCION,
        "human_input_required": False,
        "provider": proveedor,
        "candidate_count": 0,
        "candidates_evaluated": [],
        "candidates_discarded": [],
        "imagen": None,
        "image_id": None,
        "panorama_id": None,
        "camera_lat": None, "camera_lon": None,
        "building_lat": None, "building_lon": None,
        "target_lat": None, "target_lon": None, "target_source": None,
        "bearing_camera_to_building_deg": None,
        "heading": None, "heading_source": None,
        "pitch": None, "pitch_source": None,
        "fov": None, "fov_source": None,
        "capture_date": None, "attribution": None,
        "distance_m": None, "alignment_error_deg": None,
        "is_pano": None,
        "descripcion": None,
        "motivo": "",
    }

    evaluados: List[Dict[str, Any]] = []
    for c in candidatos or []:
        n = normalizar_candidato_crudo(c, proveedor=proveedor)
        if n is not None:
            evaluados.append(n)
    base["candidate_count"] = len(evaluados)
    if not evaluados:
        base["motivo"] = ("Sin candidatos de imagen devueltos por el proveedor: no hay "
                          "vista que seleccionar (se declara; no se inventa).")
        return base

    objetivo: Optional[Tuple[float, float]] = None
    origen_objetivo = "SIN_GEOMETRIA_DEL_INMUEBLE"
    c_centro = _coord_de(centroide_edificio)
    if c_centro is not None:
        objetivo, origen_objetivo = c_centro, "CENTROIDE_HUELLA_EDIFICIO"
    else:
        c_oficial = _coord_de(coordenada_oficial)
        if c_oficial is not None:
            objetivo, origen_objetivo = c_oficial, "COORDENADA_OFICIAL"

    if objetivo is None:
        base["facade_view_level"] = FACADE_VIEW_CONTEXTUAL
        base["confidence"] = FACADE_VIEW_CONTEXTUAL
        base["motivo"] = ("Sin coordenada oficial ni centroide de huella: la vista sólo "
                          "puede clasificarse como CONTEXTUAL; no se afirma orientación "
                          "hacia el inmueble.")
        return base

    base["target_source"] = origen_objetivo
    base["target_lat"], base["target_lon"] = objetivo[0], objetivo[1]

    registros: List[Dict[str, Any]] = []
    for n in evaluados:
        az = bearing_geodesico(n["camera_lat"], n["camera_lon"], objetivo[0], objetivo[1])
        dist = distancia_metros(n["camera_lat"], n["camera_lon"], objetivo[0], objetivo[1])
        compass = n.get("compass_angle")
        if n.get("is_pano"):
            err: Optional[float] = 0.0          # un panorama cubre 360°: el heading se pide
            origen_heading = "PANORAMA_HEADING_SOLICITADO_HACIA_INMUEBLE"
        elif compass is None:
            err = None                          # sin compás no se puede verificar el giro
            origen_heading = "HEADING_SOLICITADO_HACIA_INMUEBLE_SIN_COMPAS"
        else:
            err = diferencia_angular(compass, az)
            origen_heading = ("AZIMUT_COMPAS_CAMARA_VERIFICADO" if err <= tolerancia_alineacion_deg
                              else "COMPAS_CAMARA_NO_ALINEADO_CON_INMUEBLE")
        registros.append({
            **{k: n.get(k) for k in ("image_id", "panorama_id", "camera_lat", "camera_lon",
                                     "is_pano", "capture_date", "attribution", "provider",
                                     "width", "height", "fov", "license", "url")},
            "camera_lat": n["camera_lat"], "camera_lon": n["camera_lon"],
            "compass_angle": compass,
            "bearing_camera_to_building_deg": round(az, 4),
            "distance_m": round(dist, 3),
            "alignment_error_deg": None if err is None else round(err, 4),
            "heading_source": origen_heading,
        })

    # Se descartan las vistas en perspectiva que NO miran al inmueble: usarlas
    # sería afirmar una orientación que la cámara no tenía.
    idx_utilizables = [i for i, r in enumerate(registros)
                       if r["is_pano"] or r["alignment_error_deg"] is None
                       or r["alignment_error_deg"] <= ERROR_ALINEACION_MAXIMO_DEG]
    utilizables = [registros[i] for i in idx_utilizables]
    descartados = [r for i, r in enumerate(registros) if i not in set(idx_utilizables)]
    # La auditoría también es determinista: el orden de llegada no altera el resultado.
    registros.sort(key=lambda r: str(r.get("image_id") or ""))
    descartados.sort(key=lambda r: str(r.get("image_id") or ""))

    def _orden(r: Dict[str, Any]):
        err = r["alignment_error_deg"]
        return (0 if err is not None else 1,
                err if err is not None else 999.0,
                r["distance_m"],
                str(r.get("image_id") or ""))

    if not utilizables:
        base["facade_view_level"] = FACADE_VIEW_CONTEXTUAL
        base["confidence"] = FACADE_VIEW_CONTEXTUAL
        base["candidates_evaluated"] = registros
        base["candidates_discarded"] = descartados
        base["motivo"] = ("Ninguna vista del proveedor está orientada al inmueble "
                          "(todas superan el error de alineación máximo declarado): la "
                          "imagen disponible es sólo CONTEXTUAL.")
        elegido = dict(min(registros, key=lambda r: (r["distance_m"], str(r.get("image_id") or ""))))
        elegido["heading_source"] = "SIN_VISTA_ORIENTADA_AL_INMUEBLE"
    else:
        elegido = dict(min(utilizables, key=_orden))

    # ── heading / pitch / fov ────────────────────────────────────────────────
    az_inmueble = elegido["bearing_camera_to_building_deg"]
    if elegido["heading_source"] == "AZIMUT_COMPAS_CAMARA_VERIFICADO":
        heading = round(float(elegido["compass_angle"]), 4)
    else:
        heading = round(float(az_inmueble), 4)
    dist = float(elegido["distance_m"])
    altura = _float_o_none(altura_edificio_m)
    if altura is not None and dist > 0:
        pitch = round(math.degrees(math.atan(((altura / 2.0) - float(altura_camara_m)) / dist)), 4)
        pitch_source = "CALCULADO_CON_ALTURA_FISICA_DECLARADA"
    else:
        pitch = 0.0
        pitch_source = "HORIZONTAL_POR_DEFECTO_SIN_ALTURA_FISICA"
    if elegido.get("fov") is not None:
        fov, fov_source = float(elegido["fov"]), "PROVEEDOR"
    else:
        fov, fov_source = float(fov_defecto), "DEFECTO_DECLARADO_SIN_MODELO_DE_CAMARA"

    # ── nivel de confianza (§19) ─────────────────────────────────────────────
    err = elegido["alignment_error_deg"]
    fecha = elegido.get("capture_date")
    if (err is not None and err <= tolerancia_alineacion_deg
            and dist <= distancia_verificada_m and bool(fecha)):
        nivel = FACADE_VIEW_VERIFIED
    elif (err is None or err <= TOLERANCIA_ALINEACION_AMPLIA_DEG) and dist <= distancia_probable_m:
        nivel = FACADE_VIEW_PROBABLE
    else:
        nivel = FACADE_VIEW_CONTEXTUAL

    base.update({
        "facade_view_level": nivel,
        "confidence": nivel,
        "provider": elegido.get("provider") or proveedor,
        "imagen": elegido.get("image_id") or elegido.get("panorama_id"),
        "image_id": elegido.get("image_id"),
        "panorama_id": elegido.get("panorama_id"),
        "camera_lat": elegido["camera_lat"], "camera_lon": elegido["camera_lon"],
        "building_lat": objetivo[0], "building_lon": objetivo[1],
        "bearing_camera_to_building_deg": az_inmueble,
        "heading": heading, "heading_source": elegido["heading_source"],
        "pitch": pitch, "pitch_source": pitch_source,
        "fov": fov, "fov_source": fov_source,
        "capture_date": fecha,
        "attribution": sanear_texto(elegido.get("attribution") or ""),
        "distance_m": dist,
        "alignment_error_deg": err,
        "is_pano": elegido.get("is_pano"),
        "license_metadata": elegido.get("license"),
        "url": elegido.get("url"),
        "candidates_evaluated": registros,
        "candidates_discarded": descartados,
        "descripcion": etiqueta_vista_callejera(
            proveedor=elegido.get("provider") or proveedor,
            azimut_camara_inmueble=az_inmueble, distancia_m=dist, nivel=nivel),
    })
    return base


# ── errores de fuente traducidos a estados cerrados ───────────────────────────
class ErrorFuente(RuntimeError):
    """Fallo de consulta ya traducido a un estado cerrado del vocabulario."""

    def __init__(self, estado: str, detalle: str):
        super().__init__(detalle)
        self.estado = estado if estado in ESTADOS else QUERY_FAILED
        self.detalle = detalle


def estado_por_http(codigo: int) -> Tuple[str, str]:
    """Traduce un código HTTP a (estado, motivo). Fail-closed, nunca NO_MATCH."""
    codigo = int(codigo or 0)
    if codigo in (401, 403):
        return SOURCE_UNAVAILABLE, f"HTTP {codigo}: credenciales rechazadas o sin permiso."
    if codigo == 429:
        return SOURCE_UNAVAILABLE, "HTTP 429: cuota del proveedor agotada temporalmente."
    if codigo >= 500:
        return SOURCE_UNAVAILABLE, f"HTTP {codigo}: el proveedor no respondió utilizable."
    if codigo >= 400:
        return QUERY_FAILED, f"HTTP {codigo}: la consulta fue rechazada por el proveedor."
    return QUERY_FAILED, f"HTTP {codigo}: respuesta no utilizable."


def _transportes_por_defecto(url: str, timeout: float) -> Any:
    req = urllib.request.Request(url, headers={
        "User-Agent": "ARHIAX-RE/street-imagery (+due-diligence)",
        "Accept": "application/json, image/*",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _traer_json_urllib(url: str, timeout: float) -> Any:
    crudo = _transportes_por_defecto(url, timeout)
    try:
        return json.loads(crudo.decode("utf-8", "replace"))
    except Exception as exc:  # noqa: BLE001
        raise ErrorFuente(QUERY_FAILED,
                          f"Respuesta no interpretable como JSON: {type(exc).__name__}") from exc


def _traer_bytes_urllib(url: str, timeout: float) -> bytes:
    return _transportes_por_defecto(url, timeout)


# ── abstracción de proveedor (§21) ────────────────────────────────────────────
class StreetImageryProvider(abc.ABC):
    """Abstracción de un proveedor de street imagery.

    Toda consulta devuelve un resultado con estado CERRADO, procedencia completa
    y la política de licencia/persistencia aplicable. La ausencia nunca se
    convierte en ``NO_MATCH``.
    """

    PROVIDER: str = ""
    SOURCE_ID: str = ""
    NOMBRE: str = ""
    REQUIERE_CREDENCIAL: bool = True
    VARIABLES_CREDENCIAL: Tuple[str, ...] = ()
    LICENCIA_DECLARADA: str = ""
    LICENCIA_URL: str = ""
    ATRIBUCION_TEXTO: str = ""
    ATRIBUCION_REQUERIDA: bool = True
    SHARE_ALIKE: bool = False
    TERMS_URL: str = ""
    TERMS_STATUS_POR_DEFECTO: str = TERMS_UNVERIFIED
    FAILURE_SEMANTICS: str = ""
    CAMPOS_METADATA: Tuple[str, ...] = ()
    # Matriz por defecto: CERRADA. Sólo evidencia de términos VERIFICADA puede abrirla.
    PERSISTENCIA_POR_DEFECTO: Dict[str, bool] = {
        "can_persist": False, "can_embed_in_pdf": False,
        "can_modify": False, "can_redistribute": False,
    }
    FLUJO_PERSISTENCIA: str = "NINGUNO"

    def __init__(self, *, credencial: Optional[str] = None,
                 transporte_json: Optional[Callable[[str, float], Any]] = None,
                 transporte_bytes: Optional[Callable[[str, float], bytes]] = None,
                 timeout: float = 10.0,
                 politica_estricta: Optional[bool] = None) -> None:
        self._credencial = credencial
        self._transporte_json = transporte_json or _traer_json_urllib
        self._transporte_bytes = transporte_bytes or _traer_bytes_urllib
        self.timeout = float(timeout)
        self._politica_estricta = politica_estricta
        self._evidencia_terminos: Optional[Dict[str, Any]] = None

    # ── credenciales (nunca se registra el valor) ────────────────────────────
    def credencial(self) -> Optional[str]:
        if self._credencial:
            return self._credencial
        for var in self.VARIABLES_CREDENCIAL:
            valor = os.environ.get(var)
            if valor:
                return valor
        return None

    def credentials_status(self) -> Dict[str, Any]:
        if not self.REQUIERE_CREDENCIAL:
            return {"status": "NOT_REQUIRED", "origin": "NONE", "env_var": None}
        if self._credencial:
            return {"status": "CONFIGURED", "origin": "EXPLICIT", "env_var": None}
        for var in self.VARIABLES_CREDENCIAL:
            if os.environ.get(var):
                return {"status": "CONFIGURED", "origin": "ENV", "env_var": var}
        return {"status": "MISSING", "origin": "NONE",
                "env_var": (self.VARIABLES_CREDENCIAL[0] if self.VARIABLES_CREDENCIAL else None)}

    def _politica_estricta_activa(self) -> bool:
        if self._politica_estricta is not None:
            return bool(self._politica_estricta)
        return str(os.environ.get(_ENV_STRICT_TERMS, "")).strip().lower() in ("1", "true", "yes")

    # ── procedencia ──────────────────────────────────────────────────────────
    def provenance(self, *, operacion: str, extra: Optional[Dict[str, Any]] = None,
                   request_made: bool = False) -> Dict[str, Any]:
        prov = {
            "module": "api/street_imagery.py",
            "provider": self.PROVIDER,
            "source_id": self.SOURCE_ID,
            "source_name": self.NOMBRE,
            "operation": operacion,
            "authority_class": _ds.CONTEXTUAL_EXTERNA,
            "query_method": "HTTPS/JSON",
            "endpoint": self.endpoint(),
            "fields_requested": list(self.CAMPOS_METADATA),
            "failure_semantics": self.FAILURE_SEMANTICS,
            "license_declared": self.LICENCIA_DECLARADA or None,
            "license_url": self.LICENCIA_URL or None,
            "provider_terms_status": self._estado_terminos(),
            "credentials": self.credentials_status(),
            "request_made": bool(request_made),
            "generated_at": ahora(),
            "human_input_required": False,
        }
        prov.update(extra or {})
        return prov

    def endpoint(self) -> str:
        return ""

    def _resultado(self, status: str, *, operacion: str, detail: str = "",
                   payload: Any = None, raw: Any = None,
                   provenance: Optional[Dict[str, Any]] = None,
                   extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        estado = status if status in ESTADOS else QUERY_FAILED
        if status not in ESTADOS:
            detail = (f"Estado no declarado en el vocabulario cerrado ({status!r}); se "
                      f"declara QUERY_FAILED. {detail}").strip()
        base: Dict[str, Any] = {
            "provider": self.PROVIDER,
            "source_id": self.SOURCE_ID,
            "operation": operacion,
            "status": estado,
            "query_id": f"QRY-{self.PROVIDER}-{hash_canonico([self.PROVIDER, operacion, detail])[:12]}",
            "queried_at": ahora(),
            "result_count": (len(payload) if isinstance(payload, (list, tuple, dict)) else 0),
            "raw_hash": hash_canonico(raw) if raw is not None else None,
            "payload_normalized": payload,
            "detail": detail,
            "provenance": dict(provenance or self.provenance(operacion=operacion)),
            "facade_view_level": NO_IMAGE_AVAILABLE,
            "selection": None,
            "human_input_required": False,
            "blocks_dictus": False,
        }
        base.update(extra or {})
        return base

    # ── hooks específicos del proveedor ──────────────────────────────────────
    @abc.abstractmethod
    def _url_metadata(self, lat: float, lon: float, *, radio_m: float) -> Tuple[str, Dict[str, Any]]:
        raise NotImplementedError

    @abc.abstractmethod
    def _estado_de_respuesta(self, payload: Any) -> Tuple[str, str]:
        """Traduce la respuesta del proveedor a un estado cerrado + motivo."""
        raise NotImplementedError

    @abc.abstractmethod
    def _candidatos(self, payload: Any) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def _url_imagen(self, image_id: str, vista: Dict[str, Any]) -> str:
        raise ErrorFuente(NOT_SUPPORTED,
                          f"{self.PROVIDER} no expone descarga directa de bytes en este módulo.")

    # ── transporte ───────────────────────────────────────────────────────────
    def _traer_json(self, url: str, params: Optional[Dict[str, Any]] = None) -> Any:
        completa = url
        if params:
            limpio = {k: v for k, v in params.items() if v is not None}
            completa = f"{url}?{urllib.parse.urlencode(limpio)}"
        try:
            return self._transporte_json(completa, self.timeout)
        except ErrorFuente:
            raise
        except urllib.error.HTTPError as exc:
            estado, motivo = estado_por_http(exc.code)
            raise ErrorFuente(estado, motivo) from exc
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            raise ErrorFuente(SOURCE_UNAVAILABLE,
                              f"La fuente no respondió ({type(exc).__name__}).") from exc
        except Exception as exc:  # noqa: BLE001
            raise ErrorFuente(QUERY_FAILED,
                              f"Fallo inesperado de consulta: {type(exc).__name__}: {exc}") from exc

    def _traer_bytes(self, url: str) -> bytes:
        try:
            return self._transporte_bytes(url, self.timeout)
        except ErrorFuente:
            raise
        except urllib.error.HTTPError as exc:
            estado, motivo = estado_por_http(exc.code)
            raise ErrorFuente(estado, motivo) from exc
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            raise ErrorFuente(SOURCE_UNAVAILABLE,
                              f"La fuente no respondió ({type(exc).__name__}).") from exc
        except Exception as exc:  # noqa: BLE001
            raise ErrorFuente(QUERY_FAILED,
                              f"Fallo inesperado de descarga: {type(exc).__name__}: {exc}") from exc

    # ── término/licencia ─────────────────────────────────────────────────────
    def _estado_terminos(self) -> str:
        if self._evidencia_terminos and self._evidencia_terminos.get("terms_status"):
            return str(self._evidencia_terminos["terms_status"])
        if self.TERMS_STATUS_POR_DEFECTO not in ESTADOS_TERMINOS:
            return TERMS_UNVERIFIED
        return self.TERMS_STATUS_POR_DEFECTO

    def registrar_evidencia_terminos(self, evidencia: Dict[str, Any]) -> Dict[str, Any]:
        """Registra evidencia de términos verificada (url + fecha + hash)."""
        ev = dict(evidencia or {})
        valida = bool(ev.get("evidence_url")) and bool(ev.get("retrieved_at")) and bool(ev.get("sha256"))
        if not valida:
            ev["terms_status"] = TERMS_UNVERIFIED
            ev["reason"] = ("Evidencia incompleta (falta evidence_url, retrieved_at o sha256): "
                            "no se acepta como verificación → UNVERIFIED (fail-closed).")
        elif ev.get("terms_status") not in ESTADOS_TERMINOS:
            ev["terms_status"] = TERMS_UNVERIFIED
            ev["reason"] = "terms_status no declarado en el vocabulario: UNVERIFIED."
        self._evidencia_terminos = ev
        return dict(ev)

    def license_info(self, *, image_id: Optional[str] = None,
                     image_metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Licencia y términos aplicables, con estado declarado (fail-closed)."""
        meta = dict(image_metadata or {})
        estado = self._estado_terminos()
        motivos: List[str] = []
        licencia_imagen = meta.get("license") or meta.get("licencia")
        if licencia_imagen:
            declarada = (self.LICENCIA_DECLARADA or "").strip().lower()
            observada = str(licencia_imagen).strip().lower()
            if not declarada or (declarada not in observada and observada not in declarada):
                estado = TERMS_UNVERIFIED
                motivos.append(f"La metadata de la imagen declara «{licencia_imagen}», que no "
                               f"coincide con la licencia declarada del proveedor: UNVERIFIED.")
        elif estado in (TERMS_DECLARED, TERMS_VERIFIED) and self.LICENCIA_DECLARADA:
            motivos.append("La metadata de la imagen no declara licencia propia: se registra la "
                           "licencia declarada del proveedor.")
        if self._politica_estricta_activa() and estado != TERMS_VERIFIED:
            motivos.append("Política estricta activa: sólo términos VERIFIED habilitan persistir.")
        return {
            "provider": self.PROVIDER,
            "image_id": image_id,
            "provider_terms_status": estado,
            "terms_status": estado,
            "license_name": self.LICENCIA_DECLARADA or None,
            "license_url": self.LICENCIA_URL or None,
            "terms_url": self.TERMS_URL or None,
            "terms_evidence": dict(self._evidencia_terminos or {}) or None,
            "license_observed_in_metadata": licencia_imagen,
            "attribution_required": bool(self.ATRIBUCION_REQUERIDA),
            "attribution_text": self.ATRIBUCION_TEXTO or None,
            "share_alike": bool(self.SHARE_ALIKE),
            "observations": motivos,
            "provenance": self.provenance(operacion="license_info"),
        }

    def persistence_policy(self, *, terms_evidence: Optional[Dict[str, Any]] = None,
                           image_metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Decisión de persistencia por proveedor. FAIL-CLOSED por defecto.

        Regla: una imagen NO puede descargarse, guardarse, modificarse ni
        incrustarse en PDF si los términos no lo permiten de forma verificable.
        La metadata de la imagen sólo puede RESTRINGIR (nunca ampliar) el permiso;
        ampliarlo exige evidencia de términos VERIFICADA con url+fecha+hash.
        """
        if terms_evidence:
            self.registrar_evidencia_terminos(terms_evidence)
        info = self.license_info(image_metadata=image_metadata)
        estado = info["provider_terms_status"]
        matriz = dict(self.PERSISTENCIA_POR_DEFECTO)
        motivos = list(info["observations"])
        abierta_por_evidencia = False
        evidencia = info.get("terms_evidence") or {}

        if estado == TERMS_RESTRICTED:
            matriz = {k: False for k in matriz}
            motivos.append("Los términos consultados PROHÍBEN persistir: se cierra la matriz.")
        elif estado == TERMS_VERIFIED and evidencia.get("license_allows_persist") is True:
            for clave in ("can_persist", "can_embed_in_pdf", "can_modify", "can_redistribute"):
                if clave in evidencia:
                    matriz[clave] = bool(evidencia[clave])
            abierta_por_evidencia = bool(matriz.get("can_persist"))
            motivos.append("Permiso otorgado por evidencia de términos VERIFICADA "
                           "(url + fecha + hash registrados).")
        elif estado == TERMS_UNVERIFIED:
            matriz = {k: False for k in matriz}
            motivos.append("Términos no verificables: matriz cerrada (can_persist=False, "
                           "can_embed_in_pdf=False). No se asume permiso.")
        elif self._politica_estricta_activa() and estado != TERMS_VERIFIED:
            matriz = {k: False for k in matriz}
            motivos.append("Política estricta activa y términos no VERIFIED: matriz cerrada.")
        elif estado == TERMS_DECLARED:
            motivos.append(
                f"Licencia DECLARADA por el contrato del proveedor "
                f"({self.LICENCIA_DECLARADA or 'sin nombre'}): permite persistir con "
                f"atribución obligatoria"
                + (" y share-alike." if self.SHARE_ALIKE else ".")
                + " No se ha verificado en línea en esta corrida (terms_status=DECLARED, no "
                  "VERIFIED); activar ARHIAX_IMAGERY_STRICT_TERMS=1 exige VERIFIED.")

        if not matriz.get("can_persist"):
            matriz["can_embed_in_pdf"] = False
        return {
            "provider": self.PROVIDER,
            "provider_terms_status": estado,
            "can_persist": bool(matriz.get("can_persist", False)),
            "can_download_bytes": bool(matriz.get("can_persist", False)),
            "can_embed_in_pdf": bool(matriz.get("can_embed_in_pdf", False)),
            "can_modify": bool(matriz.get("can_modify", False)),
            "can_redistribute": bool(matriz.get("can_redistribute", False)),
            "storage_flow": self.FLUJO_PERSISTENCIA if matriz.get("can_persist") else "NINGUNO",
            "attribution_required": bool(self.ATRIBUCION_REQUERIDA),
            "attribution_text": self.ATRIBUCION_TEXTO or None,
            "share_alike": bool(self.SHARE_ALIKE),
            "evidence_based_override": abierta_por_evidencia,
            "reasons": motivos,
            "fail_closed": not bool(matriz.get("can_persist")),
            "provenance": self.provenance(operacion="persistence_policy"),
        }

    # ── §21 · métodos exigidos ───────────────────────────────────────────────
    def get_metadata(self, lat: float, lon: float, *, radio_m: float = 50.0,
                     coordenada_oficial: Any = None) -> Dict[str, Any]:
        """Metadata del proveedor para el punto (sólo metadata; sin bytes)."""
        cred = self.credentials_status()
        if cred["status"] == "MISSING":
            return self._resultado(
                SOURCE_UNAVAILABLE, operacion="get_metadata", detail=MOTIVO_SIN_CREDENCIALES,
                provenance=self.provenance(operacion="get_metadata",
                                           extra={"credentials": cred, "request_made": False}))
        try:
            url, params = self._url_metadata(lat, lon, radio_m=radio_m)
        except ErrorFuente as exc:
            return self._resultado(exc.estado, operacion="get_metadata", detail=exc.detalle,
                                   provenance=self.provenance(operacion="get_metadata"))
        endpoint = url
        try:
            payload = self._traer_json(url, params)
        except ErrorFuente as exc:
            return self._resultado(
                exc.estado, operacion="get_metadata", detail=exc.detalle,
                provenance=self.provenance(operacion="get_metadata",
                                           extra={"credentials": cred, "request_made": True,
                                                  "endpoint": endpoint}))
        estado, motivo = self._estado_de_respuesta(payload)
        candidatos = self._candidatos(payload) if estado == AVAILABLE else []
        if estado == AVAILABLE and not candidatos:
            estado, motivo = NO_MATCH, ("El proveedor respondió correctamente y no hay imagen "
                                        "en el punto consultado (NO_MATCH declarado).")
        return self._resultado(
            estado, operacion="get_metadata", detail=motivo, raw=payload,
            payload={"candidates": candidatos, "candidate_count": len(candidatos),
                     "request": {"lat": float(lat), "lon": float(lon), "radio_m": float(radio_m)}},
            provenance=self.provenance(operacion="get_metadata",
                                       extra={"credentials": cred, "request_made": True,
                                              "endpoint": endpoint,
                                              "request_params": sorted(params.keys())}))

    def get_best_view(self, lat: float, lon: float, building_geometry: Any = None, *,
                      coordenada_oficial: Any = None, altura_edificio_m: Any = None,
                      radio_m: float = 50.0,
                      tolerancia_alineacion_deg: float = TOLERANCIA_ALINEACION_DEG) -> Dict[str, Any]:
        """Selecciona AUTOMÁTICAMENTE la vista orientada hacia el inmueble."""
        meta = self.get_metadata(lat, lon, radio_m=radio_m, coordenada_oficial=coordenada_oficial)
        licencia = self.license_info()
        politica = self.persistence_policy()
        prov = self.provenance(operacion="get_best_view",
                               extra={"query_id": meta.get("query_id"),
                                      "metadata_status": meta.get("status"),
                                      "endpoint": meta.get("provenance", {}).get("endpoint")})
        if meta["status"] != AVAILABLE:
            return self._resultado(
                meta["status"], operacion="get_best_view",
                detail=meta["detail"] or "Sin metadata utilizable: no se selecciona vista.",
                raw=meta.get("raw_hash"),
                provenance=prov,
                extra={"facade_view_level": NO_IMAGE_AVAILABLE, "selection": None,
                       "metadata_status": meta["status"], "license": licencia,
                       "persistence": politica})
        candidatos = (meta.get("payload_normalized") or {}).get("candidates") or []
        centroide = centroide_huella(building_geometry) if building_geometry else None
        seleccion = seleccionar_vista_automatica(
            candidatos, coordenada_oficial=coordenada_oficial or {"lat": lat, "lon": lon},
            centroide_edificio=centroide, altura_edificio_m=altura_edificio_m,
            proveedor=self.PROVIDER, tolerancia_alineacion_deg=tolerancia_alineacion_deg)
        return self._resultado(
            AVAILABLE, operacion="get_best_view",
            detail=("Vista seleccionada automáticamente por azimut cámara→inmueble." if
                    seleccion.get("imagen") else str(seleccion.get("motivo") or "")),
            raw=meta.get("raw_hash"), payload=seleccion, provenance=prov,
            extra={"facade_view_level": seleccion.get("facade_view_level", NO_IMAGE_AVAILABLE),
                   "selection": seleccion, "metadata_status": AVAILABLE,
                   "license": licencia, "persistence": politica,
                   "human_input_required": False})

    def get_image(self, lat: Optional[float] = None, lon: Optional[float] = None, *,
                  image_id: Optional[str] = None, vista: Optional[Dict[str, Any]] = None,
                  dest_dir: Any = None, allow_download: bool = True,
                  terms_evidence: Optional[Dict[str, Any]] = None,
                  image_metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Obtiene los bytes de la imagen SOLO si la política de licencia lo permite."""
        vista = dict(vista or {})
        image_id = image_id or vista.get("image_id") or vista.get("imagen")
        crudo_licencia = (image_metadata if image_metadata is not None
                          else vista.get("license_metadata"))
        meta_imagen = ({"license": crudo_licencia} if isinstance(crudo_licencia, str)
                       else dict(crudo_licencia or {}))
        politica = self.persistence_policy(terms_evidence=terms_evidence,
                                           image_metadata=meta_imagen)
        licencia = self.license_info(image_id=image_id, image_metadata=meta_imagen)
        extra = {"downloaded": False, "bytes_written": 0, "path": None, "content_bytes": None,
                 "sha256": None, "can_persist": politica["can_persist"],
                 "can_embed_in_pdf": politica["can_embed_in_pdf"],
                 "persistence": politica, "license": licencia,
                 "attribution": licencia.get("attribution_text")}
        if not image_id:
            return self._resultado(NOT_SUPPORTED, operacion="get_image",
                                   detail="Sin image_id: no hay imagen que obtener.",
                                   extra=extra)
        if not politica["can_persist"]:
            return self._resultado(
                NOT_SUPPORTED, operacion="get_image",
                detail=("Licencia/términos del proveedor no permiten descargar ni persistir "
                        "esta imagen: NO se descarga ningún byte (fail-closed). "
                        + " ".join(politica.get("reasons") or [])).strip(),
                provenance=self.provenance(operacion="get_image",
                                           extra={"policy": politica,
                                                  "download_attempted": False}),
                extra=extra)
        if not allow_download:
            return self._resultado(NOT_SUPPORTED, operacion="get_image",
                                   detail="Descarga deshabilitada explícitamente por el llamador.",
                                   extra=extra)
        cred = self.credentials_status()
        if cred["status"] == "MISSING":
            return self._resultado(
                SOURCE_UNAVAILABLE, operacion="get_image", detail=MOTIVO_SIN_CREDENCIALES,
                provenance=self.provenance(operacion="get_image",
                                           extra={"credentials": cred, "download_attempted": False}),
                extra=extra)
        try:
            url = self._url_imagen(str(image_id), vista)
        except ErrorFuente as exc:
            return self._resultado(exc.estado, operacion="get_image", detail=exc.detalle,
                                   extra=extra)
        try:
            contenido = self._traer_bytes(url)
        except ErrorFuente as exc:
            return self._resultado(
                exc.estado, operacion="get_image",
                detail=f"No se pudo descargar la imagen: {exc.detalle}",
                provenance=self.provenance(operacion="get_image",
                                           extra={"credentials": cred, "download_attempted": True,
                                                  "endpoint": url.split("?")[0]}),
                extra=extra)
        sha = hash_canonico(contenido)
        ruta_rel: Optional[str] = None
        if dest_dir is not None:
            try:
                carpeta = Path(dest_dir)
                carpeta.mkdir(parents=True, exist_ok=True)
                destino = carpeta / f"{self.PROVIDER.lower()}_{image_id}.jpg"
                destino.write_bytes(contenido)
                try:
                    ruta_rel = str(destino.relative_to(_DIR_RAIZ))
                except ValueError:
                    ruta_rel = str(destino)
            except OSError as exc:
                return self._resultado(
                    QUERY_FAILED, operacion="get_image",
                    detail=(f"Los bytes se obtuvieron, pero NO pudieron persistirse en disco: "
                            f"{type(exc).__name__}: {exc}"),
                    payload={"image_id": image_id, "sha256": sha, "persisted": False},
                    provenance=self.provenance(operacion="get_image",
                                               extra={"credentials": cred,
                                                      "download_attempted": True,
                                                      "endpoint": url.split("?")[0]}),
                    extra={**extra, "downloaded": True, "bytes_written": 0,
                           "sha256": sha, "content_bytes": contenido})
        extra.update({"downloaded": True, "bytes_written": len(contenido),
                      "path": ruta_rel, "content_bytes": contenido, "sha256": sha})
        return self._resultado(
            AVAILABLE, operacion="get_image",
            detail=("Imagen obtenida bajo licencia que permite persistir. Atribución "
                    f"obligatoria: {licencia.get('attribution_text') or 'n/d'}."),
            raw=contenido, payload={"image_id": image_id, "sha256": sha,
                                    "persisted": bool(ruta_rel)},
            provenance=self.provenance(operacion="get_image",
                                       extra={"credentials": cred, "download_attempted": True,
                                              "endpoint": url.split("?")[0]}),
            extra=extra)


# ── MAPILLARY (candidato principal de persistencia) ───────────────────────────
class MapillaryProvider(StreetImageryProvider):
    """Mapillary Graph API. Licencia declarada CC BY-SA 4.0 (atribución + share-alike).

    Es el candidato principal de persistencia del sistema: la licencia permite
    conservar e incrustar la imagen con atribución. Aun así, si la metadata de la
    imagen declara otra licencia (o ninguna verificable), la política se CIERRA
    para esa imagen.
    """

    PROVIDER = MAPILLARY
    SOURCE_ID = "IMAGERY_MAPILLARY"
    NOMBRE = "Mapillary (vista callejera colaborativa)"
    REQUIERE_CREDENCIAL = True
    VARIABLES_CREDENCIAL = ("ARHIAX_MAPILLARY_TOKEN", "MAPILLARY_TOKEN",
                            "MAPILLARY_ACCESS_TOKEN")
    LICENCIA_DECLARADA = "CC BY-SA 4.0"
    LICENCIA_URL = "https://www.mapillary.com/terms"
    TERMS_URL = "https://www.mapillary.com/terms"
    ATRIBUCION_TEXTO = "© Mapillary contributors (CC BY-SA 4.0)"
    ATRIBUCION_REQUERIDA = True
    SHARE_ALIKE = True
    TERMS_STATUS_POR_DEFECTO = TERMS_DECLARED
    FAILURE_SEMANTICS = ("sin token -> SOURCE_UNAVAILABLE; HTTP 401/403/429 o 5xx -> "
                         "SOURCE_UNAVAILABLE; data vacía con respuesta válida -> NO_MATCH")
    CAMPOS_METADATA = ("id", "computed_geometry", "computed_compass_angle", "is_pano",
                       "captured_at", "thumb_1024_url", "width", "height")
    # Persistencia permitida por la licencia declarada (con atribución y share-alike).
    PERSISTENCIA_POR_DEFECTO = {"can_persist": True, "can_embed_in_pdf": True,
                                "can_modify": True, "can_redistribute": True}
    FLUJO_PERSISTENCIA = "COPIAR_BAJO_CC_BY_SA_4_0_CON_ATRIBUCION"
    URL_BASE = "https://graph.mapillary.com/images"

    def endpoint(self) -> str:
        return self.URL_BASE

    def _url_metadata(self, lat: float, lon: float, *, radio_m: float) -> Tuple[str, Dict[str, Any]]:
        dlat = float(radio_m) / 111320.0
        dlon = float(radio_m) / max(1e-6, 111320.0 * math.cos(math.radians(float(lat))))
        bbox = f"{lon - dlon:.7f},{lat - dlat:.7f},{lon + dlon:.7f},{lat + dlat:.7f}"
        return self.URL_BASE, {
            "access_token": self.credencial(),
            "fields": ",".join(self.CAMPOS_METADATA),
            "bbox": bbox,
            "limit": 50,
        }

    def _estado_de_respuesta(self, payload: Any) -> Tuple[str, str]:
        if not isinstance(payload, dict):
            return QUERY_FAILED, "Respuesta de Mapillary no interpretable como objeto JSON."
        error = payload.get("error")
        if error:
            msg = (error.get("message") if isinstance(error, dict) else str(error)) or "error"
            codigo = error.get("code") if isinstance(error, dict) else None
            if str(codigo) in ("190", "102", "104") or "token" in msg.lower():
                return SOURCE_UNAVAILABLE, f"Mapillary rechazó la credencial: {msg}"
            return QUERY_FAILED, f"Mapillary devolvió error: {msg}"
        data = payload.get("data")
        if data is None:
            return QUERY_FAILED, "Respuesta de Mapillary sin campo 'data'."
        if not isinstance(data, list):
            return QUERY_FAILED, "El campo 'data' de Mapillary no es una lista."
        return AVAILABLE, f"Mapillary respondió con {len(data)} imágenes candidatas."

    def _candidatos(self, payload: Any) -> List[Dict[str, Any]]:
        salida: List[Dict[str, Any]] = []
        for item in (payload or {}).get("data") or []:
            if not isinstance(item, dict):
                continue
            geom = item.get("computed_geometry") or item.get("geometry") or {}
            coords = geom.get("coordinates") if isinstance(geom, dict) else None
            if not coords or len(coords) < 2:
                continue
            capturado = item.get("captured_at")
            fecha = None
            if capturado:
                try:
                    ms = float(capturado)
                    if ms > 1e11:      # milisegundos
                        ms = ms / 1000.0
                    fecha = datetime.fromtimestamp(ms, tz=timezone.utc).date().isoformat()
                except (TypeError, ValueError, OSError):
                    fecha = None
            try:
                salida.append({
                    "image_id": str(item.get("id") or ""),
                    "panorama_id": str(item.get("id") or ""),
                    "camera_lat": float(coords[1]), "camera_lon": float(coords[0]),
                    "compass_angle": item.get("computed_compass_angle"),
                    "is_pano": bool(item.get("is_pano")),
                    "capture_date": fecha,
                    "attribution": self.ATRIBUCION_TEXTO,
                    "provider": self.PROVIDER,
                    "width": item.get("width"), "height": item.get("height"),
                    "fov": None,
                    "license": item.get("license") or self.LICENCIA_DECLARADA,
                    "url": item.get("thumb_1024_url"),
                    "metadata": dict(item),
                })
            except (TypeError, ValueError):
                continue
        return salida

    def _url_imagen(self, image_id: str, vista: Dict[str, Any]) -> str:
        thumb = (vista.get("url") or (vista.get("metadata") or {}).get("thumb_1024_url")
                 or (vista.get("license_metadata") or {}).get("thumb_1024_url"))
        if thumb:
            return str(thumb)
        token = self.credencial() or ""
        return (f"{self.URL_BASE}/{urllib.parse.quote(str(image_id))}"
                f"?access_token={urllib.parse.quote(token)}&fields=thumb_1024_url")


# ── GOOGLE STREET VIEW (fail-closed: sin persistencia) ────────────────────────
class GoogleStreetViewProvider(StreetImageryProvider):
    """Google Street View (Metadata API). Persistencia PROHIBIDA por defecto.

    No se asume que una imagen de Google pueda descargarse, guardarse, modificarse
    ni incrustarse en un PDF: ``can_persist=False`` y ``can_embed_in_pdf=False``
    salvo evidencia de términos VERIFICADA. Sin verificación →
    ``provider_terms_status="UNVERIFIED"`` y fail-closed.
    """

    PROVIDER = GOOGLE_STREET_VIEW
    SOURCE_ID = "IMAGERY_GOOGLE_STREET_VIEW"
    NOMBRE = "Google Street View (Maps Platform)"
    REQUIERE_CREDENCIAL = True
    VARIABLES_CREDENCIAL = ("ARHIAX_GOOGLE_MAPS_API_KEY", "GOOGLE_MAPS_API_KEY",
                            "GOOGLE_STREETVIEW_API_KEY")
    LICENCIA_DECLARADA = ""
    LICENCIA_URL = "https://cloud.google.com/maps-platform/terms"
    TERMS_URL = "https://cloud.google.com/maps-platform/terms"
    ATRIBUCION_TEXTO = "© Google"
    ATRIBUCION_REQUERIDA = True
    SHARE_ALIKE = False
    TERMS_STATUS_POR_DEFECTO = TERMS_UNVERIFIED
    FAILURE_SEMANTICS = ("REQUEST_DENIED/OVER_QUERY_LIMIT/sin key -> SOURCE_UNAVAILABLE; "
                         "ZERO_RESULTS/NOT_FOUND -> NO_MATCH; INVALID_REQUEST -> QUERY_FAILED")
    CAMPOS_METADATA = ("status", "date", "pano_id", "location", "copyright")
    PERSISTENCIA_POR_DEFECTO = {"can_persist": False, "can_embed_in_pdf": False,
                                "can_modify": False, "can_redistribute": False}
    FLUJO_PERSISTENCIA = "NINGUNO"
    URL_BASE_METADATA = "https://maps.googleapis.com/maps/api/streetview/metadata"
    URL_BASE_IMAGEN = "https://maps.googleapis.com/maps/api/streetview"

    def endpoint(self) -> str:
        return self.URL_BASE_METADATA

    def _url_metadata(self, lat: float, lon: float, *, radio_m: float) -> Tuple[str, Dict[str, Any]]:
        return self.URL_BASE_METADATA, {
            "location": f"{float(lat):.7f},{float(lon):.7f}",
            "key": self.credencial(),
            "source": "outdoor",
        }

    def _estado_de_respuesta(self, payload: Any) -> Tuple[str, str]:
        if not isinstance(payload, dict):
            return QUERY_FAILED, "Respuesta de Google no interpretable como objeto JSON."
        estado = str(payload.get("status") or "").upper()
        if estado == "OK":
            return AVAILABLE, "Google Street View respondió con panorama disponible."
        if estado in ("ZERO_RESULTS", "NOT_FOUND"):
            return NO_MATCH, ("Google respondió: no hay panorama en el punto consultado "
                              f"(status={estado}).")
        if estado in ("REQUEST_DENIED", "OVER_QUERY_LIMIT", "OVER_DAILY_LIMIT", "UNKNOWN_ERROR"):
            return SOURCE_UNAVAILABLE, (f"Google no pudo atender la consulta "
                                        f"(status={estado}): "
                                        f"{payload.get('error_message') or 'sin detalle'}.")
        if estado == "INVALID_REQUEST":
            return QUERY_FAILED, "Consulta inválida para Google Street View."
        return QUERY_FAILED, f"Google devolvió un estado no reconocido: {estado or 'vacío'}."

    def _candidatos(self, payload: Any) -> List[Dict[str, Any]]:
        if not isinstance(payload, dict):
            return []
        loc = payload.get("location") or {}
        try:
            lat, lon = float(loc.get("lat")), float(loc.get("lng"))
        except (TypeError, ValueError):
            return []
        pano = payload.get("pano_id") or payload.get("panoId")
        return [{
            "image_id": str(pano or f"GSV-{lat:.6f},{lon:.6f}"),
            "panorama_id": pano,
            "camera_lat": lat, "camera_lon": lon,
            "compass_angle": None,          # la Metadata API no expone el azimut del compás
            "is_pano": True,                # Street View es panorámico: el heading se solicita
            "capture_date": payload.get("date"),
            "attribution": payload.get("copyright") or self.ATRIBUCION_TEXTO,
            "provider": self.PROVIDER,
            "width": None, "height": None, "fov": None,
            "license": None,                # la Metadata API no declara licencia de reuso
            "url": None,
            "metadata": dict(payload),
        }]

    def _url_imagen(self, image_id: str, vista: Dict[str, Any]) -> str:
        token = self.credencial() or ""
        lat = vista.get("camera_lat") or vista.get("building_lat")
        lon = vista.get("camera_lon") or vista.get("building_lon")
        params = {
            "size": "640x640",
            "key": urllib.parse.quote(token),
            "heading": vista.get("heading"),
            "pitch": vista.get("pitch"),
            "fov": vista.get("fov"),
        }
        if lat is not None and lon is not None:
            params["location"] = f"{float(lat):.7f},{float(lon):.7f}"
        else:
            params["pano"] = image_id
        limpio = {k: v for k, v in params.items() if v is not None}
        return f"{self.URL_BASE_IMAGEN}?{urllib.parse.urlencode(limpio)}"


# ── NO_IMAGE_AVAILABLE (proveedor centinela) ─────────────────────────────────
class NoImageProvider(StreetImageryProvider):
    """Centinela de ausencia declarada.

    No consulta ninguna fuente y NUNCA inventa imágenes: existe para que la
    ausencia de vista callejera sea un ESTADO EXPLÍCITO y no un hueco silencioso.
    """

    PROVIDER = NO_IMAGE_AVAILABLE
    SOURCE_ID = "IMAGERY_NONE"
    NOMBRE = "Sin imagen disponible (centinela)"
    REQUIERE_CREDENCIAL = False
    LICENCIA_DECLARADA = ""
    ATRIBUCION_REQUERIDA = False
    TERMS_STATUS_POR_DEFECTO = TERMS_NOT_APPLICABLE
    FAILURE_SEMANTICS = "siempre NOT_SUPPORTED: no hay fuente de imagen que consultar"
    PERSISTENCIA_POR_DEFECTO = {"can_persist": False, "can_embed_in_pdf": False,
                                "can_modify": False, "can_redistribute": False}

    def endpoint(self) -> str:
        return ""

    def _url_metadata(self, lat: float, lon: float, *, radio_m: float) -> Tuple[str, Dict[str, Any]]:
        raise ErrorFuente(NOT_SUPPORTED,
                          "Proveedor centinela: no existe fuente de imagen que consultar.")

    def _estado_de_respuesta(self, payload: Any) -> Tuple[str, str]:
        return NOT_SUPPORTED, "Proveedor centinela: no hay imagen disponible."

    def _candidatos(self, payload: Any) -> List[Dict[str, Any]]:
        return []

    def get_metadata(self, lat: float, lon: float, *, radio_m: float = 50.0,
                     coordenada_oficial: Any = None) -> Dict[str, Any]:
        return self._resultado(
            NOT_SUPPORTED, operacion="get_metadata",
            detail=("No hay vista callejera disponible: se declara el estado explícito. "
                    "Una ausencia NO se convierte en NO_MATCH y no se inventa ninguna imagen."),
            payload={"candidates": [], "candidate_count": 0},
            provenance=self.provenance(operacion="get_metadata"))

    def get_best_view(self, lat: float, lon: float, building_geometry: Any = None, *,
                      coordenada_oficial: Any = None, altura_edificio_m: Any = None,
                      radio_m: float = 50.0,
                      tolerancia_alineacion_deg: float = TOLERANCIA_ALINEACION_DEG) -> Dict[str, Any]:
        meta = self.get_metadata(lat, lon, radio_m=radio_m)
        return self._resultado(
            NOT_SUPPORTED, operacion="get_best_view", detail=meta["detail"],
            provenance=self.provenance(operacion="get_best_view"),
            extra={"facade_view_level": NO_IMAGE_AVAILABLE, "selection": None,
                   "license": self.license_info(), "persistence": self.persistence_policy(),
                   "metadata_status": NOT_SUPPORTED})

    def get_image(self, lat: Optional[float] = None, lon: Optional[float] = None, *,
                  image_id: Optional[str] = None, vista: Optional[Dict[str, Any]] = None,
                  dest_dir: Any = None, allow_download: bool = True,
                  terms_evidence: Optional[Dict[str, Any]] = None,
                  image_metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._resultado(
            NOT_SUPPORTED, operacion="get_image",
            detail="Sin imagen disponible: no hay bytes que obtener ni que guardar.",
            extra={"downloaded": False, "bytes_written": 0, "path": None,
                   "content_bytes": None, "can_persist": False, "can_embed_in_pdf": False,
                   "persistence": self.persistence_policy(), "license": self.license_info()})


# ── registro y orquestación automática ────────────────────────────────────────
_CLASES: Dict[str, type] = {
    MAPILLARY: MapillaryProvider,
    GOOGLE_STREET_VIEW: GoogleStreetViewProvider,
    NO_IMAGE_AVAILABLE: NoImageProvider,
}
# Orden de intento: Mapillary primero (persistencia viable), luego Google.
ORDEN_PROVEEDORES: Tuple[str, ...] = (MAPILLARY, GOOGLE_STREET_VIEW)


def obtener_proveedor(nombre: str, **kwargs: Any) -> StreetImageryProvider:
    """Fábrica de proveedores por nombre del vocabulario cerrado."""
    clave = str(nombre or "").upper()
    if clave not in _CLASES:
        raise ValueError(f"Proveedor de street imagery desconocido: {nombre!r}. "
                         f"Válidos: {list(_CLASES)}")
    return _CLASES[clave](**kwargs)


def estado_consolidado(resultados: Any) -> str:
    """Estado agregado de varias consultas. Fail-closed: la duda gana a NO_MATCH."""
    estados = []
    if isinstance(resultados, dict):
        iterable = resultados.values()
    else:
        iterable = resultados or []
    for r in iterable:
        if isinstance(r, dict):
            estados.append(r.get("status"))
        else:
            estados.append(r)
    for preferido in (AVAILABLE, QUERY_FAILED, SOURCE_UNAVAILABLE, NOT_SUPPORTED):
        if preferido in estados:
            return preferido
    return NO_MATCH


def consultar_vista_automatica(lat: float, lon: float, building_geometry: Any = None, *,
                               coordenada_oficial: Any = None, altura_edificio_m: Any = None,
                               radio_m: float = 50.0,
                               proveedores: Optional[Sequence[Any]] = None) -> Dict[str, Any]:
    """Consulta automática: intenta los proveedores en orden y devuelve la mejor vista.

    Nunca exige intervención humana. Si no hay vista, devuelve el estado declarado
    (``SOURCE_UNAVAILABLE``/``NOT_SUPPORTED``/``NO_MATCH``) SIN bloquear el dictamen.
    """
    instancias: List[StreetImageryProvider]
    if proveedores is None:
        instancias = [obtener_proveedor(n) for n in ORDEN_PROVEEDORES]
        instancias.append(obtener_proveedor(NO_IMAGE_AVAILABLE))
    else:
        instancias = [obtener_proveedor(p) if isinstance(p, str) else p for p in proveedores]

    intentos: Dict[str, Dict[str, Any]] = {}
    seleccion: Optional[Dict[str, Any]] = None
    elegido: Optional[str] = None
    for prov in instancias:
        try:
            res = prov.get_best_view(lat, lon, building_geometry,
                                     coordenada_oficial=coordenada_oficial,
                                     altura_edificio_m=altura_edificio_m, radio_m=radio_m)
        except Exception as exc:  # noqa: BLE001 — el fallo es un estado, no una excepción
            res = {"status": QUERY_FAILED, "facade_view_level": NO_IMAGE_AVAILABLE,
                   "selection": None, "provider": prov.PROVIDER,
                   "detail": f"Fallo inesperado: {type(exc).__name__}: {exc}"}
        intentos[prov.PROVIDER] = {
            "status": res.get("status"),
            "facade_view_level": res.get("facade_view_level", NO_IMAGE_AVAILABLE),
            "detail": res.get("detail"),
            "query_id": res.get("query_id"),
            "credentials": prov.credentials_status(),
            "provider_terms_status": prov._estado_terminos(),
            "selection": res.get("selection"),
            "license": res.get("license"),
            "persistence": res.get("persistence"),
        }
        if res.get("status") == AVAILABLE and res.get("selection") and seleccion is None:
            if res["selection"].get("imagen") or res["selection"].get("camera_lat") is not None:
                seleccion, elegido = res["selection"], prov.PROVIDER

    # El centinela NO_IMAGE_AVAILABLE no vota: sólo declara ausencia explícita.
    votantes = ({k: v for k, v in intentos.items() if k != NO_IMAGE_AVAILABLE}
                or dict(intentos))
    estado = estado_consolidado(votantes)
    return {
        "status": estado,
        "provider": elegido,
        "providers_attempted": [p.PROVIDER for p in instancias],
        "attempts": intentos,
        "statuses": {k: v["status"] for k, v in intentos.items()},
        "view": seleccion,
        "facade_view_level": (seleccion or {}).get("facade_view_level", NO_IMAGE_AVAILABLE),
        "human_input_required": False,
        "blocks_dictus": False,
        "dictus_gate_impact": "NONE",
        "detail": ("Vista callejera obtenida automáticamente." if estado == AVAILABLE else
                   "Sin vista callejera utilizable: estado declarado y registrado. La ausencia "
                   "de imagen NO bloquea el análisis ni el dictamen."),
        "provenance": {
            "module": "api/street_imagery.py",
            "generated_at": ahora(),
            "request": {"lat": float(lat), "lon": float(lon), "radio_m": float(radio_m),
                        "coordenada_oficial": _coord_de(coordenada_oficial)},
            "order": [p.PROVIDER for p in instancias],
            "human_input_required": False,
        },
    }


def persistencias_permitidas(proveedores: Optional[Sequence[str]] = None) -> Dict[str, Dict[str, Any]]:
    """Matriz de persistencia declarada por proveedor (para auditoría del PDF)."""
    nombres = list(proveedores or PROVEEDORES)
    salida: Dict[str, Dict[str, Any]] = {}
    for n in nombres:
        prov = obtener_proveedor(n)
        pol = prov.persistence_policy()
        salida[prov.PROVIDER] = {
            "provider_terms_status": pol["provider_terms_status"],
            "can_persist": pol["can_persist"],
            "can_embed_in_pdf": pol["can_embed_in_pdf"],
            "can_modify": pol["can_modify"],
            "storage_flow": pol["storage_flow"],
            "attribution_required": pol["attribution_required"],
        }
    return salida


def verificar_terminos(proveedor: Any, *, url: Optional[str] = None,
                       transporte_bytes: Optional[Callable[[str, float], bytes]] = None,
                       timeout: float = 10.0) -> Dict[str, Any]:
    """Consulta la página de términos y registra evidencia (url + fecha + hash).

    Sólo se declara ``VERIFIED`` si el documento descargado contiene literalmente
    la licencia declarada por el proveedor. Sin red o sin coincidencia →
    ``UNVERIFIED`` y fail-closed. Nunca se fabrica evidencia.
    """
    prov = obtener_proveedor(proveedor) if isinstance(proveedor, str) else proveedor
    destino = url or prov.TERMS_URL or prov.LICENCIA_URL
    evidencia: Dict[str, Any] = {"evidence_url": destino, "retrieved_at": ahora(),
                                 "sha256": None, "terms_status": TERMS_UNVERIFIED}
    if not destino:
        evidencia["reason"] = "El proveedor no declara URL de términos."
        return prov.registrar_evidencia_terminos(evidencia)
    traer = transporte_bytes or prov._transporte_bytes
    try:
        contenido = traer(destino, timeout)
    except Exception as exc:  # noqa: BLE001
        evidencia["reason"] = f"No se pudo consultar los términos ({type(exc).__name__})."
        return prov.registrar_evidencia_terminos(evidencia)
    texto = contenido.decode("utf-8", "replace") if isinstance(contenido, (bytes, bytearray)) \
        else str(contenido)
    evidencia["sha256"] = hash_canonico(contenido if isinstance(contenido, (bytes, bytearray))
                                        else texto)
    evidencia["content_bytes"] = len(contenido) if isinstance(contenido, (bytes, bytearray)) else len(texto)
    declarada = (prov.LICENCIA_DECLARADA or "").strip()
    plano = re.sub(r"<[^>]+>", " ", texto)
    if declarada and declarada.lower() in plano.lower():
        evidencia.update({"terms_status": TERMS_VERIFIED, "license_allows_persist": True,
                          "reason": f"El documento de términos contiene «{declarada}»."})
    else:
        evidencia["reason"] = ("El documento de términos no contiene la licencia declarada "
                              "de forma verificable: UNVERIFIED (fail-closed).")
    return prov.registrar_evidencia_terminos(evidencia)


def verificar_vocabulario() -> Dict[str, Any]:
    """Comprueba que los vocabularios de este módulo coinciden con el Source Pack."""
    return {
        "estados": tuple(ESTADOS) == tuple(_ds.ESTADOS),
        "estados_sin_dato": tuple(ESTADOS_SIN_DATO) == tuple(_ds.ESTADOS_SIN_DATO),
        "niveles_fachada": tuple(NIVELES_FACHADA) == tuple(_ds.NIVELES_FACHADA),
        "autoridad_contextual": _ds.CONTEXTUAL_EXTERNA == "CONTEXTUAL_EXTERNAL",
        "proveedores_sin_duplicados": len(set(PROVEEDORES)) == len(PROVEEDORES),
        "no_match_no_esta_entre_los_sin_dato": NO_MATCH not in ESTADOS_SIN_DATO,
    }


__all__ = [
    "AVAILABLE", "NO_MATCH", "SOURCE_UNAVAILABLE", "NOT_SUPPORTED", "QUERY_FAILED", "ESTADOS",
    "ESTADOS_SIN_DATO", "MAPILLARY", "GOOGLE_STREET_VIEW", "NO_IMAGE_AVAILABLE", "PROVEEDORES",
    "FACADE_VIEW_VERIFIED", "FACADE_VIEW_PROBABLE", "FACADE_VIEW_CONTEXTUAL", "NIVELES_FACHADA",
    "TERMS_VERIFIED", "TERMS_DECLARED", "TERMS_UNVERIFIED", "TERMS_RESTRICTED",
    "TERMS_NOT_APPLICABLE", "ESTADOS_TERMINOS", "TEXTO_VISTA_AUTORIZADO",
    "TEXTO_PROHIBIDO_FACHADA_PRINCIPAL", "METODO_SELECCION",
    "bearing_geodesico", "distancia_metros", "diferencia_angular", "centroide_huella",
    "sanear_texto", "etiqueta_vista_callejera", "normalizar_candidato_crudo",
    "seleccionar_vista_automatica", "estado_por_http", "ErrorFuente",
    "StreetImageryProvider", "MapillaryProvider", "GoogleStreetViewProvider", "NoImageProvider",
    "obtener_proveedor", "estado_consolidado", "consultar_vista_automatica",
    "persistencias_permitidas", "verificar_terminos", "verificar_vocabulario",
]

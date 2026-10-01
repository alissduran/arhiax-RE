# -*- coding: utf-8 -*-
"""
ARHIAX RE — FACADE SOLAR · exposición solar de la FACHADA VISIBLE (§21/§22).

Rótulo obligatorio del análisis: **ANÁLISIS SOLAR AUTOMATIZADO DE LA FACHADA
VISIBLE**. Nunca es una medición física.

Qué hace
────────
Combina, cuando existen, las entradas disponibles:
  · coordenada oficial del predio,
  · geometría de la cámara de street imagery (cámara + inmueble + heading/pitch/fov),
  · huella del edificio (centroide),
  · posición solar (``api/solar_engine.py``),
  · bearing de la fachada visible (normal hacia el observador).
y produce una EXPOSICIÓN declarada: dirección de incidencia, fachada visible,
ángulo relativo sol-fachada y estado aproximado.

Estados cerrados (§22)
──────────────────────
``DIRECT_EXPOSURE_LIKELY | OBLIQUE_EXPOSURE | FACADE_SHADED_OR_REARWARD |
INSUFFICIENT_GEOMETRY``. Sin geometría suficiente el estado es
``INSUFFICIENT_GEOMETRY`` y JAMÁS se promueve a ``DIRECT_EXPOSURE_LIKELY``.

Reglas duras
────────────
1. Si NO hay altura física fiable **no** se simula la longitud física de la
   sombra (``shadow_length_simulated=False``, ``physical_shadow_length_m=None``).
2. ``POT.altura_max`` (altura NORMATIVA) JAMÁS se mapea a
   ``building_physical_height``: se rechaza y se declara. La regla bloqueante se
   delega en ``api/dictus_sources.altura_fisica`` (una sola verdad).
3. Con ``building_height``/``building_levels`` de una fuente automática fiable se
   registra ``height_source``, se habilita la simulación avanzada y
   ``shadow_confidence="OK"``. Sin ella, ``shadow_confidence`` se DEGRADA: nunca
   se bloquea DICTUS y nunca se inventa una altura.
4. Este módulo NO toca valoración, fórmulas, release gate, master hash, identity
   rules, screening thresholds ni la gramática de decisión.
"""
from __future__ import annotations

import datetime as _dt
import importlib
import importlib.util
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

_DIR_API = Path(__file__).resolve().parent
_DIR_RAIZ = _DIR_API.parent


def _cargar_modulo(nombre: str, *rutas: Path):
    """Importa un módulo hermano de ``api/`` de forma determinista (sin cwd/sys.path)."""
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
_si = _cargar_modulo("street_imagery", _DIR_API / "street_imagery.py")
try:
    _solar = _cargar_modulo("solar_engine", _DIR_API / "solar_engine.py",
                            _DIR_RAIZ / "solar_engine.py")
except ImportError:  # pragma: no cover — el motor solar es parte del núcleo
    _solar = None

# ── utilidades numéricas / de coordenadas ─────────────────────────────────────
def _num(v: Any, defecto: Optional[float] = None) -> Optional[float]:
    try:
        if v is None or v == "":
            return defecto
        return float(v)
    except (TypeError, ValueError):
        return defecto


def _coord(valor: Any) -> Optional[Tuple[float, float]]:
    if valor is None:
        return None
    if isinstance(valor, dict):
        lat = _num(valor.get("lat", valor.get("latitud")))
        lon = _num(valor.get("lon", valor.get("longitud")))
    elif isinstance(valor, (tuple, list)) and len(valor) >= 2:
        lat, lon = _num(valor[0]), _num(valor[1])
    else:
        return None
    if lat is None or lon is None:
        return None
    return lat, lon


# ── vocabulario de estados (§22) ──────────────────────────────────────────────
DIRECT_EXPOSURE_LIKELY = "DIRECT_EXPOSURE_LIKELY"
OBLIQUE_EXPOSURE = "OBLIQUE_EXPOSURE"
FACADE_SHADED_OR_REARWARD = "FACADE_SHADED_OR_REARWARD"
INSUFFICIENT_GEOMETRY = "INSUFFICIENT_GEOMETRY"
ESTADOS_EXPOSICION: Tuple[str, ...] = (DIRECT_EXPOSURE_LIKELY, OBLIQUE_EXPOSURE,
                                       FACADE_SHADED_OR_REARWARD, INSUFFICIENT_GEOMETRY)

ETIQUETA_ANALISIS_SOLAR = "ANÁLISIS SOLAR AUTOMATIZADO DE LA FACHADA VISIBLE"
TIPO_ANALISIS = "ANALISIS_SOLAR_AUTOMATIZADO_FACHADA_VISIBLE"
ES_MEDICION_FISICA = False

SHADOW_CONFIDENCE_OK = "OK"
SHADOW_CONFIDENCE_DEGRADED = "DEGRADED"

UMBRAL_INCIDENCIA_DIRECTA_DEG = 45.0
UMBRAL_INCIDENCIA_OBLICUA_DEG = 90.0
ELEVACION_MINIMA_DIRECTA_DEG = 5.0
ELEVACION_MINIMA_SOMBRA_M = 2.0
ALTURA_PISO_M = 3.0
ALTURA_CAMARA_DEFECTO_M = 2.5

# Toda fuente que sea NORMATIVA (no física) queda prohibida como altura del edificio.
TOKENS_ALTURA_PROHIBIDOS: Tuple[str, ...] = ("POT", "NORMATIV", "EDIFICABILIDAD",
                                             "ALTURA_MAXIMA", "ALTURA_MAX")

MOTIVO_SIN_ALTURA = ("No hay fuente automática de altura física: NO se simula longitud "
                     "física exacta de sombra. El estado de exposición se declara como "
                     "aproximado y shadow_confidence se degrada (nunca se bloquea DICTUS).")


class AlturaNormativaComoFisicaRechazada(ValueError):
    """Se intentó mapear una altura NORMATIVA (POT.altura_max) a altura física."""


# ── regla bloqueante §25: altura normativa ≠ altura física ────────────────────
def es_fuente_normativa(height_source: Any) -> bool:
    """¿La fuente declarada es normativa (no física)?"""
    intento = str(height_source or "").upper()
    return bool(intento) and any(t in intento for t in TOKENS_ALTURA_PROHIBIDOS)


def resolver_altura_fisica(*, building_height: Any = None, building_levels: Any = None,
                           height_source: str = "", altura_normativa_pot: Any = None,
                           altura_piso_m: float = ALTURA_PISO_M,
                           estricto: bool = False) -> Dict[str, Any]:
    """Resuelve la altura FÍSICA del edificio, o la degrada declarándolo.

    La decisión la toma ``api/dictus_sources.altura_fisica`` (regla bloqueante
    única del sistema). Aquí sólo se añade la derivación desde niveles y el
    rechazo explícito de fuentes normativas.

    ``estricto=True`` hace FALLAR (``AlturaNormativaComoFisicaRechazada``) cuando
    alguien intenta pasar POT.altura_max como altura física; en el flujo normal
    (``estricto=False``) el intento se rechaza, se declara y no bloquea nada.
    """
    normativa_declarada = _num(altura_normativa_pot)
    if estricto and es_fuente_normativa(height_source) and (building_height is not None
                                                            or building_levels is not None):
        raise AlturaNormativaComoFisicaRechazada(
            f"PROHIBIDO: «{height_source}» es altura NORMATIVA y no puede convertirse en "
            f"building_physical_height. POT.altura_max sólo describe la norma urbanística.")

    def _degradar(motivo: str, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        salida = {"building_physical_height": None, "height_source": None,
                  "shadow_confidence": SHADOW_CONFIDENCE_DEGRADED, "reason": motivo,
                  "engine": "api/dictus_sources.altura_fisica",
                  "blocks_dictus": False, "altura_normativa_pot": normativa_declarada,
                  "altura_normativa_usada_como_fisica": False,
                  "advanced_simulation_enabled": False}
        salida.update(extra or {})
        return salida

    if building_height is None and building_levels is None:
        return _degradar(MOTIVO_SIN_ALTURA)

    if not height_source:
        base = _ds.altura_fisica(building_height if building_height is not None else 0.0)
        return _degradar("Altura/niveles sin fuente declarada: no se acepta como altura "
                         "física del edificio.",
                         {"rejected_source": None, "intento_sin_fuente": True,
                          "dictus_sources_reason": base.get("reason")})

    if es_fuente_normativa(height_source):
        intento = building_height if building_height is not None else (
            _num(building_levels, 0.0) * float(altura_piso_m))
        base = _ds.altura_fisica(intento, height_source=height_source,
                                 altura_normativa_pot=normativa_declarada)
        return _degradar(
            base.get("reason") or ("RECHAZADO: altura normativa no es altura física."),
            {"rejected_source": height_source,
             "intento_rechazado": {"building_height": _num(building_height),
                                   "building_levels": _num(building_levels)},
             "dictus_sources_reason": base.get("reason")})

    if building_height is None:
        niveles = _num(building_levels)
        if not niveles or niveles <= 0:
            return _degradar("Niveles inválidos: no se deriva altura física.",
                             {"rejected_source": height_source})
        derivada = round(float(niveles) * float(altura_piso_m), 3)
        fuente_derivada = f"{height_source} [derivada: {niveles} niveles × {altura_piso_m} m]"
        base = _ds.altura_fisica(derivada, height_source=fuente_derivada,
                                 altura_normativa_pot=normativa_declarada)
        salida = dict(base)
        salida.update({
            "engine": "api/dictus_sources.altura_fisica",
            "derivation": {"building_levels": niveles, "altura_piso_m": float(altura_piso_m),
                           "derived_height_m": derivada,
                           "note": "Altura DERIVADA de niveles declarados por una fuente "
                                   "automática identificada (no es medición ni norma)."},
            "blocks_dictus": False,
            "altura_normativa_pot": normativa_declarada,
            "altura_normativa_usada_como_fisica": False,
            "advanced_simulation_enabled": salida.get("shadow_confidence") == SHADOW_CONFIDENCE_OK,
        })
        return salida

    base = _ds.altura_fisica(building_height, height_source=height_source,
                             altura_normativa_pot=normativa_declarada)
    salida = dict(base)
    salida.update({"engine": "api/dictus_sources.altura_fisica",
                   "blocks_dictus": False, "altura_normativa_pot": normativa_declarada,
                   "altura_normativa_usada_como_fisica": False,
                   "advanced_simulation_enabled":
                       salida.get("shadow_confidence") == SHADOW_CONFIDENCE_OK})
    return salida


def angulo_relativo_sol_fachada(solar_az: float, facade_az: float) -> float:
    """Diferencia angular (0-180°) entre el azimut solar y la normal de la fachada."""
    return _si.diferencia_angular(solar_az, facade_az)


def bearing_fachada_visible(*, camera_lat: Any = None, camera_lon: Any = None,
                            building_lat: Any = None, building_lon: Any = None,
                            heading: Any = None) -> Optional[Dict[str, Any]]:
    """Normal (azimut) de la FACHADA VISIBLE a partir de la geometría de la cámara.

    La superficie visible es la que mira al observador: su normal apunta del
    inmueble hacia la cámara. Sin coordenadas de cámara e inmueble se usa el
    heading de la cámara + 180° (declarado como método distinto). Sin ninguna de
    las dos cosas → ``None`` (geometría insuficiente, no se adivina).
    """
    clat, clon = _num(camera_lat), _num(camera_lon)
    blat, blon = _num(building_lat), _num(building_lon)
    hd = _num(heading)
    if None not in (clat, clon, blat, blon):
        az = _si.bearing_geodesico(blat, blon, clat, clon)
        return {"azimut_normal": round(az, 4),
                "metodo": "NORMAL_FACHADA_VISIBLE_DESDE_CAMARA_CALLEJERA",
                "descripcion": _si.TEXTO_VISTA_AUTORIZADO,
                "distancia_camara_inmueble_m": round(
                    _si.distancia_metros(clat, clon, blat, blon), 3)}
    if hd is not None:
        return {"azimut_normal": round((hd + 180.0) % 360.0, 4),
                "metodo": "HEADING_CAMARA_MAS_180_SIN_COORDENADA_DEL_INMUEBLE",
                "descripcion": _si.TEXTO_VISTA_AUTORIZADO,
                "distancia_camara_inmueble_m": None}
    return None


def _extraer_geometria_camara(valor: Any) -> Optional[Dict[str, Any]]:
    """Normaliza la geometría de cámara (dict de street imagery o de la corrida)."""
    if not isinstance(valor, dict):
        return None
    # Puede venir el agregado de street_imagery ({"view": {...}}) o la selección directa.
    if isinstance(valor.get("view"), dict):
        agregado = valor
        valor = dict(agregado["view"])
        valor.setdefault("imagery_status", agregado.get("status"))
        valor.setdefault("imagery_facade_view_level", agregado.get("facade_view_level"))
    campos = ("camera_lat", "camera_lon", "building_lat", "building_lon", "heading", "pitch",
              "fov", "provider", "image_id", "panorama_id", "capture_date",
              "bearing_camera_to_building_deg", "facade_view_level", "imagery_status",
              "selection_method")
    salida = {k: valor.get(k) for k in campos}
    if all(salida.get(k) is None for k in ("camera_lat", "camera_lon", "heading")):
        return None
    return salida


def _resolver_solar(*, lat: Any, lon: Any, dt: Any = None, fecha: Any = None, hora: Any = None,
                    solar_position: Any = None, tz_offset: float = -5.0) -> Optional[Dict[str, Any]]:
    """Posición solar declarada o calculada con ``api/solar_engine.py``."""
    if solar_position is not None:
        az = el = None
        if isinstance(solar_position, dict):
            az = _num(solar_position.get("azimut", solar_position.get("azimuth")))
            el = _num(solar_position.get("elevacion", solar_position.get("elevation")))
        elif isinstance(solar_position, (tuple, list)) and len(solar_position) >= 2:
            az, el = _num(solar_position[0]), _num(solar_position[1])
        if az is None or el is None:
            return None
        return {"azimut": az, "elevacion": el, "origen": "DECLARADA_POR_LLAMADOR",
                "fecha_hora": None}
    if _solar is None:
        return None
    momento = None
    if isinstance(dt, _dt.datetime):
        momento = dt
    elif fecha is not None:
        try:
            if isinstance(fecha, str):
                base = _dt.date.fromisoformat(fecha[:10])
            elif isinstance(fecha, _dt.date):
                base = fecha
            else:
                base = None
            if base is not None:
                h = _num(hora, 12.0) or 12.0
                minutos_totales = int(round(h * 60.0)) % (24 * 60)
                momento = _dt.datetime(base.year, base.month, base.day,
                                       minutos_totales // 60, minutos_totales % 60)
        except (ValueError, TypeError):
            momento = None
    if momento is None:
        return None
    latn, lonn = _num(lat), _num(lon)
    if latn is None or lonn is None:
        return None
    try:
        az, el = _solar.get_solar_position(latn, lonn, momento, tz_offset=tz_offset)
    except Exception:  # noqa: BLE001 — el fallo es un estado, no una excepción
        return None
    return {"azimut": float(az), "elevacion": float(el),
            "origen": "solar_engine.get_solar_position",
            "fecha_hora": momento.isoformat(), "tz_offset": float(tz_offset)}


def _bloqueado_por_obstruccion(solar_az: float, solar_el: float,
                              obstrucciones: Optional[Sequence[Any]]) -> Optional[str]:
    """Sectores de obstrucción DECLARADOS por el llamador (nunca inventados)."""
    for sector in obstrucciones or []:
        try:
            ini, fin, max_el = (float(sector[0]), float(sector[1]), float(sector[2]))
        except (TypeError, ValueError, IndexError):
            continue
        dentro = (ini <= solar_az <= fin) if ini <= fin else (solar_az >= ini or solar_az <= fin)
        if dentro and solar_el <= max_el:
            return f"Obstrucción declarada en el sector {ini:.0f}°-{fin:.0f}° hasta {max_el:.0f}° de elevación."
    return None


class FacadeSolarExposure:
    """Exposición solar declarada de la fachada visible (§21/§22).

    Entradas opcionales: coordenada oficial, geometría de cámara de street
    imagery, huella del edificio, posición solar, bearing de la fachada visible y
    altura física (con ``height_source``). Nada es obligatorio: lo que falte se
    declara como geometría faltante y el estado cae en
    ``INSUFFICIENT_GEOMETRY`` en lugar de suponerse.
    """

    def __init__(self, *, lat: Any = None, lon: Any = None, coordenada_oficial: Any = None,
                 camera_geometry: Any = None, geometria_camara: Any = None,
                 building_geometry: Any = None, huella_edificio: Any = None,
                 facade_bearing: Any = None, azimut_fachada: Any = None,
                 building_height: Any = None, building_levels: Any = None,
                 height_source: str = "", altura_normativa_pot: Any = None,
                 solar_position: Any = None, obstrucciones: Optional[Sequence[Any]] = None,
                 altura_piso_m: float = ALTURA_PISO_M,
                 altura_camara_m: float = ALTURA_CAMARA_DEFECTO_M,
                 estricto: bool = False, dt: Any = None, fecha: Any = None,
                 hora: Any = None, tz_offset: float = -5.0) -> None:
        coord = _coord(coordenada_oficial) or _coord((lat, lon))
        self.lat = coord[0] if coord else _num(lat)
        self.lon = coord[1] if coord else _num(lon)
        self.coordenada_oficial = {"lat": self.lat, "lon": self.lon} if coord else None
        self.camera_geometry = _extraer_geometria_camara(
            camera_geometry if camera_geometry is not None else geometria_camara)
        self.building_geometry = building_geometry if building_geometry is not None else huella_edificio
        self.facade_bearing = _num(facade_bearing if facade_bearing is not None else azimut_fachada)
        self.building_height = building_height
        self.building_levels = building_levels
        self.height_source = height_source
        self.altura_normativa_pot = altura_normativa_pot
        self.solar_position = solar_position
        self.obstrucciones = list(obstrucciones or [])
        self.altura_piso_m = float(altura_piso_m)
        self.altura_camara_m = float(altura_camara_m)
        self.estricto = bool(estricto)
        self.dt = dt
        self.fecha = fecha
        self.hora = hora
        self.tz_offset = float(tz_offset)

    # ── constructores de conveniencia (todo automático) ──────────────────────
    @classmethod
    def desde_vista_callejera(cls, lat: Any, lon: Any, vista: Any, **kwargs: Any) -> "FacadeSolarExposure":
        """Construye el análisis desde el resultado de ``street_imagery``."""
        geom = _extraer_geometria_camara(vista)
        return cls(lat=lat, lon=lon, camera_geometry=geom, **kwargs)

    # ── API ──────────────────────────────────────────────────────────────────
    def exposicion(self, *, dt: Any = None, fecha: Any = None, hora: Any = None,
                   solar_position: Any = None, tz_offset: Optional[float] = None) -> Dict[str, Any]:
        """Calcula la exposición declarada de la fachada visible."""
        faltantes: List[str] = []
        sol = _resolver_solar(lat=self.lat, lon=self.lon,
                              dt=dt if dt is not None else self.dt,
                              fecha=fecha if fecha is not None else self.fecha,
                              hora=hora if hora is not None else self.hora,
                              solar_position=(solar_position if solar_position is not None
                                              else self.solar_position),
                              tz_offset=(self.tz_offset if tz_offset is None else tz_offset))
        if sol is None:
            faltantes.append("POSICION_SOLAR")
            if self.lat is None or self.lon is None:
                faltantes.append("COORDENADA_OFICIAL")

        fachada = self._fachada_visible()
        if fachada is None:
            faltantes.append("AZIMUT_FACHADA_VISIBLE")

        altura = resolver_altura_fisica(
            building_height=self.building_height, building_levels=self.building_levels,
            height_source=self.height_source, altura_normativa_pot=self.altura_normativa_pot,
            altura_piso_m=self.altura_piso_m, estricto=self.estricto)

        altura_m = _num(altura.get("building_physical_height"))
        avanzada = bool(altura.get("advanced_simulation_enabled")) and altura_m is not None
        salida: Dict[str, Any] = {
            "etiqueta": ETIQUETA_ANALISIS_SOLAR,
            "analysis_type": TIPO_ANALISIS,
            "es_medicion_fisica": ES_MEDICION_FISICA,
            "estado": INSUFFICIENT_GEOMETRY,
            "estado_aproximado": True,
            "direccion_incidencia_solar": sol,
            "fachada_visible": fachada,
            "angulo_relativo_sol_fachada_deg": None,
            "building_physical_height": altura.get("building_physical_height"),
            "height_source": altura.get("height_source"),
            "altura_regla": altura,
            "altura_normativa_pot": _num(self.altura_normativa_pot),
            "altura_normativa_usada_como_fisica": False,
            "shadow_confidence": altura.get("shadow_confidence"),
            "shadow_length_simulated": False,
            "physical_shadow_length_m": None,
            "simulacion_avanzada_habilitada": avanzada,
            "geometria_faltante": faltantes,
            "motivo": "",
            "limitaciones": [],
            "blocks_dictus": False,
            "dictus_gate_impact": "NONE",
            "human_input_required": False,
            "provenance": self._provenance(sol=sol, fachada=fachada, altura=altura),
        }

        if faltantes:
            salida["motivo"] = (
                "Geometría insuficiente (" + ", ".join(faltantes) + "): no se emite un estado "
                "de exposición. La falta de geometría NUNCA se promueve a "
                "DIRECT_EXPOSURE_LIKELY.")
            salida["limitaciones"].append(
                "Sin posición solar y/o sin azimut de la fachada visible no puede calcularse "
                "el ángulo relativo sol-fachada.")
            return salida

        solar_az, solar_el = float(sol["azimut"]), float(sol["elevacion"])
        facade_az = float(fachada["azimut_normal"])
        delta = round(angulo_relativo_sol_fachada(solar_az, facade_az), 2)
        salida["angulo_relativo_sol_fachada_deg"] = delta

        obstruccion = _bloqueado_por_obstruccion(solar_az, solar_el, self.obstrucciones)
        if solar_el <= 0:
            estado = FACADE_SHADED_OR_REARWARD
            salida["motivo"] = "El sol está bajo el horizonte a la fecha/hora analizada."
        elif obstruccion:
            estado = FACADE_SHADED_OR_REARWARD
            salida["motivo"] = obstruccion
        elif delta <= UMBRAL_INCIDENCIA_DIRECTA_DEG and solar_el >= ELEVACION_MINIMA_DIRECTA_DEG:
            estado = DIRECT_EXPOSURE_LIKELY
            salida["motivo"] = (f"El sol incide sobre la vista identificada con un ángulo "
                                f"relativo de {delta}° (≤ {UMBRAL_INCIDENCIA_DIRECTA_DEG}°).")
        elif delta <= UMBRAL_INCIDENCIA_OBLICUA_DEG:
            estado = OBLIQUE_EXPOSURE
            salida["motivo"] = (
                f"Incidencia oblicua: el ángulo relativo sol-fachada es {delta}°"
                + (" con elevación solar rasante." if solar_el < ELEVACION_MINIMA_DIRECTA_DEG else "."))
        else:
            estado = FACADE_SHADED_OR_REARWARD
            salida["motivo"] = (f"El sol queda por detrás de la vista identificada "
                                f"(ángulo relativo {delta}° > {UMBRAL_INCIDENCIA_OBLICUA_DEG}°).")

        salida["estado"] = estado
        salida["estado_aproximado"] = not avanzada

        if avanzada and solar_el > ELEVACION_MINIMA_SOMBRA_M:
            longitud = float(altura_m) / math.tan(math.radians(solar_el))
            salida["shadow_length_simulated"] = True
            salida["physical_shadow_length_m"] = round(longitud, 3)
            salida["limitaciones"].append(
                "La longitud de sombra es TEÓRICA (altura física de fuente declarada / "
                "tan(elevación)), sin obstrucciones del entorno salvo las declaradas.")
        else:
            salida["limitaciones"].append(MOTIVO_SIN_ALTURA)

        salida["limitaciones"].append(
            "Análisis automatizado de la fachada visible: no es una medición física ni un "
            "levantamiento de campo.")
        if self.camera_geometry is None:
            salida["limitaciones"].append(
                "No hay street imagery disponible: el azimut de fachada proviene de un valor "
                "declarado por el llamador (no de una cámara verificada).")
        return salida

    # alias de paridad de API (inglés)
    def analyze(self, **kwargs: Any) -> Dict[str, Any]:
        return self.exposicion(**kwargs)

    # ── internos ─────────────────────────────────────────────────────────────
    def _fachada_visible(self) -> Optional[Dict[str, Any]]:
        if self.facade_bearing is not None:
            return {"azimut_normal": round(self.facade_bearing % 360.0, 4),
                    "metodo": "DECLARADO_POR_LLAMADOR",
                    "descripcion": _si.TEXTO_VISTA_AUTORIZADO,
                    "distancia_camara_inmueble_m": (
                        self.camera_geometry or {}).get("distancia_camara_inmueble_m")}
        geometria = self.camera_geometry
        centroide = _si.centroide_huella(self.building_geometry) if self.building_geometry else None
        if geometria:
            res = bearing_fachada_visible(
                camera_lat=geometria.get("camera_lat"), camera_lon=geometria.get("camera_lon"),
                building_lat=(centroide or {}).get("lat") if centroide else geometria.get("building_lat"),
                building_lon=(centroide or {}).get("lon") if centroide else geometria.get("building_lon"),
                heading=geometria.get("heading"))
            if res:
                res["camera"] = {
                    "provider": geometria.get("provider"),
                    "image_id": geometria.get("image_id"),
                    "capture_date": geometria.get("capture_date"),
                    "heading": geometria.get("heading"), "pitch": geometria.get("pitch"),
                    "fov": geometria.get("fov"),
                    "facade_view_level": geometria.get("facade_view_level"),
                    "imagery_status": geometria.get("imagery_status"),
                }
                res["target_source"] = ("CENTROIDE_HUELLA_EDIFICIO" if centroide
                                        else "COORDENADA_DEL_INMUEBLE_EN_LA_VISTA")
                return res
        if centroide and (self.lat is not None and self.lon is not None):
            return {"azimut_normal": round(_si.bearing_geodesico(self.lat, self.lon,
                                                                centroide["lat"],
                                                                centroide["lon"]), 4),
                    "metodo": "CENTROIDE_HUELLA_DESDE_COORDENADA_OFICIAL",
                    "descripcion": _si.TEXTO_VISTA_AUTORIZADO,
                    "distancia_camara_inmueble_m": None,
                    "target_source": "CENTROIDE_HUELLA_EDIFICIO"}
        return None

    def _provenance(self, *, sol: Optional[Dict[str, Any]], fachada: Optional[Dict[str, Any]],
                    altura: Dict[str, Any]) -> Dict[str, Any]:
        geom = self.camera_geometry or {}
        return {
            "module": "api/facade_solar.py",
            "label": ETIQUETA_ANALISIS_SOLAR,
            "analysis_type": TIPO_ANALISIS,
            "is_physical_measurement": ES_MEDICION_FISICA,
            "generated_at": _si.ahora(),
            "inputs": {
                "coordenada_oficial": self.coordenada_oficial,
                "imagery_status": geom.get("imagery_status"),
                "imagery_provider": geom.get("provider"),
                "imagery_image_id": geom.get("image_id"),
                "facade_view_level": geom.get("facade_view_level"),
                "building_geometry_present": self.building_geometry is not None,
                "solar_position_source": (sol or {}).get("origen"),
                "facade_bearing_source": (fachada or {}).get("metodo"),
                "obstrucciones_declaradas": len(self.obstrucciones),
            },
            "height_rule": {
                "engine": "api/dictus_sources.altura_fisica",
                "building_physical_height": altura.get("building_physical_height"),
                "height_source": altura.get("height_source"),
                "shadow_confidence": altura.get("shadow_confidence"),
                "altura_normativa_pot_rechazada": altura.get("rejected_source"),
                "pot_altura_max_usada_como_fisica": False,
            },
            "modules": ["api/dictus_sources.py", "api/street_imagery.py",
                        "api/solar_engine.py"],
            "human_input_required": False,
            "blocks_dictus": False,
        }


def analizar_exposicion_fachada(lat: Any = None, lon: Any = None, *,
                                fecha: Any = None, hora: Any = None, dt: Any = None,
                                solar_position: Any = None, vista: Any = None,
                                building_geometry: Any = None, facade_bearing: Any = None,
                                building_height: Any = None, building_levels: Any = None,
                                height_source: str = "", altura_normativa_pot: Any = None,
                                obstrucciones: Optional[Sequence[Any]] = None,
                                **kwargs: Any) -> Dict[str, Any]:
    """Atajo funcional: construye ``FacadeSolarExposure`` y devuelve la exposición."""
    if vista is not None and "camera_geometry" not in kwargs and "geometria_camara" not in kwargs:
        kwargs["camera_geometry"] = vista
    analisis = FacadeSolarExposure(
        lat=lat, lon=lon, building_geometry=building_geometry, facade_bearing=facade_bearing,
        building_height=building_height, building_levels=building_levels,
        height_source=height_source, altura_normativa_pot=altura_normativa_pot,
        solar_position=solar_position, obstrucciones=obstrucciones, **kwargs)
    return analisis.exposicion(dt=dt, fecha=fecha, hora=hora, solar_position=solar_position)


def verificar_vocabulario() -> Dict[str, Any]:
    """Comprueba que los vocabularios coinciden con el Source Pack (§22/§25)."""
    regla_pot = resolver_altura_fisica(building_height=11, height_source="POT.altura_max",
                                       altura_normativa_pot=11)
    fisica_ok = resolver_altura_fisica(building_height=9.0,
                                       height_source="MS_BUILDINGS_FOOTPRINT.height")
    return {
        "estados_exposicion": tuple(ESTADOS_EXPOSICION) == tuple(_ds.ESTADOS_EXPOSICION),
        "etiqueta": ETIQUETA_ANALISIS_SOLAR == _ds.ETIQUETA_ANALISIS_SOLAR,
        "regla_altura_delegada": (regla_pot.get("engine") == "api/dictus_sources.altura_fisica"),
        "pot_rechazado": regla_pot.get("building_physical_height") is None,
        "altura_fisica_con_fuente_aceptada": fisica_ok.get("building_physical_height") == 9.0,
        "nunca_medicion_fisica": ES_MEDICION_FISICA is False,
    }


__all__ = [
    "DIRECT_EXPOSURE_LIKELY", "OBLIQUE_EXPOSURE", "FACADE_SHADED_OR_REARWARD",
    "INSUFFICIENT_GEOMETRY", "ESTADOS_EXPOSICION", "ETIQUETA_ANALISIS_SOLAR", "TIPO_ANALISIS",
    "ES_MEDICION_FISICA", "SHADOW_CONFIDENCE_OK", "SHADOW_CONFIDENCE_DEGRADED",
    "UMBRAL_INCIDENCIA_DIRECTA_DEG", "UMBRAL_INCIDENCIA_OBLICUA_DEG",
    "ELEVACION_MINIMA_DIRECTA_DEG", "ALTURA_PISO_M", "MOTIVO_SIN_ALTURA",
    "TOKENS_ALTURA_PROHIBIDOS", "AlturaNormativaComoFisicaRechazada",
    "es_fuente_normativa", "resolver_altura_fisica", "angulo_relativo_sol_fachada",
    "bearing_fachada_visible", "FacadeSolarExposure", "analizar_exposicion_fachada",
    "verificar_vocabulario",
]

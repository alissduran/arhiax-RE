# -*- coding: utf-8 -*-
"""CLIENTE HTTP ÚNICO DE ADQUISICIÓN DEL SOURCE PACK (FASE B).

Un solo cliente para todo el pack. No hay seis clientes: este módulo es el ÚNICO lugar
donde vive la red y donde se declara **qué perfil de petición** se usó.

PERFIL DE PETICIÓN VERSIONADO
-----------------------------
``barranquilla-navigation-http/1.0.0`` es el perfil de NAVEGACIÓN ya demostrado en
``api/market_harvest.py`` (``NAV_HEADERS``). Este módulo NO re-declara esas cabeceras: las
toma del cliente demostrado (una sola fuente de verdad) y las versiona aquí. El perfil
``basic-agent-json/1.0.0`` es el patrón de la sonda v1 (``Accept: application/json`` con UA
de bot) y se conserva SÓLO como control de la sonda doble.

SONDA DOBLE (A/B) — ARTE FACTUAL, NO INTERPRETACIÓN
--------------------------------------------------
``probe_dual(url)`` pide **la misma URL** bajo los dos perfiles y devuelve AMBOS códigos:

* ``basic_http_status``      -> perfil A (``basic-agent-json/1.0.0``)
* ``navigation_http_status`` -> perfil B (``barranquilla-navigation-http/1.0.0``)

Un ``403`` en A con ``200`` en B NO es ``SOURCE_UNAVAILABLE``: es
``RUNTIME_ACCESS_RESTRICTED`` de la petición básica **con ruta automática válida**. El
cliente no decide el estado operacional: reporta hechos (código, bytes, hash, cuerpo) y
deja que la medición decida. Prohibido etiquetar todo 403 como ``SOURCE_UNAVAILABLE``.

TRANSPORTES (RELEVO)
--------------------
Un relevo HTTP automático es una ruta automática: no exige descarga manual, GIS manual,
click manual, edición manual, valor pegado ni consulta humana. Se declara SIEMPRE con su
nombre de transporte, y la autoridad de la fuente NO se degrada por transportarla.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

__all__ = [
    "VERSION_CLIENTE", "REQUEST_PROFILE_ID", "PROFILE_BASIC_ID",
    "RequestProfile", "PROFILE_BASIC", "PROFILE_NAVIGATION", "PERFILES",
    "perfil_por_id", "BASIC_HEADERS", "NAVIGATION_HEADERS",
    "TRANSPORT_DIRECTO", "TRANSPORT_RELEVO",
    "RawFetch", "fetch_raw", "DualProbe", "probe_dual", "codigo_efectivo",
    "RELEVOS", "RelaySpec", "url_de_relevo", "fetch_via_relay", "fetch_json_arcgis",
    "clasificar_acceso", "ESTADOS_DE_ACCESO",
]


VERSION_CLIENTE = "acquisition-http/1.0.0"

#: Perfil de petición versionado de NAVEGACIÓN (el corregido y demostrado).
REQUEST_PROFILE_ID = "barranquilla-navigation-http/1.0.0"
#: Perfil de CONTROL: patrón de la sonda v1 (el que produjo el 403).
PROFILE_BASIC_ID = "basic-agent-json/1.0.0"

TRANSPORT_DIRECTO = "DIRECT"
TRANSPORT_RELEVO = "RELAY"


# ══════════════════════════════════════════════════════════════════════════════
# 0 · CABECERAS — una sola fuente de verdad para el perfil de navegación
# ══════════════════════════════════════════════════════════════════════════════
BASIC_HEADERS: Dict[str, str] = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ARHIAX-RE-SourcePack/1.0",
    "Accept": "application/json",
}


def _cliente_demostrado():
    """Importa el cliente YA DEMOSTRADO (``api/market_harvest.py``).

    Este módulo NO re-declara ni las cabeceras ni la clase de respuesta del cliente
    demostrado: las TOMA. Se importa en diferido (mismo patrón que usa `market_harvest`
    para `market_evidence`) para no crear ciclos y para que este módulo siga siendo
    importable de forma aislada. Si el módulo demostrado no estuviera disponible, se falla
    CERRADO: NUNCA se inventa un perfil ni una respuesta por silencio.
    """
    try:
        import market_harvest          # noqa: PLC0415
    except ImportError:                # pragma: no cover - ruta de script
        raiz = Path(__file__).resolve().parent.parent
        if str(raiz / "api") not in sys.path:
            sys.path.insert(0, str(raiz / "api"))
        import market_harvest          # noqa: PLC0415,F811
    return market_harvest


_MH = _cliente_demostrado()

#: Cabeceras EXACTAS del perfil ``barranquilla-navigation-http/1.0.0``.
NAVIGATION_HEADERS: Dict[str, str] = dict(_MH.NAV_HEADERS)

#: MEDIDO Y REPRODUCIBLE (docs/source_pack/raw/phase_b/_probe_matrix_2x2.json):
#: el geoportal responde 200 SÓLO con el contexto TLS por defecto (verificación de
#: certificado ACTIVA) **y** el perfil de navegación. Cualquier otro cuadrante — incluido
#: un contexto con `verify_mode=CERT_NONE`, que es el que usaban las herramientas de la
#: sonda v1 — recibe 403 de Cloudflare. Desactivar la verificación NO es una opción de
#: este cliente: se declara aquí para que ninguna herramienta vuelva a introducirlo.
TLS_VERIFICACION_OBLIGATORIA = True


@dataclass(frozen=True)
class RequestProfile:
    """Un perfil de petición VERSIONADO. Lo que no está aquí, no se envió."""

    profile_id: str
    headers: Mapping[str, str]
    descripcion: str
    es_perfil_operativo: bool

    def como_dict(self) -> Dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "descripcion": self.descripcion,
            "es_perfil_operativo": self.es_perfil_operativo,
            "cabeceras": dict(self.headers),
        }


PROFILE_BASIC = RequestProfile(
    profile_id=PROFILE_BASIC_ID,
    headers=BASIC_HEADERS,
    descripcion=("Patrón de la sonda v1: User-Agent de bot + `Accept: application/json`. "
                 "Se conserva SÓLO como control A/B; no es el perfil operativo."),
    es_perfil_operativo=False,
)

PROFILE_NAVIGATION = RequestProfile(
    profile_id=REQUEST_PROFILE_ID,
    headers=NAVIGATION_HEADERS,
    descripcion=("Cabeceras de navegación de navegador real (Accept de documento + "
                 "Sec-Fetch-Dest/Mode/Site/User + Upgrade-Insecure-Requests + Referer). "
                 "Perfil operativo del pack: es el que se usa para adquirir."),
    es_perfil_operativo=True,
)

PERFILES: Tuple[RequestProfile, ...] = (PROFILE_BASIC, PROFILE_NAVIGATION)


def perfil_por_id(profile_id: str) -> RequestProfile:
    for p in PERFILES:
        if p.profile_id == profile_id:
            return p
    raise KeyError(f"perfil de petición desconocido: {profile_id!r}")


# ══════════════════════════════════════════════════════════════════════════════
# 1 · TRANSPORTE DIRECTO
# ══════════════════════════════════════════════════════════════════════════════
def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class RawFetch:
    """Respuesta cruda. ÚNICO portador de la procedencia. No lanza: todo fallo se declara.

    ⚠️ DEFINICIÓN ÚNICA DEL TIPO EN EL PACK. Esta es la única ``class RawFetch`` del
    repositorio: ``api/market_harvest.py`` ya NO declara la suya, la importa de aquí. Antes
    había DOS clases homónimas (una en ``market_harvest`` y otra derivada aquí) y, además,
    el mismo archivo era importable como ``market_harvest`` y como ``api.market_harvest``:
    el mismo objeto fallaba ``isinstance`` según por qué camino hubiera entrado, que es el
    defecto que impedía cerrar la remedición de mercado
    (``TypeError: fetch_fn debe devolver un RawFetch, no RawFetch``). Con una sola
    definición, ``type(x) is type(y)`` para cualquier instancia, venga de donde venga.

    Los campos son la UNIÓN de lo que necesitaban los dos consumidores: la procedencia
    cruda (url/código/bytes/hash/cf-ray/server) y la declaración del perfil de petición y
    del transporte (``profile_id``/``transport``/``relay``/``requested_url``). Lo que no se
    declara, no existe como evidencia.
    """

    url: str
    http_status: Optional[int]
    body: bytes
    queried_at: str
    sha256: Optional[str] = None
    bytes: int = 0
    cf_ray: Optional[str] = None
    server: Optional[str] = None
    error: Optional[str] = None
    intentos: int = 1
    ms: Optional[int] = None
    profile_id: str = REQUEST_PROFILE_ID
    transport: str = TRANSPORT_DIRECTO
    relay: Optional[str] = None
    requested_url: Optional[str] = None

    def __post_init__(self) -> None:
        if self.body is None:
            self.body = b""
        if not isinstance(self.body, (bytes, bytearray)):
            raise TypeError("RawFetch.body debe ser bytes (payload crudo sin modificar)")
        self.body = bytes(self.body)
        if self.sha256 is None and self.http_status is not None:
            # El hash se calcula sobre los BYTES EXACTOS recibidos. No se recalcula ni se
            # normaliza el cuerpo antes de hashear.
            self.sha256 = hashlib.sha256(self.body).hexdigest()
        self.bytes = len(self.body)

    @property
    def es_http_200(self) -> bool:
        return self.http_status == 200

    def json(self) -> Optional[Dict[str, Any]]:
        try:
            dato = json.loads(self.body.decode("utf-8"))
        except Exception:  # noqa: BLE001
            return None
        return dato if isinstance(dato, dict) else None

    def provenance(self, *, source_id: str, servicio: str,
                   layer_id: Optional[int] = None,
                   referencia: Optional[str] = None,
                   proveedor: Optional[str] = None) -> Dict[str, Any]:
        """Bloque de procedencia COMPLETA, compatible con el contrato del pack.

        Misma forma que la del cliente demostrado MÁS la declaración del perfil de petición
        y del transporte: lo que no se declara, no existe como evidencia. El proveedor sale
        del cliente demostrado (una sola fuente de verdad), no se re-declara aquí.
        """
        return {
            "version": "harvest-provenance/1.0.0",
            "version_cliente": VERSION_CLIENTE,
            "perfil_peticion": self.profile_id,
            "transporte": self.transport,
            "relay": self.relay,
            "source_id": source_id,
            "proveedor": proveedor or getattr(_MH, "PROVEEDOR_PORTAL", None) or (
                "Alcaldía Distrital de Barranquilla — geoportal miciudad "
                "(servidor ArcGIS REST)"),
            "fecha": (self.queried_at or "")[:10] or None,
            "referencia": referencia or (
                f"{servicio}" + (f"/MapServer/{layer_id}" if layer_id is not None
                                 else "/MapServer")),
            "url": self.url,
            "requested_url": self.requested_url or self.url,
            "queried_at": self.queried_at,
            "http_status": self.http_status,
            "bytes": self.bytes,
            "sha256": self.sha256,
            "cf_ray": self.cf_ray,
            "server": self.server,
        }

    def como_dict(self, *, con_cuerpo: bool = False) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "url": self.url,
            "requested_url": self.requested_url or self.url,
            "http_status": self.http_status,
            "bytes": self.bytes,
            "sha256": self.sha256,
            "queried_at": self.queried_at,
            "profile_id": self.profile_id,
            "transport": self.transport,
            "relay": self.relay,
            "cf_ray": self.cf_ray,
            "server": self.server,
            "error": self.error,
            "intentos": self.intentos,
            "ms": self.ms,
        }
        if con_cuerpo:
            d["body"] = self.body.decode("utf-8", "replace")
        return d


def fetch_raw(url: str, *, profile: RequestProfile = PROFILE_NAVIGATION,
              timeout: int = 30, intentos: int = 3,
              headers: Optional[Mapping[str, str]] = None,
              opener: Optional[Callable[..., Any]] = None,
              sleep: Callable[[float], None] = time.sleep,
              transport: str = TRANSPORT_DIRECTO,
              relay: Optional[str] = None,
              requested_url: Optional[str] = None) -> RawFetch:
    """GET crudo con procedencia completa y perfil declarado.

    Un ``HTTPError`` con cuerpo (el 403 de Cloudflare) se CONSERVA con su cuerpo real, para
    que el hash del bloqueo sea auditable: se documenta lo que la fuente respondió.
    """
    cabeceras = dict(profile.headers)
    cabeceras.update(dict(headers or {}))
    abrir = opener or urllib.request.urlopen
    ultimo: Optional[RawFetch] = None
    for i in range(max(1, intentos)):
        queried_at = _utcnow()
        t0 = time.time()
        try:
            req = urllib.request.Request(url, headers=cabeceras)
            with abrir(req, timeout=timeout) as resp:
                return RawFetch(
                    url=url, http_status=getattr(resp, "status", None), body=resp.read(),
                    queried_at=queried_at,
                    cf_ray=(resp.headers.get("cf-ray") if resp.headers else None),
                    server=(resp.headers.get("server") if resp.headers else None),
                    intentos=i + 1, ms=int((time.time() - t0) * 1000),
                    profile_id=profile.profile_id, transport=transport, relay=relay,
                    requested_url=requested_url)
        except urllib.error.HTTPError as exc:
            cuerpo = b""
            try:
                cuerpo = exc.read()
            except Exception:  # noqa: BLE001
                cuerpo = b""
            ultimo = RawFetch(
                url=url, http_status=exc.code, body=cuerpo, queried_at=queried_at,
                cf_ray=(exc.headers or {}).get("cf-ray"),
                server=(exc.headers or {}).get("server"),
                error=f"HTTPError {exc.code} {exc.reason}", intentos=i + 1,
                ms=int((time.time() - t0) * 1000), profile_id=profile.profile_id,
                transport=transport, relay=relay, requested_url=requested_url)
        except Exception as exc:  # noqa: BLE001
            ultimo = RawFetch(
                url=url, http_status=None, body=b"", queried_at=queried_at,
                error=f"{type(exc).__name__}: {exc}", intentos=i + 1,
                ms=int((time.time() - t0) * 1000), profile_id=profile.profile_id,
                transport=transport, relay=relay, requested_url=requested_url)
        if i + 1 < max(1, intentos):
            sleep(1.5 * (i + 1))
    assert ultimo is not None
    return ultimo


# ══════════════════════════════════════════════════════════════════════════════
# 2 · SONDA DOBLE (A/B)
# ══════════════════════════════════════════════════════════════════════════════
@dataclass
class DualProbe:
    """Hecho medido de una URL bajo DOS perfiles. No interpreta: reporta."""

    url: str
    basic: RawFetch
    navigation: RawFetch
    perfil_basico: str = PROFILE_BASIC_ID
    perfil_navegacion: str = REQUEST_PROFILE_ID

    @property
    def flips_a_exito(self) -> bool:
        """El perfil de navegación ALCANZA donde el básico fue rechazado."""
        return (self.basic.http_status != 200 and self.navigation.http_status == 200)

    @property
    def restringido_en_runtime(self) -> bool:
        """HTTP 401/403 bajo CUALQUIER perfil: restricción de acceso en runtime."""
        return any(getattr(x, "http_status", None) in (401, 403)
                   for x in (self.basic, self.navigation))

    @property
    def alcanzable(self) -> bool:
        return self.navigation.http_status == 200

    def como_dict(self, *, con_cuerpo: bool = False) -> Dict[str, Any]:
        return {
            "url": self.url,
            "perfil_basico": self.perfil_basico,
            "perfil_navegacion": self.perfil_navegacion,
            "basic_http_status": self.basic.http_status,
            "navigation_http_status": self.navigation.http_status,
            "basic_bytes": self.basic.bytes,
            "navigation_bytes": self.navigation.bytes,
            "basic_sha256": self.basic.sha256,
            "navigation_sha256": self.navigation.sha256,
            "navigation_cf_ray": self.navigation.cf_ray,
            "navigation_server": self.navigation.server,
            "queried_at": self.navigation.queried_at,
            "flip_403_200": bool(self.basic.http_status == 403
                                 and self.navigation.http_status == 200),
            "alcanzable_con_perfil_navegacion": self.alcanzable,
            "restringido_en_runtime": self.restringido_en_runtime,
            "basic": self.basic.como_dict(con_cuerpo=con_cuerpo),
            "navigation": self.navigation.como_dict(con_cuerpo=con_cuerpo),
        }


def probe_dual(url: str, *, timeout: int = 30, intentos: int = 2,
               sleep: Callable[[float], None] = time.sleep,
               opener: Optional[Callable[..., Any]] = None) -> DualProbe:
    """Misma URL, DOS perfiles, AMBOS códigos registrados."""
    basic = fetch_raw(url, profile=PROFILE_BASIC, timeout=timeout, intentos=intentos,
                      sleep=sleep, opener=opener)
    nav = fetch_raw(url, profile=PROFILE_NAVIGATION, timeout=timeout, intentos=intentos,
                    sleep=sleep, opener=opener)
    return DualProbe(url=url, basic=basic, navigation=nav)


def codigo_efectivo(probe: DualProbe) -> Optional[int]:
    """El código que MANDA para la adquisición: el del perfil operativo (navegación)."""
    return probe.navigation.http_status


# ══════════════════════════════════════════════════════════════════════════════
# 3 · RELEVOS HTTP AUTOMÁTICOS (ruta automática, sin intervención humana)
# ══════════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class RelaySpec:
    """Un relevo automático. ``envuelve`` construye la URL del relevo."""

    relay_id: str
    descripcion: str
    envuelve: Callable[[str], str]
    #: ``True`` si el relevo devuelve el JSON del target ya parseado en un sobre.
    sobre_json: str = ""


RELEVOS: Tuple[RelaySpec, ...] = (
    RelaySpec("allorigins_raw", "api.allorigins.win/raw (cuerpo crudo byte a byte)",
              lambda u: "https://api.allorigins.win/raw?url=" + urllib.parse.quote(u, safe="")),
    RelaySpec("microlink", "api.microlink.io (sobre JSON con data.text)",
              lambda u: "https://api.microlink.io/?url=" + urllib.parse.quote(u, safe=""),
              sobre_json="microlink"),
    RelaySpec("codetabs", "api.codetabs.com/v1/proxy (cuerpo crudo)",
              lambda u: "https://api.codetabs.com/v1/proxy/?quest="
                        + urllib.parse.quote(u, safe="")),
    RelaySpec("jina_r", "r.jina.ai (texto renderizado)",
              lambda u: "https://r.jina.ai/" + u),
)


def url_de_relevo(relay_id: str, url: str) -> str:
    for r in RELEVOS:
        if r.relay_id == relay_id:
            return r.envuelve(url)
    raise KeyError(f"relevo desconocido: {relay_id!r}")


def _desenvolver(relay_id: str, raw: RawFetch) -> bytes:
    """Quita el sobre del relevo. Si el sobre no se entiende, se devuelve lo crudo."""
    if relay_id != "microlink":
        return raw.body
    try:
        sobre = json.loads(raw.body.decode("utf-8"))
    except Exception:  # noqa: BLE001
        return raw.body
    if not isinstance(sobre, dict):
        return raw.body
    dato = (sobre.get("data") or {})
    if not isinstance(dato, dict):
        return raw.body
    contenido = dato.get("text", dato.get("json"))
    if isinstance(contenido, dict):
        return json.dumps(contenido, ensure_ascii=False).encode("utf-8")
    if isinstance(contenido, str):
        return contenido.encode("utf-8")
    return raw.body


def fetch_via_relay(url: str, relay_id: str, *, timeout: int = 60, intentos: int = 2,
                    sleep: Callable[[float], None] = time.sleep,
                    opener: Optional[Callable[..., Any]] = None,
                    desenvolver: bool = True) -> RawFetch:
    """GET a ``url`` A TRAVÉS de un relevo automático, con procedencia del transporte."""
    envuelta = url_de_relevo(relay_id, url)
    raw = fetch_raw(envuelta, profile=PROFILE_NAVIGATION, timeout=timeout,
                    intentos=intentos, sleep=sleep, opener=opener,
                    transport=TRANSPORT_RELEVO, relay=relay_id, requested_url=url)
    if desenvolver and raw.http_status == 200 and raw.body:
        cuerpo = _desenvolver(relay_id, raw)
        if cuerpo is not raw.body:
            raw = RawFetch(url=envuelta, http_status=raw.http_status, body=cuerpo,
                           queried_at=raw.queried_at, cf_ray=raw.cf_ray,
                           server=raw.server, error=raw.error, intentos=raw.intentos,
                           ms=raw.ms, profile_id=raw.profile_id,
                           transport=TRANSPORT_RELEVO, relay=relay_id,
                           requested_url=url)
    return raw


def fetch_json_arcgis(url: str, *, timeout: int = 60, intentos: int = 1,
                      sleep: Callable[[float], None] = time.sleep,
                      opener: Optional[Callable[..., Any]] = None) -> Tuple[RawFetch, bool]:
    """Devuelve ``(RawFetch, es_json_arcgis)``.

    ``es_json_arcgis`` exige HTTP 200 **y** un cuerpo que sea el JSON de ArcGIS REST. Un
    200 con la página de bloqueo de Cloudflare NO es una respuesta válida: es un cuerpo
    malformado, y se declara como tal en vez de fingir éxito.
    """
    raw = fetch_raw(url, profile=PROFILE_NAVIGATION, timeout=timeout, intentos=intentos,
                    sleep=sleep, opener=opener)
    if raw.http_status != 200:
        return raw, False
    dato = raw.json()
    if not isinstance(dato, dict):
        return raw, False
    if "error" in dato and not any(k in dato for k in ("currentVersion", "layers",
                                                       "tables", "fields", "features",
                                                       "spatialReference", "geometryType")):
        return raw, False
    return raw, True


# ══════════════════════════════════════════════════════════════════════════════
# 4 · CLASIFICACIÓN DEL ACCESO (hecho medido -> estado de acceso)
# ══════════════════════════════════════════════════════════════════════════════
ESTADOS_DE_ACCESO: Tuple[str, ...] = (
    "ACCESS_OK",                  # HTTP 200 con cuerpo ArcGIS legible
    "ACCESS_OK_VIA_PROFILE",      # 403/401 básico, 200 navegación: ruta válida
    "ACCESS_OK_VIA_RELAY",        # alcanzable sólo a través de un relevo automático
    "RUNTIME_ACCESS_RESTRICTED",  # 401/403 en TODOS los perfiles y relevos medidos
    "ENDPOINT_NOT_FOUND",         # 404: el servicio/capa no existe
    "QUERY_FAILED",               # respuesta ilegible / ArcGIS error / transporte caído
)


def clasificar_acceso(*, probe: Optional[DualProbe] = None,
                      relay_fetch: Optional[RawFetch] = None,
                      json_valido: Optional[bool] = None,
                      error_arcgis: Optional[bool] = None) -> str:
    """Traduce hechos medidos a un estado de acceso CERRADO. No inventa: exige medida."""
    if error_arcgis:
        return "QUERY_FAILED"
    if probe is not None:
        if probe.navigation.http_status == 200:
            if json_valido is False:
                return "QUERY_FAILED"
            return ("ACCESS_OK_VIA_PROFILE" if probe.basic.http_status not in (200,)
                    else "ACCESS_OK")
        if probe.navigation.http_status in (401, 403) or probe.basic.http_status in (401, 403):
            # Sólo es RESTRICCIÓN si NINGÚN relevo automático alcanzó la fuente.
            if relay_fetch is not None and relay_fetch.http_status == 200:
                return "ACCESS_OK_VIA_RELAY"
            return "RUNTIME_ACCESS_RESTRICTED"
        if probe.navigation.http_status == 404:
            return "ENDPOINT_NOT_FOUND"
    if relay_fetch is not None and relay_fetch.http_status == 200:
        return "ACCESS_OK_VIA_RELAY"
    return "QUERY_FAILED"

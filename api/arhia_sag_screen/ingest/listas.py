"""Listas sancionatorias en vivo: descarga -> parseo -> hash -> caché versionada.

Permite que el screening use datos reales (ONU/OFAC) con una lista versionada por SHA-256.
Flujo:
    1) Si hay caché válida para la fuente, se reutiliza (sin red).
    2) Si no (o `force_refresh`), descarga la fuente oficial, parsea (namespace-agnóstico),
       calcula hash y guarda en caché.
    3) Ante error de red, si hay caché la reutiliza; si no, lanza `ListaNoDisponible`.
El llamador puede degradar a listas inyectadas si la fuente no está disponible.
"""
import json
import os
from dataclasses import asdict, dataclass
from typing import Optional, Tuple

from .registry import LIST_CATALOG
from .downloader import fetch_http
from .onu import parse_onu_xml
from .ofac import parse_ofac_sdn
from .uk import parse_uk_ofsi_xml
from .ue import parse_ue_xml
from .sources import FUENTES
from ..contracts import ListaVersion, RegistroNormalizado
from ..evidence.versioning import sha256_hex

_PARSERS = {"onu": parse_onu_xml, "ofac": parse_ofac_sdn, "uk": parse_uk_ofsi_xml, "ue": parse_ue_xml}


class ListaNoDisponible(Exception):
    pass


def _default_cache_dir():
    base = os.environ.get("ARHIA_LISTAS_CACHE")
    if base:
        return base
    here = os.path.dirname(__file__)
    root = os.path.abspath(os.path.join(here, "..", ".."))
    return os.path.join(root, "cache_listas")


def descargar_fuente(fuente: str, url: Optional[str] = None, timeout: int = 60):
    """Descarga y parsea una fuente; devuelve (ListaVersion, registros). No cachea."""
    if fuente not in _PARSERS:
        raise ListaNoDisponible(f"fuente sin parser: {fuente}")
    cat = FUENTES.get(fuente) or {"nombre": fuente, "url": "", "formato": ""}
    raw = fetch_http(url or cat.get("url"), timeout=timeout)
    registros = tuple(_PARSERS[fuente](raw))
    h = sha256_hex(raw)
    lista = ListaVersion(fuente=fuente, nombre=cat.get("nombre", fuente), url=url or cat.get("url", ""),
                         formato=cat.get("formato", ""), fecha_emision="", version=h[:16], hash=h,
                         licencia="public", registros=len(registros), estado="OPERATIVA",
                         autoridad=cat.get("autoridad", ""), metodo=cat.get("metodo", "oficial_fetch"),
                         vigencia=cat.get("vigencia", ""))
    return lista, registros


def _servir(registros):
    return tuple(
        RegistroNormalizado(id=r.get("id", ""), nombre=r.get("nombre", ""),
                            alias=tuple(r.get("alias", ())), tipo_documento=r.get("tipo_documento"),
                            numero_documento=r.get("numero_documento"),
                            fecha_nacimiento=r.get("fecha_nacimiento"),
                            programas=tuple(r.get("programas", ())),
                            fuente=r.get("fuente", ""), lista_version=r.get("lista_version", ""))
        for r in registros)


def _leer_cache(cache_dir, fuente):
    meta_path = os.path.join(cache_dir, fuente + "_meta.json")
    data_path = os.path.join(cache_dir, fuente + "_registros.json")
    if not (os.path.exists(meta_path) and os.path.exists(data_path)):
        return None
    with open(meta_path, encoding="utf-8") as f:
        m = json.load(f)
    lista = ListaVersion(fuente=m["fuente"], nombre=m["nombre"], url=m["url"], formato=m["formato"],
                         fecha_emision=m.get("fecha_emision") or m.get("fechaEmision", ""),
                         version=m["version"], hash=m["hash"],
                         licencia=m.get("licencia", "public"), registros=m.get("registros", 0),
                         estado=m.get("estado", "OPERATIVA"), autoridad=m.get("autoridad", ""),
                         metodo=m.get("metodo", ""), vigencia=m.get("vigencia", ""))
    with open(data_path, encoding="utf-8") as f:
        regs = _servir(json.load(f))
    return lista, regs


def _escribir_cache(cache_dir, fuente, lista, registros):
    os.makedirs(cache_dir, exist_ok=True)
    with open(os.path.join(cache_dir, fuente + "_meta.json"), "w", encoding="utf-8") as f:
        json.dump(asdict(lista), f, ensure_ascii=False)
    with open(os.path.join(cache_dir, fuente + "_registros.json"), "w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in registros], f, ensure_ascii=False)


def obtener_lista(fuente: str, *, cache_dir: Optional[str] = None,
                  force_refresh: bool = False, timeout: int = 180):
    """Devuelve (ListaVersion, registros) usando caché si está disponible."""
    cache = cache_dir or _default_cache_dir()
    if not force_refresh:
        cached = _leer_cache(cache, fuente)
        if cached is not None:
            return cached
    try:
        lista, regs = descargar_fuente(fuente, timeout=timeout)
    except Exception:
        cached = _leer_cache(cache, fuente)
        if cached is not None:
            return cached
        raise ListaNoDisponible(f"No se pudo descargar ni hay caché para {fuente}")
    _escribir_cache(cache, fuente, lista, regs)
    return lista, regs


def preparar_screening(fuente: str = "onu", *, cache_dir: Optional[str] = None,
                       force_refresh: bool = False) -> Tuple[tuple, ListaVersion]:
    """Para el screening de la plataforma: devuelve (registros_lista, ListaVersion)."""
    lista, regs = obtener_lista(fuente, cache_dir=cache_dir, force_refresh=force_refresh)
    return regs, lista


def _versionar_muestra(fuente: str, regs):
    raw = json.dumps([asdict(r) for r in regs], sort_keys=True, ensure_ascii=False).encode("utf-8")
    h = sha256_hex(raw)
    cat = FUENTES[fuente] if fuente in FUENTES else {"nombre": fuente, "url": "", "formato": ""}
    lista = ListaVersion(fuente=fuente, nombre=cat.get("nombre", fuente), url=cat.get("url", ""),
                         formato=cat.get("formato", ""), fecha_emision="", version=h[:16], hash=h,
                         licencia="public", registros=len(regs), estado="SYNTHETIC_TEST_FIXTURE",
                         autoridad=cat.get("autoridad", ""), metodo=cat.get("metodo", "fixture_sintetica"),
                         vigencia=cat.get("vigencia", ""))
    return lista


def ingestar_fichero(fuente: str, ruta: str, *, cache_dir: Optional[str] = None):
    """Ingesta un archivo local de una lista (p. ej. el XML de la UE) y lo versiona/cachea.

    Útil cuando la fuente no es consumible en vivo (p. ej. EU webgate tras anti-bot 403).
    Devuelve (ListaVersion, registros).
    """
    if fuente not in _PARSERS:
        raise ListaNoDisponible(f"fuente sin parser: {fuente}")
    with open(ruta, "rb") as f:
        raw = f.read()
    registros = tuple(_PARSERS[fuente](raw))
    if not registros:
        raise ListaNoDisponible(f"el archivo {fuente} no arrojó registros (estructura no reconocida)")
    h = sha256_hex(raw)
    cat = FUENTES.get(fuente) or {"nombre": fuente}
    lista = ListaVersion(fuente=fuente, nombre=cat.get("nombre", fuente), url="local",
                         formato="xml", fecha_emision="", version=h[:16], hash=h,
                         licencia="public", registros=len(registros))
    _escribir_cache(cache_dir or _default_cache_dir(), fuente, lista, registros)
    return lista, registros


def obtener_listas(fuentes=None, *, cache_dir: Optional[str] = None,
                   force_refresh: bool = False, timeout: int = 180):
    """Devuelve {fuente: (ListaVersion, registros)} para cada fuente configurada.

    - 'live': se intenta descargar (con caché); si falla, la fuente NO se incluye.
    - 'fichero': usa el cache (archivo ya ingerido); si no hay, NO se incluye.
    - 'fuera_de_alcance': no es fuente de screening y se omite.

    03S.1: se eliminó el fallback a "muestra sintética". Un registro de prueba
    NO es evidencia de screening: si la fuente no se puede adquirir, la fuente
    simplemente no aparece (el consumidor la reporta como no disponible). Los
    datos sintéticos viven en `tests/fixtures/` (§12).
    """
    keys = fuentes or list(FUENTES)
    out = {}
    cache = cache_dir or _default_cache_dir()
    for f in keys:
        cat = FUENTES.get(f)
        if cat is None:
            continue
        politica = cat.get("politica")
        if politica == "fuera_de_alcance":
            continue
        if politica == "fichero":
            cached = _leer_cache(cache, f)
            if cached is not None:
                out[f] = cached
            continue
        if politica == "live":
            try:
                lista, regs = obtener_lista(f, cache_dir=cache_dir,
                                            force_refresh=force_refresh,
                                            timeout=timeout)
                out[f] = (lista, list(regs))
            except ListaNoDisponible:
                continue
    return out

# -*- coding: utf-8 -*-
"""ARHIAX RE — SOURCE PACK v1.0-R1 · requisito G: bloque canónico de LICENCIA por fuente.

Una sola pieza declara, por `source_id`, QUÉ licencia aplica, QUÉ se consultó de
verdad (URL + fecha + `sha256` del contenido descargado), qué se puede hacer con el
dato (persistir / modificar / incrustar / share-alike) y con qué estado de
verificación — sin silenciar nada:

    provider_terms_status ∈ {VERIFIED, DECLARED, UNVERIFIED, RESTRICTED, NOT_APPLICABLE}

Reglas duras
────────────
1. **Ningún permiso se asume.** Un término sin evidencia NO es `VERIFIED`. Si el
   contenido no pudo descargarse, `terms_hash=None` **con motivo**; nunca se finge
   un hash.
2. **Fail-closed de imágenes de tercero**: Google Street View se cierra
   (`can_persist=False`, `can_embed=False`) salvo que la evidencia de términos lo
   habilite EXPLÍCITAMENTE. La evidencia obtenida en esta ronda lo PROHÍBE
   (`RESTRICTED`): la matriz queda cerrada de forma permanente mientras el hash
   consultado sea el vigente.
3. **`can_embed=False` ⇒ ningún flujo incrusta.** `autorizar_incrustacion()` es la
   única vía y devuelve `permitido=False` con motivo para toda fuente sin permiso
   de incrustación declarado.
4. Lo que falta para pasar a `VERIFIED` se declara por fuente en
   `gap_para_verified` y se resume en `resumen()` / `docs/source_pack/
   LICENSES_EVIDENCE.md`. Un estado `DECLARED` NO congela el pack: se declara el
   hueco, no se convierte en una prohibición silenciosa.

Este módulo NO toca `api/street_imagery.py` (su vocabulario se reutiliza, no se
duplica), ni valoración, fórmulas, compuerta ni hash maestro.
"""
from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

_DIR_API = Path(__file__).resolve().parent
_DIR_RAIZ = _DIR_API.parent


def _cargar_modulo(nombre: str, *rutas: Path):
    """Importa un módulo hermano de `api/` de forma determinista (sin depender del cwd)."""
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


try:                                        # vocabulario y política ya existentes
    si = _cargar_modulo("street_imagery", _DIR_API / "street_imagery.py")
except Exception:                           # noqa: BLE001 — el bloque no depende de él
    si = None

DIR_PACK = _DIR_RAIZ / "docs" / "source_pack"
RUTA_REGISTRO = DIR_PACK / "barranquilla_sources_v1.json"
RUTA_MANIFEST = DIR_PACK / "BARRANQUILLA_SOURCE_PACK_MANIFEST.json"
RUTA_METODOLOGIA_LONJA = (_DIR_RAIZ / "motor_tma_lonja_baq_v1.0" / "motor_tma_lonja_baq_v1.0"
                          / "lonja_layer" / "lonja_baq_metodologia.yaml")

# ── vocabulario CERRADO (mismo que api/street_imagery.py) ─────────────────────
VERIFIED = "VERIFIED"                  # términos consultados y hasheados, con permiso explícito
DECLARED = "DECLARED"                  # licencia declarada, sin verificación completa
UNVERIFIED = "UNVERIFIED"              # no verificable → fail-closed
RESTRICTED = "RESTRICTED"              # términos consultados que PROHÍBEN persistir
NOT_APPLICABLE = "NOT_APPLICABLE"      # sin licencia de tercero (cálculo propio)
ESTADOS_PROVIDER_TERMS: Tuple[str, ...] = (VERIFIED, DECLARED, UNVERIFIED, RESTRICTED,
                                           NOT_APPLICABLE)

# ── campos del bloque canónico (G) ────────────────────────────────────────────
CAMPOS_BLOQUE: Tuple[str, ...] = (
    "source_id", "license_name", "license_version", "terms_url", "consulted_at",
    "terms_hash", "attribution_text", "can_persist", "can_modify", "can_embed",
    "share_alike", "provider_terms_status",
)
# Campos adicionales declarados por este bloque (auditoría; no sustituyen a los de arriba).
CAMPOS_ADICIONALES: Tuple[str, ...] = (
    "terms_hash_reason", "consulted_http_status", "consulted_bytes", "evidence_ids",
    "gap_para_verified", "notes", "institution", "declared_in",
)

FUENTE_MAPILLARY = "MAPILLARY"
FUENTE_GOOGLE = "GOOGLE_STREET_VIEW"
FUENTE_OSM = "OSM_OVERPASS"
FUENTE_LONJA = "LONJA_MARKET_BAQ"
FUENTE_SOLAR = "SOLAR_ENGINE"
FUENTE_SOMBRA = "SHADOW_FACADE_EXPOSURE"

FECHA_CONSULTA = "2026-09-29"          # fecha REAL de la consulta de términos (UTC)
ATRIBUCION_OSM = "© OpenStreetMap contributors (ODbL 1.0)"
ATRIBUCION_MAPILLARY = "© Mapillary contributors (CC BY-SA 4.0)"
ATRIBUCION_GOOGLE = "© Google"
ATRIBUCION_ALCALDIA = ("Fuente: Alcaldía Distrital de Barranquilla — datos abiertos "
                       "(geoportal miciudad), con atribución a la fuente oficial")
ATRIBUCION_LONJA = ("Artefacto local de metodología de mercado del producto "
                    "(sin institución proveedora verificada; la Lonja no es una fuente de "
                    "datos y no suministra el valor por m²)")

# ── evidencia de términos consultada REALMENTE en esta ronda ──────────────────
# Cada registro es una INSTANTÁNEA: `sha256` identifica los bytes descargados en
# `consulted_at`, no un artefacto inmutable del proveedor (las páginas son dinámicas).
EVIDENCIA: Dict[str, Dict[str, Any]] = {
    "MAPILLARY_TERMS": {
        "url": "https://www.mapillary.com/terms",
        "consulted_at": FECHA_CONSULTA,
        "http_status": 200,
        "bytes": 118250,
        "sha256": "61f11ac253d4f7c84c62b94799b89f285114af7e247f748f79a92919fa54e6b9",
        "tipo_contenido": "text/html; charset=utf-8",
        "descargado": True,
        "pagina_dinamica": True,
        "marcadores": {"cc_by_sa": True, "cc_by_sa_4_0": False, "creative_commons": True,
                       "odbl": False, "prohibicion_explicita": False},
        "cita": ("«Tu uso de cualquier Contenido del usuario proporcionado por otros usuarios "
                 "está sujeto a la licencia Creative Commons Compartir Igual (CC BY-SA), "
                 "salvo que indiquemos lo contrario.»"),
        "resultado": DECLARED,
        "motivo": ("El contenido consultado SÍ expone una licencia CC BY-SA para el Contenido "
                   "del usuario de otros usuarios, pero NO declara la versión y admite "
                   "excepciones por conjunto de datos («salvo que indiquemos lo contrario»), "
                   "además de reservarse el resto de derechos. Sin versión explícita en los "
                   "términos consultados, el estado se queda en DECLARED."),
    },
    "MAPILLARY_CC_BY_SA_4_0": {
        "url": ("https://help.mapillary.com/hc/en-us/articles/"
                "115001770409-CC-BY-SA-license-for-open-data"),
        "consulted_at": FECHA_CONSULTA,
        "http_status": 403,
        "bytes": None,
        "sha256": None,
        "descargado": False,
        "pagina_dinamica": True,
        "resultado": UNVERIFIED,
        "motivo": ("HTTP 403 Forbidden: la página que fija la VERSIÓN de la licencia "
                   "(CC BY-SA 4.0) no pudo descargarse, así que no hay hash ni cita que "
                   "pueda subir el estado a VERIFIED."),
    },
    "GOOGLE_MAPS_PLATFORM_TERMS": {
        "url": "https://cloud.google.com/maps-platform/terms",
        "consulted_at": FECHA_CONSULTA,
        "http_status": 200,
        "bytes": 2412706,
        "sha256": "40ab3eab2c4469d397397cc20f1018c00fc5f514143e3bc3736348fc05b287b0",
        "tipo_contenido": "text/html; charset=utf-8",
        "descargado": True,
        "pagina_dinamica": True,
        "marcadores": {"cc_by_sa": False, "no_scraping": True, "no_caching": True,
                       "no_crear_contenido_derivado": True},
        "cita": ("«No Scraping. Customer will not export, extract, or otherwise scrape Google "
                 "Maps Content for use outside the Services … (i) pre-fetch, index, store, "
                 "reshare, or rehost Google Maps Content outside the services; (ii) bulk "
                 "download Google Maps tiles, Street View images …» · «No Caching. Customer "
                 "will not cache Google Maps Content except as expressly permitted under the "
                 "Maps Service Specific Terms.» · «No Creating Content From Google Maps "
                 "Content.»"),
        "resultado": RESTRICTED,
        "motivo": ("Los términos consultados PROHÍBEN explícitamente pre-descargar, indexar, "
                   "almacenar, recachear, recompartir o rehospedar el contenido de Google Maps "
                   "(incluidas las imágenes de Street View) y crear contenido derivado: la "
                   "matriz queda CERRADA de forma permanente mientras este hash sea el vigente."),
    },
    "GOOGLE_STREETVIEW_POLICIES": {
        "url": "https://developers.google.com/maps/documentation/streetview/policies",
        "consulted_at": FECHA_CONSULTA,
        "http_status": 200,
        "bytes": 195577,
        "sha256": "b05384c507e67f8b5a3f69275c0a1fdbfeb64c1a8c36e753af8c52c58da9e389",
        "tipo_contenido": "text/html; charset=utf-8",
        "descargado": True,
        "pagina_dinamica": True,
        "marcadores": {"prohibicion_explicita": True, "cc_del_sitio_documentacion": True},
        "cita": ("«Content pre-fetching, indexing, storing, or caching is generally prohibited, "
                 "except for place IDs and panorama IDs.»"),
        "resultado": RESTRICTED,
        "motivo": ("Políticas de Street View: prohibido pre-descargar, indexar, almacenar o "
                   "cachear el contenido (salvo place IDs y panorama IDs) → fail-closed. "
                   "La licencia CC BY 4.0 que aparece en la página se refiere al CONTENIDO DE "
                   "LA DOCUMENTACIÓN, no a las imágenes de Street View."),
    },
    "OSM_COPYRIGHT": {
        "url": "https://www.openstreetmap.org/copyright",
        "consulted_at": FECHA_CONSULTA,
        "http_status": 200,
        "bytes": 21314,
        "sha256": "fd65145af733b0d170e0e33c340e59061cdba1f60803efb832477081516dca4c",
        "tipo_contenido": "text/html; charset=utf-8",
        "descargado": True,
        "pagina_dinamica": True,
        "marcadores": {"odbl": True, "cc_by_sa": True, "atribucion": True},
        "cita": ("«OpenStreetMap is open data, licensed under the Open Data Commons Open "
                 "Database License (ODbL) by the OpenStreetMap Foundation (OSMF). … You are "
                 "free to copy, distribute, transmit and adapt our data, as long as you credit "
                 "OpenStreetMap and its contributors. If you alter or build upon our data, you "
                 "may distribute the result only under the same licence.»"),
        "resultado": VERIFIED,
        "motivo": ("La licencia está publicada junto al dato, se descargó y se hasheó en esta "
                   "corrida, y autoriza de forma explícita copiar/adaptar con atribución y "
                   "share-alike: único término de este pack que alcanza VERIFIED."),
    },
    "ALCALDIA_APERTURA_DATOS": {
        "url": "https://www.barranquilla.gov.co/documento/plan-de-apertura-de-datos/",
        "consulted_at": FECHA_CONSULTA,
        "http_status": 403,
        "bytes": None,
        "sha256": None,
        "descargado": False,
        "pagina_dinamica": True,
        "resultado": UNVERIFIED,
        "motivo": ("HTTP 403 Forbidden (Cloudflare) al consultar la página de apertura de datos "
                   "del Distrito: no hay contenido descargable ni hash. Coincide con lo ya "
                   "documentado para el geoportal en docs/source_pack/raw/golden/"
                   "_retrieval_paths_probe*.json."),
    },
    "LONJA_METODOLOGIA_LOCAL": {
        "url": None,
        "ruta_local": str(RUTA_METODOLOGIA_LONJA.relative_to(_DIR_RAIZ)),
        "consulted_at": FECHA_CONSULTA,
        "http_status": None,
        "bytes": None,
        "sha256": None,       # se rellena en tiempo de ejecución (artefacto real)
        "descargado": True,
        "resultado": DECLARED,
        "motivo": ("La licencia es CONTRACTUAL y el documento vive en el repositorio: su "
                   "contenido se puede hashear localmente, pero un contrato no se verifica "
                   "contra una URL pública. DECISIÓN DE PRODUCTO: la Lonja NO es una fuente "
                   "de datos (no aporta el valor por m², ni dataset, ni contrato); este "
                   "artefacto local se conserva sólo como metodología propia del producto."),
    },
}


def _sha256_artefacto(ruta: Path) -> Optional[str]:
    try:
        return hashlib.sha256(Path(ruta).read_bytes()).hexdigest()
    except Exception:  # noqa: BLE001
        return None


def hash_canonico(payload: Any) -> str:
    """sha256 canónico (mismo criterio que `dictus_sources.hash_canonico`)."""
    if isinstance(payload, (bytes, bytearray)):
        return hashlib.sha256(bytes(payload)).hexdigest()
    crudo = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                       default=str)
    return hashlib.sha256(crudo.encode("utf-8")).hexdigest()


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


# ══════════════════════════════════════════════════════════════════════════════
# 1 · DESCARGA DE TÉRMINOS (urllib real; transporte inyectable para pruebas offline)
# ══════════════════════════════════════════════════════════════════════════════
CABECERAS = {"User-Agent": "ARHIAX-RE-source-pack/1.0 (+audit)"}


def _transporte_urllib(url: str, timeout: float) -> bytes:
    import urllib.error
    import urllib.request
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=CABECERAS),
                                    timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTPError {exc.code} {exc.reason}") from exc


def descargar_terminos(url: str, *, transporte: Optional[Callable[[str, float], bytes]] = None,
                       timeout: float = 25.0,
                       consultado_en: Optional[str] = None) -> Dict[str, Any]:
    """Descarga los términos y devuelve URL + fecha + `sha256` (o el motivo del fallo).

    El hash se calcula sobre los BYTES descargados: si la descarga falla, el hash es
    `None` y el motivo queda declarado (nunca se inventa un hash).
    """
    traer = transporte or _transporte_urllib
    registro: Dict[str, Any] = {"url": url, "consulted_at": consultado_en or FECHA_CONSULTA,
                                "descargado": False, "http_status": None, "bytes": None,
                                "sha256": None, "terms_hash": None, "contenido": None,
                                "motivo": ""}
    try:
        crudo = traer(url, timeout)
    except Exception as exc:  # noqa: BLE001 — un fallo es un estado declarado
        registro["motivo"] = (f"No se pudo descargar el contenido de términos: "
                              f"{type(exc).__name__}: {exc}. `terms_hash=None` + motivo.")
        return registro
    if not crudo:
        registro["motivo"] = "El transporte devolvió contenido vacío: `terms_hash=None` + motivo."
        return registro
    registro.update({"descargado": True, "http_status": 200, "bytes": len(crudo),
                     "sha256": hashlib.sha256(bytes(crudo)).hexdigest(),
                     "terms_hash": hashlib.sha256(bytes(crudo)).hexdigest(),
                     "contenido": crudo,
                     "motivo": "Contenido descargado y hasheado en esta consulta."})
    return registro


def _texto_plano(crudo: Any) -> str:
    texto = (crudo.decode("utf-8", "replace") if isinstance(crudo, (bytes, bytearray))
             else str(crudo or ""))
    texto = re.sub(r"<script[\s\S]*?</script>", " ", texto)
    texto = re.sub(r"<[^>]+>", " ", texto)
    return " ".join(texto.split())


def analizar_terminos(contenido: Any) -> Dict[str, Any]:
    """Marcadores de licencia presentes en el contenido consultado (sin interpretar de más)."""
    plano = _texto_plano(contenido)
    buscar = {
        "cc_by_sa": r"CC BY-SA",
        "cc_by_sa_con_version": r"CC BY-SA\s*[0-9](\.[0-9])?",
        "creative_commons": r"Creative Commons",
        "odbl": r"Open Database License",
        "permite_persistir": r"(you are free to copy, distribute|may distribute the result|"
                             r"free to copy|atribución|attribution)",
        "excepcion_por_conjunto": r"(unless we indicate otherwise|salvo que indiquemos lo "
                                  r"contrario|CC BY-NC-SA)",
        # Prohibición de almacenar/cachear/redistribuir EL CONTENIDO (cierra la matriz).
        "prohibicion_explicita": r"(pre-fetch, index, store, reshare|not cache\b|no caching|"
                                 r"generally prohibited|prohibid[oa]\s+(?:almacenar|cachear|"
                                 r"redistribuir|descargar)|must not be stored)",
        # Reserva general de derechos: impide VERIFIED (falta autorización explícita), pero
        # NO es una prohibición de persistencia sobre el contenido licenciado.
        "reserva_de_derechos": r"(all rights reserved|reserved by us|"
                               r"distinto del expresamente autorizado|"
                               r"other than as expressly (?:authorized|permitted))",
    }
    return {clave: bool(re.search(patron, plano, re.IGNORECASE))
            for clave, patron in buscar.items()}


def evaluar_estado_por_evidencia(analisis: Dict[str, Any], *, licencia_esperada: str = "") -> Dict[str, Any]:
    """Dicta el estado del término a partir del contenido: prohibir cierra; declarar no abre.

    `VERIFIED` exige TODAS estas condiciones explícitas en el contenido consultado:
      1. una licencia reconocible (CC BY-SA / ODbL / equivalente declarado),
      2. la VERSIÓN de esa licencia impresa en el contenido,
      3. una autorización explícita de uso/persistencia,
      4. ninguna prohibición explícita y ninguna excepción por conjunto de datos.
    """
    faltan: List[str] = []
    if analisis.get("prohibicion_explicita"):
        return {"provider_terms_status": RESTRICTED,
                "motivo": ("El contenido consultado PROHÍBE explícitamente almacenar/cachear/"
                           "redistribuir: matriz cerrada de forma permanente."),
                "faltantes_para_verified": ["la prohibición tendría que levantarse por escrito"]}
    licencia = (analisis.get("cc_by_sa") or analisis.get("odbl")
                or analisis.get("creative_commons"))
    if not licencia:
        faltan.append("el contenido consultado no nombra ninguna licencia")
    if not analisis.get("cc_by_sa_con_version") and not analisis.get("odbl"):
        faltan.append("el contenido consultado no imprime la VERSIÓN de la licencia")
    if not analisis.get("permite_persistir"):
        faltan.append("el contenido consultado no autoriza explícitamente el uso/persistencia")
    if analisis.get("excepcion_por_conjunto"):
        faltan.append("el contenido admite excepciones por conjunto de datos")
    if analisis.get("reserva_de_derechos"):
        faltan.append("el contenido reserva los usos no autorizados expresamente")
    if not faltan:
        return {"provider_terms_status": VERIFIED,
                "motivo": ("Términos consultados, hasheados y con licencia + versión + "
                           "autorización explícitas: VERIFIED."),
                "faltantes_para_verified": []}
    return {"provider_terms_status": DECLARED,
            "motivo": ("El contenido consultado no alcanza VERIFIED: " + "; ".join(faltan) + "."),
            "faltantes_para_verified": faltan}


def verificar_terminos(url: str, *, transporte: Optional[Callable[[str, float], bytes]] = None,
                       timeout: float = 25.0,
                       consultado_en: Optional[str] = None) -> Dict[str, Any]:
    """Consulta viva de términos: URL + fecha + `sha256` + estado dictado por el contenido."""
    registro = descargar_terminos(url, transporte=transporte, timeout=timeout,
                                  consultado_en=consultado_en)
    registro["analisis"] = analizar_terminos(registro.get("contenido") or "")
    dictamen = evaluar_estado_por_evidencia(registro["analisis"])
    registro.update(dictamen)
    if not registro["descargado"]:
        registro["provider_terms_status"] = UNVERIFIED
        registro["faltantes_para_verified"] = ["descargar el contenido de términos (hoy falló)"]
    registro.pop("contenido", None)
    return registro


def verificar_evidencia_registrada(evidencia_id: str, *,
                                   transporte: Optional[Callable[[str, float], bytes]] = None,
                                   timeout: float = 25.0) -> Dict[str, Any]:
    """Re-descarga una evidencia registrada y compara su `sha256` con el anotado.

    Coincidencia ⇒ el contenido no cambió. Discrepancia ⇒ la página es dinámica y la
    evidencia identificaba una INSTANTÁNEA: se declara, no se finge que sigue igual.
    """
    registro = EVIDENCIA.get(evidencia_id)
    if registro is None:
        return {"evidencia_id": evidencia_id, "coincide": False,
                "motivo": "No existe esa evidencia en el registro de este módulo."}
    if not registro.get("url"):
        return {"evidencia_id": evidencia_id, "coincide": False,
                "hash_registrado": registro.get("sha256"),
                "motivo": "La evidencia no tiene URL pública (artefacto local o contractual)."}
    actual = descargar_terminos(registro["url"], transporte=transporte, timeout=timeout)
    return {
        "evidencia_id": evidencia_id,
        "url": registro["url"],
        "hash_registrado": registro.get("sha256"),
        "hash_actual": actual.get("sha256"),
        "bytes_actuales": actual.get("bytes"),
        "coincide": bool(actual.get("sha256") and actual.get("sha256") == registro.get("sha256")),
        "pagina_dinamica": bool(registro.get("pagina_dinamica")),
        "motivo": ("El contenido consultado coincide byte a byte con el registrado."
                   if actual.get("sha256") and actual.get("sha256") == registro.get("sha256")
                   else (actual.get("motivo") or
                         "El contenido cambió respecto a la instantánea registrada"
                         + (" (página dinámica: el hash identifica la instantánea, no un "
                            "artefacto estable)." if registro.get("pagina_dinamica") else "."))),
    }


def verificar_terminos_mapillary(*, transporte: Optional[Callable[[str, float], bytes]] = None,
                                 timeout: float = 25.0,
                                 consultado_en: Optional[str] = None) -> Dict[str, Any]:
    """Consulta los términos de Mapillary (URL documentada por el propio proveedor).

    Guarda URL consultada, fecha y `sha256` del contenido. Si el HTML no expone la
    licencia (o no imprime su versión), el estado se queda en `DECLARED` **con la URL
    y el hash de lo descargado**, y se dice explícitamente qué falta.
    """
    return verificar_terminos("https://www.mapillary.com/terms", transporte=transporte,
                              timeout=timeout, consultado_en=consultado_en)


def verificar_terminos_google(*, transporte: Optional[Callable[[str, float], bytes]] = None,
                              timeout: float = 25.0,
                              consultado_en: Optional[str] = None) -> Dict[str, Any]:
    """Consulta los términos de Google: prohibición explícita ⇒ `RESTRICTED` (fail-closed)."""
    registro = verificar_terminos("https://cloud.google.com/maps-platform/terms",
                                  transporte=transporte, timeout=timeout,
                                  consultado_en=consultado_en)
    if registro["provider_terms_status"] != RESTRICTED:
        registro["provider_terms_status"] = UNVERIFIED
        registro["can_persist"] = False
        registro["can_embed"] = False
        registro["faltantes_para_verified"] = ["resolución contractual explícita y escrita"]
        registro["motivo"] = (registro.get("motivo") or "") + (" Sin prohibición detectada, "
                                                              "pero SIN permiso explícito: "
                                                              "fail-closed (UNVERIFIED).")
    return registro


# ══════════════════════════════════════════════════════════════════════════════
# 2 · CATÁLOGO DE BLOQUES DE LICENCIA
# ══════════════════════════════════════════════════════════════════════════════
def _bloque(*, source_id: str, license_name: str, license_version: Optional[str],
            terms_url: Optional[str], consulted_at: Optional[str], terms_hash: Optional[str],
            terms_hash_reason: Optional[str], attribution_text: Optional[str],
            can_persist: bool, can_modify: bool, can_embed: bool, share_alike: bool,
            provider_terms_status: str, institution: Optional[str] = None,
            http_status: Optional[int] = None, consulted_bytes: Optional[int] = None,
            evidence_ids: Optional[Sequence[str]] = None, gap_para_verified: Optional[str] = None,
            notes: str = "", declared_in: str = "") -> Dict[str, Any]:
    if provider_terms_status not in ESTADOS_PROVIDER_TERMS:
        provider_terms_status = UNVERIFIED      # estado no declarado = fail-closed
    return {
        "source_id": source_id,
        "license_name": license_name,
        "license_version": license_version,
        "terms_url": terms_url,
        "consulted_at": consulted_at,
        "terms_hash": terms_hash,
        "terms_hash_reason": terms_hash_reason,
        "attribution_text": attribution_text,
        "can_persist": bool(can_persist),
        "can_modify": bool(can_modify),
        "can_embed": bool(can_embed),
        "share_alike": bool(share_alike),
        "provider_terms_status": provider_terms_status,
        "consulted_http_status": http_status,
        "consulted_bytes": consulted_bytes,
        "evidence_ids": list(evidence_ids or []),
        "gap_para_verified": gap_para_verified,
        "notes": notes,
        "institution": institution,
        "declared_in": declared_in,
    }


def _registro_fuentes() -> Dict[str, Dict[str, Any]]:
    try:
        return json.loads(Path(RUTA_REGISTRO).read_text(encoding="utf-8")).get("sources") or {}
    except Exception:  # noqa: BLE001
        return {}


def _ev(evidencia_id: str) -> Dict[str, Any]:
    return dict(EVIDENCIA.get(evidencia_id) or {})


def construir_catalogo() -> Dict[str, Dict[str, Any]]:
    """Construye el bloque canónico de CADA fuente del registro (35) + verificación cruzada.

    Los valores se toman del registro/manifest del producto (declarado) y de la
    evidencia de términos consultada en esta ronda (real). Nada se inventa: cuando no
    hay evidencia, el estado es `UNVERIFIED` y el hueco queda escrito.
    """
    fuentes = _registro_fuentes()
    catalogo: Dict[str, Dict[str, Any]] = {}
    ev_alcaldia = _ev("ALCALDIA_APERTURA_DATOS")
    ev_mapillary = _ev("MAPILLARY_TERMS")
    ev_map_gap = _ev("MAPILLARY_CC_BY_SA_4_0")
    ev_google = _ev("GOOGLE_MAPS_PLATFORM_TERMS")
    ev_google2 = _ev("GOOGLE_STREETVIEW_POLICIES")
    ev_osm = _ev("OSM_COPYRIGHT")
    ev_lonja = _ev("LONJA_METODOLOGIA_LOCAL")

    _anexo = "CATASTRO_BAQ_ADOPCION_ANEXO1"
    for sid, fuente in fuentes.items():
        institucion = fuente.get("institution")
        declarado = "registry:docs/source_pack/barranquilla_sources_v1.json"
        can_persist = bool(fuente.get("can_persist_raw", True))
        can_embed = bool(fuente.get("can_embed_image", False))

        if sid == _anexo:
            catalogo[sid] = _bloque(
                source_id=sid, institution=institucion,
                license_name=("Documento oficial aportado por el usuario (Certificado SNR / "
                              "anexo de adopción catastral IGAC): copia normalizada con hash"),
                license_version=None,
                terms_url="https://www.supernotariado.gov.co/",
                consulted_at=None, terms_hash=None,
                terms_hash_reason=("Documento aportado por el usuario, no una página de "
                                   "términos: no hay contenido de licencia que descargar."),
                attribution_text="Documento oficial aportado por el titular del expediente",
                can_persist=can_persist, can_modify=False, can_embed=False, share_alike=False,
                provider_terms_status=UNVERIFIED,
                gap_para_verified=("Resolución/documento de autorización de reutilización del "
                                   "certificado emitido por la SNR."),
                notes=("El registro declara can_persist_raw=true: se conserva una copia "
                       "normalizada con hash, no el original completo."),
                declared_in=declarado)
            continue
        if sid == FUENTE_OSM:
            catalogo[sid] = _bloque(
                source_id=sid, institution=institucion,
                license_name="Open Database License (ODbL) 1.0", license_version="1.0",
                terms_url=ev_osm.get("url"),
                consulted_at=ev_osm.get("consulted_at"), terms_hash=ev_osm.get("sha256"),
                terms_hash_reason=ev_osm.get("motivo"),
                attribution_text=ATRIBUCION_OSM,
                can_persist=can_persist, can_modify=True, can_embed=False, share_alike=True,
                provider_terms_status=VERIFIED, http_status=ev_osm.get("http_status"),
                consulted_bytes=ev_osm.get("bytes"), evidence_ids=["OSM_COPYRIGHT"],
                gap_para_verified=None,
                notes=("Único término del pack verificado en línea con hash. Datos, no "
                       "imágenes: no hay imagen de proveedor que incrustar (can_embed=False "
                       "significa «no aplica incrustación de imagen»)."),
                declared_in=declarado)
            continue
        if sid == FUENTE_MAPILLARY:
            catalogo[sid] = _bloque(
                source_id=sid, institution=institucion,
                license_name="Creative Commons Attribution-ShareAlike (CC BY-SA) para el "
                             "Contenido del usuario de otros usuarios",
                license_version=None,
                terms_url=ev_mapillary.get("url"),
                consulted_at=ev_mapillary.get("consulted_at"),
                terms_hash=ev_mapillary.get("sha256"),
                terms_hash_reason=ev_mapillary.get("motivo"),
                attribution_text=ATRIBUCION_MAPILLARY,
                can_persist=can_persist, can_modify=True, can_embed=can_embed, share_alike=True,
                provider_terms_status=DECLARED,
                http_status=ev_mapillary.get("http_status"),
                consulted_bytes=ev_mapillary.get("bytes"),
                evidence_ids=["MAPILLARY_TERMS", "MAPILLARY_CC_BY_SA_4_0"],
                gap_para_verified=(
                    "Falta UNA de estas dos cosas: (a) descargar y hashear la página que fija "
                    "la VERSIÓN de la licencia (CC BY-SA 4.0) — consultada hoy y bloqueada con "
                    "HTTP 403 — o (b) un documento del proveedor que confirme la versión y el "
                    "alcance por conjunto de datos. Mientras falte, el estado es DECLARED y "
                    "NO se congela el pack por ello: se declara el hueco."),
                notes=(ev_mapillary.get("motivo") or "") + " " + (ev_map_gap.get("motivo") or ""),
                declared_in=declarado)
            continue
        if sid == FUENTE_GOOGLE:
            catalogo[sid] = _bloque(
                source_id=sid, institution=institucion,
                license_name="Google Maps Platform Terms — Street View (uso restringido)",
                license_version=None,
                terms_url=ev_google.get("url"),
                consulted_at=ev_google.get("consulted_at"),
                terms_hash=ev_google.get("sha256"),
                terms_hash_reason=ev_google.get("motivo"),
                attribution_text=ATRIBUCION_GOOGLE,
                can_persist=False, can_modify=False, can_embed=False, share_alike=False,
                provider_terms_status=RESTRICTED,
                http_status=ev_google.get("http_status"),
                consulted_bytes=ev_google.get("bytes"),
                evidence_ids=["GOOGLE_MAPS_PLATFORM_TERMS", "GOOGLE_STREETVIEW_POLICIES"],
                gap_para_verified=("No hay nada que «verificar» para abrir: la evidencia "
                                   "consultada PROHÍBE almacenar y cachear. Solo un documento "
                                   "contractual escrito de Google podría cambiar el estado."),
                notes=(ev_google.get("motivo") or "") + " " + (ev_google2.get("cita") or ""),
                declared_in=declarado)
            continue
        if sid == FUENTE_LONJA:
            sha_yaml = _sha256_artefacto(RUTA_METODOLOGIA_LONJA)
            catalogo[sid] = _bloque(
                source_id=sid, institution=institucion,
                license_name=("Artefacto local de metodología de mercado — licencia "
                              "DECLARADA, contrato no verificado"),
                license_version=None,
                terms_url=str(RUTA_METODOLOGIA_LONJA.relative_to(_DIR_RAIZ)),
                consulted_at=ev_lonja.get("consulted_at"), terms_hash=sha_yaml,
                terms_hash_reason=("El «término» es un documento CONTRACTUAL del repositorio: "
                                   "se hashea el artefacto real (metodología), pero un "
                                   "contrato no se verifica contra una URL pública."),
                attribution_text=ATRIBUCION_LONJA,
                can_persist=can_persist, can_modify=False, can_embed=False, share_alike=False,
                provider_terms_status=DECLARED,
                evidence_ids=["LONJA_METODOLOGIA_LOCAL"],
                gap_para_verified=("Contrato firmado de la Lonja BAQ que autorice "
                                   "explícitamente uso y persistencia (hoy la autorización es "
                                   "declarada por el productor, no verificada)."),
                notes=("Artefacto local del producto (NO es una fuente de datos: la Lonja no "
                       "aporta datos a DICTUS). Hash del "
                       f"artefacto metodológico: {sha_yaml}. Declarado no redistribuible; sin "
                       "incrustación de imagen."),
                declared_in=declarado)
            continue
        if sid in (FUENTE_SOLAR, FUENTE_SOMBRA):
            catalogo[sid] = _bloque(
                source_id=sid, institution=institucion,
                license_name="Cálculo propio de ARHIAX RE (sin licencia de tercero)",
                license_version=None, terms_url=None, consulted_at=None, terms_hash=None,
                terms_hash_reason="No hay licencia de tercero que consultar: es cálculo propio.",
                attribution_text="Cálculo propio ARHIAX RE",
                can_persist=can_persist, can_modify=True, can_embed=False, share_alike=False,
                provider_terms_status=NOT_APPLICABLE,
                gap_para_verified=None,
                notes=("Resultado reproducible y auditable. can_embed=False significa «no hay "
                       "imagen DE PROVEEDOR»; un PNG propio se rige por el manifiesto de "
                       "activos visuales."),
                declared_in=declarado)
            continue

        # Familia Alcaldía Distrital (catastro, POT, equipamiento, riesgo): datos abiertos.
        catalogo[sid] = _bloque(
            source_id=sid, institution=institucion,
            license_name=("Datos abiertos de la Alcaldía Distrital de Barranquilla (geoportal "
                          "miciudad) — uso con atribución a la fuente oficial"),
            license_version=None,
            terms_url="https://catastro.barranquilla.gov.co/mi-ciudad/",
            consulted_at=ev_alcaldia.get("consulted_at"), terms_hash=None,
            terms_hash_reason=(ev_alcaldia.get("motivo") or "") +
                              " Ninguna fuente del Distrito publica términos junto al servicio.",
            attribution_text=ATRIBUCION_ALCALDIA,
            can_persist=can_persist, can_modify=False, can_embed=False, share_alike=False,
            provider_terms_status=UNVERIFIED,
            http_status=ev_alcaldia.get("http_status"),
            evidence_ids=["ALCALDIA_APERTURA_DATOS"],
            gap_para_verified=("Obtener y hashear la licencia oficial de reutilización del "
                               "Distrito (hoy la página de apertura de datos responde 403 y el "
                               "geoportal 403 Cloudflare): sin URL + fecha + sha256 no hay "
                               "VERIFIED."),
            notes=("Uso con atribución obligatoria a la fuente oficial; sin incrustación de "
                   "imagen; sin redistribución del crudo fuera del expediente."),
            declared_in=declarado)
    return catalogo


_CATALOGO: Optional[Dict[str, Dict[str, Any]]] = None


def catalogo_licencias(*, refrescar: bool = False) -> Dict[str, Dict[str, Any]]:
    """Catálogo de bloques de licencia (por `source_id`). Se construye una vez y se cachea."""
    global _CATALOGO
    if _CATALOGO is None or refrescar:
        _CATALOGO = construir_catalogo()
    return _CATALOGO


def licencia(source_id: str) -> Optional[Dict[str, Any]]:
    """Bloque canónico de licencia de una fuente (`None` si la fuente no está declarada)."""
    return catalogo_licencias().get(str(source_id))


def campos_faltantes(bloque: Optional[Dict[str, Any]]) -> List[str]:
    """Campos del bloque canónico que no están presentes (bloque incompleto = defecto)."""
    if not isinstance(bloque, dict):
        return list(CAMPOS_BLOQUE)
    return [campo for campo in CAMPOS_BLOQUE if campo not in bloque]


def bloque_completo(bloque: Optional[Dict[str, Any]]) -> bool:
    return not campos_faltantes(bloque)


# ══════════════════════════════════════════════════════════════════════════════
# 3 · PERMISOS: NINGÚN FLUJO INCRUSTA SIN PERMISO DECLARADO
# ══════════════════════════════════════════════════════════════════════════════
_ENV_STRICT_TERMS = "ARHIAX_IMAGERY_STRICT_TERMS"
ESTADOS_QUE_PERMITEN_INCRUSTAR: Tuple[str, ...] = (VERIFIED, DECLARED)


def _modo_estricto() -> bool:
    return str(os.environ.get(_ENV_STRICT_TERMS, "")).strip().lower() in ("1", "true", "yes")


def autorizar_incrustacion(source_id: str, *, destino: Optional[str] = None) -> Dict[str, Any]:
    """Única vía de incrustación. FAIL-CLOSED: sin permiso declarado ⇒ `permitido=False`."""
    bloque = licencia(source_id)
    if bloque is None:
        return {"source_id": source_id, "permitido": False, "destino": destino,
                "can_embed": False, "flujo": "NINGUNO",
                "motivo": f"Fuente «{source_id}» sin bloque de licencia declarado: fail-closed."}
    estado = bloque.get("provider_terms_status")
    motivos: List[str] = []
    if not bloque.get("can_embed"):
        motivos.append("el bloque declara can_embed=False: ningún flujo puede incrustar")
    if estado not in ESTADOS_QUE_PERMITEN_INCRUSTAR:
        motivos.append(f"provider_terms_status={estado} no habilita incrustación")
    if _modo_estricto() and estado != VERIFIED:
        motivos.append(f"modo estricto ({_ENV_STRICT_TERMS}=1): sólo VERIFIED incrusta")
    permitido = not motivos
    return {
        "source_id": source_id,
        "permitido": permitido,
        "can_embed": bool(bloque.get("can_embed")),
        "provider_terms_status": estado,
        "destino": destino,
        "flujo": ("COPIAR_CON_ATRIBUCION" if permitido else "NINGUNO"),
        "attribution_text": bloque.get("attribution_text") if permitido else None,
        "share_alike": bool(bloque.get("share_alike")),
        "motivo": ("Incrustación autorizada por el bloque de licencia (can_embed=True, "
                   f"estado {estado})." if permitido else "; ".join(motivos) + "."),
    }


def persistencias_permitidas() -> Dict[str, Dict[str, Any]]:
    """Matriz declarada de persistencia/incrustación por fuente (auditoría)."""
    return {sid: {"can_persist": b["can_persist"], "can_modify": b["can_modify"],
                  "can_embed": b["can_embed"], "share_alike": b["share_alike"],
                  "provider_terms_status": b["provider_terms_status"],
                  "attribution_text": b["attribution_text"],
                  "terms_hash": b["terms_hash"]}
            for sid, b in catalogo_licencias().items()}


def resumen() -> Dict[str, Any]:
    """Resumen auditable: cuántas fuentes por estado y QUÉ falta para VERIFIED."""
    catalogo = catalogo_licencias()
    por_estado: Dict[str, int] = {estado: 0 for estado in ESTADOS_PROVIDER_TERMS}
    verificadas, pendientes = [], []
    for sid, bloque in catalogo.items():
        estado = bloque.get("provider_terms_status")
        por_estado[estado] = por_estado.get(estado, 0) + 1
        (verificadas if estado == VERIFIED else pendientes).append(sid)
    return {
        "total_fuentes": len(catalogo),
        "por_estado": por_estado,
        "verificadas": sorted(verificadas),
        "pendientes_de_verified": sorted(pendientes),
        "no_verificables_por_diseno": sorted(
            sid for sid, b in catalogo.items()
            if b.get("provider_terms_status") == NOT_APPLICABLE),
        "huecos_para_verified": {sid: (b.get("gap_para_verified") or "no declarado")
                                 for sid, b in sorted(catalogo.items())
                                 if b.get("provider_terms_status") != VERIFIED},
        "congelado_por_licencia": False,
        "nota": ("Un estado DECLARED/UNVERIFIED NO congela el pack: se declara el hueco. Lo "
                 "único cerrado por licencia es lo que la evidencia PROHÍBE (Google → "
                 "RESTRICTED, fail-closed) y lo que no tiene permiso de incrustación."),
        "generado_at": ahora(),
    }


def verificar_vocabulario() -> Dict[str, Any]:
    """El vocabulario de estados de este bloque coincide con el de `street_imagery`."""
    resultado = {"estados_coinciden": True, "detalle": "street_imagery no disponible"}
    if si is not None:
        resultado = {
            "estados_coinciden": tuple(ESTADOS_PROVIDER_TERMS) == tuple(si.ESTADOS_TERMINOS),
            "detalle": {"license_blocks": list(ESTADOS_PROVIDER_TERMS),
                        "street_imagery": list(si.ESTADOS_TERMINOS)},
        }
    return resultado


def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Bloques de licencia del Source Pack")
    ap.add_argument("--source", help="muestra el bloque de una fuente")
    ap.add_argument("--resumen", action="store_true", help="resumen por estado")
    ap.add_argument("--verificar-mapillary", action="store_true",
                    help="consulta VIVA de los términos de Mapillary (red)")
    ap.add_argument("--verificar-google", action="store_true",
                    help="consulta VIVA de los términos de Google (red)")
    args = ap.parse_args(list(argv) if argv is not None else None)
    if args.source:
        print(json.dumps(licencia(args.source), ensure_ascii=False, indent=1))
    if args.verificar_mapillary:
        print(json.dumps(verificar_terminos_mapillary(), ensure_ascii=False, indent=1))
    if args.verificar_google:
        print(json.dumps(verificar_terminos_google(), ensure_ascii=False, indent=1))
    if args.resumen or not (args.source or args.verificar_mapillary or args.verificar_google):
        print(json.dumps(resumen(), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

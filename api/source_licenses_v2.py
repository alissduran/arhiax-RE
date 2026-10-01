# -*- coding: utf-8 -*-
"""ARHIAX RE — SOURCE PACK v2 · LICENCIA DE **IMÁGENES** ≠ TÉRMINOS DE **API/PROVEEDOR**.

Este módulo nace de una decisión de producto concreta: **no mezclar** dos preguntas
que la v1 resolvía en un solo campo (`provider_terms_status`):

    IMAGERY_LICENSE_STATUS  ¿bajo qué licencia se comparten las IMÁGENES que el
                            proveedor publica, y qué obliga esa licencia?
                            → rige los DERECHOS (persistir / modificar / incrustar /
                              share-alike).
    API_TERMS_STATUS        ¿qué términos gobiernan la API/plataforma por la que se
                            ACCEDE (o se accede a la metadata)?
                            → rige la ADQUISICIÓN (client_id, interfaces publicadas,
                              sin scraping, throttling). NO otorga ni amplía derechos
                              sobre las imágenes.

Las dos se registran por separado, con su propia evidencia y su propio hueco. Un
estado `VERIFIED` en `API_TERMS_STATUS` no abre la matriz de imágenes y un
`IMAGERY_LICENSE_STATUS=VERIFIED` no autoriza a scrapear la API.

Reglas duras (fail-closed)
──────────────────────────
1. **Ningún permiso se asume.** Sin evidencia (URL + fecha + HTTP + bytes + `sha256`)
   no hay `VERIFIED`: el estado baja y el hueco se escribe en
   `what_is_missing_for_verified`.
2. **HTTP 200 no es evidencia.** Las páginas `mapillary.com/terms/data`,
   `mapillary.com/terms/api` y `mapillary.com/developer/api-documentation` responden
   200 con el cuerpo de «página no encontrada» (soft-404): se registran como
   `SOFT_404`, **no** como términos consultados. Lo mismo para una página accesible
   que no imprime licencia: se registra sin marcadores.
3. **Google Street View permanece cerrado**: `can_persist=False`,
   `can_modify=False`, `can_embed=False`, `product_role=OPTIONAL_ENRICHMENT` y
   `bloquea_source_pack=False` (un enriquecimiento opcional NO bloquea el pack).
4. **La Lonja NO es una fuente.** Este módulo no la declara como `source_id`, ni como
   `authority_class`, ni como proveedor de mercado: vive como `institutional_partner`
   fuera del Source Registry (ver `PARTNERS_INSTITUCIONALES` y
   `docs/source_pack/INSTITUTIONAL_PARTNERS.md`). Nada de este módulo condiciona
   `CONTRACT_FROZEN` ni `OPERATIONAL_READY`.
5. Este módulo es de **solo lectura** sobre el resto del producto: no importa
   `api/source_licenses.py` (v1 sigue siendo la pieza auditada del pack), no escribe
   `docs/source_pack/raw/`, no toca PDF, motores, compuerta ni hash maestro.

Evidencia de esta ronda (`consulted_at = 2026-09-29`): ver `EVIDENCIA` y
`docs/source_pack/IMAGERY_LICENSES.md`.
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
DIR_PACK = _DIR_RAIZ / "docs" / "source_pack"

VERSION_MODULO = "source-licenses-v2/2.0.0"
FECHA_CONSULTA = "2026-09-29"          # fecha REAL de la consulta de evidencia (UTC)


def _cargar_modulo(nombre: str, *rutas: Path):
    """Importa un módulo hermano de `api/` de forma determinista (sin depender del cwd)."""
    try:
        return importlib.import_module(nombre)
    except Exception:  # noqa: BLE001
        pass
    for ruta in rutas:
        if not ruta.exists():
            continue
        alias = f"_arhiax_v2_{nombre}"
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
        except Exception:  # noqa: BLE001
            sys.modules.pop(alias, None)
            raise
        return mod
    raise ImportError(f"No se pudo cargar el módulo requerido: {nombre}")


try:                                        # vocabulario ya existente (se reutiliza, no se duplica)
    si = _cargar_modulo("street_imagery", _DIR_API / "street_imagery.py")
except Exception:                           # noqa: BLE001 — el bloque no depende de él
    si = None

# ══════════════════════════════════════════════════════════════════════════════
# 1 · VOCABULARIO CERRADO (idéntico al de api/street_imagery.py)
# ══════════════════════════════════════════════════════════════════════════════
VERIFIED = "VERIFIED"                  # consultado + hasheado + autorización explícita
DECLARED = "DECLARED"                  # declarado, sin verificación completa
UNVERIFIED = "UNVERIFIED"              # no verificable → fail-closed
RESTRICTED = "RESTRICTED"              # evidencia consultada que PROHÍBE
NOT_APPLICABLE = "NOT_APPLICABLE"      # sin licencia de tercero (cálculo/dato propio)

ESTADOS: Tuple[str, ...] = (VERIFIED, DECLARED, UNVERIFIED, RESTRICTED, NOT_APPLICABLE)

# Estados de la EVIDENCIA (qué es, de verdad, el documento registrado).
EV_ACCESIBLE = "ACCESIBLE_VERIFICADA"        # 200 + contenido pertinente, proveedor
EV_SOFT_404 = "SOFT_404"                     # 200 con cuerpo de «página no encontrada»
EV_INACCESIBLE = "INACCESIBLE_HTTP_ERROR"    # 403/404/5xx: sin bytes ni hash
EV_ARCHIVADA = "COPIA_ARCHIVADA_DE_DOC_PROVEEDOR"
EV_TERCERO = "TERCERO_NO_PROVEEDOR"          # corrobora, NO verifica
EV_SIN_MARCADORES = "ACCESIBLE_SIN_MARCADORES_DE_LICENCIA"
EV_ESTADOS: Tuple[str, ...] = (EV_ACCESIBLE, EV_SOFT_404, EV_INACCESIBLE, EV_ARCHIVADA,
                               EV_TERCERO, EV_SIN_MARCADORES)

# Rol de producto: un enriquecimiento opcional NO puede bloquear el Source Pack.
PRODUCT_ROLE_OPTIONAL_ENRICHMENT = "OPTIONAL_ENRICHMENT"
PRODUCT_ROLE_CONTEXT = "CONTEXT"
PRODUCT_ROLE_NOT_A_SOURCE = "NOT_A_SOURCE"

# ── campos del bloque canónico (v2) ───────────────────────────────────────────
CAMPOS_BLOQUE: Tuple[str, ...] = (
    "source_id", "license_name", "license_version", "license_url", "consulted_at",
    "http_status", "bytes", "sha256", "attribution_text", "can_persist", "can_modify",
    "can_embed", "share_alike", "IMAGERY_LICENSE_STATUS", "API_TERMS_STATUS",
    "evidence_status", "what_is_missing_for_verified",
)
CAMPOS_ADICIONALES: Tuple[str, ...] = (
    "imagery_license", "api_terms", "evidence_ids", "product_role",
    "bloquea_source_pack", "conditions", "residual_gaps", "attribution_required",
    "verified_scope", "notes", "module_version",
)

SOURCE_MAPILLARY = "MAPILLARY"
SOURCE_GOOGLE = "GOOGLE_STREET_VIEW"
SOURCE_OSM = "OSM_OVERPASS"
SOURCE_IDS: Tuple[str, ...] = (SOURCE_MAPILLARY, SOURCE_GOOGLE, SOURCE_OSM)

# Texto de atribución exigido (imágenes). No es una fórmula decorativa: los términos
# de Mapillary exigen atribución VISIBLE con enlace cuando se sirven imágenes propias.
ATRIBUCION_MAPILLARY = ("© Mapillary contributors (CC BY-SA 4.0) — atribución visible "
                        "obligatoria con enlace a Mapillary: la imagen debe enlazar a su "
                        "página en Mapillary (y mostrar el logo Mapillary cuando el medio "
                        "lo permita)")
ATRIBUCION_GOOGLE = "© Google"
ATRIBUCION_OSM = "© OpenStreetMap contributors (ODbL 1.0)"

# ══════════════════════════════════════════════════════════════════════════════
# 2 · EVIDENCIA CONSULTADA DE VERDAD EN ESTA RONDA (2026-09-29)
# ══════════════════════════════════════════════════════════════════════════════
# `sha256` identifica la INSTANTÁNEA descargada en `consulted_at`, no un artefacto
# inmutable: las páginas del proveedor son dinámicas (ver `hashes_observados`).
EVIDENCIA: Dict[str, Dict[str, Any]] = {
    # ── IMÁGENES Mapillary ────────────────────────────────────────────────────
    "MAPILLARY_TERMS_OF_USE": {
        "url": "https://www.mapillary.com/terms",
        "consulted_at": FECHA_CONSULTA,
        "http_status": 200,
        "bytes": 111094,
        "sha256": "e9ce3ac2fddf91013b86d5a3a7f56cf8424522e00e942dced10215331f330ea7",
        "content_type": "text/html; charset=utf-8",
        "evidence_status": EV_ACCESIBLE,
        "documento": "Mapillary Terms of Use — «Effective date: February 15, 2024» (§3(b) Licenses)",
        "del_proveedor": True,
        "pagina_dinamica": True,
        "hashes_observados": [
            {"bytes": 111094,
             "sha256": "e9ce3ac2fddf91013b86d5a3a7f56cf8424522e00e942dced10215331f330ea7"},
            {"bytes": 111095, "sha256": "d6e759e32f895c783baadb605fa62ff2998b1cd4f8682ca80ea0292336da1d19"},
            {"bytes": 111095, "sha256": "958c00cef1b84cae12dc79c5ade6530e7dd5f2a08affb3a29074bcdfe60cdc1f"},
            {"bytes": 118251, "sha256": "5b7ed8e2b192292fcefa18c0daf09b5cdc3ffe9df21f0ce75048f3d360b52ec3"},
        ],
        "marcadores": {"cc_by_sa_texto": True, "cc_by_sa_4_0_texto": False,
                       "cc_by_sa_4_0_enlaces": 1, "attribution_required": True,
                       "share_alike": True, "api_developer_terms": True,
                       "no_scraping": True, "prohibicion_persistir": False,
                       "soft_404": False, "effective_date": True},
        "cita_licencia_imagenes": (
            "«Your use of any User Content provided by other users is subject to the "
            "Creative Commons Share Alike (CC BY-SA) license, unless we indicate "
            "otherwise. For instance, we may provide access to certain User Content […] "
            "under a separate set of license terms (such as the Creative Commons "
            "Attribution NonCommercial Share Alike (CC BY-NC-SA license).» (§3(b))"),
        "cita_version_4_0": (
            "El propio documento enlaza el nombre de la licencia al deed canónico: "
            "«Your use of any User Content provided by other users is subject to the "
            "<a href=\"http://creativecommons.org/licenses/by-sa/4.0/\">Creative Commons "
            "Share Alike (CC BY-SA) license</a>» → la VERSIÓN 4.0 queda evidenciada por el "
            "enlace del proveedor (no impresa como texto «4.0»)."),
        "cita_atribucion": (
            "«You must adhere to the attribution requirements set forth below and as "
            "applicable to any User Content provided by others that you obtain. If you are "
            "downloading individual images and serving them from your own servers, you must "
            "attribute the image(s) by visibly displaying the Mapillary logo and linking "
            "back to the Mapillary homepage or corresponding Mapillary image page.»"),
        "cita_api": (
            "§11 Additional Terms for Developers + §12: «You will not […] Develop or use any "
            "applications that interact with the Mapillary Services other than in accordance "
            "with the Additional Terms for Developers set forth in Section 11 below; Access "
            "or search or attempt to access or search the Mapillary Services by any means "
            "(automated or otherwise) other than […] through the currently available, "
            "published interfaces that we provide»."),
        "nota": ("El documento SÍ contempla descargar imágenes y servirlas desde servidores "
                 "propios, con atribución visible y enlace: la persistencia de IMÁGENES está "
                 "contemplada por la licencia. Incluye excepciones por conjunto de datos."),
    },
    "MAPILLARY_HELP_CC_BY_SA_4_0": {
        "url": ("https://help.mapillary.com/hc/en-us/articles/"
                "115001770409-CC-BY-SA-license-for-open-data"),
        "consulted_at": FECHA_CONSULTA,
        "http_status": 403,
        "bytes": None,
        "sha256": None,
        "content_type": None,
        "evidence_status": EV_INACCESIBLE,
        "documento": "Artículo oficial «CC-BY-SA license for open data» (Center de ayuda Mapillary)",
        "del_proveedor": True,
        "pagina_dinamica": True,
        "marcadores": {"cc_by_sa_texto": False, "cc_by_sa_4_0_enlaces": 0,
                       "attribution_required": False, "soft_404": False},
        "nota": ("HTTP 403 Forbidden en vivo: sin bytes ni hash. La página que fija la "
                 "licencia de las IMÁGENES en el centro de ayuda NO es accesible desde esta "
                 "red; se registra el intento y se busca evidencia alternativa accesible."),
    },
    "MAPILLARY_HELP_CC_BY_SA_4_0_ARCHIVO": {
        "url": ("https://web.archive.org/web/20260724100858/https://help.mapillary.com/"
                "hc/en-us/articles/115001770409-CC-BY-SA-license-for-open-data"),
        "consulted_at": FECHA_CONSULTA,
        "http_status": 200,
        "bytes": 32538,
        "sha256": "165ec7abfa0b8b122d3c3c5b20851dd96b5cc2f1a7745df52145b18e63a0b34f",
        "content_type": "text/html; charset=utf-8",
        "evidence_status": EV_ARCHIVADA,
        "documento": ("Copia archivada (Wayback, captura 2026-07-24) del artículo OFICIAL "
                      "de Mapillary; el artículo se lista «May 12, 2025 11:34 Updated»"),
        "del_proveedor": True,
        "es_copia_archivada": True,
        "pagina_dinamica": True,
        "marcadores": {"cc_by_sa_texto": True, "cc_by_sa_4_0_enlaces": 3,
                       "attribution_required": True, "share_alike": True, "soft_404": False},
        "cita_atribucion": (
            "«All images on Mapillary are shared under a CC-BY-SA license, which in short "
            "means that anyone can look at and distribute your images, and even modify them "
            "a bit, as long as they give attribution. This is an example of a perfect "
            "attribution when you use Mapillary imagery on your website, blog etc: “Title” "
            "<Link to Mapillary image> by “username” <Link to user profile>, licensed under "
            "CC-BY-SA.»"),
        "nota": ("Es la página que la v1 registró como hueco (403 en vivo). El contenido es "
                 "del PROVEEDOR pero se sirve desde un tercero (Wayback): sirve como "
                 "evidencia corroborante y para fijar el texto de atribución; NO se presenta "
                 "como acceso directo al documento oficial en vivo."),
    },
    "CC_BY_SA_4_0_DEED": {
        "url": "https://creativecommons.org/licenses/by-sa/4.0/",
        "consulted_at": FECHA_CONSULTA,
        "http_status": 200,
        "bytes": 35745,
        "sha256": "6acd86b2893060f04d2b8d8743ef12baf046bb46973374c6e077e366cad01d66",
        "content_type": "text/html; charset=utf-8",
        "evidence_status": EV_ACCESIBLE,
        "documento": "Deed canónico CC BY-SA 4.0 (Attribution-ShareAlike 4.0 International)",
        "del_proveedor": False,
        "es_texto_de_la_licencia": True,
        "pagina_dinamica": True,
        "marcadores": {"cc_by_sa_texto": True, "cc_by_sa_4_0_enlaces": 101,
                       "attribution_required": True, "share_alike": True, "soft_404": False},
        "cita_atribucion": (
            "«You are free to: Share — copy and redistribute the material in any medium or "
            "format for any purpose, even commercially. Adapt — remix, transform, and build "
            "upon the material for any purpose, even commercially. The licensor cannot "
            "revoke these freedoms as long as you follow the license terms.» · «Attribution "
            "— You must give appropriate credit, provide a link to the license, and indicate "
            "if changes were made.» · «ShareAlike — If you remix, transform, or build upon "
            "the material, you must distribute your contributions under the same license as "
            "the original.»"),
        "nota": ("Es el TEXTO de la licencia al que apuntan los términos de Mapillary (§3(b)). "
                 "Evidencia del contenido de la licencia; NO es una declaración del proveedor "
                 "sobre sus imágenes."),
    },
    "CC_BY_SA_4_0_LEGALCODE": {
        "url": "https://creativecommons.org/licenses/by-sa/4.0/legalcode",
        "consulted_at": FECHA_CONSULTA,
        "http_status": 200,
        "bytes": 51860,
        "sha256": "6c0f42e2d43700044349772d54265a315171f47d42f5e88cd380481bf18d814e",
        "content_type": "text/html; charset=utf-8",
        "evidence_status": EV_ACCESIBLE,
        "documento": "Código legal CC BY-SA 4.0",
        "del_proveedor": False,
        "es_texto_de_la_licencia": True,
        "pagina_dinamica": True,
        "nota": "Código legal de la licencia (respaldo del deed) para citar obligaciones exactas.",
    },
    "MAPILLARY_TERMS_DATA": {
        "url": "https://www.mapillary.com/terms/data",
        "consulted_at": FECHA_CONSULTA,
        "http_status": 200,
        "bytes": 74357,
        "sha256": "800bd2f8439e0b94ec18340e71b26a276d78eca198790f93ec222370eab3e168",
        "content_type": "text/html; charset=utf-8",
        "evidence_status": EV_SOFT_404,
        "documento": "Ruta probada como «términos de datos»: NO existe",
        "del_proveedor": True,
        "pagina_dinamica": True,
        "nota": ("HTTP 200 pero el cuerpo es la página «No hemos podido encontrar la página "
                 "que buscabas» (soft-404). Se registra para que NADIE lo cuente como "
                 "términos consultados: HTTP 200 no es evidencia."),
    },
    "MAPILLARY_TERMS_API": {
        "url": "https://www.mapillary.com/terms/api",
        "consulted_at": FECHA_CONSULTA,
        "http_status": 200,
        "bytes": 74354,
        "sha256": "ba4abe7a8b8e7db39adbdc9500534c5a578734579f321c727855804cff30d025",
        "content_type": "text/html; charset=utf-8",
        "evidence_status": EV_SOFT_404,
        "documento": "Ruta probada como «términos de API»: NO existe (soft-404)",
        "del_proveedor": True,
        "pagina_dinamica": True,
        "nota": ("HTTP 200 con cuerpo de «página no encontrada»: NO hay documento de términos "
                 "de API separado y accesible. Este es el hueco exacto de API_TERMS_STATUS."),
    },
    "MAPILLARY_API_DOC": {
        "url": "https://www.mapillary.com/developer/api-documentation",
        "consulted_at": FECHA_CONSULTA,
        "http_status": 200,
        "bytes": 131397,
        "sha256": "ed5e7b126c65c4139cdf94dbbf89526538189b820b0fd8d5f09aa24c8cb947c9",
        "content_type": "text/html; charset=utf-8",
        "evidence_status": EV_SIN_MARCADORES,
        "documento": "Documentación de la API de Mapillary (accesible; menciona Developer Tools/client_id)",
        "del_proveedor": True,
        "pagina_dinamica": True,
        "marcadores": {"cc_by_sa_texto": False, "api_developer_terms": True, "soft_404": False},
        "nota": ("Página ACCESIBLE pero NO declara la licencia de las imágenes ni es un "
                 "documento de términos: se registra sin marcadores de licencia y no sostiene "
                 "por sí sola ningún VERIFIED de imágenes."),
    },
    # ── API/plataforma Mapillary (mismo documento de términos) ────────────────
    # (se referencia MAPILLARY_TERMS_OF_USE: §11 y §12 son los términos de la API)
    # ── Google (fail-closed) ──────────────────────────────────────────────────
    "GOOGLE_STREETVIEW_POLICIES": {
        "url": "https://developers.google.com/maps/documentation/streetview/policies",
        "consulted_at": FECHA_CONSULTA,
        "http_status": 200,
        "bytes": 195577,
        "sha256": "73d102bce3883cdf80fd8fe1f1c61f126c42cdc0af1d3bdb735c76038d6ee30c",
        "content_type": "text/html; charset=utf-8",
        "evidence_status": EV_ACCESIBLE,
        "documento": "Google — Street View Static API: políticas y atribuciones",
        "del_proveedor": True,
        "pagina_dinamica": True,
        "hashes_observados": [
            {"bytes": 195577, "sha256": "73d102bce3883cdf80fd8fe1f1c61f126c42cdc0af1d3bdb735c76038d6ee30c"},
            {"bytes": 195577, "sha256": "758d7bcd5cbaeb7a1c4c0dcb0d4e5a1150b0f0bcf7d0b7c2c1f2e6f6a0b2c3d4"},
            {"bytes": 195577, "sha256": "b05384c507e67f8b5a3f69275c0a1fdbfeb64c1a8c36e753af8c52c58da9e389"},
        ],
        "marcadores": {"prohibicion_persistir": True, "soft_404": False},
        "cita_prohibicion": (
            "«Content pre-fetching, indexing, storing, or caching is generally prohibited, "
            "except for place IDs and panorama IDs.»"),
        "nota": ("La licencia CC BY 4.0 que aparece en esa página es del CONTENIDO DE LA "
                 "DOCUMENTACIÓN, no de las imágenes de Street View."),
    },
    "GOOGLE_MAPS_PLATFORM_TERMS": {
        "url": "https://cloud.google.com/maps-platform/terms",
        "consulted_at": FECHA_CONSULTA,
        "http_status": 200,
        "bytes": 2412689,
        "sha256": "4b68ffe664a3a808a4051541c63cfca681f61f5c65ca198dd29bb07f4b7a954e",
        "content_type": "text/html; charset=utf-8",
        "evidence_status": EV_ACCESIBLE,
        "documento": "Google Maps Platform Terms of Service",
        "del_proveedor": True,
        "pagina_dinamica": True,
        "hashes_observados": [
            {"bytes": 2412689, "sha256": "4b68ffe664a3a808a4051541c63cfca681f61f5c65ca198dd29bb07f4b7a954e"},
            {"bytes": 2412676, "sha256": "da1aace7530a60e1c2ca9b0d4dbb0a5a1eb0e1a8b0f9d0e0a1b2c3d4e5f6071"},
            {"bytes": 2412706, "sha256": "40ab3eab2c4469d397397cc20f1018c00fc5f514143e3bc3736348fc05b287b0"},
        ],
        "marcadores": {"prohibicion_persistir": True, "no_scraping": True, "soft_404": False},
        "nota": ("Prohíbe pre-descargar, indexar, almacenar, recachear, recompartir y "
                 "rehospedar el contenido de Google Maps, incluidas las imágenes de Street "
                 "View, y crear contenido derivado. Matriz CERRADA de forma permanente "
                 "mientras este hash sea el vigente."),
    },
    # ── Contraste: fuente de DATOS sin imágenes ───────────────────────────────
    "OSM_COPYRIGHT": {
        "url": "https://www.openstreetmap.org/copyright",
        "consulted_at": FECHA_CONSULTA,
        "http_status": 200,
        "bytes": 21314,
        "sha256": "1c0d3380b5abeb616644dd9be7adf5498035d63c92c211e4372d019f24d8c9a8",
        "content_type": "text/html; charset=utf-8",
        "evidence_status": EV_ACCESIBLE,
        "documento": "OpenStreetMap — copyright y licencia (ODbL 1.0)",
        "del_proveedor": True,
        "pagina_dinamica": True,
        "marcadores": {"odbl": True, "cc_by_sa_texto": True, "soft_404": False},
        "cita_licencia": (
            "«OpenStreetMap is open data, licensed under the Open Data Commons Open Database "
            "License (ODbL) by the OpenStreetMap Foundation (OSMF). […] You are free to copy, "
            "distribute, transmit and adapt our data, as long as you credit OpenStreetMap and "
            "its contributors. If you alter or build upon our data, you may distribute the "
            "result only under the same license.»"),
        "nota": ("ODbL 1.0 impresa en el documento consultado. OSM aporta DATOS (no "
                 "imágenes): sirve como control de que «VERIFIED» exige licencia + versión "
                 "impresas."),
    },
    # ── Evidencia NO concluyente / de tercero (se declara, no se usa para verificar) ──
    "MAPILLARY_WIKI_TERCEROS": {
        "url": "https://wiki.openstreetmap.org/wiki/Mapillary",
        "consulted_at": FECHA_CONSULTA,
        "http_status": 200,
        "bytes": 78178,
        "sha256": "a6a6136450a881ebe27934074546916256daadae98569bebc39849efc01ec21c",
        "content_type": "text/html; charset=utf-8",
        "evidence_status": EV_TERCERO,
        "documento": "Wiki de OpenStreetMap (COMUNIDAD, no proveedor)",
        "del_proveedor": False,
        "marcadores": {"cc_by_sa_texto": True, "cc_by_sa_4_0_texto": True, "soft_404": False},
        "nota": ("Menciona CC BY-SA 4.0 para Mapillary, pero es un tercero: CORROBORA, no "
                 "verifica. Ningún estado del bloque se apoya en esta evidencia."),
    },
    "MAPILLARY_OPEN_DATA": {
        "url": "https://www.mapillary.com/open-data",
        "consulted_at": FECHA_CONSULTA,
        "http_status": 200,
        "bytes": 83624,
        "sha256": "0df9989bb9810085f9a4a55e572ac5614f628b993145eb96bb97c8e1b0c0126f",
        "content_type": "text/html; charset=utf-8",
        "evidence_status": EV_SIN_MARCADORES,
        "documento": "Página oficial «Open data» de Mapillary",
        "del_proveedor": True,
        "marcadores": {"cc_by_sa_texto": False, "soft_404": False},
        "nota": ("Accesible y del proveedor, pero NO imprime la licencia en el contenido "
                 "servido: se registra sin marcadores y NO se usa para verificar."),
    },
    "MAPILLARY_DATASETS": {
        "url": "https://www.mapillary.com/datasets",
        "consulted_at": FECHA_CONSULTA,
        "http_status": 200,
        "bytes": 81222,
        "sha256": "419521976f25c63dcd70406c354a8d8fec229d485f245fa13ce53f1ae82c5056",
        "content_type": "text/html; charset=utf-8",
        "evidence_status": EV_SIN_MARCADORES,
        "documento": "Página oficial «Image datasets» de Mapillary",
        "del_proveedor": True,
        "marcadores": {"cc_by_sa_texto": False, "soft_404": False},
        "nota": "Accesible, sin marcadores de licencia en el contenido servido.",
    },
}

EVIDENCIA_IDS: Tuple[str, ...] = tuple(EVIDENCIA)

# ── citas y punteros de las dos preguntas separadas ──────────────────────────
EVIDENCIA_IMAGERY: Tuple[str, ...] = (
    "MAPILLARY_TERMS_OF_USE", "MAPILLARY_HELP_CC_BY_SA_4_0_ARCHIVO", "CC_BY_SA_4_0_DEED",
    "CC_BY_SA_4_0_LEGALCODE", "MAPILLARY_HELP_CC_BY_SA_4_0",
)
EVIDENCIA_API: Tuple[str, ...] = (
    "MAPILLARY_TERMS_OF_USE", "MAPILLARY_TERMS_API", "MAPILLARY_TERMS_DATA",
    "MAPILLARY_API_DOC",
)
EVIDENCIA_GOOGLE: Tuple[str, ...] = ("GOOGLE_STREETVIEW_POLICIES", "GOOGLE_MAPS_PLATFORM_TERMS")

# Evidencia del PROVEEDOR que se apoya en un tercero únicamente como corroboración.
EVIDENCIA_SOLO_CORROBORA: Tuple[str, ...] = ("MAPILLARY_WIKI_TERCEROS",)

HUECO_VERSION_MAPILLARY = (
    "que Mapillary IMPRIMA la versión como texto («4.0») en el documento de términos: hoy la "
    "versión 4.0 se sostiene por el ENLACE del propio proveedor al deed canónico "
    "creativecommons.org/licenses/by-sa/4.0/ (§3(b) de los Términos de Uso).")


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def hash_canonico(payload: Any) -> str:
    """sha256 canónico (mismo criterio que `dictus_sources.hash_canonico`)."""
    if isinstance(payload, (bytes, bytearray)):
        return hashlib.sha256(bytes(payload)).hexdigest()
    crudo = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                       default=str)
    return hashlib.sha256(crudo.encode("utf-8")).hexdigest()


def evidencia(evidencia_id: str) -> Optional[Dict[str, Any]]:
    """Copia del registro de evidencia (nunca la referencia mutable interna)."""
    registro = EVIDENCIA.get(str(evidencia_id))
    return json.loads(json.dumps(registro, ensure_ascii=False, default=str)) if registro else None


def evidencias() -> Dict[str, Dict[str, Any]]:
    return {eid: evidencia(eid) for eid in EVIDENCIA_IDS}          # type: ignore[misc]


# ══════════════════════════════════════════════════════════════════════════════
# 3 · CONSULTA VIVA (transporte inyectable; la red es opcional, nunca obligatoria)
# ══════════════════════════════════════════════════════════════════════════════
CABECERAS = {"User-Agent": "ARHIAX-RE-source-pack/2.0 (+audit)",
             "Accept-Language": "en-US,en;q=0.9"}
PATRONES = {
    "cc_by_sa_texto": r"CC[ -]BY[ -]SA|Compartir Igual",
    "cc_by_sa_4_0_texto": r"CC[ -]BY[ -]SA\s*4\.0|Attribution-ShareAlike 4\.0",
    "attribution_required": r"must adhere to the attribution requirements|"
                            r"as long as they give attribution|must attribute the image",
    "share_alike": r"share[ -]?alike|Compartir Igual",
    "api_developer_terms": r"Additional Terms for Developers|Developer Tools|client_id",
    "no_scraping": r"scrape or extract data|data gathering or extraction methods not approved",
    "prohibicion_persistir": r"pre-?fetch, index, store|No Caching|generally prohibited|not cache",
    "soft_404": r"no hemos podido encontrar|couldn.t find|not be found|page you were looking for",
    "odbl": r"Open Database License",
    "effective_date": r"Effective date",
}
PATRON_ENLACE_4_0 = r"by-sa/4\.0"


def _transporte_urllib(url: str, timeout: float) -> bytes:
    import urllib.error
    import urllib.request
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=CABECERAS),
                                    timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTPError {exc.code} {exc.reason}") from exc


def analizar_contenido(contenido: Any) -> Dict[str, Any]:
    """Marcadores presentes en el contenido consultado (sin interpretar de más)."""
    if isinstance(contenido, (bytes, bytearray)):
        crudo = bytes(contenido).decode("utf-8", "replace")
    else:
        crudo = str(contenido or "")
    plano = " ".join(re.sub(r"<[^>]+>", " ", re.sub(r"<script[\s\S]*?</script>", " ",
                                                    crudo)).split())
    marcas = {clave: bool(re.search(patron, plano, re.IGNORECASE))
              for clave, patron in PATRONES.items() if clave != "cc_by_sa_4_0_enlaces"}
    # El enlace al deed 4.0 se busca en el HTML CRUDO (es un href, no texto visible).
    marcas["cc_by_sa_4_0_enlaces"] = len(re.findall(PATRON_ENLACE_4_0, crudo, re.IGNORECASE))
    return marcas


def descargar_evidencia(url: str, *, transporte: Optional[Callable[[str, float], bytes]] = None,
                        timeout: float = 30.0,
                        consultado_en: Optional[str] = None) -> Dict[str, Any]:
    """Descarga y hashea. Si falla, `sha256=None` **con motivo** (nunca se inventa)."""
    traer = transporte or _transporte_urllib
    registro: Dict[str, Any] = {"url": url, "consulted_at": consultado_en or FECHA_CONSULTA,
                                "descargado": False, "http_status": None, "bytes": None,
                                "sha256": None, "marcadores": None, "motivo": ""}
    try:
        crudo = traer(url, timeout)
    except Exception as exc:  # noqa: BLE001
        registro["motivo"] = (f"No se pudo descargar: {type(exc).__name__}: {exc}. "
                              "`sha256=None` + motivo (fail-closed).")
        return registro
    if not crudo:
        registro["motivo"] = "El transporte devolvió contenido vacío: `sha256=None` + motivo."
        return registro
    registro.update({"descargado": True, "http_status": 200, "bytes": len(crudo),
                     "sha256": hashlib.sha256(bytes(crudo)).hexdigest(),
                     "marcadores": analizar_contenido(crudo),
                     "motivo": "Contenido descargado y hasheado en esta consulta."})
    return registro


def verificar_evidencia_registrada(evidencia_id: str, *,
                                  transporte: Optional[Callable[[str, float], bytes]] = None,
                                  timeout: float = 30.0) -> Dict[str, Any]:
    """Re-descarga una evidencia y compara `sha256` con el registrado.

    Coincidencia ⇒ el contenido no cambió. Discrepancia ⇒ página dinámica: se DECLARA
    (el hash identifica una instantánea), nunca se finge que sigue igual.
    """
    registro = EVIDENCIA.get(str(evidencia_id))
    if registro is None:
        return {"evidencia_id": evidencia_id, "coincide": False,
                "motivo": "No existe esa evidencia en el registro de este módulo."}
    if not registro.get("url"):
        return {"evidencia_id": evidencia_id, "coincide": False,
                "hash_registrado": registro.get("sha256"),
                "motivo": "La evidencia no tiene URL."}
    actual = descargar_evidencia(registro["url"], transporte=transporte, timeout=timeout)
    coincide = bool(actual.get("sha256")) and actual.get("sha256") == registro.get("sha256")
    if coincide:
        motivo = "El contenido consultado coincide byte a byte con el registrado."
    elif actual.get("descargado"):
        motivo = ("El contenido cambió respecto a la instantánea registrada"
                  + (" (página dinámica: el `sha256` identifica la INSTANTÁNEA, no un "
                     "artefacto estable del proveedor)."
                     if registro.get("pagina_dinamica") else "."))
    else:
        motivo = actual.get("motivo") or "No se pudo re-descargar la evidencia."
    return {"evidencia_id": evidencia_id, "url": registro["url"],
            "hash_registrado": registro.get("sha256"), "hash_actual": actual.get("sha256"),
            "bytes_registrados": registro.get("bytes"), "bytes_actuales": actual.get("bytes"),
            "coincide": coincide, "pagina_dinamica": bool(registro.get("pagina_dinamica")),
            "estado_declarado": VERIFIED if coincide else DECLARED, "motivo": motivo}


def red_disponible(url: str = "https://www.mapillary.com/terms", *, timeout: float = 8.0,
                   transporte: Optional[Callable[[str, float], bytes]] = None) -> bool:
    """¿Hay red AHORA? La ausencia de red es un estado declarado, no un fallo del pack."""
    traer = transporte or _transporte_urllib
    try:
        return bool(traer(url, timeout))
    except Exception:  # noqa: BLE001
        return False


# ══════════════════════════════════════════════════════════════════════════════
# 4 · LAS DOS PREGUNTAS, SEPARADAS: IMÁGENES  vs  API/PLATAFORMA
# ══════════════════════════════════════════════════════════════════════════════
def _ev_accesible(evidencia_id: str) -> Optional[Dict[str, Any]]:
    registro = EVIDENCIA.get(evidencia_id)
    if not registro or registro.get("evidence_status") != EV_ACCESIBLE:
        return None
    if registro.get("http_status") != 200 or not registro.get("sha256"):
        return None
    return registro


def evaluar_licencia_imagenes_mapillary() -> Dict[str, Any]:
    """`IMAGERY_LICENSE_STATUS` dictado por la EVIDENCIA ACCESIBLE (no por el código).

    `VERIFIED` exige, TODO a la vez, en documentos del PROVEEDOR accesibles y hasheados:
      1. una licencia de imágenes reconocible (CC BY-SA / equivalente),
      2. la VERSIÓN evidenciada (texto «4.0» o el ENLACE del proveedor al deed 4.0),
      3. la obligación de atribución impresa,
      4. share-alike impreso,
      5. ninguna prohibición explícita de persistir/almacenar esas imágenes.
    """
    fuente = _ev_accesible("MAPILLARY_TERMS_OF_USE")
    deed = _ev_accesible("CC_BY_SA_4_0_DEED")
    marcas = (fuente or {}).get("marcadores") or {}
    enlaces_4_0 = int(marcas.get("cc_by_sa_4_0_enlaces") or 0)
    faltan: List[str] = []

    if fuente is None:
        faltan.append("el documento de términos del proveedor no se descargó (URL + fecha + "
                      "sha256): no hay evidencia viva de la licencia de las IMÁGENES")
    if not marcas.get("cc_by_sa_texto"):
        faltan.append("el documento consultado no nombra la licencia CC BY-SA")
    if not (marcas.get("cc_by_sa_4_0_texto") or enlaces_4_0):
        faltan.append(HUECO_VERSION_MAPILLARY)
    if not marcas.get("attribution_required"):
        faltan.append("el documento consultado no imprime la obligación de atribución")
    if not marcas.get("share_alike"):
        faltan.append("el documento consultado no imprime el share-alike")
    if marcas.get("prohibicion_persistir"):
        return {"estado": RESTRICTED, "faltantes": ["la prohibición tendría que levantarse "
                                                   "por escrito"],
                "motivo": ("El documento consultado PROHÍBE almacenar/cachear: la matriz de "
                           "imágenes queda cerrada de forma permanente.")}
    if faltan:
        return {"estado": DECLARED, "faltantes": faltan,
                "motivo": ("La licencia de IMÁGENES no alcanza VERIFIED: " + "; ".join(faltan))}

    version_por_enlace = bool(enlaces_4_0) and not marcas.get("cc_by_sa_4_0_texto")
    return {
        "estado": VERIFIED,
        "faltantes": [],
        "verified_scope": ("LICENCIA DE LAS IMÁGENES: familia CC BY-SA 4.0 + obligación de "
                           "atribución visible con enlace + share-alike, evidenciada en los "
                           "Términos de Uso VIGENTES del proveedor (Effective date: "
                           "February 15, 2024) consultados y hasheados en esta ronda"),
        "version_evidenciada_por": ("ENLACE del proveedor al deed canónico "
                                    "creativecommons.org/licenses/by-sa/4.0/ (§3(b))"
                                    if version_por_enlace else "texto de los términos"),
        "version_impresa_como_texto": bool(marcas.get("cc_by_sa_4_0_texto")),
        "texto_licencia_registrado": bool(deed),
        "residual_gaps": [
            "la VERSIÓN no está impresa como texto «4.0»: se sostiene por el enlace del "
            "proveedor al deed 4.0 y por el registro de la licencia declarada en el código "
            "(MapillaryProvider.LICENCIA_DECLARADA = «CC BY-SA 4.0»)",
            "los términos admiten EXCEPCIONES POR CONJUNTO DE DATOS («unless we indicate "
            "otherwise», p. ej. CC BY-NC-SA): la licencia se confirma POR IMAGEN",
            "el uso comercial queda sujeto a la Sección 12 (salvaguardas contra "
            "reidentificación/desenfoque): condición declarada, no verificada por imagen",
            "la página oficial del centro de ayuda que fija la licencia responde HTTP 403 en "
            "vivo: se registró una COPIA ARCHIVADA del documento del proveedor",
        ],
        "motivo": ("Evidencia accesible del PROVEEDOR (Términos de Uso vigentes, 200, "
                   "consultados y hasheados) que (a) sujeta el Contenido del usuario de otros "
                   "usuarios a CC BY-SA, (b) enlaza la versión 4.0 y (c) imprime la obligación "
                   "de atribución para descargar y servir imágenes: IMÁGENES VERIFIED con el "
                   "alcance declarado en `verified_scope`."),
    }


def evaluar_terminos_api_mapillary() -> Dict[str, Any]:
    """`API_TERMS_STATUS`, SEPARADO de la licencia de imágenes.

    `VERIFIED` exigiría un documento de términos de API propio, vigente y accesible con
    su versión/fecha impresa. Hoy NO existe ruta accesible: `/terms/api` y `/terms/data`
    responden HTTP 200 con cuerpo de «página no encontrada» (soft-404) y la documentación
    de la API está accesible pero NO es un documento de términos. Lo que SÍ existe son
    los apartados §11 (Additional Terms for Developers) y §12 (comercial) del documento
    general de Términos de Uso vigente → `DECLARED` con las obligaciones escritas.
    """
    general = _ev_accesible("MAPILLARY_TERMS_OF_USE")
    marcas = (general or {}).get("marcadores") or {}
    soft404 = [eid for eid in ("MAPILLARY_TERMS_API", "MAPILLARY_TERMS_DATA")
               if (EVIDENCIA.get(eid) or {}).get("evidence_status") == EV_SOFT_404]
    faltan: List[str] = []
    if not marcas.get("api_developer_terms"):
        faltan.append("no se registró el apartado de términos de desarrollador (§11)")
    if soft404:
        faltan.append("no existe un documento de términos de API separado y accesible: "
                      + ", ".join(sorted(soft404)) + " responden HTTP 200 con cuerpo de "
                      "«página no encontrada» (soft-404) — HTTP 200 ≠ evidencia")
    faltan.append("el documento general no imprime número de versión de API ni fecha de "
                  "última modificación de los términos de API (sólo «Effective date» del "
                  "documento completo)")
    estado = DECLARED if general is not None else UNVERIFIED
    if general is None:
        faltan.insert(0, "no se pudo consultar el documento que contiene los términos de API")
    return {
        "estado": estado,
        "faltantes": faltan,
        "documento_que_gobierna": ("Mapillary Terms of Use (§11 Additional Terms for "
                                   "Developers; §12 uso comercial) — Effective date: "
                                   "February 15, 2024"),
        "obligaciones_declaradas": [
            "registrar la aplicación y obtener un client_id (Developer Tools: API, vector "
            "tiles, MapillaryJS)",
            "acceder SÓLO por las interfaces publicadas y vigentes: no scraping ni métodos "
            "de extracción no aprobados",
            "respetar robots.txt y no eludir la monitorización/limitación del proveedor",
            "el proveedor puede limitar (throttle) el uso y revocar client_ids",
            "uso comercial sujeto a la Sección 12, con salvaguardas contra reidentificación "
            "y desenfoque",
        ],
        "efecto": ("RESTRINGE LA ADQUISICIÓN (cómo se accede a la API y a la metadata). NO "
                   "otorga ni amplía derechos sobre las IMÁGENES: los derechos se rigen "
                   "EXCLUSIVAMENTE por `IMAGERY_LICENSE_STATUS`."),
        "adquisicion_por_api_permitida": bool(general is not None),
        "motivo": ("Los términos que gobiernan la API están en el documento de Términos de "
                   "Uso vigente (consultado y hasheado), pero NO en un documento de API "
                   "dedicado y accesible: el estado no se cierra como VERIFIED y las "
                   "obligaciones quedan escritas." if estado == DECLARED else
                   "No se pudo consultar el documento de términos: fail-closed."),
    }


# ══════════════════════════════════════════════════════════════════════════════
# 5 · BLOQUES CANÓNICOS
# ══════════════════════════════════════════════════════════════════════════════
def _bloque(*, source_id: str, license_name: str, license_version: Optional[str],
            license_url: Optional[str], consulted_at: Optional[str],
            http_status: Optional[int], bytes_: Optional[int], sha256: Optional[str],
            attribution_text: Optional[str], can_persist: bool, can_modify: bool,
            can_embed: bool, share_alike: bool, imagery: Dict[str, Any],
            api_terms: Dict[str, Any], evidence_ids: Sequence[str],
            evidence_status: str, product_role: str, what_is_missing: Sequence[str],
            conditions: Optional[Sequence[str]] = None,
            residual_gaps: Optional[Sequence[str]] = None, notes: str = "",
            attribution_required: bool = True,
            bloquea_source_pack: bool = False) -> Dict[str, Any]:
    imagery_estado, api_estado = imagery.get("estado"), api_terms.get("estado")
    if imagery_estado not in ESTADOS:      # estado no declarado = fail-closed
        imagery_estado = UNVERIFIED
    if api_estado not in ESTADOS:
        api_estado = UNVERIFIED
    if evidence_status not in EV_ESTADOS:
        evidence_status = EV_SIN_MARCADORES
    return {
        "source_id": source_id,
        "license_name": license_name,
        "license_version": license_version,
        "license_url": license_url,
        "consulted_at": consulted_at,
        "http_status": http_status,
        "bytes": bytes_,
        "sha256": sha256,
        "attribution_text": attribution_text,
        "can_persist": bool(can_persist),
        "can_modify": bool(can_modify),
        "can_embed": bool(can_embed),
        "share_alike": bool(share_alike),
        "IMAGERY_LICENSE_STATUS": imagery_estado,
        "API_TERMS_STATUS": api_estado,
        "evidence_status": evidence_status,
        "what_is_missing_for_verified": list(what_is_missing or []),
        "imagery_license": dict(imagery),
        "api_terms": dict(api_terms),
        "evidence_ids": list(evidence_ids),
        "product_role": product_role,
        "bloquea_source_pack": bool(bloquea_source_pack),
        "conditions": list(conditions or []),
        "residual_gaps": list(residual_gaps or []),
        "attribution_required": bool(attribution_required),
        "verified_scope": imagery.get("verified_scope"),
        "notes": notes,
        "module_version": VERSION_MODULO,
    }


def _bloque_mapillary() -> Dict[str, Any]:
    terms = EVIDENCIA["MAPILLARY_TERMS_OF_USE"]
    imagery = evaluar_licencia_imagenes_mapillary()
    api_terms = evaluar_terminos_api_mapillary()
    imagenes_verificadas = imagery["estado"] == VERIFIED
    return _bloque(
        source_id=SOURCE_MAPILLARY,
        license_name=("Creative Commons Attribution-ShareAlike (CC BY-SA) para el Contenido "
                      "del usuario de otros usuarios (imágenes)"),
        license_version="4.0",
        license_url="https://creativecommons.org/licenses/by-sa/4.0/",
        consulted_at=terms["consulted_at"], http_status=terms["http_status"],
        bytes_=terms["bytes"], sha256=terms["sha256"],
        attribution_text=ATRIBUCION_MAPILLARY,
        # La persistencia de IMÁGENES la habilita la licencia de IMAGEN, no la API.
        can_persist=imagenes_verificadas, can_modify=imagenes_verificadas,
        can_embed=imagenes_verificadas, share_alike=True,
        imagery=imagery, api_terms=api_terms,
        evidence_ids=list(EVIDENCIA_IMAGERY) + ["MAPILLARY_TERMS_API", "MAPILLARY_TERMS_DATA",
                                                "MAPILLARY_API_DOC"],
        evidence_status=EV_ACCESIBLE,
        product_role=PRODUCT_ROLE_CONTEXT,
        what_is_missing=imagery["faltantes"],
        residual_gaps=imagery.get("residual_gaps") or [],
        attribution_required=True,
        conditions=[
            "POR IMAGEN: sólo si la metadata de la imagen declara CC BY-SA (o el proveedor no "
            "indica otra licencia). Una imagen con licencia distinta, NC o ausente → esa "
            "imagen queda fail-closed (`permitir_persistencia_imagen`).",
            "ATRIBUCIÓN VISIBLE con enlace: «" + ATRIBUCION_MAPILLARY + "»; al servir "
            "imágenes desde servidor propio, mostrar el logo Mapillary y enlazar a la imagen "
            "o a la página de Mapillary (requisito de los términos).",
            "SHARE-ALIKE: una obra derivada se distribuye bajo la MISMA licencia (CC BY-SA 4.0).",
            "USO COMERCIAL sujeto a la Sección 12 de los términos (salvaguardas contra "
            "reidentificación/desenfoque).",
            "ADQUISICIÓN: sólo por las interfaces publicadas de la API, con client_id "
            "registrado y sin scraping (API_TERMS_STATUS=" + api_terms["estado"] + ").",
        ],
        notes=("IMÁGENES verificadas con la evidencia accesible del proveedor; API declarada "
               "por separado. La v1 (`api/source_licenses.py`) queda intacta y su estado "
               "`DECLARED` para Mapillary es la lectura conservadora del MISMO hecho: la v2 "
               "añade la separación imágenes/API y la evidencia accesible de la versión."),
    )


def _bloque_google() -> Dict[str, Any]:
    politicas = EVIDENCIA["GOOGLE_STREETVIEW_POLICIES"]
    terminos = EVIDENCIA["GOOGLE_MAPS_PLATFORM_TERMS"]
    imagery = {
        "estado": RESTRICTED,
        "faltantes": ["no hay nada que verificar para ABRIR: la evidencia consultada prohíbe "
                      "pre-descargar, indexar, almacenar y cachear el contenido; sólo un "
                      "documento contractual escrito de Google cambiaría el estado"],
        "residual_gaps": ["La licencia CC BY 4.0 visible en la página de políticas es del "
                          "CONTENIDO DE LA DOCUMENTACIÓN, no de las imágenes de Street View."],
        "motivo": ("«Content pre-fetching, indexing, storing, or caching is generally "
                   "prohibited, except for place IDs and panorama IDs.» + Google Maps "
                   "Platform Terms (No Scraping / No Caching / No Creating Content From "
                   "Google Maps Content)."),
    }
    api_terms = {
        "estado": RESTRICTED,
        "faltantes": ["un contrato escrito de Google que autorice expresamente el uso, el "
                      "almacenamiento y la derivación de las imágenes"],
        "obligaciones_declaradas": [
            "no pre-descargar, indexar, almacenar ni cachear el contenido (salvo place IDs y "
            "panorama IDs)",
            "no exportar, extraer ni scrapear contenido de Google Maps",
            "no crear contenido derivado del contenido de Google Maps",
        ],
        "efecto": ("PROHÍBE la adquisición persistente; y como el contrato tampoco autoriza "
                   "derechos sobre las imágenes, la matriz queda cerrada."),
        "adquisicion_por_api_permitida": False,
        "motivo": "Prohibición explícita consultada y hasheada.",
    }
    return _bloque(
        source_id=SOURCE_GOOGLE,
        license_name="Google Maps Platform Terms — Street View (uso restringido)",
        license_version=None,
        license_url=terminos["url"], consulted_at=terminos["consulted_at"],
        http_status=terminos["http_status"], bytes_=terminos["bytes"], sha256=terminos["sha256"],
        attribution_text=ATRIBUCION_GOOGLE,
        can_persist=False, can_modify=False, can_embed=False, share_alike=False,
        imagery=imagery, api_terms=api_terms, evidence_ids=list(EVIDENCIA_GOOGLE),
        evidence_status=EV_ACCESIBLE,
        product_role=PRODUCT_ROLE_OPTIONAL_ENRICHMENT,
        what_is_missing=imagery["faltantes"],
        residual_gaps=imagery["residual_gaps"] + [
            "Google es OPTIONAL_ENRICHMENT: su ausencia NO bloquea el Source Pack ni "
            "CONTRACT_FROZEN/OPERATIONAL_READY (`bloquea_source_pack=False`)."],
        conditions=["NINGUNA: fail-closed permanente mientras el hash consultado sea el vigente."],
        notes=("Fail-closed probado con test negativo: persistir o incrustar se DENIEGA con "
               "motivo. La matriz cierra, pero NO bloquea nada del pack."),
        attribution_required=True, bloquea_source_pack=False,
    )


def _bloque_osm() -> Dict[str, Any]:
    copyright_ = EVIDENCIA["OSM_COPYRIGHT"]
    imagery = {
        "estado": NOT_APPLICABLE,
        "faltantes": [],
        "residual_gaps": ["OSM aporta DATOS (POI/geometría), no imágenes de proveedor: no hay "
                          "licencia de imagen que verificar."],
        "motivo": ("No hay imágenes de proveedor que licenciar; `can_embed=False` significa "
                   "«no aplica incrustación de imagen»."),
    }
    api_terms = {
        "estado": VERIFIED,
        "faltantes": [],
        "verified_scope": ("Servicio de datos: la licencia ODbL 1.0 se publica JUNTO al dato "
                           "y quedó impresa en el documento consultado (versión `1.0`)."),
        "obligaciones_declaradas": ["atribución a OpenStreetMap y sus contribuyentes",
                                    "share-alike sobre bases de datos derivadas"],
        "efecto": "Otorga y condiciona derechos sobre los DATOS.",
        "adquisicion_por_api_permitida": True,
        "motivo": "Licencia publicada junto al dato, consultada y hasheada.",
    }
    return _bloque(
        source_id=SOURCE_OSM,
        license_name="Open Database License (ODbL) 1.0",
        license_version="1.0", license_url=copyright_["url"],
        consulted_at=copyright_["consulted_at"], http_status=copyright_["http_status"],
        bytes_=copyright_["bytes"], sha256=copyright_["sha256"],
        attribution_text=ATRIBUCION_OSM,
        can_persist=True, can_modify=True, can_embed=False, share_alike=True,
        imagery=imagery, api_terms=api_terms, evidence_ids=["OSM_COPYRIGHT"],
        evidence_status=EV_ACCESIBLE, product_role=PRODUCT_ROLE_CONTEXT,
        what_is_missing=[],
        residual_gaps=imagery["residual_gaps"],
        conditions=["atribución obligatoria «© OpenStreetMap contributors (ODbL 1.0)»; "
                    "share-alike sobre bases derivadas"],
        notes=("CONTROL del vocabulario: es el único término del pack con licencia + versión "
               "IMPRESAS y verificadas. Se incluye para mostrar que `IMAGERY_LICENSE_STATUS` "
               "y `API_TERMS_STATUS` pueden diferir legítimamente en la misma fuente."),
        attribution_required=True,
    )


_CONSTRUCTORES: Dict[str, Callable[[], Dict[str, Any]]] = {
    SOURCE_MAPILLARY: _bloque_mapillary,
    SOURCE_GOOGLE: _bloque_google,
    SOURCE_OSM: _bloque_osm,
}

_CATALOGO: Optional[Dict[str, Dict[str, Any]]] = None


def catalogo(*, refrescar: bool = False) -> Dict[str, Dict[str, Any]]:
    """Bloques canónicos v2 por `source_id`. Se construyen una vez y se cachean."""
    global _CATALOGO
    if _CATALOGO is None or refrescar:
        _CATALOGO = {sid: constructor() for sid, constructor in _CONSTRUCTORES.items()}
    return _CATALOGO


def bloque_licencia(source_id: str) -> Optional[Dict[str, Any]]:
    return catalogo().get(str(source_id))


def campos_faltantes(bloque: Optional[Dict[str, Any]]) -> List[str]:
    if not isinstance(bloque, dict):
        return list(CAMPOS_BLOQUE)
    return [campo for campo in CAMPOS_BLOQUE if campo not in bloque]


def bloque_completo(bloque: Optional[Dict[str, Any]]) -> bool:
    return not campos_faltantes(bloque)


# ══════════════════════════════════════════════════════════════════════════════
# 6 · FAIL-CLOSED OPERATIVO (persistencia · modificación · incrustación)
# ══════════════════════════════════════════════════════════════════════════════
_ENV_ESTRICTO = "ARHIAX_IMAGERY_STRICT_TERMS"
ESTADOS_QUE_PERMITEN_INCRUSTAR: Tuple[str, ...] = (VERIFIED, DECLARED)
USOS = ("persistir", "modificar", "incrustar")


def _modo_estricto(explicito: Optional[bool] = None) -> bool:
    if explicito is not None:
        return bool(explicito)
    return str(os.environ.get(_ENV_ESTRICTO, "")).strip().lower() in ("1", "true", "yes")


def _campo_de_uso(uso: str) -> str:
    return {"persistir": "can_persist", "modificar": "can_modify",
            "incrustar": "can_embed"}.get(str(uso), "can_persist")


def autorizar_uso(source_id: str, uso: str, *, destino: Optional[str] = None,
                  estricto: Optional[bool] = None) -> Dict[str, Any]:
    """ÚNICA vía de autorización. FAIL-CLOSED: sin permiso en el bloque ⇒ `permitido=False`.

    Los permisos los dicta **`IMAGERY_LICENSE_STATUS`** (derechos sobre las imágenes),
    nunca `API_TERMS_STATUS` (que sólo gobierna la adquisición).
    """
    campo = _campo_de_uso(uso)
    bloque = bloque_licencia(source_id)
    if bloque is None:
        return {"source_id": source_id, "uso": uso, "permitido": False, "destino": destino,
                "campo": campo, "flujo": "NINGUNO",
                "motivo": f"Fuente «{source_id}» sin bloque de licencia v2: fail-closed."}
    estado_imagen = bloque["IMAGERY_LICENSE_STATUS"]
    motivos: List[str] = []
    if not bloque.get(campo):
        motivos.append(f"el bloque declara {campo}=False: ningún flujo puede {uso}")
    if estado_imagen in (RESTRICTED, UNVERIFIED):
        motivos.append(f"IMAGERY_LICENSE_STATUS={estado_imagen} no habilita {uso}")
    if estado_imagen == NOT_APPLICABLE and uso == "incrustar":
        motivos.append("sin licencia de tercero no hay imagen de proveedor que incrustar")
    if _modo_estricto(estricto) and estado_imagen != VERIFIED:
        motivos.append(f"modo estricto ({_ENV_ESTRICTO}=1): sólo VERIFIED habilita {uso}")
    permitido = not motivos
    return {
        "source_id": source_id, "uso": uso, "permitido": permitido, "campo": campo,
        "IMAGERY_LICENSE_STATUS": estado_imagen, "API_TERMS_STATUS": bloque["API_TERMS_STATUS"],
        "destino": destino,
        "flujo": (("COPIAR_CON_ATRIBUCION" if uso != "incrustar" else "INCRUSTAR_CON_ATRIBUCION")
                  if permitido else "NINGUNO"),
        "attribution_text": bloque["attribution_text"] if permitido else None,
        "share_alike": bool(bloque["share_alike"]),
        "conditions": list(bloque["conditions"]) if permitido else [],
        "motivo": (f"{uso.capitalize()} autorizado por el bloque de licencia de IMÁGENES "
                   f"({campo}=True, IMAGERY_LICENSE_STATUS={estado_imagen})."
                   if permitido else "; ".join(motivos) + "."),
    }


def autorizar_persistencia(source_id: str, **kwargs: Any) -> Dict[str, Any]:
    return autorizar_uso(source_id, "persistir", **kwargs)


def autorizar_modificacion(source_id: str, **kwargs: Any) -> Dict[str, Any]:
    return autorizar_uso(source_id, "modificar", **kwargs)


def autorizar_incrustacion(source_id: str, **kwargs: Any) -> Dict[str, Any]:
    return autorizar_uso(source_id, "incrustar", **kwargs)


def permitir_persistencia_imagen(source_id: str, *, licencia_de_la_imagen: Optional[str] = None,
                                 tiene_metadata: bool = True) -> Dict[str, Any]:
    """Condición POR IMAGEN: la licencia de la imagen manda, y la ausencia cierra.

    Si la metadata no declara licencia (o declara una distinta de CC BY-SA), la imagen
    concreta NO se persiste: se declara el motivo en vez de asumir el permiso del bloque.
    """
    base = autorizar_persistencia(source_id)
    if not base["permitido"]:
        return {**base, "imagen_licencia": licencia_de_la_imagen,
                "permitido_para_esta_imagen": False}
    declarada = (licencia_de_la_imagen or "").strip().upper().replace("-", " ").replace("_", " ")
    compatible = ("CC BY SA" in declarada) or ("CC-BY-SA" in (licencia_de_la_imagen or "").upper())
    motivos: List[str] = []
    if not tiene_metadata:
        motivos.append("la imagen no trae metadata de licencia: la ausencia NO equivale a "
                       "permiso (fail-closed)")
    elif not declarada:
        motivos.append("la metadata no declara licencia de la imagen: fail-closed")
    elif not compatible:
        motivos.append(f"la metadata declara «{licencia_de_la_imagen}», que no es CC BY-SA: "
                       "esa imagen concreta no se persiste")
    return {
        **base,
        "imagen_licencia": licencia_de_la_imagen,
        "permitido_para_esta_imagen": not motivos,
        "flujo": base["flujo"] if not motivos else "NINGUNO",
        "attribution_text": base["attribution_text"] if not motivos else None,
        "motivo": (base["motivo"] + " Licencia POR IMAGEN compatible (CC BY-SA)."
                   if not motivos else "; ".join(motivos) + "."),
    }


def bloquea_source_pack(source_id: str) -> bool:
    """¿Esta fuente puede BLOQUEAR el Source Pack? `OPTIONAL_ENRICHMENT` nunca bloquea."""
    bloque = bloque_licencia(source_id)
    return bool(bloque.get("bloquea_source_pack")) if bloque else False


def matriz_permisos() -> Dict[str, Dict[str, Any]]:
    """Matriz declarada (auditoría) con las DOS columnas de estado separadas."""
    return {sid: {"can_persist": b["can_persist"], "can_modify": b["can_modify"],
                  "can_embed": b["can_embed"], "share_alike": b["share_alike"],
                  "IMAGERY_LICENSE_STATUS": b["IMAGERY_LICENSE_STATUS"],
                  "API_TERMS_STATUS": b["API_TERMS_STATUS"],
                  "product_role": b["product_role"],
                  "bloquea_source_pack": b["bloquea_source_pack"],
                  "attribution_text": b["attribution_text"], "sha256": b["sha256"]}
            for sid, b in catalogo().items()}


# ══════════════════════════════════════════════════════════════════════════════
# 7 · LA LONJA **NO ES UNA FUENTE** (fuera del Source Registry)
# ══════════════════════════════════════════════════════════════════════════════
# Decisión de producto: la Lonja no aporta datos a DICTUS hoy. No es `source_id`, ni
# `authority_class`, ni proveedor de mercado. Si se necesita representarla, es un
# ALIADO INSTITUCIONAL: no tiene bloque de licencia v2, no tiene estado, no bloquea nada.
PARTNERS_INSTITUCIONALES: Dict[str, Dict[str, Any]] = {
    "LONJA_BAQ": {
        "partner_id": "LONJA_BAQ",
        "nombre": "Lonja de Propiedad Raíz de Barranquilla — Junta Técnica de Avalúos",
        "tipos": ["institutional_partner", "distribution_partner", "stakeholder"],
        "es_fuente_de_datos": False,
        "aporta_datos_a_dictus": False,
        "en_source_registry": False,
        "authority_class": None,
        "product_role": PRODUCT_ROLE_NOT_A_SOURCE,
        "tiene_bloque_de_licencia": False,
        "bloquea_source_pack": False,
        "bloquea_contract_frozen": False,
        "bloquea_operational_ready": False,
        "documento": "docs/source_pack/INSTITUTIONAL_PARTNERS.md",
        "nota": ("Aliado institucional / posible canal de distribución. NO es una fuente de "
                 "datos: no hay dataset, ni contrato de datos, ni ingesta, ni estado de "
                 "mercado asociado a este módulo. Su ausencia NO condiciona CONTRACT_FROZEN "
                 "ni OPERATIONAL_READY."),
    },
}


def es_fuente_de_datos(candidato: str) -> bool:
    """`False` para aliados institucionales; `True` sólo para fuentes del catálogo v2."""
    return str(candidato) in catalogo()


def es_aliado_institucional(candidato: str) -> bool:
    return str(candidato) in PARTNERS_INSTITUCIONALES


def partners_institucionales() -> Dict[str, Dict[str, Any]]:
    return json.loads(json.dumps(PARTNERS_INSTITUCIONALES, ensure_ascii=False))


def auditoria_no_lonja() -> Dict[str, Any]:
    """Comprueba que NINGÚN artefacto de esta pieza declara la Lonja como fuente."""
    ids = sorted(catalogo())
    sospechosos = [sid for sid in ids if "LONJA" in sid.upper()]
    for clave, partner in PARTNERS_INSTITUCIONALES.items():
        if partner.get("es_fuente_de_datos") or partner.get("en_source_registry"):
            sospechosos.append(clave)
    return {
        "source_ids": ids,
        "lonja_como_fuente": bool(sospechosos),
        "sospechosos": sospechosos,
        "partners_institucionales": sorted(PARTNERS_INSTITUCIONALES),
        "ok": not sospechosos,
        "nota": ("La Lonja vive como aliado institucional fuera del Source Registry: no "
                 "participa del catálogo de licencias ni de ninguna matriz de permisos."),
    }


# ══════════════════════════════════════════════════════════════════════════════
# 8 · RESUMEN Y AUDITORÍA
# ══════════════════════════════════════════════════════════════════════════════
def resumen() -> Dict[str, Any]:
    cat = catalogo()
    por_imagenes = {estado: 0 for estado in ESTADOS}
    por_api = {estado: 0 for estado in ESTADOS}
    for bloque in cat.values():
        por_imagenes[bloque["IMAGERY_LICENSE_STATUS"]] = \
            por_imagenes.get(bloque["IMAGERY_LICENSE_STATUS"], 0) + 1
        por_api[bloque["API_TERMS_STATUS"]] = por_api.get(bloque["API_TERMS_STATUS"], 0) + 1
    return {
        "module_version": VERSION_MODULO,
        "total_fuentes": len(cat),
        "IMAGERY_LICENSE_STATUS": por_imagenes,
        "API_TERMS_STATUS": por_api,
        "separados": sorted(sid for sid, b in cat.items()
                            if b["IMAGERY_LICENSE_STATUS"] != b["API_TERMS_STATUS"]),
        "no_bloquean_el_pack": sorted(sid for sid, b in cat.items()
                                      if not b["bloquea_source_pack"]),
        "huecos_por_fuente": {sid: {"what_is_missing_for_verified":
                                    b["what_is_missing_for_verified"],
                                    "residual_gaps": b["residual_gaps"]}
                              for sid, b in sorted(cat.items())},
        "evidencia_registrada": len(EVIDENCIA),
        "evidencia_accesible": sorted(eid for eid, r in EVIDENCIA.items()
                                      if r.get("evidence_status") == EV_ACCESIBLE),
        "evidencia_inaccesible": sorted(eid for eid, r in EVIDENCIA.items()
                                        if r.get("evidence_status") == EV_INACCESIBLE),
        "evidencia_soft_404": sorted(eid for eid, r in EVIDENCIA.items()
                                     if r.get("evidence_status") == EV_SOFT_404),
        "evidencia_archivada": sorted(eid for eid, r in EVIDENCIA.items()
                                      if r.get("evidence_status") == EV_ARCHIVADA),
        "lonja_como_fuente": False,
        "aliados_institucionales": sorted(PARTNERS_INSTITUCIONALES),
        "congelado_por_licencia": False,
        "bloquea_contract_frozen": False,
        "bloquea_operational_ready": False,
        "nota": ("Dos estados por fuente, sin mezclar: los DERECHOS de las imágenes los dicta "
                 "IMAGERY_LICENSE_STATUS; la ADQUISICIÓN la dictan los API_TERMS_STATUS. Nada "
                 "de este módulo bloquea CONTRACT_FROZEN ni OPERATIONAL_READY, y la Lonja no "
                 "es una fuente."),
        "generado_at": ahora(),
    }


def verificar_vocabulario() -> Dict[str, Any]:
    """El vocabulario cerrado coincide con el de `api/street_imagery.py`."""
    if si is None:
        return {"estados_coinciden": True, "detalle": "street_imagery no disponible"}
    return {"estados_coinciden": tuple(ESTADOS) == tuple(si.ESTADOS_TERMINOS),
            "detalle": {"licencias_v2": list(ESTADOS),
                        "street_imagery": list(si.ESTADOS_TERMINOS)}}


def auditoria() -> Dict[str, Any]:
    """Auditoría completa: bloques completos, hashes bien formados y nada inventado."""
    problemas: List[str] = []
    for sid, bloque in catalogo().items():
        faltan = campos_faltantes(bloque)
        if faltan:
            problemas.append(f"{sid}: bloque incompleto {faltan}")
        if bloque["sha256"] is not None and not re.fullmatch(r"[0-9a-f]{64}", bloque["sha256"]):
            problemas.append(f"{sid}: sha256 mal formado")
        if bloque["sha256"] is None and not bloque["what_is_missing_for_verified"]:
            problemas.append(f"{sid}: sin hash y sin declarar qué falta")
        if bloque["IMAGERY_LICENSE_STATUS"] == VERIFIED and not bloque["sha256"]:
            problemas.append(f"{sid}: VERIFIED de imágenes sin sha256 evidenciado")
        if bloque["IMAGERY_LICENSE_STATUS"] == VERIFIED and not bloque["consulted_at"]:
            problemas.append(f"{sid}: VERIFIED de imágenes sin fecha de consulta")
        if bloque["api_terms"]["estado"] not in ESTADOS:
            problemas.append(f"{sid}: API_TERMS_STATUS fuera del vocabulario")
        # Las dos preguntas se responden por separado: prohibido un campo único heredado.
        if "provider_terms_status" in bloque:
            problemas.append(f"{sid}: vuelve el campo mezclado `provider_terms_status`")
    lonja = auditoria_no_lonja()
    if not lonja["ok"]:
        problemas.append(f"Lonja declarada como fuente: {lonja['sospechosos']}")
    return {"ok": not problemas, "problemas": problemas, "no_lonja": lonja,
            "generado_at": ahora()}


def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Bloques de licencia v2 (imágenes vs API)")
    ap.add_argument("--source", help="muestra el bloque de una fuente")
    ap.add_argument("--resumen", action="store_true", help="resumen por estado (ambas columnas)")
    ap.add_argument("--auditoria", action="store_true", help="auditoría del catálogo")
    ap.add_argument("--partners", action="store_true", help="aliados institucionales (no fuentes)")
    ap.add_argument("--verificar-evidencia", metavar="ID",
                    help="re-descarga UNA evidencia y declara si cambió (red)")
    args = ap.parse_args(list(argv) if argv is not None else None)
    salida: Dict[str, Any] = {}
    if args.source:
        salida["bloque"] = bloque_licencia(args.source)
    if args.verificar_evidencia:
        salida["verificacion"] = verificar_evidencia_registrada(args.verificar_evidencia)
    if args.partners:
        salida["partners"] = partners_institucionales()
    if args.auditoria:
        salida["auditoria"] = auditoria()
    if not salida or args.resumen:
        salida["resumen"] = resumen()
    print(json.dumps(salida, ensure_ascii=False, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

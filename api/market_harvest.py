# -*- coding: utf-8 -*-
"""ARHIAX RE — MARKET HARVEST · adquisición AUTOMÁTICA de evidencia de mercado real.

QUÉ HACE ESTE MÓDULO
────────────────────
Consulta, por HTTP y sin intervención manual, las capas de MERCADO que el geoportal
municipal de Barranquilla publica en su servidor ArcGIS REST, y traduce lo que la fuente
DICE a los contratos que ya existen en el producto (`api/market_evidence.py`,
`api/atribucion_mercado.py`). No estima, no valora y no abre ninguna compuerta: sólo
ADQUIERE y DECLARA.

QUÉ NO HACE (reglas duras)
──────────────────────────
1. **Cero valores inventados.** No se promedia un rango, no se divide un precio por el
   área del sujeto, no se rellena con `0`, no se usa un prior. Si la fuente declara un
   RANGO, viaja un rango y `valor_m2` queda en `None` con el motivo declarado.
2. **Cero `MANUAL_CONFIG` como evidencia.** Un origen no habilitante NUNCA se etiqueta
   como externo: `origin_efectivo` se degrada y `usable_for_estimation` cae a `False`.
3. **Procedencia COMPLETA obligatoria.** Sin URL exacta, `queried_at`, `http_status`,
   bytes y sha256 del payload crudo, el resultado NO puede ser `EXTERNAL_SOURCE`
   utilizable. La falta de procedencia degrada a `MANUAL_CONFIG` (fail-closed), igual que
   hace `api/atribucion_mercado.py::clasificar_origen`.
4. **Ausencia ≠ `NO_MATCH`.** `NO_MATCH` exige una consulta EJECUTADA con éxito contra
   una capa que SÍ tiene datos. No poder consultar es `SOURCE_UNAVAILABLE`; consultar y
   romper el parseo es `QUERY_FAILED`. Confundirlos convertiría un problema de red en una
   afirmación sobre el mercado.
5. **La Lonja no se introduce.** No es fuente (`api/market_sources.py`); este módulo no
   la nombra, no la consulta y no la sustituye.
6. **El payload crudo se preserva SIN MODIFICAR** en `docs/estimation/raw/<capa>.json`
   (bytes exactos de la respuesta), para que el hash sea reproducible.

CLOUDFLARE (hecho medido, no supuesto)
──────────────────────────────────────
El host `miciudad.barranquilla.gov.co` está detrás de Cloudflare y responde **HTTP 403**
con el interstitial «Just a moment…» a peticiones cuyo `Accept`/`Sec-Fetch-*` no parecen
de navegación. Medido el 2026-09-29: la MISMA URL devuelve 200 cuando la petición lleva
cabeceras de navegación completas (`NAV_HEADERS` en este módulo) y 403 sin ellas. Por eso
este módulo usa `NAV_HEADERS` y AUN ASÍ trata el 403 como estado de primera clase.

    python -m pytest tests/test_market_harvest.py -q          # offline, sin red
    python api/market_harvest.py --golden                     # adquiere y escribe artefactos
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

__all__ = [
    "VERSION_HARVEST", "VERSION_PROVENANCE",
    # estados cerrados
    "STATUS_OK", "STATUS_NO_MATCH", "STATUS_SOURCE_UNAVAILABLE", "STATUS_QUERY_FAILED",
    "STATUS_NOT_SUPPORTED", "ESTADOS_HARVEST", "ESTADOS_AUSENCIA",
    # orígenes (vocabulario replicado de `api/atribucion_mercado.py`)
    "ORIGEN_EXTERNO", "ORIGEN_COMPUTADO", "ORIGEN_MANUAL", "ORIGEN_ESTATICO",
    "ORIGEN_PRIOR", "ORIGEN_LEGACY_PRIOR", "ORIGENES",
    "ORIGENES_HABILITANTES", "ORIGENES_NO_HABILITANTES", "origin_sostiene_estimacion",
    "CAMPOS_PROVENANCE_OBLIGATORIOS", "PROCEDENCIA_EXTERNA_OBLIGATORIA",
    "provenance_faltante", "clasificar_procedencia_harvest",
    # tipos de referencia
    "TIPO_VALOR_M2_UNIDAD", "TIPO_VALOR_M2_SUELO", "TIPO_CANON_ARRENDAMIENTO",
    "TIPO_AVALUO_CATASTRAL_AGREGADO", "TIPO_VALOR_TRANSACCION_SIN_AREA",
    "TIPO_CONTEO_TRANSACCIONES", "TIPOS_REFERENCIA",
    # specs y capas
    "BASE_PORTAL", "NAV_HEADERS", "PROVEEDOR_PORTAL", "LayerSpec", "CAPAS_MERCADO",
    "capas_por_source_id", "parsear_banda_m2", "banda_contiene",
    "seleccionar_capa_banda",
    # transporte
    "RawFetch", "fetch_raw", "metadata_url", "query_url", "sin_red",
    # adquisición
    "Sujeto", "sujeto_desde_manifest", "adquirir_capa", "adquirir_todas",
    # traducción a contratos
    "referencia_nivel_3", "GAP_REPORT_schema", "construir_gap_report",
    "construir_artefacto",
    # identidad de la evidencia: CONTENIDO estable vs ADQUISICIÓN volátil
    "HASH_POLICY_VERSION", "CAMPOS_CONTENIDO_ESTABLE", "CAMPOS_ADQUISICION_VOLATIL",
    "content_hash_de_referencia", "acquisition_id_de_referencia",
    "acquisition_hash_de_referencia", "politica_de_hash", "rehashear_referencia",
]

# ══════════════════════════════════════════════════════════════════════════════
# 0 · VERSIONES
# ══════════════════════════════════════════════════════════════════════════════
VERSION_HARVEST = "market-harvest/1.0.0"
VERSION_PROVENANCE = "harvest-provenance/1.0.0"


# ══════════════════════════════════════════════════════════════════════════════
# 1 · ESTADOS CERRADOS DE ADQUISICIÓN
# ══════════════════════════════════════════════════════════════════════════════
STATUS_OK = "OK"
#: La consulta SE EJECUTÓ y la capa TIENE datos, pero ninguno es del sujeto.
STATUS_NO_MATCH = "NO_MATCH"
#: No se pudo alcanzar la fuente (403 Cloudflare, 5xx, timeout, DNS). NO es NO_MATCH.
STATUS_SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
#: Se alcanzó, pero la consulta o el parseo fallaron. NO es NO_MATCH.
STATUS_QUERY_FAILED = "QUERY_FAILED"
#: La capa responde y puede traer dato, pero NO declara el concepto pedido
#: (valor de mercado por m² de unidad construida). Es una limitación de la FUENTE.
STATUS_NOT_SUPPORTED = "NOT_SUPPORTED"

ESTADOS_HARVEST: Tuple[str, ...] = (
    STATUS_OK, STATUS_NO_MATCH, STATUS_SOURCE_UNAVAILABLE, STATUS_QUERY_FAILED,
    STATUS_NOT_SUPPORTED,
)

#: Estados que significan AUSENCIA de dato. Se declaran como conjunto para que la
#: distinción «ausencia ≠ NO_MATCH» sea comprobable en código, no sólo en prosa.
ESTADOS_AUSENCIA: Tuple[str, ...] = (
    STATUS_SOURCE_UNAVAILABLE, STATUS_QUERY_FAILED, STATUS_NOT_SUPPORTED,
)

#: Sub-estados de la consulta al PUNTO exacto del sujeto (se conservan aunque el
#: resultado principal venga de un ámbito más amplio declarado).
STATUS_PUNTO_OK = STATUS_OK
STATUS_PUNTO_NO_MATCH = STATUS_NO_MATCH


# ══════════════════════════════════════════════════════════════════════════════
# 2 · VOCABULARIO DE ORIGEN (replicado: este módulo no depende de otro al importarse)
# ══════════════════════════════════════════════════════════════════════════════
ORIGEN_EXTERNO = "EXTERNAL_SOURCE"
ORIGEN_COMPUTADO = "COMPUTED_FROM_SOURCES"
ORIGEN_MANUAL = "MANUAL_CONFIG"
ORIGEN_ESTATICO = "STATIC_REFERENCE"
ORIGEN_PRIOR = "MODEL_PRIOR"
ORIGEN_LEGACY_PRIOR = "LEGACY_MODEL_PRIOR"

ORIGENES: Tuple[str, ...] = (ORIGEN_EXTERNO, ORIGEN_COMPUTADO, ORIGEN_MANUAL,
                             ORIGEN_ESTATICO, ORIGEN_PRIOR, ORIGEN_LEGACY_PRIOR)
ORIGENES_HABILITANTES = frozenset({ORIGEN_EXTERNO, ORIGEN_COMPUTADO})
ORIGENES_NO_HABILITANTES = frozenset({ORIGEN_MANUAL, ORIGEN_ESTATICO, ORIGEN_PRIOR,
                                      ORIGEN_LEGACY_PRIOR})


def origin_sostiene_estimacion(origin: Optional[str]) -> bool:
    """¿Este origen puede sostener una cifra? Mismo criterio que el resto del producto."""
    return origin in ORIGENES_HABILITANTES


#: Campos de procedencia que ESTE módulo exige para admitir `EXTERNAL_SOURCE`.
CAMPOS_PROVENANCE_OBLIGATORIOS: Tuple[str, ...] = (
    "url", "queried_at", "http_status", "bytes", "sha256",
)

#: Campos que exige `api/atribucion_mercado.py::clasificar_origen` para `EXTERNAL_SOURCE`.
PROCEDENCIA_EXTERNA_OBLIGATORIA: Tuple[str, ...] = (
    "source_id", "proveedor", "fecha", "referencia", "sha256",
)


def provenance_faltante(provenance: Optional[Mapping[str, Any]],
                        campos: Sequence[str] = CAMPOS_PROVENANCE_OBLIGATORIOS
                        ) -> Tuple[str, ...]:
    """Campos de procedencia ausentes o vacíos. `sha256` y `url` no admiten comodines."""
    if not isinstance(provenance, Mapping):
        return tuple(campos)
    faltan: List[str] = []
    for campo in campos:
        valor = provenance.get(campo)
        if valor is None:
            faltan.append(campo)
            continue
        if isinstance(valor, str) and not valor.strip():
            faltan.append(campo)
            continue
        if campo == "sha256":
            texto = str(valor)
            if len(texto) != 64 or not re.fullmatch(r"[0-9a-f]{64}", texto):
                faltan.append(campo)
        if campo == "http_status" and not isinstance(valor, int):
            faltan.append(campo)
    return tuple(faltan)


def clasificar_procedencia_harvest(declaracion: Mapping[str, Any], *,
                                   origen_declarado: Optional[str] = None) -> Dict[str, Any]:
    """Clasifica el ORIGEN de un resultado del harvest con degradación fail-closed.

    Reglas, en orden:

    1. Un origen declarado NO habilitante (`MANUAL_CONFIG`, `STATIC_REFERENCE`,
       `MODEL_PRIOR`, `LEGACY_MODEL_PRIOR`) se conserva tal cual y **jamás** se promueve
       a `EXTERNAL_SOURCE`, tenga o no procedencia.
    2. `EXTERNAL_SOURCE` sólo se honra si la procedencia está COMPLETA y la respuesta fue
       un HTTP 200 real. Si falta cualquier campo → se DEGRADA a `MANUAL_CONFIG` y se
       declara el motivo.
    3. Un origen no declarado se clasifica `MANUAL_CONFIG`: la ausencia de declaración
       nunca se interpreta como fuente.

    Devuelve `origin` (efectivo), `origin_declarado`, `origin_gate`, `origin_blockers` y
    `provenance_faltante`, en el mismo vocabulario que `api/atribucion_mercado.py`.
    """
    declaracion = dict(declaracion or {})
    declarado = origen_declarado or declaracion.get("origen_tipo")
    declarado = str(declarado).strip().upper() if declarado else None
    provenance = declaracion.get("provenance") or {}
    faltan = provenance_faltante(provenance)
    # Una procedencia que no es un mapping no puede leerse: se trata como AUSENTE, no
    # como un objeto del que extraer campos (evita AttributeError y, sobre todo, evita
    # que un valor de tipo inesperado se cuele como procedencia válida).
    http_status = provenance.get("http_status") if isinstance(provenance, Mapping) else None
    blockers: List[str] = []

    if declarado not in ORIGENES:
        efectivo = ORIGEN_MANUAL
        blockers.append(
            f"origen no declarado: se clasifica {efectivo} (no habilita la estimación)")
    elif declarado in ORIGENES_NO_HABILITANTES:
        # Regla dura: un origen no habilitante NUNCA se etiqueta como externo.
        efectivo = declarado
        blockers.append(
            f"origen {efectivo} no habilita la estimación (no es una fuente externa)")
    elif faltan:
        efectivo = ORIGEN_MANUAL
        blockers.append(
            f"origen declarado {declarado} SIN procedencia completa "
            f"(falta: {', '.join(faltan)}): se degrada a {efectivo}")
    elif http_status != 200:
        efectivo = ORIGEN_MANUAL
        blockers.append(
            f"la respuesta no es un HTTP 200 verificable (http_status={http_status!r}): "
            f"sin respuesta exitosa no hay evidencia externa; se degrada a {efectivo}")
    else:
        efectivo = declarado

    gate = efectivo in ORIGENES_HABILITANTES and not blockers
    return {
        "version": VERSION_PROVENANCE,
        "origin": efectivo,
        "origin_declarado": declarado,
        "origin_gate": bool(gate),
        "origin_blockers": blockers,
        "provenance_faltante": list(faltan),
    }


# ══════════════════════════════════════════════════════════════════════════════
# 3 · TIPOS DE REFERENCIA — qué declara REALMENTE cada capa
# ══════════════════════════════════════════════════════════════════════════════
TIPO_VALOR_M2_UNIDAD = "VALOR_M2_UNIDAD_CONSTRUIDA"
TIPO_VALOR_M2_SUELO = "VALOR_M2_SUELO_URBANO"
TIPO_CANON_ARRENDAMIENTO = "CANON_DE_ARRENDAMIENTO"
TIPO_AVALUO_CATASTRAL_AGREGADO = "AVALUO_CATASTRAL_AGREGADO"
TIPO_VALOR_TRANSACCION_SIN_AREA = "VALOR_TRANSACCION_SIN_AREA"
TIPO_CONTEO_TRANSACCIONES = "CONTEO_TRANSACCIONES"

TIPOS_REFERENCIA: Tuple[str, ...] = (
    TIPO_VALOR_M2_UNIDAD, TIPO_VALOR_M2_SUELO, TIPO_CANON_ARRENDAMIENTO,
    TIPO_AVALUO_CATASTRAL_AGREGADO, TIPO_VALOR_TRANSACCION_SIN_AREA,
    TIPO_CONTEO_TRANSACCIONES,
)

#: SÓLO un valor de mercado por m² de UNIDAD CONSTRUIDA puede sostener la estimación de
#: una unidad PH. Un valor de suelo, un canon o un conteo son otros conceptos: se
#: declaran, se conservan, y no sostienen esta cifra.
TIPOS_QUE_SOSTIENEN_ESTIMACION = frozenset({TIPO_VALOR_M2_UNIDAD})


# ══════════════════════════════════════════════════════════════════════════════
# 4 · ESPECIFICACIÓN DE CAPAS REALES DEL GEOPORTAL
# ══════════════════════════════════════════════════════════════════════════════
BASE_PORTAL = "https://miciudad.barranquilla.gov.co/gis/rest/services"
PROVEEDOR_PORTAL = ("Alcaldía Distrital de Barranquilla — geoportal miciudad "
                    "(servidor ArcGIS REST)")

#: Cabeceras de navegación. MEDIDO: con ellas la misma URL que devuelve 403 pasa a 200.
NAV_HEADERS: Dict[str, str] = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
               "image/avif,image/webp,*/*;q=0.8"),
    "Accept-Language": "es-CO,es;q=0.9,en;q=0.8",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "Referer": "https://miciudad.barranquilla.gov.co/",
}


@dataclass(frozen=True)
class LayerSpec:
    """Una capa REAL del geoportal, con el concepto que declara y su vigencia.

    `layer_id` puede ser ``None`` cuando la capa dependa de la banda de área del sujeto:
    en ese caso `seleccionar_capa_banda` resuelve qué `layer_id` corresponde. El valor
    resuelto SIEMPRE viaja en la salida (`layer_id` + `layer_name`), nunca se asume.
    """

    source_id: str
    servicio: str
    layer_id: Optional[int]
    layer_name: str
    tipo_referencia: str
    campos_declarados: Tuple[str, ...]
    #: Campo del que se lee el ámbito de match (punto / manzana / polígono contenedor).
    ambito: str = "PUNTO_SUJETO"
    #: Ámbitos alternativos que se intentan si el primario no devuelve dato.
    ambitos_alternativos: Tuple[str, ...] = ()
    #: Campo de la capa que declara el inicio/fin de vigencia, si existe.
    campo_effective_from: Optional[str] = None
    campo_effective_to: Optional[str] = None
    #: Texto LITERAL de la fuente que declara la vigencia (se copia, no se interpreta).
    vigencia_texto: str = ""
    #: Campo de la capa que declara tamaño de muestra, si existe.
    campo_sample_size: Optional[str] = None
    #: Rango de área construida que cubre la capa ("36-60"), si la capa es por banda.
    banda_area_m2: Optional[str] = None
    #: `True` si la capa es la que declara valor de mercado por m² de unidad construida.
    sostiene_estimacion: bool = False
    notas: str = ""


CAPAS_MERCADO: Tuple[LayerSpec, ...] = (
    LayerSpec(
        source_id="BAQ_OBS_VALORESM2_AREA",
        servicio="valoresm2_area",
        layer_id=None,          # se resuelve por banda de área del sujeto
        layer_name="Rango valores por m². Área (36-60m²).",
        tipo_referencia=TIPO_VALOR_M2_UNIDAD,
        campos_declarados=("objectid", "nombre", "area_construida", "min_valor_m2",
                           "max_valor_m2", "shape"),
        ambito="PUNTO_SUJETO",
        vigencia_texto=("Muestra el resultado del análisis de las compraventas "
                        "inmobiliarias registradas por la Superintendencia de Notariado y "
                        "Registro durante el periodo de enero a mayo de 2026. La "
                        "información muestra, para cada localidad, los rangos de valores "
                        "mínimos y máximos agrupados por áreas."),
        campo_sample_size=None,   # la fuente NO declara N
        banda_area_m2="36-60",
        sostiene_estimacion=True,
        notas=("Declara RANGO (min/max) por LOCALIDAD y banda de área; NO declara un valor "
               "único ni el tamaño de la muestra. Cuatro capas hermanas (layer_id 1..4) "
               "cubren las bandas 36-60, 61-175, 176-290 y >291 m²."),
    ),
    LayerSpec(
        source_id="BAQ_OBS_VALORSUELOURBANO",
        servicio="valorsuelourbano",
        layer_id=5,
        layer_name="Valor del metro cuadrado del suelo urbano. Vigencia 2026.",
        tipo_referencia=TIPO_VALOR_M2_SUELO,
        campos_declarados=("objectid", "valorm2", "codigozona", "vigencia", "shape"),
        ambito="PUNTO_SUJETO",
        campo_effective_to="vigencia",
        vigencia_texto=("Representa el valor por metro cuadrado del suelo urbano para las "
                        "vigencias entre 2022 a 2026 en el distrito de Barranquilla."),
        notas=("Es valor de SUELO URBANO por zona geoeconómica, no valor de una unidad "
               "construida en PH: otro concepto. Se declara y NO sostiene la estimación "
               "de la unidad."),
    ),
    LayerSpec(
        source_id="BAQ_OBS_VALORCOMPRAVENTAS",
        servicio="valorcompraventas",
        layer_id=7,
        layer_name="Valor compraventas 2025",
        tipo_referencia=TIPO_VALOR_TRANSACCION_SIN_AREA,
        campos_declarados=("objectid", "valor_millones", "fecha_captura_oferta",
                           "condicion_predio", "destinacion_economica", "anio", "shape"),
        ambito="PUNTO_SUJETO",
        ambitos_alternativos=("BUFFER_300M",),
        campo_effective_to="anio",
        vigencia_texto=("Muestra el comportamiento del mercado inmobiliario en "
                        "Barranquilla entre 2019 y 2025."),
        notas=("Registros individuales de compraventa con valor y fecha, pero SIN ÁREA "
               "declarada: no hay valor por m² y NO se deriva dividiendo por el área del "
               "sujeto. Ésta es la limitación que hay que cerrar."),
    ),
    LayerSpec(
        source_id="BAQ_OBS_ARRENDAMIENTOS",
        servicio="arrendamientos",
        layer_id=1,
        layer_name="Valor arrendamientos. Año 2024.",
        tipo_referencia=TIPO_CANON_ARRENDAMIENTO,
        campos_declarados=("objectid", "codigo_manzana", "cantidad_ofertas",
                           "valor_promedio", "valor_minimo", "valor_maximo", "shape"),
        ambito="MANZANA_SUJETO",
        vigencia_texto=("Consolida información sobre los cánones de arrendamiento "
                        "recopilados de diferentes fuentes para diferentes periodos en el "
                        "Distrito de Barranquilla."),
        campo_sample_size="cantidad_ofertas",
        notas=("Declara canon de arrendamiento por MANZANA con su cantidad de ofertas "
               "(muestra declarada). No es un valor de venta por m²: se declara y no "
               "sostiene la estimación de valor de la unidad."),
    ),
    LayerSpec(
        source_id="BAQ_OBS_AVALUOCATASTRAL",
        servicio="avaluocatastral",
        layer_id=1,
        layer_name="Avalúo catastral por destino económico. Vigencia 2026.",
        tipo_referencia=TIPO_AVALUO_CATASTRAL_AGREGADO,
        campos_declarados=("objectid", "destino", "avaluo", "shape"),
        ambito="PUNTO_SUJETO",
        vigencia_texto=("Muestra el avalúo catastral total clasificados según el destino "
                        "económico predominante, permitiendo realizar análisis "
                        "comparativos, fiscales."),
        notas=("El avalúo es un TOTAL agregado del polígono por destino económico (el "
               "polígono del sujeto abarca ~37 millones de m²): no es un valor unitario ni "
               "de mercado. Se declara y no sostiene la estimación."),
    ),
    LayerSpec(
        source_id="BAQ_OBS_CANTIDADTRANSACCIONES",
        servicio="cantidadtransacciones",
        layer_id=8,
        layer_name="Cantidad de transacciones por manzana. Año 2026.",
        tipo_referencia=TIPO_CONTEO_TRANSACCIONES,
        campos_declarados=("objectid", "codigo_manzana", "cantidad",
                           "destino_predominante", "anio", "identificador_barrio",
                           "nombre_barrio", "localidad", "shape"),
        ambito="MANZANA_SUJETO",
        campo_effective_from="anio",
        vigencia_texto=("Muestra la distribución anual de las compraventas de predios en "
                        "el Distrito de Barranquilla para 2026 entre los meses de enero y "
                        "mayo, representadas a nivel de manzana."),
        notas=("Declara CUÁNTAS transacciones hubo en la manzana, no a qué valor: es "
               "liquidez/actividad de mercado, no precio. Sostiene contexto y NO una cifra."),
    ),
)


def capas_por_source_id() -> Dict[str, LayerSpec]:
    return {c.source_id: c for c in CAPAS_MERCADO}


def capa_por_servicio(servicio: str) -> Optional[LayerSpec]:
    for c in CAPAS_MERCADO:
        if c.servicio == servicio:
            return c
    return None


_BANDA_RE = re.compile(r"^\s*(\d+)\s*-\s*(\d+)\s*$")
_BANDA_MAYOR_RE = re.compile(r"^\s*>\s*(\d+)\s*$")
#: Sufijos de unidad que las capas pegan a la banda («36-60m²», «36-60 m2»). Se retiran
#: SÓLO para leer los límites: la banda declarada viaja luego LITERAL en la salida.
_SUFIJO_UNIDAD_RE = re.compile(r"\s*(m\s*2|m\u00b2|mts\s*2|metros?\s*cuadrados?)\s*$",
                               re.IGNORECASE)


def parsear_banda_m2(texto: Any) -> Optional[Tuple[float, float]]:
    """Convierte la banda declarada por la capa ("36-60", "36-60m²", ">291m²") a límites.

    Devuelve ``None`` si el texto no declara una banda reconocible: no se adivina. El
    sufijo de unidad se retira únicamente para poder leer los números; el texto ORIGINAL
    es el que se publica en la salida.
    """
    if texto is None:
        return None
    limpio = _SUFIJO_UNIDAD_RE.sub("", str(texto)).strip()
    m = _BANDA_RE.match(limpio)
    if m:
        return (float(m.group(1)), float(m.group(2)))
    m = _BANDA_MAYOR_RE.match(limpio)
    if m:
        return (float(m.group(1)) + 1.0, float("inf"))
    return None


def banda_contiene(banda: Any, area_m2: Any) -> bool:
    """¿La banda declarada contiene el área del sujeto? Sin dato → ``False`` (fail-closed)."""
    limites = parsear_banda_m2(banda)
    try:
        area = float(area_m2)
    except (TypeError, ValueError):
        return False
    if limites is None:
        return False
    return limites[0] <= area <= limites[1]


def seleccionar_capa_banda(layers: Iterable[Mapping[str, Any]], area_m2: Any
                           ) -> Optional[Dict[str, Any]]:
    """Elige la capa cuya banda de área declarada CONTIENE el área del sujeto.

    La elección se decide por el nombre de la capa que la propia fuente publica
    («…Área (36-60m²).»), no por un `layer_id` escrito a mano: si la fuente renumerara
    sus capas, la elección seguiría siendo la correcta y quedaría declarada.
    """
    for layer in layers or []:
        if not isinstance(layer, Mapping):
            continue
        nombre = str(layer.get("name") or "")
        m = re.search(r"\((\s*\d+\s*-\s*\d+\s*m?²?\s*)\)", nombre) or \
            re.search(r"\((\s*>\s*\d+\s*m?²?\s*)\)", nombre)
        if not m:
            continue
        if banda_contiene(m.group(1), area_m2):
            return {"layer": dict(layer), "banda_area_m2": m.group(1).strip()}
    return None


# ══════════════════════════════════════════════════════════════════════════════
# 5 · TRANSPORTE — la red vive AQUÍ y sólo aquí (todo lo demás es inyectable)
# ══════════════════════════════════════════════════════════════════════════════
@dataclass
class RawFetch:
    """Respuesta cruda de una petición. Es el ÚNICO portador de la procedencia."""

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

    def provenance(self, *, source_id: str, servicio: str, layer_id: Optional[int],
                   referencia: Optional[str] = None) -> Dict[str, Any]:
        """Bloque de procedencia COMPLETA, listo para `clasificar_origen`."""
        return {
            "version": VERSION_PROVENANCE,
            "source_id": source_id,
            "proveedor": PROVEEDOR_PORTAL,
            "fecha": (self.queried_at or "")[:10] or None,
            "referencia": referencia or f"{servicio}" + (
                f"/MapServer/{layer_id}" if layer_id is not None else "/MapServer"),
            "url": self.url,
            "queried_at": self.queried_at,
            "http_status": self.http_status,
            "bytes": self.bytes,
            "sha256": self.sha256,
            "cf_ray": self.cf_ray,
            "server": self.server,
        }


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def fetch_raw(url: str, *, timeout: int = 30, intentos: int = 3,
              headers: Optional[Mapping[str, str]] = None,
              opener: Optional[Callable[..., Any]] = None,
              sleep: Callable[[float], None] = time.sleep) -> RawFetch:
    """GET crudo con procedencia. No lanza: TODO fallo se convierte en estado declarado.

    Un `HTTPError` con cuerpo (403 de Cloudflare) se conserva con su cuerpo real para que
    el hash del bloqueo sea auditable: se documenta lo que la fuente respondió, no lo que
    habría gustado que respondiera.
    """
    cabeceras = dict(NAV_HEADERS)
    cabeceras.update(dict(headers or {}))
    abrir = opener or urllib.request.urlopen
    ultimo: Optional[RawFetch] = None
    for i in range(max(1, intentos)):
        queried_at = _utcnow()
        t0 = time.time()
        try:
            req = urllib.request.Request(url, headers=cabeceras)
            with abrir(req, timeout=timeout) as resp:
                cuerpo = resp.read()
                return RawFetch(url=url, http_status=getattr(resp, "status", None),
                                body=cuerpo, queried_at=queried_at,
                                cf_ray=(resp.headers.get("cf-ray")
                                        if resp.headers else None),
                                server=(resp.headers.get("server")
                                        if resp.headers else None),
                                intentos=i + 1, ms=int((time.time() - t0) * 1000))
        except urllib.error.HTTPError as exc:
            cuerpo = b""
            try:
                cuerpo = exc.read()
            except Exception:  # noqa: BLE001
                cuerpo = b""
            ultimo = RawFetch(url=url, http_status=exc.code, body=cuerpo,
                              queried_at=queried_at,
                              cf_ray=((exc.headers or {}).get("cf-ray")),
                              server=((exc.headers or {}).get("server")),
                              error=f"HTTPError {exc.code} {exc.reason}",
                              intentos=i + 1, ms=int((time.time() - t0) * 1000))
        except Exception as exc:  # noqa: BLE001
            ultimo = RawFetch(url=url, http_status=None, body=b"", queried_at=queried_at,
                              error=f"{type(exc).__name__}: {exc}", intentos=i + 1,
                              ms=int((time.time() - t0) * 1000))
        if i + 1 < max(1, intentos):
            sleep(1.5 * (i + 1))
    assert ultimo is not None
    return ultimo


def metadata_url(spec: LayerSpec) -> str:
    return f"{BASE_PORTAL}/observatorio/{spec.servicio}/MapServer?f=json"


def query_url(spec: LayerSpec, layer_id: int, *, where: Optional[str] = None,
              geometry: Optional[str] = None, geometry_type: str = "esriGeometryPoint",
              in_sr: Optional[str] = None, spatial_rel: Optional[str] = None,
              distance: Optional[float] = None, units: Optional[str] = None,
              count_only: bool = False, out_fields: str = "*") -> str:
    """URL EXACTA de la consulta. Se construye aquí y se registra tal cual se pidió."""
    params: Dict[str, Any] = {"f": "json", "outFields": out_fields,
                              "returnGeometry": "false"}
    if count_only:
        params["returnCountOnly"] = "true"
    if geometry is not None:
        params.update({"geometry": geometry, "geometryType": geometry_type,
                       "spatialRel": spatial_rel or "esriSpatialRelIntersects"})
        if in_sr:
            params["inSR"] = in_sr
        if distance is not None:
            params["distance"] = distance
            params["units"] = units or "esriSRUnit_Meter"
    params["where"] = where if where is not None else "1=1"
    return (f"{BASE_PORTAL}/observatorio/{spec.servicio}/MapServer/{layer_id}/query?"
            + urllib.parse.urlencode(params))


def sin_red(*_a: Any, **_k: Any):
    """Centinela de `fetch_fn` cuando NO hay red disponible: no simula una respuesta."""
    raise RuntimeError("sin_red(): no hay transporte de red en esta ejecución")


# ══════════════════════════════════════════════════════════════════════════════
# 6 · EL SUJETO
# ══════════════════════════════════════════════════════════════════════════════
@dataclass
class Sujeto:
    """Identidad del inmueble a consultar.

    Cada campo se declara; lo que no se sabe viaja en ``None``. Sin área y sin ubicación
    no se puede consultar una banda ni un punto: se declara y no se inventa.
    """

    folio: Optional[str] = None
    barrio: Optional[str] = None
    localidad: Optional[str] = None
    codigo_manzana: Optional[str] = None
    estrato: Optional[str] = None
    tipologia: Optional[str] = None
    area_m2: Optional[float] = None
    lat: Optional[float] = None
    lon: Optional[float] = None

    @property
    def punto_wgs84(self) -> Optional[str]:
        """Punto en el orden que exige ArcGIS: ``lon,lat``. Sin ambos → ``None``."""
        if self.lat is None or self.lon is None:
            return None
        return f"{self.lon},{self.lat}"

    def puede_consultar_punto(self) -> bool:
        return self.punto_wgs84 is not None

    def to_dict(self) -> Dict[str, Any]:
        return {"folio": self.folio, "barrio": self.barrio, "localidad": self.localidad,
                "codigo_manzana": self.codigo_manzana, "estrato": self.estrato,
                "tipologia": self.tipologia, "area_m2": self.area_m2,
                "lat": self.lat, "lon": self.lon}


def sujeto_desde_manifest(ruta: Any) -> Sujeto:
    """Lee el sujeto del expediente REAL. No completa huecos: lo que falte queda `None`."""
    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    modelo = datos.get("modelo") or {}
    urbano = modelo.get("urban_context") or {}
    ctx = modelo.get("market_context") or {}
    ofi = ctx.get("official_urban_context") or {}
    coords = ctx.get("coordinates") or {}
    return Sujeto(
        folio=datos.get("folio") or datos.get("case_id"),
        barrio=urbano.get("barrio") or ofi.get("barrio"),
        localidad=urbano.get("localidad") or ofi.get("localidad"),
        codigo_manzana=ofi.get("codigo_manzana"),
        estrato=urbano.get("estrato") or ofi.get("estrato"),
        tipologia=urbano.get("tipologia"),
        area_m2=urbano.get("area"),
        lat=coords.get("lat"),
        lon=coords.get("lon"),
    )


# ══════════════════════════════════════════════════════════════════════════════
# 7 · ADQUISICIÓN DE UNA CAPA
# ══════════════════════════════════════════════════════════════════════════════
def _features(respuesta: Optional[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    if not isinstance(respuesta, Mapping):
        return []
    feats = respuesta.get("features")
    if not isinstance(feats, list):
        return []
    return [dict(f.get("attributes") or {}) for f in feats if isinstance(f, Mapping)]


def _valor_o_rango(tipo: str, attrs: Mapping[str, Any]) -> Dict[str, Any]:
    """Traduce los atributos CRUDOS al concepto, sin derivar nada que no esté declarado."""
    if tipo == TIPO_VALOR_M2_UNIDAD:
        return {"nombre": attrs.get("nombre"),
                "area_construida": attrs.get("area_construida"),
                "min_valor_m2": attrs.get("min_valor_m2"),
                "max_valor_m2": attrs.get("max_valor_m2")}
    if tipo == TIPO_VALOR_M2_SUELO:
        return {"valorm2": attrs.get("valorm2"), "codigozona": attrs.get("codigozona")}
    if tipo == TIPO_CANON_ARRENDAMIENTO:
        return {"codigo_manzana": attrs.get("codigo_manzana"),
                "cantidad_ofertas": attrs.get("cantidad_ofertas"),
                "valor_promedio": attrs.get("valor_promedio"),
                "valor_minimo": attrs.get("valor_minimo"),
                "valor_maximo": attrs.get("valor_maximo")}
    if tipo == TIPO_AVALUO_CATASTRAL_AGREGADO:
        return {"destino": attrs.get("destino"), "avaluo": attrs.get("avaluo")}
    if tipo == TIPO_VALOR_TRANSACCION_SIN_AREA:
        return {"registros": len(attrs.get("_registros") or []),
                "valor_millones": (attrs.get("_registros") or [{}])[0].get("valor_millones")
                if attrs.get("_registros") else attrs.get("valor_millones"),
                "fecha_captura_oferta": attrs.get("fecha_captura_oferta"),
                "condicion_predio": attrs.get("condicion_predio"),
                "destinacion_economica": attrs.get("destinacion_economica")}
    if tipo == TIPO_CONTEO_TRANSACCIONES:
        return {"codigo_manzana": attrs.get("codigo_manzana"),
                "cantidad": attrs.get("cantidad"),
                "destino_predominante": attrs.get("destino_predominante"),
                "nombre_barrio": attrs.get("nombre_barrio"),
                "localidad": attrs.get("localidad")}
    return dict(attrs)


def adquirir_capa(spec: LayerSpec, sujeto: Sujeto, *,
                  fetch_fn: Optional[Callable[..., RawFetch]] = None,
                  layer_id: Optional[int] = None,
                  layer_name: Optional[str] = None,
                  banda_area_m2: Optional[str] = None,
                  registros_por_capa: int = 25,
                  out_dir: Optional[Path] = None,
                  timeout: int = 30) -> Dict[str, Any]:
    """Consulta UNA capa y devuelve el registro de adquisición con su estado cerrado.

    Orden de operaciones:
      1. metadata del MapServer (para declarar `layer_id`, campos y geometría REALES);
      2. consulta por el ámbito del sujeto (punto, manzana o buffer);
      3. si no hay match en el ámbito primario, se intentan los alternativos declarados;
      4. clasificación del origen con degradación fail-closed.

    Nunca lanza por causas de red: devuelve `SOURCE_UNAVAILABLE`/`QUERY_FAILED`.
    """
    traer = fetch_fn or fetch_raw
    lid = spec.layer_id if layer_id is None else layer_id
    nombre = layer_name or spec.layer_name
    banda = banda_area_m2 or spec.banda_area_m2
    consultas: List[Dict[str, Any]] = []

    def _traer(url: str) -> RawFetch:
        """Toda causa de red se convierte en un `RawFetch` declarado; NUNCA en excepción."""
        try:
            obtenido = traer(url, timeout=timeout)
        except Exception as exc:  # noqa: BLE001
            return RawFetch(url=url, http_status=None, body=b"", queried_at=_utcnow(),
                            error=f"{type(exc).__name__}: {exc}")
        if not isinstance(obtenido, RawFetch):
            raise TypeError(
                f"fetch_fn debe devolver un RawFetch, no {type(obtenido).__name__}: "
                f"un transporte que no declara procedencia no es admisible")
        return obtenido

    # ── 1 · metadata ─────────────────────────────────────────────────────────
    m_url = metadata_url(spec)
    m_raw = _traer(m_url)
    meta = m_raw.json()
    m_prov = m_raw.provenance(source_id=spec.source_id, servicio=spec.servicio,
                              layer_id=lid)
    consultas.append({"rol": "METADATA", "url": m_url,
                      "http_status": m_raw.http_status, "bytes": m_raw.bytes,
                      "sha256": m_raw.sha256, "error": m_raw.error})
    if out_dir is not None:
        _escribir_crudo(out_dir / f"{spec.servicio}__metadata.json", m_raw)
    if meta is None:
        estado = (STATUS_SOURCE_UNAVAILABLE if not m_raw.es_http_200
                  else STATUS_QUERY_FAILED)
        return _resultado(spec, sujeto, lid, nombre, banda, estado, m_raw, m_prov,
                          consultas, None, None,
                          motivo=("no se pudo leer la metadata de la capa: "
                                  f"{m_raw.error or 'respuesta no-JSON'}"),
                          out_dir=out_dir)

    # ── 2 · resolución de layer_id / nombre / banda desde la FUENTE ──────────
    if lid is None:
        elegida = seleccionar_capa_banda(meta.get("layers") or [], sujeto.area_m2)
        if elegida is None:
            return _resultado(spec, sujeto, None, nombre, banda, STATUS_NO_MATCH,
                              m_raw, m_prov, consultas, None, meta,
                              motivo=("ninguna capa del servicio declare una banda de "
                                      f"área que contenga el área del sujeto "
                                      f"({sujeto.area_m2} m²): no se elige capa a dedo"),
                              out_dir=out_dir)
        lid = elegida["layer"]["id"]
        nombre = str(elegida["layer"].get("name") or nombre)
        banda = elegida["banda_area_m2"]
        m_prov = m_raw.provenance(source_id=spec.source_id, servicio=spec.servicio,
                                  layer_id=lid)
    else:
        for l in meta.get("layers") or []:
            if isinstance(l, Mapping) and l.get("id") == lid:
                nombre = str(l.get("name") or nombre)

    # ── 3 · consultas por ámbito ─────────────────────────────────────────────
    ambitos = (spec.ambito,) + tuple(spec.ambitos_alternativos)
    elegido: Optional[Dict[str, Any]] = None
    punto_status: Optional[str] = None
    #: Respuesta del ámbito PRIMARIO. Aunque no haya match, es la evidencia cruda de la
    #: consulta al sujeto y es la que se preserva como `raw/<capa>.json`.
    principal: Optional[RawFetch] = None

    for ambito in ambitos:
        if ambito == "PUNTO_SUJETO":
            if not sujeto.puede_consultar_punto():
                consultas.append({"rol": "PUNTO_SUJETO", "url": None,
                                  "http_status": None, "bytes": 0, "sha256": None,
                                  "error": "sin coordenadas del sujeto",
                                  "estado": STATUS_SOURCE_UNAVAILABLE})
                if punto_status is None:
                    punto_status = STATUS_SOURCE_UNAVAILABLE
                continue
            url = query_url(spec, lid, geometry=sujeto.punto_wgs84, in_sr="4326")
        elif ambito == "MANZANA_SUJETO":
            if not sujeto.codigo_manzana:
                consultas.append({"rol": "MANZANA_SUJETO", "url": None,
                                  "http_status": None, "bytes": 0, "sha256": None,
                                  "error": "sin código de manzana del sujeto",
                                  "estado": STATUS_SOURCE_UNAVAILABLE})
                continue
            url = query_url(spec, lid,
                            where=f"codigo_manzana = '{sujeto.codigo_manzana}'")
        elif ambito == "BUFFER_300M":
            if not sujeto.puede_consultar_punto():
                consultas.append({"rol": "BUFFER_300M", "url": None, "http_status": None,
                                  "bytes": 0, "sha256": None,
                                  "error": "sin coordenadas del sujeto",
                                  "estado": STATUS_SOURCE_UNAVAILABLE})
                continue
            url = query_url(spec, lid, geometry=sujeto.punto_wgs84, in_sr="4326",
                            distance=300.0, units="esriSRUnit_Meter")
        else:
            raise ValueError(f"ámbito desconocido: {ambito!r}")

        raw = _traer(url)
        if principal is None:
            principal = raw
        cuerpo = raw.json()
        registro = {"rol": ambito, "url": url, "http_status": raw.http_status,
                    "bytes": raw.bytes, "sha256": raw.sha256, "error": raw.error,
                    "cf_ray": raw.cf_ray}
        consultas.append(registro)
        if out_dir is not None:
            sufijo = ambito.lower()
            _escribir_crudo(out_dir / f"{spec.servicio}__{sufijo}.json", raw)

        if cuerpo is None:
            registro["estado"] = (STATUS_SOURCE_UNAVAILABLE if not raw.es_http_200
                                  else STATUS_QUERY_FAILED)
            if ambito == "PUNTO_SUJETO":
                punto_status = registro["estado"]
            continue
        if "error" in cuerpo and isinstance(cuerpo.get("error"), Mapping):
            registro["estado"] = STATUS_QUERY_FAILED
            registro["error_arcgis"] = cuerpo.get("error")
            if ambito == "PUNTO_SUJETO":
                punto_status = STATUS_QUERY_FAILED
            continue

        feats = _features(cuerpo)
        registro["estado"] = STATUS_OK if feats else STATUS_NO_MATCH
        registro["n_features"] = len(feats)
        if ambito == "PUNTO_SUJETO":
            punto_status = registro["estado"]
        if feats and elegido is None:
            elegido = {"ambito": ambito, "raw": raw, "cuerpo": cuerpo, "features": feats,
                       "url": url}

    # ── 4 · sin dato en ningún ámbito ────────────────────────────────────────
    if elegido is None:
        # La metadata NO cuenta: "alcanzar el servicio" no es "haber consultado el dato
        # del sujeto". Sólo las consultas de ámbito deciden si la consulta se ejecutó.
        consultas_ambito = [c for c in consultas if c.get("rol") != "METADATA"]
        tuvo_respuesta = any(c.get("http_status") == 200 for c in consultas_ambito)
        estados = {c.get("estado") for c in consultas_ambito if c.get("estado")}

        if not tuvo_respuesta:
            estado = STATUS_SOURCE_UNAVAILABLE
            motivo = ("ninguna consulta al sujeto alcanzó la fuente: la capa es "
                      "INALCANZABLE (o no hay con qué consultarla), NO «no hay mercado "
                      "para el sujeto»")
        elif estados & {STATUS_OK, STATUS_NO_MATCH}:
            # Al menos una consulta se EJECUTÓ con éxito contra una capa que respondió
            # JSON válido: esto sí es un NO_MATCH afirmable.
            estado = STATUS_NO_MATCH
            motivo = ("consultas ejecutadas con éxito y la capa tiene datos, pero ninguno "
                      "corresponde al sujeto en los ámbitos declarados: "
                      + ", ".join(ambitos))
        elif STATUS_QUERY_FAILED in estados:
            estado = STATUS_QUERY_FAILED
            motivo = "la fuente respondió pero ninguna consulta pudo interpretarse"
        else:
            estado = STATUS_SOURCE_UNAVAILABLE
            motivo = "las consultas no obtuvieron respuesta utilizable de la fuente"
        prov = principal
        prov_prov = (prov.provenance(source_id=spec.source_id, servicio=spec.servicio,
                                     layer_id=lid) if prov is not None else m_prov)
        return _resultado(spec, sujeto, lid, nombre, banda, estado, prov, prov_prov,
                          consultas, None, meta, motivo=motivo,
                          punto_status=punto_status, out_dir=out_dir,
                          vigencia_texto=spec.vigencia_texto)

    # ── 5 · concepto: ¿la capa declara lo que se necesita? ───────────────────
    attrs = dict(elegido["features"][0])
    if spec.tipo_referencia == TIPO_VALOR_TRANSACCION_SIN_AREA:
        attrs["_registros"] = elegido["features"][:registros_por_capa]
    sostiene = spec.tipo_referencia in TIPOS_QUE_SOSTIENEN_ESTIMACION
    estado = STATUS_OK if sostiene else STATUS_NOT_SUPPORTED

    prov = elegido["raw"].provenance(source_id=spec.source_id, servicio=spec.servicio,
                                     layer_id=lid)
    return _resultado(spec, sujeto, lid, nombre, banda, estado, elegido["raw"], prov,
                      consultas, _valor_o_rango(spec.tipo_referencia, attrs), meta,
                      motivo=_motivo_concepto(spec), punto_status=punto_status,
                      ambito_match=elegido["ambito"], attrs=attrs,
                      out_dir=out_dir, vigencia_texto=spec.vigencia_texto,
                      n_features=len(elegido["features"]))


def _motivo_concepto(spec: LayerSpec) -> str:
    if spec.tipo_referencia in TIPOS_QUE_SOSTIENEN_ESTIMACION:
        return ("la capa declara valor de mercado por m² para la banda de área del sujeto "
                "y trae dato para su localidad")
    razones = {
        TIPO_VALOR_M2_SUELO: ("declara valor del metro cuadrado de SUELO URBANO, no de una "
                              "unidad construida en PH: otro concepto, no sostiene la "
                              "estimación de la unidad"),
        TIPO_CANON_ARRENDAMIENTO: ("declara CANON DE ARRENDAMIENTO, no un valor de venta "
                                   "por m²; capitalizar exigiría una tasa que la fuente no "
                                   "declara"),
        TIPO_AVALUO_CATASTRAL_AGREGADO: ("declara el AVALÚO CATASTRAL TOTAL de un polígono "
                                         "por destino económico, no un valor unitario de "
                                         "mercado"),
        TIPO_VALOR_TRANSACCION_SIN_AREA: ("declara VALOR DE TRANSACCIÓN por registro pero "
                                          "SIN ÁREA: no hay valor por m² y no se deriva "
                                          "dividiendo por el área del sujeto"),
        TIPO_CONTEO_TRANSACCIONES: ("declara CUÁNTAS transacciones hubo en la manzana, no "
                                    "a qué valor: es actividad de mercado, no precio"),
    }
    return razones.get(spec.tipo_referencia, "la capa no declara el concepto requerido")


def _resultado(spec: LayerSpec, sujeto: Sujeto, layer_id: Optional[int],
               layer_name: str, banda: Optional[str], estado: str, raw: Optional[RawFetch],
               provenance: Mapping[str, Any], consultas: List[Dict[str, Any]],
               valor: Optional[Mapping[str, Any]], meta: Optional[Mapping[str, Any]],
               *, motivo: str, punto_status: Optional[str] = None,
               ambito_match: Optional[str] = None,
               attrs: Optional[Mapping[str, Any]] = None,
               out_dir: Optional[Path] = None,
               vigencia_texto: Optional[str] = None,
               n_features: int = 0) -> Dict[str, Any]:
    """Construye el registro de adquisición con los campos EXACTOS del contrato.

    Como efecto auditable, preserva la respuesta cruda en ``raw/<capa>.json`` — los BYTES
    exactos que la fuente devolvió, sin reformatear — para que el `sha256` declarado sea
    reproducible por un tercero.
    """
    if out_dir is not None and raw is not None:
        _escribir_crudo(Path(out_dir) / f"{spec.servicio}.json", raw)
    attrs = dict(attrs or {})
    vigencia = _vigencia(spec, attrs, meta)
    sample_size = attrs.get(spec.campo_sample_size) if spec.campo_sample_size else None
    procedencia = clasificar_procedencia_harvest(
        {"origen_tipo": ORIGEN_EXTERNO, "provenance": provenance},
        origen_declarado=ORIGEN_EXTERNO)
    # El origen sólo viaja como EXTERNAL_SOURCE si la procedencia está completa Y la
    # consulta trajo dato. Sin dato no hay evidencia externa que citar.
    if estado != STATUS_OK or not provenance_faltante(provenance) == ():
        procedencia["origin"] = (ORIGEN_MANUAL if procedencia["origin"] == ORIGEN_EXTERNO
                                 else procedencia["origin"])
        procedencia["origin_gate"] = False
        if estado != STATUS_OK and not procedencia["origin_blockers"]:
            procedencia["origin_blockers"] = [
                f"la adquisición quedó en {estado}: sin dato no se declara fuente externa "
                f"que lo sostenga"]

    usable = (estado == STATUS_OK
              and spec.tipo_referencia in TIPOS_QUE_SOSTIENEN_ESTIMACION
              and procedencia["origin_gate"])

    return {
        "version_harvest": VERSION_HARVEST,
        "source_id": spec.source_id,
        "servicio": spec.servicio,
        "service_url": f"{BASE_PORTAL}/observatorio/{spec.servicio}/MapServer",
        "layer_id": layer_id,
        "layer_name": layer_name if layer_id is not None else None,
        "layer_name_esperado": spec.layer_name,
        "banda_area_m2": banda,
        "http_status": provenance.get("http_status"),
        "consulted_at": provenance.get("queried_at"),
        "bytes": provenance.get("bytes"),
        "sha256": provenance.get("sha256"),
        "cf_ray": provenance.get("cf_ray"),
        "status": estado,
        "status_scope": ambito_match,
        "status_punto_sujeto": punto_status,
        "n_features": n_features,
        "value_or_range": dict(valor) if valor is not None else None,
        "tipo_referencia": spec.tipo_referencia,
        "effective_from": vigencia["effective_from"],
        "effective_to": vigencia["effective_to"],
        "effective_basis": vigencia["basis"],
        "effective_precision": vigencia["precision"],
        "vigencia_texto_literal": vigencia["vigencia_texto_literal"],
        # El texto de metodología lo declara la FUENTE: se copia su literal, no se redacta.
        "metodologia_declarada": vigencia_texto or spec.vigencia_texto or None,
        "sample_size": sample_size,
        "sample_size_declarado_por": spec.campo_sample_size,
        "usable_for_estimation": bool(usable),
        "origin": procedencia["origin"],
        "origin_declarado": procedencia["origin_declarado"],
        "origin_gate": procedencia["origin_gate"],
        "origin_blockers": procedencia["origin_blockers"],
        "provenance": dict(provenance),
        "provenance_faltante": list(provenance_faltante(provenance)),
        "queries": consultas,
        "campos_declarados_por_la_fuente": list(spec.campos_declarados),
        "reason": motivo,
        "notas": spec.notas,
    }


def _vigencia(spec: LayerSpec, attrs: Mapping[str, Any],
              meta: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """Vigencia DECLARADA por la capa. Sin declaración → ``None`` (no se supone)."""
    desde = attrs.get(spec.campo_effective_from) if spec.campo_effective_from else None
    hasta = attrs.get(spec.campo_effective_to) if spec.campo_effective_to else None
    basis: List[str] = []
    if spec.campo_effective_from and desde is not None:
        basis.append(f"campo `{spec.campo_effective_from}`")
    if spec.campo_effective_to and hasta is not None:
        basis.append(f"campo `{spec.campo_effective_to}`")
    if spec.vigencia_texto:
        basis.append("descripción del servicio")
    return {"effective_from": str(desde) if desde is not None else None,
            "effective_to": str(hasta) if hasta is not None else None,
            "basis": "; ".join(basis) or "la capa NO declara vigencia",
            "precision": "CAMPO" if (desde is not None or hasta is not None)
            else ("TEXTO" if spec.vigencia_texto else "NO_DECLARADA"),
            "vigencia_texto_literal": spec.vigencia_texto or None}


def _escribir_crudo(destino: Path, raw: RawFetch) -> None:
    """Preserva la respuesta cruda SIN MODIFICAR (bytes exactos) para que el hash cuadre."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(raw.body)


def adquirir_todas(sujeto: Sujeto, *, fetch_fn: Optional[Callable[..., RawFetch]] = None,
                   out_dir: Optional[Path] = None, timeout: int = 30,
                   capas: Sequence[LayerSpec] = CAPAS_MERCADO) -> List[Dict[str, Any]]:
    """Adquiere TODAS las capas declaradas. Un fallo en una no impide las demás."""
    salida: List[Dict[str, Any]] = []
    for spec in capas:
        try:
            salida.append(adquirir_capa(spec, sujeto, fetch_fn=fetch_fn, out_dir=out_dir,
                                        timeout=timeout))
        except Exception as exc:  # noqa: BLE001
            # Un fallo inesperado se DECLARA; jamás se convierte en un valor por defecto.
            salida.append({
                "version_harvest": VERSION_HARVEST, "source_id": spec.source_id,
                "servicio": spec.servicio,
                "service_url": f"{BASE_PORTAL}/observatorio/{spec.servicio}/MapServer",
                "layer_id": spec.layer_id, "layer_name": None,
                "http_status": None, "consulted_at": _utcnow(), "bytes": 0,
                "sha256": None, "status": STATUS_QUERY_FAILED,
                "value_or_range": None, "effective_from": None, "effective_to": None,
                "sample_size": None, "usable_for_estimation": False,
                "origin": ORIGEN_MANUAL, "origin_gate": False,
                "origin_blockers": [f"excepción no prevista: {type(exc).__name__}: {exc}"],
                "provenance": {}, "reason": "adquisición interrumpida por excepción",
            })
    return salida


# ══════════════════════════════════════════════════════════════════════════════
# 8 · TRADUCCIÓN A LOS CONTRATOS DEL PRODUCTO
# ══════════════════════════════════════════════════════════════════════════════
def _sha256_canonico(dato: Any) -> str:
    texto = json.dumps(dato, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                       default=str)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


# ══════════════════════════════════════════════════════════════════════════════
# 7.1 · IDENTIDAD DE LA EVIDENCIA: CONTENIDO (estable) vs ADQUISICIÓN (volátil)
# ══════════════════════════════════════════════════════════════════════════════
# DEFECTO CERRADO: el `evidence_hash` de una referencia de nivel 3 incluía
# `queried_at`, así que CAMBIABA en cada adquisición de la MISMA evidencia
# (`6f84f220…` → `d89aa0c2…`) y ningún revisor podía verificar el hash contra el
# payload. Ahora hay DOS hechos separados, cada uno con su nombre:
#
#   · `content_hash`      — sha256 canónico del CONTENIDO que la fuente publicó (el
#                           sha256 de los BYTES CRUDOS de la respuesta + los campos
#                           materiales del contrato). NO depende de cuándo se
#                           consultó: se reproduce desde `docs/estimation/raw/`.
#   · `acquisition_id`    — identificador del EVENTO de adquisición (fuente, URL
#     `acquisition_hash`   exacta, `queried_at`, HTTP, bytes, borde Cloudflare). Es
#                           volátil por naturaleza y se declara APARTE.
#
# `evidence_hash` se conserva como ALIAS del `content_hash` (estable) para no romper
# a quien ya lo citaba; con la política anterior era volátil y por eso no verificaba.
HASH_POLICY_VERSION = "dictus-evidence-hash/2.0.0"

#: Campos que definen el CONTENIDO de la evidencia (estables entre adquisiciones).
CAMPOS_CONTENIDO_ESTABLE: Tuple[str, ...] = (
    "source_id", "reference_id", "layer_id", "banda_area_m2", "area_sujeto_m2",
    "rango_valor_m2", "valor_m2", "sample_size", "metodologia_declarada",
    "vigencia_declarada", "payload_sha256",
)
#: Campos que identifican la ADQUISICIÓN (volátiles: cambian en cada consulta).
CAMPOS_ADQUISICION_VOLATIL: Tuple[str, ...] = (
    "source_id", "url_consultada", "service_url", "queried_at", "http_status", "bytes",
    "cf_ray", "layer_id",
)


def politica_de_hash() -> Dict[str, Any]:
    """Política de hash DECLARADA (versionada) de la evidencia de nivel 3."""
    return {
        "version": HASH_POLICY_VERSION,
        "content_hash": ("sha256 canónico del CONTENIDO publicado por la fuente: los "
                         "BYTES CRUDOS (`payload_sha256`) + los campos materiales del "
                         "contrato. ESTABLE entre adquisiciones."),
        "acquisition_id": ("identificador del EVENTO de adquisición (fuente, URL exacta, "
                          "`queried_at`, HTTP, bytes, borde Cloudflare). VOLÁTIL por "
                          "diseño: se declara aparte y NUNCA entra al `content_hash`."),
        "evidence_hash": ("alias del `content_hash` (estable). Antes incluía `queried_at` "
                          "y cambiaba en cada adquisición, así que no era verificable."),
        "campos_contenido_estable": list(CAMPOS_CONTENIDO_ESTABLE),
        "campos_adquisicion_volatil": list(CAMPOS_ADQUISICION_VOLATIL),
    }


def _nucleo_de_contenido(referencia: Mapping[str, Any]) -> Dict[str, Any]:
    """Proyección del CONTENIDO (sin un solo campo de adquisición)."""
    return {c: referencia.get(c) for c in CAMPOS_CONTENIDO_ESTABLE}


def content_hash_de_referencia(referencia: Mapping[str, Any]) -> str:
    """`content_hash` ESTABLE de una referencia de nivel 3 (sin `queried_at`)."""
    base = _nucleo_de_contenido(referencia)
    if not base.get("payload_sha256"):
        # Sin sha256 del payload crudo la evidencia no es verificable: se declara el
        # estado, no se fabrica un hash que aparente verificabilidad.
        base["payload_sha256"] = None
        base["payload_sha256_ausente"] = True
    return _sha256_canonico(base)


def acquisition_hash_de_referencia(referencia: Mapping[str, Any]) -> str:
    """`acquisition_hash` VOLÁTIL: sella el evento de adquisición, no el contenido."""
    return _sha256_canonico({c: referencia.get(c) for c in CAMPOS_ADQUISICION_VOLATIL})


def acquisition_id_de_referencia(referencia: Mapping[str, Any]) -> str:
    """`acquisition_id` legible del evento de adquisición (fuente + hash corto)."""
    fuente = str(referencia.get("source_id") or "FUENTE")
    return f"ACQ-{fuente}-{acquisition_hash_de_referencia(referencia)[:12]}"


def rehashear_referencia(referencia: Mapping[str, Any]) -> Dict[str, Any]:
    """Devuelve la referencia con la identidad de hash de `HASH_POLICY_VERSION`.

    Reescribe SÓLO los campos de hash e identidad; todo lo demás viaja intacto (la
    adquisición literal y lo que la fuente declara no se toca).
    """
    ref = dict(referencia)
    ref["content_hash"] = content_hash_de_referencia(ref)
    ref["acquisition_hash"] = acquisition_hash_de_referencia(ref)
    ref["acquisition_id"] = acquisition_id_de_referencia(ref)
    ref["evidence_hash"] = ref["content_hash"]
    ref["hash_policy"] = politica_de_hash()
    return ref


def referencia_nivel_3(resultado: Mapping[str, Any], sujeto: Sujeto, *,
                       market_evidence: Any = None) -> Optional[Dict[str, Any]]:
    """Construye el objeto LEVEL_3_AGGREGATED_MARKET_REFERENCES de una adquisición.

    Devuelve ``None`` si la adquisición no es un valor de mercado por m² de unidad
    construida, si el estado no es `OK` o si la procedencia o el origen no habilitan.

    NO deriva nada: la fuente declara un RANGO, así que el rango viaja y ``valor_m2``
    queda en ``None`` con el motivo. Promediar min y max sería un valor INVENTADO por
    este módulo y no está en la fuente.
    """
    if not isinstance(resultado, Mapping):
        return None
    if resultado.get("status") != STATUS_OK:
        return None
    if resultado.get("tipo_referencia") not in TIPOS_QUE_SOSTIENEN_ESTIMACION:
        return None
    if not resultado.get("origin_gate"):
        return None
    if provenance_faltante(resultado.get("provenance")) != ():
        return None
    valor = resultado.get("value_or_range") or {}
    minimo, maximo = valor.get("min_valor_m2"), valor.get("max_valor_m2")
    if minimo is None and maximo is None:
        return None

    metodologia = (resultado.get("provenance", {}).get("referencia") or "")
    nucleo = {
        "reference_id": (f"{resultado['source_id']}/L{resultado.get('layer_id')}/"
                         f"{valor.get('nombre')}"),
        "source_id": resultado["source_id"],
        "origin": resultado["origin"],
        "service_url": resultado.get("service_url"),
        "layer_id": resultado.get("layer_id"),
        "layer_name": resultado.get("layer_name"),
        "sector_referencia": valor.get("nombre"),
        "banda_area_m2": valor.get("area_construida") or resultado.get("banda_area_m2"),
        "area_sujeto_m2": sujeto.area_m2,
        "rango_valor_m2": {"min": minimo, "max": maximo, "unidad": "COP/m2",
                           "moneda": "COP", "base": "m2_area_construida"},
        "valor_m2": None,
        "motivo_valor_m2_ausente": (
            "la fuente declara un RANGO (min_valor_m2 / max_valor_m2) y NO un valor único; "
            "promediar los extremos sería un valor inventado por este módulo"),
        "sample_size": resultado.get("sample_size"),
        "sample_size_declarado": resultado.get("sample_size") is not None,
        "vigencia_declarada": {"effective_from": resultado.get("effective_from"),
                               "effective_to": resultado.get("effective_to"),
                               "basis": resultado.get("effective_basis"),
                               "precision": resultado.get("effective_precision"),
                               "texto_literal": resultado.get("vigencia_texto_literal")},
        "metodologia_declarada": resultado.get("metodologia_declarada"),
        "http_status": resultado.get("http_status"),
        "queried_at": resultado.get("consulted_at"),
        "cf_ray": resultado.get("cf_ray"),
        "payload_sha256": resultado.get("sha256"),
        "bytes": resultado.get("bytes"),
        "url_consultada": (resultado.get("provenance") or {}).get("url"),
    }
    # §7.1 · DOS hechos separados: el CONTENIDO (`content_hash`, estable) y la
    # ADQUISICIÓN (`acquisition_id` / `acquisition_hash`, volátiles). Con la política
    # anterior el `evidence_hash` incluía `queried_at` y cambiaba en cada adquisición
    # de la MISMA evidencia: no era verificable por un revisor.
    nucleo = rehashear_referencia(nucleo)

    referencia = {
        "nivel": "LEVEL_3_AGGREGATED_MARKET_REFERENCES",
        **nucleo,
        "provenance": dict(resultado.get("provenance") or {}),
        "usable_for_estimation": True,
        "limitaciones_declaradas": [
            "el rango agregado NO acredita una unidad: agrega por localidad y banda de área",
            ("la fuente NO declara el tamaño de la muestra (N) del análisis"),
            ("la vigencia es a nivel de MES según el texto de la fuente, no una fecha "
             "exacta por registro"),
        ],
        "declaracion": ("Referencia agregada de mercado publicada por el geoportal "
                        "municipal: valor por m² de la banda de área del sujeto en su "
                        "localidad, con metodología, fuente y vigencia declaradas."),
    }
    # Si el contrato de evidencia está disponible, se CLASIFICA con él (no se reimplementa).
    if market_evidence is not None:
        referencia["clasificacion_contrato"] = market_evidence.nivel_referencia_de_origen(
            referencia["origin"], agregado=True,
            metodologia_declarada=resultado.get("metodologia_declarada")
            or resultado.get("provenance", {}).get("referencia"))
        referencia["escalera"] = market_evidence.evaluar_escalera([referencia["nivel"]])
    return referencia


def construir_gap_report(resultados: Sequence[Mapping[str, Any]],
                         referencias: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """GAP REPORT: por qué la compuerta sigue cerrada y QUÉ habría que incorporar.

    Si hay al menos una referencia LEVEL 3 utilizable, dice qué pasa de
    `CLOSED/MISSING_MARKET_EVIDENCE` a `OPEN_WITH_LIMITATIONS` y qué falta todavía para
    `OPEN` (comparables directos con área).
    """
    por_estado: Dict[str, List[str]] = {}
    for r in resultados:
        por_estado.setdefault(str(r.get("status")), []).append(str(r.get("source_id")))
    utiles = [r for r in resultados if r.get("usable_for_estimation")]
    hay_nivel_3 = bool(referencias)

    if hay_nivel_3:
        r0 = referencias[0]
        rango = r0.get("rango_valor_m2") or {}
        estado_transicion = {
            "desde": {"ESTIMATION_GATE": "CLOSED",
                      "motivo_cierre": "MISSING_MARKET_EVIDENCE"},
            "hacia": {"ESTIMATION_GATE": "OPEN_WITH_LIMITATIONS"},
            "por_que": (f"se incorpora UNA referencia agregada LEVEL 3 con origen "
                        f"{r0.get('origin')} y procedencia completa: valor por m² de la "
                        f"banda {r0.get('banda_area_m2')} m² en "
                        f"{r0.get('sector_referencia')!r}, rango "
                        f"{rango.get('min')}–{rango.get('max')} COP/m², publicada por el "
                        f"geoportal municipal con metodología y vigencia declaradas"),
            "no_alcanza_para_OPEN": (
                "LEVEL 3 agrega por localidad y banda de área: NO acredita la unidad. "
                "`OPEN` exige evidencia de calidad HIGH/MEDIUM y comparables directos "
                "(LEVEL 1) con área, precio y ubicación de la MISMA unidad observada."),
        }
    else:
        estado_transicion = {
            "desde": {"ESTIMATION_GATE": "CLOSED",
                      "motivo_cierre": "MISSING_MARKET_EVIDENCE"},
            "hacia": {"ESTIMATION_GATE": "CLOSED",
                      "motivo_cierre": "MISSING_MARKET_EVIDENCE"},
            "por_que": "ninguna capa consultada declaró valor de mercado por m² de la banda del sujeto",
        }

    fuentes_necesarias = [
        {
            "prioridad": 1,
            "fuente_automatica": "Geoportal municipal de Barranquilla · observatorio/valoresm2_area (layer de la banda del sujeto)",
            "url_servicio": (f"{BASE_PORTAL}/observatorio/valoresm2_area/MapServer"),
            "estado_actual": "YA INCORPORADA" if hay_nivel_3 else "NO INCORPORADA",
            "campos_que_debe_declarar": ["nombre (localidad)", "area_construida (banda m²)",
                                          "min_valor_m2", "max_valor_m2",
                                          "metodologia (texto)", "vigencia (desde/hasta)",
                                          "sample_size (N del análisis)"],
            "campos_que_faltan_hoy": (["sample_size (N)"] if hay_nivel_3 else
                                      ["todos"]),
            "por_que": ("es la ÚNICA capa pública hallada que declara valor de mercado por "
                        "m² de área construida para la banda 36-60 m², que contiene los "
                        "58,75 m² del sujeto"),
        },
        {
            "prioridad": 2,
            "fuente_automatica": "Geoportal municipal de Barranquilla · observatorio/valorcompraventas (registro individual)",
            "url_servicio": (f"{BASE_PORTAL}/observatorio/valorcompraventas/MapServer"),
            "estado_actual": "NO INCORPORADA — falta el campo de área",
            "campos_que_debe_declarar": ["valor_millones", "fecha_captura_oferta",
                                          "condicion_predio", "destinacion_economica",
                                          "area_construida_m2 (NO EXISTE HOY)",
                                          "numero_predial o dirección (NO EXISTE HOY)"],
            "campos_que_faltan_hoy": ["area_construida_m2", "identificador del inmueble"],
            "por_que": ("publica cada compraventa con valor y fecha (6792 registros en "
                        "2025; 178 en 300 m del sujeto, todos PH_Unidad_Predial "
                        "Habitacional) pero SIN área: sin área no hay valor/m² y NO se "
                        "deriva dividiendo por el área del sujeto. Es la vía más corta de "
                        "LEVEL 2 → LEVEL 1."),
        },
        {
            "prioridad": 3,
            "fuente_automatica": "SNR — Superintendencia de Notariado y Registro (microdatos de compraventa)",
            "url_servicio": "https://www.supernotariado.gov.co/ (datos abiertos de compraventas)",
            "estado_actual": "NO INCORPORADA",
            "campos_que_debe_declarar": ["fecha de escritura", "valor de la transacción",
                                          "área del inmueble", "número predial (NUPRE)",
                                          "municipio/barrio", "tipo de inmueble"],
            "campos_que_faltan_hoy": ["descarga automática con área y número predial"],
            "por_que": ("es la FUENTE PRIMARIA que el propio geoportal declara estar "
                        "usando; acceder al microdato con área y NUPRE permitiría "
                        "comparables con distancia real al sujeto (LEVEL 1)"),
        },
        {
            "prioridad": 4,
            "fuente_automatica": "Geoportal municipal de Barranquilla · observatorio/arrendamientos",
            "url_servicio": (f"{BASE_PORTAL}/observatorio/arrendamientos/MapServer"),
            "estado_actual": "INCORPORADA COMO CONTEXTO (no sostiene cifra)",
            "campos_que_debe_declarar": ["codigo_manzana", "cantidad_ofertas",
                                          "valor_promedio", "valor_minimo", "valor_maximo",
                                          "tasa_de_capitalización (NO EXISTE HOY)",
                                          "área de la unidad (NO EXISTE HOY)"],
            "campos_que_faltan_hoy": ["tasa de capitalización declarada", "área por oferta"],
            "por_que": ("ya trae canon declarado para la manzana exacta del sujeto "
                        "(48 ofertas en 2024); con una tasa de capitalización DECLARADA "
                        "podría sostener un método de capitalización de rentas"),
        },
    ]

    return {
        "version_gap": "market-harvest-gap/1.0.0",
        "mision": ("decir con exactitud qué fuente automática habría que incorporar para "
                   "pasar de ESTIMATION_GATE=CLOSED/MISSING_MARKET_EVIDENCE a "
                   "OPEN_WITH_LIMITATIONS"),
        "resumen": {
            "capas_consultadas": len(resultados),
            "capas_ok": len(por_estado.get(STATUS_OK, [])),
            "no_match": len(por_estado.get(STATUS_NO_MATCH, [])),
            "source_unavailable": len(por_estado.get(STATUS_SOURCE_UNAVAILABLE, [])),
            "query_failed": len(por_estado.get(STATUS_QUERY_FAILED, [])),
            "not_supported": len(por_estado.get(STATUS_NOT_SUPPORTED, [])),
            "usables_para_estimacion": len(utiles),
            "referencias_nivel_3": len(referencias),
            "por_estado": {k: sorted(v) for k, v in sorted(por_estado.items())},
        },
        "transicion_de_compuerta": estado_transicion,
        "fuentes_que_hay_que_incorporar": fuentes_necesarias,
        "regla_ausencia": ("una capa que no responde es SOURCE_UNAVAILABLE, NO NO_MATCH: "
                           "la ausencia de dato NO se convierte en una afirmación sobre el "
                           "mercado"),
    }


def construir_artefacto(sujeto: Sujeto, resultados: Sequence[Mapping[str, Any]], *,
                        referencias: Optional[Sequence[Mapping[str, Any]]] = None
                        ) -> Dict[str, Any]:
    """Artefacto completo del harvest: por capa + LEVEL 3 + GAP REPORT."""
    referencias = list(referencias or [])
    por_capa: Dict[str, Any] = {}
    for r in resultados:
        clave = r.get("servicio") or r.get("source_id")
        por_capa[clave] = {
            "source_id": r.get("source_id"),
            "service_url": r.get("service_url"),
            "layer_id": r.get("layer_id"),
            "layer_name": r.get("layer_name"),
            "http_status": r.get("http_status"),
            "consulted_at": r.get("consulted_at"),
            "bytes": r.get("bytes"),
            "sha256": r.get("sha256"),
            "status": r.get("status"),
            "status_scope": r.get("status_scope"),
            "status_punto_sujeto": r.get("status_punto_sujeto"),
            "value_or_range": r.get("value_or_range"),
            "tipo_referencia": r.get("tipo_referencia"),
            "banda_area_m2": r.get("banda_area_m2"),
            "effective_from": r.get("effective_from"),
            "effective_to": r.get("effective_to"),
            "effective_basis": r.get("effective_basis"),
            "effective_precision": r.get("effective_precision"),
            "metodologia_declarada": r.get("metodologia_declarada"),
            "sample_size": r.get("sample_size"),
            "sample_size_declarado_por": r.get("sample_size_declarado_por"),
            "usable_for_estimation": r.get("usable_for_estimation"),
            "origin": r.get("origin"),
            "origin_declarado": r.get("origin_declarado"),
            "origin_gate": r.get("origin_gate"),
            "origin_blockers": r.get("origin_blockers"),
            "provenance_faltante": r.get("provenance_faltante"),
            "cf_ray": r.get("cf_ray"),
            "n_features": r.get("n_features"),
            "reason": r.get("reason"),
            "provenance": r.get("provenance"),
            "queries": r.get("queries"),
            "notas": r.get("notas"),
        }
    return {
        "version_harvest": VERSION_HARVEST,
        "folio": sujeto.folio,
        "sujeto": sujeto.to_dict(),
        "generado_por": "api/market_harvest.py",
        "proveedor": PROVEEDOR_PORTAL,
        "portal": BASE_PORTAL,
        "capas": por_capa,
        "level_3_referencias": referencias,
        "GAP_REPORT": construir_gap_report(resultados, referencias),
        "declaracion": ("Adquisición AUTOMÁTICA de evidencia de mercado real. Cero valores "
                        "inventados: lo que la fuente declara viaja literal; lo que no "
                        "declara viaja en null con el motivo. Ausencia ≠ NO_MATCH."),
    }


# ══════════════════════════════════════════════════════════════════════════════
# 9 · CLI — adquiere el Golden REAL y escribe los artefactos
# ══════════════════════════════════════════════════════════════════════════════
ROOT = Path(__file__).resolve().parent.parent
MANIFEST_GOLDEN = (ROOT / "docs" / "forensics" / "040-646406" / "dictus_2b"
                   / "DICTUS_MANIFEST_040-646406.json")
RAW_DIR = ROOT / "docs" / "estimation" / "raw"
SALIDA_GOLDEN = ROOT / "docs" / "estimation" / "MARKET_HARVEST_040-646406.json"


def _market_evidence():
    """Importa `api/market_evidence.py` para CLASIFICAR con el contrato existente."""
    try:
        import market_evidence          # noqa: PLC0415
        return market_evidence
    except Exception:                   # noqa: BLE001
        try:
            sys.path.insert(0, str(ROOT / "api"))
            import market_evidence      # noqa: PLC0415,F811
            return market_evidence
        except Exception:               # noqa: BLE001
            return None


def main(argv: Optional[Sequence[str]] = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    manifest = MANIFEST_GOLDEN
    if "--manifest" in argv:
        manifest = Path(argv[argv.index("--manifest") + 1])
    sujeto = sujeto_desde_manifest(manifest)
    print(f"sujeto: folio={sujeto.folio} barrio={sujeto.barrio} "
          f"localidad={sujeto.localidad} manzana={sujeto.codigo_manzana} "
          f"area={sujeto.area_m2} m² punto={sujeto.punto_wgs84}")

    me = _market_evidence()
    resultados = adquirir_todas(sujeto, out_dir=RAW_DIR)

    referencias: List[Dict[str, Any]] = []
    for r in resultados:
        ref = referencia_nivel_3(r, sujeto, market_evidence=me)
        print(f"  {r['source_id']:34s} [{r['http_status']}] {str(r['bytes']):>7} B "
              f"sha={str(r['sha256'])[:8]} {r['status']:<18} "
              f"usable={r['usable_for_estimation']}")
        if ref is not None:
            referencias.append(ref)

    artefacto = construir_artefacto(sujeto, resultados, referencias=referencias)
    SALIDA_GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    SALIDA_GOLDEN.write_text(json.dumps(artefacto, ensure_ascii=False, indent=2),
                             encoding="utf-8")
    print(f"\nGAP_REPORT: {json.dumps(artefacto['GAP_REPORT']['resumen'], ensure_ascii=False)}")
    print(f"escrito: {SALIDA_GOLDEN}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

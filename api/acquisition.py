# -*- coding: utf-8 -*-
"""ARHIAX RE — MODO DE ADQUISICIÓN POR FUENTE (LIVE / SNAPSHOT / FALLBACK AUTORIZADO).

Este módulo separa explícitamente los DOS estados que el Source Pack venía mezclando:

  · **CONTRACT_FROZEN** — el CONTRATO está cerrado: registro completo con metadata real,
    market formalizada, binding tipado, precedencia determinista, escalera de resolución,
    licencias documentadas y —ahora— modo de adquisición declarado por fuente.
  · **OPERATIONAL_READY** — además, los dominios CORE tienen una RUTA AUTOMÁTICA VÁLIDA
    HOY (consulta en vivo que responde, snapshot automático dentro de su `freshness_policy`,
    o fallback autorizado vigente). Un CORE que solo puede declararse `SOURCE_UNAVAILABLE`
    NO es «operativo»: es una ausencia declarada, y este módulo la mide en vez de taparla.

Reglas duras (§1 / §2 / §27 + decisión de producto):

  · Vocabulario CERRADO de modos: `LIVE_QUERY` | `AUTOMATED_SNAPSHOT` | `AUTHORIZED_FALLBACK`.
  · Si `LIVE_QUERY` falla (`SOURCE_UNAVAILABLE` / `NOT_SUPPORTED` / `QUERY_FAILED`) y existe
    un snapshot automático dentro de su `freshness_policy`, se resuelve DESDE EL SNAPSHOT.
  · El dato CONSERVA la `authority_class` de la fuente ORIGINAL: nunca se degrada por venir
    de un snapshot (`provenance.original_authority_class`).
  · Un snapshot VENCIDO (fuera de `freshness_policy`) **NO resuelve**: se declara con su
    estado y se sigue la escalera (`api/source_resolution.py`), que no se reimplementa aquí.
  · Los snapshots se DESCUBREN del repositorio (hash real, fecha real). Nada se inventa: los
    artefactos hallados pero no declarados quedan en el inventario como NO utilizables.

Determinismo: el hash de CONTENIDO de un snapshot es su sha256; `queried_at`/`run_id` quedan
FUERA de todo hash de contenido (ver `hash_contenido` y la prueba de reproducibilidad).

Documentación: `docs/source_pack/ACQUISITION_MODES.md` ·
matriz computada: `docs/source_pack/SOURCE_ACQUISITION_MATRIX_040-646406.csv` ·
inventario real: `docs/source_pack/SNAPSHOT_INVENTORY.json`.

CLI:
    python -m api.acquisition --estado            # veredicto + cobertura CORE (offline)
    python -m api.acquisition --inventario        # inventario de snapshots (JSON a stdout)
    python -m api.acquisition --escribir          # sella registro/gemelo, matriz e inventario
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
import sys
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

try:  # importable como paquete (`api.acquisition`) y como módulo plano (patrón de los tests)
    from . import dictus_sources as ds
    from . import source_resolution as sr
except ImportError:  # pragma: no cover — import plano cuando `api/` está en sys.path
    import dictus_sources as ds  # type: ignore[no-redef]
    import source_resolution as sr  # type: ignore[no-redef]

__all__ = [
    "PACK_ETIQUETA",
    # vocabularios cerrados
    "ACQUISITION_MODES", "LIVE_QUERY", "AUTOMATED_SNAPSHOT", "AUTHORIZED_FALLBACK",
    "PRODUCT_ROLES", "CORE_IDENTITY", "CORE_NORMATIVE", "CORE_RISK", "CORE_MARKET",
    "DECISION_CONTEXT", "OPTIONAL_ENRICHMENT", "ROLES_CORE",
    "ESTADOS_SNAPSHOT", "SNAPSHOT_VIGENTE", "SNAPSHOT_VENCIDO", "SNAPSHOT_NO_UTILIZABLE",
    "SNAPSHOT_AUSENTE",
    "FRESHNESS_DEFAULT", "FAMILIAS_FUENTE",
    # frescura / modos
    "familia_de_fuente", "freshness_de_fuente", "rol_de_fuente", "requisitos_de_rol",
    "modos_por_fuente", "evaluar_vigencia", "snapshot_para", "modo_efectivo_de_fuente",
    "fecha_de_referencia",
    # snapshots reales
    "SNAPSHOTS_DECLARADOS", "RAICES_ESCANEO", "descubrir_snapshots", "inventario_snapshots",
    "escribir_inventario", "hash_archivo", "fecha_de_creacion_de_archivo",
    # orquestación (usa la escalera, no la reimplementa)
    "resolver_con_acquisition_mode", "resolver_dominio_con_acquisition_mode",
    "provenance_adquisicion", "resolver_identidad_canonica", "leer_golden",
    "payload_efectivo", "resultado_efectivo", "leer_matriz",
    "partes_del_folio", "marcadores_de_unidad", "analisis_unidad",
    "consultas_de_la_corrida_congelada", "MODOS_SNAPSHOT_CLASE",
    # producto / aceptación
    "matriz_roles", "escribir_matriz", "estado_operativo", "sellar_registro",
    "escribir_registro_gemelo", "sellar_manifest", "hash_contenido",
    "DOMINIOS_DECLARADOS", "COLUMNAS_MATRIZ",
]

PACK_ETIQUETA = "barranquilla-source-pack/1.0.0 · acquisition-modes/1"

RAIZ = Path(__file__).resolve().parent.parent
DIR_PACK = RAIZ / "docs" / "source_pack"
RUTA_REGISTRO = DIR_PACK / "barranquilla_sources_v1.json"
RUTA_REGISTRO_YAML = DIR_PACK / "barranquilla_sources_v1.yaml"
RUTA_MANIFEST = DIR_PACK / "BARRANQUILLA_SOURCE_PACK_MANIFEST.json"
RUTA_MATRIZ_LEGACY = DIR_PACK / "SOURCE_COVERAGE_MATRIX_040-646406.csv"
RUTA_MATRIZ = DIR_PACK / "SOURCE_ACQUISITION_MATRIX_040-646406.csv"
RUTA_INVENTARIO = DIR_PACK / "SNAPSHOT_INVENTORY.json"
RUTA_RUN_STATE = (RAIZ / "docs" / "forensics" / "040-646406" / "dictus_2b"
                  / "DICTUS_RUN_STATE_040-646406.json")
RUTA_CAPTURA_OSM = DIR_PACK / "raw" / "golden" / "osm_overpass.json"
RUTA_PROBE_GEOPORTAL = DIR_PACK / "raw" / "golden" / "_layers_probe.json"

# Fecha de referencia de la ventana de congelación. Se DECLARA en el registro
# (`reference_date`) para que la frescura sea determinista y no dependa del reloj de la
# máquina: «¿sirve hoy?» significa «¿sirve en la ventana congelada del pack?».
REFERENCE_DATE_POR_DEFECTO = "2026-09-29"

# ══════════════════════════════════════════════════════════════════════════════
# §1 · VOCABULARIO CERRADO DE MODOS DE ADQUISICIÓN
# ══════════════════════════════════════════════════════════════════════════════
LIVE_QUERY = "LIVE_QUERY"
AUTOMATED_SNAPSHOT = "AUTOMATED_SNAPSHOT"
AUTHORIZED_FALLBACK = "AUTHORIZED_FALLBACK"
ACQUISITION_MODES = (LIVE_QUERY, AUTOMATED_SNAPSHOT, AUTHORIZED_FALLBACK)

# Clase del artefacto que respalda cada modo.
MODOS_SNAPSHOT_CLASE = {
    AUTOMATED_SNAPSHOT: "AUTOMATED_SNAPSHOT_ARTIFACT",
    AUTHORIZED_FALLBACK: "AUTHORIZED_FALLBACK_ARTIFACT",
}

ESTADOS_SIN_DATO_DE_CONTRATO = tuple(ds.ESTADOS_SIN_DATO) + (ds.CONSULTA_FALLIDA,)

# ══════════════════════════════════════════════════════════════════════════════
# §B · ROL DE PRODUCTO POR FUENTE (vocabulario CERRADO de 6)
# ══════════════════════════════════════════════════════════════════════════════
CORE_IDENTITY = "CORE_IDENTITY"
CORE_NORMATIVE = "CORE_NORMATIVE"
CORE_RISK = "CORE_RISK"
CORE_MARKET = "CORE_MARKET"
DECISION_CONTEXT = "DECISION_CONTEXT"
OPTIONAL_ENRICHMENT = "OPTIONAL_ENRICHMENT"
PRODUCT_ROLES = (CORE_IDENTITY, CORE_NORMATIVE, CORE_RISK, CORE_MARKET, DECISION_CONTEXT,
                 OPTIONAL_ENRICHMENT)
ROLES_CORE = (CORE_IDENTITY, CORE_NORMATIVE, CORE_RISK, CORE_MARKET)

# Regla DECLARADA de `required_for_decision` / `blocking_if_missing`:
#   · rol CORE                        → requerido para decidir  Y bloquea si falta;
#   · DECISION_CONTEXT                → requerido para decidir, NO bloquea si falta;
#   · OPTIONAL_ENRICHMENT             → ni requerido ni bloqueante.
# Guarda adicional: una capa HISTORICAL_REFERENCE es REFERENCIA (nunca operativa), así que
# su ausencia no es requerida ni bloqueante aunque su familia sea CORE.
REQUISITOS_POR_ROL = {
    CORE_IDENTITY: {"required_for_decision": True, "blocking_if_missing": True},
    CORE_NORMATIVE: {"required_for_decision": True, "blocking_if_missing": True},
    CORE_RISK: {"required_for_decision": True, "blocking_if_missing": True},
    CORE_MARKET: {"required_for_decision": True, "blocking_if_missing": True},
    DECISION_CONTEXT: {"required_for_decision": True, "blocking_if_missing": False},
    OPTIONAL_ENRICHMENT: {"required_for_decision": False, "blocking_if_missing": False},
}
REQUISITOS_HISTORICA = {"required_for_decision": False, "blocking_if_missing": False}

PRODUCT_ROLE_POR_FUENTE: Dict[str, str] = {
    "CATASTRO_BAQ_ADOPCION_ANEXO1": CORE_IDENTITY,
    "CATASTRO_BAQ_CONSTRUCCION": DECISION_CONTEXT,
    "CATASTRO_BAQ_DESTINO_ECONOMICO": DECISION_CONTEXT,
    "CATASTRO_BAQ_DIRECCION": CORE_IDENTITY,
    "CATASTRO_BAQ_MANZANA": DECISION_CONTEXT,
    "CATASTRO_BAQ_PREDIO": CORE_IDENTITY,
    "CATASTRO_BAQ_TERRENO": CORE_IDENTITY,
    "GOOGLE_STREET_VIEW": OPTIONAL_ENRICHMENT,
    "LONJA_MARKET_BAQ": CORE_MARKET,
    "MAPILLARY": OPTIONAL_ENRICHMENT,
    "OSM_OVERPASS": OPTIONAL_ENRICHMENT,
    "POT_BAQ_AREAS_ACTIVIDAD": CORE_NORMATIVE,
    "POT_BAQ_BARRIOS": DECISION_CONTEXT,
    "POT_BAQ_EDIFICABILIDAD": CORE_NORMATIVE,
    "POT_BAQ_ESTRATIFICACION": DECISION_CONTEXT,
    "POT_BAQ_INUNDACION_2024": CORE_RISK,
    "POT_BAQ_INUNDACION_HIST": CORE_RISK,
    "POT_BAQ_LOCALIDADES": DECISION_CONTEXT,
    "POT_BAQ_POLIGONOS_USO": CORE_NORMATIVE,
    "POT_BAQ_REMOCION_2024": CORE_RISK,
    "POT_BAQ_REMOCION_HIST": CORE_RISK,
    "POT_BAQ_RIESGO_2024": CORE_RISK,
    "POT_BAQ_RIESGO_HIST": CORE_RISK,
    "POT_BAQ_TRATAMIENTO": CORE_NORMATIVE,
    "SHADOW_FACADE_EXPOSURE": DECISION_CONTEXT,
    "SOLAR_ENGINE": DECISION_CONTEXT,
}
PRODUCT_ROLE_POR_PREFIJO: Dict[str, str] = {"EQUIPAMIENTO_": DECISION_CONTEXT}

# ══════════════════════════════════════════════════════════════════════════════
# §1 · MODO DE ADQUISICIÓN DECLARADO POR FUENTE
# ══════════════════════════════════════════════════════════════════════════════
# `acquisition_mode` declara la RUTA PRIMARIA por la que el pack adquiere la fuente:
#   · LIVE_QUERY          → hay servicio que se consulta en vivo en cada corrida;
#   · AUTOMATED_SNAPSHOT  → la ruta primaria es la copia empaquetada y hasheada de la
#                           respuesta de la MISMA fuente (capa POT, captura de Overpass);
#   · AUTHORIZED_FALLBACK → la ruta primaria es un INSTRUMENTO autorizado distinto de la
#                           respuesta del servicio (registro de adopción: documento
#                           oficial normalizado; metodología de la Lonja: documento
#                           contractual autorizado dentro del motor TMA).
# El modo REALMENTE USADO se registra por resultado (`acquisition_mode` en el resultado):
# una fuente LIVE_QUERY que cae puede resolverse por AUTOMATED_SNAPSHOT sin perder su
# `authority_class` original.
MODO_POR_FUENTE: Dict[str, str] = {
    "CATASTRO_BAQ_ADOPCION_ANEXO1": AUTHORIZED_FALLBACK,
    "LONJA_MARKET_BAQ": AUTHORIZED_FALLBACK,
    # Fuentes CALCULADAS: no hay servicio que consultar y su valor NO es un snapshot (se
    # recalcula en cada corrida) → su ruta es la ejecución en vivo del cálculo local.
    "SOLAR_ENGINE": LIVE_QUERY,
    "SHADOW_FACADE_EXPOSURE": LIVE_QUERY,
}
MODO_POR_DEFECTO = LIVE_QUERY

# ══════════════════════════════════════════════════════════════════════════════
# §1 · FRESCURA DECLARADA POR FAMILIA DE FUENTE (días)
# ══════════════════════════════════════════════════════════════════════════════
FRESHNESS_DEFAULT: Dict[str, Dict[str, Any]] = {
    "CATASTRO": {
        "dias": 90,
        "fundamento": ("El registro catastral se actualiza por resolución de adopción y por "
                       "anualidad: una copia de más de un trimestre no puede sostener la "
                       "identidad ni el destino vigente."),
    },
    "POT": {
        "dias": 365,
        "fundamento": ("El POT vigente (Decreto 893 de 2024) no cambia dentro del año: un "
                       "snapshot anual es vigente para uso/tratamiento/edificabilidad."),
    },
    "RIESGO": {
        "dias": 365,
        "fundamento": ("Las capas de amenaza del POT vigente se publican con el POT: se "
                       "acepta una copia de hasta un año, nunca una capa sin sello."),
    },
    "EQUIPAMIENTO": {
        "dias": 365,
        "fundamento": "El equipamiento oficial se publica por POT/anuario municipal.",
    },
    "MERCADO": {
        "dias": 180,
        "fundamento": ("La metodología de valoración tiene vigencia trimestral/semestral "
                       "declarada en el propio artefacto: media anualidad es el máximo."),
    },
    "CONTEXTO": {
        "dias": 30,
        "fundamento": ("El contexto del entorno (OSM) cambia de forma continua: una captura "
                       "de más de un mes se declara vencida."),
    },
    "CONTEXTO_IMAGEN": {
        "dias": 30,
        "fundamento": ("Una imagen de fachada solo describe el estado del inmueble en su "
                       "fecha de captura: se exige captura reciente."),
    },
    "CALCULADA": {
        "dias": 1,
        "fundamento": ("Un resultado CALCULADO vale para la corrida que lo produjo: se "
                       "recalcula siempre, nunca se reutiliza de un snapshot."),
    },
}
FAMILIAS_FUENTE = tuple(sorted(FRESHNESS_DEFAULT))

FAMILIA_POR_PREFIJO: Tuple[Tuple[str, str], ...] = (
    ("CATASTRO_", "CATASTRO"),
    ("EQUIPAMIENTO_", "EQUIPAMIENTO"),
    ("GOOGLE_", "CONTEXTO_IMAGEN"),
    ("LONJA_", "MERCADO"),
    ("MAPILLARY", "CONTEXTO_IMAGEN"),
    ("OSM_", "CONTEXTO"),
    ("POT_", "POT"),
    ("SHADOW_", "CALCULADA"),
    ("SOLAR_", "CALCULADA"),
)
# Excepciones declaradas (la familia NO se adivina: se declara).
FAMILIA_POR_FUENTE: Dict[str, str] = {
    "POT_BAQ_REMOCION_2024": "RIESGO",
    "POT_BAQ_REMOCION_HIST": "RIESGO",
    "POT_BAQ_INUNDACION_2024": "RIESGO",
    "POT_BAQ_INUNDACION_HIST": "RIESGO",
    "POT_BAQ_RIESGO_2024": "RIESGO",
    "POT_BAQ_RIESGO_HIST": "RIESGO",
}

# ══════════════════════════════════════════════════════════════════════════════
# INVENTARIO DE SNAPSHOTS REALES DEL REPOSITORIO
# ══════════════════════════════════════════════════════════════════════════════
SNAPSHOT_AUSENTE = "AUSENTE"
SNAPSHOT_VIGENTE = "VIGENTE"
SNAPSHOT_VENCIDO = "VENCIDO"
SNAPSHOT_NO_UTILIZABLE = "NO_UTILIZABLE"
ESTADOS_SNAPSHOT = (SNAPSHOT_AUSENTE, SNAPSHOT_VIGENTE, SNAPSHOT_VENCIDO,
                    SNAPSHOT_NO_UTILIZABLE)

# Consulta declarada de cada artefacto (cómo se extrae el atributo del snapshot).
CONSULTA_PUNTO_EN_POLIGONO = "PUNTO_EN_POLIGONO"
CONSULTA_REGISTRO_POR_IDENTIFICADOR = "REGISTRO_POR_IDENTIFICADOR"
CONSULTA_SECTOR_POR_BARRIO = "SECTOR_POR_BARRIO"
CONSULTA_CAPTURA_CONTEXTO = "CAPTURA_CONTEXTO"

# Artefactos DECLARADOS usables, con la evidencia que los respalda. `origen_declarado`
# cita el campo del REGISTRO que autoriza el uso (nunca una decisión de este módulo).
SNAPSHOTS_DECLARADOS: Tuple[Dict[str, Any], ...] = (
    {
        "artifact_id": "SNAP_POT_REMOCION_MASA",
        "ruta": "api/data/amenaza_remocion_masa.geojson",
        "kind": "PACKAGED_GEOJSON",
        "modo": AUTOMATED_SNAPSHOT,
        "fuentes": ("POT_BAQ_REMOCION_2024",),
        "atributos": ("remocion",),
        "consulta": CONSULTA_PUNTO_EN_POLIGONO,
        "campo_nivel": "niveldeamenaza",
        "campo_atributo": "amenaza",
        "campos_vigencia": (),
        "origen_declarado": ("`local_fallback` de POT_BAQ_REMOCION_2024 en el registro "
                            "(copia empaquetada de la capa POT vigente)"),
        "usable": True,
        "motivo_no_usable": "",
    },
    {
        "artifact_id": "SNAP_POT_AREAS_EN_RIESGO",
        "ruta": "api/data/areas_en_riesgo.geojson",
        "kind": "PACKAGED_GEOJSON",
        "modo": AUTOMATED_SNAPSHOT,
        "fuentes": ("POT_BAQ_RIESGO_2024",),
        "atributos": ("riesgo",),
        "consulta": CONSULTA_PUNTO_EN_POLIGONO,
        "campo_nivel": "nivelderiesgo",
        "campo_atributo": "riesgo",
        "campos_vigencia": (),
        "origen_declarado": ("`local_fallback` de POT_BAQ_RIESGO_2024 en el registro "
                            "(copia empaquetada de la capa POT vigente)"),
        "usable": True,
        "motivo_no_usable": "",
    },
    {
        "artifact_id": "SNAP_ADOPCION_CATASTRAL_ANEXO1",
        "ruta": "api/data/barranquilla_adopcion_anexo1.json",
        "kind": "PACKAGED_REGISTRY",
        "modo": AUTHORIZED_FALLBACK,
        "fuentes": ("CATASTRO_BAQ_ADOPCION_ANEXO1",),
        "atributos": ("identidad_nupre",),
        "consulta": CONSULTA_REGISTRO_POR_IDENTIFICADOR,
        "campo_nivel": "",
        "campo_atributo": "",
        "campos_clave": ("numero_predial", "codigo_homologado", "fmi", "codigo_registral"),
        "campos_vigencia": (),
        "origen_declarado": ("`fallback_policy` de CATASTRO_BAQ_ADOPCION_ANEXO1: «Fallback "
                            "AUTORITATIVO exacto cuando el MapServer no responde; es un "
                            "registro estático con hash»"),
        "usable": True,
        "motivo_no_usable": "",
    },
    {
        "artifact_id": "SNAP_LONJA_METODOLOGIA",
        "ruta": ("motor_tma_lonja_baq_v1.0/motor_tma_lonja_baq_v1.0/lonja_layer/"
                 "lonja_baq_metodologia.yaml"),
        "kind": "PACKAGED_YAML",
        "modo": AUTHORIZED_FALLBACK,
        "fuentes": ("LONJA_MARKET_BAQ",),
        "atributos": ("mercado",),
        "consulta": CONSULTA_SECTOR_POR_BARRIO,
        "campo_nivel": "",
        "campo_atributo": "valor_m2",
        "campos_clave": ("valor_suelo_por_sector",),
        "campos_vigencia": ("declaracion.vigencia_desde", "declaracion.vigencia_hasta"),
        "origen_declarado": ("`base_url` `local:` con el identificador histórico sellado "
                             "LONJA_MARKET_BAQ (declarado NOT_A_SOURCE y fuera del Source "
                             "Registry: artefacto local de metodología, SIN documento "
                             "contractual ni institución proveedora verificada)"),
        "usable": True,
        "motivo_no_usable": "",
    },
    {
        "artifact_id": "SNAP_OSM_OVERPASS_CAPTURA",
        "ruta": "docs/source_pack/raw/golden/osm_overpass.json",
        "kind": "RAW_CAPTURE",
        "modo": AUTOMATED_SNAPSHOT,
        "fuentes": ("OSM_OVERPASS",),
        "atributos": ("servicios_de_contexto",),
        "consulta": CONSULTA_CAPTURA_CONTEXTO,
        "campo_nivel": "",
        "campo_atributo": "elementos",
        "campos_clave": (),
        "campos_vigencia": ("_capture.queried_at",),
        "origen_declarado": ("`local_fallback` de OSM_OVERPASS en el registro (captura cruda "
                            "preservada sin modificar)"),
        "usable": True,
        "motivo_no_usable": "",
    },
    # ── artefactos REALES hallados en el repo que NO se pueden usar ──────────────
    {
        "artifact_id": "SNAP_ESTRATO_PROBE_TRACES",
        "ruta": "docs/forensics/040-646406/golden_03i1/ESTRATO_PROBE_TRACE.json",
        "kind": "PROBE_TRACE",
        "modo": "",
        "fuentes": ("POT_BAQ_ESTRATIFICACION",),
        "atributos": (),
        "consulta": "",
        "campo_nivel": "",
        "campo_atributo": "",
        "campos_vigencia": (),
        "origen_declarado": ("Sonda 03I.1 declarada en `evidence_base` del registro como "
                            "«consultas en vivo documentadas»"),
        "usable": False,
        "motivo_no_usable": ("La captura devuelve las MANZANAS DEL BUFFER de 150 m "
                            "(codigo_manzana ...006/...007) y el predio Golden está en la "
                            "manzana ...004: usarla para afirmar el estrato del predio sería "
                            "una inferencia ESPACIAL por vecindad, prohibida para un dato "
                            "oficial (BINDING_ESPACIAL_CONTEXTO no autoriza identidad ni "
                            "hecho oficial)."),
    },
    {
        "artifact_id": "SNAP_CATASTRO_PREDIO_FIXTURE",
        "ruta": "docs/source_pack/raw/golden/catastro_baq_predio.json",
        "kind": "TEST_FIXTURE",
        "modo": "",
        "fuentes": ("CATASTRO_BAQ_PREDIO",),
        "atributos": (),
        "consulta": "",
        "campo_nivel": "",
        "campo_atributo": "",
        "campos_vigencia": (),
        "origen_declarado": ("El propio registro lo declara: evidence.origin="
                            "ARTEFACTO_DE_PRUEBA, capture_file de "
                            "tests/test_source_pack_contract.py"),
        "usable": False,
        "motivo_no_usable": ("Es un fixture escrito por una prueba, NO una respuesta de "
                            "servicio: usarlo como evidencia sería fabricar el dato."),
    },
)

# Raíces que se ESCANEAN para no ocultar ningún artefacto real del repositorio.
RAICES_ESCANEO: Tuple[str, ...] = (
    "api/data",
    "docs/source_pack/raw/golden",
    "docs/forensics/040-646406/golden_03i1",
    "motor_tma_lonja_baq_v1.0",
)
PATRONES_ESCANEO: Tuple[str, ...] = ("*.geojson", "*.json", "*.yaml", "*.yml", "*.csv")

# ══════════════════════════════════════════════════════════════════════════════
# DOMINIOS DE LA MATRIZ (los 18 dominios de cobertura del pack)
# ══════════════════════════════════════════════════════════════════════════════
COLUMNAS_MATRIZ: Tuple[str, ...] = (
    "domain", "source_id", "product_role", "status", "binding", "normalized_result",
    "authority", "provenance", "raw_hash", "required_for_decision", "blocking_if_missing",
)

DOMINIOS_DECLARADOS: Tuple[Dict[str, Any], ...] = (
    {"domain": "identidad", "fuente": "CATASTRO_BAQ_ADOPCION_ANEXO1",
     "atributo": "identidad_nupre", "identidad": True},
    {"domain": "direccion", "fuente": "CATASTRO_BAQ_DIRECCION",
     "atributo": "direccion_predio", "identidad": True},
    {"domain": "predio", "fuente": "CATASTRO_BAQ_PREDIO", "atributo": "predio",
     "identidad": True},
    {"domain": "construccion", "fuente": "CATASTRO_BAQ_CONSTRUCCION",
     "atributo": "altura_fisica", "identidad": False},
    {"domain": "barrio", "fuente": "POT_BAQ_BARRIOS", "atributo": "barrio",
     "identidad": False},
    {"domain": "localidad", "fuente": "POT_BAQ_LOCALIDADES", "atributo": "localidad",
     "identidad": False},
    {"domain": "destino", "fuente": "CATASTRO_BAQ_DESTINO_ECONOMICO",
     "atributo": "destino_catastral", "identidad": False},
    {"domain": "uso_pot", "fuente": "POT_BAQ_POLIGONOS_USO", "atributo": "uso_pot",
     "identidad": False},
    {"domain": "tratamiento", "fuente": "POT_BAQ_TRATAMIENTO", "atributo": "tratamiento",
     "identidad": False},
    {"domain": "edificabilidad", "fuente": "POT_BAQ_EDIFICABILIDAD",
     "atributo": "edificabilidad_altura_normativa", "identidad": False},
    {"domain": "remocion", "fuente": "POT_BAQ_REMOCION_2024", "atributo": "remocion",
     "identidad": False},
    {"domain": "inundacion", "fuente": "POT_BAQ_INUNDACION_2024", "atributo": "inundacion",
     "identidad": False},
    {"domain": "riesgo", "fuente": "POT_BAQ_RIESGO_2024", "atributo": "riesgo",
     "identidad": False},
    {"domain": "equipamiento_oficial", "fuente": "EQUIPAMIENTO_*",
     "atributo": "equipamiento_oficial", "identidad": False},
    {"domain": "servicios_contexto", "fuente": "OSM_OVERPASS",
     "atributo": "servicios_de_contexto", "identidad": False},
    {"domain": "street_imagery", "fuente": "MAPILLARY+GOOGLE_STREET_VIEW",
     "atributo": "servicios_de_contexto", "identidad": False},
    {"domain": "solar", "fuente": "SOLAR_ENGINE+SHADOW_FACADE_EXPOSURE",
     "atributo": "exposicion_solar_fachada", "identidad": False},
    {"domain": "mercado", "fuente": "LONJA_MARKET_BAQ", "atributo": "mercado",
     "identidad": False},
)


# ══════════════════════════════════════════════════════════════════════════════
# Utilidades
# ══════════════════════════════════════════════════════════════════════════════
def _norm(texto: Any) -> str:
    t = unicodedata.normalize("NFKD", str(texto if texto is not None else ""))
    return " ".join(t.encode("ascii", "ignore").decode().upper().split())


def hash_contenido(payload: Any) -> str:
    """Hash de CONTENIDO (estable, sin reloj ni identificadores de corrida).

    `queried_at`, `run_id`, `query_id` y `generado_en` se EXCLUYEN: son metadatos de la
    corrida, no contenido. Dos corridas con las MISMAS respuestas crudas producen el mismo
    `hash_contenido`.
    """
    if isinstance(payload, (bytes, bytearray)):
        return hashlib.sha256(bytes(payload)).hexdigest()
    return ds.hash_canonico(_sin_metadatos_de_corrida(payload))


_METADATOS_DE_CORRIDA = frozenset({"queried_at", "run_id", "query_id", "generado_en",
                                   "generated_at", "consultado_en", "tested_at",
                                   "source_queried_at"})


def _sin_metadatos_de_corrida(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _sin_metadatos_de_corrida(v) for k, v in obj.items()
                if k not in _METADATOS_DE_CORRIDA}
    if isinstance(obj, (list, tuple)):
        return [_sin_metadatos_de_corrida(v) for v in obj]
    return obj


def hash_archivo(ruta: Any) -> str:
    """sha256 real del archivo (0 si no existe)."""
    p = Path(ruta)
    if not p.is_absolute():
        p = RAIZ / p
    if not p.exists():
        return ""
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for bloque in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(bloque)
    return h.hexdigest()


def _ruta_absoluta(ruta: Any) -> Path:
    p = Path(ruta)
    return p if p.is_absolute() else RAIZ / p


def _ruta_relativa(p: Any) -> str:
    try:
        return str(Path(p).resolve().relative_to(RAIZ)).replace("\\", "/")
    except Exception:  # noqa: BLE001
        return str(p).replace("\\", "/")


def _mapa_fechas_de_commit() -> Dict[str, str]:
    """Última fecha de commit por archivo con UNA SOLA pasada de git (offline).

    `git log --format=%x00%cI --name-only` emite, del commit más nuevo al más viejo, la
    fecha y los archivos tocados: la PRIMERA aparición de un archivo es su último commit.
    """
    try:
        proc = subprocess.run(["git", "log", "--format=%x00%cI", "--name-only"],
                              cwd=str(RAIZ), capture_output=True, text=True, timeout=120)
    except Exception:  # noqa: BLE001 — sin git se declara el mtime
        return {}
    if proc.returncode != 0:
        return {}
    fechas: Dict[str, str] = {}
    actual = ""
    for linea in (proc.stdout or "").splitlines():
        if linea.startswith("\x00"):
            actual = linea[1:].strip()
        elif linea.strip() and actual:
            fechas.setdefault(linea.strip().replace("\\", "/"), actual)
    return fechas


def fecha_de_creacion_de_archivo(ruta: Any, *, con_git: bool = True,
                                 fechas: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Fecha de creación/commit REAL del artefacto (git; si no, mtime declarado).

    Devuelve `{"fecha": ISO8601|None, "origen": "git_commit"|"mtime_sin_commit"|"ausente",
    "detalle": ...}`. Nunca inventa una fecha: si el archivo no existe, `fecha` es None.
    """
    rel = _ruta_relativa(_ruta_absoluta(ruta))
    p = _ruta_absoluta(ruta)
    if not p.exists():
        return {"fecha": None, "origen": "ausente", "detalle": f"no existe {rel}"}
    if con_git:
        if fechas is None:
            fechas = _mapa_fechas_de_commit()
        if fechas.get(rel):
            return {"fecha": fechas[rel], "origen": "git_commit",
                    "detalle": f"git log -1 --format=%cI -- {rel}"}
    return {"fecha": datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat(),
            "origen": "mtime_sin_commit",
            "detalle": (f"sin commit en git para {rel}: se declara el mtime del archivo "
                        f"(la fecha no se inventa)")}


def _a_fecha(valor: Any) -> Optional[date]:
    if valor in (None, ""):
        return None
    texto = str(valor).strip()
    try:
        return date.fromisoformat(texto[:10])
    except ValueError:
        return None


def _dias_entre(desde: Any, hasta: Any) -> Optional[int]:
    a, b = _a_fecha(desde), _a_fecha(hasta)
    return (b - a).days if a and b else None


# ══════════════════════════════════════════════════════════════════════════════
# Registro y vocabularios
# ══════════════════════════════════════════════════════════════════════════════
def _registro(registro: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if registro is not None:
        reg = dict(registro)
        reg.setdefault("sources", {})
        return reg
    try:
        reg = ds.cargar_registro()
    except Exception as exc:  # noqa: BLE001 — la ausencia de registro es un estado
        return {"registry_version": ds.REGISTRY_VERSION, "sources": {},
                "_status": ds.NO_SOPORTADA,
                "reason": f"No se pudo cargar el registro: {type(exc).__name__}: {exc}"}
    reg = dict(reg)
    reg.setdefault("sources", {})
    return reg


def fecha_de_referencia(registro: Optional[Dict[str, Any]] = None) -> str:
    """Fecha de la ventana de congelación declarada por el pack (determinista)."""
    reg = _registro(registro)
    for clave in ("reference_date", "fecha_de_referencia"):
        if reg.get(clave):
            return str(reg[clave])[:10]
    return REFERENCE_DATE_POR_DEFECTO


def familia_de_fuente(source_id: str) -> str:
    """Familia declarada de la fuente (nunca adivinada: tabla + prefijos declarados)."""
    sid = str(source_id)
    if sid in FAMILIA_POR_FUENTE:
        return FAMILIA_POR_FUENTE[sid]
    for prefijo, familia in FAMILIA_POR_PREFIJO:
        if sid.startswith(prefijo):
            return familia
    raise KeyError(f"Fuente sin familia declarada: {sid}. Declárela en "
                   f"FAMILIA_POR_FUENTE antes de usarla.")


def freshness_de_fuente(source_id: str) -> Dict[str, Any]:
    """`freshness_policy` cuantificada de la fuente: familia, días y fundamento."""
    familia = familia_de_fuente(source_id)
    politica = dict(FRESHNESS_DEFAULT[familia])
    politica.update({"source_id": str(source_id), "familia": familia,
                     "etiqueta": f"{familia}:{politica['dias']}d"})
    return politica


def rol_de_fuente(source_id: str) -> str:
    """`product_role` declarado de la fuente (CORE_* / contexto / enriquecimiento)."""
    sid = str(source_id)
    if sid in PRODUCT_ROLE_POR_FUENTE:
        return PRODUCT_ROLE_POR_FUENTE[sid]
    for prefijo, rol in PRODUCT_ROLE_POR_PREFIJO.items():
        if sid.startswith(prefijo):
            return rol
    raise KeyError(f"Fuente sin `product_role` declarado: {sid}.")


def requisitos_de_rol(rol: str, *, precedence: Optional[str] = None) -> Dict[str, bool]:
    """`required_for_decision` / `blocking_if_missing` derivados del rol declarado.

    Una capa `HISTORICAL_REFERENCE` se trata como REFERENCIA: no es requerida ni
    bloqueante aunque su familia sea CORE (nunca es operativa).
    """
    if str(precedence or "").upper() == ds.HISTORICAL_REFERENCE:
        return dict(REQUISITOS_HISTORICA)
    if rol not in REQUISITOS_POR_ROL:
        raise KeyError(f"Rol de producto no declarado: {rol!r}. "
                       f"Vocabulario cerrado: {PRODUCT_ROLES}")
    return dict(REQUISITOS_POR_ROL[rol])


def modo_declarado_de_fuente(source_id: str, fuente: Optional[Dict[str, Any]] = None) -> str:
    """Modo de adquisición DECLARADO de la fuente (ruta primaria del pack)."""
    sid = str(source_id)
    if sid in MODO_POR_FUENTE:
        return MODO_POR_FUENTE[sid]
    f = dict(fuente or {})
    base = str(f.get("base_url") or "")
    if base.startswith("local:"):
        # Sin servicio que consultar: la ruta primaria es el artefacto del pack.
        return AUTOMATED_SNAPSHOT
    return MODO_POR_DEFECTO


# ══════════════════════════════════════════════════════════════════════════════
# Descubrimiento de snapshots REALES
# ══════════════════════════════════════════════════════════════════════════════
def _vigencia_declarada_en_artefacto(ruta: Path, campos: Sequence[str]) -> Dict[str, Any]:
    """Lee las fechas de vigencia DENTRO del artefacto (`declaracion.vigencia_*`)."""
    if not campos or not ruta.exists() or ruta.suffix.lower() not in (".yaml", ".yml"):
        return {}
    try:
        import yaml  # type: ignore
        doc = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001
        return {}
    salida: Dict[str, Any] = {}
    for campo in campos:
        actual: Any = doc
        for parte in str(campo).split("."):
            actual = actual.get(parte) if isinstance(actual, dict) else None
            if actual is None:
                break
        if actual:
            salida[campo] = actual
    return salida


def _fecha_captura_declarada(ruta: Path) -> Optional[str]:
    if not ruta.exists() or ruta.suffix.lower() != ".json":
        return None
    try:
        doc = json.loads(ruta.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    captura = doc.get("_capture") if isinstance(doc, dict) else None
    if isinstance(captura, dict) and captura.get("queried_at"):
        return str(captura["queried_at"])
    return None


def _familia_del_artefacto(declarado: Dict[str, Any]) -> str:
    fuentes = tuple(declarado.get("fuentes") or ())
    if fuentes:
        return familia_de_fuente(fuentes[0])
    return "CONTEXTO"


def descubrir_snapshots(*, con_git: bool = True,
                        declarados: Sequence[Dict[str, Any]] = SNAPSHOTS_DECLARADOS,
                        raices: Sequence[str] = RAICES_ESCANEO) -> List[Dict[str, Any]]:
    """Inventario COMPLETO de los snapshots reales del repositorio.

    Para cada artefacto devuelve: `ruta`, `fecha_de_creacion` (commit ISO o mtime declarado),
    `bytes`, `sha256`, `kind`, `fuentes`, `atributos` que puede satisfacer, `consulta`
    declarada, `vigencia_declarada_en_el_artefacto` y `usable` + `motivo_no_usable`.

    Además ESCANEA las raíces declaradas y añade todo artefacto hallado que no esté
    declarado, marcado `declarado: false` y `usable: false`: nada real queda oculto y nada
    no declarado se usa.
    """
    inventario: List[Dict[str, Any]] = []
    vistas: set = set()
    fechas = _mapa_fechas_de_commit() if con_git else {}
    for decl in declarados:
        ruta = _ruta_absoluta(decl["ruta"])
        rel = _ruta_relativa(ruta)
        vistas.add(rel)
        fecha = fecha_de_creacion_de_archivo(ruta, con_git=con_git, fechas=fechas)
        familia = _familia_del_artefacto(decl)
        vigencia = _vigencia_declarada_en_artefacto(ruta, tuple(decl.get("campos_vigencia") or ()))
        captura = _fecha_captura_declarada(ruta)
        inventario.append({
            "artifact_id": decl["artifact_id"],
            "ruta": rel,
            "declarado": True,
            "kind": decl["kind"],
            "bytes": ruta.stat().st_size if ruta.exists() else 0,
            "sha256": hash_archivo(ruta),
            "fecha_de_creacion": fecha["fecha"],
            "fecha_origen": fecha["origen"],
            "fecha_detalle": fecha["detalle"],
            "modo": decl.get("modo") or "",
            "fuentes": list(decl.get("fuentes") or ()),
            "atributos": list(decl.get("atributos") or ()),
            "consulta": decl.get("consulta") or "",
            "campo_nivel": decl.get("campo_nivel") or "",
            "campo_atributo": decl.get("campo_atributo") or "",
            "campos_clave": list(decl.get("campos_clave") or ()),
            "familia": familia,
            "freshness_dias": FRESHNESS_DEFAULT[familia]["dias"],
            "vigencia_declarada_en_el_artefacto": vigencia,
            "fecha_de_captura_declarada": captura,
            "origen_declarado": decl.get("origen_declarado") or "",
            "usable": bool(decl.get("usable", True)) and ruta.exists(),
            "motivo_no_usable": (decl.get("motivo_no_usable") or
                                 ("" if ruta.exists() else f"no existe {rel}")),
        })
    for raiz_txt in raices:
        raiz = _ruta_absoluta(raiz_txt)
        if not raiz.exists():
            continue
        for patron in PATRONES_ESCANEO:
            for ruta in sorted(raiz.rglob(patron)):
                rel = _ruta_relativa(ruta)
                if rel in vistas or "__pycache__" in rel:
                    continue
                vistas.add(rel)
                fnd = fecha_de_creacion_de_archivo(ruta, con_git=con_git, fechas=fechas)
                inventario.append({
                    "artifact_id": None,
                    "ruta": rel,
                    "declarado": False,
                    "kind": "NO_DECLARADO",
                    "bytes": ruta.stat().st_size,
                    "sha256": hash_archivo(ruta),
                    "fecha_de_creacion": fnd["fecha"],
                    "fecha_origen": fnd["origen"],
                    "fecha_detalle": fnd["detalle"],
                    "modo": "",
                    "fuentes": [],
                    "atributos": [],
                    "consulta": "",
                    "campo_nivel": "",
                    "campo_atributo": "",
                    "campos_clave": [],
                    "familia": "",
                    "freshness_dias": None,
                    "vigencia_declarada_en_el_artefacto": {},
                    "fecha_de_captura_declarada": None,
                    "origen_declarado": "",
                    "usable": False,
                    "motivo_no_usable": ("Hallado en el repositorio pero NO declarado en el "
                                        "pack: usarlo exigiría inventar su autorización."),
                })
    inventario.sort(key=lambda x: (not x["declarado"], x["ruta"]))
    return inventario


def inventario_snapshots(*, con_git: bool = True,
                         registro: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Inventario en formato entregable (JSON) con su resumen."""
    reg = _registro(registro)
    snaps = descubrir_snapshots(con_git=con_git)
    usables = [s for s in snaps if s["usable"]]
    ref = fecha_de_referencia(reg)
    resuelven_hoy = [s for s in usables
                     if evaluar_vigencia(s, ref, registro=reg)["estado"] == SNAPSHOT_VIGENTE]
    return {
        "pack_version": ds.PACK_VERSION,
        "reference_date": ref,
        "raices_escaneadas": list(RAICES_ESCANEO),
        "patrones": list(PATRONES_ESCANEO),
        "snapshots": snaps,
        "resumen": {
            "total_artefactos": len(snaps),
            "declarados": sum(1 for s in snaps if s["declarado"]),
            "usables": len(usables),
            "no_usables": len([s for s in snaps if not s["usable"]]),
            "resuelven_en_la_ventana": len(resuelven_hoy),
            "no_resuelven_en_la_ventana": [
                {"artifact_id": s["artifact_id"], "ruta": s["ruta"],
                 "estado": evaluar_vigencia(s, ref, registro=reg)["estado"]}
                for s in usables if s not in resuelven_hoy],
            "fuentes_con_snapshot": sorted({sid for s in usables for sid in s["fuentes"]}),
            "fuentes_que_resuelven_hoy": sorted({sid for s in resuelven_hoy
                                                 for sid in s["fuentes"]}),
            "por_modo": {m: sorted({sid for s in usables if s["modo"] == m
                                    for sid in s["fuentes"]})
                         for m in (AUTOMATED_SNAPSHOT, AUTHORIZED_FALLBACK)},
        },
    }


def escribir_inventario(ruta: Any = RUTA_INVENTARIO, *,
                        registro: Optional[Dict[str, Any]] = None) -> Path:
    inv = inventario_snapshots(registro=registro)
    p = _ruta_absoluta(ruta)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(inv, ensure_ascii=False, indent=1, sort_keys=True),
                 encoding="utf-8")
    return p


# ══════════════════════════════════════════════════════════════════════════════
# Frescura / vigencia de un snapshot
# ══════════════════════════════════════════════════════════════════════════════
def evaluar_vigencia(snapshot: Dict[str, Any], fecha: Optional[str] = None,
                     *, registro: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """¿Está el snapshot DENTRO de su `freshness_policy` para `fecha`?

    Límite = el MENOR entre (fecha de creación + días de la familia) y la vigencia que el
    PROPIO artefacto declara (p. ej. el artefacto local de metodología declara
    `vigencia_hasta`). Un snapshot vencido NO resuelve: el resultado lo declara y la
    escalera sigue.
    """
    ref = str(fecha or fecha_de_referencia(registro))[:10]
    familia = snapshot.get("familia") or ""
    dias = snapshot.get("freshness_dias")
    if dias is None and familia in FRESHNESS_DEFAULT:
        dias = FRESHNESS_DEFAULT[familia]["dias"]
    ancla = _a_fecha(snapshot.get("fecha_de_creacion"))
    limite_familia = (ancla + timedelta(days=int(dias))) if (ancla and dias) else None
    vig = dict(snapshot.get("vigencia_declarada_en_el_artefacto") or {})
    hasta = None
    for clave, valor in vig.items():
        if str(clave).endswith("vigencia_hasta"):
            hasta = _a_fecha(valor)
    limites = [d for d in (limite_familia, hasta) if d is not None]
    limite = min(limites) if limites else None
    consultada = _a_fecha(ref)
    base = {
        "estado": SNAPSHOT_VIGENTE,
        "fecha_consultada": ref,
        "fecha_de_creacion": snapshot.get("fecha_de_creacion"),
        "fecha_origen": snapshot.get("fecha_origen"),
        "familia": familia,
        "restriccion_dias": dias,
        "limite": limite.isoformat() if limite else None,
        "limite_por_familia": limite_familia.isoformat() if limite_familia else None,
        "limite_por_artefacto": hasta.isoformat() if hasta else None,
        "vigencia_declarada_en_el_artefacto": vig,
        "dias_restantes": _dias_entre(ref, limite) if limite else None,
        "motivo": "",
    }
    if not snapshot.get("usable"):
        base["estado"] = SNAPSHOT_NO_UTILIZABLE
        base["motivo"] = snapshot.get("motivo_no_usable") or "artefacto no utilizable"
        return base
    if ancla is None or limite is None or consultada is None:
        base["estado"] = SNAPSHOT_VENCIDO
        base["motivo"] = ("Sin fecha de creación o sin límite de frescura declarado: no "
                          "puede afirmarse que el snapshot esté vigente, así que NO resuelve.")
        return base
    if consultada > limite:
        base["estado"] = SNAPSHOT_VENCIDO
        if hasta is not None and hasta < (limite_familia or hasta):
            base["motivo"] = (f"El PROPIO artefacto declara vigencia hasta "
                              f"{hasta.isoformat()} y la corrida es {ref}: el snapshot está "
                              f"VENCIDO ({(consultada - limite).days} días fuera).")
        else:
            base["motivo"] = (f"Fuera de la `freshness_policy` de la familia {familia} "
                              f"({dias} días desde {ancla.isoformat()}): límite "
                              f"{limite.isoformat()}, corrida {ref} "
                              f"({(consultada - limite).days} días fuera).")
        return base
    base["motivo"] = (f"Vigente: creado {ancla.isoformat()} y límite {limite.isoformat()} "
                      f"para la corrida {ref} ({base['dias_restantes']} días de margen).")
    return base


def snapshots_de_fuente(source_id: str, *, inventario: Optional[List[Dict[str, Any]]] = None,
                        con_git: bool = True) -> List[Dict[str, Any]]:
    inv = inventario if inventario is not None else descubrir_snapshots(con_git=con_git)
    return [s for s in inv if str(source_id) in (s.get("fuentes") or [])]


def snapshot_para(atributo: str, *, registro: Optional[Dict[str, Any]] = None,
                  fecha: Optional[str] = None,
                  inventario: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """Snapshots DECLARADOS que pueden satisfacer `atributo`, con su veredicto de vigencia.

    Devuelve una lista ordenada (vigentes primero, luego por `artifact_id`) de
    `{"artifact_id", "ruta", "fuente", "modo", "sha256", "bytes", "vigencia": {...},
    "usable": bool, "consulta": ...}`. Lista vacía = «ese atributo no tiene snapshot»:
    una ausencia declarada, nunca un snapshot inventado.
    """
    ref = fecha or fecha_de_referencia(registro)
    inv = inventario if inventario is not None else descubrir_snapshots()
    salida: List[Dict[str, Any]] = []
    for snap in inv:
        if str(atributo) not in (snap.get("atributos") or []):
            continue
        vig = evaluar_vigencia(snap, ref, registro=registro)
        salida.append({
            "artifact_id": snap.get("artifact_id"),
            "ruta": snap["ruta"],
            "fuente": (snap.get("fuentes") or [None])[0],
            "fuentes": list(snap.get("fuentes") or []),
            "modo": snap.get("modo") or "",
            "modo_clase": MODOS_SNAPSHOT_CLASE.get(snap.get("modo") or "", ""),
            "consulta": snap.get("consulta") or "",
            "campo_nivel": snap.get("campo_nivel") or "",
            "campo_atributo": snap.get("campo_atributo") or "",
            "campos_clave": list(snap.get("campos_clave") or []),
            "sha256": snap.get("sha256") or "",
            "bytes": snap.get("bytes") or 0,
            "fecha_de_creacion": snap.get("fecha_de_creacion"),
            "fecha_origen": snap.get("fecha_origen"),
            "vigencia": vig,
            "usable": bool(snap.get("usable")) and vig["estado"] == SNAPSHOT_VIGENTE,
            "resuelve": bool(snap.get("usable")) and vig["estado"] == SNAPSHOT_VIGENTE,
        })
    salida.sort(key=lambda s: (not s["usable"], str(s["artifact_id"]), s["ruta"]))
    return salida


def modos_por_fuente(registro: Optional[Dict[str, Any]] = None, *,
                     fecha: Optional[str] = None,
                     inventario: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """`acquisition_mode` + `product_role` + snapshot + frescura, fuente por fuente.

    Devuelve `{source_id: {...}}` con la ruta declarada, el artefacto que la respalda (si
    existe), el veredicto de vigencia para la fecha de referencia y si HOY resuelve.
    """
    reg = _registro(registro)
    ref = fecha or fecha_de_referencia(reg)
    inv = inventario if inventario is not None else descubrir_snapshots()
    salida: Dict[str, Any] = {}
    for sid, fuente in sorted((reg.get("sources") or {}).items()):
        rol = rol_de_fuente(sid)
        precedencia = str((fuente or {}).get("precedence") or "")
        req = requisitos_de_rol(rol, precedence=precedencia)
        modo = modo_declarado_de_fuente(sid, fuente)
        snaps = snapshots_de_fuente(sid, inventario=inv)
        detalle_snaps = []
        for s in snaps:
            vig = evaluar_vigencia(s, ref, registro=reg)
            detalle_snaps.append({
                "artifact_id": s.get("artifact_id"),
                "ruta": s["ruta"],
                "kind": s.get("kind"),
                "bytes": s.get("bytes"),
                "sha256": s.get("sha256"),
                "fecha_de_creacion": s.get("fecha_de_creacion"),
                "fecha_origen": s.get("fecha_origen"),
                "modo": s.get("modo") or "",
                "modo_clase": MODOS_SNAPSHOT_CLASE.get(s.get("modo") or "", ""),
                "atributos": list(s.get("atributos") or []),
                "consulta": s.get("consulta") or "",
                "usable": bool(s.get("usable")),
                "motivo_no_usable": s.get("motivo_no_usable") or "",
                "vigencia": vig,
                "resuelve_hoy": bool(s.get("usable")) and vig["estado"] == SNAPSHOT_VIGENTE,
            })
        vigentes = [d for d in detalle_snaps if d["resuelve_hoy"]]
        descartados = [d for d in detalle_snaps if not d["resuelve_hoy"]]
        en_vivo = str((fuente or {}).get("base_url") or "").startswith("http")
        salida[sid] = {
            "source_id": sid,
            "product_role": rol,
            "authority_class": (fuente or {}).get("authority_class"),
            "precedence": precedencia,
            "enabled": (fuente or {}).get("enabled") is not False,
            "required_for_decision": req["required_for_decision"],
            "blocking_if_missing": req["blocking_if_missing"],
            "acquisition_mode": modo,
            "ruta_en_vivo": bool(en_vivo),
            "familia": familia_de_fuente(sid),
            "freshness": dict(FRESHNESS_DEFAULT[familia_de_fuente(sid)],
                              source_id=sid, familia=familia_de_fuente(sid)),
            "snapshots": detalle_snaps,
            "snapshots_usables": vigentes,
            "snapshots_descartados": descartados,
            "resuelve_hoy": bool(vigentes) or (bool(en_vivo) and not vigentes),
            "motivo_resolucion": (
                "resuelve desde snapshot vigente: " + ", ".join(d["ruta"] for d in vigentes)
                if vigentes else
                ("depende de una consulta en vivo (geoportal HTTP 403 verificado en la "
                 "ventana): sin snapshot declarado no hay ruta automática"
                 if en_vivo and not detalle_snaps else
                 ("snapshot declarado pero VENCIDO o NO UTILIZABLE:"
                  if detalle_snaps else "sin snapshot declarado"))),
        }
    return salida


# ══════════════════════════════════════════════════════════════════════════════
# Extracción de valor desde un snapshot (adaptador declarado)
# ══════════════════════════════════════════════════════════════════════════════
def _punto_del_contexto(contexto: Optional[Dict[str, Any]]) -> Optional[Tuple[float, float]]:
    ctx = contexto or {}
    punto = ctx.get("punto") or {}
    lat = punto.get("lat", ctx.get("lat"))
    lon = punto.get("lon", ctx.get("lon"))
    try:
        return float(lat), float(lon)
    except (TypeError, ValueError):
        return None


def _identificadores_del_contexto(contexto: Optional[Dict[str, Any]]) -> Dict[str, str]:
    ctx = contexto or {}
    ids = dict(ctx.get("identificadores") or {})
    for clave in ("numero_predial", "codigo_homologado", "fmi", "direccion", "barrio"):
        if ctx.get(clave) not in (None, "") and not ids.get(clave):
            ids[clave] = str(ctx[clave])
    return {k: str(v) for k, v in ids.items() if v not in (None, "")}


def _en_anillo(x: float, y: float, anillo: Sequence[Any]) -> bool:
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


def _contiene(geom: Dict[str, Any], x: float, y: float) -> bool:
    tipo, coords = geom.get("type"), geom.get("coordinates")

    def _poli(anillos: Sequence[Any]) -> bool:
        if not anillos or not _en_anillo(x, y, anillos[0]):
            return False
        return not any(_en_anillo(x, y, h) for h in anillos[1:])
    if tipo == "Polygon":
        return _poli(coords)
    if tipo == "MultiPolygon":
        return any(_poli(p) for p in coords)
    return False


_ORDEN_NIVELES = {"MUY ALTA": 4, "ALTA": 3, "MEDIA": 2, "MEDIO": 2, "BAJA": 1, "BAJO": 1}


def _consulta_punto_en_poligono(snap: Dict[str, Any], contexto: Optional[Dict[str, Any]]
                                ) -> Dict[str, Any]:
    punto = _punto_del_contexto(contexto)
    if punto is None:
        return {"status": ds.FUENTE_NO_DISPONIBLE, "payload": None,
                "detail": ("El snapshot espacial no puede consultarse sin coordenada oficial: "
                           "se declara la ausencia en vez de inferir un punto."),
                "fields": {}}
    lat, lon = punto
    doc = json.loads(_ruta_absoluta(snap["ruta"]).read_text(encoding="utf-8"))
    feats = doc.get("features") or []
    campo = snap.get("campo_nivel") or ""
    campo_attr = snap.get("campo_atributo") or "valor"
    hits = [dict(f.get("properties") or {}) for f in feats
            if _contiene(f.get("geometry") or {}, lon, lat)]
    if not hits:
        return {"status": ds.SIN_COINCIDENCIA,
                "payload": {"capa": Path(snap["ruta"]).name, "poligonos_evaluados": len(feats),
                            "coincidencias": 0},
                "detail": (f"La capa respondió: el punto NO cae en ningún polígono "
                           f"({len(feats)} evaluados)."),
                "fields": {}}
    niveles = [str(h.get(campo) or "") for h in hits]
    peor = max(niveles, key=lambda n: _ORDEN_NIVELES.get(n.upper(), 0)) if niveles else ""
    return {"status": ds.DISPONIBLE,
            "payload": {campo_attr: peor, "capa": Path(snap["ruta"]).name,
                        "poligonos": len(feats), "nivel_por_poligono": niveles,
                        "poligonos_coincidentes": [
                            {k: v for k, v in h.items()
                             if k in ("objectid", campo, "clase_suelo", "clasesuelo")}
                            for h in hits],
                        "regla": ("se reporta el nivel MÁS ALTO y se listan TODOS los "
                                  "polígonos coincidentes: no se elige en silencio.")},
            "detail": f"{len(hits)} polígono(s) contienen el punto.",
            "fields": {"nivel_reportado": peor, "poligonos_coincidentes": len(hits)}}


def _consulta_registro_por_identificador(snap: Dict[str, Any],
                                         contexto: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    ids = _identificadores_del_contexto(contexto)
    claves = [c for c in (snap.get("campos_clave") or ()) if ids.get(c)]
    if not claves:
        return {"status": ds.NO_SOPORTADA, "payload": None,
                "detail": ("Sin ninguno de los identificadores declarados "
                           f"({list(snap.get('campos_clave') or ())}) el registro no puede "
                           "consultarse: ausencia declarada, NUNCA «sin coincidencia», y no "
                           "se pide el dato a una persona."),
                "fields": {}}
    doc = json.loads(_ruta_absoluta(snap["ruta"]).read_text(encoding="utf-8"))
    regs = doc.get("registros") or []
    conjuntos = {c: {i for i, r in enumerate(regs) if str(r.get(c) or "") == ids[c]}
                 for c in claves}
    usados = {k: v for k, v in conjuntos.items() if v}
    lista = sorted(usados)
    for a in range(len(lista)):
        for b in range(a + 1, len(lista)):
            if usados[lista[a]].isdisjoint(usados[lista[b]]):
                return {"status": ds.CONSULTA_FALLIDA,
                        "payload": {"match_status": "CONFLICT",
                                    "coincidencias": {k: sorted(v) for k, v in conjuntos.items()}},
                        "detail": ("Los identificadores de entrada apuntan a registros "
                                   "DISJUNTOS: se declara CONFLICT y no se elige uno en "
                                   "silencio."),
                        "fields": {}}
    if not usados:
        return {"status": ds.SIN_COINCIDENCIA,
                "payload": {"match_status": "NO_MATCH", "identificadores_usados": claves},
                "detail": (f"El registro respondió sin coincidencia exacta para "
                           f"({', '.join(claves)})."),
                "fields": {}}
    comun = set.intersection(*usados.values())
    if len(comun) != 1:
        return {"status": ds.SIN_COINCIDENCIA,
                "payload": {"match_status": "NO_MATCH",
                            "coincidencias": {k: sorted(v) for k, v in conjuntos.items()}},
                "detail": "El registro respondió sin coincidencia única.",
                "fields": {}}
    reg = dict(regs[next(iter(comun))])
    grado = len(lista)
    return {"status": ds.DISPONIBLE,
            "payload": dict(reg, **{
                "match_status": {1: "EXACT_1", 2: "EXACT_2", 3: "EXACT_3"}.get(grado,
                                                                               f"EXACT_{grado}"),
                "identificadores_usados": lista,
                "identity_verified": grado == 3,
                "registro": reg,
                "fuente": doc.get("source_name"),
                "resolucion": f"{doc.get('resolution_number')} de {doc.get('resolution_date')}",
            }),
            "detail": ("" if grado == 3 else
                       f"Coincidencia parcial ({grado} identificador(es)): la identidad NO "
                       "se declara verificada."),
            "fields": {"match_status": "EXACT_%d" % grado, "identity_verified": grado == 3}}


def _consulta_sector_por_barrio(snap: Dict[str, Any], contexto: Optional[Dict[str, Any]]
                                ) -> Dict[str, Any]:
    ids = _identificadores_del_contexto(contexto)
    barrio = ids.get("barrio") or ""
    if not barrio:
        return {"status": ds.NO_SOPORTADA, "payload": None,
                "detail": ("Sin barrio declarado no se puede consultar el sector de mercado: "
                           "ausencia declarada, nunca sector inventado."),
                "fields": {}}
    try:
        import yaml  # type: ignore
        doc = yaml.safe_load(_ruta_absoluta(snap["ruta"]).read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001
        return {"status": ds.CONSULTA_FALLIDA, "payload": None,
                "detail": f"YAML no interpretable: {type(exc).__name__}: {exc}", "fields": {}}
    sectores = doc.get("valor_suelo_por_sector") or {}
    declaracion = doc.get("declaracion") or {}
    consolidacion = doc.get("regla_consolidacion") or {}
    base = {"methodology_id": "lonja_baq_metodologia",
            "version": consolidacion.get("version"),
            "vigencia": {"desde": declaracion.get("vigencia_desde"),
                         "hasta": declaracion.get("vigencia_hasta")},
            "barrio_consultado": barrio}
    elegido = None
    for clave, datos in sectores.items():
        if str(clave).lower() == barrio.lower():
            elegido = (clave, datos)
            break
    if elegido is None:
        return {"status": ds.SIN_COINCIDENCIA,
                "payload": {**base, "match_type": "NO_MATCH",
                            "sectores_declarados": sorted(str(k) for k in sectores)},
                "detail": (f"El barrio «{barrio}» no está en valor_suelo_por_sector: NO se "
                           "inventa sector."),
                "fields": {}}
    nombre, datos = elegido
    return {"status": ds.DISPONIBLE,
            "payload": {**base, "match_type": "EXACT", "sector": nombre,
                        "valor_m2": datos.get("valor_central_m2"),
                        "valor_central_m2": datos.get("valor_central_m2"),
                        "rango_min_m2": datos.get("rango_min_m2"),
                        "rango_max_m2": datos.get("rango_max_m2"),
                        "fuente_metodologica": datos.get("fuente"),
                        "vigencia_sector": datos.get("vigencia")},
            "detail": "", "fields": {"valor_m2": datos.get("valor_central_m2")}}


def _consulta_captura_contexto(snap: Dict[str, Any], contexto: Optional[Dict[str, Any]]
                               ) -> Dict[str, Any]:
    doc = json.loads(_ruta_absoluta(snap["ruta"]).read_text(encoding="utf-8"))
    data = doc.get("response") or {}
    meta = doc.get("_capture") or {}
    els = data.get("elements") or []
    if not els:
        return {"status": ds.SIN_COINCIDENCIA,
                "payload": {"captura": meta.get("queried_at"), "elementos": 0},
                "detail": "La captura cruda no trae elementos.", "fields": {}}
    cats: Dict[str, int] = {}
    for e in els:
        t = e.get("tags") or {}
        k = t.get("amenity") or t.get("shop") or "otro"
        cats[k] = cats.get(k, 0) + 1
    return {"status": ds.DISPONIBLE,
            "payload": {"elementos": len(els), "servicios": dict(sorted(cats.items(),
                                                                        key=lambda x: -x[1])),
                        "categorias": dict(sorted(cats.items(), key=lambda x: -x[1])),
                        "radio_m": (meta.get("point") or {}).get("radio_m", 1500),
                        "espejo": str(meta.get("endpoint") or "").split("/")[2],
                        "capturado_en": meta.get("queried_at"),
                        "nivel_autoridad": "CONTEXTO: nunca autoridad oficial"},
            "detail": "captura cruda preservada sin modificar (snapshot declarado).",
            "fields": {"elementos": len(els)}}


_CONSULTAS_SNAPSHOT: Dict[str, Callable[[Dict[str, Any], Optional[Dict[str, Any]]],
                                        Dict[str, Any]]] = {
    CONSULTA_PUNTO_EN_POLIGONO: _consulta_punto_en_poligono,
    CONSULTA_REGISTRO_POR_IDENTIFICADOR: _consulta_registro_por_identificador,
    CONSULTA_SECTOR_POR_BARRIO: _consulta_sector_por_barrio,
    CONSULTA_CAPTURA_CONTEXTO: _consulta_captura_contexto,
}


def _resultado_desde_snapshot(sid: str, fuente: Dict[str, Any], snap: Dict[str, Any],
                              salida: Dict[str, Any], *, fecha: str,
                              punto_de_consulta: str = "") -> Dict[str, Any]:
    """Envuelve el valor del snapshot en el `SourceResult` de §27 SIN degradar autoridad.

    El `provenance.original_authority_class` conserva la clase de la fuente ORIGINAL y el
    payload se envuelve con `autoridad_preservada=True`.
    """
    prov = {
        "source_id": sid,
        "source_name": fuente.get("source_name"),
        "institution": fuente.get("institution"),
        "authority_class": fuente.get("authority_class"),
        "original_authority_class": fuente.get("authority_class"),
        "service": fuente.get("service"),
        "layer_id": fuente.get("layer_id"),
        "query_method": fuente.get("query_method"),
        "version_or_vigency": fuente.get("version_or_vigency"),
        "precedence": fuente.get("precedence"),
        "license_or_terms": fuente.get("license_or_terms"),
        "acquisition_mode": snap.get("modo") or "",
        "acquisition_mode_clase": MODOS_SNAPSHOT_CLASE.get(snap.get("modo") or "", ""),
        "snapshot": {
            "artifact_id": snap.get("artifact_id"),
            "ruta": snap["ruta"],
            "sha256": snap.get("sha256"),
            "bytes": snap.get("bytes"),
            "fecha_de_creacion": snap.get("fecha_de_creacion"),
            "fecha_origen": snap.get("fecha_origen"),
            "kind": snap.get("kind"),
            "consulta": snap.get("consulta"),
            "punto_de_consulta": punto_de_consulta,
        },
        "autoridad_preservada": True,
        "fuente_original": sid,
    }
    payload = salida.get("payload")
    if isinstance(payload, dict):
        payload = dict(payload, autoridad_preservada=True,
                       _source_id_original=sid,
                       _authority_class_original=fuente.get("authority_class"),
                       _acquisition_mode=snap.get("modo") or "")
    return ds.resultado(sid, str(salida.get("status") or ds.CONSULTA_FALLIDA),
                        payload_normalized=payload, provenance=prov,
                        queried_at=f"{fecha}T00:00:00+00:00",
                        detail=str(salida.get("detail") or ""),
                        binding_status=ds.SIN_BINDING)


# ══════════════════════════════════════════════════════════════════════════════
# Orquestación: la escalera de `source_resolution` manda, aquí solo se le dan las
# consultas resueltas por modo de adquisición.
# ══════════════════════════════════════════════════════════════════════════════
def _consulta_de(consultas: Any, sid: str) -> Optional[Dict[str, Any]]:
    if consultas is None:
        return None
    resultado = consultas(sid) if callable(consultas) else (consultas or {}).get(sid)
    return resultado if isinstance(resultado, dict) else None


def resolver_con_acquisition_mode(atributo: str, *, consultas: Any = None,
                                  registro: Optional[Dict[str, Any]] = None,
                                  fecha: Optional[str] = None,
                                  contexto: Optional[Dict[str, Any]] = None,
                                  cobertura: Optional[Dict[str, Any]] = None,
                                  inventario: Optional[List[Dict[str, Any]]] = None
                                  ) -> Dict[str, Any]:
    """Resuelve UN atributo integrando el modo de adquisición en la ESCALERA existente.

    NO reimplementa la escalera: la orquesta. Para cada fuente del escalón:

      1. se intenta la consulta EN VIVO que aportó el llamador (`consultas`);
      2. si la fuente no respondió o respondió una ausencia (`SOURCE_UNAVAILABLE` /
         `NOT_SUPPORTED` / `QUERY_FAILED`), y el pack DECLARA un snapshot para ese
         (atributo, fuente), se resuelve DESDE EL SNAPSHOT si está dentro de su
         `freshness_policy`;
      3. si el snapshot está VENCIDO (o no es utilizable) NO resuelve: se declara en
         `snapshots_vencidos` con su estado y la escalera sigue su curso.

    Añade al resultado de la escalera la clave `acquisition` con, por fuente: el modo
    realmente usado, el snapshot, su `sha256`, la fecha de la consulta en vivo, el límite
    de frescura y `original_authority_class`. `provenance_adquisicion(resultado)` devuelve
    ese registro para la fuente SELECCIONADA.
    """
    atributo = str(atributo)
    reg = _registro(registro)
    ref = str(fecha or fecha_de_referencia(reg))[:10]
    inv = inventario if inventario is not None else descubrir_snapshots()
    punto = _punto_del_contexto(contexto)
    escalon = sr.escalon_para_atributo(atributo, registro=reg, cobertura=cobertura, fecha=ref)
    modos: Dict[str, Dict[str, Any]] = {}
    vencidos: List[Dict[str, Any]] = []
    efectivas: Dict[str, Dict[str, Any]] = {}
    # Snapshots DECLARADOS para este atributo, con su veredicto de vigencia (una vez).
    declarados_atributo = snapshot_para(atributo, registro=reg, fecha=ref, inventario=inv)

    for entrada in escalon:
        sid = entrada["source_id"]
        fuente = (reg.get("sources") or {}).get(sid) or {}
        vivo = _consulta_de(consultas, sid)
        estado_vivo = str((vivo or {}).get("status") or "")
        registro_modo: Dict[str, Any] = {
            "source_id": sid,
            "authority_class": entrada.get("authority_class"),
            "original_authority_class": fuente.get("authority_class"),
            "declared_mode": modo_declarado_de_fuente(sid, fuente),
            "acquisition_mode": LIVE_QUERY if vivo is not None else "",
            "live_status": estado_vivo or None,
            "source_queried_at": (vivo or {}).get("queried_at") or None,
            "snapshot": None,
            "snapshot_created_at": None,
            "freshness_limit": None,
            "content_hash": None,
            "raw_hash": (vivo or {}).get("raw_hash") or None,
            "usado": bool(vivo is not None and estado_vivo == ds.DISPONIBLE),
            "motivo": ("La consulta EN VIVO aportó el dato: el snapshot no se usa."
                       if vivo is not None and estado_vivo == ds.DISPONIBLE else ""),
        }
        if vivo is not None:
            efectivas[sid] = vivo
        necesita_snapshot = (vivo is None) or (estado_vivo in ESTADOS_SIN_DATO_DE_CONTRATO)
        candidatos = [c for c in declarados_atributo if sid in (c.get("fuentes") or [])]
        if necesita_snapshot and not candidatos:
            registro_modo["motivo"] = ("Sin consulta en vivo utilizable y sin snapshot "
                                       "declarado para este atributo: ausencia declarada, "
                                       "nunca inventada.")
        for cand in candidatos:
            vig = cand["vigencia"]
            if not cand["usable"]:
                vencidos.append({
                    "source_id": sid, "artifact_id": cand["artifact_id"], "ruta": cand["ruta"],
                    "estado_vigencia": vig["estado"], "limite": vig["limite"],
                    "motivo": vig["motivo"], "resolve": False,
                })
                registro_modo["motivo"] = (f"snapshot {cand['ruta']} "
                                           f"{vig['estado']}: NO resuelve. {vig['motivo']}")
                continue
            if not necesita_snapshot:
                registro_modo["motivo"] = ("la consulta en vivo respondió: el snapshot no se "
                                           "usa (no hay ausencia que cubrir).")
                break
            salida = _CONSULTAS_SNAPSHOT[cand["consulta"]](cand, contexto) if cand["consulta"] \
                else {"status": ds.NO_SOPORTADA, "payload": None,
                      "detail": "El snapshot no declara consulta.", "fields": {}}
            if salida.get("status") not in ds.ESTADOS:
                salida["status"] = ds.CONSULTA_FALLIDA
            res_snap = _resultado_desde_snapshot(
                sid, fuente, cand, salida, fecha=ref,
                punto_de_consulta=(f"lat={punto[0]},lon={punto[1]}" if punto else ""))
            efectivas[sid] = res_snap
            disponible = str(salida.get("status")) == ds.DISPONIBLE
            registro_modo.update({
                "acquisition_mode": cand["modo"],
                "declared_mode": registro_modo["declared_mode"],
                "snapshot": cand["ruta"],
                "artifact_id": cand["artifact_id"],
                "snapshot_created_at": cand["fecha_de_creacion"],
                "snapshot_created_origin": cand["fecha_origen"],
                "freshness_limit": vig["limite"],
                "freshness_familia": vig["familia"],
                "freshness_dias": vig["restriccion_dias"],
                "content_hash": cand["sha256"],
                "snapshot_status": salida.get("status"),
                "snapshot_detail": str(salida.get("detail") or ""),
                "snapshot_consultado": True,
                "raw_hash": cand["sha256"],
                "usado": disponible,
                "motivo": (f"LIVE_QUERY no aportó dato utilizable "
                           f"({estado_vivo or 'sin consulta en vivo'}); se resuelve por "
                           f"{cand['modo']} desde {cand['ruta']} ({vig['motivo']}); la "
                           f"authority_class ORIGINAL "
                           f"({fuente.get('authority_class')}) se conserva."
                           if disponible else
                           f"LIVE_QUERY no aportó dato utilizable "
                           f"({estado_vivo or 'sin consulta en vivo'}); el snapshot "
                           f"{cand['modo']} {cand['ruta']} se consultó y declaró "
                           f"{salida.get('status')}: {salida.get('detail') or 'sin detalle'} "
                           f"NO resuelve y la escalera sigue. La ausencia NO es NO_MATCH."),
            })
            break
        modos[sid] = registro_modo

    resultado = sr.resolver_atributo(atributo, consultas=efectivas, fecha=ref, registro=reg,
                                     cobertura=cobertura)
    seleccionado = modos.get(str(resultado.get("selected_source") or ""))
    resultado["acquisition"] = {
        "attribute": atributo,
        "fecha": ref,
        "modo_por_fuente": modos,
        "snapshots_vencidos": vencidos,
        "seleccionado": _registro_seleccionado(seleccionado, resultado, escalon),
        "consultas_efectivas": efectivas,
        "ladder_version": sr.PACK_ETIQUETA,
        "acquisition_version": PACK_ETIQUETA,
    }
    return resultado


def payload_efectivo(resultado: Dict[str, Any], source_id: Optional[str] = None) -> Any:
    """Payload NORMALIZADO que devolvió la fuente (en vivo o desde su snapshot).

    Es la evidencia de la consulta efectiva tal como la escalera la vio. Devuelve `None`
    si no hubo consulta efectiva: nunca fabrica un payload.
    """
    res = resultado_efectivo(resultado, source_id)
    return res.get("payload_normalized")


def resultado_efectivo(resultado: Dict[str, Any], source_id: Optional[str] = None
                       ) -> Dict[str, Any]:
    """`SourceResult` efectivo (en vivo o desde snapshot) de la fuente consultada."""
    adq = (resultado or {}).get("acquisition") or {}
    cons = adq.get("consultas_efectivas") or {}
    sid = (source_id or (adq.get("seleccionado") or {}).get("original_source")
           or resultado.get("selected_source"))
    return dict(cons.get(str(sid)) or {}) if sid else {}


def ctx_lat(contexto: Optional[Dict[str, Any]]) -> Any:
    """Latitud declarada en el contexto de consulta (o None)."""
    punto = _punto_del_contexto(contexto)
    return punto[0] if punto else None


def ctx_lon(contexto: Optional[Dict[str, Any]]) -> Any:
    """Longitud declarada en el contexto de consulta (o None)."""
    punto = _punto_del_contexto(contexto)
    return punto[1] if punto else None


def _registro_seleccionado(registro_modo: Optional[Dict[str, Any]], resultado: Dict[str, Any],
                           escalon: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Registro de adquisición del valor SELECCIONADO por la escalera ({} si no hay)."""
    if not registro_modo:
        return {}
    return {
        "original_source": registro_modo["source_id"],
        "acquisition_mode": registro_modo["acquisition_mode"],
        "declared_mode": registro_modo["declared_mode"],
        "authority_class": registro_modo["authority_class"],
        "snapshot": registro_modo.get("snapshot"),
        "snapshot_created_at": registro_modo.get("snapshot_created_at"),
        "snapshot_created_origin": registro_modo.get("snapshot_created_origin"),
        "source_queried_at": registro_modo.get("source_queried_at"),
        "freshness_limit": registro_modo.get("freshness_limit"),
        "freshness_familia": registro_modo.get("freshness_familia"),
        "freshness_dias": registro_modo.get("freshness_dias"),
        "content_hash": registro_modo.get("content_hash"),
        "raw_hash": registro_modo.get("raw_hash"),
        "live_status": registro_modo.get("live_status"),
        "escalon_step": next((e["escalon_step"] for e in escalon
                              if e["source_id"] == registro_modo["source_id"]), None),
        "resolution_status": resultado.get("resolution_status"),
        "provenance": {
            "original_authority_class": (registro_modo.get("original_authority_class")
                                         or registro_modo.get("authority_class")),
            "fuente_original": registro_modo["source_id"],
            "autoridad_no_degradada": True,
        },
        "motivo": registro_modo.get("motivo") or "",
    }


def provenance_adquisicion(resultado: Dict[str, Any]) -> Dict[str, Any]:
    """Bloque de procedencia de ADQUISICIÓN del valor resuelto (dict vacío si no lo hay).

    Claves: `original_source`, `acquisition_mode` (el REALMENTE usado),
    `snapshot_created_at`, `source_queried_at`, `freshness_limit`, `content_hash`
    (sha256 del snapshot) y `provenance.original_authority_class`.
    """
    if not isinstance(resultado, dict):
        return {}
    adq = resultado.get("acquisition") or {}
    seleccionado = adq.get("seleccionado") or {}
    if not seleccionado:
        return {}
    return dict(seleccionado)


def resolver_dominio_con_acquisition_mode(atributos: Sequence[str], *, consultas: Any = None,
                                          registro: Optional[Dict[str, Any]] = None,
                                          fecha: Optional[str] = None,
                                          contexto: Optional[Dict[str, Any]] = None
                                          ) -> Dict[str, Any]:
    """Resuelve VARIOS atributos con el modo de adquisición integrado."""
    resultados = {
        str(a): resolver_con_acquisition_mode(a, consultas=consultas, registro=registro,
                                             fecha=fecha, contexto=contexto)
        for a in atributos
    }
    return {"resultados": resultados,
            "solo_valor_resuelto": sr.solo_valor_resuelto(resultados),
            "anexo_alternativas": sr.anexo_alternativas(resultados),
            "adquisicion": {a: provenance_adquisicion(r) for a, r in resultados.items()}}


# ══════════════════════════════════════════════════════════════════════════════
# Entrada REAL del Golden (leída, nunca codificada a mano)
# ══════════════════════════════════════════════════════════════════════════════
def leer_golden(ruta: Any = RUTA_RUN_STATE) -> Dict[str, Any]:
    """Identidad real del caso Golden, LEÍDA del run state."""
    p = _ruta_absoluta(ruta)
    if not p.exists():
        raise SystemExit(f"ERROR: no existe el run state del Golden: {p}")
    rs = json.loads(p.read_text(encoding="utf-8"))
    ident = rs.get("property_identity") or {}
    mc = rs.get("market_context") or {}
    coord = mc.get("coordinates") or {}
    adm = ident.get("administrativo") or {}
    prov = mc.get("coordinate_provenance") or {}
    generado = str(rs.get("generated_at") or "")
    return {
        "run_state": _ruta_relativa(p),
        "run_id": rs.get("run_id"),
        "folio": ident.get("folio"),
        "nupre": ident.get("nupre"),
        "numero_predial": ident.get("codigo_catastral"),
        "direccion": ident.get("direccion_raw"),
        "unidad": ident.get("unidad"),
        "torre": ident.get("torre"),
        "apartamento": ident.get("apartamento"),
        "barrio": adm.get("barrio"),
        "estrato": adm.get("estrato"),
        "tratamiento": adm.get("tratamiento"),
        "lat": coord.get("lat"),
        "lon": coord.get("lon"),
        "coordinate_source": mc.get("coordinate_source"),
        "coordinate_provenance": prov,
        "fecha": generado[:10] or None,
        "generated_at": generado,
    }


def consultas_de_la_corrida_congelada(
        registro: Optional[Dict[str, Any]] = None, *, fecha: Optional[str] = None,
        incluir_adaptadores_locales: bool = True,
        contexto: Optional[Dict[str, Any]] = None,
        live: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Dict[str, Any]]:
    """`SourceResult` de la corrida CONGELADA, con la verdad verificada de la ventana.

    · Servicios ArcGIS del geoportal → `SOURCE_UNAVAILABLE` por HTTP 403 (Cloudflare),
      verificado en `raw/golden/_layers_probe.json` (150/150 intentos con 403) y con una
      sonda propia en la ventana. NUNCA se declara `NO_MATCH`.
    · Fuentes deshabilitadas → `NOT_SUPPORTED` con el motivo del registro.
    · Fuentes CALCULADAS y de imagen → se ejecutan de verdad con la coordenada y la fecha
      del Golden (cálculo local, sin red); sin credenciales la imagen declara su ausencia.
    · `OSM_OVERPASS` NO se declara en vivo: en esta corrida no se consultó la red, así que
      su ausencia es «sin consulta» y la resuelve su snapshot declarado.
    """
    reg = _registro(registro)
    ref = str(fecha or fecha_de_referencia(reg))[:10]
    salida: Dict[str, Dict[str, Any]] = dict(live or {})
    for sid, fuente in sorted((reg.get("sources") or {}).items()):
        base = str((fuente or {}).get("base_url") or "")
        if (fuente or {}).get("enabled") is False:
            salida.setdefault(sid, ds.resultado(
                sid, ds.NO_SOPORTADA, queried_at=f"{ref}T00:00:00+00:00",
                detail=("Fuente deshabilitada en el registro: su layer_id no pudo "
                        "verificarse (ver notes de la fuente)."),
                provenance={"source_id": sid, "authority_class": fuente.get("authority_class"),
                            "acquisition_mode": LIVE_QUERY}))
            continue
        if base.startswith("http") and sid != "OSM_OVERPASS":
            salida.setdefault(sid, ds.resultado(
                sid, ds.FUENTE_NO_DISPONIBLE, queried_at=f"{ref}T00:00:00+00:00",
                detail=("Geoportal/servicio inalcanzable en la ventana: HTTP 403 "
                        "(Cloudflare) verificado (raw/golden/_layers_probe.json: 150/150 "
                        "intentos con 403). Una ausencia NUNCA se convierte en NO_MATCH."),
                provenance={"source_id": sid, "authority_class": fuente.get("authority_class"),
                            "acquisition_mode": LIVE_QUERY,
                            "http_status": 403}))
    if incluir_adaptadores_locales:
        salida.update(_consultas_locales(contexto, ref))
    return salida


def _consultas_locales(contexto: Optional[Dict[str, Any]], ref: str
                       ) -> Dict[str, Dict[str, Any]]:
    """Adaptadores LOCALES reales (cálculo y credenciales): nada simulado."""
    salida: Dict[str, Dict[str, Any]] = {}
    ctx = contexto or {}
    try:
        import datetime as _dt
        sys.path.insert(0, str(RAIZ))
        sys.path.insert(0, str(RAIZ / "api"))
        import solar_engine as se  # noqa: E402
        lat, lon = float(ctx.get("lat")), float(ctx.get("lon"))
        fecha_dt = _dt.datetime.fromisoformat(str(ctx.get("fecha") or ref) + "T12:00:00")
        az, el = se.get_solar_position(lat, lon, fecha_dt)
        salida["SOLAR_ENGINE"] = ds.resultado(
            "SOLAR_ENGINE", ds.DISPONIBLE, queried_at=f"{ref}T00:00:00+00:00",
            payload_normalized={"exposicion": "CALCULADA", "irradiacion": None,
                                "azimut": az, "inclinacion": el,
                                "metodo": "get_solar_position(lat, lon, dt, tz_offset=-5)",
                                "es_medicion_fisica": False},
            provenance={"source_id": "SOLAR_ENGINE", "authority_class": ds.CALCULADA,
                        "acquisition_mode": LIVE_QUERY})
        import facade_solar as fs  # noqa: E402
        out = fs.analizar_exposicion_fachada(lat, lon, fecha=str(ctx.get("fecha") or ref),
                                            hora=12.0)
        salida["SHADOW_FACADE_EXPOSURE"] = ds.resultado(
            "SHADOW_FACADE_EXPOSURE", ds.DISPONIBLE, queried_at=f"{ref}T00:00:00+00:00",
            payload_normalized={"exposicion": out.get("estado"),
                                "estado_exposicion": out.get("estado"),
                                "shadow_confidence": out.get("shadow_confidence"),
                                "es_medicion_fisica": out.get("es_medicion_fisica"),
                                "altura_fisica": out.get("building_physical_height")},
            provenance={"source_id": "SHADOW_FACADE_EXPOSURE",
                        "authority_class": ds.CALCULADA,
                        "acquisition_mode": LIVE_QUERY})
    except Exception as exc:  # noqa: BLE001 — el fallo es un estado, no una excepción
        salida.setdefault("SOLAR_ENGINE", ds.resultado(
            "SOLAR_ENGINE", ds.CONSULTA_FALLIDA, queried_at=f"{ref}T00:00:00+00:00",
            detail=f"motor solar no ejecutable: {type(exc).__name__}: {exc}"))
    try:
        import street_imagery as si  # noqa: E402
        agg = si.consultar_vista_automatica(float(ctx.get("lat")), float(ctx.get("lon")), None,
                                           coordenada_oficial=(float(ctx.get("lat")),
                                                               float(ctx.get("lon"))))
        salida["MAPILLARY"] = ds.resultado(
            "MAPILLARY", str(agg.get("status")), queried_at=f"{ref}T00:00:00+00:00",
            payload_normalized={"image_url": None,
                                "estado": agg.get("facade_view_level"),
                                "fecha_captura": None,
                                "human_input_required": agg.get("human_input_required")},
            detail="Sin credenciales/evidencia de imagen: ausencia declarada.",
            provenance={"source_id": "MAPILLARY", "authority_class": ds.CONTEXTUAL_EXTERNA})
        salida["GOOGLE_STREET_VIEW"] = ds.resultado(
            "GOOGLE_STREET_VIEW", str(agg.get("status")), queried_at=f"{ref}T00:00:00+00:00",
            payload_normalized={"image_url": None, "estado": agg.get("facade_view_level"),
                                "fecha_captura": None},
            detail="Proveedor en FAIL-CLOSED por términos no verificados y sin credencial.",
            provenance={"source_id": "GOOGLE_STREET_VIEW",
                        "authority_class": ds.CONTEXTUAL_EXTERNA})
    except Exception as exc:  # noqa: BLE001
        for sid in ("MAPILLARY", "GOOGLE_STREET_VIEW"):
            salida.setdefault(sid, ds.resultado(
                sid, ds.CONSULTA_FALLIDA, queried_at=f"{ref}T00:00:00+00:00",
                detail=f"street imagery no ejecutable: {type(exc).__name__}: {exc}"))
    return salida


# ══════════════════════════════════════════════════════════════════════════════
# Identidad canónica por CUALQUIERA de las dos entradas (dirección o matrícula)
# ══════════════════════════════════════════════════════════════════════════════
def _fmi_desde_folio(folio: Any) -> str:
    """Parte registral del folio SNR («CODIGO-FMI» → FMI). Regla declarada, no manual."""
    return str(folio or "").split("-")[-1].strip()


def partes_del_folio(folio: Any) -> Dict[str, str]:
    """Descompone el folio SNR por su formato declarado `ORIP-FMI`.

    Regla DECLARADA (no inventada): el folio de matrícula inmobiliaria se compone del
    código de la oficina de registro (ORIP) y del número de matrícula (p. ej. `040-646406`
    → `codigo_registral=040`, `fmi=646406`). Ambos son campos REALES del registro de
    adopción (`codigo_registral`, `fmi`), así que el folio entra por DOS claves tipadas
    exactas y no requiere que ninguna persona aporte nada más. Un folio con más de un
    guion conserva la parte final como FMI y la primera como ORIP.
    """
    texto = str(folio or "").strip()
    partes = [p for p in texto.split("-") if p != ""]
    if len(partes) >= 2:
        return {"codigo_registral": partes[0], "fmi": partes[-1]}
    if len(partes) == 1:
        return {"fmi": partes[0]}
    return {}


_UNIDAD_RE = re.compile(r"\b(TORRE|TO|APARTAMENTO|APTO|AP|UNIDAD|UN)\s*#?\s*(\d+[A-Za-z]?)\b",
                        re.IGNORECASE)


def marcadores_de_unidad(direccion: Any) -> Dict[str, str]:
    """Torre y apartamento de una nomenclatura municipal, por sus ABREVIATURAS reales.

    El registro de adopción escribe `Transversal 43 100 50 TO 8 AP 430`: `TO` = torre y
    `AP` = apartamento. Extraerlos evita que dos caminos de entrada (dirección o matrícula)
    describan la MISMA unidad con marcadores distintos.
    """
    salida: Dict[str, str] = {}
    for tipo, valor in _UNIDAD_RE.findall(str(direccion or "")):
        t = tipo.upper()
        if t in ("TORRE", "TO") and "torre" not in salida:
            salida["torre"] = valor
        elif t in ("APARTAMENTO", "APTO", "AP") and "apartamento" not in salida:
            salida["apartamento"] = valor
        elif t in ("UNIDAD", "UN") and "unidad" not in salida:
            salida["unidad"] = valor
    return salida


def resolver_identidad_canonica(entrada: Dict[str, Any], *, consultas: Any = None,
                                registro: Optional[Dict[str, Any]] = None,
                                fecha: Optional[str] = None,
                                contexto: Optional[Dict[str, Any]] = None,
                                inventario: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Resuelve la IDENTIDAD CANÓNICA con UN SOLO dato de entrada: dirección o matrícula.

    Encadena la ESCALERA (no la reimplementa):
      1. `direccion_predio` — consulta EN VIVO de la nomenclatura oficial (capa 105) y, si
         responde, toma de ella los identificadores tipados (número predial / NUPRE) y la
         coordenada;
      2. `identidad_nupre` — con esos identificadores, o con las DOS partes del folio SNR
         (`ORIP` + `FMI`, descompuestas por la regla declarada), el registro de adopción
         catastral (modo AUTHORIZED_FALLBACK) confirma la identidad por claves EXACTAS;
      3. con la evidencia CONVERGIDA se construye el `CanonicalPropertyIdentity`
         (`api/canonical.build_canonical_property_identity`): el MISMO inmueble alcanza la
         MISMA identidad por cualquiera de las dos entradas.

    NUNCA pide identificadores a una persona: lo que falte se declara y
    `intervencion_manual` es siempre False.
    """
    atributo_direccion = "direccion_predio"
    atributo_identidad = "identidad_nupre"
    ctx = dict(contexto or {})
    ids: Dict[str, Any] = {}
    if entrada.get("direccion"):
        ctx.setdefault("direccion", str(entrada["direccion"]))
    if entrada.get("folio"):
        ids.update({k: v for k, v in partes_del_folio(entrada["folio"]).items() if v})
    for clave in ("numero_predial", "nupre", "codigo_homologado", "fmi", "codigo_registral"):
        if entrada.get(clave):
            ids[clave] = entrada[clave]
    ctx["identificadores"] = {**{k: str(v) for k, v in ids.items() if v},
                              **dict(ctx.get("identificadores") or {})}

    resoluciones: Dict[str, Any] = {}
    # 1 · dirección oficial en vivo (si la hay): de ella salen los identificadores tipados
    if entrada.get("direccion"):
        r_dir = resolver_con_acquisition_mode(
            atributo_direccion, consultas=consultas, registro=registro, fecha=fecha,
            contexto=ctx, inventario=inventario)
        resoluciones[atributo_direccion] = r_dir
        valor = payload_efectivo(r_dir)
        if isinstance(valor, dict) and r_dir.get("resolution_status") in (sr.RESOLVED_PRIMARY,
                                                                         sr.RESOLVED_FALLBACK):
            if valor.get("numero_predial") or valor.get("numero_predial_nacional"):
                ctx["identificadores"].setdefault(
                    "numero_predial",
                    str(valor.get("numero_predial") or valor.get("numero_predial_nacional")))
            for clave in ("codigo_homologado", "nupre", "fmi"):
                if valor.get(clave):
                    ctx["identificadores"].setdefault(clave, str(valor[clave]))
            for clave in ("lat", "lon"):
                if valor.get(clave) is not None and ctx.get(clave) is None:
                    ctx[clave] = valor[clave]
            if isinstance(valor.get("centroide"), dict) and ctx.get("lat") is None:
                ctx["lat"] = valor["centroide"].get("lat")
                ctx["lon"] = valor["centroide"].get("lon")
            if valor.get("direccion") and not ctx.get("direccion"):
                ctx["direccion"] = valor["direccion"]
    # 2 · identidad canónica (registro de adopción por claves EXACTAS tipadas)
    r_id = resolver_con_acquisition_mode(atributo_identidad, consultas=consultas,
                                        registro=registro, fecha=fecha, contexto=ctx,
                                        inventario=inventario)
    resoluciones[atributo_identidad] = r_id

    registro_adopcion = None
    candidato = payload_efectivo(r_id)
    if isinstance(candidato, dict) and r_id.get("resolution_status") in (sr.RESOLVED_PRIMARY,
                                                                        sr.RESOLVED_FALLBACK):
        registro_adopcion = dict(candidato)
    identidad = None
    adquisicion = {}
    if registro_adopcion:
        construida = _identidad_canonica_desde_registro(registro_adopcion, entrada=entrada,
                                                       ctx=ctx, fecha=fecha)
        identidad = construida["canonical_property_identity"]
        adquisicion = construida["adquisicion_de_identidad"]
    return {
        "entrada": dict(entrada),
        "entrada_declarada": ("DIRECCION" if entrada.get("direccion") else
                              ("MATRICULA" if entrada.get("folio") else "IDENTIFICADORES")),
        "identificadores_usados": {k: v for k, v in ctx["identificadores"].items() if v},
        "resoluciones": resoluciones,
        "registro_de_adopcion": registro_adopcion,
        "canonical_property_identity": identidad,
        "adquisicion_de_identidad": adquisicion,
        "intervencion_manual": False,
        "requiere_identificadores_manuales": False,
        "motivo": ("" if identidad else
                   "Identidad canónica NO alcanzada con esta entrada: se declara la ausencia "
                   "(ver `resoluciones`) en vez de pedir datos a una persona."),
    }


# Regla DECLARADA de confianza de identidad: dos o más claves EXACTAS tipadas que apuntan
# al MISMO registro equivalen a una identificación exacta (`MATCH_EXACT` en `api/canonical`);
# con UNA sola clave la identidad se declara como coincidencia por matrícula y NO se eleva.
GRADO_MINIMO_MATCH_EXACT = 2


def _identidad_canonica_desde_registro(registro_adopcion: Dict[str, Any],
                                       *, entrada: Dict[str, Any], ctx: Dict[str, Any],
                                       fecha: Optional[str]) -> Dict[str, Any]:
    """Construye el `CanonicalPropertyIdentity` real con `api/canonical` (sin red).

    Los insumos son la evidencia CONVERGIDA (el registro oficial y las dos partes del folio),
    no la forma de entrada: por eso la dirección y la matrícula producen el MISMO objeto.
    """
    try:
        sys.path.insert(0, str(RAIZ / "api"))
        from canonical import (build_canonical_property_identity,  # noqa: E402
                               ESTADO_MATCH_EXACT, ESTADO_MATCH_BY_MATRICULA)
    except Exception:  # noqa: BLE001 — sin el módulo canónico no se fabrica identidad
        return {"canonical_property_identity": None,
                "adquisicion_de_identidad": {
                    "motivo": "`api.canonical` no importable: no se fabrica identidad."}}

    reg = dict(registro_adopcion.get("registro") or registro_adopcion)
    numero_predial = str(reg.get("numero_predial") or reg.get("numero_predial_nacional") or "")
    nupre = str(reg.get("codigo_homologado") or "")
    direccion_oficial = str(reg.get("direccion") or "")
    folio = str(entrada.get("folio") or "").strip()
    partes = partes_del_folio(folio) if folio else {}
    fmi_registro = str(reg.get("fmi") or "")
    if not folio:
        orip = str(reg.get("codigo_registral") or "")
        folio = f"{orip}-{fmi_registro}" if (orip and fmi_registro) else fmi_registro
    marcadores = marcadores_de_unidad(direccion_oficial)
    grado_texto = str(registro_adopcion.get("match_status") or "")
    grado = int(grado_texto.split("_")[-1]) if grado_texto.rsplit("_", 1)[-1].isdigit() else 0
    estado_identidad = (ESTADO_MATCH_EXACT if grado >= GRADO_MINIMO_MATCH_EXACT
                        else ESTADO_MATCH_BY_MATRICULA)
    analisis = {
        "nupre": nupre or None,
        "codigo_catastral": numero_predial or None,
        "direccion": direccion_oficial or None,
        "folio": folio or None,
        "torre": marcadores.get("torre"),
        "apartamento": marcadores.get("apartamento"),
        "unidad": analisis_unidad(marcadores),
    }
    predio_real = {
        "predio": {"numero_predial_nacional": numero_predial or None,
                   "codigo_homologado": nupre or None,
                   "direccion_oficial": direccion_oficial or None,
                   "matricula_inmobiliaria": None},
        "entorno": {},
    }
    identidad = build_canonical_property_identity(
        analysis=analisis, folio=folio, predio_real=predio_real, nom=None,
        identidad={"estado": estado_identidad,
                   "detalle": (f"Identidad confirmada por el registro de adopción catastral "
                               f"con {grado_texto or 'coincidencia declarada'} sobre claves "
                               f"EXACTAS tipadas; la `authority_class` ORIGINAL "
                               f"({ctx.get('authority_class') or 'AUTHORITATIVE_OFFICIAL'}) "
                               f"se conserva.")},
        ciudad="barranquilla",
        metodo_resolucion="nupre" if nupre else "codigo_predial",
    )
    adq = {
        "regla_de_confianza": (
            f"Con {GRADO_MINIMO_MATCH_EXACT} o más claves EXACTAS tipadas que apuntan al "
            f"MISMO registro se declara identificación exacta ({ESTADO_MATCH_EXACT}); con "
            f"una sola clave la identidad NO se eleva ({ESTADO_MATCH_BY_MATRICULA})."),
        "match_status": grado_texto or None,
        "match_degree": grado,
        "claves_exactas_usadas": list(registro_adopcion.get("identificadores_usados") or []),
        "identity_verified_por_grado": bool(grado == 3),
        "identification_mode": "AUTOMATED_SNAPSHOT/FALLBACK autorizado sobre registro oficial",
        "entrada_declarada": ("DIRECCION" if entrada.get("direccion") else
                              ("MATRICULA" if entrada.get("folio") else "IDENTIFICADORES")),
        "folio_usado": folio,
        "partes_del_folio": partes,
        "fmi_del_registro": fmi_registro,
        "fecha_de_referencia": str(fecha or "")[:10] or None,
        "provenance": {
            "original_authority_class": (ctx.get("original_authority_class")
                                         or "AUTHORITATIVE_OFFICIAL"),
            "fuente_original": "CATASTRO_BAQ_ADOPCION_ANEXO1",
            "autoridad_no_degradada": True,
        },
    }
    return {"canonical_property_identity": identidad, "adquisicion_de_identidad": adq}


def analisis_unidad(marcadores: Dict[str, str]) -> Optional[str]:
    """Texto de unidad declarado (`APARTAMENTO 430 TORRE 8`) o None si no hay marcadores."""
    partes = []
    if marcadores.get("unidad"):
        partes.append(f"UNIDAD {marcadores['unidad']}")
    if marcadores.get("apartamento"):
        partes.append(f"APARTAMENTO {marcadores['apartamento']}")
    if marcadores.get("torre"):
        partes.append(f"TORRE {marcadores['torre']}")
    return " ".join(partes) or None


# ══════════════════════════════════════════════════════════════════════════════
# MATRIZ DE ROLES Y ADQUISICIÓN (11 columnas, TODO calculado)
# ══════════════════════════════════════════════════════════════════════════════
def _fuentes_del_dominio(fuente_txt: str, reg: Dict[str, Any]) -> List[str]:
    if "*" in fuente_txt:
        prefijo = fuente_txt.split("*")[0]
        return sorted(sid for sid in (reg.get("sources") or {}) if sid.startswith(prefijo))
    if "+" in fuente_txt:
        return [p for p in fuente_txt.split("+") if p]
    return [fuente_txt]


def _rol_de_dominio(fuentes: Sequence[str]) -> str:
    roles: List[str] = []
    for sid in fuentes:
        rol = rol_de_fuente(sid)
        if rol not in roles:
            roles.append(rol)
    if len(roles) == 1:
        return roles[0]
    return "MIXED(" + "|".join(sorted(roles)) + ")"


def _requisitos_de_dominio(fuentes: Sequence[str], reg: Dict[str, Any],
                           rol: str) -> Dict[str, bool]:
    if len(fuentes) == 1:
        f = (reg.get("sources") or {}).get(fuentes[0]) or {}
        return requisitos_de_rol(rol, precedence=f.get("precedence"))
    req = [requisitos_de_rol(rol_de_fuente(s),
                            precedence=((reg.get("sources") or {}).get(s) or {}).get("precedence"))
           for s in fuentes]
    return {"required_for_decision": any(r["required_for_decision"] for r in req),
            "blocking_if_missing": any(r["blocking_if_missing"] for r in req)}


def _status_de_dominio(intentos: Sequence[Dict[str, Any]], fuentes: Sequence[str],
                       reg: Dict[str, Any]) -> Tuple[str, str]:
    """Estado del dominio, DERIVADO de las fuentes del propio dominio (nunca NO_MATCH)."""
    presentes = [s for s in fuentes if s in (reg.get("sources") or {})]
    if fuentes and not presentes:
        return ds.NO_SOPORTADA, ("La fuente que el dominio declara NO está en el registro "
                                 "vigente del pack: se declara su ausencia y NO se inventa "
                                 "ni se sustituye por otra fuente.")
    propios = [i for i in intentos if i.get("source_id") in set(fuentes)]
    estados = [str(i.get("status")) for i in propios]
    if not estados:
        f = (reg.get("sources") or {}).get(fuentes[0]) if fuentes else {}
        if (f or {}).get("enabled") is False:
            return ds.NO_SOPORTADA, "Fuente deshabilitada en el registro."
        return ds.FUENTE_NO_DISPONIBLE, "La fuente no entró al escalón del atributo."
    if ds.DISPONIBLE in estados:
        return ds.DISPONIBLE, ""
    if all(e == ds.NO_SOPORTADA for e in estados):
        return ds.NO_SOPORTADA, "Todas las fuentes del dominio declaran NOT_SUPPORTED."
    if ds.CONSULTA_FALLIDA in estados:
        return ds.CONSULTA_FALLIDA, "Alguna fuente del dominio declara QUERY_FAILED."
    if ds.SIN_COINCIDENCIA in estados and not any(e in ESTADOS_SIN_DATO_DE_CONTRATO
                                                  for e in estados):
        return ds.SIN_COINCIDENCIA, ("La fuente contestó SIN coincidencia: el dominio queda "
                                     "sin dato y la escalera NUNCA lo convierte en valor ni "
                                     "en cero.")
    if all(str(e) == sr.NOT_RUN for e in estados):
        return ds.FUENTE_NO_DISPONIBLE, ("No se ejecutó consulta para las fuentes del "
                                         "dominio: no puede afirmarse nada del dato (una "
                                         "ausencia declarada, nunca NO_MATCH).")
    return ds.FUENTE_NO_DISPONIBLE, "Ausencia declarada por las fuentes del dominio."


def _valor_normalizado(valor: Any) -> str:
    if valor is None:
        return ""
    if isinstance(valor, str):
        return valor
    return json.dumps(valor, ensure_ascii=False, sort_keys=True, default=str)


def matriz_roles(*, registro: Optional[Dict[str, Any]] = None,
                 fecha: Optional[str] = None,
                 contexto: Optional[Dict[str, Any]] = None,
                 consultas: Any = None,
                 inventario: Optional[List[Dict[str, Any]]] = None,
                 golden: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Matriz de cobertura con `product_role`, modo de adquisición y bloqueo (CALCULADA).

    Columnas: `domain, source_id, product_role, status, binding, normalized_result,
    authority, provenance, raw_hash, required_for_decision, blocking_if_missing`.
    Ningún resultado se escribe a mano: `status`, `binding`, el valor normalizado, la
    autoridad (SIEMPRE la original), la procedencia y el hash salen de una corrida real de
    la escalera con el modo de adquisición.
    """
    reg = _registro(registro)
    ref = str(fecha or fecha_de_referencia(reg))[:10]
    golden = dict(golden if golden is not None else leer_golden())
    ctx = dict(contexto or {
        "punto": {"lat": golden.get("lat"), "lon": golden.get("lon")},
        "identificadores": {"numero_predial": golden.get("numero_predial"),
                            "codigo_homologado": golden.get("nupre"),
                            "fmi": _fmi_desde_folio(golden.get("folio")),
                            "barrio": golden.get("barrio")},
        "lat": golden.get("lat"), "lon": golden.get("lon"),
        "barrio": golden.get("barrio"),
        "fecha": golden.get("fecha") or ref,
    })
    consultas = consultas if consultas is not None else consultas_de_la_corrida_congelada(
        reg, fecha=ref, contexto=ctx)
    inv = inventario if inventario is not None else descubrir_snapshots()

    filas: List[Dict[str, Any]] = []
    for dominio in DOMINIOS_DECLARADOS:
        fuente_txt = dominio["fuente"]
        fuentes = _fuentes_del_dominio(fuente_txt, reg)
        rol = _rol_de_dominio(fuentes)
        req = _requisitos_de_dominio(fuentes, reg, rol)
        resultado = resolver_con_acquisition_mode(
            dominio["atributo"], consultas=consultas, registro=reg, fecha=ref, contexto=ctx,
            inventario=inv)
        intentos = list(resultado.get("attempts") or [])
        status, motivo_status = _status_de_dominio(intentos, fuentes, reg)
        propio = next((i for i in intentos if i.get("source_id") in set(fuentes)), None)
        valor = (propio or {}).get("value")
        prov_dominio = (resultado.get("acquisition") or {}).get("modo_por_fuente") or {}
        usado = next((prov_dominio[s] for s in fuentes if s in prov_dominio and
                      prov_dominio[s].get("usado")), None)
        autoridad = "+".join(dict.fromkeys(
            str((reg.get("sources") or {}).get(s, {}).get("authority_class") or "")
            for s in fuentes)) or None
        if usado:
            provenance = (
                f"modo={usado['acquisition_mode']} (declarado {usado['declared_mode']}) | "
                f"original={usado['source_id']} | snapshot={usado.get('snapshot')} | "
                f"sha256:{str(usado.get('content_hash') or '')[:16]} | "
                f"frescura={usado.get('freshness_familia')}:"
                f"{usado.get('freshness_dias')}d hasta {usado.get('freshness_limit')} | "
                f"consultado_en={usado.get('source_queried_at')} | live={usado.get('live_status')}"
            )
            raw_hash = usado.get("raw_hash") or ""
        else:
            explicacion = next((i.get("rejected_reason") for i in intentos
                                if i.get("source_id") in set(fuentes) and
                                i.get("rejected_reason")), "")
            motivos = "; ".join(str(prov_dominio[s].get("motivo") or "")
                                for s in fuentes if s in prov_dominio)
            intentado = next((prov_dominio[s] for s in fuentes if s in prov_dominio
                              and prov_dominio[s].get("snapshot_consultado")), None)
            detalle_snap_intentado = ""
            if intentado:
                detalle_snap_intentado = (
                    f" | snapshot_intentado={intentado.get('snapshot')} "
                    f"({intentado.get('acquisition_mode')}) "
                    f"→ {intentado.get('snapshot_status')}: "
                    f"{str(intentado.get('snapshot_detail') or '')[:220]}")
            vencidos_dominio = [v for v in (resultado.get("acquisition") or {}).get(
                "snapshots_vencidos") or [] if v.get("source_id") in set(fuentes)]
            detalle_snap = "; ".join(
                f"{v['ruta']} → {v['estado_vigencia']} (límite {v['limite']}): {v['motivo']}"
                for v in vencidos_dominio)
            provenance = (f"modo=sin_valor | fuentes={', '.join(fuentes)} | "
                          f"motivo={motivo_status} | {motivos}{detalle_snap_intentado} | "
                          f"{detalle_snap} | {explicacion[:200]}")
            raw_hash = ""
        if status == ds.DISPONIBLE and valor is not None:
            normalizado = _valor_normalizado(valor)[:600]
        else:
            normalizado = (f"AUSENCIA_DECLARADA: {status} — "
                           f"{(motivo_status or 'sin valor utilizable')}")
        binding = _binding_de_dominio(dominio,
                                      payload_efectivo(resultado, propio["source_id"])
                                      if propio else None, ctx)
        filas.append({
            "domain": dominio["domain"],
            "source_id": fuente_txt,
            "product_role": rol,
            "status": status,
            "binding": binding,
            "normalized_result": normalizado,
            "authority": autoridad or "",
            "provenance": provenance,
            "raw_hash": raw_hash,
            "required_for_decision": bool(req["required_for_decision"]),
            "blocking_if_missing": bool(req["blocking_if_missing"]),
        })
    return filas


def _binding_de_dominio(dominio: Dict[str, Any], valor: Any,
                        ctx: Dict[str, Any]) -> str:
    """Binding TIPADO del dominio: solo la identidad autoriza identidad."""
    if not dominio.get("identidad"):
        return "NO_APLICA_NO_AUTORIZA_IDENTIDAD"
    if not isinstance(valor, dict):
        return ds.SIN_BINDING
    ids = _identificadores_del_contexto(ctx)
    res = ds.elegir_predio_canonico([{"attributes": dict(valor)}],
                                    nupre=ids.get("codigo_homologado", ""),
                                    numero_predial=ids.get("numero_predial", ""),
                                    codigo_homologado=ids.get("codigo_homologado", ""))
    return str(res.get("binding_status") or ds.SIN_BINDING)


def escribir_matriz(filas: Sequence[Dict[str, Any]], ruta: Any = RUTA_MATRIZ) -> Path:
    p = _ruta_absoluta(ruta)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(COLUMNAS_MATRIZ))
        w.writeheader()
        for fila in filas:
            w.writerow({c: fila.get(c, "") for c in COLUMNAS_MATRIZ})
    return p


def leer_matriz(ruta: Any = RUTA_MATRIZ) -> List[Dict[str, str]]:
    p = _ruta_absoluta(ruta)
    with p.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


# ══════════════════════════════════════════════════════════════════════════════
# ESTADO: CONTRACT_FROZEN vs OPERATIONAL_READY
# ══════════════════════════════════════════════════════════════════════════════
CRITERIOS_CONTRACT_FROZEN: Tuple[Tuple[str, str], ...] = (
    ("registro_completo",
     "Las 35 fuentes declaran las 25 claves del contrato + product_role + acquisition_mode"),
    ("metadata_real",
     "Cada fuente declara institución, servicio, capa, método, vigencia, licencia y evidencia"),
    ("market_formalizada",
     "El dominio `mercado` NO tiene fuente: la tasa es un PARÁMETRO declarado por la "
     "corrida (`origin = MANUAL_CONFIG`, no habilita la valoración). El identificador "
     "histórico sellado LONJA_MARKET_BAQ se conserva declarado NOT_A_SOURCE, fuera del "
     "Source Registry y con su fila en estado NO DISPONIBLE"),
    ("binding_tipado",
     "`api/dictus_sources.elegir_predio_canonico` coteja SOLO campos del mismo tipo"),
    ("precedencia_determinista",
     "El orden de la escalera se deriva de autoridad → vigencia → prioridad → alfabeto"),
    ("escalera_por_atributo",
     "`api/source_resolution` resuelve por atributo con fallback y registro de intentos"),
    ("licencias_documentadas",
     "`api/source_licenses` documenta licencia y política de persistencia por fuente"),
    ("modos_de_adquisicion",
     "Cada fuente declara modo (LIVE/SNAPSHOT/FALLBACK) y su snapshot real con sha256"),
    ("snapshots_descubiertos",
     "El inventario declara ruta, fecha de commit, bytes, sha256 y atributos de cada snapshot"),
    ("gemelos_identicos",
     "El registro JSON y su YAML gemelo tienen EXACTAMENTE el mismo contenido"),
)


def estado_operativo(*, registro: Optional[Dict[str, Any]] = None,
                     fecha: Optional[str] = None,
                     filas: Optional[Sequence[Dict[str, Any]]] = None,
                     contexto: Optional[Dict[str, Any]] = None,
                     consultas: Any = None,
                     inventario: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Veredicto de dos estados: CONTRACT_FROZEN y OPERATIONAL_READY, con sus evidencias."""
    reg = _registro(registro)
    ref = str(fecha or fecha_de_referencia(reg))[:10]
    inv = inventario if inventario is not None else descubrir_snapshots()
    filas = list(filas) if filas is not None else matriz_roles(
        registro=reg, fecha=ref, contexto=contexto, consultas=consultas, inventario=inv)
    modos = modos_por_fuente(reg, fecha=ref, inventario=inv)

    core: List[Dict[str, Any]] = []
    for fila in filas:
        rol = str(fila["product_role"])
        if rol not in ROLES_CORE:
            continue
        cubierto = fila["status"] == ds.DISPONIBLE
        core.append({
            "domain": fila["domain"],
            "source_id": fila["source_id"],
            "product_role": rol,
            "status": fila["status"],
            "cubierto_automaticamente": cubierto,
            "bloquea": bool(fila["blocking_if_missing"]) and not cubierto,
            "provenance": fila["provenance"],
        })
    no_cubiertos = [c for c in core if not c["cubierto_automaticamente"]]
    cubiertos = [c for c in core if c["cubierto_automaticamente"]]

    modos_sin_snapshot = sorted(sid for sid, m in modos.items()
                                if m["enabled"] and m["ruta_en_vivo"] and not m["snapshots"])
    return {
        "pack_version": ds.PACK_VERSION,
        "reference_date": ref,
        "contract_frozen": {
            "estado": "CONTRACT_FROZEN",
            "criterios": [{"criterio": c, "evidencia": e}
                          for c, e in CRITERIOS_CONTRACT_FROZEN],
        },
        "operational_ready": {
            "estado": "OPERATIONAL_READY" if not no_cubiertos else "OPERATIONAL_NOT_READY",
            "listo": not no_cubiertos,
            "dominios_core": core,
            "core_cubiertos": [c["domain"] for c in cubiertos],
            "core_no_cubiertos": [c["domain"] for c in no_cubiertos],
            "dominios_bloqueantes": [c["domain"] for c in core if c["bloquea"]],
            "fuentes_en_vivo_sin_snapshot": modos_sin_snapshot,
        },
        "veredicto": ("PRODUCTION_READY" if not no_cubiertos
                      else "CONTRACT_FROZEN / OPERATIONAL_NOT_READY"),
        "justificacion": (
            "El CONTRATO está congelado (registro, roles, modos, escalera, licencias y "
            "precedencia) y los dominios CORE con snapshot vigente resuelven con su "
            "authority_class original; pero "
            + (", ".join(c["domain"] for c in no_cubiertos) or "ninguno")
            + " NO tiene ruta automática válida hoy (geoportal HTTP 403 verificado y/o "
              "snapshot vencido o inexistente). Un CORE que solo puede declararse "
              "SOURCE_UNAVAILABLE no es «operativo»: por eso el veredicto NO es "
              "PRODUCTION_READY."),
    }


# ══════════════════════════════════════════════════════════════════════════════
# Sellado del registro (JSON + gemelo YAML) y del manifest
# ══════════════════════════════════════════════════════════════════════════════
def sellar_registro(registro: Optional[Dict[str, Any]] = None, *,
                    inventario: Optional[List[Dict[str, Any]]] = None,
                    fecha: Optional[str] = None) -> Dict[str, Any]:
    """Añade `product_role`, `acquisition_mode` y `acquisition_snapshot` a CADA fuente.

    La metadata del snapshot (ruta, sha256, fecha de commit, bytes) se toma del inventario
    REAL: si un artefacto cambia, el sello deja de coincidir y la prueba lo denuncia.
    """
    reg = dict(_registro(registro))
    reg.setdefault("reference_date", str(fecha or REFERENCE_DATE_POR_DEFECTO)[:10])
    reg.setdefault("acquisition_modes_version", PACK_ETIQUETA)
    inv = inventario if inventario is not None else descubrir_snapshots()
    fuentes = dict(reg.get("sources") or {})
    for sid, fuente in fuentes.items():
        f = dict(fuente)
        rol = rol_de_fuente(sid)
        f["product_role"] = rol
        f["acquisition_mode"] = modo_declarado_de_fuente(sid, f)
        snaps = snapshots_de_fuente(sid, inventario=inv)
        f["acquisition_snapshot"] = None
        f["acquisition_snapshot_descartados"] = []
        for s in snaps:
            vig = evaluar_vigencia(s, reg.get("reference_date"), registro=reg)
            sigue = bool(s.get("usable")) and vig["estado"] == SNAPSHOT_VIGENTE
            if not sigue:
                f["acquisition_snapshot_descartados"].append({
                    "artifact_id": s.get("artifact_id"),
                    "ruta": s["ruta"],
                    "kind": s.get("kind"),
                    "sha256": s.get("sha256"),
                    "fecha_de_creacion": s.get("fecha_de_creacion"),
                    "estado_vigencia": vig["estado"],
                    "limite": vig["limite"],
                    "motivo": (vig["motivo"] or s.get("motivo_no_usable") or ""),
                })
                if s.get("usable"):
                    f["acquisition_snapshot"] = {
                        "artifact_id": s.get("artifact_id"),
                        "ruta": s["ruta"],
                        "kind": s.get("kind"),
                        "bytes": s.get("bytes"),
                        "sha256": s.get("sha256"),
                        "fecha_de_creacion": s.get("fecha_de_creacion"),
                        "fecha_origen": s.get("fecha_origen"),
                        "modo": s.get("modo") or "",
                        "modo_clase": MODOS_SNAPSHOT_CLASE.get(s.get("modo") or "", ""),
                        "atributos": list(s.get("atributos") or []),
                        "consulta": s.get("consulta") or "",
                        "vigencia": {"estado": vig["estado"], "limite": vig["limite"],
                                     "familia": vig["familia"],
                                     "dias": vig["restriccion_dias"], "motivo": vig["motivo"]},
                        "resuelve_en_la_ventana": False,
                    }
                continue
            f["acquisition_snapshot"] = {
                "artifact_id": s.get("artifact_id"),
                "ruta": s["ruta"],
                "kind": s.get("kind"),
                "bytes": s.get("bytes"),
                "sha256": s.get("sha256"),
                "fecha_de_creacion": s.get("fecha_de_creacion"),
                "fecha_origen": s.get("fecha_origen"),
                "modo": s.get("modo") or "",
                "modo_clase": MODOS_SNAPSHOT_CLASE.get(s.get("modo") or "", ""),
                "atributos": list(s.get("atributos") or []),
                "consulta": s.get("consulta") or "",
                "vigencia": {"estado": vig["estado"], "limite": vig["limite"],
                             "familia": vig["familia"], "dias": vig["restriccion_dias"],
                             "motivo": vig["motivo"]},
                "resuelve_en_la_ventana": True,
            }
            break
        fuentes[sid] = f
    reg["sources"] = fuentes
    return reg


def escribir_registro_gemelo(registro: Dict[str, Any], *,
                            ruta_json: Any = RUTA_REGISTRO,
                            ruta_yaml: Any = RUTA_REGISTRO_YAML) -> Dict[str, str]:
    """Escribe el registro canónico (JSON) y su GEMELO legible (YAML) con el MISMO contenido."""
    pj = _ruta_absoluta(ruta_json)
    py = _ruta_absoluta(ruta_yaml)
    pj.write_text(json.dumps(registro, ensure_ascii=False, indent=1, sort_keys=True),
                  encoding="utf-8")
    py.write_text(_dump_yaml(registro), encoding="utf-8")
    return {"json": str(pj), "yaml": str(py), "sha256_json": hash_archivo(pj),
            "sha256_yaml": hash_archivo(py), "payload_sha256": ds.hash_canonico(registro)}


def _dump_yaml(payload: Dict[str, Any]) -> str:
    """Gemelo YAML con la MISMA cabecera y huella que usa `scripts/source_pack_build.py`."""
    cabecera = (
        "# " + "=" * 76 + "\n"
        "# BARRANQUILLA SOURCE PACK v1.0 — registro de fuentes (gemelo legible)\n"
        "#\n"
        "# Este archivo es el GEMELO LEGIBLE de barranquilla_sources_v1.json, que es el\n"
        "# registro canónico que lee api/dictus_sources.cargar_registro(). Ambos tienen\n"
        "# EXACTAMENTE el mismo contenido y se regeneran juntos con:\n"
        "#     python scripts/source_pack_build.py\n"
        "#     python -m api.acquisition --escribir   (capa de adquisición: product_role,\n"
        "#                                             acquisition_mode, snapshots reales)\n"
        "#\n"
        "# Cada fuente declara las 25 claves del contrato de fuentes (§33): source_id,\n"
        "# source_name, institution, authority_class, base_url, service, layer_id,\n"
        "# layer_name, geometry_type, query_method, expected_fields, primary_keys,\n"
        "# binding_fields, spatial_reference, legal_or_normative_context,\n"
        "# version_or_vigency, precedence, fallback_policy, freshness_policy,\n"
        "# failure_semantics, license_or_terms, can_persist_raw, can_embed_image,\n"
        "# provenance_fields, enabled. Más spec_layer_id, verification_status,\n"
        "# local_fallback, notes, evidence, product_role, acquisition_mode y\n"
        "# acquisition_snapshot (capa de adquisición: docs/source_pack/ACQUISITION_MODES.md).\n"
        "# " + "=" * 76 + "\n")
    try:
        import yaml  # type: ignore
        cuerpo = yaml.safe_dump(payload, allow_unicode=True, sort_keys=True, width=100,
                                default_flow_style=False)
    except Exception:  # noqa: BLE001 — sin PyYAML el JSON sigue siendo el canónico
        cuerpo = json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True)
    return f"{cabecera}# payload_sha256: {ds.hash_canonico(payload)}\n{cuerpo}"


def sellar_manifest(registro: Optional[Dict[str, Any]] = None, *,
                    inventario: Optional[Dict[str, Any]] = None,
                    estado: Optional[Dict[str, Any]] = None,
                    filas: Optional[Sequence[Dict[str, Any]]] = None,
                    ruta: Any = RUTA_MANIFEST) -> Dict[str, Any]:
    """Añade al manifest las secciones de la capa de adquisición (sin tocar `coverage`)."""
    p = _ruta_absoluta(ruta)
    man = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    reg = _registro(registro)
    inv = inventario if inventario is not None else inventario_snapshots(registro=reg)
    estado = estado if estado is not None else estado_operativo(registro=reg, filas=filas)
    man["manifest_version"] = "barranquilla-source-pack-manifest/1.1.0"
    man["tested_at"] = datetime.now(timezone.utc).isoformat()
    man["acquisition_modes"] = {
        "version": PACK_ETIQUETA,
        "modes": list(ACQUISITION_MODES),
        "rule": ("Si LIVE_QUERY falla (SOURCE_UNAVAILABLE/NOT_SUPPORTED/QUERY_FAILED) y "
                 "existe un snapshot automático dentro de su freshness_policy, se resuelve "
                 "desde el snapshot CONSERVANDO la authority_class de la fuente ORIGINAL. "
                 "Un snapshot vencido NO resuelve: se declara y se sigue la escalera."),
        "freshness_default_dias": {k: v["dias"] for k, v in FRESHNESS_DEFAULT.items()},
        "reference_date": fecha_de_referencia(reg),
        "snapshot_inventory": _ruta_relativa(RUTA_INVENTARIO),
        "matrix_file": _ruta_relativa(RUTA_MATRIZ),
        "docs": "docs/source_pack/ACQUISITION_MODES.md",
    }
    man["product_roles"] = {
        "vocabulary": list(PRODUCT_ROLES),
        "core_roles": list(ROLES_CORE),
        "requisitos_por_rol": REQUISITOS_POR_ROL,
        "historica_es_referencia": REQUISITOS_HISTORICA,
    }
    man["operational_readiness"] = {
        "veredicto": estado["veredicto"],
        "contract_frozen": True,
        "operational_ready": estado["operational_ready"]["listo"],
        "core_cubiertos": estado["operational_ready"]["core_cubiertos"],
        "core_no_cubiertos": estado["operational_ready"]["core_no_cubiertos"],
        "dominios_bloqueantes": estado["operational_ready"]["dominios_bloqueantes"],
        "justificacion": estado["justificacion"],
        "geoportal_http_403_verificado": True,
    }
    man["snapshot_inventory"] = inv["resumen"]
    # Las huellas de metadata se recalculan sobre la entrada SELLADA (incluye la capa de
    # adquisición) con la MISMA fórmula del constructor del pack: sha256 canónico de la
    # entrada sin `evidence`.
    man["source_metadata_hashes"] = {
        sid: ds.hash_canonico({k: v for k, v in f.items() if k != "evidence"})
        for sid, f in (reg.get("sources") or {}).items()}
    man["source_metadata_hashes_formula"] = ("sha256 canónico de la entrada de la fuente sin "
                                             "`evidence` (incluye product_role, "
                                             "acquisition_mode y acquisition_snapshot)")
    p.write_text(json.dumps(man, ensure_ascii=False, indent=1, sort_keys=True),
                 encoding="utf-8")
    return man


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════
def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Modo de adquisición por fuente y estado CONTRACT_FROZEN/"
                    "OPERATIONAL_READY del Barranquilla Source Pack.")
    ap.add_argument("--estado", action="store_true", help="imprime el veredicto y la cobertura")
    ap.add_argument("--inventario", action="store_true", help="imprime el inventario (JSON)")
    ap.add_argument("--matriz", action="store_true", help="imprime la matriz (CSV)")
    ap.add_argument("--escribir", action="store_true",
                    help="escribe registro+gemelo sellados, matriz, inventario y manifest")
    args = ap.parse_args(argv)

    reg = _registro()
    filas = matriz_roles(registro=reg)
    if args.escribir:
        inventario = inventario_snapshots(registro=reg)
        sellado = sellar_registro(reg)
        info = escribir_registro_gemelo(sellado)
        p_matriz = escribir_matriz(filas)
        p_inv = escribir_inventario(registro=sellado)
        estado = estado_operativo(registro=sellado, filas=filas,
                                  inventario=inventario["snapshots"])
        sellar_manifest(sellado, inventario=inventario, estado=estado, filas=filas)
        print(f"registro sellado: {info['json']} (payload_sha256 {info['payload_sha256'][:16]})")
        print(f"gemelo YAML: {info['yaml']} (sha256 {info['sha256_yaml'][:16]})")
        print(f"matriz: {p_matriz} ({len(filas)} filas × {len(COLUMNAS_MATRIZ)} columnas)")
        print(f"inventario: {p_inv}")
        print(f"manifest: {_ruta_relativa(RUTA_MANIFEST)}")
        print(f"VEREDICTO: {estado['veredicto']}")
        return 0
    if args.inventario:
        print(json.dumps(inventario_snapshots(registro=reg), ensure_ascii=False, indent=1,
                         sort_keys=True))
        return 0
    if args.matriz:
        import io
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=list(COLUMNAS_MATRIZ))
        w.writeheader()
        for fila in filas:
            w.writerow({c: fila.get(c, "") for c in COLUMNAS_MATRIZ})
        print(buf.getvalue())
        return 0
    estado = estado_operativo(registro=reg, filas=filas)
    print(f"reference_date: {estado['reference_date']}")
    print(f"contract: {estado['contract_frozen']['estado']} "
          f"({len(estado['contract_frozen']['criterios'])} criterios)")
    print(f"operational: {estado['operational_ready']['estado']}")
    print(f"  CORE cubiertos: {estado['operational_ready']['core_cubiertos']}")
    print(f"  CORE NO cubiertos: {estado['operational_ready']['core_no_cubiertos']}")
    print(f"VEREDICTO: {estado['veredicto']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

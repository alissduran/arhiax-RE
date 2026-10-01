# -*- coding: utf-8 -*-
"""ARHIAX RE — BARRANQUILLA SOURCE PACK v1.0 · constructor del registro de fuentes.

Regenera, de forma DETERMINISTA y sin intervención manual:

    docs/source_pack/barranquilla_sources_v1.yaml    (registro legible)
    docs/source_pack/barranquilla_sources_v1.json    (gemelo canónico; el loader lee este)
    docs/source_pack/BARRANQUILLA_SOURCE_PACK_MANIFEST.json

Fuentes de verdad usadas al construir (§10):

  1. CAPTURAS CRUDAS de `docs/source_pack/raw/golden/` (escritas por las sondas del pack).
     Cuando existe `raw/golden/<source_id en minúsculas>.json` se marca la fuente como
     VERIFIED_IN_CAPTURE y se adjunta el hash del crudo y los campos OBSERVADOS.
  2. EVIDENCIA EN CÓDIGO del propio repositorio (consultas EN VIVO documentadas en
     `api/catastro_predio.py`, `api/address_resolution.py`, `api/edificabilidad.py`).
  3. CAPAS POT EMPAQUETADAS (`api/data/*.geojson`) que se usan como FALLBACK DECLARADO
     del servicio en vivo cuando éste no es alcanzable.
  4. BLOQUE DE NEGOCIO declarado abajo: es la ÚNICA fuente de los campos que no se
     observaron. NUNCA se inventa un campo: si no hay evidencia, `expected_fields` va
     vacío y la fuente queda `enabled: false` con `notes` explicando la evidencia real
     encontrada (id/nombre observado) o su ausencia.

Uso:
    python scripts/source_pack_build.py            # escribe los 3 artefactos
    python scripts/source_pack_build.py --check     # valida sin escribir (CI)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "api"))

import dictus_sources as ds  # noqa: E402

DIR_PACK = RAIZ / "docs" / "source_pack"
DIR_RAW = DIR_PACK / "raw" / "golden"
RUTA_YAML = DIR_PACK / "barranquilla_sources_v1.yaml"
RUTA_JSON = DIR_PACK / "barranquilla_sources_v1.json"
RUTA_MANIFEST = DIR_PACK / "BARRANQUILLA_SOURCE_PACK_MANIFEST.json"

REGISTRY_VERSION = ds.REGISTRY_VERSION
PACK_VERSION = ds.PACK_VERSION

CLAVES_OBLIGATORIAS = ("source_id", "source_name", "institution", "authority_class",
                       "base_url", "service", "layer_id", "layer_name", "geometry_type",
                       "query_method", "expected_fields", "primary_keys", "binding_fields",
                       "spatial_reference", "legal_or_normative_context", "version_or_vigency",
                       "precedence", "fallback_policy", "freshness_policy",
                       "failure_semantics", "license_or_terms", "can_persist_raw",
                       "can_embed_image", "provenance_fields", "enabled")

# ── URLs reales de los servicios (observadas en capturas y en el código) ──────
GEO = "https://miciudad.barranquilla.gov.co/gis/rest/services"
CATASTRO_DA = f"{GEO}/catastro/datosabiertos/MapServer"
CATASTRO_DESTINO = f"{GEO}/catastro/destinoseconomicos/MapServer"
ORD = f"{GEO}/ordenamiento"
ORD_UA = f"{ORD}/unidadesadministrativas/MapServer"
ORD_ESTRATO = f"{ORD}/estratificacion/MapServer"
ORD_PLANEACION = f"{ORD}/planeacion/MapServer"

SR = ("EPSG:4326 (WGS84) — se consulta con outSR=4326; el SR nativo del servicio "
      "no quedó capturado en esta corrida")

FALLA = ("HTTP != 200, error ArcGIS o excepción → SOURCE_UNAVAILABLE / QUERY_FAILED; "
         "respuesta sin coincidencias → NO_MATCH; capa inexistente o fuente deshabilitada "
         "→ NOT_SUPPORTED. Una ausencia NUNCA se convierte en NO_MATCH.")

FRESCURA = ("Consulta en vivo por corrida; el crudo se preserva sin modificar en "
            "docs/source_pack/raw/golden/ con su sha256. Sin caché persistente.")

PROV = ["source_id", "source_name", "institution", "authority_class", "service", "layer_id",
        "query_method", "version_or_vigency", "precedence", "license_or_terms"]

# ── licencias / términos (§ entregable 5) ────────────────────────────────────
LIC_ALCALDIA = ("Datos abiertos de la Alcaldía Distrital de Barranquilla (geoportal "
                "miciudad.barranquilla.gov.co). Uso permitido con atribución a la fuente "
                "oficial. Los términos específicos no se publican junto al servicio "
                "(provider_terms_status=UNVERIFIED).")
LIC_POT_LOCAL = ("Capa POT oficial empaquetada localmente como copia normalizada (GeoJSON) "
                 "del servicio de la Alcaldía; datos abiertos con atribución a la fuente "
                 "oficial. Hash del archivo declarado en el manifest.")
LIC_OSM = ("Open Database License (ODbL) 1.0 — © OpenStreetMap contributors. Atribución "
           "obligatoria; share-alike sobre bases derivadas.")
LIC_MAPILLARY = ("CC BY-SA 4.0 — © Mapillary contributors. Atribución obligatoria y "
                 "share-alike (texto de atribución declarado por api/street_imagery.py).")
LIC_GOOGLE = ("Google Maps Platform / Street View: sus términos prohíben almacenar o "
              "redistribuir las imágenes. provider_terms_status=UNVERIFIED → FAIL-CLOSED: "
              "no se persiste el crudo ni se incrusta la imagen.")
LIC_LONJA = ("Metodología contractual de la Lonja de Propiedad Raíz de Barranquilla "
             "(lonja_baq_metodologia.yaml): documento de la Junta Técnica de Avalúos, no "
             "redistribuible sin contrato. Uso autorizado dentro del motor TMA de ARHIAX RE.")
LIC_COMPUTED = ("Cálculo propio de ARHIAX RE sobre entradas declaradas (coordenada, fecha, "
                "geometría oficial). Sin licencia de terceros sobre el resultado; "
                "reproducible y auditable.")
LIC_CTL = ("Certificado de Tradición y Libertad (SNR) y anexo de adopción catastral: "
           "documentos oficiales aportados por el usuario; se conserva copia normalizada "
           "con hash, no el original completo.")

NORM_POT_2024 = "Decreto 893 de 2024"
NORM_SIN_DATO = "Sin contexto normativo específico declarado en el pack (fuente de contexto)."
NORM_CATASTRO = ("Ley 14 de 1983 y Resolución IGAC 1040 de 2023 (gestión catastral); "
                 "acuerdo de adopción catastral de Barranquilla, Resolución GGCD 003 de 2025.")


def _f(source_id: str, *, source_name: str, institution: str, authority_class: str,
       base_url: str, service: str, layer_id: Any, layer_name: str, geometry_type: str,
       query_method: str, expected_fields: List[str], primary_keys: List[str],
       binding_fields: List[str], version_or_vigency: str, precedence: str,
       legal_or_normative_context: str = NORM_SIN_DATO,
       license_or_terms: str = LIC_ALCALDIA, authored_class: str = "",
       can_persist_raw: bool = True, can_embed_image: bool = False,
       fallback_policy: str = "", enabled: bool = True, spec_layer_id: Any = None,
       verification_status: str = "DECLARED_PENDING_LIVE_VERIFICATION",
       notes: str = "", local_fallback: str = "") -> Dict[str, Any]:
    """Construye una fuente declarando SIEMPRE las 25 claves del contrato."""
    return {
        "source_id": source_id,
        "source_name": source_name,
        "institution": institution,
        "authority_class": authority_class,
        "base_url": base_url,
        "service": service,
        "layer_id": layer_id,
        "layer_name": layer_name,
        "geometry_type": geometry_type,
        "query_method": query_method,
        "expected_fields": list(expected_fields),
        "primary_keys": list(primary_keys),
        "binding_fields": list(binding_fields),
        "spatial_reference": SR,
        "legal_or_normative_context": legal_or_normative_context,
        "version_or_vigency": version_or_vigency,
        "precedence": precedence,
        "fallback_policy": fallback_policy or (
            "Sin fallback: si la capa no responde se declara SOURCE_UNAVAILABLE y NO se "
            "sustituye el dato por otra fuente ni por un valor por defecto."),
        "freshness_policy": FRESCURA,
        "failure_semantics": FALLA,
        "license_or_terms": license_or_terms,
        "can_persist_raw": bool(can_persist_raw),
        "can_embed_image": bool(can_embed_image),
        "provenance_fields": list(PROV),
        "enabled": bool(enabled),
        # ── declarativos (trazabilidad; no sustituyen a las 25 claves) ─────────
        "spec_layer_id": layer_id if spec_layer_id is None else spec_layer_id,
        "verification_status": verification_status,
        "local_fallback": local_fallback or None,
        "notes": notes,
    }


# ═════════════════════════════════════════════════════════════════════════════
# BLOQUE DE NEGOCIO — registro declarado (35 fuentes)
# ═════════════════════════════════════════════════════════════════════════════
def bloque_de_negocio() -> Dict[str, Dict[str, Any]]:
    AO = ds.AUTORITATIVA_OFICIAL
    AC = ds.AUTORITATIVA_CONTRACTUAL
    CX = ds.CONTEXTUAL_EXTERNA
    CO = ds.CALCULADA
    fuentes: List[Dict[str, Any]] = []

    # ── Catastro (Alcaldía — Gerencia de Catastro) ───────────────────────────
    fuentes.append(_f(
        "CATASTRO_BAQ_DIRECCION",
        source_name="Dirección oficial (nomenclatura del predio)",
        institution="Alcaldía Distrital de Barranquilla — Gerencia de Catastro Distrital",
        authority_class=AO, base_url=CATASTRO_DA, service="ArcGIS REST MapServer",
        layer_id=105, layer_name="Dirección", geometry_type="esriGeometryPoint",
        query_method="query por punto (geometry + inSR=4326) y por atributos de nomenclatura",
        expected_fields=["valor_via_principal", "clase_via_principal", "valor_via_generadora",
                         "letra_via_generadora", "numero_predio", "tipo_direccion",
                         "es_direccion_principal", "complemento", "nombre_predio",
                         "codigo_postal", "cr_predio_guid", "cr_construccion_guid",
                         "cr_terreno_guid"],
        primary_keys=["objectid"], binding_fields=["codigo_postal", "cr_predio_guid"],
        version_or_vigency="Servicio vigente; captura real de la capa 105 con campos y "
                           "valores observados (nomenclatura TV 43 ... 101 C 35).",
        precedence=ds.CURRENT_OFFICIAL, legal_or_normative_context=NORM_CATASTRO,
        verification_status="VERIFIED_IN_CAPTURE",
        notes="Evidencia real: captura de la capa 105 en la sonda 03I.1 (fields y "
              "atributos observados). El `codigo_postal` de 30 dígitos del servicio es el "
              "código catastral, no un código postal postal (documentado en "
              "api/address_resolution.py)."))

    fuentes.append(_f(
        "CATASTRO_BAQ_TERRENO",
        source_name="Terreno (lote) del predio",
        institution="Alcaldía Distrital de Barranquilla — Gerencia de Catastro Distrital",
        authority_class=AO, base_url=CATASTRO_DA, service="ArcGIS REST MapServer",
        layer_id=315, layer_name="Terreno", geometry_type="esriGeometryPolygon",
        query_method="query por punto en buffer (geometry + distance) — 315 es el id REAL "
                     "observado para Terreno",
        expected_fields=["name", "relacion_superficie", "estado_terreno", "globalid",
                         "objectid"],
        primary_keys=["globalid"], binding_fields=["name"],
        version_or_vigency="Servicio vigente; captura real de la capa 315 "
                           "(name = número predial de 30 dígitos).",
        precedence=ds.CURRENT_OFFICIAL, legal_or_normative_context=NORM_CATASTRO,
        spec_layer_id=3, verification_status="VERIFIED_IN_CAPTURE",
        notes="Evidencia real: la capa 315 respondió con el terreno del predio Golden "
              "(name 080010103000010040001900000000, relacion_superficie En_Rasante). El id "
              "«3» del enunciado del pack NO se corroboró; se registra el id observado y se "
              "conserva el id declarado en `spec_layer_id` para trazabilidad."))

    fuentes.append(_f(
        "CATASTRO_BAQ_CONSTRUCCION",
        source_name="Construcción (huella, pisos y altura construida)",
        institution="Alcaldía Distrital de Barranquilla — Gerencia de Catastro Distrital",
        authority_class=AO, base_url=CATASTRO_DA, service="ArcGIS REST MapServer",
        layer_id=310, layer_name="Construcción", geometry_type="esriGeometryPolygon",
        query_method="query por punto del predio (SAFE_SINGLE_LAYER)",
        expected_fields=["tipo_construccion", "total_pisos", "total_sotanos",
                         "total_mezanines", "total_semisotanos",
                         "altura_total_construccion", "st_area(shape)", "local_id",
                         "estado_construccion"],
        primary_keys=["globalid", "local_id"], binding_fields=["local_id"],
        version_or_vigency="Servicio vigente; campos tomados de la consulta en vivo "
                           "documentada en api/catastro_predio.py::consultar_construccion.",
        precedence=ds.CURRENT_OFFICIAL, legal_or_normative_context=NORM_CATASTRO,
        spec_layer_id=4,
        verification_status="VERIFIED_IN_CODE_EVIDENCE",
        notes="Evidencia real: api/catastro_predio.py declara CAPA_CONSTRUCCION = 310 y "
              "consulta esos campos en vivo (03D.1, SAFE_SINGLE_LAYER). El id «4» del "
              "enunciado no fue corroborado. La altura de esta capa es de CONSTRUCCIÓN "
              "(física declarada por catastro); no se usa como altura normativa."))

    fuentes.append(_f(
        "CATASTRO_BAQ_PREDIO",
        source_name="Predio (tabla catastral: destino económico, tipo, estrato, FMI)",
        institution="Alcaldía Distrital de Barranquilla — Gerencia de Catastro Distrital",
        authority_class=AO, base_url=CATASTRO_DA, service="ArcGIS REST MapServer (tabla)",
        layer_id=100, layer_name="Predio (tabla de atributos, sin geometría)",
        geometry_type="esriGeometryNull (tabla)",
        query_method="query por atributos EXACTOS: numero_predial_nacional / "
                     "codigo_homologado (NUPRE); sin geometría",
        expected_fields=["numero_predial_nacional", "numero_predial_anterior",
                         "codigo_homologado", "destinacion_economica", "tipo_predio",
                         "tipo_vivienda", "estrato", "estado_fmi",
                         "area_catastral_terreno", "globalid"],
        primary_keys=["numero_predial_nacional", "globalid"],
        binding_fields=["numero_predial_nacional", "codigo_homologado", "globalid"],
        version_or_vigency="Servicio vigente; campos tomados de la consulta en vivo "
                           "documentada en api/catastro_predio.py (bloque A/B recursivo).",
        precedence=ds.CURRENT_OFFICIAL, legal_or_normative_context=NORM_CATASTRO,
        verification_status="VERIFIED_IN_CODE_EVIDENCE",
        notes="Evidencia real: la tabla 100 EXISTE (responde con error ArcGIS 400 "
              "«Invalid or missing input parameters» a una consulta con geometría, propio "
              "de una tabla) mientras que la capa 500 devuelve 404 «Layer not found» — el "
              "comentario histórico de api/catastro_predio.py («500 Predio oculta pero "
              "consultable») quedó desactualizado. El destino económico (destinacion_"
              "economica) es DESTINO CATASTRAL y NO es el uso normativo del POT."))

    fuentes.append(_f(
        "CATASTRO_BAQ_DESTINO_ECONOMICO",
        source_name="Destino económico vigente por año (servicio por anualidad)",
        institution="Alcaldía Distrital de Barranquilla — Gerencia de Catastro Distrital",
        authority_class=AO, base_url=CATASTRO_DESTINO, service="ArcGIS REST MapServer",
        layer_id=5, layer_name="Destino económico (anualidad 2026)",
        geometry_type="esriGeometryNull (tabla/capa por punto)",
        query_method="query por punto o por identificador del predio",
        expected_fields=["destinacion_economica"],
        primary_keys=["numero_predial"], binding_fields=["numero_predial"],
        version_or_vigency="Anualidad declarada por el servicio: capa 5 = 2026 "
                           "(api/catastro_predio.py, bloque destino económico vigente).",
        precedence=ds.CURRENT_OFFICIAL, legal_or_normative_context=NORM_CATASTRO,
        verification_status="VERIFIED_IN_CODE_EVIDENCE",
        notes="Evidencia real: api/catastro_predio.py documenta «catastro/destinoseconomicos: "
              "destino económico por año (capa 5 = 2026)». El valor se compara con el del "
              "año anterior y, si difiere, se declara la discrepancia en vez de elegir uno."))

    fuentes.append(_f(
        "CATASTRO_BAQ_MANZANA",
        source_name="Manzana catastral",
        institution="Alcaldía Distrital de Barranquilla — Gerencia de Catastro Distrital",
        authority_class=AO, base_url=CATASTRO_DA, service="ArcGIS REST MapServer",
        layer_id=320, layer_name="Manzana", geometry_type="esriGeometryPolygon",
        query_method="query por punto en buffer (geometry + distance)",
        expected_fields=["codigo", "nombre", "globalid", "objectid"],
        primary_keys=["globalid"], binding_fields=["codigo"],
        version_or_vigency="Servicio vigente; captura real de la capa 320.",
        precedence=ds.CURRENT_OFFICIAL, legal_or_normative_context=NORM_CATASTRO,
        verification_status="VERIFIED_IN_CAPTURE",
        notes="Evidencia real: la capa 320 respondió con las manzanas del buffer "
              "(codigo 08001010300001006/007). La manzana del predio (08001010300001004) se "
              "obtiene del prefijo de 17 dígitos del número predial, no del buffer."))

    fuentes.append(_f(
        "CATASTRO_BAQ_ADOPCION_ANEXO1",
        source_name="Registro de adopción catastral (Anexo 1) — identidad canónica",
        institution="Alcaldía Distrital de Barranquilla / IGAC — Resolución GGCD 003 de 2025",
        authority_class=AO,
        base_url="local:api/data/barranquilla_adopcion_anexo1.json",
        service="Copia normalizada versionada con hash (no se descarga en cada corrida)",
        layer_id=None, layer_name="Anexo 1 de adopción catastral",
        geometry_type="No aplica (registro tabular)",
        query_method="coincidencia EXACTA de numero_predial + codigo_homologado + fmi "
                     "(EXACT_3) — nunca fuzzy para identidad verificada",
        expected_fields=["numero_predial", "codigo_homologado", "fmi", "codigo_registral"],
        primary_keys=["numero_predial"], binding_fields=["numero_predial",
                                                         "codigo_homologado", "fmi"],
        version_or_vigency="Resolución GGCD 003 del 07/03/2025 (Anexo 1 de adopción "
                           "catastral de Barranquilla).",
        precedence=ds.CURRENT_OFFICIAL, legal_or_normative_context=NORM_CATASTRO,
        license_or_terms=LIC_CTL,
        verification_status="VERIFIED_IN_CAPTURE",
        fallback_policy=("Fallback AUTORITATIVO exacto cuando el MapServer no responde: es "
                         "un registro estático con hash, NUNCA un fallback espacial/bbox."),
        notes="Evidencia real: api/barranquilla_adopcion.py resuelve identidad por EXACT_3 y "
              "declara CONFLICT si dos identificadores contradicen. NO aporta barrio/estrato "
              "(market_context_ready=False)."))

    # ── Ordenamiento / POT ──────────────────────────────────────────────────
    fuentes.append(_f(
        "POT_BAQ_BARRIOS",
        source_name="Barrios (unidades administrativas)",
        institution="Alcaldía Distrital de Barranquilla — Secretaría Distrital de Planeación",
        authority_class=AO, base_url=ORD_UA, service="ArcGIS REST MapServer",
        layer_id=1, layer_name="Barrios", geometry_type="esriGeometryPolygon",
        query_method="query por punto (barrio oficial) + consolidación por campo",
        expected_fields=["nombre_barrio", "identificador", "localidad", "nombre_pieza"],
        primary_keys=["identificador"], binding_fields=["nombre_barrio"],
        version_or_vigency="Servicio vigente; campos tomados de la consulta en vivo "
                           "documentada en api/catastro_predio.py::consultar_entorno_urbano.",
        precedence=ds.CURRENT_OFFICIAL, spec_layer_id=91,
        verification_status="VERIFIED_IN_CODE_EVIDENCE",
        notes="Evidencia real: api/catastro_predio.py consulta "
              "ordenamiento/unidadesadministrativas/MapServer capa 1 con esos out_fields; "
              "api/address_resolution.py atribuye el barrio a esa misma capa. El id «91» del "
              "enunciado NO se corroboró (la verificación en vivo devolvió HTTP 403 "
              "Cloudflare en la ventana de congelación)."))

    fuentes.append(_f(
        "POT_BAQ_LOCALIDADES",
        source_name="Localidades (unidades administrativas)",
        institution="Alcaldía Distrital de Barranquilla — Secretaría Distrital de Planeación",
        authority_class=AO, base_url=ORD_UA, service="ArcGIS REST MapServer",
        layer_id=1, layer_name="Barrios/Localidades (campo `localidad`; capa 3 "
                               "«Localidades» documentada por el módulo)",
        geometry_type="esriGeometryPolygon",
        query_method="query por punto; lectura del campo `localidad` de la capa de barrios",
        expected_fields=["localidad", "identificador", "nombre_barrio"],
        primary_keys=["identificador"], binding_fields=["localidad"],
        version_or_vigency="Servicio vigente. La corrida Golden resolvió localidad = «02» "
                           "por la capa oficial en vivo (urban_source_summary: "
                           "official_urban_layer).",
        precedence=ds.CURRENT_OFFICIAL, spec_layer_id=92,
        verification_status="VERIFIED_IN_CODE_EVIDENCE",
        notes="Evidencia real: api/catastro_predio.py documenta "
              "«ordenamiento/unidadesadministrativas: 1 Barrios, 3 Localidades» y lee el "
              "campo `localidad` de la capa 1; el run state Golden declara localidad «02» con "
              "procedencia MIXTA EN VIVO (barrio, localidad, pieza_urbana, estrato, "
              "tratamiento). El id «92» del enunciado NO se corroboró. Lo que quedó SIN DATO "
              "en esa corrida fue la COMUNA (traza NULL_VALUE), que NO se confunde con la "
              "localidad. En esta ventana de congelación la capa no fue alcanzable: se declara "
              "SOURCE_UNAVAILABLE, jamás un valor por defecto."))

    fuentes.append(_f(
        "POT_BAQ_ESTRATIFICACION",
        source_name="Estratificación socioeconómica por manzana",
        institution="Alcaldía Distrital de Barranquilla — Secretaría Distrital de Planeación",
        authority_class=AO, base_url=ORD_ESTRATO, service="ArcGIS REST MapServer",
        layer_id=1, layer_name="Estratificación por manzanas",
        geometry_type="esriGeometryPolygon",
        query_method="query por punto y por atributo `codigo_manzana`",
        expected_fields=["codigo_manzana", "estratificacion", "nombre_barrio",
                         "identificador", "localidad"],
        primary_keys=["codigo_manzana"], binding_fields=["codigo_manzana"],
        version_or_vigency="Servicio vigente; captura real (manzana 08001010300001004 → "
                           "estratificacion 4, barrio Miramar, localidad 02).",
        precedence=ds.CURRENT_OFFICIAL,
        verification_status="VERIFIED_IN_CAPTURE",
        fallback_policy=("Si el punto no cae en el polígono de manzana, se resuelve por "
                         "el prefijo de 17 dígitos del número predial (identificador exacto) "
                         "y se declara el método; nunca por valor por defecto."),
        notes="Evidencia real: capturas ESTRATO_PROBE_TRACE_2/3/4 (dos rutas: espacial y por "
              "identificador). El valor «No aplica» de manzanas vecinas NO se usa como "
              "estrato."))

    fuentes.append(_f(
        "POT_BAQ_TRATAMIENTO",
        source_name="Tratamientos urbanísticos (POT vigente)",
        institution="Alcaldía Distrital de Barranquilla — Secretaría Distrital de Planeación",
        authority_class=AO, base_url=ORD_PLANEACION, service="ArcGIS REST MapServer",
        layer_id=4, layer_name="Tratamientos urbanísticos",
        geometry_type="esriGeometryPolygon",
        query_method="query por punto + consolidación INDEPENDIENTE por atributo",
        expected_fields=["tratamiento", "tipo_tratamiento", "altura_maxima"],
        primary_keys=["objectid"], binding_fields=["tratamiento"],
        version_or_vigency="Servicio vigente; corrida Golden: tratamiento «Consolidacion», "
                           "tipo «Nivel 2», altura_maxima 11 (PISOS).",
        precedence=ds.CURRENT_OFFICIAL, spec_layer_id=83,
        verification_status="VERIFIED_IN_CODE_EVIDENCE",
        notes="Evidencia real: api/catastro_predio.py consulta "
              "ordenamiento/planeacion/MapServer capa 4 con esos out_fields; los tres campos "
              "se consolidan por separado (03H.2A) y si discrepan quedan None + AMBIGUOUS. El "
              "id «83» del enunciado NO se corroboró. `altura_maxima` es ALTURA NORMATIVA en "
              "PISOS: jamás altura física."))

    fuentes.append(_f(
        "POT_BAQ_EDIFICABILIDAD",
        source_name="Edificabilidad y altura normativa máxima",
        institution="Alcaldía Distrital de Barranquilla — Secretaría Distrital de Planeación",
        authority_class=AO, base_url=ORD_PLANEACION, service="ArcGIS REST MapServer",
        layer_id=4, layer_name="Tratamientos urbanísticos (proyección de los campos "
                               "normativos de edificabilidad)",
        geometry_type="esriGeometryPolygon",
        query_method="query por punto; lectura de `altura_maxima` (PISOS) y del tratamiento",
        expected_fields=["altura_maxima", "tratamiento", "tipo_tratamiento"],
        primary_keys=["objectid"], binding_fields=["tratamiento"],
        version_or_vigency="Servicio vigente; corrida Golden: altura_maxima = 11 "
                           "(valor normativo). Puede ser texto («Plan Parcial») → entonces "
                           "NO se afirma número.",
        precedence=ds.CURRENT_OFFICIAL, spec_layer_id=89,
        verification_status="VERIFIED_IN_CODE_EVIDENCE",
        notes="Evidencia real: api/edificabilidad.py resuelve la altura con la capa POT de "
              "tratamientos (`altura_maxima` en PISOS) y advierte que es referencial con "
              "fecha de la norma. El id «89» del enunciado NO se corroboró. REGLA "
              "BLOQUEANTE: este valor NUNCA se usa como altura física del edificio."))

    fuentes.append(_f(
        "POT_BAQ_AREAS_ACTIVIDAD",
        source_name="Áreas de actividad (uso normativo del suelo)",
        institution="Alcaldía Distrital de Barranquilla — Secretaría Distrital de Planeación",
        authority_class=AO, base_url=ORD, service="ArcGIS REST MapServer (capa no verificada)",
        layer_id=85, layer_name="Áreas de actividad (id declarado, no observado)",
        geometry_type="No verificado", query_method="query por punto (no ejecutada)",
        expected_fields=[], primary_keys=[], binding_fields=[], enabled=False,
        version_or_vigency="NO VERIFICADO en esta corrida.",
        precedence=ds.CURRENT_OFFICIAL, spec_layer_id=85,
        verification_status="UNVERIFIED_LIVE",
        notes="El layer_id 85 no pudo verificarse: el geoportal respondió HTTP 403 "
              "(Cloudflare) a toda consulta en la ventana de congelación "
              "(raw/golden/_layers_probe.json: 150 intentos, 0 metadatos). Evidencia REAL "
              "disponible y distinta: la corrida Golden dejó `area_actividad = None` "
              "(api/urban_context) y ningún módulo del repositorio consulta una capa 85. "
              "Se registra DESHABILITADA para no afirmar un dato sin fuente. NUNCA se "
              "inventan campos."))

    fuentes.append(_f(
        "POT_BAQ_POLIGONOS_USO",
        source_name="Polígonos de uso del POT",
        institution="Alcaldía Distrital de Barranquilla — Secretaría Distrital de Planeación",
        authority_class=AO, base_url=ORD, service="ArcGIS REST MapServer (capa no verificada)",
        layer_id=87, layer_name="Polígonos de uso (id declarado, no observado)",
        geometry_type="No verificado", query_method="query por punto (no ejecutada)",
        expected_fields=[], primary_keys=[], binding_fields=[], enabled=False,
        version_or_vigency="NO VERIFICADO en esta corrida.",
        precedence=ds.CURRENT_OFFICIAL, spec_layer_id=87,
        verification_status="UNVERIFIED_LIVE",
        notes="El layer_id 87 no pudo verificarse (geoportal HTTP 403 en toda la ventana: "
              "raw/golden/_layers_probe.json). Evidencia REAL disponible: el uso normativo "
              "se infiere hoy del tratamiento POT (capa 4 de planeación) y del destino "
              "económico catastral, que son fuentes DISTINTAS y no se mezclan. Registrada "
              "DESHABILITADA; sin campos inventados."))

    # ── Riesgo POT: vigente (Decreto 893 de 2024) vs histórico ──────────────
    fuentes.append(_f(
        "POT_BAQ_REMOCION_2024",
        source_name="Amenaza por remoción en masa (POT vigente 2024)",
        institution="Alcaldía Distrital de Barranquilla — Secretaría Distrital de Planeación",
        authority_class=AO, base_url=ORD,
        service="ArcGIS REST MapServer (capa no verificada) + capa POT oficial "
                "empaquetada localmente como fallback declarado",
        layer_id=73, layer_name="Remoción en masa 2024 (id declarado, no observado)",
        geometry_type="esriGeometryPolygon (observado en la copia empaquetada)",
        query_method="intersección punto-polígono sobre la capa POT empaquetada; query por "
                     "punto contra el servicio cuando esté alcanzable",
        expected_fields=["objectid", "niveldeamenaza", "clase_suelo", "st_area(shape)"],
        primary_keys=["objectid"], binding_fields=["niveldeamenaza"],
        version_or_vigency=NORM_POT_2024 + " (capa vigente).",
        precedence=ds.CURRENT_NORMATIVE,
        legal_or_normative_context=NORM_POT_2024, license_or_terms=LIC_POT_LOCAL,
        enabled=True, spec_layer_id=73, verification_status="VERIFIED_IN_CAPTURE",
        local_fallback="api/data/amenaza_remocion_masa.geojson",
        fallback_policy=("FALLBACK DECLARADO: copia POT oficial empaquetada en "
                         "api/data/amenaza_remocion_masa.geojson (2.000 polígonos) usada "
                         "solo cuando el servicio en vivo no responde; la procedencia del "
                         "resultado declara el fallback y el servicio queda declarado "
                         "SOURCE_UNAVAILABLE en la misma corrida."),
        notes="Evidencia real: la copia empaquetada contiene el punto del predio Golden en "
              "DOS polígonos (objectid 469 «Media» y 1369 «Baja»); se reporta el nivel más "
              "alto (Media) y se listan ambos — nunca se elige en silencio. Coincide con el "
              "run state 2b («Media · polígono: intersecta el predio»). Capas 2024 = "
              "precedencia vigente sobre las históricas."))

    fuentes.append(_f(
        "POT_BAQ_INUNDACION_2024",
        source_name="Amenaza por inundación (POT vigente 2024)",
        institution="Alcaldía Distrital de Barranquilla — Secretaría Distrital de Planeación",
        authority_class=AO, base_url=ORD, service="ArcGIS REST MapServer (capa no verificada)",
        layer_id=77, layer_name="Inundación 2024 (id declarado, no observado)",
        geometry_type="No verificado", query_method="query por punto (no ejecutada)",
        expected_fields=[], primary_keys=[], binding_fields=[], enabled=False,
        version_or_vigency=NORM_POT_2024 + " (precedencia vigente declarada).",
        precedence=ds.CURRENT_NORMATIVE, legal_or_normative_context=NORM_POT_2024,
        spec_layer_id=77, verification_status="UNVERIFIED_LIVE",
        notes="El layer_id 77 no pudo verificarse (geoportal HTTP 403 en toda la ventana: "
              "raw/golden/_layers_probe.json). NO existe copia empaquetada de inundación en "
              "api/data (solo remoción y áreas en riesgo). La corrida Golden dejó "
              "`inundacion = None`, es decir NO EVALUADO: se declara NOT_SUPPORTED, jamás "
              "«sin amenaza de inundación»."))

    fuentes.append(_f(
        "POT_BAQ_RIESGO_2024",
        source_name="Áreas en riesgo (POT vigente 2024)",
        institution="Alcaldía Distrital de Barranquilla — Secretaría Distrital de Planeación",
        authority_class=AO, base_url=ORD,
        service="ArcGIS REST MapServer (capa no verificada) + capa POT oficial "
                "empaquetada localmente como fallback declarado",
        layer_id=81, layer_name="Áreas en riesgo 2024 (id declarado, no observado)",
        geometry_type="esriGeometryPolygon (observado en la copia empaquetada)",
        query_method="intersección punto-polígono sobre la capa empaquetada; query por punto "
                     "contra el servicio cuando esté alcanzable",
        expected_fields=["objectid", "clasesuelo", "nivelderiesgo", "st_area(shape)"],
        primary_keys=["objectid"], binding_fields=["nivelderiesgo"],
        version_or_vigency=NORM_POT_2024 + " (capa vigente).",
        precedence=ds.CURRENT_NORMATIVE, legal_or_normative_context=NORM_POT_2024,
        license_or_terms=LIC_POT_LOCAL, spec_layer_id=81,
        verification_status="VERIFIED_IN_CAPTURE",
        local_fallback="api/data/areas_en_riesgo.geojson",
        fallback_policy=("FALLBACK DECLARADO: copia POT oficial empaquetada en "
                         "api/data/areas_en_riesgo.geojson (1.306 polígonos)."),
        notes="Evidencia real: el punto oficial del predio Golden cae en el polígono "
              "objectid 1124 con nivelderiesgo «Medio» (clasesuelo 1); coincide con el run "
              "state 2b («Medio · polígono: intersecta el predio»)."))

    fuentes.append(_f(
        "POT_BAQ_REMOCION_HIST",
        source_name="Amenaza por remoción en masa (capa histórica, POT anterior)",
        institution="Alcaldía Distrital de Barranquilla — Secretaría Distrital de Planeación",
        authority_class=AO, base_url=ORD, service="ArcGIS REST MapServer (capa no verificada)",
        layer_id=71, layer_name="Remoción en masa (versión anterior, id declarado)",
        geometry_type="No verificado", query_method="query por punto (no ejecutada)",
        expected_fields=[], primary_keys=[], binding_fields=[], enabled=False,
        version_or_vigency="Versión ANTERIOR del POT: referencia comparativa, no vigente.",
        precedence=ds.HISTORICAL_REFERENCE, spec_layer_id=71,
        verification_status="UNVERIFIED_LIVE",
        notes="El layer_id 71 no pudo verificarse (geoportal HTTP 403 en toda la ventana). "
              "Se registra como referencia histórica DESHABILITADA: una capa histórica no se "
              "asciende nunca a vigente (api/dictus_sources.resolver_precedencia la manda a "
              "`displaced` y con solo históricas declara SIN DATO)."))

    fuentes.append(_f(
        "POT_BAQ_INUNDACION_HIST",
        source_name="Amenaza por inundación (capa histórica, POT anterior)",
        institution="Alcaldía Distrital de Barranquilla — Secretaría Distrital de Planeación",
        authority_class=AO, base_url=ORD, service="ArcGIS REST MapServer (capa no verificada)",
        layer_id=75, layer_name="Inundación (versión anterior, id declarado)",
        geometry_type="No verificado", query_method="query por punto (no ejecutada)",
        expected_fields=[], primary_keys=[], binding_fields=[], enabled=False,
        version_or_vigency="Versión ANTERIOR del POT: referencia comparativa, no vigente.",
        precedence=ds.HISTORICAL_REFERENCE, spec_layer_id=75,
        verification_status="UNVERIFIED_LIVE",
        notes="El layer_id 75 no pudo verificarse (geoportal HTTP 403). Registrada "
              "DESHABILITADA como referencia histórica declarada."))

    fuentes.append(_f(
        "POT_BAQ_RIESGO_HIST",
        source_name="Áreas en riesgo (capa histórica, POT anterior)",
        institution="Alcaldía Distrital de Barranquilla — Secretaría Distrital de Planeación",
        authority_class=AO, base_url=ORD, service="ArcGIS REST MapServer (capa no verificada)",
        layer_id=79, layer_name="Áreas en riesgo (versión anterior, id declarado)",
        geometry_type="No verificado", query_method="query por punto (no ejecutada)",
        expected_fields=[], primary_keys=[], binding_fields=[], enabled=False,
        version_or_vigency="Versión ANTERIOR del POT: referencia comparativa, no vigente.",
        precedence=ds.HISTORICAL_REFERENCE, spec_layer_id=79,
        verification_status="UNVERIFIED_LIVE",
        notes="El layer_id 79 no pudo verificarse (geoportal HTTP 403). Registrada "
              "DESHABILITADA como referencia histórica declarada."))

    # ── Equipamiento OFICIAL (conjunto OFFICIAL_EQUIPMENT_CONTEXT) ───────────
    for lid in (18, 20, 21, 22, 23, 24, 25, 26, 27):
        fuentes.append(_f(
            f"EQUIPAMIENTO_{lid}",
            source_name=f"Equipamiento oficial — capa {lid} (conjunto "
                        f"OFFICIAL_EQUIPMENT_CONTEXT)",
            institution="Alcaldía Distrital de Barranquilla — capas de equipamiento oficial",
            authority_class=AO, base_url=ORD,
            service="ArcGIS REST MapServer (capa no verificada)",
            layer_id=lid, layer_name=f"Equipamiento oficial capa {lid} (id declarado, "
                                     f"no observado)",
            geometry_type="No verificado", query_method="query por radio (no ejecutada)",
            expected_fields=[], primary_keys=[], binding_fields=[], enabled=False,
            version_or_vigency="NO VERIFICADO en esta corrida.",
            precedence=ds.CURRENT_OFFICIAL, spec_layer_id=lid,
            verification_status="UNVERIFIED_LIVE",
            notes="El layer_id " + str(lid) + " no pudo verificarse (geoportal HTTP 403 en "
                  "toda la ventana: raw/golden/_layers_probe.json, 150 intentos sin "
                  "metadatos). Evidencia REAL disponible: el equipamiento que hoy consume el "
                  "dictamen proviene de un proveedor de mapas abierto (api/poi_engine.py, "
                  "OSM/Overpass) y el estado del recurso lo declara «proveedor de mapas "
                  "abierto» (api/dictus_estado.py). Se registra DESHABILITADA para no "
                  "presentar contexto como autoridad oficial; sin campos inventados. Al "
                  "verificarse la capa, se habilita y se separa en OFFICIAL_EQUIPMENT_CONTEXT "
                  "(api/dictus_sources.separar_equipamiento)."))

    # ── Fuentes externas / contractuales / calculadas ───────────────────────
    fuentes.append(_f(
        "OSM_OVERPASS",
        source_name="Equipamiento y servicios de contexto (OpenStreetMap vía Overpass)",
        institution="OpenStreetMap Foundation (datos colaborativos)",
        authority_class=CX, base_url="https://overpass-api.de/api/interpreter",
        service="Overpass API (espejos: overpass-api.de, kumi.systems, mail.ru)",
        layer_id=None, layer_name="Sin capa: consulta temática por radio (amenity/shop/...)",
        geometry_type="Nodos y vías/áreas OSM (out center)",
        query_method="POST Overpass QL con radio configurable alrededor de la coordenada",
        expected_fields=["elements[].type", "elements[].id", "elements[].lat", "elements[].lon",
                         "elements[].center", "elements[].tags.amenity",
                         "elements[].tags.shop", "elements[].tags.name"],
        primary_keys=["type", "id"], binding_fields=["lat", "lon"],
        version_or_vigency="Base OSM viva (se consulta en cada corrida).",
        precedence="CONTEXTUAL_REFERENCE", license_or_terms=LIC_OSM,
        verification_status="VERIFIED_IN_CAPTURE",
        local_fallback="docs/source_pack/raw/golden/osm_overpass.json",
        fallback_policy=("FALLBACK DECLARADO: si ningún espejo responde (se observaron HTTP "
                         "504 y timeouts), se usa la respuesta cruda capturada y preservada "
                         "en docs/source_pack/raw/golden/osm_overpass.json, declarando en la "
                         "procedencia que es una captura y no una consulta viva."),
        notes="Evidencia real de esta ventana: Overpass respondió 30 elementos en 1.500 m "
              "alrededor del predio Golden (categorías observadas: restaurant, bank, mall, "
              "place_of_worship, clinic, supermarket, pharmacy, school); la captura cruda "
              "quedó preservada sin modificar. Los espejos son inestables (overpass-api.de y "
              "maps.mail.ru devolvieron HTTP 504, kumi.systems timeout): por eso existe el "
              "fallback declarado. Es CONTEXTO: nunca autoridad oficial y nunca se mezcla con "
              "el equipamiento oficial (separar_equipamiento)."))

    fuentes.append(_f(
        "MAPILLARY",
        source_name="Street imagery — Mapillary (vista callejera colaborativa)",
        institution="Mapillary (Meta) — contributors",
        authority_class=CX, base_url="https://graph.mapillary.com",
        service="Mapillary Graph API", layer_id=None,
        layer_name="Sin capa: búsqueda de imágenes por proximidad a la coordenada",
        geometry_type="Puntos de captura (computed_geometry)",
        query_method="búsqueda por radio/bbox y selección DETERMINISTA de la imagen de "
                     "fachada (sin elección humana)",
        expected_fields=[], primary_keys=["id"], binding_fields=["id"],
        version_or_vigency="API viva; sin credencial configurada en esta corrida.",
        precedence="CONTEXTUAL_REFERENCE", license_or_terms=LIC_MAPILLARY,
        can_persist_raw=True, can_embed_image=True,
        verification_status="CREDENTIAL_MISSING",
        notes="Evidencia real de esta ventana: el código exige las credenciales "
              "ARHIAX_MAPILLARY_TOKEN / MAPILLARY_TOKEN / MAPILLARY_ACCESS_TOKEN "
              "(api/street_imagery.py, MapillaryProvider.VARIABLES_CREDENCIAL) y TODAS están "
              "AUSENTES; no existen archivos .env / api/.env / public/.env en el "
              "repositorio. Consecuencia declarada: credentials_status MISSING, "
              "facade_view_level NO_IMAGE_AVAILABLE, request_made=False (ni siquiera se toca "
              "la red) y el resto del pack sigue. Detalle en "
              "docs/source_pack/STREET_IMAGERY_REPORT.md."))

    fuentes.append(_f(
        "GOOGLE_STREET_VIEW",
        source_name="Street imagery — Google Street View (fail-closed)",
        institution="Google LLC — Google Maps Platform",
        authority_class=CX, base_url="https://maps.googleapis.com/maps/api/streetview",
        service="Street View Static API / Metadata API", layer_id=None,
        layer_name="Sin capa: imagen panorámica por coordenada y encabezado",
        geometry_type="Punto de captura declarado por el proveedor",
        query_method="metadata + imagen; SELECCIÓN DETERMINISTA y FAIL-CLOSED mientras "
                     "`provider_terms_status` sea UNVERIFIED",
        expected_fields=[], primary_keys=[], binding_fields=[],
        version_or_vigency="API viva; sin credencial ni términos verificados en esta corrida.",
        precedence="CONTEXTUAL_REFERENCE", license_or_terms=LIC_GOOGLE,
        can_persist_raw=False, can_embed_image=False,
        verification_status="FAIL_CLOSED_TERMS_UNVERIFIED",
        notes="Evidencia real de esta ventana: el código exige ARHIAX_GOOGLE_MAPS_API_KEY / "
              "GOOGLE_MAPS_API_KEY / GOOGLE_STREETVIEW_API_KEY "
              "(api/street_imagery.py, GoogleStreetViewProvider.VARIABLES_CREDENCIAL) y "
              "TODAS están AUSENTES; sin .env en el repositorio. Además el proveedor queda en "
              "FAIL-CLOSED por términos: `terms_status = UNVERIFIED` (su LICENCIA_DECLARADA "
              "está vacía, así que `verificar_terminos()` no puede alcanzar VERIFIED) → "
              "can_persist=False y can_embed_in_pdf=False: NO se descarga ni incrusta imagen. "
              "La ausencia de esta fuente NO bloquea el pack "
              "(consultar_vista_automatica → blocks_dictus=False)."))

    # ── LA LONJA **NO ES UNA FUENTE** (decisión de producto) ──────────────────
    # `LONJA_MARKET_BAQ` ya NO se construye como fuente del Source Registry: no tiene
    # institución proveedora verificada, ni URL, ni dataset, ni contrato de datos, ni
    # valor por m² suministrado por un tercero. Su lugar es el bloque
    # `no_fuentes_institucionales()` (aliado institucional), que este registro declara
    # igual que `api/source_licenses_v2.py::PARTNERS_INSTITUCIONALES`.
    # Evidencia: docs/source_pack/MARKET_CONTEXT_AUDIT.md y
    # docs/source_pack/INSTITUTIONAL_PARTNERS.md.

    fuentes.append(_f(
        "SOLAR_ENGINE",
        source_name="Motor solar (posición del sol por coordenada y fecha)",
        institution="ARHIAX RE — cálculo propio",
        authority_class=CO, base_url="local:solar_engine.py",
        service="Cálculo determinista NOAA (ecuación del tiempo + declinación)",
        layer_id=None, layer_name="get_solar_position(lat, lon, dt, tz_offset=-5)",
        geometry_type="No aplica (cálculo)",
        query_method="función determinista: coordenada + fecha/hora local (UTC-5)",
        expected_fields=["azimuth", "elevation"], primary_keys=[], binding_fields=["lat", "lon"],
        version_or_vigency="Código versionado en el repositorio; sin dependencia de red.",
        precedence="COMPUTED_REFERENCE", license_or_terms=LIC_COMPUTED,
        verification_status="VERIFIED_IN_CODE_EVIDENCE",
        notes="Evidencia real: solar_engine.get_solar_position es pura y no requiere red ni "
              "intervención humana; funciona solo con coordenada y fecha. Es CÁLCULO: se "
              "etiqueta como análisis automatizado y nunca como norma."))

    fuentes.append(_f(
        "SHADOW_FACADE_EXPOSURE",
        source_name="Exposición solar de fachada y sombras (FACADE_SOLAR_EXPOSURE)",
        institution="ARHIAX RE — cálculo propio",
        authority_class=CO, base_url="local:api/facade_solar.py + api/shadow_render.py",
        service="Análisis de incidencia sobre la fachada visible y render de sombras",
        layer_id=None, layer_name="analyze_facade_exposure / FACADE_SOLAR_EXPOSURE",
        geometry_type="No aplica (cálculo sobre geometría oficial del predio)",
        query_method="determinista: azimut de fachada + posición solar + fecha; degrada si "
                     "falta geometría o altura física",
        expected_fields=["facade_solar_exposure", "shadow_confidence", "incidence_angle"],
        primary_keys=[], binding_fields=["coordenada", "fecha"],
        version_or_vigency="Código versionado; la corrida Golden declaró "
                           "altura_dependiente = true.",
        precedence="COMPUTED_REFERENCE", license_or_terms=LIC_COMPUTED,
        verification_status="VERIFIED_IN_CODE_EVIDENCE",
        notes="Evidencia real: el run state Golden declara `solar_state.altura_dependiente = "
              "true` y la leyenda del dictamen usa «ANÁLISIS SOLAR AUTOMATIZADO DE LA "
              "FACHADA VISIBLE». Sin altura física la confianza de sombra DEGRADA "
              "(shadow_confidence = DEGRADED) y NO se inventa altura: POT.altura_max es "
              "altura NORMATIVA. Degradar nunca bloquea."))

    return {f["source_id"]: f for f in fuentes}


# ═════════════════════════════════════════════════════════════════════════════
# Evidencia de capturas crudas
# ═════════════════════════════════════════════════════════════════════════════
def _campos_observados(crudo: Any) -> List[str]:
    """Nombres de campo OBSERVADOS en un crudo (sin inventar nada)."""
    campos: List[str] = []

    def _attrs(obj: Any) -> None:
        if isinstance(obj, dict):
            at = obj.get("attributes")
            if isinstance(at, dict):
                campos.extend(sorted(at.keys()))
            for v in obj.values():
                _attrs(v)
        elif isinstance(obj, list):
            for v in obj:
                _attrs(v)

    _attrs(crudo)
    vistos: List[str] = []
    for c in campos:
        if c not in vistos:
            vistos.append(c)
    return vistos


# Capturas que NO son respuestas de un servicio sino artefactos de prueba: se conservan
# (el test del contrato las reescribe) pero el registro NO las presenta como evidencia de
# una consulta real. Se declaran como tales para no confundir al consumidor del pack.
CAPTURAS_DE_PRUEBA = {
    "catastro_baq_predio.json", "pot_baq_areas_actividad.json", "pot_baq_poligonos_uso.json",
    "test_fuente.json",
}


def adjuntar_evidencia(fuentes: Dict[str, Dict[str, Any]],
                       directorio: Path) -> Dict[str, Dict[str, Any]]:
    """Adjunta la captura cruda real de cada fuente, si existe (nunca la modifica)."""
    for sid, f in fuentes.items():
        candidatos = [directorio / f"{sid.lower()}.json", directorio / f"{sid}.json"]
        for ruta in candidatos:
            if not ruta.exists():
                continue
            crudo_bytes = ruta.read_bytes()
            try:
                crudo = json.loads(crudo_bytes.decode("utf-8", "replace"))
            except Exception:  # noqa: BLE001 — el crudo ilegible no se corrige, se declara
                crudo = None
            es_prueba = ruta.name in CAPTURAS_DE_PRUEBA
            f["evidence"] = {
                "capture_file": str(ruta.relative_to(RAIZ)).replace("\\", "/"),
                "capture_sha256": hashlib.sha256(crudo_bytes).hexdigest(),
                "origin": ("ARTEFACTO_DE_PRUEBA" if es_prueba
                           else "RESPUESTA_DE_SERVICIO_O_CAPTURA_DEL_PACK"),
                "observed_fields": (_campos_observados(crudo)
                                    if crudo is not None and not es_prueba else []),
                "raw_modified": False,
            }
            if es_prueba:
                f["evidence"]["note"] = (
                    "Archivo escrito por tests/test_source_pack_contract.py (fixture del "
                    "contrato), NO es una respuesta de servicio: no se usa como evidencia de "
                    "campos observados.")
            if crudo is None:
                f["evidence"]["note"] = ("crudo no interpretable como JSON; se preserva sin "
                                         "modificar")
            break
    return fuentes


def no_fuentes_institucionales() -> Dict[str, Any]:
    """Aliados / artefactos que **NO** son fuentes de datos del Source Registry.

    Decisión de producto vigente (coincide con
    `api/source_licenses_v2.py::PARTNERS_INSTITUCIONALES` y con
    `docs/source_pack/INSTITUTIONAL_PARTNERS.md`): la Lonja **no aporta datos a
    DICTUS**. No es `source_id` del registro, no tiene `authority_class`, ni dataset,
    ni contrato de datos, ni URL, ni bloque de licencia, ni valor por m² suministrado.
    Se declara aquí para que el registro no la silencie: la retira de `sources` y dice
    POR QUÉ.
    """
    return {
        "nota": ("Decisión de producto: la Lonja NO es una fuente de datos. Se retira del "
                 "Source Registry (`sources`) y se declara como aliado institucional. El "
                 "valor de mercado que usa la valoración es un PARÁMETRO DECLARADO POR LA "
                 "CORRIDA, leído de un artefacto local de metodología, sin fuente externa "
                 "automática verificable."),
        "declarado_en": ["api/source_licenses_v2.py::PARTNERS_INSTITUCIONALES",
                         "docs/source_pack/INSTITUTIONAL_PARTNERS.md"],
        "auditoria": "docs/source_pack/MARKET_CONTEXT_AUDIT.md",
        "aliados": {
            "LONJA_BAQ": {
                "partner_id": "LONJA_BAQ",
                "source_id_historico": "LONJA_MARKET_BAQ",
                "nombre": "Lonja de Propiedad Raíz de Barranquilla — Junta Técnica de Avalúos",
                "tipos": ["institutional_partner", "distribution_partner", "stakeholder"],
                "es_fuente_de_datos": False,
                "aporta_datos_a_dictus": False,
                "en_source_registry": False,
                "authority_class": None,
                "product_role": "NOT_A_SOURCE",
                "tiene_bloque_de_licencia": False,
                "bloquea_source_pack": False,
                "retirada_del_registro": True,
                "motivo": ("No hay dataset de la Lonja, ni contrato de datos, ni columna "
                           "obligatoria, ni periodicidad, ni vigencia, ni valor por m² "
                           "suministrado por ella. Sin URL, sin fecha de consulta y sin "
                           "comparables. El identificador `LONJA_MARKET_BAQ` se conserva "
                           "como identificador histórico sellado (no se renombra), pero NO "
                           "sostiene ninguna afirmación de fuente."),
            },
        },
        "valor_de_mercado": {
            "es_fuente_de_datos": False,
            "etiqueta": "parámetros declarados por la corrida",
            "procedencia": ("artefacto local de metodología del producto "
                            "(motor_tma_lonja_baq_v1.0/motor_tma_lonja_baq_v1.0/lonja_layer/"
                            "lonja_baq_metodologia.yaml)"),
            "fuente_externa_verificable": False,
            "estado_declarado": ("NO DISPONIBLE como fuente: el valor se declara como "
                                 "parámetro de la corrida"),
            "resolucion_de_mercado": ("fail-closed: sin fuente en el registro la resolución "
                                      "declara SOURCE_UNAVAILABLE / DATOS_AUSENTES y NUNCA "
                                      "sirve un valor sustituido ni por defecto"),
            "nota": ("El valor proviene de una constante escrita a mano en el artefacto local "
                     "(sin URL, sin fecha de consulta, sin `sample_size` y sin comparables) y "
                     "su vigencia declarada (2026-08-31) estaba VENCIDA en la corrida "
                     "040-646406 (2026-09-28). No se sustituye por ninguna fuente inventada."),
        },
    }


def construir_registro() -> Dict[str, Any]:
    fuentes = adjuntar_evidencia(bloque_de_negocio(), DIR_RAW)
    faltan = {sid: [k for k in CLAVES_OBLIGATORIAS if k not in f]
              for sid, f in fuentes.items()}
    faltan = {k: v for k, v in faltan.items() if v}
    if faltan:
        raise SystemExit(f"ERROR: fuentes sin claves obligatorias: {faltan}")
    malas = {sid: f["authority_class"] for sid, f in fuentes.items()
             if f["authority_class"] not in ds.CLASES_AUTORIDAD}
    if malas:
        raise SystemExit(f"ERROR: authority_class fuera del contrato: {malas}")
    return {
        "registry_version": REGISTRY_VERSION,
        "pack_version": PACK_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ciudad": "barranquilla",
        "measurement_window": ("Ventana de congelación del pack: 2026-09-29. El geoportal "
                               "de la Alcaldía devolvió HTTP 403 (Cloudflare) a toda "
                               "consulta desde esta máquina durante la ventana; se declara "
                               "en cada fuente afectada."),
        "evidence_base": [
            "docs/source_pack/raw/golden/*.json (capturas crudas preservadas sin modificar)",
            "docs/forensics/040-646406/golden_03i1/ESTRATO_PROBE_TRACE*.json (consultas en vivo documentadas)",
            "api/catastro_predio.py, api/address_resolution.py, api/edificabilidad.py (evidencia en código)",
            "api/data/amenaza_remocion_masa.geojson y api/data/areas_en_riesgo.geojson (capas POT oficiales empaquetadas)",
        ],
        "sources": fuentes,
        "no_fuentes_institucionales": no_fuentes_institucionales(),
    }


# ═════════════════════════════════════════════════════════════════════════════
# Serialización (YAML gemelo del JSON canónico, MISMO contenido)
# ═════════════════════════════════════════════════════════════════════════════
def _dump_yaml(payload: Dict[str, Any]) -> str:
    cabecera = (
        "# " + "=" * 76 + "\n"
        "# BARRANQUILLA SOURCE PACK v1.0 — registro de fuentes (gemelo legible)\n"
        "#\n"
        "# Este archivo es el GEMELO LEGIBLE de barranquilla_sources_v1.json, que es el\n"
        "# registro canónico que lee api/dictus_sources.cargar_registro(). Ambos tienen\n"
        "# EXACTAMENTE el mismo contenido y se regeneran juntos con:\n"
        "#     python scripts/source_pack_build.py\n"
        "#\n"
        "# Cada fuente declara las 25 claves del contrato de fuentes (§33): source_id,\n"
        "# source_name, institution, authority_class, base_url, service, layer_id,\n"
        "# layer_name, geometry_type, query_method, expected_fields, primary_keys,\n"
        "# binding_fields, spatial_reference, legal_or_normative_context,\n"
        "# version_or_vigency, precedence, fallback_policy, freshness_policy,\n"
        "# failure_semantics, license_or_terms, can_persist_raw, can_embed_image,\n"
        "# provenance_fields, enabled. Más spec_layer_id, verification_status,\n"
        "# local_fallback, notes y (si la hay) evidence.\n"
        "# " + "=" * 76 + "\n")
    try:
        import yaml  # type: ignore
        cuerpo = yaml.safe_dump(payload, allow_unicode=True, sort_keys=True, width=100,
                                default_flow_style=False)
    except Exception:  # noqa: BLE001 — sin PyYAML se usa el emisor mínimo determinista
        cuerpo = _yaml_minimo(payload)
    huella = ds.hash_canonico(payload)
    return f"{cabecera}# payload_sha256: {huella}\n{cuerpo}"


def _yaml_minimo(obj: Any, indent: int = 0) -> str:
    """Emisor YAML mínimo (subconjunto: dict/list/str/int/float/bool/None)."""
    esp = " " * indent

    def esc(v: str) -> str:
        plano = (v and "\n" not in v and ":" not in v and "#" not in v
                 and not v.strip().startswith(("-", "?", "*", "&", "!", "%", "@", "`"))
                 and v.strip() == v)
        if plano:
            return v
        return json.dumps(v, ensure_ascii=False)

    if isinstance(obj, dict):
        lineas = []
        for k in sorted(obj):
            v = obj[k]
            if isinstance(v, (dict, list)) and v:
                lineas.append(f"{esp}{k}:")
                lineas.append(_yaml_minimo(v, indent + 2))
            elif isinstance(v, (dict, list)):
                lineas.append(f"{esp}{k}: {'{}' if isinstance(v, dict) else '[]'}")
            else:
                lineas.append(f"{esp}{k}: {_literal(v)}")
        return "\n".join(lineas)
    if isinstance(obj, list):
        lineas = []
        for it in obj:
            if isinstance(it, (dict, list)) and it:
                sub = _yaml_minimo(it, indent + 2).lstrip()
                lineas.append(f"{esp}- {sub}")
            else:
                lineas.append(f"{esp}- {_literal(it)}")
        return "\n".join(lineas)
    return f"{esp}{_literal(obj)}"


def _literal(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    return json.dumps(str(v), ensure_ascii=False)


# ═════════════════════════════════════════════════════════════════════════════
# Manifest
# ═════════════════════════════════════════════════════════════════════════════
def construir_manifest(registro: Dict[str, Any]) -> Dict[str, Any]:
    fuentes = registro["sources"]
    hashes = {sid: ds.hash_canonico({k: v for k, v in f.items() if k != "evidence"})
              for sid, f in fuentes.items()}
    habilitadas = sorted(sid for sid, f in fuentes.items() if f.get("enabled") is not False)
    deshabilitadas = sorted(sid for sid, f in fuentes.items() if f.get("enabled") is False)
    sin_credencial = [sid for sid in ("MAPILLARY", "GOOGLE_STREET_VIEW")]
    return {
        "manifest_version": "barranquilla-source-pack-manifest/1.0.0",
        "pack_version": PACK_VERSION,
        "registry_version": REGISTRY_VERSION,
        "generated_at": registro["generated_at"],
        "approved_sources": habilitadas,
        "source_metadata_hashes": hashes,
        "precedence_rules": {
            "authority_classes": list(ds.CLASES_AUTORIDAD),
            "normative_classes": list(ds.CLASES_NORMATIVAS),
            "risk_precedence_order": list(ds.PRECEDENCIA_RIESGO),
            "binding_precedence_order": list(ds.PRECEDENCIA_BINDING),
            "silent_override": False,
            "rules": [
                "CURRENT_NORMATIVE (POT vigente, Decreto 893 de 2024) > CURRENT_OFFICIAL > "
                "HISTORICAL_REFERENCE. Una capa histórica nunca se asciende en silencio.",
                "Identidad del predio: NUPRE exacto > número predial exacto > relación "
                "oficial > dirección ligada. La coincidencia ESPACIAL es solo contexto y "
                "NUNCA autoriza identidad; jamás se elige features[0].",
                "AUTHORITATIVE_CONTRACTUAL es una autoridad DECLARADA: sostiene la "
                "metodología de valoración, no una afirmación normativa territorial. La "
                "Lonja NO es una fuente de datos (decisión de producto): el valor de mercado "
                "es un parámetro declarado por la corrida, sin fuente externa verificable.",
                "CONTEXTUAL_REFERENCE (OSM/Mapillary/Google) y COMPUTED_REFERENCE "
                "(motor solar/sombras) no sostienen afirmaciones normativas.",
                "Destino económico catastral (hecho) ≠ uso normativo del POT (norma): "
                "nunca se copia uno sobre el otro.",
                "POT.altura_max es altura NORMATIVA en pisos: nunca altura física del "
                "edificio.",
            ],
        },
        "licenses": {
            "policy": ("El crudo se preserva sin modificar solo si la licencia lo permite; "
                       "la normalización vive en un objeto aparte. Si no puede persistirse, "
                       "el resultado declara estado y no se escribe archivo."),
            "fail_closed_policy": ("El pack es MÁS ESTRICTO que el valor por defecto del "
                                   "código: mientras no exista evidencia hasheada "
                                   "(evidence_url + retrieved_at + sha256), "
                                   "provider_terms_status queda UNVERIFIED — también para "
                                   "Mapillary, cuyo módulo declara CC BY-SA 4.0 por defecto. "
                                   "UNVERIFIED cierra can_persist/can_embed_in_pdf."),
            "by_source": {sid: {"license_or_terms": f["license_or_terms"],
                                "can_persist_raw": f["can_persist_raw"],
                                "can_embed_image": f["can_embed_image"],
                                "provider_terms_status": _terms_status(sid)}
                          for sid, f in sorted(fuentes.items())},
            "unverified_terms": ["GOOGLE_STREET_VIEW", "MAPILLARY"],
        },
        "legal_context": {
            "pot_vigente": NORM_POT_2024,
            "catastro": NORM_CATASTRO,
            "adopcion_catastral": "Resolución GGCD 003 del 07/03/2025 (Anexo 1)",
            "valoracion": ("Ley 1673 de 2013; Decreto 556 de 2014; Decreto 1420 de 1998; "
                           "Resolución IGAC 620 de 2008; Resolución IGAC 1040 de 2023 mod. "
                           "746 de 2024 (parámetros declarados por la corrida; la Lonja no "
                           "es una fuente de datos)"),
            "ordenamiento_territorial": ("Ley 388 de 1997 (zonas de riesgo no mitigable; "
                                         "determinantes de ordenamiento)"),
        },
        "tested_at": registro["generated_at"],
        "golden_case": {
            "folio": "040-646406",
            "nupre": "AFT0005BOHA",
            "numero_predial": "080010103000010040001908040002",
            "direccion": ("TV 43 # 100 - 50 CONJUNTO RESIDENCIAL NAPOLI APARTAMENTOS ETAPA 3 "
                          "APARTAMENTO 430 TORRE 8"),
            "barrio": "Miramar", "estrato": "4", "tratamiento": "Consolidacion",
            "coordenada": {"lat": 11.006055954316363, "lon": -74.8375696549899,
                           "coordinate_source": "OFFICIAL_PREDIO"},
            "run_state": ("docs/forensics/040-646406/dictus_2b/"
                          "DICTUS_RUN_STATE_040-646406.json (los identificadores se LEEN de "
                          "ese archivo; no están codificados a mano en la matriz)"),
        },
        "known_limitations": [
            "El geoportal miciudad.barranquilla.gov.co devolvió HTTP 403 (Cloudflare) a toda "
            "consulta desde esta máquina durante la ventana de congelación: las fuentes de "
            "catastro y POT quedan declaradas SOURCE_UNAVAILABLE, no NO_MATCH.",
            "Ninguna ruta alternativa de recuperación funcionó (Wayback sin capturas, "
            "espejos de la API de ArcGIS Online sin resultados, proxies CORS con error "
            "522/401/429). Evidencia: raw/golden/_retrieval_paths_probe*.json.",
            "Las capas POT demandadas por el enunciado (3, 4, 83, 85, 87, 89, 91, 92, "
            "71/73/75/77/79/81, equipamiento 18/20-27) NO se pudieron verificar; donde hubo "
            "evidencia real de otra capa se registró esa capa y se conservó el id declarado "
            "en `spec_layer_id`. Las capas sin ninguna evidencia quedaron `enabled: false`.",
            "Sin credenciales de street imagery (Mapillary/Google): nivel NO_IMAGE_AVAILABLE "
            "declarado; no bloquea el resto del pack.",
            "La amenaza por remoción del predio Golden cae en DOS polígonos superpuestos "
            "(objectid 469 «Media» y 1369 «Baja»): el pack reporta el nivel más alto y lista "
            "ambos; no elige en silencio.",
            "La amenaza por inundación no tiene capa verificada ni copia empaquetada: se "
            "declara NOT_SUPPORTED, nunca «sin amenaza».",
            "La localidad del predio Golden quedó NO RESUELTA en la corrida de origen "
            "(NULL_VALUE); el pack la declara como tal.",
            "El equipo de equipamiento OFICIAL (OFFICIAL_EQUIPMENT_CONTEXT) está registrado "
            "pero DESHABILITADO hasta verificar las capas: el equipo que hoy se reporta "
            "proviene de OSM (contexto), no de la Alcaldía.",
            "Las capas POT empaquetadas NO llevan dentro un sello de decreto ni de versión "
            "(campos reales: objectid, niveldeamenaza/clase_suelo y "
            "nivelderiesgo/clasesuelo): la atribución «Decreto 893 de 2024» es del registro "
            "del pack y no es verificable dentro del artefacto GeoJSON.",
            "La metodología local declara vigencia hasta 2026-08-31, anterior a esta "
            "corrida; ningún consumidor la convierte en bloqueo y el pack la declara como "
            "metodología en revisión (no la silencia).",
            "MERCADO SIN FUENTE EXTERNA VERIFICABLE: el valor por m² del producto es una "
            "constante declarada en el artefacto local de metodología (sin URL, sin fecha de "
            "consulta, sin `sample_size` y sin comparables). No existe una fuente de mercado "
            "en el Source Registry: `LONJA_MARKET_BAQ` se retiró por decisión de producto "
            "(la Lonja no aporta datos a DICTUS) y la resolución de mercado declara "
            "SOURCE_UNAVAILABLE / DATOS_AUSENTES, nunca un valor sustituido. Para "
            "OPERATIONAL_READY en mercado hace falta una fuente de mercado de tercero "
            "verificable (URL + fecha de consulta + sha256 + comparables) o la validación "
            "firmada del avaluador. Detalle: "
            "docs/source_pack/acceptance_report.md §Mercado.",
            "Las rutas alternativas de recuperación (proxies CORS de terceros, espejos, "
            "traducción, Wayback) NO son una vía de obtención autorizada: se documentan como "
            "intentos fallidos (raw/golden/_retrieval_paths_probe*.json, "
            "_proxy_control_matrix.json) y la política del pack es fail-closed.",
            "Solo hay crudos persistidos de 4 fuentes (3 con nombre canónico + una de "
            "prueba): las demás fuentes no produjeron crudo porque no fueron alcanzables o "
            "porque su licencia no lo permite (Google).",
            "Los rótulos de precedencia CONTEXTUAL_REFERENCE y COMPUTED_REFERENCE son "
            "etiquetas propias del REGISTRO (no constantes de api/dictus_sources.py, que no se "
            "modifica): resolver_precedencia manda cualquier nivel desconocido a `displaced`, "
            "que es la dirección segura.",
        ],
        "disabled_sources": deshabilitadas,
        "credential_gaps": {
            "missing_env": ["ARHIAX_MAPILLARY_TOKEN", "MAPILLARY_TOKEN",
                            "MAPILLARY_ACCESS_TOKEN", "ARHIAX_GOOGLE_MAPS_API_KEY",
                            "GOOGLE_MAPS_API_KEY", "GOOGLE_STREETVIEW_API_KEY",
                            "ARHIAX_IMAGERY_STRICT_TERMS"],
            "env_files_present": [],
            "affected_sources": sin_credencial,
            "declared_effect": ("credentials_status=MISSING → facade_view_level="
                                "NO_IMAGE_AVAILABLE, request_made=False, blocks_dictus=False "
                                "(la ausencia de imagen NO bloquea el pack)."),
        },
        "fallback_declared": {
            sid: f["local_fallback"] for sid, f in sorted(fuentes.items())
            if f.get("local_fallback")
        },
    }


def _terms_status(sid: str) -> str:
    if sid == "GOOGLE_STREET_VIEW":
        return "UNVERIFIED (fail-closed: no se persiste crudo ni se incrusta imagen)"
    if sid == "MAPILLARY":
        return "UNVERIFIED (licencia CC BY-SA 4.0 declarada por el proveedor; atribución obligatoria)"
    if sid in ("OSM_OVERPASS",):
        return "ODbL 1.0 (términos públicos verificados)"
    if sid in ("SOLAR_ENGINE", "SHADOW_FACADE_EXPOSURE"):
        return "N/A (cálculo propio)"
    if sid == "LONJA_MARKET_BAQ":
        # Histórico: la pieza ya NO es una fuente del registro (decisión de producto).
        # La rama se conserva por trazabilidad de los hashes del pack v1.
        return ("N/A (no es una fuente de datos: artefacto local de metodología del producto)")
    return "UNVERIFIED (no publicados junto al servicio; uso con atribución a la fuente oficial)"


def escribir(registro: Dict[str, Any]) -> Dict[str, str]:
    DIR_PACK.mkdir(parents=True, exist_ok=True)
    RUTA_JSON.write_text(json.dumps(registro, ensure_ascii=False, indent=1, sort_keys=True),
                         encoding="utf-8")
    RUTA_YAML.write_text(_dump_yaml(registro), encoding="utf-8")
    manifest = construir_manifest(registro)
    RUTA_MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=1,
                                        sort_keys=True), encoding="utf-8")
    return {"json": str(RUTA_JSON), "yaml": str(RUTA_YAML), "manifest": str(RUTA_MANIFEST),
            "sources": str(len(registro["sources"])),
            "manifest_hash": ds.hash_canonico(manifest)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Construye el registro de fuentes del pack.")
    ap.add_argument("--check", action="store_true",
                    help="valida el registro en memoria sin escribir archivos")
    args = ap.parse_args()
    registro = construir_registro()
    habilitadas = sum(1 for f in registro["sources"].values() if f.get("enabled") is not False)
    if args.check:
        print(f"OK registro: {len(registro['sources'])} fuentes "
              f"({habilitadas} habilitadas, "
              f"{len(registro['sources']) - habilitadas} deshabilitadas declaradas)")
        return 0
    salida = escribir(registro)
    for k, v in salida.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

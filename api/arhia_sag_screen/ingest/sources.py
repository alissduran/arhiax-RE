"""Catálogo de fuentes del subsistema de screening (LEGADO, 03S.1).

AVISO 03S.1 — este catálogo NO es la autoridad de fuentes vigentes. La autoridad
es `sanctions.registry` (SourceRegistry), que declara:

  * UN_CONSOLIDATED   — ONU, lista consolidada del Consejo de Seguridad (CURRENT)
  * OFAC_SDN          — OFAC Sanctions List Service, SDN (CURRENT)
  * UK_SANCTIONS_LIST — UK Sanctions List FCDO (CURRENT)  ← migración 03S.1
  * UK_OFSI_CONLIST_HISTORICAL — ConList.xml (HISTORICAL, solo reproducibilidad)
  * UIAF_SIREL        — REGULATORY_REPORTING, FUERA del screening
  * EU_CONSOLIDATED   — OPCIONAL / OFFICIAL_FILE_REQUIRED

Aislamiento de datos de demostración (§12 del prompt 03S.1): los registros
sintéticos de las listas de prueba YA NO viven en el módulo productivo; se
movieron a `tests/fixtures/screening/muestras_sinteticas.json`.
Este módulo no contiene ningún registro de lista: solo metadatos de catálogo.
Regla: SYNTHETIC_TEST_FIXTURE != SCREENING EVIDENCE.
"""

ONU_XML = "https://scsanctions.un.org/resources/xml/en/consolidated.xml"
# OFAC Sanctions List Service (endpoint oficial vigente de exportación SDN).
OFAC_XML = "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.XML"
# UK: fuente vigente (UK Sanctions List, FCDO). El antiguo ConList.xml de OFSI
# queda como HISTORICAL_SOURCE para reproducibilidad de dictámenes históricos.
UK_XML = "https://sanctionslist.fcdo.gov.uk/docs/UK-Sanctions-List.xml"
UK_OFSI_LEGACY_XML = ("https://ofsistorage.blob.core.windows.net/publishlive/"
                      "2022format/ConList.xml")

# `politica`:
#   "live"    -> descarga del feed oficial (ONU, OFAC, UK).
#   "fichero" -> ingesta del archivo oficial (UE); el portal bloquea la descarga.
#   "fuera_de_alcance" -> NO es fuente de screening (UIAF/SIREL, PEP).
FUENTES = {
    "onu": {
        "nombre": "ONU — Security Council Consolidated List",
        "url": ONU_XML, "formato": "xml", "parser": "onu", "politica": "live",
        "categoria": "SANCTIONS_LIST", "source_id": "UN_CONSOLIDATED",
        "descripcion": "Lista consolidada del Consejo de Seguridad de la ONU (personas y entidades).",
    },
    "ofac": {
        "nombre": "OFAC — Specially Designated Nationals (SDN)",
        "url": OFAC_XML, "formato": "xml", "parser": "ofac", "politica": "live",
        "categoria": "SANCTIONS_LIST", "source_id": "OFAC_SDN",
        "descripcion": "Sanciones de EE.UU. (SDN) — OFAC Sanctions List Service. Solo SDN: "
                       "no cubre las listas no-SDN consolidadas.",
    },
    "uk": {
        "nombre": "UK — UK Sanctions List (FCDO/OFSI)",
        "url": UK_XML, "formato": "xml", "parser": "uk_sanctions_list",
        "politica": "live", "categoria": "SANCTIONS_LIST",
        "source_id": "UK_SANCTIONS_LIST",
        "descripcion": "Lista única de sanciones del Reino Unido. Sustituye al consolidated "
                       "list del Tesoro (ConList.xml), que queda como fuente histórica.",
    },
    "ue": {
        "nombre": "UE — Consolidated Sanctions List (DG FISMA / FSF, XML 1.1)",
        "url": "https://webgate.ec.europa.eu/fsd/fsf/public/files/xmlFullSanctionsList_1_1/content",
        "url_mirror": "https://sankcijas.fid.gov.lv/files/xmlFullSanctionsList_1_1.xml",
        "formato": "xml", "parser": "ue", "politica": "fichero",
        "categoria": "SANCTIONS_LIST", "source_id": "EU_CONSOLIDATED",
        "origin": "EU_DG_FISMA", "channel": "OFFICIAL_CRAWLER_OR_INSTITUTIONAL_MIRROR",
        "authority": "INSTITUTIONAL",
        "descripcion": "OPCIONAL en 03S.1 (OFFICIAL_FILE_REQUIRED): se ingesta el XML oficial "
                       "con `ingestar_fichero('ue', ruta.xml)` y se versiona.",
    },
    "uiaf": {
        "nombre": "UIAF — canal de reporte regulatorio (SIREL)",
        "url": "", "formato": "", "parser": "none", "politica": "fuera_de_alcance",
        "categoria": "REGULATORY_REPORTING", "source_id": "UIAF_SIREL",
        "descripcion": "UIAF/SIREL NO es una lista de screening: es el canal de reporte del "
                       "sujeto obligado. Fuera de alcance en 03S.1 (03S.x Regulatory Reporting).",
    },
    "uk_ofsi_legacy": {
        "nombre": "UK — OFSI Consolidated List (ConList.xml) — HISTÓRICO",
        "url": UK_OFSI_LEGACY_XML, "formato": "xml", "parser": "uk",
        "politica": "fuera_de_alcance", "categoria": "SANCTIONS_LIST",
        "source_id": "UK_OFSI_CONLIST_HISTORICAL",
        "descripcion": "HISTORICAL_SOURCE: solo para reproducir dictámenes históricos. "
                       "PROHIBIDO como fuente vigente de UK.",
    },
    "pep": {
        "nombre": "PEP — Personas Expuestas Políticamente (Colombia)",
        "url": "", "formato": "", "parser": "none", "politica": "fuera_de_alcance",
        "categoria": "PEP_REGISTRY", "source_id": "PEP_COLOMBIA",
        "descripcion": "PEP avanzado fuera de 03S.1: se declara, no se simula.",
    },
}


def lista_de_fuentes():
    return list(FUENTES)


def fuentes_de_screening():
    """Claves de fuentes que SÍ cuentan como evidencia de screening."""
    return [k for k, v in FUENTES.items()
            if v.get("categoria") == "SANCTIONS_LIST"
            and v.get("politica") in ("live", "fichero")]

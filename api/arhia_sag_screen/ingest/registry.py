"""Catálogo de listas sancionatorias y sus fuentes oficiales."""
LIST_CATALOG = {
    "onu": {
        "fuente": "onu",
        "nombre": "Security Council Consolidated List",
        "url": "https://scsanctions.un.org/resources/xml/en/consolidated.xml",
        "formato": "xml",
        "licencia": "public",
        "programacion": "semanal",
    },
    "ofac-sdn": {
        "fuente": "ofac",
        "nombre": "Specially Designated Nationals (SDN)",
        "url": "https://www.treasury.gov/ofac/downloads/sdn.xml",
        "formato": "xml",
        "licencia": "public",
        "programacion": "diaria",
    },
}

"""Catálogo multifuente de listas para el screening SARLAFT/SAGRILAFT+PTEE.

La circular (Cap. IX) exige consultar **listas vinculantes**. ONU y OFAC son el baseline
internacional; el set completo incluye UIAF (lista cautelar/vinculante colombiana), UE, Reino
Unido (HMT/OFSI), PEP (servidores públicos) e Interpol.

`politica` indica cómo se obtiene la fuente:
  - "live"   -> se intenta descargar y parsear el feed oficial (ONU, OFAC).
  - "muestra"-> no hay feed limpio/publico fiable (UIAF, UE, UK, PEP, Interpol); se usa una
               muestra determinista versionada, documentando que el conector oficial es aparte.
Cada fuente aporta una `muestra` (RegistroNormalizado) para que el screening sea completo y
versionado aunque la fuente no sea consumible en vivo.
"""
from ..contracts import RegistroNormalizado

ONU_XML = "https://scsanctions.un.org/resources/xml/en/consolidated.xml"
OFAC_XML = "https://www.treasury.gov/ofac/downloads/sdn.xml"
UK_XML = "https://ofsistorage.blob.core.windows.net/publishlive/2022format/ConList.xml"


def _r(id, nombre, alias=(), tid=None, num=None, fuente="", version=""):
    return RegistroNormalizado(id=id, nombre=nombre, alias=alias, tipo_documento=tid,
                               numero_documento=num, fuente=fuente, lista_version=version)


FUENTES = {
    "onu": {
        "nombre": "ONU — Security Council Consolidated List",
        "url": ONU_XML, "formato": "xml", "parser": "onu", "politica": "live",
        "descripcion": "Lista consolidada del Consejo de Seguridad de la ONU (personal y entidades).",
        "muestra": (),
    },
    "ofac": {
        "nombre": "OFAC — Specially Designated Nationals (SDN)",
        "url": OFAC_XML, "formato": "xml", "parser": "ofac", "politica": "live",
        "descripcion": "Sanciones de EE.UU. (SDN) — OFAC.",
        "muestra": (),
    },
    "uiaf": {
        "nombre": "UIAF — Lista vinculante / cautelar (Colombia)",
        "url": "", "formato": "csv", "parser": "generic", "politica": "muestra",
        "descripcion": "Lista cautelar/vinculante difundida por la UIAF. En producción se integra por "
                       "el canal oficial (usuario autorizado); aquí se usa una muestra determinista.",
        "muestra": (_r("uiaf-001", "JORGE ALIRIO GONZALEZ", ("J. GONZALEZ",), "cc", "98520011", "uiaf"),
                    _r("uiaf-002", "FACTORIA PACIFICO SAS", ("FACTORIA PACIFICO",), "nit", "800999887", "uiaf")),
    },
    "ue": {
        "nombre": "UE — Consolidated Sanctions List (DG FISMA / FSF, XML 1.1)",
        "url": "https://webgate.ec.europa.eu/fsd/fsf/public/files/xmlFullSanctionsList_1_1/content",
        "url_mirror": "https://sankcijas.fid.gov.lv/files/xmlFullSanctionsList_1_1.xml",
        "formato": "xml", "parser": "ue", "politica": "fichero",
        "origin": "EU_DG_FISMA", "channel": "OFFICIAL_CRAWLER_OR_INSTITUTIONAL_MIRROR", "authority": "INSTITUTIONAL",
        "descripcion": "Lista consolidada de sanciones de la UE (DG FISMA/FSF, XML 1.1). webgate bloquea "
                       "el acceso automatizado (403 anti-bot) y el mirror devuelve HTML; por eso se "
                       "**ingesta el XML** (vía crawler oficial de FSF / mirror / carga manual) con "
                       "`ingestar_fichero('ue', ruta.xml)` y se versiona/cachea.",
        "muestra": (_r("ue-001", "PETROLEOS NORTE S.L.", (), "nit", "B12345678", "ue"),
                    _r("ue-002", "VIKTOR KRUPIN", (), "pasaporte", "TR1234567", "ue")),
    },
    "uk": {
        "nombre": "UK — OFSI / HMT Sanctions List",
        "url": UK_XML, "formato": "xml", "parser": "uk", "politica": "live",
        "descripcion": "Lista de sanciones financieras del Reino Unido (OFSI/HMT). XML grande (~54 MB) "
                       "parseado por streaming; se cachea versionado.",
        "muestra": (_r("uk-001", "MARIANO KOVAC", ("MARIAN KOVAC",), "pasaporte", "UK7654321", "uk"),
                    _r("uk-002", "CARBON MINING LTD", (), "nit", "GB99887766", "uk")),
    },
    "pep": {
        "nombre": "PEP — Personas Expuestas Políticamente (Colombia)",
        "url": "", "formato": "csv", "parser": "generic", "politica": "muestra",
        "descripcion": "Servidores públicos / PEP (Procuraduría, Contraloría, registros oficiales). "
                       "En producción se alimenta del registro de servidores públicos.",
        "muestra": (_r("pep-001", "RODRIGO CASTRO RAMOS", ("R. CASTRO",), "cc", "72110033", "pep"),
                    _r("pep-002", "MARTA LUCIA VALENCIA", (), "cc", "43009988", "pep")),
    },
    "interpol": {
        "nombre": "Interpol — Red Notices",
        "url": "", "formato": "xml", "parser": "generic", "politica": "muestra",
        "descripcion": "Notificaciones rojas de Interpol (LA/FT, terrorismo).",
        "muestra": (_r("int-001", "ALEXEI SMIRNOV", (), "pasaporte", "IN554433", "interpol"),
                    _r("int-002", "LA UNION CARTEL", ("UNION CARTEL",), "nit", "IN110099", "interpol")),
    },
}


def lista_de_fuentes():
    return list(FUENTES)

"""Pipeline de ingesta: descarga -> hash -> version -> detección de cambio."""
from dataclasses import dataclass

from ..contracts import ListaVersion
from ..evidence.versioning import sha256_hex


@dataclass(frozen=True)
class ResultadoIngesta:
    lista: ListaVersion
    hubo_cambio: bool


def ingerir(catalogo_entry, fetch, version_anterior=None):
    """Descarga una fuente y la versiona por hash.

    catalogo_entry: dict del registry (fuente, nombre, url, formato, licencia).
    fetch: callable(url) -> bytes (permite inyección para tests offline).
    version_anterior: hash previo (str | None). Devuelve (ListaVersion, hubo_cambio).
    """
    raw = fetch(catalogo_entry["url"])
    h = sha256_hex(raw)
    lista = ListaVersion(
        fuente=catalogo_entry["fuente"],
        nombre=catalogo_entry["nombre"],
        url=catalogo_entry["url"],
        formato=catalogo_entry["formato"],
        fecha_emision="",
        version=h[:16],
        hash=h,
        licencia=catalogo_entry.get("licencia", "public"),
    )
    hubo_cambio = (version_anterior is None) or (version_anterior != h)
    return ResultadoIngesta(lista=lista, hubo_cambio=hubo_cambio)

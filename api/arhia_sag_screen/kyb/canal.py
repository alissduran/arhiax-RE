"""Canal de denuncias (PTEE / SAGRILAFT) — recepción y estado de una denuncia.

Modela el canal interno de recepción de denuncias anónimas (requisito del PTEE y del
SAGRILAFT). En producción se enlaza con una herramienta externa que garantiza anonimato;
aquí se modela la recepción, clasificación y trazabilidad de la denuncia.
"""
import datetime
from dataclasses import dataclass, field
from typing import Optional, Tuple

ESTADOS_CANAL = ("RECIBIDA", "EN_ANALISIS", "DERIVADA", "EN_TRAMITE", "CERRADA")
CATEGORIAS = ("corrupcion", "soborno", "laft", "conflicto_interes", "otro")


@dataclass(frozen=True)
class Denuncia:
    id: str
    categoria: str
    descripcion: str
    fecha: str
    anonima: bool = True
    canal: str = "interno"
    estado: str = "RECIBIDA"
    seguimiento: Tuple[str, ...] = ()


def registrar_denuncia(id, categoria, descripcion, *, fecha="", anonima=True, canal="interno"):
    """Registra una denuncia anónima y devuelve la Denuncia. La fecha por defecto es ahora."""
    fecha = fecha or datetime.datetime.now(datetime.timezone.utc).isoformat()
    return Denuncia(id=id, categoria=categoria, descripcion=descripcion, fecha=fecha,
                    anonima=anonima, canal=canal, estado="RECIBIDA")


def avanzar(denuncia, nuevo_estado, nota=""):
    """Avanza el estado de una denuncia (valida la cadena)."""
    if denuncia.estado == "CERRADA":
        return denuncia
    return Denuncia(id=denuncia.id, categoria=denuncia.categoria, descripcion=denuncia.descripcion,
                    fecha=denuncia.fecha, anonima=denuncia.anonima, canal=denuncia.canal,
                    estado=nuevo_estado,
                    seguimiento=denuncia.seguimiento + ((nota or nuevo_estado),))

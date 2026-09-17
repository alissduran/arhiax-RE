"""Contratos del dominio de títulos (pre-dictamen jurídico-inmobiliario)."""
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class Evidencia:
    id: str
    documento: str
    fragmento: str = ""


@dataclass(frozen=True)
class Anotacion:
    numero: int
    tipo: str           # compraventa | hipoteca | embargo | medida_cautelar | gravamen | cancelacion | limitacion | afectacion | aclaracion | otro
    fecha: str          # ISO
    instrumento: str = ""
    titular: str = ""   # adquiriente en compraventa
    detalle: str = ""
    estado: str = "vigente"   # vigente | cancelada


@dataclass(frozen=True)
class Predio:
    folio_matricula: str
    codigo_catastral: str
    direccion: str = ""
    area_registral: float = 0.0
    area_catastral: float = 0.0


@dataclass(frozen=True)
class Parte:
    rol: str
    nombre: str
    tipo_documento: str = ""
    numero_documento: str = ""
    beneficiario_final: str = ""


@dataclass(frozen=True)
class Avaluo:
    valor: float
    metodo: str = ""
    fecha: str = ""
    avaluador: str = ""


@dataclass(frozen=True)
class Pago:
    monto: float
    medio: str = ""
    pagador: str = ""
    es_tercero: bool = False


@dataclass(frozen=True)
class Caso:
    id: str
    tipo: str
    predio: Predio
    partes: Tuple[Parte, ...] = ()
    anotaciones: Tuple[Anotacion, ...] = ()
    avaluo: Optional[Avaluo] = None
    precio_pactado: Optional[float] = None
    pagos: Tuple[Pago, ...] = ()
    titular: str = ""
    amenazas: Tuple[str, ...] = ()
    sarlaft_estado: str = ""


@dataclass(frozen=True)
class Hallazgo:
    id: str
    titulo: str
    estado: str                 # OK | OBSERVACION | RIESGO | INFORMACION_INSUFICIENTE | INCONSISTENTE | REQUIERE_REVISION
    severidad: str              # baja | media | alta | critica
    descripcion: str = ""       # qué es / qué detectó el motor (técnico)
    base_legal: str = ""        # sustento normativo/jurídico
    implicacion: str = ""       # consecuencia operacional/jurídica
    regla: str = ""
    evidencia: Tuple[Evidencia, ...] = ()
    accion: str = ""
    responsable: str = "sistema"   # sistema | abogado | avaluador

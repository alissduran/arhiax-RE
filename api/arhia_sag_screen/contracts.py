"""Contratos de datos del módulo de screening (subsistema SAG, F1b + F2a)."""
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class Contraparte:
    contraparte_id: str
    tipo: str  # "natural" | "juridica"
    nombre: str
    tipo_documento: Optional[str] = None
    numero_documento: Optional[str] = None
    alias: Tuple[str, ...] = ()


@dataclass(frozen=True)
class ListaVersion:
    fuente: str
    nombre: str
    url: str
    formato: str
    fecha_emision: str
    version: str
    hash: str
    licencia: str = "public"
    registros: int = 0
    estado: str = "OPERATIVA"          # OPERATIVA | SYNTHETIC_TEST_FIXTURE | NO_DISPONIBLE
    autoridad: str = ""                # autoridad emisora (ONU/OFAC/UIAF...)
    metodo: str = ""                   # método de obtención
    vigencia: str = ""                 # fecha de vigencia de la fuente


@dataclass(frozen=True)
class RegistroNormalizado:
    id: str
    nombre: str
    alias: Tuple[str, ...] = ()
    tipo_documento: Optional[str] = None
    numero_documento: Optional[str] = None
    fecha_nacimiento: Optional[str] = None
    programas: Tuple[str, ...] = ()
    fuente: str = ""
    lista_version: str = ""


@dataclass(frozen=True)
class ResultadoConsulta:
    contraparte_id: str
    lista: str
    lista_version: str
    lista_hash: str
    resultado: str  # "coincidencia" | "candidato" | "sinCoincidencia" | "revisionManual"
    score: float = 0.0
    matched_fields: Tuple[str, ...] = ()
    coincidencia_id: Optional[str] = None


# ---- Fase 2a: KYB ----

@dataclass(frozen=True)
class Accionista:
    tipo_documento: Optional[str] = None
    numero_documento: Optional[str] = None
    nombre: str = ""
    participacion: float = 0.0


@dataclass(frozen=True)
class RegistroJuridico:
    nit: str
    razon_social: str
    estado: str = ""
    representante_legal: Optional[str] = None
    composicion_accionaria: Tuple[Accionista, ...] = ()
    ingresos: Optional[float] = None
    activos: Optional[float] = None
    sector: str = ""
    vigilada_por: str = ""
    fuente: str = ""
    lista_version: str = ""


@dataclass(frozen=True)
class BeneficiarioFinal:
    tipo_documento: Optional[str] = None
    numero_documento: Optional[str] = None
    nombre: str = ""
    participacion: float = 0.0
    criterio: str = ""  # "participacion" | "control_efectivo" | "representante_legal_subsidiario"
    limitacion: Optional[str] = None
    # Campos del Registro Único de Beneficiarios Finales (RUB)
    pais_residencia: str = ""
    fecha_adquisicion: str = ""
    vinculo: str = ""      # socio | representante_legal | controlante | liquidador
    calidad: str = ""      # directo | indirecto
    base_legal: str = ""   # sustento (C.Com. 260/261; ET 260-1; regla subsidiaria)

"""
TMA — Triangulación Metodológica Asistida
Contrato de datos común — Sinergia Consulting Group

Todas las piezas (M1, M2, M3, Consolidación, Bandeja) respetan estas estructuras.
Esto permite que cada pieza se construya independientemente y se integren sin código a la medida.

Marco normativo: Resolución IGAC 1040 de 2023 (mod. 746/2024)
Métodos reconocidos: Comparación de Mercado, Costo de Reposición, Capitalización de Rentas, Técnica Residual.
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Literal, Optional
import hashlib
import json


def stable_hash(obj) -> str:
    """Hash SHA-256 estable sobre el contenido serializado (orden de claves fijo)."""
    if hasattr(obj, '__dict__'):
        obj = asdict(obj) if hasattr(obj, '__dataclass_fields__') else obj.__dict__
    serialized = json.dumps(obj, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(serialized.encode('utf-8')).hexdigest()


@dataclass
class Insumo:
    """Un insumo individual usado por un método valuatorio (un comparable, una serie de costos, etc.)"""
    fuente: str                    # "Metrocuadrado.com", "Camacol Atlántico Q1-2026", etc.
    url_o_referencia: str          # URL específica o referencia documental
    fecha_captura: str             # ISO 8601
    descripcion: str               # Descripción humana del insumo
    contenido: dict                # Datos estructurados específicos del insumo
    hash_insumo: str = ""          # SHA-256 sobre contenido serializado

    def __post_init__(self):
        if not self.hash_insumo:
            payload = {
                'fuente': self.fuente,
                'url_o_referencia': self.url_o_referencia,
                'fecha_captura': self.fecha_captura,
                'descripcion': self.descripcion,
                'contenido': self.contenido,
            }
            self.hash_insumo = stable_hash(payload)


@dataclass
class AjusteAplicado:
    """Un ajuste técnico aplicado a un comparable o cálculo."""
    nombre: str                    # "Ajuste por área", "Ajuste por antigüedad", etc.
    factor: float                  # Multiplicador aplicado (ej: 1.05 = +5%)
    justificacion: str             # Explicación humana


@dataclass
class ResultadoMetodo:
    """Resultado de aplicar un método valuatorio a un predio."""
    metodo: Literal["M1", "M2", "M3", "M4"]
    nombre_metodo: str             # "Comparación de Mercado", etc.
    valor_central_cop: int         # Pesos colombianos
    banda_baja_cop: int
    banda_alta_cop: int
    valor_por_m2_central: int      # Para comparabilidad cruzada
    insumos: list[Insumo] = field(default_factory=list)
    ajustes_aplicados: list[AjusteAplicado] = field(default_factory=list)
    metodologia_descripcion: str = ""   # Texto que va al dictamen
    observaciones: list[str] = field(default_factory=list)
    hash_resultado: str = ""

    def __post_init__(self):
        if not self.hash_resultado:
            payload = {
                'metodo': self.metodo,
                'valor_central_cop': self.valor_central_cop,
                'banda': [self.banda_baja_cop, self.banda_alta_cop],
                'insumos_hashes': [i.hash_insumo for i in self.insumos],
                'ajustes': [(a.nombre, a.factor) for a in self.ajustes_aplicados],
            }
            self.hash_resultado = stable_hash(payload)


@dataclass
class ReglaConsolidacion:
    """Regla declarada por el avaluador o por la metodología corporativa de la Lonja."""
    pesos: dict                    # {"M1": 0.6, "M2": 0.3, "M3": 0.1}
    tolerancia_coherencia_pct: float       # Distancia máxima entre métodos para considerar coherente (ej: 0.15 = 15%)
    fallback_dos_metodos: dict     # Pesos cuando un método se desestima por distancia
    autor: str                     # "Avaluador X RAA" o "Metodología Corporativa Lonja BAQ"
    version: str                   # "v1.0"


@dataclass
class Predio:
    """Identificación del predio bajo avalúo."""
    folio_matricula: str
    direccion: str
    ciudad: str
    barrio: str
    estrato: int
    area_construida_m2: float
    coeficiente_copropiedad: float = 0.0
    tipologia: str = ""            # "Apartamento NO VIS", "Casa", etc.
    antiguedad_anos: int = 0
    piso: Optional[int] = None
    descripcion_adicional: str = ""


@dataclass
class AvaluoConsolidado:
    """Resultado final del motor TMA — listo para revisión y firma."""
    predio: Predio
    fecha_calculo: str             # ISO 8601
    metodos_ejecutados: list[ResultadoMetodo]
    regla_consolidacion: ReglaConsolidacion
    distancia_max_observada_pct: float
    metodos_efectivos: list[str]   # Métodos que entraron al consolidado (algunos pueden haber sido desestimados)
    pesos_efectivos: dict          # Pesos finales aplicados
    valor_consolidado_cop: int
    banda_consolidada_baja_cop: int
    banda_consolidada_alta_cop: int
    estado: Literal["VERDE", "AMARILLA", "ROJA"]
    razon_estado: str              # Explicación del semáforo
    requiere_visita: bool
    observaciones_motor: list[str] = field(default_factory=list)
    hash_avaluo: str = ""
    
    def __post_init__(self):
        if not self.hash_avaluo:
            payload = {
                'predio': asdict(self.predio),
                'fecha_calculo': self.fecha_calculo,
                'metodos_hashes': [m.hash_resultado for m in self.metodos_ejecutados],
                'regla_consolidacion': asdict(self.regla_consolidacion),
                'valor_consolidado_cop': self.valor_consolidado_cop,
                'estado': self.estado,
            }
            self.hash_avaluo = stable_hash(payload)


@dataclass
class FirmaAvaluador:
    """Firma criptográfica del avaluador RAA sobre el avalúo consolidado."""
    avaluador_nombre: str
    raa_inscripcion: str
    era_afiliacion: str            # "ANA", "ANAV", "RNA", etc.
    categoria_raa: str
    fecha_firma: str               # ISO 8601
    hash_avaluo_firmado: str       # Hash del AvaluoConsolidado al momento de firma
    firma_ed25519: str             # Firma criptográfica (en producción real)
    valor_final_determinado_cop: int   # El avaluador puede ajustar el consolidado dentro de la banda
    observaciones_avaluador: str = ""


# ============================================================
# UTILIDADES DE FORMATO
# ============================================================
def fmt_cop(valor: int) -> str:
    """Formatea pesos colombianos: 295000000 -> '$ 295.000.000'"""
    return f"$ {valor:,}".replace(",", ".")


def fmt_m2(valor: int) -> str:
    """Formatea valor por m²"""
    return f"$ {valor:,}/m²".replace(",", ".")


def fmt_pct(valor: float) -> str:
    """Formatea porcentaje"""
    return f"{valor*100:.2f}%"


if __name__ == "__main__":
    print("Contrato de datos TMA cargado correctamente.")
    print("Estructuras disponibles: Insumo, AjusteAplicado, ResultadoMetodo,")
    print("                         ReglaConsolidacion, Predio, AvaluoConsolidado, FirmaAvaluador")

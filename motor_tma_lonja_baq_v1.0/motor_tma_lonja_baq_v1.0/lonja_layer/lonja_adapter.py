"""
ADAPTADOR LONJA → MOTOR TMA
═══════════════════════════════════════════════════════════════════════════════

Este módulo es el ÚNICO punto de integración entre la metodología declarada
por la Lonja (en YAML) y el motor de ejecución TMA.

El motor NO sabe nada de la Lonja. Solo recibe:
  - Pesos de consolidación
  - Tolerancia de coherencia
  - Tasas de capitalización
  - Costos de construcción base + factor de actualización
  - Coeficientes Fitto-Corvini
  - Corrimiento oferta-cierre por nivel de ancla
  - Valores de suelo por sector

Si la Lonja cambia un parámetro en el YAML, el motor lo recoge automáticamente
en el siguiente avalúo. NO hay código Python que tocar.

Esta separación es la que hace creíble decir a Franco:
  "El motor ejecuta lo que la Lonja declara. No al revés."
"""
import yaml
import sys
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from typing import Optional


@dataclass
class LonjaConfig:
    """Configuración cargada desde el YAML de la Lonja."""
    yaml_path: str
    fecha_carga: str
    entidad: str
    vigencia_desde: str
    vigencia_hasta: str
    metodos_activos: dict
    pesos_consolidacion: dict
    tolerancia_coherencia: float
    coef_variacion_max: float
    redistribucion_fallback: bool
    factor_costos: float
    tipologias_aprobadas: list
    coef_fitto_corvini: dict
    vida_util_por_sistema: dict
    tasas_capitalizacion: dict
    corrimiento_oferta_cierre: dict
    pesos_homogeneidad: dict
    valores_suelo: dict
    firma_corporativa: dict
    yaml_completo: dict  # Para referencia y trazabilidad

    def hash_declaracion(self) -> str:
        """Hash del YAML completo — sirve para sellar la versión usada en cada dictamen."""
        import hashlib
        contenido_str = yaml.safe_dump(self.yaml_completo, sort_keys=True)
        return hashlib.sha256(contenido_str.encode()).hexdigest()


def cargar_declaracion_lonja(yaml_path: str) -> LonjaConfig:
    """
    Carga el archivo YAML de declaración de la Lonja y lo convierte en la
    estructura que el motor consume.
    
    Esta función NO valida contra reglas internas de Sinergia. Confía en lo
    que la Lonja declaró. Lo único que valida es la integridad estructural
    del YAML (que existan las claves requeridas).
    """
    path = Path(yaml_path)
    if not path.exists():
        raise FileNotFoundError(f"Declaración de Lonja no encontrada: {yaml_path}")
    
    with open(path, 'r', encoding='utf-8') as f:
        yml = yaml.safe_load(f)
    
    # Verificar estructura mínima
    claves_requeridas = ['declaracion', 'metodos_activos', 'regla_consolidacion',
                          'costos_construccion', 'depreciacion', 'capitalizacion_rentas',
                          'comparacion_mercado', 'valor_suelo_por_sector', 'firma_corporativa']
    for k in claves_requeridas:
        if k not in yml:
            raise ValueError(f"YAML incompleto — falta sección requerida: '{k}'")
    
    # Verificar vigencia
    hoy = datetime.now().strftime('%Y-%m-%d')
    vigencia_hasta = yml['declaracion']['vigencia_hasta']
    if hoy > vigencia_hasta:
        print(f"⚠ ADVERTENCIA: La declaración de la Lonja venció el {vigencia_hasta}. "
              f"Solicitar a la Junta Técnica nueva versión antes de emitir más dictámenes.",
              file=sys.stderr)
    
    return LonjaConfig(
        yaml_path=str(path.absolute()),
        fecha_carga=datetime.now().isoformat(),
        entidad=yml['declaracion']['entidad'],
        vigencia_desde=yml['declaracion']['vigencia_desde'],
        vigencia_hasta=yml['declaracion']['vigencia_hasta'],
        metodos_activos={k: v.get('activo', False) for k, v in yml['metodos_activos'].items()},
        pesos_consolidacion=yml['regla_consolidacion']['pesos_default'],
        tolerancia_coherencia=yml['regla_consolidacion']['tolerancia_coherencia_pct'],
        coef_variacion_max=yml['regla_consolidacion']['coeficiente_variacion_max'],
        redistribucion_fallback=yml['regla_consolidacion']['redistribucion_fallback'],
        factor_costos=yml['costos_construccion']['factor_actualizacion'],
        tipologias_aprobadas=yml['costos_construccion']['tipologias_aprobadas'],
        coef_fitto_corvini=yml['depreciacion']['coeficientes'],
        vida_util_por_sistema=yml['depreciacion']['vida_util_anos'],
        tasas_capitalizacion=yml['capitalizacion_rentas']['tasas_por_tipologia'],
        corrimiento_oferta_cierre=yml['comparacion_mercado']['corrimiento_oferta_cierre'],
        pesos_homogeneidad=yml['comparacion_mercado']['pesos_homogeneidad'],
        valores_suelo=yml['valor_suelo_por_sector'],
        firma_corporativa=yml['firma_corporativa'],
        yaml_completo=yml,
    )


def imprimir_resumen_declaracion(cfg: LonjaConfig):
    """Imprime un resumen legible de lo que la Lonja declaró."""
    print("=" * 72)
    print(f"DECLARACIÓN METODOLÓGICA CARGADA")
    print("=" * 72)
    print(f"Entidad:                  {cfg.entidad}")
    print(f"Vigencia:                 {cfg.vigencia_desde} → {cfg.vigencia_hasta}")
    print(f"Hash de declaración:      {cfg.hash_declaracion()[:16]}…")
    print()
    print("Métodos activos:")
    for m, activo in cfg.metodos_activos.items():
        marker = "✓" if activo else "✗"
        print(f"  {marker} {m}")
    print()
    print(f"Regla de consolidación declarada por la Lonja:")
    for m, peso in cfg.pesos_consolidacion.items():
        print(f"  {m}: {peso*100:.0f}%")
    print(f"  Tolerancia de coherencia: {cfg.tolerancia_coherencia*100:.0f}%")
    print(f"  Coef. variación máx:      {cfg.coef_variacion_max*100:.1f}%")
    print(f"  Fallback redistribución:  {'sí' if cfg.redistribucion_fallback else 'no'}")
    print()
    print(f"Factor actualización costos {datetime.now().year}: {cfg.factor_costos:.4f}")
    print(f"Tipologías aprobadas:     {len(cfg.tipologias_aprobadas)} tipologías Camacol")
    print(f"Tasas capitalización:     {len(cfg.tasas_capitalizacion)} tipologías declaradas")
    print(f"Sectores con valor suelo: {len(cfg.valores_suelo)} sectores")
    print()
    print("Firma corporativa:")
    for fir in cfg.firma_corporativa['firmantes_obligatorios']:
        print(f"  • {fir['rol']}")
    print()


if __name__ == "__main__":
    cfg = cargar_declaracion_lonja('/home/claude/lonja_layer/lonja_baq_metodologia.yaml')
    imprimir_resumen_declaracion(cfg)

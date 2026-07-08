"""
Módulo de Depreciación Fitto-Corvini
Implementación rigurosa según Resolución IGAC 620 de 2008.

La norma colombiana exige modelos de depreciación CONTINUOS (no lineales) que tengan
en cuenta la edad y el estado de conservación, según las ecuaciones de Fitto y Corvini.

Vidas útiles según la norma:
  - Estructura en concreto, metálica, mampostería estructural: 100 años
  - Muros de carga: 70 años

Estados de conservación (Resolución 620 de 2008):
  Clase 1 (1.0): Bien conservado, sin reparaciones
  Clase 2 (2.0): Bien conservado, reparaciones menores
  Clase 3 (3.0): Reparaciones sencillas
  Clase 4 (4.0): Reparaciones importantes
  Clase 5 (5.0): Amenaza ruina (depreciación 100%)

Las ecuaciones de Fitto-Corvini relacionan el porcentaje de la vida (X) y el estado:
  Estado 1.0:  Y = 0.5 × (X² + X)
              ≈ depreciación mínima
  Estado 1.5:  Y = 0.5 × (X² + X·1.084)
  Estado 2.0:  Y = 0.5 × (X² + X·1.168) + 0.5 × X(1-X) × 0.025  
  Estado 2.5:  Y = 0.5 × (X² + X·1.252) + 0.5 × X(1-X) × 0.0809
  Estado 3.0:  Y = 0.5 × (X² + X·1.336) + 0.5 × X(1-X) × 0.1810
  Estado 3.5:  Y = 0.5 × (X² + X·1.420) + 0.5 × X(1-X) × 0.3320
  Estado 4.0:  Y = 0.5 × (X² + X·1.504) + 0.5 × X(1-X) × 0.5230
  Estado 5.0:  Y = 1.0 (depreciación total)

Donde:
  X = edad cronológica / vida útil
  Y = factor de depreciación (porcentaje a descontar del valor a nuevo)

Para conjunto Napoli (estructura concreto, 3 años, estado Clase 1-2 por antigüedad):
  Vida útil = 100 años
  X = 3/100 = 0.03
  Estado típico para PH nueva bien mantenida: Clase 1.5 a 2.0
"""


# Coeficientes de Fitto-Corvini por estado de conservación
# Cada coeficiente C corresponde al término que multiplica X(1-X) en la fórmula:
# Y = (1/2) × [X² + (X × A_estado)] + (1/2) × X(1-X) × C_estado
# Donde A_estado es el coeficiente lineal y C_estado el de mantenimiento
COEFICIENTES_FITTO_CORVINI = {
    1.0: {"A": 1.000, "C": 0.000},   # Excelente
    1.5: {"A": 1.084, "C": 0.000},   # Muy bueno
    2.0: {"A": 1.168, "C": 0.025},   # Bueno
    2.5: {"A": 1.252, "C": 0.0809},  # Bueno-Regular
    3.0: {"A": 1.336, "C": 0.1810},  # Regular
    3.5: {"A": 1.420, "C": 0.3320},  # Regular-Malo
    4.0: {"A": 1.504, "C": 0.5230},  # Malo
    5.0: {"A": 0.000, "C": 1.000},   # Demolición (Y = 1 directamente)
}

VIDA_UTIL_ANOS = {
    "concreto": 100,
    "metalica": 100,
    "mamposteria_estructural": 100,
    "muros_carga": 70,
}


def calcular_depreciacion_fitto_corvini(edad_anos: float, estado_clase: float, sistema_constructivo: str = "concreto") -> dict:
    """
    Calcula el factor de depreciación según Fitto-Corvini conforme Resolución IGAC 620/2008.
    
    Args:
        edad_anos: Edad cronológica del inmueble en años
        estado_clase: Clase de conservación (1.0 a 5.0)
        sistema_constructivo: Sistema estructural ("concreto", "metalica", "mamposteria_estructural", "muros_carga")
    
    Returns:
        dict con:
          - factor_depreciacion: Y, porcentaje a descontar del valor a nuevo (0 a 1)
          - factor_conservacion: 1 - Y, porcentaje del valor que se conserva
          - vida_util: vida útil aplicada
          - X: porcentaje de vida consumida
          - metodologia: descripción
    """
    # Caso especial: estado 5.0 = demolición
    if estado_clase >= 5.0:
        return {
            "factor_depreciacion": 1.0,
            "factor_conservacion": 0.0,
            "vida_util_anos": VIDA_UTIL_ANOS[sistema_constructivo],
            "X": 1.0,
            "estado_clase": estado_clase,
            "metodologia": "Estado de Conservación Clase 5 — depreciación total (Resolución IGAC 620/2008)"
        }
    
    # Validar estado
    estados_validos = sorted(COEFICIENTES_FITTO_CORVINI.keys())
    estado_validado = min(estados_validos, key=lambda e: abs(e - estado_clase))
    
    # Validar sistema constructivo
    if sistema_constructivo not in VIDA_UTIL_ANOS:
        sistema_constructivo = "concreto"
    
    vida_util = VIDA_UTIL_ANOS[sistema_constructivo]
    
    # Calcular X (porcentaje de vida consumida)
    X = edad_anos / vida_util
    
    # Aplicar fórmula Fitto-Corvini
    A = COEFICIENTES_FITTO_CORVINI[estado_validado]["A"]
    C = COEFICIENTES_FITTO_CORVINI[estado_validado]["C"]
    
    Y_base = 0.5 * (X**2 + X * A)
    Y_correccion = 0.5 * X * (1 - X) * C
    Y = Y_base + Y_correccion
    
    # Cap en [0, 1]
    Y = max(0.0, min(1.0, Y))
    
    return {
        "factor_depreciacion": Y,
        "factor_conservacion": 1.0 - Y,
        "vida_util_anos": vida_util,
        "X": X,
        "estado_clase": estado_validado,
        "sistema_constructivo": sistema_constructivo,
        "coef_A": A,
        "coef_C": C,
        "metodologia": (
            f"Depreciación Fitto-Corvini (Resolución IGAC 620/2008): "
            f"Estado de Conservación Clase {estado_validado:.1f}, "
            f"vida útil {vida_util} años, edad {edad_anos:.1f} años, "
            f"X={X*100:.2f}%, factor depreciación Y={Y*100:.2f}%, "
            f"valor conservado {(1-Y)*100:.2f}%."
        )
    }


if __name__ == "__main__":
    print("="*70)
    print("Test del módulo Fitto-Corvini")
    print("="*70)
    
    # Caso Conjunto Napoli: 3 años, estado Clase 1.5 (muy bueno, prácticamente nuevo)
    res = calcular_depreciacion_fitto_corvini(edad_anos=3, estado_clase=1.5, sistema_constructivo="concreto")
    print(f"\nConjunto Napoli (3 años, Clase 1.5):")
    print(f"  Factor depreciación: {res['factor_depreciacion']*100:.3f}%")
    print(f"  Factor conservación: {res['factor_conservacion']*100:.3f}%")
    print(f"  X (vida consumida): {res['X']*100:.2f}%")
    
    # Comparación con depreciación lineal del 1% anual usada antes
    depreciacion_lineal = 0.03  # 3% para 3 años
    print(f"\n  Comparación:")
    print(f"    Lineal anterior (1%/año):    {depreciacion_lineal*100:.3f}%")
    print(f"    Fitto-Corvini real:          {res['factor_depreciacion']*100:.3f}%")
    print(f"    Diferencia:                  {(res['factor_depreciacion']-depreciacion_lineal)*100:+.3f}pp")
    
    # Algunos otros casos para validar la curva
    print(f"\nValidación de la curva Fitto-Corvini (concreto, 100 años vida útil):")
    print(f"  {'Edad':>6} {'Estado':>8} {'X':>7} {'Y(%)':>8} {'Conserva%':>10}")
    casos = [(0, 1.0), (5, 1.5), (10, 2.0), (20, 2.0), (30, 2.5), (50, 3.0), (75, 3.5), (90, 4.0)]
    for edad, est in casos:
        r = calcular_depreciacion_fitto_corvini(edad, est)
        print(f"  {edad:>6} {est:>8.1f} {r['X']*100:>6.1f}% {r['factor_depreciacion']*100:>7.2f}% {r['factor_conservacion']*100:>9.2f}%")

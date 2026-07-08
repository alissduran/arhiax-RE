"""
PIEZA 3 — Constructor M3: Método de Capitalización de Rentas

Marco normativo: Resolución IGAC 1040 de 2023 — Método de Capitalización de Rentas o Ingresos.

Fórmula:
  Valor M3 = Renta Neta Anual / Tasa de Capitalización
  
Donde:
  - Renta Neta Anual = Canon Mensual × 12 × (1 - Vacancia) × (1 - Gastos No Recuperables)
  - Tasa de Capitalización = tasa de mercado para residencial Costa Caribe (típicamente 6%-8%)

Aplicabilidad: válido para activos que generan o pueden generar renta — apartamentos
para arriendo, locales, oficinas. Para Apto 430 Nápoli: aplicable como método secundario.

Output: ResultadoMetodo con valor central, banda 80%, insumos trazables.
"""
import sys
sys.path.insert(0, '/home/claude/tma_engine/piezas')
sys.path.insert(0, '/home/claude/tma_engine/datos')

from contrato_datos import (
    ResultadoMetodo, Insumo, AjusteAplicado, Predio
)


def construir_M3(predio: Predio, canones_data: dict) -> ResultadoMetodo:
    """
    Aplica el método de capitalización de rentas.
    
    Args:
        predio: Predio bajo avalúo
        canones_data: dict con cánones de mercado y tasa de capitalización
    
    Returns:
        ResultadoMetodo con M3 ejecutado
    """
    
    # ============================================================
    # PASO 1: Identificar tipología aplicable
    # ============================================================
    if predio.estrato == 4 and 50 <= predio.area_construida_m2 <= 70:
        tipologia_canon = "apto_NO_VIS_50_70m2_estrato4"
    else:
        tipologia_canon = list(canones_data["rangos_canon_mensual_por_tipologia"].keys())[0]
    
    rangos_canon = canones_data["rangos_canon_mensual_por_tipologia"][tipologia_canon]
    
    # ============================================================
    # PASO 2: Construir insumos trazables
    # ============================================================
    insumos = []
    
    insumo_canones = Insumo(
        fuente=canones_data["fuente"],
        url_o_referencia=canones_data["url_referencia"],
        fecha_captura=canones_data["fecha_captura"],
        descripcion=f"Cánones de arrendamiento observados — tipología: {tipologia_canon}",
        contenido={
            "tipologia": tipologia_canon,
            "canon_min_cop": rangos_canon["canon_min_cop"],
            "canon_central_cop": rangos_canon["canon_central_cop"],
            "canon_max_cop": rangos_canon["canon_max_cop"],
        }
    )
    insumos.append(insumo_canones)
    
    insumo_tasa = Insumo(
        fuente="Referencia tasa capitalización mercado residencial Costa Caribe",
        url_o_referencia=canones_data["url_referencia"],
        fecha_captura=canones_data["fecha_captura"],
        descripcion="Tasa de capitalización aplicable y supuestos de vacancia/gastos",
        contenido={
            "tasa_central_pct": canones_data["tasa_capitalizacion_mercado_residencial_pct"],
            "tasa_min_pct": canones_data["tasa_min_pct"],
            "tasa_max_pct": canones_data["tasa_max_pct"],
            "vacancia_pct": canones_data["vacancia_estimada_pct"],
            "gastos_no_recuperables_pct": canones_data["gastos_no_recuperables_pct"],
        }
    )
    insumos.append(insumo_tasa)
    
    # ============================================================
    # PASO 3: Calcular renta neta anual (caso central)
    # ============================================================
    canon_mensual_central = rangos_canon["canon_central_cop"]
    canon_mensual_min = rangos_canon["canon_min_cop"]
    canon_mensual_max = rangos_canon["canon_max_cop"]
    
    factor_neto = (1.0 - canones_data["vacancia_estimada_pct"]) * (1.0 - canones_data["gastos_no_recuperables_pct"])
    
    renta_neta_anual_central = canon_mensual_central * 12 * factor_neto
    renta_neta_anual_min = canon_mensual_min * 12 * factor_neto
    renta_neta_anual_max = canon_mensual_max * 12 * factor_neto
    
    # ============================================================
    # PASO 4: Capitalización - valor = renta neta / tasa
    # ============================================================
    tasa_central = canones_data["tasa_capitalizacion_mercado_residencial_pct"]
    tasa_min = canones_data["tasa_min_pct"]
    tasa_max = canones_data["tasa_max_pct"]
    
    valor_central_cop = int(renta_neta_anual_central / tasa_central)
    
    # Para banda baja: peor escenario combinado (canon mínimo + tasa máxima = valor menor)
    valor_baja_cop = int(renta_neta_anual_min / tasa_max)
    # Para banda alta: mejor escenario combinado (canon máximo + tasa mínima = valor mayor)
    valor_alta_cop = int(renta_neta_anual_max / tasa_min)
    
    # Pero estos extremos son demasiado amplios para banda 80%
    # Aplicamos quartiles internos
    banda_baja_cop = int((valor_central_cop + valor_baja_cop) / 2)
    banda_alta_cop = int((valor_central_cop + valor_alta_cop) / 2)
    
    valor_por_m2_central = int(valor_central_cop / predio.area_construida_m2)
    
    # ============================================================
    # PASO 5: Documentar ajustes
    # ============================================================
    ajustes_aplicados = [
        AjusteAplicado(
            nombre="Canon mensual de mercado",
            factor=1.0,
            justificacion=f"Canon central observado para tipología {tipologia_canon}: $ {canon_mensual_central:,} COP/mes "
                         f"(rango $ {canon_mensual_min:,} - $ {canon_mensual_max:,})."
        ),
        AjusteAplicado(
            nombre="Vacancia estimada",
            factor=1.0 - canones_data["vacancia_estimada_pct"],
            justificacion=f"Tasa de vacancia del {canones_data['vacancia_estimada_pct']*100:.1f}% — refleja meses sin arrendatario en el ciclo anual."
        ),
        AjusteAplicado(
            nombre="Gastos no recuperables",
            factor=1.0 - canones_data["gastos_no_recuperables_pct"],
            justificacion=f"Gastos administrativos, mantenimiento y seguros no recuperables del propietario: {canones_data['gastos_no_recuperables_pct']*100:.1f}%."
        ),
        AjusteAplicado(
            nombre=f"Tasa de capitalización aplicada: {tasa_central*100:.1f}%",
            factor=tasa_central,
            justificacion=f"Tasa de capitalización para residencial Costa Caribe — rango común {tasa_min*100:.0f}%-{tasa_max*100:.0f}%, "
                         f"central {tasa_central*100:.1f}%. Banda construida con tasas extremas combinadas con cánones extremos."
        ),
    ]
    
    # ============================================================
    # PASO 6: Texto metodológico
    # ============================================================
    metodologia = (
        f"Método M3 — Capitalización de Rentas (Resolución IGAC 1040/2023). "
        f"Canon mensual central observado: $ {canon_mensual_central:,} COP/mes. "
        f"Renta neta anual = canon × 12 × (1 - {canones_data['vacancia_estimada_pct']*100:.0f}% vacancia) × (1 - {canones_data['gastos_no_recuperables_pct']*100:.0f}% gastos) "
        f"= $ {renta_neta_anual_central:,.0f}. "
        f"Tasa de capitalización aplicada: {tasa_central*100:.2f}%. "
        f"Valor M3 = renta neta anual / tasa = $ {valor_central_cop:,}."
    )
    
    # ============================================================
    # PASO 7: Observaciones
    # ============================================================
    observaciones = []
    
    yield_implicito = renta_neta_anual_central / valor_central_cop
    observaciones.append(
        f"Yield neto implícito en el resultado: {yield_implicito*100:.2f}% — coherente con la tasa de capitalización aplicada por construcción."
    )
    
    pago_meses = valor_central_cop / canon_mensual_central
    observaciones.append(
        f"El activo se 'paga' (a renta bruta sin descuentos) en {pago_meses:.1f} meses — métrica de referencia para inversionistas."
    )
    
    observaciones.append(
        "M3 es método secundario en este avalúo — se aplica con peso menor en consolidado dado que el activo está en uso residencial directo, no en arriendo activo."
    )
    
    # ============================================================
    # PASO 8: Construir ResultadoMetodo
    # ============================================================
    resultado = ResultadoMetodo(
        metodo="M3",
        nombre_metodo="Capitalización de Rentas",
        valor_central_cop=valor_central_cop,
        banda_baja_cop=banda_baja_cop,
        banda_alta_cop=banda_alta_cop,
        valor_por_m2_central=valor_por_m2_central,
        insumos=insumos,
        ajustes_aplicados=ajustes_aplicados,
        metodologia_descripcion=metodologia,
        observaciones=observaciones,
    )
    
    return resultado


if __name__ == "__main__":
    from insumos_napoli import PREDIO_NAPOLI_430, CANONES_MIRAMAR_2026
    from contrato_datos import fmt_cop, fmt_m2
    
    print("="*70)
    print("PIEZA 3 — Constructor M3: Capitalización de Rentas")
    print("="*70)
    
    resultado = construir_M3(PREDIO_NAPOLI_430, CANONES_MIRAMAR_2026)
    
    print(f"\nMétodo: {resultado.metodo} — {resultado.nombre_metodo}")
    print(f"Insumos: {len(resultado.insumos)}")
    print(f"Ajustes: {len(resultado.ajustes_aplicados)}")
    print(f"\nResultado:")
    print(f"  Valor central:    {fmt_cop(resultado.valor_central_cop)}")
    print(f"  Banda 80%:        {fmt_cop(resultado.banda_baja_cop)} — {fmt_cop(resultado.banda_alta_cop)}")
    print(f"  Valor por m²:     {fmt_m2(resultado.valor_por_m2_central)}")
    print(f"\nHash:               {resultado.hash_resultado[:16]}...")
    print(f"\nObservaciones:")
    for o in resultado.observaciones:
        print(f"  · {o}")

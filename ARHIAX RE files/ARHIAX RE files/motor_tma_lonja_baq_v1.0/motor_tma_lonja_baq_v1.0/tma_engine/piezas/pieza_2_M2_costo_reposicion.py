"""
PIEZA 2 — Constructor M2: Método de Costo de Reposición a Nuevo

Marco normativo: Resolución IGAC 1040 de 2023 — Método de Costo.

Fórmula:
  Valor M2 = (Costo Construcción Nuevo × Factor Depreciación) + Valor del Suelo (cuota)
  
Donde:
  - Costo Construcción Nuevo = Costo m² Camacol × Área Construida
  - Factor Depreciación = 1 - (años × tasa_anual)
  - Valor del Suelo = Valor m² terreno × Área del lote × Coeficiente copropiedad

Para Conjunto Napoli (multifamiliar medio-medio, 4-5 pisos, estrato 4 Barranquilla):
Tipología Camacol aplicable: "Multifamiliar medio-medio"

Output: ResultadoMetodo con valor central, banda 80%, insumos trazables.
"""
import sys
sys.path.insert(0, '/home/claude/tma_engine/piezas')
sys.path.insert(0, '/home/claude/tma_engine/datos')

from contrato_datos import (
    ResultadoMetodo, Insumo, AjusteAplicado, Predio
)
from depreciacion_fitto_corvini import calcular_depreciacion_fitto_corvini


def construir_M2(
    predio: Predio,
    costos_camacol: dict,
    valor_suelo_data: dict,
    tipologia_camacol: str = "Multifamiliar medio-medio (4-5 pisos)",
    estado_conservacion_clase: float = 1.5,
    sistema_constructivo: str = "concreto"
) -> ResultadoMetodo:
    """
    Aplica el método de costo de reposición a nuevo.
    
    Args:
        predio: Predio bajo avalúo
        costos_camacol: dict con tipologías Camacol y costos por m²
        valor_suelo_data: dict con datos del valor del suelo en zona homogénea
        tipologia_camacol: tipología aplicable para el activo
    
    Returns:
        ResultadoMetodo con M2 ejecutado
    """
    
    # ============================================================
    # PASO 1: Construir insumos trazables
    # ============================================================
    insumos = []
    
    # Insumo 1: Tabla Camacol
    insumo_camacol = Insumo(
        fuente=costos_camacol["fuente"],
        url_o_referencia=costos_camacol["url_referencia"],
        fecha_captura=costos_camacol["fecha_captura"],
        descripcion=f"Costos de construcción Camacol Q1-2026 — tipología aplicable: {tipologia_camacol}",
        contenido={
            "tipologia": tipologia_camacol,
            "costo_directo_m2": costos_camacol["tipologias"][tipologia_camacol]["costo_directo_m2"],
            "costo_total_m2": costos_camacol["tipologias"][tipologia_camacol]["costo_total_m2"],
            "vigencia": costos_camacol["vigencia"],
        }
    )
    insumos.append(insumo_camacol)
    
    # Insumo 2: Valor del suelo
    insumo_suelo = Insumo(
        fuente=valor_suelo_data["fuente"],
        url_o_referencia=valor_suelo_data["url_referencia"],
        fecha_captura=valor_suelo_data["fecha_captura"],
        descripcion="Valor del suelo en zona homogénea geoeconómica Miramar (referencial)",
        contenido={
            "valor_m2_terreno_cop": valor_suelo_data["valor_m2_terreno_cop_referencial"],
            "area_lote_estimada_m2": valor_suelo_data["area_lote_conjunto_napoli_estimada_m2"],
            "observaciones": valor_suelo_data["observaciones"],
        }
    )
    insumos.append(insumo_suelo)
    
    # ============================================================
    # PASO 2: Calcular costo de construcción a nuevo
    # ============================================================
    costo_total_m2_nuevo = costos_camacol["tipologias"][tipologia_camacol]["costo_total_m2"]
    costo_construccion_nuevo = costo_total_m2_nuevo * predio.area_construida_m2
    
    # ============================================================
    # PASO 3: Aplicar depreciación Fitto-Corvini (Resolución IGAC 620/2008)
    # ============================================================
    # NORMATIVO: la Resolución 620/2008 EXIGE modelos continuos (no lineales)
    # con edad y estado de conservación. Fitto-Corvini es el método estándar.
    depreciacion = calcular_depreciacion_fitto_corvini(
        edad_anos=predio.antiguedad_anos,
        estado_clase=estado_conservacion_clase,
        sistema_constructivo=sistema_constructivo
    )
    factor_depreciacion = depreciacion["factor_depreciacion"]
    factor_conservacion = depreciacion["factor_conservacion"]
    
    costo_construccion_depreciado = int(costo_construccion_nuevo * factor_conservacion)
    
    # ============================================================
    # PASO 4: Calcular valor del suelo (cuota del activo)
    # ============================================================
    valor_lote_completo = (
        valor_suelo_data["valor_m2_terreno_cop_referencial"] *
        valor_suelo_data["area_lote_conjunto_napoli_estimada_m2"]
    )
    valor_suelo_cuota_activo = int(valor_lote_completo * predio.coeficiente_copropiedad)
    
    # ============================================================
    # PASO 5: Valor M2 central = construcción depreciada + cuota suelo
    # ============================================================
    valor_central_cop = costo_construccion_depreciado + valor_suelo_cuota_activo
    valor_por_m2_central = int(valor_central_cop / predio.area_construida_m2)
    
    # ============================================================
    # PASO 6: Construir banda 80% considerando incertidumbre
    # ============================================================
    # Banda baja: tipología un escalón menor
    costo_baja_m2 = costos_camacol["tipologias"]["Multifamiliar medio-bajo"]["costo_total_m2"]
    construccion_baja = int(costo_baja_m2 * predio.area_construida_m2 * factor_conservacion)
    valor_suelo_baja = int(valor_suelo_cuota_activo * 0.85)  # -15% incertidumbre suelo
    banda_baja_cop = construccion_baja + valor_suelo_baja
    
    # Banda alta: tipología un escalón mayor (alto típico)
    costo_alta_m2 = costos_camacol["tipologias"]["Multifamiliar alto típico (6 pisos)"]["costo_total_m2"]
    construccion_alta = int(costo_alta_m2 * predio.area_construida_m2 * factor_conservacion)
    valor_suelo_alta = int(valor_suelo_cuota_activo * 1.15)  # +15% incertidumbre suelo
    banda_alta_cop = construccion_alta + valor_suelo_alta
    
    # ============================================================
    # PASO 7: Documentar ajustes
    # ============================================================
    ajustes_aplicados = [
        AjusteAplicado(
            nombre=f"Tipología Camacol aplicable: {tipologia_camacol}",
            factor=1.0,
            justificacion=f"Conjunto Napoli es propiedad horizontal multifamiliar de 4-5 pisos con acabados estándar — tipología 'medio-medio' aplicable según referencias publicadas Camacol Q1-2026. Costo total por m² aplicado: $ {costo_total_m2_nuevo:,}."
        ),
        AjusteAplicado(
            nombre=f"Depreciación Fitto-Corvini (Resolución IGAC 620/2008)",
            factor=factor_conservacion,
            justificacion=(
                f"Método Fitto-Corvini exigido por Resolución IGAC 620/2008 para construcciones. "
                f"Sistema {sistema_constructivo}, vida útil {depreciacion['vida_util_anos']} años, "
                f"edad {predio.antiguedad_anos} años, X={depreciacion['X']*100:.2f}%, "
                f"Estado de Conservación Clase {estado_conservacion_clase:.1f}, "
                f"factor depreciación Y={factor_depreciacion*100:.2f}%, "
                f"factor conservación {factor_conservacion*100:.2f}%."
            )
        ),
        AjusteAplicado(
            nombre="Valor del suelo (cuota propiedad horizontal)",
            factor=predio.coeficiente_copropiedad,
            justificacion=f"Aplicación del coeficiente de copropiedad de {predio.coeficiente_copropiedad*100:.4f}% sobre el valor estimado del lote del conjunto (área lote × valor m² terreno zona homogénea Miramar)."
        ),
        AjusteAplicado(
            nombre="Banda 80% por sensibilidad de tipología y suelo",
            factor=1.0,
            justificacion="Banda construida con tipologías Camacol adyacentes (medio-bajo y alto típico) y sensibilidad ±15% sobre valor del suelo para reflejar incertidumbre de la zona homogénea publicada."
        ),
    ]
    
    # ============================================================
    # PASO 8: Texto metodológico
    # ============================================================
    metodologia = (
        f"Método M2 — Costo de Reposición a Nuevo (Resolución IGAC 1040/2023, mod. 746/2024). "
        f"Costo de construcción aplicado según tipología Camacol Q2-2026 ajustada: "
        f"'{tipologia_camacol}' con costo total $ {costo_total_m2_nuevo:,}/m². "
        f"Costo de construcción a nuevo: $ {costo_construccion_nuevo:,.0f}. "
        f"Depreciación Fitto-Corvini (Resolución IGAC 620/2008): "
        f"sistema {sistema_constructivo}, vida útil {depreciacion['vida_util_anos']} años, "
        f"edad {predio.antiguedad_anos} años, Estado Clase {estado_conservacion_clase:.1f}, "
        f"factor conservación {factor_conservacion*100:.2f}%. "
        f"Costo construcción depreciado: $ {costo_construccion_depreciado:,}. "
        f"Valor del suelo (cuota): $ {valor_suelo_cuota_activo:,} "
        f"(coeficiente copropiedad {predio.coeficiente_copropiedad*100:.4f}%). "
        f"Valor M2 = construcción depreciada + cuota suelo."
    )
    
    # ============================================================
    # PASO 9: Observaciones
    # ============================================================
    observaciones = []
    
    pct_construccion = costo_construccion_depreciado / valor_central_cop
    observaciones.append(
        f"Componente construcción: {pct_construccion*100:.1f}% del valor M2 ($ {costo_construccion_depreciado:,})."
    )
    observaciones.append(
        f"Componente suelo: {(1-pct_construccion)*100:.1f}% del valor M2 ($ {valor_suelo_cuota_activo:,})."
    )
    
    if predio.antiguedad_anos < 10:
        observaciones.append(
            f"Edificación con antigüedad {predio.antiguedad_anos} años — Estado de Conservación Clase {estado_conservacion_clase:.1f} "
            f"(modo ACA Forense valida la clase con visita in situ). Curva Fitto-Corvini aplicada."
        )
    
    observaciones.append(
        "Valor del suelo es referencial — en modo ACA Forense se actualiza con consulta IGAC formal a Zona Homogénea Geoeconómica vigente."
    )
    
    # ============================================================
    # PASO 10: Construir ResultadoMetodo
    # ============================================================
    resultado = ResultadoMetodo(
        metodo="M2",
        nombre_metodo="Costo de Reposición a Nuevo",
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
    from insumos_napoli import (
        PREDIO_NAPOLI_430, COSTOS_CAMACOL_2026, VALOR_SUELO_MIRAMAR_2026,
        PREDIO_NAPOLI_430_TECNICO
    )
    from contrato_datos import fmt_cop, fmt_m2
    
    print("="*70)
    print("PIEZA 2 — Constructor M2: Costo de Reposición a Nuevo (Fitto-Corvini)")
    print("="*70)
    
    resultado = construir_M2(
        PREDIO_NAPOLI_430,
        COSTOS_CAMACOL_2026,
        VALOR_SUELO_MIRAMAR_2026,
        tipologia_camacol=PREDIO_NAPOLI_430_TECNICO["tipologia_camacol"],
        estado_conservacion_clase=PREDIO_NAPOLI_430_TECNICO["estado_conservacion_clase"],
        sistema_constructivo=PREDIO_NAPOLI_430_TECNICO["sistema_constructivo"],
    )
    
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

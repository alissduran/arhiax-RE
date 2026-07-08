"""
PIEZA 4 — Motor de Consolidación

Recibe los resultados de M1, M2, M3 y aplica:
  1. Regla de consolidación declarada (pesos por método)
  2. Verificación de coherencia entre métodos (banda de coherencia)
  3. Semáforo VERDE / AMARILLA / ROJA según convergencia
  4. Construcción del AvaluoConsolidado listo para revisión y firma

Reglas semáforo:
  VERDE   — todos los métodos dentro de tolerancia (≤15% de distancia)
            → estado "listo_para_firma", revisión 2-4 minutos
  AMARILLA — un método se aparta más de 15% pero los otros dos coinciden
            → método discordante se desestima, se reconsolida con dos
            → revisión 10-15 minutos (avaluador valida la decisión)
  ROJA    — dos o más métodos se apartan, no hay convergencia
            → "elevar_visita" — el avaluador debe ir físicamente
"""
import sys
sys.path.insert(0, '/home/claude/tma_engine/piezas')

from contrato_datos import (
    AvaluoConsolidado, ResultadoMetodo, ReglaConsolidacion, Predio
)
from datetime import datetime


# ============================================================
# REGLA DE CONSOLIDACIÓN POR DEFECTO PARA APARTAMENTOS NO VIS
# ============================================================
REGLA_DEFAULT_APTO_NO_VIS = ReglaConsolidacion(
    pesos={"M1": 0.60, "M2": 0.30, "M3": 0.10},
    tolerancia_coherencia_pct=0.15,
    fallback_dos_metodos={"M1": 0.70, "M2": 0.30},
    autor="Metodología corporativa Sinergia LAI v1.0 (pendiente validación con metodología corporativa Lonja BAQ)",
    version="v1.0"
)


def calcular_distancia_max(metodos: list[ResultadoMetodo]) -> tuple[float, str, str]:
    """
    Calcula la distancia máxima entre los valores centrales de los métodos.
    Retorna (distancia_pct, metodo_a_id, metodo_b_id) - los dos métodos más distantes.
    """
    valores = [(m.metodo, m.valor_central_cop) for m in metodos]
    max_dist = 0.0
    par_max = (None, None)
    for i, (id_a, va) in enumerate(valores):
        for id_b, vb in valores[i+1:]:
            promedio = (va + vb) / 2
            dist = abs(va - vb) / promedio
            if dist > max_dist:
                max_dist = dist
                par_max = (id_a, id_b)
    return max_dist, par_max[0], par_max[1]


def evaluar_coherencia(metodos: list[ResultadoMetodo], tolerancia_pct: float):
    """
    Evalúa cuál(es) método(s) está(n) dentro de tolerancia y cuál(es) fuera.
    Un método está fuera si su distancia al promedio de los demás supera la tolerancia.
    
    Retorna: (metodos_dentro, metodos_fuera) ambos listas de IDs (str).
    """
    if len(metodos) < 2:
        return [m.metodo for m in metodos], []
    
    metodos_dentro = []
    metodos_fuera = []
    
    for m in metodos:
        otros = [x.valor_central_cop for x in metodos if x.metodo != m.metodo]
        promedio_otros = sum(otros) / len(otros)
        dist = abs(m.valor_central_cop - promedio_otros) / promedio_otros
        if dist <= tolerancia_pct:
            metodos_dentro.append(m.metodo)
        else:
            metodos_fuera.append(m.metodo)
    
    return metodos_dentro, metodos_fuera


def consolidar(
    predio: Predio,
    metodos_ejecutados: list[ResultadoMetodo],
    regla: ReglaConsolidacion = None
) -> AvaluoConsolidado:
    """
    Consolida los resultados de los métodos en un AvaluoConsolidado final.
    """
    if regla is None:
        regla = REGLA_DEFAULT_APTO_NO_VIS
    
    observaciones_motor = []
    
    # ============================================================
    # PASO 1: Calcular distancia máxima entre métodos
    # ============================================================
    distancia_max_pct, met_a, met_b = calcular_distancia_max(metodos_ejecutados)
    observaciones_motor.append(
        f"Distancia máxima entre métodos: {distancia_max_pct*100:.2f}% (entre {met_a} y {met_b})."
    )
    
    # ============================================================
    # PASO 2: Evaluar coherencia método por método
    # ============================================================
    metodos_dentro, metodos_fuera = evaluar_coherencia(metodos_ejecutados, regla.tolerancia_coherencia_pct)
    
    # ============================================================
    # PASO 3: Determinar semáforo
    # ============================================================
    if len(metodos_fuera) == 0:
        # Todos los métodos coinciden
        estado = "VERDE"
        razon_estado = (
            f"Los tres métodos valuatorios convergen dentro de la tolerancia declarada "
            f"({regla.tolerancia_coherencia_pct*100:.0f}%). Distancia máxima observada: {distancia_max_pct*100:.2f}%. "
            f"El avalúo está listo para revisión y firma del avaluador (revisión estimada: 2-4 minutos)."
        )
        requiere_visita = False
        metodos_efectivos_ids = [m.metodo for m in metodos_ejecutados]
        pesos_efectivos = regla.pesos
        observaciones_motor.append("Coherencia metodológica fuerte — semáforo VERDE.")
    
    elif len(metodos_fuera) == 1:
        # Un método se aparta — se desestima y se reconsolida con los demás
        estado = "AMARILLA"
        metodo_fuera = metodos_fuera[0]
        razon_estado = (
            f"El método {metodo_fuera} se aparta más de la tolerancia ({regla.tolerancia_coherencia_pct*100:.0f}%). "
            f"Los demás métodos convergen. El motor desestima {metodo_fuera} y consolida con los métodos restantes "
            f"según regla fallback. Avaluador debe validar la decisión (revisión estimada: 10-15 minutos)."
        )
        requiere_visita = False
        metodos_efectivos_ids = metodos_dentro
        # Construir pesos efectivos: usar fallback si está definido para los dos restantes, si no normalizar
        if set(metodos_efectivos_ids) == set(regla.fallback_dos_metodos.keys()):
            pesos_efectivos = regla.fallback_dos_metodos
        else:
            # Normalizar pesos originales sobre métodos restantes
            suma_pesos_dentro = sum(regla.pesos.get(m, 0) for m in metodos_efectivos_ids)
            pesos_efectivos = {m: regla.pesos.get(m, 0) / suma_pesos_dentro for m in metodos_efectivos_ids}
        observaciones_motor.append(
            f"Método {metodo_fuera} desestimado por divergencia. Reconsolidación con {len(metodos_efectivos_ids)} métodos."
        )
    
    else:
        # Dos o más métodos se apartan — no hay convergencia
        estado = "ROJA"
        razon_estado = (
            f"Múltiples métodos se apartan de la tolerancia. No hay convergencia metodológica. "
            f"El motor recomienda elevar a visita in situ del avaluador para verificación física del activo "
            f"y revisión integral de los insumos. No se consolida automáticamente."
        )
        requiere_visita = True
        metodos_efectivos_ids = [m.metodo for m in metodos_ejecutados]  # Todos, pero sin consolidar
        pesos_efectivos = regla.pesos
        observaciones_motor.append("Divergencia entre métodos — semáforo ROJA. Requiere visita.")
    
    # ============================================================
    # PASO 4: Calcular valor consolidado
    # ============================================================
    if estado == "ROJA":
        # No consolidamos automáticamente — devolvemos rangos amplios
        valores = [m.valor_central_cop for m in metodos_ejecutados]
        bandas_bajas = [m.banda_baja_cop for m in metodos_ejecutados]
        bandas_altas = [m.banda_alta_cop for m in metodos_ejecutados]
        valor_consolidado_cop = int(sum(valores) / len(valores))  # Promedio simple como referencia
        banda_consolidada_baja = min(bandas_bajas)
        banda_consolidada_alta = max(bandas_altas)
    else:
        # Consolidación ponderada
        suma_ponderada = 0.0
        suma_pesos = 0.0
        bandas_bajas_ponderadas = 0.0
        bandas_altas_ponderadas = 0.0
        for m in metodos_ejecutados:
            if m.metodo in metodos_efectivos_ids:
                peso = pesos_efectivos[m.metodo]
                suma_ponderada += m.valor_central_cop * peso
                bandas_bajas_ponderadas += m.banda_baja_cop * peso
                bandas_altas_ponderadas += m.banda_alta_cop * peso
                suma_pesos += peso
        
        valor_consolidado_cop = int(suma_ponderada / suma_pesos)
        banda_consolidada_baja = int(bandas_bajas_ponderadas / suma_pesos)
        banda_consolidada_alta = int(bandas_altas_ponderadas / suma_pesos)
    
    # ============================================================
    # PASO 5: Construir AvaluoConsolidado
    # ============================================================
    consolidado = AvaluoConsolidado(
        predio=predio,
        fecha_calculo=datetime.now().isoformat(),
        metodos_ejecutados=metodos_ejecutados,
        regla_consolidacion=regla,
        distancia_max_observada_pct=distancia_max_pct,
        metodos_efectivos=metodos_efectivos_ids,
        pesos_efectivos=pesos_efectivos,
        valor_consolidado_cop=valor_consolidado_cop,
        banda_consolidada_baja_cop=banda_consolidada_baja,
        banda_consolidada_alta_cop=banda_consolidada_alta,
        estado=estado,
        razon_estado=razon_estado,
        requiere_visita=requiere_visita,
        observaciones_motor=observaciones_motor,
    )
    
    return consolidado


if __name__ == "__main__":
    sys.path.insert(0, '/home/claude/tma_engine/datos')
    from insumos_napoli import (
        PREDIO_NAPOLI_430, COMPARABLES_NAPOLI_MIRAMAR,
        COSTOS_CAMACOL_2026, VALOR_SUELO_MIRAMAR_2026, CANONES_MIRAMAR_2026
    )
    from pieza_1_M1_comparacion_mercado import construir_M1
    from pieza_2_M2_costo_reposicion import construir_M2
    from pieza_3_M3_capitalizacion_rentas import construir_M3
    from contrato_datos import fmt_cop, fmt_m2
    
    print("="*70)
    print("PIEZA 4 — Motor de Consolidación TMA")
    print("="*70)
    
    # Ejecutar los tres métodos
    m1 = construir_M1(PREDIO_NAPOLI_430, COMPARABLES_NAPOLI_MIRAMAR)
    m2 = construir_M2(PREDIO_NAPOLI_430, COSTOS_CAMACOL_2026, VALOR_SUELO_MIRAMAR_2026)
    m3 = construir_M3(PREDIO_NAPOLI_430, CANONES_MIRAMAR_2026)
    
    # Consolidar
    consolidado = consolidar(PREDIO_NAPOLI_430, [m1, m2, m3])
    
    print(f"\n--- Resultados por método ---")
    for m in consolidado.metodos_ejecutados:
        print(f"  {m.metodo} ({m.nombre_metodo}):")
        print(f"     Valor central: {fmt_cop(m.valor_central_cop)} | $/m²: {fmt_m2(m.valor_por_m2_central)}")
        print(f"     Banda 80%:     {fmt_cop(m.banda_baja_cop)} — {fmt_cop(m.banda_alta_cop)}")
    
    print(f"\n--- Consolidación ---")
    print(f"  Distancia máxima entre métodos: {consolidado.distancia_max_observada_pct*100:.2f}%")
    print(f"  Métodos efectivos: {consolidado.metodos_efectivos}")
    print(f"  Pesos efectivos: {consolidado.pesos_efectivos}")
    print(f"\n--- AVALÚO CONSOLIDADO ---")
    print(f"  Valor central:    {fmt_cop(consolidado.valor_consolidado_cop)}")
    print(f"  Banda 80%:        {fmt_cop(consolidado.banda_consolidada_baja_cop)} — {fmt_cop(consolidado.banda_consolidada_alta_cop)}")
    print(f"  $/m² central:     {fmt_m2(int(consolidado.valor_consolidado_cop / PREDIO_NAPOLI_430.area_construida_m2))}")
    print(f"\n  Estado:           {consolidado.estado}  ({'requiere visita' if consolidado.requiere_visita else 'no requiere visita'})")
    print(f"  Hash avalúo:      {consolidado.hash_avaluo[:16]}...")
    print(f"\n  Razón:            {consolidado.razon_estado}")
    
    print(f"\n--- Observaciones del motor ---")
    for o in consolidado.observaciones_motor:
        print(f"  · {o}")

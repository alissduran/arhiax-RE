# -*- coding: utf-8 -*-
"""
ARHIAX RE — Motor de Análisis de Cargas Económicas Hipotecarias
Bloque 3 Sprint 1

Estima el saldo, cuota mensual orientativa y LTV de una hipoteca
a partir de los datos disponibles del CTL y el valor del inmueble.

NOTA: Todos los valores son ESTIMACIONES REFERENCIALES de carácter
automático. No sustituyen análisis financiero por profesional idóneo.
"""

import datetime
from pathlib import Path


# ── Constantes referenciales ──────────────────────────────────────────────────

# Tasa referencial DTF + spread estándar crédito hipotecario NO VIS en Colombia
# Fuente: Banco de la República, promedio 2023-2024
TASA_REFERENCIAL_ANUAL = 0.1250  # 12.50% EA

# LTV típico para crédito hipotecario NO VIS en Colombia
LTV_TIPICO = 0.70  # 70% del valor del inmueble

# Plazo estándar crédito hipotecario NO VIS
PLAZO_TIPICO_ANOS = 20


def _tasa_mensual(tasa_anual_ea):
    """Convierte tasa efectiva anual (EA) a tasa efectiva mensual."""
    return (1 + tasa_anual_ea) ** (1 / 12) - 1


def _cuota_pago_igual(capital, tasa_mensual, n_cuotas):
    """Calcula la cuota mensual de amortización por el método francés (pago igual).
    
    Args:
        capital:      Saldo inicial del crédito.
        tasa_mensual: Tasa efectiva mensual (decimal).
        n_cuotas:     Número total de cuotas.
    
    Returns:
        Cuota mensual fija.
    """
    if n_cuotas <= 0:  # M-06: proteger división por cero con plazo 0
        return 0
    if tasa_mensual == 0:
        return capital / n_cuotas
    return capital * (tasa_mensual * (1 + tasa_mensual) ** n_cuotas) / \
           ((1 + tasa_mensual) ** n_cuotas - 1)


def _saldo_en_periodo(capital, tasa_mensual, n_cuotas, cuotas_pagadas):
    """Calcula el saldo insoluto del crédito después de N cuotas pagadas."""
    cuota = _cuota_pago_igual(capital, tasa_mensual, n_cuotas)
    saldo = capital
    for _ in range(cuotas_pagadas):
        saldo = saldo * (1 + tasa_mensual) - cuota
    return max(0, saldo)


def estimar_carga_hipotecaria(
    valor_inmueble,
    fecha_constitucion,
    plazo_anos=None,
    tasa_anual=None,
    capital_original=None,
):
    """Estima la carga económica de un gravamen hipotecario.

    Args:
        valor_inmueble:     Valor referencial del inmueble en COP.
        fecha_constitucion: Fecha de constitución del gravamen (str 'YYYY-MM-DD'
                            o 'DD-MM-YYYY') o None.
        plazo_anos:         Plazo original del crédito en años. Si es None,
                            usa PLAZO_TIPICO_ANOS.
        tasa_anual:         Tasa efectiva anual decimal. Si es None,
                            usa TASA_REFERENCIAL_ANUAL.
        capital_original:   Capital original del crédito. Si es None,
                            se estima como valor_inmueble × LTV_TIPICO.

    Returns:
        Dict con:
            capital_estimado:           Capital original estimado en COP.
            saldo_estimado:             Saldo insoluto estimado en COP.
            cuota_mensual_orientativa:  Cuota mensual en COP.
            ltv_estimado:               LTV = saldo / valor_inmueble.
            plazo_original_anos:        Plazo original usado.
            plazo_restante_anos:        Plazo restante estimado.
            cuotas_pagadas:             Cuotas estimadas pagadas.
            tasa_anual_usada:           Tasa anual usada (decimal).
            es_estimacion:              True siempre (recordatorio).
            advertencia:                Texto de disclaimer.
    """
    # M-06: validación de inputs (evita TypeError con None y división por cero).
    # 03F: UNKNOWN != ZERO. Sin valor inmobiliario habilitado NO se fabrica $0
    # (que parecería una deuda real): se devuelve available=False con campos None.
    _valor_ok = isinstance(valor_inmueble, (int, float)) and valor_inmueble > 0
    _capital_ok = isinstance(capital_original, (int, float)) and capital_original > 0

    if not isinstance(plazo_anos, (int, float)) or plazo_anos <= 0:
        plazo_anos = None
    if tasa_anual is not None and (
        not isinstance(tasa_anual, (int, float)) or not (0 < tasa_anual <= 1)
    ):
        # Descartar tasas absurdas (p. ej. 12.5 en vez de 0.125)
        tasa_anual = None

    tasa_ea = tasa_anual if tasa_anual is not None else TASA_REFERENCIAL_ANUAL
    plazo = plazo_anos if plazo_anos is not None else PLAZO_TIPICO_ANOS

    if not _valor_ok and not _capital_ok:
        # UNKNOWN: sin valor del inmueble ni cuantía del CTL -> nada estimable.
        return {
            "available": False,
            "capital_estimado": None,
            "saldo_estimado": None,
            "cuota_mensual_orientativa": None,
            "ltv_estimado": None,
            "plazo_original_anos": plazo,
            "plazo_restante_anos": None,
            "cuotas_pagadas": 0,
            "tasa_anual_usada": tasa_ea,
            "es_estimacion": True,
            "advertencia": ("No existe una estimación de valor inmobiliario "
                            "habilitada para esta ejecución."),
        }

    valor = valor_inmueble if _valor_ok else 0.0
    capital = capital_original if _capital_ok else int(valor * LTV_TIPICO)

    n_cuotas_total = plazo * 12
    tm = _tasa_mensual(tasa_ea)

    # Calcular cuotas pagadas a la fecha de hoy
    cuotas_pagadas = 0
    plazo_restante = plazo
    if fecha_constitucion:
        try:
            # Intentar ambos formatos de fecha
            for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
                try:
                    fecha_dt = datetime.datetime.strptime(
                        str(fecha_constitucion).strip(), fmt
                    )
                    break
                except ValueError:
                    continue
            else:
                fecha_dt = None

            if fecha_dt:
                hoy = datetime.datetime.today()
                delta_meses = (hoy.year - fecha_dt.year) * 12 + \
                              (hoy.month - fecha_dt.month)
                cuotas_pagadas = min(max(0, delta_meses), n_cuotas_total)
                plazo_restante = max(0, (n_cuotas_total - cuotas_pagadas) / 12)
        except Exception:
            pass

    saldo = _saldo_en_periodo(capital, tm, n_cuotas_total, cuotas_pagadas)
    cuota = _cuota_pago_igual(capital, tm, n_cuotas_total)
    # LTV requiere el valor del inmueble: sin él es NO CALCULABLE (no 0%).
    ltv = saldo / valor if _valor_ok else None

    return {
        "available": True,
        "capital_estimado": int(round(capital, -3)),
        "saldo_estimado": int(round(saldo, -3)),
        "cuota_mensual_orientativa": int(round(cuota, -3)),
        "ltv_estimado": round(ltv, 4) if ltv is not None else None,
        "plazo_original_anos": plazo,
        "plazo_restante_anos": round(plazo_restante, 1),
        "cuotas_pagadas": cuotas_pagadas,
        "tasa_anual_usada": tasa_ea,
        "es_estimacion": True,
        "advertencia": (
            "Los valores de saldo, cuota y LTV son ESTIMACIONES REFERENCIALES "
            "de carácter automático basadas en supuestos típicos del mercado "
            "hipotecario colombiano (Ley 546/1999). No sustituyen análisis "
            "financiero por el banco acreedor ni extracto oficial del crédito."
        ),
    }


def generar_tabla_carga(resultado, fmt_cop):
    """Genera una lista de filas para la tabla de Sección 04C del PDF.

    Args:
        resultado: Dict retornado por estimar_carga_hipotecaria().
        fmt_cop:   Función de formato COP (ej. lambda v: f'$ {v:,.0f}').

    Returns:
        List of (label, valor) tuples para data_table().
    """
    # 03F: UNKNOWN != ZERO. Sin base de valor se declara NO ESTIMABLE / NO
    # CALCULABLE, nunca $0 (que parecería una deuda real de cero).
    if resultado.get("available") is False:
        return [
            ("Capital estimado del crédito", "NO ESTIMABLE"),
            ("Saldo insoluto estimado (hoy)", "NO ESTIMABLE"),
            ("Cuota mensual orientativa", "NO ESTIMABLE"),
            ("LTV estimado", "NO CALCULABLE"),
            ("Motivo", resultado.get("advertencia") or "valor inmobiliario no disponible"),
        ]

    def _fmt(v):
        return "NO ESTIMABLE" if v is None else f"{fmt_cop(v)} COP"

    _ltv = resultado.get("ltv_estimado")
    ltv_txt = ("NO CALCULABLE" if _ltv is None else
               f"{_ltv * 100:.1f}% — " + (
                   "ALTO RIESGO (>80%)" if _ltv > 0.80 else
                   "MODERADO (60-80%)" if _ltv > 0.60 else
                   "BAJO (<60%)"))
    return [
        ("Capital estimado del crédito",
         _fmt(resultado["capital_estimado"]) + (f" (LTV típico {LTV_TIPICO*100:.0f}%)"
                                                 if resultado.get("capital_estimado") is not None else "")),
        ("Saldo insoluto estimado (hoy)", _fmt(resultado["saldo_estimado"])),
        ("Cuota mensual orientativa", _fmt(resultado["cuota_mensual_orientativa"])),
        ("LTV estimado", ltv_txt),
        ("Tasa de referencia usada",
         f"{resultado['tasa_anual_usada']*100:.2f}% EA (referencial DTF+spread)"),
        ("Plazo original / Cuotas pagadas",
         f"{resultado['plazo_original_anos']} años / {resultado['cuotas_pagadas']} cuotas"),
        ("Plazo restante estimado",
         f"{resultado['plazo_restante_anos']:.1f} años"),
        ("Naturaleza de la estimación",
         "REFERENCIAL AUTOMÁTICA — No sustituye extracto oficial del acreedor"),
    ]

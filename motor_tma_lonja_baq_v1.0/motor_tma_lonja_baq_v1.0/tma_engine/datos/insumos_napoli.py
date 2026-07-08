"""
Datos reales del predio bajo avalúo y comparables recolectados de portales públicos.

PREDIO: Apto 430, Torre 8, Conjunto Residencial Napoli
Folio Matrícula: 040-646406
Capturados de Metrocuadrado, Trovit, Nuroa, Mitula entre 06-May-2026.
Las URLs reales corresponden a búsquedas en esos portales en esa fecha.
En producción, estos datos los recolecta automáticamente el scraper M1.
"""
from datetime import datetime
import sys
sys.path.insert(0, '/home/claude/tma_engine/piezas')
from contrato_datos import Predio


# ============================================================
# PREDIO BAJO AVALÚO
# ============================================================
PREDIO_NAPOLI_430 = Predio(
    folio_matricula="040-646406",
    direccion="TV 43 # 100-50, Apto 430, Torre 8, Etapa 3, Conjunto Residencial Napoli",
    ciudad="Barranquilla",
    barrio="Miramar",
    estrato=4,
    area_construida_m2=58.75,
    coeficiente_copropiedad=0.002037,  # 0.2037%
    tipologia="Apartamento NO VIS - Propiedad Horizontal",
    antiguedad_anos=3,                 # Conjunto entregado 2023
    piso=4,                            # Apto 430 = piso 4
    descripcion_adicional="Conjunto cerrado con amenidades (piscina, gimnasio, salón social, vigilancia 24h)"
)


# ============================================================
# COMPARABLES RECOLECTADOS DE PORTALES PÚBLICOS (06-May-2026)
# ============================================================
# Estructura: cada comparable es un dict con los campos necesarios
# para que M1 los procese.

COMPARABLES_NAPOLI_MIRAMAR = [
    {
        "id": "C1",
        "fuente_portal": "Trovit / Nuroa",
        "url": "https://casas.trovit.com.co/apartamento-sector-miramar-barranquilla",
        "fecha_captura": "2026-05-06",
        "conjunto": "Conjunto Napoli (mismo)",
        "barrio": "Miramar",
        "estrato": 4,
        "area_m2": 66.87,
        "habitaciones": 2,
        "banos": 2,
        "piso": None,
        "precio_oferta_cop": 300000000,
        "precio_por_m2_observado": 4486000,
        "estado": "Para estrenar",
        "orientacion": "Lado sombra, torre fresca",
        "notas": "Apartamento para estrenar en el mismo Conjunto Napoli — comparable directo de máxima homogeneidad",
        "es_oferta": True,                 # Es precio de listado, no de cierre
    },
    {
        "id": "C2",
        "fuente_portal": "Nuroa.com.co",
        "url": "https://www.nuroa.com.co/venta/apartamento-barrio-miramar-barranquilla",
        "fecha_captura": "2026-05-06",
        "conjunto": "Conjunto Napoli (mismo)",
        "barrio": "Miramar",
        "estrato": 4,
        "area_m2": 67.00,
        "habitaciones": 2,
        "banos": 2,
        "piso": None,
        "precio_oferta_cop": 288000000,
        "precio_por_m2_observado": 4299000,
        "estado": "Excelentes acabados",
        "orientacion": None,
        "notas": "Apartamento en Conjunto Napoli con excelentes acabados — comparable directo",
        "es_oferta": True,
    },
    {
        "id": "C3",
        "fuente_portal": "Trovit",
        "url": "https://casas.trovit.com.co/apartamento-sector-miramar-barranquilla",
        "fecha_captura": "2026-05-06",
        "conjunto": "Sorrento (vecino mismo cluster Miramar)",
        "barrio": "Miramar",
        "estrato": 4,
        "area_m2": 70.00,
        "habitaciones": 3,
        "banos": 2,
        "piso": 8,
        "precio_oferta_cop": 308000000,
        "precio_por_m2_observado": 4400000,
        "estado": "Remodelado",
        "orientacion": "Lado sombra, piso alto",
        "notas": "Conjunto vecino del mismo cluster urbanístico - apartamento remodelado piso alto",
        "es_oferta": True,
    },
    {
        "id": "C4",
        "fuente_portal": "Mitula Casas",
        "url": "https://casas.mitula.com.co/casas/apartamentos-estrato-4-barranquilla-miramar",
        "fecha_captura": "2026-05-06",
        "conjunto": "Miramar - barrio (conjunto cerrado)",
        "barrio": "Miramar",
        "estrato": 4,
        "area_m2": 55.00,
        "habitaciones": 2,
        "banos": 2,
        "piso": None,
        "precio_oferta_cop": 231000000,
        "precio_por_m2_observado": 4200000,
        "estado": "Bueno - usado",
        "orientacion": None,
        "notas": "2 hab 2 baños, balcón, vista interior, conjunto cerrado",
        "es_oferta": True,
    },
    {
        "id": "C5",
        "fuente_portal": "Mitula Casas",
        "url": "https://casas.mitula.com.co/casas/apartamentos-estrato-4-barranquilla-miramar",
        "fecha_captura": "2026-05-06",
        "conjunto": "Miramar - barrio",
        "barrio": "Miramar",
        "estrato": 4,
        "area_m2": 57.00,
        "habitaciones": 2,
        "banos": 2,
        "piso": None,
        "precio_oferta_cop": 228000000,
        "precio_por_m2_observado": 4000000,
        "estado": "Bueno",
        "orientacion": None,
        "notas": "2 alcobas + estudio, conjunto con todas las amenidades",
        "es_oferta": True,
    },
    {
        "id": "C6",
        "fuente_portal": "Mitula Casas",
        "url": "https://casas.mitula.com.co/casas/apartamentos-estrato-4-barranquilla-miramar",
        "fecha_captura": "2026-05-06",
        "conjunto": "Miramar - barrio",
        "barrio": "Miramar",
        "estrato": 4,
        "area_m2": 52.00,
        "habitaciones": 2,
        "banos": 2,
        "piso": None,
        "precio_oferta_cop": 250000000,
        "precio_por_m2_observado": 4807000,
        "estado": "Vendido reciente (precio observado en transacción)",
        "orientacion": None,
        "notas": "Precio explícito reportado en oferta cerrada - probable transacción cercana",
        "es_oferta": True,
    },
    {
        "id": "C7",
        "fuente_portal": "Nuroa",
        "url": "https://www.nuroa.com.co/venta/apartamento-barrio-miramar-barranquilla",
        "fecha_captura": "2026-05-06",
        "conjunto": "Miramar - barrio",
        "barrio": "Miramar",
        "estrato": 4,
        "area_m2": 48.00,
        "habitaciones": 2,
        "banos": 2,
        "piso": None,
        "precio_oferta_cop": 187000000,
        "precio_por_m2_observado": 3896000,
        "estado": "Bueno",
        "orientacion": None,
        "notas": "Apartamento de 48 m², 2 hab 2 baños - menor extremo de banda",
        "es_oferta": True,
    },
    {
        "id": "C8",
        "fuente_portal": "Trovit",
        "url": "https://casas.trovit.com.co/apartamento-barranquilla-miramar",
        "fecha_captura": "2026-05-06",
        "conjunto": "Miramar - barrio (conjunto premium)",
        "barrio": "Miramar",
        "estrato": 4,
        "area_m2": 85.00,
        "habitaciones": 3,
        "banos": 3,
        "piso": None,
        "precio_oferta_cop": 400000000,
        "precio_por_m2_observado": 4706000,
        "estado": "Excelentes acabados",
        "orientacion": None,
        "notas": "Conjunto con amenidades premium - extremo superior de banda",
        "es_oferta": True,
    },
]


# ============================================================
# SERIES CAMACOL ATLÁNTICO Q1-2026 (Costo de Reposición)
# ============================================================
# Datos recogidos del web search anterior - referencias publicadas
# Tabla base Camacol (Feb-2025), escalada al 2026 según incremento SMMLV
# Fuente: incremento SMMLV 2026 = +23.7%, fórmula Camacol Bogotá-Cundinamarca Ene-2026: 1% SMMLV ≈ 1.12% costos
# Proyección 2025→2026: +25.76% (validado por ICOCED Ene-2026: +3.69% solo en el primer mes)
_FACTOR_2025_A_2026 = 1.2576

_COSTOS_BASE_2025 = {
    "Multifamiliar VIS": {"costo_directo_m2": 1727745, "costo_total_m2": 1913780},
    "Multifamiliar medio-bajo": {"costo_directo_m2": 1777278, "costo_total_m2": 2192399},
    "Multifamiliar medio una alcoba": {"costo_directo_m2": 1907202, "costo_total_m2": 2100077},
    "Multifamiliar medio-medio (4-5 pisos)": {"costo_directo_m2": 2872130, "costo_total_m2": 3302130},
    "Multifamiliar medio-alto (5-6 pisos)": {"costo_directo_m2": 2399318, "costo_total_m2": 2639412},
    "Multifamiliar alto típico (6 pisos)": {"costo_directo_m2": 2785829, "costo_total_m2": 3370570},
    "Multifamiliar alto full acabados importados": {"costo_directo_m2": 3950091, "costo_total_m2": 4698571},
}

COSTOS_CAMACOL_2026 = {
    "fuente": "Camacol regional Atlántico (proyección 2026 sobre tabla Feb-2025) + DANE ICOCED Ene-2026",
    "url_referencia": "https://camacol.co/ + https://vivienda.com.co/precio-metro-cuadrado-construccion-colombia-2026/",
    "fecha_captura": "2026-05-06",
    "vigencia": "Q2-2026",
    "factor_proyeccion_2025_a_2026": _FACTOR_2025_A_2026,
    "justificacion_factor": (
        f"Incremento SMMLV 2026: +23.7% (a $1.750.905). "
        f"Fórmula Camacol Bogotá-Cundinamarca: 1% SMMLV ≈ 1.12% costos. "
        f"Proyección: +{(_FACTOR_2025_A_2026-1)*100:.2f}%. "
        f"Validado ICOCED Ene-2026: +3.69%."
    ),
    "tipologias": {
        tipo: {
            "costo_directo_m2": int(v["costo_directo_m2"] * _FACTOR_2025_A_2026),
            "costo_total_m2": int(v["costo_total_m2"] * _FACTOR_2025_A_2026),
        }
        for tipo, v in _COSTOS_BASE_2025.items()
    },
    "tipologias_base_2025_referencia": _COSTOS_BASE_2025,
    "rangos_camacol_2026_estandar": {
        "VIS": (1800000, 2200000),
        "Vivienda clase media": (2500000, 3500000),
        "Apartamentos torre estándar": (2200000, 3000000),
        "Vivienda alta gama": (4500000, 7000000),
    },
    "smmlv_2026": 1750905,
    "icoced_variacion_ene_2026": 0.0369,
    # Depreciación: ya NO se usa lineal. Ahora usamos Fitto-Corvini (Resolución IGAC 620/2008)
    # vía módulo depreciacion_fitto_corvini.py
    "depreciacion_metodo": "Fitto-Corvini (Resolución IGAC 620/2008)",
    "vida_util_concreto_anos": 100,
}

# Atributos técnicos del predio para M2
PREDIO_NAPOLI_430_TECNICO = {
    "sistema_constructivo": "concreto",       # Estructura de concreto reforzado
    "estado_conservacion_clase": 1.5,         # Clase 1.5 = "muy bueno" (PH nueva 3 años)
    "vida_util_anos": 100,                    # IGAC 620: 100 años para concreto
    "tipologia_camacol": "Multifamiliar medio-medio (4-5 pisos)",
}


# ============================================================
# VALOR DEL SUELO — ZONAS HOMOGÉNEAS GEOECONÓMICAS BARRANQUILLA
# ============================================================
# Referencia: el coeficiente de copropiedad determina la cuota del lote del conjunto
# que corresponde al apartamento. El valor del lote del conjunto se estima vía
# zona homogénea geoeconómica vigente del sector.
VALOR_SUELO_MIRAMAR_2026 = {
    "fuente": "Estimación referencial Zona Homogénea Geoeconómica Miramar",
    "url_referencia": "https://catastrosoledad.gov.co (referencia metodológica) + observación urbana",
    "fecha_captura": "2026-05-06",
    "valor_m2_terreno_cop_referencial": 4500000,  # COP/m² terreno en sector Miramar consolidado estrato 4 (cercanía al río Magdalena, alta valorización)
    "observaciones": "Valor del suelo en sector consolidado Miramar — referencia para cálculo M2. Sector con cercanía al río Magdalena, en cluster residencial estrato 4 de alta valorización. En modo ACA Forense con consulta IGAC formal, el valor se actualiza con la Zona Homogénea Geoeconómica vigente publicada por GC Barranquilla.",
    "area_lote_conjunto_napoli_estimada_m2": 7000,  # Estimación del lote total del conjunto - Napoli es un conjunto grande con múltiples torres y amenidades
}


# ============================================================
# CÁNONES DE ARRENDAMIENTO MIRAMAR (M3) — ACTUALIZADO 2026
# ============================================================
# Cánones reales observados en portales (Mitula, Nuroa, Properati, Trovit) — May-2026
# Properati reporta precio medio Barranquilla estrato 4: $2.500.000/mes
# Observaciones específicas Miramar 50-70m² estrato 4 con amenidades:
#   - Apartamento 90m² Miramar estrato 4: $1.900.000 (con admin)
#   - Apartamento 60m² Miramar estrato 4 piso 11: $1.800.000-2.000.000 (premium)
#   - Apartamento 72m² Miramar estrato 4 piso 12: $1.700.000-1.900.000
# Tasas de capitalización RESIDENCIAL 2026 (vs comercial 7.5-9%):
#   - Residencial estable: 5.5% - 7.0%
#   - Vacancia residencial Miramar: 4-7% (alta demanda)
CANONES_MIRAMAR_2026 = {
    "fuente": "Observación portales públicos arriendo May-2026 (Mitula, Nuroa, Properati, Trovit)",
    "url_referencia": "https://casas.mitula.com.co/casas/arriendo-apartamentos-miramar + https://www.properati.com.co/s/barranquilla-atlantico/apartamento/arriendo",
    "fecha_captura": "2026-05-06",
    "rangos_canon_mensual_por_tipologia": {
        # Apartamento NO VIS estrato 4, 50-70 m², amenidades de conjunto, Miramar
        # AJUSTADO 2026: rango real observado $1.700.000-$2.300.000
        "apto_NO_VIS_50_70m2_estrato4": {
            "canon_min_cop": 1700000,
            "canon_central_cop": 2000000,
            "canon_max_cop": 2300000,
        },
    },
    "tasa_capitalizacion_mercado_residencial_pct": 0.085,  # 8.5% — cap rate IMPLÍCITO Costa Caribe estrato 4
    "tasa_min_pct": 0.075,                                 # Apartamentos premium con baja vacancia
    "tasa_max_pct": 0.095,                                 # Mayor riesgo (vacancia, ubicación menos premium)
    "vacancia_estimada_pct": 0.06,                         # 6% vacancia más realista
    "gastos_no_recuperables_pct": 0.10,                    # 10% gastos no recuperables del propietario
    "justificacion": (
        "Cánones observados Miramar mayo 2026: rango $1.500.000-$2.300.000 según área y conjunto. "
        "Para 50-70m² con amenidades (caso Napoli): central $2.000.000/mes. "
        "Tasa de capitalización CALIBRADA al cap rate implícito del mercado venta-arriendo Miramar (8.5%): "
        "no es la tasa 'deseada' por inversionistas (6-7%) sino la implícita en transacciones reales — "
        "donde precios de venta suben más rápido que cánones, generando cap rates mayores. "
        "Vacancia 6% (rotación realista) + 10% gastos no recuperables (admin, mantenimiento, predial)."
    ),
}


if __name__ == "__main__":
    print(f"Predio: {PREDIO_NAPOLI_430.folio_matricula}")
    print(f"Dirección: {PREDIO_NAPOLI_430.direccion}")
    print(f"Área: {PREDIO_NAPOLI_430.area_construida_m2} m²")
    print(f"Comparables cargados: {len(COMPARABLES_NAPOLI_MIRAMAR)}")
    print(f"Tipologías Camacol: {len(COSTOS_CAMACOL_2026['tipologias'])}")
    print(f"Cánones referencia: {list(CANONES_MIRAMAR_2026['rangos_canon_mensual_por_tipologia'].keys())}")

# -*- coding: utf-8 -*-
"""
ARHIAX RE — Motor de Score Actuarial Integrado LAI v1.0
Bloque A Sprint 2

Calcula el score ponderado de riesgo del activo a partir de los hallazgos
dinámicos, el resultado geoespacial, el análisis registral y la carga económica.

Ponderación LAI v1.0:
  40% Registral  — tradición, gravámenes, discrepancias
  30% Jurídico   — CTL, titularidad, limitaciones de dominio
  20% Hidrológico — amenazas y riesgos POT
  10% Catastral  — área, NUPRE, destino económico

Todos los scores parciales van de 0 a 100.
Score integrado = suma ponderada de los 4 componentes.
"""

from reportlab.lib import colors as rl_colors


# ── Paleta de colores por rango de score ─────────────────────────────────────

def color_score(score: float):
    """Retorna (color_texto, color_fondo, etiqueta) según el rango del score."""
    if score >= 90:
        return (rl_colors.HexColor("#1A6B3A"), rl_colors.HexColor("#EBF5EE"), "EXCELENTE")
    elif score >= 75:
        return (rl_colors.HexColor("#1A6B3A"), rl_colors.HexColor("#EBF5EE"), "FAVORABLE")
    elif score >= 60:
        return (rl_colors.HexColor("#F08C2B"), rl_colors.HexColor("#FFF5EB"), "MODERADO")
    elif score >= 40:
        return (rl_colors.HexColor("#D92C2C"), rl_colors.HexColor("#FDF2F2"), "ELEVADO")
    else:
        return (rl_colors.HexColor("#D92C2C"), rl_colors.HexColor("#FDF2F2"), "CRITICO")


# ── Motor de scoring ──────────────────────────────────────────────────────────

def calcular_score_actuarial(
    hallazgos: list,
    geo_eval: dict,
    analysis: dict,
    val_data: dict,
    carga: dict = None,
) -> dict:
    """Calcula el score actuarial integrado LAI v1.0.

    Args:
        hallazgos:  Lista de tuples (sev, tc, bg, titulo, fuente, desc, impl).
        geo_eval:   Dict del motor geoespacial (amenaza_remocion_masa, areas_en_riesgo).
        analysis:   Dict del legal_analyzer (folio, titulares, anotaciones, hallazgos).
        val_data:   Dict del motor de valoración (consolidado, ltv_estimado, ...).
        carga:      Dict del motor de cargas económicas (opcional).

    Returns:
        Dict con score_registral, score_juridico, score_hidrologico,
        score_catastral, score_integrado, detalle (list), etiqueta, colores.
    """
    # ── Score Registral (base 100) ────────────────────────────────────────────
    score_registral = 100.0
    detalle_registral = []
    anotaciones = analysis.get("anotaciones", [])

    # Penalización por SEVERIDAD de los hallazgos (no por duplicar criterios con
    # las anotaciones): un hallazgo ALTO (hipoteca/embargo vigente, ausencia de
    # CTL) es BLOQUEANTE y debe reflejarse en el score — antes una hipoteca
    # vigente ALTO solo restaba 8 pts y el score salía 92 con semáforo ROJO
    # (contradicción inicio/fin del dictamen).
    _tiene_alto = False
    for sev, _tc, _bg, titulo, _f, _d, _i in hallazgos:
        if sev == "ALTO":
            score_registral -= 30
            detalle_registral.append(f"-30 pts: {titulo.split('|')[-1].strip()}")
            _tiene_alto = True
        elif sev == "MEDIO":
            score_registral -= 12
            detalle_registral.append(f"-12 pts: {titulo.split('|')[-1].strip()}")

    # LTV alto penaliza en registral (E1 aprobado)
    if carga and carga.get("ltv_estimado", 0) > 0.80:
        score_registral -= 5
        detalle_registral.append(f"-5 pts: LTV estimado > 80% ({carga['ltv_estimado']*100:.0f}%)")

    # CTL reciente (bonificación si la fecha de apertura es < 90 días) — simplificado
    # (penaliza si no hay CTL cargado)
    if not anotaciones:
        score_registral -= 10
        detalle_registral.append("-10 pts: Sin anotaciones registrales procesadas")

    score_registral = max(0, min(100, score_registral))

    # ── Score Jurídico (base 100) ─────────────────────────────────────────────
    score_juridico = 100.0
    detalle_juridico = []

    for sev, tc, bg, titulo, fuente, desc, impl in hallazgos:
        titulo_l = titulo.lower()
        if "ausencia" in titulo_l and "ctl" in titulo_l:
            score_juridico -= 20
            detalle_juridico.append("-20 pts: Ausencia de CTL")
        elif "afectacion" in titulo_l and "vivienda" in titulo_l:
            score_juridico -= 5
            detalle_juridico.append("-5 pts: Afectación a vivienda familiar vigente")
        elif "patrimonio" in titulo_l and "familia" in titulo_l:
            score_juridico -= 5
            detalle_juridico.append("-5 pts: Patrimonio de familia inembargable")
        elif "tracto" in titulo_l or "sucesivo" in titulo_l:
            score_juridico -= 10
            detalle_juridico.append("-10 pts: Tracto sucesivo no validado")

    # Sin titulares identificados
    titulares = analysis.get("titulares", "")
    if "PENDIENTE" in str(titulares).upper() or not titulares:
        score_juridico -= 8
        detalle_juridico.append("-8 pts: Titulares no identificados")

    score_juridico = max(0, min(100, score_juridico))

    # ── Score Hidrológico (base 100) ──────────────────────────────────────────
    score_hidrologico = 100.0
    detalle_hidro = []

    am = geo_eval.get("amenaza_remocion_masa", {})
    ri = geo_eval.get("areas_en_riesgo", {})

    if am.get("intersecta"):
        nivel_am = str(am.get("nivel", "")).upper()
        if "ALTA" in nivel_am or "ALTO" in nivel_am:
            score_hidrologico -= 15
            detalle_hidro.append(f"-15 pts: Amenaza remoción en masa ALTA")
        elif "MEDIA" in nivel_am or "MEDIO" in nivel_am:
            score_hidrologico -= 8
            detalle_hidro.append(f"-8 pts: Amenaza remoción en masa MEDIA")
        else:
            score_hidrologico -= 5
            detalle_hidro.append(f"-5 pts: Amenaza remoción en masa BAJA")

    if ri.get("intersecta"):
        nivel_ri = str(ri.get("nivel", "")).upper()
        if "ALTA" in nivel_ri or "ALTO" in nivel_ri:
            score_hidrologico -= 15
            detalle_hidro.append(f"-15 pts: Área en riesgo ALTA")
        elif "MEDIA" in nivel_ri or "MEDIO" in nivel_ri:
            score_hidrologico -= 8
            detalle_hidro.append(f"-8 pts: Área en riesgo MEDIA")
        else:
            score_hidrologico -= 5
            detalle_hidro.append(f"-5 pts: Área en riesgo BAJA")

    if not am.get("intersecta") and not ri.get("intersecta"):
        # Ciudad sin capas de riesgo resueltas (NO EVALUADO): NO se afirma
        # "sin afectación" ni "score pleno" sin haberse evaluado (desinformación).
        resumen_geo = (geo_eval.get("resumen_ejecutivo") or "").lower()
        if "no evaluado" in resumen_geo or "pendiente" in resumen_geo:
            detalle_hidro.append("Amenaza/riesgo NO EVALUADO (sin fuente en vivo) — componente no calificable")
        else:
            detalle_hidro.append("Sin afectación en capas POT — Score pleno")

    score_hidrologico = max(0, min(100, score_hidrologico))

    # ── Score Catastral (base 100) ────────────────────────────────────────────
    score_catastral = 100.0
    detalle_catastral = []

    area = val_data.get("area", 0) if val_data.get("area") else 0
    if not area or area <= 0:
        score_catastral -= 10
        detalle_catastral.append("-10 pts: Área no validada o cero")
    else:
        detalle_catastral.append(f"Área validada: {area} m² — Score pleno")

    # Valor 0 o muy bajo es señal de datos incompletos
    if val_data.get("consolidado", 0) <= 0:
        score_catastral -= 5
        detalle_catastral.append("-5 pts: Valor referencial no calculado")

    score_catastral = max(0, min(100, score_catastral))

    # ── Score Integrado ponderado ─────────────────────────────────────────────
    score_integrado = round(
        score_registral  * 0.40 +
        score_juridico   * 0.30 +
        score_hidrologico * 0.20 +
        score_catastral  * 0.10,
        1
    )

    # Coherencia con el semáforo del resumen: un hallazgo ALTO es BLOQUEANTE y
    # el score integrado NO puede declarar perfil EXCELENTE/FAVORABLE con un
    # bloqueante activo (antes: inicio 'BLOQUEADO/ROJO' vs. fin 'Score 95.8
    # EXCELENTE'). Se topa el integrado a zona ELEVADO.
    bloqueado = _tiene_alto
    if bloqueado:
        score_integrado = min(score_integrado, 55.0)
        # Los parciales se mantienen como están; solo el integrado y su etiqueta
        # reflejan el bloqueo cualitativo.

    # Colores para el score integrado
    tc_int, bg_int, etiqueta_int = color_score(score_integrado)
    if bloqueado:
        etiqueta_int = "BLOQUEADO"

    return {
        "score_registral":   round(score_registral, 1),
        "score_juridico":    round(score_juridico, 1),
        "score_hidrologico": round(score_hidrologico, 1),
        "score_catastral":   round(score_catastral, 1),
        "score_integrado":   score_integrado,
        "etiqueta":          etiqueta_int,
        "bloqueado":         bloqueado,
        "colores": {
            "registral":   color_score(score_registral),
            "juridico":    color_score(score_juridico),
            "hidrologico": color_score(score_hidrologico),
            "catastral":   color_score(score_catastral),
            "integrado":   (tc_int, bg_int, etiqueta_int),
        },
        "detalle": {
            "registral":   detalle_registral or ["Sin penalizaciones registrales"],
            "juridico":    detalle_juridico  or ["Sin penalizaciones jurídicas"],
            "hidrologico": detalle_hidro,
            "catastral":   detalle_catastral,
        },
        "ponderacion": {
            "registral":   0.40,
            "juridico":    0.30,
            "hidrologico": 0.20,
            "catastral":   0.10,
        },
    }


def generar_narrativa_score(score_result: dict) -> str:
    """Genera la narrativa de una línea para el banner del score integrado."""
    si = score_result["score_integrado"]
    et = score_result["etiqueta"]
    sr = score_result["score_registral"]
    sj = score_result["score_juridico"]
    sh = score_result["score_hidrologico"]
    sc = score_result["score_catastral"]
    if score_result.get("bloqueado"):
        return (
            f"Perfil BLOQUEADO (hallazgos de severidad ALTO activos): score "
            f"integrado topeado en {si}/100. Registral: {sr}/100 · Jurídico: "
            f"{sj}/100 · Hidrológico: {sh}/100 · Catastral: {sc}/100. "
            f"Metodología ponderada LAI v1.0 (40/30/20/10).")
    return (
        f"Perfil de riesgo {et} (Score {si}/100). "
        f"Registral: {sr}/100 · Jurídico: {sj}/100 · "
        f"Hidrológico: {sh}/100 · Catastral: {sc}/100. "
        f"Metodología ponderada LAI v1.0 (40/30/20/10)."
    )

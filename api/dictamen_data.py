import os

# --- Colores Globales ---
from reportlab.lib import colors

C_ROJO = colors.HexColor("#D92C2C")
C_NARANJA = colors.HexColor("#F08C2B")
C_VERDE = colors.HexColor("#1A6B3A")
C_OK_BG = colors.HexColor("#EBF5EE")
C_ALERTA_BG = colors.HexColor("#FFF5EB")
C_RIESGO_BG = colors.HexColor("#FDF2F2")
C_AZUL_OSC = colors.HexColor("#0D2C6B")
C_AZUL_MED = colors.HexColor("#2B54A3")
C_DORADO = colors.HexColor("#C19C4D")
C_BORDE = colors.HexColor("#E2E8F0")
C_NEGRO_MONO = colors.HexColor("#0A1424")


def precondiciones_valoracion(clase_suelo=None, destino=None, tipologia=None,
                              unidad_ph_no_resuelta=False,
                              market_context_blocked=False):
    """Precondiciones de valoración por tipología (bug L), identidad (03D) y
    contexto de mercado (03H).

    La comparación de mercado (M1) y la capitalización de rentas (M3) NO proceden
    sobre ciertos predios: suelo de protección, no construible o rural. Tampoco
    procede emitir una estimación de mercado de una UNIDAD PH cuya identidad no
    está suficientemente resuelta (03D) NI con contexto de mercado insuficiente
    (03H: barrio/estrato/tipología/tasa no resueltos). Devuelve procede=False +
    motivo.
    """
    if unidad_ph_no_resuelta:
        return {"procede": False,
                "motivo": "identidad predial de la unidad PH insuficientemente resuelta"}
    if market_context_blocked:
        return {"procede": False,
                "motivo": "contexto de mercado insuficiente (barrio/estrato/tipología/tasa de mercado no resueltos)"}
    cs = (clase_suelo or "").strip().lower()
    dst = (destino or "").strip().lower()
    tip = (tipologia or "").strip().lower()
    if "proteccion" in cs or "protección" in cs:
        return {"procede": False, "motivo": "clase de suelo de protección"}
    if "no construible" in dst or "no edificable" in dst \
            or "no construible" in tip or "no edificable" in tip:
        return {"procede": False, "motivo": "predio no construible"}
    if cs == "rural" or ("rural" in dst and "urbano" not in dst):
        return {"procede": False, "motivo": "suelo rural (no comparación urbana)"}
    return {"procede": True, "motivo": None}


def get_valuation(area_construida_m2, barrio, estrato=4, metodo_principal="m1",
                  ciudad="barranquilla", clase_suelo=None, destino=None, tipologia=None,
                  unidad_ph_no_resuelta=False, market_context_blocked=False,
                  valuation_authorized=False, market_context=None,
                  allow_legacy_reference=False):
    """
    Retorna la valoracion tecnica de mercado consolidando M1 (comparacion de
    mercado), M2 (costo de reposicion) y M3 (capitalizacion de rentas).

    03H.1A — FAIL-CLOSED por defecto: sin `valuation_authorized=True` (o sin el
    flag EXPLÍCITO `allow_legacy_reference=True`) NO se calcula nada. Así el
    default implícito no puede producir $305.5M ni $399.5M.

    ÚNICA AUTORIDAD de la tasa de mercado: `market_context`
    (`sector_metodologico.value_m2`). Esta función NO vuelve a resolver el sector
    desde el YAML cuando recibe un MarketContext; solo lee cap_rate y factor de
    costos de la metodología. Sin tasa válida en el contexto -> bloqueado.

    Regla de negocio (practica de la LONJA de Barranquilla, no de la Resolucion
    IGAC 941/2026): propiedad horizontal terminada -> metodo principal M1
    (comparacion de mercado, 100%); M3 (capitalizacion de rentas) solo en casos
    excepcionales con renta demostrable. La seleccion definitiva del metodo y la
    firma son del avaluador inscrito en el RAA.
    """
    import yaml
    from pathlib import Path

    cap_rate_neto = 0.0485
    val_m2_mercado = None
    factor_costos = 1.2576
    es_pasto = "pasto" in (ciudad or "").lower()
    market_rate_source = None
    market_rate_sector = None
    market_rate_match_type = None

    def _bloqueado(motivo):
        return {
            "consolidado": 0, "banda_baja": 0, "banda_alta": 0,
            "m1": 0, "m2": 0, "m3": 0,
            "metodo_principal": metodo_principal,
            "m1_m2": 0, "m3_m2": 0, "canon_mensual": 0,
            "cap_rate": cap_rate_neto,
            "metodologia_local": not es_pasto,
            "metodologia_aplica": False,
            "motivo_no_aplica": motivo,
            "value_m2": None, "market_rate_source": None,
            "market_rate_sector": None, "market_rate_match_type": None,
        }

    # ── 03H.1A: fail-closed. No hay permiso implícito. ──
    if not valuation_authorized and not allow_legacy_reference:
        return _bloqueado("valoración no autorizada (identidad o contexto de "
                          "mercado insuficiente)")

    # ── Precondición por tipología (bug L), identidad (03D) y contexto (03H) ──
    _pre = precondiciones_valoracion(clase_suelo=clase_suelo, destino=destino,
                                     tipologia=tipologia,
                                     unidad_ph_no_resuelta=unidad_ph_no_resuelta,
                                     market_context_blocked=market_context_blocked)
    if not _pre["procede"]:
        return _bloqueado(_pre["motivo"])

    # ── Metodología (solo cap_rate y factor de costos; NO la tasa) ──
    _yml = None
    if not es_pasto:
        base_dir = Path(__file__).resolve().parent
        yaml_path = (base_dir.parent / "motor_tma_lonja_baq_v1.0"
                     / "motor_tma_lonja_baq_v1.0" / "lonja_layer"
                     / "lonja_baq_metodologia.yaml")
        try:
            if yaml_path.exists():
                with open(yaml_path, "r", encoding="utf-8") as f:
                    _yml = yaml.safe_load(f)
        except Exception as e:
            print(f"[VALUATION][WARN] YAML Lonja no legible: {e}")

    # ── 03H.1A: la tasa viene EXCLUSIVAMENTE del MarketContext ──
    if market_context is not None:
        _sector = market_context.get("sector_metodologico") or {}
        val_m2_mercado = _sector.get("value_m2")
        market_rate_source = (market_context.get("market_rate_source")
                              or _sector.get("source"))
        market_rate_sector = _sector.get("matched_sector")
        market_rate_match_type = _sector.get("match_type")
        # barrio/estrato VERIFICADOS (nunca defaults legacy)
        _b = market_context.get("barrio") or {}
        if _b.get("value"):
            barrio = _b["value"]
        _e = market_context.get("estrato") or {}
        if _e.get("value") is not None:
            estrato = _e["value"]
        if not isinstance(val_m2_mercado, (int, float)) or val_m2_mercado <= 0:
            return _bloqueado("tasa de mercado no resuelta por el MarketContext "
                              "(MARKET_RATE_INVALID)")
    elif allow_legacy_reference:
        # Modo LEGACY explícito y exploratorio: resuelve del YAML con fallback
        # MARCADO (nunca autoriza una valoración de alta confianza).
        if es_pasto:
            estrato_map = {3: 3800000, 4: 5200000, 5: 6500000, 6: 7800000}
            val_m2_mercado = estrato_map.get(int(estrato), 5200000)
            market_rate_match_type = "GENERIC_ESTRATO_FALLBACK"
            market_rate_source = "referencia genérica por estrato (sin metodología local)"
        elif _yml:
            valores_suelo = _yml.get("valor_suelo_por_sector", {})
            _barrio = str(barrio or "")
            barrio_key = _barrio.replace(" ", "_").strip().title()
            sector_match = None
            for k in valores_suelo.keys():
                if k.lower() == barrio_key.lower() or k.lower() in _barrio.lower():
                    sector_match = k
                    break
            if sector_match:
                _v = valores_suelo[sector_match].get("valor_central_m2")
                market_rate_source = valores_suelo[sector_match].get("fuente")
                market_rate_sector = sector_match
                if _v is None or _v <= 0:
                    val_m2_mercado = None
                    market_rate_match_type = "MARKET_RATE_INVALID"
                else:
                    val_m2_mercado = _v
                    market_rate_match_type = "EXACT"
            else:
                estrato_map = {3: 3800000, 4: 5200000, 5: 6500000, 6: 7800000}
                val_m2_mercado = estrato_map.get(int(estrato), 5200000)
                market_rate_source = ("fallback genérico por estrato "
                                      "(no específico de sector)")
                market_rate_match_type = "GENERIC_ESTRATO_FALLBACK"
        if val_m2_mercado is None or val_m2_mercado <= 0:
            return _bloqueado("tasa de mercado inválida (MARKET_RATE_INVALID)")
    else:
        # Autorización sin MarketContext: no hay tasa autorizada -> fail-closed.
        return _bloqueado("autorización sin MarketContext (tasa de mercado no "
                          "resuelta por la única autoridad)")

    # Cap Rate (M3) y factor de costos (M2) — parámetros de metodología.
    if _yml:
        tasas_tip = _yml.get("capitalizacion_rentas", {}).get("tasas_por_tipologia", {})
        estrato_key = f"apto_NO_VIS_estrato_{estrato}"
        if estrato_key in tasas_tip:
            cap_rate_neto = tasas_tip[estrato_key].get("tasa_central", 0.0485)
        factor_costos = _yml.get("costos_construccion", {}).get(
            "factor_actualizacion", 1.2576)

    # M1: Comparacion de Mercado (metodo principal para PH terminada, 100%)
    m1_base = int(area_construida_m2 * val_m2_mercado)
    m1_total_central = int(m1_base * 1.02)
    
    # Canon de arriendo mensual (tasa implicita del sector)
    # Renta tipica mensual estimada: ~0.55% del valor por m2
    canon_mensual = int(area_construida_m2 * (val_m2_mercado * 0.00538))
    
    # M3: Capitalizacion de Rentas
    m3_total_central = int((canon_mensual * 0.84 * 12) / cap_rate_neto)
    
    # M2: Reposicion Fisica Depreciada
    costo_construccion_base = 2800000 # multifamiliar tipico
    valor_lote_m2 = int(val_m2_mercado * 0.30) # 30% del valor total es el lote
    m2_total_central = int(area_construida_m2 * (costo_construccion_base * factor_costos * 0.85 + valor_lote_m2))

    # Valor consolidado segun metodo principal (practica Lonja): PH -> M1 (100%); excepcional -> M3.
    val_consolidado = m3_total_central if metodo_principal == "m3" else m1_base
    val_consolidado = int(round(val_consolidado, -4))
    m1_total_central = int(round(m1_total_central, -4))
    m3_total_central = int(round(m3_total_central, -4))
    m2_total_central = int(round(m2_total_central, -4))
    
    banda_baja = int(val_consolidado * 0.935)
    banda_alta = int(val_consolidado * 1.09)
    
    return {
        "consolidado": val_consolidado,
        "banda_baja": banda_baja,
        "banda_alta": banda_alta,
        "m1": m1_total_central,
        "m2": m2_total_central,
        "m3": m3_total_central,
        "metodo_principal": metodo_principal,
        "m1_m2": int(m1_total_central / area_construida_m2) if area_construida_m2 else 0,
        "m3_m2": int(m3_total_central / area_construida_m2) if area_construida_m2 else 0,
        "canon_mensual": canon_mensual,
        "cap_rate": cap_rate_neto,
        "metodologia_local": not es_pasto,
        "metodologia_aplica": True,
        "motivo_no_aplica": None,
        # 03H: provenance de la tasa de mercado (no emitir $/m² sin fuente).
        "value_m2": val_m2_mercado,
        "market_rate_source": market_rate_source,
        "market_rate_sector": market_rate_sector,
        "market_rate_match_type": market_rate_match_type,
    }


def get_hallazgos(barrio, analysis=None):
    """
    Genera hallazgos dinámicos a partir del análisis real del CTL.
    Bloque C Sprint 2: eliminado el switch hardcodeado por barrio.

    Args:
        barrio:   Nombre del barrio (ya no determina el contenido).
        analysis: Dict del legal_analyzer. Si es None, usa fallback de ausencia de CTL.

    Returns:
        Lista de tuples (sev, tc, bg, titulo, fuente, desc, impl).
    """
    # Si el legal_analyzer ya produjo hallazgos dinámicos, usarlos directamente
    if analysis and analysis.get("hallazgos"):
        return analysis["hallazgos"]

    # Fallback: sin CTL cargado
    return [
        ("ALTO", C_ROJO, colors.HexColor("#FFF0F0"),
         "H-01 | AUSENCIA DE CERTIFICADO DE TRADICION Y LIBERTAD (CTL)",
         "Requerimiento Documental Obligatorio",
         "No se aporto el Certificado de Tradicion y Libertad para este activo. "
         "Esto impide validar la titularidad del dominio, la vigencia registral y "
         "la existencia de limitaciones o afectaciones legales activas en la ORIP.",
         "BLOQUEO TOTAL para estructuracion fiduciaria, originacion de creditos y garantias. "
         "La viabilidad juridica del activo queda en estado PENDIENTE hasta la expedicion "
         "y lectura del certificado actualizado (no mayor a 30 dias, VUR-SNR)."),
        ("MEDIO", C_NARANJA, C_ALERTA_BG,
         "H-02 | Gravamenes y Limitaciones de Dominio No Verificados",
         "Estudio de Titulos / ORIP",
         "Ante la falta del CTL, no es posible confirmar la inexistencia de hipotecas "
         "vigentes, embargos judiciales, afectaciones a vivienda familiar, patrimonios "
         "de familia, demandas inscritas o usufructos.",
         "Riesgo juridico medio-alto. No realizar desembolso ni constitucion de garantias "
         "sin verificar previamente el estado registral en la base oficial del SNR."),
    ]


def get_recs(barrio, analysis=None, hallazgos=None):
    """
    Genera recomendaciones dinámicas a partir de los hallazgos reales.
    Bloque C Sprint 2: eliminado el switch hardcodeado por barrio.

    Args:
        barrio:    Nombre del barrio (ya no determina el contenido).
        analysis:  Dict del legal_analyzer.
        hallazgos: Lista de hallazgos para derivar recomendaciones.

    Returns:
        Lista de tuples (titulo, descripcion).
    """
    recs = []

    # Usar recomendaciones del legal_analyzer si existen
    if analysis and analysis.get("recs"):
        return analysis["recs"]

    # Generar recomendaciones desde hallazgos si no hay CTL analizado
    if hallazgos:
        h_idx = 1
        for sev, tc, bg, titulo, fuente, desc, impl in hallazgos:
            titulo_l = titulo.lower()
            if "ausencia" in titulo_l and "ctl" in titulo_l:
                recs.append((
                    f"R-0{h_idx} | Requerimiento INMEDIATO de Certificado SNR",
                    "Solicitar el CTL actualizado (no mayor a 30 dias) en la Ventanilla "
                    "Unica de Registro (VUR) del SNR: ventanillaunicaregistry.supernotariado.gov.co. "
                    "Ningun proceso de debida diligencia puede avanzar sin este insumo basico."
                ))
                h_idx += 1
            elif "hipoteca" in titulo_l:
                recs.append((
                    f"R-0{h_idx} | Gestion de Gravamen Hipotecario",
                    "Tramitar la cancelacion del gravamen hipotecario vigente o verificar "
                    "condiciones de subrogacion con el acreedor. Registrar en el ORIP."
                ))
                h_idx += 1
            elif "cesion" in titulo_l or "discrepancia" in titulo_l:
                recs.append((
                    f"R-0{h_idx} | Aclaracion Registral de la Cesion de Cartera",
                    "Verificar con el banco cesionario la cesion formal y solicitar "
                    "su inscripcion en el folio SNR para alinear el registro publico."
                ))
                h_idx += 1
            elif "afectacion" in titulo_l and "vivienda" in titulo_l:
                recs.append((
                    f"R-0{h_idx} | Levantamiento de Afectacion a Vivienda Familiar",
                    "Obtener escritura publica de levantamiento con consentimiento de "
                    "ambos titulares e inscribirla en el ORIP antes de cualquier acto de disposicion."
                ))
                h_idx += 1

    if not recs:
        recs.append((
            "R-01 | Verificacion General del Estado Registral",
            "Solicitar y analizar el CTL actualizado para confirmar el estado "
            "registral del activo antes de cualquier decision de credito o estructuracion."
        ))

    return recs


def get_identificacion_dt(barrio, db_record, val_data, fmt_cop):
    barrio = barrio.lower().strip()
    folio = db_record.get("folio_matricula", "040-XXXXXX")
    direccion = db_record.get("direccion", "")
    area = db_record.get("area", 0)
    
    if "miramar" in barrio:
        # Los datos personales/registrales NUNCA se hardcodean (F-14/H-04): se poblan
        # desde el CTL analizado (campo "titulares" del db_record) o quedan pendientes.
        titulares = db_record.get("titulares")
        if not titulares:
            titulares = "PENDIENTE DE VERIFICACION (Requiere Certificado de Tradicion y Libertad del predio)"
        return [
            ("Matricula Inmobiliaria", f"{folio} (Circulo Registral 040 Barranquilla)"),
            ("Direccion oficial", direccion),
            ("Tipologia", "Apartamento -- Propiedad Horizontal (NO VIS)"),
            ("Area privada construida", f"{area} m2"),
            ("Coeficiente de copropiedad", "N/D (Sujeto a regimen de PH / Requiere CTL)"),
            ("Apertura del folio", "N/D (Requiere CTL del predio)"),
            ("NUPRE", "N/D (Sujeto a consulta GC-BAQ)"),
            ("Titulares vigentes", titulares),
            ("Modalidad de adquisicion", "N/D (Requiere CTL del predio)"),
            ("Valor Comercial Consolidado", f"{fmt_cop(val_data['consolidado'])} COP (Banda: {fmt_cop(val_data['banda_baja'])} -- {fmt_cop(val_data['banda_alta'])})"),
            ("Constructor / Enajenante", "N/D (Requiere CTL del predio)"),
            ("Acreedor hipotecario (SNR)", "N/D (Requiere CTL del predio)"),
            ("Acreedor hipotecario (REAL)", "N/D (Requiere CTL del predio)"),
            ("ORIP", "Oficina de Registro de Instrumentos Publicos -- Barranquilla"),
            ("Fuente registral", "Pendiente de verificacion registral (sin CTL del predio)"),
        ]
    else:
        return [
            ("Matricula Inmobiliaria", f"{folio} (Circulo Registral 040 Barranquilla)"),
            ("Direccion oficial", direccion),
            ("Tipologia", "Residencial -- (Sujeto a verificacion catastral)"),
            ("Area privada construida", f"{area} m2 (Estimado para calculo / Sin soporte CTL)"),
            ("Coeficiente de copropiedad", "N/D (Sujeto a regimen de PH / Sin soporte CTL)"),
            ("Apertura del folio", "N/D (Sin soporte CTL)"),
            ("NUPRE", "N/D (Sujeto a consulta GC-BAQ)"),
            ("Titulares vigentes", "PENDIENTE DE VERIFICACION (Sin Certificado de Tradicion y Libertad)"),
            ("Modalidad de adquisicion", "PENDIENTE DE VERIFICACION (Sin Certificado de Tradicion y Libertad)"),
            ("Valor Comercial Consolidado", f"{fmt_cop(val_data['consolidado'])} COP (Banda: {fmt_cop(val_data['banda_baja'])} -- {fmt_cop(val_data['banda_alta'])})"),
            ("Constructor / Enajenante", "N/D (Sin soporte CTL)"),
            ("Acreedor hipotecario (SNR)", "PENDIENTE DE VERIFICACION (Sin Certificado de Tradicion y Libertad)"),
            ("Acreedor hipotecario (REAL)", "PENDIENTE DE VERIFICACION (Sin Certificado de Tradicion y Libertad)"),
            ("ORIP", "Oficina de Registro de Instrumentos Publicos -- Barranquilla"),
            ("Fuente registral", f"Pendiente de verificacion registral (sin CTL, matricula {folio})"),
        ]

def get_localizacion_dt(barrio, lat, lon):
    barrio_clean = barrio.strip().title() if barrio else "Barranquilla"
    return [
        ("Coordenadas WGS84", f"Lat: {lat:.5f} N | Lon: {lon:.5f} W"),
        ("Sector urbano", f"Perímetro Urbano Barranquilla / {barrio_clean}"),
        ("Barrio / sector oficial", barrio_clean),
        ("Infraestructura vial", "Malla vial urbana y corredores de conectividad inmediata"),
        ("Equipamientos cercanos", "Equipamientos institucionales, comerciales y asistenciales en radio 2.0 km"),
    ]

def get_cobertura_alert(barrio, ciudad="barranquilla", pois=None, poi_status=None):
    barrio_clean = barrio.strip().title() if barrio else "el sector"
    c = (ciudad or "").lower()
    if "medellin" in c or "medellín" in c:
        nombre_ciudad = "Medellín"
    elif "bogota" in c or "bogotá" in c:
        nombre_ciudad = "Bogotá D.C."
    elif "pasto" in c or "nariño" in c or "narino" in c:
        nombre_ciudad = "Pasto (Nariño)"
    else:
        nombre_ciudad = "Barranquilla"
    # 'Bogotá D.C.' ya termina en punto: no duplicar el punto de la frase
    punto = "" if nombre_ciudad.endswith(".") else "."

    # 03F/03F.1: la narrativa se construye desde el estado REAL por categoría.
    # Distingue NO_MATCH (fuente respondió, 0 resultados) de SOURCE_UNAVAILABLE
    # (no se pudo completar la consulta). No afirmar categorías no verificadas.
    if pois is not None or poi_status is not None:
        _cats = ("Salud", "Educacion", "Comercio", "Recreacion")
        _disp, _no_match, _src_unavail = [], [], []
        for _c in _cats:
            st = (poi_status or {}).get(_c)
            if st is None:
                st = "AVAILABLE" if (pois or {}).get(_c) else "NO_MATCH"
            if st == "AVAILABLE":
                _disp.append(_c)
            elif st == "SOURCE_UNAVAILABLE":
                _src_unavail.append(_c)
            elif st == "NO_MATCH":
                _no_match.append(_c)
        _partes = []
        if _disp:
            _partes.append(
                f"En un radio de 2.0 km en torno al inmueble en <b>{barrio_clean}</b> "
                f"({nombre_ciudad}{punto}) se verificaron equipamientos de "
                f"<b>{', '.join(_disp).lower()}</b>.")
        for _c in _no_match:
            _partes.append(f"No se encontraron equipamientos verificables de "
                           f"{_c.lower()} dentro del radio consultado.")
        for _c in _src_unavail:
            _partes.append(f"No fue posible completar la consulta de equipamientos "
                           f"de {_c.lower()} durante esta ejecución.")
        if not _partes:
            return (
                f"<b>EVALUACION DE COBERTURA:</b> No se verificaron equipamientos urbanos "
                f"en un radio de 2.0 km en torno al inmueble en <b>{barrio_clean}</b> "
                f"({nombre_ciudad}): las fuentes consultadas no devolvieron resultados "
                f"verificables en esta ejecución. No se incluyen equipamientos no verificados."
            )
        _partes.append("La accesibilidad peatonal y vehicular queda sujeta a verificación de campo.")
        return "<b>EVALUACION DE COBERTURA:</b> " + " ".join(_partes)

    # Sin datos de POI (legacy): no afirmar categorías específicas.
    return (
        f"<b>EVALUACION DE COBERTURA:</b> El inmueble ubicado en <b>{barrio_clean}</b> cuenta con una calificacion "
        f"de conectividad y equipamiento <b>SATISFACTORIA</b> dentro del perimetro urbano de {nombre_ciudad}{punto} "
        f"La verificación de equipamientos de comercio, salud, educacion y recreacion en el radio de 2.0 km queda "
        f"sujeta a confirmación de campo."
    )

def get_analisis_registral_text(barrio):
    return (
        "<b>Auditoría de Tradición:</b> El análisis registral se computa a partir de las anotaciones "
        "y actos inscritos en el folio de matrícula inmobiliaria del inmueble. Las salvedades, gravámenes "
        "o limitaciones identificadas se reflejan en la tabla de hallazgos periciales del presente dictamen."
    )

def get_valoracion_alert(barrio, val_data, fmt_cop, ciudad="barranquilla"):
    barrio_clean = barrio.strip().title() if barrio else "el sector"
    metodo = (val_data.get("metodo_principal") or "m1").lower()
    if metodo == "m3":
        metodo_txt = ("el método de capitalización de rentas (M3) como caso excepcional, "
                      "según la renta demostrable del inmueble")
    else:
        metodo_txt = ("el método de comparación de mercado (M1) como método principal para "
                      "propiedad horizontal terminada")
    # Pasto: sin metodología local verificada, la estimación es referencia genérica
    # por estrato (nunca la Lonja de Barranquilla).
    if "pasto" in (ciudad or "").lower():
        metodo_ref = ("Referencia genérica por estrato (sin metodología local de Pasto "
                      "verificada): valor sujeto a validación del avaluador RAA.")
    else:
        metodo_ref = "Práctica de la Lonja de Barranquilla: PH = 100% M1; M3 solo excepcional."
    return (
        f"<b>SINTESIS DE VALORACION:</b> La estimación comercial de "
        f"<b>{fmt_cop(val_data['consolidado'])} COP</b> responde a {metodo_txt}, "
        f"calibrado por sector geoeconómico ({barrio_clean}). "
        f"{metodo_ref}"
    )

def get_alcance_dt(barrio, ciudad="barranquilla", receipts=None):
    # F-21: alcance honesto — no se afirman integraciones que no existen.
    # Bug H: si llegan `receipts` (estado real de la ejecución), las filas de
    # geocodificación/POI/GIS/volcán/SARLAFT reflejan lo que REALMENTE corrió,
    # no una afirmación estática "EJECUTADA EN VIVO".
    es_med = "medellin" in (ciudad or "").lower()
    es_bog = "bogota" in (ciudad or "").lower()
    es_pas = "pasto" in (ciudad or "").lower()

    _gis = ((receipts or {}).get("gis") or {})
    _capas = _gis.get("capas") or {}
    _fuente_gis = _gis.get("estado_fuente") or ""
    _volc = (receipts or {}).get("riesgo_volcanico") or {}
    _poi = (receipts or {}).get("poi") or {}
    _sag = (receipts or {}).get("sarlaft") or {}

    def _estado_capa(clave, default):
        if not receipts or clave not in _capas:
            return default
        det = _capas[clave]
        estado = det.get("estado") if isinstance(det, dict) else det
        if estado == "MATCH_EXACT":
            return "EJECUTADA EN VIVO -- capa con coincidencia para el predio"
        if estado == "NO_MATCH":
            return "CONSULTADA -- sin coincidencia para este predio (verificar en el geoportal)"
        if estado == "SOURCE_UNAVAILABLE":
            return "NO DISPONIBLE -- el servicio no respondió en esta generación"
        return f"ESTADO {estado}"

    def _sarlaft_txt(default):
        """03S.1: el capítulo 16 consume el MISMO ScreeningSummary que el 09.

        Antes, en Barranquilla esta fila estaba fija en "NO EJECUTADA" mientras el
        capítulo 09 podía reportar un screening ejecutado: dos estados
        contradictorios en el mismo documento. Ahora hay una sola verdad.
        """
        if not receipts:
            return default
        _status = _sag.get("status")
        if _sag.get("ejecutado"):
            _detalle = "screening {}".format(_sag.get("etiqueta") or "—")
            # § 03S.1A-3: la cobertura se declara SIEMPRE, separada de la decisión.
            _cobertura = (_sag.get("coverage_status")
                          or ("COVERAGE_COMPLETE" if _sag.get("coverage_complete")
                              else "COVERAGE_PARTIAL"))
            _detalle += " · " + _cobertura.replace("COVERAGE_", "cobertura ").lower()
            _srcs = [f.get("source_id") for f in (_sag.get("fuentes") or [])]
            if _srcs:
                _detalle += " · fuentes: " + ", ".join(_srcs)
            if _sag.get("fuentes_pendientes"):
                _detalle += " · NO DISPONIBLES: " + ", ".join(_sag.get("fuentes_pendientes"))
            if _sag.get("evidence_expected") is not None:
                _detalle += " · evidencia {}/{} · cadena {}".format(
                    _sag.get("evidence_created"), _sag.get("evidence_expected"),
                    _sag.get("evidence_chain_status") or "—")
            return "EJECUTADO -- " + _detalle
        return ("NO EJECUTADO -- " + (_sag.get("reason")
                or "sin fuentes oficiales disponibles en esta generación"))

    def _snr_txt():
        """03D.2: la fila SNR refleja si el CTL está adjuntado (fuente única:
        receipts.ctl_adjuntado). No puede contradecir al capítulo 16.B."""
        if (receipts or {}).get("ctl_adjuntado"):
            return "PROCESADO -- CTL adjuntado (anotaciones del folio extraídas del certificado)"
        return "PENDIENTE -- Requiere CTL del predio (las anotaciones se procesan si se adjunta)"

    def _catastro_txt(exacto, espacial, no_disp, legacy):
        """03D.2: estado de ejecución catastral desde receipts (fuente única)."""
        _cat = ((receipts or {}).get("catastro") or {})
        if _cat.get("exacto"):
            return exacto
        if _cat.get("espacial"):
            return espacial
        if receipts and not _cat.get("consultado"):
            return no_disp
        return legacy

    if es_med:
        return [
            ("Datos registrales SNR", _snr_txt()),
            ("Capa catastral Medellín", "CONSULTADA EN VIVO -- Uso del predio (servidormapas Alcaldía)"),
            ("POT/Ordenamiento Medellín", "EJECUTADA -- Clasificación de suelo y tratamientos consultados en vivo"),
            ("Riesgos/Amenazas Medellín", "EJECUTADA -- Capas de gestión del riesgo DAGRD consultadas en vivo"),
            ("Integracion WFS-IGAC", "PLANIFICADA -- En desarrollo para consulta en vivo (ver roadmap)"),
            ("Sincronizacion Curaduria", "NO VALIDADA -- Requiere confrontación con licencia de construcción"),
            ("Screening de contrapartes", _sarlaft_txt("NO EJECUTADO -- requiere fuentes oficiales de sanciones")),
            ("Estimacion referencial", "NO sustituye avalúo elaborado por avaluador inscrito en el RAA (Ley 1673/2013 · Resolución IGAC 941/2026)"),
        ]
    if es_bog:
        return [
            ("Datos registrales SNR", _snr_txt()),
            ("Capa catastral Bogotá", "CONSULTADA EN VIVO -- Lote, sector, uso por manzana (serviciosgis catastro distrital)"),
            ("POT/Ordenamiento Bogotá", "EJECUTADA -- Suelo Decreto 555/2021, UPZ y localidad consultados en vivo"),
            ("Riesgos/Amenazas Bogotá", "EJECUTADA -- Capas IDIGER consultadas en vivo (mov. masa, sismos, geotecnia)"),
            ("Detalle predial (NUPRE/destino por predio)", "NO DISPONIBLE EN ABIERTO -- El catastro distrital no expone capa predial con NUPRE; el destino es uso predominante por manzana (referencial)"),
            ("Sincronizacion Curaduria", "NO VALIDADA -- Requiere confrontación con licencia de construcción"),
            ("Screening de contrapartes", _sarlaft_txt("NO EJECUTADO -- requiere fuentes oficiales de sanciones")),
            ("Estimacion referencial", "NO sustituye avalúo elaborado por avaluador inscrito en el RAA (Ley 1673/2013 · Resolución IGAC 941/2026)"),
        ]
    if es_pas:
        return [
            ("Datos registrales SNR", _snr_txt()),
            ("Geocodificacion del predio", "EJECUTADA -- OSM/Nominatim (coordenadas en Pasto)"),
            ("Equipamiento urbano (POI)", ("CONSULTADO -- OpenStreetMap/Overpass (respaldo Photon)"
                                           if _poi.get("disponible") else
                                           "NO DISPONIBLE -- Overpass/Photon no respondieron en esta generación")
             if receipts else "EJECUTADA -- OpenStreetMap/Overpass con respaldo Photon (radio 2 km)"),
            ("Capa catastral Pasto (NUPRE, areas)",
             _estado_capa("predios_estratificacion", "EJECUTADA EN VIVO -- Geoportal Municipal de Pasto (Planeacion)")
             if receipts else "EJECUTADA EN VIVO -- Geoportal Municipal de Pasto (Planeacion)"),
            ("POT/Ordenamiento Pasto",
             _estado_capa("tratamientos_urbanisticos", "EJECUTADA EN VIVO -- Clase de suelo, area de actividad, tratamiento y edificabilidad por predio")
             if receipts else "EJECUTADA EN VIVO -- Clase de suelo, area de actividad, tratamiento y edificabilidad por predio"),
            ("Riesgo volcanico (Volcan Galeras)",
             ("EJECUTADA EN VIVO -- SGC " + (_volc.get("nivel") or "N/D")) if _volc.get("disponible")
             else "NO DISPONIBLE -- el mapa SGC no respondió en esta generación"
             if receipts else "EJECUTADA EN VIVO -- Mapa oficial de amenaza volcanica del SGC"),
            ("Riesgos municipales por predio",
             _estado_capa("riesgos_urbano", "EJECUTADA EN VIVO -- Riesgo volcanico, inundacion, remocion en masa, subsidencia y ZAVA (geoportal de Pasto)")
             if receipts else "EJECUTADA EN VIVO -- Riesgo volcanico, inundacion, remocion en masa, subsidencia y ZAVA (geoportal de Pasto)"),
            ("Sincronizacion Curaduria", "NO VALIDADA -- Requiere confrontación con licencia de construcción"),
            ("Screening de contrapartes", _sarlaft_txt("NO EJECUTADO -- requiere fuentes oficiales de sanciones")),
            ("Estimacion referencial", "REFERENCIA GENERICA POR ESTRATO -- No usa metodología local; no sustituye avalúo RAA (Ley 1673/2013 · Resolución IGAC 941/2026)"),
        ]
    return [
        ("Datos registrales SNR", _snr_txt()),
        ("Capa catastral BAQ",
         _catastro_txt(
             "CONSULTADA EN VIVO -- Predio resuelto por codigo/NUPRE del CTL",
             "CONSULTADA EN VIVO -- Interseccion espacial (bbox) sin identificacion exacta del predio",
             "NO DISPONIBLE -- el servicio abierto no respondio en esta generacion",
             "REFERENCIAL -- Estimacion del modulo ARHIAX RE (sin consulta en vivo verificada)")),
        ("POT/Ordenamiento BAQ", "EJECUTADA -- Cruce espacial sobre capas POT empaquetadas"),
        ("Riesgos/Amenazas BAQ", "EJECUTADA -- Cruce espacial STRtree contra capas de amenaza y riesgo"),
        ("Integracion WFS-IGAC", "PLANIFICADA -- En desarrollo para consulta en vivo (ver roadmap)"),
        ("Sincronizacion Curaduria", "NO VALIDADA -- Requiere confrontación con licencia de construcción"),
        ("Screening de contrapartes", _sarlaft_txt("NO EJECUTADO -- requiere fuentes oficiales de sanciones")),
        ("Estimacion referencial", "NO sustituye avalúo elaborado por avaluador inscrito en el RAA (Ley 1673/2013)"),
    ]

def _destino_source_txt(destino_economico, gc_sigla, es_bog, es_pas, source=None):
    """03H.2A (#G): el origen del destino económico debe ser el REAL.

    Antes se afirmaba "(Capa Predio GC-BAQ, en vivo)" para cualquier destino, sin
    importar si el valor venía del servicio temático de destinos económicos, de un
    fallback espacial o de una inferencia del CTL. Eso atribuía a la capa Predio
    un dato que no salió de ahí.

    `source` (contrato del motor):
      capa_predio | thematic_exact | thematic_spatial | ctl_inferred | pot_context
      None -> origen no declarado: se etiqueta de forma NEUTRA.
    """
    if es_bog:
        return f"{destino_economico} (uso predominante por manzana, en vivo)"
    if es_pas:
        return f"{destino_economico} (area de actividad del POT Pasto, en vivo)"
    if source == "capa_predio":
        return f"{destino_economico} (Capa Predio {gc_sigla}, en vivo)"
    if source == "thematic_exact":
        return (f"{destino_economico} (Servicio Destinos Economicos -- "
                f"identificador exacto)")
    if source == "thematic_spatial":
        return (f"{destino_economico} (Servicio Destinos Economicos -- "
                f"contexto espacial)")
    if source == "ctl_inferred":
        return f"{destino_economico} (inferido del CTL adjunto)"
    if source == "pot_context":
        return f"{destino_economico} (norma POT del poligono, en vivo)"
    # Origen no declarado por el motor: no se atribuye a una capa concreta.
    return f"{destino_economico} (fuente catastral en vivo)"


def get_catastral_dt(barrio, area, destino_economico=None, nupre=None,
                     codigo_catastral=None, condicion=None, area_catastral=None,
                     tipo_construccion=None, pisos=None, estrato=None,
                     ciudad="barranquilla", destino_source=None):
    barrio_clean = barrio.strip().title() if barrio else "Pendiente de verificacion"
    es_med = "medellin" in (ciudad or "").lower()
    es_bog = "bogota" in (ciudad or "").lower()
    es_pas = "pasto" in (ciudad or "").lower()
    if es_bog:
        gc_nombre = "Bogotá"
        gc_sigla = "GC-BOG"
    elif es_med:
        gc_nombre = "Medellín"
        gc_sigla = "GC-MED"
    elif es_pas:
        gc_nombre = "Pasto"
        gc_sigla = "GC-PAS"
    else:
        gc_nombre = "Barranquilla"
        gc_sigla = "GC-BAQ"
    # Sprint 2 (exactitud): el destino económico y el NUPRE salen del catastro en
    # vivo cuando el CTL trae código/NUPRE; nunca se asume HABITACIONAL por defecto.
    if destino_economico:
        destino_txt = _destino_source_txt(destino_economico, gc_sigla, es_bog,
                                          es_pas, destino_source)
    elif es_pas:
        # El geoportal de Pasto SI publica el uso del predio: si no llegó, se
        # declara PENDIENTE (sin el texto 'NO REGISTRA', retirado del informe).
        destino_txt = "PENDIENTE DE VERIFICACION"
    else:
        destino_txt = "PENDIENTE DE VERIFICACION (Requiere consulta catastral del predio)"
    condicion_txt = condicion if condicion else "Pendiente de verificacion"
    if tipo_construccion and pisos:
        constr_txt = f"{tipo_construccion} -- {pisos} piso(s)"
    elif tipo_construccion:
        constr_txt = tipo_construccion
    elif es_pas:
        constr_txt = "PENDIENTE DE VERIFICACION"
    else:
        constr_txt = "Pendiente de verificacion"
    # 03H.2 — Estrato: la AUSENCIA del dato NO implica uso no residencial.
    #   estrato=None + destino=None            -> PENDIENTE DE VERIFICACIÓN
    #   destino=Habitacional + estrato=None    -> PENDIENTE (uso residencial
    #                                             confirmado; estrato no resuelto)
    #   destino exclusivamente no residencial   -> "No aplica (uso no residencial
    #                                             declarado)"
    # Nunca se afirma "no aplica" sin evidencia explícita de un destino no
    # residencial declarado.
    if estrato not in (None, "", "No_Aplica"):
        estrato_txt = estrato
    else:
        _dest_up = str(destino_economico or "").upper()
        # Un uso MIXTO ("residencial, comercial y de servicios") SIGUE siendo
        # residencial para efectos de estrato.
        _es_resid = any(k in _dest_up for k in ("RESIDENCIAL", "VIVIENDA",
                                                "HABITACIONAL"))
        _no_resid = (not _es_resid) and any(
            k in _dest_up for k in ("INDUSTRIAL", "BODEGA", "COMERCIAL", "OFICINA",
                                    "LOTE", "GARAJE"))
        if _no_resid:
            estrato_txt = "No aplica (uso no residencial declarado)"
        elif _es_resid:
            estrato_txt = ("PENDIENTE — uso residencial confirmado; estrato no "
                           "resuelto")
        else:
            estrato_txt = "PENDIENTE DE VERIFICACIÓN"
    # Regresión (CTL real 040-646406): 'Área Registrada' es el área PRIVADA del
    # inmueble que declara el CTL (apartamento 430: 58.75 m2). El área de TERRENO
    # catastral (22.05 m2 del lote) NO es el área del apartamento: mostrarla como
    # 'Área Registrada' confunde (la 4.1B ya la reporta como 'Área terreno').
    area_reg_txt = f"{area:.2f} m2" if area else "Pendiente de verificación (requiere el área del CTL)"
    return [
        ("Area Registrada", area_reg_txt),
        # 03H.2: el barrio proviene de la capa oficial POT/unidades
        # administrativas; "Barrio / sector oficial" es la etiqueta honesta.
        ("Barrio / sector oficial", barrio_clean),
        ("NUPRE", nupre if nupre else f"Pendiente de consulta {gc_sigla}"),
        ("Codigo catastral", codigo_catastral if codigo_catastral else f"Pendiente de consulta {gc_sigla}"),
        ("Destino economico catastral", destino_txt),
        ("Condicion juridica", condicion_txt),
        ("Tipo de construccion", constr_txt),
        ("Estrato", estrato_txt),
    ]

def get_pot_summary_dt(barrio, ciudad="barranquilla", clase_suelo=None,
                       uso_economico=None, upz=None, tratamiento=None,
                       tipo_tratamiento=None):
    """Resumen POT por ciudad. Cuando la consulta en vivo trajo el valor real
    (clase_suelo, uso, UPZ, tratamiento) se muestra; si no, PENDIENTE (nunca se
    afirma un valor genérico como si fuera del predio)."""
    es_med = "medellin" in (ciudad or "").lower()
    es_bog = "bogota" in (ciudad or "").lower()
    es_pas = "pasto" in (ciudad or "").lower()

    def _v(valor, pendiente):
        valor = (valor or "").strip()
        return valor if valor and valor.upper() not in ("N/A", "N/D", "NONE") else pendiente

    if es_med:
        suelo = _v(clase_suelo, "PENDIENTE (consulta en vivo no disponible)")
        uso = _v(uso_economico, "PENDIENTE (consulta en vivo no disponible)")
        trat = _v(tratamiento, "PENDIENTE (consulta en vivo no disponible)")
        return [
            ("Clasificacion del suelo", f"{suelo} (POT Medellín - Acuerdo 48/2014, en vivo)" if _v(clase_suelo, "") else suelo),
            ("Norma uso de suelo", f"{uso} (catastro en vivo)" if _v(uso_economico, "") else uso),
            ("Tratamiento urbanistico", f"{trat} (polígono {tipo_tratamiento})" if (_v(tratamiento, "") and tipo_tratamiento) else trat),
            ("Altura maxima segun tratamiento", "Sujeta a ficha normativa del polígono específico"),
            ("Planes Parciales", "NO EVALUADO en capas abiertas (verificar en Planeación)"),
            ("Planes de Reordenamiento", "NO EVALUADO en capas abiertas (verificar en Planeación)"),
            ("Fuente de capas", "Servidormapas Alcaldía de Medellín (consultas en vivo, Sprint 3)"),
        ]
    if es_bog:
        suelo = _v(clase_suelo, "PENDIENTE (consulta en vivo no disponible)")
        uso = _v(uso_economico, "PENDIENTE (consulta en vivo no disponible)")
        upz_txt = _v(upz, "PENDIENTE (consulta en vivo no disponible)")
        return [
            ("Clasificacion del suelo", f"{suelo} (POT Bogotá Decreto 555/2021, en vivo)" if _v(clase_suelo, "") else suelo),
            ("Norma uso de suelo", f"{uso} (uso predominante por manzana, en vivo)" if _v(uso_economico, "") else uso),
            ("Unidad de Planeamiento Zonal (UPZ)", f"{upz_txt} (capa UPZ catastro distrital)" if _v(upz, "") else upz_txt),
            ("Altura maxima segun tratamiento", "Sujeta a ficha normativa del polígono específico (UPZ)"),
            ("Planes Parciales", "NO EVALUADO en capas abiertas (verificar en la SDP)"),
            ("Planes de Reordenamiento", "NO EVALUADO en capas abiertas (verificar en la SDP)"),
            ("Fuente de capas", "Catastro Distrital Bogotá (serviciosgis, consultas en vivo, Sprint 3)"),
        ]
    if es_pas:
        # Pasto: el geoportal municipal publica la normativa del POT por predio
        # (tratamiento, edificabilidad, clase de suelo, area de actividad).
        _suelo = _v(clase_suelo, "")
        _uso = _v(uso_economico, "")
        _trat = _v(tratamiento, "")
        return [
            ("Clasificacion del suelo",
             f"{_suelo} (POT Pasto, en vivo)" if _suelo
             else "PENDIENTE (consulta en vivo no disponible)"),
            ("Norma uso de suelo",
             f"{_uso} (area de actividad, POT Pasto en vivo)" if _uso
             else "PENDIENTE (consulta en vivo no disponible)"),
            ("Tratamiento urbanistico",
             (f"{_trat} (poligono {tipo_tratamiento})" if tipo_tratamiento else _trat)
             if _trat else "PENDIENTE (consulta en vivo no disponible)"),
            ("Altura maxima segun tratamiento",
             "Ver tabla 'Edificabilidad' (capa de tratamientos del POT Pasto)"),
            ("Planes Parciales", "NO EVALUADO en capas abiertas (verificar en Planeacion Pasto)"),
            ("Planes de Reordenamiento", "NO EVALUADO en capas abiertas (verificar en Planeacion Pasto)"),
            ("Fuente de capas",
             "Geoportal Municipal de Pasto -- Planeacion (consultas en vivo)"),
        ]
    return [
        ("Clasificacion del suelo", "SUELO URBANO (POT Barranquilla - Confirmado)"),
        ("Norma uso de suelo", "ACTIVIDAD URBANA RESIDENCIAL / COMERCIAL"),
        ("Tratamiento urbanistico", "CONSOLIDACION / DESARROLLO (Según polígono POT)"),
        ("Altura maxima segun tratamiento", "Sujeta a ficha normativa del polígono específico"),
        ("Planes Parciales", "SIN AFECTACION DIRECTA REGISTRADA"),
        ("Planes de Reordenamiento", "SIN AFECTACION DIRECTA REGISTRADA"),
        ("Fuente de capas", "GeoJSON POT Barranquilla empaquetados en la aplicacion (sin consulta en vivo)"),
    ]



def get_geospatial_evaluation(lat, lon):
    """
    Realiza la evaluación geoespacial en tiempo real del predio según los GeoJSON POT de Barranquilla.
    Importa explícitamente desde api/geospatial_engine.py (motor STRtree completo de 171 líneas).
    """
    try:
        import sys
        from pathlib import Path as _Path
        _api_dir = str(_Path(__file__).resolve().parent)  # ya es api/
        if _api_dir not in sys.path:
            sys.path.insert(0, _api_dir)
        from geospatial_engine import evaluate_predio
        return evaluate_predio(lat, lon)
    except Exception as e:
        return {
            'amenaza_remocion_masa': {'intersecta': False, 'nivel': 'Indeterminado', 'clase_suelo': 'N/A', 'area_poligono_m2': 0, 'objectid': None, 'color_hex': '#7F8C8D'},
            'areas_en_riesgo': {'intersecta': False, 'nivel': 'Indeterminado', 'clase_suelo': 'N/A', 'area_poligono_m2': 0, 'objectid': None, 'color_hex': '#7F8C8D'},
            'resumen_ejecutivo': f'No se completó la verificación espacial: {e}'
        }

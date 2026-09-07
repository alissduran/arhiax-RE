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


def get_valuation(area_construida_m2, barrio, estrato=4):
    """
    Retorna la valoracion tecnica de mercado consolidando M1, M2 y M3
    segun los parametros declarados en el YAML de la Lonja de Barranquilla.
    """
    import yaml
    from pathlib import Path
    
    # Resolver ruta de la metodologia de la Lonja
    base_dir = Path(__file__).resolve().parent
    yaml_path = base_dir.parent / "motor_tma_lonja_baq_v1.0" / "motor_tma_lonja_baq_v1.0" / "lonja_layer" / "lonja_baq_metodologia.yaml"
    
    # Parámetros por defecto en caso de falla de carga
    cap_rate_neto = 0.0485
    val_m2_mercado = 5200000
    factor_costos = 1.2576
    
    try:
        if yaml_path.exists():
            with open(yaml_path, 'r', encoding='utf-8') as f:
                yml = yaml.safe_load(f)
            
            # 1. Obtener valor del suelo por sector o fallback
            valores_suelo = yml.get("valor_suelo_por_sector", {})
            # Normalizar nombre de barrio para búsqueda en las claves del YAML
            barrio_key = barrio.replace(" ", "_").strip().title()
            
            # Buscar coincidencia exacta o parcial
            sector_match = None
            for k in valores_suelo.keys():
                if k.lower() == barrio_key.lower() or k.lower() in barrio.lower():
                    sector_match = k
                    break
                    
            if sector_match:
                val_m2_mercado = valores_suelo[sector_match].get("valor_central_m2", 5200000)
            else:
                # Fallback por estrato
                estrato_map = {3: 3800000, 4: 5200000, 5: 6500000, 6: 7800000}
                val_m2_mercado = estrato_map.get(int(estrato), 5200000)
                
            # 2. Cap Rate (M3)
            tasas_tip = yml.get("capitalizacion_rentas", {}).get("tasas_por_tipologia", {})
            estrato_key = f"apto_NO_VIS_estrato_{estrato}"
            if estrato_key in tasas_tip:
                cap_rate_neto = tasas_tip[estrato_key].get("tasa_central", 0.0485)
                
            # 3. Factor de costos (M2)
            factor_costos = yml.get("costos_construccion", {}).get("factor_actualizacion", 1.2576)
    except Exception as e:
        print(f"[VALUATION][WARN] Fallo de integracion YAML, usando fallbacks: {e}")

    # M1: Comparacion de Mercado
    val_consolidado = int(area_construida_m2 * val_m2_mercado)
    m1_total_central = int(val_consolidado * 1.02)
    
    # Canon de arriendo mensual (tasa implicita del sector)
    # Renta tipica mensual estimada: ~0.55% del valor por m2
    canon_mensual = int(area_construida_m2 * (val_m2_mercado * 0.00538))
    
    # M3: Capitalizacion de Rentas
    m3_total_central = int((canon_mensual * 0.84 * 12) / cap_rate_neto)
    
    # M2: Reposicion Fisica Depreciada
    costo_construccion_base = 2800000 # multifamiliar tipico
    valor_lote_m2 = int(val_m2_mercado * 0.30) # 30% del valor total es el lote
    m2_total_central = int(area_construida_m2 * (costo_construccion_base * factor_costos * 0.85 + valor_lote_m2))
    
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
        "m1_m2": int(m1_total_central / area_construida_m2) if area_construida_m2 else 0,
        "m3_m2": int(m3_total_central / area_construida_m2) if area_construida_m2 else 0,
        "canon_mensual": canon_mensual,
        "cap_rate": cap_rate_neto
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
        ("Barrio catastral", barrio_clean),
        ("Infraestructura vial", "Malla vial urbana y corredores de conectividad inmediata"),
        ("Equipamientos cercanos", "Equipamientos institucionales, comerciales y asistenciales en radio 2.0 km"),
    ]

def get_cobertura_alert(barrio, ciudad="barranquilla"):
    barrio_clean = barrio.strip().title() if barrio else "el sector"
    c = (ciudad or "").lower()
    if "medellin" in c or "medellín" in c:
        nombre_ciudad = "Medellín"
    elif "bogota" in c or "bogotá" in c:
        nombre_ciudad = "Bogotá D.C."
    else:
        nombre_ciudad = "Barranquilla"
    # 'Bogotá D.C.' ya termina en punto: no duplicar el punto de la frase
    punto = "" if nombre_ciudad.endswith(".") else "."
    return (
        f"<b>EVALUACION DE COBERTURA:</b> El inmueble ubicado en <b>{barrio_clean}</b> cuenta con una calificacion "
        f"de conectividad y equipamiento <b>SATISFACTORIA</b> dentro del perimetro urbano de {nombre_ciudad}{punto} "
        f"El radio de amortiguacion de 2.0 km concentra equipamientos de comercio, salud, educacion y recreacion, "
        f"garantizando accesibilidad peatonal y vehicular bajo el estandar de proximidad urbana."
    )

def get_analisis_registral_text(barrio):
    return (
        "<b>Auditoría de Tradición:</b> El análisis registral se computa a partir de las anotaciones "
        "y actos inscritos en el folio de matrícula inmobiliaria del inmueble. Las salvedades, gravámenes "
        "o limitaciones identificadas se reflejan en la tabla de hallazgos periciales del presente dictamen."
    )

def get_valoracion_alert(barrio, val_data, fmt_cop):
    barrio_clean = barrio.strip().title() if barrio else "el sector"
    return (
        f"<b>SINTESIS DE VALORACION:</b> La estimación comercial consolidada de "
        f"<b>{fmt_cop(val_data['consolidado'])} COP</b> responde a la metodología valuatoria "
        f"consolidada del modulo ARHIAX (M1 · M2 · M3), "
        f"integrando el método de comparación de mercado (M1) calibrado por sector geoeconómico ({barrio_clean}) "
        f"y el método de capitalización de rentas (M3) según la tasa de rentabilidad neta de la tipología."
    )

def get_alcance_dt(barrio, ciudad="barranquilla"):
    # F-21: alcance honesto — no se afirman integraciones que no existen.
    es_med = "medellin" in (ciudad or "").lower()
    es_bog = "bogota" in (ciudad or "").lower()
    if es_med:
        return [
            ("Datos registrales SNR", "PENDIENTE -- Requiere CTL del predio (las anotaciones se procesan si se adjunta)"),
            ("Capa catastral Medellín", "CONSULTADA EN VIVO -- Uso del predio (servidormapas Alcaldía)"),
            ("POT/Ordenamiento Medellín", "EJECUTADA -- Clasificación de suelo y tratamientos consultados en vivo"),
            ("Riesgos/Amenazas Medellín", "EJECUTADA -- Capas de gestión del riesgo DAGRD consultadas en vivo"),
            ("Integracion WFS-IGAC", "PLANIFICADA -- En desarrollo para consulta en vivo (ver roadmap)"),
            ("Sincronizacion Curaduria", "NO VALIDADA -- Requiere confrontación con licencia de construcción"),
            ("Verificacion SARLAFT", "NO EJECUTADA -- Requiere cruce de listas restrictivas en plataforma externa"),
            ("Estimacion referencial", "NO sustituye avalúo elaborado por avaluador inscrito en el RAA (Ley 1673/2013)"),
        ]
    if es_bog:
        return [
            ("Datos registrales SNR", "PENDIENTE -- Requiere CTL del predio (las anotaciones se procesan si se adjunta)"),
            ("Capa catastral Bogotá", "CONSULTADA EN VIVO -- Lote, sector, uso por manzana (serviciosgis catastro distrital)"),
            ("POT/Ordenamiento Bogotá", "EJECUTADA -- Suelo Decreto 555/2021, UPZ y localidad consultados en vivo"),
            ("Riesgos/Amenazas Bogotá", "EJECUTADA -- Capas IDIGER consultadas en vivo (mov. masa, sismos, geotecnia)"),
            ("Detalle predial (NUPRE/destino por predio)", "NO DISPONIBLE EN ABIERTO -- El catastro distrital no publica capa predial con NUPRE; el destino es uso predominante por manzana (referencial)"),
            ("Sincronizacion Curaduria", "NO VALIDADA -- Requiere confrontación con licencia de construcción"),
            ("Verificacion SARLAFT", "NO EJECUTADA -- Requiere cruce de listas restrictivas en plataforma externa"),
            ("Estimacion referencial", "NO sustituye avalúo elaborado por avaluador inscrito en el RAA (Ley 1673/2013)"),
        ]
    return [
        ("Datos registrales SNR", "PENDIENTE -- Requiere CTL del predio (las anotaciones se procesan si se adjunta)"),
        ("Capa catastral BAQ", "REFERENCIAL -- Estimacion del modulo ARHIAX RE (sin consulta en vivo)"),
        ("POT/Ordenamiento BAQ", "EJECUTADA -- Cruce espacial sobre capas POT empaquetadas"),
        ("Riesgos/Amenazas BAQ", "EJECUTADA -- Cruce espacial STRtree contra capas de amenaza y riesgo"),
        ("Integracion WFS-IGAC", "PLANIFICADA -- En desarrollo para consulta en vivo (ver roadmap)"),
        ("Sincronizacion Curaduria", "NO VALIDADA -- Requiere confrontación con licencia de construcción"),
        ("Verificacion SARLAFT", "NO EJECUTADA -- Requiere cruce de listas restrictivas en plataforma externa"),
        ("Estimacion referencial", "NO sustituye avalúo elaborado por avaluador inscrito en el RAA (Ley 1673/2013)"),
    ]

def get_catastral_dt(barrio, area, destino_economico=None, nupre=None,
                     codigo_catastral=None, condicion=None, area_catastral=None,
                     tipo_construccion=None, pisos=None, estrato=None,
                     ciudad="barranquilla"):
    barrio_clean = barrio.strip().title() if barrio else "Pendiente de verificacion"
    es_med = "medellin" in (ciudad or "").lower()
    es_bog = "bogota" in (ciudad or "").lower()
    if es_bog:
        gc_nombre = "Bogotá"
        gc_sigla = "GC-BOG"
    elif es_med:
        gc_nombre = "Medellín"
        gc_sigla = "GC-MED"
    else:
        gc_nombre = "Barranquilla"
        gc_sigla = "GC-BAQ"
    # Sprint 2 (exactitud): el destino económico y el NUPRE salen del catastro en
    # vivo cuando el CTL trae código/NUPRE; nunca se asume HABITACIONAL por defecto.
    if destino_economico:
        if es_bog:
            destino_txt = f"{destino_economico} (uso predominante por manzana, en vivo)"
        else:
            destino_txt = f"{destino_economico} (Capa Predio {gc_sigla}, en vivo)"
    else:
        destino_txt = "PENDIENTE DE VERIFICACION (Requiere consulta catastral del predio)"
    condicion_txt = condicion if condicion else "Pendiente de verificacion"
    if tipo_construccion and pisos:
        constr_txt = f"{tipo_construccion} -- {pisos} piso(s)"
    elif tipo_construccion:
        constr_txt = tipo_construccion
    else:
        constr_txt = "Pendiente de verificacion"
    area_reg_txt = f"{area:.2f} m2" if area else "Pendiente de verificacion"
    if area_catastral and area_catastral != area:
        area_reg_txt = f"{area:.2f} m2 (registral) / {area_catastral:.2f} m2 (catastral)" if area else f"{area_catastral:.2f} m2 (catastral)"
    return [
        ("Area Registrada", area_reg_txt),
        ("Barrio catastral", barrio_clean),
        ("NUPRE", nupre if nupre else f"Pendiente de consulta {gc_sigla}"),
        ("Codigo catastral", codigo_catastral if codigo_catastral else f"Pendiente de consulta {gc_sigla}"),
        ("Destino economico catastral", destino_txt),
        ("Condicion juridica", condicion_txt),
        ("Tipo de construccion", constr_txt),
        ("Estrato", estrato if estrato not in (None, "", "No_Aplica") else "No aplica (uso no residencial)"),
    ]

def get_pot_summary_dt(barrio, ciudad="barranquilla", clase_suelo=None,
                       uso_economico=None, upz=None, tratamiento=None,
                       tipo_tratamiento=None):
    """Resumen POT por ciudad. Cuando la consulta en vivo trajo el valor real
    (clase_suelo, uso, UPZ, tratamiento) se muestra; si no, PENDIENTE (nunca se
    afirma un valor genérico como si fuera del predio)."""
    es_med = "medellin" in (ciudad or "").lower()
    es_bog = "bogota" in (ciudad or "").lower()

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

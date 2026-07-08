import math
import datetime

def get_solar_position(lat, lon, dt, tz_offset=-5):
    """
    Calcula la posición del sol (azimut y elevación) para una coordenada, fecha y hora local (UTC-5 por defecto).
    
    lat: Latitud en grados decimales (Norte positivo, Sur negativo)
    lon: Longitud en grados decimales (Este positivo, Oeste negativo)
    dt: Objeto datetime en hora local
    tz_offset: Diferencia horaria con UTC (ej. -5 para Barranquilla)
    
    Retorna: (azimuth, elevation) en grados.
    """
    # 1. Calcular el día del año (N)
    day_of_year = dt.timetuple().tm_yday
    
    # 2. Convertir hora local a hora decimal del día
    decimal_hour = dt.hour + dt.minute / 60.0 + dt.second / 3600.0
    
    # 3. Ángulo fraccional del año (gamma) en radianes
    gamma = (2.0 * math.pi / 365.0) * (day_of_year - 1 + (decimal_hour - 12.0) / 24.0)
    
    # 4. Ecuación del tiempo (eqt) en minutos
    eqt = 229.18 * (0.000075 + 
                    0.001868 * math.cos(gamma) - 
                    0.032077 * math.sin(gamma) - 
                    0.014615 * math.cos(2.0 * gamma) - 
                    0.040849 * math.sin(2.0 * gamma))
    
    # 5. Declinación solar (delta) en radianes
    delta = (0.006918 - 
             0.399912 * math.cos(gamma) + 
             0.070257 * math.sin(gamma) - 
             0.006758 * math.cos(2.0 * gamma) + 
             0.000907 * math.sin(2.0 * gamma) - 
             0.002697 * math.cos(3.0 * gamma) + 
             0.001480 * math.sin(3.0 * gamma))
    
    # 6. Desfase de tiempo solar en minutos
    # Longitud es en grados. La fórmula estándar de la NOAA asume longitud positiva al este.
    # Como Barranquilla está en el oeste (-74.8115), usamos la suma directa al pasar lon.
    time_offset = eqt + 4.0 * lon - 60.0 * tz_offset
    
    # 7. Tiempo Solar Verdadero (tst) en minutos
    tst = decimal_hour * 60.0 + time_offset
    
    # 8. Ángulo horario (ha) en radianes
    ha = math.radians((tst / 4.0) - 180.0)
    
    # Convertir latitud a radianes
    lat_rad = math.radians(lat)
    
    # 9. Ángulo cenital (zenith) y Elevación
    cos_zenith = (math.sin(lat_rad) * math.sin(delta) + 
                  math.cos(lat_rad) * math.cos(delta) * math.cos(ha))
    
    # Prevenir errores de redondeo de punto flotante fuera del rango [-1, 1]
    cos_zenith = max(-1.0, min(1.0, cos_zenith))
    zenith_rad = math.acos(cos_zenith)
    elevation = 90.0 - math.degrees(zenith_rad)
    
    # 10. Azimut solar (medido desde el Norte, en sentido horario)
    # Evitar división por cero si el sol está directamente en el cenit
    if abs(elevation - 90.0) < 0.001:
        azimuth = 180.0
    else:
        cos_azimuth = ((math.sin(delta) - math.sin(lat_rad) * math.cos(zenith_rad)) / 
                       (math.cos(lat_rad) * math.sin(zenith_rad)))
        cos_azimuth = max(-1.0, min(1.0, cos_azimuth))
        azimuth_deg = math.degrees(math.acos(cos_azimuth))
        
        # Ajuste de cuadrante según el ángulo horario (ha)
        if ha > 0:
            azimuth = 360.0 - azimuth_deg
        else:
            azimuth = azimuth_deg
            
    return round(azimuth, 2), round(elevation, 2)

def analyze_facade_exposure(solar_az, solar_el, facade_az, obstructions=None):
    """
    Analiza la incidencia solar en una fachada específica y si cae en sol o sombra.
    
    solar_az: Azimut del sol (0-360°)
    solar_el: Elevación del sol (grados)
    facade_az: Azimut de la fachada (0-360°)
    obstructions: Lista de tuplas (start_az, end_az, max_el) definiendo obstáculos vecinos.
                  Ej. [(240, 280, 30)] bloquea el sol si está entre 240° y 280° de azimut
                  y a menos de 30° de elevación.
                  
    Retorna: (status, description)
             status: "Sol Directo", "Sombra (Obstáculo)", "Sombra (Orientación)", "Noche"
    """
    if solar_el <= 0:
        return "Noche", "El sol se encuentra bajo el horizonte."
        
    # Verificar si el sol está detrás de la fachada (la fachada cubre 180° frontales)
    # Ángulo relativo entre el sol y la fachada
    angle_diff = abs(solar_az - facade_az) % 360
    if angle_diff > 180:
        angle_diff = 360 - angle_diff
        
    # Si el sol incide con un ángulo mayor a 90° respecto a la normal de la fachada, está detrás de la misma
    if angle_diff > 90:
        return "Sombra (Orientación)", "El sol está detrás del inmueble (fachada opuesta)."
        
    # Verificar obstrucciones físicas definidas
    if obstructions:
        for start_az, end_az, max_el in obstructions:
            # Manejar cruce por cero en azimut (ej. 350 a 10)
            if start_az <= end_az:
                in_az_range = (start_az <= solar_az <= end_az)
            else:
                in_az_range = (solar_az >= start_az or solar_az <= end_az)
                
            if in_az_range and solar_el <= max_el:
                return "Sombra (Obstáculo)", f"Obstrucción física de estructura vecina (sector {start_az}°-{end_az}°)."
                
    # Calcular ángulo de incidencia (para metadatos de radiación teórica)
    # 0° = incidencia perfectamente perpendicular
    incidence_angle = round(angle_diff, 1)
    return "Sol Directo", f"Exposición directa a la radiación solar. Ángulo de incidencia: {incidence_angle}°."

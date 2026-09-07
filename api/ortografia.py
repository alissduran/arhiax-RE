# -*- coding: utf-8 -*-
"""
ARHIAX RE — Corrector ortográfico en español para el texto del dictamen
========================================================================
Los textos del compilador se escribieron sin tildes para evitar problemas de
encoding. Este módulo restaura la ortografía correcta (tildes) en tiempo de
renderizado, sin tocar las cadenas fuente (que mantienen compatibilidad con
tests y con los motores).

Cobertura:
  1. Diccionario curado de palabras inequívocas del dominio (área, código,
     matrícula, sísmico, jurídico, geotécnico...).
  2. Regla productiva: toda palabra terminada en 'ion' (…) es aguda terminada
     en -n y lleva tilde en la i: 'direccion' -> 'dirección',
     'construccion' -> 'construcción', 'avion' -> 'avión' (con excepciones
     como 'guion'/'ion').
  3. Preservación de mayúsculas ('ANALISIS' -> 'ANÁLISIS') y de las etiquetas
     HTML (<b>, <link>, <font>...) que ReportLab interpreta.

Solo se corrigen palabras SIN ambigüedad en este dominio; las ambiguas
('esta/está', 'si/sí', 'como/cómo', 'mas/más') se dejan como están para no
introducir errores.
"""
import re

# Palabra sin tilde (minúscula) -> correcta (minúscula). Solo términos
# inequívocos del dominio del dictamen.
_CORRECCIONES = {
    # -álisis / esdrújulas frecuentes
    "analisis": "análisis", "analitico": "analítico", "analitica": "analítica",
    "analiticamente": "analíticamente",
    "area": "área", "areas": "áreas",
    "codigo": "código", "codigos": "códigos",
    "numero": "número", "numeros": "números",
    "matricula": "matrícula", "matriculas": "matrículas",
    "circulo": "círculo", "circulos": "círculos",
    "regimen": "régimen",
    "pagina": "página", "paginas": "páginas",
    "indice": "índice", "indices": "índices",
    "ambito": "ámbito",
    "unico": "único", "unica": "única", "unicamente": "únicamente",
    "maximo": "máximo", "maxima": "máxima", "maximos": "máximos", "maximas": "máximas",
    "minimo": "mínimo", "minima": "mínima",
    "ultima": "última", "ultimo": "último", "ultimas": "últimas", "ultimos": "últimos",
    "proximo": "próximo", "proxima": "próxima", "proximos": "próximos",
    "proximidad": "proximidad",
    # -ico/-ica esdrújulas típicas del dominio
    "tecnico": "técnico", "tecnica": "técnica", "tecnicos": "técnicos", "tecnicas": "técnicas",
    "tecnologicamente": "tecnológicamente",
    "juridico": "jurídico", "juridica": "jurídica", "juridicos": "jurídicos", "juridicas": "jurídicas",
    "sismico": "sísmico", "sismica": "sísmica", "sismicos": "sísmicos",
    "hidrologico": "hidrológico", "hidrologica": "hidrológica",
    "geologico": "geológico", "geologica": "geológica", "geologicas": "geológicas",
    "geotecnico": "geotécnico", "geotecnica": "geotécnica",
    "geografico": "geográfico", "geografica": "geográfica", "geograficas": "geográficas",
    "topografico": "topográfico", "topograficos": "topográficos",
    "publico": "público", "publica": "pública", "publicos": "públicos", "publicas": "públicas",
    "automatico": "automático", "automatica": "automática", "automaticamente": "automáticamente",
    "economico": "económico", "economica": "económica", "economicos": "económicos", "economicas": "económicas",
    "economia": "economía",
    "catastral": "catastral",
    "predial": "predial",
    "registral": "registral",
    "administrativo": "administrativo",
    "electro": "electro",
    # verbos en pasado (el motor ...ó)
    "identifico": "identificó", "detecto": "detectó", "genero": "generó",
    "consulto": "consultó", "analizo": "analizó", "ejecuto": "ejecutó",
    "realizo": "realizó", "encontro": "encontró", "verifico": "verificó",
    "cruzo": "cruzó", "obtuvo": "obtuvo", "resolvio": "resolvió",
    "calculos": "cálculos",
    # miscelánea inequívoca
    "segun": "según",
    "dia": "día", "dias": "días",
    "categoria": "categoría", "categorias": "categorías",
    "fotografia": "fotografía",
    "energia": "energía",
    "periodo": "período",
    "vehiculo": "vehículo", "vehiculos": "vehículos",
    "geodesica": "geodésica", "geodesico": "geodésico",
    "metrica": "métrica", "metricas": "métricas", "metricamente": "métricamente",
    "critico": "crítico", "critica": "crítica", "criticos": "críticos",
    "tipologia": "tipología", "tipologias": "tipologías",
    "avaluo": "avalúo", "avaluos": "avalúos",
    "curaduria": "curaduría", "curadurias": "curadurías",
    "poligono": "polígono", "poligonos": "polígonos",
    "hectareas": "hectáreas", "centimetros": "centímetros",
    "bogota": "bogotá", "medellin": "medellín",
    "especifico": "específico", "especifica": "específica", "especificos": "específicos", "especificas": "específicas",
    "urbanistico": "urbanístico", "urbanistica": "urbanística", "urbanisticos": "urbanísticos", "urbanisticas": "urbanísticas",
    "predominante": "predominante", "incidencia": "incidencia",
    "simulacion": "simulación",
    "silenciosamente": "silenciosamente",
    "tambien": "también",
    "aqui": "aquí",
    "allí": "allí",
    "ultimo": "último",
    "sobre": "sobre",
    "transito": "tránsito",
    "juridico": "jurídico",
}

# Palabras terminadas en 'ion' que NO llevan tilde en la i (excepciones).
_EXCEPCIONES_ION = {"guion", "ion", "pion"}


def _corregir_token(token):
    """Corrige un token sin etiquetas. Devuelve el token corregido."""
    if not token or len(token) < 2:
        return token
    lower = token.lower()
    if any(ch in lower for ch in "ÁÉÍÓÚáéíóú"):
        return token  # ya tiene tilde (o es otra cosa)
    correcto = _CORRECCIONES.get(lower)
    if correcto is None:
        # Regla productiva -ión (agudas terminadas en -n)
        if lower.endswith("ion") and lower not in _EXCEPCIONES_ION and len(lower) >= 5:
            correcto = lower[:-3] + "ión"
    if correcto is None:
        return token
    # Preservar mayúsculas: token original
    if token == token.upper():
        return correcto.upper()
    if token[:1].isupper():
        return correcto[0].upper() + correcto[1:]
    return correcto


_SEGMENTO = re.compile(r"(<[^>]*>|[A-Za-zÁÉÍÓÚáéíóúÑñ]+|[^A-Za-zÁÉÍÓÚáéíóúÑñ<]+)")
_RE_URL = re.compile(r"(?:https?://|www\.)[^\s<>\"'\)]+", re.IGNORECASE)


def corregir_es(texto):
    """Corrige la ortografía (tildes) de un texto plano o con etiquetas HTML
    simples, sin alterar las etiquetas ni las URLs (un 'medellin' dentro de
    'www.medellin.gov.co' no debe acentuarse)."""
    if not texto or not isinstance(texto, str):
        return texto
    # Proteger URLs para no acentuar palabras dentro de dominios/rutas
    urls = _RE_URL.findall(texto)
    marcado = texto
    for i, u in enumerate(urls):
        marcado = marcado.replace(u, "\x00URL{}\x00".format(i), 1)
    partes = _SEGMENTO.findall(marcado)
    salida = []
    for p in partes:
        if p.startswith("<") or "\x00" in p or not re.match(r"^[A-Za-zÁÉÍÓÚáéíóúÑñ]+$", p):
            salida.append(p)
        else:
            salida.append(_corregir_token(p))
    resultado = "".join(salida)
    for i, u in enumerate(urls):
        resultado = resultado.replace("\x00URL{}\x00".format(i), u, 1)
    return resultado

# -*- coding: utf-8 -*-
"""
ARHIAX RE — Edificabilidad y Altura Máxima (Norma Urbanística) — Sprint 3
=========================================================================
Entrega los parámetros de edificabilidad del predio según la norma urbanística
de cada ciudad (tratamiento, índice de construcción, densidad, altura máxima en
pisos) y confronta con lo ya construido según el catastro — detectando el caso
típico de "construyeron 20 pisos donde la norma solo permitía 11".

Fuentes oficiales verificadas EN VIVO:
  * Barranquilla : capa POT 'Tratamientos urbanísticos' (planeación) de la
                   Alcaldía — campo `altura_maxima` en PISOS (p. ej. '11',
                   '40') o 'Plan Parcial' cuando la altura la fija un plan.
  * Medellín     : capa VM_22_Tratamientos_Urbanos (servidormapas, POT
                   Acuerdo 48 de 2014) — `indiceconstruccmax`, `densidadmax`,
                   `franjabase`, `alturanormativa` (pisos cuando el polígono
                   la expone; la capa VM_28 no publica altura numérica).
  * Bogotá D.C.  : SIN capa abierta de pisos máximos. La altura se define en
                   la ficha normativa de la UPZ (SDP — Decreto 555/2021 y UPZ
                   adoptadas). El dictamen remite a la consulta oficial y NO
                   afirma un número (regla de honestidad).

Advertencias incorporadas en el texto: la altura de la capa es referencial con
fecha de la norma; la licencia de construcción aprobada puede tener derechos
adquiridos y la norma puede estar en revisión (p. ej. el POT de Medellín en
2025-2026). La palabra final sobre una licencia es de la curaduría/planeación.
"""
import re

from reportlab.lib import colors

_NA = ("", "N/A", "N/D", "NO APLICA", "NO REGISTRA", "NO APLICA (N/A)")

# Portales oficiales para la verificación final por ciudad (deep-links)
_PORTAL_OFICIAL = {
    "barranquilla": ("miciudad.barranquilla.gov.co",
                     "https://miciudad.barranquilla.gov.co/gis"),
    "medellin": ("servidormapas Alcaldía de Medellín",
                 "https://www.medellin.gov.co/servidormapas"),
    "bogota": ("SDP / Mapas Bogotá",
               "https://mapas.bogota.gov.co"),
    "pasto": ("Alcaldía de Pasto / Planeación",
              "https://www.pasto.gov.co"),
}


def _parse_pisos(v):
    """Interpreta un valor como número de pisos: '11', 11, '11.0', '20' -> int.
    Devuelve None si no es numérico (N/A, Plan Parcial, texto...)."""
    if v is None:
        return None
    s = str(v).strip()
    if not s or s.upper() in _NA or "plan parcial" in s.lower():
        return None
    s = s.replace(",", ".").split()[0] if s.split() else s
    try:
        f = float(s)
        if f >= 1 and f == int(f):
            return int(f)
        return int(f) if f >= 1 else None
    except ValueError:
        return None


def altura_permitida(ciudad, ent2):
    """Altura normativa máxima del predio.

    Devuelve (pisos, tipo, texto):
      pisos: int si la capa expone un número (pisos) | None
      tipo : 'pisos' | 'plan_parcial' | 'franja' | 'ficha_upz' | 'sin_dato'
      texto: descripción corta para la tabla del dictamen.
    """
    e = ent2 or {}
    ciudad = (ciudad or "barranquilla").lower().strip()

    if ciudad == "medellin":
        p = _parse_pisos(e.get("altura_normativa"))
        if p:
            return p, "pisos", "Hasta {} pisos (POT Medellín)".format(p)
        franja = (e.get("franja_altura") or "").strip()
        if franja and franja.upper() not in _NA:
            return None, "franja", "Definida por franja de altura: {}".format(franja)
        return None, "sin_dato", None

    if ciudad == "bogota":
        # No hay capa abierta de pisos máximos en Bogotá: la altura se fija en
        # la ficha normativa de la UPZ (SDP). Nunca se inventa un número.
        return None, "ficha_upz", None

    if ciudad == "pasto":
        # El geoportal de Pasto publica la edificabilidad por predio en
        # 'tratamiento_urbanistico' (p. ej. "PEMP - 4 pisos - 11,20 metros"):
        # pasto_territorio la parsea y la deja en entorno['altura_maxima'].
        p = _parse_pisos(e.get("altura_maxima"))
        if p:
            return p, "pisos", "Hasta {} pisos (POT Pasto)".format(p)
        txt = (e.get("edificabilidad_texto") or "").strip()
        if txt and txt.upper() not in _NA:
            return None, "texto", txt
        return None, "ficha_pot", None

    # Barranquilla (default)
    am = (e.get("altura_maxima") or "").strip()
    if not am or am.upper() in _NA:
        return None, "sin_dato", None
    if "plan parcial" in am.lower():
        return None, "plan_parcial", "Sujeta a Plan Parcial (ver ficha del plan)"
    p = _parse_pisos(am)
    if p:
        return p, "pisos", "Hasta {} pisos (POT Barranquilla)".format(p)
    return None, "texto", am


def _texto_pisos_construidos(pisos_construidos, construction_status=None):
    """03H.2: distinguir 'sin construcción' (NO_MATCH) de 'fuente no disponible'.

    03I.1 · F12 (hallazgo real de la corrida Golden con el CTL original): con el
    punto geocodificado de la dirección oficial la capa 310 respondió sin features
    y el dictamen imprimía "capa de construcción consultada sin edificación
    registrada en el punto" — para un inmueble que el MISMO dictamen identifica
    como apartamento en propiedad horizontal (unidad 430, matrícula 040-646406).
    Una respuesta sin features NO prueba que no exista edificación: el punto puede
    caer en la vía (el geocodificador devuelve el eje de la dirección). Se declara
    la ausencia de REGISTRO en la capa, sin afirmar ausencia de construcción.
    """
    pisos_ok = _parse_pisos(pisos_construidos)
    if pisos_ok:
        return "{} piso(s)".format(pisos_ok)
    if construction_status == "SOURCE_UNAVAILABLE":
        return ("PENDIENTE — fuente de construcción no disponible en esta "
                "ejecución.")
    if construction_status == "NOT_EVALUATED":
        return "PENDIENTE DE VERIFICACIÓN (capa de construcción no consultada)"
    if construction_status == "NO_MATCH":
        return ("N/D — la capa de construcción no devolvió registro en el punto "
                "consultado (no se afirma ausencia de edificación)")
    return "PENDIENTE DE VERIFICACIÓN"


def filas_edificabilidad(ciudad, ent2, pisos_construidos, construction_status=None):
    """Filas (label, valor) para la tabla 'Edificabilidad y Altura Máxima'."""
    e = ent2 or {}
    ciudad = (ciudad or "barranquilla").lower().strip()
    pisos_ok = _parse_pisos(pisos_construidos)
    filas = []

    if ciudad == "medellin":
        filas.append(("Tratamiento urbanístico",
                      (e.get("tratamiento") or "N/D") +
                      ((" (polígono {})".format(e["codigo_tratamiento"]))
                       if e.get("codigo_tratamiento") else "")))
        filas.append(("Índice de construcción máx.",
                      e.get("indice_construccion_max") or "N/D"))
        filas.append(("Densidad máx. (viv/ha, POT)",
                      e.get("densidad_max") or "N/D"))
        filas.append(("Franja de altura",
                      e.get("franja_altura") or "N/D"))
        _, _, txt_alt = altura_permitida(ciudad, e)
        filas.append(("Altura normativa máxima", txt_alt or "N/D"))
    elif ciudad == "bogota":
        filas.append(("UPZ (Unidad de Planeamiento Zonal)",
                      e.get("upz") or "N/D"))
        _trat_bog = (e.get("tratamiento") or "").strip()
        _suelo_bog = (e.get("clase_suelo") or "").strip()
        _trat_bog_txt = " / ".join(x for x in (_trat_bog, _suelo_bog) if x) or "N/D"
        filas.append(("Tratamiento / suelo (Decreto 555/2021)", _trat_bog_txt))
        filas.append(("Altura normativa máxima",
                      "Ficha normativa de la UPZ (SDP) — consulta oficial requerida"))
    elif ciudad == "pasto":
        filas.append(("Comuna / corregimiento", e.get("comuna") or "N/D"))
        filas.append(("Tratamiento / suelo (POT Pasto)",
                      "Consulta en Planeación Pasto (sin capa en vivo verificada)"))
        filas.append(("Altura normativa máxima",
                      "Ficha normativa del POT Pasto (Planeación) — consulta oficial requerida"))
    else:
        filas.append(("Tratamiento urbanístico",
                      (e.get("tratamiento") or "N/D") +
                      ((" ({})".format(e["tipo_tratamiento"]))
                       if e.get("tipo_tratamiento") else "")))
        _, _, txt_alt = altura_permitida(ciudad, e)
        filas.append(("Altura normativa máxima", txt_alt or "N/D"))

    # Pisos construidos (catastro) — común a todas las ciudades
    filas.append(("Pisos construidos (catastro)",
                  _texto_pisos_construidos(pisos_construidos, construction_status)))

    # Confrontación construido vs. permitido
    estado, texto = _confrontacion(ciudad, e, pisos_construidos, construction_status)
    filas.append(("Confrontación (construido vs. norma)", texto))
    return filas


def _confrontacion(ciudad, ent2, pisos_construidos, construction_status=None):
    """Compara pisos construidos con la altura permitida.

    Devuelve (estado, texto): estado en
    'exceso' | 'dentro' | 'pendiente' | 'pendiente_fuente'
    | 'sin_registro_construccion' | 'sin_norma'.

    03I.1 · F12: la ausencia de registro en la capa de construcción NO es "no hay
    edificación" ni habilita aplicar la norma "para desarrollo nuevo": el punto
    geocodificado puede corresponder a la vía.
    """
    permitido, tipo, _ = altura_permitida(ciudad, ent2)
    construidos = _parse_pisos(pisos_construidos)
    if construidos is None:
        if construction_status == "SOURCE_UNAVAILABLE":
            return "pendiente_fuente", (
                "No se compara: la fuente de construcción (capa catastral) no "
                "estuvo disponible en esta ejecución.")
        if construction_status in ("NOT_EVALUATED", None):
            return "pendiente", (
                "No se compara: la capa de construcción no se consultó en esta "
                "ejecución.")
        # NO_MATCH: la capa respondió SIN REGISTRO en el punto consultado. No se
        # afirma ausencia de edificación (el punto puede caer en la vía) ni se
        # aplica la norma de desarrollo nuevo.
        return "sin_registro_construccion", (
            "No se compara: la capa de construcción no devolvió registro en el "
            "punto geocodificado (el punto puede corresponder a la vía o el "
            "registro estar asociado a la unidad predial). No se afirma ausencia "
            "de edificación ni lote disponible; verificar la construcción por "
            "código catastral / unidad predial.")
    if permitido is None:
        if tipo == "ficha_upz":
            return "pendiente", (
                "No se compara: la altura permitida requiere la ficha normativa "
                "de la UPZ (SDP) / consulta urbanística oficial")
        if tipo == "ficha_pot":
            return "pendiente", (
                "No se compara: la altura permitida requiere la ficha normativa "
                "del POT Pasto (Planeación) / consulta urbanística oficial")
        if tipo == "plan_parcial":
            return "pendiente", (
                "No se compara: la altura la define el Plan Parcial del polígono "
                "(verificar ficha del plan en la Alcaldía)")
        if tipo == "franja":
            return "pendiente", (
                "No se compara en pisos: la altura se define por franja/ficha "
                "normativa del polígono (verificar en Planeación)")
        return "sin_norma", (
            "PENDIENTE: la norma del polígono no expone altura numérica en las "
            "capas abiertas; verificar en la autoridad de planeación / curaduría")
    if construidos > permitido:
        return "exceso", (
            "POSIBLE EXCESO: {} pisos construidos frente a un máximo normativo "
            "de {} pisos".format(construidos, permitido))
    return "dentro", (
        "Dentro de la altura normativa aparente: {} pisos (máx. {})".format(
            construidos, permitido))


def hallazgo_exceso_altura(ciudad, ent2, pisos_construidos):
    """Hallazgo H-URB cuando lo construido excede la altura normativa.

    Devuelve la tupla de hallazgo ARHIAX (severidad, color, fondo, título,
    fuente, descripción, implicación) o None si no hay exceso verificable."""
    permitido = altura_permitida(ciudad, ent2)[0]
    construidos = _parse_pisos(pisos_construidos)
    if not permitido or not construidos or construidos <= permitido:
        return None
    nombre = {"barranquilla": "Barranquilla", "medellin": "Medellín",
              "bogota": "Bogotá D.C.", "pasto": "Pasto"}.get((ciudad or "").lower(), "la ciudad")
    return (
        "ALTO",
        colors.HexColor("#D92C2C"),
        colors.HexColor("#FFF0F0"),
        "H-URB | Posible Exceso de Altura: {} pisos construidos vs. norma hasta {} pisos".format(
            construidos, permitido),
        "POT {} -- Norma urbanística".format(nombre),
        ("La edificación registrada en catastro ({0} pisos) supera la altura "
         "máxima normativa del polígono ({1} pisos) según las capas oficiales "
         "del POT de {2}. Esta situación puede implicar unidades sin licencia, "
         "sanciones urbanísticas o imposibilidad de legalizar la totalidad "
         "construida.").format(construidos, permitido, nombre),
        ("Verificación OBLIGATORIA ante la curaduría urbana / autoridad de "
         "planeación: confrontar la licencia de construcción y la ficha "
         "normativa del polígono. Impacto directo en titularidad de unidades, "
         "avalúos y estructuración de garantías."))


def filas_licencia(lic):
    """Filas (label, valor) con los datos autorizados por la licencia (mejora 5).
    Solo incluye lo que el analizador identificó con certeza; el resto N/D."""
    l = lic or {}
    filas = []
    num = (l.get("numero_licencia") or "").strip()
    filas.append(("N° Licencia de construcción", num or "NO REGISTRA — no se adjuntó"))
    if num:
        if l.get("modalidad"):
            filas.append(("Modalidad", str(l["modalidad"]).capitalize()))
        if l.get("curaduria"):
            filas.append(("Curaduría urbana / entidad", "Curaduría {}".format(l["curaduria"])))
        if l.get("pisos_aprobados"):
            filas.append(("Pisos autorizados por licencia",
                          "{} piso(s)".format(l["pisos_aprobados"])))
        if l.get("altura_aprobada_m"):
            filas.append(("Altura autorizada",
                          "{} m".format(l["altura_aprobada_m"])))
        if l.get("area_aprobada_m2"):
            filas.append(("Área autorizada",
                          "{} m²".format(l["area_aprobada_m2"])))
        if l.get("fecha_expedicion"):
            filas.append(("Fecha de expedición", l["fecha_expedicion"]))
    return filas


def confrontacion_con_licencia(ciudad, ent2, pisos_construidos, lic):
    """Confrontación total: lo LICENCIADO vs lo CONSTRUIDO vs la norma POT.

    La licencia de construcción es la autorización CONCRETA del proyecto: si el
    analizador identificó los pisos autorizados, tiene prioridad sobre la capa
    POT (una licencia puede amparar más pisos por derechos adquiridos o norma
    anterior). Devuelve (estado, texto) con estado en
    'exceso_licencia' | 'dentro_licencia' | 'licencia_sin_pisos' | 'sin_licencia'.
    """
    lic = lic or {}
    pisos_lic = lic.get("pisos_aprobados")
    construidos = _parse_pisos(pisos_construidos)

    if not (lic.get("numero_licencia") or pisos_lic):
        return "sin_licencia", None

    if not pisos_lic:
        return "licencia_sin_pisos", (
            "Licencia adjuntada, pero no se identificó el número de pisos "
            "autorizados en el texto: revisar manualmente la licencia.")

    if construidos is None:
        return "sin_construccion_lic", (
            "Catastro sin pisos registrados: aplicar los {} pisos autorizados "
            "por la licencia como parámetro del proyecto.".format(pisos_lic))

    if construidos > pisos_lic:
        return "exceso_licencia", (
            "POSIBLE EXCESO FRENTE A LA LICENCIA: {} pisos construidos (catastro) "
            "superan los {} pisos autorizados por la licencia adjuntada.".format(
                construidos, pisos_lic))

    # construidos <= licenciados: conforme a licencia; contrastar con la capa POT
    permitido = altura_permitida(ciudad, ent2)[0]
    if permitido and pisos_lic > permitido:
        return "dentro_licencia", (
            "Dentro de la licencia ({} pisos construidos de {} autorizados). La "
            "licencia ampara más pisos que la capa POT actual ({}): posibles "
            "derechos adquiridos o norma anterior — verificar vigencia de la "
            "licencia y su ejecución.".format(construidos, pisos_lic, permitido))
    return "dentro_licencia", (
        "Dentro de la licencia: {} pisos construidos de {} autorizados "
        "(coherente con la norma POT).".format(construidos, pisos_lic))


def hallazgo_exceso_licencia(ciudad, ent2, pisos_construidos, lic):
    """Hallazgo H-LIC cuando lo construido excede lo LICENCIADO (mejora 5).

    Es la alerta del caso 'la constructora edificó 20 pisos donde la licencia
    autorizaba 11' aunque la capa POT no lo reflejara. None si no hay exceso
    verificable (nunca se afirma sin pisos licenciados identificados)."""
    lic = lic or {}
    pisos_lic = lic.get("pisos_aprobados")
    construidos = _parse_pisos(pisos_construidos)
    if not pisos_lic or not construidos or construidos <= pisos_lic:
        return None
    nombre = {"barranquilla": "Barranquilla", "medellin": "Medellín",
              "bogota": "Bogotá D.C.", "pasto": "Pasto"}.get((ciudad or "").lower(), "la ciudad")
    num_lic = (lic.get("numero_licencia") or "licencia adjuntada").strip()
    return (
        "ALTO",
        colors.HexColor("#D92C2C"),
        colors.HexColor("#FFF0F0"),
        "H-LIC | Exceso frente a Licencia: {} pisos construidos vs. {} autorizados".format(
            construidos, pisos_lic),
        "Licencia de construcción -- {}".format(num_lic),
        ("La edificación registrada en catastro ({0} pisos) supera los {1} pisos "
         "autorizados por la licencia de construcción adjuntada al caso "
         "({2}). Un exceso frente a la licencia puede implicar unidades sin "
         "licencia, sanciones urbanísticas o imposibilidad de legalizar la "
         "totalidad construida en {3}.").format(construidos, pisos_lic, num_lic, nombre),
        ("Verificación OBLIGATORIA ante la curaduría urbana: confrontar la "
         "licencia, sus planos aprobados y la obra ejecutada. Impacto directo "
         "en la titularidad de unidades, avalúos y estructuración de garantías."))


def fuente_norma_texto(ciudad, ent2=None):
    """Texto de fuente normativa y fecha para la tabla (honesto, con la norma)."""
    e = ent2 or {}
    ciudad = (ciudad or "barranquilla").lower().strip()
    if ciudad == "medellin":
        fecha = (e.get("fecha_norma") or "").strip()
        base = "POT Medellín Acuerdo 48 de 2014 -- servidormapas, capa VM_22 Tratamientos Urbanos"
        if fecha:
            base += " (polígono adoptado el {})".format(fecha)
        return base + (". En revisión del POT 2025-2026: confirmar vigencia en Planeación." if not fecha else ".")
    if ciudad == "bogota":
        return ("POT Bogotá Decreto 555 de 2021 -- la altura se fija por ficha "
                "normativa de la UPZ (SDP). Consulta oficial: ")
    if ciudad == "pasto":
        return ("POT de Pasto (Nariño) -- sin capa de altura en abierto verificada; "
                "la altura se fija por ficha normativa (Planeación). Consulta oficial: ")
    return ("POT Barranquilla -- capa oficial 'Tratamientos urbanísticos' "
            "(datos abiertos Alcaldía). Consulta oficial: ")


def link_oficial(ciudad):
    """(nombre, url) del portal oficial de verificación por ciudad."""
    return _PORTAL_OFICIAL.get((ciudad or "barranquilla").lower(),
                               _PORTAL_OFICIAL["barranquilla"])

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


def filas_edificabilidad(ciudad, ent2, pisos_construidos):
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
    else:
        filas.append(("Tratamiento urbanístico",
                      (e.get("tratamiento") or "N/D") +
                      ((" ({})".format(e["tipo_tratamiento"]))
                       if e.get("tipo_tratamiento") else "")))
        _, _, txt_alt = altura_permitida(ciudad, e)
        filas.append(("Altura normativa máxima", txt_alt or "N/D"))

    # Pisos construidos (catastro) — común a todas las ciudades
    filas.append(("Pisos construidos (catastro)",
                  "{} piso(s)".format(pisos_ok) if pisos_ok else
                  "N/D -- sin pisos registrados en catastro (posible lote sin edificacion)"))

    # Confrontación construido vs. permitido
    estado, texto = _confrontacion(ciudad, e, pisos_construidos)
    filas.append(("Confrontación (construido vs. norma)", texto))
    return filas


def _confrontacion(ciudad, ent2, pisos_construidos):
    """Compara pisos construidos con la altura permitida.

    Devuelve (estado, texto): estado en
    'exceso' | 'dentro' | 'pendiente' | 'sin_construccion' | 'sin_norma'."""
    permitido, tipo, _ = altura_permitida(ciudad, ent2)
    construidos = _parse_pisos(pisos_construidos)
    if construidos is None:
        return "sin_construccion", (
            "PENDIENTE: catastro sin pisos registrados (aplica la norma para "
            "desarrollo nuevo según la altura permitida)")
    if permitido is None:
        if tipo == "ficha_upz":
            return "pendiente", (
                "No se compara: la altura permitida requiere la ficha normativa "
                "de la UPZ (SDP) / consulta urbanística oficial")
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
              "bogota": "Bogotá D.C."}.get((ciudad or "").lower(), "la ciudad")
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
    return ("POT Barranquilla -- capa oficial 'Tratamientos urbanísticos' "
            "(datos abiertos Alcaldía). Consulta oficial: ")


def link_oficial(ciudad):
    """(nombre, url) del portal oficial de verificación por ciudad."""
    return _PORTAL_OFICIAL.get((ciudad or "barranquilla").lower(),
                               _PORTAL_OFICIAL["barranquilla"])

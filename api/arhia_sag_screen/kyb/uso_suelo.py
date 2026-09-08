"""Análisis de uso del suelo / polígono del POT — qué se puede y qué no se puede hacer.

Complementa el expediente con la capa de **ordenamiento territorial**: según el polígono del
Plan de Ordenamiento Territorial (POT) en el que está el predio, determina el **uso del suelo**,
la **edificabilidad** (índices, altura, densidad), los **retiros/restricciones** y — lo clave —
si una **actividad consultada** (comercial, entretenimiento, residencial, industrial…) está
**permitida o no**. Base legal: Ley 388/1997 (ordenamiento territorial) + acuerdo POT municipal.
"""
from dataclasses import dataclass
from typing import Optional, Tuple

from arhia_title.contracts import Predio

BASE_POT = "Ley 388/1997 (ordenamiento territorial) + Acuerdo del POT municipal."


@dataclass(frozen=True)
class ZonaPOT:
    codigo: str
    nombre: str
    uso_principal: str
    usos_permitidos: Tuple[str, ...]
    usos_no_permitidos: Tuple[str, ...]
    edificabilidad: dict
    retiros: str
    restricciones: Tuple[str, ...]
    base: str = BASE_POT
    fuente: str = "POT municipal"
    vigencia: str = "2026"


CATALOGO_ZONAS = {
    "R1": ZonaPOT("R1", "Residencial consolidado", "residencial",
        usos_permitidos=("residencial", "comercio_basico", "servicios"),
        usos_no_permitidos=("industrial", "entretenimiento_alto_impacto", "bodegaje"),
        edificabilidad={"indice_construccion": 1.8, "indice_ocupacion": 0.7, "altura_max": 5,
                        "densidad": "60 viv/ha"},
        retiros="3 m lateral · 5 m frontal", restricciones=("zona_no_inundable",)),
    "C1": ZonaPOT("C1", "Comercial central", "comercio",
        usos_permitidos=("comercio", "servicios", "mixto_residencial_comercial", "entretenimiento"),
        usos_no_permitidos=("industrial_pesado", "bodegaje"),
        edificabilidad={"indice_construccion": 2.5, "indice_ocupacion": 0.8, "altura_max": 8,
                        "densidad": "alto"},
        retiros="0 m (uso continuo) · 3 m si torre", restricciones=("reserva_vial",)),
    "E1": ZonaPOT("E1", "Equipamiento / entretenimiento", "equipamiento",
        usos_permitidos=("entretenimiento", "comercio", "servicios", "cultural"),
        usos_no_permitidos=("residencial_de_menor", "industrial", "bodegaje"),
        edificabilidad={"indice_construccion": 1.2, "indice_ocupacion": 0.6, "altura_max": 3,
                        "densidad": "bajo"},
        retiros="6 m perimetral", restricciones=("estudio_impacto",)),
    "M1": ZonaPOT("M1", "Mixto (residencial + comercio)", "mixto",
        usos_permitidos=("residencial", "comercio", "servicios", "oficinas"),
        usos_no_permitidos=("industrial", "entretenimiento_alto_impacto"),
        edificabilidad={"indice_construccion": 2.2, "indice_ocupacion": 0.75, "altura_max": 6,
                        "densidad": "80 viv/ha"},
        retiros="3 m", restricciones=("no_afectacion_rio",)),
    "I1": ZonaPOT("I1", "Industrial / logístico", "industrial",
        usos_permitidos=("industrial", "bodegaje", "logistica"),
        usos_no_permitidos=("residencial", "comercio_minorista"),
        edificabilidad={"indice_construccion": 1.5, "indice_ocupacion": 0.6, "altura_max": 4,
                        "densidad": "n/a"},
        retiros="8 m", restricciones=("mitigacion_ambiental",)),
    "PR": ZonaPOT("PR", "Protección / riesgo", "proteccion",
        usos_permitidos=("parque", "recreacion_pasiva", "equipamiento_punto"),
        usos_no_permitidos=("residencial", "comercial", "industrial", "entretenimiento", "edificacion_nueva"),
        edificabilidad={"indice_construccion": 0.1, "indice_ocupacion": 0.1, "altura_max": 1,
                        "densidad": "n/a"},
        retiros="no edificable", restricciones=("amenaza_inundacion", "amenaza_remocion", "ronda_hidrica")),
}


@dataclass(frozen=True)
class FichaUsoSuelo:
    predio_id: str
    zona: str                      # código de zona (capa de suelo/actividad) o "no_mapeado"
    zona_nombre: str
    uso_principal: str
    usos_permitidos: Tuple[str, ...]
    usos_no_permitidos: Tuple[str, ...]
    edificabilidad: Tuple[dict, ...]
    retiros: str
    restricciones: Tuple[str, ...]
    actividad_consultada: str
    actividad_resultado: str       # permitida | no_permitida | requiere_concepto | sin_consultar
    base: str
    capas: Tuple[dict, ...] = ()   # hallazgos por capa del POT (multi-capa)
    es_no_edificable: bool = False


def _buscar_zona(predio, zona=None, mapeo=None):
    if zona:
        return CATALOGO_ZONAS.get(zona)
    mapeo = mapeo or {}
    cc = (predio.codigo_catastral or "").strip()
    for prefijo, code in mapeo.items():
        if cc.startswith(prefijo):
            return CATALOGO_ZONAS.get(code)
    return None


# Sinónimos de actividad -> término canónico del catálogo de zonas.
SINONIMOS = {
    "comercial": "comercio", "comercio": "comercio", "local": "comercio", "tienda": "comercio",
    "residencial": "residencial", "vivienda": "residencial", "casa": "residencial",
    "entretenimiento": "entretenimiento", "recreacion": "entretenimiento", "ocio": "entretenimiento",
    "industrial": "industrial", "fabrica": "industrial", "bodega": "bodegaje", "bodegaje": "bodegaje",
    "servicios": "servicios", "servicio": "servicios", "oficina": "oficinas", "oficinas": "oficinas",
    "logistica": "logistica", "cultural": "cultural", "mixto": "mixto",
}


def _canon(act):
    return SINONIMOS.get(act, act)


def _edific(zp):
    return tuple({"indice": k, "valor": v} for k, v in zip(zp.edificabilidad.keys(), zp.edificabilidad.values()))


def _no_edificable(zp):
    return (zp.retiros == "no edificable") or float(zp.edificabilidad.get("indice_construccion", 1.0)) <= 0.1


def _decidir(act, permitidos, no_permitidos):
    """Decisión de actividad sobre el conjunto agregado de capas (lo más restrictivo gana)."""
    if not act:
        return "sin_consultar"
    if act in no_permitidos:
        return "no_permitida"
    if act in permitidos:
        return "permitida"
    return "requiere_concepto"


def punto_en_poligono(pt, poligono):
    """Test de punto-en-polígono (ray casting) para capas POT por polígono."""
    x, y = pt
    inside = False
    n = len(poligono)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = poligono[i]
        xj, yj = poligono[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _zona_por_poligono(coordenadas, poligonos):
    """Devuelve el código de zona cuya capa-polígono contiene el punto, o None."""
    for zona, pol in (poligonos or {}).items():
        if punto_en_poligono(coordenadas, pol):
            return zona
    return None


def _analizar_multicapa(predio, actividad, capas_pot):
    """Analiza el predio contra VARIAS capas superpuestas del POT (suelo + riesgo/ronda + tratamiento).

    - Cada capa resuelve una zona por prefijo catastral (mapeo de la capa).
    - El uso permitido se exige en TODAS las capas (intersección); lo no permitido es la unión.
    - Lo más restrictivo manda: una actividad prohibida en una sola capa es NO_PERMITIDA.
    """
    hits = []
    for nombre_capa, mapeo_capa in capas_pot.items():
        zp = _buscar_zona(predio, None, mapeo_capa)
        if zp is None:
            continue
        hits.append((nombre_capa, zp))

    if not hits:
        return FichaUsoSuelo(
            predio_id=predio.folio_matricula or predio.codigo_catastral or "",
            zona="no_mapeado", zona_nombre="Sin zona POT mapeada", uso_principal="",
            usos_permitidos=(), usos_no_permitidos=(), edificabilidad=(), retiros="",
            restricciones=(), actividad_consultada=actividad, actividad_resultado="sin_consultar",
            base=BASE_POT + " Falta mapeo del polígono (código catastral/cuadra).")

    act = _canon((actividad or "").strip().lower())

    def _ccanon(terms):
        return frozenset(_canon(t) for t in terms)

    # Capa primaria = suelo/actividad si existe; si no, la primera.
    primaria = next((zp for n, zp in hits if n in ("suelo", "actividad", "uso_suelo")), hits[0][1])

    # Intersección de permitidos / unión de no permitidos entre capas (términos canónicos).
    permitidos = _ccanon(primaria.usos_permitidos)
    no_permitidos = _ccanon(primaria.usos_no_permitidos)
    for n, zp in hits:
        permitidos &= _ccanon(zp.usos_permitidos)
        no_permitidos |= _ccanon(zp.usos_no_permitidos)

    restricciones = tuple(sorted({r for n, zp in hits for r in zp.restricciones}))
    no_edif = any(_no_edificable(zp) for n, zp in hits)
    capa_hits = tuple({"capa": n, "zona": zp.codigo, "zona_nombre": zp.nombre,
                       "uso_principal": zp.uso_principal,
                       "retiros": zp.retiros, "restricciones": tuple(zp.restricciones),
                       "es_no_edificable": _no_edificable(zp)} for n, zp in hits)

    return FichaUsoSuelo(
        predio_id=predio.folio_matricula or predio.codigo_catastral or "",
        zona=primaria.codigo, zona_nombre=primaria.nombre, uso_principal=primaria.uso_principal,
        usos_permitidos=tuple(sorted(permitidos)), usos_no_permitidos=tuple(sorted(no_permitidos)),
        edificabilidad=_edific(primaria) if not no_edif else (),
        retiros=primaria.retiros, restricciones=restricciones,
        actividad_consultada=actividad, actividad_resultado=_decidir(act, permitidos, no_permitidos),
        base=BASE_POT + " Análisis multi-capa (" + "; ".join(n for n, z in hits) + ").",
        capas=capa_hits, es_no_edificable=no_edif)


def analizar_uso_suelo(predio: Predio, actividad: str = "", *, zona: Optional[str] = None,
                       mapeo=None, capas_pot: Optional[dict] = None,
                       coordenadas=None, poligonos: Optional[dict] = None) -> FichaUsoSuelo:
    """Analiza el uso del suelo / polígono POT del predio y evalúa la actividad consultada.

    ``poligonos`` (XN-8b) resuelve la zona por **capa de polígono** (intersección geográfica sobre
    las ``coordenadas`` (lat, lon) del predio), complementando el mapeo por prefijo catastral.
    """
    if capas_pot:
        return _analizar_multicapa(predio, actividad, capas_pot)

    zp = _buscar_zona(predio, zona, mapeo)
    metodo = "mapeo catastral"
    if zp is None and coordenadas and poligonos:
        code = _zona_por_poligono(coordenadas, poligonos)
        if code:
            zp = CATALOGO_ZONAS.get(code)
            metodo = "polígono (intersección geográfica)"
    if zp is None:
        return FichaUsoSuelo(
            predio_id=predio.folio_matricula or predio.codigo_catastral or "",
            zona="no_mapeado", zona_nombre="Sin zona POT mapeada", uso_principal="",
            usos_permitidos=(), usos_no_permitidos=(), edificabilidad=(), retiros="",
            restricciones=(), actividad_consultada=actividad, actividad_resultado="sin_consultar",
            base=BASE_POT + " Falta mapeo del polígono (código catastral/cuadra o coordenadas).")

    act = _canon((actividad or "").strip().lower())
    if not act:
        res = "sin_consultar"
    elif act in zp.usos_permitidos:
        res = "permitida"
    elif act in zp.usos_no_permitidos:
        res = "no_permitida"
    else:
        res = "requiere_concepto"

    return FichaUsoSuelo(
        predio_id=predio.folio_matricula or predio.codigo_catastral or "",
        zona=zp.codigo, zona_nombre=zp.nombre, uso_principal=zp.uso_principal,
        usos_permitidos=zp.usos_permitidos, usos_no_permitidos=zp.usos_no_permitidos,
        edificabilidad=_edific(zp), retiros=zp.retiros, restricciones=zp.restricciones,
        actividad_consultada=actividad, actividad_resultado=res,
        base=zp.base + f" [resolución por {metodo}]",
        es_no_edificable=_no_edificable(zp))

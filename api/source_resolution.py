# -*- coding: utf-8 -*-
"""ARHIAX RE — BARRANQUILLA SOURCE PACK v1.0 · RESOLUTION LADDER POR ATRIBUTO.

Este módulo NO toca el contrato de fuentes (`api/dictus_sources.py`): lo CONSUME.
Define la ESCALERA DE RESOLUCIÓN por atributo: consulta la fuente de mayor autoridad
y vigencia declarada PARA ESE ATRIBUTO y, si no devuelve dato utilizable, baja
automáticamente al siguiente escalón autorizado, registrando SIEMPRE qué fuente se
seleccionó, cuáles se intentaron y con qué estado.

Reglas duras:

  · Múltiples capas NO son un conflicto por defecto. El objetivo es OBTENER EL MEJOR
    HECHO DISPONIBLE y saber exactamente de dónde salió.
  · `CONFLICT` SOLO si dos fuentes aplicables al MISMO atributo, con la MISMA
    semántica, la MISMA vigencia, autoridad COMPARABLE y el MISMO objeto devuelven
    valores INCOMPATIBLES que la regla de precedencia NO puede resolver.
  · Una capa HISTÓRICA nunca compite con una VIGENTE: la vigente produce el valor
    operativo y la histórica queda como provenance/referencia en el anexo.
  · Ausencia de dato (`SOURCE_UNAVAILABLE` / `NOT_SUPPORTED` / `QUERY_FAILED`) NUNCA se
    convierte en `NO_MATCH` ni en conflicto: solo baja al siguiente escalón.
  · DICTUS expone únicamente el VALOR RESUELTO y su provenance (`solo_valor_resuelto`);
    las fuentes alternativas/fallback van al ANEXO (`anexo_alternativas`).

Determinismo: el orden del escalón se deriva de `authority_class`, luego vigencia,
luego `source_priority` explícito y luego `source_id` alfabético. Permutar el orden de
entrada del registro o de las consultas produce EXACTAMENTE el mismo resultado.

Documentación completa: `docs/source_pack/RESOLUTION_LADDER.md`.
"""
from __future__ import annotations

import fnmatch
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

try:  # importable como `api.source_resolution` y como módulo plano (patrón de los tests)
    from . import dictus_sources as ds
except ImportError:  # pragma: no cover — import plano cuando `api/` está en sys.path
    import dictus_sources as ds  # type: ignore[no-redef]

__all__ = [
    "PACK_ETIQUETA",
    "RESOLVED_PRIMARY", "RESOLVED_FALLBACK", "UNRESOLVED", "AMBIGUOUS",
    "RESOLUTION_SOURCE_UNAVAILABLE", "SOURCE_UNAVAILABLE", "ESTADOS_RESOLUCION",
    "CONFLICT", "NOT_RUN", "ROL_OPERATIVA", "ROL_REFERENCIA",
    "CENTINELAS_SIN_DATO",
    "COBERTURA_ATRIBUTOS", "ATRIBUTOS", "atributos_declarados", "estado_registro",
    "valor_utilizable", "normalizar_valor", "valores_compatibles",
    "escalon_para_atributo", "resolver_atributo", "resolver_dominio",
    "solo_valor_resuelto", "anexo_alternativas", "es_conflicto",
    "VeredictoConflicto", "ORDEN_AUTORIDAD", "ORDEN_VIGENCIA",
]

PACK_ETIQUETA = "barranquilla-source-pack/1.0.0 · resolution-ladder/1"

# ── estados de resolución (vocabulario CERRADO de 5) ──────────────────────────
RESOLVED_PRIMARY = "RESOLVED_PRIMARY"
RESOLVED_FALLBACK = "RESOLVED_FALLBACK"
UNRESOLVED = "UNRESOLVED"
AMBIGUOUS = "AMBIGUOUS"
# El 5.º estado es el estado de ausencia del contrato de fuentes (§27).
RESOLUTION_SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
SOURCE_UNAVAILABLE = ds.FUENTE_NO_DISPONIBLE           # "SOURCE_UNAVAILABLE"
ESTADOS_RESOLUCION = (RESOLVED_PRIMARY, RESOLVED_FALLBACK, UNRESOLVED, AMBIGUOUS,
                      SOURCE_UNAVAILABLE)

# Etiqueta del bloque de conflicto (el estado de resolución asociado es `AMBIGUOUS`).
CONFLICT = "CONFLICT"

# Marcador LOCAL de la escalera: `NOT_RUN` NO es un estado de fuente del contrato §27.
# Significa «no se ejecutó consulta» (sin consulta declarada o fuera de ventana de
# vigencia). Nunca contiene dato, nunca es valor y NUNCA se lee como `NO_MATCH`.
NOT_RUN = "NOT_RUN"

ROL_OPERATIVA = "OPERATIVA"
ROL_REFERENCIA = "SOLO_REFERENCIA"

# ── orden de evaluación declarado (§2 / §12) ─────────────────────────────────
ORDEN_AUTORIDAD = {
    ds.AUTORITATIVA_OFICIAL: 0,
    ds.AUTORITATIVA_CONTRACTUAL: 1,
    ds.CONTEXTUAL_EXTERNA: 2,
    ds.CALCULADA: 3,
}
ORDEN_VIGENCIA = {
    ds.CURRENT_NORMATIVE: 0,
    ds.CURRENT_OFFICIAL: 1,
    "CONTEXTUAL_REFERENCE": 2,
    "COMPUTED_REFERENCE": 3,
    ds.HISTORICAL_REFERENCE: 4,
}
_RANGO_DESCONOCIDO = 9
_PRIORIDAD_POR_DEFECTO = 100

# ── valor utilizable (qué NO es un dato) ─────────────────────────────────────
# Nota: "0" NO está en el conjunto por decisión explícita del pack — el cero es un valor
# legítimo y la escalera JAMÁS lo inventa para tapar una ausencia (ver `valor_utilizable`).
CENTINELAS_SIN_DATO = frozenset({
    "-", "--", "...", "NA", "N/A", "N.D.", "ND", "N/D", "NO DISPONIBLE",
    "NO DISPONIBLES", "NO DISPONIBLE EN LA FUENTE", "SIN DATO", "SIN DATOS",
    "SIN INFORMACION", "NO APLICA", "NO APLICABLE", "NULL", "NONE", "UNDEFINED",
    "UNKNOWN", "DESCONOCIDO", "NO REPORTADO", "NO REGISTRA", "NO REGISTRADO",
    "PENDIENTE", "SIN ESPECIFICAR", "VACIO", "EMPTY", "TBD", "POR DEFINIR",
})


def _norm(texto: Any) -> str:
    """Mayúsculas, sin acentos, espacios colapsados. Solo para comparar."""
    t = unicodedata.normalize("NFKD", str(texto if texto is not None else ""))
    return " ".join(t.encode("ascii", "ignore").decode().upper().split())


def valor_utilizable(valor: Any) -> bool:
    """¿Es `valor` un DATO utilizable? `None`, `""`, `[]`, `{}`, `"NO DISPONIBLE"`,
    `"N/D"` y centinelas equivalentes NO lo son. El cero y `False` SÍ lo son: son
    respuestas contestadas, y la escalera nunca los fabrica por ausencia."""
    if valor is None:
        return False
    if isinstance(valor, bool):
        return True
    if isinstance(valor, (int, float)):
        return True
    if isinstance(valor, (list, tuple, set, frozenset)):
        return any(valor_utilizable(x) for x in valor)
    if isinstance(valor, dict):
        if not valor:
            return False
        return any(valor_utilizable(x) for x in valor.values())
    t = _norm(valor)
    if not t:
        return False
    return t not in CENTINELAS_SIN_DATO


def normalizar_valor(valor: Any) -> Any:
    """Forma canónica estable del valor para comparar (no para imprimir).

    `4`, `"4"` y `"4.0"` son el MISMO valor; `["A","B"]` y `["B","A"]` son el mismo
    conjunto; los dicts se comparan por claves ordenadas.
    """
    if valor is None:
        return None
    if isinstance(valor, bool):
        return "TRUE" if valor else "FALSE"
    if isinstance(valor, (int, float)):
        f = float(valor)
        return str(int(f)) if f.is_integer() else repr(round(f, 6))
    if isinstance(valor, (list, tuple, set, frozenset)):
        return "[" + "|".join(sorted(str(normalizar_valor(x)) for x in valor)) + "]"
    if isinstance(valor, dict):
        return "{" + ",".join(f"{_norm(k)}={normalizar_valor(v)}"
                              for k, v in sorted(valor.items(), key=lambda kv: _norm(kv[0]))) + "}"
    t = _norm(valor)
    if not t:
        return ""
    try:
        f = float(t.replace(",", "."))
    except ValueError:
        return t
    return str(int(f)) if f.is_integer() else repr(round(f, 6))


def valores_compatibles(a: Any, b: Any) -> bool:
    """Dos valores son COMPATIBLES si su forma canónica coincide."""
    return normalizar_valor(a) == normalizar_valor(b)


# ── escalera declarada por atributo ──────────────────────────────────────────
# `fuentes`: conjunto declarado de fuentes candidatas. El ORDEN lo deriva la escalera
# del registro (autoridad → vigencia → `source_priority` → `source_id`), NUNCA del
# orden de escritura. Los comodines (`EQUIPAMIENTO_*`) se expanden contra el registro
# y se ordenan alfabéticamente antes de entrar al escalón.
#
# Por candidato se puede declarar:
#   semantics / object_key  → semántica y objeto de ESE par (atributo, fuente): dos
#                             fuentes solo compiten si coinciden en ambos.
#   campos                  → campos donde buscar el valor dentro del payload; si
#                             ninguno casa, el payload completo ES el valor.
#   source_priority         → prioridad explícita PARA ESE ATRIBUTO.
#   vigente_desde/_hasta    → ventana de vigencia (ISO). Fuera de ella la fuente no se
#                             consulta: se registra como `NOT_RUN`, jamás como dato.
#
# Por atributo:
#   admite_fallback_si_no_match → si una fuente que SÍ contestó `NO_MATCH` permite que
#                                 otra fuente aporte el valor.
#   admite_conflicto            → si sus discrepancias irresolubles se declaran
#                                 `CONFLICT` (fuentes CONTEXTUAL/CALCULADA: no).
#   historica_como_fallback     → si una capa HISTORICAL_REFERENCE puede aportar el
#                                 valor operativo. Falso en todo el pack (§12).
COBERTURA_ATRIBUTOS: Dict[str, Dict[str, Any]] = {
    # ── identidad ────────────────────────────────────────────────────────────
    "identidad_nupre": {
        "description": "Identidad canónica del predio (NUPRE / número predial homologado).",
        "semantics": "IDENTIDAD_PREDIAL_CANONICA",
        "object_key": "PREDIO",
        "campos": ["numero_predial_nacional", "codigo_homologado", "nupre", "numero_predial",
                   "fmi", "name"],
        "admite_fallback_si_no_match": False,
        "fuentes": {
            "CATASTRO_BAQ_ADOPCION_ANEXO1": {"source_priority": 10},
            "CATASTRO_BAQ_PREDIO": {"source_priority": 20},
            "CATASTRO_BAQ_TERRENO": {"source_priority": 30},
        },
    },
    "predio": {
        "description": "Registro catastral del predio (área, tipo, FMI, terreno).",
        "semantics": "REGISTRO_CATASTRAL_PREDIO",
        "object_key": "PREDIO",
        "campos": ["numero_predial_nacional", "area_catastral_terreno", "tipo_predio",
                   "estado_fmi", "relacion_superficie", "name"],
        "fuentes": {
            "CATASTRO_BAQ_PREDIO": {"source_priority": 10},
            "CATASTRO_BAQ_TERRENO": {"source_priority": 20},
            "CATASTRO_BAQ_MANZANA": {"source_priority": 40},
        },
    },
    "direccion_predio": {
        "description": "Nomenclatura oficial del predio.",
        "semantics": "DIRECCION_OFICIAL_NOMENCLATURA",
        "object_key": "PREDIO",
        "campos": ["direccion", "valor_via_principal", "numero_predio", "nombre_predio"],
        "fuentes": {
            "CATASTRO_BAQ_DIRECCION": {"source_priority": 10},
            "CATASTRO_BAQ_PREDIO": {"source_priority": 30},
        },
    },
    # ── división política administrativa ────────────────────────────────────
    "barrio": {
        "description": "Barrio oficial del predio.",
        "semantics": "DIVISION_BARRIO",
        "object_key": "BARRIO",
        "campos": ["barrio", "nombre_barrio", "nombre", "codigo_barrio"],
        "fuentes": {
            "POT_BAQ_BARRIOS": {"source_priority": 10},
        },
    },
    "localidad": {
        "description": "Localidad distrital del predio.",
        "semantics": "DIVISION_LOCALIDAD",
        "object_key": "LOCALIDAD",
        "campos": ["localidad", "nombre_localidad", "nombre", "codigo_localidad"],
        "fuentes": {
            "POT_BAQ_LOCALIDADES": {"source_priority": 10},
            "POT_BAQ_BARRIOS": {"source_priority": 30},
        },
    },
    "estrato": {
        "description": "Estrato socioeconómico (catastro vs POT: SIN prioridad declarada).",
        "semantics": "ESTRATO_SOCIOECONOMICO",
        "object_key": "PREDIO",
        "campos": ["estrato", "estratificacion", "codigo_estrato", "nombre_estrato"],
        # Sin `source_priority`: el pack NO declara cuál manda. Si discrepan, es CONFLICT.
        "fuentes": {
            "POT_BAQ_ESTRATIFICACION": {},
            "CATASTRO_BAQ_PREDIO": {},
        },
    },
    # ── catastro vs POT: DOS objetos distintos ──────────────────────────────
    "destino_catastral": {
        "description": "Destino económico catastral. NO es el uso normativo del POT.",
        "semantics": "DESTINO_ECONOMICO_CATASTRAL",
        "object_key": "PREDIO",
        "campos": ["destinacion_economica", "destino_economico"],
        "fuentes": {
            # La capa de anualidad vigente es la operativa; la tabla maestra es respaldo.
            "CATASTRO_BAQ_DESTINO_ECONOMICO": {"source_priority": 10,
                                               "vigente_desde": "2026-01-01"},
            "CATASTRO_BAQ_PREDIO": {"source_priority": 30},
        },
    },
    "uso_pot": {
        "description": "Uso normativo del POT. NO es el destino catastral.",
        "semantics": "USO_NORMATIVO_POT",
        "object_key": "PREDIO",
        "campos": ["nombre_uso", "uso", "simb_activ", "actividad", "codigo_uso"],
        "fuentes": {
            "POT_BAQ_AREAS_ACTIVIDAD": {"source_priority": 10},
            "POT_BAQ_POLIGONOS_USO": {"source_priority": 20},
        },
    },
    "tratamiento": {
        "description": "Tratamiento urbanístico del POT.",
        "semantics": "TRATAMIENTO_URBANISTICO_POT",
        "object_key": "PREDIO",
        "campos": ["tratamiento", "nombre_tratamiento", "simb_trat", "codigo_tratamiento"],
        "fuentes": {"POT_BAQ_TRATAMIENTO": {}},
    },
    "edificabilidad_altura_normativa": {
        "description": ("Altura NORMATIVA del POT y parámetros de edificabilidad. "
                        "Nunca es altura física del edificio (api/dictus_sources.altura_fisica)."),
        "semantics": "ALTURA_NORMATIVA_POT",
        "object_key": "PREDIO",
        "campos": ["altura_max", "edificabilidad", "indice_edificabilidad", "ic", "io",
                   "aislamiento", "antejardin", "densidad"],
        "fuentes": {"POT_BAQ_EDIFICABILIDAD": {}},
    },
    "altura_fisica": {
        "description": "Altura física declarada por catastro (construcción).",
        "semantics": "ALTURA_FISICA_CONSTRUCCION",
        "object_key": "PREDIO",
        "campos": ["altura_total_construccion", "total_pisos"],
        "fuentes": {"CATASTRO_BAQ_CONSTRUCCION": {}},
    },
    # ── riesgo oficial (vigente vs histórica) ───────────────────────────────
    "remocion": {
        "description": "Amenaza por remoción en masa (capa vigente del POT).",
        "semantics": "AMENAZA_REMOCION_MASA",
        "object_key": "PREDIO",
        "campos": ["amenaza", "nivel_remocion", "grado_amenaza", "clasificacion"],
        "fuentes": {
            "POT_BAQ_REMOCION_2024": {},
            "POT_BAQ_REMOCION_HIST": {},
        },
    },
    "inundacion": {
        "description": "Amenaza por inundación (capa vigente del POT).",
        "semantics": "AMENAZA_INUNDACION",
        "object_key": "PREDIO",
        "campos": ["amenaza", "nivel_inundacion", "grado_amenaza", "clasificacion"],
        "fuentes": {
            "POT_BAQ_INUNDACION_2024": {},
            "POT_BAQ_INUNDACION_HIST": {},
        },
    },
    "riesgo": {
        "description": "Riesgo oficial del POT (capa vigente).",
        "semantics": "RIESGO_OFICIAL_POT",
        "object_key": "PREDIO",
        "campos": ["riesgo", "nivel_riesgo", "grado_riesgo", "clasificacion"],
        "fuentes": {
            "POT_BAQ_RIESGO_2024": {},
            "POT_BAQ_RIESGO_HIST": {},
        },
    },
    # ── equipamiento y contexto: no se mezclan (§15) ────────────────────────
    "equipamiento_oficial": {
        "description": "Equipamiento con autoridad OFICIAL (conjunto separado del contexto).",
        "semantics": "EQUIPAMIENTO_OFICIAL",
        "object_key": "ENTORNO",
        "campos": ["equipamiento", "tipo_equipamiento", "nombre", "categoria", "clase"],
        "fuentes": {"EQUIPAMIENTO_*": {}},
    },
    "servicios_de_contexto": {
        "description": ("Servicios y contexto del entorno. Fuentes CONTEXTUAL_EXTERNAL: "
                        "no sostienen afirmación normativa y no producen CONFLICT."),
        "semantics": "CONTEXTO_ENTORNO",
        "object_key": "ENTORNO",
        "campos": ["servicios", "pois", "amenities", "elementos", "conteo"],
        "admite_conflicto": False,
        "fuentes": {
            # OSM/Overpass es el proveedor de contexto que HOY está operativo
            # (api/poi_engine.py); las imágenes de fachada son complementarias y Google
            # queda en FAIL-CLOSED por términos no verificados.
            "OSM_OVERPASS": {"source_priority": 10, "semantics":
                             "CONTEXTO_SERVICIOS_VECINOS",
                             "campos": ["servicios", "pois", "amenities", "elementos",
                                        "conteo"]},
            "MAPILLARY": {"source_priority": 20, "semantics": "CONTEXTO_IMAGEN_FACHADA",
                          "object_key": "FACHADA",
                          "campos": ["image_url", "url", "imagen", "fecha_captura"]},
            "GOOGLE_STREET_VIEW": {"source_priority": 30, "semantics":
                                   "CONTEXTO_IMAGEN_FACHADA", "object_key": "FACHADA",
                                   "campos": ["image_url", "url", "imagen", "fecha_captura"]},
        },
    },
    "mercado": {
        "description": ("Valor/mercado del suelo por parámetros declarados por la corrida "
                        "(metodología local del producto): NO tiene fuente de datos. La "
                        "resolución declara la ausencia y el mercado no se sustituye por "
                        "contexto."),
        "semantics": "VALOR_MERCADO_SUELO",
        "object_key": "ZONA_MERCADO",
        "campos": ["valor_m2", "precio_m2", "valor_comercial_m2", "rango_mercado", "muestra"],
        # DECISIÓN DE PRODUCTO: la Lonja NO es una fuente de datos (no aporta el valor por
        # m², ni dataset, ni contrato, ni URL). Por eso este escalón está VACÍO a propósito:
        # no se declara ninguna fuente y la resolución queda declarada como NO DISPONIBLE.
        # El valor de mercado que usa la valoración es un parámetro declarado por la corrida
        # (api/market_context.py), sin fuente externa automática verificable.
        "fuentes": {},
        "no_fuente": True,
        "no_fuente_motivo": ("MERCADO SIN FUENTE: el valor de mercado del producto es un "
                             "parámetro declarado por la corrida (artefacto local de "
                             "metodología), sin fuente externa automática verificable. La "
                             "resolución de mercado declara la ausencia (NO DISPONIBLE) y NO "
                             "se sustituye por ningún otro dato, ni por un valor por defecto, "
                             "ni por el promedio de otros sectores."),
    },
    "exposicion_solar_fachada": {
        "description": "Exposición solar de la fachada visible (fuentes CALCULADAS).",
        "semantics": "EXPOSICION_SOLAR_FACHADA",
        "object_key": "FACHADA",
        "campos": ["exposicion", "estado_exposicion", "irradiacion"],
        "admite_conflicto": False,
        "fuentes": {
            "SHADOW_FACADE_EXPOSURE": {"semantics": "SOMBRA_CONTEXTUAL_FACHADA",
                                       "campos": ["shadow_exposure", "exposicion",
                                                  "estado_exposicion", "shadow_confidence"]},
            "SOLAR_ENGINE": {"semantics": "IRRADIACION_GEOMETRICA_FACHADA",
                             "campos": ["exposicion", "irradiacion", "azimut", "inclinacion"]},
        },
    },
}

ATRIBUTOS: Tuple[str, ...] = tuple(sorted(COBERTURA_ATRIBUTOS))


def atributos_declarados() -> List[str]:
    """Atributos con escalera declarada en el pack (orden alfabético estable)."""
    return list(ATRIBUTOS)


# ── registro de fuentes ──────────────────────────────────────────────────────
def _cargar_registro(registro: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Registro inyectado o el del Source Pack. Declara `_status` si no hay registro."""
    if registro is not None:
        reg = dict(registro)
        reg.setdefault("sources", {})
        reg.setdefault("registry_version", ds.REGISTRY_VERSION)
        return reg
    try:
        reg = ds.cargar_registro()
    except Exception as exc:  # noqa: BLE001 — la ausencia de registro es un estado
        return {"registry_version": ds.REGISTRY_VERSION, "sources": {},
                "_status": ds.NO_SOPORTADA,
                "reason": f"No se pudo cargar el registro: {type(exc).__name__}: {exc}"}
    reg = dict(reg)
    reg.setdefault("sources", {})
    return reg


def estado_registro(registro: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Estado del registro de fuentes: declaración explícita de ausencia."""
    reg = _cargar_registro(registro)
    fuentes = reg.get("sources") or {}
    return {
        "registry_version": reg.get("registry_version") or ds.REGISTRY_VERSION,
        "registry_status": reg.get("_status") or "AVAILABLE",
        "source_count": len(fuentes),
        "registry_path": str(Path(ds.RUTA_REGISTRO)),
        "reason": reg.get("reason") or "",
    }


def _cobertura(inyectada: Optional[Dict[str, Any]] = None) -> Dict[str, Dict[str, Any]]:
    """Tabla declarada, opcionalmente ampliada/reemplazada atributo por atributo."""
    tabla: Dict[str, Dict[str, Any]] = {}
    for attr, regla in COBERTURA_ATRIBUTOS.items():
        tabla[attr] = _normalizar_regla(attr, regla)
    for attr, regla in (inyectada or {}).items():
        tabla[str(attr)] = _normalizar_regla(str(attr), regla)
    return tabla


def _normalizar_regla(atributo: str, regla: Any) -> Dict[str, Any]:
    """Acepta la regla declarada y también una regla YA normalizada (idempotente)."""
    if regla is None:
        regla = {}
    if isinstance(regla, (list, tuple)):
        regla = {"fuentes": list(regla)}
    if isinstance(regla, dict) and "fuentes" not in regla and "candidatos" not in regla:
        # dict de overrides por fuente ({"S1": {...}}) sin bloque atributo.
        regla = {"fuentes": regla}
    regla = dict(regla or {})
    candidatos: List[Tuple[str, Dict[str, Any]]] = []
    crudo = regla.get("candidatos")
    pares = (isinstance(crudo, (list, tuple)) and crudo
             and all(isinstance(c, (list, tuple)) and len(c) == 2 for c in crudo))
    if pares:                                   # regla ya normalizada
        for sid, over in crudo:
            candidatos.append((str(sid), dict(over or {})))
    else:
        fuentes = regla.get("fuentes") or crudo or {}
        if isinstance(fuentes, dict):
            for sid, over in fuentes.items():
                candidatos.append((str(sid), dict(over or {})))
        else:
            for sid in fuentes:
                candidatos.append((str(sid), {}))
    return {
        "atributo": atributo,
        "description": str(regla.get("description") or ""),
        "semantics": regla.get("semantics"),
        "object_key": regla.get("object_key"),
        "campos": [str(c) for c in (regla.get("campos") or [])],
        "admite_fallback_si_no_match": bool(regla.get("admite_fallback_si_no_match", True)),
        "admite_conflicto": bool(regla.get("admite_conflicto", True)),
        "historica_como_fallback": bool(regla.get("historica_como_fallback", False)),
        # Atributo declarado SIN fuente de datos (decisión de producto): el escalón está
        # vacío a propósito y la resolución declara la ausencia. Se conserva la marca al
        # normalizar porque `resolver_atributo` la lee de aquí.
        "no_fuente": bool(regla.get("no_fuente", False)),
        "no_fuente_motivo": str(regla.get("no_fuente_motivo") or ""),
        "candidatos": candidatos,
    }


def _expandir(patron: str, fuentes: Dict[str, Any]) -> List[str]:
    if "*" in patron or "?" in patron:
        return sorted(sid for sid in fuentes if fnmatch.fnmatchcase(sid, patron))
    return [patron]


def _rank_autoridad(clase: Any) -> int:
    return ORDEN_AUTORIDAD.get(str(clase or "").upper(), _RANGO_DESCONOCIDO)


def _rank_vigencia(precedencia: Any) -> int:
    return ORDEN_VIGENCIA.get(str(precedencia or "").upper(), _RANGO_DESCONOCIDO)


def _vigencia_de(fuente: Dict[str, Any]) -> str:
    return str(fuente.get("precedence") or "").upper()


def _en_ventana(over: Dict[str, Any], fecha: Optional[str]) -> Tuple[bool, str]:
    """Ventana de vigencia declarada para el par (atributo, fuente).

    Sin `fecha`, o con fechas no parseables, la fuente permanece consultable: la
    escalera nunca excluye por un dato de fecha ilegible.
    """
    if fecha is None:
        return True, ""
    try:
        hoy = date.fromisoformat(str(fecha)[:10])
    except ValueError:
        return True, ""
    for clave, dentro in (("vigente_desde", lambda h, lim: h >= lim),
                          ("vigente_hasta", lambda h, lim: h <= lim)):
        limite = over.get(clave)
        if not limite:
            continue
        try:
            lim = date.fromisoformat(str(limite)[:10])
        except ValueError:
            continue
        if not dentro(hoy, lim):
            return False, (f"Fuera de la ventana de vigencia declarada ({clave}={limite}) "
                           f"para la fecha consultada {fecha}.")
    return True, ""


def _prioridad(sid: str, fuente: Dict[str, Any], over: Dict[str, Any]) -> Tuple[int, str]:
    if "source_priority" in over and over["source_priority"] is not None:
        return int(over["source_priority"]), "PER_ATTRIBUTE"
    if fuente.get("source_priority") is not None:
        return int(fuente["source_priority"]), "REGISTRY"
    return _PRIORIDAD_POR_DEFECTO, "DEFAULT"


def _escalon(atributo: str, regla: Dict[str, Any], reg: Dict[str, Any],
             fecha: Optional[str] = None, solo_en_ventana: bool = False
             ) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Escalón ORDENADO y determinista + fuentes declaradas pero no registradas.

    Orden: `authority_class` → vigencia → `source_priority` → `source_id` alfabético.
    El índice (`order_index`) se fija sobre el escalón COMPLETO, con independencia del
    filtro por fecha: así «primario» significa «la fuente de mayor autoridad declarada
    para el atributo», no «la primera que quedó tras filtrar».
    """
    fuentes: Dict[str, Any] = reg.get("sources") or {}
    entradas: List[Dict[str, Any]] = []
    no_registradas: List[str] = []
    for patron, over in regla["candidatos"]:
        for sid in _expandir(patron, fuentes):
            fuente = fuentes.get(sid)
            if not isinstance(fuente, dict):
                if sid not in no_registradas:
                    no_registradas.append(sid)
                continue
            vigencia = _vigencia_de(fuente)
            autoridad = str(fuente.get("authority_class") or "")
            prioridad, origen = _prioridad(sid, fuente, over)
            en_ventana, motivo_ventana = _en_ventana(over, fecha)
            referencia = (vigencia == ds.HISTORICAL_REFERENCE
                          and not regla["historica_como_fallback"])
            entradas.append({
                "source_id": sid,
                "source_name": fuente.get("source_name"),
                "institution": fuente.get("institution"),
                "authority_class": autoridad,
                "vigencia": vigencia,
                "source_priority": prioridad,
                "priority_origin": origen,
                "rank": [_rank_autoridad(autoridad), _rank_vigencia(vigencia), prioridad],
                "semantics": over.get("semantics", regla["semantics"]),
                "object_key": over.get("object_key", regla["object_key"]),
                "campos": [str(c) for c in (over.get("campos") or regla["campos"])],
                "role": ROL_REFERENCIA if referencia else ROL_OPERATIVA,
                "enabled": fuente.get("enabled") is not False,
                "vigencia_status": "EN_VENTANA" if en_ventana else "FUERA_DE_VENTANA",
                "vigencia_reason": motivo_ventana,
                "registry": {
                    "source_id": sid,
                    "source_name": fuente.get("source_name"),
                    "institution": fuente.get("institution"),
                    "authority_class": autoridad,
                    "service": fuente.get("service"),
                    "layer_id": fuente.get("layer_id"),
                    "layer_name": fuente.get("layer_name"),
                    "query_method": fuente.get("query_method"),
                    "version_or_vigency": fuente.get("version_or_vigency"),
                    "precedence": fuente.get("precedence"),
                    "license_or_terms": fuente.get("license_or_terms"),
                    "base_url": fuente.get("base_url"),
                },
            })
    entradas.sort(key=lambda e: (e["rank"][0], e["rank"][1], e["rank"][2], e["source_id"]))
    for i, e in enumerate(entradas):
        e["escalon_step"] = i + 1
        e["order_index"] = i
    if solo_en_ventana:
        entradas = [e for e in entradas if e["vigencia_status"] == "EN_VENTANA"]
    return entradas, sorted(no_registradas)


def escalon_para_atributo(atributo: str, *, registro: Optional[Dict[str, Any]] = None,
                          cobertura: Optional[Dict[str, Any]] = None,
                          fecha: Optional[str] = None) -> List[Dict[str, Any]]:
    """Escalón ORDENADO y determinista de fuentes autorizadas para `atributo`.

    `[]` significa «ninguna fuente del pack cubre este atributo»: eso se resuelve como
    `UNRESOLVED`, nunca como conflicto ni como `NO_MATCH`.
    """
    tabla = _cobertura(cobertura)
    regla = tabla.get(str(atributo))
    if regla is None:
        return []
    reg = _cargar_registro(registro)
    entradas, _ = _escalon(str(atributo), regla, reg, fecha=fecha, solo_en_ventana=True)
    return [dict(e) for e in entradas]


def _anexo_id(atributo: str) -> str:
    limpio = "".join(ch if ch.isalnum() else "-" for ch in _norm(atributo)).strip("-")
    return f"ANEXO-FUENTES-{limpio}"


# ── definición ESTRICTA de conflicto ─────────────────────────────────────────
class VeredictoConflicto(dict):
    """Resultado de `es_conflicto`: dict con el motivo y con valor de verdad.

    Es FALSO cuando no hay conflicto, de modo que
    `assertTrue(es_conflicto(a, b))` y `es_conflicto(a, b)["reason"]` son ambos válidos.
    """

    def __bool__(self) -> bool:
        return bool(self.get("conflict"))

    @property
    def conflict(self) -> bool:
        return bool(self.get("conflict"))

    @property
    def reason(self) -> str:
        return str(self.get("reason") or "")


def _descriptor(candidato: Any, *, registro: Optional[Dict[str, Any]] = None,
                attribute: Optional[str] = None,
                cobertura: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Normaliza cualquier candidato/resultado/intento a descriptor comparable."""
    x = dict(candidato or {})
    attr = str(x.get("attribute") or attribute or "")
    sid = str(x.get("source_id") or x.get("selected_source") or "")
    reg = _cargar_registro(registro)
    fuente = (reg.get("sources") or {}).get(sid) or {}
    regla = _cobertura(cobertura).get(attr) if attr else None
    vigencia = x.get("vigencia")
    if vigencia is None:
        vigencia = x.get("selected_vigencia") or _vigencia_de(fuente)
    autoridad = x.get("authority_class")
    if autoridad is None:
        autoridad = (x.get("provenance") or {}).get("authority_class") or fuente.get(
            "authority_class")
    semantics = x.get("semantics")
    object_key = x.get("object_key")
    if regla is not None:
        semantics = semantics if semantics is not None else regla["semantics"]
        object_key = object_key if object_key is not None else regla["object_key"]
    prioridad, origen = _prioridad(sid, fuente, {})
    if x.get("source_priority") is not None:
        prioridad, origen = int(x["source_priority"]), str(x.get("priority_origin") or "GIVEN")
    return {
        "source_id": sid,
        "attribute": attr or None,
        "value": x.get("value"),
        "semantics": semantics,
        "object_key": object_key,
        "vigencia": str(vigencia or "").upper(),
        "authority_class": str(autoridad or "").upper(),
        "source_priority": prioridad,
        "priority_origin": origen,
        "rank": x.get("rank") or [_rank_autoridad(autoridad), _rank_vigencia(vigencia),
                                  prioridad],
    }


def es_conflicto(a: Any, b: Any, *, registro: Optional[Dict[str, Any]] = None,
                 attribute: Optional[str] = None,
                 cobertura: Optional[Dict[str, Any]] = None) -> VeredictoConflicto:
    """Definición ESTRICTA de CONFLICT. Devuelve veredicto falso/verdadero + motivo.

    Es CONFLICT **solo** si se cumplen las SEIS condiciones a la vez:

      1. MISMA SEMÁNTICA  — miden lo mismo y la semántica está declarada.
      2. MISMO OBJETO     — hablan del mismo objeto (`object_key`).
      3. MISMA VIGENCIA   — mismo `precedence` (vigente con vigente, histórica con
                            histórica). Histórica vs vigente NUNCA es conflicto.
      4. AUTORIDAD COMPARABLE — misma `authority_class`, o ambas clases normativas
                            (AUTHORITATIVE_OFFICIAL / AUTHORITATIVE_CONTRACTUAL). Una
                            fuente CONTEXTUAL o COMPUTED no compite con una oficial.
      5. VALORES INCOMPATIBLES — ambos utilizables y con forma canónica distinta.
      6. PRECEDENCIA QUE NO RESUELVE — empatan en (autoridad, vigencia, prioridad): la
                            regla de precedencia no puede decidir. Si una es
                            estrictamente superior, NO hay conflicto: hay precedencia.
    """
    da = _descriptor(a, registro=registro, attribute=attribute, cobertura=cobertura)
    db = _descriptor(b, registro=registro, attribute=attribute, cobertura=cobertura)

    sem_a, sem_b = _norm(da["semantics"]), _norm(db["semantics"])
    obj_a, obj_b = _norm(da["object_key"]), _norm(db["object_key"])
    misma_semantica = bool(sem_a) and sem_a == sem_b
    mismo_objeto = bool(obj_a) and obj_a == obj_b
    misma_vigencia = bool(da["vigencia"]) and da["vigencia"] == db["vigencia"]
    clases = {da["authority_class"], db["authority_class"]}
    autoridad_comparable = (bool(da["authority_class"])
                            and da["authority_class"] == db["authority_class"]) or (
        clases.issubset(set(ds.CLASES_NORMATIVAS)) and len(clases) == 2)
    valor_a, valor_b = da["value"], db["value"]
    valores_utilizables = valor_utilizable(valor_a) and valor_utilizable(valor_b)
    valores_incompatibles = valores_utilizables and not valores_compatibles(valor_a, valor_b)
    misma_precedencia = list(da["rank"]) == list(db["rank"])

    condiciones = {
        "misma_semantica": misma_semantica,
        "mismo_objeto": mismo_objeto,
        "misma_vigencia": misma_vigencia,
        "autoridad_comparable": autoridad_comparable,
        "valores_incompatibles": valores_incompatibles,
        "precedencia_no_resuelve": misma_precedencia,
    }
    hay = all(condiciones.values())
    if hay:
        fallos: List[str] = []
        motivo = (
            f"CONFLICT: «{da['source_id']}» y «{db['source_id']}» son aplicables al MISMO "
            f"atributo ({da['attribute'] or db['attribute'] or 'sin atributo declarado'}), "
            f"con la MISMA semántica ({da['semantics']}), el MISMO objeto "
            f"({da['object_key']}), la MISMA vigencia ({da['vigencia']}) y autoridad "
            f"COMPARABLE ({da['authority_class']} / {db['authority_class']}), y devuelven "
            f"valores INCOMPATIBLES ({normalizar_valor(valor_a)!r} vs "
            f"{normalizar_valor(valor_b)!r}) que la regla de precedencia NO resuelve "
            f"(empatan en autoridad, vigencia y prioridad).")
    else:
        fallos = [k for k, v in condiciones.items() if not v]
        detalles = {
            "misma_semantica": "semántica distinta o no declarada: miden cosas distintas",
            "mismo_objeto": "objeto distinto o no declarado: no hablan del mismo hecho",
            "misma_vigencia": (f"vigencia distinta ({da['vigencia'] or '?'} vs "
                               f"{db['vigencia'] or '?'}): una capa histórica no compite "
                               f"con la vigente"),
            "autoridad_comparable": (f"autoridad no comparable ({da['authority_class'] or '?'} "
                                     f"vs {db['authority_class'] or '?'}): contexto/calculado "
                                     f"no compite con oficial"),
            "valores_incompatibles": (f"valores compatibles o no utilizables "
                                      f"({normalizar_valor(valor_a)!r} vs "
                                      f"{normalizar_valor(valor_b)!r})"),
            "precedencia_no_resuelve": ("la regla de precedencia SÍ resuelve: hay una fuente "
                                        "estrictamente superior (autoridad/vigencia/prioridad)"),
        }
        motivo = ("NO es conflicto — " + "; ".join(detalles[k] for k in fallos) + ".")
    return VeredictoConflicto({
        "conflict": hay,
        "reason": motivo,
        "sources": [da["source_id"], db["source_id"]],
        "values": [{"source_id": da["source_id"], "value": valor_a},
                   {"source_id": db["source_id"], "value": valor_b}],
        "semantics": da["semantics"] if misma_semantica else None,
        "object_key": da["object_key"] if mismo_objeto else None,
        "vigencia": da["vigencia"] if misma_vigencia else None,
        "authority_class": da["authority_class"],
        "conditions": condiciones,
        "unmet": fallos,
        "descriptors": [da, db],
    })


# ── resolución ───────────────────────────────────────────────────────────────
def _consulta(sid: str, consultas: Any) -> Optional[Dict[str, Any]]:
    """`consultas` es un mapa `source_id -> SourceResult` o un callable por fuente."""
    if consultas is None:
        return None
    resultado = consultas(sid) if callable(consultas) else (consultas or {}).get(sid)
    return resultado if isinstance(resultado, dict) else None


def _estado(resultado: Dict[str, Any]) -> Tuple[str, str]:
    estado = str(resultado.get("status") or "")
    if estado in ds.ESTADOS:
        return estado, ""
    return ds.CONSULTA_FALLIDA, (f"Estado «{estado or 'vacío'}» no declarado en el contrato "
                                 f"§27: se trata como QUERY_FAILED (nunca como NO_MATCH).")


def _extraer_valor(payload: Any, campos: Sequence[str]) -> Any:
    """Valor del atributo dentro del payload: primer campo declarado que casa; si
    ninguno casa, el payload COMPLETO es el valor."""
    if isinstance(payload, dict) and campos:
        for campo in campos:
            objetivo = _norm(campo)
            for clave, valor in payload.items():
                if _norm(clave) == objetivo:
                    return valor
    return payload


def _intento(entrada: Dict[str, Any], estado: str, valor: Any, motivo: str) -> Dict[str, Any]:
    return {
        "source_id": entrada["source_id"],
        "status": estado,
        "value": valor,
        "rejected_reason": motivo,
        "escalon_step": entrada["escalon_step"],
        "order_index": entrada["order_index"],
        "authority_class": entrada["authority_class"],
        "vigencia": entrada["vigencia"],
        "semantics": entrada["semantics"],
        "object_key": entrada["object_key"],
        "role": entrada["role"],
        "ladder_role": "",
    }


def _clave_rank(entrada: Dict[str, Any]) -> List[Any]:
    return list(entrada["rank"])


def resolver_atributo(atributo: str, *, consultas: Any = None,
                      fecha: Optional[str] = None,
                      registro: Optional[Dict[str, Any]] = None,
                      cobertura: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Resuelve UN atributo recorriendo su escalón de fuentes autorizadas.

    Devuelve un dict con `attribute`, `resolution_status` (uno de los 5 estados),
    `value`, `selected_source`, `selected_status`, `attempts` (ordenados),
    `fallbacks_used`, `conflict`, `provenance`, `annex_reference`, `semantics`,
    `object_key` y `vigencia`.
    """
    atributo = str(atributo)
    tabla = _cobertura(cobertura)
    regla = tabla.get(atributo)
    reg = _cargar_registro(registro)
    anexo = _anexo_id(atributo)
    res: Dict[str, Any] = {
        "attribute": atributo,
        "attribute_declared": regla is not None,
        "description": (regla or {}).get("description") or "",
        "resolution_status": UNRESOLVED,
        "value": None,
        "selected_source": None,
        "selected_status": None,
        "attempts": [],
        "fallbacks_used": [],
        "conflict": None,
        "provenance": {},
        "annex_reference": anexo,
        "semantics": (regla or {}).get("semantics"),
        "object_key": (regla or {}).get("object_key"),
        "vigencia": None,
        "fecha": fecha,
        "registry_version": reg.get("registry_version") or ds.REGISTRY_VERSION,
        "registry_status": reg.get("_status") or "AVAILABLE",
        "unregistered_sources": [],
        "first_escalon_source": None,
        "ladder_notes": [],
        "reason": "",
    }
    if regla is None:
        res["reason"] = ("Ninguna fuente del Source Pack declara este atributo: no existe "
                         "escalón que recorrer. No es un conflicto ni una ausencia de dato: "
                         "es cobertura inexistente.")
        res["ladder_notes"].append("cobertura_inexistente")
        return res

    # Atributo declarado SIN fuente de datos (decisión de producto): el mercado del
    # producto es un parámetro declarado por la corrida, no un dato de fuente. Se declara
    # la ausencia —`SOURCE_UNAVAILABLE`— y NUNCA se sustituye por otro dato ni por un valor
    # por defecto. No es NO_MATCH (no hubo consulta a ninguna fuente) ni UNRESOLVED (la
    # ausencia está declarada, no es un vacío sin explicación).
    if regla.get("no_fuente"):
        res["resolution_status"] = SOURCE_UNAVAILABLE
        res["reason"] = (regla.get("no_fuente_motivo")
                         or "El atributo no tiene fuente de datos declarada: se declara la "
                            "ausencia y NO se sustituye el valor.")
        res["ladder_notes"].append("sin_fuente_declarada")
        return res

    entradas, no_registradas = _escalon(atributo, regla, reg, fecha=fecha)
    res["unregistered_sources"] = no_registradas
    if no_registradas:
        res["ladder_notes"].append(
            "fuentes declaradas para el atributo que NO están en el registro: "
            + ", ".join(no_registradas))
    if not entradas:
        res["reason"] = ("El atributo está declarado, pero ninguna de sus fuentes existe en "
                         "el registro vigente: escalón vacío.")
        res["ladder_notes"].append("escalon_vacio")
        return res
    res["first_escalon_source"] = entradas[0]["source_id"]

    intentos: List[Dict[str, Any]] = []
    for e in entradas:
        if e["vigencia_status"] != "EN_VENTANA":
            intentos.append(_intento(e, NOT_RUN, None,
                                     e["vigencia_reason"] + " No se consulta: es ausencia "
                                     "de vigencia, no ausencia de dato ni NO_MATCH."))
    elegibles = [e for e in entradas if e["vigencia_status"] == "EN_VENTANA"]

    viables: List[Dict[str, Any]] = []
    referencias: List[Dict[str, Any]] = []
    detenido = False
    for e in elegibles:
        resultado = _consulta(e["source_id"], consultas)
        if resultado is None:
            intentos.append(_intento(e, NOT_RUN, None,
                                     "No se ejecutó consulta para esta fuente: se declara y "
                                     "se baja al siguiente escalón."))
            continue
        estado, nota_estado = _estado(resultado)
        valor = (_extraer_valor(resultado.get("payload_normalized"), e["campos"])
                 if estado == ds.DISPONIBLE else None)
        if estado == ds.DISPONIBLE and not valor_utilizable(valor):
            intentos.append(_intento(e, estado, valor,
                                     "La fuente respondió, pero el valor no es utilizable "
                                     "(vacío o centinela: None/\"\"/[]/{}/\"NO DISPONIBLE\"/"
                                     "\"N/D\"): no es un dato. Se baja al siguiente escalón."))
            continue
        if estado == ds.SIN_COINCIDENCIA:
            if not regla["admite_fallback_si_no_match"]:
                intentos.append(_intento(e, estado, None,
                                         "La fuente contestó NO_MATCH y el atributo NO admite "
                                         "que otra fuente lo aporte: se detiene el escalón."))
                detenido = True
                break
            intentos.append(_intento(e, estado, None,
                                     "La fuente contestó NO_MATCH (contestó: no hay dato "
                                     "suyo). El atributo admite que otra fuente lo aporte: se "
                                     "baja al siguiente escalón. Ausencia ≠ NO_MATCH."))
            continue
        if estado in ds.ESTADOS_SIN_DATO or estado == ds.CONSULTA_FALLIDA:
            intentos.append(_intento(e, estado, None,
                                     f"Ausencia declarada ({estado}): NUNCA se interpreta como "
                                     f"NO_MATCH ni como conflicto. Se baja al siguiente "
                                     f"escalón. {nota_estado}".strip()))
            continue
        # DISPONIBLE con valor utilizable.
        candidato = dict(e)
        candidato["value"] = valor
        candidato["status"] = estado
        if e["role"] == ROL_REFERENCIA:
            referencias.append(candidato)
            intentos.append(_intento(e, estado, valor,
                                     "Capa HISTÓRICA con valor: se conserva como provenance "
                                     "y referencia del anexo; NO compite con la vigente y no "
                                     "se asciende a valor operativo."))
        else:
            viables.append(candidato)
            intentos.append(_intento(e, estado, valor, ""))

    seleccionado: Optional[Dict[str, Any]] = None
    grupo: List[Dict[str, Any]] = []
    pares: List[VeredictoConflicto] = []
    if not detenido and viables:
        top = viables[0]
        grupo = [c for c in viables if _clave_rank(c) == _clave_rank(top)]
        if regla["admite_conflicto"] and len(grupo) > 1:
            for i in range(len(grupo)):
                for j in range(i + 1, len(grupo)):
                    veredicto = es_conflicto(grupo[i], grupo[j], registro=reg,
                                             attribute=atributo, cobertura=tabla)
                    if veredicto:
                        pares.append(veredicto)
        elif not regla["admite_conflicto"] and len(viables) > 1:
            res["ladder_notes"].append(
                "El atributo declara `admite_conflicto=False` (fuentes de contexto o "
                "calculadas): sus discrepancias NO se declaran CONFLICT, van al anexo.")

    if pares:
        afectadas = []
        for p in pares:
            for sid in p["sources"]:
                if sid not in afectadas:
                    afectadas.append(sid)
        res["resolution_status"] = AMBIGUOUS
        res["conflict"] = {
            "label": CONFLICT,
            "attribute": atributo,
            "resolution_status": AMBIGUOUS,
            "reason": (" ".join(p["reason"] for p in pares) +
                       " No se elige ninguna de las dos: se declara el conflicto con sus "
                       "candidatos y se conserva todo en el anexo."),
            "sources": afectadas,
            "values": [{"source_id": v["source_id"], "value": v["value"]}
                       for p in pares for v in p["values"]],
            "pairs": [{"sources": p["sources"], "values": p["values"], "reason": p["reason"]}
                      for p in pares],
            "semantics": pares[0]["semantics"],
            "object_key": pares[0]["object_key"],
            "vigencia": pares[0]["vigencia"],
            "authority_class": pares[0]["authority_class"],
        }
        res["reason"] = res["conflict"]["reason"]
        res["vigencia"] = pares[0]["vigencia"]
    elif viables:
        seleccionado = viables[0]
        res["value"] = seleccionado["value"]
        res["selected_source"] = seleccionado["source_id"]
        res["selected_status"] = seleccionado["status"]
        res["vigencia"] = seleccionado["vigencia"]
        res["semantics"] = seleccionado["semantics"]
        res["object_key"] = seleccionado["object_key"]
        res["fallbacks_used"] = [e["source_id"]
                                 for e in entradas[:seleccionado["order_index"]]]
        res["resolution_status"] = (RESOLVED_PRIMARY if seleccionado["order_index"] == 0
                                    else RESOLVED_FALLBACK)
        corroboran = [c["source_id"] for c in grupo[1:]
                      if valores_compatibles(c["value"], seleccionado["value"])]
        if corroboran:
            res["ladder_notes"].append("Valor corroborado por: " + ", ".join(corroboran))
        if referencias:
            res["ladder_notes"].append(
                "Capas históricas conservadas como referencia (NO compiten con la vigente): "
                + ", ".join(r["source_id"] for r in referencias))
        if res["resolution_status"] == RESOLVED_FALLBACK:
            res["reason"] = ("La fuente primaria del atributo no aportó valor utilizable: se "
                             "resolvió con el siguiente escalón autorizado "
                             f"({seleccionado['source_id']}). Fuentes intentadas antes: "
                             + (", ".join(res["fallbacks_used"]) or "ninguna") + ".")
        else:
            res["reason"] = (f"Resuelto por la fuente de mayor autoridad y vigencia declarada "
                             f"para el atributo ({seleccionado['source_id']}).")
        res["provenance"] = _provenance(seleccionado, res, corroboran, referencias)
    else:
        # Sin valor operativo: distinguir AUSENCIA de CUBRIR-SIN-DATO.
        estados_intento = [i["status"] for i in intentos]
        hay_ausencia = any(s in ds.ESTADOS_SIN_DATO or s == ds.CONSULTA_FALLIDA
                           for s in estados_intento)
        hay_no_match = ds.SIN_COINCIDENCIA in estados_intento
        if referencias:
            res["resolution_status"] = SOURCE_UNAVAILABLE
            res["reason"] = ("Solo hay capas HISTÓRICAS con valor: NO se ascienden a valor "
                             "operativo (una histórica nunca compite con la vigente). Se "
                             "declara ausencia de la capa aplicable y las históricas quedan "
                             "como referencia del anexo.")
            res["fallbacks_used"] = [r["source_id"] for r in referencias]
        elif detenido:
            res["resolution_status"] = UNRESOLVED
            res["reason"] = ("La fuente que contestó devolvió NO_MATCH y el atributo no admite "
                             "que otra fuente lo aporte: el hecho queda sin resolver, sin "
                             "fabricar ausencia ni conflicto.")
        elif hay_ausencia:
            res["resolution_status"] = SOURCE_UNAVAILABLE
            res["reason"] = ("Ninguna fuente aplicable devolvió valor: hay ausencias "
                             "declaradas (SOURCE_UNAVAILABLE / NOT_SUPPORTED / QUERY_FAILED). "
                             "Una ausencia NO es NO_MATCH ni un conflicto, y NO se sustituye "
                             "por cero ni por un valor por defecto.")
        elif hay_no_match:
            # `NO_MATCH` es un estado de fuente que SÍ contestó: no es ausencia.
            res["resolution_status"] = UNRESOLVED
            res["reason"] = ("Las fuentes aplicables que contestaron devolvieron NO_MATCH: el "
                             "resultado es «sin dato en las fuentes que contestaron», "
                             "declarado como UNRESOLVED; el resto del escalón no se pudo "
                             "consultar. Nunca se declara como valor cero.")
        else:
            res["resolution_status"] = SOURCE_UNAVAILABLE
            res["reason"] = ("No se ejecutó ninguna consulta para las fuentes del atributo: no "
                             "puede afirmarse nada sobre el dato. Se declara SOURCE_UNAVAILABLE "
                             "(nunca NO_MATCH).")

    roles = _roles(res, regla, seleccionado, grupo, viables, referencias, pares)
    for intento in intentos:
        intento["ladder_role"] = roles.get(intento["source_id"], "NO_SELECCIONADA")
    res["attempts"] = intentos
    if res["resolution_status"] not in ESTADOS_RESOLUCION:  # blindaje del vocabulario
        raise AssertionError(f"Estado de resolución no declarado: {res['resolution_status']}")
    _blindar_ausencias(res)
    return res


def _provenance(seleccionado: Dict[str, Any], res: Dict[str, Any], corroban: List[str],
                referencias: List[Dict[str, Any]]) -> Dict[str, Any]:
    prov = dict(seleccionado["registry"])
    prov.update({
        "attribute": res["attribute"],
        "resolution_status": res["resolution_status"],
        "semantics": seleccionado["semantics"],
        "object_key": seleccionado["object_key"],
        "vigencia": seleccionado["vigencia"],
        "escalon_step": seleccionado["escalon_step"],
        "escalon_source_id": seleccionado["source_id"],
        "escalon_order": seleccionado["order_index"],
        "is_fallback": res["resolution_status"] == RESOLVED_FALLBACK,
        "fallbacks_used": list(res["fallbacks_used"]),
        "corroborated_by": list(corroban),
        "historical_references": [r["source_id"] for r in referencias],
        "source_priority": seleccionado["source_priority"],
        "priority_origin": seleccionado["priority_origin"],
        "annex_reference": res["annex_reference"],
        "registry_version": res["registry_version"],
        "fecha": res["fecha"],
        "ladder_version": PACK_ETIQUETA,
    })
    return prov


def _roles(res: Dict[str, Any], regla: Dict[str, Any],
           seleccionado: Optional[Dict[str, Any]],
           grupo: List[Dict[str, Any]], viables: List[Dict[str, Any]],
           referencias: List[Dict[str, Any]],
           pares: List[VeredictoConflicto]) -> Dict[str, str]:
    roles: Dict[str, str] = {}
    for r in referencias:
        roles[r["source_id"]] = "REFERENCIA_HISTORICA"
    if res["resolution_status"] == AMBIGUOUS:
        en_conflicto = [sid for p in pares for sid in p["sources"]]
        for sid in en_conflicto:
            roles[sid] = "EN_CONFLICTO"
        for c in viables:
            roles.setdefault(c["source_id"], "DESPLAZADA_POR_PRECEDENCIA")
    elif seleccionado is not None:
        roles[seleccionado["source_id"]] = "SELECCIONADA"
        for c in viables:
            sid = c["source_id"]
            if sid == seleccionado["source_id"]:
                continue
            if valores_compatibles(c["value"], seleccionado["value"]):
                roles[sid] = "CORROBORA"
            elif (_norm(c["semantics"]) != _norm(seleccionado["semantics"])
                  or _norm(c["object_key"]) != _norm(seleccionado["object_key"])):
                roles[sid] = "COMPLEMENTARIA"
            elif _clave_rank(c) != _clave_rank(seleccionado):
                roles[sid] = "DESPLAZADA_POR_PRECEDENCIA"
            elif not regla["admite_conflicto"]:
                roles[sid] = "DISCREPANCIA_SIN_CONFLICTO"
            else:
                roles[sid] = "DESPLAZADA_POR_PRECEDENCIA"
    return roles


def _blindar_ausencias(res: Dict[str, Any]) -> None:
    """§27/§10: ningún estado de ausencia se convierte en NO_MATCH en NINGÚN punto."""
    if res["resolution_status"] == ds.SIN_COINCIDENCIA:
        raise AssertionError("La escalera no puede resolver con NO_MATCH: use UNRESOLVED.")
    for intento in res["attempts"]:
        if intento["status"] == ds.FUENTE_NO_DISPONIBLE and not intento["rejected_reason"]:
            raise AssertionError("Ausencia declarada sin motivo: prohibido.")


# ── dominio completo ─────────────────────────────────────────────────────────
def resolver_dominio(atributos_por_dominio: Dict[str, Any], *, consultas: Any = None,
                     fecha: Optional[str] = None,
                     registro: Optional[Dict[str, Any]] = None,
                     cobertura: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Resuelve un CONJUNTO de atributos.

    `atributos_por_dominio` acepta dos formas:
      · `{atributo: consultas}`  (mapa `source_id -> SourceResult` o callable por
        atributo) — la forma directa;
      · `{dominio: [atributo, ...]}` con `consultas` global — agrupa por dominio.

    La forma se decide por el TIPO del valor: lista/tupla/conjunto → agrupación por
    dominio; mapa o callable → consultas del atributo. Un anidamiento
    `{dominio: {atributo: consultas}}` NO se interpreta como dominio: hay que aplanarlo a
    `{atributo: consultas}`.

    Devuelve `{"resultados": {atributo: resultado}, "resumen": {...}, "dominios": {...}}`.
    El `resumen` cuenta: `resolved_primary`, `resolved_fallback`, `unresolved`,
    `ambiguous`, `source_unavailable` y `conflicts`.
    """
    consultas_por_atributo: Dict[str, Any] = {}
    dominios: Dict[str, List[str]] = {}
    for clave, valor in (atributos_por_dominio or {}).items():
        if isinstance(valor, (list, tuple, set, frozenset)):
            dominios[str(clave)] = [str(a) for a in valor]
            for attr in dominios[str(clave)]:
                consultas_por_atributo.setdefault(attr, consultas)
        else:
            consultas_por_atributo[str(clave)] = valor if valor is not None else consultas

    resultados: Dict[str, Dict[str, Any]] = {}
    for atributo, cons in consultas_por_atributo.items():
        resultados[atributo] = resolver_atributo(atributo, consultas=cons, fecha=fecha,
                                                registro=registro, cobertura=cobertura)

    resumen = {
        "resolved_primary": 0,
        "resolved_fallback": 0,
        "unresolved": 0,
        "ambiguous": 0,
        "source_unavailable": 0,
        "conflicts": 0,
        "resolved": 0,
        "total": len(resultados),
        "registry_status": _cargar_registro(registro).get("_status") or "AVAILABLE",
    }
    for r in resultados.values():
        estado = r["resolution_status"]
        if estado == RESOLVED_PRIMARY:
            resumen["resolved_primary"] += 1
            resumen["resolved"] += 1
        elif estado == RESOLVED_FALLBACK:
            resumen["resolved_fallback"] += 1
            resumen["resolved"] += 1
        elif estado == UNRESOLVED:
            resumen["unresolved"] += 1
        elif estado == AMBIGUOUS:
            resumen["ambiguous"] += 1
        elif estado == SOURCE_UNAVAILABLE:
            resumen["source_unavailable"] += 1
        if r["conflict"]:
            resumen["conflicts"] += 1
    return {"resultados": resultados, "resumen": resumen, "dominios": dict(dominios),
            "annex_reference": "ANEXO-FUENTES-DOMINIO"}


def _solo_resultados(resultados: Any) -> Dict[str, Dict[str, Any]]:
    if isinstance(resultados, dict) and isinstance(resultados.get("resultados"), dict):
        return resultados["resultados"]
    return resultados or {}


# ── vistas para DICTUS y para el ANEXO ───────────────────────────────────────
def solo_valor_resuelto(resultados: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Lo que DICTUS imprime: SOLO el valor resuelto y su provenance.

    Nada de intentos, fallbacks ni discrepancias: eso vive en el anexo. Un atributo sin
    valor resuelto (`UNRESOLVED`, `AMBIGUOUS`, `SOURCE_UNAVAILABLE`) NO aparece aquí.
    """
    cuerpo: Dict[str, Any] = {}
    for atributo, r in _solo_resultados(resultados).items():
        if not isinstance(r, dict):
            continue
        if r.get("resolution_status") in (RESOLVED_PRIMARY, RESOLVED_FALLBACK):
            cuerpo[atributo] = {"value": r.get("value"),
                                "provenance": dict(r.get("provenance") or {})}
    return cuerpo


def anexo_alternativas(resultados: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Fuentes intentadas / fallback / históricas / en conflicto — para el ANEXO."""
    anexo: Dict[str, Any] = {}
    for atributo, r in _solo_resultados(resultados).items():
        if not isinstance(r, dict):
            continue
        intentos = list(r.get("attempts") or [])
        alternativas = [i for i in intentos if i.get("ladder_role") != "SELECCIONADA"]
        anexo[atributo] = {
            "annex_reference": r.get("annex_reference"),
            "resolution_status": r.get("resolution_status"),
            "reason": r.get("reason"),
            "selected_source": r.get("selected_source"),
            "semantics": r.get("semantics"),
            "object_key": r.get("object_key"),
            "vigencia": r.get("vigencia"),
            "sources_attempted": [i["source_id"] for i in intentos],
            "alternativas": alternativas,
            "fallbacks_used": list(r.get("fallbacks_used") or []),
            "historical_references": [i["source_id"] for i in intentos
                                      if i.get("ladder_role") == "REFERENCIA_HISTORICA"],
            "conflict": r.get("conflict"),
            "ladder_notes": list(r.get("ladder_notes") or []),
        }
    return anexo

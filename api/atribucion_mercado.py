# -*- coding: utf-8 -*-
"""ARHIAX RE — procedencia HONESTA de la tasa de mercado.

Decisión de producto (docs/source_pack/INSTITUTIONAL_PARTNERS.md): la **Lonja no es
una fuente de datos**. No aporta datos a DICTUS, no es `source_id`, no es
`authority_class`, no tiene dataset, contrato de datos, URL ni bloque de licencia.

Consecuencia de texto, y objeto de este módulo: el valor de mercado que usa el
producto es un **parámetro declarado por la corrida**, leído de un artefacto local de
metodología, **sin fuente externa automática verificable**. Cualquier texto que hoy
atribuya ese valor a una fuente inexistente se reescribe aquí a la verdad.

Reglas duras:
1. **No se inventa ninguna fuente sustituta.** Donde no hay fuente externa, se dice
   `sin fuente externa automática verificada`; donde no hay dato, `NO DISPONIBLE`.
2. **No se toca ningún identificador sellado** (`SOURCE_ID`, `METHODOLOGY_ID`, rutas,
   `api/acquisition.py`, `api/source_licenses_v2.py`) ni ninguna fórmula, umbral,
   compuerta, gramática o hash: esto es sólo texto legible.
3. **No se muta el artefacto metodológico.** El YAML conserva su declaración literal
   (es la traza de lo que se declaró); la etiqueta verdadera se aplica al exponerla.
"""
from __future__ import annotations

import re
import unicodedata
from typing import List, Optional

# ── vocabulario verdadero (único lugar donde se define) ───────────────────────
ETIQUETA_PARAMETROS = "parámetros declarados por la corrida"
SIN_FUENTE_EXTERNA = "sin fuente externa automática verificada"
NO_DISPONIBLE = "NO DISPONIBLE"
ETIQUETA_METODO = "Comparación de mercado (parámetros declarados por la corrida)"

# Nombre institucional que NO debe aparecer como fuente ni como práctica: no hay
# dataset, ni contrato, ni valor por m² suministrado por esa entidad.
_ATRIBUCION_NO_ACREDITADA = "lonja"

# Fragmento de atribución: separador (+ · ; |) opcional y el resto de la mención.
_FRAGMENTO = re.compile(r"(?i)(?:\s*(?:\+|·|;|\|)\s*|\s*,\s*)?(?:la\s+)?lonja[^.;|·+]*")
_SEPARADORES_BORDE = re.compile(r"^[\s,;·|\-+]+|[\s,;·|\-+]+$")


def _sin_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto)
                   if unicodedata.category(c) != "Mn")


def contiene_atribucion_no_acreditada(texto: Optional[str]) -> bool:
    """¿El texto afirma o sugiere una fuente que no existe?"""
    if not texto:
        return False
    return _ATRIBUCION_NO_ACREDITADA in _sin_acentos(str(texto)).lower()


def limpiar_atribucion_no_acreditada(texto: Optional[str], *,
                                     por_defecto: Optional[str] = None) -> Optional[str]:
    """Devuelve el texto SIN la atribución no acreditada, conservando el resto literal.

    Si al quitar la atribución no queda nada, se declara `por_defecto`
    (`sin fuente externa automática verificada` si no se indica otro).
    """
    if texto is None:
        return None
    limpio = str(texto)
    if not contiene_atribucion_no_acreditada(limpio):
        return limpio
    limpio = _FRAGMENTO.sub("", limpio)
    limpio = re.sub(r"\s{2,}", " ", limpio)
    limpio = _SEPARADORES_BORDE.sub("", limpio).strip()
    if not limpio:
        return por_defecto if por_defecto is not None else SIN_FUENTE_EXTERNA
    return limpio


def etiqueta_tasa(texto: Optional[str]) -> Optional[str]:
    """Etiqueta verdadera de la tasa/parámetros de mercado (idempotente).

    - Si no hay texto: `None` (el render no imprime la línea; nunca un texto falso).
    - Si el texto declara la fuente real (precio verificado en la constructora), se
      conserva tal cual y se añade QUÉ es y de dónde NO viene.
    - Si el texto era sólo la atribución no acreditada, se declara sin fuente externa.
    """
    if texto is None:
        return None
    actual = str(texto).strip()
    if not actual:
        return None
    if _sin_acentos(ETIQUETA_PARAMETROS) in _sin_acentos(actual):
        return actual                       # ya está etiquetado: idempotente
    limpio = limpiar_atribucion_no_acreditada(actual)
    if not limpio:
        return f"{ETIQUETA_PARAMETROS} — {SIN_FUENTE_EXTERNA}"
    if _sin_acentos(limpio).lower().strip() == _sin_acentos(SIN_FUENTE_EXTERNA).lower():
        return f"{ETIQUETA_PARAMETROS} — {limpio}"
    return f"{limpio} — {ETIQUETA_PARAMETROS} ({SIN_FUENTE_EXTERNA})"


def procedencia_de_mercado() -> dict:
    """Declaración de procedencia del valor de mercado, para provenance máquina."""
    return {
        "es_fuente_de_datos": False,
        "aporta_datos_a_dictus": False,
        "en_source_registry": False,
        "fuente_externa_verificable": False,
        "etiqueta": ETIQUETA_PARAMETROS,
        "nota": (f"El valor de mercado es {ETIQUETA_PARAMETROS} (artefacto local de "
                 f"metodología): {SIN_FUENTE_EXTERNA}. La Lonja no es una fuente de "
                 f"datos y no se sustituye por ninguna fuente inventada."),
    }


# ══════════════════════════════════════════════════════════════════════════════
# COMPUERTA SEMÁNTICA · ORIGEN DE TODA TASA O VALOR
# ══════════════════════════════════════════════════════════════════════════════
# Toda tasa o valor que el producto imprime debe declarar DE DÓNDE SALE. No basta con
# etiquetar «verificado»: el origen se clasifica en un vocabulario CERRADO y sólo dos
# clases pueden habilitar la valoración, y sólo con procedencia COMPLETA.
#
# La regla no premia la buena intención: premia la TRAZABILIDAD. Un valor escrito a
# mano en un artefacto local es `MANUAL_CONFIG` aunque quien lo escribió lo haya
# verificado a ojo; un valor por defecto del código es `MODEL_PRIOR`. Ninguno de los
# dos abre la compuerta.

ORIGEN_EXTERNO = "EXTERNAL_SOURCE"          # fuente externa identificable y citada
ORIGEN_COMPUTADO = "COMPUTED_FROM_SOURCES"  # derivado de ≥2 fuentes citadas
ORIGEN_MANUAL = "MANUAL_CONFIG"             # escrito/configurado a mano (YAML, config)
ORIGEN_ESTATICO = "STATIC_REFERENCE"        # tabla/constante de referencia estática
ORIGEN_PRIOR = "MODEL_PRIOR"                # default o fallback codificado

ORIGENES = (ORIGEN_EXTERNO, ORIGEN_COMPUTADO, ORIGEN_MANUAL, ORIGEN_ESTATICO,
            ORIGEN_PRIOR)

# SÓLO estas dos clases pueden habilitar `VALUATION_GATE` (y sólo con procedencia
# completa). Las demás son legítimas para CONTEXTO, nunca para autorizar una cifra.
ORIGENES_HABILITANTES = frozenset({ORIGEN_EXTERNO, ORIGEN_COMPUTADO})

# Campos mínimos de procedencia por clase habilitante. Sin TODOS ellos, la clase
# declarada NO se honra: se degrada a la clase conservadora que corresponda.
PROCEDENCIA_EXTERNA = ("source_id", "proveedor", "fecha", "referencia", "sha256")
PROCEDENCIA_COMPUTADA_CAMPOS = ("proveedor", "fecha", "referencia", "sha256")
PROCEDENCIA_COMPUTADA_MIN_FUENTES = 2

# Etiquetas legibles (lo que el lector del documento entiende).
ETIQUETA_ORIGEN = {
    ORIGEN_EXTERNO: "fuente externa citada (verificable)",
    ORIGEN_COMPUTADO: "calculado a partir de fuentes citadas",
    ORIGEN_MANUAL: "valor declarado a mano por la corrida (sin fuente externa automática)",
    ORIGEN_ESTATICO: "referencia estática (no es una medición de la corrida)",
    ORIGEN_PRIOR: "valor por defecto del modelo (sin fuente: no autoriza cifra)",
}

# Etiqueta de la ENTIDAD que declara la metodología local. El artefacto YAML nombra una
# entidad que NO es fuente de datos del producto: exponerla como proveedora sería
# afirmar una fuente que no existe. Se declara lo que es y se conserva la traza.
ENTIDAD_NO_VERIFICADA = "artefacto local de metodología (sin institución proveedora verificada)"


def entidad_declarada(texto: Optional[str]) -> Optional[str]:
    """Declaración HONESTA de la entidad que firma la metodología local.

    Si el artefacto nombra una entidad que el producto NO reconoce como fuente de
    datos, se declara `ENTIDAD_NO_VERIFICADA` en lugar de imprimir el nombre: el
    nombre no es una fuente y presentarlo como tal es exactamente lo prohibido. La
    traza literal se conserva en el artefacto (YAML) y en `docs/source_pack/**`.
    """
    if texto is None:
        return None
    if contiene_atribucion_no_acreditada(texto):
        return ENTIDAD_NO_VERIFICADA
    return str(texto)


def _procedencia_faltante(declaracion: dict, campos, minimo_fuentes=None):
    """Campos de procedencia ausentes (y fuentes insuficientes, si aplica)."""
    faltan = []
    for campo in campos:
        valor = declaracion.get(campo)
        if valor is None or (isinstance(valor, str) and not valor.strip()):
            faltan.append(campo)
    if minimo_fuentes is not None:
        fuentes = declaracion.get("fuentes") or []
        if not isinstance(fuentes, (list, tuple)):
            return faltan + ["fuentes[]"]
        if len(fuentes) < minimo_fuentes:
            faltan.append(f"fuentes[] (se exigen >= {minimo_fuentes})")
        else:
            for i, f in enumerate(fuentes):
                if not isinstance(f, dict):
                    faltan.append(f"fuentes[{i}]")
                    continue
                for campo in PROCEDENCIA_COMPUTADA_CAMPOS:
                    v = f.get(campo)
                    if v is None or (isinstance(v, str) and not v.strip()):
                        faltan.append(f"fuentes[{i}].{campo}")
    return faltan


def clasificar_origen(declaracion: Optional[dict], *,
                      por_defecto: str = ORIGEN_MANUAL) -> dict:
    """Clasifica el ORIGEN de una tasa/valor y decide si puede habilitar la valoración.

    `declaracion` es el registro que acompaña al valor (la fila del artefacto local, el
    bloque de configuración o la constante del código). Claves reconocidas:

        origen_tipo  : una de `ORIGENES`
        proveedor / fecha / referencia / sha256 / source_id  : procedencia
        fuentes      : lista de registros con proveedor/fecha/referencia/sha256

    Devuelve un dict con:
        origin            : clase EFECTIVA (nunca una clase habilitante sin procedencia)
        origin_declarado  : lo que el artefacto declaró (para que la degradación sea visible)
        origin_gate       : ¿puede habilitar `VALUATION_GATE`?
        origin_blockers   : motivos legibles de la NO habilitación (nunca vacío si falla)
        origin_provenance : la procedencia copiada (para trazas y hashes)
        origin_etiqueta   : texto legible para el documento
    """
    declaracion = declaracion if isinstance(declaracion, dict) else {}
    declarado = declaracion.get("origen_tipo")
    declarado = str(declarado).strip().upper() if declarado else None
    procedencia = {campo: declaracion.get(campo)
                   for campo in ("source_id", "proveedor", "fecha", "referencia",
                                 "sha256", "fuentes") if campo in declaracion}
    blockers: List[str] = []

    if declarado not in ORIGENES:
        efectivo = por_defecto
        blockers.append(
            f"origen no declarado por el artefacto: se clasifica {efectivo} "
            f"(no habilita la valoración)")
    elif declarado in ORIGENES_HABILITANTES:
        if declarado == ORIGEN_EXTERNO:
            faltan = _procedencia_faltante(declaracion, PROCEDENCIA_EXTERNA)
        else:
            faltan = _procedencia_faltante(declaracion, (),
                                           minimo_fuentes=PROCEDENCIA_COMPUTADA_MIN_FUENTES)
        if faltan:
            efectivo = por_defecto
            blockers.append(
                f"origen declarado {declarado} SIN procedencia completa "
                f"(falta: {', '.join(faltan)}): se degrada a {efectivo}")
        else:
            efectivo = declarado
    else:
        efectivo = declarado
        blockers.append(
            f"origen {efectivo} no habilita la valoración "
            f"({ETIQUETA_ORIGEN.get(efectivo, efectivo)})")

    gate = efectivo in ORIGENES_HABILITANTES and not blockers
    return {
        "origin": efectivo,
        "origin_declarado": declarado,
        "origin_gate": bool(gate),
        "origin_blockers": blockers,
        "origin_provenance": procedencia,
        "origin_etiqueta": ETIQUETA_ORIGEN.get(efectivo, efectivo),
    }


# Nota sobre el artefacto local: sus filas declaran su `fuente` en TEXTO LIBRE. Un
# texto de fuente SIN `origen_tipo` y SIN procedencia estructurada (id de fuente,
# fecha, referencia y hash) NO es una fuente externa verificable: es un valor
# configurado a mano. La ausencia de declaración NUNCA se interpreta como fuente.

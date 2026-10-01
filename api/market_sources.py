# -*- coding: utf-8 -*-
"""ARHIAX RE — SOURCE PACK v1.0-R1 · `LONJA_MARKET_BAQ`: de fuente formalizada a
NO FUENTE declarada (decisión de producto vigente).

DECISIÓN DE PRODUCTO (docs/source_pack/INSTITUTIONAL_PARTNERS.md,
`api/source_licenses_v2.py::PARTNERS_INSTITUCIONALES`): la **Lonja no es una fuente
de datos**. No aporta datos a DICTUS, no es `source_id` del Source Registry, no tiene
dataset, contrato de datos, URL, bloque de licencia ni valor por m² suministrado.

Qué significa para esta pieza (reconciliación de la divergencia declarada en
`INSTITUTIONAL_PARTNERS.md:35-55`):

  · `SOURCE_ID = "LONJA_MARKET_BAQ"` es un **identificador histórico sellado**: NO se
    renombra (viaja en hashes) y NO se presenta como fuente.
  · **`LONJA_MARKET_BAQ` ya no está en el Source Registry** (`sources` de
    `docs/source_pack/barranquilla_sources_v1.json`). Vive donde le corresponde: como
    ALIADO INSTITUCIONAL, en el bloque `no_fuentes_institucionales` del registro.
  · La consulta de mercado es **fail-closed**: al no ser fuente, declara la ausencia
    (`SOURCE_UNAVAILABLE` / `DATOS_AUSENTES`) y **NUNCA** sirve un valor como si
    viniera de una fuente, ni lo sustituye por un valor por defecto, ni por el
    promedio de otros sectores. El **valor declarado por la corrida** (una constante
    escrita a mano en el artefacto local de metodología) se conserva ETIQUETADO como
    tal, porque no se oculta información: se declara su procedencia real.
  · `api/market_context.py` (y el artefacto local que él lee) sigue siendo la
    METODOLOGÍA del producto y la ÚNICA autoridad de la tasa que usa la valoración.
    Esta pieza no toca valoración, fórmulas, compuerta, hash maestro ni PDF.

Lo que se CONSERVA de la pieza (no se borra funcionalidad): la tabla versionada
derivada del producto, la resolución automática por sector/alias con `AMBIGUOUS`
cuando no puede decidir, el contrato por fila (`CONTRATO_FILA`), la vigencia
declarada (`vigencia_ok`, fail-closed) y la prueba del Golden 040-646406.

Reglas duras de esta pieza
──────────────────────────
1. **Cero dependencia manual**: el valor por m² NUNCA viaja pegado a mano. Se
   resuelve por `lookup` contra la tabla declarada
   (`docs/source_pack/lonja_market_baq_v1.json`), y esa tabla se GENERA desde el
   artefacto local de metodología real (`derivar_tabla_desde_producto()`).
2. **Tabla por fila con contrato explícito** (`CONTRATO_FILA`): city, sector,
   neighborhood_aliases, property_typology, property_regime, economic_use,
   area_band, value_per_m2, range_low, range_high, effective_from, effective_to,
   sample_size, methodology_version, source_version, source_hash. Un atributo que
   el producto NO declara se deja AUSENTE (`null`) y se declara en
   `atributos_ausentes` (`DATOS_AUSENTES`): no se rellena con una suposición.
3. **Resolución automática y determinista** (`resolver_sector`): normaliza
   acentos/mayúsculas/separadores, resuelve por SECTOR o por ALIAS de barrio y
   aplica las restricciones que la fila SÍ declara (tipología, régimen, uso
   económico, banda de área). Si hay más de un candidato → `AMBIGUOUS` con los
   candidatos: nunca se elige uno en silencio.
4. **Vigencia declarada**: `vigencia_ok` compara `effective_from`/`effective_to`
   con la fecha de la corrida. Sin fechas o sin fecha de corrida → no puede
   afirmarse vigencia (fail-closed declarado, `vigencia_ok=False`).
5. Un estado de mercado que no quepa en los cinco estados cerrados de §27 se
   DICTA explícitamente en `MAPA_ESTADOS` y viaja además en el payload como
   `market_status`: la ambigüedad no se degrada a «no hay mercado» ni a un valor
   elegido a dedo.

Este módulo NO toca valoración, fórmulas, compuerta, hash maestro, PDF ni
`api/dictus_sources.py`. La valoración sigue operando como hoy: la tasa la sigue
resolviendo `api/market_context.py`.
"""
from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import re
import sys
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_DIR_API = Path(__file__).resolve().parent
_DIR_RAIZ = _DIR_API.parent


def _cargar_modulo(nombre: str, *rutas: Path):
    """Importa un módulo hermano de `api/` de forma determinista (sin depender del cwd)."""
    try:
        return importlib.import_module(nombre)
    except Exception:
        pass
    for ruta in rutas:
        if not ruta.exists():
            continue
        alias = f"_arhiax_{nombre}"
        ya = sys.modules.get(alias)
        if ya is not None:
            return ya
        spec = importlib.util.spec_from_file_location(alias, ruta)
        if spec is None or spec.loader is None:
            continue
        mod = importlib.util.module_from_spec(spec)
        sys.modules[alias] = mod
        try:
            spec.loader.exec_module(mod)
        except Exception:
            sys.modules.pop(alias, None)
            raise
        return mod
    raise ImportError(f"No se pudo cargar el módulo requerido: {nombre}")


ds = _cargar_modulo("dictus_sources", _DIR_API / "dictus_sources.py")
_mc = _cargar_modulo("market_context", _DIR_API / "market_context.py")
_am = _cargar_modulo("atribucion_mercado", _DIR_API / "atribucion_mercado.py")

# ── identidad histórica del artefacto (NO es una fuente) ──────────────────────
# `SOURCE_ID` es un IDENTIFICADOR SELLADO (viaja en hashes y en la adquisición):
# se conserva sin renombrar, pero se DECLARA que no es una fuente de datos.
SOURCE_ID = "LONJA_MARKET_BAQ"
SOURCE_ID_HISTORICO = SOURCE_ID
# S10 · identidad verdadera: no hay institución proveedora verificada (sin URL, sin
# contrato de datos, sin dataset, sin valor por m² suministrado por tercero).
SOURCE_NAME = "Parámetros de mercado declarados por la corrida — artefacto de metodología local"
INSTITUTION = "Artefacto local del producto (sin institución proveedora verificada)"
AUTHORITY_CLASS = ds.AUTORITATIVA_CONTRACTUAL
# Rol histórico declarado en el pack v1 (se conserva para trazabilidad de hashes
# antiguos) frente al rol VIGENTE, que es la decisión de producto.
PRODUCT_ROLE_HISTORICO = "CORE_MARKET"
PRODUCT_ROLE = "NOT_A_SOURCE"
# Doctrina, en dos banderas que cualquier consumidor puede consultar.
ES_FUENTE_DE_DATOS = False
EN_SOURCE_REGISTRY = False
APORTA_DATOS_A_DICTUS = False
# Autoridad CONTRACTUAL: sostiene la metodología de valoración, NUNCA una
# afirmación normativa territorial. No cambia con la decisión de producto.
ES_AUTORIDAD_NORMATIVA = AUTHORITY_CLASS in ds.CLASES_NORMATIVAS

DIR_PACK = _DIR_RAIZ / "docs" / "source_pack"
RUTA_TABLA = DIR_PACK / "lonja_market_baq_v1.json"
RUTA_REGISTRO = DIR_PACK / "barranquilla_sources_v1.json"
TABLA_VERSION = "lonja-market-baq-table/1.0.0"


def en_source_registry(registro: Optional[Dict[str, Any]] = None) -> bool:
    """¿El Source Registry del producto declara esta pieza como FUENTE de datos?

    Hoy la respuesta es **NO** por decisión de producto: `LONJA_MARKET_BAQ` fue
    retirada del registro y se declara como aliado institucional en
    `no_fuentes_institucionales`. La comprobación es de DATO (lee el registro), no una
    constante optimista: si alguien la reintrodujera como fuente, esto devuelve `True`
    y la consulta de mercado deja de servirse como si fuera una fuente.
    """
    if registro is None:
        try:
            registro = json.loads(RUTA_REGISTRO.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 — un registro ilegible no es prueba de fuente
            return False
    return SOURCE_ID in (registro.get("sources") or {})


# ── contrato de registro POR FILA ─────────────────────────────────────────────
CONTRATO_FILA: Tuple[str, ...] = (
    "city", "sector", "neighborhood_aliases", "property_typology", "property_regime",
    "economic_use", "area_band", "value_per_m2", "range_low", "range_high",
    "effective_from", "effective_to", "sample_size", "methodology_version",
    "source_version", "source_hash",
)
# Atributos que la fila puede NO declarar: se dejan ausentes y se declaran.
ATRIBUTOS_AUSENTABLES: Tuple[str, ...] = (
    "neighborhood_aliases", "property_typology", "property_regime", "economic_use",
    "area_band", "sample_size", "range_low", "range_high",
)
# Atributos que RESTRINGEN la resolución cuando la fila los declara.
ATRIBUTOS_RESTRICTIVOS: Tuple[str, ...] = (
    "city", "property_typology", "property_regime", "economic_use", "area_band",
)

# ── estados de la resolución de mercado (cerrados en este módulo) ─────────────
RESUELTO = "RESOLVED"
SIN_COINCIDENCIA = "NO_MATCH"
AMBIGUO = "AMBIGUOUS"
DATOS_AUSENTES = "DATOS_AUSENTES"
FUENTE_NO_DISPONIBLE = "SOURCE_UNAVAILABLE"
ESTADOS_MERCADO: Tuple[str, ...] = (RESUELTO, SIN_COINCIDENCIA, AMBIGUO,
                                    DATOS_AUSENTES, FUENTE_NO_DISPONIBLE)
# Ambigüedad y ausencia de datos NO son «no hay mercado»: se dictan aparte y se
# transportan al vocabulario CERRADO de §27 sin perder el motivo.
MAPA_ESTADOS: Dict[str, str] = {
    RESUELTO: ds.DISPONIBLE,
    SIN_COINCIDENCIA: ds.SIN_COINCIDENCIA,
    AMBIGUO: ds.CONSULTA_FALLIDA,        # la consulta no puede resolverse a UNA fila
    DATOS_AUSENTES: ds.NO_SOPORTADA,     # la tabla declara que el dato no existe
    FUENTE_NO_DISPONIBLE: ds.FUENTE_NO_DISPONIBLE,
}

# ── estados de la tabla versionada ────────────────────────────────────────────
TABLA_OK = "OK"
TABLA_AUSENTE = "TABLA_AUSENTE"
TABLA_INCOMPLETA = "TABLA_INCOMPLETA"

# ── estados de vigencia ───────────────────────────────────────────────────────
VIGENTE = "VIGENTE"
VENCIDA = "VENCIDA"
NO_INICIADA = "NO_INICIADA"
VIGENCIA_DESCONOCIDA = "DESCONOCIDA"

# ── tipos de coincidencia del sector ──────────────────────────────────────────
MATCH_EXACT = "EXACT"
MATCH_NORMALIZED_EXACT = "NORMALIZED_EXACT"
MATCH_ALIAS = "ALIAS"
MATCH_AMBIGUOUS = "AMBIGUOUS"
MATCH_NO_MATCH = "NO_MATCH"


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalizar(texto: Any) -> str:
    """Normaliza acentos, mayúsculas y separadores (`_`/`-`/espacios son lo mismo)."""
    t = unicodedata.normalize("NFKD", str(texto or ""))
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return " ".join(re.sub(r"[^0-9A-Za-z]+", " ", t).upper().split())


def _texto(valor: Any) -> Optional[str]:
    if valor is None:
        return None
    t = str(valor).strip()
    return t or None


def _area_banda(area_band: Any) -> Tuple[Optional[float], Optional[float]]:
    if isinstance(area_band, dict):
        return _a_float(area_band.get("min")), _a_float(area_band.get("max"))
    if isinstance(area_band, (list, tuple)) and len(area_band) == 2:
        return _a_float(area_band[0]), _a_float(area_band[1])
    return None, None


def _a_float(valor: Any) -> Optional[float]:
    try:
        return float(valor) if valor is not None else None
    except (TypeError, ValueError):
        return None


def _a_fecha(valor: Any) -> Optional[date]:
    if valor is None or valor == "":
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    t = str(valor).strip()
    for formato in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(t[:10], formato).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(t.replace("Z", "+00:00")).date()
    except ValueError:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# 1 · TABLA VERSIONADA
# ══════════════════════════════════════════════════════════════════════════════
def _fila_vacia(*, city: str, sector: str, valor: Any, low: Any, high: Any,
                effective_from: Any, effective_to: Any, methodology_version: Any,
                source_version: Any, source_hash: Any) -> Dict[str, Any]:
    """Fila con el contrato COMPLETO: lo que el producto no declara queda en `None`."""
    return {
        "city": city,
        "sector": sector,
        "neighborhood_aliases": [],
        "property_typology": None,
        "property_regime": None,
        "economic_use": None,
        "area_band": {"min": None, "max": None},
        "value_per_m2": valor,
        "range_low": low,
        "range_high": high,
        "effective_from": effective_from,
        "effective_to": effective_to,
        "sample_size": None,
        "methodology_version": methodology_version,
        "source_version": source_version,
        "source_hash": source_hash,
    }


def atributos_ausentes(fila: Dict[str, Any]) -> List[str]:
    """Atributos del contrato que la fila NO declara (se declaran, no se inventan)."""
    faltan: List[str] = []
    for campo in ATRIBUTOS_AUSENTABLES:
        valor = fila.get(campo)
        if valor is None or valor == [] or valor == "":
            faltan.append(campo)
        elif campo == "area_band":
            minimo, maximo = _area_banda(valor)
            if minimo is None and maximo is None:
                faltan.append(campo)
    if _texto(fila.get("value_per_m2")) is None and fila.get("value_per_m2") is None:
        faltan.append("value_per_m2")
    return faltan


def _ciudad_del_producto() -> Optional[str]:
    """Ciudad declarada por el registro de fuentes del propio producto."""
    try:
        reg = json.loads(Path(RUTA_REGISTRO).read_text(encoding="utf-8"))
    except Exception:
        return None
    return _texto(reg.get("ciudad"))


def derivar_tabla_desde_producto() -> Dict[str, Any]:
    """Genera la tabla de mercado DESDE el artefacto local de metodología del producto.

    Insumo único: `api/market_context.py` + el artefacto que él lee
    (`lonja_baq_metodologia.yaml`). Cada fila cita su valor declarado
    (`valor_suelo_por_sector.<sector>.valor_central_m2`), su rango y su vigencia.
    Ningún valor se escribe a mano: si el producto no lo declara, queda ausente.
    """
    met = _mc.market_methodology()
    metodologia = _mc._load_lonja()          # artefacto real (sin caché)
    sectores = metodologia.get("valor_suelo_por_sector") or {}
    ciudad = _ciudad_del_producto()
    filas: List[Dict[str, Any]] = []
    for clave in sectores:
        resolucion = _mc.resolve_market_sector(clave)
        if resolucion.get("matched_sector") is None:
            # El producto no resolvió este sector: se declara, no se rellena.
            filas.append({
                "city": ciudad, "sector": clave, "neighborhood_aliases": [],
                "property_typology": None, "property_regime": None,
                "economic_use": None, "area_band": {"min": None, "max": None},
                "value_per_m2": None, "range_low": None, "range_high": None,
                "effective_from": met.get("vigencia_desde"),
                "effective_to": met.get("vigencia_hasta"),
                "sample_size": None, "methodology_version": met.get("version"),
                "source_version": f"{met.get('file')}",
                "source_hash": met.get("sha256"),
                "_motivo": ("El producto no resolvió el sector "
                            f"«{clave}» con su propia metodología."),
            })
            continue
        fila = _fila_vacia(
            city=ciudad, sector=resolucion.get("matched_sector"),
            valor=resolucion.get("value_m2"),
            low=resolucion.get("rango_min_m2"), high=resolucion.get("rango_max_m2"),
            effective_from=met.get("vigencia_desde"), effective_to=met.get("vigencia_hasta"),
            methodology_version=met.get("version"),
            source_version=f"{met.get('file')}::{str(met.get('sha256'))[:12]}",
            source_hash=met.get("sha256"))
        # Procedencia declarada POR el producto para esta fila (texto de fuente y
        # vigencia del propio sector): se transcribe, no se interpreta.
        fila["source_date"] = resolucion.get("source_date")
        fila["fuente_declarada"] = resolucion.get("source")
        fila["valor_declarado_en"] = f"valor_suelo_por_sector.{clave}.valor_central_m2"
        fila["rango_declarado_en"] = (f"valor_suelo_por_sector.{clave}.rango_min_m2/"
                                      f"rango_max_m2")
        fila["atributos_ausentes_en_la_fila"] = atributos_ausentes(fila)
        filas.append(fila)
    return {
        "source_id": SOURCE_ID,
        "source_name": SOURCE_NAME,
        "institution": INSTITUTION,
        "authority_class": AUTHORITY_CLASS,
        "product_role": PRODUCT_ROLE,
        "table_version": TABLA_VERSION,
        "methodology_id": met.get("id"),
        "methodology_version": met.get("version"),
        "methodology_entity": _am.entidad_declarada(met.get("entity")),
        "methodology_file": met.get("file"),
        "methodology_sha256": met.get("sha256"),
        "source_version": f"{met.get('file')}::{str(met.get('sha256'))[:12]}",
        "vigencia": {"desde": met.get("vigencia_desde"), "hasta": met.get("vigencia_hasta")},
        "derivation": {
            "metodo": "api/market_context.py::market_methodology + resolve_market_sector",
            "artefacto": f"motor_tma_lonja_baq_v1.0/motor_tma_lonja_baq_v1.0/lonja_layer/"
                         f"{met.get('file')}",
            "ciudad_declarada_en": "docs/source_pack/barranquilla_sources_v1.json::ciudad",
            "generado_por": "api/market_sources.py::derivar_tabla_desde_producto",
            "regla": ("Todo valor proviene del artefacto metodológico del producto; "
                      "un atributo que el producto no declara queda AUSENTE."),
        },
        "generated_at": ahora(),
        "rows": filas,
        "source_hash": ds.hash_canonico(filas),
    }


def escribir_tabla(ruta: Optional[Path] = None) -> Path:
    """Escribe la tabla versionada con su `source_hash` canónico."""
    destino = Path(ruta or RUTA_TABLA)
    tabla = derivar_tabla_desde_producto()
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(tabla, ensure_ascii=False, indent=1, sort_keys=False),
                       encoding="utf-8")
    return destino


def cargar_tabla(ruta: Optional[Path] = None) -> Dict[str, Any]:
    """Carga la tabla versionada y VERIFICA su contrato por fila y su hash.

    Un problema NO se silencia: se declara (`estado`, `motivo`) y la resolución
    posterior queda en estado declarado (nunca con un valor supuesto).
    """
    p = Path(ruta or RUTA_TABLA)
    base: Dict[str, Any] = {
        "source_id": SOURCE_ID, "source_name": SOURCE_NAME, "institution": INSTITUTION,
        "authority_class": AUTHORITY_CLASS, "product_role": PRODUCT_ROLE,
        "table_version": None, "methodology_version": None, "source_version": None,
        "methodology_sha256": None, "generated_at": None, "vigencia": {},
        "derivation": {}, "rows": [], "estado": TABLA_AUSENTE, "motivo": "",
        "ruta": str(p), "hash_declarado": None, "hash_recalculado": None,
        "hash_verificado": False, "atributos_ausentes": [], "campos_faltantes": [],
    }
    if not p.exists():
        base["motivo"] = (f"No existe la tabla versionada de mercado ({p}): la fuente "
                          f"declara SOURCE_UNAVAILABLE y NO se sustituye el valor por "
                          f"ningún otro dato ni por un valor por defecto.")
        return base
    try:
        datos = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        base["motivo"] = f"La tabla versionada no es JSON legible: {type(exc).__name__}: {exc}"
        return base

    filas = [f for f in (datos.get("rows") or []) if isinstance(f, dict)]
    if not filas:
        base["estado"] = TABLA_AUSENTE
        base["motivo"] = "La tabla versionada no declara ninguna fila de mercado."
        return base
    campos_faltantes = sorted({k for f in filas for k in CONTRATO_FILA if k not in f})
    if campos_faltantes:
        base["estado"] = TABLA_INCOMPLETA
        base["campos_faltantes"] = campos_faltantes
        base["motivo"] = ("La tabla no cumple el contrato por fila: faltan "
                          + ", ".join(campos_faltantes)
                          + ". No se usa una tabla incompleta: se declara.")
        base["rows"] = filas
        return base

    for clave, campo in (("table_version", "table_version"),
                         ("methodology_version", "methodology_version"),
                         ("source_version", "source_version"),
                         ("methodology_sha256", "methodology_sha256"),
                         ("generated_at", "generated_at"), ("vigencia", "vigencia"),
                         ("derivation", "derivation")):
        base[clave] = datos.get(campo)
    base["rows"] = filas
    base["hash_declarado"] = datos.get("source_hash")
    base["hash_recalculado"] = ds.hash_canonico(filas)
    base["hash_verificado"] = (base["hash_declarado"] == base["hash_recalculado"])
    ausentes: List[str] = []
    for fila in filas:
        for atributo in (fila.get("atributos_ausentes_en_la_fila")
                         or atributos_ausentes(fila)):
            if atributo not in ausentes:
                ausentes.append(atributo)
    base["atributos_ausentes"] = ausentes
    base["estado"] = TABLA_OK
    base["motivo"] = (
        "Tabla versionada cargada y verificada; atributos que el producto NO declara "
        "y que por tanto NO restringen ni se inventan: "
        + (", ".join(ausentes) if ausentes else "ninguno"))
    if not base["hash_verificado"]:
        base["estado"] = TABLA_INCOMPLETA
        base["motivo"] = ("El `source_hash` declarado no coincide con el recalculado: la "
                          "tabla pudo modificarse fuera del método de derivación. No se usa.")
    return base


# ══════════════════════════════════════════════════════════════════════════════
# 2 · RESOLUCIÓN AUTOMÁTICA DE SECTOR (lookup, nunca valor a mano)
# ══════════════════════════════════════════════════════════════════════════════
def _coincide_sector(fila: Dict[str, Any], termino: str) -> Tuple[bool, Optional[str]]:
    """Coincidencia por sector o por ALIAS de barrio (normalizada). Devuelve (sí/no, alias)."""
    objetivo = normalizar(termino)
    if not objetivo:
        return False, None
    if normalizar(fila.get("sector")) == objetivo:
        return True, None
    for alias in (fila.get("neighborhood_aliases") or []):
        if normalizar(alias) == objetivo:
            return True, str(alias)
    return False, None


def _tipo_match(fila: Dict[str, Any], termino: str, alias: Optional[str]) -> str:
    if alias:
        return MATCH_ALIAS
    crudo = str(fila.get("sector") or "")
    if crudo.strip() == str(termino or "").strip():
        return MATCH_EXACT
    return MATCH_NORMALIZED_EXACT


def _evaluar_restricciones(fila: Dict[str, Any], *, typology: Any, regime: Any,
                           economic_use: Any, area_m2: Any) -> Dict[str, Any]:
    """Aplica SOLO las restricciones que la fila declara. Ausente ≠ restricción."""
    motivos: List[str] = []
    no_declarados: List[str] = []
    cumple = True
    entradas = {
        "property_typology": (fila.get("property_typology"), typology, "tipología"),
        "property_regime": (fila.get("property_regime"), regime, "régimen de propiedad"),
        "economic_use": (fila.get("economic_use"), economic_use, "uso económico"),
    }
    for campo, (exigido, observado, etiqueta) in entradas.items():
        exigido_t = _texto(exigido)
        if exigido_t is None:
            no_declarados.append(campo)
            continue
        observado_t = _texto(observado)
        if observado_t is None:
            cumple = False
            motivos.append(f"la fila exige {etiqueta}=«{exigido_t}» y la consulta no la "
                           f"declara: no puede afirmarse coincidencia")
            continue
        if normalizar(exigido_t) != normalizar(observado_t):
            cumple = False
            motivos.append(f"{etiqueta}: la fila exige «{exigido_t}» y la consulta declara "
                           f"«{observado_t}»")
    minimo, maximo = _area_banda(fila.get("area_band"))
    if minimo is None and maximo is None:
        no_declarados.append("area_band")
    else:
        area = _a_float(area_m2)
        if area is None:
            cumple = False
            motivos.append(f"la fila exige banda de área [{minimo}, {maximo}] m² y la "
                           f"consulta no declara área")
        elif (minimo is not None and area < minimo) or (maximo is not None and area > maximo):
            cumple = False
            motivos.append(f"área {area} m² fuera de la banda declarada "
                           f"[{minimo}, {maximo}] m²")
    return {"cumple": cumple, "motivos": motivos,
            "atributos_no_declarados_por_la_tabla": no_declarados}


def resolver_sector(*, tabla: Optional[Dict[str, Any]] = None,
                    city: Any = None, sector: Any = None, barrio: Any = None,
                    typology: Any = None, regime: Any = None, economic_use: Any = None,
                    area_m2: Any = None) -> Dict[str, Any]:
    """Resuelve la fila de mercado por lookup automático (nunca un valor pegado a mano).

    Criterios: SECTOR o ALIAS de barrio (normalizando acentos/mayúsculas/separadores)
    + las restricciones que la fila declara (ciudad, tipología, régimen, uso
    económico, banda de área). Estados: `RESOLVED | NO_MATCH | AMBIGUOUS |
    DATOS_AUSENTES | SOURCE_UNAVAILABLE`. Con más de un candidato devuelve
    `AMBIGUOUS` y los candidatos: jamás elige uno en silencio.
    """
    tabla = tabla if tabla is not None else cargar_tabla()
    base: Dict[str, Any] = {
        "estado": tabla.get("estado") if tabla.get("estado") != TABLA_OK else SIN_COINCIDENCIA,
        "source_id": SOURCE_ID, "product_role": PRODUCT_ROLE,
        "entrada": {"city": _texto(city), "sector": _texto(sector), "barrio": _texto(barrio),
                    "typology": _texto(typology), "regime": _texto(regime),
                    "economic_use": _texto(economic_use), "area_m2": _a_float(area_m2)},
        "match_type": MATCH_NO_MATCH, "fila": None, "sector": None, "alias_usado": None,
        "candidatos": [], "descartadas": [],
        "atributos_no_declarados_por_la_tabla": list(tabla.get("atributos_ausentes") or []),
        "datos_ausentes": [], "motivos": [], "tabla_estado": tabla.get("estado"),
        "tabla_hash_verificado": tabla.get("hash_verificado"),
        "tabla_version": tabla.get("table_version"),
    }
    if tabla.get("estado") == TABLA_AUSENTE:
        base["estado"] = FUENTE_NO_DISPONIBLE
        base["motivos"].append(tabla.get("motivo") or "tabla ausente")
        return base
    if tabla.get("estado") != TABLA_OK:
        base["estado"] = DATOS_AUSENTES
        base["motivos"].append(tabla.get("motivo") or "tabla no utilizable")
        return base

    termino = _texto(sector) or _texto(barrio)
    if not termino:
        base["estado"] = DATOS_AUSENTES
        base["motivos"].append("La consulta no declara sector ni barrio: sin término de "
                               "resolución no se elige ninguna fila.")
        return base

    candidatas: List[Dict[str, Any]] = []
    for fila in tabla.get("rows") or []:
        coincide, alias = _coincide_sector(fila, termino)
        if not coincide:
            continue
        evaluacion = _evaluar_restricciones(fila, typology=typology, regime=regime,
                                            economic_use=economic_use, area_m2=area_m2)
        registro = {
            "sector": fila.get("sector"), "city": fila.get("city"),
            "alias_usado": alias, "match_type": _tipo_match(fila, termino, alias),
            "value_per_m2": fila.get("value_per_m2"),
            "range_low": fila.get("range_low"), "range_high": fila.get("range_high"),
            "fila": fila,
            "atributos_no_declarados_por_la_tabla":
                evaluacion["atributos_no_declarados_por_la_tabla"],
        }
        if not evaluacion["cumple"]:
            registro["motivos"] = evaluacion["motivos"]
            base["descartadas"].append(registro)
            continue
        if city is not None and _texto(fila.get("city")) is not None \
                and normalizar(fila.get("city")) != normalizar(city):
            registro["motivos"] = [f"ciudad: la fila declara «{fila.get('city')}» y la "
                                   f"consulta declara «{_texto(city)}»"]
            base["descartadas"].append(registro)
            continue
        candidatas.append(registro)

    if not candidatas:
        base["estado"] = SIN_COINCIDENCIA
        base["motivos"].append(
            f"El sector/barrio «{termino}» no resuelve ninguna fila de la tabla: "
            + (f"{len(base['descartadas'])} fila(s) con ese nombre quedaron descartadas "
               f"por sus restricciones declaradas"
               if base["descartadas"] else
               "la tabla no declara ese sector ni ningún alias suyo")
            + ". Ausencia declarada: NO se sustituye por un valor por defecto ni por el "
              "promedio de otros sectores.")
        return base
    if len(candidatas) > 1:
        base["estado"] = AMBIGUO
        base["candidatos"] = [{k: v for k, v in c.items() if k != "fila"} for c in candidatas]
        base["motivos"].append(
            f"«{termino}» coincide con {len(candidatas)} filas sin que las restricciones "
            f"declaradas permitan decidir: se devuelve AMBIGUOUS con los candidatos y NO se "
            f"elige uno en silencio.")
        return base

    elegida = candidatas[0]
    base.update({
        "estado": RESUELTO, "match_type": elegida["match_type"],
        "fila": elegida["fila"], "sector": elegida["sector"],
        "alias_usado": elegida["alias_usado"],
        "datos_ausentes": atributos_ausentes(elegida["fila"]),
    })
    base["motivos"].append(
        f"Sector «{elegida['sector']}» resuelto por {elegida['match_type']}"
        + (f" (alias «{elegida['alias_usado']}»)" if elegida["alias_usado"] else "")
        + " desde la tabla versionada; los atributos que la tabla no declara no se "
          "aplican como restricción ni se rellenan.")
    return base


# ══════════════════════════════════════════════════════════════════════════════
# 3 · VIGENCIA
# ══════════════════════════════════════════════════════════════════════════════
def evaluar_vigencia(*, effective_from: Any, effective_to: Any,
                     fecha_corrida: Any) -> Dict[str, Any]:
    """¿La fila estaba vigente en la fecha de la corrida? Sin datos NO se afirma."""
    desde, hasta = _a_fecha(effective_from), _a_fecha(effective_to)
    corrida = _a_fecha(fecha_corrida)
    if corrida is None:
        return {"vigencia_ok": False, "estado": VIGENCIA_DESCONOCIDA,
                "effective_from": _texto(effective_from), "effective_to": _texto(effective_to),
                "fecha_corrida": _texto(fecha_corrida),
                "motivo": ("La corrida no declara fecha: no puede afirmarse vigencia "
                           "(fail-closed).")}
    if desde is None or hasta is None:
        return {"vigencia_ok": False, "estado": VIGENCIA_DESCONOCIDA,
                "effective_from": _texto(effective_from), "effective_to": _texto(effective_to),
                "fecha_corrida": corrida.isoformat(),
                "motivo": ("La fila no declara effective_from/effective_to: la vigencia no "
                           "puede afirmarse (fail-closed), aunque el valor exista.")}
    if corrida < desde:
        return {"vigencia_ok": False, "estado": NO_INICIADA, "effective_from": desde.isoformat(),
                "effective_to": hasta.isoformat(), "fecha_corrida": corrida.isoformat(),
                "motivo": (f"La fila entra en vigencia el {desde.isoformat()} y la corrida es "
                           f"del {corrida.isoformat()}.")}
    if corrida > hasta:
        return {"vigencia_ok": False, "estado": VENCIDA, "effective_from": desde.isoformat(),
                "effective_to": hasta.isoformat(), "fecha_corrida": corrida.isoformat(),
                "motivo": (f"VIGENCIA VENCIDA: la fila declara vigencia hasta el "
                           f"{hasta.isoformat()} y la corrida es del {corrida.isoformat()} "
                           f"({(corrida - hasta).days} día(s) después). El valor NO se "
                           f"presenta como vigente.")}
    return {"vigencia_ok": True, "estado": VIGENTE, "effective_from": desde.isoformat(),
            "effective_to": hasta.isoformat(), "fecha_corrida": corrida.isoformat(),
            "motivo": (f"Fila vigente entre {desde.isoformat()} y {hasta.isoformat()} para la "
                       f"corrida del {corrida.isoformat()}.")}


# ══════════════════════════════════════════════════════════════════════════════
# 4 · CONSULTA DE MERCADO → SourceResult de dictus_sources (§27)
# ══════════════════════════════════════════════════════════════════════════════
def consultar_mercado(*, city: Any = None, sector: Any = None, barrio: Any = None,
                      typology: Any = None, regime: Any = None, economic_use: Any = None,
                      area_m2: Any = None, fecha_corrida: Any = None,
                      tabla: Optional[Dict[str, Any]] = None,
                      ruta_tabla: Optional[Path] = None) -> Dict[str, Any]:
    """Consulta la pieza de mercado y devuelve el `SourceResult` del contrato §27.

    DOCTRINA (decisión de producto): esta pieza **NO es una fuente de datos**. Si el
    Source Registry no la declara como fuente (hoy no la declara: fue retirada), el
    estado es `SOURCE_UNAVAILABLE` con `value_per_m2 = None`: se DECLARA la ausencia y
    **no se sirve ningún valor como si viniera de una fuente**.

    Lo que sí viaja, etiquetado y separado, es el **valor declarado por la corrida**
    (`valor_declarado_por_la_corrida`), que es una constante escrita a mano en el
    artefacto local de metodología: se transcribe porque no se oculta información, y
    NUNCA se sustituye por un valor por defecto ni por el promedio de otros sectores.

    Procedencia completa (autoridad, `source_version`, `methodology_version`,
    `source_hash`, vigencia) y `vigencia_ok` calculado contra la fecha de la corrida.
    """
    tabla = tabla if tabla is not None else cargar_tabla(ruta_tabla)
    resolucion = resolver_sector(tabla=tabla, city=city, sector=sector, barrio=barrio,
                                 typology=typology, regime=regime,
                                 economic_use=economic_use, area_m2=area_m2)
    fila = resolucion.get("fila") or {}
    vigencia = evaluar_vigencia(
        effective_from=fila.get("effective_from", (tabla.get("vigencia") or {}).get("desde")),
        effective_to=fila.get("effective_to", (tabla.get("vigencia") or {}).get("hasta")),
        fecha_corrida=fecha_corrida)
    es_fuente = en_source_registry()
    estado = MAPA_ESTADOS.get(resolucion["estado"], ds.CONSULTA_FALLIDA)
    if not es_fuente:
        # Fail-closed por doctrina: no hay fuente de mercado que pueda «disponer» el dato.
        estado = ds.FUENTE_NO_DISPONIBLE

    provenance: Dict[str, Any] = {
        "source_id": SOURCE_ID,
        "source_name": SOURCE_NAME,
        "institution": INSTITUTION,
        "authority_class": AUTHORITY_CLASS,
        "product_role": PRODUCT_ROLE,
        "product_role_historico": PRODUCT_ROLE_HISTORICO,
        "es_fuente_de_datos": ES_FUENTE_DE_DATOS,
        "aporta_datos_a_dictus": APORTA_DATOS_A_DICTUS,
        "en_source_registry": es_fuente,
        "source_id_es_identificador_historico": True,
        "service": "Tabla versionada derivada del artefacto local de metodología",
        "query_method": ("lookup determinista por sector/alias + restricciones declaradas "
                         "(sin fuzzy semántico)"),
        "layer_id": None,
        "version_or_vigency": (f"metodología {tabla.get('methodology_version')} · vigencia "
                               f"{vigencia.get('effective_from')}→"
                               f"{vigencia.get('effective_to')}"),
        "precedence": "CURRENT_OFFICIAL",
        "license_or_terms": ("Artefacto local de metodología de mercado del producto "
                             "(licencia DECLARADA, contrato no verificado). No hay "
                             "institución proveedora verificada ni dataset de tercero: el "
                             "valor por m² NO lo suministra un proveedor externo."),
        "methodology_id": _mc.METHODOLOGY_ID,
        "methodology_version": tabla.get("methodology_version"),
        "methodology_sha256": tabla.get("methodology_sha256"),
        "source_version": tabla.get("source_version"),
        "table_version": tabla.get("table_version"),
        "table_path": tabla.get("ruta"),
        "source_hash": tabla.get("hash_declarado"),
        "source_hash_recalculado": tabla.get("hash_recalculado"),
        "source_hash_verificado": tabla.get("hash_verificado"),
        "effective_from": vigencia.get("effective_from"),
        "effective_to": vigencia.get("effective_to"),
        "fecha_corrida": vigencia.get("fecha_corrida"),
        "vigencia_ok": vigencia["vigencia_ok"],
        "vigencia_estado": vigencia["estado"],
        "vigencia_motivo": vigencia["motivo"],
        "market_status": resolucion["estado"],
        "match_type": resolucion.get("match_type"),
        "alias_usado": resolucion.get("alias_usado"),
        "sector_input": resolucion["entrada"].get("sector") or resolucion["entrada"].get("barrio"),
        "atributos_no_declarados_por_la_tabla":
            resolucion.get("atributos_no_declarados_por_la_tabla"),
        "datos_ausentes": resolucion.get("datos_ausentes"),
        "derivation": tabla.get("derivation"),
        "procedencia_declarada": _am.procedencia_de_mercado(),
        "queried_at": ahora(),
    }

    payload: Dict[str, Any] = {
        "market_status": resolucion["estado"],
        "sector": resolucion.get("sector"),
        "city": fila.get("city"),
        # NO se sirve el valor como dato de fuente: la pieza no es una fuente.
        "value_per_m2": None if not es_fuente else fila.get("value_per_m2"),
        "range_low": None if not es_fuente else fila.get("range_low"),
        "range_high": None if not es_fuente else fila.get("range_high"),
        "valor_declarado_por_la_corrida": {
            "es_fuente_de_datos": False,
            "etiqueta": _am.ETIQUETA_PARAMETROS,
            "sector": resolucion.get("sector"),
            "value_per_m2": fila.get("value_per_m2"),
            "range_low": fila.get("range_low"),
            "range_high": fila.get("range_high"),
            "match_type": resolucion.get("match_type"),
            "fuente_declarada": fila.get("fuente_declarada"),
            "vigencia_ok": vigencia["vigencia_ok"],
            "vigencia_estado": vigencia["estado"],
            "nota": ("Constante declarada en el artefacto local de metodología del producto; "
                     "sin fuente externa automática verificable. Se transcribe ETIQUETADA y "
                     "no se sustituye por ningún valor por defecto."),
        },
        "source_date": fila.get("source_date"),
        "fuente_declarada": fila.get("fuente_declarada"),
        "vigencia_ok": vigencia["vigencia_ok"],
        "vigencia_estado": vigencia["estado"],
        "vigencia_motivo": vigencia["motivo"],
        "match_type": resolucion.get("match_type"),
        "datos_ausentes": resolucion.get("datos_ausentes") or [],
        "atributos_no_declarados_por_la_tabla":
            resolucion.get("atributos_no_declarados_por_la_tabla") or [],
        "motivos": list(resolucion.get("motivos") or []),
        "candidatos": resolucion.get("candidatos") or [],
        "descartadas": [{k: v for k, v in d.items() if k != "fila"}
                        for d in (resolucion.get("descartadas") or [])],
        "trazabilidad": {"tabla_version": tabla.get("table_version"),
                         "valor_declarado_en": fila.get("valor_declarado_en"),
                         "rango_declarado_en": fila.get("rango_declarado_en")},
    }

    detail = " ".join(resolucion.get("motivos") or [])
    if resolucion["estado"] == RESUELTO and not vigencia["vigencia_ok"]:
        # La vigencia vencida del parámetro declarado se declara SIEMPRE (no se silencia).
        detail = ((detail + " " if detail else "") + "ATENCIÓN: " + vigencia["motivo"])
    if not es_fuente:
        detail = ("FUENTE NO DISPONIBLE (doctrina de producto): `" + SOURCE_ID + "` NO está en "
                  "el Source Registry — la Lonja no es una fuente de datos y no aporta el "
                  "valor por m². El valor de mercado del producto es un parámetro declarado "
                  "por la corrida (artefacto local de metodología), sin fuente externa "
                  "automática verificable: se declara la ausencia y NO se sustituye por "
                  "ningún otro dato ni por un valor por defecto. "
                  + (detail if detail else ""))
    if not detail:
        detail = f"Estado de mercado declarado: {resolucion['estado']}."

    resultado = ds.resultado(
        SOURCE_ID, estado, payload_normalized=payload,
        raw={"entrada": resolucion["entrada"], "fila": fila or None,
             "candidatos": resolucion.get("candidatos") or [],
             "descartadas": [{k: v for k, v in d.items() if k != "fila"}
                             for d in (resolucion.get("descartadas") or [])],
             "vigencia": vigencia},
        provenance=provenance, detail=detail, binding_status=ds.SIN_BINDING)
    # La ausencia de crudo persistido se DECLARA: esta pieza no escribe en
    # docs/source_pack/raw/ (intocable en esta ronda).
    resultado["raw_persisted"] = False
    resultado["raw_path"] = None
    return resultado


def mercado_utilizable(resultado: Dict[str, Any]) -> bool:
    """Fail-closed: una tasa de mercado sólo es utilizable si RESOLVIÓ como FUENTE y está
    vigente. Con la doctrina vigente (`LONJA_MARKET_BAQ` no es una fuente de datos) esto
    es **siempre False**: no hay fuente de mercado que pueda disponer el dato.
    """
    if not isinstance(resultado, dict) or resultado.get("status") != ds.DISPONIBLE:
        return False
    prov = resultado.get("provenance") or {}
    if prov.get("es_fuente_de_datos") is False or prov.get("en_source_registry") is False:
        return False
    payload = resultado.get("payload_normalized") or {}
    return bool(payload.get("value_per_m2")) and payload.get("vigencia_ok") is True


# ══════════════════════════════════════════════════════════════════════════════
# 5 · GOLDEN 040-646406
# ══════════════════════════════════════════════════════════════════════════════
RUTA_GOLDEN_RUN_STATE = (_DIR_RAIZ / "docs" / "forensics" / "040-646406" / "dictus_2b"
                         / "DICTUS_RUN_STATE_040-646406.json")


def _entradas_del_golden(run_state: Dict[str, Any]) -> Dict[str, Any]:
    """Extrae del run state REAL las entradas de la consulta (nada pegado a mano)."""
    mc = run_state.get("market_context") or {}
    uc = run_state.get("urban_context") or {}
    sector_met = mc.get("sector_metodologico") or {}

    def _campo(bloque, clave):
        valor = (bloque or {}).get(clave)
        return valor.get("value") if isinstance(valor, dict) else valor

    return {
        "city": run_state.get("ciudad"),
        "barrio": _campo(mc.get("barrio"), "value") or uc.get("barrio"),
        "estrato": _campo(mc.get("estrato"), "value") or uc.get("estrato"),
        "typology": _campo(mc.get("tipologia"), "value") or uc.get("tipologia"),
        "regime": uc.get("condicion_juridica"),
        "economic_use": _campo(mc.get("uso"), "value") or uc.get("destino_economico"),
        "area_m2": uc.get("area"),
        "fecha_corrida": run_state.get("generated_at"),
        "run_id": run_state.get("run_id"),
        "folio": (run_state.get("property_identity") or {}).get("folio"),
        "sector_declarado_por_la_corrida": sector_met.get("matched_sector"),
        "valor_declarado_por_la_corrida": sector_met.get("value_m2"),
        "banda_declarada_por_la_corrida": [sector_met.get("rango_min_m2"),
                                           sector_met.get("rango_max_m2")],
        "match_type_declarado_por_la_corrida": sector_met.get("match_type"),
    }


def resolver_mercado_golden(ruta_run_state: Optional[Path] = None,
                            *,
                            tabla: Optional[Dict[str, Any]] = None,
                            ruta_tabla: Optional[Path] = None) -> Dict[str, Any]:
    """Prueba obligatoria con el Golden: DECLARA qué resuelve y qué no, sin inventar.

    DOS planos, separados a propósito:

      · **Fuente de mercado**: NO existe (`es_fuente_de_datos=False`). `resuelve` es
        `False` por doctrina y el motivo es explícito.
      · **Parámetro declarado por la corrida**: se resuelve por lookup contra la tabla
        versionada (derivada del artefacto local de metodología) y se contrasta con el
        run state REAL para probar que NO se copia de él.
    """
    p = Path(ruta_run_state or RUTA_GOLDEN_RUN_STATE)
    if not p.exists():
        return {"resuelve": False, "estado": FUENTE_NO_DISPONIBLE, "sector": None,
                "valor_m2": None, "banda": None, "vigencia_ok": False,
                "ruta_run_state": str(p),
                "motivo": (f"No existe el estado de corrida del Golden ({p}): no hay entradas "
                           f"que resolver y NO se inventa ninguna."),
                "datos_ausentes": [], "resultado": None, "contraste_con_run_state": None,
                "es_fuente_de_datos": False, "en_source_registry": False,
                "parametro_declarado": None}
    try:
        run_state = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"resuelve": False, "estado": DATOS_AUSENTES,
                "sector": None, "valor_m2": None, "banda": None, "vigencia_ok": False,
                "ruta_run_state": str(p),
                "motivo": f"El estado de corrida no es JSON legible: {type(exc).__name__}: {exc}",
                "datos_ausentes": [], "resultado": None, "contraste_con_run_state": None,
                "es_fuente_de_datos": False, "en_source_registry": False,
                "parametro_declarado": None}

    entradas = _entradas_del_golden(run_state)
    # El término de resolución es el BARRIO oficial declarado por el producto, NO el
    # sector que el propio run state ya había resuelto: resolver con la respuesta
    # anterior no probaría nada.
    resultado = consultar_mercado(
        city=entradas["city"], sector=None, barrio=entradas["barrio"],
        typology=entradas["typology"], regime=entradas["regime"],
        economic_use=entradas["economic_use"], area_m2=entradas["area_m2"],
        fecha_corrida=entradas["fecha_corrida"], tabla=tabla, ruta_tabla=ruta_tabla)
    payload = resultado.get("payload_normalized") or {}
    prov = resultado.get("provenance") or {}
    declarado = payload.get("valor_declarado_por_la_corrida") or {}
    es_fuente = bool(prov.get("en_source_registry"))
    # `resuelve` = «el MERCADO resuelve como fuente». Hoy no: no hay fuente de mercado.
    resuelve = bool(es_fuente and payload.get("market_status") == RESUELTO
                    and resultado.get("status") == ds.DISPONIBLE)
    # `parametro_resuelto` = el valor DECLARADO POR LA CORRIDA se resolvió por lookup.
    parametro_resuelto = (declarado.get("value_per_m2") is not None
                          and payload.get("market_status") == RESUELTO)
    contraste = {
        "sector_declarado_por_la_corrida": entradas["sector_declarado_por_la_corrida"],
        "valor_declarado_por_la_corrida": entradas["valor_declarado_por_la_corrida"],
        "banda_declarada_por_la_corrida": entradas["banda_declarada_por_la_corrida"],
        "match_type_declarado_por_la_corrida":
            entradas["match_type_declarado_por_la_corrida"],
        "nota": ("El contraste es una COMPROBACIÓN de consistencia con el run state. El valor "
                 "resuelto NO se toma del run state: se resuelve por lookup contra la tabla "
                 "versionada, que a su vez se deriva del artefacto local de metodología del "
                 "producto. No es una fuente de datos externa."),
    }
    if parametro_resuelto:
        contraste["coincide_sector"] = (normalizar(declarado.get("sector"))
                                        == normalizar(entradas["sector_declarado_por_la_corrida"]))
        contraste["coincide_valor"] = (declarado.get("value_per_m2")
                                       == entradas["valor_declarado_por_la_corrida"])
    return {
        "resuelve": resuelve,
        "es_fuente_de_datos": ES_FUENTE_DE_DATOS,
        "en_source_registry": es_fuente,
        "product_role": PRODUCT_ROLE,
        "estado": payload.get("market_status"),
        "status_source_result": resultado.get("status"),
        "sector": declarado.get("sector"),
        "valor_m2": declarado.get("value_per_m2"),
        "banda": {"low": declarado.get("range_low"), "high": declarado.get("range_high")},
        "vigencia_ok": payload.get("vigencia_ok"),
        "vigencia_estado": payload.get("vigencia_estado"),
        "motivo": resultado.get("detail"),
        "motivo_no_resuelve": None if resuelve else resultado.get("detail"),
        "parametro_declarado": {
            "resuelve": parametro_resuelto,
            "etiqueta": _am.ETIQUETA_PARAMETROS,
            "fuente_externa_verificable": False,
            "sector": declarado.get("sector"),
            "valor_m2": declarado.get("value_per_m2"),
        },
        "datos_ausentes": payload.get("datos_ausentes") or [],
        "atributos_no_declarados_por_la_tabla":
            payload.get("atributos_no_declarados_por_la_tabla") or [],
        "entradas": entradas,
        "campo_de_resolucion": "barrio (declarado por el producto; no se resuelve con el "
                               "sector que el propio run state ya había resuelto)",
        "ruta_run_state": str(p),
        "contraste_con_run_state": contraste,
        "resultado": resultado,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 6 · CLI (regeneración de la tabla y comprobación del Golden)
# ══════════════════════════════════════════════════════════════════════════════
def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="LONJA_MARKET_BAQ (identificador histórico, NO una fuente de datos) — "
                    "tabla declarada y Golden")
    ap.add_argument("--escribir-tabla", action="store_true",
                    help="regenera docs/source_pack/lonja_market_baq_v1.json desde el producto")
    ap.add_argument("--golden", action="store_true", help="resuelve el Golden 040-646406")
    args = ap.parse_args(argv)
    if args.escribir_tabla:
        ruta = escribir_tabla()
        tabla = cargar_tabla(ruta)
        print(json.dumps({"ruta": str(ruta), "filas": len(tabla["rows"]),
                          "source_hash": tabla["hash_declarado"],
                          "hash_verificado": tabla["hash_verificado"],
                          "atributos_ausentes": tabla["atributos_ausentes"]},
                         ensure_ascii=False, indent=1))
    if args.golden:
        salida = resolver_mercado_golden()
        print(json.dumps({k: v for k, v in salida.items() if k != "resultado"},
                         ensure_ascii=False, indent=1, default=str))
    if not args.escribir_tabla and not args.golden:
        ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

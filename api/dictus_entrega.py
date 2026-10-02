# -*- coding: utf-8 -*-
"""DICTUS 2.0B-R1 — ENTREGA DEL PRODUCTO: el EJECUTIVO es el documento principal.

Qué resuelve este módulo
------------------------
2.0B produjo el `ExecutiveDocumentModel` y su renderer, pero el artefacto que el
producto **entregaba** seguía siendo el dictamen técnico legacy de 17 páginas
(`ARHIAX_Dictamen_<folio>_final.pdf`). Este módulo cierra esa brecha en un solo
punto: la corrida real del producto (`compile_pdf`, UNA vez) deja observadores de
solo lectura, y de ahí salen los DOS documentos del producto:

    DICTUS_EJECUTIVO_<folio>.pdf   ← documento PRINCIPAL que ve el usuario
    DICTUS_TECNICO_<folio>.pdf     ← ANEXO técnico (nunca al revés)

Además aplica las **aserciones duras** sobre el PDF FÍSICO ya escrito:
`page_count <= 6`, el orden exacto de las 6 páginas aprobadas, la ausencia de
encabezados legacy y de cualquier fuga técnica (p. ej. `ARHIAX_EVIDENCE_HMAC_KEY`).
Si alguna falla, la entrega NO se produce: se levanta `EntregaEjecutivaInvalida`.

Nada de esto modifica motores: identidad, valoración, POT, screening, sanciones,
HMAC, contexto de mercado, binding canónico, hallazgos, consultas POI ni la
arquitectura de hash. Solo se instrumenta la corrida y se decide qué se entrega.
"""
from __future__ import annotations

import json
import unicodedata
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import dictus_ejecutivo as de
import dictus_estado as dse
import dictus_historia as dh
import dictus_manifiesto as dm
import dictus_secciones as secciones_mod
import attribute_truth as at

MAX_PAGINAS_EJECUTIVO = 6

ARCHIVO_EJECUTIVO = "DICTUS_EJECUTIVO_{folio}.pdf"
ARCHIVO_TECNICO = "DICTUS_TECNICO_{folio}.pdf"
ARCHIVO_MANIFEST = "DICTUS_MANIFEST_{folio}.json"
ARCHIVO_RUN_STATE = "DICTUS_RUN_STATE_{folio}.json"

# Arquitectura APROBADA del documento ejecutivo (§4). El orden es el contrato:
# la página N del PDF debe contener, y solo, el título N.
TITULOS_APROBADOS = (
    "DECISIÓN DEL INMUEBLE",
    "DECISIÓN JURÍDICA",
    "DECISIÓN DE CONTRAPARTES",
    "DECISIÓN TERRITORIAL Y URBANÍSTICA",
    "ENTORNO, EQUIPAMIENTO, ASOLEAMIENTO Y SOMBRAS",
    "IDENTIDAD, MERCADO Y VALOR",
)

# Encabezados del dictamen técnico legacy (§5): si alguno aparece como capítulo en
# el ejecutivo, la entrega se considera NO APTA (se está entregando el técnico).
ENCABEZADOS_LEGACY = (
    "00 - Naturaleza de este Documento",
    "01 - Identificación del Activo",
    "02 - Localización Geográfica",
    "03 - Análisis de Equipamiento Urbano",
    "04 - Análisis Registral SNR",
    "05 - Pre-dictamen jurídico",
    "06 - Análisis Catastral y Urbanístico",
    "07 - Estimación Referencial",
    "08 - Análisis Hidrológico",
    "09 - Screening",
    "10 - Hallazgos",
    "11 - Resumen",
    "12 - Score Actuarial",
    "13 - Estructurabilidad Fiduciaria",
    "14 - Recomendaciones Operacionales",
    "15 - Ruta de Verificación",
    "16 - Declaración de Alcance",
    "17 - Sello de Integridad",
)

# Fugas técnicas prohibidas en el cuerpo ejecutivo (§8): una excepción de HMAC, una
# traza de pila o el nombre de la variable de entorno NUNCA se imprimen al usuario.
PATRONES_PROHIBIDOS = (
    "ARHIAX_EVIDENCE_HMAC_KEY",
    "RuntimeError",
    "Traceback (most recent call last)",
    "File \"",
    "api/pdf_compiler.py",
    "stack trace",
)

# Contenido mínimo exigido por página (§14). Se comprueba sobre el texto extraído.
#
# §7 (cierre semántico Fase 3) · La página 6 exigía la marca «Valor estimado», que era el
# rótulo del bloque legacy («VALOR ESTIMADO POR LA CORRIDA · VALORACIÓN NO DISPONIBLE»).
# Ese rótulo nombraba un hecho —la estimación— que DICTUS SÍ produce y lo hacía al lado
# de la ESTIMACIÓN INDICATIVA, y el cliente lo leía como «no hay estimación»: se
# RENOMBRÓ al de la compuerta que realmente cierra (`VERIFIED_MARKET_EVIDENCE_GATE`).
# La marca se sustituye por las dos que SÍ declaran el contenido material de la página en
# las DOS ramas (con cifra y sin cifra) y la aserción ENDURECE: pasa de 2 marcas
# semánticamente ambiguas a 3 marcas verificables.
CONTENIDO_MINIMO = {
    # §14 · 2.0D: la página 1 es un TABLERO DE DECISIÓN, no un resumen de datos.
    1: ("DECISIÓN DEL INMUEBLE", "hallazgo", "DECISIÓN DICTUS", "AFECTA A",
        "DISPOSICIÓN GLOBAL"),
    3: ("ONU", "OFAC SDN", "UK Sanctions List"),
    5: ("Salud", "Educación"),
    6: ("ESTIMACIÓN ECONÓMICA", "VERIFIED_MARKET_EVIDENCE_GATE", "Mercado"),
}


class EntregaEjecutivaInvalida(RuntimeError):
    """El PDF ejecutivo FÍSICO no cumple la arquitectura aprobada. No se entrega."""


# ── normalización de texto para las comprobaciones ────────────────────────────
def _norm(s: Any) -> str:
    t = unicodedata.normalize("NFC", str(s or ""))
    return " ".join(t.split())


def _norm_mayus(s: Any) -> str:
    return _norm(s).upper()


# ── captura de la corrida (observadores de solo lectura) ──────────────────────
def iniciar_captura() -> Dict[str, Any]:
    """Instrumenta la corrida del producto. Debe llamarse ANTES de `compile_pdf`."""
    captura: Dict[str, Any] = {}
    return dse.instalar_observadores(captura)


def _fecha_corrida(rs: Dict[str, Any]) -> Optional[str]:
    """Fecha de referencia de la corrida (la que el propio estado declara)."""
    return str((rs or {}).get("generated_at") or "")[:10] or None


def historial_del_caso(folio: str, raiz: Optional[Path] = None) -> Dict[str, Any]:
    """Informe de coherencia histórica versionado del folio, si existe.

    Es un INSUMO de la corrida (evidencia de primer orden), no algo que el ejecutivo
    averigüe por su cuenta. Si el folio no tiene expediente histórico auditado se
    devuelve `{}` y el documento declara «sin expediente histórico comparado» — nunca
    «sin cambios», que sería afirmar algo no verificado.
    """
    folio = str(folio or "").strip()
    if not folio or folio.lower() in ("pendiente", "sin-folio"):
        return {}
    base = Path(raiz) if raiz else Path(__file__).resolve().parent.parent
    candidatos = [
        base / "docs" / "forensics" / folio / "dictus_2"
        / "HISTORICAL_CONSISTENCY_REPORT.json",
        base / "docs" / "forensics" / folio / "HISTORICAL_CONSISTENCY_REPORT.json",
    ]
    for ruta in candidatos:
        try:
            if ruta.exists():
                return json.loads(ruta.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 — un informe ilegible no rompe la corrida
            continue
    return {}


# ── construcción de los dos documentos desde el estado canónico ───────────────
def construir_entregables(
    captura: Dict[str, Any], *,
    folio: str,
    ciudad: str,
    tecnico: Path,
    salida_dir: Path,
    area: Any = None,
    tipo_unidad: Optional[str] = None,
    historial: Optional[Dict[str, Any]] = None,
    run_id: Optional[str] = None,
    versionado: Optional[Dict[str, Any]] = None,
    generated_at: Optional[str] = None,
    publicar_manifest: Optional[Path] = None,
) -> Dict[str, Any]:
    """Genera el Ejecutivo (principal) y publica el manifest de la MISMA corrida.

    `captura` es lo que dejaron los observadores durante `compile_pdf`. No se
    recalcula nada: el estado canónico se construye con lo ya producido.
    """
    captura = captura or {}
    # El asoleamiento ya lo calculó el compilador durante ESTA corrida; se expone al
    # estado sin recalcular nada. Si la corrida no produjo momentos (o el llamador ya
    # los aportó, p. ej. en una prueba), se respeta lo que haya.
    _momentos = (getattr(dse, "_SOLAR", {}).get("momentos")
                 or (captura.get("solar") or {}).get("momentos") or [])
    captura["solar"] = {"momentos": list(_momentos)}
    if not run_id:
        run_id = str(uuid.uuid4())

    salida_dir = Path(salida_dir)
    salida_dir.mkdir(parents=True, exist_ok=True)
    folio_txt = str(folio or "SIN-FOLIO")
    hist = historial if historial is not None else historial_del_caso(folio_txt)

    rs = dse.construir_run_state(captura, run_id=run_id, folio=folio_txt, ciudad=ciudad,
                                 versionado=dict(versionado or {}),
                                 generated_at=(generated_at
                                               or (captura.get("receipts") or {}).get("generated_at")),
                                 area=area, tipo_unidad=tipo_unidad)
    # ── BLOCK 1 · VERDAD ÚNICA POR ATRIBUTO ──────────────────────────────────
    # 1. El informe de coherencia se recalcula con las SIETE condiciones cuando la matriz
    #    histórica del folio está disponible (el archivo del expediente NO se reescribe):
    #    el recuento de conflictos abiertos se deriva SOLO de TRUE_CONFLICT.
    # 2. Se resuelve la escalera por atributo y se PERSISTE el mínimo auditable
    #    (`source_attempts`, `source_selected`, `source_authority`, `source_vigency`,
    #    `acquisition_mode`, `resolution_status`, `fact_status`, `canonical_value`,
    #    `canonical_reason`, `evidence_id`, `content_hash`, `queried_at`).
    # 3. La verdad única se aplica al estado: ningún valor queda declarado «verificado»
    #    sin fuente seleccionada.
    matriz = dh.cargar_matriz_del_caso(folio_txt)
    hist = dh.reclasificar_informe(hist, matriz)
    rs["historical_consistency"] = hist
    registro_atributos = at.resolver_atributos(rs, historial=hist, fecha=_fecha_corrida(rs))
    at.aplicar_verdad_al_estado(rs, registro_atributos)
    at.assert_single_truth_per_attribute(registro_atributos)
    at.assert_reglas_duras(registro_atributos)
    rs[at.CLAVE_RUN_STATE] = registro_atributos
    dse.agregar_findings_de_coherencia(rs, hist)
    # ── BLOCK 1.1 · B — UNA SOLA VERDAD CANÓNICA DEL RECUENTO ────────────────
    # El recuento se resuelve UNA vez aquí, con la única función canónica, y se
    # PERSISTE en el RunState. El modelo de documento y el manifest reciben ESE MISMO
    # objeto (no vuelven a contar), y el PDF imprime el valor ya resuelto. Así
    # `runstate_count == manifest_count == model_count == pdf_count` no depende de que
    # cuatro sitios coincidan: dependen de que solo uno calcule.
    resumen_conflictos = dh.get_true_conflict_summary(hist)
    rs["historical_consistency_summary"] = resumen_conflictos
    modelo = dm.construir_documento_maestro(rs, historial=hist, folio=folio_txt,
                                            resumen_conflictos=resumen_conflictos)

    secciones = secciones_mod.desde_estado(rs, modelo, hist)
    ejecutivo = salida_dir / ARCHIVO_EJECUTIVO.format(folio=folio_txt)
    de.render(modelo, secciones, ejecutivo)

    # ── ASERCIÓN DURA sobre el PDF FÍSICO (§3, §4, §5, §8) ────────────────────
    auditoria = auditar_ejecutivo(ejecutivo)

    # §7/§10 del hotfix 2.0D-R1 · el presupuesto vertical REAL de la corrida queda en el
    # manifest del producto (no es bloque canónico: no altera el hash maestro).
    presupuesto = {str(p): de.page_budget(p) for p in range(1, MAX_PAGINAS_EJECUTIVO + 1)}
    modelo["render_budget"] = presupuesto

    # (B) HECHOS IMPRESOS CON SU ORIGEN. El manifest del producto registra QUÉ hecho se
    # imprimió, con qué ESTADO y con qué ORIGEN declarado (vocabulario cerrado de
    # `atribucion_mercado`) más su procedencia. Sin este registro, auditar si un hecho
    # VERIFICADO tiene un origen prohibido obligaría a re-derivar las secciones desde el
    # código: aquí se lee el artefacto que la corrida produjo. Es el mismo criterio que
    # `render_budget`: se añade DESPUÉS del hash maestro (no es bloque canónico), porque
    # describe el render, no el estado.
    manifiesto_hechos = secciones.get("identidad") or {}
    modelo["hechos_impresos"] = {
        "identidad": {
            "origen": manifiesto_hechos.get("origen"),
            "filas": [
                {"etiqueta": f.get("etiqueta"), "valor": f.get("valor"),
                 "estado": f.get("estado"),
                 "origin": (f.get("origin") or {}).get("origin"),
                 "origin_declarado": (f.get("origin") or {}).get("origin_declarado"),
                 "origin_gate": (f.get("origin") or {}).get("origin_gate"),
                 "origin_etiqueta": (f.get("origin") or {}).get("origin_etiqueta"),
                 "origin_blockers": (f.get("origin") or {}).get("origin_blockers"),
                 "origin_provenance": (f.get("origin") or {}).get("origin_provenance")}
                for f in (manifiesto_hechos.get("filas") or [])],
        },
        "geometria": {
            "atributo": manifiesto_hechos.get("geometria_atributo"),
            "etiqueta": manifiesto_hechos.get("geometria_etiqueta"),
            "estado": manifiesto_hechos.get("geometria_estado"),
        },
        "nota": ("`origin` es el origen EFECTIVO (nunca una clase habilitante sin "
                 "procedencia); `origin_declarado` es lo que declaró la corrida, para que "
                 "la degradación sea visible."),
    }

    manifest = {
        "master_manifest_version": dm.MASTER_MANIFEST_VERSION,
        "run_state_version": dse.RUN_STATE_VERSION,
        "run_id": run_id,
        "dictus_id": modelo["document_identity"]["dictus_id"],
        "generated_at": modelo["document_identity"]["generated_at"],
        "folio": folio_txt,
        "master_hash": modelo["master_hash"],
        "master_hash_abreviado": modelo["master_hash_abreviado"],
        "evidence_manifest": modelo["evidence_manifest"],
        "ejecutivo_paginas": auditoria["page_count"],
        "ejecutivo_titulos": auditoria["titulos"],
        "render_budget": presupuesto,
        "modelo": modelo,
        # BLOCK 1.1 · B — PROYECCIÓN del resumen canónico en el MANIFEST. No es un
        # segundo cálculo: es el MISMO objeto que el RunState persistió y que el modelo
        # de documento transporta, expuesto también en la raíz del manifest para que un
        # revisor lo lea sin abrir el modelo. El manifest NO replica el informe de
        # coherencia completo (`requieren_revision`, `clasificaciones_conflicto`): su
        # contrato es `modelo.historical_consistency` + este resumen.
        "historical_consistency_summary": modelo["historical_consistency_summary"],
    }
    mpath = salida_dir / ARCHIVO_MANIFEST.format(folio=folio_txt)
    mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    (salida_dir / ARCHIVO_RUN_STATE.format(folio=folio_txt)).write_text(
        json.dumps(rs, ensure_ascii=False, indent=1, default=str), encoding="utf-8")

    if publicar_manifest is not None:
        destino = Path(publicar_manifest)
        destino.mkdir(parents=True, exist_ok=True)
        (destino / mpath.name).write_bytes(mpath.read_bytes())

    tecnico = Path(tecnico)
    return {
        "run_id": run_id,
        "folio": folio_txt,
        "ejecutivo": ejecutivo,
        "tecnico": tecnico if tecnico.exists() else None,
        "manifest_path": mpath,
        "manifest": manifest,
        "run_state": rs,
        "modelo": modelo,
        "secciones": secciones,
        "auditoria": auditoria,
    }


# ── aserciones duras sobre el PDF entregado ──────────────────────────────────
def _paginas_texto(ruta: Path) -> List[str]:
    """Texto REAL del PDF, página por página (pypdf: la misma librería que lo lee el
    revisor). No hay caché ni texto de cortesía: se lee el archivo físico."""
    from pypdf import PdfReader
    lector = PdfReader(str(ruta))
    return [pag.extract_text() or "" for pag in lector.pages]


def auditar_ejecutivo(ruta: Path) -> Dict[str, Any]:
    """Lee el PDF escrito y aplica el contrato. Levanta si algo no se cumple."""
    ruta = Path(ruta)
    if not ruta.exists():
        raise EntregaEjecutivaInvalida(f"No existe el PDF ejecutivo: {ruta}")
    paginas = _paginas_texto(ruta)
    texto_completo = _norm("\n".join(paginas))
    mayus = _norm_mayus(texto_completo)
    fallos: List[str] = []

    # §3 — límite duro de páginas.
    if len(paginas) > MAX_PAGINAS_EJECUTIVO:
        fallos.append(f"page_count={len(paginas)} > {MAX_PAGINAS_EJECUTIVO}")

    # §4 — orden exacto: la página N contiene el título N (y ninguno anterior).
    titulos: List[str] = []
    for i, esperado in enumerate(TITULOS_APROBADOS, start=1):
        if i > len(paginas):
            fallos.append(f"falta la página {i} ({esperado})")
            titulos.append(None)
            continue
        pagina = _norm_mayus(paginas[i - 1])
        if _norm_mayus(esperado) not in pagina:
            fallos.append(f"la página {i} no dice «{esperado}»")
            titulos.append(None)
        else:
            titulos.append(esperado)
    for i, t in enumerate(TITULOS_APROBADOS, start=1):
        for j, u in enumerate(TITULOS_APROBADOS, start=1):
            if i != j and _norm_mayus(u) in _norm_mayus(paginas[i - 1] if i <= len(paginas) else ""):
                fallos.append(f"la página {i} contiene el título de la página {j}")

    # §5 — ningún encabezado legacy puede aparecer como capítulo.
    for enc in ENCABEZADOS_LEGACY:
        if _norm_mayus(enc) in mayus:
            fallos.append(f"encabezado legacy presente: «{enc}»")

    # §8 — sin fugas técnicas.
    for pat in PATRONES_PROHIBIDOS:
        if _norm_mayus(pat) in mayus:
            fallos.append(f"fuga técnica presente: «{pat}»")

    # §14 — contenido mínimo por página.
    for idx, marcas in CONTENIDO_MINIMO.items():
        pagina = _norm(paginas[idx - 1] if idx <= len(paginas) else "")
        pagina_mayus = _norm_mayus(pagina)
        for marca in marcas:
            if _norm(marca) not in pagina and _norm_mayus(marca) not in pagina_mayus:
                fallos.append(f"la página {idx} no contiene «{marca}»")

    # Retícula: si el renderer declaró desbordes, el documento no está apto aunque
    # tenga 6 páginas (el contenido se solaparía).
    for v in list(de.VIOLACIONES):
        fallos.append(f"retícula: {v}")

    resultado = {
        "archivo": str(ruta),
        "page_count": len(paginas),
        "titulos": titulos,
        "orden_ok": all(t is not None for t in titulos),
        "fallos": fallos,
        "ok": not fallos,
    }
    if fallos:
        raise EntregaEjecutivaInvalida(
            "El PDF ejecutivo no cumple la arquitectura aprobada: " + "; ".join(fallos))
    return resultado


def verificar_entrega(manifest: Dict[str, Any]) -> Dict[str, Any]:
    """Verifica el hash maestro del manifest entregado (contrato de VERIFY)."""
    return dse.verify_dictus_master_hash(manifest, str(manifest.get("master_hash") or ""))

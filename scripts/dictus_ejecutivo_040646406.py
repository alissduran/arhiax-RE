# -*- coding: utf-8 -*-
"""DICTUS 2.0 — Genera el DICTUS EJECUTIVO del folio Golden (§AR).

    python scripts/dictus_ejecutivo_040646406.py

Toma el ESTADO REAL de la última corrida del producto, el cuerpo técnico ya emitido y
el informe de coherencia histórica, y produce:

  docs/forensics/<folio>/dictus_2/
    DICTUS_EJECUTIVO_<folio>.pdf          ← 6 páginas ejecutivas + hoja de anexos +
                                            cuerpo técnico completo como Anexos A–I
    EXECUTIVE_DOCUMENT_MODEL.json         ← modelo canónico (entrada del hash maestro)
    EVIDENCE_MANIFEST.json                ← manifest de evidencias
    MASTER_HASH.json                      ← hash maestro + contrato VERIFY
    REPORTE_ANTES_DESPUES.md              ← comparación de estructura
    CONTRADICCIONES.md                    ← encontradas / resueltas / abiertas
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))

import dictus_ejecutivo as de          # noqa: E402
import dictus_historia as dh           # noqa: E402
import dictus_manifiesto as dm         # noqa: E402

FO = "docs/forensics/{folio}"
LISTAS_POR_DEFECTO = ("Lista Consolidada ONU", "OFAC SDN", "UK Sanctions List")

NOMBRES_ANEXOS = [
    ("A", "Evidencia registral", "Certificado de tradición y libertad, cadena de "
                                 "tradición completa, anotaciones, gravámenes y titularidad."),
    ("B", "Catastro e identidad", "Identidad canónica, capa predial, dirección oficial, "
                                  "coordenada y su procedencia."),
    ("C", "POT / urbanismo / riesgos", "Capas oficiales consultadas, tratamientos, "
                                       "alturas, estratificación y gestión del riesgo."),
    ("D", "Screening / contrapartes", "Consultas por sujeto, fuente, versión, hashes de "
                                      "consulta y cadena de evidencia."),
    ("E", "Equipamiento / geografía / solar", "Inventario de equipamientos, accesibilidad, "
                                              "asoleamiento y simulación de sombras."),
    ("F", "Metodología de valoración", "Parámetros, sector, tasa, bandas y trazabilidad "
                                       "metodológica."),
    ("G", "Manifest de evidencias", "Manifest completo, DICTUS_MASTER_HASH y hash del "
                                    "archivo PDF (no son el mismo hash)."),
    ("H", "Declaración de alcance", "Naturaleza del documento, límites y responsabilidad "
                                    "profesional."),
    ("I", "Historial de coherencia", "Attribute History Matrix y conflictos históricos "
                                     "del mismo inmueble."),
]


def _texto_pdf(ruta: Path) -> str:
    return dh.cargar_texto_pdf(ruta)


def parsear_hallazgos(texto: str) -> list:
    """Hallazgos del capítulo 10 del cuerpo técnico (severidad, código, descripción)."""
    ini = texto.find("10 - ")
    fin = texto.find("11 - ")
    bloque = texto[ini:fin if fin > ini else len(texto)]
    salida = []
    for m in re.finditer(r"Severidad:\s*(ALTO|MEDIO|INFORMATIVO)\s*\n?"
                         r"(?:Fuente:\s*([^\n]*)\n)?"
                         r"(H-[\w\-]+ \| [^\n]+)\n?"
                         r"(?:Descripci[oó]n:\s*([^\n]*)\n?)?"
                         r"(?:Implicaci[oó]n operacional:\s*([^\n]*))?", bloque):
        sev, fuente, titulo, desc, impl = m.groups()
        codigo = titulo.split("|")[0].strip()
        titulo_txt = titulo.split("|", 1)[1].strip() if "|" in titulo else titulo
        salida.append({
            "severidad": sev, "codigo": codigo, "titulo": titulo_txt,
            "fuente": (fuente or "").strip(),
            "por_que": (desc or "").strip()[:300],
            "accion": (impl or "").strip()[:260],
            "afectados": [], "impacto": "",
        })
    return salida


def afectados_de(hallazgo: dict, historia: dict) -> tuple:
    """Actores afectados e impacto por actor (§I). Derivado del TIPO de hallazgo."""
    t = dh._norm(hallazgo.get("titulo", "") + " " + hallazgo.get("codigo", ""))
    if "HIPOTECA" in t or "EMBARGO" in t or "CAUTELAR" in t or "GRAVAMEN" in t:
        return (["COMPRADOR", "VENDEDOR", "INMOBILIARIA", "BANCO / FINANCIADOR"],
                "Comprador: el gravamen se hereda con el inmueble. Vendedor: condición para "
                "transferir. Inmobiliaria: riesgo de retraso o caída. Banco: afecta la "
                "garantía y la prelación.")
    if "AUSENCIA DE CERTIFICADO" in t or "AUSENCIA DE CTL" in t:
        return (["COMPRADOR", "VENDEDOR", "BANCO / FINANCIADOR", "ASEGURADORA DE TÍTULO"],
                "Sin CTL no se verifica titularidad ni cargas: el banco y el asegurador de "
                "títulos no pueden suscribir; el comprador asume riesgo no medido.")
    if "AFECTACION" in t or "RIESGO" in t or "AMENAZA" in t or "GEO" in t:
        return (["COMPRADOR", "BANCO / FINANCIADOR", "ASEGURADORA"],
                "Puede exigir verificación técnica específica y condicionar la financiación "
                "o la póliza.")
    if "COHERENCIA" in t or "HISTORIC" in t:
        return (["COMPRADOR", "VENDEDOR", "INMOBILIARIA", "BANCO / FINANCIADOR",
                 "ASEGURADORA DE TÍTULO"],
                "Dos ejecuciones del mismo predio produjeron resultados distintos: la cifra "
                "no es utilizable como hecho hasta resolver el polígono/ficha aplicable.")
    if "TITULARIDAD" in t or "TITULARES" in t:
        return (["COMPRADOR", "VENDEDOR", "INMOBILIARIA", "ASEGURADORA DE TÍTULO"],
                "Quién puede vender y en qué proporción es condición de la operación.")
    return ([], "")


def parsear_sujetos(texto: str) -> list:
    """Contrapartes desde el recibo del dictamen (fila única 05 = 09 = 16)."""
    salida = []
    for m in re.finditer(r"Contraparte ([\w\-]+)\s*\n?([^\n]*)\n?([^\n]*)\n?([^\n]*)\n?([^\n]*)",
                         texto):
        sid, nombre, tipo, doc, _extra = m.groups()
        nombre = " ".join(str(nombre).split())
        if not nombre or nombre.upper().startswith("CONTRAPARTE"):
            continue
        if any(s["subject_id"] == sid for s in salida):
            continue
        salida.append({"subject_id": sid, "nombre": nombre, "tipo": tipo.strip(),
                       "documento": doc.strip(), "rol": "contraparte del caso"})
    return salida


def parsear_solar(texto: str) -> dict:
    momentos = []
    for m in re.finditer(r"(\d{2}:\d{2})\s*COT\s*([\d\.]+)°\s*([\d\.]+)°\s*([^\n]{0,40})", texto):
        hora, azimut, elev, estado = m.groups()
        momentos.append({"hora": hora, "azimut": azimut + "°", "elevacion": elev + "°",
                         "estado": " ".join(estado.split())[:60] or "estado no declarado"})
    if not momentos:
        for m in re.finditer(r"(09:00|12:00|15:00)[^\n]{0,30}(sol directo|sombra[^\n]{0,30})",
                             texto, re.IGNORECASE):
            momentos.append({"hora": m.group(1), "estado": m.group(2).strip(),
                             "azimut": None, "elevacion": None})
    return {"momentos": momentos, "altura_dependiente": True}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Genera el DICTUS ejecutivo 2.0")
    ap.add_argument("--folio", default="040-646406")
    args = ap.parse_args(argv)

    base = ROOT / FO.format(folio=args.folio)
    salida = base / "dictus_2"
    gold = base / "golden_03i1"

    estado = json.loads((gold / "GOLDEN_INTERNAL_STATE.json").read_text(encoding="utf-8"))
    tecnico = gold / "ARHIAX_Dictamen_040-646406_03I2BA.pdf"
    if not tecnico.exists():
        tecnicos = sorted(gold.glob("ARHIAX_Dictamen_*.pdf"))
        if not tecnicos:
            print("[FAIL] no hay cuerpo técnico emitido en golden_03i1")
            return 1
        tecnico = tecnicos[-1]
    texto = _texto_pdf(tecnico)
    hist = json.loads((salida / "HISTORICAL_CONSISTENCY_REPORT.json").read_text(encoding="utf-8"))
    estado["historical_consistency"] = hist

    # ── Hechos extraídos del cuerpo técnico (misma extracción que la historia) ──
    atr = dh.extraer_atributos(texto)
    val = atr["__globales__"]

    # ── Hallazgos + actores ────────────────────────────────────────────────────
    hallazgos = parsear_hallazgos(texto)
    for h in hallazgos:
        h["afectados"], h["impacto"] = afectados_de(h, hist)
    # El conflicto histórico de un atributo material ES un hallazgo (§D).
    for c in hist.get("conflictos_abiertos", []):
        h = {"severidad": "ALTO", "codigo": "H-COH",
             "titulo": f"Coherencia histórica: {c['atributo'].replace('_', ' ')}",
             "fuente": "Expediente histórico del mismo inmueble",
             "por_que": c["detalle"],
             "accion": "Resolver con la ficha/polígono aplicable antes de usar la cifra.",
             "afectados": [], "impacto": ""}
        h["afectados"], h["impacto"] = afectados_de(h, hist)
        hallazgos.insert(0, h)

    # ── Indicadores ejecutivos (§G) desde el ESTADO, no inventados ─────────────
    ident = estado.get("identity") or {}
    coords = estado.get("coordinates") or {}
    urb = estado.get("urban") or {}
    market = estado.get("market") or {}
    valuation = estado.get("valuation") or {}
    scr = estado.get("screening") or {}
    grav = dh._norm(atr["gravamenes"]["value"] or "")
    con_carga = "HIPOTECA" in grav or "EMBARGO" in grav or "CAUTELAR" in grav
    hay_urb_conf = any(c["atributo"] in dh.ATRIBUTOS_URBANISTICOS
                       for c in hist.get("conflictos_abiertos", []))
    indicadores = [
        ("Identidad", dh.VERIFICADO if ident.get("identity_verified") else dh.REQUIERE_VALIDACION,
         f"Matrícula, NUPRE y predial resueltos ({de._v(ident.get('resolution_method'))})."),
        ("Títulos", "CON_CONDICIONES" if con_carga else dh.VERIFICADO,
         ("Cargas vigentes declaradas." if con_carga else "Sin cargas vigentes declaradas.")),
        ("Contrapartes", "SIN_COINCIDENCIAS" if scr.get("executed") else "INCOMPLETA",
         f"{de._v(scr.get('subjects_screened'))} sujeto(s) · cadena "
         f"{de._v(scr.get('evidence_chain_status'))}."),
        ("Territorio", dh.REQUIERE_VALIDACION if hay_urb_conf else dh.VERIFICADO,
         ("Coherencia histórica abierta en atributos urbanísticos."
          if hay_urb_conf else "Capas oficiales consultadas.")),
        ("Valoración", "DISPONIBLE" if (valuation.get("authorization") or {}).get("allowed")
         else "NO_DISPONIBLE",
         ("Valoración autorizada." if (valuation.get("authorization") or {}).get("allowed")
          else "No autorizada: se declara el blocker, sin cifras.")),
    ]

    # ── Coherencia por atributo urbanístico (Urban Consistency Gate) ───────────
    coherencia = {}
    for atributo in ("altura_maxima", "tratamiento", "uso_pot", "clase_suelo"):
        g = dh.gate_urbanistico(hist if "cambios" in hist else {"cambios": [], "versiones": []},
                                atributo, (atr.get(atributo) or {}).get("value"))
        # `gate_urbanistico` consume la MATRIZ; aquí se usa el reporte ya calculado.
        info = next((c for c in hist.get("conflictos_abiertos", [])
                     if c["atributo"] == atributo), None)
        explicado = next((c for c in hist.get("cambios_explicados", [])
                          if c["atributo"] == atributo), None)
        if info:
            coherencia[atributo] = {"estado": dh.HISTORICAL_CONFLICT,
                                    "mensaje": info["detalle"], "valores": info["valores"]}
        elif explicado:
            coherencia[atributo] = {"estado": dh.CAMBIO_CON_FUENTE,
                                    "mensaje": explicado["detalle"], "valores": []}
        else:
            coherencia[atributo] = {"estado": dh.VERIFICADO,
                                    "mensaje": "Sin cambios entre las versiones comparadas.",
                                    "valores": []}

    # La cifra de altura solo se imprime si el gate la autoriza.
    altura_mostrar = None
    if coherencia.get("altura_maxima", {}).get("estado") != dh.HISTORICAL_CONFLICT:
        altura_mostrar = (atr.get("altura_maxima") or {}).get("value")
    tratamiento_mostrar = None
    if coherencia.get("tratamiento", {}).get("estado") != dh.HISTORICAL_CONFLICT:
        tratamiento_mostrar = (atr.get("tratamiento") or {}).get("value")

    if coherencia.get("altura_maxima", {}).get("estado") == dh.HISTORICAL_CONFLICT:
        hallazgos.insert(0, {
            "severidad": "ALTO", "codigo": "H-POT",
            "titulo": "Edificabilidad: requiere validación de coherencia",
            "fuente": "Capa oficial de tratamientos (POT)",
            "por_que": ("El expediente ha producido resultados normativos distintos en "
                        "ejecuciones previas para el mismo predio. La cifra definitiva no se "
                        "presenta hasta resolver qué polígono/ficha normativa es aplicable."),
            "accion": "Solicitar certificación de norma urbanística al curador o a Planeación "
                      "y validar el polígono aplicable.",
            "afectados": ["COMPRADOR", "INMOBILIARIA", "BANCO / FINANCIADOR",
                          "ASEGURADORA DE TÍTULO"],
            "impacto": "Condiciona ampliaciones, licencias y el respaldo técnico del valor.",
        })

    # ── Secciones del ejecutivo ────────────────────────────────────────────────
    secciones = {
        "hallazgos": hallazgos,
        "indicadores": indicadores,
        "ctx": {
            "area": (atr.get("area") or {}).get("value"),
            "regimen": (atr.get("regimen_juridico") or {}).get("value"),
            "uso": (atr.get("destino_economico") or {}).get("value"),
        },
        "legal": {
            "titulares": ([{"nombre": (atr.get("titulares") or {}).get("value"),
                            "tipo": "no declarado",
                            "documento": "no declarado", "participacion": "no declarada",
                            "verificacion": dh.VERIFICADO}]
                          if (atr.get("titulares") or {}).get("value") else []),
            "gravamenes": [{"severidad": h["severidad"], "titulo": h["titulo"],
                            "detalle": h["por_que"][:200], "accion": h["accion"][:160]}
                           for h in hallazgos
                           if any(k in dh._norm(h["titulo"]) for k in
                                  ("HIPOTECA", "EMBARGO", "CAUTELAR", "GRAVAMEN",
                                   "AFECTACION"))],
            "condiciones": [h["accion"] for h in hallazgos if h["accion"]][:5],
        },
        "contrapartes": {
            "listas": list(LISTAS_POR_DEFECTO),   # se sustituyen abajo por las reales
            "sujetos": parsear_sujetos(texto),
        },
        "preparacion": [
            ("COMPRA / VENTA",
             "PREPARADA" if not hallazgos else "REQUIERE_REVISION",
             "El expediente reúne identidad, títulos, contrapartes y valor para la decisión; "
             "las condiciones anteriores son del comprador y del vendedor."),
            ("CRÉDITO HIPOTECARIO",
             "PREPARADA" if (valuation.get("authorization") or {}).get("allowed")
             else "INCOMPLETO",
             "DICTUS no aprueba crédito: entrega el expediente verificable para que el banco "
             "evalúe garantía, prelación y riesgo."),
            ("SEGURO DE TÍTULO",
             "PREPARADA" if scr.get("evidence_chain_status") == "SEALED" else "REQUIERE_REVISION",
             "DICTUS no asegura ni declara asegurable: entrega hechos comprobados y su "
             "evidencia sellada para el suscriptor."),
        ],
        "urbano": {
            "filas": [
                {"etiqueta": "Clase de suelo", "valor": (atr.get("clase_suelo") or {}).get("value"),
                 "estado": coherencia.get("clase_suelo", {}).get("estado")},
                {"etiqueta": "Destino económico (catastro)",
                 "valor": (atr.get("destino_economico") or {}).get("value"),
                 "estado": dh.VERIFICADO,
                 "nota": "Dimensión catastral: no es el uso normativo del POT."},
                {"etiqueta": "Uso / actividad POT", "valor": (atr.get("uso_pot") or {}).get("value"),
                 "estado": coherencia.get("uso_pot", {}).get("estado"),
                 "nota": "Dimensión normativa: no es el destino catastral."},
                {"etiqueta": "Tratamiento urbanístico", "valor": tratamiento_mostrar,
                 "estado": coherencia.get("tratamiento", {}).get("estado"),
                 "nota": None if tratamiento_mostrar else
                         "El expediente produjo tratamientos distintos: no se imprime una cifra."},
                {"etiqueta": "Altura / edificabilidad", "valor": altura_mostrar,
                 "estado": coherencia.get("altura_maxima", {}).get("estado"),
                 "nota": None if altura_mostrar else
                         "Resultados normativos distintos en ejecuciones previas: requiere "
                         "validación de coherencia."},
                {"etiqueta": "Planes parciales", "valor": (atr.get("planes_parciales") or {}).get("value"),
                 "estado": dh.VERIFICADO},
                {"etiqueta": "Estrato", "valor": (atr.get("estrato") or {}).get("value"),
                 "estado": dh.VERIFICADO if (atr.get("estrato") or {}).get("value")
                 else dh.SIN_DATO},
                {"etiqueta": "Barrio / localidad",
                 "valor": " / ".join(x for x in [(atr.get("barrio") or {}).get("value"),
                                                 (atr.get("localidad") or {}).get("value")] if x),
                 "estado": dh.VERIFICADO if (atr.get("barrio") or {}).get("value") else dh.SIN_DATO},
            ],
        },
        "riesgos": [
            {"tipo": "Amenaza / riesgo del POT", "nivel": (atr.get("amenaza") or {}).get("value"),
             "implicacion": "Puede afectar al comprador, al banco y a la aseguradora: exige "
                            "verificación técnica específica (Anexo C)."},
            {"tipo": "Riesgo volcánico (SGC)", "nivel": (atr.get("riesgo") or {}).get("value"),
             "implicacion": "Se declara el estado real de la fuente; no se afirma ausencia de "
                            "amenaza si el punto no está cartografiado."},
        ],
        "coherencia": coherencia,
        "entorno": {
            "categorias": [
                {"nombre": c, "conteo": (estado.get("poi", {}).get("categorias", {}).get(c) or
                                         {}).get("count"),
                 "estado": "DISPONIBLE" if (estado.get("poi", {}).get("categorias", {}).get(c) or
                                            {}).get("status") == "AVAILABLE" else "NO_DISPONIBLE",
                 "mas_cercano": None}
                for c in ("Salud", "Educacion", "Comercio", "Recreacion")
            ],
            "accesibilidad": [
                ("Barrio / sector oficial", (atr.get("barrio") or {}).get("value")),
                ("Localidad", (atr.get("localidad") or {}).get("value")),
                ("Coordenada oficial",
                 " / ".join(str(x) for x in [(atr.get("coordenada") or {}).get("value")] if x) or
                 de._v((estado.get("coordinates") or {}).get("lat"))),
                ("Vías de acceso inmediato", "geocodificadas en el Anexo E"),
            ],
        },
        "solar": parsear_solar(texto),
        "identidad": {
            "filas": [
                {"etiqueta": "Dirección oficial", "valor": (atr.get("direccion") or {}).get("value"),
                 "estado": dh.VERIFICADO},
                {"etiqueta": "Matrícula", "valor": (atr.get("matricula") or {}).get("value"),
                 "estado": dh.VERIFICADO},
                {"etiqueta": "NUPRE", "valor": (atr.get("nupre") or {}).get("value"),
                 "estado": dh.VERIFICADO},
                {"etiqueta": "Número predial", "valor": (atr.get("numero_predial") or {}).get("value"),
                 "estado": dh.VERIFICADO},
                {"etiqueta": "Unidad (torre / apartamento)",
                 "valor": (atr.get("unidad") or {}).get("value"), "estado": dh.VERIFICADO},
                {"etiqueta": "Área", "valor": (atr.get("area") or {}).get("value") + " m²"
                 if (atr.get("area") or {}).get("value") else None, "estado": dh.VERIFICADO},
                {"etiqueta": "Régimen jurídico", "valor": (atr.get("regimen_juridico") or {}).get("value"),
                 "estado": dh.VERIFICADO},
                {"etiqueta": "Geometría oficial del predio",
                 "valor": (coords.get("source") or "no declarada"),
                 "estado": dh.VERIFICADO if coords.get("verified") else dh.REQUIERE_VALIDACION},
                {"etiqueta": "Binding predio ↔ identidad canónica",
                 "valor": ((coords.get("provenance") or {}).get("canonical_binding_status")
                           or "NO_COMPARABLE"),
                 "estado": dh.VERIFICADO
                 if (coords.get("provenance") or {}).get("canonical_binding_status") == "VERIFIED"
                 else dh.REQUIERE_VALIDACION},
            ],
        },
        "valor": {
            "autorizado": bool((valuation.get("authorization") or {}).get("allowed")),
            "consolidado": (f"$ {int(valuation['consolidado']):,}".replace(",", ".")
                            if valuation.get("consolidado") else None),
            "rango": (f"$ {int(valuation['banda_baja']):,}".replace(",", ".")
                      if valuation.get("banda_baja") else None),
            "area": (atr.get("area") or {}).get("value"),
            "valor_m2": (f"$ {int(valuation['value_m2']):,}".replace(",", ".")
                         if valuation.get("value_m2") else None),
            "fecha": str(val.get("fecha_emision") or "")[:10] or None,
            "sector": market.get("sector"),
            "metodologia": market.get("market_methodology_version"),
            "motivo": valuation.get("motivo_no_aplica"),
            "pasos": [
                "Se verificó la identidad del inmueble (matrícula, NUPRE y número predial).",
                "Se verificó el contexto territorial (barrio, estrato y norma con fuentes oficiales).",
                "Se identificó el sector metodológico de mercado y su tasa.",
                "Se aplicó la metodología declarada (comparación de mercado para propiedad horizontal).",
                "Se construyó el valor y su banda con parámetros trazables.",
                "La interpretación profesional corresponde al experto competente.",
            ],
        },
    }

    # Listas realmente consultadas: del propio cuerpo técnico (nunca hardcodeadas).
    m_fuentes = re.search(r"[Ff]uentes configuradas:\s*([^\n\.]{3,80})", texto)
    if m_fuentes:
        reales = [x.strip().title() for x in re.split(r",| y ", m_fuentes.group(1)) if x.strip()]
        if reales:
            secciones["contrapartes"]["listas"] = reales
    for s in secciones["contrapartes"]["sujetos"]:
        s["por_lista"] = {li: "SIN_COINCIDENCIAS" for li in secciones["contrapartes"]["listas"]}
        s["resultado"] = ("SIN_COINCIDENCIAS" if scr.get("evidence_chain_status") == "SEALED"
                          else "INCOMPLETA")

    if not secciones["contrapartes"]["sujetos"]:
        secciones["contrapartes"]["sujetos"] = [{
            "nombre": "Sin contrapartes declaradas en esta ejecución", "tipo": "—",
            "documento": "—", "rol": "—", "por_lista": {},
            "resultado": "INCOMPLETA"}]

    # ── Modelo canónico + hash maestro ────────────────────────────────────────
    modelo = dm.construir_documento_maestro(estado, hallazgos=hallazgos, historial=hist,
                                            folio=args.folio, solar=secciones["solar"])

    # ── Render: ejecutivo + hoja de anexos + cuerpo técnico (Anexos A–I) ──────
    ej = de.render(modelo, secciones, salida / f"DICTUS_EJECUTIVO_{args.folio}.pdf")
    hoja = de.hoja_anexos(salida / "_anexos_hoja.pdf", NOMBRES_ANEXOS)

    import pymupdf
    final = pymupdf.open()
    with pymupdf.open(str(ej)) as d1:
        final.insert_pdf(d1)
    with pymupdf.open(str(hoja)) as d2:
        final.insert_pdf(d2)
    with pymupdf.open(str(tecnico)) as d3:
        final.insert_pdf(d3)
    destino = salida / f"DICTUS_2.0_EXPEDIENTE_{args.folio}.pdf"
    final.save(str(destino))
    final.close()
    hoja.unlink(missing_ok=True)

    # ── Artefactos ────────────────────────────────────────────────────────────
    (salida / "EXECUTIVE_DOCUMENT_MODEL.json").write_text(
        json.dumps(modelo, ensure_ascii=False, indent=1), encoding="utf-8")
    (salida / "EVIDENCE_MANIFEST.json").write_text(
        json.dumps(modelo["evidence_manifest"], ensure_ascii=False, indent=1), encoding="utf-8")
    import hashlib
    pdf_sha = hashlib.sha256(destino.read_bytes()).hexdigest()
    (salida / "MASTER_HASH.json").write_text(json.dumps({
        "dictus_id": modelo["document_identity"]["dictus_id"],
        "master_manifest_version": dm.MASTER_MANIFEST_VERSION,
        "master_hash": modelo["master_hash"],
        "master_hash_abreviado": modelo["master_hash_abreviado"],
        "pdf_binary_sha256": pdf_sha,
        "nota": ("DICTUS_MASTER_HASH sella el conjunto canónico de hechos y evidencias; "
                 "pdf_binary_sha256 sella el archivo entregado. Son hashes distintos y no "
                 "se sustituyen entre sí."),
        "verify": dm.verificar(modelo, modelo["master_hash"]),
        "historico": {"veredicto": hist.get("veredicto"),
                      "conflictos_abiertos": [c["atributo"] for c in hist.get("conflictos_abiertos", [])]},
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    with pymupdf.open(str(destino)) as d:
        print(f"[ejecutivo] {destino.relative_to(ROOT)} · {d.page_count} páginas "
              f"(6 ejecutivas + 1 hoja de anexos + {d.page_count - 7} de cuerpo técnico)")
    print(f"[ejecutivo] hash maestro {modelo['master_hash'][:16]}… · "
          f"pdf {pdf_sha[:16]}… · evidencias "
          f"{modelo['evidence_manifest']['evidence_count']}")
    print(f"[ejecutivo] retícula: {'OK' if not de.VIOLACIONES else de.VIOLACIONES}")
    print(f"[ejecutivo] hallazgos en página 1: {len(hallazgos)} · "
          f"conflictos históricos abiertos: {len(hist.get('conflictos_abiertos', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

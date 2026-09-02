# -*- coding: utf-8 -*-
"""
ARHIAX RE - Analizador Legal de Certificados de Libertad y Tradicion
Parsea el texto de un CTL y genera anotaciones, titulares, constructor
y hallazgos dinamicos reales.
"""

import re
import os
import sys
import pypdf
from pathlib import Path

# Colores globales ARHIAX para ReportLab
from reportlab.lib import colors

C_ROJO = colors.HexColor("#D92C2C")
C_NARANJA = colors.HexColor("#F08C2B")
C_VERDE = colors.HexColor("#1A6B3A")
C_OK_BG = colors.HexColor("#EBF5EE")
C_ALERTA_BG = colors.HexColor("#FFF5EB")
C_RIESGO_BG = colors.HexColor("#FDF2F2")

def analizar_certificado(pdf_path):
    """
    Carga el PDF del Certificado de Libertad y Tradicion y delega el analisis.
    """
    res = {
        "folio": "040-XXXXXX",
        "direccion": "Pendiente de verificacion",
        "barrio": "Desconocido",
        "apertura": "N/D",
        "titulares": "PENDIENTE DE VERIFICACION (Sin Certificado cargado)",
        "constructor": "N/D",
        "anotaciones": [],
        "hallazgos": [],
        "recs": [],
        # Sprint 2 (exactitud): códigos del CTL para resolver el predio real en catastro
        "codigo_catastral": None,
        "nupre": None,
        "tipo_predio_snr": None,
        "descripcion_ctl": None,
        "modalidad_adquisicion": "N/D",
    }

    if not pdf_path or not os.path.exists(pdf_path):
        res["hallazgos"] = [
            ("ALTO", C_ROJO, C_RIESGO_BG,
             "H-01 | AUSENCIA DE CERTIFICADO DE TRADICION Y LIBERTAD (CTL)",
             "Requerimiento Documental Obligatorio",
             "No se aporto el Certificado de Tradicion y Libertad en PDF para validar la titularidad y gravamenes del activo.",
             "BLOQUEO TOTAL para estructuracion fiduciaria u originacion de creditos. Requiere cargue de CTL.")
        ]
        res["recs"] = [
            ("R-01 | Requerimiento INMEDIATO de Certificado SNR", 
             "El propietario o estructurador debe solicitar de manera urgente el Certificado de Tradicion y Libertad actualizado.")
        ]
        return res

    try:
        reader = pypdf.PdfReader(pdf_path)
        texto = ""
        for page in reader.pages:
            t = page.extract_text()
            if t:
                texto += t
        
        return analizar_texto_certificado(texto)
    except Exception as e:
        print("[LEGAL_ANALYZER][ERROR] Falla al analizar CTL {}: {}".format(pdf_path, e))
        res["hallazgos"] = [
            ("MEDIO", C_NARANJA, C_ALERTA_BG,
             "H-01 | ERROR EN ANALISIS DE CTL",
             "Estudio de Titulos / ORIP",
             "No se pudo extraer metadatos del CTL por falla tecnica: {}.".format(e),
             "Se requiere verificacion manual de la tradicion del inmueble.")
        ]
        return res

def analizar_texto_certificado(texto):
    """
    Parsea el texto de un Certificado de Libertad y Tradicion y extrae anotaciones,
    titulares, afectaciones, hipotecas y cancelaciones de forma dinámica.
    """
    res = {
        "folio": "040-XXXXXX",
        "direccion": "Pendiente de verificacion",
        "barrio": "Desconocido",
        "apertura": "N/D",
        "titulares": "PENDIENTE DE VERIFICACION (Sin propietarios vigentes detectados)",
        "constructor": "N/D",
        "anotaciones": [],
        "hallazgos": [],
        "recs": [],
        "codigo_catastral": None,
        "nupre": None,
        "tipo_predio_snr": None,
        "descripcion_ctl": None,
        "modalidad_adquisicion": "N/D",
    }

    if not texto:
        return res

    try:
        # 1. Extraer Folio
        m_folio = re.search(r"\b(\d{3}-\d+)\b", texto)
        if m_folio:
            res["folio"] = m_folio.group(1)

        # 2. Apertura del Folio
        m_apertura = re.search(r"(?:fecha\s+apertura|abierto\s+el|apertura)\s*[:\-]?\s*([^\n\r]+)", texto, re.IGNORECASE)
        if m_apertura:
            # El CTL real pega el texto siguiente: "28-03-2001  RADICACIÓN: 2001-8209 ..."
            res["apertura"] = m_apertura.group(1).strip()

        # 2b. Código catastral y NUPRE (fuente de verdad para el predio real)
        m_cc = re.search(r"(?:CODIGO\s*CATASTRAL|C[OÓ]DIGO\s*CATASTRAL)\s*[:\-]?\s*(\d{20,30})", texto, re.IGNORECASE)
        if m_cc:
            res["codigo_catastral"] = m_cc.group(1)
        m_nupre = re.search(r"NUPRE\s*[:\-]?\s*([A-Z0-9]{8,40})", texto, re.IGNORECASE)
        if m_nupre:
            cand = m_nupre.group(1).strip()
            if re.match(r"^(AFT|NPR|08001)", cand, re.IGNORECASE):
                res["nupre"] = cand

        # 2c. Tipo de predio (URBANO/RURAL) y descripción (BODEGA/CASA/APARTAMENTO...)
        m_tipo = re.search(r"Tipo\s+Predio\s*:\s*([A-ZÁÉÍÓÚÑ ]{3,20})", texto, re.IGNORECASE)
        if m_tipo:
            res["tipo_predio_snr"] = m_tipo.group(1).strip()
        m_desc = re.search(
            r"DESCRIPCION\s*:.*?\n(.*?)(?=\n\s*\n|\nAREA|\nSUPERINTENDENCIA|\nDIRECCION|\nCABIDA|\Z)",
            texto, re.IGNORECASE | re.DOTALL)
        if not m_desc:
            # Formato compacto: "DESCRIPCION: CABIDA Y LINDEROS ... BODEGA NRO 3 ..."
            m_desc = re.search(r"DESCRIPCION\s*:\s*(.+?)(?=\n\s*\n|\nAREA|\nSUPERINTENDENCIA|\Z)",
                               texto, re.IGNORECASE | re.DOTALL)
        if m_desc:
            bloque = m_desc.group(1)
            primera = " ".join(bloque.split())[:400]
            res["descripcion_ctl"] = primera

        # 2d. Dirección del inmueble (formato CTL SNR: bloque DIRECCION DEL INMUEBLE)
        m_dir = re.search(
            r"DIRECCION\s+DEL\s+INMUEBLE\s*\n(?:Tipo\s+Predio\s*:[^\n]*\n)?\s*(?:\d+\)\s*)?"
            r"([A-Z0-9ÁÉÍÓÚÑ \.\#\-]{8,80})",
            texto, re.IGNORECASE)
        if m_dir:
            cand_dir = m_dir.group(1).strip()
            if re.search(r"\b(CL|CLL|CALLE|CRA|KR|CARRERA|TV|AV|DG|DIAGONAL)\b", cand_dir, re.IGNORECASE) and re.search(r"\d", cand_dir):
                res["direccion"] = cand_dir

        # Parsear Anotaciones - Requiere que ANOTACION este en una nueva linea.
        # El CTL real usa indistintamente "ANOTACION: Nro 001", "ANOTACION Nro 002"
        # y "Anotación Nro: 0" (salvedades). Se normaliza ":" pegado al token.
        _texto_anot = re.sub(r"ANOTACI[OÓ]N\s*:", "ANOTACION ", texto, flags=re.IGNORECASE)
        _texto_anot = re.sub(r"Anotaci[oó]n\s+Nro\s*:", "ANOTACION ", _texto_anot, flags=re.IGNORECASE)
        anotaciones_raw = re.split(r"(?:\r?\n|^)\s*ANOTACI[OÓ]N\s+(?:Nro|N[oO]?|:)?\s*", _texto_anot, flags=re.IGNORECASE)

        
        parsed_anotaciones = []
        cancelaciones = [] # lista de tuples (anot_cancela, anot_cancelada)

        for a_block in anotaciones_raw[1:]:  # Omitir texto previo a la anotacion 1
            a_block_clean = a_block.strip().lstrip(":. \tº°")
            lines = [line.strip() for line in a_block_clean.split("\n") if line.strip()]
            if not lines:
                continue
            
            num_anot_match = re.match(r"^(\d+)", lines[0])
            if not num_anot_match:
                continue
            num_anot = num_anot_match.group(1).zfill(3)

            fecha_match = re.search(r"(\d{2}-\d{2}-\d{4})", a_block_clean)
            fecha_anot = fecha_match.group(1) if fecha_match else "N/D"

            # Unir con \n (NO con espacio): los adquirentes/titulares se extraen
            # de líneas completas "A: NOMBRE" y con espacio los nombres se mezclan.
            bloque_texto = "\n".join(lines)


            tipo_anot = "OTRO"
            sup = bloque_texto.upper()
            # Prioridad 1: CANCELACION (p. ej. "CANCELACION: 0843 ... CANCELACION HIPOTECA").
            # Debe evaluarse ANTES de HIPOTECA: la anotación que cancela menciona la hipoteca.
            if "CANCELACION" in sup or "SE CANCELA ANOTACION" in sup or "CANCELA LA ANOTACION" in sup:
                tipo_anot = "CANCELACION"
            # Prioridad 2: aclaraciones/modificaciones (no crean ni extinguen gravámenes)
            elif "ACLARACION" in sup or "MODIFICACION A LA HIPOTECA" in sup or "CORRECCION" in sup:
                tipo_anot = "OTRO: Aclaracion"
            elif "HIPOTECA" in sup:
                tipo_anot = "GRAVAMEN: Hipoteca"
            elif "EMBARGO" in sup or "MEDIDA CAUTELAR" in sup:
                tipo_anot = "GRAVAMEN: Embargo"
            elif "AFECTACION" in sup or "VIVIENDA FAMILIAR" in sup:
                tipo_anot = "LIMITACION: Afectacion Vivienda"
            elif "PATRIMONIO" in sup and "INEMBARGABLE" in sup:
                tipo_anot = "LIMITACION: Patrimonio Familia"
            elif "COMPRAVENTA" in sup or "ADQUISICION" in sup or "FUSION" in sup \
                    or "DIVISION MATERIAL" in sup or "PERMUTA" in sup or "ADJUDICACION" in sup \
                    or "MODO DE ADQUISICION" in sup:
                tipo_anot = "COMPRAVENTA"

            # Extraer partes (De: A:) de líneas completas (formato SNR).
            partes = "N/D"
            de_part = ""
            a_part = ""
            for _l in lines:
                _ls = _l.strip()
                m_de = re.match(r"DE\s*:\s*(.+)", _ls, re.IGNORECASE)
                m_a = re.match(r"A\s*:\s*(.+)", _ls, re.IGNORECASE)
                if m_de and not de_part:
                    de_part = m_de.group(1).strip()
                elif m_a and not a_part:
                    a_part = m_a.group(1).strip()
            if de_part or a_part:
                partes = "{} -> {}".format(de_part, a_part) if de_part and a_part else (de_part or a_part)
                if len(partes) > 120:
                    partes = partes[:117] + "..."

            # Registrar cancelaciones
            if tipo_anot == "CANCELACION":
                cancela_match = re.search(r"cancela\s+(?:anotaci[oó]n|anot\.?)\s*(?:nro|n[o])?\s*[:\-\s]*\s*(\d+)", bloque_texto, re.IGNORECASE)
                if cancela_match:
                    target_anot = cancela_match.group(1).zfill(3)
                    cancelaciones.append((num_anot, target_anot))


            parsed_anotaciones.append({
                "num": num_anot,
                "fecha": fecha_anot,
                "tipo": tipo_anot,
                "partes": partes,
                "texto": bloque_texto,
                "estado": "VIGENTE"
            })

        # Aplicar cancelaciones
        for canc_anot, target in cancelaciones:
            for item in parsed_anotaciones:
                if item["num"] == target:
                    item["estado"] = "CANCELADA -- Anot. {} la extingue".format(canc_anot)

        # 4. Extraer duenos: la anotación de adquisición de dominio MÁS RECIENTE
        # no cancelada (compraventa, fusión, división, permuta, adjudicación) define
        # al titular actual. Se toma la línea "A:" (adquirente) del bloque.
        def _adquirente_de(bloque_texto):
            """Extrae el nombre del adquirente de la línea 'A: ...' de una anotación."""
            for line in bloque_texto.split("\n"):
                ls = line.strip()
                m = re.match(r"A\s*:\s*(.+)", ls, re.IGNORECASE)
                if m:
                    nombre = m.group(1).strip()
                    # Quitar marcas de titular (X / I) y documentos (CC/NIT/CE)
                    nombre = re.sub(r"\s*[XI]\s*$", "", nombre)
                    nombre = re.sub(r"(?:\bCC\b|\bNIT\b|\bCE\b|C\.C\.|N\.I\.T\.)\s*[\d\.\-]+", "", nombre, flags=re.IGNORECASE)
                    nombre = re.sub(r"[.,;]$", "", nombre).strip()
                    nombre = " ".join(nombre.split())
                    if len(nombre) >= 3:
                        return nombre
            return None

        titulares_lista = []
        for item in reversed(parsed_anotaciones):
            if item["tipo"] == "COMPRAVENTA" and "CANCELADA" not in item["estado"]:
                nombre_titular = _adquirente_de(item["texto"])
                if not nombre_titular:
                    # Fallback: buscar el "A:" en el texto sin saltos de línea
                    m2 = re.search(r"A\s*:\s*([^,\.]{4,90})", item["texto"], re.IGNORECASE)
                    nombre_titular = m2.group(1).strip() if m2 else None
                if nombre_titular:
                    titulares_lista.append(nombre_titular)
                    break
        
        if titulares_lista:
            res["titulares"] = " + ".join(titulares_lista)
        else:
            prop_match = re.findall(r"a\s+favor\s+de\s+([A-Z\s]{4,40})", texto)
            if prop_match:
                res["titulares"] = prop_match[-1].strip()
            else:
                res["titulares"] = "PENDIENTE DE VERIFICACION (No se identificó anotación de adquisición vigente en el CTL)"

        # Constructor: solo empresas constructoras/urbanizadoras explícitas con
        # nombre propio. "INMOBILIARIA"/"S.A.S." sueltos NO cuentan (aparecen en
        # "MATRICULA INMOBILIARIA" y en toda sociedad). Se exige que el match NO
        # esté rodeado de palabras comunes de plantilla del certificado.
        const_match = re.search(
            r"(CONSTRUCTORA|URBANIZADORA|CONSTRUCTOR|CONCIVI|MARVAL)\s+([A-ZÁÉÍÓÚÑ0-9&\s]{3,30})",
            texto, re.IGNORECASE)
        if const_match:
            cand_const = const_match.group(0).strip()
            # Descartar coincidencias espurias (plantillas del certificado)
            if re.search(r"SUPERINTEND|REGISTRO|ORIP|NOTARIADO|MATRICULA|ESCRITURA|CERTIFICADO",
                         cand_const, re.IGNORECASE) or len(cand_const) > 45:
                res["constructor"] = "N/D"
            else:
                res["constructor"] = cand_const
        else:
            res["constructor"] = "N/D"

        # 5. Generar lista de anotaciones final
        res["anotaciones"] = [
            (item["num"], item["fecha"], item["tipo"], item["partes"], item["estado"])
            for item in parsed_anotaciones
        ]

        # 5b. Inferir acreedor_snr del CTL (D1 — NLP automático)
        # Extrae el acreedor del gravamen hipotecario más reciente activo
        hipotecas_vigentes = [
            item for item in parsed_anotaciones
            if "GRAVAMEN" in item["tipo"] and "Hipoteca" in item["tipo"]
            and "CANCELADA" not in item["estado"]
        ]
        if hipotecas_vigentes:
            partes_hip = hipotecas_vigentes[-1]["partes"]
            # Las partes tienen formato "De -> A" donde A es el acreedor
            if "->" in partes_hip:
                acreedor_raw = partes_hip.split("->")[-1].strip()
            else:
                acreedor_raw = partes_hip.strip()
            # Fallback al texto completo si el extracto es muy corto
            if len(acreedor_raw) < 4:
                acreedor_raw = hipotecas_vigentes[-1]["texto"][:80]
            res["acreedor_snr"] = acreedor_raw
        else:
            res["acreedor_snr"] = None
        # acreedor_real se declara externamente o queda None (sin discrepancia)
        res.setdefault("acreedor_real", None)

        # 6. Generar Hallazgos dinamicos
        h_idx = 1
        for item in parsed_anotaciones:
            if "GRAVAMEN" in item["tipo"] and "CANCELADA" not in item["estado"]:
                res["hallazgos"].append((
                    "ALTO", C_ROJO, C_RIESGO_BG,
                    "H-0{} | {} Vigente (Anot. {})".format(h_idx, item['tipo'], item['num']),
                    "SNR Registral",
                    "Se detecto un gravamen activo registrado en la anotacion {}: {}...".format(item['num'], item['texto'][:250]),
                    "BLOQUEO para estructuracion fiduciaria. Requiere levantamiento de hipoteca/embargo."
                ))
                res["recs"].append((
                    "R-0{} | Cancelacion de gravamen Anot. {}".format(h_idx, item['num']),
                    "Se debe tramitar la escritura publica de cancelacion y registrarla en el folio SNR para sanear el predio."
                ))
                h_idx += 1
            elif "LIMITACION" in item["tipo"] and "CANCELADA" not in item["estado"]:
                res["hallazgos"].append((
                    "MEDIO", C_NARANJA, C_ALERTA_BG,
                    "H-0{} | Afectacion/Limitacion Vigente (Anot. {})".format(h_idx, item['num']),
                    "SNR Registral",
                    "Se detecto una afectacion o limitacion al dominio vigente: {}...".format(item['texto'][:250]),
                    "Restringe libre disposicion. Venta o traspaso requiere consentimiento de los conyuges/titulares."
                ))
                res["recs"].append((
                    "R-0{} | Levantamiento de Limitacion Anot. {}".format(h_idx, item['num']),
                    "Si se aporta a fideicomiso, se requiere desafectacion mediante escritura publica conjunta."
                ))
                h_idx += 1

        # Si no hay hallazgos de alerta, tradicion limpia
        if not res["hallazgos"]:
            res["hallazgos"].append((
                "INFORMATIVO", C_VERDE, C_OK_BG,
                "H-01 | Tradicion Registral Libre de Gravamenes Activos",
                "SNR -- Tradicion",
                "Se analizaron todas las anotaciones del certificado. No se detectaron hipotecas, embargos ni afectaciones vigentes.",
                "Favorable para la originacion de creditos y estructuracion de garantias sin restricciones."
            ))

    except Exception as e:
        print("[LEGAL_ANALYZER][ERROR] Falla al procesar texto de CTL: {}".format(e))
        res["hallazgos"] = [
            ("MEDIO", C_NARANJA, C_ALERTA_BG,
             "H-01 | ERROR EN PARSING DE TEXTO CTL",
             "Estudio de Titulos / ORIP",
             "No se pudo analizar el contenido textual del CTL por falla interna: {}.".format(e),
             "Se requiere verificacion manual de la tradicion del inmueble.")
        ]
    
    return res


# ── Bloque 2 Sprint 1 — Conciliación Registral ───────────────────────────────

def _normalizar_entidad(nombre):
    """Normaliza el nombre de una entidad financiera para comparación robusta.
    Elimina sufijos legales, tildes y espacios extra."""
    import unicodedata
    if not nombre:
        return ""
    nfkd = unicodedata.normalize("NFKD", nombre.upper())
    texto = "".join(c for c in nfkd if not unicodedata.combining(c))
    sufijos = [
        r"\bS\.A\.S\.?\b", r"\bS\.A\.?\b", r"\bLTDA\.?\b",
        r"\bE\.P\.?\b", r"\bS\.A\.S\b", r"\bCOLPATRIA\b",
    ]
    for s in sufijos:
        texto = re.sub(s, "", texto)
    texto = re.sub(r"[.\-,]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


_ENTIDADES_EQUIV = [
    {"BANCO DE BOGOTA", "BOGOTA"},
    {"SCOTIABANK COLPATRIA", "COLPATRIA", "SCOTIABANK"},
    {"BANCOLOMBIA", "SURAMERICANA"},
    {"DAVIVIENDA", "GRANBANCO", "BANCO CAFETERO"},
    {"BBVA", "BANCO BILBAO VIZCAYA"},
    {"AV VILLAS", "BANCO AV VILLAS"},
]


def _mismo_grupo(a, b):
    """Retorna True si ambas entidades pertenecen al mismo grupo financiero."""
    for grupo in _ENTIDADES_EQUIV:
        en_grupo_a = any(tok in a for tok in grupo)
        en_grupo_b = any(tok in b for tok in grupo)
        if en_grupo_a and en_grupo_b:
            return True
    return False


def detectar_discrepancia_acreedor(acreedor_snr, acreedor_real):
    """Detecta discrepancias entre el acreedor registrado en el SNR
    y el acreedor real declarado por el titular.

    Args:
        acreedor_snr:  Nombre del acreedor tal como aparece en el folio SNR.
        acreedor_real: Nombre del acreedor real declarado por el titular.

    Returns:
        None si no hay discrepancia.
        Dict con tipo, severidad, acreedor_snr, acreedor_real,
        hallazgo_titulo, hallazgo_descripcion, hallazgo_implicacion.
    """
    if not acreedor_snr and not acreedor_real:
        return None

    snr_norm = _normalizar_entidad(acreedor_snr or "")
    real_norm = _normalizar_entidad(acreedor_real or "")

    if snr_norm == real_norm:
        return None

    if snr_norm and real_norm and _mismo_grupo(snr_norm, real_norm):
        return None

    if snr_norm and real_norm and snr_norm != real_norm:
        return {
            "tipo": "CESION_NO_REGISTRADA",
            "severidad": "ALTO",
            "acreedor_snr": acreedor_snr,
            "acreedor_real": acreedor_real,
            "hallazgo_titulo": (
                "H-DISC | Discrepancia Acreedor SNR vs. Acreedor Real (Cesion de Cartera)"
            ),
            "hallazgo_descripcion": (
                "El folio SNR registra a {} como acreedor hipotecario. "
                "Sin embargo, el titular declara que {} es el acreedor "
                "real del credito (posible cesion de cartera no inscrita en el ORIP). "
                "El SNR no refleja este cambio, generando una discrepancia entre el "
                "registro publico y la realidad operativa del credito.".format(
                    acreedor_snr, acreedor_real)
            ),
            "hallazgo_implicacion": (
                "OBLIGATORIO para due diligence: Verificar con el banco cesionario la "
                "cesion formal y solicitar su anotacion en el folio SNR. Sin este "
                "registro, cualquier operacion sobre el activo referenciara al acreedor "
                "incorrecto. [REQUIERE VERIFICACION por profesional del derecho]"
            ),
        }

    if not snr_norm and real_norm:
        return {
            "tipo": "ACREEDOR_NO_REGISTRADO",
            "severidad": "ALTO",
            "acreedor_snr": None,
            "acreedor_real": acreedor_real,
            "hallazgo_titulo": "H-DISC | Acreedor Declarado No Inscrito en el SNR",
            "hallazgo_descripcion": (
                "El titular declara que {} tiene un gravamen sobre el activo, "
                "pero el folio SNR no registra ningun acreedor hipotecario. "
                "Posible hipoteca no inscrita o gravamen informal.".format(acreedor_real)
            ),
            "hallazgo_implicacion": (
                "Verificar con el acreedor declarado el estado del credito y proceder "
                "a la inscripcion formal del gravamen si corresponde. "
                "[REQUIERE VERIFICACION por profesional del derecho]"
            ),
        }

    return None

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

def _parsear_cuantia_cop(texto: str):
    """Extrae y convierte a entero una cuantía en COP declarada en una anotación
    ('CUANTIA: $ 160.000.000', 'por valor de 160.000.000', '160.000.000,00').
    Devuelve None si no se encuentra (el dictamen NO inventa la cuantía)."""
    if not texto:
        return None
    m = re.search(
        r"(?:CREDITO INICIAL APROBADO POR|VALOR ACTO|CUANTIA|por\s+valor\s+de)"
        r"\s*:?\s*\$?\s*([\d]{1,3}(?:[.,][\d]{3})+)", texto, re.IGNORECASE)
    if not m:
        return None
    raw = m.group(1)
    # '160.000.000' (formato colombiano: punto de miles) o '160,000,000'
    if "," in raw and "." in raw:
        # 1.234.567,89 -> quitar puntos, coma a decimal (se descarta)
        num = raw.replace(".", "").replace(",", "")
    elif "." in raw and "," not in raw:
        num = raw.replace(".", "")     # 160.000.000 -> 160000000
    elif "," in raw and "." not in raw:
        num = raw.replace(",", "")     # 160,000,000 -> 160000000
    else:
        num = raw
    try:
        return int(num)
    except (TypeError, ValueError):
        return None


def inferir_condicion_juridica(texto, descripcion_ctl=None):
    """Infiera la CONDICIÓN JURÍDICA (Propiedad Horizontal / No PH) desde el
    texto del CTL/SNR — fuente registral disponible en todas las ciudades.

    El dato catastral de 'condición' solo lo publica Barranquilla; Medellín y
    Bogotá no lo exponen en capas abiertas, pero el folio sí lo dice:
      * PH: mención de 'PROPIEDAD HORIZONTAL', 'COEFICIENTE' (de copropiedad),
        'REGLAMENTO DE PROPIEDAD HORIZONTAL', 'CONSTITUCION DE PROPIEDAD
        HORIZONTAL' o unidad con coeficiente (apartamento/oficina/parqueadero).
      * No PH: 'NO PROPIEDAD HORIZONTAL' explícito, o lote/terreno/bodega
        descrito como predio independiente sin marcadores de copropiedad.

    Regla de honestidad: sin marcador claro devuelve None (el dictamen lo deja
    PENDIENTE para verificación del profesional). Nunca se afirma PH ni No PH
    sin evidencia en el folio.
    """
    if not texto:
        return None
    sup = " ".join(str(texto).upper().split())
    desc = " ".join(str(descripcion_ctl or "").upper().split())
    # 1) No PH explícito tiene prioridad sobre menciones genéricas de PH
    if "NO PROPIEDAD HORIZONTAL" in sup:
        return "No Propiedad Horizontal"
    # 2) Marcadores fuertes de propiedad horizontal
    marcadores_ph = [
        "PROPIEDAD HORIZONTAL",
        "REGLAMENTO DE PROPIEDAD HORIZONTAL",
        "CONSTITUCION DE PROPIEDAD HORIZONTAL",
        "COEFICIENTE",
    ]
    if any(m in sup for m in marcadores_ph):
        return "Propiedad Horizontal"
    # 2b) Un folio individual de APARTAMENTO implica régimen de PH (unidad con
    # coeficiente en la descripción/escritura); se acepta de la descripción.
    if any(k in desc for k in ("APARTAMENTO", "APTO ", "APTO.")):
        return "Propiedad Horizontal"
    # 3) Predio independiente (lote/terreno/bodega) sin marcadores PH
    if any(k in sup for k in ("BODEGA", "LOTE DE TERRENO", "TERRENO", "CASA LOTE")):
        if "COEFICIENTE" not in sup and "APARTAMENTO" not in sup:
            return "No Propiedad Horizontal"
    return None


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
        "anotaciones_detalle": [],
        "hallazgos": [],
        "recs": [],
        # Sprint 2 (exactitud): códigos del CTL para resolver el predio real en catastro
        "codigo_catastral": None,
        "nupre": None,
        "tipo_predio_snr": None,
        "descripcion_ctl": None,
        "modalidad_adquisicion": "N/D",
        "circulo_registral": None,
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

def _extraer_folio(texto):
    """Extrae la matrícula inmobiliaria del texto de un CTL/SNR.

    Colombia usa una matrícula por oficina de registro: Barranquilla '040-...',
    Medellín '001-...' y Bogotá con sub-oficinas alfanuméricas '50C-...',
    '50N-...', '50S-...'. El CTL moderno la etiqueta 'Nro Matrícula: 50C-...' y
    el clásico 'MATRICULA INMOBILIARIA: 040-...'. Los folios que solo se CITAN
    en el cuerpo (p. ej. 'REGISTRADA AL FOLIO 050-0554696' en la
    COMPLEMENTACION de un CTL de Bogotá) no deben ganarle a la etiqueta.
    Retorna el folio o None.
    """
    if not texto:
        return None
    # 1) Etiquetas de matrícula (moderna 'Nro Matrícula:' y clásica)
    m = re.search(
        r"(?:NRO\s+|No\.?\s+|N[°º]?\.?\s+|NUMERO\s+)?"
        r"MATR[IÍ]CULA(?:\s+INMOBILIARIA)?\s*[:\-]?\s*"
        r"([0-9]{2,3}[A-Z]?-\d{1,12})", texto, re.IGNORECASE)
    if m:
        return m.group(1)
    # 2) Fallback sin etiqueta: exige >=4 dígitos tras el guion para no capturar
    #    fechas (dd-mm-aaaa) ni turnos ('2026-50C-1-644770' -> '50C-1').
    m2 = re.search(r"\b(\d{3}-\d{4,12})\b", texto) or \
         re.search(r"\b(\d{2}[A-Z]-\d{4,12})\b", texto)
    return m2.group(1) if m2 else None


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
        "anotaciones_detalle": [],
        "hallazgos": [],
        "recs": [],
        "codigo_catastral": None,
        "nupre": None,
        "tipo_predio_snr": None,
        "descripcion_ctl": None,
        "modalidad_adquisicion": "N/D",
        # Sprint 3 (mejora 2): círculo registral real que declara el CTL
        # (p. ej. '001 - MEDELLIN', '050 - BOGOTA D.C. ZONA CENTRO'). Permite
        # detectar un CTL de otra ciudad adjuntado por error al caso.
        "circulo_registral": None,
        # Remediation 03D: dirección base + unidad PH (sin pérdida de especificidad).
        "direccion_base": None,
        "torre": None,
        "apartamento": None,
        "unidad": None,
    }

    if not texto:
        return res

    try:
        # 1. Extraer Folio. Colombia usa matrículas por oficina de registro:
        #    Barranquilla '040-...', Medellín '001-...' y Bogotá con sub-oficinas
        #    alfanuméricas '50C-...', '50N-...', '50S-...' (Zona Centro/Norte/Sur).
        #    El CTL moderno etiqueta 'Nro Matrícula: 50C-1463431' (encabezado) y el
        #    clásico 'MATRICULA INMOBILIARIA: 040-...'; los folios históricos que
        #    se CITAN dentro del texto (p. ej. 'REGISTRADA AL FOLIO 050-0554696'
        #    en la COMPLEMENTACION) nunca deben ganarle a la etiqueta principal.
        m_folio = _extraer_folio(texto)
        if m_folio:
            res["folio"] = m_folio

        # 1b. Círculo registral real declarado en el CTL (recortado en DEPTO/
        #     MUNICIPIO/VEREDA que comparten la misma línea en los CTL de Bogotá)
        m_circ = re.search(
            r"(?:CIRCULO\s+REGISTRAL|C[IÍ]RCULO\s+REGISTRAL)\s*[:\-]?\s*"
            r"([0-9]{2,3}[A-Z]?[^\n\r]{0,45}?)(?=\s+DEPTO\b|\s+MUNICIPIO\b|\s+VEREDA\b|\n|$)",
            texto, re.IGNORECASE)
        if m_circ:
            res["circulo_registral"] = " ".join(m_circ.group(1).split()).strip(" -")

        # 2. Apertura del Folio
        m_apertura = re.search(r"(?:fecha\s+apertura|abierto\s+el|apertura)\s*[:\-]?\s*([^\n\r]+)", texto, re.IGNORECASE)
        if m_apertura:
            # El CTL real pega el texto siguiente: "28-03-2001  RADICACIÓN: 2001-8209 ..."
            res["apertura"] = m_apertura.group(1).strip()

        # 2b. Código catastral y NUPRE (fuente de verdad para el predio real)
        # El CTL de Bogotá trae códigos de 18+ dígitos y puede pegar la etiqueta
        # siguiente ('COD CATASTRAL ANT') sin espacio: se acepta 15-30 dígitos.
        m_cc = re.search(r"(?:CODIGO\s*CATASTRAL|C[OÓ]DIGO\s*CATASTRAL)\s*[:\-]?\s*(\d{15,30})", texto, re.IGNORECASE)
        if m_cc:
            res["codigo_catastral"] = m_cc.group(1)
        m_nupre = re.search(r"NUPRE\s*[:\-]?\s*([A-Z0-9]{8,40})", texto, re.IGNORECASE)
        if m_nupre:
            cand = m_nupre.group(1).strip()
            # El NUPRE es el identificador predial nacional: el prefijo varía por
            # ciudad/gestor (AFT en BAQ, NPR nuevo, AAA en Bogotá...). Solo se
            # valida que contenga dígitos (no es una palabra suelta del CTL).
            if re.search(r"\d", cand) and len(cand) <= 15:
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

        # 2d. Dirección del inmueble (formato CTL SNR: bloque DIRECCION DEL INMUEBLE).
        # El CTL de Bogotá distingue la DIRECCION CATASTRAL oficial (p. ej.
        # '2) DG 61B 20 04 AP 401 (DIRECCION CATASTRAL)') junto a otras placas
        # registrales ('AVENIDA (CALLE) 63 20-04/CARRERA 20 61-55...'): se
        # prefiere la CATASTRAL y se descarta la unidad (AP/EDIFICIO/PH).
        _dir_oficial = None
        idx_di = texto.upper().find("DIRECCION DEL INMUEBLE")
        if idx_di >= 0:
            ventana = texto[idx_di: idx_di + 700]
            m_cat = re.search(
                r"([A-Z0-9ÁÉÍÓÚÑ\.\#\-/ ]{4,90}?)\s*\(?\s*DIRECCION CATASTRAL",
                ventana, re.IGNORECASE)
            if m_cat:
                _dir_oficial = m_cat.group(1)
            else:
                m_prim = re.search(
                    r"(?:[0-9]+\)\s*)?((?:AV|AVENIDA|CL|CLL|CALLE|CRA|KR|CARRERA|"
                    r"TV|DG|DIAGONAL|AK)\s*[A-Z0-9ÁÉÍÓÚÑ\.\#\-/ ]{4,60})",
                    ventana, re.IGNORECASE)
                if m_prim:
                    _dir_oficial = m_prim.group(1)
        if _dir_oficial:
            # Remediation 03D: NO destruir la unidad. La dirección COMPLETA se
            # preserva (direccion_raw) y se DERIVA la base + torre/apartamento.
            _dir_full = re.sub(r"\(?\s*DIRECCION CATASTRAL\s*\)?", "", _dir_oficial)
            _dir_full = " ".join(_dir_full.split()).strip(" .,;/")
            if (re.search(r"\b(CL|CLL|CALLE|CRA|KR|CARRERA|TV|AV|AVENIDA|DG|DIAGONAL|AK)\b",
                          _dir_full, re.IGNORECASE)
                    and re.search(r"\d", _dir_full)):
                res["direccion"] = _dir_full
                # Derivación no destructiva de la base y la unidad inmobiliaria.
                from unidad_inmobiliaria import extraer_unidad
                _unidad = extraer_unidad(_dir_full)
                res["direccion_base"] = _unidad["direccion_base"]
                res["torre"] = _unidad["torre"]
                res["apartamento"] = _unidad["apartamento"]
                res["unidad"] = _unidad["unidad"]

        # Parsear Anotaciones - Requiere que ANOTACION este en una nueva linea.
        # El CTL real usa indistintamente "ANOTACION: Nro 001", "ANOTACION Nro 002"
        # y "Anotación Nro: 0" (salvedades). Se normaliza ":" pegado al token.
        _texto_anot = re.sub(r"ANOTACI[OÓ]N\s*:", "ANOTACION ", texto, flags=re.IGNORECASE)
        _texto_anot = re.sub(r"Anotaci[oó]n\s+Nro\s*:", "ANOTACION ", _texto_anot, flags=re.IGNORECASE)
        # Regresión (CTL real 040-646406, queja del usuario): la sección
        # SALVEDADES del certificado ("Anotación Nro: 5 Nro corrección: 1...
        # INSERCIÓN ACTO OMITIDO ART.59 LEY 1579/12") lista correcciones de
        # anotaciones ANTERIORES, NO anotaciones nuevas del folio. El split las
        # capturaba como anotaciones fantasma '005/007/008/006/000 OTRO N/D
        # VIGENTE'. Todo lo posterior a 'SALVEDADES' no pertenece a la cadena
        # de tradición: se descarta.
        _corte_salvedades = re.search(
            r"\bSALVEDADES\s*:?\s*\(?Informaci[oó]n Anterior o Corregida",
            _texto_anot, re.IGNORECASE)
        if _corte_salvedades:
            _texto_anot = _texto_anot[:_corte_salvedades.start()]
        else:
            # Sin SALVEDADES: si hay un cierre 'NRO TOTAL DE ANOTACIONES: *N*' y
            # después NO hay más anotaciones, cortar ahí (el texto posterior es
            # el sello del registrador). Si el total aparece ANTES de más
            # anotaciones (CTL fragmentados), se ignora y el parseo sigue.
            _m_total = re.search(
                r"NRO\s+TOTAL\s+DE\s+ANOTACIONES\s*:\s*\*?\d+\*?", _texto_anot,
                re.IGNORECASE)
            if _m_total:
                _resto = _texto_anot[_m_total.end():]
                if not re.search(r"(?:\r?\n|^)\s*ANOTACI[OÓ]N\s+(?:Nro|N[oO]?|:)?\s*\d+",
                                 _resto, re.IGNORECASE):
                    _texto_anot = _texto_anot[:_m_total.end()]
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
            elif "EMBARGO" in sup and "MEDIDA CAUTELAR" not in sup:
                tipo_anot = "GRAVAMEN: Embargo"
            # Medida cautelar DISTINTA del embargo (bug J): inscripción de demanda,
            # prohibición de enajenar, comiso o extinción de dominio no son embargos.
            elif ("MEDIDA CAUTELAR" in sup or "INSCRIPCION DE DEMANDA" in sup
                  or "PROHIBICION" in sup or "PROHIBICIÓN" in sup or "COMISO" in sup
                  or "EXTINCION DE DOMINIO" in sup):
                tipo_anot = "MEDIDA CAUTELAR"
            # Gravamen genérico distinto de hipoteca/embargo (servidumbre, usufructo,
            # u otro gravamen no clasificado). Va DESPUÉS de hipoteca/embargo para no
            # capturar "GRAVAMEN: HIPOTECA" / "GRAVAMEN: EMBARGO" como genérico.
            elif "SERVIDUMBRE" in sup or "USUFRUCTO" in sup or "GRAVAMEN" in sup:
                tipo_anot = "GRAVAMEN"
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
        # Detalle completo (texto crudo) por anotación: lo usa el GPV-F-77 para
        # redactar el tracto sucesivo con escritura/notaría sin re-parsear el PDF.
        res["anotaciones_detalle"] = parsed_anotaciones

        # 5b. Inferir acreedor_snr del CTL (D1 — NLP automático)
        # Extrae el acreedor del gravamen hipotecario más reciente activo
        hipotecas_vigentes = [
            item for item in parsed_anotaciones
            if "GRAVAMEN" in item["tipo"] and "Hipoteca" in item["tipo"]
            and "CANCELADA" not in item["estado"]
        ]
        if hipotecas_vigentes:
            _ult_hip = hipotecas_vigentes[-1]
            partes_hip = _ult_hip["partes"]
            # Las partes tienen formato "De -> A" donde A es el acreedor
            if "->" in partes_hip:
                acreedor_raw = partes_hip.split("->")[-1].strip()
            else:
                acreedor_raw = partes_hip.strip()
            # Fallback al texto completo si el extracto es muy corto
            if len(acreedor_raw) < 4:
                acreedor_raw = _ult_hip["texto"][:80]
            res["acreedor_snr"] = acreedor_raw
            # Fecha y CUANTÍA de la hipoteca vigente (la carga económica 08B debe
            # amortizar desde la CONSTITUCIÓN del crédito — anotación de hipoteca —
            # no desde la apertura del folio, y usar la cuantía declarada en el
            # CTL en vez de un LTV supuesto).
            res["hipoteca_vigente"] = {
                "anotacion": _ult_hip.get("num"),
                "fecha": _ult_hip.get("fecha"),
                "acreedor": res["acreedor_snr"],
                "cuantia_cop": _parsear_cuantia_cop(_ult_hip.get("texto") or ""),
            }
        else:
            res["acreedor_snr"] = None
            res["hipoteca_vigente"] = None
        # acreedor_real se declara externamente o queda None (sin discrepancia)
        res.setdefault("acreedor_real", None)

        # 6. Generar Hallazgos dinamicos (redactados en LENGUAJE CLARO para que
        # cualquier persona entienda qué significa el gravamen y a quién afecta).
        h_idx = 1

        def _acreedor_de(item):
            """Acreedor legible de una anotación de gravamen ('A: BBVA...')."""
            partes = (item.get("partes") or "").strip()
            a = partes.split("->")[-1].strip() if "->" in partes else partes
            if len(a) < 4:
                m = re.search(r"A\s*:\s*([A-Z0-9ÁÉÍÓÚÑ&\.\s]{6,90})",
                              item.get("texto") or "")
                a = m.group(1).strip() if m else ""
            a = re.sub(r"(?:\.?NIT#?\s*[\d]+|N\.?I\.?T\.?\s*[\d]+)", "", a, flags=re.I)
            return " ".join(a.split()).strip(" .,;")

        def _cuantia_de(item):
            m = re.search(
                r"(?:CREDITO INICIAL APROBADO POR|VALOR ACTO|CUANTIA|por\s+valor\s+de)\s*"
                r"\$?\s*([\d]{1,3}(?:[.,][\d]{3})+)", (item.get("texto") or ""), re.IGNORECASE)
            return m.group(1) if m else None

        for item in parsed_anotaciones:
            _tipo_an = item["tipo"]
            # Cargas/graves separados por CATEGORÍA (bug J): hipoteca, embargo,
            # medida cautelar y gravamen genérico se distinguen (no se funden).
            _es_carga = ("GRAVAMEN" in _tipo_an or _tipo_an == "MEDIDA CAUTELAR") \
                and "CANCELADA" not in item["estado"]
            if _es_carga:
                es_hipoteca = "Hipoteca" in _tipo_an
                es_embargo = "Embargo" in _tipo_an
                es_cautelar = _tipo_an == "MEDIDA CAUTELAR"
                acreedor = _acreedor_de(item)
                cuantia = _cuantia_de(item)
                fecha = item.get("fecha") or "N/D"
                extra_acr = (" a favor de {}".format(acreedor)) if acreedor else ""
                extra_mto = (" por {} COP".format(cuantia)) if cuantia else ""
                if es_hipoteca:
                    titulo = "H-0{} | Hipoteca vigente{} (Anot. {})".format(
                        h_idx, extra_acr, item['num'])
                    desc = (
                        "El folio registra una HIPOTECA VIGENTE inscrita el {} (anot. {}){}".format(
                            fecha, item['num'], extra_acr + extra_mto) + ". "
                        "En lenguaje claro: este inmueble esta comprometido como garantia de un "
                        "credito que aun no ha sido cancelado. La hipoteca es una carga que pesa "
                        "sobre la propiedad (no sobre la persona): sigue al inmueble aunque cambie "
                        "de dueno hasta que se pague el credito y se cancele en el registro."
                    )
                    impl = (
                        "Para vender, refinanciar o dar este inmueble en garantia, primero hay que "
                        "gestionar el credito con {} y tramitar la CANCELACION de la hipoteca ante "
                        "la ORIP. No impide ser dueno, pero condiciona cualquier operacion sobre el "
                        "apartamento hasta que el gravamen se levante.".format(
                            acreedor if acreedor else "el banco acreedor")
                    )
                elif es_embargo:
                    titulo = "H-0{} | Embargo vigente{} (Anot. {})".format(
                        h_idx, extra_acr, item['num'])
                    desc = (
                        "El folio registra un EMBARGO VIGENTE inscrito el {} (anot. {}){}".format(
                            fecha, item['num'], extra_acr) + ". "
                        "En lenguaje claro: una autoridad judicial ha ordenado retener o impedir "
                        "la disposicion del inmueble. El embargo NO transfiere la propiedad, pero "
                        "bloquea cualquier venta o gravamen mientras este vigente."
                    )
                    impl = (
                        "Se requiere el levantamiento del embargo mediante orden judicial (pago de "
                        "la obligacion, caución o terminación del proceso) y su cancelacion en el "
                        "registro antes de disponer o gravar el inmueble."
                    )
                elif es_cautelar:
                    titulo = "H-0{} | Medida cautelar vigente (Anot. {})".format(
                        h_idx, item['num'])
                    desc = (
                        "El folio registra una MEDIDA CAUTELAR VIGENTE inscrita el {} (anot. {}): "
                        "{}. En lenguaje claro: existe una orden judicial (p. ej. inscripcion de "
                        "demanda, prohibicion de enajenar, comiso o extincion de dominio) que "
                        "restringe la libre disposicion del inmueble.".format(
                            fecha, item['num'], (item.get('texto') or '')[:120])
                    )
                    impl = (
                        "La medida cautelar restringe la disposicion del inmueble hasta su "
                        "levantamiento por orden judicial. Verificar el proceso que la origina y "
                        "tramitar su cancelacion antes de cualquier operacion."
                    )
                else:
                    # Gravamen genérico (servidumbre, usufructo u otro).
                    titulo = "H-0{} | Gravamen vigente (Anot. {})".format(h_idx, item['num'])
                    desc = (
                        "El folio registra un GRAVAMEN VIGENTE inscrito el {} (anot. {}): {}. "
                        "En lenguaje claro: existe una carga real (p. ej. servidumbre o usufructo) "
                        "que limita el dominio o su uso y debe tenerse en cuenta.".format(
                            fecha, item['num'], (item.get('texto') or '')[:120])
                    )
                    impl = (
                        "Verificar la naturaleza del gravamen y su vigencia; segun el caso, "
                        "tramitar su cancelacion o asumirlo como carga real que acompanara al "
                        "inmueble en cualquier operacion."
                    )
                res["hallazgos"].append(("ALTO", C_ROJO, C_RIESGO_BG, titulo,
                                         "SNR Registral", desc, impl))
                res["recs"].append((
                    "R-0{} | Cancelacion/levantamiento Anot. {}".format(h_idx, item['num']),
                    "Tramitar con {} el levantamiento o cancelacion de la carga y registrarla "
                    "en el folio SNR para dejar el inmueble libre.".format(
                        acreedor if acreedor else "la autoridad/entidad competente")
                ))
                h_idx += 1
            elif "LIMITACION" in item["tipo"] and "CANCELADA" not in item["estado"]:
                res["hallazgos"].append((
                    "MEDIO", C_NARANJA, C_ALERTA_BG,
                    "H-0{} | Afectacion/Limitacion Vigente (Anot. {})".format(h_idx, item['num']),
                    "SNR Registral",
                    "El folio registra una limitacion al dominio (anot. {}): {}. En lenguaje claro: "
                    "el inmueble tiene una restriccion legal (p. ej. afectacion a vivienda familiar) "
                    "que exige el consentimiento de las personas protegidas para venderlo o "
                    "traspasarlo.".format(item['num'], (item.get('texto') or '')[:160]),
                    "Vender o aportar el inmueble requiere el levantamiento de la limitacion con la "
                    "participacion de los titulares/beneficiarios ante notaria."
                ))
                res["recs"].append((
                    "R-0{} | Levantamiento de Limitacion Anot. {}".format(h_idx, item['num']),
                    "Tramitar la desafectacion/levantamiento de la limitacion mediante escritura "
                    "publica conjunta y su registro en el folio SNR."
                ))
                h_idx += 1

        # Si no hay hallazgos de alerta, tradicion limpia
        if not res["hallazgos"]:
            res["hallazgos"].append((
                "INFORMATIVO", C_VERDE, C_OK_BG,
                "H-01 | Tradicion Registral Libre de Gravamenes Activos",
                "SNR -- Tradicion",
                "Se analizaron todas las anotaciones del folio y NO se encontraron hipotecas, "
                "embargos ni afectaciones vigentes. En lenguaje claro: el inmueble aparece libre "
                "de cargas registradas.",
                "Favorable para vender, dar en garantia o estructurar operaciones sin restricciones "
                "registrales (sujeto a verificar el paz y salvo de impuestos)."
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

    # Texto completo del CTL (para inferencias como condición jurídica PH/No PH)
    res["texto_ctl"] = texto[:30000] if texto else None

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

# -*- coding: utf-8 -*-
"""
ARHIAX RE — Generador Dinámico de Ruta de Verificación Profesional
Bloque 4 Sprint 1

Genera una lista de pasos concretos y ordenados para el profesional
del derecho o estructurador que debe cerrar los hallazgos del informe.

La ruta se genera automáticamente a partir de los hallazgos activos.
Es estática (PDF) — no mantiene estado entre sesiones.
"""


# ── Catálogo de pasos por tipo de hallazgo ────────────────────────────────────
# Cada entrada define un paso de verificación que se activa cuando
# el hallazgo correspondiente está presente en el informe.

_CATALOGO_PASOS = [
    {
        "trigger": "ausencia_ctl",
        "numero_base": 1,
        "descripcion": (
            "Solicitar el Certificado de Tradición y Libertad (CTL) actualizado "
            "(no mayor a 30 días) para la matrícula inmobiliaria en la Ventanilla "
            "Única de Registro (VUR) del SNR: ventanillaunicaregistry.supernotariado.gov.co. "
            "Ningún proceso de debida diligencia puede avanzar sin este insumo."
        ),
        "actor": "Propietario / Estructurador",
        "plazo": "Inmediato (máx. 48 horas)",
        "fuente": "SNR — VUR",
    },
    {
        "trigger": "hipoteca_vigente",
        "numero_base": 2,
        "descripcion": (
            "Solicitar extracto oficial del crédito hipotecario al banco acreedor "
            "registrado en el SNR. Verificar: saldo insoluto, cuota mensual, "
            "fecha de vencimiento, tasa vigente y cláusulas de prepago. "
            "Si el acreedor declarado difiere del SNR, ver Paso de Cesión."
        ),
        "actor": "Titular / Estructurador Financiero",
        "plazo": "5 días hábiles",
        "fuente": "Banco Acreedor (extracto oficial)",
    },
    {
        "trigger": "cesion_no_registrada",
        "numero_base": 3,
        "descripcion": (
            "Verificar con el banco cesionario (acreedor real declarado) "
            "la existencia y términos de la cesión de cartera. Solicitar: "
            "(i) certificación de la cesión, (ii) paz y salvo de la obligación "
            "cedida. Tramitar ante la ORIP la inscripción de la cesión en el folio "
            "de matrícula inmobiliaria para alinear el registro público con la "
            "realidad operativa del crédito."
        ),
        "actor": "Banco Cesionario + Profesional del Derecho",
        "plazo": "10 días hábiles",
        "fuente": "ORIP — Escritura pública de cesión",
    },
    {
        "trigger": "afectacion_vivienda",
        "numero_base": 4,
        "descripcion": (
            "Si se pretende transferir el dominio o aportar el activo a un "
            "fideicomiso: obtener el levantamiento de la afectación a vivienda "
            "familiar mediante escritura pública suscrita por AMBOS titulares "
            "(Anot. correspondiente). El levantamiento debe inscribirse en el ORIP. "
            "Sin este requisito, cualquier acto de disposición es nulo de pleno derecho."
        ),
        "actor": "Ambos titulares + Notaría + ORIP",
        "plazo": "15 días hábiles",
        "fuente": "Ley 258/1996 — Escritura pública de levantamiento",
    },
    {
        "trigger": "patrimonio_familia",
        "numero_base": 5,
        "descripcion": (
            "Verificar el régimen de patrimonio de familia inembargable. "
            "Si se pretende ejecutar una garantía o transferir el dominio: "
            "obtener resolución judicial o notarial de desafectación conforme "
            "a la Ley 70/1931 y sus modificaciones. El activo es inembargable "
            "por acreedores distintos al acreedor hipotecario de adquisición."
        ),
        "actor": "Profesional del Derecho + Juzgado/Notaría",
        "plazo": "30 días hábiles (proceso judicial)",
        "fuente": "Ley 70/1931 — ORIP",
    },
    {
        "trigger": "embargo_vigente",
        "numero_base": 6,
        "descripcion": (
            "Identificar el proceso judicial que originó el embargo (número de "
            "radicado, juzgado, acreedor demandante). Evaluar con abogado litigante "
            "las opciones: (i) pago de la obligación y solicitud de levantamiento, "
            "(ii) sustitución de garantía, (iii) nulidad procesal si corresponde. "
            "El embargo bloquea cualquier acto de disposición del bien."
        ),
        "actor": "Abogado Litigante + Juzgado",
        "plazo": "Variable según proceso judicial",
        "fuente": "Juzgado competente — ORIP",
    },
    {
        "trigger": "discrepancia_pot",
        "numero_base": 7,
        "descripcion": (
            "Verificar con la Curaduría Urbana de {ciudad} la licencia de "
            "construcción del proyecto, confrontando el polígono de tratamiento "
            "urbanístico aplicable y la altura máxima permitida. Si existe "
            "discrepancia entre lo construido y la norma vigente, evaluar riesgo "
            "de contingencia urbanística con el curador competente."
        ),
        "actor": "Curaduría Urbana / Planeación de {ciudad}",
        "plazo": "15 días hábiles",
        "fuente": "POT {ciudad} — Licencia de construcción",
    },
    {
        "trigger": "riesgo_geoespacial",
        "numero_base": 8,
        "descripcion": (
            "Solicitar concepto geotécnico de un ingeniero civil certificado "
            "para el predio. La intersección con zonas de amenaza del POT "
            "puede generar: recargos en pólizas de seguros, restricciones para "
            "originación hipotecaria y condicionamientos para licencias de "
            "construcción futuras. El concepto debe adjuntarse al expediente."
        ),
        "actor": "Ingeniero Geotécnico Certificado",
        "plazo": "20 días hábiles",
        "fuente": "POT {ciudad} — Capas oficiales de gestión del riesgo (evaluación ARHIAX)",
    },
    {
        "trigger": "sarlaft_pendiente",
        "numero_base": 9,
        "descripcion": (
            "Ejecutar verificación SARLAFT formal cruzando la identidad de "
            "los titulares y el acreedor contra: (i) listas OFAC, ONU, "
            "(ii) listas UIAF-Colombia, (iii) bases de datos de PEP "
            "(Personas Expuestas Políticamente). Esta verificación es "
            "obligatoria antes de cualquier desembolso o apertura de negocio."
        ),
        "actor": "Oficial de Cumplimiento / UIAF",
        "plazo": "2 días hábiles",
        "fuente": "SARLAFT — Plataforma externa de listas restrictivas",
    },
]


def generar_ruta(hallazgos, nombre_ciudad="Barranquilla"):
    """Genera la ruta de verificación a partir de los hallazgos activos.

    Args:
        hallazgos: Lista de dicts con al menos la key 'tipo'.
                   Ejemplo: [{"tipo": "hipoteca_vigente", "referencia": "Anot. 007"}]
        nombre_ciudad: Nombre de la ciudad del caso (los pasos de norma
                   urbanística se redactan con la ciudad correcta; antes
                   'Barranquilla' se filtraba en dictámenes de otras ciudades).

    Returns:
        Lista de pasos ordenados (dicts). Lista vacía si no hay hallazgos
        que requieran verificación (activo limpio).
    """
    if not hallazgos:
        return []

    # Normalizar tipos de hallazgos presentes
    tipos_presentes = {h.get("tipo", "").lower().strip() for h in hallazgos}
    referencias = {h.get("tipo", ""): h.get("referencia", "") for h in hallazgos}

    pasos = []
    numero_secuencial = 1

    for plantilla in _CATALOGO_PASOS:
        trigger = plantilla["trigger"]
        if trigger in tipos_presentes:
            paso = {
                "numero": numero_secuencial,
                "trigger": trigger,
                "descripcion": plantilla["descripcion"].format(ciudad=nombre_ciudad),
                "actor": plantilla["actor"].format(ciudad=nombre_ciudad),
                "plazo": plantilla["plazo"],
                "fuente": plantilla["fuente"].format(ciudad=nombre_ciudad),
                "referencia_hallazgo": referencias.get(trigger, ""),
            }
            pasos.append(paso)
            numero_secuencial += 1

    return pasos


def generar_tabla_ruta(ruta, fmt_label=None):
    """Convierte la ruta en filas para tabla PDF.

    Args:
        ruta:      Lista de pasos de generar_ruta().
        fmt_label: Función de formato para el label del paso (opcional).

    Returns:
        Lista de (paso_label, descripcion, actor, plazo) para renderizado.
    """
    if not ruta:
        return []

    filas = []
    for paso in ruta:
        label = f"Paso {paso['numero']}"
        if paso.get("referencia_hallazgo"):
            label += f" [{paso['referencia_hallazgo']}]"
        filas.append((
            label,
            paso["descripcion"],
            paso["actor"],
            paso["plazo"],
        ))
    return filas

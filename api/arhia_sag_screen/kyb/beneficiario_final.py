"""Derivación y reporte de beneficiario final (Colombia) — estructura del RUB.

El Registro Único de Beneficiarios Finales (RUB) exige identificar a la(s) persona(s)
natural(es) que en última instancia poseen o controlan a la entidad. Criterios (referente
normativo):
  - Participación: >= umbral (5%) de capital.
  - Control efectivo: C.Com. arts. 260/261 (control societario) + ET art. 260-1.
  - Regla subsidiaria: si no se identifica persona natural, se reporta el representante legal.
Se distingue beneficiario **directo** e **indirecto** (vía cadena de sociedades intermedias).
"""
from ..contracts import BeneficiarioFinal

# Umbral de beneficiario final en Colombia (DIAN/RUB): 5% o más.
UMBRAL_BF = 0.05

_BASE_PARTICIPACION = "Criterio de participación >= {pct}% (RUB; C.Com. arts. 260/261; ET art. 260-1)."
_BASE_SUBSIDIARIA = ("Regla subsidiaria: al no identificarse persona natural con participación >= umbral "
                     "ni control efectivo, se reporta al representante legal.")


def derivar_beneficiario_final(registro, umbral=UMBRAL_BF, fecha="", pais=""):
    """Devuelve los beneficiarios finales directos (o subsidiario) del registro."""
    accionistas = [a for a in registro.composicion_accionaria if a.participacion >= umbral]
    if accionistas:
        return tuple(
            BeneficiarioFinal(
                tipo_documento=a.tipo_documento,
                numero_documento=a.numero_documento,
                nombre=a.nombre,
                participacion=round(a.participacion, 4),
                criterio="participacion",
                pais_residencia=pais,
                fecha_adquisicion=fecha,
                vinculo="socio",
                calidad="directo",
                base_legal=_BASE_PARTICIPACION.format(pct=int(round(umbral * 100))),
            )
            for a in accionistas
        )
    # Regla subsidiaria: representante legal cuando no hay persona natural identificable.
    if registro.representante_legal:
        return (
            BeneficiarioFinal(
                nombre=registro.representante_legal,
                criterio="representante_legal_subsidiario",
                limitacion="sin accionista >= umbral; verificar control efectivo y regla subsidiaria",
                pais_residencia=pais,
                fecha_adquisicion=fecha,
                vinculo="representante_legal",
                calidad="directo",
                base_legal=_BASE_SUBSIDIARIA,
            ),
        )
    return (
        BeneficiarioFinal(limitacion="sin composición accionaria ni representante legal; verificar control efectivo",
                          criterio="sin_identificar",
                          base_legal="Sin beneficiario por participación ni regla subsidiaria; verificar control efectivo (C.Com. 260/261; ET 260-1)."),
    )


def _es_juridica(accionista):
    return str(accionista.tipo_documento or "").lower() in ("nit", "n.i.t", "juridica")


def reporte_rub(registro, *, sociedades=None, umbral=UMBRAL_BF, fecha="", pais="",
                grupos_control=None, umbral_control=0.50):
    """Construye el reporte RUB (corrección P1-1): resolución **recursiva** del grafo societario.

    - Recorre la cadena de sociedades intermedias (con detección de ciclos).
    - **Agrega** la participación de una misma persona natural por múltiples rutas.
    - Criterios: **participación** directa/indirecta (>= umbral) y **control conjunto/efectivo**
      (personas que actúan en concierto y en conjunto superan ``umbral_control``, o un controlante
      con mayoría — C.Com. 260/261; ET 260-1). ``grupos_control`` es un análisis **opt-in** que el
      oficial aporta (grupo de vinculados en concierto); sin él el motor no lo presume.
    - Regla subsidiaria solo si no se identifica persona natural. Salida con limitaciones y rutas.
    """
    sociedades = sociedades or {}
    acumulado = {}
    visitados = set()
    ciclo_detectado = False

    def acumular(a, factor, calidad, ruta):
        if not a.nombre:
            return
        base = (a.tipo_documento, a.numero_documento, a.nombre)
        cur = acumulado.get(base)
        if cur is None:
            cur = {"tipo_documento": a.tipo_documento, "numero_documento": a.numero_documento,
                   "nombre": a.nombre, "participacion": 0.0, "criterios": set(), "calidades": set(),
                   "rutas": set()}
            acumulado[base] = cur
        cur["participacion"] += factor
        cur["criterios"].add("participacion" if calidad == "directo" else "participacion_indirecta")
        cur["calidades"].add(calidad)
        cur["rutas"].add("->".join(ruta))

    def resolver(reg, factor, calidad, ruta):
        nonlocal ciclo_detectado
        if reg.nit in visitados:
            ciclo_detectado = True
            return
        visitados.add(reg.nit)
        for a in reg.composicion_accionaria:
            if a.participacion <= 0:
                continue
            f = factor * a.participacion
            if _es_juridica(a) and a.numero_documento in sociedades:
                resolver(sociedades[a.numero_documento], f, "indirecto", ruta + (a.numero_documento,))
            elif not _es_juridica(a):
                acumular(a, f, ("directo" if not ruta else "indirecto"), ruta)
        visitados.remove(reg.nit)

    resolver(registro, 1.0, "directo", ())

    # Control conjunto: grupos aportados por el oficial que en conjunto superan umbral_control.
    flag_conjunto = {}
    if grupos_control:
        for etiqueta, claves in grupos_control.items():
            total = 0.0
            presentes = []
            for clave in claves:
                cur = acumulado.get(clave)
                if cur is not None:
                    presentes.append(clave)
                    total += cur["participacion"]
            if presentes and total >= umbral_control:
                for clave in presentes:
                    flag_conjunto.setdefault(clave, set()).add(etiqueta)

    pct_txt = int(round(umbral * 100))
    base_part = _BASE_PARTICIPACION.format(pct=pct_txt)
    base_control = ("Control efectivo / control conjunto de vinculados que actúan en concierto "
                    "(C.Com. arts. 260/261; ET art. 260-1).")
    reporte = []
    for cur in acumulado.values():
        clave = (cur["tipo_documento"], cur["numero_documento"], cur["nombre"])
        grupos = flag_conjunto.get(clave, set())
        participacion = cur["participacion"]
        es_indirecto = "indirecto" in cur["calidades"]
        # Filtro: persona natural que es BF por participación, control conjunto o control efectivo.
        if participacion >= umbral:
            criterio = "participacion"
        elif grupos:
            criterio = "control_conjunto"
        else:
            continue  # por debajo de umbral y sin control: no es BF
        limitaciones = []
        if len(cur["rutas"]) > 1:
            limitaciones.append("participación agregada por múltiples rutas")
        if participacion > umbral_control:
            limitaciones.append(f"control efectivo por mayoría ({participacion:.0%})")
        if grupos:
            limitaciones.append("control conjunto de vinculados en concierto (" + " + ".join(sorted(grupos)) + ")")
        reporte.append({
            "tipo_documento": cur["tipo_documento"], "numero_documento": cur["numero_documento"],
            "nombre": cur["nombre"], "participacion": round(min(participacion, 1.0), 4),
            "criterio": criterio,
            "vinculo": "socio", "calidad": "indirecto" if es_indirecto else "directo",
            "pais_residencia": pais, "fecha_adquisicion": fecha,
            "limitacion": "; ".join(limitaciones) if limitaciones else None,
            "base_legal": base_part if criterio == "participacion" else base_control,
            "rutas": sorted(cur["rutas"])})

    if not reporte:
        if registro.representante_legal:
            reporte.append({"tipo_documento": None, "numero_documento": None, "nombre": registro.representante_legal,
                            "participacion": 0.0, "criterio": "representante_legal_subsidiario", "vinculo": "representante_legal",
                            "calidad": "directo", "pais_residencia": pais, "fecha_adquisicion": fecha,
                            "limitacion": "sin accionista >= umbral ni control identificado", "base_legal": _BASE_SUBSIDIARIA})
        else:
            reporte.append({"tipo_documento": None, "numero_documento": None, "nombre": "", "participacion": 0.0,
                            "criterio": "sin_identificar", "vinculo": "", "calidad": "",
                            "pais_residencia": "", "fecha_adquisicion": fecha,
                            "limitacion": "verificar control efectivo (C.Com. 260/261; ET 260-1)",
                            "base_legal": "Sin persona natural identificable; verificar control efectivo."})
    if ciclo_detectado and reporte:
        reporte[0] = {**reporte[0], "limitacion": (reporte[0].get("limitacion") or "") + "; cadena con ciclo detectado"}
    return reporte

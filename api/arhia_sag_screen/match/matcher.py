"""Motor de consulta multi-atributo.

Estados del resultado (de mayor a menor severidad):
    - ``coincidencia``   : confirmada por documento exacto, o por nombre fuerte CORROBORADO
                           por un atributo independiente del mismo registro (alias/token-sort).
    - ``candidato``      : nombre fuerte (>= umbral_alerta) SIN corroboración independiente.
      Es una señal PROBABLE que exige revisión humana antes de confirmar (Fase 1 de auditoría).
    - ``revisionManual`` : nombre moderado (en [umbral_revision, umbral_alerta)).
    - ``sinCoincidencia``: sin evidencia.

La corroboración evita falsos positivos de "nombre común": un solo atributo coincidente
(igual que un apellido popular) se deja como ``candidato``; dos atributos independientes del
mismo registro que coinciden confirman ``coincidencia``.
"""
import difflib

from ..contracts import ResultadoConsulta
from ..normalize.docs import normalize_documento
from ..normalize.names import normalize_name, token_sort


def consultar(contraparte, registros, lista, lista_version, lista_hash,
              umbral_alerta=0.90, umbral_revision=0.80):
    tipo, num = normalize_documento(contraparte.tipo_documento, contraparte.numero_documento)
    if num:
        for r in registros:
            if r.numero_documento and r.numero_documento == num:
                if tipo is None or r.tipo_documento is None or r.tipo_documento == tipo:
                    return _res(contraparte.contraparte_id, lista, lista_version, lista_hash,
                                "coincidencia", 1.0, ("documento",), r.id)
    mejor = _mejor_nombre(contraparte.nombre, registros)
    if mejor is not None:
        r, score, attr = mejor
        if score >= umbral_alerta:
            if _corrobora(contraparte.nombre, r, umbral_alerta):
                campos = ("nombre", attr, "corroborado")
                return _res(contraparte.contraparte_id, lista, lista_version, lista_hash,
                            "coincidencia", score, campos, r.id)
            # Nombre fuerte pero sin atributo independiente que lo confirme -> probable.
            return _res(contraparte.contraparte_id, lista, lista_version, lista_hash,
                        "candidato", score, ("nombre", attr), None)
        if score >= umbral_revision:
            return _res(contraparte.contraparte_id, lista, lista_version, lista_hash,
                        "revisionManual", score, ("nombre", attr), None)
    return _res(contraparte.contraparte_id, lista, lista_version, lista_hash,
                "sinCoincidencia", 0.0, (), None)


def _mejor_nombre(nombre, registros):
    target = normalize_name(nombre)
    mejor = None
    for r in registros:
        for attr, cand in (("nombre", r.nombre),) + tuple(("alias", a) for a in r.alias):
            if not cand:
                continue
            score = difflib.SequenceMatcher(None, target, normalize_name(cand)).ratio()
            if mejor is None or score > mejor[1]:
                mejor = (r, score, attr)
    return mejor


def _corrobora(nombre, r, umbral_alerta):
    """Señal adicional del mismo registro que CONFIRMA el match de nombre.

    ``candidato`` (una única señal fuerte) se convierte en ``coincidencia`` si el mismo registro
    aporta una segunda evidencia independiente:
        (a) conjuntos de tokens equivalentes del nombre principal (nombre normalizado),
        (b) un atributo registrado (nombre o alias) coincide EXACTAMENTE (ratio ~1.0), o
        (c) dos atributos distintos del registro coinciden con fuerza (>= umbral_alerta).
    """
    tq = normalize_name(nombre)
    if token_sort(nombre) == token_sort(r.nombre):
        return True
    ratios = []
    if r.nombre:
        ratios.append(difflib.SequenceMatcher(None, tq, normalize_name(r.nombre)).ratio())
    for a in r.alias:
        if a:
            ratios.append(difflib.SequenceMatcher(None, tq, normalize_name(a)).ratio())
    if any(x >= 0.999 for x in ratios):
        return True
    fuertes = [x for x in ratios if x >= umbral_alerta]
    return len(fuertes) >= 2


def _res(cid, lista, lv, lh, resultado, score, campos, coinc_id):
    return ResultadoConsulta(
        contraparte_id=cid, lista=lista, lista_version=lv, lista_hash=lh,
        resultado=resultado, score=round(score, 4), matched_fields=campos,
        coincidencia_id=coinc_id,
    )

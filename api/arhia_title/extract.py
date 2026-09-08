"""Motor documental: extrae hechos del Informe Base LAI (texto) → Caso estructurado."""
import re

from .contracts import Avaluo, Caso, Predio


def _campo(texto, patron):
    m = re.search(patron, texto)
    return m.group(1).strip() if m else ""


def _num(s):
    s = (s or "").replace("$", "").replace(" ", "")
    try:
        return float(s.replace(".", "").replace(",", "."))
    except ValueError:
        return None


def extraer_caso(texto, id_caso, anotaciones=()):
    m_area = re.search(r"Area Registrada\s*([\d.]+)\s*m2 \(registral\) / ([\d.]+)\s*m2 \(catastral\)", texto)
    area_reg = float(m_area.group(1)) if m_area else 0.0
    area_cat = float(m_area.group(2)) if m_area else 0.0
    valor = _num(_campo(texto, r"Valor Comercial Consolidado\s*\$?\s*([\d.,]+)"))
    amenazas = tuple(sorted(set(a.upper() for a in re.findall(r"AMENAZA\s+(ALTA|MEDIA|BAJA)", texto, re.IGNORECASE))))
    sarlaft = "pendiente" if re.search(r"PENDIENTE VERIFICACI", texto) else ""
    return Caso(
        id=id_caso,
        tipo="informe_base",
        predio=Predio(
            folio_matricula=_campo(texto, r"Matricula Inmobiliaria\s*(\d{3}-\d+)"),
            codigo_catastral=_campo(texto, r"Codigo catastral\s*(\d+)"),
            direccion=_campo(texto, r"Direccion oficial\s*(.+)"),
            area_registral=area_reg,
            area_catastral=area_cat,
        ),
        anotaciones=anotaciones,
        avaluo=Avaluo(valor=valor) if valor else None,
        titular=_campo(texto, r"Titulares vigentes\s*(.+)"),
        amenazas=amenazas,
        sarlaft_estado=sarlaft,
    )

"""Parser del informe "10.000 empresas más grandes de Colombia" (Supersociedades SIIS).

El informe real comienza con filas de título (ej. "BASE SUPERFINANCIERA", "Miles de pesos")
antes de la fila de encabezados. Este parser busca automáticamente la fila que contiene
"NIT" y "RAZON SOCIAL" y mapea por palabra clave (robusto a sufijos de año y asteriscos).
La columna SUPERVISOR indica la superintendencia que vigila a la empresa (SUPERFINANCIERA
= régimen SARLAFT; SUPERSOCIEDADES/Superservicios = otros).
"""
import csv
import io
import re
import unicodedata
from typing import Dict

from ..contracts import RegistroJuridico

COLUMN_KEYWORDS: Dict[str, str] = {
    "nit": "nit",
    "razon_social": "razon social",
    "supervisor": "supervisor",
    "ciiu": "ciiu",
    "macrosector": "macrosector",
    "ingresos": "ingresos operacionales",
    "activos": "activo",
    "patrimonio": "patrimonio",
    "utilidad": "ganancia",
    "departamento": "departamento",
}


def _norm(s):
    nfd = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn").strip().lower()


def _build_header_index(fieldnames):
    return {_norm(f): f for f in fieldnames if f is not None}


def _get(row, header_index, field):
    keyword = COLUMN_KEYWORDS.get(field)
    if keyword is None:
        return None
    for norm_header, original in header_index.items():
        if norm_header == keyword and original in row:
            return row[original]
    for norm_header, original in header_index.items():
        if keyword in norm_header and original in row:
            return row[original]
    return None


def _parse_number(value):
    """Convierte '$ 100.000.000.000' / '1.234,56' a float. None si no parsea."""
    if value is None:
        return None
    s = str(value).strip().replace("$", "").replace(" ", "").replace("'", "")
    if not s:
        return None
    s2 = s.replace(".", "").replace(",", ".")
    try:
        return float(s2)
    except ValueError:
        try:
            return float(re.sub(r"[^0-9.\-]", "", s))
        except ValueError:
            return None


def _detect_delimiter(sample):
    """Elige ';' / ',' / tab por frecuencia (más robusto que Sniffer en CSVs cortos)."""
    counts = {d: sample[:4000].count(d) for d in (",", ";", "\t")}
    d = max(counts, key=counts.get)
    return d if counts[d] > 0 else ";"


def parse_rows(rows, fieldnames):
    header_index = _build_header_index(fieldnames)
    out = []
    for row in rows:
        nit = _get(row, header_index, "nit")
        razon = _get(row, header_index, "razon_social") or ""
        if not nit and not razon:
            continue
        out.append(RegistroJuridico(
            nit=nit or "",
            razon_social=razon,
            sector=_get(row, header_index, "ciiu") or _get(row, header_index, "macrosector") or "",
            ingresos=_parse_number(_get(row, header_index, "ingresos")),
            activos=_parse_number(_get(row, header_index, "activos")),
            vigilada_por=(_get(row, header_index, "supervisor") or "").upper(),
            fuente="supersociedades-siis",
        ))
    return out


def parse_csv(texto, delimiter=None):
    sample = texto[:8192]
    if delimiter is None:
        delimiter = _detect_delimiter(sample)
    rows = list(csv.reader(io.StringIO(texto), delimiter=delimiter))
    hdr_idx = 0
    for i, row in enumerate(rows):
        joined = " ".join(_norm(c) for c in row if c)
        if "nit" in joined and "razon social" in joined:
            hdr_idx = i
            break
    else:
        return []
    header = rows[hdr_idx]
    data = []
    for row in rows[hdr_idx + 1:]:
        d = {header[c]: row[c] for c in range(min(len(header), len(row)))}
        data.append(d)
    return parse_rows(data, header)


_INDICE_CACHE: Dict[str, Dict[str, RegistroJuridico]] = {}


def leer_archivo(path: str):
    with open(path, encoding="utf-8-sig") as f:
        return parse_csv(f.read())


def indexar(registros):
    return {r.nit: r for r in registros if r.nit}


def obtener_indice(path: str) -> Dict[str, RegistroJuridico]:
    """Devuelve el índice NIT -> RegistroJuridico, cacheado por ruta."""
    if path not in _INDICE_CACHE:
        _INDICE_CACHE[path] = indexar(leer_archivo(path))
    return _INDICE_CACHE[path]


def buscar_por_nit(path: str, nit: str) -> RegistroJuridico:
    """Devuelve el RegistroJuridico del NIT, o None si no está en el informe SIIS."""
    if not nit:
        return None
    return obtener_indice(path).get(str(nit).strip())

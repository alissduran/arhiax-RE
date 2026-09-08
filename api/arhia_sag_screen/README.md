# arhia_sag_screen — Motor de screening de listas (F1b)

Primer slice de Fase 1: ingesta ONU + OFAC, normalización, matching y evidencia 9.22.

## Estructura
- `contracts.py` — dataclasses (Contraparte, ListaVersion, RegistroNormalizado, ResultadoConsulta).
- `normalize/` — transliteración, Soundex, metáfono, normalización de nombres y documentos.
- `ingest/` — catálogo de listas + parsers XML de ONU y OFAC.
- `match/` — motor de consulta (exacto por documento + fuzzy por nombre).
- `evidence/` — hashing sha256 + construcción del evento `LISTA_CONSULTADA` (SAG-C03).

## Tests
```
py -m unittest discover -s arhia_sag_screen/tests -t . -v
```

## Estado
Fase 1 (ONU + OFAC). Pendiente: ingesta programada (T8), índice persistente, y Fase 2 (KYB bulk + antecedentes).

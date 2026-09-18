# INPUT_DIFF — 040-646406

Comparación de variables entre BASELINE A (dictus anterior) y BASELINE B (dictus actual).

| Variable | Anterior | Actual | Same? | Source | First transformation |
| --- | --- | --- | --- | --- | --- |
| folio | 040-646406 | 040-646406 | SAME | CTL | — |
| direccion_raw (CTL) | TV 43 # 100-50 TO 8 AP 430 | TV 43 # 100-50 | CHANGED | legal_analyzer | `re.split` de unidad (legal_analyzer.py:290-293) |
| torre | TO 8 | (ausente) | CHANGED | perdida en extracción | legal_analyzer.py:291-293 |
| apartamento | AP 430 | (ausente) | CHANGED | perdida en extracción | legal_analyzer.py:291-293 |
| barrio | Miramar | PENDIENTE DE VERIFICACIÓN | CHANGED | catastro (entorno) | resolución catastral degradada |
| ciudad | barranquilla | barranquilla | SAME | Case | — |
| lat/lon | (predio exacto) | (punto por dirección sin unidad) | CHANGED | geocoder | dirección sin unidad |
| NUPRE | UNKNOWN | UNKNOWN | UNKNOWN | CTL | — |
| codigo_catastral | UNKNOWN | UNKNOWN | UNKNOWN | CTL | — |
| destino_economico | Habitacional | PENDIENTE | CHANGED | catastro (predio) | fallback 5 features |
| tipologia | Uso Habitacional | PENDIENTE DE VERIFICACIÓN | CHANGED | dictamen_data | destino no resuelto |
| condicion_juridica | Propiedad Horizontal | (degradada) | CHANGED | catastro/CTL | predio no exacto |
| estrato | 4 | No aplica / uso no residencial | CHANGED | catastro (entorno) | predio no exacto |
| area_registral | 58.75 m² | 58.75 m² | SAME | CTL | — |
| area_catastral | UNKNOWN | UNKNOWN | UNKNOWN | catastro | — |
| coeficiente_PH | UNKNOWN | UNKNOWN | UNKNOWN | CTL | — |
| sector_geoeconomico | Miramar | (fallback estrato 4) | CHANGED | dictamen_data | barrio vacío |
| precio_m2 | 6.800.000 | 5.200.000 | CHANGED | dictamen_data | sector → estrato fallback |

**Conclusión de input:** la única variable material que cambió en la entrada a
valoración es `barrio` (y por lo tanto `precio_m2`), y su causa es la pérdida de la
unidad en la dirección (`direccion_raw`), que degradó la resolución catastral.

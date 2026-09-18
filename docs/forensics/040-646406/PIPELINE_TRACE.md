# PIPELINE_TRACE — 040-646406

Traza de extremo a extremo. Se marca el primer punto de divergencia (FDP).

```text
CTL/PDF (folio 040-646406, "TV 43 # 100-50 TO 8 AP 430")
  ↓
raw extraction (legal_analyzer.analizar_certificado)
  ↓
normalized extraction (legal_analyzer.py:289-299)
  ↓  ← FIRST_DIVERGENCE_POINT
  ↓  re.split descarta APARTAMENTO/AP/TORRE -> "TV 43 # 100-50"
  ↓
Case (dictamenes.direccion = "Pendiente" inicial; NO contiene torre/AP)
  ↓
canonical property identity (api/canonical.py)  [solo Pasto/nomenclatura; BAQ no]
  ↓
catastro resolution (catastro_predio.enriquecer_desde_ctl / por punto)
  ↓  ← degradada: sin unidad, la resolución ya no identifica el predio exacto
  ↓     (dictus actual muestra 5 features)
  ↓
geocoding (geocoder) sobre dirección sin unidad
  ↓
market context: barrio Miramar -> PENDIENTE; destino Habitacional -> PENDIENTE
  ↓
valuation inputs: precio/m² 6.8M -> 5.2M (fallback estrato 4)
  ↓
M1 = area × precio/m² × 1.02  → 407.49M → 311.61M
M3 = renta/cap, renta = area × precio/m² × 0.00538 → 446.7M → 341.6M
  ↓
consolidated = area × precio/m² (M1 100%) → 399.5M → 305.5M
  ↓
Dictus
```

## FIRST_DIVERGENCE_POINT

- **Archivo:** `api/legal_analyzer.py`
- **Función:** `analizar_texto_certificado` (bloque de "DIRECCION DEL INMUEBLE")
- **Líneas:** 289-299 (en concreto el `re.split` de 291-293)
- **Commit:** `f247a20` "Direccion oficial: preferir la DIRECCION CATASTRAL del CTL (Bogota real)"
- **Transformación:** `"TV 43 # 100-50 TO 8 AP 430"` → `"TV 43 # 100-50"`

El FDP es causal: al perder la unidad, toda la cadena downstream (catastro → barrio →
precio/m²) se degrada. No es un problema de geocoding ni de render; es la extracción
de dirección que descarta la unidad.

# Criterios de Aceptación — Motor TMA + Capa Lonja BAQ v1.0

**Sinergia Consulting Group S.A.S.**
**Versión:** 1.0
**Fecha:** 07 de mayo de 2026
**Para:** Alisson (validación técnica), Marcelo (verificación post-instalación)

---

## Para qué este documento

Este archivo lista los **criterios verificables** que se deben cumplir después de instalar el paquete para considerarlo correctamente operativo. Son 12 criterios organizados en 4 niveles. Si los 12 se cumplen, el paquete está listo para operar.

Hay tres niveles de prioridad:

- **CA-CRÍTICO (5):** sin esto no se puede operar bajo ninguna circunstancia.
- **CA-ESENCIAL (4):** sin esto el dictamen no es válido como avalúo corporativo.
- **CA-DESEABLE (3):** mejora trazabilidad pero no bloquea operación.

---

## Nivel 1 — Instalación correcta

### CA-1 (CRÍTICO) — Python disponible y versión correcta

**Verificación:**
```bash
python3 --version
```

**Criterio de aceptación:** salida que indica `Python 3.10.x` o superior.

**Si falla:** la versión de Python en el entorno de ejecución es muy antigua. Marcelo no puede proceder hasta que se instale Python 3.10+.

---

### CA-2 (CRÍTICO) — Estructura de directorios completa

**Verificación:**
```bash
find . -type f -name "*.py" | wc -l
find . -type f -name "*.yaml" | wc -l
find . -type f -name "*.md" | wc -l
```

**Criterio de aceptación:**
- Mínimo **9 archivos `.py`** (8 piezas de motor + run_dictamen.py + lonja_adapter.py + ejecucion_lonja_baq.py + road_test.py + insumos_napoli.py = 13)
- Exactamente **1 archivo `.yaml`** (lonja_baq_metodologia.yaml)
- Mínimo **3 archivos `.md`** (README + INSTRUCCIONES_ANTIGRAVITY + CRITERIOS_ACEPTACION)

**Si falla:** el zip se descomprimió incompleto o se borraron archivos. Pedir el zip de nuevo.

---

### CA-3 (CRÍTICO) — Dependencias instaladas

**Verificación:**
```bash
python3 -c "import yaml; print('PyYAML', yaml.__version__)"
```

**Criterio de aceptación:** salida del estilo `PyYAML 6.0.1` o superior.

**Si falla:** ejecutar `pip install -r requirements.txt --break-system-packages`.

---

## Nivel 2 — Pipeline funcional

### CA-4 (CRÍTICO) — La demo corre sin errores

**Verificación:**
```bash
python3 run_dictamen.py --demo
```

**Criterio de aceptación:** el script termina con código de salida 0 y muestra el bloque "AVALÚO CORPORATIVO LONJA BAQ" con valores numéricos.

**Si falla:** revisar los mensajes de error. Los más comunes están documentados en `INSTRUCCIONES_ANTIGRAVITY.md`.

---

### CA-5 (CRÍTICO) — Resultado bit-exacto del caso Napoli

**Verificación:** después de correr `python3 run_dictamen.py --demo`, leer la sección "VALIDACIÓN DE INTEGRIDAD".

**Criterio de aceptación:** los siguientes valores deben aparecer **exactamente**:

| Variable | Valor esperado |
|---|---|
| Valor consolidado obtenido | `$ 241.246.035` |
| Hash YAML obtenido | `e8071f829afdb4b6…` |
| Diferencia con esperado | `$ 0 (0.000%)` |
| Resultado validación | `✓ VALIDACIÓN OK (bit-exacto)` |
| Resultado integridad | `✓ INTEGRIDAD CONFIRMADA` |

**Si falla:** **NO PROCEDER** con dictámenes reales. Reportar a Ray la salida completa de la demo.

---

### CA-6 (ESENCIAL) — Estado AMARILLA y fallback aplicado

**Verificación:** en la salida de la demo, verificar las siguientes líneas:

```
Métodos efectivos: M1, M3
Pesos efectivos:   {'M1': 0.7, 'M3': 0.3}
Estado:            AMARILLA
```

**Criterio de aceptación:** los tres valores aparecen exactamente como se muestran arriba.

**Por qué:** confirma que la regla de fallback declarada por la Lonja está activa. M2 se desestima por divergencia >15%, M1 y M3 se redistribuyen 70/30. Cualquier desviación indica que el YAML se modificó o el motor de consolidación no está aplicando la regla correctamente.

---

## Nivel 3 — Generación de dictamen

### CA-7 (ESENCIAL) — Dictamen HTML se genera

**Verificación:**
```bash
python3 run_dictamen.py --dictamen
ls output_corrida/dictamen_napoli.html
```

**Criterio de aceptación:** el archivo `output_corrida/dictamen_napoli.html` existe y pesa entre 25 y 35 KB.

---

### CA-8 (DESEABLE) — Dictamen PDF se genera

**Verificación:**
```bash
ls output_corrida/dictamen_napoli.pdf
```

**Criterio de aceptación:** el archivo existe y pesa entre 60 y 100 KB.

**Si falla:** weasyprint no se instaló correctamente. **No es bloqueante** — el HTML se puede imprimir a PDF desde cualquier navegador. Reportar a Ray para que evalúe si vale la pena instalar weasyprint en este entorno.

---

### CA-9 (ESENCIAL) — Dictamen contiene los datos correctos

**Verificación:** abrir `output_corrida/dictamen_napoli.html` (o el PDF) en un navegador y verificar:

| Campo | Valor esperado |
|---|---|
| Folio matrícula | `040-646406` |
| Predio | `Apto 430, Torre 8, Conjunto Residencial Napoli` |
| Área | `58.75 m²` |
| Coeficiente copropiedad | `0.2037%` |
| Número de dictamen | `ARHIAX-LAI-2026-DICT-0001` |
| Marco normativo citado | Ley 1673/2013, Decreto 1420/1998 Art. 11, Resolución IGAC 620/2008 |

**Criterio de aceptación:** los seis campos coinciden exactamente.

**Si falla:** algún archivo de datos (`insumos_napoli.py`) o del motor fue modificado. Restaurar desde el zip original.

---

## Nivel 4 — Capacidad de parametrización

### CA-10 (ESENCIAL) — El road test demuestra parametrización

**Verificación:**
```bash
python3 run_dictamen.py --road-test
```

**Criterio de aceptación:** la salida muestra **5 escenarios** con cambios distintos en el YAML, cada uno con su hash de declaración correspondiente. El escenario 4 (cap rate 7.0%) y el escenario 5 (fallback 50/50) deben mostrar valores consolidados **distintos** a los escenarios 1, 2 y 3.

**Por qué:** confirma que el motor obedece TODAS las reglas declaradas en el YAML, no solo los pesos default. Es la prueba operativa del principio "la metodología es de la Lonja, el motor es el ejecutor".

---

### CA-11 (DESEABLE) — Modificación del YAML cambia el resultado

**Verificación manual:**
1. Hacer una copia del YAML: `cp lonja_layer/lonja_baq_metodologia.yaml /tmp/yaml_test.yaml`
2. Editar `/tmp/yaml_test.yaml` y cambiar la línea `tasa_central: 0.085` (en la sección apto_NO_VIS_estrato_4) a `tasa_central: 0.070`.
3. Correr: `python3 run_dictamen.py --yaml /tmp/yaml_test.yaml`

**Criterio de aceptación:** el valor consolidado resultante es **distinto** a $ 241.246.035 (debería ser mayor, porque al bajar la tasa de capitalización el método M3 produce un valor más alto).

**Si falla:** el motor no está leyendo el YAML correctamente. Reportar a Ray.

---

### CA-12 (DESEABLE) — Output de referencia coincide

**Verificación:**
```bash
diff output_corrida/dictamen_napoli.html output_referencia/dictamen_napoli.html
```

**Criterio de aceptación:** el comando `diff` no muestra diferencias significativas (puede haber diferencias en timestamps o números de dictamen autoincrementales, pero el contenido sustantivo debe ser idéntico).

**Si falla:** generación local difiere de la referencia. Investigar versiones de Python o diferencias de entorno.

---

## Resumen ejecutivo

| Nivel | Criterios | Status esperado para considerar OK |
|---|---|---|
| 1 — Instalación | CA-1, CA-2, CA-3 | **Todos los 3 deben pasar (críticos)** |
| 2 — Pipeline | CA-4, CA-5, CA-6 | **CA-4 y CA-5 críticos, CA-6 esencial** |
| 3 — Dictamen | CA-7, CA-8, CA-9 | **CA-7 y CA-9 esenciales, CA-8 deseable** |
| 4 — Parametrización | CA-10, CA-11, CA-12 | **CA-10 esencial, CA-11 y CA-12 deseables** |

**Definición de hecho del paquete:**
- Si pasan **todos los CRÍTICOS y ESENCIALES**, el paquete está listo para operar.
- Si fallan los DESEABLES pero pasan los demás, el paquete opera pero con menor trazabilidad.
- Si falla cualquier CRÍTICO, el paquete **no debe usarse para emitir dictámenes reales** hasta resolver el problema.

---

## Reporte de validación

Cuando se complete la validación, generar un reporte simple así (puede ser por email a Ray):

```
VALIDACIÓN MOTOR TMA + CAPA LONJA BAQ v1.0
Operador: [Alisson / Marcelo]
Entorno:  [Antigravity / Local / Otro]
Fecha:    [YYYY-MM-DD]

CA-1   ✓ / ✗
CA-2   ✓ / ✗
CA-3   ✓ / ✗
CA-4   ✓ / ✗
CA-5   ✓ / ✗  (Valor obtenido: $ ____________ / esperado: $ 241.246.035)
CA-6   ✓ / ✗
CA-7   ✓ / ✗
CA-8   ✓ / ✗  (PDF: sí / no)
CA-9   ✓ / ✗
CA-10  ✓ / ✗
CA-11  ✓ / ✗
CA-12  ✓ / ✗

OBSERVACIONES:
  [...]
```

---

**Sinergia Consulting Group S.A.S. — Estrategia ejecutada como sistema.**

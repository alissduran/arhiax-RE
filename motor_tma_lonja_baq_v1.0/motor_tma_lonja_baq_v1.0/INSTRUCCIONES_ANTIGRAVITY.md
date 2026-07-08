# Instrucciones de ejecución en Antigravity — Para Marcelo

**Sinergia Consulting Group S.A.S.**
**Paquete:** Motor TMA + Capa Lonja BAQ v1.0
**Fecha:** 07 de mayo de 2026

---

## Para qué este documento

Marcelo, este archivo es para que puedas correr el motor TMA en Antigravity sin tener que entender el código Python por dentro. Solo necesitas seguir los pasos en orden.

Si algo falla, hay una sección al final con soluciones a los errores comunes.

---

## Paso 1 — Subir el paquete

1. Descomprime el archivo `motor_tma_lonja_baq_v1.0.zip` en tu computador.
2. Sube la carpeta completa `motor_tma_lonja_baq_v1.0/` al espacio de trabajo de Antigravity.
3. Verifica que la estructura quedó así:

```
motor_tma_lonja_baq_v1.0/
├── run_dictamen.py
├── README.md
├── INSTRUCCIONES_ANTIGRAVITY.md     ← este archivo
├── CRITERIOS_ACEPTACION.md
├── requirements.txt
├── tma_engine/
├── lonja_layer/
├── output_referencia/
└── docs/
```

---

## Paso 2 — Abrir terminal en Antigravity

En Antigravity, abre una terminal (suele ser un panel inferior o lateral). Si no la encuentras, busca "Terminal" en el menú principal o usa el atajo `` Ctrl+` `` (en Linux/Windows) o `` Cmd+` `` (en Mac).

Una vez en la terminal, navega al directorio del paquete:

```bash
cd /ruta/donde/subiste/motor_tma_lonja_baq_v1.0
```

(Reemplaza `/ruta/donde/subiste/` por la ruta real en tu Antigravity.)

---

## Paso 3 — Verificar que Python está disponible

```bash
python3 --version
```

Debe responder **Python 3.10** o superior. Si la versión es menor, contacta a Ray.

---

## Paso 4 — Instalar las dependencias

```bash
pip install -r requirements.txt
```

Si Antigravity te pide instalar con una bandera adicional (mensaje del estilo "externally-managed-environment"), corre:

```bash
pip install --break-system-packages -r requirements.txt
```

Este comando instala dos librerías:
- **PyYAML** — para leer el archivo de metodología de la Lonja.
- **weasyprint** — para generar el dictamen pericial en PDF.

Si **weasyprint** falla en la instalación, no te preocupes: el motor funciona igual, solo no generará el PDF (sí generará el HTML que puedes abrir en cualquier navegador).

---

## Paso 5 — Correr la demo de validación

Este es el comando más importante. Te dice si todo está bien instalado.

```bash
python3 run_dictamen.py --demo
```

**Qué deberías ver al final:**

```
┌─ AVALÚO CORPORATIVO LONJA BAQ ────────────────────────────────────────┐
│  Valor consolidado:                  $ 241.246.035                    │
│  Estado:            AMARILLA                                          │
└───────────────────────────────────────────────────────────────────────┘

VALIDACIÓN DE INTEGRIDAD
  Valor consolidado esperado:   $ 241.246.035
  Valor consolidado obtenido:   $ 241.246.035
  Resultado:                    ✓ VALIDACIÓN OK (bit-exacto)
  Hash YAML esperado:           e8071f829afdb4b6…
  Hash YAML obtenido:           e8071f829afdb4b6…
  Resultado:                    ✓ INTEGRIDAD CONFIRMADA
```

Si ves los dos `✓` en verde, la instalación es perfecta y puedes pasar al Paso 6.

Si ves un `⚠` o `ERROR`, ve a la sección "Solución de problemas" al final.

---

## Paso 6 — Generar el dictamen pericial PDF

```bash
python3 run_dictamen.py --dictamen
```

Esto crea:
- `output_corrida/dictamen_napoli.html` — dictamen en HTML
- `output_corrida/dictamen_napoli.pdf` — dictamen en PDF (si weasyprint funcionó)

**Compara tu PDF generado contra el de referencia que viene en `output_referencia/dictamen_napoli.pdf`.** Deben ser idénticos en contenido (puede haber diferencias mínimas en metadatos del PDF, eso está bien).

---

## Paso 7 — Correr el road test (opcional pero recomendado)

```bash
python3 run_dictamen.py --road-test
```

Esto ejecuta 5 escenarios donde se cambian parámetros del YAML de la Lonja (pesos, tasas, tolerancia, fallback) y muestra cómo el motor responde a cada cambio. Es la mejor forma de ver cómo funciona la "capa Lonja".

---

## Paso 8 — Reportar a Ray

Cuando hayas completado los pasos 1 al 6, envía a Ray:

1. Captura de pantalla (o copia del texto) de la salida del Paso 5 (demo).
2. El archivo `output_corrida/dictamen_napoli.pdf` que generaste.
3. Confirmación de que ambos `✓` salieron en verde.

Con eso queda confirmada la operación del motor en Antigravity.

---

## Solución de problemas comunes

### Error: `ModuleNotFoundError: No module named 'yaml'`

Las dependencias no se instalaron. Corre de nuevo:
```bash
pip install --break-system-packages -r requirements.txt
```

### Error: `ModuleNotFoundError: No module named 'contrato_datos'`

Estás corriendo el script desde una ubicación incorrecta. Asegúrate de estar dentro de la carpeta `motor_tma_lonja_baq_v1.0/` antes de ejecutar:
```bash
pwd                    # debe mostrar la ruta del paquete
ls run_dictamen.py     # debe encontrar el archivo
```

### Error: `Permission denied: /home/claude/...`

El motor original espera ciertas rutas en `/home/claude/`. En Antigravity esto puede no estar permitido. Solución: el script `run_dictamen.py` ya maneja esto creando las rutas necesarias automáticamente. Si aun así falla, contacta a Ray.

### El PDF no se genera (solo HTML)

`weasyprint` no se instaló correctamente. Eso es OK — el HTML está bien y se puede imprimir a PDF abriéndolo en un navegador (Chrome, Firefox, Edge) y usando "Imprimir → Guardar como PDF".

### El valor consolidado obtenido es distinto a $ 241.246.035

Hay un problema de integridad. **No procedas con dictámenes reales hasta que Ray valide.** Posibles causas:
- Algún archivo se corrompió en el zip
- Versión de Python distinta produce diferencias numéricas (raro pero posible)
- Algún archivo fue modificado sin querer

Envía a Ray la salida completa del Paso 5 y él te dice qué hacer.

### Antigravity dice "Python no encontrado"

Antigravity puede tener Python en otra ruta. Prueba con:
```bash
which python3
which python
```

Si encuentra `python` (sin el 3), reemplaza `python3` por `python` en todos los comandos.

---

## Glosario rápido

- **YAML:** archivo de texto con la metodología declarada por la Lonja. Editarlo cambia los parámetros del avalúo. No requiere recompilar nada.
- **M1, M2, M3:** los tres métodos de avalúo (Mercado, Costo, Rentas).
- **Hash:** "huella digital" del YAML. Si dos hashes coinciden, los archivos son idénticos. Si difieren, algo cambió.
- **Estado AMARILLA:** el motor encontró que un método (M2) se aparta más del 15% de los otros, lo desestimó, y consolidó con los métodos restantes según la regla de fallback declarada por la Lonja. Esto es **comportamiento esperado** para el caso Napoli, no un error.

---

## Si tienes dudas

Cualquier cosa que no esté clara, pregunta a Ray antes de seguir. **Es preferible parar y preguntar** que avanzar con un dictamen que pueda tener problemas.

---

**Sinergia Consulting Group S.A.S. — Estrategia ejecutada como sistema.**

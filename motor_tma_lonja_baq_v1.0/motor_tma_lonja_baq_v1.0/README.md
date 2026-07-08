# Motor TMA + Capa Lonja BAQ — v1.0

**Sinergia Consulting Group S.A.S.**
**Versión:** 1.0
**Fecha de empaque:** 07 de mayo de 2026
**Origen:** TR-2026-052 (motor original) + Capa de parametrización Lonja BAQ
**Para:** Alisson (validación técnica), Marcelo (ejecución en Antigravity)

---

## Qué es esto

Este paquete contiene el motor de avalúos **TMA** (Tasación / Avalúo / Modelado) construido por Sinergia, junto con la **capa de parametrización Lonja BAQ** que permite que el motor ejecute la metodología declarada por la Lonja de Propiedad Raíz de Barranquilla a través de un archivo YAML.

El paquete es **autocontenido**: contiene todo el código, los datos del caso de prueba (Apto 430 Conjunto Napoli), la metodología declarada por la Lonja, y un dictamen pericial pre-generado como referencia para validación.

**Principio arquitectónico clave:** el motor no contiene la metodología. La metodología está en `lonja_layer/lonja_baq_metodologia.yaml`. El motor obedece. Si la Lonja cambia un parámetro en el YAML, todos los avalúos posteriores reflejan el cambio sin tocar código.

---

## Estructura del paquete

```
motor_tma_lonja_baq_v1.0/
├── README.md                          ← este archivo (delegación general)
├── INSTRUCCIONES_ANTIGRAVITY.md       ← específico para Marcelo
├── CRITERIOS_ACEPTACION.md            ← validación post-instalación
├── requirements.txt                   ← dependencias Python
├── run_dictamen.py                    ← punto de entrada único
│
├── tma_engine/
│   ├── piezas/
│   │   ├── contrato_datos.py                   ← clases base (Predio, ResultadoMetodo, etc.)
│   │   ├── depreciacion_fitto_corvini.py       ← módulo Fitto-Corvini (Res. IGAC 620/2008)
│   │   ├── pieza_1_M1_comparacion_mercado.py
│   │   ├── pieza_2_M2_costo_reposicion.py
│   │   ├── pieza_3_M3_capitalizacion_rentas.py
│   │   ├── pieza_4_motor_consolidacion.py      ← regla 60/30/10, semáforo, fallback
│   │   ├── pieza_5_bandeja_revision.py         ← bandeja HTML + función firmar_avaluo
│   │   └── pieza_6_dictamen_pdf.py             ← generador del dictamen pericial
│   └── datos/
│       └── insumos_napoli.py                   ← datos del caso de prueba
│
├── lonja_layer/
│   ├── lonja_baq_metodologia.yaml              ← metodología declarada por la Lonja
│   ├── lonja_adapter.py                        ← cargador del YAML
│   ├── ejecucion_lonja_baq.py                  ← pipeline con parámetros Lonja
│   └── road_test.py                            ← 5 escenarios de cambio de parámetros
│
├── output_referencia/
│   ├── dictamen_napoli.html                    ← dictamen pericial pre-generado
│   └── dictamen_napoli.pdf                     ← versión PDF
│
└── docs/
    └── Addendum_Capa_Parametrizacion_Lonja.docx   ← documento de soporte conceptual
```

---

## Requisitos del sistema

- **Python:** 3.10 o superior
- **Sistema operativo:** Linux, macOS, Windows (probado en Linux)
- **Espacio en disco:** ~2 MB (sin contar dependencias)
- **Memoria:** mínima (el pipeline completo corre en menos de 100 MB)

---

## Instalación

```bash
# 1) Descomprimir el paquete
unzip motor_tma_lonja_baq_v1.0.zip
cd motor_tma_lonja_baq_v1.0

# 2) Instalar dependencias
pip install -r requirements.txt

# 3) Validar instalación corriendo la demo
python3 run_dictamen.py --demo
```

Si la demo termina con `✓ VALIDACIÓN OK (bit-exacto)` y `✓ INTEGRIDAD CONFIRMADA`, la instalación está correcta.

---

## Modos de ejecución

El script `run_dictamen.py` es el punto de entrada único. Tiene cuatro modos:

| Comando | Qué hace |
|---|---|
| `python3 run_dictamen.py --demo` | Ejecuta el pipeline completo del caso Napoli y valida resultado contra valores de referencia. **Empezar siempre por aquí.** |
| `python3 run_dictamen.py --dictamen` | Genera el dictamen pericial PDF/HTML del caso Napoli. Salida en `output_corrida/`. |
| `python3 run_dictamen.py --road-test` | Ejecuta los 5 escenarios del road test que demuestran cómo el motor obedece cambios en el YAML sin recompilar código. |
| `python3 run_dictamen.py --yaml <ruta>` | Ejecuta el pipeline con un YAML Lonja específico (para casos futuros con parámetros distintos). |

---

## Resultado esperado del caso Napoli

Cuando se corre `python3 run_dictamen.py --demo`, el resultado debe ser:

```
┌─ AVALÚO CORPORATIVO LONJA BAQ ────────────────────────────────────────┐
│  Valor consolidado:                  $ 241.246.035                    │
│  Banda 80%:         $ 209.556.510 — $ 273.548.092                     │
│  Estado:            AMARILLA                                          │
└───────────────────────────────────────────────────────────────────────┘

Métodos efectivos: M1, M3
Pesos efectivos:   {'M1': 0.7, 'M3': 0.3}

Hash YAML obtenido:  e8071f829afdb4b6…
```

**Estos valores son la referencia.** Si tu corrida produce algo distinto, hay un problema de instalación o de versiones — ver `CRITERIOS_ACEPTACION.md`.

---

## Para Alisson — validación técnica

1. Corre `python3 run_dictamen.py --demo`. Verifica el resultado bit-exacto.
2. Corre `python3 run_dictamen.py --road-test`. Lee la salida y entiende cómo el YAML controla la ejecución.
3. Abre `lonja_layer/lonja_baq_metodologia.yaml` y revisa la estructura. Cada sección está comentada.
4. Lee el `Addendum_Capa_Parametrizacion_Lonja.docx` en `docs/` para el contexto conceptual.
5. Si todo cuadra, validar contra el `CRITERIOS_ACEPTACION.md`.

## Para Marcelo — ejecución en Antigravity

Ver archivo `INSTRUCCIONES_ANTIGRAVITY.md` con paso a paso específico para esa plataforma.

---

## Modificaciones permitidas y NO permitidas

**Permitidas:**
- Editar `lonja_baq_metodologia.yaml` para probar otros parámetros (es exactamente el caso de uso del motor).
- Modificar `insumos_napoli.py` para probar otros predios.
- Crear nuevos archivos `.py` en `lonja_layer/` que importen del motor.

**NO permitidas (rompen integridad):**
- Modificar archivos en `tma_engine/piezas/` (rompe los hashes y la trazabilidad).
- Modificar `lonja_adapter.py` o `ejecucion_lonja_baq.py` (cambian el comportamiento esperado).
- Eliminar el archivo `output_referencia/dictamen_napoli.pdf` (es la referencia de validación).

---

## Soporte y referencias

- **Marco normativo:** Ley 1673/2013, Decreto 1420/1998 Art. 11, Resolución IGAC 620/2008, Resolución IGAC 1040/2023.
- **Hash YAML Lonja v0.1:** `e8071f829afdb4b69116da794068641f`
- **Valor consolidado de referencia caso Napoli:** $ 241.246.035
- **Estado de referencia:** AMARILLA (M2 desestimado por divergencia >15%, fallback M1=0.7 / M3=0.3)

Para reportar problemas o pedir actualización del YAML por la Junta Técnica de la Lonja BAQ, contactar a Ray Miller — Sinergia Consulting Group S.A.S.

---

**Estrategia ejecutada como sistema.**

# Titulux · ARHIAX — Parche Sprint 0
## Cuatro cambios listos para insertar (solo texto + 1 regla)

> Objetivo: que la próxima versión ya refleje el posicionamiento "insumo base de fuentes públicas, sujeto a verificación profesional", sin construir todavía los módulos nuevos. Aplicar los cuatro y re-emitir.

---

## CAMBIO 1 — Renombrar y quitar la retórica de autoridad

**Regla:** el producto no puede llamarse "dictamen" ni declararse "aprobado". Un dictamen es una opinión profesional; "aprobado" es un veredicto. Ambos exceden el alcance declarado. Se conserva la marca ARHIAX y el código de estándar `LAI`, solo cambia el sustantivo del producto y se neutraliza el banner.

**Buscar → Reemplazar (exacto):**

| # | Buscar | Reemplazar |
|---|---|---|
| 1a | `Motor Geo-Provenance · Dictamen LAI` | `Motor Geo-Provenance · Informe Base LAI` |
| 1b | `✔ DICTAMEN LAI: APROBADO CON OBSERVACIONES` | `▪ INFORME BASE LAI — RESULTADO PRELIMINAR: 2 ALTO · 2 MEDIO · 3 INFORMATIVO (sujeto a verificación profesional)` |
| 1c | `Certificado N°:` | `Referencia N°:` |
| 1d | `09 - Certificado de Trazabilidad (Provenance)` | `09 - Sello de Integridad del Insumo (Provenance)` |
| 1e | Pie de página: `ARHIAX Dictamen LAI \| Folio` | `ARHIAX Informe Base LAI \| Folio` |

**Nota para el dev:** 1b debe generarse dinámicamente a partir del conteo real de hallazgos, no quedar hardcodeado. El texto anterior es el ejemplo instanciado para Napoli.

---

## CAMBIO 2 — Disclaimer de alcance (Bloque 0)

**Cambio de código:** definir la constante `SCOPE_DISCLAIMER` y renderizarla en (a) una nueva **Sección 00** justo debajo del encabezado, y (b) el pie de cada página en versión corta.

**Texto exacto — Sección 00 (versión completa):**
> **NATURALEZA DE ESTE DOCUMENTO.** Este es un **análisis de base** producido automáticamente por el motor ARHIAX a partir de fuentes públicas (Superintendencia de Notariado y Registro, geoportales municipales, catastro, OpenStreetMap y bases abiertas). **No constituye estudio de títulos, concepto jurídico ni avalúo comercial** en los términos de la Ley 1673 de 2013 ni de las normas de metodología valuatoria vigentes. Es un insumo preliminar **sujeto a verificación por profesional del derecho con tarjeta profesional vigente y/o avaluador inscrito en el Registro Abierto de Avaluadores (RAA)**. Ninguna decisión de crédito, garantía o compraventa debe adoptarse con base exclusiva en este documento.

**Texto exacto — pie de página (versión corta, una línea):**
> Insumo base de fuentes públicas · No sustituye estudio de títulos ni avalúo · Sujeto a verificación profesional.

```python
SCOPE_DISCLAIMER_FULL = (
    "NATURALEZA DE ESTE DOCUMENTO. Este es un análisis de base producido "
    "automáticamente por el motor ARHIAX a partir de fuentes públicas (SNR, "
    "geoportales municipales, catastro, OpenStreetMap y bases abiertas). No "
    "constituye estudio de títulos, concepto jurídico ni avalúo comercial en los "
    "términos de la Ley 1673 de 2013 ni de las normas de metodología valuatoria "
    "vigentes. Es un insumo preliminar sujeto a verificación por profesional del "
    "derecho con tarjeta profesional vigente y/o avaluador inscrito en el RAA. "
    "Ninguna decisión de crédito, garantía o compraventa debe adoptarse con base "
    "exclusiva en este documento."
)
SCOPE_DISCLAIMER_FOOTER = (
    "Insumo base de fuentes públicas · No sustituye estudio de títulos ni "
    "avalúo · Sujeto a verificación profesional."
)
```

---

## CAMBIO 3 — Gate deóntico: matar la contradicción del score

**Problema:** coexisten "Activo APTO para portafolio" (Sec. 08) e "Imposible estructurar hasta cancelación de hipoteca" (H-01). Regla dura: cualquier gravamen o limitación vigente bloquea la estructurabilidad fiduciaria, con semáforo ROJO, sin importar el score general.

**Cambio de código — regla:**
```python
BLOQUEOS_FIDUCIARIOS = {
    "hipoteca_vigente", "embargo", "afectacion_vivienda_familiar",
    "patrimonio_de_familia", "demanda_civil_inscrita",
    "prohibicion_judicial", "medida_cautelar", "usufructo_vigente",
}

def evaluar_estructurabilidad_fiduciaria(hallazgos):
    bloqueos = [h for h in hallazgos
                if h.tipo in BLOQUEOS_FIDUCIARIOS and h.estado == "VIGENTE"]
    if bloqueos:
        return {
            "semaforo": "ROJO",
            "estructurable": False,
            "condiciones_precedentes": [condicion_para(b) for b in bloqueos],
        }
    return {"semaforo": "VERDE", "estructurable": True, "condiciones_precedentes": []}
```

**Reemplazo del bloque "Para FIC / Estructurador" (Sec. 08):**

Buscar:
> Activo APTO para portafolio. Sin prohibiciones de transferencia. Compraventa NO VIS ($268.5M) permite libre circulacion. Titular es pareja joven con copropiedad 50/50. Monitorear afectacion a vivienda familiar que requiere consentimiento de ambos conyuges.

Reemplazar (salida instanciada para Napoli — semáforo ROJO):
> **Estructurabilidad fiduciaria: BLOQUEADA (semáforo ROJO).** El activo NO es estructurable como garantía fiduciaria en su estado registral actual. Condiciones precedentes para habilitarlo: (i) cancelación de la hipoteca abierta a favor de Banco de Bogotá (Anot. 007); (ii) levantamiento de la afectación a vivienda familiar con consentimiento de ambos titulares (Anot. 008); (iii) registro de la cesión de cartera a Scotiabank Colpatria en el folio. El activo sí circula libremente para compraventa (sin prohibición de transferencia), pero ello **no equivale** a estructurabilidad como colateral fiduciario. `[REQUIERE VERIFICACIÓN por profesional del derecho]`

**Test obligatorio (debe fallar la emisión si no pasa):**
```python
def test_no_contradiccion(texto_documento):
    apto = "APTO para portafolio" in texto_documento
    bloqueado = ("BLOQUEADA" in texto_documento
                 or "Imposible estructurar" in texto_documento)
    assert not (apto and bloqueado), \
        "Contradicción: veredicto apto y bloqueo coexisten en el mismo documento."
```

---

## CAMBIO 4 — Cerrar el boundary del avalúo (Bloque 6)

**Problema:** el fix anterior quedó a medias; la palabra "avalúo" se sigue filtrando en tres lugares, y las etiquetas nuevas emiten juicios valuatorios ("sobreprecio") que un insumo base no puede emitir.

**4.1 — Fugas de la palabra "avalúo" (buscar → reemplazar exacto):**

| Ubicación | Buscar | Reemplazar |
|---|---|---|
| Título 04B | `04B - Estimacion de Valor Comercial` | `04B - Estimación Referencial de Mercado (NO es avalúo)` |
| Fuente 04B | `MONOGRAFIA DE AVALUO ARHIAX & COMPONENTES TECNICOS VALUATORIOS` | `ESTIMACIÓN REFERENCIAL DE MERCADO ARHIAX (AUTOMÁTICA)` |
| Tabla 04B | `Vigencia del Avaluo` | `Vigencia de la estimación referencial` |
| Sección 10 | `Avaluo formal INTEGRADO -- Rango de valor referencial basado en Monografia de Avaluo ARHIAX` | `Estimación referencial de mercado — NO sustituye avalúo elaborado por avaluador inscrito en el RAA (Ley 1673/2013)` |
| Campo valor | `Valor Comercial Consolidado` | `Valor central estimado (referencial)` |

**4.2 — Eliminar las etiquetas de juicio valuatorio.** La banda visual emite juicios ("Zona de Liquidación", "Zona de Sobreprecio") que corresponden al avaluador, no al motor.

Buscar:
> `$ 354.786.000` / `Zona de Liquidacion` — `$ 407.800.000` / `VALOR PROBABLE DE MERCADO` — `$ 460.813.999` / `Zona de Sobreprecio`

Reemplazar por etiquetas neutras:
> `$ 354.786.000` / `Banda baja (P10)` — `$ 407.800.000` / `Valor central estimado` — `$ 460.813.999` / `Banda alta (P90)`

**4.3 — Insertar disclaimer al pie de la Sección 04B:**
> Esta estimación es referencial y de carácter automático. **No sustituye un avalúo comercial** elaborado por avaluador inscrito en el RAA conforme a la Ley 1673 de 2013 y las metodologías valuatorias vigentes.

**Test de boundary:**
```python
def test_boundary_avaluo(texto_seccion_valor):
    # La palabra "avalúo" solo puede aparecer negada.
    import re
    for m in re.finditer(r"aval[uú]o", texto_seccion_valor, re.IGNORECASE):
        contexto = texto_seccion_valor[max(0, m.start()-40):m.start()]
        assert re.search(r"no\s+(es|sustituye|constituye)", contexto, re.IGNORECASE), \
            "Uso de 'avalúo' sin negación explícita."
```

---

## Checklist de cierre del Sprint 0

- [ ] 1 · Encabezado, banner y pie renombrados (sin "Dictamen" ni "Aprobado").
- [ ] 2 · `SCOPE_DISCLAIMER` en Sección 00 y en pie de cada página.
- [ ] 3 · Gate fiduciario activo · bloque FIC condicionado · `test_no_contradiccion` en verde.
- [ ] 4 · Tres fugas de "avalúo" corregidas · etiquetas de juicio eliminadas · disclaimer 04B insertado · `test_boundary_avaluo` en verde.

*Al cerrar estos cuatro, el documento pasa de "producto que sobre-reclama autoridad" a "insumo base honesto y defendible". Los módulos diferenciadores (semáforo de estructurabilidad completo, conciliación registral, cargas económicas, ruta de verificación) entran en el Sprint 1, sobre los Bloques 2, 3, 4 y 7 del brief v7.*

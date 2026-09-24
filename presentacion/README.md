# Presentación comercial — DICTUS / ARHIAX RE · Igama Financiera e Inmobiliaria

## Pieza vigente

**`DICTUS_Presentacion_Ejecutiva.pdf`** — 5 láminas, 1280 × 720 (16:9). Pieza comercial
para **compradores, vendedores e inmobiliarias**. Se regenera con:

```powershell
python presentacion/generar_presentacion_dictus_ejecutiva.py
```

| Lámina | Contenido |
|---|---|
| P1 | Portada: **«DICTUS: confianza verificable para comprar, vender y financiar inmuebles»** + subtítulo (estimación económica + análisis legal + contexto geodésico + evidencia reutilizable) + los **dos objetivos estratégicos** (crédito hipotecario · seguro de títulos) + cobertura municipal |
| P2 | Problema y oportunidad: **compradores y vendedores** · **inmobiliarias** y la tesis «el mercado necesita una capa de confianza previa a la promesa de compraventa» |
| P3 | Solución: **cinco capacidades integradas** (estimación económica, revisión jurídica y de títulos, análisis geodésico y urbano, contrapartes frente a listas restrictivas conforme al SAGRILAFT, expediente verificable con hash/sello/trazabilidad) + reuso por comprador, vendedor, inmobiliaria, banco y aseguradora |
| P4 | Metodología en tres capas: **la norma · el concepto técnico · la validación experta** |
| P5 | **Tres canales de ingresos** (informe previo de confianza · verificación de títulos de inmuebles captados · servicios B2B para bancos y aseguradoras) + ciudades + frase de cierre |

Reglas de la pieza (aplicadas al escribirlas, para que no se pierdan):

1. Máximo cinco láminas y una idea dominante por lámina; poco texto, lenguaje ejecutivo.
2. Las listas se presentan como **«listas restrictivas y sancionatorias aplicables,
   conforme al SAGRILAFT»**: **no se nombran fuentes concretas**.
3. Nada de «lo que falta»: el material de cliente no habla de pendientes, limitaciones
   ni roadmap.
4. Toda afirmación metodológica se apoya en la norma y en la validación del experto
   (avaluador, abogado, geodesta). El motor sugiere y compara; **firma el profesional**.
5. El logo del cliente va en la cabecera de cada lámina (`assets/igama-logo.png`).
6. La frase de cierre —**«Menos incertidumbre. Más crédito. Más cierres. Más
   confianza.»**— aparece solo en la última lámina.

### Verificación de la pieza vigente

El generador ejecuta su propio QA al terminar (`qa()`): 5 láminas, contenido obligatorio
**38/38**, **0** términos vetados («pendiente», «falta», «no disponible», «roadmap»,
fuentes de listas citadas) y la frase de cierre en la última lámina. QA geométrico de la
corrida: **0 desbordes** de margen, **0 colisiones** de texto, **0** textos fuera de su
tarjeta y **0** glifos no imprimibles (todo el texto es WinAnsi; los iconos son
vectoriales).

## Piezas anteriores (se conservan)

- `ARHIAX_RE_Presentacion_Empresarial.pdf` — deck empresarial de 5 láminas
  (`generar_presentacion_empresarial.py`), con el encuadre «Expediente Verificado»
  en cinco capas y la tesis de los dos objetivos estratégicos.
- `ARHIAx_Igama_Presentacion.html` / `.pdf` — deck navegable en HTML (autocontenido),
  16:9, con la versión extensa del producto.
- `ARHIAX_RE_Confianza_Transactional.pdf` — generado por
  `generar_presentacion_5_slides.py`, con notas de presentador y «propuesta visual».
- `generar_entrega_documento.py` → `ARHIAX_RE_Entrega_Completa.pdf`.

## Verificación rápida de cualquier pieza

```powershell
python -c "import pymupdf;d=pymupdf.open('presentacion/DICTUS_Presentacion_Ejecutiva.pdf');print(d.page_count, d[0].rect)"
```


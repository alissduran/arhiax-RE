# Presentación comercial — ARHIAX RE · Igama Financiera e Inmobiliaria

## Pieza vigente

**`ARHIAX_RE_Presentacion_Empresarial.pdf`** — 5 láminas, 1280 × 720 (16:9).
Se regenera con:

```powershell
python presentacion/generar_presentacion_empresarial.py
```

| Lámina | Contenido |
|---|---|
| P1 | Tesis: **dos objetivos estratégicos** (profundizar el crédito hipotecario · establecer las bases del seguro de títulos) y cobertura municipal (Barranquilla, Medellín, Bogotá, Pasto, Bucaramanga) |
| P2 | El problema con **doble perspectiva**: compradores y vendedores · inmobiliarias |
| P3 | La solución: **Expediente Verificado** en cinco capas + sello inmutable y reuso |
| P4 | Metodología: **la norma, el concepto y la validación del experto** |
| P5 | Beneficios por actor y **tres canales de ingreso** |

Reglas de la pieza (aplicadas al escribirlas, para que no se pierdan):

1. Máximo cinco láminas y una idea dominante por lámina.
2. El screening se presenta como **listas restrictivas conforme a los requerimientos del
   SAGRILAFT**, con sus atributos de evidencia (hash de la consulta, versión de la
   fuente, **sello inmutable**, reuso autorizado). No se nombran listas concretas.
3. Nada de «lo que falta»: el material de cliente no habla de pendientes internos.
4. Toda afirmación metodológica se apoya en la norma citada y en la validación del
   experto (avaluador RAA, abogado, geodesta). El motor sugiere y compara; **firma el
   profesional**.
5. El logo del cliente va en la cabecera de cada lámina (`assets/igama-logo.png`).

## Piezas anteriores (se conservan)

- `ARHIAx_Igama_Presentacion.html` / `.pdf` — deck navegable en HTML (autocontenido),
  16:9, con la versión extensa del producto.
- `ARHIAX_RE_Confianza_Transactional.pdf` — generado por
  `generar_presentacion_5_slides.py`, con notas de presentador y «propuesta visual».
- `generar_entrega_documento.py` → `ARHIAX_RE_Entrega_Completa.pdf`.

## Verificación de la pieza vigente

```powershell
python -c "import pymupdf;d=pymupdf.open('presentacion/ARHIAX_RE_Presentacion_Empresarial.pdf');print(d.page_count)"
```

Comprobaciones ejecutadas en la última corrida: **5 páginas** de 1280 × 720, contenido
obligatorio presente **24/24** (objetivos, doble perspectiva, cinco capas, SAGRILAFT,
hash/sello/reuso, las cinco ciudades, norma/concepto/validación, tres canales) y
**cero** apariciones de términos vetados (listas concretas, «falta», «pendiente»,
«no disponible»). QA geométrico: 0 desbordes de margen y 0 colisiones de texto.

# Resolución IGAC 941 de 2026 — Métodos de avalúo y propiedad horizontal
## Informe de investigación y matriz de cotejo contra las reglas implementadas en ARHIAX

---

## 0. Fuentes, método de obtención y advertencia de fiabilidad

### 0.1 Fuente primaria (texto oficial)

El IGAC publica el acto en su normograma:

- Página oficial: `https://www.igac.gov.co/node/53595`
  - Título oficial (transcrito literalmente de la ficha): **"Por la cual se fijan los métodos y las condiciones de elaboración y presentación de avalúos conforme al capítulo 3 del título 2 del Decreto 1170 de 2015 y se establecen otras disposiciones"**
  - **Fecha de emisión: viernes 31 de julio de 2026.** Publicado en web el **miércoles 12 de agosto de 2026**.
  - **Estado: Vigente.** Observación de la ficha: *"Deroga Resolución 620 de 2008, y los incisos 1,2 y 3 del artículo 14 de la Resolución 898 de 2014"*.
  - Adjuntos: `R 0941 - 2026 SE FIJAN LOS MÉTODOS Y LAS CONDICIONES DE ELABORACIÓN Y PRESENTACIÓN DE AVALÚOS.pdf` y `Anexo_Final_.pdf`.
- PDF de la resolución (descargado, 7.342.305 bytes): `https://www.igac.gov.co/sites/default/files/transparencia/normograma/R%200941%20-%202026%20SE%20FIJAN%20LOS%20M%C3%89TODOS%20Y%20LAS%20CONDICIONES%20DE%20ELABORACI%C3%93N%20Y%20PRESENTACI%C3%93N%20DE%20AVAL%C3%9AOS.pdf`
- PDF del anexo (descargado, 1.717.455 bytes): `https://www.igac.gov.co/sites/default/files/transparencia/normograma/Anexo_Final_.pdf`

### 0.2 Cómo se extrajo el texto (y por qué importa)

**Ninguno de los dos PDF oficiales tiene capa de texto.** Son documentos escaneados:

- Resolución: 117 imágenes de página (JPEG, ~634×820 px, ≈75–80 DPI), 0 fuentes embebidas.
- Anexo_Final: 27 imágenes (es el **suplemento de figuras y diagramas**, no el anexo técnico completo).

Por tanto el texto se obtuvo así:

1. Extracción de las 117 imágenes de página del PDF oficial (resolviendo la cadena de filtros `/Filter [/FlateDecode /DCTDecode]`), numeradas `pg001`…`pg117`, que **coinciden 1:1 con las páginas impresas** (verificado contra el pie "Página | N").
2. OCR completo con el motor **Windows.Media.Ocr (es-ES)** a 2× de escala.
3. **Verificación visual directa** (lectura de las imágenes de página) de los artículos críticos: págs. 12, 17, 18, 21, 23, 24, 34, 35, 63, 70, 72, 75.

**Consecuencia para la fiabilidad:** todas las citas de este informe se marcan según su nivel de verificación. Donde el OCR y una lectura visual independiente coinciden, la cita es sólida. Las palabras sueltas de un escaneo a ~75 DPI pueden tener ambigüedad ortográfica (un caso real detectado y resuelto: *"integrales"* vs. *"integrados"* en el Art. 13.9.b — ver §5.1). Las **fórmulas matemáticas no son legibles de forma fiable** en este escaneo y se advierten expresamente.

### 0.3 Estructura confirmada del acto

La resolución tiene **61 artículos** en **9 títulos**, más un **anexo técnico que hace parte integral** del acto (Art. 3). Estructura verificada:

| Título | Contenido | Artículos |
|---|---|---|
| TÍTULO I | Disposiciones generales | 1–5 |
| TÍTULO II | Gestión valuatoria (Cap. I Aspectos técnicos y jurídicos; Cap. II Elaboración del avalúo y contenido mínimo del informe) | 6–14 |
| **TÍTULO III** | **MÉTODOS VALUATORIOS Y SU APLICACIÓN** | **15–34** |
| TÍTULO IV | Procedimientos específicos | 35–45 |
| TÍTULO V | Elaboración de avalúos en zonas rurales | 46–48 |
| TÍTULO VI | Criterios para la determinación del valor comercial de terrenos en suelos de protección | 49 |
| TÍTULO VII | Cálculo del efecto plusvalía | 50–57 |
| TÍTULO VIII | De la controversia de los avalúos | 58 |
| TÍTULO IX | Disposiciones finales | 59–61 |

TÍTULO III se subdivide en:

- CAPÍTULO I. **MÉTODO DE COMPARACIÓN O DE MERCADO** → Arts. 16–21
- CAPÍTULO II. **MÉTODO DE RENTA O CAPITALIZACIÓN DE INGRESOS** → Arts. 22–26
- CAPÍTULO III. **MÉTODO DEL COSTO** → Arts. 27–30
- CAPÍTULO IV. **MÉTODO TÉCNICA RESIDUAL** → Arts. 31–34

---

## 1. NOMENCLATURA OFICIAL DE MÉTODOS

### 1.1 El artículo que la fija: Artículo 15 — "Métodos Valuatorios"

**Texto confirmado (lectura visual directa + OCR coincidentes, dos lecturas independientes):**

> **Artículo 15. Métodos Valuatorios.** Para la determinación del valor comercial, en el marco de la presente resolución, deberán aplicarse los siguientes métodos valuatorios:
>
> **a) Método de comparación o de mercado.**
> **b) Método de renta o capitalización de ingresos.**
> **c) Método del costo.**
> **d) Método (técnica) residual.**
>
> **Parágrafo.** En el desarrollo de los métodos, el avaluador deberá indicar de manera expresa las fuentes o medios de los cuales se obtuvo cada uno de los datos e información utilizados.

**Los cuatro nombres oficiales son, literalmente:**

| Literal | **Nombre oficial exacto** | Ancla normativa |
|---|---|---|
| a) | **Método de comparación o de mercado** | Art. 15 lit. a); desarrollado Arts. 16–21; anexo técnico §2.1 |
| b) | **Método de renta o capitalización de ingresos** | Art. 15 lit. b); desarrollado Arts. 22–26; anexo técnico §2.2 |
| c) | **Método del costo** | Art. 15 lit. c); desarrollado Arts. 27–30; anexo técnico §2.3 |
| d) | **Método (técnica) residual** | Art. 15 lit. d); desarrollado Arts. 31–34; anexo técnico §2.4 |

### 1.2 Puntos críticos sobre la nomenclatura

1. **No existe "M1/M2/M3" en la norma.** Las etiquetas M1/M2/M3 son exclusivamente de ARHIAX y no corresponden a ninguna nomenclatura oficial.

2. **No existe un "método de reposición" como método autónomo.** "Costo de reposición" y "costo de reproducción" son **dos procesos dentro del Método del costo**, definidos en el Art. 28. El nombre del método es *Método del costo*; la reposición es un insumo (el "CT" de la ecuación del Art. 27).

3. **La norma define CUATRO métodos, no tres.** ARHIAX opera con una taxonomía de tres (M1/M2/M3); el cuarto —**Método (técnica) residual**— está en el listado obligatorio del Art. 15 lit. d) y desarrollado en un capítulo propio (Arts. 31–34).

4. **El residual se denomina con doble nombre.** El Art. 15 lit. d) lo llama "Método (técnica) residual"; el Capítulo IV se titula "MÉTODO TÉCNICA RESIDUAL"; el Art. 31 lo define como "Método (Técnica) Residual"; y el anexo técnico §2.4 lo rotula "Método (técnica) Residual". El paréntesis es parte del nombre oficial y refleja que la norma lo trata como método y técnica a la vez.

5. **El método de renta tiene un nombre compuesto obligatorio:** "Método de renta **o** capitalización de ingresos". Dentro de él hay **dos técnicas** (Art. 22): *capitalización directa* (Art. 23) y *capitalización por análisis de flujo de caja descontado* (Art. 25). El FCD **no es un método aparte**: es una técnica del método de renta. (Confirmado por lectura visual: *"En el desarrollo de este método podrán emplearse análisis por capitalización directa o capitalización por análisis de flujo de caja descontado."*)

6. **Corroboración secundaria (nivel b):** Arroyave & Asociados (abogadosaya.com) escribe: *"Comparación o mercado, renta o capitalización de ingresos, costo y técnica residual se mantienen como los cuatro métodos valuatorios (artículo 15)"*. Coincide exactamente con el texto que verifiqué.

### 1.3 Índice del Anexo Técnico (transcrito del propio anexo, pág. 2 del anexo)

- 1. Glosario de términos para la gestión valuatoria
- **2. Métodos valuatorios**
  - 2.1. Método de comparación o de mercado
  - 2.2. Método de Renta o Capitalización de Ingresos
    - 2.2.1. Capitalización por Flujo de Caja Descontado (FCD)
  - 2.3. Método del costo
    - 2.3.1. Vidas útiles de referencia
    - 2.3.2. Vida útil prolongada
    - 2.3.3. Tabla de Estados de Conservación
    - 2.3.4. Depreciación (2.3.4.1 construcciones/anexos; 2.3.4.2 valor actual; 2.3.4.3 tabla Ross-Heideck)
  - 2.4. Método (técnica) Residual
- 3. Procedimientos Específicos (3.1 Avalúo de Inmuebles Dotacionales o Institucionales; 3.2 Valoración de Maquinaria o Equipos)
- 4. Avalúos en zonas rurales
- 5. Plusvalía
- 6. Fórmulas de apoyo
- 7. Referencias bibliográficas

**No hay ninguna sección del anexo dedicada específicamente a propiedad horizontal.** Las reglas de PH están en el cuerpo de la resolución (Arts. 13.9.b, 14, 17, 19.2, 36, 37), no en el anexo, salvo el glosario y la lista de datos mínimos del estudio de mercado (§2.1).

---

## 2. QUÉ DICE CADA ARTÍCULO RELEVANTE

### 2.1 Regla general de selección de método (la pieza más importante para el cotejo)

**Artículo 13, numeral 9 — "Determinación del valor del inmueble"** (pág. 12, verificada por lectura visual directa):

> **9. Determinación del valor del inmueble:** determinar el valor comercial del inmueble mediante la aplicación de los métodos, técnicas, parámetros, procedimientos y lineamientos establecidos en la presente resolución, conforme a lo normado en el artículo 2.2.2.3.25 del Decreto 1170 de 2015 y teniendo en cuenta los siguientes aspectos:
>
> **a)** La selección del método valuatorio deberá obedecer a las características físicas, jurídicas y económicas del inmueble, así como a la disponibilidad y calidad de la información. El avaluador deberá justificar técnicamente la selección del método.
>
> **b)** Para inmuebles no sometidos al régimen de propiedad horizontal el avalúo deberá liquidarse y presentarse con los valores unitarios de terreno y construcción. Para inmuebles sometidos al régimen de propiedad horizontal el avalúo deberá liquidarse y presentarse en **valores integrales** por metro cuadrado de área privada.
>
> **c)** En los casos en que se solicite el avalúo de un área o fracción de terreno que haga parte de un inmueble de mayor extensión, el avalúo se realizará a partir del análisis del inmueble en su totalidad. [...]

**Consecuencias (nivel a, texto confirmado):**
- La selección del método **no está predeterminada por el tipo de inmueble ni por su condición jurídica (PH/NPH)**. Depende de (i) características físicas, jurídicas y económicas, (ii) disponibilidad y calidad de la información, y (iii) exige **justificación técnica expresa**.
- Para **PH** la regla de presentación es imperativa: **valores integrales por m² de área privada**.
- Para **NPH** la regla es la opuesta: **valores unitarios de terreno y construcción separados**.

### 2.2 Ítem de informe específico de PH

**Artículo 14, numeral 4, literal c)** (pág. 14, OCR):
> c) Datos del título de adquisición. **Si el inmueble está sometido al régimen de propiedad horizontal citar adicionalmente los datos del reglamento de Propiedad Horizontal y coeficientes de copropiedad.**

**Artículo 14** (pág. 8, OCR) exige incluir, entre las características de las construcciones:
> g. **Las características de las áreas comunes en inmuebles sometidos al régimen de propiedad horizontal.**

### 2.3 MÉTODO DE COMPARACIÓN O DE MERCADO (Arts. 16–21)

**Art. 16. Definición** (pág. 17, confirmado visualmente): procedimiento valuatorio que busca establecer técnicamente el valor comercial de un inmueble "a partir del análisis de las ofertas o transacciones recientes, de inmuebles similares o comparables con el que se esté valorando".

**Art. 17. Aplicación** (pág. 18, confirmado visualmente). Datos mínimos, entre ellos:
> **c)** Áreas de terreno, construcciones, cultivos y anexos constructivos; **así como las áreas privadas, garajes, depósitos, áreas libres para inmuebles sometidos al régimen de propiedad horizontal.**

Y, en el proceso de análisis de los datos de mercado:
> **a)** Para los inmuebles **no** sometidos al régimen de propiedad horizontal, los valores del terreno y de la construcción deberán ser analizados de manera independiente [...]
> **d)** Los valores de las construcciones se estimarán con base en los lineamientos técnicos del **método de costo**.
> **f)** Al efectuar la depuración de ofertas o transacciones de inmuebles **sometidos al régimen de propiedad horizontal, se debe considerar la existencia de garajes, depósitos, áreas libres (bien sean privados o comunes de uso exclusivo), para efectos de descontarlos y así obtener el valor integral correspondiente al área privada.**
> **e)** Se deberán documentar todos los datos de ofertas o transacciones utilizados.

*(Nota de transcripción: en el original impreso los literales de esta segunda lista aparecen en el orden a), b), c), d), **f), e)** — "f)" antes de "e)". Se reproduce el orden observado.)*

> **Parágrafo [del Art. 17]:** el método de comparación o de mercado **no constituye un proceso de igualación** de las ofertas o transacciones frente al inmueble objeto de estudio. Su aplicación consiste en el análisis técnico de las dinámicas del mercado para la construcción del valor [...]

**Art. 18. Análisis de Valores Integrales para Inmuebles No Sometidos al Régimen de Propiedad Horizontal:** permite, **como alternativa técnica complementaria**, usar valores unitarios integrales sobre área construida o sobre área de terreno para NPH. (Nótese: para NPH el valor integral es *complementario*; para PH es *la regla*.)

**Artículo 19, numeral 2 — Inmuebles sometidos al régimen de propiedad horizontal (PH)** (pág. 21, confirmado visualmente, lectura de alta confianza):

> **2. Inmuebles sometidos al régimen de propiedad horizontal (PH):**
> **a) El análisis estadístico de los datos se efectuará sobre valores integrales por metro cuadrado de área privada.**
> **b)** Cuando el dato de mercado (apartamento, local, oficina, etc.) cuente con garajes, depósitos, áreas libres o cualquier otra unidad, de carácter privado o comunes de uso exclusivo, **su valor se deberá descontar del valor negociado**, de manera que permita la comparación con el inmueble objeto de avalúo.
> **c)** Cuando se trate de inmuebles donde la PH refiera a la figura de **condominio o similar**, o cuya condición jurídica recaiga sobre el terreno o donde dada la condición de la PH su condición física se asemeja a un NPH, **aplicarán las mismas condiciones del numeral 1 del presente artículo, expresado en valores integrales.**

El encabezado del Art. 19 (pág. 20) enmarca ambos numerales: *"en virtud de la condición jurídica del inmueble en avalúo (**PH o NPH**), se debe tener en cuenta los siguientes lineamientos"*.

**Art. 20. Herramientas y medidas estadísticas:** catálogo enunciativo y **no taxativo** (tendencia central, dispersión, forma, técnicas robustas IQR/MAD, modelos estadísticos/econométricos). *"El uso de estas medidas es de carácter optativo y complementario. No constituyen un listado obligatorio ni reglas automáticas de decisión."*

> **Parágrafo 2:** Podrán emplearse como herramientas complementarias, conforme a la Norma Internacional de Valuación vigente (IVS), los **Modelos de Valuación Automatizados (AVM)**, herramientas avanzadas, modelos econométricos, geoestadísticos, de aprendizaje automático, **inteligencia artificial** u otros enfoques cuantitativos. El avaluador será responsable de garantizar confiabilidad e idoneidad; los modelos deberán (i) estar documentados en un manual auditable, (ii) sustentar calidad, suficiencia y ausencia de sesgo de los datos de entrada, (iii) incluir medición del error con métricas verificables (R², MAPE, RMSE), y (iv) contar con validación crítica del avaluador, **"sin que el resultado del modelo pueda presentarse por sí solo como un avalúo final"**.

**Artículo 21. Criterios para la Adopción del Valor** (pág. 22, OCR):
> [...] se establecen como límites máximos del coeficiente de variación los siguientes porcentajes:
> **Inmuebles urbanos: Hasta el 7.50%**
> **Inmuebles rurales: Hasta el 10.0%**
> **Parágrafo 1:** Cuando el avaluador no utilice la media aritmética como valor unitario de terreno, deberá sustentar su elección mediante el análisis conjunto de la media, la mediana, la presencia de valores atípicos, la comparabilidad de la muestra y las condiciones del mercado [...]

*(El umbral 7,5 % urbano / 10,0 % rural está corroborado por dos fuentes independientes: OCR del texto oficial y la fuente secundaria abogadosaya.com.)*

**Anexo técnico §2.1 — cierre de la sección:**
> "De conformidad con el método de comparación o de mercado, el tratamiento de las ofertas o transacciones de bienes similares o comparables **no consiste en un proceso automatizado de homogenización, sino en una depuración, clasificación, comparación y análisis de los datos.**"

**Anexo técnico §2.1 — Nota 2 (pág. 75, verificada por lectura visual):**
> **Nota 2:** Para efectos de la presente resolución, el procedimiento denominado **homologación u homologación mediante factores, no es aplicable** en la elaboración de los avalúos aquí regulados. Esta restricción metodológica de parte de IGAC no es reciente, se fundamenta en que **el uso de factores de ajuste para homogenizar la información del mercado distorsiona la realidad inmobiliaria y genera alteraciones en el valor.**

**Anexo técnico §2.1 — Nota 1:** para PH en figura de condominio debe incluirse, entre los datos de mercado, **el área del terreno y su unidad de medida**.

**Anexo técnico §2.1 — Datos mínimos del estudio de mercado para PH urbano/suburbano** (pág. 75, verificado): número de oferta, fecha de captura, tipo de inmueble (apartamento, oficina, local, consultorio, garaje, depósito), localización (municipio, comuna, localidad, sector, barrio, dirección y **nombre de la copropiedad**), coordenadas aproximadas, tipo de dato, valor de oferta, valor negociado, porcentaje de negociación, **área privada (m²) construida y libres**, **área de uso exclusivo y/o unidades privadas complementarias** (parqueaderos, depósitos), **valor global o unitario de esas unidades**, **valor unitario integral (COP/m²)**, observaciones, fuente, captura de pantalla, registro fotográfico.

### 2.4 MÉTODO DE RENTA O CAPITALIZACIÓN DE INGRESOS (Arts. 22–26)

**Artículo 22. Definición** (pág. 23, confirmado por lectura visual, alta confianza):
> Es el procedimiento valuatorio que busca establecer técnicamente el valor comercial del inmueble **a partir de las rentas o ingresos que se puedan obtener del mismo o de inmuebles similares y comparables** por sus características físicas, de uso y ubicación. Este procedimiento está basado en la premisa que los inmuebles cuentan con un potencial de generación de rentas y beneficios económicos e ingresos. **En el desarrollo de este método podrán emplearse análisis por capitalización directa o capitalización por análisis de flujo de caja descontado.**

**Artículo 23. Capitalización Directa:** `A = r / i` (A = avalúo o valor comercial; r = renta, canon de arrendamiento o ingreso; i = tasa de capitalización de la renta). Regla de coherencia bruto/neto. La variable **r** admite deducciones del propietario (administración o pago de la copropiedad, impuesto predial, seguros, mantenimiento y otros).

La variable **i** (pág. 24): *"deberá derivarse, preferiblemente, de la relación observada en el mercado entre los valores del canon de arrendamiento y los precios de venta de inmuebles comparables (observación directa del mercado). En su defecto, podrá construirse siempre que se cuente con el soporte técnico correspondiente."*

> **Parágrafo [Art. 24]:** No se tendrán en cuenta rentas asociadas a marcas, patentes, secretos empresariales, derechos de autor, nombres comerciales, derechos deportivos, espectro radioeléctrico, fondo de comercio, prima comercial y otros similares.

**Artículo 24. Aplicación de la Capitalización Directa:** (a) investigar **los contratos vigentes** que determinen las rentas del inmueble objeto de avalúo **y/o comparables**; (b) **investigación de mercado de arrendamiento de inmuebles similares**; (c) verificar que los arrendamientos correspondan al mercado; (d) establecer la tasa según el uso y localización comparable; (e) revisar que el canon mensual capitalizable **no exceda el máximo legal permitido** (Ley 820 de 2003) para vivienda urbana.

**Artículo 25. Capitalización por Análisis de Flujo de Caja Descontado:** exige dos tasas — **tasa de descuento** (flujos netos de efectivo futuros, según nivel de riesgo del tipo de inmueble) y **tasa terminal de capitalización** (valor continuo).

**Artículo 26. Aplicación del FCD:** 4 pasos — (1) estimación de ingresos y gastos (gastos mínimos: predial, seguros, mantenimiento, administración, servicios públicos, imprevistos, comisión por administración inmobiliaria); (2) construcción del flujo de caja (periodicidad anual, semestral o mensual); (3) determinación de la tasa de descuento (procedimientos directos de mercado o indirectos de construcción, con soporte técnico); (4) **el valor del inmueble corresponde al Valor Presente Neto (VPN) de los flujos descontados**.

**Hallazgo crítico (nivel a):** **ni el Art. 22 ni el Art. 23 ni el Art. 24 establecen condición, restricción o supuesto de excepcionalidad alguna para usar el método de renta.** Lo único que condiciona es que las rentas sean *obtenibles* — del propio inmueble **o de inmuebles similares y comparables** (renta imputada) — y que exista estudio de mercado de arriendos.

### 2.5 MÉTODO DEL COSTO (Arts. 27–30)

**Artículo 27. Definición** (pág. 26, OCR): procedimiento mediante el cual se determina técnicamente el valor comercial total de un inmueble "a partir de la estimación del valor del terreno y del valor actual o depreciado de las construcciones y anexos constructivos que formen parte del bien". Variables declaradas en el texto:

- **VC** = Valor comercial del inmueble
- **CT** = Costo total de reposición o reproducción a nuevo de las construcciones y anexos constructivos
- **D** = Depreciación acumulada
- **VT** = Valor total del terreno

> *(Advertencia de fiabilidad: la **ecuación** del Art. 27 no es legible de forma fiable en el escaneo —solo se leen los nombres de las variables. La forma `VC = CT − D + VT` es **inferencia mía** a partir de las definiciones, no texto confirmado. Debe verificarse en el PDF oficial.)*

Reglas adicionales del Art. 27: el CT debe soportarse en fuentes técnicas idóneas y/o presupuestos de obra; **la depreciación acumulada deberá calcularse mediante un modelo continuo que incorpore la edad y el estado de conservación**; el valor del terreno se determina por cualquiera de las metodologías técnicamente viables de la resolución.

**Artículo 28. Costo total de Reposición o Reproducción a Nuevo** — **dos procesos**:
> **Costo de reposición:** valor a nuevo de la construcción, calculado como el costo total de construir **una edificación similar** con **materiales y técnicas actuales**.
> **Costo de reproducción:** valor estimado a partir del costo para **reproducir una réplica**, empleando **los mismos materiales o materiales sustitutos**, procurando mantener los diseños y métodos constructivos originales. **Aplicable a los bienes de interés cultural (BIC).**

El costo total = costos directos + indirectos, sustentado en presupuestos que consideren los costos del lugar. **Parágrafo 2:** si no existe información técnica, el avaluador puede estimar con base en tipologías constructivas, modelos de costos, bases de datos o publicaciones especializadas, dejando constancia.

**Artículo 29. Vida útil:** periodo durante el cual el inmueble es útil. Las edificaciones cuya edad **supere la vida útil de referencia** de la tabla guía del anexo se clasifican, para el cálculo de la depreciación, como **edificaciones de vida útil prolongada** = edad + vida remanente estimada según el estado de conservación actual.

**Artículo 30. Determinación de la Depreciación Acumulada:** *"se deberán emplear **modelos continuos, excluyendo los modelos discontinuos o en escaleta**"*; se aplica el sistema que combina las teorías de **Ross y Heideck (modelo Ross-Heideck)**, que incorpora depreciación por edad y por estado de conservación. Se define el factor de depreciación FD con X = edad, n = vida útil, E = coeficiente asociado a la calificación del estado de conservación según criterios de mantenimiento/conservación de Heideck, y `E = (100 − Coeficiente Depreciación)/100`.
> **Parágrafo:** Las construcciones catalogadas como **BIC**, de conservación arquitectónica, históricas o monumentales, así como aquellas cuya antigüedad constituya atributo de valor, **no estarán sujetas a depreciación acumulada por edad**; su valor sí se afecta por el estado de conservación actual.

**Anexo técnico §2.3.1 — Vidas útiles de referencia** (Tabla 2): categorías *Temporales (desmontables)*, *Vida Corta*, *Media*, *Vida Larga*, *Permanentes*, *Patrimoniales*, con valores **30 / 50 / 70 / 100 / >100** años. *(La asignación exacta de cada valor a cada categoría es **dudosa** en el escaneo —la tabla se leyó desordenada; verificar en el PDF.)* Nota 2 de la tabla: las vidas útiles son **valores de referencia** y **deberán utilizarse en la aplicación del método del costo**. Existe además categoría *Especiales (edificaciones no tradicionales)* y *Prolongada (vida útil sustentada)*.

### 2.6 MÉTODO (TÉCNICA) RESIDUAL (Arts. 31–34)

**Artículo 31. Definición:** determina el valor comercial del inmueble, **generalmente para el terreno**, a partir del monto total de las ventas de un proyecto urbanístico o constructivo conforme a la normatividad urbanística y al mercado del producto final vendible. Para el valor total del terreno **se descuentan al monto de ventas proyectadas los costos totales y la utilidad esperada**.
> **Parágrafo:** el método residual deberá desarrollarse bajo el principio de **mayor y mejor uso** [...] el mayor y mejor uso **no corresponde únicamente al máximo permitido por la norma urbanística**, sino al uso aceptado y demandado por el mercado al momento de la valoración.

**Artículo 32. Técnicas:** dos — **Residual Estático** (no incorpora el tiempo; lotes útiles o proyectos de corto plazo) y **Residual Dinámico** (incorpora la variación de ingresos y costos en el tiempo, etapas, velocidad de ventas, programación constructiva; proyectos de mediano y largo plazo; la tasa de descuento debe estar sustentada).

**Artículo 33. Aplicación** — 9 aspectos: análisis normativo (cesiones, área neta urbanizable, área útil, volumetría, edificabilidad, usos); estimación de ventas totales **sustentada mediante el método de comparación o de mercado**; costos de urbanismo (evitar duplicar indirectos); costos de construcción (solo directos); costo total del proyecto; utilidad esperada (concordante con uso, localización, TIR del sector, **VPN ≥ 0**); soporte de la información; **resultado = valor total del inmueble (terreno + construcción), por lo que no se adiciona de nuevo el valor del terreno**; presentación desagregada (estimar construcción por el método del costo y descontarla).
> **Parágrafo:** cuando el inmueble se encuentre desarrollado bajo su mayor y mejor uso, **el método podrá aplicarse de manera excepcional** con el único fin de establecer el valor del terreno [...]

**Artículo 34. Estimación del Valor de un Terreno en Bruto (VTB):** cuando no sea posible determinarlo por comparación directa **ni resulte aplicable el método residual**, se puede estimar a partir de un terreno urbanizado de condiciones similares: `VTB = (Vtu (1 − g)) − Cu` *(la notación de la ecuación es **parcialmente legible**; debe verificarse en el PDF oficial)*, con Vtu = valor del terreno urbanizado de referencia **determinado mediante comparación o de mercado**, g = ganancia por la acción de urbanizar, Cu = costos de urbanismo por m² de área útil. Define **Área Útil (AU)** y %AU = (AT − AF − C)/AT.

### 2.7 REGLAS ESPECÍFICAS DE PROPIEDAD HORIZONTAL

#### 2.7.1 Artículo 36 — el artículo nuclear (texto verificado por lectura visual directa)

> **Artículo 36. Avalúos de Inmuebles Sometidos al Régimen de Propiedad Horizontal.** El avalúo se practicará **exclusivamente sobre las áreas privadas legalmente constituidas**, teniendo en cuenta **los derechos derivados de los coeficientes de copropiedad**.
>
> En los inmuebles que están sometidos al régimen de propiedad horizontal, la valoración se realizará considerando los siguientes aspectos:
>
> **1. Valor integral:** los valores comerciales deberán determinarse como **un valor integral por metro cuadrado**.
>
> **2. Parqueaderos, garajes, depósitos o áreas libres:** se debe verificar si estas unidades tienen restricciones como servidumbres. **Si cuentan con una matrícula inmobiliaria independiente** a la de la unidad principal (apartamento, local, oficina, etc.), **su valor se determinará de forma global o por metro cuadrado (m²)**, en concordancia con el mercado inmobiliario. **Por el contrario, si corresponden a bienes comunes de uso exclusivo, su valor se considerará implícito dentro del valor integral de la unidad principal y no se liquidarán de manera independiente.**
>
> **3. Áreas privadas diferenciadas:** cuando el área privada del inmueble esté compuesta por **área privada construida y área privada libre** (patios, terrazas, balcones, entre otros), **a cada una de estas se le deberá asignar valor de manera diferenciada**, de acuerdo con sus características.
>
> **4. Usos:** los usos a considerar en el avalúo son aquellos **aprobados en las respectivas licencias de urbanismo y/o construcción** de la edificación de la que hace parte la unidad privada objeto de estudio, los cuales deben **guardar concordancia con lo formalizado en el reglamento de propiedad horizontal**.
>
> **Parágrafo 1.** En aquellos casos en que el inmueble se encuentre sometido al régimen de propiedad horizontal bajo la **figura de condominio o similar, en donde el terreno corresponde al área privada**, el avalúo se practicará **tanto para el terreno como para la construcción**; en todo caso deberá hacerse el análisis y la presentación del avalúo **considerando el valor integral del inmueble**.
>
> **Parágrafo 2.** Cuando el inmueble objeto de avalúo presente un **área atípica** respecto a la tendencia predominante en el mercado inmobiliario de referencia y dicha condición **dificulte la aplicación directa del método de comparación o de mercado o del método renta o capitalización de ingresos**, el avaluador podrá efectuar un análisis técnico basado en **muestras comparables de menor área, aplicando un procedimiento análogo al estipulado en el artículo subsiguiente**.

#### 2.7.2 Hallazgo decisivo: el Art. 36 NO prescribe método

**El Artículo 36 no establece ningún método preferente, principal, obligatorio ni subsidiario para propiedad horizontal.** Sus cuatro numerales son reglas de **objeto** (qué se avalúa: áreas privadas) y de **valor** (cómo se expresa y descompone: valor integral, tratamiento de garajes, áreas diferenciadas, usos). La selección del método sigue rigiéndose por la regla general del **Art. 13.9.a** (características + información + justificación técnica).

Además, el **Parágrafo 2 del Art. 36 menciona expresamente dos métodos como de "aplicación directa" para PH** —el de comparación o de mercado **y** el de renta o capitalización de ingresos—, lo que confirma que la norma contempla **ambos** como métodos ordinariamente disponibles en PH.

**La única regla de "preferencia / excepcionalidad" de la resolución está en el Artículo 35 (inmuebles de uso dotacional o institucional), no en PH** (texto verificado por lectura visual):

> **Artículo 35. Avalúos de Inmuebles de Uso Dotacional o Institucional.** [...] el avaluador deberá proceder de la siguiente manera:
> **1. Preferencia:** se deberán aplicar los métodos valuatorios establecidos en la presente resolución, atendiendo a la disponibilidad, calidad y verificabilidad de la información técnica y de mercado inmobiliario existente.
> **2. Excepcionalidad:** en ausencia de evidencia de mercado suficiente y verificable, o cuando la naturaleza del inmueble y sus restricciones de uso impidan la estimación de ingresos o rentas imputadas, se podrá emplear el procedimiento descrito en el Anexo Técnico de esta resolución.
> **3. Análisis de Consistencia:** en todo caso, el avaluador deberá contrastar y sustentar que el resultado obtenido guarde estricta coherencia con la dinámica inmobiliaria de la zona o municipio donde se ubica el inmueble.

El procedimiento del anexo al que remite el Art. 35.2 es el **§3.1.1 "Procedimiento para el cálculo de un factor de relación por uso"** (factor entre valores unitarios de terreno de usos de alta dinámica inmobiliaria y usos dotacionales). **Es exclusivo de dotacionales.**

#### 2.7.3 Artículo 37 — NPH que se asimila a copropiedad

> **Artículo 37. Avalúos de Inmuebles No Sometidos al Régimen de Propiedad Horizontal que presentan Características Físicas de una Copropiedad.** Cuando el inmueble no esté sometido al régimen de propiedad horizontal, pero por su uso y conformación **se asimile a estos** (oficinas, locales, apartamentos, entre otros), y la investigación de mercado se haya realizado para inmuebles que **sí** están sometidos al régimen de propiedad horizontal, el avaluador deberá realizar la correcta liquidación, empleando la siguiente ecuación:
>
> **VTI = (APE × VI) − CA**
>
> En donde: **VTI** = Valor Total del Inmueble; **APE** = Área Privada Estimada; **VI** = Valor Integral por metro cuadrado; **CA** = Costo Total de Adecuación.

*(El Art. 37 continúa en la pág. 36 con la ecuación de APE y reglas sobre costos de adecuación —licencias, permisos, impuestos, trámites en curaduría y elaboración y registro del reglamento de PH— que se descuentan del VTI; la advertencia de que **el valor integral ya incluye el terreno y por tanto no debe agregarse de nuevo**; y que el VTI debe discriminar terreno y construcción apoyándose en los métodos de mercado y de costo. Lectura de pág. 36 vía OCR: nivel a-b, recomendable verificar.)*

#### 2.7.4 Otras disposiciones con incidencia en PH

- **Art. 40 (BIC):** para inmuebles **sometidos a PH**, "el valor comercial se determinará **como un valor integral**"; para NPH se discrimina terreno (método de comparación) y construcción (método del costo). Métodos admitidos: comparación, costo o renta "según la disponibilidad y calidad de la información".
- **Art. 45 (Derecho Real Accesorio de Superficie):** criterios de asignación de método — **residual** para el valor del área libre aprovechable; **renta o capitalización de ingresos** para los ingresos de las edificaciones; **comparación o de mercado** para el valor de arrendamiento de las unidades superficiarias y soporte de los otros dos.
- **Art. 59 (Transitoriedad):** los avalúos en desarrollo y las solicitudes de revisión, recursos y actuaciones iniciadas antes de la vigencia continúan rigiéndose por las disposiciones vigentes al momento de su iniciación.
- **Art. 60 (Vigencia y Derogatoria):** rige a partir de su **publicación en el Diario Oficial** y deroga la Resolución 620 de 2008, el artículo 13 y los incisos 1, 2 y 3 del artículo 14 de la Resolución 898 de 2014 del IGAC, así como las demás disposiciones contrarias. *(Lectura OCR de la pág. 56; la ficha del IGAC menciona solo los incisos 1–3 del art. 14 de la Res. 898/2014 — **verificar el alcance exacto respecto del art. 13**.)*
- **Art. 61 (Publicación):** publicar en el Diario Oficial y en la web del IGAC (art. 65 Ley 1437 de 2011).

### 2.8 Glosario del anexo — definiciones relevantes (verificadas por lectura visual)

> **Valor Integral:** el término valor integral se utiliza tanto en el contexto de inmuebles sometidos al régimen de propiedad horizontal (PH) como en aquellos que no lo están (NPH). Su aplicación varía según el caso:
> • **Inmuebles en Propiedad Horizontal (PH):** El valor integral unitario es el resultado de **dividir el valor total de un avalúo, oferta o transacción entre el área privada (en m²)**. En este tipo de bienes, **dicho valor involucra de forma implícita la proporción equivalente que le corresponde al inmueble sobre las áreas o bienes comunes.**
> • **Inmuebles no sometidos a Propiedad Horizontal (NPH):** El valor integral unitario se obtiene al dividir el valor total del avalúo, oferta o transacción entre el área del terreno o el área de construcción, según el caso a analizar.

> **Régimen de Propiedad Horizontal:** sistema jurídico que regula el sometimiento a propiedad horizontal de un edificio o conjunto, construido o por construirse.

> **Área privada construida:** extensión superficial cubierta de cada bien privado, **excluyendo los bienes comunes localizados dentro de sus linderos**, de conformidad con las normas legales.

> **Área privada libre:** extensión superficial privada semi descubierta o descubierta, **excluyendo los bienes comunes localizados dentro de sus linderos**, de conformidad con las normas legales.

> **Avalúo Comercial:** es el precio más probable por el cual un predio se ofertaría en un mercado donde el comprador y el vendedor actuarían libremente, sabiendo las condiciones físicas y jurídicas que afectan el bien.

> **Comparabilidad:** calidad de un inmueble para ser confrontado técnica y económicamente con otros bienes referentes [...] **Esta noción no implica identidad absoluta, sino la existencia de similitudes sustanciales en los atributos que el mercado valora.**

> **Tasa de capitalización:** parámetro que permite convertir un ingreso estabilizado en un valor presente [...]

**Hallazgos negativos del glosario (verificados):**
- **No hay entrada de glosario para "coeficiente" ni "coeficiente de copropiedad"** en el anexo técnico. El término se usa en los Arts. 14.4.c y 36 sin definición propia → su contenido debe tomarse del régimen legal de PH (Ley 675 de 2001).
- No hay entrada para "propiedad horizontal" como tal (solo "Régimen de Propiedad Horizontal").
- No hay definición de "unidad privada" ni de "bienes comunes de uso exclusivo" en el glosario revisado.

---

## 3. MATRIZ DE COTEJO: reglas ARHIAX vs. Resolución 941 de 2026

**Leyenda de veredictos:** ✅ **CONFIRMA** · ⚠️ **MATIZA** (parcialmente correcto, requiere ajuste o condicionamiento) · ❌ **CONTRADICE** · ➕ **VACÍO** (la norma exige algo que el sistema no cubre)

### 3.1 Regla implementada #1 — "Propiedad horizontal terminada → método principal de Comparación de Mercado (M1), 100 %"

| Aspecto | Veredicto | Fundamento normativo |
|---|---|---|
| Que la comparación de mercado sea **aplicable** a PH | ✅ **CONFIRMA** | Art. 15 lit. a); Arts. 16–21; Art. 17 lit. c) y f); **Art. 19 num. 2** (dedica un numeral entero a PH *dentro* del método de comparación); Art. 36 par. 2 |
| Que sea el **método principal / obligatorio** para PH | ❌ **NO CONFIRMADO — MATIZA** | **Art. 15** lista los cuatro métodos **sin jerarquía**; **Art. 13.9.a** establece que la selección "deberá obedecer a las características físicas, jurídicas y económicas del inmueble, así como a la disponibilidad y calidad de la información" y que "el avaluador deberá **justificar técnicamente** la selección"; **Art. 36 no prescribe método alguno**; **Art. 36 par. 2** trata la comparación **y** la renta como métodos de "aplicación directa" en PH. La única regla de preferencia de la resolución es el **Art. 35** (dotacional/institucional). |
| Que sea **100 %** (asignación exclusiva del valor por comparación) | ⚠️ **MATIZA** | El Art. 17 lit. d) obliga a que **"los valores de las construcciones se estimarán con base en los lineamientos técnicos del método de costo"** — es decir, **aun usando comparación de mercado hay un componente obligatorio del método del costo** en la estimación de construcciones. Un "100 % comparación" sin componente de costo en las construcciones es contrario al Art. 17 lit. d). |
| Que la condición "**terminada**" active la regla | ❌ **SIN RESPALDO NORMATIVO — MATIZA** | **No existe en la norma ninguna distinción PH terminada / en construcción / en planos como criterio de selección de método.** El Art. 36 se aplica a "inmuebles sometidos al régimen de propiedad horizontal" y exige que el avalúo se practique "exclusivamente sobre las **áreas privadas legalmente constituidas**". *(Inferencia mía, nivel c: "legalmente constituidas" parece calificar la constitución **jurídica** de las áreas privadas —vía reglamento de PH— y no la terminación física de la obra. Si ARHIAX condiciona la regla a la terminación física, ese criterio no proviene de la Resolución 941.)* |
| **Presentación del avalúo de PH** | ❌ **RIESGO DE CONTRADICCIÓN** | Art. 13.9.b: para PH el avalúo **debe liquidarse y presentarse en valores integrales por m² de área privada** (no en terreno + construcción separados, como en NPH). Art. 19.2.a y Art. 36.1 lo reiteran. **Si ARHIAX emite para PH una liquidación separada de terreno y construcción, contradice el Art. 13.9.b.** |

### 3.2 Regla implementada #2 — "Capitalización de Rentas (M3) solo en casos excepcionales con renta demostrable"

| Aspecto | Veredicto | Fundamento normativo |
|---|---|---|
| Que el método de renta sea **aplicable** a PH | ✅ **CONFIRMA** | Art. 15 lit. b); Arts. 22–26; **Art. 36 par. 2** lo nombra expresamente junto a la comparación como método de "aplicación directa" para PH |
| Que sea **excepcional** en PH | ⚠️ **MATIZA** | La norma **no lo limita ni lo hace excepcional para PH**. Tratarlo como excepcional es una política interna admisible, pero **no está en la Resolución 941** y debe justificarse caso a caso bajo el Art. 13.9.a (que obliga a elegir el método técnicamente procedente y a justificarlo). |
| Que exija "**renta demostrable**" (del propio inmueble) | ❌ **CONTRADICE (parcialmente)** | **Art. 22:** el valor se establece "a partir de las rentas o ingresos que se puedan obtener **del mismo o de inmuebles similares y comparables**" → **la norma admite renta imputada de comparables**, no exige arrendamiento propio existente. **Art. 24 lit. b):** exige "investigación de mercado de arrendamiento de inmuebles similares". **Art. 24 lit. a):** los contratos vigentes pueden ser del inmueble **"y/o comparables"**. → Un requisito de "renta demostrable del propio inmueble" es **más estricto que la norma**. |
| Que la tasa de capitalización deba provenir de mercado | ✅ **CONFIRMA** | Art. 23 (pág. 24): la tasa i "deberá derivarse, preferiblemente, de la relación observada en el mercado entre los valores del canon de arrendamiento y los precios de venta de inmuebles comparables (observación directa del mercado)". En su defecto puede construirse con soporte técnico. |
| Que el techo legal de la Ley 820/2003 se valide | ➕ **VACÍO A VERIFICAR** | Art. 24 lit. e): el canon mensual capitalizable **no debe exceder el máximo legal** de la Ley 820 de 2003 para vivienda urbana. Debe confirmarse si ARHIAX lo valida. |

### 3.3 Regla implementada #3 — Nomenclatura interna M1 / M2 / M3

| Aspecto | Veredicto | Fundamento normativo |
|---|---|---|
| Uso de etiquetas M1/M2/M3 como nombres de método | ❌ **CONTRADICE** | Art. 15 fija los nombres oficiales: a) Método de comparación o de mercado; b) Método de renta o capitalización de ingresos; c) Método del costo; d) Método (técnica) residual. Las etiquetas M1/M2/M3 no existen en la norma y **no pueden usarse en el informe técnico** (Art. 14 num. 9 exige señalar los "métodos aplicados"; Art. 15 par. exige indicar las fuentes de cada dato). |
| "M2 = costo de reposición" | ⚠️ **MATIZA / CONTRADICE** | El método se llama **Método del costo** (Art. 15 lit. c). "Reposición" es uno de **dos procesos** internos (Art. 28), siendo el otro **reproducción** (réplica con materiales/métodos originales, **aplicable a BIC**). La etiqueta ARHIAX colapsa el método con uno solo de sus procesos y omite el de reproducción. |
| Existencia de M4 | ➕ **VACÍO (omisión)** | **Falta el Método (técnica) residual** (Art. 15 lit. d; Arts. 31–34; anexo §2.4), con sus dos técnicas (estático / dinámico, Art. 32) y el método de valor de terreno en bruto (Art. 34). También falta el **FCD como técnica del método de renta** (Art. 25–26), que no es un método autónomo. |

### 3.4 Reglas adicionales de la norma que ARHIAX debe cumplir en PH (verificar implementación)

| # | Regla de la Resolución 941 | Ancla | Estado en ARHIAX |
|---|---|---|---|
| 1 | Avalúo de PH se practica **exclusivamente sobre áreas privadas legalmente constituidas**, considerando **los derechos derivados de los coeficientes de copropiedad** | **Art. 36** (intro) | ➕ por verificar |
| 2 | Para PH, **descontar del valor negociado** de cada comparable el valor de garajes, depósitos, áreas libres o cualquier unidad privada o común de uso exclusivo, **para obtener el valor integral del área privada** | **Art. 19 num. 2 lit. b)**; Art. 17 lit. f) | ➕ por verificar |
| 3 | En PH, el **análisis estadístico se hace sobre valores integrales por m² de área privada** | **Art. 19 num. 2 lit. a)** | ➕ por verificar |
| 4 | **Áreas privadas diferenciadas:** si el área privada comprende área privada construida y área privada libre (patios, terrazas, balcones), **asignar valor diferenciado a cada una** | **Art. 36 num. 3** | ➕ por verificar |
| 5 | **Garajes/parqueaderos/depósitos:** con **matrícula inmobiliaria independiente** → se valoran de forma global o por m²; si son **bienes comunes de uso exclusivo** → **valor implícito** en el valor integral de la unidad principal y **no se liquidan por separado** | **Art. 36 num. 2** | ➕ por verificar |
| 6 | **Usos:** solo los aprobados en las licencias de urbanismo y/o construcción, concordantes con el **reglamento de propiedad horizontal** | **Art. 36 num. 4** | ➕ por verificar |
| 7 | PH en **figura de condominio** con terreno = área privada: avalúo **de terreno y de construcción**, pero análisis y presentación **con el valor integral del inmueble** | **Art. 36 par. 1**; Art. 19.2.c; anexo §2.1 Nota 1 | ➕ por verificar |
| 8 | **Área atípica** en PH: análisis técnico con **muestras comparables de menor área**, con procedimiento análogo al Art. 37 | **Art. 36 par. 2** | ➕ por verificar |
| 9 | NPH asimilable a copropiedad: **VTI = (APE × VI) − CA**, descontando costos de adecuación; el valor integral **ya incluye el terreno** (no volver a sumarlo) | **Art. 37** | ➕ por verificar |
| 10 | **Prohibida la homologación mediante factores** (factores de ajuste para homogenizar el mercado) | **Anexo técnico §2.1 Nota 2**; y §2.1 cierre ("no consiste en un proceso automatizado de homogenización") | ➕ **crítico** si ARHIAX homologa comparables con factores |
| 11 | **Coeficiente de variación máximo: 7,50 % urbano / 10,0 % rural** | **Art. 21** | ➕ por verificar umbral |
| 12 | El informe debe citar **reglamento de PH y coeficientes de copropiedad** y describir **las características de las áreas comunes** en PH | **Art. 14 num. 4 lit. c)**; Art. 14 num. 2 lit. g) | ➕ por verificar |
| 13 | Estudio de mercado en PH debe registrar: **nombre de la copropiedad**, área privada construida **y libres**, área y valor (global o unitario) de unidades privadas complementarias, y **valor unitario integral (COP/m²)** | **Anexo técnico §2.1** (pág. 75) | ➕ por verificar |
| 14 | Si se usan **AVM / IA / modelos**: manual auditable, ausencia de sesgo de datos, métricas de error (R², MAPE, RMSE) y validación del avaluador; **el modelo no puede presentarse por sí solo como avalúo final** | **Art. 20 par. 2** | ➕ por verificar |
| 15 | Para PH, **valores integrales por m² de área privada** en la liquidación y presentación | **Art. 13.9.b**; Art. 19.2.a; Art. 36.1 | ❌ si hoy se presenta terreno+construcción separados |
| 16 | Los **valores de las construcciones** se estiman con los lineamientos del **método del costo**, aun en comparación de mercado | **Art. 17 lit. d)** | ➕ por verificar |

---

## 4. SÍNTESIS DEL COTEJO

1. **La regla "PH → Comparación de Mercado como método principal, 100 %" NO está en la Resolución 941.** La norma: (i) enumera cuatro métodos sin jerarquía (Art. 15); (ii) hace depender la selección del método de las características del inmueble y de la información disponible, con **justificación técnica obligatoria** (Art. 13.9.a); (iii) dedica el Art. 36 a PH sin prescribir método; y (iv) menciona expresamente **comparación y renta** como métodos de aplicación directa en PH (Art. 36 par. 2). Como **default operativo interno** es defendible, pero debe (a) justificarse caso a caso y (b) no excluir los demás métodos.
2. **La única regla de jerarquía de métodos de la resolución es para inmuebles de uso dotacional o institucional (Art. 35: Preferencia / Excepcionalidad / Análisis de Consistencia).** Conviene verificar que ARHIAX no haya importado por error ese esquema a PH.
3. **"M1 100 %" tropieza con el Art. 17 lit. d):** los valores de las construcciones deben estimarse con los lineamientos del **método del costo**, incluso dentro del método de comparación.
4. **"M3 solo excepcional y con renta demostrable" es más restrictivo que la norma.** El Art. 22 admite renta **imputada de comparables** y el Art. 24 lit. b) exige estudio de mercado de arriendos; el Art. 36 par. 2 trata la renta como método de aplicación directa en PH.
5. **La etiqueta M2 "costo de reposición" es imprecisa y el sistema carece del cuarto método.** El método se llama **Método del costo** y contiene **reposición *y* reproducción** (Art. 28). Falta el **Método (técnica) residual** (Art. 15 lit. d; Arts. 31–34).
6. **El riesgo normativo más alto está en la presentación:** para PH la norma exige **valores integrales por m² de área privada** (Art. 13.9.b), no la discriminación terreno/construcción propia de NPH.
7. **Prohibición relevante:** la **homologación mediante factores** no es aplicable (anexo técnico §2.1 Nota 2). Si el motor de ARHIAX ajusta comparables con factores, contradice la norma.
8. **Componentes de valor en PH que el sistema debería tratar explícitamente:** garajes/depósitos con matrícula independiente vs. bienes comunes de uso exclusivo (Art. 36.2), y **valor diferenciado** entre área privada construida y área privada libre (Art. 36.3).

---

## 5. VACÍOS E INCERTIDUMBRES

### 5.1 Puntos resueltos durante la investigación (para trazabilidad)

- **"valores integrales" vs. "valores integrados" (Art. 13.9.b).** El OCR y mi lectura visual del escaneo dan **"integrales"**; una lectura independiente sugirió "integrados". Se resuelve como **"integrales"** porque (i) el Art. 19.2.a usa la frase casi idéntica *"valores integrales por metro cuadrado de área privada"* (lectura de alta confianza), (ii) el glosario define **"Valor Integral"**, y (iii) "integrados" no aparece en ningún otro lugar del acto. **Recomendación: confirmar la palabra en el PDF oficial**, pues es la que fija la regla de presentación del avalúo de PH.
- **El Art. 36 se verificó por lectura visual directa de las páginas 34 y 35** (dos lecturas convergentes), por lo que su contenido es de **alta confianza**.
- **Anexo_Final_.pdf NO es el anexo técnico**: es el suplemento de **figuras** (27 imágenes: esquema del FCD, esquema del método residual, construcción de costos, influencia de la forma, ejemplos de lotes). El anexo técnico (con glosario, tablas de vida útil, Ross-Heideck y modelos de costos agrícolas/pecuarios) es la **parte final de la resolución escaneada, páginas 57 a 117** (página del anexo N = página del PDF N − 56).

### 5.2 Lo que NO se pudo confirmar

| Vacío | Detalle | Cómo cerrarlo |
|---|---|---|
| **Fórmulas matemáticas** | Las ecuaciones del **Art. 27** (valor comercial del método del costo), **Art. 30** (depreciación, factor FD, valor actual), **Art. 34** (VTB, %AU) y **Art. 37** (APE) **no son legibles de forma fiable** en el escaneo. Se leyeron los nombres de las variables, no los símbolos. | Leer el PDF oficial en pantalla, con zoom, en las págs. 26, 28–29, 32–33 y 35–36. |
| **Tabla 2 "Vidas útiles de referencia"** | Se leyeron las categorías (Temporales/Desmontables, Vida Corta, Media, Vida Larga, Permanentes, Patrimoniales; Especiales; Prolongada) y los valores 30/50/70/100/>100, pero **el emparejamiento fila–valor quedó desordenado por el OCR**. | Anexo técnico pág. 22 (PDF pág. 78). |
| **Tabla 7 "Coeficientes K de Ross-Heideck"** | Tabla numérica extensa (págs. 36–39 del anexo); el OCR la devolvió corrupta. No debe usarse ninguna cifra de este informe proveniente de esa tabla. | Anexo técnico págs. 36–39 (PDF págs. 92–95). |
| **Fecha exacta de entrada en vigencia** | El Art. 60 dice que rige **a partir de su publicación en el Diario Oficial**. Lo que consta es la **publicación web del 12 de agosto de 2026**. | Consultar la edición del **Diario Oficial** para fijar la fecha de vigencia y, con ella, la frontera del régimen de transitoriedad (Art. 59). |
| **Alcance de la derogatoria del Art. 60** | La pág. 56 (OCR) dice que deroga "la Resolución 620 de 2008, **el artículo 13** y los incisos 1, 2 y 3 del artículo 14 de la Resolución 898 de 2014"; la ficha del IGAC menciona solo los incisos 1–3 del art. 14. | Verificar el texto exacto del Art. 60 en el PDF oficial. |
| **"Coeficiente de copropiedad"** | El glosario del anexo **no lo define** (ni define "unidad privada" ni "bienes comunes de uso exclusivo"), pese a que el Art. 36 lo hace determinante. | Acudir al régimen legal de PH (**Ley 675 de 2001**) y al reglamento de PH de cada copropiedad (que el Art. 14.4.c obliga a citar). |
| **Artículos no revisados en detalle** | Este informe se centró en métodos y PH. **No se leyeron en detalle los Arts. 53–57** (capítulos de plusvalía sobre incremento por obras públicas y modelos econométricos) ni los Arts. 6–12 y 43–44, 46–48, 49–52. Su contenido es ajeno al foco, pero no puede afirmarse que no contengan alguna disposición de PH. | Leer Título VII completo (págs. 50–54). |
| **Distinción "PH terminada"** | **No se encontró en la norma ninguna regla que distinga PH terminada de PH en construcción o en planos**, ni como criterio de método ni de valor. Si ARHIAX la usa, es un supuesto propio. | Confirmar leyendo Título II y IV completos; o reformular la regla como decisión interna documentada. |
| **Nota 2 del anexo §2.1 — alcance de la prohibición** | El texto prohíbe "el procedimiento denominado homologación u homologación mediante factores". No precisa si abarca cualquier factor corrector (p. ej. por área o por antigüedad) o solo la homologación clásica de la Res. 620/2008. | Anexo técnico pág. 19 (PDF pág. 75), verificada visualmente; el alcance interpretativo debe discutirse con criterio técnico. |

### 5.3 Qué debe leer directamente un avaluador/abogado en el PDF oficial

Por orden de prioridad:

1. **Art. 15** (PDF pág. 17) — la lista de los cuatro métodos (nombre exacto).
2. **Art. 13 num. 9 lits. a) y b)** (PDF pág. 12) — regla de selección de método y de presentación PH vs. NPH. **Confirmar la palabra "integrales".**
3. **Art. 36 completo** (PDF págs. 34–35) — la regla nuclear de PH, sus 4 numerales y sus 2 parágrafos.
4. **Art. 19 nums. 1 y 2** (PDF págs. 20–21) — lineamientos de análisis de mercado PH vs. NPH.
5. **Art. 17 lits. c), d) y f)** (PDF pág. 18) — datos mínimos y depuración de comparables en PH; obligación del método del costo para construcciones.
6. **Art. 37** (PDF págs. 35–36) — NPH asimilable a copropiedad y ecuación del VTI.
7. **Anexo técnico §2.1 completo** (PDF págs. 73–76) — datos mínimos del estudio de mercado y **Nota 2 (prohibición de homologación por factores)**.
8. **Anexo técnico, glosario: "Valor Integral", "Área privada construida", "Área privada libre"** (PDF págs. 63 y 72).
9. **Arts. 22–26** (PDF págs. 23–26) — método de renta, sus dos técnicas y sus requisitos.
10. **Arts. 27–30** (PDF págs. 26–29) — método del costo, reposición vs. reproducción, Ross-Heideck.
11. **Arts. 31–34** (PDF págs. 29–34) — método (técnica) residual, estático vs. dinámico.
12. **Art. 21** (PDF pág. 22) — umbrales del coeficiente de variación.
13. **Arts. 59–61** (PDF pág. 56) — transitoriedad y vigencia (y la edición del **Diario Oficial**).

**URLs directas:**
- Resolución: `https://www.igac.gov.co/sites/default/files/transparencia/normograma/R%200941%20-%202026%20SE%20FIJAN%20LOS%20M%C3%89TODOS%20Y%20LAS%20CONDICIONES%20DE%20ELABORACI%C3%93N%20Y%20PRESENTACI%C3%93N%20DE%20AVAL%C3%9AOS.pdf`
- Anexo (figuras): `https://www.igac.gov.co/sites/default/files/transparencia/normograma/Anexo_Final_.pdf`
- Ficha normativa: `https://www.igac.gov.co/node/53595`

### 5.4 Clasificación de la evidencia usada en este informe

| Nivel | Descripción | Dónde se aplicó |
|---|---|---|
| **(a) Texto confirmado de la norma** | Lectura visual directa de la imagen de página oficial, con dos lecturas convergentes y/o corroboración cruzada | Arts. 15, 16, 17, 19 num. 2, 20, 22, 23, 24, 25, 35, 36, 37; glosario (Valor Integral, Área privada construida, Área privada libre, Régimen de PH); anexo §2.1 Nota 1 y Nota 2 y lista de datos PH |
| **(a−) Texto de la norma vía OCR** | OCR del PDF oficial, sin segunda lectura visual | Arts. 2–14, 18, 21, 26–34, 38–61; anexo técnico (salvo lo listado arriba) |
| **(b) Interpretación de fuente secundaria** | Artículo de firma jurídica | Cuatro métodos del Art. 15; umbrales 7,5 %/10 %; visita técnica obligatoria (Art. 10); afectaciones no inscritas (Art. 12); AVM/IA (Art. 20); Ross-Heideck en reemplazo de Fitto-Corvini; 61 artículos y 9 títulos |
| **(c) Inferencia propia** | Deducción mía, marcada como tal | Forma `VC = CT − D + VT` del Art. 27; lectura de "legalmente constituidas" como condición jurídica y no física; lectura de los veredictos de la matriz de cotejo |

**Fuente secundaria utilizada:** *"QUÉ CAMBIA CON LA RESOLUCIÓN IGAC 941 DE 2026 EN LA ELABORACIÓN DE AVALÚOS COMERCIALES EN COLOMBIA"*, Arroyave & Asociados (abogadosaya.com), 12 de agosto de 2026 — `https://abogadosaya.com/blog/que-cambia-con-la-resolucion-igac-941-de-2026-en-la-elaboracion-de-avaluos-comerciales-en-colombia/`
**Fuente secundaria utilizada:** OCH Group, ficha de la norma y reproducción parcial del texto (hasta el Art. 9) — `https://www.ochgroup.co/norma/resolucion-0941-de-2026-metodos-y-condiciones-para-la-elaboracion-y-presentacion-de-avaluos/` (la reproducción de OCH coincide literalmente con el texto que extraje del PDF oficial, lo que valida la cadena de extracción).

---

*Informe elaborado a partir del PDF oficial escaneado publicado por el IGAC, con extracción de imágenes de página, OCR (Windows.Media.Ocr es-ES) y verificación visual directa de los artículos críticos. Las fórmulas matemáticas y las tablas numéricas del anexo técnico no pudieron leerse con fiabilidad y se señalan expresamente.*

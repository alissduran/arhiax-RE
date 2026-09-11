# Plan maestro de ajustes IGAC 0941 — ARHIAX Confianza Predial

**Versión:** 0.2 — 10 de septiembre de 2026  
**Finalidad:** convertir la nueva normativa valuatoria en requisitos de producto, datos, operación y control.  
**Naturaleza:** especificación de implementación sujeta a validación de un avaluador inscrito en RAA y abogado competente.

## 1. Alcance normativo

El IGAC registra la Resolución 941 de 2026 como vigente. Su objeto es fijar métodos y condiciones de elaboración y presentación de avalúos conforme al capítulo 3 del título 2 del Decreto 1170 de 2015. La página oficial indica que deroga la Resolución 620 de 2008 y los incisos 1, 2 y 3 del artículo 14 de la Resolución 898 de 2014. Fue emitida el 31 de julio y publicada el 12 de agosto de 2026.

La normativa y los formatos oficiales del IGAC distinguen, entre otros, informes urbanos, rurales, de mejoras y de propiedad horizontal. Esto confirma que el sistema debe clasificar el expediente antes de sugerir metodología o pedir evidencia.

## 2. Decisión de diseño

ARHIAX no debe “hacer el avalúo”. Debe operar como **asistente de conformidad valuatoria**:

`tipología → propósito → datos mínimos → método candidato → evidencia → alerta → revisión del avaluador → versión/firma`

El motor puede sugerir, comparar y detectar inconsistencias; la selección definitiva del método, los supuestos, el valor y la firma siguen siendo del avaluador.

## 3. Ajustes obligatorios al producto

### 3.1 Clasificador inicial del inmueble

Agregar campos obligatorios:

| Bloque | Campos mínimos |
|---|---|
| Identidad | matrícula, CHIP/cédula catastral, dirección, municipio, coordenadas, fuente y fecha |
| Régimen | NPH, PH, PH matriz, unidad privada, lote, condominio, rural, mejora, informalidad |
| Propósito | comercial, garantía, judicial, administrativo, expropiación, contable u otro |
| Estado | construido, en construcción, lote, ruina, mejora, proyecto, uso actual y uso permitido |
| Geometría | áreas de terreno, construcción y privadas/comunes; frente, fondo, linderos y plano fuente |
| Urbanismo | POT, tratamiento, uso, norma, licencia, afectaciones, riesgo y restricciones |
| Mercado | fecha de referencia, comparables, oferta, transacciones y ajustes |

### 3.2 Enrutamiento de métodos

La regla de negocio no debe ser “el sistema aplica M1/M3/M4”. Debe ser:

1. clasificar el activo y el propósito del avalúo;
2. identificar el método o combinación técnicamente defendible;
3. solicitar los datos mínimos y fuentes;
4. advertir incompatibilidades y ausencia de información;
5. dejar la decisión y firma al avaluador competente;
6. registrar versión normativa, fecha, supuestos y excepciones.

La afirmación recibida de Franco se implementa inicialmente como regla para validación profesional:

| Caso | Regla provisional | Salida ARHIAX |
|---|---|---|
| Lote | revisar M4/residual cuando el valor dependa del potencial de desarrollo; no asumir que todo lote exige M4 | solicitar norma urbanística, aprovechamiento, costos, tiempos, ventas y sensibilidad; escalar al avaluador |
| PH | revisar M1/mercado como método principal para unidad terminada; valor integral y áreas comunes según corresponda | validar unidad, matriz, coeficientes, áreas, comparables y consistencia integral |
| PH excepcional | revisar M3/ingresos cuando el inmueble tenga renta demostrable o sea la base económica del valor | solicitar contratos, ingresos, vacancia, gastos, tasa y horizonte; escalar |
| Urbano NPH | comparar mercado, costo o ingresos según características y finalidad | no permitir método por defecto sin justificación |
| Rural | verificar uso, productividad, accesibilidad, suelo protegido, agua, mejoras y áreas homogéneas aplicables | fuente, fecha, georreferencia y trazabilidad de cada variable |

**Control:** ninguna de estas filas debe presentarse al usuario como regla normativa definitiva hasta cotejar artículo, parágrafo, anexo y régimen transitorio de la Resolución 0941.

### 3.3 Propiedad horizontal

Incorporar un subexpediente PH con: escritura de constitución, reglamento, reformas, licencia, plano aprobado, unidad privada, bienes comunes, coeficiente, áreas, parqueaderos y depósitos, destinación, restricciones, administración, estado constructivo y diferencias entre realidad, catastro, plano y reglamento.

El sistema debe generar alertas separadas para: área privada inconsistente, coeficiente faltante, unidad no individualizada, bienes comunes atribuidos como privados, reforma no soportada, licencia ausente, uso incompatible y valoración no integral.

### 3.4 Lotes y residual

Agregar módulo de potencial de desarrollo: área útil, índice de ocupación, índice de construcción, altura, obligaciones urbanísticas, cesiones, cargas, costos directos/indirectos, comercialización, financiación, plazo, riesgo de aprobación y sensibilidad. El resultado debe ser una **memoria de supuestos para el avaluador**, no un valor automático.

### 3.5 Homogeneización y comparables

Crear un registro de cada comparable con ubicación, fecha, fuente, tipo de operación, área, uso, topografía, frente, acceso, servicios, estado, régimen, características constructivas, condiciones de negociación y ajustes aplicados.

La homogeneización debe ser explicable: variable observada → diferencia → ajuste → justificación → responsable. Prohibir ajustes sin fuente o con factor opaco. Conservar los comparables descartados y la razón del descarte.

### 3.6 Construcción y materiales

Separar dato observado de dato inferido. Registrar sistema constructivo, estructura, cubierta, fachada, acabados, instalaciones, edad, conservación, vida útil remanente, obsolescencia, reparaciones, daños y fuente. Si el dato proviene de inspección, identificar inspector y fecha; si proviene de catastro o licencia, conservar el documento fuente.

### 3.7 Informe y memoria de cálculo

El generador debe incluir: identificación, solicitante, finalidad, fecha de corte, fecha de inspección, fuentes, descripción, metodología seleccionada, métodos descartados, datos de mercado, cálculos, supuestos, limitaciones, incertidumbre, anexos, versión normativa, identidad del avaluador, RAA cuando corresponda, firma y control de cambios.

No usar expresiones como “predio seguro”, “valor verdadero”, “avalúo certificado por IA” o “asegurabilidad garantizada”.

## 4. Validaciones normativas antes de producción

- Transcribir a una matriz artículo/parágrafo/anexo la nomenclatura oficial de métodos.
- Verificar la afirmación sobre lote/M4 y documentar excepciones.
- Verificar si en PH M1 es regla general, cuándo procede M3 y cómo se determina el valor integral.
- Identificar campos obligatorios de materiales, edad, conservación, vida útil, áreas comunes, estado constructivo y homogeneización.
- Confirmar transición, vigencia operativa, formatos obligatorios y alcance subjetivo.
- Revisar si el método puede ser combinado y cómo debe justificarse.
- Confirmar reglas de inspección, fuentes de mercado, fecha de referencia, redondeos y memoria de cálculo.
- Comparar los formatos oficiales vigentes del IGAC con el esquema JSON de ARHIAX.

El PDF local está disponible en la carpeta de confianza predial, pero la extracción automática no quedó disponible en el entorno. Por eso las reglas M1/M3/M4 anteriores son **hipótesis de parametrización** tomadas de la reunión y no reglas legales definitivas. Antes de producción se debe hacer una lectura visual/manual del PDF y del anexo con un avaluador experto.

## 5. Fuentes y gobierno de datos

La curaduría puede ser una fuente para licencias urbanísticas, actos, planos y trazabilidad del trámite, sujeto a disponibilidad, reserva, derechos de petición, interoperabilidad y protección de datos. IGAC/catastro puede aportar variables físicas y geográficas según el gestor catastral y el producto disponible; no debe asumirse que todos los materiales constructivos estén disponibles públicamente o con el nivel de detalle requerido.

## Diseño de datos recomendado

Cada atributo debe registrar: fuente, fecha de consulta, titularidad, autorización de uso, nivel de confianza, evidencia asociada, versión y responsable de validación. El sistema debe distinguir dato catastral, dato registral, dato urbanístico, dato de inspección y dato inferido. Para cada campo debe existir estado `verified`, `reported`, `inferred`, `conflict` o `unknown`.

No mezclar avalúo catastral con valor comercial. El sistema debe mostrar fuente, finalidad y fecha de cada cifra y alertar cuando se comparen magnitudes no equivalentes.

## 6. Requisitos de pruebas

Antes del piloto, construir un corpus de al menos 30 expedientes anonimizados: 10 PH, 10 NPH y 10 lotes, incluyendo casos con inconsistencias. Un comité de avaluadores debe producir el gold standard.

Métricas mínimas: completitud del expediente, clasificación correcta de tipología, concordancia del método candidato, sensibilidad de alertas críticas, falsos positivos, tiempo hasta revisión profesional, trazabilidad de comparables y porcentaje de salidas que preservan autoría.

**Criterio de bloqueo:** si el sistema no puede justificar fuente, regla, fecha y responsable, no debe emitir recomendación valuatoria; debe emitir `UNKNOWN` y escalar.

## 7. Relación con seguros de títulos

ARHIAX debe posicionarse inicialmente como infraestructura de evidencia, prevención y originación, no como aseguradora. La Superintendencia Financiera explica que la actividad aseguradora y los ramos requieren autorización; las compañías y corredores autorizados pueden verificarse en los registros de la SFC. El diseño debe comenzar con una aseguradora/corredor y definir cobertura, exclusiones, prima, reservas, reaseguro, siniestros y responsabilidad profesional.

La conformidad IGAC puede ser insumo de suscripción, pero no equivale a asegurabilidad ni elimina exclusiones de título. El producto debe separar expresamente: evidencia valuatoria, concepto profesional, decisión de suscripción y póliza.

## 8. Backlog priorizado

| Prioridad | Ajuste | Responsable | Gate |
|---|---|---|---|
| P0 | Leer y mapear PDF/anexo 0941 artículo por artículo | abogado + avaluador | matriz normativa firmada |
| P0 | Clasificador PH/NPH/lote/rural/mejora | producto | 100% casos de prueba |
| P0 | Motor de estados y procedencia de datos | ingeniería | auditoría reproducible |
| P0 | M1/M3/M4 como reglas versionadas y no automáticas | valuación | aprobación comité técnico |
| P1 | Módulo de homogeneización y comparables | valuación + datos | memoria explicable |
| P1 | Módulo de lote/residual | valuación + urbanismo | sensibilidad y revisión |
| P1 | Informe compatible con formato oficial | producto | revisión avaluador |
| P1 | Subexpediente PH | jurídico + valuación | checklist completo |
| P2 | Integración curaduría/IGAC | alianzas | fuente y autorización |
| P2 | Paquete de evidencia para aseguradora | seguros | underwriting partner |

## Fuentes de referencia

- [IGAC — Resolución 941 de 2026](https://www.igac.gov.co/node/53595)
- [IGAC — Gestión valuatoria y formatos](https://www.igac.gov.co/index.php/taxonomia/gestion-valuatoria)
- [SFC — Información general de aseguradoras e intermediarios](https://www.superfinanciera.gov.co/publicaciones/15491/industrias-supervisadasindustria-aseguradorainformacion-general-aseguradoras-e-intermediarios-de-seguros-15491/)
- [SFC — Lista de entidades autorizadas](https://www.superfinanciera.gov.co/publicaciones/10114907/lista-de-entidades/)

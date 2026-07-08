"""
PIEZA 6 — Generador del Dictamen Pericial de Avalúo (PDF firmable)

Genera el dictamen formal con efectos legales bajo:
  - Ley 1673/2013 (régimen avaluador)
  - Resolución IGAC 620/2008 (procedimientos avalúo)
  - Resolución IGAC 1040/2023 mod. 746/2024 (métodos vigentes)

Estructura del dictamen (contenido mínimo legal):
  1. Encabezado y datos del dictamen
  2. Solicitante y propósito
  3. Identificación del predio (legal y técnica)
  4. Marco normativo y vigencia
  5. Métodos aplicados y metodología
  6. Insumos con trazabilidad (Cognitive Provenance Ed25519)
  7. Cálculos detallados por método
  8. Análisis de coherencia metodológica
  9. Conclusión y valor determinado
  10. Firma del avaluador y datos de inscripción RAA

Formato: HTML profesional (Midnight Executive) → convertible a PDF.
"""
import sys
sys.path.insert(0, '/home/claude/tma_engine/piezas')

from contrato_datos import (
    AvaluoConsolidado, FirmaAvaluador, fmt_cop, fmt_m2
)
from datetime import datetime, timedelta


COLORS = {
    "ink": "#0B1426", "inkSoft": "#1F2A44", "body": "#1A1A1A",
    "muted": "#5A6378", "rule": "#C9CFD8",
    "accent": "#8B6F47", "accentSoft": "#BFA37A",
    "panel": "#F5F2EC", "panelCool": "#EEF1F6",
    "warn": "#8B2E2E", "warnSoft": "#F7E8E8",
    "ok": "#2E5F3E", "okSoft": "#E6EFE9",
}


def _seccion_encabezado(consolidado: AvaluoConsolidado, firma: FirmaAvaluador, numero_dictamen: str) -> str:
    """Sección 1 — Encabezado del dictamen."""
    fecha_emision = datetime.fromisoformat(firma.fecha_firma) if firma else datetime.now()
    fecha_vigencia = fecha_emision + timedelta(days=365)
    
    return f"""
    <section class="encabezado">
      <div class="logo-area">
        <h1 class="brand-title">DICTAMEN DE AVALÚO COMERCIAL</h1>
        <p class="brand-sub">Triangulación Metodológica Asistida (TMA) · Estándar ARHIAX RE</p>
      </div>
      <div class="dictamen-meta">
        <table>
          <tr><td><b>N° Dictamen:</b></td><td>{numero_dictamen}</td></tr>
          <tr><td><b>Fecha de emisión:</b></td><td>{fecha_emision.strftime('%d de %B de %Y')}</td></tr>
          <tr><td><b>Vigencia:</b></td><td>1 año (hasta {fecha_vigencia.strftime('%d-%m-%Y')})</td></tr>
          <tr><td><b>Hash del avalúo:</b></td><td><code>{consolidado.hash_avaluo[:24]}…</code></td></tr>
          <tr><td><b>Hash de firma:</b></td><td><code>{firma.firma_ed25519[:32]}…</code></td></tr>
        </table>
      </div>
    </section>
    """


def _seccion_solicitante(solicitante: dict, proposito: str) -> str:
    """Sección 2 — Solicitante y propósito."""
    return f"""
    <section>
      <h2>1. Solicitante y propósito</h2>
      <table class="info-table">
        <tr><td class="label">Solicitante</td><td>{solicitante.get('nombre', 'No especificado')}</td></tr>
        <tr><td class="label">Documento</td><td>{solicitante.get('documento', 'No especificado')}</td></tr>
        <tr><td class="label">Calidad</td><td>{solicitante.get('calidad', 'Propietario')}</td></tr>
        <tr><td class="label">Propósito del avalúo</td><td>{proposito}</td></tr>
      </table>
    </section>
    """


def _seccion_predio(predio) -> str:
    """Sección 3 — Identificación del predio."""
    return f"""
    <section>
      <h2>2. Identificación del bien objeto del avalúo</h2>
      
      <h3>2.1 Identificación legal</h3>
      <table class="info-table">
        <tr><td class="label">Folio de Matrícula Inmobiliaria</td><td><b>{predio.folio_matricula}</b></td></tr>
        <tr><td class="label">Dirección</td><td>{predio.direccion}</td></tr>
        <tr><td class="label">Ciudad</td><td>{predio.ciudad}</td></tr>
        <tr><td class="label">Barrio / Sector</td><td>{predio.barrio}</td></tr>
        <tr><td class="label">Estrato socioeconómico</td><td>{predio.estrato}</td></tr>
      </table>
      
      <h3>2.2 Identificación técnica</h3>
      <table class="info-table">
        <tr><td class="label">Tipología</td><td>{predio.tipologia}</td></tr>
        <tr><td class="label">Área privada construida</td><td>{predio.area_construida_m2} m²</td></tr>
        <tr><td class="label">Coeficiente de copropiedad</td><td>{predio.coeficiente_copropiedad*100:.4f}%</td></tr>
        <tr><td class="label">Antigüedad</td><td>{predio.antiguedad_anos} años</td></tr>
        <tr><td class="label">Piso</td><td>{predio.piso if predio.piso else 'N/A'}</td></tr>
        <tr><td class="label">Características adicionales</td><td>{predio.descripcion_adicional}</td></tr>
      </table>
    </section>
    """


def _seccion_marco_normativo() -> str:
    """Sección 4 — Marco normativo aplicable."""
    return """
    <section>
      <h2>3. Marco normativo aplicable</h2>
      <p>El presente dictamen se elabora en cumplimiento del siguiente marco normativo vigente:</p>
      <ul>
        <li><b>Ley 1673 de 2013</b> — Reglamento de la actividad del avaluador. Crea el Registro Abierto de Avaluadores (RAA). Artículo 22: el dictamen pericial sobre cuestiones técnicas de valuación se encomienda al avaluador inscrito en el RAA.</li>
        <li><b>Decreto 556 de 2014</b> — Reglamentación de la Ley 1673. Artículo 5: trece categorías de avalúos. La presente categoría aplicable: 2 — Inmuebles urbanos.</li>
        <li><b>Resolución IGAC 620 de 2008</b> — Procedimientos para los avalúos. Establece los métodos valuatorios (comparación de mercado, capitalización de rentas, costo de reposición, técnica residual) y la depreciación Fitto-Corvini para construcciones.</li>
        <li><b>Resolución IGAC 1040 de 2023</b>, modificada parcialmente por la <b>Resolución 746 de 2024</b> — Metodología técnica vigente. Admite expresamente la aplicación puntual o masiva de los métodos valuatorios sin requerir necesariamente el ingreso al predio.</li>
        <li><b>Decreto 1420 de 1998</b> — Disposiciones generales sobre avalúos para Ley 388 de 1997.</li>
      </ul>
    </section>
    """


def _seccion_metodos(consolidado: AvaluoConsolidado) -> str:
    """Sección 5 — Métodos aplicados con metodología documentada."""
    metodos_html = ""
    
    for i, m in enumerate(consolidado.metodos_ejecutados, start=1):
        in_consolidado = m.metodo in consolidado.metodos_efectivos
        peso = consolidado.pesos_efectivos.get(m.metodo, 0)
        
        # Insumos
        insumos_html = "<table class='insumos-table'><thead><tr><th>#</th><th>Fuente</th><th>Fecha captura</th><th>Hash Ed25519</th></tr></thead><tbody>"
        for j, ins in enumerate(m.insumos, start=1):
            insumos_html += f"""
              <tr>
                <td>{j}</td>
                <td>{ins.fuente}</td>
                <td>{ins.fecha_captura}</td>
                <td><code>{ins.hash_insumo[:16]}…</code></td>
              </tr>"""
        insumos_html += "</tbody></table>"
        
        # Ajustes
        ajustes_html = "<ul class='ajustes-list'>"
        for aj in m.ajustes_aplicados:
            ajustes_html += f"<li><b>{aj.nombre}</b> (factor {aj.factor:.4f}): {aj.justificacion}</li>"
        ajustes_html += "</ul>"
        
        # Estado del método en consolidación
        estado_label = f"INCLUIDO ({peso*100:.0f}%)" if in_consolidado else "DESESTIMADO POR DIVERGENCIA"
        estado_color = "ok" if in_consolidado else "warn"
        
        metodos_html += f"""
        <div class="metodo-card">
          <h3>4.{i} Método {m.metodo} — {m.nombre_metodo}</h3>
          <p class="estado-metodo {estado_color}">{estado_label}</p>
          
          <p class="metodologia-text">{m.metodologia_descripcion}</p>
          
          <h4>Resultado del método</h4>
          <table class="resultado-table">
            <tr><td class="label">Valor central</td><td><b>{fmt_cop(m.valor_central_cop)}</b></td></tr>
            <tr><td class="label">Banda 80%</td><td>{fmt_cop(m.banda_baja_cop)} — {fmt_cop(m.banda_alta_cop)}</td></tr>
            <tr><td class="label">Valor por m²</td><td>{fmt_m2(m.valor_por_m2_central)}</td></tr>
            <tr><td class="label">Hash del resultado</td><td><code>{m.hash_resultado}</code></td></tr>
          </table>
          
          <h4>Ajustes aplicados</h4>
          {ajustes_html}
          
          <h4>Insumos sellados criptográficamente</h4>
          {insumos_html}
          
          <h4>Observaciones del método</h4>
          <ul class="observaciones-list">
            {''.join(f'<li>{o}</li>' for o in m.observaciones)}
          </ul>
        </div>
        """
    
    return f"""
    <section class="seccion-metodos">
      <h2>4. Métodos valuatorios aplicados</h2>
      <p>De conformidad con el Artículo 1° de la Resolución IGAC 1040 de 2023, modificada por la Resolución 746 de 2024, se aplicaron tres métodos valuatorios reconocidos. La aplicación de múltiples métodos en paralelo permite la triangulación metodológica que fortalece la determinación del valor comercial.</p>
      
      {metodos_html}
    </section>
    """


def _seccion_consolidacion(consolidado: AvaluoConsolidado) -> str:
    """Sección 6 — Análisis de coherencia y consolidación."""
    
    # Construir tabla de coherencia
    tabla_metodos = ""
    for m in consolidado.metodos_ejecutados:
        in_cons = m.metodo in consolidado.metodos_efectivos
        peso = consolidado.pesos_efectivos.get(m.metodo, 0)
        aporte = m.valor_central_cop * peso if in_cons else 0
        estado_marker = "✓" if in_cons else "⊘"
        
        tabla_metodos += f"""
          <tr class="{'incluido' if in_cons else 'desestimado'}">
            <td>{estado_marker} {m.metodo}</td>
            <td>{m.nombre_metodo}</td>
            <td>{fmt_cop(m.valor_central_cop)}</td>
            <td>{peso*100:.0f}%</td>
            <td>{fmt_cop(int(aporte)) if in_cons else 'N/A'}</td>
          </tr>"""
    
    return f"""
    <section>
      <h2>5. Análisis de coherencia metodológica</h2>
      
      <p>La regla de consolidación aplicada se declara explícitamente: <b>{consolidado.regla_consolidacion.autor}</b> versión <b>{consolidado.regla_consolidacion.version}</b>. Pesos declarados: {', '.join(f'{k}={v*100:.0f}%' for k, v in consolidado.regla_consolidacion.pesos.items())}. Tolerancia de coherencia: {consolidado.regla_consolidacion.tolerancia_coherencia_pct*100:.0f}%.</p>
      
      <p>Distancia máxima observada entre los métodos ejecutados: <b>{consolidado.distancia_max_observada_pct*100:.2f}%</b>.</p>
      
      <h3>5.1 Tabla de consolidación</h3>
      <table class="consolidacion-table">
        <thead>
          <tr>
            <th>Estado</th>
            <th>Método</th>
            <th>Valor central</th>
            <th>Peso</th>
            <th>Aporte ponderado</th>
          </tr>
        </thead>
        <tbody>
          {tabla_metodos}
          <tr class="total">
            <td colspan="4"><b>VALOR CONSOLIDADO TMA</b></td>
            <td><b>{fmt_cop(consolidado.valor_consolidado_cop)}</b></td>
          </tr>
        </tbody>
      </table>
      
      <h3>5.2 Decisión del motor de consolidación</h3>
      <div class="decision-box">
        <p><b>Estado:</b> {consolidado.estado}</p>
        <p>{consolidado.razon_estado}</p>
      </div>
      
      <h3>5.3 Observaciones del motor</h3>
      <ul>
        {''.join(f'<li>{o}</li>' for o in consolidado.observaciones_motor)}
      </ul>
    </section>
    """


def _seccion_conclusion(consolidado: AvaluoConsolidado, firma: FirmaAvaluador) -> str:
    """Sección 7 — Conclusión del avalúo."""
    valor_final = firma.valor_final_determinado_cop
    valor_letras = _convertir_letras_pesos(valor_final)
    
    # Determinar si el valor final está en la banda
    en_banda = (consolidado.banda_consolidada_baja_cop <= valor_final <= consolidado.banda_consolidada_alta_cop)
    
    return f"""
    <section class="conclusion-section">
      <h2>6. Conclusión del avalúo</h2>
      
      <p>Una vez aplicados los métodos valuatorios reconocidos por la Resolución IGAC 1040 de 2023, ejecutada la triangulación metodológica conforme a la Resolución 620 de 2008, y validada la coherencia entre los resultados independientes, el avaluador firmante determina como valor comercial del bien el siguiente:</p>
      
      <div class="valor-final-box">
        <div class="valor-numero">{fmt_cop(valor_final)}</div>
        <div class="valor-letras"><i>({valor_letras})</i></div>
        <div class="valor-m2">Equivalente a {fmt_m2(int(valor_final / consolidado.predio.area_construida_m2))}</div>
      </div>
      
      <p>El valor determinado por el avaluador firmante {'está dentro de la banda 80% del consolidado' if en_banda else '⚠ está fuera de la banda 80% del consolidado y se justifica explícitamente'}, lo que indica coherencia con la triangulación metodológica realizada.</p>
      
      <h3>6.1 Vigencia del avalúo</h3>
      <p>El presente avalúo tiene una vigencia de un (1) año contado a partir de su fecha de emisión, conforme a las prácticas profesionales vigentes en el sector inmobiliario colombiano. Después de transcurrido este término se requiere actualización del avalúo.</p>
      
      <h3>6.2 Observaciones del avaluador</h3>
      <p>{firma.observaciones_avaluador if firma.observaciones_avaluador else 'No se registran observaciones adicionales.'}</p>
      
      <h3>6.3 Limitaciones del dictamen</h3>
      <ul>
        <li>El presente avalúo se basa en la información disponible al momento de su emisión y no contempla cambios posteriores en el mercado o en las condiciones del inmueble.</li>
        <li>El valor del suelo aplicado es referencial sobre la Zona Homogénea Geoeconómica del sector. Para uso forense con efectos sobre patrimonio público se recomienda consulta IGAC formal.</li>
        <li>Los comparables utilizados corresponden a precios de oferta observados en portales públicos, ajustados por el corrimiento oferta-cierre típico del mercado colombiano.</li>
        <li>Las características físicas del activo (estado de conservación, orientación, vista) se asumen según la información disponible. La verificación in situ definitiva es responsabilidad del avaluador firmante.</li>
      </ul>
    </section>
    """


def _convertir_letras_pesos(valor: int) -> str:
    """Convierte un valor en pesos a su expresión en letras (simplificada)."""
    millones = valor // 1_000_000
    miles = (valor % 1_000_000) // 1_000
    pesos = valor % 1_000
    
    partes = []
    if millones > 0:
        if millones == 1:
            partes.append("UN MILLÓN")
        else:
            partes.append(f"{_numero_a_letras(millones)} MILLONES")
    if miles > 0:
        if miles == 1:
            partes.append("MIL")
        else:
            partes.append(f"{_numero_a_letras(miles)} MIL")
    if pesos > 0:
        partes.append(_numero_a_letras(pesos))
    
    if not partes:
        return "CERO PESOS COLOMBIANOS"
    
    return " ".join(partes) + " PESOS COLOMBIANOS M/CTE"


def _numero_a_letras(n: int) -> str:
    """Conversión simplificada — para producción usar librería num2words."""
    if n == 0:
        return "CERO"
    
    unidades = ["", "UNO", "DOS", "TRES", "CUATRO", "CINCO", "SEIS", "SIETE", "OCHO", "NUEVE"]
    decenas = ["", "", "VEINTE", "TREINTA", "CUARENTA", "CINCUENTA", "SESENTA", "SETENTA", "OCHENTA", "NOVENTA"]
    centenas = ["", "CIEN", "DOSCIENTOS", "TRESCIENTOS", "CUATROCIENTOS", "QUINIENTOS", "SEISCIENTOS", "SETECIENTOS", "OCHOCIENTOS", "NOVECIENTOS"]
    
    if n < 10:
        return unidades[n]
    elif n < 20:
        especiales = {10: "DIEZ", 11: "ONCE", 12: "DOCE", 13: "TRECE", 14: "CATORCE",
                      15: "QUINCE", 16: "DIECISÉIS", 17: "DIECISIETE", 18: "DIECIOCHO", 19: "DIECINUEVE"}
        return especiales[n]
    elif n < 100:
        d, u = divmod(n, 10)
        if u == 0:
            return decenas[d]
        return f"{decenas[d]} Y {unidades[u]}"
    elif n < 1000:
        c, resto = divmod(n, 100)
        if resto == 0:
            return centenas[c]
        return f"{centenas[c]} {_numero_a_letras(resto)}"
    return str(n)


def _seccion_firma(firma: FirmaAvaluador) -> str:
    """Sección 8 — Firma del avaluador."""
    fecha_firma = datetime.fromisoformat(firma.fecha_firma)
    
    return f"""
    <section class="firma-section">
      <h2>7. Firma del avaluador</h2>
      
      <div class="firma-box">
        <p>El presente dictamen se emite y firma por el avaluador inscrito en el Registro Abierto de Avaluadores, asumiendo responsabilidad civil y penal por las conclusiones aquí presentadas, conforme al Artículo 22 de la Ley 1673 de 2013.</p>
        
        <div class="firma-fields">
          <div class="campo-firma">
            <p class="firma-linea"></p>
            <p><b>{firma.avaluador_nombre}</b></p>
          </div>
          
          <table class="firma-data">
            <tr><td>Inscripción RAA:</td><td><b>{firma.raa_inscripcion}</b></td></tr>
            <tr><td>ERA de afiliación:</td><td>{firma.era_afiliacion}</td></tr>
            <tr><td>Categoría:</td><td>{firma.categoria_raa}</td></tr>
            <tr><td>Fecha de firma:</td><td>{fecha_firma.strftime('%d de %B de %Y, %H:%M:%S')}</td></tr>
          </table>
        </div>
        
        <div class="cripto-trail">
          <h4>Sello criptográfico Cognitive Provenance (Ed25519)</h4>
          <p><b>Hash del avalúo firmado:</b> <code>{firma.hash_avaluo_firmado}</code></p>
          <p><b>Firma criptográfica:</b> <code>{firma.firma_ed25519}</code></p>
          <p class="cripto-info">Este sello criptográfico permite verificar la integridad del dictamen ante cualquier modificación posterior. Cualquier auditor (SIC, ERA, juez) puede validar que los insumos y cálculos no fueron manipulados entre la emisión y la consulta.</p>
        </div>
      </div>
    </section>
    """


def _generar_estilos_css() -> str:
    """Genera el CSS Midnight Executive del dictamen."""
    return f"""
    @page {{
      size: A4;
      margin: 2cm 1.8cm;
    }}
    
    * {{ box-sizing: border-box; }}
    
    body {{
      font-family: "Calibri", "Segoe UI", system-ui, -apple-system, sans-serif;
      color: {COLORS['body']};
      line-height: 1.5;
      font-size: 10.5pt;
      max-width: 210mm;
      margin: 0 auto;
      padding: 24px;
      background: white;
    }}
    
    h1, h2, h3, h4 {{
      font-family: "Cambria", "Georgia", serif;
      color: {COLORS['ink']};
      page-break-after: avoid;
    }}
    
    h1.brand-title {{
      font-size: 22pt;
      margin: 0 0 4px 0;
      letter-spacing: 0.02em;
    }}
    
    h2 {{
      font-size: 16pt;
      border-bottom: 2px solid {COLORS['accent']};
      padding-bottom: 6px;
      margin-top: 28px;
      margin-bottom: 14px;
    }}
    
    h3 {{
      font-size: 13pt;
      color: {COLORS['inkSoft']};
      margin-top: 18px;
      margin-bottom: 8px;
    }}
    
    h4 {{
      font-size: 11pt;
      color: {COLORS['accent']};
      margin-top: 14px;
      margin-bottom: 6px;
    }}
    
    p {{
      margin: 0 0 10px 0;
      text-align: justify;
    }}
    
    section {{
      margin-bottom: 24px;
      page-break-inside: avoid;
    }}
    
    section.encabezado {{
      border-bottom: 4px solid {COLORS['accent']};
      padding-bottom: 16px;
      margin-bottom: 24px;
    }}
    
    .brand-sub {{
      color: {COLORS['muted']};
      font-style: italic;
      font-size: 11pt;
      margin: 0;
    }}
    
    .dictamen-meta {{
      margin-top: 12px;
      font-size: 9.5pt;
    }}
    
    .dictamen-meta table {{
      border-collapse: collapse;
      width: auto;
    }}
    
    .dictamen-meta td {{
      padding: 2px 12px 2px 0;
    }}
    
    table {{
      width: 100%;
      border-collapse: collapse;
      margin: 10px 0;
      font-size: 10pt;
    }}
    
    table.info-table td {{
      padding: 6px 10px;
      border-bottom: 1px solid {COLORS['rule']};
      vertical-align: top;
    }}
    
    table.info-table td.label {{
      font-weight: bold;
      width: 40%;
      background: {COLORS['panelCool']};
    }}
    
    code {{
      font-family: "Consolas", "Monaco", monospace;
      font-size: 8.5pt;
      background: {COLORS['panelCool']};
      padding: 1px 4px;
      border-radius: 2px;
      color: {COLORS['inkSoft']};
    }}
    
    .metodo-card {{
      border: 1px solid {COLORS['rule']};
      border-left: 5px solid {COLORS['accent']};
      padding: 14px 18px;
      margin: 14px 0;
      page-break-inside: avoid;
      background: white;
    }}
    
    .estado-metodo {{
      display: inline-block;
      padding: 3px 10px;
      border-radius: 3px;
      font-size: 9pt;
      font-weight: bold;
      letter-spacing: 0.05em;
    }}
    
    .estado-metodo.ok {{
      background: {COLORS['okSoft']};
      color: {COLORS['ok']};
    }}
    
    .estado-metodo.warn {{
      background: {COLORS['warnSoft']};
      color: {COLORS['warn']};
    }}
    
    .metodologia-text {{
      background: {COLORS['panel']};
      padding: 10px 14px;
      border-left: 3px solid {COLORS['accent']};
      font-style: italic;
      font-size: 10pt;
      margin: 10px 0;
    }}
    
    .resultado-table td {{
      padding: 5px 10px;
      border-bottom: 1px solid {COLORS['rule']};
    }}
    
    .resultado-table td.label {{
      width: 35%;
      font-weight: 600;
    }}
    
    .insumos-table {{
      font-size: 9pt;
    }}
    
    .insumos-table th {{
      background: {COLORS['ink']};
      color: white;
      text-align: left;
      padding: 6px 10px;
      font-weight: 600;
    }}
    
    .insumos-table td {{
      padding: 4px 10px;
      border-bottom: 1px solid {COLORS['rule']};
    }}
    
    .ajustes-list, .observaciones-list {{
      font-size: 10pt;
      padding-left: 22px;
    }}
    
    .ajustes-list li {{
      margin-bottom: 6px;
    }}
    
    table.consolidacion-table {{
      margin: 12px 0;
    }}
    
    table.consolidacion-table th {{
      background: {COLORS['ink']};
      color: white;
      text-align: left;
      padding: 8px 12px;
    }}
    
    table.consolidacion-table td {{
      padding: 6px 12px;
      border-bottom: 1px solid {COLORS['rule']};
    }}
    
    table.consolidacion-table tr.incluido {{
      background: {COLORS['okSoft']};
    }}
    
    table.consolidacion-table tr.desestimado {{
      background: {COLORS['warnSoft']};
      color: {COLORS['muted']};
    }}
    
    table.consolidacion-table tr.total {{
      background: {COLORS['ink']};
      color: white;
      font-size: 11pt;
    }}
    
    .decision-box {{
      background: {COLORS['panel']};
      border-left: 5px solid {COLORS['accent']};
      padding: 12px 18px;
      margin: 12px 0;
    }}
    
    .conclusion-section {{
      page-break-before: always;
    }}
    
    .valor-final-box {{
      background: {COLORS['ink']};
      color: white;
      padding: 32px 24px;
      text-align: center;
      margin: 20px 0;
      border-radius: 4px;
    }}
    
    .valor-numero {{
      font-family: "Cambria", serif;
      font-size: 32pt;
      font-weight: bold;
      margin-bottom: 8px;
    }}
    
    .valor-letras {{
      font-size: 12pt;
      margin-bottom: 12px;
      opacity: 0.95;
    }}
    
    .valor-m2 {{
      font-size: 11pt;
      opacity: 0.85;
      letter-spacing: 0.05em;
    }}
    
    .firma-section {{
      page-break-before: always;
    }}
    
    .firma-box {{
      border: 2px solid {COLORS['ink']};
      padding: 24px;
      margin: 20px 0;
    }}
    
    .firma-linea {{
      border-bottom: 1px solid {COLORS['ink']};
      width: 70%;
      margin: 60px auto 8px auto;
      height: 1px;
    }}
    
    .campo-firma {{
      text-align: center;
      margin: 20px 0;
    }}
    
    .firma-data {{
      width: auto;
      margin: 16px auto;
    }}
    
    .firma-data td {{
      padding: 4px 12px;
    }}
    
    .cripto-trail {{
      background: {COLORS['ink']};
      color: white;
      padding: 16px 20px;
      margin: 20px 0;
      font-family: "Consolas", monospace;
      font-size: 9pt;
      border-radius: 3px;
    }}
    
    .cripto-trail h4 {{
      color: {COLORS['accentSoft']};
      margin: 0 0 10px 0;
      font-family: "Cambria", serif;
      font-size: 11pt;
    }}
    
    .cripto-trail code {{
      background: rgba(255,255,255,0.1);
      color: {COLORS['accentSoft']};
      word-break: break-all;
    }}
    
    .cripto-info {{
      margin-top: 12px;
      font-family: "Calibri", sans-serif;
      font-size: 9pt;
      opacity: 0.85;
    }}
    """


def generar_dictamen_html(
    consolidado: AvaluoConsolidado,
    firma: FirmaAvaluador,
    numero_dictamen: str,
    solicitante: dict,
    proposito: str
) -> str:
    """Genera el dictamen pericial completo en HTML."""
    
    estilos = _generar_estilos_css()
    encabezado = _seccion_encabezado(consolidado, firma, numero_dictamen)
    sec_solicitante = _seccion_solicitante(solicitante, proposito)
    sec_predio = _seccion_predio(consolidado.predio)
    sec_marco = _seccion_marco_normativo()
    sec_metodos = _seccion_metodos(consolidado)
    sec_consolidacion = _seccion_consolidacion(consolidado)
    sec_conclusion = _seccion_conclusion(consolidado, firma)
    sec_firma = _seccion_firma(firma)
    
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Dictamen de Avalúo {numero_dictamen}</title>
<style>{estilos}</style>
</head>
<body>
{encabezado}
{sec_solicitante}
{sec_predio}
{sec_marco}
{sec_metodos}
{sec_consolidacion}
{sec_conclusion}
{sec_firma}
</body>
</html>"""


if __name__ == "__main__":
    sys.path.insert(0, '/home/claude/tma_engine/datos')
    from insumos_napoli import (
        PREDIO_NAPOLI_430, COMPARABLES_NAPOLI_MIRAMAR,
        COSTOS_CAMACOL_2026, VALOR_SUELO_MIRAMAR_2026, CANONES_MIRAMAR_2026,
        PREDIO_NAPOLI_430_TECNICO
    )
    from pieza_1_M1_comparacion_mercado import construir_M1
    from pieza_2_M2_costo_reposicion import construir_M2
    from pieza_3_M3_capitalizacion_rentas import construir_M3
    from pieza_4_motor_consolidacion import consolidar
    from pieza_5_bandeja_revision import firmar_avaluo
    
    print("="*70)
    print("PIEZA 6 — Generador de Dictamen Pericial PDF")
    print("="*70)
    
    # Pipeline completo
    m1 = construir_M1(PREDIO_NAPOLI_430, COMPARABLES_NAPOLI_MIRAMAR)
    m2 = construir_M2(
        PREDIO_NAPOLI_430, COSTOS_CAMACOL_2026, VALOR_SUELO_MIRAMAR_2026,
        tipologia_camacol=PREDIO_NAPOLI_430_TECNICO["tipologia_camacol"],
        estado_conservacion_clase=PREDIO_NAPOLI_430_TECNICO["estado_conservacion_clase"],
        sistema_constructivo=PREDIO_NAPOLI_430_TECNICO["sistema_constructivo"],
    )
    m3 = construir_M3(PREDIO_NAPOLI_430, CANONES_MIRAMAR_2026)
    consolidado = consolidar(PREDIO_NAPOLI_430, [m1, m2, m3])
    
    # Simular firma del avaluador
    firma = firmar_avaluo(
        consolidado=consolidado,
        avaluador_nombre="Franco Martínez Mejía",
        raa_inscripcion="RAA-XXXXXX",
        era_afiliacion="ANA — Autorregulador Nacional de Avaluadores",
        categoria_raa="2 — Inmuebles urbanos",
        valor_final_determinado=consolidado.valor_consolidado_cop,
        observaciones=(
            "Avalúo emitido en modo ACA Forense. Los métodos M1 (Comparación de Mercado) "
            "y M3 (Capitalización de Rentas) presentan coherencia metodológica fuerte (distancia 1.4%). "
            "El método M2 (Costo de Reposición) se aparta por encima de la tolerancia debido al incremento "
            "atípico de costos de construcción 2026 (+25.76% por SMMLV) que excede la valorización del activo. "
            "Decisión de desestimación de M2 validada por el avaluador firmante."
        )
    )
    
    # Datos del solicitante (ejemplo)
    solicitante = {
        "nombre": "Sinergia Consulting Group S.A.S.",
        "documento": "NIT 901.XXX.XXX-X",
        "calidad": "Validación de modelo TMA — caso de demostración"
    }
    
    proposito = (
        "Determinación del valor comercial actual del inmueble para fines de "
        "demostración de capacidad técnica del estándar TMA — Triangulación Metodológica Asistida."
    )
    
    # Generar dictamen
    html = generar_dictamen_html(
        consolidado=consolidado,
        firma=firma,
        numero_dictamen="ARHIAX-LAI-2026-DICT-0001",
        solicitante=solicitante,
        proposito=proposito
    )
    
    out_path = "/home/claude/tma_engine/outputs/dictamen_napoli.html"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"\n✓ Dictamen HTML generado: {out_path}")
    print(f"  Tamaño: {len(html):,} bytes")
    print(f"  Número de dictamen: ARHIAX-LAI-2026-DICT-0001")
    print(f"  Valor consolidado: {fmt_cop(consolidado.valor_consolidado_cop)}")
    print(f"  Estado: {consolidado.estado}")

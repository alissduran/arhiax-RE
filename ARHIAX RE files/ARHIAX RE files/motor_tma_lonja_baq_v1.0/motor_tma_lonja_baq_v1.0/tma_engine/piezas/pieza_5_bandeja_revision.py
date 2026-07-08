"""
PIEZA 5 — Bandeja de Revisión y Firma del Avaluador

Recibe el AvaluoConsolidado y produce:
  1. Vista de revisión (HTML) — lo que el avaluador ve para validar y firmar
  2. Cálculo de tiempo estimado de revisión según semáforo
  3. Mecanismo de firma con FirmaAvaluador

En producción real:
  - La firma Ed25519 sería con clave privada del avaluador
  - El HTML se renderiza dentro de la app de la plataforma
  - Tras firma, el documento se sella y se entrega al cliente
"""
import sys
sys.path.insert(0, '/home/claude/tma_engine/piezas')

from contrato_datos import (
    AvaluoConsolidado, FirmaAvaluador, ResultadoMetodo, fmt_cop, fmt_m2, fmt_pct, stable_hash
)
from datetime import datetime
import os


# ============================================================
# COLORES MIDNIGHT EXECUTIVE
# ============================================================
COLORS = {
    "ink": "#0B1426", "inkSoft": "#1F2A44", "body": "#1A1A1A",
    "muted": "#5A6378", "rule": "#C9CFD8",
    "accent": "#8B6F47", "accentSoft": "#BFA37A",
    "panel": "#F5F2EC", "panelCool": "#EEF1F6",
    "warn": "#8B2E2E", "warnSoft": "#F7E8E8",
    "ok": "#2E5F3E", "okSoft": "#E6EFE9",
    "amber": "#8C6B14", "amberSoft": "#F8EFD4",
    "new": "#1F4E79", "newSoft": "#DCE6F1",
}

ESTADO_COLORS = {
    "VERDE": ("#2E5F3E", "#E6EFE9", "✓ LISTO PARA FIRMA", "Revisión estimada: 2-4 minutos"),
    "AMARILLA": ("#8C6B14", "#F8EFD4", "⚠ REQUIERE VALIDACIÓN", "Revisión estimada: 10-15 minutos"),
    "ROJA": ("#8B2E2E", "#F7E8E8", "✗ ELEVAR A VISITA", "Visita in situ requerida"),
}


def generar_bandeja_html(consolidado: AvaluoConsolidado) -> str:
    """Genera la vista HTML de revisión que el avaluador opera."""
    
    estado_color, estado_bg, estado_label, estado_tiempo = ESTADO_COLORS[consolidado.estado]
    predio = consolidado.predio
    
    # Construir filas de cada método
    metodos_html = ""
    for m in consolidado.metodos_ejecutados:
        in_consolidado = m.metodo in consolidado.metodos_efectivos
        peso = consolidado.pesos_efectivos.get(m.metodo, 0)
        peso_label = f"Peso: {peso*100:.0f}%" if in_consolidado else "DESESTIMADO"
        peso_color = COLORS["ok"] if in_consolidado else COLORS["muted"]
        
        insumos_html = ""
        for ins in m.insumos[:5]:  # Primeros 5 insumos
            insumos_html += f"""
            <div style="font-size:11px;color:{COLORS['muted']};margin:2px 0;">
                <code style="color:{COLORS['accent']};">{ins.hash_insumo[:12]}…</code>
                · {ins.fuente} · {ins.fecha_captura}
            </div>"""
        
        ajustes_html = ""
        for aj in m.ajustes_aplicados:
            ajustes_html += f"""
            <li style="font-size:12px;margin:4px 0;">
                <b>{aj.nombre}</b> (factor {aj.factor:.3f}): {aj.justificacion}
            </li>"""
        
        observaciones_html = "".join(f"<li style='font-size:12px;'>{o}</li>" for o in m.observaciones)
        
        metodos_html += f"""
        <div class="method-card" style="border-left:5px solid {COLORS['accent'] if in_consolidado else COLORS['muted']};">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                <div>
                    <div style="font-size:11px;color:{COLORS['muted']};letter-spacing:0.05em;">{m.metodo}</div>
                    <div style="font-family:Cambria,Georgia,serif;font-size:18px;font-weight:bold;color:{COLORS['ink']};">{m.nombre_metodo}</div>
                </div>
                <div style="text-align:right;">
                    <div style="font-size:11px;color:{peso_color};font-weight:bold;letter-spacing:0.05em;">{peso_label}</div>
                </div>
            </div>
            
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin:14px 0;">
                <div style="padding:10px;background:{COLORS['panelCool']};border-radius:3px;text-align:center;">
                    <div style="font-size:10px;color:{COLORS['muted']};">VALOR CENTRAL</div>
                    <div style="font-size:18px;font-weight:bold;color:{COLORS['ink']};">{fmt_cop(m.valor_central_cop)}</div>
                </div>
                <div style="padding:10px;background:{COLORS['panelCool']};border-radius:3px;text-align:center;">
                    <div style="font-size:10px;color:{COLORS['muted']};">$ POR M²</div>
                    <div style="font-size:18px;font-weight:bold;color:{COLORS['ink']};">{fmt_m2(m.valor_por_m2_central)}</div>
                </div>
                <div style="padding:10px;background:{COLORS['panelCool']};border-radius:3px;text-align:center;">
                    <div style="font-size:10px;color:{COLORS['muted']};">BANDA 80%</div>
                    <div style="font-size:13px;color:{COLORS['ink']};">{fmt_cop(m.banda_baja_cop)}<br/>—<br/>{fmt_cop(m.banda_alta_cop)}</div>
                </div>
            </div>
            
            <details style="margin-top:10px;">
                <summary style="cursor:pointer;color:{COLORS['accent']};font-size:13px;font-weight:bold;">▸ Ver metodología, ajustes e insumos ({len(m.insumos)} insumos · {len(m.ajustes_aplicados)} ajustes)</summary>
                <div style="margin-top:10px;padding:12px;background:{COLORS['panel']};border-radius:3px;">
                    <p style="font-size:12px;font-style:italic;margin:0 0 10px 0;">{m.metodologia_descripcion}</p>
                    
                    <b style="font-size:12px;color:{COLORS['ink']};">Ajustes aplicados:</b>
                    <ul style="margin:4px 0 10px 16px;">{ajustes_html}</ul>
                    
                    <b style="font-size:12px;color:{COLORS['ink']};">Insumos sellados (Ed25519):</b>
                    <div style="margin:4px 0;">{insumos_html}</div>
                    
                    <b style="font-size:12px;color:{COLORS['ink']};">Observaciones:</b>
                    <ul style="margin:4px 0 0 16px;">{observaciones_html}</ul>
                    
                    <div style="margin-top:10px;font-size:10px;color:{COLORS['muted']};">
                        <b>Hash resultado:</b> <code>{m.hash_resultado}</code>
                    </div>
                </div>
            </details>
        </div>
        """
    
    # Observaciones del motor
    obs_motor_html = "".join(f"<li>{o}</li>" for o in consolidado.observaciones_motor)
    
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8" />
<title>Bandeja de Revisión TMA — Folio {predio.folio_matricula}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{
    font-family: "Calibri", "Segoe UI", system-ui, -apple-system, sans-serif;
    color: {COLORS['body']};
    background: #f0f0f0;
    margin: 0;
    padding: 24px 16px;
    line-height: 1.55;
    font-size: 14px;
  }}
  .container {{
    max-width: 980px;
    margin: 0 auto;
    background: white;
    box-shadow: 0 2px 14px rgba(0,0,0,0.08);
    border-radius: 4px;
    overflow: hidden;
  }}
  .header {{
    background: {COLORS['ink']};
    color: white;
    padding: 24px 36px;
    border-bottom: 4px solid {COLORS['accent']};
  }}
  .header h1 {{
    font-family: Cambria, Georgia, serif;
    font-size: 28px;
    margin: 0 0 4px 0;
  }}
  .header .sub {{ font-size: 14px; opacity: 0.85; }}
  .header .meta {{ font-size: 12px; opacity: 0.7; margin-top: 8px; font-family: Consolas, monospace; }}
  
  .body {{ padding: 24px 36px; }}
  
  .estado-banner {{
    background: {estado_bg};
    border-left: 6px solid {estado_color};
    padding: 18px 24px;
    margin: 0 0 24px 0;
    border-radius: 3px;
  }}
  .estado-banner .label {{
    font-family: Cambria, Georgia, serif;
    font-size: 22px;
    font-weight: bold;
    color: {estado_color};
  }}
  .estado-banner .tiempo {{
    font-size: 13px;
    color: {COLORS['ink']};
    margin-top: 4px;
  }}
  .estado-banner .razon {{
    font-size: 13px;
    color: {COLORS['body']};
    margin-top: 10px;
  }}
  
  .resultado-grande {{
    text-align: center;
    background: {COLORS['accent']};
    color: white;
    padding: 24px;
    border-radius: 4px;
    margin: 24px 0;
  }}
  .resultado-grande .num {{
    font-family: Cambria, Georgia, serif;
    font-size: 42px;
    font-weight: bold;
  }}
  .resultado-grande .lab {{ font-size: 12px; opacity: 0.85; letter-spacing: 0.1em; }}
  .resultado-grande .banda {{ font-size: 14px; margin-top: 8px; opacity: 0.95; }}
  
  .info-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
    margin: 18px 0;
  }}
  .info-card {{
    background: {COLORS['panel']};
    padding: 14px 18px;
    border-radius: 3px;
  }}
  .info-card .lab {{ font-size: 10px; color: {COLORS['muted']}; letter-spacing: 0.05em; }}
  .info-card .val {{ font-size: 14px; color: {COLORS['ink']}; font-weight: 600; }}
  
  h2 {{
    font-family: Cambria, Georgia, serif;
    color: {COLORS['ink']};
    font-size: 20px;
    border-bottom: 2px solid {COLORS['accent']};
    padding-bottom: 6px;
    margin: 28px 0 16px 0;
  }}
  
  .method-card {{
    background: white;
    border: 1px solid {COLORS['rule']};
    padding: 16px 18px;
    margin: 14px 0;
    border-radius: 3px;
  }}
  
  details summary {{ outline: none; }}
  details summary::marker {{ color: {COLORS['accent']}; }}
  
  .obs-motor {{
    background: {COLORS['newSoft']};
    border-left: 5px solid {COLORS['new']};
    padding: 12px 18px;
    margin: 16px 0;
    border-radius: 3px;
  }}
  .obs-motor h3 {{
    font-family: Cambria, Georgia, serif;
    margin: 0 0 8px 0;
    color: {COLORS['new']};
    font-size: 14px;
  }}
  
  .acciones {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
    margin: 28px 0 16px 0;
  }}
  .btn {{
    padding: 16px 24px;
    border-radius: 4px;
    text-align: center;
    font-weight: bold;
    cursor: pointer;
    font-size: 14px;
    border: none;
    transition: transform 0.05s;
  }}
  .btn:hover {{ transform: translateY(-1px); }}
  .btn.primary {{
    background: {COLORS['ok']};
    color: white;
  }}
  .btn.secondary {{
    background: white;
    color: {COLORS['ink']};
    border: 2px solid {COLORS['rule']};
  }}
  .btn.warn {{
    background: {COLORS['warn']};
    color: white;
  }}
  
  .signature-zone {{
    border: 2px dashed {COLORS['accent']};
    padding: 24px;
    margin: 24px 0;
    background: {COLORS['panel']};
    border-radius: 4px;
    text-align: center;
  }}
  .signature-zone .cap {{
    font-style: italic;
    color: {COLORS['muted']};
    margin-bottom: 12px;
    font-size: 13px;
  }}
  .signature-zone .input-row {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
    margin: 12px 0;
    text-align: left;
  }}
  .signature-zone .input-row > div {{
    background: white;
    padding: 12px;
    border-radius: 3px;
    border: 1px solid {COLORS['rule']};
  }}
  .signature-zone label {{ font-size: 11px; color: {COLORS['muted']}; text-transform: uppercase; }}
  
  .audit-trail {{
    background: {COLORS['ink']};
    color: white;
    padding: 18px 24px;
    margin: 24px 0 0 0;
    font-family: Consolas, Monaco, monospace;
    font-size: 11px;
    line-height: 1.7;
    border-radius: 3px;
  }}
  .audit-trail h3 {{
    font-family: Cambria, Georgia, serif;
    font-size: 14px;
    margin: 0 0 10px 0;
    color: {COLORS['accentSoft']};
  }}
  
  .pequeño {{ font-size: 11px; color: {COLORS['muted']}; }}
</style>
</head>
<body>
<div class="container">

  <div class="header">
    <h1>Bandeja de Revisión TMA</h1>
    <div class="sub">Triangulación Metodológica Asistida — Estándar LAI v1.0</div>
    <div class="meta">Folio {predio.folio_matricula} · Hash avalúo: <code>{consolidado.hash_avaluo[:24]}…</code></div>
  </div>

  <div class="body">

    <div class="estado-banner">
      <div class="label">{estado_label}</div>
      <div class="tiempo">{estado_tiempo}</div>
      <div class="razon">{consolidado.razon_estado}</div>
    </div>

    <h2>Activo bajo avalúo</h2>
    <div class="info-grid">
      <div class="info-card"><div class="lab">FOLIO MATRÍCULA</div><div class="val">{predio.folio_matricula}</div></div>
      <div class="info-card"><div class="lab">DIRECCIÓN</div><div class="val">{predio.direccion}</div></div>
      <div class="info-card"><div class="lab">ÁREA CONSTRUIDA</div><div class="val">{predio.area_construida_m2} m²</div></div>
      <div class="info-card"><div class="lab">COEF. COPROPIEDAD</div><div class="val">{predio.coeficiente_copropiedad*100:.4f}%</div></div>
      <div class="info-card"><div class="lab">ESTRATO / TIPOLOGÍA</div><div class="val">Estrato {predio.estrato} · {predio.tipologia}</div></div>
      <div class="info-card"><div class="lab">ANTIGÜEDAD</div><div class="val">{predio.antiguedad_anos} años · Piso {predio.piso}</div></div>
    </div>

    <div class="resultado-grande">
      <div class="lab">VALOR CONSOLIDADO TMA</div>
      <div class="num">{fmt_cop(consolidado.valor_consolidado_cop)}</div>
      <div class="banda">Banda 80%: {fmt_cop(consolidado.banda_consolidada_baja_cop)} — {fmt_cop(consolidado.banda_consolidada_alta_cop)}</div>
      <div class="pequeño" style="color:rgba(255,255,255,0.85);margin-top:8px;">$/m² central: {fmt_m2(int(consolidado.valor_consolidado_cop / predio.area_construida_m2))} · Distancia máxima entre métodos: {consolidado.distancia_max_observada_pct*100:.2f}%</div>
    </div>

    <h2>Métodos valuatorios aplicados</h2>
    <p class="pequeño" style="margin-bottom:14px;">Cada método se ejecutó independientemente con sus propios insumos sellados criptográficamente. Los métodos efectivos en consolidado están resaltados.</p>

    {metodos_html}

    <div class="obs-motor">
      <h3>Observaciones del motor de consolidación</h3>
      <ul style="margin:0;font-size:13px;">{obs_motor_html}</ul>
    </div>

    <h2>Regla de consolidación aplicada</h2>
    <div class="info-grid">
      <div class="info-card"><div class="lab">AUTOR DE LA REGLA</div><div class="val">{consolidado.regla_consolidacion.autor}</div></div>
      <div class="info-card"><div class="lab">VERSIÓN</div><div class="val">{consolidado.regla_consolidacion.version}</div></div>
      <div class="info-card"><div class="lab">PESOS DECLARADOS</div><div class="val">{', '.join(f'{k}={v*100:.0f}%' for k,v in consolidado.regla_consolidacion.pesos.items())}</div></div>
      <div class="info-card"><div class="lab">TOLERANCIA COHERENCIA</div><div class="val">{consolidado.regla_consolidacion.tolerancia_coherencia_pct*100:.0f}%</div></div>
    </div>

    <h2>Zona de firma del avaluador RAA</h2>
    <div class="signature-zone">
      <div class="cap">Validado el avalúo consolidado y los hashes de los insumos, el avaluador procede a firmar.<br/>Esta firma adhiere el dictamen al régimen de la Ley 1673 de 2013.</div>
      
      <div class="input-row">
        <div><label>NOMBRE DEL AVALUADOR</label><div style="margin-top:4px;font-weight:bold;">[A diligenciar]</div></div>
        <div><label>INSCRIPCIÓN RAA</label><div style="margin-top:4px;font-weight:bold;">[N° RAA]</div></div>
        <div><label>ERA AFILIACIÓN</label><div style="margin-top:4px;font-weight:bold;">[ANA / ANAV / RNA]</div></div>
        <div><label>CATEGORÍA RAA</label><div style="margin-top:4px;font-weight:bold;">Categoría 2 — Inmuebles urbanos</div></div>
      </div>
      
      <div style="margin:18px 0;">
        <label style="font-size:11px;color:{COLORS['muted']};text-transform:uppercase;">VALOR FINAL DETERMINADO POR EL AVALUADOR</label>
        <div style="margin-top:6px;font-family:Cambria;font-size:24px;font-weight:bold;color:{COLORS['ink']};">
          {fmt_cop(consolidado.valor_consolidado_cop)} <span style="font-size:13px;font-weight:normal;color:{COLORS['muted']};">(ajustable dentro de la banda 80%)</span>
        </div>
      </div>

      <div class="acciones">
        <button class="btn primary">✓ FIRMAR Y EMITIR DICTAMEN</button>
        <button class="btn secondary">⊘ AJUSTAR VALOR Y FIRMAR</button>
      </div>
      <div class="acciones">
        <button class="btn secondary">▸ Solicitar visita in situ</button>
        <button class="btn warn">✗ Rechazar — devolver al motor</button>
      </div>
    </div>

    <div class="audit-trail">
      <h3>Cadena de auditoría criptográfica</h3>
      <div>Hash avalúo consolidado: <span style="color:{COLORS['accentSoft']};">{consolidado.hash_avaluo}</span></div>
      <div>Fecha de cálculo: {consolidado.fecha_calculo}</div>
      <div>Métodos ejecutados (hashes):</div>
      {''.join(f'<div style="margin-left:16px;">  · {m.metodo}: <span style="color:{COLORS["accentSoft"]};">{m.hash_resultado}</span></div>' for m in consolidado.metodos_ejecutados)}
      <div style="margin-top:10px;">Total insumos sellados: {sum(len(m.insumos) for m in consolidado.metodos_ejecutados)}</div>
      <div>Total ajustes documentados: {sum(len(m.ajustes_aplicados) for m in consolidado.metodos_ejecutados)}</div>
      <div style="margin-top:10px;color:{COLORS['accentSoft']};">Cualquier modificación posterior al cálculo de los insumos invalida los hashes y se detecta automáticamente en auditoría.</div>
    </div>

  </div>
</div>
</body>
</html>
"""
    return html


def firmar_avaluo(
    consolidado: AvaluoConsolidado,
    avaluador_nombre: str,
    raa_inscripcion: str,
    era_afiliacion: str,
    categoria_raa: str,
    valor_final_determinado: int = None,
    observaciones: str = ""
) -> FirmaAvaluador:
    """
    Aplica la firma del avaluador sobre el consolidado.
    
    En producción real: la firma_ed25519 se calcula con la clave privada del avaluador
    sobre el hash del avalúo. Aquí simulamos con un hash determinístico.
    """
    if valor_final_determinado is None:
        valor_final_determinado = consolidado.valor_consolidado_cop
    
    # Validar que el valor final esté dentro de banda
    if not (consolidado.banda_consolidada_baja_cop <= valor_final_determinado <= consolidado.banda_consolidada_alta_cop):
        raise ValueError(
            f"Valor final ${valor_final_determinado:,} fuera de banda 80% "
            f"(${consolidado.banda_consolidada_baja_cop:,} - ${consolidado.banda_consolidada_alta_cop:,}). "
            f"Si el avaluador desea firmar fuera de banda debe documentar la razón explícita y elevar el dictamen."
        )
    
    # Hash criptográfico simulado (en producción: Ed25519 con clave privada del avaluador)
    payload_firma = {
        "hash_avaluo": consolidado.hash_avaluo,
        "avaluador": avaluador_nombre,
        "raa": raa_inscripcion,
        "valor_final": valor_final_determinado,
        "fecha": datetime.now().isoformat(),
    }
    firma_simulada = stable_hash(payload_firma)
    
    firma = FirmaAvaluador(
        avaluador_nombre=avaluador_nombre,
        raa_inscripcion=raa_inscripcion,
        era_afiliacion=era_afiliacion,
        categoria_raa=categoria_raa,
        fecha_firma=datetime.now().isoformat(),
        hash_avaluo_firmado=consolidado.hash_avaluo,
        firma_ed25519=f"ED25519-SIMULATED:{firma_simulada}",
        valor_final_determinado_cop=valor_final_determinado,
        observaciones_avaluador=observaciones,
    )
    
    return firma


if __name__ == "__main__":
    sys.path.insert(0, '/home/claude/tma_engine/datos')
    from insumos_napoli import (
        PREDIO_NAPOLI_430, COMPARABLES_NAPOLI_MIRAMAR,
        COSTOS_CAMACOL_2026, VALOR_SUELO_MIRAMAR_2026, CANONES_MIRAMAR_2026
    )
    from pieza_1_M1_comparacion_mercado import construir_M1
    from pieza_2_M2_costo_reposicion import construir_M2
    from pieza_3_M3_capitalizacion_rentas import construir_M3
    from pieza_4_motor_consolidacion import consolidar
    
    print("="*70)
    print("PIEZA 5 — Bandeja de Revisión y Firma del Avaluador")
    print("="*70)
    
    # Pipeline completo
    m1 = construir_M1(PREDIO_NAPOLI_430, COMPARABLES_NAPOLI_MIRAMAR)
    m2 = construir_M2(PREDIO_NAPOLI_430, COSTOS_CAMACOL_2026, VALOR_SUELO_MIRAMAR_2026)
    m3 = construir_M3(PREDIO_NAPOLI_430, CANONES_MIRAMAR_2026)
    consolidado = consolidar(PREDIO_NAPOLI_430, [m1, m2, m3])
    
    # Generar bandeja HTML
    html = generar_bandeja_html(consolidado)
    out_path = "/home/claude/tma_engine/outputs/bandeja_revision_napoli.html"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"\n✓ Bandeja HTML generada: {out_path}")
    print(f"  Tamaño: {len(html):,} bytes")
    print(f"  Estado: {consolidado.estado}")
    print(f"  Tiempo de revisión esperado: {ESTADO_COLORS[consolidado.estado][3]}")
    
    # Simular firma del avaluador (Franco como ejemplo)
    print(f"\n--- Simulación de firma del avaluador ---")
    firma = firmar_avaluo(
        consolidado=consolidado,
        avaluador_nombre="[Avaluador firmante - a designar]",
        raa_inscripcion="[N° RAA del avaluador]",
        era_afiliacion="[ANA/ANAV/RNA]",
        categoria_raa="Categoría 2 — Inmuebles urbanos",
        valor_final_determinado=consolidado.valor_consolidado_cop,
        observaciones="Avalúo consolidado dentro de banda 80%; tres métodos convergen con coherencia metodológica fuerte."
    )
    
    print(f"  Firma aplicada (simulación):")
    print(f"    Avaluador:        {firma.avaluador_nombre}")
    print(f"    Valor final:      {fmt_cop(firma.valor_final_determinado_cop)}")
    print(f"    Hash firmado:     {firma.hash_avaluo_firmado[:24]}…")
    print(f"    Firma simulada:   {firma.firma_ed25519[:50]}…")
    print(f"    Fecha firma:      {firma.fecha_firma}")

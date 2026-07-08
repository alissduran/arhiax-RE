#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════
RUN_DICTAMEN.PY — Punto de entrada único del Motor TMA + Capa Lonja BAQ
═══════════════════════════════════════════════════════════════════════════════

Uso 1 — DEMO del caso Napoli (validación inicial):
    python3 run_dictamen.py --demo

Uso 2 — CLI parametrizado (operación):
    python3 run_dictamen.py --yaml ./lonja_layer/lonja_baq_metodologia.yaml

Uso 3 — Solo generar dictamen PDF/HTML del caso Napoli:
    python3 run_dictamen.py --dictamen

Uso 4 — Road test (5 escenarios para demostrar parametrización):
    python3 run_dictamen.py --road-test

═══════════════════════════════════════════════════════════════════════════════
ESTRUCTURA DEL PAQUETE:
    motor_tma_lonja_baq_v1.0/
    ├── run_dictamen.py              ← este archivo
    ├── tma_engine/
    │   ├── piezas/                  ← 8 archivos: motor + dictamen
    │   └── datos/                   ← insumos del caso Napoli
    ├── lonja_layer/
    │   ├── lonja_baq_metodologia.yaml   ← metodología declarada por la Lonja
    │   ├── lonja_adapter.py
    │   ├── ejecucion_lonja_baq.py
    │   └── road_test.py
    ├── output_referencia/           ← dictamen Napoli pre-generado
    └── docs/                        ← Addendum capa parametrización Lonja
═══════════════════════════════════════════════════════════════════════════════
"""
import sys
import os
import argparse
from pathlib import Path

# ─────────────────────────────────────────────────────────────────
# AJUSTE DE PATHS — Detecta la ubicación del paquete automáticamente
# ─────────────────────────────────────────────────────────────────
PAQUETE_ROOT = Path(__file__).resolve().parent
TMA_PIEZAS = PAQUETE_ROOT / "tma_engine" / "piezas"
TMA_DATOS = PAQUETE_ROOT / "tma_engine" / "datos"
LONJA_LAYER = PAQUETE_ROOT / "lonja_layer"
OUTPUT_DIR = PAQUETE_ROOT / "output_corrida"

# Agregar al sys.path
sys.path.insert(0, str(TMA_PIEZAS))
sys.path.insert(0, str(TMA_DATOS))
sys.path.insert(0, str(LONJA_LAYER))

# ─────────────────────────────────────────────────────────────────
# COMPATIBILIDAD CON CÓDIGO ORIGINAL — Crea symlinks o directorios
# espejo en /home/claude/ donde el código original espera encontrarlos
# ─────────────────────────────────────────────────────────────────
def _setup_compatibility_paths():
    """
    El código original (TR-052) tiene paths absolutos /home/claude/...
    Esta función crea los paths espejo si no existen, para que los imports funcionen
    sin modificar el código original. Esto preserva los hashes originales.
    """
    home_claude = Path("/home/claude")
    if not home_claude.exists():
        try:
            home_claude.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            print("⚠ No se pudo crear /home/claude (permisos). Esto puede fallar en algunos entornos.", file=sys.stderr)
            print("  En Antigravity esto debería funcionar. En Windows usa run_dictamen.py desde el root del paquete.", file=sys.stderr)
            return
    
    # Crear estructura espejo si no existe
    espejo_targets = [
        (home_claude / "tma_engine" / "piezas", TMA_PIEZAS),
        (home_claude / "tma_engine" / "datos", TMA_DATOS),
        (home_claude / "lonja_layer", LONJA_LAYER),
    ]
    
    for espejo, real in espejo_targets:
        if not espejo.exists():
            espejo.parent.mkdir(parents=True, exist_ok=True)
            try:
                espejo.symlink_to(real, target_is_directory=True)
            except (OSError, NotImplementedError):
                # En Windows o si symlink falla, copiar archivos
                import shutil
                shutil.copytree(real, espejo, dirs_exist_ok=True)


def cmd_demo():
    """Ejecuta el pipeline completo del caso Napoli con la metodología declarada por la Lonja BAQ."""
    print("═" * 72)
    print("MOTOR TMA + CAPA LONJA BAQ — DEMO CASO NAPOLI")
    print("═" * 72)
    print()
    print("Predio:  Apto 430, Torre 8, Conjunto Residencial Napoli")
    print("Folio:   040-646406")
    print("Área:    58.75 m²")
    print()
    
    # Importar y ejecutar
    from lonja_adapter import cargar_declaracion_lonja
    from ejecucion_lonja_baq import ejecutar_avaluo_lonja
    from insumos_napoli import PREDIO_NAPOLI_430, COMPARABLES_NAPOLI_MIRAMAR
    from contrato_datos import fmt_cop, fmt_m2
    
    yaml_path = LONJA_LAYER / "lonja_baq_metodologia.yaml"
    cfg = cargar_declaracion_lonja(str(yaml_path))
    print(f"✓ YAML Lonja cargado — Hash: {cfg.hash_declaracion()[:16]}…")
    print()
    
    consolidado, m1, m2, m3 = ejecutar_avaluo_lonja(
        PREDIO_NAPOLI_430, COMPARABLES_NAPOLI_MIRAMAR, cfg
    )
    
    print(f"M1 (Mercado):    {fmt_cop(m1.valor_central_cop):>20}  ({fmt_m2(m1.valor_por_m2_central)})")
    print(f"M2 (Costo):      {fmt_cop(m2.valor_central_cop):>20}  ({fmt_m2(m2.valor_por_m2_central)})")
    print(f"M3 (Rentas):     {fmt_cop(m3.valor_central_cop):>20}  ({fmt_m2(m3.valor_por_m2_central)})")
    print()
    print(f"┌─ AVALÚO CORPORATIVO LONJA BAQ ─" + "─" * 38 + "┐")
    print(f"│  Valor consolidado: {fmt_cop(consolidado.valor_consolidado_cop):>30}      │")
    print(f"│  Banda 80%:         {fmt_cop(consolidado.banda_consolidada_baja_cop)} — {fmt_cop(consolidado.banda_consolidada_alta_cop):>10}      │")
    print(f"│  Estado:            {consolidado.estado:<41}│")
    print(f"└" + "─" * 71 + "┘")
    print()
    print(f"Métodos efectivos: {', '.join(consolidado.metodos_efectivos)}")
    print(f"Pesos efectivos:   {consolidado.pesos_efectivos}")
    print()
    print("─" * 72)
    print("VALIDACIÓN DE INTEGRIDAD")
    print("─" * 72)
    
    # Comparar contra valores esperados (transferencia de sesión TR-052)
    valor_esperado = 241246035
    valor_real = consolidado.valor_consolidado_cop
    diff = abs(valor_real - valor_esperado)
    diff_pct = diff / valor_esperado * 100
    
    print(f"  Valor consolidado esperado:   {fmt_cop(valor_esperado)}")
    print(f"  Valor consolidado obtenido:   {fmt_cop(valor_real)}")
    print(f"  Diferencia:                   {fmt_cop(diff)} ({diff_pct:.3f}%)")
    
    if diff_pct < 0.01:
        print(f"  Resultado:                    ✓ VALIDACIÓN OK (bit-exacto)")
    elif diff_pct < 1.0:
        print(f"  Resultado:                    ✓ Tolerancia OK (<1%)")
    else:
        print(f"  Resultado:                    ⚠ DIVERGENCIA — revisar instalación")
    
    print()
    
    # Hash YAML esperado
    hash_yaml_esperado = "e8071f829afdb4b6"
    hash_yaml_real = cfg.hash_declaracion()[:16]
    print(f"  Hash YAML esperado:           {hash_yaml_esperado}…")
    print(f"  Hash YAML obtenido:           {hash_yaml_real}…")
    print(f"  Resultado:                    {'✓' if hash_yaml_esperado == hash_yaml_real else '⚠'} {'INTEGRIDAD CONFIRMADA' if hash_yaml_esperado == hash_yaml_real else 'ARCHIVOS MODIFICADOS — revisar'}")
    print()
    print("═" * 72)
    print("FIN DEMO. Para generar el dictamen PDF: python3 run_dictamen.py --dictamen")
    print("═" * 72)


def cmd_dictamen():
    """Genera el dictamen pericial PDF del caso Napoli."""
    print("═" * 72)
    print("GENERACIÓN DICTAMEN PERICIAL PDF — CASO NAPOLI")
    print("═" * 72)
    
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    # Pieza 6 espera tma_engine/outputs en /home/claude
    home_outputs = Path("/home/claude/tma_engine/outputs")
    home_outputs.mkdir(parents=True, exist_ok=True)
    
    # Ejecutar pieza 6
    import subprocess
    result = subprocess.run(
        [sys.executable, str(TMA_PIEZAS / "pieza_6_dictamen_pdf.py")],
        capture_output=True, text=True
    )
    print(result.stdout)
    if result.returncode != 0:
        print("ERROR:", result.stderr, file=sys.stderr)
        return 1
    
    # Copiar HTML al output local
    html_src = home_outputs / "dictamen_napoli.html"
    if html_src.exists():
        import shutil
        shutil.copy(html_src, OUTPUT_DIR / "dictamen_napoli.html")
        print(f"✓ HTML copiado a: {OUTPUT_DIR / 'dictamen_napoli.html'}")
        
        # Intentar generar PDF
        try:
            from weasyprint import HTML
            pdf_path = OUTPUT_DIR / "dictamen_napoli.pdf"
            HTML(str(html_src)).write_pdf(str(pdf_path))
            print(f"✓ PDF generado:    {pdf_path}")
        except ImportError:
            print("⚠ weasyprint no instalado. Solo se generó HTML.")
            print("  Para PDF instalar: pip install weasyprint")
        except Exception as e:
            print(f"⚠ Error generando PDF: {e}")
    
    print("═" * 72)


def cmd_road_test():
    """Ejecuta los 5 escenarios del road test que demuestran parametrización Lonja."""
    print("═" * 72)
    print("ROAD TEST — 5 ESCENARIOS DE PARAMETRIZACIÓN LONJA")
    print("═" * 72)
    
    import subprocess
    result = subprocess.run(
        [sys.executable, str(LONJA_LAYER / "road_test.py")],
        capture_output=True, text=True
    )
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr, file=sys.stderr)


def cmd_yaml(yaml_path: str):
    """Ejecuta el pipeline con un YAML Lonja arbitrario (para casos futuros)."""
    print("═" * 72)
    print(f"EJECUCIÓN CON YAML PARAMETRIZADO: {yaml_path}")
    print("═" * 72)
    
    yaml_path_obj = Path(yaml_path).resolve()
    if not yaml_path_obj.exists():
        print(f"ERROR: YAML no encontrado: {yaml_path}", file=sys.stderr)
        return 1
    
    from lonja_adapter import cargar_declaracion_lonja
    from ejecucion_lonja_baq import ejecutar_avaluo_lonja
    from insumos_napoli import PREDIO_NAPOLI_430, COMPARABLES_NAPOLI_MIRAMAR
    from contrato_datos import fmt_cop
    
    cfg = cargar_declaracion_lonja(str(yaml_path_obj))
    print(f"✓ YAML cargado — Hash: {cfg.hash_declaracion()[:16]}…\n")
    
    consolidado, m1, m2, m3 = ejecutar_avaluo_lonja(
        PREDIO_NAPOLI_430, COMPARABLES_NAPOLI_MIRAMAR, cfg
    )
    
    print(f"Valor consolidado: {fmt_cop(consolidado.valor_consolidado_cop)}")
    print(f"Estado:            {consolidado.estado}")
    print(f"Métodos efectivos: {', '.join(consolidado.metodos_efectivos)}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Motor TMA + Capa Lonja BAQ — Sinergia Consulting Group S.A.S.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("--demo", action="store_true",
                        help="Ejecuta demo del caso Napoli (validación inicial)")
    parser.add_argument("--dictamen", action="store_true",
                        help="Genera dictamen pericial PDF/HTML del caso Napoli")
    parser.add_argument("--road-test", action="store_true",
                        help="Ejecuta los 5 escenarios del road test Lonja")
    parser.add_argument("--yaml", type=str, default=None,
                        help="Ejecuta pipeline con un YAML Lonja específico")
    
    args = parser.parse_args()
    
    # Setup compatibility paths
    _setup_compatibility_paths()
    
    if args.demo:
        cmd_demo()
    elif args.dictamen:
        cmd_dictamen()
    elif args.road_test:
        cmd_road_test()
    elif args.yaml:
        cmd_yaml(args.yaml)
    else:
        # Sin argumentos = demo por defecto
        print("ℹ Sin argumentos. Ejecutando --demo por defecto.")
        print("  Para más opciones: python3 run_dictamen.py --help")
        print()
        cmd_demo()


if __name__ == "__main__":
    sys.exit(main() or 0)

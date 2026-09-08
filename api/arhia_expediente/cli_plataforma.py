"""CLI de la plataforma: ejecuta un dictamen desde un JSON y genera MD/HTML/PDF.

Uso:
    py -m arhia_expediente.cli_plataforma caso.json [--out directorio]
"""
import argparse
import json
import os
import sys

from arhia_expediente.plataforma import (dictamen_a_json, ejecutar_desde_json, generar_dictamen_markdown,
                                         generar_dictamen_html)
from arhia_expediente.pdf_render import generar_dictamen_pdf


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("caso_json")
    parser.add_argument("--out", default=None, help="directorio de salida (MD/HTML/PDF)")
    parser.add_argument("--json", action="store_true", help="imprimir solo el JSON del dictamen")
    args = parser.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    with open(args.caso_json, encoding="utf-8") as f:
        payload = json.load(f)
    d = ejecutar_desde_json(payload)
    resumen = dictamen_a_json(d)

    if args.json:
        print(json.dumps(resumen, ensure_ascii=False, indent=2))
        return

    print("=== DICTAMEN COMPLETO ===")
    print(f"Caso: {d.caso.id} · Tipo: {d.caso.tipo}")
    print(f"Veredicto: {d.conclusion.veredicto}")
    print(f"Fundamento: {d.conclusion.fundamento}")
    print(f"Cumplimiento: régimen {d.integridad.regimen} · screening {d.integridad.screening} · "
          f"BF {d.integridad.beneficiario_final or '-'} · perfil {d.integridad.perfil}")
    print(f"Eventos de evidencia: {len(d.compliance_eventos)} (hmacChain: "
          f"{all(e.get('hmacChain') for e in d.compliance_eventos)})")

    out_dir = args.out or os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.join(out_dir, "dictamen_" + (d.caso.id or "caso"))
    with open(base + ".md", "w", encoding="utf-8") as f:
        f.write(generar_dictamen_markdown(d))
    with open(base + ".html", "w", encoding="utf-8") as f:
        f.write(generar_dictamen_html(d))
    pdf = generar_dictamen_pdf(d, base + ".pdf")
    print(f"Markdown: {os.path.abspath(base + '.md')}")
    print(f"HTML    : {os.path.abspath(base + '.html')}")
    print(f"PDF     : {pdf}")


if __name__ == "__main__":
    main()

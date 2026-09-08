"""Demo del marco documental SAGRILAFT+PTEE (manual, código de ética, política, matriz)."""
import io
import os
import sys

from arhia_sag_screen.marco_documental import generar_marco_documental


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    m = generar_marco_documental("ARHIAX REAL ESTATE S.A.S", "pleno_reforzado", entidad_nit="901234567")
    print("=== MANUAL SAGRILAFT+PTEE (extracto) ===")
    print("\n".join(m.manual.split("\n")[:7]))
    print("\n=== CÓDIGO DE ÉTICA (extracto) ===")
    print("\n".join(m.codigo_etica.split("\n")[:4]))
    print("\n=== MATRIZ DE RIESGO ===")
    for r in m.matriz:
        print(f"  {r['id']} [{r['categoria']}] {r['factor']} | inherente {r['riesgo_inherente']} "
              f"-> residual {r['riesgo_residual']} | control {r['control']} | {r['responsable']}")

    out_dir = os.path.join(os.path.dirname(__file__), "data", "marco_documental")
    os.makedirs(out_dir, exist_ok=True)
    docs = {"manual_sagrilaft_ptee": m.manual, "codigo_etica": m.codigo_etica,
            "politica_riesgos": m.politica_riesgos}
    for name, txt in docs.items():
        with io.open(os.path.join(out_dir, name + ".md"), "w", encoding="utf-8") as f:
            f.write(txt)
    # matriz como tabla MD
    with io.open(os.path.join(out_dir, "matriz_riesgo.md"), "w", encoding="utf-8") as f:
        f.write("# Matriz de riesgo SAGRILAFT+PTEE\n\n| ID | Categoría | Factor | Prob | Impacto | Inherente | Control | Residual | Responsable |\n")
        f.write("|---|---|---|---|---|---|---|---|---|\n")
        for r in m.matriz:
            f.write(f"| {r['id']} | {r['categoria']} | {r['factor']} | {r['probabilidad']} | "
                    f"{r['impacto']} | {r['riesgo_inherente']} | {r['control']} | "
                    f"{r['riesgo_residual']} | {r['responsable']} |\n")
    print("\nMarco documental escrito en:", os.path.abspath(out_dir))


if __name__ == "__main__":
    main()

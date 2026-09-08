"""Demo del pipeline único de cumplimiento."""
import sys

from arhia_sag_screen.compliance import evaluar_operacion
from arhia_sag_screen.contracts import Accionista, Contraparte, RegistroJuridico, RegistroNormalizado


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    cp = Contraparte("cp-1", "juridica", "PARQUE INDUSTRIAL CLAVERIA S.A.S", "nit", "900253457")
    reg = RegistroJuridico(nit="900253457", razon_social="PARQUE INDUSTRIAL CLAVERIA S.A.S",
                           ingresos=50_000_000_000, activos=60_000_000_000, sector="inmobiliario",
                           composicion_accionaria=(Accionista("nit", "800123", "INVERSIONES CLAVERIA S.A", 0.60),))
    lista = [RegistroNormalizado(id="onu-1", nombre="PARQUE INDUSTRIAL CLAVERIA", fuente="onu")]
    r = evaluar_operacion(cp, {"monto": 400_000_000, "patronNormal": 100_000_000, "senales": ["pagoFraccionado"], "operacionId": "op-050"},
                          registro=reg, registros_lista=lista, catalogo_senales=("pagoPorTercero", "pagoFraccionado"))
    print("=== Reporte de Cumplimiento SAGRILAFT+PTEE ===")
    print(f"Contraparte: {r.nombre} ({r.contraparte_id})")
    print(f"Régimen: {r.regimen}")
    print(f"Screening: {r.screening}")
    print(f"Beneficiario final: {r.beneficiarios_finales}")
    print(f"Señales: {list(r.senales)}")
    print(f"Operación inusual: {r.operacion_inusual}")
    print(f"Perfil: {r.perfil}")
    print(f"Eventos emitidos: {len(r.eventos)} (todos con hmacChain: {all(e['hmacChain'] for e in r.eventos)})")


if __name__ == "__main__":
    main()

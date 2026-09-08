"""Demo end-to-end del pipeline único integrado SAGRILAFT+PTEE.

Recorre la cadena completa de UNA operación: régimen → screening → BF → matriz →
señales → DD → detección → ROS/AROS → corredor de caso → reporte, con evidencia
emitida por los bundes Rego (B20..B30) vía `opaclient` (motor OPA).
"""
import datetime
import os
import sys

from arhia_sag_screen.pipeline import ejecutar_pipeline
from arhia_sag_screen.contracts import Accionista, Contraparte, RegistroJuridico, RegistroNormalizado

SAG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "opa-rego", "sag"))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    now = datetime.datetime(2026, 9, 7, 12, 0, 0, tzinfo=datetime.timezone.utc)
    cp = Contraparte("cp-1", "juridica", "PARQUE INDUSTRIAL CLAVERIA S.A.S", "nit", "900253457")
    reg = RegistroJuridico(nit="900253457", razon_social="PARQUE INDUSTRIAL CLAVERIA S.A.S",
                           ingresos=50_000_000_000, activos=60_000_000_000, sector="inmobiliario",
                           representante_legal="JOSE PEREZ",
                           composicion_accionaria=(Accionista("nit", "800123", "INVERSIONES CLAVERIA S.A", 0.60),))
    lista = [RegistroNormalizado(id="onu-1", nombre="PEDRO GOMEZ", fuente="onu")]
    op = {"monto": 400_000_000, "patronNormal": 100_000_000, "senales": ["pagoFraccionado"],
          "operacionId": "op-050", "domicilio": "Calle 1", "beneficiarioFinal": "SI",
          "representanteLegal": "JOSE PEREZ", "personaContacto": "ANA", "cargo": "Gerente",
          "fechaConocimiento": "2026-01-01"}

    r = ejecutar_pipeline(cp, op, registro=reg, registros_lista=lista,
                          catalogo_senales=("pagoPorTercero", "pagoFraccionado"), now=now,
                          hmac_key="arhia-demo-sag-2026", opa_dir=SAG_DIR, engine="auto",
                          ultima_actualizacion=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
                          solicitudes_dd=1, ultimo_ros_ts=1590000000, ultimo_aros_ts=1590000000)

    print("=== PIPELINE ÚNICO INTEGRADO SAGRILAFT+PTEE ===")
    print(f"Contraparte : {r.nombre} ({r.contraparte_id})")
    print(f"Régimen     : {r.regimen}  [{r.fundamento_regimen}]")
    print(f"Screening   : {r.screening}")
    print(f"BFs         : {tuple(b.nombre for b in r.beneficiarios_finales)}")
    print(f"Perfil      : {r.perfil}  [factores: {list(r.factores)}]")
    print(f"Señales     : {list(r.senales)}")
    print(f"DD          : vencida={r.dd_vencida} inmediata={r.dd_inmediata} exceso={r.dd_exceso}")
    print(f"Detección   : inusual={r.operacion_inusual} requiere_analisis={r.requiere_analisis}")
    print(f"ROS/AROS    : aros_requerido={r.aros_requerido} ausencia_denuncias={r.ausencia_denuncias}")
    print(f"Caso        : {r.caso_id} -> {r.caso_estado}")
    print(f"Eventos     : {len(r.eventos)} (hmacChain: {all(e.get('hmacChain') for e in r.eventos)})")
    print("--- secuencia de evidencia ---")
    for i, e in enumerate(r.eventos, 1):
        print(f"  {i:>2}. [{e.get('controlId')}] {e.get('eventType')}")


if __name__ == "__main__":
    main()

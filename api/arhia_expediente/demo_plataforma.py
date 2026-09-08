"""Demo del Dictamen Completo integrado (título + SAGRILAFT/PTEE + expediente + conclusión).

Usa el folio real 040-347004 y modela una compraventa con un pago por tercero
(señal de alerta 9.20) para mostrar la conclusión del profesional simulado.
"""
import datetime
import io
import os
import sys

from arhia_title.contracts import Anotacion, Avaluo, Caso, Pago, Parte, Predio
from arhia_sag_screen.contracts import Accionista, RegistroJuridico, RegistroNormalizado
from arhia_expediente.plataforma import ejecutar_plataforma, generar_dictamen_markdown, generar_dictamen_html
from arhia_expediente.pdf_render import generar_dictamen_pdf

NOW = datetime.datetime(2026, 9, 7, 12, 0, 0, tzinfo=datetime.timezone.utc)
SAG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "opa-rego", "sag"))
SIIS_CSV = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Base_10000_empresas_2026.csv"))


def _caso():
    return Caso(
        id="DIC-040-347004", tipo="compraventa",
        predio=Predio("040-347004", "080010102000001710004000000000", "Carrera 54 # 75-206, Barranquilla",
                      area_registral=475.0, area_catastral=475.0),
        partes=(
            Parte("vendedor", "PARQUE INDUSTRIAL CLAVERIA S.A.S", "nit", "900253457", "INVERSIONES CLAVERIA S.A"),
            Parte("comprador", "INVERSIONES DEL CARIBE S.A.S", "nit", "901234567", "MIGUEL ANTONIO VEGA"),
        ),
        anotaciones=(
            Anotacion(1, "compraventa", "2001-03-21", "Esc 2001", titular="VICTOR DIAZ CLAVERIA CIA. S. EN C."),
            Anotacion(2, "hipoteca", "2009-03-03", "Esc 2009", detalle="Hipoteca BANCOLOMBIA", estado="cancelada"),
            Anotacion(3, "aclaracion", "2010-01-21", "Aclaración"),
            Anotacion(4, "compraventa", "2014-11-05", "Esc 2014", titular="PARQUE INDUSTRIAL CLAVERIA S.A.S"),
            Anotacion(5, "aclaracion", "2014-11-05", "Aclaración"),
            Anotacion(6, "cancelacion", "2017-08-09", "Cancelación hipoteca BANCOLOMBIA"),
        ),
        avaluo=Avaluo(1_800_000_000, "comparación de mercado", "2026-08-01", "Simulado — Avaluador RAA"),
        precio_pactado=1_800_000_000,
        pagos=(Pago(1_500_000_000, "transferencia", "MIGUEL ANTONIO VEGA", es_tercero=True),),
        titular="PARQUE INDUSTRIAL CLAVERIA S.A.S",
    )


def _registro_comprador():
    return RegistroJuridico(nit="901234567", razon_social="INVERSIONES DEL CARIBE S.A.S",
                            ingresos=20_000_000_000, activos=25_000_000_000, sector="inmobiliario",
                            representante_legal="JOSE PEREZ",
                            composicion_accionaria=(Accionista("cc", "999", "MIGUEL ANTONIO VEGA", 0.60),))


def _screening_envivo():
    """Intenta usar la lista ONU real; devuelve (registros, fuente, version, hash) o None."""
    try:
        from arhia_sag_screen.ingest.listas import ListaNoDisponible, preparar_screening
        regs, lista = preparar_screening("onu")
        return regs, lista.fuente, lista.version, lista.hash
    except Exception:
        return None


FUENTES_SARLAFT = ("onu", "ofac", "uiaf", "ue", "uk", "pep", "interpol")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print("Screening: multifuente SARLAFT -> " + ", ".join(FUENTES_SARLAFT)
          + " (ONU/OFAC en vivo · resto muestra versionada)")
    d = ejecutar_plataforma(
        _caso(), rol_contraparte="comprador", registro_contraparte=_registro_comprador(),
        fuentes_activas=FUENTES_SARLAFT,
        catalogo_senales=("pagoPorTercero", "pagoFraccionado"),
        senales_ptee=("usoIntermediario",), usa_intermediario=True, es_funcionario_publico=False,
        canal_denuncias=True,
        zona_predio="C1", actividad_predio="entretenimiento",
        patron_normal=500_000_000, now=NOW, hmac_key="arhia-demo-sag-2026",
        rub_fecha="2024-01-15", rub_pais="Colombia",
        opa_dir=SAG_DIR, engine="auto",
        ultima_actualizacion=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
        solicitudes_dd=1, ultimo_ros_ts=1590000000, ultimo_aros_ts=1590000000,
    )
    print(generar_dictamen_markdown(d))
    out = os.path.join(os.path.dirname(__file__), "data", "dictamen_040_347004_integrado.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with io.open(out, "w", encoding="utf-8") as f:
        f.write(generar_dictamen_html(d))
    print("\nHTML generado:", os.path.abspath(out))

    pdf = os.path.join(os.path.dirname(__file__), "data", "dictamen_040_347004_integrado.pdf")
    os.makedirs(os.path.dirname(pdf), exist_ok=True)
    print("PDF generado :", generar_dictamen_pdf(d, pdf))

    # --- Demostración: auto-régimen desde el SIIS real por NIT ---
    print("\n=== AUTO-RÉGIMEN SIIS (NIT real) ===")
    eco = Caso(id="DIC-SIIS", tipo="compraventa",
               predio=Predio("040-999999", "9999", "Barranquilla", 300.0, 300.0),
               partes=(Parte("vendedor", "FIDEICOMISO INDUSTRIAL S.A.S", "nit", "900000001"),
                       Parte("comprador", "ECOPETROL S.A", "nit", "899999068")),
               anotaciones=(Anotacion(1, "compraventa", "2010-01-01", titular="FIDEICOMISO INDUSTRIAL S.A.S"),),
               avaluo=Avaluo(2_000_000_000), precio_pactado=2_000_000_000,
               pagos=(Pago(2_000_000_000, "transferencia", "ECOPETROL S.A"),))
    d2 = ejecutar_plataforma(eco, rol_contraparte="comprador", siis_path=SIIS_CSV,
                             accionistas=(Accionista("cc", "1", "ESTADO COLOMBIANO", 0.88),),
                             registro_contraparte=None, catalogo_senales=("pagoPorTercero", "pagoFraccionado"),
                             patron_normal=1_000_000_000, now=NOW, hmac_key="arhia-demo-sag-2026",
                             engine="python")
    print(f"Contraparte: {d2.caso.id} · {d2.integridad.regimen} (auto-desde-SIIS) · BF: {d2.integridad.beneficiario_final} · Veredicto: {d2.conclusion.veredicto}")


if __name__ == "__main__":
    main()

"""Demo de la capa científica/patentométrica (XN) del MVP mejorado de ARHIAX.

Ejercita los elementos contribuyentes de las skills 1 y 2 en un solo flujo de consola:
  XN-1 libro de evidencia autoritativa · XN-2 identidad temporal/geométrica · XN-3 coherencia
  precio–avalúo con comparables · XN-4 derechos como capas temporales · XN-5 consentimiento auditado ·
  XN-6 flujo de cierre · XN-7 portabilidad/B18 · XN-8 conector SIREL + capas POT por polígono ·
  XN-9 harness de gold standard (gate FNR).

Todo sobre datos de prueba. NO se declara desempeño; XN-8 envío en vivo y XN-9 corpus real son GATED.
"""
import datetime

from arhia_title.contracts import Anotacion, Caso, Parte, Predio
from arhia_sag_screen.kyb.identidad import conciliar_identidad
from arhia_sag_screen.kyb.uso_suelo import analizar_uso_suelo
from arhia_sag_screen.kyb.portabilidad import registrar_consentimiento
from arhia_sag_screen.reporte_uiaf import OperacionSospechosa, ReporteROS
from arhia_sag_screen.sirel import preparar_sobre, enviar
from arhia_expediente.evidencia_autoritativa import (EV_FINDING_ACCEPTED, EV_REPORT_SIGNED,
                                                     LibroEvidenciaAutoridad)
from arhia_expediente.flujo_cierre import avanzar, construir_flujo
from arhia_expediente.gold_standard import corpus_sintetico, evaluar_corpus
from arhia_title.comparables import Comparable, analizar_con_comparables
from arhia_title.derechos import construir_capas

NOW = datetime.datetime(2026, 9, 8, 12, 0, 0, tzinfo=datetime.timezone.utc)


def _caso():
    return Caso("T-DEMO", "compraventa",
                Predio("040-1", "080010102", "Barranquilla", 80.0, 80.0),
                partes=(Parte("vendedor", "JUNIARYS ROCA", "cc", "1143"),
                        Parte("comprador", "X SAS", "nit", "900.1")),
                anotaciones=(Anotacion(1, "compraventa", "2010-05-10", titular="JUNIARYS ROCA"),
                             Anotacion(2, "hipoteca", "2015-03-15", detalle="Hipoteca abierta", estado="vigente")),
                titular="JUNIARYS ROCA")


def main():
    print("=== ARHIAX · Capa científica/patentométrica (XN) ===")
    caso = _caso()

    # XN-4 derechos como capas
    md = construir_capas(caso)
    print(f"[XN-4] {md.resumen}")

    # XN-3 coherencia precio–avalúo con comparables
    comps = (Comparable("c1", "Dir 1", 100, 400_000_000, 4_000_000, 0.90, "mercado"),
             Comparable("c2", "Dir 2", 90, 360_000_000, 4_000_000, 0.88, "mercado"))
    ac = analizar_con_comparables(520_000_000, 100, comps)
    print(f"[XN-3] {ac.motivo}")

    # XN-6 flujo de cierre
    fl = construir_flujo(caso.id)
    for e in ("PROMESA", "PROTOCOLO", "ESCRITURA"):
        fl = avanzar(fl, e, evidencia=(e.lower(),))
    print(f"[XN-6] {fl.progreso:.0%} · cuello de botella: {fl.cuello_botella}")

    # XN-1 libro de evidencia autoritativa
    libro = LibroEvidenciaAutoridad(now=NOW)
    libro.emitir(EV_FINDING_ACCEPTED, "TIT_B03", "abogado", "Dr. A.", "Acepto el hallazgo.", "CONFIRMADO")
    libro.emitir(EV_REPORT_SIGNED, "REP", "avaluador", "Ing. B.", "Valido y firmo.", "FIRMADO")
    print(f"[XN-1] {len(libro.eventos())} evento(s) de autoridad · cadena íntegra: {libro.cadena_integra()}")

    # XN-2 identidad temporal/geométrica
    fi = conciliar_identidad(caso, referencias={
        "coordenadas": {"folio": (11.0001, -74.8001), "catastro": (11.0002, -74.8002)},
        "validez": {"folio": "2027-01-01", "catastro": "2026-12-15"}})
    print(f"[XN-2] conciliado={fi.conciliado} · coords={fi.coord_consistentes} · "
          f"fuentes temporales={len(fi.fuentes_temporales)} · corrección silenciosa={fi.correccion_silenciosa}")

    # XN-5 consentimiento auditado
    cons = registrar_consentimiento("JUNIARYS ROCA", "transferir evidencia del expediente", ahora=NOW)
    print(f"[XN-5] {cons.quien} autorizó «{cons.que_autoriza}» ({cons.base_juridica})")

    # XN-8b capas POT por polígono
    pol = {"C1": [(11.00, -74.80), (11.01, -74.80), (11.01, -74.79), (11.00, -74.79)]}
    fsu = analizar_uso_suelo(caso.predio, "comercial", coordenadas=(11.005, -74.795), poligonos=pol)
    print(f"[XN-8b] zona por polígono: {fsu.zona} · actividad: {fsu.actividad_resultado}")

    # XN-8a conector SIREL (envío gated)
    op = OperacionSospechosa("cc", "1143", "JUNIARYS", "natural", "compraventa", 520_000_000,
                             "COP", ("marcoSospechoso",), "prueba", "2026-09-08")
    sobre = preparar_sobre(ReporteROS(entidad_nit="900.1", entidad_nombre="X SAS", operaciones=(op,)))
    env = enviar(sobre)
    print(f"[XN-8a] SIREL sobre validado (hash {sobre['hash'][:10]}…) · envío: {env.estado}")

    # XN-9 gold standard (fixture sintético)
    gs = evaluar_corpus(corpus_sintetico())
    print(f"[XN-9] gold standard (sintético): FNR={gs.fnr} · cobertura={gs.cobertura} · "
          f"gate_pasa={gs.gate_pasa} (corpus real GATED)")

    print("=== Fin de la capa XN (datos de prueba; desempeño no declarado) ===")


if __name__ == "__main__":
    main()

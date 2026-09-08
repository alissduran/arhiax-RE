"""Demo del monitoreo continuo de cartera — tablero + alertas de cumplimiento."""
import datetime
import sys

from arhia_sag_screen.contracts import Accionista, Contraparte, RegistroJuridico, RegistroNormalizado
from arhia_sag_screen.monitoreo import monitorear_cartera

NOW = datetime.datetime(2026, 9, 7, 12, 0, 0, tzinfo=datetime.timezone.utc)


def _reg(nit, nombre, ingresos, activos, accionista):
    return RegistroJuridico(nit=nit, razon_social=nombre, ingresos=ingresos, activos=activos,
                            sector="inmobiliario", representante_legal="JOSE",
                            composicion_accionaria=(Accionista("cc", "1", accionista, 0.60),))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    items = [
        {"contraparte": Contraparte("cp-1", "juridica", "ALFA ARRIENDOS S.A.S", "nit", "900001"),
         "registro": _reg("900001", "ALFA ARRIENDOS S.A.S", 60_000_000_000, 70_000_000_000, "JUAN GOMEZ"),
         "operacion": {"operacionId": "op-1", "monto": 400_000_000, "patronNormal": 100_000_000,
                       "senales": ["pagoPorTercero"], "senalesPTEE": ("usoIntermediario",),
                       "usaIntermediario": True, "canalDenuncias": True}},
        {"contraparte": Contraparte("cp-2", "juridica", "BETA INMOBILIARIA S.A.S", "nit", "900002"),
         "registro": _reg("900002", "BETA INMOBILIARIA S.A.S", 5_000_000_000, 6_000_000_000, "JOSE PEREZ"),
         "operacion": {"operacionId": "op-2", "monto": 80_000_000, "patronNormal": 100_000_000,
                       "senales": (), "canalDenuncias": True}},
        {"contraparte": Contraparte("cp-3", "juridica", "GAMMA INMOBILIARIA S.A.S", "nit", "900003"),
         "registro": _reg("900003", "GAMMA INMOBILIARIA S.A.S", 20_000_000_000, 25_000_000_000, "MARIA LINARES"),
         "operacion": {"operacionId": "op-3", "monto": 900_000_000, "patronNormal": 100_000_000,
                       "senales": [], "senalesPTEE": ("pagoFuncionarioPublico",),
                       "esFuncionarioPublico": True, "canalDenuncias": False}},
    ]
    lista = [RegistroNormalizado(id="onu-1", nombre="JUAN GOMEZ", fuente="onu")]
    r = monitorear_cartera(items, registros_lista=lista,
                           catalogo_senales=("pagoPorTercero", "pagoFraccionado"),
                           catalogo_ptee=("usoIntermediario", "pagoFuncionarioPublico", "pagoNoDocumentado"),
                           now=NOW, hmac_key="k", engine="python")
    print("=== MONITOREO DE CARTERA SAGRILAFT+PTEE ===")
    print(f"Entidades: {r.total} · Coincidencias: {r.con_coincidencia} · DD vencida: {r.dd_vencidas} · "
          f"Perfil alto: {r.perfil_alto} · Señales: {r.con_senales} · Inusuales: {r.inusuales} · "
          f"BF en listas: {r.bf_coincidencias} · PTEE alto: {r.ptee_alto}")
    print("\n-- Tablero (indicadores) --")
    for t in r.tablero:
        print(f"  {t['indicador']}: {t['valor']}")
    print("\n-- Alertas --")
    for a in r.alertas:
        print(f"  [{a['contraparteId']}] {a['alerta']}")


if __name__ == "__main__":
    main()

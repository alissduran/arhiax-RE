"""Demo del reporte a la UIAF (ROS/AROS) — estructura SIREL-compatible y validable."""
import datetime
import io
import os
import sys

from arhia_sag_screen.contracts import Contraparte, RegistroNormalizado
from arhia_sag_screen.pipeline import ejecutar_pipeline
from arhia_sag_screen.reporte_uiaf import generar_reporte_uiaf, serializar_json, serializar_xml, validar

NOW = datetime.datetime(2026, 9, 7, 12, 0, 0, tzinfo=datetime.timezone.utc)
ENTIDAD = {"nit": "901234567", "nombre": "ARHIAX REAL ESTATE S.A.S"}


def _cp():
    return Contraparte("cp-1", "juridica", "PARQUE INDUSTRIAL CLAVERIA S.A.S", "nit", "900253457")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    # Caso 1: operación sospechosa (coincidencia en listas) -> ROS
    lista = [RegistroNormalizado(id="onu-1", nombre="PARQUE INDUSTRIAL CLAVERIA S.A.S",
                                 tipo_documento="nit", numero_documento="900253457", fuente="onu")]
    res_ros = ejecutar_pipeline(_cp(), {"monto": 400_000_000, "patronNormal": 100_000_000,
                                        "senales": ["pagoFraccionado"], "operacionId": "op-r"},
                                registros_lista=lista, now=NOW, engine="python")
    rep_ros = generar_reporte_uiaf(_cp(), {"monto": 400_000_000, "patronNormal": 100_000_000,
                                           "senales": ["pagoFraccionado"], "operacionId": "op-r"},
                                   res_ros, entidad_nit=ENTIDAD["nit"], entidad_nombre=ENTIDAD["nombre"], now=NOW)
    print("=== ROS (Operación Sospechosa) — validar:", validar(rep_ros) or "OK", "===")
    print("Sujeto:", rep_ros.operaciones[0].nombre, "| cuantía", rep_ros.operaciones[0].cuantia,
          "| señales", list(rep_ros.operaciones[0].senales))
    print(serializar_json(rep_ros))

    # Caso 2: sin operaciones sospechosas -> AROS del trimestre
    res_aros = ejecutar_pipeline(_cp(), {"monto": 40_000_000, "patronNormal": 100_000_000,
                                         "senales": [], "operacionId": "op-a"},
                                 now=NOW, engine="python")
    rep_aros = generar_reporte_uiaf(_cp(), {"monto": 40_000_000, "patronNormal": 100_000_000,
                                            "senales": [], "operacionId": "op-a"},
                                    res_aros, entidad_nit=ENTIDAD["nit"], entidad_nombre=ENTIDAD["nombre"],
                                    trimestre="2026-T3", inicio="2026-07-01", fin="2026-09-30", now=NOW)
    print("\n=== AROS (Ausencia) — validar:", validar(rep_aros) or "OK", "===")
    print(serializar_xml(rep_aros))

    out = os.path.join(os.path.dirname(__file__), "data", "reporte_uiaf_ros.xml")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with io.open(out, "w", encoding="utf-8") as f:
        f.write(serializar_xml(rep_ros))
    print("\nXML ROS escrito:", os.path.abspath(out))


if __name__ == "__main__":
    main()

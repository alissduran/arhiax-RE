"""Demo del Expediente de Confianza (folio 040-347004) con integridad SAGRILAFT."""
import io
import os
import sys

from arhia_expediente.expediente import FichaIntegridad, construir, generar_markdown
from arhia_title.contracts import Anotacion
from arhia_title.extract import extraer_caso

ANOTACIONES = (
    Anotacion(1, "compraventa", "2001-03-21", titular="VICTOR DIAZ CLAVERIA CIA. S. EN C."),
    Anotacion(2, "hipoteca", "2009-03-03", estado="cancelada", detalle="Hipoteca BANCOLOMBIA"),
    Anotacion(4, "compraventa", "2014-11-05", titular="PARQUE INDUSTRIAL CLAVERIA S.A.S"),
    Anotacion(6, "cancelacion", "2017-08-09", detalle="Cancelación hipoteca"),
)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    path = os.path.join(os.path.dirname(__file__), "..", "arhia_title", "data", "dictamen_040_347004.txt")
    with open(path, encoding="utf-8") as f:
        texto = f.read()
    caso = extraer_caso(texto, "040-347004", ANOTACIONES)
    integridad = FichaIntegridad(screening="pendiente", beneficiario_final="PARQUE INDUSTRIAL CLAVERIA S.A.S", regimen="pleno", sarlaft="pendiente")
    exp = construir(caso, integridad)
    print(generar_markdown(exp))


if __name__ == "__main__":
    main()

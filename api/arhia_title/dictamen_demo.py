"""Pipeline documento→hechos→hallazgos con el dictamen real 040-347004."""
import os

from .contracts import Anotacion
from .extract import extraer_caso
from .report import generar_informe
from .report_html import escribir
from .rules import ejecutar

ANOTACIONES_REALES = (
    Anotacion(1, "compraventa", "2001-03-21", "Esc 2001", titular="VICTOR DIAZ CLAVERIA CIA. S. EN C."),
    Anotacion(2, "hipoteca", "2009-03-03", "Esc 2009", detalle="Hipoteca BANCOLOMBIA", estado="cancelada"),
    Anotacion(3, "aclaracion", "2010-01-21", "Aclaración"),
    Anotacion(4, "compraventa", "2014-11-05", "Esc 2014", titular="PARQUE INDUSTRIAL CLAVERIA S.A.S"),
    Anotacion(5, "aclaracion", "2014-11-05", "Aclaración"),
    Anotacion(6, "cancelacion", "2017-08-09", "Cancelación hipoteca BANCOLOMBIA"),
    Anotacion(7, "otro", "2022-06-09", "N/D"),
)


def main():
    path = os.path.join(os.path.dirname(__file__), "data", "dictamen_040_347004.txt")
    with open(path, encoding="utf-8") as f:
        texto = f.read()
    caso = extraer_caso(texto, "040-347004", ANOTACIONES_REALES)
    hallazgos = ejecutar(caso)
    print(generar_informe(caso, hallazgos))
    out = os.path.join(os.path.dirname(__file__), "data", "informe_040_347004.html")
    escribir(caso, hallazgos, out)
    print("\nHTML generado:", os.path.abspath(out))


if __name__ == "__main__":
    main()

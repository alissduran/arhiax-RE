"""Caso demo: compraventa urbano residencial Barranquilla (folio 040-347004)."""
from .contracts import Anotacion, Avaluo, Caso, Pago, Parte, Predio
from .report import generar_informe
from .rules import ejecutar


def caso_demo():
    return Caso(
        id="DEMO-040-347004",
        tipo="compraventa",
        predio=Predio(
            folio_matricula="040-347004",
            codigo_catastral="08001-01-01-0001-0001-001",
            direccion="Barranquilla, Carrera 3 # 49-16",
            area_registral=80.0,
            area_catastral=85.0,
        ),
        partes=(
            Parte("vendedor", "JUNIARYS ROCA NAVARRO", "cc", "1143143392"),
            Parte("comprador", "CARLOS RODRIGUEZ", "cc", "1045678901"),
        ),
        anotaciones=(
            Anotacion(1, "compraventa", "2010-05-10", "Esc 1287 Notaría 3", titular="JUNIARYS ROCA NAVARRO"),
            Anotacion(2, "hipoteca", "2015-03-15", "Esc 2015-0451", detalle="Hipoteca abierta sin cuantía"),
            Anotacion(3, "embargo", "2022-07-01", "Oficio Juzgado 5 Civil", detalle="Embargo por proceso ejecutivo"),
        ),
        avaluo=Avaluo(valor=450_000_000, metodo="mercado", fecha="2026-08-15", avaluador="Avaluador Lonja BAQ"),
        precio_pactado=520_000_000,
        pagos=(
            Pago(200_000_000, "transferencia", "CARLOS RODRIGUEZ"),
            Pago(320_000_000, "efectivo", "INVERSIONES XYZ S.A.S", es_tercero=True),
        ),
    )


def main():
    caso = caso_demo()
    hallazgos = ejecutar(caso)
    print(generar_informe(caso, hallazgos))


if __name__ == "__main__":
    main()

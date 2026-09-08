# arhia_title — Motor determinista de pre-dictamen jurídico-inmobiliario

Espejo en Python de los bundles OPA/Rego (TIT/CAT/VAL/TRX) del pre-dictamen.
No sustituye al abogado: produce hallazgos trazables (hecho → evidencia → regla),
separando resultado automático de conclusión profesional.

## Ejecutar el demo
```
py -m arhia_title.demo
```

## Tests
```
py -m unittest arhia_title.tests.test_rules -v
```

## Reglas
- TIT_B01 identidad/consistencia · TIT_B02 cronología · TIT_B03 titularidad
- TIT_B04 gravámenes · TIT_B05 cancelaciones · VAL_B01 precio/avalúo · TRX_B01 pagos/terceros

# -*- coding: utf-8 -*-
"""Lista las rutas de la API y marca cuáles NO exigen autenticación y tocan la BD.

Se usa para saber si existe una sonda pública que revele el estado de la base
(migraciones) sin credenciales. No modifica nada.
"""
import ast
import ast as _ast
import pathlib

SRC = pathlib.Path(__file__).resolve().parent.parent / "api" / "index.py"
arbol = ast.parse(SRC.read_text(encoding="utf-8"))

rutas = []
for nodo in ast.walk(arbol):
    if not isinstance(nodo, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
        continue
    decoradores = []
    for d in nodo.decorator_list:
        if isinstance(d, _ast.Call) and isinstance(d.func, _ast.Attribute):
            metodo = d.func.attr
            ruta = d.args[0].value if d.args and isinstance(d.args[0], _ast.Constant) else ""
            if metodo in ("get", "post", "put", "delete", "api_route"):
                decoradores.append((metodo, ruta))
    if not decoradores:
        continue
    firma = ast.unparse(nodo.args)
    con_auth = "require_auth" in firma or "require_admin" in firma
    cuerpo = ast.unparse(nodo)
    toca_db = "get_db_connection" in cuerpo
    for metodo, ruta in decoradores:
        rutas.append({"metodo": metodo.upper(), "ruta": ruta, "auth": con_auth,
                      "toca_db": toca_db, "nombre": nodo.name})

print(f"rutas totales: {len(rutas)}")
publicas = [r for r in rutas if not r["auth"]]
print(f"rutas SIN autenticación: {len(publicas)}")
for r in publicas:
    marca = "  <-- TOCA LA BASE" if r["toca_db"] else ""
    print(f"   {r['metodo']:6} {r['ruta']:55} {r['nombre']}{marca}")
print()
print("¿existe una sonda pública que revele el estado de la BD?",
      any(r["toca_db"] for r in publicas))

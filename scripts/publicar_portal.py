# -*- coding: utf-8 -*-
"""Publica la experiencia del portal DICTUS en la carpeta servida por la app.

`public/` es lo que FastAPI monta en la raíz (`app.mount("/", StaticFiles(...))`),
así que un archivo ahí es, literalmente, la experiencia que ve el usuario. La fuente
de verdad vive en `ui/portal/` (y los tokens en `ui/prototipo/tokens.css`); este
script genera la copia desplegable en `public/portal/`:

    ui/portal/index.html   →  public/portal/index.html
    ui/portal/portal.js    →  public/portal/portal.js
    ui/portal/portal.css   →  public/portal/portal.css   (import reescrito a tokens.css)
    ui/prototipo/tokens.css→  public/portal/tokens.css   (copia literal)

Así el sistema de diseño sigue teniendo UN solo origen y lo desplegado sigue siendo
comprobable: `tests/test_portal_dictus_ui.py` regenera y compara byte a byte.

Uso:
    python scripts/publicar_portal.py            # escribe la copia desplegable
    python scripts/publicar_portal.py --check     # solo verifica (código 1 si difiere)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ORIGEN = ROOT / "ui" / "portal"
TOKENS = ROOT / "ui" / "prototipo" / "tokens.css"
DESTINO = ROOT / "public" / "portal"

CABECERA_CSS = ("/* GENERADO por scripts/publicar_portal.py desde "
                "ui/portal/portal.css — NO editar a mano. */\n")


def _css_desplegable() -> str:
    """El CSS del portal con el import de tokens apuntando a la copia local."""
    css = (ORIGEN / "portal.css").read_text(encoding="utf-8")
    css = css.replace('@import url("../prototipo/tokens.css");',
                      '@import url("tokens.css");')
    return CABECERA_CSS + css


def artefactos() -> dict[Path, str]:
    """Ruta destino -> contenido exacto que debe tener."""
    return {
        DESTINO / "index.html": (ORIGEN / "index.html").read_text(encoding="utf-8"),
        DESTINO / "portal.js": (ORIGEN / "portal.js").read_text(encoding="utf-8"),
        DESTINO / "portal.css": _css_desplegable(),
        DESTINO / "tokens.css": TOKENS.read_text(encoding="utf-8"),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Publica el portal DICTUS en public/")
    ap.add_argument("--check", action="store_true",
                    help="no escribe: falla si la copia desplegable no coincide")
    args = ap.parse_args(argv)

    desincronizados = []
    for destino, contenido in artefactos().items():
        actual = destino.read_text(encoding="utf-8") if destino.exists() else None
        if actual == contenido:
            print(f"[OK]   {destino.relative_to(ROOT)}")
            continue
        desincronizados.append(destino)
        if args.check:
            print(f"[DESYNC] {destino.relative_to(ROOT)}"
                  + ("" if actual is not None else " (no existe)"))
        else:
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(contenido, encoding="utf-8")
            print(f"[GEN]  {destino.relative_to(ROOT)}")

    if args.check and desincronizados:
        print(f"\n[FAIL] {len(desincronizados)} archivo(s) desincronizados: "
              "ejecute `python scripts/publicar_portal.py`")
        return 1
    print(f"\n[OK] portal publicado en public/portal/ "
          f"({len(artefactos())} archivo(s)) — se sirve en /portal/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

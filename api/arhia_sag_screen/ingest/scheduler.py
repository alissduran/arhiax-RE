"""Programador de ingesta (stub). En producción: cron o APScheduler invocan run_once."""
from .pipeline import ingerir
from .registry import LIST_CATALOG


def run_once(fetch, on_change=None):
    """Descarga y versiona todas las fuentes del catálogo; reporta cambios."""
    resultados = {}
    for key, entry in LIST_CATALOG.items():
        r = ingerir(entry, fetch)
        resultados[key] = r
        if on_change is not None and r.hubo_cambio:
            on_change(r.lista)
    return resultados

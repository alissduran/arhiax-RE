"""Descarga de fuentes oficiales (HTTP)."""
import urllib.request


def fetch_http(url, timeout=60):
    """Descarga cruda por HTTP(S). En producción añadir reintentos y backoff."""
    req = urllib.request.Request(url, headers={"User-Agent": "arhia-sag/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()

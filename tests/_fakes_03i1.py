# -*- coding: utf-8 -*-
"""Fakes de red para las regresiones 03I.1 (sin tocar el producto ni la red).

Sustituyen `catastro_predio._query_capa` / `_get_json` por respuestas
deterministas, de modo que el resolver de estrato por MANZANA pueda probarse
sin salir a internet y sin depender del servicio real de la Alcaldía.
"""
from __future__ import annotations

import contextlib


class _FakeResp:
    def __init__(self, code, payload):
        self.status_code = code
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


@contextlib.contextmanager
def patch_catastro(*, caido=False, numero_predial=None, manzana=None, estrato=None,
                   barrio=None, localidad=None, corroborada=True):
    """Parchea las consultas de `catastro_predio` con respuestas controladas.

    Args:
        caido: el servicio no responde (disponible=False).
        manzana / estrato / barrio / localidad: lo que devuelve la capa de
            estratificación para el prefijo del número predial.
        corroborada: si la capa catastral de manzanas confirma el código.
    """
    import catastro_predio as cp

    def _query_capa(base, capa, where, out_fields="*", max_features=5,
                    return_geometry=False, timeout=None):
        if caido:
            return {"disponible": False, "features": [], "error": "servicio sin respuesta"}
        if "estratificacion" in base:
            if not manzana:
                return {"disponible": True, "features": [], "total": 0, "error": None}
            return {"disponible": True, "features": [{"properties": {
                "codigo_manzana": manzana, "estratificacion": estrato,
                "nombre_barrio": barrio, "localidad": localidad,
                "identificador": "119"}}], "total": 1, "error": None}
        if "datosabiertos" in base and capa == cp.CAPA_MANZANA:
            feats = [{"properties": {"codigo": manzana}}] if (manzana and corroborada) else []
            return {"disponible": True, "features": feats, "total": len(feats), "error": None}
        return {"disponible": False, "features": [], "error": "no fakeado"}

    _orig = cp._query_capa
    cp._query_capa = _query_capa
    try:
        yield
    finally:
        cp._query_capa = _orig

# -*- coding: utf-8 -*-
"""
ARHIAX RE — Configuración por ciudad (Sprint 3, I-3: expansión multi-ciudad)

Carga api/config/ciudades.yaml con los geoportales institucionales verificados
por ciudad (Barranquilla activa; Bogotá/Medellín/Cali en evaluación) y los
servicios nacionales (IGAC, IDEAM, ICDE, SNR...).
"""

from __future__ import annotations

from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parent

_cache = None


def get_config() -> dict:
    """Carga (una vez) ciudades.yaml. Devuelve el dict completo."""
    global _cache
    if _cache is None:
        path = CONFIG_DIR / "ciudades.yaml"
        with open(path, "r", encoding="utf-8") as f:
            _cache = yaml.safe_load(f) or {}
    return _cache


def get_ciudad(nombre: str = "barranquilla") -> dict:
    """Devuelve la config de una ciudad (dict vacío si no existe)."""
    cfg = get_config()
    return cfg.get("ciudades", {}).get(nombre, {})


def listar_ciudades() -> dict:
    """Devuelve {nombre: estado} de todas las ciudades configuradas."""
    cfg = get_config()
    return {k: v.get("estado", "SIN ESTADO") for k, v in cfg.get("ciudades", {}).items()}


def get_nacionales() -> dict:
    """Devuelve la config de servicios nacionales (IGAC, IDEAM, ICDE, SNR...)."""
    cfg = get_config()
    return cfg.get("nacionales", {})

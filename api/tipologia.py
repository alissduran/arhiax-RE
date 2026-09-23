# -*- coding: utf-8 -*-
"""Tipología del predio — ADAPTER de compatibilidad (03I.2A §17).

La lógica de clasificación vive en `clasificacion.clasificar_inmueble`, que separa
las TRES dimensiones (régimen jurídico, uso económico y tipología física). Esta
función se mantiene porque el render y los módulos existentes consumen **un texto**,
y ese texto se deriva de la clasificación: nunca de mezclar uso con régimen.

Historia del defecto (03I.2 · D-2): el destino económico catastral («Habitacional»,
«Comercial», «Oficina») se escribía como si fuera la tipología, borrando la evidencia
registral de propiedad horizontal. Ahora el régimen manda sobre su propia dimensión y
un uso **nunca** decide el régimen.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from clasificacion import clasificar_inmueble, texto_tipologia

# Textos de compatibilidad (mismos valores que el render ya usa).
TIPOLOGIA_SIN_CONSULTA = "PENDIENTE DE VERIFICACION (Requiere consulta catastral)"
TIPOLOGIA_BODEGA = "Bodega -- Uso Industrial"
TIPOLOGIA_PH_CATASTRAL = "Apartamento -- Propiedad Horizontal (condición catastral)"
TIPOLOGIA_PH_CTL = "Apartamento -- Propiedad Horizontal (inferido del CTL)"
TIPOLOGIA_PH_DEMO = "Apartamento -- Propiedad Horizontal (NO VIS)"


def tipologia_de_predio(*, destino_economico: Optional[str],
                        descripcion_ctl: Optional[str] = None,
                        condicion_juridica: Optional[str] = None,
                        condicion_source: Optional[str] = None,
                        fuentes_tematicas=(),
                        predio_resuelto: bool = False,
                        es_caso_demo: bool = False,
                        tiene_ctl: bool = True,
                        descripcion_catastral: Optional[str] = None,
                        tipologia_fisica_fuente: Optional[str] = None,
                        tipologia_source: Optional[str] = None) -> str:
    """Devuelve el TEXTO de tipología del dictamen (adapter de compatibilidad)."""
    clas = clasificar_inmueble(
        condicion_juridica=condicion_juridica,
        condicion_source=condicion_source,
        destino_economico=destino_economico,
        descripcion_registral=descripcion_ctl,
        descripcion_catastral=descripcion_catastral,
        tipologia_fisica_fuente=tipologia_fisica_fuente,
        tipologia_source=tipologia_source,
    )
    texto = texto_tipologia(clas)
    # Caso de demostración explícito (sin CTL): no se confunde con una resolución real.
    if (es_caso_demo and not tiene_ctl
            and clas["physical_typology"].get("value") is None
            and clas["juridical_regime"].get("value") is None):
        return TIPOLOGIA_PH_DEMO
    return texto


def clasificacion_de_predio(**kwargs) -> Dict[str, Any]:
    """Acceso directo a la clasificación completa (tres dimensiones + conflictos)."""
    return clasificar_inmueble(**kwargs)

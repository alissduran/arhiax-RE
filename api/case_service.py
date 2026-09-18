# -*- coding: utf-8 -*-
"""
ARHIAX RE — CaseService (operaciones de aplicación del Case).

Fuente de verdad del Case: Postgres/Neon (o SQLite local en dev/test). Este
servicio NO toca localStorage ni decide presentación; solo valida, normaliza y
persiste a través de `CaseRepository`.

`created_by` / `updated_by` son metadatos de auditoría (NO ownership); no se usan
para ocultar ni restringir casos (ver ADR-002).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from case_repository import CaseRepository

_repo = CaseRepository()

_CIUDADES = ("barranquilla", "medellin", "bogota", "pasto")
_ESTADO_INICIAL = "PENDIENTE_IMAGENES"


def _normalizar_ciudad(ciudad) -> str:
    c = (ciudad or "barranquilla").lower().strip()
    return c if c in _CIUDADES else "barranquilla"


class ValidationError(ValueError):
    """Error de validación del Case (se traduce a HTTP 400 en la capa HTTP)."""


def create_case(*, folio_matricula: str, direccion: str, barrio: str = "",
                estrato: int = 4, area: float = 0.0, ciudad: str = "barranquilla",
                acreedor_real: Optional[str] = None,
                created_by: Optional[str] = None) -> Dict[str, Any]:
    """Crea y persiste un Case. Valida que exista folio o dirección."""
    folio = (folio_matricula or "").strip()
    direccion = (direccion or "").strip()
    if not folio and not direccion:
        raise ValidationError(
            "Debe ingresar la matrícula inmobiliaria o la dirección del predio.")

    folio = folio or "Pendiente"
    direccion = direccion or "Pendiente"
    ciudad = _normalizar_ciudad(ciudad)

    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_id = _repo.insert(
        folio_matricula=folio, direccion=direccion, barrio=barrio or "",
        estrato=int(estrato or 4), area=float(area or 0.0),
        estado=_ESTADO_INICIAL, valor_consolidado=0, fecha_creacion=fecha,
        ciudad=ciudad, created_by=created_by,
    )
    if acreedor_real:
        _repo.update(new_id, {"acreedor_real": acreedor_real})
    caso = _repo.get(new_id)
    return caso if caso is not None else {"id": new_id}


def get_case(case_id: int) -> Optional[Dict[str, Any]]:
    return _repo.get(case_id)


def list_cases() -> List[Dict[str, Any]]:
    return _repo.list()


def update_case(case_id: int, fields: Dict[str, Any],
                updated_by: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Actualiza campos permitidos del Case y registra updated_by."""
    if "ciudad" in fields:
        fields["ciudad"] = _normalizar_ciudad(fields["ciudad"])
    if updated_by is not None:
        fields["updated_by"] = updated_by
    return _repo.update(case_id, fields)


def delete_case(case_id: int) -> bool:
    return _repo.delete(case_id)

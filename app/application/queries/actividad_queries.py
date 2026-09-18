"""Queries para el contexto de Actividades - Sistema BICU.

Representan solicitudes de lectura pura. No modifican estado ni conocen SQL.
"""

from datetime import date
from typing import Optional, Union
from pydantic import BaseModel, Field


class ConsultarActividadesPorPeriodoQuery(BaseModel):
    """Consulta de actividades desarrolladas en un rango temporal con filtro opcional de sede."""

    fecha_inicio: Union[date, str] = Field(..., description="Fecha inicial del período.")
    fecha_fin: Union[date, str] = Field(..., description="Fecha final del período.")
    sede: Optional[str] = Field(default=None, description="Filtro opcional por sede o recinto.")

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }


class ObtenerDetalleActividadQuery(BaseModel):
    """Consulta de una actividad específica por su identificador único (UUID)."""

    id_actividad: str = Field(..., description="UUID de la actividad a consultar.")

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }

"""Queries para el contexto de Participación y Asistencias - Sistema BICU.

Representan solicitudes de consulta sobre asistencias y cola de revisión humana.
"""

from typing import Optional
from pydantic import BaseModel, Field


class ConsultarParticipantesPorActividadQuery(BaseModel):
    """Consulta de la lista completa de participantes vinculados a una actividad."""

    id_actividad: str = Field(..., description="UUID de la actividad institucional.")

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }


class ConsultarParticipantesEnRevisionQuery(BaseModel):
    """Consulta de participantes con bandera de revisión humana activada."""

    id_actividad: Optional[str] = Field(
        default=None,
        description="Filtro opcional por actividad específica."
    )

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }

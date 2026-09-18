"""Queries para el contexto de Evidencias y Custodia Digital - Sistema BICU.

Representan solicitudes de lectura de activos digitales y galería institucional.
"""

from pydantic import BaseModel, Field


class ConsultarEvidenciasActividadQuery(BaseModel):
    """Consulta de la colección ordenada de evidencias asociadas a una actividad."""

    id_actividad: str = Field(..., description="UUID de la actividad institucional.")

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }

"""Queries para el contexto de Calidad, Auditoría y Discrepancias - Sistema BICU.

Representan solicitudes de lectura pericial de discrepancias no resueltas.
"""

from typing import Optional
from pydantic import BaseModel, Field


class ConsultarDiscrepanciasPendientesQuery(BaseModel):
    """Consulta de discrepancias activas pendientes de resolución o aclaración humana."""

    severidad: Optional[str] = Field(
        default=None,
        description="Filtro opcional por severidad ('INFO', 'WARNING', 'ERROR')."
    )

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }

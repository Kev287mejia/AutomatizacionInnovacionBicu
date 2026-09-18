"""Queries para el contexto de Informes Semanales Consolidados - Sistema BICU.

Representan solicitudes de lectura de consolidados periódicos de recinto.
"""

from pydantic import BaseModel, Field


class ConsultarInformeSemanalPorPeriodoQuery(BaseModel):
    """Consulta de informe semanal consolidado por período y recinto exactos."""

    anio: int = Field(..., ge=2020, le=2050, description="Año calendario.")
    mes: int = Field(..., ge=1, le=12, description="Mes del año (1..12).")
    numero_semana: int = Field(..., ge=1, le=5, description="Semana operativa (1..5).")
    sede: str = Field(..., description="Sede o recinto emisor.")

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }

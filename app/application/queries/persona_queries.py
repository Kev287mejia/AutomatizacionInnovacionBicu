"""Queries para el contexto de Personas e Identidades - Sistema BICU.

Representan solicitudes de búsqueda o recuperación bio-demográfica.
"""

from pydantic import BaseModel, Field


class BuscarPersonasPorNombreQuery(BaseModel):
    """Consulta difusa o coincidente de personas por nombre."""

    nombre_query: str = Field(..., min_length=1, description="Cadena textual a buscar en nombres.")
    limite: int = Field(default=10, ge=1, le=100, description="Cantidad máxima de coincidencias.")

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }


class ObtenerPersonaPorIdQuery(BaseModel):
    """Consulta de una persona por su identificador UUID interno."""

    id_persona_interno: str = Field(..., description="UUID interno de la persona en el SSOT.")

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }

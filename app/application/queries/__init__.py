"""Subpaquete de Queries (Consultas de Lectura) de la capa de Aplicación - Sistema BICU."""

from app.application.queries.actividad_queries import (
    ConsultarActividadesPorPeriodoQuery,
    ObtenerDetalleActividadQuery,
)
from app.application.queries.persona_queries import (
    BuscarPersonasPorNombreQuery,
    ObtenerPersonaPorIdQuery,
)
from app.application.queries.participacion_queries import (
    ConsultarParticipantesPorActividadQuery,
    ConsultarParticipantesEnRevisionQuery,
)
from app.application.queries.evidencia_queries import (
    ConsultarEvidenciasActividadQuery,
)
from app.application.queries.informe_queries import (
    ConsultarInformeSemanalPorPeriodoQuery,
)
from app.application.queries.discrepancia_queries import (
    ConsultarDiscrepanciasPendientesQuery,
)

__all__ = [
    # Actividades
    "ConsultarActividadesPorPeriodoQuery",
    "ObtenerDetalleActividadQuery",
    # Personas
    "BuscarPersonasPorNombreQuery",
    "ObtenerPersonaPorIdQuery",
    # Participación
    "ConsultarParticipantesPorActividadQuery",
    "ConsultarParticipantesEnRevisionQuery",
    # Evidencias
    "ConsultarEvidenciasActividadQuery",
    # Informes
    "ConsultarInformeSemanalPorPeriodoQuery",
    # Discrepancias
    "ConsultarDiscrepanciasPendientesQuery",
]

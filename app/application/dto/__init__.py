"""Subpaquete de Data Transfer Objects (DTOs) de la capa de Aplicación - Sistema BICU."""

from app.application.dto.input_dtos import (
    FilaParticipanteIngestaDTO,
    PartidaPresupuestariaDTO,
    DetalleActividadInformeDTO,
)
from app.application.dto.output_dtos import (
    IngestaListaAsistenciaResultDTO,
    ActividadResumenDTO,
    ActividadDetalleDTO,
    PersonaResumenDTO,
    PersonaDetalleDTO,
    ParticipacionDetalleDTO,
    EvidenciaVinculadaDTO,
    DiscrepanciaDetalleDTO,
    InformeSemanalCompletoDTO,
    PlanificacionAsignadaDTO,
    DisenoMetodologicoAsignadoDTO,
    InformeActividadRegistradoDTO,
)

__all__ = [
    "FilaParticipanteIngestaDTO",
    "PartidaPresupuestariaDTO",
    "DetalleActividadInformeDTO",
    "IngestaListaAsistenciaResultDTO",
    "ActividadResumenDTO",
    "ActividadDetalleDTO",
    "PersonaResumenDTO",
    "PersonaDetalleDTO",
    "ParticipacionDetalleDTO",
    "EvidenciaVinculadaDTO",
    "DiscrepanciaDetalleDTO",
    "InformeSemanalCompletoDTO",
    "PlanificacionAsignadaDTO",
    "DisenoMetodologicoAsignadoDTO",
    "InformeActividadRegistradoDTO",
]


"""Subpaquete de Fakes en Memoria e InMemoryUnitOfWork para la capa Application - Sistema BICU."""

from app.application.fakes.in_memory_actividad_repo import InMemoryActividadRepository
from app.application.fakes.in_memory_persona_repo import InMemoryPersonaRepository
from app.application.fakes.in_memory_participacion_repo import InMemoryParticipacionRepository
from app.application.fakes.in_memory_evidencia_repo import InMemoryEvidenciaRepository
from app.application.fakes.in_memory_informe_semanal_repo import InMemoryInformeSemanalRepository
from app.application.fakes.in_memory_discrepancia_repo import InMemoryDiscrepanciaRepository
from app.application.fakes.in_memory_uow import InMemoryUnitOfWork

__all__ = [
    "InMemoryActividadRepository",
    "InMemoryPersonaRepository",
    "InMemoryParticipacionRepository",
    "InMemoryEvidenciaRepository",
    "InMemoryInformeSemanalRepository",
    "InMemoryDiscrepanciaRepository",
    "InMemoryUnitOfWork",
]

"""Subpaquete de Commands (Intenciones de Mutación) de la capa de Aplicación - Sistema BICU."""

from app.application.commands.actividad_commands import (
    RegistrarActividadCommand,
    AsignarPlanificacionCommand,
    AsignarDisenoMetodologicoCommand,
    RegistrarInformeActividadCommand,
)
from app.application.commands.persona_commands import (
    RegistrarPersonaCommand,
)
from app.application.commands.participacion_commands import (
    RegistrarParticipacionIndividualCommand,
    IngestarListaAsistenciaCommand,
)
from app.application.commands.evidencia_commands import (
    RegistrarEvidenciaDigitalCommand,
    VincularEvidenciaActividadCommand,
    DesvincularEvidenciaActividadCommand,
)
from app.application.commands.informe_commands import (
    CrearInformeSemanalCommand,
    AsociarActividadesInformeSemanalCommand,
)
from app.application.commands.discrepancia_commands import (
    RegistrarDiscrepanciaCommand,
    ResolverRevisionDiscrepanciaCommand,
)

__all__ = [
    # Actividades
    "RegistrarActividadCommand",
    "AsignarPlanificacionCommand",
    "AsignarDisenoMetodologicoCommand",
    "RegistrarInformeActividadCommand",
    # Personas
    "RegistrarPersonaCommand",
    # Participación
    "RegistrarParticipacionIndividualCommand",
    "IngestarListaAsistenciaCommand",
    # Evidencias
    "RegistrarEvidenciaDigitalCommand",
    "VincularEvidenciaActividadCommand",
    "DesvincularEvidenciaActividadCommand",
    # Informes
    "CrearInformeSemanalCommand",
    "AsociarActividadesInformeSemanalCommand",
    # Discrepancias
    "RegistrarDiscrepanciaCommand",
    "ResolverRevisionDiscrepanciaCommand",
]

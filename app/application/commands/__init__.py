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
from app.application.commands.calidad_commands import (
    EvaluarCalidadActividadCommand,
)
from app.application.commands.pipeline_commands import (
    EjecutarPipelineActividadCommand,
    ExportarMatricesActividadCommand,
    ExportarMatricesPeriodoCommand,
)
from app.application.commands.batch_commands import (
    IngestarCarpetaWordCommand,
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
    # Calidad
    "EvaluarCalidadActividadCommand",
    # Pipeline y Exportación
    "EjecutarPipelineActividadCommand",
    "ExportarMatricesActividadCommand",
    "ExportarMatricesPeriodoCommand",
    # Batch
    "IngestarCarpetaWordCommand",
]

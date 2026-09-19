"""Subpaquete de Casos de Uso (Use Cases) de la capa Application - Sistema BICU.

Implementa la orquestación de operaciones de mutación (Commands) y consulta (Queries)
respetando Clean Architecture, la inversión de dependencias y la separación de capas.
"""

from app.application.use_cases.actividad import (
    RegistrarActividadUseCase,
    AsignarPlanificacionUseCase,
    AsignarDisenoMetodologicoUseCase,
    RegistrarInformeActividadUseCase,
)
from app.application.use_cases.persona import (
    RegistrarPersonaUseCase,
)
from app.application.use_cases.participacion import (
    RegistrarParticipacionIndividualUseCase,
    IngestarListaAsistenciaUseCase,
    EnrutarParticipacionesActividadUseCase,
)
from app.application.use_cases.calidad import (
    EvaluarCalidadActividadUseCase,
    ConsultarDiscrepanciasPendientesUseCase,
    ResolverRevisionDiscrepanciaUseCase,
)

from app.application.use_cases.pipeline import (
    ProcesarPipelineActividadUseCase,
)
from app.application.use_cases.exportacion import (
    ExportarMatricesActividadUseCase,
    ExportarMatricesPeriodoUseCase,
)
from app.application.use_cases.word import (
    ActividadNoEncontradaError,
    GenerarInformeActividadWordUseCase,
    GenerarInformeSemanalWordUseCase,
    GenerarDossierConsolidadoWordUseCase,
)

from app.application.use_cases.ingestar_actividad_desde_word import (
    IngestarActividadDesdeWordUseCase,
)
from app.application.use_cases.batch import (
    ProcesarPipelineDesdeWordUseCase,
    IngestarCarpetaWordUseCase,
)

__all__ = [
    "RegistrarActividadUseCase",
    "AsignarPlanificacionUseCase",
    "AsignarDisenoMetodologicoUseCase",
    "RegistrarInformeActividadUseCase",
    "RegistrarPersonaUseCase",
    "RegistrarParticipacionIndividualUseCase",
    "IngestarListaAsistenciaUseCase",
    "EnrutarParticipacionesActividadUseCase",
    "EvaluarCalidadActividadUseCase",
    "ConsultarDiscrepanciasPendientesUseCase",
    "ResolverRevisionDiscrepanciaUseCase",
    "ProcesarPipelineActividadUseCase",
    "ExportarMatricesActividadUseCase",
    "ExportarMatricesPeriodoUseCase",
    "ActividadNoEncontradaError",
    "GenerarInformeActividadWordUseCase",
    "GenerarInformeSemanalWordUseCase",
    "GenerarDossierConsolidadoWordUseCase",
    "IngestarActividadDesdeWordUseCase",
    "ProcesarPipelineDesdeWordUseCase",
    "IngestarCarpetaWordUseCase",
]

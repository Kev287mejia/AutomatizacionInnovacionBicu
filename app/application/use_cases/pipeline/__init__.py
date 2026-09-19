"""app.application.use_cases.pipeline

Casos de uso para la orquestación integral del pipeline institucional.
"""

from app.application.use_cases.pipeline.procesar_pipeline_actividad import (
    ProcesarPipelineActividadUseCase,
)

__all__ = ["ProcesarPipelineActividadUseCase"]

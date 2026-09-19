"""app.application.use_cases.batch

Casos de uso para el procesamiento por lote (batch) de documentos Word institucionales.
"""

from app.application.use_cases.batch.procesar_pipeline_desde_word import (
    ProcesarPipelineDesdeWordUseCase,
)
from app.application.use_cases.batch.ingestar_carpeta_word import (
    IngestarCarpetaWordUseCase,
)

__all__ = [
    "ProcesarPipelineDesdeWordUseCase",
    "IngestarCarpetaWordUseCase",
]

"""
app.word_consolidator.ui.services

Módulo de servicios de aplicación y traducción de errores de la interfaz institucional.
"""

from app.word_consolidator.ui.services.error_translator import (
    ErrorInstitucionalInfo,
    ErrorTranslator,
    NOMBRES_OFICIALES_MATRICES,
)
from app.word_consolidator.ui.services.application_service import (
    ConsolidationAppService,
    MatrixValidationItem,
    PreflightStatus,
    MESES_ESPANOL,
)

__all__ = [
    "ErrorInstitucionalInfo",
    "ErrorTranslator",
    "NOMBRES_OFICIALES_MATRICES",
    "ConsolidationAppService",
    "MatrixValidationItem",
    "PreflightStatus",
    "MESES_ESPANOL",
]

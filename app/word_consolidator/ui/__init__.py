"""
app.word_consolidator.ui

Módulo de Interfaz Gráfica Institucional BICU (Fase 14.9).
Proporciona la aplicación de escritorio y la capa de operación para el personal administrativo y académico.
"""

from app.word_consolidator.ui.app import ConsolidatorApp, main
from app.word_consolidator.ui.services.application_service import ConsolidationAppService
from app.word_consolidator.ui.services.error_translator import ErrorTranslator
from app.word_consolidator.ui.workers.consolidation_worker import ConsolidationWorker

__all__ = [
    "ConsolidatorApp",
    "ConsolidationAppService",
    "ConsolidationWorker",
    "ErrorTranslator",
    "main",
]

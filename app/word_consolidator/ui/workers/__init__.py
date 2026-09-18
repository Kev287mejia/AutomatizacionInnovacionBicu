"""
app.word_consolidator.ui.workers

Módulo de trabajadores asíncronos para ejecución del pipeline sin bloqueo de interfaz.
"""

from app.word_consolidator.ui.workers.consolidation_worker import (
    ConsolidationEvent,
    ConsolidationEventType,
    ConsolidationWorker,
    ETAPAS_PIPELINE,
)

__all__ = [
    "ConsolidationEvent",
    "ConsolidationEventType",
    "ConsolidationWorker",
    "ETAPAS_PIPELINE",
]

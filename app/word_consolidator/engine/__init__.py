"""
app.word_consolidator.engine

Módulo del motor de consolidación institucional de BICU (Fase 14.4).
Exporta ConsolidationEngine y sus modelos de dominio asociados.
"""

from app.word_consolidator.engine.consolidation_engine import (
    ActividadConsolidada,
    ConsolidationEngine,
    ParticipacionConsolidada,
    ResultadoConsolidacion,
    TotalesM1,
    TotalesNominales,
)
from app.word_consolidator.engine.discrepancy_detector import DiscrepancyDetector

__all__ = [
    "ActividadConsolidada",
    "ConsolidationEngine",
    "DiscrepancyDetector",
    "ParticipacionConsolidada",
    "ResultadoConsolidacion",
    "TotalesM1",
    "TotalesNominales",
]

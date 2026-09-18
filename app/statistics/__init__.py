"""
app.statistics

Módulo de cálculo de estadísticas institucionales y agregaciones (Fase 7).
Transforma el modelo interno SSOT y el ResultadoRouting en métricas oficiales y
prepara la estructura de datos para la Matriz 1: Consolidado de Actividades.
"""

from app.statistics.models import (
    DesgloseSexo,
    DesgloseCategoria,
    EstadisticaActividad,
    EstadisticaCalidad,
    DistribucionEdades,
    EstadisticaGlobal,
)
from app.statistics.statistics_engine import StatisticsEngine
from app.statistics.reporter import StatisticsReporter

__all__ = [
    "DesgloseSexo",
    "DesgloseCategoria",
    "EstadisticaActividad",
    "EstadisticaCalidad",
    "DistribucionEdades",
    "EstadisticaGlobal",
    "StatisticsEngine",
    "StatisticsReporter",
]

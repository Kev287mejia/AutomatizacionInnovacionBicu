"""app.reporting

Capa de Reporting y Dashboard Institucional BICU.
Fase 29.20.1 — Implementación Controlada del Núcleo Reporting Service.

PRINCIPIOS ARQUITECTÓNICOS:
  - Solo Lectura: No modifica fuentes, ni SQLite, ni V001-V004.
  - Inversión de Dependencias y Desacoplamiento Limpio.
  - Consumo exclusivo de app/indicators/ (Fuente Única de Verdad Analítica).
  - Cero duplicación de fórmulas matemáticas.
  - Cero código de UI / widgets / gráficos en esta capa.
"""

from app.reporting.domain.enums import (
    AlertStatus,
    ExportFormat,
    MultisessionGoalMode,
    ReportType,
)
from app.reporting.domain.dto import (
    ChartDatasetDTO,
    DashboardCardDTO,
    DashboardDataDTO,
    DashboardSectionDTO,
    ReportDocumentDTO,
    ReportFilterDTO,
    ReportMetricItemDTO,
    ReportSectionDTO,
)
from app.reporting.infrastructure.memory_cache import ReportingMemoryCache
from app.reporting.application.reporting_service import ReportingService

__all__ = [
    "AlertStatus",
    "ExportFormat",
    "MultisessionGoalMode",
    "ReportType",
    "ChartDatasetDTO",
    "DashboardCardDTO",
    "DashboardDataDTO",
    "DashboardSectionDTO",
    "ReportDocumentDTO",
    "ReportFilterDTO",
    "ReportMetricItemDTO",
    "ReportSectionDTO",
    "ReportingMemoryCache",
    "ReportingService",
]

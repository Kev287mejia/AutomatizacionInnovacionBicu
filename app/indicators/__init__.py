"""Módulo app.indicators — Capa Analítica de Indicadores Institucionales BICU.

Fase 29.19.1–29.19.2 — Auditoría e Implementación Controlada de Indicadores.

PRINCIPIOS:
  - Solo Lectura. No modifica datos, ni corrige, ni completa NULL.
  - Determinista y auditable.
  - Independiente de UI, IA y pipeline de Word.
  - Respeta PLANIFICADO ≠ EJECUTADO y esquemas V001–V004.
"""

from app.indicators.domain.contracts import (
    IndicatorCategory,
    IndicatorDefinition,
    IndicatorId,
    IndicatorQuery,
    IndicatorReport,
    IndicatorResult,
)
from app.indicators.domain.catalog import IndicatorCatalog, INDICATOR_CATALOG
from app.indicators.domain.ports import IndicatorReaderPort
from app.indicators.infrastructure.sqlite_reader import SQLiteIndicatorReader
from app.indicators.application.service import IndicatorCalculationService

__all__ = [
    "IndicatorCategory",
    "IndicatorDefinition",
    "IndicatorId",
    "IndicatorQuery",
    "IndicatorReport",
    "IndicatorResult",
    "IndicatorCatalog",
    "INDICATOR_CATALOG",
    "IndicatorReaderPort",
    "SQLiteIndicatorReader",
    "IndicatorCalculationService",
]

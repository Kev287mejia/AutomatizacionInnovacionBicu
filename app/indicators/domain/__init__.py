"""Paquete app.indicators.domain — Núcleo de dominio de indicadores institucionales."""

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
]

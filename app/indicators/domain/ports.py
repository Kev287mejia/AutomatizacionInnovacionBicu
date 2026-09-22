"""Puertos del Dominio de Indicadores Institucionales BICU.

Fase 29.19.1–29.19.2 — Auditoría e Implementación Controlada de Indicadores.

Define el contrato de solo lectura para el acceso a las fuentes certificadas.
PROHIBICIÓN ESTRICTA: Cero métodos de inserción, actualización, eliminación o mutación.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from app.indicators.domain.contracts import IndicatorQuery


class IndicatorReaderPort(ABC):
    """Puerto de lectura analítica sobre el patrimonio de datos institucional (V001–V004)."""

    @abstractmethod
    def get_planning_activities(self, query: IndicatorQuery) -> List[Dict[str, Any]]:
        """Recupera actividades planificadas en el período/dimensiones especificadas."""
        pass

    @abstractmethod
    def get_executed_activities(self, query: IndicatorQuery) -> List[Dict[str, Any]]:
        """Recupera actividades efectivamente ejecutadas ('EJECUTADA', 'REPORTADA', 'CERRADA')."""
        pass

    @abstractmethod
    def get_execution_links(self, query: IndicatorQuery) -> List[Dict[str, Any]]:
        """Recupera vínculos de trazabilidad entre planificación y ejecución (V004)."""
        pass

    @abstractmethod
    def get_participations(self, query: IndicatorQuery) -> List[Dict[str, Any]]:
        """Recupera participaciones efectivas del período (excluyendo M5 histórico)."""
        pass

    @abstractmethod
    def get_unique_persons(self, query: IndicatorQuery) -> List[Dict[str, Any]]:
        """Recupera el conjunto de personas participantes únicas en el período."""
        pass

    @abstractmethod
    def get_discrepancies(self, query: IndicatorQuery) -> List[Dict[str, Any]]:
        """Recupera registros de discrepancias M1 vs M2–M5 para el período."""
        pass

    @abstractmethod
    def get_methodological_designs(self, query: IndicatorQuery) -> List[Dict[str, Any]]:
        """Recupera diseños metodológicos asociados a actividades planificadas."""
        pass

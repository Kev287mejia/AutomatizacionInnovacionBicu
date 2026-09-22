"""app.review.application.ports

Puertos e interfaces abstractas para la persistencia e integración de la Cola de Revisión.
Define los contratos requeridos por la capa de aplicación.
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from app.review.application.dto import (
    CandidateMatchDTO,
    ReviewCaseDetailDTO,
    ReviewCaseSummaryDTO,
    ReviewHistoryItemDTO,
    ReviewResolutionResultDTO,
)
from app.review.domain.models import ReviewDecision


class IReviewQueueRepository(ABC):
    """Contrato del repositorio para la gestión pericial de la Cola de Revisión."""

    @abstractmethod
    def list_pending_cases(
        self, id_actividad: Optional[str] = None
    ) -> List[ReviewCaseSummaryDTO]:
        """Lista todas las participaciones en COLA_REVISION excluyendo históricos M5."""
        pass

    @abstractmethod
    def get_case_detail(self, id_participacion: str) -> Optional[ReviewCaseDetailDTO]:
        """Obtiene el detalle completo de un caso en revisión."""
        pass

    @abstractmethod
    def search_candidates(
        self, nombre: str, excluir_id_persona: str, limite: int = 5
    ) -> List[CandidateMatchDTO]:
        """Busca candidatos potenciales por nombre para asistencia al operador."""
        pass

    @abstractmethod
    def execute_atomic_resolution(
        self,
        id_participacion: str,
        decision: ReviewDecision,
    ) -> ReviewResolutionResultDTO:
        """Ejecuta atómicamente la resolución y asienta auditoría DISCREPANCY_RESOLVE."""
        pass

    @abstractmethod
    def list_history(self, limite: int = 50) -> List[ReviewHistoryItemDTO]:
        """Recupera los eventos de resolución de discrepancias asentados en auditoria_evento."""
        pass

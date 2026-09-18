"""Puerto abstracto del patrón Unit of Work (Frontera Transaccional).

Define el contrato IUnitOfWork que permite a los casos de uso coordinar
operaciones atómicas entre múltiples repositorios sin acoplamiento a SQLite.
"""

from abc import ABC, abstractmethod
from typing import Optional, Type
from types import TracebackType

from app.core.ports.actividad_repository import IActividadRepository
from app.core.ports.persona_repository import IPersonaRepository
from app.core.ports.participacion_repository import IParticipacionRepository
from app.core.ports.evidencia_repository import IEvidenciaRepository
from app.core.ports.informe_semanal_repository import IInformeSemanalRepository
from app.core.ports.discrepancia_repository import IDiscrepanciaRepository


class IUnitOfWork(ABC):
    """Contrato abstracto para el patrón Unit of Work en la capa de Aplicación.

    Garantiza que múltiples operaciones sobre distintos repositorios se ejecuten
    dentro de un único límite transaccional atómico (All-or-Nothing).
    """

    actividades: IActividadRepository
    personas: IPersonaRepository
    participaciones: IParticipacionRepository
    evidencias: IEvidenciaRepository
    informes_semanales: IInformeSemanalRepository
    discrepancias: IDiscrepanciaRepository

    @abstractmethod
    def __enter__(self) -> "IUnitOfWork":
        """Inicia el ámbito transaccional coordinado.

        Returns:
            La propia instancia del Unit of Work activa.
        """
        ...

    @abstractmethod
    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """Finaliza el ámbito transaccional.

        Si ocurrió una excepción no controlada (`exc_type is not None`),
        debe asegurar la reversión automática (`rollback`) de los cambios pendientes.
        """
        ...

    @abstractmethod
    def commit(self) -> None:
        """Confirma atómicamente la totalidad de operaciones ejecutadas en la transacción."""
        ...

    @abstractmethod
    def rollback(self) -> None:
        """Revierte la totalidad de operaciones ejecutadas en la transacción."""
        ...

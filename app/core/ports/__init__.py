"""app.core.ports

Puertos e interfaces abstractas de persistencia y transaccionalidad (Clean Architecture).
Completamente desacoplados de SQLite, SQL o cualquier tecnología de infraestructura.
"""

from app.core.ports.actividad_repository import IActividadRepository
from app.core.ports.persona_repository import IPersonaRepository
from app.core.ports.participacion_repository import IParticipacionRepository
from app.core.ports.evidencia_repository import IEvidenciaRepository
from app.core.ports.informe_semanal_repository import IInformeSemanalRepository
from app.core.ports.discrepancia_repository import IDiscrepanciaRepository
from app.core.ports.unit_of_work import IUnitOfWork

from app.core.exceptions.persistence_exceptions import (
    PersistenceError,
    EntityNotFoundError,
    EntityAlreadyExistsError,
    ReferentialIntegrityError,
    TransactionError,
)

__all__ = [
    "IActividadRepository",
    "IPersonaRepository",
    "IParticipacionRepository",
    "IEvidenciaRepository",
    "IInformeSemanalRepository",
    "IDiscrepanciaRepository",
    "IUnitOfWork",
    "PersistenceError",
    "EntityNotFoundError",
    "EntityAlreadyExistsError",
    "ReferentialIntegrityError",
    "TransactionError",
]

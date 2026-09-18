"""app.infrastructure.persistence.repositories

Adaptadores concretos de repositorios y Unit of Work sobre SQLite.
Implementan los contratos abstractos de la capa `app.core.ports`.
"""

from app.infrastructure.persistence.repositories.actividad_repository import (
    SQLiteActividadRepository,
)
from app.infrastructure.persistence.repositories.persona_repository import (
    SQLitePersonaRepository,
)
from app.infrastructure.persistence.repositories.participacion_repository import (
    SQLiteParticipacionRepository,
)
from app.infrastructure.persistence.repositories.evidencia_repository import (
    SQLiteEvidenciaRepository,
)
from app.infrastructure.persistence.repositories.informe_semanal_repository import (
    SQLiteInformeSemanalRepository,
)
from app.infrastructure.persistence.repositories.discrepancia_repository import (
    SQLiteDiscrepanciaRepository,
)
from app.infrastructure.persistence.repositories.unit_of_work import (
    SQLiteUnitOfWork,
)

__all__ = [
    "SQLiteActividadRepository",
    "SQLitePersonaRepository",
    "SQLiteParticipacionRepository",
    "SQLiteEvidenciaRepository",
    "SQLiteInformeSemanalRepository",
    "SQLiteDiscrepanciaRepository",
    "SQLiteUnitOfWork",
]

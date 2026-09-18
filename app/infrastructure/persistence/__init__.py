"""Submódulo de Persistencia - Capa de Infraestructura BICU.

Exporta los componentes fundamentales de configuración, conexión, esquema,
migraciones y transacciones.
"""

from app.infrastructure.persistence.config import (
    DatabaseConfig,
    DatabaseSecurityError,
    get_default_database_directory,
    get_default_database_path,
    is_onedrive_path,
)
from app.infrastructure.persistence.connection import (
    SQLiteConnectionManager,
    transaction,
)
from app.infrastructure.persistence.schema import (
    EXPECTED_TABLE_NAMES,
    SCHEMA_VERSION_TABLE_DDL,
    INITIAL_SCHEMA_DDL_STATEMENTS,
    INITIAL_INDEXES_DDL_STATEMENTS,
)
from app.infrastructure.persistence.migrations import (
    Migration,
    MigrationRunner,
    MIGRATION_REGISTRY,
    MIGRATION_V001,
)
from app.infrastructure.persistence.repositories import (
    SQLiteActividadRepository,
    SQLitePersonaRepository,
    SQLiteParticipacionRepository,
    SQLiteEvidenciaRepository,
    SQLiteInformeSemanalRepository,
    SQLiteDiscrepanciaRepository,
    SQLiteUnitOfWork,
)

__all__ = [
    "DatabaseConfig",
    "DatabaseSecurityError",
    "get_default_database_directory",
    "get_default_database_path",
    "is_onedrive_path",
    "SQLiteConnectionManager",
    "transaction",
    "EXPECTED_TABLE_NAMES",
    "SCHEMA_VERSION_TABLE_DDL",
    "INITIAL_SCHEMA_DDL_STATEMENTS",
    "INITIAL_INDEXES_DDL_STATEMENTS",
    "Migration",
    "MigrationRunner",
    "MIGRATION_REGISTRY",
    "MIGRATION_V001",
    "SQLiteActividadRepository",
    "SQLitePersonaRepository",
    "SQLiteParticipacionRepository",
    "SQLiteEvidenciaRepository",
    "SQLiteInformeSemanalRepository",
    "SQLiteDiscrepanciaRepository",
    "SQLiteUnitOfWork",
]

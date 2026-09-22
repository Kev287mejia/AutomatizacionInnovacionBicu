"""Capa de Persistencia Satélite para el Módulo de Planificación y Diseño Metodológico.

Fase 29.4.2 — Implementación de Persistencia SQLite V003.
Fase 29.18.1 — Trazabilidad Planificación ↔ Ejecución (V004, PlanningExecutionLink).
Exporta el esquema V003/V004, los repositorios concretos y la unidad de trabajo satélite.
"""

from app.planning.infrastructure.persistence.mappers import (
    AIProposalMapper,
    FAQTableMapper,
    MethodologicalDesignMapper,
    OperationalActivityMapper,
    PlannedActivityMapper,
    PlanningExecutionLinkMapper,
    TimeBlockMapper,
)
from app.planning.infrastructure.persistence.repositories import (
    SQLiteCatalogRepository,
    SQLiteMethodologicalDesignRepository,
    SQLitePlannedActivityRepository,
    SQLitePlanningExecutionLinkRepository,
)
from app.planning.infrastructure.persistence.schema_v003 import (
    EXPECTED_PLANNING_TABLE_NAMES,
    V003_INDEXES_DDL_STATEMENTS,
    V003_SCHEMA_DDL_STATEMENTS,
)
from app.planning.infrastructure.persistence.schema_v004 import (
    EXPECTED_V004_TABLE_NAMES,
    V004_INDEXES_DDL_STATEMENTS,
    V004_SCHEMA_DDL_STATEMENTS,
)
from app.planning.infrastructure.persistence.unit_of_work import (
    PlanningUnitOfWork,
)

__all__ = [
    # V003
    "V003_SCHEMA_DDL_STATEMENTS",
    "V003_INDEXES_DDL_STATEMENTS",
    "EXPECTED_PLANNING_TABLE_NAMES",
    # V004
    "V004_SCHEMA_DDL_STATEMENTS",
    "V004_INDEXES_DDL_STATEMENTS",
    "EXPECTED_V004_TABLE_NAMES",
    # Mappers
    "PlannedActivityMapper",
    "MethodologicalDesignMapper",
    "FAQTableMapper",
    "TimeBlockMapper",
    "OperationalActivityMapper",
    "AIProposalMapper",
    "PlanningExecutionLinkMapper",
    # Repositories
    "SQLitePlannedActivityRepository",
    "SQLiteMethodologicalDesignRepository",
    "SQLiteCatalogRepository",
    "SQLitePlanningExecutionLinkRepository",
    # Unit of Work
    "PlanningUnitOfWork",
]

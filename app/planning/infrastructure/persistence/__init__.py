"""Capa de Persistencia Satélite para el Módulo de Planificación y Diseño Metodológico.

Fase 29.4.2 — Implementación de Persistencia SQLite V003.
Exporta el esquema V003, los repositorios concretos y la unidad de trabajo satélite.
"""

from app.planning.infrastructure.persistence.mappers import (
    AIProposalMapper,
    FAQTableMapper,
    MethodologicalDesignMapper,
    OperationalActivityMapper,
    PlannedActivityMapper,
    TimeBlockMapper,
)
from app.planning.infrastructure.persistence.repositories import (
    SQLiteCatalogRepository,
    SQLiteMethodologicalDesignRepository,
    SQLitePlannedActivityRepository,
)
from app.planning.infrastructure.persistence.schema_v003 import (
    EXPECTED_PLANNING_TABLE_NAMES,
    V003_INDEXES_DDL_STATEMENTS,
    V003_SCHEMA_DDL_STATEMENTS,
)
from app.planning.infrastructure.persistence.unit_of_work import (
    PlanningUnitOfWork,
)

__all__ = [
    "V003_SCHEMA_DDL_STATEMENTS",
    "V003_INDEXES_DDL_STATEMENTS",
    "EXPECTED_PLANNING_TABLE_NAMES",
    "PlannedActivityMapper",
    "MethodologicalDesignMapper",
    "FAQTableMapper",
    "TimeBlockMapper",
    "OperationalActivityMapper",
    "AIProposalMapper",
    "SQLitePlannedActivityRepository",
    "SQLiteMethodologicalDesignRepository",
    "SQLiteCatalogRepository",
    "PlanningUnitOfWork",
]

# app/planning/domain/__init__.py
# Capa de Dominio Puro — Modulo Planificacion -> Diseno Metodologico
# Fase 29.3 — Sin dependencias de infraestructura, persistencia, UI ni nucleo word_consolidator.
from app.planning.domain.catalogs import (
    CATALOG_C1_EJES,
    CATALOG_C2_PROGRAMAS,
    CATALOG_C3_AMBITOS,
    CATALOG_C4_TIPOS_EVENTO,
    CATALOG_C5_TIPOS_PROYECTO,
)
from app.planning.domain.dtos import (
    FAQTableDTO,
    MethodologicalDesignDTO,
    OperationalActivityDTO,
    PlannedActivityDTO,
    TimeBlockDTO,
)
from app.planning.domain.entities import (
    MethodologicalDesign,
    PlannedActivity,
)
from app.planning.domain.ports import (
    AIAssistancePort,
    CatalogRepositoryPort,
    MethodologicalDesignRepositoryPort,
    MethodologicalDocumentRendererPort,
    PlannedActivityRepositoryPort,
)
from app.planning.domain.rules_engine import InstitutionalRulesEngine
from app.planning.domain.validator import (
    MethodologicalDesignValidator,
    ValidationIssue,
    ValidationReport,
    ValidationSeverity,
)
from app.planning.domain.value_objects import (
    AIProposal,
    CatalogReference,
    DesignStatus,
    FAQTable,
    OperationalActivity,
    ParticipantGoals,
    TimeBlock,
)

__all__ = [
    # Catalogs
    "CATALOG_C1_EJES",
    "CATALOG_C2_PROGRAMAS",
    "CATALOG_C3_AMBITOS",
    "CATALOG_C4_TIPOS_EVENTO",
    "CATALOG_C5_TIPOS_PROYECTO",
    # Value Objects
    "DesignStatus",
    "CatalogReference",
    "ParticipantGoals",
    "TimeBlock",
    "OperationalActivity",
    "FAQTable",
    "AIProposal",
    # Entities
    "PlannedActivity",
    "MethodologicalDesign",
    # Rules & Validation
    "InstitutionalRulesEngine",
    "ValidationSeverity",
    "ValidationIssue",
    "ValidationReport",
    "MethodologicalDesignValidator",
    # DTOs
    "PlannedActivityDTO",
    "TimeBlockDTO",
    "OperationalActivityDTO",
    "FAQTableDTO",
    "MethodologicalDesignDTO",
    # Ports
    "PlannedActivityRepositoryPort",
    "MethodologicalDesignRepositoryPort",
    "CatalogRepositoryPort",
    "AIAssistancePort",
    "MethodologicalDocumentRendererPort",
]

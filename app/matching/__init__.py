"""
app.matching

Módulo de coincidencia y unificación de entidades (Actividades y Personas).
"""

from app.matching.activity_matcher import ActivityMatcher, ActivityMatchResult
from app.matching.person_matcher import (
    PersonMatcher,
    PersonComparisonResult,
    TipoCoincidenciaPersona
)
from app.matching.identity_resolver import (
    IdentityResolver,
    IdentityResolutionResult,
    FusionRecord,
    CandidatePair
)

__all__ = [
    "ActivityMatcher",
    "ActivityMatchResult",
    "PersonMatcher",
    "PersonComparisonResult",
    "TipoCoincidenciaPersona",
    "IdentityResolver",
    "IdentityResolutionResult",
    "FusionRecord",
    "CandidatePair",
]

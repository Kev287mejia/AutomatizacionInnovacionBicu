"""
app.core.models

Módulos de modelos de datos principales (SSOT):
- Activity: Evento o actividad institucional.
- Person: Persona o protagonista participante.
- Participation: Vínculo entre persona y actividad (base de routing).
- ValidationResult: Registro de validaciones y hallazgos.
"""

from app.core.models.activity import Activity
from app.core.models.person import Person
from app.core.models.participation import Participation
from app.core.models.validation_result import ValidationResult
from app.core.models.evidence import Evidencia, TipoEvidencia, ActividadEvidenciaVinculo
from app.core.models.weekly_report import InformeSemanal, DetalleInformeSemanal
from app.core.models.discrepancy import (
    Discrepancia,
    TipoDiscrepancia,
    SeveridadDiscrepancia,
    EstadoDiscrepancia,
)

# Alias canónicos en español para interoperabilidad institucional
Actividad = Activity
Persona = Person
Participacion = Participation

__all__ = [
    "Activity",
    "Actividad",
    "Person",
    "Persona",
    "Participation",
    "Participacion",
    "ValidationResult",
    "Evidencia",
    "TipoEvidencia",
    "ActividadEvidenciaVinculo",
    "InformeSemanal",
    "DetalleInformeSemanal",
    "Discrepancia",
    "TipoDiscrepancia",
    "SeveridadDiscrepancia",
    "EstadoDiscrepancia",
]

"""app.quality

Módulo de Calidad, Validación y Gestión de Discrepancias Institucionales BICU.
Gobernado bajo el principio inviolable DETECTAR ≠ CORREGIR (Regla RN-C07).
"""

from app.quality.models import (
    EstadoGeneralCalidad,
    IValidationRule,
    QualityAssessment,
    QualityContext,
    SeveridadCalidad,
    ValidationFinding,
)
from app.quality.validator import QualityValidator
from app.quality.rules import (
    ReglaQ01CedulaVacia,
    ReglaQ02CedulaFormatoDudoso,
    ReglaQ03FechaEnCedula,
    ReglaQ04NombreVacio,
    ReglaQ05SexoIncompatible,
    ReglaQ06SexoAusente,
    ReglaQ07EdadAusente,
    ReglaQ08EdadAtipicaEstamento,
    ReglaQ09CarreraAbreviadaAmbigua,
    ReglaQ10CarreraNoHomologada,
    ReglaQ11EtniaNoCatalogada,
    ReglaQ12CategoriaDesconocida,
    ReglaQ13ParticipacionRepetida,
    ReglaQ14PrevalenciaBeneficiario,
    ReglaQ15IntegridadReferencialHuerfana,
    ReglaQ16TituloDiscordanteWordVsAsistencia,
    ReglaQ17FechaDiscordanteWordVsAsistencia,
    ReglaQ18MetaPlanificadaVsAsistenciasReales,
    ReglaQ19ConteoNarrativoVsFilasNominales,
    ReglaQ20PosibleDuplicadoPersona,
)

__all__ = [
    "EstadoGeneralCalidad",
    "IValidationRule",
    "QualityAssessment",
    "QualityContext",
    "QualityValidator",
    "SeveridadCalidad",
    "ValidationFinding",
    "ReglaQ01CedulaVacia",
    "ReglaQ02CedulaFormatoDudoso",
    "ReglaQ03FechaEnCedula",
    "ReglaQ04NombreVacio",
    "ReglaQ05SexoIncompatible",
    "ReglaQ06SexoAusente",
    "ReglaQ07EdadAusente",
    "ReglaQ08EdadAtipicaEstamento",
    "ReglaQ09CarreraAbreviadaAmbigua",
    "ReglaQ10CarreraNoHomologada",
    "ReglaQ11EtniaNoCatalogada",
    "ReglaQ12CategoriaDesconocida",
    "ReglaQ13ParticipacionRepetida",
    "ReglaQ14PrevalenciaBeneficiario",
    "ReglaQ15IntegridadReferencialHuerfana",
    "ReglaQ16TituloDiscordanteWordVsAsistencia",
    "ReglaQ17FechaDiscordanteWordVsAsistencia",
    "ReglaQ18MetaPlanificadaVsAsistenciasReales",
    "ReglaQ19ConteoNarrativoVsFilasNominales",
    "ReglaQ20PosibleDuplicadoPersona",
]

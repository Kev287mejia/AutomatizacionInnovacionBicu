"""app.application.use_cases.word

Casos de uso de generación de documentos Word institucionales.

Fase 26.8 — Bloque 2: Integración SQLite → Application → WordACL → Renderer → DOCX.
"""

from app.application.use_cases.word.generar_informe_actividad_word import (
    ActividadNoEncontradaError,
    GenerarInformeActividadWordUseCase,
)
from app.application.use_cases.word.generar_informe_semanal_word import (
    GenerarInformeSemanalWordUseCase,
)
from app.application.use_cases.word.generar_dossier_consolidado_word import (
    GenerarDossierConsolidadoWordUseCase,
)

__all__ = [
    "ActividadNoEncontradaError",
    "GenerarInformeActividadWordUseCase",
    "GenerarInformeSemanalWordUseCase",
    "GenerarDossierConsolidadoWordUseCase",
]

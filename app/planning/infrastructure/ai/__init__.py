"""
app.planning.infrastructure.ai — Adaptadores de Asistencia de IA para Planificación.

Fase 29.14 / 29.17 — Implementación Controlada de Asistencia IA.
Aísla completamente los adaptadores de IA respecto a la persistencia SQLite y al núcleo protegido.
"""
from app.planning.infrastructure.ai.factory import get_ai_assistance_adapter
from app.planning.infrastructure.ai.gemini_adapter import GeminiAIAssistanceAdapter
from app.planning.infrastructure.ai.mock_adapter import LocalMockAIAssistanceAdapter

__all__ = [
    "GeminiAIAssistanceAdapter",
    "LocalMockAIAssistanceAdapter",
    "get_ai_assistance_adapter",
]

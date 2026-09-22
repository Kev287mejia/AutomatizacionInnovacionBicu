"""
app.planning.infrastructure.ai.factory — Fábrica de Selección Explícita de Proveedor de IA.

Fase 29.17 — Integración Controlada de Gemini API Free Tier.
Garantiza la selección determinística y auditable del proveedor de IA:
- AI_PROVIDER=mock   -> LocalMockAIAssistanceAdapter
- AI_PROVIDER=gemini -> GeminiAIAssistanceAdapter (con fallback a mock si no hay API key o hay fallo)
- Por defecto (sin variable) -> LocalMockAIAssistanceAdapter (offline-first)
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from app.planning.domain.ports import AIAssistancePort
from app.planning.infrastructure.ai.gemini_adapter import GeminiAIAssistanceAdapter
from app.planning.infrastructure.ai.mock_adapter import LocalMockAIAssistanceAdapter

logger = logging.getLogger("bicu.planning.ai.factory")


def get_ai_assistance_adapter(provider: Optional[str] = None) -> AIAssistancePort:
    """Obtiene una instancia de AIAssistancePort basada en la selección explícita de proveedor.

    Comportamiento determinista:
      - provider == 'mock': Retorna LocalMockAIAssistanceAdapter (100% offline).
      - provider == 'gemini':
          - Si GEMINI_API_KEY existe y no está vacía: retorna GeminiAIAssistanceAdapter.
          - Si GEMINI_API_KEY está ausente o vacía: registra fallback y retorna LocalMockAIAssistanceAdapter.
      - Cualquier otro valor o ausencia de configuración: retorna LocalMockAIAssistanceAdapter.

    Args:
        provider: Identificador explícito ('mock' o 'gemini'). Si es None, se lee de AI_PROVIDER.

    Returns:
        Instancia válida de AIAssistancePort.
    """
    selected_provider = (
        provider or os.environ.get("AI_PROVIDER", "mock")
    ).strip().lower()

    if selected_provider == "gemini":
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key:
            logger.warning(
                "get_ai_assistance_adapter: AI_PROVIDER='gemini' fue solicitado, pero "
                "GEMINI_API_KEY está ausente o vacía. Conmutando de forma segura a LocalMockAIAssistanceAdapter."
            )
            return LocalMockAIAssistanceAdapter()

        logger.info(
            "get_ai_assistance_adapter: Instanciando GeminiAIAssistanceAdapter (Google Gemini Free Tier / Dev)."
        )
        return GeminiAIAssistanceAdapter(api_key=api_key)

    elif selected_provider == "mock":
        logger.info(
            "get_ai_assistance_adapter: Instanciando LocalMockAIAssistanceAdapter (Proveedor Offline Determinístico)."
        )
        return LocalMockAIAssistanceAdapter()

    else:
        logger.warning(
            "get_ai_assistance_adapter: Proveedor desconocido '%s'. Utilizando LocalMockAIAssistanceAdapter por defecto.",
            selected_provider,
        )
        return LocalMockAIAssistanceAdapter()

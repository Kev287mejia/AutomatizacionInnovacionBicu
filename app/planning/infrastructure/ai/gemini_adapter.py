"""
app.planning.infrastructure.ai.gemini_adapter — Adaptador de Asistencia IA con Google Gemini API.

Fase 29.17 — Integración Controlada de Gemini API Free Tier.
Diseñado para DESARROLLO, PRUEBAS Y DEMOSTRACIÓN ACADÉMICA INSTITUCIONAL.
NO es el proveedor institucional definitivo de producción.

REGLAS ARQUITECTÓNICAS OBLIGATORIAS:
  - Implementa estrictamente AIAssistancePort.
  - Exclusivamente llamadas HTTPS REST vía biblioteca estándar 'requests'.
  - Timeout estricto de máximo 8.0 segundos.
  - Fallback automático y seguro hacia LocalMockAIAssistanceAdapter ante cualquier error de red o cuota.
  - Registro seguro de auditoría de errores (proveedor, tipo de error, código HTTP) SIN exponer API keys ni datos sensibles.
  - Retorna invariablemente AIProposal con requires_review=True y accepted=None.
  - Cero dependencias hacia app.word_consolidator, matrices M1-M5 o SQLite.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

import requests

from app.planning.domain.ports import AIAssistancePort
from app.planning.domain.value_objects import (
    AI_ALLOWED_TARGET_FIELDS,
    AIProposal,
)
from app.planning.infrastructure.ai.mock_adapter import LocalMockAIAssistanceAdapter

logger = logging.getLogger("bicu.planning.ai.gemini")

# URL base oficial de la API de Google Gemini (v1beta REST)
GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiAIAssistanceAdapter(AIAssistancePort):
    """Adaptador de infraestructura que conecta con Google Gemini API REST (Free Tier / Dev).

    Invariantes:
    - Implementa AIAssistancePort.
    - Cero almacenamiento o exposición de credenciales en logs, excepciones o repr.
    - Conmuta a fallback_adapter ante cualquier error de conectividad, cuota o parseo.
    - Solo recibe datos previamente sanitizados por AIContextBuilder.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout_seconds: float = 8.0,
        fallback_adapter: Optional[AIAssistancePort] = None,
        session: Optional[requests.Session] = None,
    ) -> None:
        """Inicializa el adaptador Gemini.

        Args:
            api_key: Clave de API de Gemini. Si es None, se lee de la variable GEMINI_API_KEY.
            model_name: Nombre del modelo Gemini. Si es None, se lee de GEMINI_MODEL o default 'gemini-2.5-flash'.
            timeout_seconds: Tiempo límite estricto de petición en segundos (máximo 8.0s).
            fallback_adapter: Adaptador de respaldo ante fallos (por defecto LocalMockAIAssistanceAdapter).
            session: Sesión de requests opcional para inyección en pruebas unitarias.
        """
        self._api_key = (api_key or os.environ.get("GEMINI_API_KEY", "")).strip()
        self.model_name = (
            model_name or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        ).strip()
        self.timeout_seconds = min(float(timeout_seconds), 8.0)
        self.fallback_adapter = fallback_adapter or LocalMockAIAssistanceAdapter()
        self._session = session or requests.Session()

    def __repr__(self) -> str:
        # Enmascaramiento total de credenciales en representaciones
        has_key = bool(self._api_key)
        return (
            f"<GeminiAIAssistanceAdapter(model='{self.model_name}', "
            f"has_api_key={has_key}, timeout={self.timeout_seconds}s)>"
        )

    def generate_narrative_proposal(
        self,
        target_field: str,
        source_inputs: dict[str, Any],
    ) -> AIProposal:
        """Genera una propuesta narrativa utilizando Gemini API con fallback controlado.

        Args:
            target_field: Campo destino asistible (validado contra AI_ALLOWED_TARGET_FIELDS).
            source_inputs: Diccionario de entradas sanitizado por AIContextBuilder.

        Returns:
            AIProposal con requires_review=True y accepted=None.

        Raises:
            ValueError: Si target_field no está autorizado por el dominio.
        """
        if target_field not in AI_ALLOWED_TARGET_FIELDS:
            raise ValueError(
                f"target_field '{target_field}' no está permitido para asistencia de IA. "
                f"Campos permitidos: {sorted(AI_ALLOWED_TARGET_FIELDS)}."
            )

        # Si no hay API key configurada, conmutar inmediatamente a fallback
        if not self._api_key:
            self._log_safe_fallback(
                reason="API key ausente o vacía (GEMINI_API_KEY no configurada)",
                status_code=None,
            )
            return self._execute_fallback(target_field, source_inputs)

        # Construcción del prompt institucional controlado
        prompt_text = self._build_institutional_prompt(target_field, source_inputs)

        # Invocación protegida con timeout y captura exhaustiva de errores
        try:
            url = f"{GEMINI_API_BASE_URL}/{self.model_name}:generateContent"
            headers = {
                "Content-Type": "application/json",
                "x-goog-api-key": self._api_key,
            }
            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": prompt_text}],
                    }
                ],
                "generationConfig": {
                    "temperature": 0.2,
                    "responseMimeType": "application/json",
                },
            }

            response = self._session.post(
                url,
                headers=headers,
                json=payload,
                timeout=self.timeout_seconds,
            )

            # Control de códigos HTTP
            if response.status_code != 200:
                self._log_safe_fallback(
                    reason=f"Respuesta HTTP no exitosa del proveedor Gemini",
                    status_code=response.status_code,
                )
                return self._execute_fallback(target_field, source_inputs)

            response_data = response.json()
            content_text = self._extract_content_from_response(response_data)

            if not content_text or not content_text.strip():
                self._log_safe_fallback(
                    reason="Contenido devuelto por Gemini vacío o no textual",
                    status_code=response.status_code,
                )
                return self._execute_fallback(target_field, source_inputs)

            # Parsear salida estructurada JSON esperada: {"proposed_content": "..."}
            parsed_json = json.loads(content_text)
            proposed_content = parsed_json.get("proposed_content", "").strip()

            if not proposed_content:
                self._log_safe_fallback(
                    reason="Estructura JSON devuelta no contiene 'proposed_content' válido",
                    status_code=response.status_code,
                )
                return self._execute_fallback(target_field, source_inputs)

            # Construir y retornar AIProposal legítima
            return AIProposal.create(
                target_field=target_field,
                proposed_content=proposed_content,
                source_inputs=dict(source_inputs),
                confidence=0.90,
            )

        except requests.exceptions.Timeout:
            self._log_safe_fallback(
                reason=f"Timeout de red superado ({self.timeout_seconds}s) en llamada a Gemini",
                status_code=None,
            )
            return self._execute_fallback(target_field, source_inputs)

        except requests.exceptions.ConnectionError:
            self._log_safe_fallback(
                reason="Error de conexión / sin acceso a Internet al contactar Gemini",
                status_code=None,
            )
            return self._execute_fallback(target_field, source_inputs)

        except (requests.exceptions.RequestException, json.JSONDecodeError, KeyError, IndexError) as exc:
            self._log_safe_fallback(
                reason=f"Excepción controlada procesando respuesta de Gemini: {type(exc).__name__}",
                status_code=getattr(getattr(exc, "response", None), "status_code", None),
            )
            return self._execute_fallback(target_field, source_inputs)

        except Exception as exc:
            self._log_safe_fallback(
                reason=f"Excepción inesperada en adaptador Gemini: {type(exc).__name__}",
                status_code=None,
            )
            return self._execute_fallback(target_field, source_inputs)

    def _execute_fallback(
        self,
        target_field: str,
        source_inputs: dict[str, Any],
    ) -> AIProposal:
        """Ejecuta el adaptador de respaldo de forma segura."""
        if self.fallback_adapter is None:
            raise RuntimeError(
                "La asistencia de IA no está disponible y no se configuró un adaptador de respaldo."
            )
        # Delegar en el adaptador local (mock)
        return self.fallback_adapter.generate_narrative_proposal(target_field, source_inputs)

    def _log_safe_fallback(self, reason: str, status_code: Optional[int]) -> None:
        """Registra de manera segura el evento de fallback SIN exponer secretos."""
        status_info = f" [HTTP {status_code}]" if status_code else ""
        logger.warning(
            "GeminiAIAssistanceAdapter: Activando fallback hacia adaptador local. "
            "Proveedor: Google Gemini Free Tier | Causa: %s%s | Fallback: LocalMockAIAssistanceAdapter",
            reason,
            status_info,
        )

    def _build_institutional_prompt(
        self,
        target_field: str,
        source_inputs: dict[str, Any],
    ) -> str:
        """Construye un prompt institucional estricto y determinista."""
        activity_name = source_inputs.get("activity_name", "Actividad Institucional")
        proposito = source_inputs.get("proposito") or "el fortalecimiento de competencias institucionales"
        eje = source_inputs.get("eje_estrategia", "")
        programa = source_inputs.get("programa", "")
        tipo_evento = source_inputs.get("tipo_evento", "")
        step_number = source_inputs.get("step_number")
        phase_label = source_inputs.get("phase_label")

        prompt = (
            "Eres un asistente de redacción pedagógica y metodológica para Bluefields Indian & Caribbean University (BICU).\n"
            "Tu única tarea es generar una propuesta de borrador narrativo para el campo especificado.\n\n"
            "REGLAS OBLIGATORIAS:\n"
            "1. NO inventes datos institucionales, participantes, personas, cédulas, teléfonos, correos ni datos financieros.\n"
            "2. NO modifiques fechas, sedes, municipios, códigos de eje ni cantidades cuantitativas.\n"
            "3. Basa tu propuesta exclusivamente en el contexto pedagógico suministrado.\n"
            "4. La propuesta será revisada y validada por un responsable humano antes de ser incorporada.\n"
            "5. Debes responder ESTRICTAMENTE en formato JSON con la siguiente estructura:\n"
            '   {"proposed_content": "texto de la propuesta"}\n\n'
            f"CONTEXTO DE LA ACTIVIDAD:\n"
            f"- Nombre de la actividad: {activity_name}\n"
            f"- Propósito académico: {proposito}\n"
            f"- Eje estratégico: {eje}\n"
            f"- Programa institucional: {programa}\n"
            f"- Tipo de evento: {tipo_evento}\n"
            f"- Campo destino a redactar: {target_field}\n"
        )

        if step_number is not None:
            prompt += f"- Número de paso operativo: {step_number}\n"
        if phase_label is not None:
            prompt += f"- Fase operativa: {phase_label}\n"

        prompt += "\nGenera únicamente el objeto JSON solicitado con la redacción en español formal universitario."
        return prompt

    def _extract_content_from_response(self, response_data: dict[str, Any]) -> str:
        """Extrae el texto generado desde la estructura de respuesta estándar de Gemini."""
        candidates = response_data.get("candidates", [])
        if not candidates:
            return ""
        first_candidate = candidates[0]
        content = first_candidate.get("content", {})
        parts = content.get("parts", [])
        if not parts:
            return ""
        return parts[0].get("text", "")

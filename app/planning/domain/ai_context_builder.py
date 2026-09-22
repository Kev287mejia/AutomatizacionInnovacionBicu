"""
AIContextBuilder — Constructor de contexto sanitizado para asistencia de IA.

Fase 29.14 — Implementación Controlada del Núcleo de Asistencia IA.
Aplica el principio de DATA MINIMIZATION mediante LISTA BLANCA ESTRICTA (Whitelisting).
Garantiza que NINGÚN dato sensible (PII, personas, cédulas, contactos, metas, finanzas, ejecución)
sea expuesto al puerto de asistencia de IA.
"""
from __future__ import annotations

from typing import Any, Optional

from app.planning.domain.entities import PlannedActivity
from app.planning.domain.value_objects import AI_ALLOWED_TARGET_FIELDS


class AIContextBuilder:
    """Constructor de contexto sanitizado para asistencia de IA mediante lista blanca estricta."""

    # Lista blanca estricta de claves permitidas en el contexto
    WHITELISTED_CONTEXT_KEYS: frozenset[str] = frozenset({
        "activity_name",
        "proposito",
        "eje_estrategia",
        "programa",
        "tipo_evento",
        "target_field",
        "step_number",
        "phase_label",
    })

    @classmethod
    def build_context(
        cls,
        activity: PlannedActivity,
        target_field: str,
        step_number: Optional[int] = None,
        phase_label: Optional[str] = None,
    ) -> dict[str, Any]:
        """Construye un contexto sanitizado a partir de una PlannedActivity y el campo objetivo.

        Args:
            activity: Actividad planificada institucional.
            target_field: Campo destino a asistir (debe pertenecer a AI_ALLOWED_TARGET_FIELDS).
            step_number: Número de paso operacional (requerido si target_field es 'procedure' u 'operative_goal').
            phase_label: Etiqueta de la fase operacional (opcional, ej. 'I. INICIAL').

        Returns:
            Diccionario sanitizado conteniendo ÚNICAMENTE claves autorizadas.

        Raises:
            ValueError: Si target_field no está permitido o si falta step_number para campos operacionales.
        """
        if not target_field or target_field not in AI_ALLOWED_TARGET_FIELDS:
            raise ValueError(
                f"target_field '{target_field}' no está permitido para asistencia de IA. "
                f"Campos permitidos: {sorted(AI_ALLOWED_TARGET_FIELDS)}."
            )

        if target_field in ("procedure", "operative_goal"):
            if step_number is None or not isinstance(step_number, int) or step_number < 1:
                raise ValueError(
                    f"Para asistir '{target_field}' es obligatorio proporcionar un 'step_number' entero >= 1."
                )

        # Extracción segura bajo lista blanca — datos faltantes permanecen None/missing
        context: dict[str, Any] = {
            "activity_name": activity.activity_name.strip() if activity.activity_name else "",
            "proposito": activity.proposito.strip() if (activity.proposito and activity.proposito.strip()) else None,
            "eje_estrategia": activity.eje_estrategia.strip() if activity.eje_estrategia else "",
            "programa": activity.programa.strip() if activity.programa else "",
            "tipo_evento": activity.tipo_evento.strip() if activity.tipo_evento else "",
            "target_field": target_field,
        }

        if step_number is not None:
            context["step_number"] = step_number
        if phase_label is not None and phase_label.strip():
            context["phase_label"] = phase_label.strip()

        # Filtrado final redundante para garantizar contención absoluta
        sanitized = {k: v for k, v in context.items() if k in cls.WHITELISTED_CONTEXT_KEYS}
        return sanitized

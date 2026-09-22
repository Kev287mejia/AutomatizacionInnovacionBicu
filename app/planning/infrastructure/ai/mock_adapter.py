"""
LocalMockAIAssistanceAdapter — Adaptador mock determinístico local para asistencia de IA.

Fase 29.14 — Implementación Controlada del Núcleo de Asistencia IA.
Provee respuestas determinísticas sin requerir conexión a Internet ni APIs externas.
Diseñado para pruebas unitarias, de integración y desarrollo offline.

REGLAS ABSOLUTAS:
  - 100% offline (cero llamadas HTTP, cero dependencias de red, cero APIs externas).
  - Cero dependencias hacia app.word_consolidator o matrices patrimoniales M1-M5.
  - Cero acceso directo a SQLite o repositorios (aislamiento estricto).
  - Retorna siempre instancias válidas de AIProposal con requires_review=True y accepted=None.
"""
from __future__ import annotations

from typing import Any

from app.planning.domain.ports import AIAssistancePort
from app.planning.domain.value_objects import AI_ALLOWED_TARGET_FIELDS, AIProposal


class LocalMockAIAssistanceAdapter(AIAssistancePort):
    """Adaptador mock local determinístico que implementa AIAssistancePort.

    Invariantes:
    - 100% offline (sin llamadas HTTP ni dependencias de red).
    - No conoce ni importa app.word_consolidator ni matrices M1-M5.
    - No escribe directamente en SQLite ni accede a repositorios.
    - Devuelve siempre instancias válidas de AIProposal con requires_review=True.
    """

    def __init__(self, default_confidence: float = 0.85) -> None:
        self.default_confidence = default_confidence

    def generate_narrative_proposal(
        self,
        target_field: str,
        source_inputs: dict[str, Any],
    ) -> AIProposal:
        """Genera una propuesta narrativa determinística según el campo solicitado.

        Args:
            target_field: Campo permitido a asistir.
            source_inputs: Entradas sanitizadas para trazabilidad.

        Returns:
            AIProposal con requires_review=True y accepted=None.

        Raises:
            ValueError: Si target_field no pertenece a AI_ALLOWED_TARGET_FIELDS.
        """
        if target_field not in AI_ALLOWED_TARGET_FIELDS:
            raise ValueError(
                f"target_field '{target_field}' no está permitido para asistencia de IA. "
                f"Campos permitidos: {sorted(AI_ALLOWED_TARGET_FIELDS)}."
            )

        activity_name = source_inputs.get("activity_name", "Actividad")
        proposito = source_inputs.get("proposito") or "el fortalecimiento de competencias institucionales"

        if target_field == "introduction":
            content = (
                f"El presente diseño metodológico orienta el desarrollo de la actividad '{activity_name}'. "
                f"Esta iniciativa académica responde al propósito de promover {proposito}, "
                "fomentando la participación activa y el aprendizaje significativo de los protagonistas."
            )
        elif target_field == "methodological_approach":
            content = (
                f"Para la actividad '{activity_name}', se adopta un enfoque participativo, dialógico "
                "y vivencial centrado en el protagonista, combinando exposición conceptual reflexiva "
                "con ejercicios prácticos aplicados y plenarias de retroalimentación colectiva."
            )
        elif target_field == "objective_1":
            content = (
                f"Desarrollar capacidades teórico-prácticas orientadas a {proposito}, "
                "mediante el análisis reflexivo de los fundamentos metodológicos institucionales."
            )
        elif target_field == "objective_2":
            content = (
                f"Aplicar herramientas e instrumentos operativos en el marco de '{activity_name}', "
                "generando propuestas de acción concretas articuladas a los objetivos institucionales."
            )
        elif target_field == "procedure":
            step_number = source_inputs.get("step_number", 1)
            phase_label = source_inputs.get("phase_label", f"Fase {step_number}")
            content = (
                f"Paso {step_number} ({phase_label}): El facilitador orienta la dinámica pedagógica "
                f"enfocada en '{activity_name}', facilitando la interacción grupal y sistematizando las conclusiones."
            )
        elif target_field == "operative_goal":
            step_number = source_inputs.get("step_number", 1)
            content = (
                f"Lograr que los participantes completen satisfactoriamente las actividades previstas "
                f"en el paso {step_number}, consolidando los resultados de aprendizaje esperados."
            )
        else:
            content = f"Propuesta sugerida para {target_field} en el marco de '{activity_name}'."

        return AIProposal.create(
            target_field=target_field,
            proposed_content=content,
            source_inputs=dict(source_inputs),
            confidence=self.default_confidence,
        )

"""app.review.domain.exceptions

Excepciones del dominio de Cola de Revisión.
Garantizan el cumplimiento estricto de transiciones de estado, validación
de decisiones y protección del patrimonio histórico.
"""


class ReviewQueueDomainError(Exception):
    """Excepción base para errores de dominio en la cola de revisión."""


class InvalidStateTransitionError(ReviewQueueDomainError):
    """Lanzada cuando se intenta una transición no autorizada en el ciclo de vida del caso."""


class InvalidDecisionError(ReviewQueueDomainError):
    """Lanzada cuando una decisión humana no cumple las reglas del dominio."""


class HistoricalDataProtectionError(ReviewQueueDomainError):
    """Lanzada ante cualquier intento de incorporar o modificar registros patrimoniales históricos."""

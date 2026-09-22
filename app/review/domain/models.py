"""app.review.domain.models

Entidades y agregados del dominio de Cola de Revisión.
Gobernados bajo el principio inviolable DETECTAR ≠ CORREGIR, EVIDENCIA ≠ SUPOSICIÓN
y preservación estricta de registros históricos.
"""

from dataclasses import dataclass
from typing import Optional

from app.review.domain.enums import (
    EstamentoInstitucional,
    ReviewCaseStatus,
    ReviewCaseType,
    ReviewDecisionType,
)
from app.review.domain.exceptions import (
    HistoricalDataProtectionError,
    InvalidDecisionError,
    InvalidStateTransitionError,
)


@dataclass(frozen=True)
class ReviewDecision:
    """Decisión explícita adoptada por el operador humano ante un caso de revisión."""

    tipo_decision: ReviewDecisionType
    justificacion: str
    usuario_operador: str
    fecha_resolucion: str
    nuevo_estamento: Optional[EstamentoInstitucional] = None
    id_persona_seleccionada: Optional[str] = None
    nueva_cedula: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.justificacion or not self.justificacion.strip():
            raise InvalidDecisionError("La justificación pericial de la decisión es obligatoria.")
        if not self.usuario_operador or not self.usuario_operador.strip():
            raise InvalidDecisionError("El usuario operador que adopta la decisión es obligatorio.")
        if not self.fecha_resolucion or not self.fecha_resolucion.strip():
            raise InvalidDecisionError("La fecha y hora de la resolución es obligatoria.")

        if self.tipo_decision == ReviewDecisionType.CONFIRMAR_ESTAMENTO:
            if self.nuevo_estamento is None:
                raise InvalidDecisionError(
                    "Para CONFIRMAR_ESTAMENTO se requiere especificar un estamento del catálogo oficial."
                )
        elif self.tipo_decision == ReviewDecisionType.CONFIRMAR_IDENTIDAD:
            if not self.id_persona_seleccionada and not self.nueva_cedula:
                raise InvalidDecisionError(
                    "Para CONFIRMAR_IDENTIDAD se requiere indicar una persona existente o una cédula válida."
                )


@dataclass
class ReviewCase:
    """Entidad de dominio que encapsula el ciclo de vida y trazabilidad de un caso en revisión."""

    id_caso: str
    id_actividad: str
    id_persona: str
    nombre_persona: str
    estamento_actual: str
    motivo_revision: str
    tipo_caso: ReviewCaseType
    estado: ReviewCaseStatus = ReviewCaseStatus.PENDIENTE
    cedula_persona: Optional[str] = None
    archivo_fuente: Optional[str] = None
    fila_fuente: Optional[int] = None
    fecha_deteccion: Optional[str] = None
    fecha_resolucion: Optional[str] = None
    usuario_resolutor: Optional[str] = None
    observaciones: Optional[str] = None
    es_historico_preexistente: bool = False

    def __post_init__(self) -> None:
        # Invariante INV-03: Los 32 registros históricos M5 jamás pueden ingresar al ciclo de revisión
        if self.es_historico_preexistente:
            raise HistoricalDataProtectionError(
                f"El registro '{self.id_caso}' está marcado como histórico preexistente "
                "y no puede ser gestionado en la cola de revisión."
            )

    def iniciar_revision(self, usuario: str) -> None:
        """Transición: PENDIENTE -> EN_REVISION."""
        if not usuario or not usuario.strip():
            raise InvalidStateTransitionError("Se requiere identificar al usuario que inicia la revisión.")

        if self.estado != ReviewCaseStatus.PENDIENTE:
            raise InvalidStateTransitionError(
                f"No se puede iniciar revisión: el caso está en estado '{self.estado.value}', esperado 'PENDIENTE'."
            )

        self.estado = ReviewCaseStatus.EN_REVISION
        self.usuario_resolutor = usuario.strip()

    def resolver(self, decision: ReviewDecision) -> None:
        """Transición: EN_REVISION -> RESUELTO."""
        if self.estado != ReviewCaseStatus.EN_REVISION:
            raise InvalidStateTransitionError(
                f"No se puede resolver: el caso debe estar en estado 'EN_REVISION' (actual: '{self.estado.value}')."
            )

        if decision.tipo_decision not in (
            ReviewDecisionType.CONFIRMAR_ESTAMENTO,
            ReviewDecisionType.CONFIRMAR_IDENTIDAD,
        ):
            raise InvalidDecisionError(
                f"La decisión '{decision.tipo_decision.value}' no es válida para transicionar a RESUELTO."
            )

        self.estado = ReviewCaseStatus.RESUELTO
        self.fecha_resolucion = decision.fecha_resolucion
        self.usuario_resolutor = decision.usuario_operador
        self.observaciones = decision.justificacion

    def marcar_no_resoluble(self, justificacion: str, usuario: str, fecha: str) -> None:
        """Transición: EN_REVISION -> NO_RESOLUBLE."""
        if self.estado != ReviewCaseStatus.EN_REVISION:
            raise InvalidStateTransitionError(
                f"No se puede marcar como no resoluble: el caso debe estar en 'EN_REVISION' (actual: '{self.estado.value}')."
            )

        if not justificacion or not justificacion.strip():
            raise InvalidDecisionError("Se requiere una justificación formal para declarar un caso NO_RESOLUBLE.")

        if not usuario or not usuario.strip():
            raise InvalidDecisionError("Se requiere el usuario operador que declara el caso NO_RESOLUBLE.")

        self.estado = ReviewCaseStatus.NO_RESOLUBLE
        self.fecha_resolucion = fecha
        self.usuario_resolutor = usuario.strip()
        self.observaciones = justificacion.strip()

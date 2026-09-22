"""app.review.application.service

Servicio de aplicación para la orquestación pericial de la Cola de Revisión.
Gobernado bajo:
- DETECTAR ≠ CORREGIR: Toda resolución requiere acción humana explícita.
- EVIDENCIA ≠ SUPOSICIÓN: Prohibido fabricar datos o autocompletar cédulas.
- PLANIFICADO ≠ EJECUTADO: Total aislamiento respecto a Planning.
- Inviolabilidad de M5 Histórico: Los 32 registros preexistentes nunca ingresan a la cola.
- Aislamiento de capas: Expone exclusivamente DTOs inmutables a la UI y desacopla infraestructura.
"""

from datetime import datetime
from typing import List, Optional

from app.audit.audit_logger import get_logger
from app.review.application.dto import (
    CandidateMatchDTO,
    ReviewCaseDetailDTO,
    ReviewCaseSummaryDTO,
    ReviewHistoryItemDTO,
    ReviewResolutionResultDTO,
)
from app.review.domain.enums import (
    EstamentoInstitucional,
    ReviewDecisionType,
)
from app.review.domain.exceptions import (
    InvalidDecisionError,
    ReviewQueueDomainError,
)
from app.review.domain.models import ReviewDecision
from app.review.application.ports import IReviewQueueRepository

logger = get_logger(__name__)


class ReviewQueueApplicationService:
    """Servicio de aplicación que coordina los casos de uso de la Cola de Revisión."""

    def __init__(self, repository: IReviewQueueRepository) -> None:
        """Inicializa el servicio inyectando el puerto de persistencia."""
        self._repository = repository

    def listar_casos_pendientes(
        self, id_actividad: Optional[str] = None
    ) -> List[ReviewCaseSummaryDTO]:
        """Recupera la lista de casos pendientes de resolución pericial."""
        return self._repository.list_pending_cases(id_actividad=id_actividad)

    def obtener_detalle_caso(
        self, id_participacion: str
    ) -> Optional[ReviewCaseDetailDTO]:
        """Recupera el detalle pericial de un caso con su evidencia contextual."""
        if not id_participacion or not id_participacion.strip():
            raise ValueError("El identificador de la participación es obligatorio.")
        return self._repository.get_case_detail(id_participacion.strip())

    def iniciar_revision(
        self, id_participacion: str, usuario: str
    ) -> Optional[ReviewCaseDetailDTO]:
        """Asienta el inicio de revisión humana para un caso específico."""
        if not usuario or not usuario.strip():
            raise ValueError("Se requiere identificar al usuario operador.")

        detalle = self.obtener_detalle_caso(id_participacion)
        if not detalle:
            raise ReviewQueueDomainError(f"Caso '{id_participacion}' no encontrado.")

        # Retorna el detalle con el usuario resolutor preasignado
        return ReviewCaseDetailDTO(
            id_caso=detalle.id_caso,
            id_actividad=detalle.id_actividad,
            nombre_actividad=detalle.nombre_actividad,
            id_persona=detalle.id_persona,
            nombre_persona=detalle.nombre_persona,
            estamento_actual=detalle.estamento_actual,
            tipo_caso=detalle.tipo_caso,
            motivo_revision=detalle.motivo_revision,
            estado="EN_REVISION",
            cedula_persona=detalle.cedula_persona,
            sexo_persona=detalle.sexo_persona,
            carrera_o_cargo=detalle.carrera_o_cargo,
            entidad_externa=detalle.entidad_externa,
            archivo_fuente=detalle.archivo_fuente,
            fila_fuente=detalle.fila_fuente,
            fecha_actividad=detalle.fecha_actividad,
            lugar_actividad=detalle.lugar_actividad,
            usuario_resolutor=usuario.strip(),
            fecha_resolucion=None,
            observaciones=None,
            candidatos_sugeridos=detalle.candidatos_sugeridos,
        )

    def resolver_estamento(
        self,
        id_participacion: str,
        nuevo_estamento: str,
        justificacion: str,
        usuario: str,
    ) -> ReviewResolutionResultDTO:
        """Resuelve el estamento del participante asignándolo a un valor del catálogo cerrado."""
        if not nuevo_estamento or not nuevo_estamento.strip():
            raise InvalidDecisionError("Debe seleccionar un estamento institucional oficial.")

        estamento_norm = nuevo_estamento.strip().upper()
        try:
            estamento_enum = EstamentoInstitucional(estamento_norm)
        except ValueError:
            validos = [e.value for e in EstamentoInstitucional]
            raise InvalidDecisionError(
                f"El estamento '{nuevo_estamento}' no pertenece al catálogo oficial BICU. Valores permitidos: {validos}."
            )

        decision = ReviewDecision(
            tipo_decision=ReviewDecisionType.CONFIRMAR_ESTAMENTO,
            nuevo_estamento=estamento_enum,
            justificacion=justificacion,
            usuario_operador=usuario,
            fecha_resolucion=datetime.now().isoformat(),
        )

        return self._repository.execute_atomic_resolution(
            id_participacion=id_participacion,
            decision=decision,
        )

    def resolver_identidad(
        self,
        id_participacion: str,
        id_persona_existente: Optional[str] = None,
        nueva_cedula: Optional[str] = None,
        justificacion: str = "",
        usuario: str = "",
    ) -> ReviewResolutionResultDTO:
        """Resuelve la identidad vinculando a persona existente o asignando nueva cédula validada."""
        if not id_persona_existente and not nueva_cedula:
            raise InvalidDecisionError(
                "Debe proporcionar una persona existente seleccionada o una nueva cédula oficial."
            )

        decision = ReviewDecision(
            tipo_decision=ReviewDecisionType.CONFIRMAR_IDENTIDAD,
            id_persona_seleccionada=id_persona_existente.strip() if id_persona_existente else None,
            nueva_cedula=nueva_cedula.strip() if nueva_cedula else None,
            justificacion=justificacion,
            usuario_operador=usuario,
            fecha_resolucion=datetime.now().isoformat(),
        )

        return self._repository.execute_atomic_resolution(
            id_participacion=id_participacion,
            decision=decision,
        )

    def marcar_no_resoluble(
        self,
        id_participacion: str,
        motivo: str,
        usuario: str,
    ) -> ReviewResolutionResultDTO:
        """Declara formalmente el caso como NO_RESOLUBLE conservando su evidencia para auditoría."""
        decision = ReviewDecision(
            tipo_decision=ReviewDecisionType.MARCAR_NO_RESOLUBLE,
            justificacion=motivo,
            usuario_operador=usuario,
            fecha_resolucion=datetime.now().isoformat(),
        )

        return self._repository.execute_atomic_resolution(
            id_participacion=id_participacion,
            decision=decision,
        )

    def listar_historial_resoluciones(
        self, limite: int = 50
    ) -> List[ReviewHistoryItemDTO]:
        """Recupera el historial de eventos periciales asentados en auditoria_evento."""
        return self._repository.list_history(limite=limite)

    def buscar_candidatos_persona(
        self, query: str, excluir_id_persona: str = "", limite: int = 10
    ) -> List[CandidateMatchDTO]:
        """Busca candidatos potenciales en el padrón institucional (asistencia al operador)."""
        return self._repository.search_candidates(
            nombre=query,
            excluir_id_persona=excluir_id_persona,
            limite=limite,
        )

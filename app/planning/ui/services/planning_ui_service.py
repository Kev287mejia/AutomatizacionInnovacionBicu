"""
app.planning.ui.services.planning_ui_service

Fachada de Servicio de Aplicación para la Interfaz Gráfica de Planificación Institucional BICU.
Fase 29.11 — Implementación Controlada de la UI de Planificación Institucional.

Aísla completamente a las vistas de CustomTkinter respecto a la persistencia SQLite,
inversión de dependencias y orquestación de servicios de dominio.
Traduce excepciones técnicas a mensajes institucionales comprensibles y accionables.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Union
import uuid

from app.infrastructure.persistence.connection import SQLiteConnectionManager
from app.planning.application.services import (
    MethodologicalDesignService,
    MethodologicalDocumentExportService,
)
from app.planning.domain.dtos import (
    AcceptAIProposalCommand,
    AIProposalDTO,
    MethodologicalDesignDTO,
    PlannedActivityDetailDTO,
    PlannedActivitySummaryDTO,
    RejectAIProposalCommand,
    RequestAIProposalCommand,
    UpdateMethodologicalDesignCommand,
    ValidationReportDTO,
)
from app.planning.domain.ports import AIAssistancePort
from app.planning.domain.validator import MethodologicalDesignValidator
from app.planning.infrastructure.ai import get_ai_assistance_adapter
from app.planning.infrastructure.ai.mock_adapter import LocalMockAIAssistanceAdapter
from app.planning.infrastructure.document_rendering import (
    DocxMethodologicalDocumentRenderer,
    DocumentRenderingError,
)
from app.planning.infrastructure.persistence import (
    PlanningUnitOfWork,
    SQLiteMethodologicalDesignRepository,
)

logger = logging.getLogger(__name__)


class PlanningUIError(Exception):
    """Excepción amigable formateada para la presentación en la interfaz de usuario."""

    def __init__(self, message: str, technical_details: Optional[str] = None) -> None:
        super().__init__(message)
        self.message = message
        self.technical_details = technical_details or ""


class PlanningUIService:
    """Fachada de interacción para la UI de Planificación y Diseño Metodológico.

    Orquesta las operaciones entre MethodologicalDesignService y
    MethodologicalDocumentExportService sin acoplar las vistas de Tkinter a SQLite.
    """

    def __init__(
        self,
        design_service: Optional[MethodologicalDesignService] = None,
        export_service: Optional[MethodologicalDocumentExportService] = None,
        connection_manager: Optional[SQLiteConnectionManager] = None,
        ai_assistance_port: Optional[AIAssistancePort] = None,
    ) -> None:
        self._connection_manager = connection_manager or SQLiteConnectionManager()

        if ai_assistance_port is not None:
            self._ai_port: Optional[AIAssistancePort] = ai_assistance_port
        else:
            self._ai_port = get_ai_assistance_adapter()

        if design_service is not None:
            self._design_service = design_service
            if getattr(self._design_service, "_ai_port", None) is None and self._ai_port is not None:
                self._design_service._ai_port = self._ai_port
        else:
            uow = PlanningUnitOfWork(connection_manager=self._connection_manager)
            validator = MethodologicalDesignValidator()
            self._design_service = MethodologicalDesignService(
                uow=uow,
                validator=validator,
                ai_assistance_port=self._ai_port,
            )

        if export_service is not None:
            self._export_service = export_service
        else:
            conn = self._connection_manager.get_connection()
            design_repo = SQLiteMethodologicalDesignRepository(conn)
            renderer = DocxMethodologicalDocumentRenderer()
            self._export_service = MethodologicalDocumentExportService(
                design_repository=design_repo,
                renderer=renderer,
            )

    def list_activities(
        self,
        sede: Optional[str] = None,
        status: Optional[str] = None,
        search_term: Optional[str] = None,
    ) -> tuple[PlannedActivitySummaryDTO, ...]:
        """Obtiene actividades planificadas con filtros institucionales."""
        try:
            # Normalizar valores vacíos o comodines
            clean_sede = None if (not sede or sede == "Todas") else sede.strip()
            clean_status = None if (not status or status == "Todos") else status.strip()
            clean_search = None if (not search_term or not search_term.strip()) else search_term.strip()

            return self._design_service.list_activities_with_design_status(
                sede=clean_sede,
                status=clean_status,
                search_term=clean_search,
            )
        except Exception as e:
            logger.error(f"Error al listar actividades planificadas: {e}", exc_info=True)
            raise PlanningUIError(
                "No fue posible consultar las actividades del Plan Operativo Anual (POA). "
                "Verifique la conexión institucional con la base de datos.",
                technical_details=str(e),
            ) from e

    def get_activity_detail(self, activity_ref: str) -> Optional[PlannedActivityDetailDTO]:
        """Obtiene el detalle completo de una actividad planificada."""
        try:
            return self._design_service.get_activity_detail(activity_ref)
        except Exception as e:
            logger.error(f"Error al obtener detalle de actividad '{activity_ref}': {e}", exc_info=True)
            raise PlanningUIError(
                f"No fue posible consultar la información de la actividad seleccionada ('{activity_ref}').",
                technical_details=str(e),
            ) from e

    def create_design_draft(self, activity_ref: str, created_by: str) -> MethodologicalDesignDTO:
        """Crea o inicializa un borrador DRAFT de diseño metodológico."""
        try:
            return self._design_service.create_design_draft(
                activity_ref=activity_ref,
                created_by=created_by,
            )
        except RuntimeError as e:
            # Violación de R-08 (ya aprobado)
            raise PlanningUIError(
                "No se puede crear un nuevo borrador: La actividad seleccionada ya cuenta con un "
                "Diseño Metodológico en estado APROBADO, el cual es inmutable institucionalmente (Regla R-08).",
                technical_details=str(e),
            ) from e
        except ValueError as e:
            raise PlanningUIError(
                f"Información insuficiente para crear el borrador: {e}",
                technical_details=str(e),
            ) from e
        except Exception as e:
            logger.error(f"Error inesperado al crear borrador para '{activity_ref}': {e}", exc_info=True)
            raise PlanningUIError(
                "Ocurrió un error inesperado al inicializar el borrador del Diseño Metodológico.",
                technical_details=str(e),
            ) from e

    def update_design_draft(self, command: UpdateMethodologicalDesignCommand) -> MethodologicalDesignDTO:
        """Actualiza los bloques de un diseño metodológico en estado DRAFT."""
        try:
            return self._design_service.update_design_draft(command)
        except RuntimeError as e:
            raise PlanningUIError(
                "Operación rechazada: El diseño metodológico ya se encuentra en estado APROBADO "
                "y no puede ser modificado (Regla R-08 de inmutabilidad institucional).",
                technical_details=str(e),
            ) from e
        except ValueError as e:
            raise PlanningUIError(
                f"Datos inconsistentes en el diseño metodológico: {e}",
                technical_details=str(e),
            ) from e
        except Exception as e:
            logger.error(f"Error al actualizar borrador '{command.design_id}': {e}", exc_info=True)
            raise PlanningUIError(
                "No fue posible guardar los cambios en el borrador del diseño metodológico. "
                "Por favor intente nuevamente.",
                technical_details=str(e),
            ) from e

    def validate_design(self, design_id: uuid.UUID) -> ValidationReportDTO:
        """Ejecuta las validaciones institucionales pre-exportación."""
        try:
            return self._design_service.validate_design(design_id)
        except ValueError as e:
            raise PlanningUIError(
                f"No se pudo validar el diseño metodológico: {e}",
                technical_details=str(e),
            ) from e
        except Exception as e:
            logger.error(f"Error al validar diseño '{design_id}': {e}", exc_info=True)
            raise PlanningUIError(
                "Ocurrió un error durante el proceso de validación institucional del diseño.",
                technical_details=str(e),
            ) from e

    def approve_design(self, design_id: uuid.UUID, approved_by: str) -> MethodologicalDesignDTO:
        """Aprueba formalmente el diseño metodológico."""
        try:
            return self._design_service.approve_design(design_id=design_id, approved_by=approved_by)
        except RuntimeError as e:
            raise PlanningUIError(
                "El diseño metodológico ya se encuentra formalmente APROBADO (inmutable R-08).",
                technical_details=str(e),
            ) from e
        except ValueError as e:
            raise PlanningUIError(
                f"No se puede aprobar el diseño metodológico debido a observaciones pendientes: {e}",
                technical_details=str(e),
            ) from e
        except Exception as e:
            logger.error(f"Error al aprobar diseño '{design_id}': {e}", exc_info=True)
            raise PlanningUIError(
                "Ocurrió un error inesperado al procesar la aprobación institucional.",
                technical_details=str(e),
            ) from e

    def export_docx(self, design_id: uuid.UUID, output_path: Union[str, Path]) -> str:
        """Exporta el diseño metodológico a documento Word (.docx)."""
        try:
            out_str = str(output_path)
            return self._export_service.export_by_id(design_id=design_id, output_path=out_str)
        except DocumentRenderingError as e:
            raise PlanningUIError(
                "Error al generar el documento oficial en Word. Si el archivo ya existe y está "
                "abierto en Microsoft Word, por favor ciérrelo e intente nuevamente.",
                technical_details=str(e),
            ) from e
        except PermissionError as e:
            raise PlanningUIError(
                "Acceso denegado al guardar el archivo Word en la ruta especificada. "
                "Verifique que posea permisos de escritura en la carpeta de destino.",
                technical_details=str(e),
            ) from e
        except ValueError as e:
            raise PlanningUIError(
                f"No se pudo generar el documento: {e}",
                technical_details=str(e),
            ) from e
        except Exception as e:
            logger.error(f"Error al exportar DOCX para diseño '{design_id}': {e}", exc_info=True)
            raise PlanningUIError(
                "Ocurrió un error inesperado al renderizar el documento Word institucional.",
                technical_details=str(e),
            ) from e

    def request_ai_proposal(
        self,
        design_id: uuid.UUID,
        target_field: str,
        step_number: Optional[int] = None,
        phase_label: Optional[str] = None,
    ) -> AIProposalDTO:
        """Solicita una propuesta de asistencia de IA para un campo autorizado del diseño metodológico.

        Args:
            design_id: Identificador único del diseño metodológico.
            target_field: Campo narrativo autorizado a asistir.
            step_number: Número de paso para campos de la matriz operativa (opcional).
            phase_label: Etiqueta de la fase para campos de la matriz operativa (opcional).

        Returns:
            AIProposalDTO con la propuesta generada en estado pendiente de revisión.

        Raises:
            PlanningUIError: Si el diseño está aprobado (R-08), no existe, o falla el adaptador.
        """
        try:
            cmd = RequestAIProposalCommand(
                design_id=design_id,
                target_field=target_field,
                step_number=step_number,
                phase_label=phase_label,
            )
            return self._design_service.request_ai_proposal(command=cmd, ai_port=self._ai_port)
        except RuntimeError as e:
            logger.warning(f"Error al solicitar propuesta IA para '{design_id}': {e}")
            err_str = str(e)
            if "APPROVED" in err_str or "R-08" in err_str:
                raise PlanningUIError(
                    "No se puede generar una propuesta de asistencia: "
                    "El diseño metodológico ya se encuentra en estado APROBADO "
                    "y es inmutable institucionalmente (Regla R-08).",
                    technical_details=err_str,
                ) from e
            raise PlanningUIError(
                "No fue posible generar una propuesta en este momento. El diseño actual no fue modificado.",
                technical_details=err_str,
            ) from e
        except ValueError as e:
            logger.warning(f"Validación rechazada al solicitar propuesta IA para '{design_id}': {e}")
            raise PlanningUIError(
                f"No fue posible procesar la solicitud de asistencia: {e}",
                technical_details=str(e),
            ) from e
        except Exception as e:
            logger.error(f"Error inesperado al solicitar propuesta IA para '{design_id}': {e}", exc_info=True)
            raise PlanningUIError(
                "No fue posible generar una propuesta en este momento. El diseño actual no fue modificado.",
                technical_details=str(e),
            ) from e

    def accept_ai_proposal(
        self,
        design_id: uuid.UUID,
        proposal_id: uuid.UUID,
        reviewer: str,
    ) -> MethodologicalDesignDTO:
        """Acepta formalmente una propuesta de asistencia de IA y vuelca su contenido al borrador (DRAFT).

        Args:
            design_id: Identificador único del diseño metodológico.
            proposal_id: Identificador único de la propuesta de asistencia a aceptar.
            reviewer: Nombre del funcionario que revisa y acepta la propuesta.

        Returns:
            MethodologicalDesignDTO actualizado con el contenido propuesto (en estado DRAFT).

        Raises:
            PlanningUIError: Si el diseño está aprobado, no existe, o falta el revisor.
        """
        try:
            cmd = AcceptAIProposalCommand(
                design_id=design_id,
                proposal_id=proposal_id,
                reviewer=reviewer,
            )
            return self._design_service.accept_ai_proposal(command=cmd)
        except RuntimeError as e:
            logger.warning(f"Error de estado al aceptar propuesta IA '{proposal_id}': {e}")
            raise PlanningUIError(
                "Operación rechazada: El diseño metodológico ya se encuentra en estado APROBADO "
                "y no puede ser modificado (Regla R-08).",
                technical_details=str(e),
            ) from e
        except ValueError as e:
            logger.warning(f"Validación rechazada al aceptar propuesta IA '{proposal_id}': {e}")
            raise PlanningUIError(
                f"No se pudo aceptar la propuesta de asistencia: {e}",
                technical_details=str(e),
            ) from e
        except Exception as e:
            logger.error(f"Error inesperado al aceptar propuesta IA '{proposal_id}': {e}", exc_info=True)
            raise PlanningUIError(
                "Ocurrió un error inesperado al aplicar la propuesta de asistencia.",
                technical_details=str(e),
            ) from e

    def reject_ai_proposal(
        self,
        design_id: uuid.UUID,
        proposal_id: uuid.UUID,
        reviewer: str,
        rejection_reason: str,
    ) -> MethodologicalDesignDTO:
        """Rechaza formalmente una propuesta de asistencia de IA registrando el motivo obligatorio.

        Args:
            design_id: Identificador único del diseño metodológico.
            proposal_id: Identificador único de la propuesta de asistencia a rechazar.
            reviewer: Nombre del funcionario que revisa y rechaza la propuesta.
            rejection_reason: Motivo obligatorio del rechazo institucional.

        Returns:
            MethodologicalDesignDTO con la propuesta registrada como rechazada.

        Raises:
            PlanningUIError: Si el diseño está aprobado, no existe, o faltan revisor/motivo.
        """
        try:
            cmd = RejectAIProposalCommand(
                design_id=design_id,
                proposal_id=proposal_id,
                reviewer=reviewer,
                rejection_reason=rejection_reason,
            )
            return self._design_service.reject_ai_proposal(command=cmd)
        except RuntimeError as e:
            logger.warning(f"Error de estado al rechazar propuesta IA '{proposal_id}': {e}")
            raise PlanningUIError(
                "Operación rechazada: El diseño metodológico ya se encuentra en estado APROBADO (Regla R-08).",
                technical_details=str(e),
            ) from e
        except ValueError as e:
            logger.warning(f"Validación rechazada al rechazar propuesta IA '{proposal_id}': {e}")
            raise PlanningUIError(
                f"No se pudo registrar el rechazo de la propuesta: {e}",
                technical_details=str(e),
            ) from e
        except Exception as e:
            logger.error(f"Error inesperado al rechazar propuesta IA '{proposal_id}': {e}", exc_info=True)
            raise PlanningUIError(
                "Ocurrió un error inesperado al procesar el rechazo de la propuesta.",
                technical_details=str(e),
            ) from e

    def list_ai_proposals(self, design_id: uuid.UUID) -> tuple[AIProposalDTO, ...]:
        """Lista todas las propuestas de asistencia de IA asociadas a un diseño metodológico.

        Args:
            design_id: Identificador único del diseño metodológico.

        Returns:
            Tupla con los DTOs de todas las propuestas históricas asociadas.

        Raises:
            PlanningUIError: Si design_id es nulo o no existe.
        """
        try:
            return self._design_service.list_ai_proposals(design_id=design_id)
        except ValueError as e:
            raise PlanningUIError(
                f"No se pudieron consultar las propuestas del diseño: {e}",
                technical_details=str(e),
            ) from e
        except Exception as e:
            logger.error(f"Error al listar propuestas IA para '{design_id}': {e}", exc_info=True)
            raise PlanningUIError(
                "No fue posible consultar el historial de propuestas de asistencia de IA.",
                technical_details=str(e),
            ) from e

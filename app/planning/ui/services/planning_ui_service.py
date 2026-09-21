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
    MethodologicalDesignDTO,
    PlannedActivityDetailDTO,
    PlannedActivitySummaryDTO,
    UpdateMethodologicalDesignCommand,
    ValidationReportDTO,
)
from app.planning.domain.validator import MethodologicalDesignValidator
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
    ) -> None:
        self._connection_manager = connection_manager or SQLiteConnectionManager()

        if design_service is not None:
            self._design_service = design_service
        else:
            uow = PlanningUnitOfWork(connection_manager=self._connection_manager)
            validator = MethodologicalDesignValidator()
            self._design_service = MethodologicalDesignService(uow=uow, validator=validator)

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

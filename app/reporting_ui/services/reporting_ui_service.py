"""app.reporting_ui.services.reporting_ui_service

Servicio de Aplicación para la Capa Visual de Reporting y Dashboard BICU.
Fase 29.20.3 — Integración Controlada de Reporting + Dashboard.

PRINCIPIOS:
  - Cero consultas directas a SQLite ni acceso a M1–M5.
  - Cero lógica matemática duplicada (todo proviene de ReportingService e Indicators).
  - Comunicación síncrona y transparente.
  - Orquestación de exportadores derivados autorizados (XLSX, DOCX, CSV).
"""

from pathlib import Path
from typing import Dict, List, Optional, Union

from app.reporting.application.reporting_service import ReportingService
from app.reporting.domain.dto import (
    DashboardDataDTO,
    ReportDocumentDTO,
    ReportFilterDTO,
)
from app.reporting.domain.enums import (
    ExportFormat,
    MultisessionGoalMode,
    ReportType,
)
from app.reporting.infrastructure.exporters.csv_exporter import CSVReportExporter
from app.reporting.infrastructure.exporters.docx_exporter import DOCXReportExporter
from app.reporting.infrastructure.exporters.xlsx_exporter import XLSXReportExporter


class ReportingUIService:
    """Servicio de aplicación que aísla las vistas CustomTkinter del núcleo del sistema."""

    def __init__(
        self,
        reporting_service: ReportingService,
        xlsx_exporter: Optional[XLSXReportExporter] = None,
        docx_exporter: Optional[DOCXReportExporter] = None,
        csv_exporter: Optional[CSVReportExporter] = None,
    ) -> None:
        self._reporting_service = reporting_service
        self._xlsx_exporter = xlsx_exporter or XLSXReportExporter()
        self._docx_exporter = docx_exporter or DOCXReportExporter()
        self._csv_exporter = csv_exporter or CSVReportExporter()

    def get_dashboard(self, filters: Optional[ReportFilterDTO] = None) -> DashboardDataDTO:
        """Obtiene el payload inmutable del Dashboard de 5 niveles sin cálculos en UI."""
        return self._reporting_service.get_dashboard_data(filters=filters)

    def generate_report(
        self,
        report_type: ReportType,
        filters: Optional[ReportFilterDTO] = None,
    ) -> ReportDocumentDTO:
        """Genera un documento oficial estructurado (REP-01 a REP-05)."""
        return self._reporting_service.generate_report(report_type=report_type, filters=filters)

    def export_report(
        self,
        document: ReportDocumentDTO,
        output_path: Union[str, Path],
        export_format: ExportFormat,
    ) -> Path:
        """Exporta un reporte previamente generado a uno de los formatos MVP aprobados."""
        if export_format == ExportFormat.XLSX:
            return self._xlsx_exporter.export(document, output_path)
        elif export_format == ExportFormat.DOCX:
            return self._docx_exporter.export(document, output_path)
        elif export_format == ExportFormat.CSV:
            return self._csv_exporter.export(document, output_path)
        elif export_format == ExportFormat.PDF:
            raise NotImplementedError("El formato PDF se encuentra clasificado como post-MVP. Use XLSX, DOCX o CSV.")
        else:
            raise ValueError(f"Formato de exportación no reconocido: '{export_format}'.")

    def get_available_report_types(self) -> List[Dict[str, str]]:
        """Retorna el catálogo canónico de reportes institucionales autorizados."""
        return [
            {
                "type": ReportType.REP_01.value,
                "enum": ReportType.REP_01,
                "title": "Balance Ejecutivo de Gestión Institucional",
                "description": "Síntesis transversal de actividades, cumplimiento POA, cobertura de participantes y salud de datos.",
            },
            {
                "type": ReportType.REP_02.value,
                "enum": ReportType.REP_02,
                "title": "Evaluación de Cumplimiento del POA",
                "description": "Comparativa pericial entre metas planificadas y ejecución efectiva en territorio (Plan vs Ejecución).",
            },
            {
                "type": ReportType.REP_03.value,
                "enum": ReportType.REP_03,
                "title": "Cobertura Demográfica y Atención de Protagonistas",
                "description": "Desglose de beneficiarios por estamento (estudiantes, docentes, colaboradores) y sexo.",
            },
            {
                "type": ReportType.REP_04.value,
                "enum": ReportType.REP_04,
                "title": "Extensión y Descentralización Territorial",
                "description": "Presencia territorial institucional por sede y municipio en la Costa Caribe.",
            },
            {
                "type": ReportType.REP_05.value,
                "enum": ReportType.REP_05,
                "title": "Auditoría de Trazabilidad, Gobernanza y Salud del Dato",
                "description": "Diagnóstico de integridad, documentos procesados, eventos emergentes y discrepancias activas.",
            },
        ]

    def get_default_filters(self) -> ReportFilterDTO:
        """Retorna la configuración de filtros predeterminada conforme a directivas."""
        return ReportFilterDTO(
            multisession_goal_mode=MultisessionGoalMode.COHORT_UNIQUE.value,
            require_verified_id_for_unique_persons=True,
        )

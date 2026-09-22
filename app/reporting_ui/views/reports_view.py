"""app.reporting_ui.views.reports_view

Catálogo y generador interactivo de los 5 reportes institucionales aprobados BICU.
Fase 29.20.3 — Integración Controlada de Reporting + Dashboard.

PRINCIPIOS:
  - Catálogo estricto de reportes oficiales MVP:
      REP-01: Balance Ejecutivo de Gestión Institucional
      REP-02: Evaluación de Cumplimiento del POA
      REP-03: Cobertura Demográfica y Atención de Protagonistas
      REP-04: Extensión y Descentralización Territorial
      REP-05: Auditoría de Trazabilidad, Gobernanza y Salud del Dato
  - Generación bajo demanda e integración directa con ReportPreviewView.
"""

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import customtkinter as ctk

from app.reporting.domain.dto import ReportDocumentDTO, ReportFilterDTO
from app.reporting.domain.enums import ExportFormat, ReportType
from app.reporting_ui.views.report_preview_view import ReportPreviewView


class ReportsView(ctk.CTkFrame):
    """Vista de catálogo de reportes institucionales y previsualización/exportación."""

    def __init__(
        self,
        master: Any,
        on_generate_report: Optional[Callable[[ReportType, ReportFilterDTO], ReportDocumentDTO]] = None,
        on_export_report: Optional[Callable[[ReportDocumentDTO, Path, ExportFormat], Path]] = None,
        get_active_filters: Optional[Callable[[], ReportFilterDTO]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self.on_generate_report = on_generate_report
        self.on_export_report = on_export_report
        self.get_active_filters = get_active_filters

        self._init_ui()

    def _init_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)

        # -----------------------------------------------------------------
        # Panel Izquierdo: Catálogo de los 5 Reportes Oficiales
        # -----------------------------------------------------------------
        catalog_panel = ctk.CTkFrame(self, fg_color=("gray95", "gray17"), corner_radius=6, border_width=1, border_color=("gray85", "gray25"))
        catalog_panel.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)
        catalog_panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            catalog_panel,
            text="CATÁLOGO DE REPORTES OFICIALES",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=("#0B3C5D", "#4FC3F7"),
            anchor="w",
        ).pack(fill="x", padx=12, pady=(12, 6))

        # Lista de reportes
        reports_catalog = [
            (
                ReportType.REP_01,
                "REP-01: Balance Ejecutivo",
                "Balance consolidado de gestión, cumplimiento global y salud del dato.",
            ),
            (
                ReportType.REP_02,
                "REP-02: Cumplimiento POA",
                "Evaluación plan vs ejecución, cobertura de metas y eventos emergentes.",
            ),
            (
                ReportType.REP_03,
                "REP-03: Cobertura Demográfica",
                "Protagonistas atendidos, personas únicas y desglose por estamento y sexo.",
            ),
            (
                ReportType.REP_04,
                "REP-04: Extensión Territorial",
                "Descentralización y alcance en sedes y municipios de la Costa Caribe.",
            ),
            (
                ReportType.REP_05,
                "REP-05: Trazabilidad y Salud",
                "Auditoría técnica de documentos, discrepancias y estado de enlaces V004.",
            ),
        ]

        for r_type, title, desc in reports_catalog:
            card = ctk.CTkFrame(catalog_panel, fg_color=("white", "gray20"), corner_radius=6, border_width=1, border_color=("gray80", "gray30"))
            card.pack(fill="x", padx=10, pady=5)

            ctk.CTkLabel(
                card,
                text=title,
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                anchor="w",
            ).pack(fill="x", padx=10, pady=(8, 2))

            ctk.CTkLabel(
                card,
                text=desc,
                font=ctk.CTkFont(family="Segoe UI", size=9),
                text_color=("gray40", "gray70"),
                anchor="w",
                wraplength=220,
                justify="left",
            ).pack(fill="x", padx=10, pady=(0, 6))

            btn = ctk.CTkButton(
                card,
                text="Generar Reporte  ➔",
                font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                fg_color="#0B3C5D",
                hover_color="#07263D",
                height=28,
                command=lambda rt=r_type: self._handle_generate(rt),
            )
            btn.pack(fill="x", padx=10, pady=(0, 8))

        # -----------------------------------------------------------------
        # Panel Derecho: Vista Previa y Exportación
        # -----------------------------------------------------------------
        self.preview_panel = ReportPreviewView(
            self,
            on_export_requested=self.on_export_report,
        )
        self.preview_panel.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)

    def _handle_generate(self, report_type: ReportType) -> None:
        filters = self.get_active_filters() if self.get_active_filters else ReportFilterDTO()
        if self.on_generate_report:
            doc = self.on_generate_report(report_type, filters)
            self.preview_panel.display_report(doc)

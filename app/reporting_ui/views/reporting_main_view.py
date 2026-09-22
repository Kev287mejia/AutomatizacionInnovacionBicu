"""app.reporting_ui.views.reporting_main_view

Vista principal contenedora del MÓDULO 4: REPORTES Y DASHBOARD INSTITUCIONAL BICU.
Fase 29.20.3 — Integración Controlada de Reporting + Dashboard.

PRINCIPIOS:
  - Estructura visual armónica con la aplicación institucional (#0B3C5D / #1A2634).
  - Coordinación de flujo mediante ReportingUIService.
  - Cero consultas a SQLite, cero cálculos matemáticos duplicados en la UI.
  - Navegación clara por pestañas: Dashboard (5 Niveles), Reportes Oficiales, Filtros y Metodología.
"""

from pathlib import Path
from typing import Any, Callable, Optional

import customtkinter as ctk

from app.reporting.domain.dto import DashboardDataDTO, ReportDocumentDTO, ReportFilterDTO
from app.reporting.domain.enums import ExportFormat, ReportType
from app.reporting_ui.services.reporting_ui_service import ReportingUIService
from app.reporting_ui.views.dashboard_view import DashboardView
from app.reporting_ui.views.report_filters_view import ReportFiltersView
from app.reporting_ui.views.reports_view import ReportsView


class ReportingMainView(ctk.CTkFrame):
    """Contenedor maestro del Módulo 4: Reportes y Dashboard Institucional."""

    def __init__(
        self,
        master: Any,
        ui_service: ReportingUIService,
        on_volver_menu: Optional[Callable[[], None]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self.ui_service = ui_service
        self.on_volver_menu = on_volver_menu
        self._current_filters: ReportFilterDTO = self.ui_service.get_default_filters()

        self._init_ui()
        self.refresh_dashboard()

    def _init_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ---------------------------------------------------------------------
        # 1. ENCABEZADO INSTITUCIONAL (#0B3C5D / #1A2634)
        # ---------------------------------------------------------------------
        header = ctk.CTkFrame(self, fg_color=("#0B3C5D", "#1A2634"), corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=0)

        title_lbl = ctk.CTkLabel(
            header,
            text="BLUEFIELDS INDIAN & CARIBBEAN UNIVERSITY — BICU",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color="white",
            anchor="w",
        )
        title_lbl.grid(row=0, column=0, padx=20, pady=(12, 2), sticky="w")

        sub_lbl = ctk.CTkLabel(
            header,
            text="MÓDULO 4: REPORTES Y DASHBOARD INSTITUCIONAL (5 NIVELES)",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=("#E0E0E0", "#B0BEC5"),
            anchor="w",
        )
        sub_lbl.grid(row=1, column=0, padx=20, pady=(0, 12), sticky="w")

        if self.on_volver_menu:
            btn_volver = ctk.CTkButton(
                header,
                text="← Menú Principal",
                font=ctk.CTkFont(family="Segoe UI", size=12),
                fg_color="#1A2634",
                hover_color="#07263D",
                width=130,
                height=32,
                corner_radius=5,
                command=self.on_volver_menu,
            )
            btn_volver.grid(row=0, column=1, rowspan=2, padx=15, pady=10, sticky="e")

        # ---------------------------------------------------------------------
        # 2. PESTAÑAS PRINCIPALES DEL MÓDULO (Tabview)
        # ---------------------------------------------------------------------
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=15, pady=10)

        self.tab_dash = self.tabview.add("1. Dashboard Institucional")
        self.tab_reports = self.tabview.add("2. Reportes Oficiales")
        self.tab_filters = self.tabview.add("3. Filtros y Parámetros")

        self.tab_dash.grid_columnconfigure(0, weight=1)
        self.tab_dash.grid_rowconfigure(1, weight=1)
        self.tab_reports.grid_columnconfigure(0, weight=1)
        self.tab_reports.grid_rowconfigure(0, weight=1)
        self.tab_filters.grid_columnconfigure(0, weight=1)
        self.tab_filters.grid_rowconfigure(0, weight=1)

        # ---------------------------------------------------------------------
        # Pestaña 1: Dashboard
        # ---------------------------------------------------------------------
        # Barra de acción rápida de Dashboard
        dash_action_bar = ctk.CTkFrame(self.tab_dash, fg_color="transparent")
        dash_action_bar.grid(row=0, column=0, sticky="ew", padx=10, pady=(4, 6))
        dash_action_bar.grid_columnconfigure(0, weight=1)

        btn_refresh = ctk.CTkButton(
            dash_action_bar,
            text="Actualizar Dashboard",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#0B3C5D",
            hover_color="#07263D",
            width=160,
            height=30,
            command=self.refresh_dashboard,
        )
        btn_refresh.grid(row=0, column=1, sticky="e")

        self.dashboard_view = DashboardView(self.tab_dash)
        self.dashboard_view.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)

        # ---------------------------------------------------------------------
        # Pestaña 2: Reportes Oficiales
        # ---------------------------------------------------------------------
        self.reports_view = ReportsView(
            self.tab_reports,
            on_generate_report=self._handle_generate_report,
            on_export_report=self._handle_export_report,
            get_active_filters=lambda: self._current_filters,
        )
        self.reports_view.grid(row=0, column=0, sticky="nsew")

        # ---------------------------------------------------------------------
        # Pestaña 3: Filtros y Parámetros
        # ---------------------------------------------------------------------
        self.filters_view = ReportFiltersView(
            self.tab_filters,
            on_apply_filters=self._handle_apply_filters,
            initial_filters=self._current_filters,
        )
        self.filters_view.grid(row=0, column=0, sticky="nsew")

    def refresh_dashboard(self) -> None:
        """Recupera los datos del Dashboard a través del servicio y solicita el re-renderizado."""
        dash_data = self.ui_service.get_dashboard(filters=self._current_filters)
        self.dashboard_view.render(dash_data)

    def _handle_apply_filters(self, filters: ReportFilterDTO) -> None:
        """Callback al presionar 'Aplicar Filtros' en ReportFiltersView."""
        self._current_filters = filters
        self.refresh_dashboard()
        # Cambiar automáticamente a la pestaña de Dashboard para ver el resultado
        self.tabview.set("1. Dashboard Institucional")

    def _handle_generate_report(self, report_type: ReportType, filters: ReportFilterDTO) -> ReportDocumentDTO:
        return self.ui_service.generate_report(report_type=report_type, filters=filters)

    def _handle_export_report(self, document: ReportDocumentDTO, target_path: Path, export_format: ExportFormat) -> Path:
        return self.ui_service.export_report(document=document, output_path=target_path, export_format=export_format)

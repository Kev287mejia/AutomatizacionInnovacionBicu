#!/usr/bin/env python
"""
run_consolidator.py

Lanzador Institucional del Consolidador Word BICU (Fase 14.9 / Fase 29.20.3).
Permite iniciar la aplicación de escritorio directamente desde la raíz del proyecto.
Composition Root: conecta las fábricas de vista de Módulo 3 y Módulo 4 de forma desacoplada.
"""

import sys
from pathlib import Path

# Asegurar que el directorio raíz del proyecto esté en sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.planning.ui.views.planning_main_view import PlanningMainView
from app.word_consolidator.ui.app import ConsolidatorApp


def create_reporting_view(container, on_back):
    """Composition root para el Módulo 4: Reportes y Dashboard Institucional."""
    from app.infrastructure.persistence.config import DatabaseConfig
    from app.infrastructure.persistence.connection import SQLiteConnectionManager
    from app.indicators.application.service import IndicatorCalculationService
    from app.indicators.infrastructure.sqlite_reader import SQLiteIndicatorReader
    from app.reporting.application.reporting_service import ReportingService
    from app.reporting_ui.services.reporting_ui_service import ReportingUIService
    from app.reporting_ui.views.reporting_main_view import ReportingMainView

    cfg = DatabaseConfig()
    mgr = SQLiteConnectionManager(cfg)
    conn = mgr.get_connection()
    reader = SQLiteIndicatorReader(conn)
    indicator_svc = IndicatorCalculationService(reader)
    reporting_svc = ReportingService(indicator_svc)
    ui_svc = ReportingUIService(reporting_svc)
    return ReportingMainView(container, ui_service=ui_svc, on_volver_menu=on_back)


def main() -> None:
    app = ConsolidatorApp(
        planning_view_factory=lambda container, on_back: PlanningMainView(
            container, on_volver_menu=on_back
        ),
        reporting_view_factory=create_reporting_view,
    )
    app.mainloop()


if __name__ == "__main__":
    main()

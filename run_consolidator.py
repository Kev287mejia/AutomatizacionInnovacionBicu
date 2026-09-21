#!/usr/bin/env python
"""
run_consolidator.py

Lanzador Institucional del Consolidador Word BICU (Fase 14.9).
Permite iniciar la aplicación de escritorio directamente desde la raíz del proyecto.
"""

import sys
from pathlib import Path

# Asegurar que el directorio raíz del proyecto esté en sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.planning.ui.views.planning_main_view import PlanningMainView
from app.word_consolidator.ui.app import ConsolidatorApp


def main() -> None:
    app = ConsolidatorApp(
        planning_view_factory=lambda container, on_back: PlanningMainView(
            container, on_volver_menu=on_back
        )
    )
    app.mainloop()


if __name__ == "__main__":
    main()

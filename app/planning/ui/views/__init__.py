"""
app.planning.ui.views

Componentes y vistas de la interfaz de usuario de planificación institucional.
Fase 29.11 — Implementación Controlada de la UI de Planificación Institucional.
"""

from app.planning.ui.views.activities_list_view import PlannedActivitiesListView
from app.planning.ui.views.activity_detail_view import PlannedActivityDetailView
from app.planning.ui.views.approval_dialog import ApprovalDialog
from app.planning.ui.views.design_editor_view import MethodologicalDesignEditorView
from app.planning.ui.views.planning_main_view import PlanningMainView
from app.planning.ui.views.validation_dialog import ValidationDialog

__all__ = [
    "PlannedActivitiesListView",
    "PlannedActivityDetailView",
    "MethodologicalDesignEditorView",
    "ValidationDialog",
    "ApprovalDialog",
    "PlanningMainView",
]

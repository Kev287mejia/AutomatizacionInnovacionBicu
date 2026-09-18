"""
app.word_consolidator.ui.views

Módulo de vistas y componentes gráficos de la interfaz institucional CustomTkinter.
"""

from app.word_consolidator.ui.views.main_window import MainWindow
from app.word_consolidator.ui.views.matrix_selection_view import MatrixSelectionView
from app.word_consolidator.ui.views.period_selection_view import PeriodSelectionView
from app.word_consolidator.ui.views.progress_view import ProgressView
from app.word_consolidator.ui.views.result_view import ResultView
from app.word_consolidator.ui.views.validation_view import ValidationView

__all__ = [
    "MainWindow",
    "MatrixSelectionView",
    "PeriodSelectionView",
    "ProgressView",
    "ResultView",
    "ValidationView",
]

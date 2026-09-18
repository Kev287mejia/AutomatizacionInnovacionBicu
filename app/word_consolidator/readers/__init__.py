"""
app.word_consolidator.readers

Módulo de lectura no destructiva y filtrado temporal para las cinco matrices oficiales de BICU.
"""

from app.word_consolidator.readers.period_filter import PeriodFilter
from app.word_consolidator.readers.matrix_reader import MatrixReader

__all__ = [
    "PeriodFilter",
    "MatrixReader",
]

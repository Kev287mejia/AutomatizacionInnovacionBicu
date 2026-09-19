"""Capa de adaptacion y contratos para la integracion hacia Word.

Expone contratos (DTOs), politicas de presentacion y el adaptador WordACL.
"""

from app.application.word_acl.policies import PoliticaPresentacionRevisionWord
from app.application.word_acl.dtos import (
    FuenteCifras,
    FuenteResultados,
    WordEstamentoItemDTO,
    WordEvidenciaItemDTO,
    WordActividadDTO,
    WordWeeklyReportDataset,
)
from app.application.word_acl.adapters import WordACL

__all__ = [
    "FuenteCifras",
    "FuenteResultados",
    "PoliticaPresentacionRevisionWord",
    "WordEstamentoItemDTO",
    "WordEvidenciaItemDTO",
    "WordActividadDTO",
    "WordWeeklyReportDataset",
    "WordACL",
]

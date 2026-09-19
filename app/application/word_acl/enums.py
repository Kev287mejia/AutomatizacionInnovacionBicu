"""Modulo de compatibilidad para enumeraciones de politicas y fuentes."""

from app.application.word_acl.policies import PoliticaPresentacionRevisionWord
from app.application.word_acl.dtos import FuenteCifras, FuenteResultados

__all__ = [
    "FuenteCifras",
    "FuenteResultados",
    "PoliticaPresentacionRevisionWord",
]

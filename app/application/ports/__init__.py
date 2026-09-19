"""app.application.ports

Puertos de salida de la capa Application hacia infraestructura externa.
"""

from app.application.ports.word_document_port import (
    IWordActividadRenderer,
    IWordInformeSemanalRenderer,
    IWordDossierRenderer,
)
from app.application.ports.word_activity_extractor import (
    IWordActivityExtractor,
)

__all__ = [
    "IWordActividadRenderer",
    "IWordInformeSemanalRenderer",
    "IWordDossierRenderer",
    "IWordActivityExtractor",
]

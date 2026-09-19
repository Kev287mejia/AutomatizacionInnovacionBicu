"""app.infrastructure.word_reader

Adaptadores de infraestructura para la lectura y extracción física de documentos Word (.docx).

Contiene la implementación concreta del extractor de informes de actividad
institucional conforme al puerto IWordActivityExtractor.
"""

from app.infrastructure.word_reader.word_activity_extractor import (
    WordActivityExtractor,
)

__all__ = [
    "WordActivityExtractor",
]

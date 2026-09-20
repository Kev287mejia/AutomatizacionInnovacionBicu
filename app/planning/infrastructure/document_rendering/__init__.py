"""
Paquete de Renderizado de Documentos — Infraestructura de Planificación.

Fuente: FASE_29_5_2 §14, §17.
Implementa adaptadores para la generación física de documentos institucionales.
"""
from app.planning.infrastructure.document_rendering.docx_renderer import (
    DocxMethodologicalDocumentRenderer,
    DocumentRenderingError,
)

__all__ = [
    "DocxMethodologicalDocumentRenderer",
    "DocumentRenderingError",
]

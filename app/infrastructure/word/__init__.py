"""app.infrastructure.word

Adaptadores de infraestructura para la generación de documentos Word institucionales.

Este paquete contiene las implementaciones concretas de los puertos Word
definidos en app.application.ports.word_document_port.

Permite importar python-docx y los renderizadores patrimoniales
(app.word_consolidator.*) sin violar la restricción de la capa Application.
"""

from app.infrastructure.word.institutional_docx_adapter import (
    InstitutionalDocxActividadAdapter,
    InstitutionalDocxInformeSemanalAdapter,
    InstitutionalDocxDossierAdapter,
)

__all__ = [
    "InstitutionalDocxActividadAdapter",
    "InstitutionalDocxInformeSemanalAdapter",
    "InstitutionalDocxDossierAdapter",
]

"""app.application.ports.word_activity_extractor

Puerto abstracto de salida (Output Port) para la extracción estructurada de actividades Word (.docx).

Define el contrato que desacopla la capa de Aplicación de cualquier librería
de manipulación de documentos físicos (python-docx, etc.).

La capa Application NUNCA importa docx directamente.
Toda operación de lectura de documentos Word se realiza exclusivamente a través de este puerto.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Union

from app.application.dto.word_extraction_dtos import (
    WordActivityExtractionResultDTO,
)


class IWordActivityExtractor(ABC):
    """Puerto de salida: extrae datos estructurados de un informe de actividad Word."""

    @abstractmethod
    def extract(self, file_path: Union[str, Path]) -> WordActivityExtractionResultDTO:
        """Lee un archivo Word (.docx) y extrae sus tablas y secciones estructuradas.

        Args:
            file_path: Ruta al archivo .docx en el sistema de archivos.

        Returns:
            WordActivityExtractionResultDTO con Ficha Técnica (Tabla 1), Matriz Cuantitativa
            (Tabla 2), secciones narrativas, evidencias detectadas y diagnóstico técnico.
        """
        ...

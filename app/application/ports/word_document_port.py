"""app.application.ports.word_document_port

Puerto de salida (Output Port) para la generación de documentos Word institucionales.

Define el contrato abstracto que desacopla la capa Application de cualquier
implementación concreta de renderizado DOCX (python-docx, etc.).

La capa Application NUNCA importa python-docx directamente.
Toda operación de renderizado DOCX se realiza exclusivamente a través de este puerto.
"""

import io
from abc import ABC, abstractmethod
from typing import Optional, Union
from pathlib import Path

from app.application.word_acl.dtos import (
    WordActividadDTO,
    WordWeeklyReportDataset,
)


class IWordActividadRenderer(ABC):
    """Puerto de salida: renderiza un WordActividadDTO como documento DOCX.

    Producto individual de actividad (Informe Individual de Actividad).
    """

    @abstractmethod
    def render(
        self,
        actividad_dto: WordActividadDTO,
        output_path: Optional[Union[str, Path]] = None,
    ) -> io.BytesIO:
        """Genera el DOCX de informe individual para una actividad.

        Args:
            actividad_dto: DTO adaptado de la actividad para presentación Word.
            output_path: Ruta opcional de escritura en disco.

        Returns:
            BytesIO con el contenido DOCX generado.
        """
        ...


class IWordInformeSemanalRenderer(ABC):
    """Puerto de salida: renderiza un WordWeeklyReportDataset como DOCX.

    Producto B: Informe Semanal Ejecutivo Institucional.
    """

    @abstractmethod
    def render(
        self,
        dataset: WordWeeklyReportDataset,
        output_path: Optional[Union[str, Path]] = None,
    ) -> io.BytesIO:
        """Genera el DOCX del informe semanal ejecutivo.

        Args:
            dataset: Dataset completo adaptado para presentación Word.
            output_path: Ruta opcional de escritura en disco.

        Returns:
            BytesIO con el contenido DOCX generado.
        """
        ...


class IWordDossierRenderer(ABC):
    """Puerto de salida: renderiza un dossier consolidado multi-actividad como DOCX.

    Producto C: Dossier Consolidado de actividades en un período.
    """

    @abstractmethod
    def render(
        self,
        dataset: WordWeeklyReportDataset,
        output_path: Optional[Union[str, Path]] = None,
    ) -> io.BytesIO:
        """Genera el DOCX del dossier consolidado.

        Args:
            dataset: Dataset consolidado adaptado para presentación Word.
            output_path: Ruta opcional de escritura en disco.

        Returns:
            BytesIO con el contenido DOCX generado.
        """
        ...

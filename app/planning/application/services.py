"""
Servicios de Aplicación — Módulo de Planificación y Diseño Metodológico.

Fase 29.5.4 — Integración Controlada Planning V003 → Document Model → DOCX.
Orquesta el flujo técnico entre los puertos de persistencia (repositorios),
el modelo de dominio puro, la transformación a DTO y el puerto de renderizado DOCX.

REGLAS DE AISLAMIENTO:
  - Cero dependencias hacia SQLite o infraestructura concreta (inversión de dependencias).
  - Cero dependencias hacia app.word_consolidator (núcleo protegido).
  - Cero dependencias hacia servicios de IA.
  - Único camino central de exportación: export_design().
"""
from __future__ import annotations

from typing import Optional
import uuid

from app.planning.domain.entities import MethodologicalDesign
from app.planning.domain.ports import (
    MethodologicalDesignRepositoryPort,
    MethodologicalDocumentRendererPort,
)


class MethodologicalDocumentExportService:
    """Servicio de aplicación para exportar Diseños Metodológicos a documentos DOCX.

    Mantiene un único camino central de exportación:
      export_by_id()             ──┐
                                   ├──> export_design() ──> design.to_dto() ──> renderer.render()
      export_by_activity_ref()   ──┘
    """

    def __init__(
        self,
        design_repository: MethodologicalDesignRepositoryPort,
        renderer: MethodologicalDocumentRendererPort,
    ) -> None:
        """Inicializa el servicio inyectando los puertos requeridos.

        Args:
            design_repository: Puerto de acceso a datos para consultar diseños.
            renderer: Puerto para renderizar el DTO en un documento físico.
        """
        self._design_repo = design_repository
        self._renderer = renderer

    def export_design(
        self,
        design: MethodologicalDesign,
        output_path: str,
        objectives_heading: str = "OBJETIVOS DEL TALLER ARTÍSTICO",
        program_section_label: str = "III. PROGRAMA",
        matrix_section_label: str = "VI. MATRIZ DE PLANIFICACIÓN",
    ) -> str:
        """Camino central único: transforma el agregado a DTO y delega al renderer.

        Args:
            design: Agregado de dominio MethodologicalDesign.
            output_path: Ruta de destino en el sistema de archivos.
            objectives_heading: Encabezado del bloque de objetivos.
            program_section_label: Encabezado de la tabla de programa/agenda.
            matrix_section_label: Encabezado de la matriz operativa.

        Returns:
            Ruta canónica del archivo DOCX generado.

        Raises:
            ValueError: Si design es nulo.
            DocumentRenderingError: Si ocurre un error durante el renderizado.
        """
        if design is None:
            raise ValueError("El diseño metodológico a exportar no puede ser nulo.")

        dto = design.to_dto(
            objectives_heading=objectives_heading,
            program_section_label=program_section_label,
            matrix_section_label=matrix_section_label,
        )
        return self._renderer.render(dto, output_path)

    def export_by_id(
        self,
        design_id: uuid.UUID,
        output_path: str,
        objectives_heading: str = "OBJETIVOS DEL TALLER ARTÍSTICO",
        program_section_label: str = "III. PROGRAMA",
        matrix_section_label: str = "VI. MATRIZ DE PLANIFICACIÓN",
    ) -> str:
        """Recupera el diseño por su UUID y delega a export_design()."""
        design = self._design_repo.get_by_id(design_id)
        if design is None:
            raise ValueError(f"No se encontró diseño metodológico con ID '{design_id}'.")

        return self.export_design(
            design=design,
            output_path=output_path,
            objectives_heading=objectives_heading,
            program_section_label=program_section_label,
            matrix_section_label=matrix_section_label,
        )

    def export_by_activity_ref(
        self,
        planned_activity_ref: str,
        output_path: str,
        objectives_heading: str = "OBJETIVOS DEL TALLER ARTÍSTICO",
        program_section_label: str = "III. PROGRAMA",
        matrix_section_label: str = "VI. MATRIZ DE PLANIFICACIÓN",
    ) -> str:
        """Recupera el diseño por la referencia institucional de la actividad y delega a export_design()."""
        design = self._design_repo.get_by_activity_ref(planned_activity_ref)
        if design is None:
            raise ValueError(
                f"No se encontró diseño metodológico para la actividad planificada con referencia '{planned_activity_ref}'."
            )

        return self.export_design(
            design=design,
            output_path=output_path,
            objectives_heading=objectives_heading,
            program_section_label=program_section_label,
            matrix_section_label=matrix_section_label,
        )

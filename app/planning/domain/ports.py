"""
Puertos Abstractos del Dominio — Modulo Planificacion -> Diseno Metodologico.

Fuente arquitectonica:
  FASE_29_2_DISENO_ARQUITECTONICO_PLANIFICACION_DISENO.md §15, §17, §20
  Fase 29.3 — Implementacion del Dominio Puro

Clasificacion: DECISION ARQUITECTONICA (contratos de inversion de dependencias).

Estos puertos son INTERFACES ABSTRACTAS puras (ABC / Protocol).
REGLAS ABSOLUTAS DE ESTA FASE:
  - NO crear implementaciones SQLite.
  - NO crear implementaciones Gemini / OpenRouter / Ollama / HTTP.
  - NO crear implementaciones python-docx / docx-template.
  - Cero dependencias de infraestructura en el dominio.
"""
from __future__ import annotations

import abc
import uuid
from typing import Any, Optional, Sequence

from app.planning.domain.dtos import MethodologicalDesignDTO, PlanningSourceReadResultDTO
from app.planning.domain.entities import MethodologicalDesign, PlannedActivity
from app.planning.domain.value_objects import AIProposal, CatalogReference


class PlannedActivityRepositoryPort(abc.ABC):
    """Puerto abstracto para lectura de actividades planificadas.

    Fuente: FASE_29_2 §11, §20.
    Clasificacion: DECISION ARQUITECTONICA.

    PlannedActivity es de SOLO LECTURA en este modulo.
    """

    @abc.abstractmethod
    def get_by_internal_id(self, activity_internal_id: uuid.UUID) -> Optional[PlannedActivity]:
        """Obtiene una actividad por su UUID tecnico interno (D-04)."""
        raise NotImplementedError

    @abc.abstractmethod
    def get_by_planning_id(self, planning_id: str) -> Optional[PlannedActivity]:
        """Obtiene una actividad por su clave natural institucional (D-04)."""
        raise NotImplementedError

    @abc.abstractmethod
    def list_all(self) -> Sequence[PlannedActivity]:
        """Lista todas las actividades planificadas disponibles."""
        raise NotImplementedError


class MethodologicalDesignRepositoryPort(abc.ABC):
    """Puerto abstracto para persistencia y consulta de Disenos Metodologicos.

    Fuente: FASE_29_2 §9, §22.
    Clasificacion: DECISION ARQUITECTONICA.
    """

    @abc.abstractmethod
    def get_by_id(self, design_id: uuid.UUID) -> Optional[MethodologicalDesign]:
        """Obtiene un diseno metodologico por su UUID."""
        raise NotImplementedError

    @abc.abstractmethod
    def get_by_activity_id(self, activity_internal_id: uuid.UUID) -> Sequence[MethodologicalDesign]:
        """Obtiene todos los disenos asociados a una actividad planificada."""
        raise NotImplementedError

    @abc.abstractmethod
    def get_by_activity_ref(self, planned_activity_ref: str) -> Optional[MethodologicalDesign]:
        """Obtiene el diseño metodológico vigente asociado a una referencia institucional."""
        raise NotImplementedError

    @abc.abstractmethod
    def save(self, design: MethodologicalDesign) -> None:
        """Persiste un diseno metodologico (creacion o actualizacion)."""
        raise NotImplementedError


class CatalogRepositoryPort(abc.ABC):
    """Puerto abstracto para consulta de catalogos institucionales C1 a C5.

    Fuente: FASE_29_1, FASE_29_2 §13 (R-08).
    Clasificacion: EVIDENCIA DIRECTA (catalogos) + DECISION ARQUITECTONICA (puerto).
    """

    @abc.abstractmethod
    def get_catalog_entries(self, catalog_name: str) -> Sequence[CatalogReference]:
        """Obtiene todas las entradas de un catalogo por su nombre o codigo (C1-C5)."""
        raise NotImplementedError

    @abc.abstractmethod
    def is_valid_code(self, catalog_name: str, code: str) -> bool:
        """Valida si un codigo pertenece al catalogo especificado."""
        raise NotImplementedError


class AIAssistancePort(abc.ABC):
    """Puerto abstracto para el servicio de asistencia narrativa por IA.

    Fuente: FASE_29_2 §14.
    Clasificacion: DECISION ARQUITECTONICA.

    REGLAS DE CONTENCION ESTRICTA:
      - Solo asiste campos narrativos/pedagogicos permitidos:
        introduction, methodological_approach, objective_1, objective_2,
        operative_goal, procedure.
      - PROHIBIDO acceder o generar campos cuantitativos o institucionales:
        activity_name, sede, area_responsable, participant_goals,
        eje_estrategia, programa, tipo_evento, total_minutes, etc.
      - Toda respuesta debe encapsularse en un AIProposal con requires_review=True.
    """

    @abc.abstractmethod
    def generate_narrative_proposal(
        self,
        target_field: str,
        source_inputs: dict[str, Any],
    ) -> AIProposal:
        """Genera una propuesta narrativa para un campo permitido.

        Args:
            target_field: Campo destino (debe ser uno de los permitidos por R-AI-01).
            source_inputs: Diccionario de entradas permitidas para trazabilidad.

        Returns:
            AIProposal con requires_review=True y accepted=None.

        Raises:
            ValueError: Si target_field no es un campo permitido para IA.
        """
        raise NotImplementedError


class MethodologicalDocumentRendererPort(abc.ABC):
    """Puerto abstracto para la generacion del documento DOCX final.

    Fuente: FASE_29_2 §17.
    Clasificacion: DECISION ARQUITECTONICA.

    PRINCIPIO: Ceguera a Reglas.
      El renderer recibe un MethodologicalDesignDTO completamente validado
      y es responsable unicamente de la estructura, tablas y estilos visuales.
    """

    @abc.abstractmethod
    def render(self, design_dto: MethodologicalDesignDTO, output_path: str) -> str:
        """Renderiza el diseno a un archivo DOCX y retorna el path generado.

        Args:
            design_dto: Contrato de datos inmutable y previamente validado.
            output_path: Ruta de destino para el archivo .docx.

        Returns:
            Ruta del archivo generado.
        """
        raise NotImplementedError


class PlanningSourceReaderPort(abc.ABC):
    """Puerto abstracto para la lectura de fuentes externas de planificacion (POA).

    Fuente: FASE_29_7 §5.
    Clasificacion: DECISION ARQUITECTONICA.

    PRINCIPIO: Ceguera a Infraestructura de Persistencia.
      El reader solo abre, analiza y normaliza tecnicamente el archivo externo (Excel),
      retornando PlanningSourceReadResultDTO sin acoplamiento a base de datos ni modelos de ejecucion.
    """

    @abc.abstractmethod
    def read_planning_source(
        self,
        file_path: str,
        sheet_name: Optional[str] = None,
    ) -> PlanningSourceReadResultDTO:
        """Lee un archivo institucional de planificacion y retorna los datos tecnicamente normalizados.

        Args:
            file_path: Ruta al archivo Excel institucional.
            sheet_name: Nombre especifico de la hoja a procesar (opcional).

        Returns:
            PlanningSourceReadResultDTO con actividades procesadas, advertencias y errores estructurales.
        """
        raise NotImplementedError


class PlanningUnitOfWorkPort(abc.ABC):
    """Puerto abstracto para la Unidad de Trabajo Satelite de Planificacion.

    Fuente: FASE_29_7 §10, FASE_29_4_2.
    Clasificacion: DECISION ARQUITECTONICA.
    """

    @property
    @abc.abstractmethod
    def planned_activities(self) -> PlannedActivityRepositoryPort:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def methodological_designs(self) -> MethodologicalDesignRepositoryPort:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def catalogs(self) -> CatalogRepositoryPort:
        raise NotImplementedError

    @abc.abstractmethod
    def __enter__(self) -> "PlanningUnitOfWorkPort":
        raise NotImplementedError

    @abc.abstractmethod
    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def commit(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def rollback(self) -> None:
        raise NotImplementedError
